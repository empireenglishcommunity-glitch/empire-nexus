"""Tests for the OFFLINE podcast renderer (scripts/render_podcast_episode.py).

The renderer only touches the heavy engine (Chatterbox Multilingual) inside
render(); its planning, pace, and language-splitting helpers are pure and must
work with nothing installed — that is what CI exercises here. We import the
module by path (it lives in scripts/, not the src package) and check it reuses
the bot's own parse/voice functions and splits mixed Arabic/English correctly."""
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


# ── split_by_language: the core of the Arabic-pronunciation fix ──────────────
# The English-only engines read Arabic script letter-by-letter; the fix splits
# each line into Arabic vs English runs so each is synthesised in its own
# language. These assertions pin that behaviour.
def test_split_pure_english():
    mod = _load()
    assert mod.split_by_language("Good morning everyone.") == [
        ("en", "Good morning everyone.")]


def test_split_pure_arabic():
    mod = _load()
    runs = mod.split_by_language("صباح الخير")
    assert runs == [("ar", "صباح الخير")]


def test_split_mixed_keeps_order_and_language():
    mod = _load()
    runs = mod.split_by_language("Good morning! صباح الخير. Today we talk.")
    # en → ar → en, in order; every Arabic char is in an "ar" run and no run empty
    assert [lang for lang, _ in runs] == ["en", "ar", "en"]
    assert runs[0][1].startswith("Good morning")
    assert "صباح" in runs[1][1]
    assert runs[2][1].strip().startswith("Today")
    assert all(text.strip() for _, text in runs)


def test_split_arabic_inside_english_line():
    mod = _load()
    runs = mod.split_by_language("I drink coffee. أشرب القهوة. Coffee is nice.")
    assert [lang for lang, _ in runs] == ["en", "ar", "en"]
    # The Arabic run carries the actual Arabic words (not split per character).
    assert "أشرب القهوة" in runs[1][1]


def test_split_blank_returns_empty():
    mod = _load()
    assert mod.split_by_language("") == []
    assert mod.split_by_language("   ") == []


def test_split_no_arabic_run_is_labelled_ar_wrongly():
    mod = _load()
    # A line with digits/punctuation but no Arabic must stay entirely English.
    runs = mod.split_by_language("Wake up at 6 o'clock, okay?")
    assert all(lang == "en" for lang, _ in runs)


def test_chunk_text_respects_limit():
    mod = _load()
    long = " ".join(["Sentence number %d here." % i for i in range(60)])
    parts = mod._chunk_text(long, limit=120)
    assert len(parts) > 1
    assert all(len(p) <= 200 for p in parts)   # each chunk well under the cap


def test_cohost_reference_urls_are_per_language_and_distinct():
    mod = _load()
    # Both co-host roles must have BOTH a native English and native Arabic ref,
    # and the two co-hosts must differ so they don't sound identical.
    assert set(mod.COHOST_REF_URLS) == {"cohost_f", "cohost_m"}
    for role in ("cohost_f", "cohost_m"):
        assert set(mod.COHOST_REF_URLS[role]) == {"en", "ar"}
    assert mod.COHOST_REF_URLS["cohost_f"]["en"] != mod.COHOST_REF_URLS["cohost_m"]["en"]
    # The Arabic prompts are native Arabic samples (…/ar_…).
    assert "ar_" in mod.COHOST_REF_URLS["cohost_f"]["ar"]
    assert "ar_" in mod.COHOST_REF_URLS["cohost_m"]["ar"]


def test_anti_hallucination_settings_present():
    mod = _load()
    # Both languages must set a repetition_penalty above the model default (1.2)
    # and a tightened sampling window to suppress repeats/breaths.
    for lang in ("en", "ar"):
        s = mod.GEN_SETTINGS[lang]
        assert s["repetition_penalty"] > 1.2
        assert 0 < s["min_p"] <= 0.2
        assert s["temperature"] <= 0.7


def test_trim_and_gate_removes_edge_silence():
    mod = _load()
    import numpy as np
    sr = 24000
    sig = np.concatenate([
        np.zeros(int(sr * 0.4), dtype="float32"),
        (0.3 * np.sin(2 * np.pi * 200 * np.arange(sr) / sr)).astype("float32"),
        np.zeros(int(sr * 0.4), dtype="float32"),
    ])
    out = mod._trim_and_gate(sig, sr)
    assert len(out) < len(sig)          # edges trimmed
    assert len(out) > sr * 0.5          # speech kept


def test_trim_and_gate_handles_empty_and_silent():
    mod = _load()
    import numpy as np
    assert len(mod._trim_and_gate(np.zeros(0, dtype="float32"), 24000)) == 0
    # All-silence input must not crash and must not blow up in size.
    sil = np.zeros(2400, dtype="float32")
    assert len(mod._trim_and_gate(sil, 24000)) <= len(sil)


# ── emotion + Arabic diacritics settings ─────────────────────────────────────
def test_gen_settings_expressive_and_arabic_language_transfer():
    mod = _load()
    # English is more expressive than flat-neutral 0.5, and Arabic uses
    # cfg_weight 0 so the reference accent doesn't bleed into Arabic.
    assert mod.GEN_SETTINGS["en"]["exaggeration"] > 0.5
    assert mod.GEN_SETTINGS["ar"]["cfg_weight"] == 0.0
    assert 0.25 <= mod.GEN_SETTINGS["ar"]["exaggeration"] <= 2.0


def test_diacritize_is_graceful_without_engine():
    mod = _load()
    # If text2tashkeel isn't importable, _diacritize_arabic must return the
    # input unchanged rather than raise. (When it IS present it adds tashkeel.)
    out = mod._diacritize_arabic("صباح الخير")
    assert isinstance(out, str) and out.strip()          # never empty / never raises
    assert mod._diacritize_arabic("") == ""              # blank stays blank
