from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import config
from medha.core.schema import repair_lesson
from medha.lesson import (
    ChatMessage,
    GenerationError,
    GenerationRequest,
    LessonCache,
    LessonGenerator,
    StepEvent,
    estimate_duration_s,
    extract_json_object,
    llm_lesson_schema,
    llm_outline_schema,
    llm_step_lesson_schema,
    make_lesson_id,
    parse_lesson_json,
    sanitize_latex,
    sanitize_payload,
    sanitize_text,
)
from medha.lesson.__main__ import main


def valid_payload() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "lesson_id": "model-chosen",
        "title": "Newton's Second Law",
        "subject": "physics",
        "target_concept": "newton_second_law",
        "difficulty": "beginner",
        "style_id": "default",
        "steps": [
            {
                "id": "s1",
                "concept": "force and acceleration",
                "narration": (
                    "Force equals mass times acceleration. "
                    "It connects force, mass, and acceleration."
                ),
                "board": [
                    {
                        "op": "write_text",
                        "id": "a1",
                        "text": "Newton's Second Law",
                        "region": "title",
                        "start": {"sentence": 0, "char": 0},
                    },
                    {
                        "op": "write_math",
                        "id": "a2",
                        "latex": "F = m a",
                        "rect": {"x": 0.06, "y": 0.22, "w": 0.4, "h": 0.14},
                        "start": {"sentence": 1, "char": 0},
                    },
                ],
            },
            {
                "id": "s2",
                "concept": "inverse relationship with mass",
                "narration": (
                    "If mass doubles, acceleration halves at the same force. "
                    "Let us check that idea."
                ),
                "board": [
                    {
                        "op": "write_text",
                        "id": "a3",
                        "text": "More mass -> less acceleration",
                        "rect": {"x": 0.06, "y": 0.5, "w": 0.4, "h": 0.1},
                    }
                ],
                "checkpoint": None,
            },
        ],
        "meta": {},
    }


def make_hit(index: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        chunk_id=f"{'a' * 12}-c{index:04d}",
        doc_id="a" * 64,
        text="Newton's second law says force equals mass times acceleration.",
        citation=f"physics.pdf, page {index + 1}",
        source="physics.pdf",
        page_start=index + 1,
        page_end=index + 1,
        heading_path=("Newton",),
        token_count=12,
        vector_score=0.9,
        rerank_score=0.8,
        score=0.8,
    )


class FakeClient:
    model = "fake-qwen"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        format_schema: dict[str, Any] | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        self.calls.append(
            {
                "messages": copy.deepcopy(messages),
                "schema": format_schema,
                "options": options,
            }
        )
        index = len(self.calls) - 1
        if index >= len(self.responses):
            raise AssertionError("unexpected extra model call")
        return self.responses[index]


class FakeRetriever:
    def __init__(self, hits: list[Any], *, reranked: bool = True) -> None:
        self.hits = hits
        self.reranked = reranked
        self.queries: list[str] = []
        self.rerank_calls: list[bool] = []
        self.closed = 0

    def close(self) -> None:
        self.closed += 1

    def query(
        self,
        text: str,
        *,
        top_k: int | None = None,
        candidates: int | None = None,
        rerank: bool = True,
    ) -> SimpleNamespace:
        self.queries.append(text)
        self.rerank_calls.append(rerank)
        return SimpleNamespace(hits=self.hits, reranked=self.reranked)


class OomRetriever:
    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1

    def query(
        self,
        _text: str,
        *,
        top_k: int | None = None,
        candidates: int | None = None,
        rerank: bool = True,
    ) -> SimpleNamespace:
        del top_k, candidates, rerank
        raise OSError(22, "The paging file is too small for this operation")


def test_generate_falls_back_when_retrieval_runs_out_of_memory(
    tmp_path: Path,
) -> None:
    client = FakeClient([json.dumps(valid_payload())])
    retriever = OomRetriever()
    generator = LessonGenerator(
        client=client,
        retriever=retriever,
        cache=LessonCache(tmp_path),
    )
    result = generator.generate(
        GenerationRequest(topic="Newton's second law", steps=2),
        use_cache=False,
    )

    assert len(result.lesson.steps) == 2
    assert any("out of memory" in warning for warning in result.warnings)
    assert retriever.closed == 1


def test_generate_grounds_prompt_and_fills_meta(tmp_path: Path) -> None:
    client = FakeClient([json.dumps(valid_payload())])
    retriever = FakeRetriever([make_hit(0)])
    generator = LessonGenerator(
        client=client,
        retriever=retriever,
        cache=LessonCache(tmp_path),
    )
    request = GenerationRequest(topic="Newton's second law", subject="physics", steps=2)
    result = generator.generate(request, use_cache=False)

    assert not result.cached
    assert result.attempts == 1
    assert result.retrieved == 1
    assert result.material_chars > 0
    assert result.lesson.subject == "physics"
    assert result.lesson.meta.model == "fake-qwen"
    assert result.lesson.meta.prompt_version == config.LESSON_PROMPT_VERSION
    assert result.lesson.meta.sources == ["physics.pdf, page 1"]
    assert result.lesson.meta.material_hash
    assert result.lesson.lesson_id != "model-chosen"
    assert result.lesson.lesson_id.startswith("newton-s-second-law-")
    assert retriever.queries == ["Newton's second law"]
    assert retriever.rerank_calls == [True]
    assert retriever.closed == 1
    first_call = client.calls[0]
    assert first_call["schema"] == llm_lesson_schema()
    prompt = "\n".join(message["content"] for message in first_call["messages"])
    assert "[S1] physics.pdf, page 1" in prompt
    assert "force equals mass times acceleration" in prompt


def test_reranker_fallback_is_reported(tmp_path: Path) -> None:
    client = FakeClient([json.dumps(valid_payload())])
    retriever = FakeRetriever([make_hit()], reranked=False)
    generator = LessonGenerator(
        client=client,
        retriever=retriever,
        cache=LessonCache(tmp_path),
    )
    result = generator.generate(
        GenerationRequest(topic="Newton's second law", steps=2),
        use_cache=False,
    )
    assert any("reranker" in warning for warning in result.warnings)


def test_generate_uses_cache(tmp_path: Path) -> None:
    client = FakeClient([json.dumps(valid_payload())])
    retriever = FakeRetriever([make_hit()])
    cache = LessonCache(tmp_path)
    generator = LessonGenerator(client=client, retriever=retriever, cache=cache)
    request = GenerationRequest(topic="Newton's second law", steps=2)

    first = generator.generate(request)
    second = generator.generate(request)

    assert not first.cached
    assert second.cached
    assert len(client.calls) == 1
    assert second.lesson == first.lesson
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_generate_without_rag_warns(tmp_path: Path) -> None:
    client = FakeClient([json.dumps(valid_payload())])
    generator = LessonGenerator(
        client=client,
        retriever=FakeRetriever([]),
        cache=LessonCache(tmp_path),
    )
    result = generator.generate(
        GenerationRequest(topic="Newton's second law", steps=2, use_rag=False),
        use_cache=False,
    )
    assert result.retrieved == 0
    assert result.lesson.meta.sources == []
    assert any("disabled" in warning for warning in result.warnings)


def test_invalid_action_is_dropped(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["steps"][0]["board"].append({"op": "draw", "id": "a9", "shape": "arrow"})
    client = FakeClient([json.dumps(payload)])
    generator = LessonGenerator(
        client=client,
        retriever=FakeRetriever([]),
        cache=LessonCache(tmp_path),
    )
    result = generator.generate(
        GenerationRequest(topic="Newton's second law", steps=2, use_rag=False),
        use_cache=False,
    )
    assert len(result.lesson.steps[0].board) == 2
    assert result.attempts == 1
    assert any("a9" in warning for warning in result.warnings)


def test_wrong_step_count_is_retried(tmp_path: Path) -> None:
    short = valid_payload()
    short["steps"] = short["steps"][:1]
    client = FakeClient([json.dumps(short), json.dumps(valid_payload())])
    generator = LessonGenerator(
        client=client,
        retriever=FakeRetriever([]),
        cache=LessonCache(tmp_path),
    )
    result = generator.generate(
        GenerationRequest(topic="Newton's second law", steps=2, use_rag=False),
        use_cache=False,
    )
    assert result.attempts == 2
    assert len(result.lesson.steps) == 2
    assert any("exactly 2" in warning for warning in result.warnings)


def test_invalid_response_is_retried(tmp_path: Path) -> None:
    client = FakeClient(["not json", json.dumps(valid_payload())])
    generator = LessonGenerator(
        client=client,
        retriever=FakeRetriever([]),
        cache=LessonCache(tmp_path),
    )
    result = generator.generate(
        GenerationRequest(topic="Newton's second law", steps=2, use_rag=False),
        use_cache=False,
    )
    assert result.attempts == 2
    assert any("retried" in warning for warning in result.warnings)
    assert len(client.calls[1]["messages"]) == 3


def test_invalid_response_fails_after_attempts(tmp_path: Path) -> None:
    client = FakeClient(["not json", "still not json"])
    generator = LessonGenerator(
        client=client,
        retriever=FakeRetriever([]),
        cache=LessonCache(tmp_path),
    )
    with pytest.raises(GenerationError, match="invalid lesson"):
        generator.generate(
            GenerationRequest(topic="Newton's second law", use_rag=False),
            use_cache=False,
        )


def test_missing_fields_are_defaulted(tmp_path: Path) -> None:
    payload = valid_payload()
    del payload["title"]
    del payload["target_concept"]
    del payload["lesson_id"]
    client = FakeClient([json.dumps(payload)])
    generator = LessonGenerator(
        client=client,
        retriever=FakeRetriever([]),
        cache=LessonCache(tmp_path),
    )
    result = generator.generate(
        GenerationRequest(topic="Force and motion", steps=2, use_rag=False),
        use_cache=False,
    )
    assert result.lesson.title == "Force and motion"
    assert result.lesson.target_concept == "force-and-motion"


def test_generate_stepwise_emits_one_step_at_a_time(tmp_path: Path) -> None:
    outline = {
        "title": "Newton's Second Law",
        "target_concept": "newton_second_law",
        "steps": [
            {"concept": "force and acceleration"},
            {"concept": "mass changes acceleration"},
        ],
    }
    first = valid_payload()
    first["steps"] = first["steps"][:1]
    second = valid_payload()
    second["steps"] = second["steps"][1:]
    client = FakeClient([json.dumps(outline), json.dumps(first), json.dumps(second)])
    retriever = FakeRetriever([make_hit()])
    generator = LessonGenerator(
        client=client,
        retriever=retriever,
        cache=LessonCache(tmp_path),
    )
    events: list[StepEvent] = []
    closed_at_steps: list[int] = []

    def on_step(event: StepEvent) -> None:
        events.append(event)
        closed_at_steps.append(retriever.closed)

    result = generator.generate_stepwise(
        GenerationRequest(topic="Newton's second law", subject="physics", steps=2),
        on_step,
        use_cache=False,
    )

    assert closed_at_steps == [1, 1]
    assert [event.index for event in events] == [0, 1]
    assert [len(event.lesson.steps) for event in events] == [1, 2]
    assert events[0].step.id == "s1"
    assert events[1].step.id == "s2"
    assert len(result.lesson.steps) == 2
    assert result.lesson.steps[0].id == "s1"
    assert result.lesson.steps[1].id == "s2"
    actions = [
        action.id for step in result.lesson.steps for action in step.board
    ]
    assert len(actions) == len(set(actions))
    assert client.calls[0]["schema"] == llm_outline_schema()
    assert client.calls[1]["schema"] == llm_step_lesson_schema()
    assert client.calls[2]["schema"] == llm_step_lesson_schema()
    assert retriever.queries == [
        "Newton's second law",
        "Newton's second law force and acceleration",
        "Newton's second law mass changes acceleration",
    ]
    assert retriever.closed == 1
    assert result.lesson.meta.sources


def test_generate_stepwise_continues_when_retrieval_runs_out_of_memory(
    tmp_path: Path,
) -> None:
    outline = {
        "title": "Newton's Second Law",
        "target_concept": "newton_second_law",
        "steps": [
            {"concept": "force and acceleration"},
            {"concept": "mass changes acceleration"},
        ],
    }
    first = valid_payload()
    first["steps"] = first["steps"][:1]
    second = valid_payload()
    second["steps"] = second["steps"][1:]
    client = FakeClient([json.dumps(outline), json.dumps(first), json.dumps(second)])
    retriever = OomRetriever()
    generator = LessonGenerator(
        client=client,
        retriever=retriever,
        cache=LessonCache(tmp_path),
    )
    events: list[StepEvent] = []

    result = generator.generate_stepwise(
        GenerationRequest(topic="Newton's second law", steps=2),
        events.append,
        use_cache=False,
    )

    assert [event.index for event in events] == [0, 1]
    assert len(result.lesson.steps) == 2
    assert any("out of memory" in warning for warning in result.warnings)
    assert retriever.closed == 1


def test_parse_json_fences_and_braces() -> None:
    raw = 'Here is the lesson:\n```json\n{"title": "A {brace}", "n": 1}\n```'
    assert parse_lesson_json(raw) == {"title": "A {brace}", "n": 1}
    assert parse_lesson_json('{"lesson": {"title": "wrapped"}}') == {"title": "wrapped"}


def test_extract_incomplete_json_fails() -> None:
    with pytest.raises(ValueError, match="incomplete"):
        extract_json_object('{"a": 1')
    with pytest.raises(ValueError, match="no JSON"):
        extract_json_object("nothing")


def test_lesson_id_is_deterministic() -> None:
    request = GenerationRequest(topic="Newton's second law", steps=2)
    first = make_lesson_id(request, "a" * 64)
    second = make_lesson_id(request, "a" * 64)
    third = make_lesson_id(request, "b" * 64)
    assert first == second
    assert first != third
    assert first.startswith("newton-s-second-law-")


def test_estimate_duration() -> None:
    lesson, issues = repair_lesson(valid_payload())
    assert issues == []
    assert estimate_duration_s(lesson) > 0


def test_sanitize_model_text_and_latex() -> None:
    assert sanitize_text("F = m \u00d7 a at 3 m/s\u00b2 \ufffd") == "F = m times a at 3 m/s^2"
    assert sanitize_latex("F = 2 \\times 3 \\text{ N}") == "F = 2 \\times 3 \\mathrm{ N}"
    assert sanitize_latex("m/s\u00b2") == "m/s^2"
    payload = sanitize_payload({"latex": "a\u00d7b", "text": "a\u00d7b"})
    assert payload == {"latex": "a \\times b", "text": "a times b"}


def test_cache_round_trip_and_corruption(tmp_path: Path) -> None:
    lesson, _ = repair_lesson(valid_payload())
    cache = LessonCache(tmp_path)
    key = "a" * 64
    cache.save(key, lesson)
    assert cache.load(key) == lesson

    cache.path_for(key).write_text("not json", encoding="utf-8")
    assert cache.load(key) is None
    assert cache.clear() == 1


def test_cache_rejects_unsafe_key(tmp_path: Path) -> None:
    cache = LessonCache(tmp_path)
    with pytest.raises(ValueError, match="cache key"):
        cache.path_for("../secret")


def test_cli_rejects_material_with_no_rag() -> None:
    assert main(["generate", "--topic", "Force", "--material", "x.pdf", "--no-rag"]) == 2
