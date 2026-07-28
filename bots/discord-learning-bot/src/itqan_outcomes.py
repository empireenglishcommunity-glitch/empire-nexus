"""Itqan — outcome delivery after a weekly-assessment attempt finishes (Phase 6).

Routes a finished attempt to its human consequence:

- **mastered / distinction** → a public 🏅 *Week Champions* celebration
  (positive-only; names the student + week + streak). Never shames.
- **not yet** → a PRIVATE, encouraging DM with the exact review list, and the
  missed words are **re-injected into the student's SRS queue** (due today) so
  a "not yet" becomes targeted extra practice. The daily tasks / streak /
  calendar are **never touched** (R7.1).
- **flagged** → the owner is notified via Empire Ops for a human call; the
  student just sees a neutral "being reviewed" state on the page.

Every Discord/Telegram side-effect here is **best-effort** and never raises
into the caller: scoring already succeeded and was persisted, so a failed
celebration post or DM must not turn the /finish request into a 500.

Called from the `/api/assessment/finish` route (the only place attempts are
finished), which is itself gated behind the `itqan_weekly_assessment` flag —
so none of this runs until the flag is on.
"""
import json
import logging

from . import database

logger = logging.getLogger("empire-bot.itqan")


# ============================================================
#  Entry point
# ============================================================

async def deliver_outcome(discord_id: str, level: str, week: int,
                          attempt_id: int, verdict: dict) -> None:
    """Fire the right consequence for a finished attempt. Best-effort."""
    try:
        status = verdict.get("status")
        result = verdict.get("result")

        # Borderline / AI-error → the owner decides (student sees "being
        # reviewed"). We do NOT celebrate or send a not-yet DM here.
        if status == "flagged":
            await _notify_owner_flagged(discord_id, level, week, attempt_id, verdict)
            return

        if result == "mastered":
            await _celebrate_champion(discord_id, level, week, verdict)
            return

        # not_yet (scored): private support + targeted re-inject.
        # NOTHING about the daily flow is mutated.
        missed, production_missed = _reinject_weak_items(discord_id, attempt_id)
        await _support_dm(discord_id, level, week, verdict, missed, production_missed)
    except Exception as e:  # pragma: no cover - safety net
        logger.error(f"itqan deliver_outcome failed: {e}")


# ============================================================
#  not_yet — SRS re-inject (pure DB, no daily-flow mutation)
# ============================================================

def _reinject_weak_items(discord_id: str, attempt_id: int):
    """Re-add the words the student got wrong into their SRS queue, due today,
    so 'Review Past Words' immediately serves what they just struggled with.

    Returns (missed:[(word, meaning)], production_missed:bool) for the DM. Only
    touches vocab_srs — daily tasks, streak, points and the calendar are left
    completely alone."""
    try:
        rows = database.itqan_get_items(attempt_id)
    except Exception:
        rows = []
    due_today = database._today_local().isoformat()
    missed = []
    production_missed = False
    for r in rows:
        if r.get("correct") in (1, True):
            continue
        skill = r.get("skill")
        if skill in ("speaking", "writing"):
            production_missed = True
            continue
        try:
            payload = json.loads(r.get("prompt_ref") or "{}")
        except Exception:
            payload = {}
        word = ""       # the English term SRS is keyed on
        meaning = ""
        if skill == "vocab":
            word, meaning = payload.get("expected", ""), payload.get("prompt_ar", "")
        elif skill == "pronunciation":
            word = payload.get("word", "") or payload.get("expected", "")
        elif skill == "listening":
            word, meaning = payload.get("say_en", ""), payload.get("expected", "")
        word = (word or "").strip()
        if word:
            database.add_word_to_srs(discord_id, word, next_review=due_today)
            missed.append((word, (meaning or "").strip()))
    return missed, production_missed


# ============================================================
#  mastered — public Week Champions celebration
# ============================================================

def _week_streak(mastered_weeks: set, week: int) -> int:
    """Consecutive mastered weeks ending at `week` (…W-1, W)."""
    streak = 0
    w = week
    while w in mastered_weeks:
        streak += 1
        w -= 1
    return streak


async def _champions_channel(guild, level: str):
    """Find (by stored id, then by name) or create the per-level Week Champions
    channel. The id is persisted in settings so we only create it once."""
    import discord as dlib
    key = f"itqan_champions_channel_{level.lower()}"
    stored = database.get_setting(key, "")
    if stored.isdigit():
        ch = guild.get_channel(int(stored))
        if ch:
            return ch
    name = f"l{level[1].lower()}-week-champions"
    ch = dlib.utils.get(guild.text_channels, name=name)
    if ch:
        database.set_setting(key, str(ch.id))
        return ch
    try:
        showcase = dlib.utils.get(guild.text_channels, name=f"l{level[1].lower()}-showcase")
        category = showcase.category if showcase else None
        ch = await guild.create_text_channel(
            name, category=category,
            topic="🏅 Weekly Assessment champions — mastered weeks. Positive only.")
        database.set_setting(key, str(ch.id))
        logger.info(f"itqan: created champions channel #{name} ({ch.id})")
        return ch
    except Exception as e:
        logger.warning(f"itqan: couldn't create champions channel for {level}: {e}")
        return None


async def _celebrate_champion(discord_id: str, level: str, week: int, verdict: dict) -> None:
    from . import bot as bot_mod, config
    b = getattr(bot_mod, "bot", None)
    if not b or not b.is_ready():
        logger.warning("itqan: bot not ready, skipping champions post")
        return
    guild = b.get_guild(config.GUILD_ID)
    if not guild:
        return
    member = guild.get_member(int(discord_id))
    name = (member.display_name if member
            else (database.get_member(discord_id) or {}).get("discord_name", "A student"))

    ch = await _champions_channel(guild, level)
    if not ch:
        return

    mastered = database.itqan_mastered_weeks(discord_id, level)
    streak = _week_streak(mastered, week)
    total = len(mastered)
    dist = " ⭐ **Distinction!**" if verdict.get("distinction") else ""
    streak_line = (f"🔥 {streak} weeks in a row · " if streak > 1 else "")
    msg = (f"🏅 **{name}** mastered **Week {week}**!{dist}\n"
           f"{streak_line}{total} week{'s' if total != 1 else ''} mastered so far.\n"
           f"Keep leading the way! 👑")
    try:
        await ch.send(msg)
        logger.info(f"itqan: champions post for {name} week {week} ({level})")
    except Exception as e:
        logger.warning(f"itqan: champions post failed: {e}")

    # Did this pass complete the WHOLE level? → send the certificate DM (once).
    if _is_level_complete(level, mastered):
        await _maybe_certificate_dm(discord_id, level)


def _is_level_complete(level: str, mastered_weeks) -> bool:
    """True when every week of the level has been mastered."""
    from . import curriculum
    total = curriculum.max_week_for_level(level)
    return bool(total) and len(mastered_weeks) >= total


async def _maybe_certificate_dm(discord_id: str, level: str) -> None:
    """DM the student their level-completion certificate link, once per level."""
    key = f"itqan_cert_sent_{discord_id}_{level}"
    if database.get_setting(key, ""):
        return  # already sent — don't repeat on a later re-pass
    from . import bot as bot_mod, config
    b = getattr(bot_mod, "bot", None)
    if not b:
        return
    try:
        user = b.get_user(int(discord_id))
        if user is None:
            user = await b.fetch_user(int(discord_id))
    except Exception:
        user = None
    if not user:
        return
    base = database.get_setting("practice_base_url", "https://practice.empireenglish.online")
    link = f"{base}/assessment/certificate/?level={level}"
    level_name = (config.LEVELS.get(level, {}) or {}).get("name", level)
    msg = (
        f"🎓 **Level Complete — {level} {level_name}!**\n"
        f"You've mastered every week of {level}. That's a huge achievement — "
        f"real, proven progress. 👑\n\n"
        f"View & save your certificate:\n{link}\n"
        f"━━━━━━━━━━\n"
        f"🎓 **أكملت المستوى — {level}!**\n"
        f"أتقنت كل أسابيع {level}. إنجاز كبير وتقدّم حقيقي. شوف واحفظ شهادتك من اللينك فوق. 👑"
    )
    try:
        await user.send(msg)
        database.set_setting(key, database._today_local().isoformat())
        logger.info(f"itqan: sent level-complete certificate DM ({level}) to {discord_id}")
    except Exception as e:
        logger.warning(f"itqan: certificate DM failed: {e}")


# ============================================================
#  not_yet — private, encouraging DM
# ============================================================

async def _support_dm(discord_id: str, level: str, week: int, verdict: dict,
                      missed, production_missed: bool) -> None:
    from . import bot as bot_mod
    b = getattr(bot_mod, "bot", None)
    if not b:
        return
    try:
        user = b.get_user(int(discord_id))
        if user is None:
            user = await b.fetch_user(int(discord_id))
    except Exception:
        user = None
    if not user:
        return

    lines = []
    for word, meaning in missed[:8]:
        lines.append(f"• {word}" + (f" — {meaning}" if meaning else ""))
    review = "\n".join(lines) if lines else "• Review this week's words and audio."
    prod = "\n🎙️ Also practise speaking & writing about this week's topic." if production_missed else ""

    msg = (
        f"💪 **Week {week} — you're close!**\n"
        f"Your daily progress is completely safe — nothing was locked or lost.\n\n"
        f"Review these, then retake when you're ready:\n{review}{prod}\n\n"
        f"Take a short break, then open the Weekly Test from your calendar again. "
        f"You've got this! 🌱\n"
        f"━━━━━━━━━━\n"
        f"💪 **الأسبوع {week} — قرّبت!**\n"
        f"تقدّمك اليومي في أمان تمامًا — مفيش حاجة اتقفلت أو ضاعت. "
        f"راجع الكلمات دي وبعدين أعِد الاختبار من التقويم. إنت قدّها! 🌱"
    )
    try:
        await user.send(msg)
        logger.info(f"itqan: sent not-yet support DM for week {week} to {discord_id}")
    except Exception as e:
        logger.warning(f"itqan: support DM failed: {e}")


# ============================================================
#  flagged — owner notification (Empire Ops)
# ============================================================

async def _notify_owner_flagged(discord_id: str, level: str, week: int,
                                attempt_id: int, verdict: dict) -> None:
    from . import ops_hub
    name = (database.get_member(discord_id) or {}).get("discord_name", str(discord_id))
    reason = {
        "ai_error": "an AI/recording item couldn't be scored — please re-check",
        "near_miss": "a near-miss just below the pass line — a rescue candidate",
    }.get(verdict.get("flag_reason"), "needs your judgement")
    body = (
        f"Student: {name}  ·  {level} Week {week}\n"
        f"Mastery {verdict.get('mastery_pct')}% · Consistency {verdict.get('consistency_pct')}%\n"
        f"Reason: {reason}.\n\n"
        f"Paste any of these in #admin-commands (! = paste-ready):\n"
        f"  !itqan-review {attempt_id}\n"
        f"  !itqan-pass {discord_id} {week}\n"
        f"  !itqan-reset {discord_id} {week}\n"
        f"(or use the /itqan-… menu versions and pick {name})"
    )
    try:
        res = await ops_hub.send_ops_alert("Itqan: attempt needs review", body, severity="warning")
        logger.info(f"itqan: flagged owner alert sent for attempt {attempt_id} ({name} {level} W{week}) "
                    f"-> {'ok' if res else 'no-op/None'}")
    except Exception as e:
        logger.warning(f"itqan: owner flag notify failed: {e}")


# ============================================================
#  manual owner pass — celebrate the student like an earned pass (A2)
# ============================================================

async def deliver_manual_pass(discord_id: str, level: str, week: int) -> None:
    """After an owner override marks a week mastered, tell + celebrate the
    student exactly like an earned pass (they'd otherwise never know)."""
    try:
        await _manual_pass_dm(discord_id, level, week)
        # Reuse the earned-pass celebration: Champions post + streak line, and
        # the level certificate if this completed the level.
        await _celebrate_champion(discord_id, level, week, {"distinction": False})
    except Exception as e:  # pragma: no cover - safety net
        logger.error(f"itqan deliver_manual_pass failed: {e}")


async def _manual_pass_dm(discord_id: str, level: str, week: int) -> None:
    from . import bot as bot_mod
    b = getattr(bot_mod, "bot", None)
    if not b:
        return
    try:
        user = b.get_user(int(discord_id))
        if user is None:
            user = await b.fetch_user(int(discord_id))
    except Exception:
        user = None
    if not user:
        return
    msg = (
        f"🏅 **Great news — you passed Week {week}!**\n"
        f"Your teacher reviewed your test and confirmed it. Well done — keep going! 👑\n"
        f"━━━━━━━━━━\n"
        f"🏅 **مبروك — عدّيت اختبار الأسبوع {week}!**\n"
        f"المعلّم راجع اختبارك وأكّده. شغل ممتاز — كمّل! 👑"
    )
    try:
        await user.send(msg)
        logger.info(f"itqan: manual-pass DM sent to {discord_id} ({level} W{week})")
    except Exception as e:
        logger.warning(f"itqan: manual-pass DM failed: {e}")



# ============================================================
#  due-assessment nudge (R17.2) — Arabic, once per due week
# ============================================================

async def nudge_due_students() -> int:
    """DM (Arabic, motivational) each student who has a DUE assessment — a week
    whose days are done but the test isn't passed — at most ONCE per due week.
    Only students the flag is enabled for. Returns how many were nudged."""
    from . import bot as bot_mod
    b = getattr(bot_mod, "bot", None)
    if not b:
        return 0
    try:
        data = database.itqan_status_report()
    except Exception as e:
        logger.warning(f"itqan: nudge status report failed: {e}")
        return 0
    base = database.get_setting("practice_base_url", "https://practice.empireenglish.online")
    n = 0
    for r in data.get("rows", []):
        if r.get("state") != "due" or not r.get("due_week"):
            continue
        did, level, week = r["discord_id"], r["level"], r["due_week"]
        if not database.is_feature_enabled("itqan_weekly_assessment", did):
            continue
        key = f"itqan_nudged_{did}_{level}_{week}"
        if database.get_setting(key, ""):
            continue  # already nudged for this due week
        try:
            user = b.get_user(int(did))
            if user is None:
                user = await b.fetch_user(int(did))
        except Exception:
            user = None
        if not user:
            continue
        msg = (
            f"📝 **اختبار الأسبوع {week} جاهز ومستنّيك!**\n"
            f"إنت خلّصت أيام الأسبوع — فاضل تختبر نفسك وتثبت إتقانك.\n"
            f"افتح التقويم وابدأ الاختبار: {base}/\n"
            f"إنت قدّها 💪 — النتيجة الحقيقية بتيجي بالخطوة دي."
        )
        try:
            await user.send(msg)
            database.set_setting(key, database._today_local().isoformat())
            n += 1
            logger.info(f"itqan: due-nudge sent to {did} ({level} W{week})")
        except Exception as e:
            logger.warning(f"itqan: due nudge failed for {did}: {e}")
    return n



# ============================================================
#  "almost there" nudge (G4) — encourage students 1–2 days from
#  unlocking a week's test. NO rule change: the unlock bar is still
#  "all 7 days done"; this just nudges the students who are close.
# ============================================================

def _almost_done_week(discord_id: str, level: str):
    """Return (week, [missing_day_ints]) for the EARLIEST week that is 1–2 days
    short of complete (5–6 of its 7 days done) — so finishing those day(s)
    unlocks that week's Weekly Test. Returns None if no week qualifies.

    Pure/testable: delegates the per-week "which days are still undone" decision
    to assessment.week_unlocked (the SAME gate the test itself uses), so this can
    never disagree with the real unlock rule.
    """
    from . import assessment, curriculum
    max_week = curriculum.max_week_for_level(level)
    for w in range(1, max_week + 1):
        ok, remaining = assessment.week_unlocked(discord_id, level, w)
        if ok:
            continue  # already unlocked (0 days remaining) — nothing to nudge
        if 1 <= len(remaining) <= 2:
            return (w, remaining)
    return None


async def nudge_almost_done_students() -> int:
    """DM (friendly, bilingual) each student who is 1–2 days short of completing
    a week, so finishing those day(s) unlocks that week's Weekly Test. At most
    ONCE per (student, week) — a `settings` guard makes a repeat impossible even
    across restarts, so this never nags. Flag-gated (silent unless Itqan is on
    for that student); respects quiet hours. Returns how many were nudged.

    Deliberately NOT Nour-voiced (Nour is retired) — a plain, warm bot message.
    """
    from . import bot as bot_mod
    b = getattr(bot_mod, "bot", None)
    if not b:
        return 0
    n = 0
    for m in database.all_active_members():
        did = m["discord_id"]
        level = m.get("level", "L0")
        if not database.is_feature_enabled("itqan_weekly_assessment", did):
            continue
        target = _almost_done_week(did, level)
        if not target:
            continue
        week, remaining = target
        key = f"itqan_almost_nudged_{did}_{level}_{week}"
        if database.get_setting(key, ""):
            continue  # already nudged for this week — never repeat
        try:
            if database.is_quiet_hours(did):
                continue
        except Exception:
            pass
        try:
            user = b.get_user(int(did))
            if user is None:
                user = await b.fetch_user(int(did))
        except Exception:
            user = None
        if not user:
            continue
        done = 7 - len(remaining)
        days_en = " & ".join(f"Day {d}" for d in remaining)
        days_ar = " و ".join(f"يوم {d}" for d in remaining)
        msg = (
            f"🌟 You're almost there! You've done **{done}/7** days of Week {week}. "
            f"Finish **{days_en}** and your **Weekly Test** unlocks — your shot at "
            f"the 🏅 Week Champion badge. You've got this! 💪\n"
            f"━━━━━━━━━━\n"
            f"🌟 قربت خلاص! خلّصت **{done}/7** أيام من الأسبوع {week}. "
            f"كمّل **{days_ar}** وهيفتح لك **اختبار الأسبوع** — فرصتك تكسب شارة "
            f"🏅 بطل الأسبوع. إنت قدّها! 💪"
        )
        try:
            await user.send(msg)
            database.set_setting(key, database._today_local().isoformat())
            n += 1
            logger.info(f"itqan: almost-done nudge sent to {did} ({level} W{week}, {done}/7)")
        except Exception as e:
            logger.warning(f"itqan: almost-done nudge failed for {did}: {e}")
    return n
