"""Empire English Community Bot — Additional Features Module.

Implements remaining blueprint items:
1. Gradual task intro (3→5→7 for new members)
2. Privacy notice content
3. Weekly feedback survey (Friday DM)
4. Spaced repetition (review words in quiz)
5. Weekly progress report (Monday DM)
6. Grammar Pattern Card delivery (Day 4 of week)
7. Advancement exam flow
8. Buddy system
9. English-only detection
10. Streak tracker auto-post
11. Leaderboard auto-post
12. At-risk member outreach
"""
import datetime
import logging
import random
import re

import discord

from . import config, database, curriculum

logger = logging.getLogger("empire-bot.features")


# ============================================================
#  1. GRADUAL TASK INTRO
# ============================================================

def get_allowed_tasks_for_member(discord_id: str) -> list[str]:
    """Determine how many tasks a new member should do based on days since joining.
    Day 1-3: 3 tasks (accent, vocab, community)
    Day 4-7: 5 tasks (+ speaking, writing)
    Week 2+: all 7 tasks
    """
    member = database.get_member(discord_id)
    if not member:
        return [t["id"] for t in config.DAILY_TASKS]

    joined = datetime.datetime.fromisoformat(member["joined_at"])
    days_since = (datetime.datetime.now() - joined).days

    all_tasks = [t["id"] for t in config.DAILY_TASKS]

    if days_since < 3:
        return ["accent", "vocab", "community"]
    elif days_since < 7:
        return ["accent", "vocab", "speaking", "writing", "community"]
    else:
        return all_tasks


# ============================================================
#  1b. BAWABA B5: GRADUAL ENGLISH INJECTION
# ============================================================
# The bot interface IS the first English lesson. Response language
# transitions automatically based on member's week number:
#   Week 1:  "arabic"           — all bot responses in Arabic only
#   Week 2-3: "bilingual_ar"    — Arabic first, English shown as learning
#   Week 4+: "bilingual"        — current system (English + Arabic)

def response_language(discord_id: str) -> str:
    """Determine which language phase a member is in.

    Returns: "arabic" | "bilingual_ar" | "bilingual"

    Only applies when 'bawaba_gradual_english' flag is enabled.
    When the flag is OFF, always returns "bilingual" (current behavior).
    """
    if not database.is_feature_enabled("bawaba_gradual_english"):
        return "bilingual"

    member = database.get_member(discord_id)
    if not member:
        return "bilingual"

    week = database.member_week_number(discord_id)
    if week <= 1:
        return "arabic"
    elif week <= 3:
        return "bilingual_ar"
    else:
        return "bilingual"


def bl_for_member(discord_id: str, en: str, ar: str) -> str:
    """Bilingual text helper that respects the member's language phase.

    - "arabic": shows Arabic only
    - "bilingual_ar": shows Arabic first, then English in parentheses
    - "bilingual": shows English + Arabic (current bl() behavior)

    Use this instead of raw bl() in bot responses that are seen by
    individual members (DMs, command responses). Scheduled posts to
    channels (daily tasks, leaderboards) still use the standard bl()
    since they're seen by all members at different phases.
    """
    phase = response_language(discord_id)
    if phase == "arabic":
        return ar
    elif phase == "bilingual_ar":
        return f"{ar} ({en})"
    else:
        return f"{en} / {ar}"


def done_response_for_member(discord_id: str, task_id: str, result: dict) -> str:
    """Generate the !done response message respecting the member's language phase.

    Bawaba B5: week 1 students get full Arabic, week 2-3 get Arabic-first
    bilingual, week 4+ get the current English+Arabic format.
    """
    phase = response_language(discord_id)

    task_names_ar = {
        "accent": "تدريب النطق",
        "vocab": "المفردات",
        "shadow": "المحاكاة",
        "speaking": "مهمة الكلام",
        "listening": "الاستماع",
        "writing": "الكتابة",
        "community": "المشاركة المجتمعية",
    }
    task_name_ar = task_names_ar.get(task_id, task_id)
    bar = "█" * result["tasks_today"] + "░" * (7 - result["tasks_today"])

    if phase == "arabic":
        msg = f"✅ **{task_name_ar}** — أحسنت! 👏\n\n"
        msg += f"[{bar}] {result['tasks_today']}/7 النهاردة\n"
        msg += f"🔥 سلسلة: **{result['streak']}** يوم | +{result['points']} نقطة"
        if result["tasks_today"] == 7:
            msg += "\n\n🎉 **خلصت الـ 7 مهام! بونص إضافي!** 🏛️"
    elif phase == "bilingual_ar":
        msg = f"✅ **{task_name_ar}** ({task_id}) — أحسنت! 👏\n\n"
        msg += f"[{bar}] {result['tasks_today']}/7 النهاردة (today)\n"
        msg += f"🔥 سلسلة (Streak): **{result['streak']}** يوم | +{result['points']} نقطة (points)"
        if result["tasks_today"] == 7:
            msg += "\n\n🎉 **خلصت الـ 7 مهام! بونص إضافي!** (All 7 done! Bonus!) 🏛️"
    else:
        # Standard bilingual (week 4+)
        msg = (
            f"{result['feedback']}\n\n"
            f"[{bar}] {result['tasks_today']}/7 today\n"
            f"🔥 Streak: **{result['streak']}** days | +{result['points']} points"
        )
        if result["tasks_today"] == 7:
            msg += "\n\n🎉 **ALL 7 TASKS COMPLETE!** Bonus points earned!"

    return msg


# ============================================================
#  2. PRIVACY NOTICE
# ============================================================

PRIVACY_NOTICE = """🏛️ **سياسة الخصوصية — Empire English Community**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**ما البيانات اللي بنجمعها:**
• اسم المستخدم على Discord
• التسجيلات الصوتية اللي بترفعها (للتقييم)
• النصوص اللي بتكتبها (للتصحيح)
• نقاطك واستمراريتك ومستواك

**ليه بنجمعها:**
• عشان نتابع تقدمك
• عشان AI يقدر يديك feedback
• عشان نحسن النظام

**فين بتتخزن:**
• قاعدة بيانات مشفرة على سيرفر خاص
• التسجيلات بتتحذف بعد 12 شهر من آخر نشاط

**حقوقك:**
• تقدر تطلب حذف كل بياناتك في أي وقت
• ابعت رسالة في `#support` وهنحذفها خلال 7 أيام
• تقدر تطلب نسخة من بياناتك

**الحد الأدنى للعمر:** 16 سنة

**موافقة التسجيل الصوتي:**
بمجرد رفعك تسجيل صوتي في أي قناة، انت موافق إن AI يحلله ويديك feedback.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Privacy Policy Summary (English):**
We collect: username, voice recordings (for evaluation), text submissions (for correction), points/streaks/level data.
Purpose: track progress, deliver AI feedback, improve the system.
Storage: encrypted database, recordings deleted after 12 months of inactivity.
Your rights: request deletion anytime via #support (7-day processing).
Minimum age: 16.
By uploading voice recordings, you consent to AI analysis.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*Empire English Community — Common Sense First.* 🏛️"""


# ============================================================
#  3. WEEKLY FEEDBACK SURVEY (Friday DM)
# ============================================================

FEEDBACK_QUESTIONS = [
    "1️⃣ قيّم المهام اليومية هذا الأسبوع (1-10):\nHow useful were this week's tasks? (1-10)",
    "2️⃣ إيه أصعب حاجة واجهتك؟\nWhat was the hardest part this week?",
    "3️⃣ إيه اللي تحب تتغير؟\nWhat would you change?",
]


async def send_weekly_feedback_survey(guild: discord.Guild):
    """Send 3-question feedback survey to all active members (Friday evening)."""
    members = database.all_active_members()
    sent = 0
    for m in members:
        discord_member = guild.get_member(int(m["discord_id"]))
        if not discord_member:
            continue
        try:
            await discord_member.send(
                "📋 **استبيان أسبوعي — Empire English**\n\n"
                "رأيك مهم! جاوب على الـ 3 أسئلة دول:\n\n" +
                "\n\n".join(FEEDBACK_QUESTIONS) +
                "\n\n*ابعت إجاباتك هنا (reply to this DM)*"
            )
            sent += 1
        except discord.Forbidden:
            pass
    logger.info(f"Feedback survey sent to {sent} members")


# ============================================================
#  4. SPACED REPETITION (enhanced quiz)
# ============================================================

def get_spaced_repetition_words(discord_id: str, count: int = 5) -> list[dict]:
    """Get words from previous weeks for review (spaced repetition).
    Returns words from week-1, week-2, and week-3 for review, at the
    member's OWN level (previously this defaulted to "L0" for everyone).
    """
    member = database.get_member(discord_id)
    if not member:
        return []
    level = member["level"]
    week = database.member_week_number(discord_id)
    review_words = []
    for prev_week in range(max(1, week - 3), week):
        words = curriculum.get_vocabulary_for_week(prev_week, level)
        if words:
            review_words.extend(random.sample(words, min(3, len(words))))
    return review_words[:count]


# ============================================================
#  5. WEEKLY PROGRESS REPORT (Monday DM)
# ============================================================

async def send_weekly_progress_report(guild: discord.Guild):
    """Send personalized progress report to each member (Monday morning)."""
    from . import tasks as task_engine

    members = database.all_active_members()
    sent = 0
    for m in members:
        discord_member = guild.get_member(int(m["discord_id"]))
        if not discord_member:
            continue

        completion = task_engine.calculate_completion_rate(m["discord_id"])
        current_streak, longest = database.get_streak(m["discord_id"])
        week = database.member_week_number(m["discord_id"])
        latest = database.get_latest_assessment(m["discord_id"])

        # Build visual bars
        comp_bar = "█" * int(completion / 10) + "░" * (10 - int(completion / 10))

        msg = (
            f"📊 **تقرير الأسبوع — Week {week}**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📈 نسبة الإنجاز: [{comp_bar}] **{completion}%**\n"
            f"🔥 Streak: **{current_streak}** يوم (أطول: {longest})\n"
            f"🏆 النقاط: **{m['total_points']}**\n"
        )

        if latest:
            msg += f"📝 آخر تقييم: **{latest['overall_score']:.0f}%** ({latest.get('rating', '')})\n"

        # Encouragement based on performance
        if completion >= 80:
            msg += "\n🌟 أداء ممتاز! استمر كده."
        elif completion >= 60:
            msg += "\n💪 كويس! حاول تزود شوية الأسبوع الجاي."
        elif completion >= 40:
            msg += "\n⚠️ محتاج تلتزم أكتر. حتى مهمة واحدة يوميًا أحسن من لا شيء."
        else:
            msg += "\n❗ الأسبوع ده كان ضعيف. هل محتاج مساعدة؟ كلمنا في #support"

        msg += "\n\n*النظام بيشتغل لما انت تشتغل. 🏛️*"

        try:
            await discord_member.send(msg)
            sent += 1
        except discord.Forbidden:
            pass

    logger.info(f"Weekly progress reports sent to {sent} members")


# ============================================================
#  6. GRAMMAR PATTERN CARD (Day 4 of each week)
# ============================================================

def format_grammar_card(week: int, level: str = "L0") -> str:
    """Format the grammar pattern card for posting in #cheat-sheets.
    Returns "" if this level has no grammar content authored yet — the
    caller (bot.py's grammar_card_delivery task) is expected to skip
    posting for that level rather than post an empty/broken card.
    """
    grammar = curriculum.get_grammar_pattern(week, level)
    if not grammar:
        return ""

    lines = [
        f"📖 **Grammar Pattern — Week {week}**",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"**{grammar.get('pattern_name', '')}**",
        f"*{grammar.get('pattern_name_ar', '')}*",
        "",
        f"**Formula:** `{grammar.get('formula', '')}`",
        f"**Visual:** `{grammar.get('formula_visual', '')}`",
        "",
        "**When to use:**",
        f"{grammar.get('when_to_use', '')}",
        "",
        "**بالعربي:**",
        f"{grammar.get('when_to_use_ar', '')}",
        "",
    ]

    examples = grammar.get("examples", [])
    if examples:
        lines.append("**Examples:**")
        for ex in examples[:5]:
            lines.append(f"  • {ex}")
        lines.append("")

    common_errors = grammar.get("common_errors", [])
    if common_errors:
        lines.append("**Common mistake (Arabic speakers):**")
        if isinstance(common_errors, list):
            for err in common_errors[:2]:
                if isinstance(err, dict):
                    lines.append(f"  ❌ {err.get('wrong', '')}")
                    lines.append(f"  ✅ {err.get('correct', '')}")
                else:
                    lines.append(f"  ⚠️ {err}")
        lines.append("")

    practice = grammar.get("practice_fill_blank", [])
    if practice:
        lines.append("**Practice (fill the blank):**")
        for p in practice[:3]:
            lines.append(f"  {p}")
        lines.append("")

    quick_rule = grammar.get("quick_rule", "")
    if quick_rule:
        lines.append(f"💡 **Quick rule:** {quick_rule}")
        quick_ar = grammar.get("quick_rule_ar", "")
        if quick_ar:
            lines.append(f"💡 **بالعربي:** {quick_ar}")

    return "\n".join(lines)


# ============================================================
#  7. ADVANCEMENT EXAM (!exam command)
# ============================================================

async def handle_exam_request(ctx, bot):
    """Handle !exam command — check eligibility and start exam flow."""
    member = database.get_member(str(ctx.author.id))
    if not member:
        await ctx.send("Not registered. Use `!join` first.")
        return

    level = member["level"]
    level_info = config.LEVELS.get(level, config.LEVELS["L0"])
    week = database.member_week_number(str(ctx.author.id))

    # Check minimum week requirement
    min_weeks = level_info.get("duration_weeks")
    if min_weeks and week < min_weeks[0]:
        await ctx.send(
            f"⏳ لسه مش جاهز للامتحان.\n"
            f"المستوى {level} يحتاج على الأقل **{min_weeks[0]} أسابيع**.\n"
            f"انت في الأسبوع {week}. استمر!"
        )
        return

    # Check last attempt (max 1 per month, and never while one is still
    # awaiting admin review — previously this check was unreachable
    # because nothing ever wrote a row to advancement_exams).
    last_attempt = database.last_advancement_attempt(str(ctx.author.id))
    if last_attempt:
        if last_attempt.get("status") == "pending":
            await ctx.send(
                "⏳ عندك امتحان قيد المراجعة بالفعل.\n"
                "هتوصلك النتيجة في DM خلال 48 ساعة."
            )
            return
        last_date = datetime.datetime.fromisoformat(last_attempt["attempted_at"])
        days_since = (datetime.datetime.now() - last_date).days
        if days_since < 30:
            await ctx.send(
                f"⏳ آخر محاولة كانت من {days_since} يوم.\n"
                f"تقدر تحاول تاني بعد **{30 - days_since}** يوم."
            )
            return

    # Eligible — send exam instructions via DM
    next_level = {"L0": "L1", "L1": "L2", "L2": "L3"}.get(level)
    if not next_level:
        await ctx.send("👑 انت في أعلى مستوى بالفعل! مستوى 3 هو مستوى الإتقان.")
        return

    try:
        await ctx.author.send(
            f"📋 **امتحان الترقية: {level} → {next_level}**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"الامتحان من 5 أقسام (60 دقيقة):\n\n"
            f"1️⃣ **Speaking** (10 min) — سجل 60 ثانية بدون تحضير\n"
            f"2️⃣ **Listening** (15 min) — 15 سؤال\n"
            f"3️⃣ **Vocabulary** (10 min) — 50 كلمة\n"
            f"4️⃣ **Accent** (5 min) — اقرأ passage + كلام حر\n"
            f"5️⃣ **Writing** (20 min) — اكتب فقرة\n\n"
            f"الحد الأدنى: **{level_info.get('advancement_score', 70)}%** في كل قسم\n\n"
            f"⚠️ الامتحان هيكون مع المؤسس في voice call.\n"
            f"ابعت رسالة في `#support` لتحديد الموعد.\n\n"
            f"*Good luck! 🏛️*"
        )
        await ctx.send("📩 تفاصيل الامتحان اتبعتلك في DM.")
    except discord.Forbidden:
        await ctx.send("❌ مقدرش أبعتلك DM. افتح الرسائل الخاصة.")


# ============================================================
#  8. BUDDY SYSTEM
# ============================================================

BUDDY_ELIGIBLE_ROLES = ["🏛️ Founder", "🛡️ Admin", "⚔️ Moderator", "🌟 سفير | Ambassador"]


def _eligible_buddies(guild: discord.Guild) -> list[discord.Member]:
    """Every non-bot member holding a buddy-eligible role, deduplicated.
    A member with multiple eligible roles (e.g. Founder is also Admin)
    is only counted once.
    """
    seen: dict[int, discord.Member] = {}
    for role_name in BUDDY_ELIGIBLE_ROLES:
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            continue
        for m in role.members:
            if not m.bot:
                seen[m.id] = m
    return list(seen.values())


async def assign_buddy(new_member: discord.Member, guild: discord.Guild):
    """Assign an onboarding buddy to a new member, rotating across every
    eligible buddy (Founder, Admin, Moderator, Ambassador) by current
    load rather than always picking the same single person.

    Previously this always picked founder_role.members[0] — literally
    the same one person for every new member, forever, regardless of
    how many other eligible people existed. That doesn't scale past a
    handful of members and silently overloads whoever happens to be
    role[0]. Fixed 2026-07-12, before any real students were invited,
    specifically so the first real cohort gets a working rotation from
    day one instead of a retrofit after buddies are already overloaded.

    Falls back to the old single-founder behavior only if no eligible
    buddy has ever been assigned anyone yet (cold start) or if the
    eligible pool is empty (misconfigured server) — in the latter case,
    no buddy is assigned and this is logged so an admin notices.
    """
    candidates = _eligible_buddies(guild)
    if not candidates:
        logger.warning(
            f"No eligible buddy found for {new_member.display_name} — "
            f"none of {BUDDY_ELIGIBLE_ROLES} have any members. No buddy assigned."
        )
        return

    # Pick whoever currently has the fewest active buddy assignments.
    loads = {m.id: database.count_buddy_load(str(m.id)) for m in candidates}
    buddy = min(candidates, key=lambda m: loads[m.id])

    # Bawaba B4: send a richer, more actionable buddy DM when the flag
    # is enabled — tells the buddy WHO joined, WHAT their first task is
    # today, and suggests sending a VOICE MESSAGE (not text) since the
    # new student might not be able to read English yet.
    if database.is_feature_enabled("bawaba_buddy_prompt"):
        # Get today's first task for L0 (the new member's level)
        first_task = config.DAILY_TASKS[0]  # accent drill (always first)
        try:
            await buddy.send(
                f"👋 **عضو جديد انضم: {new_member.display_name}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"انت الـ buddy بتاعه. **ابعتله رسالة صوتية** بالعربي\n"
                f"(اضغط مع الاستمرار على المايك في DM) وقوله:\n\n"
                f"• أهلاً بيك، أنا هساعدك\n"
                f"• أول مهمة ليك النهاردة: **{first_task['name_ar']}** ({first_task['name']})\n"
                f"• لما تخلصها اكتب `!1` في #bot-commands\n"
                f"• لو تايه اكتب `!مساعدة` أو كلمني\n\n"
                f"💡 *ليه صوتية؟ ممكن يكون أول مرة يتعلم إنجليزي —\n"
                f"رسالة صوتية بالعربي أسهل عليه من نص مكتوب.*\n\n"
                f"📊 عندك دلوقتي **{loads[buddy.id] + 1}** عضو تحت مسؤوليتك."
            )
        except discord.Forbidden:
            pass
    else:
        try:
            await buddy.send(
                f"👋 عضو جديد انضم: **{new_member.display_name}**\n"
                f"انت الـ buddy بتاعه. تواصل معاه خلال 12 ساعة.\n"
                f"*(عندك دلوقتي {loads[buddy.id] + 1} من الأعضاء تحت مسؤوليتك)*"
            )
        except discord.Forbidden:
            pass

    database.update_member(str(new_member.id), buddy_id=str(buddy.id))
    logger.info(
        f"Assigned buddy {buddy.display_name} to {new_member.display_name} "
        f"(buddy now has {loads[buddy.id] + 1} members)"
    )


# ============================================================
#  9. ENGLISH-ONLY DETECTION
# ============================================================

# Arabic Unicode range
_ARABIC_PATTERN = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]{3,}')

# Channels where Arabic is allowed
ARABIC_ALLOWED_CHANNELS = {"l0-questions", "support", "دليل-القنوات"}


async def check_english_only(message: discord.Message) -> bool:
    """Check if message contains Arabic in English-only channels.
    Returns True if a warning was sent (message violated rule).
    """
    if message.author.bot:
        return False

    channel_name = message.channel.name
    if channel_name in ARABIC_ALLOWED_CHANNELS:
        return False

    # Only enforce in text practice and community channels
    enforce_channels = {
        "general-chat", "introductions", "daily-word", "events",
        "l0-text-practice", "l1-text-practice", "l2-text-practice", "l3-text-practice",
    }
    if channel_name not in enforce_channels:
        return False

    # Check for Arabic text (more than 3 consecutive Arabic chars)
    if _ARABIC_PATTERN.search(message.content):
        # Check member's level for enforcement level
        member = database.get_member(str(message.author.id))
        level = member.get("level", "L0") if member else "L0"
        week = database.member_week_number(str(message.author.id)) if member else 1

        # L0 weeks 1-4: gentle reminder only
        if level == "L0" and week <= 4:
            try:
                await message.reply(
                    "💡 English only in this channel! Try in English:\n"
                    "*You can ask Arabic questions in `#l0-questions`*",
                    delete_after=30,
                )
            except Exception:
                pass
            return True
        else:
            # Stronger enforcement for L0 week 5+ and higher levels
            try:
                await message.reply(
                    "⚠️ **English only!** This channel is English-only.\n"
                    "*Arabic questions → `#l0-questions` or `#support`*",
                    delete_after=30,
                )
            except Exception:
                pass
            return True

    return False


# ============================================================
#  10. STREAK TRACKER AUTO-POST
# ============================================================

async def post_streak_tracker(guild: discord.Guild):
    """Post daily streak summary to #streak-tracker."""
    channel = discord.utils.get(guild.text_channels, name="streak-tracker")
    if not channel:
        return

    members = database.all_active_members()
    if not members:
        return

    # Sort by streak (descending)
    members.sort(key=lambda m: m["current_streak"], reverse=True)
    active_streaks = [m for m in members if m["current_streak"] > 0]

    if not active_streaks:
        return

    lines = [
        f"🔥 **Streak Tracker** — {datetime.date.today().strftime('%d %b')}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for m in active_streaks[:15]:
        fire = "🔥" * min(5, m["current_streak"] // 7 + 1)
        lines.append(f"{fire} **{m['discord_name']}** — {m['current_streak']} days")

    lines.append(f"\n*{len(active_streaks)} members with active streaks*")

    try:
        await channel.send("\n".join(lines))
    except Exception:
        pass


# ============================================================
#  11. LEADERBOARD AUTO-POST
# ============================================================

async def post_leaderboard(guild: discord.Guild):
    """Post weekly leaderboard to #leaderboard."""
    channel = discord.utils.get(guild.text_channels, name="leaderboard")
    if not channel:
        return

    rows = database.leaderboard(10)
    if not rows:
        return

    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    lines = [
        f"🏆 **Weekly Leaderboard** — {datetime.date.today().strftime('%d %b')}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for i, row in enumerate(rows):
        lvl = config.LEVELS.get(row["level"], config.LEVELS["L0"])
        lines.append(f"{medals[i]} **{row['discord_name']}** — {row['total_points']} pts {lvl['emoji']}")

    try:
        await channel.send("\n".join(lines))
    except Exception:
        pass


# ============================================================
#  12a. ADMIN "NEEDS ATTENTION" DASHBOARD (!attention)
# ============================================================
# Ties together data that already exists across the bot (inactivity,
# assessment trend, pending exams, buddy load) into a single ranked
# view for the owner/admin, instead of requiring several separate
# commands (!status, !members, !examqueue) to be checked manually.
# Deliberately read-only -- this command never sends DMs to students or
# changes any data, it only reports.

async def build_attention_report(guild: discord.Guild) -> str:
    """Build the !attention admin report: everyone who plausibly needs
    a human to look at them right now, ranked most urgent first."""
    lines = ["🔎 **Needs Attention — Empire English**", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]

    # --- 1. Pending advancement exams (already actionable via !examqueue,
    #    surfaced here too so this command is a genuine one-stop view) ---
    pending = database.pending_exams()
    if pending:
        lines.append(f"\n📋 **{len(pending)} exam(s) awaiting review:**")
        for e in pending[:5]:
            lines.append(f"  • #{e['id']} — {e.get('discord_name') or e['discord_id']} ({e['from_level']}→{e['to_level']})")
        if len(pending) > 5:
            lines.append(f"  ... and {len(pending) - 5} more (see `!examqueue`)")

    # --- 2. Inactive members, bucketed by severity (2/3/5/7+ days) ---
    # Reuses the same thresholds already defined in config, but actually
    # surfaces all of them (the scheduled streak_update loop currently
    # only ever acts on the 1-day bucket).
    all_members = database.all_active_members()
    buckets: dict[int, list[dict]] = {2: [], 3: [], 5: [], 7: []}
    for m in all_members:
        days = database.days_since_active(m)
        if days >= 7:
            buckets[7].append(m)
        elif days >= 5:
            buckets[5].append(m)
        elif days >= 3:
            buckets[3].append(m)
        elif days >= 2:
            buckets[2].append(m)

    any_inactive = any(buckets.values())
    if any_inactive:
        lines.append("\n⏰ **Inactive members:**")
        severity_labels = {
            7: "🔴 7+ days (membership_pause territory)",
            5: "🟠 5-6 days (needs a real conversation)",
            3: "🟡 3-4 days (moderator check-in)",
            2: "⚪ 2 days (buddy should reach out)",
        }
        for threshold in (7, 5, 3, 2):
            members = buckets[threshold]
            if not members:
                continue
            lines.append(f"  {severity_labels[threshold]}:")
            for m in members[:8]:
                buddy_note = ""
                if m.get("buddy_id"):
                    buddy = guild.get_member(int(m["buddy_id"]))
                    buddy_note = f" (buddy: {buddy.display_name if buddy else '?'})"
                lines.append(f"    • {m['discord_name']} — {database.days_since_active(m)}d inactive{buddy_note}")
            if len(members) > 8:
                lines.append(f"    ... and {len(members) - 8} more")

    # --- 3. Declining assessment trend (two weeks in a row getting worse) ---
    declining = database.declining_assessment_members()
    if declining:
        lines.append(f"\n📉 **{len(declining)} member(s) trending down (2 weeks in a row):**")
        for m in declining[:8]:
            lines.append(
                f"  • {m['discord_name']} — {m['previous_score']:.0f}% → {m['latest_score']:.0f}%"
            )

    # --- 4. Buddy load summary (so overload is visible before it happens) ---
    candidates = _eligible_buddies(guild)
    if candidates:
        loads = [(m, database.count_buddy_load(str(m.id))) for m in candidates]
        loads.sort(key=lambda pair: pair[1], reverse=True)
        lines.append("\n🤝 **Buddy load:**")
        # Found via load/scale testing: this section had no cap at all,
        # unlike every other section in this report (all use [:5]/[:8]).
        # At ~50+ eligible buddies (a plausible staff size for a growing
        # community, not just a synthetic extreme) the combined report
        # exceeds Discord's 2000-char message limit, and cmd_attention
        # only catches discord.Forbidden -- so ctx.author.send(report)
        # would raise discord.HTTPException uncaught. Same failure mode
        # already found and fixed for !orient's send_orientation_invite()
        # this session; capping here the same way the other sections
        # already do is simpler and more consistent than adding chunking
        # just for this one command.
        for m, load in loads[:15]:
            lines.append(f"  • {m.display_name}: {load} member(s)")
        if len(loads) > 15:
            lines.append(f"  ... and {len(loads) - 15} more")

    if len(lines) == 2:  # only the header + separator got added
        lines.append("\n✅ Nothing urgent right now.")

    return "\n".join(lines)


# ============================================================
#  12. AT-RISK MEMBER OUTREACH
# ============================================================

async def check_at_risk_members(guild: discord.Guild):
    """Check weekly assessment scores and trigger outreach for at-risk members."""
    members = database.all_active_members()
    for m in members:
        latest = database.get_latest_assessment(m["discord_id"])
        if not latest:
            continue

        score = latest.get("overall_score", 100)
        if score and score < 70:
            # At-risk: send supportive message
            discord_member = guild.get_member(int(m["discord_id"]))
            if not discord_member:
                continue

            buddy_id = m.get("buddy_id", "")
            try:
                await discord_member.send(
                    f"👋 مرحبًا {m['discord_name']}!\n\n"
                    f"لاحظنا إن آخر تقييم كان **{score:.0f}%**.\n"
                    f"ده مش مشكلة — كلنا بنمر بأوقات صعبة.\n\n"
                    f"💡 **اقتراحات:**\n"
                    f"• ركز على المهام اللي بتستمتع بيها\n"
                    f"• حتى 3 مهام يوميًا أحسن من لا شيء\n"
                    f"• ادخل voice lounge — الممارسة مع الناس بتفرق\n\n"
                    f"محتاج مساعدة؟ كلمنا في `#support` 🏛️"
                )
            except discord.Forbidden:
                pass

            # Notify buddy if assigned
            if buddy_id:
                buddy = guild.get_member(int(buddy_id))
                if buddy:
                    try:
                        await buddy.send(
                            f"⚠️ {m['discord_name']} at-risk (score: {score:.0f}%). "
                            f"Please check in with them."
                        )
                    except Exception:
                        pass



# ============================================================
#  13. DATA DELETION (!delete command)
# ============================================================

async def handle_delete_request(ctx, bot):
    """Handle !delete command — confirm and delete all member data."""
    member = database.get_member(str(ctx.author.id))
    if not member:
        await ctx.send("You're not registered. Nothing to delete.")
        return

    # Send confirmation
    await ctx.send(
        "⚠️ **طلب حذف بيانات**\n\n"
        "ده هيحذف كل بياناتك:\n"
        "• النقاط والمستوى\n"
        "• الاستمرارية (streak)\n"
        "• كل التقديمات السابقة\n"
        "• تقييماتك الأسبوعية\n\n"
        "**لتأكيد الحذف اكتب:** `!confirm-delete`\n"
        "*الحذف نهائي ومش ممكن يتراجع عنه.*"
    )


async def handle_confirm_delete(ctx, bot):
    """Actually delete all member data after confirmation."""
    discord_id = str(ctx.author.id)
    member = database.get_member(discord_id)
    if not member:
        await ctx.send("Nothing to delete.")
        return

    # Delete from database
    from . import config
    import sqlite3
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.execute("DELETE FROM daily_submissions WHERE discord_id=?", (discord_id,))
    conn.execute("DELETE FROM streaks WHERE discord_id=?", (discord_id,))
    conn.execute("DELETE FROM assessments WHERE discord_id=?", (discord_id,))
    conn.execute("DELETE FROM advancement_exams WHERE discord_id=?", (discord_id,))
    conn.execute("DELETE FROM points_log WHERE discord_id=?", (discord_id,))
    conn.execute("DELETE FROM members WHERE discord_id=?", (discord_id,))
    conn.commit()
    conn.close()

    # Remove level role
    if isinstance(ctx.author, discord.Member):
        for role in ctx.author.roles:
            if "Level" in role.name:
                try:
                    await ctx.author.remove_roles(role)
                except Exception:
                    pass

    await ctx.send(
        "✅ **تم حذف كل بياناتك بنجاح.**\n"
        "لو حبيت ترجع في أي وقت: `!join`"
    )
    logger.info(f"Data deleted for {ctx.author.display_name} ({discord_id})")


# ============================================================
#  14. MISSED DAY REPORT AUTOMATION
# ============================================================

async def post_missed_day_reminders(guild: discord.Guild):
    """Post gentle reminders in #missed-day-report for members who missed yesterday."""
    import datetime as dt

    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    channel = discord.utils.get(guild.text_channels, name="daily-check-in")
    if not channel:
        return

    members = database.all_active_members()
    missed = []
    for m in members:
        count = database.count_submissions_for_date(m["discord_id"], yesterday)
        if count == 0:
            missed.append(m)

    if not missed:
        return

    # Post a gentle group reminder (not individual shaming)
    msg = (
        f"📋 **أمس — {len(missed)} members missed tasks**\n\n"
        f"لو فاتك يوم مفيش مشكلة — المهم ترجع النهاردة.\n"
        f"حتى مهمة واحدة بتحافظ على الزخم. 💪\n\n"
        f"*Every day is a new chance. Come back stronger.*"
    )
    try:
        await channel.send(msg)
    except Exception:
        pass


# ============================================================
#  15. ORIENTATION SESSION TEMPLATE (auto-DM when scheduled)
# ============================================================

ORIENTATION_TEMPLATE = """🏛️ **جلسة التعريف — Empire English Community**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 **الموعد:** {date_time}
🔊 **المكان:** Voice channel `l0-voice-1`
⏱️ **المدة:** 30 دقيقة

**جدول الجلسة:**
1. (5 min) ترحيب + تعارف
2. (10 min) شرح النظام (7 مهام يومية + المستويات)
3. (5 min) عرض عملي: إزاي تستخدم البوت
4. (5 min) أسئلة
5. (5 min) تحديد الهدف الشخصي

**جهّز قبل الجلسة:**
• اكتب `!join <هدفك>` في #bot-commands
• حمّل Discord على الموبايل (لو مش محمّله)
• جهّز سماعة/مايك

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*حضور الجلسة إلزامي لكل عضو جديد.*
"""


async def send_orientation_invite(guild: discord.Guild, date_time_str: str):
    """Send orientation session invite to all members who haven't attended yet.

    Only caught discord.Forbidden before. Found via adversarial-input
    stress testing: !orient's admin-supplied date_time_str is inserted
    into ORIENTATION_TEMPLATE with no length check, and Discord hard-caps
    a single message at 2000 chars (raises discord.HTTPException, not
    Forbidden, if exceeded -- same failure mode tasks.py already
    documents fixing for daily_task_post(), just missed here). A
    date_time_str over ~1477 chars pushed the FIRST member's send() over
    the limit, which raised uncaught, aborted the whole loop, and left
    every remaining member with no invite at all -- silently, since the
    admin just sees cmd_orient's generic "An error occurred" with no clue
    how many (if any) actually went out. cmd_orient now also rejects an
    over-length date_time_str up front (see bot.py) so this is defense in
    depth, not the only guard.
    """
    message = ORIENTATION_TEMPLATE.format(date_time=date_time_str)
    members = database.all_active_members()
    sent = 0
    for m in members:
        discord_member = guild.get_member(int(m["discord_id"]))
        if not discord_member:
            continue
        try:
            await discord_member.send(message)
            sent += 1
        except (discord.Forbidden, discord.HTTPException):
            pass
    logger.info(f"Orientation invite sent to {sent} members")
    return sent


# ============================================================
#  16. RECRUITMENT MESSAGE TEMPLATE
# ============================================================

RECRUITMENT_MESSAGE_AR = """مرحبًا! 👋

بنبني نظام تعلم إنجليزي جديد — مش كورس عادي.
نظام يومي كامل مع مجتمع ونطق أمريكي من اليوم الأول.

🎯 محتاج 10 أشخاص فقط يجربونه مجانًا لمدة 8 أسابيع.

**في المقابل:**
• تلتزم بـ 45-60 دقيقة يوميًا
• تديني رأيك الصريح أسبوعيًا
• تسجّل تقدمك

**اللي هتحصل عليه:**
• نظام يومي مصمم لمستواك (7 مهام/يوم)
• تدريب نطق أمريكي من البداية
• مجتمع يدعمك + متابعة شخصية
• تقييم أسبوعي + خطة مخصصة
• AI يصحح كتابتك ونطقك فورًا

مجاني بالكامل. 10 مقاعد فقط.
مهتم؟ ابعتلي "أنا" 🏛️"""

RECRUITMENT_MESSAGE_EN = """Hey! 👋

We're building a new English learning system — not a course.
A daily system with community and American accent from day one.

🎯 Looking for 10 people to try it FREE for 8 weeks.

**In return:**
• Commit 45-60 min/day
• Give honest weekly feedback
• Track your progress

**You get:**
• Daily system designed for your level (7 tasks/day)
• American accent training from day 1
• Supportive community + personal follow-up
• Weekly assessment + personalized plan
• AI corrects your writing and pronunciation instantly

Completely free. 10 spots only.
Interested? Reply "I'm in" 🏛️"""


# ============================================================
#  18. SHADOWING & LISTENING RESOURCE LINKS
# ============================================================

SHADOWING_RESOURCES = {
    "L0": [
        {"title": "BBC Learning English - 6 Minute English", "url": "https://www.bbc.co.uk/learningenglish/english/features/6-minute-english", "speed": "slow"},
        {"title": "English with Lucy - Pronunciation", "url": "https://www.youtube.com/@EnglishwithLucy", "speed": "slow-medium"},
        {"title": "Rachel's English - American Pronunciation", "url": "https://www.youtube.com/@rachelsenglish", "speed": "slow"},
    ],
    "L1": [
        {"title": "TED-Ed - Short educational videos", "url": "https://www.youtube.com/@TEDEd", "speed": "medium"},
        {"title": "VOA Learning English", "url": "https://learningenglish.voanews.com/", "speed": "slow-medium"},
        {"title": "English Addict with Mr Duncan", "url": "https://www.youtube.com/@EnglishAddict", "speed": "medium"},
    ],
    "L2": [
        {"title": "TED Talks", "url": "https://www.ted.com/talks", "speed": "natural"},
        {"title": "NPR Podcasts", "url": "https://www.npr.org/podcasts", "speed": "natural"},
        {"title": "BBC World Service", "url": "https://www.bbc.co.uk/worldserviceradio", "speed": "natural"},
    ],
    "L3": [
        {"title": "The Daily (NYT Podcast)", "url": "https://www.nytimes.com/column/the-daily", "speed": "fast-natural"},
        {"title": "Freakonomics Radio", "url": "https://freakonomics.com/podcast/", "speed": "fast"},
        {"title": "Joe Rogan / Lex Fridman clips", "url": "https://www.youtube.com/@lexfridman", "speed": "fast-natural"},
    ],
}


def format_shadowing_resources(level: str) -> str:
    """Format shadowing resource recommendations for a level."""
    resources = SHADOWING_RESOURCES.get(level, SHADOWING_RESOURCES["L0"])
    lines = [f"🎧 **Shadowing Resources — {level}**\n"]
    for r in resources:
        lines.append(f"• [{r['title']}]({r['url']}) — Speed: {r['speed']}")
    lines.append("\n*Pick any clip (30-60 sec). Listen → Shadow 3x → Record #3.*")
    return "\n".join(lines)



# ============================================================
#  19. !TODAY COMMAND (personal remaining tasks)
# ============================================================

async def show_today(ctx):
    """Show what tasks remain for today with time estimate."""
    member = database.get_member(str(ctx.author.id))
    if not member:
        await ctx.send("مش مسجل. اكتب `!join` الأول.")
        return

    completed = database.tasks_completed_today(str(ctx.author.id))
    allowed = get_allowed_tasks_for_member(str(ctx.author.id))
    week = database.member_week_number(str(ctx.author.id))

    lines = [f"📅 **مهامك النهاردة — Week {week}**", "━━━━━━━━━━━━━━━━━━━━━━━━", ""]

    total_min = 0
    for task in config.DAILY_TASKS:
        tid = task["id"]
        if tid not in allowed:
            continue
        if tid in completed:
            lines.append(f"  ✅ ~~{task['emoji']} {task['name_ar']}~~")
        else:
            mins = 10 if member.get("level", "L0") == "L0" else 15
            total_min += mins
            lines.append(f"  ⬜ {task['emoji']} {task['name_ar']} — `!done {tid}`")

    lines.append("")
    done_count = len([t for t in allowed if t in completed])
    total_count = len(allowed)
    bar = "█" * done_count + "░" * (total_count - done_count)

    lines.append(f"[{bar}] {done_count}/{total_count}")

    if total_min > 0:
        lines.append(f"⏱️ الوقت المتبقي: ~{total_min} دقيقة")
    else:
        lines.append("🎉 **خلصت كل مهام النهاردة! أحسنت!**")

    await ctx.send("\n".join(lines))


# ============================================================
#  20. ARABIC BOT RESPONSES FOR L0
# ============================================================

def get_done_response_ar(task_id: str, result: dict) -> str:
    """Generate Arabic !done response for L0 students."""
    task_names_ar = {
        "accent": "تدريب النطق",
        "vocab": "المفردات",
        "shadow": "المحاكاة",
        "speaking": "مهمة الكلام",
        "listening": "الاستماع",
        "writing": "الكتابة",
        "community": "المشاركة المجتمعية",
    }
    task_name = task_names_ar.get(task_id, task_id)
    bar = "█" * result["tasks_today"] + "░" * (7 - result["tasks_today"])

    msg = f"✅ **{task_name}** — أحسنت! 👏\n\n"
    msg += f"[{bar}] {result['tasks_today']}/7 النهاردة\n"
    msg += f"🔥 Streak: **{result['streak']}** يوم | +{result['points']} نقطة"

    if result["tasks_today"] == 7:
        msg += "\n\n🎉 **خلصت الـ 7 مهام! بونص إضافي!** 🏛️"

    return msg


# ============================================================
#  21. PUBLIC CELEBRATION (all 7 tasks done)
# ============================================================

async def celebrate_completion(guild: discord.Guild, member_name: str, streak: int):
    """Post celebration in #daily-check-in when someone completes all 7 tasks."""
    channel = discord.utils.get(guild.text_channels, name="daily-check-in")
    if not channel:
        return
    try:
        await channel.send(
            f"🎉 **{member_name}** خلّص كل الـ 7 مهام النهاردة! 🔥 Streak: {streak} days\n"
            f"*Keep it up!* 🏛️"
        )
    except Exception:
        pass


async def celebrate_streak_milestone(guild: discord.Guild, member_name: str, days: int, bonus: int):
    """Post streak milestone celebration in #announcements."""
    channel = discord.utils.get(guild.text_channels, name="announcements")
    if not channel:
        channel = discord.utils.get(guild.text_channels, name="daily-check-in")
    if not channel:
        return
    try:
        await channel.send(
            f"🔥🔥🔥 **{member_name}** وصل **{days} يوم streak!** (+{bonus} bonus points)\n"
            f"*Consistency is the key to fluency.* 🏛️"
        )
    except Exception:
        pass


# ============================================================
#  22. VOICE SESSION SCHEDULE
# ============================================================

VOICE_SCHEDULE = """🔊 **جدول الجلسات الصوتية — Voice Sessions**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 **كل يوم أحد - خميس | Sunday - Thursday**
🕗 **الساعة 8:00 مساءً (توقيت دبي)**
📍 **المكان:** `l0-voice-1`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**القواعد:**
• مايك مطلوب (كاميرا اختيارية)
• إنجليزي فقط
• أقل مدة: 10 دقايق
• متكلمش أكتر من دقيقتين متواصل (اسمع غيرك)

**مش لازم تكون perfect!** الهدف إنك تتكلم.
حتى لو جملة واحدة — ده أحسن من سكوت. 🏛️

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*Voice sessions count as `!done community`*"""


# ============================================================
#  23. AUDIO/VIDEO RESOURCES FOR DAILY TASKS
# ============================================================

# Curated YouTube clips for L0 shadowing and listening (slow, clear, beginner)
L0_DAILY_CLIPS = {
    1: {  # Week 1: Greetings
        "shadowing": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "shadowing_title": "Easy English Conversations (A1) - Greetings",
        "listening": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "accent_model": "https://www.youtube.com/watch?v=n4NVPg2kHv4",
        "accent_title": "Rachel's English - P vs B sounds",
    },
    2: {  # Week 2: Numbers & Time
        "shadowing": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "shadowing_title": "Easy Conversations - Numbers & Time",
        "listening": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "accent_model": "https://www.youtube.com/watch?v=9GSLRI7kf3s",
        "accent_title": "Rachel's English - TH sounds (think/this)",
    },
    3: {  # Week 3: Family
        "shadowing": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "shadowing_title": "Easy Conversations - Family",
        "listening": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "accent_model": "https://www.youtube.com/watch?v=jPBGasJ7gxI",
        "accent_title": "Rachel's English - The Schwa Sound",
    },
    4: {  # Week 4: Home & Daily Life
        "shadowing": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "shadowing_title": "Easy Conversations - Daily Life",
        "listening": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "accent_model": "https://www.youtube.com/watch?v=V2MlOv7_lRs",
        "accent_title": "Rachel's English - R vs L",
    },
    5: {  # Week 5: Food & Shopping
        "shadowing": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "shadowing_title": "Easy Conversations - Shopping",
        "listening": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "accent_model": "https://www.youtube.com/watch?v=lEOsHCdKnvU",
        "accent_title": "Rachel's English - American R",
    },
    6: {  # Week 6: Places & Directions
        "shadowing": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "shadowing_title": "Easy Conversations - Directions",
        "listening": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "accent_model": "https://www.youtube.com/watch?v=Hfv4MTo3rCY",
        "accent_title": "Rachel's English - Word Stress",
    },
    7: {  # Week 7: Actions
        "shadowing": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "shadowing_title": "Easy Conversations - Actions",
        "listening": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "accent_model": "https://www.youtube.com/watch?v=pxlkUDiXJfI",
        "accent_title": "Rachel's English - Multi-syllable Stress",
    },
    8: {  # Week 8: Feelings
        "shadowing": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "shadowing_title": "Easy Conversations - Feelings",
        "listening": "https://www.youtube.com/watch?v=oolFQSzyHSg",
        "accent_model": "https://www.youtube.com/watch?v=dFOOQ59FXDo",
        "accent_title": "Rachel's English - Connected Speech",
    },
}


def get_daily_clip_links(week: int) -> dict:
    """Get audio/video clip links for a specific week."""
    return L0_DAILY_CLIPS.get(week, L0_DAILY_CLIPS[1])


# ============================================================
#  24. DM-BASED EXAM COLLECTION
# ============================================================

# Pending exams: {discord_id: {"stage": "speaking"|"writing"|"waiting", ...}}
_pending_exams: dict = {}


async def start_exam_collection(member: discord.Member):
    """Start collecting exam submissions via DM.

    NOTE: _pending_exams is intentionally still in-memory — it only tracks
    "which DM stage is this student on" (speaking vs writing), which is
    fine to lose on a bot restart (the student just re-runs !exam). What
    is NOT safe to keep in-memory is the actual submission content once
    collection completes — that is persisted to the database in
    handle_exam_dm() below via database.create_pending_exam().
    """
    from . import database
    m = database.get_member(str(member.id))
    from_level = m["level"] if m else "L0"
    to_level = {"L0": "L1", "L1": "L2", "L2": "L3"}.get(from_level, "L1")

    _pending_exams[str(member.id)] = {
        "stage": "speaking", "speaking": None, "writing": None,
        "from_level": from_level, "to_level": to_level,
    }
    try:
        await member.send(
            "📋 **امتحان الترقية — الجزء 1: Speaking**\n\n"
            "سجّل نفسك وانت بتتكلم عن هذا الموضوع:\n\n"
            "**\"Introduce yourself, talk about your daily routine, and what you learned.\"**\n\n"
            "⏱️ المدة: 60 ثانية على الأقل\n"
            "🎙️ **ابعت التسجيل هنا (في هذه المحادثة)**"
        )
    except discord.Forbidden:
        pass


async def handle_exam_dm(message: discord.Message) -> bool:
    """Handle exam submission in DM. Returns True if message was an exam submission."""
    from . import database
    discord_id = str(message.author.id)
    if discord_id not in _pending_exams:
        return False

    exam = _pending_exams[discord_id]

    if exam["stage"] == "speaking":
        # Check for audio attachment
        if message.attachments:
            exam["speaking"] = message.attachments[0].url
            exam["stage"] = "writing"
            await message.channel.send(
                "✅ **تم استلام التسجيل!**\n\n"
                "📋 **الجزء 2: Writing**\n\n"
                "اكتب فقرة (7 جمل على الأقل) عن:\n\n"
                "**\"Describe your daily routine from morning to evening.\"**\n\n"
                "✍️ **اكتب هنا:**"
            )
            return True
        else:
            await message.channel.send("🎙️ ابعت تسجيل صوتي (audio file) مش نص.")
            return True

    elif exam["stage"] == "writing":
        if len(message.content) >= 30:
            exam["writing"] = message.content
            exam["stage"] = "waiting"

            # Persist to the database NOW — this is the fix for the exam
            # flow's dead end. Previously the submission only ever lived
            # in this in-memory dict: nothing wrote it to the database,
            # so (a) the 30-day cooldown never actually engaged because
            # last_advancement_attempt() always saw zero rows, (b) no
            # admin was ever notified, and (c) a bot restart would lose
            # the submission with no trace.
            exam_id = database.create_pending_exam(
                discord_id,
                exam["from_level"],
                exam["to_level"],
                speaking_recording_url=exam["speaking"] or "",
                writing_submission=exam["writing"] or "",
            )

            await message.channel.send(
                "✅ **تم استلام الكتابة!**\n\n"
                "📊 الامتحان بتاعك هيتراجع خلال 48 ساعة.\n"
                "هتوصلك النتيجة هنا في DM.\n\n"
                "*Good luck! 🏛️*"
            )

            # Notify admins there's a real, actionable review pending —
            # previously this was a comment saying "handled in bot.py"
            # that pointed at code which did not exist anywhere.
            await notify_admins_of_pending_exam(
                message.author, exam_id, exam["from_level"], exam["to_level"],
                exam["speaking"] or "", exam["writing"] or "",
            )

            # Clear the in-memory DM-stage tracker — the durable record
            # now lives in the database as the source of truth.
            del _pending_exams[discord_id]
            return True
        else:
            await message.channel.send("✍️ محتاج 7 جمل على الأقل. حاول تاني.")
            return True

    return False


async def notify_admins_of_pending_exam(student: discord.User, exam_id: int,
                                        from_level: str, to_level: str,
                                        speaking_url: str, writing_text: str):
    """DM every admin (guild members with manage_guild permission) that an
    advancement exam is ready for review, with a direct link to the
    recording and the writing sample, plus the exact command to resolve it.
    """
    guild = student.mutual_guilds[0] if getattr(student, "mutual_guilds", None) else None
    if not guild:
        return
    admins = [m for m in guild.members if m.guild_permissions.manage_guild and not m.bot]
    summary = (
        f"📋 **Advancement Exam Ready for Review** (#{exam_id})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Student: **{student.display_name}** ({from_level} → {to_level})\n\n"
        f"🎙️ Speaking recording: {speaking_url or '(none)'}\n\n"
        f"✍️ Writing sample:\n> {writing_text[:800]}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"To resolve: `!examresult {exam_id} pass` or `!examresult {exam_id} fail`"
    )
    for admin in admins:
        try:
            await admin.send(summary)
        except discord.Forbidden:
            pass


def has_pending_exam(discord_id: str) -> bool:
    """Check if user is mid-DM-collection (speaking/writing stage)."""
    return discord_id in _pending_exams and _pending_exams[discord_id]["stage"] != "waiting"



# ============================================================
#  25. BAWABA B2: INTERACTIVE TUTORIAL QUEST (onboarding by doing)
# ============================================================

# Pending tutorials: {discord_id: {"step": 1-5, "completed": False}}
# Same in-memory pattern as _pending_exams — fine to lose on restart
# (the student just sees the welcome DM again on next join, or can
# trigger it via !tutorial).
_pending_tutorials: dict = {}

TUTORIAL_STEPS = {
    1: {
        "prompt": (
            "🏛️ **أهلاً بيك! خلينا نبدأ رحلتك في 5 خطوات سريعة.**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "**الخطوة 1:** اكتب الرقم `1` هنا\n"
            "*(ده هيبقى نفس الطريقة اللي تسجل بيها إنك خلصت مهمة)*"
        ),
        "accept": lambda msg: msg.strip() in ("1", "١"),
        "response": "✅ ممتاز! كده عرفت إزاي تكتب أمر. سهل صح؟ 🎉",
    },
    2: {
        "prompt": (
            "**الخطوة 2:** دلوقتي اكتب أول كلمة إنجليزي ليك:\n\n"
            "```hello```\n"
            "*(اكتبها زي ما هي)*"
        ),
        "accept": lambda msg: msg.strip().lower() in ("hello", "helo", "hllo"),
        "response": "✅ **hello** — أول كلمة إنجليزي ليك! 🏆 ده بدايتك.",
    },
    3: {
        "prompt": (
            "**الخطوة 3:** اكتب `!تقدم` عشان تشوف لوحة التقدم بتاعتك\n\n"
            "*(ده الأمر اللي بيوريك نقاطك وستريكك)*"
        ),
        "accept": lambda msg: msg.strip() in ("!تقدم", "!progress", "!تقدّم"),
        "response": "✅ شفت؟ ده مكانك — هنا هتشوف نقاطك كل يوم وهي بتزيد 📊",
    },
    4: {
        "prompt": (
            "**الخطوة 4:** اكتب `!مساعدة` عشان تشوف كل الأوامر المتاحة\n\n"
            "*(كلها بالعربي — مفيش إنجليزي مطلوب)*"
        ),
        "accept": lambda msg: msg.strip() in ("!مساعدة", "!helpar", "!help"),
        "response": "✅ تمام! دلوقتي عندك كل الأوامر. بكرة الساعة 6 هتلاقي مهامك.",
    },
    5: {
        "prompt": (
            "**الخطوة 5 (الأخيرة):** اكتب `!1` — ده هيبقى نفس الأمر\n"
            "اللي تكتبه بكرة لما تخلص أول مهمة.\n\n"
            "*(ده مجرد تمرين — مش هيسجل مهمة فعلية)*"
        ),
        "accept": lambda msg: msg.strip() in ("!1", "!تم", "!تم 1", "!done", "!done accent"),
        "response": None,  # handled specially (completion message)
    },
}

TUTORIAL_COMPLETION_MSG = (
    "🎉🎉🎉 **مبروك! خلصت رحلة التعريف!**\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "🏆 **+15 نقطة** — أول نقاط ليك!\n\n"
    "**ملخص اللي اتعلمته:**\n"
    "• `!1` إلى `!7` — لتسجيل المهام اليومية\n"
    "• `!تقدم` — لمتابعة نقاطك\n"
    "• `!مساعدة` — لكل الأوامر بالعربي\n\n"
    "**بكرة الساعة 6 الصبح:**\n"
    "هتلاقي مهام مرقمة في `#l0-daily-tasks`.\n"
    "اعمل المهمة → اكتب رقمها → خلاص! 🔥\n\n"
    "*System over instructor. Common Sense First.* 🏛️"
)


async def start_tutorial(member_or_user):
    """Start the interactive tutorial quest for a new member (DM-based).

    Called from on_member_join (when bawaba_tutorial flag is enabled) or
    from the reaction-based registration flow. Can also be triggered
    manually via !tutorial for students who want to redo it.
    """
    discord_id = str(member_or_user.id)

    # Don't restart if already in progress
    if discord_id in _pending_tutorials:
        return

    _pending_tutorials[discord_id] = {"step": 1, "completed": False}

    try:
        await member_or_user.send(TUTORIAL_STEPS[1]["prompt"])
    except discord.Forbidden:
        # Can't DM — clean up
        del _pending_tutorials[discord_id]


def has_pending_tutorial(discord_id: str) -> bool:
    """Check if user is mid-tutorial."""
    return discord_id in _pending_tutorials and not _pending_tutorials[discord_id]["completed"]


async def handle_tutorial_dm(message: discord.Message) -> bool:
    """Handle tutorial step responses in DM. Returns True if the message
    was consumed as a tutorial response (so other handlers skip it).

    Design: each step checks if the student's input matches the expected
    pattern (generous — accepts typos, Arabic numeral ١, etc.). On match,
    sends the response + the next step's prompt. On mismatch, sends a
    gentle Arabic nudge to try again. On the final step, awards points
    and marks the tutorial complete.
    """
    discord_id = str(message.author.id)
    if discord_id not in _pending_tutorials:
        return False

    tutorial = _pending_tutorials[discord_id]
    if tutorial["completed"]:
        return False

    current_step = tutorial["step"]
    step_data = TUTORIAL_STEPS.get(current_step)
    if not step_data:
        return False

    # Check if the input matches this step's acceptance criteria
    if step_data["accept"](message.content):
        # Step passed!
        if current_step < 5:
            # Send response + next step prompt
            response = step_data["response"]
            next_step = current_step + 1
            tutorial["step"] = next_step
            try:
                await message.channel.send(response)
                import asyncio
                await asyncio.sleep(1)
                await message.channel.send(TUTORIAL_STEPS[next_step]["prompt"])
            except discord.Forbidden:
                pass
        else:
            # Final step — completion!
            tutorial["completed"] = True
            try:
                await message.channel.send(TUTORIAL_COMPLETION_MSG)
            except discord.Forbidden:
                pass

            # Award points (once only — check if they already got tutorial points)
            from . import database
            # Use a simple flag in settings to prevent double-award
            already_done = database.get_setting(f"tutorial_done_{discord_id}", "")
            if not already_done:
                database.add_points(discord_id, config.POINTS_PER_TASK, "tutorial_quest")
                database.set_setting(f"tutorial_done_{discord_id}", "yes")

            # Clean up
            del _pending_tutorials[discord_id]
            logger.info(f"Bawaba B2: {message.author.display_name} completed tutorial quest (+15 pts)")

            # Tatawwur T0: prompt for Day 1 benchmark recording
            await prompt_day1_benchmark(message.author)

        return True
    else:
        # Didn't match — gentle nudge
        try:
            await message.channel.send(
                f"🔄 مش ده المطلوب. حاول تاني:\n\n"
                f"{step_data['prompt'].split('**')[-2] if '**' in step_data['prompt'] else 'حاول تاني'}"
            )
        except (discord.Forbidden, IndexError):
            pass
        return True



# ============================================================
#  26. BAWABA B6: #START-HERE CHANNEL CONTENT
# ============================================================

START_HERE_MESSAGE = """🏛️ **ابدأ من هنا — Empire English**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**مرحبًا!** ده أول مكان تبدأ منه.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 **3 خطوات وتبدأ:**

**1️⃣ سجّل نفسك**
└ روح `#bot-commands` واكتب: `!انضم`
└ أو اعمل ✅ على أي رسالة في السيرفر

**2️⃣ شوف مهامك اليومية**
└ كل يوم الساعة 6 الصبح في `#l0-daily-tasks`
└ 7 مهام مرقمة (كل مهمة 10 دقايق)

**3️⃣ سجّل إنك خلصت**
└ اكتب رقم المهمة: `!1` أو `!2` ... إلخ

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 **مش محتاج تعرف إنجليزي عشان تبدأ!**
كل الأوامر شغالة بالعربي.
اكتب `!مساعدة` في أي وقت لو محتاج مساعدة.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 **أوامر مهمة:**
• `!انضم` — سجل نفسك
• `!1` إلى `!7` — سجل مهمة
• `!تقدم` — شوف نقاطك
• `!مساعدة` — كل الأوامر

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*System over instructor. Common Sense First.* 🏛️"""



# ============================================================
#  27. NABD N3: REAL-TIME MILESTONE CELEBRATIONS
# ============================================================

_CELEBRATION_ALL_7 = [
    "🎉🎉🎉 **{name}** خلّص كل الـ 7 مهام النهاردة! بطل حقيقي! 🏛️",
    "🔥 **{name}** — السبع مهام تمام! ده مش عادي. استمر! 💪",
    "🏆 **{name}** ما شاء الله! كل المهام النهاردة! فخر المجتمع. 🏛️",
    "⭐ **{name}** خلّص كل حاجة! ده اللي بيفرق بين الناس والأبطال. 🔥",
]

_CELEBRATION_STREAK = [
    "🔥🔥🔥 **{name}** وصل **{days} يوم** streak! ده إصرار حقيقي! (+{bonus} نقطة)",
    "🏆 **{name}** — **{days} يوم** متواصل! مفيش حد يقدر يوقفك! (+{bonus} bonus)",
    "⚡ **{name}** streak: **{days} أيام**! الاستمرارية هي سر الطلاقة. (+{bonus} pts)",
]


async def send_milestone_celebration(guild, discord_id: str, milestone_type: str, **kwargs):
    """Nabd N3: send a celebration DM + optional public post.

    Called from process_submission() when a milestone is detected.
    milestone_type: 'all_7', 'streak', 'first_assessment'
    """
    if not database.is_feature_enabled("nabd_celebrations"):
        return

    prefs = database.get_notification_prefs(discord_id)
    if not prefs.get("celebrations", 1):
        return

    member = guild.get_member(int(discord_id))
    if not member:
        return

    m = database.get_member(discord_id)
    name = m["discord_name"] if m else member.display_name

    if milestone_type == "all_7":
        msg = random.choice(_CELEBRATION_ALL_7).format(name=name)
    elif milestone_type == "streak":
        msg = random.choice(_CELEBRATION_STREAK).format(
            name=name, days=kwargs.get("days", 0), bonus=kwargs.get("bonus", 0)
        )
    elif milestone_type == "first_assessment":
        msg = f"📊 **{name}** — أول تقييم أسبوعي ليك! أحسنت إنك بدأت تقيّم نفسك. 🏛️"
    else:
        return

    # Send DM
    try:
        await member.send(f"🏆 **مبروك!**\n\n{msg}")
    except discord.Forbidden:
        pass

    # Public post in #daily-check-in (for all_7 and streak)
    if milestone_type in ("all_7", "streak"):
        channel = discord.utils.get(guild.text_channels, name="daily-check-in")
        if channel:
            try:
                await channel.send(msg)
            except discord.HTTPException:
                pass


# ============================================================
#  28. NABD N5: ABSENCE RECOVERY LADDER
# ============================================================

async def check_absence_recovery(guild):
    """Nabd N5: check each member's absence level and send appropriate outreach.

    Called from a daily loop. Escalates:
      Day 2: bot DM (gentle)
      Day 3: buddy prompt
      Day 5: comeback mini-task DM
      Day 7+: final DM (already in !attention)
    """
    if not database.is_feature_enabled("nabd_absence_recovery"):
        return

    from . import tasks as task_engine
    today = task_engine.today_str()
    members = database.all_active_members()

    for m in members:
        discord_id = m["discord_id"]
        days_inactive = database.days_since_active(m)

        if days_inactive < 2:
            continue

        discord_member = guild.get_member(int(discord_id))
        if not discord_member:
            continue

        phase = response_language(discord_id)

        # Day 2: gentle bot DM
        if days_inactive >= 2 and not database.was_notification_sent(discord_id, "absence_day2", today):
            if database.was_notification_sent(discord_id, "absence_day2", (datetime.date.today() - datetime.timedelta(days=1)).isoformat()):
                continue  # already sent yesterday for this absence streak
            if phase == "arabic":
                msg = "👋 **مفتقدينك!**\n\nحتى مهمة واحدة النهاردة أحسن من لا شيء.\nاكتب `!1` وابدأ. 💪"
            else:
                msg = "👋 **We miss you!**\n\nEven one task today is better than none.\nType `!1` to start. 💪"
            try:
                await discord_member.send(msg)
                database.log_notification(discord_id, "absence_day2", today)
            except discord.Forbidden:
                pass

        # Day 3: buddy prompt
        elif days_inactive >= 3 and not database.was_notification_sent(discord_id, "absence_day3", today):
            buddy_id = m.get("buddy_id", "")
            if buddy_id:
                buddy = guild.get_member(int(buddy_id))
                if buddy:
                    try:
                        await buddy.send(
                            f"⚠️ **{m['discord_name']}** غايب من {days_inactive} أيام.\n"
                            f"ابعتله رسالة صوتية وشجعه يرجع. 🙏"
                        )
                    except discord.Forbidden:
                        pass
            database.log_notification(discord_id, "absence_day3", today)

        # Day 5: comeback mini-task
        elif days_inactive >= 5 and not database.was_notification_sent(discord_id, "absence_day5", today):
            if phase == "arabic":
                msg = (
                    "🌟 **مهمة رجوع سريعة (دقيقتين بس):**\n\n"
                    "اكتب جملة واحدة بالإنجليزي في `#general-chat`\n"
                    "ثم اكتب `!7`\n\n"
                    "كده بس! ده بيحسبلك مهمة ✅ وبيحافظ على نشاطك.\n"
                    "مش لازم تكون مثالي — المهم ترجع. 🏛️"
                )
            else:
                msg = (
                    "🌟 **Quick comeback task (2 minutes):**\n\n"
                    "Type one English sentence in `#general-chat`\n"
                    "Then type `!7`\n\n"
                    "That's it! It counts as a task ✅ and keeps you active.\n"
                    "You don't have to be perfect — just come back. 🏛️"
                )
            try:
                await discord_member.send(msg)
                database.log_notification(discord_id, "absence_day5", today)
            except discord.Forbidden:
                pass

        # Day 7+: final DM
        elif days_inactive >= 7 and not database.was_notification_sent(discord_id, "absence_day7", today):
            if phase == "arabic":
                msg = (
                    "💬 **مرحبًا {name}**\n\n"
                    "غبت عنا أسبوع كامل. كل حاجة لسه في مكانها — مستواك، نقاطك، كل شيء.\n"
                    "لو محتاج مساعدة أو عايز تتكلم، كلمنا في `#support`.\n\n"
                    "لو عايز ترجع — اكتب `!1` وابدأ من جديد. 🏛️"
                ).format(name=m["discord_name"])
            else:
                msg = (
                    "💬 **Hey {name}**\n\n"
                    "It's been a full week. Everything is still here — your level, your points, everything.\n"
                    "If you need help or want to talk, reach out in `#support`.\n\n"
                    "To come back — just type `!1` and start fresh. 🏛️"
                ).format(name=m["discord_name"])
            try:
                await discord_member.send(msg)
                database.log_notification(discord_id, "absence_day7", today)
            except discord.Forbidden:
                pass


# ============================================================
#  29. NABD N6: SOCIAL PROOF (opt-in)
# ============================================================

async def send_social_proof(guild, completer_discord_id: str):
    """Nabd N6: notify same-level peers (who opted in) that someone
    completed all 7 tasks. Max 1 per peer per day."""
    if not database.is_feature_enabled("nabd_social_proof"):
        return

    from . import tasks as task_engine
    today = task_engine.today_str()

    completer = database.get_member(completer_discord_id)
    if not completer:
        return

    level = completer["level"]
    peers = database.members_at_level(level)

    for peer in peers:
        peer_id = peer["discord_id"]
        if peer_id == completer_discord_id:
            continue  # don't notify yourself

        prefs = database.get_notification_prefs(peer_id)
        if not prefs.get("social_proof", 0):
            continue  # opted out (default OFF)

        if database.was_notification_sent(peer_id, "social_proof", today):
            continue  # max 1 per day

        # Skip if they already finished all tasks
        peer_completed = database.count_submissions_for_date(peer_id, today)
        if peer_completed >= 7:
            continue

        peer_member = guild.get_member(int(peer_id))
        if not peer_member:
            continue

        phase = response_language(peer_id)
        name = completer["discord_name"]
        if phase == "arabic":
            msg = f"👥 زميلك **{name}** خلّص كل مهامه النهاردة — يلا كمّل! 💪"
        else:
            msg = f"👥 Your peer **{name}** completed all tasks today — keep going! 💪"

        try:
            await peer_member.send(msg)
            database.log_notification(peer_id, "social_proof", today)
        except discord.Forbidden:
            pass



# ============================================================
#  30. TATAWWUR T0: VOICE PORTFOLIO INTEGRATION
# ============================================================

# The Day 1 benchmark sentence — same for every student (enables
# fair comparison over time). Short enough for a beginner, long enough
# to reveal pronunciation patterns.
DAY1_BENCHMARK_SENTENCE = "Hello, my name is... I am learning English. I want to speak like a native speaker."
DAY1_BENCHMARK_PROMPT_AR = (
    "🎙️ **آخر خطوة — سجّل صوتك!**\n\n"
    "ده أول تسجيل ليك — هنحفظه عشان بعد شهر تسمع نفسك وتشوف قد إيه اتحسنت.\n\n"
    "**اقرأ الجملة دي بصوت عالي وابعت تسجيل صوتي:**\n\n"
    f"```{DAY1_BENCHMARK_SENTENCE}```\n\n"
    "💡 *مش لازم تكون مثالي — ده مجرد نقطة البداية.*\n"
    "ابعت التسجيل هنا 👇"
)


async def handle_benchmark_recording(message) -> bool:
    """Handle a voice recording submitted after the Day 1 benchmark prompt.

    Called from on_message when a member in DM sends an attachment after
    their tutorial is complete but no benchmark exists yet.
    Returns True if the message was consumed as a benchmark submission.
    """
    if not database.is_feature_enabled("tatawwur_portfolio"):
        return False

    discord_id = str(message.author.id)

    # Only handle if: in DM, has attachment, no day1 benchmark yet
    if not isinstance(message.channel, discord.DMChannel):
        return False
    if not message.attachments:
        return False
    if database.has_day1_benchmark(discord_id):
        return False

    # Check if they were prompted (via a setting flag)
    if database.get_setting(f"benchmark_prompted_{discord_id}", "") != "yes":
        return False

    # Save the recording
    attachment = message.attachments[0]
    member = database.get_member(discord_id)
    level = member["level"] if member else "L0"
    week = database.member_week_number(discord_id) if member else 1

    database.save_voice_recording(
        discord_id,
        recording_url=attachment.url,
        recording_type="benchmark_day1",
        week=week,
        level=level,
        notes=DAY1_BENCHMARK_SENTENCE,
    )

    # Clear the prompt flag
    database.set_setting(f"benchmark_prompted_{discord_id}", "done")

    await message.channel.send(
        "✅ **تم حفظ تسجيلك الأول!** 🎉\n\n"
        "بعد 4 أسابيع هنطلب منك تسجل نفس الجملة تاني.\n"
        "وقتها هتقدر تسمع الفرق بنفسك. 📈\n\n"
        "اكتب `!صوتي` أو `!portfolio` في أي وقت عشان تشوف تسجيلاتك."
    )

    logger.info(f"Tatawwur T0: Day 1 benchmark saved for {message.author.display_name}")
    return True


async def prompt_day1_benchmark(member_or_user):
    """Send the Day 1 benchmark prompt after tutorial completion.

    Called from the tutorial quest completion handler. Sets a flag so
    handle_benchmark_recording knows to accept the next audio DM.
    """
    if not database.is_feature_enabled("tatawwur_portfolio"):
        return

    discord_id = str(member_or_user.id)
    if database.has_day1_benchmark(discord_id):
        return  # already done

    database.set_setting(f"benchmark_prompted_{discord_id}", "yes")

    try:
        import asyncio
        await asyncio.sleep(2)
        await member_or_user.send(DAY1_BENCHMARK_PROMPT_AR)
    except discord.Forbidden:
        pass
