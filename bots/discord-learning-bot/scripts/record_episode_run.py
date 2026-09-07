#!/usr/bin/env python3.12
"""Empire Chronicles — record one daily-pipeline run for observability (R9.5).

Reads the render's QA report (and the episode meta) and writes a durable per-run
row into the `podcast_runs` table via src.database, whether the episode PASSED
(emitted) or FAILED the gate. This turns the ephemeral qa.json into a queryable
history the owner can review with /story-runs.

Best-effort by design: it NEVER exits non-zero and NEVER raises, because recording
telemetry must not change the pipeline's outcome. (In CI there is no DB, so this is
a no-op there; on the server the same script is run against the live DB.)

Usage:
    python3.12 scripts/record_episode_run.py \
        --report content/podcast-audio/<slug>.qa.json \
        --meta   content/podcast-scripts/episode-meta.json
"""
import argparse
import json
import pathlib
import sys

BOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))


def _load(path: str) -> dict:
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", required=True, help="path to <slug>.qa.json")
    ap.add_argument("--meta", default="", help="path to episode-meta.json")
    args = ap.parse_args()

    result = _load(args.report)
    meta = _load(args.meta) if args.meta else {}
    if not result:
        print(f"record_episode_run: no report at {args.report}; nothing to record")
        return 0

    report = result.get("report", result)
    metrics = report.get("metrics", {})
    slug = (meta.get("slug")
            or pathlib.Path(args.report).name.replace(".qa.json", ""))
    failures = report.get("failures", []) or []
    # A failure may be unmeasured-critical rather than a named metric failure.
    failures = list(failures) + [f"{m}(unmeasured)"
                                 for m in report.get("unmeasured_critical", []) or []]

    try:
        from src import database
        database.record_podcast_run(
            slug,
            episode_number=meta.get("episode_number"),
            level=meta.get("level") or report.get("level") or "",
            passed=bool(result.get("passed")),
            attempts=int(result.get("attempts") or 0),
            failures=failures,
            metrics=metrics,
            elapsed_seconds=result.get("elapsed_seconds"),
        )
        status = "EMITTED" if result.get("passed") else "FAILED"
        print(f"record_episode_run: recorded {slug} — {status} "
              f"(attempts={result.get('attempts')})")
    except Exception as e:                                        # noqa: BLE001
        # No DB (CI) or any other problem: telemetry is best-effort.
        print(f"record_episode_run: skipped ({type(e).__name__}: {e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
