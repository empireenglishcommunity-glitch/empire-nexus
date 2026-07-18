"""Tests for Aql (#15) Phase A5 — Bounded Orchestrator + Intent Classification.

Covers:
- A5.1: classify_intent() categorization and graceful degradation.
- A5.2/A5.3/A5.4/A5.5: handle_message() end-to-end — role resolution,
  memory assembly, tool-schema restriction to role, provider fallback
  chain (Groq -> Gemini -> template), never returning None for a
  registered caller.
- A5.6: escalation short-circuits BEFORE the orchestration loop, via
  the unchanged nour_escalation.escalate_to_owner() path -- both the
  fixed-keyword check and a classifier-detected escalation.
- A5.7: THE core "bounded" guarantee — a model that always wants to
  call a tool is force-terminated into composing a real text answer
  on exactly the 3rd call, never a 4th, never spiraling.
"""
from unittest.mock import AsyncMock, patch

import pytest

from src import config, database
from src.nour import orchestrator
from src.nour.orchestrator import LLMToolResponse, ToolCallRequest
from src.nour.roles import Role


# ============================================================
#  A5.1 — classify_intent()
# ============================================================

@pytest.mark.asyncio
async def test_classify_intent_degrades_to_knowledge_question_without_groq_key(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    result = await orchestrator.classify_intent("test message")
    assert result == "knowledge_question"


@pytest.mark.asyncio
async def test_classify_intent_parses_a_real_category_from_response(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-key-for-test")

    async def fake_raw(prompt, temperature=0.0, max_tokens=10):
        return "data_request"

    with patch.object(orchestrator, "_call_groq_raw", new=fake_raw):
        result = await orchestrator.classify_intent("ما هو تقدمي؟")
    assert result == "data_request"


@pytest.mark.asyncio
async def test_classify_intent_degrades_on_unparseable_response(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-key-for-test")

    async def fake_raw(prompt, temperature=0.0, max_tokens=10):
        return "this is not one of the categories at all"

    with patch.object(orchestrator, "_call_groq_raw", new=fake_raw):
        result = await orchestrator.classify_intent("test")
    assert result == "knowledge_question"


@pytest.mark.asyncio
async def test_classify_intent_degrades_on_none_response(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-key-for-test")

    async def fake_raw(prompt, temperature=0.0, max_tokens=10):
        return None

    with patch.object(orchestrator, "_call_groq_raw", new=fake_raw):
        result = await orchestrator.classify_intent("test")
    assert result == "knowledge_question"


@pytest.mark.parametrize("category", [
    "knowledge_question", "data_request", "action_request",
    "onboarding_moment", "emotional_support", "escalation",
])
@pytest.mark.asyncio
async def test_classify_intent_recognizes_every_real_category(category, monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-key-for-test")

    async def fake_raw(prompt, temperature=0.0, max_tokens=10):
        return category

    with patch.object(orchestrator, "_call_groq_raw", new=fake_raw):
        result = await orchestrator.classify_intent("test")
    assert result == category


# ============================================================
#  Tool schema conversion helpers
# ============================================================

def test_openai_schema_conversion_shape():
    defs = [{"name": "get_x", "description": "d", "parameters": {"a": "string"}}]
    schemas = orchestrator._tool_defs_to_openai_schema(defs)
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "get_x"
    assert schemas[0]["function"]["parameters"]["properties"]["a"]["type"] == "string"
    assert "a" in schemas[0]["function"]["parameters"]["required"]


def test_openai_schema_conversion_zero_param_tool():
    defs = [{"name": "get_x", "description": "d", "parameters": {}}]
    schemas = orchestrator._tool_defs_to_openai_schema(defs)
    assert schemas[0]["function"]["parameters"]["properties"] == {}
    assert "required" not in schemas[0]["function"]["parameters"]


def test_gemini_schema_conversion_zero_param_tool_omits_parameters_key():
    defs = [{"name": "get_x", "description": "d", "parameters": {}}]
    schemas = orchestrator._tool_defs_to_gemini_schema(defs)
    decl = schemas[0]["functionDeclarations"][0]
    assert "parameters" not in decl


def test_gemini_schema_conversion_with_params():
    defs = [{"name": "get_x", "description": "d", "parameters": {"a": "string"}}]
    schemas = orchestrator._tool_defs_to_gemini_schema(defs)
    decl = schemas[0]["functionDeclarations"][0]
    assert decl["parameters"]["properties"]["a"]["type"] == "string"


def test_empty_tool_defs_produce_empty_gemini_schema():
    assert orchestrator._tool_defs_to_gemini_schema([]) == []


def test_safe_json_loads_handles_malformed_input():
    assert orchestrator._safe_json_loads("not json") == {}
    assert orchestrator._safe_json_loads('{"a": 1}') == {"a": 1}
    assert orchestrator._safe_json_loads('[1, 2]') == {}  # not a dict


# ============================================================
#  A5.2 — handle_message() basic routing
# ============================================================

@pytest.mark.asyncio
async def test_handle_message_returns_none_for_unregistered_user():
    result = await orchestrator.handle_message("never_registered", "hello")
    assert result is None


@pytest.mark.asyncio
async def test_handle_message_never_returns_none_for_registered_student():
    """Even with every LLM call unavailable, a registered student must
    get SOME response, never None/silence."""
    database.register_member("u1", "Alice")
    with patch.object(orchestrator, "_call_llm_with_tools", new=AsyncMock(return_value=None)):
        result = await orchestrator.handle_message("u1", "سؤال عادي")
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_handle_message_stores_conversation_both_turns():
    database.register_member("u1", "Alice")

    async def fake_llm(messages, tool_defs):
        return LLMToolResponse(content="مرحبا بك، كيف يمكنني مساعدتك؟", tool_calls=[])

    with patch.object(orchestrator, "_call_llm_with_tools", new=fake_llm):
        await orchestrator.handle_message("u1", "سؤال تجريبي")

    history = database.get_recent_conversation("u1", limit=10)
    roles = [h["role"] for h in history]
    assert "student" in roles
    assert "nour" in roles


# ============================================================
#  A5.3/A5.4 — provider fallback chain
# ============================================================

@pytest.mark.asyncio
async def test_call_llm_with_tools_falls_back_to_gemini_when_groq_unavailable():
    async def groq_unavailable(messages, tool_defs):
        return None

    gemini_called = []

    async def fake_gemini(messages, tool_defs):
        gemini_called.append(True)
        return LLMToolResponse(content="رد من جيميناي", tool_calls=[])

    with patch.object(orchestrator, "_call_groq_with_tools", new=groq_unavailable), \
         patch.object(orchestrator, "_call_gemini_with_tools", new=fake_gemini):
        result = await orchestrator._call_llm_with_tools([{"role": "user", "content": "hi"}], [])

    assert gemini_called == [True]
    assert result.content == "رد من جيميناي"


@pytest.mark.asyncio
async def test_call_llm_with_tools_prefers_groq_when_available():
    async def fake_groq(messages, tool_defs):
        return LLMToolResponse(content="رد من جروك", tool_calls=[])

    gemini_called = []

    async def fake_gemini(messages, tool_defs):
        gemini_called.append(True)
        return LLMToolResponse(content="should not be used", tool_calls=[])

    with patch.object(orchestrator, "_call_groq_with_tools", new=fake_groq), \
         patch.object(orchestrator, "_call_gemini_with_tools", new=fake_gemini):
        result = await orchestrator._call_llm_with_tools([{"role": "user", "content": "hi"}], [])

    assert gemini_called == []
    assert result.content == "رد من جروك"


# ============================================================
#  A5.5 — template last resort
# ============================================================

@pytest.mark.asyncio
async def test_handle_message_falls_back_to_template_when_all_providers_fail():
    from src.nour_concierge import _TEMPLATE_RESPONSES

    database.register_member("u1", "Alice")
    with patch.object(orchestrator, "_call_llm_with_tools", new=AsyncMock(return_value=None)):
        result = await orchestrator.handle_message("u1", "سؤال")
    assert result in _TEMPLATE_RESPONSES


# ============================================================
#  A5.6 — escalation short-circuits BEFORE the orchestration loop
# ============================================================

@pytest.mark.asyncio
async def test_escalation_keyword_short_circuits_before_any_llm_call():
    database.register_member("u1", "Alice")
    llm_mock = AsyncMock(return_value=LLMToolResponse(content="should never be called", tool_calls=[]))
    with patch.object(orchestrator, "_call_llm_with_tools", new=llm_mock), \
         patch("src.nour_escalation.escalate_to_owner", new=AsyncMock(return_value=True)):
        result = await orchestrator.handle_message("u1", "أريد استرداد فلوسي")

    llm_mock.assert_not_called()
    assert "الفريق" in result


@pytest.mark.asyncio
async def test_escalation_keyword_calls_real_escalate_to_owner():
    database.register_member("u1", "Alice")
    escalate_mock = AsyncMock(return_value=True)
    with patch("src.nour_escalation.escalate_to_owner", new=escalate_mock):
        await orchestrator.handle_message("u1", "أريد إلغاء اشتراكي")
    escalate_mock.assert_called_once()


@pytest.mark.asyncio
async def test_classifier_detected_escalation_also_short_circuits():
    """Defense in depth: even if the fixed keyword list misses
    something, the classifier catching 'escalation' must ALSO route
    through the same unchanged path, before any tool/retrieval loop."""
    database.register_member("u1", "Alice")

    async def fake_classify(text):
        return "escalation"

    llm_mock = AsyncMock(return_value=LLMToolResponse(content="should never be called", tool_calls=[]))
    escalate_mock = AsyncMock(return_value=True)
    with patch.object(orchestrator, "classify_intent", new=fake_classify), \
         patch.object(orchestrator, "_call_llm_with_tools", new=llm_mock), \
         patch("src.nour_escalation.escalate_to_owner", new=escalate_mock):
        result = await orchestrator.handle_message("u1", "غير واضح لغويًا لكنه تصعيد")

    llm_mock.assert_not_called()
    escalate_mock.assert_called_once()
    assert "الفريق" in result


# ============================================================
#  A5.7 — THE bounded-loop guarantee
# ============================================================

@pytest.mark.asyncio
async def test_a5_7_loop_force_terminates_at_exactly_three_calls():
    """A model that ALWAYS wants to call a tool, no matter what, must
    still be force-terminated into a real text composition on the 3rd
    (final) call -- never a 4th call, never an infinite/open-ended loop."""
    database.register_member("u1", "Alice")
    database.add_points("u1", 50, "test")

    call_log = []

    async def always_wants_tool(messages, tool_defs):
        call_log.append(bool(tool_defs))
        if tool_defs:
            return LLMToolResponse(
                content=None,
                tool_calls=[ToolCallRequest(id=f"c{len(call_log)}", name="get_my_progress", arguments={})],
            )
        # No tools offered -- this is the final, forced iteration.
        # A real model would have no choice but to produce text here;
        # this fake asserts that expectation explicitly.
        return LLMToolResponse(content="مرحبا بك، هذا رد نهائي بعد الحلقة المحدودة", tool_calls=[])

    with patch.object(orchestrator, "_call_llm_with_tools", new=always_wants_tool):
        result = await orchestrator.handle_message("u1", "سؤال يتطلب أدوات كثيرة")

    assert len(call_log) == 3
    assert call_log == [True, True, False]  # tools offered on 1st+2nd, withheld on 3rd
    assert result == "مرحبا بك، هذا رد نهائي بعد الحلقة المحدودة"


@pytest.mark.asyncio
async def test_a5_7_loop_terminates_early_if_model_answers_without_tools():
    """The bound is a MAXIMUM, not a mandatory minimum -- a model that
    answers directly on the first call must not be forced through 2
    more pointless iterations."""
    database.register_member("u1", "Alice")
    call_log = []

    async def answers_immediately(messages, tool_defs):
        call_log.append(bool(tool_defs))
        return LLMToolResponse(content="إجابة فورية بدون أي أدوات", tool_calls=[])

    with patch.object(orchestrator, "_call_llm_with_tools", new=answers_immediately):
        result = await orchestrator.handle_message("u1", "سؤال بسيط")

    assert len(call_log) == 1
    assert result == "إجابة فورية بدون أي أدوات"


@pytest.mark.asyncio
async def test_a5_7_tool_results_are_fed_back_into_the_conversation():
    """Confirms the loop actually EXECUTES the requested tool (via the
    real dispatcher, hitting the real database) and feeds the result
    back as a 'tool' role message -- not just counting iterations."""
    database.register_member("u1", "Alice", level="L2")
    database.add_points("u1", 777, "test")

    captured_messages = []

    async def one_tool_call_then_answer(messages, tool_defs):
        captured_messages.append([m for m in messages])
        if tool_defs:
            return LLMToolResponse(
                content=None,
                tool_calls=[ToolCallRequest(id="c1", name="get_my_progress", arguments={})],
            )
        return LLMToolResponse(content="بناءً على البيانات، تقدمك رائع", tool_calls=[])

    with patch.object(orchestrator, "_call_llm_with_tools", new=one_tool_call_then_answer):
        await orchestrator.handle_message("u1", "كيف تقدمي؟")

    # The 2nd LLM call's message list must include a 'tool' role
    # message with the REAL tool result (777 points) embedded.
    second_call_messages = captured_messages[1]
    tool_messages = [m for m in second_call_messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert "777" in tool_messages[0]["content"]


@pytest.mark.asyncio
async def test_a5_7_owner_only_tool_never_reaches_student_via_orchestrator():
    """End-to-end version of A3.5's boundary check: even if a
    student-facing model somehow emitted an owner-only tool name
    (should be impossible since it was never offered), the orchestrator's
    defensive re-check discards it rather than executing it."""
    database.register_member("u1", "Alice")

    async def emits_owner_tool_anyway(messages, tool_defs):
        if tool_defs:
            return LLMToolResponse(
                content=None,
                tool_calls=[ToolCallRequest(id="c1", name="get_student_status", arguments={"student_name": "Bob"})],
            )
        return LLMToolResponse(content="انتهت المحاولة", tool_calls=[])

    with patch.object(orchestrator, "_call_llm_with_tools", new=emits_owner_tool_anyway):
        result = await orchestrator.handle_message("u1", "من فضلك أعطني حالة بوب")

    # Must not raise, must not crash, and must still produce a normal
    # final response -- the disallowed tool call is silently discarded,
    # not executed.
    assert result == "انتهت المحاولة"


@pytest.mark.asyncio
async def test_a5_7_tool_error_is_fed_back_as_error_result_not_a_crash():
    database.register_member("u1", "Alice")

    call_log = []

    async def calls_a_failing_tool(messages, tool_defs):
        call_log.append(1)
        if tool_defs and len(call_log) == 1:
            return LLMToolResponse(
                content=None,
                tool_calls=[ToolCallRequest(id="c1", name="get_my_recent_scores", arguments={})],
            )
        return LLMToolResponse(content="تعاملت مع الخطأ بنجاح", tool_calls=[])

    # Force execute_tool to raise for this one call by breaking the DB
    # function it depends on.
    from src.nour.tools import dispatcher

    async def broken_tool(discord_id):
        raise RuntimeError("simulated failure")

    with patch.object(orchestrator, "_call_llm_with_tools", new=calls_a_failing_tool), \
         patch.dict(dispatcher._ALL_FUNCTIONS, {"get_my_recent_scores": broken_tool}):
        result = await orchestrator.handle_message("u1", "سؤال")

    assert result == "تعاملت مع الخطأ بنجاح"
