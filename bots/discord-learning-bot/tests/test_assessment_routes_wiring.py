"""Every declared API route must resolve to a handler that returns a Response.

WHY THIS FILE EXISTS
--------------------
`/api/assessment/item` — the endpoint every WEEKLY assessment answer goes
through — returned **HTTP 500 to every request in production**, verified live on
2026-08-30. Not for a subtle reason: the `@routes.post("/api/assessment/item")`
decorator had been left attached to the `_read_item_submission` *helper* when
that helper was extracted from the handler (commit ebb266d). aiohttp therefore
called the helper as the handler, the helper returned a `(data, error)` **tuple**
instead of a `web.Response`, and aiohttp raised before the session gate ever ran.

The real handler, `post_assessment_item`, was left registered nowhere at all.

Nothing caught it. The existing tests called `_read_item_submission` directly as
a function, which works fine — the bug only existed in the *wiring*. So this
file tests the wiring itself, generically, for every route: no matter what any
future refactor moves around, a helper accidentally left holding a route
decorator will fail here instead of in front of a student mid-exam.
"""
import inspect

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src import api_server


def _declared_routes():
    """(method, path, handler) for every route on the RouteTableDef."""
    out = []
    for r in api_server.routes:
        method = getattr(r, "method", None)
        path = getattr(r, "path", None)
        handler = getattr(r, "handler", None)
        if method and path and handler:
            out.append((method, path, handler))
    return out


def test_there_are_routes_to_check():
    """A generic sweep that silently matched nothing would pass forever."""
    assert len(_declared_routes()) > 20


@pytest.mark.parametrize("method,path,handler", _declared_routes(),
                         ids=lambda v: v if isinstance(v, str) else "")
def test_every_route_handler_is_annotated_to_return_a_response(method, path, handler):
    """A route handler must be declared as returning a web.Response.

    This is the cheap, static half of the check. `_read_item_submission` is
    annotated with no return type and genuinely returns a tuple, so it would
    have been caught here the moment it acquired a route decorator.
    """
    assert inspect.iscoroutinefunction(handler), \
        f"{method} {path} -> {handler.__name__} is not a coroutine"
    ret = inspect.signature(handler).return_annotation
    assert ret is not inspect.Signature.empty, (
        f"{method} {path} -> {handler.__name__} has no return annotation. "
        f"Route handlers must be annotated `-> web.Response`; helpers must not "
        f"carry a route decorator."
    )


def test_no_private_helper_is_registered_as_a_route():
    """Handlers are public; `_`-prefixed functions are helpers.

    `_read_item_submission` held the /api/assessment/item route for weeks. The
    naming convention already told us it was a helper — nothing enforced it.
    """
    offenders = [(m, p, h.__name__) for m, p, h in _declared_routes()
                 if h.__name__.startswith("_")]
    assert offenders == [], f"private helpers registered as routes: {offenders}"


def test_assessment_item_route_points_at_the_real_handler():
    """The specific regression, named."""
    matches = [h.__name__ for m, p, h in _declared_routes()
               if p == "/api/assessment/item" and m == "POST"]
    assert matches == ["post_assessment_item"], (
        f"/api/assessment/item is served by {matches}; it must be "
        f"post_assessment_item, not the _read_item_submission helper"
    )


def test_read_item_submission_is_not_a_route_handler():
    assert "_read_item_submission" not in [h.__name__ for _, _, h in _declared_routes()]


# ---- the dynamic half: actually call them ---------------------------------

# Unauthenticated requests to these must be REJECTED cleanly (401/400/403),
# never a 500. A 500 here means the handler could not even produce a Response.
_ITEM_ROUTES = [
    "/api/assessment/item",
    "/api/assessment/monthly/item",
    "/api/assessment/advancement/item",
    "/api/assessment/finish",
    "/api/assessment/monthly/finish",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", _ITEM_ROUTES)
async def test_unauthenticated_post_never_500s(path):
    """The exact probe that exposed this live: POST with no session.

    A correctly wired handler runs `_itqan_gate` and answers 401. The broken
    wiring answered 500 — before any auth — for every request, which is how a
    completely dead endpoint hid in plain sight.
    """
    app = web.Application()
    app.add_routes(api_server.routes)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post(path, json={"attempt_id": 1, "item_no": 1,
                                             "answer": "x"})
        assert resp.status != 500, (
            f"POST {path} returned 500 without a session — the handler could "
            f"not return a Response at all"
        )
        assert resp.status in (400, 401, 403), \
            f"POST {path} returned an unexpected {resp.status}"


@pytest.mark.asyncio
async def test_every_declared_post_route_survives_an_unauthenticated_call():
    """Whole-surface sweep: no POST route may 500 on an empty body."""
    app = web.Application()
    app.add_routes(api_server.routes)
    failures = []
    async with TestClient(TestServer(app)) as client:
        for method, path, handler in _declared_routes():
            if method != "POST" or "{" in path:
                continue
            try:
                resp = await client.post(path, json={})
            except Exception as e:  # a handler that raises is also a failure
                failures.append((path, handler.__name__, f"raised {e!r}"))
                continue
            if resp.status == 500:
                failures.append((path, handler.__name__, "HTTP 500"))
    assert failures == [], f"routes that cannot return a Response: {failures}"
