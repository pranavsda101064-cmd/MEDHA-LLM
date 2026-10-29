from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import config
from medha.lesson import (
    ChatMessage,
    LessonCache,
    LessonGenerator,
    list_lessons,
    load_lesson,
    save_lesson,
)
from medha.render.playback import ChunkedPlayback, LessonPlayback
from medha.studio.service import StudioOptions, generate_lesson, open_lesson

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "spec" / "board-action" / "v1" / "examples" / "newton.json"


def test_options_request_uses_material() -> None:
    options = StudioOptions(
        topic="Force",
        subject="physics",
        difficulty="beginner",
        steps=3,
        materials=(ROOT / "sample.pdf",),
        use_rag=False,
    )
    request = options.request()
    assert request.use_rag
    assert request.steps == 3
    assert request.subject == "physics"


def test_lesson_files_round_trip(tmp_path: Path) -> None:
    lesson = load_lesson(EXAMPLE)
    path = save_lesson(lesson, tmp_path / "lesson.json")
    assert path.is_file()
    assert load_lesson(path) == lesson
    assert list_lessons(tmp_path) == [path]


def test_open_lesson_prepares_playback_without_tts() -> None:
    result = open_lesson(EXAMPLE, StudioOptions(topic="Newton", tts=False))
    assert result.lesson.lesson_id == "newton2-demo"
    assert result.path == EXAMPLE
    assert result.playback.duration_ms > 0
    assert result.playback.prepared.track is None
    assert result.report.ok
    assert result.tts_error is None
    assert not result.playback.playing


class FakeEngine:
    voice = "af_heart"
    speed = 1.0

    def __init__(self, **_kwargs: object) -> None:
        pass

    def synthesize(self, text: str) -> np.ndarray:
        return np.zeros(len(text) * 24, dtype=np.float32)


class FakeSpeechCache:
    def load(self, *_args: object, **_kwargs: object) -> None:
        return None

    def store(self, *_args: object, **_kwargs: object) -> None:
        return None


class ScriptedClient:
    model = "fake-qwen"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def chat(
        self,
        _messages: Sequence[ChatMessage],
        *,
        format_schema: dict[str, Any] | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        del format_schema, options
        response = self.responses[self.calls]
        self.calls += 1
        return response


def _step_payload(step_id: str, concept: str, text: str, *, title: bool) -> str:
    board: dict[str, Any] = {
        "op": "write_text",
        "id": "body",
        "text": text,
        "duration_ms": 800,
    }
    if title:
        board["region"] = "title"
    else:
        board["rect"] = {"x": 0.06, "y": 0.24, "w": 0.4, "h": 0.1}
    return json.dumps(
        {
            "schema_version": "1.0.0",
            "lesson_id": "model-chosen",
            "title": "Newton's Second Law",
            "steps": [
                {
                    "id": step_id,
                    "concept": concept,
                    "narration": f"{text} is the key idea.",
                    "board": [board],
                }
            ],
        }
    )


def test_generate_stepwise_emits_partial_playback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "LESSON_CONTENT_DIR", tmp_path)
    monkeypatch.setattr("medha.tts.kokoro.KokoroEngine", FakeEngine)
    monkeypatch.setattr("medha.tts.speech.SpeechCache", FakeSpeechCache)
    outline = json.dumps(
        {
            "title": "Newton's Second Law",
            "target_concept": "newton_second_law",
            "steps": [
                {"concept": "force and acceleration"},
                {"concept": "mass changes acceleration"},
            ],
        }
    )
    client = ScriptedClient(
        [
            outline,
            _step_payload("s1", "force", "Force causes acceleration", title=True),
            _step_payload("s2", "mass", "More mass means less acceleration", title=False),
        ]
    )
    real_generator = LessonGenerator
    monkeypatch.setattr(
        "medha.studio.service.LessonGenerator",
        lambda **_kwargs: real_generator(
            client=client,
            cache=LessonCache(tmp_path / "cache"),
        ),
    )
    snapshots: list[tuple[int, bool, int]] = []

    def collect(playback: ChunkedPlayback) -> None:
        snapshots.append(
            (
                len(playback.prepared.lesson.steps),
                playback.complete,
                playback.timeline.total_ms,
            )
        )

    result = generate_lesson(
        StudioOptions(
            topic="Newton's second law",
            subject="physics",
            steps=2,
            use_rag=False,
            use_cache=False,
        ),
        partial=collect,
    )

    assert len(snapshots) == 2
    assert snapshots[0][0] == 1
    assert snapshots[0][1] is False
    assert snapshots[0][2] > 0
    assert [snapshot[0] for snapshot in snapshots] == [1, 2]
    assert result.path == tmp_path / f"{result.lesson.lesson_id}.json"
    assert result.path.is_file()
    assert isinstance(result.playback, ChunkedPlayback)
    assert result.playback.complete
    assert result.generation is not None
    assert len(result.lesson.steps) == 2
    assert result.tts_error is None
    assert client.calls == 3


def test_generate_stepwise_works_without_tts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "LESSON_CONTENT_DIR", tmp_path)
    outline = json.dumps(
        {
            "title": "Newton's Second Law",
            "target_concept": "newton_second_law",
            "steps": [
                {"concept": "force and acceleration"},
                {"concept": "mass changes acceleration"},
            ],
        }
    )
    client = ScriptedClient(
        [
            outline,
            _step_payload("s1", "force", "Force causes acceleration", title=True),
            _step_payload("s2", "mass", "More mass means less acceleration", title=False),
        ]
    )
    real_generator = LessonGenerator
    monkeypatch.setattr(
        "medha.studio.service.LessonGenerator",
        lambda **_kwargs: real_generator(
            client=client,
            cache=LessonCache(tmp_path / "cache"),
        ),
    )
    snapshots: list[int] = []

    result = generate_lesson(
        StudioOptions(
            topic="Newton's second law",
            subject="physics",
            steps=2,
            use_rag=False,
            use_cache=False,
            tts=False,
        ),
        partial=lambda playback: snapshots.append(
            len(playback.prepared.lesson.steps)
        ),
    )

    assert snapshots == [1, 2]
    assert isinstance(result.playback, ChunkedPlayback)
    assert result.playback.complete
    assert result.tts_error is None
    assert client.calls == 3


def test_generate_stepwise_falls_back_after_partial_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "LESSON_CONTENT_DIR", tmp_path)
    monkeypatch.setattr("medha.tts.kokoro.KokoroEngine", FakeEngine)
    monkeypatch.setattr("medha.tts.speech.SpeechCache", FakeSpeechCache)
    outline = json.dumps(
        {
            "title": "Newton's Second Law",
            "target_concept": "newton_second_law",
            "steps": [
                {"concept": "force and acceleration"},
                {"concept": "mass changes acceleration"},
            ],
        }
    )
    first = json.loads(
        _step_payload("s1", "force", "Force causes acceleration", title=True)
    )
    second = json.loads(
        _step_payload(
            "s2",
            "mass",
            "More mass means less acceleration",
            title=False,
        )
    )
    full = json.dumps({**first, "steps": [first["steps"][0], second["steps"][0]]})
    client = ScriptedClient(
        [
            outline,
            json.dumps(first),
            "not json",
            "not json",
            full,
        ]
    )
    real_generator = LessonGenerator
    monkeypatch.setattr(
        "medha.studio.service.LessonGenerator",
        lambda **_kwargs: real_generator(
            client=client,
            cache=LessonCache(tmp_path / "cache"),
        ),
    )
    partials: list[ChunkedPlayback] = []

    result = generate_lesson(
        StudioOptions(
            topic="Newton's second law",
            subject="physics",
            steps=2,
            use_rag=False,
            use_cache=False,
        ),
        partial=partials.append,
    )

    assert len(partials) == 1
    assert isinstance(result.playback, LessonPlayback)
    assert result.playback.prepared.lesson.steps[0].id == "s1"
    assert len(result.lesson.steps) == 2
    assert any("full lesson fallback" in warning for warning in result.warnings)
    assert not result.playback.playing


def test_open_lesson_emits_partial_playback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("medha.tts.kokoro.KokoroEngine", FakeEngine)
    monkeypatch.setattr("medha.tts.speech.SpeechCache", FakeSpeechCache)
    snapshots: list[tuple[int, bool, int]] = []

    def collect(playback: ChunkedPlayback) -> None:
        snapshots.append(
            (
                len(playback.prepared.lesson.steps),
                playback.complete,
                playback.timeline.total_ms,
            )
        )

    result = open_lesson(
        EXAMPLE,
        StudioOptions(topic="Newton", tts=True),
        partial=collect,
    )

    assert len(snapshots) == len(result.lesson.steps)
    assert snapshots[0][0] == 1
    assert snapshots[0][1] is False
    assert snapshots[0][2] > 0
    assert [snapshot[0] for snapshot in snapshots] == list(
        range(1, len(result.lesson.steps) + 1)
    )
    assert isinstance(result.playback, ChunkedPlayback)
    assert result.playback.complete
    assert result.playback.prepared.track is not None
    assert result.tts_error is None
