"""Assessment watchdog — catch a broken assessment before a student does.

WHY THIS EXISTS
---------------
Three assessment defects in a row were found from a STUDENT COMPLAINT, never
from monitoring:

  * `/api/assessment/item` answered HTTP 500 to every request for ~24 hours.
    Nobody could submit a weekly answer, at any level. No alert fired.
  * `finish_monthly_attempt` read a column that does not exist, so a completed
    monthly review could never record a result. `monthly_reviews` sat at zero
    rows while the feature was enabled and students were taking it.
  * Two students were silently locked out of a weekly test by a stale
    `in_progress` row, and neither said anything.

Every one of those is trivially detectable from outside. This module checks the
things a student would notice, and alerts the owner over Empire Ops (Telegram)
BEFORE they have to.

DESIGN RULES
------------
* Read-only. It never fixes, deletes or writes anything. Diagnosis and repair
  stay separate so a false positive can't cause damage.
* Alerts on the TRANSITION into a bad state, and again only when the finding set
  changes -- not once per run. A slow response must not become a spam loop.
* Recovery is reported too, so "no news" is never ambiguous.
* Every check is individually wrapped: a watchdog must never be the thing that
  takes the bot down.
"""
import datetime
import logging

from . import config, database

logger = logging.getLogger(__name__)

FLAG = "assessment_watchdog"

# A student abandoning a test is normal. A test still 'in_progress' a day later
# is not -- it means they could not finish, and on the weekly flow it actively
# BLOCKS them from retaking (the `attempt_in_progress` guard).
STRANDED_HOURS = 18

# Endpoints a student's assessment depends on. An unauthenticated POST must be
# REJECTED cleanly (401/400/403). A 500 means the handler cannot even build a
# response -- which is exactly how the dead /api/assessment/item hid.
PROBE_ENDPOINTS = (
    "/api/assessment/item",
    "/api/assessment/monthly/item",
    "/api/assessment/monthly/finish",
    "/api/assessment/finish",
    "/api/assessment/advancement/item",
)
_ACCEPTABLE = (400, 401, 403, 404, 409, 429)


# ============================================================
#  CHECKS
# ============================================================

def check_stranded_attempts() -> list:
    """Attempts stuck 'in_progress' long enough that the student is stuck too."""
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(hours=STRANDED_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    conn = database._connect()
    try:
        rows = conn.execute(
            "SELECT a.id, a.type, a.level, a.week, a.started_at, "
            "       COALESCE(m.discord_name, a.discord_id) AS who "
            "FROM assessment_attempts a "
            "LEFT JOIN members m ON m.discord_id = a.discord_id "
            "WHERE a.status='in_progress' AND a.started_at < ? "
            "ORDER BY a.started_at", (cutoff,)).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        kind = "weekly" if r["type"] == "weekly" else r["type"]
        blocked = " — BLOCKS retake" if r["type"] == "weekly" else ""
        out.append(f"{r['who']}: {kind} wk/rev {r['week']} open since "
                   f"{r['started_at']}{blocked}")
    return out


def check_monthly_results_recorded() -> list:
    """A finished monthly attempt with no row in `monthly_reviews`.

    This is the exact signature of the bug that hid for weeks: the attempt is
    scored, so from the inside everything looks fine, but the student's result
    was never persisted where the state machine reads it.
    """
    conn = database._connect()
    try:
        rows = conn.execute(
            "SELECT a.id, a.level, a.week, "
            "       COALESCE(m.discord_name, a.discord_id) AS who "
            "FROM assessment_attempts a "
            "LEFT JOIN members m ON m.discord_id = a.discord_id "
            "LEFT JOIN monthly_reviews r ON r.attempt_id = a.id "
            "WHERE a.type='monthly' AND a.status IN ('scored','flagged') "
            "  AND r.attempt_id IS NULL").fetchall()
    finally:
        conn.close()
    return [f"{r['who']}: monthly attempt {r['id']} finished but NO row in "
            f"monthly_reviews" for r in rows]


def check_eligible_but_never_recorded() -> list:
    """Students eligible for a monthly review for a long time with nothing
    recorded AND nothing in progress — the population-level smell that told us
    `monthly_reviews` was stuck at zero rows."""
    if not database.is_feature_enabled("assessment_monthly_review"):
        return []
    conn = database._connect()
    try:
        members = conn.execute(
            "SELECT discord_id, discord_name, level FROM members "
            "WHERE suspended_at IS NULL").fetchall()
        eligible, recorded = 0, 0
        for m in members:
            try:
                mastered = len(database.itqan_mastered_weeks(m["discord_id"], m["level"]))
            except Exception:
                continue
            if mastered < 4:
                continue
            eligible += 1
            if database.monthly_reviews_taken(m["discord_id"], m["level"]) > 0:
                recorded += 1
    finally:
        conn.close()
    # Only meaningful once several students have been eligible for a while.
    if eligible >= 3 and recorded == 0:
        return [f"{eligible} students are eligible for a monthly review and NOT "
                f"ONE result has ever been recorded — the finish path is "
                f"probably not persisting"]
    return []


def check_orphan_items() -> list:
    """Item rows whose attempt is gone. Produced by a void path that deletes the
    parent before the children, which is how the monthly void raised
    IntegrityError and answered 500."""
    conn = database._connect()
    try:
        n = conn.execute(
            "SELECT COUNT(*) c FROM assessment_items i "
            "LEFT JOIN assessment_attempts a ON a.id = i.attempt_id "
            "WHERE a.id IS NULL").fetchone()["c"]
    finally:
        conn.close()
    return [f"{n} orphan assessment_items rows (attempt deleted before its "
            f"items)"] if n else []


async def check_endpoints() -> list:
    """Probe the live endpoints unauthenticated. A 500 is the failure."""
    import aiohttp
    base = (getattr(config, "PUBLIC_API_BASE", "") or
            "https://bot.empireenglish.online").rstrip("/")
    findings = []
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for path in PROBE_ENDPOINTS:
                try:
                    async with session.post(
                            base + path,
                            json={"attempt_id": 1, "item_no": 1}) as resp:
                        if resp.status not in _ACCEPTABLE:
                            findings.append(
                                f"POST {path} -> HTTP {resp.status} "
                                f"(expected a clean rejection; 500 means the "
                                f"handler cannot return a response)")
                except Exception as e:
                    findings.append(f"POST {path} unreachable: {type(e).__name__}")
    except Exception as e:
        logger.warning("assessment_watchdog: endpoint probe setup failed: %s", e)
    return findings


# ============================================================
#  RUNNER
# ============================================================

async def run_checks() -> dict:
    """Run every check. Returns {'findings': [...], 'checked': n}."""
    findings, checked = [], 0
    for name, fn in (("endpoints", check_endpoints),
                     ("stranded", check_stranded_attempts),
                     ("monthly_recorded", check_monthly_results_recorded),
                     ("eligible_none_recorded", check_eligible_but_never_recorded),
                     ("orphan_items", check_orphan_items)):
        try:
            result = await fn() if name == "endpoints" else fn()
            findings.extend(result)
            checked += 1
        except Exception as e:
            logger.warning("assessment_watchdog: check %s errored: %s", name, e)
    return {"findings": findings, "checked": checked}


async def run_and_alert(state_holder) -> dict:
    """Run the checks and alert Empire Ops on a CHANGE of state.

    `state_holder` is any object we can stash the last finding-set on (the bot
    instance). De-duping on the finding set means a genuine outage alerts once,
    not every cycle -- while a NEW problem appearing still alerts immediately.
    """
    from . import ops_hub

    report = await run_checks()
    findings = report["findings"]
    signature = tuple(sorted(findings))
    previous = getattr(state_holder, "_assessment_watchdog_last", None)

    if not findings:
        if previous:
            try:
                await ops_hub.send_ops_message(
                    "✅ *Assessment watchdog* — all clear again\\. "
                    "The previously reported problems are gone\\.")
            except Exception as e:
                logger.warning("assessment_watchdog: recovery message failed: %s", e)
        state_holder._assessment_watchdog_last = None
        return report

    if signature == previous:
        return report  # same problem, already reported

    state_holder._assessment_watchdog_last = signature
    body = "\n".join(f"- {f}" for f in findings[:10])
    if len(findings) > 10:
        body += f"\n- … and {len(findings) - 10} more"
    try:
        await ops_hub.send_ops_alert(
            "Assessment problem detected",
            (body + "\n\nStudents are likely affected right now. Nothing has "
                    "been changed automatically — this watchdog only reports."),
            severity="warning")
    except Exception as e:
        logger.warning("assessment_watchdog: alert failed: %s", e)
    return report


def format_report(report: dict) -> str:
    """Plain text for the `!assessment-health` command."""
    findings = report.get("findings", [])
    if not findings:
        return (f"✅ **Assessment health: OK**\n"
                f"{report.get('checked', 0)} checks passed — endpoints "
                f"responding, no stranded attempts, results recording.")
    lines = [f"⚠️ **Assessment health: {len(findings)} problem(s)**", ""]
    lines += [f"• {f}" for f in findings]
    lines.append("\n_This is a read-only check — nothing was changed._")
    return "\n".join(lines)
