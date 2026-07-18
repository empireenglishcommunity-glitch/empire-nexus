"""Nour (نور) — Owner Operations Commands (Rawiya R5).

Processes /command messages from the owner in Telegram, enabling
full community management from the phone.

Commands:
  /check [name]    — full student status report
  /announce [msg]  — post announcement in Discord
  /nudge [name]    — send personalized Nour check-in
  /flag [name]     — mark student for attention
  /status          — system health overview
  /students        — quick roster with activity summary

Gated behind 'nour_owner_commands' feature flag.
"""
import datetime
import logging
from typing import Optional

from . import config, database, ops_hub

logger = logging.getLogger("empire-bot.nour.ops_commands")


async def handle_owner_command(text: str, bot) -> Optional[str]:
    """Parse and execute an owner command from Telegram.

    Returns a response string to send back to the owner, or None
    if the text is not a command.
    """
    if not database.is_feature_enabled("nour_owner_commands"):
        return None

    text = text.strip()
    if not text.startswith("/"):
        return None

    parts = text.split(None, 1)
    command = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    handlers = {
        "/check": _cmd_check,
        "/students": _cmd_students,
        "/status": _cmd_status,
        "/nudge": _cmd_nudge,
        "/announce": _cmd_announce,
        "/flag": _cmd_flag,
    }

    handler = handlers.get(command)
    if not handler:
        return (
            "📋 *Available commands:*\n"
            "/check \\[name\\] — student status\n"
            "/students — roster summary\n"
            "/status — system health\n"
            "/nudge \\[name\\] — send check\\-in\n"
            "/announce \\[msg\\] — Discord announcement\n"
            "/flag \\[name\\] \\[reason\\] — mark for attention"
        )

    return await handler(args, bot)


async def _cmd_check(name: str, bot) -> str:
    """Get full status report for a student."""
    if not name:
        return "❌ Usage: /check \\[student name\\]"

    # Find member by name (partial match)
    members = database.all_active_members()
    member = None
    for m in members:
        display_name = (m.get("discord_name", "") or "").split("#")[0].lower()
        if name.lower() in display_name:
            member = m
            break

    if not member:
        return f"❌ Student '{ops_hub.escape_markdown(name)}' not found\\."

    discord_id = member["discord_id"]
    level = member.get("level", "L0")
    streak = member.get("current_streak", 0)
    longest = member.get("longest_streak", 0)
    points = member.get("total_points", 0)
    week = database.member_week_number(discord_id)
    tasks_today = len(database.tasks_completed_today(discord_id))
    safe_name = ops_hub.escape_markdown(member.get("discord_name", "?").split("#")[0])

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
    journey_status = "Completed" if journey and journey.get("completed_at") else (
        f"Step: {journey['current_step']}" if journey else "Not started"
    )

    return (
        f"👤 *{safe_name}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Level: {level} \\| Week: {week}\n"
        f"🔥 Streak: {streak} days \\(best: {longest}\\)\n"
        f"💎 Points: {points}\n"
        f"✅ Today: {tasks_today}/7 tasks\n"
        f"⏱ Last active: {days_inactive} day\\(s\\) ago\n"
        f"🗺 Journey: {ops_hub.escape_markdown(journey_status)}"
    )


async def _cmd_students(args: str, bot) -> str:
    """Quick roster with activity summary."""
    members = database.all_active_members()
    if not members:
        return "📋 No active students\\."

    total = len(members)
    today = datetime.date.today().isoformat()

    active_today = 0
    at_risk = 0
    for m in members:
        tasks = database.tasks_completed_today(m["discord_id"])
        if tasks:
            active_today += 1
        last_active = m.get("last_active_at", "")
        try:
            last_dt = datetime.datetime.fromisoformat(last_active)
            if (datetime.datetime.now() - last_dt).days >= 3:
                at_risk += 1
        except (ValueError, TypeError):
            pass

    # Top 5 by streak
    sorted_members = sorted(members, key=lambda m: m.get("current_streak", 0), reverse=True)
    top_lines = []
    for m in sorted_members[:5]:
        name = ops_hub.escape_markdown((m.get("discord_name", "?").split("#")[0])[:12])
        streak = m.get("current_streak", 0)
        level = m.get("level", "?")
        top_lines.append(f"  {name}: 🔥{streak} \\({level}\\)")

    top_text = "\n".join(top_lines) if top_lines else "  \\(no students\\)"

    return (
        f"📋 *Student Roster*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total: {total}\n"
        f"✅ Active today: {active_today}\n"
        f"⚠️ At risk \\(3\\+ days silent\\): {at_risk}\n\n"
        f"🏆 *Top by streak:*\n{top_text}"
    )


async def _cmd_status(args: str, bot) -> str:
    """System health overview."""
    member_count = database.member_count()
    today_subs = database.total_submissions_today()

    # Bot uptime (from heartbeat)
    last_hb = database.get_setting("last_heartbeat", "")
    hb_status = "✅ Healthy" if last_hb else "❓ Unknown"

    # Flag count
    from . import flag_registry
    total_flags = len(flag_registry.REGISTRY)

    # Security stats
    sec = database.get_security_stats()

    return (
        f"⚙️ *System Status*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Bot: {hb_status}\n"
        f"👥 Members: {member_count}\n"
        f"✅ Tasks today: {today_subs}\n"
        f"🏴 Flags: {total_flags} registered\n"
        f"🏰 Security: {sec['flagged_tokens']} flagged tokens\n"
        f"🔍 Tracked tokens: {sec['total_tracked_tokens']}"
    )


async def _cmd_nudge(name: str, bot) -> str:
    """Send a personalized Nour check-in to a student."""
    if not name:
        return "❌ Usage: /nudge \\[student name\\]"

    members = database.all_active_members()
    member = None
    for m in members:
        display_name = (m.get("discord_name", "") or "").split("#")[0].lower()
        if name.lower() in display_name:
            member = m
            break

    if not member:
        return f"❌ Student '{ops_hub.escape_markdown(name)}' not found\\."

    discord_id = member["discord_id"]
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return "❌ Guild not found\\."

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
        return f"✅ Nudge sent to {ops_hub.escape_markdown(safe_name)}\\."
    except Exception:
        return f"❌ Could not DM {ops_hub.escape_markdown(safe_name)} \\(DMs disabled?\\)\\."


async def _cmd_announce(message: str, bot) -> str:
    """Post announcement in Discord #announcements or #general-chat."""
    if not message:
        return "❌ Usage: /announce \\[message\\]"

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return "❌ Guild not found\\."

    # Try #announcements first, fall back to #general-chat
    import discord as _discord
    channel = _discord.utils.get(guild.text_channels, name="announcements")
    if not channel:
        channel = _discord.utils.get(guild.text_channels, name="general-chat")
    if not channel:
        return "❌ No announcement channel found\\."

    try:
        await channel.send(f"📢 **إعلان:**\n\n{message}")
        safe_channel = ops_hub.escape_markdown(channel.name)
        return f"✅ Announced in \\#{safe_channel}\\."
    except Exception as e:
        return f"❌ Failed: {ops_hub.escape_markdown(str(e)[:100])}"


async def _cmd_flag(args: str, bot) -> str:
    """Mark a student for attention with a reason."""
    parts = args.split(None, 1)
    if not parts:
        return "❌ Usage: /flag \\[name\\] \\[reason\\]"

    name = parts[0]
    reason = parts[1] if len(parts) > 1 else "Manual flag by owner"

    members = database.all_active_members()
    member = None
    for m in members:
        display_name = (m.get("discord_name", "") or "").split("#")[0].lower()
        if name.lower() in display_name:
            member = m
            break

    if not member:
        return f"❌ Student '{ops_hub.escape_markdown(name)}' not found\\."

    # Store flag in settings (simple approach)
    discord_id = member["discord_id"]
    safe_name = member.get("discord_name", "?").split("#")[0]
    flag_key = f"flagged_{discord_id}"
    database.set_setting(flag_key, f"{reason} ({datetime.date.today().isoformat()})")

    return f"🚩 Flagged {ops_hub.escape_markdown(safe_name)}: {ops_hub.escape_markdown(reason)}"
