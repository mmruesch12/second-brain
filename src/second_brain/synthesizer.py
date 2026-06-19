"""Minimal synthesizer (LiteLLM + Ollama) per PRD §7/9.

Uses baseline_rag for retrieve, then single LLM call to produce SynthesisResponse.
Default profile 'brief' (≤5 bullets + 1 next action).
Local-first via litellm ollama provider; respects airgap/zone indirectly via retriever.
"""

import os
from typing import List, Optional
import uuid

import litellm

from src.second_brain.models import SynthesisResponse, Citation
from src.second_brain.retriever import baseline_rag


def synthesize(
    query: str,
    limit: int = 5,
    zone: Optional[str] = None,
    profile: str = "brief",
) -> SynthesisResponse:
    """Retrieve via baseline_rag then synthesize with LLM.

    Returns structured SynthesisResponse.
    Max 1 LLM call (synthesis).
    """
    if not query or not query.strip():
        return SynthesisResponse(
            answer_markdown="No query provided.",
            profile=profile,
            model_used="none",
        )

    hits = baseline_rag(query, limit=limit, zone=zone)

    if not hits:
        return SynthesisResponse(
            answer_markdown="No relevant content found in the index. Try a broader query or run `sb ingest`.",
            profile=profile,
            source_coverage={"n_chunks": 0},
            model_used="none",
        )

    # Build context
    context_lines = []
    for h in hits:
        ctx = f"[{h.get('source_path','?')} | {h.get('heading','')}]: {h.get('content','')[:400]}"
        context_lines.append(ctx)
    context = "\n\n".join(context_lines)

    # Simple prompt for brief profile
    system = "You are a concise personal knowledge assistant. Answer ONLY from the provided context. Use markdown. For 'brief' profile: at most 5 bullets + exactly 1 'Next action' if applicable. Cite inline using [path: heading] format."
    user = f"""Context:
{context}

Query: {query}

Profile: {profile}
Produce the answer now."""

    model = os.getenv("SYNTH_MODEL", "ollama/llama3.1")  # default local via litellm+ollama

    try:
        resp = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=600,
            temperature=0.2,
        )
        answer = resp.choices[0].message.content.strip()
        model_used = model
    except Exception as e:
        # Fallback for airgap/no-model or test
        answer = f"[synthesis unavailable: {str(e)[:100]}]\n\nFrom context:\n" + "\n".join(f"- {h.get('content','')[:80]}..." for h in hits[:3])
        model_used = "fallback"

    citations = [
        Citation(
            source_path=h.get("source_path", ""),
            heading=h.get("heading", ""),
            quote_span=h.get("content", "")[:120],
            chunk_id=h.get("chunk_id", ""),
        )
        for h in hits[:3]
    ]

    coverage = {
        "n_chunks": len(hits),
        "files_touched": len(set(h.get("source_path","") for h in hits)),
    }

    return SynthesisResponse(
        answer_markdown=answer,
        profile=profile,
        citations=citations,
        source_coverage=coverage,
        confidence="MEDIUM",
        trace_id=str(uuid.uuid4())[:8],
        model_used=model_used,
    )
