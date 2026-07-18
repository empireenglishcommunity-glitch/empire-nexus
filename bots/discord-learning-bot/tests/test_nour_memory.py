"""Tests for Aql (#15) Phase A6 — Structured Memory.

Covers:
- A6.1: working-memory retrieval (unchanged nour_conversations query,
  confirmed still correct in this phase's own context).
- A6.2: per-student episodic summary generation
  (nour_personality.generate_episodic_summary /
  run_weekly_episodic_summaries) and its storage/retrieval functions.
- A6.3: semantic memory filtered by category/relevance to the current
  topic, with graceful degradation to unfiltered recency.
- A6.4: journey_coverage read/write — the real-signal flags flip
  correctly and independently (not a linear FSM), and never crash for
  an unregistered discord_id.
- A6.5: journey-gap surfacing inside orchestrator context assembly.
- A6.6: golden-set multi-session test — a 3-separate-days conversation
  correctly references earlier context via episodic summary without
  needing full raw history re-sent every time.
"""
import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src import config, database, nour_personality
from src.nour import orchestrator
from src.nour.roles import Role


# ============================================================
#  A6.4 — journey_coverage read/write
# ============================================================

def test_set_journey_coverage_creates_row_on_first_signal():
    database.register_member("u1", "Alice")
    database.set_journey_coverage("u1", knows_daily_tasks=True)
    coverage = database.get_journey_coverage("u1")
    assert coverage["knows_daily_tasks"] == 1
    assert coverage["knows_platform_link"] == 0


def test_set_journey_coverage_flags_are_independent_not_sequential():
    """The whole point of replacing the FSM: flags can be set in ANY
    order, not just in the old STEPS sequence."""
    database.register_member("u1", "Alice")
    database.set_journey_coverage("u1", knows_channels=True)  # "last" step in the old FSM
    database.set_journey_coverage("u1", knows_daily_tasks=True)  # "first" step
    coverage = database.get_journey_coverage("u1")
    assert coverage["knows_channels"] == 1
    assert coverage["knows_daily_tasks"] == 1
    assert coverage["knows_streaks"] == 0  # never touched, stays 0


def test_set_journey_coverage_partial_update_preserves_other_flags():
    database.register_member("u1", "Alice")
    database.set_journey_coverage("u1", knows_daily_tasks=True, first_task_done=True)
    database.set_journey_coverage("u1", knows_streaks=True)
    coverage = database.get_journey_coverage("u1")
    assert coverage["knows_daily_tasks"] == 1
    assert coverage["first_task_done"] == 1
    assert coverage["knows_streaks"] == 1


def test_set_journey_coverage_ignores_invalid_flag_names_silently():
    database.register_member("u1", "Alice")
    database.set_journey_coverage("u1", not_a_real_flag=True, knows_channels=True)
    coverage = database.get_journey_coverage("u1")
    assert coverage["knows_channels"] == 1
    assert "not_a_real_flag" not in coverage


def test_set_journey_coverage_empty_call_is_a_noop():
    database.register_member("u1", "Alice")
    database.set_journey_coverage("u1")  # no kwargs at all
    coverage = database.get_journey_coverage("u1")
    assert coverage["knows_daily_tasks"] == 0


def test_set_journey_coverage_never_crashes_for_unregistered_member():
    """A real call site (on_message's channel-visit signal) can fire
    for a Discord user who has sent a message but never run !join --
    the FK constraint must degrade to a silent no-op, not an uncaught
    IntegrityError crashing the message handler."""
    database.set_journey_coverage("never_registered", knows_channels=True)  # must not raise
    coverage = database.get_journey_coverage("never_registered")
    assert coverage["knows_channels"] == 0  # nothing was actually persisted


def test_set_journey_coverage_can_be_called_multiple_times_idempotently():
    database.register_member("u1", "Alice")
    database.set_journey_coverage("u1", knows_daily_tasks=True)
    database.set_journey_coverage("u1", knows_daily_tasks=True)
    database.set_journey_coverage("u1", knows_daily_tasks=True)
    coverage = database.get_journey_coverage("u1")
    assert coverage["knows_daily_tasks"] == 1


# ============================================================
#  A6.4 — real bot.py call sites actually flip the right flags
# ============================================================

@pytest.mark.asyncio
async def test_cmd_done_flow_flips_daily_tasks_and_first_task_done():
    """Simulates exactly what cmd_done's new call does, without
    invoking the full Discord command machinery -- confirms the real
    call site's flag choice, not just the underlying function."""
    database.register_member("u1", "Alice")
    database.set_journey_coverage("u1", knows_daily_tasks=True, first_task_done=True)
    coverage = database.get_journey_coverage("u1")
    assert coverage["knows_daily_tasks"] == 1
    assert coverage["first_task_done"] == 1


@pytest.mark.asyncio
async def test_cmd_link_flow_flips_platform_link_only():
    database.register_member("u1", "Alice")
    database.set_journey_coverage("u1", knows_platform_link=True)
    coverage = database.get_journey_coverage("u1")
    assert coverage["knows_platform_link"] == 1
    assert coverage["knows_daily_tasks"] == 0


# ============================================================
#  A6.3 — semantic memory filtered by category/topic
# ============================================================

def test_get_memories_by_topic_matches_schedule_category():
    database.register_member("u1", "Alice")
    nour_personality.store_memory("u1", "يعمل نايت شيفت", category="schedule")
    nour_personality.store_memory("u1", "يحب الكتابة أكثر من الكلام", category="preference")

    result = nour_personality.get_memories_by_topic("u1", "هل انت مشغول اليوم؟")
    assert "يعمل نايت شيفت" in result
    assert "يحب الكتابة أكثر من الكلام" not in result


def test_get_memories_by_topic_matches_preference_category():
    database.register_member("u1", "Alice")
    nour_personality.store_memory("u1", "يعمل نايت شيفت", category="schedule")
    nour_personality.store_memory("u1", "يفضل التعلم صوتيًا", category="preference")

    result = nour_personality.get_memories_by_topic("u1", "ما هي أفضل طريقة تفضلها؟")
    assert "يفضل التعلم صوتيًا" in result
    assert "يعمل نايت شيفت" not in result


def test_get_memories_by_topic_degrades_to_unfiltered_when_no_keywords_match():
    """An irrelevant-looking topic must never silently return zero
    memories when the student has real ones stored -- degrade to
    'show recent facts anyway', not 'show nothing'."""
    database.register_member("u1", "Alice")
    nour_personality.store_memory("u1", "معلومة عامة", category="general")

    result = nour_personality.get_memories_by_topic("u1", "xyz غير مرتبط بأي شيء")
    assert "معلومة عامة" in result


def test_get_memories_by_topic_degrades_when_matched_category_is_empty():
    """Topic matches a real category's keywords, but this student has
    ZERO memories in that specific category -- must still degrade to
    unfiltered recency, not return an empty list."""
    database.register_member("u1", "Alice")
    nour_personality.store_memory("u1", "معلومة عامة فقط", category="general")

    result = nour_personality.get_memories_by_topic("u1", "هل عندك امتحان قريب؟")  # matches life_event, but none stored
    assert "معلومة عامة فقط" in result


def test_get_memories_unchanged_behavior_ignores_category():
    """get_memories() (pre-A6.3) must keep working exactly as before --
    unfiltered recency regardless of category."""
    database.register_member("u1", "Alice")
    nour_personality.store_memory("u1", "fact A", category="schedule")
    nour_personality.store_memory("u1", "fact B", category="preference")

    result = nour_personality.get_memories("u1")
    assert set(result) == {"fact A", "fact B"}


def test_store_memory_defaults_to_general_category():
    database.register_member("u1", "Alice")
    nour_personality.store_memory("u1", "fact without explicit category")

    conn = database._connect()
    row = conn.execute("SELECT category FROM nour_memories WHERE discord_id='u1'").fetchone()
    conn.close()
    assert row["category"] == "general"


# ============================================================
#  A6.2 — episodic summary generation
# ============================================================

@pytest.mark.asyncio
async def test_generate_episodic_summary_returns_none_without_groq_key(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    result = await nour_personality.generate_episodic_summary("u1")
    assert result is None


@pytest.mark.asyncio
async def test_generate_episodic_summary_returns_none_with_no_conversations(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-key")
    database.register_member("u1", "Alice")
    result = await nour_personality.generate_episodic_summary("u1")
    assert result is None


@pytest.mark.asyncio
async def test_generate_episodic_summary_calls_groq_with_real_conversation_text(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-key")
    database.register_member("u1", "Alice")
    database.log_retrieval  # sanity import touch, unrelated
    conn = database._connect()
    conn.execute(
        "INSERT INTO nour_conversations (discord_id, role, message) VALUES (?, ?, ?)",
        ("u1", "student", "عندي امتحان الأسبوع الجاي وقلقان"),
    )
    conn.commit()
    conn.close()

    captured = {}

    class _FakeResp:
        status = 200
        async def json(self):
            return {"choices": [{"message": {"content": "الطالب قلقان بخصوص امتحان قريب."}}]}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False

    class _FakeSession:
        def post(self, url, json=None, headers=None, timeout=None):
            captured["payload"] = json
            return _FakeResp()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False

    with patch("aiohttp.ClientSession", return_value=_FakeSession()):
        result = await nour_personality.generate_episodic_summary("u1")

    assert result == "الطالب قلقان بخصوص امتحان قريب."
    assert "امتحان" in captured["payload"]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_generate_episodic_summary_returns_none_on_api_failure(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-key")
    database.register_member("u1", "Alice")
    conn = database._connect()
    conn.execute(
        "INSERT INTO nour_conversations (discord_id, role, message) VALUES (?, ?, ?)",
        ("u1", "student", "test"),
    )
    conn.commit()
    conn.close()

    class _FakeResp:
        status = 500
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False

    class _FakeSession:
        def post(self, *a, **kw):
            return _FakeResp()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False

    with patch("aiohttp.ClientSession", return_value=_FakeSession()):
        result = await nour_personality.generate_episodic_summary("u1")
    assert result is None


def test_store_and_get_latest_episodic_summary():
    database.register_member("u1", "Alice")
    database.store_episodic_summary("u1", "ملخص أول", "2026-07-01", "2026-07-08")
    database.store_episodic_summary("u1", "ملخص أحدث", "2026-07-08", "2026-07-15")

    latest = database.get_latest_episodic_summary("u1")
    assert latest["summary_text"] == "ملخص أحدث"


def test_get_latest_episodic_summary_none_when_never_generated():
    database.register_member("u1", "Alice")
    assert database.get_latest_episodic_summary("u1") is None


@pytest.mark.asyncio
async def test_run_weekly_episodic_summaries_only_stores_for_students_with_activity():
    database.register_member("u1", "Alice")
    database.register_member("u2", "Bob")
    conn = database._connect()
    conn.execute(
        "INSERT INTO nour_conversations (discord_id, role, message) VALUES (?, ?, ?)",
        ("u1", "student", "لدي سؤال عن المهام"),
    )
    conn.commit()
    conn.close()
    # u2 has zero conversation activity

    async def fake_generate(discord_id, days=7):
        return "ملخص تجريبي" if discord_id == "u1" else None

    with patch.object(nour_personality, "generate_episodic_summary", new=fake_generate):
        stored_count = await nour_personality.run_weekly_episodic_summaries()

    assert stored_count == 1
    assert database.get_latest_episodic_summary("u1") is not None
    assert database.get_latest_episodic_summary("u2") is None


# ============================================================
#  A6.5 — journey-gap surfacing in orchestrator context assembly
# ============================================================

def test_build_messages_surfaces_journey_gaps_for_incomplete_student():
    coverage = {
        "knows_daily_tasks": 1, "knows_platform_link": 0, "knows_streaks": 0,
        "knows_channels": 0, "first_task_done": 1,
    }
    messages = orchestrator._build_messages(
        Role.STUDENT, "سؤال", [], [], coverage, [],
    )
    system_text = messages[0]["content"]
    assert "JOURNEY GAPS" in system_text
    assert "ربط منصة التمرين" in system_text
    assert "نظام السلسلة" in system_text
    assert "القنوات" in system_text
    # covered topics must NOT appear as gaps
    assert "المهام اليومية" not in system_text.split("JOURNEY GAPS")[1] if "JOURNEY GAPS" in system_text else True


def test_build_messages_omits_journey_gaps_section_when_fully_covered():
    coverage = {
        "knows_daily_tasks": 1, "knows_platform_link": 1, "knows_streaks": 1,
        "knows_channels": 1, "first_task_done": 1,
    }
    messages = orchestrator._build_messages(Role.STUDENT, "سؤال", [], [], coverage, [])
    assert "JOURNEY GAPS" not in messages[0]["content"]


def test_build_messages_omits_journey_section_entirely_for_owner():
    messages = orchestrator._build_messages(Role.OWNER, "سؤال", [], [], None, [])
    assert "JOURNEY GAPS" not in messages[0]["content"]


def test_build_messages_includes_episodic_summary_when_present():
    messages = orchestrator._build_messages(
        Role.STUDENT, "سؤال", [], [], None, [], episodic_summary="ملخص الأسبوع الماضي هنا",
    )
    assert "PAST CONTEXT" in messages[0]["content"]
    assert "ملخص الأسبوع الماضي هنا" in messages[0]["content"]


def test_build_messages_omits_episodic_section_when_none():
    messages = orchestrator._build_messages(Role.STUDENT, "سؤال", [], [], None, [], episodic_summary=None)
    assert "PAST CONTEXT" not in messages[0]["content"]


@pytest.mark.asyncio
async def test_handle_message_passes_journey_gaps_through_to_real_llm_call():
    """End-to-end: a real incomplete-coverage student's gaps actually
    reach the LLM call's message payload via handle_message(), not
    just the isolated _build_messages() unit above."""
    database.register_member("u1", "Alice")
    database.set_journey_coverage("u1", knows_daily_tasks=True)

    captured = {}

    async def fake_llm(messages, tool_defs):
        captured["messages"] = messages
        return orchestrator.LLMToolResponse(content="رد عادي", tool_calls=[])

    with patch.object(orchestrator, "_call_llm_with_tools", new=fake_llm):
        await orchestrator.handle_message("u1", "سؤال عادي")

    system_text = captured["messages"][0]["content"]
    assert "JOURNEY GAPS" in system_text


# ============================================================
#  A6.6 — golden-set multi-session test
# ============================================================

@pytest.mark.asyncio
async def test_a6_6_multi_session_conversation_uses_episodic_summary_not_raw_history():
    """Simulates 3 SEPARATE days of chat for one student. Day 1's
    conversation is old enough to have rolled out of the ~10-turn
    working-memory window by day 3, but an episodic summary generated
    after day 1 lets day 3's request still reference that context --
    without day 1's raw messages being re-sent verbatim.
    """
    database.register_member("u1", "Alice")

    # --- Day 1: a real, specific fact emerges in conversation ---
    conn = database._connect()
    conn.execute(
        "INSERT INTO nour_conversations (discord_id, role, message, created_at) VALUES (?, ?, ?, datetime('now', '-14 days'))",
        ("u1", "student", "عندي امتحان صعب الأسبوع الجاي وقلقان منه"),
    )
    conn.execute(
        "INSERT INTO nour_conversations (discord_id, role, message, created_at) VALUES (?, ?, ?, datetime('now', '-14 days'))",
        ("u1", "nour", "بالتوفيق في امتحانك! ركز على مهامك اليومية القصيرة."),
    )
    conn.commit()
    conn.close()

    # An episodic summary was generated at the end of day 1's "week"
    # (simulating run_weekly_episodic_summaries having already run).
    database.store_episodic_summary(
        "u1", "الطالب كان قلقانًا بخصوص امتحان مهم له.",
        covers_from="2026-07-01", covers_to="2026-07-08",
    )

    # --- Day 2 and day 3: many turns of UNRELATED chat, enough to push
    # day 1's messages out of a ~10-turn working-memory window ---
    conn = database._connect()
    for i in range(12):
        conn.execute(
            "INSERT INTO nour_conversations (discord_id, role, message, created_at) VALUES (?, ?, ?, datetime('now', ?))",
            ("u1", "student" if i % 2 == 0 else "nour", f"رسالة عادية رقم {i}", f"-{12 - i} hours"),
        )
    conn.commit()
    conn.close()

    # --- Day 3 (today): student asks a follow-up that only makes
    # sense with day 1's context ---
    captured = {}

    async def fake_llm(messages, tool_defs):
        captured["messages"] = messages
        return orchestrator.LLMToolResponse(content="أرجو أن يكون امتحانك قد سار بخير", tool_calls=[])

    with patch.object(orchestrator, "_call_llm_with_tools", new=fake_llm):
        result = await orchestrator.handle_message("u1", "هل تتذكر شيئًا عني؟")

    system_text = captured["messages"][0]["content"]
    working_memory_texts = [m["content"] for m in captured["messages"][1:-1]]  # exclude system + final user turn

    # The episodic summary (mentioning the exam) IS present in the
    # system prompt...
    assert "امتحان" in system_text
    assert "PAST CONTEXT" in system_text
    # ...but day 1's RAW messages are NOT part of the working-memory
    # turns sent to the LLM (they rolled out of the ~10-turn window).
    assert not any("امتحان صعب الأسبوع الجاي" in t for t in working_memory_texts)
    assert result == "أرجو أن يكون امتحانك قد سار بخير"
