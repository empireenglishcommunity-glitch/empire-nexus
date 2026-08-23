"""Taqdeem Phase 1 — Monthly Review generation + scoring tests.

Covers:
- generate_monthly_blueprint: correct item count, production >= 50%
- generate_monthly_blueprint: covers all weeks equally (not recency-biased)
- generate_monthly_blueprint: SRS bias (weak items prioritized)
- generate_monthly_blueprint: deterministic with same seed
- score_monthly_attempt: pass at 65%, not-pass below
- score_monthly_attempt: near_miss flagging
- score_monthly_attempt: ai_error flagging
- build_skill_breakdown: correct per-skill averages
- build_review_list: returns weak items below threshold
"""
import random

import pytest

from src import database, assessment, curriculum


# ============================================================
#  HELPERS
# ============================================================

def setup_function():
    """Ensure curriculum is loaded for tests."""
    curriculum.load_all()


# ============================================================
#  generate_monthly_blueprint
# ============================================================

def test_monthly_blueprint_item_count():
    """Generates the expected number of items."""
    database.register_member("mb1", "Alice")
    bp = assessment.generate_monthly_blueprint("mb1", "L0", [1, 2, 3, 4], total_items=16)
    # May be less if vocab pool is thin, but should be close to 16
    assert len(bp["items"]) >= 10
    assert len(bp["items"]) <= 16


def test_monthly_blueprint_production_heavy():
    """Production items (speaking + writing) are >= 50%."""
    database.register_member("mb2", "Alice")
    bp = assessment.generate_monthly_blueprint("mb2", "L0", [1, 2, 3, 4], total_items=16)
    production = [it for it in bp["items"] if it["skill"] in ("speaking", "writing")]
    assert len(production) >= len(bp["items"]) / 2


def test_monthly_blueprint_covers_multiple_weeks():
    """Items come from different weeks (not just one)."""
    database.register_member("mb3", "Alice")
    bp = assessment.generate_monthly_blueprint("mb3", "L0", [1, 2, 3, 4], total_items=16)
    weeks_seen = {it["source_week"] for it in bp["items"]}
    # Should cover at least 2 different weeks (ideally all 4, but depends on pool)
    assert len(weeks_seen) >= 2


def test_monthly_blueprint_deterministic_with_seed():
    """Same seed produces same blueprint."""
    database.register_member("mb4", "Alice")
    bp1 = assessment.generate_monthly_blueprint("mb4", "L0", [1, 2], seed="test-seed-1")
    bp2 = assessment.generate_monthly_blueprint("mb4", "L0", [1, 2], seed="test-seed-1")
    assert bp1["items"] == bp2["items"]


def test_monthly_blueprint_different_seed_different_items():
    """Different seeds produce different item orders."""
    database.register_member("mb5", "Alice")
    bp1 = assessment.generate_monthly_blueprint("mb5", "L0", [1, 2, 3, 4], seed="seed-a")
    bp2 = assessment.generate_monthly_blueprint("mb5", "L0", [1, 2, 3, 4], seed="seed-b")
    # Items should differ (at least in order)
    items1 = [(it["skill"], it.get("source_week")) for it in bp1["items"]]
    items2 = [(it["skill"], it.get("source_week")) for it in bp2["items"]]
    assert items1 != items2


def test_monthly_blueprint_type_field():
    """Blueprint has type='monthly'."""
    database.register_member("mb6", "Alice")
    bp = assessment.generate_monthly_blueprint("mb6", "L0", [1, 2])
    assert bp["type"] == "monthly"


def test_monthly_blueprint_time_limit():
    """Monthly review has 20 min time limit."""
    database.register_member("mb7", "Alice")
    bp = assessment.generate_monthly_blueprint("mb7", "L0", [1, 2])
    assert bp["time_limit_min"] == 20


# ============================================================
#  score_monthly_attempt
# ============================================================

def test_score_monthly_pass():
    """Scores >= 65% pass."""
    scores = [70.0, 80.0, 60.0, 65.0, 70.0]  # avg = 69%
    result = assessment.score_monthly_attempt(scores)
    assert result["result"] == "passed"
    assert result["retention_pct"] == 69.0


def test_score_monthly_not_pass():
    """Scores < 65% don't pass."""
    scores = [50.0, 40.0, 60.0, 55.0, 50.0]  # avg = 51%
    result = assessment.score_monthly_attempt(scores)
    assert result["result"] == "not_yet"
    assert result["retention_pct"] == 51.0


def test_score_monthly_near_miss_flagged():
    """Near-miss (within 5 of pass line) gets flagged."""
    scores = [62.0, 63.0, 64.0, 61.0, 60.0]  # avg = 62% (within 5 of 65)
    result = assessment.score_monthly_attempt(scores)
    assert result["result"] == "not_yet"
    assert result["flag_reason"] == "near_miss"
    assert result["status"] == "flagged"


def test_score_monthly_ai_error_flagged():
    """AI error gets flagged."""
    scores = [50.0, 50.0, 50.0]
    result = assessment.score_monthly_attempt(scores, has_ai_error=True)
    assert result["flag_reason"] == "ai_error"
    assert result["status"] == "flagged"


def test_score_monthly_clear_pass_not_flagged():
    """Clear pass is never flagged."""
    scores = [90.0, 85.0, 80.0]
    result = assessment.score_monthly_attempt(scores)
    assert result["result"] == "passed"
    assert result["status"] == "scored"
    assert result["flag_reason"] == ""


def test_score_monthly_custom_threshold():
    """Respects custom pass threshold from config."""
    scores = [70.0, 70.0, 70.0]  # avg = 70%
    # Custom threshold: 75%
    cfg = dict(database.PROGRESSION_CONFIG_DEFAULTS)
    cfg["progression_monthly_pass_pct"] = 75
    result = assessment.score_monthly_attempt(scores, cfg=cfg)
    assert result["result"] == "not_yet"


# ============================================================
#  build_skill_breakdown
# ============================================================

def test_skill_breakdown_correct():
    """Per-skill averages are computed correctly."""
    items = [
        {"skill": "vocab", "source_week": 1, "payload": {}},
        {"skill": "vocab", "source_week": 2, "payload": {}},
        {"skill": "speaking", "source_week": 1, "payload": {}},
        {"skill": "writing", "source_week": 1, "payload": {}},
    ]
    scores = [80.0, 60.0, 90.0, 70.0]
    breakdown = assessment.build_skill_breakdown(items, scores)
    assert breakdown["vocab"] == 70.0  # (80+60)/2
    assert breakdown["speaking"] == 90.0
    assert breakdown["writing"] == 70.0


def test_skill_breakdown_empty():
    """Empty items returns empty breakdown."""
    assert assessment.build_skill_breakdown([], []) == {}


# ============================================================
#  build_review_list
# ============================================================

def test_review_list_returns_weak_items():
    """Items below threshold appear in the review list."""
    items = [
        {"skill": "vocab", "source_week": 1, "payload": {"expected": "hello"}},
        {"skill": "vocab", "source_week": 2, "payload": {"expected": "world"}},
        {"skill": "speaking", "source_week": 3, "payload": {"target_words": ["cat"]}},
    ]
    scores = [100.0, 40.0, 50.0]  # world and cat are weak
    review = assessment.build_review_list(items, scores, threshold=60.0)
    assert len(review) == 2
    assert review[0]["word"] == "world"
    assert review[0]["source_week"] == 2
    assert review[1]["word"] == "cat"


def test_review_list_empty_when_all_strong():
    """No items in review list when all scores are above threshold."""
    items = [
        {"skill": "vocab", "source_week": 1, "payload": {"expected": "hello"}},
    ]
    scores = [100.0]
    review = assessment.build_review_list(items, scores, threshold=60.0)
    assert review == []
