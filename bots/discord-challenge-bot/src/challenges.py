"""Load and serve the challenge content."""
import json
from datetime import date, datetime
from . import config

_LEVEL_STARS = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐"}


def load_challenges():
    with open(config.CHALLENGES_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_challenge(day: int):
    """Return the challenge dict for a given day number (1-30), or None."""
    data = load_challenges()
    for c in data["challenges"]:
        if c["day"] == day:
            return c
    return None


def current_day(today: date = None) -> int:
    """Work out which challenge day it is based on START_DATE.

    Priority: database setting > environment variable > default (day 1).
    Returns a value clamped between 1 and TOTAL_DAYS, or 0 if finished.
    """
    # Try database first (persists across Docker restarts), then env var
    try:
        from . import database
        start_str = database.get_setting("START_DATE", "")
    except Exception:
        start_str = ""
    if not start_str:
        start_str = config.START_DATE

    if not start_str:
        return 1
    today = today or date.today()
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
    except ValueError:
        return 1
    delta = (today - start).days + 1
    if delta < 1:
        return 0  # not started yet
    if delta > config.TOTAL_DAYS:
        return 0  # finished
    return delta


def stars(level: int) -> str:
    return _LEVEL_STARS.get(level, "⭐")


def format_challenge(c: dict) -> str:
    """Format a challenge as a readable Arabic message."""
    return (
        f"🔥 **تحدّي اليوم {c['day']} / {config.TOTAL_DAYS}**\n"
        f"الأسبوع {c['week']} | المجال: {c['domain']} | الصعوبة: {stars(c['level'])}\n\n"
        f"📌 **المهمة:** {c['task']}\n"
        f"💡 *نصيحة:* {c['tip']}\n\n"
        f"عند الإنجاز اكتب: `!done {c['day']} <شعورك من 1 إلى 10>`\n"
        f"مثال: `!done {c['day']} 8`"
    )
