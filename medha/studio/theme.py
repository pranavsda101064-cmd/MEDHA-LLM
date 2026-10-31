"""Modern dark design system for Medha Studio: tokens, stylesheet, application."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

import config

BG = "#0b0f14"
SURFACE = "#11161d"
ELEVATED = "#161c24"
BORDER = "#232b36"
BORDER_HOVER = "#334052"
TEXT = "#e6eaf0"
MUTED = "#8a94a6"
PLACEHOLDER = "#5b6577"
ACCENT = "#355e3b"
ACCENT_HOVER = "#3f7049"
ACCENT_PRESS = "#2a4a30"
ACCENT_LINE = "#5a9a68"
SUCCESS = "#3dd68c"
WARN = "#f5b942"
DANGER = "#f06a6a"
SLATE_PAPER = "#1a212b"
SLATE_PAPER_DARK = "#151b24"
PIN_TEAL = "#4fc7c1"
WOOD_EDGE = "#3a2f24"
CORK = "#b8875b"
PAPER = "#f5e6c8"
PAPER_HOVER = "#e8d5b0"
ACTIVE_GREEN = "#355e3b"
INK = "#30251d"
PIN_BRASS = "#c49a45"

STYLE = """
QWidget {
    color: #e6eaf0;
    font-size: 13px;
}
QMainWindow, QDialog, QMessageBox {
    background: #0b0f14;
}
QLabel {
    background: transparent;
}
QLabel#brand {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: 5px;
}
QLabel#subtitle {
    color: #8a94a6;
    font-size: 12px;
    letter-spacing: 2px;
}
QLabel#fieldLabel {
    color: #8a94a6;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.6px;
}
QLabel#sectionTitle {
    color: #8a94a6;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.6px;
}
QLabel#meta, QLabel#quality {
    color: #8a94a6;
    font-size: 12px;
}
QLabel#hint {
    color: #f5b942;
    font-size: 12px;
}
QLabel#stats {
    color: #5b6577;
    font-size: 11px;
}
QLabel#timeLabel {
    font-family: Consolas, "Cascadia Mono", monospace;
    color: #8a94a6;
    font-size: 12px;
}
QLabel#titlePill {
    background: rgba(17, 22, 29, 230);
    border: 1px solid #232b36;
    border-radius: 15px;
    padding: 7px 16px;
    color: #e6eaf0;
    font-size: 12px;
    font-weight: 600;
}
QLabel#statusPill {
    background: rgba(17, 22, 29, 235);
    border: 1px solid #334052;
    border-radius: 17px;
    padding: 10px 22px;
    color: #8a94a6;
    font-size: 13px;
}
QFrame#panel {
    background: #11161d;
    border: 1px solid #232b36;
    border-radius: 16px;
}
QFrame#noticeHeader {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1c232f, stop:1 #161d27);
    border: 1px solid #2a3342;
    border-top: 4px solid #f5b942;
    border-radius: 10px;
}
QFrame#card {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a212b, stop:1 #151b24);
    border: 1px solid #2a3342;
    border-radius: 10px;
}
QFrame#pinAmber {
    background: qradialgradient(
        cx:0.35, cy:0.3, radius:0.75,
        stop:0 #fff3cf, stop:0.4 #f5b942, stop:1 #a87410
    );
    border: 1px solid #0b0f14;
    border-radius: 7px;
    min-width: 13px;
    max-width: 13px;
    min-height: 13px;
    max-height: 13px;
}
QFrame#pinIndigo {
    background: qradialgradient(
        cx:0.35, cy:0.3, radius:0.75,
        stop:0 #d3d3ff, stop:0.4 #6c6ce5, stop:1 #3d3da0
    );
    border: 1px solid #0b0f14;
    border-radius: 7px;
    min-width: 13px;
    max-width: 13px;
    min-height: 13px;
    max-height: 13px;
}
QFrame#pinTeal {
    background: qradialgradient(
        cx:0.35, cy:0.3, radius:0.75,
        stop:0 #c9fffb, stop:0.4 #4fc7c1, stop:1 #237e7a
    );
    border: 1px solid #0b0f14;
    border-radius: 7px;
    min-width: 13px;
    max-width: 13px;
    min-height: 13px;
    max-height: 13px;
}
QWidget#lessonSurface {
    background-color: #0e1a12;
    background-image: __CHALKBOARD__;
}
QWidget#lessonSurface QLabel#sectionTitle {
    color: #f5f5e6;
    font-family: "__HANDWRITING__";
    font-size: 13px;
    font-weight: normal;
    letter-spacing: 0px;
}
QWidget#lessonSurface QLabel#fieldLabel {
    color: #c9d4c9;
    font-family: "__HANDWRITING__";
    font-size: 12px;
    font-weight: normal;
    letter-spacing: 0px;
}
QWidget#lessonSurface QCheckBox {
    color: #e8f0e8;
    font-family: "__HANDWRITING__";
    font-size: 12px;
}
QWidget#lessonSurface QLabel#meta,
QWidget#lessonSurface QLabel#quality {
    color: #aebfb0;
    font-family: "__HANDWRITING__";
    font-size: 12px;
    letter-spacing: 0px;
}
QWidget#lessonSurface QLabel#hint {
    color: #ffffb8;
    font-family: "__HANDWRITING__";
    font-size: 12px;
    letter-spacing: 0px;
}
QFrame#transportBar {
    background: rgba(13, 17, 23, 235);
    border: 1px solid #232b36;
    border-radius: 18px;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget, QPlainTextEdit {
    background: #161c24;
    border: 1px solid #232b36;
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: #355e3b;
    selection-color: #ffffff;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #334052;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #5a9a68;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    color: #4c5666;
    background: #11161d;
    border-color: #1a212b;
}
QListWidget {
    outline: none;
}
QListWidget::item {
    padding: 8px 10px;
    border-radius: 8px;
    margin: 2px 4px;
    color: #c9d2de;
}
QListWidget::item:hover {
    background: #1a212b;
}
QListWidget::item:selected {
    background: rgba(53, 94, 59, 0.35);
    color: #e6eaf0;
    border: 1px solid #5a9a68;
}
QPlainTextEdit {
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 12px;
}
QComboBox QAbstractItemView {
    background: #161c24;
    border: 1px solid #334052;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: #355e3b;
    selection-color: #ffffff;
    outline: none;
}
QComboBox::drop-down {
    border: 0;
    width: 26px;
}
QPushButton {
    background: #161c24;
    border: 1px solid #232b36;
    border-radius: 8px;
    padding: 8px 14px;
    color: #e6eaf0;
}
QPushButton:hover {
    background: #1c2430;
    border-color: #334052;
}
QPushButton:pressed {
    background: #11161d;
}
QPushButton:disabled {
    color: #4c5666;
    border-color: #1a212b;
    background: #11161d;
}
QPushButton#primary {
    background: #355e3b;
    border: 1px solid #5a9a68;
    color: #f5e6c8;
    font-weight: 700;
    padding: 10px 16px;
}
QPushButton#primary:hover {
    background: #3f7049;
}
QPushButton#primary:pressed {
    background: #2a4a30;
}
QPushButton#primary:disabled {
    background: #232b36;
    border-color: #232b36;
    color: #4c5666;
}
QPushButton#ghost {
    background: transparent;
}
QPushButton#ghost:hover {
    background: #161c24;
}
QPushButton#bigPlay {
    background: #355e3b;
    border: 2px solid #5a9a68;
    border-radius: 31px;
    color: #f5e6c8;
    font-size: 24px;
    font-weight: 700;
    min-width: 62px;
    max-width: 62px;
    min-height: 62px;
    max-height: 62px;
}
QPushButton#bigPlay:hover {
    background: #3f7049;
}
QPushButton#bigPlay:pressed {
    background: #2a4a30;
}
QPushButton#bigPlay:disabled {
    background: #161c24;
    border-color: #232b36;
    color: #4c5666;
}
QPushButton#skip {
    background: #161c24;
    border: 1px solid #334052;
    border-radius: 22px;
    color: #e6eaf0;
    font-size: 12px;
    font-weight: 700;
    min-width: 44px;
    max-width: 44px;
    min-height: 44px;
    max-height: 44px;
    padding: 0px;
}
QPushButton#skip:hover {
    background: #1c2430;
    border-color: #5a9a68;
}
QPushButton#skip:disabled {
    background: #11161d;
    border-color: #1a212b;
    color: #4c5666;
}
QPushButton#hamburger {
    background-color: transparent;
    background-image: __HAMBURGER__;
    border: none;
    border-radius: 0px;
    color: #30251d;
    font-size: 16px;
    min-width: 44px;
    max-width: 44px;
    min-height: 44px;
    max-height: 44px;
    padding: 0px;
}
QPushButton#hamburger:hover {
    background-image: __HAMBURGER_HOVER__;
}
QCheckBox {
    spacing: 8px;
    background: transparent;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #334052;
    background: #161c24;
}
QCheckBox::indicator:hover {
    border-color: #5a9a68;
}
QCheckBox::indicator:checked {
    background: #355e3b;
    border: 1px solid #5a9a68;
}
QCheckBox::indicator:disabled {
    background: #11161d;
    border-color: #1a212b;
}
QCheckBox:disabled {
    color: #4c5666;
}
QSlider::groove:horizontal {
    background: #232b36;
    height: 4px;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #355e3b;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #e6eaf0;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #5a9a68;
}
QSlider:disabled::groove:horizontal {
    background: #1a212b;
}
QSlider:disabled::handle:horizontal {
    background: #2a3442;
}
QTabWidget::pane {
    border: 0;
    background: transparent;
    top: -1px;
}
QTabBar {
    background-color: #b8875b;
    background-image: __CORK__;
    min-height: 58px;
}
QTabBar::tab {
    background-color: transparent;
    background-image: __PAPER__;
    border: 1px solid transparent;
    min-width: 110px;
    max-width: 110px;
    min-height: 46px;
    max-height: 46px;
    margin: 6px 3px 6px 4px;
    padding: 0px;
    color: #30251d;
    font-family: "__HANDWRITING__";
    font-size: 15px;
    text-align: center;
}
QTabBar::tab:hover {
    background-image: __PAPER_HOVER__;
}
QTabBar::tab:selected {
    background-image: __PAPER_ACTIVE__;
    color: #f5e6c8;
}
QTabBar::tab:selected:hover {
    background-image: __PAPER_ACTIVE__;
    color: #f5e6c8;
}
QTabBar::tab:focus {
    border: 1px dashed #30251d;
}
QTabBar::tab:disabled {
    background-image: __PAPER__;
    color: #8a7f70;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #2a3442;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #3a4658;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    width: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #2a3442;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #3a4658;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    height: 0px;
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
QStatusBar {
    background: #11161d;
    border-top: 1px solid #232b36;
    color: #8a94a6;
    font-size: 12px;
}
QStatusBar::item {
    border: 0px;
}
QToolTip {
    background: #161c24;
    color: #e6eaf0;
    border: 1px solid #334052;
    padding: 5px 8px;
}
"""


def _asset(name: str) -> str:
    """Absolute url() for a generated menu texture (relative urls break under -m)."""
    return f"url('{(config.ROOT / 'assets' / 'ui' / name).as_posix()}')"


def _handwriting_family() -> str:
    """Load the bundled note-label font, falling back to system handwriting faces."""
    database = QFontDatabase()
    path = config.ROOT / "assets" / "fonts" / "GochiHand-Regular.ttf"
    if path.is_file():
        font_id = database.addApplicationFont(str(path))
        if font_id >= 0:
            families = database.applicationFontFamilies(font_id)
            if families:
                return families[0]
    for candidate in ("Ink Free", "Segoe Print", "Comic Sans MS", "Segoe UI"):
        if candidate in database.families():
            return candidate
    return "Segoe UI"


def apply_theme(app: QApplication) -> None:
    """Install the Medha dark theme on the application."""
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(ELEVATED))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(DANGER))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(ELEVATED))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(PLACEHOLDER))
    app.setPalette(palette)
    font = QFont("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)
    replacements = {
        "__CORK__": _asset("cork.png"),
        "__PAPER__": _asset("paper.png"),
        "__PAPER_HOVER__": _asset("paper_hover.png"),
        "__PAPER_ACTIVE__": _asset("paper_active.png"),
        "__HAMBURGER__": _asset("hamburger.png"),
        "__HAMBURGER_HOVER__": _asset("hamburger_hover.png"),
        "__CHALKBOARD__": _asset("chalkboard.png"),
        "__HANDWRITING__": _handwriting_family(),
    }
    style = STYLE
    for token, value in replacements.items():
        style = style.replace(token, value)
    app.setStyleSheet(style)
