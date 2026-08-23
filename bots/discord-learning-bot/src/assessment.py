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
        # Dictation: Kokoro says the English word; the student types the English
        # word they heard (a true listening/spelling check — fair for beginners
        # and no fuzzy Arabic-meaning matching). `arabic` kept only as a hint.
        payload = {"say_en": word, "expected": word, "hint_ar": arabic, "pronunciation": pron}
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

    Returns {mastery_pct, consistency_pct, result, distinction, status, flag_reason}.
    - result: 'mastered' | 'not_yet'
    - status: 'scored' | 'flagged'
    - flag_reason: '' | 'ai_error' | 'near_miss'

    A **clear pass just passes** (celebrated immediately — no review limbo). We
    only ask a human to look when the student did NOT pass AND a human might
    fairly change the outcome:
      • 'ai_error'  — an AI/transcription item couldn't be scored, so the score
        is unreliable and may be understated; or
      • 'near_miss' — they did the daily work (consistency met) but landed just
        below the mastery line (within the margin) — a rescue candidate.
    A clear not-yet (well below, work not done) is scored normally → supportive.
    """
    cfg = cfg or database.get_itqan_config()
    mastery_pass = cfg["itqan_mastery_pass_pct"]
    consistency_pass = cfg["itqan_consistency_pass_pct"]
    distinction_pct = cfg["itqan_distinction_pct"]

    mastery_pct = round(sum(item_scores) / len(item_scores), 1) if item_scores else 0.0

    passed = (mastery_pct >= mastery_pass) and (consistency_pct >= consistency_pass)
    distinction = passed and (mastery_pct >= distinction_pct)

    flag_reason = ""
    if not passed:
        near_miss = (consistency_pct >= consistency_pass
                     and 0 <= (mastery_pass - mastery_pct) <= _BORDERLINE_MARGIN)
        if has_ai_error:
            flag_reason = "ai_error"
        elif near_miss:
            flag_reason = "near_miss"
    status = "flagged" if flag_reason else "scored"

    return {
        "mastery_pct": mastery_pct,
        "consistency_pct": round(consistency_pct, 1),
        "result": "mastered" if passed else "not_yet",
        "distinction": distinction,
        "status": status,
        "flag_reason": flag_reason,
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
                      answer: str = "", audio_bytes: bytes = None,
                      audio_filename: str = "recording.webm") -> dict:
    """Score and store one item's answer. Objective items compare to the stored
    expected; audio items (pronunciation/speaking) are transcribed via Whisper
    then scored; writing scores the text. Graceful on transcription failure.

    Audio recordings are retained (owner-only) for review via itqan_save_recording."""
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
        # Retain the recording for owner review (best-effort; never blocks scoring).
        if audio_bytes:
            try:
                database.itqan_save_recording(attempt_id, discord_id, item_no,
                                              skill, audio_filename, audio_bytes)
            except Exception as e:
                _alog.warning(f"itqan: save recording failed: {e}")
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

    # Void an abandoned/blank attempt instead of scoring a 0% fail + starting a
    # 12h retake cooldown. An attempt with ZERO answered items was never really
    # taken (the student opened the test and left; the client auto-finishes it
    # when the timer has lapsed on their return). Fixed 2026-07-28 after Mai's
    # week-1 attempt was auto-scored 0% "not_yet" from an abandoned session.
    answered = sum(
        1 for it in items
        if it.get("auto_score") is not None
        or it.get("ai_score") is not None
        or it.get("feedback") == "__pending_review__"
        or (it.get("answer") or "").strip()
    )
    if answered == 0:
        database.itqan_delete_attempt(attempt_id)
        return {"ok": True, "voided": True}

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



# ============================================================
#  OWNER REPORT FORMATTING (Phase 7)
# ============================================================
#
# Turns database.itqan_report_data() into plain text that is safe to drop
# inside a Discord/Telegram code block (no Markdown, no backticks), so both
# surfaces can share one formatter.

def _pct(v) -> str:
    return "—" if v is None else f"{round(v)}%"


def format_itqan_report(data: dict) -> str:
    """Plain-text owner report for `!itqan` / Telegram `/itqan`."""
    lvl = data.get("level")
    c = data.get("counts", {})
    scope = lvl if lvl else "all levels"
    lines = [
        f"Itqan — Weekly Assessment report ({scope})",
        (f"Students: {data.get('total_students', 0)} | "
         f"mastered {c.get('mastered', 0)} · not-yet {c.get('not_yet', 0)} · "
         f"flagged {c.get('flagged', 0)} · no-attempt {c.get('none', 0)}"),
        "",
        "Per student:",
    ]
    for s in data.get("per_student", []):
        lt = s.get("latest")
        if lt:
            tag = "FLAGGED" if lt.get("status") == "flagged" else (lt.get("result") or "?")
            detail = (f"W{lt.get('week')} {tag} "
                      f"(m {_pct(lt.get('mastery_pct'))} / c {_pct(lt.get('consistency_pct'))})")
        else:
            detail = "no attempts yet"
        lines.append(f"  [{s['level']}] {s['name']}: {detail} · mastered {s['mastered_count']}")

    if data.get("flagged"):
        lines += ["", "Needs your call (flagged):"]
        for f in data["flagged"]:
            lines.append(
                f"  {f['name']} — {f['level']} W{f['week']} "
                f"(m {_pct(f.get('mastery_pct'))} / c {_pct(f.get('consistency_pct'))}) "
                f"→ !itqan-pass @{f['name']} {f['week']}  |  !itqan-reset @{f['name']} {f['week']}")

    if data.get("most_missed"):
        lines += ["", "Most-missed:"]
        for mm in data["most_missed"]:
            what = mm.get("expected") or f"({mm['skill']})"
            lines.append(f"  {what} [{mm['skill']} W{mm['source_week']}] x{mm['misses']}")

    return "\n".join(lines)



_SKILL_COACHING = {
    "listening": "Listening needs daily reps — play the word, say the meaning out loud, then type it. Try slowing the audio.",
    "pronunciation": "Have them record, then compare to the model and repeat the target sounds a few times.",
    "speaking": "Push for longer answers that actually use this week's words — even 3–4 sentences.",
    "writing": "Ask for 2–3 written sentences a day using the target words.",
    "vocab": "Review this week's flashcards and the SRS 'Review Past Words' — quick and daily.",
}


def format_attempt_review(attempt: dict, items: list, name: str = "",
                          rec_item_nos=None, coaching_note: str = "") -> str:
    """A sectioned owner **coaching brief** for one attempt: the scores + why it
    flagged, what the student did well, exactly what went wrong (grouped by
    skill), the skill to focus on, ready talking points for the student, and
    the recordings + action commands. `coaching_note` = an optional AI paragraph."""
    rec_item_nos = set(rec_item_nos or [])
    who = name or attempt.get("discord_id", "?")
    level = attempt.get("level", "?")
    week = attempt.get("week", "?")
    flags = attempt.get("integrity_flags") or "{}"
    try:
        fl = _json.loads(flags) if isinstance(flags, str) else (flags or {})
    except Exception:
        fl = {}

    def _ok(it):
        return it.get("correct") in (1, True)

    # Group by skill in a stable order.
    order = ["listening", "vocab", "pronunciation", "speaking", "writing"]
    by_skill = {}
    for it in items:
        by_skill.setdefault(it["skill"], []).append(it)
    skills_sorted = [s for s in order if s in by_skill] + \
                    [s for s in by_skill if s not in order]

    strong, weak = [], []
    for s in skills_sorted:
        its = by_skill[s]
        c = sum(1 for i in its if _ok(i))
        (strong if c == len(its) else weak).append((s, c, len(its)))

    reason = {"ai_error": "an AI/recording item couldn't be scored — check it manually",
              "near_miss": "a near-miss just below the pass line"}.get(
        attempt.get("result") != "mastered" and _flag_reason_of(attempt), "")

    L = []
    L.append(f"ITQAN REVIEW — {who} · {level} Week {week}  (attempt #{attempt.get('id')})")
    L.append("=" * 44)
    L.append(f"Result: {str(attempt.get('result')).upper()} · "
             f"Mastery {attempt.get('mastery_pct')}% · Consistency {attempt.get('consistency_pct')}%")
    if attempt.get("status") == "flagged":
        L.append(f"⚑ Flagged for you{(' — ' + reason) if reason else ''}.")
    L.append(f"Finished {attempt.get('finished_at')} · integrity: "
             f"tab-aways {fl.get('tab_aways', 0)}, blur {fl.get('blur_events', 0)}, "
             f"paste {fl.get('paste_blocked', 0)}, timer-expired {bool(attempt.get('time_expired'))}")

    # ✅ Strengths
    if strong:
        L.append("")
        L.append("✅ STRONG: " + ", ".join(f"{s} {c}/{t}" for s, c, t in strong))

    # ⚠️ What went wrong (per weak skill, with the missed items)
    if weak:
        L.append("")
        L.append("⚠️ WHAT WENT WRONG:")
        for s, c, t in weak:
            L.append(f"  • {s} — {c}/{t} correct")
            for it in by_skill[s]:
                if _ok(it):
                    continue
                given = (it.get("answer") or "").strip()
                exp = (it.get("expected") or "").strip()
                lbl = "heard" if s in ("pronunciation", "speaking") else "typed"
                bit = f"      #{it['item_no']}"
                if exp:
                    bit += f" expected \"{exp}\""
                if given:
                    bit += f" · {lbl} \"{given[:60]}\""
                if it["item_no"] in rec_item_nos:
                    bit += " 🎧"
                L.append(bit)

    # 🎯 Needs attention
    if weak:
        focus = ", ".join(s for s, _c, _t in weak)
        L.append("")
        L.append(f"🎯 NEEDS ATTENTION: {focus}")

    # 🗣️ What to say (AI note if present, else heuristic talking points)
    L.append("")
    L.append("🗣️ WHAT TO SAY TO THE STUDENT:")
    if coaching_note:
        for ln in coaching_note.strip().splitlines():
            L.append(f"  {ln.strip()}")
    else:
        passed = attempt.get("result") == "mastered"
        if passed:
            L.append("  Celebrate — they cleared the bar. Nudge them toward distinction next time.")
        else:
            mp = attempt.get("mastery_pct") or 0
            L.append(f"  Start positive: their consistency was {attempt.get('consistency_pct')}% — the effort is there.")
            L.append(f"  They're at {mp}% mastery. Name the ONE skill to fix, then invite a retake:")
        for s, _c, _t in weak[:2]:
            L.append(f"  • {_SKILL_COACHING.get(s, 'Review this skill together.')}")

    # 🎧 Recordings + actions
    L.append("")
    if rec_item_nos:
        L.append(f"🎧 {len(rec_item_nos)} recording(s) attached — listen before deciding.")
    L.append(f"ACTIONS:  !itqan-pass @{who} {week}   |   !itqan-reset @{who} {week}")
    return "\n".join(L)


def _flag_reason_of(attempt: dict) -> str:
    """Best-effort flag reason (attempts table doesn't store it, so infer from
    status; callers that have the verdict can pass it in the note instead)."""
    return "near_miss" if attempt.get("status") == "flagged" else ""


async def build_coaching_note(attempt: dict, items: list) -> str:
    """A short, warm, specific coaching paragraph the teacher can relay to the
    student. Uses the shared LLM; returns '' on any failure (heuristic bullets
    then cover it) so review is never blocked."""
    try:
        from . import ai_engine
    except Exception:
        return ""

    def _ok(it):
        return it.get("correct") in (1, True)
    missed = [it for it in items if not _ok(it)]
    missed_desc = "; ".join(
        f"{it['skill']} (expected '{(it.get('expected') or '').strip()}')"
        for it in missed[:6]) or "nothing major"
    prompt = (
        "You are a kind English teacher for Arabic-speaking beginners. In 2-3 short, "
        "warm, specific sentences, tell me (the teacher) what to say to a student about "
        "their weekly test so I can coach them. Be encouraging, name what to practise, "
        "avoid jargon.\n"
        f"Result: {attempt.get('result')} · mastery {attempt.get('mastery_pct')}% · "
        f"consistency {attempt.get('consistency_pct')}%.\n"
        f"They struggled with: {missed_desc}.\n"
        "Write only the coaching message."
    )
    try:
        out = await ai_engine._call_llm(prompt, temperature=0.6)
        return (out or "").strip()
    except Exception:
        return ""



def format_itqan_due(data: dict) -> str:
    """Plain-text full status report (R17.1) for !itqan-due / /itqan-due,
    with DUE + flagged students surfaced first."""
    lvl = data.get("level")
    c = data.get("counts", {})
    scope = lvl if lvl else "all levels"
    lines = [
        f"Itqan — status ({scope})",
        (f"Students: {data.get('total_students', 0)} | "
         f"⏳ due {c.get('due', 0)} · ⚑ flagged {c.get('flagged', 0)} · "
         f"▶ in-progress {c.get('in_progress', 0)} · ✅ up-to-date {c.get('up_to_date', 0)}"),
    ]
    icon = {"due": "⏳", "flagged": "⚑", "in_progress": "▶", "up_to_date": "✅"}
    for state in ("flagged", "due", "in_progress", "up_to_date"):
        group = [r for r in data.get("rows", []) if r["state"] == state]
        if not group:
            continue
        lines.append("")
        lines.append(f"{icon[state]} {state.replace('_', ' ').upper()}:")
        for r in group:
            lines.append(f"  [{r['level']}] {r['name']} — {r['label']} · mastered {r['mastered_count']}")
    return "\n".join(lines)



# ============================================================
#  MONTHLY REVIEW — generation + scoring (Taqdeem Phase 1)
# ============================================================
#
# Unlike the weekly assessment (65% recent / 35% spiral), the monthly review
# draws EQUALLY from all weeks in the review period, SRS-biased toward items
# the student is most likely to have forgotten. Production (speaking + writing)
# is weighted ≥ 50% of items — because production proves real acquisition, not
# just recognition.


def generate_monthly_blueprint(discord_id: str, level: str,
                               weeks_covered: list[int],
                               seed: str | None = None,
                               total_items: int = 16) -> dict:
    """Build the blueprint for a Monthly Progress Review.

    Draws equally from all `weeks_covered`, SRS-biased toward weak items,
    with ≥ 50% production items (speaking + writing).

    Returns: {level, weeks_covered, seed, time_limit_min, type: 'monthly',
              items: [{item_no, skill, source_week, payload}, ...]}
    """
    cfg = database.get_progression_config()
    time_limit = 20  # fixed for monthly

    if seed is None:
        seed = f"monthly:{discord_id}:{level}:{'-'.join(map(str, weeks_covered))}:{random.randint(1, 1_000_000)}"
    rng = random.Random(seed)

    # Gather vocabulary from all covered weeks
    all_vocab: list[dict] = []
    for w in weeks_covered:
        for v in _week_vocab(level, w):
            item = dict(v)
            item["_week"] = w
            all_vocab.append(item)

    if not all_vocab:
        return {"level": level, "weeks_covered": weeks_covered, "seed": seed,
                "time_limit_min": time_limit, "type": "monthly", "items": []}

    # SRS bias: prioritize weak/due items
    due_words = {d.get("word") for d in database.get_due_reviews(discord_id, limit=200)}
    weak = [v for v in all_vocab if v.get("word") in due_words]
    rest = [v for v in all_vocab if v.get("word") not in due_words]
    rng.shuffle(weak)
    rng.shuffle(rest)
    pool = weak + rest  # weak items first

    # Determine production vs objective split (≥ 50% production)
    production_count = max(total_items // 2, 8)  # at least half
    objective_count = total_items - production_count

    items: list[dict] = []

    # Production items: cycle speaking/writing across different weeks
    production_skills = ["speaking", "writing"]
    for i in range(production_count):
        if i >= len(pool):
            break
        v = pool[i]
        source_week = v.get("_week", weeks_covered[0])
        skill = production_skills[i % 2]
        theme = curriculum.get_theme(source_week, level) or "your practice"
        target_words = [v.get("word", "")]

        if skill == "speaking":
            items.append({
                "skill": "speaking", "source_week": source_week,
                "payload": {
                    "prompt_en": f"Say a sentence using the word '{v.get('word', '')}'.",
                    "prompt_ar": f"قول جملة باستخدام كلمة '{v.get('word', '')}'.",
                    "target_words": target_words, "min_seconds": 10,
                },
            })
        else:
            items.append({
                "skill": "writing", "source_week": source_week,
                "payload": {
                    "prompt_en": f"Write a sentence using '{v.get('word', '')}'.",
                    "prompt_ar": f"اكتب جملة باستخدام '{v.get('word', '')}'.",
                    "target_words": target_words, "min_chars": 20,
                },
            })

    # Objective items: cycle vocab/listening/pronunciation from remaining pool
    obj_pool = pool[production_count:]
    for i in range(objective_count):
        if i >= len(obj_pool):
            break
        v = obj_pool[i]
        skill = _OBJECTIVE_SKILLS[i % len(_OBJECTIVE_SKILLS)]
        items.append(_vocab_item(v, v.get("_week", weeks_covered[0]), skill))

    # Shuffle to mix production and objective (but keep a deterministic order)
    rng.shuffle(items)

    for idx, it in enumerate(items, start=1):
        it["item_no"] = idx

    return {
        "level": level, "weeks_covered": weeks_covered, "seed": seed,
        "time_limit_min": time_limit, "type": "monthly", "items": items,
    }


def score_monthly_attempt(item_scores: list[float],
                          has_ai_error: bool = False,
                          cfg: dict | None = None) -> dict:
    """Score a Monthly Review attempt.

    Single dimension: Retention Score = average of item scores.
    Simpler than the weekly's two-dimension (consistency already proven by
    passing the 4 weeklies that triggered this review).

    Returns {retention_pct, result, status, flag_reason, skill_breakdown}.
    - result: 'passed' | 'not_yet'
    - status: 'scored' | 'flagged'
    """
    cfg = cfg or database.get_progression_config()
    pass_pct = cfg.get("progression_monthly_pass_pct", 65)

    retention_pct = round(sum(item_scores) / len(item_scores), 1) if item_scores else 0.0
    passed = retention_pct >= pass_pct

    flag_reason = ""
    if not passed:
        near_miss = 0 <= (pass_pct - retention_pct) <= _BORDERLINE_MARGIN
        if has_ai_error:
            flag_reason = "ai_error"
        elif near_miss:
            flag_reason = "near_miss"
    status = "flagged" if flag_reason else "scored"

    return {
        "retention_pct": retention_pct,
        "result": "passed" if passed else "not_yet",
        "status": status,
        "flag_reason": flag_reason,
    }


def build_skill_breakdown(items: list[dict], item_scores: list[float]) -> dict:
    """Build a per-skill breakdown from scored items.

    Returns {skill: average_score} for each skill that appeared in the items.
    Used for the diagnostic output (student sees which skills are strong/weak).
    """
    skill_totals: dict[str, list[float]] = {}
    for i, item in enumerate(items):
        skill = item.get("skill", "unknown")
        if i < len(item_scores):
            if skill not in skill_totals:
                skill_totals[skill] = []
            skill_totals[skill].append(item_scores[i])

    return {
        skill: round(sum(scores) / len(scores), 1) if scores else 0.0
        for skill, scores in skill_totals.items()
    }


def build_review_list(items: list[dict], item_scores: list[float],
                      threshold: float = 60.0) -> list[dict]:
    """Build a specific review list of items the student got wrong or weak on.

    Returns [{skill, source_week, word, score}, ...] for items below threshold.
    This is what gives the student actionable "go review week 2 Day 3 vocab".
    """
    review = []
    for i, item in enumerate(items):
        if i >= len(item_scores):
            break
        if item_scores[i] < threshold:
            word = item.get("payload", {}).get("expected", "") or \
                   item.get("payload", {}).get("word", "") or \
                   (item.get("payload", {}).get("target_words", [""])[0] if item.get("payload", {}).get("target_words") else "")
            review.append({
                "skill": item.get("skill", ""),
                "source_week": item.get("source_week", 0),
                "word": word,
                "score": item_scores[i],
            })
    return review
