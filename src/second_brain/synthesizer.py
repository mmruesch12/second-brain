"""Minimal synthesizer (LiteLLM + Ollama) per PRD §7/9.

Uses hardened retrieve (filters + 1-hop wikilinks + heuristic router) then single LLM call to produce SynthesisResponse.
baseline_rag remains immortal for eval comparison / "beat baseline".
Default profile 'brief' (≤5 bullets + 1 next action).
Phase 2: optional stream (fast TTFT print) + verify (2nd cheap LLM for grounding).
Local-first via litellm ollama provider; respects airgap/zone indirectly via retriever.
"""

import os
import sys
from typing import List, Optional
import uuid

import litellm

from second_brain.models import SynthesisResponse, Citation
from second_brain.retriever import retrieve, heuristic_router


def synthesize(
    query: str,
    limit: int = 5,
    zone: Optional[str] = None,
    profile: str = "brief",
    since: Optional[str] = None,
    tags: Optional[List[str]] = None,
    path_prefix: Optional[str] = None,
    stream: bool = False,
    verify: bool = False,
) -> SynthesisResponse:
    """Retrieve via hardened retrieve (filters + wikilinks via router) then synthesize (1 LLM).

    baseline_rag kept for comparison only (immortal). Max 1 LLM call (2 if verify=True).
    stream=True: litellm stream chunks printed live for fast TTFT UX.
    """
    if not query or not query.strip():
        ans = "No query provided."
        if stream:
            sys.stdout.write(ans + "\n")
            sys.stdout.flush()
        return SynthesisResponse(
            answer_markdown=ans,
            profile=profile,
            model_used="none",
        )

    # Phase 1: heuristic router + hardened retrieve (baseline_rag contract preserved for eval beats)
    rcfg = heuristic_router(query, zone=zone, since=since, limit=limit, profile=profile, path_prefix=path_prefix, tags=tags, ref_date=None)
    eff_limit = rcfg.get("limit", limit)
    eff_zone = rcfg.get("zone") or zone
    eff_since = rcfg.get("since") or since
    eff_tags = rcfg.get("tags") or tags
    eff_path = rcfg.get("path_prefix") or path_prefix
    hits = retrieve(query, limit=eff_limit, zone=eff_zone, since=eff_since, path_prefix=eff_path, tags=eff_tags)

    if not hits:
        ans = "No indexed content matched. Suggest broader terms + `sb ingest --status`."
        if stream:
            sys.stdout.write(ans + "\n")
            sys.stdout.flush()
        return SynthesisResponse(
            answer_markdown=ans,
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

    # Differentiated profiles per PRD (brief default: <=5 bullets +1 next action)
    if profile == "brief":
        pinstr = "at most 5 bullets + exactly 1 'Next action' if applicable. Be concise."
    elif profile == "standard":
        pinstr = "5-8 bullets or short paras with key details; list explicit sources."
    else:
        pinstr = "exhaustive detail from context, full citations, quote spans, coverage summary."
    system = f"You are a personal knowledge assistant. Answer ONLY from the provided context. Use markdown. Profile '{profile}': {pinstr} Cite inline using [path: heading] format."
    user = f"""Context:
{context}

Query: {query}

Profile: {profile}
Produce the answer now."""

    model = os.getenv("SYNTH_MODEL", "ollama/llama3.1")  # default local via litellm+ollama

    airgap = os.getenv("SECOND_BRAIN_AIRGAP", "0") == "1"
    if airgap:
        # Hard block per AGENTS §3: SECOND_BRAIN_AIRGAP=1 must prevent all egress (LLM path)
        answer = "Synthesis blocked under airgap (SECOND_BRAIN_AIRGAP=1). Local models only."
        model_used = "airgap-blocked"
        if stream:
            sys.stdout.write(answer + "\n")
            sys.stdout.flush()
    else:
        try:
            if stream:
                answer = ""
                for chunk in litellm.completion(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    max_tokens=600,
                    temperature=0.2,
                    stream=True,
                ):
                    delta = ""
                    if chunk and chunk.choices and chunk.choices[0].delta:
                        delta = chunk.choices[0].delta.content or ""
                    if delta:
                        sys.stdout.write(delta)
                        sys.stdout.flush()
                        answer += delta
                sys.stdout.write("\n")
                sys.stdout.flush()
            else:
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
            # Fallback for no-model or test
            answer = f"[synthesis unavailable: {str(e)[:100]}]\n\nFrom context:\n" + "\n".join(f"- {h.get('content','')[:80]}..." for h in hits[:3])
            model_used = "fallback"
            if stream:
                sys.stdout.write(answer + "\n")
                sys.stdout.flush()

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

    resp = SynthesisResponse(
        answer_markdown=answer,
        profile=profile,
        citations=citations,
        source_coverage=coverage,
        confidence="MEDIUM",
        trace_id=str(uuid.uuid4())[:8],
        model_used=model_used,
    )
    if verify:
        try:
            from .verifier import verify_citations
            resp.verifier_verdict = verify_citations(query, answer, hits)
        except Exception as ve:
            resp.verifier_verdict = "UNVERIFIED"
    return resp
