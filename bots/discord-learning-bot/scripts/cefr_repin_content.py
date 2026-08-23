"""Mi'yar System Harmonization — Step 6 live content re-pin.

After the CEFR server rebuild (Step 4) + text rewrite (Step 6), two things need
fixing on the LIVE server:
  1. The six new CEFR zone channels (a1-… … c2-…) have NO pinned "how to use
     this channel" guide yet — pin them (additive, safe).
  2. #welcome, #rules and #roles-info still show the OLD 4-level pinned text —
     refresh them (delete the bot's old pin, post the updated CEFR version).

Idempotent + DRY-RUN by default (prints the plan, changes nothing). Pass
--apply to perform. Run inside the bot container (uses the bot token).

    python scripts/cefr_repin_content.py            # dry-run
    python scripts/cefr_repin_content.py --apply    # perform
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import discord
from dotenv import load_dotenv

from src import config
import setup_server as ss
from channel_guides import CHANNEL_GUIDES

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID", "0") or "0")

# Channels whose pinned message CONTENT changed in Step 6 → refresh (replace).
_REFRESH = {
    "welcome": ss.WELCOME_MESSAGE,
    "rules": ss.RULES_MESSAGE,
    "roles-info": ss.ROLES_INFO_MESSAGE,
}


class Repinner(discord.Client):
    def __init__(self, apply: bool):
        super().__init__(intents=discord.Intents(guilds=True))
        self.apply = apply

    async def on_ready(self):
        mode = "APPLY" if self.apply else "DRY-RUN"
        print(f"\n{'='*60}\n  CEFR content re-pin — {mode}\n{'='*60}")
        try:
            guild = self.get_guild(GUILD_ID)
            if not guild:
                print(f"❌ Guild {GUILD_ID} not found"); return
            await self._pin_new_channel_guides(guild)
            await self._refresh_changed_pins(guild)
            print(f"\n✅ {mode} complete.")
        except Exception as e:
            import traceback; traceback.print_exc(); print(f"❌ ERROR: {e}")
        finally:
            await self.close()

    async def _bot_guide_msg(self, channel):
        """Return the bot's existing PINNED message in the channel, or None.
        We check the channel's pinned messages (not recent history): the guide
        we post is always pinned, so a pinned bot message is the reliable
        'already has a guide' signal — correct even on busy channels like
        #general-chat where the old pin is far back in history."""
        try:
            for m in await channel.pins():
                if m.author.id == self.user.id:
                    return m
        except discord.Forbidden:
            return None
        return None

    async def _pin_new_channel_guides(self, guild):
        print("\n[1/2] Pin guides on channels that don't have one yet")
        pinned = skipped = missing = 0
        for ch_name, text in CHANNEL_GUIDES.items():
            if ch_name in _REFRESH:
                continue  # welcome/rules/roles-info are handled by the refresh step
            channel = discord.utils.get(guild.text_channels, name=ch_name)
            if not channel:
                missing += 1
                continue
            existing = await self._bot_guide_msg(channel)
            if existing:
                skipped += 1
                continue
            print(f"      → pin guide in #{ch_name}")
            if self.apply:
                try:
                    msg = await channel.send(text)
                    await msg.pin()
                    await asyncio.sleep(0.5)
                except discord.HTTPException as e:
                    print(f"        ⚠️ failed: {e}")
                    continue
            pinned += 1
        print(f"      pinned={pinned} already-had-guide={skipped} channel-not-found={missing}")

    async def _refresh_changed_pins(self, guild):
        print("\n[2/2] Refresh #welcome / #rules / #roles-info pinned text")
        for ch_name, new_text in _REFRESH.items():
            channel = discord.utils.get(guild.text_channels, name=ch_name)
            if not channel:
                print(f"      ⚠️ #{ch_name} not found")
                continue
            old = await self._bot_guide_msg(channel)
            action = "replace old bot message" if old else "post (none existing)"
            print(f"      → #{ch_name}: {action}")
            if self.apply:
                try:
                    if old:
                        try:
                            await old.unpin()
                        except discord.HTTPException:
                            pass
                        await old.delete()
                    msg = await channel.send(new_text)
                    await msg.pin()
                    await asyncio.sleep(0.6)
                except discord.HTTPException as e:
                    print(f"        ⚠️ failed: {e}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="perform (default: dry-run)")
    args = ap.parse_args()
    if not DISCORD_TOKEN or not GUILD_ID:
        raise SystemExit("DISCORD_TOKEN and GUILD_ID must be set")
    Repinner(apply=args.apply).run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
