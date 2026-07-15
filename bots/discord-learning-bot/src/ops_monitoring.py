"""Markaz (مركز) Phases M4 + M5 — Weekly Report, Revenue Intelligence, System Health.

M4: Weekly business report (Sunday 9 AM Dubai), conversion/churn real-time
    alerts, monthly summary.
M5: System health monitoring (restart detection, Groq failure tracking,
    heartbeat presence, database error alerts).

All functions here are called either from bot.py task loops or from
specific hook points in other modules (e.g. ai_engine.py for Groq
failure tracking). None of them raise — failures are logged and
silently skipped, consistent with the rest of the Markaz design
("never crash the bot for an ops notification failure").
"""
import datetime
import logging
import time
from typing import Optional

from . import config, database, ops_hub

logger = logging.getLogger("empire-bot.ops_monitoring")

# ============================================================
#  M5.2: GROQ FAILURE TRACKING
# ============================================================

# In-memory counter (resets on restart, which is fine — we only care
# about sustained failures within a single running period, not
# historical counts). A restart itself already sends a separate
# "bot restarted" alert (M5.1), so the Groq counter naturally
# resetting after a restart is a feature, not a bug.
_groq_failures: list[float] = []  # timestamps of recent failures
_GROQ_FAILURE_THRESHOLD = 5
_GROQ_FAILURE_WINDOW = 3600  # 1 hour
_groq_alert_sent_at: float = 0  # throttle: max 1 alert per hour


async def track_groq_failure() -> None:
    """Call this from any Groq API call site on failure. If failures
    exceed the threshold within the window, sends a single alert to
    the owner (throttled to at most 1 per hour)."""
    global _groq_alert_sent_at
    now = time.time()
    _groq_failures.append(now)

    # Prune old entries outside the window
    cutoff = now - _GROQ_FAILURE_WINDOW
    while _groq_failures and _groq_failures[0] < cutoff:
        _groq_failures.pop(0)

    if len(_groq_failures) >= _GROQ_FAILURE_THRESHOLD:
        if now - _groq_alert_sent_at > _GROQ_FAILURE_WINDOW:
            _groq_alert_sent_at = now
            await ops_hub.send_ops_alert(
                "Groq API Issues",
                f"{len(_groq_failures)} failures in the last hour\\. "
                f"Gemini fallback is handling requests, but Groq may be "
                f"down or rate\\-limited\\.",
                severity="warning",
            )


# ============================================================
#  M5.1: BOT RESTART DETECTION
# ============================================================

async def notify_bot_restart() -> None:
    """Call once from on_ready() to inform the owner the bot just
    started/restarted. Useful for knowing deploys happened, and for
    catching unexpected restarts (OOM kills, crashes, etc.)."""
    try:
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y\\-%m\\-%d %H:%M UTC")
        await ops_hub.send_ops_alert(
            "Bot Restarted",
            f"Empire English Bot came online at {now}\\.\n"
            f"Version: `{ops_hub.escape_markdown(config.BOT_VERSION)}`",
            severity="info",
        )
    except Exception as e:
        logger.error(f"ops_monitoring: restart notification failed: {e}")


# ============================================================
#  M5.4: DATABASE ERROR DETECTION
# ============================================================

_db_error_alert_sent_at: float = 0  # throttle: max 1 per 10 minutes


async def notify_database_error(error: Exception, context: str = "") -> None:
    """Call from any database operation that catches a SQLite error.
    Sends a throttled alert to the owner (max 1 per 10 minutes)."""
    global _db_error_alert_sent_at
    now = time.time()
    if now - _db_error_alert_sent_at < 600:  # 10 min throttle
        return
    _db_error_alert_sent_at = now
    safe_err = ops_hub.escape_markdown(str(error)[:200])
    safe_ctx = ops_hub.escape_markdown(context[:100]) if context else "unknown"
    try:
        await ops_hub.send_ops_alert(
            "Database Error",
            f"Context: {safe_ctx}\nError: `{safe_err}`",
            severity="critical",
        )
    except Exception as e:
        logger.error(f"ops_monitoring: DB error notification failed: {e}")


# ============================================================
#  M4.1-M4.2: WEEKLY BUSINESS REPORT (Sunday 9 AM Dubai)
# ============================================================

async def send_weekly_report() -> None:
    """Comprehensive weekly business metrics report sent to the owner.
    Called by a @tasks.loop in bot.py (Sunday 9 AM Dubai time)."""
    try:
        from zoneinfo import ZoneInfo
        zone = ZoneInfo(config.TIMEZONE)
    except Exception:
        zone = datetime.timezone.utc

    now = datetime.datetime.now(zone)
    week_start = (now.date() - datetime.timedelta(days=7)).isoformat()
    week_end = (now.date() - datetime.timedelta(days=1)).isoformat()

    # Gather metrics
    total_members = database.member_count()
    members = database.all_active_members()

    # Activity this week (count unique active days per member)
    week_active = 0
    week_submissions = 0
    for day_offset in range(7):
        d = (now.date() - datetime.timedelta(days=day_offset + 1)).isoformat()
        day_active = database.count_active_members_on(d)
        day_subs = database.total_submissions_on_date(d)
        if day_active > 0:
            week_active = max(week_active, day_active)
        week_submissions += day_subs

    # New members this week
    new_this_week = 0
    for day_offset in range(7):
        d = (now.date() - datetime.timedelta(days=day_offset + 1)).isoformat()
        new_this_week += database.count_new_members_on(d)

    # Retention: members who were active at least 3 of 7 days
    active_3plus = 0
    for m in members:
        days_active = 0
        for day_offset in range(7):
            d = (now.date() - datetime.timedelta(days=day_offset + 1)).isoformat()
            subs = database.get_submissions_for_date(m["discord_id"], d)
            if subs:
                days_active += 1
        if days_active >= 3:
            active_3plus += 1

    retention_pct = round((active_3plus / total_members * 100), 1) if total_members > 0 else 0

    # Average tasks per active student
    avg_tasks = round(week_submissions / max(week_active, 1), 1)

    # Top 3 students by streak
    top_streaks = database.streak_leaderboard(limit=3)

    # Streak milestones this week
    all_milestones = []
    for day_offset in range(7):
        d = (now.date() - datetime.timedelta(days=day_offset + 1)).isoformat()
        all_milestones.extend(database.streak_milestones_on(d))

    # Level distribution
    levels = {}
    for lvl in ["L0", "L1", "L2", "L3"]:
        levels[lvl] = len(database.members_at_level(lvl))

    # Pending escalations
    pending = database.count_pending_escalations()

    # Build the report
    lines = [
        f"📊 *Weekly Report — Week ending {ops_hub.escape_markdown(week_end)}*",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "*📈 Growth*",
        f"  Total students: *{total_members}*",
        f"  New this week: *{new_this_week}*",
        "",
        "*🎯 Engagement*",
        f"  Peak daily active: *{week_active}*",
        f"  Tasks completed: *{week_submissions}*",
        f"  Avg tasks/active student: *{ops_hub.escape_markdown(str(avg_tasks))}*",
        f"  Retention \\(3\\+/7 days\\): *{ops_hub.escape_markdown(str(retention_pct))}%*",
        "",
        f"*👥 Levels:* 🌱L0:{levels['L0']} \\| 💪L1:{levels['L1']} \\| 🚀L2:{levels['L2']} \\| 👑L3:{levels['L3']}",
        "",
    ]

    if top_streaks:
        lines.append("*🔥 Top Streaks*")
        for i, s in enumerate(top_streaks, 1):
            name = (s.get("discord_name") or "?").split("#")[0]
            lines.append(f"  {i}\\. {ops_hub.escape_markdown(name)} — {s['current_streak']}d")
        lines.append("")

    if all_milestones:
        m_text = ", ".join(
            f"{ops_hub.escape_markdown(m['discord_name'])} {m['days']}d"
            for m in all_milestones[:5]
        )
        lines.append(f"🏆 Milestones this week: {len(all_milestones)} \\({m_text}\\)")
    else:
        lines.append("🏆 Milestones this week: 0")

    lines.append("")
    if pending > 0:
        lines.append(f"🚨 *{pending} pending escalation\\(s\\)*")
    else:
        lines.append("✅ All systems healthy, no pending escalations\\.")

    try:
        await ops_hub.send_ops_message("\n".join(lines))
    except Exception as e:
        logger.error(f"ops_monitoring: weekly report send failed: {e}")


# ============================================================
#  M4.3: CONVERSION-READY ALERT (first 7-day streak)
# ============================================================

async def check_conversion_ready(discord_id: str, student_name: str, streak: int) -> None:
    """Call when a student's streak is updated. If they just hit their
    FIRST 7-day streak, alert the owner — this is a strong conversion
    signal (engaged enough to be worth a personal follow-up/upsell)."""
    if streak != 7:
        return
    if not database.is_feature_enabled("markaz_conversion_alerts"):
        return

    # Check if this is genuinely the FIRST time they hit 7 (longest_streak
    # would be 7 if so — if it's higher, they've been here before).
    member = database.get_member(discord_id)
    if not member:
        return
    if member.get("longest_streak", 0) > 7:
        return  # Not their first time — skip

    safe_name = ops_hub.escape_markdown(student_name.split("#")[0])
    level = member.get("level", "?")
    await ops_hub.send_ops_alert(
        "Conversion Ready",
        f"🎯 *{safe_name}* just completed their first 7\\-day streak\\!\n"
        f"Level: {level}\n\n"
        f"This student is engaged and may be ready for a personal "
        f"follow\\-up, premium offer, or advanced track invitation\\.",
        severity="success",
    )


# ============================================================
#  M4.4: CHURN RISK ALERT (active student goes silent 3+ days)
# ============================================================

async def check_churn_risk() -> None:
    """Scan all active members for churn risk: previously active students
    (had a streak ≥ 3 at some point) who haven't submitted anything in
    3+ days. Called from the daily digest loop (once per day is enough —
    this is a slow-moving signal, not a real-time one).

    Sends at most 3 alerts per day to avoid flooding (the daily digest
    already shows overall metrics; these individual alerts are for the
    highest-value-at-risk students only)."""
    if not database.is_feature_enabled("markaz_churn_alerts"):
        return
    members = database.all_active_members()
    now = datetime.datetime.now(datetime.timezone.utc)
    at_risk = []

    for m in members:
        # Only care about students who were meaningfully engaged before
        longest = m.get("longest_streak", 0)
        if longest < 3:
            continue

        last_active = m.get("last_active_at", "")
        if not last_active:
            continue

        try:
            last_dt = datetime.datetime.fromisoformat(last_active.replace("Z", ""))
            days_silent = (now - last_dt).days
        except (ValueError, TypeError):
            continue

        if days_silent >= 3:
            at_risk.append({
                "name": (m.get("discord_name") or "?").split("#")[0],
                "level": m.get("level", "?"),
                "days_silent": days_silent,
                "longest_streak": longest,
                "current_streak": m.get("current_streak", 0),
            })

    # Sort by longest_streak descending (highest-value students first)
    at_risk.sort(key=lambda x: x["longest_streak"], reverse=True)

    # Send at most 3 individual alerts
    for student in at_risk[:3]:
        safe_name = ops_hub.escape_markdown(student["name"])
        await ops_hub.send_ops_alert(
            "Churn Risk",
            f"⚠️ *{safe_name}* \\({student['level']}\\) has been silent "
            f"for *{student['days_silent']} days*\\.\n"
            f"Previous best streak: {student['longest_streak']}d "
            f"\\(current: {student['current_streak']}d\\)\\.\n\n"
            f"Consider a personal reach\\-out\\.",
            severity="warning",
        )


# ============================================================
#  M4.5: MONTHLY SUMMARY (1st of month, 9:30 AM Dubai)
# ============================================================

async def send_monthly_summary() -> None:
    """High-level monthly overview: engagement tiers, growth, revenue
    potential. Called by a @tasks.loop on the 1st of each month."""
    try:
        from zoneinfo import ZoneInfo
        zone = ZoneInfo(config.TIMEZONE)
    except Exception:
        zone = datetime.timezone.utc

    now = datetime.datetime.now(zone)
    # Only run on the 1st
    if now.day != 1:
        return

    members = database.all_active_members()
    total = len(members)

    # Engagement tiers based on current_streak
    high_engagement = sum(1 for m in members if m.get("current_streak", 0) >= 14)
    medium_engagement = sum(1 for m in members if 3 <= m.get("current_streak", 0) < 14)
    low_engagement = sum(1 for m in members if m.get("current_streak", 0) < 3)

    # Level distribution
    levels = {}
    for lvl in ["L0", "L1", "L2", "L3"]:
        levels[lvl] = len(database.members_at_level(lvl))

    prev_month = (now.date().replace(day=1) - datetime.timedelta(days=1)).strftime("%B %Y")

    lines = [
        f"📅 *Monthly Summary — {ops_hub.escape_markdown(prev_month)}*",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"*👥 Total Active:* {total}",
        f"*📊 Engagement Tiers:*",
        f"  🟢 High \\(14\\+d streak\\): {high_engagement}",
        f"  🟡 Medium \\(3\\-13d\\): {medium_engagement}",
        f"  🔴 Low \\(<3d\\): {low_engagement}",
        "",
        f"*📈 Levels:* 🌱L0:{levels['L0']} \\| 💪L1:{levels['L1']} \\| 🚀L2:{levels['L2']} \\| 👑L3:{levels['L3']}",
        "",
        f"*💰 Revenue Potential:*",
        f"  Conversion\\-ready \\(streak≥7\\): {sum(1 for m in members if m.get('current_streak', 0) >= 7)}",
        f"  Premium candidates \\(L2\\+\\): {levels['L2'] + levels['L3']}",
        "",
        "💡 Focus: convert high\\-engagement L0/L1 students to paid tiers\\.",
    ]

    try:
        await ops_hub.send_ops_message("\n".join(lines))
    except Exception as e:
        logger.error(f"ops_monitoring: monthly summary send failed: {e}")
