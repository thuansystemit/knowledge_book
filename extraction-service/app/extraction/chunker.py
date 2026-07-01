"""Prose chunking with page + chapter tracking.

Adapted from the toeic chunker's line-aware sliding window (the question-boundary
mode is dropped — this is prose, not numbered items). Each chunk records its page
range and the nearest preceding heading so per-chunk extractions can be anchored
to a chapter/section for source citations (PRD §8: source_refs)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

PAGE_MARKER = "\f"

# Heading heuristics: short lines that look like a chapter/section title.
# Mirrors the Sprint-0 finding that font cues aren't in the text stream, so we
# fall back to textual patterns. Three independent shapes:
#   - "Chapter N ..." (case-insensitive)
#   - numbered section "1" / "1.2 Title"
#   - an ALL-CAPS line (case-sensitive — that's the signal)
_HEADING_CHAPTER_RE = re.compile(r"^\s*chapter\s+\d+\b", re.IGNORECASE)
_HEADING_NUMBERED_RE = re.compile(r"^\s*\d+(?:\.\d+)*\s+\S")
_HEADING_ALLCAPS_RE = re.compile(r"^[A-Z][A-Z0-9 ,'&\-]{3,60}$")


@dataclass
class Chunk:
    index: int
    page_start: int
    page_end: int
    chapter: str          # nearest preceding heading ("" if none seen yet)
    content: str
    token_estimate: int


def _estimate_tokens(text: str) -> int:
    # ~0.75 words/token — good enough for budgeting.
    return int(len(text.split()) / 0.75)


def _looks_like_heading(line: str) -> bool:
    s = line.strip()
    if not (3 < len(s) <= 70):
        return False
    if _HEADING_CHAPTER_RE.match(s):
        return True
    # Numbered/all-caps titles shouldn't end like a running sentence.
    if s.endswith((".", ",", ";", ":")):
        return False
    return bool(_HEADING_NUMBERED_RE.match(s) or _HEADING_ALLCAPS_RE.match(s))


def chunk_text(text: str, max_tokens: int = 1200, overlap_tokens: int = 150) -> List[Chunk]:
    """Line-aware sliding window. Never splits mid-line; carries the nearest
    preceding heading into each chunk as its `chapter` anchor."""
    pages = text.split(PAGE_MARKER) if PAGE_MARKER in text else [text]

    # (line, page_no, current_heading)
    lines: List[tuple] = []
    heading = ""
    for page_no, page in enumerate(pages, start=1):
        for line in page.split("\n"):
            if _looks_like_heading(line):
                heading = line.strip()
            lines.append((line, page_no, heading))

    if not lines:
        return [Chunk(0, 1, len(pages), "", text.strip(), _estimate_tokens(text))]

    chunks: List[Chunk] = []
    n = len(lines)
    i = 0
    while i < n:
        j, tokens = i, 0
        while j < n and tokens < max_tokens:
            tokens += max(1, _estimate_tokens(lines[j][0]))
            j += 1
        window = lines[i:j]
        content = "\n".join(ln for ln, _, _ in window).strip()
        if content:
            chunks.append(
                Chunk(
                    index=len(chunks),
                    page_start=window[0][1],
                    page_end=window[-1][1],
                    chapter=window[0][2],
                    content=content,
                    token_estimate=_estimate_tokens(content),
                )
            )
        if j >= n:
            break
        # Step back ~overlap_tokens worth of lines for context continuity.
        back, ov, k = 0, 0, j - 1
        while k > i and ov < overlap_tokens:
            ov += max(1, _estimate_tokens(lines[k][0]))
            k -= 1
            back += 1
        i = max(i + 1, j - back)
    return chunks
