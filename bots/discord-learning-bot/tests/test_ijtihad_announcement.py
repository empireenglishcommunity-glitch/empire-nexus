"""Ijtihad — the launch announcement copy.

This is the one artefact in the whole rework that every student reads, and it is
the only chance to frame a reset as an addition rather than a loss. So its
structure is tested, not just eyeballed:

  * "your history is safe" must come BEFORE "the race restarts" — the reverse
    order reads as a threat to the students with most to lose from a reset;
  * it must respect the Sahin bidi rule (no Arabic line carrying 2+ embedded LTR
    tokens), because that genuinely disorients Arabic readers;
  * it must be bilingual throughout, since some students are beginners.
"""
import re

from src import bot as bot_mod


def _text(season=None):
    return bot_mod.build_ijtihad_announcement(season)


def test_history_is_reassured_before_the_reset_is_mentioned():
    """THE ORDERING RULE. Loss-framing first would make veterans read the whole
    message as a threat."""
    t = _text()
    permanent = t.find("permanent")
    seasons = t.find("4-week seasons")
    assert permanent != -1 and seasons != -1
    assert permanent < seasons, "reassurance must precede the reset"


def test_says_the_record_never_resets():
    t = _text()
    assert "never resets" in t
    assert "مايتصفّرش" in t


def test_states_the_core_promise():
    t = _text()
    assert "works hardest **right now** leads" in t
    assert "not whoever joined first" in t


def test_is_bilingual():
    t = _text()
    assert re.search(r"[\u0600-\u06FF]", t), "must contain Arabic"
    assert re.search(r"[A-Za-z]", t), "must contain English"


def test_mentions_the_three_student_facing_changes():
    t = _text()
    assert "daily target" in t
    assert "freezes" in t
    assert "measured against you" in t


def test_commands_are_present_for_the_student_to_act_on():
    t = _text()
    for cmd in ("!sijil", "!target", "!season", "!growth"):
        assert cmd in t


def test_includes_the_season_window_when_a_season_exists():
    t = _text({"label": "Season 1", "started_on": "2026-08-30",
               "ends_on": "2026-09-26"})
    assert "2026-08-30" in t and "2026-09-26" in t


def test_omits_the_window_when_there_is_no_season():
    assert "→" not in _text().split("Work is what counts")[0].split("seasons")[-1][:40]


def test_no_arabic_line_carries_two_embedded_latin_tokens():
    """Sahin bidi rule: 2+ LTR islands inside an RTL line force the eye to jump
    between directions in an order that doesn't match the typed order."""
    arabic = re.compile(r"[\u0600-\u06FF]")
    # An "LTR island" here is a backticked command or a bold Latin phrase.
    island = re.compile(r"`[^`]+`|\*\*[A-Za-z][^*]*\*\*")
    offenders = []
    for line in _text().splitlines():
        if not arabic.search(line):
            continue
        if len(island.findall(line)) >= 2:
            offenders.append(line)
    assert not offenders, f"bidi rule violated on: {offenders}"


def test_commands_sit_on_their_own_lines():
    """A command line must not also carry Arabic prose, for the same bidi
    reason."""
    arabic = re.compile(r"[\u0600-\u06FF]")
    for line in _text().splitlines():
        stripped = line.strip()
        if stripped.startswith("`") and stripped.endswith("`"):
            assert not arabic.search(stripped), stripped
