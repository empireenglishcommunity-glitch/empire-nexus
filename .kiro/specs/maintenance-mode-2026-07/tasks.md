# Maintenance Mode & "What's New" — Tasks

Each phase = its own PR → full test suite → owner merge → deploy → live-verify.

## Phase 1 — Status brain + API + page reaction
- [ ] 1.1 `src/maintenance.py`: `get_status()`, `start()`, `end()`, `is_active()`,
      auto-end failsafe, backed by `get_setting`/`set_setting`.
- [ ] 1.2 `GET /api/status` (public, no token, CORS) in `api_server.py`.
- [ ] 1.3 `site/js/status.js`: fetch status, render soft banner / hard overlay
      (bilingual, ETA, "progress safe"), fail-open.
- [ ] 1.4 CSS in `empire.css` (`.maint-banner`, `.maint-overlay`).
- [ ] 1.5 Include `status.js` on every page: `index.html`, `gate.html`,
      `guide/index.html`, and generated exercise pages via `generate.py`.
- [ ] 1.6 Tests: `get_status`/`start`/`end`/auto-end; `/api/status` shape.
- [ ] 1.7 Ship + verify: toggle via a temporary manual set, confirm banner/overlay
      appear/disappear live with no redeploy.

## Phase 2 — Commands + broadcast
- [ ] 2.1 `maintenance.broadcast_start()/broadcast_end()`: Discord `#announcements`
      + bot presence + optional Telegram groups (`MAINTENANCE_TG_CHAT_IDS`).
- [ ] 2.2 `@command("/maintenance")` in `ops_commands.py` (start|end|status).
- [ ] 2.3 `!maintenance` owner-only Discord command in `bot.py`.
- [ ] 2.4 Restore presence + re-apply active state on `on_ready`.
- [ ] 2.5 Tests: command parsing, owner gate, broadcast targets (mocked).
- [ ] 2.6 Ship + verify live (soft + hard, start + end).
- [ ] 2.7 OWNER INPUT: paid + free Telegram group chat IDs (bot must be member).

## Phase 3 — Streak protection + auto-resume
- [ ] 3.1 Record maintenance day(s) (Asia/Dubai) while active.
- [ ] 3.2 `_recompute_streak()` bridges across maintenance days (non-breaking).
- [ ] 3.3 Scheduled auto-resume check fires `end` broadcast if window elapsed.
- [ ] 3.4 Tests: streak bridged across a maintenance day; auto-resume.
- [ ] 3.5 Ship + verify.

## Phase 4 — Changelog + What's New + guide
- [ ] 4.1 `content/changelog.json` source + loader.
- [ ] 4.2 `end` broadcast uses latest changelog entry.
- [ ] 4.3 Page "What's New" one-time toast (localStorage seen-id) in `status.js`.
- [ ] 4.4 Guide "Latest updates / آخر التحديثات" section via `generate.py`.
- [ ] 4.5 Tests + ship + verify.

## Phase 5 — Optional polish (only if wanted)
- [ ] 5.1 Scheduled/pre-announced maintenance.
- [ ] 5.2 Support-channel auto-responder during maintenance.
- [ ] 5.3 Status heartbeat dot in the page header.

## Cross-cutting
- [ ] Update `SYSTEM-MAP.md` (chronicle) + `STATUS.md` when done.
- [ ] Register any new feature flag in `flag_registry.py` (e.g. `maintenance_mode`
      kill-switch) if introduced.
