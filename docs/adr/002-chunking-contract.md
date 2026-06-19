# ADR 002: Chunking Contract

**Date:** 2026-06-19  
**Status:** Accepted  
**Context:** Spec Gate (pre-Phase 0a)

## Context

The project requires a deterministic, structure-preserving chunking strategy for Markdown (and later PDF) documents before any retrieval or synthesis can succeed. Per PRD §8 (Data Contracts) and AGENTS.md §6 (Frozen stack + Spec gate), the chunking contract must be defined and justified before Phase 0a implementation code.

Evidence from `docs/problem-evidence.md` shows recurring failure modes caused by poor chunking in current tools:

- Important details live in sub-bullets or code snippets under H3s; plain search or LLM paste loses hierarchy.
- Critical context lives inside fenced code blocks or tables that simple chunkers split or ignore.
- The decisive decision lived under an H2... heading context was not preserved.
- Performance numbers lived inside code fences and tables... because atomic blocks were not respected.
- Discussion split across a design spike note (code block with options)...

These directly impact the north-star `sb weekly` workflow (cited synthesis across notes) and the golden-query set (which includes queries relying on heading structure, atomic code/tables, and cross-chunk context).

PRD §8 explicitly defines Chunking Contract v1:

| Rule | Value |
|------|-------|
| Markdown split | H1–H3 aware |
| Target size | 400–800 tokens |
| Overlap | 80 tokens |
| Code blocks | Atomic (never split) |
| Metadata per chunk | `heading_path`, `chunk_index`, `source_line_range` |
| PDF | Section-aware via local parser; fallback fixed window |

All contracts implemented as Pydantic models with tests. Citations must include `source_path`, `chunk_id`, and quote span.

Current state: ADR-001 (vector/models) accepted. No implementation code yet. Golden queries (35) and problem-evidence exist to validate the contract later.

Alternatives considered:
- Naive fixed-size or sentence splitters: lose heading hierarchy and structure (proven failure in evidence).
- RecursiveCharacterTextSplitter (LangChain default): often splits code blocks and tables; insufficient H1–H3 awareness without heavy customization.
- Whole-document or paragraph-only: leads to either too-large contexts (poor retrieval) or loss of atomic sections.
- Token-only without structure: fails the "heading_path" and "atomic code" requirements for traceable synthesis.

## Decision

Adopt **exactly** the Chunking Contract v1 from PRD §8 as the frozen contract for Phase 0 (changes only via future ADR with golden-eval evidence):

- **Markdown split:** H1–H3 aware  
  Split primarily on headings, preserving the full heading path for each chunk (e.g., "# Project X > ## Risks > ### Mitigation"). This ensures context is not lost for sub-sections.

- **Target size:** 400–800 tokens  
  Aim for chunks in this range to balance context richness with retrieval precision (vector search works better on focused passages).

- **Overlap:** 80 tokens  
  Fixed overlap between adjacent chunks to handle information that straddles boundaries (e.g., a sentence that continues across a heading or list).

- **Code blocks:** Atomic (never split)  
  Fenced code blocks (```...```), tables, and similar atomic content units must remain entirely within one chunk. This directly addresses multiple documented failure modes.

- **Metadata per chunk:**  
  - `heading_path`: full ancestor heading chain (string or list)
  - `chunk_index`: position within the document
  - `source_line_range`: original line numbers (start, end) for traceability and quote spans

- **PDF handling:** Section-aware via local parser (pymupdf/pdfplumber); fallback to fixed window only when structure is absent.

The chunker will produce `Chunk` objects (Pydantic) containing content + this metadata. `DocumentMetadata` will also carry overall parse info.

This contract will be implemented in Phase 0a (after full spec gate), with unit tests. It is the foundation for `baseline_rag`, citations, and eval scoring on grounding + citation precision.

## Consequences

**Positive:**
- Directly solves the structure-loss problems documented in problem-evidence.md.
- Enables high-quality citations: every synthesized claim can point to `source_path` + `chunk_id` + quote span + heading_path.
- Improves retrieval quality for the golden set (many queries rely on H2/H3 context, code snippets, tables).
- Predictable, testable behavior — easier to debug retrieval failures.
- Consistent with PRD §8 and AGENTS.md frozen requirements.
- Lays groundwork for wikilink expansion and metadata filters in Phase 1.

**Negative / Trade-offs:**
- More complex chunker implementation than naive splitters (must parse Markdown headings, detect atomic blocks, track line numbers and heading stacks).
- Fixed token targets + overlap may produce slightly uneven semantic chunks in some documents; mitigated by later eval-driven tuning (only after baseline is immortal).
- Requires token counting (tiktoken or equivalent) during chunking — acceptable local dependency.

**Risks & Mitigations:**
- Poor chunk quality on real messy notes: Mitigated by golden-query eval + rubric (Grounding, Citation precision). If baseline underperforms, iterate retrieval/chunking before adding agents (per PRD kill criteria).
- Edge cases in Markdown (nested lists, mixed code+text): Will be exercised by the `demo/` corpus (required before Phase 0a) and unit tests.
- Token counting variance across models: Use a consistent tokenizer for chunking decisions; document it.

**Next steps (post this ADR):**
- Complete remaining spec gate items (.secondbrainignore, .env.example, demo/).
- Implement chunker + Pydantic `Chunk` / `DocumentMetadata` models (with tests) in Phase 0a.
- Use the contract in ingest pipeline and baseline_rag.
- Run golden queries on demo corpus and record baseline scores.

This ADR is required by AGENTS.md §5 and the autonomous loop prompt before Phase 0a code. It will be referenced by the chunker implementation and future retrieval work.

**References:**
- PRD §8 Data Contracts (exact table)
- AGENTS.md §6 (Chunking: H1–H3 aware, 400–800 tokens, 80-token overlap, atomic code blocks)
- `docs/problem-evidence.md` (failure modes 1,4,8 and implications section)
- ADR 001 (for overall frozen stack context)
- Golden queries (queries relying on headings, code, tables)