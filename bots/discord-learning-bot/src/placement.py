"""Mi'yar Phase 8 — CEFR placement (self-contained, criterion-referenced).

Design (see .kiro/specs/cefr-curriculum/design.md → Phase 8, and
content/cefr/PHASE8-ASSESSMENT-ALIGNMENT.md §7):

  * Placement produces a PER-SKILL CEFR profile, not one number — CEFR is
    skill-differentiated and collapsing it to a single score is a known misuse.
  * It is adaptive by BRANCHING: probe at a band, and the running correct-rate
    steps the next block up/down one band (the IRT routing idea, without
    claiming empirical calibration we cannot support at n=17).
  * The OVERALL level is deliberately CONSERVATIVE — a student is slotted where
    they can succeed, never at the ceiling of their range. A well-placed student
    who advances fast is a far better outcome than a mis-placed one who stalls.

This module is PURE engine + storage. The interactive item-serving runner and
the API/command surface are wired separately (they touch api_server/bot.py).
Everything stays inert until placement is offered; it never force-retests
current students (requirement R6.3).
"""
from statistics import mean

from . import config, curriculum, database

# A skill "passes" a band if the student answers at least this fraction right.
PLACEMENT_PASS_RATE = 0.60
# Branching thresholds: step up when strong, down when weak, else hold.
_STEP_UP_RATE = 0.80
_STEP_DOWN_RATE = 0.40
# The four CEFR skill modes we profile. Reading is folded into vocab/grammar
# for now (documented as a later enhancement).
PLACEMENT_SKILLS = ("vocab_grammar", "listening", "writing", "speaking")


# ── Band arithmetic (CEFR or legacy key in; CEFR level out) ──

def band_index(level: str) -> int:
    """0-based index of a level in CEFR_ORDER (A1=0 … C2=5). Accepts legacy keys."""
    ck = config.cefr_key(level)
    return config.CEFR_ORDER.index(ck) if ck in config.CEFR_ORDER else 0


def index_to_band(idx: int) -> str:
    """Clamp an index into [A1, C2] and return the CEFR level."""
    idx = max(0, min(len(config.CEFR_ORDER) - 1, int(idx)))
    return config.CEFR_ORDER[idx]


def step_band(current_idx: int, correct_rate: float) -> int:
    """Adaptive routing: strong performance steps up a band, weak steps down,
    middling holds. Clamped to the CEFR range."""
    if correct_rate >= _STEP_UP_RATE:
        current_idx += 1
    elif correct_rate <= _STEP_DOWN_RATE:
        current_idx -= 1
    return max(0, min(len(config.CEFR_ORDER) - 1, current_idx))


def resolve_skill_band(blocks: list[dict]) -> str:
    """Resolve one skill to a CEFR band from its probe blocks.

    `blocks` is an ordered list of {band, correct_rate} the runner recorded. The
    resolved band is the HIGHEST band the student actually passed
    (correct_rate ≥ PLACEMENT_PASS_RATE); if they passed none, the lowest band
    probed. Highest-passed (not highest-attempted) keeps placement honest: being
    shown a hard item is not evidence you can do it."""
    if not blocks:
        return config.CEFR_ORDER[0]
    passed = [b for b in blocks if b.get("correct_rate", 0) >= PLACEMENT_PASS_RATE]
    if passed:
        return index_to_band(max(band_index(b["band"]) for b in passed))
    return index_to_band(min(band_index(b["band"]) for b in blocks))


# ── The conservative overall rule (the heart of R6) ──

def conservative_overall(skill_bands: dict) -> str:
    """Combine a per-skill CEFR profile into a single placement level.

    Rule: the LOWER of
      (a) the rounded mean of the skill bands, and
      (b) one band above the weakest skill (min + 1).
    (a) stops one strong skill from over-placing; (b) stops one weak skill from
    trapping an otherwise-capable student at the floor. The lower of the two is
    the conservative choice — start where they can succeed."""
    if not skill_bands:
        return config.CEFR_ORDER[0]
    idxs = [band_index(b) for b in skill_bands.values()]
    mean_idx = round(mean(idxs))
    min_plus_one = min(idxs) + 1
    return index_to_band(min(mean_idx, min_plus_one))


# ── Item pool (objective skills drawn from the curriculum) ──

def build_placement_pool(per_band: int = 5) -> dict:
    """Draw objective placement items per CEFR band from the curriculum vocab, so
    the runner has a bank to probe with. Returns {band: [items]}.

    Uses a representative early + mid week per level so items reflect that band's
    difficulty. Pure data assembly — no scoring, no state."""
    curriculum.load_all()
    pool: dict[str, list] = {}
    for band in config.CEFR_ORDER:
        max_wk = curriculum.CEFR_WEEK_COUNTS.get(band, 0)
        items: list = []
        for wk in {1, max(1, max_wk // 2), max_wk}:
            if wk:
                items.extend(curriculum.get_vocabulary_for_week(wk, band) or [])
        # de-dup by word, cap
        seen, uniq = set(), []
        for it in items:
            w = (it.get("word") or "").lower()
            if w and w not in seen:
                seen.add(w)
                uniq.append(it)
        pool[band] = uniq[: max(per_band, 8)]
    return pool


# ── Orchestrator: record a completed placement, optionally slot ──

def place_student(discord_id: str, skill_bands: dict, *, slot: bool = False,
                  source: str = "self") -> dict:
    """Persist a completed placement and (optionally, opt-in) slot the student.

    Returns {overall_level, recommended_week, skill_bands, slotted}. Slotting is
    OFF by default and is never applied to a student who did not choose to place
    (R6.3). Slotting sends them to week 1 of the placed level (R6.2)."""
    overall = conservative_overall(skill_bands)
    recommended_week = 1
    database.save_placement_result(discord_id, overall, skill_bands,
                                   recommended_week=recommended_week, source=source)
    slotted = False
    if slot:
        database.set_level(discord_id, overall)  # stamps week-1 calendar anchor
        slotted = True
    return {
        "overall_level": overall,
        "level_name": config.level_info(overall).get("name", overall),
        "recommended_week": recommended_week,
        "skill_bands": skill_bands,
        "slotted": slotted,
    }
