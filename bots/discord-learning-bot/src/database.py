"""Empire English Community Bot — Database Layer (SQLite).

Handles all persistent state: members, daily submissions, streaks,
weekly assessments, points/badges, and operational settings.

Schema designed for the 7-task daily loop, weekly assessments,
and level advancement tracking described in the Learning System blueprint.
"""
import sqlite3
import datetime
from pathlib import Path
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
    conn.close()


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
    """Update arbitrary fields on a member."""
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [discord_id]
    conn = _connect()
    conn.execute(f"UPDATE members SET {sets}, last_active_at=datetime('now') WHERE discord_id=?", values)
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
    """Set current streak and update longest if needed."""
    conn = _connect()
    member = conn.execute(
        "SELECT longest_streak FROM members WHERE discord_id=?", (discord_id,)
    ).fetchone()
    longest = max(streak, member["longest_streak"] if member else 0)
    conn.execute(
        "UPDATE members SET current_streak=?, longest_streak=? WHERE discord_id=?",
        (streak, longest, discord_id),
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
    """Add points to a member and log the event."""
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
    """Save a weekly assessment result."""
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
    """Log an advancement exam attempt."""
    conn = _connect()
    conn.execute(
        """INSERT INTO advancement_exams
           (discord_id, from_level, to_level, speaking_score, listening_score,
            vocabulary_score, accent_score, writing_score, passed, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            discord_id, from_level, to_level,
            scores.get("speaking"), scores.get("listening"),
            scores.get("vocabulary"), scores.get("accent"),
            scores.get("writing"), 1 if passed else 0, notes,
        ),
    )
    conn.commit()
    conn.close()


def last_advancement_attempt(discord_id: str) -> Optional[dict]:
    """Get the most recent advancement exam attempt."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM advancement_exams WHERE discord_id=? ORDER BY attempted_at DESC LIMIT 1",
        (discord_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


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


def member_week_number(discord_id: str) -> int:
    """Calculate which week a member is in (from join date)."""
    member = get_member(discord_id)
    if not member:
        return 1
    joined = datetime.datetime.fromisoformat(member["joined_at"])
    days = (datetime.datetime.now() - joined).days
    return max(1, (days // 7) + 1)
