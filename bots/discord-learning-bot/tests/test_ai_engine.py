"""Tests for src/ai_engine.py.

Covers the pure JSON-extraction logic exhaustively, plus the graceful-
degradation behavior of every generator function when no AI provider
is configured. This is safe to test without mocking the network: with
GEMINI_API_KEY and GROQ_API_KEY both empty (set in conftest.py),
_call_gemini()/_call_groq() short-circuit on the missing key and
return None *before* attempting any HTTP request, so _call_llm() (and
everything built on it) is exercised for real, end-to-end, with zero
network calls.
"""
import pytest

from src import ai_engine


# ============================================================
#  _extract_json — the core parsing helper every generator depends on
# ============================================================

def test_extract_json_plain_object():
    assert ai_engine._extract_json('{"a": 1, "b": "two"}') == {"a": 1, "b": "two"}


def test_extract_json_code_fence_with_json_language_tag():
    text = '```json\n{"word": "hello"}\n```'
    assert ai_engine._extract_json(text) == {"word": "hello"}


def test_extract_json_code_fence_no_language_tag():
    text = '```\n{"word": "hello"}\n```'
    assert ai_engine._extract_json(text) == {"word": "hello"}


def test_extract_json_with_leading_and_trailing_prose():
    text = 'Sure, here is the JSON:\n{"score": 85}\nHope that helps!'
    assert ai_engine._extract_json(text) == {"score": 85}


def test_extract_json_array():
    text = '[{"word": "a"}, {"word": "b"}]'
    assert ai_engine._extract_json(text) == [{"word": "a"}, {"word": "b"}]


def test_extract_json_array_with_surrounding_text():
    text = 'Here you go:\n[{"word": "a"}]\nDone.'
    assert ai_engine._extract_json(text) == [{"word": "a"}]


def test_extract_json_nested_braces():
    text = '{"outer": {"inner": {"deep": 1}}}'
    assert ai_engine._extract_json(text) == {"outer": {"inner": {"deep": 1}}}


def test_extract_json_object_containing_arrays():
    text = '{"words": ["a", "b", "c"], "count": 3}'
    result = ai_engine._extract_json(text)
    assert result["words"] == ["a", "b", "c"]
    assert result["count"] == 3


def test_extract_json_invalid_json_returns_none():
    assert ai_engine._extract_json("{not valid json at all") is None


def test_extract_json_empty_string_returns_none():
    assert ai_engine._extract_json("") is None


def test_extract_json_none_input_returns_none():
    assert ai_engine._extract_json(None) is None


def test_extract_json_no_braces_or_brackets_returns_none():
    assert ai_engine._extract_json("just a plain sentence, no json here") is None


def test_extract_json_whitespace_only_returns_none():
    assert ai_engine._extract_json("   \n\t  ") is None


# ============================================================
#  LLM CALL LAYER — graceful degradation without API keys
# ============================================================

@pytest.mark.asyncio
async def test_call_gemini_returns_none_without_api_key():
    """conftest.py sets GEMINI_API_KEY='' — must short-circuit, not crash."""
    result = await ai_engine._call_gemini("any prompt")
    assert result is None


@pytest.mark.asyncio
async def test_call_groq_returns_none_without_api_key():
    result = await ai_engine._call_groq("any prompt")
    assert result is None


@pytest.mark.asyncio
async def test_call_llm_returns_none_when_both_providers_unavailable():
    result = await ai_engine._call_llm("any prompt")
    assert result is None


# ============================================================
#  GENERATOR FUNCTIONS — every one must degrade to None/fallback
#  gracefully, never raise, when no AI provider is configured.
# ============================================================

@pytest.mark.asyncio
async def test_generate_speaking_mission_returns_none_without_api_key():
    result = await ai_engine.generate_speaking_mission("L0", 1, "Saturday", "free_talk", "Greetings")
    assert result is None


@pytest.mark.asyncio
async def test_evaluate_writing_returns_none_without_api_key():
    result = await ai_engine.evaluate_writing("My name is Ahmed.", "Introduce yourself.", "L0")
    assert result is None


@pytest.mark.asyncio
async def test_generate_vocabulary_sheet_returns_none_without_api_key():
    result = await ai_engine.generate_vocabulary_sheet("L0", 1, "Greetings")
    assert result is None


@pytest.mark.asyncio
async def test_generate_grammar_card_returns_none_without_api_key():
    result = await ai_engine.generate_grammar_card("L0", 1, "Present Simple")
    assert result is None


@pytest.mark.asyncio
async def test_generate_progress_summary_returns_none_without_api_key():
    result = await ai_engine.generate_progress_summary("Ahmed", "L0", 1, {"tasks_completed": 5})
    assert result is None


@pytest.mark.asyncio
async def test_generate_accent_drill_returns_none_without_api_key():
    result = await ai_engine.generate_accent_drill("L0", 1)
    assert result is None


# ============================================================
#  quick_feedback — the one generator with a real, deterministic
#  fallback path (must NEVER return None — daily task flow depends
#  on always getting some response back).
# ============================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("task_type", [
    "accent", "vocab", "shadow", "speaking", "listening", "writing", "community",
])
async def test_quick_feedback_fallback_for_every_known_task_type(task_type):
    result = await ai_engine.quick_feedback("Ahmed", task_type, feeling=7)
    assert result
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_quick_feedback_fallback_for_unknown_task_type():
    result = await ai_engine.quick_feedback("Ahmed", "some_unknown_task", feeling=5)
    assert result
    assert "Task completed" in result


@pytest.mark.asyncio
async def test_quick_feedback_low_feeling_still_returns_message():
    result = await ai_engine.quick_feedback("Ahmed", "writing", feeling=1)
    assert result
