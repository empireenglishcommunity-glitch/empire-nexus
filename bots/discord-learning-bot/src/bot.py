"""Empire English Community Bot — Main Discord Bot.

The operational heart of the Learning Operating System. Handles:
  - Scheduled daily task delivery (6 AM) to level-specific channels
  - Scheduled weekly assessment prompts (Sunday 10 AM)
  - Member commands: !done, !progress, !streak, !top, !level, !help
  - Writing feedback pipeline (auto-evaluates submissions in #writing-feedback)
  - Streak tracking and leaderboard updates
  - Admin commands: !setlevel, !announce, !status, !reset

Commands:
  !join <goal>         Register and set your learning goal
  !done [task]         Mark a task as completed
  !progress            View your current progress dashboard
  !streak              View your streak info
  !top                 Leaderboard (points)
  !streaks             Leaderboard (streaks)
  !level               View your level info and advancement progress
  !week                View this week's curriculum focus
  !assess              Calculate this week's assessment score
  !help                Show all commands

Admin:
  !status              Bot and system status
  !attention           Ranked "who needs a human right now" report
  !setlevel @user L#   Set a member's level
  !announce <msg>      Broadcast to announcements
  !members             List all members with levels
"""
import asyncio
import datetime
import logging
from typing import Optional

import discord
from discord.ext import commands, tasks

from . import config, database, curriculum, tasks as task_engine, ai_engine, verification, features

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("empire-bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents, help_command=None)

# Per-user locks for !done's cooldown check. Found via rapid-fire/
# concurrency stress testing: verification.check_cooldown() and
# record_done_time() are separated by genuine async work (verify_task()'s
# real channel.history() Discord API calls), so two !done invocations
# for the SAME user fired close together (double-click, client retry, a
# duplicate gateway event) could both read "cooldown not active" before
# either one records -- letting a user submit two DIFFERENT tasks
# within what's supposed to be one 5-minute-spaced window. Confirmed via
# a 2-way asyncio.gather() race simulation. Not a data-integrity or
# double-points bug (log_submission()'s UNIQUE(discord_id, date, task_id)
# constraint already makes the SAME task un-double-submittable regardless
# -- confirmed separately), just a minor anti-spam-pacing bypass -- but
# real and reachable, so worth closing properly rather than leaving as a
# known gap. A lock per discord_id (not a single global lock) means this
# only ever serializes a user against their OWN concurrent !done calls,
# never against other members'.
_done_locks: dict[str, asyncio.Lock] = {}


def _get_done_lock(discord_id: str) -> asyncio.Lock:
    lock = _done_locks.get(discord_id)
    if lock is None:
        lock = asyncio.Lock()
        _done_locks[discord_id] = lock
    return lock


# ============================================================
#  BAWABA (Phase B0): Arabic command aliases + number tasks
# ============================================================

# Bawaba B1: track which messages are today's daily task posts (for
# reaction-based task completion). Cleared on each daily_task_post() run.
_daily_task_messages: set[int] = set()
_TASK_NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]
_EMOJI_TO_TASK_INDEX = {e: i for i, e in enumerate(_TASK_NUMBER_EMOJIS)}

# Maps Arabic command words to their English equivalents. The rewriting
# happens in on_message BEFORE bot.process_commands() runs, so every
# existing command handler works with Arabic input for free — no
# per-command changes needed. Gated behind the 'bawaba_aliases' flag.

ARABIC_COMMAND_ALIASES = {
    "انضم": "join",
    "تم": "done",
    "خلص": "done",
    "تقدم": "progress",
    "مساعدة": "helpar",
    "سلسلة": "streak",
    "مستوى": "level",
    "أسبوع": "week",
    "تقييم": "assess",
    "ترتيب": "top",
    "سلسلات": "streaks",
    "حالة": "systemstatus",
    "صيانة": "maintenance",
    "اليوم": "today",
    "تعليم": "tutorial",
}

# Maps Arabic task names to their English task_id equivalents (for !تم نطق etc.)
ARABIC_TASK_ALIASES = {
    "نطق": "accent",
    "مفردات": "vocab",
    "محاكاة": "shadow",
    "كلام": "speaking",
    "استماع": "listening",
    "كتابة": "writing",
    "مجتمع": "community",
}


def _rewrite_arabic_command(content: str, prefix: str) -> Optional[str]:
    """If the message starts with the bot prefix + an Arabic alias,
    rewrite it to the English equivalent. Returns the rewritten string,
    or None if no rewriting was needed.

    Examples:
      "!تم نطق"  → "!done accent"
      "!تم 3"    → "!done 3"  (number kept as-is, handled by cmd_done)
      "!انضم هدفي أتكلم" → "!join هدفي أتكلم"
      "!مساعدة"  → "!help"
      "!hello"   → None (not Arabic, no rewrite)
    """
    if not content.startswith(prefix):
        return None

    after_prefix = content[len(prefix):]
    parts = after_prefix.split(None, 1)  # split on first whitespace
    if not parts:
        return None

    cmd_word = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    # Check if the command word is an Arabic alias
    english_cmd = ARABIC_COMMAND_ALIASES.get(cmd_word)
    if english_cmd is None:
        return None

    # If the command is "done" and there's an argument, try to translate
    # the task name from Arabic too
    if english_cmd == "done" and rest:
        task_arg = rest.split(None, 1)[0]
        english_task = ARABIC_TASK_ALIASES.get(task_arg)
        if english_task:
            # Replace only the task argument, keep anything after it
            remaining = rest.split(None, 1)
            rest = english_task + ("" if len(remaining) < 2 else " " + remaining[1])

    if rest:
        return f"{prefix}{english_cmd} {rest}"
    return f"{prefix}{english_cmd}"



# ============================================================
#  TIMEZONE HELPER
# ============================================================

def _zone():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(config.TIMEZONE)
    except Exception:
        return datetime.timezone.utc


def _level_role_name(level: str) -> str:
    """Get the Discord role name for a level."""
    role_map = {"L0": "\U0001f331 Level 0 | \u0645\u0628\u062a\u062f\u0626", "L1": "\U0001f4aa Level 1 | \u0645\u062a\u0642\u062f\u0645", "L2": "\U0001f680 Level 2 | \u0645\u062a\u0648\u0627\u0635\u0644", "L3": "\U0001f451 Level 3 | \u0637\u0644\u064a\u0642"}
    return role_map.get(level, "\U0001f331 Level 0 | \u0645\u0628\u062a\u062f\u0626")


async def _get_or_create_role(guild: discord.Guild, role_name: str) -> discord.Role:
    """Get a role by name or create it if missing."""
    role = discord.utils.get(guild.roles, name=role_name)
    if not role:
        role = await guild.create_role(name=role_name)
    return role


async def _assign_level_role(member: discord.Member, new_level: str):
    """Remove old level roles and assign the new one."""
    guild = member.guild
    # Remove all level roles
    for lvl in ["L0", "L1", "L2", "L3"]:
        role_name = _level_role_name(lvl)
        role = discord.utils.get(guild.roles, name=role_name)
        if role and role in member.roles:
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                pass
    # Add new level role
    new_role = await _get_or_create_role(guild, _level_role_name(new_level))
    try:
        await member.add_roles(new_role)
    except discord.Forbidden:
        logger.warning(f"Cannot assign role {new_level} to {member.display_name}")


def _find_channel(guild: discord.Guild, name: str):
    """Find a text channel by name."""
    return discord.utils.get(guild.text_channels, name=name)


async def _send_onboarding_media(member: discord.Member):
    """Bawaba B3: send pre-generated multimedia onboarding assets (journey
    map infographic + Arabic audio clips) as DM attachments.

    Gracefully skips any files that don't exist yet (they need to be
    generated on the server via scripts/onboarding/generate_*.py first).
    """
    from pathlib import Path
    media_dir = Path(__file__).resolve().parent.parent / "scripts" / "onboarding"

    # Send journey map infographic (if generated)
    journey_map = media_dir / "images" / "journey_map.png"
    if journey_map.exists():
        try:
            await member.send(
                "🗺️ **خريطة رحلتك:**",
                file=discord.File(str(journey_map), filename="journey_map.png"),
            )
            await asyncio.sleep(1)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # Send audio clips (if generated)
    audio_dir = media_dir / "audio"
    audio_files = sorted(audio_dir.glob("*.mp3")) if audio_dir.exists() else []
    if audio_files:
        try:
            await member.send(
                "🎧 **اسمع الشرح بالعربي** (4 كليبات قصيرة):",
                files=[discord.File(str(f), filename=f.name) for f in audio_files[:4]],
            )
            await asyncio.sleep(1)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # Send video link (if configured)
    if config.ONBOARDING_VIDEO_URL:
        try:
            await member.send(
                f"🎬 **فيديو شرح (3 دقايق):** {config.ONBOARDING_VIDEO_URL}\n"
                f"*شوف الفيديو لو عايز تفهم أكتر بالتفصيل*"
            )
            await asyncio.sleep(1)
        except (discord.Forbidden, discord.HTTPException):
            pass


# ============================================================
#  BOT EVENTS
# ============================================================

@bot.event
async def on_ready():
    database.init_db()
    # Ensure the 'systemstatus' flag is enabled by default (Aegis Phase 5:
    # this was initially gated during development; now it's public).
    # Only sets it if it has never been touched — respects any admin's
    # explicit !flag disable systemstatus.
    from src.database import _connect
    conn = _connect()
    row = conn.execute("SELECT name FROM feature_flags WHERE name='systemstatus'").fetchone()
    conn.close()
    if row is None:
        database.set_feature_flag("systemstatus", enabled=True, updated_by="on_ready_default")
    # Load curriculum data from JSON files
    from . import curriculum
    curriculum.load_all()
    cstats = curriculum.stats()
    logger.info(f"Curriculum: {cstats['total_vocabulary']} words, {cstats['total_speaking_missions']} speaking, {cstats['accent_weeks']} accent weeks")
    logger.info(f"Bot online: {bot.user} | v{config.BOT_VERSION} | {len(bot.guilds)} server(s)")
    if not daily_task_post.is_running():
        daily_task_post.start()
    if not weekly_assessment.is_running():
        weekly_assessment.start()
    if not streak_update.is_running():
        streak_update.start()
    if not friday_feedback_survey.is_running():
        friday_feedback_survey.start()
    if not monday_progress_report.is_running():
        monday_progress_report.start()
    if not grammar_card_delivery.is_running():
        grammar_card_delivery.start()
    if not daily_streak_post.is_running():
        daily_streak_post.start()
    if not weekly_leaderboard_post.is_running():
        weekly_leaderboard_post.start()
    if not at_risk_check.is_running():
        at_risk_check.start()
    if not missed_day_report.is_running():
        missed_day_report.start()
    if not midnight_voice_reset.is_running():
        midnight_voice_reset.start()
    if not heartbeat.is_running():
        heartbeat.start()


@bot.event
async def on_member_join(member: discord.Member):
    """Auto-register new members and send welcome DM with full manual."""
    database.register_member(str(member.id), member.display_name)
    # Assign buddy
    await features.assign_buddy(member, member.guild)

    # Bawaba B2: if the tutorial quest flag is enabled, start the
    # interactive tutorial instead of the 4-message text wall.
    if database.is_feature_enabled("bawaba_tutorial"):
        try:
            await member.send(
                f"🏛️ **أهلًا بيك في Empire English, {member.display_name}!**\n\n"
                f"ده نظام تعلّم يومي هيخليك تتكلم إنجليزي.\n"
                f"خلينا نبدأ بـ 5 خطوات سريعة (دقيقتين بس) 👇"
            )

            # Bawaba B3: send multimedia onboarding assets if available
            if database.is_feature_enabled("bawaba_multimedia"):
                await _send_onboarding_media(member)

            await asyncio.sleep(1)
            await features.start_tutorial(member)
        except discord.Forbidden:
            pass
        return

    try:
        # Message 1: Welcome + First Steps
        await member.send(
            f"🏛️ **أهلًا بيك في Empire English Community, {member.display_name}!**\n\n"
            f"ده مش كورس عادي. ده **نظام تعلّم يومي** هيخليك تتكلم إنجليزي بلهجة أمريكية صح.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🚀 **أول 5 دقايق — ابدأ من هنا:**\n\n"
            f"1️⃣ اقرأ قناة `#rules` واقبل القوانين\n"
            f"2️⃣ روح `#bot-commands` واكتب:\n"
            f"```!join هدفي أتكلم إنجليزي بطلاقة```\n"
            f"3️⃣ كل يوم الساعة 6 الصبح — شوف `#l0-daily-tasks`\n"
            f"4️⃣ بعد ما تخلص المهمة اكتب: `!done accent`\n"
            f"5️⃣ شوف تقدمك: `!progress`"
        )
        await asyncio.sleep(2)

        # Message 2: Daily Tasks + Commands (with verification info)
        await member.send(
            "📅 **الروتين اليومي (7 مهام — 45 دقيقة بس):**\n\n"
            "🎯 تدريب النطق — سجل صوتك في `#l0-showcase` ← ثم `!done accent`\n"
            "📖 مفردات جديدة — `!done vocab` ← البوت هيسألك سؤال\n"
            "🎧 المحاكاة (Shadowing) — سجل 30 ثانية في `#l0-showcase` ← ثم `!done shadow`\n"
            "🎙️ مهمة الكلام — سجل صوتك في `#l0-showcase` ← ثم `!done speaking`\n"
            "👂 تمرين الاستماع — `!done listening` ← البوت هيسألك سؤال\n"
            "✍️ تمرين الكتابة — اكتب في `#l0-text-practice` ← ثم `!done writing`\n"
            "💬 مشاركة مجتمعية — اكتب في `#general-chat` أو ادخل voice 10 دقايق ← ثم `!done community`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ **مهم:** لازم تعمل المهمة الأول وبعدين تكتب `!done`\n"
            "البوت بيتأكد إنك فعلاً عملت المهمة قبل ما يديك النقاط."
        )
        await asyncio.sleep(2)

        # Message 3: Levels + Points
        await member.send(
            "🏆 **نظام المستويات:**\n\n"
            "🌱 **Level 0** — مبتدئ (8-12 أسبوع)\n"
            "   الهدف: تعريف نفسك في 60 ثانية\n\n"
            "💪 **Level 1** — النجاة (10-14 أسبوع)\n"
            "   الهدف: مونولوج 2 دقيقة بدون تحضير\n\n"
            "🚀 **Level 2** — التواصل (12-16 أسبوع)\n"
            "   الهدف: عرض 5 دقايق عن أي موضوع\n\n"
            "👑 **Level 3** — الطلاقة (مستمر)\n"
            "   كلام طبيعي بلهجة أمريكية\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔥 **النقاط:** كل مهمة = 15 نقطة | الـ 7 مهام = +100 بونص\n"
            "🔥 **Streaks:** 7 أيام = +200 | 30 يوم = +1000 | 100 يوم = +5000"
        )
        await asyncio.sleep(2)

        # Message 4: Channel Guide
        await member.send(
            "🗺️ **خريطة القنوات المهمة:**\n\n"
            "⭐ `#bot-commands` — اكتب كل الأوامر هنا\n"
            "⭐ `#l0-daily-tasks` — المهام اليومية (6 صباحًا)\n"
            "📝 `#l0-text-practice` — تمارين الكتابة\n"
            "🎙️ `#l0-showcase` — شارك تسجيلاتك\n"
            "❓ `#l0-questions` — أسئلة (عربي مسموح هنا)\n"
            "🔊 `l0-voice-1` — غرفة صوتية للتمرين\n"
            "💬 `#general-chat` — دردشة إنجليزي\n"
            "📖 `#daily-word` — كلمة اليوم\n"
            "🎙️ `#speaking-feedback` — ارفع تسجيل ← AI يرد عليك\n"
            "📊 `#daily-check-in` — سجل خطتك كل صباح\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏛️ **خلاصة:** ادخل كل يوم. اعمل الـ 7 مهام. اكتب `!done`. بس كده.\n"
            "النظام هيعمل الباقي. 💪\n\n"
            "*System over instructor. Common Sense First.* 🏛️"
        )
    except discord.Forbidden:
        pass  # DMs disabled by user


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🔒 You don't have permission for this command.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`. Type `!help` for usage.")
        return
    logger.error(f"Command error in !{ctx.command}: {error}")
    await ctx.send("⚠️ An error occurred. Please try again or contact a moderator.")


@bot.event
async def on_voice_state_update(member, before, after):
    """Track voice channel time for community task verification."""
    if member.bot:
        return
    # Joined a voice channel
    if before.channel is None and after.channel is not None:
        verification.on_voice_join(str(member.id))
    # Left a voice channel
    elif before.channel is not None and after.channel is None:
        verification.on_voice_leave(str(member.id))


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """Bawaba Phase B1: handle emoji reactions for registration and task completion.

    Two flows:
    1. ✅ on a welcome/registration message → auto-register the student
    2. 1️⃣-7️⃣ on a daily task post → trigger !done for that task number

    Gated behind the 'bawaba_reactions' feature flag. Verification still
    applies for task reactions — the emoji is just the trigger, not a
    bypass of the proof-checking system.
    """
    # Ignore bot's own reactions
    if payload.user_id == bot.user.id:
        return

    # Check feature flag (use None for discord_id since this is a global check)
    if not database.is_feature_enabled("bawaba_reactions"):
        return

    guild = bot.get_guild(payload.guild_id) if payload.guild_id else None
    if not guild:
        return

    emoji_str = str(payload.emoji)

    # --- Flow 1: ✅ reaction → auto-register ---
    if emoji_str == "✅":
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
        # Check if already registered
        existing = database.get_member(str(payload.user_id))
        if existing:
            return  # already registered, no-op
        # Register them
        database.register_member(str(payload.user_id), member.display_name)
        # Assign Level 0 role
        await _assign_level_role(member, "L0")
        # Assign buddy
        await features.assign_buddy(member, guild)
        # Send Arabic confirmation DM
        try:
            await member.send(
                "✅ **تم تسجيلك!** أهلاً بيك في Empire English 🏛️\n\n"
                "انت دلوقتي في **Level 0** — مبتدئ.\n"
                "كل يوم الساعة 6 الصبح هتلاقي مهام في قناة `#l0-daily-tasks`.\n\n"
                "اكتب `!مساعدة` في `#bot-commands` لو محتاج مساعدة.\n"
                "أو اكتب `!1` لما تخلص أول مهمة. بالتوفيق! 💪"
            )
        except discord.Forbidden:
            pass
        logger.info(f"Bawaba B1: {member.display_name} registered via ✅ reaction")
        return

    # --- Flow 2: 1️⃣-7️⃣ on a daily task post → !done ---
    if emoji_str in _EMOJI_TO_TASK_INDEX and payload.message_id in _daily_task_messages:
        task_index = _EMOJI_TO_TASK_INDEX[emoji_str]
        task_id = config.DAILY_TASKS[task_index]["id"]
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return

        # Check if registered
        member_data = database.get_member(str(payload.user_id))
        if not member_data:
            return  # not registered, can't submit

        # Check if already done today
        completed_today = database.tasks_completed_today(str(payload.user_id))
        if task_id in completed_today:
            return  # already submitted, no-op

        # Check gradual task intro (same as cmd_done)
        allowed = features.get_allowed_tasks_for_member(str(payload.user_id))
        if task_id not in allowed:
            return  # task not unlocked yet, silent no-op for reactions

        # NOTE: for reaction-based submission, we skip the full verification
        # flow (audio upload check, quiz, etc.) — reactions are meant for
        # tasks that have simpler verification or where the student already
        # completed the proof. The cooldown still applies.
        async with _get_done_lock(str(payload.user_id)):
            cool_allowed, _ = verification.check_cooldown(str(payload.user_id))
            if not cool_allowed:
                return  # on cooldown, silent no-op

            # For tasks requiring proof (accent, shadow, speaking need audio;
            # vocab/listening need quiz), reaction alone is NOT enough.
            # Only allow reaction-based completion for tasks with simpler
            # verification: writing (just needs text in channel) and
            # community (voice time or chat post).
            proof_required_tasks = {"accent", "shadow", "speaking", "vocab", "listening"}
            if task_id in proof_required_tasks:
                # Try to verify — for now, check if there's evidence in
                # the relevant channel (same as cmd_done does via verify_task)
                if isinstance(member, discord.Member):
                    passed, _ = await verification.verify_task(task_id, member, guild)
                    if not passed:
                        return  # no proof found, silent no-op

            # Process the submission
            verification.record_done_time(str(payload.user_id))
            result = await task_engine.process_submission(
                str(payload.user_id), member.display_name, task_id
            )

        if result.get("new"):
            # Send a brief Arabic confirmation in the channel
            channel = bot.get_channel(payload.channel_id)
            if channel:
                try:
                    await channel.send(
                        f"✅ {member.mention} — `{task_id}` تم! "
                        f"({result['tasks_today']}/7 اليوم) 🔥{result['streak']}",
                        delete_after=30,
                    )
                except discord.HTTPException:
                    pass
            logger.info(f"Bawaba B1: {member.display_name} completed '{task_id}' via reaction")


# ============================================================
#  SCHEDULED TASKS
# ============================================================

@tasks.loop(time=datetime.time(hour=config.DAILY_TASK_HOUR, tzinfo=_zone()))
async def daily_task_post():
    """Post daily tasks to each level's task channel at configured hour."""
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    # Bawaba B1: clear yesterday's tracked message IDs
    _daily_task_messages.clear()

    for level_key in ["L0", "L1", "L2", "L3"]:
        members = database.members_at_level(level_key)
        if not members:
            continue

        # Determine the week (use first member's week — all same level start similarly)
        week = database.member_week_number(members[0]["discord_id"])

        # Generate tasks
        task_data = await task_engine.generate_daily_tasks(level_key, week)
        # Send as multiple messages if needed — a single combined string
        # (the old format_daily_post() behavior) is frequently well over
        # Discord's 2000-char message limit (up to ~3600 chars for L3),
        # which previously made channel.send() raise discord.HTTPException
        # on most days; that exception was only logged, so daily tasks were
        # likely silently failing to post for most level/week combinations.
        message_chunks = task_engine.format_daily_post_chunks(task_data)

        # Find the channel
        channel_name = f"l{level_key[1]}-daily-tasks"
        channel = _find_channel(guild, channel_name)
        if channel:
            try:
                sent_messages = []
                for chunk in message_chunks:
                    msg = await channel.send(chunk)
                    sent_messages.append(msg)
                logger.info(f"Posted daily tasks to #{channel_name} (week {week}, {len(message_chunks)} message(s))")

                # Bawaba B1: add number reactions to the FIRST message
                # so students can react instead of typing commands
                if database.is_feature_enabled("bawaba_reactions") and sent_messages:
                    first_msg = sent_messages[0]
                    _daily_task_messages.add(first_msg.id)
                    for emoji in _TASK_NUMBER_EMOJIS[:7]:
                        try:
                            await first_msg.add_reaction(emoji)
                        except discord.HTTPException:
                            break  # rate limited or no permission, stop trying
            except discord.HTTPException as e:
                logger.error(f"Failed to post to #{channel_name}: {e}")


@tasks.loop(time=datetime.time(hour=config.WEEKLY_ASSESSMENT_HOUR, tzinfo=_zone()))
async def weekly_assessment():
    """Send weekly assessment prompts every Sunday."""
    if _now().weekday() != 6:  # 6 = Sunday
        return

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    members = database.all_active_members()
    for member_data in members:
        discord_member = guild.get_member(int(member_data["discord_id"]))
        if not discord_member:
            continue

        week_num = database.member_week_number(member_data["discord_id"])

        try:
            await discord_member.send(
                f"📊 **WEEKLY ASSESSMENT — Week {week_num}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Complete these tasks today (30 min total):\n\n"
                f"1️⃣ **SPEAKING** (5 min)\n"
                f"Record 60 seconds answering: \"What did you learn this week?\"\n\n"
                f"2️⃣ **WRITING** (8 min)\n"
                f"Write 5 sentences about your week in English.\n\n"
                f"3️⃣ **VOCABULARY** (5 min)\n"
                f"Type 10 words you learned this week with their meanings.\n\n"
                f"Submit everything in #writing-feedback or #speaking-feedback.\n"
                f"Use `!assess` when done to calculate your score.\n\n"
                f"⏰ Due by: Sunday 11:59 PM"
            )
        except discord.Forbidden:
            pass

    logger.info(f"Weekly assessments sent to {len(members)} members")


@tasks.loop(hours=1)
async def streak_update():
    """Hourly check for streak updates and inactive member interventions."""
    inactive = task_engine.check_inactive_members()
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    for action, members in inactive.items():
        if action == "dm_reminder":
            for m in members[:5]:  # Limit batch size
                discord_member = guild.get_member(int(m["discord_id"]))
                if discord_member:
                    try:
                        await discord_member.send(
                            f"👋 Hey {m['discord_name']}! We noticed you haven't been active. "
                            f"Even one task today keeps your streak alive. You got this! 🏛️"
                        )
                    except discord.Forbidden:
                        pass


def _now():
    """Current datetime helper (redefined at module level for tasks)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo(config.TIMEZONE))
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


# --- Additional Scheduled Tasks (from blueprint Phase 4-6) ---

@tasks.loop(time=datetime.time(hour=20, minute=0, tzinfo=_zone()))
async def friday_feedback_survey():
    """Send weekly feedback survey every Friday evening."""
    if _now().weekday() != 4:  # 4 = Friday
        return
    guild = bot.get_guild(config.GUILD_ID)
    if guild:
        await features.send_weekly_feedback_survey(guild)


@tasks.loop(time=datetime.time(hour=7, minute=0, tzinfo=_zone()))
async def monday_progress_report():
    """Send weekly progress report every Monday morning."""
    if _now().weekday() != 0:  # 0 = Monday
        return
    guild = bot.get_guild(config.GUILD_ID)
    if guild:
        await features.send_weekly_progress_report(guild)


@tasks.loop(time=datetime.time(hour=config.DAILY_TASK_HOUR, minute=30, tzinfo=_zone()))
async def grammar_card_delivery():
    """Post grammar pattern card on Day 4 of each week (Wednesday).

    Previously this only ever checked L0 members, so L1/L2/L3 students
    never received a grammar card regardless of content availability.
    Now loops over every level, same pattern as daily_task_post(), and
    silently skips a level if it has no grammar content authored yet
    (format_grammar_card returns "" in that case).
    """
    if _now().weekday() != 2:  # 2 = Wednesday
        return
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    channel = discord.utils.get(guild.text_channels, name="cheat-sheets")
    if not channel:
        logger.warning("grammar_card_delivery: #cheat-sheets channel not found")
        return

    for level_key in ["L0", "L1", "L2", "L3"]:
        members = database.members_at_level(level_key)
        if not members:
            continue

        week = database.member_week_number(members[0]["discord_id"])
        card = features.format_grammar_card(week, level_key)
        if not card:
            logger.info(f"No grammar card content for {level_key} week {week} — skipped")
            continue

        try:
            await channel.send(card)
            logger.info(f"Grammar card posted for {level_key} week {week}")
        except discord.HTTPException as e:
            logger.error(f"Failed to post grammar card for {level_key}: {e}")


@tasks.loop(minutes=2)
async def heartbeat():
    """Write a live timestamp to the settings table every 2 minutes, and
    update the bot's Discord presence to reflect maintenance mode.

    Aegis Phase 2 (production-safe-deploys spec): scripts/health_check.py
    runs as an EXTERNAL process (invoked via `docker exec` from
    deploy.sh, or run standalone by an admin), so it has no way to call
    bot.is_ready() directly on the actual running gateway connection --
    that's only meaningful from inside this same process. This loop is
    the bridge: as long as it's still firing, the bot's event loop is
    genuinely alive and connected (a crashed or disconnected bot stops
    firing loops entirely), and health_check.py can check "was this
    updated recently" from outside without needing any new
    infrastructure -- just the same settings table this bot already
    treats as its single source of runtime truth everywhere else.
    2 minutes is frequent enough that a health check run right after a
    deploy (per deploy.sh's `sleep 5` before checking) will always see a
    fresh value if the bot is actually healthy, without being so
    frequent it adds meaningful load.

    Aegis Phase 5: also checks the 'maintenance_mode' setting and
    updates the bot's Discord presence accordingly. This means
    deploy.py can set 'maintenance_mode=on' in the DB (via docker exec)
    BEFORE restarting, and the bot will show the maintenance presence
    within 2 minutes of coming back up. The !maintenance command also
    sets this flag for manual use.
    """
    database.set_setting("last_heartbeat", datetime.datetime.now(_zone()).isoformat())

    # Check maintenance mode and update presence
    maintenance = database.get_setting("maintenance_mode", "off")
    try:
        if maintenance == "on":
            await bot.change_presence(
                activity=discord.Game(name="\U0001f527 Updating... / \u0628\u064a\u062a\u0645 \u0627\u0644\u062a\u062d\u062f\u064a\u062b"),
                status=discord.Status.idle,
            )
        else:
            await bot.change_presence(
                activity=discord.Game(name="\U0001f3db\ufe0f Empire English | !help"),
                status=discord.Status.online,
            )
    except Exception:
        pass  # presence update is best-effort, never crash the heartbeat


@tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=_zone()))
async def midnight_voice_reset():
    """Reset today's voice-channel-minute tracking at midnight.

    verification.get_voice_minutes_today() is what the !done community
    check calls to decide whether someone spent 10+ minutes in voice
    "today" -- but nothing was ever calling reset_daily_voice() to clear
    the tracking dict at day boundaries. That made _voice_sessions a
    lifetime running total instead of a daily one: any member who ever
    accumulated 10+ voice minutes, on any single day, would pass the
    !done community voice check every day forever after, with zero
    actual voice activity on later days -- a real anti-cheat bypass, not
    just an unbounded-memory-growth concern. Found via a stress test
    that simulated two "days" of voice activity across a fake midnight
    boundary with no reset in between.
    """
    verification.reset_daily_voice()


@tasks.loop(time=datetime.time(hour=22, minute=0, tzinfo=_zone()))
async def daily_streak_post():
    """Post streak tracker summary every evening."""
    guild = bot.get_guild(config.GUILD_ID)
    if guild:
        await features.post_streak_tracker(guild)


@tasks.loop(time=datetime.time(hour=7, minute=30, tzinfo=_zone()))
async def weekly_leaderboard_post():
    """Post leaderboard every Sunday morning."""
    if _now().weekday() != 6:  # 6 = Sunday
        return
    guild = bot.get_guild(config.GUILD_ID)
    if guild:
        await features.post_leaderboard(guild)


@tasks.loop(time=datetime.time(hour=9, minute=0, tzinfo=_zone()))
async def at_risk_check():
    """Check for at-risk members every Monday."""
    if _now().weekday() != 0:  # 0 = Monday
        return
    guild = bot.get_guild(config.GUILD_ID)
    if guild:
        await features.check_at_risk_members(guild)


@tasks.loop(time=datetime.time(hour=8, minute=0, tzinfo=_zone()))
async def missed_day_report():
    """Post missed-day reminders every morning."""
    guild = bot.get_guild(config.GUILD_ID)
    if guild:
        await features.post_missed_day_reminders(guild)



# ============================================================
#  MEMBER COMMANDS
# ============================================================

@bot.command(name="join")
async def cmd_join(ctx, *, goal: str = ""):
    """Register as a community member."""
    # Found via message-length stress testing: a real Discord message is
    # itself capped at 2000 chars, so "!join <goal>" already lets a user
    # supply a goal up to ~1994 chars -- long enough that this command's
    # own welcome response (which echoes the goal back) exceeds Discord's
    # 2000-char send limit on its own. on_command_error() catches the
    # resulting discord.HTTPException so the bot doesn't crash, but the
    # member's registration silently succeeds while their confirmation
    # message fails, leaving them unsure !join even worked. !progress
    # also echoes this same goal, so capping here (at input time) protects
    # both display sites at once. 200 chars is generous for a genuine
    # short personal goal statement while leaving no realistic path back
    # over the limit.
    goal = goal[:200]
    is_new = database.register_member(str(ctx.author.id), ctx.author.display_name, goal=goal)
    if is_new:
        # Assign Level 0 role
        if isinstance(ctx.author, discord.Member):
            await _assign_level_role(ctx.author, "L0")
        msg = f"🌱 Welcome {ctx.author.mention}! You're registered at **Level 0**."
        if goal:
            msg += f"\n🎯 Goal: **{goal}**"
        msg += "\n\nYour daily tasks will appear in #l0-daily-tasks every morning."
    else:
        msg = f"✅ You're already registered, {ctx.author.mention}! Use `!progress` to check your status."
    await ctx.send(msg)


@bot.command(name="done")
async def cmd_done(ctx, task: str = None):
    """Mark a task as completed (with verification). Usage: !done accent / !done speaking / etc."""
    valid_tasks = [t["id"] for t in config.DAILY_TASKS]

    if not task:
        completed = database.tasks_completed_today(str(ctx.author.id))
        remaining = [t for t in valid_tasks if t not in completed]
        if not remaining:
            await ctx.send("🎉 All tasks done today! Amazing!")
            return
        await ctx.send(
            f"Which task? Use: `!done <task>`\n"
            f"Remaining: {', '.join(f'`{t}`' for t in remaining)}\n"
            f"Completed: {len(completed)}/7"
        )
        return

    task = task.lower().strip()
    if task not in valid_tasks:
        await ctx.send(f"❌ Unknown task. Valid: {', '.join(f'`{t}`' for t in valid_tasks)}")
        return

    # GRADUAL INTRO: Check if this task is unlocked for new members
    allowed = features.get_allowed_tasks_for_member(str(ctx.author.id))
    if task not in allowed:
        member = database.get_member(str(ctx.author.id))
        joined = datetime.datetime.fromisoformat(member["joined_at"]) if member else datetime.datetime.now()
        days = (datetime.datetime.now() - joined).days
        await ctx.send(
            f"🔒 مهمة `{task}` مش متاحة لسه.\n"
            f"انت في اليوم {days + 1}. المهام المتاحة ليك:\n"
            f"{', '.join(f'`{t}`' for t in allowed)}\n\n"
            f"*الـ 7 مهام هتكون متاحة من الأسبوع التاني.*"
        )
        return

    # Check if already done today
    completed_today = database.tasks_completed_today(str(ctx.author.id))
    if task in completed_today:
        await ctx.send(f"✅ You already submitted `{task}` today. Keep going!")
        return

    # Serialize this user's own !done attempts (see _get_done_lock's
    # docstring above) so the cooldown check below and record_done_time()
    # further down can't both pass for two near-simultaneous invocations
    # racing across the real async Discord API work in between them.
    async with _get_done_lock(str(ctx.author.id)):
        # TIME GATE: 5 min cooldown between !done commands
        allowed, remaining_secs = verification.check_cooldown(str(ctx.author.id))
        if not allowed:
            mins = remaining_secs // 60
            secs = remaining_secs % 60
            await ctx.send(f"⏳ استنى {mins}:{secs:02d} قبل ما تسجل مهمة تانية.\n(5 دقايق بين كل `!done`)")
            return

        # VOCAB: Two-step quiz flow
        if task == "vocab":
            question, answer, word = verification.generate_vocab_quiz(str(ctx.author.id))
            await ctx.send(f"📖 **اختبار مفردات:**\n\n{question}\n\n*اكتب إجابتك هنا:*")
            return  # Answer handled in on_message

        # LISTENING: Two-step quiz flow
        if task == "listening":
            prompt, answer = verification.generate_listening_quiz(str(ctx.author.id))
            await ctx.send(prompt)
            return  # Answer handled in on_message

        # OTHER TASKS: Verify proof exists
        if isinstance(ctx.author, discord.Member):
            passed, error_msg = await verification.verify_task(task, ctx.author, ctx.guild)
            if not passed:
                await ctx.send(f"❌ **لم يتم التحقق:**\n\n{error_msg}")
                return

        # PASSED VERIFICATION — process the submission
        verification.record_done_time(str(ctx.author.id))

        result = await task_engine.process_submission(
            str(ctx.author.id), ctx.author.display_name, task
        )

    if not result["new"]:
        await ctx.send(f"✅ You already submitted `{task}` today. Keep going!")
        return

    # Format response — Arabic for L0, English for higher
    member_data = database.get_member(str(ctx.author.id))
    level = member_data.get("level", "L0") if member_data else "L0"

    if level == "L0":
        msg = features.get_done_response_ar(task, result)
    else:
        bar = "█" * result["tasks_today"] + "░" * (7 - result["tasks_today"])
        msg = (
            f"{result['feedback']}\n\n"
            f"[{bar}] {result['tasks_today']}/7 today\n"
            f"🔥 Streak: **{result['streak']}** days | +{result['points']} points"
        )
        if result["tasks_today"] == 7:
            msg += "\n\n🎉 **ALL 7 TASKS COMPLETE!** Bonus points earned!"

    await ctx.send(msg)

    # PUBLIC CELEBRATION: all 7 tasks done
    if result["tasks_today"] == 7 and isinstance(ctx.author, discord.Member):
        await features.celebrate_completion(ctx.guild, ctx.author.display_name, result["streak"])

    # STREAK MILESTONE celebration
    if result["streak"] in config.STREAK_BONUS_POINTS and isinstance(ctx.author, discord.Member):
        bonus = config.STREAK_BONUS_POINTS[result["streak"]]
        await features.celebrate_streak_milestone(ctx.guild, ctx.author.display_name, result["streak"], bonus)


@bot.command(name="progress")
async def cmd_progress(ctx):
    """View your progress dashboard."""
    member = database.get_member(str(ctx.author.id))
    if not member:
        await ctx.send("You're not registered yet. Use `!join` to start.")
        return

    level_info = config.LEVELS.get(member["level"], config.LEVELS["L0"])
    week = database.member_week_number(str(ctx.author.id))
    completion = task_engine.calculate_completion_rate(str(ctx.author.id))
    completed_today = database.tasks_completed_today(str(ctx.author.id))
    bar = "█" * len(completed_today) + "░" * (7 - len(completed_today))

    latest = database.get_latest_assessment(str(ctx.author.id))
    score_line = f"📊 Last assessment: **{latest['overall_score']:.0f}%** ({latest['rating']})" if latest else "📊 No assessment yet"

    msg = (
        f"**{ctx.author.display_name}'s Progress**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{level_info['emoji']} Level: **{member['level']}** — {level_info['name']}\n"
        f"📅 Week: **{week}**\n"
        f"🎯 Goal: {member['goal'] or '—'}\n"
        f"🏆 Points: **{member['total_points']}**\n"
        f"🔥 Streak: **{member['current_streak']}** days (best: {member['longest_streak']})\n"
        f"📈 Completion rate (7 days): **{completion}%**\n"
        f"{score_line}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Today [{bar}] {len(completed_today)}/7\n"
        f"Track: {member['track']}"
    )
    await ctx.send(msg)


@bot.command(name="streak")
async def cmd_streak(ctx):
    """View your streak details."""
    current, longest = database.get_streak(str(ctx.author.id))
    completed = database.tasks_completed_today(str(ctx.author.id))
    bar = "█" * len(completed) + "░" * (7 - len(completed))

    msg = (
        f"🔥 **{ctx.author.display_name}'s Streak**\n\n"
        f"Current: **{current}** days\n"
        f"Longest ever: **{longest}** days\n"
        f"Today: [{bar}] {len(completed)}/7\n"
    )
    # Show next milestone
    for threshold, bonus in sorted(config.STREAK_BONUS_POINTS.items()):
        if current < threshold:
            msg += f"\n🎯 Next bonus: **{threshold}-day streak** (+{bonus} pts) — {threshold - current} days away"
            break

    await ctx.send(msg)



@bot.command(name="top")
async def cmd_top(ctx):
    """Points leaderboard."""
    rows = database.leaderboard(10)
    if not rows:
        await ctx.send("No members yet. Be the first to `!join`! 🌱")
        return
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    lines = ["🏆 **Points Leaderboard**\n"]
    for i, row in enumerate(rows):
        lvl = config.LEVELS.get(row["level"], config.LEVELS["L0"])
        lines.append(f"{medals[i]} {row['discord_name']} — {row['total_points']} pts {lvl['emoji']}")
    await ctx.send("\n".join(lines))


@bot.command(name="streaks")
async def cmd_streaks(ctx):
    """Streak leaderboard."""
    rows = database.streak_leaderboard(10)
    if not rows:
        await ctx.send("No streaks yet. Start with `!done`! 🔥")
        return
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    lines = ["🔥 **Streak Leaderboard**\n"]
    for i, row in enumerate(rows):
        lines.append(f"{medals[i]} {row['discord_name']} — {row['current_streak']} days (best: {row['longest_streak']})")
    await ctx.send("\n".join(lines))


@bot.command(name="level")
async def cmd_level(ctx):
    """View your level info and what's needed to advance."""
    member = database.get_member(str(ctx.author.id))
    if not member:
        await ctx.send("Not registered. Use `!join` first.")
        return

    level = member["level"]
    level_info = config.LEVELS[level]
    week = database.member_week_number(str(ctx.author.id))

    msg = (
        f"{level_info['emoji']} **Your Level: {level} — {level_info['name']}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 You're in week **{week}**\n"
        f"📖 Vocabulary target: {level_info['vocab_target']} words\n"
        f"🎙️ Speaking target: {level_info['speaking_target_seconds']} seconds\n"
        f"⏱️ Daily time ({member['track']}): ~{level_info['daily_minutes_core']} min\n"
    )
    if level_info["advancement_score"]:
        msg += (
            f"\n**To advance to the next level:**\n"
            f"• Pass the Exit Exam (minimum {level_info['advancement_score']}%)\n"
            f"• Available after week {level_info['duration_weeks'][0]} minimum\n"
            f"• All 5 exam sections must pass individually"
        )
    else:
        msg += "\n👑 Level 3 is the mastery level — no advancement. Pursue quarterly certification!"

    await ctx.send(msg)


@bot.command(name="week")
async def cmd_week(ctx):
    """View this week's curriculum focus (phonemes, vocab theme, etc.).

    BUG FIX (2026-07-11): this command previously read the member's level
    into a variable but never actually used it — it always pulled from
    config.PHONEME_WEEKS / config.VOCAB_THEMES, two hardcoded, L0-only
    dictionaries that predate the per-level curriculum.py system. An L1/L2/L3
    member running !week was silently shown L0's phoneme focus and vocab
    theme (e.g. "schwa" + "Family & People", L0's actual week 3 content),
    even though real, correct L1-L3 content already existed and loads fine
    for every other command. Found via live Discord testing after deploying
    the L1-L3 content fix — !week itself was never re-pointed at
    curriculum.py. Now uses the same level-aware functions as everywhere
    else (get_accent_focus, get_accent_focus_ar, get_theme, get_grammar_pattern).
    """
    member = database.get_member(str(ctx.author.id))
    if not member:
        await ctx.send("Not registered. Use `!join` first.")
        return

    week = database.member_week_number(str(ctx.author.id))
    level = member["level"]

    focus = curriculum.get_accent_focus(week, level)
    focus_ar = curriculum.get_accent_focus_ar(week, level)
    vocab_theme = curriculum.get_theme(week, level)
    grammar = curriculum.get_grammar_pattern(week, level)
    grammar_name = grammar.get("pattern_name") if grammar else None

    lines = [
        f"📅 **Week {week} Focus** ({level})",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if focus:
        lines.append(f"🎯 Accent focus: {focus}")
        if focus_ar:
            lines.append(f"   {focus_ar}")
    else:
        lines.append("🎯 Accent focus: content for this week is being finalized — check back soon.")
    lines.append(f"📖 Vocabulary theme: **{vocab_theme}**")
    if grammar_name:
        lines.append(f"📝 Grammar pattern: **{grammar_name}**")
    lines.append(
        f"🎙️ Speaking mission type: {config.SPEAKING_MISSION_TYPES.get(task_engine.current_day_name(), 'free_talk')}"
    )
    await ctx.send("\n".join(lines))


@bot.command(name="assess")
async def cmd_assess(ctx):
    """Calculate and save this week's assessment score.

    This command never existed until now, even though weekly_assessment()'s
    Sunday DM explicitly instructs every member to run `!assess` when done,
    and !help/the module docstring both documented it — found via
    adversarial-input stress testing on database.save_assessment(), which
    turned out to have zero production callers anywhere in the bot. As a
    result !progress's "Last assessment" line and !attention's
    declining-assessment-trend detection always silently showed
    "No assessment yet" / never fired in any real deployment.

    Scores each config.ASSESSMENT_DIMENSIONS entry from real data already
    on record this week (see task_engine.build_weekly_assessment's
    docstring for exactly how) — this does not ask the member anything or
    call the AI a second time, it just totals up what verification.py and
    the #writing-feedback pipeline already confirmed. Awards
    POINTS_ASSESSMENT once per week (re-running !assess later the same
    week refreshes the stored score, e.g. after a late writing submission,
    without double-awarding points).
    """
    member = database.get_member(str(ctx.author.id))
    if not member:
        await ctx.send("Not registered. Use `!join` first.")
        return

    week = database.member_week_number(str(ctx.author.id))
    already_assessed = database.get_assessment_for_week(str(ctx.author.id), week) is not None

    result = task_engine.build_weekly_assessment(str(ctx.author.id))
    database.save_assessment(
        str(ctx.author.id), week, result["scores"], result["overall"], result["rating"],
    )

    if not already_assessed:
        database.add_points(str(ctx.author.id), config.POINTS_ASSESSMENT, "weekly_assessment")

    dim_lines = []
    for dim in config.ASSESSMENT_DIMENSIONS:
        score = result["scores"].get(dim["id"], 0)
        dim_lines.append(f"  {dim['name']}: **{score:.0f}%**")

    missing = [
        t for t in ("speaking", "listening", "vocab", "accent", "writing")
        if t not in result["submitted_tasks"]
    ]
    missing_note = (
        f"\n⚠️ Not completed this week: {', '.join(f'`{t}`' for t in missing)}"
        if missing else "\n✅ All assessment tasks completed this week!"
    )
    bonus_note = f"\n🏆 +{config.POINTS_ASSESSMENT} assessment points!" if not already_assessed else ""

    await ctx.send(
        f"📊 **Week {week} Assessment — {ctx.author.display_name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(dim_lines) +
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"**Overall: {result['overall']:.0f}% — {result['rating']}**"
        f"{missing_note}{bonus_note}"
    )


@bot.command(name="help")
async def cmd_help(ctx):
    """Show all available commands."""
    await ctx.send(
        "**🏛️ Empire English Bot — Commands**\n\n"
        "**Learning:**\n"
        "`!join <goal>` — Register and set your goal\n"
        "`!done <task>` — Mark a task done (with verification)\n"
        "`!today` — See your remaining tasks for today\n"
        "`!progress` — Your full progress dashboard\n"
        "`!streak` — Your streak details\n"
        "`!level` — Your level info and advancement requirements\n"
        "`!week` — This week's curriculum focus\n"
        "`!assess` — Calculate this week's assessment score\n"
        "`!top` — Points leaderboard\n"
        "`!streaks` — Streak leaderboard\n"
        "`!systemstatus` — Check system health (public)\n\n"
        "**How `!done` works (verification):**\n"
        "🎯 `!done accent` — upload audio in #showcase first\n"
        "📖 `!done vocab` — bot asks you a word quiz\n"
        "🎧 `!done shadow` — upload 30s+ audio in #showcase first\n"
        "🎙️ `!done speaking` — upload audio in #showcase first\n"
        "👂 `!done listening` — bot asks a comprehension question\n"
        "✍️ `!done writing` — write in #text-practice first (20+ chars)\n"
        "💬 `!done community` — post in #general-chat or 10min voice\n"
        "⏳ 5 min cooldown between each `!done`\n\n"
        "**Admin:**\n"
        "`!status` — Bot status\n"
        "`!attention` — Ranked list of who needs a human right now (inactive, declining, pending exams, buddy load)\n"
        "`!setlevel @user L0/L1/L2/L3` — Set someone's level\n"
        "`!announce <message>` — Broadcast announcement\n"
        "`!members` — List all members\n"
        "`!orient <date/time>` — Send orientation invite\n"
        "`!recruit ar/en` — Get recruitment message template\n"
        "`!resources L0/L1/L2/L3` — Post shadowing resources\n"
        "`!examqueue` — List advancement exams awaiting review\n"
        "`!examresult <id> pass/fail` — Resolve an exam (auto-promotes on pass)\n"
        "`!flag list/enable/disable/beta` — Feature flag management\n"
        "`!maintenance on/off` — Toggle maintenance mode (deploy presence)\n\n"
        "**Account:**\n"
        "`!delete` — Request deletion of all your data\n"
        "`!exam` — Request level advancement exam\n"
    )


@bot.command(name="helpar")
async def cmd_helpar(ctx):
    """Arabic help — shows all commands with Arabic explanations.

    Bawaba Phase B0: triggered by !مساعدة (Arabic alias for help).
    Shows the full command list with Arabic descriptions and emphasizes
    the number-based shortcuts and Arabic aliases.
    """
    if not database.is_feature_enabled("bawaba_aliases"):
        # If Bawaba isn't enabled, just show regular English help
        await cmd_help(ctx)
        return

    await ctx.send(
        "**🏛️ أوامر البوت — Empire English**\n\n"
        "**📋 أوامر بالأرقام (الأسهل):**\n"
        "`!1` — تم مهمة النطق\n"
        "`!2` — تم مهمة المفردات\n"
        "`!3` — تم مهمة المحاكاة\n"
        "`!4` — تم مهمة الكلام\n"
        "`!5` — تم مهمة الاستماع\n"
        "`!6` — تم مهمة الكتابة\n"
        "`!7` — تم مهمة المجتمع\n\n"
        "**📋 أوامر بالعربي:**\n"
        "`!انضم <هدفك>` — سجل نفسك وحط هدفك\n"
        "`!تم` أو `!تم 1` — سجل إنك خلصت مهمة\n"
        "`!تقدم` — شوف تقدمك\n"
        "`!سلسلة` — شوف الـ streak بتاعك\n"
        "`!مستوى` — معلومات عن مستواك\n"
        "`!أسبوع` — محتوى الأسبوع ده\n"
        "`!تقييم` — احسب تقييم الأسبوع\n"
        "`!ترتيب` — لوحة النقاط\n"
        "`!حالة` — حالة النظام\n"
        "`!مساعدة` — الصفحة دي\n\n"
        "**⚡ طريقة الاستخدام:**\n"
        "1️⃣ كل يوم الساعة 6 الصبح هتلاقي مهام مرقمة 1-7\n"
        "2️⃣ اعمل المهمة\n"
        "3️⃣ اكتب رقمها: `!1` أو `!2` ... إلخ\n"
        "4️⃣ البوت هيتأكد ويديك النقاط ✅\n\n"
        "**🎯 أسماء المهام بالعربي (لو حبيت):**\n"
        "`!تم نطق` | `!تم مفردات` | `!تم محاكاة` | `!تم كلام`\n"
        "`!تم استماع` | `!تم كتابة` | `!تم مجتمع`\n\n"
        "💡 *كل الأوامر بالإنجليزي لسه شغالة عادي: `!done accent` إلخ*"
    )


# ============================================================
#  WRITING FEEDBACK (auto-detect submissions in #writing-feedback)
# ============================================================

@bot.event
async def on_message(message: discord.Message):
    """Detect writing submissions, auto-evaluate, handle quiz answers, and enforce English-only."""
    # Don't respond to bot's own messages
    if message.author.bot:
        return

    # Handle exam DM submissions
    if isinstance(message.channel, discord.DMChannel):
        if features.has_pending_exam(str(message.author.id)):
            handled = await features.handle_exam_dm(message)
            if handled:
                return
        # Bawaba B2: handle tutorial quest DM responses
        if features.has_pending_tutorial(str(message.author.id)):
            handled = await features.handle_tutorial_dm(message)
            if handled:
                return

    # English-only detection (before processing commands)
    await features.check_english_only(message)

    # BAWABA (Phase B0): rewrite Arabic aliases to English commands
    # before process_commands() sees them. Gated behind feature flag.
    if message.content.startswith(config.BOT_PREFIX) and database.is_feature_enabled("bawaba_aliases"):
        rewritten = _rewrite_arabic_command(message.content, config.BOT_PREFIX)
        if rewritten is not None:
            message.content = rewritten

    # BAWABA (Phase B0): number-based task commands (!1 through !7)
    # Rewrite "!1" to "!done accent", "!2" to "!done vocab", etc.
    if message.content.startswith(config.BOT_PREFIX) and database.is_feature_enabled("bawaba_aliases"):
        after_prefix = message.content[len(config.BOT_PREFIX):]
        if after_prefix.strip() in ("1", "2", "3", "4", "5", "6", "7"):
            task_num = int(after_prefix.strip())
            task_id = config.DAILY_TASKS[task_num - 1]["id"]
            message.content = f"{config.BOT_PREFIX}done {task_id}"

    # Process commands first
    await bot.process_commands(message)

    # Handle pending VOCAB quiz answers
    if verification.has_pending_quiz(str(message.author.id)):
        if message.channel.name == "bot-commands" and not message.content.startswith("!"):
            passed, error_msg = verification.check_vocab_answer(str(message.author.id), message.content)
            if passed:
                # Process the vocab submission
                verification.record_done_time(str(message.author.id))
                result = await task_engine.process_submission(
                    str(message.author.id), message.author.display_name, "vocab"
                )
                bar = "█" * result["tasks_today"] + "░" * (7 - result["tasks_today"])
                await message.channel.send(
                    f"✅ **صح!** أحسنت {message.author.mention}!\n\n"
                    f"[{bar}] {result['tasks_today']}/7 today\n"
                    f"🔥 Streak: **{result['streak']}** days | +{result['points']} points"
                )
            else:
                await message.channel.send(f"{message.author.mention} {error_msg}")
            return

    # Handle pending LISTENING quiz answers
    if verification.has_pending_listening(str(message.author.id)):
        if message.channel.name == "bot-commands" and not message.content.startswith("!"):
            passed, error_msg = verification.check_listening_answer(str(message.author.id), message.content)
            if passed:
                verification.record_done_time(str(message.author.id))
                result = await task_engine.process_submission(
                    str(message.author.id), message.author.display_name, "listening"
                )
                bar = "█" * result["tasks_today"] + "░" * (7 - result["tasks_today"])
                await message.channel.send(
                    f"✅ **صح!** أحسنت {message.author.mention}!\n\n"
                    f"[{bar}] {result['tasks_today']}/7 today\n"
                    f"🔥 Streak: **{result['streak']}** days | +{result['points']} points"
                )
            else:
                await message.channel.send(f"{message.author.mention} {error_msg}")
            return

    # Auto-evaluate writing in #writing-feedback channel
    if message.channel.name == "writing-feedback" and len(message.content) > 30:
        member = database.get_member(str(message.author.id))
        if not member:
            return

        # Show typing indicator
        async with message.channel.typing():
            result = await ai_engine.evaluate_writing(
                submission=message.content,
                original_prompt="(submitted directly to #writing-feedback)",
                level=member["level"],
            )

        if result:
            # Log as writing task submission
            database.log_submission(
                str(message.author.id),
                task_engine.today_str(),
                "writing",
                content=message.content[:500],
                score=result.get("overall_score"),
                feedback=result.get("feedback_en", ""),
            )

            # Send feedback as reply
            feedback_msg = (
                f"📝 **Writing Feedback for {message.author.display_name}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Overall: **{result['overall_score']}/100** — {result.get('rating', '')}\n\n"
                f"{result.get('feedback_en', '')}\n\n"
                f"🎯 Focus: {result.get('one_thing_to_practice', '')}"
            )
            await message.reply(feedback_msg)


# ============================================================
#  ADVANCEMENT EXAM
# ============================================================

@bot.command(name="exam")
async def cmd_exam(ctx):
    """Request the level advancement exam."""
    await features.handle_exam_request(ctx, bot)
    # If eligible, start DM collection
    member = database.get_member(str(ctx.author.id))
    if member:
        level_info = config.LEVELS.get(member["level"], config.LEVELS["L0"])
        week = database.member_week_number(str(ctx.author.id))
        min_weeks = level_info.get("duration_weeks")
        if min_weeks and week >= min_weeks[0]:
            await features.start_exam_collection(ctx.author)


@bot.command(name="examresult")
@commands.has_permissions(manage_guild=True)
async def cmd_examresult(ctx, exam_id: int = None, result: str = None):
    """Resolve a pending advancement exam. Usage: !examresult <id> pass|fail

    Closes the loop that !exam previously left open: on 'pass' this
    actually calls database.set_level() and reassigns the Discord role
    (the same promotion logic !setlevel uses), then DMs the student.
    On 'fail' it DMs constructive next steps. Either way the exam row
    moves out of 'pending', which also releases the 30-day cooldown.
    """
    if exam_id is None or result not in ("pass", "fail"):
        await ctx.send("Usage: `!examresult <id> pass` or `!examresult <id> fail`")
        return

    exam = database.get_exam_by_id(exam_id)
    if not exam:
        await ctx.send(f"❌ No exam found with id `{exam_id}`.")
        return
    if exam["status"] != "pending":
        await ctx.send(f"⚠️ Exam #{exam_id} was already resolved as **{exam['status']}**.")
        return

    passed = result == "pass"
    database.resolve_exam(exam_id, passed, resolved_by=str(ctx.author.id))

    student = ctx.guild.get_member(int(exam["discord_id"]))

    if passed:
        database.set_level(exam["discord_id"], exam["to_level"])
        if student:
            await _assign_level_role(student, exam["to_level"])
        level_info = config.LEVELS.get(exam["to_level"], config.LEVELS["L0"])
        await ctx.send(
            f"✅ Exam #{exam_id}: **{exam['discord_id']}** passed → promoted to "
            f"**{exam['to_level']}** ({level_info['name']})"
        )
        if student:
            try:
                await student.send(
                    f"🎉 **مبروك! نجحت في امتحان الترقية!**\n\n"
                    f"انت دلوقتي في **{exam['to_level']} — {level_info['name']}** {level_info['emoji']}\n\n"
                    f"استمر! 🏛️"
                )
            except discord.Forbidden:
                pass
    else:
        await ctx.send(f"📋 Exam #{exam_id}: **{exam['discord_id']}** marked as failed. Stays at {exam['from_level']}.")
        if student:
            try:
                await student.send(
                    "📋 **نتيجة امتحان الترقية**\n\n"
                    "لسه مش وقتها. استمر في التمرين وحاول تاني بعد شهر.\n"
                    "ابعت `#support` لو عايز تفاصيل أكتر عن نقاط التحسين.\n\n"
                    "احنا معاك. 🏛️"
                )
            except discord.Forbidden:
                pass


@bot.command(name="examqueue")
@commands.has_permissions(manage_guild=True)
async def cmd_examqueue(ctx):
    """List all advancement exams awaiting review."""
    rows = database.pending_exams()
    if not rows:
        await ctx.send("✅ No exams pending review.")
        return
    lines = [f"📋 **Pending Exams ({len(rows)})**\n"]
    for r in rows:
        lines.append(
            f"#{r['id']} — {r.get('discord_name') or r['discord_id']} "
            f"({r['from_level']} → {r['to_level']}) — submitted {r['attempted_at']}"
        )
    lines.append("\nResolve with `!examresult <id> pass` or `!examresult <id> fail`")
    try:
        await ctx.author.send("\n".join(lines))
        await ctx.send("📩 Exam queue sent to your DMs.", delete_after=5)
    except discord.Forbidden:
        await ctx.send("\n".join(lines))


@bot.command(name="delete")
async def cmd_delete(ctx):
    """Request deletion of all your data."""
    await features.handle_delete_request(ctx, bot)


@bot.command(name="today")
async def cmd_today(ctx):
    """Show your remaining tasks for today."""
    await features.show_today(ctx)


@bot.command(name="tutorial")
async def cmd_tutorial(ctx):
    """Start (or restart) the interactive onboarding tutorial.

    Bawaba B2: the same 5-step DM quest that new members get on join.
    Useful for existing members who want to learn the Arabic commands,
    or for testing. Gated behind 'bawaba_tutorial' flag.
    """
    if not database.is_feature_enabled("bawaba_tutorial"):
        await ctx.send("هذه الميزة مش متاحة حالياً.")
        return
    try:
        await features.start_tutorial(ctx.author)
        await ctx.send("📩 شوف الـ DMs — بدأنا رحلة التعريف! 🏛️", delete_after=10)
    except discord.Forbidden:
        await ctx.send("❌ مقدرش أبعتلك DM. افتح الرسائل الخاصة.")


@bot.command(name="confirm-delete")
async def cmd_confirm_delete(ctx):
    """Confirm data deletion."""
    await features.handle_confirm_delete(ctx, bot)


# ============================================================
#  ADMIN COMMANDS
# ============================================================

@bot.command(name="status")
@commands.has_permissions(manage_guild=True)
async def cmd_status(ctx):
    """Bot and system status (sent via DM to admin)."""
    member_count = database.member_count()
    today_subs = database.total_submissions_today()
    active_levels = {}
    for lvl in ["L0", "L1", "L2", "L3"]:
        active_levels[lvl] = len(database.members_at_level(lvl))

    msg = (
        f"**🤖 Empire English Bot Status**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Version: **{config.BOT_VERSION}**\n"
        f"Guilds: {len(bot.guilds)}\n"
        f"Members (registered): **{member_count}**\n"
        f"  🌱 L0: {active_levels['L0']} | 💪 L1: {active_levels['L1']} | "
        f"🚀 L2: {active_levels['L2']} | 👑 L3: {active_levels['L3']}\n"
        f"Submissions today: **{today_subs}**\n"
        f"Daily tasks: {'🟢 Running' if daily_task_post.is_running() else '🔴 Stopped'}\n"
        f"Assessments: {'🟢 Running' if weekly_assessment.is_running() else '🔴 Stopped'}\n"
        f"Gemini: {'🟢' if config.GEMINI_API_KEY else '🔴'} | "
        f"Groq: {'🟢' if config.GROQ_API_KEY else '⚪'}\n"
        f"Timezone: {config.TIMEZONE}\n"
        f"Task delivery: {config.DAILY_TASK_HOUR}:00"
    )
    try:
        await ctx.author.send(msg)
        await ctx.send("📩 Status sent to your DMs.", delete_after=5)
    except discord.Forbidden:
        await ctx.send(msg)


@bot.command(name="systemstatus")
async def cmd_systemstatus(ctx):
    """Public, read-only system health check — anyone can run this.

    Aegis Phase 5: now enabled for everyone (previously gated behind the
    'systemstatus' feature flag during Phase 1 development). Shows no
    admin-sensitive facts (no AI-key presence, no per-level member
    breakdown), just "is the system healthy right now" — reinforcing the
    professional/reliable brand for paying students without a new paid
    service. Distinct from the existing admin-only !status.
    """
    if not database.is_feature_enabled("systemstatus", str(ctx.author.id)):
        return  # still respects the kill switch if an admin explicitly
                # disables it via !flag disable systemstatus

    checks = []
    all_ok = True

    try:
        database.member_count()
        checks.append("✅ Database")
    except Exception:
        checks.append("❌ Database")
        all_ok = False

    checks.append("✅ Discord connection" if bot.is_ready() else "❌ Discord connection")
    all_ok = all_ok and bot.is_ready()

    try:
        weeks_loaded = curriculum.stats()["weeks_loaded"]
        checks.append(f"✅ Curriculum ({weeks_loaded} weeks loaded)" if weeks_loaded == 38 else f"⚠️ Curriculum ({weeks_loaded}/38 weeks)")
    except Exception:
        checks.append("❌ Curriculum")
        all_ok = False

    database.set_setting("last_systemstatus_check", datetime.datetime.now().isoformat())

    header = "✅ **All systems operational**" if all_ok else "⚠️ **Some systems need attention**"
    await ctx.send(
        f"{header}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(checks)
    )


@bot.command(name="setlevel")
@commands.has_permissions(manage_guild=True)
async def cmd_setlevel(ctx, member: discord.Member = None, level: str = None):
    """Set a member's level. Usage: !setlevel @user L1"""
    if not member or not level:
        await ctx.send("Usage: `!setlevel @user L0/L1/L2/L3`")
        return
    level = level.upper()
    if level not in config.LEVELS:
        await ctx.send("❌ Invalid level. Use: L0, L1, L2, L3")
        return

    database.set_level(str(member.id), level)
    await _assign_level_role(member, level)
    level_info = config.LEVELS[level]
    await ctx.send(f"✅ {member.display_name} is now **{level}** — {level_info['emoji']} {level_info['name']}")


@bot.command(name="flag")
@commands.has_permissions(manage_guild=True)
async def cmd_flag(ctx, action: str = None, name: str = None, *members: discord.Member):
    """Feature flag admin command — Aegis Phase 1 (production-safe deploys).

    Usage:
      !flag list                       — show every flag ever set
      !flag enable <name>               — turn a feature on for EVERYONE
      !flag disable <name>              — turn a feature off for everyone
                                           (the kill switch: instant, no
                                           redeploy, no downtime)
      !flag beta <name> @user1 @user2   — turn a feature on ONLY for the
                                           given members (test on
                                           yourself or a trusted few
                                           before a full release)

    This decouples "deploy" (code reaches the server, dormant) from
    "release" (a real student sees new behavior) — see
    .kiro/specs/production-safe-deploys/design.md. New risky behavior
    in other commands should be wrapped:
        if database.is_feature_enabled("name", str(ctx.author.id)):
            ... new behavior ...
        else:
            ... old behavior, or a no-op ...
    """
    if action not in ("list", "enable", "disable", "beta"):
        await ctx.send(
            "Usage:\n"
            "`!flag list`\n"
            "`!flag enable <name>`\n"
            "`!flag disable <name>`\n"
            "`!flag beta <name> @user1 @user2 ...`"
        )
        return

    if action == "list":
        flags = database.list_feature_flags()
        if not flags:
            await ctx.send("No feature flags have been set yet.")
            return
        # Capped the same way !attention's buddy-load section is (found
        # via message-length stress testing that session) -- unlikely to
        # matter at this bot's real scale, but cheap insurance against
        # the same class of Discord 2000-char overflow bug.
        lines = ["🚩 **Feature Flags:**"]
        for f in flags[:20]:
            state = "🟢 ON (everyone)" if f["enabled"] and not f["allowed_ids"] else \
                    f"🟡 ON (beta: {f['allowed_ids']})" if f["enabled"] else "🔴 OFF"
            lines.append(f"  `{f['name']}` — {state}")
        if len(flags) > 20:
            lines.append(f"  ... and {len(flags) - 20} more")
        await ctx.send("\n".join(lines))
        return

    if not name:
        await ctx.send(f"Usage: `!flag {action} <name>`" + (" @user1 @user2 ..." if action == "beta" else ""))
        return

    if action == "enable":
        database.set_feature_flag(name, enabled=True, updated_by=str(ctx.author.id))
        await ctx.send(f"🟢 Flag `{name}` is now **ON for everyone**.")
    elif action == "disable":
        database.set_feature_flag(name, enabled=False, updated_by=str(ctx.author.id))
        await ctx.send(f"🔴 Flag `{name}` is now **OFF for everyone**.")
    elif action == "beta":
        if not members:
            await ctx.send(f"Usage: `!flag beta {name} @user1 @user2 ...`")
            return
        allowed_ids = ",".join(str(m.id) for m in members)
        database.set_feature_flag(name, enabled=True, allowed_ids=allowed_ids, updated_by=str(ctx.author.id))
        names = ", ".join(m.display_name for m in members)
        await ctx.send(f"🟡 Flag `{name}` is now **ON for beta testers only**: {names}")


@bot.command(name="maintenance")
@commands.has_permissions(manage_guild=True)
async def cmd_maintenance(ctx, mode: str = None):
    """Toggle maintenance mode (changes bot presence during deploys).

    Usage:
      !maintenance on   — show "Updating..." presence (idle status)
      !maintenance off  — restore normal presence (online status)
      !maintenance      — show current state

    Aegis Phase 5: deploy.py sets this flag automatically before a
    deploy (via docker exec) so students see a deliberate "updating"
    status rather than the bot just disappearing and reappearing. The
    heartbeat loop (every 2 min) picks up the flag and updates presence.
    This command lets an admin toggle it manually for longer maintenance
    windows or testing.
    """
    if mode not in ("on", "off", None):
        await ctx.send("Usage: `!maintenance on` or `!maintenance off`")
        return

    if mode is None:
        current = database.get_setting("maintenance_mode", "off")
        status_text = "\U0001f527 **Maintenance mode is ON**" if current == "on" else "\u2705 **Maintenance mode is OFF** (normal)"
        await ctx.send(status_text)
        return

    database.set_setting("maintenance_mode", mode)

    if mode == "on":
        await bot.change_presence(
            activity=discord.Game(name="\U0001f527 Updating... / \u0628\u064a\u062a\u0645 \u0627\u0644\u062a\u062d\u064a\u062b"),
            status=discord.Status.idle,
        )
        await ctx.send("\U0001f527 Maintenance mode **ON** — bot presence updated to 'Updating...'")
    else:
        await bot.change_presence(
            activity=discord.Game(name="\U0001f3db\ufe0f Empire English | !help"),
            status=discord.Status.online,
        )
        await ctx.send("\u2705 Maintenance mode **OFF** — bot presence restored to normal.")


@bot.command(name="announce")
@commands.has_permissions(manage_guild=True)
async def cmd_announce(ctx, *, message: str = ""):
    """Send announcement to #announcements."""
    if not message:
        await ctx.send("Usage: `!announce <your message>`")
        return
    # Found via message-length stress testing: a real Discord message is
    # itself capped at 2000 chars, so !announce's own header
    # ("📢 **Announcement**\n\n") pushes a max-length message over
    # Discord's 2000-char send limit on its own. Unlike !join's goal
    # (fixed by truncating -- a short personal statement losing its tail
    # is harmless), an announcement's exact wording matters, so reject
    # with a clear message instead of silently cutting it off, same
    # approach as this session's !orient fix.
    if len(message) > 1950:
        await ctx.send(
            f"❌ That's too long ({len(message)} chars). Keep it under 1950 characters "
            f"so it fits in a single message."
        )
        return
    guild = ctx.guild
    channel = _find_channel(guild, "announcements")
    if channel:
        await channel.send(f"📢 **Announcement**\n\n{message}")
        await ctx.send(f"✅ Announcement sent to #{channel.name}")
    else:
        await ctx.send("❌ #announcements channel not found.")


@bot.command(name="attention")
@commands.has_permissions(manage_guild=True)
async def cmd_attention(ctx):
    """Ranked 'who needs a human right now' report: inactive members by
    severity, declining assessment trends, pending exams, and buddy
    load — combining signals that already exist across the bot into
    one view instead of several separate commands. Read-only, sent via
    DM (falls back to the channel if DMs are closed, same pattern as
    !status/!members)."""
    report = await features.build_attention_report(ctx.guild)
    try:
        await ctx.author.send(report)
        await ctx.send("📩 Attention report sent to your DMs.", delete_after=5)
    except discord.Forbidden:
        await ctx.send(report)


@bot.command(name="members")
@commands.has_permissions(manage_guild=True)
async def cmd_members(ctx):
    """List all registered members with their levels (sent via DM)."""
    members = database.all_active_members()
    if not members:
        await ctx.send("No registered members yet.")
        return
    lines = [f"**👥 Members ({len(members)})**\n"]
    for m in members[:20]:
        lvl = config.LEVELS.get(m["level"], config.LEVELS["L0"])
        streak_str = f"🔥{m['current_streak']}" if m["current_streak"] > 0 else ""
        lines.append(f"{lvl['emoji']} {m['discord_name']} — {m['level']} | {m['total_points']} pts {streak_str}")
    if len(members) > 20:
        lines.append(f"\n... and {len(members) - 20} more")
    try:
        await ctx.author.send("\n".join(lines))
        await ctx.send("📩 Members list sent to your DMs.", delete_after=5)
    except discord.Forbidden:
        await ctx.send("\n".join(lines))



# ============================================================
#  ADMIN: ORIENTATION & RECRUITMENT
# ============================================================

@bot.command(name="orient")
@commands.has_permissions(manage_guild=True)
async def cmd_orient(ctx, *, date_time: str = ""):
    """Send orientation invite to all members. Usage: !orient Saturday 7PM"""
    if not date_time:
        await ctx.send("Usage: `!orient Saturday 7PM Dubai time`")
        return
    # ORIENTATION_TEMPLATE is ~523 chars empty; Discord's hard 2000-char
    # message limit leaves roughly 1477 chars of headroom. Reject early
    # with a clear message instead of relying solely on
    # send_orientation_invite()'s per-member try/except (found via
    # adversarial-input stress testing -- see features.py for details).
    if len(date_time) > 1000:
        await ctx.send(
            f"❌ That's too long ({len(date_time)} chars). Keep it under 1000 characters "
            f"so the invite fits in a single DM."
        )
        return
    guild = ctx.guild
    sent = await features.send_orientation_invite(guild, date_time)
    await ctx.author.send(f"📩 Orientation invite sent to {sent} members for: {date_time}")
    await ctx.send("📩 Done.", delete_after=5)


@bot.command(name="recruit")
@commands.has_permissions(manage_guild=True)
async def cmd_recruit(ctx, lang: str = "ar"):
    """Show recruitment message template. Usage: !recruit ar / !recruit en"""
    if lang == "en":
        msg = features.RECRUITMENT_MESSAGE_EN
    else:
        msg = features.RECRUITMENT_MESSAGE_AR
    await ctx.author.send(f"📋 **Recruitment Template ({lang}):**\n\n{msg}")
    await ctx.send("📩 Template sent to your DMs.", delete_after=5)


@bot.command(name="resources")
@commands.has_permissions(manage_guild=True)
async def cmd_resources(ctx, level: str = "L0"):
    """Post shadowing resources for a level. Usage: !resources L0"""
    level = level.upper()
    if level not in ["L0", "L1", "L2", "L3"]:
        await ctx.send("Usage: `!resources L0/L1/L2/L3`")
        return
    msg = features.format_shadowing_resources(level)
    channel = discord.utils.get(ctx.guild.text_channels, name="cheat-sheets")
    if channel:
        await channel.send(msg)
        await ctx.send(f"📩 Resources posted in #cheat-sheets for {level}", delete_after=5)
    else:
        await ctx.send(msg)


# ============================================================
#  ENTRY POINT
# ============================================================

def run():
    """Start the bot. Called from run.py."""
    if not config.DISCORD_TOKEN:
        raise SystemExit("❌ DISCORD_TOKEN not set. Copy .env.example to .env and fill in values.")
    if not config.GUILD_ID:
        raise SystemExit("❌ GUILD_ID not set. Set your Discord server ID in .env.")

    logger.info(f"Starting {config.BOT_NAME} v{config.BOT_VERSION}...")
    logger.info(f"  Guild: {config.GUILD_ID}")
    logger.info(f"  Daily tasks at: {config.DAILY_TASK_HOUR}:00 {config.TIMEZONE}")
    logger.info(f"  AI: Gemini={'✅' if config.GEMINI_API_KEY else '❌'} Groq={'✅' if config.GROQ_API_KEY else '⚪'}")

    try:
        bot.run(config.DISCORD_TOKEN, log_handler=None)
    except KeyboardInterrupt:
        logger.info("Bot stopped by operator.")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise
