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
BOT_VERSION = "1.0.0"
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

# ============================================================
#  AI PROVIDERS
# ============================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")

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

# Daily task structure (7 tasks in fixed order — same every level)
DAILY_TASKS = [
    {"id": "accent", "name": "Accent/Phoneme Drill", "name_ar": "تدريب النطق", "emoji": "🎯"},
    {"id": "vocab", "name": "Vocabulary Acquisition", "name_ar": "مفردات جديدة", "emoji": "📖"},
    {"id": "shadow", "name": "Shadowing Practice", "name_ar": "تمرين المحاكاة", "emoji": "🎧"},
    {"id": "speaking", "name": "Speaking Mission", "name_ar": "مهمة الكلام", "emoji": "🎙️"},
    {"id": "listening", "name": "Listening Exercise", "name_ar": "تمرين الاستماع", "emoji": "👂"},
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
