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


def synth_to_wav(engine_kind: str, character: str, level: str, text: str,
                 out_path: str) -> dict:
    """Synthesise one line and write it to `out_path` (WAV @ rv2.SR). Returns a
    result dict. Raises on hard failure (caller maps to exit code)."""
    import soundfile as sf
    from src import sawt_cast

    rv2 = _load_rv2()
    ch = sawt_cast.character_for(character)

    if engine_kind == "clone":
        ref = rv2._SFX_DIR / sawt_cast.CLONE_REF_MAI
        if not ref.exists():
            raise FileNotFoundError(f"clone reference missing: {ref}")
        engine = rv2.CloneEngine(ref)
        # Force the clone branch in synth_line regardless of the label's registry
        # engine, so the worker does exactly what it was asked to.
        ch = {**ch, "engine": sawt_cast.ENGINE_CLONE}
        line = rv2.synth_line(text, ch, level, kokoro=None, clone=engine)
    else:
        engine = rv2.KokoroEngine()
        ch = {**ch, "engine": sawt_cast.ENGINE_KOKORO}
        line = rv2.synth_line(text, ch, level, kokoro=engine, clone=None)

    if line is None or not len(line):
        raise RuntimeError("engine produced no audio for the line")

    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    # Explicit WAV format: the .part extension gives soundfile nothing to infer from.
    sf.write(str(tmp), line, rv2.SR, format="WAV")
    tmp.replace(out)                       # atomic: no partial file on failure
    return {"ok": True, "seconds": round(len(line) / rv2.SR, 3), "sr": int(rv2.SR)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", required=True, choices=["kokoro", "clone"])
    ap.add_argument("--character", required=True, help="speaker label, e.g. 'Maya'")
    ap.add_argument("--level", default="A2")
    ap.add_argument("--text", default="")
    ap.add_argument("--text-file", default="",
                    help="read the spoken text from this file (overrides --text)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

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
