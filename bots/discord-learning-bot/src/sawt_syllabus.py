"""Empire English Chronicles — CEFR/syllabus alignment (Phase 6).

Ties the daily story to the SAME curriculum the rest of Empire English runs on
(spec R7):

  * TARGET LEVEL is derived from LIVE student data — the CEFR band the active
    student body actually occupies — never hardcoded (R7.2). Today that resolves
    to A1 (all active students are A1); it will follow the community as it grows.
  * The level's `config.PODCAST_LEVEL_PROFILES` entry then drives pace, vocabulary
    band, and the duration window (R7.1) — those already flow through
    `sawt_story.target_length` / `sawt_cast.speed_for_level` / the audio gate's
    `duration_window`, so this module's job is to pick the right LEVEL and feed the
    current week's VOCABULARY in.
  * CURRENT WEEK is the representative curriculum week for that band, and its words
    (`curriculum.get_vocabulary_for_week`) are woven into the story — never shown
    as a word list (R7.3).
  * ARABIC support is DEFERRED but designed-for: the profile already carries
    `arabic_ratio`; `arabic_directive()` is the single reserved hook, disabled
    today, so scaffolding can be switched on later without a rewrite (R7.4).

Everything degrades gracefully: if the DB/curriculum can't be read (e.g. the
offline CI render has no database), the target level falls back to
`sawt_story.STORY_LEVEL` and vocabulary is simply empty — the episode is still
level-shaped by its profile and never blocks.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Optional

logger = logging.getLogger("empire-bot.sawt.syllabus")

# How many current-week words to surface to the writer. A handful is enough to
# reinforce naturally; a long list would push the story toward a vocabulary drill.
MAX_VOCAB_WORDS = 8

# ARABIC SCAFFOLDING MASTER SWITCH (R7.4). Reserved hook only — the owner's
# standing decision is English-only, so this stays False. When enabled, the level
# profile's arabic_ratio would drive how much Arabic clarification is woven in.
ARABIC_SCAFFOLDING_ENABLED = False


def _default_level() -> str:
    try:
        from . import sawt_story
        return sawt_story.STORY_LEVEL
    except Exception:                                            # noqa: BLE001
        return "A2"


def resolve_target_level() -> str:
    """The CEFR band to pitch today's episode at, from LIVE member data (R7.2).

    It's the MODE of active members' levels (the band the most students occupy),
    with ties broken toward the LOWER band (kinder to more learners). Falls back to
    the story default if there's no readable membership (e.g. CI has no DB).
    """
    try:
        from . import database, config
        members = database.all_active_members()
        levels = [config.cefr_key(m.get("level") or "") for m in members
                  if (m.get("level") or "").strip()]
        levels = [lv for lv in levels if lv in config.CEFR_ORDER]
        if not levels:
            return _default_level()
        counts = Counter(levels)
        top = max(counts.values())
        # Tie-break toward the lowest band (serve the most learners gently).
        winners = [lv for lv, c in counts.items() if c == top]
        winners.sort(key=lambda lv: config.CEFR_ORDER.index(lv))
        return winners[0]
    except Exception:                                            # noqa: BLE001
        logger.exception("resolve_target_level failed; using default level")
        return _default_level()


def resolve_current_week(level: str) -> int:
    """A representative curriculum week for `level`, from live data (R7.3).

    Uses the MEDIAN week of active members at that level (robust to outliers),
    clamped to the number of authored weeks for the level. Falls back to week 1
    when there's nothing to read.
    """
    try:
        from . import database, config, curriculum
        key = config.cefr_key(level)
        members = [m for m in database.all_active_members()
                   if config.cefr_key(m.get("level") or "") == key]
        weeks = []
        for m in members:
            try:
                weeks.append(int(database.member_week_number(m["discord_id"])))
            except Exception:                                    # noqa: BLE001
                continue
        if not weeks:
            week = 1
        else:
            weeks.sort()
            week = weeks[len(weeks) // 2]                        # median
        try:
            maxw = int(curriculum.max_week_for_level(key))
            if maxw >= 1:
                week = max(1, min(week, maxw))
        except Exception:                                        # noqa: BLE001
            week = max(1, week)
        return week
    except Exception:                                            # noqa: BLE001
        logger.exception("resolve_current_week failed; using week 1")
        return 1


def vocabulary_for(level: str, week: int, limit: int = MAX_VOCAB_WORDS) -> list[str]:
    """The current curriculum week's target words (English) for `level`, to weave
    into the story. Returns [] on any problem (so generation never depends on it)."""
    try:
        from . import config, curriculum
        # Ensure the weekly content is loaded (idempotent). The offline generator
        # does not boot the bot, so nothing else will have called it.
        try:
            if not getattr(curriculum, "_weekly_data", None):
                curriculum.load_all()
        except Exception:                                        # noqa: BLE001
            pass
        rows = curriculum.get_vocabulary_for_week(int(week), config.cefr_key(level))
        words = []
        for r in rows or []:
            w = (r.get("word") if isinstance(r, dict) else str(r)) or ""
            w = w.strip()
            if w:
                words.append(w)
        return words[:max(0, int(limit))]
    except Exception:                                            # noqa: BLE001
        logger.exception("vocabulary_for failed; no curriculum words this episode")
        return []


def arabic_directive(level: str) -> str:
    """RESERVED Arabic-scaffolding hook (R7.4). Returns a prompt directive when
    ARABIC_SCAFFOLDING_ENABLED is on (using the level's arabic_ratio), else ''.
    Kept as the single switch so enabling Arabic later needs no rewrite."""
    if not ARABIC_SCAFFOLDING_ENABLED:
        return ""
    try:
        from . import config
        ratio = float(config.podcast_level_profile(level).get("arabic_ratio", 0.0))
    except Exception:                                            # noqa: BLE001
        ratio = 0.0
    if ratio <= 0.0:
        return ""
    pct = int(round(ratio * 100))
    return (f"\nARABIC SUPPORT: weave in gentle Egyptian-Arabic clarifications for "
            f"the hardest new words — about {pct}% of the words, right after the "
            f"English, never as a separate translation list.")


def plan_for_today() -> dict:
    """One call the daily generator uses: resolve the level, its week, and the
    current-week vocabulary to reinforce. Always returns a usable dict."""
    level = resolve_target_level()
    week = resolve_current_week(level)
    vocab = vocabulary_for(level, week)
    return {"level": level, "week": week, "vocabulary": vocab}
