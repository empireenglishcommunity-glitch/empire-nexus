# Maintenance Mode & "What's New" — Design

## Architecture

```
        ┌───────────────────────────────────────────┐
        │  SYSTEM STATUS (bot DB — settings table)   │
        │  maintenance_active 0|1                     │
        │  maintenance_level  soft|hard               │
        │  maintenance_reason, _eta, _started_at,     │
        │  _message, _auto_end_at                     │
        └───────────────┬───────────────────────────┘
                        │ maintenance.py (get/set/broadcast helpers)
      ┌─────────────────┼──────────────────────────────┐
      ▼                 ▼                                ▼
 GET /api/status   Discord bot                    Telegram (Markaz)
 (public JSON)     - presence = 🔧                /maintenance start|end|status
      │            - #announcements post          ops_commands @command
      ▼            - streak protection
 Practice page (client-side)
 - soft banner / hard overlay (bilingual, ETA, "progress safe")
 - "What's New" toast
 - guide "Latest updates" section
```

## Data model (settings key/value — no new table)
Use existing `get_setting`/`set_setting`:
- `maintenance_active`: "0" | "1"
- `maintenance_level`: "soft" | "hard"
- `maintenance_reason`: free text (shown to students, optional)
- `maintenance_message`: optional custom override text
- `maintenance_eta`: ISO timestamp or short text ("~20 min")
- `maintenance_started_at`: ISO timestamp
- `maintenance_auto_end_at`: ISO timestamp (now + window; failsafe)

New module `src/maintenance.py` wraps these: `get_status() -> dict`,
`start(level, reason, eta, window_minutes)`, `end()`, `is_active()`,
`is_within_active_window(date)` (for streak protection).

## Phase 1 — status brain + API + page
- `maintenance.py` with get/set backed by settings; `get_status()` also honors
  the auto-end failsafe (if now > auto_end_at, treat as live).
- `api_server.py`: `@routes.get("/api/status")` — public, no token, returns
  `{state, level, reason, eta, message, started_at}`. Add CORS header (page is
  a different origin) — reuse existing CORS handling if present, else allow GET.
- Practice page: new `site/js/status.js`, included in the `<head>` of every page
  (index, gate, guide, and every generated exercise page via generate.py).
  - Fetches `${API_BASE}/api/status` (network, no-store).
  - `live` → nothing.
  - `soft` → injects a dismissible top banner (bilingual, reason, ETA).
  - `hard` → injects a fixed full-screen overlay (bilingual, ETA countdown,
    "🔒 progress safe"), blocks interaction.
  - Fail-open: any fetch error → render nothing.
  - CSS in `empire.css` (`.maint-banner`, `.maint-overlay`).

## Phase 2 — commands + broadcast
- `ops_commands.py`: `@command("/maintenance")` → parse `start|end|status`,
  call `maintenance.*`, then broadcast.
- Discord: `!maintenance` owner-only command in `bot.py` (mirror logic).
- Broadcast helper in `maintenance.py`:
  - Discord: post to `#announcements` (reuse `/announce` pattern) + set
    `bot.change_presence(activity=..., status=idle)` on start, restore on end.
  - Telegram: post to configured group chat IDs via the ops bot token. New
    config `MAINTENANCE_TG_CHAT_IDS` (comma-separated); skip if empty.
- Messages are pre-written bilingual templates (start/end), with reason/ETA/
  changelog interpolated.

## Phase 3 — streak protection + auto-resume
- Record maintenance day(s): when active, mark the Asia/Dubai date(s) in a
  `maintenance_days` set (settings JSON or tiny table).
- `_recompute_streak()`: when checking for a "gap" day, treat a maintenance day
  as a non-breaking pass (bridge the streak across it).
- Auto-resume: `get_status()` returns `live` once `now > auto_end_at`; a
  lightweight scheduled check also fires the "end" broadcast if it auto-resumed.

## Phase 4 — changelog + What's New + guide
- `content/changelog.json` (or `.md`): list of `{version/date, title, items[],
  audience}`. Single source.
- `end` uses the latest entry as the broadcast body (or an inline message).
- Page "What's New": `status.js` compares latest changelog id to a
  `localStorage` seen-id; if newer, shows a one-time dismissible toast.
- Guide: `generate.py` (dojo) renders a "Latest updates / آخر التحديثات"
  section from `changelog.json` at build time; redeploy refreshes it. (Bot can
  also expose `GET /api/changelog` for a live version later.)

## Failure modes
- Status endpoint down → page assumes live (R6.3).
- Auto-end prevents stuck-locked students (R6.1).
- Telegram groups unset → Discord-only broadcast (R4.3).
- Bot restart mid-maintenance → state persists (settings table), presence
  re-applied on `on_ready` if still active.

## Testing
- Unit: `maintenance.start/end/get_status`, auto-end expiry, streak bridging
  across a maintenance day, `/api/status` shape, command parsing + owner gate.
- Manual/live per phase: toggle soft/hard, verify page banner/overlay,
  broadcast fires, presence changes, streak preserved, auto-resume.
