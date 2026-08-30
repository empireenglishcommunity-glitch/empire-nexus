"""Empire English Bot — HTTP API (Sahel S6 + Wuslah W0-W5).

Runs alongside the Discord bot on port 8099 (internal only).
Provides progress data for the practice platform via link tokens.

Endpoints:
  GET  /api/progress?token=<token>         — returns JSON progress data (legacy)
  GET  /api/progress-v2?token=<token>      — enhanced progress + adaptive fields (W3)
  GET  /api/dashboard?token=<token>        — full aggregated dashboard (W0)
  GET  /api/leaderboard?token=<token>      — top 10 + requester rank (W0)
  GET  /api/nour-tips?token=<token>        — AI study tips or generic fallback (W4)
  GET  /api/notifications?token=<token>    — notification preferences (W5)
  POST /api/srs-review                     — record SRS review result
  POST /api/complete-exercise              — web-to-Discord task confirmation (W2)
  POST /api/notifications                  — update notification preferences (W5)
"""
import asyncio
import json
import logging
import time
from collections import defaultdict
from pathlib import Path

from aiohttp import web

from . import database, maintenance, config

logger = logging.getLogger("empire-bot.api")

routes = web.RouteTableDef()

# ============================================================
#  Hisn D036 fix: real milestone catalog for the dashboard
# ============================================================

_MILESTONES_FILE = Path(__file__).resolve().parent.parent / "content" / "milestones" / "milestones.json"
_milestones_catalog_cache: list[dict] | None = None


def _get_milestones_catalog() -> list[dict]:
    """Flat list of every real milestone (id/name/name_ar/level) from
    the single source of truth, `content/milestones/milestones.json` —
    the SAME file `!markmilestone` and `narrative_engine.py` read from.

    Hisn D036 fix: the dashboard's milestone grid previously used a
    hardcoded, entirely fictional set of 12 IDs (`first_recording`,
    `streak_7`, `level_l1`, etc.) with ZERO overlap with the real 15
    milestone IDs used everywhere else in the system — meaning the
    grid could never show an "achieved" badge for any milestone a
    student actually completed, always showing every real milestone as
    locked, for every student, forever. This function is the fix:
    serve the real catalog so the frontend can render real IDs/names
    instead of an invented list.

    Cached in-memory after first load — this file changes rarely (a
    curriculum content decision, not a per-request concern), same
    caching pattern as `curriculum.py`'s own content loading.
    """
    global _milestones_catalog_cache
    if _milestones_catalog_cache is not None:
        return _milestones_catalog_cache
    catalog: list[dict] = []
    try:
        if _MILESTONES_FILE.exists():
            all_milestones = json.loads(_MILESTONES_FILE.read_text(encoding="utf-8"))
            for level, items in all_milestones.items():
                for m in items:
                    catalog.append({
                        "id": m.get("id"),
                        "name": m.get("name"),
                        "name_ar": m.get("name_ar"),
                        "level": level,
                    })
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load milestones catalog: {e}")
        catalog = []
    _milestones_catalog_cache = catalog
    return catalog

# ============================================================
#  RATE LIMITING (Wuslah W0.3 — 60 req/min per token)
# ============================================================

_rate_limits: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 20  # requests per window (Hissar P2: tightened from 60)


def _check_rate_limit(token: str) -> bool:
    """Returns True if the request is allowed, False if rate-limited."""
    now = time.time()
    timestamps = _rate_limits[token]

    # Prune entries older than the window
    cutoff = now - _RATE_LIMIT_WINDOW
    while timestamps and timestamps[0] < cutoff:
        timestamps.pop(0)

    if len(timestamps) >= _RATE_LIMIT_MAX:
        return False

    timestamps.append(now)
    return True


def _cors_headers(request=None) -> dict:
    """Hissar P2: CORS restricted to allowed origins only.
    Previously was Access-Control-Allow-Origin: * (any website could
    use the API). Now only allows the real practice platform domains.
    """
    allowed_origins = {
        "https://practice.empireenglish.online",
        "https://empire-practice-8l0.pages.dev",
    }
    origin = ""
    if request and hasattr(request, "headers"):
        origin = request.headers.get("Origin", "")
    # Also allow Cloudflare Pages preview URLs (*.empire-practice-8l0.pages.dev)
    if origin in allowed_origins or origin.endswith(".empire-practice-8l0.pages.dev"):
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-Darb-Session",
            # Darb: the practice page sends the empire_session cookie
            # cross-subdomain (practice. -> bot.), which requires this.
            "Access-Control-Allow-Credentials": "true",
        }
    # Unknown origin: return CORS headers with the primary domain
    # (browsers will block if it doesn't match their Origin, which is
    # the desired behavior — blocks unauthorized frontends)
    return {
        "Access-Control-Allow-Origin": "https://practice.empireenglish.online",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _level_progress(total_points: int, level: str) -> tuple[int, int, float]:
    """Cosmetic XP bar for the dashboard: lifetime points relative to the CEFR
    level thresholds. Returns (xp_in_level, xp_needed, level_pct).

    Any level key works — a legacy record (L0-L3) is normalized to its CEFR level
    via config.cefr_key(), and at the top of the ladder (C2, no next level) the
    bar reads 100%.

    🔴 CLAMPED AT ZERO, deliberately (Ijtihad Phase 0.1). Level promotion is
    exam-gated and awards NO points, while these thresholds assume points and
    level advance together. So a student who advances FASTER than they accumulate
    points -- i.e. the strongest, hardest-working ones -- had
    total_points < current_threshold and were shown a NEGATIVE progress bar
    (e.g. a promoted A2 student on 800 points rendered (800-2000)/3000 = -40%).
    The clamp makes the display honest and is correct regardless of the root
    cause; the root cause (achievement awarding nothing) is fixed in Ijtihad
    Phase 3, after which this bar is superseded outright. See
    .kiro/specs/ijtihad-effort-economy/.
    """
    cefr = config.cefr_key(level or "A1")
    next_level = config.next_cefr_level(cefr)
    if not next_level:
        return int(total_points), 0, 100.0
    current_threshold = config.level_xp_threshold(cefr)
    next_threshold = config.level_xp_threshold(next_level)
    xp_in_level = max(0, int(total_points) - current_threshold)
    xp_needed = next_threshold - current_threshold
    level_pct = min(100.0, round(xp_in_level / max(xp_needed, 1) * 100, 1))
    return xp_in_level, xp_needed, level_pct


def _touch_token(token: str) -> None:
    """Update last_used timestamp on the token for expiry tracking (W0.4)."""
    try:
        conn = database._connect()
        conn.execute(
            "UPDATE link_tokens SET last_used=datetime('now') WHERE token=?",
            (token,),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Non-critical — don't break the request for housekeeping


async def _log_ip_and_check(token: str, request: web.Request) -> None:
    """Hissar P5: Log the request IP and check for token sharing.

    If the token has been used from 5+ unique IPs, send a Telegram alert
    to the owner via Markaz ops hub. Non-blocking, non-fatal.
    """
    if not database.is_feature_enabled("hissar_ip_detection"):
        return

    # Get client IP (behind reverse proxy, check X-Forwarded-For first)
    ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not ip:
        ip = request.headers.get("X-Real-IP", "")
    if not ip:
        peername = request.transport.get_extra_info("peername")
        ip = peername[0] if peername else "unknown"

    if not ip or ip == "unknown":
        return

    unique_count = database.log_token_ip(token, ip)

    # Auto-flag at 5+ unique IPs
    if unique_count >= 5:
        # Check if we already alerted for this token recently (avoid spam)
        alert_key = f"ip_alert_{token}"
        if database.get_setting(alert_key):
            return  # Already alerted

        # Mark as alerted
        database.set_setting(alert_key, "1")

        # Get member info for the alert
        member = database.get_member_by_token(token)
        member_name = (member.get("discord_name", "Unknown") if member else "Unknown").split("#")[0]
        discord_id = member.get("discord_id", "?") if member else "?"

        # Send Telegram alert
        try:
            from . import ops_hub
            await ops_hub.send_ops_alert(
                title="Token Sharing Detected",
                body=(
                    f"Student: {member_name} (ID: {discord_id})\n"
                    f"Unique IPs: {unique_count}\n"
                    f"Token may be shared with unauthorized users.\n\n"
                    f"Action: Use !revoke @{member_name} to invalidate their token."
                ),
                severity="warning",
            )
        except Exception:
            pass  # Alert is best-effort


# ============================================================
#  EXISTING ENDPOINTS (Sahel S6)
# ============================================================
#  Maintenance-mode: public system status (no token — the practice page
#  polls this on load to show a maintenance banner/overlay).
# ============================================================

@routes.get("/api/status")
async def get_status(request: web.Request) -> web.Response:
    """Public system status for the practice page. No auth: it carries no
    student data, and the page must be able to read it even mid-maintenance.
    Fail-open by design (if this is unreachable the page assumes 'live')."""
    try:
        status = maintenance.get_status()
    except Exception as e:
        logger.warning(f"/api/status failed, reporting live: {e}")
        status = {"state": "live"}
    return web.json_response(status, headers=_cors_headers(request))


@routes.options("/api/status")
async def options_status(request: web.Request) -> web.Response:
    return web.Response(status=204, headers=_cors_headers(request))


@routes.get("/api/changelog")
async def get_changelog(request: web.Request) -> web.Response:
    """Public 'What's New' feed — recent release notes. Used by the practice
    page (one-time toast) and the guide's 'Latest updates' section."""
    try:
        from . import changelog
        entries = changelog.get_entries(limit=10)
    except Exception as e:
        logger.warning(f"/api/changelog failed: {e}")
        entries = []
    return web.json_response({"entries": entries}, headers=_cors_headers(request))


@routes.options("/api/changelog")
async def options_changelog(request: web.Request) -> web.Response:
    return web.Response(status=204, headers=_cors_headers(request))


# ============================================================

@routes.get("/api/progress")
async def get_progress(request: web.Request) -> web.Response:
    """Return progress JSON for a given link token."""
    token = request.query.get("token", "")
    if not token:
        return web.json_response({"error": "token required"}, status=400)

    if not _check_rate_limit(token):
        return web.json_response({"error": "rate limit exceeded"}, status=429)

    progress = database.get_progress_for_token(token)
    if not progress:
        # Fall back to the Darb session token (the current system): the page
        # sends its signed session token here, which the legacy link-token
        # lookup doesn't recognise. Accept it when the signature is valid AND
        # its device session is still active (same bar as every Darb endpoint),
        # so the header can show the student's real Discord streak instead of a
        # device-local guess. This was returning 404 for every Darb student.
        from . import darb
        payload = darb.verify_session(token)
        if payload and database.is_device_session_active(payload.get("sid", "")):
            progress = database.get_progress_for_discord_id(payload.get("did", ""))

    if not progress:
        return web.json_response({"error": "invalid token"}, status=404)

    _touch_token(token)
    return web.json_response(progress, headers=_cors_headers())


@routes.post("/api/srs-review")
async def post_srs_review(request: web.Request) -> web.Response:
    """Record an SRS review result from the practice platform."""
    try:
        data = await request.json()
    except (json.JSONDecodeError, Exception):
        return web.json_response({"error": "invalid JSON"}, status=400)

    token = data.get("token", "")
    word = data.get("word", "")
    score = data.get("score")

    if not token or not word or score is None:
        return web.json_response({"error": "token, word, and score required"}, status=400)

    if not _check_rate_limit(token):
        return web.json_response({"error": "rate limit exceeded"}, status=429)

    member = database.get_member_by_token(token)
    if not member:
        return web.json_response({"error": "invalid token"}, status=404)

    try:
        score = int(score)
        if not (0 <= score <= 5):
            raise ValueError
    except (ValueError, TypeError):
        return web.json_response({"error": "score must be 0-5"}, status=400)

    database.record_srs_review(member["discord_id"], word, score)
    _touch_token(token)
    return web.json_response({"ok": True}, headers=_cors_headers())


# ============================================================
#  WUSLAH W0.1: /api/dashboard — full aggregated student data
# ============================================================

@routes.get("/api/dashboard")
async def get_dashboard(request: web.Request) -> web.Response:
    """Return full dashboard payload for the student dashboard page.

    One single call gives the web frontend everything it needs to render
    the complete dashboard — no multiple round-trips on mobile.
    """
    token = request.query.get("token", "")
    if not token:
        return web.json_response({"error": "token required"}, status=400)

    if not _check_rate_limit(token):
        return web.json_response({"error": "rate limit exceeded"}, status=429)

    if not database.is_feature_enabled("wuslah_dashboard_api"):
        return web.json_response({"error": "dashboard API not enabled"}, status=503)

    member = database.get_member_by_token(token)
    if not member:
        return web.json_response({"error": "invalid token"}, status=404)

    discord_id = member["discord_id"]
    _touch_token(token)

    import datetime

    # Asia/Dubai "today", same source of truth as database reads and the
    # Discord commands (audit fix: was naive date.today() = server/UTC, which
    # disagreed with Dubai-logged submissions during the 00:00-04:00 window).
    today = database._today_local().isoformat()

    # --- Pronunciation (14 days) ---
    pron_scores_raw = database.get_recent_scores(discord_id, days=14)
    pron_scores = [{"date": s["date"], "score": round(s["score"], 1)} for s in pron_scores_raw]
    pron_avg = round(sum(s["score"] for s in pron_scores_raw) / len(pron_scores_raw), 1) if pron_scores_raw else None
    if len(pron_scores_raw) >= 4:
        recent = pron_scores_raw[:len(pron_scores_raw) // 2]
        older = pron_scores_raw[len(pron_scores_raw) // 2:]
        diff = (sum(s["score"] for s in recent) / len(recent)) - (sum(s["score"] for s in older) / len(older))
        pron_trend = "improving" if diff > 5 else "declining" if diff < -5 else "stable"
    else:
        pron_trend = "stable" if pron_scores_raw else "no_data"

    # --- Milestones catalog ---
    conn = database._connect()
    # Hisn D036 fix: send the real milestone catalog (id/name/name_ar/level
    # for all 15 real milestones), so the frontend can render real IDs and
    # names instead of the previous hardcoded, entirely fictional 12-ID list
    # that shared zero overlap with any real milestone_id.
    milestones_catalog = _get_milestones_catalog()

    # --- Assessments (last 8 weeks) ---
    assessments_raw = conn.execute(
        "SELECT week_number, overall_score, assessed_at FROM assessments WHERE discord_id=? ORDER BY week_number DESC LIMIT 8",
        (discord_id,),
    ).fetchall()
    assessments = [{"week": r["week_number"], "score": r["overall_score"], "date": r["assessed_at"]} for r in assessments_raw]

    # --- SRS stats ---
    srs_due = conn.execute(
        "SELECT COUNT(*) as cnt FROM vocab_srs WHERE discord_id=? AND next_review<=?",
        (discord_id, today),
    ).fetchone()["cnt"]
    srs_mastered = conn.execute(
        "SELECT COUNT(*) as cnt FROM vocab_srs WHERE discord_id=? AND interval_days>=21",
        (discord_id,),
    ).fetchone()["cnt"]
    srs_total = conn.execute(
        "SELECT COUNT(*) as cnt FROM vocab_srs WHERE discord_id=?",
        (discord_id,),
    ).fetchone()["cnt"]
    srs_accuracy = round((srs_mastered / srs_total * 100), 1) if srs_total > 0 else 0

    # --- Week activity (7-day grid) ---
    week_activity = {}
    task_types = ["accent", "shadowing", "listening", "vocab", "writing", "grammar", "speaking"]
    _today_local = database._today_local()
    for day_offset in range(7):
        d = (_today_local - datetime.timedelta(days=day_offset)).isoformat()
        day_subs = conn.execute(
            "SELECT task_id FROM daily_submissions WHERE discord_id=? AND date=?",
            (discord_id, d),
        ).fetchall()
        day_tasks = [r["task_id"] for r in day_subs]
        day_name = (_today_local - datetime.timedelta(days=day_offset)).strftime("%a")
        week_activity[day_name] = {t: (t in day_tasks) for t in task_types}

    # --- Leaderboard rank ---
    rank_row = conn.execute(
        """SELECT COUNT(*) + 1 as rank FROM members
           WHERE status='active' AND total_points > ?""",
        (member["total_points"],),
    ).fetchone()
    leaderboard_rank = rank_row["rank"] if rank_row else 0

    # --- Nour study tips ---
    # The legacy nour_study_tips table (Wuslah W4) was removed; it was
    # superseded by the weekly growth letter (Masar M2, served via
    # /api/growth-letter). The dashboard's tips card no longer sources
    # from it, so this is always an empty list now.
    nour_tips = []

    conn.close()

    # --- Difficulty level (Dhaka' adaptive engine) ---
    difficulty_level = member.get("difficulty_level", 2)

    # --- Level progress (CEFR-aware) ---
    # Gamified XP bar: total_points relative to the CEFR level thresholds
    # (config.CEFR_XP_THRESHOLDS). Any level key works — a legacy record (L0-L3)
    # is normalized to its CEFR level via config.cefr_key(), and at the top of
    # the ladder (C2, no next level) the bar reads 100%.
    current_level = member.get("level", "A1")
    xp_in_level, xp_needed, level_pct = _level_progress(
        member["total_points"], current_level)

    # --- Days since active ---
    last_active = member.get("last_active_at", "")
    try:
        last_dt = datetime.datetime.fromisoformat(last_active.replace("Z", ""))
        days_since_active = (datetime.datetime.now() - last_dt).days
    except (ValueError, TypeError, AttributeError):
        days_since_active = 0

    # --- Masar M1.2: Momentum Score (fixes Hisn D012) ---
    # Only included when the flag is enabled for this specific member
    # (per-member allowlist supported, same as every other flag check
    # in this codebase). Omitted entirely when disabled -- NOT sent as
    # null/zero -- so the frontend's existing fallback to the old XP
    # bar behavior needs no special-casing and this is a safe,
    # instantly-revertible addition (D010's flag-gating lesson: gate
    # the DATA, not just a display toggle client-side).
    momentum = None
    if database.is_feature_enabled("masar_momentum_score", discord_id):
        from . import narrative_engine
        momentum = narrative_engine.momentum_score(discord_id)

    dashboard = {
        "discord_id": discord_id,
        "discord_name": member.get("discord_name", "").split("#")[0],
        "level": current_level,
        "streak": member.get("current_streak", 0),
        "longest_streak": member.get("longest_streak", 0),
        "total_points": member.get("total_points", 0),
        "leaderboard_rank": leaderboard_rank,
        "days_since_active": days_since_active,
        "difficulty_level": difficulty_level,
        "pronunciation": {
            "scores_14d": pron_scores,
            "average": pron_avg,
            "trend": pron_trend,
        },
        "milestones_catalog": milestones_catalog,
        "assessments": assessments,
        "srs": {
            "due_count": srs_due,
            "mastered_count": srs_mastered,
            "total_count": srs_total,
            "accuracy_pct": srs_accuracy,
        },
        "week_activity": week_activity,
        "level_progress": {
            "current_xp": xp_in_level,
            "needed_for_next": xp_needed,
            "pct": level_pct,
        },
        "nour_tips": nour_tips,
    }
    if momentum is not None:
        dashboard["momentum"] = momentum

    # Itqan weekly-assessment progress (weeks mastered / total / streak).
    # Flag-gated + conditionally added (never null) so the frontend's fallback
    # needs no special-casing and this stays instantly revertible.
    if database.is_feature_enabled("itqan_weekly_assessment", discord_id):
        dashboard["itqan"] = database.itqan_progress(discord_id, current_level)

    return web.json_response(dashboard, headers=_cors_headers())


# ============================================================
#  WUSLAH W0.2: /api/leaderboard — top 10 + requester's rank
# ============================================================

@routes.get("/api/leaderboard")
async def get_leaderboard(request: web.Request) -> web.Response:
    """Return top 10 students by points + requester's own rank."""
    token = request.query.get("token", "")
    if not token:
        return web.json_response({"error": "token required"}, status=400)

    if not _check_rate_limit(token):
        return web.json_response({"error": "rate limit exceeded"}, status=429)

    if not database.is_feature_enabled("wuslah_dashboard_api"):
        return web.json_response({"error": "dashboard API not enabled"}, status=503)

    member = database.get_member_by_token(token)
    if not member:
        return web.json_response({"error": "invalid token"}, status=404)

    _touch_token(token)

    top = database.leaderboard(limit=10)
    top_list = [
        {
            "name": (r.get("discord_name") or "?").split("#")[0],
            "level": r.get("level", "?"),
            "points": r.get("total_points", 0),
            "streak": r.get("current_streak", 0),
        }
        for r in top
    ]

    # Requester's rank
    conn = database._connect()
    rank_row = conn.execute(
        "SELECT COUNT(*) + 1 as rank FROM members WHERE status='active' AND total_points > ?",
        (member["total_points"],),
    ).fetchone()
    conn.close()

    return web.json_response({
        "top": top_list,
        "your_rank": rank_row["rank"] if rank_row else 0,
        "your_points": member.get("total_points", 0),
        "your_name": (member.get("discord_name") or "?").split("#")[0],
    }, headers=_cors_headers())


# ============================================================
#  WUSLAH W2: POST /api/complete-exercise — cross-platform task confirmation
# ============================================================

@routes.post("/api/complete-exercise")
async def post_complete_exercise(request: web.Request) -> web.Response:
    """Record a web-based exercise completion in the bot's database.

    Writes to daily_submissions exactly as !done does — the streak
    engine, points, celebrations all fire on the next Discord event
    that reads this data. The UNIQUE constraint on
    (discord_id, date, task_id) prevents double-counting if the student
    also runs !done on Discord for the same task.
    """
    try:
        data = await request.json()
    except (json.JSONDecodeError, Exception):
        return web.json_response({"error": "invalid JSON"}, status=400)

    token = data.get("token", "")
    exercise_type = data.get("exercise_type", "")

    if not token or not exercise_type:
        return web.json_response({"error": "token and exercise_type required"}, status=400)

    if not _check_rate_limit(token):
        return web.json_response({"error": "rate limit exceeded"}, status=429)

    if not database.is_feature_enabled("wuslah_exercise_confirm"):
        return web.json_response({"error": "exercise confirmation not enabled"}, status=503)

    member = database.get_member_by_token(token)
    if not member:
        return web.json_response({"error": "invalid token"}, status=404)

    # Validate exercise_type
    valid_types = ["accent", "shadowing", "listening", "vocab", "writing", "grammar", "speaking"]
    if exercise_type not in valid_types:
        return web.json_response({"error": f"invalid exercise_type, must be one of: {', '.join(valid_types)}"}, status=400)

    import datetime
    discord_id = member["discord_id"]
    # NOTE on dates: this handler no longer computes its own "today". The
    # submission is logged by tasks.process_submission under tasks.today_str(),
    # which is the CANONICAL Asia/Dubai logging date every reader compares
    # against (see database._today_local()'s docstring). That preserves the
    # audit fix for the 00:00-04:00 Dubai window -- a web confirmation must be
    # logged under the same date it is later read back under, or it shows as
    # "still remaining".

    # ONE award path (Ijtihad Phase 0.2). This endpoint used to call
    # log_submission + add_points(POINTS_PER_TASK) directly and NEVER call
    # update_streak -- so a task completed here earned points but no streak
    # credit, unlike the identical action on Discord (!done) or via
    # /api/practice-complete, which both go through tasks.process_submission.
    # Its own spec (ecosystem-harmony W2.1) always said this endpoint should
    # "update streak, award points exactly like !done does"; it just never did.
    # Routing through process_submission makes that true, and gives seasonal
    # scoring a single choke point so Discord and web can never disagree.
    # process_submission calls log_submission itself and returns new=False on a
    # duplicate, preserving this endpoint's idempotency.
    from . import tasks
    name = member.get("discord_name") or "Student"
    try:
        result = await tasks.process_submission(discord_id, name, exercise_type)
        added = bool(result.get("new"))
    except Exception as e:
        logger.warning(f"complete-exercise: process_submission failed: {e}")
        added = False

    if added:
        # Touch last_active (process_submission does not do this).
        database.update_member(discord_id, last_active_at=datetime.datetime.now().isoformat())

    # Return current tasks_today count
    tasks_today = len(database.tasks_completed_today(discord_id))
    _touch_token(token)

    return web.json_response({
        "ok": True,
        "added": added,
        "tasks_today": tasks_today,
        "total_tasks": 7,
    }, headers=_cors_headers())


# ============================================================
#  WUSLAH W3: Expanded /api/progress with adaptive fields
# ============================================================
# (Already handled by /api/dashboard which includes difficulty_level,
#  days_since_active, and pronunciation data. The legacy /api/progress
#  endpoint is left unchanged for backwards compatibility. The web JS
#  in app.js uses ConnectedProgress which hits /api/progress — we add
#  the adaptive fields there too so existing pages benefit.)

@routes.get("/api/progress-v2")
async def get_progress_v2(request: web.Request) -> web.Response:
    """Enhanced progress endpoint with adaptive practice fields.

    Extends the legacy /api/progress with: difficulty_level,
    days_since_active, weak_phonemes, recommended_exercise, srs_due_count.
    Used by app.js ConnectedProgress for adaptive behavior on practice pages.
    """
    token = request.query.get("token", "")
    if not token:
        return web.json_response({"error": "token required"}, status=400)

    if not _check_rate_limit(token):
        return web.json_response({"error": "rate limit exceeded"}, status=429)

    if not database.is_feature_enabled("wuslah_adaptive"):
        return web.json_response({"error": "adaptive progress API not enabled"}, status=503)

    member = database.get_member_by_token(token)
    if not member:
        return web.json_response({"error": "invalid token"}, status=404)

    _touch_token(token)

    import datetime
    discord_id = member["discord_id"]
    today = database._today_local().isoformat()  # Asia/Dubai (audit fix)

    # Basic progress (same as legacy)
    streak = member.get("current_streak", 0)
    level = member.get("level", "A1")
    tasks_today = len(database.tasks_completed_today(discord_id))

    # Adaptive fields
    difficulty_level = member.get("difficulty_level", 2)

    # Days since active
    last_active = member.get("last_active_at", "")
    try:
        last_dt = datetime.datetime.fromisoformat(last_active.replace("Z", ""))
        days_since_active = (datetime.datetime.now() - last_dt).days
    except (ValueError, TypeError, AttributeError):
        days_since_active = 0

    # SRS due count
    conn = database._connect()
    srs_due = conn.execute(
        "SELECT COUNT(*) as cnt FROM vocab_srs WHERE discord_id=? AND next_review<=?",
        (discord_id, today),
    ).fetchone()["cnt"]

    # Weak phonemes (phonemes scoring below 65% in last 7 days)
    pron_scores = database.get_recent_scores(discord_id, days=7)
    phoneme_scores = {}
    for s in pron_scores:
        tid = s.get("task_id", "")
        if tid not in phoneme_scores:
            phoneme_scores[tid] = []
        phoneme_scores[tid].append(s["score"])
    weak_phonemes = [tid for tid, scores in phoneme_scores.items()
                     if sum(scores)/len(scores) < 65]

    # Recommended exercise (simplest heuristic: what hasn't been done today)
    today_subs = conn.execute(
        "SELECT task_id FROM daily_submissions WHERE discord_id=? AND date=?",
        (discord_id, today),
    ).fetchall()
    done_today = {r["task_id"] for r in today_subs}
    conn.close()

    exercise_priority = ["accent", "vocab", "shadowing", "listening", "writing", "grammar", "speaking"]
    recommended = next((e for e in exercise_priority if e not in done_today), None)

    return web.json_response({
        "streak": streak,
        "level": level,
        "tasks_today": tasks_today,
        "difficulty_level": difficulty_level,
        "days_since_active": days_since_active,
        "srs_due_count": srs_due,
        "weak_phonemes": weak_phonemes[:3],
        "recommended_exercise": recommended,
    }, headers=_cors_headers())


# ============================================================
#  MASAR M2.4: /api/growth-letter — Nour's Weekly Growth Letter
#  (fixes Hisn D020, replaces /api/nour-tips below)
# ============================================================

@routes.get("/api/growth-letter")
async def get_growth_letter(request: web.Request) -> web.Response:
    """Return the most recently generated Weekly Growth Letter for the
    student, cached in nour_growth_letters by nour_growth_letter_task()
    (bot.py) — zero AI cost per page load, same caching pattern as the
    old /api/nour-tips endpoint below.

    Same flag-gating pattern already correctly used elsewhere in this
    file (top-level `is_feature_enabled()` call inside the handler,
    confirmed via Hisn D010's fix as the pattern that cannot be
    silently bypassed) — this endpoint reuses that exact pattern
    rather than inventing a new gating approach.
    """
    token = request.query.get("token", "")
    if not token:
        return web.json_response({"error": "token required"}, status=400)

    if not _check_rate_limit(token):
        return web.json_response({"error": "rate limit exceeded"}, status=429)

    member = database.get_member_by_token(token)
    if not member:
        return web.json_response({"error": "invalid token"}, status=404)

    # Deliberately NO early no-discord_id flag check here (unlike some
    # other endpoints in this file) -- is_feature_enabled(name) with no
    # discord_id only returns True when the flag's allowed_ids is EMPTY
    # (see its own docstring). An early check here, before we know WHO
    # is asking, would incorrectly reject every member whenever the
    # flag is scoped to a restricted allowlist -- exactly the gradual
    # beta-squad rollout this flag is meant to support. The single
    # per-member check below (run only once we know discord_id) is both
    # correct and sufficient: it still returns False for everyone when
    # the flag is fully OFF, and True only for allowlisted members when
    # it's restricted.
    discord_id = member["discord_id"]
    if not database.is_feature_enabled("masar_growth_letter", discord_id):
        return web.json_response({"error": "growth letter API not enabled"}, status=503)

    _touch_token(token)

    letter = database.get_latest_growth_letter(discord_id)
    if not letter:
        return web.json_response({
            "letter": None,
            "generated_at": None,
            "source": None,
        }, headers=_cors_headers())

    return web.json_response({
        "letter": letter["letter_text"],
        "generated_at": letter["generated_at"],
        "source": letter["source"],
    }, headers=_cors_headers())


# ============================================================
#  WUSLAH W4: /api/nour-tips — study tips
#  (LEGACY — superseded by /api/growth-letter above per Masar M2. The
#  backing nour_study_tips cache table was removed, so this endpoint
#  now always returns generic level-appropriate tips. Kept in place so
#  any in-flight dashboard session still calling it keeps working.)
# ============================================================

@routes.get("/api/nour-tips")
async def get_nour_tips(request: web.Request) -> web.Response:
    """Return study tips for the student.

    The personalized cache (nour_study_tips) was removed along with the
    concierge subsystem; this endpoint now always serves generic
    level-appropriate tips — zero AI cost per page load.
    """
    token = request.query.get("token", "")
    if not token:
        return web.json_response({"error": "token required"}, status=400)

    if not _check_rate_limit(token):
        return web.json_response({"error": "rate limit exceeded"}, status=429)

    if not database.is_feature_enabled("wuslah_nour_tips"):
        return web.json_response({"error": "study tips API not enabled"}, status=503)

    member = database.get_member_by_token(token)
    if not member:
        return web.json_response({"error": "invalid token"}, status=404)

    _touch_token(token)
    level = member.get("level", "A1")

    # Generic level-appropriate tips (the personalized cache was removed).
    generic_tips = _generic_tips_for_level(level)
    return web.json_response({
        "tips": generic_tips,
        "generated_at": None,
        "source": "generic",
    }, headers=_cors_headers())


def _generic_tips_for_level(level: str) -> list[str]:
    """Static fallback tips when AI-generated ones aren't available."""
    tips = {
        "A1": [
            "Focus on daily accent drills — 5 minutes of practice builds muscle memory",
            "Use the SRS flashcards before bed — sleep consolidates vocabulary",
            "Record yourself and compare with the model — you'll hear the difference",
        ],
        "A2": [
            "Shadow full sentences now, not just words — build natural rhythm",
            "Try the dictation exercises — writing what you hear strengthens listening",
            "Review your pronunciation scores — focus on any phoneme below 70%",
        ],
        "B1": [
            "Practice speaking in complete paragraphs — fluency over perfection",
            "Challenge yourself with the writing exercises — express original thoughts",
            "Listen to the model audio at full speed — train your ear for natural pace",
        ],
        "B2": [
            "Focus on nuance — intonation, emphasis, and emotional expression",
            "Try explaining complex ideas in English without translating from Arabic",
            "Record a 2-minute monologue weekly — track your confidence growth",
        ],
        "C1": [
            "Refine register — switch between formal and casual English deliberately",
            "Argue both sides of a topic aloud — build spontaneous, nuanced fluency",
            "Read authentic long-form English daily and summarise it in your own words",
        ],
        "C2": [
            "Polish idiom and collocation — aim for natural, native-like phrasing",
            "Present a complex idea for 5 minutes with no notes — master coherence",
            "Critique a nuanced text in English — precision of expression is the goal",
        ],
    }
    return tips.get(config.cefr_key(level), tips["A1"])


# ============================================================
#  WUSLAH W5: /api/notifications — read/update preferences
# ============================================================

@routes.get("/api/notifications")
async def get_notifications(request: web.Request) -> web.Response:
    """Return current notification preferences for the student."""
    token = request.query.get("token", "")
    if not token:
        return web.json_response({"error": "token required"}, status=400)

    if not _check_rate_limit(token):
        return web.json_response({"error": "rate limit exceeded"}, status=429)

    member = database.get_member_by_token(token)
    if not member:
        return web.json_response({"error": "invalid token"}, status=404)

    _touch_token(token)
    prefs = database.get_notification_prefs(member["discord_id"])
    return web.json_response(prefs, headers=_cors_headers())


@routes.post("/api/notifications")
async def post_notifications(request: web.Request) -> web.Response:
    """Update notification preferences from the web dashboard."""
    try:
        data = await request.json()
    except (json.JSONDecodeError, Exception):
        return web.json_response({"error": "invalid JSON"}, status=400)

    token = data.get("token", "")
    if not token:
        return web.json_response({"error": "token required"}, status=400)

    if not _check_rate_limit(token):
        return web.json_response({"error": "rate limit exceeded"}, status=429)

    member = database.get_member_by_token(token)
    if not member:
        return web.json_response({"error": "invalid token"}, status=404)

    discord_id = member["discord_id"]
    _touch_token(token)

    # Allowed fields to update
    allowed_fields = {
        "morning_dm", "evening_dm", "streak_alert",
        "celebrations", "social_proof", "weekly_summary",
    }

    conn = database._connect()
    try:
        for key, value in data.items():
            if key in allowed_fields:
                # Coerce to int (0 or 1)
                val = 1 if value else 0
                conn.execute(
                    f"""INSERT INTO notification_preferences (discord_id, {key})
                        VALUES (?, ?)
                        ON CONFLICT(discord_id) DO UPDATE SET {key}=excluded.{key}, updated_at=datetime('now')""",
                    (discord_id, val),
                )
        conn.commit()
    finally:
        conn.close()

    prefs = database.get_notification_prefs(discord_id)
    return web.json_response({"ok": True, "preferences": prefs}, headers=_cors_headers())


# ============================================================
#  HISSAR P3: /api/validate-token — lightweight token check
# ============================================================

@routes.get("/api/validate-token")
async def get_validate_token(request: web.Request) -> web.Response:
    """Lightweight token validation for content gating on practice pages.

    Hissar P3: practice pages hide their content until this endpoint
    confirms the student holds a valid link token. Much lighter than
    /api/progress (no DB aggregation, no heavy joins) — just checks
    that the token exists and is associated with an active member.

    Returns:
      200 {"valid": true, "name": "...", "level": "L0"}  — token OK
      401 {"valid": false}                                — invalid/expired
      429 {"error": "rate limit exceeded"}                — throttled
    """
    token = request.query.get("token", "")
    if not token:
        return web.json_response({"valid": False}, status=401, headers=_cors_headers(request))

    if not _check_rate_limit(token):
        return web.json_response({"error": "rate limit exceeded"}, status=429, headers=_cors_headers(request))

    member = database.get_member_by_token(token)
    if not member:
        return web.json_response({"valid": False}, status=401, headers=_cors_headers(request))

    _touch_token(token)
    await _log_ip_and_check(token, request)
    return web.json_response({
        "valid": True,
        "name": (member.get("discord_name") or "Student").split("#")[0],
        "level": member.get("level", "A1"),
    }, headers=_cors_headers(request))


# ============================================================
#  DARB (درب) — Phase 1 endpoints (claim, session, calendar, complete)
# ============================================================
#
# These power the gated personal practice experience. They authenticate
# via the signed `empire_session` device token (Darb), NOT the legacy
# link token. Dormant until the practice-page UI (Phase 2) and edge gate
# (Phase 3) use them.

def _client_ip(request: web.Request) -> str:
    ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not ip:
        ip = request.headers.get("X-Real-IP", "")
    if not ip and request.transport:
        peer = request.transport.get_extra_info("peername")
        if peer:
            ip = peer[0]
    return ip or ""


def _session_from_request(request: web.Request):
    """Return the verified + non-revoked Darb session payload, or None.

    Accepts the token from the `empire_session` cookie (browser), an
    `X-Darb-Session` header, or a `?session=` query param (for testing
    without a browser). Also confirms the device session isn't revoked."""
    from . import darb
    tok = (request.cookies.get("empire_session")
           or request.headers.get("X-Darb-Session")
           or request.query.get("session", ""))
    payload = darb.verify_session(tok)
    if not payload:
        return None
    sid = payload.get("sid")
    if not sid or not database.is_device_session_active(sid):
        return None
    return payload


@routes.post("/api/claim")
async def post_claim(request: web.Request) -> web.Response:
    """Flow A: exchange a one-time claim code for a durable session token."""
    from . import darb
    try:
        body = await request.json()
    except Exception:
        body = {}
    code = (body.get("code") or "").strip()
    if not code:
        return web.json_response({"ok": False, "error": "missing code"},
                                 status=400, headers=_cors_headers(request))
    result = await darb.claim(
        code, ip=_client_ip(request),
        user_agent=request.headers.get("User-Agent", ""),
    )
    if not result:
        return web.json_response({"ok": False, "error": "invalid or expired code"},
                                 status=400, headers=_cors_headers(request))
    return web.json_response(
        {"ok": True, "token": result["token"], "level": result["level"],
         "name": result["name"]},
        headers=_cors_headers(request),
    )


@routes.get("/api/session-status")
async def get_session_status(request: web.Request) -> web.Response:
    """Edge revocation check: is this session still valid + not revoked?"""
    payload = _session_from_request(request)
    if not payload:
        return web.json_response({"valid": False}, status=401,
                                 headers=_cors_headers(request))
    database.touch_device_session(payload["sid"])
    return web.json_response({"valid": True, "revoked": False,
                             "level": payload.get("lvl")},
                            headers=_cors_headers(request))


@routes.get("/api/calendar")
async def get_calendar(request: web.Request) -> web.Response:
    """The student's personal, join-anchored calendar (their level only)."""
    from . import darb
    payload = _session_from_request(request)
    if not payload:
        return web.json_response({"error": "unauthorized"}, status=401,
                                 headers=_cors_headers(request))
    database.touch_device_session(payload["sid"])
    cal = darb.build_calendar(payload["did"])
    if cal is None:
        return web.json_response({"error": "not found"}, status=404,
                                 headers=_cors_headers(request))
    return web.json_response(cal, headers=_cors_headers(request))


@routes.post("/api/practice-complete")
async def post_practice_complete(request: web.Request) -> web.Response:
    """Flow C: record a content-day exercise completion. Runs the
    canonical points/streak path (`process_submission`, same as Discord
    `!done`) AND the content-day mastery/tier upsert."""
    from . import curriculum
    payload = _session_from_request(request)
    if not payload:
        return web.json_response({"ok": False, "error": "unauthorized"},
                                 status=401, headers=_cors_headers(request))
    try:
        body = await request.json()
    except Exception:
        body = {}
    discord_id = payload["did"]
    level = payload.get("lvl", "A1")
    exercise = (body.get("exercise") or "").strip()
    try:
        week = int(body.get("week"))
        day = int(body.get("day"))
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "bad week/day"},
                                 status=400, headers=_cors_headers(request))
    if exercise not in database.TRACKED_EXERCISES:
        return web.json_response({"ok": False, "error": "bad exercise"},
                                 status=400, headers=_cors_headers(request))
    if not (1 <= week <= curriculum.max_week_for_level(level)) or not (1 <= day <= 7):
        return web.json_response({"ok": False, "error": "week/day out of range"},
                                 status=400, headers=_cors_headers(request))
    database.touch_device_session(payload["sid"])

    # Canonical points/streak (identical path to Discord !done). Duplicate
    # same-day completions are absorbed by log_submission's UNIQUE
    # constraint (no double points). Best-effort — never fail the
    # completion over a feedback/streak hiccup.
    member = database.get_member(discord_id)
    name = member.get("discord_name", "Student") if member else "Student"
    is_weekly = exercise in database.WEEKLY_EXERCISES
    if not is_weekly:
        try:
            from . import tasks
            await tasks.process_submission(discord_id, name, exercise)
        except Exception as e:
            logger.warning(f"practice-complete: process_submission failed: {e}")

    # Content-day mastery/tier truth (the calendar's source of truth).
    m = database.record_practice_mastery(discord_id, level, week, day, exercise)

    if is_weekly:
        # Weekly exercises deliberately bypass tasks.process_submission:
        # that function logs a DAILY submission and awards POINTS_ALL_TASKS
        # when count_submissions_for_date() hits exactly 7. Logging grammar
        # there would let a student reach "7 submissions today" WITHOUT
        # doing all 7 daily tasks (grammar + 6 tasks), handing out the
        # all-tasks bonus unearned, and would also pollute streak counting.
        # So we award the flat per-task points directly and leave the daily
        # streak/bonus machinery completely untouched. Only on a genuine
        # tier increment, so re-opening the page cannot farm points.
        if m.get("incremented"):
            try:
                database.add_points(discord_id, config.POINTS_PER_TASK,
                                    f"weekly:{exercise}")
            except Exception as e:
                logger.warning(f"practice-complete: weekly points failed: {e}")
    day_state = database.get_calendar_mastery(discord_id, level).get((week, day), {})
    return web.json_response({
        "ok": True,
        "exercise": exercise,
        "exercise_tier": m["exercise_tier"],
        "incremented": m["incremented"],
        "day_tier": day_state.get("day_tier", 0),
        "day_done": day_state.get("done", False),
    }, headers=_cors_headers(request))


# ============================================================
#  DARB Phase 4 — Submit Recording → #showcase + auto-complete
# ============================================================

# Nutq (pronunciation-feedback spec): curriculum day-name convention is
# Saturday=0 .. Friday=6 (same as tasks.generate_daily_tasks). day is 1-7.
_NUTQ_DAY_NAMES = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def _drill_primary_text(drill) -> str:
    """The exact sentence/passage the practice page SHOWS the student to record,
    for a given accent drill. Mirrors empire-dojo scripts/generate.py
    normalize_drill().primary_text so scoring targets exactly what was displayed
    (Nutq 2 R10 — closes the accent/shadow/day-7 drift):
      - review drill (day 6):     record_this (fallback: first challenge sentence)
      - assessment drill (day 7): test_yourself.passage
      - normal drill:             record_this (fallback: first sentence_practice)
    Returns "" when there's no scoreable target (→ scoring cleanly skips)."""
    if not isinstance(drill, dict):
        return ""
    dtype = drill.get("type")
    if dtype == "review":
        cs = drill.get("challenge_sentences") or []
        return (drill.get("record_this") or (cs[0] if cs else "") or "").strip()
    if dtype == "assessment":
        ty = drill.get("test_yourself") if isinstance(drill.get("test_yourself"), dict) else {}
        return (ty.get("passage") or "").strip()
    sp = drill.get("sentence_practice") or []
    return (drill.get("record_this") or (sp[0] if sp else "") or "").strip()


def _pronunciation_expected_text(week: int, day: int, level: str) -> str:
    """The target text to score an accent/shadow recording against for
    (week, day, level) — the SAME text the page displays (see _drill_primary_text;
    both the accent and shadowing pages render the normalized accent drill's
    primary_text). Returns "" if there's no target text (→ scoring skipped)."""
    from . import curriculum
    try:
        day_index = max(0, min(6, int(day) - 1))
        day_name = _NUTQ_DAY_NAMES[day_index]
        daily = curriculum.get_daily_content(int(week), day_name, day_index, level)
        return _drill_primary_text(daily.get("accent_drill"))
    except Exception:
        return ""


@routes.post("/api/submit-recording")
async def post_submit_recording(request: web.Request) -> web.Response:
    """Flow D: upload a recording from the practice page → bot posts it
    to the student's #lN-showcase channel on Discord, then auto-marks
    the exercise as done (same as if they ran !done).

    Expects multipart/form-data with:
      - audio: the recording file (audio/webm, audio/mp4, audio/ogg, etc.)
      - exercise: one of accent/shadow/vocab/listening
      - week: integer
      - day: integer

    Auth: Darb session (same as other Darb endpoints).
    """
    payload = _session_from_request(request)
    if not payload:
        return web.json_response({"ok": False, "error": "unauthorized"},
                                 status=401, headers=_cors_headers(request))

    discord_id = payload["did"]
    level = payload.get("lvl", "A1")

    # Parse multipart
    try:
        reader = await request.multipart()
    except Exception:
        return web.json_response({"ok": False, "error": "multipart required"},
                                 status=400, headers=_cors_headers(request))

    audio_data = None
    audio_filename = "recording.webm"
    exercise = None
    week = None
    day = None

    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name == "audio":
            audio_data = await part.read()  # max enforced by client_max_size
            # Determine filename from content type
            ct = part.headers.get("Content-Type", "audio/webm")
            if "mp4" in ct or "m4a" in ct:
                audio_filename = "recording.m4a"
            elif "ogg" in ct:
                audio_filename = "recording.ogg"
            else:
                audio_filename = "recording.webm"
        elif part.name == "exercise":
            exercise = (await part.text()).strip()
        elif part.name == "week":
            try:
                week = int(await part.text())
            except (ValueError, TypeError):
                pass
        elif part.name == "day":
            try:
                day = int(await part.text())
            except (ValueError, TypeError):
                pass

    if not audio_data:
        return web.json_response({"ok": False, "error": "no audio file"},
                                 status=400, headers=_cors_headers(request))
    # Recording exercises = the 4 core practice exercises + speaking (E1).
    # Speaking is additive: it posts to #showcase and completes the speaking
    # daily task, but the calendar's "green" still needs the 4 core only
    # (get_calendar_mastery ignores non-core exercises), so existing green
    # days are grandfathered.
    if exercise not in database.PRACTICE_EXERCISES and exercise != "speaking":
        return web.json_response({"ok": False, "error": "bad exercise"},
                                 status=400, headers=_cors_headers(request))
    if not week or not day:
        return web.json_response({"ok": False, "error": "week and day required"},
                                 status=400, headers=_cors_headers(request))
    from . import curriculum
    if not (1 <= week <= curriculum.max_week_for_level(level)) or not (1 <= day <= 7):
        return web.json_response({"ok": False, "error": "week/day out of range"},
                                 status=400, headers=_cors_headers(request))

    # Get member info
    member_data = database.get_member(discord_id)
    if not member_data:
        return web.json_response({"ok": False, "error": "member not found"},
                                 status=404, headers=_cors_headers(request))
    name = member_data.get("discord_name", "Student")

    # Post to Discord #lN-showcase channel
    posted = await _post_recording_to_showcase(
        discord_id, level, name, exercise, week, day, audio_data, audio_filename
    )

    # Auto-complete: run process_submission + record_practice_mastery
    # (same as !done + Phase 2 wiring — best-effort, never fail the upload)
    try:
        from . import tasks as task_engine
        result = await task_engine.process_submission(discord_id, name, exercise)
    except Exception as e:
        logger.warning(f"submit-recording: process_submission failed: {e}")
        result = {"new": False}

    # Record mastery for the SPECIFIC content-day the student is practising
    # (from the form), NOT today. Bug fix: previously used today_week_day(),
    # so a recording made while catching up on a PAST day was credited to
    # today's day instead — the past day stayed stuck at 2/4 (only the
    # vocab/listening 'Done' checkbox, which correctly used the viewed day,
    # registered). Now accent/shadow catch-up reaches 4/4 like it should.
    try:
        database.record_practice_mastery(discord_id, level, week, day, exercise)
    except Exception as e:
        logger.warning(f"submit-recording: mastery recording failed: {e}")

    # Get updated day state for tier feedback
    day_state = database.get_calendar_mastery(discord_id, level).get((week, day), {})

    # Nutq (pronunciation-feedback spec) Phase 1: best-effort pronunciation
    # scoring for accent/shadow recordings. Runs AFTER completion + the
    # #showcase post above, so it can NEVER block or undo them. Flag-gated
    # (tatawwur_pronunciation), bounded by a timeout, and fully wrapped: any
    # failure/timeout/disable → {"scored": false} and the exercise still
    # completes exactly as before. Feedback is private to this authenticated
    # response (never posted publicly).
    # Nutq (grade-best-read model): a "Send to Discord" — INCLUDING the up-to-5
    # tier redos — is PRACTICE. It never spends Azure and shows NO number
    # (Option A): the only score a student ever sees is the accurate Azure
    # "official grade", earned on demand via /api/grade-best-read. Here we just
    # tell the flag-enabled student the grade button is available and whether
    # today's grade is already used. Completion + #showcase already happened
    # above and are never affected.
    pronunciation = {"scored": False}
    try:
        if exercise == "shadow" and \
                database.is_feature_enabled("tatawwur_pronunciation", discord_id):
            expected_text = _pronunciation_expected_text(week, day, level)
            if expected_text:
                today = database._today_local().isoformat()
                cap = _nutq_daily_cap(discord_id)
                pronunciation = {
                    "scored": False,          # Option A: no practice number
                    "practice": True,         # → frontend shows encouragement + grade button
                    "can_official_grade": True,
                    "official_grade_used": database.azure_calls_today(discord_id, today) >= cap,
                }
            else:
                logger.info(f"submit-recording: no shadow target text for w{week}d{day} "
                            f"{level} — grade button hidden")
    except Exception as e:
        logger.warning(f"submit-recording: pronunciation setup failed (non-fatal): {e}")

    return web.json_response({
        "ok": True,
        "posted": posted,
        "exercise": exercise,
        "exercise_tier": day_state.get("exercises", {}).get(exercise, 0),
        "day_tier": day_state.get("day_tier", 0),
        "day_done": day_state.get("done", False),
        "already_done": not result.get("new", True),
        "pronunciation": pronunciation,
    }, headers=_cors_headers(request))


@routes.post("/api/pronunciation-check")
async def post_pronunciation_check(request: web.Request) -> web.Response:
    """Nutq (pronunciation-feedback spec) Phase 3: score-ONLY re-check for the
    "try again" practice loop. Transcribes + scores + returns feedback, but does
    NOT post to #showcase, complete the exercise, touch mastery/points/streak,
    or persist a score. Private practice feedback only. Flag-gated; accent/shadow
    only; bounded by a timeout and fully wrapped so it never errors the client."""
    payload = _session_from_request(request)
    if not payload:
        return web.json_response({"ok": False, "error": "unauthorized"},
                                 status=401, headers=_cors_headers(request))
    discord_id = payload["did"]
    level = payload.get("lvl", "A1")

    if not database.is_feature_enabled("tatawwur_pronunciation", discord_id):
        # Feature off → nothing to check (client shows nothing).
        return web.json_response({"ok": True, "pronunciation": {"scored": False}},
                                 headers=_cors_headers(request))

    try:
        reader = await request.multipart()
    except Exception:
        return web.json_response({"ok": False, "error": "multipart required"},
                                 status=400, headers=_cors_headers(request))

    audio_data = None
    audio_filename = "recording.webm"
    exercise = None
    week = None
    day = None
    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name == "audio":
            audio_data = await part.read()
            ct = part.headers.get("Content-Type", "audio/webm")
            if "mp4" in ct or "m4a" in ct:
                audio_filename = "recording.m4a"
            elif "ogg" in ct:
                audio_filename = "recording.ogg"
            else:
                audio_filename = "recording.webm"
        elif part.name == "exercise":
            exercise = (await part.text()).strip()
        elif part.name == "week":
            try:
                week = int(await part.text())
            except (ValueError, TypeError):
                pass
        elif part.name == "day":
            try:
                day = int(await part.text())
            except (ValueError, TypeError):
                pass

    if not audio_data:
        return web.json_response({"ok": False, "error": "no audio file"},
                                 status=400, headers=_cors_headers(request))
    if exercise != "shadow":
        return web.json_response({"ok": False, "error": "bad exercise"},
                                 status=400, headers=_cors_headers(request))
    from . import curriculum
    if not week or not day or not (1 <= week <= curriculum.max_week_for_level(level)) \
            or not (1 <= day <= 7):
        return web.json_response({"ok": False, "error": "week/day out of range"},
                                 status=400, headers=_cors_headers(request))

    pronunciation = {"scored": False}
    try:
        expected_text = _pronunciation_expected_text(week, day, level)
        if expected_text:
            from . import pronunciation_scorer
            res = await asyncio.wait_for(
                pronunciation_scorer.score_recording_bytes(
                    audio_data, audio_filename, expected_text,
                    discord_id, exercise, level, store=False,  # private re-check
                    allow_azure=False,  # try-again = free engine only (never spend the daily Azure grade)
                ),
                timeout=config.NUTQ_SCORE_BUDGET_SECONDS,
            )
            if res and res.success:
                pronunciation = {
                    "scored": True,
                    "is_beginner_grace": False,  # Nutq: grace removed — "try again" shows a real score too
                    "score": round(res.score),
                    "feedback_en": res.feedback_en,
                    "feedback_ar": res.feedback_ar,
                    "missed_words": res.missed_words,
                    "transcript": res.transcript,
                    "expected": expected_text,
                }
    except asyncio.TimeoutError:
        logger.info("pronunciation-check: scoring timed out")
    except Exception as e:
        logger.warning(f"pronunciation-check failed (non-fatal): {e}")

    return web.json_response({"ok": True, "pronunciation": pronunciation},
                             headers=_cors_headers(request))


def _nutq_daily_cap(discord_id: str) -> int:
    """The per-student daily official-grade cap. Defaults to the global
    NUTQ_AZURE_MAX_CALLS_PER_DAY (owner-controlled, strict 1/day by default).
    PR3 will let the owner override this for specific students via /nutq cap."""
    try:
        override = database.nutq_daily_cap_override(discord_id)
        if override is not None:
            return int(override)
    except Exception:
        pass
    return config.NUTQ_AZURE_MAX_CALLS_PER_DAY


@routes.post("/api/grade-best-read")
async def post_grade_best_read(request: web.Request) -> web.Response:
    """Nutq (grade-best-read model): the student's ONE official pronunciation
    grade per day. Scores the submitted take with Azure (accurate) — atomically
    capped at N/day (default 1, PR1) — stores it, and posts it to the private
    teacher feed. Falls back to the free local engine only when Azure is
    unavailable (usage guard / not configured), and still consumes the daily
    slot so the button stays strictly 1/day regardless of engine.

    Deliberately does NOT post to #showcase, complete the exercise, or touch
    mastery/points/streak — completion is /api/submit-recording's job. This is
    purely the accurate score-of-record. Flag-gated; shadow only; bounded by a
    timeout and fully wrapped so it never errors the client."""
    payload = _session_from_request(request)
    if not payload:
        return web.json_response({"ok": False, "error": "unauthorized"},
                                 status=401, headers=_cors_headers(request))
    discord_id = payload["did"]
    level = payload.get("lvl", "A1")

    if not database.is_feature_enabled("tatawwur_pronunciation", discord_id):
        return web.json_response({"ok": True, "pronunciation": {"scored": False}},
                                 headers=_cors_headers(request))

    try:
        reader = await request.multipart()
    except Exception:
        return web.json_response({"ok": False, "error": "multipart required"},
                                 status=400, headers=_cors_headers(request))

    audio_data = None
    audio_filename = "recording.webm"
    exercise = None
    week = None
    day = None
    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name == "audio":
            audio_data = await part.read()
            ct = part.headers.get("Content-Type", "audio/webm")
            if "mp4" in ct or "m4a" in ct:
                audio_filename = "recording.m4a"
            elif "ogg" in ct:
                audio_filename = "recording.ogg"
            else:
                audio_filename = "recording.webm"
        elif part.name == "exercise":
            exercise = (await part.text()).strip()
        elif part.name == "week":
            try:
                week = int(await part.text())
            except (ValueError, TypeError):
                pass
        elif part.name == "day":
            try:
                day = int(await part.text())
            except (ValueError, TypeError):
                pass

    if not audio_data:
        return web.json_response({"ok": False, "error": "no audio file"},
                                 status=400, headers=_cors_headers(request))
    if exercise != "shadow":
        return web.json_response({"ok": False, "error": "bad exercise"},
                                 status=400, headers=_cors_headers(request))
    from . import curriculum
    if not week or not day or not (1 <= week <= curriculum.max_week_for_level(level)) \
            or not (1 <= day <= 7):
        return web.json_response({"ok": False, "error": "week/day out of range"},
                                 status=400, headers=_cors_headers(request))

    today = database._today_local().isoformat()
    cap = _nutq_daily_cap(discord_id)
    # Already used today's official grade → tell the client (button shows "graded
    # today"); never call Azure again.
    if database.azure_calls_today(discord_id, today) >= cap:
        return web.json_response(
            {"ok": True, "already_graded": True,
             "pronunciation": {"scored": False, "official_grade_used": True}},
            headers=_cors_headers(request))

    pronunciation = {"scored": False}
    try:
        expected_text = _pronunciation_expected_text(week, day, level)
        if expected_text:
            from . import pronunciation_scorer
            logger.info(f"grade-best-read: Azure-grading shadow w{week}d{day} {level} "
                        f"for {discord_id} (audio {len(audio_data)} bytes)")
            res = await asyncio.wait_for(
                pronunciation_scorer.score_recording_bytes(
                    audio_data, audio_filename, expected_text,
                    discord_id, exercise, level, allow_azure=True,
                ),
                timeout=config.NUTQ_SCORE_BUDGET_SECONDS,
            )
            if res and res.success:
                # If the official grade fell back to the free engine (Azure
                # unavailable at scale), still consume today's slot so the
                # button is strictly 1/day regardless of engine. (When Azure
                # WAS used, score_recording_bytes already reserved the slot.)
                if res.engine != "azure":
                    database.reserve_azure_call_today(discord_id, today, cap)
                pronunciation = {
                    "scored": True,
                    "official": True,
                    "is_beginner_grace": False,
                    "score": round(res.score),
                    "feedback_en": res.feedback_en,
                    "feedback_ar": res.feedback_ar,
                    "missed_words": res.missed_words,
                    "transcript": res.transcript,
                    "expected": expected_text,
                    "official_grade_used": True,
                }
    except asyncio.TimeoutError:
        logger.info("grade-best-read: scoring timed out")
    except Exception as e:
        logger.warning(f"grade-best-read failed (non-fatal): {e}")

    # Owner oversight: the official grade (and only the official grade) goes to
    # the private teacher feed.
    if pronunciation.get("scored"):
        member_data = database.get_member(discord_id) or {}
        name = member_data.get("discord_name", "Student")
        await _post_teacher_feed(name, exercise, week, day, pronunciation)

    return web.json_response({"ok": True, "pronunciation": pronunciation},
                             headers=_cors_headers(request))


async def _post_recording_to_showcase(discord_id: str, level: str, name: str,
                                       exercise: str, week: int, day: int,
                                       audio_data: bytes, filename: str) -> bool:
    """Post an audio recording to the student's #lN-showcase Discord channel.
    Returns True if posted successfully, False otherwise (best-effort)."""
    try:
        from . import bot as bot_mod, config
        import discord as discord_lib
        import io

        discord_bot = bot_mod.bot
        if not discord_bot or not discord_bot.is_ready():
            logger.warning("submit-recording: bot not ready, can't post to Discord")
            return False

        guild = discord_bot.get_guild(config.GUILD_ID)
        if not guild:
            logger.warning("submit-recording: guild not found")
            return False

        channel_name = f"{config.level_slug(level)}-showcase"
        channel = discord_lib.utils.get(guild.text_channels, name=channel_name)
        if not channel:
            logger.warning(f"submit-recording: channel {channel_name} not found")
            return False

        # Build the message
        exercise_names = {
            "accent": "Accent Drill",
            "shadow": "Shadowing",
            "vocab": "Vocabulary",
            "listening": "Listening",
            "speaking": "Speaking Practice",
        }
        ex_display = exercise_names.get(exercise, exercise)
        caption = f"🎙️ **{name}** — {ex_display} (Week {week}, Day {day})"

        # Send with audio file attachment
        audio_file = discord_lib.File(io.BytesIO(audio_data), filename=filename)
        await channel.send(content=caption, file=audio_file)
        logger.info(f"submit-recording: posted {filename} ({len(audio_data)} bytes) to #{channel_name} for {name}")
        return True

    except Exception as e:
        logger.error(f"submit-recording: Discord post failed: {e}")
        return False


async def _post_teacher_feed(name: str, exercise: str, week: int, day: int,
                             pronunciation: dict) -> None:
    """Nutq — post a student's daily pronunciation score to the owner-only
    'teacher feed' channel (config.NUTQ_TEACHER_FEED_CHANNEL_ID) for oversight.
    Student still sees their own feedback privately on the page. Best-effort:
    disabled when the channel id is 0; never raises to the caller."""
    try:
        cid = config.NUTQ_TEACHER_FEED_CHANNEL_ID
        if not cid or not (pronunciation or {}).get("scored"):
            return
        from . import bot as bot_mod
        discord_bot = bot_mod.bot
        if not discord_bot or not discord_bot.is_ready():
            return
        channel = discord_bot.get_channel(cid)
        if channel is None:
            channel = await discord_bot.fetch_channel(cid)
        missed = ", ".join(pronunciation.get("missed_words", []) or []) or "—"
        msg = (f"🎯 **Pronunciation** — **{name}** · Week {week} Day {day} · {exercise}\n"
               f"Score: **{pronunciation.get('score')}%**\n"
               f"Focus: {missed}\n"
               f"💬 {pronunciation.get('feedback_en', '')}")
        await channel.send(msg)
        logger.info(f"teacher-feed: posted score for {name} (w{week}d{day})")
    except Exception as e:  # noqa: BLE001 — oversight extra, never break the flow
        logger.warning(f"teacher-feed post failed (non-fatal): {e}")


# ============================================================
#  DARB — Vocab Review (SRS) via Darb session
# ============================================================

@routes.get("/api/darb/srs")
async def get_darb_srs(request: web.Request) -> web.Response:
    """Return the student's due SRS review words (Darb-session authed)."""
    payload = _session_from_request(request)
    if not payload:
        return web.json_response({"error": "unauthorized"}, status=401,
                                 headers=_cors_headers(request))
    database.touch_device_session(payload["sid"])
    data = database.get_srs_review_data(payload["did"])
    return web.json_response(data, headers=_cors_headers(request))


@routes.post("/api/darb/srs-review")
async def post_darb_srs_review(request: web.Request) -> web.Response:
    """Record an SRS review result (Darb-session authed)."""
    payload = _session_from_request(request)
    if not payload:
        return web.json_response({"ok": False, "error": "unauthorized"},
                                 status=401, headers=_cors_headers(request))
    try:
        body = await request.json()
    except Exception:
        body = {}
    word = (body.get("word") or "").strip()
    score = body.get("score")
    if not word or score is None:
        return web.json_response({"ok": False, "error": "word and score required"},
                                 status=400, headers=_cors_headers(request))
    try:
        score = int(score)
        if not (0 <= score <= 5):
            raise ValueError
    except (ValueError, TypeError):
        return web.json_response({"ok": False, "error": "score must be 0-5"},
                                 status=400, headers=_cors_headers(request))
    database.record_srs_review(payload["did"], word, score)
    database.touch_device_session(payload["sid"])
    return web.json_response({"ok": True}, headers=_cors_headers(request))


# ============================================================
#  ITQAN (weekly assessment) — attempt lifecycle API  (Phase 3)
# ============================================================
#
# All four endpoints are Darb-session authed AND gated behind the
# `itqan_weekly_assessment` flag (OFF until Phase 9). The scoring, unlock
# gate, cooldown, single-attempt and time-limit rules all live server-side
# in `assessment.py` — the client is never trusted.

def _itqan_gate(request: web.Request):
    """Shared auth + flag gate. Returns (payload, None) on success, or
    (None, web.Response) with the error to return."""
    payload = _session_from_request(request)
    if not payload:
        return None, web.json_response({"ok": False, "error": "unauthorized"},
                                       status=401, headers=_cors_headers(request))
    if not database.is_feature_enabled("itqan_weekly_assessment", payload["did"]):
        return None, web.json_response({"ok": False, "enabled": False,
                                        "error": "disabled"},
                                       status=403, headers=_cors_headers(request))
    return payload, None


def _itqan_week_arg(raw, level: str):
    """Parse + range-check a week value. Returns int or None."""
    from . import curriculum
    try:
        week = int(raw)
    except (TypeError, ValueError):
        return None
    if not (1 <= week <= curriculum.max_week_for_level(level)):
        return None
    return week


@routes.get("/api/assessment/status")
async def get_assessment_status(request: web.Request) -> web.Response:
    """State for the page/calendar. With ?week=N: that week's state
    (locked | available | in_progress | cooldown | not_yet | mastered).
    Without it: the enabled flag + the set of already-mastered weeks."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    discord_id, level = payload["did"], payload.get("lvl", "A1")
    database.touch_device_session(payload["sid"])
    cfg = database.get_itqan_config()
    thresholds = {
        "mastery_pass_pct": cfg["itqan_mastery_pass_pct"],
        "consistency_pass_pct": cfg["itqan_consistency_pass_pct"],
        "distinction_pct": cfg["itqan_distinction_pct"],
        "time_limit_min": cfg["itqan_time_limit_min"],
    }
    raw_week = request.query.get("week")
    if raw_week is not None:
        week = _itqan_week_arg(raw_week, level)
        if week is None:
            return web.json_response({"ok": False, "error": "bad week"},
                                     status=400, headers=_cors_headers(request))
        state = assessment.get_week_state(discord_id, level, week)
        return web.json_response({"ok": True, "enabled": True, "week": week,
                                  "config": thresholds, **state},
                                 headers=_cors_headers(request))
    return web.json_response({
        "ok": True, "enabled": True, "config": thresholds,
        "mastered_weeks": sorted(database.itqan_mastered_weeks(discord_id, level)),
    }, headers=_cors_headers(request))


@routes.get("/api/assessment/certificate")
async def get_assessment_certificate(request: web.Request) -> web.Response:
    """Level-completion certificate data for the dojo certificate page.
    `eligible` is True only when every week of the level is mastered."""
    payload, err = _itqan_gate(request)
    if err:
        return err
    discord_id, level = payload["did"], payload.get("lvl", "A1")
    database.touch_device_session(payload["sid"])
    data = database.itqan_certificate_data(discord_id, level)
    return web.json_response({"ok": True, **data}, headers=_cors_headers(request))


# ============================================================
#  Mi'yar Phase 8 — CEFR placement (adaptive, per-skill profile)
# ============================================================

@routes.get("/api/cefr/progress")
async def get_cefr_progress(request: web.Request) -> web.Response:
    """Phase 9: the student's per-level CEFR can-do checklist + progress.
    Each descriptor the level teaches, marked reached (a mastered week evidences
    it) or not — powers the /can-do/ page."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    did, level = payload["did"], payload.get("lvl", "A1")
    database.touch_device_session(payload["sid"])
    cdp = assessment.can_do_progress(did, level)
    descs = assessment.can_do_descriptors(cdp["level"])
    evidenced, taught = set(cdp["evidenced"]), set(cdp["taught"])
    # Phase 11C: attach the EVIDENCE behind each descriptor — which exercise on
    # which content day proves it — so the checklist shows work, not just a
    # tick. Best-effort: the checklist must still render without it.
    portfolio = {}
    try:
        pf = assessment.descriptor_portfolio(did, cdp["level"])
        portfolio = {p["code"]: p for p in pf["descriptors"]}
    except Exception as e:
        logger.warning(f"cefr/progress: portfolio unavailable: {e}")

    out = []
    for mode in ("reception", "production", "interaction", "mediation"):
        for d in descs.get(mode, []):
            if d.get("code") in taught:
                p = portfolio.get(d["code"]) or {}
                out.append({"code": d["code"], "en": d.get("en"), "ar": d.get("ar"),
                            "mode": mode, "reached": d["code"] in evidenced,
                            "evidence": p.get("evidence", []),
                            "evidence_count": p.get("evidence_count", 0),
                            "proves_with": p.get("possible_exercises", [])})
    evidenced_count = sum(1 for d in out if d["evidence_count"])
    return web.json_response({
        "ok": True, "level": cdp["level"],
        "level_name": config.level_info(cdp["level"]).get("name", cdp["level"]),
        "reached": cdp["reached"], "total": cdp["total"], "pct": cdp["pct"],
        "evidenced": evidenced_count,
        "evidence_pct": round(100 * evidenced_count / len(out)) if out else 0,
        "descriptors": out,
    }, headers=_cors_headers(request))


@routes.get("/api/cefr/contract")
async def get_cefr_contract(request: web.Request) -> web.Response:
    """Phase 11C: the student's LEVEL COMPLETION CONTRACT — the three criteria
    that make "finished this level" a provable statement (all work done, every
    can-do statement evidenced, exit exam passed), each with its own progress
    detail. Reporting only: it never controls access to a certificate."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    did, level = payload["did"], payload.get("lvl", "A1")
    database.touch_device_session(payload["sid"])
    contract = assessment.level_completion_contract(did, level)
    return web.json_response({"ok": True, **contract},
                             headers=_cors_headers(request))


@routes.post("/api/placement/start")
async def post_placement_start(request: web.Request) -> web.Response:
    """Begin a placement session; returns the first objective block."""
    from . import placement_runner
    payload, err = _itqan_gate(request)
    if err:
        return err
    database.touch_device_session(payload["sid"])
    out = placement_runner.start_session(payload["did"])
    return web.json_response(out, headers=_cors_headers(request))


@routes.post("/api/placement/answer")
async def post_placement_answer(request: web.Request) -> web.Response:
    """Submit the current block's answers; returns the next block or the writing task."""
    from . import placement_runner
    payload, err = _itqan_gate(request)
    if err:
        return err
    database.touch_device_session(payload["sid"])
    try:
        body = await request.json()
    except Exception:
        body = {}
    out = await placement_runner.submit_answers(payload["did"], body.get("answers") or {})
    return web.json_response(out, status=200 if out.get("ok") else 400,
                             headers=_cors_headers(request))


@routes.post("/api/placement/writing")
async def post_placement_writing(request: web.Request) -> web.Response:
    """Submit the typed writing sample; finalises + returns the per-skill profile."""
    from . import placement_runner
    payload, err = _itqan_gate(request)
    if err:
        return err
    database.touch_device_session(payload["sid"])
    try:
        body = await request.json()
    except Exception:
        body = {}
    out = await placement_runner.submit_writing(payload["did"], body.get("text", ""))
    return web.json_response(out, status=200 if out.get("ok") else 400,
                             headers=_cors_headers(request))


@routes.post("/api/placement/speaking")
async def post_placement_speaking(request: web.Request) -> web.Response:
    """Submit the spoken response (multipart `audio`, transcribed via Whisper;
    or JSON {transcript} fallback). Finalises the placement profile."""
    from . import placement_runner, pronunciation_scorer
    payload, err = _itqan_gate(request)
    if err:
        return err
    database.touch_device_session(payload["sid"])
    transcript = ""
    ctype = request.headers.get("Content-Type", "")
    if ctype.startswith("multipart/"):
        try:
            reader = await request.multipart()
            while True:
                part = await reader.next()
                if part is None:
                    break
                if part.name == "audio":
                    audio_bytes = await part.read()
                    ct = part.headers.get("Content-Type", "audio/webm")
                    fn = ("recording.m4a" if ("mp4" in ct or "m4a" in ct)
                          else "recording.ogg" if "ogg" in ct else "recording.webm")
                    try:
                        transcript = await pronunciation_scorer.transcribe_audio(
                            audio_bytes, fn) or ""
                    except Exception:
                        transcript = ""
                elif part.name == "transcript":
                    transcript = (await part.text()).strip()
        except Exception:
            return web.json_response({"ok": False, "error": "multipart required"},
                                     status=400, headers=_cors_headers(request))
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        transcript = (body.get("transcript") or "").strip()
    out = await placement_runner.submit_speaking(payload["did"], transcript)
    return web.json_response(out, status=200 if out.get("ok") else 400,
                             headers=_cors_headers(request))


@routes.post("/api/placement/slot")
async def post_placement_slot(request: web.Request) -> web.Response:
    """Opt-in: place the student at their result level (week 1)."""
    from . import placement_runner
    payload, err = _itqan_gate(request)
    if err:
        return err
    database.touch_device_session(payload["sid"])
    out = placement_runner.slot_student(payload["did"])
    return web.json_response(out, status=200 if out.get("ok") else 400,
                             headers=_cors_headers(request))


@routes.post("/api/assessment/start")
async def post_assessment_start(request: web.Request) -> web.Response:
    """Begin a new attempt for a week (if unlocked, no active attempt, and
    off cooldown). Returns the drawn items with answers stripped."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    discord_id, level = payload["did"], payload.get("lvl", "A1")
    try:
        body = await request.json()
    except Exception:
        body = {}
    week = _itqan_week_arg(body.get("week"), level)
    if week is None:
        return web.json_response({"ok": False, "error": "bad week"},
                                 status=400, headers=_cors_headers(request))
    database.touch_device_session(payload["sid"])
    result = assessment.start_attempt(discord_id, level, week)
    status = 200 if result.get("ok") else 409
    return web.json_response(result, status=status, headers=_cors_headers(request))


async def _read_item_submission(request: web.Request):
    """Parse an assessment item submission that may arrive as EITHER
    JSON ({attempt_id, item_no, answer} for text items) OR
    multipart/form-data (an `audio` part + `attempt_id`/`item_no` fields
    for pronunciation/speaking items). Returns (data, None) on success or
    (None, error_response), following the _itqan_gate idiom.

    Every assessment family (weekly, monthly, advancement) MUST parse
    submissions through this one helper: a speaking/pronunciation answer is
    always multipart, so an endpoint that only reads JSON silently rejects
    every recording. That was the 2026-08 bug where the monthly and
    advancement endpoints called request.json() only — audio items returned
    "bad_json" and the student saw "Couldn't save that answer" no matter how
    many times they retried."""
    attempt_id = item_no = None
    answer = ""
    audio_bytes = None
    audio_filename = "recording.webm"
    ctype = request.headers.get("Content-Type", "")

    if ctype.startswith("multipart/"):
        try:
            reader = await request.multipart()
        except Exception:
            return None, web.json_response({"ok": False, "error": "multipart required"},
                                           status=400, headers=_cors_headers(request))
        while True:
            part = await reader.next()
            if part is None:
                break
            if part.name == "audio":
                audio_bytes = await part.read()
                ct = part.headers.get("Content-Type", "audio/webm")
                if "mp4" in ct or "m4a" in ct:
                    audio_filename = "recording.m4a"
                elif "ogg" in ct:
                    audio_filename = "recording.ogg"
                else:
                    audio_filename = "recording.webm"
            elif part.name == "answer":
                answer = (await part.text()).strip()
            elif part.name == "attempt_id":
                try:
                    attempt_id = int(await part.text())
                except (ValueError, TypeError):
                    pass
            elif part.name == "item_no":
                try:
                    item_no = int(await part.text())
                except (ValueError, TypeError):
                    pass
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        answer = (body.get("answer") or "").strip()
        try:
            attempt_id = int(body.get("attempt_id"))
            item_no = int(body.get("item_no"))
        except (TypeError, ValueError):
            attempt_id = item_no = None

    if attempt_id is None or item_no is None:
        return None, web.json_response({"ok": False, "error": "attempt_id and item_no required"},
                                       status=400, headers=_cors_headers(request))
    return {"attempt_id": attempt_id, "item_no": item_no, "answer": answer,
            "audio_bytes": audio_bytes, "audio_filename": audio_filename}, None


@routes.post("/api/assessment/item")
async def post_assessment_item(request: web.Request) -> web.Response:
    """Submit one item's answer. Text items send JSON
    {attempt_id, item_no, answer}; recording items send multipart/form-data
    with an `audio` part plus `attempt_id` and `item_no` fields. Scoring is
    stored server-side; the correctness is intentionally NOT returned during
    the test.

    ⚠️ The route decorator belongs HERE, on the handler. It was accidentally
    left on `_read_item_submission` when that helper was extracted (commit
    ebb266d), which un-registered this handler entirely: aiohttp then called
    the helper as the handler, the helper returned a `(data, error)` TUPLE
    instead of a Response, and every weekly item submission answered
    HTTP 500 -- before even reaching the session gate. Verified live on
    2026-08-30: `/api/assessment/item` returned 500 while the correctly
    decorated `/api/assessment/monthly/item` returned 401. See
    test_assessment_routes_wiring.py, which now fails if any declared route
    resolves to a handler that cannot return a Response."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    discord_id = payload["did"]
    data, err = await _read_item_submission(request)
    if err:
        return err
    database.touch_device_session(payload["sid"])
    result = await assessment.submit_item(discord_id, data["attempt_id"], data["item_no"],
                                          answer=data["answer"],
                                          audio_bytes=data["audio_bytes"],
                                          audio_filename=data["audio_filename"])
    status = 200 if result.get("ok") else 400
    return web.json_response(result, status=status, headers=_cors_headers(request))


@routes.post("/api/assessment/finish")
async def post_assessment_finish(request: web.Request) -> web.Response:
    """Finalize an attempt: aggregate → verdict → persist (and record
    Week Mastered on a pass). Returns the full results payload."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    discord_id = payload["did"]
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        attempt_id = int(body.get("attempt_id"))
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "attempt_id required"},
                                 status=400, headers=_cors_headers(request))
    integrity_flags = body.get("integrity_flags")
    if integrity_flags is not None and not isinstance(integrity_flags, dict):
        integrity_flags = None
    database.touch_device_session(payload["sid"])
    result = assessment.finish_attempt(discord_id, attempt_id, integrity_flags=integrity_flags)

    # Fire the outcome (Phase 6): 🏅 Champions post on a pass, private support
    # DM + SRS re-inject on a not-yet, owner alert on a flagged attempt. This
    # is best-effort — scoring is already persisted, so a failed Discord post
    # must never turn a successful finish into an error.
    if result.get("ok"):
        try:
            from . import itqan_outcomes
            att = database.itqan_get_attempt(attempt_id)
            if att:
                await itqan_outcomes.deliver_outcome(
                    discord_id, att["level"], att["week"], attempt_id, result["verdict"])
        except Exception as e:
            logger.warning(f"itqan: outcome delivery error: {e}")

    status = 200 if result.get("ok") else 400
    return web.json_response(result, status=status, headers=_cors_headers(request))


# ============================================================
#  MONTHLY REVIEW API (Taqdeem Phase 2)
# ============================================================

@routes.get("/api/assessment/monthly/status")
async def get_monthly_status(request: web.Request) -> web.Response:
    """Monthly Review state: not_due | available | in_progress | cooldown | passed."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    discord_id, level = payload["did"], payload.get("lvl", "A1")
    database.touch_device_session(payload["sid"])
    state = assessment.get_monthly_state(discord_id, level)
    return web.json_response({"ok": True, **state}, headers=_cors_headers(request))


@routes.post("/api/assessment/monthly/start")
async def post_monthly_start(request: web.Request) -> web.Response:
    """Begin a new Monthly Review attempt (if due and not on cooldown)."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    discord_id, level = payload["did"], payload.get("lvl", "A1")
    database.touch_device_session(payload["sid"])
    result = assessment.start_monthly_attempt(discord_id, level)
    status = 200 if result.get("ok") else 409
    return web.json_response(result, status=status, headers=_cors_headers(request))


@routes.post("/api/assessment/monthly/item")
async def post_monthly_item(request: web.Request) -> web.Response:
    """Submit an answer for a monthly review item. Reuses the same item
    scoring as weekly (Whisper for audio, AI for text, objective for vocab)
    and the same submission parser, so speaking/pronunciation recordings
    (multipart audio) are accepted here exactly as they are on the weekly
    endpoint."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    discord_id = payload["did"]
    data, err = await _read_item_submission(request)
    if err:
        return err
    database.touch_device_session(payload["sid"])
    # Reuse the same submit_item (it works on any attempt_id regardless of type)
    result = await assessment.submit_item(discord_id, data["attempt_id"], data["item_no"],
                                          answer=data["answer"],
                                          audio_bytes=data["audio_bytes"],
                                          audio_filename=data["audio_filename"])
    status = 200 if result.get("ok") else 400
    return web.json_response(result, status=status, headers=_cors_headers(request))


@routes.post("/api/assessment/monthly/finish")
async def post_monthly_finish(request: web.Request) -> web.Response:
    """Finalize a monthly review attempt and get the verdict."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    discord_id = payload["did"]
    database.touch_device_session(payload["sid"])
    try:
        body = await request.json()
    except Exception:
        body = {}
    attempt_id = body.get("attempt_id")
    if not attempt_id:
        return web.json_response({"ok": False, "error": "missing attempt_id"},
                                 status=400, headers=_cors_headers(request))
    integrity_flags = body.get("integrity_flags", {})
    result = assessment.finish_monthly_attempt(discord_id, int(attempt_id),
                                               integrity_flags=integrity_flags)

    # Fire outcome delivery (Phase 3): DM the student + alert owner if needed.
    # Best-effort — scoring already persisted.
    if result.get("ok") and not result.get("voided"):
        try:
            from . import monthly_outcomes
            att = database.itqan_get_attempt(int(attempt_id))
            review_number = att["week"] if att else 1
            level = payload.get("lvl", "A1")
            await monthly_outcomes.deliver_monthly_outcome(
                discord_id, level, review_number, result)
        except Exception as e:
            logger.warning(f"monthly: outcome delivery error: {e}")

    status = 200 if result.get("ok") else 400
    return web.json_response(result, status=status, headers=_cors_headers(request))


# ============================================================
#  ADVANCEMENT EXAM API (Taqdeem Phase 4)
# ============================================================

@routes.get("/api/assessment/advancement/status")
async def get_advancement_status(request: web.Request) -> web.Response:
    """Advancement Exam state: disabled | locked | available | cooldown | passed."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    discord_id, level = payload["did"], payload.get("lvl", "A1")
    database.touch_device_session(payload["sid"])
    state = assessment.get_advancement_state(discord_id, level)
    return web.json_response({"ok": True, **state}, headers=_cors_headers(request))


@routes.post("/api/assessment/advancement/start")
async def post_advancement_start(request: web.Request) -> web.Response:
    """Begin a new Advancement Exam attempt (Part A)."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    discord_id, level = payload["did"], payload.get("lvl", "A1")
    database.touch_device_session(payload["sid"])
    result = assessment.start_advancement_attempt(discord_id, level)
    status = 200 if result.get("ok") else 409
    return web.json_response(result, status=status, headers=_cors_headers(request))


@routes.post("/api/assessment/advancement/item")
async def post_advancement_item(request: web.Request) -> web.Response:
    """Submit an answer for an advancement exam item (Part A). Uses the same
    submission parser as the weekly/monthly endpoints, so speaking and
    pronunciation recordings (multipart audio) are accepted here too."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    discord_id = payload["did"]
    data, err = await _read_item_submission(request)
    if err:
        return err
    database.touch_device_session(payload["sid"])
    result = await assessment.submit_item(discord_id, data["attempt_id"], data["item_no"],
                                          answer=data["answer"],
                                          audio_bytes=data["audio_bytes"],
                                          audio_filename=data["audio_filename"])
    status = 200 if result.get("ok") else 400
    return web.json_response(result, status=status, headers=_cors_headers(request))


@routes.post("/api/assessment/advancement/finish-a")
async def post_advancement_finish_a(request: web.Request) -> web.Response:
    """Finalize Part A of the advancement exam. Returns Part A scores;
    does NOT determine final pass/fail (that's after Part B)."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    discord_id = payload["did"]
    database.touch_device_session(payload["sid"])
    try:
        body = await request.json()
    except Exception:
        body = {}
    attempt_id = body.get("attempt_id")
    if not attempt_id:
        return web.json_response({"ok": False, "error": "missing attempt_id"},
                                 status=400, headers=_cors_headers(request))
    integrity_flags = body.get("integrity_flags", {})
    result = assessment.finish_advancement_part_a(discord_id, int(attempt_id),
                                                  integrity_flags=integrity_flags)
    status = 200 if result.get("ok") else 400
    return web.json_response(result, status=status, headers=_cors_headers(request))


@routes.get("/api/assessment/advancement/part-b")
async def get_advancement_part_b(request: web.Request) -> web.Response:
    """Get the Part B prompt for the student's level."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    level = payload.get("lvl", "A1")
    database.touch_device_session(payload["sid"])
    prompt = assessment.get_part_b_prompt(level)
    return web.json_response({"ok": True, **prompt}, headers=_cors_headers(request))


@routes.post("/api/assessment/advancement/finish-b")
async def post_advancement_finish_b(request: web.Request) -> web.Response:
    """Submit Part B recording transcript and get the FINAL advancement verdict.
    The client transcribes via Whisper (or sends raw audio — but for now we
    expect a transcript string from the existing recording infrastructure)."""
    from . import assessment
    payload, err = _itqan_gate(request)
    if err:
        return err
    discord_id = payload["did"]
    database.touch_device_session(payload["sid"])
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"},
                                 status=400, headers=_cors_headers(request))
    attempt_id = body.get("attempt_id")
    transcript = body.get("transcript", "")
    if not attempt_id:
        return web.json_response({"ok": False, "error": "missing attempt_id"},
                                 status=400, headers=_cors_headers(request))
    if not transcript.strip():
        return web.json_response({"ok": False, "error": "empty transcript"},
                                 status=400, headers=_cors_headers(request))
    # Mi'yar Phase 8: the advancement exam IS the CEFR exit exam. Verdict comes
    # from criterion cut scores + AI descriptor-rater + boundary human review.
    result = await assessment.finish_advancement_exit(discord_id, int(attempt_id), transcript)

    # Fire outcome delivery: pass -> promote + certificate, fail -> retake DM,
    # review -> "under review" DM + owner alert (!exam-review). Best-effort.
    if result.get("ok"):
        try:
            from . import advancement_outcomes
            level = result.get("level") or payload.get("lvl", "A1")
            await advancement_outcomes.deliver_exit_exam_outcome(
                discord_id, level, {
                    "decision": result["decision"],
                    "distinction": result.get("distinction", False),
                    "part_a_pct": result["part_a_pct"],
                    "part_b_total": result["part_b_total"],
                    "confidence": result["confidence"],
                    "reasons": result.get("reasons", []),
                })
        except Exception as e:
            logger.warning(f"exit-exam: outcome delivery error: {e}")

    status = 200 if result.get("ok") else 400
    return web.json_response(result, status=status, headers=_cors_headers(request))


# ============================================================
#  CORS preflight handler
# ============================================================

@routes.options("/api/{tail:.*}")
async def cors_preflight(request: web.Request) -> web.Response:
    """Handle CORS preflight requests."""
    return web.Response(headers=_cors_headers(request))


# ============================================================
#  APP SETUP
# ============================================================

def create_app() -> web.Application:
    """Create the aiohttp web application."""
    app = web.Application(client_max_size=10 * 1024 * 1024)  # 10MB for audio uploads
    app.add_routes(routes)
    return app


async def start_api_server(port: int = 8099):
    """Start the API server (call from bot's on_ready or setup_hook)."""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"API server running on port {port}")
    return runner
