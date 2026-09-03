"""Mi'yar System Harmonization — Step 4: Discord server structure tests.

Locks the CEFR role/zone definitions in setup_server.py so a server (re)build
creates exactly the six CEFR levels, in lockstep with config.level_role_name()
(which the bot uses to assign/strip roles). A mismatch here would orphan roles
or break level isolation on the live server.
"""
import sys
from pathlib import Path

import pytest

# setup_server.py lives in scripts/ and imports its sibling channel_guides.
_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from src import config
import setup_server as ss


def _role_names():
    return [r["name"] for r in ss.ROLES_CONFIG]


def _cat_names():
    return [c["name"] for c in ss.CATEGORIES_CONFIG]


# ============================================================
#  ROLES
# ============================================================

def test_six_cefr_level_roles_present_and_match_config():
    names = _role_names()
    for lvl in config.CEFR_ORDER:
        assert config.level_role_name(lvl) in names, f"missing role for {lvl}"


def test_no_legacy_level_roles_remain():
    names = " | ".join(_role_names())
    for legacy in config.LEGACY_ROLE_NAMES.values():
        assert legacy not in names, f"legacy role still in setup: {legacy}"


def test_no_legacy_level_role_refs_in_any_overwrite():
    """No category/channel overwrite should still key on a legacy L0–L3 role."""
    legacy = set(config.LEGACY_ROLE_NAMES.values())
    for cat in ss.CATEGORIES_CONFIG:
        for k in cat["overwrites"]:
            assert k not in legacy, f"legacy overwrite in {cat['name']}: {k}"
        for ch in cat["channels"]:
            for k in (ch.get("override") or {}):
                assert k not in legacy, f"legacy override in #{ch['name']}: {k}"


# ============================================================
#  ZONES
# ============================================================

def test_six_cefr_zones_present():
    cats = _cat_names()
    zones = [c for c in cats if "ZONE" in c]
    assert len(zones) == 6, f"expected 6 CEFR zones, got {zones}"
    for lvl in config.CEFR_ORDER:
        assert any(c.startswith(f"{config.CEFR_LEVELS[lvl]['emoji']} {lvl} ZONE") for c in cats), \
            f"missing zone for {lvl}"


def test_zone_channels_are_slug_prefixed():
    a1 = next(c for c in ss.CATEGORIES_CONFIG if c["name"].startswith("🌱 A1 ZONE"))
    names = [ch["name"] for ch in a1["channels"]]
    assert names == ["a1-daily-tasks", "a1-text-practice", "a1-voice-1",
                     "a1-voice-2", "a1-questions", "a1-showcase"]


@pytest.mark.parametrize("lvl", config.CEFR_ORDER)
def test_zone_isolation(lvl):
    """Each zone: its own level role can view; every OTHER level role denied."""
    zone = next(c for c in ss.CATEGORIES_CONFIG
                if c["name"].startswith(f"{config.CEFR_LEVELS[lvl]['emoji']} {lvl} ZONE"))
    ow = zone["overwrites"]
    own = config.level_role_name(lvl)
    # own role: view allowed
    allow, _ = ow[own].pair()
    assert allow.view_channel is True, f"{lvl} own role not allowed to view its zone"
    # other level roles: view denied
    for other in config.CEFR_ORDER:
        if other == lvl:
            continue
        _, deny = ow[config.level_role_name(other)].pair()
        assert deny.view_channel is True, f"{lvl} zone does not deny {other}"


def test_daily_tasks_channels_match_bot_routing():
    """The a1-daily-tasks … channel names must equal what the bot posts to
    (config.level_slug), or migrated students get no daily-task post."""
    for lvl in config.CEFR_ORDER:
        zone = next(c for c in ss.CATEGORIES_CONFIG if c["name"].startswith(
            f"{config.CEFR_LEVELS[lvl]['emoji']} {lvl} ZONE"))
        expected = f"{config.level_slug(lvl)}-daily-tasks"
        assert any(ch["name"] == expected for ch in zone["channels"])


# ============================================================
#  MIGRATION SCRIPT
# ============================================================

def test_migration_script_imports_and_targets_legacy_zones():
    import cefr_migrate_server as mig
    # It archives exactly the four legacy zone categories.
    assert len(mig._LEGACY_ZONE_NAMES) == 4
    assert "🌱 المستوى 0 | LEVEL 0" in mig._LEGACY_ZONE_NAMES



# ============================================================
#  Enriched #rules: copyright / legal + message chunking
# ============================================================

def test_rules_message_includes_copyright_and_legal_rules():
    """#rules must carry the IP/copyright, privacy, account, and own-work rules,
    attributed to MACAL EMPIRE (parent brand) / EEC (branch)."""
    m = ss.RULES_MESSAGE
    for token in ("RULE 8", "RULE 9", "RULE 10", "RULE 11",
                  "Copyright", "MACAL EMPIRE", "© MACAL EMPIRE", "EEC"):
        assert token in m, f"#rules must mention {token!r}"


def test_rules_message_is_bilingual():
    """The new rules include Arabic alongside English."""
    assert "الأكاديمية" in ss.RULES_MESSAGE or "ملك MACAL EMPIRE" in ss.RULES_MESSAGE


def test_chunk_message_respects_discord_limit():
    chunks = ss._chunk_message(ss.RULES_MESSAGE)
    assert len(chunks) >= 1
    assert all(len(c) <= 2000 for c in chunks), "every chunk must fit Discord's 2000-char limit"
    # nothing important is lost across the split
    joined = "\n".join(chunks)
    for token in ("RULE 1", "RULE 8", "RULE 11", "© MACAL EMPIRE"):
        assert token in joined


def test_chunk_message_keeps_short_content_single():
    assert ss._chunk_message(ss.WELCOME_MESSAGE) == [ss.WELCOME_MESSAGE]
    assert ss._chunk_message("short") == ["short"]


def test_chunk_message_hard_splits_a_giant_line():
    giant = "x" * 4500          # a single line with no boundaries
    chunks = ss._chunk_message(giant)
    assert all(len(c) <= 2000 for c in chunks)
    assert "".join(chunks) == giant   # no characters lost
