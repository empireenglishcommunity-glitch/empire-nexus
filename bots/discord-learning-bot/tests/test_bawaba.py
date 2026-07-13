"""Bawaba Phase B0 — Arabic command aliases + number-based task commands.

Tests the rewriting logic that translates Arabic commands to English
equivalents before bot.process_commands() sees them.
"""
import pytest

from src.bot import _rewrite_arabic_command, ARABIC_COMMAND_ALIASES, ARABIC_TASK_ALIASES
from src import config


# ============================================================
#  ARABIC COMMAND ALIAS REWRITING
# ============================================================

def test_rewrite_arabic_join():
    result = _rewrite_arabic_command("!انضم هدفي أتكلم إنجليزي", "!")
    assert result == "!join هدفي أتكلم إنجليزي"


def test_rewrite_arabic_done_with_arabic_task():
    result = _rewrite_arabic_command("!تم نطق", "!")
    assert result == "!done accent"


def test_rewrite_arabic_done_with_number():
    result = _rewrite_arabic_command("!تم 3", "!")
    assert result == "!done 3"


def test_rewrite_arabic_done_no_arg():
    result = _rewrite_arabic_command("!تم", "!")
    assert result == "!done"


def test_rewrite_arabic_done_alternative_alias():
    """!خلص is an alternative alias for !done"""
    result = _rewrite_arabic_command("!خلص مفردات", "!")
    assert result == "!done vocab"


def test_rewrite_arabic_progress():
    result = _rewrite_arabic_command("!تقدم", "!")
    assert result == "!progress"


def test_rewrite_arabic_help():
    result = _rewrite_arabic_command("!مساعدة", "!")
    assert result == "!helpar"


def test_rewrite_arabic_streak():
    result = _rewrite_arabic_command("!سلسلة", "!")
    assert result == "!streak"


def test_rewrite_arabic_assess():
    result = _rewrite_arabic_command("!تقييم", "!")
    assert result == "!assess"


def test_rewrite_arabic_level():
    result = _rewrite_arabic_command("!مستوى", "!")
    assert result == "!level"


def test_rewrite_arabic_week():
    result = _rewrite_arabic_command("!أسبوع", "!")
    assert result == "!week"


def test_rewrite_english_command_returns_none():
    """English commands should NOT be rewritten."""
    result = _rewrite_arabic_command("!done accent", "!")
    assert result is None


def test_rewrite_non_command_returns_none():
    """Messages not starting with prefix should not be rewritten."""
    result = _rewrite_arabic_command("hello world", "!")
    assert result is None


def test_rewrite_empty_after_prefix_returns_none():
    result = _rewrite_arabic_command("!", "!")
    assert result is None


def test_rewrite_unknown_arabic_word_returns_none():
    """An Arabic word not in the alias table should NOT be rewritten."""
    result = _rewrite_arabic_command("!مرحبا", "!")
    assert result is None


def test_rewrite_respects_custom_prefix():
    """Ghost bot uses ? prefix — rewriting should work with any prefix."""
    result = _rewrite_arabic_command("?تم نطق", "?")
    assert result == "?done accent"


# ============================================================
#  ARABIC TASK ALIASES (completeness check)
# ============================================================

def test_all_seven_tasks_have_arabic_aliases():
    """Every task in DAILY_TASKS must have an Arabic alias."""
    task_ids_with_aliases = set(ARABIC_TASK_ALIASES.values())
    for task in config.DAILY_TASKS:
        assert task["id"] in task_ids_with_aliases, (
            f"Task '{task['id']}' has no Arabic alias in ARABIC_TASK_ALIASES"
        )


def test_arabic_task_aliases_map_to_valid_task_ids():
    """Every Arabic task alias must map to a real task id."""
    valid_ids = {t["id"] for t in config.DAILY_TASKS}
    for arabic, english in ARABIC_TASK_ALIASES.items():
        assert english in valid_ids, (
            f"Arabic alias '{arabic}' maps to '{english}' which is not a valid task id"
        )


# ============================================================
#  NUMBER-BASED TASK COMMANDS
# ============================================================

def test_number_commands_map_to_correct_tasks():
    """!1 through !7 should map to tasks in DAILY_TASKS order."""
    expected = [t["id"] for t in config.DAILY_TASKS]
    assert expected == ["accent", "vocab", "shadow", "speaking",
                        "listening", "writing", "community"]
    # The mapping happens in on_message (tested via integration), but
    # we verify the assumption this relies on: DAILY_TASKS order is fixed
    assert len(config.DAILY_TASKS) == 7
