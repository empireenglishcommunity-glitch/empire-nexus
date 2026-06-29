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
  !setlevel @user L#   Set a member's level
  !announce <msg>      Broadcast to announcements
  !members             List all members with levels
"""
import asyncio
import datetime
import logging
import discord
from discord.ext import commands, tasks

from . import config, database, tasks as task_engine, ai_engine, verification

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
    logger.info(f"Bot online: {bot.user} | v{config.BOT_VERSION} | {len(bot.guilds)} server(s)")
    if not daily_task_post.is_running():
        daily_task_post.start()
    if not weekly_assessment.is_running():
        weekly_assessment.start()
    if not streak_update.is_running():
        streak_update.start()


@bot.event
async def on_member_join(member: discord.Member):
    """Auto-register new members and send welcome DM with full manual."""
    database.register_member(str(member.id), member.display_name)
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
            f"📅 **الروتين اليومي (7 مهام — 45 دقيقة بس):**\n\n"
            f"🎯 تدريب النطق — سجل صوتك في `#l0-showcase` ← ثم `!done accent`\n"
            f"📖 مفردات جديدة — `!done vocab` ← البوت هيسألك سؤال\n"
            f"🎧 المحاكاة (Shadowing) — سجل 30 ثانية في `#l0-showcase` ← ثم `!done shadow`\n"
            f"🎙️ مهمة الكلام — سجل صوتك في `#l0-showcase` ← ثم `!done speaking`\n"
            f"👂 تمرين الاستماع — `!done listening` ← البوت هيسألك سؤال\n"
            f"✍️ تمرين الكتابة — اكتب في `#l0-text-practice` ← ثم `!done writing`\n"
            f"💬 مشاركة مجتمعية — اكتب في `#general-chat` أو ادخل voice 10 دقايق ← ثم `!done community`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⚠️ **مهم:** لازم تعمل المهمة الأول وبعدين تكتب `!done`\n"
            f"البوت بيتأكد إنك فعلاً عملت المهمة قبل ما يديك النقاط."
        )
        await asyncio.sleep(2)

        # Message 3: Levels + Points
        await member.send(
            f"🏆 **نظام المستويات:**\n\n"
            f"🌱 **Level 0** — مبتدئ (8-12 أسبوع)\n"
            f"   الهدف: تعريف نفسك في 60 ثانية\n\n"
            f"💪 **Level 1** — النجاة (10-14 أسبوع)\n"
            f"   الهدف: مونولوج 2 دقيقة بدون تحضير\n\n"
            f"🚀 **Level 2** — التواصل (12-16 أسبوع)\n"
            f"   الهدف: عرض 5 دقايق عن أي موضوع\n\n"
            f"👑 **Level 3** — الطلاقة (مستمر)\n"
            f"   كلام طبيعي بلهجة أمريكية\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔥 **النقاط:** كل مهمة = 15 نقطة | الـ 7 مهام = +100 بونص\n"
            f"🔥 **Streaks:** 7 أيام = +200 | 30 يوم = +1000 | 100 يوم = +5000"
        )
        await asyncio.sleep(2)

        # Message 4: Channel Guide
        await member.send(
            f"🗺️ **خريطة القنوات المهمة:**\n\n"
            f"⭐ `#bot-commands` — اكتب كل الأوامر هنا\n"
            f"⭐ `#l0-daily-tasks` — المهام اليومية (6 صباحًا)\n"
            f"📝 `#l0-text-practice` — تمارين الكتابة\n"
            f"🎙️ `#l0-showcase` — شارك تسجيلاتك\n"
            f"❓ `#l0-questions` — أسئلة (عربي مسموح هنا)\n"
            f"🔊 `l0-voice-1` — غرفة صوتية للتمرين\n"
            f"💬 `#general-chat` — دردشة إنجليزي\n"
            f"📖 `#daily-word` — كلمة اليوم\n"
            f"🎙️ `#speaking-feedback` — ارفع تسجيل ← AI يرد عليك\n"
            f"📊 `#daily-check-in` — سجل خطتك كل صباح\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏛️ **خلاصة:** ادخل كل يوم. اعمل الـ 7 مهام. اكتب `!done`. بس كده.\n"
            f"النظام هيعمل الباقي. 💪\n\n"
            f"*System over instructor. Common Sense First.* 🏛️"
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
        message = task_engine.format_daily_post(task_data)

        # Find the channel
        channel_name = f"l{level_key[1]}-daily-tasks"
        channel = _find_channel(guild, channel_name)
        if channel:
            try:
                await channel.send(message)
                logger.info(f"Posted daily tasks to #{channel_name} (week {week})")
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
        level = member_data["level"]

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

    # Format response
    bar = "█" * result["tasks_today"] + "░" * (7 - result["tasks_today"])
    msg = (
        f"{result['feedback']}\n\n"
        f"[{bar}] {result['tasks_today']}/7 today\n"
        f"🔥 Streak: **{result['streak']}** days | +{result['points']} points"
    )
    if result["tasks_today"] == 7:
        msg += "\n\n🎉 **ALL 7 TASKS COMPLETE!** Bonus points earned!"

    await ctx.send(msg)


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
    """View this week's curriculum focus (phonemes, vocab theme, etc.)."""
    member = database.get_member(str(ctx.author.id))
    if not member:
        await ctx.send("Not registered. Use `!join` first.")
        return

    week = database.member_week_number(str(ctx.author.id))
    level = member["level"]
    phoneme_info = config.PHONEME_WEEKS.get(week, config.PHONEME_WEEKS.get(1, {}))
    vocab_theme = config.VOCAB_THEMES.get(week, "General")

    msg = (
        f"📅 **Week {week} Focus**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Phonemes: {phoneme_info.get('focus', 'Review')}\n"
        f"   Vowels: {', '.join(phoneme_info.get('vowels', []))}\n"
        f"   Consonants: {', '.join(phoneme_info.get('consonants', []))}\n"
        f"📖 Vocabulary theme: **{vocab_theme}**\n"
        f"🎙️ Speaking mission type: {config.SPEAKING_MISSION_TYPES.get(task_engine.current_day_name(), 'free_talk')}"
    )
    await ctx.send(msg)


@bot.command(name="help")
async def cmd_help(ctx):
    """Show all available commands."""
    await ctx.send(
        "**🏛️ Empire English Bot — Commands**\n\n"
        "**Learning:**\n"
        "`!join <goal>` — Register and set your goal\n"
        "`!done <task>` — Mark a task done (with verification)\n"
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
        "`!setlevel @user L0/L1/L2/L3` — Set someone's level\n"
        "`!announce <message>` — Broadcast announcement\n"
        "`!members` — List all members\n"
    )



# ============================================================
#  WRITING FEEDBACK (auto-detect submissions in #writing-feedback)
# ============================================================

@bot.event
async def on_message(message: discord.Message):
    """Detect writing submissions, auto-evaluate, and handle quiz answers."""
    # Don't respond to bot's own messages
    if message.author.bot:
        return

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
        await ctx.send(f"❌ Invalid level. Use: L0, L1, L2, L3")
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
