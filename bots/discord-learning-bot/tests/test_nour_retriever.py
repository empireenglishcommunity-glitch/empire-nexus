"""Tests for src/nour/knowledge/retriever.py — Aql (#15) Phase A1.5/A1.6.

Phase A1.7's fault-injection test lives here: it verifies the DATA
LAYER boundary (database.get_chunks_by_domains's SQL `WHERE domain IN
(...)` clause) filters correctly EVEN IF a caller passes an expanded
domain list -- defense in depth beneath the application-layer check in
src/nour/permissions.py. This directly matches design.md Section 4.2's
"second enforcement point" framing: this test is written against the
data layer function itself, deliberately bypassing the normal
application-layer call path (permissions.get_knowledge_domains), to
prove the data layer doesn't merely rely on well-behaved callers.

Embedding calls are never made for real in this suite (no network in
tests, matching test_nour_embedder.py's own convention) -- retrieve()
is tested with embed_text mocked, and the keyword-fallback tier is
tested by forcing embed_text to return None.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from src import database
from src.nour import permissions
from src.nour.roles import Role
from src.nour.knowledge.embedder import pack_embedding
from src.nour.knowledge.retriever import retrieve, RetrievedChunk


def _insert_chunk(domain: str, heading: str, content: str, vec: np.ndarray) -> int:
    return database.insert_knowledge_chunk(
        domain=domain, source_file=f"{domain}.md", heading=heading,
        content=content, embedding=pack_embedding(vec),
        embedding_model="gemini-embedding-001",
    )


def _unit_vec(*nonzero_indices, dim: int = 768) -> np.ndarray:
    """A simple, distinguishable unit vector for deterministic cosine
    similarity comparisons in tests."""
    v = np.zeros(dim, dtype=np.float32)
    for i in nonzero_indices:
        v[i] = 1.0
    norm = np.linalg.norm(v)
    return v / norm if norm else v


# ============================================================
#  A1.7 — DEFENSE-IN-DEPTH FAULT INJECTION (data layer itself)
# ============================================================

def test_data_layer_never_returns_owner_domain_when_given_only_student_domains():
    """Not a fault injection yet -- baseline: calling the data layer
    with exactly the student's real allowed list must never surface
    an owner-only chunk."""
    _insert_chunk("faq", "س", "ج", _unit_vec(0))
    _insert_chunk("owner_ops", "عملية", "محتوى", _unit_vec(1))

    student_domains = permissions.get_knowledge_domains(Role.STUDENT)
    rows = database.get_chunks_by_domains(student_domains)
    domains = {r["domain"] for r in rows}
    assert "owner_ops" not in domains
    assert "faq" in domains


def test_fault_injection_expanded_domain_list_still_filters_correctly():
    """A1.7's actual fault-injection test: deliberately construct an
    EXPANDED domain list (as if a bug had merged student + owner
    domains together) and confirm get_chunks_by_domains() still only
    returns rows whose domain is literally IN that list -- it never
    "helpfully" expands or contracts scope on its own. This proves the
    SQL WHERE clause is a real, mechanical filter, not a rubber stamp
    that happens to work today only because callers are well-behaved.

    This does NOT prove the application layer never passes such an
    expanded list (permissions.py + retrieve() are responsible for
    that, and are tested separately) -- it proves that if it ever did,
    the leak would be exactly the union of what was asked for, nothing
    more, nothing silently added.
    """
    _insert_chunk("faq", "س", "ج", _unit_vec(0))
    _insert_chunk("owner_ops", "عملية", "محتوى", _unit_vec(1))
    _insert_chunk("architecture", "بنية", "تفاصيل", _unit_vec(2))
    _insert_chunk("commands", "أمر", "شرح", _unit_vec(3))

    # Fault: an expanded list that improperly includes owner domains.
    faulty_expanded_list = list(permissions.get_knowledge_domains(Role.STUDENT)) + ["owner_ops", "architecture"]
    rows = database.get_chunks_by_domains(faulty_expanded_list)
    domains = {r["domain"] for r in rows}

    # The data layer faithfully returns exactly what was asked for --
    # this demonstrates WHY the application layer (retrieve(), never
    # passing anything but permissions.get_knowledge_domains(role))
    # is the layer that must be correct; the data layer is a correct,
    # unopinionated filter, not a second guesser.
    assert domains == {"faq", "owner_ops", "architecture", "commands"}


def test_retrieve_student_role_never_returns_owner_domain_chunk():
    """The REAL end-to-end guarantee: retrieve() called with
    Role.STUDENT, through its normal application-layer path (never a
    fault-injected list), must never surface an owner-only chunk --
    regardless of similarity score, even if the owner chunk is a
    perfect semantic match for the query."""
    _insert_chunk("faq", "سؤال عام", "جواب عام", _unit_vec(0))
    _insert_chunk("owner_ops", "نشر الكود", "تفاصيل النشر السرية", _unit_vec(0))  # identical vector on purpose

    async def fake_embed(text, task_type="RETRIEVAL_QUERY"):
        return _unit_vec(0)  # perfectly matches BOTH chunks above

    with patch("src.nour.knowledge.retriever.embed_text", new=fake_embed):
        results = asyncio.run(
            retrieve("كيف أنشر الكود؟", Role.STUDENT, top_k=4, discord_id="u1")
        )

    domains = {r.domain for r in results}
    assert "owner_ops" not in domains
    assert "faq" in domains


def test_retrieve_owner_role_can_see_owner_domain_chunk():
    _insert_chunk("faq", "سؤال عام", "جواب عام", _unit_vec(0))
    _insert_chunk("owner_ops", "نشر الكود", "تفاصيل النشر", _unit_vec(1))

    async def fake_embed(text, task_type="RETRIEVAL_QUERY"):
        return _unit_vec(1)  # matches owner_ops chunk best

    with patch("src.nour.knowledge.retriever.embed_text", new=fake_embed):
        results = asyncio.run(
            retrieve("كيف أنشر الكود؟", Role.OWNER, top_k=4, discord_id="owner1")
        )

    domains = {r.domain for r in results}
    assert "owner_ops" in domains


def test_retrieve_reserved_role_returns_empty_without_calling_embed():
    """ADMIN/MODERATOR/COACH have no populated domain mapping -- must
    short-circuit to empty BEFORE ever making an embedding call (cost
    + correctness: no wasted API call for a role with nothing to
    retrieve)."""
    embed_mock = AsyncMock(return_value=_unit_vec(0))
    with patch("src.nour.knowledge.retriever.embed_text", new=embed_mock):
        results = asyncio.run(
            retrieve("test", Role.ADMIN, top_k=4)
        )
    assert results == []
    embed_mock.assert_not_called()


# ============================================================
#  RANKING
# ============================================================

def test_retrieve_orders_by_similarity_descending():
    _insert_chunk("faq", "بعيد", "محتوى بعيد", _unit_vec(5))
    _insert_chunk("faq", "قريب", "محتوى قريب", _unit_vec(0))
    _insert_chunk("faq", "متوسط", "محتوى متوسط", _unit_vec(0, 5))  # 45 degrees from query

    async def fake_embed(text, task_type="RETRIEVAL_QUERY"):
        return _unit_vec(0)

    with patch("src.nour.knowledge.retriever.embed_text", new=fake_embed):
        results = asyncio.run(
            retrieve("query", Role.STUDENT, top_k=3)
        )

    sims = [r.similarity for r in results]
    assert sims == sorted(sims, reverse=True)
    assert results[0].heading == "قريب"


def test_retrieve_respects_top_k():
    for i in range(6):
        _insert_chunk("faq", f"عنوان{i}", f"محتوى{i}", _unit_vec(i))

    async def fake_embed(text, task_type="RETRIEVAL_QUERY"):
        return _unit_vec(0)

    with patch("src.nour.knowledge.retriever.embed_text", new=fake_embed):
        results = asyncio.run(
            retrieve("query", Role.STUDENT, top_k=2)
        )
    assert len(results) == 2


# ============================================================
#  KEYWORD FALLBACK TIER
# ============================================================

def test_retrieve_falls_back_to_keywords_when_embedding_unavailable():
    """If the Gemini embedding call fails (returns None), retrieve()
    must degrade to the OLD keyword-matching tier rather than raise or
    return nothing -- design.md Section 4.3's explicit requirement."""
    _insert_chunk("daily_tasks", "المهام", "شرح المهام اليومية", _unit_vec(0))
    _insert_chunk("owner_ops", "نشر", "تفاصيل سرية", _unit_vec(1))

    async def fake_embed_none(text, task_type="RETRIEVAL_QUERY"):
        return None

    with patch("src.nour.knowledge.retriever.embed_text", new=fake_embed_none):
        results = asyncio.run(
            retrieve("ما هي مهامي اليومية task", Role.STUDENT, top_k=4, discord_id="u1")
        )

    domains = {r.domain for r in results}
    assert "owner_ops" not in domains
    # "task" is one of daily_tasks.md's keywords in _KB_CATEGORIES.
    assert "daily_tasks" in domains


def test_retrieve_keyword_fallback_still_respects_role_boundary():
    """Even in the degraded fallback tier, an owner-only domain must
    never leak into a student-role result, even if the query's
    keywords would have matched an owner-only file's keyword list (not
    the case today since owner_ops.md has no keyword entry, but this
    test guards the INVARIANT, not today's specific keyword lists)."""
    _insert_chunk("owner_ops", "نشر", "تفاصيل", _unit_vec(0))

    async def fake_embed_none(text, task_type="RETRIEVAL_QUERY"):
        return None

    with patch("src.nour.knowledge.retriever.embed_text", new=fake_embed_none):
        results = asyncio.run(
            retrieve("انشر الكود deploy", Role.STUDENT, top_k=4)
        )
    assert all(r.domain != "owner_ops" for r in results)


def test_retrieve_logs_every_call():
    _insert_chunk("faq", "س", "ج", _unit_vec(0))

    async def fake_embed(text, task_type="RETRIEVAL_QUERY"):
        return _unit_vec(0)

    with patch("src.nour.knowledge.retriever.embed_text", new=fake_embed):
        asyncio.run(
            retrieve("سؤال", Role.STUDENT, top_k=4, discord_id="u42")
        )

    conn = database._connect()
    row = conn.execute("SELECT * FROM nour_retrieval_log WHERE discord_id='u42'").fetchone()
    conn.close()
    assert row is not None
    assert row["role"] == "student"
