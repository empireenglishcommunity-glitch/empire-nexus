#!/usr/bin/env python3
"""
Deploy script for the Empire English Community Bot — Aegis Phase 2
(production-safe-deploys spec, .kiro/specs/production-safe-deploys/).

Wraps the full deploy sequence into ONE command, so "did I remember to
back up first" and "did I remember to tag the image before overwriting
:latest" stop being things a human has to remember every single time:

    1. Take a pre-deploy database backup, tagged with the current git SHA
    2. Build the new Docker image
    3. Tag the freshly-built image with the git SHA (BEFORE it becomes
       :latest) so rollback.py has something concrete to roll back to
    4. Swap the running container to the new image
    5. Run scripts/health_check.py against it
    6. If unhealthy: print the exact rollback.py command and exit non-zero
       (does NOT automatically roll back -- an operator should look at
       WHY it's unhealthy first, not just blindly revert every time)

Run this FROM THE HOST (not inside the container -- it needs to run
`docker` commands against the container, and a container can't easily
manage its own replacement from inside itself):

    cd /opt/empire-english-bot && python3 scripts/deploy.py

This is intentionally a thin script over the docker-compose.yml that
already exists, not a competing deployment system -- for a routine
change with no reason for extra caution, `docker compose up -d --build`
by itself still works exactly as before. Use this script specifically
when you want the backup-before-and-tag-for-rollback safety net.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGE_NAME = "empire-english-bot-empire-english-bot"
CONTAINER_NAME = "empire-english-bot"
KEEP_TAGGED_IMAGES = 5  # matches design.md's Component 2: cheap on disk,
                        # makes "go back two deploys" possible without a rebuild


def run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    """Run a command, always printing it first (deploys should never be
    a black box), and raise on failure unless the caller opts out."""
    print(f"$ {' '.join(cmd)}")
    check = kwargs.pop("check", True)
    return subprocess.run(cmd, cwd=REPO_ROOT, check=check, **kwargs)


def get_git_sha() -> str:
    result = run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip()


def get_git_commit_summary() -> str:
    result = run(["git", "log", "-1", "--format=%s"], capture_output=True, text=True)
    return result.stdout.strip()


def prune_old_tagged_images():
    """Keep only the most recent KEEP_TAGGED_IMAGES tags of
    empire-english-bot (git-SHA-tagged images from previous deploys),
    dropping older ones. Never touches :latest or untagged/dangling
    layers here -- `docker image prune` (routine, unrelated to this
    script) already handles dangling layers on its own schedule.
    """
    result = run(
        ["docker", "images", CONTAINER_NAME, "--format", "{{.Tag}}\t{{.CreatedAt}}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return
    # Found via live testing against a real Docker/Podman image list: a
    # naive substring check for "\tlatest" (assuming "latest" only ever
    # appears as a SECOND field, after a tab) silently let :latest itself
    # through, because .Tag is the FIRST field here -- the real line is
    # "latest\t<timestamp>", with no tab BEFORE "latest". Parse the tag
    # field explicitly instead of guessing at substring shapes.
    pairs = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip() or "\t" not in line:
            continue
        tag, created_at = line.split("\t", 1)
        if tag != "latest":
            pairs.append((tag, created_at))
    # Docker's own --format ordering isn't guaranteed sorted; sort by
    # CreatedAt newest-first so we reliably keep the KEEP_TAGGED_IMAGES
    # most recent, not an arbitrary set.
    pairs.sort(key=lambda p: p[1], reverse=True)
    tags_to_remove = [tag for tag, _ in pairs[KEEP_TAGGED_IMAGES:]]
    for tag in tags_to_remove:
        print(f"🗑️  Pruning old tagged image: {CONTAINER_NAME}:{tag}")
        run(["docker", "rmi", f"{CONTAINER_NAME}:{tag}"], check=False)


def deploy(skip_backup: bool = False) -> int:
    git_sha = get_git_sha()
    commit_summary = get_git_commit_summary()
    print(f"🚀 Deploying {git_sha} — {commit_summary}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    if not skip_backup:
        print("\n📦 Step 1/5: Pre-deploy backup")
        result = run(
            ["docker", "exec", CONTAINER_NAME, "python3", "scripts/backup.py", "--tag", f"pre-deploy-{git_sha}"],
            check=False,
        )
        if result.returncode != 0:
            print("⚠️  Pre-deploy backup failed or container wasn't running yet (fine on a first-ever deploy) — continuing.")
    else:
        print("\n📦 Step 1/5: Pre-deploy backup — SKIPPED (--skip-backup)")

    print("\n🔨 Step 2/5: Building image")
    run(["docker", "compose", "build", "--pull"])

    print(f"\n🏷️  Step 3/5: Tagging image as {CONTAINER_NAME}:{git_sha}")
    run(["docker", "tag", f"{IMAGE_NAME}:latest", f"{CONTAINER_NAME}:{git_sha}"])

    print("\n🔄 Step 4/5: Swapping container to the new image")
    # Set maintenance mode BEFORE the swap so the bot shows "Updating..."
    # during the few seconds of restart (picked up by the heartbeat loop
    # within 2 minutes, or immediately if the bot's own on_ready fires)
    run(
        ["docker", "exec", CONTAINER_NAME, "python3", "-c",
         "import sys; sys.path.insert(0,'.'); from src import database; database.init_db(); database.set_setting('maintenance_mode', 'on')"],
        check=False,
    )
    run(["docker", "compose", "up", "-d"])

    print("\n⏳ Waiting 5s for startup before health check...")
    time.sleep(5)

    print("\n🩺 Step 5/5: Health check")
    health_result = run(
        ["docker", "exec", CONTAINER_NAME, "python3", "scripts/health_check.py"],
        check=False,
    )

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if health_result.returncode == 0:
        print(f"✅ Deploy successful: {git_sha}")
        prune_old_tagged_images()

        # Turn off maintenance mode (if it was set before the deploy)
        run(
            ["docker", "exec", CONTAINER_NAME, "python3", "-c",
             "import sys; sys.path.insert(0,'.'); from src import database; database.init_db(); database.set_setting('maintenance_mode', 'off')"],
            check=False,
        )

        # Post to #dev-log (best-effort — never blocks a successful deploy)
        print("\n📝 Posting to #dev-log...")
        run(
            ["docker", "exec", CONTAINER_NAME, "python3", "scripts/post_deploy_log.py",
             "--sha", git_sha, "--message", commit_summary],
            check=False,
        )
        return 0
    else:
        print(f"❌ HEALTH CHECK FAILED after deploying {git_sha}.")
        print("   To roll back: python3 scripts/rollback.py")
        print(f"   (Or manually: docker tag {CONTAINER_NAME}:<previous-sha> {IMAGE_NAME}:latest && docker compose up -d)")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-backup", action="store_true", help="Skip the pre-deploy backup step (not recommended)")
    args = parser.parse_args()
    return deploy(skip_backup=args.skip_backup)


if __name__ == "__main__":
    sys.exit(main())
