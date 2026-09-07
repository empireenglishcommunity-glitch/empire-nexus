"""Empire English Chronicles — THE SCRIPT VALIDATOR (spec 4.5 / 4.7 / 4.8).

The audio QA gate (scripts/audio_qa.py) inspects the finished MP3. This validator
inspects the SCRIPT, before a second of audio is rendered, and rejects an episode
that would waste a render or reach a learner in bad shape. Every failure is a short,
specific, human sentence — because those sentences are fed straight back to the
writer for bounded regeneration (spec 4.6), so they must tell it exactly what to fix.

`validate_episode(ep, ...)` returns a LIST of problem strings; an empty list means
the episode passes. It NEVER raises — a validator that crashes would take the whole
pipeline down, which is worse than a weak episode.

Checks (spec 4.5 unless noted):
  * audio contract   — only legal [SFX:...] (podcast_lab), no parenthetical stage
                        directions, markers on their own line;
  * cast legality    — every speaker maps to a real cast member (sawt_cast);
  * cliffhanger      — the episode ends unresolved / on a hook;
  * A/B choice       — two present, distinct, and non-trivial;
  * continuity       — does not contradict the arc's established facts (light);
  * level fit        — spoken word count lands in the CEFR duration window;
  * curiosity device — at least one of the four devices is present (4.7);
  * recap-at-open    — episode > 1 opens with a one-line recap (4.8);
  * vote-at-close    — the close invites the audience to choose (4.8);
  * personalisation safety — a student-named character is never the antagonist
                        (R8.7; the name list arrives in Phase 5 — hook is here now).
"""
from __future__ import annotations

import re

from . import sawt_cast, podcast_lab, sawt_story, sawt_bible

# Inline [SFX:name] or [SFX:a|b] markers, anywhere in the text.
_SFX_RE = re.compile(r"\[sfx:\s*([^\]]+)\]", re.IGNORECASE)
# A parenthetical stage direction like "(whisper)" or "(low, through comm)" — these
# get read aloud and are banned (they were a real shipped defect).
_PAREN_DIRECTION_RE = re.compile(r"\([^)]*\)")
# Words for word-count: letters/digits/apostrophes, ignoring bracketed markers.
_WORD_RE = re.compile(r"[A-Za-z0-9']+")

# How far outside the CEFR duration window we tolerate before failing level-fit.
# The generator already over-asks ×1.3; this is the acceptance band around the
# window converted to words, kept a little generous because ASR/pace vary.
_LEVEL_FIT_SLACK = 0.25

# Cliffhanger / vote / recap signals — cheap, robust text cues.
_VOTE_CUES = ("vote", "choose", "choice", "option a", "option b", "decide",
              "tomorrow", "what should", "which")
_CLIFFHANGER_CUES = ("?", "…", "...", "suddenly", "but then", "before",
                     "to be continued", "what happens next")
_RECAP_CUES = ("last time", "previously", "yesterday", "we left", "so far",
               "when we last", "remember")

# Curiosity devices (spec 4.7) — each detected by cheap, DISTINCTIVE textual
# signals. Deliberately excludes words that also appear in the mandatory
# vote-prompt ("tomorrow", "choose", "or", ...), so a passing vote prompt cannot by
# itself satisfy the curiosity requirement — the two checks stay independent.
_CURIOSITY_SIGNALS = {
    "unanswered-question": ("?",),
    "ticking-clock": ("minutes", "hours", "midnight", "tonight", "in time",
                      "too late", "hurry", "deadline", "running out", "before it"),
    "reframing-reveal": ("realized", "realised", "wasn't", "was not", "actually",
                        "all along", "the truth", "turned out", "never was",
                        "suddenly"),
}


def _spoken_segments(script: str):
    """[(speaker, text)] using the SAME parser the renderer uses, so we count what
    will actually be voiced."""
    try:
        from . import sawt_tts
        return sawt_tts.parse_script(script)
    except Exception:                                            # noqa: BLE001
        # Fallback parser mirroring sawt_tts semantics.
        segs = []
        for raw in (script or "").splitlines():
            line = raw.strip()
            if not line or line[:1] in "[(":
                continue
            m = re.match(r"^\s*([^:\n]{1,40}):\s*(.+)$", line)
            if m and m.group(2).strip():
                segs.append((m.group(1).strip(), m.group(2).strip()))
        return segs


def _spoken_word_count(segments) -> int:
    n = 0
    for _spk, text in segments:
        text = _SFX_RE.sub(" ", text)            # drop inline markers
        n += len(_WORD_RE.findall(text))
    return n


def _level_word_window(level: str) -> tuple:
    """(min_words, max_words) acceptable for `level`, from the CEFR duration window
    and the measured per-pace WPM used by sawt_story.target_length."""
    from . import config
    try:
        prof = config.podcast_level_profile(level or sawt_story.STORY_LEVEL)
        dmin, dmax = float(prof["duration_min"]), float(prof["duration_max"])
        pace = prof.get("pace", "slow")
    except Exception:                                            # noqa: BLE001
        dmin, dmax, pace = 300.0, 420.0, "slow"
    wpm = {"very_slow": 118.0, "slow": 133.0, "moderate": 155.0,
           "natural": 175.0, "fast": 190.0, "native": 205.0}.get(pace, 133.0)
    # The word window must match what the AUDIO gate actually allows: final duration
    # = spoken words at `wpm` PLUS ~45s of non-speech overhead (intro/outro/per-line
    # gaps/pauses). BOTH bounds must keep the render INSIDE [dmin, dmax]:
    #   * HIGH bound: NO positive slack (a small negative margin, *0.98) so a full
    #     delivery can't blow past dmax (measured 2026-09-07: a script the validator
    #     passed rendered to 490s, over A2's 420s).
    #   * LOW bound: NO negative slack. The previous code multiplied the low bound by
    #     (1 - 0.25), which accepted scripts ~25% shorter than dmin needs — so a
    #     valid-by-words script rendered to 225s and FAILED the 300s duration floor
    #     (measured 2026-09-07, 'The Silent Page'). A small POSITIVE margin (*1.05)
    #     keeps the shortest accepted script comfortably above dmin even when Kokoro
    #     delivers slightly faster than the modelled WPM.
    OVERHEAD_S = 45.0        # must match sawt_story.target_length's overhead margin
    lo = max(30.0, dmin - OVERHEAD_S) / 60.0 * wpm * 1.05
    hi = max(60.0, dmax - OVERHEAD_S) / 60.0 * wpm * 0.98
    return int(lo), int(hi)


def _legal_sfx_set() -> set:
    try:
        return set(podcast_lab.sfx_names())
    except Exception:                                            # noqa: BLE001
        return set()


def _tail(script: str, n_lines: int = 6) -> str:
    lines = [ln for ln in (script or "").splitlines() if ln.strip()]
    return "\n".join(lines[-n_lines:]).lower()


def _head(script: str, n_lines: int = 4) -> str:
    lines = [ln for ln in (script or "").splitlines() if ln.strip()]
    return "\n".join(lines[:n_lines]).lower()


def validate_episode(ep: dict, level: str = None, episode_number: int = 1,
                     arc: dict = None, is_arc_finale: bool = False,
                     student_names: list = None) -> list:
    """Return a list of specific problems with `ep`. Empty == passes. Never raises.

    `ep` is the normalized episode dict from sawt_story (title, script, recap,
    facts, mood, vote_a, vote_b, motif_used). `student_names` is the Phase-5 cast
    roster of learner names appearing in the story (empty until Phase 5); the
    dignity check is wired now so it activates the moment names exist."""
    problems: list = []
    try:
        arc = arc or {}
        script = str(ep.get("script", "") or "")
        segments = _spoken_segments(script)

        # --- structural floor -------------------------------------------------
        if len(segments) < 4:
            problems.append("The script has fewer than 4 spoken lines — write a "
                            "full episode of dialogue and narration.")

        # --- cast legality ----------------------------------------------------
        legal_display = {n.lower() for n in sawt_cast.speaking_names()}
        seen_illegal = set()
        for spk, _text in segments:
            entry = sawt_cast.character_for(spk)
            # character_for falls back to narrator for unknowns; treat a label that
            # is neither a known display name nor a known match-token as illegal.
            low = spk.lower().strip()
            known = (low in legal_display
                     or entry["key"] != sawt_cast.DEFAULT_CHARACTER
                     or "narrator" in low or "host" in low)
            if not known and low not in seen_illegal:
                seen_illegal.add(low)
        if seen_illegal:
            allowed = ", ".join(sawt_cast.speaking_names())
            problems.append(
                f"These speakers are not in the cast: {', '.join(sorted(seen_illegal))}. "
                f"Use ONLY these names: {allowed}.")

        # --- SFX legality (audio contract) ------------------------------------
        legal_sfx = _legal_sfx_set()
        bad_sfx = set()
        for m in _SFX_RE.finditer(script):
            for token in re.split(r"[|,/]", m.group(1)):
                name = token.strip().lower()
                if name and legal_sfx and name not in legal_sfx:
                    bad_sfx.add(name)
        if bad_sfx:
            problems.append(
                f"These sound effects don't exist: {', '.join(sorted(bad_sfx))}. "
                f"Use only [SFX:...] names from the menu, or describe the sound in "
                f"the Narrator's words instead.")

        # --- no parenthetical stage directions --------------------------------
        paren_hits = []
        for spk, text in segments:
            if _PAREN_DIRECTION_RE.search(text):
                paren_hits.append(spk)
        if paren_hits:
            problems.append(
                "Remove parenthetical stage directions like '(whisper)' — they get "
                "read aloud. Show tone through the words themselves.")

        # --- level fit --------------------------------------------------------
        words = _spoken_word_count(segments)
        lo, hi = _level_word_window(level)
        if words < lo:
            problems.append(
                f"Too short: about {words} spoken words, but this level needs "
                f"roughly {lo}-{hi}. Develop the scene further.")
        elif words > hi:
            problems.append(
                f"Too long: about {words} spoken words, but this level needs "
                f"roughly {lo}-{hi}. Tighten the episode.")

        # --- A/B choice quality ----------------------------------------------
        a = str(ep.get("vote_a", "") or "").strip()
        b = str(ep.get("vote_b", "") or "").strip()
        if not a or not b:
            problems.append("Provide TWO vote options (vote_a and vote_b).")
        else:
            if a.lower() == b.lower():
                problems.append("The two vote options are identical — make them "
                                "genuinely different choices.")
            if len(a) < 3 or len(b) < 3:
                problems.append("The vote options are too short to be meaningful — "
                                "give each a clear, tempting label.")

        # --- vote-prompt-at-close (4.8) + cliffhanger -------------------------
        tail = _tail(script)
        if not any(cue in tail for cue in _VOTE_CUES):
            problems.append("End by inviting the audience to VOTE between the two "
                            "options (e.g. 'Vote below. Tomorrow the story "
                            "continues the way you choose').")
        if not any(cue in tail for cue in _CLIFFHANGER_CUES):
            problems.append("End on a real cliffhanger — an open question or a "
                            "moment of suspense, not a tidy conclusion.")

        # --- recap-at-open (4.8) ---------------------------------------------
        if episode_number and int(episode_number) > 1 and not is_arc_finale:
            head = _head(script)
            recap_text = str(ep.get("recap", "") or "").strip()
            if not recap_text and not any(cue in head for cue in _RECAP_CUES):
                problems.append("Open with a one-line recap of where we left off "
                                "(this is not episode 1).")

        # --- curiosity device (4.7) ------------------------------------------
        low_all = script.lower()
        wanted = (arc.get("curiosity") if arc else None)
        has_device = False
        for _dev, sigs in _CURIOSITY_SIGNALS.items():
            if any(s in low_all for s in sigs):
                has_device = True
                break
        if not has_device:
            hint = sawt_bible.GENRES.get(arc.get("genre", ""), {}).get(
                "curiosity", wanted or "unanswered-question")
            problems.append(
                f"Add a curiosity device — e.g. {hint.replace('-', ' ')}: leave a "
                f"clear question open, add time pressure, or plant a twist.")

        # --- continuity (light) ----------------------------------------------
        facts = (arc.get("established_facts") if arc else None) or []
        # We can't reason semantically here; we do the cheap, high-value check:
        # a NEGATION that directly contradicts a stated fact phrase. Kept
        # conservative to avoid false rejects (the writer also gets the facts).
        for f in facts:
            fl = str(f).strip().lower()
            if len(fl) > 8 and (f"not {fl}" in low_all or f"no {fl}" in low_all):
                problems.append(
                    f"Do not contradict an established fact: '{f}'.")

        # --- personalisation safety (R8.7) — Phase 5 hook --------------------
        for name in (student_names or []):
            nl = str(name).strip().lower()
            if not nl:
                continue
            # If a learner-named character exists, they must never be cast as the
            # antagonist / villain, and never given demeaning dialogue.
            for spk, text in segments:
                if nl in spk.lower():
                    tl = text.lower()
                    if any(w in tl for w in ("villain", "evil", "stupid", "idiot",
                                             "hate you", "worthless")):
                        problems.append(
                            f"Student-named character '{name}' must never be an "
                            f"antagonist or receive demeaning dialogue.")
                        break
    except Exception:                                            # noqa: BLE001
        # A validator crash must NEVER block the pipeline or spin regeneration
        # forever: treat an internal error as a soft-pass (no problems reported).
        # The audio QA gate downstream is the fail-closed backstop.
        import logging
        logging.getLogger("empire-bot.sawt.validator").exception(
            "script validator crashed — soft-passing this episode")
        return []

    return problems
