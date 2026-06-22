"""Bounded `sb reflect` per PRD §7.3 Phase 3: extract tasks/open_questions/connections from recent notes (via retrieve since).
Target 1 LLM call (extraction only). Output ReflectionResponse (cited items). Export to actions.md (deduped).
Uses hardened retrieve path. Airgap/empty/err graceful. Cap ~50 notes processed.
No scheduler, no inferences beyond quoted text.
"""

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict
from uuid import uuid4  # explicit, no __import__ hack


from second_brain.models import ReflectionItem, ReflectionResponse
from second_brain.retriever import retrieve, heuristic_router

import litellm  # type: ignore  # top-level like synthesizer/verifier; tests patch "second_brain.reflect.litellm.completion"


def _nice_source_path(sp: str) -> str:
    """Format source_path for *user-facing* citations/actions (relative/demo form).
    Keeps internal storage (abs ok for FS) but prevents /home leaks in output per AGENTS §3.
    Prefer 'demo/...' for demo corpus; else rel to cwd or basename.
    """
    if not sp:
        return "?"
    s = str(sp).replace("\\", "/")
    if "/demo/" in s:
        return "demo/" + s.split("/demo/", 1)[1]
    if s.startswith("demo/"):
        return s
    try:
        p = Path(s)
        cwd = Path.cwd()
        if p.is_absolute():
            try:
                return p.relative_to(cwd).as_posix()
            except Exception:
                return p.name or s.split("/")[-1]
        return s
    except Exception:
        return s.split("/")[-1] or s


def _clean_text_for_item(text: str, max_len: int = 80) -> str:
    """Strip frontmatter + junk; return clean one-line usable text/quote for fallback items (addresses junk in actions)."""
    if not text:
        return ""
    t = text.strip()
    # strip leading yaml frontmatter block if present
    if t.startswith("---"):
        parts = re.split(r"\n---\s*\n", t, maxsplit=2)
        if len(parts) > 1:
            t = parts[-1].strip()
    # take first meaningful sentence/line
    for sep in ["\n\n", ". ", "\n", "  "]:
        if sep in t:
            cand = t.split(sep, 1)[0].strip()
            if len(cand) > 4:
                t = cand
                break
    t = re.sub(r"\s+", " ", t)[:max_len].strip()
    if t and not t.endswith((".", "!", "?", "...")) and len(t) > 8:
        t += "..."
    return t or ""



def _parse_reflect_output(raw: str) -> Dict[str, List[Dict[str, str]]]:
    """Robust parse for local LLM: prefer fenced ```json, else json, else section heuristics.
    Returns {"tasks": [...], "open_questions": [...], "connections": [...] } with items {text, citation, quote}.
    """
    text = (raw or "").strip()
    if not text:
        return {"tasks": [], "open_questions": [], "connections": []}

    # Try fenced json first
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    candidate = m.group(1).strip() if m else text

    # Try direct json
    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            for k in ("tasks", "open_questions", "connections"):
                if k not in data:
                    data[k] = []
            return {k: data.get(k, []) for k in ("tasks", "open_questions", "connections")}
    except Exception:
        pass

    # Fallback: section parse (for weak local models)
    sections: Dict[str, List[Dict[str, str]]] = {"tasks": [], "open_questions": [], "connections": []}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("### tasks") or low == "tasks:" or "tasks" == low:
            current = "tasks"
            continue
        if low.startswith("### open") or "open_questions" in low or "questions" == low:
            current = "open_questions"
            continue
        if low.startswith("### connection") or "connections" in low:
            current = "connections"
            continue
        if current and stripped.startswith(("- ", "* ", "• ")):
            item = stripped[2:].strip()
            # try extract [cite] "quote"
            cit = ""
            quote = ""
            cm = re.search(r"\[([^\]]+?)\]", item)
            if cm:
                cit = cm.group(1).strip()
                item = re.sub(r"\s*\[[^\]]+?\]\s*", " ", item).strip()
            qm = re.search(r'"([^"]+)"', item)
            if qm:
                quote = qm.group(1)
                item = re.sub(r'\s*"[^"]*"\s*', " ", item).strip()
            # cleanup trailing
            item = item.strip(" -:").strip()
            if item or cit:
                sections[current].append({"text": item or "See cited note", "citation": cit or "note", "quote": quote})
    # if nothing, treat whole as one if short
    if not any(sections.values()) and len(text) < 400:
        sections["tasks"].append({"text": text[:200], "citation": "", "quote": ""})
    return sections


def _dedupe_items(existing_text: str, new_items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Simple dedupe: skip if normalized text or citation already in recent actions.md content."""
    if not existing_text:
        return new_items
    ex_norm = existing_text.lower()
    out = []
    for it in new_items:
        t = (it.get("text", "") + " " + it.get("citation", "")).strip().lower()
        if t and t in ex_norm:
            continue
        # improved: require word-ish boundary for loose short (split on non-alnum)
        if len(t) > 8:
            import re as _re
            words = set(_re.findall(r'\w+', t))
            ex_words = set(_re.findall(r'\w+', ex_norm))
            if words and words.issubset(ex_words):
                continue
        out.append(it)
    return out


def _write_actions_md(resp: ReflectionResponse, header_date: str, days: int = 7, out_path: Optional[str] = None) -> str:
    """Append (or create) dated section in actions.md (or provided out_path for test isolation) with checkboxes. Dedupes.
    Uses actual days in header. Returns written path or ''.
    """
    target = Path(out_path) if out_path else Path("actions.md")
    date_str = header_date or datetime.now().strftime("%Y-%m-%d")
    section_header = f"## {date_str} (reflect --days {days})"

    try:
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
    except Exception:
        existing = ""

    # Build items for sections
    def fmt_item(it: ReflectionItem) -> str:
        c = it.citation or "note"
        q = f' "{it.quote}"' if it.quote else ""
        return f"- [ ] {it.text} [{c}]{q}"

    # Dedupe new content
    deduped_tasks = _dedupe_items(existing, [{"text": t.text, "citation": t.citation, "quote": t.quote} for t in resp.tasks])
    deduped_qs = _dedupe_items(existing, [{"text": o.text, "citation": o.citation, "quote": o.quote} for o in resp.open_questions])
    deduped_conns = _dedupe_items(existing, [{"text": c.text, "citation": c.citation, "quote": c.quote} for c in resp.connections])

    if not (deduped_tasks or deduped_qs or deduped_conns) and not resp.note:
        # nothing new and no note, still write header for traceability?
        pass  # fall to write header+empty

    body = []
    body.append(section_header)
    body.append("### Tasks")
    if deduped_tasks:
        for it in deduped_tasks:
            c = it.get("citation", "note")
            q = f' "{it.get("quote","")}"' if it.get("quote") else ""
            body.append(f"- [ ] {it.get('text','')} [{c}]{q}")
    else:
        body.append("- [ ] (none surfaced)")
    body.append("")
    body.append("### Open questions")
    if deduped_qs:
        for it in deduped_qs:
            c = it.get("citation", "note")
            q = f' "{it.get("quote","")}"' if it.get("quote") else ""
            body.append(f"- [ ] {it.get('text','')} [{c}]{q}")
    else:
        body.append("- [ ] (none surfaced)")
    body.append("")
    body.append("### Connections")
    if deduped_conns:
        for it in deduped_conns:
            c = it.get("citation", "note")
            q = f' "{it.get("quote","")}"' if it.get("quote") else ""
            body.append(f"- [ ] {it.get('text','')} [{c}]{q}")
    else:
        body.append("- [ ] (none surfaced)")
    body.append("")
    if resp.note:
        body.append(f"> Note: {resp.note}")
    body.append("")

    new_section = "\n".join(body)
    try:
        if section_header in existing:
            # avoid full dup section header; append anyway? or update in place not for MVP
            # per dedupe, append new dated if rerun
            pass
        with open(target, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n\n"):
                f.write("\n\n")
            f.write(new_section)
        return str(target)
    except Exception:
        return ""


def reflect(
    days: int = 7,
    max_items: int = 3,
    zone: Optional[str] = None,
    since: Optional[str] = None,
    ref_date: Optional[datetime] = None,
    actions_path: Optional[str] = None,
    debug: bool = False,
) -> ReflectionResponse:
    """Bounded reflection per PRD §7.3: retrieve recent (modified_at window via since from router), 1 LLM (or fallback) extract cited tasks/open_questions/connections.
    Cap 50 notes processed (unique sources). Returns model; always side-effects actions export (deduped, with checkboxes).
    Respects airgap (early guard before any retrieve/embed to prevent crash/egress), empty -> empty lists + note.
    Uses hardened retrieve + heuristic_router always (0 LLM for retrieval).
    ref_date for determinism in tests/harness (default 2026-06-21 for demo); actions_path for test isolation.
    Note: query/topic removed (not in PRD/CLI contract for reflect; internal default q only).
    """
    ref = ref_date or datetime(2026, 6, 21)  # demo determinism (harness/tests pass explicit; real use can pass now() or default adjusted)
    eff_since = since or (ref - timedelta(days=days)).strftime("%Y-%m-%d")

    q = "Extract actionable tasks, open questions, and cross-note connections from recent notes. Ground strictly in quoted text."

    # EARLY airgap guard (before router/retrieve/embed to prevent any egress/crash per AGENTS §3 + review)
    airgap = os.getenv("SECOND_BRAIN_AIRGAP", "0") == "1"
    if airgap:
        resp = ReflectionResponse(
            note="Reflection blocked under airgap (SECOND_BRAIN_AIRGAP=1).",
            model_used="airgap-blocked",
        )
        _write_actions_md(resp, ref.strftime("%Y-%m-%d"), days=days, out_path=actions_path)
        return resp

    # Exercise router + retrieve for Phase consistency (past issues avoided)
    rcfg = heuristic_router(q, zone=zone, since=eff_since, limit=50, profile="brief", ref_date=ref)
    eff_zone = rcfg.get("zone") or zone
    eff_lim = min(100, rcfg.get("limit", 50))  # over for chunks, cap notes later
    hits = retrieve(q, limit=eff_lim, zone=eff_zone, since=rcfg.get("since") or eff_since, path_prefix=rcfg.get("path_prefix"), tags=rcfg.get("tags"))

    # Cap 50 notes: unique source_paths (fixed control flow per review)
    seen_sources: set = set()
    capped_hits = []
    for h in hits:
        sp = str(h.get("source_path", ""))
        if sp not in seen_sources:
            if len(seen_sources) >= 50:
                break
            seen_sources.add(sp)
        capped_hits.append(h)
    hits = capped_hits[:50 * 3]  # ~3 chunks/note rough

    if not hits:
        resp = ReflectionResponse(
            note=f"No notes modified since {eff_since} (or empty index).",
            model_used="none",
        )
        _write_actions_md(resp, ref.strftime("%Y-%m-%d"), days=days, out_path=actions_path)
        return resp

    # Build compact context (cite-ready; use nice relative for LLM prompt + output consistency). Limit to keep prompt small.
    context_lines = []
    for h in hits[:30]:  # bound
        sp = _nice_source_path(h.get("source_path", "?"))
        hd = h.get("heading", h.get("heading_path", ""))
        cont = str(h.get("content", ""))[:280]
        context_lines.append(f"[{sp} | {hd}]: {cont}")
    context = "\n\n".join(context_lines)

    # Prompt: force structured, cited, 1-line items, max_items cap, only from context
    system = (
        "You are a precise personal note extractor. ONLY use the provided Context from notes. "
        "Output ONLY valid JSON object: {\"tasks\": [{\"text\": \"one-line task\", \"citation\": \"path:heading\", \"quote\": \"short verbatim\"}], "
        "\"open_questions\": [...same...], \"connections\": [...same...]} . "
        f"Limit each list to at most {max_items} items. Each item MUST have citation in [path: heading] style and short quote from text. "
        "No external knowledge or inferences. Be grounded."
    )
    user = f"""Context:
{context}

Task: extract recent tasks, open questions, and note-to-note connections (e.g. same project across docs). Cite every item. JSON only."""

    model = os.getenv("SYNTH_MODEL", "ollama/llama3.1")
    model_used = model
    raw = ""

    try:
        resp = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=400,
            temperature=0.1,
        )
        raw = (resp.choices[0].message.content or "").strip()
        model_used = model
    except Exception as e:
        raw = ""
        model_used = "fallback"
        # fallback parse from hits themselves (no LLM). Clean frontmatter/junk per review; make usable one-line + short quote.
        fb_items = []
        for h in hits[:max_items]:
            rawc = h.get("content", "")
            text = _clean_text_for_item(rawc)
            q = _clean_text_for_item(rawc, max_len=60)
            nice_sp = _nice_source_path(h.get("source_path", "?"))
            fb_items.append({
                "text": text or "See source",
                "citation": f"{nice_sp}: {h.get('heading','')}",
                "quote": q,
            })
        sections = {"tasks": fb_items[:1], "open_questions": fb_items[1:2] or [], "connections": fb_items[2:3] or []}
        data = sections
        items = {k: [ReflectionItem(**it) for it in v] for k, v in data.items()}
        resp_obj = ReflectionResponse(
            **items,
            model_used=model_used,
            note=f"[fallback no LLM: {str(e)[:60]}]",
            trace_id="fb",
        )
        _write_actions_md(resp_obj, ref.strftime("%Y-%m-%d"), days=days, out_path=actions_path)
        return resp_obj

    sections = _parse_reflect_output(raw)
    # enforce max_items and convert
    for k in list(sections.keys()):
        sections[k] = sections[k][:max_items]

    try:
        data = {
            "tasks": [ReflectionItem(**it) if isinstance(it, dict) else it for it in sections.get("tasks", [])],
            "open_questions": [ReflectionItem(**it) if isinstance(it, dict) else it for it in sections.get("open_questions", [])],
            "connections": [ReflectionItem(**it) if isinstance(it, dict) else it for it in sections.get("connections", [])],
        }
    except Exception:
        # last resort
        data = {"tasks": [], "open_questions": [], "connections": []}

    resp_obj = ReflectionResponse(
        **data,
        model_used=model_used,
        trace_id=uuid4().hex[:8],
    )
    if not any([resp_obj.tasks, resp_obj.open_questions, resp_obj.connections]):
        resp_obj.note = resp_obj.note or "No structured items extracted (local model parse); see actions.md for raw context trace."

    _write_actions_md(resp_obj, ref.strftime("%Y-%m-%d"), days=days, out_path=actions_path)
    return resp_obj
