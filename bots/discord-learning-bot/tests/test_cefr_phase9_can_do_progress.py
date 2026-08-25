"""Phase 9 — CEFR can-do progress (transparency).

A student's mastered weeks evidence the can-do descriptors those weeks target;
progress = evidenced / taught for the level.
"""
from src import assessment, curriculum, database


def _master(did, level, week):
    database.itqan_upsert_mastery(did, level, week, False, week)


def test_week_files_expose_can_do_codes():
    curriculum.load_all()
    codes = curriculum.get_can_do_for_week(1, "A1")
    assert codes and all(c.startswith("A1.") for c in codes)


def test_progress_zero_before_any_mastery():
    database.register_member("p9a", "Prog A")
    database.set_level("p9a", "A1")
    cdp = assessment.can_do_progress("p9a", "A1")
    assert cdp["level"] == "A1"
    assert cdp["total"] > 0            # A1 weeks target descriptors
    assert cdp["reached"] == 0 and cdp["pct"] == 0


def test_progress_increases_with_mastered_weeks():
    database.register_member("p9b", "Prog B")
    database.set_level("p9b", "A1")
    before = assessment.can_do_progress("p9b", "A1")
    # master week 1 → its can-do codes become evidenced
    _master("p9b", "A1", 1)
    after = assessment.can_do_progress("p9b", "A1")
    assert after["reached"] >= 1
    assert after["reached"] > before["reached"]
    assert 0 < after["pct"] <= 100
    week1_codes = set(curriculum.get_can_do_for_week(1, "A1"))
    assert week1_codes.issubset(set(after["evidenced"]))


def test_evidenced_is_capped_at_taught_total():
    database.register_member("p9c", "Prog C")
    database.set_level("p9c", "A1")
    total_weeks = curriculum.max_week_for_level("A1")
    for w in range(1, total_weeks + 1):
        _master("p9c", "A1", w)
    cdp = assessment.can_do_progress("p9c", "A1")
    assert cdp["reached"] == cdp["total"]     # mastered everything → all reached
    assert cdp["pct"] == 100
