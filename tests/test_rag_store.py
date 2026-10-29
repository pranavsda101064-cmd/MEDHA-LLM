from __future__ import annotations

from typing import Any

import pytest

from medha.ingest.models import (
    Chunk,
    ChunkingInfo,
    IngestDocument,
    IngestResult,
    ParserInfo,
    SourceInfo,
)
from medha.rag import ChromaStore, RagError

pytest.importorskip("chromadb")


def make_result(include_first: bool = True, include_second: bool = True) -> IngestResult:
    doc_id = "a" * 64
    source = SourceInfo(
        path="C:/docs/sample.pdf",
        filename="sample.pdf",
        sha256=doc_id,
        format="pdf",
        bytes=100,
    )
    specs = [
        ("c0000", 0, "Force equals mass times acceleration.", 1, "sample.pdf, page 1"),
        ("c0001", 1, "A worked example uses ten newtons.", 2, "sample.pdf, page 2"),
    ]
    chunks = []
    for chunk_id, ordinal, text, page, citation in specs:
        if (ordinal == 0 and not include_first) or (ordinal == 1 and not include_second):
            continue
        chunks.append(
            Chunk(
                chunk_id=f"{doc_id[:12]}-{chunk_id}",
                doc_id=doc_id,
                ordinal=ordinal,
                text=text,
                token_count=7,
                block_ids=[f"{doc_id[:12]}-b{ordinal:04d}"],
                page_start=page,
                page_end=page,
                locator_kind="page",
                heading_path=["Newton"],
                citation=citation,
            )
        )
    document = IngestDocument(
        schema_version="1.0.0",
        doc_id=doc_id,
        source=source,
        parser=ParserInfo(version="test", schema_version="1.0.0"),
        title="Newton",
        page_count=2,
        locator_kind="page",
        blocks=[],
    )
    return IngestResult(
        document=document,
        chunks=chunks,
        chunking=ChunkingInfo(tokenizer="test", max_tokens=450, overlap=64),
    )


@pytest.fixture
def store() -> Any:
    import chromadb

    client = chromadb.EphemeralClient()
    return ChromaStore(
        client=client,
        collection_name="medha_test_store",
        embedding_model="test",
        embedding_dim=4,
    )


def test_replace_document_and_query(store: Any) -> None:
    result = make_result()
    report = store.replace_document(result, [[1, 0, 0, 0], [0, 1, 0, 0]])
    assert report.indexed == 2
    assert report.removed == 0
    assert report.collection_count == 2
    assert store.count() == 2

    hits = store.query([1, 0, 0, 0], n_results=2)
    assert len(hits) == 2
    assert hits[0].citation == "sample.pdf, page 1"
    assert hits[0].vector_score == pytest.approx(1.0)
    assert hits[0].heading_path == ("Newton",)


def test_has_document_matches_existing_chunks(store: Any) -> None:
    store.reset()
    result = make_result()
    assert not store.has_document(result)
    store.replace_document(result, [[1, 0, 0, 0], [0, 1, 0, 0]])
    assert store.has_document(result)
    changed = make_result(include_second=False)
    assert not store.has_document(changed)


def test_stale_chunks_are_removed(store: Any) -> None:
    store.replace_document(make_result(), [[1, 0, 0, 0], [0, 1, 0, 0]])
    report = store.replace_document(make_result(include_first=False), [[0, 1, 0, 0]])
    assert report.indexed == 1
    assert report.removed == 1
    assert report.collection_count == 1
    hits = store.query([0, 1, 0, 0], n_results=5)
    assert [hit.chunk_id for hit in hits] == ["aaaaaaaaaaaa-c0001"]


def test_reset_and_stats(store: Any) -> None:
    store.replace_document(make_result(), [[1, 0, 0, 0], [0, 1, 0, 0]])
    assert store.stats().count == 2
    store.reset()
    assert store.count() == 0


def test_dimension_mismatch_is_rejected(store: Any) -> None:
    result = make_result()
    with pytest.raises(RagError):
        store.replace_document(result, [[1, 0, 0]])
    with pytest.raises(RagError):
        store.query([1, 0, 0])


def test_empty_collection_returns_no_hits(store: Any) -> None:
    assert store.query([1, 0, 0, 0]) == []
