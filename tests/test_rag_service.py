from __future__ import annotations

from collections.abc import Sequence

import pytest

from medha.ingest.models import (
    Chunk,
    ChunkingInfo,
    IngestDocument,
    IngestResult,
    ParserInfo,
    SourceInfo,
)
from medha.rag import RagError, RagService
from medha.rag.models import CollectionStats, IndexReport
from medha.rag.store import StoreHit


class FakeEmbedder:
    name = "fake-embed"
    dimension = 4

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


class FakeReranker:
    name = "fake-rerank"

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        self.calls.append((query, list(texts)))
        return [0.9 if "good" in text else 0.1 for text in texts]


class OomReranker:
    name = "oom-rerank"

    def __init__(self) -> None:
        self.closed = 0

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        raise OSError(22, "The paging file is too small for this operation")

    def close(self) -> None:
        self.closed += 1


class FakeStore:
    def __init__(
        self,
        hits: list[StoreHit],
        *,
        has_document: bool = False,
        count: int | None = None,
    ) -> None:
        self.hits = hits
        self.has_document_value = has_document
        self.count_value = count if count is not None else (100 if hits else 0)
        self.replaced: list[tuple[IngestResult, list[list[float]]]] = []
        self.queries: list[tuple[list[float], int | None]] = []

    def has_document(self, _result: IngestResult) -> bool:
        return self.has_document_value

    def replace_document(
        self, result: IngestResult, embeddings: list[list[float]]
    ) -> IndexReport:
        self.replaced.append((result, embeddings))
        return IndexReport(
            doc_id=result.document.doc_id,
            indexed=len(result.chunks),
            removed=0,
            collection_count=len(result.chunks),
        )

    def query(self, vector: list[float], *, n_results: int | None = None) -> list[StoreHit]:
        self.queries.append((vector, n_results))
        return self.hits[: n_results or len(self.hits)]

    def count(self) -> int:
        return self.count_value

    def stats(self) -> CollectionStats:
        return CollectionStats(count=len(self.hits), collection="fake")


def make_hit(chunk_id: str, text: str, score: float) -> StoreHit:
    return StoreHit(
        chunk_id=chunk_id,
        doc_id="a" * 64,
        text=text,
        citation=f"sample.pdf, page 1 ({chunk_id})",
        source="sample.pdf",
        page_start=1,
        page_end=1,
        heading_path=("Newton",),
        token_count=9,
        vector_score=score,
    )


def make_result() -> IngestResult:
    doc_id = "a" * 64
    source = SourceInfo(
        path="C:/docs/sample.pdf",
        filename="sample.pdf",
        sha256=doc_id,
        format="pdf",
        bytes=100,
    )
    chunks = [
        Chunk(
            chunk_id=f"{doc_id[:12]}-c0000",
            doc_id=doc_id,
            ordinal=0,
            text="good force text",
            token_count=3,
            block_ids=["b0"],
            page_start=1,
            page_end=1,
            locator_kind="page",
            citation="sample.pdf, page 1",
        ),
        Chunk(
            chunk_id=f"{doc_id[:12]}-c0001",
            doc_id=doc_id,
            ordinal=1,
            text="unrelated text",
            token_count=2,
            block_ids=["b1"],
            page_start=2,
            page_end=2,
            locator_kind="page",
            citation="sample.pdf, page 2",
        ),
    ]
    document = IngestDocument(
        schema_version="1.0.0",
        doc_id=doc_id,
        source=source,
        parser=ParserInfo(version="test", schema_version="1.0.0"),
        title="Sample",
        page_count=2,
        locator_kind="page",
        blocks=[],
    )
    return IngestResult(
        document=document,
        chunks=chunks,
        chunking=ChunkingInfo(tokenizer="test", max_tokens=450, overlap=64),
    )


def test_index_result_embeds_all_chunks() -> None:
    embedder = FakeEmbedder()
    store = FakeStore([])
    service = RagService(embedder=embedder, reranker=FakeReranker(), store=store)
    report = service.index_result(make_result())
    assert report.indexed == 2
    assert embedder.calls == [["good force text", "unrelated text"]]
    assert len(store.replaced[0][1]) == 2


def test_index_result_skips_already_indexed_document() -> None:
    embedder = FakeEmbedder()
    store = FakeStore([], has_document=True)
    service = RagService(embedder=embedder, reranker=FakeReranker(), store=store)
    report = service.index_result(make_result())
    assert report.indexed == 0
    assert embedder.calls == []
    assert store.replaced == []


def test_query_reranks_and_limits() -> None:
    hits = [
        make_hit("a-c0", "unrelated text", 0.8),
        make_hit("a-c1", "good force text", 0.2),
    ]
    embedder = FakeEmbedder()
    reranker = FakeReranker()
    service = RagService(embedder=embedder, reranker=reranker, store=FakeStore(hits))
    result = service.query("force", top_k=1, candidates=2)
    assert result.reranked
    assert result.reranker == "fake-rerank"
    assert result.candidate_count == 2
    assert [hit.chunk_id for hit in result.hits] == ["a-c1"]
    assert result.hits[0].score == pytest.approx(0.9)
    assert reranker.calls == [("force", ["unrelated text", "good force text"])]


def test_query_skips_reranker_for_small_index() -> None:
    hits = [
        make_hit("a-c0", "unrelated text", 0.8),
        make_hit("a-c1", "good force text", 0.2),
    ]
    reranker = FakeReranker()
    service = RagService(
        embedder=FakeEmbedder(),
        reranker=reranker,
        store=FakeStore(hits, count=2),
    )
    result = service.query("force", top_k=2, candidates=2)
    assert not result.reranked
    assert reranker.calls == []


def test_query_can_skip_reranker() -> None:
    hits = [
        make_hit("a-c0", "unrelated text", 0.8),
        make_hit("a-c1", "good force text", 0.2),
    ]
    embedder = FakeEmbedder()
    reranker = FakeReranker()
    service = RagService(embedder=embedder, reranker=reranker, store=FakeStore(hits))
    result = service.query("force", top_k=2, candidates=2, rerank=False)
    assert not result.reranked
    assert [hit.chunk_id for hit in result.hits] == ["a-c0", "a-c1"]
    assert all(hit.rerank_score is None for hit in result.hits)
    assert reranker.calls == []


def test_query_falls_back_when_reranker_runs_out_of_memory() -> None:
    hits = [
        make_hit("a-c0", "unrelated text", 0.8),
        make_hit("a-c1", "good force text", 0.2),
    ]
    reranker = OomReranker()
    service = RagService(
        embedder=FakeEmbedder(),
        reranker=reranker,
        store=FakeStore(hits),
    )
    result = service.query("force", top_k=2, candidates=2)
    assert not result.reranked
    assert [hit.chunk_id for hit in result.hits] == ["a-c0", "a-c1"]
    assert all(hit.rerank_score is None for hit in result.hits)
    assert reranker.closed == 1


def test_query_without_hits() -> None:
    service = RagService(
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        store=FakeStore([]),
    )
    result = service.query("nothing")
    assert result.hits == []
    assert result.candidate_count == 0
    assert not result.reranked


def test_invalid_query_limits() -> None:
    service = RagService(
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        store=FakeStore([]),
    )
    with pytest.raises(RagError):
        service.query("force", top_k=5, candidates=2)
    with pytest.raises(RagError):
        service.query("   ")
