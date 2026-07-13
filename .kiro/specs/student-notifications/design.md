# Design — Nabd (نبض): Student Notification System

## Architecture: Time-Triggered Personal Outreach

```
    6:05 AM          8:00 PM         9:00 PM         Realtime
       │                │               │               │
       ▼                ▼               ▼               ▼
┌─────────────┐  ┌───────────┐  ┌──────────────┐  ┌──────────┐
│  Morning    │  │  Evening  │  │  Streak-at-  │  │Milestone │
│  Kickstart  │  │  Reminder │  │  Risk Alert  │  │Celebrate │
│  (DM)       │  │  (DM)     │  │  (DM)        │  │(DM+Pub)  │
└─────────────┘  └───────────┘  └──────────────┘  └──────────┘
       │                │               │               │
       ▼                ▼               ▼               ▼
┌──────────────────────────────────────────────────────────────┐
│                  NOTIFICATION ENGINE                          │
│                                                              │
│  • Check: should this student get this notification?         │
│  • Check: are they in quiet hours?                           │
│  • Check: have they opted out of this type?                  │
│  • Check: language phase (Bawaba B5)                         │
│  • Format: personal message with their real data             │
│  • Send: Discord DM (graceful on Forbidden)                  │
│  • Log: record what was sent (prevent double-sends)          │
└──────────────────────────────────────────────────────────────┘
```

## Component 1 — Notification Preferences (database + commands)

**New table:**
```sql
CREATE TABLE IF NOT EXISTS notification_preferences (
    discord_id      TEXT PRIMARY KEY,
    morning_dm      INTEGER NOT NULL DEFAULT 1,
    evening_dm      INTEGER NOT NULL DEFAULT 1,
    streak_alert    INTEGER NOT NULL DEFAULT 1,
    celebrations    INTEGER NOT NULL DEFAULT 1,
    social_proof    INTEGER NOT NULL DEFAULT 0,  -- opt-IN
    weekly_summary  INTEGER NOT NULL DEFAULT 1,
    quiet_start     TEXT DEFAULT '23:00',  -- 11 PM
    quiet_end       TEXT DEFAULT '05:00',  -- 5 AM
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Command:** `!إشعارات` / `!notifications` — shows settings, allows toggling.

**Quiet hours check:** before any DM, check if current time (in the
member's timezone — use config.TIMEZONE for now since all students are
in the same region) is between quiet_start and quiet_end. If so, skip.

## Component 2 — Morning Kickstart (6:05 AM)

**Trigger:** new `@tasks.loop` firing at `DAILY_TASK_HOUR:05` (5 min
after the daily task post). Could also be a second pass in the existing
`daily_task_post` loop — but a separate loop is cleaner (different
concern: posting to channels vs. DM'ing individuals).

**Logic per student:**
1. Skip if `morning_dm` preference is OFF
2. Skip if they already completed ≥1 task today (don't nag the active)
3. Skip if quiet hours
4. Build personal message:
   - Greeting (time-appropriate: صباح الخير)
   - Current streak + "keep it going" framing
   - First available task name (respects gradual intro)
   - Practice platform link for today
5. Send DM (catch Forbidden, log)

**Message template (week 1 / arabic phase):**
```
🌅 صباح الخير {name}!

مهامك جاهزة 📋
🔥 سلسلتك: {streak} يوم — خلي اليوم رقم {streak+1}!

أول مهمة: {task_name_ar}
🌐 اتمرن أونلاين: {practice_url}

اكتب `!1` لما تخلص 💪
```

## Component 3 — Evening Incomplete Reminder (8 PM)

**Trigger:** `@tasks.loop` at 20:00.

**Logic per student:**
1. Skip if `evening_dm` preference is OFF
2. Skip if quiet hours
3. Get today's completed tasks count
4. Skip if count == 0 (total absence → handled by streak-at-risk)
5. Skip if count >= 7 (all done → no reminder needed)
6. Build message showing remaining tasks + quickest suggestion

**Message template:**
```
⏰ عندك {remaining} مهام لسه النهاردة.

المتبقي: {task_list}

💡 أسرع مهمة: {easiest_task} (5 دقايق بس)
اكتب `!{task_number}` لما تخلص
```

## Component 4 — Streak-at-Risk Alert (9 PM)

**Trigger:** `@tasks.loop` at 21:00.

**Logic per student:**
1. Skip if `streak_alert` preference is OFF
2. Skip if quiet hours
3. Skip if current_streak < 3 (not worth alerting for a 1-2 day streak)
4. Skip if they completed ANY task today (even 1 means streak is safe)
5. Skip if already sent a streak alert today (check notification_log)
6. Build urgent message

**Message template:**
```
⚠️ سلسلتك ({streak} يوم) هتنكسر الليلة!

لو عملت مهمة واحدة بس قبل 12 الليل، هتحافظ عليها.

💡 أسهل حاجة تعملها دلوقتي:
اكتب `!7` (مشاركة مجتمعية — ادخل voice 10 دقايق أو اكتب جملة في #general-chat)

ما تضيعش {streak} يوم شغل! 🔥
```

## Component 5 — Real-Time Milestone Celebrations

**Trigger:** called from `process_submission()` directly (not a loop —
happens immediately when the milestone is reached).

**Milestones:**
- All 7 tasks complete today → public + DM
- Streak hits a STREAK_BONUS_POINTS threshold → DM + public
- First assessment submitted (week_number 1) → DM
- Completion rate ≥90% for a full week → DM

**Design:** a library of varied celebration messages (not the same
template every time). Randomly select from 3-5 variants per milestone
type. Arabic-first, warm, specific to what they achieved.

## Component 6 — Weekly Progress Summary (Friday 8 PM)

**Trigger:** `@tasks.loop` on Friday at 20:00 (or replaces the existing
`monday_progress_report` — same idea, richer content, better timing).

**Content:**
- This week's completion rate (visual bar) vs. last week
- Strongest task type (most submitted) and weakest (least submitted)
- Specific encouragement based on tier:
  - ≥80%: "أداء ممتاز! استمر"
  - 60-79%: "كويس! حاول تزود مهمة واحدة يوميًا"
  - 40-59%: "محتاج تلتزم أكتر — حتى 3 مهام يوميًا كافية"
  - <40%: "الأسبوع ده كان صعب. هل محتاج مساعدة؟ كلمنا في #support"

## Component 7 — Absence Recovery Ladder

**Trigger:** checked daily (inside the existing `streak_update` hourly
loop, or a dedicated daily loop).

**New table column or setting:** track which escalation level was last
sent to each member, to avoid repeating the same level.

**Ladder:**
| Days missed | Action | Who acts |
|---|---|---|
| 2 | Bot DM: gentle "مفتقدينك" | Bot |
| 3 | Buddy prompt: "ابعتله صوتية" | Buddy (via DM) |
| 5 | Bot DM: "comeback mini-task" (one easy thing) | Bot |
| 7+ | Already in !attention; bot sends final DM | Bot + Admin |

**Design:** each step is logged in `notification_log` with a type like
`absence_day2`, `absence_day3`, etc. The check only sends if that
specific level hasn't been sent for this current absence streak (not
ever — if they come back and disappear again, the ladder restarts).

## Component 8 — Notification Log (prevent duplicates + analytics)

**New table:**
```sql
CREATE TABLE IF NOT EXISTS notification_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    notification_type TEXT NOT NULL,  -- morning_dm, evening_dm, streak_alert, etc.
    sent_at         TEXT NOT NULL DEFAULT (datetime('now')),
    date            TEXT NOT NULL,    -- the day this notification is about
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_notif_log ON notification_log(discord_id, notification_type, date);
```

Every notification sent gets logged here. Before sending, check:
"has this type already been sent to this member for this date?" If yes,
skip. This prevents double-sends from retries, bot restarts, or
overlapping loop executions.

Also useful for analytics: "how many students got the streak-at-risk
alert this week?" → informs whether the daily task timing is right.

## Component 9 — Social Proof (opt-in)

**Trigger:** called from `process_submission()` when someone completes
all 7 tasks.

**Logic:** for each member at the SAME level who has `social_proof=1`
in preferences AND hasn't completed all tasks today, send a brief nudge:
"زميلك {name} خلّص كل مهامه — يلا كمّل!"

**Rate limit:** max 1 social proof notification per member per day
(even if multiple peers finish). Use notification_log.

---

## Feature Flags

Each notification type has its own flag for gradual rollout:
- `nabd_morning` — morning kickstart
- `nabd_evening` — evening reminder
- `nabd_streak_alert` — streak-at-risk
- `nabd_celebrations` — milestone celebrations
- `nabd_weekly_summary` — Friday progress report
- `nabd_absence_recovery` — absence ladder
- `nabd_social_proof` — social proof nudges

---

## What this deliberately does NOT do

- No Telegram/email/push — Discord DM only (keeps it simple)
- No AI-generated messages — templates are predictable and fast
- No notification sounds/pings outside Discord's own DM behavior
- No public shaming — social proof is opt-in, never shows failures
- No notifications for admin/moderators (they use !attention instead)
