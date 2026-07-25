"""Changelog / "What's New" — student-facing release notes.

Single source of truth (bot DB settings JSON). Consumed by:
- the `/maintenance end` broadcast ("we're back — what's new"),
- `GET /api/changelog` → the practice-page "✨ What's New" toast and the
  guide's "Latest updates / آخر التحديثات" section,
- the ops `/changelog` command.

Entries are `{id, date, text}`, newest first, capped to the most recent N.
`id` is a monotonic timestamp used by the page to show each update once.
"""
import json
import logging
import time

from . import database

logger = logging.getLogger("empire-bot.changelog")

_KEY = "changelog_entries"
_KEEP = 50


def get_entries(limit: int = 10) -> list[dict]:
    """Most recent changelog entries, newest first."""
    try:
        entries = json.loads(database.get_setting(_KEY, "[]"))
        if not isinstance(entries, list):
            entries = []
    except Exception:
        entries = []
    return entries[: max(0, limit)]


def latest() -> dict:
    entries = get_entries(1)
    return entries[0] if entries else {}


def add_entry(text: str) -> dict:
    """Publish a new 'What's New' entry. Returns the entry (or {} if empty)."""
    text = (text or "").strip()
    if not text:
        return {}
    entries = get_entries(limit=_KEEP)
    # Ensure a strictly-increasing id even if two entries land in one second.
    new_id = int(time.time())
    if entries:
        try:
            new_id = max(new_id, int(entries[0].get("id", 0)) + 1)
        except Exception:
            pass
    entry = {
        "id": new_id,
        "date": database._today_local().isoformat(),
        "text": text,
    }
    entries.insert(0, entry)
    try:
        database.set_setting(_KEY, json.dumps(entries[:_KEEP]))
    except Exception as e:
        logger.warning(f"changelog: add_entry failed: {e}")
        return {}
    logger.info(f"changelog: published entry {new_id}: {text[:80]!r}")
    return entry
