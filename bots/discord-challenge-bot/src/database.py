"""SQLite storage for participants and their daily progress. 100% free, no server."""
import sqlite3
from datetime import date
from . import config


def _connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS participants (
            user_id    TEXT PRIMARY KEY,
            username   TEXT,
            goal       TEXT,
            joined_at  TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS progress (
            user_id   TEXT,
            day       INTEGER,
            feeling   INTEGER,
            logged_at TEXT,
            PRIMARY KEY (user_id, day)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def get_setting(key: str, default: str = "") -> str:
    """Retrieve a persistent setting from the database."""
    conn = _connect()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    """Store a persistent setting in the database."""
    conn = _connect()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def register(user_id: str, username: str, goal: str = ""):
    conn = _connect()
    conn.execute(
        """INSERT INTO participants (user_id, username, goal, joined_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,
               goal=CASE WHEN excluded.goal != '' THEN excluded.goal ELSE participants.goal END""",
        (user_id, username, goal, date.today().isoformat()),
    )
    conn.commit()
    conn.close()


def log_done(user_id: str, username: str, day: int, feeling: int):
    """Record that a user completed a given day. Returns True if newly logged."""
    register(user_id, username)
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO progress (user_id, day, feeling, logged_at)
               VALUES (?, ?, ?, ?)""",
            (user_id, day, feeling, date.today().isoformat()),
        )
        conn.commit()
        newly = True
    except sqlite3.IntegrityError:
        newly = False  # already logged this day
    conn.close()
    return newly


def completed_count(user_id: str) -> int:
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM progress WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row["n"]


def current_streak(user_id: str) -> int:
    """Longest run of consecutive completed day-numbers ending at the user's max day."""
    conn = _connect()
    rows = conn.execute(
        "SELECT day FROM progress WHERE user_id = ? ORDER BY day", (user_id,)
    ).fetchall()
    conn.close()
    days = [r["day"] for r in rows]
    if not days:
        return 0
    streak = 1
    best_tail = 1
    for i in range(1, len(days)):
        if days[i] == days[i - 1] + 1:
            best_tail += 1
        else:
            best_tail = 1
        streak = max(streak, best_tail)
    # streak ending at the latest day
    tail = 1
    for i in range(len(days) - 1, 0, -1):
        if days[i] == days[i - 1] + 1:
            tail += 1
        else:
            break
    return tail


def leaderboard(limit: int = 10):
    conn = _connect()
    rows = conn.execute(
        """SELECT p.username, COUNT(pr.day) AS done
           FROM participants p
           LEFT JOIN progress pr ON p.user_id = pr.user_id
           GROUP BY p.user_id
           ORDER BY done DESC, p.username ASC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [(r["username"], r["done"]) for r in rows]


def get_participant(user_id: str):
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM participants WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def all_participants():
    conn = _connect()
    rows = conn.execute("SELECT user_id, username FROM participants").fetchall()
    conn.close()
    return [(r["user_id"], r["username"]) for r in rows]
