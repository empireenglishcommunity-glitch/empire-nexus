"""Aql (العقل) — Shadow Mode (Phase A8.4/A8.5, design.md Section 12 Phase M1).

**A8.4**: there is no new flag-enable mechanism to build here — this
phase REUSES the existing `database.set_feature_flag()` machinery
(Aegis Phase 1) exactly as designed:

    database.set_feature_flag(
        "nour_aql_core", enabled=True,
        allowed_ids=config.OWNER_DISCORD_ID, updated_by="owner",
    )

This restricts `nour_aql_core` to the owner's own Discord ID only —
the self-testing tier, matching this project's own established "test
on yourself first" pattern (Aegis's own stated precedent, reused
verbatim here rather than inventing a parallel allowlist mechanism).
`run_shadow_check()` below is what actually consults this flag.

**A8.5**: `run_shadow_check()` is the shadow-mode entry point. When
`nour_aql_core` is enabled for a given `discord_id` (per the flag
above), it runs the NEW pipeline (`orchestrator.handle_message()`)
ALONGSIDE whatever the OLD pipeline (`nour_concierge.handle_message()`)
already produced, but NEVER sends the new response anywhere — it is
only logged, side-by-side with the old response, for manual owner
review (design.md Section 12 Phase M1's explicit "zero user-visible
risk during this phase" framing).

This module does not call nour_concierge.handle_message() itself —
that remains bot.py's job, unchanged. run_shadow_check() is designed
to be called AFTER the old pipeline has already produced its response,
so the old response can be passed in for the side-by-side log, rather
than this module re-deciding when the old pipeline should run.
"""
import logging
from typing import Optional

from .. import config, database
from . import orchestrator
from .roles import resolve_role

logger = logging.getLogger("empire-bot.nour.shadow")


def enable_self_test(updated_by: str = "owner") -> None:
    """A8.4: enable `nour_aql_core` for the owner's own Discord ID
    ONLY. A thin, documented wrapper over the EXISTING
    `database.set_feature_flag()` allowlist mechanism -- not a new
    mechanism. Raises ValueError if `OWNER_DISCORD_ID` is unset in
    config (matching config.py's own "fail-safe default, not
    fail-open" framing for that setting -- shadow mode must never
    silently target an empty allowlist, which `is_feature_enabled()`
    would otherwise treat as "on for everyone").
    """
    if not config.OWNER_DISCORD_ID:
        raise ValueError(
            "Aql shadow mode: OWNER_DISCORD_ID is not set in config -- "
            "cannot restrict nour_aql_core to an owner-only allowlist "
            "without it. Set OWNER_DISCORD_ID in .env first."
        )
    database.set_feature_flag(
        "nour_aql_core", enabled=True,
        allowed_ids=config.OWNER_DISCORD_ID, updated_by=updated_by,
    )
    logger.info(f"Aql shadow mode: nour_aql_core enabled for owner-only allowlist ({updated_by})")


def is_shadow_eligible(discord_id: str) -> bool:
    """True if `nour_aql_core` is enabled for this specific
    discord_id (per the existing feature-flag allowlist semantics) --
    the single gate `run_shadow_check()` consults before doing any
    work, so a message from anyone NOT on the allowlist costs nothing
    beyond this one flag lookup."""
    return database.is_feature_enabled("nour_aql_core", discord_id)


async def run_shadow_check(discord_id: str, text: str, old_response: Optional[str]) -> Optional[dict]:
    """design.md Section 12 Phase M1. If `discord_id` is
    shadow-eligible, runs the NEW pipeline and logs it side-by-side
    with `old_response` -- but NEVER returns the new response for
    sending; the return value here is for TESTS/inspection/manual
    comparison only, matching this phase's "zero user-visible risk"
    guarantee structurally: nothing calling this function can
    accidentally end up sending the new pipeline's output, because
    this function's return value is explicitly a comparison record,
    not a "response to send."

    Returns None if `discord_id` is not shadow-eligible (the common
    case for every real student today, since the allowlist is
    owner-only per A8.4) -- callers should treat None as "shadow mode
    did nothing, proceed exactly as before this phase existed."

    Never raises: any failure in the NEW pipeline is caught and
    logged as a comparison record with `new_response=None` and an
    `error` field, rather than propagating -- shadow mode existing
    at all must never be able to break the OLD pipeline's real
    response path, which has already completed by the time this is
    called.
    """
    if not is_shadow_eligible(discord_id):
        return None

    role = resolve_role(discord_id)
    new_response: Optional[str] = None
    error: Optional[str] = None
    try:
        new_response = await orchestrator.handle_message(discord_id, text)
    except Exception as e:
        logger.error(f"Aql shadow mode: NEW pipeline raised for {discord_id}: {e}")
        error = str(e)[:300]

    record = {
        "discord_id": discord_id,
        "role": role.value if role else None,
        "text": text,
        "old_response": old_response,
        "new_response": new_response,
        "error": error,
        "responses_match": (
            old_response is not None and new_response is not None
            and old_response.strip() == new_response.strip()
        ),
    }
    database.log_shadow_comparison(**record)
    logger.info(
        f"Aql shadow mode: comparison logged for {discord_id} "
        f"(match={record['responses_match']}, error={bool(error)})"
    )
    return record
