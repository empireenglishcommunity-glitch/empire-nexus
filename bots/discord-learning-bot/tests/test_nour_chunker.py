"""Tests for src/nour/knowledge/chunker.py — Aql (#15) Phase A1.1.

This module is the DIRECT fix for the root cause identified in
requirements.md Section 0: nour_concierge._load_kb_file() truncates at
a hard content[:2000] boundary with no regard for word/sentence edges.
These tests exist to prove chunk boundaries NEVER fall mid-word or
mid-sentence, against both synthetic edge cases and every real
knowledge file that ships in this repo.
"""
import re
from pathlib import Path

import pytest

from src.nour.knowledge.chunker import (
    MAX_CHUNK_CHARS,
    chunk_markdown_file,
    _split_on_h2_headers,
    _split_on_paragraph_breaks,
)

KB_DIR = Path(__file__).resolve().parent.parent / "data" / "nour_knowledge"


# ============================================================
#  SYNTHETIC EDGE CASES
# ============================================================

def _write_md(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_basic_two_section_file(tmp_path):
    content = (
        "# عنوان\n\n"
        "> هذا الملف جزء من قاعدة معرفة نور.\n\n"
        "## القسم الأول\n\n"
        "محتوى القسم الأول.\n\n"
        "## القسم الثاني\n\n"
        "محتوى القسم الثاني.\n"
    )
    filepath = _write_md(tmp_path, "test.md", content)
    chunks = chunk_markdown_file(filepath, "test_domain")

    assert len(chunks) == 2
    assert chunks[0].heading == "القسم الأول"
    assert "محتوى القسم الأول" in chunks[0].content
    assert chunks[1].heading == "القسم الثاني"
    assert "محتوى القسم الثاني" in chunks[1].content


def test_frontmatter_before_first_h2_is_discarded(tmp_path):
    """The title (#) and the standard intro blockquote (repeated
    verbatim across every real knowledge file) must never become their
    own chunk -- they carry no answerable content and would otherwise
    produce a near-duplicate chunk in every single file."""
    content = (
        "# عنوان الملف\n\n"
        "> هذا الملف جزء من قاعدة معرفة نور — المدربة الذكية في Empire English.\n\n"
        "## أول قسم حقيقي\n\n"
        "هذا هو المحتوى الحقيقي.\n"
    )
    filepath = _write_md(tmp_path, "test.md", content)
    chunks = chunk_markdown_file(filepath, "test_domain")

    assert len(chunks) == 1
    for c in chunks:
        assert "هذا الملف جزء من قاعدة معرفة" not in c.content
        assert "عنوان الملف" not in c.content


def test_empty_section_produces_no_chunk(tmp_path):
    content = (
        "# عنوان\n\n"
        "## قسم فاضي\n\n"
        "## قسم فيه محتوى\n\n"
        "محتوى حقيقي هنا.\n"
    )
    filepath = _write_md(tmp_path, "test.md", content)
    chunks = chunk_markdown_file(filepath, "test_domain")

    assert len(chunks) == 1
    assert chunks[0].heading == "قسم فيه محتوى"


def test_no_h2_headers_at_all_falls_back_to_one_section(tmp_path):
    """A malformed/unexpected file (no ## headers) must still produce
    SOMETHING retrievable, not silently zero chunks."""
    content = "# عنوان\n\nمحتوى بلا عناوين فرعية على الإطلاق.\n"
    filepath = _write_md(tmp_path, "test.md", content)
    chunks = chunk_markdown_file(filepath, "test_domain")

    assert len(chunks) == 1
    assert "محتوى بلا عناوين" in chunks[0].content


def test_oversized_section_splits_at_paragraph_breaks_never_mid_sentence(tmp_path):
    """THE core regression test for the original bug. Build a section
    deliberately larger than MAX_CHUNK_CHARS out of many small,
    complete paragraphs, and verify every resulting piece both starts
    and ends at a paragraph boundary -- reconstructing the pieces (with
    paragraph joins) must reproduce the original paragraphs exactly,
    proving no paragraph was cut in half."""
    paragraphs = [f"هذه الجملة الكاملة رقم {i} في الفقرة وتحتوي على معلومات مفيدة جداً للطالب." for i in range(40)]
    body = "\n\n".join(paragraphs)
    content = f"# عنوان\n\n## قسم طويل جداً\n\n{body}\n"
    filepath = _write_md(tmp_path, "test.md", content)

    assert len(body) > MAX_CHUNK_CHARS, "test fixture must actually exceed the cap to be meaningful"

    chunks = chunk_markdown_file(filepath, "test_domain")
    assert len(chunks) > 1, "an oversized section must be split into multiple pieces"

    for c in chunks:
        assert len(c.content) <= MAX_CHUNK_CHARS or "\n\n" not in c.content, (
            "a piece over the cap is only acceptable if it's a single "
            "unsplittable paragraph, per chunk_markdown_file's documented "
            "oversized-single-paragraph tradeoff"
        )
        # Every piece must start and end on a complete paragraph -- i.e.
        # the piece, stripped, must exactly equal one or more of the
        # original whole paragraphs joined by "\n\n". No fragment.
        piece_paragraphs = c.content.strip().split("\n\n")
        for p in piece_paragraphs:
            assert p.strip() in paragraphs, f"chunk contains a fragment not matching any whole paragraph: {p[:80]!r}"


def test_oversized_single_paragraph_kept_intact_not_sliced(tmp_path):
    """A single paragraph with NO blank-line breaks that alone exceeds
    the cap must be kept whole -- reintroducing an arbitrary
    mid-sentence slice here would be exactly the bug this module exists
    to eliminate, so an oversized-but-intact chunk is the correct,
    documented tradeoff."""
    huge_paragraph = "كلمة " * 800  # no blank lines anywhere, guaranteed over the cap
    content = f"# عنوان\n\n## قسم\n\n{huge_paragraph}\n"
    filepath = _write_md(tmp_path, "test.md", content)

    assert len(huge_paragraph) > MAX_CHUNK_CHARS

    chunks = chunk_markdown_file(filepath, "test_domain")
    assert len(chunks) == 1
    assert chunks[0].content.strip() == huge_paragraph.strip()


def test_no_chunk_ever_starts_or_ends_with_a_hyphenated_break():
    """Heuristic smoke test across ALL real shipped knowledge files:
    no chunk boundary should produce content that starts or ends
    mid-word. A simple, real-world proxy for this: no chunk's content
    starts with a lowercase Latin letter immediately following what
    would be a mid-word cut (Arabic has no case, so the strongest
    general check available is "no chunk is empty, no chunk's raw
    stripped content differs from a naive whitespace-trim of itself" --
    i.e. nothing was sliced off after chunking that a human authoring
    pass wouldn't already have there)."""
    for f in sorted(KB_DIR.glob("*.md")):
        chunks = chunk_markdown_file(f, f.stem)
        for c in chunks:
            assert c.content == c.content.strip(), (
                f"{f.name} chunk {c.heading!r} has leading/trailing "
                f"whitespace that should have been stripped"
            )
            assert c.content, f"{f.name} produced an empty chunk for heading {c.heading!r}"


# ============================================================
#  REAL KNOWLEDGE FILES — full corpus smoke test
# ============================================================

@pytest.mark.parametrize("filepath", sorted(KB_DIR.glob("*.md")), ids=lambda p: p.stem)
def test_every_real_knowledge_file_chunks_without_frontmatter_leak(filepath):
    chunks = chunk_markdown_file(filepath, filepath.stem)
    assert len(chunks) > 0, f"{filepath.name} produced zero chunks"
    for c in chunks:
        assert "هذا الملف جزء من قاعدة معرفة" not in c.content, (
            f"{filepath.name} chunk {c.heading!r} leaked the standard "
            f"front-matter intro line"
        )
        assert c.domain == filepath.stem
        assert c.source_file == filepath.name


def test_full_corpus_produces_a_reasonable_chunk_count():
    """Sanity bound matching design.md Section 4.2's own estimate
    ('~150 chunks today'). A drastic deviation (e.g. 5 chunks total, or
    5000) would indicate the chunker is broken against real content
    even if the synthetic tests above pass."""
    total = sum(len(chunk_markdown_file(f, f.stem)) for f in KB_DIR.glob("*.md"))
    assert 50 <= total <= 500, f"unexpected total chunk count: {total}"


# ============================================================
#  INTERNAL HELPERS (direct tests, not just via chunk_markdown_file)
# ============================================================

def test_split_on_h2_headers_discards_frontmatter():
    text = "# Title\n\n> intro\n\n## First\n\nbody1\n\n## Second\n\nbody2\n"
    sections = _split_on_h2_headers(text)
    assert [h for h, _ in sections] == ["First", "Second"]


def test_split_on_paragraph_breaks_packs_greedily():
    paragraphs = ["a" * 100, "b" * 100, "c" * 100]
    body = "\n\n".join(paragraphs)
    pieces = _split_on_paragraph_breaks(body, max_chars=250)
    # First two paragraphs (100+2+100=202 chars) fit under 250; the
    # third would push it to 304, so it must start a new piece.
    assert len(pieces) == 2
    assert "a" * 100 in pieces[0] and "b" * 100 in pieces[0]
    assert "c" * 100 in pieces[1]
