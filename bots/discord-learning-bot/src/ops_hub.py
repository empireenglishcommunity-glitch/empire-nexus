"""Markaz (مركز) — Telegram Operations Hub.

A dedicated Telegram bot (@empire_ops_eec_bot, "Empire Ops") for
owner-facing operational messages: escalations, daily/weekly digests,
system health, and quick actions. Separate from any student-facing
or generic alert bot — see .kiro/specs/telegram-operations-hub/.

Phase M0: core messaging only (send_ops_message, send_ops_alert).
Later phases (M1-M5) add digests, reply forwarding, and commands.
"""
import logging
from typing import Optional

import aiohttp

from . import config

logger = logging.getLogger("empire-bot.ops_hub")

SEVERITY_EMOJI = {
    "info": "ℹ️",
    "success": "✅",
    "warning": "⚠️",
    "critical": "🚨",
}

# Markaz M0/M1 bug (found during live testing, confirmed against Telegram's
# own API docs at core.telegram.org/bots/api#markdown-style): legacy
# parse_mode="Markdown" does NOT reliably support escaping all its own
# special characters — a backslash-escaped '*' (e.g. "Ahmed\*Test") still
# raises a 400 "can't parse entities" even though '_' escapes fine. Verified
# directly against the live Bot API. The docs are explicit that legacy
# Markdown entities "must not be nested" and recommend MarkdownV2 instead.
#
# Fix: use MarkdownV2 everywhere, which has a complete, well-defined
# escaping rule (straight from the Bot API docs' "MarkdownV2 style"
# section): "In all other places characters '_', '*', '[', ']', '(', ')',
# '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!' must be
# escaped with the preceding character '\'."
PARSE_MODE = "MarkdownV2"
_MD_SPECIAL_CHARS = list("_*[]()~`>#+-=|{}.!")


def escape_markdown(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters in untrusted text.

    Use this around any user-generated/dynamic substring (student names,
    student messages, error text) before embedding it in a message sent
    with parse_mode="MarkdownV2". Do NOT use it on the literal Markdown
    formatting you write yourself (e.g. the *bold* titles/headers) —
    those characters are meant to be parsed as formatting, not escaped.
    """
    if not text:
        return text
    # Escape backslash first, so we don't double-escape the backslashes
    # we're about to introduce for the other special characters.
    text = text.replace("\\", "\\\\")
    for ch in _MD_SPECIAL_CHARS:
        text = text.replace(ch, f"\\{ch}")
    return text


async def send_ops_message(text: str, reply_markup: Optional[dict] = None,
                            parse_mode: str = PARSE_MODE) -> Optional[dict]:
    """Send a message to the owner via the Empire Ops bot.

    Returns the Telegram API 'result' dict on success (includes
    message_id, useful for later reply-forwarding), or None on any
    failure. Never raises — a failed Telegram send must never crash
    the Discord bot.
    """
    if not config.OPS_BOT_TOKEN or not config.OPS_CHAT_ID:
        logger.warning("ops_hub: OPS_BOT_TOKEN or OPS_CHAT_ID not set, skipping message")
        return None

    url = f"https://api.telegram.org/bot{config.OPS_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.OPS_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload,
                                     timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("result")
                body = await resp.text()
                logger.error(f"ops_hub: sendMessage failed: {resp.status} — {body[:200]}")

                # Defensive fallback: a Markdown parse failure (bad entities
                # from unescaped user text) must never mean the alert is
                # lost entirely — retry once as plain text.
                if parse_mode and "can't parse entities" in body:
                    logger.warning("ops_hub: retrying send as plain text after Markdown parse failure")
                    plain_payload = {"chat_id": config.OPS_CHAT_ID, "text": text}
                    if reply_markup:
                        plain_payload["reply_markup"] = reply_markup
                    async with session.post(url, json=plain_payload,
                                             timeout=aiohttp.ClientTimeout(total=10)) as retry_resp:
                        if retry_resp.status == 200:
                            data = await retry_resp.json()
                            return data.get("result")
                        retry_body = await retry_resp.text()
                        logger.error(f"ops_hub: plain-text retry also failed: {retry_resp.status} — {retry_body[:200]}")
                return None
    except Exception as e:
        logger.error(f"ops_hub: send_ops_message error: {e}")
        return None


async def send_ops_alert(title: str, body: str, severity: str = "info") -> Optional[dict]:
    """Send a formatted alert to the owner.

    severity: one of "info", "success", "warning", "critical" — controls
    the leading emoji. Unknown severities fall back to "info".

    title/body are treated as plain, untrusted free text and are escaped
    automatically (MarkdownV2 requires escaping literal punctuation like
    '.', '!', '-', '(', ')' even in text the caller writes themselves).
    If a caller ever needs literal Markdown formatting *inside* body,
    build the message with send_ops_message() directly instead.
    """
    emoji = SEVERITY_EMOJI.get(severity, SEVERITY_EMOJI["info"])
    safe_title = escape_markdown(title)
    safe_body = escape_markdown(body)
    msg = f"{emoji} *{safe_title}*\n━━━━━━━━━━━━━━━━━━━━\n\n{safe_body}"
    return await send_ops_message(msg)
