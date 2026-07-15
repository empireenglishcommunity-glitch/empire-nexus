# Hisn H0.3-H0.6 — Foundation Procedures

This file documents the exact, verified procedures for the remaining
H0 foundation steps. Each was checked against the real source (not
memory) before being written down here.

---

## H0.3 — Production Database Backup (verified)

`scripts/backup.py` exists at
`bots/discord-learning-bot/scripts/backup.py`, supports `--tag`, and
its 12 unit tests all **pass** (confirmed live: `pytest tests/test_backup.py`
→ 12 passed). No code changes needed here — this step is about running
it against the REAL production database before any Hisn testing begins.

### ⚠️ Real risk found while verifying this (read before running)

`backup.py`'s own docstring states tagged and untagged backups share
**one rotation pool of 14** (`MAX_BACKUPS = 14`), by design — a
tagged snapshot is meant to enable a same-day rollback, not to be a
permanent archive. **If the Hisn testing campaign runs longer than a
few days while the daily 3 AM cron keeps adding routine backups, the
`pre-hisn-testing` tagged snapshot could get silently rotated out and
deleted** before H7 finishes. This is exactly the kind of thing this
whole spec exists to catch — so the procedure below copies the backup
out of the rotation pool immediately, per the docstring's own stated
escape hatch ("If you need a permanent, never-rotated snapshot, copy
the file out of the backup directory yourself").

### Procedure (run on the production server)

```bash
# 1. Take the tagged backup (inside the running container, since the
#    DB lives on a Docker-managed volume):
docker exec empire-english-bot python3 scripts/backup.py --tag pre-hisn-testing

# 2. Immediately copy it OUT of the rotation pool to a permanent location
#    (do not rely on the 14-backup rotation to preserve it):
docker exec empire-english-bot sh -c 'cp /app/backups/empire_english_pre-hisn-testing_*.db /app/backups/PERMANENT_pre-hisn-testing.db'

# 3. Copy it off the container entirely, to the host filesystem, so it
#    survives even a full container rebuild:
docker cp empire-english-bot:/app/backups/PERMANENT_pre-hisn-testing.db /opt/empire-english-bot/PERMANENT_pre-hisn-testing.db

# 4. Verify the backup is a valid, openable SQLite database with real data:
docker exec empire-english-bot python3 -c "
import sqlite3
conn = sqlite3.connect('/app/backups/PERMANENT_pre-hisn-testing.db')
print('Tables:', [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()])
print('Member count:', conn.execute('SELECT COUNT(*) FROM members').fetchone()[0])
"
```

Only proceed to H1 once step 4's output shows real table names and a
member count that makes sense (0, since no real students exist yet —
but the query must run without error).

---

## H0.4 — Database Clone for Destructive/Concurrent Testing

Per `design.md`'s Component 1: anything in H5 (multi-student load
simulation) or any other test that WRITES concurrently must run
against a clone, never the live production file, because SQLite's
WAL-mode locking behavior under real concurrent writers is exactly
what H5 needs to observe — but observing it must not risk corrupting
the real (currently empty, but soon real) database.

### Procedure

```bash
# On the production server, after H0.3's backup is confirmed valid:
docker exec empire-english-bot cp /app/data_persist/empire_english.db /app/data_persist/HISN_TEST_CLONE.db

# Copy the clone off-server for local/sandbox testing (this sandbox
# environment, where H5's stress_test.py will actually run):
docker cp empire-english-bot:/app/data_persist/HISN_TEST_CLONE.db ./HISN_TEST_CLONE.db
```

The clone is used for:
- H5 (multi-student concurrent load simulation) — entirely
- Any part of H1-H4 that the tester judges "risky enough not to run
  against production directly" (use judgment; most flag toggles and
  read-only command tests are safe against production as-is, per
  `design.md`'s explicit allowance for non-destructive tests)

The clone is **discarded** after H5 completes (H5.6) — it is never
merged back into production; it exists purely to observe behavior
under load.

### Executed (2026-07-15, session 17)

Ran the procedure above for real: `docker exec ... cp` inside the
container, then `docker cp` out to the sandbox at
`/projects/sandbox/.agents/hisn-testing/HISN_TEST_CLONE.db`. Verified
the clone independently before trusting it: opened it with a fresh
`sqlite3` connection, confirmed 22 tables and a member count of 4
(matching H0.5's D005 finding of 4 pre-existing real member rows —
consistent, not a coincidence). Server-side copies (`/tmp` and the
in-container copy at `data_persist/`) were removed immediately after
the sandbox copy was confirmed valid, so only one clone copy persists,
in the sandbox. For H5's actual stress test run, a second copy of this
same clone was placed inside the container at a clearly-distinct path
(`/app/HISN_STRESS_TEST_CLONE.db`, never `data_persist/empire_english.db`)
with `config.DB_PATH` monkey-patched to point at it before any
`database.py` function was called — confirmed the real production file
was never opened by the stress test script (see H5's own log output:
"production empire_english.db was NEVER opened by this script"). That
container-side copy was deleted after H5 completed (H5.6).

---

## H0.5 — Ghost Testing Environment Verification

### Confirmed from `setup_server.py`'s `CATEGORIES_CONFIG` (verified
via `generate_test_matrix.py`'s channel scan):

The **👻 Ghost Testing** category exists with 3 channels:
- `ghost-commands`
- `ghost-showcase`
- `ghost-writing`

### What still needs live (not just code-level) verification:
1. Confirm this category actually exists on the LIVE Discord server
   (setup_server.py defines the intended state; it must have actually
   been run/applied — verify via the bot or Discord UI directly)
2. Confirm its permission overwrites actually isolate it from regular
   member roles (view_channel=False for Level 0-3 roles) — this is
   H1.8's job specifically, but H0.5 just confirms the category is
   reachable/exists before H1 begins
3. Identify or create 2-3 test Discord accounts:
   - Option A: the owner's own alt/secondary Discord account
   - Option B: ask 1-2 trusted people (if available) to create throwaway
     accounts specifically for this
   - Option C: a single test account is sufficient for most of H1-H4;
     only H5's concurrent simulation truly needs multiple simultaneous
     actors, and H5 uses direct DB/API calls (not real Discord clients)
     for that, per `design.md`'s Component 4 — so **multiple real
     Discord accounts are NOT strictly required**, only helpful for
     H1's manual command-testing pass

**Owner action needed:** confirm (2) is actually true on the live
server (I do not have live Discord API access in this session to
check it myself), and decide on (3)'s approach before H1 begins.

### Update (2026-07-15) — live verification completed, 4 defects found + fixed

Connected to the live Discord server via the bot's own REST API access
(temporary SSH, since revoked). Confirmed:
- Ghost Testing category exists live with all 3 intended channels
  (`ghost-commands`, `ghost-showcase`, `ghost-writing`)
- Isolation verified via raw permission-overwrite bits: the `@everyone`
  role has `VIEW_CHANNEL` explicitly denied (`deny: 1024`) on this
  category — regular members genuinely cannot see it

While doing this, found and fixed 4 real defects (full detail in
`defect_log.md`, entries D001-D004):
- D001: LEVEL 2 category's emoji was corrupted (`→` instead of `🚀`)
- D002: a second, empty, duplicate "LEVEL 2" category existed
- D003: ACCOUNTABILITY and RESOURCES categories' emoji were corrupted
  (`▪` instead of `📊`/`📚`)
- D004: leftover default "Text Channels"/"Voice Channels" categories
  (Discord's auto-created defaults, never cleaned up)

All 4 fixed live via the Discord API (renames + deletions of empty/
unused categories only — no real channel content or permissions
touched) and re-verified post-fix. The live category list now matches
`setup_server.py`'s intended 12-category design exactly.

Also found (D005, info-only): the database already contains 4 real
member rows from prior sessions' work, none of which conflict with the
`GHOST_TEST_` cleanup pattern from H0.6.

---

## H0.6 — GHOST_TEST_ Naming Convention + Cleanup

### Convention
Every member row created for testing purposes uses:
```
discord_name = "GHOST_TEST_<descriptive-suffix>#<4-digit-tag>"
discord_id   = a clearly out-of-range synthetic ID (e.g. "900000001",
                "900000002", ... — real Discord snowflake IDs are
                17-19 digits, so a 9-digit ID can never collide with
                a real one)
```

### Verified cleanup statement

```sql
-- Removes all test-created data across every table that references
-- discord_id, in FK-safe order (children before parents).
DELETE FROM pending_escalations WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM nour_study_tips WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM nour_conversations WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM link_tokens WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM voice_portfolio WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM vocab_srs WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM ability_milestones WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM conversation_sessions WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM pronunciation_scores WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM notification_preferences WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM notification_log WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM advancement_exams WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM assessments WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM points_log WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM streaks WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM daily_submissions WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
DELETE FROM members WHERE discord_id LIKE '9%' AND LENGTH(discord_id) = 9;
```

**Note on the `LENGTH(discord_id) = 9` guard:** this is deliberate and
important — it prevents this cleanup from ever accidentally matching a
real Discord snowflake ID that happens to start with '9' (real IDs are
17-19 digits long, so the length check is what actually guarantees
safety, not the '9%' prefix alone). Verified this logic against a
synthetic test below before trusting it against any real data.

### Verification test (run before relying on this in H5/H7)

```python
# Confirms the cleanup pattern matches ONLY synthetic 9-digit test IDs
# and never a realistic 18-19-digit Discord snowflake, even one that
# happens to start with '9'.
test_ids = [
    "900000001",           # synthetic test ID -> SHOULD match
    "900000002",           # synthetic test ID -> SHOULD match
    "912345678901234567",  # realistic snowflake starting with 9 -> must NOT match
    "123456789012345678",  # realistic snowflake -> must NOT match
]
for tid in test_ids:
    matches = tid.startswith("9") and len(tid) == 9
    expected = tid in ("900000001", "900000002")
    assert matches == expected, f"FAILED for {tid}"
print("All cleanup-pattern safety checks passed.")
```
