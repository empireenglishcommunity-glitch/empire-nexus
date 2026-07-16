"""Tests for narrative_engine.py's AI-output quality guards.

Covers D033's _has_unexpected_script() and D035's follow-up
_has_blocked_foreign_word() -- together these catch AI hallucination
glitches (a stray foreign-language fragment mid-sentence) before they
ever reach a student.
"""
from src import narrative_engine


# ============================================================
#  _has_unexpected_script() (D033)
# ============================================================

def test_has_unexpected_script_detects_the_original_d033_repro():
    text = "انت جاهز، đặc biệt tốt hôm nay!"
    assert narrative_engine._has_unexpected_script(text) is True


def test_has_unexpected_script_false_for_pure_arabic():
    text = "مبروك يا نجم! إنجاز اكتمل — ده تقدم حقيقي، يلا نكمل كده!"
    assert narrative_engine._has_unexpected_script(text) is False


def test_has_unexpected_script_false_for_arabic_plus_english():
    text = "Great job! يلا نكمل مع بعض, KEEP GOING!"
    assert narrative_engine._has_unexpected_script(text) is False


def test_has_unexpected_script_detects_cjk():
    text = "مبروك 你好 يا نجم"
    assert narrative_engine._has_unexpected_script(text) is True


def test_has_unexpected_script_detects_cyrillic():
    text = "мброок يا نجم"
    assert narrative_engine._has_unexpected_script(text) is True


# ============================================================
#  _has_blocked_foreign_word() (D035, follow-up to D033)
# ============================================================

def test_has_blocked_foreign_word_detects_the_real_m4_repro():
    """The exact real hallucination caught live during Masar M4's
    testing -- 'cùng' (Vietnamese for 'together') uses only a shared
    Latin-1 diacritic, so D033's script-range guard alone missed it."""
    text = "يلا GhostTestSynthetic نكمل cùng بعض، هنتعلم أكتر وأكتر!"
    assert narrative_engine._has_blocked_foreign_word(text) is True


def test_has_blocked_foreign_word_false_for_legitimate_french_loanwords():
    """Must NOT false-positive on legitimate accented Latin-1 text --
    this is the exact tradeoff D035's entry documents: a narrow
    blocklist widening (e.g. blocking all of Latin-1 Supplement) would
    break real French/Portuguese loanwords and names."""
    text = "Bonjour, je m'appelle José, j'aime le café"
    assert narrative_engine._has_blocked_foreign_word(text) is False


def test_has_blocked_foreign_word_false_for_pure_arabic():
    text = "مبروك يا نجم! إنجاز اكتمل — ده تقدم حقيقي، يلا نكمل كده!"
    assert narrative_engine._has_blocked_foreign_word(text) is False


def test_has_blocked_foreign_word_false_for_arabic_plus_english():
    text = "Great job! يلا نكمل مع بعض, KEEP GOING!"
    assert narrative_engine._has_blocked_foreign_word(text) is False


def test_has_blocked_foreign_word_is_whole_word_not_substring():
    """Must match whole words only -- must not flag a blocked word
    merely appearing as a substring inside a longer legitimate word."""
    text = "This is a discussion about cocoa production"  # contains "co" but not "của" etc as a word
    assert narrative_engine._has_blocked_foreign_word(text) is False


def test_has_blocked_foreign_word_case_insensitive():
    text = "Something Được happened here"
    assert narrative_engine._has_blocked_foreign_word(text) is True


def test_has_blocked_foreign_word_detects_original_d033_word_too():
    """đặc is also in the curated list -- defense in depth alongside
    the script-range guard, which already catches it via its
    Vietnamese-specific diacritic characters."""
    text = "انت جاهز، đặc biệt تمام النهاردة!"
    assert narrative_engine._has_blocked_foreign_word(text) is True
