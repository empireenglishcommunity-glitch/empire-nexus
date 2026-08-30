"""A completed Monthly Review must produce a result. It never could.

REPORTED: Mai Mohamed completed the monthly assessment and no result appeared.

ROOT CAUSE: `finish_monthly_attempt` read `row.get("score")` from
`assessment_items` — a column that does not exist. Real per-item scores live in
`auto_score` (objective) and `ai_score` (pronunciation/speaking/writing). So
every item resolved to 0.0, the "are all the scores zero?" void guard concluded
the attempt was never answered, and the attempt plus all its items were DELETED
before the `INSERT INTO monthly_reviews` could run.

That INSERT was unreachable code. `monthly_reviews` therefore held zero rows
community-wide while the feature was enabled and students were completing
reviews — and because the attempt row was deleted too, not even an orphan
remained as evidence.

Two knock-on effects made it worse:
  * `get_monthly_state` counts rows in `monthly_reviews`, so the state stayed
    permanently "available" — the student could retake forever, always to
    nothing.
  * The frontend checks `data.voided` first and dropped the student into the
    WEEKLY intro, titled "Week NaN — Assessment", with a note claiming they had
    run out of time before answering. Mai answered everything.

The identical defect existed in `finish_advancement_part_a`, so exit exams were
broken the same way at every level.

Level-independent, student-independent: nothing in the broken path reads level.
"""
import datetime
import json

import pytest

from src import assessment, database


LEVEL = "A1"
DID = "9001"


@pytest.fixture(autouse=True)
def student():
    database.register_member(DID, "Test Student", level=LEVEL)
    database.set_feature_flag("assessment_monthly_review", enabled=True)
    # 4 mastered weeks makes a monthly review due.
    for wk in (1, 2, 3, 4):
        database.itqan_upsert_mastery(DID, LEVEL, wk, False, None)
    return DID


def _attempt_with_items(items, attempt_type="monthly", review_number=1):
    """Create an attempt row + items, then apply per-item scoring.

    `items` is a list of dicts: {skill, auto_score?, ai_score?, answer?,
    feedback?} — mirroring exactly what `itqan_save_item` writes.
    """
    conn = database._connect()
    cur = conn.execute(
        "INSERT INTO assessment_attempts (discord_id, level, week, attempt_no, seed, type) "
        "VALUES (?,?,?,?,?,?)",
        (DID, LEVEL, review_number, 1, "seed", attempt_type),
    )
    attempt_id = cur.lastrowid
    conn.commit()
    conn.close()

    blueprint = [{"item_no": i + 1, "skill": it.get("skill", "vocab"),
                  "source_week": 1, "payload": {"expected": "x"}}
                 for i, it in enumerate(items)]
    database.itqan_insert_items(attempt_id, DID, blueprint)

    for i, it in enumerate(items):
        database.itqan_save_item(
            attempt_id, i + 1,
            answer=it.get("answer", "an answer"),
            auto_score=it.get("auto_score"),
            ai_score=it.get("ai_score"),
            correct=it.get("correct"),
            feedback=it.get("feedback", ""),
        )
    return attempt_id


# ============================================================
#  THE REGRESSION
# ============================================================

def test_completed_monthly_review_writes_a_result_row():
    """The whole bug in one test: this returned {'voided': True} and wrote
    nothing, no matter how well the student did."""
    attempt_id = _attempt_with_items([
        {"skill": "vocab", "auto_score": 100.0},
        {"skill": "listening", "auto_score": 80.0},
        {"skill": "speaking", "ai_score": 70.0},
        {"skill": "writing", "ai_score": 90.0},
    ])

    result = assessment.finish_monthly_attempt(DID, attempt_id)

    assert result["ok"] is True
    assert not result.get("voided"), "a fully answered review must never be voided"
    assert result["retention_pct"] == 85.0
    assert result["result"] == "passed"

    assert database.monthly_reviews_taken(DID, LEVEL) == 1
    assert database.monthly_reviews_passed(DID, LEVEL) == 1


def test_the_result_row_holds_the_real_score_and_breakdown():
    attempt_id = _attempt_with_items([
        {"skill": "vocab", "auto_score": 100.0},
        {"skill": "vocab", "auto_score": 50.0},
        {"skill": "speaking", "ai_score": 60.0},
    ])
    assessment.finish_monthly_attempt(DID, attempt_id)

    conn = database._connect()
    row = conn.execute("SELECT * FROM monthly_reviews WHERE discord_id=?",
                       (DID,)).fetchone()
    conn.close()
    assert row is not None, "no row in monthly_reviews"
    assert row["attempt_id"] == attempt_id
    assert row["retention_score"] == 70.0
    breakdown = json.loads(row["skill_breakdown"])
    assert breakdown["vocab"] == 75.0     # (100 + 50) / 2
    assert breakdown["speaking"] == 60.0


def test_ai_scored_items_are_read_not_ignored():
    """Speaking/writing/pronunciation store into `ai_score`. The old read
    ignored it entirely, which is why production items counted for nothing."""
    attempt_id = _attempt_with_items([
        {"skill": "speaking", "ai_score": 90.0},
        {"skill": "writing", "ai_score": 90.0},
    ])
    result = assessment.finish_monthly_attempt(DID, attempt_id)
    assert result["retention_pct"] == 90.0
    assert result["result"] == "passed"


def test_the_attempt_row_survives_and_is_marked_scored():
    """The old void branch hard-deleted the attempt AND its items, destroying
    the evidence that the student had ever sat the review."""
    attempt_id = _attempt_with_items([{"skill": "vocab", "auto_score": 75.0}])
    assessment.finish_monthly_attempt(DID, attempt_id)

    attempt = database.itqan_get_attempt(attempt_id)
    assert attempt is not None, "the attempt row was deleted"
    assert attempt["status"] == "scored"
    assert attempt["result"] == "passed"
    assert attempt["finished_at"]
    assert len(database.itqan_get_items(attempt_id)) == 1


# ============================================================
#  ANSWERED-BUT-WRONG IS NOT THE SAME AS UNANSWERED
# ============================================================

def test_a_genuinely_answered_attempt_scoring_zero_is_still_recorded():
    """The old guard was `all(s == 0)`, which threw away a real attempt that
    happened to score nothing. A wrong answer is still an answer."""
    attempt_id = _attempt_with_items([
        {"skill": "vocab", "auto_score": 0.0, "answer": "wrong"},
        {"skill": "listening", "auto_score": 0.0, "answer": "also wrong"},
    ])
    result = assessment.finish_monthly_attempt(DID, attempt_id)

    assert not result.get("voided"), "answered-but-wrong must not be voided"
    assert result["retention_pct"] == 0.0
    assert result["result"] == "not_yet"
    assert database.monthly_reviews_taken(DID, LEVEL) == 1


def test_a_truly_blank_attempt_is_still_voided():
    """The void behaviour is correct and must survive — an abandoned attempt
    should not become a 0% failure on the student's record."""
    attempt_id = _attempt_with_items([
        {"skill": "vocab", "answer": ""},
        {"skill": "listening", "answer": ""},
    ])
    result = assessment.finish_monthly_attempt(DID, attempt_id)

    assert result["voided"] is True
    assert result["reason"] == "no_answers"
    assert database.monthly_reviews_taken(DID, LEVEL) == 0
    assert database.itqan_get_attempt(attempt_id) is None


def test_an_item_pending_manual_review_flags_rather_than_fails():
    """`__pending_review__` means the AI scorer errored. The attempt must be
    FLAGGED for the owner, not quietly recorded as a failure."""
    attempt_id = _attempt_with_items([
        {"skill": "vocab", "auto_score": 90.0},
        {"skill": "speaking", "feedback": "__pending_review__"},
    ])
    result = assessment.finish_monthly_attempt(DID, attempt_id)

    assert not result.get("voided")
    assert result["status"] == "flagged"
    assert result["flag_reason"] == "ai_error"


# ============================================================
#  STATE MACHINE — unblocked as a consequence
# ============================================================

def test_state_advances_to_passed_after_a_pass():
    """Because no row was ever written, `get_monthly_state` was stuck on
    'available' forever and a student could retake endlessly to no effect."""
    assert assessment.get_monthly_state(DID, LEVEL)["state"] == "available"

    attempt_id = _attempt_with_items([{"skill": "vocab", "auto_score": 95.0}])
    assessment.finish_monthly_attempt(DID, attempt_id)

    assert assessment.get_monthly_state(DID, LEVEL)["state"] == "passed"


def test_a_failed_review_enters_cooldown_instead_of_immediate_retake():
    attempt_id = _attempt_with_items([
        {"skill": "vocab", "auto_score": 10.0, "answer": "no"},
    ])
    assessment.finish_monthly_attempt(DID, attempt_id)
    assert assessment.get_monthly_state(DID, LEVEL)["state"] == "cooldown"


# ============================================================
#  THE SAME DEFECT IN THE ADVANCEMENT (EXIT) EXAM
# ============================================================

def test_advancement_part_a_reads_real_item_scores():
    """`finish_advancement_part_a` carried an identical `row.get("score")`,
    so exit exams were broken the same way at every level."""
    attempt_id = _attempt_with_items([
        {"skill": "vocab", "auto_score": 80.0},
        {"skill": "listening", "auto_score": 80.0},
        {"skill": "speaking", "ai_score": 80.0},
        {"skill": "writing", "ai_score": 80.0},
        {"skill": "pronunciation", "ai_score": 80.0},
    ], attempt_type="advancement")
    conn = database._connect()
    conn.execute(
        "INSERT INTO advancement_exams (discord_id, level, attempt_num, attempt_id) "
        "VALUES (?,?,?,?)", (DID, LEVEL, 1, attempt_id))
    conn.commit()
    conn.close()

    result = assessment.finish_advancement_part_a(DID, attempt_id)

    assert result["ok"] is True
    assert not result.get("voided"), "a fully answered Part A must not be voided"
    assert result["part_a_score"] == 80.0
    assert database.itqan_get_attempt(attempt_id) is not None


def test_advancement_part_a_still_voids_a_blank_attempt():
    attempt_id = _attempt_with_items(
        [{"skill": "vocab", "answer": ""}], attempt_type="advancement")
    result = assessment.finish_advancement_part_a(DID, attempt_id)
    assert result["voided"] is True


# ============================================================
#  THE SHARED HELPERS
# ============================================================

@pytest.mark.parametrize("row,expected", [
    ({"auto_score": 90.0}, (90.0, False)),
    ({"ai_score": 75.0}, (75.0, False)),
    ({"auto_score": 0.0, "ai_score": 99.0}, (0.0, False)),   # auto wins
    ({"feedback": "__pending_review__", "auto_score": 90.0}, (0.0, True)),
    ({}, (0.0, False)),
])
def test_resolve_item_score(row, expected):
    assert assessment._resolve_item_score(row) == expected


def test_resolve_item_score_never_reads_a_score_column():
    """Guards the exact mistake: a stray `score` key must be ignored, because
    `assessment_items` has no such column and anything providing one is wrong."""
    assert assessment._resolve_item_score({"score": 100.0}) == (0.0, False)


def test_assessment_items_has_no_score_column():
    """Pin the schema fact the bug depended on, so a future reader sees why
    `_resolve_item_score` looks the way it does."""
    conn = database._connect()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(assessment_items)")}
    conn.close()
    assert "score" not in cols
    assert {"auto_score", "ai_score"} <= cols


@pytest.mark.parametrize("rows,expected", [
    ([], 0),
    ([{"answer": ""}], 0),
    ([{"answer": "  "}], 0),
    ([{"answer": "hi"}], 1),
    ([{"auto_score": 0.0}], 1),
    ([{"ai_score": 0.0}], 1),
    ([{"feedback": "__pending_review__"}], 1),
    ([{"answer": ""}, {"auto_score": 0.0}], 1),
])
def test_answered_count(rows, expected):
    assert assessment._answered_count(rows) == expected



# ============================================================
#  RESUMING AN OPEN ATTEMPT INSTEAD OF ORPHANING IT
# ============================================================

def test_starting_twice_resumes_instead_of_creating_a_second_attempt():
    """Monthly had no in-progress guard, so every visit minted a new attempt
    and stranded the previous one with the student's answers inside it."""
    first = assessment.start_monthly_attempt(DID, LEVEL)
    assert first["ok"] and not first.get("resumed")

    second = assessment.start_monthly_attempt(DID, LEVEL)
    assert second["ok"] is True
    assert second.get("resumed") is True
    assert second["attempt_id"] == first["attempt_id"], \
        "a second visit must resume, not orphan the first attempt"

    conn = database._connect()
    n = conn.execute(
        "SELECT COUNT(*) c FROM assessment_attempts "
        "WHERE discord_id=? AND type='monthly'", (DID,)).fetchone()["c"]
    conn.close()
    assert n == 1, f"{n} monthly attempts exist; only one should"


def test_a_resumed_attempt_keeps_answers_already_saved():
    started = assessment.start_monthly_attempt(DID, LEVEL)
    attempt_id = started["attempt_id"]
    database.itqan_save_item(attempt_id, 1, answer="my answer", auto_score=100.0)

    resumed = assessment.start_monthly_attempt(DID, LEVEL)
    assert resumed["attempt_id"] == attempt_id

    rows = {r["item_no"]: r for r in database.itqan_get_items(attempt_id)}
    assert rows[1]["answer"] == "my answer"
    assert rows[1]["auto_score"] == 100.0


def test_a_resumed_attempt_never_leaks_expected_answers():
    """Resume rebuilds the public payload, so it must strip server-side
    answers exactly as a fresh start does."""
    started = assessment.start_monthly_attempt(DID, LEVEL)
    resumed = assessment.start_monthly_attempt(DID, LEVEL)
    assert resumed.get("resumed") is True
    for item in resumed["items"]:
        assert "expected" not in item["payload"], \
            f"resume leaked the expected answer: {item}"
    assert len(resumed["items"]) == len(started["items"])


def test_finishing_a_resumed_attempt_records_the_result():
    """End to end on the real code path: start, resume, answer, finish."""
    started = assessment.start_monthly_attempt(DID, LEVEL)
    attempt_id = started["attempt_id"]
    assessment.start_monthly_attempt(DID, LEVEL)  # resume

    for item in database.itqan_get_items(attempt_id):
        database.itqan_save_item(attempt_id, item["item_no"],
                                 answer="answered", auto_score=80.0)

    result = assessment.finish_monthly_attempt(DID, attempt_id)
    assert not result.get("voided")
    assert result["retention_pct"] == 80.0
    assert database.monthly_reviews_taken(DID, LEVEL) == 1


def test_after_finishing_a_new_start_is_not_treated_as_a_resume():
    started = assessment.start_monthly_attempt(DID, LEVEL)
    for item in database.itqan_get_items(started["attempt_id"]):
        database.itqan_save_item(started["attempt_id"], item["item_no"],
                                 answer="a", auto_score=10.0)
    assessment.finish_monthly_attempt(DID, started["attempt_id"])
    # Failed -> cooldown, so a start must be refused rather than resumed.
    again = assessment.start_monthly_attempt(DID, LEVEL)
    assert again["ok"] is False
    assert again["error"] == "cooldown"


def test_active_attempt_of_type_ignores_other_types():
    """A weekly attempt in progress must not be mistaken for a monthly one."""
    database.itqan_create_attempt(DID, LEVEL, 1, "seed")
    assert database.itqan_active_attempt_of_type(DID, LEVEL, "monthly") is None
    assert database.itqan_active_attempt(DID, LEVEL, 1) is not None
