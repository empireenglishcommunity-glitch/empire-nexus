#!/usr/bin/env python3
"""Majlis (Community Lounge) rollout tool — preflight, phased enable, rollback.

WHY THIS EXISTS
---------------
Majlis is built through Phase 7 and has been switched off since 2026-07-31 (all
six `community_*` flags default OFF). Turning it on is therefore a *release*, and
this repo's own Aegis rules say a release is staged and reversible, never a
big-bang flip.

More importantly, Majlis has a **silent** failure mode that no test can catch,
because it depends on Discord state rather than code:

    community.MAJLIS_ANCHOR_NAME = "voice-lounge"

The anchor lounge is matched by **literal channel name**. If no voice channel
called `voice-lounge` exists in the guild, then `is_majlis_channel()` returns
False for everything, `lounge_occupancy()` returns {}, and
`is_member_in_majlis_with_company()` is always False — so Phase 1 grants
together-credit to nobody, **and nothing raises**. Students would sit together in
voice and receive no credit, which looks exactly like a broken feature.

That matters here specifically because Majlis was designed on 2026-07-31, BEFORE
the CEFR restructure (2026-08-23/24) rebuilt the guild into six level zones with
`{slug}-voice-1` / `{slug}-voice-2` channels and archived the legacy zones. So
whether `voice-lounge` survived that migration is an open question that can only
be answered against the live guild.

`preflight` answers it. Run it FIRST. It is strictly read-only.

USAGE (inside the bot container, where DISCORD_TOKEN and the DB live)
--------------------------------------------------------------------
    docker exec -w /app empire-english-bot python3 scripts/majlis_rollout.py status
    docker exec -w /app empire-english-bot python3 scripts/majlis_rollout.py preflight
    docker exec -w /app empire-english-bot python3 scripts/majlis_rollout.py enable --phase 1
    docker exec -w /app empire-english-bot python3 scripts/majlis_rollout.py enable --phase 1 --yes
    docker exec -w /app empire-english-bot python3 scripts/majlis_rollout.py enable --phase 1 --pilot 123,456 --yes
    docker exec -w /app empire-english-bot python3 scripts/majlis_rollout.py rollback --yes

`enable` and `rollback` are DRY-RUN BY DEFAULT and print exactly what they would
do. Nothing is written without `--yes`. Every operation is idempotent.

Exit codes: 0 = ok · 1 = a hard prerequisite failed / refused to act.
"""
import argparse
import asyncio
import sys

sys.path.insert(0, ".")

from src import community, config, database  # noqa: E402

# Phase order matters. Phase 1 is the one that fixes the actual complaint
# ("forced to sit alone"), so it ships first and can stand on its own. The
# later phases add reach and automation on top of it.
PHASES = {
    1: ("community_together_credit",
        "Company-aware task #7: 5 min together-time in a Majlis lounge OR the "
        "existing 10 min any-voice path. Nobody is worse off than before."),
    2: ("community_lounge_beacon",
        "Self-cleaning presence beacon in #community-live when a lounge is in "
        "the lonely-but-not-full band. Respects quiet hours."),
    3: ("community_dynamic_rooms",
        "Join-to-create overflow pods; auto-reaped when empty after a grace "
        "period."),
    4: ("community_pings_optin",
        "Opt-in `community-pings` role + Knock button. Only opted-in members "
        "are ever @-mentioned."),
    5: ("community_power_hour",
        "Scheduled Community Hour, 9-10 PM Africa/Cairo: rally post + one "
        "Telegram broadcast."),
    6: ("community_together_reward",
        "Optional bonus points when task #7 is completed via the together path."),
}
ALL_FLAGS = [name for name, _ in PHASES.values()]


def _hr(title):
    print(f"\n{'=' * 66}\n  {title}\n{'=' * 66}")


# ----------------------------------------------------------------------
#  status — DB only, no Discord
# ----------------------------------------------------------------------

def cmd_status(_args):
    _hr("MAJLIS — current flag state")
    for phase, (flag, _desc) in sorted(PHASES.items()):
        st = database.feature_flag_status(flag)
        if st["everyone"]:
            state = "ON (everyone)"
        elif st["enabled"]:
            state = f"PILOT ({len(st['allowed_ids'])} student(s))"
        else:
            state = "off"
        print(f"  Phase {phase}  {flag:<28} {state}")

    _hr("MAJLIS — config (settings overrides over defaults)")
    for k, v in sorted(community.get_config().items()):
        print(f"  {k:<38} {v}")

    rooms = community.get_majlis_room_ids()
    print(f"\n  dynamic rooms registered: {len(rooms)}"
          + (f" -> {sorted(rooms)}" if rooms else ""))
    return 0


# ----------------------------------------------------------------------
#  preflight — READ-ONLY against the live guild
# ----------------------------------------------------------------------

async def _preflight_discord():
    """Inspect the live guild. Returns (hard_failures, warnings)."""
    import discord as dlib

    hard, warn = [], []

    if not config.DISCORD_TOKEN:
        hard.append("DISCORD_TOKEN is not set — cannot inspect the guild. "
                    "Run this inside the bot container.")
        return hard, warn

    intents = dlib.Intents.default()
    intents.members = True
    intents.voice_states = True
    client = dlib.Client(intents=intents)
    result = {}

    @client.event
    async def on_ready():
        try:
            guild = client.get_guild(config.GUILD_ID) or (
                await client.fetch_guild(config.GUILD_ID))
            result["guild"] = guild.name
            result["voice_channels"] = [(vc.name, vc.id, vc.user_limit,
                                         vc.category.name if vc.category else None)
                                        for vc in guild.voice_channels]
            result["text_channels"] = [tc.name for tc in guild.text_channels]
            result["roles"] = [r.name for r in guild.roles]
            me = guild.me
            perms = me.guild_permissions
            result["perms"] = {
                "manage_channels": perms.manage_channels,
                "manage_roles": perms.manage_roles,
                "move_members": perms.move_members,
                "send_messages": perms.send_messages,
                "mention_everyone": perms.mention_everyone,
            }
        except Exception as e:  # noqa: BLE001
            result["error"] = repr(e)
        finally:
            await client.close()

    try:
        await asyncio.wait_for(client.start(config.DISCORD_TOKEN), timeout=90)
    except asyncio.TimeoutError:
        hard.append("Timed out connecting to Discord (90s).")
        return hard, warn
    except Exception as e:  # noqa: BLE001
        hard.append(f"Discord connection failed: {e!r}")
        return hard, warn

    if "error" in result:
        hard.append(f"Could not read the guild: {result['error']}")
        return hard, warn

    print(f"  guild: {result['guild']}")
    print(f"  voice channels: {len(result['voice_channels'])}")

    # --- THE critical check -------------------------------------------
    anchor = [v for v in result["voice_channels"]
              if v[0] == community.MAJLIS_ANCHOR_NAME]
    if not anchor:
        hard.append(
            f"NO voice channel named '{community.MAJLIS_ANCHOR_NAME}' exists.\n"
            "      This is the anchor lounge, matched by literal name. Without it\n"
            "      Majlis is INERT BUT SILENT: no together-credit is ever granted,\n"
            "      no beacon can fire, and dynamic rooms cannot be created (they\n"
            "      locate their category via the anchor's parent).\n"
            "      FIX: create a voice channel named exactly 'voice-lounge' in the\n"
            "      COMMUNITY category, visible to @everyone and all six level\n"
            "      roles (setup_server.py already defines it this way), then\n"
            "      re-run preflight. Do NOT enable any flag until this passes.")
    else:
        name, cid, limit, cat = anchor[0]
        print(f"  anchor '{name}' found: id={cid} category={cat!r} user_limit={limit}")
        if cat is None:
            warn.append("The anchor has no category. #community-live would be "
                        "created at guild root, and dynamic pods inherit no "
                        "category. Cosmetic, but move it into COMMUNITY.")
        want = community.get_lounge_capacity()
        if limit != want:
            warn.append(f"Anchor user_limit={limit}, config lounge_capacity={want}. "
                        f"`ensure_anchor_capacity()` will set it on the next "
                        f"voice event — no action needed, just so it's expected.")

    # --- self-healing, so warn only -----------------------------------
    if community.COMMUNITY_LIVE_CHANNEL not in result["text_channels"]:
        warn.append(f"#{community.COMMUNITY_LIVE_CHANNEL} does not exist yet. "
                    f"It is auto-created on first use (needs Manage Channels).")
    if community.COMMUNITY_PINGS_ROLE not in result["roles"]:
        warn.append(f"Role '{community.COMMUNITY_PINGS_ROLE}' does not exist yet. "
                    f"Auto-created on first use (needs Manage Roles).")

    # --- permissions the phases actually need -------------------------
    p = result["perms"]
    if not p["manage_channels"]:
        hard.append("Bot lacks Manage Channels — Phase 2 (#community-live) and "
                    "Phase 3 (dynamic pods) cannot work.")
    if not p["manage_roles"]:
        warn.append("Bot lacks Manage Roles — Phase 4's opt-in role cannot be "
                    "created or assigned. Phases 1-3 are unaffected.")
    if not p["move_members"]:
        warn.append("Bot lacks Move Members — Phase 3 cannot move a joiner into "
                    "the pod it spawns. Phases 1-2 are unaffected.")
    return hard, warn


def cmd_preflight(_args):
    _hr("MAJLIS PREFLIGHT — read-only. Nothing is modified.")

    hard, warn = [], []

    # DB reachable
    try:
        database.list_feature_flags()
        print("  [ok] database reachable")
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] database unreachable: {e!r}")
        return 1

    # All six flags must be registered, or !flag list can't manage them
    registered = {f["name"] for f in database.list_feature_flags()}
    missing = [f for f in ALL_FLAGS if f not in registered]
    if missing:
        hard.append(f"These flags are not in the DB yet: {missing}. "
                    f"Restart the bot so `sync_flag_registry()` inserts them.")
    else:
        print(f"  [ok] all 6 community_* flags registered in feature_flags")

    print("\n  --- live guild ---")
    h2, w2 = asyncio.run(_preflight_discord())
    hard += h2
    warn += w2

    if warn:
        _hr(f"WARNINGS ({len(warn)}) — not blocking")
        for w in warn:
            print(f"  ! {w}")

    if hard:
        _hr(f"HARD FAILURES ({len(hard)}) — DO NOT ENABLE YET")
        for h in hard:
            print(f"  x {h}")
        print("\n  Result: NOT READY.\n")
        return 1

    _hr("PREFLIGHT PASSED")
    print("  Majlis prerequisites are satisfied. Recommended next step:\n"
          "    enable --phase 1 --pilot <your-own-discord-id> --yes\n"
          "  Sit in the lounge with one other person, confirm task #7 credits,\n"
          "  then re-run with --phase 1 --yes for everyone.\n")
    return 0


# ----------------------------------------------------------------------
#  enable / rollback
# ----------------------------------------------------------------------

def cmd_enable(args):
    phases = sorted(PHASES) if args.all else [args.phase]
    if not args.all and args.phase not in PHASES:
        print(f"Unknown phase {args.phase}. Valid: {sorted(PHASES)}")
        return 1

    pilot = [p.strip() for p in (args.pilot or "").split(",") if p.strip()]
    mode = f"PILOT ({len(pilot)} student(s): {', '.join(pilot)})" if pilot else "EVERYONE"
    _hr(f"{'APPLY' if args.yes else 'DRY RUN'} — enable Majlis phase(s) "
        f"{phases} for {mode}")

    if not args.yes:
        print("  Nothing will be written. Re-run with --yes to apply.\n")

    if args.all and not pilot and args.yes:
        print("  REFUSING: --all + everyone in one step is exactly the big-bang\n"
              "  release Aegis exists to prevent. Enable phase by phase, or pass\n"
              "  --pilot to limit the blast radius. (--all is fine with --pilot.)\n")
        return 1

    for phase in phases:
        flag, desc = PHASES[phase]
        before = database.feature_flag_status(flag)
        state = ("ON (everyone)" if before["everyone"]
                 else f"PILOT({len(before['allowed_ids'])})" if before["enabled"]
                 else "off")
        print(f"\n  Phase {phase} — {flag}")
        print(f"    {desc}")
        print(f"    before: {state}")

        if before["everyone"] and not pilot:
            print("    -> already ON for everyone; no change")
            continue

        if not args.yes:
            print(f"    -> WOULD set enabled=True, allowlist="
                  f"{'[' + ','.join(pilot) + ']' if pilot else '(everyone)'}")
            continue

        if pilot:
            for did in pilot:
                r = database.feature_flag_grant(flag, did, updated_by="majlis_rollout")
                print(f"    -> grant {did}: {r}")
        else:
            database.set_feature_flag(flag, True, "", updated_by="majlis_rollout")
            print("    -> ON for everyone")

        after = database.feature_flag_status(flag)
        print(f"    after:  enabled={after['enabled']} everyone={after['everyone']} "
              f"allowlist={len(after['allowed_ids'])}")

    if args.yes:
        print("\n  Done. Flags take effect immediately — no restart, no redeploy.")
        print("  Kill switch:  python3 scripts/majlis_rollout.py rollback --yes")
        print("  Or per flag:  !flag disable <name>   (Discord)\n")
    return 0


def cmd_rollback(args):
    _hr(f"{'APPLY' if args.yes else 'DRY RUN'} — disable ALL Majlis flags")
    if not args.yes:
        print("  Nothing will be written. Re-run with --yes to apply.\n")
    for phase, (flag, _d) in sorted(PHASES.items()):
        st = database.feature_flag_status(flag)
        if not st["enabled"]:
            print(f"  Phase {phase} {flag:<28} already off")
            continue
        if args.yes:
            database.set_feature_flag(flag, False, "", updated_by="majlis_rollback")
            print(f"  Phase {phase} {flag:<28} -> OFF")
        else:
            print(f"  Phase {phase} {flag:<28} WOULD go OFF")
    if args.yes:
        print("\n  All Majlis behaviour is off. Student data (together_minutes,\n"
              "  points already granted) is NOT deleted — disabling stops new\n"
              "  accrual, it does not claw anything back.\n")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="print current flag + config state (read-only)")
    sub.add_parser("preflight", help="check every prerequisite (read-only)")

    e = sub.add_parser("enable", help="enable a phase (dry-run unless --yes)")
    e.add_argument("--phase", type=int, default=1, help="phase number 1-6")
    e.add_argument("--all", action="store_true",
                   help="all phases (requires --pilot when applying)")
    e.add_argument("--pilot", default="",
                   help="comma-separated discord_ids to limit the release to")
    e.add_argument("--yes", action="store_true", help="actually write")

    r = sub.add_parser("rollback", help="disable all Majlis flags")
    r.add_argument("--yes", action="store_true", help="actually write")

    args = ap.parse_args()
    return {"status": cmd_status, "preflight": cmd_preflight,
            "enable": cmd_enable, "rollback": cmd_rollback}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
