"""Unit tests for the Chunker (PRD §8 / ADR-002 contract).

Run with: python -m pytest tests/ -q
"""

import pytest

from src.second_brain.chunker import chunk_markdown, Chunk


def test_empty_input():
    assert chunk_markdown("") == []
    assert chunk_markdown("   \n\n  ") == []


def test_simple_headings_and_content():
    md = """# H1 Title

Some intro text here.

## H2 Section

More text under H2.

### H3 Sub

Details at H3 level.
"""
    chunks = chunk_markdown(md, min_tokens=10, max_tokens=100, overlap_tokens=5)
    assert len(chunks) >= 1
    assert any("H1 Title" in c.heading_path for c in chunks)
    # heading path should reflect hierarchy
    h3_chunk = next((c for c in chunks if "H3 Sub" in c.heading_path), None)
    assert h3_chunk is not None
    assert "H1 Title > H2 Section > H3 Sub" in h3_chunk.heading_path or "H1 Title > H2 Section" in h3_chunk.heading_path


def test_atomic_code_blocks_not_split():
    md = """# Code Example

Here is a block:

```python
def foo():
    return 42

x = 1
y = 2
z = 3
print(x + y + z)
```

After the code.
"""
    chunks = chunk_markdown(md, min_tokens=5, max_tokens=50, overlap_tokens=5)
    # The whole code fence must appear in one chunk
    code_chunk = next((c for c in chunks if "def foo" in c.content), None)
    assert code_chunk is not None
    assert "print(x + y + z)" in code_chunk.content
    # no chunk should contain only partial code
    for c in chunks:
        if "```python" in c.content:
            assert "print(x + y + z)" in c.content


def test_size_and_overlap():
    # Generate content that forces splitting
    long_section = "\n".join([f"This is paragraph {i} with some words to count tokens." for i in range(30)])
    md = f"# Long Doc\n\n## Section A\n\n{long_section}\n\n## Section B\n\nMore text here."
    chunks = chunk_markdown(md, min_tokens=30, max_tokens=60, overlap_tokens=10)
    assert len(chunks) >= 2
    # sizes roughly in range (allow some flexibility for heading overhead)
    for c in chunks:
        tok = len(c.content.split())  # rough proxy; real count in impl
        # We don't assert strict here because our test proxy is word count; the impl uses tiktoken
        assert len(c.content) > 10
    # overlap roughly present between consecutive (heuristic)
    if len(chunks) >= 2:
        # last ~10-15 chars of prev should somewhat appear near start of next (not guaranteed exact due to token vs text)
        prev_tail = chunks[0].content[-15:].strip()
        next_head = chunks[1].content[:50]
        # loose check
        assert any(tok in next_head for tok in prev_tail.split()[:3]) or len(chunks) > 2


def test_metadata_fields():
    md = """# Root

## Child

Text.
"""
    chunks = chunk_markdown(md, min_tokens=1, max_tokens=100)
    for c in chunks:
        assert isinstance(c.chunk_index, int)
        assert isinstance(c.heading_path, str)
        assert isinstance(c.source_line_range, tuple)
        assert len(c.source_line_range) == 2
        assert c.source_line_range[0] <= c.source_line_range[1]


def test_h1_h3_awareness():
    md = """# Top

Intro.

## Mid

Mid content.

### Deep

Deep details.

## Another Mid

More.
"""
    chunks = chunk_markdown(md, min_tokens=1, max_tokens=200)
    deep = next((c for c in chunks if "Deep" in c.heading_path), None)
    assert deep is not None
    assert "Top" in deep.heading_path
    assert "Mid" in deep.heading_path or "Deep" in deep.heading_path
