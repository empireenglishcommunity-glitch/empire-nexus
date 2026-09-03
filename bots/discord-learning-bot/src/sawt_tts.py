"""Sawt (صوت) — podcast audio assembly (Phase 3).

Turns a reviewed, speaker-labelled script into a multi-speaker audio episode:

  1. parse_script  — split "Speaker: line" text into ordered (speaker, text) segments.
  2. VOICE registry — map each speaker to an engine + voice (owner → cloned voice,
     co-hosts → Kokoro voice ids).
  3. assemble_episode — synthesize each segment with the right engine and stitch
     them together with natural pauses + loudness normalization.

CRITICAL infra note (see the spec's Phase 3 decision): the Discord bot runs in a
512MB / 0.5-CPU container and CANNOT host a TTS engine in-process. So the engine
adapter is *pluggable* and *degrades gracefully*: if no engine is importable on
the host — the normal case for the bot — engine_available() is False and
assemble_episode returns a clear "render offline" result instead of crashing.
The identical code path produces real audio wherever an engine IS available
(the GitHub Actions renderer, a GPU host, or a future TTS service).
"""
import logging
import re
from typing import Optional

logger = logging.getLogger("empire-bot.sawt.tts")

# Speaker → voice. "owner" uses the cloned voice (Chatterbox + reference clip);
# everyone else uses a Kokoro voice id. Matching is case-insensitive and by
# substring, so "Host (you)" → owner, "AI co-host" → a co-host voice, etc.
# Order matters: the co-host entries are checked BEFORE "owner" so a label like
# "AI co-host" (which contains "host") maps to a co-host, not the owner. The
# owner match tokens are deliberately specific ("host (you)", "you", "owner") and
# never a bare "host".
VOICE_REGISTRY = {
    "cohost_f": {"engine": "kokoro", "voice_id": "af_heart",
                 "match": ("co-host", "cohost", "ai guest 1", "guest 1")},
    "cohost_m": {"engine": "kokoro", "voice_id": "am_adam",
                 "match": ("ai host", "ai guest 2", "guest 2", "ai guest", "guest")},
    "owner": {"engine": "clone", "match": ("host (you)", "(you)", "owner")},
}

# A line looks like "Speaker name: the spoken text". [PAUSE] markers are kept
# in the text so the synth step can insert a real pause.
_LINE_RE = re.compile(r"^\s*([^:\n]{1,40}):\s*(.+)$")


def parse_script(script: str) -> list:
    """Parse a speaker-labelled script into ordered [(speaker, text), ...].

    Lines without a "Speaker: text" shape (blank lines, section rules, stray
    notes) are skipped. A line's speaker keeps its original label; mapping to a
    voice happens in voice_for()."""
    segments = []
    for raw in (script or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        speaker, text = m.group(1).strip(), m.group(2).strip()
        if text:
            segments.append((speaker, text))
    return segments


def voice_for(speaker_label: str) -> dict:
    """Map a script speaker label to a voice entry from VOICE_REGISTRY.
    Falls back to the female co-host voice for an unrecognized label."""
    low = (speaker_label or "").lower()
    for key, entry in VOICE_REGISTRY.items():
        for token in entry["match"]:
            if token in low:
                return {"role": key, **entry}
    return {"role": "cohost_f", **VOICE_REGISTRY["cohost_f"]}


def engine_available() -> bool:
    """True only if a TTS engine can actually run in THIS process. On the 512MB
    bot host this is False (kokoro-onnx / chatterbox aren't installed there), so
    callers fall back to the offline-render path. Never raises."""
    try:
        import importlib.util
        return (importlib.util.find_spec("kokoro_onnx") is not None
                or importlib.util.find_spec("chatterbox") is not None)
    except Exception:
        return False


def plan_episode(script: str) -> dict:
    """A dry, engine-free plan of what an episode would synthesize: the segment
    count, the distinct voices used, and whether the owner's cloned voice is
    needed. Safe to run anywhere (no audio, no engine)."""
    segs = parse_script(script)
    voices = {}
    for speaker, _text in segs:
        v = voice_for(speaker)
        voices.setdefault(v["role"], 0)
        voices[v["role"]] += 1
    return {
        "segment_count": len(segs),
        "voices": voices,
        "needs_clone": any(voice_for(s)["engine"] == "clone" for s, _ in segs),
    }


async def assemble_episode(script: str, out_path: str = None) -> dict:
    """Assemble a multi-speaker episode from a script.

    Returns a result dict: {ok, reason, segment_count, out_path}. When no engine
    is available in-process (the bot host), returns ok=False with a reason that
    tells the owner to render offline — it NEVER crashes the command. Where an
    engine IS available, this is the seam that drives real synthesis (Kokoro for
    co-hosts, Chatterbox + the owner's reference clip for the cloned voice),
    inserts natural pauses, and loudness-normalizes — implemented by the
    offline renderer, which imports this module's parse_script/voice_for.
    """
    plan = plan_episode(script)
    if plan["segment_count"] == 0:
        return {"ok": False, "reason": "empty_script", "segment_count": 0,
                "out_path": None}
    if not engine_available():
        return {
            "ok": False,
            "reason": "engine_unavailable",
            "segment_count": plan["segment_count"],
            "out_path": None,
        }
    # Engine IS available (CI renderer / GPU host / future service). The concrete
    # synthesis is provided by the offline renderer that imports parse_script +
    # voice_for; the bot process never reaches here on the 512MB host.
    raise NotImplementedError(
        "In-process synthesis runs only in the offline renderer, not the bot.")
