"""Shared Groq HTTP client with a bounded, conservative retry on 429.

WHY THIS EXISTS
---------------
Both ai_engine and narrative_engine POST to Groq's chat-completions
endpoint. On the Groq free tier, HTTP 429 (rate-limit) is common but
almost always *transient* — Groq returns a ``Retry-After`` telling us
how long to wait. Previously any 429 meant the request immediately fell
back to non-AI content (curated tasks / rule-based scoring / templates)
AND counted toward the "Groq API Issues" owner alert.

A single, bounded retry that honours a *small* Retry-After recovers most
of those transient 429s, which means fewer requests fall back and fewer
alerts fire — without changing the shape of anything a student sees.

DELIBERATELY CONSERVATIVE (so this can never hurt the live system):
  * Retries AT MOST ONCE, and ONLY on 429. 5xx / other errors are NOT
    retried — an immediate retry does not help a server-side outage and
    we must not hammer a struggling API.
  * Waits only when Retry-After is present and <= MAX_RETRY_AFTER_SECONDS.
    A "come back in 60s" therefore does NOT stall a student's request —
    we give up immediately and let the caller fall back, exactly as before.
  * Never raises. Any exception (timeout, connection error) returns a
    GroqResult with ok=False and status=None, matching the old behaviour.
  * The API-key guard stays in the callers, so "no key configured" is
    still a silent None with no failure tracked (unchanged).

Reverting is a one-line change per call site (call the endpoint directly
again); no data, schema, or student-facing surface is touched.
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

from . import config

logger = logging.getLogger("empire-bot.groq_client")

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Never stall a live request longer than this waiting on a rate-limit.
MAX_RETRY_AFTER_SECONDS = 5.0
# Used when a 429 arrives without a usable Retry-After header.
DEFAULT_RETRY_WAIT_SECONDS = 1.0


@dataclass
class GroqResult:
    """Outcome of a Groq call. ``status`` is the HTTP status of the FINAL
    attempt (429/5xx/etc.), or None when no response was received at all
    (timeout / connection error). Callers use ``status`` to track
    failures for the ops alert."""
    ok: bool
    text: Optional[str] = None
    status: Optional[int] = None


def _parse_retry_after(header_value: Optional[str]) -> Optional[float]:
    """Parse a Retry-After header expressed in seconds. Returns None for a
    missing/unparseable/negative value (Groq sends a plain seconds value;
    we intentionally do not handle the HTTP-date form — a missing parse
    just means we use the default short wait)."""
    if not header_value:
        return None
    try:
        seconds = float(header_value)
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


async def chat_completion(payload: dict, timeout_seconds: float) -> GroqResult:
    """POST a chat-completion ``payload`` to Groq with one bounded 429 retry.

    ``payload`` is the full request body (model, messages, temperature,
    optional max_tokens). Callers keep their own GROQ_API_KEY guard and
    decide how to track failures / fall back based on the returned status.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
    }
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def _attempt(session) -> tuple[GroqResult, Optional[float]]:
        """One HTTP attempt. Returns (result, retry_after_seconds_or_None)."""
        async with session.post(_GROQ_URL, json=payload, headers=headers,
                                timeout=timeout) as resp:
            if resp.status == 200:
                data = await resp.json()
                text = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                return GroqResult(ok=True, text=text.strip() if text else None,
                                  status=200), None
            retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
            return GroqResult(ok=False, text=None, status=resp.status), retry_after

    try:
        async with aiohttp.ClientSession() as session:
            result, retry_after = await _attempt(session)
            if result.ok:
                return result

            # Only a 429 is worth an immediate retry, and only if the
            # server is telling us to come back *soon*.
            if result.status == 429:
                wait = retry_after if retry_after is not None else DEFAULT_RETRY_WAIT_SECONDS
                if wait <= MAX_RETRY_AFTER_SECONDS:
                    logger.info(f"Groq 429 rate-limit; retrying once after {wait:.1f}s")
                    await asyncio.sleep(wait)
                    retry_result, _ = await _attempt(session)
                    return retry_result
                logger.warning(
                    f"Groq 429 with Retry-After={wait:.0f}s (> {MAX_RETRY_AFTER_SECONDS:.0f}s cap); "
                    f"not waiting, falling back"
                )
            return result
    except Exception as e:
        logger.error(f"Groq request failed: {e}")
        return GroqResult(ok=False, text=None, status=None)
