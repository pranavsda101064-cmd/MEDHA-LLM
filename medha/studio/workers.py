"""Qt worker wrappers for generated and opened lessons."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

import config

from .service import StudioOptions, generate_lesson, open_lesson

logger = logging.getLogger(__name__)


class _Worker(QObject):
    status = Signal(str)
    partial = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    @Slot()
    def run(self) -> None:
        try:
            self._run()
        except Exception as exc:
            logger.exception("Studio worker failed: %s", exc)
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def _run(self) -> None:
        raise NotImplementedError


class GenerateWorker(_Worker):
    def __init__(self, options: StudioOptions) -> None:
        super().__init__()
        self.options = options

    def _run(self) -> None:
        self.finished.emit(
            generate_lesson(self.options, self.status.emit, self.partial.emit)
        )


class OpenWorker(_Worker):
    def __init__(self, path: Path, options: StudioOptions) -> None:
        super().__init__()
        self.path = path
        self.options = options

    def _run(self) -> None:
        self.finished.emit(
            open_lesson(
                self.path,
                self.options,
                self.status.emit,
                self.partial.emit,
            )
        )


class VoiceTestWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, voice: str, speed: float) -> None:
        super().__init__()
        self.voice = voice
        self.speed = speed

    @Slot()
    def run(self) -> None:
        try:
            from medha.tts.audio import AudioPlayer
            from medha.tts.kokoro import KokoroEngine

            engine = KokoroEngine(voice=self.voice, speed=self.speed)
            samples = engine.synthesize("Medha narration is ready.")
            player = AudioPlayer(samples, config.TTS_SAMPLE_RATE, enabled=True)
            if not player.start():
                raise RuntimeError(player.last_error or "audio output unavailable")
            time.sleep(min(4.0, len(samples) / config.TTS_SAMPLE_RATE))
            player.stop()
        except Exception as exc:
            logger.exception("Voice test failed")
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.finished.emit(f"Voice test played with {engine.voice}")
