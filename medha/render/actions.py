"""Translate board actions into chalk visuals and animate them on a timeline."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Any

import config
from medha.core.schema import (
    BoardAction,
    BulletListAction,
    DrawAction,
    EraseAction,
    HighlightAction,
    ImageAction,
    LessonScript,
    PointAction,
    ScrollAction,
    WriteMathAction,
    WriteTextAction,
)

from . import shapes
from .geometry import Point, bounds, clamp
from .scene import Board, RectTuple, StrokeItem
from .timeline import Timeline, build_timeline


def region_rect(region: str) -> RectTuple:
    mx = config.BOARD_MARGIN_X
    my = config.BOARD_MARGIN_Y
    if region == "title":
        return mx, 0.045, 1.0 - 2.0 * mx, config.TITLE_BAND_H
    if region == "top":
        return mx, 0.04, 1.0 - 2.0 * mx, 0.22
    if region == "left":
        return mx, 0.23, 0.45, 0.60
    if region == "right":
        return 0.52, 0.23, 0.43, 0.60
    if region == "center":
        return 0.18, 0.24, 0.64, 0.48
    if region == "bottom":
        return mx, 0.76, 1.0 - 2.0 * mx, 0.16
    if region == "full":
        return mx, my, 1.0 - 2.0 * mx, 1.0 - 2.0 * my
    return mx, 0.23, 0.45, 0.60


def _rect_tuple(rect: Any) -> RectTuple:
    return (rect.x, rect.y, rect.w, rect.h)


def _action_rect(rect: object | None, region: str) -> RectTuple:
    return _rect_tuple(rect) if rect is not None else region_rect(region)


def _text_size(rect: RectTuple, base: float) -> float:
    return max(0.014, min(base, rect[3] * 0.56))


def math_to_text(latex: str) -> str:
    """Small LaTeX-to-ASCII fallback for previews.

    Used only when matplotlib mathtext is unavailable or cannot parse the
    expression.
    """
    text = latex.strip()
    if not any(token in text for token in ("\\", "{", "}", "$", "^", "_")):
        return text
    fraction = re.compile(r"\\frac\{([^{}]*)\}\{([^{}]*)\}")
    while fraction.search(text):
        text = fraction.sub(r"(\1)/(\2)", text)
    replacements = {
        r"\times": " x ",
        r"\cdot": " * ",
        r"\rightarrow": " -> ",
        r"\to": " -> ",
        r"\left": "",
        r"\right": "",
        r"\,": " ",
        r"\;": " ",
        r"\!": "",
        r"\ ": " ",
        r"\pi": "pi",
        r"\theta": "theta",
        r"\alpha": "alpha",
        r"\Delta": "delta",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"\\sqrt\{([^{}]*)\}", r"sqrt(\1)", text)
    text = text.replace("{", "").replace("}", "").replace("$", "")
    text = re.sub(r"\^\{([^{}]*)\}", r"^\1", text)
    return text.replace("\\", "")


@lru_cache(maxsize=256)
def mathtext_segments(latex: str) -> tuple[tuple[Point, ...], ...]:
    """Flatten matplotlib mathtext into board-space polylines."""
    try:
        from matplotlib.textpath import TextPath
    except ImportError:
        return ()
    math = latex if latex.startswith("$") else f"${latex}$"
    try:
        path = TextPath((0.0, 0.0), math, size=1.0, usetex=False)
        polygons: Any = path.to_polygons(closed_only=False)
    except (RuntimeError, ValueError, OSError):
        return ()
    segments: list[tuple[Point, ...]] = []
    for polygon in polygons:
        points: list[Point] = []
        for raw_point in polygon:
            raw_x, raw_y = raw_point
            point = (float(raw_x), float(raw_y))
            if not points or point != points[-1]:
                points.append(point)
        if len(points) >= 2:
            segments.append(tuple(points))
    return tuple(segments)


def _add_text(
    board: Board,
    text: str,
    rect: RectTuple,
    size: float,
    color: str,
    width_px: float,
    align: str = "left",
) -> list[StrokeItem]:
    return board.add_text(
        text,
        at=(rect[0], rect[1]),
        size=size,
        color=color,
        width_px=width_px,
        max_width=rect[2],
        align=align,
        tracking=0.01,
        line_gap=1.3,
    )


def _render_text(board: Board, action: WriteTextAction) -> list[StrokeItem]:
    rect = _action_rect(action.rect, action.region)
    style = action.style
    base = 0.032 * style.font_size
    if action.region == "title" and action.rect is None:
        base = 0.074 * style.font_size
    elif action.region == "bottom" and action.rect is None:
        base = 0.026 * style.font_size
    size = _text_size(rect, base)
    return _add_text(
        board,
        action.text,
        rect,
        size,
        style.color,
        2.3 + 0.6 * style.font_size,
        style.align,
    )


def _render_math(board: Board, action: WriteMathAction) -> list[StrokeItem]:
    rect = _action_rect(action.rect, action.region)
    segments = mathtext_segments(action.latex)
    if not segments:
        base = 0.030 * action.font_size
        size = _text_size(rect, base)
        return _add_text(
            board,
            math_to_text(action.latex),
            rect,
            size,
            action.color,
            2.6,
        )

    xs = [point[0] for segment in segments for point in segment]
    ys = [point[1] for segment in segments for point in segment]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    source_w = max(1e-6, max_x - min_x)
    source_h = max(1e-6, max_y - min_y)
    scale = min(rect[2] / source_w, rect[3] / source_h) * 0.94
    offset_x = rect[0] + (rect[2] - source_w * scale) / 2.0
    offset_y = rect[1] + (rect[3] - source_h * scale) / 2.0
    width_px = 2.4 + 0.3 * action.font_size
    return [
        board.add_polyline(
            [
                (offset_x + (x - min_x) * scale, offset_y + (max_y - y) * scale)
                for x, y in segment
            ],
            action.color,
            width_px,
        )
        for segment in segments
    ]


def _draw_strokes(action: DrawAction) -> list[list[Point]]:
    points = [(point.x, point.y) for point in action.points]
    rect = _rect_tuple(action.rect) if action.rect is not None else None
    shape = action.shape
    if shape == "line":
        return shapes.line(points[0], points[1])
    if shape == "arrow":
        return shapes.arrow(points[0], points[1])
    if shape == "polyline":
        return shapes.polyline(points)
    if rect is None:
        return []
    if shape == "circle":
        x, y, w, h = rect
        return shapes.circle((x + w / 2.0, y + h / 2.0), min(w, h) / 2.0)
    if shape == "ellipse":
        return shapes.ellipse(rect)
    if shape == "rect":
        return shapes.rectangle(rect)
    if shape == "axes":
        return shapes.axes(rect)
    if shape == "spring":
        x, y, w, h = rect
        return shapes.spring((x, y + h / 2.0), (x + w, y + h / 2.0))
    if shape == "block":
        return shapes.block(rect)
    if shape == "incline":
        return shapes.incline(rect)
    if shape == "resistor":
        return shapes.resistor(rect)
    if shape == "battery":
        return shapes.battery(rect)
    if shape == "waveform":
        return shapes.waveform(rect)
    if shape == "grid":
        return shapes.grid(rect)
    if shape == "pulley":
        x, y, w, h = rect
        center = (x + w / 2.0, y + h / 2.0)
        return [*shapes.circle(center, min(w, h) / 2.0), [(x, center[1]), (x + w, center[1])]]
    if shape == "atom":
        x, y, w, h = rect
        center = (x + w / 2.0, y + h / 2.0)
        return [
            *shapes.circle(center, min(w, h) / 2.0, 36),
            *shapes.ellipse((x, y + h * 0.25, w, h * 0.5)),
            *shapes.ellipse((x + w * 0.25, y, w * 0.5, h)),
        ]
    if shape == "graph":
        return shapes.axes(rect)
    return shapes.rectangle(rect)


def _render_draw(board: Board, action: DrawAction) -> list[StrokeItem]:
    items = [
        board.add_polyline(stroke, action.color, action.width)
        for stroke in _draw_strokes(action)
    ]
    if action.label:
        if action.points:
            at = (action.points[0].x, action.points[0].y - 0.035)
        elif action.rect is not None:
            at = (action.rect.x, action.rect.y - 0.035)
        else:
            at = (0.1, 0.1)
        items.extend(
            board.add_text(
                action.label,
                at=at,
                size=0.024,
                color=action.color,
                width_px=2.0,
                max_width=0.4,
            )
        )
    return items


def _render_image(board: Board, action: ImageAction) -> list[StrokeItem]:
    rect = _rect_tuple(action.rect)
    items = [
        board.add_polyline(stroke, "diagram", 1.6, alpha=0.7)
        for stroke in shapes.rectangle(rect)
    ]
    caption = action.caption or ", ".join(action.tags)
    caption_rect = (rect[0] + 0.012, rect[1] + 0.012, rect[2] - 0.024, rect[3] - 0.024)
    items.extend(
        _add_text(
            board,
            f"[{caption}]",
            caption_rect,
            max(0.014, min(0.030, rect[3] * 0.14)),
            "diagram",
            1.8,
        )
    )
    return items


def _target_bounds(items: list[StrokeItem]) -> RectTuple | None:
    points = [point for item in items for point in item.points]
    if not points:
        return None
    min_x, min_y, max_x, max_y = bounds(points)
    pad = 0.012
    return (
        max(0.0, min_x - pad),
        max(0.0, min_y - pad),
        min(1.0, max_x + pad) - max(0.0, min_x - pad),
        min(1.0, max_y + pad) - max(0.0, min_y - pad),
    )


def _render_highlight(
    board: Board,
    action: HighlightAction,
    visuals: dict[str, ActionVisual],
) -> list[StrokeItem]:
    target = visuals.get(action.target)
    if target is None:
        return []
    rect = _target_bounds(target.items)
    if rect is None:
        return []
    return [
        board.add_polyline(stroke, action.color, action.width, alpha=0.55)
        for stroke in shapes.rectangle(rect)
    ]


def _render_point(board: Board, action: PointAction) -> list[StrokeItem]:
    center = (action.at.x, action.at.y)
    items = [
        board.add_polyline(stroke, action.color, 2.6)
        for stroke in shapes.circle(center, 0.014, 24)
    ]
    items.extend(
        board.add_polyline(stroke, action.color, 1.8)
        for stroke in (
            [(center[0] - 0.026, center[1]), (center[0] - 0.012, center[1])],
            [(center[0] + 0.012, center[1]), (center[0] + 0.026, center[1])],
            [(center[0], center[1] - 0.026), (center[0], center[1] - 0.012)],
            [(center[0], center[1] + 0.012), (center[0], center[1] + 0.026)],
        )
    )
    if action.label:
        items.extend(
            board.add_text(
                action.label,
                at=(center[0] + 0.022, center[1] - 0.025),
                size=0.020,
                color=action.color,
                width_px=1.8,
                max_width=0.24,
            )
        )
    return items


def _render_bullets(board: Board, action: BulletListAction) -> list[StrokeItem]:
    rect = _action_rect(action.rect, action.region)
    size = _text_size(rect, 0.032 * action.style.font_size)
    text = "\n".join(f"- {item}" for item in action.items)
    return board.add_text(
        text,
        at=(rect[0], rect[1]),
        size=size,
        color=action.style.color,
        width_px=2.4,
        max_width=rect[2],
        line_gap=1.5,
    )


@dataclass
class ActionVisual:
    action_id: str
    op: str
    items: list[StrokeItem] = field(default_factory=list)
    target: str | None = None
    region: RectTuple | None = None
    instant: bool = False
    scroll_amount: float = 0.0
    scroll_direction: str = "up"

    def cloned(self, progress: float, offset_y: float = 0.0) -> list[StrokeItem]:
        if not self.items:
            return []
        if self.instant or len(self.items) == 1:
            return [
                replace(
                    item,
                    points=[(x, y + offset_y) for x, y in item.points],
                    progress=clamp(progress, 0.0, 1.0),
                )
                for item in self.items
            ]
        slot = 1.0 / len(self.items)
        out: list[StrokeItem] = []
        for index, item in enumerate(self.items):
            local = clamp((progress - index * slot) / (slot * 0.88), 0.0, 1.0)
            out.append(
                replace(
                    item,
                    points=[(x, y + offset_y) for x, y in item.points],
                    progress=local,
                )
            )
        return out


def _make_visual(
    board: Board,
    action: BoardAction,
    visuals: dict[str, ActionVisual],
) -> ActionVisual:
    visual = ActionVisual(action.id, action.op)
    before = len(board.items)
    if isinstance(action, WriteTextAction):
        _render_text(board, action)
    elif isinstance(action, WriteMathAction):
        _render_math(board, action)
    elif isinstance(action, DrawAction):
        _render_draw(board, action)
    elif isinstance(action, ImageAction):
        _render_image(board, action)
    elif isinstance(action, HighlightAction):
        _render_highlight(board, action, visuals)
    elif isinstance(action, PointAction):
        _render_point(board, action)
    elif isinstance(action, BulletListAction):
        _render_bullets(board, action)
    elif isinstance(action, EraseAction):
        visual.target = action.target
        visual.region = _rect_tuple(action.region) if action.region is not None else None
    elif isinstance(action, ScrollAction):
        visual.instant = True
        visual.scroll_amount = action.amount
        visual.scroll_direction = action.direction
    if len(board.items) > before:
        visual.items = board.items[before:]
    return visual


def build_visuals(lesson: LessonScript) -> dict[str, ActionVisual]:
    board = Board()
    visuals: dict[str, ActionVisual] = {}
    for step in lesson.steps:
        for action in step.board:
            visuals[action.id] = _make_visual(board, action, visuals)
    return visuals


def _intersects(item: StrokeItem, region: RectTuple) -> bool:
    if not item.points:
        return False
    min_x, min_y, max_x, max_y = bounds(item.points)
    x, y, w, h = region
    return not (max_x < x or min_x > x + w or max_y < y or min_y > y + h)


def render_frame(
    board: Board,
    visuals: dict[str, ActionVisual],
    timeline: Timeline,
    time_ms: int,
) -> None:
    board.clear()
    clear_time: int | None = None
    erased: set[str] = set()
    erase_regions: list[RectTuple] = []
    scroll_y = 0.0
    for visual in visuals.values():
        timing = timeline.timing(visual.action_id)
        if timing is None or timing.start_ms > time_ms:
            continue
        if visual.op == "clear":
            clear_time = max(clear_time or 0, timing.start_ms)
            scroll_y = 0.0
        elif visual.op == "scroll":
            direction = -1.0 if visual.scroll_direction == "up" else 1.0
            scroll_y += direction * visual.scroll_amount
        elif visual.op == "erase":
            if visual.target:
                erased.add(visual.target)
            if visual.region:
                erase_regions.append(visual.region)

    for visual in visuals.values():
        timing = timeline.timing(visual.action_id)
        if timing is None or time_ms < timing.start_ms:
            continue
        if clear_time is not None and timing.start_ms < clear_time:
            continue
        if visual.action_id in erased:
            continue
        progress = 1.0 if timing.duration_ms <= 0 else clamp(
            (time_ms - timing.start_ms) / timing.duration_ms, 0.0, 1.0
        )
        for item in visual.cloned(progress, scroll_y):
            if any(_intersects(item, region) for region in erase_regions):
                continue
            board.items.append(item)


def render_lesson_frame(
    board: Board,
    lesson: LessonScript,
    time_ms: int,
    visuals: dict[str, ActionVisual] | None = None,
    timeline: Timeline | None = None,
) -> None:
    timeline = timeline or build_timeline(lesson)
    visuals = visuals or build_visuals(lesson)
    render_frame(board, visuals, timeline, time_ms)
