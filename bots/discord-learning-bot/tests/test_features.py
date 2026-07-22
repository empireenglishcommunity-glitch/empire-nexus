"""Tests for src/features.py.

Covers the pure/sync logic functions directly (task gating, spaced
repetition, grammar card formatting, resource lookups, response
formatting) and the Discord-dependent async functions via lightweight
Mock objects standing in for discord.Guild/Member — the same boundary
discord-challenge-bot's own test suite draws around Discord-object code.
"""
import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src import config, database, features


# ============================================================
#  1. GRADUAL TASK INTRO
# ============================================================

def test_get_allowed_tasks_unregistered_member_gets_all_tasks():
    """Falls back to the full task list for an unknown member rather
    than raising or returning an empty list."""
    allowed = features.get_allowed_tasks_for_member("nonexistent")
    assert allowed == [t["id"] for t in config.DAILY_TASKS]


# The gradual 3->5->7 task ramp was removed: every member now gets all 7
# tasks from day one, so that two members at the same level always see the
# same thing regardless of when they joined. These tests assert that new
# consistent behavior across the same join-date scenarios the ramp used to
# differentiate (brand new, day 3, day 5, week 2+).

def test_get_allowed_tasks_new_member_gets_all_seven():
    database.register_member("u1", "Alice")
    allowed = features.get_allowed_tasks_for_member("u1")
    assert allowed == [t["id"] for t in config.DAILY_TASKS]


def test_get_allowed_tasks_day_5_gets_all_seven():
    database.register_member("u1", "Alice")
    joined = (datetime.datetime.now() - datetime.timedelta(days=5)).isoformat()
    database.update_member("u1", joined_at=joined)
    allowed = features.get_allowed_tasks_for_member("u1")
    assert allowed == [t["id"] for t in config.DAILY_TASKS]


def test_get_allowed_tasks_week_2_plus_gets_all_seven():
    database.register_member("u1", "Alice")
    joined = (datetime.datetime.now() - datetime.timedelta(days=10)).isoformat()
    database.update_member("u1", joined_at=joined)
    allowed = features.get_allowed_tasks_for_member("u1")
    assert allowed == [t["id"] for t in config.DAILY_TASKS]


def test_get_allowed_tasks_day_3_gets_all_seven():
    database.register_member("u1", "Alice")
    joined = (datetime.datetime.now() - datetime.timedelta(days=3)).isoformat()
    database.update_member("u1", joined_at=joined)
    allowed = features.get_allowed_tasks_for_member("u1")
    assert allowed == [t["id"] for t in config.DAILY_TASKS]


# ============================================================
#  4. SPACED REPETITION
# ============================================================

def test_spaced_repetition_unregistered_member_returns_empty():
    assert features.get_spaced_repetition_words("nonexistent") == []


def test_spaced_repetition_week_1_returns_empty_no_prior_weeks():
    """range(max(1, week-3), week) is empty when week==1 -- there's
    nothing before week 1 to review yet."""
    database.register_member("u1", "Alice", level="L0")
    words = features.get_spaced_repetition_words("u1")
    assert words == []


def test_spaced_repetition_pulls_from_own_level_not_hardcoded_l0():
    """Regression guard: this previously always used a hardcoded 'L0'
    lookup regardless of the member's real level."""
    database.register_member("u1", "Alice", level="L2")
    joined = (datetime.datetime.now() - datetime.timedelta(days=14)).isoformat()
    database.update_member("u1", joined_at=joined)
    words = features.get_spaced_repetition_words("u1", count=5)
    # member_week_number for 14 days = 14//7+1 = 3, so review weeks are 1,2
    from src import curriculum
    l2_week1_words = {w["word"] for w in curriculum.get_vocabulary_for_week(1, "L2")}
    l2_week2_words = {w["word"] for w in curriculum.get_vocabulary_for_week(2, "L2")}
    valid_words = l2_week1_words | l2_week2_words
    for w in words:
        assert w["word"] in valid_words


def test_spaced_repetition_respects_count_limit():
    database.register_member("u1", "Alice", level="L0")
    joined = (datetime.datetime.now() - datetime.timedelta(days=30)).isoformat()
    database.update_member("u1", joined_at=joined)
    words = features.get_spaced_repetition_words("u1", count=2)
    assert len(words) <= 2


# ============================================================
#  6. GRAMMAR PATTERN CARD FORMATTING
# ============================================================

def test_format_grammar_card_l0_week1_produces_nonempty_card():
    card = features.format_grammar_card(1, "L0")
    assert card
    assert "Grammar Pattern" in card


def test_format_grammar_card_unknown_level_returns_empty_string():
    """Caller (bot.py) is expected to skip posting entirely when this
    returns "" -- must not return None or raise, since callers likely
    do `if card:` style checks."""
    card = features.format_grammar_card(1, "L99")
    assert card == ""


def test_format_grammar_card_includes_arabic_translation():
    card = features.format_grammar_card(1, "L0")
    assert "بالعربي" in card


def test_format_grammar_card_every_level_and_week_produces_output():
    """Every real week/level combination with authored grammar content
    must format without raising, for all 38 weeks."""
    from src import curriculum
    for level in ("L0", "L1", "L2", "L3"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            card = features.format_grammar_card(week, level)
            assert card, f"{level} week {week} produced an empty grammar card"


# ============================================================
#  9. ENGLISH-ONLY DETECTION (pure regex logic)
# ============================================================

def test_arabic_pattern_detects_arabic_text():
    assert features._ARABIC_PATTERN.search("مرحبا بك") is not None


def test_arabic_pattern_ignores_short_arabic_fragments():
    """Requires 3+ consecutive Arabic characters -- a single stray
    Arabic character (e.g. copy-pasted) shouldn't trigger enforcement."""
    assert features._ARABIC_PATTERN.search("hi") is None


def test_arabic_pattern_no_false_positive_on_pure_english():
    assert features._ARABIC_PATTERN.search("Hello, how are you today?") is None


@pytest.mark.asyncio
async def test_check_english_only_allows_arabic_in_allowed_channel():
    message = MagicMock()
    message.author.bot = False
    message.channel.name = "l0-questions"
    message.content = "ممكن سؤال؟"
    message.reply = AsyncMock()
    result = await features.check_english_only(message)
    assert result is False
    message.reply.assert_not_called()


@pytest.mark.asyncio
async def test_check_english_only_ignores_non_enforced_channel():
    message = MagicMock()
    message.author.bot = False
    message.channel.name = "some-random-channel"
    message.content = "ممكن سؤال؟"
    result = await features.check_english_only(message)
    assert result is False


@pytest.mark.asyncio
async def test_check_english_only_ignores_bot_messages():
    message = MagicMock()
    message.author.bot = True
    message.channel.name = "general-chat"
    message.content = "ممكن سؤال؟"
    result = await features.check_english_only(message)
    assert result is False


@pytest.mark.asyncio
async def test_check_english_only_flags_arabic_in_enforced_channel():
    database.register_member("u1", "Alice", level="L2")
    message = MagicMock()
    message.author.bot = False
    message.author.id = "u1"
    message.channel.name = "general-chat"
    message.content = "ممكن حد يساعدني؟"
    message.reply = AsyncMock()
    result = await features.check_english_only(message)
    assert result is True
    message.reply.assert_called_once()


@pytest.mark.asyncio
async def test_check_english_only_allows_pure_english_in_enforced_channel():
    message = MagicMock()
    message.author.bot = False
    message.author.id = "u1"
    message.channel.name = "general-chat"
    message.content = "Can someone help me?"
    message.reply = AsyncMock()
    result = await features.check_english_only(message)
    assert result is False
    message.reply.assert_not_called()


@pytest.mark.asyncio
async def test_check_english_only_gentle_for_l0_early_weeks():
    database.register_member("u1", "Alice", level="L0")
    joined = datetime.datetime.now().isoformat()  # week 1
    database.update_member("u1", joined_at=joined)
    message = MagicMock()
    message.author.bot = False
    message.author.id = "u1"
    message.channel.name = "l0-text-practice"
    message.content = "ممكن حد يساعدني؟"
    message.reply = AsyncMock()
    await features.check_english_only(message)
    call_text = message.reply.call_args.args[0]
    assert "English only!" not in call_text  # gentle version, no bold warning


@pytest.mark.asyncio
async def test_check_english_only_stronger_for_higher_levels():
    database.register_member("u1", "Alice", level="L2")
    message = MagicMock()
    message.author.bot = False
    message.author.id = "u1"
    message.channel.name = "general-chat"
    message.content = "ممكن حد يساعدني؟"
    message.reply = AsyncMock()
    await features.check_english_only(message)
    call_text = message.reply.call_args.args[0]
    assert "English only!" in call_text


# ============================================================
#  8. BUDDY SYSTEM
# ============================================================

def _make_member(member_id, roles=None, is_bot=False):
    m = MagicMock()
    m.id = member_id
    m.bot = is_bot
    m.roles = roles or []
    m.display_name = f"Member{member_id}"
    m.send = AsyncMock()
    return m


def _make_role(name, members):
    r = MagicMock()
    r.name = name
    r.members = members
    return r


def test_eligible_buddies_deduplicates_multi_role_member():
    """A member holding both Founder and Admin roles must only appear
    once in the eligible-buddy pool."""
    founder = _make_member(1)
    guild = MagicMock()
    founder_role = _make_role("🏛️ Founder", [founder])
    admin_role = _make_role("🛡️ Admin", [founder])  # same person, 2nd role
    mod_role = _make_role("⚔️ Moderator", [])
    amb_role = _make_role("🌟 سفير | Ambassador", [])
    guild.roles = [founder_role, admin_role, mod_role, amb_role]

    candidates = features._eligible_buddies(guild)
    assert len(candidates) == 1
    assert candidates[0].id == 1


def test_eligible_buddies_excludes_bots():
    bot_member = _make_member(1, is_bot=True)
    human_member = _make_member(2, is_bot=False)
    guild = MagicMock()
    founder_role = _make_role("🏛️ Founder", [bot_member, human_member])
    guild.roles = [founder_role]

    candidates = features._eligible_buddies(guild)
    ids = [c.id for c in candidates]
    assert 1 not in ids
    assert 2 in ids


def test_eligible_buddies_missing_role_does_not_crash():
    """discord.utils.get returns None for a role that doesn't exist on
    this server -- must skip it, not raise."""
    guild = MagicMock()
    guild.roles = []  # none of the buddy-eligible roles exist
    candidates = features._eligible_buddies(guild)
    assert candidates == []


@pytest.mark.asyncio
async def test_assign_buddy_picks_least_loaded_candidate():
    """Regression guard for the real bug this fixed: previously always
    assigned founder_role.members[0], forever, regardless of load."""
    database.register_member("buddy1", "Buddy1")
    database.register_member("buddy2", "Buddy2")
    # buddy1 already has 3 people; buddy2 has 0.
    for i in range(3):
        database.register_member(f"existing{i}", f"Existing{i}")
        database.update_member(f"existing{i}", buddy_id="buddy1")

    buddy1 = _make_member("buddy1")
    buddy2 = _make_member("buddy2")
    guild = MagicMock()
    guild.roles = [_make_role("🏛️ Founder", [buddy1, buddy2])]

    new_member = _make_member("newperson")
    new_member.display_name = "NewPerson"
    database.register_member("newperson", "NewPerson")

    await features.assign_buddy(new_member, guild)

    assert database.get_member("newperson")["buddy_id"] == "buddy2"
    buddy2.send.assert_called_once()
    buddy1.send.assert_not_called()


@pytest.mark.asyncio
async def test_assign_buddy_no_eligible_candidates_logs_and_skips():
    """Empty eligible-buddy pool (misconfigured server) must not crash
    -- just skip assignment (verified by no DB update happening)."""
    guild = MagicMock()
    guild.roles = []
    new_member = _make_member("newperson")
    database.register_member("newperson", "NewPerson")

    await features.assign_buddy(new_member, guild)

    assert database.get_member("newperson")["buddy_id"] == ""


@pytest.mark.asyncio
async def test_assign_buddy_dm_forbidden_still_assigns_in_database():
    """If the buddy has DMs closed, the assignment itself must still
    persist -- only the notification should silently fail."""
    import discord
    database.register_member("buddy1", "Buddy1")
    buddy1 = _make_member("buddy1")
    buddy1.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(status=403), "no dms"))
    guild = MagicMock()
    guild.roles = [_make_role("🏛️ Founder", [buddy1])]

    new_member = _make_member("newperson")
    database.register_member("newperson", "NewPerson")

    await features.assign_buddy(new_member, guild)
    assert database.get_member("newperson")["buddy_id"] == "buddy1"


# ============================================================
#  12a. !attention ADMIN DASHBOARD
# ============================================================

@pytest.mark.asyncio
async def test_attention_report_shows_nothing_urgent_when_all_clean():
    guild = MagicMock()
    guild.roles = []
    database.register_member("u1", "Alice")
    database.update_member("u1", last_active_at=datetime.datetime.now().isoformat())

    report = await features.build_attention_report(guild)
    assert "Nothing urgent" in report


@pytest.mark.asyncio
async def test_attention_report_lists_pending_exams():
    guild = MagicMock()
    guild.roles = []
    database.register_member("u1", "Alice")
    database.create_pending_exam("u1", "L0", "L1")

    report = await features.build_attention_report(guild)
    assert "exam(s) awaiting review" in report


@pytest.mark.asyncio
async def test_attention_report_buckets_inactive_members_by_severity():
    guild = MagicMock()
    guild.roles = []
    database.register_member("u1", "Alice")
    old = (datetime.datetime.now() - datetime.timedelta(days=8)).isoformat()
    database.update_member("u1", last_active_at=old)

    report = await features.build_attention_report(guild)
    assert "Inactive members" in report
    assert "membership_pause territory" in report  # 7+ day bucket label


@pytest.mark.asyncio
async def test_attention_report_shows_declining_trend_members():
    guild = MagicMock()
    guild.roles = []
    database.register_member("u1", "Alice")
    database.update_member("u1", last_active_at=datetime.datetime.now().isoformat())
    database.save_assessment("u1", 1, {}, overall=90, rating="Excellent")
    database.save_assessment("u1", 2, {}, overall=60, rating="At Risk")

    report = await features.build_attention_report(guild)
    assert "trending down" in report
    assert "90%" in report
    assert "60%" in report


@pytest.mark.asyncio
async def test_attention_report_shows_buddy_load():
    buddy1 = _make_member("buddy1")
    guild = MagicMock()
    guild.roles = [_make_role("🏛️ Founder", [buddy1])]
    database.register_member("buddy1", "Buddy1")
    database.register_member("u1", "Alice")
    database.update_member("u1", buddy_id="buddy1", last_active_at=datetime.datetime.now().isoformat())

    report = await features.build_attention_report(guild)
    assert "Buddy load" in report
    assert "Member1" in report or "1 member(s)" in report


@pytest.mark.asyncio
async def test_attention_report_buddy_load_section_stays_under_discord_limit():
    """Found via load/scale testing: the buddy-load section had no cap,
    unlike every other section in this report -- at ~50+ eligible
    buddies (a plausible staff size for a growing community) the combined
    report exceeded Discord's 2000-char message limit, which
    cmd_attention (only catches discord.Forbidden, not
    discord.HTTPException) would have let crash uncaught. Confirm the
    report stays well under the limit even with a large buddy pool."""
    buddies = [_make_member(f"staff{i}") for i in range(200)]
    guild = MagicMock()
    guild.roles = [_make_role("🏛️ Founder", buddies)]

    report = await features.build_attention_report(guild)
    assert len(report) < 2000
    assert "... and" in report
    assert "more" in report


# ============================================================
#  12. AT-RISK MEMBER OUTREACH
# ============================================================

@pytest.mark.asyncio
async def test_check_at_risk_members_dms_low_scorer():
    """discord_id must be a real Discord snowflake (numeric string) --
    check_at_risk_members() calls int(m["discord_id"]) internally, same
    as production usage, so test IDs must be numeric-looking too."""
    database.register_member("111", "Alice")
    database.save_assessment("111", 1, {}, overall=50, rating="Critical")

    discord_member = _make_member(111)
    guild = MagicMock()
    guild.get_member = MagicMock(return_value=discord_member)

    await features.check_at_risk_members(guild)
    discord_member.send.assert_called_once()


@pytest.mark.asyncio
async def test_check_at_risk_members_skips_good_scorer():
    database.register_member("111", "Alice")
    database.save_assessment("111", 1, {}, overall=95, rating="Excellent")

    discord_member = _make_member(111)
    guild = MagicMock()
    guild.get_member = MagicMock(return_value=discord_member)

    await features.check_at_risk_members(guild)
    discord_member.send.assert_not_called()


@pytest.mark.asyncio
async def test_check_at_risk_members_notifies_buddy():
    database.register_member("111", "Alice")
    database.register_member("222", "Buddy1")
    database.update_member("111", buddy_id="222")
    database.save_assessment("111", 1, {}, overall=50, rating="Critical")

    student = _make_member(111)
    buddy = _make_member(222)

    def get_member_side_effect(discord_id):
        return {111: student, 222: buddy}.get(discord_id)

    guild = MagicMock()
    guild.get_member = MagicMock(side_effect=get_member_side_effect)

    await features.check_at_risk_members(guild)
    buddy.send.assert_called_once()


@pytest.mark.asyncio
async def test_check_at_risk_members_no_assessment_is_skipped():
    database.register_member("111", "Alice")  # never assessed
    discord_member = _make_member(111)
    guild = MagicMock()
    guild.get_member = MagicMock(return_value=discord_member)

    await features.check_at_risk_members(guild)
    discord_member.send.assert_not_called()


# ============================================================
#  RESOURCE LOOKUPS / FORMATTING (pure)
# ============================================================

def test_format_shadowing_resources_known_level():
    text = features.format_shadowing_resources("L1")
    assert "L1" in text
    assert "TED-Ed" in text


def test_format_shadowing_resources_unknown_level_falls_back_to_l0():
    text = features.format_shadowing_resources("L99")
    assert "Rachel's English" in text  # an L0 resource


def test_get_daily_clip_links_known_week():
    links = features.get_daily_clip_links(3)
    assert "shadowing" in links
    assert links["accent_title"] == "Rachel's English - The Schwa Sound"


def test_get_daily_clip_links_unknown_week_falls_back_to_week_1():
    links = features.get_daily_clip_links(999)
    assert links == features.L0_DAILY_CLIPS[1]


def test_get_done_response_ar_known_task():
    result = features.get_done_response_ar("vocab", {"tasks_today": 3, "streak": 5, "points": 15})
    assert "المفردات" in result
    assert "3/7" in result
    assert "15" in result


def test_get_done_response_ar_all_seven_tasks_shows_bonus_message():
    result = features.get_done_response_ar("writing", {"tasks_today": 7, "streak": 5, "points": 115})
    assert "بونص" in result


def test_get_done_response_ar_unknown_task_id_uses_raw_id():
    result = features.get_done_response_ar("mystery_task", {"tasks_today": 1, "streak": 1, "points": 15})
    assert "mystery_task" in result


# ============================================================
#  EXAM DM COLLECTION FLOW (in-memory stage tracker)
# ============================================================

@pytest.mark.asyncio
async def test_start_exam_collection_sets_speaking_stage():
    database.register_member("u1", "Alice", level="L0")
    member = _make_member("u1")
    await features.start_exam_collection(member)
    assert features.has_pending_exam("u1") is True
    assert features._pending_exams["u1"]["stage"] == "speaking"
    assert features._pending_exams["u1"]["to_level"] == "L1"
    member.send.assert_called_once()


@pytest.mark.asyncio
async def test_handle_exam_dm_ignores_non_exam_users():
    message = MagicMock()
    message.author.id = "not_in_exam_flow"
    result = await features.handle_exam_dm(message)
    assert result is False


@pytest.mark.asyncio
async def test_handle_exam_dm_speaking_stage_requires_attachment():
    database.register_member("u1", "Alice", level="L0")
    member = _make_member("u1")
    await features.start_exam_collection(member)

    message = MagicMock()
    message.author.id = "u1"
    message.attachments = []
    message.channel.send = AsyncMock()

    result = await features.handle_exam_dm(message)
    assert result is True
    assert features._pending_exams["u1"]["stage"] == "speaking"  # unchanged
    message.channel.send.assert_called_once()


@pytest.mark.asyncio
async def test_handle_exam_dm_speaking_stage_accepts_attachment_advances_to_writing():
    database.register_member("u1", "Alice", level="L0")
    member = _make_member("u1")
    await features.start_exam_collection(member)

    attachment = MagicMock()
    attachment.url = "https://cdn.discord.com/recording.mp3"
    message = MagicMock()
    message.author.id = "u1"
    message.attachments = [attachment]
    message.channel.send = AsyncMock()

    result = await features.handle_exam_dm(message)
    assert result is True
    assert features._pending_exams["u1"]["stage"] == "writing"
    assert features._pending_exams["u1"]["speaking"] == attachment.url


@pytest.mark.asyncio
async def test_handle_exam_dm_writing_stage_rejects_short_text():
    database.register_member("u1", "Alice", level="L0")
    features._pending_exams["u1"] = {
        "stage": "writing", "speaking": "url", "writing": None,
        "from_level": "L0", "to_level": "L1",
    }
    message = MagicMock()
    message.author.id = "u1"
    message.content = "too short"
    message.channel.send = AsyncMock()

    result = await features.handle_exam_dm(message)
    assert result is True
    assert features._pending_exams["u1"]["stage"] == "writing"  # unchanged


@pytest.mark.asyncio
async def test_handle_exam_dm_writing_stage_persists_to_database_and_clears_memory():
    """This is the real fix's regression test: a completed submission
    must reach the database (create_pending_exam), not just live in
    the in-memory dict, and the in-memory tracker must be cleared once
    the durable record exists."""
    database.register_member("u1", "Alice", level="L0")
    features._pending_exams["u1"] = {
        "stage": "writing", "speaking": "https://x/rec.mp3", "writing": None,
        "from_level": "L0", "to_level": "L1",
    }
    message = MagicMock()
    message.author.id = "u1"
    message.author.mutual_guilds = []  # notify_admins_of_pending_exam no-ops safely
    message.content = "This is a long enough writing sample to pass the length check easily."
    message.channel.send = AsyncMock()

    result = await features.handle_exam_dm(message)
    assert result is True
    assert "u1" not in features._pending_exams  # cleared from memory

    attempt = database.last_advancement_attempt("u1")
    assert attempt is not None
    assert attempt["speaking_recording_url"] == "https://x/rec.mp3"
    assert attempt["status"] == "pending"


def test_has_pending_exam_false_once_waiting():
    """Once stage becomes 'waiting' (post-submission, pre-admin-review),
    has_pending_exam must report False -- the DM flow itself is done,
    even though a database row is still pending admin action."""
    features._pending_exams["u1"] = {"stage": "waiting"}
    assert features.has_pending_exam("u1") is False


def test_has_pending_exam_false_for_unknown_user():
    assert features.has_pending_exam("never-started") is False
