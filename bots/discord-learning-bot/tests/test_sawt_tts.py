"""Tests for Sawt Phase 3 — script parsing, voice mapping, and the graceful
engine-unavailable degrade (the bot host has no TTS engine)."""
import pytest

from src import sawt_tts, bot as botmod, database


SCRIPT = """Host (you): Hello, welcome! [PAUSE]
AI co-host: Hi there!

━━━━━━━━
AI co-host: coffee (قهوة) is a hot drink.
AI guest 2: My take on that...
Host (you): Right, exactly."""


# ── parse_script ─────────────────────────────────────────────────────────────
def test_parse_script_extracts_speaker_lines_and_skips_noise():
    segs = sawt_tts.parse_script(SCRIPT)
    assert len(segs) == 5                       # blank line + ━━━ rule skipped
    assert segs[0] == ("Host (you)", "Hello, welcome! [PAUSE]")
    assert segs[1][0] == "AI co-host"


def test_parse_script_empty():
    assert sawt_tts.parse_script("") == []
    assert sawt_tts.parse_script("no speaker labels here") == []


# ── voice_for (co-host must NOT map to owner) ────────────────────────────────
def test_voice_mapping():
    assert sawt_tts.voice_for("Host (you)")["role"] == "owner"
    assert sawt_tts.voice_for("Owner")["role"] == "owner"
    assert sawt_tts.voice_for("AI co-host")["role"] == "cohost_f"   # not owner!
    assert sawt_tts.voice_for("AI host")["role"] == "cohost_m"
    assert sawt_tts.voice_for("AI guest 2")["role"] == "cohost_m"
    # unknown label falls back to a co-host voice, never crashes
    assert sawt_tts.voice_for("Random Person")["engine"] == "kokoro"


def test_owner_uses_clone_engine():
    assert sawt_tts.voice_for("Host (you)")["engine"] == "clone"


# ── plan_episode ─────────────────────────────────────────────────────────────
def test_plan_episode_counts_and_flags_clone():
    plan = sawt_tts.plan_episode(SCRIPT)
    assert plan["segment_count"] == 5
    assert plan["needs_clone"] is True
    assert plan["voices"]["owner"] == 2


# ── engine availability + graceful assemble ──────────────────────────────────
def test_engine_unavailable_on_bot_host():
    # kokoro_onnx / chatterbox are not installed in the bot/test env.
    assert sawt_tts.engine_available() is False


@pytest.mark.asyncio
async def test_assemble_degrades_gracefully():
    res = await sawt_tts.assemble_episode(SCRIPT)
    assert res["ok"] is False
    assert res["reason"] == "engine_unavailable"
    assert res["segment_count"] == 5


@pytest.mark.asyncio
async def test_assemble_empty_script():
    res = await sawt_tts.assemble_episode("")
    assert res["ok"] is False and res["reason"] == "empty_script"


# ── /generate-audio command surface ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_generate_audio_text_requires_script():
    eid = database.create_episode("A1", "No Script", "solo_ai")
    msg = await botmod._generate_audio_text(guild=None, episode_id=eid)
    assert "no script" in msg.lower()


@pytest.mark.asyncio
async def test_generate_audio_text_shows_plan_and_offline_guidance():
    eid = database.create_episode("A1", "Has Script", "solo_ai", script=SCRIPT)
    msg = await botmod._generate_audio_text(guild=None, episode_id=eid)
    assert "Audio plan" in msg
    assert "Segments" in msg
    # graceful offline guidance (no engine on the bot host)
    assert "offline" in msg.lower()


def test_generate_audio_commands_registered():
    assert botmod.bot.tree.get_command("generate-audio") is not None
    assert botmod.bot.get_command("generate-audio") is not None
    assert "generate-audio" in botmod._admin_command_names()
