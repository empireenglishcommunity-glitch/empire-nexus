"""Markaz (مركز) Phase M3 — Quick-action Telegram commands.

Owner-facing commands that can be sent directly to @empire_ops_eec_bot
without needing Discord open. Dispatched from ops_poller._handle_update()
when a message begins with '/' and isn't a reply to another message.

All handlers receive (args: str, bot) and return a response string
(already MarkdownV2-formatted) to send back to the owner. Handlers
must never raise — they catch their own errors and return a friendly
error message instead.
"""
import datetime
import logging
from typing import Optional

import discord

from . import config, database, ops_hub

logger = logging.getLogger("empire-bot.ops_commands")


# ============================================================
#  COMMAND REGISTRY
# ============================================================

COMMANDS: dict[str, callable] = {}


def command(name: str):
    """Decorator to register a Telegram command handler."""
    def decorator(func):
        COMMANDS[name] = func
        return func
    return decorator


async def dispatch(text: str, bot) -> Optional[str]:
    """Parse a /command from the message text and dispatch to the right
    handler. Returns the response message (MarkdownV2-formatted) to send
    back, or None if the text isn't a recognized command.

    Called from ops_poller._handle_update() for standalone (non-reply)
    messages that start with '/'.
    """
    if not text.startswith("/"):
        return None

    parts = text.split(None, 1)
    cmd_name = parts[0].lower().split("@")[0]  # strip @botname suffix
    args = parts[1] if len(parts) > 1 else ""

    handler = COMMANDS.get(cmd_name)
    if not handler:
        available = ", ".join(sorted(COMMANDS.keys()))
        return f"❓ Unknown command: `{ops_hub.escape_markdown(cmd_name)}`\n\nAvailable: {ops_hub.escape_markdown(available)}"

    try:
        return await handler(args, bot)
    except Exception as e:
        logger.error(f"ops_commands: error in {cmd_name}: {e}")
        return f"❌ Error running `{ops_hub.escape_markdown(cmd_name)}`: {ops_hub.escape_markdown(str(e)[:200])}"


# ============================================================
#  /status — bot uptime, API health, active student count
# ============================================================

@command("/status")
async def handle_status(args: str, bot) -> str:
    """System health snapshot."""
    member_count = database.member_count()
    today_subs = database.total_submissions_today()
    pending = database.count_pending_escalations()

    # Level breakdown
    levels = {}
    for lvl in ["L0", "L1", "L2", "L3"]:
        levels[lvl] = len(database.members_at_level(lvl))

    # Uptime from heartbeat
    last_hb = database.get_setting("last_heartbeat", "")
    hb_status = "✅" if last_hb else "⚠️ no heartbeat"

    # AI providers
    groq = "✅" if config.GROQ_API_KEY else "❌"
    gemini = "✅" if config.GEMINI_API_KEY else "❌"

    # Bot connection
    bot_ok = "✅" if bot.is_ready() else "❌"

    lines = [
        "*🤖 Empire English Bot — Status*",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"*Version:* `{ops_hub.escape_markdown(config.BOT_VERSION)}`",
        f"*Discord:* {bot_ok} \\| Guilds: {len(bot.guilds)}",
        f"*Heartbeat:* {hb_status}",
        f"*AI:* Groq {groq} \\| Gemini {gemini}",
        "",
        f"*👥 Students:* {member_count} registered",
        f"  🌱 L0: {levels['L0']} \\| 💪 L1: {levels['L1']} \\| 🚀 L2: {levels['L2']} \\| 👑 L3: {levels['L3']}",
        f"*✅ Today:* {today_subs} submissions",
        f"*🚨 Escalations:* {pending} pending",
    ]
    return "\n".join(lines)


# ============================================================
#  /students — list active students with level + streak
# ============================================================

@command("/students")
async def handle_students(args: str, bot) -> str:
    """List active students. Paginated — send '/students 2' for page 2."""
    PAGE_SIZE = 10
    try:
        page = max(1, int(args.strip())) if args.strip() else 1
    except ValueError:
        page = 1

    members = database.all_active_members()
    total = len(members)

    if total == 0:
        return "👥 No active students registered yet\\."

    # Sort by streak descending for a useful default view
    for m in members:
        streak_data = database.get_streak(m["discord_id"])
        m["_streak"] = streak_data[0] if streak_data else 0
    members.sort(key=lambda m: m["_streak"], reverse=True)

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)
    start = (page - 1) * PAGE_SIZE
    page_members = members[start:start + PAGE_SIZE]

    lines = [
        f"*👥 Active Students* \\(page {page}/{total_pages}, {total} total\\)",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for i, m in enumerate(page_members, start=start + 1):
        name = (m.get("discord_name") or "Unknown").split("#")[0]
        safe_name = ops_hub.escape_markdown(name)
        level = m.get("level", "?")
        streak = m["_streak"]
        lines.append(f"{i}\\. *{safe_name}* — {level}, 🔥{streak}d")

    if total_pages > 1:
        lines.append("")
        lines.append(f"📄 Page {page}/{total_pages} — send `/students {page + 1}` for next")

    return "\n".join(lines)


# ============================================================
#  /flag — toggle feature flags from Telegram
# ============================================================

@command("/flag")
async def handle_flag(args: str, bot) -> str:
    """Toggle or list feature flags.

    /flag           — list all flags with current state
    /flag <name> on  — enable a flag
    /flag <name> off — disable a flag
    """
    args = args.strip()

    if not args:
        # List all flags
        flags = database.list_feature_flags()
        if not flags:
            return "🚩 No feature flags configured\\."
        lines = ["*🚩 Feature Flags*", "━━━━━━━━━━━━━━━━━━━━", ""]
        for f in flags:
            state = "🟢" if f["enabled"] else "🔴"
            safe_name = ops_hub.escape_markdown(f["name"])
            lines.append(f"  {state} `{safe_name}`")
        lines.append("")
        lines.append("Toggle: `/flag <name> on` or `/flag <name> off`")
        return "\n".join(lines)

    parts = args.split()
    flag_name = parts[0]

    if len(parts) < 2:
        # Just show this flag's state
        enabled = database.is_feature_enabled(flag_name)
        state = "🟢 ON" if enabled else "🔴 OFF"
        return f"🚩 `{ops_hub.escape_markdown(flag_name)}` is currently *{state}*"

    action = parts[1].lower()
    if action in ("on", "enable", "1", "true"):
        database.set_feature_flag(flag_name, enabled=True, updated_by="telegram_ops")
        return f"🟢 `{ops_hub.escape_markdown(flag_name)}` is now *ON*"
    elif action in ("off", "disable", "0", "false"):
        database.set_feature_flag(flag_name, enabled=False, updated_by="telegram_ops")
        return f"🔴 `{ops_hub.escape_markdown(flag_name)}` is now *OFF*"
    else:
        return f"❓ Unknown action `{ops_hub.escape_markdown(action)}`\\. Use `on` or `off`\\."


# ============================================================
#  /announce — post to Discord #announcements
# ============================================================

@command("/announce")
async def handle_announce(args: str, bot) -> str:
    """Post an announcement to Discord #announcements channel."""
    if not args.strip():
        return "Usage: `/announce Your message here`"

    message = args.strip()
    if len(message) > 1950:
        return f"❌ Too long \\({len(message)} chars\\)\\. Keep under 1950\\."

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return "❌ Discord guild not found\\."

    channel = discord.utils.get(guild.text_channels, name="announcements")
    if not channel:
        return "❌ `#announcements` channel not found\\."

    try:
        await channel.send(f"📢 **Announcement**\n\n{message}")
        return f"✅ Posted to \\#announcements \\({len(message)} chars\\)"
    except Exception as e:
        logger.error(f"ops_commands /announce: {e}")
        return f"❌ Failed to post: {ops_hub.escape_markdown(str(e)[:150])}"


# ============================================================
#  /nour — quick toggle for nour_concierge flag
# ============================================================

@command("/nour")
async def handle_nour(args: str, bot) -> str:
    """Quick toggle for the nour_concierge feature flag.

    /nour       — show current state
    /nour on    — enable Nour
    /nour off   — disable Nour
    """
    flag_name = "nour_concierge"
    args = args.strip().lower()

    if not args:
        enabled = database.is_feature_enabled(flag_name)
        state = "🟢 ON" if enabled else "🔴 OFF"
        return f"💬 Nour is currently *{state}*\n\nToggle: `/nour on` or `/nour off`"

    if args in ("on", "enable", "1"):
        database.set_feature_flag(flag_name, enabled=True, updated_by="telegram_ops")
        return "💬 Nour is now *🟢 ON* — responding to student DMs and \\#ask\\-nour"
    elif args in ("off", "disable", "0"):
        database.set_feature_flag(flag_name, enabled=False, updated_by="telegram_ops")
        return "💬 Nour is now *🔴 OFF* — students will get no AI response until re\\-enabled"
    else:
        return f"❓ Use `/nour on` or `/nour off`"


# ============================================================
#  /help — list available commands
# ============================================================

@command("/help")
async def handle_help(args: str, bot) -> str:
    """List all available commands."""
    lines = [
        "*📡 Empire Ops — Commands*",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "`/status` — Bot health, students, AI status",
        "`/students` — Active students with level \\+ streak",
        "`/flag` — List/toggle feature flags",
        "`/flag <name> on/off` — Toggle a specific flag",
        "`/announce <msg>` — Post to \\#announcements",
        "`/nour on/off` — Quick toggle for Nour AI concierge",
        "`/help` — This message",
        "",
        "💡 Reply to an escalation message to respond as Nour\\.",
    ]
    return "\n".join(lines)



# ============================================================
#  /check — full student status report (Rawiya R5)
# ============================================================

@command("/check")
async def handle_check(args: str, bot) -> str:
    """Get a detailed status report for a specific student.

    Usage: /check [name or partial name]
    """
    if not args.strip():
        return "Usage: `/check [student name]`"

    name = args.strip().lower()
    members = database.all_active_members()
    member = None
    for m in members:
        display_name = (m.get("discord_name", "") or "").split("#")[0].lower()
        if name in display_name:
            member = m
            break

    if not member:
        return f"❌ Student '{ops_hub.escape_markdown(args.strip())}' not found\\."

    discord_id = member["discord_id"]
    level = member.get("level", "L0")
    streak, longest = database.get_streak(discord_id)
    points = member.get("total_points", 0)
    week = database.member_week_number(discord_id)
    tasks_today = len(database.tasks_completed_today(discord_id))
    safe_name = ops_hub.escape_markdown((member.get("discord_name", "?").split("#")[0]))

    # Days since active
    last_active = member.get("last_active_at", "")
    try:
        last_dt = datetime.datetime.fromisoformat(last_active)
        days_inactive = (datetime.datetime.now() - last_dt).days
    except (ValueError, TypeError):
        days_inactive = 0

    # Journey status
    from . import nour_journey
    journey = nour_journey._get_journey(discord_id)
    if journey and journey.get("completed_at"):
        journey_status = "✅ Completed"
    elif journey:
        journey_status = f"Step: {ops_hub.escape_markdown(journey['current_step'])}"
    else:
        journey_status = "Not started"

    # Pronunciation
    pron_avg = database.get_pronunciation_average(discord_id)

    return (
        f"👤 *{safe_name}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Level: {level} \\| Week: {week}\n"
        f"🔥 Streak: {streak} days \\(best: {longest}\\)\n"
        f"💎 Points: {points:,}\n"
        f"✅ Today: {tasks_today}/7 tasks\n"
        f"⏱ Last active: {days_inactive} day\\(s\\) ago\n"
        f"🎙 Pronunciation avg: {pron_avg:.0f}%\n"
        f"🗺 Journey: {journey_status}"
    )


# ============================================================
#  /nudge — send personalized Nour check-in (Rawiya R5)
# ============================================================

@command("/nudge")
async def handle_nudge(args: str, bot) -> str:
    """Send a personalized Nour check-in DM to a student.

    Usage: /nudge [name or partial name]
    """
    if not args.strip():
        return "Usage: `/nudge [student name]`"

    name = args.strip().lower()
    members = database.all_active_members()
    member = None
    for m in members:
        display_name = (m.get("discord_name", "") or "").split("#")[0].lower()
        if name in display_name:
            member = m
            break

    if not member:
        return f"❌ Student '{ops_hub.escape_markdown(args.strip())}' not found\\."

    discord_id = member["discord_id"]
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return "❌ Discord guild not found\\."

    discord_member = guild.get_member(int(discord_id))
    if not discord_member:
        return "❌ Member not in server\\."

    safe_name = (member.get("discord_name", "").split("#")[0]) or "there"
    try:
        await discord_member.send(
            f"👋 مرحبًا {safe_name}!\n\n"
            f"كل شيء على ما يرام؟ لاحظت أنك لم تكن نشطًا مؤخرًا.\n"
            f"إذا احتجت أي مساعدة أو لديك سؤال، أنا هنا دائمًا 😊\n\n"
            f"💡 تذكّر: مهمة واحدة يوميًا تكفي للحفاظ على السلسلة!"
        )
        return f"✅ Nudge sent to *{ops_hub.escape_markdown(safe_name)}*\\."
    except Exception as e:
        return f"❌ Could not DM {ops_hub.escape_markdown(safe_name)}: {ops_hub.escape_markdown(str(e)[:100])}"
