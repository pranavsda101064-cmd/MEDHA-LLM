"""A board scene made of normalized vector strokes.

The scene is renderer-agnostic: it can be meshed for OpenGL, exported, or
sampled in tests. Chalk wobble is applied at mesh time in pixel space.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

import config

from .chalk import ChalkStroke, make_chalk
from .font import HersheyFont
from .geometry import Point, Transform, partial_polyline
from .mesh import Mesh, build_mesh
from .shapes import (
    arrow,
    axes,
    battery,
    block,
    circle,
    ellipse,
    grid,
    incline,
    line,
    normalize_rect,
    polyline,
    rectangle,
    resistor,
    spring,
    waveform,
)

RectTuple = tuple[float, float, float, float]


@dataclass
class StrokeItem:
    points: list[Point]
    color: str = "chalk"
    width_px: float = config.STROKE_WIDTH_PX
    seed: int = 0
    passes: int = 2
    alpha: float = 1.0
    progress: float = 1.0


@dataclass
class Board:
    font: HersheyFont | None = None
    items: list[StrokeItem] = field(default_factory=list)
    _seed: int = 0

    def __post_init__(self) -> None:
        if self.font is None:
            self.font = HersheyFont.load()

    def next_seed(self) -> int:
        self._seed += 1
        return self._seed

    def clear(self) -> None:
        self.items.clear()

    def add_polyline(
        self,
        points: list[Point],
        color: str = "chalk",
        width_px: float | None = None,
        alpha: float = 1.0,
    ) -> StrokeItem:
        item = StrokeItem(
            points=list(points),
            color=color,
            width_px=config.STROKE_WIDTH_PX if width_px is None else width_px,
            seed=self.next_seed(),
            alpha=alpha,
        )
        self.items.append(item)
        return item

    def add_shape(self, shape: str, **kwargs: Any) -> list[StrokeItem]:
        color = str(kwargs.pop("color", "diagram"))
        width = kwargs.pop("width_px", None)
        if shape in {"line", "arrow"}:
            start = kwargs.pop("start")
            end = kwargs.pop("end")
            strokes = line(start, end) if shape == "line" else arrow(start, end)
        elif shape == "polyline":
            strokes = polyline(kwargs.pop("points"))
        elif shape == "circle":
            strokes = circle(kwargs.pop("center"), float(kwargs.pop("radius")))
        elif shape == "ellipse":
            strokes = ellipse(normalize_rect(kwargs.pop("rect")))
        elif shape == "rect":
            strokes = rectangle(normalize_rect(kwargs.pop("rect")))
        elif shape == "axes":
            strokes = axes(normalize_rect(kwargs.pop("rect")))
        elif shape == "incline":
            strokes = incline(normalize_rect(kwargs.pop("rect")))
        elif shape == "block":
            strokes = block(normalize_rect(kwargs.pop("rect")))
        elif shape == "resistor":
            strokes = resistor(normalize_rect(kwargs.pop("rect")))
        elif shape == "battery":
            strokes = battery(normalize_rect(kwargs.pop("rect")))
        elif shape == "grid":
            strokes = grid(normalize_rect(kwargs.pop("rect")))
        elif shape == "waveform":
            rect = normalize_rect(kwargs.pop("rect"))
            strokes = waveform(rect, float(kwargs.pop("cycles", 3.0)))
        elif shape == "spring":
            strokes = spring(
                kwargs.pop("start"),
                kwargs.pop("end"),
            )
        else:
            raise ValueError(f"unsupported shape {shape!r}")
        return [self.add_polyline(stroke, color, width) for stroke in strokes]

    def add_text(
        self,
        text: str,
        at: Point,
        size: float,
        color: str = "chalk",
        width_px: float | None = None,
        max_width: float | None = None,
        align: str = "left",
        tracking: float = 0.01,
        line_gap: float = 1.3,
    ) -> list[StrokeItem]:
        assert self.font is not None
        layout = self.font.layout(
            text,
            size=size,
            max_width=max_width,
            tracking=tracking,
            line_gap=line_gap,
            align=align,
        )
        return [
            self.add_polyline(stroke, color, width_px)
            for stroke in layout.translated(at[0], at[1])
        ]

    def build(self, transform: Transform, alpha_scale: float = 1.0) -> Mesh:
        jitter = config.STROKE_JITTER * min(transform.width, transform.height)
        all_strokes: list[ChalkStroke] = []
        for item in self.items:
            if item.progress <= 0.0:
                continue
            visible = partial_polyline(item.points, item.progress)
            if len(visible) < 2:
                continue
            pixel_points = [transform.to_px(point) for point in visible]
            chalk = make_chalk(
                pixel_points,
                width=item.width_px,
                color=item.color,
                seed=item.seed,
                jitter=jitter,
                passes=item.passes,
            )
            all_strokes.extend(replace(stroke, alpha=stroke.alpha * item.alpha) for stroke in chalk)
        return build_mesh(all_strokes, transform, alpha_scale)
