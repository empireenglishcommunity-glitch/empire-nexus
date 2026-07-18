"""Nour (نور) — Onboarding Intelligence.

Detects confused new students and helps them via DM:
- Wrong channel usage (command in wrong channel)
- Command typos (e.g. "done" without "!")
- Student hasn't completed first task after 48h
- Not onboarded after 3 days (step-by-step walkthrough)

This runs inline in on_message (not scheduled) — catches confusion
in real-time before students give up.
"""
import datetime
import logging
from typing import Optional

import discord

from . import config, database

logger = logging.getLogger("empire-bot.nour.onboarding")

# Track which students we've already helped today (prevent spam)
_helped_today: dict[str, str] = {}  # discord_id → last help type


def _is_new_student(member_data: dict) -> bool:
    """Check if student joined within the last 48 hours."""
    joined = member_data.get("joined_at", "")
    if not joined:
        return False
    try:
        joined_dt = datetime.datetime.fromisoformat(joined.replace("Z", ""))
        hours = (datetime.datetime.now() - joined_dt).total_seconds() / 3600
        return hours <= 48
    except (ValueError, TypeError):
        return False


def _already_helped(discord_id: str, help_type: str) -> bool:
    """Check if we already helped this student with this issue today."""
    key = f"{discord_id}:{help_type}"
    today = datetime.date.today().isoformat()
    return _helped_today.get(key) == today


def _mark_helped(discord_id: str, help_type: str):
    """Mark that we helped this student with this issue today."""
    key = f"{discord_id}:{help_type}"
    _helped_today[key] = datetime.date.today().isoformat()


async def check_wrong_channel(message: discord.Message) -> bool:
    """Detect if a student typed a command in the wrong channel.

    If they typed a command (starts with !) in a channel that's NOT
    #bot-commands, gently redirect them via DM.

    Returns True if we handled it (caller should not process further).
    """
    # Only check guild messages (not DMs)
    if not hasattr(message.channel, 'name'):
        return False

    # Only check commands
    if not message.content.startswith(config.BOT_PREFIX):
        return False

    # These channels are fine for commands
    allowed_channels = {"bot-commands", "ask-nour"}
    if message.channel.name in allowed_channels:
        return False

    discord_id = str(message.author.id)
    member_data = database.get_member(discord_id)
    if not member_data:
        return False

    # Only help new students (experienced ones know better)
    if not _is_new_student(member_data):
        return False

    if _already_helped(discord_id, "wrong_channel"):
        return False

    # Send gentle redirect via DM
    try:
        name = member_data.get("discord_name", "").split("#")[0] or message.author.display_name
        await message.author.send(
            f"👋 مرحبًا {name}!\n\n"
            f"الأوامر تعمل فقط في قناة `#bot-commands`.\n"
            f"اذهب إلى هناك واكتب الأمر مرة أخرى وسيعمل معك 👍\n\n"
            f"إذا احتجت مساعدة في أي شيء، أرسل لي هنا أو اكتب في `#ask-nour` 😊"
        )
        _mark_helped(discord_id, "wrong_channel")
        logger.info(f"Nour onboarding: redirected {name} from #{message.channel.name} to #bot-commands")
    except (discord.Forbidden, discord.HTTPException):
        pass

    return False  # Don't block command processing — let it fail naturally with an error


async def check_command_typo(message: discord.Message) -> bool:
    """Detect common command typos and help via DM.

    Catches things like:
    - "done accent" (missing !)
    - "!تم" in a non-command channel
    - "done" alone (missing task name)

    Returns True if we helped (prevents duplicate handling).
    """
    if not hasattr(message.channel, 'name'):
        return False

    text = message.content.strip().lower()
    discord_id = str(message.author.id)

    # Check if it looks like a command attempt without !
    command_attempts = ["done", "تم", "progress", "تقدم", "help", "مساعدة", "streak", "سلسلة"]
    is_attempt = any(text == cmd or text.startswith(f"{cmd} ") for cmd in command_attempts)

    if not is_attempt:
        return False

    member_data = database.get_member(discord_id)
    if not member_data:
        return False

    if not _is_new_student(member_data):
        return False

    if _already_helped(discord_id, "command_typo"):
        return False

    # Send help via DM
    try:
        name = member_data.get("discord_name", "").split("#")[0] or message.author.display_name
        correct_command = f"!{text.split()[0]}" if text.split() else "!done"
        await message.author.send(
            f"💡 {name}، يبدو أنك تريد كتابة أمر!\n\n"
            f"الأوامر يجب أن تبدأ بعلامة `!` — أي اكتب `{correct_command}` وليس `{text.split()[0]}`\n\n"
            f"جرّب في `#bot-commands`:\n"
            f"```\n!done accent\n```\n"
            f"أو اكتب `!مساعدة` إذا أردت رؤية جميع الأوامر 😊"
        )
        _mark_helped(discord_id, "command_typo")
        logger.info(f"Nour onboarding: helped {name} with command typo '{text[:20]}'")
    except (discord.Forbidden, discord.HTTPException):
        pass

    return False  # Don't block message processing
