"""Markdown chunker implementing the PRD §8 / ADR-002 Chunking Contract v1.

Rules (frozen):
- Markdown split: H1–H3 aware
- Target size: 400–800 tokens
- Overlap: 80 tokens
- Code blocks: Atomic (never split)
- Metadata per chunk: heading_path, chunk_index, source_line_range
"""

import re
from typing import List, Tuple

import tiktoken
from pydantic import BaseModel


class Chunk(BaseModel):
    """A single chunk of a document.

    Follows the contract for use in ingest + retrieval.
    """
    content: str
    heading_path: str
    chunk_index: int
    source_line_range: Tuple[int, int]


def _get_encoder():
    """Use cl100k_base (common for modern models; consistent for chunking decisions)."""
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Return token count using the chosen encoding."""
    enc = _get_encoder()
    return len(enc.encode(text, disallowed_special=()))


def _is_code_fence_start(line: str) -> bool:
    return bool(re.match(r'^\s*```', line))


def _is_heading(line: str) -> bool:
    return bool(re.match(r'^\s*#{1,3}\s+', line))


def _heading_level_and_title(line: str) -> Tuple[int, str]:
    m = re.match(r'^\s*(#{1,3})\s+(.*)$', line)
    if not m:
        return 0, ""
    level = len(m.group(1))
    title = m.group(2).strip()
    return level, title


def chunk_markdown(
    text: str,
    min_tokens: int = 400,
    max_tokens: int = 800,
    overlap_tokens: int = 80,
) -> List[Chunk]:
    """Split markdown following the exact contract.

    - Respects H1-H3 boundaries for structure.
    - Never splits inside ``` code fences (atomic).
    - Tries to keep chunks in [min, max] tokens.
    - Provides ~overlap_tokens of context from previous chunk.
    - Returns rich metadata for citations and filtering.
    """
    if not text or not text.strip():
        return []

    lines = text.splitlines(keepends=True)
    enc = _get_encoder()

    chunks: List[Chunk] = []
    current_lines: List[str] = []
    heading_stack: List[str] = []
    chunk_idx = 0
    line_start = 1
    i = 0
    n = len(lines)

    def current_tokens() -> int:
        return count_tokens("".join(current_lines))

    def emit_chunk():
        nonlocal chunk_idx, line_start, current_lines
        if not current_lines:
            return
        content = "".join(current_lines).strip()
        if not content:
            current_lines = []
            return
        hpath = " > ".join(heading_stack) if heading_stack else "ROOT"
        end_line = line_start + len(current_lines) - 1
        chunks.append(
            Chunk(
                content=content,
                heading_path=hpath,
                chunk_index=chunk_idx,
                source_line_range=(line_start, end_line),
            )
        )
        chunk_idx += 1

        # prepare overlap for next
        overlap_buf: List[str] = []
        overlap_tok = 0
        for l in reversed(current_lines):
            overlap_buf.append(l)
            overlap_tok = count_tokens("".join(reversed(overlap_buf)))
            if overlap_tok >= overlap_tokens:
                break
        current_lines = list(reversed(overlap_buf))
        # approximate new start line (conservative)
        line_start = end_line - len(current_lines) + 1

    while i < n:
        line = lines[i]

        # atomic code block
        if _is_code_fence_start(line):
            code_block: List[str] = [line]
            i += 1
            while i < n and not _is_code_fence_start(lines[i]):
                code_block.append(lines[i])
                i += 1
            if i < n:
                code_block.append(lines[i])
                i += 1
            current_lines.extend(code_block)
            continue

        # heading
        if _is_heading(line):
            lvl, title = _heading_level_and_title(line)
            # close deeper or equal levels
            while heading_stack and len(heading_stack) >= lvl:
                heading_stack.pop()
            if lvl <= 3:
                heading_stack.append(title)
            # decide whether to emit before starting new section
            if current_lines and current_tokens() >= min_tokens:
                emit_chunk()
            current_lines.append(line)
            i += 1
            continue

        current_lines.append(line)
        i += 1

        # emit if over max
        if current_tokens() > max_tokens:
            emit_chunk()

    # final chunk
    if current_lines:
        emit_chunk()

    # merge very small trailing chunks if possible (post-process)
    if len(chunks) >= 2:
        last = chunks[-1]
        prev = chunks[-2]
        if count_tokens(last.content) < min_tokens and count_tokens(prev.content) < max_tokens:
            merged_content = (prev.content + "\n\n" + last.content).strip()
            if count_tokens(merged_content) <= max_tokens:
                chunks[-2] = Chunk(
                    content=merged_content,
                    heading_path=prev.heading_path,
                    chunk_index=prev.chunk_index,
                    source_line_range=prev.source_line_range,
                )
                chunks.pop()

    return chunks
