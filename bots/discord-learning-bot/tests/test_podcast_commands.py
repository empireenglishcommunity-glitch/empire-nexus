"""Tests for Podcast Studio (Sawt) Phase 1 — flags, commands, and channel isolation.

Covers the sawt flags, the episode command surface (registered + admin-gated),
the publish/list helper logic, and that #<slug>-podcast is treated as a level
zone (so /setupgate keeps it isolated to its own level).
"""
import pytest

from src import bot as botmod, database, role_gate, config, flag_registry


class FakeCat:
    def __init__(self, name):
        self.name = name


class FakeChannel:
    def __init__(self, name, category=None):
        self.name = name
        self.category = FakeCat(category) if category else None


# ── Flags (Task 1.2) ─────────────────────────────────────────────────────────
def test_sawt_flags_registered_default_off():
    reg = {e[0]: e for e in flag_registry.REGISTRY}
    assert "sawt_episodes" in reg and reg["sawt_episodes"][3] is False
    assert "sawt_listen_credit" in reg and reg["sawt_listen_credit"][3] is False
    assert reg["sawt_episodes"][2] == "sawt"


def test_sawt_initiative_exists():
    assert "sawt" in flag_registry.INITIATIVES
    emoji, label, desc = flag_registry.INITIATIVES["sawt"]
    assert label == "SAWT"


# ── Channel isolation (Task 1.3 / 3) ─────────────────────────────────────────
def test_podcast_channel_is_a_level_zone():
    # #<slug>-podcast must be recognized as that level's zone (slug prefix),
    # so /setupgate denies the gateway role and only the own-level role sees it.
    assert role_gate.level_zone_of(FakeChannel("a1-podcast")) == "A1"
    assert role_gate.level_zone_of(FakeChannel("c2-podcast")) == "C2"
    # And it is NOT admin-only / archived.
    assert role_gate.is_admin_only_channel(FakeChannel("a1-podcast")) is False


# ── Command registration ─────────────────────────────────────────────────────
def test_commands_registered_and_admin_gated():
    assert botmod.bot.tree.get_command("create-episode") is not None
    assert botmod.bot.tree.get_command("publish-episode") is not None
    assert botmod.bot.tree.get_command("episodes") is not None
    # prefix + /admin bridge for the two that make sense as text commands
    assert botmod.bot.get_command("publish-episode") is not None
    assert botmod.bot.get_command("episodes") is not None
    assert "publish-episode" in botmod._admin_command_names()
    assert "episodes" in botmod._admin_command_names()


# ── Publish/list helpers ─────────────────────────────────────────────────────
def test_episodes_list_text_empty_and_populated():
    assert "No podcast episodes" in botmod._episodes_list_text()
    eid = database.create_episode("A1", "Ep One", "solo_ai")
    txt = botmod._episodes_list_text()
    assert "Ep One" in txt and "draft" in txt
    txt_a1 = botmod._episodes_list_text("A1")
    assert "Ep One" in txt_a1


@pytest.mark.asyncio
async def test_publish_refuses_missing_and_audioless():
    # Missing episode
    msg = await botmod._publish_episode_text(guild=None, episode_id=9999)
    assert "not found" in msg.lower()
    # Episode with no audio → refuses (asks for audio) before touching Discord
    eid = database.create_episode("A1", "No Audio", "solo_ai")
    msg2 = await botmod._publish_episode_text(guild=None, episode_id=eid)
    assert "no audio" in msg2.lower()
    assert database.get_episode(eid)["published"] == 0   # not published


@pytest.mark.asyncio
async def test_publish_refuses_already_published():
    eid = database.create_episode("A1", "Done", "solo_ai",
                                  audio_url="https://cdn/a.mp3")
    database.publish_episode(eid)
    msg = await botmod._publish_episode_text(guild=None, episode_id=eid)
    assert "already published" in msg.lower()


@pytest.mark.asyncio
async def test_publish_posts_and_marks_published():
    """With a fake guild/channel, publish posts the episode, pins reaction,
    stores the message id, and marks it published."""
    posted = {}

    class FakeMsg:
        id = 4242
        async def add_reaction(self, emoji):
            posted["reacted"] = emoji

    class FakeChan:
        name = "a1-podcast"
        mention = "#a1-podcast"
        async def send(self, content):
            posted["content"] = content
            return FakeMsg()

    eid = database.create_episode("A1", "Great Ep", "solo_ai",
                                  description="desc", audio_url="https://cdn/a.mp3")

    async def fake_ensure(guild, level):
        return FakeChan()
    import src.bot as b
    orig = b._ensure_podcast_channel
    b._ensure_podcast_channel = fake_ensure
    try:
        msg = await b._publish_episode_text(guild=object(), episode_id=eid)
    finally:
        b._ensure_podcast_channel = orig

    assert "Published" in msg
    ep = database.get_episode(eid)
    assert ep["published"] == 1
    assert ep["audio_message_id"] == "4242"
    assert "Great Ep" in posted["content"]
    assert posted["reacted"] == "✅"
