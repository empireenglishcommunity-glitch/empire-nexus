"""Nour (نور) — Escalation Pipeline.

Sends Telegram alerts to the owner when Nour can't handle something.
Owner can reply via Telegram → response forwarded to student as Nour.

Gated behind 'nour_escalation' feature flag.
"""
import logging
from typing import Optional

import aiohttp
import discord

from . import config, database, ops_hub
from .ops_hub import escape_markdown

logger = logging.getLogger("empire-bot.nour.escalation")

# Markaz M2: escalation → discord_id mapping is now persisted in the
# database (database.pending_escalations table) rather than kept only
# in this in-memory dict. An in-memory-only map meant any escalation
# the owner hadn't replied to yet would become permanently unmatchable
# after a restart/redeploy — a real gap, since a redeploy can happen at
# any time relative to when the owner gets around to replying. Kept as
# a thin in-memory cache is unnecessary now; all reads/writes go
# through database.py so ops_poller.py (M2) sees the same state.


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
                database.record_pending_escalation(tg_msg_id, discord_id, student_name)
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
                        database.record_pending_escalation(tg_msg_id, discord_id, student_name)
                    logger.info(f"Nour escalation sent to Telegram (legacy bot): {student_name}")
                    return True
                else:
                    body = await resp.text()
                    logger.error(f"Telegram alert failed: {resp.status} — {body[:200]}")
                    return False
    except Exception as e:
        logger.error(f"Nour escalation error: {e}")
        return False


async def forward_reply_to_student(discord_id: str, reply_text: str, bot) -> bool:
    """Markaz M2.2 — deliver the owner's Telegram reply to the student
    as a DM "from Nour" on Discord.

    Returns True if the DM was delivered, False otherwise (e.g. the
    student has DMs disabled, left the server, or the guild/member
    can't be found). Never raises.
    """
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        logger.error("Nour escalation reply: guild not found")
        return False

    try:
        discord_member = guild.get_member(int(discord_id))
    except (ValueError, TypeError):
        discord_member = None

    if not discord_member:
        logger.warning(f"Nour escalation reply: member {discord_id} not found in guild")
        return False

    try:
        await discord_member.send(reply_text)
    except discord.Forbidden:
        logger.warning(f"Nour escalation reply: DMs disabled for {discord_id}")
        return False
    except Exception as e:
        logger.error(f"Nour escalation reply: failed to DM {discord_id}: {e}")
        return False

    # The DM succeeded — this is a delivered reply regardless of what
    # happens next. Storing it in conversation history is best-effort
    # bookkeeping, not part of "did the student receive the message?".
    # Deliberately a SEPARATE try/except from the send() above: an
    # earlier version wrapped both in one block, so a history-storage
    # failure (e.g. a FOREIGN KEY error if the member row is somehow
    # missing) got misreported as "delivery failed" even though the
    # student's DM had already gone through — found via live testing.
    try:
        _store_reply_in_history(discord_id, reply_text)
    except Exception as e:
        logger.error(f"Nour escalation reply: DM delivered but failed to store history for {discord_id}: {e}")

    return True


def _store_reply_in_history(discord_id: str, reply_text: str) -> None:
    """Store the owner's (as-Nour) reply in nour_conversations, so it
    shows up in future conversation history / escalation context same
    as any other Nour message."""
    conn = database._connect()
    # try/finally is required here, not optional style — found via live
    # testing that a raised exception inside execute() (e.g. a FOREIGN
    # KEY failure) skipped conn.close() entirely, leaking an open
    # connection with a dangling transaction that then locked the
    # database file ("database is locked") for every subsequent
    # operation, including the caller's own resolve_pending_escalation()
    # call a moment later. This is exactly the kind of bug that only
    # shows up in production under real failure conditions, not in a
    # happy-path test.
    try:
        conn.execute(
            """INSERT INTO nour_conversations (discord_id, role, message, intent)
               VALUES (?, 'nour', ?, 'owner_reply')""",
            (discord_id, reply_text[:500]),
        )
        conn.commit()
    finally:
        conn.close()


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
