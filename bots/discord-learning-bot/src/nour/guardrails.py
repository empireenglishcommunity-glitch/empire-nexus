"""Aql (العقل) — Output Guardrails (Phase A4).

design.md Section 7: **the direct, mechanical fix for the original
reported bug** ("occasionally outputs nonsensical foreign-language
text"). Every response passes through `guarded_generate()` before it
can reach a user — this is a hard gate, not an advisory check. A
script-drifted or bidi-broken response becomes structurally
UNREACHABLE to a student, matching requirements.md's FR8/FR9 hard
language ("cannot reach the student", not "should reduce").

Nothing here is reimplemented from scratch where a proven
implementation already exists in this codebase:
  - check_script_conformance() reuses the EXACT Arabic-range regex
    already proven correct in scripts/bidi_check.py and features.py
    (three independent places in this codebase now agree on the same
    Unicode ranges — that consistency matters more than any one of
    them being "improved" in isolation).
  - check_bidi_structure() is a DIRECT IMPORT of
    scripts.bidi_check.find_bidi_issues() — not a second copy of that
    logic that could silently drift out of sync with the first.
  - The template fallback list is nour_concierge._TEMPLATE_RESPONSES
    itself, imported, not duplicated -- one list of "never silence"
    responses for the whole codebase, not two that could diverge.
"""
import hashlib
import logging
import random
import re
from typing import Awaitable, Callable, Optional

from .. import database
from .roles import Role

logger = logging.getLogger("empire-bot.nour.guardrails")

# Same Arabic Unicode ranges as scripts/bidi_check.py's _ARABIC_CHAR
# and features.py's _ARABIC_PATTERN -- deliberately the identical
# regex text (not re-derived), so a future change to "what counts as
# Arabic" made in one place is a visible prompt to check the other two,
# not a silent three-way drift.
_ARABIC_CHAR = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")

# A "letter" for the purposes of the script-dominance ratio: any
# Unicode word character that is not a digit and not "other" (\W is
# non-word, so [^\d\s\W] is exactly "a word character that isn't a
# digit or whitespace" -- i.e. actual letters from ANY script,
# Arabic or Latin or otherwise). Matches design.md Section 7's own
# regex exactly.
_ANY_LETTER = re.compile(r"[^\d\s\W]", re.UNICODE)

SCRIPT_CONFORMANCE_THRESHOLD = 0.7  # dominant, not 100% -- names/numbers/emoji are fine mixed in


def check_script_conformance(text: str, expected_script: str = "arabic") -> bool:
    """True if `text` is DOMINANTLY the expected script. Digits,
    punctuation, and emoji are script-neutral and never count against
    conformance either way (they're excluded from the denominator by
    _ANY_LETTER, which only matches actual letters).

    An empty string or a string with zero letters at all (pure emoji,
    pure digits, pure punctuation) is NOT a violation -- there is no
    "wrong script" to detect in the absence of any script at all.
    """
    if expected_script != "arabic":
        raise NotImplementedError(
            "check_script_conformance() only supports expected_script='arabic' today "
            "-- Nour's system prompt (nour_concierge.NOUR_SYSTEM_PROMPT) mandates "
            "Modern Standard Arabic for every response; no code path currently asks "
            "for a different expected script."
        )
    total_letters = len(_ANY_LETTER.findall(text))
    if total_letters == 0:
        return True
    arabic_chars = len(_ARABIC_CHAR.findall(text))
    return (arabic_chars / total_letters) > SCRIPT_CONFORMANCE_THRESHOLD


def check_bidi_structure(text: str) -> list[str]:
    """Direct import of scripts.bidi_check.find_bidi_issues() -- see
    this module's docstring for why this must never become a second,
    independently-maintained copy of that logic. Returns the list of
    offending lines (empty list = no issues)."""
    from scripts.bidi_check import find_bidi_issues
    return find_bidi_issues(text)


# design.md Section 7 / A4.3: start CONSERVATIVE. Real internal table
# names, real deploy/rollback commands, and real flag-internals
# terminology that should structurally never appear in a response
# generated for a student (the knowledge-domain boundary in
# permissions.py is the PRIMARY defense -- this list is defense in
# depth, catching the case where a leak marker appears anyway, e.g.
# the model inventing a plausible-sounding internal detail rather than
# actually having retrieved it from an owner-only chunk). Expand this
# list from REAL nour_guardrail_events log data post-launch, not from
# speculation about what might leak -- a marker added here without a
# real observed (or at minimum, deliberately red-teamed) leak is
# exactly the kind of un-anchored guess this codebase's own steering
# repeatedly warns against.
OWNER_LEAK_MARKERS = [
    # Real internal table names (database_schema.md / _SCHEMA) --
    # a student has no legitimate reason to ever see these strings.
    "knowledge_chunks", "nour_tool_calls", "nour_guardrail_events",
    "nour_retrieval_log", "feature_flags", "pending_escalations",
    "consumed_proof_messages", "done_cooldowns", "token_ip_log",
    # Real deploy/rollback commands (deployment_runbook.md) --
    "docker compose", "scripts/deploy.py", "scripts/rollback.py",
    "git pull origin main",
    # Real flag-internals terminology (flag_registry_reference.md) --
    "flag_registry.py", "REGISTRY =", "nour_aql_core",
    # Owner-identifying config --
    "OWNER_DISCORD_ID", "GEMINI_API_KEY", "GROQ_API_KEY",
]


def check_role_leak(text: str, role: Role) -> bool:
    """True if the response PASSES the leak check (no owner-only
    marker found). Student-role only -- the owner has no leak
    boundary against themself, so this trivially passes for
    Role.OWNER (and any other role) without scanning, matching
    design.md Section 7's own stated rationale."""
    if role != Role.STUDENT:
        return True
    return not any(marker in text for marker in OWNER_LEAK_MARKERS)


def _passes_all_guardrails(text: str, role: Role) -> tuple[bool, Optional[str]]:
    """Runs all three checks. Returns (passed, failure_type) where
    failure_type is one of 'script' | 'bidi' | 'role_leak' | None.
    Checked in a fixed order (script, then bidi, then role_leak) so
    a response that fails more than one check is consistently
    attributed to the SAME failure type across repeated runs --
    useful for the A4.5 logging this feeds, where a stable
    attribution matters more than which specific check happens to
    "win" on a borderline response.
    """
    if not check_script_conformance(text):
        return False, "script"
    bidi_issues = check_bidi_structure(text)
    if bidi_issues:
        return False, "bidi"
    if not check_role_leak(text, role):
        return False, "role_leak"
    return True, None


def _hint_for_failure(failure_type: str) -> str:
    """A short, Arabic-only corrective instruction appended to the
    retry prompt -- per design.md Section 7, distinct wording per
    failure type so the retry has an actual chance of fixing the
    SPECIFIC thing that failed, not a generic "try again"."""
    hints = {
        "script": (
            "\n\n[تصحيح: اكتب الرد بالكامل بالعربية الفصحى الحديثة فقط، "
            "بدون أي كلمات أو حروف بلغة أخرى.]"
        ),
        "bidi": (
            "\n\n[تصحيح: ضع كل مرجع إنجليزي (مثل اسم قناة أو أمر) في سطر "
            "مستقل به. لا تجمع مرجعين إنجليزيين في السطر نفسه.]"
        ),
        "role_leak": (
            "\n\n[تصحيح: أعد كتابة الرد بدون ذكر أي تفاصيل تقنية داخلية "
            "(أسماء جداول قاعدة بيانات، أوامر نشر، تفاصيل النظام الداخلية).]"
        ),
    }
    return hints.get(failure_type, "\n\n[تصحيح: أعد كتابة الرد بشكل أوضح.]")


def _hash_text(text: str) -> str:
    """SHA-256 hash, not the raw text -- design.md Section 13's own
    stated rationale for nour_guardrail_events.original_text_hash:
    avoid storing a second copy of every failure verbatim. A hash is
    enough to correlate repeated identical failures without doubling
    the codebase's exposure surface for whatever content triggered
    the failure in the first place."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


PromptFn = Callable[..., Awaitable[str]]


async def guarded_generate(prompt_fn: PromptFn, role: Role = Role.STUDENT,
                           discord_id: str = "", max_retries: int = 1) -> str:
    """Wraps any generation call. On any guardrail failure, retries
    ONCE (max_retries=1, per design.md Section 7) with an explicit
    Arabic-only corrective instruction appended via
    `prompt_fn(correction_hint=...)`. If the retry ALSO fails, returns
    a pre-written template -- NEVER a failed-guardrail response, per
    requirements.md's FR8/FR9.

    `prompt_fn` is any zero-arg-or-`correction_hint`-kwarg async
    callable that returns the generated text as a string -- this
    function is deliberately agnostic to WHICH AI provider or prompt
    composition produced that text (Groq vs. Gemini, or the future
    orchestrator's own composition), matching design.md's framing of
    this as a wrapper around "any generation call".

    Every attempt's outcome is logged to `nour_guardrail_events`
    (Phase A4.5) -- a response that passes on the FIRST try is not
    logged at all (there is nothing to observe; logging only happens
    when a guardrail actually triggered), matching
    nour_guardrail_events' own doc comment: "a non-zero role-leak-block
    count here is itself valuable signal."
    """
    from .. import nour_concierge  # local import: avoid a hard
    # circular dependency at module load time (nour_concierge.py does
    # not import guardrails.py, but this keeps the coupling one-directional
    # and explicit rather than accidental)

    response = await prompt_fn()
    passed, failure_type = _passes_all_guardrails(response, role)
    if passed:
        return response

    logger.warning(f"Nour guardrail: '{failure_type}' failure on first attempt, retrying with correction hint")
    corrected = await prompt_fn(correction_hint=_hint_for_failure(failure_type))
    corrected_passed, corrected_failure_type = _passes_all_guardrails(corrected, role)

    if corrected_passed:
        _log_guardrail_event(discord_id, failure_type, response, "corrected_on_retry")
        return corrected

    logger.warning(
        f"Nour guardrail: retry ALSO failed ('{corrected_failure_type}'), "
        f"using template fallback"
    )
    _log_guardrail_event(discord_id, failure_type, response, "template_fallback")
    return random.choice(nour_concierge._TEMPLATE_RESPONSES)


def _log_guardrail_event(discord_id: str, guardrail_type: str, original_text: str, outcome: str) -> None:
    database.log_guardrail_event(
        discord_id=discord_id,
        guardrail_type=guardrail_type,
        original_text_hash=_hash_text(original_text),
        outcome=outcome,
    )
