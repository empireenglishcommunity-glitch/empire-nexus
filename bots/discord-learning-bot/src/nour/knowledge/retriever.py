"""Aql (العقل) — Retrieval (Phase A1.5/A1.6).

design.md Section 4.3: role-scoped semantic retrieval over
`knowledge_chunks`. This module is the runtime counterpart to
scripts/embed_knowledge.py (Phase A1.3, which populates the table
offline) — retrieve() never embeds or writes knowledge content
itself, it only embeds the incoming QUERY and reads existing rows.

Defense in depth (design.md Section 4.2): the SQL
`WHERE domain IN (...)` clause inside database.get_chunks_by_domains()
is the role boundary at the data layer. This module's job is to never
pass that function anything except `permissions.get_knowledge_domains(role)` —
see test_nour_retriever.py's A1.7 fault-injection test, which verifies
the DATA LAYER itself still filters correctly even if a caller (by bug
or by a future careless edit) passed an expanded domain list.
"""
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ... import database
from .. import permissions
from ..roles import Role
from .embedder import cosine_similarity, embed_text, unpack_embedding

logger = logging.getLogger("empire-bot.nour.retriever")


@dataclass
class RetrievedChunk:
    id: int
    domain: str
    source_file: str
    heading: str
    content: str
    similarity: float


async def retrieve(query: str, role: Role, top_k: int = 4,
                   discord_id: str = "") -> list[RetrievedChunk]:
    """Role-scoped semantic retrieval per design.md Section 4.3.

    1. Resolve the caller's allowed domains via
       permissions.get_knowledge_domains(role) — NEVER an expanded or
       unfiltered list (see this module's docstring).
    2. Embed the query (RETRIEVAL_QUERY task type — asymmetric vs. the
       RETRIEVAL_DOCUMENT type used when chunks were indexed).
    3. If the embedding call fails (no API key, network error, quota),
       fall back to the OLD keyword-matching tier
       (`nour_concierge._KB_CATEGORIES` logic) — degraded but
       functional, never a hard failure (design.md Section 4.3).
    4. Otherwise, score every allowed-domain chunk by cosine similarity
       in-process and return the top_k.

    Every call is logged to `nour_retrieval_log` (design.md Section 13)
    for later retrieval-quality analysis, regardless of which tier
    (embedding or fallback) actually served the request.
    """
    allowed_domains = permissions.get_knowledge_domains(role)
    if not allowed_domains:
        # Reserved/unpopulated role (ADMIN/MODERATOR/COACH) — no
        # mapping exists yet, so there is nothing to retrieve. Matches
        # permissions.py's "empty means no access, not fallback"
        # convention.
        return []

    query_embedding = await embed_text(query, task_type="RETRIEVAL_QUERY")

    if query_embedding is None:
        logger.warning("Nour retrieve(): embedding unavailable, using keyword fallback")
        chunks = _keyword_fallback(query, allowed_domains, top_k)
        database.log_retrieval(
            discord_id=discord_id, role=role.value, query_text=query,
            top_chunk_ids=[c.id for c in chunks], top_similarity=0.0,
        )
        return chunks

    candidates = database.get_chunks_by_domains(allowed_domains)
    scored: list[tuple[float, dict]] = []
    for row in candidates:
        try:
            vec = unpack_embedding(row["embedding"])
            sim = cosine_similarity(query_embedding, vec)
        except Exception as e:
            logger.error(f"Nour retrieve(): failed to score chunk {row.get('id')}: {e}")
            continue
        scored.append((sim, row))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    top = scored[:top_k]
    results = [
        RetrievedChunk(
            id=row["id"], domain=row["domain"], source_file=row["source_file"],
            heading=row["heading"], content=row["content"], similarity=sim,
        )
        for sim, row in top
    ]

    database.log_retrieval(
        discord_id=discord_id, role=role.value, query_text=query,
        top_chunk_ids=[c.id for c in results],
        top_similarity=results[0].similarity if results else 0.0,
    )
    return results


def _keyword_fallback(query: str, allowed_domains: list[str], top_k: int) -> list[RetrievedChunk]:
    """Degraded-but-functional fallback tier, reusing (not discarding)
    the existing keyword map from nour_concierge.py — design.md
    Section 4.3. Only chunks whose domain is in `allowed_domains` are
    ever considered, so the role boundary holds even in the fallback
    path.
    """
    from ...nour_concierge import _KB_CATEGORIES

    message_lower = query.lower()
    matched_files = []
    for filename, keywords in _KB_CATEGORIES.items():
        if any(kw in message_lower for kw in keywords):
            matched_files.append(filename)

    if not matched_files:
        matched_files = ["faq.md", "system_overview.md"]

    matched_domains = [f[:-3] for f in matched_files if f.endswith(".md")]
    matched_domains = [d for d in matched_domains if d in allowed_domains]
    if not matched_domains:
        # Nothing matched fell inside this role's allowed set — do not
        # silently widen scope; return nothing rather than leak an
        # out-of-scope domain's content.
        return []

    rows = database.get_chunks_by_domains(matched_domains)
    results = [
        RetrievedChunk(
            id=row["id"], domain=row["domain"], source_file=row["source_file"],
            heading=row["heading"], content=row["content"], similarity=0.0,
        )
        for row in rows[:top_k]
    ]
    return results
