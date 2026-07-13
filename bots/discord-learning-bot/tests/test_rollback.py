"""Tests for scripts/rollback.py — Aegis Phase 2 (production-safe-deploys).

Mocks subprocess.run rather than requiring a real Docker daemon (see
test_deploy.py's module docstring for the same rationale — the real
mechanism was also verified live against a real Docker/Podman
environment, which is what found the bug test_list_tagged_images_
excludes_latest guards against).
"""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_SPEC = importlib.util.spec_from_file_location(
    "rollback", Path(__file__).resolve().parent.parent / "scripts" / "rollback.py"
)
rollback = importlib.util.module_from_spec(_SPEC)
sys.modules["rollback"] = rollback
_SPEC.loader.exec_module(rollback)


def _docker_images_output(*tag_created_pairs):
    return "\n".join(f"{tag}\t{created}" for tag, created in tag_created_pairs)


def test_list_tagged_images_excludes_latest():
    """Regression test for the identical bug found and fixed in
    deploy.py's prune_old_tagged_images() — see test_deploy.py for the
    full explanation. rollback.py had the same naive substring filter."""
    fake_output = _docker_images_output(
        ("latest", "2026-07-13 12:00:00 +0000 UTC"),
        ("aaa1111", "2026-07-13 11:00:00 +0000 UTC"),
    )
    with patch.object(rollback, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=fake_output)
        result = rollback.list_tagged_images()

    tags = [tag for tag, _ in result]
    assert "latest" not in tags
    assert "aaa1111" in tags


def test_list_tagged_images_sorted_newest_first():
    fake_output = _docker_images_output(
        ("older", "2026-01-01 00:00:00 +0000 UTC"),
        ("newer", "2026-07-01 00:00:00 +0000 UTC"),
    )
    with patch.object(rollback, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=fake_output)
        result = rollback.list_tagged_images()

    assert [tag for tag, _ in result] == ["newer", "older"]


def test_list_tagged_images_empty_when_docker_images_fails():
    with patch.object(rollback, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert rollback.list_tagged_images() == []


def test_rollback_fails_cleanly_with_no_tagged_images():
    with patch.object(rollback, "list_tagged_images", return_value=[]):
        exit_code = rollback.rollback()
    assert exit_code == 1


def test_rollback_fails_cleanly_for_unknown_sha():
    with patch.object(rollback, "list_tagged_images", return_value=[("aaa1111", "2026-07-13")]):
        exit_code = rollback.rollback(target_sha="never-existed")
    assert exit_code == 1


def test_rollback_defaults_to_most_recent_when_no_sha_given():
    with patch.object(rollback, "list_tagged_images", return_value=[("newest", "2026-07-13"), ("older", "2026-07-12")]):
        with patch.object(rollback, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            rollback.rollback()

    # The docker tag call should reference "newest", not "older" --
    # args[0] is the full command list, e.g.
    # ["docker", "tag", "empire-english-bot:newest", "...:latest"].
    tag_calls = [call for call in mock_run.call_args_list if call.args[0][:2] == ["docker", "tag"]]
    assert len(tag_calls) == 1
    assert "newest" in tag_calls[0].args[0][2]
