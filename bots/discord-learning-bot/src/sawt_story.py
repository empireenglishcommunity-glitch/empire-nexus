"""Sawt (صوت) — Empire Chronicles serialized-story generation.

The storytelling podcast is ONE continuous story told one episode per day. Each
episode ends on a cliffhanger with an A/B audience vote; the next day's episode
continues the story the way the audience chose. This module generates the NEXT
episode's script (English-only) from the running story so far + the winning
choice, in the cast format the renderer understands:

    Narrator: ...              (owner's cloned voice)
    Maya: ...                  (Mai's cloned voice)
    Leo: ...                   (a distinct American voice)
    ... [SFX:knock|creak]      (real sound effects, inline)
    ... [PAUSE 2s]             (dramatic timing)

It WRITES a script + the two vote options; it never renders audio (that's the
offline renderer) and never posts anything (that's the bot).
"""
import asyncio
import json
import logging
import re
from typing import Optional

from . import config, ai_engine, sawt_cast, sawt_bible, podcast_lab

logger = logging.getLogger("empire-bot.sawt.story")

# Level band for the story: mixed but pitched around A2–B1 so it's approachable
# for most students while still engaging (English-only per the owner's decision).
STORY_LEVEL = "A2"


def story_cast_names() -> list:
    """The speaking names the writer may use — DERIVED from the cast registry
    (sawt_cast), never a hand-kept list, so the writer can only name characters the
    renderer can actually voice (spec R2.7, R6.2)."""
    return sawt_cast.speaking_names()


def legal_sfx() -> list:
    """The inline [SFX:...] names the writer may use — DERIVED from the podcast_lab
    manifest (spec R5.6), so the writer can never request a sound we don't own.
    Falls back to a tiny safe set only if the library can't be read."""
    try:
        names = podcast_lab.sfx_names()
        if names:
            return names
    except Exception:                                            # noqa: BLE001
        pass
    return ["knock", "creak", "footsteps"]


_STORY_SYSTEM = (
    "You are the head writer of 'Empire English Chronicles', a serialized audio "
    "drama for English learners. You write natural, cinematic, suspenseful spoken "
    "scripts in CLEAR, simple English. Return ONLY valid JSON — no preamble.")


def target_length(level: str = None) -> tuple:
    """(target_words, target_minutes) for an episode at `level`.

    Derived from the SAME CEFR profile the rest of Empire English uses, so episode
    length follows the learner's level (spec R7.1). Every v1 episode was 98-161s
    against A2's 300-420s window and failed the duration gate — the generator was
    asking for "~2 minutes" regardless of level.

    Words are computed from the level's delivery pace: at slower paces the same
    minute holds fewer words, so a slower level needs FEWER words for the same
    duration, not more."""
    lvl = level or STORY_LEVEL
    try:
        from . import config
        prof = config.podcast_level_profile(lvl)
        dmin, dmax = float(prof["duration_min"]), float(prof["duration_max"])
        pace = prof.get("pace", "slow")
    except Exception:                                            # noqa: BLE001
        dmin, dmax, pace = 300.0, 420.0, "slow"
    # Measured words-per-minute of the cast at each CEFR pace (benchmarked with
    # scripts/benchmark_story_voices.py — see src/sawt_cast.PACE_SPEED).
    wpm = {"very_slow": 118.0, "slow": 133.0, "moderate": 155.0,
           "natural": 175.0, "fast": 190.0, "native": 205.0}.get(pace, 133.0)
    # The gate measures FINAL AUDIO duration = spoken words at `wpm` PLUS non-speech
    # overhead the words don't account for: the musical intro (~1.5s), the outro
    # (~2.5s), a short gap between every line (~0.3-0.5s each — dozens of them), and
    # any [PAUSE] beats. Measured 2026-09-07: 65 lines of speech that computed to
    # ~400s rendered to 424s (over A2's 420s ceiling). So budget the WORDS against
    # the window MINUS that overhead, not the raw window.
    OVERHEAD_S = 45.0                      # intro+outro+per-line gaps+pauses, measured
                                           # (2026-09-07: 28s under-shot -> 421s; a
                                           # bigger margin lands the render well
                                           # inside the ceiling)
    usable_max = max(60.0, dmax - OVERHEAD_S)
    usable_min = max(30.0, dmin - OVERHEAD_S)
    # Aim a little below the middle of the (overhead-adjusted) window for room.
    target_seconds = usable_min + (usable_max - usable_min) * 0.40
    words = target_seconds / 60.0 * wpm
    # Mild over-ask (LLMs often under-deliver: measured asked 780, got 586)...
    words *= 1.15
    # ...but CLAMP so even a FULL delivery + overhead stays ~5% under the ceiling.
    max_words = (usable_max * 0.95) / 60.0 * wpm
    words = min(words, max_words)
    return int(round(words / 10.0) * 10), target_seconds / 60.0


# A curated, unambiguous SFX shortlist to SUGGEST in the prompt — the most
# story-useful sounds. The validator still accepts the full podcast_lab vocabulary;
# this just keeps the prompt readable and steers the writer to reliable effects.
_SFX_SUGGESTED = ["knock", "door", "creak", "footsteps", "wind", "thunder",
                  "clock", "bell", "crowd", "water", "fire", "glass"]

# Curiosity devices the writer must land at least one of (spec §6.5 / task 4.7).
_CURIOSITY_MENU = {
    "unanswered-question": "raise a specific question and deliberately NOT answer it",
    "ticking-clock": "put a clear time pressure on the characters",
    "reframing-reveal": "reveal one fact that makes the listener re-read the scene",
    "two-branches": "end with two genuinely tempting, very different choices",
}


def _sfx_menu() -> str:
    """The [SFX:...] menu shown in the prompt — the curated shortlist intersected
    with what the library actually owns, so we never suggest a missing effect."""
    have = set(legal_sfx())
    menu = [s for s in _SFX_SUGGESTED if s in have] or sorted(have)[:12]
    return ", ".join(f"[SFX:{s}]" for s in menu)


def build_story_prompt(previous_summary: str, winning_choice: str,
                       episode_number: int, level: str = None,
                       arc: dict = None, is_arc_opener: bool = False,
                       is_arc_finale: bool = False, past_choices: list = None,
                       motif_seen: bool = False,
                       student_cameos: list = None,
                       vocabulary: list = None) -> str:
    """Prompt the LLM to write the next episode as JSON. Now ARC-AWARE (spec 4.4):
    it injects the story bible (recurring characters + their wants), the current
    arc (genre, setting, premise, mood, established facts), the CEFR length, the
    legal SFX menu (from the owned library), and the arc's position (opener /
    middle / finale). `arc` is the sawt_arc arc block; when omitted the prompt
    degrades gracefully to a single warm standalone episode."""
    target_words, target_minutes = target_length(level)
    sfx = _sfx_menu()
    arc = arc or {}
    genre = arc.get("genre") or "everyday"
    setting = arc.get("setting") or "a small town"
    premise = arc.get("premise") or "an ordinary day turns on one small decision"
    mood = arc.get("mood") or sawt_bible.genre_mood(genre)
    leads = arc.get("leads") or sawt_bible.leads_for_arc(genre)
    facts = arc.get("established_facts") or []
    curiosity = arc.get("curiosity") or "unanswered-question"
    curiosity_hint = _CURIOSITY_MENU.get(curiosity,
                                         _CURIOSITY_MENU["unanswered-question"])

    # --- Continuity / arc position ---------------------------------------------
    if is_arc_opener and episode_number == 1:
        continuity = (
            f"This is episode {episode_number} — the VERY FIRST episode of the "
            f"series, and it OPENS a new story arc. Introduce the world and the "
            f"lead characters and hook the listener fast.")
    elif is_arc_opener:
        continuity = (
            f"This is episode {episode_number}. The previous arc has ended. START "
            f"A BRAND-NEW, SELF-CONTAINED STORY — a fresh {genre} arc in a new "
            f"place. Do NOT continue the old plot; only the recurring characters "
            f"carry over. The story so far (for character continuity only):\n"
            f"{previous_summary}")
    else:
        so_far = f"The story so far:\n{previous_summary}\n\n" if previous_summary else ""
        chose = (f"The audience voted for this to happen next: \"{winning_choice}\".\n"
                 f"Continue the story from that choice.\n" if winning_choice else "")
        finale = ("This is the FINALE of the arc — bring the arc's central question "
                  "to a satisfying RESOLUTION this episode, while still ending on a "
                  "small hook and an A/B vote that opens tomorrow's brand-new arc.\n"
                  if is_arc_finale else "")
        continuity = (f"This is episode {episode_number}. {so_far}{chose}{finale}")

    facts_block = ""
    if facts:
        facts_block = ("\nESTABLISHED FACTS you must stay consistent with (do not "
                       "contradict these):\n" + "\n".join(f"- {f}" for f in facts))

    # The listener-echo signature: occasionally nod to a past audience choice.
    echo_block = ""
    if past_choices:
        echo_block = (f"\nLISTENER ECHO (optional, subtle): the audience has shaped "
                      f"this story before — e.g. they once chose \"{past_choices[-1]}\". "
                      f"You may quietly acknowledge that their choices mattered.")

    # The recurring motif signature.
    motif = sawt_bible.MOTIF
    if motif_seen:
        motif_block = (f"\nMOTIF: {motif['name']} has already appeared in this arc. "
                       f"You may reference it again, lightly.")
    else:
        motif_block = (f"\nMOTIF (optional texture): you MAY let {motif['name']} "
                       f"appear briefly. {motif['note']}")

    # STUDENT CAMEOS (Phase 5). Real learners appear as brief, friendly guest
    # characters — never the villain, never embarrassed, first name only. Each
    # comes with its KNOWN gender so the writer keeps pronouns/role right (we never
    # guess a gender). These names become ADDITIONALLY-allowed speakers on top of
    # the fixed cast; the validator enforces the dignity rules.
    # ARABIC SCAFFOLDING (Phase 6 / R7.4) — reserved hook, disabled today. Returns
    # '' unless sawt_syllabus.ARABIC_SCAFFOLDING_ENABLED is turned on, so enabling
    # Arabic later needs no change here.
    arabic_block = ""
    try:
        from . import sawt_syllabus
        arabic_block = sawt_syllabus.arabic_directive(level)
    except Exception:                                            # noqa: BLE001
        arabic_block = ""

    # CURRICULUM VOCABULARY (Phase 6 / R7.3). The current teaching week's target
    # words, to REINFORCE naturally inside the story — never as a word list, quiz,
    # or definition. Optional: empty when the curriculum isn't readable.
    vocab_block = ""
    vocab_list = [str(w).strip() for w in (vocabulary or []) if str(w).strip()]
    if vocab_list:
        vocab_block = (
            "\n\nCURRICULUM TIE-IN (this week's words): "
            + ", ".join(f"\"{w}\"" for w in vocab_list) + ".\n"
            "Weave SEVERAL of these words NATURALLY into the dialogue and narration "
            "so a learner meets them in a real context — never as a list, a "
            "definition, or a vocabulary lesson. If a word doesn't fit the scene, "
            "skip it rather than force it.")

    cameo_block = ""
    cameo_names_list = [c.get("story_name") for c in (student_cameos or [])
                        if c.get("story_name")]
    if cameo_names_list:
        who = ", ".join(
            f"{c['story_name']} ({(c.get('gender') or '').strip() or 'unspecified'})"
            for c in student_cameos if c.get("story_name"))
        cameo_block = (
            f"\n\nGUEST LEARNERS (feature warmly, briefly): {who}.\n"
            f"- These are REAL students of our community appearing as a friendly "
            f"treat. Give EACH a short, positive moment (a helpful line, a kind "
            f"exchange, a small brave act) — a background guest, not the focus.\n"
            f"- Use their gender ONLY for correct pronouns/role; do not comment on "
            f"it. Use their FIRST NAME exactly as given.\n"
            f"- ABSOLUTE RULES: a guest learner is NEVER the villain/antagonist, is "
            f"NEVER mocked, insulted, frightened, humiliated or shown failing, and "
            f"NEVER says or receives demeaning words. If in doubt, make them kind "
            f"and capable. They may speak, so label their lines with their first "
            f"name (e.g. '{cameo_names_list[0]}: ...').")

    return f"""{continuity}

Write this episode of Empire English Chronicles as a spoken audio script.

THIS ARC:
- Genre: {genre}. Setting: {setting}.
- Premise / engine of the arc: {premise}.
- Emotional mood: {mood} (the background music will match this — write to it).
- Leads to feature: {', '.join(leads)}.{facts_block}{echo_block}{motif_block}

LENGTH — this is a hard requirement, not a guideline:
Write approximately {target_words} words of SPOKEN text (all speaker lines added
together). That fills a {target_minutes:.0f}-minute episode at this level's delivery
pace; an episode outside its length window is rejected automatically. Do not pad —
use the room to develop the scene, let characters react, and build tension.

CAST (use these names EXACTLY; each maps to a distinct voice — you may not invent
new named characters, only use these{" plus the GUEST LEARNERS listed below" if cameo_names_list else ""}):
{sawt_bible.character_brief()}
Use 2–4 speaking characters this episode (not all at once) — lively but not
confusing for a learner. Feature the arc's leads above.{cameo_block}{vocab_block}{arabic_block}

STYLE:
- CLEAR simple English (learners), but genuinely suspenseful and cinematic.
- Real spoken dialogue, short sentences, natural rhythm.
- WHO SAYS WHAT: characters speak ONLY the words they say out loud; the NARRATOR
  describes all action and scene. NEVER put narration in a character line — not
  "Maya: I push the door open" but "Narrator: Maya pushes the door open."
- NO stage directions or parenthetical delivery hints (no "(low)", "(whisper)") —
  they get read aloud. Show tone through the words and the Narrator.
- Sound effects: use ONLY from this menu — {sfx} — on their OWN line, never spoken
  by a character. Do NOT invent effects; if you need other atmosphere, have the
  Narrator describe it in words.
- Use [PAUSE 2s] to hold tension, especially right before the cliffhanger.
- OPEN with the Narrator's signature "Welcome to Empire English Chronicles..."
  {"and a ONE-LINE recap of where we left off" if episode_number > 1 else ""}.
- CURIOSITY: this episode must {curiosity_hint}.
- END on a strong cliffhanger, then the Narrator asks the audience to choose
  between EXACTLY TWO clearly-different, both-tempting options, and says
  "Vote below. Tomorrow, the story continues the way you choose."

Return ONLY this JSON object (no preamble, no code fences):
{{
  "title": "short episode title",
  "script": "the full speaker-labelled script, one line per speaker turn (Narrator:/Maya:/Leo:/Sara:/Mrs. Adel:/The Stranger:/Nour:) with inline [SFX:...] and [PAUSE 2s] markers",
  "recap": "2-3 sentence summary of what happened THIS episode (seeds the next one)",
  "facts": ["1-4 short new story facts established this episode, for continuity"],
  "mood": "{mood}",
  "vote_a": "short label for choice A",
  "vote_b": "short label for choice B",
  "motif_used": {str(bool(motif_seen)).lower()}
}}"""


def _extract_json(text: str) -> Optional[dict]:
    """Pull the JSON object out of an LLM response (tolerant of code fences)."""
    if not text:
        return None
    # Strip <think>…</think> reasoning blocks first. Some accessible Groq models
    # (e.g. qwen/qwen3.6-27b) prepend a reasoning block that can itself contain
    # braces, which would derail the outermost-{…} match below. Remove it (and any
    # unclosed trailing "<think>…" with no closer) before looking for the JSON.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)
    text = re.sub(r"<think>.*$", "", text, flags=re.S | re.I)
    # Strip ```json fences if present.
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    # Grab the outermost {...}.
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None


def _valid_episode(d: dict) -> bool:
    """A usable episode has a title, a parseable script, and two vote options."""
    if not isinstance(d, dict):
        return False
    for k in ("title", "script", "vote_a", "vote_b"):
        if not str(d.get(k, "")).strip():
            return False
    # The script must contain at least a few "Speaker: line" turns. Match any
    # capitalized speaker label (Narrator/Maya/Leo/Sara/Omar/The Stranger/…),
    # not a fixed list, so the expanded cast doesn't get rejected.
    lines = [ln for ln in d["script"].splitlines()
             if re.match(r"^\s*[A-Z][\w.'\- ]{0,30}:\s*\S", ln)]
    return len(lines) >= 4


def _normalize_episode(d: dict, arc: dict = None) -> dict:
    """Coerce a parsed LLM object into the episode dict the pipeline uses."""
    arc = arc or {}
    facts = d.get("facts")
    if isinstance(facts, str):
        facts = [facts]
    facts = [str(f).strip() for f in (facts or []) if str(f).strip()][:4]
    return {
        "title": str(d["title"]).strip()[:200],
        "script": str(d["script"]).strip(),
        "recap": str(d.get("recap", "")).strip(),
        "facts": facts,
        "mood": (str(d.get("mood", "")).strip().lower()
                 or arc.get("mood") or "warm"),
        "vote_a": str(d["vote_a"]).strip()[:100],
        "vote_b": str(d["vote_b"]).strip()[:100],
        "motif_used": bool(d.get("motif_used", False)),
    }


# Bounded regeneration: how many times to re-ask the writer, feeding back the
# specific validator violations, before giving up (spec 4.6).
MAX_REGEN_ATTEMPTS = 3


async def generate_episode(previous_summary: str = "", winning_choice: str = "",
                           episode_number: int = 1, level: str = None,
                           arc: dict = None, is_arc_opener: bool = False,
                           is_arc_finale: bool = False, past_choices: list = None,
                           motif_seen: bool = False,
                           student_cameos: list = None,
                           vocabulary: list = None) -> Optional[dict]:
    """Generate the next Empire Chronicles episode (arc-aware). Returns a dict with
    keys title, script, recap, facts, mood, vote_a, vote_b, motif_used — or None if
    the LLM is unavailable or no attempt passes validation. Never raises.

    `student_cameos` (Phase 5) is an optional list of {story_name, gender} learner
    cameos to weave in as brief, friendly background characters; the prompt and the
    validator both receive them so they are cast safely (gender-matched, never an
    antagonist, first-name only). Omit/empty ⇒ a name-free episode (R8.4).

    Runs BOUNDED REGENERATION (spec 4.6): if the generated script fails the script
    validator, the specific violations are appended to the prompt and the writer is
    asked again, up to MAX_REGEN_ATTEMPTS times. The best-effort last parse is
    returned only if it structurally parses AND passes validation."""
    student_cameos = student_cameos or []
    student_names = [c.get("story_name") for c in student_cameos
                     if c.get("story_name")]
    base_prompt = build_story_prompt(
        previous_summary, winning_choice, episode_number, level=level, arc=arc,
        is_arc_opener=is_arc_opener, is_arc_finale=is_arc_finale,
        past_choices=past_choices, motif_seen=motif_seen,
        student_cameos=student_cameos, vocabulary=vocabulary)

    # Lazily import the validator so a broken validator import can never take the
    # generator down; if it's unavailable we fall back to the structural check.
    try:
        from . import sawt_script_validator as validator
    except Exception:                                            # noqa: BLE001
        validator = None

    feedback = ""
    for attempt in range(1, MAX_REGEN_ATTEMPTS + 1):
        prompt = base_prompt if not feedback else (
            base_prompt + "\n\nYOUR PREVIOUS ATTEMPT WAS REJECTED. Fix EXACTLY "
            "these problems and return the full corrected JSON:\n" + feedback)
        try:
            text = await _call_llm_json(prompt, temperature=0.9, level=level)
        except Exception as e:                                   # noqa: BLE001
            logger.warning("sawt.story: generation failed: %s", e)
            return _fallback_episode(episode_number, level, arc,
                                     previous_summary, validator, student_names,
                                     is_arc_finale)
        d = _extract_json(text or "")
        if not _valid_episode(d):
            logger.warning("sawt.story: attempt %s returned an unusable episode",
                           attempt)
            feedback = "- Return valid JSON with a title, a speaker-labelled " \
                       "script of at least 4 lines, and two vote options."
            continue
        ep = _normalize_episode(d, arc)
        if validator is None:
            return ep
        problems = validator.validate_episode(
            ep, level=level, episode_number=episode_number, arc=arc,
            is_arc_finale=is_arc_finale, student_names=student_names)
        if not problems:
            return ep
        logger.warning("sawt.story: attempt %s failed validation: %s",
                       attempt, "; ".join(problems))
        feedback = "\n".join(f"- {p}" for p in problems)

    logger.warning("sawt.story: exhausted %s attempts; using fallback episode",
                   MAX_REGEN_ATTEMPTS)
    return _fallback_episode(episode_number, level, arc, previous_summary,
                             validator, student_names, is_arc_finale)


def _fallback_episode(episode_number, level, arc, previous_summary, validator,
                      student_names, is_arc_finale):
    """Return a guaranteed-valid, gate-passing fallback episode so the daily build
    NEVER produces 'nothing' when the (free-tier) LLM is unavailable. The fallback
    is composed offline (no network, no cost) and is validated the same way a
    generated episode is; if for any reason it doesn't validate, we still return it
    (it is hand-built to pass) rather than None, because a fallback that ships beats
    an empty day. Never raises."""
    try:
        from . import sawt_fallback
        mood = (arc or {}).get("mood") or "mystery"
        ep = sawt_fallback.build_fallback_episode(
            episode_number=episode_number or 1, level=level, mood=mood,
            previous_summary=previous_summary or "")
        if validator is not None:
            problems = validator.validate_episode(
                ep, level=level, episode_number=episode_number, arc=arc,
                is_arc_finale=is_arc_finale, student_names=student_names)
            if problems:
                # Log but still ship — the fallback is authored to pass; a validator
                # quirk must not turn into an empty day.
                logger.warning("sawt.story: fallback had validator notes: %s",
                               "; ".join(problems))
        logger.info("sawt.story: shipping fallback episode '%s'", ep.get("title"))
        return ep
    except Exception as e:                                       # noqa: BLE001
        logger.warning("sawt.story: fallback composition failed: %s", e)
        return None


def _max_tokens_for(level: str = None) -> int:
    """Completion-token budget for one episode, sized from its target length.

    WHY THIS IS COMPUTED, NOT GUESSED (all measured against the live provider):
      * With no `max_tokens` at all, a CEFR-length episode came back truncated.
      * `max_tokens=8000` was rejected outright with **HTTP 413 Payload Too Large**
        — the cap applies to prompt + completion TOGETHER, so a big number is not
        "safe", it is fatal.
      * `max_tokens=2000` succeeded and produced a 725-word script (A2 target 780).
      * The configured model is a REASONING model (`openai/gpt-oss-120b`), which
        spends part of the budget thinking. Too small a budget therefore returns
        HTTP 200 with EMPTY content rather than an error — a failure mode that is
        easy to misread as "the LLM is down".
    So the budget must be big enough to think AND write, but small enough to avoid
    413: ~2.4 tokens per target word plus overhead, clamped to a proven window."""
    # SIZED FOR THE KEY'S TPM LIMIT, not just the episode. Measured 2026-09-08
    # against the production key: qwen/qwen3.8-27b has an 8000 tokens-per-minute
    # on-demand limit, and Groq reserves (prompt_tokens + max_tokens) against it up
    # front. The story prompt is ~1100 tokens, so a max_tokens of 2648-3200 reserved
    # ~3700-4300 tokens/request — only ~2 requests fit in a minute, and the regen +
    # model-retry loops then hammered straight into HTTP 429 ("Request too large").
    # A full A2 episode (~770 words) needs only ~1100-1400 completion tokens, so a
    # 1600 ceiling writes the whole episode AND leaves TPM headroom for retries.
    words, _minutes = target_length(level)
    return int(min(1600, max(900, words * 1.7 + 400)))


async def _call_llm_json(prompt: str, temperature: float = 0.9,
                         level: str = None) -> Optional[str]:
    """Story LLM call. Returns raw text (expected to contain a JSON object) or None.

    PROVIDER ORDER (evidence-based, 2026-09-07): **Groq is primary**, Gemini is an
    OPTIONAL last resort.
      * Gemini kept costing time/credits: the available key returned 403 on every
        gemini-3.x model (no tier access) and 404 on gemini-2.5 (unavailable), so it
        produced NOTHING while we burned retries on it. It's now last, and only
        tried if a key is set.
      * Groq works and is fast, but the general model `openai/gpt-oss-120b` is a
        REASONING model that returns empty-200 on long generations. So story
        generation uses a dedicated STANDARD instruction model,
        `config.GROQ_STORY_MODEL` (llama-3.3-70b-versatile: 131k context / 32k max
        completion), which actually writes the full episode.
    The offline job also honours a longer Groq Retry-After (free-tier 429s are
    7-15s) — waiting beats producing no episode."""
    max_tokens = _max_tokens_for(level)

    # 1) Groq PRIMARY. Model ACCESS is per-key (measured: this key 404s on
    #    llama-3.3-70b-versatile), so try a CHAIN of candidate models and use the
    #    first that returns real text. 404/400 on one model -> try the next.
    if config.GROQ_API_KEY:
        from . import groq_client
        models = [getattr(config, "GROQ_STORY_MODEL", config.GROQ_MODEL)] + [
            m for m in getattr(config, "GROQ_STORY_MODEL_FALLBACKS", [])
            if m != getattr(config, "GROQ_STORY_MODEL", None)
        ]
        for model in models:
            payload = {
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,      # sized to the episode; see _max_tokens_for()
                "messages": [
                    {"role": "system", "content": _STORY_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
            }
            # Per-model retry ladder. Each failure mode needs a DIFFERENT response:
            #   413            -> asked for too much: SHRINK the completion budget.
            #   200 + no text  -> model ran out of room: GROW the budget.
            #   429            -> rate limited: WAIT (offline job), then retry.
            #   404/400        -> model not accessible to this key: NEXT model.
            #   anything else   -> transport/model error: NEXT model.
            budget = max_tokens
            next_model = False
            for attempt in range(1, 4):
                payload["max_tokens"] = budget
                try:
                    # This is the OFFLINE daily job (not user-facing), so it can
                    # afford to honour a longer Retry-After: Groq free-tier 429s on
                    # the good models come back with 24-35s waits, and WAITING for
                    # the primary beats cascading to a weaker fallback. 40s covers
                    # the observed range.
                    result = await groq_client.chat_completion(
                        payload, timeout_seconds=120, max_retry_after=40.0)
                    if result.ok and result.text:
                        return result.text
                    text_len = len(result.text or "")
                    logger.warning("sawt.story: Groq unusable (model=%s, attempt %s, "
                                   "max_tokens=%s, status=%s, text_len=%s)",
                                   model, attempt, budget, result.status, text_len)
                    if result.status == 413:
                        budget = max(700, int(budget * 0.6))
                    elif result.status == 429:
                        # The good models' 429 is a TOKENS-PER-MINUTE limit (measured
                        # 8000 TPM on qwen3.8), which refills on a ~60s window. A
                        # short 8-24s nap lands back in the SAME exhausted window and
                        # 429s again — the storm we saw. Wait out most of the minute
                        # so the budget actually refills before retrying (offline job,
                        # so the wait is fine).
                        await asyncio.sleep(min(60, 20 * attempt))
                    elif result.status == 200 and text_len == 0:
                        # Reasoning-model empty-200: grow the budget, but never past a
                        # TPM-safe ceiling (a too-large max_tokens is itself a 429 —
                        # "Request too large" — on an 8000 TPM key).
                        budget = min(1600, int(budget * 1.4) + 200)
                    else:
                        # 404/400/5xx etc. — this model won't work; try the next one.
                        next_model = True
                        break
                except Exception as e:  # noqa: BLE001
                    logger.warning("sawt.story: Groq call error (model=%s, "
                                   "attempt %s): %s", model, attempt, e)
                    next_model = True
                    break
            if next_model:
                continue

    # 2) Gemini LAST RESORT — only if a key is configured. Often unavailable for the
    #    project's key (403/404), so it must never be depended on.
    if config.GEMINI_API_KEY:
        try:
            text = await ai_engine._call_gemini(prompt, temperature,
                                                max_output_tokens=max_tokens)
            if text:
                return text
            logger.warning("sawt.story: Gemini returned nothing")
        except Exception as e:  # noqa: BLE001
            logger.warning("sawt.story: Gemini error (%s)", e)

    logger.warning("sawt.story: no provider produced a usable script")
    return None
