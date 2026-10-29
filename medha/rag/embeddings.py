"""Offline BGE-M3 dense embeddings through ONNX Runtime on CPU."""

from __future__ import annotations

import gc
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

import config

from .errors import RagError


class Embedder(Protocol):
    name: str
    dimension: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class BgeM3Embedder:
    name = "bge-m3-onnx"
    dimension = config.EMBED_DIM

    def __init__(
        self,
        *,
        model_path: Path | None = None,
        tokenizer_path: Path | None = None,
        max_length: int | None = None,
        batch_size: int | None = None,
        num_threads: int | None = None,
    ) -> None:
        self.model_path = Path(model_path or config.EMBED_ONNX_PATH)
        self.tokenizer_path = Path(tokenizer_path or config.EMBED_TOKENIZER_PATH)
        self.max_length = max_length or config.EMBED_MAX_LENGTH
        self.batch_size = max(1, batch_size or config.EMBED_BATCH_SIZE)
        self.num_threads = max(1, num_threads or config.EMBED_NUM_THREADS)
        self._session: Any = None
        self._tokenizer: Any = None

    def _check_files(self) -> None:
        paths = (self.model_path, self.tokenizer_path)
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            raise RagError(
                "BGE-M3 ONNX files missing: "
                + ", ".join(missing)
                + ". Run: python tools/fetch_models.py --profile core"
            )

    def _load(self) -> tuple[Any, Any]:
        if self._session is not None:
            return self._session, self._tokenizer
        self._check_files()
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise RagError(
                "RAG dependencies are missing; install requirements/rag.txt"
            ) from exc

        tokenizer = Tokenizer.from_file(str(self.tokenizer_path))
        tokenizer.enable_truncation(max_length=self.max_length)
        pad_id = tokenizer.token_to_id("<pad>")
        tokenizer.enable_padding(pad_id=1 if pad_id is None else pad_id, pad_token="<pad>")

        options = ort.SessionOptions()
        options.intra_op_num_threads = self.num_threads
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        options.enable_cpu_mem_arena = False
        session = ort.InferenceSession(
            str(self.model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self._tokenizer = tokenizer
        self._session = session
        return session, tokenizer

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        clean = [text.strip() for text in texts]
        if any(not text for text in clean):
            raise RagError("cannot embed empty text")

        import numpy as np

        session, tokenizer = self._load()
        outputs = {output.name for output in session.get_outputs()}
        output_name = (
            "sentence_embedding" if "sentence_embedding" in outputs else "token_embeddings"
        )
        vectors: list[list[float]] = []
        for start in range(0, len(clean), self.batch_size):
            batch = clean[start : start + self.batch_size]
            encodings = tokenizer.encode_batch(batch, add_special_tokens=True)
            ids = np.asarray([encoding.ids for encoding in encodings], dtype=np.int64)
            mask = np.asarray(
                [encoding.attention_mask for encoding in encodings], dtype=np.int64
            )
            result = session.run(
                [output_name],
                {"input_ids": ids, "attention_mask": mask},
            )[0]
            matrix = np.asarray(result, dtype=np.float32)
            if matrix.ndim == 3:
                matrix = matrix[:, 0, :]
            if config.EMBED_NORMALIZE:
                norms = np.linalg.norm(matrix, axis=1, keepdims=True)
                matrix = matrix / np.clip(norms, 1e-12, None)
            vectors.extend(matrix.tolist())
        return vectors

    def close(self) -> None:
        self._session = None
        self._tokenizer = None
        gc.collect()
