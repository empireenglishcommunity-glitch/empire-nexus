#!/usr/bin/env python3.12
"""Fold the gated renderer's licence credit line into episode-meta.json.

The gated renderer writes a QA report (…qa.json) that includes a `credit` line —
the exact CC-BY attribution(s) for the Podcast Lab assets the episode actually used
(or a generic CC0 line). The bot reads `episode-meta.json` when it posts, so we copy
the credit across here. Kept as a real script (not an inline workflow heredoc) so it
is testable and free of YAML-indentation hazards.

Usage:
    python3.12 scripts/merge_credit_into_meta.py <episode-meta.json> <qa-report.json>

Never fails the pipeline: a missing or unreadable report just leaves meta unchanged.
"""
import json
import sys


def merge(meta_path: str, qa_path: str) -> bool:
    """Copy qa['credit'] into meta['credit'] if present. Returns True if written."""
    try:
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        with open(qa_path, encoding="utf-8") as fh:
            qa = json.load(fh)
    except Exception as e:                                       # noqa: BLE001
        print(f"merge_credit: could not read inputs ({e}); leaving meta unchanged")
        return False
    credit = str(qa.get("credit", "") or "").strip()
    if not credit:
        print("merge_credit: no credit in QA report; leaving meta unchanged")
        return False
    meta["credit"] = credit
    try:
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)
    except Exception as e:                                       # noqa: BLE001
        print(f"merge_credit: could not write meta ({e})")
        return False
    print(f"merge_credit: set credit -> {credit}")
    return True


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: merge_credit_into_meta.py <meta.json> <qa.json>",
              file=sys.stderr)
        return 2
    merge(sys.argv[1], sys.argv[2])
    return 0            # never fail the pipeline over a cosmetic credit line


if __name__ == "__main__":
    sys.exit(main())
