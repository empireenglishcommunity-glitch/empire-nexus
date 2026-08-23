"""Taqdeem — Advancement Exam outcome delivery (Phase 6).

Routes a finished advancement exam to its consequence:
- **passed** → AUTO-PROMOTE (set_level) + certificate DM + Champions post + owner notify
- **not passed** → private DM with per-skill + Part B breakdown + 7-day retake info
- Owner notified on EVERY attempt (pass or fail) — for 16 students this is manageable

All side-effects are best-effort and never raise.
"""
import json
import logging

from . import database

logger = logging.getLogger("empire-bot.advancement")

# Level progression now uses the CEFR chain (A1→A2→…→C2) via
# config.next_cefr_level(), so promotion walks all six levels, not the legacy
# four. (The old hardcoded _NEXT_LEVEL {L0→L1…} is gone.)


# ============================================================
#  Entry point
# ============================================================

async def deliver_advancement_outcome(discord_id: str, level: str,
                                      attempt_id: int, result: dict) -> None:
    """Fire the right consequence for a finished advancement exam."""
    try:
        if result.get("passed"):
            await _promote_and_celebrate(discord_id, level, result)
        else:
            await _send_not_pass_dm(discord_id, level, result)

        # Owner always notified (every attempt)
        await _notify_owner(discord_id, level, result)

    except Exception as e:
        logger.warning(f"advancement: outcome delivery error for {discord_id}: {e}")


# ============================================================
#  PASS → auto-promote + celebrate
# ============================================================

async def _reassign_discord_role(discord_id: str, new_level: str) -> None:
    """Give the student their new level's Discord role (and strip the old one),
    so an auto-promotion actually moves them into the next CEFR zone. Reuses
    the bot's single role-assignment helper. Best-effort: never blocks the
    promotion if the member isn't reachable."""
    from . import bot as bot_mod, config
    b = getattr(bot_mod, "bot", None)
    if not b or not getattr(config, "GUILD_ID", 0):
        return
    guild = b.get_guild(config.GUILD_ID)
    if not guild:
        return
    try:
        member = guild.get_member(int(discord_id))
    except (ValueError, TypeError):
        return
    if not member:
        return
    try:
        await bot_mod._assign_level_role(member, new_level)
        logger.info(f"advancement: reassigned {discord_id} to {new_level} role/zone")
    except Exception as e:
        logger.warning(f"advancement: role reassign failed for {discord_id}: {e}")


async def _promote_and_celebrate(discord_id: str, level: str, result: dict) -> None:
    """The big moment: promote the student to the next level."""
    from . import config
    next_level = config.next_cefr_level(level)
    if not next_level:
        logger.info(f"advancement: {discord_id} passed {level} but no next level (max)")
        return

    # 1. Promote (sets level + resets calendar anchor)
    database.set_level(discord_id, next_level)
    logger.info(f"advancement: PROMOTED {discord_id} from {level} to {next_level}")

    # 1b. Move them to the new level's Discord role + zone (this was previously
    #     never done on auto-promotion — the DB level advanced but the student
    #     kept their old role/zone).
    await _reassign_discord_role(discord_id, next_level)

    # 2. Mark as promoted in advancement_exams
    conn = database._connect()
    try:
        conn.execute(
            "UPDATE advancement_exams SET promoted=1 WHERE discord_id=? AND level=? AND passed=1",
            (discord_id, level))
        conn.commit()
    finally:
        conn.close()

    # 3. DM the student (private congratulation + certificate link)
    await _send_promotion_dm(discord_id, level, next_level, result)

    # 4. Champions post (public celebration)
    await _post_champions(discord_id, level, next_level, result)


async def _send_promotion_dm(discord_id: str, from_level: str, to_level: str,
                             result: dict) -> None:
    from . import bot as bot_mod
    b = getattr(bot_mod, "bot", None)
    if not b:
        return
    try:
        user = b.get_user(int(discord_id))
        if user is None:
            user = await b.fetch_user(int(discord_id))
    except Exception:
        return
    if not user:
        return

    overall = result.get("overall_pct", 0)
    msg = (
        f"🎓 **مبروك! اتقبلت في {to_level}!**\n\n"
        f"نتيجتك النهائية: **{overall}%** ✅\n"
        f"أنت أثبتّ إنك جاهز/ة للمستوى التالي. فخورين بيك!\n\n"
        f"📜 شهادتك متاحة على صفحة التمرين: "
        f"https://practice.empireenglish.online/assessment/certificate/\n\n"
        f"تقويمك اتجدّد — ابدأ {to_level} من الأسبوع الأول! 🚀\n"
        f"━━━━━━━━━━\n"
        f"🎓 **Congratulations! You've been promoted to {to_level}!**\n"
        f"Final score: {overall}%. You proved you're ready. We're proud of you!\n"
        f"Your calendar has been reset — start {to_level} from Week 1! 🚀"
    )
    try:
        await user.send(msg)
        logger.info(f"advancement: promotion DM sent to {discord_id}")
    except Exception as e:
        logger.warning(f"advancement: promotion DM failed: {e}")


async def _post_champions(discord_id: str, from_level: str, to_level: str,
                          result: dict) -> None:
    """Post a public celebration in the Champions channel."""
    from . import bot as bot_mod, itqan_outcomes
    b = getattr(bot_mod, "bot", None)
    if not b or not b.guilds:
        return

    guild = b.guilds[0]
    name = (database.get_member(discord_id) or {}).get("discord_name", "A student")
    overall = result.get("overall_pct", 0)

    # Reuse the champions channel finder from Itqan
    ch = await itqan_outcomes._champions_channel(guild, from_level)
    if not ch:
        return

    msg = (
        f"🎓🎓🎓 **LEVEL ADVANCEMENT** 🎓🎓🎓\n\n"
        f"**{name}** has advanced from **{from_level}** to **{to_level}**!\n"
        f"Final score: **{overall}%**\n\n"
        f"They completed all weekly tests, passed the monthly review, "
        f"and proved themselves in the advancement exam. مبروك! 🚀"
    )
    try:
        await ch.send(msg)
        logger.info(f"advancement: Champions post for {discord_id} ({from_level}->{to_level})")
    except Exception as e:
        logger.warning(f"advancement: Champions post failed: {e}")


# ============================================================
#  NOT-PASS → private support
# ============================================================

async def _send_not_pass_dm(discord_id: str, level: str, result: dict) -> None:
    from . import bot as bot_mod
    b = getattr(bot_mod, "bot", None)
    if not b:
        return
    try:
        user = b.get_user(int(discord_id))
        if user is None:
            user = await b.fetch_user(int(discord_id))
    except Exception:
        return
    if not user:
        return

    overall = result.get("overall_pct", 0)
    per_skill = result.get("per_skill", {})
    part_b = result.get("part_b_detail", {})
    reason = result.get("reason_if_failed", "")
    failed_skills = result.get("failed_skills", [])

    # Skill breakdown
    skill_lines = []
    for skill, score in sorted(per_skill.items()):
        mark = "✅" if score >= 60 else "⚠️"
        skill_lines.append(f"  {mark} {skill}: {score}%")
    skills_text = "\n".join(skill_lines) if skill_lines else ""

    # Part B breakdown
    part_b_text = ""
    if part_b:
        part_b_text = (
            f"\n🎙️ Part B ({part_b.get('total', 0)}/100):\n"
            f"  Fluency: {part_b.get('fluency', 0)}/25\n"
            f"  Accuracy: {part_b.get('accuracy', 0)}/25\n"
            f"  Vocab: {part_b.get('vocab_range', 0)}/25\n"
            f"  Pronunciation: {part_b.get('pronunciation', 0)}/25"
        )

    cfg = database.get_progression_config()
    cooldown_days = cfg.get("progression_advancement_retake_cooldown_days", 7)

    msg = (
        f"📊 **اختبار الترقية — {level}**\n"
        f"النتيجة: **{overall}%** (المطلوب 75%)\n\n"
        f"📊 **Part A — مهاراتك:**\n{skills_text}\n"
        f"{part_b_text}\n\n"
        f"{'⚠️ مهارات تحت الحد الأدنى: ' + ', '.join(failed_skills) if failed_skills else ''}\n"
        f"{'📝 السبب: ' + reason if reason else ''}\n\n"
        f"⏳ تقدر تعيد بعد {cooldown_days} أيام. "
        f"تقدّمك اليومي في أمان — كمّل تمرين! 🌱\n"
        f"━━━━━━━━━━\n"
        f"📊 **Advancement Exam — {level}**\n"
        f"Score: {overall}% (need 75%). Retake in {cooldown_days} days. "
        f"Your daily progress is safe — keep practising!"
    )
    try:
        await user.send(msg)
        logger.info(f"advancement: not-pass DM sent to {discord_id}")
    except Exception as e:
        logger.warning(f"advancement: not-pass DM failed: {e}")


# ============================================================
#  Owner notification (every attempt)
# ============================================================

async def _notify_owner(discord_id: str, level: str, result: dict) -> None:
    from . import ops_hub
    name = (database.get_member(discord_id) or {}).get("discord_name", str(discord_id))
    passed = result.get("passed", False)
    overall = result.get("overall_pct", 0)
    icon = "🎓" if passed else "📊"
    verdict = "PASSED — PROMOTED!" if passed else "not yet"

    body = (
        f"{icon} **{name}** — Advancement Exam ({level}): **{verdict}**\n"
        f"Overall: {overall}% | Part A: {result.get('part_a_score', 0)}% | "
        f"Part B: {result.get('part_b_score', 0)}/100"
    )
    try:
        severity = "info" if passed else "warning"
        await ops_hub.send_ops_alert("Advancement Exam attempt", body, severity=severity)
        logger.info(f"advancement: owner notified for {discord_id} ({verdict})")
    except Exception as e:
        logger.warning(f"advancement: owner notification failed: {e}")
