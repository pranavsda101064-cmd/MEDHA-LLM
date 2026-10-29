"""Qt/OpenGL window for the board."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeyEvent, QSurfaceFormat
from PySide6.QtOpenGL import QOpenGLWindow
from PySide6.QtWidgets import QApplication

import config

from .geometry import Transform
from .gl import GLRenderer
from .scene import Board

SceneFactory = Callable[[Board], None]
FrameFactory = Callable[[Board, float], None]


class BoardWindow(QOpenGLWindow):
    def __init__(
        self,
        scene_factory: SceneFactory | None = None,
        frame_factory: FrameFactory | None = None,
    ) -> None:
        super().__init__()
        self.setTitle(config.APP_NAME)
        self.resize(config.BOARD_WIDTH, config.BOARD_HEIGHT)
        self._scene_factory = scene_factory
        self._frame_factory = frame_factory
        self._renderer = GLRenderer()
        self._board = Board()
        self._started_at = time.perf_counter()

    def initializeGL(self) -> None:
        self._renderer.initialize()
        self._board = Board()
        self._started_at = time.perf_counter()
        if self._scene_factory is not None:
            self._scene_factory(self._board)

    def resizeGL(self, width: int, height: int) -> None:
        self._renderer.resize(width, height)

    def paintGL(self) -> None:
        elapsed = time.perf_counter() - self._started_at
        if self._frame_factory is not None:
            self._frame_factory(self._board, elapsed)
        self._renderer.draw_background(elapsed)
        transform = Transform(max(1, self.width()), max(1, self.height()))
        self._renderer.draw_mesh(self._board.build(transform))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_F11:
            if self.windowState() == Qt.WindowState.WindowFullScreen:
                self.showNormal()
            else:
                self.showFullScreen()
        else:
            super().keyPressEvent(event)


def run(
    scene_factory: SceneFactory | None = None,
    frame_factory: FrameFactory | None = None,
    duration_ms: int | None = None,
    screenshot_path: Path | None = None,
    screenshot_delay_ms: int = 700,
    animate: bool = False,
    on_start: Callable[[], None] | None = None,
    on_stop: Callable[[], None] | None = None,
) -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL, True)
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setSamples(4)
    fmt.setSwapInterval(1)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication.instance() or QApplication([])
    window = BoardWindow(scene_factory, frame_factory)
    window.show()
    timer: QTimer | None = None
    if animate:
        timer = QTimer(window)
        timer.timeout.connect(window.update)
        timer.start(16)
    if on_start is not None:
        QTimer.singleShot(0, on_start)
    if screenshot_path is not None:

        def capture() -> None:
            image = window.grabFramebuffer()
            if not image.isNull():
                image.save(str(screenshot_path))

        QTimer.singleShot(screenshot_delay_ms, capture)
    if duration_ms is not None:
        QTimer.singleShot(duration_ms, app.quit)
    try:
        code = app.exec()
    finally:
        if timer is not None:
            timer.stop()
        if on_stop is not None:
            on_stop()
    return code
