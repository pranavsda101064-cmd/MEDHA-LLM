"""Compact JSON schema used for Ollama grammar-constrained generation.

The full Pydantic schema is the validation source of truth. Ollama's grammar
compiler struggles with the full discriminated-union schema, so the model gets a
smaller permissive envelope and the generator repairs and validates the result.
"""

from __future__ import annotations

from typing import Any

_SUBJECTS = ["math", "physics", "chemistry", "electronics", "ai", "general"]
_DIFFICULTIES = ["beginner", "intermediate", "advanced"]
_REGIONS = ["auto", "title", "left", "center", "right", "top", "bottom", "full"]
_COLORS = [
    "chalk",
    "math",
    "diagram",
    "yellow",
    "red",
    "blue",
    "green",
    "orange",
    "white",
]
_SHAPES = [
    "line",
    "arrow",
    "polyline",
    "circle",
    "ellipse",
    "rect",
    "axes",
    "spring",
    "block",
    "incline",
    "pulley",
    "resistor",
    "battery",
    "waveform",
    "atom",
    "graph",
    "grid",
]
_OPS = [
    "write_text",
    "write_math",
    "draw",
    "image",
    "highlight",
    "erase",
    "point",
    "scroll",
    "pause",
    "clear",
    "bullet_list",
]
_STRING = {"type": "string"}
_NUMBER = {"type": "number"}
_INTEGER = {"type": "integer"}
_BOOLEAN = {"type": "boolean"}
_POS = {
    "type": "object",
    "properties": {"x": _NUMBER, "y": _NUMBER},
    "required": ["x", "y"],
}
_RECT = {
    "type": "object",
    "properties": {"x": _NUMBER, "y": _NUMBER, "w": _NUMBER, "h": _NUMBER},
    "required": ["x", "y", "w", "h"],
}
_ANCHOR = {
    "type": "object",
    "properties": {"sentence": _INTEGER, "char": _INTEGER},
    "required": ["sentence", "char"],
}
_STYLE = {
    "type": "object",
    "properties": {
        "font_size": _NUMBER,
        "color": {"type": "string", "enum": _COLORS},
        "bold": _BOOLEAN,
        "underline": _BOOLEAN,
        "align": {"type": "string", "enum": ["left", "center", "right"]},
    },
}
_CHECKPOINT = {
    "type": "object",
    "properties": {
        "question": _STRING,
        "expected": _STRING,
        "hints": {"type": "array", "items": _STRING},
    },
    "required": ["question", "expected"],
}
_ACTION = {
    "type": "object",
    "properties": {
        "op": {"type": "string", "enum": _OPS},
        "id": _STRING,
        "duration_ms": _INTEGER,
        "start": _ANCHOR,
        "text": _STRING,
        "latex": _STRING,
        "shape": {"type": "string", "enum": _SHAPES},
        "points": {"type": "array", "items": _POS},
        "rect": _RECT,
        "region": {"type": "string", "enum": _REGIONS},
        "style": _STYLE,
        "speed": _NUMBER,
        "font_size": _NUMBER,
        "color": {"type": "string", "enum": _COLORS},
        "width": _NUMBER,
        "filled": _BOOLEAN,
        "label": _STRING,
        "tags": {"type": "array", "items": _STRING},
        "fade_ms": _INTEGER,
        "opacity": _NUMBER,
        "caption": _STRING,
        "target": _STRING,
        "at": _POS,
        "amount": _NUMBER,
        "direction": {"type": "string", "enum": ["up", "down"]},
        "items": {"type": "array", "items": _STRING},
        "item_gap": _NUMBER,
    },
    "required": ["op", "id"],
}
_STEP = {
    "type": "object",
    "properties": {
        "id": _STRING,
        "concept": _STRING,
        "narration": _STRING,
        "board": {"type": "array", "items": _ACTION},
        "checkpoint": _CHECKPOINT,
    },
    "required": ["id", "concept", "narration", "board"],
}


def llm_outline_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "title": _STRING,
            "target_concept": _STRING,
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "concept": _STRING,
                        "goal": _STRING,
                    },
                    "required": ["concept"],
                },
            },
        },
        "required": ["title", "steps"],
    }


def llm_step_lesson_schema() -> dict[str, Any]:
    schema = llm_lesson_schema()
    schema["properties"]["steps"] = {
        "type": "array",
        "items": _STEP,
        "minItems": 1,
        "maxItems": 1,
    }
    return schema


def llm_lesson_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string"},
            "lesson_id": _STRING,
            "title": _STRING,
            "subject": {"type": "string", "enum": _SUBJECTS},
            "target_concept": _STRING,
            "difficulty": {"type": "string", "enum": _DIFFICULTIES},
            "style_id": _STRING,
            "steps": {"type": "array", "items": _STEP},
            "meta": {"type": "object"},
        },
        "required": ["title", "steps"],
    }
