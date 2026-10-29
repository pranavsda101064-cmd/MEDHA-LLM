from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from medha.core.schema import LessonScript, validate_lesson
from medha.render.timeline import build_timeline
from medha.tts.audio import AudioPlayer, StreamingAudioPlayer
from medha.tts.speech import SpeechCache, synthesize_lesson, synthesize_step


class FakeEngine:
    voice = "af_heart"
    speed = 1.0

    def __init__(self) -> None:
        self.calls: list[str] = []

    def synthesize(self, text: str) -> np.ndarray:
        self.calls.append(text)
        count = len(text) * 24
        return np.linspace(0.0, 0.1, count, dtype=np.float32)


def make_lesson() -> LessonScript:
    return validate_lesson(
        {
            "schema_version": "1.0.0",
            "lesson_id": "tts-demo",
            "title": "TTS demo",
            "subject": "general",
            "steps": [
                {
                    "id": "s1",
                    "concept": "first",
                    "narration": "One two. Three four.",
                    "board": [
                        {
                            "op": "write_text",
                            "id": "a1",
                            "text": "One",
                            "start": {"sentence": 0, "char": 0},
                        },
                        {
                            "op": "write_text",
                            "id": "a2",
                            "text": "Three",
                            "start": {"sentence": 1, "char": 0},
                        },
                    ],
                },
                {
                    "id": "s2",
                    "concept": "second",
                    "narration": "Five six.",
                    "board": [
                        {
                            "op": "write_text",
                            "id": "a3",
                            "text": "Five",
                            "start": {"sentence": 0, "char": 0},
                        }
                    ],
                },
            ],
        }
    )


def test_synthesize_lesson_builds_audio_and_real_timings(tmp_path: Path) -> None:
    engine = FakeEngine()
    track = synthesize_lesson(
        make_lesson(),
        engine=engine,
        cache=SpeechCache(tmp_path),
        lead_ms=100,
        sentence_gap_ms=50,
        step_gap_ms=200,
    )
    assert engine.calls == ["One two.", "Three four.", "Five six."]
    assert track.sentence_ms == ((8, 11), (9,))
    assert track.audio.size == 9072
    assert track.duration_ms == 378
    assert track.sample_rate == 24000


def test_sentence_cache_avoids_second_synthesis(tmp_path: Path) -> None:
    lesson = make_lesson()
    cache = SpeechCache(tmp_path)
    first = FakeEngine()
    track_one = synthesize_lesson(lesson, engine=first, cache=cache)
    second = FakeEngine()
    track_two = synthesize_lesson(lesson, engine=second, cache=cache)
    assert first.calls
    assert second.calls == []
    assert track_one.sentence_ms == track_two.sentence_ms
    assert np.allclose(track_one.audio, track_two.audio, atol=1e-4)


def test_timeline_matches_audio_gaps_and_lead(tmp_path: Path) -> None:
    track = synthesize_lesson(
        make_lesson(),
        engine=FakeEngine(),
        cache=SpeechCache(tmp_path),
        lead_ms=100,
        sentence_gap_ms=50,
        step_gap_ms=200,
    )
    timeline = build_timeline(
        make_lesson(),
        sentence_ms=[list(step) for step in track.sentence_ms],
        lead_ms=track.lead_ms,
        sentence_gap_ms=track.sentence_gap_ms,
        step_gap_ms=track.step_gap_ms,
    )
    assert timeline.actions["a1"].start_ms == 100
    assert timeline.actions["a2"].start_ms == 158
    assert timeline.actions["a3"].start_ms == 369


def test_speech_track_writes_wav(tmp_path: Path) -> None:
    track = synthesize_lesson(
        make_lesson(),
        engine=FakeEngine(),
        cache=SpeechCache(tmp_path / "cache"),
    )
    output = track.write_wav(tmp_path / "lesson.wav")
    assert output.is_file()
    import soundfile as sf

    data, sample_rate = sf.read(str(output), dtype="float32")
    assert sample_rate == track.sample_rate
    assert len(data) == track.audio.size


def test_audio_player_clock_is_clamped_when_disabled() -> None:
    player = AudioPlayer(np.zeros(2400, dtype=np.float32), 24000, enabled=False)
    assert player.duration_ms == 100
    assert player.position_ms() == 0
    player.start()
    time.sleep(0.02)
    position = player.position_ms()
    assert 1 <= position <= 100
    assert player.clock_ms() >= position
    player.stop()

    short = AudioPlayer(np.zeros(1, dtype=np.float32), 24000, enabled=False)
    short.start()
    time.sleep(0.005)
    assert short.position_ms() == 0
    assert short.clock_ms() >= 1
    short.stop()


def test_engine_voice_mismatch_is_rejected(tmp_path: Path) -> None:
    engine = FakeEngine()
    engine.voice = "bf_emma"
    with pytest.raises(ValueError, match="engine voice"):
        synthesize_lesson(make_lesson(), engine=engine, cache=SpeechCache(tmp_path))


def test_synthesize_step_returns_only_that_step(tmp_path: Path) -> None:
    engine = FakeEngine()
    chunk = synthesize_step(
        make_lesson().steps[0],
        step_index=0,
        engine=engine,
        cache=SpeechCache(tmp_path),
        sentence_gap_ms=50,
    )
    assert engine.calls == ["One two.", "Three four."]
    assert chunk.step_index == 0
    assert chunk.sentence_ms == (8, 11)
    assert chunk.duration_ms == 69
    assert chunk.audio.size == 1656


def test_streaming_audio_clock_survives_appends_and_pause() -> None:
    player = StreamingAudioPlayer(24000, enabled=False)
    assert player.duration_ms == 0
    assert not player.buffering
    player.append(np.zeros(2400, dtype=np.float32))
    assert player.duration_ms == 100
    player.start()
    time.sleep(0.02)
    assert 1 <= player.position_ms() <= 100
    player.pause()
    paused = player.position_ms()
    time.sleep(0.01)
    assert player.position_ms() == paused

    player.append(np.zeros(2400, dtype=np.float32))
    assert player.duration_ms == 200
    assert player.position_ms() == paused
    player.start()
    time.sleep(0.02)
    assert player.position_ms() >= paused
    player.seek(150)
    assert player.position_ms() == 150
    player.stop()
    assert player.position_ms() == 0
