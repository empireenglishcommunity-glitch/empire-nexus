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
    with patch.object(sawt_script.ai_engine, "_call_llm",
                      AsyncMock(return_value=fake)):
        out = await sawt_script.generate_script("Coffee", "A1", "solo_ai")
    assert out == fake


@pytest.mark.asyncio
async def test_generate_script_none_when_llm_empty():
    with patch.object(sawt_script.ai_engine, "_call_llm",
                      AsyncMock(return_value="")):
        assert await sawt_script.generate_script("Coffee", "A1", "solo_ai") is None


@pytest.mark.asyncio
async def test_generate_script_none_when_llm_errors():
    with patch.object(sawt_script.ai_engine, "_call_llm",
                      AsyncMock(side_effect=RuntimeError("boom"))):
        assert await sawt_script.generate_script("Coffee", "A1", "solo_ai") is None


@pytest.mark.asyncio
async def test_generate_script_rejects_invalid_format():
    with pytest.raises(ValueError):
        await sawt_script.generate_script("Coffee", "A1", "not_a_format")


# ── command registration ─────────────────────────────────────────────────────
def test_generate_script_command_registered():
    from src import bot as botmod
    assert botmod.bot.tree.get_command("generate-script") is not None
