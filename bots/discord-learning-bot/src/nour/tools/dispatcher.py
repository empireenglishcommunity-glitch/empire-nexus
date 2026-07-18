"""Aql (العقل) — Tool Dispatcher (Phase A3.3/A3.4).

design.md Section 3 + Section 5. Single entry point for invoking any
tool, for any role. Validates the requested tool name against the
caller's TOOL_REGISTRY[role] BEFORE executing — structurally redundant
with the fact that owner-only tool schemas are never offered to a
student-role LLM call in the first place (Component 2's context
assembly only registers TOOL_REGISTRY[role]'s own schemas), but
present anyway per this codebase's established "double-check
security-relevant logic" convention (see Hissar's role-gate +
channel-permission overwrite combination for precedent, and
permissions.py's own is_tool_allowed() docstring).

Every call — allowed or rejected, successful or failed — is logged to
`nour_tool_calls` (Phase A3.4, design.md Section 13).
"""
import logging
import time
from typing import Any, Optional

from ... import database
from .. import permissions
from ..roles import Role
from . import student_tools, owner_tools

logger = logging.getLogger("empire-bot.nour.tool_dispatcher")


class ToolError(Exception):
    """Raised by execute_tool() for any dispatch-level failure
    (unknown tool name, tool not permitted for this role, or the
    underlying tool function itself raising). Callers (the future
    orchestrator, Phase A5) must catch this and compose a graceful
    response — never let it surface as a raw exception to the user."""


# Merge both role tiers' dispatch tables into one lookup by tool name.
# A name collision between the two would be a genuine bug (the same
# tool name meaning two different things depending on who calls it) --
# asserted here at import time so it fails loudly at startup, not
# silently at the first ambiguous dispatch.
_ALL_FUNCTIONS: dict[str, Any] = {}
for _name, _fn in student_tools.FUNCTIONS.items():
    _ALL_FUNCTIONS[_name] = _fn
for _name, _fn in owner_tools.FUNCTIONS.items():
    assert _name not in _ALL_FUNCTIONS, (
        f"Aql tool dispatcher: '{_name}' is defined in BOTH student_tools "
        f"and owner_tools -- tool names must be globally unique."
    )
    _ALL_FUNCTIONS[_name] = _fn


# Tools whose real function signature takes NO discord_id at all
# (every owner tool, since owner tools take model-supplied business
# parameters instead — student_name, message, etc. — never a caller
# identity parameter, per owner_tools.py's own docstring). The
# dispatcher must NOT attempt to inject discord_id as a positional
# arg for these, unlike every student tool.
_STUDENT_SCOPED_TOOLS = frozenset(student_tools.FUNCTIONS.keys())

# Merged schema lookup by name (student_tools.TOOLS + owner_tools.TOOLS)
# -- same import-time uniqueness guarantee as _ALL_FUNCTIONS above,
# since both lists are keyed by the same tool names.
_ALL_SCHEMAS: dict[str, dict] = {}
for _schema in student_tools.TOOLS:
    _ALL_SCHEMAS[_schema["name"]] = _schema
for _schema in owner_tools.TOOLS:
    _ALL_SCHEMAS[_schema["name"]] = _schema


def get_tool_schemas_for_role(role: Role) -> list[dict]:
    """Returns the model-facing TOOLS schema list for exactly this
    role's permitted tools (permissions.get_tool_registry(role)) --
    the orchestrator (Phase A5) calls this ONCE per request and passes
    the result to the LLM call; a student-role request never even
    constructs a schema dict for an owner-only tool name, matching
    design.md Section 3's framing that there is nothing for a
    prompt-injection attempt to extract because it was never fetched
    into that request's working set in the first place."""
    allowed_names = permissions.get_tool_registry(role)
    return [_ALL_SCHEMAS[name] for name in allowed_names if name in _ALL_SCHEMAS]


async def execute_tool(name: str, role: Role, discord_id: str,
                       arguments: Optional[dict] = None) -> Any:
    """Execute a tool by name, on behalf of `role`, for `discord_id`.

    1. Reject immediately (ToolError, not a silent no-op and not a
       successful-looking empty result) if `name` is not in
       permissions.get_tool_registry(role) — this is A3.5's exact
       requirement: an owner-only tool name reaching this function
       through a student's role must raise, never silently succeed.
    2. For a student-scoped tool, `discord_id` is passed as the
       function's caller-identity argument — arguments dict, even if
       it somehow contained a `discord_id` key, is NEVER used for this
       (student_tools.py's functions don't even accept it as a kwarg
       name, so this is enforced by the function signature itself,
       not just by this dispatcher's discipline).
    3. For an owner tool, `arguments` (model-supplied business
       parameters) are passed as **kwargs; discord_id is NOT passed at
       all, matching owner_tools.py's actual signatures.
    4. Every attempt (rejected or executed, successful or failed) is
       logged to nour_tool_calls via database.log_tool_call().
    """
    arguments = arguments or {}
    started = time.monotonic()

    allowed = permissions.is_tool_allowed(role, name)
    if not allowed:
        latency_ms = int((time.monotonic() - started) * 1000)
        error_msg = f"tool '{name}' is not permitted for role '{role.value}'"
        database.log_tool_call(
            discord_id=discord_id, role=role.value, tool_name=name,
            arguments=_redact(name, arguments), latency_ms=latency_ms,
            success=False, error_message=error_msg,
        )
        raise ToolError(error_msg)

    fn = _ALL_FUNCTIONS.get(name)
    if fn is None:
        # In the registry (permissions.py knows the NAME) but no
        # implementation exists yet -- a real "not built yet" gap,
        # distinct from "not permitted". Still a ToolError either way
        # from the caller's perspective (nothing executed), but the
        # message says why.
        latency_ms = int((time.monotonic() - started) * 1000)
        error_msg = f"tool '{name}' is registered for role '{role.value}' but has no implementation"
        database.log_tool_call(
            discord_id=discord_id, role=role.value, tool_name=name,
            arguments=_redact(name, arguments), latency_ms=latency_ms,
            success=False, error_message=error_msg,
        )
        raise ToolError(error_msg)

    try:
        if name in _STUDENT_SCOPED_TOOLS:
            result = await fn(discord_id)
        else:
            result = await fn(**arguments)
    except Exception as e:
        latency_ms = int((time.monotonic() - started) * 1000)
        logger.error(f"Aql tool dispatcher: '{name}' raised: {e}")
        database.log_tool_call(
            discord_id=discord_id, role=role.value, tool_name=name,
            arguments=_redact(name, arguments), latency_ms=latency_ms,
            success=False, error_message=str(e)[:300],
        )
        raise ToolError(f"tool '{name}' failed: {e}") from e

    latency_ms = int((time.monotonic() - started) * 1000)
    database.log_tool_call(
        discord_id=discord_id, role=role.value, tool_name=name,
        arguments=_redact(name, arguments), latency_ms=latency_ms,
        success=True,
    )
    return result


# Argument keys that should never be persisted verbatim to the
# nour_tool_calls log, per tool. Currently none of the real A3 tools
# take a genuinely sensitive parameter (no passwords/tokens flow
# through this layer) -- this exists as the designated extension point
# design.md Section 13 calls for ("arguments minus any sensitive
# values"), so a future tool with a sensitive parameter has an
# obvious, already-wired place to register redaction rather than
# needing to touch the dispatcher's core logic.
_REDACT_KEYS: dict[str, set] = {}


def _redact(tool_name: str, arguments: dict) -> dict:
    keys_to_redact = _REDACT_KEYS.get(tool_name, set())
    if not keys_to_redact:
        return arguments
    return {
        k: ("<redacted>" if k in keys_to_redact else v)
        for k, v in arguments.items()
    }
