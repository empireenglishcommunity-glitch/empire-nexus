"""Sawt (صوت) — owner voice-clone consent + reference clip storage (Phase 3).

Voice cloning is allowed ONLY for the owner's own voice, and ONLY with explicit
stored consent. This module holds:
  * the consent record (a DB setting), and
  * the reference clip on disk (config.SAWT_DIR/owner_voice_ref.<ext>).

The actual synthesis lives in sawt_tts; this module just guards "may we clone,
and do we have a clip". Both are required before any clone happens.
"""
import logging
import os

from . import config, database

logger = logging.getLogger("empire-bot.sawt.voice")

_CONSENT_KEY = "sawt_voice_consent"          # "yes" once granted
_REF_CLIP_KEY = "sawt_voice_ref_path"        # stored path to the reference clip

# Audio extensions we accept for the reference clip.
REF_CLIP_EXTS = (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm")


def has_consent() -> bool:
    """True if the owner has recorded voice-clone consent."""
    return database.get_setting(_CONSENT_KEY, "") == "yes"


def grant_consent() -> None:
    """Record the owner's voice-clone consent."""
    database.set_setting(_CONSENT_KEY, "yes")
    logger.info("sawt: owner voice-clone consent granted")


def revoke_consent() -> None:
    """Withdraw consent. The clone path refuses again immediately."""
    database.set_setting(_CONSENT_KEY, "")
    logger.info("sawt: owner voice-clone consent revoked")


def ref_clip_path() -> str:
    """The stored reference-clip path, or '' if none saved / missing on disk."""
    p = database.get_setting(_REF_CLIP_KEY, "")
    if p and os.path.exists(p):
        return p
    return ""


def save_ref_clip(data: bytes, filename: str) -> str:
    """Save the owner's reference clip to SAWT_DIR and record its path.
    Returns the stored path. Raises ValueError on an unsupported extension."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in REF_CLIP_EXTS:
        raise ValueError(f"Unsupported audio type {ext!r}; use one of {REF_CLIP_EXTS}")
    config.SAWT_DIR.mkdir(parents=True, exist_ok=True)
    dest = config.SAWT_DIR / f"owner_voice_ref{ext}"
    with open(dest, "wb") as fh:
        fh.write(data)
    database.set_setting(_REF_CLIP_KEY, str(dest))
    logger.info("sawt: saved owner voice reference clip (%d bytes) at %s",
                len(data), dest)
    return str(dest)


def clone_ready() -> tuple[bool, str]:
    """Can the owner's voice be cloned right now? Returns (ready, reason).

    Requires ALL of: the sawt_voice_clone flag ON, consent granted, and a
    reference clip on disk. `reason` explains the first missing piece."""
    if not database.is_feature_enabled("sawt_voice_clone"):
        return False, "the `sawt_voice_clone` flag is off"
    if not has_consent():
        return False, "no voice-clone consent on record (run `!sawt-consent`)"
    if not ref_clip_path():
        return False, "no reference clip saved (attach one with `!sawt-consent`)"
    return True, ""
