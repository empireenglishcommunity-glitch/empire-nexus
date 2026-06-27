# Phase 0 — Build Kit

**Build assets v1.0** · implements `../PHASE_0_IMPLEMENTATION_SPEC.md` + `../PHASE_0_CONTENT_ASSETS.md`

> **What this folder is.** Everything needed to *assemble* the Phase 0 capture spine with minimal thinking — importable CRM sheets, the bilingual bot copy as data, the Config template, the quiz scoring logic, and click-by-click runbooks for Make.com and BotFather. Follow the build order below.

> **Decisions baked in:** Telegram bot → Discord · Make.com orchestrator (n8n fallback) · Google Sheets CRM · Cal.com booking · Arabic-led MSA (fresh/conversational) · **no public prices day one** (pricing via call/DM).

---

## 📁 Files in this kit

| File | Purpose | You do |
|---|---|---|
| `crm/subscribers.csv` | Subscribers tab headers (import) | Import to Google Sheets |
| `crm/events.csv` | Events tab headers (import) | Import to Google Sheets |
| `crm/config.csv` | Config tab — knobs, weights, thresholds, links | Import + fill your links |
| `crm/string_table.csv` | All bot copy, `key,ar,en` (import) | Import to Google Sheets |
| `quiz-logic.md` | Quiz questions → points → level mapping + edge rule | Reference while building A2 |
| `make-scenarios.md` | Make.com scenarios A1–A9, module-by-module | Build in Make.com |
| `botfather-setup.md` | Bot creation, commands, menu, deep link | Do in Telegram |

---

## 🧭 Build order (do in this sequence)

> Mirrors spec §12. Each step is testable before the next depends on it.

1. **Accounts** — create them (see `botfather-setup.md` §1 + spec §3): Telegram bot, dedicated Google account, Make.com, Cal.com, MailerLite/Brevo (account only).
2. **Google Sheet** — create one spreadsheet named `Empire CRM`; import the 4 CSVs as 4 tabs (`Subscribers`, `Events`, `Config`, `String_Table`). See §"Importing the CSVs" below.
3. **BotFather** — create the bot, set commands + menu button (`botfather-setup.md`).
4. **Cal.com** — create the "Free Level & Roadmap Call" event; copy its link into Config.
5. **Make.com scenarios** — build A1 → A9 in order (`make-scenarios.md`), testing each.
6. **Fill Config** — paste your real links (bot, Cal.com, Discord, group, resource) into the `Config` tab.
7. **Produce + link assets** (parallel) — record 3 audio clips + make the PDF (Content Asset 5), upload, paste URL into Config `RESOURCE_LINK`. Until ready, bot serves PDF text and marks audio "coming soon."
8. **End-to-end dry run** — run the acceptance tests below.

---

## 📥 Importing the CSVs into Google Sheets

1. Create a new Google Sheet → name it **`Empire CRM`**.
2. For each CSV: **File → Import → Upload**, choose the file, select **"Insert new sheet(s)"**, and set separator to **Comma**. Keep **"Convert text to numbers/dates" OFF** for `String_Table` (preserves Arabic/leading symbols).
3. Rename each imported tab to match: `Subscribers`, `Events`, `Config`, `String_Table`.
4. In `Subscribers`, after import, add the formula columns for `lead_score` and `segment` (see `quiz-logic.md` §"Lead score & segment formulas").
5. Add the **plan templates** (`plan_l0`–`plan_l3`) and **level-name** keys to the `String_Table` tab — full bilingual text is in `quiz-logic.md` §2–§3 (kept there because they're the quiz's output).

> **Encoding:** the CSVs are UTF-8. Arabic will render correctly. If a cell shows mojibake, re-import and ensure UTF-8.

---

## 🔐 Secrets — where they go (and don't)

| Secret | Lives in | NEVER in |
|---|---|---|
| Telegram bot token | Make.com connection (credential store) | the Sheet, this repo, chat |
| Google/Make/Cal.com auth | Each tool's own connection | anywhere in the repo |

The repo and the Sheet hold **config and copy only** — never tokens.

---

## ✅ Acceptance tests (Definition of Done — from spec §13)

Run each as a real user on a test Telegram account. Phase 0 ships only when all pass.

| ID | Test | Pass condition |
|---|---|---|
| T1 | New user `/start` | Bilingual welcome + 5-button menu; CRM row created (status New); `JOINED_BOT` logged |
| T2 | Complete quiz | Provisional level returned; correct plan template with echoed goal/track |
| T3 | CRM write | Row has telegram_id, level, score, goal, track, language, timestamps |
| T4 | Consent | "No" still delivers value, consent=FALSE; "Yes" sets consent=TRUE + consent_at |
| T5 | Booking | Cal.com opens prefilled; after booking → booked=TRUE, status=Hot, `BOOKED` logged, founder alerted |
| T6 | Resource | "3 American Sounds" delivered; `RESOURCE_CLAIMED` logged |
| T7 | Events | All 6 event types appear with timestamps |
| T8 | Score/segment | lead_score + segment update after actions; crossing 80 → Hot + alert |
| T9 | Backup | Dated backup of Subscribers + Events exists after daily run |
| T10 | Idempotency | Re-sending `/start` or retrying a scenario does NOT duplicate rows/events or double-message |

> When all 10 pass → **Gate 0→1 is open** (see `../../02-strategy/MASTER_IMPLEMENTATION_ROADMAP.md` §9). Only then begin Phase 1.

---

## 🆘 If you get stuck

- Make.com free-tier ops limit hit → see spec §14 (batch writes; n8n self-host fallback).
- Arabic shows reversed/odd → store ar and en in separate columns (already done); test emoji placement on-device.
- Booking not matching CRM → confirm the Cal.com link carries `?src=bot&tid={telegram_id}` (botfather/Cal step).
