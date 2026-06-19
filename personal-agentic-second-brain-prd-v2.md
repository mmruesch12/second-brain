# PRD: Personal Agentic Second Brain

**Project Name (Working Title):** Personal Agentic Second Brain  
**CLI / package name (frozen for Phase 0):** `second-brain` (`sb` alias)  
**Version:** 0.2 (consensus-hardened MVP)  
**Date:** June 19, 2026  
**Owner:** Matt Ruesch  
**Status:** Draft — approved for Phase 0 after spec gate items below are checked  
**Supersedes:** `personal-agentic-second-brain-prd.md` (v0.1)

---

## 0. What Changed in v0.2

This revision incorporates adversarial review from five lenses (PM, architect, UX, privacy, implementation realism). Consensus themes:

| Theme | v0.1 problem | v0.2 resolution |
|-------|--------------|-----------------|
| Dual mandate | Personal utility vs. interview demo pulled in opposite directions | **Personal utility is primary**; demo artifacts ship only after daily use is proven |
| Build sequence | LangGraph + 4 agents before retrieval proven | **Retrieval-first**: baseline RAG → eval → optional verifier → LangGraph only if earned |
| Success metrics | 70% self-assessed, unfalsifiable | **Golden-query eval set + rubric**; self-assessment is supplemental |
| Privacy | "Local-first" with cloud as implicit default | **Air-gap by default**; explicit `--cloud` with egress ledger |
| UX | Principles without acceptance criteria | **Brief-by-default**, fast-path streaming, bounded rituals, inbox capture |
| Scope | Graph layer, PDF, Streamlit, reflection all in early phases | **Deferred or narrowed** with explicit phase gates |
| Spec gaps | Chunking, metadata, state schema deferred | **Data contracts and ADRs required before Phase 1** |

---

## 1. Vision

Build a governed, personal knowledge operating system that ingests scattered notes, research, ideas, and documents, then lets me query, synthesize, and act on that information with strong traceability, optional verification, and human oversight.

The goal is to reduce cognitive load and context-switching friction in a life with high demands (work leadership, family, home projects, creative work). This should feel like an extension of my thinking — not another system I have to maintain.

**Priority rule (resolves dual mandate):** Personal daily value gates every feature. Interview/resume value comes from *honest tradeoffs, eval discipline, and real usage learnings* — not agent count or demo polish. Public artifacts (architecture diagrams, trace screenshots) use a **synthetic demo corpus** only; never real personal notes.

---

## 2. North-Star Workflow

MVP validation traces to **one** recurring workflow:

> **Friday weekly synthesis** — From notes ingested that week, produce a cited, ≤5-bullet summary of key themes, open questions, and next actions in under 5 minutes.

All phase gates, golden queries, and acceptance tests prioritize this workflow. Other flows (meeting prep, task extraction) are stretch goals after the north-star works 4 consecutive weeks.

### Starter Rituals (opinionated defaults)

Ship 3 CLI rituals to collapse decision fatigue:

| Command | Purpose |
|---------|---------|
| `sb morning` | 3 bullets: what matters today (from last 48h notes) |
| `sb prep <topic>` | Cited brief for upcoming meeting/decision |
| `sb weekly` | Bounded reflection digest (north-star workflow) |

First-run wizard forces picking one default ritual for 14 days.

---

## 3. Goals & Success Metrics

### Primary Goals

- Make it dramatically easier to find, connect, and synthesize information across personal and professional notes.
- Provide reliable, cited answers with clear provenance.
- Surface actionable insights without overwhelming output.
- Demonstrate thoughtful agentic patterns *only where they earn their cost*.

### Success Metrics (MVP — falsifiable)

**A. Golden-query eval (objective, weekly)**

- 30–50 real queries in `eval/golden_queries.yaml` before Phase 0 code.
- Each query tagged: `factual` | `synthesis` | `temporal` | `cross-doc`.
- **Useful Answer Rubric** (score 1–3 per dimension, max 15):

| Dimension | What it measures |
|-----------|------------------|
| Grounding | Claims supported by retrieved chunks |
| Citation precision | Claims map to correct sources |
| Completeness | Answers the question asked |
| Concision | Concise, low-friction; no dump |
| Actionability | Clear next step when applicable |

- **Gate:** ≥70% of golden queries score ≥10/15 before Phase 3 (daily use).
- **Gate:** Agentic features must beat immortal `baseline_rag` by ≥10% on rubric or grounding dimension.

**B. North-star workflow (behavioral)**

- `sb weekly` completed 4 consecutive Fridays with self-rated ≥ useful.
- Wall-clock ≤5 minutes end-to-end.

**C. UX (operational)**

- p95 time-to-first-token **<3s** (streamed).
- Default output profile `brief` ≤5 bullets + 1 next action.
- Maintenance budget ≤5 min/week (auto-ingest; health report only on anomalies).

**D. Privacy (verifiable)**

- Zero unintended egress events during Phase 3 (reviewed via `sb audit egress --since 7d`).
- Cloud calls require explicit `--cloud` or per-query consent.

**E. Supplemental (subjective)**

- Self-assessed usefulness after 2–3 weeks of real use.
- "I reach for `sb` before Cmd+F / ad-hoc search" — logged first week.

---

## 4. Problem Evidence (required before Phase 0)

Add to `docs/problem-evidence.md`:

1. Top 3 recurring knowledge tasks (time spent today, failure modes).
2. Current workarounds (Obsidian search, grep, paste-into-ChatGPT, etc.) and why they fail.
3. 10 manual queries on real notes *before* building agents — record where search fails.

This justifies hybrid retrieval scope and prevents solution-first building.

---

## 5. Target Users

- **Primary:** Matt Ruesch (single user for MVP).
- **Future consideration:** Light multi-user or shared family knowledge — explicitly out of scope for v1.

---

## 6. MVP Scope (Ruthlessly Prioritized)

### In Scope for v1

**Ingestion & index**

- Local-first ingestion: **Markdown first** (Phase 0a), **text-native PDF** second (Phase 0b).
- Inbox-first capture: `sb capture "..."` + drop-folder sync; metadata classification *after* capture.
- Incremental ingest: content-hash IDs, tombstone on delete, `.secondbrainignore`.
- Chunking Contract v1 (see §8).
- Metadata Schema v1 with enforced `DataZone` (see §10).

**Retrieval**

- Vector similarity + metadata filters (path, date, tags, zone).
- **MVP graph = extracted structure only:** wikilinks, heading hierarchy, frontmatter tags — no LLM entity extraction.
- 1-hop link expansion at query time (optional boost, not separate agent).

**Query pipeline (retrieval-first)**

- Phase 0–1: `retrieve → synthesize` (max 2 LLM calls).
- Phase 2: optional **citation verifier** (critic v1 = grounding check only).
- LangGraph orchestration **only when gated** (see §12) — not Phase 1 default.

**Interface**

- CLI primary with interactive `sb` picker (recent queries, default ritual, capture).
- Output profiles: `brief` (default) | `standard` | `audit`.
- Progressive disclosure: headline → sources → trace (trace hidden unless `--debug`).

**Verification & governance**

- Fast path: stream answer immediately; verifier runs async or on `--verify`.
- Human-in-the-loop MVP = **Tier 0 only:** post-answer thumbs + optional correction (sparse, not every query).
- Structured cited responses via Pydantic `SynthesisResponse` schema.

**Reflection (bounded)**

- `sb reflect --days 7 --max-items 3` — explicit window, capped digest.
- Each item: one-tap actions (snooze / done / trash) + mandatory citation.
- No scheduler in MVP; no inferential productivity insights — pattern observations grounded in quoted text only.

**Observability**

- Local JSONL trace per query (`trace_id`, chunks, model, tokens, cost, latency, rubric).
- User mode (default) vs dev mode (`--debug` shows full trace).
- LangSmith **out of scope** for real personal data in MVP.

**Privacy & security (MVP requirements)**

- Air-gap default: local embeddings + local LLM (Ollama).
- Egress ledger for every off-machine byte.
- Secret scanner pre-egress; zone enforcement at retrieval.
- `sb purge <path>` with end-to-end verification.

### Explicitly Out of Scope for MVP

- Multi-user / sharing.
- Voice interface.
- Long-term conversational memory across sessions (persistence = trace replay / resume only).
- LLM-extracted knowledge graph / entity extraction.
- Scanned PDF / OCR (Tier 2 — backlog).
- Cloud PDF parsers (LlamaParse, etc.) — opt-in post-MVP only.
- Streamlit / polished UI (defer to Phase 4+ if daily CLI use proven).
- LangSmith or cloud tracing on real data.
- Complex external automations (GitHub issues, calendar, etc.).
- Email/Slack ingestion, mobile app, browser extension, plugin ecosystem.
- Auto-sync from cloud note apps.
- Numeric confidence scores (use discrete `HIGH` / `MEDIUM` / `LOW` + source coverage).
- Planner/Router LLM agent (heuristic router in MVP).

### Agent Count Non-Goal

No more than **2 LLM-calling steps** in the default query path for v1 (`synthesize` + optional `verify`). Additional LangGraph nodes require documented eval proof baseline cannot match.

---

## 7. Core User Flows

### 7.1 Capture + Ingestion

1. **Quick capture:** `sb capture "thought"` → lands in `inbox/` as timestamped Markdown.
2. **Bulk ingest:** Drop files into watched folder or `sb ingest <path>`.
3. System assigns `DataZone` from path mapping; user can override at ingest.
4. Parse → chunk (per contract) → embed (local) → index with metadata manifest.
5. Classification agent *suggests* tags/project **after** capture; one-click confirm. Never required at capture time.
6. Notify when indexed (target: <60s for single capture).

### 7.2 Query + Synthesis (fast path default)

1. User asks question (or runs ritual command).
2. Heuristic router applies: zone filter, temporal `--since`, retrieval params. No LLM planner in MVP.
3. Hybrid retriever: vector top-k → metadata filter → optional 1-hop wikilink expansion → rerank.
4. Synthesizer streams `brief` answer with citations (Pydantic schema).
5. **Async** (unless `--verify`): citation verifier checks grounding; surfaces changes only if verdict differs.
6. Layered output: headline → expand sources → expand trace (`--debug` only).
7. Sparse feedback: occasional thumbs; one-tap "wrong source" on citation.

**Query classes (router, not agents):**

| Class | Path | LLM calls |
|-------|------|-----------|
| `LOOKUP` | retrieve + template format | 0–1 |
| `SYNTHESIS` | retrieve + synthesize | 1 |
| `VERIFY` | + async/sync verifier | 2 |

`sb quick` skips verifier. `--verify` runs verifier synchronously.

### 7.3 Reflection (bounded)

1. `sb reflect --days 7 --max-items 3 [--zone personal]`
2. Select notes by `modified_at` in window (cap 50 notes processed).
3. Output structured JSON: `{tasks[], open_questions[], connections[]}` — each item cited.
4. Human triage: snooze / done / trash. Export to `actions.md` with dedupe.

### 7.4 Feedback & Improvement

- `feedback.jsonl`: `trace_id`, `rating`, `correction_text`, `timestamp`.
- Corrections off by default for cloud-routed queries.
- Weekly optional review of bad answers → promote to few-shot examples (manual, Phase 3+).

---

## 8. Data Contracts (required before Phase 1)

All contracts implemented as Pydantic models with tests.

### Chunking Contract v1

| Rule | Value |
|------|-------|
| Markdown split | H1–H3 aware |
| Target size | 400–800 tokens |
| Overlap | 80 tokens |
| Code blocks | Atomic (never split) |
| Metadata per chunk | `heading_path`, `chunk_index`, `source_line_range` |
| PDF | Section-aware via local parser; fallback fixed window |

### Metadata Schema v1

```
source_path, content_hash, doc_id, ingested_at, modified_at,
title, tags[], wikilinks[], heading_path, doc_type, data_zone,
embedding_model_version, parse_method, parse_quality
```

### SynthesisResponse Schema

```
answer_markdown, profile (brief|standard|audit),
citations[] (source_path, heading, quote_span, chunk_id),
source_coverage (n_chunks, date_range, files_touched),
confidence (HIGH|MEDIUM|LOW), verifier_verdict?,
trace_id, egress (bool), model_used
```

### Trace Record (JSONL)

```
trace_id, timestamp, query, query_class, data_zone,
retrieved_chunk_ids[], model_calls[], latency_ms,
tokens, cost_usd, verifier_verdict, user_feedback
```

---

## 9. Technical Architecture

| Component | Choice (frozen Phase 0) | Notes |
|-----------|-------------------------|-------|
| **Language** | Python 3.12+ | Pin in `pyproject.toml` / lockfile |
| **Vector store** | LanceDB | ADR-001; Parquet export for rebuild |
| **Embeddings** | Local `nomic-embed-text` (or equiv.) | Block ingest if endpoint non-loopback |
| **LLM default** | Ollama local | Cloud via explicit `--cloud` only |
| **LLM abstraction** | LiteLLM | Config in `config/models.yaml` |
| **PDF** | `pymupdf` / `pdfplumber` (T0/T1) | T2 OCR deferred; cloud parsers opt-in |
| **Orchestration** | Plain functions → LangGraph when gated | Not day-one |
| **Storage** | Local files + LanceDB + SQLite manifests | `0700` on data root |
| **Interface** | CLI (`typer` or `click`) | Interactive `sb` picker |
| **Observability** | Local JSONL | No LangSmith on real data |

### Model Routing Table (MVP)

| Role | Default model tier | Notes |
|------|-------------------|-------|
| Synthesis | Local strong / `--cloud` frontier | Only required LLM for most queries |
| Verification | Local small / cheap | Citation check only in v1 |
| Reflection | Local cheap | Batch; zone-scoped |
| Embeddings | Local only | Never cloud in MVP |

Per-query cost cap: $0.05 when `--cloud` (hard stop). Local reports `$0.00` explicitly.

### LangGraph Gate (when to adopt)

Adopt LangGraph only when **all** are true:

1. Baseline + verifier cannot handle a documented branching case (e.g., human interrupt mid-synthesis, parallel retrieval paths).
2. Golden-query eval shows ≥15% failure mode that structured branching fixes.
3. Agent State Schema (TypedDict/Pydantic) is written and reviewed.

If adopted: start 2-node graph (retrieve → synthesize); max 2 critic iterations; checkpoints for HITL resume only — **not** conversational memory.

---

## 10. Data, Privacy & Security

### Threat Model (§10.1)

| Asset | Threat | MVP mitigation |
|-------|--------|----------------|
| Note content | Cloud API exfiltration | Air-gap default; egress ledger |
| Embeddings | Full corpus leaked at ingest | Local embeddings only |
| Query logs | Sensitive Q&A persisted | Encrypt logs; 90-day TTL; chunk IDs not raw text |
| Work-adjacent notes | NDA / employer exposure | `WORK_ADJACENT` zone; cloud disallowed |
| Ingested secrets | Credentials in notes | Secret scanner + `.secondbrainignore` |
| Checkpoints | State in backups/git | Encrypt; `.gitignore`; exclude from cloud sync |

### DataZone Enforcement

| Zone | Ingest path example | Cloud LLM | Cloud embed |
|------|---------------------|-----------|-------------|
| `PERSONAL` | `~/notes/personal/**` | `--cloud` only | Never |
| `WORK_ADJACENT` | `~/notes/work/**` | Never in MVP | Never |
| `PUBLIC_DEMO` | `demo/**` | Allowed | Allowed |

Retrieval **must** filter by zone unless `--zone all` with explicit warning. Golden-query leak tests: zero cross-zone retrieval.

### Egress Ledger

Append-only: `{timestamp, provider, model, chunk_ids, byte_count, data_zone, user_consent_flag}`.

CLI: `sb audit egress --since 2026-06-01`. Fail closed if ledger write fails.

Kill switch: `SECOND_BRAIN_AIRGAP=1` — hard block all egress.

### Deletion Contract

`sb purge <path>` removes: source chunks, vectors, checkpoint refs, log entries. Acceptance: deleted file → zero vector hits within 60 seconds.

### PDF Metadata Allowlist

Index only: `{source_filename, user_tags, ingest_date, data_zone}`. Strip Author, Creator, embedded paths by default.

---

## 11. Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Poor retrieval on messy notes | High | Chunking contract + golden eval + Phase 1 retrieval-only iteration |
| Over-engineering agents | High | Baseline must beat agents; max 2 LLM steps default |
| Cloud misconfiguration | Critical | Air-gap default; egress ledger; weekly audit |
| Embedding exfiltration at ingest | Critical | Local embeddings; block non-loopback |
| Reflection guilt backlog | High | Max 3 items; snooze/dismiss; opt-in only |
| PDF parse failures | Medium | Tiered PDF; ingest status dashboard; don't block MVP |
| Scope creep | Medium | Backlog with justification; agent count non-goal |
| Timeline slip | Medium | Phase gates; cut Streamlit/graph/cloud before cutting eval |
| Maintenance abandonment | Medium | ≤5 min/week budget; auto-ingest; kill criteria below |

### Kill / Pivot Criteria

- After Phase 0+1: if <5/10 golden queries beat current workaround → pause agents, fix retrieval only.
- If no near-daily use by week 4 of Phase 3 → shrink to static search index or archive.
- If verifier changes answer <10% of time over 50 queries → demote or remove.

**Open question (empirical):** How good can local retrieval + optional verifier get on real unstructured notes without fine-tuning? Answered by golden eval trend line, not speculation.

---

## 12. Phasing & Realistic Timeline

### Phase 0a — Markdown + Baseline (2–3 days)

**Deliverables:** Repo, MD ingest, local embeddings, LanceDB index, `sb query`, immortal `baseline_rag`, golden eval harness.

**Acceptance:**

- 10 MD files ingest → query → ≥3 citations.
- Golden set baseline scores logged.
- `sb ingest --status` shows manifest.

### Phase 0b — PDF + Capture (1–2 days)

**Deliverables:** T0/T1 PDF ingest, `sb capture`, inbox flow, ingest failure dashboard.

**Acceptance:**

- ≥80% of 20-file PDF sample `ok` or `partial`.
- `sb capture` → queryable in <60s.

### Phase 1 — Retrieval Hardening (2–3 days)

**Deliverables:** Metadata filters, wikilink expansion, heuristic router, `brief` output profile, zone enforcement.

**Acceptance:**

- ≥10% rubric or recall uplift vs Phase 0a on golden set.
- Zero cross-zone leaks on leak-test queries.

**Explicit deferrals:** LangGraph, verifier, reflection, Streamlit.

### Phase 2 — Verification + Rituals (1–2 days)

**Deliverables:** Citation verifier (async default), `sb morning|prep|weekly`, fast-path streaming.

**Acceptance:**

- Grounding dimension ≥10% above baseline.
- `sb weekly` completes in ≤5 min on real notes.
- p95 first-token <3s.

### Phase 3 — Reflection + Daily Use (1 weekend + 3–4 weeks)

**Deliverables:** Bounded `sb reflect`, `actions.md` export, weekly eval ritual, decision log.

**Acceptance:**

- 5 manual reflect runs rated useful.
- 4 consecutive `sb weekly` successes.
- 3-week upward rubric trend.

### Phase 4+ — Optional (gated)

- LangGraph (if gate criteria met).
- Streamlit (only if daily CLI use established).
- PDF OCR (Tier 2).
- Cloud model routing improvements with redaction middleware.

**Revised target:** Useful MVP in **6–10 focused days** across Phases 0–2, then 3–4 weeks real-world iteration. Honest estimate replaces v0.1 "3–5 sessions."

---

## 13. Testing Strategy

| Layer | What |
|-------|------|
| Unit | Chunker fixtures, metadata parser, zone filter, citation validator |
| Integration | Ingest → retrieve path (mocked embeddings) |
| Regression | Golden-query harness (weekly; cached retrieval in CI) |
| Privacy | Cross-zone leak tests; egress ledger writes |
| Smoke | `sb doctor` — embeddings, index health, PDF parse stats |

Target: local test suite <2 min.

---

## 14. Failure Mode Catalog

| Failure | User-facing behavior |
|---------|---------------------|
| Empty retrieval | "No indexed content matched." Suggest broader terms + `sb ingest --status` |
| Verifier timeout | Return synthesis with `UNVERIFIED` banner |
| Secret detected pre-egress | Block call; show masked preview; suggest redaction |
| Cloud without consent | Hard fail with `use --cloud to confirm` |
| PDF parse fail | Quarantine file; show in `sb ingest --status` as `failed` |
| Cost cap exceeded | Stop; show spend; suggest local model |
| Zone mismatch | Refuse mixed-zone synthesis; suggest `--zone` |

---

## 15. Success Criteria (MVP complete)

MVP is successful when **all** are true:

1. I actively prefer `sb weekly` over my prior ad-hoc method for Friday synthesis.
2. Golden-query eval ≥70% at ≥10/15 rubric score.
3. Zero unintended egress during 2-week Phase 3 trial.
4. Maintenance ≤5 min/week sustained.
5. I can articulate architecture, tradeoffs, and eval results with authenticity (resume value follows utility, not vice versa).

---

## 16. Spec Gate Checklist (before Phase 0 code)

- [ ] `docs/problem-evidence.md` written
- [ ] `eval/golden_queries.yaml` — 30+ queries
- [ ] ADR-001: LanceDB + local embeddings + Ollama default
- [ ] ADR-002: Chunking Contract v1
- [ ] DataZone path mapping documented
- [ ] `demo/` synthetic corpus for any public artifact

---

## Appendix A: CLI Contract (summary)

```
sb                          # interactive picker
sb capture "<text>"         # quick inbox capture
sb ingest <path>            # bulk ingest
sb ingest --status          # manifest + failures
sb query "<question>"       # default brief profile
sb query --verify "<q>"     # sync verifier
sb quick "<question>"       # skip verifier
sb morning | sb prep <t> | sb weekly   # rituals
sb reflect --days 7 --max-items 3
sb audit egress --since <date>
sb purge <path>
sb doctor                   # health check
```

Global flags: `--zone`, `--cloud`, `--profile`, `--debug`, `--json`, `--since`.

---

## Appendix B: Suggested Next Steps

1. Complete spec gate checklist (§16).
2. Write `docs/problem-evidence.md` and `eval/golden_queries.yaml`.
3. Scaffold repo: chunker tests, ingest CLI, baseline RAG — **no LangGraph**.
4. Run Phase 0a on real Markdown notes; log baseline scores.
5. Iterate retrieval until golden eval gate passes; only then Phase 2+.

---

## Appendix C: Review Consensus Log

Adversarial reviews (June 19, 2026) — 5 lenses, 126 total issues → integrated above.

| Lens | Issues | Top consensus contribution |
|------|--------|------------------------------|
| PM | 22 | Personal utility primary; north-star workflow; cut timeline |
| Architect | 36 | Data contracts; defer graph; eval harness gates Phase 1 |
| UX | 22 | Fast path; bounded reflection; rituals; brief default |
| Privacy | 24 | Air-gap default; egress ledger; zone enforcement |
| Implementer | 22 | Retrieval-first sequencing; baseline immortal; phase gates |

---

*This PRD prioritizes building something I will actually use. Agentic sophistication is earned through eval results, not assumed at kickoff.*

**End of PRD v0.2**