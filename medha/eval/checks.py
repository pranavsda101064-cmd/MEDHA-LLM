"""Cheap, deterministic lesson checks used by CI and Studio."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

import config
from medha.core.schema import LessonScript, split_sentences
from medha.lesson.generator import estimate_duration_s
from medha.lesson.layout import text_collisions
from medha.render.actions import build_visuals, mathtext_segments, render_frame
from medha.render.geometry import Transform
from medha.render.scene import Board
from medha.render.timeline import build_timeline
from medha.tts.speech import SpeechTrack

from .models import EvalIssue, LessonReport, Severity

_NON_STROKE_OPS = {"pause", "clear", "scroll", "erase"}
_WORD_RE = re.compile(r"\b\w+\b")


def _issue(
    severity: Severity,
    code: str,
    message: str,
    *,
    step_id: str | None = None,
    action_id: str | None = None,
) -> EvalIssue:
    return EvalIssue(
        severity=severity,
        code=code,
        message=message,
        step_id=step_id,
        action_id=action_id,
    )


def _finalize(
    report: LessonReport,
    *,
    errors: int,
    warnings: int,
) -> LessonReport:
    report.errors = errors
    report.warnings = warnings
    report.ok = errors == 0
    report.score = max(0, 100 - 25 * errors - 5 * warnings)
    return report


def evaluate_lesson(
    lesson: LessonScript,
    *,
    path: Path | None = None,
    speech_track: SpeechTrack | None = None,
    render_smoke: bool = True,
) -> LessonReport:
    issues: list[EvalIssue] = []
    steps = len(lesson.steps)
    actions = sum(len(step.board) for step in lesson.steps)
    reading_ms = round(estimate_duration_s(lesson) * 1000)

    if speech_track is not None:
        timeline = build_timeline(
            lesson,
            sentence_ms=[list(step) for step in speech_track.sentence_ms],
            step_gap_ms=speech_track.step_gap_ms,
            sentence_gap_ms=speech_track.sentence_gap_ms,
            lead_ms=speech_track.lead_ms,
        )
    else:
        timeline = build_timeline(lesson)

    if actions == 0:
        issues.append(_issue("error", "board.no_actions", "lesson has no board actions"))
    if timeline.total_ms <= 0:
        issues.append(_issue("error", "timing.empty", "timeline has no duration"))
    for left, right in text_collisions(lesson)[:8]:
        issues.append(
            _issue(
                "warning",
                "board.text_overlap",
                f"text actions {left} and {right} overlap",
            )
        )

    for step in lesson.steps:
        text = step.narration.strip()
        if "\ufffd" in text:
            issues.append(
                _issue(
                    "error",
                    "text.replacement",
                    "narration contains Unicode replacement characters",
                    step_id=step.id,
                )
            )
        if len(_WORD_RE.findall(text)) < 3:
            issues.append(
                _issue(
                    "warning",
                    "narration.short",
                    "narration is very short",
                    step_id=step.id,
                )
            )
        if not step.board:
            issues.append(
                _issue(
                    "warning",
                    "step.empty_board",
                    "step has no board actions",
                    step_id=step.id,
                )
            )
        if len(step.board) > 12:
            issues.append(
                _issue(
                    "warning",
                    "step.dense",
                    "more than 12 actions in one step",
                    step_id=step.id,
                )
            )
        sentences = split_sentences(text)
        if sentences and len(text) / max(1, len(sentences)) > 320:
            issues.append(
                _issue(
                    "warning",
                    "narration.long_sentence",
                    "a sentence is over 320 characters",
                    step_id=step.id,
                )
            )

    visuals = {}
    try:
        visuals = build_visuals(lesson)
    except Exception as exc:
        issues.append(
            _issue("error", "render.visuals", f"cannot build board visuals: {exc}")
        )

    if visuals:
        for step in lesson.steps:
            for action in step.board:
                if action.op in _NON_STROKE_OPS:
                    continue
                visual = visuals.get(action.id)
                if visual is None or not visual.items:
                    issues.append(
                        _issue(
                            "warning",
                            "render.empty_action",
                            f"{action.op} produced no strokes",
                            step_id=step.id,
                            action_id=action.id,
                        )
                    )
                if action.op == "image":
                    issues.append(
                        _issue(
                            "warning",
                            "render.image_placeholder",
                            "images render as a placeholder box",
                            step_id=step.id,
                            action_id=action.id,
                        )
                    )
                if action.op == "write_math" and not mathtext_segments(action.latex):
                    issues.append(
                        _issue(
                            "warning",
                            "math.fallback",
                            "LaTeX could not be parsed; ASCII fallback is used",
                            step_id=step.id,
                            action_id=action.id,
                        )
                    )

    if lesson.meta.material_hash and not lesson.meta.sources:
        issues.append(
            _issue(
                "warning",
                "source.missing",
                "material hash is set but no sources are recorded",
            )
        )
    if lesson.meta.estimated_duration_s is not None:
        drift = abs(lesson.meta.estimated_duration_s * 1000 - reading_ms)
        if drift > max(3000, reading_ms * 0.25):
            issues.append(
                _issue(
                    "warning",
                    "meta.duration_drift",
                    "estimated_duration_s differs from narration estimate",
                )
            )
    if speech_track is not None:
        drift = abs(timeline.total_ms - speech_track.duration_ms)
        if drift > max(1200, speech_track.duration_ms * 0.15):
            issues.append(
                _issue(
                    "warning",
                    "tts.timing_drift",
                    "timeline and synthesized speech durations differ",
                )
            )

    if render_smoke and visuals:
        try:
            board = Board()
            for fraction in (0.25, 0.5, 0.75, 1.0):
                render_frame(
                    board,
                    visuals,
                    timeline,
                    round(timeline.total_ms * fraction),
                )
            mesh = board.build(Transform(1280, 720))
            if mesh.vertex_count == 0:
                issues.append(
                    _issue(
                        "warning",
                        "render.empty_end",
                        "the final frame has no visible strokes",
                    )
                )
        except Exception as exc:
            issues.append(
                _issue("error", "render.smoke", f"render smoke failed: {exc}")
            )

    errors = sum(1 for issue in issues if issue.severity == "error")
    warnings = sum(1 for issue in issues if issue.severity == "warning")
    return _finalize(
        LessonReport(
            path=str(path) if path is not None else None,
            lesson_id=lesson.lesson_id,
            title=lesson.title,
            steps=steps,
            actions=actions,
            timeline_ms=timeline.total_ms,
            reading_ms=reading_ms,
            issues=issues,
        ),
        errors=errors,
        warnings=warnings,
    )


def _invalid_report(path: Path, message: str) -> LessonReport:
    issue = _issue("error", "schema.invalid", message)
    return _finalize(
        LessonReport(path=str(path), issues=[issue]),
        errors=1,
        warnings=0,
    )


def evaluate_file(
    path: Path,
    *,
    speech_track: SpeechTrack | None = None,
    render_smoke: bool = True,
) -> LessonReport:
    target = Path(path)
    try:
        payload: Any = json.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        return _invalid_report(target, f"cannot read lesson: {exc}")
    except json.JSONDecodeError as exc:
        return _invalid_report(target, f"invalid JSON: {exc}")
    try:
        lesson = LessonScript.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first.get("loc", ()))
        message = first.get("msg", "validation failed")
        detail = f"invalid lesson schema at {location}: {message}" if location else message
        return _invalid_report(target, detail)
    return evaluate_lesson(
        lesson,
        path=target,
        speech_track=speech_track,
        render_smoke=render_smoke,
    )


def evaluate_corpus(
    directory: Path | None = None,
    *,
    render_smoke: bool = True,
) -> list[LessonReport]:
    root = Path(directory or config.LESSON_CONTENT_DIR)
    if not root.exists():
        return []
    return [
        evaluate_file(path, render_smoke=render_smoke)
        for path in sorted(root.glob("*.json"))
    ]
