#!/usr/bin/env python3
"""Hisn H2.6 setup helper — creates 2 synthetic GHOST_TEST_ members with
real link tokens directly in the production database, so
api_adversarial_test.py (run from OUTSIDE the container, against the
real public URL) has a genuine valid token to test with.

Two members are created (not one) specifically to test H2.8's
cross-member data leakage check: member A's token must never return
member B's data.

Run INSIDE the bot's container:
    docker cp setup_ghost_members.py empire-english-bot:/app/setup_ghost_members.py
    docker exec empire-english-bot python3 /app/setup_ghost_members.py
    docker exec empire-english-bot rm -f /app/setup_ghost_members.py

Prints the two tokens + member B's name fragment to stdout — pass them
as argv to api_adversarial_test.py.

Cleanup: run cleanup_ghost_members.py afterward (same FK-safe pattern
as command_harness.py's cleanup, reused here) to leave zero residue.
"""
import sys

sys.path.insert(0, "/app")
from src import database

database.init_db()

MEMBER_A_ID = "900000010"
MEMBER_A_NAME = "GHOST_TEST_H2ApiRunnerA#0001"
MEMBER_B_ID = "900000011"
MEMBER_B_NAME = "GHOST_TEST_H2ApiRunnerB#0002"

database.register_member(MEMBER_A_ID, MEMBER_A_NAME, goal="Hisn H2 API test member A")
database.register_member(MEMBER_B_ID, MEMBER_B_NAME, goal="Hisn H2 API test member B")

token_a = database.create_link_token(MEMBER_A_ID)
token_b = database.create_link_token(MEMBER_B_ID)

# Give member A a bit of real data so /api/dashboard's fields aren't
# all trivially empty (a stronger test than an all-zero blank member).
import datetime
today = datetime.date.today().isoformat()
database.log_submission(MEMBER_A_ID, today, "vocab")
try:
    from src import config
    database.add_points(MEMBER_A_ID, config.POINTS_PER_TASK, "hisn_h2_setup")
except Exception as e:
    print(f"(non-fatal) could not add points: {e}")

print("GHOST_TEST_ members created:")
print(f"  Member A: discord_id={MEMBER_A_ID} name={MEMBER_A_NAME} token={token_a}")
print(f"  Member B: discord_id={MEMBER_B_ID} name={MEMBER_B_NAME} token={token_b}")
print()
print("Run the adversarial test from the sandbox with:")
print(f"  python3 api_adversarial_test.py {token_a} {token_b} H2ApiRunnerB")
