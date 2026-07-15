#!/usr/bin/env python3
"""Hisn H1.6-H1.8 — Live Channel/Permission Audit.

Queries the live Discord server (via the bot's own REST API access)
for every category's permission overwrites and child channels, printed
in a format suitable for manual reconciliation against
setup_server.py's CATEGORIES_CONFIG.

Run INSIDE the bot's container (needs config.DISCORD_TOKEN):
    docker cp channel_audit.py empire-english-bot:/app/channel_audit.py
    docker exec empire-english-bot python3 /app/channel_audit.py
    docker exec empire-english-bot rm -f /app/channel_audit.py

Note: uses raw aiohttp + the Discord REST API directly rather than
discord.py's gateway client, since this doesn't need a live gateway
connection (avoiding any risk of interfering with the actual running
bot's own connection) — just simple authenticated REST calls.
"""
import asyncio
import sys
sys.path.insert(0, "/app")
import aiohttp
from src import config


async def main():
    headers = {
        "Authorization": f"Bot {config.DISCORD_TOKEN}",
        "User-Agent": "DiscordBot (empire-english-bot, 1.0)",
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f"https://discord.com/api/v10/guilds/{config.GUILD_ID}/channels") as resp:
            data = await resp.json()

        async with session.get(f"https://discord.com/api/v10/guilds/{config.GUILD_ID}/roles") as resp:
            roles = await resp.json()
        role_map = {r["id"]: r["name"] for r in roles}
        role_map[config.GUILD_ID] = "@everyone"

        categories = sorted([c for c in data if c.get("type") == 4], key=lambda c: c.get("position", 0))
        print(f"TOTAL_CATEGORIES={len(categories)}")
        print(f"TOTAL_CHANNELS={len([c for c in data if c['type'] in (0, 2)])}")
        print()

        for cat in categories:
            children = sorted(
                [c for c in data if c.get("parent_id") == cat["id"]],
                key=lambda c: c.get("position", 0),
            )
            print(f"CATEGORY: {cat['name']} (id={cat['id']}, {len(children)} channels)")
            for ow in cat.get("permission_overwrites", []):
                # type: 0 = role, 1 = member. Both are valid and
                # meaningful -- see Hisn defect_log.md D007 for a real
                # example of a member-type overwrite (the bot's own
                # account) that looked like an "unmapped role" until
                # investigated properly.
                label = role_map.get(ow["id"], f"member:{ow['id']}")
                print(f"  overwrite: {label} (type={ow['type']}) allow={ow['allow']} deny={ow['deny']}")
            for ch in children:
                ch_type = "voice" if ch["type"] == 2 else "text"
                print(f"    - {ch['name']} ({ch_type})")
            print()


asyncio.run(main())
