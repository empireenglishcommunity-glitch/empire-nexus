#!/usr/bin/env python3
"""Hisn H2.6 cleanup — removes the 2 GHOST_TEST_ members created by
setup_ghost_members.py from the production database, FK-safe
(children-before-parents), same convention as command_harness.py's
cleanup and H0.6's documented cleanup SQL.

Run INSIDE the bot's container:
    docker cp cleanup_ghost_members.py empire-english-bot:/app/cleanup_ghost_members.py
    docker exec empire-english-bot python3 /app/cleanup_ghost_members.py
    docker exec empire-english-bot rm -f /app/cleanup_ghost_members.py
"""
import sys

sys.path.insert(0, "/app")
from src import database

database.init_db()

TEST_IDS = ["900000010", "900000011"]

conn = database._connect()
try:
    for discord_id in TEST_IDS:
        for table in [
            "daily_submissions", "streaks", "points_log", "notification_preferences",
            "notification_log", "voice_portfolio", "vocab_srs", "ability_milestones",
            "assessments", "advancement_exams",
            "pronunciation_scores", "link_tokens", "nour_conversations",
            "nour_study_tips", "pending_escalations", "members",
        ]:
            conn.execute(f"DELETE FROM {table} WHERE discord_id=?", (discord_id,))
    conn.commit()
    print("Cleanup OK — both GHOST_TEST_ H2 API test members removed.")

    # Verify zero residue
    remaining = 0
    for discord_id in TEST_IDS:
        row = conn.execute("SELECT COUNT(*) as c FROM members WHERE discord_id=?", (discord_id,)).fetchone()
        remaining += row["c"]
    print(f"Verification: {remaining} residual member rows (expect 0).")
except Exception as e:
    print(f"Cleanup FAILED: {type(e).__name__}: {e}")
    print(f"Manual cleanup needed for discord_ids={TEST_IDS}")
    sys.exit(1)
finally:
    conn.close()
