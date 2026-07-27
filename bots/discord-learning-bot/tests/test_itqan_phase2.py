"""Itqan Phase 2 — scoring engine. Pure functions + two-dimension verdict."""
from src import assessment, database


# ---- objective (vocab / listening) ----

def test_objective_correct_and_forgiving_typo():
    item = {"payload": {"expected": "house"}}
    assert assessment.score_objective(item, "house")["correct"] is True
    assert assessment.score_objective(item, "  HOUSE ")["correct"] is True
    assert assessment.score_objective(item, "hous")["correct"] is True   # 1-char typo
    r = assessment.score_objective(item, "car")
    assert r["correct"] is False and r["auto_score"] == 0.0
    assert "house" in r["feedback"]


# ---- pronunciation (from transcript) ----

def test_pronunciation_scores():
    assert assessment.score_pronunciation("water", "water")["ai_score"] == 100.0
    assert assessment.score_pronunciation("water", "I said water clearly")["ai_score"] == 100.0
    assert assessment.score_pronunciation("water", "banana")["ai_score"] == 0.0


# ---- speaking (lenient, rewards real attempt + target words) ----

def test_speaking_rewards_attempt_and_targets():
    empty = assessment.score_speaking(["morning", "coffee"], "")
    assert empty["ai_score"] == 0.0
    attempt = assessment.score_speaking(["morning", "coffee"], "in the morning i drink coffee every day")
    assert attempt["ai_score"] == 100.0  # both targets + long enough
    weak = assessment.score_speaking(["morning", "coffee"], "i wake up")
    assert 0 < weak["ai_score"] < 100  # real attempt, no targets → partial


# ---- writing ----

def test_writing_rewards_length_and_targets():
    assert assessment.score_writing(["family"], "no")["ai_score"] == 0.0
    good = assessment.score_writing(["family"], "I love my family and we eat together every evening.")
    assert good["ai_score"] == 100.0


# ---- consistency (from practice_mastery) ----

def test_consistency_from_week_completion(monkeypatch):
    # Fake calendar mastery: all 4 core done on 7 days of week 2 → 100%.
    core = database.PRACTICE_EXERCISES
    full = {(2, d): {"exercises": {c: 1 for c in core}} for d in range(1, 8)}
    monkeypatch.setattr(database, "get_calendar_mastery", lambda did, lvl: full)
    assert assessment.compute_consistency("u1", "L0", 2) == 100.0

    # Only half the cells done → 50%.
    half = {(2, d): {"exercises": {c: (1 if i < 2 else 0) for i, c in enumerate(core)}}
            for d in range(1, 8)}
    monkeypatch.setattr(database, "get_calendar_mastery", lambda did, lvl: half)
    assert assessment.compute_consistency("u1", "L0", 2) == 50.0


# ---- final verdict ----

CFG = {"itqan_mastery_pass_pct": 70, "itqan_consistency_pass_pct": 70,
       "itqan_distinction_pct": 90, "itqan_retake_cooldown_min": 720,
       "itqan_spiral_recent_weight": 0.65, "itqan_time_limit_min": 15}


def test_verdict_mastered():
    v = assessment.score_attempt([80, 90, 100, 75], consistency_pct=85, cfg=CFG)
    assert v["result"] == "mastered"
    assert v["status"] == "scored"
    assert v["distinction"] is False


def test_verdict_distinction():
    v = assessment.score_attempt([95, 90, 100, 92], consistency_pct=100, cfg=CFG)
    assert v["result"] == "mastered" and v["distinction"] is True


def test_verdict_not_yet_low_mastery():
    v = assessment.score_attempt([40, 30, 50, 20], consistency_pct=100, cfg=CFG)
    assert v["result"] == "not_yet"


def test_verdict_not_yet_when_inconsistent_even_if_smart():
    # High mastery but they didn't do the daily work → not a pass.
    v = assessment.score_attempt([95, 95, 95, 95], consistency_pct=40, cfg=CFG)
    assert v["result"] == "not_yet"


def test_verdict_clear_pass_is_not_flagged():
    # Right on the line = a clear pass → celebrate immediately, no review limbo.
    v = assessment.score_attempt([70, 70, 70, 70], consistency_pct=90, cfg=CFG)
    assert v["result"] == "mastered"
    assert v["status"] == "scored"
    assert v["flag_reason"] == ""


def test_verdict_flagged_on_near_miss_below_line():
    # Did the daily work (consistency met) but landed just below the line → rescue candidate.
    v = assessment.score_attempt([66, 66, 66, 66], consistency_pct=90, cfg=CFG)
    assert v["result"] == "not_yet"
    assert v["status"] == "flagged"
    assert v["flag_reason"] == "near_miss"


def test_verdict_clear_not_yet_is_not_flagged():
    # Well below the line → honest not-yet, supportive path (no owner review).
    v = assessment.score_attempt([50, 50, 50, 50], consistency_pct=90, cfg=CFG)
    assert v["result"] == "not_yet"
    assert v["status"] == "scored"
    assert v["flag_reason"] == ""


def test_verdict_flagged_on_ai_error_only_when_not_passed():
    # AI item errored AND they didn't clearly pass → flag for owner re-score.
    v = assessment.score_attempt([50, 50, 50], consistency_pct=90, has_ai_error=True, cfg=CFG)
    assert v["status"] == "flagged"
    assert v["flag_reason"] == "ai_error"
    # But a clear pass despite an AI error just passes (their score cleared the bar).
    v2 = assessment.score_attempt([90, 90, 90], consistency_pct=90, has_ai_error=True, cfg=CFG)
    assert v2["status"] == "scored"
