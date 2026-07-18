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

    # Wuslah W0.4: last_used on link_tokens table (for token expiry)
    lt_cols = {row["name"] for row in conn.execute("PRAGMA table_info(link_tokens)")}
    if "last_used" not in lt_cols:
        conn.execute("ALTER TABLE link_tokens ADD COLUMN last_used TEXT DEFAULT NULL")

    # Aql A0.6: category on nour_memories table (semantic memory
    # classification -- design.md Section 6). Additive column, same
    # zero-migration-risk pattern as gender/difficulty_level/last_used
    # above. Existing rows default to 'general' rather than NULL, so
    # every pre-existing memory is still a valid, filterable row
    # immediately -- not silently excluded from category-filtered
    # retrieval until someone re-classifies it.
    nm_cols = {row["name"] for row in conn.execute("PRAGMA table_info(nour_memories)")}
    if "category" not in nm_cols:
        conn.execute("ALTER TABLE nour_memories ADD COLUMN category TEXT NOT NULL DEFAULT 'general'")

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

-- Tatawwur (system-evolution spec) Phase T0: voice progress portfolio.
-- Stores benchmark recordings and daily accent recordings over time,
-- enabling students to HEAR their own transformation.
CREATE TABLE IF NOT EXISTS voice_portfolio (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    recorded_at     TEXT NOT NULL DEFAULT (datetime('now')),
    recording_url   TEXT NOT NULL,
    recording_type  TEXT NOT NULL DEFAULT 'daily',
    week            INTEGER DEFAULT NULL,
    level           TEXT DEFAULT '',
    duration_seconds REAL DEFAULT NULL,
    ai_score        REAL DEFAULT NULL,
    notes           TEXT DEFAULT '',
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_voice_portfolio ON voice_portfolio(discord_id, recording_type);

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

-- Tatawwur Phase T3: ability milestones tracking.
CREATE TABLE IF NOT EXISTS ability_milestones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    milestone_id    TEXT NOT NULL,
    completed_at    TEXT NOT NULL DEFAULT (datetime('now')),
    evidence_url    TEXT DEFAULT '',
    level           TEXT NOT NULL DEFAULT 'L0',
    FOREIGN KEY (discord_id) REFERENCES members(discord_id),
    UNIQUE(discord_id, milestone_id)
);

-- Tatawwur Phase T5: conversation session tracking.
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scheduled_at    TEXT NOT NULL,
    level           TEXT NOT NULL DEFAULT 'L0',
    status          TEXT NOT NULL DEFAULT 'scheduled',
    participant_ids TEXT DEFAULT '',
    prompt_id       TEXT DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Sahel Phase S6: personal link tokens for practice platform connection.
CREATE TABLE IF NOT EXISTS link_tokens (
    token           TEXT PRIMARY KEY,
    discord_id      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    last_used       TEXT DEFAULT NULL,
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_link_tokens_member ON link_tokens(discord_id);

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

-- Nour Phase N2: proactive outreach log (prevents double-sending).
CREATE TABLE IF NOT EXISTS nour_outreach_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    outreach_type   TEXT NOT NULL,
    date            TEXT NOT NULL,
    sent_at         TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_nour_outreach ON nour_outreach_log(discord_id, outreach_type, date);

-- Nour Phase N5: memory persistence (facts Nour remembers about students).
CREATE TABLE IF NOT EXISTS nour_memories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    fact            TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_nour_memories ON nour_memories(discord_id);

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

-- Markaz Phase M2: persistent escalation → discord_id mapping. Previously
-- this lived only in an in-memory dict (nour_escalation._pending_escalations),
-- which meant any escalation the owner hadn't yet replied to before a
-- redeploy became permanently unmatchable (the reply would arrive with a
-- telegram_message_id the fresh process had never seen). Persisting this
-- means reply-forwarding survives restarts/deploys.
CREATE TABLE IF NOT EXISTS pending_escalations (
    telegram_message_id INTEGER PRIMARY KEY,
    discord_id           TEXT NOT NULL,
    student_name         TEXT NOT NULL DEFAULT '',
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    resolved             INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_pending_escalations_discord ON pending_escalations(discord_id);

-- Wuslah Phase W4: AI-generated study tips (pre-computed weekly).
-- SUPERSEDED by Masar Phase M2's nour_growth_letters table below --
-- W4.2 (the actual generation task) was designed but never built, so
-- every real student silently received only the generic fallback
-- tips (Hisn D020). Left in place, inert, rather than dropped, per
-- Masar design.md's own note that the migration choice is decided at
-- implementation time -- this way any code still reading it (the old
-- /api/nour-tips endpoint, until M2.5 replaces its dashboard card)
-- keeps working exactly as before with zero behavior change.
CREATE TABLE IF NOT EXISTS nour_study_tips (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    tip_text        TEXT NOT NULL,
    generated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    week            INTEGER NOT NULL,
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_nour_tips ON nour_study_tips(discord_id, week);

-- Masar Phase M0.4 / M2: Nour's Weekly Growth Letter cache. Fixes
-- Hisn D020 by replacing nour_study_tips above with a real, verified
-- generation path (narrative_engine.build_growth_letter()) --
-- generated once per week per student by nour_growth_letter_task()
-- (M2.2), cached here so the dashboard's /api/growth-letter (M2.4)
-- serves it with zero extra AI cost per page load, same pattern as
-- the old nour_study_tips table it replaces.
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
-- SUPERSEDED by Aql's journey_coverage table below (design.md Section
-- 9.1 / 8.1) once Phase A6/A7 cuts over -- left in place, inert, per
-- this codebase's own established migration discipline (see
-- nour_study_tips's precedent: superseded tables are never dropped in
-- the same change that stops writing to them, only in a later,
-- separate cleanup once the replacement is confirmed live).
CREATE TABLE IF NOT EXISTS student_journey (
    discord_id      TEXT PRIMARY KEY,
    current_step    TEXT NOT NULL DEFAULT 'welcome',
    step_data       TEXT DEFAULT '{}',
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    last_step_at    TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT DEFAULT NULL,
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

-- ============================================================
-- AQL (Nour Intelligence Core, Initiative #15) — Phase A0 schema.
-- See .kiro/specs/nour-intelligence-core/design.md for full rationale
-- on every table below. All additive, all inert until the
-- corresponding later phase (A1/A3/A4/A6) actually reads/writes them.
-- ============================================================

-- design.md Section 4.2: chunked + embedded knowledge base. Replaces
-- keyword-substring matching (_KB_CATEGORIES in nour_concierge.py)
-- with real semantic search. `domain` values match
-- data/nour_knowledge/*.md filename stems (student domains) plus new
-- data/nour_knowledge_owner/*.md stems (owner-only domains, Phase A2)
-- -- these are exactly the strings enumerated in
-- src/nour/permissions.py's KNOWLEDGE_DOMAINS mapping.
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    domain          TEXT NOT NULL,
    source_file     TEXT NOT NULL,
    heading         TEXT NOT NULL,
    content         TEXT NOT NULL,
    embedding       BLOB NOT NULL,
    embedding_model TEXT NOT NULL,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_knowledge_domain ON knowledge_chunks(domain);

-- design.md Section 6: episodic memory -- a compact per-student
-- summary of PAST conversation sessions (not verbatim), replacing the
-- need to re-send unbounded raw history on every request. Regenerated
-- weekly per active student (Phase A6.2).
CREATE TABLE IF NOT EXISTS nour_episodic_summaries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    summary_text    TEXT NOT NULL,
    covers_from     TEXT NOT NULL,
    covers_to       TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_episodic_discord ON nour_episodic_summaries(discord_id);

-- design.md Section 9.1: onboarding coverage model, replacing the
-- rigid linear FSM in nour_journey.py. Independent boolean facts,
-- not a sequence -- each flips based on a real signal (task
-- completion, !link usage, channel visits), the SAME detection
-- wiring Rawiya's FSM used, just writing to a coverage table instead
-- of advancing a state pointer (Phase A6.4). Nour's context assembly
-- surfaces uncovered topics as conversational material to weave in
-- naturally, rather than firing a scripted message regardless of fit.
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

-- design.md Section 13: observability for tool-calling (Phase A3.4).
-- Every tool call is logged -- name, args (minus sensitive values),
-- latency, success/fail -- for debugging and for identifying which
-- tools are actually used vs. dead weight.
CREATE TABLE IF NOT EXISTS nour_tool_calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    role            TEXT NOT NULL,
    tool_name       TEXT NOT NULL,
    arguments_json  TEXT DEFAULT '{}',
    latency_ms      INTEGER DEFAULT NULL,
    success         INTEGER NOT NULL DEFAULT 1,
    error_message   TEXT DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_discord ON nour_tool_calls(discord_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_tool ON nour_tool_calls(tool_name);

-- design.md Section 13 / Section 7: observability for the output
-- guardrail gate (Phase A4.5) -- the DIRECT metric for whether the
-- original "random foreign-language output" bug is actually fixed in
-- production. A non-zero role-leak-block count here is itself
-- valuable signal: the structural boundary held AND defense-in-depth
-- caught something, meaning the layered design is working as intended.
CREATE TABLE IF NOT EXISTS nour_guardrail_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id          TEXT NOT NULL,
    guardrail_type      TEXT NOT NULL,  -- 'script' | 'bidi' | 'role_leak'
    original_text_hash  TEXT NOT NULL,  -- hash, not raw text -- avoid storing a second copy of every failure verbatim
    outcome             TEXT NOT NULL,  -- 'corrected_on_retry' | 'template_fallback'
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_guardrail_type ON nour_guardrail_events(guardrail_type);

-- design.md Section 13: observability for retrieval quality (Phase
-- A1.6-A1.7). Every retrieval query + the top-k chunk IDs returned +
-- which chunk was actually used in the final composed answer --
-- the direct replacement for the old ad-hoc "weekly self-review" Groq
-- analysis, now grounded in real retrieval data instead of a sampled
-- conversation summary. Frequent queries with low-similarity top
-- results reveal real knowledge-base gaps.
CREATE TABLE IF NOT EXISTS nour_retrieval_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    role            TEXT NOT NULL,
    query_text      TEXT NOT NULL,
    top_chunk_ids   TEXT DEFAULT '[]',   -- JSON list of knowledge_chunks.id
    top_similarity  REAL DEFAULT NULL,
    used_chunk_id   INTEGER DEFAULT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_retrieval_discord ON nour_retrieval_log(discord_id);
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
    return total_submissions_on_date(datetime.date.today().isoformat())


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
    first. Public counterpart of nour_concierge._get_recent_conversation
    (same query) — used by nour_escalation.py (Markaz M1.4) to include
    conversation history in escalation alerts without reaching into
    nour_concierge's private helpers."""
    conn = _connect()
    rows = conn.execute(
        """SELECT role, message, created_at FROM nour_conversations
           WHERE discord_id=? ORDER BY created_at DESC LIMIT ?""",
        (discord_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


# ============================================================
#  MARKAZ M2: PENDING ESCALATIONS (persistent reply-forwarding map)
# ============================================================

def record_pending_escalation(telegram_message_id: int, discord_id: str,
                              student_name: str = "") -> None:
    """Record a telegram_message_id → discord_id mapping so a later
    owner reply (which only carries the replied-to message_id) can be
    routed back to the right student, even across a bot restart."""
    conn = _connect()
    # try/finally on all four pending_escalations functions below:
    # this table is written to from a long-running background poller
    # (ops_poller.py) that never restarts on its own, so any leaked
    # connection here compounds indefinitely rather than being cleared
    # by a process restart soon after — worth the extra safety even
    # though these specific statements don't hit a FOREIGN KEY (unlike
    # the nour_conversations insert where this exact bug was found).
    try:
        conn.execute(
            """INSERT OR REPLACE INTO pending_escalations
               (telegram_message_id, discord_id, student_name, resolved)
               VALUES (?, ?, ?, 0)""",
            (telegram_message_id, discord_id, student_name),
        )
        conn.commit()
    finally:
        conn.close()


def get_pending_escalation(telegram_message_id: int) -> Optional[dict]:
    """Look up the discord_id for a given telegram_message_id, or None
    if no unresolved escalation matches it."""
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT * FROM pending_escalations
               WHERE telegram_message_id=? AND resolved=0""",
            (telegram_message_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def resolve_pending_escalation(telegram_message_id: int) -> None:
    """Mark an escalation as resolved after the owner's reply has been
    forwarded, so it's no longer matched (also keeps the table from
    growing unbounded in an unhelpful way — resolved rows are still
    kept for history, just excluded from lookups)."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE pending_escalations SET resolved=1 WHERE telegram_message_id=?",
            (telegram_message_id,),
        )
        conn.commit()
    finally:
        conn.close()


def count_pending_escalations() -> int:
    """Count unresolved escalations awaiting an owner reply. Used by
    the Markaz daily digest."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM pending_escalations WHERE resolved=0"
        ).fetchone()
    finally:
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
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
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
#  VOICE PORTFOLIO (Tatawwur Phase T0 — hear your growth)
# ============================================================

def save_voice_recording(discord_id: str, recording_url: str,
                         recording_type: str = "daily",
                         week: int = None, level: str = "",
                         duration_seconds: float = None,
                         ai_score: float = None, notes: str = "") -> int:
    """Save a voice recording to the portfolio. Returns the new row's id.

    recording_type: 'benchmark_day1', 'benchmark_periodic', 'daily',
                    'assessment', 'milestone'
    """
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO voice_portfolio
           (discord_id, recording_url, recording_type, week, level,
            duration_seconds, ai_score, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (discord_id, recording_url, recording_type, week, level,
         duration_seconds, ai_score, notes),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_voice_portfolio(discord_id: str) -> list[dict]:
    """Get all recordings for a member, oldest first."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM voice_portfolio WHERE discord_id=? ORDER BY recorded_at ASC",
        (discord_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_voice_benchmarks(discord_id: str) -> list[dict]:
    """Get only benchmark recordings (day 1 + periodic), for progress comparison."""
    conn = _connect()
    rows = conn.execute(
        """SELECT * FROM voice_portfolio
           WHERE discord_id=? AND recording_type LIKE 'benchmark%'
           ORDER BY recorded_at ASC""",
        (discord_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_voice_recordings(discord_id: str) -> int:
    """Count total recordings in portfolio."""
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM voice_portfolio WHERE discord_id=?",
        (discord_id,),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def has_day1_benchmark(discord_id: str) -> bool:
    """Check if this member already has a Day 1 benchmark recording."""
    conn = _connect()
    row = conn.execute(
        "SELECT 1 FROM voice_portfolio WHERE discord_id=? AND recording_type='benchmark_day1'",
        (discord_id,),
    ).fetchone()
    conn.close()
    return row is not None



# ============================================================
#  SPACED REPETITION (Tatawwur Phase T2)
# ============================================================

def add_word_to_srs(discord_id: str, word: str):
    """Add a word to the SRS queue (idempotent — skips if exists)."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO vocab_srs (discord_id, word) VALUES (?, ?)",
            (discord_id, word),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # already in SRS
    finally:
        conn.close()


def get_due_reviews(discord_id: str, limit: int = 3) -> list[dict]:
    """Get words due for review today (next_review <= today)."""
    today = datetime.date.today().isoformat()
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

    next_review = (datetime.date.today() + datetime.timedelta(days=interval)).isoformat()

    conn.execute(
        """UPDATE vocab_srs SET ease_factor=?, interval_days=?, next_review=?,
           review_count=?, last_score=? WHERE discord_id=? AND word=?""",
        (ef, interval, next_review, count + 1, quality, discord_id, word),
    )
    conn.commit()
    conn.close()


def get_srs_stats(discord_id: str) -> dict:
    """Get vocab SRS statistics for a member."""
    today = datetime.date.today().isoformat()
    conn = _connect()
    total = conn.execute("SELECT COUNT(*) as c FROM vocab_srs WHERE discord_id=?", (discord_id,)).fetchone()["c"]
    due = conn.execute("SELECT COUNT(*) as c FROM vocab_srs WHERE discord_id=? AND next_review<=?", (discord_id, today)).fetchone()["c"]
    mastered = conn.execute("SELECT COUNT(*) as c FROM vocab_srs WHERE discord_id=? AND interval_days>=30", (discord_id,)).fetchone()["c"]
    conn.close()
    return {"total": total, "due_today": due, "mastered": mastered, "learning": total - mastered}


# ============================================================
#  ABILITY MILESTONES (Tatawwur Phase T3)
# ============================================================

def complete_milestone(discord_id: str, milestone_id: str, evidence_url: str = "", level: str = "L0") -> bool:
    """Mark a milestone as completed. Returns True if newly completed."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO ability_milestones (discord_id, milestone_id, evidence_url, level) VALUES (?, ?, ?, ?)",
            (discord_id, milestone_id, evidence_url, level),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # already completed
    finally:
        conn.close()


def get_completed_milestones(discord_id: str) -> list[str]:
    """Get list of milestone_ids this member has completed."""
    conn = _connect()
    rows = conn.execute(
        "SELECT milestone_id FROM ability_milestones WHERE discord_id=?",
        (discord_id,),
    ).fetchall()
    conn.close()
    return [r["milestone_id"] for r in rows]


# ============================================================
#  CONVERSATION SESSIONS (Tatawwur Phase T5)
# ============================================================

def create_conversation_session(scheduled_at: str, level: str, participant_ids: str, prompt_id: str = "") -> int:
    """Create a scheduled conversation session. Returns the new id."""
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO conversation_sessions (scheduled_at, level, participant_ids, prompt_id) VALUES (?, ?, ?, ?)",
        (scheduled_at, level, participant_ids, prompt_id),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_upcoming_sessions(level: str = None) -> list[dict]:
    """Get upcoming conversation sessions (status='scheduled')."""
    conn = _connect()
    if level:
        rows = conn.execute(
            "SELECT * FROM conversation_sessions WHERE status='scheduled' AND level=? ORDER BY scheduled_at",
            (level,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM conversation_sessions WHERE status='scheduled' ORDER BY scheduled_at"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]



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
    """Get progress data for the practice platform given a link token."""
    member = get_member_by_token(token)
    if not member:
        return None

    discord_id = member["discord_id"]
    today = datetime.date.today().isoformat()

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
        "level": member.get("level", "L0"),
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

    next_review = (datetime.date.today() + datetime.timedelta(days=interval)).isoformat()

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


def get_recent_scores(discord_id: str, days: int = 7) -> list[dict]:
    """Get pronunciation scores from the last N days."""
    cutoff = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
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
    zero AI cost per page load, same caching pattern as the old
    nour_study_tips table this replaces."""
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
