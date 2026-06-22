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
    fetch_by_filter,
    _apply_metadata_filters,
    log_decision,
    list_decisions,
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


def _fake_meta(source_path: str = "demo/notes/test.md", data_zone: str = "PUBLIC_DEMO", doc_type: str = "markdown", parse_quality: str = "ok") -> DocumentMetadata:
    now = datetime.utcnow()
    return DocumentMetadata(
        source_path=source_path,
        content_hash="deadbeef" * 8,
        doc_id="doc1234567890ab",
        ingested_at=now,
        title="Test Doc",
        tags=["test"],
        data_zone=data_zone,
        doc_type=doc_type,
        parse_quality=parse_quality,
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
    # Patch embed to deterministic fixed vector (no ollama). Patch both module attr and the name bound in store (from-import).
    def fake_embed(text: str):
        # simple hash based deterministic 768-dim
        base = sum(ord(c) for c in text) % 100 / 100.0
        return [base + (i % 7) * 0.01 for i in range(768)]

    monkeypatch.setattr(emb_mod, "embed_text", fake_embed)
    monkeypatch.setattr("second_brain.store.embed_text", fake_embed)

    meta = _fake_meta()
    chunks = _fake_chunks(3)
    add_document(meta, chunks)

    status = get_manifest_status()
    assert len(status) == 1
    assert status[0]["doc_id"] == meta.doc_id
    assert status[0]["num_chunks"] == 3
    assert status[0]["data_zone"] == "PUBLIC_DEMO"
    assert status[0].get("doc_type") == "markdown"
    assert status[0].get("parse_quality") == "ok"


def test_search_basic(monkeypatch):
    def fake_embed(text: str):
        base = 0.42 if "Falcon" in text else 0.1
        return [base + (i % 5) * 0.001 for i in range(768)]

    monkeypatch.setattr(emb_mod, "embed_text", fake_embed)
    monkeypatch.setattr("second_brain.store.embed_text", fake_embed)

    meta = _fake_meta()
    add_document(meta, _fake_chunks(2))

    hits = search("Project Falcon latency", limit=5)
    assert len(hits) >= 1
    assert any("Falcon" in h.get("content", "") for h in hits)


def test_zone_filter_in_search(monkeypatch):
    def fake_embed(_):
        return [0.5 + (i % 3) * 0.01 for i in range(768)]

    monkeypatch.setattr(emb_mod, "embed_text", fake_embed)
    monkeypatch.setattr("second_brain.store.embed_text", fake_embed)

    meta_p = _fake_meta(data_zone="PERSONAL")
    add_document(meta_p, _fake_chunks(1))

    meta_pub = _fake_meta(source_path="demo/pub.md", data_zone="PUBLIC_DEMO")
    add_document(meta_pub, _fake_chunks(1))

    # Search with zone
    hits_p = search("anything", limit=10, data_zone="PERSONAL")
    assert len(hits_p) >= 1 and all(h["data_zone"] == "PERSONAL" for h in hits_p)

    hits_all = search("anything", limit=10, data_zone="all")
    assert len(hits_all) >= 2


def test_empty_chunks_noop(monkeypatch):
    """0-chunk now records manifest row (for failure visibility) but no vectors; updated post 0b fix."""
    def fake_embed(_): return [0.0]*768
    monkeypatch.setattr(emb_mod, "embed_text", fake_embed)
    monkeypatch.setattr("second_brain.store.embed_text", fake_embed)

    add_document(_fake_meta(), [])
    status = get_manifest_status()
    assert len(status) == 1
    assert status[0]["num_chunks"] == 0
    # no vectors added for 0-chunk (lance table may be empty or prior)
    # (vectors conditional in add_document)


def test_search_metadata_filters(monkeypatch):
    def fake_embed(_):
        return [0.42 + (i % 5) * 0.001 for i in range(768)]

    monkeypatch.setattr(emb_mod, "embed_text", fake_embed)
    monkeypatch.setattr("second_brain.store.embed_text", fake_embed)

    now = datetime.utcnow()
    meta_acme = DocumentMetadata(
        source_path="demo/acme.md",
        content_hash="h"*64,
        doc_id="acme1",
        ingested_at=now,
        modified_at=now,
        title="Acme",
        tags=["acme", "planning"],
        data_zone="PUBLIC_DEMO",
    )
    add_document(meta_acme, _fake_chunks(1))

    meta_f = DocumentMetadata(
        source_path="demo/falcon.md",
        content_hash="h"*64,
        doc_id="falc1",
        ingested_at=now,
        modified_at=datetime(2026, 5, 1),
        title="Falcon",
        tags=["falcon"],
        data_zone="PUBLIC_DEMO",
    )
    add_document(meta_f, _fake_chunks(1))

    # tag any
    hits = search("anything", limit=5, tags=["acme"])
    assert len(hits) >= 1 and any("acme" in str(h.get("source_path", "")) for h in hits)

    # since filter (acme uses now >= 2026-06-01, falcon old)
    hits_since = search("x", limit=5, since="2026-06-01")
    assert len(hits_since) >= 1 and any("acme" in str(h.get("source_path", "")) for h in hits_since)

    # path prefix (acme added with "demo/acme.md"; prefix matches)
    hits_p = search("x", limit=5, path_prefix="demo/ac")
    assert len(hits_p) >= 1 and any("acme" in str(h.get("source_path", "")) for h in hits_p)


def test_cross_zone_no_leak(monkeypatch):
    """Zero tolerance cross-zone leaks (Phase 1 privacy)."""
    def fake_embed(_):
        return [0.5 + (i % 3) * 0.01 for i in range(768)]

    monkeypatch.setattr(emb_mod, "embed_text", fake_embed)
    monkeypatch.setattr("second_brain.store.embed_text", fake_embed)

    meta_p = _fake_meta(source_path="notes/personal.md", data_zone="PERSONAL")
    add_document(meta_p, _fake_chunks(1))

    meta_pub = _fake_meta(source_path="demo/pub.md", data_zone="PUBLIC_DEMO")
    add_document(meta_pub, _fake_chunks(1))

    hits_pub = search("anything", limit=10, data_zone="PUBLIC_DEMO")
    assert all(h["data_zone"] == "PUBLIC_DEMO" for h in hits_pub)
    assert not any(h["data_zone"] == "PERSONAL" for h in hits_pub)

    hits_pers = search("anything", limit=10, data_zone="PERSONAL")
    assert all(h["data_zone"] == "PERSONAL" for h in hits_pers)
    assert not any(h["data_zone"] == "PUBLIC_DEMO" for h in hits_pers)


def test_fetch_by_filter_wikilink(monkeypatch):
    def fake_embed(_):
        return [0.1] * 768

    monkeypatch.setattr(emb_mod, "embed_text", fake_embed)
    monkeypatch.setattr("second_brain.store.embed_text", fake_embed)

    meta = _fake_meta(source_path="demo/link.md", data_zone="PUBLIC_DEMO")
    meta.wikilinks = ["target-doc"]
    add_document(meta, _fake_chunks(1))

    hits = fetch_by_filter(wikilink_target="target-doc", limit=5)
    assert len(hits) >= 1


def test_search_match_all_tags_and_bad_since(monkeypatch):
    def fake_embed(_):
        return [0.5] * 768
    monkeypatch.setattr(emb_mod, "embed_text", fake_embed)
    monkeypatch.setattr("second_brain.store.embed_text", fake_embed)

    now = datetime.utcnow()
    m1 = DocumentMetadata(source_path="demo/m1.md", content_hash="h1", doc_id="m1", ingested_at=now, modified_at=now, tags=["acme", "q3"], data_zone="PUBLIC_DEMO")
    add_document(m1, _fake_chunks(1))
    m2 = DocumentMetadata(source_path="demo/m2.md", content_hash="h2", doc_id="m2", ingested_at=now, modified_at=now, tags=["acme"], data_zone="PUBLIC_DEMO")
    add_document(m2, _fake_chunks(1))

    # match_all: only docs with all tags
    hits_all = search("x", limit=5, tags=["acme", "q3"], match_all_tags=True)
    assert len(hits_all) >= 1 and all("m1" in str(h.get("source_path","")) for h in hits_all)

    # bad since: no crash, loose keep
    hits_bad = search("x", limit=5, since="not-a-date")
    assert isinstance(hits_bad, list)


def test_legacy_rows_missing_cols(monkeypatch):
    """Pre-Phase1 rows missing tags/wikilinks/modified_at should not crash filter; treated lenient (direct legacy dict sim)."""
    # true legacy row: no Phase1 meta cols at all (sim pre-Phase1 Lance row)
    legacy = {
        "doc_id": "leg",
        "chunk_index": 0,
        "content": "legacy content no meta",
        "source_path": "demo/legacy.md",
        "heading_path": "L",
        "data_zone": "PUBLIC_DEMO",
        "title": "L",
        # missing: tags, modified_at, wikilinks  (sim old row)
    }
    # tag requested on missing -> filter drops (lenient: [] treated as no match)
    filtered = _apply_metadata_filters([legacy], tags=["nonexistent"])
    assert isinstance(filtered, list) and len(filtered) == 0
    # no tag req -> keeps
    filtered2 = _apply_metadata_filters([legacy])
    assert len(filtered2) == 1
    # since on missing ma: keeps (lenient)
    filtered3 = _apply_metadata_filters([legacy], since="2026-01-01")
    assert len(filtered3) == 1


def test_decision_log_append_list():
    """Phase3: direct unit test for log_decision + list_decisions (append, most-recent, since filter, keys, empty, citation). Uses tmp fixture."""
    # clean start (list should be empty)
    assert list_decisions(limit=10) == []
    p = log_decision("Decision A about Phoenix", citation="demo/notes/2026-06-05-acme-q3.md")
    assert "decisions.jsonl" in p
    # append second
    log_decision("Decision B on Falcon sync")
    entries = list_decisions(limit=5)
    assert len(entries) == 2
    assert entries[0]["text"] == "Decision B on Falcon sync"  # most recent first
    assert entries[1]["citation"] == "demo/notes/2026-06-05-acme-q3.md"
    assert "timestamp" in entries[0]
    # since filter (future date -> none)
    assert list_decisions(since="2030-01-01") == []
    # since that matches first
    recent = list_decisions(since="2026-01-01", limit=1)
    assert len(recent) == 1 and "Falcon" in recent[0]["text"]
    # citation empty str for absent (standardized)
    log_decision("No cite decision")
    assert any(e.get("citation") == "" for e in list_decisions(limit=1))
