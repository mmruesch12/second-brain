"""Personal Agentic Second Brain (sb).

Phase 0a baseline: local MD ingest, LanceDB + embeddings, baseline_rag,
synthesis, golden eval harness, CLI (ingest/query/doctor).
"""

__version__ = "0.0.1"

# Note: submodules (chunker, models, etc.) are imported explicitly by callers
# to allow lazy / optional heavy deps (tiktoken, lancedb, litellm) per AGENTS.
