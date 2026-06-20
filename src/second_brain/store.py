"""LanceDB vector store + SQLite manifest for Phase 0a.

Implements local embeddings + LanceDB index + manifest (PRD §9, §12, ADR-001).
- Chunks stored with vector + rich metadata (source, zone, headings).
- Manifest tracks ingested documents for status / incremental.
- Data dir respects SECOND_BRAIN_DATA_DIR, 0700 perms.
- Embeddings always local-only via embeddings module.
"""

import fnmatch
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
                "modified_at": meta.modified_at.isoformat() if meta.modified_at else None,
                "tags": list(meta.tags) if meta.tags else [],
                "wikilinks": list(meta.wikilinks) if meta.wikilinks else [],
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


def _parse_since(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        d = s[:10]
        return datetime.fromisoformat(f"{d}T00:00:00")
    except Exception:
        return None


def _apply_metadata_filters(
    records: List[Dict[str, Any]],
    data_zone: Optional[str] = None,
    path_prefix: Optional[str] = None,
    since: Optional[str] = None,
    tags: Optional[List[str]] = None,
    match_all_tags: bool = False,
    wikilink_target: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Post-filter for Phase 1 metadata filters (path prefix/glob, date since, tags any/all, wikilink, zone)."""
    if not records:
        return records
    since_dt = _parse_since(since)
    tagset = set(t.lower() for t in (tags or []))
    out: List[Dict[str, Any]] = []
    for r in records:
        # None or falsy (not 'all') = no zone filter (broad; allows default PERSONAL per resolve/ingest + data-zones).
        # Explicit zone requested enforces (zero leak on mixed when provided). Use --zone all (with CLI warn) for broad explicit.
        if data_zone and data_zone.lower() not in ("all", "none", "") and r.get("data_zone") != data_zone:
            continue
        sp = str(r.get("source_path", "")).replace("\\", "/")
        if path_prefix:
            pp = str(path_prefix).replace("\\", "/")
            # normalize for abs from real ingest (Path.resolve()) vs rel "demo/..." ; support subdir/glob
            sp_norm = sp
            if "/demo/" in sp:
                sp_norm = "demo/" + sp.split("/demo/", 1)[1]
            elif sp.startswith("demo/") or sp == "demo":
                sp_norm = sp
            pp_norm = pp
            if pp.startswith("demo/") or pp == "demo":
                pp_norm = pp
            if not (sp_norm.startswith(pp_norm) or fnmatch.fnmatch(sp_norm, pp_norm) or
                    fnmatch.fnmatch(sp, "**/" + pp_norm.lstrip("./")) or sp.endswith("/" + pp_norm.lstrip("./")) or
                    sp.endswith(pp_norm)):
                continue
        if since_dt:
            ma = r.get("modified_at")
            if ma:
                try:
                    md = datetime.fromisoformat(str(ma)[:19].replace(" ", "T"))
                    if md < since_dt:
                        continue
                except Exception:
                    pass  # keep if unparsable
        rtags = r.get("tags") or []
        if isinstance(rtags, str):
            rtags = [x.strip() for x in rtags.split(",") if x.strip()]
        if tagset:
            rtset = set(str(t).lower() for t in rtags)
            if match_all_tags:
                if not tagset.issubset(rtset):
                    continue
            elif not (tagset & rtset):
                continue
        if wikilink_target:
            wls = r.get("wikilinks") or []
            if isinstance(wls, str):
                wls = [x.strip() for x in wls.split(",") if x.strip()]
            base = Path(sp).stem
            wt = wikilink_target.strip()
            # tighten: exact wikilink match or exact stem/basename reverse (avoid substring overmatch on short tokens)
            matched = wt in wls or wt == base or any(w.strip() == wt for w in wls)
            if not matched:
                continue
        out.append(r)
    return out


def search(
    query: str,
    limit: int = 8,
    data_zone: Optional[str] = None,
    path_prefix: Optional[str] = None,
    since: Optional[str] = None,
    tags: Optional[List[str]] = None,
    match_all_tags: bool = False,
) -> List[Dict[str, Any]]:
    """Semantic search + Phase 1 metadata filters (path, since, tags, zone). Post-filter for robustness.

    Used by baseline_rag (backward compat) and hardened retrieve.
    """
    if not query:
        return []
    vec = embed_text(query)
    db = lancedb.connect(_lancedb_uri())
    try:
        tbl = db.open_table(TABLE_NAME)
    except Exception:
        return []
    q = tbl.search(vec).limit(max(limit * 2, 20))  # overfetch for post-filter
    results = q.to_list()
    results = _apply_metadata_filters(
        results,
        data_zone=data_zone,
        path_prefix=path_prefix,
        since=since,
        tags=tags,
        match_all_tags=match_all_tags,
    )
    # strip heavy vector
    for r in results:
        r.pop("vector", None)
    return results[:limit]


def fetch_by_filter(
    data_zone: Optional[str] = None,
    path_prefix: Optional[str] = None,
    since: Optional[str] = None,
    tags: Optional[List[str]] = None,
    wikilink_target: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Metadata-only fetch for wikilink expansion / filter queries (dummy vec + post filter)."""
    db = lancedb.connect(_lancedb_uri())
    try:
        tbl = db.open_table(TABLE_NAME)
    except Exception:
        return []
    dummy = [0.0] * EMBED_DIM
    try:
        q = tbl.search(dummy).limit(max(limit * 2, 100))
        results = q.to_list()
    except Exception:
        return []
    results = _apply_metadata_filters(
        results,
        data_zone=data_zone,
        path_prefix=path_prefix,
        since=since,
        tags=tags,
        wikilink_target=wikilink_target,
    )
    for r in results:
        r.pop("vector", None)
    return results[:limit]


def reset_index() -> None:
    """Dangerous helper for tests: removes lancedb dir contents (not manifest)."""
    import shutil
    ldb = Path(_lancedb_uri())
    if ldb.exists():
        shutil.rmtree(ldb, ignore_errors=True)
