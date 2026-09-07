"""End-to-end proof that engine isolation plumbing works WITHOUT a real TTS engine.

We point EEC_KOKORO_PYTHON / EEC_CLONE_PYTHON at a tiny fake 'python' (a shell shim)
that runs a stub worker writing a silent WAV. Then we render a 2-speaker script and
assert a real episode comes out — proving the subprocess round-trip, WAV read-back,
resample, assembly and mastering all work. This is the risky glue; the actual TTS is
covered by the engines' own correctness, exercised in CI.
"""
import importlib.util
import os
import pathlib
import stat

import numpy as np
import soundfile as sf

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "scripts"


def _load_rv2():
    spec = importlib.util.spec_from_file_location("rsv_e2e", SCRIPTS / "render_story_v2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_fake_worker_python(tmp_path):
    """Create an executable that mimics `python voice_worker.py ... --out X`: it
    parses --out and writes ~0.4s of quiet audio @ 24k there, then prints JSON."""
    stub = tmp_path / "fake_worker.py"
    stub.write_text(
        "import sys, json\n"
        "import numpy as np, soundfile as sf\n"
        "a = sys.argv\n"
        "def wav(p):\n"
        "    sf.write(p, (np.random.randn(9600).astype('float32')*0.05), 24000, format='WAV')\n"
        "if '--manifest' in a:\n"          # BATCH mode: write every line's out
        "    m = json.load(open(a[a.index('--manifest')+1]))\n"
        "    res = []\n"
        "    for it in m:\n"
        "        wav(it['out']); res.append({'index': it['index'], 'ok': True, 'seconds': 0.4})\n"
        "    print(json.dumps({'ok': True, 'results': res, 'sr': 24000}))\n"
        "else:\n"                          # single-line mode
        "    wav(a[a.index('--out')+1])\n"
        "    print(json.dumps({'ok': True, 'seconds': 0.4, 'sr': 24000}))\n",
        encoding="utf-8")
    # a shell shim that ignores the real voice_worker.py path arg and runs our stub
    shim = tmp_path / "fakepython"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        "# args: <voice_worker.py> --engine ... --out ... ; run our stub instead\n"
        'shift 1\n'                       # drop the voice_worker.py path
        f'exec {os.sys.executable} "{stub}" "$@"\n',
        encoding="utf-8")
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR)
    return str(shim)


def test_render_via_isolated_subprocess_workers(tmp_path, monkeypatch):
    fake_py = _make_fake_worker_python(tmp_path)
    monkeypatch.setenv("EEC_ISOLATE_ENGINES", "1")
    monkeypatch.setenv("EEC_KOKORO_PYTHON", fake_py)
    monkeypatch.setenv("EEC_CLONE_PYTHON", fake_py)

    mod = _load_rv2()          # re-read env for ISOLATION flags
    # A 2-speaker script: Narrator (kokoro) + Maya (clone) — both routed to workers.
    script = ("Narrator: Welcome to the story tonight.\n"
              "Maya: I am here, and I am listening.\n"
              "Narrator: And so it began.\n")
    out = tmp_path / "ep.mp3"
    res = mod.render(script, out, level="A2", music="none", sound_design=False)
    assert res["ok"] is True
    assert out.exists() and out.stat().st_size > 0
    # the assembled programme has real duration (3 short lines + gaps)
    assert res["duration_seconds"] > 0.5
    y, sr = sf.read(str(out))
    assert sr == mod.SR and len(y) > 0
