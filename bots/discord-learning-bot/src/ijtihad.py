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


def format_award_line(points: int) -> str:
    """One bilingual line to append to an existing celebration message.

    Deliberately additive: the celebration DMs/posts already exist and are warm.
    This does not restructure them, it just makes the reward visible -- silently
    crediting points a student never sees is the same as not paying them.
    """
    if points <= 0:
        return ""
    return f"\n🏅 **+{points} Ijtihad points** / **+{points} نقطة اجتهاد**"
