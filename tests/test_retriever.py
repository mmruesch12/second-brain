"""Tests for immortal baseline_rag retriever.

Mocks store.search. Verifies zone filter passthrough, empty handling, citation keys.
"""

from unittest.mock import patch

from src.second_brain.retriever import baseline_rag


def test_baseline_rag_basic():
    fake_hits = [
        {"doc_id": "d1", "chunk_index": 0, "content": "foo", "source_path": "demo/a.md", "heading_path": "H", "data_zone": "PUBLIC_DEMO", "title": "A"},
        {"doc_id": "d2", "chunk_index": 1, "content": "bar", "source_path": "demo/b.md", "heading_path": "H2", "data_zone": "PUBLIC_DEMO", "title": "B"},
    ]

    with patch("src.second_brain.retriever.search", return_value=fake_hits) as m:
        res = baseline_rag("test query", limit=5)
        assert len(res) == 2
        assert res[0]["chunk_id"] == "d1:0"
        assert res[0]["heading"] == "H"
        assert "content" in res[0]
        m.assert_called_once()


def test_baseline_rag_empty_query():
    res = baseline_rag("")
    assert res == []
    res2 = baseline_rag("   ")
    assert res2 == []


def test_baseline_rag_zone_filter():
    with patch("src.second_brain.retriever.search", return_value=[]) as m:
        baseline_rag("q", zone="PERSONAL")
        m.assert_called_with("q", limit=8, data_zone="PERSONAL")


def test_baseline_rag_adds_citation_keys():
    fake = [{"doc_id": "x", "chunk_index": 3, "content": "c", "source_path": "s", "heading_path": "hp", "data_zone": "d"}]
    with patch("src.second_brain.retriever.search", return_value=fake):
        res = baseline_rag("q")
        assert res[0]["chunk_id"] == "x:3"
        assert res[0]["heading"] == "hp"
