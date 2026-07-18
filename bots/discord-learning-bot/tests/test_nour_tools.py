"""Tests for Aql (#15) Phase A3 — Tool Layer.

Covers:
- A3.1: student tool set returns real data shaped correctly.
- A3.2: owner tool set are thin wrappers over EXISTING ops_commands.py
  / nour_ops_commands.py functions (mocked bot, not reimplemented
  logic).
- A3.3/A3.5: the dispatcher's role gate — an owner-only tool name
  reaching execute_tool() through Role.STUDENT must raise ToolError,
  never silently succeed.
- A3.4: every dispatch attempt (allowed or rejected, success or
  failure) is logged to nour_tool_calls.
- A3.6: every student tool's real function signature has NO
  parameter that could target a different student's data (inspected
  via `inspect.signature`, not just read by eye).
"""
import inspect

import pytest

from src import database
from src.nour import permissions
from src.nour.roles import Role
from src.nour.tools import dispatcher, owner_tools, student_tools
from src.nour.tools.dispatcher import ToolError, execute_tool


# ============================================================
#  A3.6 — student tool signatures can never target another student
# ============================================================

def test_no_student_tool_accepts_a_discord_id_style_parameter_besides_the_bound_one():
    """Every student tool function must have EXACTLY ONE parameter
    (the caller-identity one the dispatcher injects), and it must be
    positional -- no keyword parameter through which a model could
    supply a *different* target identity (e.g. `student_name`,
    `target_id`, `other_discord_id`) alongside or instead of it."""
    suspicious_names = {"student_name", "target_id", "other_discord_id",
                        "user_id", "member_id", "name"}
    for tool_name, fn in student_tools.FUNCTIONS.items():
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        assert params == ["discord_id"], (
            f"student tool '{tool_name}' has parameters {params} -- "
            f"expected exactly ['discord_id'] (the dispatcher-bound "
            f"caller identity), per design.md Section 5.2's rule that "
            f"every student tool is implicitly 'about me'"
        )
        assert not (set(params) & suspicious_names - {"discord_id"}), (
            f"student tool '{tool_name}' has a suspicious extra parameter"
        )


def test_student_tools_schema_list_declares_zero_parameters():
    """The TOOLS schema list offered to the model must show `{}` for
    every student tool's parameters -- this is the actual evidence a
    model-facing function-calling schema has nothing to inject a
    target identity into (design.md Section 5.2)."""
    for tool_def in student_tools.TOOLS:
        assert tool_def["parameters"] == {}, (
            f"student tool schema '{tool_def['name']}' declares "
            f"non-empty parameters: {tool_def['parameters']}"
        )


def test_student_tools_and_schema_list_are_the_same_set():
    schema_names = {t["name"] for t in student_tools.TOOLS}
    impl_names = set(student_tools.FUNCTIONS.keys())
    assert schema_names == impl_names


def test_student_tools_match_permissions_registry_exactly():
    registry_names = set(permissions.get_tool_registry(Role.STUDENT))
    impl_names = set(student_tools.FUNCTIONS.keys())
    assert registry_names == impl_names


def test_owner_tools_match_permissions_registry_exactly():
    registry_owner_only = set(permissions.get_tool_registry(Role.OWNER)) - set(
        permissions.get_tool_registry(Role.STUDENT)
    )
    impl_names = set(owner_tools.FUNCTIONS.keys())
    assert registry_owner_only == impl_names


# ============================================================
#  A3.1 — student tools return real data
# ============================================================

@pytest.mark.asyncio
async def test_get_my_progress_for_real_member():
    database.register_member("u1", "Alice", level="L1")
    database.add_points("u1", 150, "test")
    result = await student_tools.get_my_progress("u1")
    assert result["found"] is True
    assert result["level"] == "L1"
    assert result["total_points"] == 150


@pytest.mark.asyncio
async def test_get_my_progress_for_unknown_member():
    result = await student_tools.get_my_progress("ghost")
    assert result["found"] is False


@pytest.mark.asyncio
async def test_get_my_journey_coverage_defaults_to_all_false():
    database.register_member("u1", "Alice")
    result = await student_tools.get_my_journey_coverage("u1")
    assert result == {
        "knows_daily_tasks": False,
        "knows_platform_link": False,
        "knows_streaks": False,
        "knows_channels": False,
        "first_task_done": False,
    }


@pytest.mark.asyncio
async def test_get_my_recent_scores_empty_for_new_member():
    database.register_member("u1", "Alice")
    result = await student_tools.get_my_recent_scores("u1")
    assert result["scores_last_7_days"] == []
    assert result["average_7d"] == 0.0
    assert result["total_scored"] == 0


@pytest.mark.asyncio
async def test_get_my_recent_scores_with_real_data():
    import datetime
    database.register_member("u1", "Alice")
    today = datetime.date.today().isoformat()
    database.store_pronunciation_score(
        "u1", today, "accent", 85.0, "expected", "transcript",
    )
    result = await student_tools.get_my_recent_scores("u1")
    assert result["total_scored"] == 1
    assert result["average_7d"] == 85.0


@pytest.mark.asyncio
async def test_get_leaderboard_position_ranks_correctly():
    database.register_member("u1", "Alice")
    database.register_member("u2", "Bob")
    database.register_member("u3", "Carol")
    database.add_points("u1", 300, "test")
    database.add_points("u2", 500, "test")
    database.add_points("u3", 100, "test")

    result = await student_tools.get_leaderboard_position("u2")
    assert result["found"] is True
    assert result["rank"] == 1

    result = await student_tools.get_leaderboard_position("u3")
    assert result["rank"] == 3


@pytest.mark.asyncio
async def test_get_leaderboard_position_unknown_member():
    result = await student_tools.get_leaderboard_position("ghost")
    assert result["found"] is False


# ============================================================
#  A3.2 — owner tools are thin wrappers (mocked bot)
# ============================================================

class _FakeGuild:
    def __init__(self):
        self.text_channels = []

    def get_member(self, _id):
        return None


class _FakeBot:
    def __init__(self):
        self.guilds = []
        self._ready = True

    def is_ready(self):
        return self._ready

    def get_guild(self, _id):
        return None


@pytest.fixture(autouse=True)
def _register_fake_bot():
    owner_tools.set_bot(_FakeBot())
    yield
    owner_tools.set_bot(None)


@pytest.mark.asyncio
async def test_get_student_status_delegates_to_ops_commands_handle_check():
    database.register_member("u1", "Alice", level="L2")
    result = await owner_tools.get_student_status("Alice")
    assert "Alice" in result or "L2" in result


@pytest.mark.asyncio
async def test_get_student_status_unknown_name():
    result = await owner_tools.get_student_status("NoSuchPerson")
    assert "not found" in result.lower() or "❌" in result


@pytest.mark.asyncio
async def test_get_roster_summary_delegates_to_ops_commands():
    database.register_member("u1", "Alice")
    result = await owner_tools.get_roster_summary()
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_system_health_delegates_to_ops_commands():
    result = await owner_tools.get_system_health()
    assert isinstance(result, str)
    assert "Status" in result or "status" in result.lower()


@pytest.mark.asyncio
async def test_get_security_stats_reads_real_database_function():
    result = await owner_tools.get_security_stats()
    assert "flagged_tokens" in result
    assert "total_tracked_tokens" in result


@pytest.mark.asyncio
async def test_toggle_feature_flag_sets_real_flag():
    await owner_tools.toggle_feature_flag("some_test_flag", True)
    assert database.is_feature_enabled("some_test_flag") is True
    await owner_tools.toggle_feature_flag("some_test_flag", False)
    assert database.is_feature_enabled("some_test_flag") is False


@pytest.mark.asyncio
async def test_owner_tool_without_bot_registered_raises_runtime_error():
    owner_tools.set_bot(None)
    with pytest.raises(RuntimeError):
        await owner_tools.get_system_health()


@pytest.mark.asyncio
async def test_explain_code_behavior_filters_to_code_domains(monkeypatch):
    """explain_code_behavior must only surface chunks from the
    architecture/codebase_map/database_schema domains -- not every
    owner domain (e.g. not deployment_runbook or flag_registry_reference,
    which have their own dedicated tools/purpose)."""
    import numpy as np
    from src.nour.knowledge.embedder import pack_embedding

    database.insert_knowledge_chunk(
        domain="architecture", source_file="architecture.md", heading="بنية",
        content="محتوى البنية", embedding=pack_embedding(np.random.rand(768).astype(np.float32)),
        embedding_model="gemini-embedding-001",
    )
    database.insert_knowledge_chunk(
        domain="deployment_runbook", source_file="deployment_runbook.md", heading="نشر",
        content="محتوى النشر", embedding=pack_embedding(np.random.rand(768).astype(np.float32)),
        embedding_model="gemini-embedding-001",
    )

    async def fake_embed(text, task_type="RETRIEVAL_QUERY"):
        return np.random.rand(768).astype(np.float32)

    monkeypatch.setattr("src.nour.knowledge.retriever.embed_text", fake_embed)

    result = await owner_tools.explain_code_behavior("كيف يعمل النظام")
    domains_found = {c["domain"] for c in result["chunks"]}
    assert "deployment_runbook" not in domains_found


# ============================================================
#  A3.3/A3.5 — dispatcher role gate
# ============================================================

@pytest.mark.asyncio
async def test_owner_only_tool_via_student_role_raises_tool_error():
    database.register_member("u1", "Alice")
    with pytest.raises(ToolError):
        await execute_tool("get_student_status", Role.STUDENT, "u1",
                           {"student_name": "Alice"})


@pytest.mark.asyncio
async def test_owner_only_tool_via_student_role_never_silently_succeeds():
    """Explicit A3.5 wording check: not just 'raises something', but
    specifically never returns a normal-looking successful result."""
    database.register_member("u1", "Alice")
    try:
        result = await execute_tool("get_student_status", Role.STUDENT, "u1", {})
        assert False, f"expected ToolError, got a return value: {result!r}"
    except ToolError:
        pass


@pytest.mark.asyncio
async def test_student_tool_via_owner_role_is_allowed():
    """Owner gets student-safe tools too (owner is a superset) --
    confirms the gate isn't accidentally student-only in reverse."""
    database.register_member("owner1", "Owner")
    result = await execute_tool("get_my_progress", Role.OWNER, "owner1", {})
    assert result["found"] is True


@pytest.mark.asyncio
async def test_unknown_tool_name_raises_tool_error():
    database.register_member("u1", "Alice")
    with pytest.raises(ToolError):
        await execute_tool("delete_everything", Role.STUDENT, "u1", {})


@pytest.mark.asyncio
async def test_reserved_role_gets_zero_tools_via_dispatcher():
    """ADMIN has no populated TOOL_REGISTRY mapping -- every tool call
    attempt through that role must be rejected, matching
    permissions.py's 'empty means no access' convention."""
    with pytest.raises(ToolError):
        await execute_tool("get_my_progress", Role.ADMIN, "someone", {})


@pytest.mark.asyncio
async def test_student_tool_executes_successfully_via_dispatcher():
    database.register_member("u1", "Alice", level="L1")
    result = await execute_tool("get_my_progress", Role.STUDENT, "u1", {})
    assert result["found"] is True
    assert result["level"] == "L1"


@pytest.mark.asyncio
async def test_owner_tool_executes_successfully_via_dispatcher():
    result = await execute_tool("get_security_stats", Role.OWNER, "owner1", {})
    assert "flagged_tokens" in result


# ============================================================
#  A3.4 — every dispatch attempt is logged
# ============================================================

def _get_tool_call_rows(discord_id: str) -> list[dict]:
    conn = database._connect()
    rows = conn.execute(
        "SELECT * FROM nour_tool_calls WHERE discord_id=? ORDER BY id", (discord_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@pytest.mark.asyncio
async def test_successful_call_is_logged_with_success_true():
    database.register_member("u1", "Alice")
    await execute_tool("get_my_progress", Role.STUDENT, "u1", {})
    rows = _get_tool_call_rows("u1")
    assert len(rows) == 1
    assert rows[0]["tool_name"] == "get_my_progress"
    assert rows[0]["role"] == "student"
    assert rows[0]["success"] == 1
    assert rows[0]["latency_ms"] is not None


@pytest.mark.asyncio
async def test_rejected_call_is_logged_with_success_false():
    database.register_member("u1", "Alice")
    try:
        await execute_tool("get_student_status", Role.STUDENT, "u1", {})
    except ToolError:
        pass
    rows = _get_tool_call_rows("u1")
    assert len(rows) == 1
    assert rows[0]["success"] == 0
    assert "not permitted" in rows[0]["error_message"]


@pytest.mark.asyncio
async def test_failing_tool_call_is_logged_with_success_false():
    """A tool that IS permitted but raises internally (e.g. no bot
    registered) must still log a failed attempt, not skip logging."""
    owner_tools.set_bot(None)
    try:
        await execute_tool("get_system_health", Role.OWNER, "owner1", {})
    except ToolError:
        pass
    rows = _get_tool_call_rows("owner1")
    assert len(rows) == 1
    assert rows[0]["success"] == 0


@pytest.mark.asyncio
async def test_unknown_tool_call_is_logged():
    database.register_member("u1", "Alice")
    try:
        await execute_tool("not_a_real_tool", Role.STUDENT, "u1", {})
    except ToolError:
        pass
    rows = _get_tool_call_rows("u1")
    assert len(rows) == 1
    assert rows[0]["success"] == 0
