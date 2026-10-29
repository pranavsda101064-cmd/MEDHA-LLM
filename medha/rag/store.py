"""Persistent Chroma collection for cited teaching chunks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import config
from medha.ingest.models import IngestResult

from .errors import RagError
from .models import CollectionStats, IndexReport


@dataclass(frozen=True)
class StoreHit:
    chunk_id: str
    doc_id: str
    text: str
    citation: str
    source: str
    page_start: int | None
    page_end: int | None
    heading_path: tuple[str, ...]
    token_count: int
    vector_score: float


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any, default: str = "") -> str:
    return default if value is None else str(value)


class ChromaStore:
    def __init__(
        self,
        *,
        path: Path | None = None,
        collection_name: str | None = None,
        client: Any = None,
        embedding_model: str | None = None,
        embedding_dim: int | None = None,
    ) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise RagError(
                "chromadb is not installed; install requirements/rag.txt"
            ) from exc

        self.path = Path(path or config.CHROMA_DIR)
        self.collection_name = collection_name or config.CHROMA_COLLECTION
        self.embedding_model = embedding_model or config.EMBED_MODEL_ID
        self.embedding_dim = embedding_dim or config.EMBED_DIM
        if client is None:
            from chromadb.config import Settings

            self.path.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(
                path=str(self.path),
                settings=Settings(anonymized_telemetry=config.CHROMA_TELEMETRY),
            )
        self.client = client
        self.collection = self._open_collection()

    def _metadata(self) -> dict[str, str | int]:
        return {
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim,
            "schema_version": config.RAG_SCHEMA_VERSION,
        }

    def _open_collection(self) -> Any:
        expected = self._metadata()
        metadata: dict[str, Any] = {"hnsw:space": "cosine", **expected}
        collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=None,
            metadata=metadata,
        )
        existing = dict(collection.metadata or {})
        for key, value in expected.items():
            if existing.get(key) not in (None, value):
                raise RagError(
                    f"Chroma collection {self.collection_name!r} was built with "
                    f"{key}={existing.get(key)!r}, expected {value!r}. "
                    "Delete data/chroma or use a new collection."
                )
        if any(existing.get(key) != value for key, value in expected.items()):
            merged = {**existing, **expected}
            clean = {
                key: value
                for key, value in merged.items()
                if not key.startswith("hnsw:")
            }
            collection.modify(metadata=clean)
        return collection

    def count(self) -> int:
        return int(self.collection.count())

    def stats(self) -> CollectionStats:
        return CollectionStats(count=self.count(), collection=self.collection_name)

    def has_document(self, result: IngestResult) -> bool:
        current_ids = {chunk.chunk_id for chunk in result.chunks}
        if not current_ids:
            return False
        existing = self.collection.get(
            where={"doc_id": result.document.doc_id},
            include=[],
        )
        return set(existing.get("ids") or []) == current_ids

    def replace_document(
        self,
        result: IngestResult,
        embeddings: Sequence[Sequence[float]],
    ) -> IndexReport:
        if len(embeddings) != len(result.chunks):
            raise RagError(
                f"embedding count {len(embeddings)} does not match chunk count "
                f"{len(result.chunks)}"
            )
        for vector in embeddings:
            if len(vector) != self.embedding_dim:
                raise RagError(
                    f"embedding dimension {len(vector)} does not match {self.embedding_dim}"
                )

        doc_id = result.document.doc_id
        existing = self.collection.get(where={"doc_id": doc_id}, include=[])
        existing_ids = set(existing.get("ids") or [])
        current_ids = {chunk.chunk_id for chunk in result.chunks}
        stale = sorted(existing_ids - current_ids)

        if result.chunks:
            self.collection.upsert(
                ids=[chunk.chunk_id for chunk in result.chunks],
                embeddings=[list(vector) for vector in embeddings],
                documents=[chunk.text for chunk in result.chunks],
                metadatas=[
                    self._chunk_metadata(result, chunk) for chunk in result.chunks
                ],
            )
        if stale:
            self.collection.delete(ids=stale)

        return IndexReport(
            doc_id=doc_id,
            indexed=len(result.chunks),
            removed=len(stale),
            collection_count=self.count(),
        )

    def _chunk_metadata(self, result: IngestResult, chunk: Any) -> dict[str, str | int]:
        metadata: dict[str, str | int] = {
            "doc_id": result.document.doc_id,
            "chunk_id": chunk.chunk_id,
            "citation": chunk.citation,
            "source": result.document.source.filename,
            "format": result.document.source.format,
            "locator_kind": chunk.locator_kind,
            "ordinal": chunk.ordinal,
            "token_count": chunk.token_count,
        }
        if chunk.page_start is not None:
            metadata["page_start"] = chunk.page_start
        if chunk.page_end is not None:
            metadata["page_end"] = chunk.page_end
        if chunk.heading_path:
            metadata["heading_path"] = " > ".join(chunk.heading_path)
        return metadata

    def query(self, vector: Sequence[float], *, n_results: int | None = None) -> list[StoreHit]:
        if len(vector) != self.embedding_dim:
            raise RagError(
                f"query embedding dimension {len(vector)} does not match "
                f"{self.embedding_dim}"
            )
        count = self.count()
        if count == 0:
            return []
        requested = max(1, n_results or config.RERANK_CANDIDATES)
        raw = self.collection.query(
            query_embeddings=[list(vector)],
            n_results=min(requested, count),
            include=["documents", "metadatas", "distances"],
        )
        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        hits: list[StoreHit] = []
        for index, chunk_id in enumerate(ids):
            meta: Mapping[str, Any] = (
                metadatas[index] if index < len(metadatas) and metadatas[index] else {}
            )
            distance = (
                float(distances[index])
                if index < len(distances) and distances[index] is not None
                else 1.0
            )
            heading = _as_str(meta.get("heading_path"))
            hits.append(
                StoreHit(
                    chunk_id=str(chunk_id),
                    doc_id=_as_str(meta.get("doc_id")),
                    text=_as_str(documents[index] if index < len(documents) else ""),
                    citation=_as_str(meta.get("citation")),
                    source=_as_str(meta.get("source")),
                    page_start=_as_int(meta.get("page_start")),
                    page_end=_as_int(meta.get("page_end")),
                    heading_path=tuple(heading.split(" > ")) if heading else (),
                    token_count=_as_int(meta.get("token_count")) or 0,
                    vector_score=1.0 - distance,
                )
            )
        return hits

    def reset(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception as exc:
            raise RagError(f"could not reset collection: {exc}") from exc
        self.collection = self._open_collection()
