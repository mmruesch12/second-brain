# ADR 001: Vector Store and Models

**Date:** 2026-06-19  
**Status:** Accepted  
**Context:** Spec Gate (pre-Phase 0a)

## Context

The project requires a local-first, privacy-preserving vector store and embedding/LLM stack for the MVP retrieval pipeline. Per PRD §9 (Technical Architecture) and AGENTS.md §6 (Frozen stack), key decisions must be made before any Phase 0a implementation code. The stack must support:

- Local embeddings only (no cloud by default, block non-loopback).
- Local LLM by default (Ollama), with explicit `--cloud` opt-in only.
- Fast, reliable vector search with metadata filtering (path, date, tags, data_zone).
- Parquet-friendly export for rebuilds/manifests.
- Abstraction layer to allow model swaps without rewriting retrieval/synthesis code.
- Alignment with DataZone rules (PERSONAL/WORK_ADJACENT never use cloud embeddings; PUBLIC_DEMO allows for demos).
- Support for the north-star `sb weekly` and golden-query eval (30+ queries before Phase 0a code).

Current reality: no implementation yet. We have problem-evidence.md, data-zones.md, and eval/golden_queries.yaml (35 public-safe queries). Golden queries will be used to establish immortal `baseline_rag` scores.

Alternatives considered (high-level, not exhaustive):
- Chroma / Weaviate / Qdrant: good but heavier or less Parquet-native for air-gapped rebuilds.
- OpenAI / cloud embeddings + LLM: violates air-gap default and DataZone hard rules for PERSONAL/WORK_ADJACENT.
- Pure SQLite + FTS or BM25 only: insufficient for semantic similarity on messy personal notes.
- Custom HNSW or Annoy on disk: high maintenance, no mature metadata + zone filtering out of the box.
- LangChain vector stores: adds unnecessary abstraction layers before baseline is proven.

## Decision

Adopt the following frozen stack for Phase 0 (change only via subsequent ADR citing golden eval evidence):

- **Vector store:** LanceDB
  - Local, embedded (no server).
  - Excellent Parquet export for manifests/rebuilds.
  - Strong support for metadata filtering (critical for zone, date, path, tags).
  - Lightweight and fast for personal corpus sizes.

- **Embeddings:** Local only (`nomic-embed-text` or equivalent, via sentence-transformers or Ollama embeddings API)
  - Block any ingest if the endpoint is non-loopback.
  - Never cloud for MVP (even with `--cloud` for synthesis).

- **LLM default:** Ollama (local)
  - Default model tier chosen per PRD Model Routing Table.
  - Cloud frontier models allowed **only** with explicit `--cloud` flag + per-query consent + egress ledger.
  - Cost cap: hard stop at $0.05 per query when using cloud.

- **LLM abstraction:** LiteLLM
  - Unified interface for local (Ollama) and optional cloud calls.
  - Config in `config/models.yaml` (to be created in Phase 0a).
  - Enables swapping without touching core retrieval/synthesis.

- **CLI entry point decision (deferred detail):** Prefer `typer` for the `sb` CLI (easy, modern, good help + interactive picker potential) until a follow-up ADR or implementation review decides `click`. Frozen in this ADR as "typer preferred unless evidence against."

This decision is recorded before any code so that:
- Ingest, chunker, `baseline_rag`, and `sb query` can be built against a stable contract.
- Golden eval harness can measure baseline quality.
- DataZone enforcement can be implemented at ingest + retrieval time.

## Consequences

**Positive:**
- Strong privacy/air-gap guarantees from day one.
- Simple local setup (no external services for baseline).
- Metadata + zone filtering is first-class in LanceDB.
- Easy rebuilds and audit via Parquet + manifests.
- LiteLLM gives future flexibility without premature complexity.
- Directly enables immortal `baseline_rag` + eval before any agentic layers.
- Matches PRD frozen stack and AGENTS.md exactly.

**Negative / Trade-offs:**
- LanceDB is less "famous" than Chroma in some circles (but superior for our Parquet + local use case).
- Local embeddings may be slower/lower quality than cloud on first run; we accept this and will measure via golden set (must beat workarounds).
- LiteLLM adds a small dependency; we will pin versions and keep usage minimal (only for the 0-2 LLM calls in default path).
- No graph features in vector store (by design — MVP uses only extracted wikilinks/structure).

**Risks & Mitigations:**
- Local model quality on personal notes: Mitigated by golden-query eval gate before Phase 1. If <5/10 beat current workarounds, pause agents and iterate retrieval only (per PRD kill criteria).
- Egress leaks: Enforced by DataZone rules + secret scanner + `SECOND_BRAIN_AIRGAP=1` + ledger.
- Future model changes: Require new ADR + evidence from eval that baseline is insufficient.

**Next steps (post this ADR):**
- Create `.env.example` (placeholders only).
- Create `.secondbrainignore` (with comments).
- Build `demo/` synthetic corpus exercising headings, wikilinks, code blocks, tables, frontmatter, dates.
- Proceed to Phase 0a scaffolding (pyproject.toml, chunker, etc.) only after full spec gate green + logged.

This ADR is required by AGENTS.md §5 and PRD §16 before Phase 0a code. It will be referenced in code and future ADRs.

**References:**
- PRD §9 Technical Architecture (frozen choices)
- AGENTS.md §6 Frozen stack + §5 Spec gate
- Data zones doc (for embedding rules)
- Golden queries (for eval discipline)