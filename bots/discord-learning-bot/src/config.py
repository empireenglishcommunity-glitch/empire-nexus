"""Empire English Community Bot — Central Configuration.

All settings loaded from environment variables (.env file).
Never hardcode secrets. This module is the single source of truth for config.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================================
#  BOT IDENTITY
# ============================================================
BOT_VERSION = "1.3.0"
BOT_NAME = "Empire English Community Bot"
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Hisn D023: the Ghost Bot (Aegis Phase 6) is a second instance of this
# exact same codebase, running in the SAME real production guild under a
# separate token/prefix, intended to be fully isolated via Discord channel
# permission overwrites (restricted to a hidden admin-only category).
#
# That isolation only covers channel-scoped activity. Guild-wide events --
# on_member_join, DM-based flows, reaction-based registration -- are NOT
# channel-scoped and fire for BOTH bot instances on every real event in the
# guild, regardless of which channels either bot can see. Confirmed live
# during Hisn H6: a real join by a Ghost Testing account triggered BOTH
# bots' on_member_join handlers, resulting in two separate, uncoordinated
# welcome-DM sequences landing in the same inbox (one of them from a stale
# Ghost Bot build using an outdated onboarding flow) -- exactly the kind of
# "unprofessional and confusing" first impression this is a Blocker for.
#
# Set IS_GHOST_INSTANCE=true in .env.ghost (and ONLY there -- must stay
# unset/false in the real production .env) to let guild-wide event handlers
# no-op for the ghost instance. The ghost bot's actual purpose (testing
# command behavior against the real guild's role/channel structure via a
# synthetic test account manually running commands) does not require it to
# react to real member joins or DMs at all.
IS_GHOST_INSTANCE = os.getenv("IS_GHOST_INSTANCE", "false").strip().lower() in ("1", "true", "yes")

# ============================================================
#  DISCORD
# ============================================================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID", "0") or "0")

# Command channels (real guild defaults; overridable via env). Student
# commands are used in #bot-commands; admin/owner commands are consolidated
# into the private #admin-commands channel. If ADMIN_COMMANDS_CHANNEL_ID is 0,
# the admin-channel gate is disabled (fail-open) so nothing can break.
BOT_COMMANDS_CHANNEL_ID = int(os.getenv("BOT_COMMANDS_CHANNEL_ID", "1519798081833537657") or "0")
ADMIN_COMMANDS_CHANNEL_ID = int(os.getenv("ADMIN_COMMANDS_CHANNEL_ID", "1529207979302195291") or "0")

# ============================================================
#  AI PROVIDERS
# ============================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
# Aql (#15) Phase A1.2: separate from GEMINI_MODEL above (which is the
# CHAT model) -- this is Gemini's dedicated embedding model, used only
# by src/nour/knowledge/embedder.py for chunk/query embeddings.
# gemini-embedding-001 is the current stable, well-documented model;
# free-tier quota is generous for a corpus of a few hundred chunks
# (design.md Section 11's cost analysis).
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")

# Nutq — self-hosted phoneme pronunciation scorer (services/nutq-scorer).
# This is the FALLBACK engine (used when Azure is unavailable / usage guard trips).
# Internal Docker-network URL; empty disables the call (→ best-effort skip).
NUTQ_SCORER_URL = os.getenv("NUTQ_SCORER_URL", "http://nutq-scorer:8080")
NUTQ_SCORER_TOKEN = os.getenv("NUTQ_SCORER_TOKEN", "")

# Nutq — Azure Pronunciation Assessment (PRIMARY engine). Key + region come from
# the free Azure Speech (F0) resource; empty key → Azure disabled (→ local fallback).
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "")
NUTQ_AZURE_ENABLED = os.getenv("NUTQ_AZURE_ENABLED", "true").strip().lower() in ("1", "true", "yes")
# Free tier is ~5 audio hours/month; guard switches to the local engine at 90%.
NUTQ_AZURE_FREE_SECONDS = int(os.getenv("NUTQ_AZURE_FREE_SECONDS", str(5 * 3600)) or str(5 * 3600))
NUTQ_AZURE_GUARD_FRACTION = float(os.getenv("NUTQ_AZURE_GUARD_FRACTION", "0.9") or "0.9")
# Cost policy: max Azure shadow scorings per student per day. Owner decision:
# STRICT 1/day — the daily graded read gets Azure; "try again" uses the free
# local engine (zero extra Azure cost). Override via env if ever needed.
NUTQ_AZURE_MAX_CALLS_PER_DAY = int(os.getenv("NUTQ_AZURE_MAX_CALLS_PER_DAY", "1") or "1")
# Best-effort scoring time budget (seconds). Long shadow passages need more than
# the original 8s (Azure processes the whole utterance); still bounded so the
# page's "Send" never hangs. Completion + #showcase happen BEFORE scoring anyway.
NUTQ_SCORE_BUDGET_SECONDS = float(os.getenv("NUTQ_SCORE_BUDGET_SECONDS", "15") or "15")
# Azure grades only the first N seconds of a recording (owner decision): keeps
# each Azure check cheap so many students stay within the free tier, while every
# student still gets the ACCURATE Azure score on their first N seconds.
NUTQ_AZURE_MAX_AUDIO_SECONDS = int(os.getenv("NUTQ_AZURE_MAX_AUDIO_SECONDS", "20") or "20")
# Nutq — private "teacher feed": a Discord channel (owner-only, students not in it)
# where the bot posts each student's daily pronunciation score for oversight.
# Student still sees their own feedback privately on the page. 0 = disabled.
NUTQ_TEACHER_FEED_CHANNEL_ID = int(os.getenv("NUTQ_TEACHER_FEED_CHANNEL_ID", "0") or "0")

# ============================================================
#  GOOGLE SHEETS CRM
# ============================================================
GOOGLE_SERVICE_ACCOUNT_EMAIL = os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL", "")
GOOGLE_PRIVATE_KEY = os.getenv("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n")
# No production Sheet ID as a source-code default — a real identifier should
# only ever live in the deployed .env file, never in a fallback baked into
# the codebase (found during the 2026-07-11 security sweep; not a credential
# by itself, but this pattern is exactly how real secrets end up committed
# by accident later). Configure via SHEET_ID in .env.
SHEET_ID = os.getenv("SHEET_ID", "")
SHEET_GID_SUBSCRIBERS = int(os.getenv("SHEET_GID_SUBSCRIBERS", "0") or "0")
SHEET_GID_EVENTS = int(os.getenv("SHEET_GID_EVENTS", "0") or "0")

# ============================================================
#  SCHEDULING
# ============================================================
DAILY_TASK_HOUR = int(os.getenv("DAILY_TASK_HOUR", "6") or "6")
WEEKLY_ASSESSMENT_HOUR = int(os.getenv("WEEKLY_ASSESSMENT_HOUR", "10") or "10")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Dubai")

# ---- Speaking as the 5th required practice exercise (calendar green) ----
# Speaking (E1) is a 5th practice-page exercise. A practice day whose calendar
# DATE is on/after SPEAKING_LAUNCH_DATE requires all 5 exercises (accent, vocab,
# shadow, listening, speaking) to turn "green"; every day BEFORE it is
# grandfathered at the original 4 and can NEVER be un-greened (protects historic
# streaks). Set to a far-future date (e.g. "2099-01-01") to disable the 5th
# requirement entirely. Format: YYYY-MM-DD.
SPEAKING_LAUNCH_DATE = os.getenv("SPEAKING_LAUNCH_DATE", "2026-07-25")

# ============================================================
#  PRACTICE PLATFORM (empireenglishcommunity-glitch/empire-dojo)
# ============================================================
# The web-based daily practice pages (accent drill, shadowing, listening,
# vocab flashcards with Kokoro TTS audio) that mirror each day's curriculum
# 1:1. Defaults to the live Cloudflare Pages URL, which works today.
PRACTICE_PLATFORM_URL = os.getenv(
    "PRACTICE_PLATFORM_URL", "https://practice.empireenglish.online"
).rstrip("/")

# Sahel S6: API port for practice platform connection
API_PORT = int(os.getenv("API_PORT", "8099") or "8099")

# Darb (درب) Phase 1: HMAC secret used to sign practice-platform device
# session tokens. MUST be set in the production server's .env (and the
# SAME value in the Cloudflare Pages env for the Phase 3 edge gate). It
# is NEVER committed to git. When empty, session minting/verification is
# disabled (fail-safe: no valid sessions can be produced or accepted).
# Generate once with: python3 -c "import secrets; print(secrets.token_hex(32))"
DARB_SESSION_SECRET = os.getenv("DARB_SESSION_SECRET", "")

# ============================================================
#  BAWABA: ONBOARDING VIDEO (optional — YouTube link)
# ============================================================
# A 3-minute screen-recorded walkthrough of the Discord mobile app,
# narrated in Arabic. Set in .env once recorded and uploaded.
# The bot includes this link in the welcome DM when bawaba_multimedia
# flag is enabled. Empty string = not yet recorded (gracefully skipped).
ONBOARDING_VIDEO_URL = os.getenv("ONBOARDING_VIDEO_URL", "")

# ============================================================
#  TELEGRAM ALERTS (optional — lifecycle notifications)
# ============================================================
TELEGRAM_ALERT_TOKEN = os.getenv("TELEGRAM_ALERT_TOKEN", "")
TELEGRAM_ALERT_CHAT_ID = os.getenv("TELEGRAM_ALERT_CHAT_ID", "")

# ============================================================
#  MARKAZ: TELEGRAM OPERATIONS HUB (dedicated ops bot — @empire_ops_eec_bot)
# ============================================================
# Separate from TELEGRAM_ALERT_TOKEN above (which was the shared
# @EmpireEnglishBot). Empire Ops is a dedicated bot for owner-facing
# operational messages only: escalations, digests, reports, quick
# actions. See .kiro/specs/telegram-operations-hub/ for the full spec.
OPS_BOT_TOKEN = os.getenv("OPS_BOT_TOKEN", "")
OPS_CHAT_ID = os.getenv("OPS_CHAT_ID", "")  # Owner's private chat with the ops bot

# Maintenance-mode student broadcast: comma-separated Telegram chat IDs of the
# student groups (paid + free) the ops bot should post maintenance start/end
# notices to. The ops bot MUST be a member/admin of each group. Empty = skip
# Telegram groups (Discord #announcements broadcast still fires). E.g.
# MAINTENANCE_TG_CHAT_IDS="-1001234567890,-1009876543210"
MAINTENANCE_TG_CHAT_IDS = [
    c.strip() for c in os.getenv("MAINTENANCE_TG_CHAT_IDS", "").split(",") if c.strip()
]

# ============================================================
#  AQL (Nour Intelligence Core, Initiative #15) — ROLE RESOLUTION
# ============================================================
# The owner's real Discord snowflake ID. This is the structural
# identity check nour/roles.resolve_role() uses to grant the OWNER
# role from Discord (not Telegram) — the Telegram path never needs
# this at all, since every message arriving via OPS_CHAT_ID above is
# already definitionally the owner (unchanged from how ops_poller.py
# has always treated that chat ID).
#
# Deliberately NOT derived from a Discord ROLE (roles are editable by
# anyone with sufficient server permissions) or from being "the first
# registered member" (fragile, accidental). This must be set once in
# .env to the owner's actual Discord user ID and never changes at
# runtime. Empty string = unset, meaning no one currently resolves as
# OWNER via the Discord path (fail-safe default, not fail-open).
OWNER_DISCORD_ID = os.getenv("OWNER_DISCORD_ID", "")

# ============================================================
#  PATHS
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FONTS_DIR = BASE_DIR / "fonts"

# Persistent storage: Docker volume at /app/data_persist, or local fallback
_PERSIST_DIR = BASE_DIR / "data_persist"
if _PERSIST_DIR.is_dir():
    DB_PATH = _PERSIST_DIR / "empire_english.db"
else:
    DB_PATH = BASE_DIR / "empire_english.db"

OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================
#  LEARNING SYSTEM PARAMETERS
# ============================================================
LEVELS = {
    "L0": {
        "name": "Absolute Beginner",
        "name_ar": "مبتدئ تمامًا",
        "emoji": "🌱",
        "color": 0xA8E6CF,
        "duration_weeks": (8, 12),
        "daily_minutes_core": 45,
        "daily_minutes_intensive": 120,
        "vocab_target": 500,
        "speaking_target_seconds": 60,
        "advancement_score": 70,
    },
    "L1": {
        "name": "Survival English",
        "name_ar": "إنجليزية النجاة",
        "emoji": "💪",
        "color": 0x2ECC71,
        "duration_weeks": (10, 14),
        "daily_minutes_core": 60,
        "daily_minutes_intensive": 150,
        "vocab_target": 1500,
        "speaking_target_seconds": 120,
        "advancement_score": 75,
    },
    "L2": {
        "name": "Communication",
        "name_ar": "التواصل",
        "emoji": "🚀",
        "color": 0x3498DB,
        "duration_weeks": (12, 16),
        "daily_minutes_core": 75,
        "daily_minutes_intensive": 180,
        "vocab_target": 3000,
        "speaking_target_seconds": 240,
        "advancement_score": 80,
    },
    "L3": {
        "name": "Fluency & Native Accent",
        "name_ar": "الطلاقة واللهجة",
        "emoji": "👑",
        "color": 0xC27C0E,
        "duration_weeks": None,  # Ongoing
        "daily_minutes_core": 90,
        "daily_minutes_intensive": 200,
        "vocab_target": 5000,
        "speaking_target_seconds": 300,
        "advancement_score": None,  # No advancement — mastery tiers instead
    },
}

# ============================================================
#  CEFR LEVEL MODEL (Mi'yar) — the six official CEFR levels
# ============================================================
#
# Additive + backwards-compatible: the legacy LEVELS dict (L0–L3) is left
# untouched so nothing breaks while Mi'yar is built behind the
# `cefr_curriculum` flag. Once a student is migrated (Phase 2), their
# member.level becomes a CEFR key (A1–C2) and code resolves display info via
# level_info() below, which accepts BOTH legacy and CEFR keys.

CEFR_LEVELS = {
    "A1": {
        "cefr": "A1", "title": "Breakthrough",
        "name": "Beginner", "name_ar": "مبتدئ",
        "emoji": "🌱", "color": 0xA8E6CF,
        "order": 0, "weeks": 10,
        "vocab_target": 750, "speaking_target_seconds": 60,
        "advancement_score": 70,
    },
    "A2": {
        "cefr": "A2", "title": "Waystage",
        "name": "Elementary", "name_ar": "أساسي",
        "emoji": "🌿", "color": 0x2ECC71,
        "order": 1, "weeks": 12,
        "vocab_target": 1500, "speaking_target_seconds": 90,
        "advancement_score": 72,
    },
    "B1": {
        "cefr": "B1", "title": "Threshold",
        "name": "Intermediate", "name_ar": "متوسط",
        "emoji": "🚀", "color": 0x3498DB,
        "order": 2, "weeks": 14,
        "vocab_target": 3250, "speaking_target_seconds": 120,
        "advancement_score": 75,
    },
    "B2": {
        "cefr": "B2", "title": "Vantage",
        "name": "Upper-Intermediate", "name_ar": "فوق المتوسط",
        "emoji": "💪", "color": 0x9B59B6,
        "order": 3, "weeks": 16,
        "vocab_target": 5000, "speaking_target_seconds": 180,
        "advancement_score": 75,
    },
    "C1": {
        "cefr": "C1", "title": "Effective Operational Proficiency",
        "name": "Advanced", "name_ar": "متقدّم",
        "emoji": "🏆", "color": 0xE67E22,
        "order": 4, "weeks": 18,
        "vocab_target": 8000, "speaking_target_seconds": 240,
        "advancement_score": 78,
    },
    "C2": {
        "cefr": "C2", "title": "Mastery",
        "name": "Proficiency", "name_ar": "إتقان",
        "emoji": "👑", "color": 0xC0392B,
        "order": 5, "weeks": 20,
        "vocab_target": 10000, "speaking_target_seconds": 300,
        "advancement_score": 80,
    },
}

# Legacy → CEFR mapping (used by the silent migration + backwards reads).
LEGACY_LEVEL_MAP = {"L0": "A1", "L1": "A2", "L2": "B1", "L3": "B2"}
CEFR_TO_LEGACY = {v: k for k, v in LEGACY_LEVEL_MAP.items()}
CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def is_cefr_level(level: str) -> bool:
    """True if `level` is a CEFR key (A1–C2)."""
    return level in CEFR_LEVELS


def next_cefr_level(level: str) -> str:
    """The CEFR level after `level`, or None at the top (C2). Accepts a legacy
    key too (maps it first)."""
    cefr = level if level in CEFR_LEVELS else LEGACY_LEVEL_MAP.get(level)
    if cefr not in CEFR_ORDER:
        return None
    i = CEFR_ORDER.index(cefr)
    return CEFR_ORDER[i + 1] if i + 1 < len(CEFR_ORDER) else None


def level_info(level: str) -> dict:
    """Resolve display/config info for a level key, accepting BOTH CEFR
    (A1–C2) and legacy (L0–L3) keys. This is the single lookup that lets the
    codebase work during and after the migration. Falls back to A1/L0."""
    if level in CEFR_LEVELS:
        return CEFR_LEVELS[level]
    if level in LEVELS:
        # Legacy key: return the legacy dict but annotate its CEFR equivalent.
        info = dict(LEVELS[level])
        info["cefr"] = LEGACY_LEVEL_MAP.get(level, "A1")
        return info
    return CEFR_LEVELS["A1"]


# ============================================================
#  CEFR harmonization helpers — the SINGLE source of truth for how a
#  student's level becomes a display label, a Discord role name, or a
#  channel/URL slug. Every module (bot displays, role assignment, daily-task
#  routing, practice API, setup script) must go through these rather than
#  hardcoding L0–L3 or reaching into config.LEVELS directly, so the whole
#  system stays in harmony on the six CEFR levels.
# ============================================================

# Exact legacy L0–L3 Discord role names (pre-CEFR). Retained ONLY so the
# migration / role-reassignment can find and strip a student's stale legacy
# role before granting their CEFR role. Do NOT use for new assignments.
LEGACY_ROLE_NAMES = {
    "L0": "🌱 Level 0 | مبتدئ",
    "L1": "💪 Level 1 | متقدم",
    "L2": "🚀 Level 2 | متواصل",
    "L3": "👑 Level 3 | طليق",
}

# Cumulative points (XP) to be considered "in" each CEFR level — drives the
# gamified progress bar on the practice dashboard (CEFR replacement for the
# old hardcoded {"L0":0,"L1":2000,"L2":5000,"L3":10000}).
CEFR_XP_THRESHOLDS = {"A1": 0, "A2": 2000, "B1": 5000, "B2": 10000, "C1": 18000, "C2": 30000}


def level_slug(level: str) -> str:
    """CEFR channel/URL slug for a level: 'A1' -> 'a1'. Legacy keys are
    normalised to their CEFR level FIRST ('L1' -> 'a2'), so a slug can NEVER
    point at an archived legacy l0–l3 channel or path. Used for Discord channel
    names (a1-daily-tasks) and practice-site paths (/a1/week1/day1/)."""
    return cefr_key(level).lower()


def cefr_key(level: str) -> str:
    """Normalize ANY level key to its CEFR key (A1–C2). A CEFR key returns
    itself; a legacy key maps via LEGACY_LEVEL_MAP; anything else -> 'A1'.
    Role names, display labels and slugs are all derived from the CEFR level's
    OWN data via this, so a legacy key renders identically to its CEFR level
    (no drift between 'L0' and 'A1')."""
    if level in CEFR_LEVELS:
        return level
    return LEGACY_LEVEL_MAP.get(level, "A1")


def level_display(level: str) -> str:
    """Short student-facing label for a level, e.g. '🌱 A1 · Breakthrough'.
    Accepts CEFR or legacy keys (both render as the CEFR level)."""
    info = CEFR_LEVELS[cefr_key(level)]
    return f"{info['emoji']} {info['cefr']} · {info['title']}".strip()


def level_role_name(level: str) -> str:
    """Discord role name for a level, CEFR-driven and bilingual:
    '<emoji> <CEFR> | <arabic name>' (e.g. '🌱 A1 | مبتدئ'). Accepts legacy
    keys (rendered as their CEFR equivalent)."""
    info = CEFR_LEVELS[cefr_key(level)]
    return f"{info['emoji']} {info['cefr']} | {info['name_ar']}".strip()


def all_cefr_role_names() -> list:
    """The six CEFR level role names, in order A1→C2."""
    return [level_role_name(lvl) for lvl in CEFR_ORDER]


def all_managed_level_role_names() -> list:
    """Every level role the bot manages: the six CEFR roles PLUS the four
    legacy L0–L3 role names. Used when assigning a new level role so ANY
    stale level role (CEFR or legacy) is stripped first."""
    return all_cefr_role_names() + list(LEGACY_ROLE_NAMES.values())


def level_xp_threshold(level: str) -> int:
    """Cumulative points needed to be 'in' this level (0 for A1). Accepts
    legacy keys (mapped to their CEFR equivalent)."""
    return CEFR_XP_THRESHOLDS.get(cefr_key(level), 0)


# Daily task structure (7 tasks in fixed order — same every level)
DAILY_TASKS = [
    {"id": "accent", "name": "Accent/Phoneme Drill", "name_ar": "تدريب النطق", "emoji": "🎯"},
    {"id": "vocab", "name": "Vocabulary Acquisition", "name_ar": "مفردات جديدة", "emoji": "📖"},
    {"id": "shadow", "name": "Shadowing Practice", "name_ar": "تمرين المحاكاة", "emoji": "🎧"},
    # listening before speaking so the daily-post numbering reads 1-2-3-4-5
    # in display order (the post lists these as accent, vocab, shadow,
    # listening, speaking; the emoji number = position here, so the two must
    # agree). !1-!7 and the reaction emojis index into this list, so they
    # stay consistent automatically: !4 = listening, !5 = speaking.
    {"id": "listening", "name": "Listening Exercise", "name_ar": "تمرين الاستماع", "emoji": "👂"},
    {"id": "speaking", "name": "Speaking Mission", "name_ar": "مهمة الكلام", "emoji": "🎙️"},
    {"id": "writing", "name": "Writing Practice", "name_ar": "تمرين الكتابة", "emoji": "✍️"},
    {"id": "community", "name": "Community Participation", "name_ar": "مشاركة مجتمعية", "emoji": "💬"},
]

# Weekly assessment dimensions
ASSESSMENT_DIMENSIONS = [
    {"id": "speaking", "name": "Speaking Fluency", "weight": 0.30},
    {"id": "listening", "name": "Listening Comprehension", "weight": 0.20},
    {"id": "vocabulary", "name": "Vocabulary Recall", "weight": 0.15},
    {"id": "accent", "name": "Accent/Pronunciation", "weight": 0.15},
    {"id": "writing", "name": "Writing Sample", "weight": 0.10},
    {"id": "completion", "name": "Task Completion Rate", "weight": 0.10},
]

# Streak and gamification
STREAK_BONUS_POINTS = {7: 200, 14: 400, 30: 1000, 60: 2500, 100: 5000}
POINTS_PER_TASK = 15
POINTS_ALL_TASKS = 100  # Bonus for completing all 7 in a day
POINTS_VOICE_LOUNGE = 20
POINTS_PEER_FEEDBACK = 15
POINTS_ASSESSMENT = 50
POINTS_ADVANCEMENT = 500

# Attendance intervention thresholds (days missed)
INTERVENTION_THRESHOLDS = {
    1: "dm_reminder",
    2: "buddy_outreach",
    3: "moderator_checkin",
    5: "reengagement_conversation",
    7: "membership_pause",
}

# ============================================================
#  PHONEME SCHEDULE (Level 0, 8 weeks)
# ============================================================
PHONEME_WEEKS = {
    1: {
        "vowels": ["/iː/ (sheep)", "/ɪ/ (ship)", "/eɪ/ (say)", "/æ/ (cat)"],
        "consonants": ["/p/", "/b/", "/t/", "/d/", "/k/", "/g/"],
        "focus": "Minimal pairs: sheep/ship, cat/cut, pat/bat",
    },
    2: {
        "vowels": ["/ɑː/ (father)", "/oʊ/ (go)", "/ʊ/ (book)", "/uː/ (food)"],
        "consonants": ["/f/", "/v/", "/s/", "/z/", "/θ/", "/ð/"],
        "focus": "th-sounds (think vs. this), f/v contrast",
    },
    3: {
        "vowels": ["/ɜːr/ (bird)", "/ə/ (about)", "/ɛ/ (bed)", "/ʌ/ (cup)"],
        "consonants": ["/m/", "/n/", "/ŋ/", "/h/", "/w/", "/j/"],
        "focus": "The schwa — most common English sound",
    },
    4: {
        "vowels": ["/aɪ/ (my)", "/aʊ/ (how)", "/ɔɪ/ (boy)"],
        "consonants": ["/tʃ/", "/dʒ/", "/l/", "/r/"],
        "focus": "R vs L contrast (critical for Arabic speakers)",
    },
    5: {
        "vowels": ["/ɪr/ (here)", "/ɛr/ (hair)", "/ɑːr/ (car)"],
        "consonants": ["Review + combinations"],
        "focus": "American R (retroflex) practice",
    },
    6: {
        "vowels": ["Review all vowels in context"],
        "consonants": ["Review all consonants in context"],
        "focus": "Word-level production (not isolated sounds)",
    },
    7: {
        "vowels": ["Vowel reduction patterns (unstressed → schwa)"],
        "consonants": ["Consonant clusters: str-, spl-, thr-"],
        "focus": "Multi-syllable words with correct stress",
    },
    8: {
        "vowels": ["All 44 phonemes in sentence context"],
        "consonants": ["Final clusters: -nds, -lps, -sks"],
        "focus": "Connected speech basics",
    },
}

# ============================================================
#  VOCABULARY THEMES (Level 0, 8 weeks)
# ============================================================
VOCAB_THEMES = {
    1: "Greetings & Self",
    2: "Numbers, Time, Days",
    3: "Family & People",
    4: "Home & Daily Life",
    5: "Food & Shopping",
    6: "Places & Directions",
    7: "Actions & Descriptions",
    8: "Feelings & Opinions",
}

# ============================================================
#  SPEAKING MISSION ROTATION (7-day cycle)
# ============================================================
SPEAKING_MISSION_TYPES = {
    "Saturday": "self_introduction",
    "Sunday": "describe",
    "Monday": "list_count",
    "Tuesday": "read_aloud",
    "Wednesday": "answer_questions",
    "Thursday": "shadow_repeat",
    "Friday": "free_talk",
}
