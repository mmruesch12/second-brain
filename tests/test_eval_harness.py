"""Tests for golden eval harness (PRD §3/13).

Tests loading (35+ queries), scoring range, mock run, result shape.
"""

from src.second_brain.eval_harness import load_golden_queries, run_golden_eval, compute_rubric


def test_loads_golden_queries():
    qs = load_golden_queries()
    assert len(qs) >= 30
    assert any("synthesis" in q.get("tags", []) for q in qs)
    assert all(q.get("source_hint", "").startswith("demo/") for q in qs)


def test_rubric_scores_in_range():
    q = "What were decisions on Project Falcon?"
    hits = [{"content": "Decision A on Falcon. Risk high.", "source_path": "demo/x.md"} for _ in range(3)]
    ans = "Decisions made. Next: review."
    total, dims = compute_rubric(q, hits, ans)
    assert 5 <= total <= 15
    assert all(1 <= v <= 3 for v in dims.values())


def test_run_harness_mock():
    summary = run_golden_eval(use_real_retrieval=False)
    assert summary["num_queries"] >= 30
    assert 0 <= summary["avg_score"] <= 15
    assert "results" in summary
    assert len(summary["results"]) == summary["num_queries"]
    # basic coverage
    assert summary["pass_10_15"] >= 0
