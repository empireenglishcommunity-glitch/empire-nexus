#!/usr/bin/env python3
"""Hisn H2.6-H2.8 — API Endpoint Adversarial Testing.

Tests all 10 real API endpoints (per H0.2's verified count) against the
LIVE production API server, from OUTSIDE the container (real HTTP over
the network, exactly what a real browser on practice.empireenglish.online
would send) -- not a local aiohttp TestClient. This is deliberately a
stronger test than the unit tests already written during Wuslah
development, matching this campaign's "test the live system" philosophy
(the same one that caught D008).

Endpoints under test (from api_server.py's own module docstring):
  GET  /api/progress
  GET  /api/progress-v2
  GET  /api/dashboard
  GET  /api/leaderboard
  GET  /api/nour-tips
  GET  /api/notifications
  POST /api/srs-review
  POST /api/complete-exercise
  POST /api/notifications
  OPTIONS /api/{tail} (CORS preflight catch-all)

Input matrix per R5 / H2.6:
  - valid token (a real GHOST_TEST_ member's token, created by this script)
  - invalid token (well-formed but nonexistent)
  - missing token
  - malformed JSON (POST endpoints only)
  - SQL-injection-style string in token/body fields
  - XSS-style string in body fields
  - oversized payload
  - rapid-fire (61 requests in <60s) to trigger the 429 rate limit

H2.7: CORS headers checked against a real Origin header matching
practice.empireenglish.online.

H2.8: every error response body is scanned for stack-trace/file-path
leakage and for any sign of cross-member data (a second GHOST_TEST_
member's data must never appear in the first member's response).

Run from OUTSIDE the container (this machine), against the real public
URL. Requires the GHOST_TEST_ setup step (creates 2 synthetic members +
tokens directly in the DB) to be run INSIDE the container first -- see
`setup_ghost_members.py` companion script, or the inline SQL this
script prints if it can't reach the DB directly.
"""
import json
import string
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "https://bot.empireenglish.online"
ORIGIN = "https://practice.empireenglish.online"

results = []  # (endpoint, case, status, detail)


def req(method, path, token=None, body=None, headers=None, timeout=15):
    url = f"{BASE_URL}{path}"
    if token is not None and method == "GET":
        sep = "&" if "?" in path else "?"
        url = f"{url}{sep}token={urllib.request.quote(str(token))}"

    data = None
    # NOTE (Hisn H2.6): Cloudflare's bot-fight-mode WAF in front of
    # bot.empireenglish.online blocks the default Python-urllib User-Agent
    # with HTTP 403 "error code: 1010" before the request ever reaches the
    # application. A realistic browser UA is required for this script to
    # test the actual API behavior instead of Cloudflare's edge block.
    hdrs = {
        "Origin": ORIGIN,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
    }
    if headers:
        hdrs.update(headers)

    if method == "POST":
        if body is not None:
            if isinstance(body, str):
                data = body.encode("utf-8")  # for malformed-JSON tests
            else:
                data = json.dumps(body).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")

    r = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            code = resp.status
            resp_body = resp.read().decode("utf-8", errors="replace")
            resp_headers = dict(resp.headers)
    except urllib.error.HTTPError as e:
        code = e.code
        resp_body = e.read().decode("utf-8", errors="replace")
        resp_headers = dict(e.headers)
    except Exception as e:
        return None, str(e), {}
    return code, resp_body, resp_headers


def check_leak(body_text):
    """H2.8: scan a response body for stack traces / file paths."""
    leak_markers = [
        "Traceback (most recent call last)", "/app/", "/src/",
        "  File \"", "sqlite3.OperationalError", "sqlite3.IntegrityError",
        ".py\", line",
    ]
    return [m for m in leak_markers if m in body_text]


def record(endpoint, case, ok, detail):
    results.append((endpoint, case, "OK" if ok else "ISSUE", detail))


def main():
    valid_token = sys.argv[1] if len(sys.argv) > 1 else None
    other_member_token = sys.argv[2] if len(sys.argv) > 2 else None
    other_member_name_fragment = sys.argv[3] if len(sys.argv) > 3 else None

    if not valid_token:
        print("Usage: api_adversarial_test.py <valid_ghost_token> [other_member_token] [other_member_name_fragment]")
        print("Run setup_ghost_members.py inside the container first to generate these.")
        sys.exit(2)

    INVALID_TOKEN = "not_a_real_token_" + "z" * 20
    SQLI_TOKEN = "' OR '1'='1"
    XSS_STRING = "<script>alert(1)</script>"
    OVERSIZED = "A" * 200_000

    get_endpoints = [
        "/api/progress", "/api/progress-v2", "/api/dashboard",
        "/api/leaderboard", "/api/nour-tips", "/api/notifications",
    ]

    # ---- 1. Valid token ----
    for ep in get_endpoints:
        code, body, hdrs = req("GET", ep, token=valid_token)
        ok = code == 200 and body and body.strip().startswith("{")
        record(ep, "valid_token", ok, f"HTTP {code}, len={len(body or '')}")
        if code == 200:
            leaks = check_leak(body)
            if leaks:
                record(ep, "leak_check(valid)", False, f"markers found: {leaks}")
            if other_member_name_fragment and other_member_name_fragment in body:
                record(ep, "cross_member_leak", False, "other member's name/data appeared in this member's response!")

    # ---- 2. Invalid token (well-formed, nonexistent) ----
    for ep in get_endpoints:
        code, body, hdrs = req("GET", ep, token=INVALID_TOKEN)
        ok = code == 404 and "error" in (body or "")
        record(ep, "invalid_token", ok, f"HTTP {code}: {(body or '')[:120]}")
        leaks = check_leak(body or "")
        if leaks:
            record(ep, "leak_check(invalid_token)", False, f"markers found: {leaks}")

    # ---- 3. Missing token ----
    for ep in get_endpoints:
        code, body, hdrs = req("GET", ep, token=None)
        ok = code == 400 and "error" in (body or "")
        record(ep, "missing_token", ok, f"HTTP {code}: {(body or '')[:120]}")

    # ---- 4. SQL-injection-style token ----
    for ep in get_endpoints:
        code, body, hdrs = req("GET", ep, token=SQLI_TOKEN)
        # Correct behavior: treated as just an unmatched string -> 404 invalid token.
        # A 500 or a leak marker would indicate a real injection vulnerability.
        ok = code in (400, 404) and not check_leak(body or "")
        record(ep, "sqli_token", ok, f"HTTP {code}: {(body or '')[:120]}")

    # ---- 5. Oversized token (still a GET query param) ----
    code, body, hdrs = req("GET", "/api/dashboard", token=OVERSIZED)
    ok = code in (400, 404, 414) and not check_leak(body or "")
    record("/api/dashboard", "oversized_token", ok, f"HTTP {code}, resp_len={len(body or '')}")

    # ---- POST endpoints ----
    post_cases = [
        ("/api/srs-review", {"token": valid_token, "word": "hello", "score": 3}, "valid"),
        ("/api/srs-review", {"token": valid_token, "word": "hello", "score": 99}, "invalid_score_range"),
        ("/api/srs-review", {"token": valid_token, "word": "hello"}, "missing_score"),
        ("/api/srs-review", {"token": INVALID_TOKEN, "word": "hello", "score": 3}, "invalid_token"),
        ("/api/srs-review", {"token": SQLI_TOKEN, "word": "hello", "score": 3}, "sqli_token"),
        ("/api/srs-review", {"token": valid_token, "word": XSS_STRING, "score": 3}, "xss_word"),
        ("/api/complete-exercise", {"token": valid_token, "exercise_type": "accent"}, "valid"),
        ("/api/complete-exercise", {"token": valid_token, "exercise_type": "accent"}, "duplicate(idempotent)"),
        ("/api/complete-exercise", {"token": valid_token, "exercise_type": "; DROP TABLE members;"}, "sqli_exercise_type"),
        ("/api/complete-exercise", {"token": valid_token}, "missing_exercise_type"),
        ("/api/notifications", {"token": valid_token, "morning_dm": False}, "valid_toggle"),
        ("/api/notifications", {"token": valid_token, "morning_dm": True}, "valid_toggle_restore"),
        ("/api/notifications", {"token": INVALID_TOKEN, "morning_dm": True}, "invalid_token"),
    ]
    for ep, body, case in post_cases:
        code, resp_body, hdrs = req("POST", ep, body=body)
        looks_ok = code in (200, 400, 404, 503)
        record(ep, case, looks_ok, f"HTTP {code}: {(resp_body or '')[:150]}")
        leaks = check_leak(resp_body or "")
        if leaks:
            record(ep, f"leak_check({case})", False, f"markers found: {leaks}")

    # ---- Malformed JSON ----
    for ep in ["/api/srs-review", "/api/complete-exercise", "/api/notifications"]:
        code, body, hdrs = req("POST", ep, body="{not valid json!!!")
        ok = code == 400 and "error" in (body or "")
        record(ep, "malformed_json", ok, f"HTTP {code}: {(body or '')[:120]}")

    # ---- Oversized POST payload ----
    code, body, hdrs = req("POST", "/api/srs-review", body={"token": valid_token, "word": OVERSIZED, "score": 3})
    ok = code in (200, 400, 413) and not check_leak(body or "")
    record("/api/srs-review", "oversized_payload", ok, f"HTTP {code}, resp_len={len(body or '')}")

    # ---- CORS check (H2.7) ----
    code, body, hdrs = req("GET", "/api/dashboard", token=valid_token, headers={"Origin": ORIGIN})
    acao = hdrs.get("Access-Control-Allow-Origin")
    record("/api/dashboard", "cors_header_present", acao is not None, f"Access-Control-Allow-Origin: {acao}")

    code, body, hdrs = req("OPTIONS", "/api/dashboard", headers={
        "Origin": ORIGIN,
        "Access-Control-Request-Method": "GET",
    })
    ok = code in (200, 204) and hdrs.get("Access-Control-Allow-Origin") is not None
    record("/api/dashboard", "cors_preflight", ok, f"HTTP {code}, headers={dict(hdrs)}")

    # ---- Rate limit trigger (H2.6) ----
    print("Firing 65 rapid requests to trigger rate limit (this takes a few seconds)...")
    rl_token = "RATE_LIMIT_TEST_TOKEN_" + valid_token
    codes = []
    for i in range(65):
        code, body, hdrs = req("GET", "/api/progress", token=rl_token, timeout=5)
        codes.append(code)
    got_429 = 429 in codes
    first_429_at = codes.index(429) + 1 if got_429 else None
    record("/api/progress", "rate_limit_trigger", got_429 and first_429_at == 61,
           f"429 first seen at request #{first_429_at}, codes tail: {codes[-5:]}")

    # ---- Report ----
    print()
    print("=" * 78)
    issues = [r for r in results if r[2] == "ISSUE"]
    oks = [r for r in results if r[2] == "OK"]
    print(f"OK: {len(oks)}  ISSUES: {len(issues)}  (total checks: {len(results)})")
    print()
    for ep, case, status, detail in results:
        marker = "  " if status == "OK" else ">>"
        print(f"{marker} {status:6s} {ep:28s} [{case:28s}]  {detail}")

    if issues:
        sys.exit(1)


if __name__ == "__main__":
    main()
