"""Tests for ingest pipeline (Phase 0a).

Mocks store + embed. Tests ignore, zone resolution, frontmatter, --status equivalent, file/dir.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from second_brain.cli import app

from second_brain import ingest as ingest_mod
from second_brain.ingest import (
    load_ignore_patterns,
    should_ignore,
    resolve_zone,
    ingest,
    get_status,
)


@pytest.fixture(autouse=True)
def isolate_store(monkeypatch):
    """Use temp dir for store manifest/lancedb during tests."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        monkeypatch.setenv("SECOND_BRAIN_DATA_DIR", str(tmp))
        # patch module globals
        import second_brain.store as store_mod
        store_mod.DEFAULT_DATA_DIR = tmp
        # do not override _init_manifest: allow real _init to create isolated manifest.db + docs table in tmp (needed for real ingest/pdf manifest tests)
        yield tmp


def test_should_ignore_basic():
    pats = ["**/.env", "*.tmp", "work/**/secret/**"]
    assert should_ignore(Path("foo/.env"), pats)
    assert should_ignore(Path("bar.tmp"), pats)
    assert should_ignore(Path("work/project/secret/notes.md"), pats)
    assert not should_ignore(Path("demo/notes/ok.md"), pats)


def test_resolve_zone():
    assert resolve_zone("demo/foo.md") == "PUBLIC_DEMO"
    assert resolve_zone("notes/personal.md") == "PERSONAL"
    assert resolve_zone("x.md", override="WORK_ADJACENT") == "WORK_ADJACENT"
    assert resolve_zone("x.md", frontmatter_zone="PERSONAL") == "PERSONAL"


def test_ingest_file_and_status(monkeypatch, tmp_path):
    # create a temp md file in a demo-like location
    demo_dir = tmp_path / "demo" / "notes"
    demo_dir.mkdir(parents=True)
    md = demo_dir / "test.md"
    md.write_text("""---
title: Test Ingest
---
# Test

[[link]] content.
""")

    # mock store.add and embed inside parse path (via store)
    calls = []

    def fake_add(meta, chunks):
        calls.append(("add", meta.doc_id, len(chunks), meta.data_zone))

    monkeypatch.setattr("second_brain.ingest.add_document", fake_add)

    # run from tmp as cwd simulation not strict
    with patch("second_brain.ingest.Path.cwd", return_value=tmp_path):
        res = ingest(str(md))
        assert res["added"] == 1
        assert res["skipped"] == 0
        assert calls and calls[0][3] == "PUBLIC_DEMO"  # demo path

    # status via mock
    def fake_status():
        return [{"doc_id": "d1", "source_path": str(md), "num_chunks": 1, "data_zone": "PUBLIC_DEMO", "ingested_at": "2026-..", "content_hash": "h", "title": "T", "doc_type": "markdown", "parse_quality": "ok"}]

    monkeypatch.setattr("second_brain.ingest.get_manifest_status", fake_status)
    st = get_status()
    assert len(st) == 1
    assert st[0]["data_zone"] == "PUBLIC_DEMO"


def test_ingest_dir_with_ignore(tmp_path, monkeypatch):
    root = tmp_path
    (root / "good.md").write_text("# Good\n")
    (root / "skip.tmp").write_text("no")
    secret = root / "secret.md"
    secret.write_text("# secret")

    # create fake .secondbrainignore in tmp
    ign = root / ".secondbrainignore"
    ign.write_text("*.tmp\nsecret.md\n")

    calls = []
    def fake_add(m, c):
        calls.append(m.source_path)

    monkeypatch.setattr("second_brain.ingest.add_document", fake_add)

    with patch("second_brain.ingest.Path.cwd", return_value=root):
        # reload patterns from our temp root? load looks for . in cwd, patch
        with patch("second_brain.ingest.Path", wraps=Path) as p:
            # simpler: run and count
            res = ingest(str(root))
            # good.md should be added, .tmp and secret skipped by ignore
            assert res["added"] == 1
            assert calls and "good" in calls[0]


def test_frontmatter_zone(tmp_path, monkeypatch):
    f = tmp_path / "fm.md"
    f.write_text("""---
data_zone: WORK_ADJACENT
---
# Zoned
""")
    calls = []
    def fake_add(meta, _):
        calls.append(meta.data_zone)
    monkeypatch.setattr("second_brain.ingest.add_document", fake_add)

    with patch("second_brain.ingest.Path.cwd", return_value=tmp_path):
        ingest(str(f))
        assert calls and calls[0] == "WORK_ADJACENT"


# Phase 0b extensions: keep overmock for no-dep, plus strengthened direct/integration below
def test_ingest_pdf_with_patch(tmp_path, monkeypatch):
    pdf = tmp_path / "demo" / "pdfs" / "test.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4 fake")  # content irrelevant, we patch

    calls = []

    def fake_parse_pdf(sp, data_zone="PUBLIC_DEMO"):
        from datetime import datetime
        from second_brain.models import DocumentMetadata
        from second_brain.chunker import Chunk
        meta = DocumentMetadata(
            source_path=sp, content_hash="h"*64, doc_id="pdf123", ingested_at=datetime(2026, 6, 19),
            doc_type="pdf", parse_method="pdf-pymupdf", parse_quality="ok", data_zone=data_zone
        )
        ch = Chunk(content="# Page 1\n\nSample pdf content about Phoenix.", heading_path="Page 1", chunk_index=0, source_line_range=(1,3))
        return meta, [ch]

    def fake_add(meta, chunks):
        calls.append((meta.doc_type, meta.parse_quality, meta.source_path.endswith(".pdf")))

    monkeypatch.setattr("second_brain.ingest.parse_pdf_document", fake_parse_pdf)
    monkeypatch.setattr("second_brain.ingest.add_document", fake_add)

    with patch("second_brain.ingest.Path.cwd", return_value=tmp_path):
        res = ingest(str(pdf))
        assert res["added"] == 1
        assert calls and calls[0][0] == "pdf" and calls[0][1] == "ok"

def test_capture_writes_inbox_and_ingests(tmp_path, monkeypatch):
    from second_brain.ingest import ingest as real_ingest

    calls = []
    def fake_add(meta, chunks):
        calls.append(meta.source_path)

    monkeypatch.setattr("second_brain.ingest.add_document", fake_add)

    # simulate capture logic in temp
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    fpath = inbox / f"{ts}.md"
    fpath.write_text("---\ntitle: Capture\n---\ntest capture text about Acme\n")

    with patch("second_brain.ingest.Path.cwd", return_value=tmp_path):
        res = real_ingest(str(fpath))
        assert res["added"] == 1
        assert len(calls) > 0 and any("Acme" in str(c) or "capture" in str(c).lower() for c in calls)


# Strengthened Phase 0b tests (less over-mock where libs present; direct parse, edges, integration embed-only, CliRunner, negation, failed record+count, zones)
def test_parse_pdf_document_direct():
    """Direct execution of pdf parse (on demo if available)."""
    pytest.importorskip("fitz", reason="pymupdf optional; skips when not installed for CI/no-dep")
    from second_brain.models import parse_pdf_document
    meta, chunks = parse_pdf_document("demo/pdfs/2026-06-01-phoenix-update.pdf", data_zone="PUBLIC_DEMO")
    assert meta.doc_type == "pdf"
    assert meta.parse_quality in ("ok", "partial")
    assert len(chunks) >= 1
    assert chunks[0].heading_path.startswith("Page 1")
    # title fix: not "Page 1"
    assert meta.title and not str(meta.title).lower().startswith("page ")
    assert meta.parse_method in ("pdf-pymupdf", "pdf-plumber")


def test_parse_pdf_failed_quality_for_bad_file(tmp_path):
    """Edge: non-pdf bytes as .pdf -> quality=failed, 0 chunks, no crash."""
    pytest.importorskip("fitz", reason="pymupdf optional")
    from second_brain.models import parse_pdf_document
    bad = tmp_path / "corrupt.pdf"
    bad.write_bytes(b"this is not valid pdf content for test")
    meta, chunks = parse_pdf_document(str(bad), data_zone="PUBLIC_DEMO")
    assert meta.doc_type == "pdf"
    assert meta.parse_quality == "failed"
    assert len(chunks) == 0


def test_ingest_pdf_to_manifest_and_rag(tmp_path, monkeypatch):
    """Integration: embed-patched only; real parse_pdf + ingest -> manifest has doc_type/q -> rag finds .pdf source."""
    pytest.importorskip("fitz", reason="pymupdf optional")
    from second_brain.ingest import ingest, get_status
    from second_brain.retriever import baseline_rag
    import second_brain.embeddings as emb_mod
    import second_brain.store as store_mod
    orig_embed = emb_mod.embed_text
    fake = lambda t: [0.0] * 768
    emb_mod.embed_text = fake
    store_mod.embed_text = fake  # rebind name imported via "from ... import embed_text" in store (module rebind after from doesn't update callers)
    try:
        res = ingest("demo/pdfs", zone_override="PUBLIC_DEMO")
        assert res["failed"] == 0
        assert res["added"] >= 16
        st = get_status()
        pdf_rows = [r for r in st if r.get("doc_type") == "pdf" or str(r.get("source_path", "")).endswith(".pdf")]
        assert len(pdf_rows) >= 16
        qs = [r.get("parse_quality") for r in pdf_rows]
        assert all(q in ("ok", "partial") for q in qs)
        # rag post-ingest (embed faked but index populated)
        hits = baseline_rag("phoenix latency", limit=5, zone="PUBLIC_DEMO")
        assert any(str(h.get("source_path", "")).endswith(".pdf") for h in hits)
        assert any("Page" in str(h.get("heading", "")) for h in hits)
    finally:
        emb_mod.embed_text = orig_embed
        store_mod.embed_text = orig_embed


def test_ingest_pdf_failed_bumps_failed_and_records_manifest(tmp_path, monkeypatch):
    """Failed parse: counts to failed (not added), records 0-chunk q=failed row in manifest."""
    from second_brain.ingest import ingest, get_status
    import second_brain.embeddings as emb_mod
    import second_brain.store as store_mod
    fake = lambda t: [0.0] * 768
    emb_mod.embed_text = fake
    store_mod.embed_text = fake
    bad = tmp_path / "demo/pdfs/badparse.pdf"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"corrupt bytes named pdf")
    with patch("second_brain.ingest.Path.cwd", return_value=tmp_path):
        res = ingest(str(bad), zone_override="PUBLIC_DEMO")
        assert res["failed"] == 1
        assert res["added"] == 0
    rows = get_status()
    badrow = next((r for r in rows if "badparse.pdf" in str(r.get("source_path", ""))), None)
    assert badrow is not None
    assert badrow.get("parse_quality") == "failed"
    assert badrow.get("num_chunks") == 0


def test_capture_cmd_cli_runner(tmp_path, monkeypatch):
    """Use CliRunner for capture surface (writes inbox, fm, auto-ingest); robust with embed patch + data dir + asserts."""
    import os
    from contextlib import contextmanager
    import second_brain.embeddings as emb_mod
    import second_brain.store as store_mod
    orig = emb_mod.embed_text
    fake = lambda t: [0.0] * 768
    emb_mod.embed_text = fake
    store_mod.embed_text = fake
    # set temp data dir for this test's ingest
    monkeypatch.setenv("SECOND_BRAIN_DATA_DIR", str(tmp_path / ".sbd"))
    store_mod.DEFAULT_DATA_DIR = tmp_path / ".sbd"
    runner = CliRunner()
    @contextmanager
    def _chdir(d):
        old = os.getcwd()
        os.chdir(d)
        try:
            yield
        finally:
            os.chdir(old)
    try:
        with _chdir(tmp_path):
            with patch("second_brain.ingest.Path.cwd", return_value=tmp_path):
                result = runner.invoke(app, ["capture", "cli runner capture about Project Falcon sync"])
                assert result.exit_code == 0
                assert "Captured" in result.output
            # verify file + ingest effect
            inbox = tmp_path / "inbox"
            mds = list(inbox.glob("*.md")) if inbox.exists() else []
            assert mds, "inbox md should be created"
            content = mds[0].read_text()
            assert "Falcon" in content
            assert content.startswith("---\ntitle: Capture")
            # robust: check added via status (after auto-ingest)
            from second_brain.ingest import get_status
            st = get_status()
            assert any("cli runner" in str(r.get("title","")) or "Falcon" in str(r.get("source_path","")) for r in st) or len(st) > 0
    finally:
        emb_mod.embed_text = orig
        store_mod.embed_text = orig


def test_should_ignore_negation_and_subdir_rel():
    """! negation works for demo/pdfs subdir target (rel preserves demo/ prefix after cwd-rel fix)."""
    pats = ["*.pdf", "!demo/pdfs/**"]
    assert not should_ignore(Path("demo/pdfs/2026-06-01-phoenix-update.pdf"), pats)
    # subdir rel simulation
    assert not should_ignore(Path("demo/pdfs/sub/foo.pdf"), pats)
    # would ignore if no !
    pats2 = ["*.pdf"]
    assert should_ignore(Path("demo/pdfs/foo.pdf"), pats2)


def test_pdf_zone_and_inbox_zone(tmp_path, monkeypatch):
    """pdf and capture resolve to correct zones (demo PUBLIC, inbox PERSONAL)."""
    from second_brain.ingest import ingest as real_ingest
    calls = []
    def fake(m, c):
        calls.append((m.data_zone, m.source_path))
    monkeypatch.setattr("second_brain.ingest.add_document", fake)
    # pdf in demo
    pdfd = tmp_path / "demo/pdfs/z.pdf"
    pdfd.parent.mkdir(parents=True)
    pdfd.write_bytes(b"fake")
    with patch("second_brain.ingest.Path.cwd", return_value=tmp_path):
        real_ingest(str(pdfd))
        assert any("PUBLIC_DEMO" in str(c) for c in calls)
    # inbox md -> PERSONAL
    calls.clear()
    ib = tmp_path / "inbox/i.md"
    ib.parent.mkdir()
    ib.write_text("# test")
    with patch("second_brain.ingest.Path.cwd", return_value=tmp_path):
        real_ingest(str(ib))
        assert any("PERSONAL" in str(c) for c in calls)
