"""Itqan Phase 7 — owner report aggregation + override actions."""
import pytest

from src import assessment, database


def _finished_attempt(did, level, week, result, status, mastery, consistency,
                      distinction=False):
    att = database.itqan_create_attempt(did, level, week, "seed")
    database.itqan_finish_attempt(att["id"], mastery, consistency, result,
                                  distinction, status, False)
    return att["id"]


def _wrong_items(attempt_id, did, week, pairs):
    """pairs: [(skill, expected)]. Inserts + marks each wrong."""
    items = [{"item_no": i + 1, "skill": skill, "source_week": week,
              "payload": {"expected": exp}} for i, (skill, exp) in enumerate(pairs)]
    database.itqan_insert_items(attempt_id, did, items)
    for i, _ in enumerate(pairs):
        database.itqan_save_item(attempt_id, i + 1, "x", correct=False)


@pytest.fixture
def cohort():
    database.register_member("a", "Alice", "L0")
    database.register_member("b", "Bob", "L0")
    database.register_member("c", "Cara", "L0")
    database.register_member("d", "Dan", "L0")

    # Alice mastered week 1.
    aid = _finished_attempt("a", "L0", 1, "mastered", "scored", 88.0, 100.0)
    database.itqan_upsert_mastery("a", "L0", 1, False, aid)
    # Bob not-yet week 2, missed book (vocab) + water (listening).
    bid = _finished_attempt("b", "L0", 2, "not_yet", "scored", 45.0, 90.0)
    _wrong_items(bid, "b", 2, [("vocab", "book"), ("listening", "water")])
    # Cara flagged week 2, also missed book.
    cid = _finished_attempt("c", "L0", 2, "not_yet", "flagged", 69.0, 90.0)
    _wrong_items(cid, "c", 2, [("vocab", "book")])
    # Dan: no attempts.
    return {"alice_attempt": aid, "bob_attempt": bid, "cara_attempt": cid}


# ---- aggregation ----------------------------------------------------------

def test_report_counts_route_each_student(cohort):
    data = database.itqan_report_data()
    assert data["total_students"] == 4
    c = data["counts"]
    assert c["mastered"] == 1   # Alice
    assert c["not_yet"] == 1    # Bob
    assert c["flagged"] == 1    # Cara (latest attempt flagged)
    assert c["none"] == 1       # Dan


def test_report_per_student_details(cohort):
    data = database.itqan_report_data()
    by_name = {s["name"]: s for s in data["per_student"]}
    assert by_name["Alice"]["mastered_count"] == 1
    assert by_name["Alice"]["latest"]["result"] == "mastered"
    assert by_name["Dan"]["latest"] is None
    assert by_name["Cara"]["latest"]["status"] == "flagged"


def test_report_flagged_queue(cohort):
    data = database.itqan_report_data()
    assert len(data["flagged"]) == 1
    assert data["flagged"][0]["name"] == "Cara"
    assert data["flagged"][0]["week"] == 2


def test_report_most_missed_ranks_book_first(cohort):
    data = database.itqan_report_data()
    mm = {m["expected"]: m["misses"] for m in data["most_missed"]}
    assert mm.get("book") == 2   # missed by Bob + Cara
    assert mm.get("water") == 1


def test_report_level_filter(cohort):
    database.register_member("e", "Eve", "L1")
    _finished_attempt("e", "L1", 1, "mastered", "scored", 90.0, 100.0)
    l0 = database.itqan_report_data("L0")
    assert l0["total_students"] == 4              # Eve (L1) excluded
    assert all(s["level"] == "L0" for s in l0["per_student"])


# ---- formatting -----------------------------------------------------------

def test_format_report_is_readable(cohort):
    text = assessment.format_itqan_report(database.itqan_report_data())
    assert "Itqan — Weekly Assessment report (all levels)" in text
    assert "Alice" in text and "Dan" in text
    assert "Needs your call (flagged):" in text
    assert "!itqan-pass @Cara 2" in text
    assert "Most-missed:" in text


# ---- overrides ------------------------------------------------------------

def test_admin_pass_marks_mastered(cohort):
    assert database.itqan_is_mastered("c", "L0", 2) is False
    database.itqan_admin_pass("c", "L0", 2)
    assert database.itqan_is_mastered("c", "L0", 2) is True
    # The flagged attempt is now resolved to scored/mastered.
    att = database.itqan_get_attempt(cohort["cara_attempt"])
    assert att["status"] == "scored"
    assert att["result"] == "mastered"
    # Cara now counts as mastered in the report.
    data = database.itqan_report_data()
    assert data["counts"]["flagged"] == 0
    assert data["counts"]["mastered"] == 2


def test_admin_pass_distinction(cohort):
    database.itqan_admin_pass("b", "L0", 2, distinction=True)
    att = database.itqan_get_attempt(cohort["bob_attempt"])
    assert att["result"] == "distinction"
    assert database.itqan_is_mastered("b", "L0", 2) is True


def test_reset_clears_attempts_items_mastery(cohort):
    # Bob has 1 attempt + 2 items for week 2.
    assert len(database.itqan_get_items(cohort["bob_attempt"])) == 2
    r = database.itqan_reset("b", "L0", 2)
    assert r["attempts_deleted"] == 1
    assert r["items_deleted"] == 2
    assert database.itqan_get_items(cohort["bob_attempt"]) == []
    assert database.itqan_attempts_count("b", "L0", 2) == 0


def test_reset_removes_mastery_so_week_relocks(cohort):
    aid = cohort["alice_attempt"]
    assert database.itqan_is_mastered("a", "L0", 1) is True
    r = database.itqan_reset("a", "L0", 1)
    assert r["mastery_deleted"] == 1
    assert database.itqan_is_mastered("a", "L0", 1) is False
