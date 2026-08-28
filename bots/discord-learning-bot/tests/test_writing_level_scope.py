"""The Discord-only writing/community bridge must be level-scoped — without
erasing evidence that already exists.

`writing` and `community` (`!6` / `!7`) are logged in `daily_submissions` and
never reach `practice_mastery`, which is what `descriptor_portfolio` reads. So
`database.practice_completions` bridges them onto a content day by inverting the
calendar anchor. `daily_submissions` originally had no level column, so that
bridge attributed a submission to *whichever level was queried* — a C2 student's
writing also showed up as evidence at A1.

That could never grant anything (the WORK criterion is 0 at a level you never
studied, and the certificate re-targets to the exam actually passed), but it
over-reported evidence for a level the student never took.

The column is nullable on purpose, and these tests pin BOTH halves of that
decision, because getting either one wrong is a real regression:

  * new rows carry their level and are matched exactly — no cross-level leak;
  * rows written before the column existed are NULL and still bridge, so no
    existing student loses retroactive evidence.
"""
import datetime

from src import config, database, placement

SKILLS = ("reading", "writing", "listening", "speaking")


def _onboard(discord_id, level):
    database.register_member(discord_id, f"Scope {level}")
    placement.place_student(discord_id, {s: level for s in SKILLS},
                            slot=True, source="self")
    member = database.get_member(discord_id)
    return datetime.datetime.fromisoformat(
        database.level_anchor_iso(member)).date()


def _writing_rows(discord_id, level):
    return [r for r in database.practice_completions(discord_id, level)
            if r["exercise"] == "writing"]


# ============================================================
#  New rows are level-scoped
# ============================================================

def test_writing_is_attributed_only_to_the_level_it_was_done_at(load_curriculum):
    anchor = _onboard("ws_c2", "C2")
    for i in range(5):
        database.log_submission("ws_c2", (anchor + datetime.timedelta(days=i)).isoformat(),
                                "writing", "w")

    # Present at the level actually studied...
    assert len(_writing_rows("ws_c2", "C2")) == 5
    # ...and absent from every level the student never touched.
    for other in ("A1", "A2", "B1", "B2", "C1"):
        assert _writing_rows("ws_c2", other) == [], (
            f"C2 writing leaked into {other}")


def test_log_submission_stamps_the_members_current_level(load_curriculum):
    _onboard("ws_b1", "B1")
    database.log_submission("ws_b1", "2026-03-02", "writing", "w")
    conn = database._connect()
    row = conn.execute(
        "SELECT level FROM daily_submissions WHERE discord_id=? AND task_id='writing'",
        ("ws_b1",)).fetchone()
    conn.close()
    assert row["level"] == "B1"


def test_community_is_scoped_the_same_way_as_writing(load_curriculum):
    anchor = _onboard("ws_comm", "B2")
    database.log_submission("ws_comm", anchor.isoformat(), "community", "c")
    b2 = [r for r in database.practice_completions("ws_comm", "B2")
          if r["exercise"] == "community"]
    a1 = [r for r in database.practice_completions("ws_comm", "A1")
          if r["exercise"] == "community"]
    assert len(b2) == 1
    assert a1 == []


# ============================================================
#  THE SAFETY HALF: historic rows must keep working
# ============================================================

def test_legacy_rows_with_no_level_still_bridge(load_curriculum):
    """Rows written before the `level` column existed are NULL. They must still
    produce evidence, or every existing student silently loses history the day
    this shipped."""
    anchor = _onboard("ws_legacy", "A1")
    # Simulate a pre-migration row: written directly, level left NULL.
    conn = database._connect()
    for i in range(3):
        conn.execute(
            "INSERT INTO daily_submissions (discord_id, date, task_id, content, level) "
            "VALUES (?,?,?,?,NULL)",
            ("ws_legacy", (anchor + datetime.timedelta(days=i)).isoformat(),
             "writing", "old"))
    conn.commit()
    conn.close()

    rows = _writing_rows("ws_legacy", "A1")
    assert len(rows) == 3, (
        "legacy NULL-level writing rows stopped bridging — this would erase "
        "retroactive evidence for every pre-existing student")


def test_a_promoted_students_old_level_evidence_survives(load_curriculum):
    """A student who did A1 writing and later moved to A2 must keep their A1
    evidence. Their A1 rows are stamped A1, so scoping must not hide them when
    A1 is queried after promotion."""
    anchor = _onboard("ws_promo", "A1")
    for i in range(4):
        database.log_submission("ws_promo", (anchor + datetime.timedelta(days=i)).isoformat(),
                                "writing", "w")
    assert len(_writing_rows("ws_promo", "A1")) == 4

    # Promote. set_level re-anchors the calendar to now.
    database.set_level("ws_promo", "A2")
    assert config.cefr_key(database.get_member("ws_promo")["level"]) == "A2"

    # The A1 rows are still stamped A1 and must not appear as A2 evidence.
    assert _writing_rows("ws_promo", "A2") == [], "A1 writing counted as A2 evidence"

    # A1 evidence is still attributable to A1 (the rows kept their level), which
    # is what a certificate for the completed level relies on.
    conn = database._connect()
    levels = [r["level"] for r in conn.execute(
        "SELECT level FROM daily_submissions WHERE discord_id=? AND task_id='writing'",
        ("ws_promo",)).fetchall()]
    conn.close()
    assert levels == ["A1"] * 4, levels
