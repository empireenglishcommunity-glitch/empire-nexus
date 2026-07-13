"""Empire English Community Bot — Database Layer (SQLite).

Handles all persistent state: members, daily submissions, streaks,
weekly assessments, points/badges, and operational settings.

Schema designed for the 7-task daily loop, weekly assessments,
and level advancement tracking described in the Learning System blueprint.
"""
import sqlite3
import datetime
from typing import Optional

from . import config

# ============================================================
#  INITIALIZATION
# ============================================================

def _connect() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist. Safe to call on every startup."""
    conn = _connect()
    conn.executescript(_SCHEMA)
    _migrate(conn)
    conn.close()


def _migrate(conn: sqlite3.Connection):
    """Apply idempotent, additive schema migrations for existing databases.

    CREATE TABLE IF NOT EXISTS does not add new columns to a table that
    already exists (e.g. on the live server's database file). Each
    migration below is safe to run every startup: it only adds a column
    if that column is not already present.
    """
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(advancement_exams)")}
    migrations = [
        ("status", "TEXT NOT NULL DEFAULT 'pending'"),
        ("speaking_recording_url", "TEXT DEFAULT ''"),
        ("writing_submission", "TEXT DEFAULT ''"),
        ("resolved_at", "TEXT DEFAULT NULL"),
        ("resolved_by", "TEXT DEFAULT ''"),
    ]
    for col_name, col_def in migrations:
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE advancement_exams ADD COLUMN {col_name} {col_def}")
    conn.commit()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    discord_id      TEXT PRIMARY KEY,
    discord_name    TEXT NOT NULL DEFAULT '',
    telegram_id     TEXT DEFAULT '',
    level           TEXT NOT NULL DEFAULT 'L0',
    track           TEXT NOT NULL DEFAULT 'Core',
    goal            TEXT DEFAULT '',
    joined_at       TEXT NOT NULL DEFAULT (datetime('now')),
    last_active_at  TEXT NOT NULL DEFAULT (datetime('now')),
    total_points    INTEGER NOT NULL DEFAULT 0,
    current_streak  INTEGER NOT NULL DEFAULT 0,
    longest_streak  INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'active',
    buddy_id        TEXT DEFAULT '',
    notes           TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS daily_submissions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    date            TEXT NOT NULL,
    task_id         TEXT NOT NULL,
    submitted_at    TEXT NOT NULL DEFAULT (datetime('now')),
    content         TEXT DEFAULT '',
    score           REAL DEFAULT NULL,
    feedback        TEXT DEFAULT '',
    FOREIGN KEY (discord_id) REFERENCES members(discord_id),
    UNIQUE(discord_id, date, task_id)
);

CREATE TABLE IF NOT EXISTS streaks (
    discord_id      TEXT NOT NULL,
    date            TEXT NOT NULL,
    tasks_completed INTEGER NOT NULL DEFAULT 0,
    all_seven       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (discord_id, date),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

CREATE TABLE IF NOT EXISTS assessments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    week_number     INTEGER NOT NULL,
    assessed_at     TEXT NOT NULL DEFAULT (datetime('now')),
    speaking_score  REAL DEFAULT NULL,
    listening_score REAL DEFAULT NULL,
    vocabulary_score REAL DEFAULT NULL,
    accent_score    REAL DEFAULT NULL,
    writing_score   REAL DEFAULT NULL,
    completion_rate REAL DEFAULT NULL,
    overall_score   REAL DEFAULT NULL,
    rating          TEXT DEFAULT '',
    feedback        TEXT DEFAULT '',
    FOREIGN KEY (discord_id) REFERENCES members(discord_id),
    UNIQUE(discord_id, week_number)
);

CREATE TABLE IF NOT EXISTS advancement_exams (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    from_level      TEXT NOT NULL,
    to_level        TEXT NOT NULL,
    attempted_at    TEXT NOT NULL DEFAULT (datetime('now')),
    speaking_score  REAL DEFAULT NULL,
    listening_score REAL DEFAULT NULL,
    vocabulary_score REAL DEFAULT NULL,
    accent_score    REAL DEFAULT NULL,
    writing_score   REAL DEFAULT NULL,
    passed          INTEGER NOT NULL DEFAULT 0,
    notes           TEXT DEFAULT '',
    -- Added to close the "!exam dead-end" gap: a row is now created the
    -- moment DM collection completes (status='pending'), so the 30-day
    -- cooldown actually works, the submission survives a bot restart,
    -- and an admin has something concrete to review and resolve.
    status                  TEXT NOT NULL DEFAULT 'pending',  -- pending | passed | failed
    speaking_recording_url  TEXT DEFAULT '',
    writing_submission      TEXT DEFAULT '',
    resolved_at             TEXT DEFAULT NULL,
    resolved_by             TEXT DEFAULT '',
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

CREATE TABLE IF NOT EXISTS points_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    points          INTEGER NOT NULL,
    reason          TEXT NOT NULL,
    logged_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

CREATE TABLE IF NOT EXISTS settings (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL
);

-- Aegis (production-safe-deploys spec) Phase 1: feature flags + kill
-- switch. Lets new behavior merge and deploy dormant, get enabled for
-- a specific allowlist first (test on yourself, then a trusted few),
-- then everyone -- and lets a live feature be instantly disabled again
-- with zero redeploy if it misbehaves. See
-- .kiro/specs/production-safe-deploys/design.md's "Component 1".
CREATE TABLE IF NOT EXISTS feature_flags (
    name            TEXT PRIMARY KEY,
    enabled         INTEGER NOT NULL DEFAULT 0,
    allowed_ids     TEXT DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by      TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_submissions_date ON daily_submissions(discord_id, date);
CREATE INDEX IF NOT EXISTS idx_streaks_date ON streaks(discord_id, date);
CREATE INDEX IF NOT EXISTS idx_assessments_member ON assessments(discord_id);
CREATE INDEX IF NOT EXISTS idx_points_member ON points_log(discord_id);
"""


# ============================================================
#  MEMBER OPERATIONS
# ============================================================

def register_member(discord_id: str, name: str, level: str = "L0",
                    track: str = "Core", goal: str = "",
                    telegram_id: str = "") -> bool:
    """Register a new member. Returns True if newly created, False if exists."""
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO members (discord_id, discord_name, level, track, goal, telegram_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (discord_id, name, level, track, goal, telegram_id),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Already exists — update name and last_active
        conn.execute(
            "UPDATE members SET discord_name=?, last_active_at=datetime('now') WHERE discord_id=?",
            (name, discord_id),
        )
        conn.commit()
        return False
    finally:
        conn.close()


def get_member(discord_id: str) -> Optional[dict]:
    """Get a member record or None."""
    conn = _connect()
    row = conn.execute("SELECT * FROM members WHERE discord_id=?", (discord_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_member(discord_id: str, **fields):
    """Update arbitrary fields on a member.

    Auto-touches last_active_at to now UNLESS the caller explicitly passed
    a value for it. Previously this unconditionally appended
    ", last_active_at=datetime('now')" to the SQL regardless of what was
    in `fields` -- if a caller ever passed last_active_at=... explicitly
    (e.g. a backfill script, or an admin tool correcting a member's
    activity timestamp), SQLite silently keeps the LAST assignment to a
    column that's set twice in one UPDATE, so the explicit value was
    always discarded in favor of "now" with no error or warning.
    """
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [discord_id]
    conn = _connect()
    if "last_active_at" not in fields:
        sets += ", last_active_at=datetime('now')"
    conn.execute(f"UPDATE members SET {sets} WHERE discord_id=?", values)
    conn.commit()
    conn.close()


def set_level(discord_id: str, new_level: str):
    """Update a member's level (after passing advancement exam)."""
    update_member(discord_id, level=new_level)


def all_active_members() -> list[dict]:
    """Get all members with status='active'."""
    conn = _connect()
    rows = conn.execute("SELECT * FROM members WHERE status='active' ORDER BY total_points DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def members_at_level(level: str) -> list[dict]:
    """Get all active members at a specific level."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM members WHERE level=? AND status='active'", (level,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
#  DAILY SUBMISSIONS
# ============================================================

def log_submission(discord_id: str, date: str, task_id: str,
                   content: str = "", score: float = None,
                   feedback: str = "") -> bool:
    """Log a task submission. Returns True if new, False if already exists."""
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO daily_submissions (discord_id, date, task_id, content, score, feedback)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (discord_id, date, task_id, content, score, feedback),
        )
        conn.commit()
        # Update last_active
        conn.execute(
            "UPDATE members SET last_active_at=datetime('now') WHERE discord_id=?",
            (discord_id,),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_submissions_for_date(discord_id: str, date: str) -> list[dict]:
    """Get all submissions for a member on a specific date."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM daily_submissions WHERE discord_id=? AND date=?",
        (discord_id, date),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_submissions_since(discord_id: str, days: int = 7) -> list[dict]:
    """Get all of a member's submissions from the last N days (inclusive
    of today). Used by !assess (bot.py::cmd_assess) to see which of the
    week's verified tasks (accent/vocab/shadow/speaking/listening) were
    actually completed, and to pull the most recent AI-scored writing
    submission, without adding a separate narrow query per task type.
    """
    cutoff = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM daily_submissions WHERE discord_id=? AND date>=? ORDER BY submitted_at",
        (discord_id, cutoff),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_submissions_for_date(discord_id: str, date: str) -> int:
    """Count tasks submitted on a specific date."""
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM daily_submissions WHERE discord_id=? AND date=?",
        (discord_id, date),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def tasks_completed_today(discord_id: str) -> list[str]:
    """Get list of task_ids completed today."""
    today = datetime.date.today().isoformat()
    conn = _connect()
    rows = conn.execute(
        "SELECT task_id FROM daily_submissions WHERE discord_id=? AND date=?",
        (discord_id, today),
    ).fetchall()
    conn.close()
    return [r["task_id"] for r in rows]


# ============================================================
#  STREAKS
# ============================================================

def update_streak(discord_id: str, date: str, tasks_completed: int):
    """Update the streak record for a given day."""
    all_seven = 1 if tasks_completed >= 7 else 0
    conn = _connect()
    conn.execute(
        """INSERT OR REPLACE INTO streaks (discord_id, date, tasks_completed, all_seven)
           VALUES (?, ?, ?, ?)""",
        (discord_id, date, tasks_completed, all_seven),
    )
    conn.commit()
    conn.close()
    # Recompute current streak
    _recompute_streak(discord_id)


def _recompute_streak(discord_id: str):
    """Recompute current streak from streaks table (consecutive days with >=1 task)."""
    conn = _connect()
    rows = conn.execute(
        "SELECT date, tasks_completed FROM streaks WHERE discord_id=? ORDER BY date DESC",
        (discord_id,),
    ).fetchall()
    conn.close()

    if not rows:
        _set_streak(discord_id, 0)
        return

    streak = 0
    today = datetime.date.today()
    expected = today

    for row in rows:
        row_date = datetime.date.fromisoformat(row["date"])
        if row_date == expected and row["tasks_completed"] > 0:
            streak += 1
            expected -= datetime.timedelta(days=1)
        elif row_date == expected and row["tasks_completed"] == 0:
            break
        elif row_date < expected:
            # Missed a day
            break

    _set_streak(discord_id, streak)


def _set_streak(discord_id: str, streak: int):
    """Set current streak and update longest if needed.

    Uses a single atomic UPDATE (longest_streak = MAX(longest_streak, ?))
    rather than a separate SELECT-then-UPDATE. The read-then-write version
    had a genuine, confirmed race: two concurrent calls for the same
    member (e.g. the nightly streak-update loop processing overlapping
    requests, or two rapid !done submissions) could both read the same
    "old" longest_streak before either commits its write, so whichever
    UPDATE lands second silently overwrites the first's result -- a lost
    update. Reproduced with 100 concurrent threads racing to set
    longest_streak to values 0..99: the read-then-write version recorded
    a final value well below 99 in 5/5 trials. The atomic SQL expression
    below can't lose an update this way, since SQLite serializes writes
    to the same row and each UPDATE's MAX() is evaluated against
    whatever value is actually on disk at the moment it runs, not a
    value read and cached earlier in Python.
    """
    conn = _connect()
    conn.execute(
        "UPDATE members SET current_streak=?, longest_streak=MAX(longest_streak, ?) WHERE discord_id=?",
        (streak, streak, discord_id),
    )
    conn.commit()
    conn.close()


def get_streak(discord_id: str) -> tuple[int, int]:
    """Returns (current_streak, longest_streak)."""
    member = get_member(discord_id)
    if not member:
        return (0, 0)
    return (member["current_streak"], member["longest_streak"])


# ============================================================
#  POINTS & LEADERBOARD
# ============================================================

def add_points(discord_id: str, points: int, reason: str):
    """Add points to a member and log the event.

    Clamps `points` to SQLite's native signed-64-bit INTEGER range before
    doing anything else. Every real call site in this codebase only ever
    passes fixed positive constants from config.py, so this can't be
    reached by attacker-controlled input today -- but sqlite3 raises a
    bare, uncaught OverflowError (not a normal sqlite3.Error) for any
    value outside that range, which would crash whatever command
    triggered it rather than fail gracefully. Clamping here means a
    future caller with a miscalculated or corrupted point value degrades
    to a very large (but valid, storable) number instead of an unhandled
    crash -- found via adversarial stress testing with 2**63 as input.
    """
    points = max(-(2**63), min(points, 2**63 - 1))
    conn = _connect()
    conn.execute(
        "INSERT INTO points_log (discord_id, points, reason) VALUES (?, ?, ?)",
        (discord_id, points, reason),
    )
    conn.execute(
        "UPDATE members SET total_points = total_points + ? WHERE discord_id=?",
        (points, discord_id),
    )
    conn.commit()
    conn.close()


def leaderboard(limit: int = 10) -> list[dict]:
    """Get top members by total points."""
    conn = _connect()
    rows = conn.execute(
        """SELECT discord_id, discord_name, level, total_points, current_streak
           FROM members WHERE status='active'
           ORDER BY total_points DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def streak_leaderboard(limit: int = 10) -> list[dict]:
    """Get top members by current streak."""
    conn = _connect()
    rows = conn.execute(
        """SELECT discord_id, discord_name, level, current_streak, longest_streak
           FROM members WHERE status='active'
           ORDER BY current_streak DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
#  ASSESSMENTS
# ============================================================

def save_assessment(discord_id: str, week_number: int, scores: dict,
                    overall: float, rating: str, feedback: str = ""):
    """Save a weekly assessment result.

    Clamps week_number to SQLite's signed-64-bit INTEGER range for the
    same reason add_points() does above -- an unclamped huge value raises
    a bare OverflowError instead of a normal, catchable sqlite3.Error.
    Found via adversarial stress testing with 2**63 as input.
    """
    week_number = max(-(2**63), min(week_number, 2**63 - 1))
    conn = _connect()
    conn.execute(
        """INSERT OR REPLACE INTO assessments
           (discord_id, week_number, speaking_score, listening_score,
            vocabulary_score, accent_score, writing_score, completion_rate,
            overall_score, rating, feedback)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            discord_id, week_number,
            scores.get("speaking"), scores.get("listening"),
            scores.get("vocabulary"), scores.get("accent"),
            scores.get("writing"), scores.get("completion"),
            overall, rating, feedback,
        ),
    )
    conn.commit()
    conn.close()


def get_assessment_for_week(discord_id: str, week_number: int) -> Optional[dict]:
    """Get a member's assessment for one specific week, or None.

    Used by !assess (bot.py::cmd_assess) to decide whether this is the
    member's first assessment submission for the current week (award
    POINTS_ASSESSMENT once) vs. a re-run that should just refresh the
    stored score (e.g. after a late writing-feedback score comes in)
    without awarding points a second time.
    """
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM assessments WHERE discord_id=? AND week_number=?",
        (discord_id, week_number),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_assessments(discord_id: str) -> list[dict]:
    """Get all assessments for a member, ordered by week."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM assessments WHERE discord_id=? ORDER BY week_number",
        (discord_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_assessment(discord_id: str) -> Optional[dict]:
    """Get the most recent assessment."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM assessments WHERE discord_id=? ORDER BY week_number DESC LIMIT 1",
        (discord_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ============================================================
#  ADVANCEMENT EXAMS
# ============================================================

def log_advancement_attempt(discord_id: str, from_level: str, to_level: str,
                            scores: dict, passed: bool, notes: str = ""):
    """Log a fully-resolved advancement exam attempt (scores known up front).
    Kept for any future auto-scored (non-DM-collection) exam path.
    """
    conn = _connect()
    conn.execute(
        """INSERT INTO advancement_exams
           (discord_id, from_level, to_level, speaking_score, listening_score,
            vocabulary_score, accent_score, writing_score, passed, notes, status, resolved_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            discord_id, from_level, to_level,
            scores.get("speaking"), scores.get("listening"),
            scores.get("vocabulary"), scores.get("accent"),
            scores.get("writing"), 1 if passed else 0, notes,
            "passed" if passed else "failed",
        ),
    )
    conn.commit()
    conn.close()


def create_pending_exam(discord_id: str, from_level: str, to_level: str,
                        speaking_recording_url: str = "", writing_submission: str = "") -> int:
    """Create a 'pending' advancement exam row once DM collection completes.

    This is what makes the 30-day cooldown (last_advancement_attempt) and
    the exam-review admin flow actually work — previously NOTHING ever
    wrote to this table, so every !exam request looked like a first
    attempt forever, and submitted recordings/writing were never saved
    anywhere durable (they lived only in an in-memory dict that a bot
    restart would silently wipe).

    Returns the new row's id.
    """
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO advancement_exams
           (discord_id, from_level, to_level, speaking_recording_url,
            writing_submission, status)
           VALUES (?, ?, ?, ?, ?, 'pending')""",
        (discord_id, from_level, to_level, speaking_recording_url, writing_submission),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def last_advancement_attempt(discord_id: str) -> Optional[dict]:
    """Get the most recent advancement exam attempt (any status).

    Ties on attempted_at (SQLite's datetime('now') has only second-level
    resolution, so two exams created within the same second are
    indistinguishable by timestamp alone) are broken by id DESC, so the
    row that was actually inserted last is always the one returned.
    """
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM advancement_exams WHERE discord_id=? ORDER BY attempted_at DESC, id DESC LIMIT 1",
        (discord_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def pending_exams() -> list[dict]:
    """Get all advancement exams awaiting admin review, oldest first."""
    conn = _connect()
    rows = conn.execute(
        """SELECT e.*, m.discord_name FROM advancement_exams e
           LEFT JOIN members m ON m.discord_id = e.discord_id
           WHERE e.status='pending' ORDER BY e.attempted_at ASC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_exam_by_id(exam_id: int) -> Optional[dict]:
    """Get a single advancement exam row by its id.

    An admin typing !examresult with an id outside SQLite's signed-64-bit
    INTEGER range (e.g. a typo like an extra digit) previously raised a
    bare OverflowError instead of the normal "No exam found" message --
    found via boundary-condition stress testing, same failure mode as
    add_points()/save_assessment(). Unlike those two, clamping doesn't
    make sense for an id lookup (a clamped id would just be a different,
    wrong id) -- treating it as simply not found is the correct behavior,
    consistent with how an out-of-range id like -1 already behaves below.
    """
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM advancement_exams WHERE id=?", (exam_id,)).fetchone()
    except OverflowError:
        return None
    finally:
        conn.close()
    return dict(row) if row else None


def resolve_exam(exam_id: int, passed: bool, resolved_by: str, notes: str = ""):
    """Mark a pending exam as passed/failed. Does NOT change the member's
    level itself — the caller is responsible for calling set_level() on
    pass, so the decision to promote is always an explicit, visible step.
    """
    conn = _connect()
    conn.execute(
        """UPDATE advancement_exams
           SET status=?, passed=?, notes=?, resolved_by=?, resolved_at=datetime('now')
           WHERE id=?""",
        ("passed" if passed else "failed", 1 if passed else 0, notes, resolved_by, exam_id),
    )
    conn.commit()
    conn.close()


# ============================================================
#  SETTINGS (key-value store for runtime config)
# ============================================================

def get_setting(key: str, default: str = "") -> str:
    """Get a setting value."""
    conn = _connect()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    """Set a setting value (upsert)."""
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()
    conn.close()


# ============================================================
#  FEATURE FLAGS (Aegis Phase 1 — decouple deploy from release)
# ============================================================

def is_feature_enabled(name: str, discord_id: str = None) -> bool:
    """Check if a feature flag is enabled for a given member.

    A flag that has never been set at all is treated as disabled (fail
    closed, not fail open — a typo'd flag name should never accidentally
    turn a feature on for everyone). Once `enabled=1`:
      - an empty `allowed_ids` means "on for everyone"
      - a non-empty `allowed_ids` restricts it to that comma-separated
        allowlist of discord_ids (the beta-squad case) — a discord_id
        of None (no specific member context, e.g. a scheduled task) is
        only ever treated as enabled if the allowlist is empty.
    """
    conn = _connect()
    row = conn.execute("SELECT enabled, allowed_ids FROM feature_flags WHERE name=?", (name,)).fetchone()
    conn.close()
    if row is None or not row["enabled"]:
        return False
    allowed_ids = row["allowed_ids"] or ""
    if not allowed_ids.strip():
        return True
    allowed_list = {a.strip() for a in allowed_ids.split(",") if a.strip()}
    return discord_id is not None and str(discord_id) in allowed_list


def set_feature_flag(name: str, enabled: bool, allowed_ids: str = "", updated_by: str = ""):
    """Enable/disable a feature flag, optionally restricted to an
    allowlist of comma-separated discord_ids. Upserts so the same
    command works whether the flag has ever been touched before.

    Passing allowed_ids="" while enabled=True means "on for everyone" —
    the deliberate full-release case, not a mistake. Disabling a flag
    that had an active allowlist also clears that allowlist, so a later
    `!flag enable <name>` (with no allowlist) starts from a clean
    "everyone" state rather than silently inheriting a stale beta list.
    """
    conn = _connect()
    conn.execute(
        """INSERT INTO feature_flags (name, enabled, allowed_ids, updated_at, updated_by)
           VALUES (?, ?, ?, datetime('now'), ?)
           ON CONFLICT(name) DO UPDATE SET
               enabled=excluded.enabled,
               allowed_ids=excluded.allowed_ids,
               updated_at=excluded.updated_at,
               updated_by=excluded.updated_by""",
        (name, 1 if enabled else 0, allowed_ids if enabled else "", updated_by),
    )
    conn.commit()
    conn.close()


def list_feature_flags() -> list[dict]:
    """List all feature flags that have ever been set, most recently
    updated first."""
    conn = _connect()
    rows = conn.execute("SELECT * FROM feature_flags ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
#  UTILITY / STATS
# ============================================================

def member_count() -> int:
    """Total active members."""
    conn = _connect()
    row = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE status='active'").fetchone()
    conn.close()
    return row["cnt"] if row else 0


def total_submissions_today() -> int:
    """Count all submissions across all members today."""
    today = datetime.date.today().isoformat()
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM daily_submissions WHERE date=?", (today,)
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def days_since_active(member: dict) -> int:
    """Whole days since a member's last_active_at, from a member dict
    already fetched (e.g. via all_active_members()) — avoids a second
    query per member when scanning the whole roster."""
    last = datetime.datetime.fromisoformat(member["last_active_at"])
    return (datetime.datetime.now() - last).days


def declining_assessment_members() -> list[dict]:
    """Members whose two most recent weekly assessments both exist and
    the score dropped (most recent < previous) — a real trend, not just
    a single bad week. Returns each member dict with two extra keys:
    'latest_score' and 'previous_score'.

    Deliberately a stricter/different signal from
    features.check_at_risk_members() (which fires on any single
    score < 70, regardless of trend) — this one is about knowing
    someone is sliding even if they haven't crossed the at-risk
    threshold yet.
    """
    conn = _connect()
    rows = conn.execute(
        """
        SELECT a1.discord_id, a1.overall_score as latest_score,
               a2.overall_score as previous_score
        FROM assessments a1
        JOIN assessments a2 ON a2.discord_id = a1.discord_id
                            AND a2.week_number = a1.week_number - 1
        WHERE a1.overall_score IS NOT NULL AND a2.overall_score IS NOT NULL
          AND a1.overall_score < a2.overall_score
          AND a1.week_number = (
              SELECT MAX(week_number) FROM assessments a3
              WHERE a3.discord_id = a1.discord_id
          )
        """
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        m = get_member(r["discord_id"])
        if m and m["status"] == "active":
            m = dict(m)
            m["latest_score"] = r["latest_score"]
            m["previous_score"] = r["previous_score"]
            result.append(m)
    return result


def inactive_members(days: int = 3) -> list[dict]:
    """Get members who haven't been active for N+ days."""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM members WHERE status='active' AND last_active_at < ?",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_buddy_load(buddy_discord_id: str) -> int:
    """Count how many active members currently have this person as their
    buddy. Used by features.assign_buddy() to rotate new-member
    assignments across all eligible buddies by current load, instead of
    always assigning the same single person."""
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM members WHERE status='active' AND buddy_id=?",
        (buddy_discord_id,),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def members_with_buddy(buddy_discord_id: str) -> list[dict]:
    """Get all active members whose buddy is this person."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM members WHERE status='active' AND buddy_id=?",
        (buddy_discord_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def member_week_number(discord_id: str) -> int:
    """Calculate which week a member is in (from join date)."""
    member = get_member(discord_id)
    if not member:
        return 1
    joined = datetime.datetime.fromisoformat(member["joined_at"])
    days = (datetime.datetime.now() - joined).days
    return max(1, (days // 7) + 1)
