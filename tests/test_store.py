"""Tests for LanceDB store + manifest + local embeddings integration (Phase 0a).

Uses mocks for embeddings so tests run without Ollama.
"""

import os
import tempfile
import pytest
from pathlib import Path
from datetime import datetime
from typing import List

from second_brain.store import (
    add_document,
    get_manifest_status,
    search,
    get_data_dir,
    reset_index,
)
from second_brain.models import DocumentMetadata
from second_brain.chunker import Chunk
from second_brain import embeddings as emb_mod


@pytest.fixture(autouse=True)
def tmp_data_dir(monkeypatch):
    """Isolate all store tests to a temp dir. Reset state."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        monkeypatch.setenv("SECOND_BRAIN_DATA_DIR", str(tmp))
        # force re-eval of module default
        import second_brain.store as store_mod
        store_mod.DEFAULT_DATA_DIR = tmp
        reset_index()
        yield tmp
        reset_index()


def _fake_meta(source_path: str = "demo/notes/test.md", data_zone: str = "PUBLIC_DEMO") -> DocumentMetadata:
    now = datetime.utcnow()
    return DocumentMetadata(
        source_path=source_path,
        content_hash="deadbeef" * 8,
        doc_id="doc1234567890ab",
        ingested_at=now,
        title="Test Doc",
        tags=["test"],
        data_zone=data_zone,
    )


def _fake_chunks(n: int = 2) -> List[Chunk]:
    return [
        Chunk(
            content=f"Chunk {i} content about project Falcon and latency.",
            heading_path="Test > Section",
            chunk_index=i,
            source_line_range=(1 + i * 5, 5 + i * 5),
        )
        for i in range(n)
    ]


def test_add_document_and_manifest(monkeypatch):
    # Patch embed to deterministic fixed vector (no ollama)
    def fake_embed(text: str):
        # simple hash based deterministic 768-dim
        base = sum(ord(c) for c in text) % 100 / 100.0
        return [base + (i % 7) * 0.01 for i in range(768)]

    monkeypatch.setattr(emb_mod, "embed_text", fake_embed)

    meta = _fake_meta()
    chunks = _fake_chunks(3)
    add_document(meta, chunks)

    status = get_manifest_status()
    assert len(status) == 1
    assert status[0]["doc_id"] == meta.doc_id
    assert status[0]["num_chunks"] == 3
    assert status[0]["data_zone"] == "PUBLIC_DEMO"


def test_search_basic(monkeypatch):
    def fake_embed(text: str):
        base = 0.42 if "Falcon" in text else 0.1
        return [base + (i % 5) * 0.001 for i in range(768)]

    monkeypatch.setattr(emb_mod, "embed_text", fake_embed)

    meta = _fake_meta()
    add_document(meta, _fake_chunks(2))

    hits = search("Project Falcon latency", limit=5)
    assert len(hits) >= 1
    assert any("Falcon" in h.get("content", "") for h in hits)


def test_zone_filter_in_search(monkeypatch):
    def fake_embed(_):
        return [0.5 + (i % 3) * 0.01 for i in range(768)]

    monkeypatch.setattr(emb_mod, "embed_text", fake_embed)

    meta_p = _fake_meta(data_zone="PERSONAL")
    add_document(meta_p, _fake_chunks(1))

    meta_pub = _fake_meta(source_path="demo/pub.md", data_zone="PUBLIC_DEMO")
    add_document(meta_pub, _fake_chunks(1))

    # Search with zone
    hits_p = search("anything", limit=10, data_zone="PERSONAL")
    assert len(hits_p) >= 1 and all(h["data_zone"] == "PERSONAL" for h in hits_p)

    hits_all = search("anything", limit=10)
    assert len(hits_all) >= 2


def test_empty_chunks_noop(monkeypatch):
    def fake_embed(_): return [0.0]*768
    monkeypatch.setattr(emb_mod, "embed_text", fake_embed)

    add_document(_fake_meta(), [])
    assert get_manifest_status() == []
