"""Indexing and retrieval orchestration for lesson material."""

from __future__ import annotations

import gc
from pathlib import Path
from typing import Protocol

import config
from medha.ingest import IngestResult, ingest_file

from .embeddings import BgeM3Embedder, Embedder
from .errors import RagError, is_memory_error
from .models import CollectionStats, IndexReport, QueryResult, RetrievedChunk
from .reranker import BgeReranker, Reranker
from .store import ChromaStore, StoreHit


class ChunkStore(Protocol):
    def replace_document(
        self,
        result: IngestResult,
        embeddings: list[list[float]],
    ) -> IndexReport: ...

    def query(self, vector: list[float], *, n_results: int | None = None) -> list[StoreHit]: ...

    def count(self) -> int: ...

    def stats(self) -> CollectionStats: ...


class RagService:
    def __init__(
        self,
        *,
        embedder: Embedder | None = None,
        reranker: Reranker | None = None,
        store: ChunkStore | None = None,
        use_reranker: bool = True,
    ) -> None:
        self.embedder = embedder or BgeM3Embedder()
        if reranker is not None:
            self.reranker: Reranker | None = reranker
        elif use_reranker and config.RERANK_ENABLED:
            self.reranker = BgeReranker()
        else:
            self.reranker = None
        self.store = store or ChromaStore()

    def index_result(self, result: IngestResult) -> IndexReport:
        has_document = getattr(self.store, "has_document", None)
        if callable(has_document) and has_document(result):
            return IndexReport(
                doc_id=result.document.doc_id,
                indexed=0,
                removed=0,
                collection_count=self.store.count(),
            )
        texts = [chunk.text for chunk in result.chunks]
        embeddings = self.embedder.embed(texts)
        return self.store.replace_document(result, embeddings)

    def index_file(
        self,
        path: Path,
        *,
        ocr: bool | None = None,
        use_cache: bool = True,
    ) -> IndexReport:
        result = ingest_file(path, ocr=ocr, use_cache=use_cache)
        gc.collect()
        return self.index_result(result)

    def query(
        self,
        text: str,
        *,
        top_k: int | None = None,
        candidates: int | None = None,
        rerank: bool = True,
    ) -> QueryResult:
        if not text.strip():
            raise RagError("query text is empty")
        limit = top_k or config.RAG_TOP_K
        candidate_count = candidates or config.RERANK_CANDIDATES
        if limit <= 0:
            raise RagError("top_k must be positive")
        if candidate_count < limit:
            raise RagError("candidates must be at least top_k")

        index_count = self.store.count()
        if index_count == 0:
            return QueryResult(
                query=text,
                hits=[],
                candidate_count=0,
                reranked=False,
                embedder=self.embedder.name,
                reranker=self.reranker.name if self.reranker is not None else None,
            )

        vector = self.embedder.embed([text])[0]
        hits = self.store.query(vector, n_results=candidate_count)
        if not hits:
            return QueryResult(
                query=text,
                hits=[],
                candidate_count=0,
                reranked=False,
                embedder=self.embedder.name,
                reranker=self.reranker.name if self.reranker is not None else None,
            )

        reranked = bool(
            rerank
            and self.reranker is not None
            and index_count >= config.RERANK_MIN_CHUNKS
        )
        rerank_scores: list[float] | None = None
        if reranked and self.reranker is not None:
            try:
                rerank_scores = self.reranker.rerank(
                    text, [hit.text for hit in hits]
                )
            except Exception as exc:
                if not is_memory_error(exc):
                    raise
                reranked = False
                rerank_scores = None
                close = getattr(self.reranker, "close", None)
                if callable(close):
                    close()
                gc.collect()
            if rerank_scores is not None and len(rerank_scores) != len(hits):
                raise RagError(
                    f"reranker returned {len(rerank_scores)} scores for {len(hits)} hits"
                )

        scores: list[float | None]
        if rerank_scores is None:
            scores = [None] * len(hits)
        else:
            scores = [float(score) for score in rerank_scores]
        ranked = list(zip(hits, scores, strict=True))
        ranked.sort(
            key=lambda item: (
                item[1] if item[1] is not None else item[0].vector_score,
                item[0].vector_score,
            ),
            reverse=True,
        )
        results = [
            RetrievedChunk(
                chunk_id=hit.chunk_id,
                doc_id=hit.doc_id,
                text=hit.text,
                citation=hit.citation,
                source=hit.source,
                page_start=hit.page_start,
                page_end=hit.page_end,
                heading_path=list(hit.heading_path),
                token_count=hit.token_count,
                vector_score=hit.vector_score,
                rerank_score=score,
                score=score if score is not None else hit.vector_score,
            )
            for hit, score in ranked[:limit]
        ]
        return QueryResult(
            query=text,
            hits=results,
            candidate_count=len(hits),
            reranked=reranked,
            embedder=self.embedder.name,
            reranker=self.reranker.name if self.reranker is not None else None,
        )

    def stats(self) -> CollectionStats:
        return self.store.stats()

    def close(self) -> None:
        for component in (self.embedder, self.reranker):
            close = getattr(component, "close", None)
            if callable(close):
                close()
        gc.collect()

    def reset(self) -> None:
        store = self.store
        if not isinstance(store, ChromaStore):
            raise RagError("injected stores cannot be reset")
        store.reset()
