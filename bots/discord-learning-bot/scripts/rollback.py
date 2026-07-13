#!/usr/bin/env python3
"""
Rollback script for the Empire English Community Bot — Aegis Phase 2
(production-safe-deploys spec, .kiro/specs/production-safe-deploys/).

Reverts the running container to a previous git-SHA-tagged image (one
that scripts/deploy.py tagged during an earlier deploy, BEFORE
overwriting :latest — see that script for why the tagging order
matters). Directly satisfies Requirement 3.3's "single documented
command sequence" for undoing a bad deploy.

Usage:
    python3 scripts/rollback.py                # roll back to the most
                                                # recent tagged image
                                                # OTHER than whatever
                                                # :latest currently is
    python3 scripts/rollback.py <git-sha>       # roll back to a specific
                                                # tagged image
    python3 scripts/rollback.py --list          # show available tagged
                                                # images to roll back to

This only reverts the CODE (the running container image). If the
database itself also needs reverting — e.g. a bad deploy corrupted data,
not just broke behavior — that is a SEPARATE, deliberate manual step,
NOT automated here, because restoring a database backup is destructive
and should never happen as a side effect of an otherwise-routine code
rollback:

    # 1. Stop the bot so nothing writes to the database mid-restore:
    docker compose stop empire-english-bot
    # 2. Find the pre-deploy backup you want (scripts/backup.py --tag
    #    labels these as empire_english_pre-deploy-<sha>_<timestamp>.db):
    docker exec empire-english-bot ls -la /app/backups/
    # 3. Copy it over the live database file (INSIDE the container's
    #    volume mount, so it lands in the same place the bot reads from):
    docker exec empire-english-bot cp /app/backups/<chosen-backup>.db /app/data_persist/empire_english.db
    # 4. Restart:
    docker compose up -d empire-english-bot
"""
import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGE_NAME = "empire-english-bot-empire-english-bot"
CONTAINER_NAME = "empire-english-bot"


def run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    check = kwargs.pop("check", True)
    return subprocess.run(cmd, cwd=REPO_ROOT, check=check, **kwargs)


def list_tagged_images() -> list[tuple[str, str]]:
    """Returns [(tag, created_at), ...] for every non-:latest tag of
    this bot's image, newest first."""
    result = run(
        ["docker", "images", CONTAINER_NAME, "--format", "{{.Tag}}\t{{.CreatedAt}}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    # Same fix as deploy.py's prune_old_tagged_images(): .Tag is the
    # FIRST field in this format string, so "latest" never has a tab
    # before it -- a naive "\tlatest" substring check silently lets
    # :latest itself through the filter. Parse the tag field explicitly.
    pairs = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip() or "\t" not in line:
            continue
        tag, created_at = line.split("\t", 1)
        if tag != "latest":
            pairs.append((tag, created_at))
    pairs.sort(key=lambda p: p[1], reverse=True)
    return pairs


def rollback(target_sha: str = None) -> int:
    available = list_tagged_images()
    if not available:
        print(f"❌ No tagged images found for {CONTAINER_NAME}. Nothing to roll back to.")
        print("   (Tagged images are created by scripts/deploy.py on every deploy — if none")
        print("    exist yet, this may be the first deploy since Aegis Phase 2 was adopted.)")
        return 1

    if target_sha is None:
        target_sha = available[0][0]
        print(f"ℹ️  No SHA given — rolling back to the most recent tagged image: {target_sha}")
    elif target_sha not in [tag for tag, _ in available]:
        print(f"❌ No image tagged {CONTAINER_NAME}:{target_sha} exists.")
        print("   Available:", ", ".join(tag for tag, _ in available))
        return 1

    print(f"🔙 Rolling back to {target_sha}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    run(["docker", "tag", f"{CONTAINER_NAME}:{target_sha}", f"{IMAGE_NAME}:latest"])
    run(["docker", "compose", "up", "-d"])

    print("\n🩺 Running health check against the rolled-back version...")
    health_result = run(
        ["docker", "exec", CONTAINER_NAME, "python3", "scripts/health_check.py"],
        check=False,
    )
    if health_result.returncode == 0:
        print(f"\n✅ Rolled back to {target_sha} and confirmed healthy.")
        return 0
    else:
        print(f"\n⚠️  Rolled back to {target_sha}, but the health check STILL failed.")
        print("   This means the problem is likely NOT the code you just rolled back from —")
        print("   check the database, environment variables, or external dependencies")
        print("   (Discord API, AI provider keys) before rolling back further.")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sha", nargs="?", default=None, help="Git SHA to roll back to (default: most recent tagged image)")
    parser.add_argument("--list", action="store_true", help="List available tagged images and exit, without rolling back")
    args = parser.parse_args()

    if args.list:
        available = list_tagged_images()
        if not available:
            print(f"No tagged images found for {CONTAINER_NAME}.")
            return 0
        print(f"Available tagged images for {CONTAINER_NAME} (newest first):")
        for tag, created_at in available:
            print(f"  {tag}  ({created_at})")
        return 0

    return rollback(args.sha)


if __name__ == "__main__":
    sys.exit(main())
