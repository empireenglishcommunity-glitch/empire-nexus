"""Dhaka' (ذكاء) — Adaptive Difficulty Engine.

Adjusts task difficulty per student based on their pronunciation scoring
history. Uses a rolling 7-day average with hysteresis (3 consecutive
days above/below threshold before changing) to prevent oscillation.

Difficulty Levels:
  1 = Easy:        avg < 50% for 3+ days → repeat material, simpler sentences
  2 = Normal:      default — standard curriculum progression
  3 = Challenging: avg >= 85% for 3+ days → faster speed, longer sentences

This module is DORMANT until real scoring data exists (minimum 7 scores).
The code runs on every scoring event but exits immediately if insufficient data.

Gated behind the 'tatawwur_adaptive' feature flag.
"""
import logging
from typing import Optional

from . import database

logger = logging.getLogger("empire-bot.adaptive")

# ============================================================
#  CONSTANTS
# ============================================================

DIFFICULTY_EASY = 1
DIFFICULTY_NORMAL = 2
DIFFICULTY_CHALLENGING = 3

# Thresholds for adjustment
THRESHOLD_UP = 85.0      # avg >= 85% → consider raising difficulty
THRESHOLD_DOWN = 50.0    # avg <= 50% → consider lowering difficulty
MIN_SCORES_REQUIRED = 7  # Need at least 7 scores before any adjustment
HYSTERESIS_DAYS = 3      # Must be above/below threshold for 3 consecutive scoring events


# ============================================================
#  PUBLIC API
# ============================================================

def get_difficulty(discord_id: str) -> int:
    """Get current difficulty level for a member (1/2/3)."""
    member = database.get_member(discord_id)
    if not member:
        return DIFFICULTY_NORMAL
    return member.get("difficulty_level", DIFFICULTY_NORMAL)


def get_difficulty_label(level: int) -> str:
    """Human-readable difficulty label."""
    return {
        DIFFICULTY_EASY: "Easy / سهل",
        DIFFICULTY_NORMAL: "Normal / عادي",
        DIFFICULTY_CHALLENGING: "Challenging / متقدم",
    }.get(level, "Normal / عادي")


def get_difficulty_emoji(level: int) -> str:
    """Emoji for difficulty display."""
    return {
        DIFFICULTY_EASY: "🟢",
        DIFFICULTY_NORMAL: "🟡",
        DIFFICULTY_CHALLENGING: "🔴",
    }.get(level, "🟡")


def get_content_adjustments(difficulty: int) -> dict:
    """Get content adjustment parameters for a given difficulty level.

    Used by tasks.py when generating daily tasks to adjust:
    - TTS speed for shadowing
    - Number of minimal pairs
    - Sentence length preference
    - Whether to repeat or advance
    """
    if difficulty == DIFFICULTY_EASY:
        return {
            "tts_speed": 0.5,
            "max_minimal_pairs": 3,
            "max_practice_words": 5,
            "prefer_repetition": True,
            "sentence_length": "short",  # prefer record_this sentences ≤ 8 words
        }
    elif difficulty == DIFFICULTY_CHALLENGING:
        return {
            "tts_speed": 1.0,
            "max_minimal_pairs": 7,
            "max_practice_words": 10,
            "prefer_repetition": False,
            "sentence_length": "long",  # prefer longer sentences (15+ words)
        }
    else:  # NORMAL
        return {
            "tts_speed": 0.7,
            "max_minimal_pairs": 5,
            "max_practice_words": 8,
            "prefer_repetition": False,
            "sentence_length": "medium",
        }


def check_and_adjust(discord_id: str) -> Optional[dict]:
    """Check if difficulty should change based on recent scores.

    Called after each pronunciation score is stored.
    Returns a dict with adjustment info if changed, or None if no change.

    Logic:
    1. Get last 7+ scores
    2. If fewer than MIN_SCORES_REQUIRED → do nothing (not enough data)
    3. Calculate rolling average
    4. Check hysteresis: were the last HYSTERESIS_DAYS scores ALL above/below threshold?
    5. If yes → adjust difficulty
    6. Update members.difficulty_level
    7. Return adjustment info for notification
    """
    # Hisn D034 fix: MUST pass discord_id here. Calling
    # is_feature_enabled() with no discord_id treats an allowlist-scoped
    # flag as disabled for EVERYONE, even members who are actually on
    # the allowlist -- the exact same bug class already found and fixed
    # twice in Masar M2's code (see STATUS.md's "Rule going forward").
    if not database.is_feature_enabled("tatawwur_adaptive", discord_id):
        return None

    scores = database.get_recent_scores(discord_id, days=30)
    if len(scores) < MIN_SCORES_REQUIRED:
        return None  # Not enough data yet

    current_difficulty = get_difficulty(discord_id)

    # Get the last N scores for hysteresis check
    recent_scores = [s["score"] for s in scores[:HYSTERESIS_DAYS]]
    if len(recent_scores) < HYSTERESIS_DAYS:
        return None

    # Calculate 7-day rolling average
    last_7 = [s["score"] for s in scores[:7]]
    avg_7d = sum(last_7) / len(last_7)

    # Check if we should go UP (Normal → Challenging, or Easy → Normal)
    if current_difficulty < DIFFICULTY_CHALLENGING:
        all_above = all(s >= THRESHOLD_UP for s in recent_scores)
        if all_above and avg_7d >= THRESHOLD_UP:
            new_difficulty = current_difficulty + 1
            _set_difficulty(discord_id, new_difficulty)
            logger.info(f"Adaptive: {discord_id} difficulty UP {current_difficulty}→{new_difficulty} (avg={avg_7d:.0f}%)")
            return {
                "direction": "up",
                "old": current_difficulty,
                "new": new_difficulty,
                "average": avg_7d,
                "label": get_difficulty_label(new_difficulty),
                "emoji": get_difficulty_emoji(new_difficulty),
            }

    # Check if we should go DOWN (Challenging → Normal, or Normal → Easy)
    if current_difficulty > DIFFICULTY_EASY:
        all_below = all(s <= THRESHOLD_DOWN for s in recent_scores)
        if all_below and avg_7d <= THRESHOLD_DOWN:
            new_difficulty = current_difficulty - 1
            _set_difficulty(discord_id, new_difficulty)
            logger.info(f"Adaptive: {discord_id} difficulty DOWN {current_difficulty}→{new_difficulty} (avg={avg_7d:.0f}%)")
            return {
                "direction": "down",
                "old": current_difficulty,
                "new": new_difficulty,
                "average": avg_7d,
                "label": get_difficulty_label(new_difficulty),
                "emoji": get_difficulty_emoji(new_difficulty),
            }

    return None  # No change needed


# ============================================================
#  INTERNAL
# ============================================================

def _set_difficulty(discord_id: str, level: int):
    """Update member's difficulty level in database."""
    database.update_member(discord_id, difficulty_level=level)
