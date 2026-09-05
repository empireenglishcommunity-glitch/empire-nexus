"""Tests for Empire Chronicles daily-story generation + vote data model."""
import pytest

from src import sawt_story, database, flag_registry


# ── story generation helpers (pure, no LLM) ─────────────────────────────────
def test_build_story_prompt_opening_vs_continuation():
    opening = sawt_story.build_story_prompt("", "", 1)
    assert "OPENING" in opening
    cont = sawt_story.build_story_prompt("Maya found a key.", "open the door", 5)
    assert "open the door" in cont and "episode 5" in cont
    assert "Maya found a key." in cont


def test_extract_json_tolerates_code_fences():
    raw = ('```json\n{"title":"The Key","script":"Narrator: Welcome.\\n'
           'Maya: I found it.\\nLeo: Careful.\\nNarrator: The end. [PAUSE 2s]",'
           '"recap":"Maya found a key.","vote_a":"Open it","vote_b":"Hide it"}\n```')
    d = sawt_story._extract_json(raw)
    assert d and d["title"] == "The Key"
    assert sawt_story._valid_episode(d)


def test_valid_episode_rejects_thin_or_malformed():
    assert not sawt_story._valid_episode(None)
    assert not sawt_story._valid_episode({"title": "t"})
    # Too few speaker lines.
    assert not sawt_story._valid_episode(
        {"title": "t", "script": "Narrator: hi.", "vote_a": "a", "vote_b": "b"})


def test_story_cast_matches_renderer_characters():
    # The cast names the generator uses must be voiced by the renderer.
    assert sawt_story.STORY_CAST == ["Narrator", "Maya", "Leo"]


# ── vote data model ─────────────────────────────────────────────────────────
def _make_episode():
    return database.create_episode(
        "A2", "Chronicles Test", "ai_only",
        description="Empire Chronicles episode 1", audio_url="/x.mp3")


def test_record_vote_dedup_and_tally():
    database.init_db()
    eid = _make_episode()
    assert database.record_vote("v1", eid, "A") is True
    assert database.record_vote("v2", eid, "B") is True
    # A student's first vote wins; a second is ignored.
    assert database.record_vote("v1", eid, "B") is False
    assert database.vote_counts(eid) == {"A": 1, "B": 1}


def test_record_vote_rejects_bad_choice():
    database.init_db()
    eid = _make_episode()
    assert database.record_vote("v9", eid, "X") is False
    assert database.record_vote("v9", eid, "") is False
    assert database.vote_counts(eid) == {"A": 0, "B": 0}


def test_daily_story_flag_registered_and_defaults_off():
    entry = next((f for f in flag_registry.REGISTRY
                  if f[0] == "sawt_daily_story"), None)
    assert entry is not None
    assert entry[3] is False          # default OFF until the pipeline is live



# ── dedicated podcast channel (setup / resolution) ──────────────────────────
from src import bot as botmod          # noqa: E402


def test_setup_and_reveal_podcast_commands_registered():
    assert botmod.bot.tree.get_command("setup-podcast") is not None
    assert botmod.bot.tree.get_command("reveal-podcast") is not None
    assert botmod.bot.tree.get_command("story-status") is not None
    assert botmod.bot.tree.get_command("story-approve") is not None


def test_channel_topic_and_intro_describe_student_value():
    """The channel's topic + pinned intro must explain WHY it exists and how it
    helps students learn (owner directive: 'description of its value')."""
    topic = botmod._STORY_CHANNEL_TOPIC.lower()
    assert "empire chronicles" in topic
    assert "vote" in topic
    # Names at least one concrete learning benefit.
    assert any(w in topic for w in ("listening", "pronunciation", "vocabulary"))
    intro = botmod._STORY_CHANNEL_INTRO.lower()
    assert "how it works" in intro
    assert "🅰️" in botmod._STORY_CHANNEL_INTRO and "🅱️" in botmod._STORY_CHANNEL_INTRO
    # Explicitly lists listening + pronunciation + vocabulary as benefits.
    for benefit in ("listening", "pronunciation", "vocabulary"):
        assert benefit in intro


class _FakeGuild:
    def __init__(self, channels=None):
        self._by_id = {c.id: c for c in (channels or [])}
        self.text_channels = list(channels or [])

    def get_channel(self, cid):
        return self._by_id.get(cid)


class _FakeTextChannel:
    def __init__(self, cid, name):
        self.id = cid
        self.name = name


def test_story_channel_resolves_by_stored_id_then_name():
    database.init_db()
    # No stored id, resolve by name → stores the id for next time.
    ch = _FakeTextChannel(555, botmod.config.SAWT_STORY_CHANNEL)
    guild = _FakeGuild([ch])
    assert database.get_setting(botmod._STORY_CHANNEL_KEY, "") == ""
    resolved = botmod._story_channel(guild)
    assert resolved is ch
    assert database.get_setting(botmod._STORY_CHANNEL_KEY, "") == "555"
    # Now stored — resolves by id even if the name changed (rename-safe).
    ch.name = "renamed-podcast"
    guild2 = _FakeGuild([ch])
    assert botmod._story_channel(guild2) is ch
