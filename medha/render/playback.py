"""Reusable lesson playback: board visuals, audio clock, pause and seek."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import config
from medha.core.schema import LessonScript, LessonStep, split_sentences
from medha.tts.audio import AudioPlayer, StreamingAudioPlayer
from medha.tts.speech import SpeechChunk, SpeechTrack, synthesize_lesson

from .actions import ActionVisual, build_visuals, render_frame
from .scene import Board
from .timeline import (
    CheckpointTiming,
    Timeline,
    build_timeline,
    estimate_sentence_ms,
)


@dataclass(frozen=True)
class PreparedPlayback:
    lesson: LessonScript
    visuals: dict[str, ActionVisual]
    timeline: Timeline
    track: SpeechTrack | None = None
    tail_ms: int = 1200

    @property
    def duration_ms(self) -> int:
        audio_ms = self.track.duration_ms if self.track is not None else 0
        return max(self.timeline.total_ms, audio_ms) + max(0, self.tail_ms)


def prepare_playback(
    lesson: LessonScript,
    *,
    use_tts: bool = False,
    speech_track: SpeechTrack | None = None,
    voice: str = config.KOKORO_VOICE,
    speed: float = config.KOKORO_SPEED,
    tail_ms: int = 1200,
) -> PreparedPlayback:
    visuals = build_visuals(lesson)
    track = speech_track
    if track is None and use_tts:
        track = synthesize_lesson(lesson, voice=voice, speed=speed)
    if track is not None:
        timeline = build_timeline(
            lesson,
            sentence_ms=[list(step) for step in track.sentence_ms],
            step_gap_ms=track.step_gap_ms,
            sentence_gap_ms=track.sentence_gap_ms,
            lead_ms=track.lead_ms,
        )
    else:
        timeline = build_timeline(lesson)
    return PreparedPlayback(
        lesson=lesson,
        visuals=visuals,
        timeline=timeline,
        track=track,
        tail_ms=max(0, tail_ms),
    )


class LessonPlayback:
    """Render a prepared lesson and keep the board locked to its audio clock."""

    def __init__(self, prepared: PreparedPlayback, *, play_audio: bool = True) -> None:
        self.prepared = prepared
        self._player = (
            AudioPlayer(
                prepared.track.audio,
                prepared.track.sample_rate,
                enabled=play_audio,
            )
            if prepared.track is not None
            else None
        )
        self._position_ms = 0
        self._started_at: float | None = None
        self._playing = False
        self._fired_checkpoints: set[str] = set()

    @property
    def duration_ms(self) -> int:
        return self.prepared.duration_ms

    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def audio_error(self) -> str | None:
        return self._player.last_error if self._player is not None else None

    @property
    def visuals(self) -> dict[str, ActionVisual]:
        return self.prepared.visuals

    @property
    def timeline(self) -> Timeline:
        return self.prepared.timeline

    def position_ms(self) -> int:
        if not self._playing or self._started_at is None:
            return self._position_ms
        elapsed = int((time.perf_counter() - self._started_at) * 1000)
        return min(self.duration_ms, self._position_ms + max(0, elapsed))

    def is_finished(self) -> bool:
        return self.position_ms() >= self.duration_ms

    def start(self) -> None:
        if self._playing:
            return
        if self._position_ms >= self.duration_ms:
            self._position_ms = 0
            self._fired_checkpoints.clear()
        self._started_at = time.perf_counter()
        self._playing = True
        if self._player is not None:
            self._player.start(self._position_ms)

    def pause(self) -> None:
        if not self._playing:
            return
        self._position_ms = self.position_ms()
        self._playing = False
        self._started_at = None
        if self._player is not None:
            self._player.stop()

    def stop(self) -> None:
        self._playing = False
        self._started_at = None
        self._position_ms = 0
        self._fired_checkpoints.clear()
        if self._player is not None:
            self._player.stop()

    def seek(self, position_ms: int) -> None:
        target = max(0, min(self.duration_ms, int(position_ms)))
        was_playing = self._playing
        if self._player is not None:
            self._player.stop()
        self._position_ms = target
        for checkpoint in self.timeline.checkpoints:
            if checkpoint.at_ms < target:
                self._fired_checkpoints.add(checkpoint.step_id)
            else:
                self._fired_checkpoints.discard(checkpoint.step_id)
        if was_playing:
            self._playing = False
            self.start()

    def take_checkpoint(self, position_ms: int | None = None) -> CheckpointTiming | None:
        """Return the next due checkpoint once, so the UI can pause and ask."""
        position = self.position_ms() if position_ms is None else int(position_ms)
        for checkpoint in self.timeline.checkpoints:
            if checkpoint.step_id in self._fired_checkpoints:
                continue
            if checkpoint.at_ms <= position:
                self._fired_checkpoints.add(checkpoint.step_id)
                return checkpoint
        return None

    def reset_checkpoints(self) -> None:
        self._fired_checkpoints.clear()

    def render(self, board: Board) -> None:
        render_frame(board, self.prepared.visuals, self.prepared.timeline, self.position_ms())

    def render_at(self, board: Board, position_ms: int) -> None:
        render_frame(
            board,
            self.prepared.visuals,
            self.prepared.timeline,
            max(0, min(self.duration_ms, int(position_ms))),
        )

    def write_audio(self, path: Path) -> Path | None:
        if self.prepared.track is None:
            return None
        return self.prepared.track.write_wav(path)


class ChunkedPlayback:
    """Playback that grows one step at a time as generation and TTS finish."""

    def __init__(
        self,
        lesson: LessonScript,
        *,
        play_audio: bool = True,
        voice: str = config.KOKORO_VOICE,
        speed: float = config.KOKORO_SPEED,
        sample_rate: int = config.TTS_SAMPLE_RATE,
        lead_ms: int = config.TTS_LEAD_MS,
        sentence_gap_ms: int = config.TTS_SENTENCE_GAP_MS,
        step_gap_ms: int = config.TTS_STEP_GAP_MS,
        tail_ms: int = 1200,
    ) -> None:
        self._header = lesson.model_copy(update={"steps": []})
        self._voice = voice
        self._speed = speed
        self._sample_rate = sample_rate
        self._lead_ms = max(0, lead_ms)
        self._sentence_gap_ms = max(0, sentence_gap_ms)
        self._step_gap_ms = max(0, step_gap_ms)
        self._tail_ms = max(0, tail_ms)
        self._chunks: list[SpeechChunk] = []
        self._steps: list[LessonStep] = []
        self._prepared = self._build_prepared()
        self._player = StreamingAudioPlayer(sample_rate, enabled=play_audio)
        self._playing = False
        self._complete = False
        self._fired_checkpoints: set[str] = set()
        self._lock = threading.RLock()

    @property
    def prepared(self) -> PreparedPlayback:
        with self._lock:
            return self._prepared

    @property
    def duration_ms(self) -> int:
        with self._lock:
            return self._prepared.duration_ms + (self._tail_ms if self._complete else 0)

    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def complete(self) -> bool:
        with self._lock:
            return self._complete

    @property
    def buffering(self) -> bool:
        return self._player.buffering

    @property
    def audio_error(self) -> str | None:
        return self._player.last_error

    @property
    def visuals(self) -> dict[str, ActionVisual]:
        with self._lock:
            return self._prepared.visuals

    @property
    def timeline(self) -> Timeline:
        with self._lock:
            return self._prepared.timeline

    def append(self, step: LessonStep, chunk: SpeechChunk | None = None) -> None:
        if any(existing.id == step.id for existing in self._steps):
            return
        if chunk is None:
            chunk = self._silent_chunk(step, len(self._steps))
        if chunk.sample_rate != self._sample_rate:
            raise ValueError(
                f"speech chunk sample rate is {chunk.sample_rate}, expected {self._sample_rate}"
            )
        with self._lock:
            if self._complete:
                raise RuntimeError("cannot append a step after playback is complete")
            first = not self._chunks
            self._steps.append(step)
            self._chunks.append(chunk)
            if first and self._lead_ms:
                self._player.append(self._silence(self._lead_ms))
            self._player.append(chunk.audio)
            if self._step_gap_ms:
                self._player.append(self._silence(self._step_gap_ms))
            self._prepared = self._build_prepared()

    def mark_complete(self) -> None:
        with self._lock:
            if self._complete:
                return
            self._complete = True
            target_ms = self._prepared.duration_ms + self._tail_ms
            extra_ms = max(0, target_ms - self._player.duration_ms)
            if extra_ms:
                self._player.append(self._silence(extra_ms))

    def position_ms(self) -> int:
        with self._lock:
            return min(self.duration_ms, self._player.position_ms())

    def is_finished(self) -> bool:
        with self._lock:
            return self._complete and self.position_ms() >= self.duration_ms

    def start(self) -> None:
        with self._lock:
            if self._playing:
                return
            if self.position_ms() >= self.duration_ms:
                self._player.seek(0)
                self._fired_checkpoints.clear()
            self._player.start()
            self._playing = True

    def pause(self) -> None:
        with self._lock:
            if not self._playing:
                return
            self._player.pause()
            self._playing = False

    def stop(self) -> None:
        with self._lock:
            self._player.stop()
            self._playing = False
            self._fired_checkpoints.clear()

    def seek(self, position_ms: int) -> None:
        with self._lock:
            target = max(0, min(self.duration_ms, int(position_ms)))
            self._player.seek(target)
            for checkpoint in self._prepared.timeline.checkpoints:
                if checkpoint.at_ms < target:
                    self._fired_checkpoints.add(checkpoint.step_id)
                else:
                    self._fired_checkpoints.discard(checkpoint.step_id)

    def take_checkpoint(self, position_ms: int | None = None) -> CheckpointTiming | None:
        with self._lock:
            position = self.position_ms() if position_ms is None else int(position_ms)
            for checkpoint in self._prepared.timeline.checkpoints:
                if checkpoint.step_id in self._fired_checkpoints:
                    continue
                if checkpoint.at_ms <= position:
                    self._fired_checkpoints.add(checkpoint.step_id)
                    return checkpoint
            return None

    def reset_checkpoints(self) -> None:
        with self._lock:
            self._fired_checkpoints.clear()

    def render(self, board: Board) -> None:
        with self._lock:
            render_frame(
                board,
                self._prepared.visuals,
                self._prepared.timeline,
                self.position_ms(),
            )

    def render_at(self, board: Board, position_ms: int) -> None:
        with self._lock:
            render_frame(
                board,
                self._prepared.visuals,
                self._prepared.timeline,
                max(0, min(self.duration_ms, int(position_ms))),
            )

    def write_audio(self, path: Path) -> Path | None:
        with self._lock:
            if self._prepared.track is None:
                return None
            return self._prepared.track.write_wav(path)

    def _build_prepared(self) -> PreparedPlayback:
        lesson = self._header.model_copy(update={"steps": list(self._steps)})
        track = self._build_track()
        timeline = build_timeline(
            lesson,
            sentence_ms=[list(chunk.sentence_ms) for chunk in self._chunks],
            step_gap_ms=self._step_gap_ms,
            sentence_gap_ms=self._sentence_gap_ms,
            lead_ms=self._lead_ms,
        )
        return PreparedPlayback(
            lesson=lesson,
            visuals=build_visuals(lesson),
            timeline=timeline,
            track=track,
            tail_ms=0,
        )

    def _build_track(self) -> SpeechTrack:
        parts: list[np.ndarray] = []
        if self._chunks and self._lead_ms:
            parts.append(self._silence(self._lead_ms))
        for chunk in self._chunks:
            parts.append(chunk.audio)
            if self._step_gap_ms:
                parts.append(self._silence(self._step_gap_ms))
        audio = (
            np.concatenate(parts).astype(np.float32)
            if parts
            else np.zeros(0, dtype=np.float32)
        )
        return SpeechTrack(
            audio=audio,
            sample_rate=self._sample_rate,
            sentence_ms=tuple(chunk.sentence_ms for chunk in self._chunks),
            lead_ms=self._lead_ms,
            sentence_gap_ms=self._sentence_gap_ms,
            step_gap_ms=self._step_gap_ms,
            voice=self._voice,
            speed=self._speed,
        )

    def _silent_chunk(self, step: LessonStep, step_index: int) -> SpeechChunk:
        durations = tuple(
            estimate_sentence_ms(sentence) for sentence in split_sentences(step.narration)
        )
        parts: list[np.ndarray] = []
        for index, duration_ms in enumerate(durations):
            parts.append(self._silence(duration_ms))
            if index < len(durations) - 1 and self._sentence_gap_ms:
                parts.append(self._silence(self._sentence_gap_ms))
        audio = (
            np.concatenate(parts).astype(np.float32)
            if parts
            else np.zeros(0, dtype=np.float32)
        )
        return SpeechChunk(
            step_index=step_index,
            audio=audio,
            sample_rate=self._sample_rate,
            sentence_ms=durations,
            voice=self._voice,
            speed=self._speed,
        )

    def _silence(self, duration_ms: int) -> np.ndarray:
        return np.zeros(
            round(self._sample_rate * max(0, duration_ms) / 1000),
            dtype=np.float32,
        )
