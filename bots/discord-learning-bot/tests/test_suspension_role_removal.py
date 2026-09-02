"""Regression tests: suspension must remove EVERY access-granting role.

Bug (2026-09-03): suspension removed only the gateway role (`✅ Student | طالب`)
and left the student's CEFR level role (e.g. `🌱 A1 | مبتدئ`). Since the PR #474
level-zone isolation, the per-level ZONE channels (a1-daily-tasks, a1-voice-1…)
are made visible by the LEVEL role — the gateway role is explicitly DENIED on
them. So a suspended student kept their level role and could still see their
daily-tasks zone: "still has roles, nothing happened."

These tests lock in the fix: suspend removes the gateway role AND the level
role; restore re-adds both. Nothing here talks to Discord — a fake guild/member
exercises suspension.suspend_one / restore_one directly.
"""
import pytest

from src import database, suspension, role_gate, config


GATEWAY = role_gate.STUDENT_ROLE_NAME
A1_ROLE = config.level_role_name("A1")


class FakeRole:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"FakeRole({self.name!r})"


class FakeMember:
    def __init__(self, member_id, role_names):
        self.id = int(member_id)
        self.display_name = f"user{member_id}"
        self.roles = [FakeRole(n) for n in role_names]

    async def add_roles(self, role, reason=None):
        if role.name not in [r.name for r in self.roles]:
            self.roles.append(role)

    async def remove_roles(self, role, reason=None):
        self.roles = [r for r in self.roles if r.name != role.name]

    def role_names(self):
        return {r.name for r in self.roles}


class FakeGuild:
    """A guild that knows one member and the two access roles by name."""
    def __init__(self, member):
        self._member = member
        self.roles = [FakeRole(GATEWAY), FakeRole(A1_ROLE)]

    def get_member(self, mid):
        return self._member if int(mid) == self._member.id else None

    async def create_role(self, **kwargs):
        r = FakeRole(kwargs.get("name", "role"))
        self.roles.append(r)
        return r


def _mk(discord_id="800", level="A1"):
    database.register_member(discord_id, "Suspend Target", level=level)
    database.set_level(discord_id, level)
    return discord_id


# ── SUSPEND removes both the gateway AND the level role ──────────────────────
@pytest.mark.asyncio
async def test_suspend_removes_gateway_and_level_role():
    did = _mk("801", "A1")
    member = FakeMember(did, [GATEWAY, A1_ROLE, "community-pings"])
    guild = FakeGuild(member)

    res = await suspension.suspend_one(guild, database.get_member(did), dry_run=False)

    assert res["role_removed"] is True
    # BOTH access roles are gone …
    assert GATEWAY not in member.role_names()
    assert A1_ROLE not in member.role_names()
    # … and the cosmetic pings role (no channel access) is untouched.
    assert "community-pings" in member.role_names()
    assert not res["errors"]


@pytest.mark.asyncio
async def test_suspend_strips_level_role_even_if_gateway_already_gone():
    """Drift case: a student who somehow lost the gateway role but kept the
    level role must STILL lose the level role (they can still see their zone)."""
    did = _mk("802", "A1")
    member = FakeMember(did, [A1_ROLE])          # no gateway role
    guild = FakeGuild(member)

    res = await suspension.suspend_one(guild, database.get_member(did), dry_run=False)

    assert A1_ROLE not in member.role_names()
    assert res["role_removed"] is True


@pytest.mark.asyncio
async def test_suspend_dry_run_changes_no_roles_but_flags_removal():
    did = _mk("803", "A1")
    member = FakeMember(did, [GATEWAY, A1_ROLE])
    guild = FakeGuild(member)

    res = await suspension.suspend_one(guild, database.get_member(did), dry_run=True)

    assert res["role_removed"] is True            # "will be removed"
    assert member.role_names() == {GATEWAY, A1_ROLE}   # nothing actually changed
    assert database.is_suspended(did) is False


# ── RESTORE re-adds both roles (symmetric) ───────────────────────────────────
@pytest.mark.asyncio
async def test_restore_readds_gateway_and_level_role():
    did = _mk("804", "A1")
    database.suspend_member(did)
    member = FakeMember(did, [])                  # suspended: holds no access roles
    guild = FakeGuild(member)

    res = await suspension.restore_one(guild, database.get_member(did), dry_run=False)

    assert res["role_added"] is True
    assert GATEWAY in member.role_names()
    assert A1_ROLE in member.role_names()
    assert not res["errors"]


@pytest.mark.asyncio
async def test_suspend_then_restore_round_trip():
    did = _mk("805", "A2")
    a2_role = config.level_role_name("A2")
    member = FakeMember(did, [GATEWAY, a2_role])
    guild = FakeGuild(member)
    guild.roles.append(FakeRole(a2_role))

    await suspension.suspend_one(guild, database.get_member(did), dry_run=False)
    assert member.role_names() == set()           # fully withdrawn

    await suspension.restore_one(guild, database.get_member(did), dry_run=False)
    assert GATEWAY in member.role_names()
    assert a2_role in member.role_names()          # correct level restored



# ── RE-ENFORCE: repair an already-suspended student who kept their roles ─────
@pytest.mark.asyncio
async def test_reenforce_strips_roles_of_already_suspended_student():
    """The Abeer/Narimal repair case: DB says suspended, but the level role was
    never removed (pre-fix bug). reenforce=True must strip it WITHOUT touching
    the retention clock."""
    did = _mk("806", "A1")
    database.suspend_member(did, when="2026-08-01 00:00:00")
    before = database.get_member(did)["suspended_at"]

    member = FakeMember(did, [GATEWAY, A1_ROLE])   # still holding roles
    guild = FakeGuild(member)

    res = await suspension.suspend_one(
        guild, database.get_member(did), dry_run=False, reenforce=True)

    assert res["already"] is True
    assert res["reenforced"] is True
    assert res["role_removed"] is True
    assert member.role_names() == set()            # both access roles gone
    # retention clock untouched
    assert database.get_member(did)["suspended_at"] == before


@pytest.mark.asyncio
async def test_reenforce_is_idempotent_when_roles_already_gone():
    did = _mk("807", "A1")
    database.suspend_member(did)
    member = FakeMember(did, [])                    # already has no access roles
    guild = FakeGuild(member)

    res = await suspension.suspend_one(
        guild, database.get_member(did), dry_run=False, reenforce=True)

    assert res["reenforced"] is True
    assert res["role_removed"] is True              # no-op counts as success
    assert not res["errors"]


@pytest.mark.asyncio
async def test_default_suspend_still_skips_already_suspended():
    """Without reenforce, an already-suspended student is still skipped (no
    behavior change to bulk /suspend all)."""
    did = _mk("808", "A1")
    database.suspend_member(did)
    member = FakeMember(did, [GATEWAY, A1_ROLE])
    guild = FakeGuild(member)

    res = await suspension.suspend_one(guild, database.get_member(did), dry_run=False)

    assert res["already"] is True
    assert res["reenforced"] is False
    assert member.role_names() == {GATEWAY, A1_ROLE}   # untouched
