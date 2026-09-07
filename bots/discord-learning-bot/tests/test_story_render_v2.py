"""Tests for the v2 story renderer + cast registry (spec Phase 1).

Covers the three things Phase 1 changed, and pins the defects that were measured in
v1 so they cannot come back:
  * engine/cast correctness (deterministic Kokoro cast + Mai's clone, all distinct);
  * speech flow (crossfaded joins, sentence-boundary chunking, faded gap edges);
  * mastering (-16 LUFS, true-peak ceiling, and the limiter that must not click).

The heavy engines are never loaded here — only the pure signal/text helpers, so the
suite stays fast and runs anywhere.
"""
import importlib.util
import pathlib

import numpy as np
import pytest

from src import audio_standards as STD
from src import sawt_cast

BOT_DIR = pathlib.Path(__file__).resolve().parent.parent


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, BOT_DIR / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rv2 = _load("render_story_v2", "scripts/render_story_v2.py")
qa = _load("audio_qa", "scripts/audio_qa.py")
SR = 24000


def _tone(seconds=1.0, freq=160.0, amp=0.4, sr=SR):
    t = np.arange(int(sr * seconds)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype("float32")


# ── cast registry ────────────────────────────────────────────────────────────
def test_every_character_has_its_own_voice():
    """R2.5: distinctness must come from DIFFERENT voices, never from processing
    one voice into several (which is how 'Leo sounded like Mai' happened)."""
    voices = sawt_cast.voices_in_use()
    assert len(set(voices.values())) == len(voices), (
        f"two characters share a voice: {voices}")


def test_cast_is_complete_and_gendered():
    for key, e in sawt_cast.CAST.items():
        assert e["display"], key
        assert e["gender"] in ("male", "female"), key
        assert e["engine"] in (sawt_cast.ENGINE_KOKORO, sawt_cast.ENGINE_CLONE), key
        assert e.get("voice_id") or e.get("clone_ref"), key
        assert e["match"], key
        assert e["role"], key


def test_maya_voice_is_configured():
    """v1 LAUNCH (2026-09-07): Maya is TEMPORARILY voiced by Kokoro, not Mai's
    Chatterbox clone — the clone engine was the pipeline's slowest + flakiest part
    (see sawt_cast for the rationale), so Kokoro-only ships a fast, reliable episode
    now. Mai's real voice is a planned upgrade. Either engine is valid here; what
    matters is Maya has a real, resolvable voice with a distinct id.

    When Mai's clone is restored, this test still passes (it accepts either engine)."""
    maya = sawt_cast.CAST["maya"]
    assert maya["engine"] in (sawt_cast.ENGINE_KOKORO, sawt_cast.ENGINE_CLONE)
    assert maya.get("voice_id") or maya.get("clone_ref")
    if maya["engine"] == sawt_cast.ENGINE_CLONE:
        assert "mai" in maya["clone_ref"].lower()


def test_all_cast_voices_are_distinct():
    """Distinctness (spec R2.5): no two characters share the same engine-qualified
    voice. Especially important now Maya is a Kokoro voice — she must not collide
    with Sara/Mrs. Adel/Nour."""
    voices = sawt_cast.voices_in_use()
    assert len(set(voices.values())) == len(voices), voices


def test_no_cast_voice_fails_the_naturalness_gate():
    """Voices that fail NATURALNESS are genuinely unusable — unlike small glitch
    counts, which the de-click stage provably repairs. am_michael measured
    0.014-0.016 (limit 0.012) and was the narrator the owner called unclear, so it
    must never be cast; the worst glitch offenders (am_puck 5-9, af_jessica 6) are
    also kept out to spare the repair stage unnecessary work."""
    unusable = {"am_michael", "af_nicole",      # fail naturalness
                "am_puck", "af_jessica"}        # worst measured glitch counts
    for key, e in sawt_cast.CAST.items():
        vid = e.get("voice_id")
        if vid:
            assert vid not in unusable, f"{key} uses {vid}, which failed a gate"


def test_character_lookup_and_fallback():
    assert sawt_cast.character_for("Narrator")["key"] == "narrator"
    assert sawt_cast.character_for("Maya")["key"] == "maya"
    assert sawt_cast.character_for("The Stranger")["key"] == "stranger"
    assert sawt_cast.character_for("Mrs. Adel")["key"] == "mrs_adel"
    # Unknown speakers fall back to the narrator rather than inheriting a voice.
    assert sawt_cast.character_for("Zorblax")["key"] == "narrator"
    assert sawt_cast.character_for("")["key"] == "narrator"


def test_pace_is_native_and_graded_by_level():
    """Pace comes from the CEFR profile at synthesis time. Lower level = slower."""
    a1 = sawt_cast.speed_for_level("A1", "leo")
    a2 = sawt_cast.speed_for_level("A2", "leo")
    b1 = sawt_cast.speed_for_level("B1", "leo")
    assert a1 < a2 < b1, (a1, a2, b1)
    # The narrator is slower than the cast at the same level (storytelling cadence).
    assert sawt_cast.speed_for_level("A2", "narrator") < a2


def test_generator_prompt_material_matches_the_registry():
    """The writer may only use characters the renderer can voice."""
    brief = sawt_cast.cast_brief()
    for name in sawt_cast.speaking_names():
        assert name in brief


# ── text preparation ─────────────────────────────────────────────────────────
def test_spoken_text_strips_markers_and_directions():
    out = rv2.spoken_text("(low) The door opened. [SFX:creak] [PAUSE 2s] Then silence.")
    assert "low" not in out.lower()
    assert "sfx" not in out.lower() and "creak" not in out.lower()
    assert "pause" not in out.lower()
    assert "The door opened." in out and "Then silence." in out


def test_chunking_splits_on_sentence_boundaries_only():
    text = ("First sentence here. Second sentence here! Third one? Fourth one.")
    chunks = rv2.chunk_text(text, limit=200)
    assert chunks == ["First sentence here.", "Second sentence here!",
                      "Third one?", "Fourth one."]


def test_chunking_never_splits_mid_word():
    long_sentence = "word " * 200
    for c in rv2.chunk_text(long_sentence.strip(), limit=100):
        assert not c.startswith(" ") and not c.endswith(" ")
        # every chunk is whole words
        assert all(w == "word" for w in c.split())


def test_chunking_uses_clause_boundaries_for_long_sentences():
    s = ("This is a very long single sentence, which keeps going with clauses, "
         "and more clauses, and still more clauses, until it must be split.")
    chunks = rv2.chunk_text(s, limit=60)
    assert len(chunks) > 1
    # splits happen after clause punctuation, so each piece ends cleanly
    assert all(len(c) <= 80 for c in chunks), chunks


def test_chunking_empty_is_empty():
    assert rv2.chunk_text("") == []
    assert rv2.chunk_text("   ") == []


# ── speech flow ──────────────────────────────────────────────────────────────
def test_crossfade_append_produces_no_discontinuity():
    """R3.1 — THE fix for the hard-cut defect.

    Uses COSINE segments so each one ends at peak amplitude: joining +peak directly
    to -peak is an unambiguous step discontinuity (a sine over a whole number of
    half-cycles ends at zero, which would make the naive join accidentally clean and
    the test meaningless)."""
    t = np.arange(int(SR * 0.5)) / SR
    a = (0.4 * np.cos(2 * np.pi * 200.0 * t)).astype("float32")   # ends at +0.4
    b = (-0.4 * np.cos(2 * np.pi * 200.0 * t)).astype("float32")  # starts at -0.4
    naive = np.concatenate([a, b])
    faded = rv2.crossfade_append(a, b, SR)
    n_naive, _ = qa.measure_hard_cuts(naive, SR)
    n_faded, _ = qa.measure_hard_cuts(faded, SR)
    assert n_naive >= 1, "the naive join should be detectably discontinuous"
    assert n_faded == 0, f"crossfaded join still clicks ({n_faded})"


def test_crossfade_append_handles_empty_inputs():
    a = _tone(0.2)
    assert len(rv2.crossfade_append(np.zeros(0, dtype="float32"), a, SR)) == len(a)
    assert len(rv2.crossfade_append(a, np.zeros(0, dtype="float32"), SR)) == len(a)


def test_append_gap_fades_the_tail_so_the_edge_is_continuous():
    """Measured defect: appending silence to a buffer ending at non-zero amplitude
    is itself a click — 8 appeared once the body was mastered to -16 LUFS."""
    a = _tone(0.5, 200.0)                     # ends mid-cycle, non-zero
    raw = np.concatenate([a, np.zeros(int(SR * 0.3), dtype="float32")])
    faded = rv2.append_gap(a, SR, 0.3)
    # the faded version must end its speech at ~zero before the silence
    edge = int(SR * 0.5)
    assert abs(float(faded[edge - 1])) < abs(float(raw[edge - 1]))
    assert abs(float(faded[edge - 1])) < 0.02
    assert len(faded) == len(raw)


def test_append_gap_on_empty_buffer_is_just_silence():
    out = rv2.append_gap(np.zeros(0, dtype="float32"), SR, 0.2)
    assert len(out) == int(SR * 0.2)
    assert not np.any(np.abs(out) > 1e-6)


# ── mastering ────────────────────────────────────────────────────────────────
def test_master_hits_the_loudness_target():
    """v1 shipped every episode 6-8 dB too quiet; mastering must land on target."""
    quiet = _tone(6.0, 180.0, amp=0.02)
    out = rv2.master(quiet, SR)
    lufs = qa.measure_loudness(out, SR)
    assert lufs is not None
    assert abs(lufs - STD.LUFS_TARGET) <= STD.LUFS_TOLERANCE, lufs


def test_master_respects_the_true_peak_ceiling():
    hot = _tone(6.0, 180.0, amp=0.98)
    out = rv2.master(hot, SR)
    assert qa.measure_true_peak(out, SR) <= STD.TRUE_PEAK_MAX_DBTP


def test_master_limiter_does_not_introduce_clicks():
    """REGRESSION: the first limiter took minimum(smoothed, per-sample need), which
    reintroduced sharp per-sample dips and ADDED 10 clicks. A lookahead minimum
    followed by smoothing must stay click-free."""
    loud = _tone(6.0, 180.0, amp=0.95)
    out = rv2.master(loud, SR)
    cuts, where = qa.measure_hard_cuts(out, SR)
    assert cuts <= STD.HARD_CUTS_MAX, f"mastering introduced {cuts} clicks at {where}"


def test_master_handles_empty_and_silence():
    assert len(rv2.master(np.zeros(0, dtype="float32"), SR)) == 0
    out = rv2.master(np.zeros(SR, dtype="float32"), SR)
    assert len(out) == SR


# ── the banned transforms must stay banned (R2.4) ────────────────────────────
def test_no_time_stretch_or_pitch_shift_in_the_renderer():
    """Both were tried in v1 and measurably degraded clarity: a phase vocoder
    smears consonants, and pitch-shifting displaces formants. They must not return."""
    src = (BOT_DIR / "scripts" / "render_story_v2.py").read_text()
    assert "time_stretch" not in src
    assert "pitch_shift" not in src


def test_plan_reports_cast_without_loading_engines():
    script = ("Narrator: The night was cold.\n"
              "Maya: Is someone there?\n"
              "[SFX:creak]\n"
              "The Stranger: You should not have come.\n")
    p = rv2.plan(script)
    assert p["line_count"] == 3          # the bare [SFX] line is not dialogue
    assert set(p["cast"]) == {"narrator", "maya", "stranger"}
    assert p["cast"]["maya"]["engine"] == sawt_cast.CAST["maya"]["engine"]
    assert p["cast"]["narrator"]["engine"] == sawt_cast.ENGINE_KOKORO


# ── CEFR-driven episode length (R7.1) ────────────────────────────────────────
def test_episode_length_target_follows_cefr_level():
    from src import sawt_story
    a1_words, a1_min = sawt_story.target_length("A1")
    a2_words, a2_min = sawt_story.target_length("A2")
    b1_words, b1_min = sawt_story.target_length("B1")
    assert a1_words < a2_words < b1_words
    assert a1_min < a2_min < b1_min
    # and the target must land INSIDE the level's own gate window
    for lvl, (_w, mins) in (("A1", sawt_story.target_length("A1")),
                            ("A2", sawt_story.target_length("A2")),
                            ("B1", sawt_story.target_length("B1"))):
        lo, hi = STD.duration_window(lvl)
        assert lo <= mins * 60.0 <= hi, (lvl, mins * 60.0, lo, hi)


def test_prompt_states_the_length_requirement():
    from src import sawt_story
    p = sawt_story.build_story_prompt("recap", "choice", 2, level="A2")
    words, _ = sawt_story.target_length("A2")
    assert str(words) in p
    assert "hard requirement" in p.lower()



# ── LLM budget + retry ladder (hard-won, live-measured failure modes) ────────
def test_max_tokens_is_sized_from_the_episode_length():
    """Not a magic number: too small returns EMPTY content from the reasoning
    model, and too large is rejected with a rate-limit 429 ("Request too large")
    on the key's 8000 tokens-per-minute limit (the cap covers prompt+completion).
    Measured 2026-09-08: max_tokens=1600 wrote a full 930-word episode
    (completion_tokens=1337, finish_reason=stop) while staying TPM-safe."""
    from src import sawt_story
    a1 = sawt_story._max_tokens_for("A1")
    a2 = sawt_story._max_tokens_for("A2")
    b1 = sawt_story._max_tokens_for("B1")
    assert a1 <= a2 <= b1, (a1, a2, b1)
    # Inside the TPM-safe window proven to work against the live provider: big
    # enough to write the episode, small enough to avoid the 8000-TPM "too large".
    for v in (a1, a2, b1):
        assert 900 <= v <= 1600, v


@pytest.mark.asyncio
async def test_retry_ladder_shrinks_on_413_and_grows_on_empty_200():
    """Each failure mode needs the OPPOSITE response, which is why a blanket retry
    never fixed this:
        413           -> asked for too much  -> shrink
        200 + no text -> reasoning ran out   -> grow
    """
    from src import sawt_story

    class R:
        def __init__(self, ok, text, status):
            self.ok, self.text, self.status = ok, text, status

    seen = []

    async def fake_chat(payload, timeout_seconds, **kwargs):
        seen.append(payload["max_tokens"])
        if len(seen) == 1:
            return R(False, None, 413)       # too big
        if len(seen) == 2:
            return R(True, None, 200)        # too small (empty)
        return R(True, '{"ok":1}', 200)      # just right

    # Patch the REAL module's function (isolation-safe: replacing the module in
    # sys.modules leaks between tests, because `from . import groq_client` resolves
    # the already-bound package attribute).
    from src import config, groq_client
    orig_chat = groq_client.chat_completion
    orig_key = config.GROQ_API_KEY
    groq_client.chat_completion = fake_chat
    config.GROQ_API_KEY = "test-key"
    try:
        out = await sawt_story._call_llm_json("prompt", level="A2")
    finally:
        groq_client.chat_completion = orig_chat
        config.GROQ_API_KEY = orig_key

    assert out == '{"ok":1}'
    assert len(seen) == 3, seen
    assert seen[1] < seen[0], f"413 must SHRINK the budget: {seen}"
    assert seen[2] > seen[1], f"empty 200 must GROW the budget: {seen}"


def test_truncated_json_fails_cleanly_rather_than_crashing():
    """A capped completion yields invalid JSON; it must be rejected, not raise."""
    from src import sawt_story
    assert sawt_story._extract_json('{"title":"X","script":"Narrator: hel') is None
    assert sawt_story._valid_episode(None) is False



def test_rendered_pauses_never_exceed_the_dead_air_limit(tmp_path, monkeypatch):
    """A big [PAUSE] in the script must NOT create a silence run longer than the
    QA gate allows (DEAD_AIR_MAX_S). Regression for the production run that failed
    the gate on 'dead_air_s' because a [PAUSE 2s] stacked on a speaker-change gap.

    We stub synthesis with short voiced blips so the ONLY long silences are the
    composed gaps/pauses, then measure the worst silence run the same way the gate
    does."""
    import soundfile as sf
    qa = _load("audio_qa", "scripts/audio_qa.py")

    # Stub every line to 0.5s of tone so silence runs come only from gaps/pauses.
    def fake_synth_line(text, ch, level, kokoro, clone):
        n = int(rv2.SR * 0.5)
        t = np.linspace(0, 0.5, n, endpoint=False)
        return (0.2 * np.sin(2 * np.pi * 180 * t)).astype("float32")

    monkeypatch.setattr(rv2, "synth_line_for",
                        lambda *a, **k: fake_synth_line(a[0], a[1], a[2], None, None))
    # Neither real engine is available in the test env; stub their constructors so
    # render() doesn't try to load them (synth_line_for is stubbed anyway).
    monkeypatch.setattr(rv2, "KokoroEngine", lambda: object())
    monkeypatch.setattr(rv2, "CloneEngine", lambda ref: object())

    # Narrator only (kokoro) keeps the stub path simple while still exercising the
    # PAUSE handling; Maya would need the clone engine which we don't load in tests.
    script = ("Narrator: The house was very quiet tonight.\n"
              "Narrator: Is anyone there? [PAUSE 5s]\n"
              "Narrator: No one answered, and the light went out.\n")
    out = tmp_path / "ep.mp3"
    rv2.render(script, out, level="A2", music="none", sound_design=False)

    y, sr = sf.read(str(out))
    if y.ndim > 1:
        y = y.mean(axis=1)
    worst, _runs = qa.measure_dead_air(np.asarray(y, dtype="float32"), sr)
    assert worst <= STD.DEAD_AIR_MAX_S, f"worst silence {worst}s exceeds limit"



@pytest.mark.asyncio
async def test_story_uses_groq_primary_and_the_story_model_not_gemini(monkeypatch):
    """Story generation is Groq-PRIMARY (2026-09-07): Gemini kept 403/404-ing on the
    project key, so it must not be depended on. When Groq succeeds, Gemini is never
    called, and Groq is asked with the dedicated long-form story model."""
    from src import sawt_story, config, groq_client, ai_engine

    used_model = {}

    async def fake_chat(payload, timeout_seconds, **kwargs):
        used_model["model"] = payload["model"]

        class R:
            ok, text, status = True, '{"ok":1}', 200
        return R()

    gemini_called = {"n": 0}

    async def fake_gemini(*a, **k):
        gemini_called["n"] += 1
        return "SHOULD-NOT-BE-USED"

    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(groq_client, "chat_completion", fake_chat)
    monkeypatch.setattr(ai_engine, "_call_gemini", fake_gemini)

    out = await sawt_story._call_llm_json("prompt", level="A2")
    assert out == '{"ok":1}'
    assert gemini_called["n"] == 0, "Gemini must not be called when Groq succeeds"
    assert used_model["model"] == config.GROQ_STORY_MODEL
    # The story model must be one the production key can actually reach. Measured
    # 2026-09-07: NO Llama model is accessible to the key, so it must never be one.
    assert "llama" not in config.GROQ_STORY_MODEL.lower()



@pytest.mark.asyncio
async def test_story_tries_next_groq_model_on_404(monkeypatch):
    """Groq model access is per-key: a 404 on one model must move to the NEXT model
    in the chain, not fail generation. Regression for the key that 404s on
    llama-3.3-70b-versatile but works on a fallback."""
    from src import sawt_story, config, groq_client

    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(config, "GROQ_STORY_MODEL", "model-a")
    monkeypatch.setattr(config, "GROQ_STORY_MODEL_FALLBACKS", ["model-b", "model-c"])

    tried = []

    async def fake_chat(payload, timeout_seconds, **kwargs):
        tried.append(payload["model"])

        class R:
            pass
        r = R()
        if payload["model"] == "model-a":
            r.ok, r.text, r.status = False, None, 404      # not accessible
        else:
            r.ok, r.text, r.status = True, '{"ok":1}', 200  # model-b works
        return r

    monkeypatch.setattr(groq_client, "chat_completion", fake_chat)
    out = await sawt_story._call_llm_json("prompt", level="A2")
    assert out == '{"ok":1}'
    assert tried == ["model-a", "model-b"], tried   # moved on after the 404
