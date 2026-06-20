"""Ingest pipeline for Phase 0a/0b.

`sb ingest <path>` : recursively ingest .md and text-native .pdf (respect .secondbrainignore, DataZone, parse+embed+store)
`sb ingest --status` : show manifest from store.

Supports parse_document (md) and parse_pdf_document (pdf T0/T1).
"""

import fnmatch
import re
from pathlib import Path
from typing import List, Optional, Dict, Any

from second_brain.models import parse_document, parse_pdf_document
from second_brain.store import add_document, get_manifest_status


def load_ignore_patterns(ignore_path: Optional[Path] = None) -> List[str]:
    """Load patterns from .secondbrainignore (or given path)."""
    if ignore_path is None:
        ignore_path = Path(".secondbrainignore")
    if not ignore_path.exists():
        return []
    pats: List[str] = []
    for line in ignore_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pats.append(line)
    return pats


def should_ignore(rel_path: Path, patterns: List[str]) -> bool:
    """Basic .gitignore-style matcher supporting *, **, etc. Basic ! negation support (for Phase 0b demo/pdfs)."""
    s = str(rel_path).replace("\\", "/")
    ignored = False
    for pat in patterns:
        p = pat.replace("\\", "/")
        if p.startswith("!"):
            neg = p[1:].lstrip()
            if neg:
                if (fnmatch.fnmatch(s, neg) or fnmatch.fnmatch(s, neg.rstrip("/")) or
                    ("**" in neg and re.match("^" + re.escape(neg).replace(r"\*\*", ".*").replace(r"\*", "[^/]*") + "$", s)) or
                    (neg.endswith("/**") and s.startswith(neg[:-3]))):
                    ignored = False
            continue
        # ignore patterns
        if fnmatch.fnmatch(s, p) or fnmatch.fnmatch(s, p.rstrip("/")):
            ignored = True
            continue
        if "**" in p:
            regex_pat = "^" + re.escape(p).replace(r"\*\*", ".*").replace(r"\*", "[^/]*") + "$"
            if re.match(regex_pat, s):
                ignored = True
                continue
        if p.endswith("/**") and s.startswith(p[:-3]):
            ignored = True
            continue
    return ignored


def resolve_zone(source_path: str, override: Optional[str] = None, frontmatter_zone: Optional[str] = None) -> str:
    """Resolve DataZone with precedence: --zone > frontmatter > path heuristic (demo->PUBLIC_DEMO else PERSONAL).
    Per data-zones.md: retrieval enforces; 'all' bypasses at query (with warning in CLI)."""
    if override:
        return override
    if frontmatter_zone:
        return frontmatter_zone
    p = source_path.replace("\\", "/").lower()
    if "demo/" in p or p.startswith("demo"):
        return "PUBLIC_DEMO"
    # Conservative default (owner can override with --zone or later config)
    return "PERSONAL"


def _parse_frontmatter_zone(text: str) -> Optional[str]:
    """Minimal frontmatter data_zone extractor (matches models style)."""
    if not text.lstrip().startswith("---"):
        return None
    lines = text.splitlines()
    if len(lines) < 2 or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            k, v = [x.strip() for x in line.split(":", 1)]
            if k.lower() == "data_zone":
                return v
    return None


def find_ingest_files(target: Path) -> List[Path]:
    """Find .md and .pdf files (text-native PDFs for Phase 0b)."""
    exts = {".md", ".pdf"}
    if target.is_file() and target.suffix.lower() in exts:
        return [target]
    if target.is_dir():
        return [p for p in target.rglob("*") if p.is_file() and p.suffix.lower() in exts]
    return []


def ingest(target: str, zone_override: Optional[str] = None) -> Dict[str, Any]:
    """Ingest a file or directory of .md or .pdf (Phase 0b text PDFs).

    Returns summary with added, skipped, failed counts.
    """
    root = Path(target).resolve()
    # Prefer ignore file next to target root or cwd (robust for external paths)
    ignore_path = root / ".secondbrainignore" if root.is_dir() else root.parent / ".secondbrainignore"
    patterns = load_ignore_patterns(ignore_path if ignore_path.exists() else None)
    # rel root = dir of the .sbignore we actually loaded patterns from (local for target .sb, cwd for default/root patterns)
    if ignore_path and ignore_path.exists():
        ignore_root_for_rel = ignore_path.parent
    else:
        ignore_root_for_rel = Path.cwd()
    files = find_ingest_files(root)
    added = 0
    skipped = 0
    failed = 0
    for f in files:
        try:
            rel = f.relative_to(ignore_root_for_rel)
        except Exception:
            rel = f.name
        if should_ignore(rel, patterns):
            skipped += 1
            continue
        try:
            suffix = f.suffix.lower()
            if suffix == ".pdf":
                meta, chunks = parse_pdf_document(str(f), data_zone=resolve_zone(str(f), zone_override, None))
                # note: pdf parse does not use fm zone (text PDFs rarely have yaml fm); zone from path/override
            else:
                text = f.read_text(encoding="utf-8", errors="ignore")
                fm_zone = _parse_frontmatter_zone(text)
                z = resolve_zone(str(f), zone_override, fm_zone)
                meta, chunks = parse_document(str(f), text, data_zone=z)
            add_document(meta, chunks)
            # only q=="failed" counts as failed (true parse fail per PRD §14); 0-chunk but q=ok (e.g. empty md) treated as added (manifest row still written for visibility)
            if getattr(meta, "parse_quality", "ok") == "failed":
                failed += 1
            else:
                added += 1
        except Exception:
            failed += 1
    return {"added": added, "skipped": skipped, "failed": failed, "total_files": len(files)}


def get_status() -> List[Dict[str, Any]]:
    """Return manifest for --status."""
    return get_manifest_status()
