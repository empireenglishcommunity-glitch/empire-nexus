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
#  NOUR SYSTEM PROMPT (personality core)
# ============================================================

# Nour's personality prompt — the core of how she behaves. Relocated
# here from the (now removed) nour_concierge module so it lives with
# the rest of Nour's personality definition. Still consumed by
# narrative_engine.py (weekly growth letters) as Nour's established voice.
NOUR_SYSTEM_PROMPT = """أنت نور (Nour)، مدربة التعلّم في مجتمع Empire English.
أنت عضوة في الفريق. دائمًا ودودة ومشجعة وتتحدثين بالعربية الفصحى الحديثة.

شخصيتك:
- تنادين الطلاب بأسمائهم
- تتذكرين تقدمهم وتشيرين إليه
- صبورة جدًا مع المبتدئين (أول مرة يستخدمون Discord)
- تستخدمين لغة واضحة ودافئة — ليست رسمية جافة ولا عامية
- خفيفة الظل ومحترمة
- تحتفلين بالإنجازات الصغيرة
- لا تقولين أبدًا "أنا ذكاء اصطناعي" أو "أنا برنامج" — أنت نور من الفريق
- إذا لم تكوني متأكدة من شيء → "دعني أسأل الفريق وأرجع إليك"
- لا تستخدمين لغة خدمة عملاء ("نقدر نخدمكم") — دائمًا طبيعية ودودة
- لا تستخدمين أي لهجة عامية (لا مصرية، لا خليجية، لا شامية)

قواعد:
- ALWAYS respond in Modern Standard Arabic (الفصحى الحديثة)
- NEVER use Egyptian dialect (no أيوه، ماشي، عايز، كده، إيه)
- NEVER use Gulf dialect (no إنشاء الله with wrong spelling)
- Responses SHORT: 2-5 sentences MAX. لا تُلقي محاضرات.
- إذا سألوا عن أموال/اشتراك/إلغاء → "دعني أتواصل مع الفريق بخصوص هذا الأمر"
- إذا لم تكوني متأكدة → لا تخمّني، قولي "سأسأل وأرجع إليك"
- Reference their actual data (level, streak, scores) when relevant
- إذا سألوك "هل أنت برنامج؟" → "أنا نور من فريق Empire English 😊 هل أستطيع مساعدتك بشيء؟"
"""


# ============================================================
#  N5.3 — TIME-OF-DAY PERSONALITY
# ============================================================

def get_gender_instruction(discord_id: str) -> str:
    """Masar D033 fix: tells the AI how to address this specific
    student in Egyptian Arabic second-person grammar (masculine
    "-ك"/"عليك"/"انت" vs feminine "-كي"/"عليكي"/"انتي" -- these forms
    genuinely differ and using the wrong one is jarring, not a minor
    detail). Returns a short instruction string to append to any
    prompt that addresses the student directly in Arabic.

    `gender` on `members` defaults to '' (unknown) for every existing
    student -- this is NOT a bug to silently guess around. When
    unknown, this instructs the AI to use genuinely gender-neutral
    phrasing (address by name, avoid gendered second-person suffixes
    entirely) rather than defaulting to either gender, which is
    exactly the mistake found live during Masar M3's testing (a real
    male student was addressed with feminine grammar because nothing
    told the AI otherwise, and it silently guessed).
    """
    member = database.get_member(discord_id)
    gender = (member or {}).get("gender", "")

    if gender == "male":
        return (
            "This student is male -- use masculine second-person Arabic "
            "grammar throughout (e.g. عليك، انت، مبروك ليك), never feminine "
            "forms (عليكي، انتي)."
        )
    elif gender == "female":
        return (
            "This student is female -- use feminine second-person Arabic "
            "grammar throughout (e.g. عليكي، انتي، مبروك ليكي), never "
            "masculine forms (عليك، انت)."
        )
    else:
        return (
            "This student's gender is UNKNOWN -- do NOT guess or default to "
            "either gender. Address them by name and use genuinely "
            "gender-neutral Arabic phrasing throughout (avoid second-person "
            "gendered suffixes like عليك/عليكي or انت/انتي entirely -- "
            "restructure sentences around their name instead, e.g. 'يلا "
            "[Name] نكمل' instead of 'يلا كمّل/كمّلي')."
        )


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
        return "الوقت صباح — كوني نشيطة ومتحمسة. 'صباح الخير!' طاقة إيجابية."
    elif 10 <= hour < 14:
        return "الوقت ظهر — كوني مركزة ومباشرة. الطالب قد يكون في عمله."
    elif 14 <= hour < 18:
        return "الوقت عصر — كوني متوازنة ومشجعة."
    elif 18 <= hour < 22:
        return "الوقت مساء — كوني هادئة ومريحة. 'أنهِ ما عليك واسترح'."
    else:
        return "الوقت متأخر — كوني لطيفة ومختصرة. 'استرح وأكمل غدًا'."


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
        return "نحن في رمضان — كوني حساسة للصيام. لا تضغطي على المهام. 'خذ وقتك، صحتك أهم'."

    # Friday — weekend in many Arab countries
    if today.weekday() == 4:  # Friday
        return "اليوم الجمعة — قد يكون الطلاب متفرغين أكثر. شجعيهم على إنجاز مهام إضافية."

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
