"""Phase 11C — the descriptor EVIDENCE portfolio.

`can_do_progress` answers "how many descriptors has this student reached?" at
week granularity. It cannot answer the question a certificate actually needs:
*what did the student DO that proves this statement?*

These tests pin the answer, and — more importantly — pin the honesty rules:
evidence must be attributed to the right channel, enabling skills must prove
nothing, and Discord-only work must still count.
"""

import datetime

import pytest

from src import assessment, config, curriculum, database


def _member(discord_id="p1", level="A1", joined_at="2026-08-01"):
    database.register_member(discord_id, "Portfolio Student")
    conn = database._connect()
    conn.execute("UPDATE members SET level=?, joined_at=?, level_started_at=? "
                 "WHERE discord_id=?", (level, joined_at, joined_at, discord_id))
    conn.commit()
    conn.close()
    return database.get_member(discord_id)


# ============================================================
#  THE ATTRIBUTION RULES (the honesty of the whole feature)
# ============================================================

def test_enabling_skills_prove_no_descriptor(load_curriculum):
    """No CEFR descriptor says "can do a pronunciation drill". accent,
    shadowing, vocabulary, grammar and the review quiz build the machinery a
    descriptor needs but never constitute evidence for one -- claiming
    otherwise is exactly the over-claiming this work exists to remove."""
    for ex in ("accent", "shadow", "vocab", "grammar", "review", "community"):
        assert curriculum.EVIDENCE_MODES_BY_EXERCISE[ex] == (), (
            f"{ex} must not evidence any descriptor"
        )


def test_reading_descriptors_can_only_be_proven_by_reading(load_curriculum):
    """Reading and listening are both CEFR "reception", so mode matching alone
    would let a dictation claim a reading descriptor."""
    for week in range(1, curriculum.max_week_for_level("A1") + 1):
        passage = curriculum.get_reading_for_week(week, "A1")
        if not passage:
            continue
        emap = curriculum.descriptor_evidence_map(week, "A1")
        for code in passage["can_do"]:
            assert emap.get(code) == ("reading",), (
                f"{code} in week {week} is provable by {emap.get(code)}"
            )


def test_mediation_descriptors_can_only_be_proven_by_mediation(load_curriculum):
    for week in range(1, curriculum.max_week_for_level("A1") + 1):
        med = curriculum.get_mediation_for_week(week, "A1")
        if not med:
            continue
        emap = curriculum.descriptor_evidence_map(week, "A1")
        for code in med["can_do"]:
            assert emap.get(code) == ("mediation",)


def test_written_descriptors_are_not_provable_by_speaking(load_curriculum):
    """CEFR "production" covers speaking AND writing, so A1.P.5 ("Can WRITE
    short, simple notes and messages") would otherwise be satisfied by a
    speaking task. The descriptor text names the channel; use it."""
    emap = curriculum.descriptor_evidence_map(3, "A1")
    assert emap.get("A1.P.5") == ("writing",), emap.get("A1.P.5")


def test_spoken_reception_descriptors_are_not_provable_by_reading(load_curriculum):
    """A1.R.3 is "...numbers, prices, dates and times when SPOKEN slowly".

    Every exercise allowed to evidence it must be a SPOKEN-reception one. The
    point of the assertion is the exclusion of `reading`, so it is written as a
    subset check against curriculum.SPOKEN_RECEPTION rather than as an exact
    tuple: Phase 11D added `broadcast` as a second ear-channel exercise, and an
    exact-match assertion would have failed for a correct change while still
    not saying what it actually cared about.
    """
    emap = curriculum.descriptor_evidence_map(3, "A1")
    allowed = emap.get("A1.R.3")
    assert allowed, "A1.R.3 has no evidencing exercise at all"
    assert "reading" not in allowed, allowed
    assert set(allowed) <= set(curriculum.SPOKEN_RECEPTION), allowed
    assert "listening" in allowed, allowed


def test_no_descriptor_is_listed_as_unprovable(load_curriculum):
    """A descriptor in the map must always have at least one exercise that can
    prove it; a code with no route belongs in the coverage ledger's gap plan,
    not on a student's checklist."""
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            for code, exercises in curriculum.descriptor_evidence_map(week, level).items():
                assert exercises, f"{level} w{week} {code} has no possible evidence"


# ============================================================
#  THE PORTFOLIO
# ============================================================

def test_portfolio_starts_empty_and_lists_every_taught_descriptor(load_curriculum):
    _member()
    pf = assessment.descriptor_portfolio("p1", "A1")
    assert pf["total"] == 15, f"A1 teaches 15 descriptors, portfolio has {pf['total']}"
    assert pf["evidenced"] == 0 and pf["pct"] == 0
    for d in pf["descriptors"]:
        assert d["evidence"] == [] and d["evidenced"] is False
        assert d["possible_exercises"], f"{d['code']} unprovable"
        assert d["en"] and d["ar"], f"{d['code']} not bilingual"


def test_completing_a_task_evidences_exactly_the_right_descriptors(load_curriculum):
    """A1 week 1's PASSAGE evidences A1.R.4 and nothing else.

    It used to also evidence A1.R.1, and that was an over-claim discovered in
    Phase 11D: A1.R.1 is "...when people SPEAK slowly and clearly", a SPOKEN
    descriptor, which a reading passage cannot prove. It was reaching it because
    `_narrow_by_channel` recognised "spoken" but not "speak". A1.R.1 has been
    removed from all ten A1 passages and is now evidenced by the
    extended-listening exercise, which is the channel the descriptor names.
    """
    _member()
    database.record_practice_mastery("p1", "A1", 1, 1, "reading", today="2026-08-20")
    pf = assessment.descriptor_portfolio("p1", "A1")
    by_code = {d["code"]: d for d in pf["descriptors"]}
    assert by_code["A1.R.4"]["evidenced"] is True
    assert by_code["A1.R.4"]["evidence"][0]["exercise"] == "reading"
    assert by_code["A1.R.1"]["evidenced"] is False, (
        "a reading passage must not evidence A1.R.1 — it is about slow, clear "
        "SPEECH")
    assert pf["evidenced"] == 1, [d["code"] for d in pf["descriptors"] if d["evidenced"]]


def test_the_broadcast_exercise_evidences_a1_r_1(load_curriculum):
    """The other half of the fix: A1.R.1 must be reachable, by the ear."""
    _member()
    database.record_practice_mastery("p1", "A1", 1, 1, "broadcast", today="2026-08-20")
    by_code = {d["code"]: d for d in
               assessment.descriptor_portfolio("p1", "A1")["descriptors"]}
    assert by_code["A1.R.1"]["evidenced"] is True
    assert by_code["A1.R.1"]["evidence"][0]["exercise"] == "broadcast"


def test_an_enabling_skill_completion_evidences_nothing(load_curriculum):
    _member()
    for ex in ("accent", "shadow", "vocab", "grammar", "review"):
        database.record_practice_mastery("p1", "A1", 1, 1, ex, today="2026-08-20")
    pf = assessment.descriptor_portfolio("p1", "A1")
    assert pf["evidenced"] == 0, (
        "enabling-skill completions must not evidence descriptors: "
        + str([d["code"] for d in pf["descriptors"] if d["evidenced"]])
    )


def test_discord_only_writing_still_produces_evidence(load_curriculum):
    """Writing is a DISCORD task (!6): it is logged in daily_submissions and
    never reaches practice_mastery. Without mapping it onto its content day,
    every "can write ..." descriptor would be permanently unevidenceable and
    the portfolio would understate real work."""
    _member(joined_at="2026-08-01")
    anchor = datetime.date.fromisoformat("2026-08-01")
    # week 3, day 6 is the note-writing prompt that closed A1.P.5
    d = anchor + datetime.timedelta(days=(3 - 1) * 7 + (6 - 1))
    database.log_submission("p1", d.isoformat(), "writing", "my note")
    pf = assessment.descriptor_portfolio("p1", "A1")
    by_code = {x["code"]: x for x in pf["descriptors"]}
    assert by_code["A1.P.5"]["evidenced"] is True, "note-writing did not evidence A1.P.5"
    ev = by_code["A1.P.5"]["evidence"][0]
    assert ev["exercise"] == "writing" and ev["week"] == 3 and ev["day"] == 6


def test_submissions_before_the_level_started_are_not_counted(load_curriculum):
    """A student promoted into A1 must not have pre-level work credited to it."""
    _member(joined_at="2026-08-01")
    before = (datetime.date.fromisoformat("2026-08-01") - datetime.timedelta(days=5))
    database.log_submission("p1", before.isoformat(), "writing", "old work")
    rows = database.practice_completions("p1", "A1")
    assert not [r for r in rows if r["exercise"] == "writing"], rows


def test_submissions_beyond_the_level_length_are_not_counted(load_curriculum):
    """A date past the level's last week maps to no content day."""
    _member(joined_at="2026-08-01")
    far = datetime.date.fromisoformat("2026-08-01") + datetime.timedelta(days=400)
    database.log_submission("p1", far.isoformat(), "writing", "way later")
    rows = database.practice_completions("p1", "A1")
    assert not [r for r in rows if r["exercise"] == "writing"]


def test_portfolio_is_retroactive_over_existing_history(load_curriculum):
    """The portfolio is DERIVED from practice_mastery, so a student's existing
    history produces evidence with no backfill job. This is why no new table
    was added."""
    _member()
    for week in (1, 2, 3):
        database.record_practice_mastery("p1", "A1", week, 1, "speaking",
                                         today="2026-08-2%d" % week)
    pf = assessment.descriptor_portfolio("p1", "A1")
    assert pf["evidenced"] >= 3
    for d in pf["descriptors"]:
        for e in d["evidence"]:
            assert e["exercise"] == "speaking"
            assert e["at"], "evidence must carry a date"


def test_evidence_is_ordered_and_counted(load_curriculum):
    _member()
    for week in (3, 1, 2):
        database.record_practice_mastery("p1", "A1", week, 2, "speaking",
                                         today="2026-08-20")
    pf = assessment.descriptor_portfolio("p1", "A1")
    for d in pf["descriptors"]:
        weeks = [e["week"] for e in d["evidence"]]
        assert weeks == sorted(weeks), f"{d['code']} evidence out of order"
        assert d["evidence_count"] == len(d["evidence"])


# ============================================================
#  CERTIFICATE INTEGRATION
# ============================================================

def test_certificate_carries_evidence_per_can_do_statement(load_curriculum):
    _member()
    database.record_practice_mastery("p1", "A1", 1, 1, "reading", today="2026-08-20")
    cert = database.itqan_certificate_data("p1", "A1")
    assert "evidence" in cert, "certificate has no evidence summary"
    assert cert["evidence"]["total"] == len(cert["can_do"])
    by_code = {c["code"]: c for c in cert["can_do"]}
    # A1.R.4 is the descriptor the PASSAGE proves (A1.R.1 is spoken — see
    # test_completing_a_task_evidences_exactly_the_right_descriptors).
    assert by_code["A1.R.4"]["evidenced"] is True
    assert by_code["A1.R.4"]["evidence_count"] >= 1
    # Untouched descriptors are explicitly marked unevidenced, never omitted:
    # hiding them would make the checklist look complete when it is not.
    assert by_code["A1.I.4"]["evidenced"] is False
    assert all("evidenced" in c for c in cert["can_do"])


def test_certificate_still_renders_when_the_portfolio_fails(monkeypatch, load_curriculum):
    """A certificate must never fail to render because evidence could not be
    computed — it degrades to an unevidenced checklist instead."""
    _member()
    monkeypatch.setattr(assessment, "descriptor_portfolio",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    cert = database.itqan_certificate_data("p1", "A1")
    assert cert["can_do"], "checklist disappeared"
    assert all(c["evidenced"] is False for c in cert["can_do"])
    assert cert["evidence"]["evidenced"] == 0
