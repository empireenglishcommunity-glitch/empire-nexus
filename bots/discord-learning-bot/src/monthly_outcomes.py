"""Taqdeem — Monthly Review outcome delivery (Phase 3).

Routes a finished monthly review attempt to its consequence:
- **passed** → private congratulation DM with skill radar + trajectory
- **not_yet** → private DM with skill breakdown + review list + retake pointer
- **flagged** → owner notification for human review
- **2x consecutive fail** → owner alert ("student struggling with retention")

All side-effects are best-effort and never raise — scoring already
succeeded and was persisted in Phase 2.
"""
import json
import logging

from . import database

logger = logging.getLogger("empire-bot.monthly")


# ============================================================
#  Entry point
# ============================================================

async def deliver_monthly_outcome(discord_id: str, level: str,
                                  review_number: int, result: dict) -> None:
    """Fire the right consequence for a finished monthly review. Best-effort."""
    try:
        status = result.get("status")
        verdict = result.get("result")

        if status == "flagged":
            await _notify_owner_flagged(discord_id, level, review_number, result)
            return

        if verdict == "passed":
            await _send_pass_dm(discord_id, level, review_number, result)
            return

        # not_yet
        await _send_not_pass_dm(discord_id, level, review_number, result)

        # Check for 2 consecutive fails → owner alert
        await _check_consecutive_fails(discord_id, level, review_number)

    except Exception as e:
        logger.warning(f"monthly: outcome delivery error for {discord_id}: {e}")


# ============================================================
#  Pass — private congratulation
# ============================================================

async def _send_pass_dm(discord_id: str, level: str, review_number: int,
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

    retention = result.get("retention_pct", 0)
    breakdown = result.get("skill_breakdown", {})

    # Build skill radar text
    radar_lines = []
    for skill, score in sorted(breakdown.items()):
        bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
        radar_lines.append(f"  {skill}: {bar} {score}%")
    radar = "\n".join(radar_lines) if radar_lines else "  (no breakdown)"

    msg = (
        f"🌟 **مراجعتك الشهرية #{review_number} — ممتاز!**\n"
        f"Retention Score: **{retention}%** ✅\n\n"
        f"📊 **مهاراتك / Your skills:**\n{radar}\n\n"
        f"أنت ماشي صح — الاحتفاظ بالمعلومات ممتاز. كمّل كده! 🚀\n"
        f"━━━━━━━━━━\n"
        f"🌟 **Monthly Review #{review_number} — passed!**\n"
        f"Your retention across the last 4 weeks is solid. Keep it up!"
    )
    try:
        await user.send(msg)
        logger.info(f"monthly: pass DM sent to {discord_id} (review #{review_number})")
    except Exception as e:
        logger.warning(f"monthly: pass DM failed: {e}")


# ============================================================
#  Not-pass — private support
# ============================================================

async def _send_not_pass_dm(discord_id: str, level: str, review_number: int,
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

    retention = result.get("retention_pct", 0)
    breakdown = result.get("skill_breakdown", {})
    review_list = result.get("review_list", [])

    # Skill breakdown
    radar_lines = []
    for skill, score in sorted(breakdown.items()):
        bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
        radar_lines.append(f"  {skill}: {bar} {score}%")
    radar = "\n".join(radar_lines) if radar_lines else ""

    # Review items (up to 8)
    review_lines = []
    for item in review_list[:8]:
        word = item.get("word", "")
        week = item.get("source_week", "?")
        review_lines.append(f"  • {word} (week {week})")
    review_text = "\n".join(review_lines) if review_lines else "  • راجع كلمات الأسابيع السابقة"

    cfg = database.get_progression_config()
    cooldown_h = cfg.get("progression_monthly_retake_cooldown_hours", 72)

    msg = (
        f"📊 **مراجعتك الشهرية #{review_number}**\n"
        f"Retention Score: **{retention}%** (المطلوب 65%)\n\n"
        f"📊 **مهاراتك:**\n{radar}\n\n"
        f"📝 **راجع دول:**\n{review_text}\n\n"
        f"⏳ تقدر تعيد المراجعة بعد {cooldown_h} ساعة. "
        f"تقدّمك اليومي في أمان — مفيش حاجة اتقفلت. 🌱\n"
        f"━━━━━━━━━━\n"
        f"📊 **Monthly Review #{review_number}**\n"
        f"Score: {retention}% (need 65%). Review the items above and retake "
        f"in {cooldown_h}h. Your daily progress is safe — nothing was locked."
    )
    try:
        await user.send(msg)
        logger.info(f"monthly: not-pass DM sent to {discord_id} (review #{review_number})")
    except Exception as e:
        logger.warning(f"monthly: not-pass DM failed: {e}")


# ============================================================
#  2x consecutive fail → owner alert
# ============================================================

async def _check_consecutive_fails(discord_id: str, level: str,
                                   review_number: int) -> None:
    """If the student has failed the same monthly review 2+ times, alert owner."""
    conn = database._connect()
    fails = conn.execute(
        "SELECT COUNT(*) c FROM monthly_reviews "
        "WHERE discord_id=? AND level=? AND review_number=? AND passed=0",
        (discord_id, level, review_number),
    ).fetchone()
    conn.close()

    if not fails or fails["c"] < 2:
        return

    # Alert the owner
    from . import ops_hub
    name = (database.get_member(discord_id) or {}).get("discord_name", str(discord_id))
    body = (
        f"🔔 **{name}** has failed Monthly Review #{review_number} "
        f"({level}) **{fails['c']} times**.\n"
        f"This student may need help with retention — consider checking in."
    )
    try:
        await ops_hub.send_ops_alert("Monthly Review: student struggling", body, severity="info")
        logger.info(f"monthly: owner alert sent for {discord_id} (2x fail)")
    except Exception as e:
        logger.warning(f"monthly: owner alert failed: {e}")


# ============================================================
#  Flagged — owner notification
# ============================================================

async def _notify_owner_flagged(discord_id: str, level: str,
                                review_number: int, result: dict) -> None:
    from . import ops_hub
    name = (database.get_member(discord_id) or {}).get("discord_name", str(discord_id))
    reason = {
        "ai_error": "an AI/recording item couldn't be scored",
        "near_miss": "a near-miss just below the pass line",
    }.get(result.get("flag_reason"), "needs review")

    body = (
        f"🔔 **{name}** Monthly Review #{review_number} ({level}) — **flagged**.\n"
        f"Reason: {reason}\n"
        f"Retention: {result.get('retention_pct', 0)}%\n"
        f"Review the attempt and decide: pass manually or let them retake."
    )
    try:
        await ops_hub.send_ops_alert("Monthly Review: flagged for review", body, severity="warning")
        logger.info(f"monthly: flagged alert sent for {discord_id}")
    except Exception as e:
        logger.warning(f"monthly: flagged alert failed: {e}")


# ============================================================
#  Owner report: cohort monthly status
# ============================================================

def format_monthly_report(level: str = None) -> str:
    """Generate a text report of all students' monthly review status.
    Used by /monthly (Telegram) and /majlis-monthly (Discord)."""
    members = database.all_active_members()
    lines = ["📊 Monthly Review Status", "━" * 30, ""]

    for m in members:
        lvl = m.get("level", "A1")
        if level and lvl.upper() != level.upper():
            continue
        did = m["discord_id"]
        name = m.get("discord_name", did)
        mastered = len(database.itqan_mastered_weeks(did, lvl))
        passed = database.monthly_reviews_passed(did, lvl)
        taken = database.monthly_reviews_taken(did, lvl)
        due = database.monthly_review_due(did)

        status_icon = "✅" if passed > 0 else ("📋" if due else "⏳")
        due_text = " (DUE)" if due else ""
        lines.append(
            f"  {status_icon} {name} [{lvl}] — "
            f"weeklies: {mastered}, reviews: {passed}/{taken}{due_text}"
        )

    if not lines[3:]:
        lines.append("  (no students)")

    return "\n".join(lines)
