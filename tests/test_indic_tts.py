"""English audio selection, cache separation, and optional Indic fallback."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import config
from medha.core.schema import LessonScript
from medha.lesson.store import load_lesson
from medha.tts.indic import IndicParlerEngine
from medha.tts.speech import SpeechCache, synthesize_lesson


def _lesson() -> LessonScript:
    return load_lesson(config.LESSON_CONTENT_DIR / "newton.json")


def test_indic_engine_has_language_specific_voice() -> None:
    engine = IndicParlerEngine("hi")
    assert engine.voice == "indic-hi"
    assert engine.engine_id == "indic-parler"


def test_indic_engine_reports_missing_optional_dependencies() -> None:
    engine = IndicParlerEngine("kn")
    with pytest.raises(RuntimeError, match=r"requirements/indic\.txt"):
        engine.synthesize("ಒಂದು ವಾಕ್ಯ.")


def test_cache_separates_engines(tmp_path: Path) -> None:
    cache = SpeechCache(tmp_path)
    samples = np.ones(480, dtype=np.float32)

    cache.store("hello", "voice", 1.0, 24000, samples, "kokoro")
    assert cache.load("hello", "voice", 1.0, 24000, "kokoro") is not None
    assert cache.load("hello", "voice", 1.0, 24000, "indic-parler") is None


class FakeKokoroEngine:
    engine_id = "fake-kokoro"
    speed = 1.0

    def __init__(self, *, voice: str, speed: float) -> None:
        self.voice = voice
        self.speed = speed

    def synthesize(self, text: str) -> np.ndarray:
        return np.ones(240, dtype=np.float32)


class _UnexpectedIndicEngine:
    def __init__(self, **_kwargs: object) -> None:
        raise AssertionError("Indic speech is deferred; lessons must use Kokoro")


def test_translated_lesson_keeps_english_audio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lesson = _lesson().model_copy(update={"language": "hi"})
    monkeypatch.setattr("medha.tts.kokoro.KokoroEngine", FakeKokoroEngine)
    monkeypatch.setattr("medha.tts.indic.IndicParlerEngine", _UnexpectedIndicEngine)

    track = synthesize_lesson(lesson, use_cache=False)

    assert track.voice == config.KOKORO_VOICE
    assert track.sample_rate == config.TTS_SAMPLE_RATE
