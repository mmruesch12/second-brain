"""Pydantic data models and metadata extraction per PRD §8 Data Contracts.

Implements DocumentMetadata (and ties to Chunk from chunker).
Extraction handles:
- YAML frontmatter (title, date, tags)
- [[wikilinks]]
- content hash (sha256)
- title fallback to first H1 or filename
- DataZone assignment
"""

import hashlib
import os
import re
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any

from pydantic import BaseModel

from src.second_brain.chunker import Chunk, chunk_markdown


class DocumentMetadata(BaseModel):
    """Per-document metadata per Metadata Schema v1 (PRD §8).

    Used for manifest, filtering, citation, and zone enforcement.
    """
    source_path: str
    content_hash: str
    doc_id: str
    ingested_at: datetime
    modified_at: Optional[datetime] = None
    title: Optional[str] = None
    tags: List[str] = []
    wikilinks: List[str] = []
    heading_path: Optional[str] = None
    doc_type: str = "markdown"
    data_zone: str = "PUBLIC_DEMO"
    embedding_model_version: Optional[str] = None
    parse_method: str = "markdown"
    parse_quality: str = "ok"


def _parse_frontmatter(text: str) -> dict:
    """Minimal parser for demo-style frontmatter.

    Supports:
      ---
      title: Foo Bar
      date: 2026-06-05
      tags: [acme, planning]
      ---
    Returns dict with scalar or list values. No complex YAML.
    """
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return {}
    lines = text.splitlines()
    if len(lines) < 1 or lines[0].strip() != "---":
        return {}
    fm_lines: List[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        fm_lines.append(line)
    fm: dict = {}
    for line in fm_lines:
        if ":" not in line:
            continue
        k, v = [p.strip() for p in line.split(":", 1)]
        if not k:
            continue
        if v.startswith("[") and v.endswith("]"):
            items = [x.strip() for x in v[1:-1].split(",") if x.strip()]
            fm[k] = items
        else:
            fm[k] = v
    return fm


def _extract_wikilinks(text: str) -> List[str]:
    """Extract unique [[target]] or [[target|label]] links, order-preserving."""
    matches = re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", text)
    seen: set = set()
    out: List[str] = []
    for m in matches:
        link = m.strip()
        if link and link not in seen:
            seen.add(link)
            out.append(link)
    return out


def compute_content_hash(text: str) -> str:
    """Stable SHA256 of the document text (utf-8)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_document_metadata(
    source_path: str,
    text: str,
    data_zone: str = "PUBLIC_DEMO",
    parse_method: str = "markdown",
) -> DocumentMetadata:
    """Extract DocumentMetadata from raw markdown text + path.

    - Frontmatter overrides for title/date/tags
    - Fallback title from first H1 or basename
    - Wikilinks collected from full text
    - Hashes for change detection
    """
    if text is None:
        text = ""
    fm = _parse_frontmatter(text)
    content_hash = compute_content_hash(text)

    # Stable doc_id: short hash of (path + content)
    seed = f"{source_path}:{content_hash}".encode("utf-8")
    doc_id = hashlib.sha256(seed).hexdigest()[:16]

    title = fm.get("title")
    if not title:
        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if m:
            title = m.group(1).strip()
    if not title:
        base = os.path.basename(source_path) or source_path
        title = os.path.splitext(base)[0]

    tags = fm.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.strip("[]").split(",") if t.strip()]

    wikilinks = _extract_wikilinks(text)

    # top-level heading for doc metadata
    heading_path = title or "ROOT"

    ingested_at = datetime.utcnow()

    modified_at: Optional[datetime] = None
    date_val = fm.get("date")
    if date_val:
        try:
            if isinstance(date_val, str) and len(date_val) >= 10:
                d = date_val[:10]
                modified_at = datetime.fromisoformat(f"{d}T00:00:00")
            else:
                modified_at = datetime.fromisoformat(str(date_val).replace("Z", "+00:00"))
        except Exception:
            modified_at = None

    return DocumentMetadata(
        source_path=source_path,
        content_hash=content_hash,
        doc_id=doc_id,
        ingested_at=ingested_at,
        modified_at=modified_at,
        title=title or None,
        tags=tags,
        wikilinks=wikilinks,
        heading_path=heading_path,
        doc_type="markdown",
        data_zone=data_zone,
        embedding_model_version=None,
        parse_method=parse_method,
        parse_quality="ok",
    )


def parse_document(
    source_path: str,
    text: str,
    data_zone: str = "PUBLIC_DEMO",
) -> Tuple[DocumentMetadata, List[Chunk]]:
    """Convenience: extract metadata + run chunking in one step.

    Returns (DocumentMetadata, list of Chunk).
    """
    meta = extract_document_metadata(source_path, text, data_zone)
    chunks = chunk_markdown(text)
    return meta, chunks

