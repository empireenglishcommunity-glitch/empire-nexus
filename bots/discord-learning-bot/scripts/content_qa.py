#!/usr/bin/env python3.12
"""Report content-quality metrics for reading / broadcast / mediation.

The hard, objective invariants (bad answer index, duplicate options, empty
fields, invalid can-do codes, glossary without Arabic) are enforced as a failing
test in tests/test_content_quality.py. This script is the softer companion: it
reports the *smells* that are not errors but are worth watching, so an author can
see them without the build going red.

    python3.12 scripts/content_qa.py

Reports, per item set:
  * LENGTH BIAS  -- how often the correct option is the uniquely longest. A high
    rate means a test-taker can score by picking the longest answer. It is a
    guessability smell, not a wrong answer, and is best fixed by a human
    authoring pass that lengthens distractors, never by a mechanical edit of
    currently-correct options.
  * POSITION BIAS -- the global distribution of answer indices. Per-file bias
    with only ~4 items is small-sample noise; the global spread is what matters.

Answer-key CORRECTNESS is not checkable here or anywhere automatically -- it was
established by reading every item, and stays a human responsibility on new
content.
"""
import collections
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEVELS = ("a1", "a2", "b1", "b2", "c1", "c2")


def files(kind):
    out = []
    for level in LEVELS:
        out += sorted(glob.glob(os.path.join(HERE, "content", level, kind, "*.json")))
    return out


def mcqs(d, kind):
    if kind == "broadcast":
        return ([d["gist_question"]] if d.get("gist_question") else []) + (d.get("questions") or [])
    return d.get("questions") or []


def main():
    global_pos = collections.Counter()
    total = long_hits = 0
    per_level = collections.defaultdict(lambda: [0, 0])  # level -> [long_hits, n]
    every_item_long = []
    for kind in ("reading", "broadcast"):
        for path in files(kind):
            d = json.load(open(path, encoding="utf-8"))
            level = d["level"].lower()
            fl = fn = 0
            for q in mcqs(d, kind):
                opts, ans = q.get("options"), q.get("answer")
                if not (isinstance(opts, list) and isinstance(ans, int)
                        and 0 <= ans < len(opts) and len(opts) >= 3):
                    continue
                total += 1
                fn += 1
                global_pos[ans] += 1
                lengths = [len(str(o)) for o in opts]
                if lengths[ans] == max(lengths) and lengths.count(max(lengths)) == 1:
                    long_hits += 1
                    fl += 1
                    per_level[level][0] += 1
                per_level[level][1] += 1
            if fn >= 4 and fl == fn:
                every_item_long.append(f"{level}/{kind}/{os.path.basename(path)}")

    print(f"Scanned {total} MCQ items across reading + broadcast.\n")
    print("LENGTH BIAS (correct option is the uniquely longest):")
    print(f"  overall: {long_hits}/{total} = {long_hits/total:.1%}")
    for level in LEVELS:
        h, n = per_level[level]
        if n:
            print(f"    {level}: {h}/{n} = {h/n:.0%}")
    print(f"  files where EVERY item's correct option is longest (n>=4): "
          f"{len(every_item_long)}")
    print("\nPOSITION BIAS (global answer-index distribution):")
    print(f"  {dict(sorted(global_pos.items()))}  "
          f"(index 3 is rare only because most items have 3 options)")
    top = global_pos.most_common(1)[0]
    print(f"  most-common index {top[0]} used {top[1]}/{total} = {top[1]/total:.0%}")
    print("\nBoth are guessability smells, not correctness errors. See the module "
          "docstring and content/cefr/CONTENT-REVIEW-2026-08-27.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
