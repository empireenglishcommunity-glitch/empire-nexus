"""Aql (العقل) — Markdown Chunker.

design.md Section 4.1: splits knowledge files into semantic chunks at
natural boundaries (## headers), never at a fixed character count.

THIS IS THE DIRECT FIX for the root cause identified in
requirements.md Section 0: nour_concierge._load_kb_file() truncates at
a hard content[:2000] boundary with no regard for word/sentence edges,
which can feed the model a context block that ends mid-word -- a
documented trigger for LLM script drift. A chunk boundary here always
falls between complete thoughts (a full ## section, or a full
paragraph within an oversized section), never mid-sentence or
mid-word, because splitting only ever happens at "##" header lines or
blank-line paragraph breaks -- never inside a line.
"""
import re
from dataclasses import dataclass
from pathlib import Path

# Generous per-chunk cap. Real chunks in this knowledge base (short,
# focused ## sections written for a chat-response context, not a
# textbook) are almost always well under this -- see design.md Section
# 4.1's "our real chunks are shorter" note. This cap exists to catch
# the rare oversized section, not to be hit routinely.
MAX_CHUNK_CHARS = 2000  # ~500 tokens at a conservative ~4 chars/token


@dataclass
class Chunk:
    domain: str
    source_file: str
    heading: str
    content: str


def chunk_markdown_file(filepath: Path, domain: str) -> list[Chunk]:
    """Split a markdown file into chunks, one per ## header section.

    Any section whose content exceeds MAX_CHUNK_CHARS is further split
    at paragraph breaks (blank lines) -- NEVER mid-sentence, NEVER
    mid-word. A section with no blank-line breaks at all (a single
    enormous paragraph) is kept as one oversized chunk rather than
    being sliced arbitrarily -- an oversized-but-intact chunk is a far
    smaller risk than reintroducing the exact truncation bug this
    module exists to eliminate.

    The `#` top-level title (if present, e.g. "# دليل الأوامر") is
    treated as document front-matter, not a chunk of its own -- it
    carries no answerable content by itself. Everything before the
    FIRST `##` header (typically the "> هذا الملف جزء من..." intro
    line) is similarly treated as front-matter and discarded, since it
    is identical boilerplate repeated across every knowledge file
    (Rawiya R1's own authoring convention) and would otherwise become
    a useless, near-duplicate chunk in every single file.
    """
    text = filepath.read_text(encoding="utf-8")
    sections = _split_on_h2_headers(text)

    chunks: list[Chunk] = []
    for heading, body in sections:
        body = body.strip()
        if not body:
            continue
        if len(body) <= MAX_CHUNK_CHARS:
            chunks.append(Chunk(domain=domain, source_file=filepath.name,
                                 heading=heading, content=body))
        else:
            for i, piece in enumerate(_split_on_paragraph_breaks(body, MAX_CHUNK_CHARS)):
                piece_heading = heading if i == 0 else f"{heading} (تابع)"
                chunks.append(Chunk(domain=domain, source_file=filepath.name,
                                     heading=piece_heading, content=piece))
    return chunks


_H2_PATTERN = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _split_on_h2_headers(text: str) -> list[tuple[str, str]]:
    """Returns [(heading_text, section_body), ...] for every ## header
    in the document, in order. Content before the first ## header
    (front-matter -- title + the standard intro blockquote) is
    discarded, per this function's own docstring above."""
    matches = list(_H2_PATTERN.finditer(text))
    if not matches:
        # No ## headers at all -- fall back to treating the whole file
        # (minus a possible # title line) as one section. This keeps
        # the chunker functional against a malformed/unexpected file
        # rather than silently producing zero chunks for it.
        stripped = re.sub(r"^#\s+.+$", "", text, count=1, flags=re.MULTILINE).strip()
        return [("عام", stripped)] if stripped else []

    sections = []
    for idx, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections.append((heading, text[start:end]))
    return sections


def _split_on_paragraph_breaks(body: str, max_chars: int) -> list[str]:
    """Greedily pack consecutive paragraphs (blank-line-separated
    blocks) into pieces no larger than max_chars, splitting ONLY at a
    paragraph boundary -- never inside a paragraph, never mid-sentence.
    A single paragraph that alone exceeds max_chars is kept intact as
    its own oversized piece (see chunk_markdown_file's docstring for
    why this is the correct tradeoff)."""
    paragraphs = re.split(r"\n\s*\n", body)
    pieces: list[str] = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                pieces.append(current)
            current = para  # oversized single paragraph starts its own piece
    if current:
        pieces.append(current)
    return pieces
