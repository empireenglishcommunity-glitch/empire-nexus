"""Tests for per-level zone isolation in role_gate.

Locks in the fix for the bug where !setupgate granted the shared gateway role
view on EVERY non-admin channel — including per-level zones — so every student
saw every level. Covers:
  1. level_zone_of() identifies zones (by slug + category) and not shared/admin.
  2. audit_level_isolation() flags a zone visible to @everyone / the gateway
     role / another level's role, and passes when only the own level can view.
"""
import discord
from src import role_gate, config


class FakeRole:
    def __init__(self, name):
        self.name = name


class FakeOverwrite:
    def __init__(self, view_channel=None):
        self.view_channel = view_channel


class FakeCategory:
    def __init__(self, name):
        self.name = name


class FakeTextChannel(discord.TextChannel):
    def __init__(self, name, category=None, overwrites=None):
        self.name = name
        self._cat = category
        self._ow = overwrites or {}

    @property
    def category(self):
        return self._cat

    @property
    def overwrites(self):
        return self._ow


class FakeGuild:
    def __init__(self, channels, roles, everyone):
        self.channels = channels
        self.roles = roles
        self.default_role = everyone


# ── level_zone_of ────────────────────────────────────────────────────────────
def test_level_zone_detected_by_slug():
    assert role_gate.level_zone_of(FakeTextChannel("a1-daily-tasks")) == "A1"
    assert role_gate.level_zone_of(FakeTextChannel("c2-voice-1")) == "C2"


def test_level_zone_detected_by_category():
    ch = FakeTextChannel("notes", category=FakeCategory("🌱 A1 ZONE | مبتدئ"))
    assert role_gate.level_zone_of(ch) == "A1"


def test_shared_and_admin_channels_are_not_level_zones():
    for name in ("general-chat", "community-live", "rules", "welcome",
                 "accountability", "admin-chat", "bot-logs"):
        assert role_gate.level_zone_of(FakeTextChannel(name)) is None


# ── audit_level_isolation ────────────────────────────────────────────────────
def _guild_with_a1_zone(overwrites_fn):
    everyone = FakeRole("@everyone")
    gateway = FakeRole(role_gate.STUDENT_ROLE_NAME)
    a1 = FakeRole(config.level_role_name("A1"))
    a2 = FakeRole(config.level_role_name("A2"))
    roles = [everyone, gateway, a1, a2]
    zone = FakeTextChannel("a1-daily-tasks",
                           category=FakeCategory("🌱 A1 ZONE | مبتدئ"),
                           overwrites=overwrites_fn(everyone, gateway, a1, a2))
    shared = FakeTextChannel("general-chat")
    return FakeGuild([zone, shared], roles, everyone)


def test_leak_flagged_when_gateway_role_can_view():
    guild = _guild_with_a1_zone(lambda e, g, a1, a2: {
        e: FakeOverwrite(False),
        g: FakeOverwrite(True),      # <- the bug: shared gateway role opens the zone
        a1: FakeOverwrite(True),
    })
    audit = role_gate.audit_level_isolation(guild)
    assert audit["checked"] == 1
    assert len(audit["leaks"]) == 1
    assert "gateway" in " ".join(audit["leaks"][0]["reasons"]).lower()


def test_leak_flagged_when_other_level_role_can_view():
    guild = _guild_with_a1_zone(lambda e, g, a1, a2: {
        e: FakeOverwrite(False),
        a1: FakeOverwrite(True),
        a2: FakeOverwrite(True),     # <- another level can see the A1 zone
    })
    audit = role_gate.audit_level_isolation(guild)
    assert len(audit["leaks"]) == 1
    assert "another level" in " ".join(audit["leaks"][0]["reasons"]).lower()


def test_leak_flagged_when_everyone_can_view():
    guild = _guild_with_a1_zone(lambda e, g, a1, a2: {
        e: FakeOverwrite(True),      # <- @everyone
        a1: FakeOverwrite(True),
    })
    audit = role_gate.audit_level_isolation(guild)
    assert len(audit["leaks"]) == 1


def test_no_leak_when_only_own_level_can_view():
    guild = _guild_with_a1_zone(lambda e, g, a1, a2: {
        e: FakeOverwrite(False),
        g: FakeOverwrite(False),
        a1: FakeOverwrite(True),     # own level only — correct
        a2: FakeOverwrite(False),
    })
    audit = role_gate.audit_level_isolation(guild)
    assert audit["leaks"] == []
    assert audit["ok_count"] == 1
    assert "OK" in role_gate.format_level_isolation(audit)
