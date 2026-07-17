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
import json
import logging
import time
from collections import defaultdict
from pathlib import Path

from aiohttp import web

from . import database

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
            "Access-Control-Allow-Headers": "Content-Type",
        }
    # Unknown origin: return CORS headers with the primary domain
    # (browsers will block if it doesn't match their Origin, which is
    # the desired behavior — blocks unauthorized frontends)
    return {
        "Access-Control-Allow-Origin": "https://practice.empireenglish.online",
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
    # Hisn D036 fix: also send the real milestone catalog (id/name/name_ar/level
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
        "milestones": milestones,
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
        "voice_portfolio": voice_portfolio,
        "nour_tips": nour_tips,
    }
    if momentum is not None:
        dashboard["momentum"] = momentum

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
    today = datetime.date.today().isoformat()

    # log_submission handles UNIQUE constraint (returns False if already exists)
    added = database.log_submission(discord_id, today, exercise_type)

    if added:
        # Award points (same as !done: POINTS_PER_TASK)
        from . import config
        database.add_points(discord_id, config.POINTS_PER_TASK, f"web_{exercise_type}")
        # Touch last_active
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
    today = datetime.date.today().isoformat()

    # Basic progress (same as legacy)
    streak = member.get("current_streak", 0)
    level = member.get("level", "L0")
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
#  WUSLAH W4: /api/nour-tips — pre-generated study tips
#  (LEGACY — superseded by /api/growth-letter above per Masar M2.
#  Never actually populated with real AI-generated content in
#  production, per Hisn D020 -- left in place, inert, rather than
#  removed, since some in-flight dashboard sessions might still be
#  caching the old JS that calls it until they reload. M2.5 removes
#  the dashboard's call site; this endpoint itself can be deleted in
#  a later cleanup pass once confirmed nothing calls it anymore.)
# ============================================================

@routes.get("/api/nour-tips")
async def get_nour_tips(request: web.Request) -> web.Response:
    """Return AI-generated study tips for the student.

    Tips are pre-generated weekly (by ops_monitoring's tip generation
    task) and cached in the nour_study_tips table. This endpoint just
    reads the cached result — zero AI cost per page load.

    Falls back to generic level-appropriate tips if none are cached.
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
    discord_id = member["discord_id"]
    level = member.get("level", "L0")

    # Try cached tips first
    conn = database._connect()
    tips_raw = conn.execute(
        "SELECT tip_text, generated_at FROM nour_study_tips WHERE discord_id=? ORDER BY generated_at DESC LIMIT 3",
        (discord_id,),
    ).fetchall()
    conn.close()

    if tips_raw:
        return web.json_response({
            "tips": [r["tip_text"] for r in tips_raw],
            "generated_at": tips_raw[0]["generated_at"],
            "source": "personalized",
        }, headers=_cors_headers())

    # Fallback: generic level-appropriate tips
    generic_tips = _generic_tips_for_level(level)
    return web.json_response({
        "tips": generic_tips,
        "generated_at": None,
        "source": "generic",
    }, headers=_cors_headers())


def _generic_tips_for_level(level: str) -> list[str]:
    """Static fallback tips when AI-generated ones aren't available."""
    tips = {
        "L0": [
            "Focus on daily accent drills — 5 minutes of practice builds muscle memory",
            "Use the SRS flashcards before bed — sleep consolidates vocabulary",
            "Record yourself and compare with the model — you'll hear the difference",
        ],
        "L1": [
            "Shadow full sentences now, not just words — build natural rhythm",
            "Try the dictation exercises — writing what you hear strengthens listening",
            "Review your pronunciation scores — focus on any phoneme below 70%",
        ],
        "L2": [
            "Practice speaking in complete paragraphs — fluency over perfection",
            "Challenge yourself with the writing exercises — express original thoughts",
            "Listen to the model audio at full speed — train your ear for natural pace",
        ],
        "L3": [
            "Focus on nuance — intonation, emphasis, and emotional expression",
            "Try explaining complex ideas in English without translating from Arabic",
            "Record a 2-minute monologue weekly — track your confidence growth",
        ],
    }
    return tips.get(level, tips["L0"])


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
        "level": member.get("level", "L0"),
    }, headers=_cors_headers(request))


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
