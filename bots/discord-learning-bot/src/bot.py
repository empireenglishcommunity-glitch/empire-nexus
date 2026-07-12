"""Empire English Community Bot — Main Discord Bot.

The operational heart of the Learning Operating System. Handles:
  - Scheduled daily task delivery (6 AM) to level-specific channels
  - Scheduled weekly assessment prompts (Sunday 10 AM)
  - Member commands: !done, !progress, !streak, !top, !level, !help
  - Writing feedback pipeline (auto-evaluates submissions in #writing-feedback)
  - Streak tracking and leaderboard updates
  - Admin commands: !setlevel, !announce, !status, !reset

Commands:
  !join <goal>         Register and set your learning goal
  !done [task]         Mark a task as completed
  !progress            View your current progress dashboard
  !streak              View your streak info
  !top                 Leaderboard (points)
  !streaks             Leaderboard (streaks)
  !level               View your level info and advancement progress
  !week                View this week's curriculum focus
  !assess              Request this week's assessment (if Sunday)
  !help                Show all commands

Admin:
  !status              Bot and system status
  !attention           Ranked "who needs a human right now" report
  !setlevel @user L#   Set a member's level
  !announce <msg>      Broadcast to announcements
  !members             List all members with levels
"""
import asyncio
import datetime
import logging
import discord
from discord.ext import commands, tasks

from . import config, database, curriculum, tasks as task_engine, ai_engine, verification, features

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("empire-bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents, help_command=None)



# ============================================================
#  TIMEZONE HELPER
# ============================================================

def _zone():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(config.TIMEZONE)
    except Exception:
        return datetime.timezone.utc


def _level_role_name(level: str) -> str:
    """Get the Discord role name for a level."""
    role_map = {"L0": "\U0001f331 Level 0 | \u0645\u0628\u062a\u062f\u0626", "L1": "\U0001f4aa Level 1 | \u0645\u062a\u0642\u062f\u0645", "L2": "\U0001f680 Level 2 | \u0645\u062a\u0648\u0627\u0635\u0644", "L3": "\U0001f451 Level 3 | \u0637\u0644\u064a\u0642"}
    return role_map.get(level, "\U0001f331 Level 0 | \u0645\u0628\u062a\u062f\u0626")


async def _get_or_create_role(guild: discord.Guild, role_name: str) -> discord.Role:
    """Get a role by name or create it if missing."""
    role = discord.utils.get(guild.roles, name=role_name)
    if not role:
        role = await guild.create_role(name=role_name)
    return role


async def _assign_level_role(member: discord.Member, new_level: str):
    """Remove old level roles and assign the new one."""
    guild = member.guild
    # Remove all level roles
    for lvl in ["L0", "L1", "L2", "L3"]:
        role_name = _level_role_name(lvl)
        role = discord.utils.get(guild.roles, name=role_name)
        if role and role in member.roles:
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                pass
    # Add new level role
    new_role = await _get_or_create_role(guild, _level_role_name(new_level))
    try:
        await member.add_roles(new_role)
    except discord.Forbidden:
        logger.warning(f"Cannot assign role {new_level} to {member.display_name}")


def _find_channel(guild: discord.Guild, name: str):
    """Find a text channel by name."""
    return discord.utils.get(guild.text_channels, name=name)


# ============================================================
#  BOT EVENTS
# ============================================================

@bot.event
async def on_ready():
    database.init_db()
    # Load curriculum data from JSON files
    from . import curriculum
    curriculum.load_all()
    cstats = curriculum.stats()
    logger.info(f"Curriculum: {cstats['total_vocabulary']} words, {cstats['total_speaking_missions']} speaking, {cstats['accent_weeks']} accent weeks")
    logger.info(f"Bot online: {bot.user} | v{config.BOT_VERSION} | {len(bot.guilds)} server(s)")
    if not daily_task_post.is_running():
        daily_task_post.start()
    if not weekly_assessment.is_running():
        weekly_assessment.start()
    if not streak_update.is_running():
        streak_update.start()
    if not friday_feedback_survey.is_running():
        friday_feedback_survey.start()
    if not monday_progress_report.is_running():
        monday_progress_report.start()
    if not grammar_card_delivery.is_running():
        grammar_card_delivery.start()
    if not daily_streak_post.is_running():
        daily_streak_post.start()
    if not weekly_leaderboard_post.is_running():
        weekly_leaderboard_post.start()
    if not at_risk_check.is_running():
        at_risk_check.start()
    if not missed_day_report.is_running():
        missed_day_report.start()


@bot.event
async def on_member_join(member: discord.Member):
    """Auto-register new members and send welcome DM with full manual."""
    database.register_member(str(member.id), member.display_name)
    # Assign buddy
    await features.assign_buddy(member, member.guild)
    try:
        # Message 1: Welcome + First Steps
        await member.send(
            f"🏛️ **أهلًا بيك في Empire English Community, {member.display_name}!**\n\n"
            f"ده مش كورس عادي. ده **نظام تعلّم يومي** هيخليك تتكلم إنجليزي بلهجة أمريكية صح.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🚀 **أول 5 دقايق — ابدأ من هنا:**\n\n"
            f"1️⃣ اقرأ قناة `#rules` واقبل القوانين\n"
            f"2️⃣ روح `#bot-commands` واكتب:\n"
            f"```!join هدفي أتكلم إنجليزي بطلاقة```\n"
            f"3️⃣ كل يوم الساعة 6 الصبح — شوف `#l0-daily-tasks`\n"
            f"4️⃣ بعد ما تخلص المهمة اكتب: `!done accent`\n"
            f"5️⃣ شوف تقدمك: `!progress`"
        )
        await asyncio.sleep(2)

        # Message 2: Daily Tasks + Commands (with verification info)
        await member.send(
            "📅 **الروتين اليومي (7 مهام — 45 دقيقة بس):**\n\n"
            "🎯 تدريب النطق — سجل صوتك في `#l0-showcase` ← ثم `!done accent`\n"
            "📖 مفردات جديدة — `!done vocab` ← البوت هيسألك سؤال\n"
            "🎧 المحاكاة (Shadowing) — سجل 30 ثانية في `#l0-showcase` ← ثم `!done shadow`\n"
            "🎙️ مهمة الكلام — سجل صوتك في `#l0-showcase` ← ثم `!done speaking`\n"
            "👂 تمرين الاستماع — `!done listening` ← البوت هيسألك سؤال\n"
            "✍️ تمرين الكتابة — اكتب في `#l0-text-practice` ← ثم `!done writing`\n"
            "💬 مشاركة مجتمعية — اكتب في `#general-chat` أو ادخل voice 10 دقايق ← ثم `!done community`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ **مهم:** لازم تعمل المهمة الأول وبعدين تكتب `!done`\n"
            "البوت بيتأكد إنك فعلاً عملت المهمة قبل ما يديك النقاط."
        )
        await asyncio.sleep(2)

        # Message 3: Levels + Points
        await member.send(
            "🏆 **نظام المستويات:**\n\n"
            "🌱 **Level 0** — مبتدئ (8-12 أسبوع)\n"
            "   الهدف: تعريف نفسك في 60 ثانية\n\n"
            "💪 **Level 1** — النجاة (10-14 أسبوع)\n"
            "   الهدف: مونولوج 2 دقيقة بدون تحضير\n\n"
            "🚀 **Level 2** — التواصل (12-16 أسبوع)\n"
            "   الهدف: عرض 5 دقايق عن أي موضوع\n\n"
            "👑 **Level 3** — الطلاقة (مستمر)\n"
            "   كلام طبيعي بلهجة أمريكية\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔥 **النقاط:** كل مهمة = 15 نقطة | الـ 7 مهام = +100 بونص\n"
            "🔥 **Streaks:** 7 أيام = +200 | 30 يوم = +1000 | 100 يوم = +5000"
        )
        await asyncio.sleep(2)

        # Message 4: Channel Guide
        await member.send(
            "🗺️ **خريطة القنوات المهمة:**\n\n"
            "⭐ `#bot-commands` — اكتب كل الأوامر هنا\n"
            "⭐ `#l0-daily-tasks` — المهام اليومية (6 صباحًا)\n"
            "📝 `#l0-text-practice` — تمارين الكتابة\n"
            "🎙️ `#l0-showcase` — شارك تسجيلاتك\n"
            "❓ `#l0-questions` — أسئلة (عربي مسموح هنا)\n"
            "🔊 `l0-voice-1` — غرفة صوتية للتمرين\n"
            "💬 `#general-chat` — دردشة إنجليزي\n"
            "📖 `#daily-word` — كلمة اليوم\n"
            "🎙️ `#speaking-feedback` — ارفع تسجيل ← AI يرد عليك\n"
            "📊 `#daily-check-in` — سجل خطتك كل صباح\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏛️ **خلاصة:** ادخل كل يوم. اعمل الـ 7 مهام. اكتب `!done`. بس كده.\n"
            "النظام هيعمل الباقي. 💪\n\n"
            "*System over instructor. Common Sense First.* 🏛️"
        )
    except discord.Forbidden:
        pass  # DMs disabled by user


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🔒 You don't have permission for this command.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`. Type `!help` for usage.")
        return
    logger.error(f"Command error in !{ctx.command}: {error}")
    await ctx.send("⚠️ An error occurred. Please try again or contact a moderator.")


@bot.event
async def on_voice_state_update(member, before, after):
    """Track voice channel time for community task verification."""
    if member.bot:
        return
    # Joined a voice channel
    if before.channel is None and after.channel is not None:
        verification.on_voice_join(str(member.id))
    # Left a voice channel
    elif before.channel is not None and after.channel is None:
        verification.on_voice_leave(str(member.id))




# ============================================================
#  SCHEDULED TASKS
# ============================================================

@tasks.loop(time=datetime.time(hour=config.DAILY_TASK_HOUR, tzinfo=_zone()))
async def daily_task_post():
    """Post daily tasks to each level's task channel at configured hour."""
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    for level_key in ["L0", "L1", "L2", "L3"]:
        members = database.members_at_level(level_key)
        if not members:
            continue

        # Determine the week (use first member's week — all same level start similarly)
        week = database.member_week_number(members[0]["discord_id"])

        # Generate tasks
        task_data = await task_engine.generate_daily_tasks(level_key, week)
        # Send as multiple messages if needed — a single combined string
        # (the old format_daily_post() behavior) is frequently well over
        # Discord's 2000-char message limit (up to ~3600 chars for L3),
        # which previously made channel.send() raise discord.HTTPException
        # on most days; that exception was only logged, so daily tasks were
        # likely silently failing to post for most level/week combinations.
        message_chunks = task_engine.format_daily_post_chunks(task_data)

        # Find the channel
        channel_name = f"l{level_key[1]}-daily-tasks"
        channel = _find_channel(guild, channel_name)
        if channel:
            try:
                for chunk in message_chunks:
                    await channel.send(chunk)
                logger.info(f"Posted daily tasks to #{channel_name} (week {week}, {len(message_chunks)} message(s))")
            except discord.HTTPException as e:
                logger.error(f"Failed to post to #{channel_name}: {e}")


@tasks.loop(time=datetime.time(hour=config.WEEKLY_ASSESSMENT_HOUR, tzinfo=_zone()))
async def weekly_assessment():
    """Send weekly assessment prompts every Sunday."""
    if _now().weekday() != 6:  # 6 = Sunday
        return

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    members = database.all_active_members()
    for member_data in members:
        discord_member = guild.get_member(int(member_data["discord_id"]))
        if not discord_member:
            continue

        week_num = database.member_week_number(member_data["discord_id"])

        try:
            await discord_member.send(
                f"📊 **WEEKLY ASSESSMENT — Week {week_num}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Complete these tasks today (30 min total):\n\n"
                f"1️⃣ **SPEAKING** (5 min)\n"
                f"Record 60 seconds answering: \"What did you learn this week?\"\n\n"
                f"2️⃣ **WRITING** (8 min)\n"
                f"Write 5 sentences about your week in English.\n\n"
                f"3️⃣ **VOCABULARY** (5 min)\n"
                f"Type 10 words you learned this week with their meanings.\n\n"
                f"Submit everything in #writing-feedback or #speaking-feedback.\n"
                f"Use `!assess` when done to calculate your score.\n\n"
                f"⏰ Due by: Sunday 11:59 PM"
            )
        except discord.Forbidden:
            pass

    logger.info(f"Weekly assessments sent to {len(members)} members")


@tasks.loop(hours=1)
async def streak_update():
    """Hourly check for streak updates and inactive member interventions."""
    inactive = task_engine.check_inactive_members()
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    for action, members in inactive.items():
        if action == "dm_reminder":
            for m in members[:5]:  # Limit batch size
                discord_member = guild.get_member(int(m["discord_id"]))
                if discord_member:
                    try:
                        await discord_member.send(
                            f"👋 Hey {m['discord_name']}! We noticed you haven't been active. "
                            f"Even one task today keeps your streak alive. You got this! 🏛️"
                        )
                    except discord.Forbidden:
                        pass


def _now():
    """Current datetime helper (redefined at module level for tasks)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo(config.TIMEZONE))
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


# --- Additional Scheduled Tasks (from blueprint Phase 4-6) ---

@tasks.loop(time=datetime.time(hour=20, minute=0, tzinfo=_zone()))
async def friday_feedback_survey():
    """Send weekly feedback survey every Friday evening."""
    if _now().weekday() != 4:  # 4 = Friday
        return
    guild = bot.get_guild(config.GUILD_ID)
    if guild:
        await features.send_weekly_feedback_survey(guild)


@tasks.loop(time=datetime.time(hour=7, minute=0, tzinfo=_zone()))
async def monday_progress_report():
    """Send weekly progress report every Monday morning."""
    if _now().weekday() != 0:  # 0 = Monday
        return
    guild = bot.get_guild(config.GUILD_ID)
    if guild:
        await features.send_weekly_progress_report(guild)


@tasks.loop(time=datetime.time(hour=config.DAILY_TASK_HOUR, minute=30, tzinfo=_zone()))
async def grammar_card_delivery():
    """Post grammar pattern card on Day 4 of each week (Wednesday).

    Previously this only ever checked L0 members, so L1/L2/L3 students
    never received a grammar card regardless of content availability.
    Now loops over every level, same pattern as daily_task_post(), and
    silently skips a level if it has no grammar content authored yet
    (format_grammar_card returns "" in that case).
    """
    if _now().weekday() != 2:  # 2 = Wednesday
        return
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    channel = discord.utils.get(guild.text_channels, name="cheat-sheets")
    if not channel:
        logger.warning("grammar_card_delivery: #cheat-sheets channel not found")
        return

    for level_key in ["L0", "L1", "L2", "L3"]:
        members = database.members_at_level(level_key)
        if not members:
            continue

        week = database.member_week_number(members[0]["discord_id"])
        card = features.format_grammar_card(week, level_key)
        if not card:
            logger.info(f"No grammar card content for {level_key} week {week} — skipped")
            continue

        try:
            await channel.send(card)
            logger.info(f"Grammar card posted for {level_key} week {week}")
        except discord.HTTPException as e:
            logger.error(f"Failed to post grammar card for {level_key}: {e}")


@tasks.loop(time=datetime.time(hour=22, minute=0, tzinfo=_zone()))
async def daily_streak_post():
    """Post streak tracker summary every evening."""
    guild = bot.get_guild(config.GUILD_ID)
    if guild:
        await features.post_streak_tracker(guild)


@tasks.loop(time=datetime.time(hour=7, minute=30, tzinfo=_zone()))
async def weekly_leaderboard_post():
    """Post leaderboard every Sunday morning."""
    if _now().weekday() != 6:  # 6 = Sunday
        return
    guild = bot.get_guild(config.GUILD_ID)
    if guild:
        await features.post_leaderboard(guild)


@tasks.loop(time=datetime.time(hour=9, minute=0, tzinfo=_zone()))
async def at_risk_check():
    """Check for at-risk members every Monday."""
    if _now().weekday() != 0:  # 0 = Monday
        return
    guild = bot.get_guild(config.GUILD_ID)
    if guild:
        await features.check_at_risk_members(guild)


@tasks.loop(time=datetime.time(hour=8, minute=0, tzinfo=_zone()))
async def missed_day_report():
    """Post missed-day reminders every morning."""
    guild = bot.get_guild(config.GUILD_ID)
    if guild:
        await features.post_missed_day_reminders(guild)



# ============================================================
#  MEMBER COMMANDS
# ============================================================

@bot.command(name="join")
async def cmd_join(ctx, *, goal: str = ""):
    """Register as a community member."""
    is_new = database.register_member(str(ctx.author.id), ctx.author.display_name, goal=goal)
    if is_new:
        # Assign Level 0 role
        if isinstance(ctx.author, discord.Member):
            await _assign_level_role(ctx.author, "L0")
        msg = f"🌱 Welcome {ctx.author.mention}! You're registered at **Level 0**."
        if goal:
            msg += f"\n🎯 Goal: **{goal}**"
        msg += "\n\nYour daily tasks will appear in #l0-daily-tasks every morning."
    else:
        msg = f"✅ You're already registered, {ctx.author.mention}! Use `!progress` to check your status."
    await ctx.send(msg)


@bot.command(name="done")
async def cmd_done(ctx, task: str = None):
    """Mark a task as completed (with verification). Usage: !done accent / !done speaking / etc."""
    valid_tasks = [t["id"] for t in config.DAILY_TASKS]

    if not task:
        completed = database.tasks_completed_today(str(ctx.author.id))
        remaining = [t for t in valid_tasks if t not in completed]
        if not remaining:
            await ctx.send("🎉 All tasks done today! Amazing!")
            return
        await ctx.send(
            f"Which task? Use: `!done <task>`\n"
            f"Remaining: {', '.join(f'`{t}`' for t in remaining)}\n"
            f"Completed: {len(completed)}/7"
        )
        return

    task = task.lower().strip()
    if task not in valid_tasks:
        await ctx.send(f"❌ Unknown task. Valid: {', '.join(f'`{t}`' for t in valid_tasks)}")
        return

    # GRADUAL INTRO: Check if this task is unlocked for new members
    allowed = features.get_allowed_tasks_for_member(str(ctx.author.id))
    if task not in allowed:
        member = database.get_member(str(ctx.author.id))
        joined = datetime.datetime.fromisoformat(member["joined_at"]) if member else datetime.datetime.now()
        days = (datetime.datetime.now() - joined).days
        await ctx.send(
            f"🔒 مهمة `{task}` مش متاحة لسه.\n"
            f"انت في اليوم {days + 1}. المهام المتاحة ليك:\n"
            f"{', '.join(f'`{t}`' for t in allowed)}\n\n"
            f"*الـ 7 مهام هتكون متاحة من الأسبوع التاني.*"
        )
        return

    # Check if already done today
    completed_today = database.tasks_completed_today(str(ctx.author.id))
    if task in completed_today:
        await ctx.send(f"✅ You already submitted `{task}` today. Keep going!")
        return

    # TIME GATE: 5 min cooldown between !done commands
    allowed, remaining_secs = verification.check_cooldown(str(ctx.author.id))
    if not allowed:
        mins = remaining_secs // 60
        secs = remaining_secs % 60
        await ctx.send(f"⏳ استنى {mins}:{secs:02d} قبل ما تسجل مهمة تانية.\n(5 دقايق بين كل `!done`)")
        return

    # VOCAB: Two-step quiz flow
    if task == "vocab":
        question, answer, word = verification.generate_vocab_quiz(str(ctx.author.id))
        await ctx.send(f"📖 **اختبار مفردات:**\n\n{question}\n\n*اكتب إجابتك هنا:*")
        return  # Answer handled in on_message

    # LISTENING: Two-step quiz flow
    if task == "listening":
        prompt, answer = verification.generate_listening_quiz(str(ctx.author.id))
        await ctx.send(prompt)
        return  # Answer handled in on_message

    # OTHER TASKS: Verify proof exists
    if isinstance(ctx.author, discord.Member):
        passed, error_msg = await verification.verify_task(task, ctx.author, ctx.guild)
        if not passed:
            await ctx.send(f"❌ **لم يتم التحقق:**\n\n{error_msg}")
            return

    # PASSED VERIFICATION — process the submission
    verification.record_done_time(str(ctx.author.id))

    result = await task_engine.process_submission(
        str(ctx.author.id), ctx.author.display_name, task
    )

    if not result["new"]:
        await ctx.send(f"✅ You already submitted `{task}` today. Keep going!")
        return

    # Format response — Arabic for L0, English for higher
    member_data = database.get_member(str(ctx.author.id))
    level = member_data.get("level", "L0") if member_data else "L0"

    if level == "L0":
        msg = features.get_done_response_ar(task, result)
    else:
        bar = "█" * result["tasks_today"] + "░" * (7 - result["tasks_today"])
        msg = (
            f"{result['feedback']}\n\n"
            f"[{bar}] {result['tasks_today']}/7 today\n"
            f"🔥 Streak: **{result['streak']}** days | +{result['points']} points"
        )
        if result["tasks_today"] == 7:
            msg += "\n\n🎉 **ALL 7 TASKS COMPLETE!** Bonus points earned!"

    await ctx.send(msg)

    # PUBLIC CELEBRATION: all 7 tasks done
    if result["tasks_today"] == 7 and isinstance(ctx.author, discord.Member):
        await features.celebrate_completion(ctx.guild, ctx.author.display_name, result["streak"])

    # STREAK MILESTONE celebration
    if result["streak"] in config.STREAK_BONUS_POINTS and isinstance(ctx.author, discord.Member):
        bonus = config.STREAK_BONUS_POINTS[result["streak"]]
        await features.celebrate_streak_milestone(ctx.guild, ctx.author.display_name, result["streak"], bonus)


@bot.command(name="progress")
async def cmd_progress(ctx):
    """View your progress dashboard."""
    member = database.get_member(str(ctx.author.id))
    if not member:
        await ctx.send("You're not registered yet. Use `!join` to start.")
        return

    level_info = config.LEVELS.get(member["level"], config.LEVELS["L0"])
    week = database.member_week_number(str(ctx.author.id))
    completion = task_engine.calculate_completion_rate(str(ctx.author.id))
    completed_today = database.tasks_completed_today(str(ctx.author.id))
    bar = "█" * len(completed_today) + "░" * (7 - len(completed_today))

    latest = database.get_latest_assessment(str(ctx.author.id))
    score_line = f"📊 Last assessment: **{latest['overall_score']:.0f}%** ({latest['rating']})" if latest else "📊 No assessment yet"

    msg = (
        f"**{ctx.author.display_name}'s Progress**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{level_info['emoji']} Level: **{member['level']}** — {level_info['name']}\n"
        f"📅 Week: **{week}**\n"
        f"🎯 Goal: {member['goal'] or '—'}\n"
        f"🏆 Points: **{member['total_points']}**\n"
        f"🔥 Streak: **{member['current_streak']}** days (best: {member['longest_streak']})\n"
        f"📈 Completion rate (7 days): **{completion}%**\n"
        f"{score_line}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Today [{bar}] {len(completed_today)}/7\n"
        f"Track: {member['track']}"
    )
    await ctx.send(msg)


@bot.command(name="streak")
async def cmd_streak(ctx):
    """View your streak details."""
    current, longest = database.get_streak(str(ctx.author.id))
    completed = database.tasks_completed_today(str(ctx.author.id))
    bar = "█" * len(completed) + "░" * (7 - len(completed))

    msg = (
        f"🔥 **{ctx.author.display_name}'s Streak**\n\n"
        f"Current: **{current}** days\n"
        f"Longest ever: **{longest}** days\n"
        f"Today: [{bar}] {len(completed)}/7\n"
    )
    # Show next milestone
    for threshold, bonus in sorted(config.STREAK_BONUS_POINTS.items()):
        if current < threshold:
            msg += f"\n🎯 Next bonus: **{threshold}-day streak** (+{bonus} pts) — {threshold - current} days away"
            break

    await ctx.send(msg)



@bot.command(name="top")
async def cmd_top(ctx):
    """Points leaderboard."""
    rows = database.leaderboard(10)
    if not rows:
        await ctx.send("No members yet. Be the first to `!join`! 🌱")
        return
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    lines = ["🏆 **Points Leaderboard**\n"]
    for i, row in enumerate(rows):
        lvl = config.LEVELS.get(row["level"], config.LEVELS["L0"])
        lines.append(f"{medals[i]} {row['discord_name']} — {row['total_points']} pts {lvl['emoji']}")
    await ctx.send("\n".join(lines))


@bot.command(name="streaks")
async def cmd_streaks(ctx):
    """Streak leaderboard."""
    rows = database.streak_leaderboard(10)
    if not rows:
        await ctx.send("No streaks yet. Start with `!done`! 🔥")
        return
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    lines = ["🔥 **Streak Leaderboard**\n"]
    for i, row in enumerate(rows):
        lines.append(f"{medals[i]} {row['discord_name']} — {row['current_streak']} days (best: {row['longest_streak']})")
    await ctx.send("\n".join(lines))


@bot.command(name="level")
async def cmd_level(ctx):
    """View your level info and what's needed to advance."""
    member = database.get_member(str(ctx.author.id))
    if not member:
        await ctx.send("Not registered. Use `!join` first.")
        return

    level = member["level"]
    level_info = config.LEVELS[level]
    week = database.member_week_number(str(ctx.author.id))

    msg = (
        f"{level_info['emoji']} **Your Level: {level} — {level_info['name']}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 You're in week **{week}**\n"
        f"📖 Vocabulary target: {level_info['vocab_target']} words\n"
        f"🎙️ Speaking target: {level_info['speaking_target_seconds']} seconds\n"
        f"⏱️ Daily time ({member['track']}): ~{level_info['daily_minutes_core']} min\n"
    )
    if level_info["advancement_score"]:
        msg += (
            f"\n**To advance to the next level:**\n"
            f"• Pass the Exit Exam (minimum {level_info['advancement_score']}%)\n"
            f"• Available after week {level_info['duration_weeks'][0]} minimum\n"
            f"• All 5 exam sections must pass individually"
        )
    else:
        msg += "\n👑 Level 3 is the mastery level — no advancement. Pursue quarterly certification!"

    await ctx.send(msg)


@bot.command(name="week")
async def cmd_week(ctx):
    """View this week's curriculum focus (phonemes, vocab theme, etc.).

    BUG FIX (2026-07-11): this command previously read the member's level
    into a variable but never actually used it — it always pulled from
    config.PHONEME_WEEKS / config.VOCAB_THEMES, two hardcoded, L0-only
    dictionaries that predate the per-level curriculum.py system. An L1/L2/L3
    member running !week was silently shown L0's phoneme focus and vocab
    theme (e.g. "schwa" + "Family & People", L0's actual week 3 content),
    even though real, correct L1-L3 content already existed and loads fine
    for every other command. Found via live Discord testing after deploying
    the L1-L3 content fix — !week itself was never re-pointed at
    curriculum.py. Now uses the same level-aware functions as everywhere
    else (get_accent_focus, get_accent_focus_ar, get_theme, get_grammar_pattern).
    """
    member = database.get_member(str(ctx.author.id))
    if not member:
        await ctx.send("Not registered. Use `!join` first.")
        return

    week = database.member_week_number(str(ctx.author.id))
    level = member["level"]

    focus = curriculum.get_accent_focus(week, level)
    focus_ar = curriculum.get_accent_focus_ar(week, level)
    vocab_theme = curriculum.get_theme(week, level)
    grammar = curriculum.get_grammar_pattern(week, level)
    grammar_name = grammar.get("pattern_name") if grammar else None

    lines = [
        f"📅 **Week {week} Focus** ({level})",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if focus:
        lines.append(f"🎯 Accent focus: {focus}")
        if focus_ar:
            lines.append(f"   {focus_ar}")
    else:
        lines.append("🎯 Accent focus: content for this week is being finalized — check back soon.")
    lines.append(f"📖 Vocabulary theme: **{vocab_theme}**")
    if grammar_name:
        lines.append(f"📝 Grammar pattern: **{grammar_name}**")
    lines.append(
        f"🎙️ Speaking mission type: {config.SPEAKING_MISSION_TYPES.get(task_engine.current_day_name(), 'free_talk')}"
    )
    await ctx.send("\n".join(lines))


@bot.command(name="help")
async def cmd_help(ctx):
    """Show all available commands."""
    await ctx.send(
        "**🏛️ Empire English Bot — Commands**\n\n"
        "**Learning:**\n"
        "`!join <goal>` — Register and set your goal\n"
        "`!done <task>` — Mark a task done (with verification)\n"
        "`!today` — See your remaining tasks for today\n"
        "`!progress` — Your full progress dashboard\n"
        "`!streak` — Your streak details\n"
        "`!level` — Your level info and advancement requirements\n"
        "`!week` — This week's curriculum focus\n"
        "`!top` — Points leaderboard\n"
        "`!streaks` — Streak leaderboard\n\n"
        "**How `!done` works (verification):**\n"
        "🎯 `!done accent` — upload audio in #showcase first\n"
        "📖 `!done vocab` — bot asks you a word quiz\n"
        "🎧 `!done shadow` — upload 30s+ audio in #showcase first\n"
        "🎙️ `!done speaking` — upload audio in #showcase first\n"
        "👂 `!done listening` — bot asks a comprehension question\n"
        "✍️ `!done writing` — write in #text-practice first (20+ chars)\n"
        "💬 `!done community` — post in #general-chat or 10min voice\n"
        "⏳ 5 min cooldown between each `!done`\n\n"
        "**Admin:**\n"
        "`!status` — Bot status\n"
        "`!attention` — Ranked list of who needs a human right now (inactive, declining, pending exams, buddy load)\n"
        "`!setlevel @user L0/L1/L2/L3` — Set someone's level\n"
        "`!announce <message>` — Broadcast announcement\n"
        "`!members` — List all members\n"
        "`!orient <date/time>` — Send orientation invite\n"
        "`!recruit ar/en` — Get recruitment message template\n"
        "`!resources L0/L1/L2/L3` — Post shadowing resources\n"
        "`!examqueue` — List advancement exams awaiting review\n"
        "`!examresult <id> pass/fail` — Resolve an exam (auto-promotes on pass)\n\n"
        "**Account:**\n"
        "`!delete` — Request deletion of all your data\n"
        "`!exam` — Request level advancement exam\n"
    )



# ============================================================
#  WRITING FEEDBACK (auto-detect submissions in #writing-feedback)
# ============================================================

@bot.event
async def on_message(message: discord.Message):
    """Detect writing submissions, auto-evaluate, handle quiz answers, and enforce English-only."""
    # Don't respond to bot's own messages
    if message.author.bot:
        return

    # Handle exam DM submissions
    if isinstance(message.channel, discord.DMChannel):
        if features.has_pending_exam(str(message.author.id)):
            handled = await features.handle_exam_dm(message)
            if handled:
                return

    # English-only detection (before processing commands)
    await features.check_english_only(message)

    # Process commands first
    await bot.process_commands(message)

    # Handle pending VOCAB quiz answers
    if verification.has_pending_quiz(str(message.author.id)):
        if message.channel.name == "bot-commands" and not message.content.startswith("!"):
            passed, error_msg = verification.check_vocab_answer(str(message.author.id), message.content)
            if passed:
                # Process the vocab submission
                verification.record_done_time(str(message.author.id))
                result = await task_engine.process_submission(
                    str(message.author.id), message.author.display_name, "vocab"
                )
                bar = "█" * result["tasks_today"] + "░" * (7 - result["tasks_today"])
                await message.channel.send(
                    f"✅ **صح!** أحسنت {message.author.mention}!\n\n"
                    f"[{bar}] {result['tasks_today']}/7 today\n"
                    f"🔥 Streak: **{result['streak']}** days | +{result['points']} points"
                )
            else:
                await message.channel.send(f"{message.author.mention} {error_msg}")
            return

    # Handle pending LISTENING quiz answers
    if verification.has_pending_listening(str(message.author.id)):
        if message.channel.name == "bot-commands" and not message.content.startswith("!"):
            passed, error_msg = verification.check_listening_answer(str(message.author.id), message.content)
            if passed:
                verification.record_done_time(str(message.author.id))
                result = await task_engine.process_submission(
                    str(message.author.id), message.author.display_name, "listening"
                )
                bar = "█" * result["tasks_today"] + "░" * (7 - result["tasks_today"])
                await message.channel.send(
                    f"✅ **صح!** أحسنت {message.author.mention}!\n\n"
                    f"[{bar}] {result['tasks_today']}/7 today\n"
                    f"🔥 Streak: **{result['streak']}** days | +{result['points']} points"
                )
            else:
                await message.channel.send(f"{message.author.mention} {error_msg}")
            return

    # Auto-evaluate writing in #writing-feedback channel
    if message.channel.name == "writing-feedback" and len(message.content) > 30:
        member = database.get_member(str(message.author.id))
        if not member:
            return

        # Show typing indicator
        async with message.channel.typing():
            result = await ai_engine.evaluate_writing(
                submission=message.content,
                original_prompt="(submitted directly to #writing-feedback)",
                level=member["level"],
            )

        if result:
            # Log as writing task submission
            database.log_submission(
                str(message.author.id),
                task_engine.today_str(),
                "writing",
                content=message.content[:500],
                score=result.get("overall_score"),
                feedback=result.get("feedback_en", ""),
            )

            # Send feedback as reply
            feedback_msg = (
                f"📝 **Writing Feedback for {message.author.display_name}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Overall: **{result['overall_score']}/100** — {result.get('rating', '')}\n\n"
                f"{result.get('feedback_en', '')}\n\n"
                f"🎯 Focus: {result.get('one_thing_to_practice', '')}"
            )
            await message.reply(feedback_msg)


# ============================================================
#  ADVANCEMENT EXAM
# ============================================================

@bot.command(name="exam")
async def cmd_exam(ctx):
    """Request the level advancement exam."""
    await features.handle_exam_request(ctx, bot)
    # If eligible, start DM collection
    member = database.get_member(str(ctx.author.id))
    if member:
        level_info = config.LEVELS.get(member["level"], config.LEVELS["L0"])
        week = database.member_week_number(str(ctx.author.id))
        min_weeks = level_info.get("duration_weeks")
        if min_weeks and week >= min_weeks[0]:
            await features.start_exam_collection(ctx.author)


@bot.command(name="examresult")
@commands.has_permissions(manage_guild=True)
async def cmd_examresult(ctx, exam_id: int = None, result: str = None):
    """Resolve a pending advancement exam. Usage: !examresult <id> pass|fail

    Closes the loop that !exam previously left open: on 'pass' this
    actually calls database.set_level() and reassigns the Discord role
    (the same promotion logic !setlevel uses), then DMs the student.
    On 'fail' it DMs constructive next steps. Either way the exam row
    moves out of 'pending', which also releases the 30-day cooldown.
    """
    if exam_id is None or result not in ("pass", "fail"):
        await ctx.send("Usage: `!examresult <id> pass` or `!examresult <id> fail`")
        return

    exam = database.get_exam_by_id(exam_id)
    if not exam:
        await ctx.send(f"❌ No exam found with id `{exam_id}`.")
        return
    if exam["status"] != "pending":
        await ctx.send(f"⚠️ Exam #{exam_id} was already resolved as **{exam['status']}**.")
        return

    passed = result == "pass"
    database.resolve_exam(exam_id, passed, resolved_by=str(ctx.author.id))

    student = ctx.guild.get_member(int(exam["discord_id"]))

    if passed:
        database.set_level(exam["discord_id"], exam["to_level"])
        if student:
            await _assign_level_role(student, exam["to_level"])
        level_info = config.LEVELS.get(exam["to_level"], config.LEVELS["L0"])
        await ctx.send(
            f"✅ Exam #{exam_id}: **{exam['discord_id']}** passed → promoted to "
            f"**{exam['to_level']}** ({level_info['name']})"
        )
        if student:
            try:
                await student.send(
                    f"🎉 **مبروك! نجحت في امتحان الترقية!**\n\n"
                    f"انت دلوقتي في **{exam['to_level']} — {level_info['name']}** {level_info['emoji']}\n\n"
                    f"استمر! 🏛️"
                )
            except discord.Forbidden:
                pass
    else:
        await ctx.send(f"📋 Exam #{exam_id}: **{exam['discord_id']}** marked as failed. Stays at {exam['from_level']}.")
        if student:
            try:
                await student.send(
                    "📋 **نتيجة امتحان الترقية**\n\n"
                    "لسه مش وقتها. استمر في التمرين وحاول تاني بعد شهر.\n"
                    "ابعت `#support` لو عايز تفاصيل أكتر عن نقاط التحسين.\n\n"
                    "احنا معاك. 🏛️"
                )
            except discord.Forbidden:
                pass


@bot.command(name="examqueue")
@commands.has_permissions(manage_guild=True)
async def cmd_examqueue(ctx):
    """List all advancement exams awaiting review."""
    rows = database.pending_exams()
    if not rows:
        await ctx.send("✅ No exams pending review.")
        return
    lines = [f"📋 **Pending Exams ({len(rows)})**\n"]
    for r in rows:
        lines.append(
            f"#{r['id']} — {r.get('discord_name') or r['discord_id']} "
            f"({r['from_level']} → {r['to_level']}) — submitted {r['attempted_at']}"
        )
    lines.append("\nResolve with `!examresult <id> pass` or `!examresult <id> fail`")
    try:
        await ctx.author.send("\n".join(lines))
        await ctx.send("📩 Exam queue sent to your DMs.", delete_after=5)
    except discord.Forbidden:
        await ctx.send("\n".join(lines))


@bot.command(name="delete")
async def cmd_delete(ctx):
    """Request deletion of all your data."""
    await features.handle_delete_request(ctx, bot)


@bot.command(name="today")
async def cmd_today(ctx):
    """Show your remaining tasks for today."""
    await features.show_today(ctx)


@bot.command(name="confirm-delete")
async def cmd_confirm_delete(ctx):
    """Confirm data deletion."""
    await features.handle_confirm_delete(ctx, bot)


# ============================================================
#  ADMIN COMMANDS
# ============================================================

@bot.command(name="status")
@commands.has_permissions(manage_guild=True)
async def cmd_status(ctx):
    """Bot and system status (sent via DM to admin)."""
    member_count = database.member_count()
    today_subs = database.total_submissions_today()
    active_levels = {}
    for lvl in ["L0", "L1", "L2", "L3"]:
        active_levels[lvl] = len(database.members_at_level(lvl))

    msg = (
        f"**🤖 Empire English Bot Status**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Version: **{config.BOT_VERSION}**\n"
        f"Guilds: {len(bot.guilds)}\n"
        f"Members (registered): **{member_count}**\n"
        f"  🌱 L0: {active_levels['L0']} | 💪 L1: {active_levels['L1']} | "
        f"🚀 L2: {active_levels['L2']} | 👑 L3: {active_levels['L3']}\n"
        f"Submissions today: **{today_subs}**\n"
        f"Daily tasks: {'🟢 Running' if daily_task_post.is_running() else '🔴 Stopped'}\n"
        f"Assessments: {'🟢 Running' if weekly_assessment.is_running() else '🔴 Stopped'}\n"
        f"Gemini: {'🟢' if config.GEMINI_API_KEY else '🔴'} | "
        f"Groq: {'🟢' if config.GROQ_API_KEY else '⚪'}\n"
        f"Timezone: {config.TIMEZONE}\n"
        f"Task delivery: {config.DAILY_TASK_HOUR}:00"
    )
    try:
        await ctx.author.send(msg)
        await ctx.send("📩 Status sent to your DMs.", delete_after=5)
    except discord.Forbidden:
        await ctx.send(msg)


@bot.command(name="setlevel")
@commands.has_permissions(manage_guild=True)
async def cmd_setlevel(ctx, member: discord.Member = None, level: str = None):
    """Set a member's level. Usage: !setlevel @user L1"""
    if not member or not level:
        await ctx.send("Usage: `!setlevel @user L0/L1/L2/L3`")
        return
    level = level.upper()
    if level not in config.LEVELS:
        await ctx.send("❌ Invalid level. Use: L0, L1, L2, L3")
        return

    database.set_level(str(member.id), level)
    await _assign_level_role(member, level)
    level_info = config.LEVELS[level]
    await ctx.send(f"✅ {member.display_name} is now **{level}** — {level_info['emoji']} {level_info['name']}")


@bot.command(name="announce")
@commands.has_permissions(manage_guild=True)
async def cmd_announce(ctx, *, message: str = ""):
    """Send announcement to #announcements."""
    if not message:
        await ctx.send("Usage: `!announce <your message>`")
        return
    guild = ctx.guild
    channel = _find_channel(guild, "announcements")
    if channel:
        await channel.send(f"📢 **Announcement**\n\n{message}")
        await ctx.send(f"✅ Announcement sent to #{channel.name}")
    else:
        await ctx.send("❌ #announcements channel not found.")


@bot.command(name="attention")
@commands.has_permissions(manage_guild=True)
async def cmd_attention(ctx):
    """Ranked 'who needs a human right now' report: inactive members by
    severity, declining assessment trends, pending exams, and buddy
    load — combining signals that already exist across the bot into
    one view instead of several separate commands. Read-only, sent via
    DM (falls back to the channel if DMs are closed, same pattern as
    !status/!members)."""
    report = await features.build_attention_report(ctx.guild)
    try:
        await ctx.author.send(report)
        await ctx.send("📩 Attention report sent to your DMs.", delete_after=5)
    except discord.Forbidden:
        await ctx.send(report)


@bot.command(name="members")
@commands.has_permissions(manage_guild=True)
async def cmd_members(ctx):
    """List all registered members with their levels (sent via DM)."""
    members = database.all_active_members()
    if not members:
        await ctx.send("No registered members yet.")
        return
    lines = [f"**👥 Members ({len(members)})**\n"]
    for m in members[:20]:
        lvl = config.LEVELS.get(m["level"], config.LEVELS["L0"])
        streak_str = f"🔥{m['current_streak']}" if m["current_streak"] > 0 else ""
        lines.append(f"{lvl['emoji']} {m['discord_name']} — {m['level']} | {m['total_points']} pts {streak_str}")
    if len(members) > 20:
        lines.append(f"\n... and {len(members) - 20} more")
    try:
        await ctx.author.send("\n".join(lines))
        await ctx.send("📩 Members list sent to your DMs.", delete_after=5)
    except discord.Forbidden:
        await ctx.send("\n".join(lines))



# ============================================================
#  ADMIN: ORIENTATION & RECRUITMENT
# ============================================================

@bot.command(name="orient")
@commands.has_permissions(manage_guild=True)
async def cmd_orient(ctx, *, date_time: str = ""):
    """Send orientation invite to all members. Usage: !orient Saturday 7PM"""
    if not date_time:
        await ctx.send("Usage: `!orient Saturday 7PM Dubai time`")
        return
    guild = ctx.guild
    sent = await features.send_orientation_invite(guild, date_time)
    await ctx.author.send(f"📩 Orientation invite sent to {sent} members for: {date_time}")
    await ctx.send("📩 Done.", delete_after=5)


@bot.command(name="recruit")
@commands.has_permissions(manage_guild=True)
async def cmd_recruit(ctx, lang: str = "ar"):
    """Show recruitment message template. Usage: !recruit ar / !recruit en"""
    if lang == "en":
        msg = features.RECRUITMENT_MESSAGE_EN
    else:
        msg = features.RECRUITMENT_MESSAGE_AR
    await ctx.author.send(f"📋 **Recruitment Template ({lang}):**\n\n{msg}")
    await ctx.send("📩 Template sent to your DMs.", delete_after=5)


@bot.command(name="resources")
@commands.has_permissions(manage_guild=True)
async def cmd_resources(ctx, level: str = "L0"):
    """Post shadowing resources for a level. Usage: !resources L0"""
    level = level.upper()
    if level not in ["L0", "L1", "L2", "L3"]:
        await ctx.send("Usage: `!resources L0/L1/L2/L3`")
        return
    msg = features.format_shadowing_resources(level)
    channel = discord.utils.get(ctx.guild.text_channels, name="cheat-sheets")
    if channel:
        await channel.send(msg)
        await ctx.send(f"📩 Resources posted in #cheat-sheets for {level}", delete_after=5)
    else:
        await ctx.send(msg)


# ============================================================
#  ENTRY POINT
# ============================================================

def run():
    """Start the bot. Called from run.py."""
    if not config.DISCORD_TOKEN:
        raise SystemExit("❌ DISCORD_TOKEN not set. Copy .env.example to .env and fill in values.")
    if not config.GUILD_ID:
        raise SystemExit("❌ GUILD_ID not set. Set your Discord server ID in .env.")

    logger.info(f"Starting {config.BOT_NAME} v{config.BOT_VERSION}...")
    logger.info(f"  Guild: {config.GUILD_ID}")
    logger.info(f"  Daily tasks at: {config.DAILY_TASK_HOUR}:00 {config.TIMEZONE}")
    logger.info(f"  AI: Gemini={'✅' if config.GEMINI_API_KEY else '❌'} Groq={'✅' if config.GROQ_API_KEY else '⚪'}")

    try:
        bot.run(config.DISCORD_TOKEN, log_handler=None)
    except KeyboardInterrupt:
        logger.info("Bot stopped by operator.")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise
