"""Launch the Medha Studio desktop application."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

import config
from medha.core.logging import setup_logging

from .app import StudioWindow

ROOT = Path(__file__).resolve().parents[2]
FALLBACK_LESSON = ROOT / "spec" / "board-action" / "v1" / "examples" / "newton.json"


def _configure_gl() -> None:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL, True)
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setSamples(4)
    fmt.setSwapInterval(1)
    QSurfaceFormat.setDefaultFormat(fmt)


def _smoke_lesson(path: Path | None) -> Path:
    if path is not None:
        return path
    generated = config.LESSON_CONTENT_DIR / "newton.json"
    return generated if generated.is_file() else FALLBACK_LESSON


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medha-studio", description=__doc__)
    parser.add_argument("--lesson", type=Path, default=None)
    parser.add_argument("--no-tts", action="store_true", help="start without speech")
    parser.add_argument("--smoke", action="store_true", help="load a lesson and exit")
    parser.add_argument("--screenshot", type=Path, default=None)
    parser.add_argument("--at", type=float, default=8.0, help="smoke screenshot time")
    args = parser.parse_args(argv)

    config.ensure_dirs()
    setup_logging()
    _configure_gl()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(f"{config.APP_NAME} Studio")
    app.setOrganizationName(config.APP_NAME)
    window = StudioWindow(tts=not args.no_tts)
    window.show()
    window.raise_()
    window.activateWindow()

    if args.lesson is not None:
        window.load_path(args.lesson, tts=not args.no_tts)
    elif args.smoke:
        window.load_path(_smoke_lesson(None), tts=False)

    if args.smoke:
        shot = args.screenshot.resolve() if args.screenshot is not None else None
        if shot is not None:
            shot.parent.mkdir(parents=True, exist_ok=True)

        def poll() -> None:
            if window.playback is None:
                QTimer.singleShot(200, poll)
                return
            window.seek_ms(round(args.at * 1000))
            if shot is not None:
                QTimer.singleShot(500, lambda: _grab(window, shot))
            else:
                QTimer.singleShot(500, app.quit)

        QTimer.singleShot(200, poll)
        QTimer.singleShot(15000, app.quit)

    return app.exec()


def _grab(window: StudioWindow, path: Path) -> None:
    window.grab().save(str(path))
    QApplication.quit()


if __name__ == "__main__":
    raise SystemExit(main())
