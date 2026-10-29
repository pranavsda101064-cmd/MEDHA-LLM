"""Grounded lesson generation through a local Ollama model."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import ValidationError

import config
from medha.core.schema import LessonMeta, LessonScript, LessonStep, repair_lesson
from medha.rag.errors import is_memory_error

from .cache import LessonCache, cache_key
from .client import ChatClient, ChatMessage, OllamaClient
from .errors import GenerationError
from .layout import normalize_layout
from .models import (
    GenerationRequest,
    GenerationResult,
    LessonOutline,
    SourceExcerpt,
    StepEvent,
)
from .prompt import (
    build_messages,
    build_outline_messages,
    build_step_messages,
    retry_message,
)
from .schema import llm_lesson_schema, llm_outline_schema, llm_step_lesson_schema

StepCallback = Callable[[StepEvent], None]


class Retriever(Protocol):
    def query(
        self,
        text: str,
        *,
        top_k: int | None = None,
        candidates: int | None = None,
        rerank: bool = True,
    ) -> Any: ...


def extract_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        raise ValueError("response contained no JSON object")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise ValueError("response JSON was incomplete")


def parse_lesson_json(raw: str) -> dict[str, Any]:
    text = raw.lstrip("\ufeff").strip()
    payload = json.loads(extract_json_object(text))
    if not isinstance(payload, dict):
        raise ValueError("lesson JSON must be an object")
    if "steps" not in payload and isinstance(payload.get("lesson"), dict):
        payload = payload["lesson"]
    return payload


def parse_outline_json(raw: str, request: GenerationRequest) -> LessonOutline:
    payload = parse_lesson_json(raw)
    if "outline" in payload and isinstance(payload["outline"], dict):
        payload = payload["outline"]
    title = sanitize_text(str(payload.get("title", "")))[:200] or request.topic.strip()[:200]
    target = sanitize_text(str(payload.get("target_concept", "")))[:120]
    steps = payload.get("steps")
    if not isinstance(steps, list):
        raise ValueError("outline JSON has no steps list")
    if len(steps) != request.steps:
        raise ValueError(
            f"outline has {len(steps)} step(s) but exactly {request.steps} were requested"
        )
    concepts: list[str] = []
    for index, item in enumerate(steps, start=1):
        if isinstance(item, dict):
            concept = sanitize_text(str(item.get("concept", "")))
        else:
            concept = sanitize_text(str(item))
        if not concept:
            raise ValueError(f"outline step {index} has no concept")
        concepts.append(concept[:120])
    return LessonOutline(
        title=title,
        target_concept=target or _slug(request.topic),
        concepts=tuple(concepts),
    )


def _slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return value or "lesson"


def make_lesson_id(request: GenerationRequest, material_hash: str | None) -> str:
    seed = json.dumps(
        {
            "request": request.model_dump(mode="json"),
            "material": material_hash,
            "prompt": config.LESSON_PROMPT_VERSION,
            "cache": config.LESSON_CACHE_VERSION,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    suffix = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
    return f"{_slug(request.topic)[:40].rstrip('-')}-{suffix}"


def estimate_duration_s(lesson: LessonScript) -> float:
    total = 0.0
    for step in lesson.steps:
        words = len(re.findall(r"\b\w+\b", step.narration))
        speech = words / config.LESSON_SPEECH_WORDS_PER_SECOND
        board = sum(action.duration_ms for action in step.board) / 1000.0
        total += max(speech, board) + 0.2
    return round(total, 1)


def _excerpts_from_hits(hits: list[Any]) -> tuple[list[SourceExcerpt], bool]:
    excerpts: list[SourceExcerpt] = []
    seen: set[tuple[str, str]] = set()
    used = 0
    truncated = False
    for hit in hits:
        text = str(getattr(hit, "text", "")).strip()
        if not text:
            continue
        key = (str(getattr(hit, "citation", "")), text)
        if key in seen:
            continue
        seen.add(key)
        if len(text) > config.LESSON_MAX_CHUNK_CHARS:
            text = text[: config.LESSON_MAX_CHUNK_CHARS].rsplit(" ", 1)[0] + " ..."
            truncated = True
        excerpt = SourceExcerpt(
            citation=str(getattr(hit, "citation", "")),
            text=text,
            source=str(getattr(hit, "source", "")),
            page_start=getattr(hit, "page_start", None),
            page_end=getattr(hit, "page_end", None),
        )
        cost = len(excerpt.text) + len(excerpt.citation) + 24
        if excerpts and used + cost > config.LESSON_MAX_MATERIAL_CHARS:
            truncated = True
            break
        excerpts.append(excerpt)
        used += cost
    return excerpts, truncated


def _material_hash(excerpts: list[SourceExcerpt]) -> str | None:
    if not excerpts:
        return None
    sources = sorted({excerpt.source for excerpt in excerpts if excerpt.source})
    if not sources:
        sources = sorted({excerpt.citation for excerpt in excerpts})
    return hashlib.sha256("\n".join(sources).encode("utf-8")).hexdigest()


def _retrieval_fingerprint(excerpts: list[SourceExcerpt]) -> str:
    if not excerpts:
        return ""
    lines = [f"{excerpt.citation}\n{excerpt.text}" for excerpt in excerpts]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


_TEXT_REPLACEMENTS = {
    "\u00d7": " times ",
    "\u00b7": " * ",
    "\u00b2": "^2",
    "\u00b3": "^3",
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
    "\u2022": "-",
    "\u2192": "->",
    "\u2264": "<=",
    "\u2265": ">=",
    "\u2248": "~",
    "\u00a0": " ",
}
_LATEX_REPLACEMENTS = {
    "\u00d7": " \\times ",
    "\u00b7": " \\cdot ",
    "\u00b2": "^2",
    "\u00b3": "^3",
    "\u2212": "-",
    "\ufffd": "",
}


def sanitize_text(value: str) -> str:
    text = value.replace("\ufffd", "")
    for source, target in _TEXT_REPLACEMENTS.items():
        text = text.replace(source, target)
    return re.sub(r"[ \t]+", " ", text).strip()


def sanitize_latex(value: str) -> str:
    text = value.replace("\\text{", "\\mathrm{").replace("\\dfrac", "\\frac")
    for source, target in _LATEX_REPLACEMENTS.items():
        text = text.replace(source, target)
    return re.sub(r"[ \t]+", " ", text).strip()


def sanitize_payload(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, str):
        return sanitize_latex(value) if key == "latex" else sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, dict):
        return {name: sanitize_payload(item, key=name) for name, item in value.items()}
    return value


def repair_with_drops(payload: dict[str, Any]) -> tuple[LessonScript, list[str]]:
    data = copy.deepcopy(payload)
    issues: list[str] = []
    for _ in range(20):
        try:
            lesson, repair_issues = repair_lesson(data)
            return lesson, issues + repair_issues
        except ValidationError as exc:
            removals: dict[int, set[int]] = {}
            drop_checkpoints: set[int] = set()
            for error in exc.errors():
                location = error.get("loc", ())
                if (
                    len(location) >= 4
                    and location[0] == "steps"
                    and location[2] == "board"
                ):
                    try:
                        step_index = int(location[1])
                        action_index = int(location[3])
                    except (TypeError, ValueError):
                        continue
                    removals.setdefault(step_index, set()).add(action_index)
                elif (
                    len(location) >= 3
                    and location[0] == "steps"
                    and location[2] == "checkpoint"
                ):
                    try:
                        drop_checkpoints.add(int(location[1]))
                    except (TypeError, ValueError):
                        continue
            if not removals and not drop_checkpoints:
                raise
            steps = data.get("steps")
            if not isinstance(steps, list):
                raise
            for step_index in sorted(drop_checkpoints):
                if 0 <= step_index < len(steps) and isinstance(steps[step_index], dict):
                    steps[step_index]["checkpoint"] = None
                    issues.append(f"dropped invalid checkpoint in step {step_index + 1}")
            for step_index, action_indexes in removals.items():
                if not (0 <= step_index < len(steps)):
                    continue
                step = steps[step_index]
                if not isinstance(step, dict):
                    continue
                board = step.get("board")
                if not isinstance(board, list):
                    continue
                dropped_ids: list[str] = []
                for action_index in sorted(action_indexes, reverse=True):
                    if 0 <= action_index < len(board):
                        action = board.pop(action_index)
                        action_id = action.get("id") if isinstance(action, dict) else None
                        dropped_ids.append(str(action_id or f"#{action_index + 1}"))
                if dropped_ids:
                    issues.append(
                        "dropped invalid board action(s) in step "
                        f"{step_index + 1}: {', '.join(dropped_ids)}"
                    )
    raise ValueError("lesson needed too many repair passes")


def _renumber_step(
    step: LessonStep,
    index: int,
    next_action: int,
    action_ids: dict[str, str],
) -> tuple[LessonStep, int]:
    base_actions = []
    for action in step.board:
        old_id = action.id
        action_ids[old_id] = f"a{next_action}"
        next_action += 1
        base_actions.append((action, action_ids[old_id]))
    board = []
    for action, new_id in base_actions:
        changes: dict[str, Any] = {"id": new_id}
        target = getattr(action, "target", None)
        if target is not None:
            changes["target"] = action_ids.get(target, target)
        board.append(action.model_copy(update=changes))
    return (
        step.model_copy(update={"id": f"s{index + 1}", "board": board}),
        next_action,
    )


def _limit_excerpts(
    excerpts: list[SourceExcerpt],
    max_chars: int,
) -> list[SourceExcerpt]:
    limited: list[SourceExcerpt] = []
    used = 0
    for excerpt in excerpts:
        cost = len(excerpt.text) + len(excerpt.citation) + 24
        if limited and used + cost > max_chars:
            break
        limited.append(excerpt)
        used += cost
    return limited


def _merge_excerpts(
    primary: list[SourceExcerpt],
    extra: list[SourceExcerpt],
) -> list[SourceExcerpt]:
    merged = list(primary)
    seen = {(excerpt.citation, excerpt.text) for excerpt in primary}
    for excerpt in extra:
        key = (excerpt.citation, excerpt.text)
        if key in seen:
            continue
        seen.add(key)
        merged.append(excerpt)
    return merged


class LessonGenerator:
    def __init__(
        self,
        *,
        client: ChatClient | None = None,
        retriever: Retriever | None = None,
        cache: LessonCache | None = None,
        release_retriever: bool = True,
    ) -> None:
        self._provided_client = client
        self._provided_retriever = retriever
        self.cache = cache or LessonCache()
        self.release_retriever = release_retriever

    def _client(self) -> ChatClient:
        if self._provided_client is None:
            self._provided_client = OllamaClient()
        return self._provided_client

    def _retriever(self) -> Retriever:
        if self._provided_retriever is None:
            from medha.rag import RagService

            self._provided_retriever = RagService()
        return self._provided_retriever

    def generate(
        self,
        request: GenerationRequest,
        *,
        use_cache: bool = True,
    ) -> GenerationResult:
        started = time.perf_counter()
        warnings: list[str] = []
        hits: list[Any] = []
        if request.use_rag:
            retriever = self._retriever()
            try:
                result = retriever.query(
                    request.rag_query or request.topic,
                    top_k=config.LESSON_RAG_TOP_K,
                    candidates=config.RERANK_CANDIDATES,
                    rerank=request.use_rerank,
                )
            except Exception as exc:
                if not is_memory_error(exc):
                    raise GenerationError(f"material retrieval failed: {exc}") from exc
                warnings.append(
                    "material retrieval ran out of memory; using the topic only: "
                    f"{exc}"
                )
            else:
                hits = list(result.hits)
                if request.use_rerank and not getattr(result, "reranked", True):
                    warnings.append(
                        "reranker was not used; using vector similarity ranking"
                    )
                if not hits:
                    warnings.append("no material was retrieved; using the topic only")
            finally:
                if self.release_retriever:
                    close = getattr(retriever, "close", None)
                    if callable(close):
                        close()
        else:
            warnings.append("material retrieval is disabled; using the topic only")

        excerpts, truncated = _excerpts_from_hits(hits)
        if not excerpts and request.use_rag:
            warnings.append("retrieved material was empty; using the topic only")
        if truncated:
            warnings.append("material excerpts were shortened to fit the context")

        material_hash = _material_hash(excerpts)
        messages = build_messages(request, excerpts)
        prompt_chars = sum(len(message["content"]) for message in messages)
        material_chars = sum(len(excerpt.text) for excerpt in excerpts)
        client = self._client()
        key = cache_key(
            {
                "cache_version": config.LESSON_CACHE_VERSION,
                "prompt_version": config.LESSON_PROMPT_VERSION,
                "model": client.model,
                "request": request.model_dump(mode="json"),
                "retrieval": _retrieval_fingerprint(excerpts),
            }
        )
        if use_cache:
            cached = self.cache.load(key)
            if cached is not None:
                return GenerationResult(
                    lesson=cached,
                    cached=True,
                    attempts=1,
                    retrieved=len(hits),
                    material_chars=material_chars,
                    prompt_chars=prompt_chars,
                    elapsed_s=round(time.perf_counter() - started, 3),
                    warnings=warnings,
                )

        lesson, attempts, generation_warnings = self._attempt(
            request,
            messages,
            client=client,
            material_hash=material_hash,
            excerpts=excerpts,
        )
        warnings.extend(generation_warnings)
        if use_cache:
            self.cache.save(key, lesson)
        return GenerationResult(
            lesson=lesson,
            cached=False,
            attempts=attempts,
            retrieved=len(hits),
            material_chars=material_chars,
            prompt_chars=prompt_chars,
            elapsed_s=round(time.perf_counter() - started, 3),
            warnings=warnings,
        )

    def generate_stepwise(
        self,
        request: GenerationRequest,
        on_step: StepCallback,
        *,
        use_cache: bool = True,
    ) -> GenerationResult:
        started = time.perf_counter()
        warnings: list[str] = []
        retriever = self._retriever() if request.use_rag else None
        try:
            hits: list[Any] = []
            if retriever is not None:
                hits, retrieval_warnings, query_ok = self._query_hits(
                    retriever,
                    request,
                    request.rag_query or request.topic,
                    required=True,
                )
                warnings.extend(retrieval_warnings)
                if not query_ok:
                    close = getattr(retriever, "close", None)
                    if callable(close):
                        close()
                    retriever = None
            else:
                warnings.append("material retrieval is disabled; using the topic only")

            initial_excerpts, truncated = _excerpts_from_hits(hits)
            if not initial_excerpts and request.use_rag:
                warnings.append("retrieved material was empty; using the topic only")
            if truncated:
                warnings.append("material excerpts were shortened to fit the context")
            material_hash = _material_hash(initial_excerpts)
            client = self._client()
            key = cache_key(
                {
                    "cache_version": config.LESSON_CACHE_VERSION,
                    "prompt_version": config.LESSON_PROMPT_VERSION,
                    "model": client.model,
                    "request": request.model_dump(mode="json"),
                    "retrieval": _retrieval_fingerprint(initial_excerpts),
                }
            )
            if use_cache:
                cached = self.cache.load(key)
                if cached is not None:
                    outline = LessonOutline(
                        title=cached.title,
                        target_concept=cached.target_concept or _slug(request.topic),
                        concepts=tuple(step.concept for step in cached.steps),
                    )
                    if retriever is not None and self.release_retriever:
                        close = getattr(retriever, "close", None)
                        if callable(close):
                            close()
                        retriever = None
                    for index, step in enumerate(cached.steps):
                        header = self._header_lesson(
                            request,
                            outline,
                            material_hash,
                            cached.steps[: index + 1],
                        )
                        on_step(StepEvent(index, header, step, cached=True))
                    return GenerationResult(
                        lesson=cached,
                        cached=True,
                        attempts=1,
                        retrieved=len(hits),
                        material_chars=sum(
                            len(excerpt.text) for excerpt in initial_excerpts
                        ),
                        prompt_chars=0,
                        elapsed_s=round(time.perf_counter() - started, 3),
                        warnings=warnings,
                    )

            outline, outline_attempts, outline_prompt_chars = self._outline(
                request,
                initial_excerpts,
                client=client,
            )
            all_excerpts = list(initial_excerpts)
            step_excerpts_list: list[list[SourceExcerpt]] = []
            retrieved = len(hits)
            for index, concept in enumerate(outline.concepts):
                if retriever is not None:
                    step_hits, step_retrieval_warnings, step_ok = self._query_hits(
                        retriever,
                        request,
                        f"{request.topic} {concept}",
                        required=False,
                    )
                    warnings.extend(step_retrieval_warnings)
                    retrieved += len(step_hits)
                    extra, step_truncated = _excerpts_from_hits(step_hits)
                    if step_truncated:
                        warnings.append(
                            f"step {index + 1} material was shortened to fit the context"
                        )
                    all_excerpts = _merge_excerpts(all_excerpts, extra)
                    if not step_ok:
                        close = getattr(retriever, "close", None)
                        if callable(close):
                            close()
                        retriever = None
                step_excerpts_list.append(
                    _limit_excerpts(
                        all_excerpts,
                        config.LESSON_STEP_MAX_MATERIAL_CHARS,
                    )
                )
            if retriever is not None and self.release_retriever:
                close = getattr(retriever, "close", None)
                if callable(close):
                    close()
                retriever = None
            steps: list[LessonStep] = []
            next_action = 1
            action_ids: dict[str, str] = {}
            attempts = outline_attempts
            prompt_chars = outline_prompt_chars
            for index, _concept in enumerate(outline.concepts):
                step_excerpts = step_excerpts_list[index]
                messages = build_step_messages(
                    request,
                    outline,
                    index,
                    step_excerpts,
                )
                prompt_chars += sum(len(message["content"]) for message in messages)
                step, used_attempts, step_warnings = self._attempt_step(
                    request,
                    outline,
                    index,
                    step_excerpts,
                    client=client,
                    material_hash=material_hash,
                )
                attempts += used_attempts
                warnings.extend(step_warnings)
                step, next_action = _renumber_step(
                    step, index, next_action, action_ids
                )
                steps.append(step)
                header, layout_warnings = self._normalized_header(
                    request,
                    outline,
                    material_hash,
                    steps,
                )
                warnings.extend(layout_warnings)
                steps = list(header.steps)
                on_step(StepEvent(index, header, steps[index], cached=False))

            lesson = self._with_meta(
                header,
                request=request,
                model=client.model,
                material_hash=_material_hash(all_excerpts),
                excerpts=all_excerpts,
            )
            if use_cache:
                self.cache.save(key, lesson)
            return GenerationResult(
                lesson=lesson,
                cached=False,
                attempts=attempts,
                retrieved=retrieved,
                material_chars=sum(len(excerpt.text) for excerpt in all_excerpts),
                prompt_chars=prompt_chars,
                elapsed_s=round(time.perf_counter() - started, 3),
                warnings=warnings,
            )
        finally:
            if retriever is not None and self.release_retriever:
                close = getattr(retriever, "close", None)
                if callable(close):
                    close()

    def _query_hits(
        self,
        retriever: Retriever,
        request: GenerationRequest,
        query: str,
        *,
        required: bool,
    ) -> tuple[list[Any], list[str], bool]:
        try:
            result = retriever.query(
                query,
                top_k=config.LESSON_RAG_TOP_K,
                candidates=config.RERANK_CANDIDATES,
                rerank=request.use_rerank,
            )
        except Exception as exc:
            memory_error = is_memory_error(exc)
            if required and not memory_error:
                raise GenerationError(f"material retrieval failed: {exc}") from exc
            reason = "ran out of memory" if memory_error else "failed"
            return [], [f"retrieval {reason} for {query!r}: {exc}"], False
        warnings: list[str] = []
        if request.use_rerank and not getattr(result, "reranked", True):
            warnings.append("reranker was not used; using vector similarity ranking")
        return list(result.hits), warnings, True

    def _outline(
        self,
        request: GenerationRequest,
        excerpts: list[SourceExcerpt],
        *,
        client: ChatClient,
    ) -> tuple[LessonOutline, int, int]:
        messages = build_outline_messages(request, excerpts)
        prompt_chars = sum(len(message["content"]) for message in messages)
        last_error = ""
        for attempt in range(1, config.LESSON_MAX_ATTEMPTS + 1):
            attempt_messages = list(messages)
            if last_error:
                attempt_messages.append(retry_message(last_error))
            raw = client.chat(
                attempt_messages,
                format_schema=llm_outline_schema(),
            )
            try:
                return parse_outline_json(raw, request), attempt, prompt_chars
            except ValueError as exc:
                last_error = str(exc)
        raise GenerationError(
            f"model returned an invalid outline after {config.LESSON_MAX_ATTEMPTS} "
            f"attempt(s): {last_error}"
        )

    def _attempt_step(
        self,
        request: GenerationRequest,
        outline: LessonOutline,
        index: int,
        excerpts: list[SourceExcerpt],
        *,
        client: ChatClient,
        material_hash: str | None,
    ) -> tuple[LessonStep, int, list[str]]:
        messages = build_step_messages(request, outline, index, excerpts)
        warnings: list[str] = []
        last_error = ""
        for attempt in range(1, config.LESSON_MAX_ATTEMPTS + 1):
            attempt_messages = list(messages)
            if last_error:
                attempt_messages.append(retry_message(last_error))
            raw = client.chat(
                attempt_messages,
                format_schema=llm_step_lesson_schema(),
            )
            try:
                payload = parse_lesson_json(raw)
                payload = sanitize_payload(payload)
                payload = self._normalize(payload, request, material_hash)
                lesson, issues = repair_with_drops(payload)
                if len(lesson.steps) != 1:
                    raise ValueError(
                        f"response has {len(lesson.steps)} step(s) but exactly 1 was requested"
                    )
                step = lesson.steps[0]
                if index > 0 and any(
                    getattr(action, "region", None) == "title" for action in step.board
                ):
                    raise ValueError("later step must not repeat the title region")
                if last_error:
                    warnings.append(
                        f"step {index + 1} retried after invalid response: {last_error}"
                    )
                warnings.extend(issues)
                return step, attempt, warnings
            except ValueError as exc:
                last_error = str(exc)
        raise GenerationError(
            f"model returned an invalid step {index + 1} after "
            f"{config.LESSON_MAX_ATTEMPTS} attempt(s): {last_error}"
        )

    def _header_lesson(
        self,
        request: GenerationRequest,
        outline: LessonOutline,
        material_hash: str | None,
        steps: list[LessonStep],
    ) -> LessonScript:
        return LessonScript(
            schema_version="1.0.0",
            lesson_id=make_lesson_id(request, material_hash),
            title=outline.title,
            subject=request.subject,
            target_concept=outline.target_concept,
            difficulty=request.difficulty,
            style_id=request.style_id,
            steps=list(steps),
        )

    def _normalized_header(
        self,
        request: GenerationRequest,
        outline: LessonOutline,
        material_hash: str | None,
        steps: list[LessonStep],
    ) -> tuple[LessonScript, list[str]]:
        header = self._header_lesson(request, outline, material_hash, steps)
        return normalize_layout(header)

    def _attempt(
        self,
        request: GenerationRequest,
        messages: list[ChatMessage],
        *,
        client: ChatClient,
        material_hash: str | None,
        excerpts: list[SourceExcerpt],
    ) -> tuple[LessonScript, int, list[str]]:
        warnings: list[str] = []
        last_error = ""
        for attempt in range(1, config.LESSON_MAX_ATTEMPTS + 1):
            attempt_messages = list(messages)
            if last_error:
                attempt_messages.append(retry_message(last_error))
            raw = client.chat(
                attempt_messages,
                format_schema=llm_lesson_schema(),
            )
            try:
                payload = parse_lesson_json(raw)
                payload = sanitize_payload(payload)
                payload = self._normalize(payload, request, material_hash)
                lesson, issues = repair_with_drops(payload)
                if len(lesson.steps) != request.steps:
                    raise ValueError(
                        f"lesson has {len(lesson.steps)} step(s) but exactly "
                        f"{request.steps} were requested"
                    )
                lesson = lesson.model_copy(
                    update={
                        "subject": request.subject,
                        "difficulty": request.difficulty,
                        "style_id": request.style_id,
                    }
                )
                lesson, layout_warnings = normalize_layout(lesson)
                warnings.extend(layout_warnings)
                lesson = self._with_meta(
                    lesson,
                    request=request,
                    model=client.model,
                    material_hash=material_hash,
                    excerpts=excerpts,
                )
                if last_error:
                    warnings.append(f"retried after invalid response: {last_error}")
                warnings.extend(issues)
                return lesson, attempt, warnings
            except ValueError as exc:
                last_error = str(exc)
        raise GenerationError(
            f"model returned an invalid lesson after {config.LESSON_MAX_ATTEMPTS} "
            f"attempt(s): {last_error}"
        )

    def _normalize(
        self,
        payload: dict[str, Any],
        request: GenerationRequest,
        material_hash: str | None,
    ) -> dict[str, Any]:
        data = dict(payload)
        data["schema_version"] = "1.0.0"
        data["lesson_id"] = make_lesson_id(request, material_hash)
        data["subject"] = request.subject
        data["difficulty"] = request.difficulty
        data["style_id"] = request.style_id
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            data["title"] = request.topic.strip()[:200]
        else:
            data["title"] = title.strip()[:200]
        target = data.get("target_concept")
        if not isinstance(target, str) or not target.strip():
            data["target_concept"] = _slug(request.topic)
        else:
            data["target_concept"] = target.strip()[:120]
        if not isinstance(data.get("steps"), list):
            raise ValueError("lesson JSON has no steps list")
        data["meta"] = {}
        return data

    def _with_meta(
        self,
        lesson: LessonScript,
        *,
        request: GenerationRequest,
        model: str,
        material_hash: str | None,
        excerpts: list[SourceExcerpt],
    ) -> LessonScript:
        sources: list[str] = []
        for excerpt in excerpts:
            if excerpt.citation not in sources:
                sources.append(excerpt.citation)
        meta = LessonMeta(
            model=model,
            prompt_version=config.LESSON_PROMPT_VERSION,
            material_hash=material_hash,
            style_id=request.style_id,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            estimated_duration_s=estimate_duration_s(lesson),
            sources=sources,
        )
        return lesson.model_copy(update={"meta": meta})
