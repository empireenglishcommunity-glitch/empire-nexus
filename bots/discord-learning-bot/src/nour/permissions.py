"""Aql (العقل) — Role -> Knowledge Domain / Tool Permission Mapping.

design.md Section 3. THIS is the actual security boundary, not a
prompt instruction. The context-assembly step (built in later phases)
iterates ONLY over KNOWLEDGE_DOMAINS[role] and registers ONLY
TOOL_REGISTRY[role] tool schemas with the LLM call. For a student-role
request, every owner-only domain/tool name never appears anywhere in
the prompt, the retrieval query, or the function-calling schema
offered to the model — there is nothing for a prompt-injection attempt
to extract, because it was never fetched into that request's working
set in the first place.

This is a structural allowlist, the same pattern this codebase already
trusts for feature flags (database.is_feature_enabled's "fail closed"
allowlist logic) and for Hissar's role-gate.

requirements.md Section 4.3 / Section 8: ADMIN, MODERATOR, COACH are
reserved role values (see roles.py) but must NOT receive real
domain/tool mappings in this initiative — the guard functions below
enforce that explicitly rather than silently returning an empty list
(which could be mistaken for "intentionally no access" vs. "not
implemented yet").
"""
from .roles import Role

# ============================================================
#  KNOWLEDGE DOMAINS
# ============================================================
# Domain names match the existing data/nour_knowledge/*.md filename
# stems (Rawiya R1) plus new owner-only domains added in Phase A2.
# "tutorials" is added here now (ahead of Phase A7's actual chunking
# work) so the permission mapping and its test (A0.8) are already
# correct before that content exists — adding the domain to the map
# is a no-op until Phase A1/A7 actually populates chunks under it.

_STUDENT_DOMAINS = [
    "system_overview", "daily_tasks", "channels", "commands",
    "practice_platform", "troubleshooting", "mobile_guide",
    "study_strategies", "faq", "levels_points", "tutorials",
]

_OWNER_ONLY_DOMAINS = [
    "owner_ops", "architecture", "codebase_map", "database_schema",
    "deployment_runbook", "flag_registry_reference",
]

KNOWLEDGE_DOMAINS: dict[Role, list[str]] = {
    Role.STUDENT: list(_STUDENT_DOMAINS),
    # Owner gets EVERY student domain PLUS owner-only domains.
    Role.OWNER: list(_STUDENT_DOMAINS) + list(_OWNER_ONLY_DOMAINS),
}

# ============================================================
#  TOOL REGISTRY
# ============================================================
# Tool names match the function names implemented in Phase A3
# (src/nour/tools/student_tools.py, owner_tools.py). Listed here first
# so the permission boundary and its test exist before the tools
# themselves do — the mapping is what's being verified in A0.8, not
# the tools' internal behavior (that's A3's own test suite).

_STUDENT_TOOLS = [
    "get_my_progress", "get_my_journey_coverage",
    "get_my_recent_scores", "get_leaderboard_position",
]

_OWNER_ONLY_TOOLS = [
    "get_student_status", "get_roster_summary", "get_system_health",
    "get_security_stats", "send_announcement", "nudge_student",
    "flag_student", "toggle_feature_flag", "explain_code_behavior",
]

TOOL_REGISTRY: dict[Role, list[str]] = {
    Role.STUDENT: list(_STUDENT_TOOLS),
    # Owner gets student-safe tools PLUS owner-only tools.
    Role.OWNER: list(_STUDENT_TOOLS) + list(_OWNER_ONLY_TOOLS),
}


# ============================================================
#  ACCESSORS (guard against unpopulated future roles — Requirements §4.3)
# ============================================================

def get_knowledge_domains(role: Role) -> list[str]:
    """Return the exact list of knowledge domains this role may
    retrieve from. Returns an EMPTY list (not an error, not a
    fallback to student domains) for any role without a real mapping
    yet — this is the correct "not implemented" behavior for
    ADMIN/MODERATOR/COACH per requirements.md Section 4.3: no access,
    because no real content/mapping exists for them, not because of a
    lookup failure.
    """
    return list(KNOWLEDGE_DOMAINS.get(role, []))


def get_tool_registry(role: Role) -> list[str]:
    """Return the exact list of tool names this role may invoke.
    Same "empty, not fallback" behavior as get_knowledge_domains() for
    unpopulated future roles.
    """
    return list(TOOL_REGISTRY.get(role, []))


def is_domain_allowed(role: Role, domain: str) -> bool:
    """Single-domain check, used by the data-layer defense-in-depth
    check (design.md Section 4.2's SQL WHERE domain IN (...) clause is
    the primary enforcement; this function is the same check available
    for any code path that needs a yes/no answer without fetching the
    whole list)."""
    return domain in KNOWLEDGE_DOMAINS.get(role, [])


def is_tool_allowed(role: Role, tool_name: str) -> bool:
    """Single-tool check, used by the tool dispatcher (Phase A3.3) to
    validate a requested tool name against the caller's role before
    executing — structurally redundant with the fact that owner-only
    tool schemas are never offered to a student-role LLM call in the
    first place, but present anyway per this codebase's established
    "double-check security-relevant logic" convention (see Hissar's
    role-gate + channel-permission overwrite combination for
    precedent)."""
    return tool_name in TOOL_REGISTRY.get(role, [])
