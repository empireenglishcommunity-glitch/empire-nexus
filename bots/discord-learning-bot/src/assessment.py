"""Itqan (weekly assessment) — generation engine.

Builds a week's test *blueprint* (the list of items) from the curriculum plus
the spiral rule: mostly the current week, a little from earlier weeks chosen
from what the student is most likely to have forgotten (their SRS due queue).

This module is PURE structure — it does not score anything and is not wired to
any user surface yet (later phases). Everything stays inert until the
`itqan_weekly_assessment` flag is turned on.
"""
import json
import random
from typing import Optional

from . import config, curriculum, database

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



# ============================================================
#  MONTHLY REVIEW — attempt lifecycle (Taqdeem Phase 2)
# ============================================================


def get_monthly_state(discord_id: str, level: str) -> dict:
    """State for the calendar/page: not_due | available | in_progress |
    cooldown | passed."""
    if not database.is_feature_enabled("assessment_monthly_review", discord_id):
        return {"state": "disabled"}

    if not database.monthly_review_due(discord_id):
        # Check if already passed the currently-due review
        taken = database.monthly_reviews_taken(discord_id, level)
        passed = database.monthly_reviews_passed(discord_id, level)
        if passed > 0 and passed >= taken:
            return {"state": "passed", "reviews_passed": passed}
        if taken > passed:
            # Has a failed attempt — check cooldown
            cfg = database.get_progression_config()
            cooldown_hours = cfg.get("progression_monthly_retake_cooldown_hours", 72)
            conn = database._connect()
            last = conn.execute(
                "SELECT reviewed_at FROM monthly_reviews WHERE discord_id=? AND level=? "
                "ORDER BY review_number DESC LIMIT 1", (discord_id, level)).fetchone()
            conn.close()
            if last:
                try:
                    fin = _dt.datetime.fromisoformat(last["reviewed_at"])
                    cd_until = fin + _dt.timedelta(hours=cooldown_hours)
                    if _utcnow() < cd_until:
                        return {"state": "cooldown", "cooldown_until": cd_until.isoformat()}
                except (ValueError, TypeError):
                    pass
            return {"state": "available", "review_number": taken + 1}
        return {"state": "not_due"}

    # Due and not yet taken
    taken = database.monthly_reviews_taken(discord_id, level)
    return {"state": "available", "review_number": taken + 1}


def start_monthly_attempt(discord_id: str, level: str) -> dict:
    """Create a new monthly review attempt if allowed.
    Returns {ok, attempt_id, time_limit_min, items:[public]} or {ok:False, error}."""
    if not database.is_feature_enabled("assessment_monthly_review", discord_id):
        return {"ok": False, "error": "disabled"}

    state = get_monthly_state(discord_id, level)
    if state["state"] not in ("available",):
        return {"ok": False, "error": state["state"]}

    # Determine which weeks to cover
    mastered = sorted(database.itqan_mastered_weeks(discord_id, level))
    cfg = database.get_progression_config()
    weeks_per = cfg.get("progression_monthly_weeks_per_review", 4)
    taken = database.monthly_reviews_taken(discord_id, level)
    # Cover the most recent `weeks_per` mastered weeks for this review
    start_idx = taken * weeks_per
    weeks_covered = mastered[start_idx:start_idx + weeks_per]
    if not weeks_covered:
        weeks_covered = mastered[-weeks_per:] if mastered else [1]

    # Generate blueprint
    seed = f"monthly:{discord_id}:{level}:{taken+1}:{_utcnow().timestamp()}"
    bp = generate_monthly_blueprint(discord_id, level, weeks_covered, seed=seed)

    # Create the attempt in assessment_attempts (type='monthly')
    review_number = taken + 1
    conn = database._connect()
    try:
        cur = conn.execute(
            "INSERT INTO assessment_attempts (discord_id, level, week, attempt_no, seed, type) "
            "VALUES (?, ?, ?, ?, ?, 'monthly')",
            (discord_id, level, review_number, 1, seed),
        )
        attempt_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    # Insert items
    database.itqan_insert_items(attempt_id, discord_id, bp["items"])

    return {
        "ok": True,
        "attempt_id": attempt_id,
        "review_number": review_number,
        "weeks_covered": weeks_covered,
        "time_limit_min": bp["time_limit_min"],
        "items": [
            {"item_no": it["item_no"], "skill": it["skill"],
             "source_week": it["source_week"],
             "payload": _public_payload(it["skill"], it.get("payload", {}))}
            for it in bp["items"]
        ],
    }


def finish_monthly_attempt(discord_id: str, attempt_id: int,
                           integrity_flags: dict = None) -> dict:
    """Score and finalize a monthly review attempt.
    Returns {ok, retention_pct, result, skill_breakdown, review_list}."""
    attempt = database.itqan_get_attempt(attempt_id)
    if not attempt or str(attempt["discord_id"]) != str(discord_id):
        return {"ok": False, "error": "not_found"}
    if attempt.get("type") != "monthly":
        return {"ok": False, "error": "wrong_type"}
    if attempt["status"] != "in_progress":
        return {"ok": False, "error": "not_in_progress"}

    # Gather item scores
    items_rows = database.itqan_get_items(attempt_id)
    item_scores = []
    items_data = []
    has_ai_error = False
    for row in sorted(items_rows, key=lambda r: r["item_no"]):
        score = row.get("score")
        if score is None:
            score = 0.0
            has_ai_error = True
        item_scores.append(float(score))
        try:
            payload = _json.loads(row.get("prompt_ref") or "{}")
        except Exception:
            payload = {}
        items_data.append({
            "skill": row.get("skill", ""),
            "source_week": row.get("source_week", 0),
            "payload": payload,
        })

    # Void empty attempts (same as Itqan)
    if not item_scores or all(s == 0 for s in item_scores):
        conn = database._connect()
        conn.execute("DELETE FROM assessment_attempts WHERE id=?", (attempt_id,))
        conn.execute("DELETE FROM assessment_items WHERE attempt_id=?", (attempt_id,))
        conn.commit()
        conn.close()
        return {"ok": True, "voided": True, "reason": "no_answers"}

    # Score
    verdict = score_monthly_attempt(item_scores, has_ai_error=has_ai_error)
    skill_breakdown = build_skill_breakdown(items_data, item_scores)
    review_list = build_review_list(items_data, item_scores)

    # Update the attempt row
    conn = database._connect()
    try:
        conn.execute(
            "UPDATE assessment_attempts SET finished_at=datetime('now'), status=?, "
            "mastery_pct=?, result=? WHERE id=?",
            (verdict["status"], verdict["retention_pct"], verdict["result"], attempt_id),
        )
        if integrity_flags:
            conn.execute("UPDATE assessment_attempts SET integrity_flags=? WHERE id=?",
                         (_json.dumps(integrity_flags), attempt_id))
        conn.commit()
    finally:
        conn.close()

    # Record in monthly_reviews table
    review_number = attempt.get("week", 1)  # we stored review_number in the week column
    level = attempt["level"]
    conn = database._connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO monthly_reviews "
            "(discord_id, level, review_number, attempt_id, passed, retention_score, skill_breakdown) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (discord_id, level, review_number, attempt_id,
             1 if verdict["result"] == "passed" else 0,
             verdict["retention_pct"],
             _json.dumps(skill_breakdown)),
        )
        conn.commit()
    finally:
        conn.close()

    _alog.info(f"monthly: {discord_id} review #{review_number} → "
               f"{verdict['result']} ({verdict['retention_pct']}%)")

    return {
        "ok": True,
        "retention_pct": verdict["retention_pct"],
        "result": verdict["result"],
        "status": verdict["status"],
        "flag_reason": verdict["flag_reason"],
        "skill_breakdown": skill_breakdown,
        "review_list": review_list,
    }



# ============================================================
#  ADVANCEMENT EXAM PART A — generation + scoring (Taqdeem Phase 4)
# ============================================================
#
# Full-level structured skills test: 5 skills × 3-4 items = ~18 items,
# covering ALL weeks of the student's current level. SRS-weighted toward
# weak areas. 20 minutes. The first half of the level-up gate.


# ── Mi'yar Phase 8: tag each Part A item with the CEFR can-do descriptor it
#    evidences, so an exit-exam pass can print a descriptor-referenced checklist
#    on the certificate. Each objective skill maps to a CEFR "mode". This is an
#    approximation — one short objective item is narrower than a full
#    communicative descriptor — and is documented as aligned-not-validated in
#    content/cefr/PHASE8-ASSESSMENT-ALIGNMENT.md. Interaction/mediation are not
#    covered by Part A objective items (they need the Part B integrated task). ──
_CAN_DO_SKILL_MODE = {
    "vocab": "reception",
    "listening": "reception",
    "pronunciation": "production",
    "speaking": "production",
    "writing": "production",
}


def can_do_descriptors(level: str) -> dict:
    """Load {mode: [{code, en, ar}, ...]} for a level from can_do.json. Accepts
    CEFR or legacy keys; returns {} on any failure (never raises)."""
    try:
        data = json.load(open(config.BASE_DIR / "content" / "cefr" / "can_do.json",
                              encoding="utf-8"))
        return data.get(config.cefr_key(level), {}) or {}
    except Exception:
        return {}


def can_do_progress(discord_id: str, level: str) -> dict:
    """Mi'yar Phase 9 — the student's CEFR can-do progress at `level`: how many
    of the level's TAUGHT descriptors (those its weeks target) are evidenced by
    weeks the student has mastered. Returns {level, reached, total, pct,
    evidenced, taught, mastered_weeks, total_weeks}."""
    ck = config.cefr_key(level)
    max_wk = curriculum.max_week_for_level(ck) or 0
    mastered = database.itqan_mastered_weeks(discord_id, ck) or \
        database.itqan_mastered_weeks(discord_id, level)
    taught, evidenced = set(), set()
    for wk in range(1, max_wk + 1):
        codes = curriculum.get_can_do_for_week(wk, ck)
        taught.update(codes)
        if wk in mastered:
            evidenced.update(codes)
    reached = len(evidenced & taught)
    total = len(taught)
    return {
        "level": ck,
        "reached": reached,
        "total": total,
        "pct": round(100 * reached / total) if total else 0,
        "evidenced": sorted(evidenced & taught),
        "taught": sorted(taught),
        "mastered_weeks": len(mastered),
        "total_weeks": max_wk,
    }


def descriptor_portfolio(discord_id: str, level: str) -> dict:
    """Phase 11C — EVIDENCE per CEFR descriptor, not just a checklist.

    `can_do_progress` answers "how many descriptors has this student reached?"
    at week granularity: master the week, get credit for all of its codes. That
    is fine for a progress bar but it cannot answer the question that actually
    matters on a certificate — *what did the student DO that proves this?*

    This derives that proof from `practice_mastery`, which already records every
    completion as (level, week, day, exercise) with dates. Two consequences
    worth stating:

      * no new table and no change to the completion hot path, so nothing about
        recording a completion can break;
      * it works RETROACTIVELY — every student's existing history produces a
        portfolio immediately, with no backfill job.

    Evidence is attributed strictly: `curriculum.descriptor_evidence_map`
    decides which exercises may prove which descriptor, so a dictation cannot
    claim a reading descriptor and a speaking task cannot claim "can write".
    Enabling-skill exercises (accent, shadowing, vocabulary, grammar, review)
    prove no descriptor at all by design.

    Returns {level, descriptors: [{code, en, ar, mode, evidenced, evidence:
    [{exercise, week, day, at}], possible_exercises}], evidenced, total, pct}.
    """
    ck = config.cefr_key(level)
    max_wk = curriculum.max_week_for_level(ck) or 0
    library = curriculum.can_do_descriptor_map(ck)

    # code -> {week: allowed exercises}
    wanted: dict[str, dict] = {}
    for wk in range(1, max_wk + 1):
        for code, exercises in curriculum.descriptor_evidence_map(wk, ck).items():
            wanted.setdefault(code, {})[wk] = set(exercises)

    completions = database.practice_completions(discord_id, ck)

    portfolio = []
    for code in sorted(wanted):
        d = library.get(code) or {}
        ev = []
        for row in completions:
            allowed = wanted[code].get(row["week"])
            if allowed and row["exercise"] in allowed:
                ev.append({
                    "exercise": row["exercise"],
                    "week": row["week"],
                    "day": row["day"],
                    "at": row.get("last_completed_date"),
                })
        ev.sort(key=lambda e: (e["week"], e["day"]))
        possible = sorted({x for exs in wanted[code].values() for x in exs})
        portfolio.append({
            "code": code,
            "en": d.get("en", ""),
            "ar": d.get("ar", ""),
            "mode": d.get("mode", ""),
            "evidenced": bool(ev),
            "evidence": ev,
            "evidence_count": len(ev),
            "possible_exercises": possible,
        })

    evidenced = sum(1 for p in portfolio if p["evidenced"])
    total = len(portfolio)
    return {
        "level": ck,
        "descriptors": portfolio,
        "evidenced": evidenced,
        "total": total,
        "pct": round(100 * evidenced / total) if total else 0,
    }


def tag_part_a_can_do(items: list[dict], level: str) -> list[dict]:
    """Attach a `can_do` = {code, en, mode} to each Part A item by its skill→mode
    map, cycling through the level's descriptors for that mode so items spread
    across codes (deterministic). Items whose mode has no descriptors are left
    untagged. Mutates and returns `items`."""
    cando = can_do_descriptors(level)
    counters: dict[str, int] = {}
    for it in items:
        mode = _CAN_DO_SKILL_MODE.get(it.get("skill"))
        pool = cando.get(mode or "", [])
        if not pool:
            continue
        i = counters.get(mode, 0)
        d = pool[i % len(pool)]
        counters[mode] = i + 1
        it["can_do"] = {"code": d.get("code"), "en": d.get("en"), "mode": mode}
    return items


def generate_advancement_blueprint_a(discord_id: str, level: str,
                                     seed: str | None = None,
                                     total_items: int = 18) -> dict:
    """Build Part A of the Advancement Exam: structured skills across the
    full level. 5 skills each get 3-4 items, SRS-biased toward weak spots.

    Returns: {level, type: 'advancement_a', seed, time_limit_min,
              items: [{item_no, skill, source_week, payload}, ...]}
    """
    cfg = database.get_progression_config()
    time_limit = cfg.get("progression_advancement_time_limit_part_a_min", 20)
    max_week = curriculum.max_week_for_level(level)

    if seed is None:
        seed = f"adv_a:{discord_id}:{level}:{random.randint(1, 1_000_000)}"
    rng = random.Random(seed)

    # Gather vocab from ALL weeks of the level
    all_vocab: list[dict] = []
    for w in range(1, max_week + 1):
        for v in _week_vocab(level, w):
            item = dict(v)
            item["_week"] = w
            all_vocab.append(item)

    if not all_vocab:
        return {"level": level, "type": "advancement_a", "seed": seed,
                "time_limit_min": time_limit, "items": []}

    # SRS bias
    due_words = {d.get("word") for d in database.get_due_reviews(discord_id, limit=300)}
    weak = [v for v in all_vocab if v.get("word") in due_words]
    rest = [v for v in all_vocab if v.get("word") not in due_words]
    rng.shuffle(weak)
    rng.shuffle(rest)
    pool = weak + rest

    # Distribute items across 5 skills (3-4 each, totaling ~18)
    skills = ["vocab", "listening", "pronunciation", "speaking", "writing"]
    items_per_skill = total_items // len(skills)  # 3 each = 15, remainder = 3 more
    remainder = total_items - (items_per_skill * len(skills))

    items: list[dict] = []
    pool_idx = 0

    for skill_idx, skill in enumerate(skills):
        count = items_per_skill + (1 if skill_idx < remainder else 0)
        for _ in range(count):
            if pool_idx >= len(pool):
                break
            v = pool[pool_idx]
            pool_idx += 1
            source_week = v.get("_week", 1)

            if skill in ("vocab", "listening", "pronunciation"):
                items.append(_vocab_item(v, source_week, skill))
            elif skill == "speaking":
                theme = curriculum.get_theme(source_week, level) or "your practice"
                items.append({
                    "skill": "speaking", "source_week": source_week,
                    "payload": {
                        "prompt_en": f"Say a sentence using '{v.get('word', '')}'.",
                        "prompt_ar": f"قول جملة باستخدام '{v.get('word', '')}'.",
                        "target_words": [v.get("word", "")], "min_seconds": 10,
                    },
                })
            else:  # writing
                items.append({
                    "skill": "writing", "source_week": source_week,
                    "payload": {
                        "prompt_en": f"Write a sentence using '{v.get('word', '')}'.",
                        "prompt_ar": f"اكتب جملة باستخدام '{v.get('word', '')}'.",
                        "target_words": [v.get("word", "")], "min_chars": 20,
                    },
                })

    rng.shuffle(items)
    for idx, it in enumerate(items, start=1):
        it["item_no"] = idx
    tag_part_a_can_do(items, level)  # Phase 8: descriptor-reference each item

    return {
        "level": level, "type": "advancement_a", "seed": seed,
        "time_limit_min": time_limit, "items": items,
    }


def score_advancement_part_a(items: list[dict], item_scores: list[float],
                             has_ai_error: bool = False,
                             cfg: dict | None = None) -> dict:
    """Score Part A of the Advancement Exam.

    Returns {overall_pct, per_skill: {skill: pct}, skill_mins_met: bool,
             failed_skills: [skills below 60%], status, flag_reason}.
    """
    cfg = cfg or database.get_progression_config()
    skill_min = cfg.get("progression_advancement_skill_min_pct", 60)

    # Per-skill breakdown
    skill_totals: dict[str, list[float]] = {}
    for i, item in enumerate(items):
        skill = item.get("skill", "unknown")
        if i < len(item_scores):
            if skill not in skill_totals:
                skill_totals[skill] = []
            skill_totals[skill].append(item_scores[i])

    per_skill = {
        skill: round(sum(scores) / len(scores), 1) if scores else 0.0
        for skill, scores in skill_totals.items()
    }

    # Overall Part A score
    overall_pct = round(sum(item_scores) / len(item_scores), 1) if item_scores else 0.0

    # Skill minimum check
    failed_skills = [s for s, pct in per_skill.items() if pct < skill_min]
    skill_mins_met = len(failed_skills) == 0

    # Flagging
    flag_reason = ""
    if has_ai_error:
        flag_reason = "ai_error"

    status = "flagged" if flag_reason else "scored"

    return {
        "overall_pct": overall_pct,
        "per_skill": per_skill,
        "skill_mins_met": skill_mins_met,
        "failed_skills": failed_skills,
        "status": status,
        "flag_reason": flag_reason,
    }


# ============================================================
#  ADVANCEMENT EXAM — attempt lifecycle (Taqdeem Phase 4)
# ============================================================


def get_advancement_state(discord_id: str, level: str) -> dict:
    """State for the calendar: disabled | locked | available | cooldown | passed."""
    if not database.is_feature_enabled("assessment_advancement_exam", discord_id):
        return {"state": "disabled"}

    if not database.advancement_exam_due(discord_id):
        # Check if already passed
        conn = database._connect()
        passed = conn.execute(
            "SELECT * FROM advancement_exams WHERE discord_id=? AND level=? AND passed=1",
            (discord_id, level)).fetchone()
        conn.close()
        if passed:
            return {"state": "passed"}
        return {"state": "locked"}

    # Check cooldown (7 days)
    cfg = database.get_progression_config()
    cooldown_days = cfg.get("progression_advancement_retake_cooldown_days", 7)
    conn = database._connect()
    last = conn.execute(
        "SELECT attempted_at FROM advancement_exams WHERE discord_id=? AND level=? "
        "ORDER BY attempt_num DESC LIMIT 1", (discord_id, level)).fetchone()
    conn.close()
    if last:
        try:
            fin = _dt.datetime.fromisoformat(last["attempted_at"])
            cd_until = fin + _dt.timedelta(days=cooldown_days)
            if _utcnow() < cd_until:
                return {"state": "cooldown", "cooldown_until": cd_until.isoformat()}
        except (ValueError, TypeError):
            pass

    return {"state": "available"}


def start_advancement_attempt(discord_id: str, level: str) -> dict:
    """Create a new advancement exam attempt (Part A).
    Returns {ok, attempt_id, time_limit_min, items:[public]} or {ok:False, error}."""
    if not database.is_feature_enabled("assessment_advancement_exam", discord_id):
        return {"ok": False, "error": "disabled"}

    state = get_advancement_state(discord_id, level)
    if state["state"] == "passed":
        return {"ok": False, "error": "already_passed"}
    if state["state"] == "locked":
        return {"ok": False, "error": "locked"}
    if state["state"] == "cooldown":
        return {"ok": False, "error": "cooldown", "cooldown_until": state.get("cooldown_until")}
    if state["state"] != "available":
        return {"ok": False, "error": state["state"]}

    # Generate Part A blueprint
    seed = f"adv_a:{discord_id}:{level}:{_utcnow().timestamp()}"
    bp = generate_advancement_blueprint_a(discord_id, level, seed=seed)

    # Create attempt
    attempt_num = database.advancement_attempts_count(discord_id, level) + 1
    conn = database._connect()
    try:
        cur = conn.execute(
            "INSERT INTO assessment_attempts (discord_id, level, week, attempt_no, seed, type) "
            "VALUES (?, ?, ?, ?, ?, 'advancement')",
            (discord_id, level, 0, attempt_num, seed),
        )
        attempt_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    # Insert items
    database.itqan_insert_items(attempt_id, discord_id, bp["items"])

    # Record in advancement_exams
    conn = database._connect()
    try:
        conn.execute(
            "INSERT INTO advancement_exams (discord_id, level, attempt_num, attempt_id) "
            "VALUES (?, ?, ?, ?)",
            (discord_id, level, attempt_num, attempt_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "attempt_id": attempt_id,
        "attempt_num": attempt_num,
        "time_limit_min": bp["time_limit_min"],
        "items": [
            {"item_no": it["item_no"], "skill": it["skill"],
             "source_week": it["source_week"],
             "payload": _public_payload(it["skill"], it.get("payload", {}))}
            for it in bp["items"]
        ],
    }


def finish_advancement_part_a(discord_id: str, attempt_id: int,
                              integrity_flags: dict = None) -> dict:
    """Score Part A of the advancement exam. Does NOT determine final pass/fail
    (that comes after Part B in Phase 5). Returns Part A scores for the page
    to display before Part B begins."""
    attempt = database.itqan_get_attempt(attempt_id)
    if not attempt or str(attempt["discord_id"]) != str(discord_id):
        return {"ok": False, "error": "not_found"}
    if attempt.get("type") != "advancement":
        return {"ok": False, "error": "wrong_type"}
    if attempt["status"] != "in_progress":
        return {"ok": False, "error": "not_in_progress"}

    # Gather item scores
    items_rows = database.itqan_get_items(attempt_id)
    item_scores = []
    items_data = []
    has_ai_error = False
    for row in sorted(items_rows, key=lambda r: r["item_no"]):
        score = row.get("score")
        if score is None:
            score = 0.0
            has_ai_error = True
        item_scores.append(float(score))
        try:
            payload = _json.loads(row.get("prompt_ref") or "{}")
        except Exception:
            payload = {}
        items_data.append({
            "skill": row.get("skill", ""),
            "source_week": row.get("source_week", 0),
            "payload": payload,
        })

    # Void empty attempts
    if not item_scores or all(s == 0 for s in item_scores):
        conn = database._connect()
        conn.execute("DELETE FROM assessment_attempts WHERE id=?", (attempt_id,))
        conn.execute("DELETE FROM assessment_items WHERE attempt_id=?", (attempt_id,))
        conn.execute("DELETE FROM advancement_exams WHERE attempt_id=?", (attempt_id,))
        conn.commit()
        conn.close()
        return {"ok": True, "voided": True, "reason": "no_answers"}

    # Score Part A
    verdict = score_advancement_part_a(items_data, item_scores, has_ai_error=has_ai_error)

    # Update attempt
    conn = database._connect()
    try:
        conn.execute(
            "UPDATE assessment_attempts SET finished_at=datetime('now'), status=?, "
            "mastery_pct=?, result='part_a_done' WHERE id=?",
            (verdict["status"], verdict["overall_pct"], attempt_id),
        )
        if integrity_flags:
            conn.execute("UPDATE assessment_attempts SET integrity_flags=? WHERE id=?",
                         (_json.dumps(integrity_flags), attempt_id))
        # Store Part A score in advancement_exams
        conn.execute(
            "UPDATE advancement_exams SET part_a_score=?, skill_mins=? "
            "WHERE attempt_id=?",
            (verdict["overall_pct"], _json.dumps(verdict["per_skill"]), attempt_id),
        )
        conn.commit()
    finally:
        conn.close()

    _alog.info(f"advancement: {discord_id} Part A → {verdict['overall_pct']}% "
               f"(skills_met={verdict['skill_mins_met']})")

    return {
        "ok": True,
        "part_a_score": verdict["overall_pct"],
        "per_skill": verdict["per_skill"],
        "skill_mins_met": verdict["skill_mins_met"],
        "failed_skills": verdict["failed_skills"],
        "status": verdict["status"],
        "flag_reason": verdict["flag_reason"],
    }



# ============================================================
#  ADVANCEMENT EXAM PART B — integrated production task (Phase 5)
# ============================================================
#
# A real-world production scenario: L0 = 60-second self-introduction.
# Scored by AI on 4 dimensions (each 0-25 = 100 total):
#   fluency, accuracy, vocabulary range, pronunciation clarity.
# Combined with Part A for the final pass/fail determination.

# Per-level integrated production task prompts (Phase 8: CEFR exit exam).
# Keyed by CEFR level A1-C2; each task is authored from that level's PRODUCTION
# can-do descriptors so passing Part B demonstrably evidences the level. Legacy
# L0-L3 callers are normalised to CEFR keys by get_part_b_prompt(), so nothing
# that still passes an L-key breaks. Every prompt carries the descriptor codes
# it targets, which the certificate's can-do checklist reads back.
_PART_B_PROMPTS = {
    "A1": {  # A1.P: personal details, immediate needs, very simple connected phrases
        "prompt_en": (
            "Record yourself for 60 seconds. Introduce yourself in English: "
            "your name, where you're from, what you do, and why you're learning English."
        ),
        "prompt_ar": (
            "سجّل نفسك ٦٠ ثانية. عرّف نفسك بالإنجليزي: "
            "اسمك، من فين، شغلك إيه، وليه بتتعلم إنجليزي."
        ),
        "duration_sec": 60, "prep_time_sec": 60,
        "descriptors": ["A1.P.1", "A1.P.2"],
    },
    "A2": {  # A2.P: describe routines, past activities, plans in simple connected text
        "prompt_en": (
            "Record yourself for 60 seconds. Describe your typical day from morning "
            "to night, then say one thing you did last weekend and one thing you plan "
            "to do next week."
        ),
        "prompt_ar": (
            "سجّل نفسك ٦٠ ثانية. وصّف يومك العادي من الصبح للّيل، وبعدين قول حاجة "
            "عملتها الويكند اللي فات وحاجة ناوي تعملها الأسبوع الجاي."
        ),
        "duration_sec": 60, "prep_time_sec": 60,
        "descriptors": ["A2.P.1", "A2.P.2"],
    },
    "B1": {  # B1.P: connected narrative + opinion with reasons on a familiar topic
        "prompt_en": (
            "Record yourself for 90 seconds. Tell the story of a time you learned "
            "something the hard way — what happened, how you felt, and what you would "
            "do differently. Give reasons for your view."
        ),
        "prompt_ar": (
            "سجّل نفسك ٩٠ ثانية. احكِ عن مرة اتعلمت فيها حاجة بصعوبة — إيه اللي حصل، "
            "وحسّيت بإيه، وإيه اللي كنت هتعمله بشكل مختلف. واذكر أسباب رأيك."
        ),
        "duration_sec": 90, "prep_time_sec": 90,
        "descriptors": ["B1.P.1", "B1.P.3", "B1.I.1"],
    },
    "B2": {  # B2.P: argue a position on a topical issue, weigh advantages/disadvantages
        "prompt_en": (
            "Record yourself for 2 minutes. Argue for or against this statement: "
            "'Remote work is better than working in an office.' Give a clear position, "
            "at least two supporting reasons, and acknowledge one point on the other side."
        ),
        "prompt_ar": (
            "سجّل نفسك دقيقتين. جادل مع أو ضد العبارة دي: «العمل عن بُعد أفضل من العمل "
            "في المكتب». حدّد موقفك بوضوح، اذكر سببين على الأقل، واعترف بنقطة واحدة للطرف الآخر."
        ),
        "duration_sec": 120, "prep_time_sec": 120,
        "descriptors": ["B2.P.2", "B2.P.3", "B2.I.2"],
    },
    "C1": {  # C1.P: structured extended presentation on a complex topic, nuanced view
        "prompt_en": (
            "Record yourself for 2-3 minutes. Give a structured mini-presentation on a "
            "complex issue you know well: outline the problem, present two perspectives, "
            "and end with your own reasoned conclusion. Use clear signposting."
        ),
        "prompt_ar": (
            "سجّل نفسك من دقيقتين لتلاتة. قدّم عرضًا منظّمًا عن قضية معقّدة تعرفها كويس: "
            "اعرض المشكلة، قدّم وجهتَي نظر، واختم باستنتاجك المدعّم. استخدم روابط واضحة."
        ),
        "duration_sec": 180, "prep_time_sec": 180,
        "descriptors": ["C1.P.2", "C1.P.4", "C1.I.2"],
    },
    "C2": {  # C2.P: argue a nuanced position, concede then rebut, precise and idiomatic
        "prompt_en": (
            "Record yourself for 3 minutes. Take a nuanced position on a debatable "
            "claim of your choice. State the strongest version of the opposing view, "
            "concede what is fair, then rebut it — precisely, coherently, and in your "
            "own natural register."
        ),
        "prompt_ar": (
            "سجّل نفسك تلات دقايق. اتبنَّ موقفًا دقيقًا من ادعاء قابل للجدل من اختيارك. "
            "اعرض أقوى صورة لوجهة النظر المقابلة، وسلّم بما هو منصف، ثم فنّدها — بدقّة "
            "وتماسك وبأسلوبك الطبيعي."
        ),
        "duration_sec": 180, "prep_time_sec": 180,
        "descriptors": ["C2.P.2", "C2.P.5", "C2.I.3"],
    },
}


def get_part_b_prompt(level: str) -> dict:
    """Part B integrated task prompt for a level.

    Accepts a CEFR key (A1-C2) or a legacy key (L0-L3); legacy is normalised via
    config.cefr_key so old callers keep working. Falls back to A1 for anything
    unrecognised (never raises)."""
    key = config.cefr_key(level)
    return _PART_B_PROMPTS.get(key) or _PART_B_PROMPTS.get(level) or _PART_B_PROMPTS["A1"]


def score_part_b(transcript: str, level: str, cfg: dict | None = None) -> dict:
    """Score Part B from a Whisper transcript using rule-based heuristics.

    Scores 4 dimensions (each 0-25, total 100):
    - Fluency: length + smoothness (word count, sentence structure)
    - Accuracy: basic grammar patterns (for the level)
    - Vocabulary range: unique words / total words ratio + absolute count
    - Pronunciation clarity: word confidence (Whisper transcribes clearly
      spoken words more accurately — garbled speech = shorter/fragmented)

    Returns {total, fluency, accuracy, vocab_range, pronunciation, feedback}.
    """
    words = transcript.strip().split() if transcript else []
    word_count = len(words)

    if word_count < 5:
        return {
            "total": 0, "fluency": 0, "accuracy": 0,
            "vocab_range": 0, "pronunciation": 0,
            "feedback": "No speech detected — please try recording again.",
            "feedback_ar": "مفيش كلام اتسمع — جرّب تسجّل تاني.",
        }

    # --- Fluency (0-25): based on word count for a 60s recording ---
    # L0 beginner: 30+ words in 60s = good pace; 60+ = excellent
    if word_count >= 60:
        fluency = 25
    elif word_count >= 40:
        fluency = 20
    elif word_count >= 25:
        fluency = 15
    elif word_count >= 15:
        fluency = 10
    else:
        fluency = 5

    # --- Accuracy (0-25): sentence-like structure ---
    # Simple heuristic: count periods/commas/question marks as sentence breaks
    import re
    sentences = re.split(r'[.!?]+', transcript)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 3]
    # More complete sentences = better grammar structure
    if len(sentences) >= 5:
        accuracy = 25
    elif len(sentences) >= 3:
        accuracy = 20
    elif len(sentences) >= 2:
        accuracy = 15
    elif len(sentences) >= 1:
        accuracy = 10
    else:
        accuracy = 5

    # --- Vocabulary range (0-25): unique words / total ---
    unique = set(w.lower().strip(".,!?;:\"'") for w in words)
    ratio = len(unique) / max(1, word_count)
    if ratio >= 0.7 and len(unique) >= 25:
        vocab_range = 25
    elif ratio >= 0.6 and len(unique) >= 18:
        vocab_range = 20
    elif ratio >= 0.5 and len(unique) >= 12:
        vocab_range = 15
    elif len(unique) >= 8:
        vocab_range = 10
    else:
        vocab_range = 5

    # --- Pronunciation clarity (0-25): proxy via word length consistency ---
    # Well-pronounced speech → Whisper transcribes clearly → real English words
    # Garbled → short fragments, non-words
    avg_word_len = sum(len(w) for w in words) / max(1, word_count)
    if avg_word_len >= 4.5 and word_count >= 20:
        pronunciation = 25
    elif avg_word_len >= 4.0 and word_count >= 15:
        pronunciation = 20
    elif avg_word_len >= 3.5:
        pronunciation = 15
    elif avg_word_len >= 3.0:
        pronunciation = 10
    else:
        pronunciation = 5

    total = fluency + accuracy + vocab_range + pronunciation

    # Feedback
    if total >= 80:
        feedback = "Excellent production! Clear, fluent, and well-structured."
        feedback_ar = "إنتاج ممتاز! واضح وسلس ومنظّم."
    elif total >= 60:
        feedback = "Good effort — solid foundation. Keep practising fluency."
        feedback_ar = "مجهود كويس — أساس متين. كمّل تمرين الطلاقة."
    elif total >= 40:
        feedback = "A real attempt — focus on speaking more and using varied words."
        feedback_ar = "محاولة حقيقية — ركّز على إنك تتكلم أكتر وتستخدم كلمات متنوّعة."
    else:
        feedback = "Keep trying — speak more, use the words you've learned."
        feedback_ar = "كمّل محاولة — اتكلم أكتر واستخدم الكلمات اللي اتعلمتها."

    return {
        "total": total,
        "fluency": fluency,
        "accuracy": accuracy,
        "vocab_range": vocab_range,
        "pronunciation": pronunciation,
        "feedback": feedback,
        "feedback_ar": feedback_ar,
    }


# ============================================================
#  PHASE 8 — CEFR exit exam: AI descriptor-rater + cut scores
# ============================================================
#
# Cut scores are EXPERT-ASSIGNED, not empirically calibrated (17 students is
# far too few — see content/cefr/PHASE8-ASSESSMENT-ALIGNMENT.md §3/§5). They are
# defined in ONE place here so they are never silently changed elsewhere.
# Production weight/threshold rise with level (requirement R7.2).
EXIT_EXAM_CUT_SCORES = {
    "A1": {"part_a_pct": 65, "part_b_min": 60},
    "A2": {"part_a_pct": 65, "part_b_min": 60},
    "B1": {"part_a_pct": 65, "part_b_min": 65},
    "B2": {"part_a_pct": 65, "part_b_min": 65},
    "C1": {"part_a_pct": 65, "part_b_min": 70},
    "C2": {"part_a_pct": 65, "part_b_min": 70},
}
EXIT_EXAM_DISTINCTION_PART_B = 90   # Part B >= 90 -> "with distinction"
EXIT_EXAM_REVIEW_BAND = 7           # within +/-7 of a cut -> human review
EXIT_EXAM_MIN_AI_CONFIDENCE = 0.55  # below this -> human review


def exit_exam_cut(level: str) -> dict:
    """Expert-assigned pass thresholds for a level (CEFR or legacy key)."""
    return EXIT_EXAM_CUT_SCORES.get(config.cefr_key(level), EXIT_EXAM_CUT_SCORES["A1"])


def _part_b_rater_prompt(transcript: str, level: str, prompt: dict) -> str:
    """Build the descriptor-anchored rubric prompt for the AI rater."""
    ck = config.cefr_key(level)
    descriptors = prompt.get("descriptors", [])
    desc_lines = []
    try:
        cando = json.load(open(config.BASE_DIR / "content" / "cefr" / "can_do.json",
                                encoding="utf-8")).get(ck, {})
        by_code = {}
        for mode in ("reception", "production", "interaction", "mediation"):
            for d in cando.get(mode, []):
                by_code[d.get("code")] = d.get("en", "")
        for code in descriptors:
            if code in by_code:
                desc_lines.append(f"  - {code}: {by_code[code]}")
    except Exception:
        pass
    desc_block = "\n".join(desc_lines) or "  (level production descriptors)"
    return (
        f"You are a CEFR examiner rating a spoken response at level {ck}.\n"
        f"The task targeted these can-do descriptors:\n{desc_block}\n\n"
        f"Candidate transcript (from speech-to-text, may contain minor ASR errors):\n"
        f'"""{transcript.strip()[:2000]}"""\n\n'
        f"Rate the response on four axes, each 0-25 (total 0-100), judged against "
        f"what a solid {ck} performance looks like — criterion-referenced, not "
        f"compared to other students:\n"
        f"  fluency, accuracy, vocab_range, pronunciation.\n"
        f"Also decide which of the listed descriptor codes were actually EVIDENCED, "
        f"and give your confidence 0.0-1.0 that your rating is reliable (lower it if "
        f"the transcript is too short, garbled, or off-task).\n"
        f"Respond with STRICT JSON only, no prose:\n"
        f'{{"fluency":int,"accuracy":int,"vocab_range":int,"pronunciation":int,'
        f'"evidenced_descriptors":["code",...],"confidence":float,'
        f'"feedback":"one short sentence","feedback_ar":"جملة قصيرة"}}'
    )


async def score_part_b_ai(transcript: str, level: str, prompt: dict | None = None):
    """AI descriptor-rater for Part B. Returns a score dict with rater='ai' and a
    confidence, or None on any failure (caller falls back to the rule-based
    scorer). Never raises."""
    if not transcript or len(transcript.split()) < 5:
        return None
    prompt = prompt or get_part_b_prompt(level)
    try:
        from . import ai_engine
        raw = await ai_engine._call_llm(_part_b_rater_prompt(transcript, level, prompt),
                                        temperature=0.2)
        if not raw:
            return None
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group(0) if m else raw)
        axes = {k: max(0, min(25, int(round(float(data.get(k, 0))))))
                for k in ("fluency", "accuracy", "vocab_range", "pronunciation")}
        total = sum(axes.values())
        conf = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
        return {
            "total": total, **axes,
            "evidenced_descriptors": [c for c in data.get("evidenced_descriptors", [])
                                      if isinstance(c, str)],
            "confidence": round(conf, 2),
            "rater": "ai",
            "feedback": str(data.get("feedback", ""))[:300],
            "feedback_ar": str(data.get("feedback_ar", ""))[:300],
        }
    except Exception:
        return None


async def rate_part_b(transcript: str, level: str, prompt: dict | None = None) -> dict:
    """Orchestrator: AI descriptor-rater first, rule-based scorer as the fallback
    so an LLM/network outage never blocks a student. Always returns a score dict
    tagged with the rater used and a confidence."""
    ai = await score_part_b_ai(transcript, level, prompt)
    if ai is not None:
        return ai
    fallback = score_part_b(transcript, level)
    fallback.setdefault("evidenced_descriptors", [])
    fallback["rater"] = "rule"
    fallback["confidence"] = 0.5  # neutral -> boundary logic will tend to review
    return fallback


def exit_exam_decision(level: str, part_a_pct: float, part_b: dict) -> dict:
    """Decide pass / fail / review for a CEFR exit exam.

    A clear pass or fail auto-resolves; anything within EXIT_EXAM_REVIEW_BAND of
    a cut, or rated with low AI confidence, routes to human review so automated
    judgement is never final on the least-reliable cases. Returns
    {decision: 'pass'|'fail'|'review', distinction: bool, reasons: [...],
     part_a_pct, part_b_total, confidence}."""
    cut = exit_exam_cut(level)
    b_total = int(part_b.get("total", 0))
    conf = float(part_b.get("confidence", 0.5))
    a_cut, b_cut = cut["part_a_pct"], cut["part_b_min"]

    a_margin = part_a_pct - a_cut
    b_margin = b_total - b_cut
    reasons = []

    near_boundary = abs(a_margin) <= EXIT_EXAM_REVIEW_BAND or abs(b_margin) <= EXIT_EXAM_REVIEW_BAND
    low_confidence = conf < EXIT_EXAM_MIN_AI_CONFIDENCE

    if low_confidence:
        reasons.append(f"AI rater confidence {conf:.2f} < {EXIT_EXAM_MIN_AI_CONFIDENCE}")
    if near_boundary:
        reasons.append(f"within ±{EXIT_EXAM_REVIEW_BAND} of a cut "
                       f"(A {part_a_pct:.0f} vs {a_cut}, B {b_total} vs {b_cut})")

    clear_pass = a_margin > EXIT_EXAM_REVIEW_BAND and b_margin > EXIT_EXAM_REVIEW_BAND
    clear_fail = a_margin < -EXIT_EXAM_REVIEW_BAND or b_margin < -EXIT_EXAM_REVIEW_BAND

    if low_confidence or near_boundary or not (clear_pass or clear_fail):
        decision = "review"
    elif clear_pass:
        decision = "pass"
    else:
        decision = "fail"

    return {
        "decision": decision,
        "distinction": decision == "pass" and b_total >= EXIT_EXAM_DISTINCTION_PART_B,
        "reasons": reasons,
        "part_a_pct": round(part_a_pct, 1),
        "part_b_total": b_total,
        "confidence": round(conf, 2),
        "cut": cut,
    }


async def exit_exam_finalize(discord_id: str, level: str, part_a_pct: float,
                             part_b_transcript: str, *,
                             attempt_num: int | None = None,
                             part_b_prompt: dict | None = None) -> dict:
    """Score + decide a CEFR exit exam end-to-end (Phase 8).

    Flag-gated (`assessment_advancement_exam`, fails closed). Rates Part B with
    the AI descriptor-rater (rule-based fallback so an LLM outage never blocks a
    student), applies `exit_exam_decision`, and on a `review` verdict enqueues a
    human-review row. Returns the decision dict augmented with the full Part B
    score (`part_b`) and any `review_id`. Never raises.

    The caller passes the returned decision to
    advancement_outcomes.deliver_exit_exam_outcome to fire the consequence."""
    if not database.is_feature_enabled("assessment_advancement_exam", discord_id):
        return {"decision": "disabled"}
    part_b = await rate_part_b(part_b_transcript, level, part_b_prompt)
    decision = exit_exam_decision(level, part_a_pct, part_b)
    decision["part_b"] = part_b
    decision["review_id"] = None
    if decision["decision"] == "review":
        decision["review_id"] = database.exit_exam_enqueue_review(
            discord_id, level, attempt_num,
            decision["part_a_pct"], decision["part_b_total"],
            decision["confidence"], part_b.get("rater", "?"),
            decision["reasons"], part_b.get("evidenced_descriptors", []),
        )
    return decision


def compute_advancement_final(part_a_score: float, part_b_score: float,
                              per_skill: dict, cfg: dict | None = None) -> dict:
    """Compute the final advancement pass/fail from Part A + Part B.

    Returns {overall_pct, passed, part_a_weighted, part_b_weighted,
             failed_skills, part_b_met, reason_if_failed}.
    """
    cfg = cfg or database.get_progression_config()
    a_weight = cfg.get("progression_advancement_part_a_weight", 0.6)
    b_weight = cfg.get("progression_advancement_part_b_weight", 0.4)
    overall_pass = cfg.get("progression_advancement_pass_pct", 75)
    skill_min = cfg.get("progression_advancement_skill_min_pct", 60)
    part_b_min = cfg.get("progression_advancement_part_b_min_pct", 50)

    # Part B as percentage (out of 100)
    part_b_pct = part_b_score  # already 0-100

    # Weighted overall
    overall_pct = round(part_a_score * a_weight + part_b_pct * b_weight, 1)

    # Checks
    failed_skills = [s for s, pct in per_skill.items() if pct < skill_min]
    skill_mins_met = len(failed_skills) == 0
    part_b_met = part_b_pct >= part_b_min
    overall_met = overall_pct >= overall_pass

    passed = overall_met and skill_mins_met and part_b_met

    reason = ""
    if not passed:
        if not overall_met:
            reason = f"overall {overall_pct}% < {overall_pass}%"
        elif not skill_mins_met:
            reason = f"skills below {skill_min}%: {', '.join(failed_skills)}"
        elif not part_b_met:
            reason = f"Part B {part_b_pct}% < {part_b_min}%"

    return {
        "overall_pct": overall_pct,
        "passed": passed,
        "part_a_weighted": round(part_a_score * a_weight, 1),
        "part_b_weighted": round(part_b_pct * b_weight, 1),
        "part_b_pct": part_b_pct,
        "failed_skills": failed_skills,
        "skill_mins_met": skill_mins_met,
        "part_b_met": part_b_met,
        "reason_if_failed": reason,
    }


def finish_advancement_final(discord_id: str, attempt_id: int,
                             part_b_transcript: str) -> dict:
    """Finalize the full advancement exam (Part A already scored + Part B recording).
    Computes final verdict. Returns the complete result."""
    # Get Part A data
    conn = database._connect()
    adv = conn.execute(
        "SELECT * FROM advancement_exams WHERE attempt_id=?", (attempt_id,)).fetchone()
    conn.close()

    if not adv:
        return {"ok": False, "error": "not_found"}
    if adv["passed"]:
        return {"ok": False, "error": "already_passed"}

    level = adv["level"]
    part_a_score = adv["part_a_score"] or 0.0

    # Score Part B
    part_b_result = score_part_b(part_b_transcript, level)
    part_b_score = part_b_result["total"]  # 0-100

    # Load per-skill from Part A
    try:
        per_skill = _json.loads(adv["skill_mins"] or "{}")
    except Exception:
        per_skill = {}

    # Compute final verdict
    final = compute_advancement_final(part_a_score, part_b_score, per_skill)

    # Update advancement_exams
    conn = database._connect()
    try:
        conn.execute(
            "UPDATE advancement_exams SET part_b_score=?, overall_score=?, "
            "passed=?, promoted=0 WHERE attempt_id=?",
            (part_b_score, final["overall_pct"], 1 if final["passed"] else 0, attempt_id),
        )
        conn.commit()
    finally:
        conn.close()

    _alog.info(f"advancement: {discord_id} FINAL → overall={final['overall_pct']}% "
               f"passed={final['passed']} (A={part_a_score}, B={part_b_score})")

    return {
        "ok": True,
        "passed": final["passed"],
        "overall_pct": final["overall_pct"],
        "part_a_score": part_a_score,
        "part_b_score": part_b_score,
        "part_b_detail": part_b_result,
        "per_skill": per_skill,
        "failed_skills": final["failed_skills"],
        "reason_if_failed": final["reason_if_failed"],
    }


async def finish_advancement_exit(discord_id: str, attempt_id: int,
                                  part_b_transcript: str) -> dict:
    """Mi'yar Phase 8 — finalize the advancement exam as a CEFR *exit exam*.

    Same attempt bookkeeping as finish_advancement_final, but the verdict comes
    from criterion cut scores + the AI descriptor-rater (rule-based fallback) +
    boundary human review — not the legacy weighted 75% rule. The verdict is one
    of pass / fail / review; a `review` verdict enqueues a human-review row and
    leaves the student un-promoted until the owner resolves it (!exam-pass/-fail).

    Does NOT re-check the feature flag: an exam already in progress always
    finishes (the flag gates *starting*, upstream in start_advancement_attempt).
    Async — calls the AI rater; never surfaces an LLM outage to the student
    (rate_part_b always yields a score via its rule-based fallback)."""
    conn = database._connect()
    adv = conn.execute(
        "SELECT * FROM advancement_exams WHERE attempt_id=?", (attempt_id,)).fetchone()
    conn.close()
    if not adv:
        return {"ok": False, "error": "not_found"}
    if adv["passed"]:
        return {"ok": False, "error": "already_passed"}

    level = adv["level"]
    part_a_pct = adv["part_a_score"] or 0.0
    try:
        per_skill = _json.loads(adv["skill_mins"] or "{}")
    except Exception:
        per_skill = {}

    part_b = await rate_part_b(part_b_transcript, level)
    decision = exit_exam_decision(level, part_a_pct, part_b)
    verdict = decision["decision"]
    passed = verdict == "pass"
    part_b_total = decision["part_b_total"]
    overall = round((part_a_pct + part_b_total) / 2, 1)

    conn = database._connect()
    try:
        conn.execute(
            "UPDATE advancement_exams SET part_b_score=?, overall_score=?, "
            "passed=?, promoted=0 WHERE attempt_id=?",
            (part_b_total, overall, 1 if passed else 0, attempt_id))
        conn.commit()
    finally:
        conn.close()

    review_id = None
    if verdict == "review":
        review_id = database.exit_exam_enqueue_review(
            discord_id, level, attempt_id, decision["part_a_pct"], part_b_total,
            decision["confidence"], part_b.get("rater", "?"),
            decision["reasons"], part_b.get("evidenced_descriptors", []))

    _alog.info(f"exit-exam: {discord_id} {level} FINAL -> {verdict} "
               f"(A={part_a_pct}%, B={part_b_total}/100, conf={decision['confidence']})")

    return {
        "ok": True,
        "decision": verdict,
        "passed": passed,
        "distinction": decision["distinction"],
        "level": level,
        "overall_pct": overall,
        "part_a_score": part_a_pct,
        "part_a_pct": decision["part_a_pct"],
        "part_b_score": part_b_total,
        "part_b_total": part_b_total,
        "part_b_detail": part_b,
        "per_skill": per_skill,
        "confidence": decision["confidence"],
        "reasons": decision["reasons"],
        "cut": decision["cut"],
        "review_id": review_id,
    }
