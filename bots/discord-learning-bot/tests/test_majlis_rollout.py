"""Majlis rollout tool — tests for scripts/majlis_rollout.py.

Majlis has been built since 2026-07-31 and switched off ever since. The tool
that turns it on is therefore the piece of code most likely to be run exactly
once, under time pressure, against production, by someone who did not write it.
That is worth testing more carefully than the average helper.

These tests cover the DB-side behaviour: dry-run safety, the refusal guard
against a big-bang release, pilot allowlists, idempotency, and rollback. The
Discord-side preflight is not covered here — it needs a live gateway, which is
exactly why it is a separate read-only `preflight` subcommand rather than
something baked into `enable`.

The autouse `temp_db` fixture in conftest.py points config.DB_PATH at a fresh
per-test SQLite file, so nothing here can touch a real database.
"""
import importlib.util
import pathlib
import types

import pytest

from src import database, flag_registry

_SCRIPT = (pathlib.Path(__file__).resolve().parent.parent
           / "scripts" / "majlis_rollout.py")


@pytest.fixture()
def mr():
    """Load majlis_rollout.py as a module (it lives in scripts/, not a package)."""
    spec = importlib.util.spec_from_file_location("majlis_rollout", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _flags_present():
    """The tool manages flags that must already exist in feature_flags."""
    database.sync_flag_registry()


def args(**kw):
    return types.SimpleNamespace(
        phase=kw.get("phase", 1), all=kw.get("all", False),
        pilot=kw.get("pilot", ""), yes=kw.get("yes", False))


def st(flag):
    return database.feature_flag_status(flag)


# ============================================================
#  WIRING — the tool must describe the real initiative
# ============================================================

def test_phases_match_the_registry_exactly(mr):
    """If a 7th community flag is ever added, this fails — which is the point.
    A rollout tool that silently ignores a new phase would leave it off forever
    while appearing to enable "all" of Majlis."""
    registry_majlis = {e[0] for e in flag_registry.REGISTRY if e[2] == "majlis"}
    assert set(mr.ALL_FLAGS) == registry_majlis
    assert len(mr.PHASES) == 6


def test_every_phase_has_a_description(mr):
    for phase, (flag, desc) in mr.PHASES.items():
        assert isinstance(phase, int)
        assert flag and isinstance(flag, str)
        assert desc and len(desc) > 20, f"phase {phase} needs a real description"


def test_all_majlis_flags_default_off(mr):
    """Majlis must not be live by accident. Every flag ships default OFF, so a
    fresh database never releases it."""
    for flag in mr.ALL_FLAGS:
        assert not st(flag)["enabled"]


# ============================================================
#  DRY RUN — the default must never write
# ============================================================

def test_enable_without_yes_writes_nothing(mr):
    assert mr.cmd_enable(args(phase=1)) == 0
    assert not st("community_together_credit")["enabled"]


def test_rollback_without_yes_writes_nothing(mr):
    database.set_feature_flag("community_together_credit", True, "", "test")
    assert mr.cmd_rollback(args()) == 0
    assert st("community_together_credit")["enabled"]


# ============================================================
#  THE REFUSAL GUARD
# ============================================================

def test_all_phases_to_everyone_is_refused(mr):
    """--all + everyone + --yes is the big-bang release Aegis exists to prevent.
    It must refuse AND write nothing."""
    assert mr.cmd_enable(args(all=True, yes=True)) == 1
    for flag in mr.ALL_FLAGS:
        assert not st(flag)["enabled"], "a refused release must not write"


def test_all_phases_with_pilot_is_allowed(mr):
    """The blast radius is bounded by the allowlist, so --all is fine here."""
    assert mr.cmd_enable(args(all=True, pilot="333", yes=True)) == 0
    for flag in mr.ALL_FLAGS:
        s = st(flag)
        assert s["enabled"] and not s["everyone"]
        assert "333" in s["allowed_ids"]


def test_unknown_phase_is_rejected(mr):
    assert mr.cmd_enable(args(phase=99, yes=True)) == 1
    for flag in mr.ALL_FLAGS:
        assert not st(flag)["enabled"]


# ============================================================
#  PILOT -> EVERYONE
# ============================================================

def test_pilot_release_limits_to_the_allowlist(mr):
    assert mr.cmd_enable(args(phase=1, pilot="111,222", yes=True)) == 0
    s = st("community_together_credit")
    assert s["enabled"]
    assert not s["everyone"]
    assert s["allowed_ids"] == {"111", "222"}


def test_a_phase_does_not_leak_into_other_phases(mr):
    mr.cmd_enable(args(phase=1, pilot="111", yes=True))
    for flag in mr.ALL_FLAGS[1:]:
        assert not st(flag)["enabled"]


def test_regrant_is_idempotent(mr):
    mr.cmd_enable(args(phase=1, pilot="111,222", yes=True))
    mr.cmd_enable(args(phase=1, pilot="111", yes=True))
    assert st("community_together_credit")["allowed_ids"] == {"111", "222"}


def test_widening_to_everyone_clears_the_allowlist(mr):
    mr.cmd_enable(args(phase=1, pilot="111", yes=True))
    mr.cmd_enable(args(phase=1, yes=True))
    s = st("community_together_credit")
    assert s["everyone"]
    assert s["allowed_ids"] == set()


def test_enabling_an_already_public_flag_is_a_noop(mr):
    mr.cmd_enable(args(phase=1, yes=True))
    assert mr.cmd_enable(args(phase=1, yes=True)) == 0
    assert st("community_together_credit")["everyone"]


# ============================================================
#  ROLLBACK — the kill switch
# ============================================================

def test_rollback_disables_every_phase(mr):
    for phase in mr.PHASES:
        mr.cmd_enable(args(phase=phase, pilot="111", yes=True))
    assert mr.cmd_rollback(args(yes=True)) == 0
    for flag in mr.ALL_FLAGS:
        s = st(flag)
        assert not s["enabled"]
        assert s["allowed_ids"] == set(), "a stale allowlist must not survive"


def test_rollback_is_idempotent(mr):
    mr.cmd_enable(args(phase=1, yes=True))
    mr.cmd_rollback(args(yes=True))
    assert mr.cmd_rollback(args(yes=True)) == 0
    for flag in mr.ALL_FLAGS:
        assert not st(flag)["enabled"]


def test_rollback_then_enable_starts_from_everyone_not_a_stale_pilot(mr):
    """Disabling clears the allowlist, so a later plain enable is a genuine
    full release rather than silently inheriting an old beta list."""
    mr.cmd_enable(args(phase=1, pilot="111", yes=True))
    mr.cmd_rollback(args(yes=True))
    mr.cmd_enable(args(phase=1, yes=True))
    assert st("community_together_credit")["everyone"]


def test_rollback_does_not_delete_student_data(mr):
    """Disabling stops new accrual; it must never claw back what students
    already earned."""
    database.register_member("111", "Pilot Student")
    database.add_together_minutes("111", 7)
    mr.cmd_enable(args(phase=1, yes=True))
    mr.cmd_rollback(args(yes=True))
    assert database.get_together_minutes("111") == 7


# ============================================================
#  STATUS — read-only
# ============================================================

def test_status_never_writes(mr):
    before = {f: st(f) for f in mr.ALL_FLAGS}
    assert mr.cmd_status(args()) == 0
    assert {f: st(f) for f in mr.ALL_FLAGS} == before
