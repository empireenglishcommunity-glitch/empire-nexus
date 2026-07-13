# Tasks — Nabd (نبض): Student Notification System

> **Status: ALL PHASES (N0-N7) COMPLETE AND DEPLOYED as of 2026-07-13
> (session 12).** All 8 notification flags enabled on production.
> 33 commands registered.

---

## Phase N0 — Foundation ✅

> [empire-nexus PR #70](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/70). Deployed.

- [x] notification_preferences table
- [x] notification_log table
- [x] Helper functions (get/set prefs, log, was_sent, is_quiet_hours)
- [x] !notifications / !إشعارات command
- [x] Gate behind `nabd_preferences` flag

## Phase N1 — Morning Kickstart DM ✅

> [empire-nexus PR #72](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/72). Deployed.

- [x] morning_kickstart @tasks.loop at 6:05 AM
- [x] Personal message: greeting, streak, first task, practice link
- [x] Respects preferences, quiet hours, language phase, duplicate prevention
- [x] Gate behind `nabd_morning` flag

## Phase N2 — Evening Reminder + Streak-at-Risk ✅

> [empire-nexus PR #73](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/73). Deployed.

- [x] evening_reminder @tasks.loop at 8 PM (1-6 tasks done)
- [x] streak_at_risk @tasks.loop at 9 PM (streak≥3, 0 tasks)
- [x] Gates: `nabd_evening`, `nabd_streak_alert`

## Phase N3 — Real-Time Milestone Celebrations ✅

> [empire-nexus PR #73](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/73). Deployed.

- [x] Celebration message library (4 variants all-7, 3 variants streak)
- [x] DM + public post in #daily-check-in
- [x] Wired into process_submission via milestones return field
- [x] Gate behind `nabd_celebrations`

## Phase N4 — Weekly Progress Summary ✅

> [empire-nexus PR #73](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/73). Deployed.

- [x] nabd_weekly_summary @tasks.loop Friday 8:30 PM
- [x] Completion rate, streak, points, tier encouragement
- [x] Gate behind `nabd_weekly_summary`

## Phase N5 — Absence Recovery Ladder ✅

> [empire-nexus PR #73](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/73). Deployed.

- [x] nabd_absence_check @tasks.loop 10 AM daily
- [x] Day 2: bot DM / Day 3: buddy prompt / Day 5: comeback task / Day 7+: final DM
- [x] Each level fires once per absence streak (via notification_log)
- [x] Gate behind `nabd_absence_recovery`

## Phase N6 — Social Proof (opt-in) ✅

> [empire-nexus PR #73](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/73). Deployed.

- [x] Notify same-level peers (opted in) when someone completes all 7
- [x] Max 1 per peer per day
- [x] Gate behind `nabd_social_proof`

## Phase N7 — !pulse Admin Command ✅

> [empire-nexus PR #73](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/73). Deployed.

- [x] !pulse / !نبض: today's notification counts, week total, opt-outs
