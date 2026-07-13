#!/usr/bin/env python3
"""Post a one-line deploy summary to the #dev-log channel.

Called by deploy.py after a successful health check. Uses the bot's own
Discord token (from the .env file or DISCORD_TOKEN env var) to send a
single message — no webhook, no new secrets, no new infrastructure.

Usage (from deploy.py, inside the container):
    python3 scripts/post_deploy_log.py --sha abc1234 --message "Fix streak bonus"

Or manually:
    python3 scripts/post_deploy_log.py --sha $(git rev-parse --short HEAD) \
        --message "$(git log -1 --format=%s)"

Environment:
    DISCORD_TOKEN  — the bot's token (reads from .env if present)
    GUILD_ID       — the guild to post in (reads from .env if present)

The script finds #dev-log by name in the guild's channels. If the
channel doesn't exist yet (setup_server.py hasn't been re-run since
Phase 5), the script exits 0 with a warning — it should never block
a deploy.
"""
import argparse
import asyncio
import datetime
import os
import sys

# Load .env if available (same as the bot itself does)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import discord


CHANNEL_NAME = "dev-log"


async def post_log(token: str, guild_id: int, sha: str, message: str):
    """Connect, post one message to #dev-log, disconnect."""
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    posted = False

    @client.event
    async def on_ready():
        nonlocal posted
        guild = client.get_guild(guild_id)
        if not guild:
            print(f"WARNING: guild {guild_id} not found — skipping dev-log post", file=sys.stderr)
            await client.close()
            return

        channel = discord.utils.get(guild.text_channels, name=CHANNEL_NAME)
        if not channel:
            print(f"WARNING: #{CHANNEL_NAME} channel not found in guild — skipping dev-log post", file=sys.stderr)
            await client.close()
            return

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        log_line = f"\U0001f680 `{sha}` — {message} ({timestamp})"

        try:
            await channel.send(log_line)
            posted = True
            print(f"Posted to #{CHANNEL_NAME}: {log_line}")
        except discord.Forbidden:
            print(f"WARNING: no permission to post in #{CHANNEL_NAME}", file=sys.stderr)
        except discord.HTTPException as e:
            print(f"WARNING: failed to post to #{CHANNEL_NAME}: {e}", file=sys.stderr)

        await client.close()

    try:
        await asyncio.wait_for(client.start(token), timeout=30)
    except asyncio.TimeoutError:
        print("WARNING: Discord connection timed out — skipping dev-log post", file=sys.stderr)
    except Exception as e:
        print(f"WARNING: Discord error — {e}", file=sys.stderr)

    return posted


def main():
    parser = argparse.ArgumentParser(description="Post a deploy log entry to #dev-log")
    parser.add_argument("--sha", required=True, help="Git SHA (short) of the deployed commit")
    parser.add_argument("--message", required=True, help="One-line commit message / deploy summary")
    args = parser.parse_args()

    token = os.environ.get("DISCORD_TOKEN", "")
    guild_id_str = os.environ.get("GUILD_ID", "0")

    if not token:
        print("WARNING: DISCORD_TOKEN not set — skipping dev-log post", file=sys.stderr)
        sys.exit(0)  # never block a deploy

    try:
        guild_id = int(guild_id_str)
    except ValueError:
        print(f"WARNING: GUILD_ID '{guild_id_str}' is not a valid integer — skipping", file=sys.stderr)
        sys.exit(0)

    if guild_id == 0:
        print("WARNING: GUILD_ID not set — skipping dev-log post", file=sys.stderr)
        sys.exit(0)

    asyncio.run(post_log(token, guild_id, args.sha, args.message))
    # Always exit 0 — dev-log posting should never block a deploy
    sys.exit(0)


if __name__ == "__main__":
    main()
