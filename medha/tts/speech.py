"""Sentence-level speech generation, cache, and lesson audio assembly."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

import config
from medha.core.schema import LessonScript, LessonStep, split_sentences

logger = logging.getLogger(__name__)


class Synthesizer(Protocol):
    voice: str
    speed: float

    def synthesize(self, text: str) -> np.ndarray: ...


@dataclass(frozen=True)
class SpeechTrack:
    audio: np.ndarray
    sample_rate: int
    sentence_ms: tuple[tuple[int, ...], ...]
    lead_ms: int
    sentence_gap_ms: int
    step_gap_ms: int
    voice: str
    speed: float

    @property
    def duration_ms(self) -> int:
        return round(len(self.audio) / self.sample_rate * 1000)

    def write_wav(self, path: Path) -> Path:
        import soundfile as sf

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(path), self.audio, self.sample_rate, subtype="PCM_16")
        return path


@dataclass(frozen=True)
class SpeechChunk:
    """Speech for one lesson step, without the lesson-level lead or step gap."""

    step_index: int
    audio: np.ndarray
    sample_rate: int
    sentence_ms: tuple[int, ...]
    voice: str
    speed: float

    @property
    def duration_ms(self) -> int:
        return round(len(self.audio) / self.sample_rate * 1000)


def _cache_key(
    text: str,
    voice: str,
    speed: float,
    sample_rate: int,
    engine: str = "kokoro",
) -> str:
    payload = "|".join(
        (
            config.TTS_CACHE_VERSION,
            engine,
            config.KOKORO_REVISION,
            voice,
            f"{speed:.6f}",
            str(sample_rate),
            text,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SpeechCache:
    """Per-sentence WAV cache; a miss never requires the lesson model to load."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir is not None else config.TTS_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _paths(self, key: str) -> tuple[Path, Path]:
        return self.cache_dir / f"{key}.wav", self.cache_dir / f"{key}.json"

    def load(
        self,
        text: str,
        voice: str,
        speed: float,
        sample_rate: int,
        engine: str = "kokoro",
    ) -> np.ndarray | None:
        import soundfile as sf

        key = _cache_key(text, voice, speed, sample_rate, engine)
        wav_path, meta_path = self._paths(key)
        if not wav_path.is_file() or not meta_path.is_file():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("sample_rate") != sample_rate:
                return None
            data, actual_rate = sf.read(str(wav_path), dtype="float32", always_2d=False)
        except (OSError, ValueError, json.JSONDecodeError):
            logger.warning("Ignoring unreadable TTS cache entry %s", wav_path)
            return None
        if actual_rate != sample_rate:
            return None
        return np.asarray(data, dtype=np.float32).reshape(-1)

    def store(
        self,
        text: str,
        voice: str,
        speed: float,
        sample_rate: int,
        samples: np.ndarray,
        engine: str = "kokoro",
    ) -> None:
        import soundfile as sf

        key = _cache_key(text, voice, speed, sample_rate, engine)
        wav_path, meta_path = self._paths(key)
        sample_data = np.asarray(samples, dtype=np.float32).reshape(-1)
        tmp_wav = wav_path.with_suffix(".tmp.wav")
        tmp_meta = meta_path.with_suffix(".tmp.json")
        sf.write(str(tmp_wav), sample_data, sample_rate, subtype="PCM_16")
        meta = {
            "version": config.TTS_CACHE_VERSION,
            "text": text,
            "voice": voice,
            "speed": speed,
            "engine": engine,
            "sample_rate": sample_rate,
            "duration_ms": round(len(sample_data) / sample_rate * 1000),
        }
        tmp_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        tmp_wav.replace(wav_path)
        tmp_meta.replace(meta_path)


def _silence(sample_rate: int, duration_ms: int) -> np.ndarray:
    count = max(0, round(sample_rate * duration_ms / 1000))
    return np.zeros(count, dtype=np.float32)


def _resolve_engine(
    engine: Synthesizer | None,
    *,
    voice: str,
    speed: float,
) -> tuple[Synthesizer, str, str]:
    if engine is None:
        from .kokoro import KokoroEngine

        engine = KokoroEngine(voice=voice, speed=speed)
    elif getattr(engine, "voice", voice) != voice:
        raise ValueError(f"engine voice is {engine.voice!r}, expected {voice!r}")
    elif getattr(engine, "speed", speed) != speed:
        raise ValueError(f"engine speed is {engine.speed!r}, expected {speed!r}")
    resolved_voice = str(getattr(engine, "voice", voice))
    engine_id = str(getattr(engine, "engine_id", "kokoro"))
    return engine, resolved_voice, engine_id


def _resolve_cache(cache: SpeechCache | None, use_cache: bool) -> SpeechCache | None:
    if not use_cache:
        return None
    return cache if cache is not None else SpeechCache()


def synthesize_step(
    step: LessonStep,
    *,
    step_index: int = 0,
    engine: Synthesizer | None = None,
    cache: SpeechCache | None = None,
    use_cache: bool = True,
    voice: str = config.KOKORO_VOICE,
    speed: float = config.KOKORO_SPEED,
    sample_rate: int = config.TTS_SAMPLE_RATE,
    sentence_gap_ms: int = config.TTS_SENTENCE_GAP_MS,
) -> SpeechChunk:
    """Synthesize one step so playback can start before the rest is ready."""
    narration = step.narration
    engine, voice, engine_id = _resolve_engine(engine, voice=voice, speed=speed)
    cache = _resolve_cache(cache, use_cache)
    sentences = split_sentences(narration)
    parts: list[np.ndarray] = []
    durations: list[int] = []
    for sentence_index, sentence in enumerate(sentences):
        samples = (
            cache.load(sentence, voice, speed, sample_rate, engine_id)
            if cache is not None
            else None
        )
        if samples is None:
            samples = engine.synthesize(sentence)
            if samples.size == 0:
                raise RuntimeError(f"empty speech for sentence: {sentence!r}")
            if cache is not None:
                cache.store(sentence, voice, speed, sample_rate, samples, engine_id)
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        durations.append(round(samples.size / sample_rate * 1000))
        parts.append(samples)
        if sentence_index < len(sentences) - 1:
            parts.append(_silence(sample_rate, sentence_gap_ms))
    audio = np.concatenate(parts).astype(np.float32) if parts else np.zeros(0, dtype=np.float32)
    return SpeechChunk(
        step_index=step_index,
        audio=audio,
        sample_rate=sample_rate,
        sentence_ms=tuple(durations),
        voice=voice,
        speed=speed,
    )


def synthesize_lesson(
    lesson: LessonScript,
    engine: Synthesizer | None = None,
    cache: SpeechCache | None = None,
    use_cache: bool = True,
    voice: str = config.KOKORO_VOICE,
    speed: float = config.KOKORO_SPEED,
    sample_rate: int = config.TTS_SAMPLE_RATE,
    lead_ms: int = config.TTS_LEAD_MS,
    sentence_gap_ms: int = config.TTS_SENTENCE_GAP_MS,
    step_gap_ms: int = config.TTS_STEP_GAP_MS,
) -> SpeechTrack:
    """Generate or load every sentence and assemble a playable lesson track."""
    resolved_speed = float(speed)
    engine, voice, _engine_id = _resolve_engine(engine, voice=voice, speed=resolved_speed)
    cache = _resolve_cache(cache, use_cache)

    parts: list[np.ndarray] = [np.zeros(0, dtype=np.float32)]
    if lead_ms > 0:
        parts.append(_silence(sample_rate, lead_ms))
    sentence_ms: list[tuple[int, ...]] = []
    for step_index, step in enumerate(lesson.steps):
        chunk = synthesize_step(
            step,
            step_index=step_index,
            engine=engine,
            cache=cache,
            use_cache=use_cache,
            voice=voice,
            speed=resolved_speed,
            sample_rate=sample_rate,
            sentence_gap_ms=sentence_gap_ms,
        )
        sentence_ms.append(chunk.sentence_ms)
        parts.append(chunk.audio)
        if step_index < len(lesson.steps) - 1:
            parts.append(_silence(sample_rate, step_gap_ms))

    audio = np.concatenate(parts).astype(np.float32)
    return SpeechTrack(
        audio=audio,
        sample_rate=sample_rate,
        sentence_ms=tuple(sentence_ms),
        lead_ms=max(0, lead_ms),
        sentence_gap_ms=max(0, sentence_gap_ms),
        step_gap_ms=max(0, step_gap_ms),
        voice=voice,
        speed=resolved_speed,
    )
