"""Nour (نور) — Autonomous Student Concierge.

AI-powered learning coach that handles student questions, provides
support, and proactively engages students — all while feeling like
a real, warm human team member.

Nour speaks Egyptian Arabic (عامية), knows each student personally,
responds in seconds, and only escalates truly complex issues.

AI Provider Strategy:
  1. Groq (Llama 3.3 70B) — PRIMARY (fast, reliable, good Arabic)
  2. Gemini — FALLBACK (if Groq fails)
  3. Template responses — LAST RESORT (never silence)

Gated behind 'nour_concierge' feature flag.
"""
import asyncio
import json
import logging
import random
from pathlib import Path
from typing import Optional

import aiohttp
import discord

from . import config, database

logger = logging.getLogger("empire-bot.nour")

# ============================================================
#  CONFIGURATION
# ============================================================

# Nour's personality prompt — the core of how she behaves
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

# Escalation trigger keywords
ESCALATION_KEYWORDS = [
    "payment", "refund", "cancel", "money", "فلوس", "اشتراك", "الغاء",
    "إلغاء", "محمود", "mahmoud", "owner", "المدير", "مسؤول",
]

# Maximum response tokens
MAX_RESPONSE_TOKENS = 300


# ============================================================
#  MAIN HANDLER
# ============================================================

async def handle_message(message: discord.Message) -> Optional[str]:
    """Main entry point for Nour. Routes student messages to the AI.

    Called for:
    - DMs to the bot that aren't commands (don't start with !)
    - Messages in #ask-nour channel

    Returns response text or None if shouldn't respond.
    """
    if not database.is_feature_enabled("nour_concierge"):
        return None

    # Don't respond to bots or empty messages
    if message.author.bot or not message.content.strip():
        return None

    discord_id = str(message.author.id)
    text = message.content.strip()

    # Check if registered
    member = database.get_member(discord_id)
    if not member:
        return None  # Only help registered students

    # Rawiya R8 fix: if the student is on a journey step that advances
    # purely by replying (currently only "welcome" — Nour asks their
    # goal, any reply advances), handle it here directly and SKIP the
    # general AI call entirely. Previously the AI always generated a
    # reply first (regardless of journey state) AND a separate
    # fire-and-forget background task tried to advance the journey —
    # but that background task was called with bot=None, so it never
    # actually advanced, leaving every student stuck on "welcome"
    # forever while the AI kept improvising with stale step-1 context
    # (confirmed live: this produced the exact repeating/confused
    # behavior). Fixing bot=None alone would still send TWO replies
    # per student message (an AI one + the scripted step message) —
    # this short-circuit keeps it to exactly one clean reply per turn.
    from . import nour_journey
    journey_reply = await nour_journey.try_message_triggered_advance(discord_id, text)
    if journey_reply:
        _store_conversation(discord_id, "student", text)
        _store_conversation(discord_id, "nour", journey_reply)
        return journey_reply

    # Build context
    context = _build_context(discord_id, text, member)

    # Check for escalation triggers BEFORE generating response
    if _should_escalate_immediately(text):
        _store_conversation(discord_id, "student", text, intent="escalation")
        response = "دعني أسأل الفريق بخصوص هذا الأمر وأرجع إليك في أقرب وقت 😊"
        _store_conversation(discord_id, "nour", response, intent="escalation")
        # N3: send Telegram alert to owner
        from . import nour_escalation
        name = member.get("discord_name", "").split("#")[0]
        await nour_escalation.escalate_to_owner(discord_id, name, text)
        logger.info(f"Nour: escalated message from {discord_id}: {text[:50]}")
        return response

    # Generate response via Gemini
    response = await _generate_response(context, text, member)

    if not response:
        return None

    # Store conversation
    _store_conversation(discord_id, "student", text)
    _store_conversation(discord_id, "nour", response)

    # N5.2: Extract and store memories from student's message (async, non-blocking)
    import asyncio
    from . import nour_personality
    asyncio.create_task(nour_personality.extract_memories_from_conversation(discord_id, text))

    return response


async def handle_with_human_touch(message: discord.Message):
    """Handle message with human-like timing (typing indicator + delay).

    This is the function bot.py calls — it wraps handle_message with
    the human touch simulation.
    """
    response = await handle_message(message)
    if not response:
        return

    channel = message.channel

    # Human touch: typing indicator + proportional delay
    delay = _calculate_delay(response)
    async with channel.typing():
        await asyncio.sleep(delay)

    # Rawiya R8: Use webhook in #ask-nour for Nour identity (custom name + avatar)
    # In DMs, fall back to normal send (can't use webhooks in DMs)
    sent_via_webhook = False
    if hasattr(channel, 'name') and channel.name == "ask-nour":
        sent_via_webhook = await _send_as_nour(channel, response)

    if not sent_via_webhook:
        # Occasionally split long responses into 2 messages (feels more human)
        if len(response) > 200 and random.random() < 0.2:
            # Find a good split point
            split_point = response.find("\n", len(response) // 3)
            if split_point > 0:
                await channel.send(response[:split_point])
                await asyncio.sleep(random.uniform(1.5, 3.0))
                await channel.send(response[split_point:].strip())
                return

        await channel.send(response)


# Nour's avatar URL (a warm, professional avatar)
# Using a free, stable image URL. Can be changed to a custom-uploaded one later.
NOUR_AVATAR_URL = "https://cdn.discordapp.com/embed/avatars/0.png"
NOUR_DISPLAY_NAME = "نور | Nour"

# Cache the webhook per channel to avoid creating duplicates
_nour_webhook_cache: dict[int, discord.Webhook] = {}


async def _send_as_nour(channel: discord.TextChannel, content: str) -> bool:
    """Send a message via webhook with Nour's custom name and avatar.

    Returns True if sent successfully, False if webhook unavailable
    (falls back to normal bot send).
    """
    try:
        webhook = _nour_webhook_cache.get(channel.id)

        if not webhook:
            # Find existing Nour webhook or create one
            webhooks = await channel.webhooks()
            webhook = next((w for w in webhooks if w.name == NOUR_DISPLAY_NAME), None)

            if not webhook:
                webhook = await channel.create_webhook(
                    name=NOUR_DISPLAY_NAME,
                    reason="Rawiya R8: Nour identity webhook for #ask-nour",
                )

            _nour_webhook_cache[channel.id] = webhook

        await webhook.send(
            content=content,
            username=NOUR_DISPLAY_NAME,
            avatar_url=NOUR_AVATAR_URL,
        )
        return True
    except (discord.Forbidden, discord.HTTPException, Exception) as e:
        logger.warning(f"Nour webhook send failed, falling back to bot send: {e}")
        return False


# ============================================================
#  CONTEXT BUILDING
# ============================================================

def _build_context(discord_id: str, text: str, member: dict) -> str:
    """Build rich context string for Gemini prompt."""
    from . import nour_personality

    # Student data
    level = member.get("level", "L0")
    streak = member.get("current_streak", 0)
    points = member.get("total_points", 0)
    name = member.get("discord_name", "")
    week = database.member_week_number(discord_id)

    # Today's tasks
    tasks_today = database.tasks_completed_today(discord_id)
    tasks_done = len(tasks_today)

    # Pronunciation average
    pron_avg = database.get_pronunciation_average(discord_id)

    # Recent conversation
    history = _get_recent_conversation(discord_id, limit=5)
    history_text = ""
    if history:
        history_text = "\n".join([
            f"{'Student' if h['role'] == 'student' else 'Nour'}: {h['message']}"
            for h in history
        ])

    # N5.2: Student memories (persistent facts)
    memories = nour_personality.get_memories(discord_id)
    memories_text = "\n".join(f"- {m}" for m in memories) if memories else "(no stored memories yet)"

    # N5.3: Time-of-day personality
    time_personality = nour_personality.get_time_personality()

    # N5.4: Cultural context
    cultural_context = nour_personality.get_cultural_context()

    # Masar D033 fix: tell the AI how to address this student in
    # Egyptian Arabic (gendered second-person grammar) -- previously
    # nothing did this anywhere in this codebase, so the AI silently
    # guessed a gender every single time. Applies here too, not just
    # to narrative_engine's new functions, since regular chat has the
    # identical exposure.
    gender_instruction = nour_personality.get_gender_instruction(discord_id)

    # Knowledge base (truncated to fit token limit)
    knowledge = _load_knowledge_base(text)

    # Rawiya R2: journey context (so Nour knows where the student is in onboarding)
    from . import nour_journey
    journey_context = nour_journey.get_journey_context(discord_id)

    context = f"""STUDENT DATA:
- Name: {name}
- Level: {level}, Week: {week}
- Streak: {streak} days
- Points: {points}
- Tasks today: {tasks_done}/7 done ({', '.join(tasks_today) if tasks_today else 'none yet'})
- Pronunciation average: {pron_avg:.0f}% (last 7 days)

{journey_context}

ADDRESSING THIS STUDENT: {gender_instruction}

MEMORIES (things you know about this student):
{memories_text}

TIME/CULTURAL CONTEXT:
{time_personality}
{cultural_context}

RECENT CONVERSATION:
{history_text or '(first message)'}

KNOWLEDGE BASE (use this to answer questions):
{knowledge}
"""
    return context


# ============================================================
#  RESPONSE GENERATION (Groq primary → Gemini fallback → template)
# ============================================================

async def _call_groq_chat(prompt: str, temperature: float = 0.7) -> Optional[str]:
    """Call Groq API directly for Nour responses. Fast and reliable."""
    if not config.GROQ_API_KEY:
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
    }
    payload = {
        "model": config.GROQ_MODEL,  # llama-3.3-70b-versatile
        "temperature": temperature,
        "max_tokens": MAX_RESPONSE_TOKENS,
        "messages": [
            {"role": "system", "content": NOUR_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.warning(f"Groq API error for Nour: {resp.status}")
                    # Markaz M5.2: track Groq failures for alerting
                    from . import ops_monitoring
                    import asyncio
                    asyncio.create_task(ops_monitoring.track_groq_failure())
                    return None
                data = await resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return text.strip() if text else None
    except Exception as e:
        logger.error(f"Groq call failed for Nour: {e}")
        # Markaz M5.2: track Groq failures for alerting
        from . import ops_monitoring
        import asyncio
        asyncio.create_task(ops_monitoring.track_groq_failure())
        return None


async def _call_gemini_chat(prompt: str, temperature: float = 0.7) -> Optional[str]:
    """Fallback: call Gemini for Nour responses."""
    if not config.GEMINI_API_KEY:
        return None

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": f"{NOUR_SYSTEM_PROMPT}\n\n{prompt}"}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": MAX_RESPONSE_TOKENS},
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    logger.warning(f"Gemini API error for Nour: {resp.status}")
                    return None
                data = await resp.json()
                text = (data.get("candidates", [{}])[0]
                        .get("content", {}).get("parts", [{}])[0].get("text", ""))
                return text.strip() if text else None
    except Exception as e:
        logger.error(f"Gemini call failed for Nour: {e}")
        return None


# Template fallback responses (never silence)
_TEMPLATE_RESPONSES = [
    "حسنًا، دعني أتحقق من هذا الأمر وأرجع إليك 😊",
    "سؤال جيد! دعني أسأل الفريق وأعود إليك بإجابة كاملة 👍",
    "فهمتك 👍 دعني أتأكد من المعلومة وأرجع إليك",
    "سأرد عليك في أقرب وقت 😊 إذا احتجت شيئًا آخر أخبرني",
]


async def _generate_response(context: str, student_message: str, member: dict) -> Optional[str]:
    """Generate Nour's response. Groq → Gemini → Template. Never returns None."""
    name = member.get("discord_name", "").split("#")[0]

    full_prompt = (
        f"CONTEXT:\n{context}\n\n"
        f"The student \"{name}\" just said: \"{student_message}\"\n\n"
        f"Respond as Nour (2-5 sentences max, Modern Standard Arabic / الفصحى الحديثة, warm and helpful):"
    )

    # Try 1: Groq (fast, reliable)
    response = await _call_groq_chat(full_prompt)
    if response:
        return _clean_response(response)

    # Try 2: Gemini (fallback)
    logger.info("Nour: Groq failed, trying Gemini fallback")
    response = await _call_gemini_chat(full_prompt)
    if response:
        return _clean_response(response)

    # Try 3: Template (never silence)
    logger.warning("Nour: both AI providers failed, using template response")
    return random.choice(_TEMPLATE_RESPONSES)


def _clean_response(response: str) -> str:
    """Clean up AI response artifacts."""
    response = response.strip().strip('"').strip("'")
    # Remove any "Nour:" prefix the model might add
    if response.lower().startswith("nour:"):
        response = response[5:].strip()
    # Remove markdown code blocks if present
    if response.startswith("```"):
        response = response.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return response


# ============================================================
#  ESCALATION
# ============================================================

def _should_escalate_immediately(text: str) -> bool:
    """Check if message should be escalated to owner immediately."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in ESCALATION_KEYWORDS)


# ============================================================
#  HUMAN TOUCH
# ============================================================

def _calculate_delay(response: str) -> float:
    """Calculate a human-like typing delay based on response length.

    Longer responses = longer "typing" time. Range: 3-12 seconds.
    Adds slight randomness so it never feels mechanical.
    """
    # Base: ~1 second per 30 characters (average typing speed)
    base_delay = len(response) / 30
    # Clamp between 3 and 12 seconds
    delay = max(3.0, min(12.0, base_delay))
    # Add ±20% randomness
    delay *= random.uniform(0.8, 1.2)
    return delay


# ============================================================
#  KNOWLEDGE BASE
# ============================================================


# Knowledge base directory (Rawiya R1: multi-file categorized KB)
KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "nour_knowledge"

# Category keywords for smart KB routing
_KB_CATEGORIES = {
    "daily_tasks.md": ["مهمة", "مهام", "task", "done", "تم", "accent", "vocab", "shadow", "speaking", "listening", "writing", "community", "نطق", "مفردات", "محاكاة", "كلام", "استماع", "كتابة", "مجتمع"],
    "channels.md": ["قناة", "قنوات", "channel", "showcase", "bot-commands", "ask-nour", "daily-tasks", "text-practice", "general-chat", "questions"],
    "commands.md": ["أمر", "أوامر", "command", "!done", "!progress", "!streak", "!level", "!help", "!link", "!join", "!top", "تقدم", "سلسلة", "مستوى", "مساعدة", "ربط", "انضم"],
    "practice_platform.md": ["منصة", "platform", "practice", "تمرين", "link", "ربط", "تطبيق", "app", "موقع", "website"],
    "troubleshooting.md": ["مشكلة", "problem", "لا يعمل", "خطأ", "error", "لا أستطيع", "can't", "broken", "stuck", "عالق"],
    "mobile_guide.md": ["هاتف", "موبايل", "mobile", "phone", "تطبيق", "app", "discord", "تحميل", "download", "تسجيل صوت"],
    "study_strategies.md": ["حافز", "motivation", "عادة", "habit", "كسلان", "lazy", "متى", "when", "أفضل وقت", "best time", "نصيحة", "tip", "استراتيجية"],
    "levels_points.md": ["مستوى", "level", "نقاط", "points", "سلسلة", "streak", "ترقية", "advance", "اختبار", "exam", "assess", "تقييم", "ترتيب", "leaderboard"],
    "faq.md": [],  # fallback — used when no specific category matches
    "system_overview.md": ["نظام", "system", "empire", "ما هو", "what is", "فلسفة", "philosophy", "كيف يعمل", "how"],
}

# Cache for loaded KB files
_kb_cache: dict[str, str] = {}


def _load_knowledge_base(student_message: str = "") -> str:
    """Load relevant knowledge base section(s) based on student's question.

    Rawiya R1: smart category routing — only includes the relevant
    section(s) per query, not the entire KB. Token-efficient.
    """
    # Determine which files are relevant to this question
    message_lower = student_message.lower()
    relevant_files = []

    for filename, keywords in _KB_CATEGORIES.items():
        if any(kw in message_lower for kw in keywords):
            relevant_files.append(filename)

    # If no specific match, use FAQ + system overview as defaults
    if not relevant_files:
        relevant_files = ["faq.md", "system_overview.md"]

    # Limit to 2 files max to stay within token budget
    relevant_files = relevant_files[:2]

    # Load and concatenate
    parts = []
    for filename in relevant_files:
        content = _load_kb_file(filename)
        if content:
            parts.append(content)

    return "\n\n---\n\n".join(parts) if parts else "Knowledge base unavailable."


def _load_kb_file(filename: str) -> str:
    """Load a single KB file (cached after first read)."""
    if filename in _kb_cache:
        return _kb_cache[filename]

    filepath = KNOWLEDGE_DIR / filename
    try:
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            # Truncate each file to ~2000 chars to stay within context limits
            _kb_cache[filename] = content[:2000]
            return _kb_cache[filename]
    except Exception as e:
        logger.error(f"Failed to load KB file {filename}: {e}")

    return ""


# ============================================================
#  CONVERSATION MEMORY
# ============================================================

def _store_conversation(discord_id: str, role: str, message: str,
                        intent: str = "", confidence: float = 1.0):
    """Store a conversation message for context memory."""
    conn = database._connect()
    conn.execute(
        """INSERT INTO nour_conversations (discord_id, role, message, intent, confidence)
           VALUES (?, ?, ?, ?, ?)""",
        (discord_id, role, message[:500], intent, confidence),
    )
    conn.commit()
    conn.close()


def _get_recent_conversation(discord_id: str, limit: int = 5) -> list[dict]:
    """Get last N conversation messages for context."""
    conn = database._connect()
    rows = conn.execute(
        """SELECT role, message, created_at FROM nour_conversations
           WHERE discord_id=? ORDER BY created_at DESC LIMIT ?""",
        (discord_id, limit),
    ).fetchall()
    conn.close()
    # Reverse so oldest is first (chronological order)
    return [dict(r) for r in reversed(rows)]
