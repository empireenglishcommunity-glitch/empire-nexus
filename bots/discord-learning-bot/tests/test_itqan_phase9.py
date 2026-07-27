"""Itqan pilot-polish batch — recording retention + owner review breakdown."""
import pytest

from src import assessment, database


@pytest.fixture
def student():
    database.register_member("s1", "Student", "L0")
    return "s1"


def _attempt_with_items(did):
    att = database.itqan_create_attempt(did, "L0", 1, "seed")
    aid = att["id"]
    items = [
        {"item_no": 1, "skill": "speaking", "source_week": 1,
         "payload": {"target_words": ["book"]}},
        {"item_no": 2, "skill": "vocab", "source_week": 1,
         "payload": {"expected": "book", "prompt_ar": "كتاب"}},
    ]
    database.itqan_insert_items(aid, did, items)
    return aid


# ---- recording retention --------------------------------------------------

def test_save_and_get_recording(student):
    aid = _attempt_with_items(student)
    database.itqan_save_recording(aid, student, 1, "speaking", "recording.webm", b"AUDIODATA")
    recs = database.itqan_get_recordings(aid)
    assert len(recs) == 1
    assert recs[0]["item_no"] == 1
    assert recs[0]["audio"] == b"AUDIODATA"
    assert recs[0]["skill"] == "speaking"


def test_save_recording_upserts_per_item(student):
    aid = _attempt_with_items(student)
    database.itqan_save_recording(aid, student, 1, "speaking", "r.webm", b"one")
    database.itqan_save_recording(aid, student, 1, "speaking", "r.webm", b"two")  # re-record
    recs = database.itqan_get_recordings(aid)
    assert len(recs) == 1 and recs[0]["audio"] == b"two"


def test_purge_removes_old_but_keeps_recent(student):
    aid = _attempt_with_items(student)
    database.itqan_save_recording(aid, student, 1, "speaking", "r.webm", b"x")
    # A fresh recording is kept.
    assert database.itqan_purge_recordings(days=14) == 0
    assert len(database.itqan_get_recordings(aid)) == 1
    # Backdate it beyond the window → purged.
    conn = database._connect()
    conn.execute("UPDATE assessment_recordings SET created_at=? WHERE attempt_id=?",
                 ("2000-01-01 00:00:00", aid))
    conn.commit()
    conn.close()
    assert database.itqan_purge_recordings(days=14) == 1
    assert database.itqan_get_recordings(aid) == []


def test_reset_purges_recordings(student):
    aid = _attempt_with_items(student)
    database.itqan_save_recording(aid, student, 1, "speaking", "r.webm", b"x")
    database.itqan_reset(student, "L0", 1)
    assert database.itqan_get_recordings(aid) == []


@pytest.mark.asyncio
async def test_submit_item_retains_recording(student, monkeypatch):
    async def _fake_tx(audio, filename="x"):
        return "book"
    monkeypatch.setattr("src.pronunciation_scorer.transcribe_audio", _fake_tx)
    aid = _attempt_with_items(student)
    res = await assessment.submit_item(student, aid, 1, audio_bytes=b"RAWAUDIO",
                                       audio_filename="recording.m4a")
    assert res["ok"] is True
    recs = database.itqan_get_recordings(aid)
    assert len(recs) == 1
    assert recs[0]["audio"] == b"RAWAUDIO"
    assert recs[0]["filename"] == "recording.m4a"


# ---- owner review breakdown ----------------------------------------------

def test_format_attempt_review(student):
    aid = _attempt_with_items(student)
    database.itqan_save_item(aid, 1, "i read a book", ai_score=40.0, correct=False,
                             feedback="Nice effort")
    database.itqan_save_item(aid, 2, "buk", auto_score=0.0, correct=False,
                             feedback="Correct answer: book")
    database.itqan_finish_attempt(aid, 45.0, 90.0, "not_yet", False, "flagged", False)
    att = database.itqan_get_attempt(aid)
    items = database.itqan_get_items(aid)
    text = assessment.format_attempt_review(att, items, name="BioRoMa", rec_item_nos=[1])
    assert "Itqan review — BioRoMa" in text
    assert "[audio attached]" in text          # item 1 has a recording
    assert 'heard: "i read a book"' in text     # speaking transcript labelled 'heard'
    assert 'expected: "book"' in text           # wrong vocab shows the answer
    assert "!itqan-pass @BioRoMa 1" in text
