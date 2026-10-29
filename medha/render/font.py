"""Hershey vector font loading and text layout.

Glyph strokes are in font units (y-down, matching the board). The Futural set
uses an em of 32 units. Text layout returns normalized board units.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import config

from .geometry import Point, bounds

DEFAULT_TRACKING = 0.01
DEFAULT_LINE_GAP = 1.3


@dataclass(frozen=True)
class Glyph:
    char: str
    left: int
    right: int
    strokes: tuple[tuple[Point, ...], ...] = field(default_factory=tuple)

    @property
    def ink_width(self) -> int:
        xs = [x for stroke in self.strokes for x, _ in stroke]
        if not xs:
            return max(1, self.right - self.left)
        return max(1, round(max(xs) - min(xs)))

    @property
    def advance_units(self) -> int:
        if not self.strokes:
            return max(4, self.right - self.left)
        return max(3, self.ink_width + 4)


@dataclass
class TextLayout:
    strokes: list[list[Point]]
    width: float
    height: float
    lines: list[str]

    def translated(self, x: float, y: float) -> list[list[Point]]:
        return [[(px + x, py + y) for px, py in stroke] for stroke in self.strokes]


class HersheyFont:
    def __init__(
        self,
        glyphs: dict[str, Glyph],
        units_per_em: int = 32,
        fallback: str = "?",
    ) -> None:
        self.glyphs = glyphs
        self.units_per_em = units_per_em
        self.fallback = fallback

    @classmethod
    def load(cls, path: Path | None = None) -> HersheyFont:
        source = path or config.HERSHEY_PATH
        payload = json.loads(source.read_text(encoding="utf-8"))
        glyphs: dict[str, Glyph] = {}
        for char, raw in payload["glyphs"].items():
            strokes = tuple(
                tuple((float(x), float(y)) for x, y in stroke)
                for stroke in raw.get("strokes", [])
            )
            glyphs[char] = Glyph(
                char=char,
                left=int(raw.get("left", 0)),
                right=int(raw.get("right", 10)),
                strokes=strokes,
            )
        return cls(glyphs, units_per_em=int(payload.get("units_per_em", 32)))

    def glyph(self, char: str) -> Glyph | None:
        return self.glyphs.get(char) or self.glyphs.get(self.fallback)

    def advance(self, char: str, size: float, tracking: float = DEFAULT_TRACKING) -> float:
        glyph = self.glyph(char)
        if glyph is None:
            return size * 0.5
        return (glyph.advance_units / self.units_per_em) * size + tracking * size

    def line_width(self, text: str, size: float, tracking: float = DEFAULT_TRACKING) -> float:
        return sum(self.advance(char, size, tracking) for char in text)

    def layout(
        self,
        text: str,
        size: float,
        max_width: float | None = None,
        tracking: float = DEFAULT_TRACKING,
        line_gap: float = DEFAULT_LINE_GAP,
        align: str = "left",
    ) -> TextLayout:
        lines = self._wrap(text, size, max_width, tracking)
        if not lines:
            return TextLayout([], 0.0, 0.0, [])

        strokes: list[list[Point]] = []
        widths = [self.line_width(line, size, tracking) for line in lines]
        block_width = max(widths, default=0.0)
        for line_index, line in enumerate(lines):
            offset = 0.0
            if align == "center":
                offset = (block_width - widths[line_index]) / 2.0
            elif align == "right":
                offset = block_width - widths[line_index]
            pen_x = offset
            y = line_index * size * line_gap
            for char in line:
                glyph = self.glyph(char)
                if glyph is not None:
                    scale = size / self.units_per_em
                    for stroke in glyph.strokes:
                        strokes.append([(pen_x + x * scale, y + yy * scale) for x, yy in stroke])
                pen_x += self.advance(char, size, tracking)

        if strokes:
            min_x, min_y, max_x, max_y = bounds([p for stroke in strokes for p in stroke])
            strokes = [[(x - min_x, y - min_y) for x, y in stroke] for stroke in strokes]
            return TextLayout(strokes, max_x - min_x, max_y - min_y, lines)
        return TextLayout([], block_width, len(lines) * size * line_gap, lines)

    def _wrap(
        self,
        text: str,
        size: float,
        max_width: float | None,
        tracking: float,
    ) -> list[str]:
        lines: list[str] = []
        for paragraph in text.replace("\t", " ").split("\n"):
            if not paragraph:
                lines.append("")
                continue
            current = ""
            for word in paragraph.split(" "):
                candidate = word if not current else f"{current} {word}"
                if (
                    max_width is not None
                    and current
                    and self.line_width(candidate, size, tracking) > max_width
                ):
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            lines.append(current)
        while lines and lines[-1] == "":
            lines.pop()
        return lines
