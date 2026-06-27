"""Optional Telegram notifications for bot lifecycle events.

Sends a short message to your Telegram when the bot starts, stops, or crashes.
Completely optional — if TELEGRAM_ALERT_TOKEN or TELEGRAM_ALERT_CHAT_ID are not
set, all functions silently do nothing.

Uses only Python stdlib (urllib) — no extra dependencies.
"""
import json
import logging
import urllib.request
import urllib.error
from . import config

logger = logging.getLogger("empire-challenge-bot")


def _enabled() -> bool:
    return bool(config.TELEGRAM_ALERT_TOKEN and config.TELEGRAM_ALERT_CHAT_ID)


def send(message: str):
    """Send a Telegram message to the admin. Fails silently on any error."""
    if not _enabled():
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_ALERT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": config.TELEGRAM_ALERT_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.debug(f"Telegram alert failed (non-critical): {e}")


def bot_online():
    """Notify that the bot has started successfully."""
    send(f"✅ *Challenge Bot Online*\nVersion: `{config.BOT_VERSION}`")


def bot_offline(reason: str = "unknown"):
    """Notify that the bot is shutting down."""
    send(f"🔴 *Challenge Bot Stopped*\nReason: {reason}")
