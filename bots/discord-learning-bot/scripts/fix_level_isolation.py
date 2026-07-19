#!/usr/bin/env python3
"""
Fix level channel permissions — strict level isolation.

Each student sees ONLY their own level's channels:
- L0 student → sees L0 zone only (not L1/L2/L3)
- L1 student → sees L1 zone only (not L0/L2/L3)
- L2 student → sees L2 zone only (not L0/L1/L3)
- L3 student → sees L3 zone only (not L0/L1/L2)

Run on the production server:
    cd /opt/empire-english-bot
    python3 scripts/fix_level_isolation.py

This sets permission overwrites on each level category. Safe to re-run
(idempotent — sets the same overwrites each time).
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import discord
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID", "0") or "0")

# Category names as they appear on the live server
LEVEL_CATEGORIES = {
    "L0": "🌱 المستوى 0 | LEVEL 0",
    "L1": "💪 المستوى 1 | LEVEL 1",
    "L2": "🚀 المستوى 2 | LEVEL 2",
    "L3": "👑 المستوى 3 | LEVEL 3",
}

# Role names as they appear on the live server
LEVEL_ROLES = {
    "L0": "🌱 Level 0 | مبتدئ",
    "L1": "💪 Level 1 | متقدم",
    "L2": "🚀 Level 2 | متواصل",
    "L3": "👑 Level 3 | طليق",
}

AMBASSADOR_ROLE = "🌟 سفير | Ambassador"
BOT_ROLE = "🤖 Empire Bot"


async def main():
    intents = discord.Intents.default()
    intents.guilds = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        guild = client.get_guild(GUILD_ID)
        if not guild:
            print(f"ERROR: Guild {GUILD_ID} not found")
            await client.close()
            return

        print(f"Connected to: {guild.name} ({guild.id})")

        # Find all level roles
        roles = {}
        for level, name in LEVEL_ROLES.items():
            role = discord.utils.get(guild.roles, name=name)
            if role:
                roles[level] = role
                print(f"  Found role: {name} (id={role.id})")
            else:
                print(f"  WARNING: Role '{name}' not found!")

        ambassador = discord.utils.get(guild.roles, name=AMBASSADOR_ROLE)
        bot_role = discord.utils.get(guild.roles, name=BOT_ROLE)
        everyone = guild.default_role

        if not all(roles.get(l) for l in ["L0", "L1", "L2", "L3"]):
            print("ERROR: Not all level roles found. Aborting.")
            await client.close()
            return

        # For each level category, set strict isolation permissions
        for level, cat_name in LEVEL_CATEGORIES.items():
            category = discord.utils.get(guild.categories, name=cat_name)
            if not category:
                print(f"  WARNING: Category '{cat_name}' not found — skipping")
                continue

            print(f"\n  Fixing: {cat_name}")

            # Build the overwrite dict
            overwrites = {
                everyone: discord.PermissionOverwrite(view_channel=False),
            }

            # Grant VIEW+SEND+VOICE only to THIS level's role
            overwrites[roles[level]] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, add_reactions=True,
                embed_links=True, attach_files=True,
                connect=True, speak=True, use_voice_activation=True,
            )

            # Explicitly DENY all OTHER level roles
            for other_level, other_role in roles.items():
                if other_level != level:
                    overwrites[other_role] = discord.PermissionOverwrite(view_channel=False)

            # Ambassador can see all levels (optional — remove if you
            # want ambassadors isolated too)
            if ambassador:
                overwrites[ambassador] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                    read_message_history=True, add_reactions=True,
                    embed_links=True, attach_files=True,
                    connect=True, speak=True, use_voice_activation=True,
                )

            # Bot needs full access everywhere
            if bot_role:
                overwrites[bot_role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                    embed_links=True, attach_files=True,
                    manage_messages=True, add_reactions=True,
                    mention_everyone=True,
                )

            # Apply to the category
            await category.edit(overwrites=overwrites)
            print(f"    ✅ Category overwrites set")

            # Sync all channels in this category to inherit the
            # category's permissions (removes any per-channel overrides
            # that might conflict)
            for channel in category.channels:
                try:
                    await channel.edit(sync_permissions=True)
                    print(f"    ✅ Synced: #{channel.name}")
                except Exception as e:
                    print(f"    ⚠️  Failed to sync #{channel.name}: {e}")

        print("\n✅ Done! Level isolation applied.")
        print("   L0 students see only L0 channels")
        print("   L1 students see only L1 channels")
        print("   L2 students see only L2 channels")
        print("   L3 students see only L3 channels")
        await client.close()

    await client.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
