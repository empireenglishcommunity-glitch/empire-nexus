"""Itqan Phase 3 — attempt lifecycle + server-side integrity rules.

Exercises the real DB (temp per test) through the assessment lifecycle
functions (start / submit / finish) plus the unlock gate, cooldown,
single-attempt guard, mastery persistence, and graceful transcription
failure. Curriculum vocab is faked for determinism; the calendar
(unlock + consistency source of truth) is faked per test.
"""
import json

import pytest

from src import assessment, curriculum, database


# ---- fixtures -------------------------------------------------------------

@pytest.fixture(autouse=True)
def fake_curriculum(monkeypatch):
    def _vocab(week, level="L0"):
        return [
            {"word": f"w{week}_{i}", "arabic": f"ع{week}_{i}",
             "pronunciation": f"p{week}_{i}", "pos": "noun"}
            for i in range(20)
        ]
    monkeypatch.setattr(curriculum, "get_vocabulary_for_week", _vocab)
    monkeypatch.setattr(curriculum, "get_theme", lambda week, level="L0": f"theme{week}")
    monkeypatch.setattr(database, "get_due_reviews", lambda did, limit=100: [])


@pytest.fixture
def student():
    """A registered member with the Itqan flag ON."""
    database.register_member("s1", "Student", "L0")
    database.set_feature_flag("itqan_weekly_assessment", True)
    return "s1"


def _full_week(week: int) -> dict:
    """A calendar where every day of `week` is fully done (all core
    exercises) → week is unlocked and consistency is 100%."""
    core = database.PRACTICE_EXERCISES
    return {(week, d): {"day_tier": 1, "done": True,
                        "exercises": {c: 1 for c in core}} for d in range(1, 8)}


def _unlock(monkeypatch, week: int, calendar: dict = None):
    cal = calendar if calendar is not None else _full_week(week)
    monkeypatch.setattr(database, "get_calendar_mastery", lambda did, lvl: cal)


async def _fake_transcribe_echo(audio_bytes, filename="recording.webm"):
    """Decode the bytes the test sent as the 'transcript' — lets each test
    control exactly what Whisper 'heard' per item."""
    return audio_bytes.decode("utf-8")


async def _answer_all_correct(discord_id, attempt_id):
    """Submit a correct answer for every item in the attempt."""
    for it in database.itqan_get_items(attempt_id):
        payload = json.loads(it["prompt_ref"] or "{}")
        skill = it["skill"]
        no = it["item_no"]
        if skill in ("vocab", "listening"):
            await assessment.submit_item(discord_id, attempt_id, no,
                                         answer=payload["expected"])
        elif skill == "pronunciation":
            await assessment.submit_item(discord_id, attempt_id, no,
                                         audio_bytes=payload["expected"].encode())
        elif skill == "speaking":
            words = payload.get("target_words", [])
            transcript = " ".join(words) + " i talk about my day every morning"
            await assessment.submit_item(discord_id, attempt_id, no,
                                         audio_bytes=transcript.encode())
        else:  # writing
            words = payload.get("target_words", [])
            text = " ".join(words) + " i write about this every evening with my family."
            await assessment.submit_item(discord_id, attempt_id, no, answer=text)


# ---- unlock gate ----------------------------------------------------------

def test_locked_until_week_complete(student, monkeypatch):
    # No calendar progress → all 7 days remain.
    _unlock(monkeypatch, 2, calendar={})
    unlocked, remaining = assessment.week_unlocked(student, "L0", 2)
    assert unlocked is False
    assert remaining == [1, 2, 3, 4, 5, 6, 7]
    state = assessment.get_week_state(student, "L0", 2)
    assert state["state"] == "locked"
    assert state["days_remaining"] == [1, 2, 3, 4, 5, 6, 7]


def test_partial_week_still_locked(student, monkeypatch):
    cal = _full_week(2)
    del cal[(2, 5)]  # day 5 not done
    _unlock(monkeypatch, 2, calendar=cal)
    unlocked, remaining = assessment.week_unlocked(student, "L0", 2)
    assert unlocked is False and remaining == [5]


def test_unlocked_when_all_days_done(student, monkeypatch):
    _unlock(monkeypatch, 2)
    unlocked, remaining = assessment.week_unlocked(student, "L0", 2)
    assert unlocked is True and remaining == []
    assert assessment.get_week_state(student, "L0", 2)["state"] == "available"


def test_start_blocked_when_locked(student, monkeypatch):
    _unlock(monkeypatch, 2, calendar={})
    res = assessment.start_attempt(student, "L0", 2)
    assert res["ok"] is False and res["error"] == "locked"
    assert res["days_remaining"] == [1, 2, 3, 4, 5, 6, 7]


def test_start_blocked_when_flag_off(student, monkeypatch):
    database.set_feature_flag("itqan_weekly_assessment", False)
    _unlock(monkeypatch, 2)
    res = assessment.start_attempt(student, "L0", 2)
    assert res["ok"] is False and res["error"] == "disabled"


# ---- start / item draw ----------------------------------------------------

def test_start_returns_items_with_answers_stripped(student, monkeypatch):
    _unlock(monkeypatch, 2)
    res = assessment.start_attempt(student, "L0", 2)
    assert res["ok"] is True
    assert res["attempt_no"] == 1
    assert len(res["items"]) == 10
    # No item's public payload may leak the expected answer.
    for it in res["items"]:
        assert "expected" not in it["payload"]
    # ...but the server DID store the expected answers.
    stored = database.itqan_get_items(res["attempt_id"])
    assert all(s["expected"] for s in stored
               if s["skill"] in ("vocab", "listening", "pronunciation"))


def test_single_active_attempt(student, monkeypatch):
    _unlock(monkeypatch, 2)
    first = assessment.start_attempt(student, "L0", 2)
    assert first["ok"] is True
    second = assessment.start_attempt(student, "L0", 2)
    assert second["ok"] is False and second["error"] == "attempt_in_progress"


# ---- full lifecycle: mastered --------------------------------------------

@pytest.mark.asyncio
async def test_full_lifecycle_mastered(student, monkeypatch):
    _unlock(monkeypatch, 2)
    monkeypatch.setattr("src.pronunciation_scorer.transcribe_audio", _fake_transcribe_echo)

    start = assessment.start_attempt(student, "L0", 2)
    aid = start["attempt_id"]
    await _answer_all_correct(student, aid)
    result = assessment.finish_attempt(student, aid)

    assert result["ok"] is True
    v = result["verdict"]
    assert v["result"] == "mastered"
    assert v["status"] == "scored"
    assert v["mastery_pct"] == 100.0
    assert v["consistency_pct"] == 100.0
    assert v["distinction"] is True
    # Durable mastery recorded.
    assert database.itqan_is_mastered(student, "L0", 2) is True
    assert 2 in database.itqan_mastered_weeks(student, "L0")
    assert assessment.get_week_state(student, "L0", 2)["state"] == "mastered"


@pytest.mark.asyncio
async def test_cannot_restart_once_mastered(student, monkeypatch):
    _unlock(monkeypatch, 2)
    monkeypatch.setattr("src.pronunciation_scorer.transcribe_audio", _fake_transcribe_echo)
    start = assessment.start_attempt(student, "L0", 2)
    await _answer_all_correct(student, start["attempt_id"])
    assessment.finish_attempt(student, start["attempt_id"])

    again = assessment.start_attempt(student, "L0", 2)
    assert again["ok"] is False and again["error"] == "already_mastered"


# ---- full lifecycle: not_yet (low mastery) --------------------------------

@pytest.mark.asyncio
async def test_lifecycle_not_yet_when_all_wrong(student, monkeypatch):
    _unlock(monkeypatch, 2)
    monkeypatch.setattr("src.pronunciation_scorer.transcribe_audio", _fake_transcribe_echo)
    start = assessment.start_attempt(student, "L0", 2)
    aid = start["attempt_id"]
    # Submit obviously wrong answers for every item.
    for it in database.itqan_get_items(aid):
        if it["skill"] in ("pronunciation", "speaking"):
            await assessment.submit_item(student, aid, it["item_no"],
                                         audio_bytes=b"zzz")
        else:
            await assessment.submit_item(student, aid, it["item_no"], answer="zzz")
    result = assessment.finish_attempt(student, aid)
    assert result["verdict"]["result"] == "not_yet"
    assert database.itqan_is_mastered(student, "L0", 2) is False


# ---- cooldown -------------------------------------------------------------

@pytest.mark.asyncio
async def test_cooldown_blocks_retake(student, monkeypatch):
    _unlock(monkeypatch, 2)
    monkeypatch.setattr("src.pronunciation_scorer.transcribe_audio", _fake_transcribe_echo)
    start = assessment.start_attempt(student, "L0", 2)
    for it in database.itqan_get_items(start["attempt_id"]):
        await assessment.submit_item(student, start["attempt_id"], it["item_no"],
                                     answer="zzz", audio_bytes=b"zzz")
    assessment.finish_attempt(student, start["attempt_id"])

    # Default cooldown is 720 min → immediate retake is blocked.
    state = assessment.get_week_state(student, "L0", 2)
    assert state["state"] == "cooldown"
    retry = assessment.start_attempt(student, "L0", 2)
    assert retry["ok"] is False and retry["error"] == "cooldown"


@pytest.mark.asyncio
async def test_retake_allowed_after_cooldown_zero(student, monkeypatch):
    _unlock(monkeypatch, 2)
    database.set_itqan_config("itqan_retake_cooldown_min", 0)
    monkeypatch.setattr("src.pronunciation_scorer.transcribe_audio", _fake_transcribe_echo)
    start = assessment.start_attempt(student, "L0", 2)
    for it in database.itqan_get_items(start["attempt_id"]):
        await assessment.submit_item(student, start["attempt_id"], it["item_no"],
                                     answer="zzz", audio_bytes=b"zzz")
    assessment.finish_attempt(student, start["attempt_id"])

    state = assessment.get_week_state(student, "L0", 2)
    assert state["state"] == "not_yet"
    retry = assessment.start_attempt(student, "L0", 2)
    assert retry["ok"] is True and retry["attempt_no"] == 2


# ---- graceful transcription failure --------------------------------------

@pytest.mark.asyncio
async def test_transcription_failure_flags_for_owner(student, monkeypatch):
    _unlock(monkeypatch, 2)

    async def _fail(audio_bytes, filename="recording.webm"):
        return None
    monkeypatch.setattr("src.pronunciation_scorer.transcribe_audio", _fail)

    start = assessment.start_attempt(student, "L0", 2)
    aid = start["attempt_id"]
    # Submit one recording item whose transcription fails.
    audio_item = next(it for it in database.itqan_get_items(aid)
                      if it["skill"] in ("pronunciation", "speaking"))
    res = await assessment.submit_item(student, aid, audio_item["item_no"],
                                       audio_bytes=b"anything")
    assert res["ok"] is True and res.get("pending_review") is True

    result = assessment.finish_attempt(student, aid)
    # An AI item errored → the owner must decide (never auto-fail on our bug).
    assert result["verdict"]["status"] == "flagged"


# ---- submit guards --------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_rejects_foreign_attempt(student, monkeypatch):
    _unlock(monkeypatch, 2)
    start = assessment.start_attempt(student, "L0", 2)
    res = await assessment.submit_item("someone_else", start["attempt_id"], 1,
                                       answer="x")
    assert res["ok"] is False and res["error"] == "not_found"


@pytest.mark.asyncio
async def test_cannot_submit_after_finish(student, monkeypatch):
    _unlock(monkeypatch, 2)
    monkeypatch.setattr("src.pronunciation_scorer.transcribe_audio", _fake_transcribe_echo)
    start = assessment.start_attempt(student, "L0", 2)
    aid = start["attempt_id"]
    assessment.finish_attempt(student, aid)
    res = await assessment.submit_item(student, aid, 1, answer="x")
    assert res["ok"] is False and res["error"] == "not_in_progress"


def test_finish_rejects_foreign_attempt(student, monkeypatch):
    _unlock(monkeypatch, 2)
    start = assessment.start_attempt(student, "L0", 2)
    res = assessment.finish_attempt("someone_else", start["attempt_id"])
    assert res["ok"] is False and res["error"] == "not_found"
