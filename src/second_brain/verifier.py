"""Citation verifier v1 (grounding critic only) for Phase 2 per PRD §7.2, §9, §12, §14.

Async by default (CLI launches thread unless --verify); local cheap model.
Verdicts: SUPPORTED | PARTIAL | UNSUPPORTED | UNVERIFIED (bare for errors/airgap/timeout per PRD §14; details in debug/trace).
Respects SECOND_BRAIN_AIRGAP; uses litellm for cheap local (env VERIFY_MODEL or ollama/phi3:mini).
No cloud unless caller passes model with consent (Phase2 defers heavy --cloud).
"""

import os
from typing import List, Dict, Any, Optional

import litellm


def verify_citations(
    query: str,
    answer: str,
    hits: List[Dict[str, Any]],
    model: Optional[str] = None,
    timeout: float = 15.0,
) -> str:
    """Grounding-only check: do answer claims have direct support in provided hit contexts/quotes?

    Returns verdict string for SynthesisResponse.verifier_verdict.
    Errors/timeout/airgap -> bare "UNVERIFIED" (banner per PRD §14; details in debug/trace).
    """
    if not answer or not answer.strip() or not hits:
        return "UNVERIFIED"

    airgap = os.getenv("SECOND_BRAIN_AIRGAP", "0") == "1"
    if airgap:
        return "UNVERIFIED"

    # small context for cheap model
    ctx_lines = []
    for h in hits[:4]:
        sp = h.get("source_path", "?")
        cont = str(h.get("content", ""))[:280]
        ctx_lines.append(f"[{sp}]: {cont}")
    ctx = "\n\n".join(ctx_lines)

    system = (
        "You are a strict citation grounding critic for personal notes. "
        "Respond with exactly one of: SUPPORTED, PARTIAL, UNSUPPORTED. "
        "Followed by very brief reason. Judge ONLY if Answer claims have direct textual support or close paraphrase in Context. "
        "Flag unsupported claims or quote mismatches. No external knowledge."
    )
    user = f"""Context chunks:
{ctx}

Query: {query}

Answer:
{answer[:700]}

Grounding verdict (SUPPORTED/PARTIAL/UNSUPPORTED) + short note:"""

    model = model or os.getenv("VERIFY_MODEL", "ollama/phi3:mini")

    try:
        resp = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=80,
            temperature=0.0,
            timeout=timeout,
        )
        text = (resp.choices[0].message.content or "").strip().upper()
        if "SUPPORTED" in text and "PARTIAL" not in text:
            return "SUPPORTED"
        if "PARTIAL" in text:
            return "PARTIAL"
        if "UNSUPPORTED" in text:
            return "UNSUPPORTED"
        return "UNVERIFIED"
    except Exception as e:
        msg = str(e)
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            return "UNVERIFIED"
        return "UNVERIFIED"
