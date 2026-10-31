"""Generate the Medha x Team Kanon pitch deck (.pptx).

Run with: .\\.venv\\Scripts\\python.exe tools\\make_pitch_deck.py
Output:   Medha-Kanon-Pitch.pptx at the repository root.
"""

from __future__ import annotations

import math
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Medha-Kanon-Pitch.pptx"

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BG = RGBColor(0x0F, 0x17, 0x2A)
PANEL = RGBColor(0x13, 0x20, 0x38)
PANEL_2 = RGBColor(0x17, 0x27, 0x42)
PANEL_3 = RGBColor(0x0B, 0x12, 0x20)
EMERALD = RGBColor(0x10, 0xB9, 0x81)
EMERALD_DARK = RGBColor(0x06, 0x4E, 0x3B)
EMERALD_SOFT = RGBColor(0x0E, 0x2A, 0x24)
GOLD = RGBColor(0xD4, 0xAF, 0x37)
GOLD_SOFT = RGBColor(0x3A, 0x2F, 0x14)
CHALK = RGBColor(0xF8, 0xFA, 0xFC)
MUTED = RGBColor(0x94, 0xA3, 0xB8)
DIM = RGBColor(0x64, 0x74, 0x8B)
BORDER = RGBColor(0x1E, 0x29, 0x3B)
RED = RGBColor(0xEF, 0x44, 0x44)
RED_SOFT = RGBColor(0x3A, 0x16, 0x16)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

BODY = "Segoe UI"
MONO = "Consolas"

SLIDE_W = 13.333
SLIDE_H = 7.5
TOTAL = 24


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------
def style_run(run, size=12, color=CHALK, bold=False, font=BODY, italic=False):
    font_obj = run.font
    font_obj.name = font
    font_obj.size = Pt(size)
    font_obj.bold = bold
    font_obj.italic = italic
    font_obj.color.rgb = color


def add_text(
    slide,
    x,
    y,
    w,
    h,
    text,
    size=12,
    color=CHALK,
    bold=False,
    font=BODY,
    align=PP_ALIGN.LEFT,
    anchor=MSO_ANCHOR.TOP,
    line=1.0,
    italic=False,
    margins=(0, 0, 0, 0),
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = True
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.margin_left, frame.margin_right, frame.margin_top, frame.margin_bottom = (
        Inches(m) for m in margins
    )
    frame.vertical_anchor = anchor
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.line_spacing = line
    run = paragraph.add_run()
    run.text = text
    style_run(run, size=size, color=color, bold=bold, font=font, italic=italic)
    return box


def rich_text(
    slide,
    x,
    y,
    w,
    h,
    paragraphs,
    anchor=MSO_ANCHOR.TOP,
    margins=(0, 0, 0, 0),
    wrap=True,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = wrap
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.margin_left, frame.margin_right, frame.margin_top, frame.margin_bottom = (
        Inches(m) for m in margins
    )
    frame.vertical_anchor = anchor
    first = True
    for spec in paragraphs:
        paragraph = frame.paragraphs[0] if first else frame.add_paragraph()
        first = False
        paragraph.alignment = spec.get("align", PP_ALIGN.LEFT)
        paragraph.line_spacing = spec.get("line", 1.0)
        if "space_before" in spec:
            paragraph.space_before = Pt(spec["space_before"])
        if "space_after" in spec:
            paragraph.space_after = Pt(spec["space_after"])
        for text, style in spec["runs"]:
            run = paragraph.add_run()
            run.text = text
            style_run(run, **style)
    return box


def rect(slide, x, y, w, h, fill, line=None, line_w=0.75, radius=None):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius is not None else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(
        shape_type, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    if radius is not None:
        shape.adjustments[0] = radius
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(line_w)
    shape.shadow.inherit = False
    return shape


def circle(slide, x, y, d, fill, line=None, line_w=1.0):
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(line_w)
    shape.shadow.inherit = False
    return shape


def line(slide, x1, y1, x2, y2, color=BORDER, width=1.0):
    connector = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(x1),
        Inches(y1),
        Inches(x2),
        Inches(y2),
    )
    connector.line.color.rgb = color
    connector.line.width = Pt(width)
    return connector


def chip(slide, x, y, w, h, text, fill=EMERALD_SOFT, border=EMERALD, color=EMERALD, size=8.5):
    shape = rect(slide, x, y, w, h, fill, line=border, line_w=0.75, radius=0.35)
    add_text(
        slide,
        x,
        y,
        w,
        h,
        text,
        size=size,
        color=color,
        bold=True,
        align=PP_ALIGN.CENTER,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    return shape


def label(slide, x, y, text, color=EMERALD, size=8.5, w=4.0):
    add_text(slide, x, y, w, 0.24, text, size=size, color=color, bold=True)


def base_slide(prs, kicker, title, number, source=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = BG

    rect(slide, 0, 0, SLIDE_W, 0.045, EMERALD)
    add_text(
        slide,
        0.7,
        0.36,
        9.5,
        0.25,
        kicker.upper(),
        size=8.5,
        color=EMERALD,
        bold=True,
    )
    add_text(slide, 0.68, 0.66, 11.95, 0.72, title, size=26, color=CHALK, bold=True)
    line(slide, 0.7, 1.55, 12.63, 1.55, BORDER, 1.0)
    line(slide, 0.7, 1.55, 2.4, 1.55, EMERALD, 2.0)

    add_text(
        slide,
        12.0,
        7.04,
        0.63,
        0.2,
        f"{number:02d} / {TOTAL}",
        size=8.5,
        color=DIM,
        align=PP_ALIGN.RIGHT,
    )
    line(slide, 11.9, 7.16, 12.62, 7.16, BORDER, 0.75)

    if source:
        add_text(
            slide,
            0.7,
            7.04,
            11.0,
            0.22,
            source,
            size=7.2,
            color=DIM,
        )
    return slide


def bullets(slide, items, x, y, w, gap=0.52, size=11.5, color=CHALK, marker=EMERALD):
    for index, item in enumerate(items):
        top = y + index * gap
        rect(slide, x, top + 0.075, 0.075, 0.075, marker)
        add_text(slide, x + 0.2, top, w - 0.2, gap, item, size=size, color=color, line=1.05)


def footer_chip_row(slide, items, y=6.45, x=0.7):
    cursor = x
    for item in items:
        width = 0.16 + 0.085 * len(item)
        chip(slide, cursor, y, width, 0.34, item, size=8.0)
        cursor += width + 0.14


# ---------------------------------------------------------------------------
# Slide 1 - Cover
# ---------------------------------------------------------------------------
def slide_cover(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = BG

    rect(slide, 0, 0, SLIDE_W, 0.05, EMERALD)
    rect(slide, 0.7, 0.02, 3.2, 0.02, GOLD)

    add_text(slide, 0.8, 0.7, 6.0, 0.25, "TEAM KANON  •  HACKATHON 2026", size=9, color=EMERALD, bold=True)
    add_text(slide, 0.72, 1.18, 6.2, 1.0, "Medha", size=66, color=CHALK, bold=True)
    add_text(slide, 0.8, 2.33, 6.2, 0.55, "AI Blackboard Teacher", size=27, color=GOLD, bold=True)
    add_text(
        slide,
        0.8,
        2.98,
        5.9,
        0.75,
        "Extending college STEM lectures,\nstroke by stroke.",
        size=17,
        color=MUTED,
        line=1.15,
    )
    add_text(
        slide,
        0.8,
        3.78,
        5.9,
        0.28,
        "UNIVERSITY & HIGHER-EDUCATION STEM DEPARTMENTS",
        size=9.2,
        color=EMERALD,
        bold=True,
    )

    metrics = [
        ("60 FPS", "render target"),
        ("4–8 GB", "local RAM"),
        ("±150 ms", "audio sync"),
        ("100%", "offline"),
    ]
    for index, (value, caption) in enumerate(metrics):
        x = 0.8 + index * 1.47
        rect(slide, x, 4.22, 1.33, 0.86, PANEL, line=BORDER, radius=0.08)
        add_text(slide, x + 0.12, 4.31, 1.1, 0.3, value, size=15, color=CHALK, bold=True)
        add_text(slide, x + 0.12, 4.65, 1.1, 0.22, caption, size=7.5, color=MUTED)

    add_text(
        slide,
        0.8,
        5.48,
        6.0,
        0.28,
        "Professor's Bridge  •  Offline-First  •  Multi-Regional Voice",
        size=11.5,
        color=GOLD,
        bold=True,
    )
    line(slide, 0.8, 5.93, 6.4, 5.93, BORDER, 0.75)
    add_text(slide, 0.8, 6.02, 1.6, 0.2, "TEAM KANON", size=8.5, color=EMERALD, bold=True)
    add_text(
        slide,
        0.8,
        6.25,
        6.0,
        0.24,
        "Pranav N  •  Disha R  •  Soyal  •  Kruthika",
        size=9.5,
        color=MUTED,
    )

    # Chalkboard visual
    panel_x, panel_y, panel_w, panel_h = 7.28, 1.12, 5.35, 5.35
    rect(slide, panel_x + 0.06, panel_y + 0.08, panel_w, panel_h, PANEL_3, radius=0.04)
    rect(slide, panel_x, panel_y, panel_w, panel_h, PANEL_2, line=BORDER, radius=0.04)

    # subtle grid
    for i in range(1, 5):
        line(slide, panel_x + 0.18, panel_y + i * 0.9, panel_x + panel_w - 0.18, panel_y + i * 0.9, RGBColor(0x1E, 0x29, 0x3B), 0.6)
    for i in range(1, 5):
        line(slide, panel_x + i * 1.02, panel_y + 0.2, panel_x + i * 1.02, panel_y + 4.55, RGBColor(0x1E, 0x29, 0x3B), 0.6)

    add_text(slide, panel_x + 0.22, panel_y + 0.16, 3.0, 0.2, "LIVE VECTOR CANVAS", size=7.8, color=EMERALD, bold=True)
    chip(slide, panel_x + panel_w - 0.92, panel_y + 0.13, 0.72, 0.26, "60 FPS", size=7.5)

    add_text(slide, panel_x + 0.25, panel_y + 0.62, 4.8, 0.62, "F = m a", size=37, color=CHALK, font=MONO, bold=True)
    add_text(slide, panel_x + 0.27, panel_y + 1.30, 4.8, 0.4, "a = F / m", size=21, color=EMERALD, font=MONO)

    # vector arrow
    line(slide, panel_x + 0.85, panel_y + 2.35, panel_x + 2.55, panel_y + 2.35, GOLD, 2.5)
    tri = slide.shapes.add_shape(
        MSO_SHAPE.ISOSCELES_TRIANGLE,
        Inches(panel_x + 2.55),
        Inches(panel_y + 2.20),
        Inches(0.22),
        Inches(0.30),
    )
    tri.rotation = 90
    tri.fill.solid()
    tri.fill.fore_color.rgb = GOLD
    tri.line.fill.background()
    tri.shadow.inherit = False
    add_text(slide, panel_x + 0.8, panel_y + 2.02, 1.4, 0.22, "force", size=8, color=GOLD, bold=True)
    add_text(slide, panel_x + 3.2, panel_y + 1.95, 1.8, 0.5, "vector\nstrokes", size=9, color=MUTED)

    # waveform
    add_text(slide, panel_x + 0.22, panel_y + 4.02, 3.0, 0.2, "SYNCHRONIZED NARRATION", size=7.8, color=GOLD, bold=True)
    bars = 30
    base_y = panel_y + 4.95
    for i in range(bars):
        height = 0.12 + abs(math.sin(i * 0.55)) * 0.52
        color = EMERALD if i % 3 else GOLD
        rect(
            slide,
            panel_x + 0.24 + i * 0.162,
            base_y - height,
            0.085,
            height,
            color,
            radius=0.45,
        )
    add_text(slide, panel_x + 0.24, panel_y + 5.02, 4.8, 0.2, "sentence-level speech  •  ±150 ms target", size=7.6, color=MUTED)

    return slide


# ---------------------------------------------------------------------------
# Slide 2 - Executive snapshot
# ---------------------------------------------------------------------------
def slide_snapshot(prs):
    slide = base_slide(
        prs,
        "Executive snapshot",
        "The 30-second version",
        2,
        "Sources: UDISE+ 2025–26; Mordor Intelligence 2025–2030; Medha repository (README, MODELS.md).",
    )
    cards = [
        ("PROBLEM", "100%", "of the live board build-up disappears when the lecture ends."),
        ("SOLUTION", "Local", "AI blackboard that redraws derivations and narrates every step."),
        ("MARKET", "$41.01B", "global AI-in-education spend projected by 2030 at 42.83% CAGR."),
        ("MODEL", "₹0", "cloud inference per student on campus; department licensing."),
    ]
    positions = [(0.7, 1.9), (6.82, 1.9), (0.7, 4.12), (6.82, 4.12)]
    for (label_text, value, body), (x, y) in zip(cards, positions, strict=True):
        rect(slide, x, y, 5.82, 2.05, PANEL, line=BORDER, radius=0.06)
        rect(slide, x, y, 0.06, 2.05, EMERALD if label_text != "PROBLEM" else GOLD)
        add_text(slide, x + 0.28, y + 0.22, 5.2, 0.22, label_text, size=8.5, color=EMERALD if label_text != "PROBLEM" else GOLD, bold=True)
        add_text(slide, x + 0.28, y + 0.52, 5.2, 0.62, value, size=31, color=CHALK, bold=True)
        add_text(slide, x + 0.28, y + 1.22, 5.2, 0.62, body, size=11.2, color=MUTED, line=1.12)

    rect(slide, 0.7, 6.34, 11.95, 0.48, EMERALD_SOFT, line=EMERALD_DARK, radius=0.2)
    add_text(
        slide,
        0.95,
        6.42,
        11.5,
        0.3,
        "Built on a fully local stack: Qwen3  •  BGE-M3  •  BGE reranker  •  Kokoro  •  Docling  •  OpenGL",
        size=10.2,
        color=EMERALD,
        bold=True,
    )
    return slide


# ---------------------------------------------------------------------------
# Slide 3 - Problem
# ---------------------------------------------------------------------------
def slide_problem(prs):
    slide = base_slide(
        prs,
        "Problem",
        "The lecture ends. The derivation disappears.",
        3,
        "Observation from lecture workflows; no external citation required.",
    )

    rect(slide, 0.7, 1.9, 6.3, 4.6, PANEL, line=BORDER, radius=0.04)
    rect(slide, 0.95, 2.12, 5.8, 1.85, PANEL_3, line=BORDER, radius=0.03)
    add_text(slide, 1.15, 2.25, 3.0, 0.2, "DURING CLASS", size=8, color=EMERALD, bold=True)
    add_text(slide, 1.15, 2.55, 4.6, 0.55, "F = m a", size=29, color=CHALK, font=MONO, bold=True)
    add_text(slide, 1.18, 3.12, 4.8, 0.28, "reasoning visible  •  build-up paced with voice", size=9, color=MUTED)
    line(slide, 1.15, 3.52, 6.35, 3.52, BORDER, 0.75)
    add_text(slide, 5.2, 3.2, 1.35, 0.28, "LIVE", size=9, color=EMERALD, bold=True, align=PP_ALIGN.RIGHT)

    rect(slide, 0.95, 4.18, 5.8, 2.05, PANEL_3, line=BORDER, radius=0.03)
    add_text(slide, 1.15, 4.32, 3.0, 0.2, "AFTER CLASS", size=8, color=DIM, bold=True)
    add_text(slide, 1.15, 4.62, 4.6, 0.7, "?", size=44, color=RGBColor(0x33, 0x41, 0x55), bold=True)
    add_text(slide, 1.8, 4.75, 4.2, 0.6, "Board erased.\nOnly photos remain.", size=12, color=DIM, line=1.15)
    add_text(slide, 5.2, 4.42, 1.35, 0.28, "LOST", size=9, color=GOLD, bold=True, align=PP_ALIGN.RIGHT)

    add_text(slide, 7.32, 1.95, 5.2, 0.3, "THREE COMPOUNDING FAILURES", size=8.5, color=EMERALD, bold=True)
    bullets(
        slide,
        [
            "Students photograph the final answer, not the reasoning that produced it.",
            "Professors spend 10+ hours per week redrawing diagrams and derivations.",
            "Recorded lectures are linear; a single step cannot be re-explained in another language.",
        ],
        7.35,
        2.38,
        5.15,
        gap=0.86,
        size=11.2,
    )

    rect(slide, 7.32, 5.12, 5.2, 1.08, GOLD_SOFT, line=GOLD, line_w=0.75, radius=0.05)
    add_text(
        slide,
        7.55,
        5.24,
        4.8,
        0.85,
        "The blackboard is the highest-bandwidth teaching surface — and the least persistent.",
        size=11.5,
        color=GOLD,
        bold=True,
        line=1.12,
    )
    add_text(slide, 7.32, 6.38, 5.2, 0.24, "This is the gap Medha closes.", size=9, color=MUTED, italic=True)
    return slide


# ---------------------------------------------------------------------------
# Slide 4 - Infrastructure reality
# ---------------------------------------------------------------------------
def slide_infrastructure(prs):
    slide = base_slide(
        prs,
        "Infrastructure reality",
        "Connected enough to adopt. Offline enough to need it.",
        4,
        "Sources: Ministry of Education / PIB UDISE+ 2025–26 Summary (PRID=2300408); UDISE+ 2025–26 / NIEPA Analysis Table 2.5; ITU Facts and Figures 2024 (27 Nov 2024).",
    )
    stats = [
        ("14.67 Lakh", "schools"),
        ("1.03 Crore", "teachers"),
        ("24.72 Crore", "enrolled students"),
    ]
    for index, (value, caption) in enumerate(stats):
        x = 0.7 + index * 4.05
        rect(slide, x, 1.88, 3.85, 1.02, PANEL, line=BORDER, radius=0.06)
        add_text(slide, x + 0.22, 1.98, 3.4, 0.42, value, size=21, color=CHALK, bold=True)
        add_text(slide, x + 0.22, 2.44, 3.4, 0.22, caption, size=8.5, color=MUTED)

    # Left chart
    rect(slide, 0.7, 3.18, 6.4, 3.45, PANEL, line=BORDER, radius=0.04)
    add_text(slide, 0.95, 3.32, 5.8, 0.25, "CAMPUS INFRASTRUCTURE  •  UDISE+ 2025–26", size=8.2, color=EMERALD, bold=True)

    baseline = 6.02
    max_h = 1.62
    line(slide, 1.15, baseline, 6.85, baseline, RGBColor(0x33, 0x41, 0x55), 1.0)
    for pct in (25, 50, 75, 100):
        y = baseline - max_h * pct / 100
        line(slide, 1.15, y, 6.85, y, RGBColor(0x1E, 0x29, 0x3B), 0.6)
        add_text(slide, 0.8, y - 0.07, 0.3, 0.16, str(pct), size=6.2, color=DIM, align=PP_ALIGN.RIGHT)

    bars = [("Computers available", 69.9, 2.15, EMERALD), ("Internet connected", 67.4, 4.45, GOLD)]
    for name, value, x, color in bars:
        h = max_h * value / 100
        rect(slide, x, baseline - h, 0.72, h, color, radius=0.05)
        add_text(slide, x - 0.15, baseline - h - 0.34, 1.02, 0.26, f"{value}%", size=14, color=color, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, x - 0.28, baseline + 0.12, 1.3, 0.24, name, size=8.2, color=MUTED, align=PP_ALIGN.CENTER)

    add_text(slide, 1.15, 6.25, 5.6, 0.22, "Computers are more common than connectivity.", size=8.5, color=DIM, italic=True)

    # Right callout
    rect(slide, 7.3, 3.18, 5.33, 3.45, PANEL, line=BORDER, radius=0.04)
    add_text(slide, 7.55, 3.34, 4.8, 0.22, "THE GAP IS THE OPPORTUNITY", size=8.2, color=GOLD, bold=True)
    add_text(slide, 7.55, 3.62, 4.8, 0.7, "32.6%", size=38, color=GOLD, bold=True)
    add_text(slide, 7.58, 4.28, 4.7, 0.3, "of campuses lack internet  •  4,77,491 institutions", size=9.2, color=MUTED)

    rect(slide, 7.55, 4.72, 4.82, 0.16, RGBColor(0x1E, 0x29, 0x3B), radius=0.45)
    rect(slide, 7.55, 4.72, 4.82 * 0.674, 0.16, EMERALD, radius=0.45)
    add_text(slide, 7.55, 4.9, 2.4, 0.2, "67.4% connected", size=7.8, color=EMERALD, bold=True)
    add_text(slide, 10.7, 4.9, 1.7, 0.2, "32.6% not connected", size=7.8, color=GOLD, bold=True, align=PP_ALIGN.RIGHT)

    line(slide, 7.55, 5.28, 12.37, 5.28, BORDER, 0.75)
    add_text(slide, 7.55, 5.42, 4.8, 0.3, "2.6 Billion", size=19, color=CHALK, bold=True)
    add_text(slide, 7.58, 5.74, 4.7, 0.42, "people offline in 2024 — 32% of the world, 1.8B rural.", size=8.8, color=MUTED, line=1.1)
    add_text(slide, 7.55, 6.26, 4.8, 0.22, "Offline is not a fallback. It is the deployment model.", size=8.5, color=EMERALD, bold=True)
    return slide


# ---------------------------------------------------------------------------
# Slide 5 - Market opportunity
# ---------------------------------------------------------------------------
def slide_market(prs):
    slide = base_slide(
        prs,
        "Market opportunity",
        "A large market growing faster than the tooling.",
        5,
        "Sources: Mordor Intelligence AI in Education Report 2025–2030; IAMAI–Grant Thornton Bharat Report (Jan 2025); Grand View Research; MarketsandMarkets (Oct 2026).",
    )
    growth = [
        ("GLOBAL AI IN EDUCATION", "$6.90B", "$41.01B", "2025 → 2030  •  CAGR 42.83%"),
        ("INDIA EDTECH OPPORTUNITY", "₹64,875 Cr", "₹2,50,850 Cr", "$7.50B → $29.00B  •  CAGR 25.8%"),
    ]
    for index, (name, start, end, sub) in enumerate(growth):
        x = 0.7 + index * 6.12
        rect(slide, x, 1.88, 5.82, 1.8, PANEL, line=BORDER, radius=0.05)
        add_text(slide, x + 0.24, 2.0, 5.3, 0.2, name, size=8.2, color=EMERALD, bold=True)
        rich_text(
            slide,
            x + 0.24,
            2.28,
            5.35,
            0.62,
            [{
                "runs": [
                    (start, {"size": 21, "color": MUTED, "bold": True}),
                    ("  →  ", {"size": 21, "color": GOLD, "bold": True}),
                    (end, {"size": 21, "color": CHALK, "bold": True}),
                ]
            }],
        )
        add_text(slide, x + 0.24, 3.02, 5.3, 0.24, sub, size=8.8, color=MUTED)

    rect(slide, 0.7, 3.95, 11.95, 2.55, PANEL, line=BORDER, radius=0.04)
    add_text(slide, 0.95, 4.08, 8.0, 0.22, "2030 GLOBAL AI-IN-EDUCATION FORECASTS  •  SCOPE DIFFERS BY HOUSE", size=8.2, color=GOLD, bold=True)
    rows = [
        ("Mordor Intelligence", 41.01, "42.83% CAGR"),
        ("Grand View Research", 32.27, "31.20% CAGR"),
        ("MarketsandMarkets", 5.82, "17.50% CAGR"),
    ]
    max_value = 41.01
    for index, (name, value, note) in enumerate(rows):
        y = 4.55 + index * 0.58
        add_text(slide, 0.98, y + 0.02, 2.35, 0.22, name, size=8.6, color=CHALK)
        rect(slide, 3.35, y + 0.02, 5.6, 0.2, RGBColor(0x1E, 0x29, 0x3B), radius=0.45)
        rect(slide, 3.35, y + 0.02, 5.6 * value / max_value, 0.2, EMERALD if index == 0 else EMERALD_DARK, radius=0.45)
        add_text(slide, 9.1, y, 1.2, 0.22, f"${value:.2f}B", size=9.5, color=CHALK, bold=True)
        add_text(slide, 10.35, y + 0.02, 1.7, 0.22, note, size=7.8, color=MUTED, align=PP_ALIGN.RIGHT)

    add_text(slide, 0.98, 6.26, 11.2, 0.2, "Use these as a range, not a single point estimate. The direction is unambiguous: double-digit to 40%+ growth.", size=8.0, color=DIM, italic=True)
    return slide


# ---------------------------------------------------------------------------
# Slide 6 - Personas
# ---------------------------------------------------------------------------
def slide_personas(prs):
    slide = base_slide(
        prs,
        "Target personas",
        "Three buyers, one repeated pain.",
        6,
        "Typecast for pitch narrative; not a statistical sample. Telugu language pack is on the roadmap.",
    )
    cards = [
        (
            "BK",
            "B2B Buyer",
            "College Dean / HOD",
            "4,000+ Tier-2/3 engineering colleges in India.",
            "Drive pass rates and accreditation without hiring more faculty.",
            "Decision metric: departments onboarded, cost per student.",
        ),
        (
            "AS",
            "Educator Champion",
            "Prof. Ananya Sharma",
            "College STEM faculty teaching calculus, optics, mechanics.",
            "Save 10+ hours/week preparing geometry and board derivations.",
            "Runs on existing faculty laptop: 4–8 GB RAM.",
        ),
        (
            "RP",
            "End User",
            "Ramesh Patel, 2nd-year student",
            "Engineering undergraduate preparing for internal exams.",
            "Replay the professor's derivation step-by-step, in a regional language.",
            "Languages: Kannada, Hindi, Telugu (Telugu on roadmap).",
        ),
    ]
    for index, (initials, role, name, target, goal, spec) in enumerate(cards):
        x = 0.7 + index * 4.05
        rect(slide, x, 1.9, 3.85, 4.42, PANEL, line=BORDER, radius=0.05)
        circle(slide, x + 0.24, 2.1, 0.58, EMERALD_SOFT, line=EMERALD, line_w=1.0)
        add_text(slide, x + 0.24, 2.2, 0.58, 0.3, initials, size=12, color=EMERALD, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, x + 0.96, 2.12, 2.7, 0.32, name, size=12.5, color=CHALK, bold=True)
        add_text(slide, x + 0.96, 2.45, 2.7, 0.22, role, size=8.2, color=GOLD, bold=True)
        rich_text(
            slide,
            x + 0.24,
            2.92,
            3.38,
            3.15,
            [
                {"runs": [("TARGET", {"size": 7.5, "color": EMERALD, "bold": True})], "space_after": 2},
                {"runs": [(target, {"size": 9.0, "color": MUTED})], "line": 1.08, "space_after": 10},
                {"runs": [("GOAL", {"size": 7.5, "color": EMERALD, "bold": True})], "space_after": 2},
                {"runs": [(goal, {"size": 9.0, "color": CHALK})], "line": 1.08, "space_after": 10},
                {"runs": [("HARDWARE / LANGUAGE", {"size": 7.5, "color": EMERALD, "bold": True})], "space_after": 2},
                {"runs": [(spec, {"size": 9.0, "color": MUTED})], "line": 1.08},
            ],
        )

    return slide


# ---------------------------------------------------------------------------
# Slide 7 - Solution loop
# ---------------------------------------------------------------------------
def slide_solution(prs):
    slide = base_slide(
        prs,
        "Solution",
        "One topic in. A teachable board out.",
        7,
        "Pipeline implemented in medha/lesson, medha/ingest, medha/rag, medha/render and medha/tts.",
    )
    steps = [
        ("01", "INGEST", "PDFs, PPTs, and professor's notes parsed with Docling."),
        ("02", "PLAN", "LLM writes a stepwise lesson, LaTeX, and narration."),
        ("03", "RENDER", "Vector chalk strokes build the board at 60 FPS."),
        ("04", "NARRATE", "Sentence-level speech stays within ±150 ms."),
        ("05", "CHECK", "Checkpoint questions and doubt analytics close the loop."),
    ]
    card_w = 2.16
    gap = 0.18
    for index, (number, title, body) in enumerate(steps):
        x = 0.7 + index * (card_w + gap)
        rect(slide, x, 1.92, card_w, 2.72, PANEL, line=BORDER, radius=0.06)
        circle(slide, x + 0.2, 2.1, 0.44, EMERALD_SOFT, line=EMERALD, line_w=1.0)
        add_text(slide, x + 0.2, 2.17, 0.44, 0.24, number, size=10, color=EMERALD, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, x + 0.2, 2.68, card_w - 0.4, 0.24, title, size=10, color=GOLD, bold=True)
        add_text(slide, x + 0.2, 2.98, card_w - 0.38, 1.4, body, size=9.2, color=MUTED, line=1.12)
        if index < len(steps) - 1:
            arrow = slide.shapes.add_shape(
                MSO_SHAPE.RIGHT_ARROW,
                Inches(x + card_w + 0.015),
                Inches(3.2),
                Inches(0.15),
                Inches(0.16),
            )
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = EMERALD
            arrow.line.fill.background()
            arrow.shadow.inherit = False

    rect(slide, 0.7, 4.95, 11.95, 1.15, EMERALD_SOFT, line=EMERALD_DARK, radius=0.05)
    add_text(slide, 0.95, 5.1, 8.0, 0.3, "One campus laptop or LAN server. No cloud API in the loop.", size=14, color=CHALK, bold=True)
    add_text(slide, 0.95, 5.47, 8.6, 0.3, "The professor's own syllabus becomes the grounding layer; the student sees the reasoning, not just the result.", size=9.2, color=MUTED)
    chips = [("Docling", 9.55), ("Ollama", 10.55), ("OpenGL", 11.5)]
    for text, x in chips:
        chip(slide, x, 5.28, 0.92, 0.34, text, size=8.2)
    return slide


# ---------------------------------------------------------------------------
# Slide 8 - Semantic actions
# ---------------------------------------------------------------------------
def slide_semantic(prs):
    slide = base_slide(
        prs,
        "Core design",
        "The model writes meaning. The renderer writes geometry.",
        8,
        "Contract: medha/core/schema.py and spec/board-action/v1/SPEC.md.",
    )
    rect(slide, 0.7, 1.9, 5.9, 4.02, PANEL, line=BORDER, radius=0.04)
    add_text(slide, 0.95, 2.04, 4.8, 0.22, "LLM OUTPUT  •  SEMANTIC ACTION", size=8.2, color=EMERALD, bold=True)
    code_lines = [
        "{",
        '  "op": "write_math",',
        '  "latex": "F = m a",',
        '  "rect": { "x": 0.08, "y": 0.24,',
        '            "w": 0.42, "h": 0.12 },',
        '  "duration_ms": 1500,',
        '  "start": { "sentence": 0, "char": 24 }',
        "}",
    ]
    code_paras = [
        {"runs": [(line_text, {"size": 9.0, "color": RGBColor(0xA7, 0xF3, 0xD0) if index not in (0, 7) else MUTED, "font": MONO})], "line": 1.28}
        for index, line_text in enumerate(code_lines)
    ]
    rich_text(slide, 0.95, 2.36, 5.4, 2.5, code_paras)
    add_text(slide, 0.95, 5.12, 5.4, 0.5, "No stroke points. No fonts. No pixels.", size=10.5, color=GOLD, bold=True)
    add_text(slide, 0.95, 5.44, 5.4, 0.3, "The contract stays small enough for a 4B model.", size=8.8, color=MUTED)

    rect(slide, 6.88, 1.9, 5.77, 4.02, PANEL, line=BORDER, radius=0.04)
    add_text(slide, 7.12, 2.04, 5.0, 0.22, "RENDERER OWNS", size=8.2, color=GOLD, bold=True)
    items = [
        "Normalized board coordinates and collision repair",
        "Stroke order, partial progress, and chalk texture",
        "Hershey font metrics and LaTeX-to-vector paths",
        "Audio-anchored timing and checkpoint placement",
    ]
    for index, item in enumerate(items):
        y = 2.42 + index * 0.66
        rect(slide, 7.12, y + 0.07, 0.075, 0.075, EMERALD)
        add_text(slide, 7.32, y, 5.0, 0.55, item, size=10.0, color=CHALK, line=1.05)

    add_text(slide, 7.12, 5.2, 5.2, 0.28, "Result", size=8.2, color=EMERALD, bold=True)
    add_text(slide, 7.12, 5.48, 5.2, 0.3, "Testable output  •  model-swappable  •  impossible to draw off-board", size=9.2, color=MUTED)

    rect(slide, 0.7, 6.12, 11.95, 0.55, GOLD_SOFT, line=GOLD, line_w=0.75, radius=0.2)
    add_text(slide, 0.95, 6.23, 11.4, 0.3, "This is why a small local model can produce a reliable classroom board.", size=11.5, color=GOLD, bold=True)
    return slide


# ---------------------------------------------------------------------------
# Slide 9 - Demo storyboard
# ---------------------------------------------------------------------------
def slide_storyboard(prs):
    slide = base_slide(
        prs,
        "Product experience",
        "What the student actually sees.",
        9,
        "Illustrative 60-second demo flow based on the Studio Create, playback, and checkpoint paths.",
    )
    frames = [
        ("01", "Professor uploads", "Unit 3 notes, 14 pages, one diagram-heavy PDF.", "DOCX / PDF"),
        ("02", "Medha plans", "6 steps, LaTeX equations, narration script.", "PLAN"),
        ("03", "Board builds", "Kannada voice plays while strokes appear in sync.", "LIVE"),
        ("04", "Checkpoint", "\"What happens if mass doubles?\" Analytics log the gap.", "CHECK"),
    ]
    for index, (number, title, body, tag) in enumerate(frames):
        x = 0.7 + index * 3.02
        rect(slide, x, 1.9, 2.84, 3.15, PANEL, line=BORDER, radius=0.05)
        rect(slide, x + 0.14, 2.04, 2.56, 1.28, PANEL_3, line=BORDER, radius=0.03)
        add_text(slide, x + 0.26, 2.16, 0.4, 0.22, number, size=8, color=EMERALD, bold=True)
        if index == 0:
            add_text(slide, x + 0.26, 2.42, 2.2, 0.26, "unit3_notes.pdf", size=9, color=CHALK, font=MONO)
            add_text(slide, x + 0.26, 2.72, 2.22, 0.45, "14 pages\n3 figures", size=8.5, color=MUTED)
        elif index == 1:
            add_text(slide, x + 0.26, 2.42, 2.2, 0.3, "s1  force", size=8.5, color=CHALK, font=MONO)
            add_text(slide, x + 0.26, 2.7, 2.2, 0.5, "s2  mass\ns3  acceleration", size=8.5, color=MUTED, font=MONO)
        elif index == 2:
            add_text(slide, x + 0.26, 2.4, 2.1, 0.42, "F = m a", size=17, color=CHALK, font=MONO, bold=True)
            add_text(slide, x + 0.26, 2.85, 2.2, 0.3, "a = F / m", size=10, color=EMERALD, font=MONO)
            line(slide, x + 0.26, 3.08, x + 2.4, 3.08, GOLD, 1.5)
        else:
            add_text(slide, x + 0.26, 2.4, 2.2, 0.55, "If mass doubles,\nwhat happens to a?", size=8.8, color=CHALK)
            add_text(slide, x + 0.26, 2.98, 2.2, 0.22, "answer: a halves", size=7.8, color=EMERALD, italic=True)
        add_text(slide, x + 0.14, 3.45, 2.56, 0.26, title, size=11.5, color=CHALK, bold=True)
        add_text(slide, x + 0.14, 3.76, 2.56, 0.85, body, size=8.6, color=MUTED, line=1.12)
        chip(slide, x + 0.14, 4.55, 0.72, 0.26, tag, size=7.2)

    rect(slide, 0.7, 5.38, 11.95, 0.95, PANEL, line=BORDER, radius=0.05)
    add_text(slide, 0.95, 5.5, 3.0, 0.26, "Replay any step.", size=11.5, color=CHALK, bold=True)
    add_text(slide, 0.95, 5.78, 3.6, 0.24, "No re-recording. No new lecture.", size=8.8, color=MUTED)
    for index, text in enumerate(["Switch language", "Ask a doubt", "Export to LMS"]):
        chip(slide, 5.2 + index * 2.25, 5.62, 1.95, 0.38, text, size=8.5)
    add_text(slide, 0.7, 6.55, 11.9, 0.24, "The same lesson can be replayed, translated, and grounded in the professor's notes.", size=8.8, color=DIM, italic=True)
    return slide


# ---------------------------------------------------------------------------
# Slide 10 - Competitive landscape overview
# ---------------------------------------------------------------------------
def slide_competitors_overview(prs):
    slide = base_slide(
        prs,
        "Competitive landscape",
        "Five categories. One empty quadrant.",
        10,
        "Sources: Khanmigo public pricing page (Oct 2026); UNDP Digital X Catalogue; DIKSHA / Ministry of Education; public product pages.",
    )
    cards = [
        ("MEDHA", "Proposed design", "Offline generative blackboard for higher-ed STEM. Vector derivations, regional voice, professor-grounded RAG.", "Live + offline"),
        ("KHANMIGO", "Khan Academy", "K-12 tutor in a text-chat interface. Strong content brand, but no live visual derivation build-up.", "Cloud chat"),
        ("KOLIBRI", "Learning Equality", "Offline K-12 library with 173+ language channels. Static media; no generative derivation or document Q&A.", "Offline static"),
        ("DIKSHA", "Ministry of Education", "National public digital infrastructure: e-textbooks, QR content, video. Static delivery, not interactive derivation.", "Public static"),
        ("GENERIC AI / MOOCs", "ChatGPT, Claude, NPTEL, YouTube", "Text-only chat that can drift off-syllabus, or fixed video that cannot re-explain a single step.", "Cloud / fixed"),
    ]
    for index, (name, who, body, tag) in enumerate(cards):
        x = 0.7 + index * 2.39
        highlight = index == 0
        rect(
            slide,
            x,
            1.9,
            2.21,
            4.35,
            EMERALD_SOFT if highlight else PANEL,
            line=EMERALD if highlight else BORDER,
            line_w=1.25 if highlight else 0.75,
            radius=0.05,
        )
        add_text(slide, x + 0.16, 2.05, 1.9, 0.2, name, size=8.4, color=EMERALD if highlight else CHALK, bold=True)
        add_text(slide, x + 0.16, 2.3, 1.9, 0.22, who, size=7.2, color=GOLD if highlight else MUTED)
        add_text(slide, x + 0.16, 2.65, 1.9, 2.6, body, size=8.2, color=CHALK if highlight else MUTED, line=1.12)
        chip(slide, x + 0.16, 5.55, 1.25, 0.28, tag, size=6.8, fill=EMERALD_DARK if highlight else PANEL_2, border=EMERALD if highlight else BORDER, color=EMERALD if highlight else MUTED)

    add_text(slide, 0.7, 6.5, 11.9, 0.3, "No incumbent combines offline deployment, live vector derivations, syllabus grounding, and regional voice.", size=10.5, color=GOLD, bold=True, align=PP_ALIGN.CENTER)
    return slide


# ---------------------------------------------------------------------------
# Slide 11 - Competitor matrix
# ---------------------------------------------------------------------------
def slide_matrix(prs):
    slide = base_slide(
        prs,
        "Competitive matrix",
        "Feature and architecture comparison.",
        11,
        "Sources: Khanmigo pricing (Oct 2026); Learning Equality / UNDP Digital X; DIKSHA / MoE; public product documentation. Pricing and scope as of Oct 2026.",
    )
    widths = [1.4, 2.2, 2.8, 3.0, 2.33]
    x_positions = []
    cursor = 0.7
    for width in widths:
        x_positions.append(cursor)
        cursor += width + 0.05

    headers = ["CATEGORY", "SCOPE", "BOARD & DERIVATION", "GROUNDING & LANGUAGES", "PRICING / DEPLOYMENT"]
    for x, width, header in zip(x_positions, widths, headers, strict=True):
        rect(slide, x, 1.84, width, 0.46, PANEL_2, line=BORDER, radius=0.03)
        add_text(slide, x + 0.08, 1.9, width - 0.16, 0.34, header, size=7.6, color=EMERALD, bold=True)

    rows = [
        ("MEDHA", "Proposed", "B2B university STEM departments", "Live stroke-by-stroke vector chalk; 60 FPS target", "Docling RAG over professor's PDFs; Kannada, Hindi, Telugu", "Local laptop/LAN; 4–8 GB RAM; ₹50k–₹1.5L/yr per dept"),
        ("KHANMIGO", "Khan Academy", "K-12 tutors, district plans", "Text chat; no live visual derivation build-up", "Khan Academy content; English-first", "Cloud web; $4/mo or $44/yr per user"),
        ("KOLIBRI", "Learning Equality", "Global offline K-12 learning", "Static pre-recorded media library", "173+ language channels; no generative document Q&A", "Free / MIT; self-hosted local server"),
        ("DIKSHA", "Ministry of Education", "National public digital infrastructure", "Static PDF and video playback", "State-board e-textbooks; QR-coded content", "Free government portal"),
        ("GENERIC AI / MOOCS", "ChatGPT, Claude, NPTEL", "General chat + video courses", "Text-only chat or fixed non-interactive video", "Open web (can drift off-syllabus) or fixed syllabus", "$20/mo cloud SaaS; free public streams"),
    ]
    row_h = 0.86
    for row_index, row in enumerate(rows):
        y = 2.38 + row_index * 0.91
        highlight = row_index == 0
        for col_index, (x, width) in enumerate(zip(x_positions, widths, strict=True)):
            cell = row[0] if col_index == 0 else row[col_index + 1]
            rect(
                slide,
                x,
                y,
                width,
                row_h,
                EMERALD_SOFT if highlight else PANEL,
                line=EMERALD if highlight else BORDER,
                line_w=0.9 if highlight else 0.6,
                radius=0.03,
            )
            if col_index == 0:
                rich_text(
                    slide,
                    x + 0.08,
                    y + 0.08,
                    width - 0.16,
                    row_h - 0.12,
                    [
                        {"runs": [(cell, {"size": 8.4, "color": EMERALD if highlight else CHALK, "bold": True})], "space_after": 1},
                        {"runs": [(row[1], {"size": 6.8, "color": GOLD if highlight else MUTED})]},
                    ],
                )
            else:
                add_text(
                    slide,
                    x + 0.08,
                    y + 0.08,
                    width - 0.16,
                    row_h - 0.12,
                    cell,
                    size=7.5,
                    color=CHALK if highlight else MUTED,
                    line=1.0,
                )
    return slide


# ---------------------------------------------------------------------------
# Slide 12 - Positioning
# ---------------------------------------------------------------------------
def slide_positioning(prs):
    slide = base_slide(
        prs,
        "Positioning",
        "Medha sits where offline meets generative.",
        12,
        "Qualitative positioning based on public product capabilities, Oct 2026.",
    )
    # Plot area
    px, py, pw, ph = 1.15, 1.95, 7.7, 4.55
    rect(slide, px, py, pw, ph, PANEL, line=BORDER, radius=0.03)
    mid_x = px + pw / 2
    mid_y = py + ph / 2
    line(slide, mid_x, py + 0.15, mid_x, py + ph - 0.15, BORDER, 1.0)
    line(slide, px + 0.15, mid_y, px + pw - 0.15, mid_y, BORDER, 1.0)

    add_text(slide, px + 0.18, py + 0.12, 3.2, 0.2, "OFFLINE / LOCAL", size=7.5, color=EMERALD, bold=True)
    add_text(slide, px + 0.18, py + ph - 0.58, 3.2, 0.2, "CLOUD-DEPENDENT", size=7.0, color=MUTED, bold=True)
    add_text(slide, px + 0.18, py + ph - 0.28, 2.6, 0.2, "STATIC CONTENT", size=7.0, color=MUTED, bold=True)
    add_text(slide, px + pw - 2.75, py + ph - 0.28, 2.55, 0.2, "GENERATIVE / INTERACTIVE", size=7.0, color=GOLD, bold=True, align=PP_ALIGN.RIGHT)

    def dot(x, y, name, color, r=0.09):
        circle(slide, x - r, y - r, r * 2, color)
        add_text(slide, x + 0.16, y - 0.14, 1.6, 0.28, name, size=7.8, color=CHALK)

    dot(px + 1.45, py + 1.2, "Kolibri", MUTED)
    dot(px + 1.35, py + 2.0, "DIKSHA", MUTED)
    dot(px + 1.6, py + 3.6, "MOOCs / NPTEL", MUTED)
    dot(px + pw - 1.75, py + 3.45, "ChatGPT / Claude", MUTED)
    dot(px + pw - 1.45, py + 2.35, "Khanmigo", MUTED)
    circle(slide, px + pw - 2.35, py + 1.05, 0.44, EMERALD_SOFT, line=EMERALD, line_w=1.2)
    circle(slide, px + pw - 2.22, py + 1.18, 0.18, EMERALD)
    add_text(slide, px + pw - 2.05, py + 0.98, 1.8, 0.3, "MEDHA", size=10.5, color=EMERALD, bold=True)
    add_text(slide, px + pw - 2.05, py + 1.26, 1.8, 0.22, "offline + generative", size=7.4, color=CHALK)

    # Right panel
    rect(slide, 9.15, 1.95, 3.48, 4.55, PANEL, line=BORDER, radius=0.04)
    add_text(slide, 9.36, 2.1, 3.0, 0.22, "THE EMPTY QUADRANT", size=8.0, color=GOLD, bold=True)
    add_text(slide, 9.36, 2.42, 3.0, 0.55, "Offline\n+ generative", size=20, color=CHALK, bold=True, line=1.0)
    add_text(
        slide,
        9.36,
        3.12,
        3.0,
        2.0,
        "Kolibri and DIKSHA are offline but static. Khanmigo and generic AI are generative but cloud-bound. Medha combines both.",
        size=9.0,
        color=MUTED,
        line=1.16,
    )
    line(slide, 9.36, 5.0, 12.4, 5.0, BORDER, 0.75)
    add_text(slide, 9.36, 5.12, 3.0, 0.24, "WHY IT MATTERS", size=7.8, color=EMERALD, bold=True)
    add_text(slide, 9.36, 5.4, 3.0, 0.8, "Campus-ready deployment without giving up generative explanations.", size=8.8, color=CHALK, line=1.12)
    return slide


# ---------------------------------------------------------------------------
# Slide 13 - Architecture
# ---------------------------------------------------------------------------
def slide_architecture(prs):
    slide = base_slide(
        prs,
        "Architecture",
        "Local-first, end to end.",
        13,
        "Repository layout: medha/studio, medha/lesson, medha/rag, medha/ingest, medha/render, medha/tts, medha/library.",
    )
    layers = [
        ("EXPERIENCE", "PySide6 Studio  •  OpenGL board  •  checkpoints  •  library", EMERALD),
        ("ORCHESTRATION", "Lesson generator  •  timeline  •  translator  •  evaluation", GOLD),
        ("MODELS", "Qwen3 LLM  •  BGE-M3  •  BGE reranker  •  Kokoro  •  Docling  •  SmolVLM", EMERALD),
        ("DATA", "Lesson JSON  •  Chroma vectors  •  SQLite index  •  caches", GOLD),
        ("RUNTIME", "Ollama (GPU)  •  ONNX / torch (CPU)  •  OpenGL 3.3", EMERALD),
    ]
    for index, (name, body, accent) in enumerate(layers):
        y = 1.9 + index * 0.88
        rect(slide, 0.7, y, 8.25, 0.76, PANEL, line=BORDER, radius=0.04)
        rect(slide, 0.7, y, 0.06, 0.76, accent)
        add_text(slide, 0.94, y + 0.12, 1.65, 0.22, name, size=7.6, color=accent, bold=True)
        add_text(slide, 2.55, y + 0.12, 6.15, 0.5, body, size=8.8, color=CHALK, line=1.05)

    rect(slide, 9.2, 1.9, 3.43, 4.4, PANEL, line=BORDER, radius=0.04)
    add_text(slide, 9.42, 2.04, 2.95, 0.22, "WHY LOCAL-FIRST", size=8.0, color=GOLD, bold=True)
    items = [
        ("No network dependency", "Runs on a campus laptop or LAN server."),
        ("Model-swappable", "Swap the LLM without touching the renderer."),
        ("Graceful fallbacks", "No reranker → vector search; no TTS → silent timing."),
        ("Private by default", "Lecture notes never leave the institution."),
    ]
    for index, (title, body) in enumerate(items):
        y = 2.42 + index * 0.9
        add_text(slide, 9.42, y, 2.95, 0.24, title, size=9.2, color=CHALK, bold=True)
        add_text(slide, 9.42, y + 0.28, 2.95, 0.5, body, size=8.2, color=MUTED, line=1.08)
    return slide


# ---------------------------------------------------------------------------
# Slide 14 - Model stack
# ---------------------------------------------------------------------------
def slide_models(prs):
    slide = base_slide(
        prs,
        "Model stack",
        "Small, specialized, license-clean models.",
        14,
        "Source: MODELS.md and models.lock.json. GPU only for the LLM; every helper runs on CPU.",
    )
    cards = [
        ("BRAIN", "Qwen3-4B-Instruct", "Default LLM. Phi-4-mini and Llama 3.2 fallbacks.", "Apache-2.0 / MIT / Llama community"),
        ("RETRIEVAL", "BGE-M3 + reranker", "ONNX 1024-dim embeddings + cross-encoder top-5.", "MIT / Apache-2.0"),
        ("SPEECH", "Kokoro-82M", "24 kHz English TTS, sentence-level cache.", "Apache-2.0"),
        ("DOCUMENTS", "Docling Heron + TableFormer", "Layout detection and table structure on CPU.", "Apache-2.0 / CDLA"),
        ("VISION", "SmolVLM-500M", "Figure and diagram captions for teaching material.", "Apache-2.0"),
        ("TRANSLATION", "IndicTrans2 200M", "English → Kannada / Hindi; Indic Parler voice.", "MIT / Apache-2.0 (gated)"),
    ]
    for index, (role, model_name, body, license_text) in enumerate(cards):
        row, col = divmod(index, 3)
        x = 0.7 + col * 4.05
        y = 1.9 + row * 2.15
        rect(slide, x, y, 3.85, 1.98, PANEL, line=BORDER, radius=0.05)
        add_text(slide, x + 0.2, y + 0.16, 3.4, 0.2, role, size=7.6, color=EMERALD, bold=True)
        add_text(slide, x + 0.2, y + 0.42, 3.45, 0.28, model_name, size=12.2, color=CHALK, bold=True)
        add_text(slide, x + 0.2, y + 0.78, 3.45, 0.55, body, size=8.4, color=MUTED, line=1.08)
        add_text(slide, x + 0.2, y + 1.55, 3.45, 0.22, license_text, size=7.2, color=GOLD)

    rect(slide, 0.7, 6.25, 11.95, 0.48, GOLD_SOFT, line=GOLD, line_w=0.75, radius=0.2)
    add_text(
        slide,
        0.95,
        6.34,
        11.4,
        0.3,
        "Pinned revisions + license sidecars  •  no scraped weights  •  no non-commercial models in the core demo",
        size=9.2,
        color=GOLD,
        bold=True,
    )
    return slide


# ---------------------------------------------------------------------------
# Slide 15 - Performance
# ---------------------------------------------------------------------------
def slide_performance(prs):
    slide = base_slide(
        prs,
        "Engineering",
        "Targets, not marketing numbers.",
        15,
        "Targets and guardrails from config.py; hardware profile is the reference 4–8 GB RAM laptop.",
    )
    metrics = [
        ("60 FPS", "render target", "Vector chalk strokes on reference hardware."),
        ("±150 ms", "audio-visual sync", "Audio clock is the master; the board follows."),
        ("4–8 GB", "local RAM", "4-bit LLM on GPU; all helpers on CPU."),
    ]
    for index, (value, name, body) in enumerate(metrics):
        x = 0.7 + index * 4.05
        rect(slide, x, 1.9, 3.85, 1.55, PANEL, line=BORDER, radius=0.05)
        add_text(slide, x + 0.22, 2.02, 3.4, 0.5, value, size=28, color=EMERALD, bold=True)
        add_text(slide, x + 0.22, 2.55, 3.4, 0.22, name, size=8.2, color=GOLD, bold=True)
        add_text(slide, x + 0.22, 2.82, 3.4, 0.4, body, size=8.5, color=MUTED, line=1.05)

    rect(slide, 0.7, 3.7, 11.95, 2.55, PANEL, line=BORDER, radius=0.04)
    add_text(slide, 0.95, 3.84, 8.0, 0.22, "ENGINEERING GUARDRAILS", size=8.2, color=EMERALD, bold=True)
    guardrails = [
        ("Schema-constrained JSON", "Ollama grammar + repair pass; invalid actions are dropped, not rendered."),
        ("Deterministic chalk", "Seeded wobble and stable screenshots; no random flicker between frames."),
        ("Graceful degradation", "Missing reranker, TTS, or translation never blocks the lesson."),
        ("Cached everything", "Per-sentence WAVs, ingest chunks, image captions, and lesson JSON."),
    ]
    for index, (title, body) in enumerate(guardrails):
        row, col = divmod(index, 2)
        x = 0.95 + col * 6.0
        y = 4.2 + row * 0.92
        rect(slide, x, y + 0.05, 0.075, 0.075, EMERALD)
        add_text(slide, x + 0.2, y, 5.5, 0.24, title, size=9.8, color=CHALK, bold=True)
        add_text(slide, x + 0.2, y + 0.27, 5.5, 0.5, body, size=8.4, color=MUTED, line=1.08)

    add_text(slide, 0.7, 6.45, 11.9, 0.26, "The target is not a benchmark score. It is a lecture a student can follow, replay, and understand.", size=9.0, color=GOLD, bold=True, align=PP_ALIGN.CENTER)
    return slide


# ---------------------------------------------------------------------------
# Slide 16 - USPs
# ---------------------------------------------------------------------------
def slide_usps(prs):
    slide = base_slide(
        prs,
        "Differentiators",
        "Five reasons a department says yes.",
        16,
        "Mapped to the product capabilities described in README.md and the board-action specification.",
    )
    tiles = [
        ("01", "Live board", "Dynamic derivation construction at 60 FPS target — not flat static slides."),
        ("02", "Professor's bridge", "Grounded in the professor's own syllabus; doubt analytics show where students stall."),
        ("03", "Offline campus install", "₹0 cloud inference per student; runs locally on 4–8 GB RAM hardware."),
        ("04", "Regional voice", "Kannada and Hindi voice today; Telugu language pack on the roadmap."),
        ("05", "Grounded RAG", "Answers cite college notes, not the open web; LaTeX is protected through translation."),
    ]
    positions = [
        (0.7, 1.9, 3.85), (4.74, 1.9, 3.85), (8.78, 1.9, 3.85),
        (0.7, 4.12, 5.82), (6.82, 4.12, 5.82),
    ]
    for (number, title, body), (x, y, width) in zip(tiles, positions, strict=True):
        rect(slide, x, y, width, 1.95, PANEL, line=BORDER, radius=0.05)
        add_text(slide, x + 0.22, y + 0.18, 0.6, 0.28, number, size=9.0, color=EMERALD, bold=True)
        add_text(slide, x + 0.22, y + 0.5, width - 0.44, 0.28, title, size=13.5, color=CHALK, bold=True)
        add_text(slide, x + 0.22, y + 0.86, width - 0.44, 0.85, body, size=9.0, color=MUTED, line=1.12)

    add_text(slide, 0.7, 6.35, 11.9, 0.3, "Each USP maps to something the demo can show — not a future promise.", size=9.2, color=GOLD, bold=True, align=PP_ALIGN.CENTER)
    return slide


# ---------------------------------------------------------------------------
# Slide 17 - Business model
# ---------------------------------------------------------------------------
def slide_business(prs):
    slide = base_slide(
        prs,
        "Business model",
        "College-first revenue, self-funded expansion.",
        17,
        "Pricing is a proposed commercial model for pilot validation, not a published price list.",
    )
    rect(slide, 0.7, 1.9, 6.2, 4.55, PANEL, line=BORDER, radius=0.04)
    add_text(slide, 0.95, 2.05, 5.6, 0.22, "PHASE 1  •  B2B COLLEGE REVENUE", size=8.2, color=EMERALD, bold=True)
    revenue = [
        ("Department license", "₹50,000 – ₹1,50,000 / year", 1.0, "offline install, updates, ingestion"),
        ("Teacher insights dashboard", "₹10,000 – ₹30,000 / year", 0.2, "doubt analytics and cohort gaps"),
        ("Regional language pack", "₹10,000 – ₹30,000 / year", 0.2, "per language, per department"),
    ]
    for index, (name, price, fraction, detail) in enumerate(revenue):
        y = 2.45 + index * 1.12
        add_text(slide, 0.95, y, 4.0, 0.24, name, size=9.8, color=CHALK, bold=True)
        add_text(slide, 5.0, y, 1.65, 0.24, price, size=7.8, color=GOLD, align=PP_ALIGN.RIGHT)
        rect(slide, 0.95, y + 0.3, 5.4, 0.14, RGBColor(0x1E, 0x29, 0x3B), radius=0.45)
        rect(slide, 0.95, y + 0.3, 5.4 * (0.25 + 0.75 * fraction), 0.14, EMERALD if index == 0 else EMERALD_DARK, radius=0.45)
        add_text(slide, 0.95, y + 0.49, 5.4, 0.2, detail, size=7.8, color=MUTED)

    add_text(slide, 0.95, 5.88, 5.6, 0.24, "Land with one department. Expand across affiliated colleges.", size=9.0, color=EMERALD, bold=True)

    rect(slide, 7.12, 1.9, 5.5, 4.55, PANEL, line=BORDER, radius=0.04)
    add_text(slide, 7.36, 2.05, 4.9, 0.22, "PHASE 2  •  SCHOOL EXPANSION", size=8.2, color=GOLD, bold=True)
    add_text(slide, 7.36, 2.38, 4.9, 0.55, "₹199 – ₹499", size=30, color=CHALK, bold=True)
    add_text(slide, 7.36, 2.95, 4.9, 0.24, "per student / month  •  parent subscription", size=9.0, color=MUTED)
    line(slide, 7.36, 3.32, 12.35, 3.32, BORDER, 0.75)
    add_text(slide, 7.36, 3.46, 4.9, 1.35, "Self-funded by Phase 1 college profits. Hosted B2C tutoring launches only after B2B revenue covers GPU server scaling.", size=9.2, color=CHALK, line=1.16)
    chip(slide, 7.36, 5.08, 1.55, 0.34, "No VC needed", size=9.0)
    chip(slide, 9.05, 5.08, 1.75, 0.34, "Campus-first", size=9.0)
    add_text(slide, 7.36, 5.58, 4.9, 0.5, "The B2B wedge funds the B2C platform instead of subsidizing it.", size=8.4, color=MUTED, italic=True)

    add_text(slide, 0.7, 6.58, 11.9, 0.24, "Revenue is tied to departments, not per-token inference — the economics improve as adoption grows.", size=8.8, color=GOLD, bold=True, align=PP_ALIGN.CENTER)
    return slide


# ---------------------------------------------------------------------------
# Slide 18 - Unit economics
# ---------------------------------------------------------------------------
def slide_unit_economics(prs):
    slide = base_slide(
        prs,
        "Unit economics",
        "Why the numbers work.",
        18,
        "Illustrative assumptions: 240 students per department; ₹1,00,000 annual license; $20/seat/month cloud comparison; $1 ≈ ₹83. Validate in pilot.",
    )
    rect(slide, 0.7, 1.9, 5.65, 4.55, EMERALD_SOFT, line=EMERALD, line_w=0.9, radius=0.04)
    add_text(slide, 0.95, 2.05, 5.0, 0.22, "MEDHA  •  ILLUSTRATIVE DEPARTMENT", size=8.2, color=EMERALD, bold=True)
    add_text(slide, 0.95, 2.38, 5.0, 0.5, "₹417", size=31, color=CHALK, bold=True)
    add_text(slide, 0.95, 2.9, 5.0, 0.24, "per student / year", size=9.2, color=MUTED)
    add_text(slide, 0.95, 3.2, 5.0, 0.5, "≈ ₹35 per student / month", size=10.2, color=GOLD, bold=True)
    line(slide, 0.95, 3.7, 6.1, 3.7, BORDER, 0.75)
    rows = [
        ("Department size", "240 students"),
        ("Annual license", "₹1,00,000"),
        ("Cloud inference per student", "₹0"),
        ("Marginal cost of one more rewatch", "≈ ₹0"),
    ]
    for index, (name, value) in enumerate(rows):
        y = 3.9 + index * 0.52
        add_text(slide, 0.95, y, 3.4, 0.24, name, size=8.8, color=MUTED)
        add_text(slide, 4.4, y, 1.7, 0.24, value, size=8.8, color=CHALK, bold=True, align=PP_ALIGN.RIGHT)

    rect(slide, 6.65, 1.9, 5.98, 4.55, PANEL, line=BORDER, radius=0.04)
    add_text(slide, 6.9, 2.05, 5.4, 0.22, "CLOUD CHATBOT  •  SAME 240 STUDENTS", size=8.2, color=GOLD, bold=True)
    add_text(slide, 6.9, 2.38, 5.0, 0.5, "₹3.98 L", size=31, color=GOLD, bold=True)
    add_text(slide, 6.9, 2.9, 5.0, 0.24, "per month  •  $20/seat × 240", size=9.2, color=MUTED)
    add_text(slide, 6.9, 3.2, 5.0, 0.5, "≈ ₹47.8 L per year", size=10.2, color=CHALK, bold=True)
    line(slide, 6.9, 3.7, 12.4, 3.7, BORDER, 0.75)
    add_text(slide, 6.9, 3.9, 5.4, 0.3, "≈ 48× the department license", size=16, color=GOLD, bold=True)
    add_text(slide, 6.9, 4.35, 5.4, 1.0, "The comparison is illustrative and not feature-equivalent, but it shows why campuses prefer a fixed local license over per-seat cloud billing.", size=8.4, color=MUTED, line=1.14)
    chip(slide, 6.9, 5.55, 1.9, 0.36, "Fixed cost", size=8.8)
    chip(slide, 9.0, 5.55, 2.0, 0.36, "Unlimited rewatches", size=8.8)

    add_text(slide, 0.7, 6.58, 11.9, 0.24, "One department covers support; every additional department is mostly margin.", size=9.0, color=EMERALD, bold=True, align=PP_ALIGN.CENTER)
    return slide


# ---------------------------------------------------------------------------
# Slide 19 - Roadmap
# ---------------------------------------------------------------------------
def slide_roadmap(prs):
    slide = base_slide(
        prs,
        "Roadmap",
        "From one semester to a university network.",
        19,
        "Execution plan proposed for a 24-month horizon; pilots define the actual timeline.",
    )
    line(slide, 1.0, 2.62, 12.3, 2.62, BORDER, 2.0)
    phases = [
        ("01", "Semester 1", "Free pilot in 2–3 engineering colleges", "One department per campus; measure prep hours and repeat doubts."),
        ("02", "Semester 2", "Turn pilots into case studies", "Publish pass-rate and doubt-resolution deltas; add Telugu pack."),
        ("03", "Year 1", "Department licensing across affiliates", "Target VTU / JNTU affiliate networks; add teacher dashboard."),
        ("04", "Year 2", "Hosted B2C school tutoring", "Launch only when B2B revenue covers GPU server scaling."),
    ]
    for index, (number, phase, title, body) in enumerate(phases):
        x = 0.7 + index * 3.02
        circle(slide, x + 1.22, 2.38, 0.48, EMERALD_SOFT, line=EMERALD, line_w=1.2)
        add_text(slide, x + 1.22, 2.46, 0.48, 0.24, number, size=9.0, color=EMERALD, bold=True, align=PP_ALIGN.CENTER)
        rect(slide, x, 3.02, 2.84, 2.85, PANEL, line=BORDER, radius=0.05)
        add_text(slide, x + 0.18, 3.16, 2.5, 0.22, phase.upper(), size=7.8, color=GOLD, bold=True)
        add_text(slide, x + 0.18, 3.45, 2.5, 0.55, title, size=10.5, color=CHALK, bold=True, line=1.05)
        add_text(slide, x + 0.18, 4.12, 2.5, 1.3, body, size=8.4, color=MUTED, line=1.12)
        if index == 1:
            chip(slide, x + 0.18, 5.2, 1.45, 0.28, "Telugu pack", size=7.2)
        if index < len(phases) - 1:
            line(slide, x + 2.86, 2.62, x + 3.02, 2.62, EMERALD, 1.5)

    add_text(slide, 0.7, 6.35, 11.9, 0.3, "Land narrow. Prove learning outcomes. Expand by affiliation, not by ad spend.", size=9.5, color=GOLD, bold=True, align=PP_ALIGN.CENTER)
    return slide


# ---------------------------------------------------------------------------
# Slide 20 - Team
# ---------------------------------------------------------------------------
def slide_team(prs):
    slide = base_slide(
        prs,
        "Team",
        "Team Kanon.",
        20,
        "Roles as provided by the team; no contact details included.",
    )
    members = [
        ("PN", "Pranav N", "Team Lead", "Backend & Tech Analysis", "Owns the core engine, data flow, and technical feasibility."),
        ("DR", "Disha R", "Creative Works", "UI/UX", "Owns the Studio experience, visual system, and demo polish."),
        ("S", "Soyal", "Market Analyst", "Market & Competitors", "Owns sizing, competitor teardown, and pricing logic."),
        ("K", "Kruthika", "New Member", "Product & Research", "Adds fresh perspective across research and rollout."),
    ]
    for index, (initials, name, role, focus, body) in enumerate(members):
        x = 0.7 + index * 3.02
        rect(slide, x, 1.9, 2.84, 4.1, PANEL, line=BORDER, radius=0.05)
        circle(slide, x + 0.22, 2.1, 0.68, EMERALD_SOFT, line=EMERALD, line_w=1.0)
        add_text(slide, x + 0.22, 2.24, 0.68, 0.3, initials, size=14, color=EMERALD, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, x + 0.22, 2.92, 2.4, 0.28, name, size=13.2, color=CHALK, bold=True)
        add_text(slide, x + 0.22, 3.25, 2.4, 0.22, role, size=8.2, color=GOLD, bold=True)
        add_text(slide, x + 0.22, 3.52, 2.4, 0.24, focus, size=8.0, color=EMERALD)
        line(slide, x + 0.22, 3.86, x + 2.6, 3.86, BORDER, 0.75)
        add_text(slide, x + 0.22, 3.98, 2.4, 1.7, body, size=8.6, color=MUTED, line=1.14)

    rect(slide, 0.7, 6.18, 11.95, 0.56, EMERALD_SOFT, line=EMERALD_DARK, radius=0.2)
    add_text(
        slide,
        0.95,
        6.28,
        11.4,
        0.32,
        "Backend depth  •  UI/UX craft  •  market rigor  •  fresh research perspective",
        size=10.2,
        color=EMERALD,
        bold=True,
        align=PP_ALIGN.CENTER,
    )
    return slide


# ---------------------------------------------------------------------------
# Slide 21 - Government support
# ---------------------------------------------------------------------------
def slide_government(prs):
    slide = base_slide(
        prs,
        "Policy tailwinds",
        "Government support already exists.",
        21,
        "Scheme names and headline benefits as publicly described; eligibility and amounts subject to approval.",
    )
    schemes = [
        ("DPIIT STARTUP INDIA", "100% tax exemption", "For 3 years under Section 80-IAC, plus an 80% patent rebate.", "Recognition"),
        ("MSME CGTMSE", "₹2–5 Crore", "Collateral-free debt funding for expansion and working capital.", "Credit"),
        ("INNOVATION GRANTS", "₹10–50 Lakh", "MeitY SAMRIDH and DST-SEED grants for EdTech accessibility.", "Grant"),
    ]
    for index, (name, value, body, tag) in enumerate(schemes):
        x = 0.7 + index * 4.05
        rect(slide, x, 1.9, 3.85, 3.55, PANEL, line=BORDER, radius=0.05)
        add_text(slide, x + 0.22, 2.05, 3.4, 0.22, name, size=7.8, color=EMERALD, bold=True)
        add_text(slide, x + 0.22, 2.36, 3.4, 0.62, value, size=21, color=CHALK, bold=True)
        add_text(slide, x + 0.22, 3.02, 3.4, 1.3, body, size=9.0, color=MUTED, line=1.14)
        chip(slide, x + 0.22, 4.8, 1.05, 0.3, tag, size=7.6)

    rect(slide, 0.7, 5.72, 11.95, 0.78, GOLD_SOFT, line=GOLD, line_w=0.75, radius=0.05)
    add_text(slide, 0.95, 5.84, 11.4, 0.3, "Aligns with NEP 2020, UDISE+ digital infrastructure, and regional-language mandates.", size=11.2, color=GOLD, bold=True)
    add_text(slide, 0.95, 6.14, 11.4, 0.24, "The pitch is not asking for a new ecosystem. It plugs into one that already has budget and policy cover.", size=8.6, color=MUTED)
    return slide


# ---------------------------------------------------------------------------
# Slide 22 - Risks
# ---------------------------------------------------------------------------
def slide_risks(prs):
    slide = base_slide(
        prs,
        "Risks",
        "What could go wrong — and how we de-risk it.",
        22,
        "Mitigations reflect the current implementation; remaining risks are validated in pilot.",
    )
    headers = [("RISK", 0.7, 3.85, GOLD), ("MITIGATION", 4.65, 7.98, EMERALD)]
    for header, x, width, color in headers:
        rect(slide, x, 1.84, width, 0.44, PANEL_2, line=BORDER, radius=0.03)
        add_text(slide, x + 0.14, 1.92, width - 0.28, 0.3, header, size=8.2, color=color, bold=True)

    risks = [
        ("Model hallucination", "Schema-constrained JSON, repair pass, grounded RAG, and source excerpts. No invented citations."),
        ("Hardware constraints", "4-bit LLM, CPU-only helpers, 3 GB VRAM target, and a CPU-only profile."),
        ("Language quality", "Math-protected translation, English fallback, human review, and a phased Telugu pack."),
        ("Adoption friction", "Free semester pilot, professor-in-the-loop workflow, and LMS-friendly lesson export."),
        ("Content licensing", "Professor-owned material, license-clean model stack, and no scraped content in the core demo."),
    ]
    for index, (risk, mitigation) in enumerate(risks):
        y = 2.38 + index * 0.85
        rect(slide, 0.7, y, 3.85, 0.78, RED_SOFT, line=RGBColor(0x7F, 0x1D, 0x1D), radius=0.03)
        add_text(slide, 0.86, y + 0.14, 3.55, 0.5, risk, size=9.6, color=CHALK, bold=True, line=1.05)
        rect(slide, 4.65, y, 7.98, 0.78, PANEL, line=BORDER, radius=0.03)
        add_text(slide, 4.83, y + 0.12, 7.65, 0.58, mitigation, size=8.6, color=MUTED, line=1.08)

    add_text(slide, 0.7, 6.68, 11.9, 0.24, "The biggest risk is not model quality. It is whether a department will change its lecture workflow.", size=8.8, color=GOLD, bold=True, align=PP_ALIGN.CENTER)
    return slide


# ---------------------------------------------------------------------------
# Slide 23 - Conclusion
# ---------------------------------------------------------------------------
def slide_conclusion(prs):
    slide = base_slide(
        prs,
        "Conclusion",
        "Extending the professor's reach.",
        23,
        "Prepared for institutional department pilots and university partnerships.",
    )
    rect(slide, 0.7, 1.88, 11.95, 1.45, EMERALD_SOFT, line=EMERALD, line_w=0.9, radius=0.05)
    add_text(
        slide,
        0.98,
        2.04,
        11.4,
        0.4,
        "Bridge college instruction and student doubt resolution — without the cloud.",
        size=17.5,
        color=CHALK,
        bold=True,
    )
    add_text(slide, 0.98, 2.52, 11.4, 0.3, "A local AI blackboard that preserves the professor's reasoning, not just the final answer.", size=9.6, color=MUTED)

    summary = [
        ("01", "Solves derivation loss", "Live vector build-up survives after the lecture ends, replayable step by step."),
        ("02", "Zero cloud inference", "One department license replaces per-seat cloud billing; rewatches cost ≈ ₹0."),
        ("03", "Self-funded expansion", "College B2B profits fund the future B2C school platform."),
    ]
    for index, (number, title, body) in enumerate(summary):
        x = 0.7 + index * 4.05
        rect(slide, x, 3.62, 3.85, 1.95, PANEL, line=BORDER, radius=0.05)
        add_text(slide, x + 0.22, 3.76, 0.6, 0.24, number, size=8.6, color=EMERALD, bold=True)
        add_text(slide, x + 0.22, 4.05, 3.4, 0.3, title, size=12.0, color=CHALK, bold=True)
        add_text(slide, x + 0.22, 4.42, 3.4, 0.95, body, size=8.8, color=MUTED, line=1.12)

    rect(slide, 0.7, 5.88, 11.95, 0.58, GOLD_SOFT, line=GOLD, line_w=0.75, radius=0.2)
    add_text(
        slide,
        0.95,
        5.98,
        11.4,
        0.34,
        "Prepared for institutional department pilots & university partnerships.",
        size=11.8,
        color=GOLD,
        bold=True,
        align=PP_ALIGN.CENTER,
    )
    add_text(slide, 0.7, 6.65, 11.9, 0.24, "Team Kanon", size=9.0, color=EMERALD, bold=True, align=PP_ALIGN.CENTER)
    return slide


# ---------------------------------------------------------------------------
# Slide 24 - Appendix
# ---------------------------------------------------------------------------
def slide_appendix(prs):
    slide = base_slide(
        prs,
        "Appendix",
        "Sources & assumptions.",
        24,
        "Citations are listed by source name and date. No contact details or social links are included anywhere in this deck.",
    )
    left_sources = [
        ("UDISE+ 2025–26", "Ministry of Education / PIB summary (PRID=2300408)"),
        ("UDISE+ 2025–26", "NIEPA Analysis Table 2.5"),
        ("ITU 2024", "Facts and Figures, 27 Nov 2024"),
        ("Mordor Intelligence", "AI in Education Report 2025–2030"),
        ("IAMAI–Grant Thornton", "India EdTech Report, Jan 2025"),
    ]
    right_sources = [
        ("Grand View Research", "AI in Education forecast, 2030"),
        ("MarketsandMarkets", "AI in Education forecast, Oct 2026"),
        ("Khanmigo", "Public pricing page, Oct 2026"),
        ("Learning Equality", "Kolibri / UNDP Digital X Catalogue"),
        ("DIKSHA", "Ministry of Education public portal"),
    ]
    for column, sources in enumerate((left_sources, right_sources)):
        x = 0.7 + column * 6.12
        add_text(slide, x, 1.9, 5.6, 0.24, "SOURCES" if column == 0 else "SOURCES (CONTINUED)", size=8.2, color=EMERALD, bold=True)
        for index, (name, detail) in enumerate(sources):
            y = 2.24 + index * 0.72
            rect(slide, x, y + 0.08, 0.075, 0.075, GOLD if column else EMERALD)
            add_text(slide, x + 0.2, y, 5.3, 0.24, name, size=8.8, color=CHALK, bold=True)
            add_text(slide, x + 0.2, y + 0.25, 5.3, 0.3, detail, size=7.8, color=MUTED)

    rect(slide, 0.7, 5.85, 11.95, 0.95, PANEL, line=BORDER, radius=0.04)
    add_text(slide, 0.95, 5.96, 11.4, 0.22, "KEY ASSUMPTIONS", size=8.0, color=GOLD, bold=True)
    add_text(
        slide,
        0.95,
        6.2,
        11.4,
        0.5,
        "240 students per department  •  ₹1,00,000 annual license  •  $20/seat/month cloud comparison  •  $1 ≈ ₹83  •  pilot metrics to be validated.",
        size=8.6,
        color=MUTED,
    )
    return slide


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def main() -> int:
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)

    slide_cover(prs)
    slide_snapshot(prs)
    slide_problem(prs)
    slide_infrastructure(prs)
    slide_market(prs)
    slide_personas(prs)
    slide_solution(prs)
    slide_semantic(prs)
    slide_storyboard(prs)
    slide_competitors_overview(prs)
    slide_matrix(prs)
    slide_positioning(prs)
    slide_architecture(prs)
    slide_models(prs)
    slide_performance(prs)
    slide_usps(prs)
    slide_business(prs)
    slide_unit_economics(prs)
    slide_roadmap(prs)
    slide_team(prs)
    slide_government(prs)
    slide_risks(prs)
    slide_conclusion(prs)
    slide_appendix(prs)

    prs.save(str(OUT))
    print(f"wrote {OUT} ({len(prs.slides)} slides)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
