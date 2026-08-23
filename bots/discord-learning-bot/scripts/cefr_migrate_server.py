"""Mi'yar System Harmonization — Step 4 live Discord migration.

One-time (idempotent) migration of the LIVE Discord server from the legacy
4-level structure (L0–L3) to the six CEFR zones (A1–C2). Reuses setup_server's
CEFR role/zone definitions so there is a single source of truth.

What it does, in order:
  1. SNAPSHOT  — dumps the current guild structure (roles, categories +
     channels, and every active member's current level roles) to a timestamped
     JSON file under backups/, so the migration is auditable + reversible.
  2. ROLES     — creates the six CEFR level roles (idempotent).
  3. ZONES     — creates the six CEFR level ZONE categories + channels with
     strict per-level isolation (idempotent).
  4. REASSIGN  — for every active member, adds their CEFR level role (from
     database member.level) and strips any stale legacy L0–L3 role.
  5. ARCHIVE   — renames the old L0–L3 zone categories to "📦 Archive — …",
     hides them from @everyone + all level roles (kept read-only for admins),
     preserving history without deleting anything.
  6. VERIFY    — prints a per-student check (exactly one CEFR role each).

Safety:
  - DRY-RUN by default: prints every action it WOULD take and writes NOTHING.
    Pass --apply to actually perform the migration.
  - The snapshot is always written first (even in --apply), before any change.
  - Idempotent: safe to re-run; existing roles/zones are reused, already-correct
    members are skipped.

Usage (inside the bot container, so it uses the bot token + DB):
    python scripts/cefr_migrate_server.py            # dry-run (default)
    python scripts/cefr_migrate_server.py --apply     # perform the migration
"""
import argparse
import asyncio
import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import discord
from dotenv import load_dotenv

from src import config, database
import setup_server as ss  # CEFR role/zone definitions + overwrite resolver

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID", "0") or "0")

# Old legacy zone category names → archived name. Archiving (not deleting)
# preserves all history and is fully reversible.
_LEGACY_ZONE_NAMES = [
    "🌱 المستوى 0 | LEVEL 0",
    "💪 المستوى 1 | LEVEL 1",
    "🚀 المستوى 2 | LEVEL 2",
    "👑 المستوى 3 | LEVEL 3",
]
BACKUP_DIR = Path(os.getenv("CEFR_BACKUP_DIR", "/app/backups"))


class CefrServerMigrator(discord.Client):
    def __init__(self, apply: bool):
        super().__init__(intents=discord.Intents(guilds=True, members=True))
        self.apply = apply
        self.created_roles = {}

    async def on_ready(self):
        mode = "APPLY" if self.apply else "DRY-RUN"
        print(f"\n{'='*60}\n  CEFR server migration — {mode}\n{'='*60}")
        try:
            guild = self.get_guild(GUILD_ID)
            if not guild:
                print(f"❌ Guild {GUILD_ID} not found"); return
            await self._snapshot(guild)          # always, first
            await self._ensure_roles(guild)
            await self._ensure_zones(guild)
            await self._reassign_members(guild)
            await self._archive_legacy_zones(guild)
            await self._verify(guild)
            print(f"\n✅ {mode} complete.")
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"\n❌ ERROR: {e}")
        finally:
            await self.close()

    # ---- 1. snapshot -----------------------------------------------------
    async def _snapshot(self, guild):
        snap = {
            "captured_at": datetime.datetime.now().isoformat(),
            "guild_id": guild.id,
            "roles": [r.name for r in guild.roles],
            "categories": {
                c.name: [ch.name for ch in c.channels] for c in guild.categories
            },
            "members": {},
        }
        managed = set(config.all_managed_level_role_names())
        for m in database.all_active_members():
            gm = guild.get_member(int(m["discord_id"])) if m["discord_id"].isdigit() else None
            snap["members"][m["discord_id"]] = {
                "db_level": m.get("level"),
                "discord_name": m.get("discord_name", ""),
                "current_level_roles": [r.name for r in gm.roles if r.name in managed] if gm else None,
            }
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = BACKUP_DIR / f"cefr_server_snapshot_{ts}.json"
        path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[1/6] 📸 Snapshot written: {path}")
        print(f"      roles={len(snap['roles'])} categories={len(snap['categories'])} "
              f"active_members={len(snap['members'])}")

    # ---- 2. roles --------------------------------------------------------
    async def _ensure_roles(self, guild):
        print("\n[2/6] CEFR level roles")
        existing = {r.name: r for r in guild.roles}
        for cfg in ss._cefr_level_role_configs():
            name = cfg["name"]
            if name in existing:
                self.created_roles[name] = existing[name]
                print(f"      ✓ exists: {name}")
            elif self.apply:
                role = await guild.create_role(name=name, color=discord.Color(cfg["color"]),
                                               hoist=cfg["hoist"], permissions=cfg["permissions"])
                self.created_roles[name] = role
                print(f"      ✅ created: {name}")
                await asyncio.sleep(0.4)
            else:
                print(f"      ➕ would create: {name}")

    # ---- 3. zones --------------------------------------------------------
    async def _ensure_zones(self, guild):
        print("\n[3/6] CEFR level zones")
        for cat_cfg in ss._cefr_zone_configs():
            overwrites = self._resolve_ow(guild, cat_cfg["overwrites"])
            cat = discord.utils.get(guild.categories, name=cat_cfg["name"])
            if cat:
                if self.apply:
                    await cat.edit(overwrites=overwrites)
                print(f"      ✓ zone exists: {cat_cfg['name']}")
            elif self.apply:
                cat = await guild.create_category(name=cat_cfg["name"], overwrites=overwrites)
                print(f"      ✅ zone created: {cat_cfg['name']}")
                await asyncio.sleep(0.4)
            else:
                print(f"      ➕ would create zone: {cat_cfg['name']} "
                      f"({', '.join(ch['name'] for ch in cat_cfg['channels'])})")
                continue
            for ch_cfg in cat_cfg["channels"]:
                is_voice = ch_cfg["type"] == "voice"
                pool = cat.voice_channels if is_voice else cat.text_channels
                if discord.utils.get(pool, name=ch_cfg["name"]):
                    continue
                if self.apply:
                    if is_voice:
                        await cat.create_voice_channel(name=ch_cfg["name"])
                    else:
                        await cat.create_text_channel(name=ch_cfg["name"], topic=ch_cfg.get("topic", ""))
                    print(f"        ✅ #{ch_cfg['name']}")
                    await asyncio.sleep(0.3)
                else:
                    print(f"        ➕ would create #{ch_cfg['name']}")

    def _resolve_ow(self, guild, cfg):
        out = {}
        for key, ow in cfg.items():
            if key == "@everyone":
                target = guild.default_role
            elif key == "bot":
                target = guild.self_role
            else:
                target = self.created_roles.get(key) or discord.utils.get(guild.roles, name=key)
            if target:
                out[target] = ow
        return out

    # ---- 4. reassign members --------------------------------------------
    async def _reassign_members(self, guild):
        print("\n[4/6] Reassign members to CEFR role")
        managed = config.all_managed_level_role_names()
        done = skipped = 0
        for m in database.all_active_members():
            did = m["discord_id"]
            if not did.isdigit():
                continue
            gm = guild.get_member(int(did))
            if not gm:
                print(f"      ⚠️  not in guild: {m.get('discord_name')} ({did})")
                continue
            target_name = config.level_role_name(m.get("level", "A1"))
            has_target = any(r.name == target_name for r in gm.roles)
            stale = [r for r in gm.roles if r.name in managed and r.name != target_name]
            if has_target and not stale:
                skipped += 1
                continue
            print(f"      → {m.get('discord_name')}: +{target_name}"
                  + (f"  -{[r.name for r in stale]}" if stale else ""))
            if self.apply:
                target_role = self.created_roles.get(target_name) or discord.utils.get(guild.roles, name=target_name)
                if target_role and not has_target:
                    await gm.add_roles(target_role)
                for r in stale:
                    await gm.remove_roles(r)
                await asyncio.sleep(0.4)
            done += 1
        print(f"      reassigned={done} already-correct={skipped}")

    # ---- 5. archive legacy zones ----------------------------------------
    async def _archive_legacy_zones(self, guild):
        print("\n[5/6] Archive legacy L0–L3 zones")
        deny = discord.PermissionOverwrite(view_channel=False)
        for old_name in _LEGACY_ZONE_NAMES:
            cat = discord.utils.get(guild.categories, name=old_name)
            if not cat:
                print(f"      ✓ already gone/renamed: {old_name}")
                continue
            new_name = "📦 Archive — " + old_name
            print(f"      → archive: {old_name}  →  {new_name} (hide + lock, {len(cat.channels)} channels)")
            if self.apply:
                # Hide from everyone + all level roles; keep admins' view.
                ow = {guild.default_role: deny}
                for rn in config.all_managed_level_role_names():
                    role = discord.utils.get(guild.roles, name=rn)
                    if role:
                        ow[role] = deny
                await cat.edit(name=new_name, overwrites=ow)
                for ch in cat.channels:
                    try:
                        await ch.edit(sync_permissions=True)
                    except Exception:
                        pass
                await asyncio.sleep(0.4)

    # ---- 6. verify -------------------------------------------------------
    async def _verify(self, guild):
        print("\n[6/6] Verify (each active member should hold exactly their CEFR role)")
        managed = set(config.all_managed_level_role_names())
        cefr_names = set(config.all_cefr_role_names())
        problems = 0
        for m in database.all_active_members():
            did = m["discord_id"]
            if not did.isdigit():
                continue
            gm = guild.get_member(int(did))
            if not gm:
                continue
            level_roles = [r.name for r in gm.roles if r.name in managed]
            want = config.level_role_name(m.get("level", "A1"))
            ok = level_roles == [want] and want in cefr_names
            if not ok:
                problems += 1
                print(f"      ✗ {m.get('discord_name')}: has {level_roles}, want [{want}]")
        print(f"      {'✅ all good' if problems == 0 else f'⚠️ {problems} to review'} "
              f"({'dry-run — nothing changed yet' if not self.apply else 'applied'})")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="perform the migration (default: dry-run)")
    args = ap.parse_args()
    if not DISCORD_TOKEN or not GUILD_ID:
        raise SystemExit("DISCORD_TOKEN and GUILD_ID must be set")
    CefrServerMigrator(apply=args.apply).run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
