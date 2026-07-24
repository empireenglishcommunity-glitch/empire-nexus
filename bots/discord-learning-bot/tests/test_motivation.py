"""Tests for src/motivation.py — Hafiz (حافظ) AI motivational auto-replies.

Phase F (E4, owner feedback #7): "every reply is different -- no reply is
similar to another reply... the goal is to keep them motivated and
engaged." These tests pin: uniqueness (no repeat within a channel's
recent window), post-type tailoring (text vs voice), throttling, silence
on empty/near-empty text with no attachment, and that the module never
manufactures a "correction" (R4.5 — encouragement only).
"""
from unittest.mock import patch

import pytest

from src import motivation


# ============================================================
#  BASIC BEHAVIOR
# ============================================================

@pytest.mark.asyncio
async def test_maybe_reply_returns_none_for_near_empty_text_with_no_attachment():
    """A lone emoji or a couple of characters shouldn't trigger a reply —
    avoids reacting to noise (R4.3 spirit: don't spam on nothing)."""
    with patch.object(motivation.ai_engine, "_call_llm", return_value=None):
        reply = await motivation.maybe_reply(
            "u1", "Alice", 111, "text", "👍", has_attachment=False
        )
    assert reply is None


@pytest.mark.asyncio
async def test_maybe_reply_returns_a_reply_for_a_real_sentence():
    with patch.object(motivation.ai_engine, "_call_llm", return_value="Great sentence, keep going!"):
        reply = await motivation.maybe_reply(
            "u1", "Alice", 111, "text", "I go to school every day.", has_attachment=False
        )
    assert reply == "Great sentence, keep going!"


@pytest.mark.asyncio
async def test_maybe_reply_returns_a_reply_for_a_voice_post_even_with_no_text():
    """A #showcase audio upload usually has empty message content — the
    attachment itself is the "content", so it must still trigger a reply."""
    with patch.object(motivation.ai_engine, "_call_llm", return_value="Love hearing your voice!"):
        reply = await motivation.maybe_reply(
            "u1", "Alice", 222, "voice", "", has_attachment=True
        )
    assert reply == "Love hearing your voice!"


# ============================================================
#  THROTTLE (R4.3 — avoid spamming during bursts)
# ============================================================

@pytest.mark.asyncio
async def test_second_message_within_throttle_window_gets_no_reply():
    with patch.object(motivation.ai_engine, "_call_llm", return_value="Nice one!"):
        first = await motivation.maybe_reply("u1", "Alice", 111, "text", "Hello there.", False)
        second = await motivation.maybe_reply("u1", "Alice", 111, "text", "Another one.", False)
    assert first is not None
    assert second is None


@pytest.mark.asyncio
async def test_throttle_is_per_student_not_global():
    """Two different students posting in the same channel within the
    throttle window must BOTH get a reply — the throttle is per
    (student, channel), not a channel-wide lock."""
    with patch.object(motivation.ai_engine, "_call_llm", return_value="Nice one!"):
        r1 = await motivation.maybe_reply("u1", "Alice", 111, "text", "Hello.", False)
        r2 = await motivation.maybe_reply("u2", "Bob", 111, "text", "Hi there.", False)
    assert r1 is not None
    assert r2 is not None


@pytest.mark.asyncio
async def test_throttle_is_per_channel_not_global_for_same_student():
    """The same student posting in two different channels (e.g.
    text-practice then showcase) must get a reply in each — the throttle
    doesn't block a different channel."""
    with patch.object(motivation.ai_engine, "_call_llm", return_value="Nice one!"):
        r1 = await motivation.maybe_reply("u1", "Alice", 111, "text", "Hello.", False)
        r2 = await motivation.maybe_reply("u1", "Alice", 222, "voice", "", True)
    assert r1 is not None
    assert r2 is not None


def test_throttle_expires_after_window():
    """Directly exercise the throttle helpers (no real sleep in a test)."""
    import datetime
    motivation._record_reply("u1", 111)
    assert motivation._is_throttled("u1", 111) is True
    # Simulate the window having passed by backdating the recorded time.
    motivation._last_reply_time[("u1", 111)] = (
        datetime.datetime.now() - datetime.timedelta(seconds=motivation.THROTTLE_SECONDS + 1)
    )
    assert motivation._is_throttled("u1", 111) is False


# ============================================================
#  UNIQUENESS (R4.1/R4.2 — "no reply is similar to another reply")
# ============================================================

@pytest.mark.asyncio
async def test_fallback_avoids_repeating_the_last_reply_in_the_same_channel():
    """When the AI is unavailable (fallback path), the picked fallback
    must not be the same message that was JUST sent in this channel, as
    long as other options exist in the pool."""
    with patch.object(motivation.ai_engine, "_call_llm", return_value=None):
        seen = set()
        for i in range(6):
            reply = await motivation.maybe_reply(
                f"u{i}", f"Student{i}", 111, "text", f"Sentence number {i}.", False
            )
            assert reply not in seen or len(seen) >= len(motivation._TEXT_FALLBACKS)
            seen.add(reply)
    # With a pool of 15 and only 6 draws avoiding the ring, we should see
    # meaningfully more than 1 distinct message (not literally guaranteed
    # non-repeating forever, but the ring actively steers away from the
    # most recent ones).
    assert len(seen) >= 4


@pytest.mark.asyncio
async def test_ai_prompt_includes_recent_replies_to_avoid_when_ring_nonempty():
    """The AI prompt must actually carry a "don't repeat these" hint once
    the channel has recent history — this is the mechanism the design
    doc calls for (non-repetition ring + hint to the LLM)."""
    motivation._remember_reply(111, "Great job on that sentence!")
    captured_prompts = []

    async def fake_call_llm(prompt, temperature=0.8):
        captured_prompts.append(prompt)
        return "A brand new distinct reply."

    with patch.object(motivation.ai_engine, "_call_llm", side_effect=fake_call_llm):
        await motivation.maybe_reply("u1", "Alice", 111, "text", "Another sentence here.", False)

    assert captured_prompts, "AI should have been called"
    assert "Great job on that sentence!" in captured_prompts[0]


@pytest.mark.asyncio
async def test_ai_prompt_has_no_avoid_hint_for_a_fresh_channel():
    """A channel with no reply history yet shouldn't reference a
    nonexistent history in the prompt."""
    captured_prompts = []

    async def fake_call_llm(prompt, temperature=0.8):
        captured_prompts.append(prompt)
        return "First ever reply here."

    with patch.object(motivation.ai_engine, "_call_llm", side_effect=fake_call_llm):
        await motivation.maybe_reply("u1", "Alice", 999, "text", "Fresh sentence.", False)

    assert "Do NOT reuse" not in captured_prompts[0]


# ============================================================
#  POST-TYPE TAILORING (R4.2 — "fit the voice record or the written sentence")
# ============================================================

@pytest.mark.asyncio
async def test_ai_prompt_differs_for_text_vs_voice_post_type():
    captured_prompts = []

    async def fake_call_llm(prompt, temperature=0.8):
        captured_prompts.append(prompt)
        return "A reply."

    with patch.object(motivation.ai_engine, "_call_llm", side_effect=fake_call_llm):
        await motivation.maybe_reply("u1", "Alice", 111, "text", "A written sentence.", False)
        await motivation.maybe_reply("u2", "Bob", 222, "voice", "", True)

    text_prompt, voice_prompt = captured_prompts
    assert "wrote a sentence" in text_prompt
    assert "recorded themselves speaking" in voice_prompt


def test_fallback_pools_are_distinct_for_text_and_voice():
    """The two fallback pools shouldn't just be the same messages
    reused — they're written to fit the post type (R4.2)."""
    assert set(motivation._TEXT_FALLBACKS).isdisjoint(set(motivation._VOICE_FALLBACKS))
    assert len(motivation._TEXT_FALLBACKS) >= 10
    assert len(motivation._VOICE_FALLBACKS) >= 10


# ============================================================
#  NO CORRECTIONS (R4.5 — encouragement and engagement only)
# ============================================================

def test_fallback_messages_contain_no_correction_language():
    """A cheap but real guardrail: none of the hardcoded fallback
    messages should contain correction-flavored words. (The AI path's
    correction-free behavior is enforced by the prompt instructions,
    which can't be unit-tested against a real LLM here, but the
    deterministic fallback pool — which WILL be shown to real students
    whenever the AI is unavailable — must never slip in a correction.)"""
    banned_words = ("mistake", "wrong", "error", "incorrect", "should have",
                    "actually you", "correction", "fix your")
    for pool in (motivation._TEXT_FALLBACKS, motivation._VOICE_FALLBACKS):
        for msg in pool:
            lowered = msg.lower()
            for banned in banned_words:
                assert banned not in lowered, f"Fallback contains correction language: {msg!r}"


@pytest.mark.asyncio
async def test_ai_prompt_explicitly_forbids_corrections():
    captured_prompts = []

    async def fake_call_llm(prompt, temperature=0.8):
        captured_prompts.append(prompt)
        return "A reply."

    with patch.object(motivation.ai_engine, "_call_llm", side_effect=fake_call_llm):
        await motivation.maybe_reply("u1", "Alice", 111, "text", "A written sentence.", False)

    assert "Do NOT correct" in captured_prompts[0]


# ============================================================
#  ROBUSTNESS — AI failure/garbage output falls back cleanly
# ============================================================

@pytest.mark.asyncio
async def test_falls_back_when_ai_returns_none():
    with patch.object(motivation.ai_engine, "_call_llm", return_value=None):
        reply = await motivation.maybe_reply("u1", "Alice", 111, "text", "Hello world today.", False)
    assert reply in motivation._TEXT_FALLBACKS


@pytest.mark.asyncio
async def test_falls_back_when_ai_output_is_too_long():
    too_long = "x" * (motivation.MAX_REPLY_LEN + 50)
    with patch.object(motivation.ai_engine, "_call_llm", return_value=too_long):
        reply = await motivation.maybe_reply("u1", "Alice", 111, "text", "Hello world today.", False)
    assert reply in motivation._TEXT_FALLBACKS


@pytest.mark.asyncio
async def test_falls_back_when_ai_raises_exception():
    async def boom(prompt, temperature=0.8):
        raise RuntimeError("network blip")

    with patch.object(motivation.ai_engine, "_call_llm", side_effect=boom):
        reply = await motivation.maybe_reply("u1", "Alice", 111, "text", "Hello world today.", False)
    assert reply in motivation._TEXT_FALLBACKS


@pytest.mark.asyncio
async def test_ai_reply_is_stripped_of_surrounding_quotes():
    with patch.object(motivation.ai_engine, "_call_llm", return_value='"Great sentence!"'):
        reply = await motivation.maybe_reply("u1", "Alice", 111, "text", "Hello world today.", False)
    assert reply == "Great sentence!"



# ============================================================
#  FEATURE FLAG (R4.4 — behind a flag, default off)
# ============================================================

def test_hafiz_motivation_flag_registered_and_defaults_off():
    """R4.4: the feature must be behind an on/off flag, and per the
    design doc ("default off until verified") it must sync in as
    disabled for everyone until an owner explicitly turns it on."""
    from src import database, flag_registry
    entry = next((e for e in flag_registry.REGISTRY if e[0] == "hafiz_motivation"), None)
    assert entry is not None, "hafiz_motivation must be registered in flag_registry.REGISTRY"
    _, _, initiative, default_enabled = entry
    assert default_enabled is False
    assert initiative in flag_registry.INITIATIVES

    database.sync_flag_registry()
    assert database.is_feature_enabled("hafiz_motivation") is False
    assert database.is_feature_enabled("hafiz_motivation", "any_student_id") is False


def test_hafiz_motivation_can_be_enabled_for_a_beta_allowlist():
    """Owner should be able to test with a small allowlist before a full
    rollout, same pattern as every other flag."""
    from src import database
    database.sync_flag_registry()
    database.set_feature_flag("hafiz_motivation", True, allowed_ids="tester_1,tester_2")
    assert database.is_feature_enabled("hafiz_motivation", "tester_1") is True
    assert database.is_feature_enabled("hafiz_motivation", "some_other_student") is False
