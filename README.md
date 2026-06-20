# Personal Agentic Second Brain

**A governed, personal knowledge operating system powered by multi-agent workflows.**

Build a local-first system that ingests scattered notes, research, ideas, and documents, then lets you query, synthesize, and act on that information through a multi-agent system with strong traceability, critic loops, and human oversight.

The goal is to reduce cognitive load and context-switching friction — especially valuable for high-demand lives involving work leadership, family, home projects, and creative work. This should feel like an extension of your own thinking.

---

## Vision

> Build a governed, personal knowledge operating system that ingests scattered notes, research, ideas, and documents, then lets you query, synthesize, and act on that information through a multi-agent system with strong traceability, critic loops, and human oversight.

This project serves both personal productivity and as a living, public demonstration of production-grade agentic patterns.

---

## Project Status

- **Version**: 0.0.1 (Phase 0a baseline)
- **Status**: Phase 0a complete (spec gates + Markdown ingest + baseline RAG + eval + CLI). See progress.md and PRD for details.
- **Owner**: Matt Ruesch
- **Date**: 2026-06-19

**Current PRD:** [personal-agentic-second-brain-prd-v2.md](./personal-agentic-second-brain-prd-v2.md)  
**Previous:** [personal-agentic-second-brain-prd.md](./personal-agentic-second-brain-prd.md) (v0.1, superseded)

**Contributors & AI agents:** Read [AGENTS.md](./AGENTS.md) before making changes — mandatory privacy rules, PRD phase gates, and pre-commit checklist.

---

## MVP Scope (Key Highlights)

**In Scope for v1**
- Local-first ingestion of Markdown and text-native PDFs
- Hybrid retrieval (vector similarity + metadata + wikilink structure)
- CLI-first interface (`sb` command)
- Retrieval-first pipeline: baseline RAG → optional citation verifier → LangGraph only if earned
- Structured, cited responses with source traceability
- Bounded reflection and starter rituals (`sb morning`, `sb weekly`, etc.)
- Local observability, egress ledger, and data-zone enforcement

**Explicitly Out of Scope (MVP)**
- Multi-user / sharing
- Voice, real-time collab, long-term conversational memory
- Cloud tracing on real personal data
- Polished web UI (Streamlit deferred)
- Complex external automations

See the v0.2 PRD for complete scoping, phase gates, and design principles.

---

## Key Design Principles

- **Governance first**: Optional verifier + human feedback
- **Traceability always**: Every answer shows its sources
- **Low-friction defaults**: Concise, actionable outputs
- **Local-first & private**: Air-gap by default; cloud requires explicit opt-in
- **Pragmatic determinism**: Structured outputs and explicit routing

---

## Phasing & Timeline

| Phase | Focus | Target | Status |
|-------|-------|--------|--------|
| 0a | Markdown ingest + baseline RAG + eval harness + CLI doctor | 2–3 days | **Complete** (on demo/) |
| 0b | PDF ingest + quick capture | 1–2 days | Not started |
| 1 | Retrieval hardening (no new agents) | 2–3 days | Not started |
| 2 | Citation verifier + starter rituals | 1–2 days | Not started |
| 3 | Reflection CLI + real-world iteration | 1 weekend + 3–4 weeks | Not started |

Target: Useful, personally valuable MVP in 6–10 focused days (Phases 0–2), then iterate in daily use. Phase 0a acceptance verified via harness + `sb doctor`. See `docs/progress.md`.

---

## Getting Started

### Prerequisites (local-first)
- Python 3.12+
- Ollama running locally with `nomic-embed-text` (for embeddings) and a chat model (e.g. `llama3.2` or `qwen2.5`)
- `pip install -e .` (or `PYTHONPATH=src` for direct)

```bash
# 1. Install editable + see CLI
pip install -e .
sb --help

# 2. Health check (no LLM needed)
sb doctor

# 3. Ingest the demo corpus (or your markdown)
sb ingest demo/notes

# 4. Query (requires Ollama + nomic-embed-text pulled)
sb query "What were the key decisions from Project Falcon?"

# Status / manifest
sb ingest --status
```

**Note**: Full runtime requires Ollama + models. Use `sb doctor` and `PYTHONPATH=src python -m pytest` (with mocks) for verification without all deps.

See the v0.2 PRD for architecture (LanceDB, LiteLLM/Ollama, DataZones, .secondbrainignore). Current Phase 0a implements immortal `baseline_rag`, cited synthesis, golden eval harness (demo corpus), and `sb ingest|query|doctor`. Later phases add PDF, rituals (`sb weekly`), verifier per gates.

---

## Repository Contents

| File | Description |
|------|-------------|
| `personal-agentic-second-brain-prd-v2.md` | Current product requirements document |
| `personal-agentic-second-brain-prd.md` | Original PRD (v0.1, superseded) |
| `AGENTS.md` | Rules and best practices for AI agents and contributors |
| `CONTRIBUTING.md` | Short contributor guide (links to AGENTS.md) |
| `SECURITY.md` | Vulnerability reporting policy |
| `README.md` | Project overview |
| `LICENSE` | MIT License |

---

## Success Criteria

The MVP will be considered successful when:
- I actively prefer using it over current ad-hoc methods for at least one important recurring need.
- Golden-query eval meets the rubric threshold defined in the PRD.
- I can clearly articulate the architecture, key design decisions, tradeoffs, and real usage learnings.

---

*This project prioritizes building something genuinely useful over feature completeness or agent count.*