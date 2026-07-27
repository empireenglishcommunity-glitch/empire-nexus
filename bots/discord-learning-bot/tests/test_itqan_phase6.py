"""Itqan Phase 6 — outcome delivery routing + side-effects.

Verifies that a finished attempt is routed to the right consequence:
- mastered  → public celebration only (no DM, no owner alert, no SRS churn)
- not_yet   → PRIVATE support DM + missed words re-injected into SRS (due
              today), and the daily flow (streak/points/calendar) is untouched
- flagged   → owner alert only (no public celebration, no not-yet DM)

The Discord/Telegram-touching helpers are monkeypatched to recorders; the SRS
re-inject (pure DB) runs for real so we can assert it.
"""
import pytest

from src import database, itqan_outcomes


@pytest.fixture
def student():
    database.register_member("s1", "Student", "L0")
    return "s1"


@pytest.fixture
def recorders(monkeypatch):
    """Replace the three side-effect helpers with async recorders."""
    calls = {"celebrate": [], "dm": [], "flag": []}

    async def _celebrate(discord_id, level, week, verdict):
        calls["celebrate"].append((discord_id, level, week, verdict))

    async def _dm(discord_id, level, week, verdict, missed, production_missed):
        calls["dm"].append({"missed": missed, "production_missed": production_missed})

    async def _flag(discord_id, level, week, attempt_id, verdict):
        calls["flag"].append((discord_id, level, week, attempt_id))

    monkeypatch.setattr(itqan_outcomes, "_celebrate_champion", _celebrate)
    monkeypatch.setattr(itqan_outcomes, "_support_dm", _dm)
    monkeypatch.setattr(itqan_outcomes, "_notify_owner_flagged", _flag)
    return calls


def _seed_attempt(discord_id, week=2):
    """Create an attempt with 4 items; mark vocab+listening wrong, pron right,
    speaking wrong. Returns attempt_id."""
    att = database.itqan_create_attempt(discord_id, "L0", week, "seed")
    aid = att["id"]
    items = [
        {"item_no": 1, "skill": "vocab", "source_week": week,
         "payload": {"expected": "book", "prompt_ar": "كتاب"}},
        {"item_no": 2, "skill": "listening", "source_week": week,
         "payload": {"say_en": "water", "expected": "ماء"}},
        {"item_no": 3, "skill": "pronunciation", "source_week": week,
         "payload": {"word": "apple", "expected": "apple"}},
        {"item_no": 4, "skill": "speaking", "source_week": week,
         "payload": {"target_words": ["book", "water"]}},
    ]
    database.itqan_insert_items(aid, discord_id, items)
    database.itqan_save_item(aid, 1, "wrong", correct=False)
    database.itqan_save_item(aid, 2, "wrong", correct=False)
    database.itqan_save_item(aid, 3, "apple", correct=True)
    database.itqan_save_item(aid, 4, "transcript", correct=False)
    return aid


# ---- streak math (pure) ---------------------------------------------------

def test_week_streak_counts_consecutive():
    assert itqan_outcomes._week_streak({1, 2, 3}, 3) == 3
    assert itqan_outcomes._week_streak({1, 3}, 3) == 1      # gap at 2
    assert itqan_outcomes._week_streak({2, 3, 4}, 4) == 3
    assert itqan_outcomes._week_streak(set(), 2) == 0


# ---- mastered -------------------------------------------------------------

@pytest.mark.asyncio
async def test_mastered_celebrates_only(student, recorders):
    aid = _seed_attempt(student)
    verdict = {"status": "scored", "result": "mastered", "distinction": False,
               "mastery_pct": 85.0, "consistency_pct": 100.0}
    await itqan_outcomes.deliver_outcome(student, "L0", 2, aid, verdict)

    assert len(recorders["celebrate"]) == 1
    assert recorders["dm"] == []
    assert recorders["flag"] == []
    # A pass does NOT churn the SRS queue.
    assert database.get_due_reviews(student, limit=50) == []


# ---- not_yet --------------------------------------------------------------

@pytest.mark.asyncio
async def test_not_yet_dms_privately_and_reinjects(student, recorders):
    aid = _seed_attempt(student)
    verdict = {"status": "scored", "result": "not_yet", "distinction": False,
               "mastery_pct": 45.0, "consistency_pct": 90.0}
    await itqan_outcomes.deliver_outcome(student, "L0", 2, aid, verdict)

    # Private DM only — never public, never owner.
    assert len(recorders["dm"]) == 1
    assert recorders["celebrate"] == []
    assert recorders["flag"] == []

    dm = recorders["dm"][0]
    missed_words = {w for (w, _m) in dm["missed"]}
    assert missed_words == {"book", "water"}       # objective misses only
    assert dm["production_missed"] is True          # speaking was wrong

    # Missed words were re-injected into SRS, due today.
    due_words = {r["word"] for r in database.get_due_reviews(student, limit=50)}
    assert "book" in due_words and "water" in due_words
    assert "apple" not in due_words                 # the correct one isn't


@pytest.mark.asyncio
async def test_not_yet_does_not_touch_daily_flow(student, recorders):
    before = database.get_member(student)
    aid = _seed_attempt(student)
    verdict = {"status": "scored", "result": "not_yet",
               "mastery_pct": 30.0, "consistency_pct": 50.0}
    await itqan_outcomes.deliver_outcome(student, "L0", 2, aid, verdict)

    after = database.get_member(student)
    assert after["current_streak"] == before["current_streak"]
    assert after["total_points"] == before["total_points"]
    # No daily calendar completion was written by the outcome.
    assert database.get_calendar_mastery(student, "L0") == {}


# ---- flagged --------------------------------------------------------------

@pytest.mark.asyncio
async def test_flagged_notifies_owner_only(student, recorders):
    aid = _seed_attempt(student)
    verdict = {"status": "flagged", "result": "not_yet",
               "mastery_pct": 69.0, "consistency_pct": 90.0}
    await itqan_outcomes.deliver_outcome(student, "L0", 2, aid, verdict)

    assert len(recorders["flag"]) == 1
    assert recorders["celebrate"] == []
    assert recorders["dm"] == []
    # Flagged attempts don't re-inject either (owner decides first).
    assert database.get_due_reviews(student, limit=50) == []


@pytest.mark.asyncio
async def test_flagged_mastered_is_not_celebrated(student, recorders):
    """A borderline pass (mastered but flagged) must go to the owner, NOT the
    public Champions channel."""
    aid = _seed_attempt(student)
    verdict = {"status": "flagged", "result": "mastered", "distinction": False,
               "mastery_pct": 72.0, "consistency_pct": 90.0}
    await itqan_outcomes.deliver_outcome(student, "L0", 2, aid, verdict)

    assert len(recorders["flag"]) == 1
    assert recorders["celebrate"] == []
