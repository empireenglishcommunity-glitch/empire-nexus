"""Maintenance mode — the single source of truth for system status.

Backed by the `settings` table (survives restarts; shared by the bot, the
practice-page API `/api/status`, and the ops `/maintenance` command). See
`.kiro/specs/maintenance-mode-2026-07/`.

States:
- live         — normal operation
- maintenance  — level "soft" (dismissible banner, page usable) or
                 "hard" (full-screen overlay, page not usable)

A failsafe auto-resume window guarantees students are never left locked out
if `end` is forgotten: once the auto-end time passes, get_status() reports
`live` and lazily clears the flag.
"""
import datetime
import logging
from typing import Optional

from . import database

logger = logging.getLogger("empire-bot.maintenance")

VALID_LEVELS = ("soft", "hard")
DEFAULT_WINDOW_MINUTES = 120  # R6.1 auto-resume failsafe


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _parse_iso(s: str) -> Optional[datetime.datetime]:
    try:
        dt = datetime.datetime.fromisoformat(s)
        return dt.replace(tzinfo=datetime.timezone.utc) if dt.tzinfo is None else dt
    except (ValueError, TypeError):
        return None


def is_active() -> bool:
    """True only if maintenance is on AND the auto-resume window hasn't elapsed."""
    return get_status()["state"] == "maintenance"


def get_status() -> dict:
    """Return the current system status dict.

    Honors the auto-resume failsafe: if the stored auto-end time has passed,
    report `live` and lazily clear the stored flag so it doesn't linger.
    """
    active = database.get_setting("maintenance_active", "0") == "1"
    # Legacy/unified: deploy.py and the old !maintenance command set
    # `maintenance_mode` on|off before/after a deploy. Honor it so a deploy
    # window also shows the page banner + bot presence, one source of truth.
    legacy = database.get_setting("maintenance_mode", "off") == "on"
    if not (active or legacy):
        return {"state": "live"}

    auto_end = _parse_iso(database.get_setting("maintenance_auto_end_at", ""))
    if auto_end and _now_utc() >= auto_end:
        try:
            _clear()
        except Exception:
            pass
        return {"state": "live", "auto_ended": True}

    level = database.get_setting("maintenance_level", "soft")
    if level not in VALID_LEVELS:
        level = "soft"
    return {
        "state": "maintenance",
        "level": level,
        "reason": database.get_setting("maintenance_reason", ""),
        "message": database.get_setting("maintenance_message", ""),
        "eta": database.get_setting("maintenance_eta", ""),
        "started_at": database.get_setting("maintenance_started_at", ""),
    }


def start(level: str = "soft", reason: str = "", eta: str = "",
          message: str = "", window_minutes: int = DEFAULT_WINDOW_MINUTES) -> dict:
    """Enter maintenance mode. Returns the resulting status."""
    level = level if level in VALID_LEVELS else "soft"
    now = _now_utc()
    window = window_minutes if (isinstance(window_minutes, int) and window_minutes > 0) else DEFAULT_WINDOW_MINUTES
    auto_end = now + datetime.timedelta(minutes=window)
    database.set_setting("maintenance_active", "1")
    database.set_setting("maintenance_mode", "on")  # keep legacy key in sync
    database.set_setting("maintenance_level", level)
    database.set_setting("maintenance_reason", reason or "")
    database.set_setting("maintenance_message", message or "")
    database.set_setting("maintenance_eta", eta or "")
    database.set_setting("maintenance_started_at", now.isoformat())
    database.set_setting("maintenance_auto_end_at", auto_end.isoformat())
    logger.info(
        f"maintenance START level={level} reason={reason!r} eta={eta!r} "
        f"auto_end={auto_end.isoformat()}"
    )
    return get_status()


def end() -> dict:
    """Exit maintenance mode. Returns the resulting status."""
    _clear()
    logger.info("maintenance END")
    return {"state": "live"}


def _clear() -> None:
    database.set_setting("maintenance_active", "0")
    database.set_setting("maintenance_mode", "off")  # keep legacy key in sync
    # Descriptive fields are left as-is; they're ignored while inactive and
    # overwritten on the next start().



# ============================================================
#  Phase 2 — student broadcast (Discord #announcements + Telegram
#  groups) + bot presence. Called by the /maintenance command.
# ============================================================

from . import config  # noqa: E402  (kept local to this section)

PRESENCE_TEXT = "🔧 Under maintenance — back soon"
ANNOUNCE_CHANNEL = "announcements"


def start_message(status: dict) -> str:
    """Bilingual 'we're doing maintenance' notice for students."""
    hard = status.get("level") == "hard"
    reason = status.get("message") or status.get("reason") or ""
    eta = status.get("eta") or ""
    head = ("🔧 **Quick maintenance in progress**" if hard
            else "🔧 **Minor updates in progress**")
    lines = [head]
    if hard:
        lines.append("The practice page is briefly paused while we ship an "
                     "improvement. We'll be right back.")
    else:
        lines.append("You can keep practicing — you might see small glitches "
                     "for a few minutes.")
    if reason:
        lines.append(f"• {reason}")
    # No ETA / promised time on purpose: maintenance "might take minutes, maybe
    # longer", so we never commit to a duration in the student-facing notice.
    # The minutes passed to /maintenance still drive the silent auto-resume
    # failsafe window; students just never see a promised time.
    lines.append("🔒 Your streak & progress are 100% safe.")
    lines.append("")
    lines.append("— — —")
    lines.append("🔧 **صيانة سريعة**")
    lines.append("إحنا بنطوّر حاجة بسيطة دلوقتي" +
                 ("، والصفحة متوقفة لحظات وهنرجع حالًا." if hard
                  else "، تقدر تكمّل تمرينك عادي."))
    lines.append("🔒 تقدّمك وسلسلة أيامك محفوظة بالكامل.")
    return "\n".join(lines)


def end_message(changelog: str = "") -> str:
    """Bilingual 'we're back + what's new' notice for students."""
    lines = [
        "✅ **We're back online!**",
        "Thanks for your patience 🙏",
    ]
    if changelog:
        lines.append("")
        lines.append("✨ **What's new:**")
        lines.append(changelog)
    lines.append("🔒 Your streak & progress are exactly where you left them.")
    lines.append("")
    lines.append("— — —")
    lines.append("✅ **رجعنا اشتغلنا تاني!**")
    lines.append("شكرًا لصبرك 🙏 تقدّمك وسلسلة أيامك زي ما هي.")
    return "\n".join(lines)


async def _send_discord_announcement(bot, text: str) -> bool:
    """Post to the guild's #announcements channel. Returns True on success."""
    try:
        import discord  # local import: keeps pure-logic funcs import-light
        guild = bot.get_guild(config.GUILD_ID) if config.GUILD_ID else None
        if not guild:
            return False
        channel = discord.utils.get(guild.text_channels, name=ANNOUNCE_CHANNEL)
        if not channel:
            logger.warning("maintenance: #%s channel not found", ANNOUNCE_CHANNEL)
            return False
        await channel.send(text)
        return True
    except Exception as e:
        logger.warning(f"maintenance: Discord announcement failed: {e}")
        return False


async def _send_telegram_groups(text: str) -> int:
    """Post to each configured student Telegram group. Returns count sent.
    Skips gracefully if no group IDs / no bot token are configured."""
    chat_ids = getattr(config, "MAINTENANCE_TG_CHAT_IDS", []) or []
    if not chat_ids or not config.OPS_BOT_TOKEN:
        return 0
    import aiohttp
    url = f"https://api.telegram.org/bot{config.OPS_BOT_TOKEN}/sendMessage"
    sent = 0
    try:
        async with aiohttp.ClientSession() as session:
            for cid in chat_ids:
                try:
                    # Plain text (no parse_mode) — student-facing content,
                    # avoids Markdown-escaping pitfalls.
                    async with session.post(
                        url, json={"chat_id": cid, "text": text},
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status == 200:
                            sent += 1
                        else:
                            body = await resp.text()
                            logger.warning(
                                f"maintenance: TG send to {cid} failed "
                                f"{resp.status}: {body[:150]}")
                except Exception as e:
                    logger.warning(f"maintenance: TG send to {cid} error: {e}")
    except Exception as e:
        logger.warning(f"maintenance: TG broadcast error: {e}")
    return sent


async def _set_presence(bot, active: bool) -> None:
    try:
        import discord
        if active:
            await bot.change_presence(
                status=discord.Status.idle,
                activity=discord.CustomActivity(name=PRESENCE_TEXT))
        else:
            await bot.change_presence(status=discord.Status.online, activity=None)
    except Exception as e:
        logger.warning(f"maintenance: set presence failed: {e}")


async def broadcast_start(bot, status: dict) -> dict:
    """Announce maintenance start to students + set bot presence."""
    msg = start_message(status)
    discord_ok = await _send_discord_announcement(bot, msg)
    tg_sent = await _send_telegram_groups(msg)
    await _set_presence(bot, True)
    return {"discord": discord_ok, "telegram_groups": tg_sent}


async def broadcast_end(bot, changelog: str = "") -> dict:
    """Announce 'we're back' to students + restore bot presence."""
    msg = end_message(changelog)
    discord_ok = await _send_discord_announcement(bot, msg)
    tg_sent = await _send_telegram_groups(msg)
    await _set_presence(bot, False)
    return {"discord": discord_ok, "telegram_groups": tg_sent}
