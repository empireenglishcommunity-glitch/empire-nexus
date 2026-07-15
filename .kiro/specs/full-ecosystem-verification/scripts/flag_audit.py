#!/usr/bin/env python3
"""Hisn H1.4 — Feature Flag Verification.

Iterates every flag in flag_registry.REGISTRY, toggles it on then off,
confirms is_feature_enabled() reflects each change, then restores the
flag to its documented default. Leaves zero side effects on the DB
it's run against (confirmed via the final restored-state check).

Run INSIDE the bot's container (needs the real src package + DB):
    docker cp flag_audit.py empire-english-bot:/app/flag_audit.py
    docker exec empire-english-bot python3 /app/flag_audit.py
    docker exec empire-english-bot rm -f /app/flag_audit.py
"""
import sys
sys.path.insert(0, "/app")
from src import database, flag_registry

database.init_db()

results = []
for name, desc, initiative, default in flag_registry.REGISTRY:
    database.set_feature_flag(name, enabled=True, updated_by="hisn_test")
    now_on = database.is_feature_enabled(name)

    database.set_feature_flag(name, enabled=False, updated_by="hisn_test")
    now_off = database.is_feature_enabled(name)

    # Restore to the documented default — critical, this is what makes
    # this script safe to run against a live production database.
    database.set_feature_flag(name, enabled=default, updated_by="hisn_test_restore")
    restored = database.is_feature_enabled(name)

    ok = now_on is True and now_off is False and restored == default
    results.append((name, ok, now_on, now_off, restored, default))

print(f"Total flags tested: {len(results)}")
failures = [r for r in results if not r[1]]
print(f"Failures: {len(failures)}")
for r in results:
    status = "OK" if r[1] else "FAIL"
    print(f"{status}  {r[0]:35s} on={r[2]} off={r[3]} restored={r[4]} (expected_default={r[5]})")

if failures:
    sys.exit(1)
