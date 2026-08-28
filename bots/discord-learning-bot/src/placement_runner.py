"""Mi'yar Phase 8 — CEFR placement RUNNER (the interactive session).

`placement.py` is the pure engine (band arithmetic, the conservative rule,
storage). This module drives a real student session on top of it:

  1. **Vocabulary/Grammar (objective, adaptive):** blocks of multiple-choice
     items drawn per CEFR band. A block's correct-rate branches the next block
     up/down a band (routing to the ability region). Stops when performance
     settles on a band or the block budget is spent → resolves a `vocab_grammar`
     band (highest band actually passed).
  2. **Writing (production):** one typed prompt at the resolved band, rated by
     the AI descriptor-rater (rule-based fallback — no network dependence) →
     resolves a `writing` band.
  3. **Finalise:** the per-skill profile → `placement.conservative_overall` →
     stored result. Slotting is a SEPARATE opt-in step (never forced, R6.3).

Listening & speaking are deferred (they need the audio/Whisper path) and are
documented as a later enhancement — exactly as reading was folded into
vocab/grammar. The profile is honest about which skills it measured.

All state lives server-side in `placement_session` so answers are never sent to
the client. Every function is defensive and never raises to the caller.
"""
import random

from . import assessment, config, database, placement

START_BAND_IDX = 2          # begin probing at B1 (mid-range), then branch
BLOCK_SIZE = 5              # items per objective block
MAX_VOCAB_BLOCKS = 4        # block budget before we resolve the vocab band
WRITING_PASS = 60          # AI total ≥ this → writing holds the probed band


# ── item construction ──

def _mc_block(band: str, pool: dict, rng: random.Random, n: int = BLOCK_SIZE) -> list[dict]:
    """Build a block of `n` multiple-choice items for a band: show the Arabic
    meaning, choose the English word from 4 options. Correct answer kept
    server-side only."""
    items = list(pool.get(band, []))
    rng.shuffle(items)
    all_words = [it.get("word") for b in pool.values() for it in b
                 if it.get("word")]
    all_words = list(dict.fromkeys(all_words))  # de-dup, keep order
    block = []
    for i in range(n):
        if not items:
            break
        v = items[i % len(items)]
        correct = v.get("word", "")
        arabic = v.get("arabic", "")
        if not correct or not arabic:
            continue
        distractors = [w for w in all_words if w != correct]
        rng.shuffle(distractors)
        options = distractors[:3] + [correct]
        rng.shuffle(options)
        block.append({
            "q_id": f"{band}:{i}",
            "prompt_ar": arabic,
            "options": options,
            "answer": correct,   # STRIPPED before sending to the client
        })
    return block


def _client_block(block: list[dict]) -> list[dict]:
    """The block with correct answers removed (safe to send to the browser)."""
    return [{"q_id": it["q_id"], "prompt_ar": it["prompt_ar"],
             "options": it["options"]} for it in block]


LISTEN_BLOCK = 5  # dictation items in the listening probe


def _listening_block(band: str, pool: dict, rng: random.Random,
                     n: int = LISTEN_BLOCK) -> list[dict]:
    """Build a dictation block for a band: the browser speaks `say_en` (via TTS)
    and the student types the word. Auto-scored against `answer`."""
    items = list(pool.get(band, []))
    rng.shuffle(items)
    block = []
    for i in range(n):
        if not items:
            break
        v = items[i % len(items)]
        word = v.get("word", "")
        if not word:
            continue
        block.append({"q_id": f"L{band}:{i}", "say_en": word,
                      "hint_ar": v.get("arabic", ""), "answer": word})
    return block


def _client_listen_block(block: list[dict]) -> list[dict]:
    """Listening block for the browser (keeps say_en for TTS; hides nothing more
    than the vocab block does — placement is opt-in self-assessment)."""
    return [{"q_id": it["q_id"], "say_en": it["say_en"], "hint_ar": it["hint_ar"]}
            for it in block]


# ── Listening comprehension (real broadcast audio + its own questions) ──

MAX_LISTEN_BLOCKS = 3   # adaptive listening budget


def _comprehension_block(band: str, pool: dict) -> list[dict]:
    """Items for a real listening probe at `band`: one clip, its gist question
    plus up to two detail questions. Answers stay server-side.

    Returns [] when the band has no eligible clip, which is the signal to fall
    back to the dictation probe rather than fail the session.
    """
    entry = (pool or {}).get(band)
    if not entry:
        return []
    return [{
        "q_id": f"C{band}:{i}",
        "audio_id": entry["audio_id"],
        "prompt": q["prompt"],
        "options": q["options"],
        "answer": q["answer"],
    } for i, q in enumerate(entry["questions"])]


def _client_comprehension_block(block: list[dict]) -> dict:
    """The comprehension block for the browser, with answers removed.

    `mode` is what lets the page render either probe: older clients that only
    know dictation keep working, and the audio path is additive.
    """
    return {
        "mode": "comprehension",
        "audio_url": f"/audio/{block[0]['audio_id']}.mp3" if block else "",
        "items": [{"q_id": it["q_id"], "prompt": it["prompt"],
                   "options": it["options"]} for it in block],
    }


def _start_listening(state: dict, band: str) -> dict:
    """Move the session into its listening probe at `band`.

    Prefers real comprehension; falls back to dictation so a missing clip can
    never break placement.
    """
    pool = placement.build_listening_pool()
    block = _comprehension_block(band, pool)
    if block:
        state["phase"] = "listening"
        state["listen_mode"] = "comprehension"
        state["listen_band"] = band
        state["listen_band_idx"] = placement.band_index(band)
        state["listen_blocks"] = state.get("listen_blocks") or []
        state["current_block"] = block
        payload = _client_comprehension_block(block)
        return {"ok": True, "phase": "listening", "band": band, **payload}

    rng = random.Random()
    state["phase"] = "listening"
    state["listen_mode"] = "dictation"
    state["listen_band"] = band
    state["current_block"] = _listening_block(
        band, placement.build_placement_pool(), rng)
    return {"ok": True, "phase": "listening", "band": band,
            "mode": "dictation", "block": _client_listen_block(state["current_block"])}


def _band_from_rate(band: str, rate: float) -> str:
    """A single probe block at `band` resolves to that band if passed, else one
    band lower (conservative)."""
    idx = placement.band_index(band)
    return placement.index_to_band(idx if rate >= placement.PLACEMENT_PASS_RATE
                                   else max(0, idx - 1))


# ── session lifecycle ──

def start_session(discord_id: str, seed: str | None = None) -> dict:
    """Begin a placement session and return the first objective block."""
    rng = random.Random(seed or f"plc:{discord_id}:{random.randint(1, 1_000_000)}")
    pool = placement.build_placement_pool()
    band = placement.index_to_band(START_BAND_IDX)
    block = _mc_block(band, pool, rng)
    state = {
        "phase": "vocab",
        "vocab_band_idx": START_BAND_IDX,
        "vocab_blocks": [],
        "blocks_done": 0,
        "current_block": block,
        "skill_bands": {},
        "writing": None,
    }
    database.placement_session_save(discord_id, state)
    return {"ok": True, "phase": "vocab", "band": band,
            "block_no": 1, "block": _client_block(block)}


async def submit_answers(discord_id: str, answers: dict) -> dict:
    """Score the current objective block. Handles both the adaptive VOCAB phase
    and the LISTENING (dictation) phase; advances the session accordingly."""
    state = database.placement_session_get(discord_id)
    if not state:
        return {"ok": False, "error": "no_session"}
    phase = state.get("phase")
    answers = answers or {}
    if phase == "vocab":
        return _advance_vocab(discord_id, state, answers)
    if phase == "listening":
        return _advance_listening(discord_id, state, answers)
    return {"ok": False, "error": f"not_answerable_phase:{phase}"}


def _advance_vocab(discord_id: str, state: dict, answers: dict) -> dict:
    block = state.get("current_block") or []
    correct = sum(1 for it in block if answers.get(it["q_id"]) == it["answer"])
    rate = (correct / len(block)) if block else 0.0
    cur_idx = state["vocab_band_idx"]
    band = placement.index_to_band(cur_idx)
    state["vocab_blocks"].append({"band": band, "correct_rate": round(rate, 3)})
    state["blocks_done"] += 1

    nxt_idx = placement.step_band(cur_idx, rate)
    settled = nxt_idx == cur_idx
    out_of_budget = state["blocks_done"] >= MAX_VOCAB_BLOCKS

    if not settled and not out_of_budget:
        rng = random.Random()
        pool = placement.build_placement_pool()
        nxt_band = placement.index_to_band(nxt_idx)
        state["vocab_band_idx"] = nxt_idx
        state["current_block"] = _mc_block(nxt_band, pool, rng)
        database.placement_session_save(discord_id, state)
        return {"ok": True, "phase": "vocab", "band": nxt_band,
                "block_no": state["blocks_done"] + 1,
                "block": _client_block(state["current_block"])}

    # Vocab settled → resolve its band, then probe LISTENING at that band.
    vocab_band = placement.resolve_skill_band(state["vocab_blocks"])
    state["skill_bands"]["vocab_grammar"] = vocab_band
    out = _start_listening(state, vocab_band)
    database.placement_session_save(discord_id, state)
    return out


def _advance_listening(discord_id: str, state: dict, answers: dict) -> dict:
    """Score the listening probe.

    Comprehension probes BRANCH like the vocab phase, because listening was
    previously a single block pinned at the vocab band — so a student with strong
    listening and weaker vocabulary could never be measured above it. Dictation
    (the fallback) keeps its original single-block behaviour.
    """
    block = state.get("current_block") or []
    mode = state.get("listen_mode", "dictation")

    if mode == "comprehension":
        correct = sum(1 for it in block
                      if answers.get(it["q_id"]) == it["answer"])
        rate = (correct / len(block)) if block else 0.0
        cur_idx = state.get("listen_band_idx", placement.band_index(
            state.get("listen_band", "A1")))
        band = placement.index_to_band(cur_idx)
        state["listen_blocks"] = (state.get("listen_blocks") or [])
        state["listen_blocks"].append({"band": band, "correct_rate": round(rate, 3)})

        nxt_idx = placement.step_band(cur_idx, rate)
        settled = nxt_idx == cur_idx
        out_of_budget = len(state["listen_blocks"]) >= MAX_LISTEN_BLOCKS

        if not settled and not out_of_budget:
            nxt_band = placement.index_to_band(nxt_idx)
            nxt_block = _comprehension_block(nxt_band, placement.build_listening_pool())
            if nxt_block:
                state["listen_band_idx"] = nxt_idx
                state["listen_band"] = nxt_band
                state["current_block"] = nxt_block
                database.placement_session_save(discord_id, state)
                return {"ok": True, "phase": "listening", "band": nxt_band,
                        **_client_comprehension_block(nxt_block)}
        # settled, out of budget, or no clip one band over → resolve
        state["skill_bands"]["listening"] = placement.resolve_skill_band(
            state["listen_blocks"])
    else:
        correct = sum(1 for it in block
                      if assessment._forgiving_equal(answers.get(it["q_id"], ""),
                                                     it["answer"]))
        rate = (correct / len(block)) if block else 0.0
        band = state.get("listen_band",
                         placement.index_to_band(state["vocab_band_idx"]))
        state["skill_bands"]["listening"] = _band_from_rate(band, rate)

    # → writing task at the vocab band (writing is probed at the objective band,
    #   not the listening band, so a strong listener is not handed a harder
    #   writing task than their measured language supports)
    band = placement.index_to_band(state["vocab_band_idx"])
    prompt = assessment.get_part_b_prompt(band)
    state["phase"] = "writing"
    state["current_block"] = None
    state["writing"] = {"band": band, "prompt": prompt}
    database.placement_session_save(discord_id, state)
    return {"ok": True, "phase": "writing", "band": band, "prompt": prompt}


async def submit_writing(discord_id: str, text: str) -> dict:
    """Rate the typed writing sample against the band's descriptors and finalise
    the placement (stores the result; does NOT slot — that is a separate opt-in)."""
    state = database.placement_session_get(discord_id)
    if not state or state.get("phase") != "writing":
        return {"ok": False, "error": "no_writing_phase"}
    band = state["writing"]["band"]
    score = await assessment.rate_part_b(text or "", band, state["writing"].get("prompt"))
    total = score.get("total", 0)
    idx = placement.band_index(band)
    writing_idx = idx if total >= WRITING_PASS else max(0, idx - 1)
    state["skill_bands"]["writing"] = placement.index_to_band(writing_idx)
    # → speaking task (final skill) at the same band.
    #
    # Uses a SPEAKING prompt, not `get_part_b_prompt` (the writing generator).
    # Asking a student to speak a writing task measured the wrong thing: these
    # ask for spoken performance matching the band's production descriptors.
    sp_prompt = placement.speaking_prompt(band)
    state["phase"] = "speaking"
    state["speaking"] = {"band": band, "prompt": sp_prompt}
    database.placement_session_save(discord_id, state)
    return {"ok": True, "phase": "speaking", "band": band,
            "prompt": sp_prompt, "writing_score": total}


async def submit_speaking(discord_id: str, transcript: str) -> dict:
    """Rate the spoken response (already transcribed) against the band's
    descriptors and FINALISE the placement — the 4th and last skill. Stores the
    result; does NOT slot (separate opt-in). If the transcript is empty (STT
    failed / no audio), speaking is skipped and the profile finalises on the
    other three skills."""
    state = database.placement_session_get(discord_id)
    if not state or state.get("phase") != "speaking":
        return {"ok": False, "error": "no_speaking_phase"}
    band = state["speaking"]["band"]
    total = 0
    if transcript and len(transcript.split()) >= 3:
        score = await assessment.rate_part_b(transcript, band, state["speaking"].get("prompt"))
        total = score.get("total", 0)
        idx = placement.band_index(band)
        sp_idx = idx if total >= WRITING_PASS else max(0, idx - 1)
        state["skill_bands"]["speaking"] = placement.index_to_band(sp_idx)
    state["phase"] = "done"
    database.placement_session_save(discord_id, state)

    result = placement.place_student(discord_id, state["skill_bands"],
                                     slot=False, source="self")
    return {"ok": True, "phase": "done", "speaking_score": total,
            "measured_skills": list(state["skill_bands"].keys()), **result}


def slot_student(discord_id: str) -> dict:
    """Opt-in: actually place the student at their result level (week 1) and end
    the session. Requires a finished placement result."""
    latest = database.latest_placement_result(discord_id)
    if not latest:
        return {"ok": False, "error": "no_result"}
    level = latest["overall_level"]
    database.set_level(discord_id, level)          # stamps a week-1 calendar anchor
    database.placement_session_clear(discord_id)
    return {"ok": True, "slotted": True, "level": level,
            "level_name": config.level_info(level).get("name", level)}
