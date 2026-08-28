"""Onboarding at ANY level, not just A1 — the full journey from a mid-ladder start.

Every existing journey test starts at A1, because that is where all current
students are. But placement can slot a brand-new student straight into A2-C2, and
such a student has **no prior-level history at all**. These tests pin that the
whole journey works from that start:

    placement -> slotted at the level -> study the level -> completion contract
    met -> exit exam passed -> certificate makes the full-completion claim
    -> promotion to the next level.

WHY THIS FILE EXISTS. The only test that used to exercise non-A1 levels was
`test_weekly_requirements_skip_content_that_is_not_authored`, and it now SKIPS by
design: it guards a *partially* authored level, and every level is now fully
authored. That is the correct behaviour for that test, but it silently left the
contract's satisfiability at A2-C2 unproven at exactly the moment the programme
began claiming it was ready to onboard students at any level. A claim nobody
checks is what this whole effort set out to remove, so it is checked here.

The tests deliberately go through `placement.place_student(..., slot=True)`
rather than poking the members table, so the real onboarding path is what is
under test.
"""
import datetime

import pytest

from src import assessment, config, curriculum, database, placement

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
SKILLS = ("reading", "writing", "listening", "speaking")


def _uniform_bands(level):
    """Skill profile that places a student exactly at `level`.

    conservative_overall takes min(round(mean), weakest+1); with every skill at
    the same band both terms resolve to that band, so a uniform profile is the
    clean way to target a level without depending on the rounding rule.
    """
    return {s: level for s in SKILLS}


def _onboard(discord_id, level):
    """Run the real placement path and return its result."""
    database.register_member(discord_id, f"New {level} Student")
    return placement.place_student(discord_id, _uniform_bands(level), slot=True,
                                   source="self")


def _study_whole_level(discord_id, level):
    """A student who genuinely completes every day and every weekly exercise.

    Two things this deliberately gets right, because getting either wrong makes a
    complete student look incomplete:

    1. Exercise sets come from the source lists, never hardcoded, so a newly
       shipped exercise is included automatically.
    2. Writing submissions are dated FROM THE STUDENT'S OWN LEVEL ANCHOR.
       `writing` is a Discord-only task (`!6`): it lands in `daily_submissions`,
       never in `practice_mastery`, and `database.practice_completions` maps it
       onto its content day by inverting the calendar anchor arithmetic. Dating
       the work before the anchor (e.g. a fixed 2026-01-01 while placement
       stamped `level_started_at = now`) makes that inversion yield no valid
       week, the rows are correctly skipped, and every "can write ..." descriptor
       looks unevidenced. A real student studies *after* being placed, so the
       simulation must too.
    """
    member = database.get_member(discord_id)
    anchor = datetime.datetime.fromisoformat(
        database.level_anchor_iso(member)).date()
    max_wk = curriculum.max_week_for_level(level)
    for wk in range(1, max_wk + 1):
        for day in range(1, 8):
            for ex in database.CALENDAR_EXERCISES + database.WEEKLY_EXERCISES:
                database.record_practice_mastery(discord_id, level, wk, day, ex,
                                                 today="2026-02-01")
            d = anchor + datetime.timedelta(days=(wk - 1) * 7 + (day - 1))
            database.log_submission(discord_id, d.isoformat(), "writing", "w")


def _pass_exit_exam(discord_id, level, attempt_id):
    conn = database._connect()
    conn.execute(
        "INSERT INTO advancement_exams "
        "(discord_id, level, attempt_num, attempt_id, part_a_score, "
        " part_b_score, overall_score, passed) VALUES (?,?,?,?,?,?,?,1)",
        (discord_id, level, 1, attempt_id, 80, 88, 85))
    conn.commit()
    conn.close()


# ============================================================
#  1. Placement can actually land a student on every level
# ============================================================

@pytest.mark.parametrize("level", LEVELS)
def test_placement_slots_a_new_student_into_any_level(load_curriculum, level):
    sid = f"ml_place_{level}"
    res = _onboard(sid, level)
    assert res["overall_level"] == level, res
    assert res["slotted"] is True
    # Slotting sends them to week 1 of the placed level, not to A1.
    assert res["recommended_week"] == 1
    assert config.cefr_key(database.get_member(sid)["level"]) == level


# ============================================================
#  2. THE CONTRACT MUST BE SATISFIABLE AT EVERY LEVEL
# ============================================================

@pytest.mark.parametrize("level", LEVELS)
def test_completion_contract_is_satisfiable_at_every_level(
        load_curriculum, monkeypatch, level):
    """A student onboarded straight into `level` who does everything and passes
    the exit exam must reach a fully met contract.

    If this fails for any level, that level cannot be completed by anybody and
    the programme must not claim it is ready to onboard into it.
    """
    monkeypatch.setattr(config, "SPEAKING_LAUNCH_DATE", "2099-01-01")
    sid = f"ml_full_{level}"
    _onboard(sid, level)
    _study_whole_level(sid, level)
    _pass_exit_exam(sid, level, attempt_id=7100 + LEVELS.index(level))

    c = assessment.level_completion_contract(sid, level)
    unmet = [x for x in c["criteria"] if not x["met"]]
    assert c["met"] is True, f"{level} contract unmet: {unmet}"

    cert = database.itqan_certificate_data(sid, level)
    assert cert["eligible"] is True, level
    assert cert["full_completion"] is True, level
    assert "backed by" in cert["statement_en"], level


# ============================================================
#  3. No dependency on prior-level history
# ============================================================

@pytest.mark.parametrize("level", ("A2", "B1", "B2", "C1", "C2"))
def test_midladder_student_has_no_prior_level_history_and_is_unaffected(
        load_curriculum, monkeypatch, level):
    """The whole point of mid-ladder onboarding: the student never studied the
    levels below, and nothing may require that they did."""
    monkeypatch.setattr(config, "SPEAKING_LAUNCH_DATE", "2099-01-01")
    sid = f"ml_nohist_{level}"
    _onboard(sid, level)
    _study_whole_level(sid, level)
    _pass_exit_exam(sid, level, attempt_id=7200 + LEVELS.index(level))

    # No REAL practice history anywhere below the placed level. The only rows
    # that appear for a lower level are the Discord-only `writing`/`community`
    # bridge in practice_completions: `daily_submissions` has no level column, so
    # those submissions are mapped onto whichever level is queried. That is
    # imprecise but SAFE, and the assertions below pin the safety property rather
    # than the imprecision.
    below = LEVELS[:LEVELS.index(level)]
    for lower in below:
        rows = database.practice_completions(sid, lower)
        real = sorted({r["exercise"] for r in rows
                       if r["exercise"] not in ("writing", "community")})
        assert not real, (
            f"{sid} has real practice history at {lower} it never studied: {real}")

        # THE SAFETY PROPERTY: a level the student never studied must not be
        # reported as complete.
        lower_c = assessment.level_completion_contract(sid, lower)
        assert lower_c["met"] is False, (
            f"{lower} reported COMPLETE for a student who never studied it")

        # And the certificate must never CLAIM the un-studied level. Note it
        # deliberately re-targets to the exam actually passed rather than to the
        # level argument, so asking for `lower` yields a certificate for the
        # placed level. That is the correct behaviour: it makes a false lower-level
        # claim structurally impossible.
        lower_cert = database.itqan_certificate_data(sid, lower)
        assert config.cefr_key(lower_cert["level"]) == level, (
            f"certificate asked for {lower} should re-target to the passed level "
            f"{level}, got {lower_cert['level']}")
        assert lower not in lower_cert["statement_en"], (
            f"certificate statement names {lower}, which the student never studied: "
            f"{lower_cert['statement_en']}")

    # ...and the placed level still completes fully.
    c = assessment.level_completion_contract(sid, level)
    assert c["met"] is True, [x for x in c["criteria"] if not x["met"]]
    # Evidence is derived only from this level's work.
    port = assessment.descriptor_portfolio(sid, level)
    assert port["total"] > 0, level
    assert port["evidenced"] == port["total"], (
        f"{level}: {port['total'] - port['evidenced']} descriptors unevidenced "
        f"for a student who did everything")


# ============================================================
#  4. Progression works from wherever they started
# ============================================================

@pytest.mark.parametrize("level", LEVELS)
def test_writing_only_descriptors_are_evidenceable(load_curriculum, level):
    """Regression guard for a subtle, high-cost mechanism.

    13 descriptors across the six levels can be evidenced ONLY by `writing`
    (e.g. `A1.P.4`, `B1.P.6`, `C2.P.2`). `writing` is a Discord-only task: it is
    logged in `daily_submissions` and NEVER reaches `practice_mastery`, which is
    what `descriptor_portfolio` reads. `database.practice_completions` bridges the
    gap by mapping those submissions onto their content day.

    If that bridge is ever refactored away, those 13 descriptors become
    permanently unevidenceable, the EVIDENCE criterion can never be met, and NO
    student at ANY level can reach full completion — while every other test still
    passes. This pins it.
    """
    sid = f"ml_write_{level}"
    _onboard(sid, level)
    _study_whole_level(sid, level)
    pf = assessment.descriptor_portfolio(sid, level)
    writing_only = [d for d in pf["descriptors"]
                    if d["possible_exercises"] == ["writing"]]
    if not writing_only:
        pytest.skip(f"{level} has no writing-only descriptors")
    unevidenced = [d["code"] for d in writing_only if not d["evidenced"]]
    assert not unevidenced, (
        f"{level}: writing-only descriptors {unevidenced} are unevidenced even "
        f"though the student submitted writing every day — the "
        f"daily_submissions -> content-day bridge in practice_completions is "
        f"broken, which silently makes full completion impossible at every level")


def test_promotion_chain_is_intact_from_every_level(load_curriculum):
    expected = {"A1": "A2", "A2": "B1", "B1": "B2", "B2": "C1", "C1": "C2"}
    for level, nxt in expected.items():
        assert config.next_cefr_level(level) == nxt, level
    # C2 is terminal — it must not promote anywhere.
    assert config.next_cefr_level("C2") in (None, "", "C2"), \
        "C2 must be terminal, not promote onward"


def test_every_level_has_the_content_a_placed_student_will_meet(load_curriculum):
    """A student slotted into a level must find real content on day one of week
    one — not an empty page."""
    for level in LEVELS:
        max_wk = curriculum.max_week_for_level(level)
        assert max_wk and max_wk > 0, level
        assert curriculum.get_vocabulary_for_week(1, level), f"{level} w1 vocab"
        assert curriculum.get_reading_for_week(1, level), f"{level} w1 reading"
        assert curriculum.get_mediation_for_week(1, level), f"{level} w1 mediation"
        assert curriculum.get_broadcast_for_week(1, level), f"{level} w1 broadcast"
