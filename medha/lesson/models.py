"""Request and result contracts for lesson generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

import config
from medha.core.schema import LessonScript, LessonStep, Subject

Difficulty = Literal["beginner", "intermediate", "advanced"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerationRequest(StrictModel):
    topic: str = Field(min_length=3, max_length=300)
    subject: Subject = "general"
    difficulty: Difficulty = "beginner"
    audience: str = Field(
        default=config.LESSON_DEFAULT_AUDIENCE,
        min_length=3,
        max_length=200,
    )
    steps: int = Field(default=config.LESSON_DEFAULT_STEPS, ge=1, le=config.LESSON_MAX_STEPS)
    style_id: str = Field(default="default", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
    rag_query: str | None = Field(default=None, max_length=500)
    use_rag: bool = True
    use_rerank: bool = True


class GenerationResult(StrictModel):
    lesson: LessonScript
    cached: bool = False
    attempts: int = Field(ge=1)
    retrieved: int = Field(ge=0)
    material_chars: int = Field(ge=0)
    prompt_chars: int = Field(ge=0)
    elapsed_s: float = Field(ge=0.0)
    warnings: list[str] = Field(default_factory=list)


class SourceExcerpt(StrictModel):
    citation: str
    text: str
    source: str
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)


@dataclass(frozen=True)
class LessonOutline:
    title: str
    target_concept: str
    concepts: tuple[str, ...]


@dataclass(frozen=True)
class StepEvent:
    index: int
    lesson: LessonScript
    step: LessonStep
    cached: bool = False
