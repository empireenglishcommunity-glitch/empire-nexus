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



# ============================================================
#  SCORING (Phase 2)
# ============================================================
#
# Pure, testable scoring. Objective items are graded here directly; for the
# recording-based items (pronunciation, speaking) the caller supplies the
# Whisper transcript and writing supplies the text — so this module stays free
# of network/audio concerns and is fully unit-testable. Grading is deliberately
# LENIENT for beginners: a genuine attempt is rewarded; we are not marking
# native-level grammar.

import re

_BORDERLINE_MARGIN = 5.0  # within ±5 of the pass line → flag for the owner


def _canon(s: str) -> str:
    """Lowercase, strip, drop punctuation/extra spaces — forgiving compare."""
    s = (s or "").strip().lower()
    s = re.sub(r"[^\w\s]", "", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _forgiving_equal(a: str, b: str) -> bool:
    ca, cb = _canon(a), _canon(b)
    if not ca or not cb:
        return False
    if ca == cb:
        return True
    # tolerate a single-character typo for words longer than 3 letters
    return len(cb) > 3 and _levenshtein(ca, cb) <= 1


def score_objective(item: dict, answer: str) -> dict:
    """Grade a vocab/listening item. Returns {auto_score, correct, feedback}."""
    expected = item.get("payload", {}).get("expected", "")
    correct = _forgiving_equal(answer, expected)
    return {
        "auto_score": 100.0 if correct else 0.0,
        "correct": correct,
        "feedback": "" if correct else f"Correct answer: {expected}",
    }


def score_pronunciation(expected_word: str, transcript: str) -> dict:
    """Lenient pronunciation score from a Whisper transcript."""
    ct = _canon(transcript)
    tokens = ct.split()
    if _forgiving_equal(expected_word, transcript) or _canon(expected_word) in tokens:
        return {"ai_score": 100.0, "correct": True, "feedback": ""}
    # partial credit if any token is close
    ce = _canon(expected_word)
    if any(len(ce) > 3 and _levenshtein(ce, t) <= 2 for t in tokens):
        return {"ai_score": 60.0, "correct": False,
                "feedback": f"Close — keep practicing “{expected_word}”."}
    return {"ai_score": 0.0, "correct": False,
            "feedback": f"Target word: “{expected_word}”."}


def _coverage(target_words: list, text: str) -> float:
    if not target_words:
        return 1.0
    toks = set(_canon(text).split())
    hit = sum(1 for w in target_words if _canon(w) in toks)
    return hit / len(target_words)


def score_speaking(target_words: list, transcript: str, min_words: int = 5) -> dict:
    """Lenient speaking score: reward a real attempt, add for target-word use."""
    words = _canon(transcript).split()
    if len(words) < 2:  # essentially silent / no real attempt
        return {"ai_score": 0.0, "correct": False,
                "feedback": "No speech detected — try recording again."}
    base = 40.0 if len(words) >= min_words else 25.0
    score = min(100.0, base + 60.0 * _coverage(target_words, transcript))
    return {"ai_score": round(score, 1), "correct": score >= 60,
            "feedback": "Nice effort — keep using this week's words." if score < 100 else ""}


def score_writing(target_words: list, text: str, min_chars: int = 40) -> dict:
    """Lenient writing score: reward length + target-word use."""
    clean = (text or "").strip()
    if len(clean) < 10:
        return {"ai_score": 0.0, "correct": False,
                "feedback": "Too short — write a couple of sentences."}
    base = 40.0 if len(clean) >= min_chars else 25.0
    score = min(100.0, base + 60.0 * _coverage(target_words, text))
    return {"ai_score": round(score, 1), "correct": score >= 60,
            "feedback": "Good — try to include more of this week's words." if score < 100 else ""}


def compute_consistency(discord_id: str, level: str, week: int) -> float:
    """How consistently the student did week `week`'s daily core work — the
    'were they actually active' dimension. % of (day × core-exercise) cells
    completed at least once for the week."""
    cal = database.get_calendar_mastery(discord_id, level)
    core = database.PRACTICE_EXERCISES
    expected = 7 * len(core)
    if expected == 0:
        return 0.0
    done = 0
    for day in range(1, 8):
        ex = (cal.get((week, day)) or {}).get("exercises", {})
        for c in core:
            if ex.get(c, 0) >= 1:
                done += 1
    return round(100.0 * done / expected, 1)


def score_attempt(item_scores: list, consistency_pct: float,
                  has_ai_error: bool = False, cfg: dict = None) -> dict:
    """Combine per-item scores + consistency into the final verdict.

    Returns {mastery_pct, consistency_pct, result, distinction, status}.
    - result: 'mastered' | 'not_yet'
    - status: 'scored' | 'flagged'  (flagged = owner should decide:
      an AI item errored, or the mastery score sits right on the pass line)
    """
    cfg = cfg or database.get_itqan_config()
    mastery_pass = cfg["itqan_mastery_pass_pct"]
    consistency_pass = cfg["itqan_consistency_pass_pct"]
    distinction_pct = cfg["itqan_distinction_pct"]

    mastery_pct = round(sum(item_scores) / len(item_scores), 1) if item_scores else 0.0

    passed = (mastery_pct >= mastery_pass) and (consistency_pct >= consistency_pass)
    distinction = passed and (mastery_pct >= distinction_pct)

    borderline = abs(mastery_pct - mastery_pass) <= _BORDERLINE_MARGIN
    status = "flagged" if (has_ai_error or borderline) else "scored"

    return {
        "mastery_pct": mastery_pct,
        "consistency_pct": round(consistency_pct, 1),
        "result": "mastered" if passed else "not_yet",
        "distinction": distinction,
        "status": status,
    }



# ============================================================
#  ATTEMPT LIFECYCLE (Phase 3) — server-side anti-cheat
# ============================================================
#
# start / submit / finish, with the integrity rules enforced on the SERVER
# (never trusting the client): unlock gate, one in-progress attempt, cooldown
# between retakes, the time limit, and a fresh item draw per attempt.

import json as _json
import datetime as _dt
import logging as _logging

_alog = _logging.getLogger("empire-bot.itqan")


def _utcnow() -> "_dt.datetime":
    """Naive UTC 'now' — matches SQLite's naive-UTC datetime('now') strings
    so the two can be compared directly (and avoids the deprecated utcnow())."""
    return _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)


def week_unlocked(discord_id: str, level: str, week: int):
    """Unlock rule (R1): every day of the week completed at least once
    (day is green). Returns (unlocked: bool, days_remaining: list[int])."""
    cal = database.get_calendar_mastery(discord_id, level)
    remaining = [d for d in range(1, 8)
                 if (cal.get((week, d)) or {}).get("day_tier", 0) < 1]
    return (len(remaining) == 0, remaining)


def _cooldown_until(last_finished: dict, cfg: dict):
    if not last_finished or not last_finished.get("finished_at"):
        return None
    try:
        fin = _dt.datetime.fromisoformat(last_finished["finished_at"])
    except (ValueError, TypeError):
        return None
    return fin + _dt.timedelta(minutes=cfg["itqan_retake_cooldown_min"])


def get_week_state(discord_id: str, level: str, week: int) -> dict:
    """State for the calendar/page: locked | available | in_progress |
    cooldown | not_yet | mastered."""
    if database.itqan_is_mastered(discord_id, level, week):
        return {"state": "mastered"}
    unlocked, remaining = week_unlocked(discord_id, level, week)
    if not unlocked:
        return {"state": "locked", "days_remaining": remaining}
    active = database.itqan_active_attempt(discord_id, level, week)
    if active:
        return {"state": "in_progress", "attempt_id": active["id"]}
    cfg = database.get_itqan_config()
    last = database.itqan_last_finished(discord_id, level, week)
    cd = _cooldown_until(last, cfg)
    if cd and _utcnow() < cd:
        return {"state": "cooldown", "cooldown_until": cd.isoformat(),
                "last_result": last.get("result")}
    if last:
        return {"state": "not_yet", "available": True, "last_result": last.get("result")}
    return {"state": "available"}


def _public_payload(skill: str, payload: dict) -> dict:
    """Strip the answer before sending an item to the client."""
    if skill == "vocab":
        return {"prompt_ar": payload.get("prompt_ar", "")}
    if skill == "listening":
        return {"say_en": payload.get("say_en", "")}
    if skill == "pronunciation":
        return {"word": payload.get("word", ""), "pronunciation": payload.get("pronunciation", "")}
    # speaking / writing: prompts + hints are fine to show
    return {k: v for k, v in payload.items() if k != "expected"}


def start_attempt(discord_id: str, level: str, week: int) -> dict:
    """Create a new attempt if allowed. Returns {ok, attempt_id, time_limit_min,
    items:[public]} or {ok:False, error}."""
    if not database.is_feature_enabled("itqan_weekly_assessment", discord_id):
        return {"ok": False, "error": "disabled"}
    if database.itqan_is_mastered(discord_id, level, week):
        return {"ok": False, "error": "already_mastered"}
    unlocked, remaining = week_unlocked(discord_id, level, week)
    if not unlocked:
        return {"ok": False, "error": "locked", "days_remaining": remaining}
    if database.itqan_active_attempt(discord_id, level, week):
        return {"ok": False, "error": "attempt_in_progress"}
    cfg = database.get_itqan_config()
    last = database.itqan_last_finished(discord_id, level, week)
    cd = _cooldown_until(last, cfg)
    if cd and _utcnow() < cd:
        return {"ok": False, "error": "cooldown", "cooldown_until": cd.isoformat()}

    # fresh seed per attempt → re-draw (anti-memorization)
    seed = f"{discord_id}:{level}:{week}:{_utcnow().timestamp()}"
    bp = generate_blueprint(discord_id, level, week, seed=seed)
    attempt = database.itqan_create_attempt(discord_id, level, week, seed)
    database.itqan_insert_items(attempt["id"], discord_id, bp["items"])
    return {
        "ok": True,
        "attempt_id": attempt["id"],
        "attempt_no": attempt["attempt_no"],
        "time_limit_min": bp["time_limit_min"],
        "items": [
            {"item_no": it["item_no"], "skill": it["skill"],
             "source_week": it["source_week"],
             "payload": _public_payload(it["skill"], it.get("payload", {}))}
            for it in bp["items"]
        ],
    }


async def submit_item(discord_id: str, attempt_id: int, item_no: int,
                      answer: str = "", audio_bytes: bytes = None) -> dict:
    """Score and store one item's answer. Objective items compare to the stored
    expected; audio items (pronunciation/speaking) are transcribed via Whisper
    then scored; writing scores the text. Graceful on transcription failure."""
    attempt = database.itqan_get_attempt(attempt_id)
    if not attempt or str(attempt["discord_id"]) != str(discord_id):
        return {"ok": False, "error": "not_found"}
    if attempt["status"] != "in_progress":
        return {"ok": False, "error": "not_in_progress"}
    items = {i["item_no"]: i for i in database.itqan_get_items(attempt_id)}
    row = items.get(item_no)
    if not row:
        return {"ok": False, "error": "bad_item"}
    payload = _json.loads(row["prompt_ref"] or "{}")
    skill = row["skill"]

    if skill in ("vocab", "listening"):
        res = score_objective({"payload": payload}, answer)
        database.itqan_save_item(attempt_id, item_no, answer,
                                 auto_score=res["auto_score"], correct=res["correct"],
                                 feedback=res["feedback"])
        return {"ok": True}

    if skill in ("pronunciation", "speaking"):
        transcript = None
        if audio_bytes:
            try:
                from . import pronunciation_scorer
                transcript = await pronunciation_scorer.transcribe_audio(audio_bytes)
            except Exception as e:
                _alog.warning(f"itqan transcription error: {e}")
                transcript = None
        if transcript is None:
            # graceful: keep the attempt, mark for owner review at finish
            database.itqan_save_item(attempt_id, item_no, "", ai_score=None,
                                     feedback="__pending_review__")
            return {"ok": True, "pending_review": True}
        if skill == "pronunciation":
            res = score_pronunciation(payload.get("expected", ""), transcript)
        else:
            res = score_speaking(payload.get("target_words", []), transcript)
        database.itqan_save_item(attempt_id, item_no, transcript,
                                 ai_score=res["ai_score"], correct=res["correct"],
                                 feedback=res["feedback"])
        return {"ok": True}

    # writing
    res = score_writing(payload.get("target_words", []), answer)
    database.itqan_save_item(attempt_id, item_no, answer,
                             ai_score=res["ai_score"], correct=res["correct"],
                             feedback=res["feedback"])
    return {"ok": True}


def finish_attempt(discord_id: str, attempt_id: int, integrity_flags: dict = None) -> dict:
    """Aggregate item scores + consistency → verdict; persist; on mastery
    upsert week_mastery. Returns the results payload."""
    attempt = database.itqan_get_attempt(attempt_id)
    if not attempt or str(attempt["discord_id"]) != str(discord_id):
        return {"ok": False, "error": "not_found"}
    if attempt["status"] != "in_progress":
        return {"ok": False, "error": "not_in_progress"}

    level, week = attempt["level"], attempt["week"]
    items = database.itqan_get_items(attempt_id)
    item_scores = []
    has_ai_error = False
    per_item = []
    for it in items:
        if it.get("feedback") == "__pending_review__":
            has_ai_error = True
            score = 0.0
        else:
            score = it["auto_score"] if it["auto_score"] is not None else \
                    (it["ai_score"] if it["ai_score"] is not None else 0.0)
        item_scores.append(score)
        per_item.append({"item_no": it["item_no"], "skill": it["skill"],
                         "correct": it["correct"], "feedback": it["feedback"],
                         "expected": it["expected"]})

    consistency = compute_consistency(discord_id, level, week)
    cfg = database.get_itqan_config()
    verdict = score_attempt(item_scores, consistency, has_ai_error=has_ai_error, cfg=cfg)

    # time limit (server-side)
    time_expired = False
    try:
        started = _dt.datetime.fromisoformat(attempt["started_at"])
        time_expired = (_utcnow() - started) > _dt.timedelta(
            minutes=cfg["itqan_time_limit_min"] + 1)  # +1 min grace
    except (ValueError, TypeError, KeyError):
        pass

    # persist integrity flags
    if integrity_flags:
        conn = database._connect()
        conn.execute("UPDATE assessment_attempts SET integrity_flags=? WHERE id=?",
                     (_json.dumps(integrity_flags), attempt_id))
        conn.commit()
        conn.close()

    database.itqan_finish_attempt(
        attempt_id, verdict["mastery_pct"], verdict["consistency_pct"],
        verdict["result"], verdict["distinction"], verdict["status"], time_expired)

    if verdict["result"] == "mastered" and verdict["status"] == "scored":
        database.itqan_upsert_mastery(discord_id, level, week,
                                      verdict["distinction"], attempt_id)

    return {"ok": True, "verdict": verdict, "items": per_item}
