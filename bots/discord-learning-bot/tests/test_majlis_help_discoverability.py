"""Majlis must be DISCOVERABLE, not just enabled.

Written after a real, week-long product failure found on 2026-08-29:

Majlis went live for everyone on 2026-08-22. `!ping-me` and `!knock` were
documented **nowhere** — not in `!help`, not in `scripts/channel_guides.py`. So no
student could find the opt-in command, the `community-pings` role had **zero
members**, and every presence beacon plus **six consecutive Community Hour
rallies** @-mentioned an empty role. Every mechanical part worked. It reached
nobody.

`.kiro/steering/project-rules.md` §6 already said the `!help` entry must land in
the same commit that flips a flag on. Nothing enforced it. These tests do, for
Majlis specifically: if the opt-in flag is on, the command that uses it must appear
in `!help`.
"""
import importlib
import types

import pytest

from src import database


@pytest.fixture()
def bot_mod():
    """bot.py builds its help text in module-level functions, so importing is
    enough — no gateway connection involved."""
    return importlib.import_module("src.bot")


def _ctx(author_id="12345"):
    return types.SimpleNamespace(author=types.SimpleNamespace(id=author_id))


def _on(*flags):
    for f in flags:
        database.set_feature_flag(f, True, "", "test")


def _off(*flags):
    for f in flags:
        database.set_feature_flag(f, False, "", "test")


# ============================================================
#  The opt-in command must be advertised when its flag is on
# ============================================================

def test_ping_me_is_advertised_when_pings_flag_is_on(bot_mod):
    """The exact failure: flag on, command invisible, role empty."""
    _on("community_pings_optin")
    out = bot_mod._majlis_help_section(_ctx())
    assert "!ping-me" in out, "students cannot opt in to a command they never see"


def test_knock_is_advertised_when_pings_flag_is_on(bot_mod):
    _on("community_pings_optin")
    assert "!knock" in bot_mod._majlis_help_section(_ctx())


def test_arabic_aliases_are_advertised(bot_mod):
    """This is an Arabic-first community; the aliases are the primary form for
    many students."""
    _on("community_pings_optin")
    out = bot_mod._majlis_help_section(_ctx())
    assert "إشعارات-المجلس" in out
    assert "طق" in out


def test_majlis_help_is_bidi_clean(bot_mod):
    """Sahin standing rule (steering §6): never ship an Arabic line carrying 2+
    embedded LTR islands — Discord's bidi layout makes it genuinely disorienting.

    This caught a real mistake while the section was being written: putting each
    Arabic alias inline next to its English command (``!ping-me` … (`!إشعارات-المجلس`)``)
    puts two `!` islands on one Arabic line. The aliases now sit on their own
    lines. Locked in here so the section cannot regress, mirroring
    test_bidi_check's guard over channel_guides.py.
    """
    import importlib.util
    import pathlib
    spec = importlib.util.spec_from_file_location(
        "bidi_check",
        pathlib.Path(__file__).resolve().parent.parent / "scripts" / "bidi_check.py")
    bidi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bidi)

    _on("community_pings_optin", "community_power_hour")
    issues = bidi.find_bidi_issues(bot_mod._majlis_help_section(_ctx()))
    assert issues == [], f"bidi issues in the Majlis help section: {issues}"


def test_community_hour_is_advertised_with_its_real_schedule(bot_mod):
    """A rally nobody knows about is a rally nobody attends. The time must come
    from config, not a hardcoded string that can drift."""
    _on("community_power_hour")
    out = bot_mod._majlis_help_section(_ctx())
    assert "Community Hour" in out
    assert "21:00" in out
    assert "Africa/Cairo" in out


def test_hour_section_follows_config_not_a_literal(bot_mod):
    _on("community_power_hour")
    database.set_community_config("community_hour_start", "20:30")
    assert "20:30" in bot_mod._majlis_help_section(_ctx())


# ============================================================
#  ...and must stay quiet when the flags are off
# ============================================================

def test_nothing_is_advertised_when_all_majlis_flags_are_off(bot_mod):
    """Steering §6: never advertise a dormant command — it reads as broken to a
    curious student."""
    _off("community_pings_optin", "community_power_hour")
    assert bot_mod._majlis_help_section(_ctx()) == ""


def test_pings_off_but_hour_on_shows_only_the_hour(bot_mod):
    _off("community_pings_optin")
    _on("community_power_hour")
    out = bot_mod._majlis_help_section(_ctx())
    assert "Community Hour" in out
    assert "!ping-me" not in out


def test_section_respects_a_pilot_allowlist(bot_mod):
    """A flag in pilot must only advertise to the students in the pilot."""
    database.set_feature_flag("community_pings_optin", True, "999", "test")
    assert "!ping-me" in bot_mod._majlis_help_section(_ctx("999"))
    assert "!ping-me" not in bot_mod._majlis_help_section(_ctx("111"))


# ============================================================
#  Task #7's description must match the rule actually in force
# ============================================================

def test_task7_text_mentions_the_together_path_when_enabled(bot_mod):
    """Majlis Phase 1 added a cheaper route to task #7 (5 min together) beside
    the original 10-min any-voice path. `!help` described only the old one, so
    the easier route was invisible."""
    _on("community_together_credit")
    out = bot_mod._voice_requirement_text(_ctx())
    assert "voice-lounge" in out
    assert "10 min" in out, "the original path must still be offered"


def test_task7_together_threshold_comes_from_config(bot_mod):
    _on("community_together_credit")
    database.set_community_config("community_together_minutes", 7)
    assert "7 min" in bot_mod._voice_requirement_text(_ctx())


def test_task7_text_falls_back_when_together_credit_is_off(bot_mod):
    _off("community_together_credit")
    out = bot_mod._voice_requirement_text(_ctx())
    assert out == "10 min in voice"
    assert "voice-lounge" not in out


# ============================================================
#  Help must never blow up
# ============================================================

def test_helpers_never_raise_on_a_broken_context(bot_mod):
    """`!help` is the command a confused student reaches for. It must degrade,
    never error."""
    broken = types.SimpleNamespace(author=None)
    assert bot_mod._majlis_help_section(broken) == ""
    assert bot_mod._voice_requirement_text(broken) == "10 min in voice"
