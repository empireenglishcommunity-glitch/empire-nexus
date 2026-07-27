"""Itqan Phase 10 — status report / due detection, manual-pass celebration."""
import pytest

from src import assessment, database, itqan_outcomes


@pytest.fixture
def cohort(monkeypatch):
    for did, name in [("a", "Alice"), ("b", "Bob"), ("c", "Cara")]:
        database.register_member(did, name, "L0")
    monkeypatch.setattr(database, "member_week_number", lambda did: 2)
    core = database.PRACTICE_EXERCISES

    def _full(weeks):
        cal = {}
        for w in weeks:
            for d in range(1, 8):
                cal[(w, d)] = {"day_tier": 1, "exercises": {c: 1 for c in core}}
        return cal

    cals = {
        "a": _full([1, 2]),                                    # both weeks done
        "b": {**_full([1]), **{(2, d): {"day_tier": 1} for d in range(1, 4)}},  # wk1 done, wk2 3/7
        "c": {},                                               # nothing done
    }
    monkeypatch.setattr(database, "get_calendar_mastery", lambda did, lvl: cals.get(did, {}))


# ---- status report --------------------------------------------------------

def test_status_due_and_in_progress(cohort):
    rep = database.itqan_status_report("L0")
    by = {r["name"]: r for r in rep["rows"]}
    assert by["Alice"]["state"] == "due" and by["Alice"]["due_week"] == 1
    assert by["Bob"]["state"] == "due" and by["Bob"]["due_week"] == 1
    assert by["Cara"]["state"] == "in_progress"     # current week not done, no completed week
    assert rep["counts"]["due"] == 2
    assert rep["counts"]["in_progress"] == 1


def test_status_up_to_date_when_mastered(cohort):
    database.itqan_upsert_mastery("a", "L0", 1, False, 1)
    database.itqan_upsert_mastery("a", "L0", 2, False, 2)
    rep = database.itqan_status_report("L0")
    by = {r["name"]: r for r in rep["rows"]}
    assert by["Alice"]["state"] == "up_to_date"
    assert by["Alice"]["mastered_count"] == 2


def test_status_flagged_surfaces(cohort):
    att = database.itqan_create_attempt("b", "L0", 1, "s")
    database.itqan_finish_attempt(att["id"], 66.0, 90.0, "not_yet", False, "flagged", False)
    rep = database.itqan_status_report("L0")
    by = {r["name"]: r for r in rep["rows"]}
    assert by["Bob"]["state"] == "flagged" and by["Bob"]["due_week"] == 1
    assert rep["counts"]["flagged"] == 1


def test_format_itqan_due_readable(cohort):
    text = assessment.format_itqan_due(database.itqan_status_report("L0"))
    assert "Itqan — status (L0)" in text
    assert "DUE" in text
    assert "Alice" in text and "Cara" in text


# ---- manual-pass celebration ---------------------------------------------

@pytest.mark.asyncio
async def test_deliver_manual_pass_notifies_and_celebrates(monkeypatch):
    calls = {"dm": 0, "celebrate": 0}

    async def _dm(discord_id, level, week):
        calls["dm"] += 1

    async def _celebrate(discord_id, level, week, verdict):
        calls["celebrate"] += 1

    monkeypatch.setattr(itqan_outcomes, "_manual_pass_dm", _dm)
    monkeypatch.setattr(itqan_outcomes, "_celebrate_champion", _celebrate)
    await itqan_outcomes.deliver_manual_pass("s1", "L0", 2)
    assert calls == {"dm": 1, "celebrate": 1}
