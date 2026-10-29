from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from medha.core.schema import LessonScript, split_sentences, validate_lesson
from medha.render.geometry import Transform
from medha.render.playback import ChunkedPlayback, LessonPlayback, prepare_playback
from medha.render.scene import Board
from medha.tts.speech import SpeechChunk, SpeechTrack

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "spec" / "board-action" / "v1" / "examples" / "newton.json"


def load_lesson() -> LessonScript:
    return validate_lesson(json.loads(EXAMPLE.read_text(encoding="utf-8")))


def fake_track(lesson: LessonScript) -> SpeechTrack:
    sentence_ms = tuple(
        tuple(500 for _ in split_sentences(step.narration)) for step in lesson.steps
    )
    return SpeechTrack(
        audio=np.zeros(24000, dtype=np.float32),
        sample_rate=24000,
        sentence_ms=sentence_ms,
        lead_ms=250,
        sentence_gap_ms=0,
        step_gap_ms=0,
        voice="af_heart",
        speed=1.0,
    )


def test_prepare_uses_speech_track_timing() -> None:
    lesson = load_lesson()
    prepared = prepare_playback(lesson, speech_track=fake_track(lesson))
    assert prepared.timeline.actions["a1"].start_ms == 250
    assert prepared.duration_ms > prepared.timeline.total_ms
    assert prepared.track is not None


def test_playback_pause_resume_seek_and_stop() -> None:
    prepared = prepare_playback(load_lesson(), use_tts=False)
    playback = LessonPlayback(prepared, play_audio=False)
    assert playback.position_ms() == 0
    assert not playback.playing

    playback.start()
    time.sleep(0.03)
    position = playback.position_ms()
    assert 10 <= position < 1000
    playback.pause()
    assert not playback.playing
    assert playback.position_ms() == position

    time.sleep(0.01)
    assert playback.position_ms() == position

    playback.seek(1000)
    assert playback.position_ms() == 1000
    playback.start()
    time.sleep(0.02)
    assert playback.position_ms() >= 1000
    playback.stop()
    assert playback.position_ms() == 0
    assert not playback.playing


def test_seek_is_clamped_and_frame_renders() -> None:
    prepared = prepare_playback(load_lesson(), use_tts=False)
    playback = LessonPlayback(prepared, play_audio=False)
    playback.seek(playback.duration_ms + 5000)
    assert playback.position_ms() == playback.duration_ms
    assert playback.is_finished()

    board = Board()
    playback.render(board)
    mesh = board.build(Transform(1600, 900))
    assert mesh.vertex_count > 0


def test_finished_playback_restarts_from_zero() -> None:
    prepared = prepare_playback(load_lesson(), use_tts=False)
    playback = LessonPlayback(prepared, play_audio=False)
    playback.seek(playback.duration_ms)
    playback.start()
    assert playback.position_ms() < 100
    playback.stop()


def chunk_for(step: object, step_index: int, *, gap_ms: int = 50) -> SpeechChunk:
    from medha.core.schema import LessonStep
    from medha.tts.speech import split_sentences

    assert isinstance(step, LessonStep)
    durations = tuple(100 for _ in split_sentences(step.narration))
    parts: list[np.ndarray] = []
    for index in range(len(durations)):
        parts.append(np.zeros(2400, dtype=np.float32))
        if index < len(durations) - 1:
            parts.append(np.zeros(round(24000 * gap_ms / 1000), dtype=np.float32))
    return SpeechChunk(
        step_index=step_index,
        audio=np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32),
        sample_rate=24000,
        sentence_ms=durations,
        voice="af_heart",
        speed=1.0,
    )


def test_chunked_playback_grows_while_playing() -> None:
    lesson = validate_lesson(
        {
            "schema_version": "1.0.0",
            "lesson_id": "chunked-demo",
            "title": "Chunked demo",
            "subject": "general",
            "steps": [
                {"id": "s1", "concept": "one", "narration": "One."},
                {"id": "s2", "concept": "two", "narration": "Two."},
            ],
        }
    )
    first, second = lesson.steps[:2]
    playback = ChunkedPlayback(
        lesson,
        play_audio=False,
        lead_ms=100,
        sentence_gap_ms=50,
        step_gap_ms=200,
        tail_ms=1200,
    )
    assert playback.duration_ms == 0
    assert not playback.is_finished()

    playback.append(first, chunk_for(first, 0))
    assert len(playback.prepared.lesson.steps) == 1
    assert playback.prepared.track is not None
    assert playback.timeline.total_ms == 400
    assert not playback.is_finished()

    playback.start()
    time.sleep(0.02)
    assert 1 <= playback.position_ms() < 400
    playback.pause()
    paused = playback.position_ms()
    playback.append(second, chunk_for(second, 1))
    assert len(playback.prepared.lesson.steps) == 2
    assert playback.timeline.total_ms == 700
    assert playback.position_ms() == paused

    playback.mark_complete()
    assert playback.duration_ms == playback.timeline.total_ms + 1200
    assert playback.prepared.track.duration_ms == playback.timeline.total_ms
    playback.seek(playback.duration_ms)
    assert playback.is_finished()

    playback.stop()
    assert playback.position_ms() == 0
    assert not playback.is_finished()
