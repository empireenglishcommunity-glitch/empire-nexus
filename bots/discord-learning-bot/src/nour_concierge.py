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
NOUR_SYSTEM_PROMPT = """أنت نور (Nour)، كوتش تعلّم في Empire English Community.
أنت بنت/ولد (gender-neutral) من الفريق. دايماً حنونة ومشجعة وبتتكلمي عامية مصرية.

شخصيتك:
- بتنادي الطلاب بأسمائهم
- بتفتكري تقدمهم وبتشيري ليه
- صبورة جداً مع المبتدئين (أول مرة يستخدموا Discord)
- بتستخدمي سلانج مصري طبيعي (يا باشا، تمام، أيوه، ماشي)
- خفيفة الظل بس محترمة
- بتحتفلي بالإنجازات الصغيرة
- مش بتقولي أبداً "أنا AI" أو "أنا بوت" — أنت نور من الفريق
- لو مش متأكدة من حاجة → "خليني أسأل الفريق وأرجعلك"
- مش بتستخدمي لغة رسمية ("نقدر خدمتكم"، "شكراً لتواصلكم") — دايماً طبيعية

قواعد:
- ALWAYS respond in Egyptian Arabic (عامية مصرية)
- Responses SHORT: 2-5 sentences MAX. لا تحاضري.
- لو سألوا عن فلوس/اشتراك/إلغاء → "خليني أرجع للفريق في الموضوع ده"
- لو مش متأكدة → ماتخمنيش، قولي "هسأل وأرجعلك"
- Reference their actual data (level, streak, scores) when relevant
- لو سألوك "انتي بوت؟" → "أنا نور من فريق Empire English 😊 في حاجة أقدر أساعدك فيها؟"
"""

# Escalation trigger keywords
ESCALATION_KEYWORDS = [
    "payment", "refund", "cancel", "money", "فلوس", "اشتراك", "الغاء",
    "إلغاء", "محمود", "mahmoud", "owner", "المدير", "مسؤول",
]

# Maximum response tokens
MAX_RESPONSE_TOKENS = 300

# Knowledge base path
KNOWLEDGE_BASE_PATH = Path(__file__).resolve().parent.parent / "data" / "nour_knowledge.md"


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

    # Build context
    context = _build_context(discord_id, text, member)

    # Check for escalation triggers BEFORE generating response
    if _should_escalate_immediately(text):
        _store_conversation(discord_id, "student", text, intent="escalation")
        response = "خليني أسأل الفريق في الموضوع ده وأرجعلك في أقرب وقت 😊"
        _store_conversation(discord_id, "nour", response, intent="escalation")
        # TODO: Phase N3 — send Telegram alert to owner
        logger.info(f"Nour: escalated message from {discord_id}: {text[:50]}")
        return response

    # Generate response via Gemini
    response = await _generate_response(context, text, member)

    if not response:
        return None

    # Store conversation
    _store_conversation(discord_id, "student", text)
    _store_conversation(discord_id, "nour", response)

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


# ============================================================
#  CONTEXT BUILDING
# ============================================================

def _build_context(discord_id: str, text: str, member: dict) -> str:
    """Build rich context string for Gemini prompt."""
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

    # Knowledge base (truncated to fit token limit)
    knowledge = _load_knowledge_base()

    context = f"""STUDENT DATA:
- Name: {name}
- Level: {level}, Week: {week}
- Streak: {streak} days
- Points: {points}
- Tasks today: {tasks_done}/7 done ({', '.join(tasks_today) if tasks_today else 'none yet'})
- Pronunciation average: {pron_avg:.0f}% (last 7 days)

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
                    return None
                data = await resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return text.strip() if text else None
    except Exception as e:
        logger.error(f"Groq call failed for Nour: {e}")
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
    "تمام، خليني أشوف الموضوع ده وأرجعلك 😊",
    "سؤال حلو! خليني أسأل الفريق وأرجعلك بإجابة كاملة 👍",
    "ماشي، هرد عليك في أقرب وقت 😊 لو محتاج حاجة تانية قولي",
    "فاهمك 👍 خليني أتأكد من المعلومة وأرجعلك",
]


async def _generate_response(context: str, student_message: str, member: dict) -> Optional[str]:
    """Generate Nour's response. Groq → Gemini → Template. Never returns None."""
    name = member.get("discord_name", "").split("#")[0]

    full_prompt = (
        f"CONTEXT:\n{context}\n\n"
        f"The student \"{name}\" just said: \"{student_message}\"\n\n"
        f"Respond as Nour (2-5 sentences max, Egyptian Arabic, warm and helpful):"
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

_knowledge_cache: Optional[str] = None


def _load_knowledge_base() -> str:
    """Load the knowledge base markdown file (cached after first read)."""
    global _knowledge_cache
    if _knowledge_cache is not None:
        return _knowledge_cache

    try:
        if KNOWLEDGE_BASE_PATH.exists():
            content = KNOWLEDGE_BASE_PATH.read_text(encoding="utf-8")
            # Truncate to ~3000 chars to fit in Gemini context
            _knowledge_cache = content[:3000]
            return _knowledge_cache
    except Exception as e:
        logger.error(f"Failed to load knowledge base: {e}")

    _knowledge_cache = "Knowledge base unavailable."
    return _knowledge_cache


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
