"""Nour (نور) — Escalation Pipeline.

Sends Telegram alerts to the owner when Nour can't handle something.
Owner can reply via Telegram → response forwarded to student as Nour.

Gated behind 'nour_escalation' feature flag.
"""
import logging
from typing import Optional

import aiohttp

from . import config, database, ops_hub
from .ops_hub import escape_markdown

logger = logging.getLogger("empire-bot.nour.escalation")

# Pending escalations: {telegram_message_id: discord_id}
# Used for owner reply forwarding
_pending_escalations: dict[int, str] = {}


async def escalate_to_owner(discord_id: str, student_name: str,
                            student_message: str, context: str = "") -> bool:
    """Send a Telegram alert to the owner with student context.

    Returns True if sent successfully, False otherwise.
    """
    if not database.is_feature_enabled("nour_escalation"):
        logger.info(f"Nour escalation: flag disabled, skipping alert for {student_name}")
        return False

    # Markaz M1.3: ALL escalations now route through the dedicated Empire
    # Ops bot (ops_hub.py) when configured. Falls back to the legacy
    # shared TELEGRAM_ALERT_TOKEN bot only if OPS_BOT_TOKEN isn't set yet
    # (keeps this working during the migration window / on a fresh env
    # that hasn't been given an ops bot token).
    use_ops_bot = bool(config.OPS_BOT_TOKEN and config.OPS_CHAT_ID)
    token = config.OPS_BOT_TOKEN or config.TELEGRAM_ALERT_TOKEN
    chat_id = config.OPS_CHAT_ID or config.TELEGRAM_ALERT_CHAT_ID

    if not token or not chat_id:
        logger.warning("Nour escalation: no Telegram token/chat_id configured (OPS_BOT_TOKEN or TELEGRAM_ALERT_TOKEN)")
        return False

    # Build the alert message
    member = database.get_member(discord_id)
    level = member.get("level", "?") if member else "?"
    streak = member.get("current_streak", 0) if member else 0

    # Escape untrusted/dynamic text (student name + message can contain
    # raw MarkdownV2 special chars that would otherwise break Telegram's
    # parse_mode with a 400 "can't parse entities" error).
    safe_name = escape_markdown(student_name)
    safe_message = escape_markdown(student_message)
    safe_context = escape_markdown(context)

    msg = (
        f"🚨 *ESCALATION — Nour*\n\n"
        f"👤 *{safe_name}* \\(Level {level}, streak {streak}\\)\n"
        f"💬 \"{safe_message}\"\n"
    )
    if safe_context:
        msg += f"\n📋 Context: {safe_context}\n"

    # M1.4: include recent conversation history for full context, so
    # the owner doesn't have to go check Discord to understand what led
    # up to this escalation. Excludes the just-escalated message itself
    # (already shown above) to avoid duplicating it.
    history = database.get_recent_conversation(discord_id, limit=4)
    history = [h for h in history if h["message"] != student_message][-3:]
    if history:
        history_lines = []
        for h in history:
            speaker = "Student" if h["role"] == "student" else "Nour"
            history_lines.append(f"  {speaker}: \"{escape_markdown(h['message'][:150])}\"")
        msg += "\n📜 Recent conversation:\n" + "\n".join(history_lines) + "\n"

    msg += "\n💡 Reply to this message to respond as Nour\\."

    # Prefer ops_hub.send_ops_message when the dedicated ops bot is
    # configured — reuses its automatic plain-text retry fallback for
    # Markdown parse errors, rather than duplicating that logic here.
    if use_ops_bot:
        result = await ops_hub.send_ops_message(msg)
        if result:
            tg_msg_id = result.get("message_id")
            if tg_msg_id:
                _pending_escalations[tg_msg_id] = discord_id
            logger.info(f"Nour escalation sent via Empire Ops bot: {student_name}")
            return True
        logger.error(f"Nour escalation: send_ops_message failed for {student_name}")
        return False

    # Legacy path: OPS_BOT_TOKEN not configured yet, send directly via
    # the old shared TELEGRAM_ALERT_TOKEN bot. Uses MarkdownV2 (matching
    # ops_hub.PARSE_MODE) since `msg` above was already built using
    # MarkdownV2 escaping rules — sending it with legacy "Markdown"
    # would leave stray unescaped backslashes Telegram can't parse.
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": ops_hub.PARSE_MODE,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Store the telegram message ID for reply forwarding
                    tg_msg_id = data.get("result", {}).get("message_id")
                    if tg_msg_id:
                        _pending_escalations[tg_msg_id] = discord_id
                    logger.info(f"Nour escalation sent to Telegram (legacy bot): {student_name}")
                    return True
                else:
                    body = await resp.text()
                    logger.error(f"Telegram alert failed: {resp.status} — {body[:200]}")
                    return False
    except Exception as e:
        logger.error(f"Nour escalation error: {e}")
        return False


async def send_followup(discord_id: str, bot) -> bool:
    """Send a 2-hour follow-up if escalation hasn't been resolved.

    Called by a scheduled check. Tells the student Nour is still working on it.
    """
    member = database.get_member(discord_id)
    if not member:
        return False

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return False

    discord_member = guild.get_member(int(discord_id))
    if not discord_member:
        return False

    try:
        await discord_member.send(
            "لسه بتابع الموضوع ده مع الفريق 😊 هرد عليك في أقرب وقت. شكراً لصبرك! 🙏"
        )
        return True
    except Exception:
        return False
