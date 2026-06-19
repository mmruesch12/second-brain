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

- **Version**: 0.2 (consensus-hardened MVP)
- **Status**: Planning — PRD v0.2 complete; implementation not started
- **Owner**: Matt Ruesch
- **Date**: June 19, 2026

**Current PRD:** [personal-agentic-second-brain-prd-v2.md](./personal-agentic-second-brain-prd-v2.md)  
**Previous:** [personal-agentic-second-brain-prd.md](./personal-agentic-second-brain-prd.md) (v0.1, superseded)

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

| Phase | Focus | Target |
|-------|-------|--------|
| 0a | Markdown ingest + baseline RAG + eval harness | 2–3 days |
| 0b | PDF ingest + quick capture | 1–2 days |
| 1 | Retrieval hardening (no new agents) | 2–3 days |
| 2 | Citation verifier + starter rituals | 1–2 days |
| 3 | Reflection CLI + real-world iteration | 1 weekend + 3–4 weeks |

Target: Useful, personally valuable MVP in 6–10 focused days (Phases 0–2), then iterate in daily use.

---

## Getting Started (Coming Soon)

Once implementation begins:

```bash
sb capture "quick thought"
sb ingest ./notes
sb query "What were my key insights on X last month?"
sb weekly
```

See the v0.2 PRD for technical architecture (LanceDB, LiteLLM, Ollama, etc.).

---

## Repository Contents

| File | Description |
|------|-------------|
| `personal-agentic-second-brain-prd-v2.md` | Current product requirements document |
| `personal-agentic-second-brain-prd.md` | Original PRD (v0.1, superseded) |
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