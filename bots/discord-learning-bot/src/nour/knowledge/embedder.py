"""Aql (العقل) — Gemini Embedding Client.

design.md Section 4.2: embeddings via Gemini's free embedContent
endpoint (model gemini-embedding-001), reusing the existing
GEMINI_API_KEY -- zero new signup, zero new paid service, per the $0
budget constraint.

Uses the model's documented ASYMMETRIC retrieval task types
(RETRIEVAL_DOCUMENT for knowledge chunks being indexed,
RETRIEVAL_QUERY for the student's incoming question) -- this is
Google's own recommended pattern for exactly our use case (index once,
query many times against a different kind of text), not a detail we
invented. See https://ai.google.dev/gemini-api/docs/embeddings.

Output dimensionality is fixed at 768 (Google's own recommended
value, and the smallest of the three "Recommended" sizes) --
design.md Section 4.2's numeric justification is built on this exact
dimension. gemini-embedding-001 requires MANUAL normalization for any
non-3072 output_dimensionality (unlike the newer gemini-embedding-2),
which this module performs explicitly -- skipping this step would
silently degrade cosine-similarity quality without erroring.
"""
import logging
from typing import Optional

import aiohttp
import numpy as np

from ... import config

logger = logging.getLogger("empire-bot.nour.embedder")

EMBEDDING_DIM = 768
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"


async def embed_text(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> Optional[np.ndarray]:
    """Embed a single string via the Gemini embedContent endpoint.

    task_type: "RETRIEVAL_DOCUMENT" when embedding knowledge chunks at
    index-build time (Phase A1.3), "RETRIEVAL_QUERY" when embedding an
    incoming student/owner question at query time (Phase A1.6) -- the
    asymmetric pattern Gemini's own docs recommend for retrieval.

    Returns a normalized float32 numpy array of shape (768,), or None
    on any failure (missing API key, network error, malformed
    response) -- callers must treat None as "embedding unavailable"
    and fall back accordingly (design.md Section 4.3's keyword-match
    fallback tier), never crash.
    """
    if not config.GEMINI_API_KEY:
        return None
    if not text or not text.strip():
        return None

    url = _ENDPOINT.format(model=config.GEMINI_EMBEDDING_MODEL)
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": config.GEMINI_API_KEY,
    }
    payload = {
        "model": f"models/{config.GEMINI_EMBEDDING_MODEL}",
        "content": {"parts": [{"text": text}]},
        "taskType": task_type,
        "outputDimensionality": EMBEDDING_DIM,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning(f"Gemini embedding API error {resp.status}: {body[:200]}")
                    return None
                data = await resp.json()
                values = data.get("embedding", {}).get("values", [])
                if not values:
                    logger.warning("Gemini embedding response had no values")
                    return None
                vec = np.array(values, dtype=np.float32)
                if vec.shape[0] != EMBEDDING_DIM:
                    logger.warning(f"Unexpected embedding dimension {vec.shape[0]}, expected {EMBEDDING_DIM}")
                    return None
                return _normalize(vec)
    except Exception as e:
        logger.error(f"Gemini embedding call failed: {e}")
        return None


def _normalize(vec: np.ndarray) -> np.ndarray:
    """gemini-embedding-001 requires MANUAL normalization for any
    output_dimensionality other than the full 3072 -- per Google's own
    docs (see this module's docstring). A zero vector (degenerate edge
    case, e.g. empty embedding) is returned as-is to avoid a
    divide-by-zero; cosine similarity against a zero vector is 0
    regardless, which is the correct "no similarity" result anyway."""
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


def pack_embedding(vec: np.ndarray) -> bytes:
    """Pack a float32 numpy array into raw bytes for SQLite BLOB
    storage (design.md Section 4.2's `embedding BLOB NOT NULL`
    column)."""
    return np.asarray(vec, dtype=np.float32).tobytes()


def unpack_embedding(blob: bytes) -> np.ndarray:
    """Inverse of pack_embedding -- reconstruct a float32 numpy array
    from a BLOB read back out of knowledge_chunks."""
    return np.frombuffer(blob, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors. Both embed_text() outputs
    are already normalized (unit length), so this reduces to a plain
    dot product -- but implemented as full cosine similarity (not a
    bare np.dot) so this function is correct even if called with a
    vector that wasn't produced by embed_text() (e.g. a future caller,
    or a test fixture, passing in an unnormalized vector)."""
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
