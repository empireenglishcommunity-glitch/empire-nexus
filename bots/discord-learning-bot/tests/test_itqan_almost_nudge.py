"""Tests for the Itqan 'almost there' nudge selection logic (G4).

Covers _almost_done_week(): it must pick the EARLIEST week that is 1–2 days
short (5–6/7 done), skip already-unlocked weeks, and return None when nothing
qualifies. We monkeypatch assessment.week_unlocked so the test exercises MY
selection logic directly, independent of the mastery/date machinery it delegates
to (which has its own tests).
"""
from src import itqan_outcomes, assessment, curriculum


def _patch(monkeypatch, states, max_week):
    monkeypatch.setattr(curriculum, "max_week_for_level", lambda lvl: max_week)
    monkeypatch.setattr(
        assessment, "week_unlocked",
        lambda did, lvl, w: states.get(w, (False, [1, 2, 3, 4, 5, 6, 7])),
    )


def test_picks_earliest_1_or_2_days_short(monkeypatch):
    # w1 done, w2 is 1 short, w3 is 2 short → earliest qualifying is w2.
    states = {1: (True, []), 2: (False, [5]), 3: (False, [4, 6])}
    _patch(monkeypatch, states, 8)
    assert itqan_outcomes._almost_done_week("s", "L0") == (2, [5])


def test_two_days_short_qualifies(monkeypatch):
    states = {1: (True, []), 2: (False, [3, 7])}
    _patch(monkeypatch, states, 8)
    assert itqan_outcomes._almost_done_week("s", "L0") == (2, [3, 7])


def test_three_or_more_days_short_does_not_qualify(monkeypatch):
    # Only weeks that are 1–2 short should nudge; 3+ short is "not close yet".
    states = {1: (True, []), 2: (False, [2, 4, 6])}
    _patch(monkeypatch, states, 8)
    assert itqan_outcomes._almost_done_week("s", "L0") is None


def test_all_done_returns_none(monkeypatch):
    states = {1: (True, []), 2: (True, []), 3: (True, [])}
    _patch(monkeypatch, states, 3)
    assert itqan_outcomes._almost_done_week("s", "L0") is None


def test_skips_unlocked_week_and_finds_a_later_close_one(monkeypatch):
    # w1 unlocked (skip), w2 far off (3 short), w3 is 1 short → picks w3.
    states = {1: (True, []), 2: (False, [1, 2, 3]), 3: (False, [6])}
    _patch(monkeypatch, states, 8)
    assert itqan_outcomes._almost_done_week("s", "L0") == (3, [6])
