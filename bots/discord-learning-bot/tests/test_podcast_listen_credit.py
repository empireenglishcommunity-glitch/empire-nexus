"""Tests for Podcast Studio (Sawt) Phase 1 Task 1.5 — listening credit.

A student ✅ on a published episode (or !listened <id>) records the listen and
awards a small, capped, once-per-episode credit — gated behind sawt_listen_credit.
"""
import pytest

from src import bot as botmod, database, config


def _enable(flag, on=True):
    database.set_feature_flag(flag, on, "", "test")


def _member_and_episode():
    database.register_member("stu1", "Student One", level="A1")
    eid = database.create_episode("A1", "Ep", "solo_ai", audio_url="https://cdn/a.mp3")
    database.publish_episode(eid)
    return "stu1", eid


# ── _award_listen_credit ─────────────────────────────────────────────────────
def test_credit_awarded_once_when_flag_on():
    _enable("sawt_listen_credit", True)
    did, eid = _member_and_episode()
    before = database.get_member(did)["total_points"]

    assert botmod._award_listen_credit(did, eid) is True       # first listen
    after = database.get_member(did)["total_points"]
    assert after == before + config.POINTS_PODCAST_LISTEN
    assert database.has_listened(did, eid) is True

    # Second time: no new credit, points unchanged.
    assert botmod._award_listen_credit(did, eid) is False
    assert database.get_member(did)["total_points"] == after


def test_no_credit_when_flag_off():
    _enable("sawt_listen_credit", False)
    did, eid = _member_and_episode()
    before = database.get_member(did)["total_points"]
    assert botmod._award_listen_credit(did, eid) is False
    assert database.get_member(did)["total_points"] == before
    assert database.has_listened(did, eid) is False


def test_no_credit_for_unregistered_user():
    _enable("sawt_listen_credit", True)
    eid = database.create_episode("A1", "Ep", "solo_ai", audio_url="x")
    database.publish_episode(eid)
    assert botmod._award_listen_credit("ghost999", eid) is False


# ── ✅ reaction handler ──────────────────────────────────────────────────────
class FakeMember:
    def __init__(self, mid, bot=False):
        self.id = mid
        self.bot = bot


class FakeGuild:
    def __init__(self, members):
        self._m = {str(k): v for k, v in members.items()}

    def get_member(self, mid):
        return self._m.get(str(mid))


class FakePayload:
    def __init__(self, message_id, user_id):
        self.message_id = message_id
        self.user_id = user_id     # discord passes an int; the code str()s it
        self.emoji = "✅"


@pytest.mark.asyncio
async def test_reaction_on_episode_message_awards_credit():
    _enable("sawt_listen_credit", True)
    database.register_member("stu2", "Student Two", level="A1")
    eid = database.create_episode("A1", "Ep", "solo_ai", audio_url="x")
    database.publish_episode(eid)
    database.set_episode_audio_message_id(eid, "7777")

    guild = FakeGuild({"stu2": FakeMember("stu2")})
    handled = await botmod._handle_podcast_listen_reaction(FakePayload(7777, "stu2"), guild)
    assert handled is True
    assert database.has_listened("stu2", eid) is True


@pytest.mark.asyncio
async def test_reaction_on_non_episode_message_is_ignored():
    _enable("sawt_listen_credit", True)
    guild = FakeGuild({})
    # message id that maps to no episode → not handled (lets other handlers run)
    handled = await botmod._handle_podcast_listen_reaction(FakePayload(1234, "x"), guild)
    assert handled is False


@pytest.mark.asyncio
async def test_reaction_by_bot_is_handled_but_no_credit():
    _enable("sawt_listen_credit", True)
    eid = database.create_episode("A1", "Ep", "solo_ai", audio_url="x")
    database.publish_episode(eid)
    database.set_episode_audio_message_id(eid, "8888")
    guild = FakeGuild({"9": FakeMember("9", bot=True)})
    handled = await botmod._handle_podcast_listen_reaction(FakePayload(8888, "9"), guild)
    assert handled is True                       # it IS an episode message
    assert database.episode_listen_count(eid) == 0   # but a bot earns nothing
