"""Tests for src/database.py's Aql (#15) Phase A1 knowledge-chunk and
retrieval-observability functions: insert_knowledge_chunk,
clear_knowledge_chunks, get_chunks_by_domains, count_knowledge_chunks,
log_retrieval.

These tables were created inert in Phase A0 (see test_nour_permissions.py
for the permission-boundary side of this); this file is the first thing
that actually reads/writes them, ahead of the embed script (A1.3) and
retrieve() (A1.6) that will depend on them being correct.
"""
import json

import pytest

from src import database


def _fake_embedding(n: int = 768) -> bytes:
    """A deterministic, cheap stand-in for a real packed embedding --
    these tests only care that bytes round-trip through the BLOB
    column correctly, not that they're a real vector (embedder.py's
    own tests cover pack/unpack correctness)."""
    return bytes(range(256)) * (n // 256 + 1)


# ============================================================
#  insert_knowledge_chunk / count_knowledge_chunks
# ============================================================

def test_insert_knowledge_chunk_returns_new_id():
    new_id = database.insert_knowledge_chunk(
        domain="daily_tasks", source_file="daily_tasks.md",
        heading="المهام اليومية", content="محتوى تجريبي",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )
    assert isinstance(new_id, int)
    assert new_id > 0


def test_insert_knowledge_chunk_ids_increment():
    id1 = database.insert_knowledge_chunk(
        domain="faq", source_file="faq.md", heading="س1", content="ج1",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )
    id2 = database.insert_knowledge_chunk(
        domain="faq", source_file="faq.md", heading="س2", content="ج2",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )
    assert id2 > id1


def test_count_knowledge_chunks_empty_db_is_zero():
    assert database.count_knowledge_chunks() == 0


def test_count_knowledge_chunks_total():
    for i in range(3):
        database.insert_knowledge_chunk(
            domain="faq", source_file="faq.md", heading=f"س{i}", content="ج",
            embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
        )
    assert database.count_knowledge_chunks() == 3


def test_count_knowledge_chunks_filtered_by_domain():
    database.insert_knowledge_chunk(
        domain="faq", source_file="faq.md", heading="س", content="ج",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )
    database.insert_knowledge_chunk(
        domain="owner_ops", source_file="owner_ops.md", heading="عملية", content="محتوى",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )
    assert database.count_knowledge_chunks("faq") == 1
    assert database.count_knowledge_chunks("owner_ops") == 1
    assert database.count_knowledge_chunks("nonexistent_domain") == 0


# ============================================================
#  clear_knowledge_chunks
# ============================================================

def test_clear_knowledge_chunks_all():
    database.insert_knowledge_chunk(
        domain="faq", source_file="faq.md", heading="س", content="ج",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )
    database.insert_knowledge_chunk(
        domain="owner_ops", source_file="owner_ops.md", heading="عملية", content="محتوى",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )
    removed = database.clear_knowledge_chunks()
    assert removed == 2
    assert database.count_knowledge_chunks() == 0


def test_clear_knowledge_chunks_single_domain_leaves_others_untouched():
    database.insert_knowledge_chunk(
        domain="faq", source_file="faq.md", heading="س", content="ج",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )
    database.insert_knowledge_chunk(
        domain="owner_ops", source_file="owner_ops.md", heading="عملية", content="محتوى",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )
    removed = database.clear_knowledge_chunks("faq")
    assert removed == 1
    assert database.count_knowledge_chunks("faq") == 0
    assert database.count_knowledge_chunks("owner_ops") == 1


def test_clear_knowledge_chunks_on_empty_db_returns_zero():
    assert database.clear_knowledge_chunks() == 0


# ============================================================
#  get_chunks_by_domains
# ============================================================

def test_get_chunks_by_domains_empty_list_returns_empty():
    """Matches permissions.py's own 'empty means no access' semantics
    for unpopulated future roles -- an empty domain list must never be
    silently treated as 'all domains'."""
    database.insert_knowledge_chunk(
        domain="faq", source_file="faq.md", heading="س", content="ج",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )
    assert database.get_chunks_by_domains([]) == []


def test_get_chunks_by_domains_filters_correctly():
    database.insert_knowledge_chunk(
        domain="faq", source_file="faq.md", heading="س", content="ج",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )
    database.insert_knowledge_chunk(
        domain="owner_ops", source_file="owner_ops.md", heading="عملية", content="محتوى",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )
    database.insert_knowledge_chunk(
        domain="commands", source_file="commands.md", heading="أمر", content="محتوى",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )

    student_rows = database.get_chunks_by_domains(["faq", "commands"])
    domains_returned = {r["domain"] for r in student_rows}
    assert domains_returned == {"faq", "commands"}
    assert "owner_ops" not in domains_returned
    assert len(student_rows) == 2


def test_get_chunks_by_domains_returns_full_row_dicts():
    database.insert_knowledge_chunk(
        domain="faq", source_file="faq.md", heading="عنوان", content="محتوى الفحص",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )
    rows = database.get_chunks_by_domains(["faq"])
    assert len(rows) == 1
    row = rows[0]
    assert row["heading"] == "عنوان"
    assert row["content"] == "محتوى الفحص"
    assert row["source_file"] == "faq.md"
    assert row["embedding_model"] == "gemini-embedding-001"
    assert isinstance(row["embedding"], bytes)
    assert "id" in row and "updated_at" in row


def test_get_chunks_by_domains_nonexistent_domain_returns_empty():
    database.insert_knowledge_chunk(
        domain="faq", source_file="faq.md", heading="س", content="ج",
        embedding=_fake_embedding(), embedding_model="gemini-embedding-001",
    )
    assert database.get_chunks_by_domains(["nonexistent_domain"]) == []


# ============================================================
#  log_retrieval
# ============================================================

def test_log_retrieval_does_not_raise():
    database.log_retrieval(
        discord_id="u1", role="student", query_text="كيف أرسل مهمتي اليومية؟",
        top_chunk_ids=[1, 2, 3], top_similarity=0.87, used_chunk_id=1,
    )


def test_log_retrieval_persists_row_correctly():
    database.log_retrieval(
        discord_id="u1", role="student", query_text="test query",
        top_chunk_ids=[5, 9], top_similarity=0.42,
    )
    conn = database._connect()
    row = conn.execute("SELECT * FROM nour_retrieval_log WHERE discord_id='u1'").fetchone()
    conn.close()
    assert row is not None
    assert row["role"] == "student"
    assert row["query_text"] == "test query"
    assert json.loads(row["top_chunk_ids"]) == [5, 9]
    assert row["top_similarity"] == 0.42
    assert row["used_chunk_id"] is None  # not passed -> defaults to NULL


def test_log_retrieval_truncates_long_query_text():
    long_query = "س" * 1000
    database.log_retrieval(
        discord_id="u1", role="owner", query_text=long_query,
        top_chunk_ids=[], top_similarity=0.0,
    )
    conn = database._connect()
    row = conn.execute("SELECT * FROM nour_retrieval_log WHERE discord_id='u1'").fetchone()
    conn.close()
    assert len(row["query_text"]) == 500
