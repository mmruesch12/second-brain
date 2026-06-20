"""Immortal baseline_rag retriever (Phase 0a).

Per PRD §9, §12, AGENTS §5/6: vector + simple metadata filter over the LanceDB index.
This is the baseline that must always exist; future features (router, wikilinks, etc.) must demonstrably beat it on golden eval (≥10% rubric or grounding) before merge.
No LLM calls here (max 0-1 in LOOKUP path).
"""

from typing import List, Dict, Any, Optional

from second_brain.store import search


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

    This function (and its contract) is immortal.
    """
    if not query or not query.strip():
        return []
    hits = search(query, limit=limit, data_zone=zone)
    for h in hits:
        # ensure citation-friendly keys (store provides most)
        if "chunk_id" not in h:
            h["chunk_id"] = f"{h.get('doc_id', '')}:{h.get('chunk_index', 0)}"
        if "heading" not in h:
            h["heading"] = h.get("heading_path", "")
    return hits
