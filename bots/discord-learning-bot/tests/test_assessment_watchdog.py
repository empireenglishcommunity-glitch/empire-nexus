"""The watchdog must detect each defect that previously reached a student.

Every check here is written against the SHAPE OF A REAL INCIDENT, not an
invented one. Three assessment defects in a row were found from student
complaints instead of monitoring:

  * `/api/assessment/item` answered HTTP 500 to every request for ~24h — no
    student could submit a weekly answer, at any level.
  * `finish_monthly_attempt` never recorded a result, so `monthly_reviews` sat
    at zero rows while students were completing reviews.
  * Two students were locked out of a weekly test by a stale `in_progress` row
    and neither mentioned it.

So each test reconstructs that exact database state and asserts the watchdog
would have caught it.
"""
import datetime

import pytest

from src import assessment_watchdog, database


LEVEL = "A1"


def _member(did, name):
    database.register_member(did, name, level=LEVEL)
    return did


def _attempt(did, attempt_type="weekly", week=1, status="in_progress",
             started_hours_ago=0, n_items=0):
    started = (datetime.datetime.now(datetime.timezone.utc)
               - datetime.timedelta(hours=started_hours_ago)
               ).strftime("%Y-%m-%d %H:%M:%S")
    conn = database._connect()
    cur = conn.execute(
        "INSERT INTO assessment_attempts (discord_id, level, week, attempt_no, "
        "seed, type, status, started_at) VALUES (?,?,?,?,?,?,?,?)",
        (did, LEVEL, week, 1, "s", attempt_type, status, started),
    )
    aid = cur.lastrowid
    conn.commit()
    conn.close()
    if n_items:
        database.itqan_insert_items(aid, did, [
            {"item_no": i + 1, "skill": "vocab", "source_week": week,
             "payload": {"expected": "x"}} for i in range(n_items)])
    return aid


# ============================================================
#  STRANDED ATTEMPTS — the two silently locked-out students
# ============================================================

def test_a_fresh_in_progress_attempt_is_not_flagged():
    """A student mid-test right now is normal and must not alert."""
    did = _member("700", "Busy Student")
    _attempt(did, started_hours_ago=1)
    assert assessment_watchdog.check_stranded_attempts() == []


def test_an_old_in_progress_attempt_is_flagged():
    did = _member("701", "Stuck Student")
    _attempt(did, week=2, started_hours_ago=assessment_watchdog.STRANDED_HOURS + 6)
    findings = assessment_watchdog.check_stranded_attempts()
    assert len(findings) == 1
    assert "Stuck Student" in findings[0]


def test_a_stranded_weekly_attempt_says_it_blocks_the_retake():
    """The consequence is what matters: on the weekly flow the stale row trips
    the `attempt_in_progress` guard, so the student cannot retake at all."""
    did = _member("702", "Blocked Student")
    _attempt(did, attempt_type="weekly", started_hours_ago=48)
    assert "BLOCKS retake" in assessment_watchdog.check_stranded_attempts()[0]


def test_a_finished_attempt_is_never_stranded():
    did = _member("703", "Done Student")
    _attempt(did, status="scored", started_hours_ago=100)
    assert assessment_watchdog.check_stranded_attempts() == []


# ============================================================
#  MONTHLY RESULTS NOT RECORDED — the reported bug's signature
# ============================================================

def test_a_finished_monthly_with_no_result_row_is_flagged():
    """Exactly the hidden bug: the attempt looks scored from the inside, but the
    student's result was never persisted where the state machine reads it."""
    did = _member("710", "Mai Test")
    aid = _attempt(did, attempt_type="monthly", status="scored")
    findings = assessment_watchdog.check_monthly_results_recorded()
    assert len(findings) == 1
    assert "Mai Test" in findings[0]
    assert str(aid) in findings[0]


def test_a_flagged_monthly_with_no_result_row_is_also_flagged():
    did = _member("711", "Flagged Student")
    _attempt(did, attempt_type="monthly", status="flagged")
    assert len(assessment_watchdog.check_monthly_results_recorded()) == 1


def test_a_monthly_with_its_result_row_is_clean():
    did = _member("712", "Good Student")
    aid = _attempt(did, attempt_type="monthly", status="scored")
    conn = database._connect()
    conn.execute(
        "INSERT INTO monthly_reviews (discord_id, level, review_number, "
        "attempt_id, passed, retention_score) VALUES (?,?,?,?,?,?)",
        (did, LEVEL, 1, aid, 1, 91.6))
    conn.commit()
    conn.close()
    assert assessment_watchdog.check_monthly_results_recorded() == []


def test_an_in_progress_monthly_is_not_expected_to_have_a_result_yet():
    did = _member("713", "Mid Test")
    _attempt(did, attempt_type="monthly", status="in_progress")
    assert assessment_watchdog.check_monthly_results_recorded() == []


# ============================================================
#  POPULATION SMELL — "nobody has EVER got a result"
# ============================================================

def test_many_eligible_and_zero_recorded_is_flagged():
    """The community-level signature: several students eligible for weeks and
    `monthly_reviews` still empty. This is what should have screamed."""
    database.set_feature_flag("assessment_monthly_review", enabled=True)
    for i in range(4):
        did = _member(f"72{i}", f"Eligible {i}")
        for wk in (1, 2, 3, 4):
            database.itqan_upsert_mastery(did, LEVEL, wk, False, None)
    findings = assessment_watchdog.check_eligible_but_never_recorded()
    assert len(findings) == 1
    assert "NOT ONE result" in findings[0]


def test_not_flagged_once_someone_has_a_recorded_result():
    database.set_feature_flag("assessment_monthly_review", enabled=True)
    for i in range(4):
        did = _member(f"73{i}", f"Eligible {i}")
        for wk in (1, 2, 3, 4):
            database.itqan_upsert_mastery(did, LEVEL, wk, False, None)
    conn = database._connect()
    conn.execute(
        "INSERT INTO monthly_reviews (discord_id, level, review_number, passed, "
        "retention_score) VALUES (?,?,?,?,?)", ("730", LEVEL, 1, 1, 80.0))
    conn.commit()
    conn.close()
    assert assessment_watchdog.check_eligible_but_never_recorded() == []


def test_not_flagged_when_too_few_students_are_eligible():
    """Two eligible students with no results is not yet evidence of a defect."""
    database.set_feature_flag("assessment_monthly_review", enabled=True)
    for i in range(2):
        did = _member(f"74{i}", f"Eligible {i}")
        for wk in (1, 2, 3, 4):
            database.itqan_upsert_mastery(did, LEVEL, wk, False, None)
    assert assessment_watchdog.check_eligible_but_never_recorded() == []


def test_silent_when_the_monthly_feature_is_off():
    database.set_feature_flag("assessment_monthly_review", enabled=False)
    for i in range(4):
        did = _member(f"75{i}", f"Eligible {i}")
        for wk in (1, 2, 3, 4):
            database.itqan_upsert_mastery(did, LEVEL, wk, False, None)
    assert assessment_watchdog.check_eligible_but_never_recorded() == []


# ============================================================
#  ORPHAN ITEMS — the parent-before-children delete
# ============================================================

def test_orphan_items_are_flagged():
    did = _member("760", "Orphan Owner")
    aid = _attempt(did, n_items=3)
    conn = database._connect()
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("DELETE FROM assessment_attempts WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    findings = assessment_watchdog.check_orphan_items()
    assert len(findings) == 1
    assert "3 orphan" in findings[0]


def test_no_orphans_reports_nothing():
    did = _member("761", "Clean Owner")
    _attempt(did, n_items=3)
    assert assessment_watchdog.check_orphan_items() == []


# ============================================================
#  ALERTING — must not spam, must report recovery
# ============================================================

class _Holder:
    pass


@pytest.fixture
def ops(monkeypatch):
    sent = []

    async def _alert(title, body, severity="info"):
        sent.append(("alert", title, body))

    async def _msg(text):
        sent.append(("message", text, ""))

    from src import ops_hub
    monkeypatch.setattr(ops_hub, "send_ops_alert", _alert)
    monkeypatch.setattr(ops_hub, "send_ops_message", _msg)
    return sent


@pytest.mark.asyncio
async def test_a_clean_system_sends_nothing(ops, monkeypatch):
    monkeypatch.setattr(assessment_watchdog, "check_endpoints",
                        lambda: _empty())
    holder = _Holder()
    await assessment_watchdog.run_and_alert(holder)
    assert ops == []


async def _empty():
    return []


@pytest.mark.asyncio
async def test_a_problem_alerts_once_not_every_run(ops, monkeypatch):
    """A slow response must not turn into a spam loop."""
    monkeypatch.setattr(assessment_watchdog, "check_endpoints", lambda: _empty())
    did = _member("770", "Stuck Student")
    _attempt(did, started_hours_ago=99)
    holder = _Holder()

    await assessment_watchdog.run_and_alert(holder)
    assert len([s for s in ops if s[0] == "alert"]) == 1

    await assessment_watchdog.run_and_alert(holder)
    await assessment_watchdog.run_and_alert(holder)
    assert len([s for s in ops if s[0] == "alert"]) == 1, \
        "the same finding set must not re-alert"


@pytest.mark.asyncio
async def test_a_new_problem_alerts_again(ops, monkeypatch):
    monkeypatch.setattr(assessment_watchdog, "check_endpoints", lambda: _empty())
    a = _member("780", "First Student")
    _attempt(a, started_hours_ago=99)
    holder = _Holder()
    await assessment_watchdog.run_and_alert(holder)

    b = _member("781", "Second Student")
    _attempt(b, week=3, started_hours_ago=99)
    await assessment_watchdog.run_and_alert(holder)

    assert len([s for s in ops if s[0] == "alert"]) == 2


@pytest.mark.asyncio
async def test_recovery_is_reported_so_silence_is_never_ambiguous(ops, monkeypatch):
    monkeypatch.setattr(assessment_watchdog, "check_endpoints", lambda: _empty())
    did = _member("790", "Stuck Student")
    aid = _attempt(did, started_hours_ago=99)
    holder = _Holder()
    await assessment_watchdog.run_and_alert(holder)

    database.itqan_delete_attempt(aid)
    await assessment_watchdog.run_and_alert(holder)

    messages = [s for s in ops if s[0] == "message"]
    assert len(messages) == 1
    assert "all clear" in messages[0][1]


@pytest.mark.asyncio
async def test_a_failing_check_cannot_break_the_watchdog(monkeypatch):
    """A watchdog must never be the thing that takes the bot down."""
    def _boom():
        raise RuntimeError("database exploded")

    monkeypatch.setattr(assessment_watchdog, "check_endpoints", lambda: _empty())
    monkeypatch.setattr(assessment_watchdog, "check_stranded_attempts", _boom)
    report = await assessment_watchdog.run_checks()
    assert report["checked"] == 4, "the other checks must still run"


# ============================================================
#  REPORT + REGISTRATION
# ============================================================

def test_report_is_explicit_that_nothing_was_changed():
    text = assessment_watchdog.format_report({"findings": ["something wrong"]})
    assert "read-only" in text.lower()
    assert "something wrong" in text


def test_clean_report_states_how_many_checks_ran():
    text = assessment_watchdog.format_report({"findings": [], "checked": 5})
    assert "OK" in text and "5 checks" in text


def test_probe_list_covers_the_endpoint_that_was_dead():
    assert "/api/assessment/item" in assessment_watchdog.PROBE_ENDPOINTS


def test_500_is_not_an_acceptable_status():
    """The whole point: a clean rejection is fine, a 500 is not."""
    assert 500 not in assessment_watchdog._ACCEPTABLE
    assert 401 in assessment_watchdog._ACCEPTABLE


def test_flag_is_registered_and_defaults_off():
    from src import flag_registry
    info = flag_registry.get_flag_info(assessment_watchdog.FLAG)
    assert info is not None
    assert info["default_enabled"] is False
