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
    if not active:
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
    # Descriptive fields are left as-is; they're ignored while inactive and
    # overwritten on the next start().
