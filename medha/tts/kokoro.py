"""Offline Kokoro-82M speech synthesis on CPU."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

import config

logger = logging.getLogger(__name__)


class KokoroEngine:
    """Lazy local loader for Kokoro weights, voice pack, and G2P pipeline."""

    engine_id = "kokoro"

    def __init__(
        self,
        model_dir: Path | None = None,
        voice: str = config.KOKORO_VOICE,
        speed: float = config.KOKORO_SPEED,
    ) -> None:
        self.model_dir = Path(model_dir) if model_dir is not None else config.KOKORO_MODEL_DIR
        self.voice = voice
        self.speed = speed
        self._model: Any = None
        self._pipeline: Any = None
        self._voice_pack: Any = None

    def _require_file(self, path: Path) -> Path:
        if not path.is_file():
            raise FileNotFoundError(f"Kokoro asset missing: {path}")
        return path

    @property
    def loaded(self) -> bool:
        return self._pipeline is not None

    def warmup(self) -> None:
        """Load weights and G2P resources without synthesizing speech."""
        self._load()
        logger.info("Kokoro warmup complete (voice=%s, speed=%.2f)", self.voice, self.speed)

    def _load(self) -> None:
        if self._pipeline is not None:
            return
        try:
            import torch
            from kokoro import KModel, KPipeline
        except ImportError as exc:
            raise RuntimeError(
                "Kokoro dependencies are missing; install requirements/tts.txt and cpu.txt"
            ) from exc

        try:
            import spacy.util

            if not spacy.util.is_package("en_core_web_sm"):
                raise RuntimeError(
                    "misaki English G2P needs en-core-web-sm. Install it once while "
                    "online, then the runtime is fully offline."
                )
        except ImportError as exc:
            raise RuntimeError("spaCy is required for Kokoro English G2P") from exc

        config_path = self._require_file(self.model_dir / "config.json")
        weights_path = self._require_file(self.model_dir / "kokoro-v1_0.pth")
        voice_path = self._require_file(self.model_dir / "voices" / f"{self.voice}.pt")
        logger.info("Loading Kokoro-82M from %s", self.model_dir)
        model = (
            KModel(
                repo_id=config.KOKORO_REPO_ID,
                config=str(config_path),
                model=str(weights_path),
            )
            .to(config.KOKORO_DEVICE)
            .eval()
        )
        self._pipeline = KPipeline(
            lang_code=config.KOKORO_LANG_CODE,
            repo_id=config.KOKORO_REPO_ID,
            model=model,
            device=config.KOKORO_DEVICE,
        )
        self._model = model
        self._voice_pack = torch.load(voice_path, map_location="cpu", weights_only=True)
        if not callable(self._pipeline):
            raise RuntimeError("Kokoro pipeline did not initialize")

    def synthesize(self, text: str) -> np.ndarray:
        text = text.strip()
        if not text:
            raise ValueError("cannot synthesize empty text")
        self._load()
        assert self._pipeline is not None
        assert self._voice_pack is not None
        chunks: list[np.ndarray] = []
        for result in self._pipeline(text, voice=self._voice_pack, speed=self.speed):
            audio = result.audio
            if audio is None:
                continue
            chunks.append(audio.detach().cpu().numpy().reshape(-1).astype(np.float32))
        if not chunks:
            raise RuntimeError(f"Kokoro produced no audio for: {text!r}")
        return np.concatenate(chunks).astype(np.float32)
