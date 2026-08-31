"""Empire English Community Bot — Main Discord Bot.

The operational heart of the Learning Operating System. Handles:
  - Scheduled daily task delivery (6 AM) to level-specific channels
  - Scheduled weekly recap (Sunday 10 AM)
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
from discord import app_commands
from discord.ext import commands, tasks

from . import config, database, curriculum, tasks as task_engine, ai_engine, verification, features, ops_hub, ops_poller, ops_monitoring, role_gate, nour_journey, maintenance as maintenance_mod, changelog as changelog_mod, community, bot_integrity, sijil, ijtihad_boards, ijtihad_growth, suspension, assessment_watchdog

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


# One-shot guard so admin slash commands are synced to the guild only once
# (on_ready can fire again on reconnects).
_slash_synced = False


class AdminChannelOnly(commands.CheckFailure):
    """Raised when an admin runs an admin command outside #admin-commands."""


def _is_admin_command(command) -> bool:
    """True if a prefix command is permission-gated (manage_guild/administrator)
    — detected generically so we don't have to hand-maintain a name list."""
    for chk in getattr(command, "checks", []):
        if "has_permissions" in getattr(chk, "__qualname__", ""):
            return True
    return False


def _author_is_admin(ctx_or_author, guild=None) -> bool:
    """True if the user has manage_guild — works in-guild and in DMs (by
    looking the member up in the configured guild)."""
    author = getattr(ctx_or_author, "author", ctx_or_author)
    perms = getattr(author, "guild_permissions", None)
    if perms is not None and perms.manage_guild:
        return True
    g = guild or bot.get_guild(config.GUILD_ID)
    if g is not None:
        m = g.get_member(getattr(author, "id", 0))
        if m is not None and m.guild_permissions.manage_guild:
            return True
    return False


@bot.check
async def _admin_commands_channel_gate(ctx):
    """Keep admin commands consolidated in #admin-commands.

    - Student/public commands: allowed anywhere (unchanged).
    - Admin commands in DMs or in #admin-commands: allowed.
    - Admin commands run by an ACTUAL admin in any other channel: blocked with
      a self-deleting nudge (so a stray admin command can't be seen by
      students in a public channel).
    - Admin commands attempted by a NON-admin: fall through here and get
      silently rejected by the command's own permission check (see
      on_command_error) — so we never reveal the command exists.
    """
    cmd = ctx.command
    if cmd is None or not _is_admin_command(cmd):
        return True
    if ctx.guild is None:
        return True  # DMs are fine
    if not config.ADMIN_COMMANDS_CHANNEL_ID:
        return True  # gate disabled / unconfigured -> fail open
    if ctx.channel.id == config.ADMIN_COMMANDS_CHANNEL_ID:
        return True
    # Only enforce (and nudge) for real admins; non-admins fall through to the
    # silent permission rejection so command existence isn't leaked.
    if _author_is_admin(ctx):
        raise AdminChannelOnly()
    return True

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

# Empire Reset (session-33): the 5 core exercises (accent, vocab, shadowing,
# listening, speaking) are logged AUTOMATICALLY when a student finishes them
# on the practice page (via /api/practice-complete + /api/submit-recording).
# So in Discord we only log the two Discord-side tasks — writing (!6) and
# community (!7). Any attempt to log one of the 5 core tasks in Discord (via
# !done, !1-!5, or a 1️⃣-5️⃣ reaction) shows this gentle bilingual signpost
# instead of a dead "unknown command".
_TASK_REDIRECT_MSG = (
    "✅ التمارين الخمسة الأساسية (النطق، المفردات، المحاكاة، الاستماع، الكلام) "
    "بتتسجّل **تلقائيًا** أول ما تخلّصها على منصة التمرين — افتحها بأمر `!link`.\n"
    "هنا في Discord بتسجّل بس: ✍️ الكتابة `!6` و 💬 المجتمع `!7`.\n\n"
    "✅ The 5 core exercises log **automatically** when you finish them on the "
    "practice page — open it with `!link`. In Discord you only log "
    "✍️ writing (`!6`) and 💬 community (`!7`)."
)

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
    "ترتيب": "top",
    "سلسلات": "streaks",
    "صيانة": "maintenance",
    "اليوم": "today",
    "تعليم": "tutorial",
    "إشعارات": "notifications",
    "نبض": "pulse",
    "كلماتي": "words",
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
    """Get the Discord role name for a level — CEFR-driven single source of
    truth (config.level_role_name), so it stays in lockstep with the roles
    setup_server.py creates. Accepts CEFR (A1–C2) or legacy (L0–L3) keys."""
    return config.level_role_name(level)


async def _get_or_create_role(guild: discord.Guild, role_name: str) -> discord.Role:
    """Get a role by name or create it if missing."""
    role = discord.utils.get(guild.roles, name=role_name)
    if not role:
        role = await guild.create_role(name=role_name)
    return role


async def _assign_level_role(member: discord.Member, new_level: str):
    """Remove any stale level role (CEFR or legacy) and assign the CEFR role
    for new_level. Strips every managed level role except the target, so a
    student never carries two level roles (and a leftover legacy L0–L3 role is
    cleaned up on their first CEFR (re)assignment)."""
    guild = member.guild
    new_name = config.level_role_name(new_level)
    for role_name in config.all_managed_level_role_names():
        if role_name == new_name:
            continue  # don't strip the role we're about to add
        role = discord.utils.get(guild.roles, name=role_name)
        if role and role in member.roles:
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                pass
    # Add new level role
    new_role = await _get_or_create_role(guild, new_name)
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
            "    └ التمارين الأساسية على منصة التمرين (`!link`) بتتسجّل لوحدها\n"
            "    └ الكتابة اكتب `!6` والمجتمع اكتب `!7`\n\n"
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
    # Phase 8: activate the CEFR exit exam once, automatically, on deploy
    # (owner decision — make it live). Idempotent; won't undo a later manual off.
    if database.enable_exit_exam_once():
        logger.info("CEFR exit exam auto-enabled (assessment_advancement_exam = ON)")
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

    # Register admin slash commands to THIS guild (instant, guild-scoped) so
    # /reset-student etc. get a native full-guild user picker and are auto-
    # hidden from non-admins. Guarded so it runs once, not on every reconnect.
    global _slash_synced
    if not _slash_synced and config.GUILD_ID:
        try:
            guild_obj = discord.Object(id=config.GUILD_ID)
            bot.tree.copy_global_to(guild=guild_obj)
            synced = await bot.tree.sync(guild=guild_obj)
            _slash_synced = True
            logger.info(f"Slash commands synced to guild {config.GUILD_ID}: "
                        f"{[c.name for c in synced]}")
        except Exception as e:
            logger.warning(f"Slash command sync failed (will retry next on_ready): {e}")

    if not daily_task_post.is_running():
        daily_task_post.start()
    if not weekly_recap.is_running():
        weekly_recap.start()
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
    if not retention_cycle.is_running():
        retention_cycle.start()
    if not assessment_watchdog_loop.is_running():
        assessment_watchdog_loop.start()
    if not midnight_voice_reset.is_running():
        midnight_voice_reset.start()
    if not beacon_cleanup_loop.is_running():
        beacon_cleanup_loop.start()
    if not community_hour_loop.is_running():
        community_hour_loop.start()
    if not bot_integrity_monitor.is_running():
        bot_integrity_monitor.start()

    # Majlis Phase 3: set anchor capacity + ensure hub channel on startup.
    # Best-effort, flag-gated internally.
    if database.is_feature_enabled("community_dynamic_rooms"):
        try:
            _guild = bot.get_guild(config.GUILD_ID)
            if _guild:
                await community.ensure_anchor_capacity(_guild)
                await community.ensure_hub_channel(_guild)
        except Exception as e:
            logger.warning(f"community: Phase 3 startup setup failed: {e}")
    # Nour retired (owner decision 2026-07-28): all Nour scheduled jobs are
    # disabled so no Nour-voiced DMs/reports go out. Task defs are kept for
    # history but are never started.
    # if not nour_journey_daily_check.is_running():
    #     nour_journey_daily_check.start()
    if not onboarding_gate_check.is_running():
        onboarding_gate_check.start()
    if not markaz_daily_digest.is_running():
        markaz_daily_digest.start()
    if not markaz_weekly_report.is_running():
        markaz_weekly_report.start()
    if not itqan_weekly_report.is_running():
        itqan_weekly_report.start()
    if not itqan_due_nudge.is_running():
        itqan_due_nudge.start()
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
    # Nour retired (owner decision 2026-07-28): weekly self-review + weekly
    # growth letter disabled (were the source of the "رسالة نور الأسبوعية" DM).
    # if not nour_weekly_review.is_running():
    #     nour_weekly_review.start()
    # if not nour_growth_letter_task.is_running():
    #     nour_growth_letter_task.start()
    # Audit fix (E5 robustness): voice minutes are persisted on voice-LEAVE
    # (verification.on_voice_leave). If the bot restarts while a student is
    # already sitting in a voice channel, there was no join event for that
    # session, so on_voice_leave later finds no join_time and credits zero —
    # the student can genuinely spend 10+ min in voice across a restart yet
    # have the community task show 0/10. Re-seed an in-memory join_time (=now)
    # for everyone currently in voice so at least their post-restart time is
    # counted. Best-effort, guild-scoped, ignores bots.
    try:
        for _guild in bot.guilds:
            for _vc in _guild.voice_channels:
                for _mem in _vc.members:
                    if not _mem.bot:
                        verification.on_voice_join(str(_mem.id))
    except Exception as e:
        logger.warning(f"Voice-session recovery scan failed: {e}")

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
    if isinstance(error, AdminChannelOnly):
        # An admin ran an admin command outside #admin-commands. Nudge them
        # (self-deleting so it doesn't linger in a student-visible channel)
        # and try to remove their invoking message. Command did NOT run.
        chan = f"<#{config.ADMIN_COMMANDS_CHANNEL_ID}>" if config.ADMIN_COMMANDS_CHANNEL_ID else "#admin-commands"
        try:
            await ctx.send(f"🔒 Please run admin commands in {chan}.", delete_after=8)
        except Exception:
            pass
        try:
            await ctx.message.delete()
        except Exception:
            pass
        return
    if isinstance(error, commands.MissingPermissions):
        # Silent by design: replying "you don't have permission" would confirm
        # to a student that the admin command exists. Say nothing.
        return
    if isinstance(error, commands.CheckFailure):
        # Any other check failure — stay silent (no command-existence leak).
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
    # Switched channels (left one, joined another in same event)
    elif before.channel is not None and after.channel is not None and before.channel != after.channel:
        verification.on_voice_leave(str(member.id))
        verification.on_voice_join(str(member.id))

    # Majlis Phase 1: recompute together-time state after any voice change.
    # Best-effort — never crash the event handler.
    if database.is_feature_enabled("community_together_credit"):
        try:
            verification.on_together_check(member.guild)
        except Exception:
            pass

    # Majlis Phase 2: beacon lifecycle — fire on join (when in band),
    # clear on leave (when lounge empties). Best-effort, flag-gated internally.
    try:
        # Determine which Majlis lounge was affected
        joined_channel = after.channel if (before.channel is None or
            (before.channel != after.channel and after.channel is not None)) else None
        left_channel = before.channel if (after.channel is None or
            (before.channel != after.channel and before.channel is not None)) else None

        if joined_channel and community.is_majlis_channel(joined_channel):
            await community.maybe_post_beacon(member.guild, joined_channel)
        if left_channel and community.is_majlis_channel(left_channel):
            await community.maybe_clear_beacon(member.guild, left_channel)
    except Exception:
        pass

    # Majlis Phase 3: join-to-create hub — if the member joined the hub
    # channel, spawn a new room and move them. Best-effort, flag-gated.
    try:
        joined = after.channel if (before.channel is None or
            (before.channel != after.channel and after.channel is not None)) else None
        if joined and community.is_majlis_hub(joined):
            await community.handle_hub_join(member, member.guild)
    except Exception:
        pass


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
        # Session-33 hardening: when the role-gate is active, the ONLY
        # sanctioned registration path is accepting the rules in #rules
        # (handled above by role_gate.handle_reaction_gate, which grants
        # the gateway role AND starts the guided journey). This legacy
        # "✅ anywhere → auto-register" path would register a member
        # WITHOUT the gateway role and WITHOUT the journey — a silent
        # onboarding bypass. Skip it entirely while the gate is on.
        # (Reactions in #rules already returned above; this only ever
        # concerns a ✅ left on some other visible message, e.g. #welcome.)
        if database.is_feature_enabled("hissar_role_gate"):
            return
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
        # Check if already registered
        existing = database.get_member(str(payload.user_id))
        if existing:
            return  # already registered, no-op
        # Register them
        database.register_member(str(payload.user_id), member.display_name)
        # Assign the starting CEFR role (A1) — students start on A1, not legacy L0.
        await _assign_level_role(member, "A1")
        # Assign buddy
        await features.assign_buddy(member, guild)
        # Send Arabic confirmation DM
        try:
            await member.send(
                "✅ **تم تسجيلك!** أهلاً بيك في Empire English 🏛️\n\n"
                "انت دلوقتي في **A1** — مبتدئ (Breakthrough).\n"
                "كل يوم الساعة 6 الصبح هتلاقي مهام في قناة `#a1-daily-tasks`.\n\n"
                "اكتب `!مساعدة` في `#bot-commands` لو محتاج مساعدة.\n"
                "أو افتح تمارينك بأمر `!link` وابدأ. بالتوفيق! 💪"
            )
        except discord.Forbidden:
            pass
        logger.info(f"Bawaba B1: {member.display_name} registered via ✅ reaction")
        return

    # --- Flow 2: 1️⃣-7️⃣ on a daily task post → !done ---
    if emoji_str in _EMOJI_TO_TASK_INDEX and payload.message_id in _daily_task_messages:
        task_index = _EMOJI_TO_TASK_INDEX[emoji_str]
        task_id = config.DAILY_TASKS[task_index]["id"]
        # Empire Reset (session-33): only writing + community are logged in
        # Discord; the 5 core exercises auto-log on the practice page. Ignore
        # a 1️⃣-5️⃣ reaction (the daily post no longer adds those anyway).
        if task_id not in features.DISCORD_ONLY_TASK_IDS:
            return
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
            # Darb Phase 2: mastery recording for reaction-based completions.
            # CALENDAR_EXERCISES incl. speaking (E1) so a speaking completion
            # via Discord also counts toward the day's calendar green.
            if task_id in database.CALENDAR_EXERCISES:
                try:
                    from . import darb as darb_mod
                    wk_day = darb_mod.today_week_day(str(payload.user_id))
                    if wk_day:
                        member_data = database.get_member(str(payload.user_id))
                        level = (member_data.get("level", "A1") if member_data else "A1")
                        database.record_practice_mastery(
                            str(payload.user_id), level, wk_day[0], wk_day[1], task_id
                        )
                except Exception as e:
                    logger.warning(f"Reaction mastery recording failed (non-fatal): {e}")

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

    for level_key in config.CEFR_ORDER:
        members = database.members_at_level(level_key)
        if not members:
            continue

        # Determine the week: use the MINIMUM week across all members at
        # this level, so the channel broadcast matches the newest student's
        # curriculum position. Students who joined earlier get their
        # personalized (higher-week) content via the morning_kickstart DM
        # which already uses per-student member_week_number(). This ensures
        # a student joining on day 1 sees Week 1 tasks in the channel —
        # not whatever week the oldest member happens to be on.
        week = min(database.member_week_number(m["discord_id"]) for m in members)

        # Generate tasks
        task_data = await task_engine.generate_daily_tasks(level_key, week)
        # Send as multiple messages if needed — a single combined string
        # (the old format_daily_post() behavior) is frequently well over
        # Discord's 2000-char message limit (up to ~3600 chars for L3),
        # which previously made channel.send() raise discord.HTTPException
        # on most days; that exception was only logged, so daily tasks were
        # likely silently failing to post for most level/week combinations.
        message_chunks = task_engine.format_daily_post_chunks(task_data)

        # Find the channel (CEFR slug: a1-daily-tasks, …)
        channel_name = f"{config.level_slug(level_key)}-daily-tasks"
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
                    # Empire Reset (session-33): only add the 6️⃣/7️⃣ reactions
                    # (writing + community). The 5 core exercises log
                    # automatically on the practice page, so reacting 1️⃣-5️⃣
                    # here is no longer a completion path.
                    for emoji in _TASK_NUMBER_EMOJIS[5:7]:
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

        # Practice platform link — point to the personal calendar (the
        # gated hub). Darb: the old tokenized day-deep-link no longer works
        # now that the edge gate requires an empire_session cookie (it
        # ignores ?token= and would just land the student on the gate).
        # After claiming once via !link, the student's 60-day session keeps
        # them logged in and the calendar highlights today's tasks.
        practice_url_with_token = config.PRACTICE_PLATFORM_URL

        if phase == "arabic":
            streak_text = f"\U0001f525 \u0633\u0644\u0633\u0644\u062a\u0643: **{streak}** \u064a\u0648\u0645" if streak > 0 else "\U0001f331 \u0627\u0628\u062f\u0623 \u0633\u0644\u0633\u0644\u0629 \u062c\u062f\u064a\u062f\u0629 \u0627\u0644\u0646\u0647\u0627\u0631\u062f\u0629!"
            msg = (
                f"\U0001f305 \u0635\u0628\u0627\u062d \u0627\u0644\u062e\u064a\u0631 **{m['discord_name']}**!\n\n"
                f"\u0645\u0647\u0627\u0645\u0643 \u062c\u0627\u0647\u0632\u0629 \U0001f4cb\n"
                f"{streak_text}\n\n"
                f"\u0623\u0648\u0644 \u0645\u0647\u0645\u0629: **{first_task['name_ar']}** {first_task['emoji']}\n"
                f"\U0001f310 \u0627\u062a\u0645\u0631\u0646 \u0623\u0648\u0646\u0644\u0627\u064a\u0646: {practice_url_with_token}\n\n"
                f"تمارينك الأساسية بتتسجّل لوحدها على الصفحة. الكتابة `!6` والمجتمع `!7` \U0001f4aa"
            )
        elif phase == "bilingual_ar":
            streak_text = f"\U0001f525 \u0633\u0644\u0633\u0644\u0629 (Streak): **{streak}** \u064a\u0648\u0645" if streak > 0 else "\U0001f331 \u0627\u0628\u062f\u0623 \u0633\u0644\u0633\u0644\u0629 \u062c\u062f\u064a\u062f\u0629! (Start a new streak!)"
            msg = (
                f"\U0001f305 \u0635\u0628\u0627\u062d \u0627\u0644\u062e\u064a\u0631 **{m['discord_name']}**!\n\n"
                f"\u0645\u0647\u0627\u0645\u0643 \u062c\u0627\u0647\u0632\u0629 (Tasks ready) \U0001f4cb\n"
                f"{streak_text}\n\n"
                f"\u0623\u0648\u0644 \u0645\u0647\u0645\u0629 (First task): **{first_task['name_ar']}** ({first_task['name']}) {first_task['emoji']}\n"
                f"\U0001f310 Practice online: {practice_url_with_token}\n\n"
                f"تمارينك بتتسجّل لوحدها على الصفحة (auto-logged). الكتابة `!6` والمجتمع `!7` \U0001f4aa"
            )
        else:
            streak_text = f"\U0001f525 Streak: **{streak}** days" if streak > 0 else "\U0001f331 Start a new streak today!"
            msg = (
                f"\U0001f305 Good morning **{m['discord_name']}**!\n\n"
                f"Your tasks are ready \U0001f4cb\n"
                f"{streak_text}\n\n"
                f"First task: **{first_task['name']}** {first_task['emoji']}\n"
                f"\U0001f310 Practice online: {practice_url_with_token}\n\n"
                f"Your page exercises log automatically. For writing/community type `!6` / `!7` \U0001f4aa"
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
async def weekly_recap():
    """Honest weekly recap every Sunday — real activity numbers only, no
    scores or grades.

    Replaces the old weekly "assessment", whose scoring gave 0 or 100 per
    skill purely on whether a task was submitted (attendance dressed up as a
    skill grade) and then labeled students Excellent…Critical — misleading
    and unprofessional. This simply reflects back what the student actually
    did this week; the owner promotes levels manually.
    """
    if _now().weekday() != 6:  # 6 = Sunday
        return
    if config.IS_GHOST_INSTANCE:
        return

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    members = database.all_active_members()
    sent = 0
    for member_data in members:
        discord_id = member_data["discord_id"]
        discord_member = guild.get_member(int(discord_id))
        if not discord_member:
            continue

        week_num = database.member_week_number(discord_id)
        subs = database.get_submissions_since(discord_id, days=7)
        exercises = len(subs)
        active_days = len({s["date"] for s in subs})
        current, longest = database.get_streak(discord_id)

        try:
            if exercises == 0:
                msg = (
                    f"📅 **Your week — Week {week_num}**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"No practice logged this week yet — a fresh start begins today! 🌱\n"
                    f"Open your practice page with `!link`.\n\n"
                    f"لسه مفيش تمارين الأسبوع ده — ابدأ النهاردة من `!link`. 💪"
                )
            else:
                msg = (
                    f"📅 **Your week — Week {week_num}**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"✅ Exercises completed: **{exercises}**\n"
                    f"📆 Days practiced: **{active_days}/7**\n"
                    f"🔥 Current streak: **{current}** days (best: {longest})\n\n"
                    f"Great consistency — keep going! 🏛️\n"
                    f"استمر على المداومة! 💪"
                )
            await discord_member.send(msg)
            sent += 1
        except (discord.Forbidden, discord.HTTPException):
            pass

    logger.info(f"Weekly recap: sent to {sent} member(s)")


@tasks.loop(hours=1)
async def streak_update():
    """Nudge students who have genuinely missed work — at THEIR hour, not ours.

    This runs hourly, but that is not when anyone gets messaged: it is how
    often each student is re-evaluated against their OWN rhythm
    (tasks.nudge_decision). A student who studies at 22:00 is considered late
    in the small hours after her slot; one who studies at 07:00 is considered
    late that afternoon. No single hour is treated as "late" for everybody,
    because there isn't one.

    It used to fire at 16:00 Asia/Dubai for the whole roster, which is how a
    student with a 43-day streak was told at 15:00 her time that she had not
    been active — she simply had not reached her evening session yet.

    An hourly loop was ALSO the shape of an older bug (2026-07-28), where an
    inactive student got the same DM every hour all day. What made that
    possible was the absence of a per-day guard, not the frequency. Three
    things now make a repeat impossible: the settings-table guard below,
    nudge_decision() requiring 24h+ of silence, and the fact that a student
    who stays away moves into the next intervention tier tomorrow rather than
    back into this one.
    """
    inactive = task_engine.check_inactive_members()
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    # The guard is keyed on the UTC date, not a Dubai date, so "once a day"
    # means the same thing for every student regardless of where they are.
    utc_today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    for action, members in inactive.items():
        if action != "dm_reminder":
            continue
        for m in members:
            did = str(m["discord_id"])
            key = f"streak_nudged_{did}"
            if database.get_setting(key, "") == utc_today:
                continue  # already nudged today — never double-send

            # The whole decision, per student, against their own rhythm and
            # their real submission times. Never a shared wall clock.
            send, reason = task_engine.nudge_decision(did)
            if not send:
                logger.debug(f"streak nudge skipped for {did}: {reason}")
                continue

            # A live streak contradicts the message on its face: it offers to
            # help keep a streak alive, so it cannot go to someone whose
            # streak already is. streak_at_risk() at 21:00 is the task that
            # legitimately says "do one task today".
            if (m.get("current_streak") or 0) > 0:
                logger.debug(f"streak nudge skipped for {did}: streak alive")
                continue

            prefs = database.get_notification_prefs(did)
            if not prefs.get("streak_alert", 1):
                continue

            discord_member = guild.get_member(int(did))
            if not discord_member:
                continue
            logger.info(f"streak nudge -> {did}: {reason}")
            try:
                await discord_member.send(
                    f"👋 Hey {m['discord_name']}! We haven't seen any tasks from "
                    f"you for a couple of days. Whenever you're ready, one task "
                    f"is enough to get going again — and if something is in the "
                    f"way, just reply here. 🏛️"
                )
                database.set_setting(key, utc_today)
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

    for level_key in config.CEFR_ORDER:
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

    for level_key in config.CEFR_ORDER:
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

    # Use A1 members' week (the entry level + largest cohort; A1 vocab is the
    # most useful for a mixed-level "word of the day" — higher levels already
    # know it and can still engage, A1 students are learning it). Fall back to
    # week 1 if no A1 members exist yet.
    members = database.members_at_level("A1")
    if members:
        week = database.member_week_number(members[0]["discord_id"])
    else:
        week = 1

    # Get today's day index (0=Saturday...6=Friday per curriculum convention)
    today = _now()
    day_index = (today.weekday() + 2) % 7  # Python: Mon=0; curriculum: Sat=0

    words = curriculum.get_vocabulary_for_day(week, day_index, "A1")
    if not words:
        # Fallback: try the full week's vocab and pick randomly
        words = curriculum.get_vocabulary_for_week(week, "A1")
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
        logger.info(f"Daily word posted: {word['word']} (A1 week {week})")
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

    # Auto-resume: if a maintenance window elapsed while still flagged active,
    # end it and announce "we're back" exactly once (self-heals a forgotten
    # /maintenance end within ~2 min of the window closing).
    try:
        await maintenance_mod.check_and_handle_auto_resume(bot)
    except Exception:
        pass

    # While maintenance is active, record today's date so the streak logic
    # bridges it (a maintenance day never breaks a student's streak). Cheap;
    # dedupes internally. Also catches a window that spans midnight.
    try:
        if maintenance_mod.is_active():
            maintenance_mod.mark_active_day()
    except Exception:
        pass

    # Check maintenance mode and update presence. Uses the unified
    # maintenance module (honors both the rich /maintenance state and the
    # legacy maintenance_mode flag set by deploy.py), so presence self-heals
    # within 2 min after a restart and auto-resumes when the window elapses.
    try:
        if maintenance_mod.is_active():
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

    # Hissar: bot-profile integrity (daily visible heartbeat; the fast alarm is
    # the bot_integrity_monitor loop). Added after the 2026-08-29 Ops-token theft.
    if database.is_feature_enabled("hissar_bot_integrity"):
        try:
            ok, findings = await bot_integrity.run_integrity_check()
            if ok:
                lines.append("   🛡️ Bot profiles: intact")
            else:
                lines.append("   🚨 *BOT PROFILE TAMPERING:*")
                for f in findings[:4]:
                    lines.append(f"      • {ops_hub.escape_markdown(f)}")
        except Exception as e:  # noqa: BLE001 — digest must never crash
            logger.warning(f"bot_integrity: digest check failed: {e}")

    lines.append("")
    lines.append("*All systems healthy\\.* ✅")

    await ops_hub.send_ops_message("\n".join(lines))
    # M4.4: check for churn risk as part of the morning ops cycle
    await ops_monitoring.check_churn_risk()
    # Wuslah W0.4: clean up expired link tokens (daily housekeeping)
    removed = database.cleanup_expired_tokens(days=30)
    if removed > 0:
        logger.info(f"Wuslah: cleaned up {removed} expired link token(s)")
    # Itqan: purge assessment recordings past the retention window (owner-review only).
    try:
        purged = database.itqan_purge_recordings(days=14)
        if purged > 0:
            logger.info(f"Itqan: purged {purged} assessment recording(s) older than 14 days")
    except Exception as e:
        logger.warning(f"Itqan: recording purge failed: {e}")


@tasks.loop(time=datetime.time(hour=9, minute=0, tzinfo=_zone()))
async def markaz_weekly_report():
    """Markaz Phase M4.1/M4.2 — weekly business report (Sunday 9 AM Dubai).

    Only fires on Sundays. Sends a comprehensive business dashboard to
    the owner via the Empire Ops bot."""
    now = datetime.datetime.now(_zone())
    if now.weekday() != 6:  # 6 = Sunday
        return
    await ops_monitoring.send_weekly_report()


@tasks.loop(time=datetime.time(hour=9, minute=45, tzinfo=_zone()))
async def itqan_weekly_report():
    """Itqan weekly-assessment owner summary (Sunday). Stays completely silent
    while the itqan_weekly_assessment flag is off, so it produces nothing until
    the feature is piloted (Phase 9)."""
    now = datetime.datetime.now(_zone())
    if now.weekday() != 6:  # Sunday only
        return
    if not database.is_feature_enabled("itqan_weekly_assessment"):
        return
    try:
        from . import assessment
        data = database.itqan_report_data()
        text = assessment.format_itqan_report(data).replace("`", "'")
        await ops_hub.send_ops_message(f"```\n{text}\n```")
    except Exception as e:
        logger.error(f"itqan_weekly_report failed: {e}")


@tasks.loop(time=datetime.time(hour=17, minute=0, tzinfo=_zone()))
async def itqan_due_nudge():
    """Nudge students who have a DUE weekly assessment (Arabic, once per due
    week). Per-member flag-gated inside, so it's silent outside the pilot."""
    try:
        from . import itqan_outcomes
        n = await itqan_outcomes.nudge_due_students()
        if n:
            logger.info(f"itqan: nudged {n} student(s) with a due assessment")
        # G4: also nudge students who are 1–2 days short of completing a week
        # (so finishing those day(s) unlocks that week's test). Once per
        # (student, week); no rule change to the unlock bar itself.
        n2 = await itqan_outcomes.nudge_almost_done_students()
        if n2:
            logger.info(f"itqan: nudged {n2} student(s) who are 1–2 days from unlocking a test")
    except Exception as e:
        logger.warning(f"itqan due-nudge loop failed: {e}")


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
    verification.reset_daily_together()
    community.reset_beacons()


@tasks.loop(hours=6)
async def bot_integrity_monitor():
    """Hissar: watch each bot's public identity for tampering and alert the owner
    FAST if it drifts. Added after the 2026-08-29 Ops-token theft, whose spam bio
    went unnoticed for ~4 days precisely because nothing watched for this.

    Every 6h it compares the Ops (Telegram) name/description/bio and the Discord
    bot username against their baselines (src/bot_integrity.py) and scans for spam
    signatures. On any drift it sends an immediate Empire Ops alert. Flag-gated
    (`hissar_bot_integrity`); best-effort, never crashes. The daily digest carries
    the same check as a visible heartbeat, but this is the fast alarm.

    De-dupes: it alerts on the transition into a tampered state and once per new
    distinct finding-set, not every 6h, so a slow owner response isn't spammed.
    """
    if not database.is_feature_enabled("hissar_bot_integrity"):
        return
    try:
        ok, findings = await bot_integrity.run_integrity_check()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"bot_integrity_monitor: check errored: {e}")
        return

    prev = getattr(bot, "_last_integrity_findings", None)
    if ok:
        if prev:  # recovered — tell the owner it's clean again
            await ops_hub.send_ops_message(
                "🛡️ *Bot profile integrity restored* — all bot identities match "
                "their baseline again\\.")
        bot._last_integrity_findings = None
        return

    signature = tuple(findings)
    if signature == prev:
        return  # already alerted for this exact state; don't re-spam
    bot._last_integrity_findings = signature

    # send_ops_alert escapes title/body itself, so pass PLAIN text (no markdown,
    # no manual escaping) or it double-escapes into literal backslashes.
    body = "\n".join(f"- {f}" for f in findings[:6])
    await ops_hub.send_ops_alert(
        "BOT PROFILE TAMPERING DETECTED",
        ("A bot's public identity no longer matches its baseline. This is the "
         "signature of a stolen token.\n\n" + body + "\n\n"
         "Act now: revoke/rotate the affected bot's token (BotFather /revoke for "
         "the Ops bot; Discord Developer Portal for the Discord bot), then restore "
         "the profile. See INCIDENT-2026-08-29-ops-bot-token.md."),
        severity="critical")
    logger.error(f"bot_integrity_monitor: TAMPERING — {findings}")


@tasks.loop(minutes=5)
async def beacon_cleanup_loop():
    """Majlis Phase 2+3: clean up expired beacon messages + reap empty
    dynamic Majlis rooms every 5 minutes. Flag-gated internally.
    Best-effort — never crashes."""
    try:
        guild = bot.get_guild(config.GUILD_ID)
        if guild:
            await community.cleanup_expired_beacons(guild)
            await community.reap_empty_majlis_rooms(guild)
    except Exception:
        pass


@tasks.loop(minutes=1)
async def community_hour_loop():
    """Majlis Phase 5: fire the Community Hour rally when the window starts.
    Checks every minute; fires once per day (deduped in community.py).
    Flag-gated internally. Best-effort — never crashes."""
    try:
        if community.community_hour_due():
            guild = bot.get_guild(config.GUILD_ID)
            if guild:
                await community.run_community_hour(guild)
    except Exception:
        pass


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


@tasks.loop(time=datetime.time(hour=3, minute=0, tzinfo=_zone()))
async def onboarding_gate_check():
    """Onboarding safety net (session-33). Once daily (03:00 Dubai) run a
    read-only audit of every active student against the two onboarding
    signals — the #rules gateway role and a guided-journey row — and alert
    the owner via Empire Ops if anyone is in the server without the gate
    (a bypass) or holds the role but never started the journey. Alerts only
    when the flagged set CHANGES (no daily spam) and NEVER DMs a student.
    This is the tripwire that would have caught the session-23 gap.
    """
    if config.IS_GHOST_INSTANCE:
        return
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return
    try:
        await role_gate.run_onboarding_reconciliation(guild)
    except Exception as e:
        logger.error(f"onboarding_gate_check failed: {e}")


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

    D022 fix (Hisn H4.6): staggered 5 minutes after weekly_recap
    (also 10:00 Sunday) to avoid sending 2 individual DMs to the same
    student within the same instant every Sunday.
    """
    guild = bot.get_guild(config.GUILD_ID)
    if guild:
        await features.check_absence_recovery(guild)


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


@tasks.loop(time=datetime.time(hour=11, minute=0, tzinfo=_zone()))
async def nour_growth_letter_task():
    """Masar M2.2: Nour's Weekly Growth Letter — the flagship fix for
    Hisn D020 (the AI tips engine that was designed but never built).

    Runs every WEDNESDAY at 11 AM Dubai time. Deliberately placed on a
    different DAY than every other once-a-week task in this codebase
    (markaz_weekly_report 09:00 Sun, weekly_recap 10:00 Sun,
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
        # Assign the starting CEFR role (A1) — students start on A1, not legacy L0.
        if isinstance(ctx.author, discord.Member):
            await _assign_level_role(ctx.author, "A1")
        msg = f"🌱 Welcome {ctx.author.mention}! You're registered at **A1** (Breakthrough)."
        if goal:
            msg += f"\n🎯 Goal: **{goal}**"
        msg += "\n\nYour daily tasks will appear in #a1-daily-tasks every morning."
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
        level = member_data.get("level", "A1")
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

        # DM the student with their score (beginner grace removed — Nutq:
        # every recording gets a real score + correction from attempt #1)
        try:
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
    """Log a Discord-side task. Empire Reset (session-33): the 5 core
    exercises (accent, vocab, shadowing, listening, speaking) are logged
    AUTOMATICALLY when finished on the practice page, so only the two
    Discord-side tasks are logged here — writing (`!6`) and community
    (`!7`). Every other invocation (no task, unknown task, or one of the
    5 auto-logged exercises) gently points the student to the right place.
    """
    valid_tasks = [t["id"] for t in config.DAILY_TASKS]

    # Normalize a numeric arg (e.g. "!done 6" or the Arabic "!تم 6" which
    # rewrites to "!done 6") to its task id, so numbers and names behave
    # identically here.
    _num_to_task = {str(i + 1): t["id"] for i, t in enumerate(config.DAILY_TASKS)}
    if task:
        task = task.lower().strip()
        task = _num_to_task.get(task, task)

    # Only writing + community are logged in Discord. No task, an unknown
    # task, or any of the 5 practice-page exercises → signpost, don't log.
    if (not task) or (task not in valid_tasks) or (task in features.CALENDAR_TASK_IDS):
        await ctx.send(_TASK_REDIRECT_MSG)
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

    # Darb Phase 2: record practice mastery for the student's current
    # calendar day (same once-per-day tier logic the practice page uses).
    # CALENDAR_EXERCISES = the 5 practice-page exercises incl. speaking (E1),
    # so `!done speaking` also advances the calendar; writing/community stay
    # Discord-only and don't map to the practice calendar.
    if task in database.CALENDAR_EXERCISES:
        try:
            from . import darb as darb_mod
            wk_day = darb_mod.today_week_day(str(ctx.author.id))
            if wk_day:
                member_data = database.get_member(str(ctx.author.id))
                level = (member_data.get("level", "A1") if member_data else "A1")
                database.record_practice_mastery(
                    str(ctx.author.id), level, wk_day[0], wk_day[1], task
                )
        except Exception as e:
            logger.warning(f"!done mastery recording failed (non-fatal): {e}")

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
        level = member_data.get("level", "A1") if member_data else "A1"
        if config.cefr_key(level) == "A1":
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

    level_info = config.level_info(member["level"])
    week = database.member_week_number(str(ctx.author.id))
    completion = task_engine.calculate_completion_rate(str(ctx.author.id))
    completed_today = database.tasks_completed_today(str(ctx.author.id))
    bar = "█" * len(completed_today) + "░" * (7 - len(completed_today))

    # Phase E (E6, R6.2/R6.4 — owner feedback #9: "finished all tasks but
    # still shows remaining"). Same calendar(5)-vs-Discord(2) breakdown as
    # !today (features.show_today), reusing the same shared task-id sets
    # so the two commands can never disagree about which is which.
    cal_done = len([t for t in completed_today if t in features.CALENDAR_TASK_IDS])
    disc_done = len([t for t in completed_today if t in features.DISCORD_ONLY_TASK_IDS])

    msg = (
        f"**{ctx.author.display_name}'s Progress**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{level_info['emoji']} Level: **{member['level']}** — {level_info['name']}\n"
        f"📅 Week: **{week}**\n"
        f"🎯 Goal: {member['goal'] or '—'}\n"
        f"🏆 Points: **{member['total_points']}**\n"
        f"🔥 Streak: **{member['current_streak']}** days (best: {member['longest_streak']})\n"
        f"📈 Completion rate (7 days): **{completion}%**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Today [{bar}] {len(completed_today)}/7  "
        f"(🌐 calendar {cal_done}/{len(features.CALENDAR_TASK_IDS)} + 💬 Discord {disc_done}/{len(features.DISCORD_ONLY_TASK_IDS)})\n"
        f"Track: {member['track']}"
    )

    # Phase 9 (transparency): CEFR can-do progress — how many of this level's
    # can-do goals the student has evidenced by the weeks they've mastered.
    try:
        from . import assessment
        cdp = assessment.can_do_progress(str(ctx.author.id), member["level"])
        if cdp["total"]:
            filled = round(cdp["pct"] / 10)
            cbar = "█" * filled + "░" * (10 - filled)
            msg += (
                f"\n🎓 CEFR can-do ({cdp['level']}): **{cdp['reached']}/{cdp['total']}** "
                f"[{cbar}] {cdp['pct']}%\n"
                f"   Your checklist: {config.PRACTICE_PLATFORM_URL}/can-do/"
            )
    except Exception:
        pass

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

    # Empire Reset 1b: fold the old standalone !streak (next-milestone) and
    # !level (how-to-advance) hints into the one dashboard so students have a
    # single place to look.
    for threshold, bonus in sorted(config.STREAK_BONUS_POINTS.items()):
        if member["current_streak"] < threshold:
            msg += (f"\n🎯 Next streak bonus: **{threshold} days** (+{bonus} pts) — "
                    f"{threshold - member['current_streak']} to go")
            break
    if level_info.get("advancement_score"):
        msg += ("\n🚀 To advance: keep practicing daily — your coach promotes "
                "you when you're ready.")

    await ctx.send(msg)


@bot.command(name="streak")
async def cmd_streak(ctx):
    """Empire Reset 1b: folded into !progress (which now shows your streak
    and how far to your next bonus). Kept as a gentle signpost."""
    # Aql (#15) Phase A6.4: viewing your streak is still a real signal that
    # the student knows the streak system exists.
    database.set_journey_coverage(str(ctx.author.id), knows_streaks=True)
    await ctx.send(
        "🔥 سلسلتك (وكام يوم فاضل لأقرب مكافأة) دلوقتي في `!progress`.\n"
        "🔥 Your streak — and your next bonus — is now in `!progress`."
    )



@bot.command(name="top")
async def cmd_top(ctx):
    """Points leaderboard — the top 10, PLUS the requester's own standing
    when they're outside that slice.

    Before this, `!top` only ever showed the top 10 by points, so with 16
    students the lower ~6 saw a board they weren't on and reported being
    "not listed". This appends a personal "your rank" line for anyone not
    already shown — mirroring the web `/api/leaderboard`, which has always
    returned `your_rank`/`your_points`. Purely additive: the top-10 board
    is unchanged, and it stays a top-N board (passes the 5-year/10x scale
    test — we never dump all members).

    Ijtihad Phase 5: when `ijtihad_boards` is on, this redirects to the SEASON
    board and says so in one line. `!top` has always meant "lifetime ranking", and
    lifetime ranking is precisely what rewarded seniority over work — but silently
    redefining a familiar command is how students stop trusting the numbers, so the
    old name keeps working and explains itself instead of either lying or dying."""
    if database.is_feature_enabled(ijtihad_boards.FLAG, str(ctx.author.id)):
        did = str(ctx.author.id)
        season = database.ijtihad_current_season()
        srows = database.ijtihad_season_leaderboard(season, limit=5) if season else []
        board = ijtihad_boards.format_season_board(
            season, srows, me_id=did,
            my_rank=database.ijtihad_season_rank(did, season) if season else 0,
            my_points=database.ijtihad_season_points(did, season) if season else 0)
        await ctx.send(
            "ℹ️ `!top` now shows **this season's effort** — lifetime totals moved "
            "to `!sijil`.\n\n" + board)
        return
    rows = database.leaderboard(10)
    if not rows:
        await ctx.send("No members yet. Be the first to `!join`! 🌱")
        return
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    lines = ["🏆 **Points Leaderboard**\n"]
    for i, row in enumerate(rows):
        lvl = config.level_info(row["level"])
        lines.append(f"{medals[i]} {row['discord_name']} — {row['total_points']} pts {lvl['emoji']}")

    # If the requester isn't in the shown top slice, append their own rank
    # so nobody is left feeling "not listed". get_member_rank() is 1-indexed
    # over ALL active members by points; None => not an active member (never
    # !join'd), in which case we gently point them in rather than show
    # nothing. Wrapped defensively — a leaderboard read must never crash.
    try:
        author_id = str(ctx.author.id)
        shown_ids = {str(r["discord_id"]) for r in rows}
        if author_id not in shown_ids:
            rank = database.get_member_rank(author_id)
            if rank:
                me = database.get_member(author_id) or {}
                lvl = config.level_info(me.get("level"))
                total = database.member_count()
                name = me.get("discord_name") or ctx.author.display_name
                pos = f"#{rank}/{total}" if total else f"#{rank}"
                # Arabic-only label line, then a name-first data line so an
                # Arabic display name sits at the edge (a single RTL->LTR
                # transition) rather than sandwiched between LTR groups —
                # per the project's bidi rule.
                lines.append("⋯")
                lines.append("📍 **ترتيبك دلوقتي:**")
                lines.append(
                    f"**{name}** — {pos} · {me.get('total_points', 0)} pts {lvl['emoji']}"
                )
            else:
                lines.append("⋯")
                lines.append("📍 لسه مش في اللوحة — اعمل `!join` وابدأ تجمّع نقاط 🌱")
                lines.append("📍 You're not on the board yet — use `!join` to start earning points 🌱")
    except Exception:
        # Never let the personal-rank enrichment break the core board.
        pass

    await ctx.send("\n".join(lines))


@bot.command(name="streaks")
async def cmd_streaks(ctx):
    """Empire Reset 1b: one leaderboard now — see !top."""
    await ctx.send(
        "🏆 في لوحة ترتيب واحدة بس دلوقتي — اكتب `!top`.\n"
        "🏆 There's a single leaderboard now — use `!top`."
    )


@bot.command(name="level")
async def cmd_level(ctx):
    """Empire Reset 1b: folded into !progress (which shows your level, week,
    and how to advance). Kept as a gentle signpost."""
    await ctx.send(
        "ℹ️ مستواك وأسبوعك وطريقة الترقية دلوقتي كلها في `!progress`.\n"
        "ℹ️ Your level, week, and how to advance are now all in `!progress`."
    )


@bot.command(name="growth", aliases=["تقدمي"])
async def cmd_growth(ctx):
    """Ijtihad Phase 6: your improvement against your OWN recent baseline."""
    if not database.is_feature_enabled(ijtihad_growth.FLAG, str(ctx.author.id)):
        return
    did = str(ctx.author.id)
    if not database.get_member(did):
        await ctx.send("🔒 Register first with `!start`.\n🔒 اعمل `!start` الأول.")
        return
    g = database.ijtihad_growth(did)
    lines = [f"📈 **{ctx.author.display_name}** — "
             f"Your growth / تقدّمك", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
             ijtihad_growth.format_my_growth(g)]
    recs = database.ijtihad_recognitions_for(did, limit=5)
    if recs:
        lines.append("")
        lines.append("🏅 **Recent recognitions / آخر التقديرات**")
        for r in recs:
            lines.append(f"  {ijtihad_growth.format_recognition(r['kind'])}")
    await ctx.send("\n".join(lines))


@bot.command(name="improved", aliases=["الأكثر-تقدما"])
async def cmd_improved(ctx):
    """Ijtihad Phase 6: the Most Improved board — a beginner can top it."""
    if not database.is_feature_enabled(ijtihad_growth.FLAG, str(ctx.author.id)):
        return
    rows = database.ijtihad_most_improved_board(limit=5)
    await ctx.send(ijtihad_growth.format_most_improved(rows))


@bot.command(name="spotlight", aliases=["ضوء-الأسبوع"])
async def cmd_spotlight(ctx):
    """Ijtihad Phase 6: this week's spotlight — the metric rotates weekly."""
    if not database.is_feature_enabled(ijtihad_growth.FLAG, str(ctx.author.id)):
        return
    await ctx.send(ijtihad_growth.format_spotlight(ijtihad_growth.build_spotlight()))


@bot.command(name="season", aliases=["الموسم"])
async def cmd_season(ctx):
    """Ijtihad Phase 5: this season's effort board.

    Replaces `!top` as the headline ranking. `!top` still works and points here,
    because silently changing what a familiar command measures is how a student
    stops trusting the numbers.
    """
    if not database.is_feature_enabled(ijtihad_boards.FLAG, str(ctx.author.id)):
        return
    did = str(ctx.author.id)
    season = database.ijtihad_current_season()
    rows = database.ijtihad_season_leaderboard(season, limit=5) if season else []
    my_rank = database.ijtihad_season_rank(did, season) if season else 0
    my_points = database.ijtihad_season_points(did, season) if season else 0
    await ctx.send(ijtihad_boards.format_season_board(
        season, rows, me_id=did, my_rank=my_rank, my_points=my_points))


@bot.command(name="peers", aliases=["زمايلي"])
async def cmd_peers(ctx):
    """Ijtihad Phase 5: how you compare with students at YOUR stage."""
    if not database.is_feature_enabled(ijtihad_boards.FLAG, str(ctx.author.id)):
        return
    did = str(ctx.author.id)
    if not database.get_member(did):
        await ctx.send("🔒 Register first with `!start`.\n🔒 اعمل `!start` الأول.")
        return
    season = database.ijtihad_current_season()
    cohort = database.ijtihad_journey_peers(did)
    rows = (database.ijtihad_season_board_scoped(season, cohort["peers"], limit=5)
            if season else [])
    await ctx.send(ijtihad_boards.format_peers_board(
        cohort["scope"], cohort["week"], season, rows, me_id=did))


@bot.command(name="consistency", aliases=["استمرارية"])
async def cmd_consistency(ctx):
    """Ijtihad Phase 5: longest current runs of complete days."""
    if not database.is_feature_enabled(ijtihad_boards.FLAG, str(ctx.author.id)):
        return
    rows = database.ijtihad_consistency_board(limit=5)
    await ctx.send(ijtihad_boards.format_consistency_board(rows))


def build_ijtihad_announcement(season: dict = None) -> str:
    """The launch announcement, bilingual.

    Ordered deliberately: *your history is safe* BEFORE *the race restarts*. The
    reverse order reads as a threat to the students who have been here longest,
    and they are the ones with most to lose from a reset.

    Follows the Sahin bidi rule — no Arabic line carries two embedded LTR tokens,
    and every command sits alone on its own line.
    """
    window = ""
    if season:
        window = f"\n_{season['started_on']} → {season['ends_on']}_"
    return (
        "🏛️ **حاجة جديدة في الإمبراطورية / Something new**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "**أولًا: سجلك بقى دائم.**\n"
        "كل أسبوع أتقنته، كل امتياز، كل مستوى عديته — محفوظ للأبد. مايتصفّرش أبدًا.\n"
        "**First: your record is now permanent.**\n"
        "Every week you mastered, every distinction, every level you passed — kept "
        "forever. It never resets.\n\n"
        "`!sijil`\n\n"
        "**واللي اتغيّر: الاجتهاد بقى بمواسم من ٤ أسابيع.**\n"
        "**What changed: effort now runs in 4-week seasons.**\n"
        f"{window}\n\n"
        "يعني اللي بيشتغل بجد **دلوقتي** هو اللي يتقدّم — مهم مش إمتى انضممت.\n"
        "So whoever works hardest **right now** leads — not whoever joined first.\n\n"
        "**وكمان:**\n"
        "• اختار هدفك اليومي — ٣ أو ٥ أو ٧ مهام. توصله؟ يومك كامل.\n"
        "  Choose your own daily target — 3, 5 or 7. Hit it and your day counts.\n"
        "• عندك ٢ أيام إجازة في الموسم — يوم واحد ناقص مش بيكسر سلسلتك.\n"
        "  You get 2 streak freezes a season — one missed day won't break you.\n"
        "• التقدّم بيتقاس عليك إنت، مش على غيرك.\n"
        "  Improvement is measured against you, not against anyone else.\n\n"
        "`!target`  ·  `!season`  ·  `!growth`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "الشغل هو اللي بيتحسب. / **Work is what counts.** 🏛️"
    )


@bot.command(name="ijtihad-announce")
@commands.has_permissions(administrator=True)
async def cmd_ijtihad_announce(ctx, channel_name: str = "announcements",
                               confirm: str = ""):
    """Owner: post the Ijtihad launch announcement.

    Requires an explicit `confirm` argument, because this writes to a public
    channel and there is no undo for something 17 students have already read.
    Without it, previews to the current channel instead.
    """
    season = database.ijtihad_current_season()
    text = build_ijtihad_announcement(season)
    if confirm != "confirm":
        await ctx.send("👀 **Preview** (nothing posted). To post for real:\n"
                       f"`!ijtihad-announce {channel_name} confirm`\n\n"
                       "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n" + text)
        return
    channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)
    if not channel:
        await ctx.send(f"❌ No channel named `#{channel_name}`.")
        return
    try:
        await channel.send(text)
        await ctx.send(f"✅ Posted to #{channel_name}.")
    except Exception as e:
        await ctx.send(f"❌ Couldn't post to #{channel_name}: {e}")


@bot.command(name="ijtihad-reanchor")
@commands.has_permissions(administrator=True)
async def cmd_ijtihad_reanchor(ctx, new_start: str = "", confirm: str = ""):
    """Owner: move the season calendar to a new start date.

    Built to fix one specific thing: Season 1 began a day before the new award
    table was enabled, so it holds ~2 days of points earned at roughly double the
    current rate — about a 220-point head start for whoever worked those days.
    Re-anchoring pushes those days OUTSIDE the season window, where they become
    legacy points (still counted for life, still in `!sijil`), leaving Season 1
    with one consistent rule set. Nobody's history is rewritten.
    """
    if not new_start:
        season = database.ijtihad_current_season()
        cur = (f"{season['label']}: {season['started_on']} → {season['ends_on']}"
               if season else "no season")
        await ctx.send(f"Current — {cur}\n"
                       f"Usage: `!ijtihad-reanchor YYYY-MM-DD confirm`")
        return
    if confirm != "confirm":
        await ctx.send(
            f"⚠️ This will restart the season calendar at **{new_start}**.\n"
            f"Points earned before that date become legacy (still counted for "
            f"life, still in `!sijil`) and leave the season board.\n"
            f"Nothing is deleted or rewritten.\n\n"
            f"To proceed: `!ijtihad-reanchor {new_start} confirm`")
        return
    ok, detail = database.ijtihad_reanchor_seasons(new_start)
    if not ok:
        msg = {
            "bad_date": "❌ Use YYYY-MM-DD.",
            "multiple_seasons": "❌ Refused: more than one season exists. "
                                "Re-anchoring now would move a window students "
                                "already competed in.",
            "season_completed": "❌ Refused: a season has already finished.",
        }.get(detail, f"❌ Refused: {detail}")
        await ctx.send(msg)
        return
    s = detail.get("season")
    if not s:
        await ctx.send(f"✅ Anchor set to {new_start} (still in the future — no "
                       f"active season yet).")
        return
    await ctx.send(f"✅ **{s['label']}** now runs "
                   f"**{s['started_on']} → {s['ends_on']}**.\n"
                   f"Earlier points are legacy now — still counted for life, "
                   f"still in `!sijil`.")


@bot.command(name="ijtihad-metrics")
@commands.has_permissions(administrator=True)
async def cmd_ijtihad_metrics(ctx):
    """Owner: did the Ijtihad rework actually work? (spec design §9)

    Includes the GUARD metric. If veteran engagement dropped, the honour track
    failed to do its job and that matters more than any improvement elsewhere —
    so it is reported alongside the good news, not buried.
    """
    m = database.ijtihad_metrics()
    season = m["season"]
    season_line = (f"{season['label']} ({season['started_on']} → {season['ends_on']})"
                   if season else "no season yet")
    newcomer = "✅ yes" if m["newcomer_in_a_top3"] else "—  not yet"
    lines = [
        "📊 **Ijtihad metrics**",
        f"Season: {season_line}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Active students: **{m['active_members']}**",
        "",
        "**Is a newcomer visible?**",
        f"  Joined in last 14 days: {m['newcomers_14d']}",
        f"  A newcomer in some top-3: {newcomer}",
        "",
        "**Is recognition circulating?**",
        f"  Distinct students recognised (30d): **{m['distinct_recognised_30d']}**",
        f"  Recognitions total (30d): {m['recognitions_30d']}",
        "",
        "**Are students doing the work?**",
        f"  Complete days (7d): **{m['full_days_7d']}** "
        f"({m['full_days_per_student_7d']}/student)",
        f"  Active rate (7d): **{m['active_rate_7d']}%**",
        "",
        "🛡️ **Guard — veterans must not disengage**",
        f"  Veterans (>{m['veteran_days']}d): {m['veterans']}",
        f"  Active this week: **{m['veterans_active_7d']}** "
        f"({m['veteran_active_rate_7d']}%)",
        ("" if m["guard_meaningful"] else
         "  ⚠️ _No student is older than the veteran threshold yet, so this "
         "guard cannot see anything. Lower it with_ "
         "`!ijtihad-config ijtihad_veteran_days <days>`_._"),
        "",
        "_Run this again in a week and compare — the numbers only mean something "
        "against their own history._",
    ]
    await ctx.send("\n".join(lines))


@bot.command(name="ijtihad-preview")
@commands.has_permissions(administrator=True)
async def cmd_ijtihad_preview(ctx, limit: int = 10):
    """Owner: dry-run — what each student's record and season standing looks like.

    Exists so the migration could be reviewed BEFORE anything was announced
    (spec task 8.1): a reset is safe only if you can see, in advance, exactly what
    each student will see.
    """
    season = database.ijtihad_current_season()
    lines = ["🔍 **Ijtihad preview** — per-student state",
             f"Season: {season['label'] if season else 'none'}",
             "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for m in database.all_active_members()[:limit]:
        mid = str(m["discord_id"])
        rec = database.sijil_record(mid)
        sp = database.ijtihad_season_points(mid, season) if season else 0
        fd = database.ijtihad_full_day_streak(mid, consume_freezes=False)
        name = (m.get("discord_name") or "?").split("#")[0]
        lines.append(
            f"**{name}** ({m.get('level','?')}) — season **{sp}** · "
            f"legacy {rec['legacy_xp']} · 📚{rec['weeks_mastered']} "
            f"⭐{rec['distinctions']} · 🔥{fd['streak']}d · "
            f"target {database.ijtihad_get_target(mid, season)}")
    total = database.member_count()
    if total > limit:
        lines.append(f"_…and {total - limit} more (raise the limit: "
                     f"`!ijtihad-preview {total}`)_")
    await ctx.send("\n".join(lines)[:1900])


@bot.command(name="ijtihad-config")
@commands.has_permissions(administrator=True)
async def cmd_ijtihad_config(ctx, key: str = "", value: str = ""):
    """Owner: view or set Ijtihad tunables (season length, Season 1 start,
    award amounts, target default, freezes per season).

    Exists because the Season 1 start date must be set BEFORE the seasons flag is
    enabled, and editing settings on the server by hand is exactly the kind of
    step that gets skipped or mistyped.
    """
    cfg = database.get_ijtihad_config()
    if not key:
        lines = ["⚙️ **Ijtihad config**", "```"]
        for k, v in cfg.items():
            lines.append(f"{k} = {v if v != '' else '(auto)'}")
        lines.append("```")
        lines.append("Set with: `!ijtihad-config <key> <value>`")
        await ctx.send("\n".join(lines))
        return
    if not value:
        await ctx.send(f"`{key}` = `{cfg.get(key, '(unknown key)')}`")
        return
    if database.set_ijtihad_config(key, value):
        await ctx.send(f"✅ `{key}` set to `{value}`")
    else:
        await ctx.send(f"❌ Unknown key `{key}`. Run `!ijtihad-config` to list them.")


@bot.command(name="target", aliases=["هدفي"])
async def cmd_target(ctx, value: str = ""):
    """Ijtihad Phase 4: view or set your Personal Daily Target (3, 5 or 7).

    The point of this command: "did I do my work today?" is judged against YOUR
    committed target, not a fixed 7. A student with a job and kids who genuinely
    manages 3 a day gets full credit for 3/3, instead of being permanently four
    tasks short of a bar built for someone with more free time.
    """
    if not database.is_feature_enabled("ijtihad_personal_target", str(ctx.author.id)):
        return
    did = str(ctx.author.id)
    if not database.get_member(did):
        await ctx.send("🔒 Register first with `!start`.\n🔒 اعمل `!start` الأول.")
        return

    season = database.ijtihad_current_season()
    current = database.ijtihad_get_target(did, season)
    choices = "/".join(str(c) for c in database.IJTIHAD_TARGET_CHOICES)

    if not value:
        chosen = database.ijtihad_target_is_set(did, season)
        fd = database.ijtihad_full_day_streak(did)
        left = database.ijtihad_freezes_remaining(did, season)
        note = ("" if chosen else
                f"\n_(default — pick your own with_ `!target {choices}`_)_")
        await ctx.send(
            f"🎯 **Your daily target: {current} tasks**{note}\n"
            f"🎯 **هدفك اليومي: {current} مهام**\n\n"
            f"🔥 Full-day streak: **{fd['streak']}**\n"
            f"🧊 Streak freezes left this season: **{left}**\n\n"
            f"A day counts as complete when you hit your own target.\n"
            f"اليوم يتحسب كامل لما توصل هدفك إنت."
        )
        return

    try:
        wanted = int(value)
    except ValueError:
        await ctx.send(f"❌ Pick one of: {choices}\n❌ اختار واحد من: {choices}")
        return

    ok, reason = database.ijtihad_set_target(did, wanted, season)
    if ok:
        await ctx.send(
            f"✅ Target set to **{wanted} tasks a day** for this season.\n"
            f"✅ هدفك بقى **{wanted} مهام في اليوم** للموسم ده.\n\n"
            f"Hit it and the day counts as complete — even on a busy day.\n"
            f"لما توصله اليوم يتحسب كامل — حتى لو يوم مشغول."
        )
    elif reason == "bad_target":
        await ctx.send(f"❌ Pick one of: {choices}\n❌ اختار واحد من: {choices}")
    elif reason == "already_set":
        await ctx.send(
            f"🔒 You already set your target this season (**{current}**).\n"
            f"🔒 إنت اخترت هدفك الموسم ده (**{current}**).\n\n"
            f"You can change it next season.\n"
            f"تقدر تغيّره الموسم الجاي."
        )
    else:
        await ctx.send("⏳ Seasons haven't started yet.\n⏳ المواسم لسه مبدأتش.")


@bot.command(name="sijil", aliases=["honour", "honor", "سجل"])
async def cmd_sijil(ctx):
    """Ijtihad Phase 1: your permanent Record of Honour.

    Deliberately separate from !top / points: this shows only what you EARNED
    (weeks mastered, distinctions, levels passed, perfect days, best streak),
    never how long you have been a member. It never resets, which is what makes
    a seasonal effort reset safe.
    """
    if not database.is_feature_enabled(sijil.FLAG, str(ctx.author.id)):
        return
    member = database.get_member(str(ctx.author.id))
    if not member:
        await ctx.send("🔒 Register first with `!start` — then your Sijil begins.\n"
                       "🔒 اعمل `!start` الأول — وبعدها يبدأ سجلك.")
        return
    record = sijil.build_record(str(ctx.author.id))
    await ctx.send(sijil.format_record(record, ctx.author.display_name))


@bot.command(name="hall", aliases=["قاعة-الشرف"])
async def cmd_hall_of_honour(ctx):
    """Ijtihad Phase 1: the Hall of Honour — ranked by achievement, not tenure."""
    if not database.is_feature_enabled(sijil.FLAG, str(ctx.author.id)):
        return
    entries = database.sijil_hall_of_honour(limit=5)
    await ctx.send(sijil.format_hall_of_honour(entries))


@bot.command(name="ping-me", aliases=["pingme", "إشعارات-المجلس"])
async def cmd_ping_me(ctx):
    """Majlis Phase 4: toggle the community-pings opt-in role.
    Opted-in members get @-mentioned by beacons and Knock."""
    result = await community.toggle_pings_role(ctx.author, ctx.guild)
    if result == "added":
        await ctx.send(
            "✅ فعّلت إشعارات المجلس — هتوصلك إشعارات لما حد يكون في اللاونج.\n"
            "✅ Community pings ON — you'll be notified when someone's in the Majlis."
        )
    elif result == "removed":
        await ctx.send(
            "🔕 ألغيت إشعارات المجلس — مش هتوصلك إشعارات.\n"
            "🔕 Community pings OFF — you won't be pinged anymore."
        )
    elif result == "disabled":
        await ctx.send(
            "⚠️ الميزة مش مفعّلة دلوقتي.\n"
            "⚠️ This feature isn't enabled yet."
        )
    else:
        await ctx.send("⚠️ حصل خطأ — جرّب تاني. | Something went wrong — try again.")


@bot.command(name="knock", aliases=["طق"])
async def cmd_knock(ctx):
    """Majlis Phase 4: Knock — ping opted-in members that you're in the
    Majlis and looking for company. Rate-limited, quiet-hours aware."""
    result = await community.do_knock(ctx.author, ctx.guild)
    if result == "sent":
        await ctx.send("👋 تم! بعتنا إشعار للمشتركين. | Done! Pinged opted-in members.")
    elif result == "not_in_majlis":
        await ctx.send(
            "⚠️ لازم تكون في المجلس (voice-lounge) الأول عشان تعمل Knock.\n"
            "⚠️ You need to be in the Majlis first to Knock."
        )
    elif result == "quiet_hours":
        await ctx.send(
            "🌙 دلوقتي ساعات هدوء — جرّب بعدين.\n"
            "🌙 It's quiet hours right now — try later."
        )
    elif result.startswith("cooldown:"):
        sec = result.split(":")[1]
        await ctx.send(
            f"⏳ استنّى {sec} ثانية قبل ما تعمل Knock تاني.\n"
            f"⏳ Wait {sec}s before knocking again."
        )
    elif result == "disabled":
        await ctx.send(
            "⚠️ الميزة مش مفعّلة دلوقتي.\n"
            "⚠️ This feature isn't enabled yet."
        )
    else:
        await ctx.send("⚠️ حصل خطأ — جرّب تاني. | Something went wrong — try again.")


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


# ── Guide deep-links: a topic keyword (EN or Arabic) → student-guide anchor.
#    Powers `!help <topic>` and `!guide <topic>` so anyone can be sent straight
#    to the exact section (e.g. practice.empireenglish.online/guide#streaks). ──
_GUIDE_TOPICS = {
    "start": "quickstart", "quickstart": "quickstart", "ابدأ": "quickstart", "بداية": "quickstart",
    "link": "access", "access": "access", "login": "access", "دخول": "access", "كود": "access", "ربط": "access",
    "task": "tasks", "tasks": "tasks", "مهام": "tasks", "مهمة": "tasks",
    "channel": "server", "channels": "server", "قناة": "server", "قنوات": "server",
    "calendar": "calendar", "تقويم": "calendar",
    "streak": "streaks", "streaks": "streaks", "سلسلة": "streaks",
    "point": "points", "points": "points", "نقاط": "points", "ترتيب": "points", "leaderboard": "points",
    "level": "levels", "levels": "levels", "مستوى": "levels", "مستويات": "levels",
    "pronunciation": "pronunciation", "نطق": "pronunciation", "grade": "pronunciation", "محاكاة": "pronunciation",
    "itqan": "itqan", "assessment": "itqan", "اختبار": "itqan",
    "notification": "notifications", "notifications": "notifications",
    "تنبيه": "notifications", "تنبيهات": "notifications", "اشعارات": "notifications", "إشعارات": "notifications",
    "privacy": "privacy", "data": "privacy", "خصوصية": "privacy", "بيانات": "privacy",
    "install": "install", "app": "install", "تطبيق": "install",
    "trouble": "troubleshoot", "problem": "troubleshoot", "مشكلة": "troubleshoot", "مشاكل": "troubleshoot",
    "command": "commands", "commands": "commands", "اوامر": "commands", "أوامر": "commands",
    "word": "review", "words": "review", "srs": "review", "كلمات": "review", "مراجعة": "review",
    "glossary": "glossary", "قاموس": "glossary", "مصطلحات": "glossary",
    "rules": "rules", "قواعد": "rules",
    "rights": "rights", "حقوق": "rights",
}


def _guide_link(anchor: str = "") -> str:
    base = config.PRACTICE_PLATFORM_URL.rstrip("/") + "/guide"
    return (base + "#" + anchor) if anchor else base


async def _send_guide_topic(ctx, topic: str) -> None:
    """Reply with a deep link to the guide section for `topic` (or options)."""
    anchor = _GUIDE_TOPICS.get(topic)
    if anchor:
        await ctx.send(
            f"📖 كل التفاصيل عن **{topic}** في دليلك:\n{_guide_link(anchor)}\n"
            f"— الدليل الكامل: {_guide_link()}"
        )
    else:
        await ctx.send(
            "📖 مش لاقي الموضوع ده. جرّب مثلاً: "
            "`streaks` · `points` · `levels` · `tasks` · `pronunciation` · "
            "`notifications` · `itqan` · `privacy` · `install` · `commands`\n"
            f"أو افتح الدليل الكامل: {_guide_link()}"
        )


def _voice_requirement_text(ctx) -> str:
    """Describe the voice half of task #7 accurately for THIS student.

    Majlis Phase 1 added a second, easier path (5 min together in the lounge)
    alongside the original 10-min any-voice path. `!help` kept describing only
    the old one, so the cheaper route was invisible.
    """
    try:
        did = str(ctx.author.id)
        if database.is_feature_enabled("community_together_credit", did):
            mins = community.get_together_minutes_threshold()
            return (f"**{mins} min together in 🎙️ voice-lounge** "
                    f"— or 10 min in any voice channel")
    except Exception:  # noqa: BLE001 — help must never fail to render
        pass
    return "10 min in voice"


def _majlis_help_section(ctx) -> str:
    """The Majlis block for `!help`, gated per flag.

    Written because of a real gap found 2026-08-29: Majlis went live on
    2026-08-22 and `!ping-me` / `!knock` were documented NOWHERE — not in
    `!help`, not in the channel guides. So the `community-pings` role had **zero
    members**, and every beacon and all six Community Hour rallies @-mentioned an
    empty role for a week. The feature worked and reached nobody.

    Steering §6 already required the `!help` entry to land in the same commit
    that flips a flag on. This is that entry, arriving late.
    """
    lines = []
    try:
        did = str(ctx.author.id)
        pings_on = database.is_feature_enabled("community_pings_optin", did)
        if pings_on:
            # Arabic aliases sit on their OWN lines, one LTR island each.
            # Putting an alias inline (`!ping-me` … (`!إشعارات-المجلس`)) puts two
            # `!` islands on one Arabic-containing line, which is exactly the
            # disorienting bidi pattern scripts/bidi_check.py rejects — verified
            # against it rather than assumed. See steering §6 (Sahin rule).
            lines.append(
                "`!ping-me` — get pinged when someone's in the lounge "
                "· run it again to turn pings off\n"
                "`!knock` — in the lounge and want company? ping the "
                "opted-in members\n"
                "`!إشعارات-المجلس`\n"
                "`!طق`\n")
        if database.is_feature_enabled("community_power_hour", did):
            cfg = community.get_config()
            # Only nudge toward `!ping-me` when that flag is actually on —
            # steering §6: never advertise a dormant command.
            nudge = (" Turn on `!ping-me` so you hear about it."
                     if pings_on else "")
            lines.append(
                f"🕘 **Community Hour** — every day at "
                f"{cfg.get('community_hour_start', '21:00')} "
                f"({cfg.get('community_hour_tz', 'Africa/Cairo')}) in "
                f"#community-live.{nudge}\n")
    except Exception:  # noqa: BLE001
        return ""
    if not lines:
        return ""
    return "**🏛️ The Majlis (voice lounge):**\n" + "".join(lines) + "\n"


@bot.command(name="help")
async def cmd_help(ctx, *, topic: str = ""):
    """Show commands, or deep-link to a guide section with `!help <topic>`.
    Role-aware: admins also see the Admin section."""
    topic = (topic or "").strip().lower()
    if topic:
        await _send_guide_topic(ctx, topic)
        return
    student_help = (
        "**🏛️ Empire English Bot — Commands**\n\n"
        "**📅 Your daily tasks:**\n"
        "The 5 core exercises (accent, vocabulary, shadowing, listening, "
        "speaking) are done on the **practice page** — open it with `!link`. "
        "They log **automatically** when you finish them.\n"
        "In Discord you log the 2 community tasks:\n"
        "✍️ `!6` — writing (write in #text-practice first, 20+ chars)\n"
        f"💬 `!7` — community (post in #general-chat + {_voice_requirement_text(ctx)})\n\n"
        "**Track your progress:**\n"
        "`!today` — what's left today\n"
        "`!progress` — your dashboard (level, week, streak, points, how to advance)\n"
        "`!link` — open your practice page\n"
        "`!top` — leaderboard\n"
        "`!week` · `!words` — this week's focus · your vocabulary\n"
        "`!guide` — open your full guide · `!help <topic>` — jump to a section (e.g. `!help streaks`)\n"
        "_(you'll get an honest weekly recap of your activity every Sunday)_\n\n"
        + _majlis_help_section(ctx) +
        "**Account:**\n"
        "`!join <goal>` — set your learning goal\n"
        "`!notifications` — notification settings\n"
        "`!delete` — request deletion of all your data\n"
        "`!resetme` — reset your learning history (with your consent)\n"
    )

    admin_help = (
        "\n**🔒 Admin (owner/staff only — use in #admin-commands):**\n"
        "`!status` — Bot status\n"
        "`!attention` — Ranked list of who needs a human right now (inactive, declining, buddy load)\n"
        "`!members` — List all members (with IDs)\n"
        "`!find <name>` — Find a student + their ID\n"
        "`!setlevel @user A1/A2/B1/B2/C1/C2` — Set someone's CEFR level\n"
        "`!announce <message>` — Broadcast announcement\n"
        "`!reset-student @user [reason]` — Reset a student's history (reversible)\n"
        "`!restore-student <record#>` — Undo a reset\n"
        "`!approve-reset <request#>` / `!deny-reset <request#>` — Decide a student's reset request\n"
        "`!orient <date/time>` — Send orientation invite\n"
        "`!recruit ar/en` — Get recruitment message template\n"
        "`!resources A1/A2/B1/B2/C1/C2` — Post shadowing resources\n"
        "`!flag list/enable/disable/beta` — Feature flag management\n"
        "`!maintenance start [soft|hard] [min] [reason]` — pause/warn + notify students\n"
        "`!maintenance end [what's new]` — back online + announce\n"
        "\n**Slash commands (native user picker, work from #admin-commands):**\n"
        "`/reset-student` · `/restore-student` · `/setlevel` · `/find`\n"
    )

    msg = student_help
    if _author_is_admin(ctx):
        msg += admin_help
    await ctx.send(msg)


@bot.command(name="placement")
async def cmd_placement(ctx, member: discord.Member = None):
    """Get your CEFR placement link (find your level). Admins may send it to
    someone else: `!placement @user`."""
    if member is not None and not ctx.author.guild_permissions.manage_guild:
        await ctx.send("Only admins can send a placement link to another member.")
        return
    target = member or ctx.author
    discord_id = str(target.id)
    if not database.get_member(discord_id):
        await ctx.send(("That user isn't a registered student yet." if member
                        else "You need to register first — type `!join`."))
        return
    code = database.create_claim_code(discord_id)
    if not code:
        await ctx.send("⏳ Too many link requests in the last hour — please wait a bit.")
        return
    base = config.PRACTICE_PLATFORM_URL
    try:
        await target.send(
            f"🧭 **اختبار تحديد المستوى (CEFR)**\n\n"
            f"الكود بتاعك (صالح ١٥ دقيقة، مرة واحدة بس):\n```\n{code}\n```\n"
            f"اضغط الرابط ده وابدأ على طول:\n{base}/placement/?code={code}\n\n"
            f"━━━━━━━━━━\n"
            f"🧭 **CEFR placement test** — a short adaptive check to find your level.\n"
            f"One-click start: {base}/placement/?code={code}\n"
            f"(Already logged in on this device? Just open {base}/placement/)"
        )
        await ctx.send("✅ Check your DMs! / شوف الرسائل الخاصة 📩")
    except Exception:
        await ctx.send("I couldn't DM you — please enable DMs from server members and retry.")


@bot.command(name="guide")
async def cmd_guide(ctx, *, topic: str = ""):
    """Open the student guide, optionally jumping to a section: `!guide [topic]`."""
    topic = (topic or "").strip().lower()
    anchor = _GUIDE_TOPICS.get(topic, "") if topic else ""
    await ctx.send(f"📗 دليلك الكامل: {_guide_link(anchor)}")


# Arabic alias for !guide
ARABIC_COMMAND_ALIASES["دليل"] = "guide"


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
        "**📅 مهامك اليومية:**\n"
        "التمارين الخمسة الأساسية (النطق، المفردات، المحاكاة، الاستماع، الكلام) "
        "بتعملها على **منصة التمرين** — افتحها بأمر `!link` — وبتتسجّل **تلقائيًا** "
        "أول ما تخلّصها.\n"
        "هنا في Discord بتسجّل مهمتين بس:\n"
        "`!6` — ✍️ الكتابة (اكتب في #text-practice الأول، ٢٠ حرف+)\n"
        "`!7` — 💬 المجتمع (اكتب في #general-chat أو ١٠ دقايق voice)\n\n"
        "**📊 تابع تقدمك:**\n"
        "`!اليوم` — اللي فاضل النهاردة\n"
        "`!تقدم` — لوحة تقدمك (مستواك، أسبوعك، سلسلتك، نقاطك)\n"
        "`!link` — افتح منصة التمرين\n"
        "`!ترتيب` — لوحة النقاط\n"
        "`!أسبوع` · `!كلماتي` — محتوى الأسبوع · مفرداتك\n"
        "_(هتوصلك خلاصة أسبوعية بنشاطك كل يوم أحد)_\n"
        "`!مساعدة` — الصفحة دي\n\n"
        "**⚡ طريقة الاستخدام:**\n"
        "1️⃣ التمارين الخمسة الأساسية → على منصة التمرين (`!link`) وبتتسجّل لوحدها\n"
        "2️⃣ الكتابة → اكتب في #text-practice وبعدين اكتب `!6`\n"
        "3️⃣ المجتمع → شارك في #general-chat أو voice وبعدين اكتب `!7`\n"
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

    if isinstance(message.channel, discord.DMChannel):
        # Bawaba B2: handle tutorial quest DM responses
        if features.has_pending_tutorial(str(message.author.id)):
            handled = await features.handle_tutorial_dm(message)
            if handled:
                return
        # Journey advancement: check if this DM advances the onboarding
        # journey. The rule-based onboarding journey is still active even
        # though the AI concierge has been removed — a non-command DM that
        # advances the journey gets the scripted next-step reply; anything
        # else simply falls through (no AI response).
        if not message.content.startswith(config.BOT_PREFIX):
            from . import nour_journey
            try:
                journey_reply = await nour_journey.try_message_triggered_advance(
                    str(message.author.id), message.content.strip()
                )
                if journey_reply:
                    # Journey advanced — send the scripted next-step message
                    async with message.channel.typing():
                        await asyncio.sleep(1.5)  # Human-like delay
                    await message.channel.send(journey_reply)
                    return
            except Exception as e:
                logger.error(f"Journey DM advance error: {e}")

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
                # Darb Phase 2: mastery for vocab quiz completion
                try:
                    from . import darb as darb_mod
                    wk_day = darb_mod.today_week_day(str(message.author.id))
                    if wk_day:
                        member_data = database.get_member(str(message.author.id))
                        level = (member_data.get("level", "A1") if member_data else "A1")
                        database.record_practice_mastery(
                            str(message.author.id), level, wk_day[0], wk_day[1], "vocab"
                        )
                except Exception:
                    pass
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
                # Darb Phase 2: mastery for listening quiz completion
                try:
                    from . import darb as darb_mod
                    wk_day = darb_mod.today_week_day(str(message.author.id))
                    if wk_day:
                        member_data = database.get_member(str(message.author.id))
                        level = (member_data.get("level", "A1") if member_data else "A1")
                        database.record_practice_mastery(
                            str(message.author.id), level, wk_day[0], wk_day[1], "listening"
                        )
                except Exception:
                    pass
                bar = "█" * result["tasks_today"] + "░" * (7 - result["tasks_today"])
                await message.channel.send(
                    f"✅ **صح!** أحسنت {message.author.mention}!\n\n"
                    f"[{bar}] {result['tasks_today']}/7 today\n"
                    f"🔥 Streak: **{result['streak']}** days | +{result['points']} points"
                )
            else:
                await message.channel.send(f"{message.author.mention} {error_msg}")
            return

    # Hafiz (Phase F, E4 -- owner feedback #7): AI motivational auto-reply
    # in #lN-text-practice + #lN-showcase. Deliberately narrow: pure
    # encouragement, never corrections (that's #writing-feedback's job via
    # ai_engine.evaluate_writing above, and the dedicated feedback
    # channel for speaking) -- so this must NOT fire for #writing-feedback
    # or command messages, only genuine student posts in those two
    # channels. Flag-gated (hafiz_motivation, default off).
    ch_name = getattr(message.channel, "name", None)
    if (
        database.is_feature_enabled("hafiz_motivation", str(message.author.id))
        and ch_name
        and not message.content.startswith(config.BOT_PREFIX)
        and (ch_name.endswith("-text-practice") or ch_name.endswith("-showcase"))
    ):
        from . import motivation
        post_type = "voice" if message.attachments else "text"
        try:
            reply = await motivation.maybe_reply(
                str(message.author.id), message.author.display_name,
                message.channel.id, post_type, message.content,
                bool(message.attachments),
            )
            if reply:
                await message.reply(reply, mention_author=False)
        except Exception as e:
            logger.error(f"Hafiz motivation reply error: {e}")

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


# ============================================================
#  STUDENT HISTORY RESET (governance) — Phase 2 commands
# ============================================================
# `!resetme` (student self-service, two-step authenticated consent),
# `!reset-student` (owner, on a student's request), `!restore-student` (undo).
# Every path records consent + a full snapshot via database.reset_member_history
# BEFORE anything is deleted, and pings the ops Telegram. Fully reversible.
RESET_CONSENT_TEXT = (
    "⚠️ **Reset your history — read carefully.**\n"
    "This permanently deletes your learning progress: points, streak, completed "
    "tasks, calendar progress, vocabulary review, and assessment scores. Your "
    "account stays active — you start fresh from today. **You cannot undo this "
    "yourself.** By confirming, you **request and authorize** Empire English to "
    "delete this data, and agree it was done at your request.\n"
    "Reply **`RESET`** to confirm, or **`CANCEL`** to stop.\n\n"
    "⚠️ **إعادة ضبط سجلّك — اقرأ بعناية.**\n"
    "ده هيمسح تقدّمك نهائيًا: النقاط، سلسلة الأيام، المهام المكتملة، تقدّم التقويم، "
    "مراجعة المفردات، ودرجات التقييم. حسابك هيفضل شغّال وتبدأ من جديد من النهارده. "
    "**مش هتقدر تتراجع بنفسك.** بتأكيدك، إنت بتطلب وبتصرّح لـ Empire English بمسح "
    "البيانات دي، وبتوافق إن ده تم بناءً على طلبك.\n"
    "اكتب **`RESET`** للتأكيد، أو **`CANCEL`** للإلغاء."
)


@bot.command(name="resetme")
async def cmd_resetme(ctx):
    """Student self-service: reset your OWN learning history (with consent)."""
    did = str(ctx.author.id)
    if not database.get_member(did):
        await ctx.send("You don't have any history yet — use `!join` to start. / لسه مبدأتش.")
        return
    await ctx.send(RESET_CONSENT_TEXT)

    def _check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

    try:
        reply = await bot.wait_for("message", check=_check, timeout=120)
    except asyncio.TimeoutError:
        await ctx.send("⌛ Timed out — nothing was changed. / خلص الوقت، مفيش حاجة اتغيّرت.")
        return

    if reply.content.strip().upper() != "RESET":
        await ctx.send("✅ Cancelled — your history is safe. / اتلغى، سجلك محفوظ.")
        return

    # Owner-approval gate: record the consented request as PENDING. NOTHING is
    # deleted until an admin approves (/approve or !approve-reset).
    m = database.get_member(did)
    rid = database.create_pending_reset(
        did, (m or {}).get("discord_name", ""), RESET_CONSENT_TEXT,
        reply.content.strip(), "student self-service (!resetme)",
    )
    await ctx.send(
        f"✅ Your reset request is recorded and **pending team approval** "
        f"(request #{rid}). We'll confirm here once it's reviewed — **nothing has "
        f"been deleted yet**.\n"
        f"طلبك اتسجّل و**في انتظار موافقة الفريق** (طلب #{rid}). هنأكدلك أول ما "
        f"يتراجع، ولسه **مفيش حاجة اتمسحت**."
    )
    try:
        await ops_hub.send_ops_alert(
            "Reset request — awaiting your approval",
            f"{(m or {}).get('discord_name', '?')} ({did}) requested a history reset "
            f"(request #{rid}).\n\nApprove:  /approve {rid}\nDeny:  /deny {rid}\n"
            f"(In Discord: !approve-reset {rid}  /  !deny-reset {rid})",
            severity="warning",
        )
    except Exception:
        pass


@bot.command(name="reset-student")
@commands.has_permissions(manage_guild=True)
async def cmd_reset_student(ctx, member: discord.Member = None, *, reason: str = ""):
    """(Admin) Reset a student's history on their request. Logs consent + snapshot."""
    if member is None:
        await ctx.send("Usage: `!reset-student @user [reason]`")
        return
    did = str(member.id)
    data = database.get_member(did)
    if not data:
        await ctx.send("That user isn't a registered student.")
        return
    result = database.reset_member_history(
        did, initiated_by=f"owner:{ctx.author.id}", consent_text=RESET_CONSENT_TEXT,
        affirmation="(owner-initiated on the student's request)",
        reason=reason or "(no reason given)",
    )
    rid = result["consent_id"]
    await ctx.send(
        f"✅ Reset **{member.display_name}**'s history (record #{rid}). "
        f"Reversible: `!restore-student {rid}`"
    )
    try:
        await ops_hub.send_ops_alert(
            "Student history reset (owner-initiated)",
            f"{ctx.author} reset {data.get('discord_name', '?')} ({did}). "
            f"Reason: {reason or '—'}. Consent record #{rid}. Reversible: !restore-student {rid}.",
            severity="warning",
        )
    except Exception:
        pass


@bot.command(name="restore-student")
@commands.has_permissions(manage_guild=True)
async def cmd_restore_student(ctx, consent_id: int = None):
    """(Admin) Undo a reset by restoring the snapshot from a consent record."""
    if consent_id is None:
        await ctx.send("Usage: `!restore-student <record_id>`")
        return
    restored = database.restore_member_from_consent(consent_id)
    if restored is None:
        await ctx.send(f"No consent record #{consent_id} found.")
        return
    summary = ", ".join(f"{k}={v}" for k, v in restored.items()) or "(nothing to restore)"
    await ctx.send(f"✅ Restored from record #{consent_id}: {summary}")
    try:
        await ops_hub.send_ops_alert(
            "Student history restored",
            f"{ctx.author} restored consent record #{consent_id}. Tables: {restored}",
            severity="info",
        )
    except Exception:
        pass


# ============================================================
#  ITQAN — owner report + overrides (Phase 7)
# ============================================================

def _itqan_report_chunks(text: str, limit: int = 1900):
    """Split a plain-text report into Discord-safe code-block chunks."""
    chunks, buf = [], ""
    for line in text.split("\n"):
        if len(buf) + len(line) + 1 > limit:
            chunks.append(f"```\n{buf}\n```")
            buf = ""
        buf += (line + "\n")
    if buf.strip():
        chunks.append(f"```\n{buf}\n```")
    return chunks or ["```\n(no data)\n```"]


@bot.command(name="itqan")
@commands.has_permissions(manage_guild=True)
async def cmd_itqan(ctx, level: str = None):
    """(Admin) Weekly-assessment report. Usage: !itqan [L0/L1/L2/L3]"""
    from . import assessment
    lvl = level.upper() if level else None
    if lvl and lvl not in config.CEFR_LEVELS:
        await ctx.send("Usage: `!itqan [A1/A2/B1/B2/C1/C2]`")
        return
    data = database.itqan_report_data(lvl)
    text = assessment.format_itqan_report(data)
    for chunk in _itqan_report_chunks(text):
        await ctx.send(chunk)


@bot.command(name="itqan-pass")
@commands.has_permissions(manage_guild=True)
async def cmd_itqan_pass(ctx, member: discord.Member = None, week: int = None):
    """(Admin) Manually mark a week mastered. Usage: !itqan-pass @user <week>"""
    if member is None or week is None:
        await ctx.send("Usage: `!itqan-pass @user <week>`")
        return
    data = database.get_member(str(member.id))
    if not data:
        await ctx.send("That user isn't a registered student.")
        return
    level = data.get("level", "A1")
    database.itqan_admin_pass(str(member.id), level, week)
    await ctx.send(f"✅ Marked **{member.display_name}** as mastered for **{level} Week {week}** "
                   f"— notifying + celebrating them now.")
    try:
        from . import itqan_outcomes
        await itqan_outcomes.deliver_manual_pass(str(member.id), level, week)
    except Exception:
        pass
    try:
        await ops_hub.send_ops_alert(
            "Itqan override: manual pass",
            f"{ctx.author} marked {data.get('discord_name', '?')} mastered for {level} Week {week}.",
            severity="info",
        )
    except Exception:
        pass


@bot.command(name="advance")
@commands.has_permissions(manage_guild=True)
async def cmd_advance(ctx, member: discord.Member = None):
    """(Admin) Manually promote a student to the next level.
    Usage: !advance @user — bypasses the advancement exam (owner override)."""
    if member is None:
        await ctx.send("Usage: `!advance @user`")
        return
    data = database.get_member(str(member.id))
    if not data:
        await ctx.send("That user isn't a registered student.")
        return
    level = data.get("level", "A1")
    next_level = config.next_cefr_level(level)
    if not next_level:
        await ctx.send(f"**{member.display_name}** is already at the highest level ({level}).")
        return
    database.set_level(str(member.id), next_level)
    await _assign_level_role(member, next_level)  # move them to the new CEFR role + zone
    await ctx.send(
        f"🎓 **{member.display_name}** manually promoted from **{level}** to **{next_level}**!\n"
        f"Calendar reset. They'll start {next_level} from Week 1."
    )
    try:
        await ops_hub.send_ops_alert(
            "Advancement: manual promotion",
            f"{ctx.author} promoted {data.get('discord_name', '?')} from {level} to {next_level} (override).",
            severity="info",
        )
    except Exception:
        pass


@bot.command(name="exam-review")
@commands.has_permissions(manage_guild=True)
async def cmd_exam_review(ctx, level: str = None):
    """(Admin) List CEFR exit exams awaiting human review — those that landed
    near a cut or where the AI rater was unsure. Usage: !exam-review [level]"""
    rows = database.exit_exam_pending_reviews(level)
    if not rows:
        await ctx.send("✅ No exit exams awaiting review.")
        return
    lines = ["📋 **Exit exams awaiting review:**"]
    for r in rows:
        name = (database.get_member(str(r["discord_id"])) or {}).get(
            "discord_name", r["discord_id"])
        lines.append(
            f"`#{r['id']}` **{name}** — {r['level']} · A {r['part_a_pct']}% · "
            f"B {r['part_b_total']}/100 · conf {r['ai_confidence']} ({r['rater']})\n"
            f"     {'; '.join(r.get('reasons', [])) or '—'}"
        )
    lines.append("\nResolve with `!exam-pass <id>` or `!exam-fail <id>`.")
    await ctx.send("\n".join(lines)[:1900])


@bot.command(name="exam-pass")
@commands.has_permissions(manage_guild=True)
async def cmd_exam_pass(ctx, review_id: int = None):
    """(Admin) Resolve a reviewed exit exam as PASS → promote + certificate.
    Usage: !exam-pass <review_id> (see !exam-review)"""
    if review_id is None:
        await ctx.send("Usage: `!exam-pass <review_id>` — see `!exam-review`")
        return
    row = database.exit_exam_resolve_review(review_id, "passed", str(ctx.author))
    if not row:
        await ctx.send(f"No pending review `#{review_id}`.")
        return
    from . import advancement_outcomes
    await advancement_outcomes.promote_from_review(row)
    name = (database.get_member(str(row["discord_id"])) or {}).get(
        "discord_name", row["discord_id"])
    await ctx.send(f"🎓 Review `#{review_id}` — **{name}** passed **{row['level']}**. "
                   f"Promoting + issuing certificate now.")


@bot.command(name="exam-fail")
@commands.has_permissions(manage_guild=True)
async def cmd_exam_fail(ctx, review_id: int = None):
    """(Admin) Resolve a reviewed exit exam as NOT-PASS → retake DM.
    Usage: !exam-fail <review_id> (see !exam-review)"""
    if review_id is None:
        await ctx.send("Usage: `!exam-fail <review_id>` — see `!exam-review`")
        return
    row = database.exit_exam_resolve_review(review_id, "failed", str(ctx.author))
    if not row:
        await ctx.send(f"No pending review `#{review_id}`.")
        return
    from . import advancement_outcomes
    await advancement_outcomes.fail_from_review(row)
    name = (database.get_member(str(row["discord_id"])) or {}).get(
        "discord_name", row["discord_id"])
    await ctx.send(f"📊 Review `#{review_id}` — **{name}** ({row['level']}) "
                   f"marked not-pass. Retake DM sent.")


@bot.command(name="purge-legacy-zones")
@commands.has_permissions(manage_guild=True)
async def cmd_purge_legacy_zones(ctx, confirm: str = None):
    """(Admin) Permanently DELETE the archived legacy **Level 1/2/3** zones +
    their l1–l3 channels. **Level 0 is KEPT (archived)** as a fallback.
    Preview: `!purge-legacy-zones`  ·  Delete: `!purge-legacy-zones confirm`"""
    import re as _re
    guild = ctx.guild
    if not guild:
        await ctx.send("Run this in the server.")
        return
    # Target Levels 1–3 only. Level 0 (l0-* channels + its archived category) is
    # deliberately preserved per owner decision (keep as a just-in-case archive).
    legacy_re = _re.compile(r"^l[1-3](-|$)", _re.I)

    def _is_target_category(name: str) -> bool:
        if not name.startswith("📦 Archive"):
            return False  # only archived categories
        keep = ("LEVEL 0" in name.upper()) or ("المستوى 0" in name)  # keep L0
        hits_123 = any(k in name.upper() for k in ("LEVEL 1", "LEVEL 2", "LEVEL 3")) \
            or any(k in name for k in ("المستوى 1", "المستوى 2", "المستوى 3"))
        return hits_123 and not keep

    archive_cats = [c for c in guild.categories if _is_target_category(c.name)]
    archived_children = [ch for c in archive_cats for ch in c.channels]
    legacy_named = [ch for ch in guild.channels
                    if getattr(ch, "name", "") and legacy_re.match(ch.name)]
    to_delete = list({ch.id: ch for ch in (archived_children + legacy_named)}.values())

    if not archive_cats and not to_delete:
        await ctx.send("✅ No Level 1/2/3 legacy zones found. (Level 0 archive, if any, is kept.)")
        return

    if confirm != "confirm":
        lines = [f"   • #{getattr(ch, 'name', '?')}" for ch in to_delete[:25]]
        more = f"\n   … +{len(to_delete) - 25} more" if len(to_delete) > 25 else ""
        await ctx.send(
            (f"🧹 **Legacy purge — PREVIEW** (nothing deleted yet)\n"
             f"Deleting **Level 1/2/3** — Level 0 archive is KEPT.\n"
             f"Archived categories: **{len(archive_cats)}** · channels: **{len(to_delete)}**\n"
             + "\n".join(lines) + more +
             f"\n\n⚠️ Run `!purge-legacy-zones confirm` to DELETE these permanently.")[:1900])
        return

    deleted_ch = deleted_cat = 0
    for ch in to_delete:
        try:
            await ch.delete(reason="Legacy L1–L3 retirement — purge (L0 kept)")
            deleted_ch += 1
        except Exception:
            pass
    for cat in archive_cats:
        try:
            await cat.delete(reason="Legacy L1–L3 retirement — purge (L0 kept)")
            deleted_cat += 1
        except Exception:
            pass
    await ctx.send(f"🧹 Purged **Level 1/2/3**: deleted **{deleted_ch}** channel(s) + "
                   f"**{deleted_cat}** archived categor(y/ies). Level 0 archive kept. ✅")
    try:
        await ops_hub.send_ops_alert(
            "Legacy zones purged (L1–L3)",
            f"{ctx.author} deleted {deleted_ch} L1–L3 channels + {deleted_cat} archived "
            f"categories. Level 0 archive preserved.", severity="info")
    except Exception:
        pass


@bot.command(name="organize-server")
@commands.has_permissions(manage_guild=True)
async def cmd_organize_server(ctx, confirm: str = None):
    """(Admin) Reorder every category + channel into a clean, professional
    layout (Welcome → System → your Level zones → Community → Accountability →
    Resources → Feedback → Admin → Ghost → Archive; voice channels last in each
    category; level zones get daily-tasks → text-practice → questions → showcase).
    Preview: `!organize-server`  ·  Apply: `!organize-server confirm`"""
    guild = ctx.guild
    if not guild:
        await ctx.send("Run this in the server.")
        return

    def _cat_rank(cat):
        raw = cat.name
        n = raw.upper()
        if raw.startswith("📦") or "ARCHIVE" in n:
            return 90                                  # archived → very bottom
        if "GHOST" in n:
            return 80
        if "ADMIN" in n or "الإدارة" in raw:
            return 70
        if "FEEDBACK" in n or "التقييم" in raw:
            return 62
        if "RESOURCES" in n or "المصادر" in raw:
            return 60
        if "ACCOUNTABILITY" in n or "المتابعة" in raw:
            return 58
        if "COMMUNITY" in n or "المجتمع" in raw:
            return 56
        for i, lvl in enumerate(config.CEFR_ORDER):     # A1..C2 zones grouped
            if f"{lvl} ZONE" in n:
                return 30 + i
        if "SYSTEM" in n or "الأوامر" in raw:
            return 20
        if "WELCOME" in n or "أهل" in raw:
            return 10
        return 57                                      # unknown shared → near community

    _ZONE_ORDER = ("daily-tasks", "text-practice", "questions", "showcase")

    def _chan_key(ch):
        name = ch.name.lower()
        is_voice = isinstance(ch, discord.VoiceChannel)
        for i, suf in enumerate(_ZONE_ORDER):
            if name.endswith(suf):
                return (0, i, ch.position)             # canonical zone order first
        if is_voice:
            return (2, 0, ch.position)                 # voice channels last
        return (1, ch.position, 0)                     # other text: keep current order

    ordered_cats = sorted(guild.categories, key=lambda c: (_cat_rank(c), c.name))

    # Floating (uncategorized) channels: owner/system ones (teacher-feed, logs,
    # dev, mod, admin, nutq) get tucked into the Admin category (owner-only, and
    # synced perms make them owner-only too — important for the private
    # nutq-teacher-feed). Any other orphan is reported but left where it is.
    import re as _re
    admin_cat = next((c for c in ordered_cats
                      if "ADMIN" in c.name.upper() or "الإدارة" in c.name), None)
    _admin_orphan_re = _re.compile(r"teacher-feed|nutq|-log$|^dev-|^bot-log|^mod-|admin|ops",
                                   _re.I)
    orphans = [ch for ch in guild.channels
               if not isinstance(ch, discord.CategoryChannel) and ch.category is None]
    orphans_to_admin = [ch for ch in orphans if admin_cat and _admin_orphan_re.search(ch.name or "")]
    orphans_other = [ch for ch in orphans if ch not in orphans_to_admin]

    if confirm != "confirm":
        lines = ["🗂️ **Proposed professional layout** (preview — nothing moved yet):", ""]
        for i, cat in enumerate(ordered_cats, 1):
            lines.append(f"**{i}. {cat.name}**")
            for ch in sorted(cat.channels, key=_chan_key):
                icon = "🔊 " if isinstance(ch, discord.VoiceChannel) else "#"
                lines.append(f"    {icon}{ch.name}")
        if orphans_to_admin:
            lines.append(f"\n🧩 **Floating → moved into {admin_cat.name}** (owner-only):")
            lines += [f"    #{ch.name}" for ch in orphans_to_admin]
        if orphans_other:
            lines.append("\n🧩 **Floating (left as-is — tell me where they belong):**")
            lines += [f"    #{ch.name}" for ch in orphans_other]
        lines.append("\n✅ Run `!organize-server confirm` to apply (may take ~a minute).")
        buf = ""
        for ln in lines:
            if len(buf) + len(ln) + 1 > 1900:
                await ctx.send(buf)
                buf = ln
            else:
                buf += ("\n" + ln) if buf else ln
        if buf:
            await ctx.send(buf)
        return

    await ctx.send("🗂️ Organizing… (repositioning categories + channels, ~a minute)")
    moved_cat = moved_ch = adopted = 0
    errors = []
    # 1. Tuck floating owner/system channels into Admin (sync its owner-only perms).
    for ch in orphans_to_admin:
        try:
            await ch.edit(category=admin_cat, sync_permissions=True,
                          reason="organize-server: file uncategorized owner channel under Admin")
            adopted += 1
        except Exception as e:
            errors.append(f"#{ch.name}→Admin: {e}")
    # 2. Category order.
    for pos, cat in enumerate(ordered_cats):
        try:
            await cat.edit(position=pos)
            moved_cat += 1
        except Exception as e:
            errors.append(f"category {cat.name}: {e}")
    # Text and voice channels keep SEPARATE position sequences within a
    # category — reorder each type independently or Discord ignores the move.
    for cat in ordered_cats:
        texts = [c for c in cat.channels if not isinstance(c, discord.VoiceChannel)]
        voices = [c for c in cat.channels if isinstance(c, discord.VoiceChannel)]
        for group in (texts, voices):
            for cpos, ch in enumerate(sorted(group, key=_chan_key)):
                try:
                    await ch.edit(position=cpos)
                    moved_ch += 1
                except Exception as e:
                    errors.append(f"#{ch.name}: {e}")
    out = (f"🗂️ **Organized** — repositioned **{moved_cat}** categories + "
           f"**{moved_ch}** channels"
           + (f", filed **{adopted}** floating channel(s) under Admin" if adopted else "")
           + " into the professional layout. ✅")
    if orphans_other:
        out += f"\n🧩 Still uncategorized (tell me where to put them): " + \
               ", ".join(f"#{ch.name}" for ch in orphans_other[:8])
    if errors:
        out += (f"\n⚠️ {len(errors)} item(s) couldn't move — first: `{errors[0][:150]}`"
                f"\n(Discord may need a moment / permission check — re-run if needed.)")
    await ctx.send(out[:1950])
    try:
        await ops_hub.send_ops_alert(
            "Server reorganized",
            f"{ctx.author} ran !organize-server ({moved_cat} categories, {moved_ch} channels).",
            severity="info")
    except Exception:
        pass


@bot.command(name="itqan-reset")
@commands.has_permissions(manage_guild=True)
async def cmd_itqan_reset(ctx, member: discord.Member = None, week: int = None):
    """(Admin) Clear a student's attempts for a week so they can retry.
    Usage: !itqan-reset @user <week>"""
    if member is None or week is None:
        await ctx.send("Usage: `!itqan-reset @user <week>`")
        return
    data = database.get_member(str(member.id))
    if not data:
        await ctx.send("That user isn't a registered student.")
        return
    level = data.get("level", "A1")
    r = database.itqan_reset(str(member.id), level, week)
    await ctx.send(
        f"♻️ Reset **{member.display_name}**'s {level} Week {week} assessment — "
        f"{r['attempts_deleted']} attempt(s) cleared. They can retake it.")


async def _build_itqan_review(attempt_id: int):
    """Shared builder for the review coaching-brief + audio files. Returns
    {chunks:[str], files:[discord.File], n:int} or None if the attempt is gone."""
    from . import assessment
    import io
    att = database.itqan_get_attempt(attempt_id)
    if not att:
        return None
    items = database.itqan_get_items(attempt_id)
    recs = database.itqan_get_recordings(attempt_id)
    member = database.get_member(att["discord_id"]) or {}
    name = (member.get("discord_name") or str(att["discord_id"])).split("#")[0]
    note = await assessment.build_coaching_note(att, items)   # AI paragraph (or '')
    text = assessment.format_attempt_review(
        att, items, name=name, rec_item_nos=[r["item_no"] for r in recs], coaching_note=note)
    files = [discord.File(io.BytesIO(r["audio"]),
                          filename=f"item{r['item_no']}_{r['skill']}_{r['filename']}")
             for r in recs[:10]]
    return {"chunks": _itqan_report_chunks(text), "files": files, "n": len(recs)}


@bot.command(name="itqan-review")
@commands.has_permissions(manage_guild=True)
async def cmd_itqan_review(ctx, attempt_id: int = None):
    """(Admin) Coaching brief for one attempt + its audio recordings.
    Usage: !itqan-review <attempt_id>  (the id is in the flag alert).
    Tip: from #admin-commands, /itqan-review lets you pick the student by name."""
    if attempt_id is None:
        await ctx.send("Usage: `!itqan-review <attempt_id>`  ·  or use `/itqan-review` to pick a student.")
        return
    rev = await _build_itqan_review(attempt_id)
    if rev is None:
        await ctx.send(f"No attempt #{attempt_id}.")
        return
    for chunk in rev["chunks"]:
        await ctx.send(chunk)
    if rev["files"]:
        await ctx.send(f"🎧 {rev['n']} recording(s) — listen to judge:", files=rev["files"])
    else:
        await ctx.send("🎧 No recordings retained (text-only items, or past the 14-day window).")


@bot.command(name="itqan-due")
@commands.has_permissions(manage_guild=True)
async def cmd_itqan_due(ctx, level: str = None):
    """(Admin) Full weekly-assessment status — who has a due test.
    Usage: !itqan-due [L0/L1/L2/L3]"""
    from . import assessment
    lvl = level.upper() if level else None
    if lvl and lvl not in config.CEFR_LEVELS:
        await ctx.send("Usage: `!itqan-due [A1/A2/B1/B2/C1/C2]`")
        return
    data = database.itqan_status_report(lvl)
    for chunk in _itqan_report_chunks(assessment.format_itqan_due(data)):
        await ctx.send(chunk)


# ============================================================
#  ADMIN SLASH COMMANDS (native user picker; auto-hidden from
#  non-admins)
# ============================================================
# These mirror the !reset-student / !restore-student / !setlevel / !find
# prefix commands (which stay as fallbacks). The reason they exist:
# Discord's plain @-mention typeahead only lists members who can SEE the
# current channel, so from the private #admin-commands channel students
# never appear. A slash command's USER option instead searches the WHOLE
# guild (via the members intent), so students are selectable from anywhere.
# `default_permissions(manage_guild=True)` also makes Discord auto-hide
# these from students in the UI, and an explicit check enforces it server-
# side. All replies are ephemeral (only the admin who ran it sees them).

def _search_registered_students(guild, query: str):
    """Return up to 15 (discord_id, member_row, server_nick_or_None) tuples
    for registered students whose registered name / server nickname / id
    matches `query` (case-insensitive, partial). Shared search used by /find."""
    q = (query or "").strip().casefold()
    members = database.all_active_members()
    by_id = {str(m["discord_id"]): m for m in members}
    out = {}
    for m in members:
        if q in (m.get("discord_name") or "").casefold():
            out[str(m["discord_id"])] = (m, None)
    if guild:
        for gm in guild.members:
            if gm.bot:
                continue
            did = str(gm.id)
            if did in by_id and q in f"{gm.display_name} {gm.name}".casefold():
                out.setdefault(did, (by_id[did], gm.display_name))
    if query and query.strip().isdigit() and query.strip() in by_id:
        out.setdefault(query.strip(), (by_id[query.strip()], None))
    return list(out.items())[:15], len(out)


_LEVEL_CHOICES = [
    app_commands.Choice(name=f"{k} — {v.get('title', v.get('name', k))}", value=k)
    for k, v in config.CEFR_LEVELS.items()
]


async def _student_autocomplete(interaction: discord.Interaction, current: str):
    """Bot-supplied student list for slash `student` options.

    Discord's native user-picker is scoped to members who can VIEW the current
    channel, so from the private #admin-commands channel students never show.
    Autocomplete choices are supplied by the BOT instead, so every registered
    student always appears regardless of channel visibility.
    """
    cur = (current or "").strip().casefold()
    out = []
    for m in database.all_active_members():
        name = m.get("discord_name") or "(unknown)"
        did = str(m["discord_id"])
        if cur and cur not in name.casefold() and cur not in did:
            continue
        label = f"{name} — {m.get('level', '?')}"
        out.append(app_commands.Choice(name=label[:100], value=did))
        if len(out) >= 25:
            break
    return out


async def _resolve_student_arg(interaction: discord.Interaction, value: str):
    """Turn a slash `student` value (a discord_id from autocomplete, or a
    free-typed name) into (discord_id, member_or_None, db_row_or_None)."""
    v = (value or "").strip()
    if v.isdigit():
        did = v
    else:
        rows, total = _search_registered_students(interaction.guild, v)
        if total != 1:
            return None, None, None
        did = rows[0][0]
    row = database.get_member(did)
    member = None
    if interaction.guild and did.isdigit():
        member = interaction.guild.get_member(int(did))
        if member is None:
            try:
                member = await interaction.guild.fetch_member(int(did))
            except Exception:
                member = None
    return did, member, row


@bot.tree.command(name="reset-student",
                  description="Reset a student's learning history (records consent + snapshot; reversible).")
@app_commands.describe(student="Start typing a student's name, then pick them from the list",
                       reason="Why — optional, logged with the consent record")
@app_commands.autocomplete(student=_student_autocomplete)
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.guild_only()
async def slash_reset_student(interaction: discord.Interaction,
                              student: str, reason: str = ""):
    await interaction.response.defer(ephemeral=True)
    did, member, data = await _resolve_student_arg(interaction, student)
    if not data:
        await interaction.followup.send(
            "Couldn't identify that student. Start typing the name and **pick from the list**.",
            ephemeral=True)
        return
    result = database.reset_member_history(
        did, initiated_by=f"owner:{interaction.user.id}", consent_text=RESET_CONSENT_TEXT,
        affirmation="(owner-initiated on the student's request)",
        reason=reason or "(no reason given)",
    )
    rid = result["consent_id"]
    name = member.display_name if member else data.get("discord_name", did)
    await interaction.followup.send(
        f"✅ Reset **{name}**'s history (record #{rid}).\n"
        f"Undo: `/restore-student record_id:{rid}` (or `!restore-student {rid}`)",
        ephemeral=True,
    )
    try:
        await ops_hub.send_ops_alert(
            "Student history reset (owner-initiated, via /reset-student)",
            f"{interaction.user} reset {data.get('discord_name', '?')} ({did}). "
            f"Reason: {reason or '—'}. Consent record #{rid}. Reversible: !restore-student {rid}.",
            severity="warning",
        )
    except Exception:
        pass


@bot.tree.command(name="restore-student",
                  description="Undo a reset by restoring the snapshot from a consent record number.")
@app_commands.describe(record_id="The record # shown when the reset was done")
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.guild_only()
async def slash_restore_student(interaction: discord.Interaction, record_id: int):
    await interaction.response.defer(ephemeral=True)
    restored = database.restore_member_from_consent(record_id)
    if restored is None:
        await interaction.followup.send(f"No consent record #{record_id} found.", ephemeral=True)
        return
    summary = ", ".join(f"{k}={v}" for k, v in restored.items()) or "(nothing to restore)"
    await interaction.followup.send(f"✅ Restored from record #{record_id}: {summary}", ephemeral=True)
    try:
        await ops_hub.send_ops_alert(
            "Student history restored (via /restore-student)",
            f"{interaction.user} restored consent record #{record_id}. Tables: {restored}",
            severity="info",
        )
    except Exception:
        pass


@bot.tree.command(name="setlevel", description="Set a student's level (A1–C2).")
@app_commands.describe(student="Start typing a student's name, then pick them", level="New level")
@app_commands.autocomplete(student=_student_autocomplete)
@app_commands.choices(level=_LEVEL_CHOICES)
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.guild_only()
async def slash_setlevel(interaction: discord.Interaction,
                         student: str, level: app_commands.Choice[str]):
    await interaction.response.defer(ephemeral=True)
    lvl = level.value
    if lvl not in config.CEFR_LEVELS:
        await interaction.followup.send("❌ Invalid level.", ephemeral=True)
        return
    did, member, data = await _resolve_student_arg(interaction, student)
    if not data:
        await interaction.followup.send(
            "Couldn't identify that student. Start typing the name and **pick from the list**.",
            ephemeral=True)
        return
    database.set_level(did, lvl)
    role_note = ""
    if member:
        await _assign_level_role(member, lvl)
    else:
        role_note = " _(level saved; Discord role not updated — member not reachable)_"
    li = config.level_info(lvl)
    name = member.display_name if member else data.get("discord_name", did)
    await interaction.followup.send(
        f"✅ {name} is now **{lvl}** — {li['emoji']} {li['name']}{role_note}", ephemeral=True)


@bot.tree.command(name="find", description="Find registered students by name and show their IDs.")
@app_commands.describe(query="Part of a name (or a user ID)")
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.guild_only()
async def slash_find(interaction: discord.Interaction, query: str):
    await interaction.response.defer(ephemeral=True)
    rows, total = _search_registered_students(interaction.guild, query)
    if not rows:
        await interaction.followup.send(
            f"🔍 No registered student matches **{query}**.", ephemeral=True)
        return
    lines = [f"**🔍 {total} match(es) for “{query}”:**\n"]
    for did, (m, nick) in rows:
        lvl = config.level_info(m["level"])
        name = m.get("discord_name") or "(unknown)"
        nick_str = f" _(server name: {nick})_" if nick and nick != name else ""
        lines.append(
            f"{lvl['emoji']} **{name}**{nick_str} — {m['level']} | {m['total_points']} pts\n"
            f"   🆔 `{did}`"
        )
    if total > len(rows):
        lines.append(f"\n... and {total - len(rows)} more — narrow your search.")
    await interaction.followup.send("\n".join(lines), ephemeral=True)


# ── /nutq — pronunciation feature controls (slash; ! prefix is disabled in
#    the admin channel, so these are slash subcommands) ──────────────────────
_NUTQ_FLAG = "tatawwur_pronunciation"

nutq_group = app_commands.Group(
    name="nutq",
    description="Pronunciation feature — who gets it + how many official grades/day.",
    default_permissions=discord.Permissions(manage_guild=True),
    guild_only=True,
)


@nutq_group.command(name="status",
                    description="Who has the pronunciation feature + their daily-grade caps.")
@app_commands.checks.has_permissions(manage_guild=True)
async def nutq_status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    st = database.feature_flag_status(_NUTQ_FLAG)
    default_cap = config.NUTQ_AZURE_MAX_CALLS_PER_DAY
    if not st["enabled"]:
        head = "🔴 OFF for everyone"
    elif st["everyone"]:
        head = "🟢 ON for EVERYONE"
    else:
        head = f"🟢 ON for {len(st['allowed_ids'])} student(s)"
    lines = [f"**🗣️ Nutq pronunciation** — {head}", ""]
    if st["enabled"] and not st["everyone"]:
        for did in sorted(st["allowed_ids"]):
            row = database.get_member(did)
            nm = (row.get("discord_name") if row else did) or did
            cap = database.nutq_daily_cap_override(did)
            cap_txt = f"{cap}/day" if cap is not None else f"{default_cap}/day (default)"
            lines.append(f"• {nm} — {cap_txt}")
        lines.append("")
    lines.append(f"Default cap: **{default_cap}**/day")
    lines.append("Manage: `/nutq grant` · `revoke` · `everyone` · `off` · `cap` · `capreset`")
    await interaction.followup.send("\n".join(lines), ephemeral=True)


async def _nutq_pick(interaction: discord.Interaction, student: str):
    """Resolve + report failure. Returns (did, name) or (None, None)."""
    did, member, data = await _resolve_student_arg(interaction, student)
    if not data and not (did and str(did).isdigit()):
        await interaction.followup.send(
            "Couldn't identify that student. Start typing the name and **pick from the list**.",
            ephemeral=True)
        return None, None
    name = (member.display_name if member else (data or {}).get("discord_name", did)) or did
    return did, name


@nutq_group.command(name="grant", description="Give a student the pronunciation feature.")
@app_commands.describe(student="Start typing a student's name, then pick them")
@app_commands.autocomplete(student=_student_autocomplete)
@app_commands.checks.has_permissions(manage_guild=True)
async def nutq_grant(interaction: discord.Interaction, student: str):
    await interaction.response.defer(ephemeral=True)
    did, name = await _nutq_pick(interaction, student)
    if not did:
        return
    r = database.feature_flag_grant(_NUTQ_FLAG, did, updated_by=f"discord:{interaction.user.id}")
    msg = {
        "everyone": f"ℹ️ It's already ON for everyone — **{name}** already has it.",
        "already": f"✅ **{name}** already has it.",
        "granted": f"🟢 Granted the pronunciation feature to **{name}**.",
    }[r]
    await interaction.followup.send(msg, ephemeral=True)


@nutq_group.command(name="revoke", description="Remove a student's access to the pronunciation feature.")
@app_commands.describe(student="Start typing a student's name, then pick them")
@app_commands.autocomplete(student=_student_autocomplete)
@app_commands.checks.has_permissions(manage_guild=True)
async def nutq_revoke(interaction: discord.Interaction, student: str):
    await interaction.response.defer(ephemeral=True)
    did, name = await _nutq_pick(interaction, student)
    if not did:
        return
    r = database.feature_flag_revoke(_NUTQ_FLAG, did, updated_by=f"discord:{interaction.user.id}")
    msg = {
        "everyone": ("⚠️ It's ON for **everyone** right now, so I can't remove just one. "
                     "Use `/nutq off`, or grant specific students to switch to an allowlist."),
        "not_present": f"ℹ️ **{name}** wasn't on the list.",
        "revoked": f"🟠 Removed **{name}** from the pronunciation feature.",
        "revoked_now_off": f"🔴 Removed **{name}** — the last student, so the feature is now **OFF**.",
    }[r]
    await interaction.followup.send(msg, ephemeral=True)


@nutq_group.command(name="everyone", description="Turn the pronunciation feature ON for ALL students.")
@app_commands.checks.has_permissions(manage_guild=True)
async def nutq_everyone(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    database.set_feature_flag(_NUTQ_FLAG, enabled=True, allowed_ids="",
                              updated_by=f"discord:{interaction.user.id}")
    await interaction.followup.send("🟢 Pronunciation feature is now **ON for everyone**.", ephemeral=True)


@nutq_group.command(name="off", description="Turn the pronunciation feature OFF for everyone.")
@app_commands.checks.has_permissions(manage_guild=True)
async def nutq_off(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    database.set_feature_flag(_NUTQ_FLAG, enabled=False, updated_by=f"discord:{interaction.user.id}")
    await interaction.followup.send("🔴 Pronunciation feature is now **OFF** for everyone.", ephemeral=True)


@nutq_group.command(name="cap", description="Set a student's official grades per day.")
@app_commands.describe(student="Start typing a student's name, then pick them",
                       grades="Official Azure grades per day (0–20)")
@app_commands.autocomplete(student=_student_autocomplete)
@app_commands.checks.has_permissions(manage_guild=True)
async def nutq_cap(interaction: discord.Interaction, student: str,
                   grades: app_commands.Range[int, 0, 20]):
    await interaction.response.defer(ephemeral=True)
    did, name = await _nutq_pick(interaction, student)
    if not did:
        return
    database.set_nutq_daily_cap_override(did, int(grades))
    await interaction.followup.send(
        f"✅ **{name}** can now earn **{int(grades)}** official grade(s)/day.", ephemeral=True)


@nutq_group.command(name="capreset", description="Revert a student to the default daily grade cap.")
@app_commands.describe(student="Start typing a student's name, then pick them")
@app_commands.autocomplete(student=_student_autocomplete)
@app_commands.checks.has_permissions(manage_guild=True)
async def nutq_capreset(interaction: discord.Interaction, student: str):
    await interaction.response.defer(ephemeral=True)
    did, name = await _nutq_pick(interaction, student)
    if not did:
        return
    database.clear_nutq_daily_cap_override(did)
    await interaction.followup.send(
        f"✅ **{name}** now uses the default **{config.NUTQ_AZURE_MAX_CALLS_PER_DAY}**/day.",
        ephemeral=True)


bot.tree.add_command(nutq_group)


@bot.tree.command(name="itqan-review",
                  description="Coaching brief + recordings for a student's weekly assessment.")
@app_commands.describe(student="Start typing a student's name, then pick them",
                       week="Which week (optional — defaults to their latest attempt)")
@app_commands.autocomplete(student=_student_autocomplete)
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.guild_only()
async def slash_itqan_review(interaction: discord.Interaction, student: str, week: int = None):
    await interaction.response.defer(ephemeral=True)
    did, member, data = await _resolve_student_arg(interaction, student)
    if not data:
        await interaction.followup.send(
            "Couldn't identify that student. Start typing the name and **pick from the list**.",
            ephemeral=True)
        return
    level = data.get("level", "A1")
    aid = database.itqan_latest_attempt_id(did, level, week)
    if not aid:
        await interaction.followup.send(
            f"No finished assessment for **{data.get('discord_name', did)}**"
            f"{f' in Week {week}' if week else ''} yet.", ephemeral=True)
        return
    rev = await _build_itqan_review(aid)
    if rev is None:
        await interaction.followup.send("Couldn't load that attempt.", ephemeral=True)
        return
    for chunk in rev["chunks"]:
        await interaction.followup.send(chunk, ephemeral=True)
    if rev["files"]:
        await interaction.followup.send(f"🎧 {rev['n']} recording(s) — listen to judge:",
                                        files=rev["files"], ephemeral=True)
    else:
        await interaction.followup.send(
            "🎧 No recordings retained (text-only items, or past the 14-day window).",
            ephemeral=True)


@bot.tree.command(name="itqan-pass",
                  description="Mark a student's week as mastered (resolves a flagged/near-miss attempt).")
@app_commands.describe(student="Start typing a student's name, then pick them", week="Which week")
@app_commands.autocomplete(student=_student_autocomplete)
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.guild_only()
async def slash_itqan_pass(interaction: discord.Interaction, student: str, week: int):
    await interaction.response.defer(ephemeral=True)
    did, member, data = await _resolve_student_arg(interaction, student)
    if not data:
        await interaction.followup.send(
            "Couldn't identify that student. Pick from the list.", ephemeral=True)
        return
    level = data.get("level", "A1")
    database.itqan_admin_pass(did, level, week)
    name = member.display_name if member else data.get("discord_name", did)
    try:
        from . import itqan_outcomes
        await itqan_outcomes.deliver_manual_pass(did, level, week)
    except Exception:
        pass
    await interaction.followup.send(
        f"✅ Marked **{name}** as mastered for **{level} Week {week}** — "
        f"the student has been notified + celebrated.", ephemeral=True)
    try:
        await ops_hub.send_ops_alert(
            "Itqan override: manual pass",
            f"{interaction.user} marked {data.get('discord_name', '?')} mastered for {level} Week {week}.",
            severity="info")
    except Exception:
        pass


@bot.tree.command(name="itqan-reset",
                  description="Clear a student's attempts for a week so they can retake.")
@app_commands.describe(student="Start typing a student's name, then pick them", week="Which week")
@app_commands.autocomplete(student=_student_autocomplete)
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.guild_only()
async def slash_itqan_reset(interaction: discord.Interaction, student: str, week: int):
    await interaction.response.defer(ephemeral=True)
    did, member, data = await _resolve_student_arg(interaction, student)
    if not data:
        await interaction.followup.send(
            "Couldn't identify that student. Pick from the list.", ephemeral=True)
        return
    level = data.get("level", "A1")
    r = database.itqan_reset(did, level, week)
    name = member.display_name if member else data.get("discord_name", did)
    await interaction.followup.send(
        f"♻️ Reset **{name}**'s {level} Week {week} assessment — "
        f"{r['attempts_deleted']} attempt(s) cleared. They can retake it.", ephemeral=True)


@bot.tree.command(name="itqan-due",
                  description="Weekly-assessment status for all students (who has a due test).")
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.guild_only()
async def slash_itqan_due(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    from . import assessment
    data = database.itqan_status_report(None)
    for chunk in _itqan_report_chunks(assessment.format_itqan_due(data)):
        await interaction.followup.send(chunk, ephemeral=True)


@bot.tree.command(name="majlis",
                  description="Community Lounge (Majlis) — live status + config.")
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.guild_only()
async def slash_majlis(interaction: discord.Interaction):
    """Show Majlis flag states, config, and live lounge occupancy."""
    await interaction.response.defer(ephemeral=True)

    # Flag states
    flags = [
        "community_together_credit",
        "community_lounge_beacon",
        "community_dynamic_rooms",
        "community_pings_optin",
        "community_power_hour",
        "community_together_reward",
    ]
    flag_lines = []
    for f in flags:
        st = database.feature_flag_status(f)
        icon = "✅" if st["enabled"] else "❌"
        scope = "everyone" if st["everyone"] else (f"{len(st['allowed_ids'])} students" if st["allowed_ids"] else "off")
        flag_lines.append(f"  {icon} `{f}`: {scope}")

    # Config
    cfg = community.get_config()

    # Live occupancy
    guild = interaction.guild
    occ = community.lounge_occupancy(guild) if guild else {}
    occ_lines = []
    for ch_id, members in occ.items():
        ch = guild.get_channel(int(ch_id))
        name = ch.name if ch else ch_id
        occ_lines.append(f"  🎙️ {name}: {len(members)} people")
    if not occ_lines:
        occ_lines.append("  (empty)")

    text = (
        "🏛️ **Majlis — Community Lounge**\n\n"
        "**Flags:**\n" + "\n".join(flag_lines) + "\n\n"
        "**Config:**\n"
        f"  together_minutes: {cfg.get('community_together_minutes', 5)}\n"
        f"  lounge_capacity: {cfg.get('community_lounge_capacity', 6)}\n"
        f"  beacon_max_occ: {cfg.get('community_beacon_max_occupancy', 4)}\n"
        f"  beacon_cooldown: {cfg.get('community_beacon_cooldown_min', 40)} min\n"
        f"  hour: {cfg.get('community_hour_start', '21:00')} {cfg.get('community_hour_tz', 'Africa/Cairo')} ({cfg.get('community_hour_minutes', 60)} min)\n"
        f"  reward_points: {cfg.get('community_together_reward_points', 0)}\n\n"
        "**Live Lounges:**\n" + "\n".join(occ_lines)
    )
    await interaction.followup.send(text, ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Keep permission/other failures quiet + ephemeral (no ugly tracebacks,
    no leaking command existence to non-admins)."""
    if isinstance(error, (app_commands.MissingPermissions, app_commands.CheckFailure)):
        msg = "🔒 You don't have permission for this command."
    else:
        logger.exception("Slash command error", exc_info=error)
        msg = "⚠️ Something went wrong running that command."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


async def notify_student_reset_decision(discord_id: str, approved: bool, consent_id=None):
    """DM the student the outcome of their pending reset request. Best-effort;
    used by both the Discord (!approve-reset) and Telegram (/approve) paths."""
    try:
        user = bot.get_user(int(discord_id))
        if user is None:
            user = await bot.fetch_user(int(discord_id))
        if user is None:
            return
        if approved:
            await user.send(
                f"🧾 Your history reset was **approved** and completed (record #{consent_id}). "
                f"Your account is active and you're starting fresh — good luck! 🌱\n"
                f"تمّت الموافقة على إعادة ضبط سجلّك وخلصت (سجل #{consent_id}). بالتوفيق!"
            )
        else:
            await user.send(
                "Your history reset request was **not approved** this time. If you still "
                "want it, please contact the team.\n"
                "طلب إعادة ضبط سجلّك مااتوافقش عليه دلوقتي. لو لسه عايز، كلّم الفريق."
            )
    except Exception:
        pass


@bot.command(name="approve-reset")
@commands.has_permissions(manage_guild=True)
async def cmd_approve_reset(ctx, request_id: int = None):
    """(Admin) Approve a student's pending reset request → performs the reset."""
    if request_id is None:
        await ctx.send("Usage: `!approve-reset <request#>`")
        return
    res = database.approve_pending_reset(request_id, decided_by=f"discord:{ctx.author.id}")
    if res is None:
        await ctx.send(f"No pending reset request #{request_id}.")
        return
    if res.get("error"):
        await ctx.send(f"Request #{request_id} is already **{res['status']}** — no action taken.")
        return
    await ctx.send(
        f"✅ Approved reset #{request_id} for **{res['discord_name']}** "
        f"(record #{res['consent_id']}). Undo: `!restore-student {res['consent_id']}`"
    )
    await notify_student_reset_decision(res["discord_id"], True, res["consent_id"])


@bot.command(name="deny-reset")
@commands.has_permissions(manage_guild=True)
async def cmd_deny_reset(ctx, request_id: int = None):
    """(Admin) Deny a student's pending reset request → nothing is deleted."""
    if request_id is None:
        await ctx.send("Usage: `!deny-reset <request#>`")
        return
    res = database.deny_pending_reset(request_id, decided_by=f"discord:{ctx.author.id}")
    if res is None:
        await ctx.send(f"No pending reset request #{request_id}.")
        return
    if res.get("error"):
        await ctx.send(f"Request #{request_id} is already **{res['status']}** — no action taken.")
        return
    await ctx.send(f"🚫 Denied reset #{request_id} for **{res['discord_name']}**. Nothing was deleted.")
    await notify_student_reset_decision(res["discord_id"], False)


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
            "لما تعمل تمارين المفردات على منصة التمرين (`!link`)، الكلمات هتتضاف أوتوماتيك.\n"
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


@bot.command(name="checkgate")
@commands.has_permissions(administrator=True)
async def cmd_checkgate(ctx):
    """Onboarding audit (session-33): who passed the gate / has a guided
    journey, and flags anyone who slipped past either. Read-only."""
    await role_gate.cmd_checkgate(ctx)


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
        # Also revoke all Darb device sessions (Phase 3 edge gate)
        darb_revoked = database.revoke_all_device_sessions(discord_id)
        darb_info = f"\n🔐 {darb_revoked} Darb device session(s) also revoked." if darb_revoked else ""
        await ctx.send(
            f"🔒 **Token revoked** for {member.mention}{ip_info}.{darb_info}\n"
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
    for lvl in ["A1", "A2", "B1", "B2", "C1", "C2"]:
        active_levels[lvl] = len(database.members_at_level(lvl))

    msg = (
        f"**🤖 Empire English Bot Status**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Version: **{config.BOT_VERSION}**\n"
        f"Guilds: {len(bot.guilds)}\n"
        f"Members (registered): **{member_count}**\n"
        f"  🌱 A1: {active_levels['A1']} | 🌿 A2: {active_levels['A2']} | "
        f"🚀 B1: {active_levels['B1']} | 💪 B2: {active_levels['B2']} | "
        f"🏆 C1: {active_levels['C1']} | 👑 C2: {active_levels['C2']}\n"
        f"Submissions today: **{today_subs}**\n"
        f"Daily tasks: {'🟢 Running' if daily_task_post.is_running() else '🔴 Stopped'}\n"
        f"Weekly recap: {'🟢 Running' if weekly_recap.is_running() else '🔴 Stopped'}\n"
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


@bot.command(name="setlevel")
@commands.has_permissions(manage_guild=True)
async def cmd_setlevel(ctx, member: discord.Member = None, level: str = None):
    """Set a member's level. Usage: !setlevel @user L1"""
    if not member or not level:
        await ctx.send("Usage: `!setlevel @user A1/A2/B1/B2/C1/C2`")
        return
    level = level.upper()
    if level not in config.CEFR_LEVELS:
        await ctx.send("❌ Invalid level. Use: A1, A2, B1, B2, C1, C2")
        return

    database.set_level(str(member.id), level)
    await _assign_level_role(member, level)
    level_info = config.level_info(level)
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
async def cmd_maintenance(ctx, *, arg: str = ""):
    """Maintenance mode — pauses/soft-warns the whole ecosystem + notifies students.

    Usage:
      !maintenance                          — show current status
      !maintenance start [soft|hard] [min] [reason...]
      !maintenance end [what's new...]
      !maintenance on                       — alias for `start soft`
      !maintenance off                      — alias for `end`

    Soft = dismissible banner on the practice page (page stays usable).
    Hard = full-screen overlay (page paused). Both announce to
    #announcements (+ Telegram groups if configured) and set the bot's
    presence. A 2h auto-resume failsafe prevents a forgotten `end`.
    """
    parts = arg.split()
    sub = parts[0].lower() if parts else "status"
    # Legacy aliases
    if sub == "on":
        sub, parts = "start", ["start", "soft"] + parts[1:]
    elif sub == "off":
        sub = "end"; parts = ["end"] + parts[1:]

    if sub == "status":
        s = maintenance_mod.get_status()
        if s.get("state") != "maintenance":
            await ctx.send("✅ **System is LIVE** — no maintenance active.")
        else:
            await ctx.send(
                f"🔧 **Maintenance: {s.get('level', 'soft').upper()}**\n"
                f"Reason: {s.get('reason') or '—'}\n"
                f"ETA: {s.get('eta') or '—'}")
        return

    if sub == "start":
        rest = parts[1:]
        level = "soft"
        if rest and rest[0].lower() in ("soft", "hard"):
            level = rest[0].lower(); rest = rest[1:]
        eta = ""; window = maintenance_mod.DEFAULT_WINDOW_MINUTES
        if rest and rest[0].isdigit():
            mins = int(rest[0]); rest = rest[1:]
            eta = f"~{mins} min"; window = max(mins + 15, 15)
        reason = " ".join(rest).strip()
        maintenance_mod.start(level=level, reason=reason, eta=eta, window_minutes=window)
        result = await maintenance_mod.broadcast_start(ctx.bot, maintenance_mod.get_status())
        surface = "full-screen overlay" if level == "hard" else "banner"
        await ctx.send(
            f"🔧 Maintenance **STARTED** ({level}). Students now see the {surface}.\n"
            f"Announced → Discord: {'✅' if result.get('discord') else '❌'} · "
            f"Telegram groups: {result.get('telegram_groups', 0)}\n"
            f"Auto-resumes in {window} min if you forget `!maintenance end`.")
        return

    if sub == "end":
        note = " ".join(parts[1:]).strip()
        if note:
            changelog_mod.add_entry(note)   # publish to "What's New"
        maintenance_mod.end()
        result = await maintenance_mod.broadcast_end(ctx.bot, note)
        await ctx.send(
            f"✅ Maintenance **ENDED** — system is LIVE.\n"
            f"Announced → Discord: {'✅' if result.get('discord') else '❌'} · "
            f"Telegram groups: {result.get('telegram_groups', 0)}")
        return

    await ctx.send("Usage: `!maintenance start [soft|hard] [min] [reason]` / "
                   "`!maintenance end [what's new]` / `!maintenance` (status)")


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
    severity, declining assessment trends, and buddy load — combining
    signals that already exist across the bot into one view instead of
    several separate commands. Read-only, sent via DM (falls back to the
    channel if DMs are closed, same pattern as !status/!members)."""
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
    lines = [f"**👥 Members ({len(members)})**"]
    lines.append("_ID shown so you can target from #admin-commands (e.g. `!reset-student <id>`)._\n")
    for m in members[:20]:
        lvl = config.level_info(m["level"])
        streak_str = f"🔥{m['current_streak']}" if m["current_streak"] > 0 else ""
        lines.append(
            f"{lvl['emoji']} {m['discord_name']} — {m['level']} | {m['total_points']} pts {streak_str}\n"
            f"   🆔 `{m['discord_id']}`"
        )
    if len(members) > 20:
        lines.append(f"\n... and {len(members) - 20} more — use `!find <name>` to look someone up.")
    try:
        await ctx.author.send("\n".join(lines))
        await ctx.send("📩 Members list sent to your DMs.", delete_after=5)
    except discord.Forbidden:
        await ctx.send("\n".join(lines))


@bot.command(name="find")
@commands.has_permissions(manage_guild=True)
async def cmd_find(ctx, *, query: str = ""):
    """Find registered students by (partial) name and show their IDs + a
    ready-to-paste reset line. Works from #admin-commands even though the
    Discord @-picker there can't see students (it's filtered by channel
    visibility). Usage: `!find balqees`"""
    query = query.strip()
    if not query:
        await ctx.send("Usage: `!find <name or part of a name>`")
        return

    q = query.casefold()
    members = database.all_active_members()
    by_id = {str(m["discord_id"]): m for m in members}

    matches = {}  # discord_id -> (db_row, guild_display_name or None)

    # 1) match on the registered discord_name
    for m in members:
        if q in (m.get("discord_name") or "").casefold():
            matches[str(m["discord_id"])] = (m, None)

    # 2) also match on the current server nickname / display name, and only
    #    include people who are actually registered students (in the DB)
    if ctx.guild:
        for gm in ctx.guild.members:
            if gm.bot:
                continue
            did = str(gm.id)
            if did not in by_id:
                continue
            hay = f"{gm.display_name} {gm.name}".casefold()
            if q in hay:
                matches.setdefault(did, (by_id[did], gm.display_name))

    # allow looking up directly by a pasted ID too
    if query.isdigit() and query in by_id:
        matches.setdefault(query, (by_id[query], None))

    if not matches:
        await ctx.send(
            f"🔍 No registered student matches **{query}**. "
            f"Try fewer letters, or `!members` to see everyone."
        )
        return

    rows = list(matches.items())[:15]
    lines = [f"**🔍 {len(rows)} match(es) for “{query}”:**\n"]
    for did, (m, nick) in rows:
        lvl = config.level_info(m["level"])
        name = m.get("discord_name") or "(unknown)"
        nick_str = f" _(server name: {nick})_" if nick and nick != name else ""
        lines.append(
            f"{lvl['emoji']} **{name}**{nick_str} — {m['level']} | {m['total_points']} pts\n"
            f"   🆔 `{did}`\n"
            f"   ↪ reset: `!reset-student {did} <reason>`"
        )
    if len(matches) > 15:
        lines.append(f"\n... and {len(matches) - 15} more — narrow your search.")

    out = "\n".join(lines)
    try:
        await ctx.author.send(out)
        await ctx.send("📩 Sent the matches to your DMs.", delete_after=5)
    except discord.Forbidden:
        await ctx.send(out)



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
async def cmd_resources(ctx, level: str = "A1"):
    """Post shadowing resources for a level. Usage: !resources A1"""
    level = config.cefr_key(level.upper())
    if level not in config.CEFR_ORDER:
        await ctx.send("Usage: `!resources A1/A2/B1/B2/C1/C2`")
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
async def cmd_difficulty(ctx, action: str = ""):
    """View your adaptive difficulty, or `!difficulty reset` to set it back
    to Normal. Empire Reset 1b: the old separate `!difficulty_reset` command
    is merged in here as the `reset` argument."""
    from . import adaptive_engine

    discord_id = str(ctx.author.id)
    member = database.get_member(discord_id)
    if not member:
        await ctx.send("You're not registered yet. Use `!join` to start.")
        return

    if action.strip().lower() == "reset":
        database.update_member(discord_id, difficulty_level=2)
        await ctx.send("✅ Difficulty reset to **Normal / عادي**.")
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

    platform_url = config.PRACTICE_PLATFORM_URL

    # Darb: issue a one-time CLAIM CODE (the gate/edge middleware only
    # accepts codes minted by create_claim_code -> /api/claim, NOT the
    # legacy link token). Rate-limited to 6/hour; returns None if exceeded.
    code = database.create_claim_code(discord_id)
    if not code:
        await ctx.send(
            "⏳ لقد طلبت أكواد كتير في الساعة الأخيرة. استنى شوية وحاول تاني.\n"
            "(You've requested several codes in the last hour — please wait a bit and try again.)"
        )
        return

    # Also refresh the legacy link token so the older dashboard/progress
    # API keeps working for anything still using it (harmless, not shown).
    database.create_link_token(discord_id)

    # DM the claim code + a one-click link (the gate auto-fills ?code=).
    try:
        await ctx.author.send(
            f"🔗 **كود الدخول لمنصة التمرين**\n\n"
            f"الكود بتاعك (صالح ١٥ دقيقة، مرة واحدة بس):\n"
            f"```\n{code}\n```\n\n"
            f"**اضغط الرابط ده وهيدخّلك على طول:**\n"
            f"{platform_url}?code={code}\n\n"
            f"أو افتح **{platform_url}** والصق الكود في خانة الدخول.\n\n"
            f"⚠️ **الكود ده خاص بيك — ماتشاركهوش مع حد.**\n"
            f"لو خلص أو ضاع، اكتب `!link` تاني عشان تاخد كود جديد."
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
#  SUSPENSION LIFECYCLE (monthly membership cycle)
# ============================================================
#
# Every one of these is destructive or student-visible, so they share three
# guardrails: DRY RUN IS THE DEFAULT, a typed confirmation is required to act,
# and the result is reported per student rather than as a single "done".
# A silent bulk action over 16 students is how the wrong person gets cut off.

SUSPENSION_CONFIRM_TIMEOUT = 120


async def _suspension_confirm(ctx, word: str, preview: str) -> bool:
    """Show the preview, then require the exact word typed back."""
    await ctx.send(preview)
    await ctx.send(f"Type **`{word}`** to proceed, or anything else to cancel. "
                   f"(expires in {SUSPENSION_CONFIRM_TIMEOUT}s)")

    def _check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

    try:
        reply = await bot.wait_for("message", check=_check,
                                   timeout=SUSPENSION_CONFIRM_TIMEOUT)
    except asyncio.TimeoutError:
        await ctx.send("⌛ Timed out — **nothing was changed.**")
        return False
    if reply.content.strip() != word:
        await ctx.send("✅ Cancelled — **nothing was changed.**")
        return False
    return True


def _suspension_targets(ctx, members, selector):
    """Mentions win; otherwise fall back to a bulk selector."""
    if members:
        rows = []
        for m in members:
            row = database.get_member(str(m.id))
            if row:
                rows.append(row)
        return rows, f"{len(rows)} mentioned"
    return suspension.resolve_selection(selector or "")


@bot.command(name="suspend")
@commands.has_permissions(administrator=True)
async def cmd_suspend(ctx, *args):
    """Withdraw access when a membership lapses.

    !suspend @a @b            specific students (dry run)
    !suspend all              every active student (dry run)
    !suspend all go           actually do it (asks for confirmation)
    """
    if not database.is_feature_enabled(suspension.FLAG):
        await ctx.send(f"⚠️ `{suspension.FLAG}` is disabled. "
                       f"Enable it with `!flag enable {suspension.FLAG}`.")
        return

    tokens = [a for a in args]
    live = "go" in [t.lower() for t in tokens]
    selector = next((t for t in tokens
                     if t.lower() in ("all", "expired", "suspended")), "")
    rows, desc = _suspension_targets(ctx, ctx.message.mentions, selector)

    if not rows:
        await ctx.send(
            "**Usage**\n"
            "`!suspend @student [@student2 ...]` — dry run for those students\n"
            "`!suspend all` — dry run for every active student\n"
            "`!suspend all go` — actually suspend (you'll be asked to confirm)\n\n"
            "Suspension removes the Student role (channels disappear), revokes "
            "practice-site sessions and tokens, and starts the "
            f"{database.RETENTION_DAYS}-day retention clock. **It deletes nothing.**")
        return

    guild = ctx.guild or bot.get_guild(config.GUILD_ID)

    # --- always preview first ---
    preview = await asyncio.gather(*[
        suspension.suspend_one(guild, r, dry_run=True) for r in rows])
    lines = []
    for p in preview:
        if p["already"]:
            lines.append(f"• {p['name']} — already suspended, will be skipped")
        elif p["role_removed"] is None:
            lines.append(f"• {p['name']} — ⚠️ not in the server (role step will be skipped)")
        else:
            lines.append(f"• {p['name']} — sessions: {p['sessions']}, "
                         f"token: {'yes' if p['tokens'] else 'no'}, "
                         f"role: {'will be removed' if p['role_removed'] else 'not held'}")
    body = "\n".join(lines[:30])
    if len(lines) > 30:
        body += f"\n… and {len(lines) - 30} more"

    if not live:
        await ctx.send(f"🔍 **DRY RUN — nothing changed.** Target: {desc}\n\n{body}\n\n"
                       f"Add `go` to the command to actually suspend.")
        return

    actionable = [r for r, p in zip(rows, preview) if not p["already"]]
    if not actionable:
        await ctx.send("Everyone selected is already suspended — nothing to do.")
        return

    if not await _suspension_confirm(
            ctx, "SUSPEND",
            f"⚠️ **About to suspend {len(actionable)} student(s).** "
            f"Target: {desc}\n\n{body}"):
        return

    results = []
    for r in actionable:
        results.append(await suspension.suspend_one(guild, r, dry_run=False))

    ok = [r for r in results if r["flagged"]]
    problems = [r for r in results if r["errors"]]
    msg = [f"🔒 **Suspended {len(ok)}/{len(actionable)}.**"]
    roles_removed = sum(1 for r in results if r["role_removed"] is True)
    sessions = sum(r["sessions"] for r in results)
    msg.append(f"• Student role removed: **{roles_removed}**")
    msg.append(f"• Practice sessions revoked: **{sessions}**")
    msg.append(f"• Retention clock started — purge in **{database.RETENTION_DAYS} days** "
               f"unless restored.")
    if problems:
        msg.append("\n⚠️ **Issues (each student's data is still intact):**")
        for r in problems[:10]:
            msg.append(f"• {r['name']}: {'; '.join(r['errors'])}")
    await ctx.send("\n".join(msg))


@bot.command(name="restore")
@commands.has_permissions(administrator=True)
async def cmd_restore(ctx, *args):
    """Give access back after a renewal. Resumes, never restarts.

    !restore @student          dry run
    !restore @student go       actually restore
    !restore suspended         dry run over everyone suspended
    """
    if not database.is_feature_enabled(suspension.FLAG):
        await ctx.send(f"⚠️ `{suspension.FLAG}` is disabled.")
        return

    tokens = [a.lower() for a in args]
    live = "go" in tokens
    selector = next((t for t in tokens if t in ("suspended", "all")), "")
    rows, desc = _suspension_targets(ctx, ctx.message.mentions,
                                     "suspended" if selector else "")

    if not rows:
        pending = database.suspended_members()
        listing = "\n".join(
            f"• {m['discord_name']} — suspended {m['days_suspended']}d, "
            f"purges in {m['days_until_purge']}d" for m in pending[:20]
        ) or "_nobody is currently suspended_"
        await ctx.send(
            "**Usage**\n`!restore @student` — dry run\n"
            "`!restore @student go` — actually restore\n\n"
            f"**Currently suspended ({len(pending)}):**\n{listing}")
        return

    guild = ctx.guild or bot.get_guild(config.GUILD_ID)
    preview = await asyncio.gather(*[
        suspension.restore_one(guild, r, dry_run=True) for r in rows])
    lines = []
    for r, p in zip(rows, preview):
        if p["not_suspended"]:
            lines.append(f"• {p['name']} — not suspended, will be skipped")
        else:
            lines.append(f"• {p['name']} — will bridge **{p['bridged_days']} day(s)** "
                         f"so the streak survives")
    body = "\n".join(lines[:30])

    if not live:
        await ctx.send(f"🔍 **DRY RUN — nothing changed.**\n\n{body}\n\n"
                       f"Add `go` to actually restore.")
        return

    actionable = [r for r, p in zip(rows, preview) if not p["not_suspended"]]
    if not actionable:
        await ctx.send("Nobody selected is suspended — nothing to do.")
        return

    results = []
    for r in actionable:
        res = await suspension.restore_one(guild, r, dry_run=False)
        if res["cleared"]:
            await suspension.dm_restored(guild, res["discord_id"], res["name"])
        results.append(res)

    ok = [r for r in results if r["cleared"]]
    msg = [f"✅ **Restored {len(ok)}/{len(actionable)}.**"]
    for r in results:
        bits = [f"streak bridged {r['bridged_days']}d",
                f"role {'restored' if r['role_added'] else 'NOT restored'}"]
        if r["errors"]:
            bits.append("⚠️ " + "; ".join(r["errors"]))
        msg.append(f"• {r['name']} — {', '.join(bits)}")
    msg.append("\nThey each got a DM telling them to run `!link` for a fresh "
               "practice-page code (the old session was revoked).")
    await ctx.send("\n".join(msg))


@bot.command(name="announce-renewal")
@commands.has_permissions(administrator=True)
async def cmd_announce_renewal(ctx, *args):
    """Send the end-of-month renewal notice everywhere.

    !announce-renewal "الأربعاء ٢ سبتمبر"        dry run
    !announce-renewal "الأربعاء ٢ سبتمبر" go     actually send
    """
    if not database.is_feature_enabled(suspension.FLAG):
        await ctx.send(f"⚠️ `{suspension.FLAG}` is disabled.")
        return

    tokens = list(args)
    live = bool(tokens) and tokens[-1].lower() == "go"
    if live:
        tokens = tokens[:-1]
    cutoff = " ".join(tokens).strip()
    if not cutoff:
        await ctx.send(
            "**Usage**\n"
            '`!announce-renewal "الأربعاء ٢ سبتمبر"` — dry run\n'
            '`!announce-renewal "الأربعاء ٢ سبتمبر" go` — send for real\n\n'
            "Sends a DM to every active student, posts to #announcements, and "
            "posts to the Telegram student groups. **Always state the cutoff "
            "date explicitly** — never a relative phrase like 'in 5 days'.")
        return

    res = await suspension.broadcast_renewal(bot, cutoff, dry_run=True)
    if not live:
        await ctx.send(
            f"🔍 **DRY RUN — nothing sent.**\n"
            f"• Cutoff shown to students: **{cutoff}**\n"
            f"• Would DM: **{res['targets']}** active student(s)\n"
            f"• Would post to #announcements and "
            f"{len(getattr(config, 'MAINTENANCE_TG_CHAT_IDS', []) or [])} "
            f"Telegram group(s)\n\n"
            f"Here is the exact DM a student would receive:\n\n"
            f"{suspension.renewal_dm('اسم الطالب', cutoff)[:1500]}")
        return

    if not await _suspension_confirm(
            ctx, "SEND",
            f"⚠️ **About to message {res['targets']} students** with cutoff "
            f"**{cutoff}**, plus #announcements and the Telegram groups."):
        return

    await ctx.send("📤 Sending — this takes a moment (throttled to respect "
                   "Discord's DM rate limits)…")
    out = await suspension.broadcast_renewal(bot, cutoff, dry_run=False)
    msg = [f"📬 **Renewal notice sent.**",
           f"• DMs delivered: **{len(out['sent'])}/{out['targets']}**",
           f"• #announcements: {'✅' if out['announcement'] else '❌'}",
           f"• Telegram groups: **{out['telegram_groups']}**"]
    if out["left_server"]:
        msg.append(f"\n⚠️ **Not in the server (reach them another way):** "
                   f"{', '.join(out['left_server'])}")
    if out["failed"]:
        msg.append("\n⚠️ **DM failed (likely DMs closed):**")
        for n, why in out["failed"][:10]:
            msg.append(f"• {n}: {why}")
    await ctx.send("\n".join(msg))


@bot.command(name="suspended")
@commands.has_permissions(manage_guild=True)
async def cmd_suspended(ctx):
    """Who is suspended, and how long until their data is purged."""
    rows = database.suspended_members()
    if not rows:
        await ctx.send("✅ Nobody is currently suspended.")
        return
    lines = [f"🔒 **Suspended students ({len(rows)})** — "
             f"retention {database.RETENTION_DAYS} days"]
    for m in rows:
        warn = " ⚠️" if m["days_until_purge"] <= database.PURGE_WARNING_DAYS else ""
        lines.append(f"• **{m['discord_name']}** — suspended {m['days_suspended']}d, "
                     f"purge in **{m['days_until_purge']}d**{warn}")
    lines.append("\n`!restore @student go` to bring someone back.")
    await ctx.send("\n".join(lines))


@tasks.loop(hours=3)
async def assessment_watchdog_loop():
    """Watch the assessment surface and alert Empire Ops before a student has to.

    Every 3 hours rather than daily: the dead `/api/assessment/item` endpoint
    blocked every weekly submission for roughly a day before a student mentioned
    it, and a day is far too long to be silently broken. Read-only by design —
    it reports, it never repairs.
    """
    if config.IS_GHOST_INSTANCE:
        return
    if not database.is_feature_enabled(assessment_watchdog.FLAG):
        return
    try:
        report = await assessment_watchdog.run_and_alert(bot)
        if report["findings"]:
            logger.warning("assessment_watchdog: %d finding(s): %s",
                           len(report["findings"]), report["findings"][:3])
    except Exception as e:
        logger.error(f"assessment_watchdog_loop failed: {e}")


@bot.command(name="assessment-health")
@commands.has_permissions(manage_guild=True)
async def cmd_assessment_health(ctx):
    """Run the assessment watchdog checks now and show the result."""
    await ctx.send("🔍 Checking the assessment surface…")
    try:
        report = await assessment_watchdog.run_checks()
        await ctx.send(assessment_watchdog.format_report(report))
    except Exception as e:
        await ctx.send(f"❌ The health check itself failed: `{e}`")


@tasks.loop(time=datetime.time(hour=4, minute=30, tzinfo=_zone()))
async def retention_cycle():
    """Daily: warn the owner at day 53, purge at day 60.

    Runs at 04:30 — deliberately off-hours, since a purge VACUUMs the database
    and these students work 21:00-04:00. Flag-gated and fully wrapped: a
    retention job must never be able to take the bot down.
    """
    if config.IS_GHOST_INSTANCE:
        return
    if not database.is_feature_enabled(suspension.FLAG):
        return
    try:
        summary = await suspension.run_retention_cycle(dry_run=False)
        if summary["warned"] or summary["purged"]:
            logger.info("retention_cycle: warned=%s purged=%s",
                        summary["warned"], len(summary["purged"]))
    except Exception as e:
        logger.error(f"retention_cycle failed: {e}")


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
