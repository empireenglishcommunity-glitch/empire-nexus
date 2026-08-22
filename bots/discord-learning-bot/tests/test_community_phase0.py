"""Community Lounge ("Majlis") Phase 0 — foundation tests.

Covers:
- 6 Majlis flags registered with correct defaults
- COMMUNITY_CONFIG_DEFAULTS + get/set_community_config
- together_minutes table: add/get (upsert, per-day isolation, zero-guard)
- community.py helpers: is_majlis_channel, get_majlis_room_ids,
  register/unregister, is_member_in_majlis_with_company
"""
import json

import pytest

from src import database
from src import community
from src import flag_registry


# ============================================================
#  FLAGS
# ============================================================

MAJLIS_FLAGS = [
    "community_together_credit",
    "community_lounge_beacon",
    "community_dynamic_rooms",
    "community_pings_optin",
    "community_power_hour",
    "community_together_reward",
]


def test_majlis_flags_registered():
    """All 6 Majlis flags exist in the registry."""
    names = {f[0] for f in flag_registry.REGISTRY}
    for flag in MAJLIS_FLAGS:
        assert flag in names, f"Flag '{flag}' not in REGISTRY"


def test_majlis_flags_default_off():
    """All Majlis flags default to OFF (never accidentally active)."""
    for name, _desc, _init, default in flag_registry.REGISTRY:
        if name in MAJLIS_FLAGS:
            assert default is False, f"Flag '{name}' should default OFF"


def test_majlis_initiative_in_initiatives():
    """The 'majlis' initiative is registered for display grouping."""
    assert "majlis" in flag_registry.INITIATIVES
    emoji, label, desc = flag_registry.INITIATIVES["majlis"]
    assert emoji == "🏛️"
    assert "MAJLIS" in label


def test_majlis_flags_synced_to_db():
    """sync_flag_registry creates the Majlis flags in the DB (all OFF)."""
    database.sync_flag_registry()
    for flag in MAJLIS_FLAGS:
        assert not database.is_feature_enabled(flag), f"{flag} should be OFF after sync"


# ============================================================
#  CONFIG
# ============================================================

def test_community_config_defaults():
    """get_community_config returns sane defaults when nothing is in settings."""
    cfg = database.get_community_config()
    assert cfg["community_together_minutes"] == 5
    assert cfg["community_lounge_capacity"] == 6
    assert cfg["community_beacon_max_occupancy"] == 4
    assert cfg["community_beacon_cooldown_min"] == 40
    assert cfg["community_beacon_ttl_min"] == 20
    assert cfg["community_reap_grace_min"] == 3
    assert cfg["community_hour_start"] == "21:00"
    assert cfg["community_hour_tz"] == "Africa/Cairo"
    assert cfg["community_hour_days"] == "0,1,2,3,4,5,6"
    assert cfg["community_hour_minutes"] == 60
    assert cfg["community_together_reward_points"] == 0


def test_community_config_override():
    """Owner can override a config key via set_community_config."""
    assert database.set_community_config("community_together_minutes", 3)
    cfg = database.get_community_config()
    assert cfg["community_together_minutes"] == 3


def test_community_config_rejects_unknown_key():
    """set_community_config rejects typos / unknown keys."""
    assert database.set_community_config("community_nonexistent_key", 99) is False


def test_community_config_bad_value_falls_back():
    """A garbled settings value falls back to the default (never crashes)."""
    database.set_setting("community_lounge_capacity", "not_a_number")
    cfg = database.get_community_config()
    assert cfg["community_lounge_capacity"] == 6  # default


# ============================================================
#  TOGETHER-MINUTES DATA STORE
# ============================================================

def test_add_together_minutes_basic():
    """add_together_minutes stores and get retrieves."""
    database.register_member("u1", "Alice")
    database.add_together_minutes("u1", 3.5)
    assert database.get_together_minutes("u1") == 3.5


def test_add_together_minutes_accumulates():
    """Multiple adds in the same day accumulate (upsert)."""
    database.register_member("u2", "Bob")
    database.add_together_minutes("u2", 2.0)
    database.add_together_minutes("u2", 1.5)
    assert database.get_together_minutes("u2") == 3.5


def test_add_together_minutes_zero_ignored():
    """Zero or negative minutes are silently ignored."""
    database.register_member("u3", "Carol")
    database.add_together_minutes("u3", 0)
    database.add_together_minutes("u3", -5)
    assert database.get_together_minutes("u3") == 0.0


def test_together_minutes_per_day_isolation():
    """Different dates don't bleed into each other."""
    database.register_member("u4", "Dave")
    database.add_together_minutes("u4", 10.0, date="2026-08-01")
    database.add_together_minutes("u4", 5.0, date="2026-08-02")
    assert database.get_together_minutes("u4", date="2026-08-01") == 10.0
    assert database.get_together_minutes("u4", date="2026-08-02") == 5.0


def test_together_minutes_unknown_member_returns_zero():
    """Querying an unknown member returns 0.0 (never crashes)."""
    assert database.get_together_minutes("unknown_id_999") == 0.0


# ============================================================
#  COMMUNITY.PY — CHANNEL IDENTITY
# ============================================================

class _FakeChannel:
    """Minimal mock for a Discord VoiceChannel."""
    def __init__(self, name: str, channel_id: str = "123"):
        self.name = name
        self.id = int(channel_id)


def test_is_majlis_anchor():
    """The permanent 'voice-lounge' channel is always a Majlis."""
    ch = _FakeChannel("voice-lounge", "111")
    assert community.is_majlis_channel(ch) is True


def test_is_not_majlis_level_room():
    """Level practice rooms are NOT Majlis lounges."""
    ch = _FakeChannel("l0-voice-1", "222")
    assert community.is_majlis_channel(ch) is False


def test_is_majlis_dynamic_room():
    """A dynamically registered room is identified as Majlis."""
    community.register_majlis_room("333")
    ch = _FakeChannel("Majlis 2", "333")
    assert community.is_majlis_channel(ch) is True


def test_unregister_majlis_room():
    """Unregistering removes the room from Majlis identity."""
    community.register_majlis_room("444")
    community.unregister_majlis_room("444")
    ch = _FakeChannel("Majlis 3", "444")
    assert community.is_majlis_channel(ch) is False


def test_get_majlis_room_ids_empty_by_default():
    """No dynamic rooms registered initially."""
    # Clear any leftover from other tests
    database.set_setting("majlis_rooms", "[]")
    assert community.get_majlis_room_ids() == set()


def test_register_multiple_rooms():
    """Multiple rooms can be registered and retrieved."""
    database.set_setting("majlis_rooms", "[]")  # reset
    community.register_majlis_room("500")
    community.register_majlis_room("501")
    community.register_majlis_room("502")
    ids = community.get_majlis_room_ids()
    assert ids == {"500", "501", "502"}


# ============================================================
#  COMMUNITY.PY — OCCUPANCY + COMPANY CHECK
# ============================================================

class _FakeMember:
    def __init__(self, uid: str, bot: bool = False):
        self.id = int(uid)
        self.bot = bot


class _FakeVC:
    def __init__(self, name: str, channel_id: str, members: list):
        self.name = name
        self.id = int(channel_id)
        self.members = members


class _FakeGuild:
    def __init__(self, voice_channels: list):
        self.voice_channels = voice_channels


def test_lounge_occupancy_filters_majlis_only():
    """lounge_occupancy only returns Majlis channels, ignoring level rooms."""
    vc1 = _FakeVC("voice-lounge", "100", [_FakeMember("1"), _FakeMember("2")])
    vc2 = _FakeVC("l0-voice-1", "200", [_FakeMember("3")])
    guild = _FakeGuild([vc1, vc2])
    occ = community.lounge_occupancy(guild)
    assert "100" in occ
    assert "200" not in occ
    assert occ["100"] == ["1", "2"]


def test_lounge_occupancy_ignores_bots():
    """Bots are excluded from occupancy counts."""
    vc = _FakeVC("voice-lounge", "100", [_FakeMember("1"), _FakeMember("99", bot=True)])
    guild = _FakeGuild([vc])
    occ = community.lounge_occupancy(guild)
    assert occ["100"] == ["1"]


def test_lounge_occupancy_empty_lounges_excluded():
    """Empty Majlis lounges don't appear in the result."""
    vc = _FakeVC("voice-lounge", "100", [])
    guild = _FakeGuild([vc])
    occ = community.lounge_occupancy(guild)
    assert occ == {}


def test_is_member_in_majlis_with_company_true():
    """Returns True when the member is in a Majlis with another human."""
    vc = _FakeVC("voice-lounge", "100", [_FakeMember("1"), _FakeMember("2")])
    guild = _FakeGuild([vc])
    assert community.is_member_in_majlis_with_company(guild, "1") is True


def test_is_member_in_majlis_with_company_alone():
    """Returns False when the member is alone in the Majlis."""
    vc = _FakeVC("voice-lounge", "100", [_FakeMember("1")])
    guild = _FakeGuild([vc])
    assert community.is_member_in_majlis_with_company(guild, "1") is False


def test_is_member_in_majlis_with_company_not_in_majlis():
    """Returns False when the member isn't in a Majlis at all."""
    vc = _FakeVC("l0-voice-1", "200", [_FakeMember("1"), _FakeMember("2")])
    guild = _FakeGuild([vc])
    assert community.is_member_in_majlis_with_company(guild, "1") is False


# ============================================================
#  COMMUNITY.PY — CONFIG ACCESSORS
# ============================================================

def test_get_together_minutes_threshold_default():
    assert community.get_together_minutes_threshold() == 5


def test_get_lounge_capacity_default():
    assert community.get_lounge_capacity() == 6


def test_get_beacon_max_occupancy_default():
    assert community.get_beacon_max_occupancy() == 4


def test_config_accessors_reflect_overrides():
    """Config accessors pick up owner overrides from settings."""
    database.set_community_config("community_together_minutes", 7)
    assert community.get_together_minutes_threshold() == 7
