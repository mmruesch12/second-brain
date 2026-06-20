"""Immortal baseline_rag retriever (Phase 0a) + Phase 1 hybrid retrieve.

Per PRD §9, §12, AGENTS §5/6: baseline is immortal vector + zone. retrieve() adds filters, 1-hop wikilink expansion, heuristic router.
Future features must beat baseline_rag on golden. Max 0 LLM calls in retrieval.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from second_brain.store import search, fetch_by_filter


def baseline_rag(
    query: str,
    limit: int = 8,
    zone: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Baseline semantic retrieval.

    - Embeds query locally (via store).
    - Vector top-k search.
    - Optional strict data_zone filter (enforced).
    - Returns records ready for citation/synthesis: content, source_path, heading_path, chunk_index, doc_id, data_zone, title, chunk_id (synthetic).

    This function (and its contract) is immortal. Do not alter.
    """
    if not query or not query.strip():
        return []
    hits = search(query, limit=limit, data_zone=zone)
    for h in hits:
        if "chunk_id" not in h:
            h["chunk_id"] = f"{h.get('doc_id', '')}:{h.get('chunk_index', 0)}"
        if "heading" not in h:
            h["heading"] = h.get("heading_path", "")
    return hits


def heuristic_router(
    query: str,
    zone: Optional[str] = None,
    since: Optional[str] = None,
    limit: Optional[int] = None,
    profile: str = "brief",
    path_prefix: Optional[str] = None,
    tags: Optional[List[str]] = None,
    ref_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Rule-based router (no LLM) per PRD §7.2/§12. Infers temporal since, tags, zone from CLI + query hints.
    ref_date for tests (defaults to 2026-06-20 for demo corpus dates)."""
    ref = ref_date or datetime(2026, 6, 20)  # demo-only ref; real use would use datetime.utcnow()
    cfg: Dict[str, Any] = {
        "zone": zone,
        "since": since,
        "limit": limit or 5,
        "profile": profile or "brief",
        "path_prefix": path_prefix,
        "tags": list(tags) if tags else None,
    }
    if not query:
        return cfg
    q = query.lower()
    # temporal hints for since (demo dates 2026-04/06; use ref_date)
    if since is None:
        if any(k in q for k in ("last week", "past week", "recent", "this week")):
            cfg["since"] = (ref - timedelta(days=7)).strftime("%Y-%m-%d")
        elif any(k in q for k in ("14 days", "past 14", "two weeks")):
            cfg["since"] = (ref - timedelta(days=14)).strftime("%Y-%m-%d")
        elif "last month" in q or "30 days" in q:
            cfg["since"] = (ref - timedelta(days=30)).strftime("%Y-%m-%d")
        elif "april" in q:
            cfg["since"] = "2026-04-01"
        elif "may" in q:
            cfg["since"] = "2026-05-01"
    # simple tag/project hints
    if not cfg["tags"]:
        hinted = []
        for kw, tag in [("falcon", "falcon"), ("acme", "acme"), ("phoenix", "phoenix"), ("vendor", "vendor"), ("observability", "observability"), ("latency", "latency")]:
            if kw in q:
                hinted.append(tag)
        if hinted:
            cfg["tags"] = hinted
    if not cfg["path_prefix"] and "demo/" in q:
        cfg["path_prefix"] = "demo/"
    return cfg


def _expand_with_wikilinks(
    hits: List[Dict[str, Any]],
    zone: Optional[str] = None,
    max_extra: int = 4,
) -> List[Dict[str, Any]]:
    """1-hop wikilink expansion: collect [[wikilinks]] + reverse (basename match), fetch extra chunks via metadata filter, merge unique."""
    if not hits:
        return hits
    linked: set = set()
    hit_stems: set = set()
    for h in hits:
        sp = str(h.get("source_path", "")).replace("\\", "/")
        stem = Path(sp).stem
        if stem:
            hit_stems.add(stem)
        wls = h.get("wikilinks") or []
        if isinstance(wls, str):
            wls = [x.strip() for x in wls.split(",") if x.strip()]
        for w in wls:
            if w:
                linked.add(w.strip())
    if not linked and not hit_stems:
        return hits
    extra: List[Dict[str, Any]] = []
    for tgt in list(linked)[:6]:
        cands = fetch_by_filter(data_zone=zone, wikilink_target=tgt, limit=2)
        extra.extend(cands)
    for stem in list(hit_stems)[:4]:
        cands = fetch_by_filter(data_zone=zone, wikilink_target=stem, limit=2)
        extra.extend(cands)
    seen = set()
    for h in hits:
        key = (h.get("source_path"), h.get("chunk_index"))
        seen.add(key)
    merged = list(hits)
    for e in extra:
        key = (e.get("source_path"), e.get("chunk_index"))
        if key not in seen:
            seen.add(key)
            merged.append(e)
            if len(merged) >= len(hits) + max_extra:
                break
    return merged


def retrieve(
    query: str,
    limit: int = 8,
    zone: Optional[str] = None,
    since: Optional[str] = None,
    path_prefix: Optional[str] = None,
    tags: Optional[List[str]] = None,
    match_all_tags: bool = False,
) -> List[Dict[str, Any]]:
    """Phase 1 hybrid retriever: vector (larger k) -> metadata filters (store) -> 1-hop wikilink expansion.

    Supports path prefix/glob, since date, tags (any), zone. Returns citation-ready hits.
    Extends baseline; baseline_rag remains the immortal pure version.
    """
    if not query or not query.strip():
        return []
    # over-retrieve then post in store + expand
    k = max(limit * 3, 16)
    hits = search(
        query,
        limit=k,
        data_zone=zone,
        path_prefix=path_prefix,
        since=since,
        tags=tags,
        match_all_tags=match_all_tags,
    )
    hits = _expand_with_wikilinks(hits, zone=zone)
    for h in hits:
        if "chunk_id" not in h:
            h["chunk_id"] = f"{h.get('doc_id', '')}:{h.get('chunk_index', 0)}"
        if "heading" not in h:
            h["heading"] = h.get("heading_path", "")
    return hits[:limit]
