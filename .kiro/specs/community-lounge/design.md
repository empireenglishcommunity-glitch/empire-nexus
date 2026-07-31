# Design — Community Lounge ("Majlis")

Turns task #7 from *"sit alone for 10 minutes"* into *"drop into the Majlis,
you'll likely find someone — and if not, you're invited-in and never worse off."*
Three layers, all additive and flag-gated:

1. **Humane credit** — company-aware task #7 (never punish the solo case).
2. **Presence** — a smart, self-cleaning beacon + a scheduled Community Hour.
3. **Organization** — small capped pods with automatic overflow, so it's lively
   but never a mob.

## Guiding principles

- **Additive only.** The current completion path (10 min any voice +
  `#general-chat`) stays valid forever. Everything new is a *faster/friendlier*
  path — impossible to make a student worse off.
- **Concentrate, then cap.** Meeting requires overlap → funnel social time into
  the COMMUNITY-category Majlis lounge(s) (not scattered level rooms). Then cap
  each lounge so overlap never becomes chaos.
- **Invite, don't nag.** Presence is broadcast to one dedicated, self-cleaning
  channel; @-mentions are opt-in; Telegram is reserved for Community Hour only.
- **Owner-tunable, flag-gated, reversible.** No hard-coded magic numbers; every
  layer independently switchable with no redeploy.
- **Reuse what exists.** Voice-minute tracking, quiet-hours, feature-flag
  registry, settings config, `tasks.loop` scheduler, Telegram bridge, the
  dedup-fingerprint pattern (as in `onboarding_gate_check`).

## Live baseline reused

- COMMUNITY category → `voice-lounge` (becomes **Majlis 1**) + `#general-chat`
  (unchanged task-#7 text requirement).
- Existing voice tracking: `on_voice_state_update` → `verification.on_voice_join
  /on_voice_leave`, persisted per Dubai-day via `database.add_voice_minutes`,
  restart-recovery scan in `on_ready`. **We extend this**, not replace it.
- Bot has Administrator (create/move/limit channels) — all ops feasible; still
  wrapped in try/except with static fallback.

---

## Locked design decisions (owner delegated: "go with what you recommend")

- **D1. Majlis = the COMMUNITY lounge(s) only.** Together-time counts in Majlis
  lounges. Level practice rooms are for structured practice and are left alone.
  The 10-min "any voice" path remains as the backwards-compatible fallback.
- **D2. Company-aware OR-credit.** Voice half of #7 = `(10 min any voice)` **OR**
  `(5 min together-time in a Majlis)`. Solo is never worse than today.
- **D3. Capacity cap = 6 per lounge** (ideal pod 2–5). Prevents a mob while
  keeping a group lively.
- **D4. Dynamic overflow via join-to-create.** One **"➕ افتح مجلس / New Room"**
  hub channel; joining spawns "Majlis N" (capped 6), moves the user in,
  auto-reaps when empty (grace period). `voice-lounge` (Majlis 1) is the
  permanent anchor and is never deleted.
- **D5. Capacity-aware beacon.** Beacon fires only for lounges with occupancy in
  `[1, beacon_max_occupancy=4]`; points newcomers to the "lively-not-full"
  lounge; goes silent when healthy; dedup per lounge per 40 min; self-cleans.
- **D6. `#community-live`** is a new dedicated text channel in COMMUNITY for all
  presence chatter; `#general-chat` stays for human conversation.
- **D7. @-mentions are opt-in** via a self-toggle `community-pings` role; Knock
  is an opt-in demand signal.
- **D8. Telegram = Community Hour only** (one high-signal rally). No per-join
  Telegram.
- **D9. Everything flag-gated, default OFF; phased pilot rollout** exactly like
  Itqan.

---

## Components

### 1. `community.py` (new module) — the Majlis brain
Owns lounge identity, occupancy, beacon lifecycle, dynamic-room registry, and
Community Hour logic. Pure-ish helpers are unit-testable without Discord.

- **Lounge identity:** `is_majlis_channel(channel)` — true for `voice-lounge`
  and any dynamically created "Majlis N". Backed by a small registry in
  `settings` (`majlis_rooms`: list of channel IDs the bot created) + the static
  anchor by name/ID.
- **Occupancy:** `lounge_occupancy(guild)` → `{channel_id: [member_ids]}` from
  the gateway voice state (no API spam).
- **Together-time:** extend voice tracking so that while a member is in a Majlis
  lounge **with ≥1 other member**, their *together-seconds* accrue (separate
  from raw voice minutes). Persisted per Dubai-day
  (`database.add_together_minutes` / `get_together_minutes`), same pattern as
  voice minutes (restart-safe).
- **Beacon lifecycle:** `maybe_beacon(guild, channel)` on join; `clear_beacon`
  on empty/expire. Beacon state (message id, lounge id, expires_at, last_fired)
  in memory + a lightweight `settings` mirror for restart-safety.
- **Dynamic rooms:** `ensure_overflow(guild)` creates "Majlis N" (capped) under
  COMMUNITY; `reap_empty_majlis(guild)` deletes empty bot-created lounges after
  a grace period (called from a `tasks.loop`).
- **Community Hour:** `community_hour_due()` + `run_community_hour(guild)`.

### 2. `verification.py` — company-aware credit (R1)
- Extend voice tracking to record together-seconds when in a Majlis with company.
- `verify_community` gains the OR path: voice half satisfied by
  `get_voice_minutes_today ≥ 10` **OR** `get_together_minutes_today ≥
  together_minutes`. Checklist copy adapts to whichever path is closer.
- Fully behind `community_together_credit`; with the flag OFF, the function is
  byte-for-byte today's behavior.

### 3. `bot.py` — wiring
- `on_voice_state_update`: in addition to existing join/leave, call
  `community.on_voice_change(...)` to (a) accrue together-time, (b) fire/clear
  beacons, (c) load-balance / offer overflow.
- New `tasks.loop`s: `majlis_reaper` (reap empty dynamic lounges + expire stale
  beacons), `community_hour_loop` (fire the scheduled rally). Both quiet-hours
  aware, flag-gated, started in `on_ready` only when their flag is ON.
- Join-to-create: when a member joins the "➕ New Room" hub channel, spawn +
  move (Manage Channels/Move Members).
- Owner command `/majlis` (Discord admin + Telegram): live state + config.
- `!knock` / button handler.

### 4. `flag_registry.py` — six flags (all default OFF)
`community_together_credit`, `community_lounge_beacon`,
`community_dynamic_rooms`, `community_pings_optin`, `community_power_hour`,
`community_together_reward`.

### 5. `database.py` — minimal additions
- `together_minutes` per-member-per-day (mirror of the existing voice-minute
  store; new column or a small `community_daily` table keyed by (discord_id,
  ymd)). Included in `RESET_WIPE_TABLES` if a table.
- Config keys via existing `settings` get/set (no schema churn):
  `majlis_rooms`, `community_hour` schedule, and the tunables in R9.
- Helpers: `add_together_minutes`, `get_together_minutes`, and beacon/room
  registry get/set.

### 6. Discord structure (created idempotently by the bot, guarded)
- `#community-live` text channel in COMMUNITY (create-if-missing).
- `➕ افتح مجلس | New Room` voice hub in COMMUNITY (create-if-missing).
- `voice-lounge` set to `user_limit = lounge_capacity` (Majlis 1 anchor).
- `community-pings` opt-in role (create-if-missing).
All creation is idempotent, permission-checked, try/except with fallback.

---

## Key flows

### A. Join → beacon (R2/R3/R5)
1. Member joins a Majlis lounge.
2. `on_voice_change`: compute occupancy.
3. If occupancy ∈ [1, 4] and no active beacon for this lounge within cooldown
   and not quiet-hours → post beacon to `#community-live` (jump link; @-ping only
   opted-in members). Store beacon state + expiry.
4. If occupancy ≥ 5 (healthy) → no beacon (and clear any pending one).
5. On member leave / lounge empty / expiry → edit/remove beacon (self-clean).

### B. Together-credit (R1)
1. While a member is in a Majlis with ≥1 other member, accrue together-seconds.
2. On leave (and on the daily verify), persist together-minutes for the day.
3. `verify_community` (flag ON): voice half done if `voice≥10` OR
   `together≥together_minutes`. Combined with the `#general-chat` check → #7 done.
4. Checklist shows the nearest path; solo students see the familiar X/10.

### C. Overflow pods (R4)
1. Beacon/entry prefers a lounge with room (occupancy < cap).
2. If all Majlis lounges are full → member uses the "➕ New Room" hub → bot
   spawns "Majlis N" (cap 6), moves them in, registers it.
3. `majlis_reaper` loop deletes empty bot-created lounges after grace; never
   deletes the `voice-lounge` anchor.

### D. Community Hour (R6/R7)
1. `community_hour_loop` detects the window start (schedule in `settings`,
   guild TZ), guarded by a once-per-window fingerprint (dedup like
   `onboarding_gate_check`).
2. Post rally to `#community-live` + **one** Telegram broadcast to the student
   group(s) (reuse `maintenance._send_telegram_groups` pattern) with the
   topic-of-the-day + lounge jump link.
3. During the window, the together path makes #7 trivial.

### E. Knock (R5)
Member presses "👋 Knock" (or `!knock`) while in a Majlis → posts a summon to
`#community-live` pinging the opt-in role, subject to dedup/quiet-hours/rate
limits.

---

## Configuration (settings, owner-tunable; defaults)

| Key | Default | Meaning |
|-----|---------|---------|
| `together_minutes` | 5 | together-time needed for the fast #7 path |
| `lounge_capacity` | 6 | hard cap per Majlis lounge |
| `beacon_max_occupancy` | 4 | beacon only when occupancy ≤ this |
| `beacon_cooldown_min` | 40 | min minutes between beacons per lounge |
| `beacon_ttl_min` | 20 | auto-expire a beacon after this |
| `majlis_reap_grace_min` | 3 | empty dynamic lounge grace before delete |
| `community_hour` | {days, "20:00", 30} | schedule (guild TZ) |
| `community_hour_minutes` | 30 | window length |
| `together_reward_points` | 0 (off) | optional bonus for together completion |

All reads via a `get_community_config()` with `COMMUNITY_CONFIG_DEFAULTS` (mirror
of `get_itqan_config`), audit-logged setters.

## Guardrails & failure modes (R10)

- **All flags OFF ⇒ zero behavior change.** Loops don't start; `verify_community`
  is unchanged; no channels/roles created.
- Every Discord channel/role/move op is permission-checked and try/except; on
  failure → log, fall back to the static `voice-lounge` + the 10-min path.
- Beacons/rooms are **best-effort**: a failed beacon never blocks task #7.
- Restart-safe: together-minutes persisted per day; beacon/room registry mirrored
  in `settings`; reuse the `on_ready` voice-session recovery scan.
- Rate limits are per-lounge **and** global; quiet-hours enforced everywhere.

## Scale (R11)
16 → 160 needs no admin: more people ⇒ more capped pods auto-created and auto-
reaped; beacon volume bounded by cooldown + occupancy band + global cap.

## Privacy (R12)
Only transient occupancy + per-day minute counters. No "who talked to whom" log.
Beacons name only the person currently present and expire quickly.

## Out of scope (for now)
- Cross-level matchmaking / skill-based pairing (everyone is L0 today).
- Voice transcription / participation scoring inside the lounge.
- Stage channels / events calendar integration (could be a future Community Hour
  upgrade).
- Rewiring the orphaned pronunciation engine (separate parked spec).
