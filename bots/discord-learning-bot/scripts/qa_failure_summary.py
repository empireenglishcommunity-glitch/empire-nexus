#!/usr/bin/env python3.12
"""Print a one-line human summary of a failed QA report, for the owner alert (R9.4).

Kept as a standalone script so the daily workflow doesn't embed multi-line Python
in YAML (which is fragile to quote). Prints e.g.:
    failures=wer,true_peak_dbtp attempts=3

Never raises; on any problem prints a safe fallback so the alert still sends.

Usage: python3.12 scripts/qa_failure_summary.py <path-to-qa.json>
"""
import json
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("no QA report")
        return 0
    try:
        r = json.load(open(sys.argv[1], encoding="utf-8"))
        rep = r.get("report", r)
        failures = rep.get("failures", []) or []
        unmeasured = rep.get("unmeasured_critical", []) or []
        names = list(failures) + [f"{m}(unmeasured)" for m in unmeasured]
        summary = ",".join(names) if names else "unknown"
        print(f"failures={summary} attempts={r.get('attempts')}")
    except Exception as e:                                       # noqa: BLE001
        print(f"no readable QA report ({type(e).__name__})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
