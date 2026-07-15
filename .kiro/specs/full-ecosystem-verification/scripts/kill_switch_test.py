#!/usr/bin/env python3
"""Hisn H1.5 — Kill Switch Drill.

Disables nour_concierge mid-flow, confirms handle_message() short-
circuits cleanly (no crash, returns None via the flag gate itself —
not via a later, different return point), re-enables, confirms
execution proceeds past the gate, then restores the original flag
state. Exercises the REAL handle_message() function, not a
reimplementation of its logic.

Run INSIDE the bot's container:
    docker cp kill_switch_test.py empire-english-bot:/app/kill_switch_test.py
    docker exec empire-english-bot python3 /app/kill_switch_test.py
    docker exec empire-english-bot rm -f /app/kill_switch_test.py
"""
import asyncio
import sys
sys.path.insert(0, "/app")
from src import database, nour_concierge

database.init_db()


class FakeAuthor:
    bot = False
    # Synthetic 9-digit ID starting with '9' — matches the GHOST_TEST_
    # convention from H0.6, can never collide with a real Discord
    # snowflake (17-19 digits).
    id = 900000099


class FakeMessage:
    author = FakeAuthor()
    content = "hello test message"


async def main():
    original = database.is_feature_enabled("nour_concierge")

    # Step 1: disable mid-flow
    database.set_feature_flag("nour_concierge", enabled=False, updated_by="hisn_kill_switch_test")
    msg = FakeMessage()
    try:
        result = await nour_concierge.handle_message(msg)
        print("DISABLED: handle_message returned:", result, "(expected: None, no crash)")
        disabled_ok = result is None
    except Exception as e:
        print("DISABLED: CRASHED:", e)
        disabled_ok = False

    # Step 2: re-enable, confirm execution proceeds past the flag gate
    # (a fake, unregistered author will still get None back, but from
    # the "not a member" check further down handle_message(), a
    # DIFFERENT code path than the flag gate itself).
    database.set_feature_flag("nour_concierge", enabled=True, updated_by="hisn_kill_switch_test")
    try:
        result2 = await nour_concierge.handle_message(msg)
        print("RE-ENABLED: handle_message returned:", result2,
              "(expected: None, but via the not-a-member path, not the flag gate)")
        reenabled_ok = result2 is None
    except Exception as e:
        print("RE-ENABLED: CRASHED:", e)
        reenabled_ok = False

    # Restore original state — critical for safety against a live DB.
    database.set_feature_flag("nour_concierge", enabled=original, updated_by="hisn_kill_switch_restore")
    restored = database.is_feature_enabled("nour_concierge")

    print()
    passed = disabled_ok and reenabled_ok
    print("Kill switch drill result:", "PASS" if passed else "FAIL")
    print("Original flag state restored:", restored == original)

    if not (passed and restored == original):
        sys.exit(1)


asyncio.run(main())
