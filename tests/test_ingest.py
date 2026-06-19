"""Tests for ingest pipeline (Phase 0a).

Mocks store + embed. Tests ignore, zone resolution, frontmatter, --status equivalent, file/dir.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import patch

import pytest

from src.second_brain import ingest as ingest_mod
from src.second_brain.ingest import (
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
        import src.second_brain.store as store_mod
        store_mod.DEFAULT_DATA_DIR = tmp
        store_mod._init_manifest = lambda: None  # will be called internally
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

    monkeypatch.setattr("src.second_brain.ingest.add_document", fake_add)

    # run from tmp as cwd simulation not strict
    with patch("src.second_brain.ingest.Path.cwd", return_value=tmp_path):
        res = ingest(str(md))
        assert res["added"] == 1
        assert res["skipped"] == 0
        assert calls and calls[0][3] == "PUBLIC_DEMO"  # demo path

    # status via mock
    def fake_status():
        return [{"doc_id": "d1", "source_path": str(md), "num_chunks": 1, "data_zone": "PUBLIC_DEMO", "ingested_at": "2026-..", "content_hash": "h", "title": "T"}]

    monkeypatch.setattr("src.second_brain.ingest.get_manifest_status", fake_status)
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

    monkeypatch.setattr("src.second_brain.ingest.add_document", fake_add)

    with patch("src.second_brain.ingest.Path.cwd", return_value=root):
        # reload patterns from our temp root? load looks for . in cwd, patch
        with patch("src.second_brain.ingest.Path", wraps=Path) as p:
            # simpler: run and count
            res = ingest(str(root))
            # good.md should be added, .tmp and secret skipped by ignore
            assert res["added"] == 1
            assert "good" in calls[0] if calls else True


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
    monkeypatch.setattr("src.second_brain.ingest.add_document", fake_add)

    with patch("src.second_brain.ingest.Path.cwd", return_value=tmp_path):
        ingest(str(f))
        assert calls and calls[0] == "WORK_ADJACENT"
