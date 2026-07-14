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

# Characters that break Telegram's legacy Markdown parse_mode when they
# appear unescaped inside arbitrary (e.g. student-typed) text. Discovered
# while testing M0.5: a raw underscore/asterisk/backtick in the embedded
# text causes a silent 400 "can't parse entities" — the same class of bug
# as the Discord !flag list 2000-char overflow. Escape defensively so any
# future caller embedding untrusted text never has to remember this.
_MD_SPECIAL_CHARS = ["_", "*", "`", "["]


def escape_markdown(text: str) -> str:
    """Escape Telegram legacy-Markdown special characters in untrusted text.

    Use this around any user-generated/dynamic substring (student names,
    student messages, error text) before embedding it in a message sent
    with parse_mode="Markdown". Do NOT use it on the literal Markdown
    formatting you write yourself (e.g. the *bold* titles/headers).
    """
    if not text:
        return text
    for ch in _MD_SPECIAL_CHARS:
        text = text.replace(ch, f"\\{ch}")
    return text


async def send_ops_message(text: str, reply_markup: Optional[dict] = None,
                            parse_mode: str = "Markdown") -> Optional[dict]:
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
    """
    emoji = SEVERITY_EMOJI.get(severity, SEVERITY_EMOJI["info"])
    msg = f"{emoji} *{title}*\n━━━━━━━━━━━━━━━━━━━━\n\n{body}"
    return await send_ops_message(msg)
