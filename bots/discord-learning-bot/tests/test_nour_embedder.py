"""Tests for src/nour/knowledge/embedder.py — Aql (#15) Phase A1.2.

Network-calling embed_text() is tested via mocked aiohttp responses
(no real Gemini API calls in the test suite -- consistent with how
this codebase already tests other Groq/Gemini call sites, e.g.
test_nour_concierge.py's patterns). The pure functions (pack/unpack,
cosine_similarity, normalization) are tested directly and exhaustively
-- these are the functions every later phase's correctness depends on.
"""
import numpy as np
import pytest

from src.nour.knowledge.embedder import (
    EMBEDDING_DIM,
    _normalize,
    cosine_similarity,
    embed_text,
    pack_embedding,
    unpack_embedding,
)
from src import config


# ============================================================
#  PACK / UNPACK ROUND-TRIP
# ============================================================

def test_pack_unpack_round_trip_exact():
    original = np.random.rand(EMBEDDING_DIM).astype(np.float32)
    packed = pack_embedding(original)
    restored = unpack_embedding(packed)
    np.testing.assert_array_equal(original, restored)


def test_pack_produces_expected_byte_length():
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    packed = pack_embedding(vec)
    assert len(packed) == EMBEDDING_DIM * 4  # float32 = 4 bytes each


def test_pack_accepts_non_float32_input_and_converts():
    """A caller passing a plain Python list or float64 array must not
    crash pack_embedding -- it should coerce to float32 for consistent
    BLOB size, matching what unpack_embedding always assumes."""
    vec_list = [0.1] * EMBEDDING_DIM
    packed = pack_embedding(np.array(vec_list))
    assert len(packed) == EMBEDDING_DIM * 4
    restored = unpack_embedding(packed)
    assert restored.dtype == np.float32


# ============================================================
#  NORMALIZATION
# ============================================================

def test_normalize_produces_unit_length_vector():
    vec = np.array([3.0, 4.0] + [0.0] * (EMBEDDING_DIM - 2), dtype=np.float32)
    normed = _normalize(vec)
    assert abs(np.linalg.norm(normed) - 1.0) < 1e-5


def test_normalize_zero_vector_does_not_crash():
    """A degenerate zero-vector embedding (should never happen in
    practice, but must not raise a divide-by-zero) is returned as-is."""
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    normed = _normalize(vec)
    np.testing.assert_array_equal(normed, vec)


# ============================================================
#  COSINE SIMILARITY
# ============================================================

def test_cosine_similarity_identical_vectors_is_one():
    vec = np.random.rand(EMBEDDING_DIM).astype(np.float32)
    vec = _normalize(vec)
    sim = cosine_similarity(vec, vec)
    assert abs(sim - 1.0) < 1e-5


def test_cosine_similarity_orthogonal_vectors_is_zero():
    a = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    a[0] = 1.0
    b = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    b[1] = 1.0
    sim = cosine_similarity(a, b)
    assert abs(sim) < 1e-6


def test_cosine_similarity_opposite_vectors_is_negative_one():
    a = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    a[0] = 1.0
    b = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    b[0] = -1.0
    sim = cosine_similarity(a, b)
    assert abs(sim - (-1.0)) < 1e-6


def test_cosine_similarity_handles_zero_vector_gracefully():
    zero = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    other = np.ones(EMBEDDING_DIM, dtype=np.float32)
    assert cosine_similarity(zero, other) == 0.0
    assert cosine_similarity(other, zero) == 0.0
    assert cosine_similarity(zero, zero) == 0.0


def test_cosine_similarity_is_symmetric():
    a = np.random.rand(EMBEDDING_DIM).astype(np.float32)
    b = np.random.rand(EMBEDDING_DIM).astype(np.float32)
    assert abs(cosine_similarity(a, b) - cosine_similarity(b, a)) < 1e-6


def test_cosine_similarity_works_correctly_on_unnormalized_input():
    """cosine_similarity must be correct even if given vectors that
    were NOT pre-normalized by embed_text() -- it computes full cosine
    similarity (dividing by both norms), not a bare dot product that
    would silently assume unit length."""
    a = np.array([2.0, 0.0] + [0.0] * (EMBEDDING_DIM - 2), dtype=np.float32)  # not unit length
    b = np.array([5.0, 0.0] + [0.0] * (EMBEDDING_DIM - 2), dtype=np.float32)  # not unit length, same direction
    sim = cosine_similarity(a, b)
    assert abs(sim - 1.0) < 1e-5  # same direction -> similarity 1, regardless of magnitude


# ============================================================
#  embed_text() — NETWORK CALL, MOCKED
# ============================================================

class _FakeResponse:
    def __init__(self, status, json_body):
        self.status = status
        self._json_body = json_body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self):
        return self._json_body

    async def text(self):
        return str(self._json_body)


class _FakeSession:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def post(self, *args, **kwargs):
        return self._response


@pytest.mark.asyncio
async def test_embed_text_returns_none_when_no_api_key(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    result = await embed_text("hello")
    assert result is None


@pytest.mark.asyncio
async def test_embed_text_returns_none_for_empty_string(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    assert await embed_text("") is None
    assert await embed_text("   ") is None


@pytest.mark.asyncio
async def test_embed_text_returns_normalized_vector_on_success(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    fake_values = list(np.random.rand(EMBEDDING_DIM))
    fake_response = _FakeResponse(200, {"embedding": {"values": fake_values}})

    import src.nour.knowledge.embedder as embedder_module
    monkeypatch.setattr(
        embedder_module.aiohttp, "ClientSession",
        lambda: _FakeSession(fake_response),
    )

    result = await embed_text("ما هي المهام اليومية؟")
    assert result is not None
    assert result.shape == (EMBEDDING_DIM,)
    assert abs(np.linalg.norm(result) - 1.0) < 1e-4  # manually normalized per Google's own requirement


@pytest.mark.asyncio
async def test_embed_text_returns_none_on_api_error_status(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    fake_response = _FakeResponse(429, {"error": "rate limited"})

    import src.nour.knowledge.embedder as embedder_module
    monkeypatch.setattr(
        embedder_module.aiohttp, "ClientSession",
        lambda: _FakeSession(fake_response),
    )

    result = await embed_text("test")
    assert result is None


@pytest.mark.asyncio
async def test_embed_text_returns_none_on_wrong_dimension(monkeypatch):
    """If Gemini ever returns a different dimension than requested
    (e.g. a future API change), this must be treated as a failure, not
    silently stored as a corrupt-shaped vector that would break every
    later cosine_similarity call against it."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    wrong_size_values = list(np.random.rand(512))  # not EMBEDDING_DIM
    fake_response = _FakeResponse(200, {"embedding": {"values": wrong_size_values}})

    import src.nour.knowledge.embedder as embedder_module
    monkeypatch.setattr(
        embedder_module.aiohttp, "ClientSession",
        lambda: _FakeSession(fake_response),
    )

    result = await embed_text("test")
    assert result is None


@pytest.mark.asyncio
async def test_embed_text_returns_none_on_missing_values_field(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    fake_response = _FakeResponse(200, {"embedding": {}})

    import src.nour.knowledge.embedder as embedder_module
    monkeypatch.setattr(
        embedder_module.aiohttp, "ClientSession",
        lambda: _FakeSession(fake_response),
    )

    result = await embed_text("test")
    assert result is None
