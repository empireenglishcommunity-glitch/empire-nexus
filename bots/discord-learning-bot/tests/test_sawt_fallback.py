"""Reliability: the daily build must ALWAYS produce a valid episode.

When the (free-tier) LLM is rate-limited or returns nothing usable, generation
falls back to a hand-written, gate-passing episode instead of returning None — so
the daily podcast never becomes "nothing". These tests prove the fallback is
valid at every level, rotates, and that generate_episode actually uses it when the
LLM yields nothing.
"""
import asyncio
import os
import re

import pytest

os.environ.setdefault("DISCORD_TOKEN", "x")
os.environ.setdefault("GUILD_ID", "1")
os.environ.setdefault("TIMEZONE", "UTC")


def _wc(script: str) -> int:
    return sum(len(re.sub(r"\[[^\]]*\]", "", l.split(":", 1)[1]).split())
               for l in script.splitlines() if ":" in l)


@pytest.mark.parametrize("level", ["A1", "A2", "B1"])
@pytest.mark.parametrize("epn", [1, 2, 3])
def test_fallback_is_valid_and_in_window(level, epn):
    from src import sawt_fallback as F, sawt_script_validator as V
    ep = F.build_fallback_episode(episode_number=epn, level=level, mood="mystery")
    lo, hi = V._level_word_window(level)
    assert lo <= _wc(ep["script"]) <= hi, (level, epn, _wc(ep["script"]), (lo, hi))
    problems = V.validate_episode(
        ep, level=level, episode_number=epn,
        arc={"genre": "mystery", "mood": "mystery",
             "curiosity": "unanswered-question", "established_facts": []})
    assert problems == [], f"{level} ep{epn}: {problems}"
    assert ep["is_fallback"] is True
    assert ep["vote_a"] and ep["vote_b"] and ep["vote_a"] != ep["vote_b"]


def test_fallback_rotates_between_episodes():
    from src import sawt_fallback as F
    titles = {F.build_fallback_episode(episode_number=n, level="A2")["title"]
              for n in range(1, 4)}
    assert len(titles) >= 2, "consecutive fallbacks should not be identical"


def test_fallback_only_uses_legal_cast():
    from src import sawt_fallback as F, sawt_cast
    legal = {n.lower() for n in sawt_cast.speaking_names()}
    ep = F.build_fallback_episode(episode_number=1, level="A2")
    speakers = {l.split(":", 1)[0].strip().lower()
                for l in ep["script"].splitlines() if ":" in l}
    assert speakers <= legal, f"illegal speakers: {speakers - legal}"


def test_generate_episode_returns_fallback_when_llm_gives_nothing(monkeypatch):
    """The core guarantee: if the LLM yields nothing usable, generate_episode
    returns a VALID fallback episode — never None."""
    from src import sawt_story

    async def _no_text(*a, **k):
        return None                                  # LLM produced nothing

    monkeypatch.setattr(sawt_story, "_call_llm_json", _no_text)
    ep = asyncio.run(sawt_story.generate_episode(
        previous_summary="", episode_number=2, level="A2",
        arc={"genre": "mystery", "mood": "mystery",
             "curiosity": "unanswered-question", "established_facts": []}))
    assert ep is not None, "must never return None — ship a fallback instead"
    assert ep.get("is_fallback") is True
    assert ep["script"] and ep["vote_a"] and ep["vote_b"]


def test_generate_episode_returns_fallback_when_llm_raises(monkeypatch):
    """A hard LLM error (e.g. network) also yields a fallback, not a crash/None."""
    from src import sawt_story

    async def _boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(sawt_story, "_call_llm_json", _boom)
    ep = asyncio.run(sawt_story.generate_episode(
        previous_summary="", episode_number=1, level="A2",
        arc={"genre": "mystery", "mood": "mystery",
             "curiosity": "unanswered-question", "established_facts": []}))
    assert ep is not None and ep.get("is_fallback") is True
