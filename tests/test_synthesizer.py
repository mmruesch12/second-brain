"""Tests for minimal synthesizer.

Mocks litellm and retrieve (Phase1 path). baseline_rag contract untouched/immortal.
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

    with patch("second_brain.synthesizer.retrieve", return_value=fake_hits):
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
    with patch("second_brain.synthesizer.retrieve", return_value=fake_hits):
        with patch("second_brain.synthesizer.litellm.completion", side_effect=Exception("no ollama")):
            res = synthesize("query")
            assert "synthesis unavailable" in res.answer_markdown or "From context" in res.answer_markdown
            assert res.model_used == "fallback"


def test_synthesize_stream_writes(capsys):
    """Phase2 stream path: litellm stream yields chunks, live writes + collect."""
    fake_hits = [{"source_path": "demo/s.md", "heading": "", "content": "Stream fact.", "chunk_id": "s:0"}]
    with patch("second_brain.synthesizer.retrieve", return_value=fake_hits):
        # mock stream iterator
        class Chunk:
            def __init__(self, c):
                self.choices = [type("c", (), {"delta": type("d", (), {"content": c})()})()]
        chunks = [Chunk("Live "), Chunk("stream "), Chunk("output.")]
        mock_stream = iter(chunks)
        with patch("second_brain.synthesizer.litellm.completion", return_value=mock_stream):
            res = synthesize("stream q?", stream=True)
            captured = capsys.readouterr()
            assert "Live stream output." in captured.out
            assert "Live stream output." in res.answer_markdown
            assert res.model_used


def test_synthesize_with_verify():
    """Phase2 verify: calls verifier, populates verdict on resp."""
    fake_hits = [{"source_path": "demo/v.md", "heading": "", "content": "Verify support here.", "chunk_id": "v:0"}]
    with patch("second_brain.synthesizer.retrieve", return_value=fake_hits):
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "Supported claim."
        with patch("second_brain.synthesizer.litellm.completion", return_value=mock_resp):
            with patch("second_brain.verifier.verify_citations", return_value="SUPPORTED"):
                res = synthesize("verify q", verify=True)
                assert res.verifier_verdict == "SUPPORTED"


def test_synthesize_stream_and_verify_combo(capsys):
    """Combo stream+verify."""
    fake_hits = [{"source_path": "demo/c.md", "content": "Combo ok.", "chunk_id": "c:0"}]
    with patch("second_brain.synthesizer.retrieve", return_value=fake_hits):
        class Chunk:
            def __init__(self, c): self.choices = [type("c", (), {"delta": type("d", (), {"content": c})()})()]
        with patch("second_brain.synthesizer.litellm.completion", return_value=iter([Chunk("ok")])):
            with patch("second_brain.verifier.verify_citations", return_value="PARTIAL"):
                res = synthesize("combo", stream=True, verify=True)
                assert res.verifier_verdict == "PARTIAL"
                assert "ok" in capsys.readouterr().out


def test_synthesize_stream_airgap_fallback_empty_edges(monkeypatch, capsys):
    """Extend coverage for airgap+stream, fallback+stream, no-hits+stream (PRD edges)."""
    fake_hits = [{"source_path": "demo/e.md", "content": "e", "chunk_id": "e:0"}]
    with patch("second_brain.synthesizer.retrieve", return_value=fake_hits):
        # airgap stream
        monkeypatch.setenv("SECOND_BRAIN_AIRGAP", "1")
        res = synthesize("airgap q", stream=True)
        out = capsys.readouterr().out
        assert "airgap" in out.lower() or "blocked" in out.lower()
        assert res.verifier_verdict is None or "UNVERIFIED" not in str(res.verifier_verdict)  # airgap path no verify
        monkeypatch.delenv("SECOND_BRAIN_AIRGAP", raising=False)

    with patch("second_brain.synthesizer.retrieve", return_value=fake_hits):
        with patch("second_brain.synthesizer.litellm.completion", side_effect=Exception("no model for fallback")):
            res = synthesize("fallback q", stream=True)
            out = capsys.readouterr().out
            assert "synthesis unavailable" in out or "From context" in out

    # no-hits stream (early return)
    with patch("second_brain.synthesizer.retrieve", return_value=[]):
        res = synthesize("no hits q", stream=True)
        out = capsys.readouterr().out
        assert "No indexed" in out or "No indexed" in res.answer_markdown


def test_verifier_airgap_empty_direct(monkeypatch):
    """Direct edge for verifier (airgap, empty) without new file."""
    from second_brain.verifier import verify_citations
    monkeypatch.setenv("SECOND_BRAIN_AIRGAP", "1")
    v = verify_citations("q", "ans", [{"content": "ctx"}])
    assert v == "UNVERIFIED"
    monkeypatch.delenv("SECOND_BRAIN_AIRGAP", raising=False)
    v2 = verify_citations("q", "", [{"content": "ctx"}])
    assert v2 == "UNVERIFIED"
