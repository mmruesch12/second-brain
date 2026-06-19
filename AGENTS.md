# AGENTS.md — Rules for Building in This Repo

This file is the canonical guide for AI agents and human contributors working on **Personal Agentic Second Brain** (`second-brain`, CLI alias `sb`). Read it before making changes.

**This is a public GitHub repository.** Treat every commit as permanently visible. When in doubt, do not commit.

---

## 1. Canonical References

| Document | Purpose |
|----------|---------|
| [personal-agentic-second-brain-prd-v2.md](./personal-agentic-second-brain-prd-v2.md) | **Source of truth** for scope, architecture, phase gates, and acceptance criteria |
| [README.md](./README.md) | Public project overview |
| [personal-agentic-second-brain-prd.md](./personal-agentic-second-brain-prd.md) | Superseded v0.1 — historical reference only; do not implement from it |
| [.gitignore](./.gitignore) | What must never enter version control |

If implementation conflicts with the v0.2 PRD, follow the PRD or propose an ADR in `docs/adr/` before diverging.

---

## 2. Project Priorities (in order)

1. **Personal daily utility** — features must earn their place through real use, not demo value.
2. **Privacy and local-first defaults** — air-gap by default; cloud is explicit opt-in only.
3. **Retrieval quality before agent complexity** — prove baseline RAG on golden queries before adding orchestration.
4. **Low-friction UX** — brief outputs, fast streaming, bounded rituals, minimal maintenance.
5. **Eval discipline** — measurable gates, not vibes.

**North-star workflow:** `sb weekly` — Friday synthesis in ≤5 minutes with cited bullets. All work should support or not obstruct this.

---

## 3. Security & Privacy — Non-Negotiable

### Never commit

- Personal notes, journals, work documents, or any user corpus
- Vector indexes, embeddings, SQLite/LanceDB data, or ingestion manifests with real paths
- API keys, tokens, passwords, `.env` files, or credential-bearing config
- Query logs, trace files, feedback files, or egress ledgers containing real Q&A
- `actions.md` or other reflection/triage exports
- Screenshots, architecture diagrams, or eval outputs derived from real notes
- Absolute home-directory paths tied to a real user (use `~/notes/...` or `demo/` only in docs)
- Private family names, medical details, employer-confidential content, or other PII in docs or code

### Always use for development & demos

- `demo/` — synthetic corpus only for tests, screenshots, and public artifacts
- `.env.example` — placeholder variable names, never real values
- `eval/golden_queries.yaml` — query text may be realistic but must not embed secrets or private note excerpts in the repo

### Implementation requirements

- **Default stack:** local embeddings + Ollama; block non-loopback embedding endpoints at ingest
- **Cloud calls:** require explicit `--cloud` or per-query consent; log every egress byte to the ledger
- **DataZone enforcement:** `PERSONAL`, `WORK_ADJACENT`, `PUBLIC_DEMO` — retrieval must filter by zone
- **No LangSmith** (or other cloud tracing) on real personal data in MVP
- **Secret scanner** before any off-machine model call
- **Data directory permissions:** `0700` on local data root

Kill switch env var: `SECOND_BRAIN_AIRGAP=1` must hard-block all egress.

**DataZone cloud rules (MVP):**

| Zone | Cloud LLM | Cloud embed |
|------|-----------|-------------|
| `PERSONAL` | Only with explicit `--cloud` | Never |
| `WORK_ADJACENT` | **Hard-fail** (even with `--cloud`) | Never |
| `PUBLIC_DEMO` | Allowed | Allowed |

Hard-stop cloud calls when per-query cost exceeds **$0.05** (PRD §9).

### Golden queries (`eval/golden_queries.yaml`)

**Safe to commit (public):**

- Paraphrased questions with fictional names/places (`Acme Project`, `Project Falcon`)
- Tags: `factual` | `synthesis` | `temporal` | `cross-doc` per PRD
- Optional `source_hint: demo/...` pointing only at synthetic corpus paths
- Minimum 30 queries before Phase 0a code

**Never commit:**

- Verbatim queries copied from real notes
- Employer names, client names, family names, medical/financial specifics
- Queries that only make sense with a private corpus

**Local overlay (gitignored):**

- `eval/golden_queries.local.yaml` — real queries for owner eval
- Merge at runtime via `sb eval --golden-set local|all` (when implemented)

### Repository hygiene (owner, one-time)

- Enable **Secret scanning** and **Push protection** on GitHub
- Enable **Dependabot** alerts when `pyproject.toml` exists
- Optional: require PR reviews before merge to `master` when external contributors appear

---

## 4. Pre-Commit Checklist (Required)

**Always run these checks before staging or committing.** Do not skip because a change "looks small."

### Step 1 — Inspect what changed

```bash
git status
git diff                    # unstaged
git diff --cached           # staged
```

For new files, read them. For binary files, confirm they belong in a public repo.

### Step 2 — Scan for sensitive content

Requires `rg` (ripgrep) **or** use the `grep` fallback below. Regex scan is **necessary but not sufficient**.

```bash
# Block sensitive untracked paths before git add
git status --porcelain | awk '/^\?\?/ {print $2}' | while read -r f; do
  echo "$f" | rg -qi '\.env$|\.env\.|^data/|^inbox/|^\.notes/|\.sqlite|\.lancedb|\.pem$|id_rsa|golden_queries\.(local|private)\.yaml' && \
    echo "STOP: sensitive untracked path: $f" && exit 1
done

PATTERN='api[_-]?key|secret|password|token|bearer |sk-[a-zA-Z0-9]{10,}|ghp_|gho_|xox[baprs]-|BEGIN (RSA|OPENSSH)|@.*\.(local|internal)'

if command -v rg >/dev/null 2>&1; then
  git diff HEAD | rg -i "$PATTERN" || true
  git ls-files | rg -i '^\.env(\.|$)|^(data|inbox|\.notes)/|chroma/|\.lancedb|\.sqlite|query_trace|feedback\.jsonl|^actions\.md$|golden_queries\.(local|private)\.yaml' || true
else
  git diff HEAD | grep -Eai "$PATTERN" || true
  git ls-files | grep -Eai '^\.env(\.|$)|^(data|inbox|\.notes)/|chroma/|\.lancedb|\.sqlite|query_trace|feedback\.jsonl|^actions\.md$|golden_queries\.(local|private)\.yaml' || true
fi
```

If anything matches: **stop**, remove the file from the index (`git rm --cached <file>`), add to `.gitignore` if missing, and rotate any exposed credential.

### Step 2b — Secret scanner (when tooling exists)

```bash
pre-commit run --all-files          # preferred, if hooks installed
# or one-shot:
gitleaks detect --source . --verbose --redact
```

Install hooks: `pip install pre-commit && pre-commit install`

### Step 3 — Confirm .gitignore coverage

Before adding new directories or artifact types, ensure `.gitignore` excludes them. Common additions that must stay ignored:

- `data/`, `inbox/`, `.notes/`, `chroma/`, `.lancedb/`, `*.db`, `logs/`, `traces/`
- `.env`, `.env.*`, `.venv/`, `eval/results/`, `actions.md`
- `eval/golden_queries.local.yaml`, `eval/golden_queries.private.yaml`

### Step 4 — Run tests

**Skip until `pyproject.toml` and a test suite exist.**

```bash
test -f pyproject.toml && pytest || echo "skip: no test suite yet"
```

Target: <2 min locally. Do not commit if tests fail unless the failure is documented and intentional (rare).

### Step 5 — Review commit scope

- One logical change per commit
- No drive-by refactors unrelated to the task
- No new markdown unless: (a) the user asked, (b) PRD spec gate / phase requires it (ADRs, `docs/problem-evidence.md`, decision log), or (c) updating existing docs per §9
- Commit messages: complete sentences, explain *why*, not just *what*

### Step 6 — Final gate

Ask: **Would I be comfortable if this commit appeared on the front page of Hacker News?**

If no → fix before committing.

---

## 5. Build Sequence & Scope Rules

Follow the PRD phase order. Do not skip gates.

| Phase | Build | Do not build yet |
|-------|-------|------------------|
| **0a** | MD ingest, LanceDB, local embeddings, `baseline_rag`, golden eval harness, `sb query` | LangGraph, verifier, reflection, Streamlit |
| **0b** | PDF T0/T1, `sb capture`, inbox flow | OCR, cloud PDF parsers |
| **1** | Metadata filters, wikilinks, heuristic router, zone enforcement, `brief` profile | LangGraph, verifier, reflection |
| **2** | Citation verifier (async), `sb morning\|prep\|weekly`, streaming | Streamlit, LangGraph |
| **3** | Bounded `sb reflect`, `actions.md` export | Scheduler, inferential insights |
| **4+** | LangGraph, Streamlit, OCR — **only if gated** | — |

### Agent / LLM discipline

- Default query path: **max 2 LLM calls** (synthesize + optional verify)
- No LLM planner in MVP — use heuristic router
- **LangGraph only when** all three PRD §9 *LangGraph Gate (when to adopt)* criteria are met and documented in an ADR
- Immortal `baseline_rag` must exist; new features must beat it on golden eval before merging
- Defer: Streamlit, LLM entity graph, cloud embeddings, multi-agent retrieval, long-term chat memory

### Spec gate (before Phase 0a code)

Do not start implementation until:

- [ ] `docs/problem-evidence.md` (per PRD §4: top 3 tasks, workarounds, 10 manual queries)
- [ ] `docs/data-zones.md` — path → DataZone mapping table
- [ ] `eval/golden_queries.yaml` (30+ public-safe queries; see §3 golden queries policy)
- [ ] `docs/adr/001-vector-store-and-models.md`
- [ ] `docs/adr/002-chunking-contract.md`
- [ ] `.secondbrainignore` documented in README or ADR
- [ ] `.env.example` with placeholder keys (no values)
- [ ] `demo/` synthetic corpus exists

---

## 6. Architecture & Code Conventions

### Frozen stack (Phase 0 — change only via ADR)

| Component | Choice |
|-----------|--------|
| Language | Python 3.12+ |
| Vector store | LanceDB |
| Embeddings | Local (`nomic-embed-text` or equivalent) |
| LLM default | Ollama |
| LLM abstraction | LiteLLM (`config/models.yaml`) |
| PDF | `pymupdf` / `pdfplumber` (local) |
| Orchestration | Plain functions → LangGraph when gated |
| CLI | `typer` or `click`; entry point `sb` (freeze in ADR-001; prefer `typer` until decided) |
| Schemas | Pydantic models with tests |

Preserve MIT license headers; document new dependencies' licenses in `pyproject.toml` metadata.

### User-facing failures (implement per PRD §14)

Do not invent new error copy. Match PRD §14 for: empty retrieval, verifier timeout, secret-detected pre-egress, cloud without consent, PDF parse fail, cost cap exceeded, zone mismatch.

### Data contracts (implement as typed models, not ad-hoc dicts)

- `DocumentMetadata`, `Chunk`, `SynthesisResponse`, `TraceRecord`
- Chunking: H1–H3 aware, 400–800 tokens, 80-token overlap, atomic code blocks
- Citations must include `source_path`, `chunk_id`, and quote span

### Code quality

- Match existing style in the file you edit
- Prefer extending existing functions over parallel implementations
- No verbose comments on obvious code; no drive-by cleanup
- Every diff line should serve the task
- Pin dependencies in `pyproject.toml` with a lockfile

### CLI contract

Respect the command surface in PRD Appendix A. Global flags: `--zone`, `--cloud`, `--profile`, `--debug`, `--json`, `--since`.

Output default: `brief` profile (≤5 bullets + 1 next action). Full trace only with `--debug`.

---

## 7. Testing Requirements

| Layer | Required for |
|-------|--------------|
| Unit tests | Chunker, metadata parser, zone filter, citation validator |
| Integration tests | Ingest → retrieve (mocked embeddings) |
| Regression | Golden-query harness |
| Privacy tests | Cross-zone leak tests (zero tolerance), egress ledger writes |
| Smoke | `sb doctor` health checks |

Add tests with every feature. Golden eval results go to `eval/results/` — **gitignored**, never committed.

---

## 8. Observability & Logging

- Local JSONL traces only for MVP
- Store `chunk_id` references in logs, not raw note text (when possible)
- Encrypt query/trace logs at rest when storing raw query text (PRD §10)
- Query log TTL: 90 days
- User mode hides cost/trace; dev mode requires `--debug`
- Never configure LangSmith, Sentry, or other cloud telemetry with real note content

---

## 9. Documentation Rules

- Do not create markdown files unless: (a) the user asked, (b) PRD spec gate / phase requires it (ADRs, `docs/problem-evidence.md`, decision log), or (c) updating existing docs
- Public screenshots and README examples use `demo/` data only
- ADRs go in `docs/adr/` with format: context, decision, consequences
- Update README only when project status or entry points materially change

---

## 10. What to Do When Unsure

| Situation | Action |
|-----------|--------|
| Feature not in PRD v0.2 | Do not build; add to backlog with justification |
| Need real notes to test | Use local files outside repo; never commit them |
| Cloud API seems easier | Default local; document tradeoff in ADR if proposing cloud |
| LangGraph feels necessary | Write ADR citing golden-eval evidence first |
| Sensitive file staged accidentally | `git rm --cached`, fix `.gitignore`, rotate secrets if applicable |
| Golden eval regresses | Fix before merging; do not lower thresholds silently |
| Golden eval below PRD kill threshold (<5/10 beat workaround) | Pause new agents; retrieval-only fixes per PRD §11 |
| No daily use by Phase 3 week 4 | Shrink scope per PRD kill criteria; do not add UI/agents |

---

## 11. Commit & Push Policy

- **Never** commit on the user's behalf without running the pre-commit checklist (Section 4)
- **Never** push secrets or personal data — this repo is public at `github.com/mmruesch12/second-brain`
- Prefer small, reviewable commits over large dumps
- Default branch: **`master`**. Target PRs and CI at `master`
- Do not force-push `master` without explicit user request
- Do not amend or rebase commits the user already pushed unless asked

### Agent commit delegation

- Commit only when the user explicitly asks, or when completing a delegated task that included "implement and commit"
- Doc-only changes: still run Step 2 secret scan; Steps 4–5 may be abbreviated
- Code/eval/config changes: full checklist mandatory

### External contributions (fork PRs)

- PRs must not include personal corpora, real golden queries, or `.env` files
- CI runs secret scanning on PR diffs (`.github/workflows/secret-scan.yml`)
- Maintainers: reject PRs that add binary DB/index files or home-directory paths
- Forks inherit public visibility — treat fork default branch same as upstream

Suggested commit message shape:

```
Short imperative summary (≤72 chars)

Explain why the change is needed and any tradeoffs. Note privacy/eval
impact if relevant.
```

---

## 12. Quick Reference — Red Flags in `git diff`

Stop and fix if you see any of these:

- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or similar assignments
- Bearer tokens, JWTs, private keys
- Paths like `/home/<user>/...` or `/Users/<user>/...` with real note content in code or fixtures (use `demo/notes/sample.md` instead)
- Whole note bodies in test files (use minimal synthetic fixtures in `demo/`)
- LanceDB/Chroma/SQLite binary paths added to git
- Real names, employers, or family details in docs beyond the public project owner credit
- LangSmith / cloud tracing wired without opt-in and redaction
- Automatic cloud model routing without `--cloud`

---

*When building: retrieval first, privacy by default, eval before agents, check before commit.*