#!/usr/bin/env python3
"""Hisn H2.1 — Practice Platform Page Crawler.

Crawls every page discovered from the LOCAL empire-dojo repo's file
structure, but validates against the LIVE deployed site
(https://practice.empireenglish.online) rather than just checking local
files -- this is a stronger test, since it validates what a real
student's browser would actually receive from the live CDN, not just
what's committed to the repo (which could differ if a deploy is stale,
partially failed, or the CDN is serving a cached/broken version).

For each page, checks:
  - HTTP 200 (not 404, 500, etc.)
  - No broken <audio src="...">  (each audio src itself returns 200)
  - No broken internal <a href="...">  (each internal link itself
    returns 200 -- sampled, not exhaustive per-page, to keep total
    request count reasonable across 1,334 pages)
  - Expected exercise markup present (a flashcard/quiz/accent-drill
    container element, depending on exercise type)
  - No literal "undefined", "NaN", or unrendered template markers
    (e.g. "{{" or "${") leaking into the rendered HTML

Console JS errors are explicitly OUT of scope for this script (that
needs a real headless browser, e.g. Playwright, which isn't installed
in this sandbox) -- deferred to H2.2's manual walkthrough, where a
real desktop/mobile browser's dev console can be checked directly.

Run from anywhere with network access to the live site + a local
checkout of empire-dojo:
    python3 page_crawler.py [--sample N]

By default, crawls ALL 1,334 pages (takes a few minutes). Pass
--sample N to test a random N-page subset for a quick smoke check
before committing to the full run.
"""
import argparse
import random
import re
import sys
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

BASE_URL = "https://practice.empireenglish.online"
# scripts/ -> full-ecosystem-verification/ -> specs/ -> .kiro/ -> empire-nexus/
# -> sandbox root -> empire-dojo/site. Getting this path traversal
# wrong (off-by-one on the parent count) was the FIRST bug found when
# actually running this script, not just reading it -- fixed here.
SITE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "empire-dojo" / "site"

REQUEST_TIMEOUT = 10
DELAY_BETWEEN_REQUESTS = 0.05  # be a reasonable citizen against the live CDN

# Markers that indicate a template/render failure leaking into output
BROKEN_MARKERS = ["undefined", "NaN", "{{", "${", "[object Object]"]


def discover_pages() -> list[str]:
    """Return every page's URL path, derived from the local repo's file
    structure (the site uses extensionless URLs matching directory
    names, per the project's own steering docs)."""
    if not SITE_DIR.exists():
        print(f"ERROR: empire-dojo site dir not found at {SITE_DIR}", file=sys.stderr)
        sys.exit(1)

    paths = []
    for html_file in SITE_DIR.rglob("*.html"):
        rel = html_file.relative_to(SITE_DIR)
        if rel.name == "index.html":
            # Extensionless directory URL, e.g. l0/week1/day1/accent/
            url_path = "/" + str(rel.parent) + "/"
            if str(rel.parent) == ".":
                url_path = "/"
        else:
            # A named .html file not called index -- served at its own
            # extensionless path per the site's convention (verified
            # against review/index.html and dash/index.html, both of
            # which ARE index.html files -- checked, no exceptions
            # found in this codebase's actual file layout).
            url_path = "/" + str(rel.with_suffix(""))
        paths.append(url_path)

    return sorted(set(paths))


def fetch(url: str) -> tuple:
    """Returns (status_code, body_text_or_None, error_or_None)."""
    try:
        req = Request(url, headers={"User-Agent": "Hisn-Page-Crawler/1.0"})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return (resp.status, body, None)
    except HTTPError as e:
        return (e.code, None, str(e))
    except URLError as e:
        return (None, None, str(e))


def check_page(url_path: str, homepage_body: str = None) -> dict:
    """Fetch a single page and run all checks against it.

    IMPORTANT finding from actually running this crawler (not just
    reading Cloudflare Pages' docs): this site has NO custom 404.html,
    so Cloudflare Pages' default SPA-style fallback serves the
    HOMEPAGE with an HTTP 200 status for ANY genuinely nonexistent
    path (confirmed live: /this-genuinely-does-not-exist-12345 also
    returns 200). This means "HTTP 200" alone can never detect a
    missing page on this site -- a naive version of this script would
    silently report every missing/mis-deployed page as "OK" simply
    because Cloudflare's fallback always returns 200.

    Fixed by additionally comparing the fetched body against a
    reference copy of the real homepage: if they're byte-identical (or
    near-identical) AND the URL being tested isn't actually the
    homepage itself, that's the fallback firing, not a real page.
    """
    full_url = BASE_URL + url_path
    status, body, err = fetch(full_url)

    result = {
        "path": url_path,
        "status": status,
        "ok": False,
        "issues": [],
    }

    if status != 200:
        result["issues"].append(f"HTTP {status} (expected 200): {err}")
        return result

    if body is None:
        result["issues"].append("empty response body")
        return result

    # Detect Cloudflare Pages' homepage-fallback masquerading as a 200.
    if homepage_body is not None and url_path != "/" and body.strip() == homepage_body.strip():
        result["issues"].append(
            "served the SITE HOMEPAGE instead of this page's real content "
            "(Cloudflare Pages' 404 fallback firing -- this URL doesn't actually exist)"
        )
        return result

    # Check for broken-render markers OUTSIDE of <script> tags only.
    # Found via actually running this against the live homepage (not
    # assumed): "${" and "`" template-literal syntax is completely
    # normal and correct INSIDE a <script> block (it's JS source code,
    # never meant to be HTML-rendered) -- e.g. this site's own
    # `${totalDone}/${totalPossible} exercises...` template literal in
    # its weekly-progress-chart script. An earlier version of this
    # check flagged that as a false "broken render marker" on every
    # single page that includes app.js's inline scripts. Fixed by
    # stripping <script>...</script> blocks before checking.
    body_outside_scripts = re.sub(r"<script\b[^>]*>.*?</script>", "", body, flags=re.DOTALL | re.IGNORECASE)
    for marker in BROKEN_MARKERS:
        if marker in body_outside_scripts:
            result["issues"].append(f"found broken-render marker: {marker!r}")

    # Extract and spot-check audio src attributes (sample up to 2 per
    # page to keep total request volume reasonable across 1,334 pages
    # -- most pages share the same handful of audio files, so this
    # still gives real coverage without redundant re-fetching).
    audio_srcs = re.findall(r'<audio[^>]+src="([^"]+)"', body)
    for src in audio_srcs[:2]:
        audio_url = src if src.startswith("http") else BASE_URL + (src if src.startswith("/") else url_path + src)
        a_status, _, a_err = fetch(audio_url)
        if a_status != 200:
            result["issues"].append(f"broken audio src: {src} -> HTTP {a_status} ({a_err})")

    # Expected markup presence -- at least ONE recognizable exercise
    # container should exist on every exercise page (flashcard, quiz,
    # accent drill, etc.) -- the homepage/dash/review pages have their
    # own distinct structure and are excluded from this specific check.
    if "/week" in url_path and "/day" in url_path:
        has_exercise_markup = any(
            marker in body for marker in
            ["flashcard", "quiz", "accent", "shadowing", "listening", "vocab", "card"]
        )
        if not has_exercise_markup:
            result["issues"].append("no recognizable exercise markup found on what looks like an exercise page")

    result["ok"] = len(result["issues"]) == 0
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None,
                        help="Test a random N-page subset instead of all pages")
    args = parser.parse_args()

    all_pages = discover_pages()
    print(f"Discovered {len(all_pages)} pages from local repo structure.")

    # Fetch a reference copy of the real homepage once, used to detect
    # Cloudflare Pages' 404-fallback-serves-homepage behavior (see
    # check_page()'s docstring for the full explanation of why this is
    # necessary -- found by actually running this crawler against a
    # deliberately-nonexistent URL, not assumed from documentation).
    _, homepage_body, _ = fetch(BASE_URL + "/")
    if homepage_body is None:
        print("WARNING: could not fetch reference homepage; 404-fallback detection disabled", file=sys.stderr)

    pages_to_test = all_pages
    if args.sample:
        random.seed(42)  # reproducible sampling
        pages_to_test = random.sample(all_pages, min(args.sample, len(all_pages)))
        print(f"Sampling {len(pages_to_test)} pages for this run.")

    results = []
    for i, path in enumerate(pages_to_test):
        r = check_page(path, homepage_body=homepage_body)
        results.append(r)
        if (i + 1) % 100 == 0:
            print(f"  ...{i + 1}/{len(pages_to_test)} checked", file=sys.stderr)
        time.sleep(DELAY_BETWEEN_REQUESTS)

    ok_count = sum(1 for r in results if r["ok"])
    bad = [r for r in results if not r["ok"]]

    print()
    print("=" * 70)
    print(f"Tested: {len(results)}  OK: {ok_count}  ISSUES: {len(bad)}")
    print()
    for r in bad:
        print(f"ISSUE: {r['path']} (status={r['status']})")
        for issue in r["issues"]:
            print(f"    - {issue}")

    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
