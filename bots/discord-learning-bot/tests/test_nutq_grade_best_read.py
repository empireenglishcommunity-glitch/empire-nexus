"""Nutq grade-best-read model (PR2).

Covers the pieces of the "🏅 Grade my best read (1×/day)" feature that are
unit-testable without an HTTP harness:
  - per-student daily cap override CRUD (owner control groundwork for PR3)
  - api_server._nutq_daily_cap resolver (global default vs override)
  - ScoringResult.engine tag (so grade-best-read can tell Azure from local)
"""
import pytest

from src import api_server, database, config
from src import pronunciation_scorer as ps


@pytest.fixture
def member():
    database.register_member("905grade", "Grade Best Read Test")
    return "905grade"


# ── per-student daily cap override (PR3 will expose /nutq cap) ──────────────
def test_cap_override_crud(member):
    assert database.nutq_daily_cap_override(member) is None      # default: no override
    database.set_nutq_daily_cap_override(member, 3)
    assert database.nutq_daily_cap_override(member) == 3
    database.set_nutq_daily_cap_override(member, 5)              # upsert
    assert database.nutq_daily_cap_override(member) == 5
    database.clear_nutq_daily_cap_override(member)
    assert database.nutq_daily_cap_override(member) is None      # reverts to global


def test_cap_override_floors_at_zero(member):
    database.set_nutq_daily_cap_override(member, -2)
    assert database.nutq_daily_cap_override(member) == 0
    database.clear_nutq_daily_cap_override(member)


# ── api_server cap resolver ────────────────────────────────────────────────
def test_nutq_daily_cap_defaults_to_global(member):
    assert api_server._nutq_daily_cap(member) == config.NUTQ_AZURE_MAX_CALLS_PER_DAY


def test_nutq_daily_cap_honours_override(member):
    database.set_nutq_daily_cap_override(member, 4)
    assert api_server._nutq_daily_cap(member) == 4
    database.clear_nutq_daily_cap_override(member)


# ── engine tag on the scoring result ───────────────────────────────────────
def test_scoring_result_engine_defaults_local():
    r = ps.ScoringResult(score=1, raw_score=1, transcript="", expected_text="",
                         missed_words=[], feedback_en="", feedback_ar="")
    assert r.engine == "local"
