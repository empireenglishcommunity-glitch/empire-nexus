"""Community Lounge ("Majlis") — the brain for task #7 social features.

Phase 0 skeleton: channel identity helpers, occupancy queries, and config
accessors. Pure/unit-testable where possible (no Discord API calls in the
helpers themselves — those live in bot.py wiring).

Later phases add:
- Phase 1: together-time accrual + company-aware verify_community OR path
- Phase 2: beacon lifecycle (maybe_beacon / clear_beacon)
- Phase 3: dynamic room creation + reaping
- Phase 4: opt-in pings + Knock
- Phase 5: Community Hour loop
- Phase 6: together reward
- Phase 7: owner controls + rollout
"""
import json
import logging
from typing import Optional

from . import database

logger = logging.getLogger("empire-bot.community")

# ============================================================
#  CONSTANTS
# ============================================================

# The permanent anchor lounge (never deleted, always treated as a Majlis).
# Matched by channel name since there's no config constant for its ID.
MAJLIS_ANCHOR_NAME = "voice-lounge"

# Settings key for the dynamic-rooms registry (list of channel IDs the bot
# created). Stored as JSON in `settings`.
_MAJLIS_ROOMS_KEY = "majlis_rooms"


# ============================================================
#  CHANNEL IDENTITY
# ============================================================

def is_majlis_channel(channel) -> bool:
    """Return True if `channel` is a Majlis lounge (the permanent anchor OR
    any dynamically created overflow room).

    Works with both a Discord VoiceChannel object (has `.name` and `.id`) and
    a plain dict/mock with the same keys — so it's unit-testable without
    Discord.
    """
    # The anchor is identified by name (always present in the guild).
    name = getattr(channel, "name", None) or ""
    if name == MAJLIS_ANCHOR_NAME:
        return True

    # Dynamic rooms are registered by ID in settings.
    channel_id = str(getattr(channel, "id", "") or "")
    if not channel_id:
        return False
    return channel_id in get_majlis_room_ids()


def get_majlis_room_ids() -> set[str]:
    """Return the set of channel IDs for bot-created dynamic Majlis rooms.
    The anchor is NOT included here (it's identified by name)."""
    raw = database.get_setting(_MAJLIS_ROOMS_KEY, "[]")
    try:
        ids = json.loads(raw)
        if isinstance(ids, list):
            return {str(i) for i in ids}
    except (json.JSONDecodeError, TypeError):
        pass
    return set()


def register_majlis_room(channel_id: str) -> None:
    """Add a dynamically created lounge to the registry (Phase 3)."""
    ids = get_majlis_room_ids()
    ids.add(str(channel_id))
    database.set_setting(_MAJLIS_ROOMS_KEY, json.dumps(sorted(ids)))


def unregister_majlis_room(channel_id: str) -> None:
    """Remove a reaped lounge from the registry (Phase 3)."""
    ids = get_majlis_room_ids()
    ids.discard(str(channel_id))
    database.set_setting(_MAJLIS_ROOMS_KEY, json.dumps(sorted(ids)))


# ============================================================
#  OCCUPANCY
# ============================================================

def lounge_occupancy(guild) -> dict[str, list[str]]:
    """Return {channel_id: [member_ids]} for all Majlis lounges with at
    least one non-bot member present.

    Reads from the guild's cached voice states (gateway data, no API call).
    Requires a real discord.Guild object — not unit-testable in isolation,
    but the callers (bot.py wiring) pass it. Phase 2+ uses this for beacon
    decisions and load-balancing.
    """
    result: dict[str, list[str]] = {}
    for vc in guild.voice_channels:
        if not is_majlis_channel(vc):
            continue
        members = [str(m.id) for m in vc.members if not m.bot]
        if members:
            result[str(vc.id)] = members
    return result


def is_member_in_majlis_with_company(guild, discord_id: str) -> bool:
    """Return True if `discord_id` is currently in a Majlis lounge AND at
    least one other non-bot member is also present in the same lounge.
    Used by together-time accrual (Phase 1)."""
    occ = lounge_occupancy(guild)
    for _ch_id, member_ids in occ.items():
        if discord_id in member_ids and len(member_ids) >= 2:
            return True
    return False


# ============================================================
#  CONFIG ACCESSORS (convenience wrappers)
# ============================================================

def get_config() -> dict:
    """Shorthand for database.get_community_config()."""
    return database.get_community_config()


def get_together_minutes_threshold() -> int:
    """The number of together-minutes needed for the fast #7 path."""
    return get_config().get("community_together_minutes", 5)


def get_lounge_capacity() -> int:
    """Hard cap per Majlis lounge."""
    return get_config().get("community_lounge_capacity", 6)


def get_beacon_max_occupancy() -> int:
    """Beacon only fires when lounge occupancy ≤ this."""
    return get_config().get("community_beacon_max_occupancy", 4)


# ============================================================
#  BEACON LIFECYCLE (Phase 2)
# ============================================================
#
# A "beacon" is a short, self-cleaning message posted to #community-live
# when someone is waiting in a mostly-empty Majlis lounge. It:
#   - Fires only when occupancy is in [1, beacon_max_occupancy] ("lonely/lively")
#   - Does NOT fire when the room is healthy (≥ beacon_max_occupancy) — no spam
#   - Does NOT address the person who just joined (they're the one waiting)
#   - Is deduped per lounge per beacon_cooldown_min
#   - Self-cleans (deleted) when the lounge empties or beacon expires
#   - Respects global quiet hours (23:00–05:00 bot timezone)
#
# State is in-memory (best-effort; a beacon surviving a restart isn't
# critical — the next join just fires a new one).

import datetime as _dt
import time as _time

# {lounge_channel_id: {"message_id": int, "posted_at": float (unix), "channel_id": int}}
_active_beacons: dict[str, dict] = {}

# Channel name for beacon posts
COMMUNITY_LIVE_CHANNEL = "community-live"

# Global quiet hours (beacon-specific; same window as the default student prefs)
_QUIET_START = (23, 0)  # 11 PM
_QUIET_END = (5, 0)     # 5 AM


def _is_global_quiet_hours() -> bool:
    """Check if the current time (in bot timezone) is within global quiet hours."""
    try:
        from zoneinfo import ZoneInfo
        from . import config
        tz = ZoneInfo(getattr(config, "TIMEZONE", "Asia/Dubai") or "Asia/Dubai")
        now = _dt.datetime.now(tz).time()
    except Exception:
        now = _dt.datetime.now().time()

    start = _dt.time(*_QUIET_START)
    end = _dt.time(*_QUIET_END)
    if start <= end:
        return start <= now <= end
    else:
        return now >= start or now <= end


def should_beacon(lounge_channel_id: str, occupancy: int, joiner_id: str = None) -> bool:
    """Determine whether a beacon should fire for this lounge right now.

    Returns True only when ALL conditions are met:
    - occupancy is in [1, beacon_max_occupancy]
    - not in global quiet hours
    - no active (non-expired) beacon for this lounge within cooldown
    """
    cfg = get_config()
    max_occ = cfg.get("community_beacon_max_occupancy", 4)
    cooldown_min = cfg.get("community_beacon_cooldown_min", 40)
    ttl_min = cfg.get("community_beacon_ttl_min", 20)

    # Not in the lonely/lively band
    if occupancy < 1 or occupancy > max_occ:
        return False

    # Quiet hours
    if _is_global_quiet_hours():
        return False

    # Cooldown: is there a recent beacon for this lounge?
    existing = _active_beacons.get(lounge_channel_id)
    if existing:
        age_min = (_time.time() - existing["posted_at"]) / 60
        if age_min < cooldown_min:
            return False

    return True


def record_beacon(lounge_channel_id: str, message_id: int, text_channel_id: int) -> None:
    """Record that a beacon was just posted (for dedup/cleanup)."""
    _active_beacons[lounge_channel_id] = {
        "message_id": message_id,
        "posted_at": _time.time(),
        "channel_id": text_channel_id,
    }


def get_active_beacon(lounge_channel_id: str) -> Optional[dict]:
    """Get the active beacon state for a lounge, or None."""
    return _active_beacons.get(lounge_channel_id)


def clear_beacon(lounge_channel_id: str) -> Optional[dict]:
    """Remove and return the beacon state for a lounge (so the caller can
    delete the Discord message). Returns None if no active beacon."""
    return _active_beacons.pop(lounge_channel_id, None)


def get_expired_beacons() -> list[dict]:
    """Return a list of beacon states that have exceeded their TTL.
    Caller should delete the Discord messages and call clear_beacon."""
    cfg = get_config()
    ttl_min = cfg.get("community_beacon_ttl_min", 20)
    now = _time.time()
    expired = []
    for lounge_id, state in list(_active_beacons.items()):
        age_min = (now - state["posted_at"]) / 60
        if age_min >= ttl_min:
            expired.append({"lounge_id": lounge_id, **state})
    return expired


def build_beacon_text(members_in_lounge: list[str], lounge_name: str,
                      lounge_id: str) -> str:
    """Build the bilingual beacon message text.

    Shows who's waiting (up to 3 names) + a jump link to the lounge.
    Arabic-first per project rules.
    """
    # Jump link to the voice channel
    jump = f"<#{lounge_id}>"

    if len(members_in_lounge) == 1:
        # One person waiting
        return (
            f"🎙️ في حد في **{lounge_name}** دلوقتي — تعالوا!\n"
            f"Someone's in **{lounge_name}** right now — join them!\n"
            f"👉 {jump}"
        )
    else:
        count = len(members_in_lounge)
        return (
            f"🎙️ في **{count}** في **{lounge_name}** دلوقتي — تعالوا!\n"
            f"**{count}** people in **{lounge_name}** right now — join!\n"
            f"👉 {jump}"
        )


def reset_beacons():
    """Clear all beacon state (e.g. on daily reset or for testing)."""
    _active_beacons.clear()


# ============================================================
#  #COMMUNITY-LIVE CHANNEL (Phase 2)
# ============================================================

_COMMUNITY_LIVE_KEY = "community_live_channel_id"


async def get_or_create_community_live(guild) -> Optional[object]:
    """Find (by stored ID, then by name) or create #community-live in the
    COMMUNITY category. Idempotent, permission-guarded, never crashes.

    Returns the TextChannel or None on failure.
    """
    import discord as dlib

    # Try stored ID first
    stored = database.get_setting(_COMMUNITY_LIVE_KEY, "")
    if stored.isdigit():
        ch = guild.get_channel(int(stored))
        if ch:
            return ch

    # Try by name
    ch = dlib.utils.get(guild.text_channels, name=COMMUNITY_LIVE_CHANNEL)
    if ch:
        database.set_setting(_COMMUNITY_LIVE_KEY, str(ch.id))
        return ch

    # Create in the COMMUNITY category (find it by the anchor voice-lounge's parent)
    try:
        anchor = dlib.utils.get(guild.voice_channels, name=MAJLIS_ANCHOR_NAME)
        category = anchor.category if anchor else None
        ch = await guild.create_text_channel(
            COMMUNITY_LIVE_CHANNEL,
            category=category,
            topic="🎙️ من في المجلس دلوقتي — إشعارات تلقائية | Who's in the Majlis — live presence")
        database.set_setting(_COMMUNITY_LIVE_KEY, str(ch.id))
        logger.info(f"community: created #{COMMUNITY_LIVE_CHANNEL} ({ch.id})")
        return ch
    except Exception as e:
        logger.warning(f"community: couldn't create #{COMMUNITY_LIVE_CHANNEL}: {e}")
        return None


# ============================================================
#  BEACON BOT ACTIONS (Phase 2 — called from bot.py wiring)
# ============================================================

async def maybe_post_beacon(guild, lounge_channel) -> None:
    """If conditions are met, post a beacon to #community-live for this lounge.

    Called from on_voice_state_update after a join. Handles all checks
    internally (band, quiet-hours, cooldown, flag). Best-effort.
    """
    if not database.is_feature_enabled("community_lounge_beacon"):
        return

    lounge_id = str(lounge_channel.id)
    occ = lounge_occupancy(guild)
    member_ids = occ.get(lounge_id, [])
    occupancy = len(member_ids)

    if not should_beacon(lounge_id, occupancy):
        return

    # Get or create #community-live
    live_ch = await get_or_create_community_live(guild)
    if not live_ch:
        return

    # Build and send the beacon
    lounge_name = getattr(lounge_channel, "name", MAJLIS_ANCHOR_NAME)
    text = build_beacon_text(member_ids, lounge_name, lounge_id)

    # Phase 4: prepend @-mention for opted-in members (if flag is ON)
    mention = build_beacon_mention(guild)
    if mention:
        text = mention + text

    try:
        msg = await live_ch.send(text)
        record_beacon(lounge_id, msg.id, live_ch.id)
        logger.info(f"community: beacon posted for {lounge_name} (occ={occupancy})")
    except Exception as e:
        logger.warning(f"community: beacon send failed: {e}")


async def maybe_clear_beacon(guild, lounge_channel) -> None:
    """If the lounge just emptied, delete its beacon message (self-clean).

    Called from on_voice_state_update after a leave.
    """
    if not database.is_feature_enabled("community_lounge_beacon"):
        return

    lounge_id = str(lounge_channel.id)
    occ = lounge_occupancy(guild)
    member_ids = occ.get(lounge_id, [])

    # Only clear if the lounge is now empty
    if member_ids:
        return

    beacon = clear_beacon(lounge_id)
    if not beacon:
        return

    # Delete the Discord message (best-effort)
    try:
        ch = guild.get_channel(beacon["channel_id"])
        if ch:
            msg = await ch.fetch_message(beacon["message_id"])
            await msg.delete()
            logger.info(f"community: beacon cleared for lounge {lounge_id}")
    except Exception:
        pass  # message already deleted, permissions, etc. — never crash


async def cleanup_expired_beacons(guild) -> None:
    """Delete beacon messages that have exceeded their TTL.
    Called from a periodic loop (e.g. every 5 min)."""
    if not database.is_feature_enabled("community_lounge_beacon"):
        return

    expired = get_expired_beacons()
    for info in expired:
        lounge_id = info["lounge_id"]
        beacon = clear_beacon(lounge_id)
        if not beacon:
            continue
        try:
            ch = guild.get_channel(beacon["channel_id"])
            if ch:
                msg = await ch.fetch_message(beacon["message_id"])
                await msg.delete()
                logger.info(f"community: expired beacon cleaned for {lounge_id}")
        except Exception:
            pass


# ============================================================
#  DYNAMIC PODS — CAPACITY CAPS + OVERFLOW ROOMS (Phase 3)
# ============================================================
#
# Design:
# - The anchor voice-lounge gets a user_limit = lounge_capacity (default 6).
# - A "➕ افتح مجلس | New Room" hub channel: joining it auto-spawns a new
#   capped Majlis lounge ("Majlis N") and moves the member into it.
# - Bot-created lounges auto-reap when empty (grace period).
# - The anchor is NEVER deleted.
# - All behind the `community_dynamic_rooms` flag.

# Hub channel name (join-to-create)
MAJLIS_HUB_NAME = "➕ افتح مجلس | New Room"
_MAJLIS_HUB_KEY = "majlis_hub_channel_id"

# Track when dynamic rooms became empty (for grace-period reaping)
# {channel_id_str: empty_since_timestamp}
_empty_since: dict[str, float] = {}


def next_majlis_number() -> int:
    """Determine the next number for a dynamically created Majlis room.
    Looks at the registry to find the highest existing N and returns N+1."""
    ids = get_majlis_room_ids()
    # The anchor is "Majlis 1" conceptually; dynamic start at 2
    return len(ids) + 2


def is_majlis_hub(channel) -> bool:
    """Return True if `channel` is the join-to-create hub."""
    name = getattr(channel, "name", None) or ""
    return name == MAJLIS_HUB_NAME


async def ensure_hub_channel(guild) -> Optional[object]:
    """Find or create the join-to-create hub voice channel in the COMMUNITY
    category. Idempotent, permission-guarded."""
    import discord as dlib

    # Try stored ID
    stored = database.get_setting(_MAJLIS_HUB_KEY, "")
    if stored.isdigit():
        ch = guild.get_channel(int(stored))
        if ch:
            return ch

    # Try by name
    ch = dlib.utils.get(guild.voice_channels, name=MAJLIS_HUB_NAME)
    if ch:
        database.set_setting(_MAJLIS_HUB_KEY, str(ch.id))
        return ch

    # Create in COMMUNITY category
    try:
        anchor = dlib.utils.get(guild.voice_channels, name=MAJLIS_ANCHOR_NAME)
        category = anchor.category if anchor else None
        ch = await guild.create_voice_channel(
            MAJLIS_HUB_NAME,
            category=category,
            user_limit=1,  # one person at a time triggers the spawn
        )
        database.set_setting(_MAJLIS_HUB_KEY, str(ch.id))
        logger.info(f"community: created hub channel '{MAJLIS_HUB_NAME}' ({ch.id})")
        return ch
    except Exception as e:
        logger.warning(f"community: couldn't create hub channel: {e}")
        return None


async def ensure_anchor_capacity(guild) -> None:
    """Set the anchor voice-lounge's user_limit to lounge_capacity if not
    already set. Idempotent, best-effort."""
    import discord as dlib

    anchor = dlib.utils.get(guild.voice_channels, name=MAJLIS_ANCHOR_NAME)
    if not anchor:
        return

    capacity = get_lounge_capacity()
    if anchor.user_limit != capacity:
        try:
            await anchor.edit(user_limit=capacity)
            logger.info(f"community: set {MAJLIS_ANCHOR_NAME} user_limit={capacity}")
        except Exception as e:
            logger.warning(f"community: couldn't set anchor capacity: {e}")


async def handle_hub_join(member, guild) -> None:
    """Called when a member joins the hub channel. Spawns a new Majlis lounge
    and moves the member into it. Flag-gated."""
    if not database.is_feature_enabled("community_dynamic_rooms"):
        return

    import discord as dlib

    capacity = get_lounge_capacity()
    num = next_majlis_number()
    room_name = f"Majlis {num}"

    try:
        # Find the COMMUNITY category
        anchor = dlib.utils.get(guild.voice_channels, name=MAJLIS_ANCHOR_NAME)
        category = anchor.category if anchor else None

        # Create the new capped lounge
        new_ch = await guild.create_voice_channel(
            room_name,
            category=category,
            user_limit=capacity,
        )
        register_majlis_room(str(new_ch.id))
        logger.info(f"community: spawned {room_name} ({new_ch.id}), cap={capacity}")

        # Move the member into the new room
        await member.move_to(new_ch)
        logger.info(f"community: moved {member.id} into {room_name}")

    except Exception as e:
        logger.warning(f"community: hub-join spawn/move failed: {e}")


async def reap_empty_majlis_rooms(guild) -> None:
    """Delete bot-created Majlis rooms that have been empty past the grace
    period. NEVER deletes the anchor. Called from the periodic reaper loop."""
    if not database.is_feature_enabled("community_dynamic_rooms"):
        return

    cfg = get_config()
    grace_min = cfg.get("community_reap_grace_min", 3)
    grace_sec = grace_min * 60
    now = _time.time()

    registered_ids = get_majlis_room_ids()
    if not registered_ids:
        return

    for ch_id_str in list(registered_ids):
        ch = guild.get_channel(int(ch_id_str))

        if ch is None:
            # Channel was manually deleted — clean up the registry
            unregister_majlis_room(ch_id_str)
            _empty_since.pop(ch_id_str, None)
            continue

        # Count non-bot members
        non_bot_members = [m for m in ch.members if not m.bot]

        if non_bot_members:
            # Room has people — clear the empty-since timer
            _empty_since.pop(ch_id_str, None)
            continue

        # Room is empty — start or check the grace timer
        if ch_id_str not in _empty_since:
            _empty_since[ch_id_str] = now
            continue

        # Check if grace period has elapsed
        empty_duration = now - _empty_since[ch_id_str]
        if empty_duration < grace_sec:
            continue

        # Grace expired — reap the room
        try:
            await ch.delete(reason="Majlis dynamic room: empty past grace period")
            unregister_majlis_room(ch_id_str)
            _empty_since.pop(ch_id_str, None)
            logger.info(f"community: reaped empty Majlis room {ch.name} ({ch_id_str})")
        except Exception as e:
            logger.warning(f"community: couldn't reap room {ch_id_str}: {e}")


def find_best_lounge(guild) -> Optional[str]:
    """Find the best lounge to suggest to a newcomer: a Majlis with
    occupancy in the "lively but not full" range. Returns the channel ID
    string, or None if all are full/empty.

    Used by the beacon (Phase 2) to point newcomers to the right room
    when multiple Majlis lounges exist."""
    occ = lounge_occupancy(guild)
    capacity = get_lounge_capacity()
    best_id = None
    best_occ = 0

    for ch_id, member_ids in occ.items():
        count = len(member_ids)
        # "Lively but not full" = has people but under capacity
        if 0 < count < capacity and count > best_occ:
            best_id = ch_id
            best_occ = count

    return best_id


def reset_empty_since():
    """Clear the empty-since tracking (for testing)."""
    _empty_since.clear()


# ============================================================
#  OPT-IN PINGS + KNOCK (Phase 4)
# ============================================================
#
# A `community-pings` role that students toggle themselves. Only opted-in
# members get @-mentioned by beacons and Knock. Shy learners never get
# pinged unless they choose to.

COMMUNITY_PINGS_ROLE = "community-pings"
_PINGS_ROLE_KEY = "community_pings_role_id"

# Knock rate-limit: {discord_id: last_knock_timestamp}
_knock_cooldown: dict[str, float] = {}
KNOCK_COOLDOWN_SEC = 300  # 5 minutes between knocks per member


async def get_or_create_pings_role(guild) -> Optional[object]:
    """Find or create the community-pings opt-in role. Idempotent."""
    import discord as dlib

    # Try stored ID
    stored = database.get_setting(_PINGS_ROLE_KEY, "")
    if stored.isdigit():
        role = guild.get_role(int(stored))
        if role:
            return role

    # Try by name
    role = dlib.utils.get(guild.roles, name=COMMUNITY_PINGS_ROLE)
    if role:
        database.set_setting(_PINGS_ROLE_KEY, str(role.id))
        return role

    # Create (mentionable so beacons can ping it, not hoisted)
    try:
        role = await guild.create_role(
            name=COMMUNITY_PINGS_ROLE,
            mentionable=True,
            reason="Majlis Phase 4: opt-in community presence pings"
        )
        database.set_setting(_PINGS_ROLE_KEY, str(role.id))
        logger.info(f"community: created role '{COMMUNITY_PINGS_ROLE}' ({role.id})")
        return role
    except Exception as e:
        logger.warning(f"community: couldn't create pings role: {e}")
        return None


def has_pings_role(member) -> bool:
    """Check if a member has the community-pings role."""
    return any(r.name == COMMUNITY_PINGS_ROLE for r in getattr(member, "roles", []))


async def toggle_pings_role(member, guild) -> str:
    """Toggle the community-pings role for a member.
    Returns 'added' or 'removed'."""
    if not database.is_feature_enabled("community_pings_optin", str(member.id)):
        return "disabled"

    role = await get_or_create_pings_role(guild)
    if not role:
        return "error"

    try:
        if has_pings_role(member):
            await member.remove_roles(role, reason="Majlis: student opted out of pings")
            return "removed"
        else:
            await member.add_roles(role, reason="Majlis: student opted in to pings")
            return "added"
    except Exception as e:
        logger.warning(f"community: toggle pings role failed for {member.id}: {e}")
        return "error"


def build_beacon_mention(guild) -> str:
    """Build the @-mention for the pings role, or empty string if the flag
    is OFF or role doesn't exist. Used by beacon messages."""
    if not database.is_feature_enabled("community_pings_optin"):
        return ""
    stored = database.get_setting(_PINGS_ROLE_KEY, "")
    if stored.isdigit():
        return f"<@&{stored}> "
    return ""


def can_knock(discord_id: str) -> tuple[bool, int]:
    """Check if a member can knock (rate-limited). Returns (allowed, seconds_remaining)."""
    now = _time.time()
    last = _knock_cooldown.get(discord_id, 0)
    elapsed = now - last
    if elapsed >= KNOCK_COOLDOWN_SEC:
        return True, 0
    return False, int(KNOCK_COOLDOWN_SEC - elapsed)


def record_knock(discord_id: str) -> None:
    """Record a knock for rate-limiting."""
    _knock_cooldown[discord_id] = _time.time()


async def do_knock(member, guild) -> str:
    """Execute a Knock: ping opted-in members via #community-live.
    Returns a status string for the caller to display.

    Rate-limited, quiet-hours aware, flag-gated.
    """
    if not database.is_feature_enabled("community_pings_optin", str(member.id)):
        return "disabled"

    # Must be in a Majlis lounge to knock
    in_majlis = False
    for vc in guild.voice_channels:
        if is_majlis_channel(vc):
            if any(m.id == member.id for m in vc.members):
                in_majlis = True
                break
    if not in_majlis:
        return "not_in_majlis"

    # Quiet hours
    if _is_global_quiet_hours():
        return "quiet_hours"

    # Rate limit
    allowed, remaining = can_knock(str(member.id))
    if not allowed:
        return f"cooldown:{remaining}"

    # Get #community-live
    live_ch = await get_or_create_community_live(guild)
    if not live_ch:
        return "error"

    # Build knock message
    mention = build_beacon_mention(guild)
    member_name = getattr(member, "display_name", str(member.id))
    text = (
        f"👋 **{member_name}** في المجلس ومستنّي حد — تعالوا!\n"
        f"**{member_name}** is in the Majlis and looking for company — join!\n"
        f"{mention}👉 <#{guild.voice_channels[0].id if guild.voice_channels else '0'}>"
    )

    # Find which lounge they're in for the jump link
    for vc in guild.voice_channels:
        if is_majlis_channel(vc) and any(m.id == member.id for m in vc.members):
            text = (
                f"👋 **{member_name}** في المجلس ومستنّي حد — تعالوا!\n"
                f"**{member_name}** is in the Majlis and looking for company — join!\n"
                f"{mention}👉 <#{vc.id}>"
            )
            break

    try:
        await live_ch.send(text)
        record_knock(str(member.id))
        logger.info(f"community: knock by {member.id}")
        return "sent"
    except Exception as e:
        logger.warning(f"community: knock send failed: {e}")
        return "error"


def reset_knock_cooldown():
    """Clear knock cooldowns (for testing)."""
    _knock_cooldown.clear()
