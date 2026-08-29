"""Regression: assessment item submissions must accept audio recordings.

The bug (2026-08): the monthly-review and advancement-exam item endpoints
parsed submissions with request.json() ONLY. But a speaking/pronunciation
answer is always sent as multipart/form-data with an `audio` blob, so those
endpoints returned {"ok": false, "error": "bad_json"} for every recording —
the student (Mai) saw "Couldn't save that answer — check your connection"
and retrying never helped, because the server literally could not read the
upload. Only the weekly endpoint handled multipart.

The fix routes all three endpoints through one parser, api_server.
_read_item_submission, which handles BOTH multipart audio and JSON text.
These tests lock that parser's behaviour directly (the same helper-level
unit-test approach the rest of the api_server tests use).
"""
import pytest

from src import api_server


# ============================================================
#  aiohttp request doubles — only what _read_item_submission touches
# ============================================================

class _FakePart:
    def __init__(self, name, *, text=None, data=None, content_type=None):
        self.name = name
        self._text = text
        self._data = data
        self.headers = {}
        if content_type is not None:
            self.headers["Content-Type"] = content_type

    async def read(self):
        return self._data

    async def text(self):
        return self._text


class _FakeReader:
    def __init__(self, parts):
        self._parts = list(parts)

    async def next(self):
        return self._parts.pop(0) if self._parts else None


class _FakeRequest:
    """Fake aiohttp request. content_type drives the parse branch."""
    def __init__(self, *, content_type, parts=None, json_body=None, raise_multipart=False):
        self.headers = {"Content-Type": content_type, "Origin": ""}
        self._parts = parts or []
        self._json = json_body
        self._raise_multipart = raise_multipart

    async def multipart(self):
        if self._raise_multipart:
            raise ValueError("not really multipart")
        return _FakeReader(self._parts)

    async def json(self):
        if self._json is None:
            raise ValueError("no json body")
        return self._json


# ============================================================
#  The bug: multipart audio must be parsed, not rejected
# ============================================================

@pytest.mark.asyncio
async def test_multipart_audio_is_parsed():
    parts = [
        _FakePart("audio", data=b"\x00\x01fake-audio", content_type="audio/webm"),
        _FakePart("attempt_id", text="42"),
        _FakePart("item_no", text="3"),
    ]
    req = _FakeRequest(content_type="multipart/form-data; boundary=x", parts=parts)
    data, err = await api_server._read_item_submission(req)
    assert err is None
    assert data["attempt_id"] == 42
    assert data["item_no"] == 3
    assert data["audio_bytes"] == b"\x00\x01fake-audio"
    assert data["audio_filename"] == "recording.webm"


@pytest.mark.asyncio
async def test_multipart_audio_filename_follows_content_type():
    for ct, expected in [
        ("audio/mp4", "recording.m4a"),
        ("audio/x-m4a", "recording.m4a"),
        ("audio/ogg", "recording.ogg"),
        ("audio/webm", "recording.webm"),
        ("application/octet-stream", "recording.webm"),  # unknown -> default
    ]:
        parts = [
            _FakePart("audio", data=b"a", content_type=ct),
            _FakePart("attempt_id", text="1"),
            _FakePart("item_no", text="1"),
        ]
        req = _FakeRequest(content_type="multipart/form-data; boundary=x", parts=parts)
        data, err = await api_server._read_item_submission(req)
        assert err is None
        assert data["audio_filename"] == expected, ct


@pytest.mark.asyncio
async def test_multipart_with_text_answer_part():
    parts = [
        _FakePart("answer", text="  my sentence  "),
        _FakePart("attempt_id", text="7"),
        _FakePart("item_no", text="2"),
    ]
    req = _FakeRequest(content_type="multipart/form-data; boundary=x", parts=parts)
    data, err = await api_server._read_item_submission(req)
    assert err is None
    assert data["answer"] == "my sentence"
    assert data["audio_bytes"] is None


# ============================================================
#  JSON text path still works
# ============================================================

@pytest.mark.asyncio
async def test_json_text_answer_is_parsed():
    req = _FakeRequest(content_type="application/json",
                       json_body={"attempt_id": 9, "item_no": 4, "answer": " hello "})
    data, err = await api_server._read_item_submission(req)
    assert err is None
    assert data["attempt_id"] == 9
    assert data["item_no"] == 4
    assert data["answer"] == "hello"
    assert data["audio_bytes"] is None


# ============================================================
#  Validation errors
# ============================================================

@pytest.mark.asyncio
async def test_missing_ids_returns_error():
    req = _FakeRequest(content_type="application/json",
                       json_body={"answer": "no ids here"})
    data, err = await api_server._read_item_submission(req)
    assert data is None
    assert err is not None
    assert err.status == 400


@pytest.mark.asyncio
async def test_bad_json_returns_error_not_crash():
    req = _FakeRequest(content_type="application/json", json_body=None)  # .json() raises
    data, err = await api_server._read_item_submission(req)
    assert data is None
    assert err is not None
    assert err.status == 400


@pytest.mark.asyncio
async def test_broken_multipart_returns_error():
    req = _FakeRequest(content_type="multipart/form-data; boundary=x",
                       raise_multipart=True)
    data, err = await api_server._read_item_submission(req)
    assert data is None
    assert err is not None
    assert err.status == 400
