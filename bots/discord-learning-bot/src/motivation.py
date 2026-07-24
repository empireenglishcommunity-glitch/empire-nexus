"""Hafiz (حافظ) — AI Motivational Auto-Replies.

Phase F of practice-enhancements-2026-07 (E4, owner feedback #7): "for
level 0 there are 2 channels text practice and showcase, people are
active on both and I need the bot to react to their messages and reply
with motivation messages but every reply is different -- no reply is
similar to another reply... the goal is to keep them motivated and
engaged."

Reacts to student posts in `#lN-text-practice` (written sentences) and
`#lN-showcase` (voice/audio recordings) with a short, warm, ALWAYS-VARIED
encouragement. Deliberately narrow in scope:

- Never corrects, scores, or critiques (that's `#writing-feedback`'s job
  via `ai_engine.evaluate_writing`, and the dedicated speaking-feedback
  channel) -- this is pure encouragement, R4.5.
- Never repeats a recent reply verbatim in the same channel (an
  in-memory ring per channel + a "don't reuse these" hint to the LLM).
- Throttled per student per channel so a burst of messages doesn't spam
  a reply after every single line.
- Behind the `hafiz_motivation` feature flag, default OFF, so it can be
  verified live before going out to all students.

Gated behind 'hafiz_motivation' feature flag (default off).
"""
import datetime
import logging
import random
from collections import deque
from typing import Optional

from . import ai_engine, config

logger = logging.getLogger("empire-bot.hafiz")

# ============================================================
#  THROTTLE (per student, per channel) -- avoid burst spam
# ============================================================

THROTTLE_SECONDS = 60

# {(discord_id, channel_id): datetime} -- in-memory only, matches the
# existing verification.py `_last_done_time` pattern (module-level dict,
# not persisted; a bot restart simply resets the throttle window, which
# is harmless here since worst case is one extra reply after a restart).
_last_reply_time: dict[tuple[str, int], datetime.datetime] = {}


def _is_throttled(discord_id: str, channel_id: int) -> bool:
    key = (discord_id, channel_id)
    last = _last_reply_time.get(key)
    if not last:
        return False
    return (datetime.datetime.now() - last).total_seconds() < THROTTLE_SECONDS


def _record_reply(discord_id: str, channel_id: int) -> None:
    _last_reply_time[(discord_id, channel_id)] = datetime.datetime.now()


def reset_throttle_state() -> None:
    """Test-only helper: clear all in-memory throttle/ring state so tests
    don't leak state into each other (mirrors verification.py's fixtures
    for `_last_done_time`/`_voice_sessions`)."""
    _last_reply_time.clear()
    for ring in _recent_replies.values():
        ring.clear()


# ============================================================
#  NON-REPETITION RING (per channel) -- "don't say the same thing twice"
# ============================================================

RING_SIZE = 12

# {channel_id: deque[str]} -- the last N replies actually sent in that
# channel (across all students), so a new reply is never a near-repeat
# of something a student just saw a moment ago, even from someone else.
_recent_replies: dict[int, deque] = {}


def _recent_for_channel(channel_id: int) -> deque:
    ring = _recent_replies.get(channel_id)
    if ring is None:
        ring = deque(maxlen=RING_SIZE)
        _recent_replies[channel_id] = ring
    return ring


def _remember_reply(channel_id: int, text: str) -> None:
    _recent_for_channel(channel_id).append(text)


# ============================================================
#  FALLBACK POOLS -- used if the AI call fails or returns something
#  unusable (too long, empty, etc.). Large + varied so a fallback still
#  doesn't feel repetitive; randomised, never the first untried entry.
# ============================================================

_TEXT_FALLBACKS = [
    "Look at you, writing in English! Every sentence is a brick in the wall you're building. 🧱",
    "That sentence took courage. Keep stacking them up, one by one.",
    "Writing it down makes it real. You just made your English a little more real today.",
    "Small sentence, big step. Proud of you for showing up and writing.",
    "This is exactly how fluency happens -- not all at once, but sentence by sentence, like this one.",
    "You didn't wait for perfect. You just wrote. That's the whole game. 👏",
    "Your future self is going to look back at posts like this and smile.",
    "Nice! Writing in a new language takes guts -- you've got them.",
    "Every word you type here is practice your brain remembers.",
    "That's another rep in the books. Keep the streak of showing up alive.",
    "You're turning thoughts into English, live, in front of everyone. Respect. 🙌",
    "Consistency beats perfection -- and you're being consistent right here.",
    "This is what progress actually looks like: messy, brave, and moving forward.",
    "Love seeing you write. Keep the sentences coming!",
    "You just practiced English on purpose today. That matters more than it feels like right now.",
]

_VOICE_FALLBACKS = [
    "Hearing your voice in English is huge -- most people never get past the fear of speaking. You did. 🎙️",
    "That recording took real courage. Speaking out loud is the hardest part, and you just did it.",
    "You didn't just think in English, you SPOKE it. That's a whole different level.",
    "Your voice, your English, out loud for everyone -- that's brave and it's working.",
    "This is exactly the kind of practice that builds real fluency, not just theory.",
    "Every recording is a rep your mouth and brain remember. Keep going!",
    "You showed up and spoke. That's the win, no matter how it sounded.",
    "Speaking is scary at first and you did it anyway. That's the whole story of getting fluent.",
    "Your future confident-English-speaker self says thank you for this recording. 👏",
    "That's another voice rep in the bank. Fluency is built exactly like this.",
    "Love that you recorded yourself -- that's real practice, not just studying.",
    "You just did the hardest part of learning a language: opening your mouth and going for it.",
    "Keep recording. Every clip is proof you're moving forward, not just standing still.",
    "This is what bravery in language learning sounds like. Keep it up!",
    "Your voice is getting more comfortable in English every time you do this.",
]


def _fallback_pool(post_type: str) -> list[str]:
    return _VOICE_FALLBACKS if post_type == "voice" else _TEXT_FALLBACKS


def _pick_fallback(channel_id: int, post_type: str) -> str:
    """Pick a fallback that isn't one of the last few replies actually
    sent in this channel, if avoidable."""
    pool = _fallback_pool(post_type)
    recent = set(_recent_for_channel(channel_id))
    candidates = [m for m in pool if m not in recent] or pool
    return random.choice(candidates)


# ============================================================
#  AI-GENERATED REPLY
# ============================================================

MAX_REPLY_LEN = 280


async def _generate_ai_reply(student_name: str, post_type: str,
                             channel_id: int) -> Optional[str]:
    """Ask the LLM for a short, unique, correction-free encouragement.

    post_type: "text" (a written sentence in #text-practice) or "voice"
    (an audio recording in #showcase).
    """
    recent = list(_recent_for_channel(channel_id))
    avoid_hint = ""
    if recent:
        sample = recent[-6:]
        avoid_hint = (
            "\n\nDo NOT reuse the wording, structure, or opening of any of "
            "these recent messages you (or another instance of you) already "
            "sent in this channel -- write something genuinely different:\n"
            + "\n".join(f"- {r}" for r in sample)
        )

    what_they_did = (
        "just recorded themselves speaking English out loud"
        if post_type == "voice"
        else "just wrote a sentence in English"
    )

    prompt = f"""You are a warm, encouraging English-learning community bot. A learner named {student_name} {what_they_did} in a practice channel.

Write ONE short motivational reply (max 2 short sentences, under 40 words). Rules:
- Encouragement and engagement ONLY. Do NOT correct grammar, spelling, pronunciation, or give any feedback on quality -- that happens in a different channel.
- Do NOT repeat a generic template feel -- make it sound like a real, specific, warm reaction to {"speaking up" if post_type == "voice" else "writing"}.
- Vary your opening word/phrase every time -- never start the same way twice.
- At most 1 emoji.
- Arabic-speaking learners, but reply in English.
- Plain text only, no markdown headers, no quotes around the message.{avoid_hint}"""

    try:
        result = await ai_engine._call_llm(prompt, temperature=1.0)
    except Exception as e:
        logger.warning(f"Hafiz motivation AI call raised: {e}")
        return None

    if not result:
        return None
    result = result.strip().strip('"').strip()
    if not result or len(result) > MAX_REPLY_LEN:
        return None
    return result


# ============================================================
#  PUBLIC ENTRY POINT
# ============================================================

MIN_TEXT_LENGTH = 3  # ignore near-empty messages (e.g. a lone emoji)


async def maybe_reply(discord_id: str, student_name: str, channel_id: int,
                      post_type: str, content: str,
                      has_attachment: bool) -> Optional[str]:
    """Decide whether to send a motivational reply, and produce one.

    Returns the reply text to send, or None if no reply should be sent
    (throttled, message too short/empty with no attachment, etc.). Does
    NOT check the feature flag or send anything itself -- callers
    (bot.py's on_message) own the flag check and the actual Discord
    send, exactly like the rest of this codebase's on_message hooks
    (e.g. features.check_english_only).
    """
    if post_type == "text" and not has_attachment and len(content.strip()) < MIN_TEXT_LENGTH:
        return None
    if _is_throttled(discord_id, channel_id):
        return None

    reply = await _generate_ai_reply(student_name, post_type, channel_id)
    if not reply:
        reply = _pick_fallback(channel_id, post_type)

    _record_reply(discord_id, channel_id)
    _remember_reply(channel_id, reply)
    return reply
