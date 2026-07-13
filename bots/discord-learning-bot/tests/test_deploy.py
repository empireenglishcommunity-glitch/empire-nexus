"""Tests for scripts/deploy.py — Aegis Phase 2 (production-safe-deploys).

Mocks subprocess.run rather than requiring a real Docker daemon, so
these tests are portable to CI and any dev machine. The real
deploy/rollback cycle was ALSO verified live against a real local
Docker/Podman environment before these tests were written (see the
Aegis tasks.md checkpoint for that session) -- that live testing is
what actually found the bug these tests guard against.
"""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_SPEC = importlib.util.spec_from_file_location(
    "deploy", Path(__file__).resolve().parent.parent / "scripts" / "deploy.py"
)
deploy = importlib.util.module_from_spec(_SPEC)
sys.modules["deploy"] = deploy
_SPEC.loader.exec_module(deploy)


def _docker_images_output(*tag_created_pairs):
    """Build a fake `docker images ... --format {{.Tag}}\\t{{.CreatedAt}}`
    stdout string, matching the exact real shape confirmed via live
    testing against a real Docker/Podman daemon."""
    return "\n".join(f"{tag}\t{created}" for tag, created in tag_created_pairs)


def test_prune_excludes_latest_even_though_it_is_the_first_field():
    """Regression test for a real bug found via live Docker testing:
    :latest was being deleted by prune_old_tagged_images() because the
    original filter checked for the substring '\\tlatest' assuming
    'latest' only ever appears as a SECOND field (after a tab) -- but
    .Tag is the FIRST field in this format string, so the real line is
    'latest\\t<timestamp>', with no tab before it. The naive substring
    check silently let :latest through and it got pruned."""
    fake_output = _docker_images_output(
        ("latest", "2026-07-13 12:00:00 +0000 UTC"),
        ("aaa1111", "2026-07-13 11:00:00 +0000 UTC"),
    )
    with patch.object(deploy, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=fake_output)
        deploy.prune_old_tagged_images()

    # Find the "docker rmi" calls (if any) and confirm :latest was never
    # among the tags passed to it.
    rmi_calls = [call for call in mock_run.call_args_list if call.args[0][:2] == ["docker", "rmi"]]
    removed_tags = [call.args[0][2].split(":")[-1] for call in rmi_calls]
    assert "latest" not in removed_tags


def test_prune_keeps_exactly_keep_tagged_images_count():
    tags = [(f"sha{i}", f"2026-07-13 {i:02d}:00:00 +0000 UTC") for i in range(deploy.KEEP_TAGGED_IMAGES + 3)]
    fake_output = _docker_images_output(*tags)
    with patch.object(deploy, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=fake_output)
        deploy.prune_old_tagged_images()

    rmi_calls = [call for call in mock_run.call_args_list if call.args[0][:2] == ["docker", "rmi"]]
    assert len(rmi_calls) == 3  # (KEEP_TAGGED_IMAGES + 3) - KEEP_TAGGED_IMAGES


def test_prune_removes_oldest_first():
    fake_output = _docker_images_output(
        ("newest", "2026-07-13 12:00:00 +0000 UTC"),
        ("oldest", "2026-01-01 00:00:00 +0000 UTC"),
        *[(f"mid{i}", f"2026-06-{i+1:02d} 00:00:00 +0000 UTC") for i in range(deploy.KEEP_TAGGED_IMAGES - 1)],
    )
    with patch.object(deploy, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=fake_output)
        deploy.prune_old_tagged_images()

    rmi_calls = [call for call in mock_run.call_args_list if call.args[0][:2] == ["docker", "rmi"]]
    removed_tags = [call.args[0][2].split(":")[-1] for call in rmi_calls]
    assert removed_tags == ["oldest"]


def test_prune_does_nothing_when_docker_images_fails():
    with patch.object(deploy, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        deploy.prune_old_tagged_images()  # must not raise
    # Only the initial "docker images" call should have happened, no rmi.
    assert mock_run.call_count == 1


def test_prune_handles_empty_image_list():
    with patch.object(deploy, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        deploy.prune_old_tagged_images()  # must not raise
    assert mock_run.call_count == 1
