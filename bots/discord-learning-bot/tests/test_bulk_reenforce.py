"""Tests for bulk re-enforce (/reenforce-suspensions).

After the /setupgate retroactive-grant bug re-granted roles to suspended
students, their DB status stayed 'suspended' but their Discord roles came back.
This command re-strips roles from EVERY student already flagged suspended in the
DB — and nobody else — using the re-enforce path (clock/sessions/DM untouched).
Dry run unless confirmed.
"""
import pytest

from src import bot as botmod, database, role_gate, config


GATEWAY = role_gate.STUDENT_ROLE_NAME
A1_ROLE = config.level_role_name("A1")


class FakeRole:
    def __init__(self, name):
        self.name = name


class FakeMember:
    def __init__(self, mid, roles):
        self.id = int(mid)
        self.display_name = f"user{mid}"
        self.roles = [FakeRole(n) for n in roles]

    async def remove_roles(self, role, reason=None):
        self.roles = [r for r in self.roles if r.name != role.name]

    def role_names(self):
        return {r.name for r in self.roles}


class FakeGuild:
    def __init__(self, members_by_id):
        self._m = members_by_id
        self.roles = [FakeRole(GATEWAY), FakeRole(A1_ROLE)]
        self.me = None

    def get_member(self, mid):
        return self._m.get(int(mid))


def _mk_suspended(did, name):
    database.register_member(did, name, level="A1")
    database.suspend_member(did)
    return did


@pytest.mark.asyncio
async def test_dry_run_lists_only_suspended_and_changes_nothing():
    from src import suspension
    database.set_feature_flag(suspension.FLAG, True)
    did = _mk_suspended("9201", "Suspended Sara")
    member = FakeMember(did, [GATEWAY, A1_ROLE])   # roles wrongly back
    guild = FakeGuild({int(did): member})

    text = await botmod._reenforce_suspensions_text(guild, confirm=False)

    assert "DRY RUN" in text
    assert "Suspended Sara" in text
    assert member.role_names() == {GATEWAY, A1_ROLE}   # nothing removed yet


@pytest.mark.asyncio
async def test_confirm_restrips_only_suspended_students():
    from src import suspension
    database.set_feature_flag(suspension.FLAG, True)

    s1 = _mk_suspended("9202", "Sus One")
    s2 = _mk_suspended("9203", "Sus Two")
    # An ACTIVE student who must NOT be touched.
    active = "9204"
    database.register_member(active, "Active Amy", level="A1")

    m1 = FakeMember(s1, [GATEWAY, A1_ROLE])
    m2 = FakeMember(s2, [GATEWAY, A1_ROLE])
    m_active = FakeMember(active, [GATEWAY, A1_ROLE])
    guild = FakeGuild({int(s1): m1, int(s2): m2, int(active): m_active})

    text = await botmod._reenforce_suspensions_text(guild, confirm=True)

    assert m1.role_names() == set()        # suspended → roles stripped
    assert m2.role_names() == set()
    assert m_active.role_names() == {GATEWAY, A1_ROLE}   # active untouched
    assert "Re-applied access removal" in text


@pytest.mark.asyncio
async def test_nobody_suspended_reports_clean(monkeypatch):
    from src import suspension
    database.set_feature_flag(suspension.FLAG, True)
    monkeypatch.setattr(database, "suspended_members", lambda: [])
    text = await botmod._reenforce_suspensions_text(FakeGuild({}), confirm=True)
    assert "Nobody is currently flagged suspended" in text


def test_command_registered_and_admin_gated():
    assert botmod.bot.get_command("reenforce-suspensions") is not None
    assert botmod.bot.tree.get_command("reenforce-suspensions") is not None
    assert "reenforce-suspensions" in botmod._admin_command_names()
