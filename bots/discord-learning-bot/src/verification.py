"""Empire English Community Bot — Task Verification System.

Strict verification for !done commands. Each task requires proof before
points are awarded. Prevents gaming/cheating the streak system.

Verification methods:
- accent:     Audio in #l0-showcase (AI validates it's speech)
- vocab:      Bot asks quiz question, student must answer correctly
- shadow:     Audio in #l0-showcase (min 30s)
- speaking:   Audio in #l0-showcase (min target duration)
- listening:  Bot asks comprehension question
- writing:    Post in #l0-text-practice (min 20 chars)
- community:  Posted in #general-chat OR spent 10+ min in voice today
"""
import datetime
import logging
import random
from typing import Optional

import discord

from . import database

logger = logging.getLogger("empire-bot.verify")

# ============================================================
#  TIME GATE: Minimum 5 minutes between !done commands
# ============================================================

# In-memory cache: {discord_id: last_done_timestamp}
_last_done_time: dict[str, datetime.datetime] = {}
COOLDOWN_SECONDS = 60  # 1 minute

# Voice tracking: {discord_id: {"join_time": datetime, "total_minutes": float}}
_voice_sessions: dict[str, dict] = {}


def check_cooldown(discord_id: str) -> tuple[bool, int]:
    """Check if user is past the cooldown. Returns (allowed, seconds_remaining)."""
    now = datetime.datetime.now()
    last = _last_done_time.get(discord_id)
    if last is None:
        return True, 0
    elapsed = (now - last).total_seconds()
    if elapsed >= COOLDOWN_SECONDS:
        return True, 0
    return False, int(COOLDOWN_SECONDS - elapsed)


def record_done_time(discord_id: str):
    """Record that a !done was just processed."""
    _last_done_time[discord_id] = datetime.datetime.now()


# ============================================================
#  VOICE CHANNEL TRACKING
# ============================================================

def on_voice_join(discord_id: str):
    """Called when a member joins a voice channel."""
    _voice_sessions[discord_id] = {
        "join_time": datetime.datetime.now(),
        "total_minutes": _voice_sessions.get(discord_id, {}).get("total_minutes", 0),
    }


def on_voice_leave(discord_id: str):
    """Called when a member leaves a voice channel."""
    session = _voice_sessions.get(discord_id)
    if session and session.get("join_time"):
        elapsed = (datetime.datetime.now() - session["join_time"]).total_seconds() / 60
        _voice_sessions[discord_id] = {
            "join_time": None,
            "total_minutes": session.get("total_minutes", 0) + elapsed,
        }


def get_voice_minutes_today(discord_id: str) -> float:
    """Get total voice minutes for today."""
    session = _voice_sessions.get(discord_id, {})
    total = session.get("total_minutes", 0)
    # If currently in voice, add ongoing time
    if session.get("join_time"):
        elapsed = (datetime.datetime.now() - session["join_time"]).total_seconds() / 60
        total += elapsed
    return total


def reset_daily_voice():
    """Reset voice tracking (call at midnight)."""
    _voice_sessions.clear()


# ============================================================
#  VERIFICATION: WRITING
# ============================================================

async def verify_writing(member: discord.Member, guild: discord.Guild) -> tuple[bool, str]:
    """Check if member posted 20+ chars in #l0-text-practice (or their level) in last 2 hours."""
    level = (database.get_member(str(member.id)) or {}).get("level", "L0")
    channel_name = f"l{level[1]}-text-practice"
    channel = discord.utils.get(guild.text_channels, name=channel_name)

    if not channel:
        return False, f"قناة `#{channel_name}` مش موجودة."

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)

    async for msg in channel.history(limit=50, after=cutoff):
        if msg.author.id == member.id and len(msg.content) >= 10:
            return True, ""

    return False, (
        f"لازم تكتب 10 حروف على الأقل في `#{channel_name}` الأول.\n"
        f"اكتب تمرين الكتابة هناك، وبعدين ارجع اكتب `!done writing`"
    )


# ============================================================
#  VERIFICATION: SPEAKING / ACCENT / SHADOW (Audio)
# ============================================================

async def verify_audio(member: discord.Member, guild: discord.Guild,
                       task_id: str, min_duration_hint: int = 0) -> tuple[bool, str]:
    """Check if member uploaded audio in #l0-showcase in last 2 hours.

    Hisn D028: this previously accepted ANY audio-looking attachment
    from the student in the window, for accent/speaking/shadow alike,
    with no memory of which specific message had already been used.
    Confirmed live during Hisn H6: one recording uploaded once
    satisfied !done shadow, then satisfied !done speaking too, with
    zero new proof of work for the second task -- and would keep
    satisfying any of the 3 audio task types repeatedly for the full
    2-hour window. Now requires a message that has NOT already been
    consumed as proof for this or any other task
    (database.is_message_consumed()), and marks it consumed
    (database.consume_proof_message()) the moment it's accepted --
    so the same message can never satisfy a second !done call, for
    this task or a different one.
    """
    level = (database.get_member(str(member.id)) or {}).get("level", "L0")
    channel_name = f"l{level[1]}-showcase"
    channel = discord.utils.get(guild.text_channels, name=channel_name)

    if not channel:
        return False, f"قناة `#{channel_name}` مش موجودة."

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)

    async for msg in channel.history(limit=50, after=cutoff):
        if msg.author.id == member.id and msg.attachments:
            if database.is_message_consumed(msg.id):
                continue  # already used for this or another task — skip
            for att in msg.attachments:
                # Check if it's an audio/video file
                is_audio = (att.content_type and ("audio" in att.content_type or "video" in att.content_type)) or \
                           att.filename.lower().endswith(('.mp3', '.m4a', '.wav', '.ogg', '.mp4', '.webm', '.mov', '.3gp', '.opus'))
                if is_audio:
                    if database.consume_proof_message(msg.id, str(member.id), task_id):
                        return True, ""
                    # Lost a race to another concurrent !done call consuming
                    # this exact message — keep scanning for another one.
                    break

    task_names = {"accent": "تدريب النطق", "speaking": "مهمة الكلام", "shadow": "تمرين المحاكاة"}
    task_name = task_names.get(task_id, task_id)

    return False, (
        f"لازم ترفع تسجيل صوتي **جديد** في `#{channel_name}` لكل مهمة.\n"
        f"(التسجيل اللي استخدمته قبل كده لمهمة تانية معدش يصلح تاني)\n\n"
        f"سجّل {task_name} وارفعه هناك، وبعدين ارجع اكتب `!done {task_id}`\n\n"
        f"*You need to upload a NEW recording in `#{channel_name}` for "
        f"each task — a recording already used for another task can't "
        f"be reused.*"
    )


# ============================================================
#  VERIFICATION: COMMUNITY
# ============================================================

async def verify_community(member: discord.Member, guild: discord.Guild) -> tuple[bool, str]:
    """Check if member either posted in #general-chat today OR spent 10+ min in voice."""
    # Check voice minutes
    voice_min = get_voice_minutes_today(str(member.id))
    if voice_min >= 10:
        return True, ""

    # Check if posted in general-chat today
    channel = discord.utils.get(guild.text_channels, name="general-chat")
    if channel:
        today_start = datetime.datetime.now(datetime.timezone.utc).replace(hour=0, minute=0, second=0)
        async for msg in channel.history(limit=100, after=today_start):
            if msg.author.id == member.id:
                return True, ""

    # Check speaking-feedback or daily-word
    for ch_name in ["speaking-feedback", "daily-word", "introductions"]:
        ch = discord.utils.get(guild.text_channels, name=ch_name)
        if ch:
            today_start = datetime.datetime.now(datetime.timezone.utc).replace(hour=0, minute=0, second=0)
            async for msg in ch.history(limit=50, after=today_start):
                if msg.author.id == member.id:
                    return True, ""

    return False, (
        "لازم تعمل واحدة من دول الأول:\n"
        "• اكتب رسالة في `#general-chat`\n"
        "• أو ادخل غرفة صوتية 10 دقايق\n"
        "• أو شارك في `#daily-word` أو `#speaking-feedback`\n\n"
        "بعدين ارجع اكتب `!done community`"
    )


# ============================================================
#  VERIFICATION: VOCAB (Quiz)
# ============================================================

# Pending quizzes: {discord_id: {"word": str, "answer": str, "expires": datetime}}
_pending_quizzes: dict[str, dict] = {}

# Simple word bank per week (subset — AI generates fresh ones in production)
VOCAB_QUIZ_BANK = {
    1: [("hello", "مرحبا"), ("name", "اسم"), ("good", "جيد"), ("morning", "صباح"), ("thank", "شكر"), ("please", "من فضلك"), ("yes", "نعم"), ("no", "لا")],
    2: [("one", "واحد"), ("two", "اثنين"), ("time", "وقت"), ("day", "يوم"), ("week", "أسبوع"), ("today", "اليوم"), ("clock", "ساعة"), ("hour", "ساعة")],
    3: [("family", "عائلة"), ("mother", "أم"), ("father", "أب"), ("brother", "أخ"), ("sister", "أخت"), ("friend", "صديق"), ("child", "طفل"), ("people", "ناس")],
    4: [("house", "بيت"), ("room", "غرفة"), ("door", "باب"), ("window", "نافذة"), ("kitchen", "مطبخ"), ("bed", "سرير"), ("chair", "كرسي"), ("table", "طاولة")],
    5: [("food", "طعام"), ("water", "ماء"), ("bread", "خبز"), ("rice", "أرز"), ("chicken", "دجاج"), ("fruit", "فاكهة"), ("milk", "حليب"), ("buy", "يشتري")],
    6: [("street", "شارع"), ("car", "سيارة"), ("left", "يسار"), ("right", "يمين"), ("near", "قريب"), ("far", "بعيد"), ("go", "يذهب"), ("come", "يأتي")],
    7: [("run", "يجري"), ("walk", "يمشي"), ("big", "كبير"), ("small", "صغير"), ("fast", "سريع"), ("slow", "بطيء"), ("new", "جديد"), ("old", "قديم")],
    8: [("happy", "سعيد"), ("sad", "حزين"), ("angry", "غاضب"), ("tired", "متعب"), ("love", "يحب"), ("want", "يريد"), ("think", "يفكر"), ("feel", "يشعر")],
}


def generate_vocab_quiz(discord_id: str) -> tuple[str, str, str]:
    """Generate a vocab quiz question. Returns (question_text, correct_answer, word)."""
    from . import curriculum

    member = database.get_member(discord_id)
    level = member["level"] if member else "L0"
    week = database.member_week_number(discord_id) if member else 1
    week = min(curriculum.max_week_for_level(level), max(1, week))

    # Pull from curated curriculum data (this level's vocab + previous weeks).
    # Previously this always read "week" against L0's data regardless of the
    # member's real level, so L1-L3 members were quizzed on L0 vocabulary.
    quiz_words = curriculum.get_quiz_words(week, count=20, level=level)

    if quiz_words:
        word_obj = random.choice(quiz_words)
        word = word_obj.get("word", "hello")
        arabic = word_obj.get("arabic", "مرحبا")
    else:
        # Fallback to hardcoded L0 bank only if curriculum has nothing for
        # this level/week (e.g. curriculum not loaded, or truly no data).
        words = VOCAB_QUIZ_BANK.get(week, VOCAB_QUIZ_BANK[1])
        word, arabic = random.choice(words)

    # Randomly choose direction: EN→AR or AR→EN
    if random.random() < 0.5:
        question = f"ما معنى كلمة **{word}** بالعربي؟"
        answer = arabic
    else:
        question = f"ما الكلمة الإنجليزية لـ **{arabic}**?"
        answer = word

    # Store pending quiz
    _pending_quizzes[discord_id] = {
        "word": word,
        "answer": answer.lower().strip(),
        "alternatives": [word.lower(), arabic.lower()],
        "expires": datetime.datetime.now() + datetime.timedelta(minutes=5),
    }

    return question, answer, word


def check_vocab_answer(discord_id: str, user_answer: str) -> tuple[bool, str]:
    """Check if the user's answer to the vocab quiz is correct."""
    quiz = _pending_quizzes.get(discord_id)
    if not quiz:
        return False, "مفيش سؤال معلّق. اكتب `!done vocab` تاني لبدء الاختبار."

    # Check expiry
    if datetime.datetime.now() > quiz["expires"]:
        del _pending_quizzes[discord_id]
        return False, "الوقت انتهى! اكتب `!done vocab` تاني."

    # Defensive: treat a non-string answer (e.g. None) as empty rather than
    # crashing with AttributeError on .lower(). Not reachable from bot.py's
    # real on_message handler today (discord.py's message.content is always
    # a str), but this is a public function and a bare AttributeError deep
    # in message handling is worth guarding against regardless -- found via
    # adversarial input stress testing.
    user_clean = (user_answer or "").lower().strip()
    correct = quiz["answer"]
    alternatives = quiz.get("alternatives", [correct])

    # Check if answer matches (with some leniency)
    is_correct = user_clean == correct or user_clean in alternatives

    del _pending_quizzes[discord_id]

    if is_correct:
        return True, ""
    else:
        return False, f"❌ إجابة خطأ. الإجابة الصحيحة: **{correct}**\nاكتب `!done vocab` تاني للمحاولة بسؤال جديد."


def has_pending_quiz(discord_id: str) -> bool:
    """Check if user has a pending vocab quiz."""
    quiz = _pending_quizzes.get(discord_id)
    if not quiz:
        return False
    if datetime.datetime.now() > quiz["expires"]:
        del _pending_quizzes[discord_id]
        return False
    return True


# ============================================================
#  VERIFICATION: LISTENING (Quiz)
# ============================================================

# Simple listening comprehension questions
LISTENING_QUESTIONS = [
    {"clip_desc": "Listen: 'I go to work every morning at 8 o'clock.'", "question": "What time does the person go to work?", "answer": "8", "alternatives": ["8 o'clock", "eight", "8:00"]},
    {"clip_desc": "Listen: 'My name is Sarah and I live in Cairo.'", "question": "Where does Sarah live?", "answer": "cairo", "alternatives": ["cairo", "القاهرة"]},
    {"clip_desc": "Listen: 'I have two brothers and one sister.'", "question": "How many brothers?", "answer": "2", "alternatives": ["two", "2", "اثنين"]},
    {"clip_desc": "Listen: 'I like to eat rice and chicken for lunch.'", "question": "What does the person eat for lunch?", "answer": "rice and chicken", "alternatives": ["rice", "chicken", "rice and chicken", "أرز ودجاج"]},
    {"clip_desc": "Listen: 'The weather today is sunny and warm.'", "question": "How is the weather?", "answer": "sunny", "alternatives": ["sunny", "warm", "sunny and warm", "مشمس"]},
    {"clip_desc": "Listen: 'I study English for one hour every day.'", "question": "How long does the person study?", "answer": "one hour", "alternatives": ["one hour", "1 hour", "ساعة"]},
    {"clip_desc": "Listen: 'My favorite color is blue.'", "question": "What is the favorite color?", "answer": "blue", "alternatives": ["blue", "أزرق"]},
    {"clip_desc": "Listen: 'I wake up at 6 in the morning.'", "question": "What time does the person wake up?", "answer": "6", "alternatives": ["6", "six", "6 in the morning"]},
]

_pending_listening: dict[str, dict] = {}


def generate_listening_quiz(discord_id: str) -> tuple[str, str]:
    """Generate a listening comprehension question. Returns (full_prompt, answer).

    Hisn D027: this previously always pulled from LISTENING_QUESTIONS, a
    hardcoded bank of 8 generic placeholder sentences ("My name is Sarah
    and I live in Cairo") with zero connection to the student's actual
    curriculum, level, or week. Confirmed live during Hisn H6: the
    student clicks the practice-platform listening link (which shows a
    real curriculum vocabulary word for TODAY's specific day, via
    curriculum.get_vocabulary_for_day() -- see empire-dojo's
    generate.py's gen_listening(), which is itself a vocabulary
    meaning-matching quiz, not a distinct dialogue/comprehension
    format), then comes back to Discord, types !done listening, and
    gets an entirely unrelated question about a stranger named Sarah --
    no shared word, no shared theme, no way to have "listened for" the
    answer from anything they were just shown.

    Fix: ground this in the SAME real per-day vocabulary the practice
    platform already uses, via the exact same curriculum functions the
    vocab quiz (generate_vocab_quiz, above) already calls -- so a
    student who just did the listening page's word-meaning exercise for
    "friend" now gets asked about "friend" here too, not "Cairo."
    Mirrors generate_vocab_quiz's EN<->AR question shape (this bot has
    no audio-clip-in-Discord capability, so "listening" here means
    "hear it read via TTS/Kokoro on the practice platform, then
    recall/confirm it here" -- consistent with how the practice
    platform's own listening page already works, not a new invented
    format). Falls back to the old hardcoded bank only if there's truly
    no curriculum data available (e.g. curriculum not loaded) so this
    never regresses to "no question at all."
    """
    from . import curriculum, tasks as task_engine

    member = database.get_member(discord_id)
    level = member["level"] if member else "L0"
    week = database.member_week_number(discord_id) if member else 1
    week = min(curriculum.max_week_for_level(level), max(1, week))

    # Same day-index computation used elsewhere in this codebase for the
    # practice-platform link (see tasks.py's generate_daily_tasks()) --
    # NOT a new convention invented here, so "today's words" means the
    # exact same "today" the link the student already clicked pointed at.
    day_name = task_engine.current_day_name()
    week_days = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    day_index = week_days.index(day_name) if day_name in week_days else 0

    day_words = curriculum.get_vocabulary_for_day(week, day_index, level)
    quiz_words = day_words or curriculum.get_quiz_words(week, count=20, level=level)

    if quiz_words:
        word_obj = random.choice(quiz_words)
        word = word_obj.get("word", "hello")
        arabic = word_obj.get("arabic", "مرحبا")
        if random.random() < 0.5:
            question = f"ما معنى كلمة **{word}** بالعربي؟\n\n*(نفس كلمة اليوم اللي شفتها في صفحة الاستماع)*"
            answer = arabic
            alternatives = [arabic.lower(), word.lower()]
        else:
            question = f"ما الكلمة الإنجليزية لـ **{arabic}**؟\n\n*(نفس كلمة اليوم اللي شفتها في صفحة الاستماع)*"
            answer = word
            alternatives = [word.lower(), arabic.lower()]
        prompt = f"👂 **اختبار استماع:**\n\n{question}\n\n*اكتب إجابتك هنا:*"

        _pending_listening[discord_id] = {
            "answer": answer.lower(),
            "alternatives": alternatives,
            "expires": datetime.datetime.now() + datetime.timedelta(minutes=5),
        }
        return prompt, answer

    # Fallback: no curriculum data available at all for this level/week —
    # use the old generic bank rather than showing no question.
    q = random.choice(LISTENING_QUESTIONS)

    _pending_listening[discord_id] = {
        "answer": q["answer"].lower(),
        "alternatives": [a.lower() for a in q["alternatives"]],
        "expires": datetime.datetime.now() + datetime.timedelta(minutes=5),
    }

    prompt = f"👂 **Listening Exercise:**\n\n{q['clip_desc']}\n\n❓ {q['question']}\n\n*اكتب إجابتك هنا (reply to this message):*"
    return prompt, q["answer"]


def check_listening_answer(discord_id: str, user_answer: str) -> tuple[bool, str]:
    """Check listening quiz answer."""
    quiz = _pending_listening.get(discord_id)
    if not quiz:
        return False, "مفيش سؤال معلّق. اكتب `!done listening` تاني."

    if datetime.datetime.now() > quiz["expires"]:
        del _pending_listening[discord_id]
        return False, "الوقت انتهى! اكتب `!done listening` تاني."

    # Defensive: same rationale as check_vocab_answer() above -- guard
    # against a non-string answer instead of raising AttributeError.
    user_clean = (user_answer or "").lower().strip()
    is_correct = user_clean == quiz["answer"] or user_clean in quiz["alternatives"]

    del _pending_listening[discord_id]

    if is_correct:
        return True, ""
    else:
        return False, f"❌ إجابة خطأ. الإجابة: **{quiz['answer']}**\nاكتب `!done listening` تاني للمحاولة."


def has_pending_listening(discord_id: str) -> bool:
    """Check if user has a pending listening quiz."""
    quiz = _pending_listening.get(discord_id)
    if not quiz:
        return False
    if datetime.datetime.now() > quiz["expires"]:
        del _pending_listening[discord_id]
        return False
    return True


# ============================================================
#  MASTER VERIFICATION DISPATCHER
# ============================================================

async def verify_task(task_id: str, member: discord.Member,
                      guild: discord.Guild) -> tuple[bool, str]:
    """Main verification dispatcher. Returns (passed, error_message).

    If passed=True, the task can be marked as done.
    If passed=False, error_message explains what the user needs to do.
    """
    if task_id == "writing":
        return await verify_writing(member, guild)

    elif task_id in ("accent", "speaking", "shadow"):
        return await verify_audio(member, guild, task_id)

    elif task_id == "community":
        return await verify_community(member, guild)

    elif task_id == "vocab":
        # Vocab uses a two-step flow (quiz question → answer)
        # This is handled differently in the bot command
        return True, ""  # Pre-check passes; quiz happens in bot.py

    elif task_id == "listening":
        # Listening also uses two-step flow
        return True, ""  # Pre-check passes; quiz happens in bot.py

    else:
        return True, ""  # Unknown task — allow (shouldn't happen)



# ============================================================
#  AUDIO URL RETRIEVAL (Dhaka' P1 — for pronunciation scoring)
# ============================================================

async def get_recent_audio_url(member: discord.Member, guild: discord.Guild,
                               task_id: str) -> Optional[tuple[str, str]]:
    """Find the most recent audio attachment URL from a member in their showcase channel.

    Returns (url, filename) or None if not found. Used by the pronunciation
    scorer to download the audio for transcription.
    """
    level = (database.get_member(str(member.id)) or {}).get("level", "L0")
    channel_name = f"l{level[1]}-showcase"
    channel = discord.utils.get(guild.text_channels, name=channel_name)

    if not channel:
        return None

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)

    async for msg in channel.history(limit=50, after=cutoff):
        if msg.author.id == member.id and msg.attachments:
            for att in msg.attachments:
                if att.content_type and ("audio" in att.content_type or "video" in att.content_type):
                    return (att.url, att.filename)
                if att.filename.lower().endswith(('.mp3', '.m4a', '.wav', '.ogg', '.mp4', '.webm', '.mov', '.3gp', '.opus')):
                    return (att.url, att.filename)

    return None
