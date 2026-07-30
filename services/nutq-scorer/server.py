"""Nutq 2 scorer — internal HTTP service (aiohttp).

Endpoints:
  GET  /health           → {ok, model_loaded}
  POST /score            → score one recording

/score request JSON:
  { "audio_b64": "<base64 audio bytes>", "reference_text": "...",
    "level": "L0", "filename": "rec.webm" }
/score response JSON (on success):
  { "ok": true, "score": 63.0, "raw_score": 61.2, "missed_words": ["through"],
    "per_word": [...], "feedback_en": "...", "feedback_ar": "...",
    "heard_phonemes": "...", "expected": "..." }

SAFETY
- Internal-only service; the bot calls it over the compose network.
- Shared-secret auth via X-Nutq-Token (env NUTQ_SCORER_TOKEN). If the env is
  unset, auth is disabled (dev only) and a warning is logged.
- CPU inference is serialized through a single-worker executor so we never run
  two models at once (protects the memory cap on a small box, R4).
- Every failure returns JSON (never a 500 stacktrace); the bot treats any
  non-ok/timeout as "couldn't score this time" and the student flow is untouched.
"""
import asyncio
import base64
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from aiohttp import web

import scorer

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("nutq-scorer.server")

TOKEN = os.environ.get("NUTQ_SCORER_TOKEN", "")
MAX_AUDIO_BYTES = 8 * 1024 * 1024  # 8 MB guard
# Single worker → only one inference at a time (memory safety, R4).
_EXECUTOR = ThreadPoolExecutor(max_workers=1)


def _authorized(request: web.Request) -> bool:
    if not TOKEN:
        return True  # dev mode (warned at startup)
    return request.headers.get("X-Nutq-Token", "") == TOKEN


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({
        "ok": True,
        "model_loaded": scorer._RECOGNIZER is not None,
    })


async def handle_score(request: web.Request) -> web.Response:
    if not _authorized(request):
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad json"}, status=400)

    reference_text = (data.get("reference_text") or "").strip()
    audio_b64 = data.get("audio_b64") or ""
    level = data.get("level") or "L0"
    filename = data.get("filename") or "rec.webm"
    if not reference_text or not audio_b64:
        return web.json_response(
            {"ok": False, "error": "reference_text and audio_b64 required"}, status=400)

    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception:
        return web.json_response({"ok": False, "error": "bad base64"}, status=400)
    if not audio_bytes or len(audio_bytes) > MAX_AUDIO_BYTES:
        return web.json_response({"ok": False, "error": "audio size invalid"}, status=400)

    # Offload the blocking CPU inference to the single-worker executor.
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        _EXECUTOR, scorer.score_audio, audio_bytes, reference_text, level, filename)

    status = 200 if result.get("ok") else 422
    return web.json_response(result, status=status)


def _warm_model():
    """Load the model once at startup so the first request isn't slow."""
    try:
        logger.info("warming phoneme model…")
        scorer._get_recognizer()
        logger.info("model loaded.")
    except Exception as e:  # noqa: BLE001
        logger.error("model warm failed (will lazy-load on first request): %s", e)


def make_app() -> web.Application:
    if not TOKEN:
        logger.warning("NUTQ_SCORER_TOKEN not set — auth DISABLED (dev only).")
    app = web.Application(client_max_size=MAX_AUDIO_BYTES + 1024 * 1024)
    app.router.add_get("/health", handle_health)
    app.router.add_post("/score", handle_score)
    return app


if __name__ == "__main__":
    _warm_model()
    port = int(os.environ.get("PORT", "8080"))
    web.run_app(make_app(), host="0.0.0.0", port=port)
