"""Tests for minimal synthesizer.

Mocks litellm and baseline_rag.
"""

from unittest.mock import patch, MagicMock

from second_brain.synthesizer import synthesize
from second_brain.models import SynthesisResponse


def test_synthesize_empty():
    res = synthesize("")
    assert isinstance(res, SynthesisResponse)
    assert "No query" in res.answer_markdown or "No relevant" in res.answer_markdown


def test_synthesize_with_hits_mocked():
    fake_hits = [
        {"source_path": "demo/a.md", "heading": "H1", "content": "Important fact about Falcon.", "chunk_id": "d1:0"},
    ]

    with patch("second_brain.synthesizer.baseline_rag", return_value=fake_hits):
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "- Key point [demo/a.md: H1]\n\nNext action: review Falcon."
        with patch("second_brain.synthesizer.litellm.completion", return_value=mock_resp):
            res = synthesize("What about Falcon?", profile="brief")
            assert isinstance(res, SynthesisResponse)
            assert "Key point" in res.answer_markdown
            assert len(res.citations) >= 1
            assert res.profile == "brief"
            assert res.model_used


def test_synthesize_fallback_on_error():
    fake_hits = [{"source_path": "demo/b.md", "heading": "", "content": "Data here.", "chunk_id": "d2:0"}]
    with patch("second_brain.synthesizer.baseline_rag", return_value=fake_hits):
        with patch("second_brain.synthesizer.litellm.completion", side_effect=Exception("no ollama")):
            res = synthesize("query")
            assert "synthesis unavailable" in res.answer_markdown or "From context" in res.answer_markdown
            assert res.model_used == "fallback"
