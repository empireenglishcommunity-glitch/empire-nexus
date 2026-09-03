"""Tests for the admin-channel exposure guardrail in role_gate.

These lock in the fix for the bug where !setupgate granted the Student gateway
role view+send on EVERY non-rules/welcome channel — including the admin/ghost
channels — so every student could see admin channels once they passed the gate.

Two things are covered:
  1. is_admin_only_channel() correctly identifies admin/ghost channels (by name
     and by category) and does NOT flag ordinary student channels.
  2. audit_admin_exposure() flags an admin channel that a student-reachable role
     (@everyone, the Student gateway role, or a CEFR level role) can view, and
     reports it clean when only staff roles can view.
"""
from src import role_gate, config


# ── Minimal discord doubles ─────────────────────────────────────────────────
class FakeRole:
    def __init__(self, name):
        self.name = name


class FakeOverwrite:
    def __init__(self, view_channel=None):
        self.view_channel = view_channel


class FakeCategory:
    def __init__(self, name):
        self.name = name


# discord.TextChannel is what is_admin_only_channel / audit isinstance-check
# against; subclass it so isinstance passes without a real gateway connection.
import discord


class FakeTextChannel(discord.TextChannel):
    def __init__(self, name, category=None, overwrites=None):
        # bypass discord's __init__ (needs a real state/guild)
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


# ── is_admin_only_channel ────────────────────────────────────────────────────
def test_detects_admin_channels_by_name():
    for name in ("admin-chat", "mod-actions", "member-notes", "bot-logs",
                 "dev-log", "ghost-commands", "ghost-showcase", "ghost-writing"):
        ch = FakeTextChannel(name)
        assert role_gate.is_admin_only_channel(ch), f"{name} should be admin-only"


def test_detects_admin_channels_by_category():
    # A channel with a neutral name but inside the ADMIN category is still admin.
    ch = FakeTextChannel("notes", category=FakeCategory("🔒 الإدارة | ADMIN"))
    assert role_gate.is_admin_only_channel(ch)
    ch2 = FakeTextChannel("scratch", category=FakeCategory("👻 Ghost Testing"))
    assert role_gate.is_admin_only_channel(ch2)


def test_does_not_flag_student_channels():
    for name in ("a1-daily-tasks", "a1-text-practice", "rules", "welcome",
                 "general-chat", "community-live", "a1-showcase"):
        ch = FakeTextChannel(name, category=FakeCategory("🌱 A1 ZONE | مبتدئ"))
        assert not role_gate.is_admin_only_channel(ch), f"{name} must NOT be admin-only"


# ── audit_admin_exposure ─────────────────────────────────────────────────────
def _build_guild(admin_overwrites):
    everyone = FakeRole("@everyone")
    student = FakeRole(role_gate.STUDENT_ROLE_NAME)
    a1 = FakeRole(config.level_role_name("A1"))
    admin = FakeRole("🛡️ Admin")
    roles = [everyone, student, a1, admin]
    admin_chan = FakeTextChannel(
        "admin-chat",
        category=FakeCategory("🔒 الإدارة | ADMIN"),
        overwrites=admin_overwrites(everyone, student, a1, admin),
    )
    student_chan = FakeTextChannel("a1-daily-tasks",
                                   category=FakeCategory("🌱 A1 ZONE | مبتدئ"))
    return FakeGuild([admin_chan, student_chan], roles, everyone)


def test_exposure_flags_student_role_allowed():
    # The exact bug: Student gateway role allowed view on the admin channel.
    guild = _build_guild(lambda e, s, a1, adm: {
        e: FakeOverwrite(view_channel=False),
        s: FakeOverwrite(view_channel=True),      # <-- exposure
        adm: FakeOverwrite(view_channel=True),
    })
    audit = role_gate.audit_admin_exposure(guild)
    assert audit["checked"] == 1
    assert len(audit["exposed"]) == 1
    reasons = " ".join(audit["exposed"][0]["reasons"])
    assert "Student" in reasons


def test_exposure_flags_everyone_allowed():
    guild = _build_guild(lambda e, s, a1, adm: {
        e: FakeOverwrite(view_channel=True),       # <-- exposure
        adm: FakeOverwrite(view_channel=True),
    })
    audit = role_gate.audit_admin_exposure(guild)
    assert len(audit["exposed"]) == 1
    assert any("@everyone" in r for r in audit["exposed"][0]["reasons"])


def test_exposure_flags_level_role_allowed():
    guild = _build_guild(lambda e, s, a1, adm: {
        e: FakeOverwrite(view_channel=False),
        a1: FakeOverwrite(view_channel=True),      # <-- exposure via level role
        adm: FakeOverwrite(view_channel=True),
    })
    audit = role_gate.audit_admin_exposure(guild)
    assert len(audit["exposed"]) == 1


def test_no_exposure_when_only_staff_allowed():
    # Correct state: everyone + student + level denied, only Admin allowed.
    guild = _build_guild(lambda e, s, a1, adm: {
        e: FakeOverwrite(view_channel=False),
        s: FakeOverwrite(view_channel=False),
        a1: FakeOverwrite(view_channel=False),
        adm: FakeOverwrite(view_channel=True),
    })
    audit = role_gate.audit_admin_exposure(guild)
    assert audit["exposed"] == []
    assert audit["ok_count"] == 1
    assert "OK" in role_gate.format_admin_exposure(audit)



# ── Archived legacy "Level 0" material must be admin-only (never student) ─────
# Bug: the server was migrated L0–L3 → CEFR A1–C2. The old "Level 0" category
# and its channels were archived for staff, but level_zone_of only recognizes
# a1–c2 (and config.level_slug("L0") → "a1"), so a legacy Level-0 channel matched
# no zone/admin rule and fell through to the SHARED branch — visible to students.
def test_archived_level0_category_is_admin_only():
    for cat_name in ("🌱 Level 0 | مبتدئ", "LEVEL 0", "level-0", "Level Zero"):
        ch = FakeTextChannel("some-old-chan", category=FakeCategory(cat_name))
        assert role_gate.is_admin_only_channel(ch), f"{cat_name!r} must be admin-only"


def test_archived_level0_channel_slugs_are_admin_only():
    for name in ("l0-daily-tasks", "l0-showcase", "level0-chat",
                 "level-0-questions", "level0"):
        ch = FakeTextChannel(name)
        assert role_gate.is_admin_only_channel(ch), f"{name} must be admin-only"


def test_level0_detection_does_not_catch_cefr_or_community_or_other_legacy():
    # Must NOT accidentally hide student-facing channels or other legacy levels.
    safe = [
        FakeTextChannel("community-live", category=FakeCategory("🌍 المجتمع | COMMUNITY")),
        FakeTextChannel("general-chat"),
        FakeTextChannel("a1-daily-tasks", category=FakeCategory("🌱 A1 ZONE | مبتدئ")),
        FakeTextChannel("level-1-tasks"),          # legacy A2, NOT Level 0
        FakeTextChannel("level-2-showcase"),       # legacy B1, NOT Level 0
        FakeTextChannel("control-room"),           # contains 'l0'? no — sanity
    ]
    for ch in safe:
        assert not role_gate.is_admin_only_channel(ch), f"{ch.name} must stay visible"


def test_archived_level0_is_protected_from_deletion():
    """A nice side effect: since it's now admin-only, /deletechannel also refuses
    it (protected_channel_reason flags admin channels). Confirms consistency."""
    ch = FakeTextChannel("l0-daily-tasks", category=FakeCategory("🌱 Level 0 | مبتدئ"))
    assert role_gate.protected_channel_reason(ch) is not None



# ── An ARCHIVE category (not just "Level 0") must be admin-only ───────────────
# The owner parks retired categories under an "Archive"/"أرشيف" category. Any
# channel inside it must be staff-only, even if its own name looks ordinary.
def test_archive_category_is_admin_only():
    for cat_name in ("📦 Archive | الأرشيف", "ARCHIVE", "أرشيف",
                     "🗄️ Archived — old zones", "archived"):
        ch = FakeTextChannel("some-old-chan", category=FakeCategory(cat_name))
        assert role_gate.is_admin_only_channel(ch), f"{cat_name!r} must be admin-only"


def test_archive_detection_matches_category_not_channel_name():
    # A channel literally named 'archives-of-honour' but NOT inside an archive
    # category must stay student-visible (we key archive on the CATEGORY only).
    ch = FakeTextChannel("archives-of-honour", category=FakeCategory("🏆 HONOUR"))
    assert not role_gate.is_admin_only_channel(ch)
