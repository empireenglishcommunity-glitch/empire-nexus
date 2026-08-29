"""Ijtihad Phase 0 — precondition fixes before the effort economy is built.

See .kiro/specs/ijtihad-effort-economy/. Phase 0 changes no intended behaviour;
it removes three defects that would silently corrupt season-scoped scoring:

  0.1 the dashboard XP bar could render NEGATIVE for the best students
  0.2 /api/complete-exercise awarded points but never updated the streak, so
      the same action scored differently on web vs Discord
  0.3 dead points constants (a third state between feature and dead code)
"""
from unittest.mock import AsyncMock, patch

import pytest

from src import api_server, config


# ============================================================
#  0.1 — the XP bar must never be negative
# ============================================================

def test_level_progress_never_negative_for_promoted_student():
    """THE BUG: promotion is exam-gated and awards NO points, but the bar is
    computed as total_points - level_threshold. A student promoted to A2 with
    800 lifetime points rendered (800-2000)/3000 = -40%.

    That punished exactly the students who advance FASTER than they accumulate
    points -- the hardest working ones."""
    xp_in_level, xp_needed, pct = api_server._level_progress(800, "A2")
    assert xp_in_level >= 0, "xp_in_level must never be negative"
    assert pct >= 0.0, f"progress bar must never be negative, got {pct}"
    assert pct == 0.0
    assert xp_needed == (config.CEFR_XP_THRESHOLDS["B1"]
                         - config.CEFR_XP_THRESHOLDS["A2"])


@pytest.mark.parametrize("level", ["A1", "A2", "B1", "B2", "C1", "C2"])
def test_level_progress_never_negative_at_zero_points(level):
    """A freshly promoted student at every level, with no points at all."""
    xp_in_level, _, pct = api_server._level_progress(0, level)
    assert xp_in_level >= 0
    assert 0.0 <= pct <= 100.0


def test_level_progress_is_clamped_to_100_at_top_of_ladder():
    """C2 has no next level -- the bar reads 100%, not a division by zero."""
    xp_in_level, xp_needed, pct = api_server._level_progress(31000, "C2")
    assert pct == 100.0
    assert xp_needed == 0
    assert xp_in_level == 31000


def test_level_progress_never_exceeds_100():
    """A student far past the next threshold still shows a full bar, not 400%."""
    _, _, pct = api_server._level_progress(999_999, "A1")
    assert pct == 100.0


def test_level_progress_midpoint_is_sane():
    """Halfway between A1 (0) and A2 (2000) should read ~50%."""
    xp_in_level, xp_needed, pct = api_server._level_progress(1000, "A1")
    assert xp_in_level == 1000
    assert xp_needed == 2000
    assert pct == 50.0


def test_level_progress_accepts_legacy_level_keys():
    """Legacy L0-L3 records normalise via config.cefr_key() rather than crash."""
    for legacy in ("L0", "L1", "L2", "L3"):
        xp_in_level, _, pct = api_server._level_progress(500, legacy)
        assert xp_in_level >= 0
        assert 0.0 <= pct <= 100.0


def test_level_progress_handles_missing_level():
    """A member row with an empty/None level must not explode."""
    for bad in ("", None):
        xp_in_level, _, pct = api_server._level_progress(100, bad)
        assert xp_in_level >= 0
        assert 0.0 <= pct <= 100.0


# ============================================================
#  0.3 — dead constants resolved
# ============================================================

def test_peer_feedback_constant_is_gone():
    """POINTS_PEER_FEEDBACK was never awarded anywhere and the approved Ijtihad
    design contains no peer-feedback award, so it is deleted rather than left as
    a third state between 'feature' and 'dead code'."""
    assert not hasattr(config, "POINTS_PEER_FEEDBACK")


def test_scheduled_constants_still_exist_for_phase_3():
    """POINTS_ASSESSMENT / POINTS_ADVANCEMENT are deliberately KEPT: Ijtihad
    Phase 3 wires them into real achievement payouts. This test exists so that
    deleting them is a conscious decision, not a silent cleanup."""
    assert config.POINTS_ASSESSMENT == 50
    assert config.POINTS_ADVANCEMENT == 500


# ============================================================
#  0.2 — one award path (web must behave like Discord)
# ============================================================

class _FakeRequest:
    def __init__(self, body):
        self._body = body
        self.headers = {"Origin": ""}

    async def json(self):
        return self._body


@pytest.mark.asyncio
async def test_complete_exercise_routes_through_process_submission():
    """THE BUG: this endpoint called log_submission + add_points directly and
    never called update_streak, so completing a task on the web earned points
    but no streak credit -- while the identical action on Discord (!done) or via
    /api/practice-complete did both.

    It must now go through tasks.process_submission, the same single path, so
    season-scoped sums can never disagree between web and Discord.
    """
    req = _FakeRequest({"token": "tok", "exercise_type": "accent"})
    member = {"discord_id": "555", "discord_name": "Mai"}

    with patch("src.api_server._check_rate_limit", return_value=True), \
         patch("src.database.is_feature_enabled", return_value=True), \
         patch("src.database.get_member_by_token", return_value=member), \
         patch("src.database.update_member"), \
         patch("src.database.tasks_completed_today", return_value=["accent"]), \
         patch("src.api_server._touch_token"), \
         patch("src.database.add_points") as add_points, \
         patch("src.tasks.process_submission",
               new=AsyncMock(return_value={"new": True})) as proc:
        resp = await api_server.post_complete_exercise(req)

    assert resp.status == 200
    proc.assert_awaited_once()
    # The canonical path owns the award now; the endpoint must NOT also award
    # points itself (that would double-count once seasons start summing).
    add_points.assert_not_called()
    awaited_args = proc.await_args.args
    assert awaited_args[0] == "555"
    assert awaited_args[2] == "accent"


@pytest.mark.asyncio
async def test_complete_exercise_is_idempotent_on_duplicate():
    """process_submission returns new=False for a same-day duplicate (its
    log_submission hits the UNIQUE constraint). The endpoint must report
    added=False and must not touch last_active."""
    req = _FakeRequest({"token": "tok", "exercise_type": "vocab"})
    member = {"discord_id": "555", "discord_name": "Mai"}

    with patch("src.api_server._check_rate_limit", return_value=True), \
         patch("src.database.is_feature_enabled", return_value=True), \
         patch("src.database.get_member_by_token", return_value=member), \
         patch("src.database.update_member") as update_member, \
         patch("src.database.tasks_completed_today", return_value=["vocab"]), \
         patch("src.api_server._touch_token"), \
         patch("src.tasks.process_submission",
               new=AsyncMock(return_value={"new": False})):
        resp = await api_server.post_complete_exercise(req)

    assert resp.status == 200
    update_member.assert_not_called()


@pytest.mark.asyncio
async def test_complete_exercise_survives_process_submission_failure():
    """A submission-path hiccup must not 500 the endpoint (the rest of the
    system treats these as best-effort)."""
    req = _FakeRequest({"token": "tok", "exercise_type": "writing"})
    member = {"discord_id": "555", "discord_name": "Mai"}

    with patch("src.api_server._check_rate_limit", return_value=True), \
         patch("src.database.is_feature_enabled", return_value=True), \
         patch("src.database.get_member_by_token", return_value=member), \
         patch("src.database.update_member"), \
         patch("src.database.tasks_completed_today", return_value=[]), \
         patch("src.api_server._touch_token"), \
         patch("src.tasks.process_submission",
               new=AsyncMock(side_effect=RuntimeError("boom"))):
        resp = await api_server.post_complete_exercise(req)

    assert resp.status == 200
