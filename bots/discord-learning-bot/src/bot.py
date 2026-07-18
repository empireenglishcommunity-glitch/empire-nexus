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

from . import config, database, curriculum, tasks as task_engine, ai_engine, verification, features, ops_hub, ops_poller, ops_monitoring, role_gate, nour_journey

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
    "أوافق": "agree",
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
    "إشعارات": "notifications",
    "نبض": "pulse",
    "صوتي": "portfolio",
    "كلماتي": "words",
    "قدراتي": "abilities",
    "محادثة": "conversation",
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
    """Bawaba B3: send onboarding guide as clean Discord text messages +
    human-recorded Arabic voice clips (if available).

    Replaced the html2img PNG infographic (unreadable on mobile, low-res)
    with native Discord formatting that's always crisp on any device.
    Replaced Kokoro TTS (can't actually speak Arabic — just reads letter
    names) with human-recorded voice clips from the founder.

    Voice clips are optional: if the audio/ directory has MP3 files,
    they're sent. If not (founder hasn't recorded them yet), the text
    guide alone is sufficient — it's the primary onboarding path now.
    """
    from pathlib import Path

    # --- Text-based journey map (replaces the PNG infographic) ---
    try:
        await member.send(
            "🗺️ **رحلتك في 5 خطوات:**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "1️⃣  **سجّل نفسك**\n"
            "    └ اكتب `!انضم` أو اعمل ✅ على أي رسالة\n\n"
            "2️⃣  **كل يوم الساعة 6 الصبح**\n"
            "    └ هتلاقي 7 مهام مرقمة في قناة المهام\n\n"
            "3️⃣  **اعمل المهمة**\n"
            "    └ كل مهمة 10 دقايق: نطق، مفردات، استماع...\n\n"
            "4️⃣  **سجّل إنك خلصت**\n"
            "    └ اكتب رقم المهمة: `!1` أو `!2` ... إلخ\n\n"
            "5️⃣  **شوف تقدمك يكبر 🔥**\n"
            "    └ اكتب `!تقدم` — نقاطك هتزيد كل يوم\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 مش محتاج تعرف إنجليزي عشان تبدأ.\n"
            "كل الأوامر شغالة بالعربي! اكتب `!مساعدة` لو تايه."
        )
        await asyncio.sleep(1)
    except (discord.Forbidden, discord.HTTPException):
        pass

    # --- Human-recorded Arabic audio clips (if available) ---
    media_dir = Path(__file__).resolve().parent.parent / "scripts" / "onboarding"
    audio_dir = media_dir / "audio"
    audio_files = sorted(audio_dir.glob("*.mp3")) if audio_dir.exists() else []
    if audio_files:
        try:
            await member.send(
                "🎧 **اسمع الشرح بالعربي:**",
                files=[discord.File(str(f), filename=f.name) for f in audio_files[:4]],
            )
            await asyncio.sleep(1)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # --- Video link (if configured) ---
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
    # Sync all flags from registry → database (auto-registers new flags on startup)
    added = database.sync_flag_registry()
    if added:
        logger.info(f"Flag registry sync: {added} new flag(s) added to database")
    # Load curriculum data from JSON files
    from . import curriculum
    curriculum.load_all()
    cstats = curriculum.stats()
    logger.info(f"Curriculum: {cstats['total_vocabulary']} words, {cstats['total_speaking_missions']} speaking, {cstats['accent_weeks']} accent weeks")
    logger.info(f"Bot online: {bot.user} | v{config.BOT_VERSION} | {len(bot.guilds)} server(s)")

    # Hisn D023: none of these scheduled loops are channel-scoped -- most
    # of them DM students directly (morning_kickstart, evening_reminder,
    # streak_at_risk, nabd_weekly_summary, nabd_absence_check, the Nour
    # loops), and even the channel-posting ones query the SAME real guild
    # via config.GUILD_ID regardless of which bot instance is running.
    # The ghost bot has its own separate database (confirmed live during
    # H6: a real student who merely joined the guild once was auto-
    # registered into the ghost bot's DB too, via the same on_member_join
    # bug), so left unguarded, every one of these loops would keep
    # targeting real students indefinitely -- not just once at join time.
    # The ghost bot's own documented purpose (manually running commands
    # against a synthetic test account to check behavior against the real
    # guild's role/channel structure) never needed any scheduled loop or
    # background task, so skip starting all of them entirely.
    if config.IS_GHOST_INSTANCE:
        logger.info("IS_GHOST_INSTANCE=true: skipping all scheduled loops, "
                     "ops poller, restart notification, and the API server "
                     "-- ghost bot only needs manual command invocation.")
        return

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
    if not vocab_cheat_sheet_delivery.is_running():
        vocab_cheat_sheet_delivery.start()
    if not daily_word_delivery.is_running():
        daily_word_delivery.start()
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
    if not nour_journey_daily_check.is_running():
        nour_journey_daily_check.start()
    if not markaz_daily_digest.is_running():
        markaz_daily_digest.start()
    if not markaz_weekly_report.is_running():
        markaz_weekly_report.start()
    if not markaz_monthly_summary.is_running():
        markaz_monthly_summary.start()
    # Markaz M2: start the Telegram reply-forwarding poller exactly
    # once. on_ready() can fire more than once per process (e.g. after
    # a gateway reconnect), so guard against starting a second parallel
    # poller — ops_poller.poll_for_replies() also self-guards via
    # ops_poller._running, but checking here too avoids even the
    # log-noise of a rejected duplicate start attempt.
    if not getattr(bot, "_ops_poller_started", False):
        asyncio.create_task(ops_poller.poll_for_replies(bot))
        bot._ops_poller_started = True
    # Markaz M5.1: send restart notification (only on first on_ready,
    # not on gateway reconnects — same guard as the poller).
    if not getattr(bot, "_restart_notified", False):
        asyncio.create_task(ops_monitoring.notify_bot_restart())
        bot._restart_notified = True
    if not heartbeat.is_running():
        heartbeat.start()
    if not morning_kickstart.is_running():
        morning_kickstart.start()
    if not evening_reminder.is_running():
        evening_reminder.start()
    if not streak_at_risk.is_running():
        streak_at_risk.start()
    if not nabd_weekly_summary.is_running():
        nabd_weekly_summary.start()
    if not nabd_absence_check.is_running():
        nabd_absence_check.start()
    # Nour N2: proactive outreach (every 2 hours)
    if not nour_proactive_check.is_running():
        nour_proactive_check.start()
    # Nour N5.1: weekly self-review (Sunday 10 AM)
    if not nour_weekly_review.is_running():
        nour_weekly_review.start()
    # Aql (#15) Phase A6.2: per-student episodic summary regeneration
    # (Sunday 10:30 AM -- 30 minutes after nour_weekly_review, same
    # day since both are "weekly" tasks, but staggered so they don't
    # both hit Groq's API in the exact same minute)
    if not aql_episodic_summary_task.is_running():
        aql_episodic_summary_task.start()
    # Masar M2.2: Nour's Weekly Growth Letter (Wednesday 11 AM,
    # deliberately staggered against Sunday's cluster of weekly tasks)
    if not nour_growth_letter_task.is_running():
        nour_growth_letter_task.start()
    # Sahel S6: start the API server for practice platform connection
    from . import api_server
    await api_server.start_api_server(port=8099)


@bot.event
async def on_member_join(member: discord.Member):
    """Register new members silently. Onboarding DMs are handled by Nour's
    journey (Rawiya R2) after the role-gate is accepted — NOT here.

    Rawiya R8 fix: previously this fired a full Bawaba tutorial DM
    sequence (Egyptian Arabic, 5 steps, multimedia) BEFORE the student
    even accepted rules, creating chaos alongside the Nour journey that
    fires AFTER role-gate accept. Now: just register + assign buddy,
    zero DMs. The student sees #rules and #welcome only until they
    accept, then Nour takes over with her structured MSA journey.
    """
    # Hisn D023: ghost bot guard
    if config.IS_GHOST_INSTANCE:
        return
    database.register_member(str(member.id), member.display_name)
    # Assign buddy (silent — no DM)
    await features.assign_buddy(member, member.guild)

    # Rawiya R8: Discord does NOT clear a member's past reactions from a
    # message when they leave and rejoin the server — a ✅ they left on
    # the rules message from a PREVIOUS visit is still there. Since our
    # role-gate only reacts to the on_raw_reaction_add EVENT (a NEW
    # reaction being added), a returning member whose old reaction is
    # already present gets no event at all and stays locked out until
    # they manually un-react/re-react. Self-heal: check for an existing
    # reaction on rejoin and grant the role immediately if found.
    await role_gate.check_existing_reaction_on_join(member)


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

    # Hisn D023: like on_member_join, reaction events are delivered to
    # every bot instance connected to the guild that shares the message's
    # channel visibility -- the ghost bot's registration flow (auto-register
    # + welcome DM) has no reason to ever run for a real student's ✅
    # reaction. Defense-in-depth alongside the channel-permission isolation
    # (which on its own already blocks the ghost bot from most real
    # channels, but explicit is safer than relying on that alone for a
    # flow this consequential).
    if config.IS_GHOST_INSTANCE:
        return

    # Hissar P1.2: Role-gate — handle ✅ in #rules BEFORE bawaba_reactions
    # so it takes priority. If role_gate handles it, don't fall through.
    guild = bot.get_guild(payload.guild_id) if payload.guild_id else None
    if guild:
        handled = await role_gate.handle_reaction_gate(payload, guild)
        if handled:
            return

    # Check feature flag (use None for discord_id since this is a global check)
    if not database.is_feature_enabled("bawaba_reactions"):
        return

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


@tasks.loop(time=datetime.time(hour=config.DAILY_TASK_HOUR, minute=5, tzinfo=_zone()))
async def morning_kickstart():
    """Nabd N1: Send personal morning kickstart DM to each active student.

    Fires 5 minutes after the daily task post (6:05 AM). For each student:
    - Skip if morning_dm preference is OFF
    - Skip if already completed a task today (don't nag the active)
    - Skip if quiet hours
    - Skip if already sent today (prevent double-sends on restart)
    - Build personal message: greeting, streak, first task, practice link
    - Respect Bawaba B5 language phase
    """
    if not database.is_feature_enabled("nabd_morning"):
        return

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    today = task_engine.today_str()
    members = database.all_active_members()
    sent = 0

    for m in members:
        discord_id = m["discord_id"]

        # Check preferences
        prefs = database.get_notification_prefs(discord_id)
        if not prefs.get("morning_dm", 1):
            continue

        # Skip if quiet hours
        if database.is_quiet_hours(discord_id):
            continue

        # Skip if already sent today
        if database.was_notification_sent(discord_id, "morning_dm", today):
            continue

        # Skip if already completed a task today
        completed = database.count_submissions_for_date(discord_id, today)
        if completed > 0:
            continue

        # Get the member's Discord object
        discord_member = guild.get_member(int(discord_id))
        if not discord_member:
            continue

        # Build personal message
        streak = m.get("current_streak", 0)
        week = database.member_week_number(discord_id)
        allowed_tasks = features.get_allowed_tasks_for_member(discord_id)
        first_task = next((t for t in config.DAILY_TASKS if t["id"] in allowed_tasks), config.DAILY_TASKS[0])

        # Language phase (Bawaba B5)
        phase = features.response_language(discord_id)

        # Practice platform link
        day_index = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"].index(task_engine.current_day_name()) if task_engine.current_day_name() in ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"] else 0
        practice_url = curriculum.practice_platform_day_url(week, day_index, m.get("level", "L0"))

        if phase == "arabic":
            streak_text = f"\U0001f525 \u0633\u0644\u0633\u0644\u062a\u0643: **{streak}** \u064a\u0648\u0645" if streak > 0 else "\U0001f331 \u0627\u0628\u062f\u0623 \u0633\u0644\u0633\u0644\u0629 \u062c\u062f\u064a\u062f\u0629 \u0627\u0644\u0646\u0647\u0627\u0631\u062f\u0629!"
            msg = (
                f"\U0001f305 \u0635\u0628\u0627\u062d \u0627\u0644\u062e\u064a\u0631 **{m['discord_name']}**!\n\n"
                f"\u0645\u0647\u0627\u0645\u0643 \u062c\u0627\u0647\u0632\u0629 \U0001f4cb\n"
                f"{streak_text}\n\n"
                f"\u0623\u0648\u0644 \u0645\u0647\u0645\u0629: **{first_task['name_ar']}** {first_task['emoji']}\n"
                f"\U0001f310 \u0627\u062a\u0645\u0631\u0646 \u0623\u0648\u0646\u0644\u0627\u064a\u0646: {practice_url}\n\n"
                f"\u0627\u0643\u062a\u0628 `!1` \u0644\u0645\u0627 \u062a\u062e\u0644\u0635 \U0001f4aa"
            )
        elif phase == "bilingual_ar":
            streak_text = f"\U0001f525 \u0633\u0644\u0633\u0644\u0629 (Streak): **{streak}** \u064a\u0648\u0645" if streak > 0 else "\U0001f331 \u0627\u0628\u062f\u0623 \u0633\u0644\u0633\u0644\u0629 \u062c\u062f\u064a\u062f\u0629! (Start a new streak!)"
            msg = (
                f"\U0001f305 \u0635\u0628\u0627\u062d \u0627\u0644\u062e\u064a\u0631 **{m['discord_name']}**!\n\n"
                f"\u0645\u0647\u0627\u0645\u0643 \u062c\u0627\u0647\u0632\u0629 (Tasks ready) \U0001f4cb\n"
                f"{streak_text}\n\n"
                f"\u0623\u0648\u0644 \u0645\u0647\u0645\u0629 (First task): **{first_task['name_ar']}** ({first_task['name']}) {first_task['emoji']}\n"
                f"\U0001f310 Practice online: {practice_url}\n\n"
                f"\u0627\u0643\u062a\u0628 `!1` \u0644\u0645\u0627 \u062a\u062e\u0644\u0635 (type `!1` when done) \U0001f4aa"
            )
        else:
            streak_text = f"\U0001f525 Streak: **{streak}** days" if streak > 0 else "\U0001f331 Start a new streak today!"
            msg = (
                f"\U0001f305 Good morning **{m['discord_name']}**!\n\n"
                f"Your tasks are ready \U0001f4cb\n"
                f"{streak_text}\n\n"
                f"First task: **{first_task['name']}** {first_task['emoji']}\n"
                f"\U0001f310 Practice online: {practice_url}\n\n"
                f"Type `!1` when done \U0001f4aa"
            )

        try:
            await discord_member.send(msg)
            database.log_notification(discord_id, "morning_dm", today)
            sent += 1
        except (discord.Forbidden, discord.HTTPException):
            pass

        # Rate limit: don't spam Discord's DM API
        await asyncio.sleep(0.5)

    if sent > 0:
        logger.info(f"Nabd morning kickstart: sent to {sent} member(s)")


@tasks.loop(time=datetime.time(hour=20, minute=0, tzinfo=_zone()))
async def evening_reminder():
    """Nabd N2: Evening incomplete reminder (8 PM).

    Sends a personal DM to students who completed 1-6 tasks today
    (partial — encourage them to finish). Students with 0 tasks are
    handled by streak_at_risk instead. Students with 7 are done.
    """
    if not database.is_feature_enabled("nabd_evening"):
        return

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    today = task_engine.today_str()
    members = database.all_active_members()
    sent = 0

    for m in members:
        discord_id = m["discord_id"]
        prefs = database.get_notification_prefs(discord_id)
        if not prefs.get("evening_dm", 1):
            continue
        if database.is_quiet_hours(discord_id):
            continue
        if database.was_notification_sent(discord_id, "evening_dm", today):
            continue

        completed_count = database.count_submissions_for_date(discord_id, today)
        if completed_count == 0 or completed_count >= 7:
            continue  # 0 = streak_at_risk handles it; 7 = all done

        discord_member = guild.get_member(int(discord_id))
        if not discord_member:
            continue

        remaining = 7 - completed_count
        # Find remaining task names
        completed_ids = [s["task_id"] for s in database.get_submissions_for_date(discord_id, today)]
        allowed = features.get_allowed_tasks_for_member(discord_id)
        remaining_tasks = [t for t in config.DAILY_TASKS if t["id"] in allowed and t["id"] not in completed_ids]

        phase = features.response_language(discord_id)
        if phase == "arabic":
            task_list = "\n".join(f"  • {t['name_ar']} (`!{i+1}`)" for i, t in enumerate(config.DAILY_TASKS) if t["id"] in [rt["id"] for rt in remaining_tasks])
            msg = (
                f"\u23f0 \u0639\u0646\u062f\u0643 **{remaining}** \u0645\u0647\u0627\u0645 \u0644\u0633\u0647 \u0627\u0644\u0646\u0647\u0627\u0631\u062f\u0629.\n\n"
                f"\u0627\u0644\u0645\u062a\u0628\u0642\u064a:\n{task_list}\n\n"
                f"\U0001f4a1 \u0623\u0633\u0631\u0639 \u0645\u0647\u0645\u0629: **\u0645\u0634\u0627\u0631\u0643\u0629 \u0645\u062c\u062a\u0645\u0639\u064a\u0629** \u2014 \u0627\u0643\u062a\u0628 \u062c\u0645\u0644\u0629 \u0641\u064a #general-chat \u0648\u0627\u0643\u062a\u0628 `!7`"
            )
        else:
            task_list = "\n".join(f"  • {t['name']} (`!{config.DAILY_TASKS.index(t)+1}`)" for t in remaining_tasks[:5])
            msg = (
                f"\u23f0 You have **{remaining}** tasks remaining today.\n\n"
                f"Remaining:\n{task_list}\n\n"
                f"\U0001f4a1 Quickest: **Community** \u2014 type a sentence in #general-chat then `!7`"
            )

        try:
            await discord_member.send(msg)
            database.log_notification(discord_id, "evening_dm", today)
            sent += 1
        except (discord.Forbidden, discord.HTTPException):
            pass
        await asyncio.sleep(0.5)

    if sent > 0:
        logger.info(f"Nabd evening reminder: sent to {sent} member(s)")


@tasks.loop(time=datetime.time(hour=21, minute=0, tzinfo=_zone()))
async def streak_at_risk():
    """Nabd N2: Streak-at-risk alert (9 PM).

    Urgent DM to students with streak >= 3 who completed ZERO tasks today.
    Their streak will break at midnight if they don't do at least one task.
    """
    if not database.is_feature_enabled("nabd_streak_alert"):
        return

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    today = task_engine.today_str()
    members = database.all_active_members()
    sent = 0

    for m in members:
        discord_id = m["discord_id"]
        streak = m.get("current_streak", 0)
        if streak < 3:
            continue

        prefs = database.get_notification_prefs(discord_id)
        if not prefs.get("streak_alert", 1):
            continue
        if database.is_quiet_hours(discord_id):
            continue
        if database.was_notification_sent(discord_id, "streak_alert", today):
            continue

        completed = database.count_submissions_for_date(discord_id, today)
        if completed > 0:
            continue  # streak is safe

        discord_member = guild.get_member(int(discord_id))
        if not discord_member:
            continue

        phase = features.response_language(discord_id)
        if phase == "arabic":
            msg = (
                f"\u26a0\ufe0f **\u0633\u0644\u0633\u0644\u062a\u0643 ({streak} \u064a\u0648\u0645) \u0647\u062a\u0646\u0643\u0633\u0631 \u0627\u0644\u0644\u064a\u0644\u0629!**\n\n"
                f"\u0644\u0648 \u0639\u0645\u0644\u062a \u0645\u0647\u0645\u0629 \u0648\u0627\u062d\u062f\u0629 \u0628\u0633 \u0642\u0628\u0644 12 \u0627\u0644\u0644\u064a\u0644\u060c \u0647\u062a\u062d\u0627\u0641\u0638 \u0639\u0644\u064a\u0647\u0627.\n\n"
                f"\U0001f4a1 \u0623\u0633\u0647\u0644 \u062d\u0627\u062c\u0629 \u062a\u0639\u0645\u0644\u0647\u0627 \u062f\u0644\u0648\u0642\u062a\u064a:\n"
                f"\u0627\u0643\u062a\u0628 \u062c\u0645\u0644\u0629 \u0648\u0627\u062d\u062f\u0629 \u0641\u064a #general-chat \u0648\u0628\u0639\u062f\u064a\u0646 \u0627\u0643\u062a\u0628 `!7`\n\n"
                f"\u0645\u0627 \u062a\u0636\u064a\u0639\u0634 **{streak} \u064a\u0648\u0645** \u0634\u063a\u0644! \U0001f525"
            )
        else:
            msg = (
                f"\u26a0\ufe0f **Your streak ({streak} days) will break tonight!**\n\n"
                f"Complete just ONE task before midnight to save it.\n\n"
                f"\U0001f4a1 Easiest thing to do right now:\n"
                f"Type a sentence in #general-chat then type `!7`\n\n"
                f"Don't lose **{streak} days** of work! \U0001f525"
            )

        try:
            await discord_member.send(msg)
            database.log_notification(discord_id, "streak_alert", today)
            sent += 1
        except (discord.Forbidden, discord.HTTPException):
            pass
        await asyncio.sleep(0.5)

    if sent > 0:
        logger.info(f"Nabd streak-at-risk: sent to {sent} member(s)")


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
        except (discord.Forbidden, discord.HTTPException):
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
                    except (discord.Forbidden, discord.HTTPException):
                        pass


def _now():
    """Current datetime helper (redefined at module level for tasks)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo(config.TIMEZONE))
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


# --- Additional Scheduled Tasks (from blueprint Phase 4-6) ---

@tasks.loop(time=datetime.time(hour=20, minute=5, tzinfo=_zone()))
async def friday_feedback_survey():
    """Send weekly feedback survey every Friday evening (8:05 PM).

    D022 fix (Hisn H4.6): staggered 5 minutes after evening_reminder
    (also 20:00) to avoid sending 2 individual DMs to the same
    partially-completed student within the same instant every Friday.
    """
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


@tasks.loop(time=datetime.time(hour=config.DAILY_TASK_HOUR, minute=15, tzinfo=_zone()))
async def vocab_cheat_sheet_delivery():
    """Post Weekly Vocabulary Cheat Sheet on Sunday in #cheat-sheets.

    Sahin Phase 4: the Weekly Vocabulary Cheat Sheet prompt was fully
    designed months ago (content/prompts/cheat_sheets.json, prompt #1)
    but NEVER wired up to post anywhere — the same "designed but never
    built" pattern found repeatedly in this project (D012, D020, D036).
    This is the fix.

    Uses pre-authored curriculum vocabulary data (same source as
    daily_word_delivery() and the daily vocab task), NOT AI-generated —
    more reliable, no Groq/Gemini dependency, uses real curated words.

    Fires every Sunday at DAILY_TASK_HOUR:15 (deliberately a different
    day than Wednesday's grammar card, per Masar M2's established
    "don't cluster weekly posts on the same day" precedent).

    Gated behind the `vocab_cheat_sheet` feature flag (default OFF),
    per Aegis's flag-then-release discipline.
    """
    if _now().weekday() != 6:  # 6 = Sunday
        return

    if config.IS_GHOST_INSTANCE:
        return

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    channel = discord.utils.get(guild.text_channels, name="cheat-sheets")
    if not channel:
        logger.warning("vocab_cheat_sheet_delivery: #cheat-sheets channel not found")
        return

    for level_key in ["L0", "L1", "L2", "L3"]:
        members = database.members_at_level(level_key)
        if not members:
            continue

        discord_id = members[0]["discord_id"]
        if not database.is_feature_enabled("vocab_cheat_sheet", discord_id):
            continue

        week = database.member_week_number(discord_id)
        sheet = features.format_vocab_cheat_sheet(week, level_key)
        if not sheet:
            logger.info(f"No vocab content for {level_key} week {week} — skipped")
            continue

        try:
            await channel.send(sheet)
            logger.info(f"Vocab cheat sheet posted for {level_key} week {week}")
        except discord.HTTPException as e:
            logger.error(f"Failed to post vocab cheat sheet for {level_key}: {e}")


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


@tasks.loop(time=datetime.time(hour=config.DAILY_TASK_HOUR, minute=45, tzinfo=_zone()))
async def daily_word_delivery():
    """Post Word of the Day in #daily-word every morning.

    Sahin Phase 3 finding: the bot's own daily task message tells
    students "Post in #daily-word (use today's word in a sentence)" —
    but nothing ever actually delivered a "word of the day" to that
    channel. This is the fix: picks ONE word from today's curriculum
    vocabulary (same data source as the daily vocab task) and posts it
    as a short, bilingual, inviting message students can respond to.

    Fires daily at DAILY_TASK_HOUR:45 (15 min after the daily tasks
    post at :00, and 15 min after grammar_card_delivery at :30 — so
    all three never collide). Uses the lowest-level members' current
    week to pick the word, matching daily_task_post()'s own logic for
    determining which curriculum week to use.
    """
    import random

    if config.IS_GHOST_INSTANCE:
        return

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    channel = discord.utils.get(guild.text_channels, name="daily-word")
    if not channel:
        logger.warning("daily_word_delivery: #daily-word channel not found")
        return

    # Use L0 members' week (the largest cohort, and L0's vocabulary is
    # the most useful for a mixed-level "word of the day" since higher-
    # level students already know L0 words and can still engage, while
    # L0 students are actively learning them). Fall back to week 1 if
    # no L0 members exist yet.
    members = database.members_at_level("L0")
    if members:
        week = database.member_week_number(members[0]["discord_id"])
    else:
        week = 1

    # Get today's day index (0=Saturday...6=Friday per curriculum convention)
    today = _now()
    day_index = (today.weekday() + 2) % 7  # Python: Mon=0; curriculum: Sat=0

    words = curriculum.get_vocabulary_for_day(week, day_index, "L0")
    if not words:
        # Fallback: try the full week's vocab and pick randomly
        words = curriculum.get_vocabulary_for_week(week, "L0")
    if not words:
        logger.info("daily_word_delivery: no vocabulary available, skipping")
        return

    word = random.choice(words)

    # Format the post — bilingual, inviting, simple
    msg = (
        f"📖 **Word of the Day | كلمة اليوم**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔤 **{word['word']}**\n"
        f"🔊 {word.get('pronunciation', '')}\n"
        f"📝 {word.get('arabic', '')}\n"
        f"🏷️ _{word.get('pos', '')}_\n\n"
        f"✍️ **اكتب جملة باستخدام هذه الكلمة!**\n"
        f"Write a sentence using this word below 👇"
    )

    try:
        await channel.send(msg)
        logger.info(f"Daily word posted: {word['word']} (L0 week {week})")
    except discord.HTTPException as e:
        logger.error(f"Failed to post daily word: {e}")


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


@tasks.loop(time=datetime.time(hour=7, minute=0, tzinfo=_zone()))
async def markaz_daily_digest():
    """Markaz Phase M1.1/M1.2 — morning Telegram digest (7 AM Dubai time).

    Summarizes YESTERDAY's activity in one phone-readable message via
    the Empire Ops bot: active students, tasks completed, new
    registrations, streak milestones, Nour conversations, and pending
    escalations. Gated behind 'markaz_daily_digest' so it can be
    disabled instantly without a redeploy if it ever misbehaves.
    """
    if not database.is_feature_enabled("markaz_daily_digest"):
        return

    yesterday = (datetime.datetime.now(_zone()).date() - datetime.timedelta(days=1))
    yesterday_str = yesterday.isoformat()
    display_date = yesterday.strftime("%B %-d")

    total_active = database.member_count()
    active_yesterday = database.count_active_members_on(yesterday_str)
    tasks_done = database.total_submissions_on_date(yesterday_str)
    new_members = database.count_new_members_on(yesterday_str)
    milestones = database.streak_milestones_on(yesterday_str)
    nour_convos = database.count_nour_conversations_on(yesterday_str)
    # Markaz M2: now persisted in the DB (survives restarts), not an
    # in-memory dict on the nour_escalation module.
    pending_escalations = database.count_pending_escalations()

    lines = [
        f"📊 *Daily Digest — {ops_hub.escape_markdown(display_date)}*",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"👥 Active students: *{active_yesterday}/{total_active}*",
        f"✅ Tasks completed: *{tasks_done}*",
    ]
    if milestones:
        m_text = ", ".join(
            f"{ops_hub.escape_markdown(m['discord_name'])} {m['days']}d" for m in milestones
        )
        lines.append(f"🔥 Streak milestones: {len(milestones)} \\({m_text}\\)")
    else:
        lines.append("🔥 Streak milestones: 0")
    lines.append(f"🆕 New registrations: {new_members}")
    lines.append(f"💬 Nour conversations: {nour_convos}")
    lines.append(f"🚨 Pending escalations: {pending_escalations}")

    # Hissar P6: Security monitoring section
    if database.is_feature_enabled("hissar_ip_detection"):
        sec = database.get_security_stats()
        lines.append("")
        lines.append("🏰 *Security \\(Hissar\\):*")
        lines.append(f"   🔍 Tracked tokens: {sec['total_tracked_tokens']}")
        if sec["flagged_tokens"] > 0:
            lines.append(f"   ⚠️ *Flagged \\(5\\+ IPs\\): {sec['flagged_tokens']}*")
            for s in sec["suspicious"][:3]:
                safe_name = ops_hub.escape_markdown(s["discord_name"])
                lines.append(f"      • {safe_name}: {s['ip_count']} IPs")
        else:
            lines.append("   ✅ No suspicious token sharing detected")

    lines.append("")
    lines.append(
        "*All systems healthy\\.* ✅" if pending_escalations == 0
        else f"⚠️ *{pending_escalations} escalation\\(s\\) awaiting your reply\\.*"
    )

    await ops_hub.send_ops_message("\n".join(lines))
    # M4.4: check for churn risk as part of the morning ops cycle
    await ops_monitoring.check_churn_risk()
    # Wuslah W0.4: clean up expired link tokens (daily housekeeping)
    removed = database.cleanup_expired_tokens(days=30)
    if removed > 0:
        logger.info(f"Wuslah: cleaned up {removed} expired link token(s)")


@tasks.loop(time=datetime.time(hour=9, minute=0, tzinfo=_zone()))
async def markaz_weekly_report():
    """Markaz Phase M4.1/M4.2 — weekly business report (Sunday 9 AM Dubai).

    Only fires on Sundays. Sends a comprehensive business dashboard to
    the owner via the Empire Ops bot."""
    now = datetime.datetime.now(_zone())
    if now.weekday() != 6:  # 6 = Sunday
        return
    await ops_monitoring.send_weekly_report()


@tasks.loop(time=datetime.time(hour=9, minute=30, tzinfo=_zone()))
async def markaz_monthly_summary():
    """Markaz Phase M4.5 — monthly summary (1st of month, 9:30 AM Dubai).

    Only fires on the 1st. Sends engagement tiers and revenue potential
    overview to the owner via the Empire Ops bot."""
    await ops_monitoring.send_monthly_summary()


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


@tasks.loop(time=datetime.time(hour=1, minute=0, tzinfo=_zone()))
async def nour_journey_daily_check():
    """Rawiya R2/R8: advance time-based onboarding journey steps once
    per day (platform_intro -> streaks_explained -> channels_tour ->
    independent). Runs once daily, well after midnight, so it fires at
    most once per calendar day per student regardless of when they
    joined. Safe no-op for every student not currently on one of these
    specific steps (check_advancement's own step-transition table
    already guards this — this loop just supplies the 'day_passed'
    trigger to everyone with an active journey).
    """
    if not database.is_feature_enabled("nour_journey"):
        return
    conn = database._connect()
    rows = conn.execute(
        "SELECT discord_id FROM student_journey WHERE completed_at IS NULL"
    ).fetchall()
    conn.close()
    for row in rows:
        await nour_journey.check_advancement(row["discord_id"], "day_passed", bot)


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


@tasks.loop(time=datetime.time(hour=20, minute=30, tzinfo=_zone()))
async def nabd_weekly_summary():
    """Nabd N4: Friday evening personal progress summary DM."""
    if _now().weekday() != 4:  # 4 = Friday
        return
    if not database.is_feature_enabled("nabd_weekly_summary"):
        return

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    today = task_engine.today_str()
    members = database.all_active_members()

    for m in members:
        discord_id = m["discord_id"]
        prefs = database.get_notification_prefs(discord_id)
        if not prefs.get("weekly_summary", 1):
            continue
        if database.was_notification_sent(discord_id, "weekly_summary", today):
            continue

        discord_member = guild.get_member(int(discord_id))
        if not discord_member:
            continue

        # Calculate this week vs last week
        completion = task_engine.calculate_completion_rate(discord_id, days=7)

        streak = m.get("current_streak", 0)
        phase = features.response_language(discord_id)

        # Tier-based encouragement
        if completion >= 80:
            encourage_ar = "🌟 أداء ممتاز! استمر كده."
            encourage_en = "🌟 Excellent performance! Keep it up."
        elif completion >= 60:
            encourage_ar = "💪 كويس! حاول تزود مهمة واحدة يوميًا."
            encourage_en = "💪 Good! Try to add one more task per day."
        elif completion >= 40:
            encourage_ar = "⚠️ محتاج تلتزم أكتر — حتى 3 مهام يوميًا كافية."
            encourage_en = "⚠️ Need more consistency — even 3 tasks/day is enough."
        else:
            encourage_ar = "❗ الأسبوع ده كان صعب. هل محتاج مساعدة؟ كلمنا في #support"
            encourage_en = "❗ Tough week. Need help? Reach out in #support"

        bar = "█" * int(completion / 10) + "░" * (10 - int(completion / 10))

        if phase == "arabic":
            msg = (
                f"📊 **ملخص الأسبوع:**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📈 نسبة الإنجاز: [{bar}] **{completion}%**\n"
                f"🔥 سلسلة: **{streak}** يوم\n"
                f"🏆 النقاط: **{m['total_points']}**\n\n"
                f"{encourage_ar}\n\n"
                f"*النظام بيشتغل لما انت تشتغل.* 🏛️"
            )
        else:
            msg = (
                f"📊 **Weekly Summary:**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📈 Completion: [{bar}] **{completion}%**\n"
                f"🔥 Streak: **{streak}** days\n"
                f"🏆 Points: **{m['total_points']}**\n\n"
                f"{encourage_en}\n\n"
                f"*The system works when you work.* 🏛️"
            )

        try:
            await discord_member.send(msg)
            database.log_notification(discord_id, "weekly_summary", today)
        except (discord.Forbidden, discord.HTTPException):
            pass
        await asyncio.sleep(0.5)


@tasks.loop(time=datetime.time(hour=10, minute=5, tzinfo=_zone()))
async def nabd_absence_check():
    """Nabd N5: daily absence recovery check (10:05 AM).

    D022 fix (Hisn H4.6): staggered 5 minutes after weekly_assessment
    (also 10:00 Sunday) to avoid sending 2 individual DMs to the same
    student within the same instant every Sunday.
    """
    guild = bot.get_guild(config.GUILD_ID)
    if guild:
        await features.check_absence_recovery(guild)


@tasks.loop(hours=2)
async def nour_proactive_check():
    """Nour N2: proactive outreach — check every 2 hours for students who need attention."""
    from . import nour_proactive
    try:
        await nour_proactive.run_proactive_checks(bot)
    except Exception as e:
        logger.error(f"Nour proactive check error: {e}")


@tasks.loop(time=datetime.time(hour=10, minute=0, tzinfo=_zone()))
async def nour_weekly_review():
    """Nour N5.1: weekly self-review — runs every Sunday at 10 AM."""
    if _now().weekday() != 6:  # 6 = Sunday
        return
    from . import nour_personality
    try:
        await nour_personality.run_weekly_review(bot)
    except Exception as e:
        logger.error(f"Nour weekly review error: {e}")


@tasks.loop(time=datetime.time(hour=10, minute=30, tzinfo=_zone()))
async def aql_episodic_summary_task():
    """Aql (#15) Phase A6.2: regenerate every active student's episodic
    summary once a week (design.md Section 6). Runs Sunday only, 30
    minutes after nour_weekly_review, so both weekly Groq-summarization
    jobs don't fire in the same minute.

    Gated behind 'aql_episodic_summaries' (default OFF): even though
    writing new nour_episodic_summaries rows has zero effect on
    anything Nour's CURRENT live response path reads, this task would
    otherwise start consuming real Groq API quota against every real
    student's real conversation history on a schedule, the moment this
    PR merges -- a genuine live side effect, not the "zero live
    effect" every other Aql phase has maintained. The flag makes this
    phase's actual first live behavior an explicit, deliberate, later
    decision (per this codebase's established deploy-dormant/release-
    separately discipline), not an accidental side effect of building
    the mechanism.
    """
    if not database.is_feature_enabled("aql_episodic_summaries"):
        return
    if _now().weekday() != 6:  # 6 = Sunday
        return
    from . import nour_personality
    try:
        count = await nour_personality.run_weekly_episodic_summaries(bot)
        logger.info(f"Aql episodic summaries: regenerated for {count} student(s)")
    except Exception as e:
        logger.error(f"Aql episodic summary task error: {e}")


@tasks.loop(time=datetime.time(hour=11, minute=0, tzinfo=_zone()))
async def nour_growth_letter_task():
    """Masar M2.2: Nour's Weekly Growth Letter — the flagship fix for
    Hisn D020 (the AI tips engine that was designed but never built).

    Runs every WEDNESDAY at 11 AM Dubai time. Deliberately placed on a
    different DAY than every other once-a-week task in this codebase
    (markaz_weekly_report 09:00 Sun, weekly_assessment 10:00 Sun,
    nour_weekly_review 10:00 Sun all cluster on Sunday) — not just a
    different minute on the same day, to actually spread the weekly
    notification load across the week rather than bunching 4 separate
    DM/report bursts onto students and the owner on one single day.
    11:00 also doesn't collide with any daily fixed-time task (00:00,
    06:00, 06:05, 07:00, 20:00, 21:00) — checked against the FULL
    current schedule per the D022 lesson from Hisn, not assumed.

    For each active member: gather_signals() -> build_growth_letter()
    -> store in nour_growth_letters -> DM the student. Same content is
    then available to the dashboard via GET /api/growth-letter (M2.4)
    with zero duplicate generation.

    Deliberately NO top-level no-discord_id flag check here (a bug
    caught and fixed in this same phase, in the /api/growth-letter
    endpoint below): is_feature_enabled(name) with no discord_id only
    returns True when the flag's allowed_ids is EMPTY. A top-level
    guard here, before iterating members, would make the ENTIRE task
    skip for EVERYONE whenever the flag is scoped to a restricted
    allowlist (the beta-squad rollout case) — silently defeating the
    exact gradual-rollout capability the flag exists to support. The
    per-member check inside the loop below is both correct and
    sufficient: if the flag is fully OFF, every member fails that
    check and nothing sends; if it's ON for everyone, every member
    passes; if restricted, only allowlisted members pass.
    """
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    from . import narrative_engine

    members = database.all_active_members()
    sent = 0
    failed = 0

    for m in members:
        discord_id = m["discord_id"]

        # Same per-member allowlist support as every other masar_*
        # flag check -- lets a rollout start with a trusted few before
        # everyone, consistent with this codebase's established
        # gradual-rollout pattern.
        if not database.is_feature_enabled("masar_growth_letter", discord_id):
            continue

        discord_member = guild.get_member(int(discord_id))
        if not discord_member:
            continue

        try:
            signals = narrative_engine.gather_signals(discord_id)
            if not signals:
                continue
            letter_text, source = await narrative_engine.build_growth_letter(signals)

            week = signals.get("week", 0)
            database.store_growth_letter(discord_id, letter_text, source, week)

            phase = features.response_language(discord_id)
            if phase == "arabic" or phase == "bilingual_ar":
                header = "\U0001f4dd رسالة نور الأسبوعية:\n\n"
            else:
                header = "\U0001f4dd Nour's Weekly Growth Letter:\n\n"

            await discord_member.send(header + letter_text)
            sent += 1
        except (discord.Forbidden, discord.HTTPException):
            failed += 1
        except Exception as e:
            logger.error(f"Masar growth letter error for {discord_id}: {e}")
            failed += 1

        # Rate limit: don't spam Discord's DM API
        await asyncio.sleep(0.5)

    if sent > 0 or failed > 0:
        logger.info(f"Masar growth letter task: sent to {sent} member(s), {failed} failed")


# ============================================================
#  MEMBER COMMANDS
# ============================================================

@bot.command(name="agree")
async def cmd_agree(ctx):
    """Accept server rules and unlock channels (Hissar P1.2 role-gate)."""
    await role_gate.cmd_agree(ctx)


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


@bot.command(name="gender")
async def cmd_gender(ctx, value: str = ""):
    """Masar D033 fix: set your gender so Nour addresses you correctly
    in Egyptian Arabic (masculine/feminine second-person grammar
    differ -- "عليك" vs "عليكي", "انت" vs "انتي"). Entirely optional
    and skippable -- until set, Nour uses gender-neutral phrasing, she
    never guesses. Usage: !gender male | !gender female | !gender clear
    """
    value = value.strip().lower()
    valid = {
        "male": "male", "m": "male", "ذكر": "male", "رجل": "male",
        "female": "female", "f": "female", "أنثى": "female", "انثى": "female", "ست": "female",
        "clear": "", "none": "", "reset": "",
    }
    if value not in valid:
        await ctx.send(
            "Usage: `!gender male` or `!gender female` (or `!gender clear` to reset). "
            "This is optional — it just helps Nour address you correctly in Arabic. "
            "\nاستخدم `!gender male` أو `!gender female` (أو `!gender clear` للحذف) — "
            "اختياري تماماً، بيساعد نور تتكلم معاك بالصيغة الصحيحة."
        )
        return

    discord_id = str(ctx.author.id)
    member = database.get_member(discord_id)
    if not member:
        await ctx.send("You're not registered yet. Use `!join` to start.")
        return

    database.update_member(discord_id, gender=valid[value])
    if valid[value] == "male":
        await ctx.send("✅ Got it — Nour will address you as male. / تمام، نور هتتكلم معاك كراجل.")
    elif valid[value] == "female":
        await ctx.send("✅ Got it — Nour will address you as female. / تمام، نور هتتكلم معاكي كستّ.")
    else:
        await ctx.send("✅ Cleared — Nour will use gender-neutral phrasing. / تمام، نور هتستخدم صيغة عامة.")


async def _score_pronunciation(ctx, task_id: str):
    """Dhaka' P1: background pronunciation scoring.

    Downloads the student's audio, transcribes via Whisper, compares to
    expected text, generates feedback, and DMs the student with results.
    Runs as asyncio.create_task() — never blocks the main !done flow.
    All errors are caught and logged (never crash the bot).
    """
    try:
        from . import pronunciation_scorer, curriculum

        discord_id = str(ctx.author.id)
        member_data = database.get_member(discord_id)
        if not member_data:
            return

        # Get the audio URL
        audio_info = await verification.get_recent_audio_url(ctx.author, ctx.guild, task_id)
        if not audio_info:
            logger.info(f"Pronunciation scoring: no audio found for {discord_id}/{task_id}")
            return
        audio_url, filename = audio_info

        # Get the expected text for this task
        level = member_data.get("level", "L0")
        week = database.member_week_number(discord_id)
        day_name = task_engine.current_day_name()
        day_index = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"].index(day_name) \
            if day_name in ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"] else 0

        daily = curriculum.get_daily_content(week, day_name, day_index, level)

        if task_id == "accent":
            expected_text = (daily.get("accent_drill") or {}).get("record_this", "")
        elif task_id == "shadow":
            # Shadowing uses the same record_this text as accent (the sentence
            # students practice saying — same source in generate.py's gen_shadowing)
            expected_text = (daily.get("accent_drill") or {}).get("record_this", "")
        else:
            expected_text = ""

        if not expected_text:
            logger.info(f"Pronunciation scoring: no expected text for {discord_id}/{task_id} w{week}d{day_index}")
            return

        # Run the full scoring pipeline
        result = await pronunciation_scorer.score_recording(
            audio_url=audio_url,
            expected_text=expected_text,
            discord_id=discord_id,
            task_id=task_id,
            level=level,
            filename=filename,
        )

        if not result.success:
            logger.warning(f"Pronunciation scoring failed for {discord_id}: {result.error}")
            return

        # DM the student with their score
        try:
            if result.is_beginner_grace:
                # First 3 recordings: encouragement only, no number
                await ctx.author.send(
                    f"🎙️ **Recording received!**\n\n"
                    f"💬 {result.feedback_en}\n"
                    f"💬 {result.feedback_ar}\n\n"
                    f"_Detailed scoring starts after your first 3 recordings._"
                )
            else:
                score_emoji = "🟢" if result.score >= 80 else "🟡" if result.score >= 60 else "🟠"
                stars = "⭐" * int(result.score / 20)  # 0-5 stars
                await ctx.author.send(
                    f"🎯 **Pronunciation Score** {stars}\n\n"
                    f"{score_emoji} **{result.score:.0f}%**\n\n"
                    f"💬 {result.feedback_en}\n"
                    f"💬 {result.feedback_ar}"
                    + (f"\n\n🔑 **Focus on:** {', '.join(result.missed_words[:3])}" if result.missed_words else "")
                )
        except (discord.Forbidden, discord.HTTPException):
            pass  # DMs disabled

        # A0.3: Check adaptive difficulty after scoring
        from . import adaptive_engine
        adjustment = adaptive_engine.check_and_adjust(discord_id)
        if adjustment:
            # A0.4 / Masar M4 (R5, fixes the D012/D020-style transparency
            # gap for adaptive difficulty): when masar_difficulty_notes is
            # enabled AND this member hasn't received a difficulty_change
            # notification in the last 7 days (throttle — the ADJUSTMENT
            # itself is never throttled, only the notification, per R5's
            # anti-spam acceptance criterion), send Nour's own voiced,
            # gender-aware, direction-positive note via narrative_engine
            # instead of the old hardcoded bilingual message below. When
            # the flag is off, the original A0.4 message is preserved
            # unchanged — no regression of this already-shipped Tatawwur
            # behavior for members not opted into Masar's new surface.
            sent_narrative_note = False
            if database.is_feature_enabled("masar_difficulty_notes", discord_id):
                if not database.was_notification_sent_within(discord_id, "difficulty_change", days=7):
                    try:
                        from . import narrative_engine
                        signals = narrative_engine.gather_signals(discord_id)
                        message, _source = await narrative_engine.build_difficulty_note(
                            discord_id, adjustment["direction"], signals,
                        )
                        await ctx.author.send(message)
                        database.log_notification(
                            discord_id, "difficulty_change",
                            datetime.date.today().isoformat(),
                        )
                        sent_narrative_note = True
                    except (discord.Forbidden, discord.HTTPException):
                        sent_narrative_note = True  # DMs disabled — don't fall through to the old message either
                    except Exception as e:
                        logger.error(f"Masar difficulty note error for {discord_id}: {e}")
                else:
                    # Throttled: an adjustment still happened (see check_and_adjust
                    # above, unaffected by this throttle), just no NEW notification
                    # this time — same "adjustment always applies, notification may
                    # not" split R5 requires.
                    sent_narrative_note = True

            if not sent_narrative_note:
                # A0.4 (pre-Masar, original behavior — sent when the flag is
                # off, so nothing regresses for members not on the new flag).
                try:
                    if adjustment["direction"] == "up":
                        msg = (
                            f"📈 **Level Up! / مستواك ارتفع!**\n\n"
                            f"{adjustment['emoji']} Your difficulty is now: **{adjustment['label']}**\n\n"
                            f"Your average score ({adjustment['average']:.0f}%) shows you're ready "
                            f"for more challenge. Tasks will be a bit harder now!\n\n"
                            f"متوسط درجاتك ({adjustment['average']:.0f}%) بيقول إنك جاهز "
                            f"لتحدي أكبر. المهام هتكون أصعب شوية! 💪"
                        )
                    else:
                        msg = (
                            f"🌱 **Adjusting difficulty / بنعدّل المستوى**\n\n"
                            f"{adjustment['emoji']} Your difficulty is now: **{adjustment['label']}**\n\n"
                            f"No worries! We're giving you more practice time on the basics. "
                            f"Everyone learns at their own pace.\n\n"
                            f"متقلقش! بنديك وقت أكتر على الأساسيات. "
                            f"كل واحد بيتعلم بسرعته. استمر! 🌟"
                        )
                    await ctx.author.send(msg)
                except (discord.Forbidden, discord.HTTPException):
                    pass

    except Exception as e:
        logger.error(f"Pronunciation scoring error for {ctx.author.id}/{task_id}: {e}")


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
        #
        # Hisn D026: verify_task() needs a real discord.Member + guild to
        # search channel history for the student's actual submission
        # (recording/text) -- it can never do that from a DM, since a DM
        # has no guild and ctx.author there is a discord.User, not a
        # discord.Member. The ORIGINAL code's `if isinstance(...)` guard
        # only ever ran verify_task() when in a guild -- but when NOT in
        # a guild, it silently fell through to "PASSED VERIFICATION"
        # below with NO verification at all, awarding points for zero
        # proof of work. Confirmed live during Hisn H6 investigation
        # (traced while checking whether D025's DM-crash bug also
        # affected accent/shadow/speaking/writing/community -- it
        # doesn't crash, but this silent bypass is arguably worse).
        # Explicitly reject instead, telling the student where to go.
        if not isinstance(ctx.author, discord.Member):
            await ctx.send(
                f"❌ **مينفعش تعمل `!done {task}` من الرسائل الخاصة (DM).**\n\n"
                f"لازم تكتبها في السيرفر (أي قناة) عشان البوت يقدر يتأكد "
                f"إنك فعلاً عملت المهمة.\n\n"
                f"*You can't do `!done {task}` from a DM — type it in "
                f"the server so the bot can verify your submission.*"
            )
            return
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

    # Rawiya R2/R8: advance onboarding journey on first task completion
    # (safe no-op if student isn't in journey or already past this step)
    await nour_journey.check_advancement(str(ctx.author.id), "task_completed", bot)

    # Aql (#15) Phase A6.4: journey_coverage's independent-flags model
    # replaces the FSM above -- fires on the SAME real signal
    # (task_completed), at the SAME call site, but flips a durable fact
    # rather than advancing a state pointer. Both mechanisms coexist
    # during Aql's dormant build-out (nour_journey.py is still the only
    # thing that actually sends onboarding DMs today); this call has
    # zero user-visible effect until Phase A9's cutover starts reading
    # journey_coverage instead of student_journey.
    database.set_journey_coverage(
        str(ctx.author.id), knows_daily_tasks=True, first_task_done=True,
    )

    # Format response — Bawaba B5: language adapts to member's week
    # (arabic → bilingual_ar → bilingual). Falls back to the old
    # L0-Arabic / higher-English split when the flag is OFF.
    if database.is_feature_enabled("bawaba_gradual_english"):
        msg = features.done_response_for_member(str(ctx.author.id), task, result)
    else:
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

    # Markaz M4.3: conversion-ready alert (first 7-day streak)
    if result["streak"] >= 7 and isinstance(ctx.author, discord.Member):
        asyncio.create_task(ops_monitoring.check_conversion_ready(
            str(ctx.author.id), ctx.author.display_name, result["streak"]
        ))

    # Nabd N3: milestone celebrations (varied, personal DM + public)
    if isinstance(ctx.author, discord.Member) and result.get("milestones"):
        for milestone_type, kwargs in result["milestones"]:
            await features.send_milestone_celebration(ctx.guild, str(ctx.author.id), milestone_type, **kwargs)

    # Nabd N6: social proof (notify same-level peers who opted in)
    if result["tasks_today"] == 7 and isinstance(ctx.author, discord.Member):
        await features.send_social_proof(ctx.guild, str(ctx.author.id))

    # Dhaka' P1: pronunciation scoring (async, non-blocking)
    if task in ("accent", "shadow") and isinstance(ctx.author, discord.Member):
        if database.is_feature_enabled("tatawwur_pronunciation"):
            asyncio.create_task(_score_pronunciation(ctx, task))


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

    # Dhaka' A1.3: Show difficulty + pronunciation average
    from . import adaptive_engine
    difficulty = member.get("difficulty_level", 2)
    diff_label = adaptive_engine.get_difficulty_label(difficulty)
    diff_emoji = adaptive_engine.get_difficulty_emoji(difficulty)
    pron_avg = database.get_pronunciation_average(str(ctx.author.id))
    if pron_avg > 0:
        msg += f"\n🎯 Pronunciation: **{pron_avg:.0f}%** | Difficulty: {diff_emoji} {diff_label}"

    # Masar M1.3: Momentum Score, added alongside (not replacing) the
    # level badge line above -- fixes Hisn D012 by giving students one
    # honest, clearly-labeled recency signal, computed identically to
    # the dashboard's momentum field (same narrative_engine.momentum_score()
    # call) so the two surfaces never disagree about the same student
    # at the same moment (R2's consistency requirement).
    if database.is_feature_enabled("masar_momentum_score", str(ctx.author.id)):
        from . import narrative_engine
        momentum = narrative_engine.momentum_score(str(ctx.author.id))
        momentum_label_ar = {
            "restarting": "بداية جديدة", "building": "في البناء",
            "steady": "مستقر", "strong": "زخم قوي",
        }.get(momentum["label"], "")
        msg += (
            f"\n🧭 Momentum This Week: **{momentum['score']}** ({momentum['label'].title()})"
            f" — نشاطك الأسبوعي{f' / {momentum_label_ar}' if momentum_label_ar else ''}"
        )

    await ctx.send(msg)


@bot.command(name="streak")
async def cmd_streak(ctx):
    """View your streak details."""
    # Aql (#15) Phase A6.4: actually viewing !streak is the real
    # signal that this student now knows the streak system exists --
    # a genuinely observed behavior, not a scripted checkpoint. See
    # cmd_done's comment above for why this coexists with the
    # unrelated nour_journey.py FSM with zero user-visible effect today.
    database.set_journey_coverage(str(ctx.author.id), knows_streaks=True)

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
        # Tatawwur T0: handle Day 1 benchmark recording submission
        if message.attachments:
            handled = await features.handle_benchmark_recording(message)
            if handled:
                return
        # Nour N0: handle non-command DMs as concierge conversation
        if not message.content.startswith(config.BOT_PREFIX):
            from . import nour_concierge
            try:
                await nour_concierge.handle_with_human_touch(message)
            except Exception as e:
                logger.error(f"Nour DM handler error: {e}")
            return

    # Nour N0: handle messages in #ask-nour channel
    if hasattr(message.channel, 'name') and message.channel.name == "ask-nour":
        if not message.content.startswith(config.BOT_PREFIX):
            from . import nour_concierge
            try:
                await nour_concierge.handle_with_human_touch(message)
            except Exception as e:
                logger.error(f"Nour #ask-nour handler error: {e}")
            return

    # Aql (#15) Phase A6.4: posting in one of the "tour" channels
    # nour_journey.py's own channels_tour step introduces (daily-word,
    # cheat-sheets, general-chat, ask-nour) is a real observed signal
    # that this student has found and used channels beyond the
    # default daily-tasks/bot-commands pair -- a genuine behavior, not
    # a scripted checkpoint. Cheap membership check, no extra query
    # unless the channel actually matches.
    if hasattr(message.channel, "name") and message.channel.name in (
        "daily-word", "cheat-sheets", "general-chat", "ask-nour",
    ):
        database.set_journey_coverage(str(message.author.id), knows_channels=True)

    # English-only detection (before processing commands)
    await features.check_english_only(message)

    # Nour N4: Onboarding intelligence — catch confused new students
    from . import nour_onboarding
    try:
        await nour_onboarding.check_wrong_channel(message)
        await nour_onboarding.check_command_typo(message)
    except Exception as e:
        logger.error(f"Nour onboarding check error: {e}")

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
    #
    # Hisn D025: message.channel.name doesn't exist on DMChannel at all --
    # this crashed with an AttributeError for EVERY DM message the bot
    # received (this line runs unconditionally, before checking whether
    # a quiz is even pending), which silently discarded quiz answers sent
    # via DM with no visible error to the student. Confirmed live during
    # Hisn H6: the vocab quiz question itself is sent correctly (that's a
    # !done command, handled by cmd_done regardless of channel type), but
    # since the tutorial and most onboarding happens via DM, answering in
    # the same DM conversation is the natural thing a student would do --
    # and that's exactly the path that crashed. Use getattr() with a
    # default so DMs are simply treated as "not bot-commands" (correctly
    # -- a DM channel was never going to equal that string anyway) instead
    # of crashing before the pending-quiz logic below ever runs.
    if verification.has_pending_quiz(str(message.author.id)):
        if getattr(message.channel, "name", None) == "bot-commands" and not message.content.startswith("!"):
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
    # Hisn D025: same DMChannel.name crash as the vocab handler above.
    if verification.has_pending_listening(str(message.author.id)):
        if getattr(message.channel, "name", None) == "bot-commands" and not message.content.startswith("!"):
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
    # Hisn D025: same DMChannel.name crash as the vocab/listening handlers
    # above -- this ran unconditionally for every message including DMs.
    if getattr(message.channel, "name", None) == "writing-feedback" and len(message.content) > 30:
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


@bot.command(name="testwelcome")
@commands.has_permissions(manage_guild=True)
async def cmd_testwelcome(ctx):
    """(Admin) Simulate the full new-member welcome flow on yourself.

    Sends the same DM sequence a brand-new member would get: greeting,
    multimedia assets (journey map + audio clips + video link), and the
    tutorial quest. Useful for testing B3 without needing to rejoin.
    """
    try:
        start_here_note = ""
        if database.is_feature_enabled("bawaba_start_channel"):
            start_here_note = "\n📌 **روح `#start-here` أول حاجة** — هتلاقي كل اللي محتاجه هناك.\n"

        await ctx.author.send(
            f"🏛️ **أهلًا بيك في Empire English, {ctx.author.display_name}!**\n\n"
            f"ده نظام تعلّم يومي هيخليك تتكلم إنجليزي.\n"
            f"{start_here_note}"
            f"خلينا نبدأ بـ 5 خطوات سريعة (دقيقتين بس) 👇"
        )

        # Send multimedia assets
        if database.is_feature_enabled("bawaba_multimedia"):
            await _send_onboarding_media(ctx.author)

        await asyncio.sleep(1)

        # Start tutorial
        if database.is_feature_enabled("bawaba_tutorial"):
            await features.start_tutorial(ctx.author)

        await ctx.send("📩 Welcome flow sent to your DMs!", delete_after=10)
    except discord.Forbidden:
        await ctx.send("❌ Can't DM you. Enable DMs from server members.")


@bot.command(name="notifications")
async def cmd_notifications(ctx, setting: str = None, value: str = None):
    """View or change your notification preferences.

    Nabd Phase N0: students control their notification experience.
    Usage:
      !notifications          — show current settings
      !notifications morning off  — disable morning DM
      !notifications streak on    — enable streak alerts
      !إشعارات               — same (Arabic alias)

    Valid settings: morning, evening, streak, celebrations, social, weekly
    """
    if not database.is_feature_enabled("nabd_preferences"):
        return

    discord_id = str(ctx.author.id)
    prefs = database.get_notification_prefs(discord_id)

    if setting is None:
        # Show current preferences
        def on_off(v):
            return "✅ مفعّل" if v else "❌ متوقف"

        await ctx.send(
            "🔔 **إعدادات الإشعارات:**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🌅 رسالة الصباح (morning): {on_off(prefs['morning_dm'])}\n"
            f"⏰ تذكير المساء (evening): {on_off(prefs['evening_dm'])}\n"
            f"🔥 تنبيه الـ streak (streak): {on_off(prefs['streak_alert'])}\n"
            f"🏆 احتفالات (celebrations): {on_off(prefs['celebrations'])}\n"
            f"👥 نشاط الزملاء (social): {on_off(prefs['social_proof'])}\n"
            f"📊 ملخص أسبوعي (weekly): {on_off(prefs['weekly_summary'])}\n"
            f"🌙 ساعات الهدوء: {prefs['quiet_start']} - {prefs['quiet_end']}\n\n"
            "**لتغيير إعداد:**\n"
            "`!notifications morning off` — أوقف رسالة الصباح\n"
            "`!notifications social on` — فعّل نشاط الزملاء"
        )
        return

    # Map short names to DB column names
    key_map = {
        "morning": "morning_dm",
        "evening": "evening_dm",
        "streak": "streak_alert",
        "celebrations": "celebrations",
        "social": "social_proof",
        "weekly": "weekly_summary",
    }

    if setting not in key_map:
        await ctx.send(
            f"❌ إعداد مش موجود: `{setting}`\n"
            f"الإعدادات المتاحة: morning, evening, streak, celebrations, social, weekly"
        )
        return

    if value not in ("on", "off"):
        await ctx.send("Usage: `!notifications <setting> on/off`")
        return

    db_key = key_map[setting]
    db_value = 1 if value == "on" else 0
    database.set_notification_pref(discord_id, db_key, db_value)

    status = "✅ مفعّل" if db_value else "❌ متوقف"
    await ctx.send(f"🔔 {setting}: {status}")


@bot.command(name="portfolio")
async def cmd_portfolio(ctx):
    """View your voice progress portfolio — hear your growth over time.

    Tatawwur T0: shows all benchmark recordings chronologically with
    dates, scores, and links. The "before and after" that proves the
    system works.
    """
    if not database.is_feature_enabled("tatawwur_portfolio"):
        return

    discord_id = str(ctx.author.id)
    recordings = database.get_voice_portfolio(discord_id)

    if not recordings:
        phase = features.response_language(discord_id)
        if phase == "arabic":
            await ctx.send(
                "🎙️ **محفظة صوتك فاضية لسه.**\n\n"
                "لما تبدأ تسجل صوتك في المهام اليومية، هتلاقي تسجيلاتك هنا.\n"
                "هتقدر تسمع نفسك وانت بتتحسن مع الوقت! 📈"
            )
        else:
            await ctx.send(
                "🎙️ **Your voice portfolio is empty.**\n\n"
                "As you complete speaking tasks, your recordings will appear here.\n"
                "You'll be able to hear yourself improving over time! 📈"
            )
        return

    member = database.get_member(discord_id)
    name = member["discord_name"] if member else ctx.author.display_name

    lines = [
        f"🎙️ **{name}'s Voice Portfolio**",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📊 Total recordings: **{len(recordings)}**",
        "",
    ]

    # Show benchmarks first (the key "before/after" evidence)
    benchmarks = [r for r in recordings if "benchmark" in r["recording_type"]]
    if benchmarks:
        lines.append("📍 **Benchmarks (hear your progress):**")
        for r in benchmarks:
            date = r["recorded_at"][:10]
            score_text = f" — Score: {r['ai_score']:.0f}%" if r["ai_score"] else ""
            type_label = "Day 1" if r["recording_type"] == "benchmark_day1" else f"Week {r['week'] or '?'}"
            lines.append(f"  🎤 {type_label} ({date}){score_text}")
            if r["recording_url"]:
                lines.append(f"     🔗 {r['recording_url']}")
        lines.append("")

    # Recent daily recordings (last 5)
    daily = [r for r in recordings if r["recording_type"] == "daily"]
    if daily:
        lines.append(f"🎯 **Recent recordings:** ({len(daily)} total)")
        for r in daily[-5:]:
            date = r["recorded_at"][:10]
            score_text = f" — {r['ai_score']:.0f}%" if r["ai_score"] else ""
            lines.append(f"  • {date} ({r['level']}){score_text}")

    # Dhaka' P2: Pronunciation scores from AI scoring (last 7 days)
    pronunciation_scores = database.get_recent_scores(discord_id, days=7)
    if pronunciation_scores:
        lines.append("")
        lines.append(f"🎯 **AI Pronunciation Scores (last 7 days):**")
        for ps in pronunciation_scores[:7]:
            date = ps["date"]
            task_label = "🎯 Accent" if ps["task_id"] == "accent" else "🎧 Shadow"
            stars = "⭐" * int(ps["score"] / 20)
            lines.append(f"  {task_label} {date} — {ps['score']:.0f}% {stars}")

        # Trend calculation
        if len(pronunciation_scores) >= 3:
            recent_3 = [s["score"] for s in pronunciation_scores[:3]]
            older_3 = [s["score"] for s in pronunciation_scores[-3:]]
            recent_avg = sum(recent_3) / len(recent_3)
            older_avg = sum(older_3) / len(older_3)
            diff = recent_avg - older_avg
            if diff > 5:
                trend_arrow = "↑ improving"
            elif diff < -5:
                trend_arrow = "↓ needs attention"
            else:
                trend_arrow = "→ stable"
            avg = sum(s["score"] for s in pronunciation_scores) / len(pronunciation_scores)
            lines.append(f"  📊 Average: **{avg:.0f}%** | Trend: **{trend_arrow}**")
        lines.append("")

    # Pronunciation trend (if enough data)
    scored = [r for r in recordings if r["ai_score"] is not None]
    if len(scored) >= 3:
        first_score = scored[0]["ai_score"]
        last_score = scored[-1]["ai_score"]
        change = last_score - first_score
        trend = "📈" if change > 0 else "📉" if change < 0 else "➡️"
        lines.append(f"\n{trend} **Pronunciation trend:** {first_score:.0f}% → {last_score:.0f}% ({'+' if change > 0 else ''}{change:.0f}%)")

    msg = "\n".join(lines)
    if len(msg) > 1900:
        try:
            await ctx.author.send(msg)
            await ctx.send("📩 Portfolio sent to your DMs!", delete_after=10)
        except discord.Forbidden:
            await ctx.send(msg[:1900] + "\n...")
    else:
        await ctx.send(msg)


@bot.command(name="words")
async def cmd_words(ctx):
    """View your vocabulary strength — spaced repetition stats.

    Tatawwur T2: shows how many words you know, how many are due for
    review, and your overall vocabulary strength.
    """
    if not database.is_feature_enabled("tatawwur_srs"):
        return

    discord_id = str(ctx.author.id)
    stats = database.get_srs_stats(discord_id)

    if stats["total"] == 0:
        await ctx.send(
            "📖 **لسه مفيش كلمات في نظام التكرار.**\n\n"
            "لما تخلص مهام المفردات (`!2` أو `!done vocab`)، الكلمات هتتضاف أوتوماتيك.\n"
            "النظام هيراجعلك الكلمات القديمة عشان متنساهاش! 🧠"
        )
        return

    mastered_bar = "█" * min(10, stats["mastered"] * 10 // max(stats["total"], 1)) + "░" * (10 - min(10, stats["mastered"] * 10 // max(stats["total"], 1)))

    await ctx.send(
        f"📖 **كلماتك — Vocabulary Strength**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Total words: **{stats['total']}**\n"
        f"✅ Mastered (30+ days): **{stats['mastered']}**\n"
        f"📝 Learning: **{stats['learning']}**\n"
        f"🔄 Due for review today: **{stats['due_today']}**\n\n"
        f"Strength: [{mastered_bar}] {stats['mastered']}/{stats['total']}"
    )


@bot.command(name="abilities")
async def cmd_abilities(ctx):
    """View your ability milestones — what you CAN DO now.

    Tatawwur T3: shows completed vs. pending milestones for your level.
    These are concrete, testable challenges — not just points.
    """
    if not database.is_feature_enabled("tatawwur_milestones"):
        return

    import json
    from pathlib import Path

    discord_id = str(ctx.author.id)
    member = database.get_member(discord_id)
    if not member:
        await ctx.send("مش مسجل. اكتب `!join` الأول.")
        return

    level = member["level"]
    milestones_file = Path(__file__).resolve().parent.parent / "content" / "milestones" / "milestones.json"
    if not milestones_file.exists():
        await ctx.send("⚠️ Milestones data not found.")
        return

    with open(milestones_file, encoding="utf-8") as f:
        all_milestones = json.load(f)

    level_milestones = all_milestones.get(level, [])
    if not level_milestones:
        await ctx.send(f"⚠️ No milestones defined for {level} yet.")
        return

    completed_ids = database.get_completed_milestones(discord_id)

    lines = [
        f"🎯 **قدراتك — {level} Ability Milestones**",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    done_count = 0
    for m in level_milestones:
        if m["id"] in completed_ids:
            lines.append(f"  ✅ ~~{m['name_ar']}~~ ({m['name']})")
            done_count += 1
        else:
            lines.append(f"  ⬜ **{m['name_ar']}** ({m['name']})")
            lines.append(f"     {m['description_ar']}")

    lines.append(f"\n📊 {done_count}/{len(level_milestones)} completed")

    if done_count == len(level_milestones):
        lines.append("\n🏆 **خلصت كل milestones المستوى ده! جاهز للترقية!**")

    await ctx.send("\n".join(lines))


@bot.command(name="conversation")
async def cmd_conversation(ctx):
    """Sign up for a structured conversation session.

    Tatawwur T5: weekly paired speaking practice with a same-level
    partner. The bot matches you and provides conversation prompts.
    """
    if not database.is_feature_enabled("tatawwur_conversations"):
        return

    discord_id = str(ctx.author.id)
    member = database.get_member(discord_id)
    if not member:
        await ctx.send("مش مسجل. اكتب `!join` الأول.")
        return

    level = member["level"]
    sessions = database.get_upcoming_sessions(level)

    if sessions:
        s = sessions[0]
        await ctx.send(
            f"🗣️ **الجلسة الجاية:**\n"
            f"📅 {s['scheduled_at']}\n"
            f"📊 Level: {s['level']}\n"
            f"👥 Participants: {len(s['participant_ids'].split(',')) if s['participant_ids'] else 0}\n\n"
            f"انت مسجل بالفعل! هتوصلك رسالة قبل الجلسة بنص ساعة."
        )
    else:
        await ctx.send(
            "🗣️ **جلسات المحادثة**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "مفيش جلسات مجدولة حالياً.\n"
            "الجلسات بتكون أسبوعية — هيتم الإعلان عنها في #announcements.\n\n"
            "💡 لحد ما تبدأ الجلسات، اتمرن مع الـ buddy بتاعك!"
        )


@bot.command(name="pulse")
@commands.has_permissions(manage_guild=True)
async def cmd_pulse(ctx):
    """(Admin) Nabd N7: notification system stats.

    Shows how many notifications were sent today, this week, and
    which types are most active. Quick health check for the system.
    """
    from src.database import _connect
    today = task_engine.today_str()

    conn = _connect()
    # Today's counts by type
    today_stats = conn.execute(
        "SELECT notification_type, COUNT(*) as cnt FROM notification_log WHERE date=? GROUP BY notification_type",
        (today,),
    ).fetchall()
    # This week's total
    week_start = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    week_total = conn.execute(
        "SELECT COUNT(*) as cnt FROM notification_log WHERE date >= ?",
        (week_start,),
    ).fetchone()["cnt"]
    # Total opted-out students (any preference set to 0)
    opted_out = conn.execute(
        "SELECT COUNT(DISTINCT discord_id) as cnt FROM notification_preferences WHERE morning_dm=0 OR evening_dm=0 OR streak_alert=0",
    ).fetchone()["cnt"]
    conn.close()

    lines = [
        "🔔 **Nabd — Notification Pulse**",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"**Today ({today}):**",
    ]
    if today_stats:
        for row in today_stats:
            lines.append(f"  • {row['notification_type']}: {row['cnt']} sent")
    else:
        lines.append("  (no notifications sent today)")

    lines.append(f"\n**This week:** {week_total} total notifications")
    lines.append(f"**Opted out (any type):** {opted_out} student(s)")

    await ctx.send("\n".join(lines))


@bot.command(name="poststart")
@commands.has_permissions(manage_guild=True)
async def cmd_poststart(ctx):
    """(Admin) Post the #start-here pinned message.

    Bawaba B6: posts the START_HERE_MESSAGE content to #start-here and
    pins it. Run this once after creating the channel. Idempotent — if
    the message already exists (pinned), it won't post a duplicate.
    """
    channel = _find_channel(ctx.guild, "start-here")
    if not channel:
        await ctx.send("❌ `#start-here` channel not found. Create it first.")
        return

    # Check if already pinned (avoid duplicates)
    pins = await channel.pins()
    for pin in pins:
        if pin.author == bot.user and "ابدأ من هنا" in pin.content:
            await ctx.send("✅ `#start-here` already has the pinned message.")
            return

    msg = await channel.send(features.START_HERE_MESSAGE)
    await msg.pin()
    await ctx.send("✅ Posted and pinned in `#start-here`!", delete_after=10)


@bot.command(name="confirm-delete")
async def cmd_confirm_delete(ctx):
    """Confirm data deletion."""
    await features.handle_confirm_delete(ctx, bot)


# ============================================================
#  ADMIN COMMANDS
# ============================================================

@bot.command(name="postgate")
@commands.has_permissions(administrator=True)
async def cmd_postgate(ctx):
    """Post the role-gate agreement message in #rules (Hissar P1.2)."""
    await role_gate.cmd_postgate(ctx)


@bot.command(name="setupgate")
@commands.has_permissions(administrator=True)
async def cmd_setupgate(ctx):
    """Auto-configure channel permissions for role-gate (Hissar P1.2). Run ONCE."""
    await role_gate.cmd_setupgate(ctx)


@bot.command(name="revoke")
@commands.has_permissions(administrator=True)
async def cmd_revoke(ctx, member: discord.Member = None):
    """Hissar P5: Revoke a student's practice platform token (forces re-link).

    Usage: !revoke @student
    The student will need to run !link again to get a new token.
    """
    if not member:
        await ctx.send("Usage: `!revoke @student` — invalidates their practice platform token.")
        return

    discord_id = str(member.id)
    token = database.get_token_for_member(discord_id)
    if not token:
        await ctx.send(f"⚠️ {member.display_name} has no active token.")
        return

    # Show IP info before revoking
    ip_count = database.get_token_ip_count(token)
    ips = database.get_token_ips(token)

    revoked = database.revoke_member_token(discord_id)
    if revoked:
        ip_info = f" (was used from {ip_count} unique IP{'s' if ip_count != 1 else ''})" if ip_count else ""
        await ctx.send(
            f"🔒 **Token revoked** for {member.mention}{ip_info}.\n"
            f"They must run `!link` again to get a new token.\n"
            f"Practice pages will show 'locked' until they re-link."
        )
        # DM the student
        try:
            await member.send(
                "⚠️ **تم إلغاء رابط الممارسة الخاص بك.**\n"
                "اكتب `!link` في `#bot-commands` للحصول على رابط جديد.\n\n"
                "⚠️ **Your practice link has been revoked.**\n"
                "Type `!link` in `#bot-commands` to get a new one."
            )
        except (discord.Forbidden, discord.HTTPException):
            pass
    else:
        await ctx.send(f"❌ Failed to revoke token for {member.display_name}.")


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


@bot.command(name="markmilestone")
@commands.has_permissions(manage_guild=True)
async def cmd_markmilestone(ctx, member: discord.Member = None, milestone_id: str = None):
    """Admin command: mark an ability milestone as completed for a
    student, after manually reviewing their submitted evidence
    (recording/writing/conversation per milestones.json's `type`
    field). Usage: !markmilestone @user l0_introduce

    Masar M3.2: this is `database.complete_milestone()`'s FIRST real
    call site anywhere in this codebase. Investigating M3's scope
    found that although milestones are fully designed (15 of them,
    `content/milestones/milestones.json`) and students can view their
    progress via `!abilities`, nothing anywhere ever actually called
    `complete_milestone()` — meaning no real student has EVER had a
    milestone marked complete, at all, since the feature was built.
    This is the exact D020/D012 pattern (a feature designed, but the
    piece that actually triggers it missing) applied to milestones —
    these specific milestones need a human (or future AI) to actually
    listen to a recording or read an essay and judge it, which is why
    an admin command, not an automatic detector, is the right fix here
    (out of scope: changing what the milestones themselves are, or
    how they're judged — this only gives the existing, unchanged
    system its first working way to actually award one).
    """
    if not member or not milestone_id:
        await ctx.send("Usage: `!markmilestone @user <milestone_id>` (see `!abilities` for valid IDs)")
        return

    discord_id = str(member.id)
    target = database.get_member(discord_id)
    if not target:
        await ctx.send(f"❌ {member.display_name} isn't registered.")
        return

    import json
    from pathlib import Path
    milestones_file = Path(__file__).resolve().parent.parent / "content" / "milestones" / "milestones.json"
    all_milestones = json.loads(milestones_file.read_text(encoding="utf-8"))
    level = target.get("level", "L0")
    level_milestones = {m["id"]: m for m in all_milestones.get(level, [])}
    milestone = level_milestones.get(milestone_id)
    if not milestone:
        valid_ids = ", ".join(level_milestones.keys()) or "(none defined for this level)"
        await ctx.send(f"❌ Unknown milestone_id `{milestone_id}` for {level}. Valid IDs: {valid_ids}")
        return

    newly_completed = database.complete_milestone(discord_id, milestone_id, level=level)
    if not newly_completed:
        await ctx.send(f"ℹ️ {member.display_name} already completed **{milestone['name']}** — no change.")
        return

    await ctx.send(f"✅ Marked **{milestone['name']}** ({milestone['name_ar']}) complete for {member.display_name}.")

    # Masar M3: fire the personalized unlock moment, same gating
    # discipline (celebrations preference + quiet hours) as every
    # other celebratory notification in this codebase.
    if database.is_feature_enabled("masar_milestone_moments", discord_id):
        prefs = database.get_notification_prefs(discord_id)
        if prefs.get("celebrations", 1) and not database.is_quiet_hours(discord_id):
            try:
                from . import narrative_engine
                signals = narrative_engine.gather_signals(discord_id)
                message, _source = await narrative_engine.build_milestone_moment(
                    discord_id, milestone_id, signals,
                )
                await member.send(message)
            except (discord.Forbidden, discord.HTTPException):
                pass
            except Exception as e:
                logger.error(f"Masar milestone moment error for {discord_id}: {e}")


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
        from .flag_registry import get_flags_by_initiative, INITIATIVES
        groups = get_flags_by_initiative()

        lines = ["🚩 **Feature Flags — Empire English**", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━", ""]

        for initiative_key in INITIATIVES.keys():
            if initiative_key not in groups:
                continue
            emoji, name_upper, subtitle = INITIATIVES[initiative_key]
            lines.append(f"{emoji} **{name_upper}** ({subtitle}):")
            for flag_name, description, _ in groups[initiative_key]:
                # Check actual DB state
                enabled = database.is_feature_enabled(flag_name)
                state = "🟢" if enabled else "🔴"
                lines.append(f"  {state} `{flag_name}` — {description}")
            lines.append("")

        # Show any DB flags NOT in the registry (manually created)
        db_flags = database.list_feature_flags()
        registered_names = {f[0] for group in groups.values() for f in group}
        unregistered = [f for f in db_flags if f["name"] not in registered_names]
        if unregistered:
            lines.append("❓ **Unregistered (created manually):**")
            for f in unregistered[:10]:
                state = "🟢" if f["enabled"] else "🔴"
                lines.append(f"  {state} `{f['name']}`")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("Toggle: `!flag enable/disable <name>`")

        # Smart chunking: split into Discord-safe messages (max 1900 chars each).
        # Sends multiple messages to the SAME channel. Works for any number of flags.
        chunks = []
        current_chunk = ""
        for line in lines:
            if len(current_chunk) + len(line) + 1 > 1900:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += ("\n" + line) if current_chunk else line
        if current_chunk:
            chunks.append(current_chunk)

        for chunk in chunks:
            await ctx.send(chunk)
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
#  DHAKA' A2: !difficulty COMMAND
# ============================================================

@bot.command(name="difficulty")
async def cmd_difficulty(ctx):
    """View or reset your adaptive difficulty level."""
    from . import adaptive_engine

    discord_id = str(ctx.author.id)
    member = database.get_member(discord_id)
    if not member:
        await ctx.send("You're not registered yet. Use `!join` to start.")
        return

    difficulty = member.get("difficulty_level", 2)
    label = adaptive_engine.get_difficulty_label(difficulty)
    emoji = adaptive_engine.get_difficulty_emoji(difficulty)
    pron_avg = database.get_pronunciation_average(discord_id)

    msg = (
        f"🎯 **Difficulty Level / مستوى الصعوبة**\n\n"
        f"{emoji} Current: **{label}**\n"
    )
    if pron_avg > 0:
        msg += f"📊 Pronunciation average (7d): **{pron_avg:.0f}%**\n"
    msg += (
        f"\n📋 **How it works:**\n"
        f"• Score 85%+ for 3 days → difficulty goes UP\n"
        f"• Score 50% or below for 3 days → difficulty goes DOWN\n"
        f"• Otherwise stays the same\n\n"
        f"💡 To reset to Normal: `!difficulty reset`"
    )
    await ctx.send(msg)


@bot.command(name="difficulty_reset")
async def cmd_difficulty_reset(ctx):
    """Reset difficulty to Normal."""
    discord_id = str(ctx.author.id)
    member = database.get_member(discord_id)
    if not member:
        return
    database.update_member(discord_id, difficulty_level=2)
    await ctx.send("✅ Difficulty reset to **Normal / عادي**.")


# ============================================================
#  SAHEL S6: !link COMMAND (practice platform connection)
# ============================================================

@bot.command(name="link")
async def cmd_link(ctx):
    """Generate a personal URL token and DM it to the user.
    This token connects their practice platform to their Discord progress."""
    discord_id = str(ctx.author.id)

    # Must be registered
    member = database.get_member(discord_id)
    if not member:
        await ctx.send("❌ You need to register first. Type `!join` or react ✅ to any message.")
        return

    # Generate or retrieve existing token
    token = database.create_link_token(discord_id)
    platform_url = config.PRACTICE_PLATFORM_URL

    # DM the token to the user (never in public channels)
    try:
        await ctx.author.send(
            f"🔗 **ربط حسابك بمنصة التمرين**\n\n"
            f"الرابط الشخصي بتاعك:\n"
            f"```\n{platform_url}?token={token}\n```\n\n"
            f"**أو** افتح المنصة واضغط \"Connect to Discord\" والصق:\n"
            f"```\n{token}\n```\n\n"
            f"⚠️ **ماتشاركش الرابط ده مع حد — ده خاص بيك.**\n"
            f"لو محتاج رابط جديد، اكتب `!link` تاني."
        )
        await ctx.send("✅ Check your DMs! / شوف الرسائل الخاصة 📩")
        # Rawiya R2/R8: advance onboarding journey when student links the platform
        await nour_journey.check_advancement(discord_id, "link_used", bot)
        # Aql (#15) Phase A6.4: same real signal, feeds the
        # journey_coverage independent-flags model too -- see
        # cmd_done's identical comment above for why both mechanisms
        # coexist right now with zero user-visible effect.
        database.set_journey_coverage(discord_id, knows_platform_link=True)
    except discord.Forbidden:
        await ctx.send("❌ I can't DM you. Enable DMs from server members and try again.")


# Add Arabic aliases
ARABIC_COMMAND_ALIASES["ربط"] = "link"
ARABIC_COMMAND_ALIASES["صعوبة"] = "difficulty"


# ============================================================
#  RUN
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
