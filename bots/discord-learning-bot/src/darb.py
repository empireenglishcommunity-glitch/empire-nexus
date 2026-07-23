"""Darb (درب) — gated personal practice experience: session + calendar logic.

Phase 1 backend foundation. This module holds the non-DB logic:
  * HMAC-signed device session tokens (mint/verify) — stateless crypto
    the Cloudflare Pages edge gate (Phase 3) will mirror.
  * `claim()` — the orchestration for turning a one-time claim code into
    a durable device session (consume code → create session → enforce
    the 2-device cap → mint token → alert owner on eviction).
  * `build_calendar()` — the personal, join-date-anchored calendar the
    practice page renders (Phase 2), server-computed so the browser
    never guesses dates or "today".

Everything here is inert until the Darb API endpoints (api_server.py)
and the practice-page UI (Phases 2-3) call it. DB access goes through
`database` (the tables live there); this module never opens its own
connection.
"""
import base64
import datetime
import hashlib
import hmac
import json
import logging
import secrets
import time

from . import config, database

logger = logging.getLogger("empire-bot.darb")

# ============================================================
#  CONSTANTS
# ============================================================

DEVICE_CAP = 2               # max active web sessions per student
SESSION_TTL_DAYS = 60        # signed-token lifetime (durable; re-link if lost)
CLAIM_TTL_MINUTES = 15       # one-time claim code lifetime

# Mastery tier names (index = completion_count). 0 = not started.
TIER_NAMES = {
    0: "none",
    1: "bronze",
    2: "silver",
    3: "gold",
    4: "platinum",
    5: "diamond",
}


# ============================================================
#  SIGNED SESSION TOKENS (HMAC-SHA256; verified at the edge in Phase 3)
# ============================================================
#
# Token format:  base64url(payload_json) + "." + base64url(hmac_sha256)
# payload: {"did": discord_id, "lvl": level, "sid": device_id,
#           "iat": issued_epoch, "exp": expiry_epoch}
# The secret (config.DARB_SESSION_SECRET) lives only in the server .env
# and the Cloudflare Pages env — never in git. Empty secret = fail-safe
# (no token can be minted or verified).

def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(body: str) -> str:
    secret = (config.DARB_SESSION_SECRET or "").encode()
    return _b64e(hmac.new(secret, body.encode(), hashlib.sha256).digest())


def mint_session(discord_id: str, level: str, device_id: str,
                 ttl_days: int = SESSION_TTL_DAYS) -> str:
    """Create a signed session token. Raises if the secret isn't set."""
    if not config.DARB_SESSION_SECRET:
        raise RuntimeError("DARB_SESSION_SECRET is not set — cannot mint sessions")
    now = int(time.time())
    payload = {
        "did": discord_id,
        "lvl": level,
        "sid": device_id,
        "iat": now,
        "exp": now + ttl_days * 86400,
    }
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    return f"{body}.{_sign(body)}"


def verify_session(token: str) -> dict | None:
    """Verify a session token's signature + expiry. Returns the payload
    dict (did/lvl/sid/iat/exp) if valid, else None. Does NOT check
    revocation — that's a DB lookup the caller does via
    `database.is_device_session_active(payload['sid'])`."""
    if not token or not config.DARB_SESSION_SECRET:
        return None
    try:
        body, sig = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(body)):
        return None
    try:
        payload = json.loads(_b64d(body))
    except Exception:
        return None
    try:
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
    except (TypeError, ValueError):
        return None
    return payload


# ============================================================
#  CLAIM ORCHESTRATION (Flow A)
# ============================================================

async def claim(code: str, ip: str = "", user_agent: str = "") -> dict | None:
    """Turn a one-time claim code into a durable device session.

    Returns {token, level, device_id, name} on success, None if the code
    is invalid/expired/consumed or the member no longer exists. Enforces
    the 2-device cap (revokes the oldest beyond it) and alerts the owner
    when a session is evicted (possible sharing).
    """
    discord_id = database.consume_claim_code(code)
    if not discord_id:
        return None
    member = database.get_member(discord_id)
    if not member:
        return None
    level = member.get("level", "L0")

    device_id = secrets.token_urlsafe(12)
    database.create_device_session(discord_id, device_id, ip=ip, user_agent=user_agent)
    revoked = database.enforce_device_cap(discord_id, DEVICE_CAP)
    if revoked:
        await _alert_owner_device_cap(member, discord_id, len(revoked), ip)

    token = mint_session(discord_id, level, device_id)
    logger.info(
        "Darb claim: %s (%s) new device session (%d evicted)",
        member.get("discord_name", "?"), discord_id, len(revoked),
    )
    return {
        "token": token,
        "level": level,
        "device_id": device_id,
        "name": member.get("discord_name", ""),
    }


async def _alert_owner_device_cap(member: dict, discord_id: str,
                                  evicted: int, ip: str) -> None:
    """Best-effort Telegram alert when the device cap evicts a session."""
    try:
        from . import ops_hub
        await ops_hub.send_ops_alert(
            "Darb — device cap exceeded",
            f"{member.get('discord_name', '?')} ({discord_id}) claimed a new "
            f"device from IP {ip or 'unknown'}; {evicted} oldest session(s) "
            f"revoked (cap {DEVICE_CAP}). Possible account sharing — "
            f"investigate and revoke if needed.",
            severity="warning",
        )
    except Exception as e:  # never let an alert failure break a claim
        logger.warning("Darb: owner device-cap alert failed: %s", e)


# ============================================================
#  PERSONAL CALENDAR (Flow / R7) — server-computed, join-anchored
# ============================================================

def _today_local() -> datetime.date:
    """Today in the bot's configured timezone (Asia/Dubai), so the
    calendar and the bot never disagree about what 'today' is."""
    try:
        from zoneinfo import ZoneInfo
        tz = getattr(config, "TIMEZONE", "Asia/Dubai") or "Asia/Dubai"
        return datetime.datetime.now(ZoneInfo(tz)).date()
    except Exception:
        return datetime.date.today()


def today_week_day(discord_id: str) -> tuple[int, int] | None:
    """Return the student's current calendar (week, day) based on their
    join date. Returns None if member unknown or past the level's end.

    Used by the `!done` command handler to record mastery for the correct
    content-day without the student having to specify week/day explicitly.
    """
    from . import curriculum

    member = database.get_member(discord_id)
    if not member:
        return None
    level = member.get("level", "L0")

    # Darb Phase 6: anchor to the current level's start (falls back to
    # joined_at for un-promoted students), so a promoted student's day
    # counter restarts for the new level.
    join_raw = database.level_anchor_iso(member)
    try:
        join_date = datetime.date.fromisoformat(join_raw[:10])
    except (ValueError, TypeError):
        join_date = datetime.date.today()

    today = _today_local()
    today_index = max(1, (today - join_date).days + 1)

    max_week = curriculum.max_week_for_level(level)
    total_days = max_week * 7
    if today_index > total_days:
        return None  # level complete

    week = (today_index - 1) // 7 + 1
    day = (today_index - 1) % 7 + 1
    return (week, day)


def build_calendar(discord_id: str) -> dict | None:
    """Build the student's personal calendar (their level only), anchored
    to their join date. Day 1 = join date. Returns None if unknown member.

    Each day: {index, date, week, day, state, day_tier, exercises}.
    state ∈ done | today | locked | missed. Future days are locked;
    past-not-done days are 'missed' (catch-up, still openable). Completed
    days are 'done' (green) permanently.
    """
    from . import curriculum

    member = database.get_member(discord_id)
    if not member:
        return None
    level = member.get("level", "L0")

    # Darb Phase 6: anchor to the current level's start (falls back to
    # joined_at for un-promoted students).
    join_raw = database.level_anchor_iso(member)
    try:
        join_date = datetime.date.fromisoformat(join_raw[:10])
    except (ValueError, TypeError):
        join_date = datetime.date.today()

    today = _today_local()
    today_index = max(1, (today - join_date).days + 1)

    max_week = curriculum.max_week_for_level(level)
    total_days = max_week * 7
    mastery = database.get_calendar_mastery(discord_id, level)

    days = []
    for d in range(1, total_days + 1):
        d_date = join_date + datetime.timedelta(days=d - 1)
        week = (d - 1) // 7 + 1
        day = (d - 1) % 7 + 1
        m = mastery.get((week, day))
        done = bool(m and m["done"])
        if done:
            state = "done"
        elif d > today_index:
            state = "locked"
        elif d == today_index:
            state = "today"
        else:
            state = "missed"
        days.append({
            "index": d,
            "date": d_date.isoformat(),
            "week": week,
            "day": day,
            "state": state,
            "day_tier": (m["day_tier"] if m else 0),
            "exercises": (m["exercises"] if m else {ex: 0 for ex in database.PRACTICE_EXERCISES}),
        })

    return {
        "level": level,
        "join_date": join_date.isoformat(),
        "today_index": today_index,
        "level_total_days": total_days,
        "level_complete": today_index > total_days,
        "tier_names": TIER_NAMES,
        "days": days,
    }
