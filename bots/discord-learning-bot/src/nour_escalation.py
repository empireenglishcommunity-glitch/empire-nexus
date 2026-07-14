"""Nour (نور) — Escalation Pipeline.

Sends Telegram alerts to the owner when Nour can't handle something.
Owner can reply via Telegram → response forwarded to student as Nour.

Gated behind 'nour_escalation' feature flag.
"""
import logging
from typing import Optional

import aiohttp

from . import config, database
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

    # Markaz M0.4: prefer the dedicated Empire Ops bot; fall back to the
    # old shared TELEGRAM_ALERT_TOKEN during migration so nothing breaks
    # if OPS_BOT_TOKEN isn't configured yet.
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
    # raw Markdown special chars like _ or * that would otherwise break
    # Telegram's parse_mode="Markdown" with a silent 400 error).
    safe_name = escape_markdown(student_name)
    safe_message = escape_markdown(student_message)
    safe_context = escape_markdown(context)

    msg = (
        f"🚨 *ESCALATION — Nour*\n\n"
        f"👤 *{safe_name}* (Level {level}, streak {streak})\n"
        f"💬 \"{safe_message}\"\n"
    )
    if safe_context:
        msg += f"\n📋 Context: {safe_context}\n"
    msg += f"\n💡 Reply to this message to respond as Nour."

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "Markdown",
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
                    logger.info(f"Nour escalation sent to Telegram: {student_name}")
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
