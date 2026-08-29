"""Tests for the Groq failure alert (ops_monitoring.track_groq_failure).

Locks in three fixes made after the owner reported getting the alert
"a lot" on the Empire Ops Telegram bot:

  1. The alert must NOT claim "Gemini fallback is handling requests" —
     the Google project is access-denied (403), so Gemini is dormant.
     Requests actually fall back to built-in curated/rule-based content.
  2. The body must be PLAIN text — send_ops_alert() escapes MarkdownV2
     itself, so pre-escaping here caused a double-escape and the owner
     saw literal backslashes ("rate\\-limited\\.").
  3. The alert distinguishes 429 rate-limits from 5xx outages and
     no-response failures, so it's actionable.
"""
from unittest.mock import AsyncMock, patch

import pytest

from src import ops_monitoring


@pytest.fixture(autouse=True)
def reset_groq_state():
    """track_groq_failure uses module-level globals for the failure
    window and the once-per-hour throttle. Reset them before each test
    so state never leaks between tests regardless of run order."""
    ops_monitoring._groq_failures.clear()
    ops_monitoring._groq_alert_sent_at = 0
    yield
    ops_monitoring._groq_failures.clear()
    ops_monitoring._groq_alert_sent_at = 0


async def _fire(status, times):
    """Record `times` failures with the given HTTP status, returning the
    patched send_ops_alert mock."""
    with patch("src.ops_hub.send_ops_alert", new=AsyncMock()) as alert:
        for _ in range(times):
            await ops_monitoring.track_groq_failure(status)
        return alert


# ============================================================
#  Threshold + throttle
# ============================================================

@pytest.mark.asyncio
async def test_no_alert_below_threshold():
    alert = await _fire(429, ops_monitoring._GROQ_FAILURE_THRESHOLD - 1)
    assert alert.await_count == 0


@pytest.mark.asyncio
async def test_alert_fires_at_threshold():
    alert = await _fire(429, ops_monitoring._GROQ_FAILURE_THRESHOLD)
    assert alert.await_count == 1


@pytest.mark.asyncio
async def test_alert_throttled_to_once_per_window():
    """Even with many failures past the threshold, only one alert is sent
    within the window (the owner's complaint was frequency, not absence)."""
    alert = await _fire(429, ops_monitoring._GROQ_FAILURE_THRESHOLD + 10)
    assert alert.await_count == 1


# ============================================================
#  Fix #1: truthful fallback wording (no false "Gemini is handling it")
# ============================================================

@pytest.mark.asyncio
async def test_alert_does_not_claim_gemini_is_handling_requests():
    alert = await _fire(429, ops_monitoring._GROQ_FAILURE_THRESHOLD)
    _, body, *_ = alert.await_args.args
    lowered = body.lower()
    # Must not repeat the old false claim.
    assert "gemini fallback is handling" not in lowered
    # Must state the truth: Gemini is NOT the fallback in play.
    assert "gemini is not handling" in lowered
    assert "403" in body


# ============================================================
#  Fix #2: plain text — no double-escaped backslashes
# ============================================================

@pytest.mark.asyncio
async def test_alert_body_is_plain_text_no_manual_escaping():
    alert = await _fire(429, ops_monitoring._GROQ_FAILURE_THRESHOLD)
    _, body, *_ = alert.await_args.args
    # The bug the owner saw: literal backslashes in the message. The body
    # handed to send_ops_alert (which escapes for us) must contain none.
    assert "\\" not in body


# ============================================================
#  Fix #3: actionable cause breakdown
# ============================================================

@pytest.mark.asyncio
async def test_rate_limit_wording_when_mostly_429():
    alert = await _fire(429, ops_monitoring._GROQ_FAILURE_THRESHOLD)
    _, body, *_ = alert.await_args.args
    assert "429" in body
    assert "rate-limit" in body.lower()


@pytest.mark.asyncio
async def test_server_error_wording_when_mostly_5xx():
    alert = await _fire(503, ops_monitoring._GROQ_FAILURE_THRESHOLD)
    _, body, *_ = alert.await_args.args
    assert "5xx" in body.lower() or "503" in body
    assert "outage" in body.lower()


@pytest.mark.asyncio
async def test_no_status_wording_when_calls_had_no_response():
    """Exception-path callers pass no status (timeout / connection error)."""
    with patch("src.ops_hub.send_ops_alert", new=AsyncMock()) as alert:
        for _ in range(ops_monitoring._GROQ_FAILURE_THRESHOLD):
            await ops_monitoring.track_groq_failure()  # no status arg
    _, body, *_ = alert.await_args.args
    lowered = body.lower()
    assert "timeout" in lowered or "unreachable" in lowered


@pytest.mark.asyncio
async def test_severity_is_warning():
    alert = await _fire(429, ops_monitoring._GROQ_FAILURE_THRESHOLD)
    assert alert.await_args.kwargs.get("severity") == "warning"


@pytest.mark.asyncio
async def test_title_unchanged():
    alert = await _fire(429, ops_monitoring._GROQ_FAILURE_THRESHOLD)
    title = alert.await_args.args[0]
    assert title == "Groq API Issues"
