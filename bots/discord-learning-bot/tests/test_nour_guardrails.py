"""Tests for Aql (#15) Phase A4 — Output Guardrails.

This is the phase directly targeting the ORIGINAL reported bug
("occasionally outputs nonsensical foreign-language text"), so this
test file is deliberately the most exhaustive in the Aql spec so far
(per tasks.md's own instruction: "do not skip or compress its
testing").

Covers:
- A4.1: check_script_conformance() against real Arabic, real English,
  mixed, emoji-only, and empty text.
- A4.2: check_bidi_structure() is a genuine passthrough to
  scripts.bidi_check.find_bidi_issues() (not a silent reimplementation
  that could drift).
- A4.3: check_role_leak() catches every real OWNER_LEAK_MARKERS entry
  for Role.STUDENT, and never applies to Role.OWNER.
- A4.4: guarded_generate()'s full state machine — pass-first-try,
  fail-then-retry-succeeds, fail-twice-falls-back-to-template — NEVER
  returns a guardrail-failing string on any path.
- A4.5: every guardrail trigger (and ONLY a trigger, not a
  first-try pass) is logged to nour_guardrail_events with the correct
  type/outcome, and the original text is stored ONLY as a hash.
- A4.6: the stress test — 200 reproductions of the original bug
  conditions (a provider that returns garbled/foreign-language output)
  confirm ZERO non-conformant responses ever reach the "delivered"
  stage.
"""
import hashlib
import random

import pytest

from src import database
from src.nour import guardrails
from src.nour.roles import Role


# ============================================================
#  A4.1 — check_script_conformance()
# ============================================================

def test_pure_arabic_passes():
    assert guardrails.check_script_conformance("مرحبا بك في المجتمع، كيف حالك اليوم؟") is True


def test_pure_english_fails():
    assert guardrails.check_script_conformance(
        "Hello this is a totally broken English response with no Arabic at all"
    ) is False


def test_emoji_only_passes():
    assert guardrails.check_script_conformance("😊👍🎉") is True


def test_empty_string_passes():
    assert guardrails.check_script_conformance("") is True


def test_digits_and_punctuation_only_passes():
    assert guardrails.check_script_conformance("123 456 !!! ---") is True


def test_arabic_with_one_channel_reference_passes():
    """Names/numbers/short embedded references are OK per design.md
    Section 7 -- the threshold is 'dominant', not '100%'."""
    assert guardrails.check_script_conformance("يمكنك زيارة #ask-nour للمساعدة") is True


def test_mostly_english_with_a_little_arabic_fails():
    assert guardrails.check_script_conformance(
        "This response is mostly written in English with just a tiny bit of مرحبا mixed in"
    ) is False


def test_unsupported_expected_script_raises():
    with pytest.raises(NotImplementedError):
        guardrails.check_script_conformance("test", expected_script="french")


# ============================================================
#  A4.2 — check_bidi_structure() is a genuine passthrough
# ============================================================

def test_bidi_structure_detects_known_real_issue():
    """The exact real-world example from scripts/bidi_check.py's own
    docstring (found live during Sahin Phase 1)."""
    text = "لا تكتب نصًا أو أسئلة هنا — مكانها #ask-nour أو #support"
    issues = guardrails.check_bidi_structure(text)
    assert len(issues) == 1


def test_bidi_structure_clean_text_has_no_issues():
    assert guardrails.check_bidi_structure("مرحبا بك، كيف حالك اليوم؟") == []


def test_bidi_structure_single_embedded_reference_is_fine():
    assert guardrails.check_bidi_structure("يمكنك زيارة #ask-nour للمساعدة") == []


def test_check_bidi_structure_is_the_same_function_object_behavior():
    """Confirms this is a genuine import, not a parallel
    reimplementation that could silently drift -- call the real
    scripts.bidi_check.find_bidi_issues() directly and compare output
    for several inputs."""
    from scripts.bidi_check import find_bidi_issues
    samples = [
        "لا تكتب نصًا أو أسئلة هنا — مكانها #ask-nour أو #support",
        "مرحبا بك في المجتمع",
        "استخدم !done و #general معًا للمتابعة",
        "",
    ]
    for text in samples:
        assert guardrails.check_bidi_structure(text) == find_bidi_issues(text)


# ============================================================
#  A4.3 — check_role_leak()
# ============================================================

def test_role_leak_owner_always_passes_regardless_of_content():
    leaky_text = "استخدم docker compose up وجدول knowledge_chunks و GEMINI_API_KEY"
    assert guardrails.check_role_leak(leaky_text, Role.OWNER) is True


@pytest.mark.parametrize("marker", guardrails.OWNER_LEAK_MARKERS)
def test_every_real_leak_marker_is_caught_for_student(marker):
    text = f"يمكنك استخدام {marker} للقيام بذلك"
    assert guardrails.check_role_leak(text, Role.STUDENT) is False


def test_clean_response_passes_role_leak_for_student():
    assert guardrails.check_role_leak("مرحبا بك، كيف يمكنني مساعدتك اليوم؟", Role.STUDENT) is True


def test_role_leak_markers_list_is_nonempty():
    """A4.3's explicit requirement: start with a REAL initial list,
    not an empty placeholder."""
    assert len(guardrails.OWNER_LEAK_MARKERS) >= 5


# ============================================================
#  Correction hints must themselves be guardrail-clean (found live:
#  the original "bidi" hint text ironically violated its own bidi
#  rule -- two embedded LTR references, "#channel" and "!command",
#  joined by Arabic connector text on one line).
# ============================================================

@pytest.mark.parametrize("failure_type", ["script", "bidi", "role_leak", "unknown_type"])
def test_every_correction_hint_passes_bidi_structure_check(failure_type):
    hint = guardrails._hint_for_failure(failure_type)
    assert guardrails.check_bidi_structure(hint) == []


@pytest.mark.parametrize("failure_type", ["script", "bidi", "role_leak", "unknown_type"])
def test_every_correction_hint_passes_script_conformance_check(failure_type):
    hint = guardrails._hint_for_failure(failure_type)
    assert guardrails.check_script_conformance(hint) is True


# ============================================================
#  A4.4 — guarded_generate() state machine
# ============================================================

@pytest.mark.asyncio
async def test_guarded_generate_passes_through_on_first_try():
    async def good(correction_hint=None):
        return "مرحبا بك، كيف يمكنني مساعدتك اليوم؟"

    result = await guardrails.guarded_generate(good, role=Role.STUDENT, discord_id="u1")
    assert result == "مرحبا بك، كيف يمكنني مساعدتك اليوم؟"


@pytest.mark.asyncio
async def test_guarded_generate_first_try_pass_is_never_logged():
    async def good(correction_hint=None):
        return "مرحبا بك، كيف يمكنني مساعدتك اليوم؟"

    await guardrails.guarded_generate(good, role=Role.STUDENT, discord_id="u1")
    assert database.count_guardrail_events() == 0


@pytest.mark.asyncio
async def test_guarded_generate_retries_and_succeeds():
    calls = []

    async def bad_then_good(correction_hint=None):
        calls.append(correction_hint)
        if correction_hint:
            return "مرحبا بك، هذا رد مصحح بالكامل بالعربية"
        return "Hello this response is entirely broken English"

    result = await guardrails.guarded_generate(bad_then_good, role=Role.STUDENT, discord_id="u1")
    assert result == "مرحبا بك، هذا رد مصحح بالكامل بالعربية"
    assert len(calls) == 2
    assert calls[0] is None
    assert calls[1] is not None  # a real correction hint was passed


@pytest.mark.asyncio
async def test_guarded_generate_retry_success_is_logged_as_corrected_on_retry():
    async def bad_then_good(correction_hint=None):
        if correction_hint:
            return "مرحبا بك، رد مصحح تمامًا"
        return "This is completely broken English with zero Arabic"

    await guardrails.guarded_generate(bad_then_good, role=Role.STUDENT, discord_id="u1")
    conn = database._connect()
    row = conn.execute("SELECT * FROM nour_guardrail_events WHERE discord_id='u1'").fetchone()
    conn.close()
    assert row is not None
    assert row["outcome"] == "corrected_on_retry"
    assert row["guardrail_type"] == "script"


@pytest.mark.asyncio
async def test_guarded_generate_never_returns_a_failing_response_even_when_retry_fails():
    """THE core guarantee of this entire phase: no matter how badly a
    provider misbehaves, guarded_generate() NEVER returns text that
    fails the guardrails -- it always ends in either a corrected
    response or a known-good template."""
    async def always_broken(correction_hint=None):
        return "This never gets fixed no matter what correction is applied"

    result = await guardrails.guarded_generate(always_broken, role=Role.STUDENT, discord_id="u1")
    passed, _ = guardrails._passes_all_guardrails(result, Role.STUDENT)
    assert passed is True


@pytest.mark.asyncio
async def test_guarded_generate_fallback_is_a_real_known_template():
    from src.nour_concierge import _TEMPLATE_RESPONSES

    async def always_broken(correction_hint=None):
        return "This never gets fixed no matter what correction is applied"

    result = await guardrails.guarded_generate(always_broken, role=Role.STUDENT, discord_id="u1")
    assert result in _TEMPLATE_RESPONSES


@pytest.mark.asyncio
async def test_guarded_generate_fallback_is_logged_as_template_fallback():
    async def always_broken(correction_hint=None):
        return "This never gets fixed no matter what correction is applied"

    await guardrails.guarded_generate(always_broken, role=Role.STUDENT, discord_id="u1")
    conn = database._connect()
    row = conn.execute("SELECT * FROM nour_guardrail_events WHERE discord_id='u1'").fetchone()
    conn.close()
    assert row is not None
    assert row["outcome"] == "template_fallback"


@pytest.mark.asyncio
async def test_guarded_generate_bidi_failure_type_attributed_correctly():
    # Dominantly-Arabic (passes script conformance) but has 2+ embedded
    # LTR islands on one line (fails bidi) -- isolates the bidi check
    # specifically, distinct from the script-conformance check.
    bidi_only_broken = (
        "لا تكتب هنا أبدا أي أسئلة أو استفسارات لأن هذا المكان مخصص فقط "
        "لأمور أخرى تماما — الرجاء الذهاب الى القناة المخصصة وهي #ask-nour "
        "أو استخدم قناة أخرى وهي #support للمساعدة الفورية والسريعة جدا"
    )

    async def bidi_broken(correction_hint=None):
        if correction_hint:
            return "استخدم #ask-nour للمساعدة"
        return bidi_only_broken

    await guardrails.guarded_generate(bidi_broken, role=Role.STUDENT, discord_id="u1")
    conn = database._connect()
    row = conn.execute("SELECT * FROM nour_guardrail_events WHERE discord_id='u1'").fetchone()
    conn.close()
    assert row["guardrail_type"] == "bidi"


@pytest.mark.asyncio
async def test_guarded_generate_role_leak_failure_type_attributed_correctly():
    # Dominantly-Arabic, single embedded LTR token (passes script AND
    # bidi) but contains a real OWNER_LEAK_MARKERS entry -- isolates
    # the role_leak check specifically.
    leak_only_broken = (
        "يمكنك استخدام هذا الجدول الداخلي المسمى knowledge_chunks مباشرة "
        "لحل هذا الأمر بسهولة كبيرة جدا وبدون أي مشاكل إطلاقا في أي وقت "
        "من الأوقات مهما كانت الظروف المحيطة بالطلب"
    )

    async def leaky(correction_hint=None):
        if correction_hint:
            return "يمكنني مساعدتك في هذا الأمر بكل سرور وسأتحقق من الأمر لك"
        return leak_only_broken

    await guardrails.guarded_generate(leaky, role=Role.STUDENT, discord_id="u1")
    conn = database._connect()
    row = conn.execute("SELECT * FROM nour_guardrail_events WHERE discord_id='u1'").fetchone()
    conn.close()
    assert row["guardrail_type"] == "role_leak"


@pytest.mark.asyncio
async def test_guarded_generate_owner_role_never_triggers_role_leak():
    """An owner asking about internal details must not be forced
    through a pointless retry cycle for role_leak -- only script/bidi
    apply to the owner."""
    async def technical_but_clean_script(correction_hint=None):
        return "يمكنك استخدام جدول knowledge_chunks مباشرة لحل هذا الأمر بسهولة"

    result = await guardrails.guarded_generate(
        technical_but_clean_script, role=Role.OWNER, discord_id="owner1"
    )
    assert result == "يمكنك استخدام جدول knowledge_chunks مباشرة لحل هذا الأمر بسهولة"
    assert database.count_guardrail_events() == 0


# ============================================================
#  A4.5 — hash, not raw text
# ============================================================

@pytest.mark.asyncio
async def test_original_failing_text_is_never_stored_verbatim():
    original = "This is the exact broken text that must never be stored verbatim anywhere"

    async def always_broken(correction_hint=None):
        return original

    await guardrails.guarded_generate(always_broken, role=Role.STUDENT, discord_id="u1")
    conn = database._connect()
    row = conn.execute("SELECT * FROM nour_guardrail_events WHERE discord_id='u1'").fetchone()
    conn.close()
    assert row["original_text_hash"] == hashlib.sha256(original.encode("utf-8")).hexdigest()
    assert original not in str(dict(row))


# ============================================================
#  A4.6 — STRESS TEST (SC1 acceptance test)
# ============================================================

_GARBLED_SAMPLES = [
    "This is a completely broken English response from a misbehaving provider",
    "Ceci est une réponse complètement cassée en français au lieu de l'arabe",
    "Dies ist eine völlig kaputte Antwort auf Deutsch anstelle von Arabisch",
    "これは完全に壊れた日本語の応答です、アラビア語ではありません",
    "Это полностью неисправный ответ на русском, а не на арабском языке",
    "لا تكتب نصًا أو أسئلة هنا — مكانها #ask-nour أو #general أو #support هنا",
    "يمكنك استخدام جدول knowledge_chunks و docker compose up مباشرة للحل",
    "",  # a genuinely empty/degenerate provider response
    "   ",  # whitespace-only
    "123456789",  # digits-only garbage
]


@pytest.mark.asyncio
async def test_a4_6_stress_test_200_reproductions_zero_non_conformant_reach_delivery():
    """Reproduces the exact original bug conditions (a provider that,
    under long-conversation / KB-heavy / truncation-adjacent context,
    occasionally emits garbled or foreign-language text) 200 times
    against the real guarded_generate() pipeline, alternating between
    every known-bad sample and a mix of retry-fixes-it /
    retry-also-fails behavior. Confirms 0 non-Arabic-conformant
    responses ever reach the 'delivered' stage -- design.md's SC1
    acceptance criterion, run explicitly rather than just implied by
    the smaller per-case tests above.
    """
    rng = random.Random(42)  # deterministic across CI runs
    delivered_responses = []

    for i in range(200):
        garbled = rng.choice(_GARBLED_SAMPLES)
        retry_succeeds = rng.random() < 0.5  # half the time the retry fixes it, half it doesn't

        async def flaky_provider(correction_hint=None, _garbled=garbled, _fixes=retry_succeeds):
            if correction_hint and _fixes:
                return "مرحبا بك، هذا رد مصحح بالكامل بالعربية الفصحى الحديثة"
            if correction_hint and not _fixes:
                return _garbled  # retry did NOT fix it -- provider stays broken
            return _garbled

        result = await guardrails.guarded_generate(
            flaky_provider, role=Role.STUDENT, discord_id=f"stress_{i}"
        )
        delivered_responses.append(result)

    non_conformant = [
        r for r in delivered_responses
        if not guardrails._passes_all_guardrails(r, Role.STUDENT)[0]
    ]
    assert non_conformant == [], (
        f"{len(non_conformant)}/200 delivered responses failed the guardrail "
        f"they should have been blocked by -- SC1 acceptance criterion violated"
    )
    assert len(delivered_responses) == 200
