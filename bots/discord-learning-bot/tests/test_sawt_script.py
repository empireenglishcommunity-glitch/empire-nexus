"""Tests for Podcast Studio (Sawt) Phase 2 — LLM script generation.

Covers the level-graded prompt builder and generate_script (with the LLM mocked),
plus the sawt_script_gen flag registration.
"""
from unittest.mock import AsyncMock, patch

import pytest

from src import sawt_script, config, flag_registry


# ── flag ─────────────────────────────────────────────────────────────────────
def test_sawt_script_gen_flag_registered_default_off():
    reg = {e[0]: e for e in flag_registry.REGISTRY}
    assert "sawt_script_gen" in reg
    assert reg["sawt_script_gen"][3] is False
    assert reg["sawt_script_gen"][2] == "sawt"


# ── prompt builder (level grading) ───────────────────────────────────────────
def test_prompt_grades_arabic_by_level():
    a1 = sawt_script.build_prompt("Ordering coffee", "A1", "solo_ai")
    assert "40%" in a1                      # A1 = heavy Arabic support
    assert "Beginner" in a1                 # level name present
    c2 = sawt_script.build_prompt("Climate policy", "C2", "ai_only")
    assert "English only" in c2             # C2 = no Arabic


def test_prompt_includes_format_speakers_and_topic():
    p = sawt_script.build_prompt("Daily routines", "B1", "owner_group")
    assert "Daily routines" in p
    assert "owner_group" in p
    # owner_group line-up includes the host + two AI guests
    assert "AI guest 1" in p and "AI guest 2" in p


def test_prompt_uses_legacy_level_mapping():
    # Legacy L0 → A1 profile (40% Arabic).
    assert "40%" in sawt_script.build_prompt("x", "L0", "solo_ai")


# ── generate_script (LLM mocked) ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_generate_script_returns_llm_text():
    fake = "Host (you): Hello!\nAI co-host: Hi there!"
    with patch.object(sawt_script, "_call_llm_text",
                      AsyncMock(return_value=fake)):
        out = await sawt_script.generate_script("Coffee", "A1", "solo_ai")
    assert out == fake


@pytest.mark.asyncio
async def test_generate_script_none_when_llm_empty():
    with patch.object(sawt_script, "_call_llm_text",
                      AsyncMock(return_value="")):
        assert await sawt_script.generate_script("Coffee", "A1", "solo_ai") is None


@pytest.mark.asyncio
async def test_generate_script_none_when_llm_errors():
    with patch.object(sawt_script, "_call_llm_text",
                      AsyncMock(side_effect=RuntimeError("boom"))):
        assert await sawt_script.generate_script("Coffee", "A1", "solo_ai") is None


@pytest.mark.asyncio
async def test_generate_script_rejects_invalid_format():
    with pytest.raises(ValueError):
        await sawt_script.generate_script("Coffee", "A1", "not_a_format")


@pytest.mark.asyncio
async def test_script_llm_call_does_not_force_json(monkeypatch):
    """The script path must NOT reuse the JSON-forcing system prompt (which
    mangles a free-form script). Its Groq system message is a scriptwriter one."""
    from src import config
    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")
    captured = {}

    class FakeResult:
        ok = True
        text = "Host: hi"
        status = 200

    async def fake_chat(payload, timeout_seconds):
        captured["payload"] = payload
        return FakeResult()

    from src import groq_client
    monkeypatch.setattr(groq_client, "chat_completion", fake_chat)

    out = await sawt_script._call_llm_text("prompt")
    assert out == "Host: hi"
    sys_msg = captured["payload"]["messages"][0]["content"]
    # It must NOT be the ai_engine JSON-forcing prompt, and must be scriptwriter-y.
    assert "Always return valid JSON" not in sys_msg
    assert "return only the script" in sys_msg.lower()
    assert captured["payload"]["model"] == config.GROQ_MODEL


# ── command registration ─────────────────────────────────────────────────────
def test_generate_script_command_registered():
    from src import bot as botmod
    assert botmod.bot.tree.get_command("generate-script") is not None
