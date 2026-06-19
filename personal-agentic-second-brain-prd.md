# PRD: Personal Agentic Second Brain

**Project Name (Working Title):** Personal Agentic Second Brain  
**Version:** 0.1 (MVP-focused)  
**Date:** June 19, 2026  
**Owner:** Matt Ruesch  
**Status:** Draft for review and iteration

---

## 1. Vision

Build a governed, personal knowledge operating system that ingests my scattered notes, research, ideas, and documents, then lets me query, synthesize, and act on that information through a multi-agent system with strong traceability, critic loops, and human oversight.

The goal is to reduce cognitive load and context-switching friction in a life that already has high demands (work leadership, ADHD management, family, home projects, creative work). This should feel like an extension of my own thinking rather than another tool I have to manage.

---

## 2. Goals & Success Metrics

### Primary Goals
- Make it dramatically easier to find, connect, and synthesize information across personal and professional notes.
- Provide reliable, cited answers with clear provenance and traceability.
- Surface actionable insights (tasks, reflections, connections) without overwhelming output.
- Serve as a living, public demonstration of production-grade agentic patterns that can be credibly discussed in interviews.

### Success Metrics (MVP)
- New notes and PDFs can be ingested with minimal friction and queried the same day.
- At least 70% of queries return useful, well-cited answers on first try (self-assessed after 2–3 weeks of real use).
- Daily or near-daily active use for at least one recurring workflow (research synthesis, task extraction, weekly reflection, etc.).
- Clear architecture and decision log that demonstrates thoughtful governance, iteration, and real tradeoffs.

---

## 3. Target Users

- **Primary**: Matt Ruesch (single user for MVP).
- **Future consideration**: Light multi-user or shared family knowledge (e.g., with Marissa), but explicitly out of scope for v1.

---

## 4. MVP Scope (Ruthlessly Prioritized)

### In Scope for v1
- Local-first ingestion of Markdown notes and PDFs.
- Hybrid retrieval (vector similarity + metadata/graph relationships).
- Multi-agent query orchestration built with **LangGraph**:
  - Query Planner / Router
  - Retriever agent(s)
  - Synthesizer
  - Critic / Verifier (checks grounding, completeness, contradictions, hallucinations)
- Human-in-the-loop checkpoints or explicit feedback on outputs.
- Structured, cited responses with source links and lightweight confidence indicators.
- Basic reflection / extraction agent (e.g., “scan recent notes and surface open tasks, ideas, or insights”).
- Simple CLI (primary) + optional lightweight Streamlit UI.
- Basic observability: query logging, source tracing, cost tracking (when using external models), and feedback capture.

### Explicitly Out of Scope for MVP
- Multi-user support or sharing.
- Real-time collaboration or live editing.
- Voice interface.
- Long-term conversational memory across sessions (keep per-query or short session state).
- Complex external automations (auto-creating GitHub issues, calendar events, etc.) — save for v2+.
- Heavy local model hosting or fine-tuning (start with LiteLLM abstraction).
- Polished, production-grade UI (functional and clear is sufficient).

---

## 5. Core User Flows

### 1. Ingestion Flow
Drop Markdown files or PDFs into a designated folder (or trigger via CLI).  
System parses, intelligently chunks (respecting structure), embeds, indexes with rich metadata (source file, date, tags if present, project/context), and stores.

### 2. Query + Synthesis Flow (Main Flow)
1. User asks a natural language question.
2. Planner agent decides retrieval strategy and routing.
3. Retriever(s) pull relevant chunks (hybrid search).
4. Synthesizer builds a coherent, cited answer.
5. Critic agent reviews for quality, grounding, contradictions, and completeness.
6. Present final answer with citations, trace summary, and “Was this useful?” feedback prompt.

### 3. Reflection / Extraction Flow
Trigger (manually or scheduled) a reflection pass over recent notes.  
Agent surfaces:
- Open questions or unresolved items
- Potential tasks or action items
- Interesting connections across notes
- ADHD/productivity-relevant insights (optional, user-controlled)

### 4. Feedback & Improvement Loop
- Rate answer quality or provide corrections.
- System logs feedback for future prompt improvement or few-shot examples.
- Simple version: store corrections locally. Advanced (post-MVP): use for light adaptation.

---

## 6. Technical Architecture (High-Level)

| Component          | Technology / Approach                          | Notes |
|--------------------|------------------------------------------------|-------|
| **Orchestration**  | LangGraph (stateful graphs, persistence, checkpoints) | Core strength area — enables governance and human-in-the-loop |
| **Retrieval**      | Hybrid: Vector store (Chroma / LanceDB / local Weaviate) + metadata + simple graph layer | Prioritize recall + traceability over perfect precision initially |
| **Model Access**   | LiteLLM (flexible providers: Claude, OpenAI, local via Ollama, etc.) | Start with strong reasoning model for synthesis + critic |
| **Ingestion**      | Custom Markdown chunker + Unstructured.io or LlamaParse-style for PDFs | Respect headers, preserve context, add rich metadata |
| **Storage**        | Local files + vector DB (everything stays on-device by default) | Privacy-first |
| **Interface**      | CLI (MVP primary) + optional Streamlit for nicer interaction and trace visualization | Keep UI minimal |
| **Observability**  | Built-in logging + optional LangSmith or local tracing | Track queries, retrieved sources, answers, costs, and feedback |

### Key Design Principles
- **Governance first**: Critic agent + human checkpoints on important outputs.
- **Traceability always**: Every answer must clearly show its sources.
- **Pragmatic determinism**: Use structured outputs (Pydantic) and explicit routing where it reduces nondeterminism.
- **ADHD-friendly defaults**: Favor concise, actionable outputs with clear next steps. Avoid dumping too much information.
- **Local-first & private**: Data stays on my machine unless I explicitly route to a cloud model.

---

## 7. Data & Privacy

- **Local-first by default** — nothing leaves the machine unless I choose a cloud model for a specific query.
- Easy isolation between purely personal notes and work-adjacent content (folder-based or tag-based).
- Transparent indexing — I should always be able to see what has been ingested and why.
- Future option for fully offline operation with local models.

---

## 8. Risks & Open Questions

| Risk                          | Mitigation / Notes |
|-------------------------------|--------------------|
| Poor retrieval quality on messy personal notes | Start with strong chunking strategy + metadata; iterate quickly based on real usage |
| Critic agent too conservative or ineffective | Test multiple prompting strategies; keep human override easy |
| Cost creep with frontier models | Use LiteLLM + model routing; add basic cost tracking from day one |
| Inconsistent daily use / ingestion | Design for very low friction ingestion; make reflection flow genuinely useful |
| Scope creep ("just one more agent") | Strict MVP protection — new ideas go to a backlog with clear justification |
| Maintenance burden             | Build only what I will actually use; stop if it stops delivering value |

**Biggest open question**: How good can retrieval + critic combination get on real, unstructured personal notes without massive tuning?

---

## 9. Phasing & Realistic Timeline

**Phase 0 – Foundation** (1 focused weekend)  
- Repo setup, basic ingestion pipeline (Markdown + PDF), vector indexing, simple baseline RAG.

**Phase 1 – Agentic Core** (1–2 weekends)  
- LangGraph multi-agent system (Planner → Retriever → Synthesizer → Critic).  
- CLI interface.  
- Basic tracing and feedback capture.

**Phase 2 – Usability & Reflection** (1 weekend)  
- Streamlit UI (optional but nice).  
- Reflection / extraction agent.  
- Strong README, architecture diagram (Mermaid), decision log, and usage examples.

**Phase 3 – Real-World Iteration** (Ongoing, 3–4 weeks of use)  
- Use daily in real workflows.  
- Log pain points and wins.  
- Iterate on chunking, prompting, critic effectiveness, and output format based on actual experience.

**Target**: Useful, personally valuable MVP within 3–5 focused sessions, assuming disciplined scope control.

---

## 10. Success Criteria

We will consider the MVP successful when:

- I actively prefer using it over current ad-hoc methods for at least one important recurring need.
- I can clearly articulate the architecture, key design decisions, tradeoffs, and real usage learnings (this is the professional/resume value).
- The project feels sustainable because it delivers ongoing personal value, not because it exists only for a GitHub profile.

---

## Appendix: Suggested Next Steps After PRD Approval

1. Finalize project name and GitHub repo.
2. Define detailed agent roles, prompts, and state schema.
3. Create initial repo structure and core ingestion script.
4. Build Phase 0 baseline and test on real personal notes.
5. Iterate from there.

---

*This PRD is intentionally kept tight and actionable. It prioritizes building something I will actually use and can speak about with authenticity over feature completeness.*

**End of PRD v0.1**