"""Mi'yar — CEFR channel-routing regression guard.

The live Discord server was migrated to six CEFR zones (a1-*, …, c2-*) and the
legacy L0–L3 categories were archived. Several modules, however, still built
channel names with the old `f"l{level[1]}-showcase"` pattern, which for a CEFR
level like "A1" yields **"l1-showcase"** — an *archived* channel. That silently
pointed daily-task instructions, writing verification and recording posts at
dead channels for every migrated student.

These tests lock the correct behaviour: channel names must be derived from
`config.level_slug()` so "A1" -> "a1-showcase", and the broken `l{digit}`
pattern must not come back.
"""
import re
from pathlib import Path

import pytest

from src import config

SRC = Path(__file__).resolve().parent.parent / "src"

# The exact bug: "l" + the SECOND CHARACTER of the level key + "-channel".
# For "A1"/"B2"/"C1" that character is a digit, so it built l1-/l2-/l1-…
_BROKEN_PATTERN = re.compile(r'l\{level\[1\]')


def test_level_slug_maps_cefr_levels_to_their_own_slug():
    """A1 -> a1 (NOT l1). This is the crux of the bug."""
    assert config.level_slug("A1") == "a1"
    assert config.level_slug("A2") == "a2"
    assert config.level_slug("B1") == "b1"
    assert config.level_slug("B2") == "b2"
    assert config.level_slug("C1") == "c1"
    assert config.level_slug("C2") == "c2"


def test_level_slug_still_supports_legacy_keys():
    for legacy in ("L0", "L1", "L2", "L3"):
        assert config.level_slug(legacy) == legacy.lower()


@pytest.mark.parametrize("level", config.CEFR_ORDER)
def test_showcase_and_text_practice_names_are_cefr(level):
    """The channel names the bot resolves must live in the CEFR zones."""
    slug = config.level_slug(level)
    assert f"{slug}-showcase".startswith(level.lower())
    assert f"{slug}-text-practice".startswith(level.lower())
    # and must NOT collide with a legacy/archived channel name
    assert not f"{slug}-showcase".startswith("l")


@pytest.mark.parametrize("module", [
    "tasks.py", "verification.py", "api_server.py", "features.py",
])
def test_no_broken_legacy_channel_pattern_in_source(module):
    """Guard: the `l{level[1]}-…` pattern must never reappear."""
    text = (SRC / module).read_text(encoding="utf-8")
    found = _BROKEN_PATTERN.findall(text)
    assert not found, (
        f"{module} builds a channel name with the broken legacy pattern "
        f"l{{level[1]}} — use config.level_slug(level) instead "
        f"(for 'A1' the broken form yields the ARCHIVED 'l1-…' channel)."
    )


def test_no_hardcoded_legacy_daily_tasks_channel_in_user_facing_source():
    """Onboarding/help copy must not send students to the archived
    #l0-daily-tasks channel."""
    offenders = []
    for path in SRC.glob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            # skip comments / docstring-ish lines
            if stripped.startswith("#") or stripped.startswith("--"):
                continue
            if "l0-daily-tasks" in line or "l0-showcase" in line or "l0-text-practice" in line:
                offenders.append(f"{path.name}:{i}")
    assert not offenders, (
        "hardcoded legacy channel names found (should be the CEFR a1-* "
        f"channels): {offenders}"
    )


def test_new_members_default_to_first_cefr_level():
    """A brand-new student must be created on A1, not legacy L0."""
    import inspect

    from src import database
    sig = inspect.signature(database.register_member)
    assert sig.parameters["level"].default == "A1"
