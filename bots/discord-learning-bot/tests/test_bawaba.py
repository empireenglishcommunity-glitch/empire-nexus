"""Bawaba — Arabic command aliases, number-based task commands, and
gradual English injection tests.
"""
from src.bot import _rewrite_arabic_command, ARABIC_TASK_ALIASES
from src import config, database


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



# ============================================================
#  BAWABA B5: GRADUAL ENGLISH INJECTION
# ============================================================

def test_response_language_returns_bilingual_when_flag_off():
    """When bawaba_gradual_english flag is not set, always returns bilingual."""
    from src.features import response_language
    database.register_member("lang_test_user", "Test")
    # Flag not set = disabled = bilingual
    result = response_language("lang_test_user")
    assert result == "bilingual"


def test_response_language_arabic_for_week_1():
    """Week 1 member gets 'arabic' phase."""
    from src.features import response_language
    database.register_member("lang_w1", "Week1")
    database.set_feature_flag("bawaba_gradual_english", enabled=True)
    # Member just joined = week 1
    result = response_language("lang_w1")
    assert result == "arabic"


def test_response_language_bilingual_ar_for_week_2():
    """Week 2-3 member gets 'bilingual_ar' phase."""
    from src.features import response_language
    from unittest.mock import patch
    database.register_member("lang_w2", "Week2")
    database.set_feature_flag("bawaba_gradual_english", enabled=True)
    with patch.object(database, "member_week_number", return_value=2):
        result = response_language("lang_w2")
    assert result == "bilingual_ar"


def test_response_language_bilingual_for_week_4_plus():
    """Week 4+ member gets 'bilingual' phase (current behavior)."""
    from src.features import response_language
    from unittest.mock import patch
    database.register_member("lang_w4", "Week4")
    database.set_feature_flag("bawaba_gradual_english", enabled=True)
    with patch.object(database, "member_week_number", return_value=5):
        result = response_language("lang_w4")
    assert result == "bilingual"


def test_bl_for_member_arabic_phase():
    """bl_for_member in 'arabic' phase shows only Arabic."""
    from src.features import bl_for_member
    database.register_member("bl_test_ar", "ArabicUser")
    database.set_feature_flag("bawaba_gradual_english", enabled=True)
    # Week 1 = arabic phase
    result = bl_for_member("bl_test_ar", "Done", "تم")
    assert result == "تم"
    assert "Done" not in result


def test_bl_for_member_bilingual_ar_phase():
    """bl_for_member in 'bilingual_ar' phase shows Arabic first with English in parens."""
    from src.features import bl_for_member
    from unittest.mock import patch
    database.register_member("bl_test_biar", "BiArUser")
    database.set_feature_flag("bawaba_gradual_english", enabled=True)
    with patch.object(database, "member_week_number", return_value=3):
        result = bl_for_member("bl_test_biar", "Done", "تم")
    assert result == "تم (Done)"


def test_bl_for_member_bilingual_phase():
    """bl_for_member in 'bilingual' phase shows English / Arabic."""
    from src.features import bl_for_member
    from unittest.mock import patch
    database.register_member("bl_test_bi", "BiUser")
    database.set_feature_flag("bawaba_gradual_english", enabled=True)
    with patch.object(database, "member_week_number", return_value=6):
        result = bl_for_member("bl_test_bi", "Done", "تم")
    assert result == "Done / تم"
