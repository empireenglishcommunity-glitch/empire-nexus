"""Ijtihad Phase 5 — boards. Replacing the single god-board.

WHY THERE ARE SEVERAL BOARDS INSTEAD OF ONE
-------------------------------------------
The old system had exactly one public ranking (lifetime points) plus a nightly
streak ranking. Both were won by the same people for the same reason: they had
been present longest. With one board there is one winner and sixteen losers, and
the winner is decided mostly by join date.

So there are now several surfaces on which *different kinds of student* can lead:

  * Season effort   -> whoever is working hardest right now (resets every 4 weeks)
  * Journey peers   -> whoever leads among students at the same STAGE, not tenure
  * Consistency     -> whoever is most reliable, even if slow
  * Sijil / Hall    -> whoever has built the most, ever (Phase 1 — veterans' own)

THE SIZE RULE
-------------
Every board here is capped at the top 3-5 and shows only students who actually
earned something. With ~17 active students, a top-10 board names most of the
community and quietly tells half of them they are losing. A student's own
standing is added to the reply they personally asked for, rather than published
in a list for everyone to read.

See .kiro/specs/ijtihad-effort-economy/ design §4.
"""
import datetime
import logging

from . import database

logger = logging.getLogger("empire-bot.ijtihad_boards")

FLAG = "ijtihad_boards"

_MEDALS = ["🥇", "🥈", "🥉", "🔹", "🔹"]


def _bl(en: str, ar: str) -> str:
    return f"{en} / {ar}"


def _name(raw: str) -> str:
    return (raw or "Student").split("#")[0]


def season_title(season: dict) -> str:
    """'Season 3 · Sep-Oct' — numbered, with a human month range.

    Numbering is self-maintaining (nobody has to invent a theme every 4 weeks
    forever); the month range is what makes it feel like a real period.
    """
    if not season:
        return _bl("No season yet", "مافيش موسم")
    try:
        start = datetime.date.fromisoformat(season["started_on"])
        end = datetime.date.fromisoformat(season["ends_on"])
        span = (start.strftime("%b") if start.month == end.month
                else f"{start.strftime('%b')}–{end.strftime('%b')}")
        return f"{season['label']} · {span}"
    except Exception:
        return season.get("label", "Season")


def format_season_board(season: dict, rows: list, me_id: str = "",
                        my_rank: int = 0, my_points: int = 0) -> str:
    """The season effort board: top few + the caller's own standing."""
    if not season:
        return (f"⏳ {_bl('Seasons have not started yet.', 'المواسم لسه مبدأتش.')}")

    lines = [
        f"⚔️ **{season_title(season)}** — {_bl('Effort', 'الاجتهاد')}",
        _bl("Resets every 4 weeks. Whoever works hardest NOW leads.",
            "بيتصفّر كل ٤ أسابيع. اللي بيشتغل بجد دلوقتي هو اللي يتقدّم."),
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if not rows:
        lines.append("")
        lines.append(_bl("Nobody has earned points yet this season — the board is "
                         "wide open.",
                         "محدش كسب نقط الموسم ده لحد الآن — الميدان مفتوح."))
    else:
        for i, r in enumerate(rows):
            badge = _MEDALS[i] if i < len(_MEDALS) else "🔹"
            lines.append(f"{badge} **{_name(r['discord_name'])}** "
                         f"({r.get('level', '?')}) — {r['season_points']}")

    shown = {str(r["discord_id"]) for r in rows}
    if me_id and str(me_id) not in shown:
        lines.append("")
        if my_rank and my_points:
            lines.append(f"📍 {_bl('You', 'إنت')}: **#{my_rank}** — {my_points}")
        else:
            lines.append(f"📍 {_bl('You have not earned points yet this season.', 'لسه مكسبتش نقط الموسم ده.')}")
    return "\n".join(lines)


def format_peers_board(scope: str, week: int, season: dict, rows: list,
                       me_id: str = "") -> str:
    """Journey-stage peers — comparison against students at the same stage.

    The scope line is shown on purpose: a student should know WHO they are being
    compared with, otherwise a ranking is just a number someone asserts.
    """
    if not season:
        return f"⏳ {_bl('Seasons have not started yet.', 'المواسم لسه مبدأتش.')}"

    scope_label = {
        "journey": _bl(f"students around week {week} of their journey",
                       f"طلبة حوالين الأسبوع {week} في رحلتهم"),
        "level": _bl("students at your level", "طلبة في مستواك"),
        "community": _bl("the whole community", "المجتمع كله"),
    }.get(scope, scope)

    lines = [
        f"🧭 **{_bl('Your peers', 'زمايلك')}** — {season_title(season)}",
        _bl(f"Compared with {scope_label}.", f"المقارنة مع {scope_label}."),
        _bl("Compared by stage, not by how long anyone has been here.",
            "المقارنة بالمرحلة، مش بمدة وجودك."),
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if not rows:
        lines.append("")
        lines.append(_bl("No effort recorded in your group yet this season.",
                         "مافيش اجتهاد مسجل في مجموعتك الموسم ده."))
        return "\n".join(lines)

    for i, r in enumerate(rows):
        badge = _MEDALS[i] if i < len(_MEDALS) else "🔹"
        you = f"  ← {_bl('you', 'إنت')}" if me_id and str(r["discord_id"]) == str(me_id) else ""
        lines.append(f"{badge} **{_name(r['discord_name'])}** — {r['season_points']}{you}")
    return "\n".join(lines)


def format_consistency_board(rows: list) -> str:
    """Reliability, not speed. A student on a target of 3 can top this board."""
    lines = [
        f"🎯 **{_bl('Consistency', 'الاستمرارية')}**",
        _bl("Longest current run of complete days — each measured against that "
            "student's OWN daily target.",
            "أطول سلسلة أيام كاملة — كل واحد بيتقاس على هدفه اليومي هو."),
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if not rows:
        lines.append("")
        lines.append(_bl("No active runs yet. One complete day starts one.",
                         "مافيش سلاسل شغالة. يوم كامل واحد بيبدأ سلسلة."))
        return "\n".join(lines)
    for i, r in enumerate(rows):
        badge = _MEDALS[i] if i < len(_MEDALS) else "🔹"
        lines.append(f"{badge} **{_name(r['discord_name'])}** — "
                     f"{r['streak']} {_bl('days', 'يوم')} "
                     f"({_bl('target', 'هدف')} {r['target']})")
    return "\n".join(lines)


def format_full_day_roll(day: str, rows: list, streaks: list) -> str:
    """The reformed nightly post.

    The old #streak-tracker RANKED up to 15 students by a streak that counted any
    day with >= 1 task -- the most public surface in the system, measuring the
    least meaningful thing, and naming the bottom half while doing it.

    This is a ROLL, not a ranking: everyone listed did their work today. Nobody
    can appear in a losing position, because there are no positions. A small top-3
    of current runs is appended for aspiration, which is a different thing from
    ranking everybody.
    """
    try:
        pretty = datetime.date.fromisoformat(day).strftime("%d %b")
    except Exception:
        pretty = day

    lines = [
        f"✅ **{_bl('Complete days', 'الأيام الكاملة')}** — {pretty}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if not rows:
        lines.append("")
        lines.append(_bl("Nobody finished their target today — tomorrow is open.",
                         "محدش خلّص هدفه النهاردة — بكرة فرصة جديدة."))
    else:
        names = " · ".join(f"**{_name(r['discord_name'])}** ({r['tasks']})" for r in rows)
        lines.append(names)
        lines.append("")
        n = len(rows)
        lines.append(_bl(f"{n} student{'s' if n != 1 else ''} hit their target today.",
                         f"{n} طالب وصلوا هدفهم النهاردة."))

    if streaks:
        lines.append("")
        lines.append(f"🔥 **{_bl('Longest runs', 'أطول السلاسل')}**: " +
                     " · ".join(f"{_name(s['discord_name'])} {s['streak']}d"
                                for s in streaks[:3]))
    return "\n".join(lines)
