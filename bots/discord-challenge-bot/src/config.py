"""Central configuration, loaded from environment variables (.env file)."""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_VERSION = "1.0.0"

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
CHALLENGE_CHANNEL_ID = int(os.getenv("CHALLENGE_CHANNEL_ID", "0") or "0")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DAILY_POST_HOUR = int(os.getenv("DAILY_POST_HOUR", "9") or "9")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Dubai")
START_DATE = os.getenv("START_DATE", "").strip()

# Optional: Telegram alerts for bot lifecycle events
TELEGRAM_ALERT_TOKEN = os.getenv("TELEGRAM_ALERT_TOKEN", "")
TELEGRAM_ALERT_CHAT_ID = os.getenv("TELEGRAM_ALERT_CHAT_ID", "")

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHALLENGES_PATH = os.path.join(DATA_DIR, "challenges.json")

# Persistent storage: use /app/data_persist inside Docker if it exists,
# otherwise fall back to the project root (local development).
_PERSIST_DIR = os.path.join(BASE_DIR, "data_persist")
if os.path.isdir(_PERSIST_DIR):
    DB_PATH = os.path.join(_PERSIST_DIR, "challenge.db")
    OUTPUT_DIR = os.path.join(BASE_DIR, "output")
else:
    DB_PATH = os.path.join(BASE_DIR, "challenge.db")
    OUTPUT_DIR = os.path.join(BASE_DIR, "output")

TOTAL_DAYS = 30

# Rank thresholds: (min_completed, role_name, emoji)
RANKS = [
    (30, "بطل المرونة", "👑"),
    (22, "محارب", "🥇"),
    (15, "مثابر", "🥈"),
    (1, "بدأ الرحلة", "🥉"),
]


def rank_for(completed_count: int):
    """Return (role_name, emoji) for a given number of completed challenges."""
    for threshold, name, emoji in RANKS:
        if completed_count >= threshold:
            return name, emoji
    return "مشارك جديد", "🌱"
