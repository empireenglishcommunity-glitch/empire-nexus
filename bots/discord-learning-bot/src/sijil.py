"""Sijil (سجل) — the permanent Record of Honour. Ijtihad Phase 1.

WHY THIS EXISTS
---------------
The XP economy is being changed so that effort is measured **seasonally**: it
resets every 4 weeks, so a student who joined last week can compete with one who
joined six months ago. That fixes the real unfairness (rank was a lifetime
integral, so seniority beat effort), but it creates a new risk: the students who
have been here longest would feel their history was deleted.

Sijil is the answer to that, and it is built FIRST -- deliberately before any
reset exists -- so veterans see their record preserved before they ever see a
season start at zero. It is permanent, never resets, and never decays.

It contains only things that were genuinely earned and cannot be farmed by
showing up: weeks mastered, distinctions, levels passed by examination, monthly
reviews passed, perfect (7/7) days, and the all-time best streak. Plus "Legacy
XP" -- the pre-Ijtihad lifetime points total, preserved verbatim and labelled as
history rather than as a live ranking.

This module is pure read + render. It writes nothing.
See .kiro/specs/ijtihad-effort-economy/ design §3.
"""
import logging

from . import database

logger = logging.getLogger("empire-bot.sijil")

FLAG = "ijtihad_sijil"


def _bl(en: str, ar: str) -> str:
    """Bilingual line, English first (matches the rest of the bot's student copy)."""
    return f"{en} / {ar}"


def build_record(discord_id: str) -> dict:
    """The student's permanent record. Never raises, never returns None."""
    try:
        return database.sijil_record(discord_id)
    except Exception as e:
        logger.error(f"sijil: build_record failed for {discord_id}: {e}")
        return {
            "exists": False, "legacy_xp": 0, "longest_streak": 0,
            "current_level": "A1", "joined_at": "", "weeks_mastered": 0,
            "distinctions": 0, "monthly_reviews_passed": 0, "lifetime_tasks": 0,
            "active_days": 0, "perfect_days": 0, "levels_earned": [],
        }


def has_any_achievement(record: dict) -> bool:
    """True when the student has earned at least one durable achievement.

    Used to decide between the full trophy case and the encouraging empty state.
    Deliberately excludes legacy_xp and lifetime_tasks: attendance is not an
    achievement, which is the entire thesis of this rework.
    """
    return bool(
        record.get("weeks_mastered")
        or record.get("distinctions")
        or record.get("monthly_reviews_passed")
        or record.get("levels_earned")
        or record.get("perfect_days")
    )


def format_record(record: dict, display_name: str) -> str:
    """Render one student's Sijil for Discord.

    A brand-new student must never see a wall of zeros that reads like a
    report card of failure -- they get a short, honest "your record starts now"
    instead. That empty state is a requirement, not a nicety (spec R7/1.4).
    """
    name = display_name or "Student"
    lines = [
        f"📜 **{name}'s Sijil** — {_bl('Record of Honour', 'سجل الشرف')}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if not has_any_achievement(record):
        lines += [
            "",
            _bl("Your record is empty — for now.", "سجلك فاضي — دلوقتي بس."),
            "",
            _bl("This page only fills up with things you EARN: weeks you master, "
                "distinctions you score, levels you pass, perfect 7/7 days.",
                "الصفحة دي بتتملي بحاجات بتكسبها: أسابيع بتتقنها، تقديرات امتياز، "
                "مستويات بتعديها، وأيام كاملة ٧/٧."),
            _bl("Time spent here earns nothing on this page. Work does.",
                "الوقت لوحده مش بيجيب حاجة هنا. الشغل هو اللي بيجيب."),
        ]
        if record.get("lifetime_tasks"):
            lines += [
                "",
                _bl(f"You have completed {record['lifetime_tasks']} tasks so far — "
                    f"keep going and your first badge is close.",
                    f"خلصت {record['lifetime_tasks']} مهمة لحد دلوقتي — "
                    f"كمّل وأول وسام قريب."),
            ]
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(_bl("Permanent. Never resets.", "دائم. مايتصفّرش أبدًا."))
        return "\n".join(lines)

    # --- Earned achievements ---
    lines.append("")
    lines.append(f"🏅 **{_bl('Earned', 'المكتسب')}**")

    if record.get("weeks_mastered"):
        lines.append(f"  📚 {_bl('Weeks mastered', 'أسابيع متقنة')}: "
                     f"**{record['weeks_mastered']}**")
    if record.get("distinctions"):
        lines.append(f"  ⭐ {_bl('Distinctions', 'تقديرات امتياز')}: "
                     f"**{record['distinctions']}**")
    if record.get("monthly_reviews_passed"):
        lines.append(f"  📈 {_bl('Monthly reviews passed', 'مراجعات شهرية ناجحة')}: "
                     f"**{record['monthly_reviews_passed']}**")
    if record.get("perfect_days"):
        lines.append(f"  💯 {_bl('Perfect days (7/7)', 'أيام كاملة ٧/٧')}: "
                     f"**{record['perfect_days']}**")

    levels = record.get("levels_earned") or []
    if levels:
        earned = ", ".join(lv["level"] for lv in levels)
        lines.append(f"  🎓 {_bl('Levels passed by exam', 'مستويات بامتحان')}: "
                     f"**{earned}**")

    # --- All-time bests ---
    lines.append("")
    lines.append(f"🗻 **{_bl('All-time best', 'أفضل ما حققته')}**")
    lines.append(f"  🔥 {_bl('Longest streak ever', 'أطول سلسلة')}: "
                 f"**{record.get('longest_streak', 0)}** "
                 f"{_bl('days', 'يوم')}")
    lines.append(f"  ✅ {_bl('Total tasks completed', 'إجمالي المهام')}: "
                 f"**{record.get('lifetime_tasks', 0)}**")
    lines.append(f"  📆 {_bl('Active days', 'أيام نشطة')}: "
                 f"**{record.get('active_days', 0)}**")

    if record.get("legacy_xp"):
        lines.append("")
        lines.append(f"🏛️ {_bl('Legacy XP (before seasons)', 'نقاط قديمة (قبل المواسم)')}: "
                     f"**{record['legacy_xp']}**")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(_bl("Permanent. Never resets.", "دائم. مايتصفّرش أبدًا."))
    return "\n".join(lines)


def format_hall_of_honour(entries: list) -> str:
    """Render the Hall of Honour — the permanent board.

    Capped by the caller (default 5). Ranked by achievement, never by tenure or
    lifetime points, so it cannot become another seniority ladder.
    """
    lines = [
        f"🏛️ **{_bl('Hall of Honour', 'قاعة الشرف')}**",
        _bl("Ranked by what was earned — not by how long anyone has been here.",
            "الترتيب بالمكتسب — مش بمدة وجودك."),
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if not entries:
        lines.append("")
        lines.append(_bl("No achievements recorded yet. This board fills up when "
                         "students start mastering weeks.",
                         "مافيش إنجازات مسجلة لحد الآن. القاعة بتتملي لما الطلبة "
                         "يبدأوا يتقنوا الأسابيع."))
        return "\n".join(lines)

    medals = ["🥇", "🥈", "🥉"]
    for i, e in enumerate(entries):
        badge = medals[i] if i < len(medals) else "🔹"
        raw_name = e.get("discord_name") or "Student"
        name = raw_name.split("#")[0]
        bits = []
        if e.get("weeks_mastered"):
            bits.append(f"📚 {e['weeks_mastered']}")
        if e.get("distinctions"):
            bits.append(f"⭐ {e['distinctions']}")
        if e.get("levels_earned"):
            bits.append(f"🎓 {e['levels_earned']}")
        detail = " · ".join(bits) if bits else "—"
        lines.append(f"{badge} **{name}** ({e.get('level', '?')}) — {detail}")

    lines.append("")
    lines.append(_bl("📚 weeks mastered · ⭐ distinctions · 🎓 levels passed",
                     "📚 أسابيع متقنة · ⭐ امتياز · 🎓 مستويات"))
    return "\n".join(lines)
