"""Tests for api_server.py.

Includes a regression test for D036: the dashboard's real milestone
catalog helper must return the same IDs used everywhere else in the
system (milestones.json, ability_milestones, !markmilestone) -- the
web dashboard's frontend previously used a hardcoded, entirely
fictional list of IDs with zero overlap with any real milestone_id.
"""
import json

from src import api_server


def test_get_milestones_catalog_returns_real_ids():
    catalog = api_server._get_milestones_catalog()
    assert len(catalog) > 0
    ids = {m["id"] for m in catalog}
    # These are real IDs from content/milestones/milestones.json --
    # confirming the catalog is reading the real source of truth, not
    # a stale/hardcoded list.
    assert "l0_introduce" in ids
    assert "l0_count100" in ids


def test_get_milestones_catalog_matches_milestones_json_exactly():
    """D036 regression: the catalog's IDs must be an exact match for
    milestones.json's real IDs -- this is the file !markmilestone and
    narrative_engine.py both read from, the actual source of truth."""
    with open(api_server._MILESTONES_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    expected_ids = {m["id"] for items in raw.values() for m in items}

    catalog = api_server._get_milestones_catalog()
    actual_ids = {m["id"] for m in catalog}

    assert actual_ids == expected_ids


def test_get_milestones_catalog_excludes_fictional_ids_from_the_old_bug():
    """D036: the OLD hardcoded dashboard list used IDs like
    'first_recording', 'streak_7', 'level_l1' -- none of these are
    real milestone IDs, and the real catalog must never contain
    them."""
    catalog = api_server._get_milestones_catalog()
    ids = {m["id"] for m in catalog}
    fictional_ids = {
        "first_recording", "streak_7", "streak_14", "streak_30",
        "first_assessment", "pronunciation_80", "srs_50", "srs_100",
        "level_l1", "level_l2", "level_l3", "conversation_first",
    }
    assert ids.isdisjoint(fictional_ids)


def test_get_milestones_catalog_each_entry_has_required_fields():
    catalog = api_server._get_milestones_catalog()
    for m in catalog:
        assert m["id"]
        assert m["name"]
        assert m["level"] in ("L0", "L1", "L2")



# ============================================================
#  AUDIT FIX: api_server must use Asia/Dubai "today", never the
#  server/UTC clock, so it can't disagree with how the rest of the
#  bot logs/reads submissions (the "did it but still shows remaining"
#  class of bug). All date-sensitive handlers now route through
#  database._today_local(); guard against a naive datetime.date.today()
#  creeping back in.
# ============================================================

import re
from pathlib import Path


def test_api_server_has_no_naive_date_today():
    src = Path(api_server.__file__).read_text(encoding="utf-8")
    # Strip comments so explanatory prose mentioning the old call doesn't
    # trip the guard.
    code = "\n".join(
        line.split("#", 1)[0] for line in src.splitlines()
    )
    offenders = re.findall(r"datetime\.date\.today\(\)", code)
    assert not offenders, (
        "api_server.py must use database._today_local() (Asia/Dubai), not "
        "naive datetime.date.today() (=server/UTC) — it would disagree with "
        "Dubai-logged submissions during the 00:00-04:00 window."
    )


def test_api_server_references_today_local():
    """Positive check: the module actually calls the shared Dubai helper."""
    src = Path(api_server.__file__).read_text(encoding="utf-8")
    assert "database._today_local()" in src
