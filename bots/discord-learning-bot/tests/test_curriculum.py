"""Tests for src/curriculum.py — curriculum data loading and access.

Uses the real data/ and content/ JSON files (via the session-scoped
load_curriculum fixture in conftest.py), not mocks, so these tests catch
real content regressions the same way the underlying data would actually
break the bot in production.
"""
from src import config, curriculum


# ============================================================
#  LOADING / COVERAGE
# ============================================================

def test_all_four_levels_loaded():
    stats = curriculum.stats()
    assert stats["weeks_loaded"] == 38  # 8 + 10 + 12 + 8, per LEVEL_WEEK_COUNTS


def test_level_week_counts_matches_loaded_weeks():
    for level, expected_weeks in curriculum.LEVEL_WEEK_COUNTS.items():
        for week in range(1, expected_weeks + 1):
            vocab = curriculum.get_vocabulary_for_week(week, level)
            assert vocab, f"{level} week {week} has no vocabulary loaded"


def test_max_week_for_level():
    assert curriculum.max_week_for_level("L0") == 8
    assert curriculum.max_week_for_level("L1") == 10
    assert curriculum.max_week_for_level("L2") == 12
    assert curriculum.max_week_for_level("L3") == 8


def test_max_week_for_level_unknown_defaults_to_l0():
    assert curriculum.max_week_for_level("L99") == curriculum.LEVEL_WEEK_COUNTS["L0"]


def test_accent_and_grammar_content_covers_all_levels():
    """As of 2026-07-11 all four levels have accent/grammar content
    authored (previously only L0 did). If a future change accidentally
    removes a level's content folder, this should fail loudly instead of
    curriculum.py's has_accent_content()/has_grammar_content() silently
    returning False for real students."""
    stats = curriculum.stats()
    assert stats["accent_levels_covered"] == ["L0", "L1", "L2", "L3"]
    assert stats["grammar_levels_covered"] == ["L0", "L1", "L2", "L3"]


def test_has_accent_content_and_has_grammar_content():
    for level in ("L0", "L1", "L2", "L3"):
        assert curriculum.has_accent_content(level)
        assert curriculum.has_grammar_content(level)


def test_has_accent_content_false_for_unknown_level():
    assert curriculum.has_accent_content("L99") is False


# ============================================================
#  VOCABULARY — WEEK-LEVEL
# ============================================================

def test_get_vocabulary_for_week_unknown_level_returns_empty():
    assert curriculum.get_vocabulary_for_week(1, "L99") == []


def test_get_vocabulary_for_week_unknown_week_returns_empty():
    assert curriculum.get_vocabulary_for_week(999, "L0") == []


def test_vocabulary_entries_have_required_fields():
    for level in ("L0", "L1", "L2", "L3"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            for entry in curriculum.get_vocabulary_for_week(week, level):
                assert entry.get("word"), f"{level} week {week} has a vocab entry with no word"
                assert "arabic" in entry
                assert "pronunciation" in entry
                assert "pos" in entry


def test_no_cross_week_exact_vocabulary_duplication():
    """Regression test for a real bug: 7 of L1's 10 weeks were silently
    serving Week 1's 'Daily Routines' vocabulary verbatim, despite each
    having its own correct, distinct theme. Guards against this (or any
    similar copy-paste) recurring in any level, at the exact boundary
    where the bot's own curriculum.py loader would serve it to students."""
    for level in ("L0", "L1", "L2", "L3"):
        seen = {}
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            words = tuple(w["word"] for w in curriculum.get_vocabulary_for_week(week, level))
            for prev_week, prev_words in seen.items():
                assert words != prev_words, (
                    f"{level} week {week} vocabulary is byte-identical to "
                    f"week {prev_week} — likely a copy-paste bug, not real content"
                )
            seen[week] = words


def test_vocabulary_word_count_reasonable_per_level():
    """Sanity floor — a week with e.g. 0-5 words would indicate a loading
    failure or an empty/corrupted file, not real curriculum content."""
    for level in ("L0", "L1", "L2", "L3"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            count = len(curriculum.get_vocabulary_for_week(week, level))
            assert count >= 30, f"{level} week {week} has suspiciously few words ({count})"


# ============================================================
#  VOCABULARY — DAY SPLIT (regression: bot vs. practice-site parity)
# ============================================================

def test_get_vocabulary_for_day_covers_whole_week_without_overlap():
    """The 7 daily slices for a week must be genuinely distinct day to
    day — this is the exact function whose splitting logic empire-dojo's
    generate.py must mirror byte-for-byte for the bot and practice
    website to ever agree on what a student sees on a given day.

    Compares each day's word LIST (not a flattened set of all words) to
    every other day's, since a handful of weeks legitimately contain the
    same word twice within their vocabulary on purpose — e.g. L2 week 1
    teaches "impact"/"protest"/"broadcast" as both noun and verb, with
    different stress/pronunciation and different Arabic meaning for each
    sense. That's real content, not a duplication bug, and can land on
    two different days without it being the regression this guards
    against (site falling back to day 1's exact word list on later days).
    """
    for level in ("L0", "L1", "L2", "L3"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            day_lists = []
            for day_index in range(7):
                day_words = curriculum.get_vocabulary_for_day(week, day_index, level)
                assert day_words, f"{level} week {week} day {day_index} has no words"
                day_lists.append(tuple(w["word"] for w in day_words))
            for i in range(len(day_lists)):
                for j in range(i + 1, len(day_lists)):
                    assert day_lists[i] != day_lists[j], (
                        f"{level} week {week}: day {i} and day {j} have the "
                        f"exact same word list — days are not being split distinctly"
                    )


def test_get_vocabulary_for_day_wraps_day_index():
    """day_index % 7 means day 7 (index 7) must equal day 0 (index 0)."""
    words_day0 = curriculum.get_vocabulary_for_day(1, 0, "L0")
    words_day7 = curriculum.get_vocabulary_for_day(1, 7, "L0")
    assert words_day0 == words_day7


def test_get_vocabulary_for_day_empty_week_returns_empty():
    assert curriculum.get_vocabulary_for_day(999, 0, "L0") == []


# ============================================================
#  QUIZ WORDS (spaced repetition)
# ============================================================

def test_get_quiz_words_respects_count():
    words = curriculum.get_quiz_words(5, count=10, level="L0")
    assert len(words) <= 10


def test_get_quiz_words_pulls_from_current_and_previous_two_weeks():
    """Week 1 should only draw from week 1 (no earlier weeks exist)."""
    week1_only = set(w["word"] for w in curriculum.get_vocabulary_for_week(1, "L0"))
    quiz_words = curriculum.get_quiz_words(1, count=100, level="L0")
    for w in quiz_words:
        assert w["word"] in week1_only


def test_get_quiz_words_empty_for_unknown_level():
    assert curriculum.get_quiz_words(1, count=10, level="L99") == []


# ============================================================
#  SPEAKING MISSIONS / WRITING PROMPTS
# ============================================================

def test_every_week_has_all_seven_speaking_missions():
    day_names = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for level in ("L0", "L1", "L2", "L3"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            for day in day_names:
                mission = curriculum.get_speaking_mission(week, day, level)
                assert mission, f"{level} week {week} missing speaking mission for {day}"
                assert mission.get("prompt")


def test_get_speaking_mission_unknown_day_returns_none():
    assert curriculum.get_speaking_mission(1, "Blursday", "L0") is None


def test_every_week_has_seven_writing_prompts():
    for level in ("L0", "L1", "L2", "L3"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            for day_index in range(7):
                prompt = curriculum.get_writing_prompt(week, day_index, level)
                assert prompt, f"{level} week {week} missing writing prompt for day {day_index}"


def test_get_writing_prompt_out_of_range_returns_none():
    assert curriculum.get_writing_prompt(1, 999, "L0") is None


# ============================================================
#  ACCENT DRILLS
# ============================================================

def test_get_accent_drill_returns_none_for_unknown_level():
    assert curriculum.get_accent_drill(1, 0, "L99") is None


def test_get_accent_drill_clamps_week_to_valid_range():
    """Week 999 on L0 (8 weeks) should clamp to week 8, not silently
    return None or raise — callers rely on always getting *some* content
    for a level that has content authored, even for an out-of-range week."""
    clamped = curriculum.get_accent_drill(999, 0, "L0")
    week8 = curriculum.get_accent_drill(8, 0, "L0")
    assert clamped == week8


def test_get_accent_focus_l0_falls_back_to_phoneme_weeks_if_missing():
    """L0 has a legacy hardcoded fallback (config.PHONEME_WEEKS) — verify
    the real JSON content takes priority, and that the function never
    returns None for L0 (content exists for all 8 weeks)."""
    for week in range(1, 9):
        assert curriculum.get_accent_focus(week, "L0") is not None


def test_get_accent_focus_unknown_level_returns_none_not_fabricated():
    """Only L0 has the legacy PHONEME_WEEKS fallback. A level with no
    accent content authored must return None, never a fabricated guess."""
    assert curriculum.get_accent_focus(1, "L99") is None


# ============================================================
#  GRAMMAR PATTERNS
# ============================================================

def test_get_grammar_pattern_returns_none_for_unknown_level():
    assert curriculum.get_grammar_pattern(1, "L99") is None


def test_every_week_has_a_grammar_pattern():
    for level in ("L0", "L1", "L2", "L3"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            pattern = curriculum.get_grammar_pattern(week, level)
            assert pattern, f"{level} week {week} missing grammar pattern"


# ============================================================
#  DAILY CONTENT BUNDLE
# ============================================================

def test_get_daily_content_returns_all_task_keys():
    daily = curriculum.get_daily_content(1, "Saturday", 0, "L0")
    expected_keys = {
        "week", "day_name", "day_index", "level", "vocabulary",
        "speaking_mission", "writing_prompt", "accent_drill",
        "accent_focus", "grammar_pattern", "theme",
    }
    assert expected_keys.issubset(daily.keys())


def test_get_daily_content_threads_level_through_correctly():
    """Regression guard: get_daily_content() previously silently defaulted
    every level to L0 content internally. Confirm L1's daily content is
    genuinely different from L0's, not a hidden L0 fallback."""
    l0_daily = curriculum.get_daily_content(1, "Saturday", 0, "L0")
    l1_daily = curriculum.get_daily_content(1, "Saturday", 0, "L1")
    assert l0_daily["theme"] != l1_daily["theme"]
    assert l0_daily["vocabulary"] != l1_daily["vocabulary"]


def test_get_daily_content_clamps_vocab_speaking_writing_past_max_week():
    """Found via boundary-condition stress testing: get_accent_drill()/
    get_accent_focus()/get_grammar_pattern() already clamped week
    internally, but get_vocabulary_for_day()/get_speaking_mission()/
    get_writing_prompt() did not -- so a member still within their
    level's own declared duration_weeks range (config.LEVELS' L0 says
    (8, 12), but curated content only covers 8 weeks) got real repeated
    week-8 accent/grammar content but generic non-curated filler for
    vocab/speaking/writing instead of week 8 repeating like everything
    else. Confirm week 15 for L0 (max week 8) now returns identical
    task content to week 8 itself, for every task type."""
    week_8 = curriculum.get_daily_content(8, "Saturday", 0, "L0")
    week_15 = curriculum.get_daily_content(15, "Saturday", 0, "L0")
    assert week_15["vocabulary"] == week_8["vocabulary"]
    assert week_15["vocabulary"] != []
    assert week_15["speaking_mission"] == week_8["speaking_mission"]
    assert week_15["speaking_mission"] is not None
    assert week_15["writing_prompt"] == week_8["writing_prompt"]
    assert week_15["writing_prompt"] is not None
    # The returned "week" key itself is clamped too (it's what theme/
    # grammar-name lookups key off of internally) -- callers that want to
    # display the member's REAL week number (e.g. bot.py's daily task
    # post header) already use their own separate, unclamped
    # member_week_number() value for that, not this dict's "week" key.
    assert week_15["week"] == 8


# ============================================================
#  PRACTICE PLATFORM URL BUILDERS
# ============================================================

def test_practice_platform_day_url_shape():
    url = curriculum.practice_platform_day_url(3, 0, "L1")
    assert url == f"{config.PRACTICE_PLATFORM_URL}/l1/week3/day1/"


def test_practice_platform_day_url_day_index_to_day_number():
    """day_index is 0=Saturday..6=Friday; the URL uses day1=Saturday..day7=Friday."""
    url_day0 = curriculum.practice_platform_day_url(1, 0, "L0")
    url_day6 = curriculum.practice_platform_day_url(1, 6, "L0")
    assert "/day1/" in url_day0
    assert "/day7/" in url_day6


def test_practice_platform_day_url_clamps_week():
    url = curriculum.practice_platform_day_url(999, 0, "L0")
    assert "/week8/" in url  # L0 max week is 8


def test_practice_platform_task_url_known_tasks():
    for task_id, expected_slug in (
        ("accent", "accent"), ("vocab", "vocab"),
        ("shadow", "shadowing"), ("listening", "listening"),
    ):
        url = curriculum.practice_platform_task_url(task_id, 1, 0, "L0")
        assert url is not None
        assert url.endswith(f"/{expected_slug}")


def test_practice_platform_task_url_unmapped_tasks_return_none():
    """speaking/writing/community have no matching practice-site page —
    must return None, never a fabricated/guessed link."""
    for task_id in ("speaking", "writing", "community"):
        assert curriculum.practice_platform_task_url(task_id, 1, 0, "L0") is None


def test_practice_platform_task_url_is_extensionless():
    """Verified live: the .html-suffixed path 404s on the custom domain;
    the extensionless form works everywhere. Must never regress to
    appending .html."""
    url = curriculum.practice_platform_task_url("vocab", 1, 0, "L0")
    assert not url.endswith(".html")


# ============================================================
#  THEME / MISC
# ============================================================

def test_get_theme_falls_back_to_vocab_themes_for_missing_week():
    """get_theme() falls back to config.VOCAB_THEMES only when the week
    key isn't in _weekly_data at all (e.g. week 999); every real week
    should return its own JSON-sourced theme, not the L0-only fallback
    table, for L1/L2/L3 as well as L0."""
    for level in ("L1", "L2", "L3"):
        theme = curriculum.get_theme(1, level)
        assert theme and theme != "General"


def test_is_loaded_true_after_load_all():
    assert curriculum.is_loaded() is True
