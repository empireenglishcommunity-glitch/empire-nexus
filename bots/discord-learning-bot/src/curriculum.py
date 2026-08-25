"""Empire English Community Bot — Curriculum Data Loader.

Loads curated L0 curriculum from data/ and content/ JSON files.
Provides structured access to vocabulary, speaking missions, writing prompts,
accent drills, and grammar patterns per week and day.

This module bridges Phase 2 (curated content) with Phase 3 (bot delivery).
"""
import json
import logging
import re
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
# Legacy L0–L3 week counts — RETIRED (content deleted 2026-08-25). Empty so any
# lingering reference resolves harmlessly; CEFR is the only curriculum now.
LEVEL_WEEK_COUNTS: dict = {}

# Mi'yar (CEFR) week counts — the six CEFR levels, the single source of truth.
CEFR_WEEK_COUNTS = {"A1": 10, "A2": 12, "B1": 14, "B2": 16, "C1": 18, "C2": 20}


def max_week_for_level(level: str) -> int:
    """Number of curriculum weeks for a level. CEFR-only; any input normalises
    to a CEFR level (unknown → A1)."""
    if level in CEFR_WEEK_COUNTS:
        return CEFR_WEEK_COUNTS[level]
    from . import config
    return CEFR_WEEK_COUNTS.get(config.cefr_key(level), CEFR_WEEK_COUNTS["A1"])


def expected_week_count() -> int:
    """Total number of week data files that SHOULD exist on disk across all
    known levels (legacy L0–L3 + any authored CEFR levels A1–C2). The health
    check compares this to how many actually loaded, so it auto-adapts as CEFR
    levels are added yet still catches a file that failed to parse (loaded <
    expected). Only counts levels whose files are actually present, so an
    unauthored CEFR level (no files yet) doesn't inflate the expectation."""
    from . import config as _cfg
    total = 0
    all_counts = dict(LEVEL_WEEK_COUNTS)
    all_counts.update(CEFR_WEEK_COUNTS)
    for level, max_week in all_counts.items():
        for week in range(1, max_week + 1):
            if (DATA_DIR / f"{level.lower()}_week{week}.json").exists():
                total += 1
    return total


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
_reading_data: dict = {}  # {"A1": {1: {...}, ...}, ...} — Phase 11B, per level


def load_all():
    """Load all curriculum data from JSON files. Call once at bot startup."""
    global _weekly_data, _accent_data, _grammar_data, _reading_data

    # Load weekly data (vocab/speaking/writing) for ALL levels — legacy
    # (L0–L3) AND CEFR (A1–C2). CEFR files (data/a1_weekN.json …) are added
    # per level during the Mi'yar rollout; missing files are skipped safely,
    # so this is a no-op until CEFR content exists. Keying by the level string
    # means legacy and CEFR content coexist without collision during migration.
    _all_week_counts = dict(LEVEL_WEEK_COUNTS)
    _all_week_counts.update(CEFR_WEEK_COUNTS)
    for level, max_week in _all_week_counts.items():
        for week in range(1, max_week + 1):
            path = DATA_DIR / f"{level.lower()}_week{week}.json"
            if path.exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        key = f"{level}_{week}"
                        _weekly_data[key] = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load {path}: {e}")

    # Count loaded (CEFR only — legacy L0–L3 retired)
    counts = {lvl: sum(1 for k in _weekly_data if k.startswith(f"{lvl}_"))
              for lvl in CEFR_WEEK_COUNTS}
    logger.info("Weekly data: " + ", ".join(f"{k}={v}" for k, v in counts.items()))

    # Load accent drills and grammar patterns PER LEVEL.
    # Only content/l0/{accent,grammar}/ exist today — L1-L3 folders are
    # intentionally absent until that curriculum content is written.
    # A missing folder is NOT an error: it correctly results in an empty
    # dict for that level, which get_accent_drill()/get_grammar_pattern()
    # treat as "not available yet" rather than silently falling back to L0.
    for level in _all_week_counts:
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

        # Reading passages (Phase 11B — CEFR reception). Authored level by
        # level behind the owner approval gate, so a level with no
        # content/{level}/reading/ folder is NOT an error: it stays empty and
        # get_reading_for_week() reports "not authored yet" rather than
        # borrowing another level's text.
        _reading_data[level] = {}
        reading_dir = CONTENT_DIR / level_lower / "reading"
        if reading_dir.exists():
            for path in reading_dir.glob("week*.json"):
                week_num = _parse_week_number(path.name)
                if week_num is None:
                    logger.warning(f"Skipping {path}: filename doesn't start with 'weekN'")
                    continue
                try:
                    with open(path, encoding="utf-8") as f:
                        _reading_data[level][week_num] = json.load(f)
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

def get_vocabulary_for_week(week: int, level: str = "A1") -> list[dict]:
    """Get the vocabulary words for a given week and level.
    Each word: {word, pronunciation, arabic, pos}
    """
    key = f"{level}_{week}"
    data = _weekly_data.get(key, {})
    return data.get("vocabulary", [])


def get_vocabulary_for_day(week: int, day_index: int, level: str = "A1") -> list[dict]:
    """Get the vocabulary words for a specific day (0=Saturday, 6=Friday).

    Splits the week's words into 7 contiguous, non-overlapping day slices
    that together cover EVERY word exactly once.

    ZERO-LOSS INVARIANT (regression guard — this used to silently drop
    content): the previous implementation did

        words_per_day = max(1, len(all_words) // 7)
        return all_words[day_index * words_per_day:][:words_per_day]

    which truncates on integer division and never assigns the remainder to
    any day, so the last `len(all_words) % 7` words of EVERY week were
    unreachable for every student, forever. Measured cost across the 90
    authored weeks: 354 of 2,909 words (12.2%) — A2 lost 14.9%, and the
    worst single week (34 words -> 4/day -> 28 shown) lost 6 words.

    The fix distributes the remainder instead of discarding it: the first
    `len % 7` days get one extra word (`base + 1`), the rest get `base`.
    Slices stay contiguous and in authored order, so spaced-repetition and
    "day N teaches these words" semantics are unchanged — days simply get
    1 word longer where the remainder lands.

    empire-dojo's `scripts/generate.py` MUST mirror this split exactly
    (`database.record_vocab_quiz` and `verification.py` both assume the
    bot and the practice site agree word-for-word on what a given day
    teaches), so any change here must ship with the matching dojo change.
    """
    all_words = get_vocabulary_for_week(week, level)
    if not all_words:
        return []
    day_index = day_index % 7
    base, remainder = divmod(len(all_words), 7)
    if base == 0:
        # Fewer than 7 words authored: cycle so no day is empty. Every word
        # still appears (union over the 7 days == the full week list).
        return [all_words[day_index % len(all_words)]]
    # Days before `remainder` carry one extra word; offset accounts for the
    # extra words already handed out by earlier days.
    start = day_index * base + min(day_index, remainder)
    size = base + (1 if day_index < remainder else 0)
    return all_words[start:start + size]


def get_reading_for_week(week: int, level: str = "A1") -> Optional[dict]:
    """The week's authored reading passage, or None if not authored yet.

    Phase 11B (CEFR reception). Reading was the CEFR mode with NO task at all:
    the 7 daily tasks covered listening, speaking, writing, interaction and the
    enabling skills, but nothing asked a student to read. That is why A1-B2
    each had reading descriptors (`.R.`) that no week taught, and why those
    levels could not honestly claim full CEFR coverage.

    Authored level by level behind the owner approval gate (the convention set
    by content/cefr/*-ALIGNMENT.md), so `None` is a legitimate answer for a
    level whose passages are not written yet. Callers MUST render an honest
    "not available yet" rather than substituting another level's text.

    Shape: {id, level, cefr, week, title(_ar), can_do, word_count, gist_ar,
    text, glossary[{word, ar}], questions[{q, q_ar, options, answer}]}.
    """
    level_data = _reading_data.get(level)
    if not level_data:
        return None
    week = min(max_week_for_level(level), max(1, week))
    return level_data.get(week)


def reading_levels() -> list[str]:
    """Levels that actually have authored reading passages (for the ledger and
    for honest 'is this level complete yet' reporting)."""
    return sorted(lvl for lvl, weeks in _reading_data.items() if weeks)


def get_listening_for_week(week: int, level: str = "A1") -> list[dict]:
    """Get the week's authored listening/dictation targets.

    Each item: {say_en, expected, hint_ar} — `say_en` is spoken aloud (TTS),
    `expected` is what the student must type, `hint_ar` is the Arabic hint.
    All 90 authored weeks carry exactly 5 items (450 total).

    ORPHANED-CONTENT FIX: this array existed in every week file since the
    curriculum was authored but had NO accessor and NO consumer anywhere in
    the codebase — the practice site's listening page built its dictation
    from `vocabulary` instead, so the curated set (and all 450 `hint_ar`
    Arabic hints) never reached a single student. 98% of the items' words do
    also appear in that week's `vocabulary`, so students were not missing
    those *words* wholesale; what they were missing is the authored
    dictation selection and its Arabic hints (plus 10 items whose word is
    not in the week's vocab at all).
    """
    key = f"{level}_{week}"
    data = _weekly_data.get(key, {})
    items = data.get("listening", [])
    return items if isinstance(items, list) else []


def get_listening_for_day(week: int, day_index: int, level: str = "A1") -> list[dict]:
    """Get the day's listening/dictation targets (0=Saturday, 6=Friday).

    Only 5 items are authored per week against 7 days, so slicing them per
    day would leave 2 days empty and make coverage depend on WHICH days a
    student happens to do. Instead every day gets the full set, rotated by
    day so the order varies (start at `day_index % 5`). That guarantees all
    5 authored items reach the student on any day they practise, while the
    day-specific content on the page (the comprehension quiz, built from
    that day's vocabulary) still changes daily.
    """
    items = get_listening_for_week(min(max_week_for_level(level), max(1, week)), level)
    if not items:
        return []
    offset = (day_index % 7) % len(items)
    return items[offset:] + items[:offset]


def get_quiz_words(week: int, count: int = 10, level: str = "A1") -> list[dict]:
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

def get_speaking_mission(week: int, day_name: str, level: str = "A1") -> Optional[dict]:
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

def get_writing_prompt(week: int, day_index: int, level: str = "A1") -> Optional[str]:
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


def get_accent_drill(week: int, day_index: int, level: str = "A1") -> Optional[dict]:
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


def get_accent_focus(week: int, level: str = "A1") -> Optional[str]:
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


def get_accent_focus_ar(week: int, level: str = "A1") -> str:
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


def get_grammar_pattern(week: int, level: str = "A1") -> Optional[dict]:
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

def get_daily_content(week: int, day_name: str, day_index: int, level: str = "A1") -> dict:
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


def practice_platform_day_url(week: int, day_index: int, level: str = "A1") -> str:
    """URL for the day's full exercise menu on the practice platform."""
    week = min(max_week_for_level(level), max(1, week))
    day = (day_index % 7) + 1
    return f"{config.PRACTICE_PLATFORM_URL}/{level.lower()}/week{week}/day{day}/"


def practice_platform_task_url(task_id: str, week: int, day_index: int, level: str = "A1") -> Optional[str]:
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

def get_theme(week: int, level: str = "A1") -> str:
    """Get the vocabulary theme for a week and level."""
    key = f"{level}_{week}"
    data = _weekly_data.get(key, {})
    return data.get("theme", config.VOCAB_THEMES.get(week, "General"))


def get_can_do_for_week(week: int, level: str = "A1") -> list:
    """CEFR can-do descriptor codes a week targets (e.g. ['A1.P.1', 'A1.I.2']).
    Empty list if the week has none. Accepts CEFR or legacy keys."""
    from . import config
    for key in (f"{level}_{week}", f"{config.cefr_key(level)}_{week}"):
        data = _weekly_data.get(key)
        if data:
            return list(data.get("can_do", []) or [])
    return []


_can_do_library: dict = {}   # {"A1": {code: {code, en, ar, mode}}, ...}


def can_do_descriptor_map(level: str = "A1") -> dict:
    """{code: {code, en, ar, mode}} for a level, from content/cefr/can_do.json.

    Cached after first read. Returns {} on any failure (never raises) so a
    missing/corrupt library degrades to "no goals shown", never a crash in
    the daily flow.

    NOTE the file's per-level dict mixes list-valued modes (reception,
    production, interaction, mediation) with plain string keys
    (overview_en/overview_ar), so mode values MUST be isinstance-checked.
    """
    ck = config.cefr_key(level)
    if ck in _can_do_library:
        return _can_do_library[ck]
    out: dict = {}
    try:
        path = config.BASE_DIR / "content" / "cefr" / "can_do.json"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for mode, items in (data.get(ck) or {}).items():
            if not isinstance(items, list):
                continue  # overview_en / overview_ar are strings
            for item in items:
                if isinstance(item, dict) and item.get("code"):
                    out[item["code"]] = {
                        "code": item["code"],
                        "en": item.get("en", ""),
                        "ar": item.get("ar", ""),
                        "mode": mode,
                    }
    except Exception as e:
        logger.warning(f"can_do_descriptor_map({level}) failed: {e}")
        out = {}
    _can_do_library[ck] = out
    return out


def get_can_do_details_for_week(week: int, level: str = "A1") -> list[dict]:
    """The week's CEFR can-do goals RESOLVED to {code, en, ar, mode}.

    `get_can_do_for_week` only returns bare codes like "A1.P.1", which are
    meaningless to a student. This resolves them against the descriptor
    library so the daily flow can show the actual "I can ..." sentence in
    English and Arabic.

    Phase 11A-4: these goals are the whole point of a CEFR-aligned course,
    but they were invisible during study -- surfaced only on the Phase-9
    progress screen and the certificate, i.e. after the fact. Unknown codes
    are skipped rather than rendered as a raw code.
    """
    codes = get_can_do_for_week(min(max_week_for_level(level), max(1, week)), level)
    library = can_do_descriptor_map(level)
    return [library[c] for c in codes if c in library]


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
