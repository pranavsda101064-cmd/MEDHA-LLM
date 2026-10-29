"""Offline BGE reranker for the final retrieval shortlist."""

from __future__ import annotations

import gc
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

import config

from .errors import RagError


class Reranker(Protocol):
    name: str

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]: ...


class BgeReranker:
    name = "bge-reranker-v2-m3"

    def __init__(
        self,
        *,
        model_dir: Path | None = None,
        batch_size: int | None = None,
        max_length: int | None = None,
        num_threads: int | None = None,
    ) -> None:
        self.model_dir = Path(model_dir or config.RERANKER_DIR)
        self.batch_size = max(1, batch_size or config.RERANK_BATCH_SIZE)
        self.max_length = max_length or config.RERANK_MAX_LENGTH
        self.num_threads = max(1, num_threads or config.RERANK_NUM_THREADS)
        self._model: Any = None
        self._tokenizer: Any = None
        self._torch: Any = None

    def _check_files(self) -> None:
        required = (
            self.model_dir / "config.json",
            self.model_dir / "model.safetensors",
            self.model_dir / "tokenizer.json",
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise RagError(
                "BGE reranker files missing: "
                + ", ".join(missing)
                + ". Run: python tools/fetch_models.py --profile core"
            )

    def _load(self) -> tuple[Any, Any, Any]:
        if self._model is not None:
            return self._torch, self._tokenizer, self._model
        self._check_files()
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RagError(
                "reranker dependencies are missing; install requirements/cpu.txt "
                "and requirements/rag.txt"
            ) from exc

        torch.set_num_threads(self.num_threads)
        tokenizer = AutoTokenizer.from_pretrained(
            str(self.model_dir),
            local_files_only=True,
            use_fast=True,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            str(self.model_dir),
            local_files_only=True,
            dtype=torch.float32,
            low_cpu_mem_usage=True,
        )
        model.eval()
        model.to("cpu")
        self._torch = torch
        self._tokenizer = tokenizer
        self._model = model
        return torch, tokenizer, model

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        if not texts:
            return []
        if not query.strip():
            raise RagError("cannot rerank an empty query")
        torch, tokenizer, model = self._load()
        scores: list[float] = []
        for start in range(0, len(texts), self.batch_size):
            batch_texts = list(texts[start : start + self.batch_size])
            pairs = [[query, text] for text in batch_texts]
            encoded = tokenizer(
                pairs,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            with torch.inference_mode():
                logits = model(**encoded).logits
                batch_scores = torch.sigmoid(logits.reshape(-1))
            scores.extend(float(value) for value in batch_scores.cpu().tolist())
        return scores

    def close(self) -> None:
        self._model = None
        self._tokenizer = None
        self._torch = None
        gc.collect()
