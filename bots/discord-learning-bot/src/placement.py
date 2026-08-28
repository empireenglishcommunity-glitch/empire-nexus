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

# ── Speaking prompts, one per band ──
#
# Speaking used to reuse `assessment.get_part_b_prompt(band)` — the WRITING
# prompt generator — so a student was asked to *speak* a writing task. These ask
# for spoken performance matching each band's own production descriptors, which
# is what a speaking band is supposed to measure.
# Shape deliberately mirrors `assessment._PART_B_PROMPTS` (prompt_en, prompt_ar,
# duration_sec, prep_time_sec, descriptors) so every existing consumer — the
# placement page's speaking view and the descriptor rater — works unchanged.
SPEAKING_PROMPTS = {
    "A1": {
        "prompt_en": ("Record yourself for about 60 seconds. Say your name, where "
                      "you live, and three things about your family. Short, simple "
                      "sentences are fine."),
        "prompt_ar": ("سجّل نفسك حوالي ٦٠ ثانية. قول اسمك، وإنت ساكن فين، وتلات "
                      "حاجات عن عيلتك. جمل قصيرة وبسيطة كفاية."),
        "duration_sec": 60, "prep_time_sec": 60,
        "descriptors": ["A1.P.1", "A1.P.2"],
    },
    "A2": {
        "prompt_en": ("Record yourself for about 60 seconds. Describe what you did "
                      "last weekend, then say what you plan to do next weekend."),
        "prompt_ar": ("سجّل نفسك حوالي ٦٠ ثانية. اوصف عملت إيه نهاية الأسبوع اللي "
                      "فات، وبعدين قول بتخطّط لإيه نهاية الأسبوع الجاي."),
        "duration_sec": 60, "prep_time_sec": 60,
        "descriptors": ["A2.P.1", "A2.P.2"],
    },
    "B1": {
        "prompt_en": ("Record yourself for about 90 seconds. Tell the story of a "
                      "time something went wrong for you, and explain what you "
                      "learned from it."),
        "prompt_ar": ("سجّل نفسك حوالي ٩٠ ثانية. احكي قصة مرة حصلت لك مشكلة، "
                      "واشرح إيه اللي اتعلمته منها."),
        "duration_sec": 90, "prep_time_sec": 60,
        "descriptors": ["B1.P.1", "B1.P.3"],
    },
    "B2": {
        "prompt_en": ("Record yourself for about 90 seconds. Give your opinion on "
                      "whether students should study online or in a classroom. Give "
                      "reasons, and say what someone who disagrees would argue."),
        "prompt_ar": ("سجّل نفسك حوالي ٩٠ ثانية. قول رأيك: الطلبة يدرسوا أونلاين "
                      "ولا في فصل؟ اذكر أسبابك، وقول إيه اللي هيقوله حد مخالف لرأيك."),
        "duration_sec": 90, "prep_time_sec": 90,
        "descriptors": ["B2.P.1", "B2.P.3"],
    },
    "C1": {
        "prompt_en": ("Record yourself for about 2 minutes. Argue a position on "
                      "this: 'Measuring something changes how people behave.' "
                      "Develop your argument, and concede the strongest point "
                      "against you."),
        "prompt_ar": ("سجّل نفسك حوالي دقيقتين. ادعم موقفًا في الجملة دي: «قياس أي "
                      "حاجة بيغيّر سلوك الناس». طوّر حجتك، واعترف بأقوى نقطة ضدّك."),
        "duration_sec": 120, "prep_time_sec": 90,
        "descriptors": ["C1.P.1", "C1.P.3"],
    },
    "C2": {
        "prompt_en": ("Record yourself for about 2 minutes. Brief a hostile "
                      "audience on a decision you disagree with but must defend. Be "
                      "precise, and make your own reservation clear without "
                      "undermining the decision."),
        "prompt_ar": ("سجّل نفسك حوالي دقيقتين. اشرح لجمهور معادي قرارًا إنت مش "
                      "مقتنع بيه لكن لازم تدافع عنه. كون دقيقًا، ووضّح تحفّظك من "
                      "غير ما تهدّ القرار."),
        "duration_sec": 120, "prep_time_sec": 90,
        "descriptors": ["C2.P.1", "C2.P.4"],
    },
}


def speaking_prompt(level: str) -> dict:
    """The speaking prompt for a band, in the same shape as a Part B prompt.

    Placement used to hand the student `assessment.get_part_b_prompt(band)` — the
    WRITING prompt — for the speaking task, so it measured the wrong skill.
    """
    return SPEAKING_PROMPTS.get(config.cefr_key(level), SPEAKING_PROMPTS["A1"])


# ── Listening pool (real broadcast comprehension, not word dictation) ──

def build_listening_pool() -> dict:
    """{band: {audio_id, week, questions:[{prompt, options, answer}]}} for a real
    listening-comprehension probe.

    Placement used to measure listening with five single-word dictations spoken by
    browser TTS. That tests word recognition, not comprehension, and it barely
    discriminates: a B1 and a C1 student both type "important" correctly, so the
    top of the range was effectively unmeasured.

    This uses the programme's own extended-listening content instead — already
    authored, human-approved, and rendered at each level's verified delivery pace
    (A1 124 wpm … C2 199 wpm), so the probe is level-appropriate by construction.

    Only SINGLE-SEGMENT scripts are eligible: one audio file is then the whole
    script, so the gist question is fair after a single listen. Multi-voice scripts
    span several clips and would need all of them played to be answerable.

    The shortest eligible script per band is chosen to keep placement short, and
    each yields its gist question plus up to two detail questions — three items
    from one listen, which is far more reliable than a single MCQ.
    """
    curriculum.load_all()
    pool: dict[str, dict] = {}
    for band in config.CEFR_ORDER:
        best = None
        for wk in range(1, (curriculum.CEFR_WEEK_COUNTS.get(band, 0) or 0) + 1):
            bc = curriculum.get_broadcast_for_week(wk, band)
            if not bc:
                continue
            segs = bc.get("segments") or []
            gist = bc.get("gist_question") or {}
            details = bc.get("questions") or []
            if len(segs) != 1 or not gist.get("options") or len(details) < 2:
                continue
            wc = bc.get("word_count") or len((segs[0].get("text") or "").split())
            if best is None or wc < best[0]:
                best = (wc, wk, bc)
        if not best:
            continue
        _, wk, bc = best
        items = []
        for q in [bc["gist_question"]] + list(bc.get("questions") or [])[:2]:
            opts = list(q.get("options") or [])
            ans = q.get("answer")
            if not opts or not isinstance(ans, int) or not (0 <= ans < len(opts)):
                continue
            items.append({"prompt": q.get("q", ""), "options": opts,
                          "answer": opts[ans]})
        if not items:
            continue
        pool[band] = {
            "audio_id": f"{band.lower()}-w{wk}-bc0",
            "week": wk,
            "title": bc.get("title", ""),
            "questions": items,
        }
    return pool


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
