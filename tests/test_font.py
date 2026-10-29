from __future__ import annotations

from medha.render.font import HersheyFont


def test_load_hershey_font() -> None:
    font = HersheyFont.load()
    assert len(font.glyphs) >= 90
    glyph = font.glyph("A")
    assert glyph is not None
    assert len(glyph.strokes) == 3
    space = font.glyph(" ")
    assert space is not None
    assert space.strokes == ()


def test_text_layout_returns_chalk_strokes() -> None:
    font = HersheyFont.load()
    layout = font.layout("A", size=0.1)
    assert len(layout.strokes) == 3
    assert layout.width > 0
    assert layout.height > 0


def test_narrow_glyphs_use_tighter_advance() -> None:
    font = HersheyFont.load()
    narrow = font.glyph("i")
    wide = font.glyph("R")
    assert narrow is not None
    assert wide is not None
    assert narrow.advance_units < wide.advance_units
    assert font.advance("i", 0.1) < font.advance("m", 0.1)


def test_title_text_fits_in_band() -> None:
    font = HersheyFont.load()
    width = font.line_width("Right Triangle", 0.074, tracking=0.01)
    assert width < 0.6


def test_text_layout_wraps() -> None:
    font = HersheyFont.load()
    layout = font.layout("A A A A A", size=0.1, max_width=0.05)
    assert len(layout.lines) > 1


def test_text_layout_aligns() -> None:
    font = HersheyFont.load()
    left = font.layout("A\nAA", size=0.1, align="left")
    right = font.layout("A\nAA", size=0.1, align="right")
    left_first = max(x for stroke in left.strokes[:3] for x, _ in stroke)
    right_first = max(x for stroke in right.strokes[:3] for x, _ in stroke)
    assert left_first < right_first


def test_unknown_glyph_uses_fallback() -> None:
    font = HersheyFont.load()
    layout = font.layout("\x01", size=0.1)
    assert layout.strokes


def test_translated_layout() -> None:
    font = HersheyFont.load()
    layout = font.layout("A", size=0.1)
    moved = layout.translated(0.3, 0.4)
    old_x = layout.strokes[0][0][0]
    assert moved[0][0][0] == old_x + 0.3
