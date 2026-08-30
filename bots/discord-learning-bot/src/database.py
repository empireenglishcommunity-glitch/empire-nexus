"""Empire English Community Bot — Database Layer (SQLite).

Handles all persistent state: members, daily submissions, streaks,
weekly assessments, points/badges, and operational settings.

Schema designed for the 7-task daily loop, weekly assessments,
and level advancement tracking described in the Learning System blueprint.
"""
import sqlite3
import datetime
import json
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
    # Wait (up to 5s) instead of erroring when another connection holds the
    # write lock. Required for the atomic BEGIN IMMEDIATE reservation below so
    # simultaneous submits (double-tap / client retry) queue rather than raise
    # "database is locked".
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _today_local() -> datetime.date:
    """'Today' in the bot's configured timezone (Asia/Dubai by default),
    not the server/UTC clock.

    Phase E audit (owner feedback #9 — "finished all tasks but it still
    shows remaining") found a real bug behind part of this confusion:
    every date-sensitive read in this module used bare
    `datetime.date.today()`, which follows the SERVER's system clock
    (UTC on this deployment), while submissions are LOGGED under
    `tasks.today_str()`'s timezone-aware Asia/Dubai date (same pattern
    already used by `darb._today_local()` for the personal calendar).
    For the ~4-hour window each night where the UTC calendar date has
    already flipped but Dubai's hasn't yet (20:00-24:00 UTC = 00:00-04:00
    Dubai) -- or the reverse gap depending on how the two clocks
    disagree -- a submission logged under "today" (Dubai) would then be
    read back by `tasks_completed_today()`/`_recompute_streak()`/etc.
    against the WRONG (server) "today", making a just-completed task
    invisible to `!progress`, `!today`, `!done`, and the practice-page
    API's `tasks_today` field until the server's date caught up. This
    single helper replaces every date-sensitive `datetime.date.today()`
    call in this module so they all agree with `tasks.today_str()`
    (and `darb._today_local()`) about what day it is.
    """
    try:
        from zoneinfo import ZoneInfo
        tz = getattr(config, "TIMEZONE", "Asia/Dubai") or "Asia/Dubai"
        return datetime.datetime.now(ZoneInfo(tz)).date()
    except Exception:
        return datetime.date.today()


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
    # Dhaka' A0: difficulty_level on members table
    member_cols = {row["name"] for row in conn.execute("PRAGMA table_info(members)")}
    if "difficulty_level" not in member_cols:
        conn.execute("ALTER TABLE members ADD COLUMN difficulty_level INTEGER NOT NULL DEFAULT 2")

    # Masar D033 fix: gender field on members table. Egyptian Arabic
    # second-person grammar requires knowing the addressee's gender
    # (masculine "-ك"/"عليك" vs feminine "-كي"/"عليكي") -- this field
    # never existed anywhere in this codebase before, which is the
    # root cause of Nour addressing a real male student with feminine
    # grammar (found live during Masar M3's testing). '' means unknown
    # -- every existing student today, until they explicitly set it via
    # !gender. Nothing defaults to a guess; unknown is handled by using
    # genuinely gender-neutral phrasing, never a silent assumption.
    if "gender" not in member_cols:
        conn.execute("ALTER TABLE members ADD COLUMN gender TEXT NOT NULL DEFAULT ''")

    # Darb Phase 6: level_started_at anchors the personal calendar to when
    # the student began their CURRENT level, not their original bot-join
    # date. Nullable — when NULL, callers fall back to joined_at (so every
    # existing student is unchanged: their calendar/week keep their current
    # position). It is set to 'now' on a level promotion (set_level), so a
    # student advancing L0->L1 correctly restarts at Week 1 Day 1 of the
    # new level instead of the calendar thinking they're 8 weeks deep.
    if "level_started_at" not in member_cols:
        conn.execute("ALTER TABLE members ADD COLUMN level_started_at TEXT DEFAULT NULL")

    # `level` on daily_submissions. Writing and community are Discord-only
    # tasks, so they never reach practice_mastery (which IS level-scoped) and
    # `practice_completions` has to bridge them onto a content day. Without a
    # level here that bridge had to attribute a submission to whichever level was
    # being queried, so a C2 student's writing also appeared as evidence at A1.
    # That could never grant anything (the WORK criterion is 0/70 at a level you
    # never studied, and the certificate re-targets to the exam actually passed),
    # but it over-reported evidence on a level the student never took.
    #
    # Nullable on purpose. Rows written before this column existed keep NULL, and
    # the bridge deliberately falls back to the old anchor-only behaviour for
    # them — so no existing student loses a single piece of retroactive evidence.
    # New rows carry their level and are matched exactly.
    ds_cols = {row["name"] for row in conn.execute("PRAGMA table_info(daily_submissions)")}
    if "level" not in ds_cols:
        conn.execute("ALTER TABLE daily_submissions ADD COLUMN level TEXT DEFAULT NULL")

    # Wuslah W0.4: last_used on link_tokens table (for token expiry)
    lt_cols = {row["name"] for row in conn.execute("PRAGMA table_info(link_tokens)")}
    if "last_used" not in lt_cols:
        conn.execute("ALTER TABLE link_tokens ADD COLUMN last_used TEXT DEFAULT NULL")

    # Taqdeem Phase 0: add `type` column to assessment_attempts so the same table
    # can hold weekly, monthly, and advancement attempts. Default 'weekly' means
    # all existing rows (from Itqan) remain correctly typed without data migration.
    aa_cols = {row["name"] for row in conn.execute("PRAGMA table_info(assessment_attempts)")}
    if "type" not in aa_cols:
        conn.execute("ALTER TABLE assessment_attempts ADD COLUMN type TEXT NOT NULL DEFAULT 'weekly'")

    conn.commit()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    discord_id      TEXT PRIMARY KEY,
    discord_name    TEXT NOT NULL DEFAULT '',
    telegram_id     TEXT DEFAULT '',
    level           TEXT NOT NULL DEFAULT 'A1',
    track           TEXT NOT NULL DEFAULT 'Core',
    goal            TEXT DEFAULT '',
    joined_at       TEXT NOT NULL DEFAULT (datetime('now')),
    last_active_at  TEXT NOT NULL DEFAULT (datetime('now')),
    total_points    INTEGER NOT NULL DEFAULT 0,
    current_streak  INTEGER NOT NULL DEFAULT 0,
    longest_streak  INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'active',
    buddy_id        TEXT DEFAULT '',
    notes           TEXT DEFAULT '',
    gender          TEXT NOT NULL DEFAULT ''
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

-- Nabd (student-notifications spec) Phase N0: notification preferences
-- and log tables. Enables personal, time-aware, opt-out-able notifications.
CREATE TABLE IF NOT EXISTS notification_preferences (
    discord_id      TEXT PRIMARY KEY,
    morning_dm      INTEGER NOT NULL DEFAULT 1,
    evening_dm      INTEGER NOT NULL DEFAULT 1,
    streak_alert    INTEGER NOT NULL DEFAULT 1,
    celebrations    INTEGER NOT NULL DEFAULT 1,
    social_proof    INTEGER NOT NULL DEFAULT 0,
    weekly_summary  INTEGER NOT NULL DEFAULT 1,
    quiet_start     TEXT DEFAULT '23:00',
    quiet_end       TEXT DEFAULT '05:00',
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

CREATE TABLE IF NOT EXISTS notification_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    notification_type TEXT NOT NULL,
    date            TEXT NOT NULL,
    sent_at         TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_notif_log ON notification_log(discord_id, notification_type, date);

-- Tatawwur Phase T2: spaced repetition for vocabulary recall (SM-2 algorithm).
CREATE TABLE IF NOT EXISTS vocab_srs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    word            TEXT NOT NULL,
    ease_factor     REAL NOT NULL DEFAULT 2.5,
    interval_days   INTEGER NOT NULL DEFAULT 1,
    next_review     TEXT NOT NULL DEFAULT (date('now', '+1 day')),
    review_count    INTEGER NOT NULL DEFAULT 0,
    last_score      INTEGER NOT NULL DEFAULT 0,
    added_at        TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id),
    UNIQUE(discord_id, word)
);
CREATE INDEX IF NOT EXISTS idx_vocab_srs_review ON vocab_srs(discord_id, next_review);

-- Sahel Phase S6: personal link tokens for practice platform connection.
CREATE TABLE IF NOT EXISTS link_tokens (
    token           TEXT PRIMARY KEY,
    discord_id      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    last_used       TEXT DEFAULT NULL,
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_link_tokens_member ON link_tokens(discord_id);

-- ============================================================
--  DARB (درب) — Phase 1 backend foundation
--  Gated personal practice experience. These tables are inert until
--  the Darb API endpoints + practice-page UI (Phases 2-3) use them.
-- ============================================================

-- Darb: one-time claim codes. `!link` issues a single-use code; the
-- student enters it on the practice gate to mint a device session.
-- Issuing a new code soft-invalidates any prior unconsumed one
-- (expires_at set to the past) rather than deleting it, so history is
-- preserved for rate-limiting.
CREATE TABLE IF NOT EXISTS claim_codes (
    code            TEXT PRIMARY KEY,
    discord_id      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at      TEXT NOT NULL,
    consumed_at     TEXT DEFAULT NULL,
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_claim_codes_member ON claim_codes(discord_id);

-- Darb: durable per-device web sessions (max 2 active per student). A
-- claim mints a new device_id here; the signed session cookie carries
-- it. Revoking a row makes the edge gate fail for that device.
CREATE TABLE IF NOT EXISTS device_sessions (
    device_id       TEXT PRIMARY KEY,
    discord_id      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at    TEXT DEFAULT NULL,
    created_ip      TEXT DEFAULT '',
    user_agent      TEXT DEFAULT '',
    revoked         INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_device_sessions_member ON device_sessions(discord_id);

-- Darb: content-day-aware completion + mastery. The single source of
-- truth for the personal calendar (green days) and the 5-tier mastery
-- colors. Keyed by the CONTENT day (level/week/day/exercise), not the
-- calendar date, so catch-up and cross-device both work. completion_count
-- is the mastery tier driver (capped at 5); it increments at most once
-- per calendar day (guarded by last_completed_date).
CREATE TABLE IF NOT EXISTS practice_mastery (
    discord_id            TEXT NOT NULL,
    level                 TEXT NOT NULL,
    week                  INTEGER NOT NULL,
    day                   INTEGER NOT NULL,
    exercise              TEXT NOT NULL,
    completion_count      INTEGER NOT NULL DEFAULT 0,
    first_completed_date  TEXT,
    last_completed_date   TEXT,
    PRIMARY KEY (discord_id, level, week, day, exercise),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_practice_mastery_member ON practice_mastery(discord_id, level);

-- Enhancement E5: persistent voice-lounge minutes per day, so the
-- community task's 10-minute requirement survives a bot restart (was
-- in-memory only and reset on every restart). Keyed by (discord_id, date).
CREATE TABLE IF NOT EXISTS voice_minutes (
    discord_id  TEXT NOT NULL,
    date        TEXT NOT NULL,
    minutes     REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (discord_id, date),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

-- Nour Phase N0: conversation memory for AI concierge.
CREATE TABLE IF NOT EXISTS nour_conversations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    role            TEXT NOT NULL,
    message         TEXT NOT NULL,
    intent          TEXT DEFAULT '',
    confidence      REAL DEFAULT 1.0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_nour_conversations ON nour_conversations(discord_id, created_at);

-- Dhaka' Phase P0: pronunciation scoring results.
CREATE TABLE IF NOT EXISTS pronunciation_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    date            TEXT NOT NULL,
    task_id         TEXT NOT NULL,
    score           REAL NOT NULL,
    expected_text   TEXT NOT NULL,
    transcript      TEXT NOT NULL,
    missed_words    TEXT DEFAULT '',
    feedback        TEXT DEFAULT '',
    audio_url       TEXT DEFAULT '',
    scored_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_pronunciation_scores ON pronunciation_scores(discord_id, date);

-- Masar Phase M0.4 / M2: Nour's Weekly Growth Letter cache. Fixes
-- Hisn D020 with a real, verified generation path
-- (narrative_engine.build_growth_letter()) -- generated once per week
-- per student by nour_growth_letter_task() (M2.2), cached here so the
-- dashboard's /api/growth-letter (M2.4) serves it with zero extra AI
-- cost per page load.
CREATE TABLE IF NOT EXISTS nour_growth_letters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    letter_text     TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'ai',  -- 'ai' or 'template_fallback'
    generated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    week            INTEGER NOT NULL,
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_growth_letters ON nour_growth_letters(discord_id, week);

-- Hisn D028: verify_audio() checks "did this student post ANY
-- audio-looking attachment in #l0-showcase in the last 2 hours?" for
-- accent, speaking, AND shadow alike, with no memory of which specific
-- message was already used to satisfy which task. Confirmed live
-- during Hisn H6: one recording uploaded once satisfied !done shadow,
-- then satisfied !done speaking too, with zero new proof of work for
-- the second task -- and would keep satisfying any of the 3 audio
-- task types repeatedly for the full 2-hour window. This table
-- persists (survives bot restarts, unlike an in-memory set) which
-- specific Discord message IDs have already been consumed as proof
-- for which specific task, so verify_audio() can require a NEW,
-- not-yet-consumed message for each task type.
-- message_id alone is the PRIMARY KEY (not composite with task_id):
-- once a specific message has been consumed as proof for ANY task
-- type, it must never satisfy a DIFFERENT task type either -- that's
-- exactly the bug (one shadow recording also satisfying speaking).
CREATE TABLE IF NOT EXISTS consumed_proof_messages (
    message_id      TEXT PRIMARY KEY,
    discord_id      TEXT NOT NULL,
    task_id         TEXT NOT NULL,
    consumed_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_consumed_proof ON consumed_proof_messages(discord_id, task_id);

-- Hissar P4: persistent cooldown tracking (survives bot restarts).
-- In-memory dict loses all cooldown state on restart, letting students
-- immediately submit again. This table stores the actual last-done
-- timestamp per student, checked before the in-memory fallback.
CREATE TABLE IF NOT EXISTS done_cooldowns (
    discord_id      TEXT PRIMARY KEY,
    last_done_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Hissar P5: IP logging for token sharing detection.
-- Every API request that uses a token logs the source IP here.
-- If a single token shows 5+ unique IPs, it's flagged as suspicious.
CREATE TABLE IF NOT EXISTS token_ip_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token           TEXT NOT NULL,
    ip_address      TEXT NOT NULL,
    first_seen      TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen       TEXT NOT NULL DEFAULT (datetime('now')),
    request_count   INTEGER NOT NULL DEFAULT 1,
    UNIQUE(token, ip_address)
);
CREATE INDEX IF NOT EXISTS idx_token_ip ON token_ip_log(token);

-- Rawiya R2: structured onboarding journey state machine.
-- Tracks where each student is in their guided first-week experience.
-- This is the ACTIVE onboarding journey (nour_journey.py).
CREATE TABLE IF NOT EXISTS student_journey (
    discord_id      TEXT PRIMARY KEY,
    current_step    TEXT NOT NULL DEFAULT 'welcome',
    step_data       TEXT DEFAULT '{}',
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    last_step_at    TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT DEFAULT NULL,
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

-- design.md Section 9.1: onboarding coverage model — independent
-- boolean facts about what a new student has already discovered
-- (daily tasks, platform link, streaks, channels, first task done).
-- Each flips based on a real signal (task completion, !link usage,
-- channel visits), written by set_journey_coverage(). Actively used
-- by the onboarding journey / nudges (nour_onboarding, nour_journey).
CREATE TABLE IF NOT EXISTS journey_coverage (
    discord_id          TEXT PRIMARY KEY,
    knows_daily_tasks   INTEGER NOT NULL DEFAULT 0,
    knows_platform_link INTEGER NOT NULL DEFAULT 0,
    knows_streaks       INTEGER NOT NULL DEFAULT 0,
    knows_channels      INTEGER NOT NULL DEFAULT 0,
    first_task_done     INTEGER NOT NULL DEFAULT 0,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

-- Student-history reset CONSENT LEDGER (governance / proof).
-- APPEND-ONLY: nothing in the reset path ever updates or deletes rows here.
-- Deliberately has NO foreign key to members, so the proof survives even a
-- full account deletion. Stores the exact consent shown + the student's
-- affirmation + a full pre-deletion snapshot (which also enables restore).
CREATE TABLE IF NOT EXISTS reset_consent_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id       TEXT NOT NULL,
    discord_name     TEXT NOT NULL DEFAULT '',
    initiated_by     TEXT NOT NULL DEFAULT '',
    consent_text     TEXT NOT NULL DEFAULT '',
    affirmation      TEXT NOT NULL DEFAULT '',
    reason           TEXT NOT NULL DEFAULT '',
    snapshot_json    TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    created_at_local TEXT NOT NULL DEFAULT ''
);

-- Owner-approval gate for STUDENT-initiated resets. A `!resetme` (after the
-- student's consent) creates a 'pending' row here instead of wiping; the owner
-- then /approve or /deny it. Nothing is deleted until approval. Linked to the
-- consent ledger via consent_id once approved.
CREATE TABLE IF NOT EXISTS pending_resets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id    TEXT NOT NULL,
    discord_name  TEXT NOT NULL DEFAULT '',
    consent_text  TEXT NOT NULL DEFAULT '',
    affirmation   TEXT NOT NULL DEFAULT '',
    reason        TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|denied|expired|superseded
    requested_at  TEXT NOT NULL DEFAULT (datetime('now')),
    decided_by    TEXT NOT NULL DEFAULT '',
    decided_at    TEXT DEFAULT NULL,
    consent_id    INTEGER DEFAULT NULL
);

-- Itqan (weekly mastery assessment). One row per attempt at a week's test.
CREATE TABLE IF NOT EXISTS assessment_attempts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id        TEXT NOT NULL,
    level             TEXT NOT NULL,
    week              INTEGER NOT NULL,
    attempt_no        INTEGER NOT NULL DEFAULT 1,
    started_at        TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at       TEXT DEFAULT NULL,
    status            TEXT NOT NULL DEFAULT 'in_progress',  -- in_progress|scored|flagged
    consistency_pct   REAL DEFAULT NULL,
    mastery_pct       REAL DEFAULT NULL,
    result            TEXT DEFAULT NULL,                    -- mastered|distinction|not_yet
    time_expired      INTEGER NOT NULL DEFAULT 0,
    integrity_flags   TEXT NOT NULL DEFAULT '{}',           -- JSON: tab-aways, paste attempts, ...
    seed              TEXT NOT NULL DEFAULT '',             -- deterministic item draw per attempt
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_assessment_attempts_member ON assessment_attempts(discord_id, level, week);

-- One row per question in an attempt (feeds per-item feedback + "most-missed"
-- owner reporting). discord_id is denormalized so reset/backup stay simple.
CREATE TABLE IF NOT EXISTS assessment_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id    INTEGER NOT NULL,
    discord_id    TEXT NOT NULL,
    item_no       INTEGER NOT NULL,
    skill         TEXT NOT NULL,                -- listening|vocab|pronunciation|speaking|writing
    source_week   INTEGER NOT NULL,
    prompt_ref    TEXT NOT NULL DEFAULT '',
    expected      TEXT NOT NULL DEFAULT '',
    answer        TEXT NOT NULL DEFAULT '',
    auto_score    REAL DEFAULT NULL,
    ai_score      REAL DEFAULT NULL,
    correct       INTEGER DEFAULT NULL,
    feedback      TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (attempt_id) REFERENCES assessment_attempts(id)
);
CREATE INDEX IF NOT EXISTS idx_assessment_items_attempt ON assessment_items(attempt_id);
CREATE INDEX IF NOT EXISTS idx_assessment_items_member ON assessment_items(discord_id);

-- Durable "Week Mastered" record + badge source of truth (one row per student
-- per content week once they've mastered it).
CREATE TABLE IF NOT EXISTS week_mastery (
    discord_id      TEXT NOT NULL,
    level           TEXT NOT NULL,
    week            INTEGER NOT NULL,
    mastered        INTEGER NOT NULL DEFAULT 0,
    distinction     INTEGER NOT NULL DEFAULT 0,
    mastered_at     TEXT DEFAULT NULL,
    best_attempt_id INTEGER DEFAULT NULL,
    PRIMARY KEY (discord_id, level, week),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

-- Itqan Phase 9: retain assessment audio recordings for OWNER review only
-- (speaking/pronunciation). Private, owner-gated via !itqan-review, and
-- auto-purged after a retention window (default 14 days) or on reset.
CREATE TABLE IF NOT EXISTS assessment_recordings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id   INTEGER NOT NULL,
    discord_id   TEXT NOT NULL,
    item_no      INTEGER NOT NULL,
    skill        TEXT NOT NULL DEFAULT '',
    filename     TEXT NOT NULL DEFAULT 'recording.webm',
    audio        BLOB NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (attempt_id, item_no),
    FOREIGN KEY (attempt_id) REFERENCES assessment_attempts(id)
);
CREATE INDEX IF NOT EXISTS idx_assessment_recordings_attempt ON assessment_recordings(attempt_id);
CREATE INDEX IF NOT EXISTS idx_assessment_recordings_created ON assessment_recordings(created_at);

-- Nutq: Azure Pronunciation Assessment cost controls.
--  * azure_usage: monthly audio-seconds sent to Azure — the usage GUARD reads
--    this and switches to the free local engine at ~90% of the free tier.
--  * azure_shadow_calls: per-student per-day Azure call count — the cost POLICY
--    (1 graded + up to 2 try-again re-checks per day) reads this.
CREATE TABLE IF NOT EXISTS azure_usage (
    month          TEXT PRIMARY KEY,            -- local 'YYYY-MM'
    audio_seconds  REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS azure_shadow_calls (
    discord_id     TEXT NOT NULL,
    date           TEXT NOT NULL,               -- local 'YYYY-MM-DD'
    count          INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (discord_id, date)
);
-- Nutq: per-student override of the daily official-grade cap. Absent row =
-- use the global default (NUTQ_AZURE_MAX_CALLS_PER_DAY). Owner-managed via the
-- /nutq cap command (PR3) so specific students can get more/fewer grades/day.
CREATE TABLE IF NOT EXISTS nutq_daily_cap_overrides (
    discord_id     TEXT PRIMARY KEY,
    cap            INTEGER NOT NULL
);

-- Majlis Phase 0: persistent together-minutes per day. Tracks how many
-- minutes a student spent in a Majlis lounge WITH at least one other member
-- present. Same pattern as voice_minutes (upsert, keyed by discord_id+date).
-- Used for the company-aware task #7 credit (R1): voice half done if
-- voice_min >= 10 OR together_min >= community_together_minutes.
CREATE TABLE IF NOT EXISTS together_minutes (
    discord_id  TEXT NOT NULL,
    date        TEXT NOT NULL,
    minutes     REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (discord_id, date),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

-- Taqdeem Phase 0: Monthly Progress Review tracking.
CREATE TABLE IF NOT EXISTS monthly_reviews (
    discord_id      TEXT NOT NULL,
    review_number   INTEGER NOT NULL,    -- 1st, 2nd monthly for this level
    level           TEXT NOT NULL,
    attempt_id      INTEGER DEFAULT NULL,-- FK to assessment_attempts
    passed          INTEGER NOT NULL DEFAULT 0,
    retention_score REAL DEFAULT NULL,
    skill_breakdown TEXT DEFAULT '',      -- JSON: {listening: 72, vocab: 85, ...}
    reviewed_at     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (discord_id, level, review_number),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

-- Mi'yar Phase 0: CEFR migration snapshots (reversible). One row per student
-- per migration run, holding a full pre-migration snapshot for rollback.
CREATE TABLE IF NOT EXISTS cefr_migration_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id    TEXT NOT NULL,
    from_level    TEXT NOT NULL,
    to_level      TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    migrated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    rolled_back   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_cefr_migration_member ON cefr_migration_log(discord_id);

-- Taqdeem Phase 0: Level Advancement Exam tracking.
CREATE TABLE IF NOT EXISTS advancement_exams (
    discord_id      TEXT NOT NULL,
    level           TEXT NOT NULL,       -- the level being tested (e.g. 'L0')
    attempt_num     INTEGER NOT NULL,    -- 1, 2, 3...
    attempt_id      INTEGER DEFAULT NULL,-- FK to assessment_attempts (Part A)
    part_b_recording TEXT DEFAULT '',    -- path/URL to the Part B recording
    part_a_score    REAL DEFAULT NULL,
    part_b_score    REAL DEFAULT NULL,
    overall_score   REAL DEFAULT NULL,
    skill_mins      TEXT DEFAULT '',     -- JSON: per-skill scores for min check
    passed          INTEGER NOT NULL DEFAULT 0,
    promoted        INTEGER NOT NULL DEFAULT 0,
    attempted_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (discord_id, level, attempt_num),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

-- Phase 8 (Mi'yar CEFR): exit-exam boundary review queue. A result within the
-- review band of a cut, or rated with low AI confidence, is NOT auto-decided —
-- it lands here for the owner to pass/fail. Clear passes/fails never enqueue.
CREATE TABLE IF NOT EXISTS exit_exam_reviews (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id    TEXT NOT NULL,
    level         TEXT NOT NULL,        -- CEFR level being tested (A1-C2)
    attempt_num   INTEGER DEFAULT NULL, -- FK-ish to advancement_exams.attempt_num
    part_a_pct    REAL DEFAULT NULL,
    part_b_total  INTEGER DEFAULT NULL,
    ai_confidence REAL DEFAULT NULL,
    rater         TEXT DEFAULT '',      -- 'ai' | 'rule'
    reasons       TEXT DEFAULT '',      -- JSON list of why it needs review
    evidenced     TEXT DEFAULT '',      -- JSON list of can-do codes evidenced
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending | passed | failed
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at   TEXT DEFAULT NULL,
    resolved_by   TEXT DEFAULT NULL,
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

-- Phase 8 (Mi'yar CEFR): placement results. One row per placement attempt; the
-- per-skill CEFR profile is stored as JSON so the profile can be shown to the
-- student and owner without recomputing.
CREATE TABLE IF NOT EXISTS placement_result (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id     TEXT NOT NULL,
    overall_level  TEXT NOT NULL,       -- CEFR level the student is slotted into
    skill_bands    TEXT DEFAULT '',     -- JSON: {vocab_grammar, listening, writing, speaking}
    recommended_week INTEGER NOT NULL DEFAULT 1,
    source         TEXT DEFAULT 'self', -- 'self' | 'owner' | 'import'
    taken_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

-- Phase 8 (Mi'yar CEFR): in-progress placement runner state (one per student).
-- Transient working state for the adaptive session; cleared when placement
-- finishes or is slotted. Deliberately NO FK — a placement can be taken before
-- a full member row exists, and the row is throwaway.
CREATE TABLE IF NOT EXISTS placement_session (
    discord_id  TEXT PRIMARY KEY,
    state       TEXT NOT NULL DEFAULT '{}',  -- JSON: runner state (see placement_runner)
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Ijtihad Phase 2: effort seasons. Fixed, community-wide 4-week windows (not
-- per-student) so everyone shares one rhythm and boards are comparable.
--
-- Season effort is DERIVED, never stored: it is SUM(points_log.points) with
-- date(logged_at) inside a season's window. points_log already timestamps every
-- award, so this needs no migration of historical data and no new points column.
-- Two deliberate consequences:
--   * all pre-Ijtihad points fall outside every season window, so they become
--     legacy-only (they show in Sijil, never on a season board);
--   * rollback is flipping a flag -- nothing was rewritten.
CREATE TABLE IF NOT EXISTS seasons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    label       TEXT NOT NULL,                  -- "Season 1"
    started_on  TEXT NOT NULL,                  -- ISO date, inclusive
    ends_on     TEXT NOT NULL,                  -- ISO date, inclusive
    UNIQUE(started_on)
);
"""


# ============================================================
#  STUDENT HISTORY RESET + CONSENT LEDGER (governance)
# ============================================================
#
# Two data classes, deliberately separated:
#   • LEARNING HISTORY (submissions, mastery, SRS, points, streaks, ...) — the
#     thing a student can ask us to wipe.
#   • CONSENT RECORD — the append-only PROOF that a wipe was authorized. It is
#     never touched by the reset, and it carries a full pre-deletion snapshot
#     so a reset is also fully REVERSIBLE (this is what would have saved the
#     Balqees case).

# Tables wiped on a history reset (all keyed by discord_id). KEPT (not wiped):
# members (counters reset, account preserved), notification_preferences,
# link_tokens + device_sessions (so a reset never logs the student out), and
# reset_consent_log (the proof).
RESET_WIPE_TABLES = (
    "daily_submissions", "streaks", "assessments", "points_log",
    "notification_log", "vocab_srs", "practice_mastery", "voice_minutes",
    "nour_conversations", "pronunciation_scores", "nour_growth_letters",
    "consumed_proof_messages", "done_cooldowns", "token_ip_log",
    "student_journey", "journey_coverage", "claim_codes",
    "assessment_attempts", "assessment_items", "week_mastery",
    "assessment_recordings", "together_minutes",
    "monthly_reviews", "advancement_exams",
)


def _tables_with_discord_id(conn) -> list:
    out = []
    for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        t = r["name"]
        if t == "reset_consent_log":
            continue  # never snapshot the proof ledger itself (avoids recursion)
        cols = [c["name"] for c in conn.execute(f"PRAGMA table_info({t})").fetchall()]
        if "discord_id" in cols:
            out.append(t)
    return out


# --- Snapshot (JSON) serialization helpers -------------------------------
# Snapshots dump every row of every discord_id-keyed table to JSON. Some
# columns are raw BLOBs (e.g. assessment_recordings.audio), which the stdlib
# json encoder cannot serialize (`TypeError: Object of type bytes is not JSON
# serializable`). These helpers make snapshots round-trip safely: bytes are
# base64-encoded under a type marker on dump and decoded back to bytes on
# restore.
_BYTES_MARKER = "__bytes_b64__"
_BLOB_OMITTED_MARKER = "__blob_omitted__"


def _snapshot_json_default(o):
    """json.dumps `default` hook: encode raw bytes as base64 under a marker so
    a snapshot containing a BLOB (audio recordings, etc.) is serializable AND
    fully reversible via _decode_snapshot_value()."""
    import base64
    if isinstance(o, (bytes, bytearray)):
        return {_BYTES_MARKER: base64.b64encode(bytes(o)).decode("ascii")}
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def _dumps_snapshot(snapshot: dict) -> str:
    """Serialize a snapshot to JSON, tolerating raw-bytes columns."""
    import json as _json
    return _json.dumps(snapshot, ensure_ascii=False, default=_snapshot_json_default)


def _decode_snapshot_value(v):
    """Inverse of _snapshot_json_default: turn a base64 bytes-marker dict back
    into raw bytes so a restored row re-inserts a real BLOB. Leaves any other
    value (including omitted-blob markers) untouched."""
    import base64
    if isinstance(v, dict) and _BYTES_MARKER in v and len(v) == 1:
        return base64.b64decode(v[_BYTES_MARKER])
    return v


def snapshot_member_data(discord_id: str, include_blobs: bool = True) -> dict:
    """Full export of every row keyed to this student across ALL tables that
    have a discord_id column (dynamic, so future tables are covered). Used as
    the pre-deletion proof AND to make a reset reversible.

    include_blobs=True  -> raw BLOB columns are preserved (base64-encoded at
                           dump time via _dumps_snapshot) so the snapshot can
                           fully restore the row.
    include_blobs=False -> BLOB columns are replaced with a lightweight marker
                           recording only their byte length. Used by callers
                           (e.g. the CEFR migration log) that keep the snapshot
                           purely as proof and never restore from it, so they
                           don't bloat their log with megabytes of audio."""
    conn = _connect()
    try:
        data = {}
        for t in _tables_with_discord_id(conn):
            rows = conn.execute(f"SELECT * FROM {t} WHERE discord_id=?", (discord_id,)).fetchall()
            if rows:
                out = []
                for r in rows:
                    row_dict = dict(r)
                    if not include_blobs:
                        for k, v in list(row_dict.items()):
                            if isinstance(v, (bytes, bytearray)):
                                row_dict[k] = {_BLOB_OMITTED_MARKER: {"bytes": len(v)}}
                    out.append(row_dict)
                data[t] = out
        return data
    finally:
        conn.close()


def log_reset_consent(discord_id: str, discord_name: str, initiated_by: str,
                      consent_text: str, affirmation: str, reason: str,
                      snapshot: dict) -> int:
    """Append (never update/delete) a consent record to the reset ledger,
    including the full pre-deletion snapshot as proof + for restore."""
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO reset_consent_log (discord_id, discord_name, initiated_by, "
            "consent_text, affirmation, reason, snapshot_json, created_at_local) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (discord_id, discord_name, initiated_by, consent_text, affirmation,
             reason, _dumps_snapshot(snapshot), _today_local().isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_reset_consent_records(discord_id: str = None) -> list:
    """Retrieve consent proof (metadata only, not the heavy snapshot blob)."""
    conn = _connect()
    try:
        q = ("SELECT id, discord_id, discord_name, initiated_by, affirmation, "
             "reason, created_at, created_at_local FROM reset_consent_log")
        if discord_id:
            rows = conn.execute(q + " WHERE discord_id=? ORDER BY id", (discord_id,)).fetchall()
        else:
            rows = conn.execute(q + " ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def reset_member_history(discord_id: str, *, initiated_by: str,
                         consent_text: str = "", affirmation: str = "",
                         reason: str = "") -> Optional[dict]:
    """Wipe a student's learning history (fresh start), KEEPING their account.

    Records consent + a full snapshot FIRST (so proof and restore exist even
    if the deletion is interrupted), then deletes the history tables and
    resets the member's progress counters + calendar anchor. NEVER touches
    reset_consent_log. Returns {consent_id, deleted:{table:rows}} or None if
    the member is unknown."""
    member = get_member(discord_id)
    if not member:
        return None
    snapshot = snapshot_member_data(discord_id)  # BEFORE any deletion
    consent_id = log_reset_consent(
        discord_id, member.get("discord_name", ""), initiated_by,
        consent_text, affirmation, reason, snapshot,
    )
    conn = _connect()
    try:
        # We wipe ALL of this student's rows across every history table, so
        # inter-table foreign keys (e.g. assessment_recordings -> attempts)
        # would otherwise fail purely on DELETE ORDER (a parent deleted before
        # its child). Since the whole set goes, disable FK enforcement for the
        # duration — integrity holds once the loop completes. Must be set
        # before the first DML opens a transaction.
        conn.execute("PRAGMA foreign_keys=OFF")
        deleted = {}
        for t in RESET_WIPE_TABLES:
            try:
                cur = conn.execute(f"DELETE FROM {t} WHERE discord_id=?", (discord_id,))
                deleted[t] = cur.rowcount
            except sqlite3.OperationalError:
                pass  # table may not exist in an older DB — skip safely
        # Clean slate but keep the account usable: fresh calendar + default difficulty.
        conn.execute(
            "UPDATE members SET total_points=0, current_streak=0, longest_streak=0, "
            "level_started_at=datetime('now'), difficulty_level=2 WHERE discord_id=?",
            (discord_id,),
        )
        conn.commit()
        return {"consent_id": consent_id, "deleted": deleted}
    finally:
        conn.close()


def restore_member_from_consent(consent_id: int) -> Optional[dict]:
    """Reverse a reset by re-inserting the snapshot captured in a consent
    record. Makes resets recoverable. Returns {table: rows_restored} or None
    if the consent id is unknown."""
    import json as _json
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT discord_id, snapshot_json FROM reset_consent_log WHERE id=?",
            (consent_id,),
        ).fetchone()
        if not row:
            return None
        # Re-inserting a full, self-consistent snapshot: disable FK enforcement
        # so INSERT ORDER across tables can't fail (a child restored before its
        # parent). Integrity holds once every row is back. Set before the first
        # DML opens a transaction.
        conn.execute("PRAGMA foreign_keys=OFF")
        snap = _json.loads(row["snapshot_json"] or "{}")
        restored = {}
        for table, rows in snap.items():
            n = 0
            for r in rows:
                cols = list(r.keys())
                placeholders = ", ".join("?" for _ in cols)
                try:
                    conn.execute(
                        f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
                        tuple(_decode_snapshot_value(r[c]) for c in cols),
                    )
                    n += 1
                except sqlite3.OperationalError:
                    pass
            if n:
                restored[table] = n
        conn.commit()
        return restored
    finally:
        conn.close()


# ---- Owner-approval gate for student-initiated resets --------------------

PENDING_RESET_TTL_DAYS = 7


def create_pending_reset(discord_id: str, discord_name: str, consent_text: str,
                         affirmation: str, reason: str = "") -> int:
    """Record a student's consented reset request as PENDING owner approval
    (nothing is deleted yet). Supersedes any earlier still-pending request
    from the same student so the queue can't be spammed. Returns the id."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE pending_resets SET status='superseded', decided_at=datetime('now') "
            "WHERE discord_id=? AND status='pending'",
            (discord_id,),
        )
        cur = conn.execute(
            "INSERT INTO pending_resets (discord_id, discord_name, consent_text, "
            "affirmation, reason) VALUES (?, ?, ?, ?, ?)",
            (discord_id, discord_name, consent_text, affirmation, reason),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_pending_reset(request_id: int) -> Optional[dict]:
    conn = _connect()
    try:
        r = conn.execute("SELECT * FROM pending_resets WHERE id=?", (request_id,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def list_pending_resets() -> list:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM pending_resets WHERE status='pending' ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def approve_pending_reset(request_id: int, decided_by: str) -> Optional[dict]:
    """Approve a pending request → actually performs the reset (records consent
    + snapshot + wipes history). Returns a result dict, {'error':...} if not
    pending, or None if the request id is unknown."""
    req = get_pending_reset(request_id)
    if not req:
        return None
    if req["status"] != "pending":
        return {"error": "not_pending", "status": req["status"]}
    result = reset_member_history(
        req["discord_id"],
        initiated_by=f"student-approved:{decided_by}",
        consent_text=req["consent_text"],
        affirmation=f"{req['affirmation']} | approved by {decided_by}",
        reason=req["reason"] or "student self-service (approved)",
    )
    conn = _connect()
    try:
        conn.execute(
            "UPDATE pending_resets SET status='approved', decided_by=?, "
            "decided_at=datetime('now'), consent_id=? WHERE id=?",
            (decided_by, (result or {}).get("consent_id"), request_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "request_id": request_id,
        "discord_id": req["discord_id"],
        "discord_name": req["discord_name"],
        "consent_id": (result or {}).get("consent_id"),
        "deleted": (result or {}).get("deleted"),
    }


def deny_pending_reset(request_id: int, decided_by: str) -> Optional[dict]:
    """Deny a pending request — nothing is deleted. Returns a small dict,
    {'error':...} if not pending, or None if unknown."""
    req = get_pending_reset(request_id)
    if not req:
        return None
    if req["status"] != "pending":
        return {"error": "not_pending", "status": req["status"]}
    conn = _connect()
    try:
        conn.execute(
            "UPDATE pending_resets SET status='denied', decided_by=?, "
            "decided_at=datetime('now') WHERE id=?",
            (decided_by, request_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"request_id": request_id, "discord_id": req["discord_id"],
            "discord_name": req["discord_name"]}


def expire_old_pending_resets(ttl_days: int = PENDING_RESET_TTL_DAYS) -> int:
    """Mark still-pending requests older than ttl_days as expired. Returns
    how many were expired."""
    conn = _connect()
    try:
        cur = conn.execute(
            "UPDATE pending_resets SET status='expired', decided_at=datetime('now') "
            "WHERE status='pending' AND requested_at < datetime('now', ?)",
            (f"-{int(ttl_days)} days",),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# ============================================================
#  MEMBER OPERATIONS
# ============================================================

def register_member(discord_id: str, name: str, level: str = "A1",
                    track: str = "Core", goal: str = "",
                    telegram_id: str = "") -> bool:
    """Register a new member. Returns True if newly created, False if exists.

    Mi'yar: new students start on the first CEFR level (A1). The legacy L0–L3
    keys still resolve everywhere via config.level_info()/cefr_key(), so any
    pre-migration row keeps working.
    """
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
    """Update a member's level (after passing advancement exam).

    Darb Phase 6: also stamps level_started_at = now, so the personal
    calendar and week number restart at Week 1 Day 1 of the NEW level
    (instead of the anchor staying on the original bot-join date, which
    would make the L1 calendar think the student is already 8 weeks deep
    and show most of L1 as 'missed')."""
    update_member(discord_id, level=new_level,
                  level_started_at=datetime.datetime.now().isoformat())


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
#  CONSUMED PROOF MESSAGES (Hisn D028 — prevents one recording from
#  satisfying multiple audio-based task types)
# ============================================================

def is_message_consumed(message_id: str) -> bool:
    """Check whether a specific Discord message has already been used
    as proof-of-work for ANY task (not just the one being checked now)."""
    conn = _connect()
    row = conn.execute(
        "SELECT 1 FROM consumed_proof_messages WHERE message_id=?",
        (str(message_id),),
    ).fetchone()
    conn.close()
    return row is not None


def consume_proof_message(message_id: str, discord_id: str, task_id: str) -> bool:
    """Mark a specific message as consumed for a task. Returns True if
    newly consumed, False if it was already consumed (race-safe via the
    message_id PRIMARY KEY -- a second concurrent attempt to consume the
    same message_id will hit the same IntegrityError path log_submission
    already relies on elsewhere in this file)."""
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO consumed_proof_messages (message_id, discord_id, task_id)
               VALUES (?, ?, ?)""",
            (str(message_id), discord_id, task_id),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


# ============================================================
#  DAILY SUBMISSIONS
# ============================================================

def log_submission(discord_id: str, date: str, task_id: str,
                   content: str = "", score: float = None,
                   feedback: str = "") -> bool:
    """Log a task submission. Returns True if new, False if already exists.

    Stamps the member's CURRENT level on the row, which is by definition the
    level the work was done at. `practice_completions` uses it to attribute
    Discord-only tasks (writing/community) to the right level instead of to
    whichever level happens to be queried.

    The lookup is best-effort: submissions are a hot path and must never fail
    because a level could not be read, so on any error the row is still written
    with level NULL and the bridge falls back to its previous behaviour.
    """
    level = None
    try:
        member = get_member(discord_id)
        if member and member.get("level"):
            level = config.cefr_key(member["level"])
    except Exception:  # noqa: BLE001 - never block a submission on this
        level = None

    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO daily_submissions (discord_id, date, task_id, content, score, feedback, level)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (discord_id, date, task_id, content, score, feedback, level),
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
    cutoff = (_today_local() - datetime.timedelta(days=days - 1)).isoformat()
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
    today = _today_local().isoformat()
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

    # Map date -> tasks_completed for a day-by-day backward walk.
    by_date = {row["date"]: row["tasks_completed"] for row in rows}

    # Maintenance days to BRIDGE: a day the platform was under maintenance
    # must never break a student's streak (R5.1). Read the setting directly
    # to avoid a circular import with the maintenance module.
    import json
    try:
        maint_days = set(json.loads(get_setting("maintenance_days", "[]")))
    except Exception:
        maint_days = set()

    streak = 0
    d = _today_local()
    # Walk backward day-by-day (bounded so it always terminates). This
    # reproduces the original consecutive-days logic exactly for normal
    # days, and additionally forgives maintenance days.
    for _ in range(800):
        ds = d.isoformat()
        tasks = by_date.get(ds, 0)
        if tasks and tasks > 0:
            streak += 1
            d -= datetime.timedelta(days=1)
            continue
        # No activity on this day.
        if ds in maint_days:
            # Maintenance day — bridge it: don't break, don't count it.
            d -= datetime.timedelta(days=1)
            continue
        # Genuine miss (or today not practiced yet) — the streak stops here.
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
#  ITQAN (weekly assessment) — owner-tunable config
# ============================================================
#
# Thresholds/config live in `settings` so the owner can tune them without a
# redeploy. Defaults per design §2; a missing/blank setting falls back to the
# default, and a bad value is ignored (falls back) so config can never crash
# the assessment engine.

ITQAN_CONFIG_DEFAULTS = {
    "itqan_mastery_pass_pct": 70,        # int: mastery score needed to pass
    "itqan_consistency_pass_pct": 70,    # int: daily-work score needed to pass
    "itqan_distinction_pct": 90,         # int: mastery score for a ⭐ Distinction
    "itqan_retake_cooldown_min": 720,    # int: minutes to wait before a retake
    "itqan_spiral_recent_weight": 0.65,  # float: share of items from the newest week
    "itqan_time_limit_min": 15,          # int: overall time limit
}


def get_itqan_config() -> dict:
    """Return the Itqan config, reading `settings` overrides over the defaults.
    Never raises: blank/invalid values fall back to the default."""
    cfg = {}
    for key, default in ITQAN_CONFIG_DEFAULTS.items():
        raw = get_setting(key, "")
        if raw == "":
            cfg[key] = default
            continue
        try:
            cfg[key] = type(default)(raw)
        except (ValueError, TypeError):
            cfg[key] = default
    return cfg


def set_itqan_config(key: str, value) -> bool:
    """Set one Itqan config value (owner tuning). Returns False for unknown
    keys so callers can reject typos rather than write junk settings."""
    if key not in ITQAN_CONFIG_DEFAULTS:
        return False
    set_setting(key, str(value))
    return True


# ============================================================
#  COMMUNITY LOUNGE ("MAJLIS") CONFIG
# ============================================================

# All tunables for the Majlis community-lounge feature (Phases 0–7).
# Stored in `settings`; a missing/blank value falls back to the default.
# Owner tunes via /majlis config (Phase 7); nothing crashes on bad values.
COMMUNITY_CONFIG_DEFAULTS = {
    "community_together_minutes": 5,          # int: min together-time for fast #7 path
    "community_lounge_capacity": 6,           # int: hard cap per Majlis lounge
    "community_beacon_max_occupancy": 4,      # int: beacon only when occupancy ≤ this
    "community_beacon_cooldown_min": 40,      # int: min minutes between beacons per lounge
    "community_beacon_ttl_min": 20,           # int: auto-expire a beacon after this
    "community_reap_grace_min": 3,            # int: empty dynamic lounge grace before delete
    "community_hour_start": "21:00",          # str: start time (in community_hour_tz)
    "community_hour_tz": "Africa/Cairo",      # str: Egypt time — students are Egyptian
    "community_hour_days": "0,1,2,3,4,5,6",  # str: comma-sep weekday ints (Mon=0…Sun=6)
    "community_hour_minutes": 60,             # int: window length
    "community_together_reward_points": 0,    # int: optional bonus (0 = off)
}


def get_community_config() -> dict:
    """Return the Majlis community config, reading `settings` overrides over
    the defaults. Never raises: blank/invalid values fall back to the default."""
    cfg = {}
    for key, default in COMMUNITY_CONFIG_DEFAULTS.items():
        raw = get_setting(key, "")
        if raw == "":
            cfg[key] = default
            continue
        try:
            cfg[key] = type(default)(raw)
        except (ValueError, TypeError):
            cfg[key] = default
    return cfg


def set_community_config(key: str, value) -> bool:
    """Set one Majlis config value (owner tuning). Returns False for unknown
    keys so callers can reject typos rather than write junk settings."""
    if key not in COMMUNITY_CONFIG_DEFAULTS:
        return False
    set_setting(key, str(value))
    return True


# ============================================================
#  ASSESSMENT PROGRESSION ("TAQDEEM") CONFIG
# ============================================================

PROGRESSION_CONFIG_DEFAULTS = {
    "progression_monthly_pass_pct": 65,              # int: retention score to pass monthly
    "progression_monthly_retake_cooldown_hours": 72, # int: hours before monthly retake
    "progression_monthly_weeks_per_review": 4,       # int: weekly passes that trigger a review
    "progression_advancement_pass_pct": 75,          # int: overall % to pass advancement
    "progression_advancement_skill_min_pct": 60,     # int: minimum per-skill % in Part A
    "progression_advancement_part_b_min_pct": 50,    # int: minimum Part B score %
    "progression_advancement_part_a_weight": 0.6,    # float: Part A weight in overall
    "progression_advancement_part_b_weight": 0.4,    # float: Part B weight in overall
    "progression_advancement_retake_cooldown_days": 7,  # int: days before advancement retake
    "progression_advancement_time_limit_part_a_min": 20, # int: Part A time limit
    "progression_advancement_time_limit_part_b_min": 10, # int: Part B time limit
}


def get_progression_config() -> dict:
    """Return the Taqdeem progression config, reading settings overrides over
    defaults. Never raises: blank/invalid values fall back to the default."""
    cfg = {}
    for key, default in PROGRESSION_CONFIG_DEFAULTS.items():
        raw = get_setting(key, "")
        if raw == "":
            cfg[key] = default
            continue
        try:
            cfg[key] = type(default)(raw)
        except (ValueError, TypeError):
            cfg[key] = default
    return cfg


def set_progression_config(key: str, value) -> bool:
    """Set one Taqdeem config value (owner tuning). Returns False for unknown keys."""
    if key not in PROGRESSION_CONFIG_DEFAULTS:
        return False
    set_setting(key, str(value))
    return True


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


def sync_flag_registry():
    """Auto-register all flags from flag_registry.py into the database.

    Called on every bot startup. For each flag in the registry:
    - If it doesn't exist in the DB → create it with its default_enabled value
    - If it already exists → DON'T touch it (preserve manual enable/disable state)

    This ensures !flag list always shows ALL flags, and new flags added to
    the registry appear automatically on next restart without manual !flag enable.
    """
    from . import flag_registry
    conn = _connect()
    existing = {row["name"] for row in conn.execute("SELECT name FROM feature_flags").fetchall()}

    added = 0
    for name, description, initiative, default_enabled in flag_registry.REGISTRY:
        if name not in existing:
            conn.execute(
                """INSERT INTO feature_flags (name, enabled, allowed_ids, updated_at, updated_by)
                   VALUES (?, ?, '', datetime('now'), 'auto_sync')""",
                (name, 1 if default_enabled else 0),
            )
            added += 1

    if added:
        conn.commit()
    conn.close()
    return added


def enable_exit_exam_once() -> bool:
    """One-time, idempotent activation of the CEFR exit exam
    (`assessment_advancement_exam`) on deploy — per the owner's 2026-08-25
    decision to "turn on and make everything live."

    Runs exactly once, guarded by a settings marker, so that a later deliberate
    `!flag disable assessment_advancement_exam` is NOT silently undone on the
    next restart. Returns True only on the run that actually flips it on."""
    if get_setting("exit_exam_autoenabled_v1", "") == "1":
        return False
    set_feature_flag("assessment_advancement_exam", enabled=True,
                     updated_by="phase8_autoenable")
    set_setting("exit_exam_autoenabled_v1", "1")
    return True


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


def feature_flag_status(name: str) -> dict:
    """Current state of a flag: {enabled, allowed_ids (set), everyone}.
    `everyone` is True when enabled with an empty allowlist (on for all)."""
    conn = _connect()
    row = conn.execute("SELECT enabled, allowed_ids FROM feature_flags WHERE name=?",
                       (name,)).fetchone()
    conn.close()
    enabled = bool(row and row["enabled"])
    allowed = {a.strip() for a in ((row["allowed_ids"] if row else "") or "").split(",") if a.strip()}
    return {"enabled": enabled, "allowed_ids": allowed, "everyone": enabled and not allowed}


def feature_flag_grant(name: str, discord_id: str, updated_by: str = "") -> str:
    """Give ONE student access to a flag (WHO control). Enables the flag and
    adds them to the allowlist. Returns:
      - 'everyone'  → flag is already on for all; no change (they already have it)
      - 'already'   → already in the allowlist
      - 'granted'   → added
    """
    st = feature_flag_status(name)
    did = str(discord_id)
    if st["everyone"]:
        return "everyone"
    if did in st["allowed_ids"]:
        return "already"
    ids = set(st["allowed_ids"]); ids.add(did)
    set_feature_flag(name, True, ",".join(sorted(ids)), updated_by)
    return "granted"


def feature_flag_revoke(name: str, discord_id: str, updated_by: str = "") -> str:
    """Remove ONE student's access (WHO control). Returns:
      - 'everyone'         → flag is on for ALL; can't remove just one (caller warns)
      - 'not_present'      → they weren't on the allowlist
      - 'revoked'          → removed; others remain
      - 'revoked_now_off'  → removed the last student → flag turned OFF (fail-safe:
                             removing the last person never silently opens it to all)
    """
    st = feature_flag_status(name)
    did = str(discord_id)
    if st["everyone"]:
        return "everyone"
    if did not in st["allowed_ids"]:
        return "not_present"
    ids = set(st["allowed_ids"]); ids.discard(did)
    if ids:
        set_feature_flag(name, True, ",".join(sorted(ids)), updated_by)
        return "revoked"
    set_feature_flag(name, False, "", updated_by)
    return "revoked_now_off"


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
    return total_submissions_on_date(_today_local().isoformat())


def total_submissions_on_date(date_str: str) -> int:
    """Count all submissions across all members on a specific date
    (YYYY-MM-DD). Generalized from total_submissions_today() for the
    Markaz daily digest (Phase M1), which reports on *yesterday*."""
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM daily_submissions WHERE date=?", (date_str,)
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def count_active_members_on(date_str: str) -> int:
    """Count distinct members who submitted at least one task on a
    specific date (YYYY-MM-DD). Used by the Markaz daily digest to
    report "active students yesterday"."""
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(DISTINCT discord_id) as cnt FROM daily_submissions WHERE date=?",
        (date_str,),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def count_new_members_on(date_str: str) -> int:
    """Count members who registered (joined_at) on a specific date
    (YYYY-MM-DD). Used by the Markaz daily digest."""
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM members WHERE date(joined_at)=?", (date_str,)
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def streak_milestones_on(date_str: str) -> list[dict]:
    """Get streak-bonus milestones hit on a specific date (YYYY-MM-DD),
    by reading the points_log rows written by tasks.py's streak-bonus
    logic (reason='streak_<N>'). Returns [{"discord_name": ..., "days": N}].
    Used by the Markaz daily digest."""
    conn = _connect()
    rows = conn.execute(
        """SELECT p.reason, m.discord_name FROM points_log p
           JOIN members m ON m.discord_id = p.discord_id
           WHERE date(p.logged_at)=? AND p.reason LIKE 'streak_%'""",
        (date_str,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        try:
            days = int(r["reason"].split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        name = (r["discord_name"] or "").split("#")[0]
        result.append({"discord_name": name, "days": days})
    return result


def count_nour_conversations_on(date_str: str) -> int:
    """Count distinct students who exchanged at least one message with
    Nour on a specific date (YYYY-MM-DD). Used by the Markaz daily digest."""
    conn = _connect()
    row = conn.execute(
        """SELECT COUNT(DISTINCT discord_id) as cnt FROM nour_conversations
           WHERE role='student' AND date(created_at)=?""",
        (date_str,),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_recent_conversation(discord_id: str, limit: int = 5) -> list[dict]:
    """Get the last N Nour conversation messages for a student, oldest
    first. Used by narrative_engine (growth-letter conversation-theme
    signals) to read recent history from nour_conversations."""
    conn = _connect()
    rows = conn.execute(
        """SELECT role, message, created_at FROM nour_conversations
           WHERE discord_id=? ORDER BY created_at DESC LIMIT ?""",
        (discord_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


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


def add_voice_minutes(discord_id: str, minutes: float, date: str = None) -> None:
    """Enhancement E5: persistently add voice-lounge minutes for a day
    (upsert). Survives bot restarts so the community task's 10-min
    requirement isn't wiped when the process bounces."""
    if minutes <= 0:
        return
    if date is None:
        date = _today_local().isoformat()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO voice_minutes (discord_id, date, minutes) VALUES (?, ?, ?) "
            "ON CONFLICT(discord_id, date) DO UPDATE SET minutes = minutes + excluded.minutes",
            (discord_id, date, minutes),
        )
        conn.commit()
    finally:
        conn.close()


def get_voice_minutes(discord_id: str, date: str = None) -> float:
    """Persistent voice minutes for a student on a given day (default today)."""
    if date is None:
        date = _today_local().isoformat()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT minutes FROM voice_minutes WHERE discord_id=? AND date=?",
            (discord_id, date),
        ).fetchone()
        return row["minutes"] if row else 0.0
    finally:
        conn.close()


# ============================================================
#  TOGETHER-MINUTES (Majlis Phase 0)
# ============================================================

def add_together_minutes(discord_id: str, minutes: float, date: str = None) -> None:
    """Majlis Phase 0: persistently add together-time minutes for a day
    (upsert). Together-time = minutes spent in a Majlis lounge WITH at least
    one other member present. Same semantics as add_voice_minutes."""
    if minutes <= 0:
        return
    if date is None:
        date = _today_local().isoformat()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO together_minutes (discord_id, date, minutes) VALUES (?, ?, ?) "
            "ON CONFLICT(discord_id, date) DO UPDATE SET minutes = minutes + excluded.minutes",
            (discord_id, date, minutes),
        )
        conn.commit()
    finally:
        conn.close()


def get_together_minutes(discord_id: str, date: str = None) -> float:
    """Persistent together-minutes for a student on a given day (default today)."""
    if date is None:
        date = _today_local().isoformat()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT minutes FROM together_minutes WHERE discord_id=? AND date=?",
            (discord_id, date),
        ).fetchone()
        return row["minutes"] if row else 0.0
    finally:
        conn.close()


def level_anchor_iso(member: dict) -> str:
    """Darb Phase 6: the date the student's CURRENT level began, as an ISO
    string. Falls back to joined_at when level_started_at is unset (every
    student who has never been promoted), so behaviour is identical to
    before for them. Single source of truth for both the personal
    calendar (darb.py) and the week number below, so they never diverge."""
    return (member.get("level_started_at") or member.get("joined_at") or
            datetime.datetime.now().isoformat())


def member_week_number(discord_id: str) -> int:
    """Calculate which week a member is in (from their current level's
    start — Darb Phase 6). Falls back to join date for un-promoted
    students, so this is unchanged for everyone today."""
    member = get_member(discord_id)
    if not member:
        return 1
    anchor = datetime.datetime.fromisoformat(level_anchor_iso(member))
    days = (datetime.datetime.now() - anchor).days
    return max(1, (days // 7) + 1)



# ============================================================
#  NOTIFICATIONS (Nabd Phase N0 — preferences + logging)
# ============================================================

def get_notification_prefs(discord_id: str) -> dict:
    """Get a member's notification preferences, or defaults if never set."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM notification_preferences WHERE discord_id=?",
        (discord_id,),
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    # Return defaults (matching the CREATE TABLE defaults)
    return {
        "discord_id": discord_id,
        "morning_dm": 1,
        "evening_dm": 1,
        "streak_alert": 1,
        "celebrations": 1,
        "social_proof": 0,
        "weekly_summary": 1,
        "quiet_start": "23:00",
        "quiet_end": "05:00",
    }


def set_notification_pref(discord_id: str, key: str, value) -> bool:
    """Set a single notification preference. Returns True if successful.

    Valid keys: morning_dm, evening_dm, streak_alert, celebrations,
    social_proof, weekly_summary, quiet_start, quiet_end.
    """
    valid_keys = {
        "morning_dm", "evening_dm", "streak_alert", "celebrations",
        "social_proof", "weekly_summary", "quiet_start", "quiet_end",
    }
    if key not in valid_keys:
        return False
    conn = _connect()
    # Upsert the preferences row
    conn.execute(
        """INSERT INTO notification_preferences (discord_id, {key})
           VALUES (?, ?)
           ON CONFLICT(discord_id) DO UPDATE SET {key}=excluded.{key}, updated_at=datetime('now')""".format(key=key),
        (discord_id, value),
    )
    conn.commit()
    conn.close()
    return True


def log_notification(discord_id: str, notification_type: str, date: str):
    """Record that a notification was sent (for duplicate prevention).

    Wrapped in try/except for the FK constraint — if somehow called for
    a discord_id not in the members table (shouldn't happen in normal
    flow since notification loops iterate all_active_members() first),
    it silently skips rather than crashing the notification loop.
    """
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO notification_log (discord_id, notification_type, date) VALUES (?, ?, ?)",
            (discord_id, notification_type, date),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # FK constraint — member doesn't exist, skip silently
    finally:
        conn.close()


def was_notification_sent(discord_id: str, notification_type: str, date: str) -> bool:
    """Check if a specific notification type was already sent to this
    member for this date. Used to prevent double-sends."""
    conn = _connect()
    row = conn.execute(
        "SELECT 1 FROM notification_log WHERE discord_id=? AND notification_type=? AND date=?",
        (discord_id, notification_type, date),
    ).fetchone()
    conn.close()
    return row is not None


def was_notification_sent_within(discord_id: str, notification_type: str, days: int) -> bool:
    """Masar M4 (R5): check if a notification of this type was sent to
    this member at any point in the last `days` days (not just an
    exact-date match, unlike `was_notification_sent()` above) — used
    for throttling notification TYPES that can legitimately recur
    (e.g. `difficulty_change`, which can fire more than once a week if
    the adaptive engine adjusts again), as opposed to once-per-day
    dedup. Reuses the existing `notification_log` table/index, no new
    table needed, same pattern as every other notification type in
    this codebase.
    """
    cutoff = (_today_local() - datetime.timedelta(days=days)).isoformat()
    conn = _connect()
    row = conn.execute(
        "SELECT 1 FROM notification_log WHERE discord_id=? AND notification_type=? AND date>=? LIMIT 1",
        (discord_id, notification_type, cutoff),
    ).fetchone()
    conn.close()
    return row is not None


def is_quiet_hours(discord_id: str) -> bool:
    """Check if the current time is within this member's quiet hours.

    Uses config.TIMEZONE for the current time (all students are in the
    same region for now). Quiet hours wrap around midnight: e.g.
    quiet_start=23:00, quiet_end=05:00 means 11 PM to 5 AM is quiet.
    """
    prefs = get_notification_prefs(discord_id)
    quiet_start = prefs.get("quiet_start", "23:00")
    quiet_end = prefs.get("quiet_end", "05:00")

    try:
        from zoneinfo import ZoneInfo
        now = datetime.datetime.now(ZoneInfo(config.TIMEZONE)).time()
    except Exception:
        now = datetime.datetime.now().time()

    start = datetime.time.fromisoformat(quiet_start)
    end = datetime.time.fromisoformat(quiet_end)

    # Handle wrap-around midnight (e.g. 23:00 to 05:00)
    if start <= end:
        return start <= now <= end
    else:
        return now >= start or now <= end



# ============================================================
#  SPACED REPETITION (Tatawwur Phase T2)
# ============================================================

def add_word_to_srs(discord_id: str, word: str, next_review: str = None):
    """Add a word to the SRS queue (idempotent — skips if it already exists).
    If `next_review` (YYYY-MM-DD) is given it overrides the table default
    (+1 day), so already-studied words backfilled into review can be made due
    immediately."""
    conn = _connect()
    try:
        if next_review:
            conn.execute(
                "INSERT INTO vocab_srs (discord_id, word, next_review) VALUES (?, ?, ?)",
                (discord_id, word, next_review),
            )
        else:
            conn.execute(
                "INSERT INTO vocab_srs (discord_id, word) VALUES (?, ?)",
                (discord_id, word),
            )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # already in SRS
    finally:
        conn.close()


def enroll_day_vocab_in_srs(discord_id: str, level: str, week: int, day: int,
                            next_review: str = None) -> int:
    """Enroll the vocabulary words a student studied on a content-day
    (level/week/day) into their SRS "Review Past Words" queue.

    `day` is 1-7; the curriculum split uses a 0-based index and matches the
    practice page's vocab EXACTLY (get_vocabulary_for_day == the same
    vocab[(day-1)*n : day*n] slice generate.py bakes into the page). Idempotent
    — returns the number of words enrolled."""
    from . import curriculum
    try:
        words = curriculum.get_vocabulary_for_day(week, day - 1, level)
    except Exception:
        return 0
    n = 0
    for w in words:
        term = (w.get("word") if isinstance(w, dict) else str(w)) or ""
        term = term.strip()
        if term:
            add_word_to_srs(discord_id, term, next_review=next_review)
            n += 1
    return n


def backfill_srs_recent_vocab(discord_id: str, lookback_days: int = 7) -> int:
    """One-time catch-up: enroll vocab from days the student ALREADY completed
    within the last `lookback_days` into their SRS queue, so 'Review Past
    Words' isn't empty for students who studied before enrollment was wired.
    Those words are made due TODAY (learned days ago → genuinely ready to
    review). Idempotent. Returns words enrolled (attempted)."""
    member = get_member(discord_id)
    if not member:
        return 0
    level = member.get("level", "A1")
    cutoff = (_today_local() - datetime.timedelta(days=lookback_days)).isoformat()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT DISTINCT week, day FROM practice_mastery "
            "WHERE discord_id=? AND exercise='vocab' AND last_completed_date>=?",
            (discord_id, cutoff),
        ).fetchall()
    finally:
        conn.close()
    due_today = _today_local().isoformat()
    total = 0
    for r in rows:
        total += enroll_day_vocab_in_srs(discord_id, level, r["week"], r["day"],
                                         next_review=due_today)
    return total


def get_due_reviews(discord_id: str, limit: int = 3) -> list[dict]:
    """Get words due for review today (next_review <= today)."""
    today = _today_local().isoformat()
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM vocab_srs WHERE discord_id=? AND next_review<=? ORDER BY next_review ASC LIMIT ?",
        (discord_id, today, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def record_review_result(discord_id: str, word: str, quality: int):
    """Record a review result using SM-2 algorithm.

    quality: 0-5 (0-2 = forgot, 3 = hard, 4 = good, 5 = easy)
    """
    conn = _connect()
    row = conn.execute(
        "SELECT ease_factor, interval_days, review_count FROM vocab_srs WHERE discord_id=? AND word=?",
        (discord_id, word),
    ).fetchone()
    if not row:
        conn.close()
        return

    ef = row["ease_factor"]
    interval = row["interval_days"]
    count = row["review_count"]

    # SM-2 algorithm
    if quality < 3:
        # Failed — reset interval
        interval = 1
    else:
        if count == 0:
            interval = 1
        elif count == 1:
            interval = 6
        else:
            interval = int(interval * ef)
        # Update ease factor
        ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ef = max(1.3, ef)

    next_review = (_today_local() + datetime.timedelta(days=interval)).isoformat()

    conn.execute(
        """UPDATE vocab_srs SET ease_factor=?, interval_days=?, next_review=?,
           review_count=?, last_score=? WHERE discord_id=? AND word=?""",
        (ef, interval, next_review, count + 1, quality, discord_id, word),
    )
    conn.commit()
    conn.close()


def get_srs_stats(discord_id: str) -> dict:
    """Get vocab SRS statistics for a member."""
    today = _today_local().isoformat()
    conn = _connect()
    total = conn.execute("SELECT COUNT(*) as c FROM vocab_srs WHERE discord_id=?", (discord_id,)).fetchone()["c"]
    due = conn.execute("SELECT COUNT(*) as c FROM vocab_srs WHERE discord_id=? AND next_review<=?", (discord_id, today)).fetchone()["c"]
    mastered = conn.execute("SELECT COUNT(*) as c FROM vocab_srs WHERE discord_id=? AND interval_days>=30", (discord_id,)).fetchone()["c"]
    conn.close()
    return {"total": total, "due_today": due, "mastered": mastered, "learning": total - mastered}


# ============================================================
#  LINK TOKENS (Sahel S6 — practice platform connection)
# ============================================================

def create_link_token(discord_id: str) -> str:
    """Generate a unique token for a member to connect the practice platform.
    If the member already has a token, returns the existing one."""
    import secrets
    conn = _connect()
    # Check if token already exists
    existing = conn.execute(
        "SELECT token FROM link_tokens WHERE discord_id=?", (discord_id,)
    ).fetchone()
    if existing:
        conn.close()
        return existing["token"]
    # Generate new token
    token = secrets.token_urlsafe(16)  # 22 chars, URL-safe
    conn.execute(
        "INSERT INTO link_tokens (token, discord_id) VALUES (?, ?)",
        (token, discord_id),
    )
    conn.commit()
    conn.close()
    return token


def get_member_by_token(token: str) -> dict | None:
    """Look up a member by their link token. Returns member dict or None."""
    conn = _connect()
    row = conn.execute(
        "SELECT m.* FROM members m JOIN link_tokens lt ON m.discord_id = lt.discord_id WHERE lt.token=?",
        (token,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_progress_for_token(token: str) -> dict | None:
    """Get progress data for the practice platform given a legacy link token."""
    member = get_member_by_token(token)
    if not member:
        return None
    return get_progress_for_discord_id(member["discord_id"])


def get_progress_for_discord_id(discord_id: str) -> dict | None:
    """Practice-platform progress for a student by discord_id. Shared by the
    legacy link-token path (get_progress_for_token) and the Darb-session path
    (api_server.get_progress), so both return an identical payload."""
    member = get_member(discord_id)
    if not member:
        return None

    today = _today_local().isoformat()

    # Get today's completed tasks
    tasks_today = tasks_completed_today(discord_id)

    # Get SRS due count
    conn = _connect()
    srs_due = conn.execute(
        "SELECT COUNT(*) as cnt FROM vocab_srs WHERE discord_id=? AND next_review<=?",
        (discord_id, today),
    ).fetchone()
    srs_due_count = srs_due["cnt"] if srs_due else 0

    # Get due words for review
    srs_words = conn.execute(
        "SELECT word, ease_factor, interval_days, review_count FROM vocab_srs WHERE discord_id=? AND next_review<=? LIMIT 20",
        (discord_id, today),
    ).fetchall()
    conn.close()

    return {
        "discord_id": discord_id,
        "discord_name": member.get("discord_name", ""),
        "level": member.get("level", "A1"),
        # Hisn D029: the practice platform's homepage (level/week/day
        # picker) had ZERO awareness of a connected student's real
        # progress -- it always defaulted to Level 0/Week 1 regardless
        # of who was actually connected, even though Discord itself
        # (e.g. !week) correctly knew the student's real current week.
        # Confirmed live during Hisn H6: the owner was on real Week 3
        # in Discord but the homepage picker started at Week 1. Adding
        # `week` here (previously only `level` was exposed) lets the
        # frontend (app.js's ConnectedProgress) auto-select the
        # student's real level+week once connected, instead of always
        # defaulting to L0/Week 1 for every visitor.
        "week": member_week_number(discord_id),
        "streak": member.get("current_streak", 0),
        "longest_streak": member.get("longest_streak", 0),
        "total_points": member.get("total_points", 0),
        "tasks_today": tasks_today,
        "tasks_today_count": len(tasks_today),
        "srs_due": srs_due_count,
        "srs_words": [dict(r) for r in srs_words],
        "pronunciation": _get_pronunciation_stats(discord_id),
    }


def get_srs_review_data(discord_id: str) -> dict:
    """Darb: SRS review payload (due words + streak) for the Vocab Review
    page, keyed by discord_id (Darb-session authed — NOT the legacy link
    token). Mirrors the SRS slice of get_progress_for_token."""
    member = get_member(discord_id)
    if not member:
        return {"streak": 0, "srs_due": 0, "srs_words": []}
    today = _today_local().isoformat()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM vocab_srs WHERE discord_id=? AND next_review<=?",
            (discord_id, today),
        ).fetchone()
        srs_due_count = row["cnt"] if row else 0
        srs_words = conn.execute(
            "SELECT word, ease_factor, interval_days, review_count FROM vocab_srs "
            "WHERE discord_id=? AND next_review<=? LIMIT 20",
            (discord_id, today),
        ).fetchall()
    finally:
        conn.close()
    return {
        "streak": member.get("current_streak", 0),
        "srs_due": srs_due_count,
        "srs_words": [dict(r) for r in srs_words],
    }


def _get_pronunciation_stats(discord_id: str) -> dict:
    """Get pronunciation scoring stats for the API response (Dhaka' P2)."""
    scores = get_recent_scores(discord_id, days=7)
    if not scores:
        return {"last_score": None, "average_7d": None, "trend": "no_data", "total_scored": 0}

    last_score = scores[0]["score"]
    avg = sum(s["score"] for s in scores) / len(scores)

    # Trend: compare first half vs second half
    if len(scores) >= 4:
        recent_half = scores[:len(scores) // 2]
        older_half = scores[len(scores) // 2:]
        recent_avg = sum(s["score"] for s in recent_half) / len(recent_half)
        older_avg = sum(s["score"] for s in older_half) / len(older_half)
        diff = recent_avg - older_avg
        trend = "improving" if diff > 5 else "declining" if diff < -5 else "stable"
    else:
        trend = "stable"

    return {
        "last_score": round(last_score, 1),
        "average_7d": round(avg, 1),
        "trend": trend,
        "total_scored": len(scores),
    }


def record_srs_review(discord_id: str, word: str, score: int):
    """Record an SRS review result. Score: 0-5 (SM-2 scale).
    Updates ease_factor, interval, and next_review date."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM vocab_srs WHERE discord_id=? AND word=?",
        (discord_id, word),
    ).fetchone()
    if not row:
        conn.close()
        return

    ease = row["ease_factor"]
    interval = row["interval_days"]
    count = row["review_count"]

    # SM-2 algorithm
    if score >= 3:
        if count == 0:
            interval = 1
        elif count == 1:
            interval = 6
        else:
            interval = int(interval * ease)
        count += 1
    else:
        count = 0
        interval = 1

    ease = ease + (0.1 - (5 - score) * (0.08 + (5 - score) * 0.02))
    if ease < 1.3:
        ease = 1.3

    next_review = (_today_local() + datetime.timedelta(days=interval)).isoformat()

    conn.execute(
        """UPDATE vocab_srs SET ease_factor=?, interval_days=?, next_review=?,
           review_count=?, last_score=? WHERE discord_id=? AND word=?""",
        (ease, interval, next_review, count, score, discord_id, word),
    )
    conn.commit()
    conn.close()



# ============================================================
#  PRONUNCIATION SCORES (Dhaka' P0)
# ============================================================

def store_pronunciation_score(discord_id: str, date: str, task_id: str,
                              score: float, expected_text: str, transcript: str,
                              missed_words: str = "", feedback: str = "",
                              audio_url: str = ""):
    """Store a pronunciation scoring result."""
    conn = _connect()
    conn.execute(
        """INSERT INTO pronunciation_scores
           (discord_id, date, task_id, score, expected_text, transcript,
            missed_words, feedback, audio_url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (discord_id, date, task_id, score, expected_text, transcript,
         missed_words, feedback, audio_url),
    )
    conn.commit()
    conn.close()


def azure_usage_seconds(month: str) -> float:
    """Total Azure audio-seconds used in a month (for the usage guard)."""
    conn = _connect()
    row = conn.execute("SELECT audio_seconds FROM azure_usage WHERE month=?", (month,)).fetchone()
    conn.close()
    return float(row["audio_seconds"]) if row else 0.0


def add_azure_usage(month: str, seconds: float) -> None:
    """Add audio-seconds to a month's Azure usage total (upsert)."""
    conn = _connect()
    conn.execute(
        """INSERT INTO azure_usage (month, audio_seconds) VALUES (?, ?)
           ON CONFLICT(month) DO UPDATE SET audio_seconds = audio_seconds + excluded.audio_seconds""",
        (month, max(0.0, float(seconds))),
    )
    conn.commit()
    conn.close()


def azure_calls_today(discord_id: str, date: str) -> int:
    """How many Azure shadow scorings this student has had today (cost policy)."""
    conn = _connect()
    row = conn.execute(
        "SELECT count FROM azure_shadow_calls WHERE discord_id=? AND date=?",
        (discord_id, date)).fetchone()
    conn.close()
    return int(row["count"]) if row else 0


def incr_azure_calls_today(discord_id: str, date: str) -> None:
    """Increment today's Azure shadow-call count for a student (upsert).

    NOTE: Prefer reserve_azure_call_today() in the scoring hot path — it does
    the cap check + increment atomically. This plain increment is kept for
    back-compat / non-capped callers.
    """
    conn = _connect()
    conn.execute(
        """INSERT INTO azure_shadow_calls (discord_id, date, count) VALUES (?, ?, 1)
           ON CONFLICT(discord_id, date) DO UPDATE SET count = count + 1""",
        (discord_id, date))
    conn.commit()
    conn.close()


def reserve_azure_call_today(discord_id: str, date: str, cap: int) -> bool:
    """Atomically claim ONE Azure shadow-call slot for today, iff the student is
    still under `cap`. Returns True (and increments the counter) when a slot is
    granted, False when the daily cap is already reached.

    This replaces the old check-then-act pattern (read count, later increment)
    that let two near-simultaneous submits (double-tap "Send" / a client retry)
    both pass the cap before either incremented — the bug that pushed the
    counter to 3 while the cap was 1. The read + increment run inside a single
    BEGIN IMMEDIATE transaction, so concurrent reservations serialize and the
    strict N/day guarantee holds even under races.
    """
    if cap <= 0:
        return False
    conn = _connect()
    try:
        conn.isolation_level = None  # take manual control of the transaction
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT count FROM azure_shadow_calls WHERE discord_id=? AND date=?",
            (discord_id, date)).fetchone()
        current = int(row["count"]) if row else 0
        if current >= cap:
            conn.execute("COMMIT")
            return False
        conn.execute(
            """INSERT INTO azure_shadow_calls (discord_id, date, count) VALUES (?, ?, 1)
               ON CONFLICT(discord_id, date) DO UPDATE SET count = count + 1""",
            (discord_id, date))
        conn.execute("COMMIT")
        return True
    finally:
        conn.close()


def release_azure_call_today(discord_id: str, date: str) -> None:
    """Refund one reserved Azure slot (floor 0). Called when the Azure call
    fails AFTER a slot was reserved, so a transient error never burns the
    student's one graded read for the day — they fall back to the local engine
    and can still earn their Azure grade on a retry."""
    conn = _connect()
    conn.execute(
        "UPDATE azure_shadow_calls SET count = MAX(count - 1, 0) WHERE discord_id=? AND date=?",
        (discord_id, date))
    conn.commit()
    conn.close()


def nutq_daily_cap_override(discord_id: str):
    """The student's per-day official-grade cap override, or None if they use
    the global default. Owner-set via /nutq cap (PR3)."""
    conn = _connect()
    row = conn.execute(
        "SELECT cap FROM nutq_daily_cap_overrides WHERE discord_id=?",
        (discord_id,)).fetchone()
    conn.close()
    return int(row["cap"]) if row else None


def set_nutq_daily_cap_override(discord_id: str, cap: int) -> None:
    """Set (upsert) a student's per-day official-grade cap override."""
    conn = _connect()
    conn.execute(
        """INSERT INTO nutq_daily_cap_overrides (discord_id, cap) VALUES (?, ?)
           ON CONFLICT(discord_id) DO UPDATE SET cap = excluded.cap""",
        (discord_id, max(0, int(cap))))
    conn.commit()
    conn.close()


def clear_nutq_daily_cap_override(discord_id: str) -> None:
    """Remove a student's override → they revert to the global default cap."""
    conn = _connect()
    conn.execute("DELETE FROM nutq_daily_cap_overrides WHERE discord_id=?", (discord_id,))
    conn.commit()
    conn.close()


def get_recent_scores(discord_id: str, days: int = 7) -> list[dict]:
    """Get pronunciation scores from the last N days."""
    cutoff = (_today_local() - datetime.timedelta(days=days - 1)).isoformat()
    conn = _connect()
    rows = conn.execute(
        """SELECT * FROM pronunciation_scores
           WHERE discord_id=? AND date>=?
           ORDER BY scored_at DESC""",
        (discord_id, cutoff),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pronunciation_average(discord_id: str, days: int = 7) -> float:
    """Get average pronunciation score over last N days. Returns 0.0 if no data."""
    scores = get_recent_scores(discord_id, days)
    if not scores:
        return 0.0
    return sum(s["score"] for s in scores) / len(scores)


# ============================================================
#  MASAR M2.3: Nour's Weekly Growth Letter storage (fixes D020)
# ============================================================

def store_growth_letter(discord_id: str, letter_text: str, source: str, week: int) -> None:
    """Store a generated growth letter. Called by nour_growth_letter_task()
    once per student per week. `source` is 'ai' or 'template_fallback'
    (per narrative_engine._generate_with_fallback()'s return contract),
    stored so a future audit can see how often the fallback fired."""
    conn = _connect()
    conn.execute(
        """INSERT INTO nour_growth_letters (discord_id, letter_text, source, week)
           VALUES (?, ?, ?, ?)""",
        (discord_id, letter_text, source, week),
    )
    conn.commit()
    conn.close()


def get_latest_growth_letter(discord_id: str) -> dict | None:
    """Get the most recently generated growth letter for a student, or
    None if none exists yet. Read by GET /api/growth-letter (M2.4) --
    zero AI cost per page load."""
    conn = _connect()
    row = conn.execute(
        """SELECT letter_text, source, generated_at, week FROM nour_growth_letters
           WHERE discord_id=? ORDER BY generated_at DESC LIMIT 1""",
        (discord_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ============================================================
#  WUSLAH W0.4: TOKEN EXPIRY CLEANUP
# ============================================================

def cleanup_expired_tokens(days: int = 30) -> int:
    """Remove link tokens that haven't been used in `days` days.

    Called from a daily background task. Returns the number of tokens
    removed. Tokens that have never been used (last_used is NULL) are
    judged by their created_at date instead.
    """
    conn = _connect()
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    try:
        cur = conn.execute(
            """DELETE FROM link_tokens
               WHERE (last_used IS NOT NULL AND last_used < ?)
                  OR (last_used IS NULL AND created_at < ?)""",
            (cutoff, cutoff),
        )
        removed = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return removed



# ============================================================
#  HISSAR P4: PERSISTENT COOLDOWN (survives bot restarts)
# ============================================================

def get_last_done_time(discord_id: str) -> datetime.datetime | None:
    """Get the last !done timestamp from the persistent table."""
    conn = _connect()
    row = conn.execute(
        "SELECT last_done_at FROM done_cooldowns WHERE discord_id=?",
        (discord_id,),
    ).fetchone()
    conn.close()
    if row and row["last_done_at"]:
        try:
            return datetime.datetime.fromisoformat(row["last_done_at"])
        except (ValueError, TypeError):
            return None
    return None


def record_last_done_time(discord_id: str) -> None:
    """Persist the current timestamp as the student's last !done time."""
    conn = _connect()
    conn.execute(
        """INSERT INTO done_cooldowns (discord_id, last_done_at)
           VALUES (?, datetime('now'))
           ON CONFLICT(discord_id) DO UPDATE SET last_done_at=datetime('now')""",
        (discord_id,),
    )
    conn.commit()
    conn.close()


# ============================================================
#  HISSAR P5: IP LOGGING FOR TOKEN SHARING DETECTION
# ============================================================

def log_token_ip(token: str, ip_address: str) -> int:
    """Log an IP address used with a token. Returns unique IP count for this token.

    Uses UPSERT: if the (token, ip) pair already exists, increments
    request_count and updates last_seen. Otherwise creates a new row.
    """
    conn = _connect()
    conn.execute(
        """INSERT INTO token_ip_log (token, ip_address)
           VALUES (?, ?)
           ON CONFLICT(token, ip_address) DO UPDATE SET
               last_seen=datetime('now'),
               request_count=request_count+1""",
        (token, ip_address),
    )
    conn.commit()
    # Count unique IPs for this token
    row = conn.execute(
        "SELECT COUNT(DISTINCT ip_address) as cnt FROM token_ip_log WHERE token=?",
        (token,),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_token_ip_count(token: str) -> int:
    """Get the number of unique IPs that have used this token."""
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(DISTINCT ip_address) as cnt FROM token_ip_log WHERE token=?",
        (token,),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_token_ips(token: str) -> list[dict]:
    """Get all IPs that have used a token, with timestamps and counts."""
    conn = _connect()
    rows = conn.execute(
        "SELECT ip_address, first_seen, last_seen, request_count FROM token_ip_log WHERE token=? ORDER BY last_seen DESC",
        (token,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def revoke_member_token(discord_id: str) -> bool:
    """Delete all link tokens for a member, forcing them to re-link.
    Returns True if any tokens were deleted."""
    conn = _connect()
    cur = conn.execute(
        "DELETE FROM link_tokens WHERE discord_id=?",
        (discord_id,),
    )
    conn.commit()
    removed = cur.rowcount
    conn.close()
    return removed > 0


def get_token_for_member(discord_id: str) -> str | None:
    """Get the link token for a member, or None."""
    conn = _connect()
    row = conn.execute(
        "SELECT token FROM link_tokens WHERE discord_id=?",
        (discord_id,),
    ).fetchone()
    conn.close()
    return row["token"] if row else None



# ============================================================
#  HISSAR P6: SECURITY MONITORING STATS
# ============================================================

def get_security_stats() -> dict:
    """Get security metrics for the Markaz daily digest.

    Returns:
        {
            "flagged_tokens": int,       # tokens with 5+ unique IPs
            "total_tracked_tokens": int,  # tokens that have any IP logged
            "revoked_today": int,         # tokens revoked in last 24h (via setting keys)
            "suspicious_ips": list,       # [{token, discord_name, ip_count}] for flagged
        }
    """
    conn = _connect()

    # Tokens with 5+ unique IPs (flagged)
    flagged_rows = conn.execute(
        """SELECT token, COUNT(DISTINCT ip_address) as ip_count
           FROM token_ip_log GROUP BY token HAVING ip_count >= 5"""
    ).fetchall()

    flagged_tokens = len(flagged_rows)

    # Enrich with member names
    suspicious = []
    for r in flagged_rows:
        member = get_member_by_token(r["token"])
        name = (member.get("discord_name", "Unknown") if member else "Unknown").split("#")[0]
        suspicious.append({
            "token": r["token"][:8] + "...",
            "discord_name": name,
            "ip_count": r["ip_count"],
        })

    # Total tokens with any IP activity
    tracked = conn.execute(
        "SELECT COUNT(DISTINCT token) as cnt FROM token_ip_log"
    ).fetchone()
    total_tracked = tracked["cnt"] if tracked else 0

    conn.close()

    return {
        "flagged_tokens": flagged_tokens,
        "total_tracked_tokens": total_tracked,
        "suspicious": suspicious,
    }



# ============================================================
#  ONBOARDING JOURNEY COVERAGE (nour_journey / nour_onboarding)
# ============================================================

def get_journey_coverage(discord_id: str) -> dict:
    """Read a student's onboarding coverage flags (design.md Section
    9.1). Returns all-zero defaults (matching the table's own column
    defaults) for a student with no row yet -- this is a pure READ
    added in Phase A3.1 so `get_my_journey_coverage` (the student
    tool) has something real to expose; Phase A6.4 is what wires the
    WRITE side to real signals (task completion, !link usage, etc.).
    Reading a not-yet-written row as "nothing covered yet" is correct
    either way -- it's not a placeholder that needs revisiting once
    A6.4 lands, just the natural starting state.
    """
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM journey_coverage WHERE discord_id=?", (discord_id,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {
        "discord_id": discord_id,
        "knows_daily_tasks": 0,
        "knows_platform_link": 0,
        "knows_streaks": 0,
        "knows_channels": 0,
        "first_task_done": 0,
        "updated_at": None,
    }


def get_member_rank(discord_id: str) -> Optional[int]:
    """1-indexed rank of an active member by total_points, or None if
    the member is not active/doesn't exist. leaderboard() only returns
    a top-N slice, which can't answer "where do I rank" for anyone
    outside that slice.
    """
    conn = _connect()
    rows = conn.execute(
        "SELECT discord_id FROM members WHERE status='active' ORDER BY total_points DESC"
    ).fetchall()
    conn.close()
    ids = [r["discord_id"] for r in rows]
    if discord_id not in ids:
        return None
    return ids.index(discord_id) + 1


# ============================================================
#  ONBOARDING JOURNEY COVERAGE (write path)
# ============================================================

def set_journey_coverage(discord_id: str, **flags) -> None:
    """Flip one or more journey_coverage flags for a student, based on
    a REAL observed signal (task completion, !link usage, viewing
    !streak, visiting a tour channel) -- design.md Section 9.1's
    explicit "computed from real signals, not advanced by chat
    replies" requirement, replacing the FSM's rigid step-advance model
    with independent boolean facts.

    Upserts: creates the row on a student's first tracked signal
    (INSERT OR IGNORE), otherwise only touches the flags actually
    passed -- any flag not passed keeps its current value, so calling
    this from `cmd_done` never accidentally resets `knows_channels` to
    0 just because `cmd_done` itself has no opinion about it.

    Valid flags: knows_daily_tasks, knows_platform_link, knows_streaks,
    knows_channels, first_task_done. Any other key is silently
    ignored -- a typo'd flag name must never crash a LIVE command call
    site (cmd_done, cmd_link, cmd_streak, on_message all call this
    directly per Phase A6.4).
    """
    valid_flags = {"knows_daily_tasks", "knows_platform_link", "knows_streaks",
                   "knows_channels", "first_task_done"}
    flags = {k: (1 if v else 0) for k, v in flags.items() if k in valid_flags}
    if not flags:
        return
    conn = _connect()
    try:
        # journey_coverage.discord_id has a FOREIGN KEY to members --
        # a real call site (on_message's channel-visit signal, in
        # particular) can fire for a Discord user who has sent a
        # message but never run !join. This must degrade to a silent
        # no-op, not an uncaught IntegrityError crashing the message
        # handler -- same FK-tolerance convention already used by
        # log_notification() elsewhere in this file.
        conn.execute(
            "INSERT OR IGNORE INTO journey_coverage (discord_id) VALUES (?)",
            (discord_id,),
        )
        sets = ", ".join(f"{k}=?" for k in flags) + ", updated_at=datetime('now')"
        conn.execute(
            f"UPDATE journey_coverage SET {sets} WHERE discord_id=?",
            list(flags.values()) + [discord_id],
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # FK constraint -- discord_id isn't a registered member yet
    finally:
        conn.close()


# ============================================================
#  DARB (درب) — claim codes, device sessions, practice mastery
#  Phase 1 backend foundation. All inert until the Darb API +
#  practice-page UI (Phases 2-3) call these. All time logic uses
#  SQLite's own datetime('now') (UTC) to avoid Python/SQL clock skew.
# ============================================================

# The 4 ORIGINAL practice-platform exercises. Days practised BEFORE
# config.SPEAKING_LAUNCH_DATE are "done/green" when all 4 have
# completion_count >= 1 (grandfathered — never un-greened).
PRACTICE_EXERCISES = ("accent", "vocab", "shadow", "listening")
SPEAKING_EXERCISE = "speaking"
# The FULL practice-page set once Speaking is required (E1). Days practised
# on/after config.SPEAKING_LAUNCH_DATE need all 5 of these to turn green.
CALENDAR_EXERCISES = PRACTICE_EXERCISES + (SPEAKING_EXERCISE,)

# WEEKLY exercises — tracked and rewarded, but deliberately NOT part of
# PRACTICE_EXERCISES/CALENDAR_EXERCISES, so they can never un-green a day.
#
# `grammar` is the curriculum's weekly pattern: exactly ONE pattern is
# authored per week (content/{level}/grammar/weekN.json), so requiring it
# *daily* would be wrong by design and would retroactively break every
# existing green day and streak. It is additive in exactly the way
# SPEAKING was additive before its launch date: the API accepts it,
# `record_practice_mastery` tiers it, points are awarded — but
# `get_calendar_mastery` only ever reads `required_exercises_for_date()`,
# so grammar rows are ignored by the calendar's "done" calculation.
#
# `reading` (Phase 11B) is weekly for the same reason: one passage is authored
# per week, and it is being rolled out level by level behind the owner approval
# gate, so it must never be a precondition for a day being green either.
#
# `mediation` (Phase 11B) — the fourth CEFR mode, also one authored task per
# week and also rolled out level by level, so weekly and never a day gate.
#
# `review` (Phase 11C) is the weekly retrieval-practice quiz. Weekly for the
# same reason and, like the others, never a day gate -- a student must not lose
# a green day because they have not yet sat the week's review.
#
# `broadcast` (Phase 11D) is the extended-listening exercise: about a minute of
# connected speech per week with gist-first comprehension. One script authored
# per week, rolled out level by level, so weekly and never a day gate. It is
# deliberately a SEPARATE exercise from `listening` (which is word-level
# dictation) because the two evidence different things -- see
# curriculum.get_broadcast_for_week.
WEEKLY_EXERCISES = ("grammar", "reading", "mediation", "review", "broadcast")
# Everything the practice site may legitimately report a completion for.
TRACKED_EXERCISES = CALENDAR_EXERCISES + WEEKLY_EXERCISES
MASTERY_MAX_TIER = 5  # 🥉Bronze 🥈Silver 🥇Gold 💠Platinum 💎Diamond


def speaking_launch_date() -> Optional[datetime.date]:
    """The date Speaking became the 5th REQUIRED calendar exercise, from
    config (env-overridable). None if unset/unparseable → 5th requirement
    disabled (calendar stays 4-core)."""
    raw = getattr(config, "SPEAKING_LAUNCH_DATE", "") or ""
    try:
        return datetime.date.fromisoformat(str(raw)[:10])
    except (ValueError, TypeError):
        return None


def required_exercises_for_date(d: datetime.date) -> tuple:
    """Which exercises must ALL be complete for the practice day on date `d`
    to be green. On/after the speaking launch → the 5 CALENDAR_EXERCISES;
    before it (or if disabled) → the original 4 PRACTICE_EXERCISES. This is
    what grandfathers historic days so they're never un-greened."""
    launch = speaking_launch_date()
    if launch is not None and d >= launch:
        return CALENDAR_EXERCISES
    return PRACTICE_EXERCISES


# ---- Claim codes (one-time bridge from !link to a web session) ----

def create_claim_code(discord_id: str, ttl_minutes: int = 15,
                      max_per_hour: int = 6) -> Optional[str]:
    """Issue a fresh single-use claim code for a student.

    Soft-invalidates any prior unconsumed code (so a student can't
    stockpile codes to hand out). Rate-limited to `max_per_hour` codes
    per student per rolling hour — returns None if exceeded.
    """
    import secrets
    conn = _connect()
    try:
        recent = conn.execute(
            "SELECT COUNT(*) c FROM claim_codes "
            "WHERE discord_id=? AND created_at >= datetime('now','-1 hour')",
            (discord_id,),
        ).fetchone()["c"]
        if recent >= max_per_hour:
            return None
        # Invalidate prior unconsumed codes (expire them now).
        conn.execute(
            "UPDATE claim_codes SET expires_at=datetime('now') "
            "WHERE discord_id=? AND consumed_at IS NULL",
            (discord_id,),
        )
        code = secrets.token_hex(4).upper()  # 8 hex chars, easy to read/paste
        conn.execute(
            "INSERT INTO claim_codes (code, discord_id, expires_at) "
            "VALUES (?, ?, datetime('now', ?))",
            (code, discord_id, f"+{int(ttl_minutes)} minutes"),
        )
        conn.commit()
        return code
    finally:
        conn.close()


def consume_claim_code(code: str) -> Optional[str]:
    """Atomically consume a claim code. Returns the discord_id if the
    code was valid (exists, unexpired, unconsumed) and is now consumed;
    None otherwise. The conditional UPDATE + rowcount guards against a
    double-claim race (only one caller can flip consumed_at)."""
    if not code:
        return None
    conn = _connect()
    try:
        cur = conn.execute(
            "UPDATE claim_codes SET consumed_at=datetime('now') "
            "WHERE code=? AND consumed_at IS NULL AND expires_at > datetime('now')",
            (code,),
        )
        if cur.rowcount != 1:
            conn.rollback()
            return None
        row = conn.execute(
            "SELECT discord_id FROM claim_codes WHERE code=?", (code,)
        ).fetchone()
        conn.commit()
        return row["discord_id"] if row else None
    finally:
        conn.close()


# ---- Device sessions (durable per-device web access, capped) ----

def create_device_session(discord_id: str, device_id: str,
                          ip: str = "", user_agent: str = "") -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO device_sessions "
            "(device_id, discord_id, created_ip, user_agent, last_seen_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (device_id, discord_id, ip or "", (user_agent or "")[:400]),
        )
        conn.commit()
    finally:
        conn.close()


def active_device_sessions(discord_id: str) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM device_sessions WHERE discord_id=? AND revoked=0 "
            "ORDER BY created_at ASC",
            (discord_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def revoke_device_session(device_id: str) -> None:
    conn = _connect()
    try:
        conn.execute("UPDATE device_sessions SET revoked=1 WHERE device_id=?", (device_id,))
        conn.commit()
    finally:
        conn.close()


def revoke_all_device_sessions(discord_id: str) -> int:
    """Revoke every active session for a student (owner anti-abuse action).
    Returns the number revoked."""
    conn = _connect()
    try:
        cur = conn.execute(
            "UPDATE device_sessions SET revoked=1 WHERE discord_id=? AND revoked=0",
            (discord_id,),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def enforce_device_cap(discord_id: str, cap: int = 2) -> list[str]:
    """Keep at most `cap` active sessions for a student. Revokes the
    OLDEST beyond the cap. Returns the list of revoked device_ids (so
    the caller can alert the owner)."""
    active = active_device_sessions(discord_id)
    revoked: list[str] = []
    if len(active) > cap:
        for row in active[: len(active) - cap]:  # oldest first
            revoke_device_session(row["device_id"])
            revoked.append(row["device_id"])
    return revoked


def is_device_session_active(device_id: str) -> bool:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT revoked FROM device_sessions WHERE device_id=?", (device_id,)
        ).fetchone()
        return bool(row) and row["revoked"] == 0
    finally:
        conn.close()


def touch_device_session(device_id: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE device_sessions SET last_seen_at=datetime('now') WHERE device_id=?",
            (device_id,),
        )
        conn.commit()
    finally:
        conn.close()


# ---- Practice mastery (content-day-aware completion + tiers) ----

def record_practice_mastery(discord_id: str, level: str, week: int, day: int,
                            exercise: str, today: str = None) -> dict:
    """Record one completion of a content-day exercise and return the
    resulting mastery tier.

    The tier (completion_count, capped at MASTERY_MAX_TIER) increments at
    most ONCE per calendar day — a same-day repeat does not advance it
    (spaced repetition; prevents farming). This is the calendar's source
    of truth, independent of the calendar DATE (so catching up a past day
    works). It does NOT touch streaks/points — the caller pairs this with
    the canonical `tasks.process_submission` for that.

    Returns {"exercise_tier": int, "incremented": bool}.
    """
    if today is None:
        today = _today_local().isoformat()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT completion_count, last_completed_date FROM practice_mastery "
            "WHERE discord_id=? AND level=? AND week=? AND day=? AND exercise=?",
            (discord_id, level, week, day, exercise),
        ).fetchone()
        first_time = row is None
        if first_time:
            count = 1
            conn.execute(
                "INSERT INTO practice_mastery "
                "(discord_id, level, week, day, exercise, completion_count, "
                " first_completed_date, last_completed_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (discord_id, level, week, day, exercise, count, today, today),
            )
            incremented = True
        else:
            # Empire "instant tiers" model: every GENUINE completion levels the
            # tier up by one, capped at Diamond — no once-per-day lock. The
            # caller only reaches here on a real completion (a recording sent,
            # or the flashcards/quiz actually re-done), so this reflects real
            # practice, not button-spam. incremented is False only when already
            # at the max tier (nothing left to gain today).
            prev = row["completion_count"]
            count = min(prev + 1, MASTERY_MAX_TIER)
            incremented = count > prev
            conn.execute(
                "UPDATE practice_mastery SET completion_count=?, "
                "last_completed_date=?, "
                "first_completed_date=COALESCE(first_completed_date, ?) "
                "WHERE discord_id=? AND level=? AND week=? AND day=? AND exercise=?",
                (count, today, today, discord_id, level, week, day, exercise),
            )
        conn.commit()
        result = {"exercise_tier": count, "incremented": incremented, "first_time": first_time}
    finally:
        conn.close()

    # Feed the SRS "Review Past Words" queue: the first time a student completes
    # the day's Vocabulary, enroll that day's words for spaced review (they come
    # due tomorrow, per the vocab_srs default). Best-effort and on a FRESH
    # connection AFTER the mastery write is committed + closed, so it can never
    # break or lock the mastery recording. This is the single choke point every
    # completion path funnels through (page checkbox, !done, reactions).
    # Enroll on the FIRST-ever vocab completion only — a redo must not
    # re-enroll (which would reset the spaced-repetition intervals).
    if exercise == "vocab" and result.get("first_time"):
        try:
            enroll_day_vocab_in_srs(discord_id, level, week, day)
        except Exception:
            pass  # never let SRS enrichment break mastery recording
    return result


def practice_completions(discord_id: str, level: str) -> list[dict]:
    """Every recorded practice completion for a member at a level.

    Phase 11C: the raw material for the descriptor evidence portfolio. This is
    a plain read of `practice_mastery` — the table already holds exactly what
    evidence needs (which exercise, which content day, when) — so the portfolio
    needs no new table, no new write path, and works retroactively over a
    student's whole history.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT week, day, exercise, completion_count, "
            "       first_completed_date, last_completed_date "
            "FROM practice_mastery WHERE discord_id=? AND level=? "
            "ORDER BY week, day, exercise",
            (discord_id, level),
        ).fetchall()
        out = [dict(r) for r in rows]

        # Writing and community are DISCORD-ONLY tasks (!6 / !7): they are
        # logged in daily_submissions and never reach practice_mastery. Without
        # them here, every "can write ..." descriptor would be permanently
        # unevidenceable and the portfolio would understate real work — so map
        # those submissions onto their content day too.
        #
        # daily_submissions is keyed by calendar DATE, so we invert the SAME
        # anchor arithmetic the personal calendar uses (anchor + (week-1)*7 +
        # (day-1)) to recover (week, day). If the anchor or a date is
        # unreadable we skip that row rather than guess a week.
        member = get_member(discord_id)
        if member:
            try:
                anchor = datetime.datetime.fromisoformat(
                    level_anchor_iso(member)).date()
            except (ValueError, TypeError):
                anchor = None
            if anchor is not None:
                from . import curriculum
                max_week = curriculum.max_week_for_level(level)
                # `level` is matched only when the row HAS one. Rows predating
                # that column are NULL and keep the old anchor-only behaviour, so
                # existing students lose no retroactive evidence; new rows are
                # attributed exactly and no longer leak across levels.
                want_level = config.cefr_key(level)
                sub_rows = conn.execute(
                    "SELECT date, task_id, level FROM daily_submissions "
                    "WHERE discord_id=? AND task_id IN ('writing','community') "
                    "ORDER BY date",
                    (discord_id,),
                ).fetchall()
                for r in sub_rows:
                    row_level = r["level"]
                    if row_level and config.cefr_key(row_level) != want_level:
                        continue  # work done at a different level
                    try:
                        d = datetime.date.fromisoformat(str(r["date"])[:10])
                    except (ValueError, TypeError):
                        continue
                    offset = (d - anchor).days
                    if offset < 0:
                        continue  # before this level started
                    week, day = offset // 7 + 1, offset % 7 + 1
                    if not (1 <= week <= max_week):
                        continue
                    out.append({
                        "week": week, "day": day, "exercise": r["task_id"],
                        "completion_count": 1,
                        "first_completed_date": str(r["date"])[:10],
                        "last_completed_date": str(r["date"])[:10],
                    })
    finally:
        conn.close()
    out.sort(key=lambda r: (r["week"], r["day"], r["exercise"]))
    return out


def backfill_practice_mastery_from_submissions(discord_id: str) -> dict:
    """Darb Phase 6: reconstruct calendar mastery for a student from their
    real `daily_submissions` history, so days they were actually active
    show as 'done' (green) on the new calendar instead of 'missed'.

    This is the migration path for students who were practising BEFORE the
    Phase 1 `practice_mastery` table existed. It is date-based (robust to
    the day-of-week vs join-anchored question): each historical submission
    of a practice exercise (accent/vocab/shadow/listening) is mapped to the
    content-day it falls on, using the student's level anchor
    (`level_anchor_iso`), and inserted at Bronze (completion_count=1).

    Idempotent + non-destructive: uses INSERT ... ON CONFLICT DO NOTHING,
    so it never lowers or overwrites a tier the student earned for real
    after launch. Safe to run multiple times.

    Returns {"days_marked": int, "exercises_marked": int}.
    """
    member = get_member(discord_id)
    if not member:
        return {"days_marked": 0, "exercises_marked": 0}
    level = member.get("level", "A1")
    try:
        anchor = datetime.datetime.fromisoformat(level_anchor_iso(member)).date()
    except (ValueError, TypeError):
        anchor = _today_local()

    # Which curriculum weeks exist for this level (avoid writing out-of-range)
    from . import curriculum
    max_week = curriculum.max_week_for_level(level)

    practice_ex = set(PRACTICE_EXERCISES)  # accent, vocab, shadow, listening

    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT date, task_id FROM daily_submissions WHERE discord_id=?",
            (discord_id,),
        ).fetchall()

        days_seen = set()
        exercises_marked = 0
        for r in rows:
            task = r["task_id"]
            if task not in practice_ex:
                continue
            try:
                sub_date = datetime.date.fromisoformat(r["date"][:10])
            except (ValueError, TypeError):
                continue
            day_offset = (sub_date - anchor).days
            if day_offset < 0:
                continue  # submission predates this level's start — skip
            cal_index = day_offset + 1
            week = (cal_index - 1) // 7 + 1
            day = (cal_index - 1) % 7 + 1
            if week > max_week:
                continue  # beyond the level's curriculum
            iso = sub_date.isoformat()
            cur = conn.execute(
                "INSERT INTO practice_mastery "
                "(discord_id, level, week, day, exercise, completion_count, "
                " first_completed_date, last_completed_date) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?) "
                "ON CONFLICT(discord_id, level, week, day, exercise) DO NOTHING",
                (discord_id, level, week, day, task, iso, iso),
            )
            if cur.rowcount:
                exercises_marked += 1
                days_seen.add((week, day))
        conn.commit()
        return {"days_marked": len(days_seen), "exercises_marked": exercises_marked}
    finally:
        conn.close()


def get_calendar_mastery(discord_id: str, level: str) -> dict:
    """Return per-content-day mastery for a student+level, for the
    calendar. Keyed by (week, day) → {exercises: {ex: tier}, day_tier,
    done}.

    A day is `done` when every REQUIRED exercise for that day's calendar
    DATE has tier>=1 — 5 exercises (incl. speaking) on/after
    SPEAKING_LAUNCH_DATE, or the original 4 before it (grandfathered, so a
    historic 4/4 day is never un-greened). `day_tier` is the MINIMUM tier
    across the required set (Gold day = all required reached Gold), else 0.
    `exercises` contains exactly the required set for that day, so its size
    is the "N" the page shows as done/N (4 or 5)."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT week, day, exercise, completion_count FROM practice_mastery "
            "WHERE discord_id=? AND level=?",
            (discord_id, level),
        ).fetchall()
    finally:
        conn.close()

    # Anchor (week,day) → real calendar date so we know which days require
    # speaking. Falls back to the 4-core rule if the member/anchor is
    # unknown (fail-safe: never invents a stricter requirement).
    member = get_member(discord_id)
    try:
        anchor = (datetime.date.fromisoformat(level_anchor_iso(member)[:10])
                  if member else None)
    except (ValueError, TypeError):
        anchor = None

    by_day: dict = {}
    for r in rows:
        by_day.setdefault((r["week"], r["day"]), {})[r["exercise"]] = r["completion_count"]
    result: dict = {}
    for key, exmap in by_day.items():
        week, day = key
        if anchor is not None:
            cal_index = (week - 1) * 7 + (day - 1)  # 0-based offset from anchor
            d_date = anchor + datetime.timedelta(days=cal_index)
            required = required_exercises_for_date(d_date)
        else:
            required = PRACTICE_EXERCISES
        tiers = [exmap.get(ex, 0) for ex in required]
        done = bool(tiers) and all(t >= 1 for t in tiers)
        result[key] = {
            "exercises": {ex: exmap.get(ex, 0) for ex in required},
            "day_tier": (min(tiers) if done else 0),
            "done": done,
        }
    return result



# ============================================================
#  ITQAN (weekly assessment) — attempt lifecycle
# ============================================================

def itqan_attempts_count(discord_id: str, level: str, week: int) -> int:
    conn = _connect()
    n = conn.execute(
        "SELECT COUNT(*) c FROM assessment_attempts WHERE discord_id=? AND level=? AND week=?",
        (discord_id, level, week),
    ).fetchone()["c"]
    conn.close()
    return n


def itqan_active_attempt(discord_id: str, level: str, week: int):
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM assessment_attempts WHERE discord_id=? AND level=? AND week=? "
        "AND status='in_progress' ORDER BY id DESC LIMIT 1",
        (discord_id, level, week),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def itqan_get_attempt(attempt_id: int):
    conn = _connect()
    row = conn.execute("SELECT * FROM assessment_attempts WHERE id=?", (attempt_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def itqan_create_attempt(discord_id: str, level: str, week: int, seed: str) -> dict:
    """Create an in_progress attempt; returns {id, attempt_no}."""
    attempt_no = itqan_attempts_count(discord_id, level, week) + 1
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO assessment_attempts (discord_id, level, week, attempt_no, seed) "
        "VALUES (?,?,?,?,?)",
        (discord_id, level, week, attempt_no, seed),
    )
    aid = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": aid, "attempt_no": attempt_no}


def itqan_insert_items(attempt_id: int, discord_id: str, items: list):
    """Persist blueprint items (server-side expected answer + payload)."""
    conn = _connect()
    for it in items:
        conn.execute(
            "INSERT INTO assessment_items (attempt_id, discord_id, item_no, skill, "
            "source_week, prompt_ref, expected) VALUES (?,?,?,?,?,?,?)",
            (attempt_id, discord_id, it["item_no"], it["skill"], it["source_week"],
             json.dumps(it.get("payload", {}), ensure_ascii=False),
             str(it.get("payload", {}).get("expected", ""))),
        )
    conn.commit()
    conn.close()


def itqan_get_items(attempt_id: int) -> list:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM assessment_items WHERE attempt_id=? ORDER BY item_no", (attempt_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def itqan_save_item(attempt_id: int, item_no: int, answer: str,
                    auto_score=None, ai_score=None, correct=None, feedback: str = ""):
    conn = _connect()
    conn.execute(
        "UPDATE assessment_items SET answer=?, auto_score=?, ai_score=?, correct=?, "
        "feedback=? WHERE attempt_id=? AND item_no=?",
        (answer, auto_score, ai_score,
         (None if correct is None else (1 if correct else 0)),
         feedback, attempt_id, item_no),
    )
    conn.commit()
    conn.close()


def itqan_finish_attempt(attempt_id: int, mastery_pct: float, consistency_pct: float,
                         result: str, distinction: bool, status: str, time_expired: bool):
    conn = _connect()
    conn.execute(
        "UPDATE assessment_attempts SET finished_at=datetime('now'), status=?, "
        "mastery_pct=?, consistency_pct=?, result=?, time_expired=? WHERE id=?",
        (status, mastery_pct, consistency_pct, result,
         1 if time_expired else 0, attempt_id),
    )
    if distinction:
        # store distinction implicitly via result label for the attempt
        conn.execute("UPDATE assessment_attempts SET result=? WHERE id=?",
                     ("distinction", attempt_id))
    conn.commit()
    conn.close()


def itqan_last_finished(discord_id: str, level: str, week: int):
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM assessment_attempts WHERE discord_id=? AND level=? AND week=? "
        "AND finished_at IS NOT NULL ORDER BY finished_at DESC LIMIT 1",
        (discord_id, level, week),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def itqan_is_mastered(discord_id: str, level: str, week: int) -> bool:
    conn = _connect()
    row = conn.execute(
        "SELECT mastered FROM week_mastery WHERE discord_id=? AND level=? AND week=?",
        (discord_id, level, week),
    ).fetchone()
    conn.close()
    return bool(row and row["mastered"])


def itqan_upsert_mastery(discord_id: str, level: str, week: int,
                         distinction: bool, best_attempt_id: int):
    conn = _connect()
    conn.execute(
        "INSERT INTO week_mastery (discord_id, level, week, mastered, distinction, "
        "mastered_at, best_attempt_id) VALUES (?,?,?,1,?,datetime('now'),?) "
        "ON CONFLICT(discord_id, level, week) DO UPDATE SET mastered=1, "
        "distinction=MAX(distinction, excluded.distinction), "
        "mastered_at=COALESCE(mastered_at, excluded.mastered_at), "
        "best_attempt_id=excluded.best_attempt_id",
        (discord_id, level, week, 1 if distinction else 0, best_attempt_id),
    )
    conn.commit()
    conn.close()


# ============================================================
#  IJTIHAD (EFFORT ECONOMY) — SEASONS
# ============================================================

# Owner-tunable, same pattern as ITQAN_CONFIG_DEFAULTS. `ijtihad_season1_start`
# is deliberately blank by default: the first season's anchor is chosen ONCE (see
# ijtihad_ensure_seasons) and then persisted, so season boundaries can never
# silently shift under students later.
IJTIHAD_CONFIG_DEFAULTS = {
    "ijtihad_season_weeks": 4,       # int: season length. 4 aligns with the
                                     # monthly-review cadence, so a season can
                                     # close with real achievement news.
    "ijtihad_season1_start": "",     # str: ISO date anchor. Blank = auto-pick
                                     # the most recent Saturday and persist it.
    # Phase 3 — achievement payouts. These are deliberately the LARGEST awards in
    # the economy: before this, mastering a week, scoring a distinction, passing a
    # monthly review and being promoted a level were each worth ZERO, while pure
    # attendance paid 105-205/day. Promotion at 500 is worth ~33 tasks.
    "ijtihad_ip_mastery": 150,       # int: weekly mastery pass
    "ijtihad_ip_distinction": 250,   # int: mastery at >=90% (replaces the above)
    "ijtihad_ip_monthly": 300,       # int: monthly review pass
    "ijtihad_ip_promotion": 500,     # int: level promotion (A1->A2, ...)
}


def get_ijtihad_config() -> dict:
    """Ijtihad config with `settings` overrides over the defaults.
    Never raises: blank/invalid values fall back to the default."""
    cfg = {}
    for key, default in IJTIHAD_CONFIG_DEFAULTS.items():
        raw = get_setting(key, "")
        if raw == "":
            cfg[key] = default
            continue
        try:
            cfg[key] = type(default)(raw)
        except (ValueError, TypeError):
            cfg[key] = default
    return cfg


def set_ijtihad_config(key: str, value) -> bool:
    """Set one Ijtihad config value. Returns False for unknown keys so typos are
    rejected rather than written as junk settings."""
    if key not in IJTIHAD_CONFIG_DEFAULTS:
        return False
    set_setting(key, str(value))
    return True


def _season_anchor(today: datetime.date) -> datetime.date:
    """The most recent Saturday on/before `today`.

    Saturday because the curriculum week itself starts on Saturday (the Sat=0
    convention used throughout curriculum.py), so a season boundary lands on a
    week boundary rather than mid-week.
    """
    # weekday(): Mon=0 .. Sat=5, Sun=6
    return today - datetime.timedelta(days=(today.weekday() - 5) % 7)


def ijtihad_ensure_seasons(today: Optional[datetime.date] = None) -> Optional[dict]:
    """Create any seasons needed so that `today` is covered, and return the
    season containing `today` (or None if the anchor is still in the future).

    Idempotent and safe to call on every read. Fills gaps, so a bot that was
    offline for two months still produces a correct, contiguous season history
    rather than one giant window.
    """
    today = today or _today_local()
    cfg = get_ijtihad_config()
    weeks = max(1, int(cfg["ijtihad_season_weeks"]))
    span = datetime.timedelta(days=weeks * 7 - 1)

    raw_anchor = (cfg.get("ijtihad_season1_start") or "").strip()
    if raw_anchor:
        try:
            anchor = datetime.date.fromisoformat(raw_anchor)
        except ValueError:
            anchor = _season_anchor(today)
    else:
        anchor = _season_anchor(today)
        # Persist the chosen anchor so boundaries are stable from now on.
        set_setting("ijtihad_season1_start", anchor.isoformat())

    if today < anchor:
        return None  # the owner scheduled season 1 to start later

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, label, started_on, ends_on FROM seasons ORDER BY started_on DESC LIMIT 1"
        ).fetchone()
        if row is None:
            start = anchor
            n = 1
        else:
            start = datetime.date.fromisoformat(row["ends_on"]) + datetime.timedelta(days=1)
            n = conn.execute("SELECT COUNT(*) AS c FROM seasons").fetchone()["c"] + 1
            if datetime.date.fromisoformat(row["started_on"]) <= today <= datetime.date.fromisoformat(row["ends_on"]):
                return dict(row)

        # Create forward until `today` is covered (fills any gap).
        created = None
        while start <= today:
            end = start + span
            conn.execute(
                "INSERT OR IGNORE INTO seasons (label, started_on, ends_on) VALUES (?,?,?)",
                (f"Season {n}", start.isoformat(), end.isoformat()),
            )
            created = (start, end)
            start = end + datetime.timedelta(days=1)
            n += 1
        conn.commit()

        if created is None:
            return None
        out = conn.execute(
            "SELECT id, label, started_on, ends_on FROM seasons WHERE started_on = ?",
            (created[0].isoformat(),),
        ).fetchone()
        return dict(out) if out else None
    finally:
        conn.close()


def ijtihad_current_season(today: Optional[datetime.date] = None) -> Optional[dict]:
    """The season covering today, creating it if the calendar has moved on."""
    return ijtihad_ensure_seasons(today)


def ijtihad_season_for_date(day: str) -> Optional[dict]:
    """The season containing an ISO date, or None. Pure read — does not create."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, label, started_on, ends_on FROM seasons "
            "WHERE ? BETWEEN started_on AND ends_on LIMIT 1",
            (day,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def ijtihad_all_seasons() -> list:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, label, started_on, ends_on FROM seasons ORDER BY started_on"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def ijtihad_season_points(discord_id: str, season: dict) -> int:
    """Effort points earned by one student inside a season window.

    Derived from points_log, so it reflects whatever awards were actually made
    in that window and needs no separate ledger. date(logged_at) is used because
    logged_at is a full 'YYYY-MM-DD HH:MM:SS' timestamp.
    """
    if not season:
        return 0
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT COALESCE(SUM(points), 0) AS total FROM points_log
               WHERE discord_id = ? AND date(logged_at) BETWEEN ? AND ?""",
            (discord_id, season["started_on"], season["ends_on"]),
        ).fetchone()
        return int(row["total"] or 0)
    finally:
        conn.close()


def ijtihad_season_leaderboard(season: dict, limit: int = 5) -> list:
    """Season effort board.

    Only students who actually earned something this season appear (HAVING > 0).
    That is deliberate: with ~17 active students a board that lists everyone
    tells the bottom half they are losing, which the spec forbids (R7/N3).
    """
    if not season:
        return []
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT m.discord_id, m.discord_name, m.level,
                      COALESCE(SUM(p.points), 0) AS season_points
               FROM members m
               LEFT JOIN points_log p
                      ON p.discord_id = m.discord_id
                     AND date(p.logged_at) BETWEEN ? AND ?
               WHERE m.status = 'active'
               GROUP BY m.discord_id
               HAVING season_points > 0
               ORDER BY season_points DESC, m.discord_name ASC
               LIMIT ?""",
            (season["started_on"], season["ends_on"], limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def ijtihad_season_rank(discord_id: str, season: dict) -> int:
    """1-indexed rank within the season by effort points; 0 if nothing earned.

    Shown privately to the student rather than published, so everyone knows
    where they stand without a public bottom half.
    """
    if not season:
        return 0
    mine = ijtihad_season_points(discord_id, season)
    if mine <= 0:
        return 0
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT COUNT(*) + 1 AS rank FROM (
                   SELECT m.discord_id, COALESCE(SUM(p.points), 0) AS pts
                   FROM members m
                   LEFT JOIN points_log p
                          ON p.discord_id = m.discord_id
                         AND date(p.logged_at) BETWEEN ? AND ?
                   WHERE m.status = 'active'
                   GROUP BY m.discord_id
               ) WHERE pts > ?""",
            (season["started_on"], season["ends_on"], mine),
        ).fetchone()
        return int(row["rank"] or 1)
    finally:
        conn.close()


def ijtihad_already_awarded(discord_id: str, reason: str) -> bool:
    """True if this exact award reason was already paid to this student."""
    conn = _connect()
    try:
        return conn.execute(
            "SELECT 1 FROM points_log WHERE discord_id = ? AND reason = ? LIMIT 1",
            (discord_id, reason),
        ).fetchone() is not None
    finally:
        conn.close()


def ijtihad_award_once(discord_id: str, reason: str, points: int) -> int:
    """Award `points` under a unique `reason`, at most once ever.

    Returns the points actually awarded (0 if it was already paid, or if points
    is non-positive). Achievements are permanent facts, so the dedup key is the
    reason string itself -- the same pattern the streak bonus already uses
    (tasks.py), which is what fixed the 7x200 double-award bug.

    Because season effort is derived from points_log date windows, an award made
    here automatically counts toward the current season with no extra plumbing.
    """
    if points <= 0:
        return 0
    if ijtihad_already_awarded(discord_id, reason):
        return 0
    add_points(discord_id, points, reason)
    return points


def sijil_record(discord_id: str) -> dict:
    """Ijtihad Phase 1 — the permanent Record of Honour, READ ONLY.

    Returns every durable achievement a student has accumulated, across ALL
    levels. Writes nothing and computes nothing new: every value here is already
    stored, it has simply never been shown to the student in one place.

    This exists so that seasonal effort (which resets, by design) never erases
    the record of what someone actually built. See
    .kiro/specs/ijtihad-effort-economy/ design §3.

    A brand-new member with no history returns a fully-populated dict of zeros
    and empty lists -- never None, never a missing key -- so the renderer can be
    unconditional.
    """
    member = get_member(discord_id)
    conn = _connect()
    try:
        weeks = conn.execute(
            """SELECT
                   COALESCE(SUM(CASE WHEN mastered    = 1 THEN 1 ELSE 0 END), 0) AS mastered,
                   COALESCE(SUM(CASE WHEN distinction = 1 THEN 1 ELSE 0 END), 0) AS distinctions
               FROM week_mastery WHERE discord_id = ?""",
            (discord_id,),
        ).fetchone()

        lifetime_tasks = conn.execute(
            "SELECT COUNT(*) AS n FROM daily_submissions WHERE discord_id = ?",
            (discord_id,),
        ).fetchone()

        active_days = conn.execute(
            "SELECT COUNT(*) AS n FROM streaks WHERE discord_id = ? AND tasks_completed > 0",
            (discord_id,),
        ).fetchone()

        perfect_days = conn.execute(
            "SELECT COUNT(*) AS n FROM streaks WHERE discord_id = ? AND all_seven = 1",
            (discord_id,),
        ).fetchone()

        reviews = conn.execute(
            "SELECT COUNT(*) AS n FROM monthly_reviews WHERE discord_id = ? AND passed = 1",
            (discord_id,),
        ).fetchone()

        # Levels earned by examination. `promoted` is the durable truth (an exam
        # can pass while promotion is applied separately), so accept either.
        levels = conn.execute(
            """SELECT level, MIN(attempted_at) AS earned_at
               FROM advancement_exams
               WHERE discord_id = ? AND (promoted = 1 OR passed = 1)
               GROUP BY level ORDER BY earned_at""",
            (discord_id,),
        ).fetchall()
    finally:
        conn.close()

    return {
        "exists": member is not None,
        # Pre-Ijtihad lifetime points, preserved verbatim and labelled as history.
        "legacy_xp": (member or {}).get("total_points", 0) or 0,
        "longest_streak": (member or {}).get("longest_streak", 0) or 0,
        "current_level": (member or {}).get("level", "A1") or "A1",
        "joined_at": (member or {}).get("joined_at", "") or "",
        "weeks_mastered": weeks["mastered"] if weeks else 0,
        "distinctions": weeks["distinctions"] if weeks else 0,
        "monthly_reviews_passed": reviews["n"] if reviews else 0,
        "lifetime_tasks": lifetime_tasks["n"] if lifetime_tasks else 0,
        "active_days": active_days["n"] if active_days else 0,
        "perfect_days": perfect_days["n"] if perfect_days else 0,
        "levels_earned": [
            {"level": r["level"], "earned_at": r["earned_at"]} for r in levels
        ],
    }


def sijil_hall_of_honour(limit: int = 5) -> list:
    """Ijtihad Phase 1 — the Hall of Honour: the permanent board.

    Ranked by durable achievement, NOT by lifetime points and NOT by tenure:
    weeks mastered first, then distinctions, then levels earned by exam. A
    student who joined last week and mastered 3 weeks outranks a student who has
    been present for six months and mastered none -- which is the whole point of
    separating this from the seasonal effort board.

    Only students with at least one real achievement are returned, so this can
    never become a list that quietly ranks people by how long they have existed.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT m.discord_id, m.discord_name, m.level,
                      COALESCE(SUM(CASE WHEN w.mastered    = 1 THEN 1 ELSE 0 END), 0) AS weeks_mastered,
                      COALESCE(SUM(CASE WHEN w.distinction = 1 THEN 1 ELSE 0 END), 0) AS distinctions,
                      (SELECT COUNT(DISTINCT level) FROM advancement_exams a
                        WHERE a.discord_id = m.discord_id
                          AND (a.promoted = 1 OR a.passed = 1)) AS levels_earned
               FROM members m
               LEFT JOIN week_mastery w ON w.discord_id = m.discord_id
               WHERE m.status = 'active'
               GROUP BY m.discord_id
               HAVING weeks_mastered > 0 OR distinctions > 0 OR levels_earned > 0
               ORDER BY weeks_mastered DESC, distinctions DESC, levels_earned DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def itqan_mastered_weeks(discord_id: str, level: str) -> set:
    conn = _connect()
    rows = conn.execute(
        "SELECT week FROM week_mastery WHERE discord_id=? AND level=? AND mastered=1",
        (discord_id, level),
    ).fetchall()
    conn.close()
    return {r["week"] for r in rows}



# ============================================================
#  TAQDEEM — trigger helpers (Phase 0)
# ============================================================

def monthly_reviews_passed(discord_id: str, level: str) -> int:
    """Count how many Monthly Reviews this student has passed for this level."""
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) c FROM monthly_reviews WHERE discord_id=? AND level=? AND passed=1",
        (discord_id, level),
    ).fetchone()
    conn.close()
    return row["c"] if row else 0


def monthly_reviews_taken(discord_id: str, level: str) -> int:
    """Count total Monthly Reviews attempted for this level (passed or not)."""
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) c FROM monthly_reviews WHERE discord_id=? AND level=?",
        (discord_id, level),
    ).fetchone()
    conn.close()
    return row["c"] if row else 0


def monthly_review_due(discord_id: str) -> bool:
    """Check if a Monthly Review is due for this student.

    Due when: (number of weekly passes) >= (reviews_taken + 1) * weeks_per_review
    e.g. with weeks_per_review=4: first review due after 4 weeklies, second after 8.
    Also checks the flag is ON.
    """
    if not is_feature_enabled("assessment_monthly_review", discord_id):
        return False
    member = get_member(discord_id)
    if not member:
        return False
    level = member["level"]
    mastered = itqan_mastered_weeks(discord_id, level)
    taken = monthly_reviews_taken(discord_id, level)

    cfg = get_progression_config()
    weeks_per = cfg.get("progression_monthly_weeks_per_review", 4)

    # Due if they've passed enough weeklies for the NEXT review
    needed = (taken + 1) * weeks_per
    return len(mastered) >= needed


def advancement_exam_due(discord_id: str) -> bool:
    """Check if the Level Advancement Exam is available for this student.

    Available when:
    - All weekly assessments for the level are passed
    - At least 1 Monthly Review is passed
    - Flag is ON
    """
    if not is_feature_enabled("assessment_advancement_exam", discord_id):
        return False
    member = get_member(discord_id)
    if not member:
        return False
    level = member["level"]

    # Need all weeks mastered for this level
    from . import curriculum
    total_weeks = curriculum.max_week_for_level(level)
    mastered = itqan_mastered_weeks(discord_id, level)
    if len(mastered) < total_weeks:
        return False

    # Need at least 1 monthly review passed
    if monthly_reviews_passed(discord_id, level) < 1:
        return False

    return True


def advancement_attempts_count(discord_id: str, level: str) -> int:
    """Count advancement exam attempts for this student+level."""
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) c FROM advancement_exams WHERE discord_id=? AND level=?",
        (discord_id, level),
    ).fetchone()
    conn.close()
    return row["c"] if row else 0


# ============================================================
#  MI'YAR — silent, zero-loss CEFR migration (Phase 0)
# ============================================================
#
# Remaps a student from a legacy level (L0–L3) to a CEFR level (A1–C2)
# WITHOUT losing anything. It:
#   • snapshots the full member record first (reversible),
#   • changes the `level` string on `members` AND on every per-student table
#     that carries a `level` column (week_mastery, assessment_attempts,
#     monthly_reviews, advancement_exams, …) — found dynamically so history
#     stays attached to the new level key,
#   • PRESERVES level_started_at (calendar anchor → identical week position),
#     streak, points, SRS, tokens/sessions, prefs — everything else untouched,
#   • is idempotent (a member already on a CEFR level is skipped),
#   • is dry-run-able (compute + report, write nothing),
#   • is reversible per student (rollback_cefr_migration).

def _tables_with_level_column(conn) -> list:
    """Tables (besides members) that have BOTH discord_id and level columns —
    these must have their `level` remapped so a student's history follows them
    to the new CEFR key. Discovered dynamically so future tables are covered."""
    out = []
    for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        t = r["name"]
        if t in ("members", "cefr_migration_log", "reset_consent_log"):
            continue
        cols = {c["name"] for c in conn.execute(f"PRAGMA table_info({t})").fetchall()}
        if "discord_id" in cols and "level" in cols:
            out.append(t)
    return out


def migrate_member_to_cefr(discord_id: str, dry_run: bool = True) -> dict:
    """Migrate ONE member legacy→CEFR. Returns a report dict describing what
    changed (or would change, in dry-run). Idempotent + reversible."""
    from . import config as _cfg
    member = get_member(discord_id)
    if not member:
        return {"discord_id": discord_id, "status": "not_found"}

    cur_level = member.get("level", "A1")

    # Idempotent: already a CEFR level → nothing to do.
    if cur_level in _cfg.CEFR_LEVELS:
        return {"discord_id": discord_id, "status": "already_cefr",
                "level": cur_level, "name": member.get("discord_name", "")}

    new_level = _cfg.LEGACY_LEVEL_MAP.get(cur_level)
    if not new_level:
        return {"discord_id": discord_id, "status": "no_mapping",
                "level": cur_level}

    conn = _connect()
    try:
        level_tables = _tables_with_level_column(conn)
        # Count rows that will be remapped in each table (for the report).
        remap_counts = {}
        for t in level_tables:
            c = conn.execute(
                f"SELECT COUNT(*) c FROM {t} WHERE discord_id=? AND level=?",
                (discord_id, cur_level)).fetchone()
            if c and c["c"]:
                remap_counts[t] = c["c"]

        report = {
            "discord_id": discord_id,
            "name": member.get("discord_name", ""),
            "from_level": cur_level,
            "to_level": new_level,
            "preserved": {
                "current_streak": member.get("current_streak", 0),
                "longest_streak": member.get("longest_streak", 0),
                "total_points": member.get("total_points", 0),
                "level_started_at": member.get("level_started_at"),
            },
            "remapped_tables": remap_counts,
            "status": "would_migrate" if dry_run else "migrated",
        }

        if dry_run:
            return report

        # --- WRITE PATH ---
        # 1. Snapshot first (proof). Rollback reverses the level column
        #    directly (it never re-inserts from this snapshot), so we omit
        #    raw BLOBs (audio) to keep the migration log lean — while
        #    _dumps_snapshot still guarantees the write can never crash on an
        #    unexpected bytes value.
        snapshot = snapshot_member_data(discord_id, include_blobs=False)
        conn.execute(
            "INSERT INTO cefr_migration_log (discord_id, from_level, to_level, snapshot_json) "
            "VALUES (?, ?, ?, ?)",
            (discord_id, cur_level, new_level, _dumps_snapshot(snapshot)),
        )
        # 2. Remap the member's level ONLY (preserve level_started_at + all counters).
        conn.execute("UPDATE members SET level=? WHERE discord_id=?", (new_level, discord_id))
        # 3. Remap level on every per-student table so history follows them.
        for t in level_tables:
            conn.execute(
                f"UPDATE {t} SET level=? WHERE discord_id=? AND level=?",
                (new_level, discord_id, cur_level))
        conn.commit()
        return report
    finally:
        conn.close()


def migrate_to_cefr(dry_run: bool = True, discord_id: str = None) -> dict:
    """Migrate all active members (or one) legacy→CEFR. Returns a summary +
    per-student reports. Safe to run repeatedly (idempotent)."""
    if discord_id:
        targets = [discord_id]
    else:
        targets = [m["discord_id"] for m in all_active_members()]

    reports = [migrate_member_to_cefr(d, dry_run=dry_run) for d in targets]
    summary = {}
    for r in reports:
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    return {"dry_run": dry_run, "count": len(reports),
            "summary": summary, "reports": reports}


def rollback_cefr_migration(discord_id: str) -> dict:
    """Restore a member to their pre-migration state from the most recent
    (non-rolled-back) snapshot. Reverses the level remap on members + all
    per-student tables. Returns a status dict."""
    import json as _json
    from . import config as _cfg
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM cefr_migration_log WHERE discord_id=? AND rolled_back=0 "
            "ORDER BY id DESC LIMIT 1", (discord_id,)).fetchone()
        if not row:
            return {"discord_id": discord_id, "status": "no_snapshot"}

        from_level = row["from_level"]
        to_level = row["to_level"]

        # Reverse the level remap (CEFR → legacy) on members + per-student tables.
        conn.execute("UPDATE members SET level=? WHERE discord_id=?", (from_level, discord_id))
        for t in _tables_with_level_column(conn):
            conn.execute(
                f"UPDATE {t} SET level=? WHERE discord_id=? AND level=?",
                (from_level, discord_id, to_level))
        conn.execute("UPDATE cefr_migration_log SET rolled_back=1 WHERE id=?", (row["id"],))
        conn.commit()
        return {"discord_id": discord_id, "status": "rolled_back",
                "restored_level": from_level}
    finally:
        conn.close()



# ============================================================
#  ITQAN — owner report + overrides (Phase 7)
# ============================================================

def itqan_report_data(level: str = None) -> dict:
    """Aggregate the owner-facing weekly-assessment report.

    Returns {level, per_student, flagged, most_missed, counts, total_students}.
    `level` optionally restricts to one level (else all active students)."""
    conn = _connect()
    if level:
        members = conn.execute(
            "SELECT discord_id, discord_name, level FROM members "
            "WHERE status='active' AND level=? ORDER BY level, discord_name", (level,)
        ).fetchall()
    else:
        members = conn.execute(
            "SELECT discord_id, discord_name, level FROM members "
            "WHERE status='active' ORDER BY level, discord_name"
        ).fetchall()

    per_student = []
    counts = {"mastered": 0, "not_yet": 0, "flagged": 0, "none": 0}
    for m in members:
        did = m["discord_id"]
        latest = conn.execute(
            "SELECT week, result, status, mastery_pct, consistency_pct, finished_at "
            "FROM assessment_attempts WHERE discord_id=? AND finished_at IS NOT NULL "
            "ORDER BY finished_at DESC LIMIT 1", (did,)
        ).fetchone()
        mastered_count = conn.execute(
            "SELECT COUNT(*) c FROM week_mastery WHERE discord_id=? AND mastered=1", (did,)
        ).fetchone()["c"]
        per_student.append({
            "discord_id": did,
            "name": (m["discord_name"] or "?").split("#")[0],
            "level": m["level"],
            "mastered_count": mastered_count,
            "latest": dict(latest) if latest else None,
        })
        if latest is None:
            counts["none"] += 1
        elif latest["status"] == "flagged":
            counts["flagged"] += 1
        elif latest["result"] in ("mastered", "distinction"):
            counts["mastered"] += 1
        else:
            counts["not_yet"] += 1

    # Flagged queue — attempts awaiting an owner decision.
    fq = ("SELECT a.id attempt_id, a.discord_id, a.level, a.week, a.mastery_pct, "
          "a.consistency_pct, a.finished_at, m.discord_name "
          "FROM assessment_attempts a LEFT JOIN members m ON m.discord_id=a.discord_id "
          "WHERE a.status='flagged'")
    fq_params = ()
    if level:
        fq += " AND a.level=?"
        fq_params = (level,)
    fq += " ORDER BY a.finished_at DESC"
    flagged = []
    for r in conn.execute(fq, fq_params).fetchall():
        d = dict(r)
        d["name"] = (d.pop("discord_name") or "?").split("#")[0]
        flagged.append(d)

    # Most-missed items/skills (from wrong answers).
    if level:
        mm = ("SELECT i.skill, i.source_week, i.expected, COUNT(*) misses "
              "FROM assessment_items i JOIN assessment_attempts a ON a.id=i.attempt_id "
              "WHERE i.correct=0 AND a.level=? "
              "GROUP BY i.skill, i.expected ORDER BY misses DESC LIMIT 10")
        mm_params = (level,)
    else:
        mm = ("SELECT skill, source_week, expected, COUNT(*) misses "
              "FROM assessment_items WHERE correct=0 "
              "GROUP BY skill, expected ORDER BY misses DESC LIMIT 10")
        mm_params = ()
    most_missed = [dict(r) for r in conn.execute(mm, mm_params).fetchall()]

    conn.close()
    return {
        "level": level,
        "per_student": per_student,
        "flagged": flagged,
        "most_missed": most_missed,
        "counts": counts,
        "total_students": len(members),
    }


def itqan_admin_pass(discord_id: str, level: str, week: int,
                     distinction: bool = False) -> dict:
    """Owner override: mark a week mastered manually (resolving a flagged or
    borderline attempt). Marks the latest attempt scored+mastered and upserts
    week_mastery. Returns {best_attempt_id}."""
    conn = _connect()
    latest = conn.execute(
        "SELECT id FROM assessment_attempts WHERE discord_id=? AND level=? AND week=? "
        "ORDER BY id DESC LIMIT 1", (discord_id, level, week)
    ).fetchone()
    best_id = latest["id"] if latest else None
    if best_id is not None:
        conn.execute(
            "UPDATE assessment_attempts SET status='scored', result=? WHERE id=?",
            ("distinction" if distinction else "mastered", best_id),
        )
        conn.commit()
    conn.close()
    itqan_upsert_mastery(discord_id, level, week, distinction, best_id)
    return {"best_attempt_id": best_id}


def itqan_reset(discord_id: str, level: str, week: int) -> dict:
    """Owner override: clear a student's attempts + items + mastery for a week
    so they can retake it from scratch. Returns deletion counts."""
    conn = _connect()
    attempts = [r["id"] for r in conn.execute(
        "SELECT id FROM assessment_attempts WHERE discord_id=? AND level=? AND week=?",
        (discord_id, level, week)).fetchall()]
    items_deleted = 0
    if attempts:
        qmarks = ",".join("?" * len(attempts))
        items_deleted = conn.execute(
            f"DELETE FROM assessment_items WHERE attempt_id IN ({qmarks})",
            attempts).rowcount
        conn.execute(
            f"DELETE FROM assessment_recordings WHERE attempt_id IN ({qmarks})",
            attempts)
    attempts_deleted = conn.execute(
        "DELETE FROM assessment_attempts WHERE discord_id=? AND level=? AND week=?",
        (discord_id, level, week)).rowcount
    mastery_deleted = conn.execute(
        "DELETE FROM week_mastery WHERE discord_id=? AND level=? AND week=?",
        (discord_id, level, week)).rowcount
    conn.commit()
    conn.close()
    return {"attempts_deleted": attempts_deleted, "items_deleted": items_deleted,
            "mastery_deleted": mastery_deleted}


def itqan_delete_attempt(attempt_id: int) -> None:
    """Delete a single attempt + its items + recordings. Used to VOID an
    abandoned/blank attempt (student opened the test and left, timer lapsed)
    so it is never scored as a fail and never starts a retake cooldown."""
    conn = _connect()
    conn.execute("DELETE FROM assessment_items WHERE attempt_id=?", (attempt_id,))
    conn.execute("DELETE FROM assessment_recordings WHERE attempt_id=?", (attempt_id,))
    conn.execute("DELETE FROM assessment_attempts WHERE id=?", (attempt_id,))
    conn.commit()
    conn.close()



# ============================================================
#  ITQAN — progress map + certificate data (Phase 8)
# ============================================================

def itqan_progress(discord_id: str, level: str) -> dict:
    """Weeks-mastered progress for a level: total mastered, % of the level,
    the consecutive streak from week 1, and whether the level is complete."""
    from . import curriculum
    mastered = itqan_mastered_weeks(discord_id, level)
    total = curriculum.max_week_for_level(level)
    # Streak = consecutive mastered weeks starting at week 1 (how deep their
    # unbroken mastery runs — the "progress" streak, not a time streak).
    streak = 0
    w = 1
    while w in mastered:
        streak += 1
        w += 1
    count = len(mastered)
    return {
        "mastered_count": count,
        "total_weeks": total,
        "pct": round(100.0 * count / total, 1) if total else 0.0,
        "streak": streak,
        "mastered_weeks": sorted(mastered),
        "level_complete": bool(total) and count >= total,
    }


def itqan_certificate_data(discord_id: str, level: str) -> dict:
    """Certificate data for the dojo certificate page.

    Mi'yar Phase 8: prefers an EXAM-BASED certificate — if the student has passed
    a level exit exam, the certificate certifies "demonstrated proficiency at
    CEFR Level X" (the stronger credential). Otherwise it falls back to the
    completion certificate (`eligible` only when every week is mastered)."""
    from . import curriculum, config
    prog = itqan_progress(discord_id, level)
    member = get_member(discord_id) or {}
    name = (member.get("discord_name") or "Student").split("#")[0]
    conn = _connect()
    rows = conn.execute(
        "SELECT distinction, mastered_at FROM week_mastery "
        "WHERE discord_id=? AND level=? AND mastered=1",
        (discord_id, level),
    ).fetchall()
    conn.close()
    distinction_count = sum(1 for r in rows if r["distinction"])
    dates = [r["mastered_at"] for r in rows if r["mastered_at"]]
    completed_at = max(dates) if dates else None
    # ── Choose the basis: a passed exit exam (stronger) else all-weeks-mastered.
    exam = highest_passed_exit_exam(discord_id)
    if exam:
        basis = "exam"
        cert_level = exam["level"]
        eligible = True
        distinction = (exam.get("part_b_score") or 0) >= 90  # EXIT_EXAM_DISTINCTION_PART_B
        cert_date = exam.get("attempted_at")
    else:
        basis = "mastery"
        cert_level = config.cefr_key(level)
        eligible = prog["level_complete"]
        distinction = distinction_count > 0
        cert_date = completed_at

    level_name = config.level_info(cert_level).get("name", cert_level)

    # The CEFR "can-do" statements the certified level attests to — a
    # descriptor-referenced checklist. Aligned to the CEFR Companion Volume
    # (2020); an internal, CEFR-aligned-by-design certificate, NOT an official /
    # empirically-validated certification.
    can_do = []
    try:
        cd = json.load(open(config.BASE_DIR / "content" / "cefr" / "can_do.json",
                            encoding="utf-8")).get(config.cefr_key(cert_level), {})
        for mode in ("reception", "production", "interaction", "mediation"):
            for d in cd.get(mode, []):
                can_do.append({"code": d.get("code"), "en": d.get("en"),
                               "ar": d.get("ar"), "mode": mode})
    except Exception:
        can_do = []

    # Phase 11C — attach EVIDENCE to each can-do statement, so the checklist
    # stops being an unbacked claim. Each descriptor gains what the student
    # actually did to prove it (which exercise, which content day), derived
    # from their real completion history.
    #
    # Best-effort: a certificate must still render if the portfolio cannot be
    # computed. In that case descriptors simply carry no evidence rather than
    # the page failing.
    evidence_summary = {"evidenced": 0, "total": len(can_do), "pct": 0}
    try:
        from . import assessment
        portfolio = assessment.descriptor_portfolio(discord_id, cert_level)
        by_code = {p["code"]: p for p in portfolio["descriptors"]}
        for item in can_do:
            p = by_code.get(item["code"])
            item["evidenced"] = bool(p and p["evidenced"])
            item["evidence"] = (p or {}).get("evidence", [])
            item["evidence_count"] = (p or {}).get("evidence_count", 0)
        evidence_summary = {
            "evidenced": sum(1 for i in can_do if i.get("evidenced")),
            "total": len(can_do),
            "pct": round(100 * sum(1 for i in can_do if i.get("evidenced")) / len(can_do))
            if can_do else 0,
        }
    except Exception:
        # This module deliberately has no logger; swallowing here is the point
        # -- a certificate must render even if evidence cannot be computed.
        for item in can_do:
            item.setdefault("evidenced", False)
            item.setdefault("evidence", [])
            item.setdefault("evidence_count", 0)

    # Truth-in-labelling (R0/R8): "certifies … has demonstrated proficiency at
    # CEFR Level X" — never "CEFR-certified".
    if basis == "exam":
        statement_en = (f"Empire English certifies that {name} has demonstrated "
                        f"proficiency at CEFR Level {cert_level}.")
        statement_ar = (f"تشهد Empire English أن {name} أظهر/ت إتقانًا للمستوى "
                        f"{cert_level} على الإطار الأوروبي المرجعي المشترك (CEFR).")
    else:
        statement_en = (f"Empire English certifies that {name} has completed "
                        f"CEFR Level {cert_level} — all weeks mastered.")
        statement_ar = (f"تشهد Empire English أن {name} أتمّ/ت المستوى {cert_level} "
                        f"على الإطار الأوروبي المرجعي (CEFR) — بإتقان كل الأسابيع.")

    # Phase 11C — the LEVEL COMPLETION CONTRACT.
    #
    # It gates the strongest CLAIM, never access: `eligible` above is
    # untouched, so no student who can see their certificate today loses it.
    # Retroactively revoking an earned certificate would be indefensible, and
    # this codebase already set the grandfathering precedent when speaking
    # became a required exercise.
    #
    # When all three criteria hold, the certificate additionally asserts
    # fully-evidenced completion. Short of that it reads exactly as before, and
    # the contract states plainly which criterion is outstanding.
    contract = None
    full_completion = False
    try:
        from . import assessment as _assessment
        contract = _assessment.level_completion_contract(discord_id, cert_level)
        full_completion = bool(contract["met"])
    except Exception:
        contract = None

    if full_completion:
        statement_en += (" Every CEFR can-do statement for this level is backed "
                         "by the student's own recorded work.")
        statement_ar += (" وكل أهداف الـ CEFR لهذا المستوى مدعومة بعمل الطالب "
                         "المسجَّل فعليًا.")

    return {
        "eligible": eligible,
        "basis": basis,                     # 'exam' (stronger) | 'mastery'
        # Phase 11C: provable completion. `eligible` = may they hold a
        # certificate; `full_completion` = is every claim on it proven.
        "contract": contract,
        "full_completion": full_completion,
        "name": name,
        "level": cert_level,
        "level_name": level_name,
        "statement_en": statement_en,
        "statement_ar": statement_ar,
        "distinction": distinction,
        "date": cert_date,
        # mastery-view detail (kept for backward compatibility)
        "weeks_mastered": prog["mastered_count"],
        "total_weeks": prog["total_weeks"],
        "distinction_count": distinction_count,
        "completed_at": completed_at,
        "can_do": can_do,
        # Phase 11C: how much of the checklist is actually backed by the
        # student's own recorded work.
        "evidence": evidence_summary,
        "cefr_aligned": True,
    }


def highest_passed_exit_exam(discord_id: str) -> dict | None:
    """The highest CEFR level for which the student has PASSED the exit exam
    (from `advancement_exams`), with its Part B score + date — the basis for an
    exam-based certificate. None if they have not passed any."""
    from . import config
    conn = _connect()
    rows = conn.execute(
        "SELECT level, part_b_score, overall_score, attempted_at "
        "FROM advancement_exams WHERE discord_id=? AND passed=1", (discord_id,)).fetchall()
    conn.close()
    best, best_idx = None, -1
    for r in rows:
        ck = config.cefr_key(r["level"])
        idx = config.CEFR_ORDER.index(ck) if ck in config.CEFR_ORDER else -1
        if idx > best_idx:
            best_idx = idx
            best = dict(r)
            best["level"] = ck
    return best



# ============================================================
#  ITQAN — audio recording retention for owner review (Phase 9)
# ============================================================

def itqan_save_recording(attempt_id: int, discord_id: str, item_no: int,
                         skill: str, filename: str, audio: bytes) -> None:
    """Persist one assessment recording for owner review (upsert per item)."""
    if not audio:
        return
    conn = _connect()
    conn.execute(
        "INSERT INTO assessment_recordings (attempt_id, discord_id, item_no, skill, filename, audio) "
        "VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(attempt_id, item_no) DO UPDATE SET "
        "filename=excluded.filename, audio=excluded.audio, created_at=datetime('now')",
        (attempt_id, discord_id, item_no, skill, filename, sqlite3.Binary(audio)),
    )
    conn.commit()
    conn.close()


def itqan_get_recordings(attempt_id: int) -> list:
    """All recordings for an attempt (item_no, skill, filename, audio bytes)."""
    conn = _connect()
    rows = conn.execute(
        "SELECT item_no, skill, filename, audio FROM assessment_recordings "
        "WHERE attempt_id=? ORDER BY item_no", (attempt_id,)
    ).fetchall()
    conn.close()
    return [{"item_no": r["item_no"], "skill": r["skill"],
             "filename": r["filename"], "audio": bytes(r["audio"])} for r in rows]


def itqan_purge_recordings(days: int = 14) -> int:
    """Delete recordings older than `days` (retention policy). Returns count."""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    n = conn.execute(
        "DELETE FROM assessment_recordings WHERE created_at < ?", (cutoff,)
    ).rowcount
    conn.commit()
    conn.close()
    return n



def itqan_latest_attempt_id(discord_id: str, level: str, week: int = None):
    """The most recent finished attempt id for a student (optionally a specific
    week). Used by the slash /itqan-review student+week path. Returns int|None."""
    conn = _connect()
    if week is not None:
        row = conn.execute(
            "SELECT id FROM assessment_attempts WHERE discord_id=? AND level=? AND week=? "
            "AND finished_at IS NOT NULL ORDER BY finished_at DESC LIMIT 1",
            (discord_id, level, week),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM assessment_attempts WHERE discord_id=? AND level=? "
            "AND finished_at IS NOT NULL ORDER BY finished_at DESC LIMIT 1",
            (discord_id, level),
        ).fetchone()
    conn.close()
    return row["id"] if row else None



def itqan_status_report(level: str = None) -> dict:
    """Full weekly-assessment status per student (R17.1). For each active
    student: current week, days-done, and a single actionable state:
      due       — a completed week whose assessment isn't passed yet
      flagged   — that due week's latest attempt awaits owner review
      in_progress — current week's days not all done yet
      up_to_date  — nothing due
    Returns {level, rows, counts, total_students}."""
    from . import curriculum
    conn = _connect()
    if level:
        members = conn.execute(
            "SELECT discord_id, discord_name, level FROM members "
            "WHERE status='active' AND level=? ORDER BY level, discord_name", (level,)).fetchall()
    else:
        members = conn.execute(
            "SELECT discord_id, discord_name, level FROM members "
            "WHERE status='active' ORDER BY level, discord_name").fetchall()
    members = [dict(m) for m in members]
    conn.close()

    counts = {"due": 0, "flagged": 0, "in_progress": 0, "up_to_date": 0}
    rows = []
    for m in members:
        did, lvl = m["discord_id"], m["level"]
        maxw = curriculum.max_week_for_level(lvl)
        cur_week = min(max(1, member_week_number(did)), maxw)
        cal = get_calendar_mastery(did, lvl)
        mastered = itqan_mastered_weeks(did, lvl)

        def _week_done(w):
            return all((cal.get((w, d)) or {}).get("day_tier", 0) >= 1 for d in range(1, 8))

        due_week = None
        for w in range(1, cur_week + 1):
            if w not in mastered and _week_done(w):
                due_week = w
                break

        done_days = sum(1 for d in range(1, 8)
                        if (cal.get((cur_week, d)) or {}).get("day_tier", 0) >= 1)

        if due_week is not None:
            last = itqan_last_finished(did, lvl, due_week)
            if last and last.get("status") == "flagged":
                state, label = "flagged", f"Week {due_week} — flagged, needs your review"
                counts["flagged"] += 1
            else:
                state, label = "due", f"Week {due_week} test not done"
                counts["due"] += 1
        elif not _week_done(cur_week):
            state, label = "in_progress", f"Week {cur_week}: {done_days}/7 days"
            counts["in_progress"] += 1
        else:
            state, label = "up_to_date", "up to date"
            counts["up_to_date"] += 1

        rows.append({
            "discord_id": did,
            "name": (m["discord_name"] or "?").split("#")[0],
            "level": lvl,
            "current_week": cur_week,
            "mastered_count": len(mastered),
            "due_week": due_week,
            "state": state,
            "label": label,
        })
    return {"level": level, "rows": rows, "counts": counts, "total_students": len(members)}



def itqan_gate_baseline(discord_id: str, level: str, current_week: int) -> int:
    """Grandfather baseline for the progression gate (R16.4): the week a student
    had already reached when the gate first applied to them. Stamped ONCE
    (per student+level) so enabling the gate never locks anyone out of content
    they'd already reached. Weeks at/below the baseline stay open; the gate only
    governs openings beyond it."""
    key = f"itqan_gate_baseline_{discord_id}_{level}"
    raw = get_setting(key, "")
    if raw:
        try:
            return int(raw)
        except (ValueError, TypeError):
            pass
    baseline = max(1, int(current_week))
    set_setting(key, str(baseline))
    return baseline


def itqan_allowed_week(discord_id: str, level: str, current_week: int) -> int:
    """Highest week whose content the gate allows open: the grandfather baseline,
    extended by each consecutively-mastered week from the baseline. Passing week
    W opens W+1. (Lock-only: never opens a week before its calendar date.)"""
    baseline = itqan_gate_baseline(discord_id, level, current_week)
    mastered = itqan_mastered_weeks(discord_id, level)
    allowed = baseline
    while allowed in mastered:
        allowed += 1
    return allowed



# ============================================================
#  PHASE 8 (Mi'yar CEFR) — exit-exam review queue + placement
# ============================================================

def exit_exam_enqueue_review(discord_id: str, level: str, attempt_num: int | None,
                             part_a_pct: float, part_b_total: int,
                             ai_confidence: float, rater: str,
                             reasons: list, evidenced: list) -> int:
    """Add a boundary/low-confidence exit-exam attempt to the owner review queue.
    Returns the new review id. Clear passes/fails should NOT call this."""
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO exit_exam_reviews "
        "(discord_id, level, attempt_num, part_a_pct, part_b_total, ai_confidence, "
        " rater, reasons, evidenced, status) "
        "VALUES (?,?,?,?,?,?,?,?,?, 'pending')",
        (discord_id, level, attempt_num, part_a_pct, part_b_total, ai_confidence,
         rater, json.dumps(reasons, ensure_ascii=False),
         json.dumps(evidenced, ensure_ascii=False)),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def exit_exam_pending_reviews(level: str | None = None) -> list[dict]:
    """All pending exit-exam reviews (optionally filtered to one level), oldest
    first — the owner's work queue."""
    conn = _connect()
    if level:
        rows = conn.execute(
            "SELECT * FROM exit_exam_reviews WHERE status='pending' AND level=? "
            "ORDER BY created_at ASC", (level,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM exit_exam_reviews WHERE status='pending' "
            "ORDER BY created_at ASC").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("reasons", "evidenced"):
            try:
                d[k] = json.loads(d.get(k) or "[]")
            except Exception:
                d[k] = []
        out.append(d)
    return out


def exit_exam_resolve_review(review_id: int, status: str, resolved_by: str) -> dict | None:
    """Owner resolves a queued review to 'passed' or 'failed'. Returns the
    updated row (so the caller can trigger promotion + certificate on a pass),
    or None if the id was not a pending review."""
    if status not in ("passed", "failed"):
        raise ValueError("status must be 'passed' or 'failed'")
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM exit_exam_reviews WHERE id=? AND status='pending'",
        (review_id,)).fetchone()
    if not row:
        conn.close()
        return None
    conn.execute(
        "UPDATE exit_exam_reviews SET status=?, resolved_at=datetime('now'), "
        "resolved_by=? WHERE id=?", (status, resolved_by, review_id))
    conn.commit()
    updated = conn.execute("SELECT * FROM exit_exam_reviews WHERE id=?",
                           (review_id,)).fetchone()
    conn.close()
    d = dict(updated)
    for k in ("reasons", "evidenced"):
        try:
            d[k] = json.loads(d.get(k) or "[]")
        except Exception:
            d[k] = []
    return d


def save_placement_result(discord_id: str, overall_level: str, skill_bands: dict,
                          recommended_week: int = 1, source: str = "self") -> int:
    """Persist a placement result (per-skill CEFR profile + slotted level).
    Returns the new row id. Does NOT itself change the member's level — the
    caller decides whether to slot (opt-in, never forced)."""
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO placement_result "
        "(discord_id, overall_level, skill_bands, recommended_week, source) "
        "VALUES (?,?,?,?,?)",
        (discord_id, overall_level, json.dumps(skill_bands, ensure_ascii=False),
         int(recommended_week), source),
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def placement_session_save(discord_id: str, state: dict) -> None:
    """Upsert the in-progress placement runner state for a student."""
    conn = _connect()
    conn.execute(
        "INSERT INTO placement_session (discord_id, state, updated_at) "
        "VALUES (?,?,datetime('now')) "
        "ON CONFLICT(discord_id) DO UPDATE SET state=excluded.state, "
        "updated_at=datetime('now')",
        (discord_id, json.dumps(state, ensure_ascii=False)))
    conn.commit()
    conn.close()


def placement_session_get(discord_id: str) -> dict | None:
    """The in-progress placement state, or None if there is no active session."""
    conn = _connect()
    row = conn.execute(
        "SELECT state FROM placement_session WHERE discord_id=?", (discord_id,)).fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row["state"] or "{}")
    except Exception:
        return None


def placement_session_clear(discord_id: str) -> None:
    """Drop a student's placement session (on finish / slot / restart)."""
    conn = _connect()
    conn.execute("DELETE FROM placement_session WHERE discord_id=?", (discord_id,))
    conn.commit()
    conn.close()


def latest_placement_result(discord_id: str) -> dict | None:
    """Most recent placement result for a student, or None."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM placement_result WHERE discord_id=? "
        "ORDER BY taken_at DESC, id DESC LIMIT 1", (discord_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["skill_bands"] = json.loads(d.get("skill_bands") or "{}")
    except Exception:
        d["skill_bands"] = {}
    return d
