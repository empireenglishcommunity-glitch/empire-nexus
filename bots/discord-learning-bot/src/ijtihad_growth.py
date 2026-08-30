"""Ijtihad Phase 6 — growth and grit. Seeing the students a score never shows.

WHY THIS PHASE EXISTS
---------------------
Everything so far measures effort or achievement. Neither can surface the student
the owner actually asked about: someone whose absolute English is weak, who fails,
and who comes back anyway. On any board sorted by any score they are invisible
forever -- and they are doing the hardest thing in the programme.

So this phase adds two things that are deliberately NOT rankings-by-score:

  * GROWTH -- measured against the student's own 14-day baseline, so a beginner
    improving 40% outranks a strong student who plateaued. Change, not level.
  * RECOGNITIONS -- five named moments that describe *character* rather than
    ability: Personal Best, Persistence, Comeback, Uphill, Refinement.

THE LOAD-BEARING DESIGN DECISION
Recognitions award NO points. They never move anyone up the effort board. That
separation is the whole reason we can celebrate determination honestly: a weaker
student gets genuinely, visibly seen without a stronger student being told their
work counted for less. Points measure work; recognitions notice people.

See .kiro/specs/ijtihad-effort-economy/ design §5.
"""
import datetime
import json
import logging

from . import database

logger = logging.getLogger("empire-bot.ijtihad_growth")

FLAG = "ijtihad_growth_recognition"

# A run of Full Days on the hardest difficulty tier that earns "Uphill".
UPHILL_MIN_STREAK = 5
# Days away that make a return a "Comeback" rather than an ordinary day.
COMEBACK_MIN_ABSENCE = 3
# Consecutive improving pronunciation scores that earn "Refinement".
REFINEMENT_MIN_RUN = 3

KINDS = {
    "personal_best": ("🌟", "Personal Best", "أفضل أسبوع لك"),
    "persistence":   ("🧱", "Persistence", "إصرار"),
    "comeback":      ("🔄", "Comeback", "رجوع قوي"),
    "uphill":        ("⛰️", "Uphill", "طريق صاعد"),
    "refinement":    ("🪞", "Refinement", "تحسين مستمر"),
}


def _bl(en: str, ar: str) -> str:
    return f"{en} / {ar}"


def _iso_week_key(day: datetime.date) -> str:
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


# ============================================================
#  Detectors — each returns (period_key, detail) or None
# ============================================================

def _detect_personal_best(discord_id: str, today: datetime.date):
    """Best 7-day points total the student has ever produced.

    Self-referential on purpose: infinitely fair across join dates, because it
    compares a student only with their own past.
    """
    now = database.ijtihad_points_between(
        (discord_id), (today - datetime.timedelta(days=6)).isoformat(),
        today.isoformat())
    if now <= 0:
        return None
    best_before = database.ijtihad_best_previous_week(discord_id, today)
    if best_before <= 0 or now <= best_before:
        return None
    return _iso_week_key(today), json.dumps({"points": now, "previous": best_before})


def _detect_comeback(discord_id: str, today: datetime.date):
    """Returned after real absence and completed a Full Day.

    The moment a student returns is the moment they are most likely to quit
    again, so it is the moment most worth acknowledging.
    """
    if not database.ijtihad_is_full_day(discord_id, today.isoformat()):
        return None
    away = database.ijtihad_days_absent_before(discord_id, today)
    if away < COMEBACK_MIN_ABSENCE:
        return None
    return today.isoformat(), json.dumps({"days_away": away})


def _detect_uphill(discord_id: str, today: datetime.date):
    """Sustained Full Days while on the hardest difficulty tier.

    Rewards choosing the harder road -- the exact behaviour the old economy
    punished, since Challenging content paid the same as Easy.
    """
    member = database.get_member(discord_id) or {}
    if int(member.get("difficulty_level", 2) or 2) < 3:
        return None
    fd = database.ijtihad_full_day_streak(discord_id, today, consume_freezes=False)
    if fd["streak"] < UPHILL_MIN_STREAK:
        return None
    return _iso_week_key(today), json.dumps({"streak": fd["streak"]})


def _detect_persistence(discord_id: str, today: datetime.date):
    """Failed an assessment, came back, and passed it.

    This is the single most important recognition in the set: it is the only one
    that requires having failed first.
    """
    conn = database._connect()
    try:
        rows = conn.execute(
            """SELECT level, week, result, finished_at FROM assessment_attempts
               WHERE discord_id = ? AND status = 'scored' AND result IS NOT NULL
               ORDER BY finished_at""",
            (discord_id,),
        ).fetchall()
    except Exception:
        return None
    finally:
        conn.close()

    failed = set()
    for r in rows:
        key = (r["level"], r["week"])
        if r["result"] == "not_yet":
            failed.add(key)
        elif r["result"] in ("mastered", "distinction") and key in failed:
            return (f"{r['level']}:w{r['week']}",
                    json.dumps({"level": r["level"], "week": r["week"]}))
    return None


def _detect_refinement(discord_id: str, today: datetime.date):
    """Pronunciation scores improving across consecutive attempts.

    Deliberately about the trend, not the absolute score: a student climbing
    40 -> 55 -> 62 is refining, even though 62 would look unremarkable on its own.
    """
    conn = database._connect()
    try:
        rows = conn.execute(
            """SELECT score FROM pronunciation_scores
               WHERE discord_id = ? ORDER BY scored_at DESC LIMIT ?""",
            (discord_id, REFINEMENT_MIN_RUN),
        ).fetchall()
    except Exception:
        return None
    finally:
        conn.close()
    if len(rows) < REFINEMENT_MIN_RUN:
        return None
    scores = [float(r["score"]) for r in rows][::-1]  # oldest -> newest
    if not all(b > a for a, b in zip(scores, scores[1:])):
        return None
    return _iso_week_key(today), json.dumps({"scores": scores})


_DETECTORS = {
    "personal_best": _detect_personal_best,
    "persistence": _detect_persistence,
    "comeback": _detect_comeback,
    "uphill": _detect_uphill,
    "refinement": _detect_refinement,
}


def detect_new(discord_id: str, today: datetime.date = None) -> list:
    """Run every detector and record anything new. Returns the new kinds.

    Never raises: a recognition is a nicety, and a broken detector must never
    break the flow that called it (a task submission, a nightly job).
    """
    today = today or database._today_local()
    if not database.is_feature_enabled(FLAG, str(discord_id)):
        return []
    found = []
    for kind, fn in _DETECTORS.items():
        try:
            hit = fn(discord_id, today)
        except Exception as e:
            logger.warning(f"ijtihad_growth: {kind} detector failed: {e}")
            continue
        if not hit:
            continue
        period_key, detail = hit
        if database.ijtihad_record_recognition(discord_id, kind, period_key, detail):
            found.append(kind)
    return found


# ============================================================
#  Rendering
# ============================================================

def format_recognition(kind: str) -> str:
    emoji, en, ar = KINDS.get(kind, ("🏅", kind, kind))
    return f"{emoji} **{en}** / **{ar}**"


def format_new_recognitions(kinds: list) -> str:
    """A short bilingual line to append to an existing message."""
    if not kinds:
        return ""
    return "\n" + "\n".join(format_recognition(k) for k in kinds)


def format_most_improved(rows: list) -> str:
    lines = [
        f"📈 **{_bl('Most improved', 'الأكثر تقدمًا')}**",
        _bl("Measured against each student's OWN recent baseline — not against "
            "each other.",
            "المقارنة مع مستوى كل طالب هو نفسه — مش مع بعض."),
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if not rows:
        lines.append("")
        lines.append(_bl("Not enough history yet to measure improvement.",
                         "لسه مافيش تاريخ كفاية لقياس التقدّم."))
        return "\n".join(lines)
    medals = ["🥇", "🥈", "🥉", "🔹", "🔹"]
    for i, r in enumerate(rows):
        badge = medals[i] if i < len(medals) else "🔹"
        name = (r.get("discord_name") or "Student").split("#")[0]
        lines.append(f"{badge} **{name}** ({r.get('level','?')}) — "
                     f"+{r['growth_pct']}%")
    lines.append("")
    lines.append(_bl("A beginner can top this board. That is the point.",
                     "المبتدئ يقدر يتصدّر هنا. وده المقصود."))
    return "\n".join(lines)


def format_my_growth(g: dict) -> str:
    """The student's own growth, framed so a decline is never a scolding."""
    if not g.get("eligible"):
        reason = g.get("reason")
        if reason == "too_new":
            return _bl("You're new — improvement needs a week of history first. "
                       "Keep going.",
                       "إنت جديد — قياس التقدّم محتاج أسبوع الأول. كمّل.")
        return _bl("No baseline yet — this week is your baseline. Next week we can "
                   "compare.",
                   "مافيش أساس للمقارنة لسه — الأسبوع ده هو الأساس. الأسبوع الجاي نقارن.")
    pct = g["growth_pct"]
    if pct > 0:
        return _bl(f"You're up **{pct}%** on your own recent average. "
                   f"({g['now']} vs {g['par_week']})",
                   f"إنت زايد **{pct}%** عن متوسطك. ({g['now']} مقابل {g['par_week']})")
    if pct == 0:
        return _bl(f"You're steady at your own average ({g['now']}).",
                   f"إنت ثابت على متوسطك ({g['now']}).")
    return _bl(f"You're **{abs(pct)}%** below your own recent average — "
               f"a lighter week, not a failure.",
               f"إنت أقل بـ **{abs(pct)}%** من متوسطك — أسبوع أخف، مش فشل.")


# ============================================================
#  Weekly spotlight — rotate WHICH metric is celebrated
# ============================================================

# Recognition ossifies if the same metric is celebrated every week: the same two
# or three names win forever and everyone else learns the spotlight is not for
# them. Rotating the metric means different people are genuinely in front.
SPOTLIGHT_ROTATION = ("effort", "improvement", "consistency", "achievement")


def spotlight_metric(day: datetime.date = None) -> str:
    day = day or database._today_local()
    _, week, _ = day.isocalendar()
    return SPOTLIGHT_ROTATION[week % len(SPOTLIGHT_ROTATION)]


def build_spotlight(day: datetime.date = None) -> dict:
    """Pick this week's metric and the students it highlights."""
    day = day or database._today_local()
    metric = spotlight_metric(day)
    season = database.ijtihad_current_season(day)
    if metric == "improvement":
        rows = database.ijtihad_most_improved_board(limit=3, today=day)
    elif metric == "consistency":
        rows = database.ijtihad_consistency_board(limit=3)
    elif metric == "achievement":
        rows = database.sijil_hall_of_honour(limit=3)
    else:
        rows = database.ijtihad_season_leaderboard(season, limit=3) if season else []
    return {"metric": metric, "rows": rows, "season": season}


def format_spotlight(spot: dict) -> str:
    metric = spot["metric"]
    rows = spot["rows"]
    titles = {
        "effort": ("⚔️", _bl("Hardest working this season", "الأكثر اجتهادًا الموسم ده")),
        "improvement": ("📈", _bl("Biggest improvement", "أكبر تقدّم")),
        "consistency": ("🎯", _bl("Most consistent", "الأكثر انتظامًا")),
        "achievement": ("🏛️", _bl("Most earned, all time", "الأكثر إنجازًا على الإطلاق")),
    }
    emoji, title = titles.get(metric, ("✨", metric))
    lines = [f"{emoji} **{_bl('Weekly spotlight', 'ضوء الأسبوع')}** — {title}",
             "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    if not rows:
        lines.append(_bl("Nothing to highlight yet this week.",
                         "مافيش حاجة نسلط عليها الضوء الأسبوع ده."))
        return "\n".join(lines)
    for r in rows:
        name = (r.get("discord_name") or "Student").split("#")[0]
        if metric == "improvement":
            detail = f"+{r.get('growth_pct', 0)}%"
        elif metric == "consistency":
            detail = f"{r.get('streak', 0)}d"
        elif metric == "achievement":
            detail = f"📚 {r.get('weeks_mastered', 0)}"
        else:
            detail = f"{r.get('season_points', 0)}"
        lines.append(f"✨ **{name}** — {detail}")
    lines.append("")
    lines.append(_bl("The spotlight changes what it measures every week.",
                     "ضوء الأسبوع بيغيّر اللي بيقيسه كل أسبوع."))
    return "\n".join(lines)
