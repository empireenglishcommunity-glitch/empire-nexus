"""Nour (نور) — Personality Refinement Engine (Phase N5).

Handles:
- N5.1: Weekly self-review (automated prompt tuning suggestions)
- N5.2: Memory persistence (remembers facts about students)
- N5.3: Time-of-day personality adaptation
- N5.4: Cultural awareness (Ramadan, Eid, Egyptian holidays)

All automated — zero manual work from the owner.
"""
import datetime
import json
import logging
from typing import Optional

import aiohttp

from . import config, database

logger = logging.getLogger("empire-bot.nour.personality")


# ============================================================
#  N5.2 — MEMORY PERSISTENCE
# ============================================================

def store_memory(discord_id: str, fact: str):
    """Store a key fact about a student that Nour should remember.

    Called after conversations where the student reveals something personal
    (e.g. "I work night shifts", "I have exams next week", "busy on Tuesdays").
    """
    conn = database._connect()
    # Don't store duplicates
    existing = conn.execute(
        "SELECT id FROM nour_memories WHERE discord_id=? AND fact=?",
        (discord_id, fact),
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO nour_memories (discord_id, fact) VALUES (?, ?)",
            (discord_id, fact),
        )
        conn.commit()
    conn.close()


def get_memories(discord_id: str, limit: int = 5) -> list[str]:
    """Get stored facts about a student for context building."""
    conn = database._connect()
    rows = conn.execute(
        "SELECT fact FROM nour_memories WHERE discord_id=? ORDER BY created_at DESC LIMIT ?",
        (discord_id, limit),
    ).fetchall()
    conn.close()
    return [r["fact"] for r in rows]


async def extract_memories_from_conversation(discord_id: str, student_message: str):
    """Use Groq to detect if the student revealed a memorable fact.

    Runs after each conversation. If a fact is detected, stores it.
    Lightweight — only triggers on messages with personal indicators.
    """
    # Quick keyword check before calling AI (save API calls)
    personal_indicators = [
        "شغل", "work", "busy", "مشغول", "exam", "امتحان", "travel", "سفر",
        "sick", "تعبان", "married", "kids", "أولاد", "morning", "night",
        "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "monday", "يوم", "دايماً", "always", "never", "عمري", "age",
    ]
    if not any(kw in student_message.lower() for kw in personal_indicators):
        return

    if not config.GROQ_API_KEY:
        return

    prompt = (
        f"The student said: \"{student_message}\"\n\n"
        f"Does this message reveal a personal fact Nour should remember "
        f"(like their schedule, job, family situation, or preferences)?\n\n"
        f"If YES: respond with ONLY the fact in Arabic (1 short sentence).\n"
        f"If NO: respond with exactly \"NONE\"\n\n"
        f"Examples:\n"
        f"- \"I work night shifts\" → \"بيشتغل نايت شيفت\"\n"
        f"- \"مش فاهم المهمة\" → \"NONE\"\n"
        f"- \"عندي امتحانات الأسبوع الجاي\" → \"عنده امتحانات قريب\"\n"
    )

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
        }
        payload = {
            "model": config.GROQ_MODEL,
            "temperature": 0.3,
            "max_tokens": 50,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if text and text != "NONE" and len(text) < 100:
                        store_memory(discord_id, text)
                        logger.info(f"Nour memory stored for {discord_id}: {text}")
    except Exception as e:
        logger.debug(f"Memory extraction failed (non-critical): {e}")


# ============================================================
#  N5.3 — TIME-OF-DAY PERSONALITY
# ============================================================

def get_time_personality() -> str:
    """Get personality modifier based on current time (Asia/Dubai timezone).

    Returns a short instruction to append to Nour's system prompt.
    """
    try:
        from zoneinfo import ZoneInfo
        now = datetime.datetime.now(ZoneInfo("Asia/Dubai"))
    except ImportError:
        now = datetime.datetime.now()

    hour = now.hour

    if 5 <= hour < 10:
        return "الوقت صباح — كوني منشطة ومتحمسة. 'صباح الخير!' energy."
    elif 10 <= hour < 14:
        return "الوقت ضهر — كوني مركزة ومباشرة. الطالب ممكن يكون في شغله."
    elif 14 <= hour < 18:
        return "الوقت عصر — كوني balanced ومشجعة."
    elif 18 <= hour < 22:
        return "الوقت ليل — كوني هادية ومريحة. 'يلا نخلص اللي عليك وريّح'."
    else:
        return "الوقت متأخر — كوني لطيفة وقصيرة. 'ريّح نفسك وكمّل بكره'."


# ============================================================
#  N5.4 — CULTURAL AWARENESS
# ============================================================

# Major Islamic/Egyptian dates (approximate — these shift yearly with Hijri calendar)
# Updated for 2026 estimates. Should be manually checked each year.
CULTURAL_EVENTS_2026 = {
    # Ramadan 2026 (estimated: Feb 18 - Mar 19, 2026 — already passed)
    # Eid Al-Fitr 2026 (estimated: Mar 20-22, 2026 — already passed)
    # Eid Al-Adha 2026 (estimated: May 27-30, 2026 — already passed)
    # Egyptian Revolution Day
    (7, 23): "عيد الثورة 🇪🇬",
    # Sham El-Nessim (day after Easter — variable, skip for now)
    # New Year
    (1, 1): "سنة جديدة سعيدة! 🎉",
    # Prophet's Birthday (Mawlid) 2026 estimate: ~Aug 25
    (8, 25): "مولد النبي 🌙",
}

# Ramadan 2027 estimate (for future use): ~Feb 8 - Mar 9, 2027
RAMADAN_2027_START = datetime.date(2027, 2, 8)
RAMADAN_2027_END = datetime.date(2027, 3, 9)


def get_cultural_context() -> str:
    """Get cultural awareness context for today.

    Returns a string to include in Nour's context, or empty string.
    """
    today = datetime.date.today()
    month_day = (today.month, today.day)

    # Check fixed-date events
    event = CULTURAL_EVENTS_2026.get(month_day)
    if event:
        return f"اليوم مناسبة: {event} — اذكريها لو مناسب."

    # Check Ramadan 2027 (if applicable)
    if RAMADAN_2027_START <= today <= RAMADAN_2027_END:
        return "إحنا في رمضان — كوني حساسة للصيام. ماتضغطيش على المهام. 'خد وقتك، صحتك أهم'."

    # Friday — weekend in many Arab countries
    if today.weekday() == 4:  # Friday
        return "اليوم جمعة — ممكن الطلاب يكونوا فاضيين أكتر. شجعيهم يعملوا مهام إضافية."

    return ""


# ============================================================
#  N5.1 — WEEKLY SELF-REVIEW (automated)
# ============================================================

async def run_weekly_review(bot) -> Optional[str]:
    """Weekly self-review: Nour analyzes her own conversations.

    Runs every Sunday at 10 AM. Reviews the past week's conversations,
    identifies patterns (common questions, low-confidence responses),
    and sends a Telegram report to the owner with suggestions.

    Returns the report text, or None if nothing to report.
    """
    if not config.GROQ_API_KEY:
        return None
    if not config.TELEGRAM_ALERT_TOKEN or not config.TELEGRAM_ALERT_CHAT_ID:
        return None

    # Get last 7 days of conversations
    conn = database._connect()
    cutoff = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    rows = conn.execute(
        """SELECT discord_id, role, message, intent, confidence, created_at
           FROM nour_conversations WHERE created_at >= ? ORDER BY created_at""",
        (cutoff + " 00:00:00",),
    ).fetchall()
    conn.close()

    if not rows:
        return None

    conversations = [dict(r) for r in rows]
    total = len(conversations)
    student_msgs = [c for c in conversations if c["role"] == "student"]
    escalations = [c for c in conversations if c["intent"] == "escalation"]

    # Build summary for Groq analysis
    # Take a sample of student messages (max 20)
    sample = [c["message"] for c in student_msgs[:20]]
    sample_text = "\n".join(f"- {m[:100]}" for m in sample)

    prompt = (
        f"You are reviewing an AI concierge's (Nour) conversation logs for the past week.\n\n"
        f"Stats: {total} total messages, {len(student_msgs)} from students, {len(escalations)} escalations.\n\n"
        f"Sample student messages:\n{sample_text}\n\n"
        f"Based on these patterns, give 2-3 SHORT suggestions to improve Nour's responses.\n"
        f"Focus on: common questions that could be answered better, topics students ask about "
        f"most, any gaps in knowledge.\n\n"
        f"Respond in English, bullet points, max 5 lines."
    )

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
        }
        payload = {
            "model": config.GROQ_MODEL,
            "temperature": 0.5,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                suggestions = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.error(f"Weekly review analysis failed: {e}")
        return None

    if not suggestions:
        return None

    # Send report to owner via Telegram
    report = (
        f"📊 *Nour Weekly Review*\n\n"
        f"📈 Stats (last 7 days):\n"
        f"  • Total messages: {total}\n"
        f"  • Student questions: {len(student_msgs)}\n"
        f"  • Escalations: {len(escalations)}\n\n"
        f"💡 *Suggestions:*\n{suggestions}\n\n"
        f"_(Auto-generated — no action needed unless you want to tune the prompt)_"
    )

    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_ALERT_TOKEN}/sendMessage"
        payload = {
            "chat_id": config.TELEGRAM_ALERT_CHAT_ID,
            "text": report,
            "parse_mode": "Markdown",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    logger.info("Nour weekly review sent to Telegram")
                    return report
    except Exception as e:
        logger.error(f"Failed to send weekly review: {e}")

    return None
