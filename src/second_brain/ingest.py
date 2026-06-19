"""Markdown ingest pipeline for Phase 0a.

`sb ingest <path>` : recursively ingest .md files (respect .secondbrainignore, assign DataZone, parse+embed+store)
`sb ingest --status` : show manifest from store.

Uses existing parse_document + add_document.
Implements basic .secondbrainignore and zone resolution per docs/data-zones.md and .secondbrainignore.
"""

import fnmatch
import re
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.second_brain.models import parse_document
from src.second_brain.store import add_document, get_manifest_status


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
    """Basic .gitignore-style matcher supporting *, **, etc."""
    s = str(rel_path).replace("\\", "/")
    for pat in patterns:
        p = pat.replace("\\", "/")
        # direct
        if fnmatch.fnmatch(s, p) or fnmatch.fnmatch(s, p.rstrip("/")):
            return True
        # ** support crude
        if "**" in p:
            regex_pat = "^" + re.escape(p).replace(r"\*\*", ".*").replace(r"\*", "[^/]*") + "$"
            if re.match(regex_pat, s):
                return True
        # dir prefix
        if p.endswith("/**") and s.startswith(p[:-3]):
            return True
    return False


def resolve_zone(source_path: str, override: Optional[str] = None, frontmatter_zone: Optional[str] = None) -> str:
    """Resolve DataZone with precedence: --zone > frontmatter > path heuristic (demo->PUBLIC else PERSONAL)."""
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


def find_markdown_files(target: Path) -> List[Path]:
    if target.is_file() and target.suffix.lower() == ".md":
        return [target]
    if target.is_dir():
        return [p for p in target.rglob("*.md") if p.is_file()]
    return []


def ingest(target: str, zone_override: Optional[str] = None) -> Dict[str, Any]:
    """Ingest a file or directory of markdown.

    Returns summary with added, skipped counts.
    """
    root = Path(target).resolve()
    patterns = load_ignore_patterns()
    files = find_markdown_files(root)
    added = 0
    skipped = 0
    for f in files:
        try:
            rel = f.relative_to(Path.cwd()) if f.is_relative_to(Path.cwd()) else f.relative_to(f.parent)
        except Exception:
            rel = f
        if should_ignore(rel, patterns):
            skipped += 1
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
            fm_zone = _parse_frontmatter_zone(text)
            z = resolve_zone(str(f), zone_override, fm_zone)
            meta, chunks = parse_document(str(f), text, data_zone=z)
            add_document(meta, chunks)
            added += 1
        except Exception:
            skipped += 1
    return {"added": added, "skipped": skipped, "total_files": len(files)}


def get_status() -> List[Dict[str, Any]]:
    """Return manifest for --status."""
    return get_manifest_status()
