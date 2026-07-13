# Tasks — Nabd (نبض): Student Notification System

> **How to use this file:** same discipline as Aegis/Bawaba — work top
> to bottom, check off tasks in the same commit/PR that completes them.
> Each phase ships behind a feature flag (`nabd_*`), tested on the ghost
> bot first.

---

## Phase N0 — Foundation: preferences table + notification log + engine

- [ ] **N0.1** Add `notification_preferences` table to `database.py`
  (morning_dm, evening_dm, streak_alert, celebrations, social_proof,
  weekly_summary, quiet_start, quiet_end). Default: all ON except
  social_proof (opt-in).
- [ ] **N0.2** Add `notification_log` table to `database.py` (tracks
  what was sent, prevents duplicates, enables analytics).
- [ ] **N0.3** Add helper functions: `get_notification_prefs(discord_id)`,
  `set_notification_pref(discord_id, key, value)`,
  `log_notification(discord_id, type, date)`,
  `was_notification_sent(discord_id, type, date)`,
  `is_quiet_hours(discord_id)`.
- [ ] **N0.4** Add `!إشعارات` / `!notifications` command — shows current
  settings + allows toggling individual notification types.
- [ ] **N0.5** Gate behind feature flag `nabd_preferences`.
- [ ] **N0.6** Add tests for the preference and log functions.

## Phase N1 — Morning Kickstart DM (highest impact)

- [ ] **N1.1** Add `morning_kickstart` `@tasks.loop` at
  `DAILY_TASK_HOUR` + 5 minutes. Iterates all active members, skips
  those who opted out or already completed a task today.
- [ ] **N1.2** Build the personal morning message: greeting, streak,
  first task name (respects gradual intro), practice platform link.
  Respects Bawaba B5 language phase.
- [ ] **N1.3** Log each sent notification. Respect quiet hours.
- [ ] **N1.4** Gate behind feature flag `nabd_morning`.
- [ ] **N1.5** Rate-limit sending (asyncio.sleep between DMs to stay
  under Discord's rate limit).

## Phase N2 — Evening Reminder + Streak-at-Risk Alert

- [ ] **N2.1** Add `evening_reminder` `@tasks.loop` at 20:00. Sends DM
  to students who completed 1-6 tasks (partial — encourage finish).
- [ ] **N2.2** Add `streak_at_risk` `@tasks.loop` at 21:00. Sends DM to
  students with streak ≥3 who completed 0 tasks today.
- [ ] **N2.3** Build both message templates (bilingual, personal).
  Streak-at-risk suggests the easiest task (community: just type in
  #general-chat or join voice 10 min).
- [ ] **N2.4** Gate behind flags `nabd_evening` and `nabd_streak_alert`.
- [ ] **N2.5** Both check notification_log to prevent double-sends.

## Phase N3 — Real-Time Milestone Celebrations

- [ ] **N3.1** Create a celebration message library (3-5 variants per
  milestone type: all-7-done, streak-7, streak-14, streak-30,
  first-assessment, high-completion-week).
- [ ] **N3.2** Wire into `process_submission()`: after recording the
  submission, check if a milestone was just hit. If so, send the
  celebration (DM + optional public post).
- [ ] **N3.3** Vary the message (random selection from the library) so
  it doesn't feel robotic.
- [ ] **N3.4** Gate behind flag `nabd_celebrations`.

## Phase N4 — Weekly Progress Summary

- [ ] **N4.1** Add `weekly_progress_summary` `@tasks.loop` at Friday
  20:00. Replaces or enhances the existing `monday_progress_report`.
- [ ] **N4.2** Build the summary: this week vs. last week completion,
  strongest/weakest task type, tier-based encouragement message.
- [ ] **N4.3** Visual progress bar (text-based, same pattern as !progress).
- [ ] **N4.4** Gate behind flag `nabd_weekly_summary`.

## Phase N5 — Absence Recovery Ladder

- [ ] **N5.1** Add absence tracking: extend the existing hourly
  `streak_update` loop (or add a new daily loop) to check days since
  last activity for each member.
- [ ] **N5.2** Implement the 4-step ladder: day 2 (bot DM), day 3
  (buddy prompt), day 5 (comeback mini-task DM), day 7+ (final DM +
  already in !attention).
- [ ] **N5.3** Track escalation level per member (via notification_log
  with types `absence_day2`, `absence_day3`, etc.) so each step fires
  only once per absence streak.
- [ ] **N5.4** "Comeback mini-task" design: one extremely easy task
  (e.g. "اكتب جملة واحدة بالإنجليزي في #general-chat ← ده بيحسبلك
  مهمة community") that gets them back with zero friction.
- [ ] **N5.5** Gate behind flag `nabd_absence_recovery`.

## Phase N6 — Social Proof (opt-in)

- [ ] **N6.1** When a student completes all 7 tasks, notify other
  same-level members who opted in (social_proof=1 in preferences) and
  haven't completed all tasks today.
- [ ] **N6.2** Max 1 social proof notification per member per day.
  Framing: community activity, not competition.
- [ ] **N6.3** Gate behind flag `nabd_social_proof`.

## Phase N7 — Polish: Smart Timing + Analytics Command

- [ ] **N7.1** Add `!نبض` / `!pulse` admin command: shows notification
  stats (how many morning DMs sent today, how many streak alerts,
  how many students opted out of what).
- [ ] **N7.2** Consider adaptive timing: if a student consistently
  submits tasks at 9 PM (not morning), shift their morning DM to
  afternoon. (This is a stretch goal — implement only if the simpler
  fixed-time approach proves insufficient.)

---

## Cross-phase notes

- **Feature flag naming:** all use the `nabd_` prefix.
- **Ghost bot testing:** test each phase on the ghost bot first.
- **Discord rate limits:** DMs are limited. Add `asyncio.sleep(0.5)`
  between sends in any loop that DMs multiple members.
- **Language phase:** all messages use `bl_for_member()` or
  `response_language()` from Bawaba B5 — week 1 students get Arabic,
  week 4+ get bilingual.
- **Existing features NOT replaced:** the existing
  `post_missed_day_reminders()`, `send_weekly_progress_report()`, and
  `check_at_risk_members()` continue working (they post to channels,
  not DMs). Nabd adds the PERSONAL DM layer on top.
