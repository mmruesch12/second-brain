# Personal Agentic Second Brain

**A governed, personal knowledge operating system powered by multi-agent workflows.**

Build a local-first system that ingests scattered notes, research, ideas, and documents, then lets you query, synthesize, and act on that information through a multi-agent system with strong traceability, critic loops, and human oversight.

The goal is to reduce cognitive load and context-switching friction — especially valuable for high-demand lives involving work leadership, ADHD management, family, home projects, and creative work. This should feel like an extension of your own thinking.

---

## Vision

> Build a governed, personal knowledge operating system that ingests my scattered notes, research, ideas, and documents, then lets me query, synthesize, and act on that information through a multi-agent system with strong traceability, critic loops, and human oversight.

This project serves both personal productivity and as a living, public demonstration of production-grade agentic patterns.

---

## Project Status

- **Version**: 0.1 (MVP-focused)
- **Status**: PRD complete — implementation starting
- **Owner**: Matt Ruesch
- **Date**: June 19, 2026

See the full [personal-agentic-second-brain-prd.md](./personal-agentic-second-brain-prd.md) for detailed requirements, architecture, success criteria, and phased timeline.

---

## MVP Scope (Key Highlights)

**In Scope for v1**
- Local-first ingestion of Markdown notes and PDFs
- Hybrid retrieval (vector similarity + metadata/graph)
- Multi-agent query orchestration with **LangGraph**:
  - Query Planner / Router
  - Retriever agent(s)
  - Synthesizer
  - Critic / Verifier
- Human-in-the-loop checkpoints
- Structured, cited responses with source traceability
- Basic reflection / extraction agent
- CLI primary + optional lightweight Streamlit UI
- Basic observability and feedback capture

**Explicitly Out of Scope (MVP)**
- Multi-user / sharing
- Voice, real-time collab, long-term memory across sessions
- Complex external automations
- Heavy local model hosting

See PRD for complete scoping and design principles.

---

## Key Design Principles

- **Governance first**: Critic agent + human checkpoints
- **Traceability always**: Every answer shows its sources
- **ADHD-friendly defaults**: Concise, actionable outputs
- **Local-first & private**: Data stays on-device by default
- **Pragmatic determinism**: Structured outputs and explicit routing

---

## Phasing & Timeline

| Phase | Focus                          | Target          |
|-------|--------------------------------|-----------------|
| 0     | Foundation (ingestion + baseline RAG) | 1 weekend      |
| 1     | Agentic Core (LangGraph + CLI) | 1–2 weekends   |
| 2     | Usability & Reflection         | 1 weekend      |
| 3     | Real-World Iteration           | Ongoing (3–4 weeks use) |

Target: Useful, personally valuable MVP within 3–5 focused sessions.

---

## Getting Started (Coming Soon)

Once implementation begins:

```bash
# Example future usage
personal-brain ingest ./notes
personal-brain query "What were my key insights on X last month?"
personal-brain reflect --recent
```

See PRD for initial technical architecture (LangGraph, LiteLLM, Chroma/LanceDB, etc.).

---

## Repository Contents

- `personal-agentic-second-brain-prd.md` — Full product requirements document
- `README.md` — This file (project overview)

---

## Success Criteria

The MVP will be considered successful when:
- I actively prefer using it over current ad-hoc methods for at least one important recurring need.
- I can clearly articulate the architecture, key design decisions, tradeoffs, and real usage learnings.

---

*This project prioritizes building something I will actually use and can speak about with authenticity over feature completeness.*

**End of initial project scaffold**
