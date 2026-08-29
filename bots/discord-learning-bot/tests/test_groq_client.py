"""Tests for groq_client.chat_completion — the bounded 429 retry.

Locks in the resilience fix that reduces both Groq failures and the
"Groq API Issues" owner alert:

  * a transient 429 is retried once and can succeed on the retry;
  * the retry honours a small Retry-After;
  * a 429 with a LARGE Retry-After is NOT waited on (never stalls a
    student request) — we give up and report the 429;
  * 5xx and other non-200s are NOT retried;
  * a success on the first try never retries;
  * exceptions become ok=False / status=None (no raise).
"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from src import groq_client


# ============================================================
#  aiohttp doubles (project convention: unittest.mock, no aioresponses)
# ============================================================

class _FakeResp:
    def __init__(self, status, json_data=None, headers=None):
        self.status = status
        self._json = json_data if json_data is not None else {}
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self):
        return self._json

    async def text(self):
        return json.dumps(self._json)


class _FakeSession:
    """Returns the queued responses in order, one per .post() call."""
    def __init__(self, responses):
        self._responses = list(responses)
        self.post_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def post(self, *args, **kwargs):
        self.post_calls += 1
        return self._responses.pop(0)


def _ok_body(text="hello"):
    return {"choices": [{"message": {"content": text}}]}


# ============================================================
#  Happy path
# ============================================================

@pytest.mark.asyncio
async def test_success_first_try_no_retry(monkeypatch):
    monkeypatch.setattr(groq_client.config, "GROQ_API_KEY", "test-key")
    session = _FakeSession([_FakeResp(200, _ok_body("hi"))])
    with patch("src.groq_client.aiohttp.ClientSession", return_value=session), \
         patch("src.groq_client.asyncio.sleep", new=AsyncMock()) as sleep:
        result = await groq_client.chat_completion({"model": "m", "messages": []}, 15)
    assert result.ok is True
    assert result.text == "hi"
    assert result.status == 200
    assert session.post_calls == 1
    sleep.assert_not_awaited()


# ============================================================
#  429 retry behaviour
# ============================================================

@pytest.mark.asyncio
async def test_429_then_success_retries_once(monkeypatch):
    monkeypatch.setattr(groq_client.config, "GROQ_API_KEY", "test-key")
    session = _FakeSession([
        _FakeResp(429, headers={"Retry-After": "1"}),
        _FakeResp(200, _ok_body("recovered")),
    ])
    with patch("src.groq_client.aiohttp.ClientSession", return_value=session), \
         patch("src.groq_client.asyncio.sleep", new=AsyncMock()) as sleep:
        result = await groq_client.chat_completion({"model": "m", "messages": []}, 15)
    assert result.ok is True
    assert result.text == "recovered"
    assert session.post_calls == 2
    sleep.assert_awaited_once()
    assert sleep.await_args.args[0] == 1.0


@pytest.mark.asyncio
async def test_429_twice_reports_final_429(monkeypatch):
    monkeypatch.setattr(groq_client.config, "GROQ_API_KEY", "test-key")
    session = _FakeSession([
        _FakeResp(429, headers={"Retry-After": "1"}),
        _FakeResp(429, headers={"Retry-After": "1"}),
    ])
    with patch("src.groq_client.aiohttp.ClientSession", return_value=session), \
         patch("src.groq_client.asyncio.sleep", new=AsyncMock()):
        result = await groq_client.chat_completion({"model": "m", "messages": []}, 15)
    assert result.ok is False
    assert result.status == 429
    assert session.post_calls == 2  # exactly one retry, no more


@pytest.mark.asyncio
async def test_429_with_no_retry_after_uses_default_wait(monkeypatch):
    monkeypatch.setattr(groq_client.config, "GROQ_API_KEY", "test-key")
    session = _FakeSession([
        _FakeResp(429),  # no Retry-After header
        _FakeResp(200, _ok_body("ok")),
    ])
    with patch("src.groq_client.aiohttp.ClientSession", return_value=session), \
         patch("src.groq_client.asyncio.sleep", new=AsyncMock()) as sleep:
        result = await groq_client.chat_completion({"model": "m", "messages": []}, 15)
    assert result.ok is True
    assert session.post_calls == 2
    assert sleep.await_args.args[0] == groq_client.DEFAULT_RETRY_WAIT_SECONDS


@pytest.mark.asyncio
async def test_429_with_large_retry_after_does_not_wait_or_retry(monkeypatch):
    """A 'come back in 60s' must never stall a live request — give up now."""
    monkeypatch.setattr(groq_client.config, "GROQ_API_KEY", "test-key")
    session = _FakeSession([_FakeResp(429, headers={"Retry-After": "60"})])
    with patch("src.groq_client.aiohttp.ClientSession", return_value=session), \
         patch("src.groq_client.asyncio.sleep", new=AsyncMock()) as sleep:
        result = await groq_client.chat_completion({"model": "m", "messages": []}, 15)
    assert result.ok is False
    assert result.status == 429
    assert session.post_calls == 1  # no retry
    sleep.assert_not_awaited()


# ============================================================
#  Non-429 failures are NOT retried
# ============================================================

@pytest.mark.asyncio
async def test_500_is_not_retried(monkeypatch):
    monkeypatch.setattr(groq_client.config, "GROQ_API_KEY", "test-key")
    session = _FakeSession([_FakeResp(503)])
    with patch("src.groq_client.aiohttp.ClientSession", return_value=session), \
         patch("src.groq_client.asyncio.sleep", new=AsyncMock()) as sleep:
        result = await groq_client.chat_completion({"model": "m", "messages": []}, 15)
    assert result.ok is False
    assert result.status == 503
    assert session.post_calls == 1
    sleep.assert_not_awaited()


# ============================================================
#  Exceptions never raise
# ============================================================

@pytest.mark.asyncio
async def test_exception_returns_ok_false_status_none(monkeypatch):
    monkeypatch.setattr(groq_client.config, "GROQ_API_KEY", "test-key")

    class _BoomSession:
        async def __aenter__(self):
            raise RuntimeError("network down")

        async def __aexit__(self, *exc):
            return False

    with patch("src.groq_client.aiohttp.ClientSession", return_value=_BoomSession()):
        result = await groq_client.chat_completion({"model": "m", "messages": []}, 15)
    assert result.ok is False
    assert result.status is None


# ============================================================
#  Retry-After parsing
# ============================================================

def test_parse_retry_after_handles_bad_values():
    assert groq_client._parse_retry_after(None) is None
    assert groq_client._parse_retry_after("") is None
    assert groq_client._parse_retry_after("not-a-number") is None
    assert groq_client._parse_retry_after("-3") is None
    assert groq_client._parse_retry_after("2") == 2.0
    assert groq_client._parse_retry_after("0") == 0.0
