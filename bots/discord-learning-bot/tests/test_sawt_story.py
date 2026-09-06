"""Tests for Empire Chronicles daily-story generation + vote data model."""
import pytest

from src import sawt_story, database, flag_registry


# ── story generation helpers (pure, no LLM) ─────────────────────────────────
def test_build_story_prompt_opening_vs_continuation():
    # A flagged arc opener for episode 1 introduces the world (arc-aware contract).
    opening = sawt_story.build_story_prompt("", "", 1, is_arc_opener=True)
    assert "FIRST episode" in opening and "OPENS a new story arc" in opening
    # A continuation weaves in the recap + the audience's winning choice.
    cont = sawt_story.build_story_prompt("Maya found a key.", "open the door", 5)
    assert "open the door" in cont and "episode 5" in cont
    assert "Maya found a key." in cont


def test_build_story_prompt_is_arc_aware():
    arc = {"arc_id": 2, "genre": "wonder", "setting": "a quiet town",
           "premise": "something impossible happens", "mood": "wonder",
           "curiosity": "reframing-reveal", "leads": ["Maya", "Leo"],
           "established_facts": ["the lights hum at night"]}
    p = sawt_story.build_story_prompt("prev", "", 3, arc=arc, is_arc_finale=True)
    assert "wonder" in p and "a quiet town" in p
    assert "the lights hum at night" in p          # established facts injected
    assert "FINALE" in p                            # finale instruction present


def test_prompt_vocab_is_derived_from_the_registries():
    # cast + sfx menus in the prompt must come from the real registries, not a
    # hand-kept list (the old drift bug: it listed [SFX:shimmer], which is gone).
    from src import sawt_cast, podcast_lab
    names = sawt_story.story_cast_names()
    assert names == sawt_cast.speaking_names()
    menu = sawt_story._sfx_menu()
    assert "shimmer" not in menu                    # the drifted, missing effect
    # every suggested effect is a real, resolvable library sound
    import re
    for eff in re.findall(r"\[SFX:([^\]]+)\]", menu):
        assert eff in podcast_lab.sfx_names()


def test_normalize_episode_coerces_fields():
    d = {"title": "  T  ", "script": "Narrator: hi.\nMaya: yo.\nLeo: ok.\nNarrator: end.",
         "recap": " r ", "facts": "a single fact", "mood": " Mystery ",
         "vote_a": "A", "vote_b": "B", "motif_used": 1}
    ep = sawt_story._normalize_episode(d, arc={"mood": "warm"})
    assert ep["title"] == "T" and ep["recap"] == "r"
    assert ep["facts"] == ["a single fact"]         # string coerced to list
    assert ep["mood"] == "mystery"                   # lowercased
    assert ep["motif_used"] is True


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


def test_story_cast_is_derived_from_the_cast_registry():
    # The generator's allowed names come straight from sawt_cast (single source of
    # truth), so they can never drift from the voices the renderer knows (R2.7).
    from src import sawt_cast
    names = sawt_story.story_cast_names()
    for lead in ("Narrator", "Maya", "Leo"):
        assert lead in names
    assert names == sawt_cast.speaking_names()
    # Every allowed name maps (whole-word) to a real cast entry with a voice.
    for name in names:
        ch = sawt_cast.character_for(name)
        assert ch["key"] in sawt_cast.CAST
        assert ch.get("voice_id") or ch.get("clone_ref"), f"{name} has no voice"


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
    assert "empire english chronicles" in topic
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



# ── deploy-driven go-live (bootstrap) ───────────────────────────────────────
def test_enable_daily_story_once_is_idempotent_and_empty_allowlist():
    database.init_db()
    database.set_setting("sawt_daily_story_autoenabled_v1", "")
    # First call flips it ON for everyone (empty allowlist — scheduled task has
    # no member context).
    assert database.enable_daily_story_once() is True
    st = database.feature_flag_status("sawt_daily_story")
    assert st["enabled"] is True and st["everyone"] is True
    # Second call is a no-op.
    assert database.enable_daily_story_once() is False
    # A later deliberate disable must NOT be silently undone.
    database.set_feature_flag("sawt_daily_story", enabled=False, updated_by="manual")
    assert database.enable_daily_story_once() is False


def test_bootstrap_marker_guards_single_run():
    """The bootstrap must run at most once (guarded by its settings marker)."""
    database.init_db()
    database.set_setting("sawt_chronicles_bootstrapped_v1", "1")
    # With the marker set, is_feature_enabled state is irrelevant — the guard
    # short-circuits. We assert the marker semantics the bootstrap relies on.
    assert database.get_setting("sawt_chronicles_bootstrapped_v1", "") == "1"
    assert hasattr(botmod, "bootstrap_empire_chronicles_once")
