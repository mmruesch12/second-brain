# Problem Evidence

**Source:** PRD §4 — required before Phase 0a.  
**Purpose:** Document recurring knowledge work pain points, current workarounds, and concrete failure modes of ad-hoc search. This grounds the need for structured chunking, hybrid retrieval (vector + metadata + structure), DataZone enforcement, and the north-star `sb weekly` workflow. All scenarios are generalized and use fictional names/projects only.

## Top 3 Recurring Knowledge Tasks

### 1. Weekly synthesis / Friday recap
- **Typical time today:** 25–45 minutes of manual hunting + context reconstruction.
- **Description:** Pull key decisions, open questions, and cross-team updates from the prior week across meeting notes, research spikes, and project logs.
- **Failure modes:**
  - Notes from different days use inconsistent heading styles, so keyword search misses context.
  - Important details live in sub-bullets or code snippets under H3s; plain search or LLM paste loses hierarchy.
  - Recent updates to older notes (e.g., status changes) are not surfaced because recency + content change signals are weak.
- **Impact:** Delayed or incomplete handoff to next week; repeated questions in standups.

### 2. Pre-meeting / decision prep ("What did we say about X?")
- **Typical time today:** 10–20 minutes per meeting, often repeated for the same topic.
- **Description:** Locate prior discussions, commitments, constraints, and alternatives for a specific topic (project, vendor, architecture choice) before a sync.
- **Failure modes:**
  - Related notes scattered across personal, work-adjacent, and project folders; no unified view.
  - Wikilinks or "see also" references are present but not followed automatically.
  - Chronological order is lost; the decisive meeting note is buried under later status updates.
- **Impact:** Repeating context in meetings; risk of contradicting prior decisions.

### 3. Cross-document synthesis on a theme (research, risk, planning)
- **Typical time today:** 30–60+ minutes when doing deeper work.
- **Description:** Connect insights from research notes, experiment logs, customer feedback, and architecture spikes on the same theme (e.g., "latency issues", "vendor evaluation").
- **Failure modes:**
  - Semantic similarity exists but keyword search fails on synonyms or abbreviations used inconsistently.
  - Critical context lives inside fenced code blocks or tables that simple chunkers split or ignore.
  - No reliable way to filter by project tag + time window + zone in one pass.
- **Impact:** Shallow answers; missed connections; time spent re-reading the same files.

## Current Workarounds and Why They Fail

| Workaround | Typical usage | Why it breaks down |
|------------|---------------|--------------------|
| Obsidian / note app full-text search | Quick keyword or tag lookup | No structure awareness (headings, code blocks); no date-aware ranking; no cross-folder synthesis; results are flat lists without provenance for synthesis. |
| rg / grep in terminal | Precise string matches across repo | Loses heading context and document structure; hard to combine with semantic intent; manual date filtering; no citations for downstream use. |
| Copy-paste excerpts into ChatGPT / LLM | "Summarize these notes about Project Falcon" | Loses source traceability; risk of hallucinated connections; no zone enforcement; every query risks leaking more context than intended; non-repeatable. |
| Manual inbox + dated filenames | Capture then file by hand | Inconsistent naming and tagging; search relies on memory of dates/folders; backlog grows; no automated chunking or indexing. |
| Browser bookmarks + separate docs | Research + reference | Context split across tools; no unified query surface; retrieval friction high for anything older than a week. |
| "I know it's in my notes somewhere" + re-asking colleagues | Social + personal memory | Scales poorly; error-prone; creates interruptions; knowledge is lost when people change teams. |

These workarounds are sufficient for single-file lookup but fail systematically on the north-star workflow (cited weekly synthesis) and on cross-document or temporal questions.

## 10 Manual Query Failure Examples

These are representative queries that would be run against real notes today. Each records the intent and the specific failure mode observed with current tools. (Fictional projects/names used.)

1. **"What were the final constraints we agreed on for the Acme Q3 launch?"**  
   Failure: The decisive decision lived under an H2 in a meeting note from 3 weeks ago that was later edited with status updates. rg found the word "constraints" in three other files; the actual agreement was missed because the heading context was not preserved in search results.

2. **"Summarize risks mentioned for the Falcon site migration last month."**  
   Failure: Two notes used "Falcon" as a tag and another used "site migration". Keyword search caught some but missed a table in an older research note that used "migration to Falcon" in a list item. No single pass combined semantic + metadata (date + tag).

3. **"Did Jordan commit to owning the latency investigation for the reporting pipeline?"**  
   Failure: The commitment was in a sub-bullet under "Action items" in a sync note. Plain search found Jordan's name many times; the specific ownership was not highlighted and date context was lost.

4. **"What alternatives were considered for the auth library before we picked X?"**  
   Failure: Discussion split across a design spike note (code block with options) and a later retro note. The code block was ignored or mangled by simple text search; the link between the two notes was only a casual "see earlier spike".

5. **"Find all notes tagged with Project Phoenix from the last 14 days that mention customer feedback."**  
   Failure: Tags were inconsistent (`#phoenix`, `Project Phoenix`, frontmatter tags). No reliable date + tag + keyword filter that also respected folder zones.

6. **"What open questions remain from the vendor evaluation work?"**  
   Failure: Open questions scattered in 4 different notes under varying headings ("Next steps", "Questions", "TODO"). Manual collection missed one; no structured extraction.

7. **"How did the decision on weekly demos for the internal tool get reversed?"**  
   Failure: The reversal was noted in a status update that referenced an older meeting note via a wikilink. The wikilink was not followed; search only showed the latest note.

8. **"List concrete examples of slow query performance we logged in April."**  
   Failure: Performance numbers lived inside code fences and tables. Standard search tools returned surrounding prose but dropped the actual measurements because atomic blocks were not respected.

9. **"What did the remote team say about documentation debt during the last planning cycle?"**  
   Failure: Notes lived in a work-adjacent folder. A personal search accidentally mixed in unrelated personal notes with similar keywords; no zone separation.

10. **"Give me a one-paragraph brief on the current state of the observability initiative."**  
    Failure: Current state was updated piecemeal across three notes (kickoff, mid-point check, recent experiment). No single source of truth; manual assembly took >15 min and still missed one update.

## Implications for the System

These examples show recurring needs that a plain full-text index or ad-hoc LLM paste cannot reliably meet:

- **Structure-aware chunking:** H1–H3 aware splits with atomic code/tables (PRD §8).
- **Rich metadata + filters:** dates, tags, wikilinks, source_path, data_zone (PRD §8, §10).
- **Hybrid retrieval:** vector for semantics + metadata + structure (wikilink expansion).
- **Traceable synthesis:** every claim must cite specific `source_path` + `chunk_id` + quote span.
- **Zone enforcement** at retrieval time.
- **Low-friction rituals** that produce cited, concise output (`sb weekly`, `sb prep`).

Documenting these before any code ensures we build retrieval that actually beats the documented workarounds on the golden query set.

**Next after this artifact:** Continue spec gate (data-zones.md, golden_queries.yaml, ADRs, etc.). No Phase 0a code until checklist is 100% green and logged.
