"""Masar (مسار) — Personal Growth Narrative Engine.

One shared module that turns a student's existing, already-collected
data (memories, milestones, pronunciation trend, SRS state, difficulty
level, streak, recent conversation themes) into a single "signals"
snapshot, and then into Nour-voiced, personal text for three surfaces:

  - The Weekly Growth Letter (M2, fixes D020 — the AI tips engine that
    was designed but never actually built)
  - Milestone unlock moments (M3, optional)
  - Adaptive difficulty change notes (M4, optional)

Plus one pure-computation helper, `momentum_score()` (M1, fixes D012 —
the dashboard's XP bar and level badge measuring two unrelated things).

Design principle (per .kiro/specs/masar/design.md, Component 1):
`gather_signals()` is the ONE place that knows how to read "everything
about this student." Every feature below reads the SAME snapshot,
rather than each re-querying slightly differently. `gather_signals()`
itself makes NO AI calls — it is pure data-gathering, deterministic,
and unit-testable on its own. This is the exact gap D020 had: no
generation function existed at all, so nobody could ever prove the
"AI-generated weekly tips" claim was false until Hisn found it by
accident. Testability from day one is the whole point of this module.

AI Provider Strategy (identical pattern to nour_concierge.py's proven
Groq→Gemini→template fallback, confirmed working in Hisn H4.1):
  1. Groq (Llama 3.3 70B) — PRIMARY
  2. Gemini — FALLBACK (if Groq fails)
  3. Template, built from real `signals` data — LAST RESORT (never
     silence, and unlike a generic "no letter today" string, this
     fallback is itself personal — it just isn't AI-phrased).

M0.2 note: `build_growth_letter()`, `build_milestone_moment()`, and
`build_difficulty_note()` are stub bodies in this file for now — they
wire the fallback chain correctly and return real (if generic-for-now)
text, but their full Nour-voiced prompts are built out in M2/M3/M4
respectively. The CONTRACT that matters at this phase is: never return
None, always go through the same three-tier fallback, and be live-
tested (Groq-fail/Gemini-succeed, both-fail) before anything is built
on top of them — exactly the discipline D020's engine never had.
"""
import datetime
import logging
import random
from typing import Optional

import aiohttp

from . import config, database

logger = logging.getLogger("empire-bot.narrative")

# ============================================================
#  CONFIGURATION
# ============================================================

MAX_RESPONSE_TOKENS = 300

# Reuse Nour's exact established voice (do not invent a new one, per
# requirements.md's constraint on R3). Imported lazily inside functions
# that need it, to avoid a module-load-time circular import between
# narrative_engine and nour_concierge (both import database; neither
# needs to import the other at import time).


# ============================================================
#  COMPONENT 1 — gather_signals() — pure data gathering, no AI
# ============================================================

def gather_signals(discord_id: str) -> dict:
    """Pull together everything Masar's features need about one
    student, from tables that already exist in this codebase. Makes
    NO AI calls. Every `build_*` function below is called with this
    dict's output, so every feature reads the same snapshot.

    Returns a dict with keys:
        memories, milestones_recent, pronunciation_trend, srs_state,
        difficulty_level, streak, longest_streak, level, week,
        total_points, tasks_today_count, completion_rate_7d,
        conversation_themes, discord_name
    """
    member = database.get_member(discord_id)
    if not member:
        # Caller's responsibility to check for this — gather_signals()
        # itself stays a pure function, no exception-as-control-flow.
        return {}

    from . import nour_personality

    memories = nour_personality.get_memories(discord_id, limit=5)
    milestones_recent = _get_recent_milestones(discord_id, days=14)
    pronunciation_trend = database._get_pronunciation_stats(discord_id)
    srs_state = database.get_srs_stats(discord_id)
    conversation_themes = _summarize_conversation_themes(discord_id)

    from . import tasks as tasks_module

    return {
        "discord_id": discord_id,
        "discord_name": member.get("discord_name", "").split("#")[0],
        "level": member.get("level", "L0"),
        "week": database.member_week_number(discord_id),
        "total_points": member.get("total_points", 0),
        "streak": member.get("current_streak", 0),
        "longest_streak": member.get("longest_streak", 0),
        "difficulty_level": member.get("difficulty_level", 2),
        "tasks_today_count": len(database.tasks_completed_today(discord_id)),
        "completion_rate_7d": tasks_module.calculate_completion_rate(discord_id, days=7),
        "memories": memories,
        "milestones_recent": milestones_recent,
        "pronunciation_trend": pronunciation_trend,
        "srs_state": srs_state,
        "conversation_themes": conversation_themes,
    }


def _get_recent_milestones(discord_id: str, days: int = 14) -> list[dict]:
    """Recent ability milestones signal for the growth letter.

    The ability-milestones feature was removed, so there is no longer a
    source table to query. The signature and call sites are kept intact
    so the growth letter still builds cleanly — it simply has no
    milestones to report, and every downstream consumer already handles
    an empty list gracefully.
    """
    return []


def _summarize_conversation_themes(discord_id: str, limit: int = 8) -> list[str]:
    """Plain extraction of recent nour_conversations themes — NOT an
    AI summary. Keeping gather_signals() itself free of any AI call
    (only the build_* functions call AI) makes it deterministic,
    fast, and unit-testable without network access — the same
    property that made D012's momentum_score() testable per M1.1.

    Returns a short list of student-side message snippets (the
    'intent' field when set, otherwise a truncated snippet of the
    message itself) — raw material for a prompt, not a finished
    summary.
    """
    history = database.get_recent_conversation(discord_id, limit=limit)
    themes = []
    for h in history:
        if h.get("role") != "student":
            continue
        intent = (h.get("intent") or "").strip()
        if intent and intent != "escalation":
            themes.append(intent)
        else:
            snippet = h.get("message", "").strip()[:80]
            if snippet:
                themes.append(snippet)
    return themes


# ============================================================
#  COMPONENT 3 — momentum_score() — pure computation, no AI (M1)
# ============================================================

def momentum_score(discord_id: str) -> dict:
    """A single, honestly-computed 'how am I doing lately' signal.

    Deterministic, no AI call, fast enough to compute live on every
    API/!progress call (per design.md's Component 3). Reads
    gather_signals()'s output rather than re-querying tables directly,
    so this and every other Masar feature always agree on the same
    underlying facts about a student at a given moment (R2's
    dashboard/!progress consistency requirement).

    Returns: {"score": int 0-100, "label": str, "basis": str}
    """
    signals = gather_signals(discord_id)
    if not signals:
        return {"score": 0, "label": "restarting", "basis": "no data"}

    streak_component = min(signals["streak"] / 7, 1.0) * 40
    completion_component = min(signals["completion_rate_7d"] / 100, 1.0) * 40

    trend = signals["pronunciation_trend"].get("trend", "no_data")
    trend_component = {
        "improving": 20.0,
        "stable": 10.0,
        "declining": 0.0,
        "no_data": 10.0,
    }.get(trend, 10.0)

    score = round(streak_component + completion_component + trend_component)
    score = max(0, min(100, score))

    if score < 25:
        label = "restarting"
    elif score < 50:
        label = "building"
    elif score < 75:
        label = "steady"
    else:
        label = "strong"

    return {
        "score": score,
        "label": label,
        "basis": "7-day streak + task completion + pronunciation trend",
    }


# ============================================================
#  AI CHAIN — Groq -> Gemini -> template (never returns None)
#  Same proven pattern as nour_concierge._generate_response(),
#  parameterized so all 3 build_* functions below share ONE
#  implementation instead of each re-inventing fallback logic.
# ============================================================

async def _call_groq(system_prompt: str, user_prompt: str,
                      temperature: float = 0.7) -> Optional[str]:
    """Primary provider. Identical request shape to nour_concierge's
    proven Groq call — same timeout, same failure tracking."""
    if not config.GROQ_API_KEY:
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
    }
    payload = {
        "model": config.GROQ_MODEL,
        "temperature": temperature,
        "max_tokens": MAX_RESPONSE_TOKENS,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.warning(f"Groq API error for narrative_engine: {resp.status}")
                    from . import ops_monitoring
                    import asyncio
                    asyncio.create_task(ops_monitoring.track_groq_failure())
                    return None
                data = await resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return text.strip() if text else None
    except Exception as e:
        logger.error(f"Groq call failed for narrative_engine: {e}")
        from . import ops_monitoring
        import asyncio
        asyncio.create_task(ops_monitoring.track_groq_failure())
        return None


async def _call_gemini(system_prompt: str, user_prompt: str,
                        temperature: float = 0.7) -> Optional[str]:
    """Fallback provider. Identical request shape to nour_concierge's
    proven Gemini call."""
    if not config.GEMINI_API_KEY:
        return None

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": MAX_RESPONSE_TOKENS},
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    logger.warning(f"Gemini API error for narrative_engine: {resp.status}")
                    return None
                data = await resp.json()
                text = (data.get("candidates", [{}])[0]
                        .get("content", {}).get("parts", [{}])[0].get("text", ""))
                return text.strip() if text else None
    except Exception as e:
        logger.error(f"Gemini call failed for narrative_engine: {e}")
        return None


def _clean_ai_text(text: str) -> str:
    """Same artifact-cleanup as nour_concierge._clean_response()."""
    text = text.strip().strip('"').strip("'")
    if text.lower().startswith("nour:"):
        text = text[5:].strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return text


# Masar D033 fix: character ranges for scripts that should NEVER
# appear in Nour's output (which is always Arabic, with occasional
# English words/level names). Found live during Masar M3's testing:
# a Groq response contained a stray Vietnamese word fragment ("đặc")
# mid-sentence -- a real token-hallucination glitch, not a typo --
# and nothing anywhere in this codebase ever checked AI output for
# this class of problem before sending it to a student. This is a
# deliberately narrow blocklist (scripts that have no legitimate
# reason to appear), not a broad "must be X% Arabic" heuristic that
# could false-positive on legitimate English words/numbers/emoji.
_UNEXPECTED_SCRIPT_RANGES = [
    (0x1E00, 0x1EFF),   # Latin Extended Additional (Vietnamese diacritics)
    (0x0900, 0x097F),   # Devanagari (Hindi etc.)
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs (Chinese/Japanese)
    (0x3040, 0x30FF),   # Japanese Hiragana/Katakana
    (0xAC00, 0xD7AF),   # Hangul (Korean)
    (0x0400, 0x04FF),   # Cyrillic
]


def _has_unexpected_script(text: str) -> bool:
    """True if `text` contains any character from a script that has
    no legitimate reason to appear in Nour's Arabic/English output.
    Used to catch AI hallucination glitches (a stray foreign-language
    fragment mid-sentence) before they ever reach a student, treating
    them as a failed generation rather than sending garbled text."""
    for ch in text:
        code = ord(ch)
        for start, end in _UNEXPECTED_SCRIPT_RANGES:
            if start <= code <= end:
                return True
    return False


# Masar D035 fix (follow-up to D033): a curated blocklist of common
# short foreign words that use ONLY shared Latin-1/ASCII characters —
# these can't be caught by _UNEXPECTED_SCRIPT_RANGES above, since they
# don't contain any character exclusive to a non-Latin/Vietnamese-
# specific script. Found live during Masar M4's testing: a Groq
# response contained "cùng" (Vietnamese for "together"), which uses
# only `ù` (U+00F9, ordinary Latin-1 Supplement — the SAME block used
# by legitimate French/Portuguese/Spanish accented words and names),
# so the existing guard missed it entirely.
#
# Deliberately a SMALL, curated list of actual words observed (or
# closely related to words observed) hallucinating into Nour's output,
# NOT a broad "reject all Latin-1 accented text" rule — that would
# false-positive on legitimate loanwords/names (café, naïve, José,
# etc.). This list is expected to grow over time as new hallucinated
# words are caught live; it is inherently incomplete by nature (see
# D035's defect_log.md entry for the full tradeoff discussion), but is
# a real, low-cost improvement over having nothing at all for this
# sub-class of leak.
_BLOCKED_FOREIGN_WORDS = {
    # Vietnamese words actually observed (or closely related to
    # observed) leaking into AI output during D033/D035's live testing:
    "đặc", "cùng", "được", "của", "không", "người", "những", "với",
    "này", "đã", "sẽ", "và", "là", "có", "một", "các", "để", "khi",
    "làm", "rất", "cũng", "còn", "nào", "vì", "nếu", "nên",
}


def _has_blocked_foreign_word(text: str) -> bool:
    """True if `text` contains any whole word from `_BLOCKED_FOREIGN_WORDS`
    (case-insensitive, word-boundary matched — not a substring check,
    to avoid ever flagging a blocked word that merely appears inside a
    longer legitimate word). See `_BLOCKED_FOREIGN_WORDS`'s comment for
    why this exists as a separate, narrower check from
    `_has_unexpected_script()` above.
    """
    import re
    words = re.findall(r"[^\s\d.,!?;:()\"'،؟]+", text.lower())
    return any(w in _BLOCKED_FOREIGN_WORDS for w in words)


async def _generate_with_fallback(system_prompt: str, user_prompt: str,
                                   template_fallback_fn) -> tuple[str, str]:
    """Shared 3-tier fallback used by every build_* function below.

    Returns (text, source) where source is "ai" or "template_fallback"
    — callers that persist a letter (e.g. M2's nour_growth_letters
    table) can record which path produced it, per design.md's schema.

    `template_fallback_fn` is a zero-arg callable that returns a
    signals-based (not generic) string — it is called ONLY if both AI
    providers fail, and it must never return None/empty (enforced by
    a final guard below, so this function itself never returns None
    even if a caller's fallback function has a bug).

    Masar D033 fix: a response containing an unexpected foreign
    script (see _has_unexpected_script()) is now treated as a FAILED
    generation, exactly like an empty/None response — it falls
    through to the next provider, and ultimately to the template
    fallback, rather than ever being sent to a student. Found live
    during Masar M3's testing (a Vietnamese fragment leaked into an
    otherwise-Arabic Groq response); this same class of bug could
    recur in nour_concierge's regular chat responses too, but fixing
    that call site is out of this defect's immediate scope -- flagged
    separately in defect_log.md.

    Masar D035 fix: ALSO reject a response containing a known blocked
    foreign word (see _has_blocked_foreign_word()) -- catches the
    narrower sub-class _has_unexpected_script() can't, where the
    hallucinated word uses only shared Latin-1 characters (e.g.
    "cùng").
    """
    def _is_bad(t: str) -> bool:
        return _has_unexpected_script(t) or _has_blocked_foreign_word(t)

    text = await _call_groq(system_prompt, user_prompt)
    if text and not _is_bad(text):
        return _clean_ai_text(text), "ai"
    if text:
        logger.warning(
            "narrative_engine: Groq response contained an unexpected "
            "script or blocked foreign word, discarding and trying "
            "Gemini fallback"
        )

    logger.info("narrative_engine: Groq failed, trying Gemini fallback")
    text = await _call_gemini(system_prompt, user_prompt)
    if text and not _is_bad(text):
        return _clean_ai_text(text), "ai"
    if text:
        logger.warning(
            "narrative_engine: Gemini response ALSO contained an "
            "unexpected script or blocked foreign word, discarding and "
            "using template fallback"
        )

    logger.warning("narrative_engine: both AI providers failed, using template fallback")
    fallback_text = template_fallback_fn()
    if not fallback_text:
        # Guard against a broken template function — this class of bug
        # (a fallback path that silently produces nothing) is exactly
        # what made D020 invisible; never let it happen here even by
        # accident.
        fallback_text = "احنا فاكرينك! خد وقتك وكمل شوية شوية 😊"
    return fallback_text, "template_fallback"


# ============================================================
#  COMPONENT 1 (cont'd) — build_* functions (M0.2: stub bodies,
#  full Nour-voiced prompts land in M2/M3/M4)
# ============================================================

def _nour_voice_system_prompt() -> str:
    """Reuse Nour's exact established personality, not a new voice
    (per requirements.md's R3 constraint). Imported lazily to avoid a
    module-load-time circular import with nour_concierge."""
    from . import nour_concierge
    return nour_concierge.NOUR_SYSTEM_PROMPT


async def build_growth_letter(signals: dict) -> tuple[str, str]:
    """M2.1: Nour's Weekly Growth Letter — the flagship fix for D020
    (the AI-generated tips feature that was designed in Wuslah's W4
    spec but whose actual generation task, W4.2, was never built —
    every real student silently received only generic fallback tips,
    forever, until Hisn found it).

    Per R3's acceptance criteria, the prompt must be built from AT
    LEAST 2 of: nour_memories, pronunciation trend, vocab_srs state,
    ability_milestones, difficulty_level changes, recent
    nour_conversations themes. This builds from as many of those as
    are actually present for this specific student (not always all 6
    — a brand new student may only have streak/completion data yet,
    which is fine; the letter is honest about whatever is real for
    THEM, not padded with invented specifics).

    Returns (letter_text, source).
    """
    system_prompt = _nour_voice_system_prompt()
    user_prompt = _build_growth_letter_prompt(signals)
    return await _generate_with_fallback(
        system_prompt, user_prompt,
        lambda: _template_growth_letter(signals),
    )


def _build_growth_letter_prompt(signals: dict) -> str:
    """Builds the user-facing prompt for build_growth_letter() from
    whichever signals are actually present for this student. Kept as
    its own function (not inlined) so it's directly unit-testable —
    you can assert on the STRING this produces without needing a real
    AI call, which matters for catching a regression here specifically
    (this is the exact piece of logic where D020's engine, had it ever
    been built, most likely would have quietly degraded to generic
    text without anyone noticing).
    """
    name = signals.get("discord_name", "the student")
    level = signals.get("level", "L0")
    week = signals.get("week", 1)
    streak = signals.get("streak", 0)
    completion = signals.get("completion_rate_7d", 0)

    facts = [f"Level {level}, week {week}, {streak}-day streak, {completion:.0f}% task completion this week."]

    memories = signals.get("memories", [])
    if memories:
        facts.append(f"Known personal facts about them (Nour's own memory): {'; '.join(memories[:3])}.")

    milestones = signals.get("milestones_recent", [])
    if milestones:
        names = ", ".join(m["milestone_id"] for m in milestones[:3])
        facts.append(f"Milestones unlocked in the last 14 days: {names}.")

    trend = signals.get("pronunciation_trend", {})
    if trend.get("total_scored", 0) > 0:
        facts.append(
            f"Pronunciation: {trend.get('trend', 'no_data')} trend, "
            f"7-day average {trend.get('average_7d', 0):.0f}%."
        )

    srs = signals.get("srs_state", {})
    if srs.get("total", 0) > 0:
        facts.append(
            f"Vocabulary (SRS): {srs.get('mastered', 0)} words mastered, "
            f"{srs.get('due_today', 0)} due for review today."
        )

    themes = signals.get("conversation_themes", [])
    if themes:
        facts.append(f"Recently asked Nour about: {'; '.join(themes[:2])}.")

    facts_text = "\n".join(f"- {f}" for f in facts)

    from . import nour_personality
    gender_instruction = nour_personality.get_gender_instruction(signals.get("discord_id", ""))

    return (
        f"Write a short (3-5 sentence) personal weekly check-in message in "
        f"Egyptian Arabic for {name}, in Nour's voice, for their weekly "
        f"growth letter. Use AT LEAST 2 of the specific facts below — "
        f"reference them naturally, don't just list them. Be warm and "
        f"genuinely specific to THIS student, never generic or something "
        f"that could apply to anyone:\n\n{facts_text}\n\n"
        f"ADDRESSING THIS STUDENT: {gender_instruction}\n\n"
        f"If a fact area has no data (e.g. no milestones yet), don't "
        f"mention it or apologize for it — just build the letter from "
        f"whatever facts ARE present. Write ONLY in clear Arabic (with "
        f"English words only where natural, e.g. a level name) — never "
        f"mix in any other language."
    )


def _template_growth_letter(signals: dict) -> str:
    """Non-AI fallback for the growth letter — built directly from
    real signals (per design.md: 'this fallback is itself personal,
    just not AI-phrased'), never a generic string. Uses whichever
    signal sources are actually present for this student, same
    principle as _build_growth_letter_prompt() above — this is the
    fallback that fires when BOTH AI providers are down, so it needs
    to stand on its own as genuinely personal, not just a shorter
    version of the AI prompt."""
    streak = signals.get("streak", 0)
    completion = signals.get("completion_rate_7d", 0)
    milestones = signals.get("milestones_recent", [])
    srs = signals.get("srs_state", {})
    trend = signals.get("pronunciation_trend", {})

    parts = [f"استمرارك {streak} يوم على التوالي ده حاجة حلوة فعلاً 🔥"]

    if milestones:
        parts.append(f"وكمان فتحت {len(milestones)} إنجاز جديد الأسبوعين اللي فاتوا — عاش!")

    if trend.get("total_scored", 0) > 0 and trend.get("trend") == "improving":
        parts.append("ونطقك بيتحسن بشكل واضح، حاسة بيه فعلاً 🎯")

    if srs.get("mastered", 0) > 0:
        parts.append(f"وحفظت {srs['mastered']} كلمة كويس لدرجة إنك متقنها — تقدم حقيقي 📝")

    parts.append(f"معدل الإنجاز الأسبوع ده {completion:.0f}%. يلا نكمل بنفس الطاقة 💪")
    return " ".join(parts)


async def build_milestone_moment(discord_id: str, milestone_id: str,
                                  signals: dict) -> tuple[str, str]:
    """M3.1: a personalized, in-the-moment message when a student
    unlocks one of the 12 (per design.md's framing)/15 (per the actual
    milestones.json content this session found) real ability
    milestones — fixes the generic "🏆 Unlocked!" pattern per R4.

    Looks up the real milestone's name/description from
    milestones.json (not just the raw machine ID) so the prompt is
    genuinely specific to what the student actually did, and includes
    whatever real context `signals` has (streak, related memory) for
    extra personalization when available.
    """
    milestone_info = _get_milestone_info(milestone_id, signals.get("level", "L0"))
    milestone_name = milestone_info.get("name", milestone_id) if milestone_info else milestone_id
    milestone_desc = milestone_info.get("description", "") if milestone_info else ""

    system_prompt = _nour_voice_system_prompt()
    extra_context = []
    if signals.get("streak", 0) > 0:
        extra_context.append(f"they're on a {signals['streak']}-day streak")
    memories = signals.get("memories", [])
    if memories:
        extra_context.append(f"known personal context: {memories[0]}")
    context_str = f" Additional real context: {'; '.join(extra_context)}." if extra_context else ""

    from . import nour_personality
    gender_instruction = nour_personality.get_gender_instruction(discord_id)

    user_prompt = (
        f"The student {signals.get('discord_name', '')} just completed the "
        f"'{milestone_name}' milestone ({milestone_desc}). Write a short, "
        f"warm, SPECIFIC congratulations message in Egyptian Arabic that "
        f"references what they actually accomplished, not a generic "
        f"'unlocked!' message.{context_str}\n\n"
        f"ADDRESSING THIS STUDENT: {gender_instruction}\n\n"
        f"Write ONLY in clear Arabic (English words only where natural) — "
        f"never mix in any other language."
    )
    return await _generate_with_fallback(
        system_prompt, user_prompt,
        lambda: f"🏆 مبروك يا نجم! إنجاز '{milestone_name}' اكتمل — ده تقدم حقيقي، يلا نكمل كده!",
    )


def _get_milestone_info(milestone_id: str, level: str) -> Optional[dict]:
    """Look up a milestone's real name/description from
    milestones.json, by ID and level. Returns None if not found
    (e.g. a stale/renamed ID) — callers fall back to the raw ID."""
    import json
    from pathlib import Path
    milestones_file = (
        Path(__file__).resolve().parent.parent / "content" / "milestones" / "milestones.json"
    )
    if not milestones_file.exists():
        return None
    try:
        all_milestones = json.loads(milestones_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    for m in all_milestones.get(level, []):
        if m.get("id") == milestone_id:
            return m
    return None


async def build_difficulty_note(discord_id: str, direction: str,
                                 signals: dict) -> tuple[str, str]:
    """M0.2 stub — full direction-aware prompt lands in M4.1.
    `direction` is "up" or "down"; both must be framed positively
    per R5's acceptance criteria, enforced even in this stub's
    template fallback.
    """
    system_prompt = _nour_voice_system_prompt()
    from . import nour_personality
    gender_instruction = nour_personality.get_gender_instruction(discord_id)
    language_purity_note = (
        "Write ONLY in clear Arabic (English words only where natural) — "
        "never mix in any other language."
    )

    if direction == "up":
        user_prompt = (
            f"The student {signals.get('discord_name', '')} is being moved to "
            f"a harder difficulty because their scores are strong. Write a "
            f"short, positive, encouraging message in Egyptian Arabic — "
            f"frame this as 'you're ready for more,' never as a penalty.\n\n"
            f"ADDRESSING THIS STUDENT: {gender_instruction}\n\n{language_purity_note}"
        )
        template = "الوقت مناسب لتحدي أكبر دلوقتي — هنرفع مستوى المهام شوية عشان نستمر في التطور 🚀"
    else:
        user_prompt = (
            f"The student {signals.get('discord_name', '')} is being moved to "
            f"an easier difficulty to build confidence. Write a short, "
            f"positive, encouraging message in Egyptian Arabic — frame this "
            f"as building a stronger foundation, never as a setback.\n\n"
            f"ADDRESSING THIS STUDENT: {gender_instruction}\n\n{language_purity_note}"
        )
        template = "هنبسط المهام شوية عشان نبني أساس أقوى — دي خطوة ذكية، مش تراجع 💪"

    return await _generate_with_fallback(system_prompt, user_prompt, lambda: template)
