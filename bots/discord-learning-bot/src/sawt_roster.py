"""Empire English Chronicles — student cast roster (Phase 5).

Turns willing learners into brief, friendly CAMEO characters in the daily story,
under strict safety rules (spec R8):

  * FIRST NAME ONLY, and only for the bot's own community (single GUILD_ID) — so
    nothing beyond a given name ever appears, and never across communities (R8.8).
  * ZERO gender inference: a learner is castable only if their gender is KNOWN
    ('male'/'female') and they never get a guessed gender. Unknown ⇒ not cast
    (R8.2/R8.3, P4).
  * OPT-OUT is always honoured (R8.6).
  * FAIR ROTATION by least-recently-featured, so the same few names don't recur
    (R8.5). Bookkeeping advances ONLY on an EMITTED (gate-passed) episode.
  * GRACEFUL DEGRADATION: an empty/idle roster simply yields NO names, and the
    daily episode is written name-free and never blocks (R8.4).

This module is the single seam the generator/entry point uses. It NEVER raises to
its callers — any internal problem degrades to "no cameo names", because a missing
cameo must never stop the daily episode.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("empire-bot.sawt.roster")

# How many learner cameos to feature in one episode. Kept small on purpose: a
# cameo is a warm background beat, not the plot, and a learner episode must still
# read cleanly for the level. Overridable if the owner wants more.
DEFAULT_CAMEO_COUNT = 2


def _db():
    """Import the DB layer lazily so importing this module never hard-depends on a
    ready database (tests, tooling, the offline job all import cleanly)."""
    from src import database
    return database


def seed_from_members(only_gendered: bool = True) -> int:
    """Populate the story roster from `members`, seeding an entry for every ACTIVE
    member whose gender is KNOWN. Returns the number of rows seeded/updated.

    Seeded rows are UNCONFIRMED: they do not become castable until the owner
    reviews them (confirm flow, task 5.2). Members with an unknown/empty gender are
    SKIPPED entirely — they are never given a guessed gender, so they are simply
    not eligible until they set one (R8.2/R8.3).

    `story_name` is seeded as the FIRST token of `discord_name` (first name only,
    R8.8); the owner can correct it in the review flow.
    """
    db = _db()
    seeded = 0
    try:
        for m in db.all_active_members():
            gender = (m.get("gender") or "").strip().lower()
            if only_gendered and gender not in ("male", "female"):
                continue
            display = (m.get("discord_name") or "").strip()
            first = display.split()[0] if display else ""
            if not first:
                continue
            # Do not clobber a name/gender the owner already CONFIRMED; only seed
            # rows that don't exist yet or are still unconfirmed.
            existing = {r["discord_id"]: r for r in db.get_story_roster()}
            row = existing.get(str(m["discord_id"]))
            if row and int(row.get("confirmed", 0)) == 1:
                continue
            if db.upsert_story_roster(str(m["discord_id"]), first, gender,
                                      confirmed=False):
                seeded += 1
    except Exception:                                            # noqa: BLE001
        logger.exception("seed_from_members failed; roster left unchanged")
    return seeded


def select_cameos(count: int = DEFAULT_CAMEO_COUNT,
                  gender: Optional[str] = None) -> list[dict]:
    """Pick up to `count` learner cameos for the next episode, LEAST-RECENTLY-
    FEATURED first (fair rotation, R8.5). Optionally constrain to a single
    `gender` ('male'/'female') — e.g. to match a specific guest voice.

    Returns a list of dicts: {discord_id, story_name, gender}. Returns [] on ANY
    problem or an empty roster, so the caller degrades to a name-free episode and
    never blocks (R8.4).
    """
    if count <= 0:
        return []
    try:
        rows = _db().eligible_story_roster()
    except Exception:                                            # noqa: BLE001
        logger.exception("select_cameos: roster read failed; no cameos this episode")
        return []
    picked = []
    want = (gender or "").strip().lower() or None
    for r in rows:
        g = (r.get("gender") or "").strip().lower()
        # Defence in depth: never cast an unknown gender even if a bad row slips in.
        if g not in ("male", "female"):
            continue
        if want and g != want:
            continue
        name = (r.get("story_name") or "").strip()
        if not name:
            continue
        picked.append({"discord_id": str(r["discord_id"]),
                       "story_name": name, "gender": g})
        if len(picked) >= count:
            break
    return picked


def cameo_names(cameos: list[dict]) -> list[str]:
    """Just the first names, for the validator's dignity/privacy checks."""
    return [c["story_name"] for c in (cameos or []) if c.get("story_name")]


def record_featured(cameos: list[dict]) -> None:
    """Advance rotation bookkeeping for cameos that appeared in an EMITTED episode.
    Call ONLY after the episode passed the gate and was committed (R9.3), so a
    failed render never consumes a learner's turn. Never raises."""
    ids = [c.get("discord_id") for c in (cameos or []) if c.get("discord_id")]
    if not ids:
        return
    try:
        _db().mark_story_featured(ids)
    except Exception:                                            # noqa: BLE001
        logger.exception("record_featured failed; rotation not advanced this run")
