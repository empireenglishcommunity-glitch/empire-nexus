"""Empire Challenge Bot - main Discord bot.

Features:
  - Auto-posts the daily challenge at a set hour
  - !done <day> <feeling>  -> log completion, get AI motivation, auto-rank
  - !join <goal>           -> register and set your goal
  - !me                    -> your progress, streak and rank
  - !top                   -> leaderboard
  - !today                 -> show today's challenge on demand
  - !recap <week>          -> AI weekly summary (mods)
  - !cert                  -> generate your PDF certificate
  - !status                -> bot & challenge status (mods)
  - !setday <n>            -> set current day number (mods)
  - !announce <msg>        -> send announcement (mods)
  - !reset                 -> wipe all data (admin, with confirmation)
"""
import datetime
import logging
import discord
from discord.ext import commands, tasks

from . import config, challenges, database, ai_coach, certificate, notify

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("empire-challenge-bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


def _zone():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(config.TIMEZONE)
    except Exception:
        return datetime.timezone.utc


async def _assign_rank_role(member: discord.Member, rank_name: str):
    """Create the role if missing and assign it to the member."""
    guild = member.guild
    role = discord.utils.get(guild.roles, name=rank_name)
    if role is None:
        try:
            role = await guild.create_role(name=rank_name, colour=discord.Colour.gold())
        except discord.Forbidden:
            return
    try:
        await member.add_roles(role)
    except discord.Forbidden:
        pass


@bot.event
async def on_ready():
    database.init_db()
    logger.info(f"Bot online: {bot.user} | v{config.BOT_VERSION} | {len(bot.guilds)} server(s)")
    notify.bot_online()
    if not daily_post.is_running():
        daily_post.start()


@bot.event
async def on_disconnect():
    logger.warning("Bot disconnected from Discord.")


@bot.event
async def on_resumed():
    logger.info("Bot reconnected to Discord (session resumed).")


@bot.event
async def on_command_error(ctx, error):
    """Global error handler — gives users friendly Arabic feedback."""
    if isinstance(error, commands.CommandNotFound):
        return  # Silently ignore unknown commands (e.g. !hello)

    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🔒 ليس لديك صلاحية لاستخدام هذا الأمر.")
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ ينقصك مدخل: `{error.param.name}`. اكتب `!guide` لمعرفة الاستخدام الصحيح.")
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send("❌ مدخل غير صحيح. تأكد من كتابة أرقام حيث مطلوب. اكتب `!guide` للمساعدة.")
        return

    # Unexpected errors — log and notify user
    logger.error(f"Unhandled command error in !{ctx.command}: {error}")
    await ctx.send("⚠️ حدث خطأ غير متوقع. حاول مرة أخرى أو أخبر المشرفين.")


@tasks.loop(time=datetime.time(hour=config.DAILY_POST_HOUR, tzinfo=_zone()))
async def daily_post():
    day = challenges.current_day()
    if not day:
        return
    c = challenges.get_challenge(day)
    if not c:
        return
    channel = bot.get_channel(config.CHALLENGE_CHANNEL_ID)
    if channel is None:
        logger.error("CHALLENGE_CHANNEL_ID not found. Check your .env.")
        return
    intro = ai_coach.daily_intro(day, c["task"])
    await channel.send(f"@everyone {intro}\n\n{challenges.format_challenge(c)}")


@bot.command(name="join")
async def join(ctx, *, goal: str = ""):
    database.register(str(ctx.author.id), ctx.author.display_name, goal)
    msg = f"🌱 أهلًا {ctx.author.mention}! تم تسجيلك في التحدّي."
    if goal:
        msg += f"\n🎯 هدفك: **{goal}**"
    msg += "\nبالتوفيق، نراك على القمة! 👑"
    await ctx.send(msg)


@bot.command(name="done")
async def done(ctx, day: int = None, feeling: int = 5):
    if day is None:
        day = challenges.current_day() or 1
    feeling = max(1, min(10, feeling))
    c = challenges.get_challenge(day)
    if not c:
        await ctx.send("❌ رقم اليوم غير صحيح (1 إلى 30).")
        return

    newly = database.log_done(str(ctx.author.id), ctx.author.display_name, day, feeling)
    if not newly:
        await ctx.send(f"✅ سبق أن سجّلت اليوم {day}. أحسنت على الالتزام!")
        return

    total = database.completed_count(str(ctx.author.id))
    streak = database.current_streak(str(ctx.author.id))
    rank_name, emoji = config.rank_for(total)
    coach = ai_coach.feedback(ctx.author.display_name, day, feeling, c["task"])

    await ctx.send(
        f"{emoji} {ctx.author.mention} {coach}\n"
        f"📊 أنجزت **{total}/30** | 🔥 سلسلة متتالية: **{streak}** يوم | الرتبة: **{rank_name}**"
    )

    if isinstance(ctx.author, discord.Member):
        await _assign_rank_role(ctx.author, rank_name)


@bot.command(name="me")
async def me(ctx):
    uid = str(ctx.author.id)
    total = database.completed_count(uid)
    streak = database.current_streak(uid)
    rank_name, emoji = config.rank_for(total)
    p = database.get_participant(uid)
    goal = (p or {}).get("goal") or "—"
    await ctx.send(
        f"{emoji} **تقدّم {ctx.author.display_name}**\n"
        f"🎯 الهدف: {goal}\n"
        f"✅ منجز: {total}/30\n"
        f"🔥 سلسلة متتالية: {streak} يوم\n"
        f"🏅 الرتبة الحالية: {rank_name}"
    )


@bot.command(name="top")
async def top(ctx):
    rows = database.leaderboard(10)
    if not rows:
        await ctx.send("لا يوجد مشاركون بعد. كن أول من ينضم بـ `!join` 🌱")
        return
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    lines = ["🏆 **لوحة المتصدّرين**"]
    for i, (name, done_count) in enumerate(rows):
        lines.append(f"{medals[i]} {name} — {done_count}/30")
    await ctx.send("\n".join(lines))


@bot.command(name="today")
async def today(ctx):
    day = challenges.current_day() or 1
    c = challenges.get_challenge(day)
    if not c:
        await ctx.send("لا يوجد تحدٍّ متاح الآن.")
        return
    await ctx.send(challenges.format_challenge(c))


@bot.command(name="recap")
@commands.has_permissions(manage_guild=True)
async def recap(ctx, week: int = 1):
    rows = database.leaderboard(1)
    champion = rows[0][0] if rows else "لم يُحدّد بعد"
    total_done = sum(d for _, d in database.leaderboard(100))
    active = len(database.all_participants())
    text = ai_coach.weekly_recap(week, {"active": active, "done": total_done, "champion": champion})
    await ctx.send(text)


@bot.command(name="cert")
async def cert(ctx):
    uid = str(ctx.author.id)
    total = database.completed_count(uid)
    if total < 1:
        await ctx.send("سجّل تحدّيًا واحدًا على الأقل قبل طلب الشهادة. `!done`")
        return
    rank_name, _ = config.rank_for(total)
    path = certificate.make_certificate(ctx.author.display_name, total, rank_name)
    await ctx.send(
        content=f"📜 شهادتك جاهزة يا {ctx.author.mention}! الرتبة: **{rank_name}**",
        file=discord.File(path),
    )


@bot.command(name="guide")
async def guide(ctx):
    await ctx.send(
        "**أوامر بوت التحدّي:**\n"
        "`!join <هدفك>` — انضم وحدّد هدفك\n"
        "`!today` — تحدّي اليوم\n"
        "`!done <اليوم> <شعورك 1-10>` — سجّل إنجازك\n"
        "`!me` — تقدّمك ورتبتك\n"
        "`!top` — لوحة المتصدّرين\n"
        "`!cert` — شهادتك (PDF)\n"
        "`!recap <الأسبوع>` — ملخّص أسبوعي (للمشرفين)\n\n"
        "**أوامر المشرفين:**\n"
        "`!status` — حالة البوت والتحدّي\n"
        "`!setday <رقم>` — تعيين يوم التحدّي يدويًا\n"
        "`!announce <رسالة>` — إعلان لجميع الأعضاء\n"
        "`!reset` — إعادة تعيين بيانات التحدّي (خطير!)"
    )


@bot.command(name="version")
async def version(ctx):
    """Show bot version and uptime info."""
    import platform
    await ctx.send(
        f"🤖 **Empire Challenge Bot** v{config.BOT_VERSION}\n"
        f"🐍 Python {platform.python_version()} | discord.py {discord.__version__}"
    )


# ═══════════════════════════════════════════════════════════════
#  ADMIN / MOD COMMANDS
# ═══════════════════════════════════════════════════════════════

@bot.command(name="status")
@commands.has_permissions(manage_guild=True)
async def status(ctx):
    """Show bot and challenge status summary."""
    import platform
    day = challenges.current_day() or 0
    total_participants = len(database.all_participants())
    total_logged = sum(d for _, d in database.leaderboard(1000))
    start = config.START_DATE or "(غير محدّد)"

    status_text = (
        "📊 **حالة البوت والتحدّي**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 البوت: متصل ✅ (v{config.BOT_VERSION})\n"
        f"🐍 Python: {platform.python_version()}\n"
        f"📅 تاريخ البداية: `{start}`\n"
        f"📌 اليوم الحالي: **{day}** / {config.TOTAL_DAYS}\n"
        f"👥 المشاركون: **{total_participants}**\n"
        f"✅ إجمالي التحديات المنجزة: **{total_logged}**\n"
        f"⏰ وقت النشر اليومي: الساعة **{config.DAILY_POST_HOUR}:00** ({config.TIMEZONE})\n"
        f"🧠 AI (Groq): {'✅ مفعّل' if config.GROQ_API_KEY else '❌ غير مفعّل (رسائل مدمجة)'}\n"
        f"📡 القناة: <#{config.CHALLENGE_CHANNEL_ID}>"
    )
    await ctx.send(status_text)


@bot.command(name="setday")
@commands.has_permissions(manage_guild=True)
async def setday(ctx, new_start_offset: int = None):
    """Override the current challenge day by adjusting START_DATE.

    Usage: !setday 5  — sets today as Day 5 of the challenge.
    This recalculates START_DATE so that today = the given day number.
    Persisted in the database (survives container restarts).
    """
    if new_start_offset is None or new_start_offset < 1 or new_start_offset > 30:
        await ctx.send("❌ استخدام: `!setday <رقم من 1 إلى 30>` — يجعل اليوم هو ذلك الرقم.")
        return

    from datetime import timedelta
    today = datetime.date.today()
    new_start = today - timedelta(days=new_start_offset - 1)
    new_start_str = new_start.isoformat()

    # Persist in database (survives Docker restarts)
    database.set_setting("START_DATE", new_start_str)

    # Also update in-memory config for immediate effect
    config.START_DATE = new_start_str

    await ctx.send(
        f"✅ تم! اليوم أصبح **اليوم {new_start_offset}** من التحدّي.\n"
        f"📅 تاريخ البداية الجديد: `{new_start_str}`\n"
        f"💾 محفوظ في قاعدة البيانات (يبقى بعد إعادة التشغيل)."
    )


@bot.command(name="announce")
@commands.has_permissions(manage_guild=True)
async def announce(ctx, *, message: str = ""):
    """Send an announcement to the challenge channel."""
    if not message:
        await ctx.send("❌ استخدام: `!announce <الرسالة>`")
        return

    channel = bot.get_channel(config.CHALLENGE_CHANNEL_ID)
    if channel is None:
        await ctx.send("❌ لم يتم العثور على قناة التحدّي. تحقق من CHALLENGE_CHANNEL_ID.")
        return

    announcement = f"📢 **إعلان من المشرفين:**\n\n{message}"
    await channel.send(f"@everyone {announcement}")
    await ctx.send(f"✅ تم إرسال الإعلان إلى <#{config.CHALLENGE_CHANNEL_ID}>")


@bot.command(name="reset")
@commands.has_permissions(administrator=True)
async def reset(ctx):
    """Reset all challenge data. Requires ADMINISTRATOR permission.

    This is destructive — it deletes all participant progress.
    Requires confirmation by reacting within 30 seconds.
    """
    confirm_msg = await ctx.send(
        "⚠️ **تحذير: هل أنت متأكد أنك تريد حذف جميع بيانات التحدّي؟**\n"
        "سيتم حذف جميع المشاركين وتقدّمهم. لا يمكن التراجع!\n\n"
        "تفاعل بـ ✅ خلال 30 ثانية للتأكيد، أو تجاهل للإلغاء."
    )
    await confirm_msg.add_reaction("✅")

    def check(reaction, user):
        return (
            user == ctx.author
            and str(reaction.emoji) == "✅"
            and reaction.message.id == confirm_msg.id
        )

    try:
        await bot.wait_for("reaction_add", timeout=30.0, check=check)
    except Exception:
        await ctx.send("❌ تم إلغاء إعادة التعيين (انتهى الوقت).")
        return

    # Perform the reset
    import sqlite3
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("DELETE FROM progress")
    conn.execute("DELETE FROM participants")
    conn.commit()
    conn.close()

    await ctx.send(
        "🗑️ **تم إعادة تعيين جميع البيانات.**\n"
        "جميع المشاركين وتقدّمهم تم حذفه. يمكن بدء تحدٍّ جديد الآن."
    )


def run():
    if not config.DISCORD_TOKEN:
        raise SystemExit("❌ DISCORD_TOKEN غير موجود. انسخ .env.example إلى .env واملأه.")
    logger.info(f"Starting Empire Challenge Bot v{config.BOT_VERSION}...")
    try:
        bot.run(config.DISCORD_TOKEN, log_handler=None)
    except KeyboardInterrupt:
        logger.info("Bot stopped by operator (KeyboardInterrupt).")
        notify.bot_offline("manual stop")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        notify.bot_offline(f"crash: {e}")
        raise
    finally:
        logger.info("Bot process exiting.")
