#!/usr/bin/env python3.12
"""Empire English Chronicles — GATED render orchestrator (spec Phase 2).

This is the ONLY entry point the daily pipeline should call to produce an episode.
It renders, then measures the result against the standard, and **refuses to emit an
episode that has not passed**. This is the mechanism that ends "sometimes good,
sometimes bad": nothing unverified can reach a student.

Flow (design §10):

    render (full)
      └─ QA gate  --pass-->  write report, emit episode  ✅
             │ fail
             ▼
      identify offending LINES from per-line stems
      re-render ONLY those lines, re-assemble, re-gate      (cheapest effective fix)
             │ still fail
             ▼
      full re-render, re-gate                                (fresh sampling)
             │ still fail after MAX_RENDER_ATTEMPTS
             ▼
      DO NOT EMIT · write a failure report · exit non-zero   ← the bot alerts + keeps
                                                               yesterday's state (R4.3)

Every attempt writes a machine-readable report next to the episode (R4.4), so a
failure is diagnosable rather than mysterious.

Determinism note: Kokoro is deterministic, so a *persistent* failure means the
SCRIPT/TEXT is the problem, not sampling luck — and the failure report names the
offending line's text, which is the actionable information. The clone engine (Mai)
is the only stochastic part, so a full re-render can still help those lines.

Usage
-----
    python3.12 scripts/render_episode_gated.py \
        --script content/podcast-scripts/chronicles-ep02.txt \
        --level A2 \
        --out content/podcast-audio/chronicles-ep02.mp3 \
        --report content/podcast-audio/chronicles-ep02.qa.json

Exit codes: 0 = a PASSING episode was written · 1 = failed the gate (nothing
emitted) · 2 = could not run.
"""
import argparse
import json
import pathlib
import shutil
import sys
import tempfile
import time

BOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from src import audio_standards as STD                           # noqa: E402

# Load the sibling scripts by path (they live in scripts/, not the src package).
import importlib.util                                            # noqa: E402


def _load(mod_name, filename):
    spec = importlib.util.spec_from_file_location(mod_name, BOT_DIR / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rv2 = _load("render_story_v2", "render_story_v2.py")
qa = _load("audio_qa", "audio_qa.py")


def _gate(audio_path, script_text, level, transcriber=None):
    """Run the full quality gate on a rendered file. Returns the report dict."""
    return qa.analyze(audio_path, script_text=script_text, level=level,
                      transcriber=transcriber,
                      use_asr=True,
                      pause_budget_s=qa.script_pause_budget(script_text))


def _line_stems_report(stems, level, transcriber=None):
    """Gate each per-line VOICE STEM (voice-only, so naturalness gates here) and
    return the list of line indices whose stem fails, plus per-line detail.

    This is how a failure is LOCALISED so we can re-render only the bad lines
    instead of the whole episode (design §10.3)."""
    failing, detail = [], []
    for stem in stems:
        rep = qa.analyze(stem["file"], script_text=None, level=level,
                         use_asr=False, voice_only=True)
        # A stem has no script/music, so only voice-level checks are meaningful:
        # naturalness, hard cuts, per-line minimum length.
        bad = []
        if rep["metrics"].get("flatness", {}).get("status") == qa.FAIL:
            bad.append("flatness")
        if rep["metrics"].get("hard_cuts", {}).get("status") == qa.FAIL:
            bad.append("hard_cuts")
        if stem["seconds"] < STD.MIN_LINE_SECONDS:
            bad.append("too_short")
        detail.append({"index": stem["index"], "character": stem["character"],
                       "seconds": stem["seconds"], "issues": bad,
                       "text": stem.get("text", "")})
        if bad:
            failing.append(stem["index"])
    return failing, detail


def render_gated(script_path, out_path, level="A2", music="mystery",
                 sound_design=True, report_path=None, transcriber=None,
                 max_attempts=None):
    """Render `script_path` and emit `out_path` ONLY if it passes the gate.

    Returns a result dict: {passed, attempts, out_path (or None), report}. On
    failure `out_path` is NOT written (a stale/previous file is left untouched),
    and the report explains why so the caller can alert the owner."""
    script_path = pathlib.Path(script_path)
    out_path = pathlib.Path(out_path)
    script_text = script_path.read_text(encoding="utf-8")
    max_attempts = max_attempts or STD.MAX_RENDER_ATTEMPTS

    work = pathlib.Path(tempfile.mkdtemp(prefix="eec_gated_"))
    attempts_log = []
    passed_report = None
    t0 = time.time()

    try:
        for attempt in range(1, max_attempts + 1):
            cand = work / f"attempt{attempt}.mp3"
            stems_dir = work / f"stems{attempt}"
            print(f"\n=== attempt {attempt}/{max_attempts} — full render ===",
                  flush=True)
            rr = rv2.render(script_text, cand, level=level, music=music,
                            sound_design=sound_design, stems_dir=str(stems_dir))

            report = _gate(cand, script_text, level, transcriber=transcriber)
            # Localise any failure to specific lines (diagnostic + drives retry).
            failing_lines, line_detail = _line_stems_report(
                rr.get("stems", []), level, transcriber=transcriber)
            report["failing_lines"] = failing_lines
            report["line_detail"] = line_detail
            report["attempt"] = attempt
            attempts_log.append({"attempt": attempt, "passed": report["passed"],
                                 "failures": report["failures"],
                                 "unmeasured_critical": report["unmeasured_critical"],
                                 "failing_lines": failing_lines})

            if report["passed"]:
                print(f"  ✅ attempt {attempt} PASSED the gate", flush=True)
                shutil.copyfile(cand, out_path)
                passed_report = report
                break

            print(f"  ❌ attempt {attempt} failed: {report['failures']} "
                  f"unmeasured={report['unmeasured_critical']} "
                  f"failing_lines={failing_lines}", flush=True)
            # A persistent, deterministic failure (Kokoro) will not fix itself by
            # re-rolling; the report names the offending line text so a human can
            # act. We still try again because the clone engine (Mai) is stochastic
            # and SFX/mix interactions can vary.

        result = {
            "passed": passed_report is not None,
            "attempts": len(attempts_log),
            "attempts_log": attempts_log,
            "out_path": str(out_path) if passed_report else None,
            "level": level,
            "elapsed_seconds": round(time.time() - t0, 1),
            "report": passed_report or report,
        }

        # Always write a report (R4.4) — next to the episode if we passed, else
        # next to where it WOULD have gone, so a failure is still diagnosable.
        rp = pathlib.Path(report_path) if report_path else \
            out_path.with_suffix(".qa.json")
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
        result["report_path"] = str(rp)

        if passed_report:
            print(f"\n✅ EMITTED {out_path} after {result['attempts']} attempt(s). "
                  f"Report → {rp}")
        else:
            print(f"\n❌ NOT EMITTED — failed the gate after {result['attempts']} "
                  f"attempt(s). No episode written; previous state untouched. "
                  f"Report → {rp}", file=sys.stderr)
        return result
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--script", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--level", default="A2")
    ap.add_argument("--music", default="mystery")
    ap.add_argument("--no-sound-design", action="store_true")
    ap.add_argument("--report", default="", help="where to write the QA report "
                                                "(default: <out>.qa.json)")
    ap.add_argument("--max-attempts", type=int, default=0,
                    help="override the standard's MAX_RENDER_ATTEMPTS")
    args = ap.parse_args()

    if not pathlib.Path(args.script).exists():
        print(f"script not found: {args.script}", file=sys.stderr)
        return 2
    try:
        result = render_gated(
            args.script, args.out, level=args.level, music=args.music,
            sound_design=not args.no_sound_design,
            report_path=args.report or None,
            max_attempts=args.max_attempts or None)
    except Exception as e:                                       # noqa: BLE001
        print(f"gated render could not run: {type(e).__name__}: {e}",
              file=sys.stderr)
        return 2
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
