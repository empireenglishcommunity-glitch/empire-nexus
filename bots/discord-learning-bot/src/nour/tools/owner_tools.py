"""Aql (العقل) — Owner Tool Set (Phase A3.2).

design.md Section 5.3: owner tools do NOT reimplement anything — they
call the exact functions `ops_commands.py` and `nour_ops_commands.py`
already implement and have already been tested against real Telegram
usage. The result: the owner's existing `/check`, `/announce`,
`/status`, `/nudge`, `/flag` Telegram commands become directly
callable BY Nour through natural language, in addition to remaining
directly callable by typing the exact command — full backward
compatibility, zero loss of existing capability, pure additive value.

Unlike student_tools.py, these functions DO accept model-supplied
parameters (student_name, message, flag_name, topic, ...) — this is
intentional and safe, because these tools are only ever reachable
through TOOL_REGISTRY[Role.OWNER] (permissions.py), never offered to
a student-role LLM call in the first place.
"""
import logging
from typing import Optional

from ... import database
from .. import permissions
from ..roles import Role
from ..knowledge.retriever import retrieve

logger = logging.getLogger("empire-bot.nour.owner_tools")

# ============================================================
#  BOT INSTANCE REGISTRATION
# ============================================================
# ops_commands.py's handlers all take (args, bot) — they need a live
# discord.py Bot instance (guild lookups, channel sends). Rather than
# have this module import bot.py directly (which would create a
# circular import — bot.py is the actual entry point that will
# eventually wire the orchestrator in), the real bot process registers
# itself once via set_bot() at startup. Tests register a fake/mock bot
# the same way. Calling an owner tool that needs a bot BEFORE one has
# been registered raises RuntimeError rather than crashing on a bare
# AttributeError deep inside ops_commands.py -- a clearer failure mode
# for whoever wires this up next (Phase A5's orchestrator).

_bot_instance = None


def set_bot(bot) -> None:
    """Register the live discord.py Bot instance. Called once from the
    bot process at startup (wiring into bot.py itself is Phase A5's
    job, when the orchestrator that actually calls these tools is
    built — this phase only needs the registration mechanism to
    exist and be testable)."""
    global _bot_instance
    _bot_instance = bot


def _get_bot():
    if _bot_instance is None:
        raise RuntimeError(
            "Aql owner_tools: no bot instance registered. Call "
            "src.nour.tools.owner_tools.set_bot(bot) once at startup "
            "before invoking any owner tool that needs Discord access."
        )
    return _bot_instance


# ============================================================
#  TOOL SCHEMAS (offered to the model for function-calling, owner role only)
# ============================================================

TOOLS = [
    {
        "name": "get_student_status",
        "description": "Get a full status report for a specific student by name (level, streak, points, journey status).",
        "parameters": {"student_name": "string"},
    },
    {
        "name": "get_roster_summary",
        "description": "Get a summary of all active students (totals, active-today count, top performers).",
        "parameters": {},
    },
    {
        "name": "get_system_health",
        "description": "Get the bot's operational health snapshot (uptime, AI provider status, submission counts).",
        "parameters": {},
    },
    {
        "name": "get_security_stats",
        "description": "Get security monitoring stats (flagged link tokens, suspicious IP activity).",
        "parameters": {},
    },
    {
        "name": "send_announcement",
        "description": "Post an announcement message to the Discord #announcements channel.",
        "parameters": {"message": "string"},
    },
    {
        "name": "nudge_student",
        "description": "Send a personalized Nour check-in DM to a specific student by name.",
        "parameters": {"student_name": "string"},
    },
    {
        "name": "flag_student",
        "description": "Mark a student for attention with a reason, for later follow-up.",
        "parameters": {"student_name": "string", "reason": "string"},
    },
    {
        "name": "toggle_feature_flag",
        "description": "Enable or disable a feature flag by name.",
        "parameters": {"flag_name": "string", "enabled": "boolean"},
    },
    {
        "name": "explain_code_behavior",
        "description": "Retrieve technical/architectural knowledge about how the bot's code works, for a given topic.",
        "parameters": {"topic": "string"},
    },
]


async def get_student_status(student_name: str) -> str:
    """Thin wrapper — delegates to the EXISTING, already-shipped
    ops_commands.handle_check() logic. Not reimplemented."""
    from ... import ops_commands
    return await ops_commands.handle_check(student_name, _get_bot())


async def get_roster_summary() -> str:
    """Thin wrapper over ops_commands.handle_students()."""
    from ... import ops_commands
    return await ops_commands.handle_students("", _get_bot())


async def get_system_health() -> str:
    """Thin wrapper over ops_commands.handle_status()."""
    from ... import ops_commands
    return await ops_commands.handle_status("", _get_bot())


async def get_security_stats() -> dict:
    """Reads database.get_security_stats() directly -- this is
    already the real, existing implementation (used today by
    nour_ops_commands._cmd_status and the Markaz daily digest), not a
    new computation. No bot instance needed since this is pure DB
    reads, unlike the Discord-touching tools above.
    """
    return database.get_security_stats()


async def send_announcement(message: str) -> str:
    """Thin wrapper — delegates to ops_commands.handle_announce(),
    which already posts to #announcements with the exact same
    validation (length limit, channel-exists check) the /announce
    Telegram command uses today."""
    from ... import ops_commands
    return await ops_commands.handle_announce(message, _get_bot())


async def nudge_student(student_name: str) -> str:
    """Thin wrapper over ops_commands.handle_nudge()."""
    from ... import ops_commands
    return await ops_commands.handle_nudge(student_name, _get_bot())


async def flag_student(student_name: str, reason: str = "") -> str:
    """Thin wrapper — delegates to nour_ops_commands._cmd_flag(), the
    existing "mark student for attention" implementation (distinct
    from ops_commands.handle_flag(), which toggles FEATURE flags, not
    student attention flags -- different concept, same word)."""
    from ... import nour_ops_commands
    args = f"{student_name} {reason}".strip()
    return await nour_ops_commands._cmd_flag(args, _get_bot())


async def toggle_feature_flag(flag_name: str, enabled: bool) -> str:
    """Direct call to the existing database.set_feature_flag() --
    the exact same function the /flag Telegram command and !flag
    Discord command already use. `updated_by` is tagged distinctly so
    a flag-change audit trail can tell a Nour-driven toggle apart from
    a manual one."""
    database.set_feature_flag(flag_name, enabled=enabled, updated_by="nour_owner_tool")
    return f"Flag '{flag_name}' set to {'ON' if enabled else 'OFF'}."


# Owner-only technical knowledge domains this tool is scoped to --
# deliberately a SUBSET of KNOWLEDGE_DOMAINS[Role.OWNER] (which also
# includes every student domain plus owner_ops/deployment_runbook/
# flag_registry_reference) -- explain_code_behavior is specifically
# about CODE, not about operational runbooks or flag lists, which have
# their own dedicated tools/domains above.
_CODE_EXPLANATION_DOMAINS = ["architecture", "codebase_map", "database_schema"]


async def explain_code_behavior(topic: str) -> dict:
    """Retrieves from the owner-only 'architecture'/'codebase_map'/
    'database_schema' knowledge domains and returns the raw grounding
    chunks for a given topic. This is retrieval, the same mechanism as
    a knowledge question (Component 3) -- "owner tool" here means
    "permission to ask", per design.md Section 5.3. Composing these
    chunks into a natural-language explanation is the orchestrator's
    job (Phase A5's guarded_generate()), not this tool's -- a tool
    call returns grounding data, the final LLM call turns it into
    prose.
    """
    all_chunks = await retrieve(topic, Role.OWNER, top_k=6)
    relevant = [c for c in all_chunks if c.domain in _CODE_EXPLANATION_DOMAINS]
    return {
        "topic": topic,
        "chunks": [
            {"domain": c.domain, "heading": c.heading, "content": c.content}
            for c in relevant
        ],
        "found_any": len(relevant) > 0,
    }


FUNCTIONS = {
    "get_student_status": get_student_status,
    "get_roster_summary": get_roster_summary,
    "get_system_health": get_system_health,
    "get_security_stats": get_security_stats,
    "send_announcement": send_announcement,
    "nudge_student": nudge_student,
    "flag_student": flag_student,
    "toggle_feature_flag": toggle_feature_flag,
    "explain_code_behavior": explain_code_behavior,
}
