# Phase 1: Discord Server Build — Step-by-Step Execution Guide

**Time Required:** 45-60 minutes of focused work  
**What You Need:** Discord desktop app (or browser), logged into your account  
**Output:** Complete Empire English Community Discord server, ready for content

---

## STEP 1: Create the Server (2 minutes)

1. Open Discord → click **"+"** (Add a Server) on the left sidebar
2. Click **"Create My Own"**
3. Select **"For a club or community"**
4. Server Name: `Empire English Community`
5. Upload server icon (your Empire logo — black/gold)
6. Click **Create**

---

## STEP 2: Enable Community Features (3 minutes)

1. Server Settings → **Enable Community**
2. Follow the setup wizard:
   - Verification Level: **Medium** (must have verified email)
   - Set #rules as the rules channel
   - Set #announcements as the updates channel
3. Server Settings → **Overview**:
   - Description: `System-driven English learning — American accent from day one. 🏛️`
   - Default Notifications: **Only @mentions**

---

## STEP 3: Create Roles (10 minutes)

Go to Server Settings → **Roles** → Create each role in this EXACT order (top = highest):

| # | Click "Create Role" | Name | Color | Display Separately? |
|---|---------------------|------|-------|:-------------------:|
| 1 | First | `🏛️ Founder` | #D4AF37 (gold) | Yes |
| 2 | Second | `🛡️ Admin` | #E74C3C (red) | Yes |
| 3 | Third | `⚔️ Moderator` | #E67E22 (orange) | Yes |
| 4 | Fourth | `🌟 Ambassador` | #9B59B6 (purple) | Yes |
| 5 | Fifth | `👑 Level 3` | #C27C0E (dark gold) | Yes |
| 6 | Sixth | `🚀 Level 2` | #3498DB (blue) | Yes |
| 7 | Seventh | `💪 Level 1` | #2ECC71 (green) | Yes |
| 8 | Eighth | `🌱 Level 0` | #A8E6CF (light green) | Yes |
| 9 | Ninth | `🤖 Empire Bot` | #2C3E50 (dark grey) | No |

**After creating all roles:**
- Assign yourself the `🏛️ Founder` role
- Set `@everyone` → disable ALL permissions except "Read Message History" and "View Channels" (we'll control access per channel)

---

## STEP 4: Create Categories & Channels (20 minutes)

**Right-click on the server name → Create Category** for each. Then right-click each category → **Create Channel** for the channels listed.

### Category 1: `📋 WELCOME`

| Create Channel | Type | Read-Only? |
|---------------|------|:----------:|
| `welcome` | Text | Yes (only Admin can write) |
| `rules` | Text | Yes |
| `roles-info` | Text | Yes |
| `announcements` | Text | Yes (Admin + Mod can write) |

**Permissions for this category:** @everyone → View: ✅, Send Messages: ❌

### Category 2: `⚙️ SYSTEM`

| Create Channel | Type | Notes |
|---------------|------|-------|
| `bot-commands` | Text | All members can write |
| `leaderboard` | Text | Read-only (bot writes) |
| `support` | Text | All members can write |
| `suggestions` | Text | All members can write |

**Permissions:** @everyone → View: ❌. Level 0, 1, 2, 3, Ambassador, Mod, Admin → View: ✅, Send: ✅. Leaderboard: only Bot + Admin can send.

### Category 3: `🌱 LEVEL 0 ZONE`

| Create Channel | Type | Notes |
|---------------|------|-------|
| `l0-daily-tasks` | Text | Bot posts tasks; L0 members reply |
| `l0-text-practice` | Text | Written exercises |
| `l0-voice-1` | Voice | Structured practice |
| `l0-voice-2` | Voice | Open / buddy sessions |
| `l0-questions` | Text | Arabic clarification allowed |
| `l0-showcase` | Text | Recording submissions + celebrations |

**Permissions:** @everyone → View: ❌. `🌱 Level 0` + `💪 Level 1` → View: ✅, Send: ✅, Connect/Speak: ✅. `🚀 Level 2` + `👑 Level 3` → View: ✅, Send: ❌, Connect: ❌.

### Category 4: `💪 LEVEL 1 ZONE`

| Create Channel | Type |
|---------------|------|
| `l1-daily-tasks` | Text |
| `l1-text-practice` | Text |
| `l1-voice-1` | Voice |
| `l1-voice-2` | Voice |
| `l1-questions` | Text |
| `l1-showcase` | Text |

**Permissions:** @everyone → View: ❌. `💪 Level 1` + `🚀 Level 2` → View: ✅, Send: ✅, Connect: ✅. `👑 Level 3` → View: ✅, Send: ❌. `🌱 Level 0` → View: ❌.

### Category 5: `🚀 LEVEL 2 ZONE`

| Create Channel | Type |
|---------------|------|
| `l2-daily-tasks` | Text |
| `l2-text-practice` | Text |
| `l2-voice-1` | Voice |
| `l2-voice-2` | Voice |
| `l2-debate` | Voice |
| `l2-questions` | Text |
| `l2-showcase` | Text |

**Permissions:** @everyone → View: ❌. `🚀 Level 2` + `👑 Level 3` → View: ✅, Send: ✅, Connect: ✅. Everyone else: ❌.

### Category 6: `👑 LEVEL 3 ZONE`

| Create Channel | Type |
|---------------|------|
| `l3-daily-tasks` | Text |
| `l3-text-practice` | Text |
| `l3-voice-1` | Voice |
| `l3-voice-2` | Voice |
| `l3-debate` | Voice |
| `l3-mentorship` | Text |
| `l3-showcase` | Text |

**Permissions:** @everyone → View: ❌. `👑 Level 3` only → View: ✅, Send: ✅, Connect: ✅.

### Category 7: `🌍 COMMUNITY`

| Create Channel | Type |
|---------------|------|
| `general-chat` | Text |
| `introductions` | Text |
| `voice-lounge` | Voice |
| `events` | Text |
| `daily-word` | Text |

**Permissions:** All Level roles → View: ✅, Send: ✅, Connect: ✅. @everyone → View: ❌.

### Category 8: `📊 ACCOUNTABILITY`

| Create Channel | Type |
|---------------|------|
| `daily-check-in` | Text |
| `streak-tracker` | Text (read-only for members, bot writes) |
| `weekly-goals` | Text |

**Permissions:** All Level roles → View: ✅, Send: ✅. Streak-tracker: only Bot can send.

### Category 9: `📚 RESOURCES`

| Create Channel | Type |
|---------------|------|
| `cheat-sheets` | Text |
| `video-library` | Text |
| `podcast-recs` | Text |
| `book-club` | Text |

**Permissions:** All Level roles → View: ✅, Send: ✅.

### Category 10: `💬 FEEDBACK`

| Create Channel | Type |
|---------------|------|
| `speaking-feedback` | Text |
| `writing-feedback` | Text |
| `accent-feedback` | Text |
| `grammar-qa` | Text |

**Permissions:** All Level roles → View: ✅, Send: ✅.

### Category 11: `🔒 ADMIN` (hidden)

| Create Channel | Type |
|---------------|------|
| `admin-chat` | Text |
| `mod-actions` | Text |
| `member-notes` | Text |
| `bot-logs` | Text |

**Permissions:** @everyone → View: ❌. Only Admin + Mod roles can view/send.

---

## STEP 5: Create Discord Webhooks (5 minutes)

For automated content delivery from n8n, create a webhook for each channel that will receive bot-posted content:

1. Go to each channel listed below → **Edit Channel** → **Integrations** → **Webhooks** → **New Webhook**
2. Name it "Empire Bot" and optionally set an avatar
3. **Copy the Webhook URL** — save it (you'll give these to me)

| Channel | Webhook Name | Purpose |
|---------|-------------|---------|
| `#l0-daily-tasks` | Empire Bot - L0 Tasks | Daily task delivery |
| `#l1-daily-tasks` | Empire Bot - L1 Tasks | Daily task delivery |
| `#l2-daily-tasks` | Empire Bot - L2 Tasks | Daily task delivery |
| `#l3-daily-tasks` | Empire Bot - L3 Tasks | Daily task delivery |
| `#cheat-sheets` | Empire Bot - Resources | Weekly vocab + grammar cards |
| `#leaderboard` | Empire Bot - Leaderboard | Streak/score updates |
| `#streak-tracker` | Empire Bot - Streaks | Daily streak updates |
| `#daily-word` | Empire Bot - Daily Word | Word of the day |
| `#announcements` | Empire Bot - Announcements | System announcements |

**Save all 9 webhook URLs** — you'll share them with me so I can configure the n8n workflows.

---

## STEP 6: Post Welcome Content (5 minutes)

### In `#welcome` (post this message):

```
🏛️ Welcome to Empire English Community

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The Empire English System is NOT a course.
It is a Learning Operating System.

✅ American accent training from Day 1
✅ 7 daily tasks (45-75 min for Core track)
✅ Weekly assessments with real scores
✅ AI-powered feedback on every submission
✅ Community voice lounges for real practice
✅ Level advancement through demonstrated competency

YOUR JOURNEY:
🌱 Level 0: Absolute Beginner (8-12 weeks)
💪 Level 1: Survival English (10-14 weeks)
🚀 Level 2: Communication (12-16 weeks)
👑 Level 3: Fluency & Native Accent (ongoing mastery)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 START HERE:
1. Read #rules
2. Accept the rules (click the checkmark below)
3. Check #roles-info to understand how levels work
4. Your onboarding buddy will contact you within 12 hours

🏛️ System over instructor. Execution over theory.
Common sense first.
```

### In `#rules` (post the full rules — from the implementation plan §1.5)

### In `#roles-info` (post this):

```
🏛️ HOW LEVELS WORK

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Every member starts at their placement level.
You advance ONLY by passing the Level Exit Exam.
No shortcuts. No exceptions. The system works because the standards are real.

🌱 LEVEL 0 — Absolute Beginner
• 0-500 words
• Learn all 44 English sounds
• Goal: 60-second self-introduction
• Duration: 8-12 weeks

💪 LEVEL 1 — Survival English
• 500-1,500 words
• Handle daily conversations
• Goal: 2-minute unscripted monologue
• Duration: 10-14 weeks

🚀 LEVEL 2 — Communication
• 1,500-3,000 words
• Discuss complex topics
• Goal: 5-minute presentation on any topic
• Duration: 12-16 weeks

👑 LEVEL 3 — Fluency & Native Accent
• 3,000-5,000+ words
• Native-like flow and accent
• Ongoing mastery with quarterly certification
• Duration: Lifetime membership

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 HOW TO ADVANCE:
1. Complete daily tasks consistently (7/day)
2. Score well on weekly assessments (Sunday)
3. When ready: request the Exit Exam
4. Pass ALL 5 sections → automatic level-up 🎉

No one advances without earning it.
That's what makes an Empire credential real.
```

---

## STEP 7: Final Verification (5 minutes)

Test with a second Discord account (or ask a friend):

- [ ] Join the server → see only WELCOME channels
- [ ] After accepting rules screening → still only WELCOME
- [ ] Manually assign `🌱 Level 0` role to the test account
- [ ] Verify: can now see Level 0 Zone + Community + Accountability + Resources + Feedback + System
- [ ] Verify: CANNOT see Level 1/2/3 zones
- [ ] Verify: CAN see voice channels in Level 0 Zone and Community
- [ ] Verify: CANNOT write in `#welcome`, `#rules`, `#roles-info`, `#announcements`, `#leaderboard`, `#streak-tracker`
- [ ] Verify: CAN write in `#l0-text-practice`, `#l0-showcase`, `#daily-check-in`, `#general-chat`
- [ ] Remove the test role → confirm access reverts to WELCOME only

---

## STEP 8: Give Me the Webhook URLs

After completing all steps above, send me:
1. The 9 Discord webhook URLs (from Step 5)
2. The Discord server invite link (Server Settings → Invites → Create one that never expires)
3. Confirmation that the verification test (Step 7) passed

I will then:
- Configure the n8n daily task delivery workflows
- Connect the leaderboard + streak tracker
- Set up the weekly assessment delivery
- Build the full AI engine pipeline into Discord

---

## Checklist Summary

| Step | Task | Time | Done? |
|------|------|:----:|:-----:|
| 1 | Create server | 2 min | ☐ |
| 2 | Enable Community features | 3 min | ☐ |
| 3 | Create 9 roles (exact order + colors) | 10 min | ☐ |
| 4 | Create 11 categories + 42 channels | 20 min | ☐ |
| 5 | Create 9 webhooks + save URLs | 5 min | ☐ |
| 6 | Post welcome/rules/roles content | 5 min | ☐ |
| 7 | Test with alternate account | 5 min | ☐ |
| 8 | Share webhook URLs + invite link with me | 1 min | ☐ |

**Total: ~50 minutes of focused Discord setup.**

---

*After you complete this, Phase 1 is done and I begin building the n8n workflows for Phase 3 (AI task delivery + evaluation) immediately.*
