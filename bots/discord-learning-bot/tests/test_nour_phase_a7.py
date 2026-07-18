"""Tests for Aql (#15) Phase A7 — Rawiya Absorption.

Covers:
- A7.1: nour_proactive's message generation is redirected through
  guarded_generate() -- detection logic itself confirmed unchanged.
- A7.3: the 8 tutorials are chunked/embedded verbatim (never
  paraphrased) under the `tutorials` domain, and are retrievable.
- A7.5: regression test -- every one of the 4 REAL proactive
  detection checks in nour_proactive.py still fires correctly (the
  module docstring/flag_registry's stale "9 conditions"/"5 conditions"
  claims are corrected as part of this same phase, documented in
  nour_proactive.py's own module docstring).
"""
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from src import config, database, nour_proactive
from src.nour import permissions
from src.nour.knowledge.chunker import chunk_markdown_file
from src.nour.knowledge.embedder import pack_embedding
from src.nour.roles import Role
from src.nour_tutorials import TUTORIALS

TUTORIALS_MD = (
    Path(__file__).resolve().parent.parent / "data" / "nour_knowledge" / "tutorials.md"
)


# ============================================================
#  A7.3 — tutorials are chunked verbatim, never paraphrased
# ============================================================

def test_tutorials_md_exists():
    assert TUTORIALS_MD.exists()


def test_tutorials_md_produces_exactly_8_chunks():
    chunks = chunk_markdown_file(TUTORIALS_MD, "tutorials")
    assert len(chunks) == 8


def test_every_tutorial_chunk_is_byte_for_byte_verbatim():
    """THE core A7.3 requirement: chunk content must be an EXACT match
    to the original TUTORIALS dict value -- any paraphrasing at all
    (even whitespace normalization) would violate design.md Section
    8.3's "pre-verified-correct content, retrieved and quoted, not
    regenerated" guarantee."""
    chunks = chunk_markdown_file(TUTORIALS_MD, "tutorials")
    original_values = list(TUTORIALS.values())
    assert len(chunks) == len(original_values)
    for chunk, original in zip(chunks, original_values):
        assert chunk.content == original, (
            f"chunk {chunk.heading!r} does not exactly match the original "
            f"TUTORIALS text -- verbatim guarantee violated"
        )


def test_tutorials_domain_is_a_student_accessible_domain():
    assert "tutorials" in permissions.get_knowledge_domains(Role.STUDENT)
    assert "tutorials" in permissions.get_knowledge_domains(Role.OWNER)


def test_generate_tutorials_kb_script_output_matches_committed_file():
    """Same staleness-detection pattern as A2.4's flag_registry_reference
    test -- the committed tutorials.md must be byte-identical to what
    the generator produces right now from the real TUTORIALS dict."""
    import importlib
    import sys
    scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
    sys.path.insert(0, scripts_dir)
    try:
        gen = importlib.import_module("generate_tutorials_kb")
        importlib.reload(gen)
        expected = gen.generate_markdown()
    finally:
        sys.path.remove(scripts_dir)

    actual = TUTORIALS_MD.read_text(encoding="utf-8")
    assert actual == expected, (
        "data/nour_knowledge/tutorials.md is stale -- run "
        "scripts/generate_tutorials_kb.py to regenerate it"
    )


@pytest.mark.asyncio
async def test_tutorial_content_is_retrievable_for_student_role():
    """End-to-end: index one real tutorial chunk and confirm a
    student-role retrieve() call can actually surface it."""
    from src.nour.knowledge.retriever import retrieve

    chunks = chunk_markdown_file(TUTORIALS_MD, "tutorials")
    recording_chunk = next(c for c in chunks if "تسجّل" in c.heading)
    database.insert_knowledge_chunk(
        domain=recording_chunk.domain, source_file=recording_chunk.source_file,
        heading=recording_chunk.heading, content=recording_chunk.content,
        embedding=pack_embedding(np.random.rand(768).astype(np.float32)),
        embedding_model="gemini-embedding-001",
    )

    async def fake_embed(text, task_type="RETRIEVAL_QUERY"):
        return np.random.rand(768).astype(np.float32)

    with patch("src.nour.knowledge.retriever.embed_text", new=fake_embed):
        results = await retrieve("كيف أسجل صوتي على الموبايل", Role.STUDENT, top_k=4)

    tutorial_results = [r for r in results if r.domain == "tutorials"]
    assert len(tutorial_results) >= 1
    # The retrieved content must be the UNMODIFIED original text.
    assert tutorial_results[0].content == TUTORIALS["recording_mobile"]


# ============================================================
#  A7.1 — proactive message generation redirected through guardrails
# ============================================================

@pytest.mark.asyncio
async def test_generate_proactive_message_passes_through_guardrails_on_success():
    """A clean, guardrail-passing Groq response must be returned
    unmodified -- confirms guarded_generate() is genuinely in the
    call path, not bypassed."""
    async def fake_call(student_name, context, outreach_type, correction_hint=None):
        return "مرحبًا بك! أتمنى لك يومًا سعيدًا في التعلّم 😊"

    with patch.object(nour_proactive, "_call_groq_for_proactive_message", new=fake_call):
        result = await nour_proactive._generate_proactive_message(
            "أحمد", "test context", "new_student", discord_id="u1"
        )
    assert result == "مرحبًا بك! أتمنى لك يومًا سعيدًا في التعلّم 😊"


@pytest.mark.asyncio
async def test_generate_proactive_message_guardrail_failure_gets_corrected():
    """A script-conformance-failing first attempt must be retried with
    a correction hint (guarded_generate()'s real retry tier), not
    returned as-is."""
    calls = []

    async def fake_call(student_name, context, outreach_type, correction_hint=None):
        calls.append(correction_hint)
        if correction_hint:
            return "مرحبًا بك، رسالة مصححة بالكامل بالعربية"
        return "Hello this entire message is broken English with zero Arabic"

    with patch.object(nour_proactive, "_call_groq_for_proactive_message", new=fake_call):
        result = await nour_proactive._generate_proactive_message(
            "أحمد", "test context", "quiet_student", discord_id="u1"
        )

    assert len(calls) == 2
    assert calls[1] is not None  # a real correction hint was passed on retry
    assert result == "مرحبًا بك، رسالة مصححة بالكامل بالعربية"


@pytest.mark.asyncio
async def test_generate_proactive_message_falls_back_to_guardrail_template_on_persistent_failure():
    """If the guardrail-correction retry ALSO fails, the result must
    be one of guarded_generate()'s OWN template responses -- NOT this
    module's raw broken text, and not a crash."""
    from src.nour_concierge import _TEMPLATE_RESPONSES

    async def always_broken(student_name, context, outreach_type, correction_hint=None):
        return "This stays completely broken English no matter what correction is applied"

    with patch.object(nour_proactive, "_call_groq_for_proactive_message", new=always_broken):
        result = await nour_proactive._generate_proactive_message(
            "أحمد", "test context", "score_drop", discord_id="u1"
        )
    assert result in _TEMPLATE_RESPONSES


@pytest.mark.asyncio
async def test_call_groq_for_proactive_message_appends_correction_hint_to_prompt():
    """Confirms the correction_hint is actually threaded into the real
    Groq call's prompt text, not silently dropped."""
    captured = {}

    class _FakeResp:
        status = 200
        async def json(self):
            return {"choices": [{"message": {"content": "رد تجريبي"}}]}
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
        await nour_proactive._call_groq_for_proactive_message(
            "أحمد", "ctx", "new_student", correction_hint="[تصحيح تجريبي]",
        )

    user_message = captured["payload"]["messages"][1]["content"]
    assert "[تصحيح تجريبي]" in user_message


# ============================================================
#  A7.5 — regression test: all 4 real proactive triggers still fire
# ============================================================

class _FakeMember:
    def __init__(self, discord_id):
        self.id = int(discord_id)
        self.display_name = "TestMember"
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


class _FakeGuild:
    def __init__(self, members: dict):
        self._members = members

    def get_member(self, discord_id: int):
        return self._members.get(discord_id)


class _FakeBot:
    def __init__(self, guild):
        self._guild = guild

    def get_guild(self, guild_id):
        return self._guild


@pytest.fixture
def _patch_generation():
    """Avoid any real network call for the message-generation step --
    A7.5 is testing DETECTION, not generation (already covered above)."""
    async def fake_gen(name, context, outreach_type, discord_id=""):
        return f"رسالة تجريبية لـ {outreach_type}"
    with patch.object(nour_proactive, "_generate_proactive_message", new=fake_gen):
        yield


@pytest.mark.asyncio
async def test_trigger_new_student_fires_correctly(monkeypatch, _patch_generation):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-key")
    monkeypatch.setattr(database, "is_feature_enabled", lambda name, *a: name == "nour_proactive")

    conn = database._connect()
    conn.execute(
        "INSERT INTO members (discord_id, discord_name, joined_at, last_active_at) VALUES (?, ?, datetime('now', '-30 hours'), datetime('now'))",
        ("111", "NewGuy"),
    )
    conn.commit()
    conn.close()

    member = _FakeMember("111")
    guild = _FakeGuild({111: member})
    bot = _FakeBot(guild)

    with patch.object(nour_proactive, "_last_outreach_time", return_value=None):
        await nour_proactive.run_proactive_checks(bot)

    assert len(member.sent) == 1
    assert "new_student" in member.sent[0]


@pytest.mark.asyncio
async def test_trigger_quiet_student_fires_correctly(monkeypatch, _patch_generation):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-key")
    monkeypatch.setattr(database, "is_feature_enabled", lambda name, *a: name == "nour_proactive")

    conn = database._connect()
    conn.execute(
        "INSERT INTO members (discord_id, discord_name, joined_at, last_active_at, current_streak) "
        "VALUES (?, ?, datetime('now', '-30 days'), datetime('now', '-3 days'), 5)",
        ("112", "QuietGuy"),
    )
    conn.commit()
    conn.close()

    member = _FakeMember("112")
    guild = _FakeGuild({112: member})
    bot = _FakeBot(guild)

    with patch.object(nour_proactive, "_last_outreach_time", return_value=None):
        await nour_proactive.run_proactive_checks(bot)

    assert len(member.sent) == 1
    assert "quiet_student" in member.sent[0]


@pytest.mark.asyncio
async def test_trigger_score_drop_fires_correctly(monkeypatch, _patch_generation):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-key")
    monkeypatch.setattr(database, "is_feature_enabled", lambda name, *a: name == "nour_proactive")

    import datetime as _dt
    database.register_member("113", "DropGuy")
    database.update_member("113", joined_at="2020-01-01 00:00:00")
    # get_recent_scores() orders by scored_at DESC -- inserting all 4
    # rows via store_pronunciation_score() in the same test would give
    # them an identical scored_at (same wall-clock second), making the
    # DESC ordering ambiguous/insertion-order-dependent rather than
    # reflecting real recency. Insert with EXPLICIT, distinct scored_at
    # timestamps so [0:2] deterministically means "most recent 2".
    conn = database._connect()
    dates_and_scores = [(3, 90.0), (2, 88.0), (1, 50.0), (0, 45.0)]
    for days_ago, score in dates_and_scores:
        date_str = (_dt.date.today() - _dt.timedelta(days=days_ago)).isoformat()
        scored_at = (_dt.datetime.now() - _dt.timedelta(days=days_ago)).isoformat()
        conn.execute(
            """INSERT INTO pronunciation_scores
               (discord_id, date, task_id, score, expected_text, transcript, scored_at)
               VALUES (?, ?, 'accent', ?, 'x', 'y', ?)""",
            ("113", date_str, score, scored_at),
        )
    conn.commit()
    conn.close()

    member = _FakeMember("113")
    guild = _FakeGuild({113: member})
    bot = _FakeBot(guild)

    with patch.object(nour_proactive, "_last_outreach_time", return_value=None):
        await nour_proactive.run_proactive_checks(bot)

    assert len(member.sent) == 1
    assert "score_drop" in member.sent[0]


@pytest.mark.asyncio
async def test_trigger_first_milestone_fires_correctly(monkeypatch, _patch_generation):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-key")
    monkeypatch.setattr(database, "is_feature_enabled", lambda name, *a: name == "nour_proactive")

    database.register_member("114", "MilestoneGuy")
    database.update_member("114", joined_at="2020-01-01 00:00:00", current_streak=1)
    today = __import__("datetime").date.today().isoformat()
    for task_id in ["accent", "vocab", "shadow", "speaking", "listening", "writing", "community"]:
        database.log_submission("114", today, task_id)

    member = _FakeMember("114")
    guild = _FakeGuild({114: member})
    bot = _FakeBot(guild)

    with patch.object(nour_proactive, "_last_outreach_time", return_value=None):
        await nour_proactive.run_proactive_checks(bot)

    assert len(member.sent) == 1
    assert "first_milestone" in member.sent[0]


@pytest.mark.asyncio
async def test_no_trigger_fires_for_a_normal_healthy_student(monkeypatch, _patch_generation):
    """Negative case: a student matching none of the 4 conditions
    must receive nothing."""
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-key")
    monkeypatch.setattr(database, "is_feature_enabled", lambda name, *a: name == "nour_proactive")

    database.register_member("115", "NormalGuy")
    database.update_member("115", joined_at="2020-01-01 00:00:00", current_streak=10)

    member = _FakeMember("115")
    guild = _FakeGuild({115: member})
    bot = _FakeBot(guild)

    with patch.object(nour_proactive, "_last_outreach_time", return_value=None):
        await nour_proactive.run_proactive_checks(bot)

    assert len(member.sent) == 0


def test_proactive_docstring_accurately_reflects_four_real_checks():
    """Regression guard for the stale '9 conditions'/'5th check'
    documentation found during this phase's own audit -- confirms the
    module docstring lists exactly 4 numbered checks, matching the 4
    real detection branches in run_proactive_checks()."""
    doc = nour_proactive.__doc__
    assert "1. New students" in doc
    assert "2. Active students gone quiet" in doc
    assert "3. Score drops" in doc
    assert "4. First-time milestones" in doc
    assert "5. Return after absence" not in doc


def test_flag_registry_description_matches_real_condition_count():
    from src import flag_registry
    info = flag_registry.get_flag_info("nour_enhanced_proactive")
    assert "9 conditions" not in info["description"]
