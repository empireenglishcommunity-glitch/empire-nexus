"""Tests for the OFFLINE podcast renderer (scripts/render_podcast_episode.py).

The renderer only uses heavy engines (kokoro-onnx / chatterbox) inside render();
its planning + pace helpers are pure and must work with nothing installed — that
is what CI exercises here. We import the module by path (it lives in scripts/,
not the src package) and check it reuses the bot's own parse/voice functions."""
import importlib.util
import pathlib

import pytest

BOT_DIR = pathlib.Path(__file__).resolve().parent.parent
RENDERER = BOT_DIR / "scripts" / "render_podcast_episode.py"


def _load():
    spec = importlib.util.spec_from_file_location("render_podcast_episode",
                                                  RENDERER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SCRIPT = """AI co-host: Welcome to the show!
Host (you): Good morning. صباح الخير.
AI co-host: Today, coffee.
[PAUSE]
Host (you): My favourite drink."""


def test_renderer_module_imports_without_engines():
    # Importing must NOT require kokoro-onnx or chatterbox (they load lazily).
    mod = _load()
    assert hasattr(mod, "render")
    assert hasattr(mod, "plan")


def test_plan_delegates_to_bot_and_detects_clone():
    mod = _load()
    p = mod.plan(SCRIPT)
    # Same result the bot's /generate-audio would show.
    from src import sawt_tts
    assert p == sawt_tts.plan_episode(SCRIPT)
    assert p["segment_count"] == 4          # [PAUSE] line is not a segment
    assert p["needs_clone"] is True         # "Host (you)" → owner clone
    assert p["voices"]["cohost_f"] == 2
    assert p["voices"]["owner"] == 2


def test_level_speed_is_graded_slow_to_fast():
    mod = _load()
    a1 = mod._level_speed("A1")     # very_slow
    b2 = mod._level_speed("B2")     # natural
    c2 = mod._level_speed("C2")     # native
    assert a1 < b2 < c2
    assert a1 == pytest.approx(0.72)
    assert c2 == pytest.approx(1.15)


def test_level_speed_unknown_level_falls_back():
    mod = _load()
    # cefr_key maps junk to A1, so an unknown level is the A1 (very_slow) speed.
    assert mod._level_speed("ZZ") == pytest.approx(0.72)


def test_pace_speed_table_covers_all_profile_paces():
    mod = _load()
    from src import config
    paces = {p["pace"] for p in config.PODCAST_LEVEL_PROFILES.values()}
    # Every pace descriptor a level can have must have a speed mapping.
    assert paces <= set(mod.PACE_SPEED)
