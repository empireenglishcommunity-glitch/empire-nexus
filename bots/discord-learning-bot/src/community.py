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
