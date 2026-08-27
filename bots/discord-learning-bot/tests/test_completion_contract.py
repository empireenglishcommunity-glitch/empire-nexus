"""Phase 11C — the LEVEL COMPLETION CONTRACT.

"Finished A1" used to mean "clicked through the days". These tests pin what it
means now, and pin the safety property that matters most: **the contract must
never take a certificate away from a student who already earned one.**
"""

import datetime

import pytest

from src import assessment, config, curriculum, database


def _pass_exit_exam(discord_id, level, part_b_score=88, attempt_id=7001):
    """Seed a PASSED exit exam the same way the Phase-8 tests do (there is no
    public recorder helper; assessment writes these rows during a real exam)."""
    conn = database._connect()
    conn.execute(
        "INSERT INTO advancement_exams "
        "(discord_id, level, attempt_num, attempt_id, part_a_score, "
        " part_b_score, overall_score, passed) VALUES (?,?,?,?,?,?,?,1)",
        (discord_id, level, 1, attempt_id, 80, part_b_score, 85))
    conn.commit()
    conn.close()


def _member(discord_id="c1", level="A1", joined_at="2026-01-01"):
    database.register_member(discord_id, "Contract Student")
    conn = database._connect()
    conn.execute("UPDATE members SET level=?, joined_at=?, level_started_at=? "
                 "WHERE discord_id=?", (level, joined_at, joined_at, discord_id))
    conn.commit()
    conn.close()


def _do_everything(discord_id="c1", level="A1", joined_at="2026-01-01"):
    """A student who genuinely completes the whole level."""
    anchor = datetime.date.fromisoformat(joined_at)
    max_wk = curriculum.max_week_for_level(level)
    for wk in range(1, max_wk + 1):
        for day in range(1, 8):
            # Derived from the source sets rather than hardcoded: this helper
            # models "a student who genuinely did everything", so when a new
            # weekly exercise ships it must be included automatically. Spelling
            # the list out here meant that adding `broadcast` in Phase 11D made
            # a complete student look 40/50 and failed three tests for a reason
            # that had nothing to do with what they were testing.
            for ex in database.CALENDAR_EXERCISES + database.WEEKLY_EXERCISES:
                database.record_practice_mastery(discord_id, level, wk, day, ex,
                                                today="2026-02-01")
            d = anchor + datetime.timedelta(days=(wk - 1) * 7 + (day - 1))
            database.log_submission(discord_id, d.isoformat(), "writing", "w")


# ============================================================
#  THE SAFETY PROPERTY (most important test in this file)
# ============================================================

def test_contract_never_revokes_certificate_access(load_curriculum, monkeypatch):
    """A student eligible for a certificate must STAY eligible even when the
    contract is unmet. The contract gates the strongest CLAIM, not access —
    retroactively revoking an earned certificate would be indefensible."""
    _member()
    monkeypatch.setattr(config, "SPEAKING_LAUNCH_DATE", "2099-01-01")
    # Passing the exit exam makes them eligible on the 'exam' basis.
    _pass_exit_exam("c1", "A1", part_b_score=85)
    cert = database.itqan_certificate_data("c1", "A1")
    assert cert["eligible"] is True, "exam-passer lost certificate eligibility"
    # ...while the contract is honestly NOT met (no work, no evidence).
    assert cert["full_completion"] is False
    assert cert["contract"]["met"] is False
    # And the statement is unchanged from the pre-contract wording.
    assert "backed by" not in cert["statement_en"]


def test_certificate_still_renders_when_the_contract_errors(load_curriculum, monkeypatch):
    """A certificate must never fail to render because the contract could not
    be computed."""
    _member()
    _pass_exit_exam("c1", "A1", part_b_score=85)
    monkeypatch.setattr(assessment, "level_completion_contract",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    cert = database.itqan_certificate_data("c1", "A1")
    assert cert["eligible"] is True
    assert cert["contract"] is None
    assert cert["full_completion"] is False
    assert cert["statement_en"]


# ============================================================
#  THE THREE CRITERIA
# ============================================================

def test_contract_lists_exactly_the_three_criteria(load_curriculum):
    _member()
    c = assessment.level_completion_contract("c1", "A1")
    assert [x["id"] for x in c["criteria"]] == ["work", "evidence", "retention"]
    for x in c["criteria"]:
        assert x["label_en"] and x["label_ar"], f"{x['id']} not bilingual"
        assert x["detail"], f"{x['id']} has no progress detail"


def test_a_new_student_meets_nothing(load_curriculum):
    _member()
    c = assessment.level_completion_contract("c1", "A1")
    assert c["met"] is False
    assert all(x["met"] is False for x in c["criteria"])


def test_work_alone_does_not_satisfy_the_contract(load_curriculum, monkeypatch):
    """Doing all the work is not enough: the exit exam still has to be passed.
    This is the difference between attendance and proficiency."""
    monkeypatch.setattr(config, "SPEAKING_LAUNCH_DATE", "2099-01-01")
    _member()
    _do_everything()
    c = assessment.level_completion_contract("c1", "A1")
    by_id = {x["id"]: x for x in c["criteria"]}
    assert by_id["work"]["met"] is True, by_id["work"]["detail"]
    assert by_id["evidence"]["met"] is True, by_id["evidence"]["detail"]
    assert by_id["retention"]["met"] is False
    assert c["met"] is False


def test_exam_alone_does_not_satisfy_the_contract(load_curriculum):
    """Passing the exam without doing the level does not prove the level's
    can-do statements — which is exactly the hole the contract closes."""
    _member()
    _pass_exit_exam("c1", "A1", part_b_score=95)
    c = assessment.level_completion_contract("c1", "A1")
    by_id = {x["id"]: x for x in c["criteria"]}
    assert by_id["retention"]["met"] is True
    assert by_id["work"]["met"] is False
    assert by_id["evidence"]["met"] is False
    assert c["met"] is False


def test_full_completion_is_reached_only_with_all_three(load_curriculum, monkeypatch):
    monkeypatch.setattr(config, "SPEAKING_LAUNCH_DATE", "2099-01-01")
    _member()
    _do_everything()
    _pass_exit_exam("c1", "A1", part_b_score=88)
    c = assessment.level_completion_contract("c1", "A1")
    assert c["met"] is True, [x for x in c["criteria"] if not x["met"]]

    cert = database.itqan_certificate_data("c1", "A1")
    assert cert["full_completion"] is True
    # Only now may the certificate make the stronger claim.
    assert "backed by" in cert["statement_en"]
    assert "مدعومة" in cert["statement_ar"]


# ============================================================
#  THE CONTRACT MUST BE SATISFIABLE (a contract nobody can meet is a bug)
# ============================================================

def test_weekly_requirements_skip_content_that_is_not_authored(load_curriculum, monkeypatch):
    """reading and mediation roll out level by level. Requiring them on a level
    whose content is not authored yet would make the contract permanently
    unsatisfiable for those students — which would be worse than not having a
    contract at all."""
    monkeypatch.setattr(config, "SPEAKING_LAUNCH_DATE", "2099-01-01")
    # Any level still missing ANY of the three rollout exercises will do. Was
    # keyed on reading alone, which stopped finding a level once C2 reading
    # landed; the property under test is "some rollout exercise is unauthored
    # here", not "reading specifically".
    incomplete = [l for l in ("A2", "B1", "B2", "C1", "C2")
                  if not all(curriculum.exercise_has_content(e, l)
                             for e in ("reading", "mediation", "broadcast"))]
    if not incomplete:
        pytest.skip("every level now has all three rollout exercises authored — "
                    "the unsatisfiable-contract risk this guards against is gone")
    level = incomplete[0]
    _member("c2", level=level)
    anchor = datetime.date.fromisoformat("2026-01-01")
    # Everything the student COULD actually do at this level. Derived from
    # curriculum.exercise_has_content rather than a hardcoded skip list: the
    # rollout is per level AND per exercise, so once C2 had mediation but still
    # no reading, a fixed list of "skip all three" under-recorded a complete
    # student and failed this test for a reason that had nothing to do with what
    # it tests. This way it keeps expressing its actual intent as content lands.
    doable = [e for e in database.CALENDAR_EXERCISES + database.WEEKLY_EXERCISES
              if curriculum.exercise_has_content(e, level)]
    missing = [e for e in ("reading", "mediation", "broadcast") if e not in doable]
    assert missing, f"{level} has all rollout content; pick a level that does not"
    for wk in range(1, curriculum.max_week_for_level(level) + 1):
        for day in range(1, 8):
            for ex in doable:
                database.record_practice_mastery("c2", level, wk, day, ex,
                                                today="2026-02-01")
            d = anchor + datetime.timedelta(days=(wk - 1) * 7 + (day - 1))
            database.log_submission("c2", d.isoformat(), "writing", "w")
    c = assessment.level_completion_contract("c2", level)
    work = next(x for x in c["criteria"] if x["id"] == "work")
    assert work["met"] is True, (
        f"{level} work criterion unsatisfiable without unauthored content: "
        f"{work['detail']}"
    )


def test_a1_contract_is_fully_satisfiable(load_curriculum, monkeypatch):
    """A1 is the level students are actually on, and it is 100%
    descriptor-complete, so its contract must be reachable end to end."""
    monkeypatch.setattr(config, "SPEAKING_LAUNCH_DATE", "2099-01-01")
    _member("c3")
    _do_everything("c3")
    _pass_exit_exam("c3", "A1", part_b_score=90)
    c = assessment.level_completion_contract("c3", "A1")
    assert c["met"] is True, [x for x in c["criteria"] if not x["met"]]


def test_an_exam_passed_at_another_level_does_not_count(load_curriculum, monkeypatch):
    """Retention must be proven for THIS level."""
    monkeypatch.setattr(config, "SPEAKING_LAUNCH_DATE", "2099-01-01")
    _member("c4", level="A2")
    _pass_exit_exam("c4", "A1", part_b_score=95)
    c = assessment.level_completion_contract("c4", "A2")
    retention = next(x for x in c["criteria"] if x["id"] == "retention")
    assert retention["met"] is False, "an A1 pass satisfied the A2 contract"
