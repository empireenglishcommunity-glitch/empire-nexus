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


# Aql (#15) Phase A6.3: the real category values design.md Section 6
# names for nour_memories.category (added inert in Phase A0.6, default
# 'general' for every pre-existing row). A category NOT in this set is
# still stored (store_memory never rejects a caller-supplied category
# outright -- 'general' remains a legitimate, intentional catch-all,
# not a typo to guard against), but get_memories_by_topic() below only
# ever filters using these four plus 'general'.
MEMORY_CATEGORIES = ("schedule", "preference", "life_event", "learning_style", "general")


def store_memory(discord_id: str, fact: str, category: str = "general"):
    """Store a key fact about a student that Nour should remember.

    Called after conversations where the student reveals something personal
    (e.g. "I work night shifts", "I have exams next week", "busy on Tuesdays").

    `category` defaults to 'general' (matching the column's own DB
    default from Phase A0.6) -- existing call sites that don't pass a
    category continue to behave exactly as before this parameter was
    added.
    """
    conn = database._connect()
    # Don't store duplicates
    existing = conn.execute(
        "SELECT id FROM nour_memories WHERE discord_id=? AND fact=?",
        (discord_id, fact),
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO nour_memories (discord_id, fact, category) VALUES (?, ?, ?)",
            (discord_id, fact, category),
        )
        conn.commit()
    conn.close()


def get_memories(discord_id: str, limit: int = 5) -> list[str]:
    """Get stored facts about a student for context building.

    UNCHANGED behavior -- returns the most recent `limit` facts
    regardless of category, exactly as before Phase A6.3. Existing
    call sites (nour_concierge.py, narrative_engine.py) keep this
    generic recency-based retrieval; get_memories_by_topic() below is
    the NEW, topic-aware alternative Phase A6.3 adds for the
    orchestrator's context assembly, not a replacement for this one.
    """
    conn = database._connect()
    rows = conn.execute(
        "SELECT fact FROM nour_memories WHERE discord_id=? ORDER BY created_at DESC LIMIT ?",
        (discord_id, limit),
    ).fetchall()
    conn.close()
    return [r["fact"] for r in rows]


# Cheap keyword hints per category -- design.md Section 6's "filtered
# by relevance to the current topic (not all facts dumped regardless
# of relevance, as today)". This is a deliberately simple substring
# match, not a second embedding call -- semantic facts are typically
# only a handful per student (5-10), so a cheap heuristic filter is
# proportionate; A1's real embedding-based retrieval is reserved for
# the knowledge base (hundreds of chunks), a genuinely different scale
# problem.
_CATEGORY_KEYWORDS = {
    "schedule": ["وقت", "موعد", "جدول", "متفرغ", "مشغول", "schedule", "time", "busy", "free"],
    "preference": ["أحب", "أفضل", "بفضل", "prefer", "like", "favorite", "أحسن"],
    "life_event": ["امتحان", "سفر", "زواج", "أولاد", "exam", "travel", "married", "kids", "سفرة"],
    "learning_style": ["أتعلم", "بتعلم", "طريقة", "learn", "style", "method"],
}


def get_memories_by_topic(discord_id: str, current_topic: str, limit: int = 5) -> list[str]:
    """design.md Section 6: semantic facts filtered by relevance to
    the CURRENT topic, not all facts dumped regardless of relevance.

    Matches `current_topic` against each category's keyword hints
    (case-insensitive substring match, same convention as
    nour_concierge.py's existing `_KB_CATEGORIES` keyword router) to
    pick which categories are relevant to THIS request, then returns
    only memories in those categories. Falls back to get_memories()'s
    unfiltered recency behavior if no category's keywords match
    anything in `current_topic` -- an irrelevant-looking topic string
    must never silently return zero memories when the student has
    real ones stored; it should degrade to "show the most recent
    facts anyway", not "show nothing".
    """
    topic_lower = (current_topic or "").lower()
    matched_categories = [
        cat for cat, keywords in _CATEGORY_KEYWORDS.items()
        if any(kw in topic_lower for kw in keywords)
    ]
    if not matched_categories:
        return get_memories(discord_id, limit=limit)

    conn = database._connect()
    placeholders = ",".join("?" for _ in matched_categories)
    rows = conn.execute(
        f"""SELECT fact FROM nour_memories WHERE discord_id=? AND category IN ({placeholders})
           ORDER BY created_at DESC LIMIT ?""",
        [discord_id, *matched_categories, limit],
    ).fetchall()
    conn.close()
    if not rows:
        # Matched a category but this student has zero memories in it
        # -- same "never silently show nothing" rule as above.
        return get_memories(discord_id, limit=limit)
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
#  AQL (#15) PHASE A6.2 — PER-STUDENT EPISODIC SUMMARY
# ============================================================

async def generate_episodic_summary(discord_id: str, days: int = 7) -> Optional[str]:
    """design.md Section 6: a compact, ONE-paragraph summary of a
    student's past conversation sessions, replacing the need to
    re-send unbounded raw nour_conversations history on every request.

    Reuses run_weekly_review()'s exact Groq-summarization PATTERN
    (same model, same simple prompt-and-parse shape, same
    never-crash-on-failure discipline) but redirected to a SINGLE
    student's own conversation history instead of an aggregate
    cross-student report -- this function's output is what
    database.store_episodic_summary() persists, this module never
    writes to nour_episodic_summaries itself (keeps the DB access
    pattern consistent with every other function in this file, which
    read/write nour_memories directly but delegate cross-table
    concerns to database.py's own dedicated functions where one
    exists).

    Returns the summary text, or None if there's nothing to summarize
    (no conversations in the window) or if Groq is unavailable --
    matches this codebase's universal "never crash, degrade instead"
    convention for every AI-call site.
    """
    if not config.GROQ_API_KEY:
        return None

    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    conn = database._connect()
    rows = conn.execute(
        """SELECT role, message FROM nour_conversations
           WHERE discord_id=? AND created_at >= ? ORDER BY created_at""",
        (discord_id, cutoff + " 00:00:00"),
    ).fetchall()
    conn.close()

    if not rows:
        return None

    conversation_text = "\n".join(
        f"{'الطالب' if r['role'] == 'student' else 'نور'}: {r['message'][:150]}"
        for r in rows
    )

    prompt = (
        f"هذه محادثة بين نور (مدربة تعلّم اللغة) وطالب على مدار الأسبوع الماضي:\n\n"
        f"{conversation_text}\n\n"
        f"اكتب ملخصًا قصيرًا (فقرة واحدة، ٣-٤ جمل فقط) بالعربية عن أهم ما "
        f"تحدث الطالب عنه أو احتاج مساعدة فيه، ليُستخدَم كذاكرة سياقية في "
        f"محادثات مستقبلية. لا تكرر تفاصيل روتينية (مثل تأكيد إتمام مهمة "
        f"يومية عادية) -- ركّز على ما هو مميز أو يستحق التذكر."
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
            "max_tokens": 150,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                summary = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                return summary if summary else None
    except Exception as e:
        logger.error(f"Aql episodic summary generation failed for {discord_id}: {e}")
        return None


async def run_weekly_episodic_summaries(bot=None) -> int:
    """Regenerates episodic summaries for every active student, once
    per week (design.md Section 6: "Regenerated weekly per active
    student"). Intended to be scheduled the same way
    run_weekly_review() already is (a Sunday @tasks.loop in bot.py) --
    `bot` is accepted but unused today, kept for call-site symmetry
    with run_weekly_review(bot) in case a future revision wants to
    post a completion notice somewhere.

    Returns the number of students a NEW summary was actually stored
    for (students with zero conversation activity in the window are
    skipped, not stored as an empty/None summary -- store_episodic_summary()
    is only ever called with real generated text).
    """
    students = database.all_active_members()
    covers_from = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    covers_to = datetime.date.today().isoformat()

    stored = 0
    for student in students:
        discord_id = student["discord_id"]
        summary = await generate_episodic_summary(discord_id, days=7)
        if summary:
            database.store_episodic_summary(discord_id, summary, covers_from, covers_to)
            stored += 1
    return stored


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
