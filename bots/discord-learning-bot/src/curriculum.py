"""Empire English Community Bot — Curriculum Data Loader.

Loads curated L0 curriculum from data/ and content/ JSON files.
Provides structured access to vocabulary, speaking missions, writing prompts,
accent drills, and grammar patterns per week and day.

This module bridges Phase 2 (curated content) with Phase 3 (bot delivery).
"""
import json
import logging
import re
import datetime
from pathlib import Path
from typing import Optional

from . import config

logger = logging.getLogger("empire-bot.curriculum")

# ============================================================
#  DATA DIRECTORIES
# ============================================================
DATA_DIR = config.BASE_DIR / "data"
CONTENT_DIR = config.BASE_DIR / "content"

# Number of curriculum weeks defined per level (single source of truth —
# used for loading, clamping, and quiz/spaced-repetition lookback windows).
# Any module that needs "how many weeks does this level have" must import
# this constant / call max_week_for_level() rather than hardcoding it,
# so L0/L1/L2/L3 never silently drift out of sync again.
LEVEL_WEEK_COUNTS = {"L0": 8, "L1": 10, "L2": 12, "L3": 8}


def max_week_for_level(level: str) -> int:
    """Number of curriculum weeks defined for a level (defaults to L0's 8)."""
    return LEVEL_WEEK_COUNTS.get(level, LEVEL_WEEK_COUNTS["L0"])


_WEEK_NUM_RE = re.compile(r"^week(\d+)")


def _parse_week_number(filename: str) -> Optional[int]:
    """Extract the week number from a content filename like 'week10_foo.json'.

    Content files were previously assigned a week number purely by their
    ALPHABETICAL sort position (enumerate(sorted(glob(...)), 1)) rather than
    by parsing the actual number in the filename. This is silently wrong for
    any level with 10+ weeks: Python string-sorts "week10" before "week2",
    so week10's content would be loaded and stored under key 2, and week2's
    content under some other wrong key. L0 never hit this bug (only 8 weeks,
    all single-digit), but L1 (10 weeks) and L2 (12 weeks) would have been
    silently corrupted. Parsing the number directly from the filename makes
    the mapping correct regardless of file count or sort order.
    """
    match = _WEEK_NUM_RE.match(filename)
    return int(match.group(1)) if match else None


# ============================================================
#  CACHE (loaded once at startup)
# ============================================================
_weekly_data: dict = {}   # {"L0_1": {...}, "L1_3": {...}, ...}
_accent_data: dict = {}   # {"L0": {1: {...}, 2: {...}}, "L1": {...}, ...}
_grammar_data: dict = {}  # {"L0": {1: {...}, 2: {...}}, "L1": {...}, ...}


def load_all():
    """Load all curriculum data from JSON files. Call once at bot startup."""
    global _weekly_data, _accent_data, _grammar_data

    # Load weekly data (vocab/speaking/writing) for ALL levels (L0-L3)
    for level, max_week in LEVEL_WEEK_COUNTS.items():
        for week in range(1, max_week + 1):
            path = DATA_DIR / f"{level.lower()}_week{week}.json"
            if path.exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        key = f"{level}_{week}"
                        _weekly_data[key] = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load {path}: {e}")

    # Count loaded
    l0_count = sum(1 for k in _weekly_data if k.startswith("L0_"))
    l1_count = sum(1 for k in _weekly_data if k.startswith("L1_"))
    l2_count = sum(1 for k in _weekly_data if k.startswith("L2_"))
    l3_count = sum(1 for k in _weekly_data if k.startswith("L3_"))
    logger.info(f"Weekly data: L0={l0_count}, L1={l1_count}, L2={l2_count}, L3={l3_count}")

    # Load accent drills and grammar patterns PER LEVEL.
    # Only content/l0/{accent,grammar}/ exist today — L1-L3 folders are
    # intentionally absent until that curriculum content is written.
    # A missing folder is NOT an error: it correctly results in an empty
    # dict for that level, which get_accent_drill()/get_grammar_pattern()
    # treat as "not available yet" rather than silently falling back to L0.
    for level in LEVEL_WEEK_COUNTS:
        level_lower = level.lower()
        _accent_data[level] = {}
        accent_dir = CONTENT_DIR / level_lower / "accent"
        if accent_dir.exists():
            for path in accent_dir.glob("week*.json"):
                week_num = _parse_week_number(path.name)
                if week_num is None:
                    logger.warning(f"Skipping {path}: filename doesn't start with 'weekN'")
                    continue
                try:
                    with open(path, encoding="utf-8") as f:
                        _accent_data[level][week_num] = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load {path}: {e}")

        _grammar_data[level] = {}
        grammar_dir = CONTENT_DIR / level_lower / "grammar"
        if grammar_dir.exists():
            for path in grammar_dir.glob("week*.json"):
                week_num = _parse_week_number(path.name)
                if week_num is None:
                    logger.warning(f"Skipping {path}: filename doesn't start with 'weekN'")
                    continue
                try:
                    with open(path, encoding="utf-8") as f:
                        _grammar_data[level][week_num] = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load {path}: {e}")

        logger.info(
            f"{level}: {len(_accent_data[level])} accent week(s), "
            f"{len(_grammar_data[level])} grammar week(s) loaded"
        )

    total_vocab = sum(len(w.get("vocabulary", [])) for w in _weekly_data.values())
    total_accent = sum(len(v) for v in _accent_data.values())
    total_grammar = sum(len(v) for v in _grammar_data.values())
    logger.info(f"Curriculum loaded: {len(_weekly_data)} total weeks, {total_vocab} vocab words, {total_accent} accent weeks, {total_grammar} grammar weeks")


# ============================================================
#  VOCABULARY ACCESS
# ============================================================

def get_vocabulary_for_week(week: int, level: str = "L0") -> list[dict]:
    """Get the vocabulary words for a given week and level.
    Each word: {word, pronunciation, arabic, pos}
    """
    key = f"{level}_{week}"
    data = _weekly_data.get(key, {})
    return data.get("vocabulary", [])


def get_vocabulary_for_day(week: int, day_index: int, level: str = "L0") -> list[dict]:
    """Get the 8 vocabulary words for a specific day (0=Saturday, 6=Friday).
    Splits the weekly words into 7 days of 8 words each.
    """
    all_words = get_vocabulary_for_week(week, level)
    if not all_words:
        return []
    day_index = day_index % 7
    words_per_day = max(1, len(all_words) // 7)
    start = day_index * words_per_day
    end = start + words_per_day
    return all_words[start:end]


def get_quiz_words(week: int, count: int = 10, level: str = "L0") -> list[dict]:
    """Get random words from this week + previous weeks for quiz verification."""
    import random
    all_words = []
    # Current week + last 2 weeks for spaced repetition
    for w in range(max(1, week - 2), week + 1):
        all_words.extend(get_vocabulary_for_week(w, level))
    if not all_words:
        return []
    return random.sample(all_words, min(count, len(all_words)))


# ============================================================
#  SPEAKING MISSIONS
# ============================================================

def get_speaking_mission(week: int, day_name: str, level: str = "L0") -> Optional[dict]:
    """Get the speaking mission for a specific week, day, and level.
    Returns: {type, prompt, target_seconds} or None.
    """
    key = f"{level}_{week}"
    data = _weekly_data.get(key, {})
    missions = data.get("speaking_missions", {})
    if isinstance(missions, dict):
        return missions.get(day_name)
    return None


# ============================================================
#  WRITING PROMPTS
# ============================================================

def get_writing_prompt(week: int, day_index: int, level: str = "L0") -> Optional[str]:
    """Get the writing prompt for a specific week, day (0-indexed), and level."""
    key = f"{level}_{week}"
    data = _weekly_data.get(key, {})
    prompts = data.get("writing_prompts", [])
    if isinstance(prompts, list) and day_index < len(prompts):
        return prompts[day_index]
    return None


# ============================================================
#  ACCENT DRILLS
# ============================================================

def has_accent_content(level: str) -> bool:
    """Whether any accent drill content has been authored for this level."""
    return bool(_accent_data.get(level))


def get_accent_drill(week: int, day_index: int, level: str = "L0") -> Optional[dict]:
    """Get the accent drill for a specific level, week, and day (0-indexed).

    Returns the daily drill dict from content/{level}/accent/weekX.json,
    or None if this level has no accent content authored yet — callers
    MUST handle None explicitly (e.g. an honest "coming soon" message)
    rather than assuming any level's drill is interchangeable with L0's.
    """
    level_data = _accent_data.get(level)
    if not level_data:
        return None
    week = min(max_week_for_level(level), max(1, week))
    data = level_data.get(week, {})
    daily_drills = data.get("daily_drills", [])
    if isinstance(daily_drills, list) and day_index < len(daily_drills):
        return daily_drills[day_index]
    return None


def get_accent_focus(week: int, level: str = "L0") -> Optional[str]:
    """Get this week's accent focus description for a level.
    Returns None if this level has no accent content authored yet.
    """
    week_clamped = min(max_week_for_level(level), max(1, week))
    level_data = _accent_data.get(level) or {}
    focus = level_data.get(week_clamped, {}).get("focus")
    if focus:
        return focus
    # L0 additionally has a hardcoded phoneme schedule fallback in
    # config.py (used before any JSON content existed). Preserve that
    # behavior for L0 only — L1-L3 have no such fallback table, so
    # "no content" must surface as None, not a fabricated guess.
    if level == "L0":
        return config.PHONEME_WEEKS.get(week_clamped, {}).get("focus")
    return None


def get_accent_focus_ar(week: int, level: str = "L0") -> str:
    """Get this week's accent focus in Arabic for a level (empty string if none)."""
    level_data = _accent_data.get(level)
    if not level_data:
        return ""
    week = min(max_week_for_level(level), max(1, week))
    data = level_data.get(week, {})
    return data.get("focus_ar", "")


# ============================================================
#  GRAMMAR PATTERNS
# ============================================================

def has_grammar_content(level: str) -> bool:
    """Whether any grammar pattern content has been authored for this level."""
    return bool(_grammar_data.get(level))


def get_grammar_pattern(week: int, level: str = "L0") -> Optional[dict]:
    """Get the grammar pattern card for a specific level and week.

    Returns full grammar pattern dict with formula, examples, practice, etc.,
    or None if this level has no grammar content authored yet.
    """
    level_data = _grammar_data.get(level)
    if not level_data:
        return None
    week = min(max_week_for_level(level), max(1, week))
    return level_data.get(week)


# ============================================================
#  DAILY TASK CONTENT (complete daily bundle)
# ============================================================

def get_daily_content(week: int, day_name: str, day_index: int, level: str = "L0") -> dict:
    """Get all curriculum content for a specific day.
    Returns a dict with all 7 tasks pre-populated from curated data.

    Clamps week to max_week_for_level() up front. get_accent_drill(),
    get_accent_focus(), and get_grammar_pattern() already did this
    clamping internally, but get_vocabulary_for_day()/get_speaking_mission()/
    get_writing_prompt() did not -- found via boundary-condition stress
    testing. config.LEVELS' own duration_weeks range for L0 is (8, 12),
    but curated content only exists for 8 weeks (LEVEL_WEEK_COUNTS), so any
    member still normally progressing in weeks 9-12 (not stuck, not
    failing -- simply within the level's own declared expected range) got
    real repeated week-8 accent/grammar content but a generic, non-curated
    "learn today's 8 new words" filler for vocab/speaking/writing instead
    of week 8's real curated content repeating like everything else does.
    Clamping once here, consistently, before any sub-lookup fixes that
    asymmetry for all six task types at once.
    """
    week = min(max_week_for_level(level), max(1, week))
    vocab = get_vocabulary_for_day(week, day_index, level)
    speaking = get_speaking_mission(week, day_name, level)
    writing = get_writing_prompt(week, day_index, level)
    accent = get_accent_drill(week, day_index, level)
    accent_focus = get_accent_focus(week, level)
    grammar = get_grammar_pattern(week, level)

    key = f"{level}_{week}"
    theme = _weekly_data.get(key, {}).get("theme", config.VOCAB_THEMES.get(week, "General"))

    return {
        "week": week,
        "day_name": day_name,
        "day_index": day_index,
        "level": level,
        "vocabulary": vocab,
        "speaking_mission": speaking,
        "writing_prompt": writing,
        "accent_drill": accent,
        "accent_focus": accent_focus,
        "grammar_pattern": grammar.get("pattern_name", "") if grammar else "",
        "theme": theme,
    }


# ============================================================
#  PRACTICE PLATFORM LINKS
#
# Maps a bot-side (level, week, day_index) task onto its exact page on
# empireenglishcommunity-glitch/empire-practice, so daily task messages
# can link students straight to the matching web exercise (with Kokoro
# TTS audio + browser-TTS fallback) instead of leaving accent/shadowing/
# listening/vocab as text-only Discord messages.
#
# Mapping is exact, not approximate:
#   - level:     "L0".."L3"  ->  "l0".."l3"           (folder name)
#   - week:      bot's week number == practice site's week number
#                (both now share LEVEL_WEEK_COUNTS as the single source
#                of truth: L0=8, L1=10, L2=12, L3=8 — verified identical)
#   - day_index: 0=Saturday..6=Friday (bot)  ->  day1=Saturday..day7=Friday
#                (practice site), via day = day_index + 1
# ============================================================

# Bot task id -> practice site page slug (no file extension). Only tasks
# that actually have a matching generated page are listed here;
# speaking/writing/community stay Discord-only by design (no fabricated
# links).
#
# NOTE: deliberately extensionless, not "accent.html" etc. Verified live
# that requesting the .html-suffixed path on the custom domain
# (practice.empireenglish.online) returns a genuine 404 (fresh,
# cache-control: no-store, reproduced on multiple never-before-requested
# paths), while the identical path WITHOUT the extension returns 200 on
# every domain that serves this Cloudflare Pages project (the pages.dev
# subdomain, the deployment-specific URL, and the custom domain alike).
# Root cause appears to be custom-domain-specific request handling in
# Cloudflare Pages (unconfirmed — could not fully diagnose without
# zone-level API access, which this project's API token does not have).
# Extensionless links are the verified-working form everywhere, so that
# is what the bot must generate.
_PRACTICE_PAGE_BY_TASK = {
    "accent": "accent",
    "vocab": "vocab",
    "shadow": "shadowing",
    "listening": "listening",
}


def practice_platform_day_url(week: int, day_index: int, level: str = "L0") -> str:
    """URL for the day's full exercise menu on the practice platform."""
    week = min(max_week_for_level(level), max(1, week))
    day = (day_index % 7) + 1
    return f"{config.PRACTICE_PLATFORM_URL}/{level.lower()}/week{week}/day{day}/"


def practice_platform_task_url(task_id: str, week: int, day_index: int, level: str = "L0") -> Optional[str]:
    """URL for a specific task's page on the practice platform.

    Returns None if this task has no corresponding practice-platform page
    (speaking, writing, community) — callers must handle that, not
    substitute the day-menu link as a stand-in.
    """
    page = _PRACTICE_PAGE_BY_TASK.get(task_id)
    if not page:
        return None
    week = min(max_week_for_level(level), max(1, week))
    day = (day_index % 7) + 1
    return f"{config.PRACTICE_PLATFORM_URL}/{level.lower()}/week{week}/day{day}/{page}"


# ============================================================
#  UTILITY
# ============================================================

def get_theme(week: int, level: str = "L0") -> str:
    """Get the vocabulary theme for a week and level."""
    key = f"{level}_{week}"
    data = _weekly_data.get(key, {})
    return data.get("theme", config.VOCAB_THEMES.get(week, "General"))


def is_loaded() -> bool:
    """Check if curriculum data has been loaded."""
    return len(_weekly_data) > 0


def stats() -> dict:
    """Get curriculum data statistics."""
    total_vocab = sum(len(w.get("vocabulary", [])) for w in _weekly_data.values())
    total_speaking = sum(
        len(w.get("speaking_missions", {})) if isinstance(w.get("speaking_missions"), dict) else 0
        for w in _weekly_data.values()
    )
    total_writing = sum(
        len(w.get("writing_prompts", [])) if isinstance(w.get("writing_prompts"), list) else 0
        for w in _weekly_data.values()
    )
    # _accent_data / _grammar_data are keyed {level: {week: {...}}}, so sum
    # the per-level week counts rather than counting the levels themselves.
    total_accent_weeks = sum(len(v) for v in _accent_data.values())
    total_grammar_weeks = sum(len(v) for v in _grammar_data.values())
    accent_levels_covered = sorted(lvl for lvl, v in _accent_data.items() if v)
    grammar_levels_covered = sorted(lvl for lvl, v in _grammar_data.items() if v)

    return {
        "weeks_loaded": len(_weekly_data),
        "total_vocabulary": total_vocab,
        "total_speaking_missions": total_speaking,
        "total_writing_prompts": total_writing,
        "accent_weeks": total_accent_weeks,
        "grammar_patterns": total_grammar_weeks,
        "accent_levels_covered": accent_levels_covered,
        "grammar_levels_covered": grammar_levels_covered,
    }
