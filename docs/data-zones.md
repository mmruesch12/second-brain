# Data Zones

**Source:** PRD §10 (Data, Privacy & Security) and AGENTS.md §3, §5.  
**Purpose:** Define the DataZone model, default path-to-zone mapping rules, cloud restrictions, retrieval enforcement, and interaction with `.secondbrainignore`. This contract must be implemented in ingest and query paths before Phase 0a code is considered complete. All examples use fictional paths and generalized scenarios only.

## Zone Definitions

| Zone            | Description                                                                 | Example User Paths                  | Cloud LLM          | Cloud Embed | Notes |
|-----------------|-----------------------------------------------------------------------------|-------------------------------------|--------------------|-------------|-------|
| `PERSONAL`      | Purely personal notes, journals, private projects. Highest privacy bar.    | `~/notes/personal/**`, `~/notes/journal/**` | Only with explicit `--cloud` | Never      | Default for most owner content. |
| `WORK_ADJACENT` | Work-related notes under NDA/employer policy or containing sensitive business info. | `~/notes/work/**`, `~/notes/acme-project/**` | **Hard-fail** (even with `--cloud`) | Never      | Zero tolerance for cloud leakage. |
| `PUBLIC_DEMO`   | Synthetic or public-safe content used for demos, docs, screenshots, tests. | `demo/**`, `docs/demo-notes/**`     | Allowed            | Allowed    | Only zone where cloud is broadly permitted for artifacts. |

**Cloud rules enforcement (MVP):**
- `PERSONAL`: explicit user opt-in per call or `--cloud` flag.
- `WORK_ADJACENT`: never allow cloud LLM or embed. Hard stop at ingest/query if attempted.
- `PUBLIC_DEMO`: safe for demo use and golden query source_hints.

## Default Path → DataZone Mapping

Ingestion determines zone from the source path prefix at the time of `sb ingest` or `sb capture`. The mapping is deterministic and recorded in chunk/document metadata (`data_zone` field).

Recommended default root layout (owner configures once):

```
~/notes/
├── personal/          → PERSONAL
│   ├── journal/
│   ├── ideas/
│   └── health/
├── work/              → WORK_ADJACENT
│   ├── acme/
│   ├── falcon-project/
│   └── confidential/
└── shared/            → PERSONAL (or owner override to WORK_ADJACENT)
```

- Prefix matching on the configured "notes root" (default `~/notes` or user `data_root`).
- First matching rule wins (more specific prefixes later in config).
- Inbox items (`inbox/`) default to `PERSONAL` unless explicitly dropped under a work prefix.
- Files outside any mapped prefix: refuse ingest with clear error ("No DataZone mapping for path. Use --zone or configure mapping.") or default to `PERSONAL` with warning (conservative).

### Override Mechanisms (to be implemented)
- Per-ingest: `sb ingest --zone personal <path>`
- Frontmatter in note: `data_zone: WORK_ADJACENT` (parsed at ingest, takes precedence for that doc).
- Config file (future, post spec gate): `config/zones.yaml` or similar for custom roots.

## Retrieval Enforcement

- All retrieval (vector + metadata) **must** filter by the requested zone(s).
- Default: query scoped to caller's active zone(s). User can broaden with `--zone personal,work` or `--zone all` (latter shows explicit warning + audit log entry).
- Heuristic router (Phase 1+) applies zone filter early.
- Cross-zone leakage is a hard privacy failure (see tests in Phase 1: zero-tolerance leak tests on golden queries).
- `sb query --zone public-demo` is allowed for testing/demo scenarios.
- SynthesisResponse and traces must record the effective `data_zone` set used.

## Interaction with `.secondbrainignore`

`.secondbrainignore` (root of repo or notes root) uses gitignore-style patterns. It is consulted **before** zone assignment and chunking:

- Any path matching an ignore rule is **skipped entirely** at ingest time. No metadata, no embedding, no zone assignment.
- This is the primary mechanism for excluding:
  - Secrets, credentials, API keys
  - Large binaries or exports
  - Private subfolders inside a broader zone (e.g. `work/acme/secret-nda/` inside WORK_ADJACENT)
  - Temp or cache files
- Ignored paths do **not** affect zone mapping of sibling files.
- Example `.secondbrainignore` patterns (detailed in separate artifact):

  ```
  **/.env*
  **/secrets/**
  **/*-private.*
  work/*/legal/**
  *.sqlite
  ```

- At query time, ignored content simply does not exist in the index.
- `sb ingest --status` and `sb doctor` should report ignored counts per zone.

## Zone Assignment at Ingest Flow (high level)

1. Resolve absolute path.
2. Apply `.secondbrainignore` → skip if matched.
3. Determine zone from path prefix + any frontmatter override + CLI flag.
4. Reject if zone + cloud model combination violates table above.
5. Write `data_zone` into `DocumentMetadata` and every `Chunk`.
6. Record in manifest.

## Examples (Fictional)

- `~/notes/personal/2026-06-reflections.md` → `PERSONAL` (default, can use `--cloud` only with consent)
- `~/notes/work/falcon-proj/decision-log.md` → `WORK_ADJACENT` (cloud LLM forbidden)
- `demo/corpus/project-phoenix-notes.md` → `PUBLIC_DEMO` (full cloud allowed for eval/screenshots)
- `inbox/capture-20260619.md` → `PERSONAL`
- `~/notes/work/acme/legal/contract-draft.md` (if `work/acme/legal/**` ignored) → skipped, never reaches zone logic

## Implementation Notes (for later phases)

- Zone is part of the core `Metadata` contract (see PRD §8).
- Zone filter must be applied in both vector search and metadata filter layers.
- Audit/egress ledger entries must include `data_zone`.
- Golden queries should include cross-zone leak test cases (tagged appropriately).
- `sb doctor` should surface zone distribution stats.

This document is the contract. Future code (ingest pipeline, router, retriever) must implement against these rules without deviation. Any change requires an ADR + progress log update.

**Status for spec gate:** This fulfills the "DataZone path mapping documented" requirement.
