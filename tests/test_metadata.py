"""Unit tests for DocumentMetadata + extraction (PRD §8).

Covers frontmatter, wikilinks, hashing, title fallback, integration with chunker.
"""

import pytest

from src.second_brain.models import (
    DocumentMetadata,
    extract_document_metadata,
    parse_document,
    compute_content_hash,
)
from src.second_brain.chunker import Chunk


def test_document_metadata_model_fields():
    m = DocumentMetadata(
        source_path="demo/notes/test.md",
        content_hash="a" * 64,
        doc_id="deadbeef12345678",
        ingested_at="2026-06-19T12:00:00",
    )
    assert m.source_path == "demo/notes/test.md"
    assert m.data_zone == "PUBLIC_DEMO"
    assert m.doc_type == "markdown"
    assert m.tags == []
    assert m.wikilinks == []


def test_extract_with_full_frontmatter_and_wikilinks():
    md = """---
title: Acme Q3 Planning
date: 2026-06-05
tags: [acme, planning]
---

# Acme Q3 Launch Planning

## Key Notes

See also [[2026-06-01-falcon-sync]] and [[Project Phoenix]] for context.

Constraints include budget and mobile.
"""
    meta = extract_document_metadata("demo/notes/2026-06-05-acme-q3.md", md, data_zone="PUBLIC_DEMO")
    assert isinstance(meta, DocumentMetadata)
    assert meta.title == "Acme Q3 Planning"
    assert meta.tags == ["acme", "planning"]
    assert "2026-06-01-falcon-sync" in meta.wikilinks
    assert "Project Phoenix" in meta.wikilinks
    assert meta.source_path.endswith("acme-q3.md")
    assert len(meta.content_hash) == 64
    assert len(meta.doc_id) == 16
    assert meta.modified_at is not None
    assert meta.heading_path == "Acme Q3 Planning"


def test_title_fallback_to_h1_and_filename():
    # no frontmatter, has H1
    md1 = "# My Custom Title\n\nSome content with [[a-link]]."
    m1 = extract_document_metadata("notes/xyz.md", md1)
    assert m1.title == "My Custom Title"
    assert m1.wikilinks == ["a-link"]

    # no frontmatter, no H1 -> basename
    md2 = "Just plain text without heading."
    m2 = extract_document_metadata("notes/2026-foo-bar.md", md2)
    assert m2.title == "2026-foo-bar"


def test_wikilinks_unique_and_piped():
    md = "See [[target-one]] and [[target-two|display]] plus [[target-one]] again."
    meta = extract_document_metadata("x.md", md)
    assert meta.wikilinks == ["target-one", "target-two"]


def test_content_hash_deterministic_and_changes():
    text = "identical content"
    h1 = compute_content_hash(text)
    h2 = compute_content_hash(text)
    assert h1 == h2
    assert len(h1) == 64

    h3 = compute_content_hash("different")
    assert h3 != h1


def test_parse_document_integration():
    md = """---
title: Test Doc
tags: [demo]
---

# Test Doc

Intro.

```python
print("atomic")
```

## Section
Content with [[cross-ref]].
"""
    meta, chunks = parse_document("demo/test.md", md, data_zone="PUBLIC_DEMO")
    assert isinstance(meta, DocumentMetadata)
    assert meta.title == "Test Doc"
    assert "cross-ref" in meta.wikilinks
    assert isinstance(chunks, list)
    assert len(chunks) >= 1
    for c in chunks:
        assert isinstance(c, Chunk)
        assert c.heading_path
    # chunks should contain the code block intact
    code_chunks = [c for c in chunks if "print" in c.content]
    assert len(code_chunks) == 1
    assert "atomic" in code_chunks[0].content


def test_tags_string_fallback_and_empty():
    md_str_tags = """---
title: StrTags
tags: [one, two]
---
Content.
"""
    m = extract_document_metadata("s.md", md_str_tags)
    assert m.tags == ["one", "two"]

    m2 = extract_document_metadata("empty.md", "# Empty\n\nNo fm here.")
    assert m2.tags == []
    assert m2.wikilinks == []


def test_data_zone_override():
    md = "# Zoned\n\n[[x]]"
    m = extract_document_metadata("p.md", md, data_zone="PERSONAL")
    assert m.data_zone == "PERSONAL"
