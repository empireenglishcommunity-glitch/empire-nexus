"""Nour (نور) — Structured Onboarding Journey (Rawiya R2).

A state machine that guides each new student through their first 7 days,
teaching ONE concept at a time, waiting for confirmation before advancing.

Flow:
  JOIN → WELCOME → TASK_INTRO → FIRST_TASK → PLATFORM_INTRO →
  STREAKS_EXPLAINED → CHANNELS_TOUR → INDEPENDENT

Each step:
- Has a Nour DM message (MSA, bidi-safe)
- Waits for a trigger before advancing (e.g., student completes first task)
- Has a timeout (24h → gentle nudge)
- Can be interrupted by questions (Nour answers, then resumes)

Gated behind 'nour_journey' feature flag.
"""
import asyncio
import datetime
import json
import logging
from typing import Optional

import discord

from . import config, database

logger = logging.getLogger("empire-bot.nour.journey")

# ============================================================
#  JOURNEY STEPS (ordered)
# ============================================================

STEPS = [
    "welcome",
    "task_intro",
    "first_task",
    "platform_intro",
    "streaks_explained",
    "channels_tour",
    "independent",
]

# ============================================================
#  MSA JOURNEY MESSAGES
# ============================================================

JOURNEY_MESSAGES = {
    "welcome": (
        "✅ **تم فتح القنوات — مرحبًا بك في Empire English!**\n\n"
        "أنا نور، مدربتك الشخصية هنا. سأرافقك في رحلة تعلّم الإنجليزية خطوة بخطوة.\n\n"
        "هذا ليس درسًا عاديًا — إنه نظام يومي سيجعلك تتحدث الإنجليزية بثقة.\n\n"
        "💬 أخبرني: **ما هدفك من تعلّم الإنجليزية؟**\n"
        "(مثلًا: العمل، السفر، الدراسة، أو أي سبب آخر)"
    ),

    "task_intro": (
        "📋 **نظامك اليومي — بسيط جدًا:**\n\n"
        "كل يوم لديك **٧ مهام قصيرة** (٢٠-٤٥ دقيقة إجمالًا):\n\n"
        "1️⃣ تدريب النطق 🎯\n"
        "2️⃣ مفردات جديدة 📖\n"
        "3️⃣ محاكاة المتحدثين 🎧\n"
        "4️⃣ مهمة الكلام 🎙️\n"
        "5️⃣ تمرين الاستماع 👂\n"
        "6️⃣ تمرين الكتابة ✍️\n"
        "7️⃣ مشاركة مجتمعية 💬\n\n"
        "**لنبدأ بأسهل مهمة الآن:**\n"
        "اذهب إلى قناة `#l0-text-practice` واكتب جملة واحدة بالإنجليزية "
        "(أي جملة!)، ثم اكتب `!6` في `#bot-commands`.\n\n"
        "جرّب الآن وأخبرني عندما تنتهي! 💪"
    ),

    "first_task": (
        "🎉 **أحسنت! أنجزت مهمتك الأولى!**\n\n"
        "هذا بالضبط ما ستفعله كل يوم — أنجز المهمة ثم سجّلها.\n\n"
        "📱 **الخطوة التالية:** منصة التمرين\n\n"
        "اكتب `!link` في `#bot-commands` — سيصلك رابط خاص بك.\n"
        "افتحه في المتصفح — ستجد تمارين النطق والمحاكاة والاستماع.\n\n"
        "جرّب فتح الرابط وأخبرني ماذا ترى! 😊"
    ),

    "platform_intro": (
        "✅ **ممتاز! الآن أنت مرتبط بمنصة التمرين.**\n\n"
        "في المنصة تجد:\n"
        "• 🎯 تدريب النطق — استمع وسجّل صوتك\n"
        "• 🎧 المحاكاة — قلّد المتحدث الأصلي\n"
        "• 👂 الاستماع — اختبارات فهم\n"
        "• 📖 المفردات — بطاقات تعليمية واختبارات\n\n"
        "💡 **نصيحة:** يمكنك تثبيتها كتطبيق على هاتفك:\n"
        "افتحها في المتصفح ← اضغط المشاركة ← \"إضافة إلى الشاشة الرئيسية\"\n\n"
        "غدًا سأشرح لك نظام النقاط والسلسلة (Streak). استرح الآن! 🌙"
    ),

    "streaks_explained": (
        "🔥 **نظام السلسلة والنقاط:**\n\n"
        "**السلسلة (Streak):** عدد الأيام المتتالية التي أنجزت فيها مهمة واحدة على الأقل.\n\n"
        "**النقاط:**\n"
        "• كل مهمة = ١٥ نقطة\n"
        "• إتمام ٧/٧ = مكافأة ١٠٠ نقطة إضافية\n"
        "• سلسلة ٧ أيام = ٢٠٠ نقطة\n"
        "• سلسلة ٣٠ يومًا = ١٠٠٠ نقطة!\n\n"
        "💡 **القاعدة الذهبية:** في الأيام الصعبة، أنجز مهمة واحدة فقط "
        "للحفاظ على السلسلة. مهمة واحدة أفضل من لا شيء.\n\n"
        "اكتب `!streak` في `#bot-commands` لمعرفة سلسلتك الحالية.\n"
        "واكتب `!top` لرؤية ترتيبك بين الأعضاء! 🏆"
    ),

    "channels_tour": (
        "🗺️ **دليل القنوات المهمة:**\n\n"
        "📌 **قنوات يومية:**\n"
        "• `#l0-daily-tasks` — مهامك اليومية (تظهر الساعة ٦ صباحًا)\n"
        "• `#bot-commands` — اكتب جميع الأوامر هنا\n"
        "• `#l0-showcase` — أرسل تسجيلاتك الصوتية هنا\n\n"
        "📌 **قنوات مفيدة:**\n"
        "• `#daily-word` — كلمة جديدة كل يوم\n"
        "• `#cheat-sheets` — ملخصات أسبوعية\n"
        "• `#support` — اسأل أي سؤال وسيرد عليك الفريق\n\n"
        "📌 **للتفاعل:**\n"
        "• `#general-chat` — تحدث مع المجتمع\n"
        "• `l0-voice-1` — غرفة صوتية للممارسة\n\n"
        "💡 لا تحفظ كل شيء الآن — ستتعرف عليها تدريجيًا مع الاستخدام اليومي."
    ),

    "independent": (
        "🎓 **أنت جاهز الآن!**\n\n"
        "لقد تعلمت كل ما تحتاجه للبدء:\n"
        "✅ كيف تنجز المهام وتسجّلها\n"
        "✅ كيف تستخدم منصة التمرين\n"
        "✅ كيف تعمل النقاط والسلسلة\n"
        "✅ أين تجد ما تحتاجه\n\n"
        "**روتينك اليومي بإيجاز:**\n"
        "١. افتح `#l0-daily-tasks` صباحًا\n"
        "٢. أنجز المهام السبع\n"
        "٣. سجّل كل مهمة بأمر `!done` أو `!1`-`!7`\n"
        "٤. شاهد تقدمك: `!progress`\n\n"
        "إذا احتجت مساعدة — اكتب في `#support` وسيرد عليك الفريق.\n\n"
        "**بالتوفيق في رحلتك! 🏛️💪**"
    ),
}

# Nudge messages (sent when student doesn't advance within 24h)
NUDGE_MESSAGES = {
    "welcome": "👋 مرحبًا! هل رأيت رسالتي السابقة؟ أخبرني عن هدفك من تعلّم الإنجليزية وسأساعدك 😊",
    "task_intro": "💡 هل جرّبت كتابة جملة في `#l0-text-practice`؟ أي جملة بسيطة تكفي — مثلًا: \"Hello, I am learning English.\" ثم اكتب `!6` في `#bot-commands`.",
    "first_task": "📱 هل كتبت `!link` في `#bot-commands`؟ سيصلك رابط منصة التمرين — جرّبه!",
    "platform_intro": "🌟 كيف وجدت منصة التمرين؟ إذا واجهت أي مشكلة أخبرني وسأساعدك.",
    "streaks_explained": "🔥 هل جرّبت كتابة `!streak` أو `!top`؟ شاهد أين أنت!",
    "channels_tour": "📋 هل استكشفت القنوات؟ جرّب كتابة شيء في `#general-chat` للتعرف على المجتمع!",
}


# ============================================================
#  DATABASE HELPERS
# ============================================================

def _get_journey(discord_id: str) -> Optional[dict]:
    """Get a student's journey state."""
    conn = database._connect()
    row = conn.execute(
        "SELECT * FROM student_journey WHERE discord_id=?",
        (discord_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _create_journey(discord_id: str) -> None:
    """Start a new journey for a student."""
    conn = database._connect()
    conn.execute(
        """INSERT OR IGNORE INTO student_journey (discord_id, current_step)
           VALUES (?, 'welcome')""",
        (discord_id,),
    )
    conn.commit()
    conn.close()


def _advance_step(discord_id: str, next_step: str) -> None:
    """Move student to the next journey step."""
    conn = database._connect()
    if next_step == "independent":
        conn.execute(
            """UPDATE student_journey SET current_step=?, last_step_at=datetime('now'),
               completed_at=datetime('now') WHERE discord_id=?""",
            (next_step, discord_id),
        )
    else:
        conn.execute(
            "UPDATE student_journey SET current_step=?, last_step_at=datetime('now') WHERE discord_id=?",
            (next_step, discord_id),
        )
    conn.commit()
    conn.close()


def _get_step_data(discord_id: str) -> dict:
    """Get JSON step_data for a student's journey."""
    journey = _get_journey(discord_id)
    if not journey or not journey.get("step_data"):
        return {}
    try:
        return json.loads(journey["step_data"])
    except (json.JSONDecodeError, TypeError):
        return {}


def _set_step_data(discord_id: str, data: dict) -> None:
    """Store JSON step_data for a student's journey."""
    conn = database._connect()
    conn.execute(
        "UPDATE student_journey SET step_data=? WHERE discord_id=?",
        (json.dumps(data, ensure_ascii=False), discord_id),
    )
    conn.commit()
    conn.close()


# ============================================================
#  JOURNEY ENGINE
# ============================================================

async def start_journey(member: discord.Member) -> None:
    """Start the onboarding journey for a new member.

    Called from on_member_join (after role-gate accept).
    """
    if not database.is_feature_enabled("nour_journey"):
        return

    discord_id = str(member.id)

    # Don't restart if already has a journey
    existing = _get_journey(discord_id)
    if existing:
        return

    _create_journey(discord_id)

    # Send welcome message
    try:
        await member.send(JOURNEY_MESSAGES["welcome"])
        logger.info(f"Nour journey: started for {member.display_name}")
    except (discord.Forbidden, discord.HTTPException):
        logger.warning(f"Nour journey: can't DM {member.display_name}")


def _next_step_for_trigger(current_step: str, trigger: str) -> Optional[str]:
    """Pure step-transition table — no I/O, easy to test/verify.

    Triggers:
    - "message_received" — student sent any DM (advances welcome → task_intro)
    - "task_completed" — student completed a task (advances task_intro → first_task)
    - "link_used" — student used !link (advances first_task → platform_intro)
    - "token_validated" — practice page validated (advances platform_intro → streaks)
    - "day_passed" — daily check (time-based advances)
    """
    if current_step == "welcome" and trigger == "message_received":
        return "task_intro"
    if current_step == "task_intro" and trigger == "task_completed":
        return "first_task"
    if current_step == "first_task" and trigger == "link_used":
        return "platform_intro"
    if current_step == "platform_intro" and trigger in ("token_validated", "day_passed"):
        return "streaks_explained"
    if current_step == "streaks_explained" and trigger == "day_passed":
        return "channels_tour"
    if current_step == "channels_tour" and trigger == "day_passed":
        return "independent"
    return None


async def try_message_triggered_advance(discord_id: str, student_text: str) -> Optional[str]:
    """Rawiya R8 fix: handle journey advancement for the ONE trigger that
    fires from a plain chat reply ("message_received", i.e. the
    "welcome" step — Nour asks the student's goal, any reply advances).

    Returns the next step's message (to send as the ONLY reply) if the
    journey advanced, or None if this message shouldn't be treated as
    a journey-advancing reply (not in journey, already past "welcome",
    or journey disabled) — in which case the caller should fall through
    to the normal AI response path.

    This does NOT need a live `bot`/guild lookup (unlike the other
    triggers below, which fire from command handlers that already have
    a Member/Context object) — the reply always goes back to the exact
    `discord.Message.author`/channel that's already mid-conversation
    with Nour, handled by the caller (nour_concierge.handle_message).
    """
    if not database.is_feature_enabled("nour_journey"):
        return None

    journey = _get_journey(discord_id)
    if not journey or journey.get("completed_at"):
        return None

    current_step = journey["current_step"]
    if current_step != "welcome":
        return None  # only "welcome" advances via plain chat reply

    next_step = _next_step_for_trigger(current_step, "message_received")
    if not next_step:
        return None

    _advance_step(discord_id, next_step)
    logger.info(f"Nour journey: {discord_id} advanced welcome -> {next_step} (chat reply)")
    return JOURNEY_MESSAGES.get(next_step)


async def check_advancement(discord_id: str, trigger: str, bot) -> None:
    """Check if a trigger should advance the student's journey, and if
    so, DM them the next step's message directly.

    Used for triggers that fire from command handlers / scheduled tasks
    (task_completed, link_used, token_validated, day_passed) — these
    always have a real `bot` instance available at the call site
    (command handlers run inside the live bot process), unlike the
    message-reply case above which is handled by
    try_message_triggered_advance() instead.
    """
    if not database.is_feature_enabled("nour_journey"):
        return

    journey = _get_journey(discord_id)
    if not journey or journey.get("completed_at"):
        return

    next_step = _next_step_for_trigger(journey["current_step"], trigger)
    if not next_step or not bot:
        return

    _advance_step(discord_id, next_step)
    await _send_step_message(discord_id, next_step, bot)


async def _send_step_message(discord_id: str, step: str, bot) -> None:
    """Send the journey message for a step."""
    message = JOURNEY_MESSAGES.get(step)
    if not message:
        return

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    member = guild.get_member(int(discord_id))
    if not member:
        return

    try:
        await member.send(message)
        logger.info(f"Nour journey: sent '{step}' to {member.display_name}")
    except (discord.Forbidden, discord.HTTPException):
        pass


async def send_nudges(bot) -> None:
    """Send nudge messages to students stuck on a step for 24h+.

    Called from the proactive check loop (every 2 hours).
    """
    if not database.is_feature_enabled("nour_journey"):
        return

    conn = database._connect()
    cutoff = (datetime.datetime.now() - datetime.timedelta(hours=24)).isoformat()
    rows = conn.execute(
        """SELECT discord_id, current_step FROM student_journey
           WHERE completed_at IS NULL AND last_step_at < ?""",
        (cutoff,),
    ).fetchall()
    conn.close()

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    for row in rows:
        discord_id = row["discord_id"]
        step = row["current_step"]
        nudge = NUDGE_MESSAGES.get(step)
        if not nudge:
            continue

        member = guild.get_member(int(discord_id))
        if not member:
            continue

        # Don't nudge more than once per 24h (use step_data to track)
        step_data = _get_step_data(discord_id)
        last_nudge = step_data.get("last_nudge", "")
        today = datetime.date.today().isoformat()
        if last_nudge == today:
            continue

        try:
            await member.send(nudge)
            step_data["last_nudge"] = today
            _set_step_data(discord_id, step_data)
            logger.info(f"Nour journey: nudged {member.display_name} (stuck on '{step}')")
        except (discord.Forbidden, discord.HTTPException):
            pass


def get_journey_context(discord_id: str) -> str:
    """Get journey context for Nour's AI prompt (so she knows where the student is).

    Returns a string to append to the context in nour_concierge._build_context().
    """
    journey = _get_journey(discord_id)
    if not journey:
        return "JOURNEY: Not started (not a registered student yet)."
    if journey.get("completed_at"):
        return "JOURNEY: Completed (independent student, no longer in onboarding)."

    step = journey["current_step"]
    step_idx = STEPS.index(step) if step in STEPS else 0
    return (
        f"JOURNEY: Step {step_idx + 1}/7 — '{step}'. "
        f"This student is still in onboarding. Be extra patient and encouraging. "
        f"If they seem confused about the current step, explain it again simply."
    )
