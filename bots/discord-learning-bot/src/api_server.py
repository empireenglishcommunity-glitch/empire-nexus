"""Empire English Bot — Minimal HTTP API (Sahel S6).

Runs alongside the Discord bot on port 8099 (internal only).
Provides progress data for the practice platform via link tokens.

Endpoints:
  GET /api/progress?token=<token>  — returns JSON progress data
  POST /api/srs-review             — record SRS review result
"""
import json
import logging

from aiohttp import web

from . import database

logger = logging.getLogger("empire-bot.api")

routes = web.RouteTableDef()


@routes.get("/api/progress")
async def get_progress(request: web.Request) -> web.Response:
    """Return progress JSON for a given link token."""
    token = request.query.get("token", "")
    if not token:
        return web.json_response({"error": "token required"}, status=400)

    progress = database.get_progress_for_token(token)
    if not progress:
        return web.json_response({"error": "invalid token"}, status=404)

    return web.json_response(progress, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    })


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
    return web.json_response({"ok": True}, headers={
        "Access-Control-Allow-Origin": "*",
    })


@routes.options("/api/{tail:.*}")
async def cors_preflight(request: web.Request) -> web.Response:
    """Handle CORS preflight requests."""
    return web.Response(headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    })


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
