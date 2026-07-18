"""Aql (العقل) — Role Resolution.

design.md Section 2. Determines WHO is asking, before any knowledge
retrieval or tool consideration happens. This resolution is structural
(a lookup producing a fixed, enumerable value) — never something the
LLM decides, never mutable by conversation content.

Currently fully populated: OWNER, STUDENT.
Reserved, not populated (requirements.md Section 4.3): ADMIN, MODERATOR,
COACH — the enum accepts future values with zero mechanism changes, but
no content/tools/domain mappings exist for them yet. Do not add real
behavior for these until real people hold those responsibilities.
"""
from enum import Enum
from typing import Optional

from .. import config, database


class Role(str, Enum):
    OWNER = "owner"
    STUDENT = "student"
    # Reserved for future population — requirements.md Section 4.3.
    # Do NOT add domain/tool mappings for these until real people hold
    # these responsibilities (see permissions.py's explicit guard).
    ADMIN = "admin"
    MODERATOR = "moderator"
    COACH = "coach"


def resolve_role(discord_id: str) -> Optional[Role]:
    """Resolve a Discord user ID to their Role, or None if they are
    neither the configured owner nor a registered member.

    Returns None in the "not eligible for Nour at all" case — the
    caller (the orchestrator) must not proceed to retrieval/tools/
    generation when this returns None. This exactly mirrors today's
    `if not member: return None` early-exit in
    nour_concierge.handle_message() — zero behavior change for anyone
    who wasn't already eligible.

    The owner check is intentionally FIRST and uses a hardcoded config
    value (config.OWNER_DISCORD_ID), not a Discord role name — Discord
    roles are editable by anyone with sufficient server permissions,
    which makes them unsuitable as the sole gate for unrestricted
    system access. A config value tied to one verified account, set
    once in .env, is not editable from within Discord at all.
    """
    if not discord_id:
        return None

    owner_id = config.OWNER_DISCORD_ID
    if owner_id and str(discord_id) == str(owner_id):
        return Role.OWNER

    if database.get_member(str(discord_id)):
        return Role.STUDENT

    return None


def is_owner(discord_id: str) -> bool:
    """Convenience check used by call sites that only care about the
    owner/not-owner distinction (e.g. deciding whether to apply
    graduated-presence throttling, which never applies to the owner)."""
    return resolve_role(discord_id) == Role.OWNER
