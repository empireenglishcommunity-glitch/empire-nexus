"""Tests for Aql (#15) Phase A2 — Owner-Only Knowledge Domains.

A2.6's explicit requirement: re-run A0.8's permission boundary test
philosophy, but now against the 4 REAL new owner-only knowledge files
written in this phase (architecture.md, database_schema.md,
deployment_runbook.md, flag_registry_reference.md) — confirming they
are retrievable for Role.OWNER and structurally unreachable for
Role.STUDENT, exactly the same way the original 11 student-domain
files were verified in Phase A1.

This does NOT re-test the generic domain-filtering mechanism itself
(test_nour_permissions.py and test_nour_retriever.py already cover
that exhaustively) — it verifies that THESE SPECIFIC 4 new files,
with their real content, actually chunk into the domain names
permissions.py expects, and that the boundary holds against them by
name, not just in the abstract.
"""
from pathlib import Path

import numpy as np
import pytest

from src import database
from src.nour import permissions
from src.nour.roles import Role
from src.nour.knowledge.chunker import chunk_markdown_file
from src.nour.knowledge.embedder import pack_embedding

KB_OWNER_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "nour_knowledge_owner"
)

# The 4 real files written in Phase A2 (A2.1-A2.4), and the domain name
# each MUST produce (its filename stem) -- these must be a subset of
# permissions.py's _OWNER_ONLY_DOMAINS, checked explicitly below rather
# than assumed.
A2_OWNER_FILES = [
    "architecture.md",
    "database_schema.md",
    "deployment_runbook.md",
    "flag_registry_reference.md",
]


def _index_real_owner_files():
    """Chunk (no real embedding call -- a random unit vector stands in,
    same convention as test_nour_retriever.py's manual QA run) every
    real A2 owner file into the knowledge_chunks table."""
    for filename in A2_OWNER_FILES:
        filepath = KB_OWNER_DIR / filename
        domain = filepath.stem
        for c in chunk_markdown_file(filepath, domain):
            vec = np.random.rand(768).astype(np.float32)
            database.insert_knowledge_chunk(
                domain=c.domain, source_file=c.source_file, heading=c.heading,
                content=c.content, embedding=pack_embedding(vec),
                embedding_model="gemini-embedding-001",
            )


# ============================================================
#  A2.1-A2.4: the real files exist and chunk into the RIGHT domains
# ============================================================

def test_all_four_a2_files_exist():
    for filename in A2_OWNER_FILES:
        assert (KB_OWNER_DIR / filename).exists(), f"missing {filename}"


def test_all_four_a2_files_produce_nonempty_chunks():
    for filename in A2_OWNER_FILES:
        filepath = KB_OWNER_DIR / filename
        chunks = chunk_markdown_file(filepath, filepath.stem)
        assert len(chunks) > 0, f"{filename} produced zero chunks"
        for c in chunks:
            assert c.content.strip(), f"{filename} produced an empty chunk"


def test_a2_domain_names_are_registered_as_owner_only_in_permissions():
    """Each of the 4 real files' domain (filename stem) must already
    be present in permissions.py's owner-only domain list -- this was
    pre-registered in Phase A0 (ahead of the content existing, per
    that phase's own stated convention), so this test is really
    confirming A0 and A2 agree on domain naming, not discovering it."""
    owner_domains = set(permissions.get_knowledge_domains(Role.OWNER))
    for filename in A2_OWNER_FILES:
        domain = Path(filename).stem
        assert domain in owner_domains, (
            f"domain '{domain}' (from {filename}) is not in "
            f"KNOWLEDGE_DOMAINS[Role.OWNER] -- A2 content was written "
            f"for a domain name A0 never reserved"
        )


def test_a2_domain_names_are_absent_from_student_domains():
    student_domains = set(permissions.get_knowledge_domains(Role.STUDENT))
    for filename in A2_OWNER_FILES:
        domain = Path(filename).stem
        assert domain not in student_domains, (
            f"domain '{domain}' (from {filename}) leaked into "
            f"KNOWLEDGE_DOMAINS[Role.STUDENT] -- this would make "
            f"owner-only content retrievable by students"
        )


# ============================================================
#  A2.6: re-run the permission-boundary test against REAL indexed
#  content from these 4 new files (not synthetic placeholder chunks)
# ============================================================

def test_owner_role_can_retrieve_every_new_a2_domain():
    """After indexing the real files, database.get_chunks_by_domains()
    called with the OWNER's real domain list must return at least one
    chunk from EVERY one of the 4 new domains -- proves the content
    is actually reachable for the owner, not just theoretically
    permitted."""
    _index_real_owner_files()

    owner_domains = permissions.get_knowledge_domains(Role.OWNER)
    rows = database.get_chunks_by_domains(owner_domains)
    domains_found = {r["domain"] for r in rows}

    for filename in A2_OWNER_FILES:
        domain = Path(filename).stem
        assert domain in domains_found, (
            f"owner-role retrieval never surfaced any chunk from "
            f"domain '{domain}' despite it being indexed and owner-allowed"
        )


def test_student_role_can_never_retrieve_any_new_a2_domain():
    """The A0.8-style boundary test, re-run against these specific 4
    real domains: database.get_chunks_by_domains() called with the
    STUDENT's real domain list must return ZERO chunks from any of
    the 4 new owner-only domains, even though they are indexed and
    present in the same table."""
    _index_real_owner_files()

    student_domains = permissions.get_knowledge_domains(Role.STUDENT)
    rows = database.get_chunks_by_domains(student_domains)
    domains_found = {r["domain"] for r in rows}

    for filename in A2_OWNER_FILES:
        domain = Path(filename).stem
        assert domain not in domains_found, (
            f"student-role retrieval surfaced a chunk from owner-only "
            f"domain '{domain}' -- boundary breach"
        )


def test_student_domains_still_intact_after_a2(monkeypatch):
    """Re-verify A1's original student domains are STILL correctly
    retrievable after A2's new owner-only content has been added to
    the same table -- confirms A2 was additive and didn't accidentally
    disturb the pre-existing student-domain retrieval path."""
    _index_real_owner_files()
    database.insert_knowledge_chunk(
        domain="faq", source_file="faq.md", heading="سؤال", content="جواب",
        embedding=pack_embedding(np.random.rand(768).astype(np.float32)),
        embedding_model="gemini-embedding-001",
    )

    student_domains = permissions.get_knowledge_domains(Role.STUDENT)
    rows = database.get_chunks_by_domains(student_domains)
    domains_found = {r["domain"] for r in rows}
    assert "faq" in domains_found


def test_flag_registry_reference_content_matches_generator_output():
    """A2.4's generator script must be the actual source of this
    file's content -- regenerating it must produce byte-identical
    output (i.e. the committed file is not stale relative to
    flag_registry.py). Uses the generator's own --check mode via
    direct import rather than shelling out, to keep this a fast unit
    test."""
    import importlib
    import sys
    scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
    sys.path.insert(0, scripts_dir)
    try:
        gen = importlib.import_module("generate_flag_reference")
        importlib.reload(gen)
        expected = gen.generate_markdown()
    finally:
        sys.path.remove(scripts_dir)

    actual = (KB_OWNER_DIR / "flag_registry_reference.md").read_text(encoding="utf-8")
    assert actual == expected, (
        "data/nour_knowledge_owner/flag_registry_reference.md is stale -- "
        "run scripts/generate_flag_reference.py to regenerate it"
    )
