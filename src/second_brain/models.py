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

from second_brain.chunker import Chunk, chunk_markdown


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
    doc_type: str = "markdown",
    parse_quality: str = "ok",
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
        doc_type=doc_type,
        data_zone=data_zone,
        embedding_model_version=None,
        parse_method=parse_method,
        parse_quality=parse_quality,
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


def _extract_text_from_pdf(path: str) -> tuple[str, str, str, str]:
    """Extract text from text-native PDF.

    Returns (md_text_with_#Page_headings, title, parse_quality, parse_method).
    Page headings allow reuse of chunk_markdown for heading_path.
    Prefers pymupdf (fitz), falls back to pdfplumber. Errors -> failed.
    """
    import os

    # Primary: pymupdf
    try:
        import fitz  # pymupdf
        doc = fitz.open(path)
        pages_text: list[str] = []
        for i, page in enumerate(doc):
            txt = page.get_text() or ""
            pages_text.append(f"# Page {i + 1}\n\n{txt.strip()}\n")
        full = "\n\n".join(pages_text)
        meta_title = (doc.metadata or {}).get("title") or ""
        title = meta_title.strip() or os.path.splitext(os.path.basename(path))[0]
        doc.close()
        quality = "ok" if full.strip() else "partial"
        method = "pdf-pymupdf"
        return full, title, quality, method
    except Exception:
        pass

    # Fallback: pdfplumber
    try:
        import pdfplumber
        pages_text = []
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                txt = page.extract_text() or ""
                pages_text.append(f"# Page {i + 1}\n\n{txt.strip()}\n")
            meta = pdf.metadata or {}
            meta_title = meta.get("Title") or meta.get("title") or ""
            title = meta_title.strip() or os.path.splitext(os.path.basename(path))[0]
            full = "\n\n".join(pages_text)
            quality = "ok" if full.strip() else "partial"
            method = "pdf-plumber"
            return full, title, quality, method
    except Exception:
        pass

    # total fail (quarantine; broad to handle corrupt PDFs from any parser)
    return "", os.path.basename(path), "failed", "pdf-failed"


def parse_pdf_document(
    source_path: str,
    data_zone: str = "PUBLIC_DEMO",
) -> Tuple[DocumentMetadata, List[Chunk]]:
    """Parse text-native PDF to (meta, chunks).

    Constructs page-section markdown for reuse of chunk_markdown.
    Sets doc_type="pdf", appropriate parse_method/quality.
    """
    import os
    md_text, pdf_title, quality, method = _extract_text_from_pdf(source_path)
    if quality == "failed" or not md_text.strip():
        meta = extract_document_metadata(
            source_path, "", data_zone, parse_method=method, doc_type="pdf", parse_quality="failed"
        )
        return meta, []

    meta = extract_document_metadata(
        source_path, md_text, data_zone, parse_method=method, doc_type="pdf", parse_quality=quality
    )
    if pdf_title:
        base = os.path.splitext(os.path.basename(source_path))[0]
        cur = (meta.title or "").strip()
        is_page_title = cur.lower().startswith("page ")
        if (not cur or is_page_title or cur == base):
            meta.title = pdf_title
            meta.heading_path = pdf_title or "ROOT"
    chunks = chunk_markdown(md_text)
    return meta, chunks


class Citation(BaseModel):
    source_path: str
    heading: str = ""
    quote_span: str = ""
    chunk_id: str = ""


class SynthesisResponse(BaseModel):
    """Structured synthesis per PRD §8.

    answer_markdown: the brief (or other profile) response.
    profile: brief | standard | audit
    citations: list of source refs with quote spans.
    source_coverage, confidence, model_used etc.
    """
    answer_markdown: str
    profile: str = "brief"
    citations: List[Citation] = []
    source_coverage: Dict[str, Any] = {}
    confidence: str = "MEDIUM"
    verifier_verdict: Optional[str] = None
    trace_id: Optional[str] = None
    egress: bool = False
    model_used: str = ""


class ReflectionItem(BaseModel):
    """One extracted item for reflect (task / question / connection). Mandatory citation per PRD §7.3."""
    text: str
    citation: str  # e.g. "demo/notes/2026-06-05-acme-q3.md: Acme Q3"
    quote: str = ""


class ReflectionResponse(BaseModel):
    """Structured output for `sb reflect` per PRD §7.3 / Phase 3.
    tasks / open_questions / connections lists; each item cited.
    Uses retrieve path (1 LLM target for extraction).
    """
    tasks: List[ReflectionItem] = []
    open_questions: List[ReflectionItem] = []
    connections: List[ReflectionItem] = []
    model_used: str = ""
    trace_id: Optional[str] = None
    note: Optional[str] = None  # e.g. empty retrieval or airgap note


class DecisionLogEntry(BaseModel):
    """Lightweight entry for `sb decide` / decision log (PRD Phase 3 deliverable).
    Timestamped append-only log (no LLM). Stored as JSONL under data dir (gitignored).
    """
    timestamp: str
    text: str
    citation: Optional[str] = None
