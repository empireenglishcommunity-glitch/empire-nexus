#!/usr/bin/env python3
"""Hisn Phase H0.1 — Test Matrix Generator.

Scans the ACTUAL codebase (not memory, not a hand-typed list) to produce
a complete, exhaustive test matrix. This is the ground-truth source for
the entire Hisn verification campaign — every row in the output MUST be
checked off during H1-H6 before H7's Go/No-Go sign-off.

Re-run this generator any time to re-verify nothing has silently
drifted (e.g. a 40th command added without being added to test_matrix.md).

Usage:
    python3 generate_test_matrix.py > test_matrix.md

Scans:
    bots/discord-learning-bot/src/bot.py            -> commands
    bots/discord-learning-bot/src/flag_registry.py  -> feature flags
    bots/discord-learning-bot/scripts/setup_server.py -> channels/categories
    bots/discord-learning-bot/src/api_server.py     -> API endpoints
    empire-dojo/site/                               -> practice platform pages
"""
import re
import sys
from pathlib import Path

# ── Locate repo roots relative to this script ──
# This script lives at empire-nexus/.kiro/specs/full-ecosystem-verification/
SPEC_DIR = Path(__file__).resolve().parent
EMPIRE_NEXUS = SPEC_DIR.parent.parent.parent  # .kiro/specs/X -> up 3 = empire-nexus root
SANDBOX_ROOT = EMPIRE_NEXUS.parent  # /projects/sandbox
EMPIRE_DOJO = SANDBOX_ROOT / "empire-dojo"

BOT_SRC = EMPIRE_NEXUS / "bots" / "discord-learning-bot" / "src"
BOT_SCRIPTS = EMPIRE_NEXUS / "bots" / "discord-learning-bot" / "scripts"


def scan_commands() -> list[dict]:
    """Extract every @bot.command(name="...") from bot.py, plus its
    immediately-following docstring (as a rough description) and
    whether it's admin-gated (@commands.has_permissions decorator
    immediately above it)."""
    bot_py = BOT_SRC / "bot.py"
    text = bot_py.read_text(encoding="utf-8")
    lines = text.split("\n")

    commands = []
    pattern = re.compile(r'@bot\.command\(name="([^"]+)"')

    for i, line in enumerate(lines):
        m = pattern.search(line)
        if not m:
            continue
        name = m.group(1)

        # Check both the line(s) immediately BEFORE and AFTER the
        # @bot.command(...) line for an admin-permission decorator.
        # Found via manual cross-check against bot.py: this codebase's
        # convention is decorator stacking with @bot.command(...) FIRST
        # and @commands.has_permissions(...) SECOND (i.e. below it), not
        # the other way around — an earlier version of this script only
        # scanned backward and silently reported admin_gated=False for
        # every single command, including real admin-only ones like
        # !flag and !setlevel. Checking both directions makes this
        # robust regardless of which order a given command happens to
        # use.
        admin_gated = False
        for back in range(1, 4):
            if i - back < 0:
                break
            prev = lines[i - back]
            if "has_permissions" in prev or "is_owner" in prev:
                admin_gated = True
            if not prev.strip().startswith("@") and prev.strip() != "":
                break
        for fwd in range(1, 4):
            if i + fwd >= len(lines):
                break
            nxt = lines[i + fwd]
            if "has_permissions" in nxt or "is_owner" in nxt:
                admin_gated = True
            if nxt.strip().startswith("async def") or nxt.strip().startswith("def"):
                break
            if not nxt.strip().startswith("@") and nxt.strip() != "":
                break

        # Grab the docstring on the next few lines, if present
        desc = ""
        for fwd in range(1, 6):
            if i + fwd >= len(lines):
                break
            fline = lines[i + fwd].strip()
            if fline.startswith('"""'):
                desc = fline.strip('"""').strip()
                break

        commands.append({
            "name": name,
            "admin_gated": admin_gated,
            "description": desc or "(no docstring found)",
        })

    return sorted(commands, key=lambda c: c["name"])


def scan_flags() -> list[dict]:
    """Import flag_registry.py's REGISTRY directly (safe — it's pure
    data, no side effects) rather than regex-parsing it, since the
    format is a plain Python list literal."""
    sys.path.insert(0, str(BOT_SRC.parent))
    try:
        # Import as a standalone module to avoid triggering the full
        # src package's __init__ (which may import discord.py etc. that
        # aren't installed in this environment).
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "flag_registry", BOT_SRC / "flag_registry.py"
        )
        flag_registry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(flag_registry)
        registry = flag_registry.REGISTRY
    finally:
        sys.path.pop(0)

    return [
        {"name": name, "description": desc, "initiative": initiative, "default": default}
        for name, desc, initiative, default in registry
    ]


def scan_channels() -> list[dict]:
    """Regex-parse setup_server.py's CATEGORIES_CONFIG for category
    names and channel names/types. Avoided importing this file directly
    since it likely imports discord.py at module level, which may not
    be installed in the environment running this generator."""
    setup_py = BOT_SCRIPTS / "setup_server.py"
    text = setup_py.read_text(encoding="utf-8")

    # Find the CATEGORIES_CONFIG = [ ... ] block boundaries by bracket
    # depth counting, since it's a large nested structure not easily
    # regex-matched as a whole.
    start_marker = "CATEGORIES_CONFIG = ["
    start_idx = text.index(start_marker)
    depth = 0
    idx = start_idx + len(start_marker) - 1  # position of the opening [
    end_idx = None
    for i in range(idx, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                end_idx = i
                break
    block = text[start_idx:end_idx + 1]

    # Within the block, find each category's "name": "..." and its
    # channels list's "name": "...", "type": "..."
    entries = []
    current_category = None

    cat_pattern = re.compile(r'"name":\s*"([^"]+)"')
    type_pattern = re.compile(r'"type":\s*"(text|voice)"')

    # Walk line by line, tracking whether we're inside a top-level
    # category dict (has "overwrites"/"channels" keys) vs a channel dict.
    lines = block.split("\n")
    depth_stack = []
    in_channels_list = False

    for line in lines:
        stripped = line.strip()
        if '"channels": [' in stripped:
            in_channels_list = True
            continue
        if in_channels_list and stripped.startswith("]"):
            in_channels_list = False
            continue

        name_match = cat_pattern.search(stripped)
        if name_match:
            name = name_match.group(1)
            if in_channels_list:
                # This is a channel name; find its type on the same line
                type_match = type_pattern.search(stripped)
                ch_type = type_match.group(1) if type_match else "text"
                entries.append({
                    "category": current_category,
                    "channel": name,
                    "type": ch_type,
                })
            else:
                # This is a category name
                current_category = name

    return entries


def scan_api_endpoints() -> list[dict]:
    """Extract every @routes.get/post/options(...) from api_server.py."""
    api_py = BOT_SRC / "api_server.py"
    text = api_py.read_text(encoding="utf-8")

    pattern = re.compile(r'@routes\.(get|post|options)\("([^"]+)"\)')
    endpoints = []
    for method, path in pattern.findall(text):
        endpoints.append({"method": method.upper(), "path": path})

    return endpoints


def scan_web_pages() -> dict:
    """Count practice platform pages by level/type, and list top-level
    special pages (dashboard, review, homepage)."""
    if not EMPIRE_DOJO.exists():
        return {"total": 0, "by_level": {}, "special_pages": [], "note": "empire-dojo not found at expected path"}

    site_dir = EMPIRE_DOJO / "site"
    all_html = list(site_dir.rglob("*.html"))

    by_level = {}
    special_pages = []
    for f in all_html:
        rel = f.relative_to(site_dir)
        parts = rel.parts
        if parts[0] in ("l0", "l1", "l2", "l3"):
            by_level[parts[0]] = by_level.get(parts[0], 0) + 1
        else:
            special_pages.append(str(rel))

    return {
        "total": len(all_html),
        "by_level": by_level,
        "special_pages": sorted(special_pages),
    }


def render_markdown(commands, flags, channels, endpoints, pages) -> str:
    out = []
    out.append("# Hisn Test Matrix (generated, do not hand-edit)\n")
    out.append(f"Generated from the actual codebase. Counts: "
                f"{len(commands)} commands, {len(flags)} flags, "
                f"{len(channels)} channels, {len(endpoints)} API endpoints, "
                f"{pages['total']} web pages.\n")

    # ── Commands ──
    out.append("## Discord Commands\n")
    out.append("| # | Command | Admin-gated? | Description | Tested (none/valid/invalid/oversized) | Notes |")
    out.append("|---|---|---|---|---|---|")
    for i, c in enumerate(commands, 1):
        gated = "🔒 Yes" if c["admin_gated"] else "No"
        out.append(f"| {i} | `!{c['name']}` | {gated} | {c['description'][:60]} | ☐ ☐ ☐ ☐ | |")
    out.append("")

    # ── Feature Flags ──
    out.append("## Feature Flags\n")
    out.append("| # | Flag | Initiative | Default | Toggled on | Toggled off | Notes |")
    out.append("|---|---|---|---|---|---|---|")
    for i, f in enumerate(flags, 1):
        out.append(f"| {i} | `{f['name']}` | {f['initiative']} | {'ON' if f['default'] else 'OFF'} | ☐ | ☐ | |")
    out.append("")

    # ── Channels ──
    # Category names contain a literal "|" character (e.g.
    # "📋 أهلاً | WELCOME") which corrupts Markdown table columns if
    # inserted as-is — found by reading the generator's own first-run
    # output rather than assuming the render was correct just because
    # the script didn't error. Escaped here with \| so the table
    # renders with the correct column count.
    out.append("## Discord Channels\n")
    out.append("| # | Category | Channel | Type | Permission Verified | Notes |")
    out.append("|---|---|---|---|---|---|")
    for i, ch in enumerate(channels, 1):
        safe_category = ch["category"].replace("|", "\\|")
        out.append(f"| {i} | {safe_category} | {ch['channel']} | {ch['type']} | ☐ | |")
    out.append("")

    # ── API Endpoints ──
    out.append("## API Endpoints\n")
    out.append("| # | Method | Path | Valid token | Invalid token | Malformed body | Rate limit | Notes |")
    out.append("|---|---|---|---|---|---|---|---|")
    for i, e in enumerate(endpoints, 1):
        out.append(f"| {i} | {e['method']} | `{e['path']}` | ☐ | ☐ | ☐ | ☐ | |")
    out.append("")

    # ── Web Pages ──
    out.append("## Practice Platform Pages\n")
    out.append(f"Total: **{pages['total']}** pages\n")
    out.append("| Level | Page Count | Automated Crawl | Manual Spot-Check (1 full day) |")
    out.append("|---|---|---|---|")
    for level in ["l0", "l1", "l2", "l3"]:
        count = pages["by_level"].get(level, 0)
        out.append(f"| {level.upper()} | {count} | ☐ | ☐ |")
    out.append("")
    out.append("### Special Pages (not level/week/day exercises)")
    for p in pages["special_pages"]:
        out.append(f"- ☐ `{p}`")
    out.append("")

    return "\n".join(out)


def main():
    commands = scan_commands()
    flags = scan_flags()
    channels = scan_channels()
    endpoints = scan_api_endpoints()
    pages = scan_web_pages()

    md = render_markdown(commands, flags, channels, endpoints, pages)
    print(md)

    # Also print a summary to stderr so it's visible even when stdout
    # is redirected to a file.
    print(f"\n--- SUMMARY (to stderr) ---", file=sys.stderr)
    print(f"Commands: {len(commands)}", file=sys.stderr)
    print(f"Flags: {len(flags)}", file=sys.stderr)
    print(f"Channels: {len(channels)}", file=sys.stderr)
    print(f"API endpoints: {len(endpoints)}", file=sys.stderr)
    print(f"Web pages: {pages['total']}", file=sys.stderr)


if __name__ == "__main__":
    main()
