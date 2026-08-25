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
    """Score the current objective block, branch, and return the next block, the
    writing prompt, or (if writing already done) the final profile."""
    state = database.placement_session_get(discord_id)
    if not state:
        return {"ok": False, "error": "no_session"}
    if state.get("phase") != "vocab":
        return {"ok": False, "error": "not_in_vocab_phase"}

    block = state.get("current_block") or []
    answers = answers or {}
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

    # Vocab settled → resolve its band and move to the writing task.
    vocab_band = placement.resolve_skill_band(state["vocab_blocks"])
    state["skill_bands"]["vocab_grammar"] = vocab_band
    prompt = assessment.get_part_b_prompt(vocab_band)
    state["phase"] = "writing"
    state["current_block"] = None
    state["writing"] = {"band": vocab_band, "prompt": prompt}
    database.placement_session_save(discord_id, state)
    return {"ok": True, "phase": "writing", "band": vocab_band, "prompt": prompt}


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
    state["phase"] = "done"
    database.placement_session_save(discord_id, state)

    result = placement.place_student(discord_id, state["skill_bands"],
                                     slot=False, source="self")
    return {"ok": True, "phase": "done", "writing_score": total,
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
