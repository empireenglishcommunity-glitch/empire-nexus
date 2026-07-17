#!/usr/bin/env python3
"""Sahin — Arabic/English bidirectional (bidi) text checker.

WHY THIS EXISTS:
Discord's client (like every modern text renderer) follows the Unicode
Bidirectional Algorithm (UBA) to lay out mixed-direction text. A single
Arabic (RTL) line containing TWO OR MORE separate embedded English/code
tokens (e.g. two different `#channel-name` references connected by an
Arabic word like "أو") produces a genuinely disorienting reading
experience: the eye has to jump between RTL and LTR runs multiple times
within one line, in an order that does not match the logical (typed)
order of the text. This is a real, well-documented bidi rendering
property, not a rendering bug specific to Discord or a mistake in any
one line's wording.

Found live during Sahin Phase 1 (2026-07-17): the owner flagged
`l0-showcase`'s guide line "لا تكتب نصًا أو أسئلة هنا — مكانها
#ask-nour أو #support" as unreadable — it has TWO embedded English
tokens (#ask-nour, #support) joined by "أو", producing exactly this
problem. A follow-up scan found the SAME pattern in at least 8 places
across `channel_guides.py`, not just that one line.

WHAT THIS TOOL DOES:
Scans any Arabic-containing string (or every value in a dict, e.g.
CHANNEL_GUIDES) for lines containing 2 or more separate embedded LTR
"islands" (backtick-wrapped channel/command references, or any run of
Latin-script characters) joined by Arabic connector text. Flags each
one so it can be restructured — the fix is almost always: split into
separate lines, ONE embedded LTR token per line, so each line has at
most one RTL->LTR transition and nothing Arabic trails after the LTR
token within that same line.

USAGE:
    from bidi_check import find_bidi_issues
    issues = find_bidi_issues(some_text)              # single string
    issues = find_bidi_issues_in_dict(CHANNEL_GUIDES)  # {key: [issues]}

    # Or from the command line, against channel_guides.py directly:
    python3 scripts/bidi_check.py
"""
import re

# Matches a "run" of Latin-script characters (ASCII letters, digits,
# and common symbols used in channel names/commands: #, !, -, _, <, >)
# treated as a single LTR island. Backtick-wrapped tokens
# (`#channel-name`, `!command`) are the main case in this codebase's
# Arabic content, but this also catches bare English words/tokens not
# wrapped in backticks.
_LTR_ISLAND = re.compile(r"[A-Za-z0-9#!_<>\-]+")

# Arabic Unicode ranges (same ranges used elsewhere in this codebase,
# e.g. discord-learning-bot/src/features.py's Arabic-detection regex)
_ARABIC_CHAR = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")


def _count_ltr_islands(line: str) -> int:
    """Count distinct LTR islands in a line, ignoring islands that are
    too short to matter (e.g. a single digit like the "3" in "المستوى
    3", which is not a bidi-disorienting embedded token)."""
    islands = _LTR_ISLAND.findall(line)
    # Ignore bare numbers/single-char islands -- a level number like
    # "3" embedded in Arabic text is normal and not what this check is
    # for. Require at least 2 chars OR a leading # / ! (a real
    # channel/command reference) to count as a real "island".
    real_islands = [
        isl for isl in islands
        if len(isl) >= 2 or isl in ("#", "!")
    ]
    return len(real_islands)


def find_bidi_issues(text: str) -> list[str]:
    """Return a list of lines within `text` that contain 2+ embedded
    LTR islands within a single Arabic-containing line -- the specific
    pattern that produces disorienting bidi reading order. Only checks
    lines that actually contain Arabic text (a pure-English line is
    never an issue by definition)."""
    issues = []
    for line in text.split("\n"):
        if not _ARABIC_CHAR.search(line):
            continue
        if _count_ltr_islands(line) >= 2:
            issues.append(line.strip())
    return issues


def find_bidi_issues_in_dict(content_map: dict[str, str]) -> dict[str, list[str]]:
    """Same as find_bidi_issues(), applied to every value in a dict
    (e.g. CHANNEL_GUIDES). Returns only entries that have at least one
    issue."""
    results = {}
    for key, text in content_map.items():
        issues = find_bidi_issues(text)
        if issues:
            results[key] = issues
    return results


def main():
    """Run against this project's real Arabic content maps and print
    a report. Exits with a non-zero status if any issues are found,
    so this can be wired into CI later if desired (not yet done --
    Sahin's own tasks.md tracks whether/when to add that)."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from channel_guides import CHANNEL_GUIDES

    total_issues = 0
    results = find_bidi_issues_in_dict(CHANNEL_GUIDES)
    for key, issues in results.items():
        print(f"⚠️  {key}:")
        for issue in issues:
            print(f"    {issue}")
        total_issues += len(issues)

    print()
    if total_issues:
        print(f"❌ {total_issues} bidi issue(s) found across {len(results)} entries.")
        sys.exit(1)
    else:
        print("✅ No bidi issues found (0 lines with 2+ embedded LTR islands).")
        sys.exit(0)


if __name__ == "__main__":
    main()
