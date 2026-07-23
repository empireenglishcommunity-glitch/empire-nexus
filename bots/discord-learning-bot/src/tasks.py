"""Empire English Community Bot — Task Engine.

Handles daily task generation, formatting, delivery scheduling,
streak computation, and the daily/weekly operational loop.

This module is called by the bot's scheduled tasks (discord.ext.tasks)
to generate and post content at the configured times.
"""
import datetime
import json
import logging
from pathlib import Path

from . import config, database, ai_engine

logger = logging.getLogger("empire-bot.tasks")


def _load_daily_pattern(level: str, day_of_year: int) -> dict | None:
    """Load today's conversational pattern for a level (Tatawwur T1 / Sahel S3).

    Reads from content/patterns/{level}_patterns.json, round-robins through
    all patterns based on day_of_year so each day gets a different one.
    Returns None if no patterns file exists or feature is disabled.
    """
    if not database.is_feature_enabled("tatawwur_patterns"):
        return None

    patterns_file = config.BASE_DIR / "content" / "patterns" / f"{level.lower()}_patterns.json"
    if not patterns_file.exists():
        return None

    try:
        with open(patterns_file, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    # Flatten all categories interleaved (same logic as empire-dojo's generate.py)
    flat = []
    categories = list(data.keys())
    max_per_cat = max((len(v) for v in data.values()), default=0)
    for i in range(max_per_cat):
        for cat in categories:
            items = data[cat]
            if i < len(items):
                flat.append(items[i])

    if not flat:
        return None

    return flat[day_of_year % len(flat)]

# ============================================================
#  TIME UTILITIES
# ============================================================

def _now():
    """Current datetime in configured timezone."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo(config.TIMEZONE))
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


def today_str() -> str:
    """Today's date as ISO string."""
    return _now().date().isoformat()


def current_day_name() -> str:
    """Current day name (Monday, Tuesday, etc.)."""
    return _now().strftime("%A")


def bl(en: str, ar: str) -> str:
    """Bilingual instructional line helper: 'English / Arabic', always
    shown together, matching the same approach used on the practice
    platform (empire-practice's generate.py bl()). Applied only to fixed
    instructional chrome (numbered steps, section labels, footer text)
    that repeats every single day for every student -- NOT to per-week
    curriculum content (writing prompts, speaking missions, accent drill
    target sentences), which is a separate, much larger content project
    left for a future session if wanted.

    Arabic uses the same informal/colloquial register already present in
    the curriculum's instructions_ar fields (content/l0/accent/*.json),
    not formal MSA, for consistency with what students already see."""
    return f"{en} / {ar}"


def current_week_for_member(discord_id: str) -> int:
    """Which week of the program a member is in."""
    return database.member_week_number(discord_id)


# ============================================================
#  DAILY TASK GENERATION
# ============================================================

async def generate_daily_tasks(level: str, week: int) -> dict:
    """Generate all 7 daily tasks for a given level and week.

    Uses curated curriculum data from data/l0_week*.json and content/l0/
    with AI as enhancement (not primary source).

    Returns a dict with task content ready to post.
    """
    from . import curriculum

    day_name = current_day_name()
    date = today_str()
    day_index = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"].index(day_name) if day_name in ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"] else 0

    # Load curated content for today (level MUST be threaded through here —
    # previously this silently defaulted to "L0" for every level, which
    # meant L1/L2/L3 members were served Level-0 vocabulary, speaking
    # missions, and writing prompts every single day).
    daily = curriculum.get_daily_content(week, day_name, day_index, level)
    vocab_theme = daily["theme"]
    level_info = config.LEVELS.get(level, config.LEVELS["L0"])

    # Dhaka' A1: adaptive difficulty adjustments
    # (dormant until tatawwur_adaptive flag is enabled AND student has scores)
    difficulty_adjustments = None
    if database.is_feature_enabled("tatawwur_adaptive"):
        from . import adaptive_engine
        # generate_daily_tasks is called per-level (not per-member), so we
        # can't personalize here. Difficulty affects the _scoring_ DM and
        # the practice platform speed parameter, not the Discord task post.
        # The task post stays the same for everyone at the same level.
        difficulty_adjustments = None  # Per-member adjustment in P2/A1.2 only

    tasks = []

    # Task 1: Accent/Phoneme Drill (from curriculum data)
    accent_drill = daily.get("accent_drill")
    if accent_drill:
        # Use curated accent drill
        content_lines = [f"**{bl('This week', 'الأسبوع ده')}:** {daily['accent_focus']}"]
        if accent_drill.get("target_sounds"):
            content_lines.append(f"**{bl('Sounds', 'الأصوات')}:** {', '.join(accent_drill['target_sounds'])}")
        if accent_drill.get("minimal_pairs"):
            pairs = " | ".join(f"{p['pair'][0]} / {p['pair'][1]}" for p in accent_drill["minimal_pairs"][:4])
            content_lines.append(f"**{bl('Minimal pairs', 'أزواج التمييز')}:** {pairs}")
        word_practice = accent_drill.get("word_practice")
        if word_practice:
            # word_practice is sometimes a flat list, sometimes a dict of
            # named sublists (e.g. {"long_ee": [...], "short_i": [...]}) —
            # found in 9 real drills across L0 weeks 1-4. The dict shape
            # previously crashed this function entirely with
            # "TypeError: unhashable type: 'slice'" on word_practice[:6],
            # which means the bot would fail to post daily tasks at all
            # for any member on one of those days. Flatten both shapes.
            if isinstance(word_practice, dict):
                flat_words = [w for sub in word_practice.values() if isinstance(sub, list) for w in sub]
            else:
                flat_words = word_practice
            if flat_words:
                content_lines.append(f"**{bl('Practice words', 'كلمات للتمرين')}:** {', '.join(flat_words[:6])}")
        if accent_drill.get("record_this"):
            record_this_label = bl("Record this", "سجل ده")
            content_lines.append(f"\n**{record_this_label}:** \"{accent_drill['record_this']}\"")
        content_lines.append(f"\n🎙️ {bl('Record and post in', 'سجل وحط في')} #l{level[1]}-showcase")
        practice_url = curriculum.practice_platform_task_url("accent", week, day_index, level)
        if practice_url:
            content_lines.append(f"🌐 {bl('Practice online (audio + drill)', 'اتمرن أونلاين (صوت + تدريب)')}: {practice_url}")

        tasks.append({
            "id": "accent",
            "title": f"🎯 Accent Drill — {daily['accent_focus']}",
            "content": "\n".join(content_lines),
            "duration_min": 10 if level == "L0" else 20,
        })
    else:
        # Fallback to AI-generated
        accent_result = await ai_engine.generate_accent_drill(level, week)
        if accent_result:
            tasks.append({
                "id": "accent",
                "title": "🎯 Accent Drill",
                "content": _format_accent_drill(accent_result),
                "duration_min": 10,
            })
        else:
            tasks.append(_fallback_accent_task(level, week, config.PHONEME_WEEKS.get(week, config.PHONEME_WEEKS[1])))

    # Task 2: Vocabulary (from curriculum — 8 words for today)
    today_vocab = daily.get("vocabulary", [])
    if today_vocab:
        word_lines = []
        for w in today_vocab:
            word_lines.append(f"**{w['word']}** ({w['pronunciation']}) — {w['arabic']}")
        vocab_practice_url = curriculum.practice_platform_task_url("vocab", week, day_index, level)
        vocab_link_line = f"\n🌐 Practice with flashcards: {vocab_practice_url}" if vocab_practice_url else ""
        today_words_label = bl("Today's 8 words", "كلمات اليوم")
        review_yesterday_label = bl("Review yesterday's words", "راجع كلمات إمبارح")
        tasks.append({
            "id": "vocab",
            "title": f"📖 Vocabulary — {vocab_theme}",
            "content": (
                f"**{today_words_label}:**\n" +
                "\n".join(word_lines) +
                f"\n\n**{bl('How to study', 'طريقة الحفظ')}:**\n"
                f"1. {bl('Read each word + Arabic meaning', 'اقرأ كل كلمة مع معناها بالعربي')}\n"
                f"2. {bl('Say it in your own sentence', 'قولها في جملة من عندك')}\n"
                f"3. {review_yesterday_label}\n"
                f"{vocab_link_line}\n\n"
                f"📋 {bl('Full list in', 'القائمة كاملة في')} #cheat-sheets"
            ),
            "duration_min": 10 if level == "L0" else 20,
        })
    else:
        learn_words_label = bl(
            f"Learn today's 8 new words from the {vocab_theme} theme.",
            f"احفظ ٨ كلمات جديدة النهاردة من موضوع {vocab_theme}.",
        )
        tasks.append({
            "id": "vocab",
            "title": f"📖 Vocabulary — {vocab_theme}",
            "content": (
                f"{learn_words_label}\n"
                f"{bl('Check', 'شوف')} #cheat-sheets {bl('for the full list.', 'عشان القائمة كاملة.')}"
            ),
            "duration_min": 10,
        })

    # Task 3: Shadowing
    shadow_practice_url = curriculum.practice_platform_task_url("shadow", week, day_index, level)
    shadow_link_line = f"🌐 Today's passage + studio audio: {shadow_practice_url}\n\n" if shadow_practice_url else ""
    tasks.append({
        "id": "shadow",
        "title": "🎧 Shadowing Practice",
        "content": (
            f"**{bl('Speed', 'السرعة')}:** {'60-80 WPM (slow)' if level == 'L0' else '100-120 WPM'}\n\n"
            f"{shadow_link_line}"
            f"1. {bl('Listen to a short clip once (understand the gist)', 'اسمع الكليب مرة واحدة (افهم المعنى العام)')}\n"
            f"2. {bl('Listen + read the transcript', 'اسمع + اقرأ النص')}\n"
            f"3. {bl('Shadow 3 times (speak along, match rhythm)', 'كرر معاه ٣ مرات (اتكلم في نفس الوقت، بنفس الريتم)')}\n"
            f"4. {bl('Record attempt #3 (minimum 30 seconds)', 'سجل المحاولة الثالثة (٣٠ ثانية على الأقل)')}\n"
            f"5. {bl('Note 2 words where you differed most', 'لاحظ كلمتين اختلفت فيهم عن الأصل')}\n\n"
            f"🎙️ {bl('Upload recording in', 'رفع التسجيل في')} #l{level[1]}-showcase"
        ),
        "duration_min": 10 if level == "L0" else 20,
    })

    # Task 4: Speaking Mission (from curriculum data)
    speaking = daily.get("speaking_mission")
    if speaking:
        target_sec = speaking.get("target_seconds", level_info["speaking_target_seconds"])
        tasks.append({
            "id": "speaking",
            "title": f"🎙️ Speaking Mission — {speaking.get('type', 'free_talk').replace('_', ' ').title()}",
            "content": (
                f"**{bl('Task', 'المهمة')}:** {speaking['prompt']}\n\n"
                f"⏱️ {bl('Target', 'الهدف')}: {target_sec} {bl('seconds', 'ثانية')}\n"
                f"🎙️ {bl('Record and post in', 'سجل وحط في')} #l{level[1]}-showcase"
            ),
            "duration_min": 10 if level == "L0" else 25,
        })
    else:
        # Fallback to a static prompt. Unlike the accent-drill task above,
        # this does NOT try ai_engine.generate_speaking_mission() first --
        # curated speaking_missions data exists for all 38 real weeks (see
        # test_every_week_has_all_seven_speaking_missions), so this branch
        # is not currently reachable in production. Noting the asymmetry
        # here rather than silently "fixing" it, since wiring in an extra
        # AI call changes real behavior and isn't something this cleanup
        # pass was asked to do.
        tasks.append(_fallback_speaking_task(level, config.SPEAKING_MISSION_TYPES.get(day_name, "free_talk")))

    # Task 5: Listening
    listening_practice_url = curriculum.practice_platform_task_url("listening", week, day_index, level)
    listening_link_line = f"🌐 Do it online (audio + auto-checked MCQ): {listening_practice_url}\n\n" if listening_practice_url else ""
    tasks.append({
        "id": "listening",
        "title": "👂 Listening Exercise",
        "content": (
            f"**{bl('Target speed', 'السرعة المستهدفة')}:** {'60-80 WPM' if level == 'L0' else '100-120 WPM'}\n\n"
            f"{listening_link_line}"
            f"1. {bl('Listen to a short clip (2-3 times if needed)', 'اسمع الكليب (٢-٣ مرات لو احتجت)')}\n"
            f"2. {bl('Answer comprehension questions', 'جاوب على أسئلة الفهم')}\n"
            f"3. {bl('Identify 2 new words from the clip', 'حدد كلمتين جديدة من الكليب')}\n"
            f"4. {bl('Repeat 1 sentence verbatim', 'كرر جملة واحدة زي ما هي بالحرف')}\n\n"
            f"📋 {bl('Check', 'شوف')} #resources {bl('for clips at your level.', 'عشان كليبات مستواك.')}"
        ),
        "duration_min": 8 if level == "L0" else 20,
    })

    # Task 6: Writing (from curriculum data)
    writing_prompt = daily.get("writing_prompt")
    if not writing_prompt:
        writing_prompt = _get_writing_prompt(level, week, day_name)
    tasks.append({
        "id": "writing",
        "title": "✍️ Writing Practice",
        "content": (
            f"**{bl('Prompt', 'المطلوب')}:** {writing_prompt}\n\n"
            f"{bl('Write 4-5 sentences.', 'اكتب ٤-٥ جمل.') if level == 'L0' else bl('Write a paragraph (100+ words).', 'اكتب فقرة (١٠٠ كلمة أو أكتر).')}\n"
            f"{bl('No translator! Do your best.', 'من غير مترجم! اعمل قد ما تقدر.')}\n\n"
            f"📝 {bl('Post in', 'حط في')} #l{level[1]}-text-practice"
        ),
        "duration_min": 7 if level == "L0" else 20,
    })

    # Task 7: Community
    daily_word_label = bl(
        "Post in #daily-word (use today's word in a sentence)",
        "حط في #daily-word (استخدم كلمة اليوم في جملة)",
    )
    tasks.append({
        "id": "community",
        "title": "💬 Community Participation",
        "content": (
            f"{bl('Choose one', 'اختار حاجة واحدة')}:\n"
            f"• {bl('Join voice lounge for 10+ minutes', 'دخل الفويس ١٠ دقايق على الأقل')}\n"
            f"• {bl('Reply to someone in #general-chat (in English)', 'رد على حد في #general-chat (بالإنجليزي)')}\n"
            f"• {bl('Give feedback on a recording in #speaking-feedback', 'اكتب رأيك على تسجيل في #speaking-feedback')}\n"
            f"• {daily_word_label}\n\n"
            f"🏛️ {bl('The community grows when YOU participate.', 'المجتمع بيكبر لما إنت تشارك.')}"
        ),
        "duration_min": 5 if level == "L0" else 15,
    })

    total_min = sum(t["duration_min"] for t in tasks)

    # Tatawwur T1 / Sahel S3: Daily conversational pattern
    day_of_year = datetime.date.today().timetuple().tm_yday
    pattern = _load_daily_pattern(level, day_of_year)

    return {
        "date": date,
        "day_name": day_name,
        "level": level,
        "week": week,
        "tasks": tasks,
        "total_minutes": total_min,
        "daily_pattern": pattern,
    }


# ============================================================
#  FORMATTING HELPERS
# ============================================================

def _format_accent_drill(drill: dict) -> str:
    """Format an AI-generated accent drill into readable text."""
    lines = []
    if drill.get("instructions_ar"):
        lines.append(f"📋 {drill['instructions_ar']}")
        lines.append("")
    if drill.get("phonemes"):
        lines.append(f"**{bl('Sounds', 'الأصوات')}:** {', '.join(drill['phonemes'])}")
    if drill.get("minimal_pairs"):
        pairs = " | ".join(f"{a} / {b}" for a, b in drill["minimal_pairs"][:4])
        lines.append(f"**{bl('Minimal pairs', 'أزواج التمييز')}:** {pairs}")
    if drill.get("words"):
        lines.append(f"**{bl('Practice words', 'كلمات للتمرين')}:** {', '.join(drill['words'][:6])}")
    if drill.get("sentences"):
        say_label = bl("Say", "قول")
        for s in drill["sentences"][:2]:
            lines.append(f"**{say_label}:** \"{s}\"")
    lines.append("")
    lines.append(bl("🎙️ Record yourself saying the sentences. Post in #l0-showcase.", "سجل نفسك بتقول الجمل. حط التسجيل في #l0-showcase."))
    return "\n".join(lines)


def _fallback_accent_task(level: str, week: int, phoneme_info: dict) -> dict:
    """Fallback accent task if AI generation fails."""
    week_sounds_label = bl("This week's sounds", "أصوات الأسبوع ده")
    return {
        "id": "accent",
        "title": f"🎯 Accent Drill — {phoneme_info['focus']}",
        "content": (
            f"**{week_sounds_label}:** {', '.join(phoneme_info['vowels'][:2])} + "
            f"{', '.join(phoneme_info['consonants'][:3])}\n\n"
            f"1. {bl('Say each sound 10 times in isolation', 'انطق كل صوت ١٠ مرات لوحده')}\n"
            f"2. {bl('Practice with words that contain these sounds', 'اتمرن بكلمات فيها الأصوات دي')}\n"
            f"3. {bl('Say a sentence using these sounds', 'قول جملة فيها الأصوات دي')}\n"
            f"4. {bl('Record yourself and compare', 'سجل نفسك وقارن')}\n\n"
            f"🎙️ {bl('Post your recording in', 'حط التسجيل في')} #l{level[1]}-showcase"
        ),
        "duration_min": 10,
    }


def _fallback_speaking_task(level: str, mission_type: str) -> dict:
    """Fallback speaking task if AI generation fails."""
    prompts = {
        "self_introduction": "Introduce yourself: name, where you're from, what you do.",
        "describe": "Describe what you can see in the room right now.",
        "list_count": "List 5 things you did today.",
        "read_aloud": "Read this: 'I am learning English every day. I practice speaking and listening.'",
        "answer_questions": "Answer: What is your name? Where do you live? What do you like?",
        "shadow_repeat": "Repeat this 3 times: 'I think this is a good day to practice.'",
        "free_talk": "Talk about anything for 45 seconds. No script. Just speak.",
    }
    return {
        "id": "speaking",
        "title": "🎙️ Speaking Mission",
        "content": (
            f"**{bl('Task', 'المهمة')}:** {prompts.get(mission_type, prompts['free_talk'])}\n\n"
            f"⏱️ {bl('Target', 'الهدف')}: {'45' if level == 'L0' else '90'} {bl('seconds', 'ثانية')}\n"
            f"🎙️ {bl('Record and post in', 'سجل وحط في')} #l{level[1]}-showcase"
        ),
        "duration_min": 10,
    }


def _get_writing_prompt(level: str, week: int, day_name: str) -> str:
    """Get a writing prompt appropriate for the level and week."""
    l0_prompts = {
        1: ["Write 3 sentences about yourself.", "Write your name and where you live.",
            "Write what you like to eat.", "Write about your family.",
            "Write what you do every morning.", "Write 3 things you can see.",
            "Write about your friend."],
        2: ["Describe your home.", "Write about your daily routine.",
            "What do you do on weekends?", "Describe your best friend.",
            "Write about your favorite food.", "What do you do after work/school?",
            "Write about something you like."],
        3: ["Write about your family (5 sentences).", "What did you do today?",
            "Describe your neighborhood.", "Write about your job/school.",
            "What do you want to learn?", "Describe your morning routine.",
            "Write about your hobby."],
    }
    prompts = l0_prompts.get(week, l0_prompts[3])
    day_index = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(day_name) if day_name in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] else 0
    return prompts[day_index % len(prompts)]


# ============================================================
#  TASK DELIVERY FORMATTING (Discord message)
# ============================================================

# Discord hard-caps a single message at 2000 characters (HTTP 400 /
# discord.HTTPException, error 50035, if exceeded). Leave a safety margin
# below that for formatting overhead.
DISCORD_MESSAGE_LIMIT = 1900


def format_daily_post(task_data: dict) -> str:
    """Format the full daily task set into a single Discord message string.

    RETAINED for any external caller that still wants one combined string
    (e.g. logging, tests) — but do NOT send this directly to a Discord
    channel. It is frequently well over Discord's 2000-character message
    limit (measured: up to ~3600 chars for L3, and 37 of 38 real level/week
    combinations exceed 2000 chars even before this session's practice-
    platform links were added). Use format_daily_post_chunks() + send each
    chunk separately when posting to Discord.
    """
    return "\n\n".join(format_daily_post_chunks(task_data))


def format_daily_post_chunks(task_data: dict) -> list[str]:
    """Format the daily task set into one or more Discord-message-safe chunks.

    Each returned string is guaranteed to be under DISCORD_MESSAGE_LIMIT
    characters. A single task is never split mid-content — chunks break
    between tasks, so if any individual task's content alone exceeds the
    limit (not currently the case, but not something to silently corrupt
    if it changes), that task becomes its own chunk rather than being cut off.

    Fixes a real bug found while testing this session's practice-platform
    links: channel.send() with a message over 2000 chars raises
    discord.HTTPException, which bot.py's daily_task_post() catches and
    only logs — meaning daily tasks have likely been silently failing to
    post to Discord for most level/week combinations already, independent
    of anything added in this change.
    """
    # Darb Phase 0: the daily message is decluttered into TWO clearly
    # labelled sections with exactly ONE practice-platform link (the bare
    # intro URL). The 4 platform tasks (accent/vocab/shadowing/listening)
    # are listed concisely — their full content lives on the platform, so
    # no per-task deep links here. The 3 Discord tasks (speaking/writing/
    # community) keep their prompts, since they're done in Discord. Task
    # numbers still map to !1-!7 and the reaction emojis (they index into
    # config.DAILY_TASKS, independent of the display grouping).
    level = task_data["level"]
    level_info = config.LEVELS.get(level, config.LEVELS["L0"])

    task_by_id = {t["id"]: t for t in task_data["tasks"]}
    num_by_id = {t["id"]: i + 1 for i, t in enumerate(config.DAILY_TASKS)}
    NUM_EMOJI = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣", 7: "7️⃣"}

    PRACTICE_IDS = ["accent", "vocab", "shadow", "listening"]
    DISCORD_IDS = ["speaking", "writing", "community"]

    header = "\n".join([
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📅 **{bl('DAY', 'اليوم')} — {task_data['day_name']}, {bl('Week', 'أسبوع')} {task_data['week']}**",
        f"🏛️ EMPIRE ENGLISH — {level_info['emoji']} {level_info['name']}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ])

    blocks = []

    # Section 1 — the practice platform: ONE link + the platform tasks
    # listed concisely by their real title (their full content lives on
    # the platform, so no per-task deep links and no content dump here).
    practice_present = [tid for tid in PRACTICE_IDS if tid in task_by_id]
    if practice_present:
        practice_lines = [
            f"🌐 **{bl('On the practice platform', 'على منصة التمرين')}:** {config.PRACTICE_PLATFORM_URL}",
        ]
        for tid in practice_present:
            t = task_by_id[tid]
            practice_lines.append(f"{NUM_EMOJI[num_by_id[tid]]} {t['title']}")
        practice_lines.append(
            bl("Open today and start — audio, drills and quizzes are all there.",
               "افتح يوم النهاردة وابدأ — الصوت والتمارين والاختبارات كلها هناك.")
        )
        blocks.append("\n".join(practice_lines))

    # Section 2 — the Discord tasks (done in Discord, so keep their prompts)
    discord_blocks = []
    for tid in DISCORD_IDS:
        t = task_by_id.get(tid)
        if t:
            discord_blocks.append(
                f"{NUM_EMOJI[num_by_id[tid]]} **{t['title']}** ({t['duration_min']} min)\n{t['content']}"
            )
    if discord_blocks:
        blocks.append(f"💬 **{bl('Here on Discord', 'هنا في Discord')}:**")
        blocks.extend(discord_blocks)

    footer = "\n".join([
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏱️ **{bl('Total', 'المجموع')}:** ~{task_data['total_minutes']} {bl('min', 'دقيقة')}",
        f"✅ {bl('Log each when done:', 'لما تخلص كل مهمة اكتب:')} `!done` / `!1`-`!7` {bl('in', 'في')} #daily-check-in",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ])

    # Daily conversational pattern (Tatawwur T1 / Sahel S3), if present
    pattern = task_data.get("daily_pattern")
    if pattern:
        pattern_label = bl("Today's Pattern", "نمط اليوم")
        blocks.append(
            f"💬 **{pattern_label}**\n"
            f"**\"{pattern['phrase']}\"**\n"
            f"📍 {pattern['when']}\n"
            f"🇪🇬 {pattern['arabic']}\n"
            f"💡 _{pattern['example']}_"
        )

    chunks = []
    current = [header]
    current_len = len(header)

    def flush():
        nonlocal current, current_len
        if current:
            chunks.append("\n\n".join(current))
        current = []
        current_len = 0

    for block in blocks:
        block_len = len(block)
        if current_len + block_len + 2 > DISCORD_MESSAGE_LIMIT and current:
            flush()
        current.append(block)
        current_len += block_len + 2

    if current_len + len(footer) + 2 <= DISCORD_MESSAGE_LIMIT:
        current.append(footer)
        flush()
    else:
        flush()
        chunks.append(footer)

    return chunks


def format_streak_update(discord_id: str, member_name: str) -> str:
    """Format a streak update message."""
    current, longest = database.get_streak(discord_id)
    tasks_today = len(database.tasks_completed_today(discord_id))
    total_tasks = 7

    bar = "█" * tasks_today + "░" * (total_tasks - tasks_today)
    msg = (
        f"**{member_name}** [{bar}] {tasks_today}/{total_tasks}\n"
        f"🔥 Streak: **{current}** days | Best: {longest}"
    )
    # Check streak bonus
    if current in config.STREAK_BONUS_POINTS:
        bonus = config.STREAK_BONUS_POINTS[current]
        msg += f"\n🎉 **{current}-DAY STREAK BONUS: +{bonus} points!**"

    return msg


# ============================================================
#  STREAK & POINTS COMPUTATION
# ============================================================

async def process_submission(discord_id: str, member_name: str,
                             task_id: str, content: str = "") -> dict:
    """Process a task submission: log it, update streak, award points.

    Returns dict with: new (bool), tasks_today (int), streak (int), points (int), feedback (str)
    """
    date = today_str()

    # Log the submission
    is_new = database.log_submission(discord_id, date, task_id, content)
    if not is_new:
        return {"new": False, "tasks_today": 0, "streak": 0, "points": 0, "feedback": ""}

    # Count tasks today and update streak
    tasks_today = database.count_submissions_for_date(discord_id, date)
    database.update_streak(discord_id, date, tasks_today)

    # Award points
    points = config.POINTS_PER_TASK
    database.add_points(discord_id, points, f"task:{task_id}")

    # Bonus for all 7
    if tasks_today == 7:
        database.add_points(discord_id, config.POINTS_ALL_TASKS, "all_7_tasks")
        points += config.POINTS_ALL_TASKS

    # Check streak bonuses — award ONCE per threshold per day, not once
    # per submission. Previously this fired on every !done call where
    # current_streak was in STREAK_BONUS_POINTS, meaning all 7 submissions
    # on the day the streak hits 7 each awarded 200 points (7 × 200 =
    # 1400 total instead of 200 once). Fixed by checking if a points_log
    # entry with this reason already exists for this member (streak
    # bonuses are unique per threshold — you can't hit streak_7 twice
    # without your streak resetting and rebuilding first, at which point
    # you'd get streak_7 again legitimately on the next cycle).
    current_streak, _ = database.get_streak(discord_id)
    streak_bonus_awarded = False
    if current_streak in config.STREAK_BONUS_POINTS:
        reason = f"streak_{current_streak}"
        conn = database._connect()
        already_awarded = conn.execute(
            "SELECT 1 FROM points_log WHERE discord_id=? AND reason=?",
            (discord_id, reason),
        ).fetchone()
        conn.close()
        if not already_awarded:
            bonus = config.STREAK_BONUS_POINTS[current_streak]
            database.add_points(discord_id, bonus, reason)
            points += bonus
            streak_bonus_awarded = True

    # Generate quick feedback
    feedback = await ai_engine.quick_feedback(member_name, task_id)

    # Detect milestones for Nabd N3 celebrations
    milestones = []
    if tasks_today == 7:
        milestones.append(("all_7", {}))
    if streak_bonus_awarded:
        milestones.append(("streak", {"days": current_streak, "bonus": config.STREAK_BONUS_POINTS[current_streak]}))

    return {
        "new": True,
        "tasks_today": tasks_today,
        "streak": current_streak,
        "points": points,
        "feedback": feedback,
        "milestones": milestones,
    }


# ============================================================
#  INACTIVE MEMBER DETECTION
# ============================================================

def check_inactive_members() -> dict[str, list[dict]]:
    """Check for members who need intervention.

    Returns dict keyed by intervention type with member lists.
    """
    results = {}
    for days, action in config.INTERVENTION_THRESHOLDS.items():
        members = database.inactive_members(days)
        # Filter to only those who are exactly at this threshold
        # (not already triggered for a higher threshold)
        if members:
            results[action] = members
    return results


# ============================================================
#  WEEKLY ASSESSMENT HELPERS
# ============================================================

def calculate_completion_rate(discord_id: str, days: int = 7) -> float:
    """Calculate task completion rate over the last N days."""
    total_expected = days * 7  # 7 tasks per day
    total_submitted = 0
    today = datetime.date.today()

    for i in range(days):
        date = (today - datetime.timedelta(days=i)).isoformat()
        count = database.count_submissions_for_date(discord_id, date)
        total_submitted += count

    return round((total_submitted / total_expected) * 100, 1) if total_expected > 0 else 0


def calculate_overall_score(scores: dict) -> float:
    """Calculate weighted overall assessment score."""
    total = 0
    for dim in config.ASSESSMENT_DIMENSIONS:
        score = scores.get(dim["id"], 0) or 0
        total += score * dim["weight"]
    return round(total, 1)


def score_to_rating(score: float) -> str:
    """Convert numeric score to rating label."""
    if score >= 90:
        return "Excellent"
    elif score >= 80:
        return "Strong"
    elif score >= 70:
        return "Satisfactory"
    elif score >= 60:
        return "At Risk"
    else:
        return "Critical"


def build_weekly_assessment(discord_id: str, days: int = 7) -> dict:
    """Compute this week's assessment scores from real, already-verified
    data -- no new AI call, no self-reported numbers.

    bot.py's weekly_assessment DM tells members to submit speaking,
    writing, and vocabulary work and then run `!assess`, but `!assess`
    itself never existed as a command (found via adversarial-input
    stress testing on database.save_assessment(), which turned out to
    have zero production callers anywhere in the bot). This is the
    scoring logic that command was always missing.

    Dimension scores (matching config.ASSESSMENT_DIMENSIONS' ids):
      - speaking / listening / vocabulary / accent: each 100 if the
        member has a *verified* `!done <task>` submission logged in the
        last `days` days, else 0. These four tasks are gated by
        verification.verify_task()/check_vocab_answer()/
        check_listening_answer() before database.log_submission() is
        ever called, so "a row exists" already means "passed
        verification this week" -- there's no separate quality score to
        pull for them anywhere in this codebase.
      - writing: the most recent writing submission's AI-evaluated
        score from ai_engine.evaluate_writing() (via the
        #writing-feedback auto-eval pipeline, bot.py's on_message), or 0
        if no writing was submitted this week.
      - completion: calculate_completion_rate() over the same window,
        reusing the existing tested helper rather than recomputing it.

    Returns dict with: scores (dict), overall (float), rating (str),
    submitted_tasks (list[str] actually found this week).
    """
    submissions = database.get_submissions_since(discord_id, days=days)
    submitted_task_ids = {s["task_id"] for s in submissions}

    verified_binary_tasks = {"speaking", "listening", "vocab", "accent"}
    scores = {
        "speaking": 100.0 if "speaking" in submitted_task_ids else 0.0,
        "listening": 100.0 if "listening" in submitted_task_ids else 0.0,
        "vocabulary": 100.0 if "vocab" in submitted_task_ids else 0.0,
        "accent": 100.0 if "accent" in submitted_task_ids else 0.0,
        "completion": calculate_completion_rate(discord_id, days=days),
    }

    writing_subs = [s for s in submissions if s["task_id"] == "writing" and s["score"] is not None]
    scores["writing"] = writing_subs[-1]["score"] if writing_subs else 0.0

    overall = calculate_overall_score(scores)
    rating = score_to_rating(overall)

    return {
        "scores": scores,
        "overall": overall,
        "rating": rating,
        "submitted_tasks": sorted(submitted_task_ids & (verified_binary_tasks | {"writing"})),
    }
