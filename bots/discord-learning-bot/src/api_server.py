"""Empire English Bot — HTTP API (Sahel S6 + Wuslah W0).

Runs alongside the Discord bot on port 8099 (internal only).
Provides progress data for the practice platform via link tokens.

Endpoints:
  GET  /api/progress?token=<token>     — returns JSON progress data (legacy)
  GET  /api/dashboard?token=<token>    — full aggregated dashboard (Wuslah W0)
  GET  /api/leaderboard?token=<token>  — top 10 + requester rank (Wuslah W0)
  POST /api/srs-review                 — record SRS review result
"""
import json
import logging
import time
from collections import defaultdict

from aiohttp import web

from . import database

logger = logging.getLogger("empire-bot.api")

routes = web.RouteTableDef()

# ============================================================
#  RATE LIMITING (Wuslah W0.3 — 60 req/min per token)
# ============================================================

_rate_limits: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 60  # requests per window


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


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


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


# ============================================================
#  EXISTING ENDPOINTS (Sahel S6)
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

    today = datetime.date.today().isoformat()

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

    # --- Milestones ---
    conn = database._connect()
    milestones_raw = conn.execute(
        "SELECT milestone_id, completed_at, level FROM ability_milestones WHERE discord_id=? ORDER BY completed_at DESC",
        (discord_id,),
    ).fetchall()
    milestones = [{"id": r["milestone_id"], "completed_at": r["completed_at"], "level": r["level"]} for r in milestones_raw]

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
    for day_offset in range(7):
        d = (datetime.date.today() - datetime.timedelta(days=day_offset)).isoformat()
        day_subs = conn.execute(
            "SELECT task_id FROM daily_submissions WHERE discord_id=? AND date=?",
            (discord_id, d),
        ).fetchall()
        day_tasks = [r["task_id"] for r in day_subs]
        day_name = (datetime.date.today() - datetime.timedelta(days=day_offset)).strftime("%a")
        week_activity[day_name] = {t: (t in day_tasks) for t in task_types}

    # --- Voice portfolio (last 5) ---
    voice_raw = conn.execute(
        "SELECT recorded_at, recording_type, ai_score, recording_url FROM voice_portfolio WHERE discord_id=? ORDER BY recorded_at DESC LIMIT 5",
        (discord_id,),
    ).fetchall()
    voice_portfolio = [{"date": r["recorded_at"], "type": r["recording_type"], "score": r["ai_score"], "url": r["recording_url"]} for r in voice_raw]

    # --- Leaderboard rank ---
    rank_row = conn.execute(
        """SELECT COUNT(*) + 1 as rank FROM members
           WHERE status='active' AND total_points > ?""",
        (member["total_points"],),
    ).fetchone()
    leaderboard_rank = rank_row["rank"] if rank_row else 0

    # --- Nour study tips (cached) ---
    tips_raw = conn.execute(
        "SELECT tip_text FROM nour_study_tips WHERE discord_id=? ORDER BY generated_at DESC LIMIT 3",
        (discord_id,),
    ).fetchall()
    nour_tips = [r["tip_text"] for r in tips_raw]

    conn.close()

    # --- Difficulty level (Dhaka' adaptive engine) ---
    difficulty_level = member.get("difficulty_level", 2)

    # --- Level progress ---
    # Simple XP-based progress: total_points relative to thresholds
    level_thresholds = {"L0": 0, "L1": 2000, "L2": 5000, "L3": 10000}
    current_level = member.get("level", "L0")
    levels_ordered = ["L0", "L1", "L2", "L3"]
    current_idx = levels_ordered.index(current_level) if current_level in levels_ordered else 0
    if current_idx < len(levels_ordered) - 1:
        next_level = levels_ordered[current_idx + 1]
        current_threshold = level_thresholds.get(current_level, 0)
        next_threshold = level_thresholds.get(next_level, 10000)
        xp_in_level = member["total_points"] - current_threshold
        xp_needed = next_threshold - current_threshold
        level_pct = min(100, round(xp_in_level / max(xp_needed, 1) * 100, 1))
    else:
        xp_in_level = member["total_points"]
        xp_needed = 0
        level_pct = 100

    # --- Days since active ---
    last_active = member.get("last_active_at", "")
    try:
        last_dt = datetime.datetime.fromisoformat(last_active.replace("Z", ""))
        days_since_active = (datetime.datetime.now() - last_dt).days
    except (ValueError, TypeError, AttributeError):
        days_since_active = 0

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
        "milestones": milestones,
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
        "voice_portfolio": voice_portfolio,
        "nour_tips": nour_tips,
    }

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
#  CORS preflight handler
# ============================================================

@routes.options("/api/{tail:.*}")
async def cors_preflight(request: web.Request) -> web.Response:
    """Handle CORS preflight requests."""
    return web.Response(headers=_cors_headers())


# ============================================================
#  APP SETUP
# ============================================================

def create_app() -> web.Application:
    """Create the aiohttp web application."""
    app = web.Application()
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
