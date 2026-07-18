"""Tests for Aql (#15) Phase A8.4/A8.5 — Shadow Mode.

Covers:
- A8.4: enable_self_test() correctly restricts nour_aql_core to the
  owner's own Discord ID via the EXISTING set_feature_flag allowlist
  mechanism -- not a new one -- and fails loudly if OWNER_DISCORD_ID
  is unset rather than silently enabling for an empty allowlist
  (which existing flag semantics would treat as "on for everyone").
- A8.5: run_shadow_check() never returns anything for a non-eligible
  caller (near-zero cost path), correctly runs the NEW pipeline
  alongside a provided OLD response for an eligible caller, never
  raises even if the NEW pipeline itself raises, and persists a
  correct comparison record either way.
"""
from unittest.mock import AsyncMock, patch

import pytest

from src import config, database
from src.nour import shadow
from src.nour.roles import Role


# ============================================================
#  A8.4 — enable_self_test()
# ============================================================

def test_enable_self_test_raises_without_owner_discord_id(monkeypatch):
    monkeypatch.setattr(config, "OWNER_DISCORD_ID", "")
    with pytest.raises(ValueError):
        shadow.enable_self_test()


def test_enable_self_test_restricts_to_owner_only(monkeypatch):
    monkeypatch.setattr(config, "OWNER_DISCORD_ID", "owner1")
    database.register_member("owner1", "Owner")
    database.register_member("student1", "Student")

    shadow.enable_self_test()

    assert database.is_feature_enabled("nour_aql_core", "owner1") is True
    assert database.is_feature_enabled("nour_aql_core", "student1") is False


def test_enable_self_test_does_not_enable_for_everyone(monkeypatch):
    """The exact failure mode this function's docstring warns about:
    an empty allowlist would mean 'on for everyone' under existing
    flag semantics -- confirm this never happens by accident."""
    monkeypatch.setattr(config, "OWNER_DISCORD_ID", "owner1")
    shadow.enable_self_test()
    assert database.is_feature_enabled("nour_aql_core", "some_random_student_id") is False
    assert database.is_feature_enabled("nour_aql_core", None) is False


def test_is_shadow_eligible_reflects_the_real_flag_state(monkeypatch):
    monkeypatch.setattr(config, "OWNER_DISCORD_ID", "owner1")
    assert shadow.is_shadow_eligible("owner1") is False  # not enabled yet
    shadow.enable_self_test()
    assert shadow.is_shadow_eligible("owner1") is True
    assert shadow.is_shadow_eligible("someone_else") is False


# ============================================================
#  A8.5 — run_shadow_check()
# ============================================================

@pytest.mark.asyncio
async def test_run_shadow_check_returns_none_for_non_eligible_caller():
    """The near-zero-cost path -- must not even attempt to run the
    new pipeline for a caller not on the allowlist."""
    new_pipeline_mock = AsyncMock(return_value="should never be called")
    with patch("src.nour.orchestrator.handle_message", new=new_pipeline_mock):
        result = await shadow.run_shadow_check("not_eligible", "test", old_response="old")

    assert result is None
    new_pipeline_mock.assert_not_called()


@pytest.mark.asyncio
async def test_run_shadow_check_runs_new_pipeline_for_eligible_caller(monkeypatch):
    monkeypatch.setattr(config, "OWNER_DISCORD_ID", "owner1")
    database.register_member("owner1", "Owner")
    shadow.enable_self_test()

    new_pipeline_mock = AsyncMock(return_value="رد جديد من الأورشستريتور")
    with patch("src.nour.orchestrator.handle_message", new=new_pipeline_mock):
        result = await shadow.run_shadow_check("owner1", "سؤال تجريبي", old_response="رد قديم")

    new_pipeline_mock.assert_called_once()
    assert result["old_response"] == "رد قديم"
    assert result["new_response"] == "رد جديد من الأورشستريتور"
    assert result["responses_match"] is False
    assert result["error"] is None


@pytest.mark.asyncio
async def test_run_shadow_check_detects_matching_responses(monkeypatch):
    monkeypatch.setattr(config, "OWNER_DISCORD_ID", "owner1")
    database.register_member("owner1", "Owner")
    shadow.enable_self_test()

    async def fake_new(discord_id, text):
        return "نفس الرد بالضبط"

    with patch("src.nour.orchestrator.handle_message", new=fake_new):
        result = await shadow.run_shadow_check("owner1", "سؤال", old_response="نفس الرد بالضبط")

    assert result["responses_match"] is True


@pytest.mark.asyncio
async def test_run_shadow_check_never_raises_when_new_pipeline_fails(monkeypatch):
    """The core safety guarantee: shadow mode existing at all must
    never be able to break anything, even if the NEW pipeline itself
    throws an exception."""
    monkeypatch.setattr(config, "OWNER_DISCORD_ID", "owner1")
    database.register_member("owner1", "Owner")
    shadow.enable_self_test()

    async def broken_new(discord_id, text):
        raise RuntimeError("simulated new-pipeline crash")

    with patch("src.nour.orchestrator.handle_message", new=broken_new):
        result = await shadow.run_shadow_check("owner1", "سؤال", old_response="رد قديم")  # must not raise

    assert result["new_response"] is None
    assert result["error"] is not None
    assert "simulated new-pipeline crash" in result["error"]
    assert result["responses_match"] is False


@pytest.mark.asyncio
async def test_run_shadow_check_handles_none_old_response(monkeypatch):
    """old_response can legitimately be None (e.g. the old pipeline
    itself produced no response) -- must not crash on that either."""
    monkeypatch.setattr(config, "OWNER_DISCORD_ID", "owner1")
    database.register_member("owner1", "Owner")
    shadow.enable_self_test()

    async def fake_new(discord_id, text):
        return "رد جديد"

    with patch("src.nour.orchestrator.handle_message", new=fake_new):
        result = await shadow.run_shadow_check("owner1", "سؤال", old_response=None)

    assert result["old_response"] is None
    assert result["responses_match"] is False


@pytest.mark.asyncio
async def test_run_shadow_check_persists_a_real_comparison_row(monkeypatch):
    monkeypatch.setattr(config, "OWNER_DISCORD_ID", "owner1")
    database.register_member("owner1", "Owner")
    shadow.enable_self_test()

    async def fake_new(discord_id, text):
        return "رد جديد للتحقق من التخزين"

    with patch("src.nour.orchestrator.handle_message", new=fake_new):
        await shadow.run_shadow_check("owner1", "سؤال التخزين", old_response="رد قديم للتحقق")

    rows = database.get_shadow_comparisons("owner1")
    assert len(rows) == 1
    assert rows[0]["old_response"] == "رد قديم للتحقق"
    assert rows[0]["new_response"] == "رد جديد للتحقق من التخزين"
    assert rows[0]["role"] == "owner"


@pytest.mark.asyncio
async def test_run_shadow_check_includes_resolved_role(monkeypatch):
    monkeypatch.setattr(config, "OWNER_DISCORD_ID", "owner1")
    database.register_member("owner1", "Owner")
    shadow.enable_self_test()

    async def fake_new(discord_id, text):
        return "رد"

    with patch("src.nour.orchestrator.handle_message", new=fake_new):
        result = await shadow.run_shadow_check("owner1", "سؤال", old_response="قديم")

    assert result["role"] == Role.OWNER.value


# ============================================================
#  database.py shadow-comparison functions
# ============================================================

def test_log_shadow_comparison_and_read_back():
    database.log_shadow_comparison(
        discord_id="u1", role="student", text="test",
        old_response="old", new_response="new",
        error=None, responses_match=False,
    )
    rows = database.get_shadow_comparisons("u1")
    assert len(rows) == 1
    assert rows[0]["text"] == "test"
    assert rows[0]["responses_match"] == 0


def test_get_shadow_comparisons_without_discord_id_returns_all():
    database.log_shadow_comparison("u1", "student", "t1", "o1", "n1", None, False)
    database.log_shadow_comparison("u2", "owner", "t2", "o2", "n2", None, True)
    rows = database.get_shadow_comparisons()
    assert len(rows) == 2


def test_count_shadow_comparisons_matches_only():
    database.log_shadow_comparison("u1", "student", "t1", "same", "same", None, True)
    database.log_shadow_comparison("u2", "student", "t2", "old", "new", None, False)
    assert database.count_shadow_comparisons() == 2
    assert database.count_shadow_comparisons(matches_only=True) == 1


def test_log_shadow_comparison_handles_none_values_gracefully():
    database.log_shadow_comparison(
        discord_id="u1", role=None, text="test",
        old_response=None, new_response=None,
        error="some error", responses_match=False,
    )
    rows = database.get_shadow_comparisons("u1")
    assert rows[0]["old_response"] == ""
    assert rows[0]["new_response"] == ""
    assert rows[0]["error"] == "some error"
