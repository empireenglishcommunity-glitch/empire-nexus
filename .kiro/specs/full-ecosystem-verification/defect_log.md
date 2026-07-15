# Hisn Defect Log

Running log of every issue found during the Hisn verification campaign.
Severity: **Blocker** (breaks core flow) / **Major** (works but wrong/
confusing) / **Minor** (cosmetic/edge-case) / **Info** (observation only).

---

## D001 — LEVEL 2 category had corrupted emoji (Major)

**Found during:** H0.5 (live Ghost Testing verification, discovered
incidentally while listing categories)
**Severity:** Major — the category was fully functional (correct
channels, correct permissions), but displayed `→` instead of `🚀`,
which would look broken/unprofessional to real students on day 1.
**Root cause:** Unknown — likely a partial/interrupted `setup_server.py`
run or a manual Discord UI edit that mangled the multi-byte emoji
during encoding. Confirmed via raw UTF-8 hex byte inspection (not
terminal rendering) that the live data itself contained `e28692`
(→ U+2192 RIGHTWARDS ARROW) instead of the intended `f09f9a80` (🚀
U+1F680 ROCKET).
**Fix:** Renamed the category via Discord API `PATCH` to the correct
name `🚀 المستوى 2 | LEVEL 2`. Channels and permissions were untouched
(rename only affects the category's `name` field).
**Verified:** Re-queried the category post-fix; API returned the
corrected name, and its 7 channels (`l2-daily-tasks`, `l2-voice-1`,
etc.) were confirmed still attached and unaffected.
**Status:** ✅ Resolved (2026-07-15)

---

## D002 — Duplicate empty LEVEL 2 category (Major)

**Found during:** H0.5, same investigation as D001
**Severity:** Major — a second category also named "LEVEL 2" (with the
CORRECT emoji, ironically) existed simultaneously, completely empty
(0 channels). Confusing for admins, and a sign the server's category
structure had drifted from `setup_server.py`'s intended one-category-
per-level design.
**Root cause:** Likely created by an earlier, separate run of
`setup_server.py` (or a manual re-creation attempt) that didn't detect
the existing category correctly, so it created a new one instead of
reusing/fixing the old one.
**Fix:** Confirmed the duplicate had zero child channels (checked
twice, immediately before deletion, to guard against a race with any
other process). Deleted the category via Discord API `DELETE`.
**Verified:** Post-fix category list shows exactly one "LEVEL 2"
category, with the correct emoji and all 7 real channels attached.
**Status:** ✅ Resolved (2026-07-15)

---

## D003 — ACCOUNTABILITY and RESOURCES categories had corrupted emoji (Major)

**Found during:** H0.5, same investigation as D001/D002
**Severity:** Major — same class of bug as D001: functional but
displaying `▪` (U+25AA BLACK SMALL SQUARE) instead of the intended
`📊` (ACCOUNTABILITY) and `📚` (RESOURCES).
**Root cause:** Same likely cause as D001 (encoding corruption during
setup or manual edit) — both categories showed the identical `▪`
character, suggesting a shared root cause rather than two independent
typos.
**Fix:** Renamed both categories via Discord API `PATCH` to
`📊 المتابعة | ACCOUNTABILITY` and `📚 المصادر | RESOURCES`. Channels
and permissions untouched.
**Verified:** Re-queried both post-fix; API returned corrected names,
channel counts unchanged (3 and 4 respectively).
**Status:** ✅ Resolved (2026-07-15)

---

## D004 — Leftover default "Text Channels" / "Voice Channels" categories (Minor)

**Found during:** H0.5, same investigation
**Severity:** Minor — cosmetic clutter, not referenced anywhere in
`setup_server.py`'s intended design, contained only Discord's
auto-created defaults (`general` text channel, `General` voice
channel) with no real content or purpose.
**Root cause:** Discord automatically creates these on server
creation; they were simply never cleaned up.
**Fix:** Deleted both child channels first (`general`, `General`),
then both now-empty parent categories, via Discord API `DELETE`.
**Verified:** Post-fix category list no longer contains either
default category; total category count matches `setup_server.py`'s
12 intended categories exactly (WELCOME, SYSTEM, LEVEL 0-3, COMMUNITY,
ACCOUNTABILITY, RESOURCES, FEEDBACK, ADMIN, Ghost Testing).
**Status:** ✅ Resolved (2026-07-15)

---

## D005 — Database already contains 4 real member rows (Info)

**Found during:** H0.3 (backup verification)
**Severity:** Info — not a bug, just a planning assumption to correct.
H0's original assumption was an empty database (0 real students,
since none have been invited yet). The backup verification query
showed 4 existing rows: `BioRoMa`, `Mai Mohamed`, `M.A.C.A.L EMPIRE`,
`Empire Ghost` — likely early testers/the owner's own accounts from
prior sessions' ghost-bot work, not real invited students.
**Impact on Hisn campaign:** None — verified these 4 real (17-19 digit)
Discord snowflake IDs do NOT match the `GHOST_TEST_` synthetic-ID
cleanup pattern (9-digit IDs starting with '9'), so H0.6's cleanup SQL
remains safe and will never touch these rows.
**Action:** None required for Hisn. Noted here for awareness only.
**Status:** ℹ️ No action needed



---

## D006 — WELCOME category's `دليل-القنوات` channel missing from setup_server.py (Minor)

**Found during:** H1.6 (channel audit) — live query returned 6 channels
in WELCOME, but `setup_server.py`'s config only defines 5.
**Severity:** Minor — the channel itself works fine and is actively
used (confirmed real content: a full Arabic channel-guide message
posted by the bot, and `features.py`'s `ARABIC_ALLOWED_CHANNELS`
explicitly references it by name). The gap is purely in
`setup_server.py` not being a complete, accurate source of truth —
re-running the script against a fresh server would silently omit this
channel even though the rest of the codebase depends on it existing.
**Root cause:** The channel was likely added manually (or via a
one-off script, per the `fix_all_permissions.py` precedent already
noted elsewhere in `setup_server.py`'s comments) directly against the
live server, and `setup_server.py` was never updated to match.
**Fix:** Added the channel definition to `setup_server.py`'s WELCOME
category, matching its live topic exactly (`🗺️ خريطة كاملة لكل قنوات
السيرفر بالعربي`).
**Verified:** Re-ran `generate_test_matrix.py` post-fix — channel count
increased from 59 to 60, matching the live server's actual channel
count exactly.
**Status:** ✅ Resolved (2026-07-15)

---

## D007 — Two "unmapped role" overwrites investigated, found to be correct (Info, no action)

**Found during:** H1.6, while cross-referencing category permission
overwrites against the guild's role list.
**Severity:** Info only — both turned out to be correct, not bugs.
1. Ghost Testing category's overwrite for ID `1519795406656110857`
   didn't match any role in the guild's role list. Investigated via
   the raw overwrite's `type` field (`type: 1` = member, not `type: 0`
   = role) and a direct member lookup — resolved to the bot's OWN user
   account (`Empire English Bot`), which needs a direct member-level
   grant to post/respond in Ghost Testing regardless of role. Correct
   by design.
2. Manual eyeball count of "61 live channels" vs. the generator's "60"
   was a counting error on my part (mis-reading a role-overwrite log
   line as if it were a channel line), not an actual discrepancy —
   both numbers were 60 once re-checked carefully.
**Action:** None required. Logged for completeness, since a full
verification pass should record what was checked and cleared, not
just what was broken.
**Status:** ℹ️ No action needed
