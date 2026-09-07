#!/usr/bin/env python3.12
"""Empire English Chronicles — single-line VOICE WORKER (engine isolation).

WHY THIS EXISTS
---------------
The two TTS engines the podcast uses cannot share one Python environment:
  * Kokoro (`kokoro-onnx`, the whole AI cast) requires **numpy >= 2**;
  * Chatterbox (`chatterbox-tts`, Mai's consented cloned voice) requires **numpy < 2**.
Installing both together forces a numpy downgrade and breaks one engine. Since a
normal episode has BOTH a Kokoro cast AND Maya, the gated v2 renderer would load
both in one process and fail.

This worker synthesises ONE line with ONE engine and writes it to a WAV. It is meant
to run in an ISOLATED virtualenv that has only that engine's dependencies, invoked as
a subprocess by the renderer (see render_story_v2._synth_line_isolated). It reuses the
renderer's own `synth_line` so the isolated output is identical to the in-process one
(same chunking, resample, soft-trim, crossfades).

Usage:
    python3 scripts/voice_worker.py \
        --engine kokoro|clone \
        --character "Maya" \
        --level A2 \
        --text "the spoken line" \
        --out /path/line.wav

    # or pass the text via a file (avoids shell-quoting long/edge-case lines):
    python3 scripts/voice_worker.py --engine kokoro --character Narrator \
        --level A2 --text-file line.txt --out line.wav

Prints a single JSON line to stdout: {"ok": bool, "seconds": float, "sr": int}.
Exit 0 on success, non-zero on failure. Never leaves a partial WAV on failure.
"""
import argparse
import json
import pathlib
import sys

BOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

# render_story_v2 is import-safe without either engine (engines are imported lazily
# inside their classes), so this import works in any venv.
import importlib.util  # noqa: E402


def _load_rv2():
    spec = importlib.util.spec_from_file_location(
        "render_story_v2", BOT_DIR / "scripts" / "render_story_v2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_engine(engine_kind: str, rv2):
    """Instantiate ONE engine (loaded once, reused for every line in the batch —
    this is the whole point of the batch worker: a fresh subprocess per line would
    reload a multi-GB model each time, which is unusably slow on CPU)."""
    from src import sawt_cast
    if engine_kind == "clone":
        ref = rv2._SFX_DIR / sawt_cast.CLONE_REF_MAI
        if not ref.exists():
            raise FileNotFoundError(f"clone reference missing: {ref}")
        return rv2.CloneEngine(ref), sawt_cast.ENGINE_CLONE
    return rv2.KokoroEngine(), sawt_cast.ENGINE_KOKORO


def _synth_one(rv2, engine, engine_id, engine_kind, character, level, text):
    from src import sawt_cast
    ch = sawt_cast.character_for(character)
    ch = {**ch, "engine": engine_id}
    if engine_kind == "clone":
        return rv2.synth_line(text, ch, level, kokoro=None, clone=engine)
    return rv2.synth_line(text, ch, level, kokoro=engine, clone=None)


def synth_to_wav(engine_kind: str, character: str, level: str, text: str,
                 out_path: str) -> dict:
    """Synthesise ONE line to `out_path` (WAV @ rv2.SR). Kept for the single-line
    CLI/tests; the batch path (synth_batch) is what the renderer uses in production."""
    import soundfile as sf
    rv2 = _load_rv2()
    engine, engine_id = _build_engine(engine_kind, rv2)
    line = _synth_one(rv2, engine, engine_id, engine_kind, character, level, text)
    if line is None or not len(line):
        raise RuntimeError("engine produced no audio for the line")
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    sf.write(str(tmp), line, rv2.SR, format="WAV")   # explicit fmt: .part ext
    tmp.replace(out)                                  # atomic
    return {"ok": True, "seconds": round(len(line) / rv2.SR, 3), "sr": int(rv2.SR)}


def synth_batch(engine_kind: str, manifest: list) -> dict:
    """Synthesise MANY lines with ONE engine instance (model loaded once).

    `manifest` is a list of {index, character, level, text, out}. Writes each line's
    WAV to its `out`. Returns {ok, results:[{index, ok, seconds|error}], sr}. A single
    failed line does not abort the batch — its result is marked not-ok so the caller
    can decide (the gate is the final backstop)."""
    import soundfile as sf
    rv2 = _load_rv2()
    engine, engine_id = _build_engine(engine_kind, rv2)   # ONE load for the batch
    results = []
    for item in manifest:
        idx = item.get("index")
        try:
            line = _synth_one(rv2, engine, engine_id, engine_kind,
                              item["character"], item.get("level", "A2"),
                              item["text"])
            if line is None or not len(line):
                results.append({"index": idx, "ok": False,
                                "error": "no audio"}); continue
            out = pathlib.Path(item["out"])
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(out.suffix + ".part")
            sf.write(str(tmp), line, rv2.SR, format="WAV")
            tmp.replace(out)
            results.append({"index": idx, "ok": True,
                            "seconds": round(len(line) / rv2.SR, 3)})
        except Exception as e:                                   # noqa: BLE001
            results.append({"index": idx, "ok": False,
                            "error": f"{type(e).__name__}: {e}"})
    return {"ok": all(r["ok"] for r in results), "results": results,
            "sr": int(rv2.SR)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", required=True, choices=["kokoro", "clone"])
    ap.add_argument("--manifest", default="",
                    help="JSON file: list of {index,character,level,text,out} to "
                         "synthesise with ONE engine load (batch mode)")
    ap.add_argument("--character", default="", help="speaker label (single mode)")
    ap.add_argument("--level", default="A2")
    ap.add_argument("--text", default="")
    ap.add_argument("--text-file", default="",
                    help="read the spoken text from this file (overrides --text)")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    # Batch mode: one engine load, many lines.
    if a.manifest:
        try:
            manifest = json.loads(pathlib.Path(a.manifest).read_text(encoding="utf-8"))
        except Exception as e:                                   # noqa: BLE001
            print(json.dumps({"ok": False, "error": f"bad manifest: {e}"}),
                  file=sys.stderr)
            return 2
        try:
            result = synth_batch(a.engine, manifest)
        except Exception as e:                                   # noqa: BLE001
            print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}),
                  file=sys.stderr)
            return 1
        print(json.dumps(result))
        return 0 if result["ok"] else 1

    # Single-line mode (CLI/tests).
    if not a.character or not a.out:
        print(json.dumps({"ok": False,
                          "error": "single mode needs --character and --out"}),
              file=sys.stderr)
        return 2
    text = a.text
    if a.text_file:
        text = pathlib.Path(a.text_file).read_text(encoding="utf-8")
    text = (text or "").strip()
    if not text:
        print(json.dumps({"ok": False, "error": "empty text"}), file=sys.stderr)
        return 2
    try:
        result = synth_to_wav(a.engine, a.character, a.level, text, a.out)
    except Exception as e:                                       # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}),
              file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
