"""Phase 8 — the CEFR exit exam auto-enables once on deploy (owner decision:
make it live). Idempotent, and does not undo a later manual disable."""
from src import database


def test_autoenable_turns_flag_on_once():
    assert database.is_feature_enabled("assessment_advancement_exam") is False
    assert database.enable_exit_exam_once() is True          # flips it on
    assert database.is_feature_enabled("assessment_advancement_exam") is True
    # idempotent: a second run does nothing and reports it did nothing
    assert database.enable_exit_exam_once() is False
    assert database.is_feature_enabled("assessment_advancement_exam") is True


def test_autoenable_does_not_undo_a_manual_disable():
    database.enable_exit_exam_once()
    assert database.is_feature_enabled("assessment_advancement_exam") is True
    # owner later turns it off deliberately
    database.set_feature_flag("assessment_advancement_exam", enabled=False,
                              updated_by="owner")
    # a restart must NOT re-enable it (the one-time marker is already set)
    assert database.enable_exit_exam_once() is False
    assert database.is_feature_enabled("assessment_advancement_exam") is False
