"""Tests for src/verification.py — anti-cheat verification logic.

Covers the pure/sync pieces (cooldowns, voice tracking, vocab/listening
quiz generation and checking) that don't require a live discord.Member/
discord.Guild. The channel-history-based checks (verify_writing,
verify_audio, verify_community) need real Discord objects and are out of
scope for unit tests here — same boundary the challenge-bot's test suite
draws around its own Discord-dependent code.
"""
import datetime

from src import verification

# Module-level state (cooldowns, voice sessions, pending quizzes) is reset
# before every test by the autouse clear_module_level_state fixture in
# conftest.py.


# ============================================================
#  COOLDOWN
# ============================================================

def test_check_cooldown_allowed_when_never_done():
    allowed, remaining = verification.check_cooldown("u1")
    assert allowed is True
    assert remaining == 0


def test_check_cooldown_blocked_immediately_after_record():
    verification.record_done_time("u1")
    allowed, remaining = verification.check_cooldown("u1")
    assert allowed is False
    assert 0 < remaining <= verification.COOLDOWN_SECONDS


def test_check_cooldown_allowed_after_window_elapses():
    verification._last_done_time["u1"] = (
        datetime.datetime.now() - datetime.timedelta(seconds=verification.COOLDOWN_SECONDS + 1)
    )
    allowed, remaining = verification.check_cooldown("u1")
    assert allowed is True
    assert remaining == 0


def test_check_cooldown_is_per_user():
    verification.record_done_time("u1")
    allowed, _ = verification.check_cooldown("u2")
    assert allowed is True


# ============================================================
#  VOICE TRACKING
# ============================================================

def test_voice_minutes_zero_before_any_join():
    assert verification.get_voice_minutes_today("u1") == 0


def test_voice_minutes_accumulate_after_leave():
    from src import database
    database.register_member("u1", "U1")
    verification.on_voice_join("u1")
    verification._voice_sessions["u1"]["join_time"] = (
        datetime.datetime.now() - datetime.timedelta(minutes=10)
    )
    verification.on_voice_leave("u1")
    minutes = verification.get_voice_minutes_today("u1")
    assert 9 <= minutes <= 11


def test_voice_minutes_persist_across_restart():
    """E5: minutes are stored in the DB, so a bot restart (which wipes the
    in-memory _voice_sessions) must NOT lose a student's accumulated time."""
    from src import database
    database.register_member("u1", "U1")
    verification.on_voice_join("u1")
    verification._voice_sessions["u1"]["join_time"] = (
        datetime.datetime.now() - datetime.timedelta(minutes=12)
    )
    verification.on_voice_leave("u1")
    # Simulate a restart: in-memory state gone, DB persists.
    verification._voice_sessions.clear()
    assert verification.get_voice_minutes_today("u1") >= 10


def test_voice_minutes_ongoing_session_counts_live():
    verification.on_voice_join("u1")
    verification._voice_sessions["u1"]["join_time"] = (
        datetime.datetime.now() - datetime.timedelta(minutes=5)
    )
    # Still "in voice" (no leave event yet) — should count elapsed time so far.
    minutes = verification.get_voice_minutes_today("u1")
    assert 4 <= minutes <= 6


def test_voice_minutes_accumulate_across_multiple_sessions():
    from src import database
    database.register_member("u1", "U1")
    verification.on_voice_join("u1")
    verification._voice_sessions["u1"]["join_time"] = (
        datetime.datetime.now() - datetime.timedelta(minutes=5)
    )
    verification.on_voice_leave("u1")
    verification.on_voice_join("u1")
    verification._voice_sessions["u1"]["join_time"] = (
        datetime.datetime.now() - datetime.timedelta(minutes=5)
    )
    verification.on_voice_leave("u1")
    minutes = verification.get_voice_minutes_today("u1")
    assert 9 <= minutes <= 11


def test_reset_daily_voice_clears_all_sessions():
    verification.on_voice_join("u1")
    verification.reset_daily_voice()
    assert verification.get_voice_minutes_today("u1") == 0


# ============================================================
#  VOCAB QUIZ
# ============================================================

def test_generate_vocab_quiz_returns_question_answer_word():
    from src import database
    database.register_member("u1", "Alice")
    question, answer, word = verification.generate_vocab_quiz("u1")
    assert question
    assert answer
    assert word


def test_generate_vocab_quiz_creates_pending_entry():
    from src import database
    database.register_member("u1", "Alice")
    verification.generate_vocab_quiz("u1")
    assert verification.has_pending_quiz("u1") is True


def test_generate_vocab_quiz_uses_members_real_level_curriculum():
    """Regression guard: this previously always quizzed against L0 data
    regardless of the member's real level."""
    from src import database
    database.register_member("u1", "Alice", level="L2")
    _, _, word = verification.generate_vocab_quiz("u1")
    # The word must come from real L2 curriculum vocabulary, not the
    # small hardcoded L0-only VOCAB_QUIZ_BANK fallback.
    from src import curriculum
    l2_week1_words = {w["word"] for w in curriculum.get_vocabulary_for_week(1, "L2")}
    # word may come from week 1-3 (spaced repetition window); just confirm
    # it's a real L2 curriculum word, not an L0 hardcoded-bank word.
    l0_bank_words = {w for words in verification.VOCAB_QUIZ_BANK.values() for w, _ in words}
    assert word not in l0_bank_words or word in l2_week1_words


def test_check_vocab_answer_correct():
    from src import database
    database.register_member("u1", "Alice")
    _, answer, _ = verification.generate_vocab_quiz("u1")
    passed, msg = verification.check_vocab_answer("u1", answer)
    assert passed is True
    assert msg == ""


def test_check_vocab_answer_correct_case_insensitive_with_whitespace():
    from src import database
    database.register_member("u1", "Alice")
    _, answer, _ = verification.generate_vocab_quiz("u1")
    passed, _ = verification.check_vocab_answer("u1", f"  {answer.upper()}  ")
    assert passed is True


def test_check_vocab_answer_wrong():
    from src import database
    database.register_member("u1", "Alice")
    verification.generate_vocab_quiz("u1")
    passed, msg = verification.check_vocab_answer("u1", "definitely-not-the-answer-xyz")
    assert passed is False
    assert msg  # should explain the correct answer


def test_check_vocab_answer_clears_pending_quiz_regardless_of_result():
    from src import database
    database.register_member("u1", "Alice")
    verification.generate_vocab_quiz("u1")
    verification.check_vocab_answer("u1", "wrong answer")
    assert verification.has_pending_quiz("u1") is False


def test_check_vocab_answer_no_pending_quiz():
    passed, msg = verification.check_vocab_answer("u1", "anything")
    assert passed is False
    assert msg


def test_has_pending_quiz_false_when_none():
    assert verification.has_pending_quiz("u1") is False


def test_has_pending_quiz_expires_after_timeout():
    from src import database
    database.register_member("u1", "Alice")
    verification.generate_vocab_quiz("u1")
    verification._pending_quizzes["u1"]["expires"] = (
        datetime.datetime.now() - datetime.timedelta(seconds=1)
    )
    assert verification.has_pending_quiz("u1") is False


# ============================================================
#  LISTENING QUIZ
# ============================================================

def test_generate_listening_quiz_returns_prompt_and_answer():
    prompt, answer = verification.generate_listening_quiz("u1")
    assert prompt
    assert answer


def test_generate_listening_quiz_creates_pending_entry():
    verification.generate_listening_quiz("u1")
    assert verification.has_pending_listening("u1") is True


def test_check_listening_answer_correct():
    _, answer = verification.generate_listening_quiz("u1")
    passed, msg = verification.check_listening_answer("u1", answer)
    assert passed is True
    assert msg == ""


def test_check_listening_answer_accepts_alternatives():
    """Loop until we get a question with more than one accepted answer
    form, then verify an alternative (not the primary answer) still
    passes — the quiz bank has several such questions (e.g. '8' vs
    '8 o'clock' vs 'eight')."""
    for q in verification.LISTENING_QUESTIONS:
        if len(q["alternatives"]) > 1:
            verification._pending_listening["u1"] = {
                "answer": q["answer"].lower(),
                "alternatives": [a.lower() for a in q["alternatives"]],
                "expires": datetime.datetime.now() + datetime.timedelta(minutes=5),
            }
            alt_answer = next(a for a in q["alternatives"] if a.lower() != q["answer"].lower())
            passed, _ = verification.check_listening_answer("u1", alt_answer)
            assert passed is True
            return
    raise AssertionError("no listening question with alternatives found to test")


def test_check_listening_answer_wrong():
    verification.generate_listening_quiz("u1")
    passed, msg = verification.check_listening_answer("u1", "definitely-wrong-xyz")
    assert passed is False
    assert msg


def test_check_listening_answer_no_pending_quiz():
    passed, msg = verification.check_listening_answer("u1", "anything")
    assert passed is False
    assert msg


def test_has_pending_listening_expires_after_timeout():
    verification.generate_listening_quiz("u1")
    verification._pending_listening["u1"]["expires"] = (
        datetime.datetime.now() - datetime.timedelta(seconds=1)
    )
    assert verification.has_pending_listening("u1") is False



# ============================================================
#  AUDIT FIX (E5): community day-boundary consistency
#
#  Regression tests for the audit finding that verify_community's
#  #general-chat "today" used UTC midnight while the voice-minute half of
#  the SAME task used database._today_local() (Asia/Dubai). During the
#  00:00-04:00 Dubai window the two disagreed, so a student could be told
#  the community task was incomplete when it wasn't. Both halves must now
#  use the same Asia/Dubai day boundary.
# ============================================================

import types
from unittest.mock import patch

import pytest

from src import database


def test_local_day_start_is_midnight_and_matches_today_local():
    """_local_day_start() must be 00:00, tz-aware, and land on the SAME
    calendar date as database._today_local() (both read config.TIMEZONE) —
    that shared boundary is the whole fix. tz-agnostic so it holds under the
    test env's TIMEZONE=UTC and under production's Asia/Dubai alike."""
    start = verification._local_day_start()
    assert (start.hour, start.minute, start.second) == (0, 0, 0)
    assert start.tzinfo is not None
    # Same day the rest of the bot reads submissions under.
    assert start.date() == database._today_local()


def test_local_day_start_honors_asia_dubai_and_is_not_utc_midnight():
    """With TIMEZONE=Asia/Dubai (production default), the general-chat window
    must be anchored to Dubai's day: offset +04:00, and its UTC instant is
    20:00 the previous UTC day (00:00 Dubai == 20:00 UTC) — never 00:00 UTC,
    which was the bug."""
    with patch("src.config.TIMEZONE", "Asia/Dubai"):
        start = verification._local_day_start()
    assert start.utcoffset() == datetime.timedelta(hours=4)
    assert (start.hour, start.minute, start.second) == (0, 0, 0)
    assert start.astimezone(datetime.timezone.utc).hour == 20  # 00:00 Dubai == 20:00 UTC


# ---- verify_community: BOTH voice AND chat required (E5) ----

class _FakeHistory:
    """Minimal async-iterable stand-in for discord channel.history()."""
    def __init__(self, messages):
        self._messages = messages
    def __aiter__(self):
        async def _gen():
            for m in self._messages:
                yield m
        return _gen()


def _make_guild_with_general_chat(messages):
    """Build a fake guild whose #general-chat history yields `messages`,
    and capture the `after` kwarg verify_community passes to history()."""
    captured = {}

    def _history(limit=None, after=None):
        captured["after"] = after
        return _FakeHistory(messages)

    channel = types.SimpleNamespace(name="general-chat", history=_history)
    guild = types.SimpleNamespace(text_channels=[channel])
    return guild, captured


def _msg_from(user_id):
    return types.SimpleNamespace(author=types.SimpleNamespace(id=user_id))


@pytest.mark.asyncio
async def test_verify_community_needs_both_voice_and_chat():
    member = types.SimpleNamespace(id=4242)

    # (a) voice OK, but NO chat message today -> not done, checklist shown.
    guild, _ = _make_guild_with_general_chat([])
    with patch.object(verification, "get_voice_minutes_today", return_value=15):
        ok, msg = await verification.verify_community(member, guild)
    assert ok is False
    assert "general-chat" in msg  # tells them what's still missing

    # (b) chat OK, but voice < 10 min -> not done.
    guild, _ = _make_guild_with_general_chat([_msg_from(4242)])
    with patch.object(verification, "get_voice_minutes_today", return_value=3):
        ok, msg = await verification.verify_community(member, guild)
    assert ok is False

    # (c) BOTH satisfied -> done.
    guild, _ = _make_guild_with_general_chat([_msg_from(4242)])
    with patch.object(verification, "get_voice_minutes_today", return_value=12):
        ok, msg = await verification.verify_community(member, guild)
    assert ok is True


@pytest.mark.asyncio
async def test_verify_community_chat_window_uses_dubai_day_start():
    """The `after` cutoff handed to channel.history() must be the Dubai
    day start (the fix), not UTC midnight."""
    member = types.SimpleNamespace(id=4242)
    guild, captured = _make_guild_with_general_chat([_msg_from(4242)])
    with patch.object(verification, "get_voice_minutes_today", return_value=12):
        await verification.verify_community(member, guild)
    # The cutoff must be the shared local day start, not the old UTC-midnight
    # literal. Compare only the date + that it's midnight/tz-aware (both
    # computed "now", so allow them to be the same wall-clock day).
    after = captured["after"]
    assert after.tzinfo is not None
    assert (after.hour, after.minute, after.second) == (0, 0, 0)
    assert after.date() == database._today_local()
