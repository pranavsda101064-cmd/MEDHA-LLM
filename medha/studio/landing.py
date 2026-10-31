"""Fullscreen landing page window: renders the built React landing before Studio."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeyEvent, QMouseEvent
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInfo, QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QLabel, QMainWindow, QStackedWidget

import config

logger = logging.getLogger(__name__)

ENTER_HOST = "medha.enter"
DIST_INDEX = Path(config.ROOT / "frontend" / "dist" / "index.html")
INDEX_URL = QUrl.fromLocalFile(str(DIST_INDEX))

FAILED_TEXT = (
    "The landing page could not be loaded.\n\n"
    "Press Enter or click anywhere to open Medha Studio."
)
ENTERING_TEXT = "Starting Medha Studio..."


class EnterInterceptor(QWebEngineUrlRequestInterceptor):
    """Belt-and-braces for the fake Enter host plus external subresource links."""

    entered = Signal()
    external = Signal(QUrl)

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        url = info.requestUrl()
        if url.host() == ENTER_HOST:
            info.block(True)
            self.entered.emit()
            return
        if url.scheme() in ("http", "https") and url.host() not in (
            "localhost",
            "127.0.0.1",
        ):
            info.block(True)
            self.external.emit(url)
            return
        info.block(False)


class _EnterLabel(QLabel):
    """Fallback panel: clicking it enters the studio."""

    pressed = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.pressed.emit()
        event.accept()


class _LandingView(QWebEngineView):
    """View that opens popup/target=_blank links in the system browser."""

    external = Signal(QUrl)

    def createWindow(self, _type: object) -> QWebEngineView:
        popup = QWebEngineView()
        popup.hide()
        popup.setParent(self)

        def forward(url: QUrl) -> None:
            self.external.emit(url)
            popup.deleteLater()

        popup.page().urlChanged.connect(forward)
        return popup


class LandingWindow(QMainWindow):
    """Frameless fullscreen window showing frontend/dist/index.html."""

    entered = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("QMainWindow { background: #000000; }")
        self._entering = False

        self._interceptor = EnterInterceptor()
        self._interceptor.entered.connect(self._begin_enter)
        self._interceptor.external.connect(self._open_external)

        self._view = _LandingView()
        self._view.page().profile().setUrlRequestInterceptor(self._interceptor)
        self._view.page().urlChanged.connect(self._on_url_changed)
        self._view.external.connect(self._open_external)

        self._fallback = _EnterLabel(FAILED_TEXT)
        self._fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fallback.setStyleSheet(
            "color: #f5f5e6; font-size: 16px; background: #000000;"
        )
        self._fallback.pressed.connect(self._begin_enter)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._view)
        self._stack.addWidget(self._fallback)
        self.setCentralWidget(self._stack)

        self._view.loadFinished.connect(self._on_load_finished)
        if DIST_INDEX.is_file():
            self._view.load(INDEX_URL)
        else:
            logger.error("landing build missing: %s", DIST_INDEX)
            self._on_load_finished(False)

    # --- navigation hooks -------------------------------------------------
    def _on_url_changed(self, url: QUrl) -> None:
        if url.host() == ENTER_HOST:
            self._begin_enter()
            return
        if url.scheme() in ("http", "https") and url.host() not in (
            "localhost",
            "127.0.0.1",
        ):
            QDesktopServices.openUrl(url)
            self._view.stop()
            self._view.load(INDEX_URL)

    def _on_load_finished(self, ok: bool) -> None:
        if not ok and not self._entering:
            self._stack.setCurrentWidget(self._fallback)

    # --- entering studio -------------------------------------------------
    def _begin_enter(self) -> None:
        if self._entering:
            return
        self._entering = True
        self._view.stop()
        self._fallback.setText(ENTERING_TEXT)
        self._stack.setCurrentWidget(self._fallback)
        self.entered.emit()

    def _open_external(self, url: QUrl) -> None:
        QDesktopServices.openUrl(url)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._begin_enter()
            event.accept()
            return
        super().keyPressEvent(event)
