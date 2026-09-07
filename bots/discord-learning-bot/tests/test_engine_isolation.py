"""Engine isolation for the gated v2 renderer (Option A).

Kokoro (numpy>=2) and Chatterbox (numpy<2) cannot share one env. The renderer must
be able to synthesise each line in an isolated per-engine subprocess when configured,
while keeping the simple in-process path (server + tests) as the default. These tests
pin that routing WITHOUT needing either real engine installed.
"""
import importlib.util
import json
import pathlib

import numpy as np
import soundfile as sf


SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "scripts"


def _load_rv2(name="rsv_iso"):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / "render_story_v2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_worker():
    spec = importlib.util.spec_from_file_location("voice_worker", SCRIPTS / "voice_worker.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── defaults: isolation off ─────────────────────────────────────────────────
def test_isolation_off_by_default(monkeypatch):
    monkeypatch.delenv("EEC_ISOLATE_ENGINES", raising=False)
    mod = _load_rv2()
    assert mod.ISOLATION_ENABLED is False
    assert mod._worker_python_for("kokoro") == ""
    assert mod._worker_python_for("clone") == ""


def test_isolation_on_but_no_worker_stays_in_process(monkeypatch):
    monkeypatch.setenv("EEC_ISOLATE_ENGINES", "1")
    monkeypatch.delenv("EEC_KOKORO_PYTHON", raising=False)
    mod = _load_rv2()
    assert mod.ISOLATION_ENABLED is True
    # No worker configured => empty => the render loop uses the in-process engine.
    assert mod._worker_python_for("kokoro") == ""


def test_worker_python_read_from_env(monkeypatch):
    monkeypatch.setenv("EEC_ISOLATE_ENGINES", "1")
    monkeypatch.setenv("EEC_KOKORO_PYTHON", "/venvs/kokoro/bin/python")
    monkeypatch.setenv("EEC_CLONE_PYTHON", "/venvs/clone/bin/python")
    mod = _load_rv2()
    assert mod._worker_python_for("kokoro") == "/venvs/kokoro/bin/python"
    assert mod._worker_python_for("clone") == "/venvs/clone/bin/python"


# ── routing: synth_line_for chooses isolated vs in-process ──────────────────
def test_synth_line_for_uses_in_process_when_no_worker(monkeypatch):
    mod = _load_rv2()
    calls = {"in_process": 0, "isolated": 0}

    def fake_synth_line(text, ch, level, kokoro, clone):
        calls["in_process"] += 1
        return np.ones(100, dtype="float32")

    monkeypatch.setattr(mod, "synth_line", fake_synth_line)
    monkeypatch.setattr(mod, "_worker_python_for", lambda k: "")
    ch = {"key": "narrator", "display": "Narrator", "engine": "kokoro"}
    out = mod.synth_line_for("hello", ch, "A2", kokoro=object(), clone=None)
    assert calls["in_process"] == 1 and len(out) == 100


def test_synth_line_for_uses_isolated_cache_when_present(monkeypatch):
    """When a worker is configured and the batch cache has this line, use the cache
    (no in-process synthesis)."""
    mod = _load_rv2()
    calls = {"in_process": 0}
    monkeypatch.setattr(mod, "_worker_python_for", lambda k: "/venvs/x/bin/python")

    def fake_synth_line(*a, **k):
        calls["in_process"] += 1
        return np.zeros(1, dtype="float32")

    monkeypatch.setattr(mod, "synth_line", fake_synth_line)
    ch = {"key": "maya", "display": "Maya", "engine": mod.sawt_cast.ENGINE_CLONE}
    cache = {7: np.ones(200, dtype="float32")}
    out = mod.synth_line_for("hi", ch, "A2", kokoro=None, clone=None,
                             isolated_cache=cache, index=7)
    assert len(out) == 200 and calls["in_process"] == 0


def test_isolated_missing_line_without_in_process_engine_raises_cleanly(monkeypatch):
    """Under isolation the in-process engines are NOT loaded. If the batch worker
    didn't produce this line, synth_line_for must raise a clear RuntimeError —
    never call `.say` on a None engine (the crash seen in the first prod run)."""
    import pytest
    mod = _load_rv2()
    monkeypatch.setattr(mod, "_worker_python_for", lambda k: "/venvs/x/bin/python")
    ch = {"key": "narrator", "display": "Narrator", "engine": "kokoro"}
    with pytest.raises(RuntimeError, match="did not produce line"):
        mod.synth_line_for("hi", ch, "A2", kokoro=None, clone=None,
                           isolated_cache={}, index=3)


def test_batch_synth_groups_by_engine_and_caches(monkeypatch, tmp_path):
    """_batch_synth_isolated runs ONE worker per engine and returns a
    {index: audio} cache. We fake subprocess.run to write the manifest's WAVs."""
    import json
    import subprocess as _sp
    mod = _load_rv2()
    monkeypatch.setattr(mod, "_worker_python_for", lambda k: "/venvs/x/bin/python")

    engines_invoked = []

    class _R:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        kind = cmd[cmd.index("--engine") + 1]
        engines_invoked.append(kind)
        manifest = json.loads(pathlib.Path(cmd[cmd.index("--manifest") + 1]).read_text())
        for item in manifest:
            sf.write(item["out"], np.ones(24000, dtype="float32"), 24000)  # 1s @ SR
        return _R()

    monkeypatch.setattr(_sp, "run", fake_run)

    # Narrator (kokoro) + Maya (clone) + Narrator again -> 2 kokoro, 1 clone.
    segs = [("Narrator", "Hello there."), ("Maya", "I am here."),
            ("Narrator", "And so it began.")]
    cache = mod._batch_synth_isolated(segs, "A2", tmp_path)
    assert set(cache.keys()) == {1, 2, 3}          # all three lines cached
    assert sorted(engines_invoked) == ["clone", "kokoro"]   # one worker per engine
    for y in cache.values():
        assert len(y) == mod.SR                     # 1s @ SR


# ── worker contract (engine mocked) ─────────────────────────────────────────
def test_worker_synth_to_wav_writes_file_with_mocked_engine(monkeypatch, tmp_path):
    worker = _load_worker()
    rv2 = worker._load_rv2()

    # Replace synth_line so no real engine is needed; return 0.5s of audio @ SR.
    monkeypatch.setattr(rv2, "synth_line",
                        lambda text, ch, level, kokoro, clone:
                        np.ones(int(rv2.SR * 0.5), dtype="float32"))
    # Replace the engine constructors with trivial stand-ins.
    monkeypatch.setattr(rv2, "KokoroEngine", lambda: object())
    monkeypatch.setattr(worker, "_load_rv2", lambda: rv2)

    out = tmp_path / "line.wav"
    res = worker.synth_to_wav("kokoro", "Narrator", "A2", "hello there", str(out))
    assert res["ok"] is True and out.exists()
    y, sr = sf.read(str(out))
    assert sr == rv2.SR and len(y) > 0
    # atomic: no leftover .part file
    assert not (out.with_suffix(out.suffix + ".part")).exists()


def test_worker_batch_loads_engine_once_and_writes_all(monkeypatch, tmp_path):
    """synth_batch builds the engine ONCE (not per line) and writes every line's
    WAV. The one-load property is the whole reason the batch worker exists."""
    worker = _load_worker()
    rv2 = worker._load_rv2()
    builds = {"n": 0}

    def fake_build(kind, _rv2):
        builds["n"] += 1
        return object(), "kokoro"

    monkeypatch.setattr(worker, "_build_engine", fake_build)
    monkeypatch.setattr(worker, "_synth_one",
                        lambda *a, **k: np.ones(int(rv2.SR * 0.3), dtype="float32"))
    monkeypatch.setattr(worker, "_load_rv2", lambda: rv2)

    manifest = [
        {"index": 1, "character": "Narrator", "level": "A2", "text": "one",
         "out": str(tmp_path / "l1.wav")},
        {"index": 2, "character": "Narrator", "level": "A2", "text": "two",
         "out": str(tmp_path / "l2.wav")},
        {"index": 3, "character": "Narrator", "level": "A2", "text": "three",
         "out": str(tmp_path / "l3.wav")},
    ]
    res = worker.synth_batch("kokoro", manifest)
    assert res["ok"] is True
    assert builds["n"] == 1                      # engine loaded ONCE for 3 lines
    assert all((tmp_path / f"l{i}.wav").exists() for i in (1, 2, 3))
    assert {r["index"] for r in res["results"]} == {1, 2, 3}


def test_worker_batch_one_bad_line_does_not_abort(monkeypatch, tmp_path):
    worker = _load_worker()
    rv2 = worker._load_rv2()
    monkeypatch.setattr(worker, "_build_engine", lambda k, r: (object(), "kokoro"))

    def flaky(rv2_, engine, eid, kind, character, level, text):
        if text == "boom":
            raise RuntimeError("engine hiccup")
        return np.ones(int(rv2.SR * 0.3), dtype="float32")

    monkeypatch.setattr(worker, "_synth_one", flaky)
    monkeypatch.setattr(worker, "_load_rv2", lambda: rv2)
    manifest = [
        {"index": 1, "character": "Narrator", "text": "ok", "out": str(tmp_path / "a.wav")},
        {"index": 2, "character": "Narrator", "text": "boom", "out": str(tmp_path / "b.wav")},
    ]
    res = worker.synth_batch("kokoro", manifest)
    assert res["ok"] is False                    # batch reports partial failure
    r_by_i = {r["index"]: r for r in res["results"]}
    assert r_by_i[1]["ok"] is True and r_by_i[2]["ok"] is False
    assert (tmp_path / "a.wav").exists()          # good line still written


def test_worker_cli_empty_text_exits_2():
    import subprocess
    import sys
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "voice_worker.py"),
         "--engine", "kokoro", "--character", "Narrator", "--level", "A2",
         "--text", "", "--out", "/tmp/should_not_exist.wav"],
        capture_output=True, text=True)
    assert r.returncode == 2
    assert '"ok": false' in (r.stderr or "").lower() or "empty text" in r.stderr
