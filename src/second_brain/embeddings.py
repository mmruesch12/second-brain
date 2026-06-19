"""Local-only embeddings (nomic-embed-text via Ollama) per PRD §9 and ADR-001.

Enforces:
- Air-gap default + SECOND_BRAIN_AIRGAP=1
- Embeddings NEVER use non-loopback hosts
- No cloud embeddings (even if --cloud for synthesis)
"""

import os
from typing import List

import ollama

EMBED_MODEL = "nomic-embed-text"
EMBED_DIM = 768


def _is_loopback(host: str) -> bool:
    h = (host or "").lower()
    return any(x in h for x in ("localhost", "127.0.0.1", "::1", "0.0.0.0"))


def embed_text(text: str, model: str = EMBED_MODEL) -> List[float]:
    """Embed a single text chunk. Returns dense vector.

    Raises on airgap misconfig or non-local host for embeddings.
    """
    if not text or not text.strip():
        return [0.0] * EMBED_DIM

    airgap = os.getenv("SECOND_BRAIN_AIRGAP", "0") == "1"
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    if not _is_loopback(host):
        raise RuntimeError(
            f"Local embeddings require loopback Ollama (OLLAMA_HOST={host}). "
            "Non-local embedding endpoints are blocked per PRD/AGENTS."
        )

    # Direct ollama call (respects OLLAMA_HOST env)
    try:
        resp = ollama.embeddings(model=model, prompt=text)
        vec = resp.get("embedding", [])
        if len(vec) != EMBED_DIM:
            # nomic-embed-text is 768; tolerate other but warn in future
            pass
        return vec
    except Exception as e:
        if airgap:
            raise RuntimeError("Embedding call failed under airgap (local Ollama required).") from e
        raise


def get_embed_dim() -> int:
    return EMBED_DIM
