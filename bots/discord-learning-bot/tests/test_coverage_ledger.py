"""THE COVERAGE GATE.

These tests are the standing guarantee that no authored content can sit
undelivered. They fail the build the moment any atom loses its route to a
student — which is exactly how 894 atoms went missing unnoticed before
(354 vocabulary words, 450 listening items, 90 grammar patterns and their
1,208 sub-items, plus phoneme_focus/grammar_point/can-do goals with no
surface at all).

If one of these fails, the fix is to restore the delivery route — never to
relax the assertion.
"""

import pytest

from src import coverage_ledger, curriculum, database


@pytest.fixture(scope="module")
def rep(load_curriculum):
    return coverage_ledger.report()


# ============================================================
#  THE HARD GATE — delivery must be 100%
# ============================================================

def test_no_authored_atom_is_orphaned(rep):
    """Every authored atom must have a student-facing delivery route.

    This is the whole point of the ledger. A failure here means content was
    authored (and paid for) that no student can reach.
    """
    assert rep["orphaned_atoms"] == 0, (
        "AUTHORED CONTENT IS NOT REACHING STUDENTS:\n\n"
        + coverage_ledger.format_report(rep)
    )


def test_delivery_is_complete_for_every_level_and_kind(rep):
    """Per-level, per-kind check, so a single level regressing is not hidden
    by healthy totals elsewhere."""
    for level, data in rep["levels"].items():
        assert not data["shortfalls"], (
            f"{level} has undelivered atoms: "
            + "; ".join(f"week {s['week']} {s['kind']} "
                        f"{s['delivered']}/{s['authored']}"
                        for s in data["shortfalls"])
        )
        for kind, v in data["by_kind"].items():
            assert v["delivered"] == v["authored"], (
                f"{level} {kind}: only {v['delivered']} of {v['authored']} delivered"
            )


def test_ledger_covers_every_authored_content_kind(rep):
    """Guard against the ledger itself going blind: if a new authored field
    appears in the week files and nobody ledgers it, that field is exactly
    the kind of thing that silently goes undelivered. Every kind listed here
    must stay in the ledger."""
    expected_kinds = {
        "vocabulary", "accent_drills", "listening", "speaking_missions",
        "writing_prompts", "grammar_pattern", "grammar_sub_items",
        "phoneme_focus", "grammar_point", "can_do_goals",
    }
    assert expected_kinds <= set(rep["totals"]), (
        f"ledger stopped tracking: {expected_kinds - set(rep['totals'])}"
    )


def test_every_authored_week_field_is_ledgered(load_curriculum):
    """The real anti-blindness check: read the week files directly and assert
    every content-bearing field is claimed by some ledger kind. A brand-new
    authored field fails this until it is either delivered or explicitly
    recorded as metadata."""
    # Fields that are structural metadata, not deliverable content.
    metadata = {"level", "cefr", "week", "theme"}
    # Week-file field -> the ledger kind that delivers it.
    ledgered = {
        "vocabulary": "vocabulary",
        "listening": "listening",
        "speaking_missions": "speaking_missions",
        "writing_prompts": "writing_prompts",
        "phoneme_focus": "phoneme_focus",
        "grammar_point": "grammar_point",
        "can_do": "can_do_goals",
        # `grammar_pattern` is the pattern NAME; the pattern itself (and its
        # sub-items) is delivered from content/{level}/grammar/weekN.json and
        # ledgered as grammar_pattern/grammar_sub_items.
        "grammar_pattern": "grammar_pattern",
    }
    seen = set()
    for level in coverage_ledger.CEFR_LEVELS:
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            seen |= set(curriculum._weekly_data.get(f"{level}_{week}", {}) or {})
    unaccounted = seen - metadata - set(ledgered)
    assert not unaccounted, (
        f"week files carry authored field(s) the coverage ledger does not "
        f"track: {sorted(unaccounted)}. Deliver them to students and ledger "
        f"them, or classify them as metadata — do not leave them invisible."
    )


def test_totals_match_the_audited_counts(rep):
    """Pin the headline numbers from the 2026-08-24 audit so a silent content
    loss (or an accidental duplication) is visible immediately."""
    t = rep["totals"]
    assert t["vocabulary"]["authored"] == 2909
    assert t["accent_drills"]["authored"] == 630
    assert t["speaking_missions"]["authored"] == 630
    assert t["writing_prompts"]["authored"] == 630
    assert t["listening"]["authored"] == 450
    assert t["grammar_pattern"]["authored"] == 90
    assert t["grammar_sub_items"]["authored"] == 1208


# ============================================================
#  THE GATE MUST BE ABLE TO FAIL (a guard that can't fail is theatre)
# ============================================================

def test_gate_detects_an_orphan(monkeypatch, load_curriculum):
    """Re-introduce the ORIGINAL vocabulary bug and prove the ledger catches
    it. Without this, a green gate proves nothing."""
    def lossy_split(week, day_index, level="A1"):
        words = curriculum.get_vocabulary_for_week(week, level)
        if not words:
            return []
        per_day = max(1, len(words) // 7)   # the bug: remainder discarded
        start = (day_index % 7) * per_day
        return words[start:start + per_day]

    monkeypatch.setattr(curriculum, "get_vocabulary_for_day", lossy_split)
    broken = coverage_ledger.report()
    assert broken["orphaned_atoms"] == 354, (
        "the ledger did not detect the historical 354-word loss "
        f"(got {broken['orphaned_atoms']})"
    )
    assert any(s["kind"] == "vocabulary" for s in broken["shortfalls"])


def test_gate_detects_a_missing_delivery_route(monkeypatch, load_curriculum):
    """If a delivery accessor stops returning content, the gate must fail —
    this is how the 450 orphaned listening items would be caught today."""
    monkeypatch.setattr(curriculum, "get_listening_for_day",
                        lambda *a, **k: [])
    broken = coverage_ledger.report()
    assert broken["orphaned_atoms"] == 450
    assert all(s["kind"] == "listening" for s in broken["shortfalls"])


# ============================================================
#  DESCRIPTOR COVERAGE — reported, pinned, honest
# ============================================================

def test_untaught_descriptors_match_the_pinned_baseline(rep):
    """A1-B2 do not yet teach every descriptor they publish: reading and
    mediation have no task (spec Phase 11B). That is tracked debt, not a
    delivery bug, so it is pinned to an EXACT set.

    Pinned both ways on purpose: the gate fails if a new descriptor becomes
    untaught, AND fails if one is closed without updating the baseline. The
    number can never drift silently in either direction.
    """
    actual = set(rep["untaught_descriptors"])
    expected = set(coverage_ledger.KNOWN_UNTAUGHT_DESCRIPTORS)
    assert actual == expected, (
        f"descriptor coverage changed.\n"
        f"  newly untaught: {sorted(actual - expected)}\n"
        f"  now taught (update KNOWN_UNTAUGHT_DESCRIPTORS): {sorted(expected - actual)}"
    )


def test_c1_and_c2_teach_every_descriptor_they_publish(rep):
    """C1/C2 already have full descriptor coverage — it must not regress."""
    for level in ("C1", "C2"):
        assert rep["levels"][level]["untaught_descriptors"] == [], (
            f"{level} lost descriptor coverage: "
            f"{rep['levels'][level]['untaught_descriptors']}"
        )


def test_reading_and_mediation_are_the_known_structural_gap(rep):
    """Documents WHY the baseline is non-empty: the untaught set is dominated
    by reading (.R.) and mediation (.M.) because neither has a task yet."""
    untaught = rep["untaught_descriptors"]
    assert untaught, "baseline unexpectedly empty — update this test if Phase 11B is done"
    modes = {code.split(".")[1] for code in untaught}
    assert {"R", "M"} <= modes, f"expected reading+mediation gaps, saw modes {modes}"


# ============================================================
#  TRACKING — delivered is not enough; completion must be recorded
# ============================================================

def test_every_practice_page_exercise_is_a_tracked_exercise(rep):
    """An atom that a student can reach but whose completion is not recorded
    would still be invisible to mastery and the calendar."""
    for tracked in ("accent", "vocab", "shadow", "listening", "speaking", "grammar"):
        assert tracked in database.TRACKED_EXERCISES, (
            f"{tracked} is delivered but not a tracked exercise"
        )


def test_weekly_exercises_stay_out_of_the_day_green_requirement():
    """Tracking grammar must never turn into gating a day (that would break
    every existing streak). Re-asserted here so the coverage gate itself
    protects the safety property."""
    for weekly in database.WEEKLY_EXERCISES:
        assert weekly not in database.PRACTICE_EXERCISES
        assert weekly not in database.CALENDAR_EXERCISES
