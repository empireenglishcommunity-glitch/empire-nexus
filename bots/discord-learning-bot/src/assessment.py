"""Itqan (weekly assessment) — generation engine.

Builds a week's test *blueprint* (the list of items) from the curriculum plus
the spiral rule: mostly the current week, a little from earlier weeks chosen
from what the student is most likely to have forgotten (their SRS due queue).

This module is PURE structure — it does not score anything and is not wired to
any user surface yet (later phases). Everything stays inert until the
`itqan_weekly_assessment` flag is turned on.
"""
import random
from typing import Optional

from . import curriculum, database

# Objective (auto-gradeable) skills we cycle through for the non-production
# portion of the test. Speaking + writing (production) are added separately.
_OBJECTIVE_SKILLS = ("vocab", "listening", "pronunciation")


def _week_vocab(level: str, week: int) -> list[dict]:
    return list(curriculum.get_vocabulary_for_week(week, level) or [])


def _vocab_item(v: dict, source_week: int, skill: str) -> dict:
    """Turn a curriculum word into one objective item of the given skill."""
    word = v.get("word", "")
    arabic = v.get("arabic", "")
    pron = v.get("pronunciation", "")
    if skill == "vocab":
        # Show the Arabic meaning, expect the English word (recall).
        payload = {"prompt_ar": arabic, "expected": word,
                   "direction": "ar_to_en", "pronunciation": pron}
    elif skill == "listening":
        # Kokoro says the English word; student gives the meaning.
        payload = {"say_en": word, "expected": arabic, "pronunciation": pron}
    else:  # pronunciation
        # Word shown + modeled by Kokoro; student records; Whisper scores.
        payload = {"word": word, "expected": word, "pronunciation": pron}
    return {"skill": skill, "source_week": source_week, "payload": payload}


def _prior_weak_words(discord_id: str, level: str, week: int,
                      rng: random.Random, want: int) -> list[dict]:
    """Pick `want` words from weeks 1..week-1, favoring the student's SRS
    due (weak) words — what they're most likely to have forgotten. Falls back
    to random earlier-week words when the weak queue is thin."""
    if week <= 1 or want <= 0:
        return []
    prior: list[dict] = []
    for w in range(1, week):
        for v in _week_vocab(level, w):
            item = dict(v)
            item["_week"] = w
            prior.append(item)
    if not prior:
        return []
    due_words = {d.get("word") for d in database.get_due_reviews(discord_id, limit=100)}
    weak = [v for v in prior if v.get("word") in due_words]
    rest = [v for v in prior if v.get("word") not in due_words]
    rng.shuffle(weak)
    rng.shuffle(rest)
    return (weak + rest)[:want]


def generate_blueprint(discord_id: str, level: str, week: int,
                       seed: Optional[str] = None,
                       total_items: int = 10) -> dict:
    """Build the blueprint for one week-`week` assessment attempt.

    Deterministic for a given `seed` (so a resumed attempt shows the same
    items); pass a fresh seed per new attempt to re-draw (anti-memorization).

    Returns: {level, week, seed, time_limit_min, items: [ {item_no, skill,
    source_week, payload}, ... ]} with all five skills represented and a
    ~65/35 current-vs-earlier split on the objective items.
    """
    cfg = database.get_itqan_config()
    recent_weight = cfg["itqan_spiral_recent_weight"]
    time_limit = cfg["itqan_time_limit_min"]

    if seed is None:
        seed = f"{discord_id}:{level}:{week}:{random.randint(1, 1_000_000)}"
    rng = random.Random(seed)

    recent = _week_vocab(level, week)
    recent_shuffled = list(recent)
    rng.shuffle(recent_shuffled)
    theme = curriculum.get_theme(week, level) or "this week's topic"
    target_words = [v.get("word") for v in recent_shuffled[:6] if v.get("word")]

    items: list[dict] = []

    # 1) Two production items from the CURRENT week, always (speaking + writing).
    items.append({
        "skill": "speaking", "source_week": week,
        "payload": {
            "prompt_en": f"Speak for 30 seconds about {theme}. Try to use this week's words.",
            "prompt_ar": f"اتكلّم ٣٠ ثانية عن {theme}. حاول تستخدم كلمات الأسبوع.",
            "target_words": target_words, "min_seconds": 30,
        },
    })
    items.append({
        "skill": "writing", "source_week": week,
        "payload": {
            "prompt_en": f"Write 2–3 sentences about {theme}.",
            "prompt_ar": f"اكتب ٢–٣ جمل عن {theme}.",
            "target_words": target_words, "min_chars": 40,
        },
    })

    # 2) Objective items: split the rest ~65% current / ~35% earlier weeks.
    remaining = max(0, total_items - len(items))
    if week <= 1:
        recent_n, prior_n = remaining, 0
    else:
        recent_n = round(remaining * recent_weight)
        prior_n = remaining - recent_n

    # Current-week objective items (cycle vocab/listening/pronunciation).
    for i in range(recent_n):
        if not recent_shuffled:
            break
        v = recent_shuffled[i % len(recent_shuffled)]
        skill = _OBJECTIVE_SKILLS[i % len(_OBJECTIVE_SKILLS)]
        items.append(_vocab_item(v, week, skill))

    # Earlier-week objective items (weak-queue favored).
    prior = _prior_weak_words(discord_id, level, week, rng, prior_n)
    for i, v in enumerate(prior):
        skill = _OBJECTIVE_SKILLS[i % len(_OBJECTIVE_SKILLS)]
        items.append(_vocab_item(v, v.get("_week", week), skill))

    for idx, it in enumerate(items, start=1):
        it["item_no"] = idx

    return {
        "level": level, "week": week, "seed": seed,
        "time_limit_min": time_limit, "items": items,
    }
