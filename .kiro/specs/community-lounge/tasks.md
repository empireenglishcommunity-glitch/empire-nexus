# Implementation Plan — Community Lounge ("Majlis")

## Status — LIVE FOR EVERYONE SINCE 2026-08-22, AND WORKING

> ✅ **Verified against the live database and guild on 2026-08-29.** All six flags
> have been **ON for everyone since 2026-08-22 23:25:41** (`updated_by`
> `kiro-rollout` — a prior session, the day before the CEFR restructure began).
> **No document recorded that release**, which is why this header said "not
> released" earlier the same day.
>
> **It is functioning, not just enabled:** `together_minutes` holds **7 rows across
> 3 students, ~274 minutes, 2026-08-26 → 2026-08-28**. A row only appears when a
> student is in a Majlis lounge **with company**, so the Phase 1 together-credit
> path works end to end.
>
> **Preflight passed** (Actions run 33253382924): anchor `voice-lounge` exists —
> id `1519798168684986560`, category `🌍 المجتمع | COMMUNITY`, `user_limit=6`
> already matching `lounge_capacity`. `#community-live` and the `community-pings`
> role exist too, and since neither is created by `setup_server.py` their existence
> is further evidence Majlis has genuinely run.
>
> **Still worth doing:** Phases 2–6 (beacon, dynamic pods, opt-in pings, Community
> Hour, together-reward) have been live for a week with **no Phase-7 test file** and
> no recorded observation of a beacon firing or a pod being spawned/reaped in
> production. Watch `#community-live` around 21:00 Africa/Cairo once before
> assuming all six phases behave as designed.
>
> The boxes below remain unticked and are **not** a work queue — see the note under
> "Evidence" for why they were never mass-ticked.

> 🔴 **The checkboxes below are stale — do NOT read them as the state of this
> work, and do NOT rebuild any of it.** This header said "PLAN APPROVED, Phase 0
> IN PROGRESS (2026-07-31)" with 0 of 28 boxes ticked until 2026-08-29, when a
> full ecosystem audit found Majlis had in fact shipped through **Phase 7**. It
> was also missing from `empire-chronicle`'s `SYSTEM-MAP.md`, `STATUS.md` and
> `README.md` entirely, so **no document anywhere recorded that this exists.**
> It is now documented in `SYSTEM-MAP.md` §13.
>
> **Evidence it is built** (verified 2026-08-29, all reproducible):
> - `src/community.py` — **1,028 lines**, covering every phase below
> - all **6** `community_*` flags registered in `flag_registry.py` under
>   initiative `majlis`, and wired into `bot.py`, `verification.py`,
>   `ops_commands.py`
> - `together_minutes` table in `database.py`'s `_SCHEMA`
> - scheduled loops `community_hour_loop` + `beacon_cleanup_loop` in `bot.py`,
>   plus `community.reap_empty_majlis_rooms`
> - Phase 7 owner controls: `/majlis` in `ops_commands.py` (Telegram) and the
>   `majlis` slash command in `bot.py`
> - **7 test files**, `tests/test_community_phase0.py` → `phase6.py`, all passing
>   inside the suite's 2,044
>
> **On the registry defaults:** all 6 are `default_enabled=False`, and that is
> **correct and deliberate** — it is the fail-closed ship state a *fresh* database
> gets, guarded by `test_majlis_flags_default_off`. It is **not** a claim that
> Majlis is off in production. Do not "sync" it; see steering §6.
>
> **What is genuinely NOT done:**
> - **Phase 7 has no dedicated test file** (`test_community_phase7.py` does not
>   exist) — the one real coverage gap.
> - No production observation of Phases 2–6 actually firing.
>
> Boxes below are left unticked rather than mass-ticked, because ticking them
> would require verifying all 28 sub-items individually and this header is the
> honest signal. Use the legend from `cefr-curriculum/tasks.md`: treat Phases 0–7
> as `[~]` (built + tested, **not live**). **Verify against the code before
> resuming any phase.**

Owner reviewed and approved the direction. Implementation began with Phase 0 and
ran through Phase 7.

**Owner-confirmed decisions:**
- ✅ **Majlis** direction approved.
- ✅ Pod capacity = **6**; together-time = **5 min**.
- ✅ **Community Hour = 9–10 PM Egypt time** (`Africa/Cairo`, `21:00`, 60 min).
  Scheduled in Egypt time, independent of the Dubai daily-task TZ.
- ✅ Build the **full sequence** (Phases 0–7 in order).

---

Build order. **Every phase is its own owner-merged PR, fully tested, and
deployed + live-verified with zero disruption to the 16 students.** Every
capability is behind its own flag (default OFF), so nothing is visible until we
deliberately enable it — pilot first, then all.

Legend: **[nexus]** = bot/API repo · **[dojo]** = practice site repo ·
**[chronicle]** = docs/memory.

> **Ordering rationale:** the *complaint* ("forced to sit alone") is fixed
> earliest — Phase 1 (humane credit) can ship right after foundations, before
> the fancier presence/room machinery. Each later phase adds professionalism.

---

## Phase 0 — Foundations (flags + config + data + presence helper) · [nexus]
- [ ] Register the 6 flags in `flag_registry.py` (all default OFF).
- [ ] `get_community_config()` + `COMMUNITY_CONFIG_DEFAULTS` + audit-logged
      setters in `settings` (all tunables from design §Configuration).
- [ ] Data: per-member-per-day **together-minutes** store
      (`add_together_minutes` / `get_together_minutes`), restart-safe, mirroring
      the existing voice-minute pattern; add to `RESET_WIPE_TABLES` if a table.
- [ ] `community.py` skeleton: `is_majlis_channel`, `lounge_occupancy`,
      config accessors — pure/unit-testable.
- [ ] Unit tests: config defaults/overrides; together-minute accrual math;
      Majlis identification.
- **Verify:** full suite green; **all flags OFF → no behavior change** in prod.

## Phase 1 — Humane, company-aware task #7 credit (THE COMPLAINT FIX) · [nexus]
- [ ] Extend voice tracking to accrue **together-seconds** while in a Majlis with
      ≥1 other member; persist per Dubai-day.
- [ ] `verify_community`: add the **OR** path — voice half done if
      `voice_min ≥ 10` **OR** `together_min ≥ together_minutes`; adapt the
      bilingual checklist to the nearest path. Behind `community_together_credit`.
- [ ] Tests: solo still needs 10 (flag off = identical to today); with company,
      5 min completes; `#general-chat` still required; bidi-safe copy.
- **Verify:** suite green; deploy; live-check with a real member — flag OFF path
      unchanged, flag ON grants the faster path; **no one is worse off.**

## Phase 2 — Presence beacon + `#community-live` · [nexus]
- [ ] Create `#community-live` (idempotent, guarded) in COMMUNITY.
- [ ] `maybe_beacon` / `clear_beacon`: occupancy band [1, `beacon_max_occupancy`],
      dedup per lounge per `beacon_cooldown_min`, TTL expiry, self-clean on
      empty; quiet-hours aware; jump link; **no @-ping yet** (post only). Behind
      `community_lounge_beacon`.
- [ ] Wire into `on_voice_state_update`; add `majlis_reaper`-lite loop to expire
      stale beacons (rooms reaping comes in Phase 3).
- [ ] Tests (mocked Discord): beacon fires in band, not when healthy, not for the
      joiner, deduped, cleaned on empty, silent in quiet hours.
- **Verify:** suite green; deploy; live-verify a real join posts one clean,
      self-removing beacon; spam-proof.

## Phase 3 — Tidy pods: capacity caps + dynamic overflow rooms · [nexus]
- [ ] Set `voice-lounge` `user_limit = lounge_capacity` (Majlis 1 anchor).
- [ ] Create the **"➕ افتح مجلس | New Room"** join-to-create hub (idempotent).
- [ ] Join-to-create: spawn "Majlis N" (capped), move member in, register in
      `majlis_rooms`; `reap_empty_majlis` loop deletes empty bot-created lounges
      after grace (never the anchor). Beacon becomes capacity-aware /
      load-balancing. Behind `community_dynamic_rooms`.
- [ ] Tests (mocked): spawn on hub-join, cap respected, reap only empty
      bot-created rooms, anchor never deleted, graceful on permission failure.
- **Verify:** suite green; deploy; live-verify spawn + move + auto-reap; failure
      falls back to the static lounge.

## Phase 4 — Opt-in pings + Knock · [nexus]
- [ ] `community-pings` opt-in role (create-if-missing) + self-toggle
      button/command; beacons @-ping only opted-in members. Behind
      `community_pings_optin`.
- [ ] `👋 Knock` button in `#community-live` + `!knock`: summon opted-in members,
      subject to dedup/quiet-hours/rate limits.
- [ ] Tests: only opted-in pinged; toggle on/off; knock rate-limited + quiet-hours.
- **Verify:** suite green; deploy; live-verify opt-in/out + a knock.

## Phase 5 — Community Hour + Telegram rally + topic-of-the-day · [nexus] (+ [dojo] optional)
- [ ] `community_hour_loop`: detect window start (schedule in `settings`,
      **`Africa/Cairo` / Egypt time, 21:00–22:00, 60 min** — NOT the Dubai
      daily-task TZ), once-per-window fingerprint dedup; rally in
      `#community-live` + **one**
      Telegram broadcast to student group(s) (reuse `_send_telegram_groups`);
      include topic-of-the-day + lounge jump link. Behind `community_power_hour`.
- [ ] Curated bilingual topic-prompt list (owner-editable in `settings`).
- [ ] Tests: fires once per window, dedup across reconnects, quiet-hours/schedule
      respected, Telegram called once (mocked).
- **Verify:** suite green; deploy; live dry-run of a window (no student spam);
      confirm single Telegram send.

## Phase 6 — Reward togetherness (optional bonus) · [nexus]
- [ ] On together-path completion with ≥1 distinct other member: optional
      "🤝 مجلس" acknowledgement + optional `together_reward_points` (default 0 =
      off); once/day, abuse-resistant. Behind `community_together_reward`.
- [ ] Tests: bonus only on genuine together completion, once/day, solo unaffected.
- **Verify:** suite green; deploy; live-verify with config point value.

## Phase 7 — Owner controls, guides, rollout · [nexus] + [dojo] + [chronicle]
- [ ] `/majlis` (Discord admin + Telegram): live state (who's in which lounge,
      active beacons) + current config; config setters.
- [ ] `/guide` (student): a Community/Majlis card — how #7 works now, together
      path, Community Hour, opt-in pings. `/ops-guide` (owner): control + config
      + flag reference. **[dojo]**
- [ ] SYSTEM-MAP + STATUS updated. **[chronicle]**
- [ ] **Rollout:** enable flags in a safe order to a **pilot** (e.g. BioRoMa +
      1–2), verify live, then all 16 (empty allowlist). Announce via the normal
      "what's new" changelog.
- **Verify:** suite green; guides live; pilot clean; then full enable with a live
      confirmation and zero disruption.

---

## Cross-cutting requirements (every phase)
- Full nexus test suite green before deploy; **bump `BOT_VERSION`** on each bot
  deploy; use the bot-only rebuild (`docker compose up -d --build
  empire-english-bot`).
- All new copy **bilingual, Arabic-first, bidi-safe** (run `scripts/bidi_check`).
- Reuse quiet-hours, the dedup-fingerprint pattern, and `settings` config.
- Every Discord op permission-checked + try/except with a static-lounge fallback;
  **never block task #7 or crash the bot.**
- With every flag OFF, production behavior is **identical to today**.

## Suggested fast-relief path (owner's call)
If the owner wants the complaint eased ASAP with minimal surface area: ship
**Phase 0 + Phase 1** first (humane credit) — that alone removes the "forced to
sit alone" pain — then layer Phases 2–7 for the professional experience.
