"""LanceDB vector store + SQLite manifest for Phase 0a.

Implements local embeddings + LanceDB index + manifest (PRD §9, §12, ADR-001).
- Chunks stored with vector + rich metadata (source, zone, headings).
- Manifest tracks ingested documents for status / incremental.
- Data dir respects SECOND_BRAIN_DATA_DIR, 0700 perms.
- Embeddings always local-only via embeddings module.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import lancedb

from second_brain.models import DocumentMetadata
from second_brain.chunker import Chunk
from second_brain.embeddings import embed_text, EMBED_DIM

DEFAULT_DATA_DIR = Path(os.getenv("SECOND_BRAIN_DATA_DIR", Path.home() / ".secondbrain")).expanduser()
TABLE_NAME = "chunks"


def get_data_dir() -> Path:
    """Return (and ensure) the data directory. chmod 0700 for privacy."""
    d = DEFAULT_DATA_DIR
    d.mkdir(parents=True, exist_ok=True)
    try:
        d.chmod(0o700)
    except Exception:
        pass  # best effort
    return d


def _lancedb_uri() -> str:
    return str(get_data_dir() / ".lancedb")


def _manifest_path() -> Path:
    return get_data_dir() / "manifest.db"


def _init_manifest() -> None:
    conn = sqlite3.connect(_manifest_path())
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS docs (
            doc_id TEXT PRIMARY KEY,
            source_path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            ingested_at TEXT NOT NULL,
            modified_at TEXT,
            num_chunks INTEGER NOT NULL,
            data_zone TEXT NOT NULL,
            title TEXT,
            doc_type TEXT DEFAULT 'markdown',
            parse_quality TEXT DEFAULT 'ok'
        )
        """
    )
    # compat for pre-0b dbs (Phase 0b adds pdf visibility)
    try:
        conn.execute("ALTER TABLE docs ADD COLUMN doc_type TEXT DEFAULT 'markdown'")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE docs ADD COLUMN parse_quality TEXT DEFAULT 'ok'")
    except Exception:
        pass
    conn.commit()
    conn.close()


def add_document(meta: DocumentMetadata, chunks: List[Chunk]) -> None:
    """Embed chunks (if any) into LanceDB + always record manifest entry first (for failed/0-chunk visibility per PRD §14)."""
    _init_manifest()

    # Always record meta to manifest BEFORE vectors (guarantees row even if embed step raises)
    conn = sqlite3.connect(_manifest_path())
    conn.execute(
        """
        INSERT OR REPLACE INTO docs
        (doc_id, source_path, content_hash, ingested_at, modified_at, num_chunks, data_zone, title, doc_type, parse_quality)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            meta.doc_id,
            meta.source_path,
            meta.content_hash,
            meta.ingested_at.isoformat() if isinstance(meta.ingested_at, datetime) else str(meta.ingested_at),
            meta.modified_at.isoformat() if meta.modified_at else None,
            len(chunks),
            meta.data_zone,
            meta.title,
            getattr(meta, "doc_type", "markdown"),
            getattr(meta, "parse_quality", "ok"),
        ),
    )
    conn.commit()
    conn.close()

    if chunks:
        db = lancedb.connect(_lancedb_uri())

        # Prepare records with embeddings
        records: List[Dict[str, Any]] = []
        for c in chunks:
            vec = embed_text(c.content)
            rec = {
                "vector": vec,
                "doc_id": meta.doc_id,
                "chunk_index": c.chunk_index,
                "content": c.content,
                "source_path": meta.source_path,
                "heading_path": c.heading_path,
                "data_zone": meta.data_zone,
                "title": meta.title or "",
            }
            records.append(rec)

        # Open or create table
        try:
            tbl = db.open_table(TABLE_NAME)
        except Exception:
            # First time: create with data
            tbl = db.create_table(TABLE_NAME, data=records, mode="overwrite")
        else:
            tbl.add(records)


def get_manifest_status() -> List[Dict[str, Any]]:
    """Return list of ingested documents from manifest (for --status)."""
    _init_manifest()
    conn = sqlite3.connect(_manifest_path())
    cur = conn.execute(
        "SELECT doc_id, source_path, content_hash, ingested_at, num_chunks, data_zone, title, "
        "COALESCE(doc_type, 'markdown'), COALESCE(parse_quality, 'ok') "
        "FROM docs ORDER BY ingested_at DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "doc_id": r[0],
            "source_path": r[1],
            "content_hash": r[2],
            "ingested_at": r[3],
            "num_chunks": r[4],
            "data_zone": r[5],
            "title": r[6],
            "doc_type": r[7],
            "parse_quality": r[8],
        }
        for r in rows
    ]


def search(
    query: str,
    limit: int = 8,
    data_zone: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Basic semantic search. Returns raw records (vector search + optional zone filter).

    Used by baseline_rag later.
    """
    if not query:
        return []
    vec = embed_text(query)
    db = lancedb.connect(_lancedb_uri())
    try:
        tbl = db.open_table(TABLE_NAME)
    except Exception:
        return []
    q = tbl.search(vec).limit(limit)
    results = q.to_list()
    if data_zone:
        # Reliable post-filter (MVP; works regardless of Lance .where support)
        results = [r for r in results if r.get("data_zone") == data_zone]
    # strip heavy vector from results for caller convenience
    for r in results:
        r.pop("vector", None)
    return results


def reset_index() -> None:
    """Dangerous helper for tests: removes lancedb dir contents (not manifest)."""
    import shutil
    ldb = Path(_lancedb_uri())
    if ldb.exists():
        shutil.rmtree(ldb, ignore_errors=True)
