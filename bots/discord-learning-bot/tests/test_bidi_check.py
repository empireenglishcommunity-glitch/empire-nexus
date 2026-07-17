"""Tests for scripts/bidi_check.py.

Sahin standing rule: any Arabic line with 2+ embedded LTR
(channel/command) tokens produces disorienting mixed-direction
reading order -- found live in channel_guides.py, this test suite
locks in the detection logic so a future regression is caught
automatically rather than requiring a human to notice it again.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from bidi_check import find_bidi_issues, find_bidi_issues_in_dict  # noqa: E402


def test_flags_two_backtick_tokens_joined_by_arabic():
    line = "❌ لا تكتب نصًا أو أسئلة هنا — مكانها `#ask-nour` أو `#support`"
    issues = find_bidi_issues(line)
    assert len(issues) == 1


def test_flags_three_tokens_joined_by_arabic_word():
    line = "اقرأ الترتيب: `#welcome` ثم `#rules` ثم `#roles-info`"
    issues = find_bidi_issues(line)
    assert len(issues) == 1


def test_does_not_flag_single_embedded_token():
    line = "✅ اكتب `!join` هناك لتبدأ رسميًا"
    assert find_bidi_issues(line) == []


def test_does_not_flag_pure_arabic_line():
    line = "هذا أول مكان تراه عند دخولك السيرفر — بوابتك إلى المجتمع كله."
    assert find_bidi_issues(line) == []


def test_does_not_flag_pure_ltr_line_with_no_arabic():
    """A line with multiple LTR tokens but ZERO Arabic characters is
    not a bidi issue by definition -- there's no direction to
    alternate with. This is the actual fix pattern used in
    channel_guides.py: move a multi-token list onto its own
    Arabic-free line."""
    line = "`#welcome` ← `#rules` ← `#roles-info`"
    assert find_bidi_issues(line) == []


def test_does_not_flag_a_single_digit_embedded_in_arabic():
    """A bare level number like the '3' in 'المستوى 3' should not
    count as a disorienting LTR island -- this is normal, expected
    text, not the pattern this check exists to catch."""
    line = "أسئلتك عن محتوى المستوى 3 — القواعد، المفردات."
    assert find_bidi_issues(line) == []


def test_multiline_text_flags_only_the_bad_line():
    text = (
        "✅ سطر عادي بدون مشكلة\n"
        "❌ سطر فيه مشكلة `#a` و `#b`\n"
        "✅ سطر تاني عادي"
    )
    issues = find_bidi_issues(text)
    assert len(issues) == 1
    assert "#a" in issues[0] and "#b" in issues[0]


def test_find_bidi_issues_in_dict_only_returns_entries_with_issues():
    content_map = {
        "clean": "✅ اكتب `!join` هناك",
        "bad": "❌ اذهب إلى `#a` أو `#b`",
    }
    results = find_bidi_issues_in_dict(content_map)
    assert "clean" not in results
    assert "bad" in results


def test_real_channel_guides_have_zero_bidi_issues():
    """Regression test: the real, live CHANNEL_GUIDES content must
    have zero bidi issues. This is the actual guardrail -- if a
    future edit reintroduces a 2+-token Arabic line, this test fails
    instead of silently shipping the same problem again."""
    from channel_guides import CHANNEL_GUIDES

    results = find_bidi_issues_in_dict(CHANNEL_GUIDES)
    assert results == {}, f"bidi issues found: {results}"
