"""Aql (العقل) — Bounded Orchestrator (Phase A5).

design.md Section 1 (architecture diagram) + Section 8 (Component 7).
This is the entry point that ties together every earlier phase:
role resolution (A0), retrieval (A1), owner knowledge (A2), tool
calling (A3), and output guardrails (A4) into one deterministic
request-handling pipeline.

**This is one orchestrator process, not multiple autonomous agents**
(design.md's own explicit framing). The "loop" below is a BOUNDED,
deterministic control structure — at most 3 LLM calls per request,
with tool schemas withheld entirely on the 3rd call so the model
structurally cannot request a tool it won't get a chance to use. This
is what makes "bounded" a verifiable property of the code, not just a
comment (see A5.7's test, which drives a model that ALWAYS wants to
call a tool and confirms the loop still terminates in exactly 3 calls
with a real text answer).

Zero live traffic uses this yet — `handle_message()` here is not
called from `bot.py`'s real message handler. That cutover is Phase
A9's phased migration, not this one. `nour_concierge.handle_message()`
remains completely untouched and is still the only thing answering
real messages today.
"""
import json
import logging
import random
from dataclasses import dataclass, field
from typing import Optional

import aiohttp

from .. import config, database, nour_concierge, nour_personality
from . import permissions
from .roles import Role, resolve_role
from .guardrails import guarded_generate
from .knowledge.retriever import retrieve
from .tools import dispatcher

logger = logging.getLogger("empire-bot.nour.orchestrator")

# design.md Section 8's explicit bound: the model may request tool
# calls on iterations 0 and 1, but iteration 2 (the 3rd and final
# call) offers NO tool schemas at all -- not "the model is told not
# to", but "there is nothing in the request for it to call". This is
# what makes the bound structural rather than a suggestion the model
# could ignore.
MAX_ITERATIONS = 3

_INTENT_CATEGORIES = [
    "knowledge_question", "data_request", "action_request",
    "onboarding_moment", "emotional_support", "escalation",
]

_INTENT_CLASSIFICATION_PROMPT = """صنّف الرسالة التالية إلى فئة واحدة فقط من الفئات الآتية:

knowledge_question — سؤال عن معلومة عامة عن النظام أو كيفية استخدامه
data_request — طلب معرفة بيانات شخصية (مثل تقدمي، نقاطي، سلسلتي)
action_request — طلب تنفيذ إجراء محدد (مثل إرسال إعلان، تفعيل ميزة)
onboarding_moment — سؤال من طالب جديد لا يعرف من أين يبدأ
emotional_support — تعبير عن إحباط أو إرهاق أو حاجة للتشجيع
escalation — شكوى أو سؤال عن الدفع أو الاشتراك أو الإلغاء

الرسالة: "{text}"

أجب بكلمة واحدة فقط من الفئات المذكورة أعلاه، بدون أي شرح إضافي."""


async def classify_intent(text: str) -> str:
    """One cheap/fast LLM call (Groq, low max_tokens, temperature=0
    for determinism) that categorizes the incoming message per
    design.md Section 1's six categories. Degrades gracefully to
    "knowledge_question" -- the least action-oriented, safest default
    -- on any failure (missing key, network error, an unparseable
    response), matching this codebase's universal "never crash, never
    silence" AI-call convention.
    """
    if not config.GROQ_API_KEY:
        return "knowledge_question"

    prompt = _INTENT_CLASSIFICATION_PROMPT.format(text=text)
    raw = await _call_groq_raw(prompt, temperature=0.0, max_tokens=10)
    if raw:
        cleaned = raw.strip().lower()
        for category in _INTENT_CATEGORIES:
            if category in cleaned:
                return category
    return "knowledge_question"


async def _call_groq_raw(prompt: str, temperature: float = 0.0, max_tokens: int = 10) -> Optional[str]:
    """A plain (no Nour persona, no tools) Groq chat call -- used only
    by classify_intent(), which is a classification task, not a
    conversational one, so it deliberately does NOT reuse
    nour_concierge's NOUR_SYSTEM_PROMPT."""
    if not config.GROQ_API_KEY:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config.GROQ_API_KEY}"}
    payload = {
        "model": config.GROQ_MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return text.strip() if text else None
    except Exception as e:
        logger.error(f"Aql orchestrator: classify_intent Groq call failed: {e}")
        return None


# ============================================================
#  TOOL-CALLING LLM ABSTRACTION (Groq primary, Gemini fallback)
# ============================================================

@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class LLMToolResponse:
    content: Optional[str]
    tool_calls: list = field(default_factory=list)  # list[ToolCallRequest]


def _json_type(type_str: str) -> str:
    """Our TOOLS schemas use plain words ('string', 'boolean', ...) --
    already valid JSON-Schema primitive type names, so this is mostly
    a safety net against a typo'd/unexpected value defaulting to the
    always-safe 'string' rather than producing an invalid schema."""
    return type_str if type_str in ("string", "number", "integer", "boolean", "array", "object") else "string"


def _tool_defs_to_openai_schema(tool_defs: list[dict]) -> list[dict]:
    """Converts our internal TOOLS list shape (from student_tools.py /
    owner_tools.py) into OpenAI-compatible function-calling schemas --
    the format Groq's chat completions endpoint expects."""
    schemas = []
    for t in tool_defs:
        props = {name: {"type": _json_type(t_)} for name, t_ in t["parameters"].items()}
        params = {"type": "object", "properties": props}
        if props:
            params["required"] = list(props.keys())
        schemas.append({
            "type": "function",
            "function": {"name": t["name"], "description": t["description"], "parameters": params},
        })
    return schemas


def _tool_defs_to_gemini_schema(tool_defs: list[dict]) -> list[dict]:
    """Converts our internal TOOLS list shape into Gemini's
    functionDeclarations format -- verified against Google's live
    function-calling reference at implementation time (per A5.4's
    explicit instruction not to trust a point-in-time assumption):
    https://ai.google.dev/gemini-api/docs/function-calling and
    https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/function-calling
    Zero-parameter tools (every student tool) omit the "parameters"
    key entirely rather than sending an empty object, since it is
    documented as Optional.
    """
    declarations = []
    for t in tool_defs:
        decl = {"name": t["name"], "description": t["description"]}
        props = {name: {"type": _json_type(t_)} for name, t_ in t["parameters"].items()}
        if props:
            decl["parameters"] = {"type": "object", "properties": props, "required": list(props.keys())}
        declarations.append(decl)
    return [{"functionDeclarations": declarations}] if declarations else []


def _safe_json_loads(s: str) -> dict:
    try:
        parsed = json.loads(s)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _messages_to_openai_format(messages: list[dict]) -> list[dict]:
    """Converts our internal, provider-neutral message list into
    OpenAI/Groq's exact wire format. Internal shape:
      {"role": "system"|"user", "content": str}
      {"role": "assistant", "content": str|None, "tool_calls": [{"id","name","arguments"}, ...]}
      {"role": "tool", "name": str, "tool_call_id": str, "content": str}
    """
    out = []
    for m in messages:
        role = m["role"]
        if role == "assistant" and m.get("tool_calls"):
            out.append({
                "role": "assistant",
                "content": m.get("content"),
                "tool_calls": [
                    {
                        "id": tc["id"], "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"], ensure_ascii=False)},
                    }
                    for tc in m["tool_calls"]
                ],
            })
        elif role == "tool":
            out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
        else:
            out.append({"role": role, "content": m.get("content", "") or ""})
    return out


def _messages_to_gemini_contents(messages: list[dict]) -> tuple[list[dict], Optional[str]]:
    """Converts our internal message list into Gemini's `contents`
    array (+ separately-returned system instruction text, since Gemini
    takes system instructions via a dedicated `systemInstruction`
    field, not as a message with role='system' inside `contents`)."""
    contents = []
    system_text = None
    for m in messages:
        role = m["role"]
        if role == "system":
            system_text = (system_text + "\n\n" if system_text else "") + m.get("content", "")
        elif role == "user":
            contents.append({"role": "user", "parts": [{"text": m.get("content", "")}]})
        elif role == "assistant" and m.get("tool_calls"):
            parts = []
            if m.get("content"):
                parts.append({"text": m["content"]})
            for tc in m["tool_calls"]:
                parts.append({"functionCall": {"name": tc["name"], "args": tc["arguments"]}})
            contents.append({"role": "model", "parts": parts})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": m.get("content", "") or ""}]})
        elif role == "tool":
            contents.append({
                "role": "user",
                "parts": [{"functionResponse": {"name": m["name"], "response": {"result": m.get("content", "")}}}],
            })
    return contents, system_text


async def _call_groq_with_tools(messages: list[dict], tool_defs: list[dict]) -> Optional[LLMToolResponse]:
    if not config.GROQ_API_KEY:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config.GROQ_API_KEY}"}
    payload = {
        "model": config.GROQ_MODEL,
        "temperature": 0.7,
        "max_tokens": nour_concierge.MAX_RESPONSE_TOKENS,
        "messages": _messages_to_openai_format(messages),
    }
    if tool_defs:
        payload["tools"] = _tool_defs_to_openai_schema(tool_defs)
        payload["tool_choice"] = "auto"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning(f"Aql orchestrator: Groq tool-call API error {resp.status}: {body[:200]}")
                    return None
                data = await resp.json()
                message = data.get("choices", [{}])[0].get("message", {})
                content = message.get("content")
                raw_tool_calls = message.get("tool_calls") or []
                tool_calls = [
                    ToolCallRequest(
                        id=tc.get("id", f"call_{i}"), name=tc["function"]["name"],
                        arguments=_safe_json_loads(tc["function"].get("arguments", "{}")),
                    )
                    for i, tc in enumerate(raw_tool_calls)
                ]
                return LLMToolResponse(content=content.strip() if content else None, tool_calls=tool_calls)
    except Exception as e:
        logger.error(f"Aql orchestrator: Groq tool-call call failed: {e}")
        return None


async def _call_gemini_with_tools(messages: list[dict], tool_defs: list[dict]) -> Optional[LLMToolResponse]:
    if not config.GEMINI_API_KEY:
        return None
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    )
    contents, system_text = _messages_to_gemini_contents(messages)
    payload = {
        "contents": contents,
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": nour_concierge.MAX_RESPONSE_TOKENS},
    }
    if system_text:
        payload["systemInstruction"] = {"parts": [{"text": system_text}]}
    tools = _tool_defs_to_gemini_schema(tool_defs)
    if tools:
        payload["tools"] = tools

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning(f"Aql orchestrator: Gemini tool-call API error {resp.status}: {body[:200]}")
                    return None
                data = await resp.json()
                candidate = (data.get("candidates") or [{}])[0]
                parts = candidate.get("content", {}).get("parts", [])
                text_parts = [p["text"] for p in parts if "text" in p]
                fn_calls = [p["functionCall"] for p in parts if "functionCall" in p]
                tool_calls = [
                    ToolCallRequest(id=f"gemini_{i}", name=fc["name"], arguments=fc.get("args", {}) or {})
                    for i, fc in enumerate(fn_calls)
                ]
                content = "\n".join(text_parts).strip() if text_parts else None
                return LLMToolResponse(content=content, tool_calls=tool_calls)
    except Exception as e:
        logger.error(f"Aql orchestrator: Gemini tool-call call failed: {e}")
        return None


async def _call_llm_with_tools(messages: list[dict], tool_defs: list[dict]) -> Optional[LLMToolResponse]:
    """Groq primary, Gemini fallback -- same three-tier philosophy as
    nour_concierge._generate_response(), now tool-aware at each tier
    (design.md Section 8's explicit requirement). Because both
    provider-specific functions convert from the SAME internal,
    provider-neutral message format, a provider switch mid-loop
    (Groq succeeds on iteration 0, then fails on iteration 1) is
    handled correctly -- the message history built so far is
    translatable to either provider's wire format on the next call."""
    response = await _call_groq_with_tools(messages, tool_defs)
    if response is not None:
        return response
    logger.info("Aql orchestrator: Groq tool-call unavailable, falling back to Gemini")
    return await _call_gemini_with_tools(messages, tool_defs)


# ============================================================
#  MESSAGE / CONTEXT ASSEMBLY
# ============================================================

def _build_messages(role: Role, text: str, working_memory: list[dict],
                    semantic_facts: list[str], journey_coverage: Optional[dict],
                    retrieved_chunks: list) -> list[dict]:
    """Assembles the message list for the composition call. Reuses
    nour_concierge.NOUR_SYSTEM_PROMPT verbatim (the actual personality
    is not being re-litigated in this phase) plus whatever grounding
    context is available TODAY: working memory (A1), semantic memories
    (existing nour_personality), journey coverage (A3's read path),
    and role-scoped retrieval (A1). Episodic summaries (design.md
    Section 6) are Phase A6's own build -- this function is structured
    so A6 can add one more system-prompt section without changing the
    loop shape around it.
    """
    system_parts = [nour_concierge.NOUR_SYSTEM_PROMPT]

    if role == Role.OWNER:
        system_parts.append(
            "ملاحظة: أنت تتحدث الآن مع مالك النظام (Owner)، الذي لديه صلاحية "
            "الوصول الكامل لكل الأدوات والمعرفة الإدارية المتاحة لك."
        )

    if retrieved_chunks:
        kb_text = "\n\n---\n\n".join(f"### {c.heading}\n{c.content}" for c in retrieved_chunks)
        system_parts.append(f"KNOWLEDGE BASE (استخدم هذا لتأسيس إجابتك):\n{kb_text}")

    if semantic_facts:
        system_parts.append(
            "MEMORIES (أشياء تعرفها عن هذا الطالب):\n" + "\n".join(f"- {f}" for f in semantic_facts)
        )

    if journey_coverage is not None:
        gap_labels = {
            "knows_daily_tasks": "المهام اليومية", "knows_platform_link": "ربط منصة التمرين",
            "knows_streaks": "نظام السلسلة", "knows_channels": "القنوات",
            "first_task_done": "إتمام أول مهمة",
        }
        gaps = [label for key, label in gap_labels.items() if not journey_coverage.get(key)]
        if gaps:
            system_parts.append(
                "JOURNEY GAPS (مواضيع لم يتم تغطيتها بعد مع هذا الطالب -- اذكرها بشكل طبيعي "
                "ضمن الحديث إذا كانت مناسبة للسياق، وليس كرسالة منفصلة مفروضة): " + "، ".join(gaps)
            )

    messages = [{"role": "system", "content": "\n\n".join(system_parts)}]
    for turn in working_memory:
        turn_role = "user" if turn.get("role") == "student" else "assistant"
        messages.append({"role": turn_role, "content": turn.get("message", "")})
    messages.append({"role": "user", "content": text})
    return messages


# ============================================================
#  ESCALATION (unchanged existing path)
# ============================================================

async def _handle_escalation(discord_id: str, text: str) -> str:
    """A5.6: routes through the EXISTING, UNCHANGED
    nour_escalation.escalate_to_owner() -- not reimplemented. Mirrors
    nour_concierge.handle_message()'s own escalation branch exactly
    (identical canned response, identical conversation logging), just
    reachable from this new entry point too."""
    from .. import nour_escalation

    member = database.get_member(discord_id)
    name = (member.get("discord_name", "") if member else "").split("#")[0]

    nour_concierge._store_conversation(discord_id, "student", text, intent="escalation")
    response = "دعني أسأل الفريق بخصوص هذا الأمر وأرجع إليك في أقرب وقت 😊"
    nour_concierge._store_conversation(discord_id, "nour", response, intent="escalation")

    await nour_escalation.escalate_to_owner(discord_id, name, text)
    logger.info(f"Aql orchestrator: escalated message from {discord_id}: {text[:50]}")
    return response


# ============================================================
#  MAIN ENTRY POINT
# ============================================================

async def handle_message(discord_id: str, text: str, channel_context: str = "") -> Optional[str]:
    """design.md Section 8. Role resolve -> escalation check (unchanged
    existing path, before anything else runs, matching today's
    early-exit behavior) -> intent classification -> memory assembly
    -> bounded tool/retrieval loop (max 3 LLM calls) -> guarded
    generation -> memory write.

    Returns None if `discord_id` resolves to no role at all (not a
    registered student, not the owner) -- unchanged from
    nour_concierge.handle_message()'s existing `if not member: return
    None` behavior.
    """
    role = resolve_role(discord_id)
    if role is None:
        return None

    # A5.6: keyword-based escalation check FIRST -- deterministic,
    # zero-cost, exactly nour_concierge's existing check (imported,
    # not duplicated) -- before intent classification, before any LLM
    # call, before the orchestration loop even starts.
    if nour_concierge._should_escalate_immediately(text):
        return await _handle_escalation(discord_id, text)

    intent = await classify_intent(text)
    if intent == "escalation":
        # Defense in depth: the classifier caught something the fixed
        # keyword list didn't. Same unchanged escalation path either way.
        return await _handle_escalation(discord_id, text)

    working_memory = database.get_recent_conversation(discord_id, limit=10)
    semantic_facts = nour_personality.get_memories(discord_id)
    journey_coverage = database.get_journey_coverage(discord_id) if role == Role.STUDENT else None

    tool_schemas = dispatcher.get_tool_schemas_for_role(role)
    retrieved_chunks = await retrieve(text, role, top_k=4, discord_id=discord_id)

    messages = _build_messages(role, text, working_memory, semantic_facts, journey_coverage, retrieved_chunks)

    final_text = None
    for iteration in range(MAX_ITERATIONS):
        # The bound: no tool schemas at all on the final iteration --
        # structurally forces composition, not merely instructed to.
        offer_tools = tool_schemas if iteration < MAX_ITERATIONS - 1 else []
        llm_response = await _call_llm_with_tools(messages, offer_tools)

        if llm_response is None:
            final_text = None
            break

        if llm_response.tool_calls and offer_tools:
            allowed_names = {t["name"] for t in offer_tools}
            messages.append({
                "role": "assistant", "content": llm_response.content,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in llm_response.tool_calls
                ],
            })
            for tc in llm_response.tool_calls:
                if tc.name not in allowed_names:
                    # Structurally impossible per permissions.py's
                    # Section 3 boundary (this tool's schema was never
                    # offered) -- defensive anyway, matching this
                    # codebase's "double-check security-relevant
                    # logic" convention.
                    continue
                try:
                    result = await dispatcher.execute_tool(tc.name, role, discord_id, tc.arguments)
                except dispatcher.ToolError as e:
                    result = {"error": str(e)}
                messages.append({
                    "role": "tool", "name": tc.name, "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })
            continue

        final_text = llm_response.content
        break

    if not final_text:
        final_text = random.choice(nour_concierge._TEMPLATE_RESPONSES)

    async def _prompt_fn(correction_hint: Optional[str] = None) -> str:
        if not correction_hint:
            return final_text
        retry_messages = messages + [{"role": "user", "content": correction_hint}]
        # No tools on the guardrail-correction retry -- this is a pure
        # rewrite request, not a new reasoning turn that might want to
        # call something.
        retry_response = await _call_llm_with_tools(retry_messages, [])
        return retry_response.content if retry_response and retry_response.content else final_text

    guarded_text = await guarded_generate(_prompt_fn, role=role, discord_id=discord_id)

    nour_concierge._store_conversation(discord_id, "student", text, intent=intent)
    nour_concierge._store_conversation(discord_id, "nour", guarded_text, intent=intent)

    return guarded_text
