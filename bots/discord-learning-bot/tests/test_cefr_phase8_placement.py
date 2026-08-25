"""Phase 8 (Mi'yar CEFR) — placement engine: band arithmetic, adaptive routing,
the conservative per-skill overall rule, item pool, and slotting.

Pure logic + storage; no network. Verifies R6 behaviour, especially the
conservative slotting that is the heart of the requirement.
"""
import pytest

from src import config, database, placement


# ── band arithmetic ──

def test_band_index_and_clamp_and_legacy():
    assert placement.band_index("A1") == 0
    assert placement.band_index("C2") == 5
    assert placement.band_index("L2") == 2   # legacy L2 -> B1 -> index 2
    assert placement.index_to_band(-3) == "A1"   # clamp low
    assert placement.index_to_band(99) == "C2"   # clamp high
    assert placement.index_to_band(3) == "B2"


# ── adaptive routing ──

@pytest.mark.parametrize("idx,rate,expected", [
    (2, 0.90, 3),   # strong -> step up
    (2, 0.30, 1),   # weak   -> step down
    (2, 0.60, 2),   # middling -> hold
    (5, 0.95, 5),   # already top -> clamp
    (0, 0.10, 0),   # already bottom -> clamp
])
def test_step_band(idx, rate, expected):
    assert placement.step_band(idx, rate) == expected


# ── resolve one skill from its probe blocks ──

def test_resolve_skill_band_is_highest_PASSED_not_highest_attempted():
    # passed A2 and B1, attempted (failed) B2 -> resolves to B1, not B2
    blocks = [
        {"band": "A2", "correct_rate": 0.9},
        {"band": "B1", "correct_rate": 0.7},
        {"band": "B2", "correct_rate": 0.2},
    ]
    assert placement.resolve_skill_band(blocks) == "B1"


def test_resolve_skill_band_none_passed_returns_lowest_probed():
    blocks = [{"band": "B1", "correct_rate": 0.3}, {"band": "A2", "correct_rate": 0.4}]
    assert placement.resolve_skill_band(blocks) == "A2"


def test_resolve_skill_band_empty():
    assert placement.resolve_skill_band([]) == "A1"


# ── the conservative overall rule (R6 heart) ──

def test_conservative_equal_skills_place_at_that_level():
    bands = {s: "B1" for s in placement.PLACEMENT_SKILLS}
    # mean=2(B1), min+1=3(B2) -> lower = B1
    assert placement.conservative_overall(bands) == "B1"


def test_conservative_one_weak_skill_does_not_trap_at_floor():
    # three B1 + one A1: mean=round(1.5)=2 or 1 depending, min+1 = A2
    bands = {"vocab_grammar": "B1", "listening": "B1", "writing": "B1", "speaking": "A1"}
    # min index 0 -> min+1 = 1 (A2); mean of [2,2,2,0]=1.5 -> round=2; lower = A2
    assert placement.conservative_overall(bands) == "A2"


def test_conservative_one_spike_does_not_over_place():
    bands = {"vocab_grammar": "A1", "listening": "A1", "writing": "A1", "speaking": "C2"}
    # indices [0,0,0,5]; mean=round(1.25)=1(A2); min+1=1(A2); lower=A2
    assert placement.conservative_overall(bands) == "A2"


def test_conservative_empty_defaults_a1():
    assert placement.conservative_overall({}) == "A1"


# ── item pool ──

def test_build_placement_pool_has_items_per_band():
    pool = placement.build_placement_pool()
    assert set(pool.keys()) == set(config.CEFR_ORDER)
    for band, items in pool.items():
        assert len(items) > 0, f"{band} placement pool is empty"
        # items are vocab dicts with a word
        assert any(it.get("word") for it in items)


# ── orchestrator: save + opt-in slotting ──

def test_place_student_saves_without_slotting_by_default():
    database.register_member("plc1", "Test")
    before = (database.get_member("plc1") or {}).get("level")
    bands = {"vocab_grammar": "A2", "listening": "A2", "writing": "A1", "speaking": "A1"}
    res = placement.place_student("plc1", bands, slot=False, source="self")
    assert res["slotted"] is False
    # member level unchanged (never force-slotted)
    assert (database.get_member("plc1") or {}).get("level") == before
    # but the result is stored
    saved = database.latest_placement_result("plc1")
    assert saved["overall_level"] == res["overall_level"]
    assert saved["skill_bands"] == bands


def test_place_student_slots_to_week1_when_opted_in():
    database.register_member("plc2", "Test")
    bands = {"vocab_grammar": "B1", "listening": "B1", "writing": "B1", "speaking": "B1"}
    res = placement.place_student("plc2", bands, slot=True, source="self")
    assert res["slotted"] is True and res["overall_level"] == "B1"
    assert (database.get_member("plc2") or {}).get("level") == "B1"
