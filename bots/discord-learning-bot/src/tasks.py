"""Empire English Community Bot — Task Engine.

Handles daily task generation, formatting, delivery scheduling,
streak computation, and the daily/weekly operational loop.

This module is called by the bot's scheduled tasks (discord.ext.tasks)
to generate and post content at the configured times.
"""
import datetime
import logging
from typing import Optional

from . import config, database, ai_engine

logger = logging.getLogger("empire-bot.tasks")

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


def current_week_for_member(discord_id: str) -> int:
    """Which week of the program a member is in."""
    return database.member_week_number(discord_id)


# ============================================================
#  DAILY TASK GENERATION
# ============================================================

async def generate_daily_tasks(level: str, week: int) -> dict:
    """Generate all 7 daily tasks for a given level and week.

    Returns a dict with task content ready to post:
    {
        "date": "2026-06-26",
        "day_name": "Thursday",
        "level": "L0",
        "week": 3,
        "tasks": [
            {"id": "accent", "title": "...", "content": "...", "duration_min": 10},
            ...
        ]
    }
    """
    day_name = current_day_name()
    date = today_str()
    vocab_theme = config.VOCAB_THEMES.get(week, "General")
    mission_type = config.SPEAKING_MISSION_TYPES.get(day_name, "free_talk")
    phoneme_info = config.PHONEME_WEEKS.get(week, config.PHONEME_WEEKS[1])
    level_info = config.LEVELS.get(level, config.LEVELS["L0"])

    tasks = []

    # Task 1: Accent/Phoneme Drill
    accent_drill = await ai_engine.generate_accent_drill(level, week)
    if accent_drill:
        tasks.append({
            "id": "accent",
            "title": f"🎯 Accent Drill — {phoneme_info['focus']}",
            "content": _format_accent_drill(accent_drill),
            "duration_min": 10 if level == "L0" else 20,
        })
    else:
        tasks.append(_fallback_accent_task(level, week, phoneme_info))

    # Task 2: Vocabulary
    tasks.append({
        "id": "vocab",
        "title": f"📖 Vocabulary — {vocab_theme}",
        "content": (
            f"**Theme:** {vocab_theme}\n"
            f"Learn today's 8 new words. For each word:\n"
            f"1. See definition + Arabic meaning\n"
            f"2. Listen to pronunciation\n"
            f"3. Say it in your own sentence (record yourself)\n"
            f"4. Review yesterday's words\n\n"
            f"📋 Check #cheat-sheets for this week's vocabulary list."
        ),
        "duration_min": 10 if level == "L0" else 20,
    })

    # Task 3: Shadowing
    tasks.append({
        "id": "shadow",
        "title": "🎧 Shadowing Practice",
        "content": (
            f"**Method:** {'Blind Shadowing' if level == 'L0' and week <= 4 else 'Text-Aided Shadowing'}\n"
            f"**Speed:** {'60-80 WPM (slow)' if level == 'L0' else '100-120 WPM'}\n\n"
            f"1. Listen to the clip once (understand the gist)\n"
            f"2. Listen + read the transcript\n"
            f"3. Shadow 3 times (speak along, match rhythm)\n"
            f"4. Record attempt #3\n"
            f"5. Note 2 words where you differed most\n\n"
            f"🎧 Clip for today: check #resources or use any clip at your level."
        ),
        "duration_min": 10 if level == "L0" else 20,
    })

    # Task 4: Speaking Mission (AI-generated)
    speaking = await ai_engine.generate_speaking_mission(
        level, week, day_name, mission_type, vocab_theme
    )
    if speaking:
        tasks.append({
            "id": "speaking",
            "title": f"🎙️ Speaking Mission — {speaking.get('mission_title', mission_type)}",
            "content": _format_speaking_mission(speaking, level),
            "duration_min": 10 if level == "L0" else 25,
        })
    else:
        tasks.append(_fallback_speaking_task(level, mission_type))

    # Task 5: Listening
    tasks.append({
        "id": "listening",
        "title": "👂 Listening Exercise",
        "content": (
            f"**Target speed:** {'60-80 WPM' if level == 'L0' else '100-120 WPM'}\n\n"
            f"1. Listen to a short clip (2-3 times if needed)\n"
            f"2. Answer comprehension questions\n"
            f"3. Identify 2 new words from the clip\n"
            f"4. Repeat 1 sentence verbatim\n\n"
            f"📋 Check #resources for recommended clips at your level."
        ),
        "duration_min": 8 if level == "L0" else 20,
    })

    # Task 6: Writing
    writing_prompt = _get_writing_prompt(level, week, day_name)
    tasks.append({
        "id": "writing",
        "title": "✍️ Writing Practice",
        "content": (
            f"**Prompt:** {writing_prompt}\n\n"
            f"{'Write 4-5 sentences.' if level == 'L0' else 'Write a paragraph (100+ words).'}\n"
            f"No translator! Do your best.\n\n"
            f"📝 Post in #l{level[1]}-text-practice or #writing-feedback for AI correction."
        ),
        "duration_min": 7 if level == "L0" else 20,
    })

    # Task 7: Community
    tasks.append({
        "id": "community",
        "title": "💬 Community Participation",
        "content": (
            f"Choose one:\n"
            f"• Join #voice-lounge for 10+ minutes of English conversation\n"
            f"• Reply to someone in #general-chat (in English)\n"
            f"• Give feedback on a recording in #speaking-feedback\n"
            f"• Post in #daily-word (use today's word in a sentence)\n\n"
            f"🏛️ The community grows when YOU participate."
        ),
        "duration_min": 5 if level == "L0" else 15,
    })

    total_min = sum(t["duration_min"] for t in tasks)

    return {
        "date": date,
        "day_name": day_name,
        "level": level,
        "week": week,
        "tasks": tasks,
        "total_minutes": total_min,
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
        lines.append(f"**Sounds:** {', '.join(drill['phonemes'])}")
    if drill.get("minimal_pairs"):
        pairs = " | ".join(f"{a} / {b}" for a, b in drill["minimal_pairs"][:4])
        lines.append(f"**Minimal pairs:** {pairs}")
    if drill.get("words"):
        lines.append(f"**Practice words:** {', '.join(drill['words'][:6])}")
    if drill.get("sentences"):
        for s in drill["sentences"][:2]:
            lines.append(f"**Say:** \"{s}\"")
    lines.append("")
    lines.append("🎙️ Record yourself saying the sentences. Post in #l0-showcase.")
    return "\n".join(lines)


def _format_speaking_mission(mission: dict, level: str) -> str:
    """Format an AI-generated speaking mission into readable text."""
    lines = []
    if level == "L0" and mission.get("instructions_ar"):
        lines.append(f"📋 {mission['instructions_ar']}")
        lines.append("")
    lines.append(mission.get("instructions_en", "Complete the speaking task."))
    lines.append("")
    if mission.get("guiding_questions"):
        lines.append("**Guiding questions:**")
        for q in mission["guiding_questions"][:3]:
            lines.append(f"  • {q}")
        lines.append("")
    duration = mission.get("target_duration_seconds", 60)
    lines.append(f"⏱️ Target: {duration} seconds")
    if mission.get("target_phrases"):
        lines.append(f"💡 Try to use: {', '.join(mission['target_phrases'][:3])}")
    if mission.get("phoneme_focus"):
        lines.append(f"🎯 Pronunciation focus: {mission['phoneme_focus']}")
    lines.append("")
    lines.append(f"🎙️ Record and post in #l{level[1]}-showcase")
    return "\n".join(lines)


def _fallback_accent_task(level: str, week: int, phoneme_info: dict) -> dict:
    """Fallback accent task if AI generation fails."""
    return {
        "id": "accent",
        "title": f"🎯 Accent Drill — {phoneme_info['focus']}",
        "content": (
            f"**This week's sounds:** {', '.join(phoneme_info['vowels'][:2])} + "
            f"{', '.join(phoneme_info['consonants'][:3])}\n\n"
            f"1. Say each sound 10 times in isolation\n"
            f"2. Practice with words that contain these sounds\n"
            f"3. Say a sentence using these sounds\n"
            f"4. Record yourself and compare\n\n"
            f"🎙️ Post your recording in #l{level[1]}-showcase"
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
        "title": f"🎙️ Speaking Mission",
        "content": (
            f"**Task:** {prompts.get(mission_type, prompts['free_talk'])}\n\n"
            f"⏱️ Target: {'45' if level == 'L0' else '90'} seconds\n"
            f"🎙️ Record and post in #l{level[1]}-showcase"
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

def format_daily_post(task_data: dict) -> str:
    """Format the full daily task set into a Discord message."""
    level = task_data["level"]
    level_info = config.LEVELS.get(level, config.LEVELS["L0"])
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📅 **DAY — {task_data['day_name']}, Week {task_data['week']}**",
        f"🏛️ EMPIRE ENGLISH — {level_info['emoji']} {level_info['name']}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for i, task in enumerate(task_data["tasks"], 1):
        emoji = config.DAILY_TASKS[i - 1]["emoji"] if i <= len(config.DAILY_TASKS) else "📌"
        lines.append(f"**{i}️⃣ {task['title']}** ({task['duration_min']} min)")
        lines.append(task["content"])
        lines.append("")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏱️ **Total:** ~{task_data['total_minutes']} min ({level_info['name']} Core track)",
        "✅ When done: type `!done` in #daily-check-in",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ])

    return "\n".join(lines)


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

    # Check streak bonuses
    current_streak, _ = database.get_streak(discord_id)
    if current_streak in config.STREAK_BONUS_POINTS:
        bonus = config.STREAK_BONUS_POINTS[current_streak]
        database.add_points(discord_id, bonus, f"streak_{current_streak}")
        points += bonus

    # Generate quick feedback
    feedback = await ai_engine.quick_feedback(member_name, task_id)

    return {
        "new": True,
        "tasks_today": tasks_today,
        "streak": current_streak,
        "points": points,
        "feedback": feedback,
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
