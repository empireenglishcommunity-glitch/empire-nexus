"""Aql (العقل) — Knowledge Retrieval Subsystem.

design.md Section 4. Replaces nour_concierge.py's keyword-substring
matching (_KB_CATEGORIES) with real semantic search over a chunked,
embedded knowledge base, stored in SQLite (no hosted vector DB, per
the $0 budget constraint -- design.md Section 4.2's numeric
justification).
"""
