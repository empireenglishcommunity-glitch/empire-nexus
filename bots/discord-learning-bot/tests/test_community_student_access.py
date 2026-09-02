"""Bug fix: freshly-created community channels must be visible to students.

#community-live and the Majlis hub are created at RUNTIME by community.py (not
by scripts/setup_server.py), so they inherit the COMMUNITY category's overwrites
— which deny @everyone. Until an admin re-ran !setupgate, the student gateway
role had no view overwrite on the new channel and students hit 'no permission'.

The fix grants the gateway role view/send (and denies @everyone) at creation
time via community._grant_student_access. These tests lock that in.
"""
import pytest

from src import community, role_gate


class FakeRole:
    def __init__(self, name):
        self.name = name


class FakeChannel:
    def __init__(self, name):
        self.name = name
        self.perms = {}   # role_name -> dict(view_channel=, send_messages=)

    async def set_permissions(self, target, reason=None, **kwargs):
        self.perms[target.name] = kwargs


class FakeGuild:
    def __init__(self):
        self.default_role = FakeRole("@everyone")
        self._student = FakeRole(role_gate.STUDENT_ROLE_NAME)

    # community._grant_student_access calls role_gate.get_or_create_student_role;
    # we patch that in the test to return our fake role, so no guild.create_role
    # is needed here.


@pytest.mark.asyncio
async def test_grant_student_access_opens_channel_to_gateway_role(monkeypatch):
    guild = FakeGuild()
    channel = FakeChannel("community-live")

    async def fake_get_or_create(g):
        return guild._student
    monkeypatch.setattr(role_gate, "get_or_create_student_role", fake_get_or_create)

    await community._grant_student_access(guild, channel)

    # @everyone denied, gateway role allowed view + send
    assert channel.perms["@everyone"]["view_channel"] is False
    student = channel.perms[role_gate.STUDENT_ROLE_NAME]
    assert student["view_channel"] is True
    assert student["send_messages"] is True


@pytest.mark.asyncio
async def test_grant_student_access_is_failure_tolerant(monkeypatch):
    """A permissions error must be swallowed — channel creation must never break
    because access-granting failed."""
    guild = FakeGuild()

    class BoomChannel:
        name = "community-live"

        async def set_permissions(self, *a, **k):
            raise RuntimeError("Missing Permissions")

    async def fake_get_or_create(g):
        return guild._student
    monkeypatch.setattr(role_gate, "get_or_create_student_role", fake_get_or_create)

    # Should NOT raise.
    await community._grant_student_access(guild, BoomChannel())
