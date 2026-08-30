"""Ijtihad Phase 3 — achievement payouts. The central inversion.

THE PROBLEM THIS FIXES
----------------------
Before this module, the four highest-signal achievements in the whole programme
were worth **exactly zero points**:

  * passing the weekly mastery assessment      -> 0
  * scoring a distinction (>=90%)              -> 0
  * passing the monthly progress review        -> 0
  * being promoted a level (A1->A2, ...)       -> 0

`POINTS_ASSESSMENT` and `POINTS_ADVANCEMENT` existed in config.py but were never
called from any production module. Meanwhile pure attendance paid 105-205 points
per day. The economy literally could not express "this student improved" -- only
"this student showed up".

So achievement is now the LARGEST award in the economy. Promotion pays 500,
roughly 33 completed tasks. That is the inversion: what you *achieve* should
outweigh how often you *appear*.

HOW IT INTERACTS WITH SEASONS
-----------------------------
Nothing special is needed. Season effort is derived from `points_log` date
windows (Phase 2), so an award made here is automatically counted in whatever
season it lands in. It also flows into lifetime `total_points` as before, which
is harmless -- that number is now Legacy XP, shown in Sijil.

DEDUP
-----
Every award has a unique reason string and is paid at most once, ever
(`database.ijtihad_award_once`). An achievement is a permanent fact, not a
repeatable action.

See .kiro/specs/ijtihad-effort-economy/ design §2.4.
"""
import datetime
import logging

from . import database

logger = logging.getLogger("empire-bot.ijtihad")

FLAG = "ijtihad_achievement_awards"


def _enabled(discord_id: str) -> bool:
    try:
        return database.is_feature_enabled(FLAG, str(discord_id))
    except Exception:
        return False


def _amounts() -> dict:
    return database.get_ijtihad_config()


def award_week_mastery(discord_id: str, level: str, week: int,
                       distinction: bool = False) -> int:
    """Pay for mastering a curriculum week. Returns points awarded (0 if off or
    already paid).

    A week pays once. If the student first mastered it (150) and LATER earns a
    distinction on the same week, they receive only the difference as a top-up
    rather than the full 250 again -- so the total for that week converges on the
    distinction value without ever double-paying the base.
    """
    if not _enabled(discord_id):
        return 0
    cfg = _amounts()
    base_reason = f"ijtihad:mastery:{level}:w{week}"
    try:
        if not distinction:
            return database.ijtihad_award_once(
                discord_id, base_reason, int(cfg["ijtihad_ip_mastery"]))

        full = int(cfg["ijtihad_ip_distinction"])
        base = int(cfg["ijtihad_ip_mastery"])
        if database.ijtihad_already_awarded(discord_id, base_reason):
            # Base already paid -> top up to the distinction value.
            topup = max(0, full - base)
            return database.ijtihad_award_once(
                discord_id, f"ijtihad:distinction-topup:{level}:w{week}", topup)
        # First award for this week, and it's a distinction: pay the full amount
        # under the base reason so the week can never also collect the base.
        return database.ijtihad_award_once(discord_id, base_reason, full)
    except Exception as e:
        logger.warning(f"ijtihad: mastery award failed for {discord_id}: {e}")
        return 0


def award_monthly_review(discord_id: str, level: str, review_number: int) -> int:
    """Pay for passing a monthly progress review."""
    if not _enabled(discord_id):
        return 0
    try:
        return database.ijtihad_award_once(
            discord_id,
            f"ijtihad:monthly:{level}:r{review_number}",
            int(_amounts()["ijtihad_ip_monthly"]),
        )
    except Exception as e:
        logger.warning(f"ijtihad: monthly award failed for {discord_id}: {e}")
        return 0


def award_promotion(discord_id: str, from_level: str) -> int:
    """Pay for a level promotion -- the biggest single award in the economy.

    Keyed on the level being LEFT, so each rung of the ladder pays exactly once
    even if the student somehow re-passes an exam for that level.
    """
    if not _enabled(discord_id):
        return 0
    try:
        return database.ijtihad_award_once(
            discord_id,
            f"ijtihad:promotion:{from_level}",
            int(_amounts()["ijtihad_ip_promotion"]),
        )
    except Exception as e:
        logger.warning(f"ijtihad: promotion award failed for {discord_id}: {e}")
        return 0


# ============================================================
#  PHASE 7 — THE AWARD TABLE
# ============================================================
#
# This is the change the earlier phases deliberately deferred, because it can
# only be done coherently in one piece. It REPLACES POINTS_PER_TASK (15) and
# POINTS_ALL_TASKS (100) and the STREAK_BONUS_POINTS ladder. Introducing any one
# of them alongside the legacy values would have produced two overlapping awards
# for the same action -- the exact double-award class of bug Phase 0.2 removed.
#
# Two behaviours it fixes that no amount of tuning could:
#
#   1. ATTEMPTING HARDER WORK WAS IRRATIONAL. Adaptive difficulty made tasks
#      longer and faster at "Challenging" for exactly the same 15 points as
#      "Easy", so a points-maximising student should have deliberately scored
#      badly. Difficulty now multiplies the award.
#
#   2. QUALITY WAS INVISIBLE. A 95%-accurate recording and a mumbled one paid
#      identically. Quality now multiplies too -- but only UPWARDS. The band
#      floor is 1.0, so a student who tries and does badly still receives the
#      full base award. Punishing low scores would hit precisely the
#      struggling-but-persistent students this whole rework exists to keep.
#
# Both multipliers degrade to x1.0 when their engine is disabled, so this works
# today with `tatawwur_adaptive` and `tatawwur_pronunciation` still off.

TABLE_FLAG = "ijtihad_award_table"


def award_table_enabled(discord_id: str) -> bool:
    try:
        return database.is_feature_enabled(TABLE_FLAG, str(discord_id))
    except Exception:
        return False


def difficulty_multiplier(discord_id: str, cfg: dict = None) -> float:
    """1.0 / 1.25 / 1.5 by adaptive difficulty tier.

    Returns 1.0 when `tatawwur_adaptive` is OFF: the difficulty column still holds
    a default of 2 for everyone, and paying a 1.25x bonus to the whole community
    for a tier nothing is actually assigning would be a silent across-the-board
    inflation rather than a reward for choosing harder work.
    """
    cfg = cfg or database.get_ijtihad_config()
    try:
        if not database.is_feature_enabled("tatawwur_adaptive", str(discord_id)):
            return 1.0
    except Exception:
        return 1.0
    member = database.get_member(discord_id) or {}
    tier = int(member.get("difficulty_level", 2) or 2)
    key = {1: "ijtihad_mult_easy", 2: "ijtihad_mult_standard",
           3: "ijtihad_mult_challenging"}.get(tier, "ijtihad_mult_standard")
    return max(1.0, int(cfg[key]) / 100.0)


def quality_multiplier(discord_id: str, task_id: str, day: str = None,
                       cfg: dict = None) -> float:
    """1.0 -> 1.3 by the score on this task, if a score exists.

    NEVER below 1.0 (see the module note): trying is never punished. Returns 1.0
    when no score is available, which is the normal case while pronunciation
    scoring is disabled.
    """
    cfg = cfg or database.get_ijtihad_config()
    day = day or database._today_local().isoformat()
    score = None
    try:
        score = database.ijtihad_task_score(discord_id, task_id, day)
    except Exception:
        score = None
    if score is None:
        return 1.0
    if score >= 90:
        return max(1.0, int(cfg["ijtihad_quality_90"]) / 100.0)
    if score >= 80:
        return max(1.0, int(cfg["ijtihad_quality_80"]) / 100.0)
    if score >= 70:
        return max(1.0, int(cfg["ijtihad_quality_70"]) / 100.0)
    return 1.0


def compute_task_award(discord_id: str, task_id: str, day: str = None,
                       cfg: dict = None) -> dict:
    """Points for ONE completed task under the new table.

    Returns {"points", "base", "difficulty_mult", "quality_mult"} so the caller
    (and the tests) can see how the number was reached rather than trusting it.
    """
    cfg = cfg or database.get_ijtihad_config()
    base = int(cfg["ijtihad_base_ip"])
    dm = difficulty_multiplier(discord_id, cfg)
    qm = quality_multiplier(discord_id, task_id, day, cfg)
    return {"points": int(round(base * dm * qm)), "base": base,
            "difficulty_mult": dm, "quality_mult": qm}


def award_full_day(discord_id: str, day: str = None, cfg: dict = None) -> int:
    """Bonus for meeting YOUR OWN daily target. Paid once per day.

    Replaces POINTS_ALL_TASKS, which only ever paid at 7/7 and so was
    unreachable for a student whose honest capacity is 3 a day.
    """
    cfg = cfg or database.get_ijtihad_config()
    day = day or database._today_local().isoformat()
    return database.ijtihad_award_once(
        discord_id, f"ijtihad:fullday:{day}", int(cfg["ijtihad_full_day_ip"]))


def award_streak_bonus(discord_id: str, cfg: dict = None) -> tuple:
    """Seasonal full-day streak bonus. Returns (threshold, points) or (0, 0).

    Season-scoped and bounded at 28 days, replacing the legacy ladder whose
    100-day rung was worth 333 tasks -- a prize only long tenure could reach, and
    the single clearest way the old economy paid for seniority rather than work.
    """
    cfg = cfg or database.get_ijtihad_config()
    season = database.ijtihad_current_season()
    if not season:
        return 0, 0
    try:
        streak = database.ijtihad_full_day_streak(
            discord_id, consume_freezes=False)["streak"]
    except Exception:
        return 0, 0

    # 🔴 CAP THE STREAK AT THE SEASON'S AGE.
    #
    # Found live on 2026-08-30, on day ONE of Season 1: a student with a 28-day
    # full-day streak built BEFORE the season immediately collected the top
    # 28-day bonus (600). The streak is computed over all history, so without
    # this cap a long-standing student banks the maximum seasonal bonus on the
    # season's first submission -- which is precisely the "reward tenure, not
    # work" behaviour this entire rework exists to remove. The bug was in the
    # one place best positioned to reintroduce it.
    #
    # Capping at days-elapsed means the bonus can only ever be earned by days
    # actually worked INSIDE the season: on day 1 the effective streak is 1, so
    # nothing is payable until the 7th day of a season at the earliest.
    try:
        start = datetime.date.fromisoformat(season["started_on"])
        elapsed = (database._today_local() - start).days + 1
        streak = min(streak, max(0, elapsed))
    except (ValueError, TypeError, KeyError):
        return 0, 0

    # Pay the highest threshold reached that has not been paid this season.
    for threshold in reversed(database.IJTIHAD_STREAK_THRESHOLDS):
        if streak < threshold:
            continue
        reason = f"ijtihad:streak:{season['id']}:{threshold}"
        points = int(cfg.get(f"ijtihad_streak_{threshold}", 0))
        awarded = database.ijtihad_award_once(discord_id, reason, points)
        if awarded:
            return threshold, awarded
        return 0, 0
    return 0, 0


def award_submission(discord_id: str, task_id: str, tasks_today: int) -> dict:
    """The whole per-submission award under the new table.

    Returns {"points", "task_points", "full_day_points", "streak_threshold",
    "streak_points", "detail"}. The caller decides what to show the student.
    """
    cfg = database.get_ijtihad_config()
    day = database._today_local().isoformat()

    detail = compute_task_award(discord_id, task_id, day, cfg)
    task_points = detail["points"]
    database.add_points(discord_id, task_points, f"task:{task_id}")

    target = database.ijtihad_get_target(discord_id)
    full_day_points = 0
    if tasks_today >= target:
        full_day_points = award_full_day(discord_id, day, cfg)

    threshold, streak_points = (0, 0)
    if full_day_points or tasks_today >= target:
        threshold, streak_points = award_streak_bonus(discord_id, cfg)

    return {
        "points": task_points + full_day_points + streak_points,
        "task_points": task_points,
        "full_day_points": full_day_points,
        "streak_threshold": threshold,
        "streak_points": streak_points,
        "target": target,
        "detail": detail,
    }


def format_award_line(points: int) -> str:
    """One bilingual line to append to an existing celebration message.

    Deliberately additive: the celebration DMs/posts already exist and are warm.
    This does not restructure them, it just makes the reward visible -- silently
    crediting points a student never sees is the same as not paying them.
    """
    if points <= 0:
        return ""
    return f"\n🏅 **+{points} Ijtihad points** / **+{points} نقطة اجتهاد**"
