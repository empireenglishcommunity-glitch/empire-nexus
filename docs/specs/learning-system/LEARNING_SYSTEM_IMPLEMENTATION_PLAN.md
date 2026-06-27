# Empire English — Learning System Implementation Plan

**Document Type:** Complete Build Specification  
**Date:** June 25, 2026  
**Scope:** Build the entire Empire English Community Learning System from the blueprint  
**Source:** `01-foundation/Empire English Community Learning System.md` (1,035 lines, 14 sections)  
**Goal:** Transform the design blueprint into a working, pilot-ready educational operating system

---

## Document Overview

This plan translates the complete Learning System blueprint into executable build phases. Each phase has:
- **Objectives** — what gets built
- **Detailed Tasks** — specific, actionable items
- **Deliverables** — concrete outputs
- **Dependencies** — what must exist before this phase starts
- **Completion Criteria** — how we know it's done
- **Estimated Effort** — realistic time for a solo operator

### Build Phases (Dependency Order)

```
PHASE 1: Discord Server Build (the container)
    ↓
PHASE 2: Level 0 Curriculum (the content)
    ↓
PHASE 3: AI Engine Deployment (the automation)
    ↓
PHASE 4: Evaluation & Tracking (the measurement)
    ↓
PHASE 5: Onboarding & Pilot Launch (the first 10 members)
    ↓
PHASE 6: Operations & Governance (the sustainability)
```

### Timeline Summary

| Phase | Duration | Can Parallel? |
|-------|----------|:-------------:|
| Phase 1 | 1 day | No — everything depends on this |
| Phase 2 | 2-3 weeks | No — needs Discord channels |
| Phase 3 | 3-4 days | Partial — can start during Phase 2 Week 2 |
| Phase 4 | 2-3 days | Partial — can start during Phase 2 Week 3 |
| Phase 5 | 1 week (prep) + 8 weeks (pilot) | No — needs Phases 1-4 |
| Phase 6 | Ongoing from pilot start | Parallel with Phase 5 |

**Total to Pilot Launch:** ~4-5 weeks of focused build, then 8-week pilot

---


## PHASE 1: Discord Server Build

**Objective:** Create the complete Discord server that serves as the 24/7 learning environment — all channels, roles, permissions, and the bot foundation.

**Duration:** 1 focused day  
**Dependencies:** None — this is the foundation  
**Output:** A fully structured Discord server ready to receive content and members

---

### 1.1 Server Creation & Settings

| Setting | Value |
|---------|-------|
| Server Name | Empire English Community |
| Server Icon | Empire logo (black + gold) |
| Server Banner | Brand banner image |
| Verification Level | Medium (must have verified email + 5 min on server) |
| Default Notification | Only @mentions |
| Community Features | Enable Community Server (unlocks discovery, welcome screen) |
| Welcome Screen | Enable with custom message + channel highlights |
| Rules Screening | Enable (members must accept rules before posting) |
| Language | English (primary) |

---

### 1.2 Role Hierarchy (Create in This Order — Top to Bottom)

| # | Role Name | Color | Purpose | Hoisted? | Mentionable? |
|---|-----------|-------|---------|:--------:|:------------:|
| 1 | 🏛️ Founder | Gold (#D4AF37) | Server owner | Yes | Yes |
| 2 | 🛡️ Admin | Red (#E74C3C) | Full server management | Yes | Yes |
| 3 | ⚔️ Moderator | Orange (#E67E22) | Channel moderation, member management | Yes | Yes |
| 4 | 🌟 Ambassador | Purple (#9B59B6) | Volunteer mentors (Level 2-3 members who help others) | Yes | Yes |
| 5 | 👑 Level 3 | Dark Gold (#C27C0E) | Fluency & Native Accent stage | Yes | No |
| 6 | 🚀 Level 2 | Blue (#3498DB) | Communication stage | Yes | No |
| 7 | 💪 Level 1 | Green (#2ECC71) | Survival English stage | Yes | No |
| 8 | 🌱 Level 0 | Light Green (#A8E6CF) | Absolute Beginner stage | Yes | No |
| 9 | 🤖 Empire Bot | Dark Grey (#2C3E50) | Bot role (above member roles for permissions) | No | No |
| 10 | @everyone | — | Default (no channel access except WELCOME) | — | — |

**Permission Principles:**
- `@everyone` can see WELCOME category only — everything else is locked
- Level roles grant access to their zone + lower zones (L2 can see L1 + L0)
- Ambassador/Moderator can access all level zones
- Voice channels require the matching level role
- Bot role needs: Manage Messages, Manage Roles, Send Messages, Embed Links, Attach Files, Read Message History, Add Reactions, Connect, Speak

---

### 1.3 Channel Structure (Create Categories + Channels)

#### Category 1: WELCOME (visible to @everyone)

| Channel | Type | Purpose | Permissions |
|---------|------|---------|-------------|
| #welcome | Text (read-only) | Auto-welcome message, server overview | Everyone: Read. Admin: Write |
| #rules | Text (read-only) | Community rules + English-only policy | Everyone: Read. Admin: Write |
| #roles | Text (read-only) | Role explanation + how levels work | Everyone: Read. Admin: Write |
| #announcements | Text (read-only) | Important updates, events, milestones | Everyone: Read. Admin/Mod: Write |

#### Category 2: SYSTEM

| Channel | Type | Purpose | Permissions |
|---------|------|---------|-------------|
| #bot-commands | Text | Interact with Empire Bot (check tasks, scores, streaks) | All members: R/W |
| #leaderboard | Text (read-only) | Auto-updated leaderboards (effort + improvement-based) | All members: Read. Bot: Write |
| #support | Text | Technical help, questions about the system | All members: R/W |
| #suggestions | Text | Feature requests, feedback | All members: R/W |

#### Category 3: LEVEL 0 ZONE

| Channel | Type | Purpose | Permissions |
|---------|------|---------|-------------|
| #l0-text-practice | Text | Written practice, sentence exercises | L0, L1: R/W. L2, L3: Read only |
| #l0-voice-1 | Voice | Structured voice practice (small groups) | L0, L1: Connect/Speak |
| #l0-voice-2 | Voice | Open practice / buddy sessions | L0, L1: Connect/Speak |
| #l0-questions | Text | Ask questions (Arabic allowed for 1-sentence clarification) | L0, L1, L2, L3: R/W |
| #l0-showcase | Text | Share recordings, celebrate progress | L0, L1: R/W. L2, L3: Read |
| #l0-daily-tasks | Text | Daily task delivery + submission (bot-managed) | L0: R/W. Bot: Write |

#### Category 4: LEVEL 1 ZONE

| Channel | Type | Purpose | Permissions |
|---------|------|---------|-------------|
| #l1-text-practice | Text | Written practice, paragraph exercises | L1, L2: R/W. L3: Read |
| #l1-voice-1 | Voice | Structured voice practice | L1, L2: Connect/Speak |
| #l1-voice-2 | Voice | Open practice / scenario role-plays | L1, L2: Connect/Speak |
| #l1-questions | Text | Questions about L1 content | L1, L2, L3: R/W |
| #l1-showcase | Text | Share progress recordings | L1, L2: R/W. L3: Read |
| #l1-daily-tasks | Text | Daily task delivery + submission | L1: R/W. Bot: Write |

#### Category 5: LEVEL 2 ZONE

| Channel | Type | Purpose | Permissions |
|---------|------|---------|-------------|
| #l2-text-practice | Text | Written practice, essays, opinions | L2, L3: R/W |
| #l2-voice-1 | Voice | Structured discussions | L2, L3: Connect/Speak |
| #l2-voice-2 | Voice | Debate preparation / practice | L2, L3: Connect/Speak |
| #l2-debate | Voice + Text | Structured debate sessions | L2, L3: Connect/Speak + R/W |
| #l2-questions | Text | Questions about L2 content | L2, L3: R/W |
| #l2-showcase | Text | Share essays, presentations | L2, L3: R/W |
| #l2-daily-tasks | Text | Daily task delivery + submission | L2: R/W. Bot: Write |

#### Category 6: LEVEL 3 ZONE

| Channel | Type | Purpose | Permissions |
|---------|------|---------|-------------|
| #l3-text-practice | Text | Advanced writing, style exercises | L3: R/W |
| #l3-voice-1 | Voice | Advanced discussions | L3: Connect/Speak |
| #l3-voice-2 | Voice | Presentation practice | L3: Connect/Speak |
| #l3-debate | Voice + Text | Advanced debates | L3: Connect/Speak + R/W |
| #l3-mentorship | Text | Mentor lower levels, share techniques | L3, Ambassador: R/W |
| #l3-showcase | Text | Share advanced work | L3: R/W |
| #l3-daily-tasks | Text | Daily task delivery + submission | L3: R/W. Bot: Write |

#### Category 7: COMMUNITY (all members)

| Channel | Type | Purpose | Permissions |
|---------|------|---------|-------------|
| #general-chat | Text | Off-topic English conversation | All members: R/W |
| #introductions | Text | New members introduce themselves | All members: R/W |
| #voice-lounge-open | Voice | Unstructured English chat (any level) | All members: Connect/Speak |
| #events | Text | Upcoming events, voice sessions, challenges | All members: R/W. Mod: Manage |
| #daily-word | Text | Word of the day (bot posts, members use in sentences) | All members: R/W. Bot: Write |

#### Category 8: ACCOUNTABILITY

| Channel | Type | Purpose | Permissions |
|---------|------|---------|-------------|
| #daily-check-in | Text | Morning: plan tasks. Evening: report completion. | All members: R/W |
| #streak-tracker | Text (read-only) | Bot-updated streak counts and milestones | All: Read. Bot: Write |
| #missed-day-report | Text | Members explain missed days (supportive, not punitive) | All members: R/W |
| #weekly-goals | Text | Set and review weekly goals every Monday | All members: R/W |

#### Category 9: RESOURCES

| Channel | Type | Purpose | Permissions |
|---------|------|---------|-------------|
| #cheat-sheets | Text | AI-generated and curated reference materials | All members: R/W. Bot: Write |
| #video-library | Text | Curated clips/movies/podcasts by level | All members: R/W. Mod: Pin |
| #podcast-recommendations | Text | Recommended listening by level | All members: R/W |
| #book-club | Text | Monthly reading recommendations + discussion | All members: R/W |

#### Category 10: FEEDBACK

| Channel | Type | Purpose | Permissions |
|---------|------|---------|-------------|
| #speaking-feedback | Text | Post recordings for peer/AI feedback | All members: R/W |
| #writing-feedback | Text | Submit writing for peer/AI correction | All members: R/W |
| #accent-feedback | Text | Post pronunciation clips for feedback | All members: R/W |
| #grammar-qa | Text | Grammar questions and answers | All members: R/W |

#### Category 11: ADMIN (hidden from members)

| Channel | Type | Purpose | Permissions |
|---------|------|---------|-------------|
| #admin-chat | Text | Private admin discussion | Admin, Mod only |
| #mod-actions | Text | Log of moderation actions | Admin, Mod only |
| #member-notes | Text | Notes on specific members (at-risk, flagged) | Admin, Mod only |
| #bot-logs | Text | Bot error logs, execution records | Admin only |

---

### 1.4 Bot Requirements (Empire Discord Bot)

The Discord bot is the operational backbone. It handles task delivery, scoring, streaks, leaderboards, and automated responses.

**Bot Platform Options (choose one):**

| Option | Cost | Complexity | Recommended? |
|--------|------|:----------:|:------------:|
| **Discord.js custom bot** (self-hosted on Hetzner) | $0 | High | For Phase 2+ |
| **Carl-bot** (free tier) | $0 | Low | Roles + auto-mod only |
| **MEE6** (free/premium) | $0-12/mo | Low | Leveling + auto-mod |
| **Custom n8n + Discord API** | $0 | Medium | Task delivery + CRM integration |

**Recommended for Pilot (Phase 1-2):** Use **Carl-bot** (free) for role management + auto-moderation + welcome messages. Use **n8n webhooks** for task delivery, scoring, and CRM integration (leveraging existing infrastructure). Build a custom Discord.js bot only if the pilot validates the system and scale demands it.

**Core Bot Functions (build incrementally):**

| Function | Priority | Method |
|----------|:--------:|--------|
| Welcome new members + assign base role | P1 | Carl-bot auto-role |
| Post daily tasks to #lX-daily-tasks channels | P1 | n8n scheduled workflow + Discord webhook |
| Accept task submissions (text/voice links) | P1 | n8n webhook listener |
| Track daily check-ins and streaks | P1 | n8n + Google Sheets |
| Post weekly assessment prompts (Sunday) | P2 | n8n scheduled |
| Update leaderboard | P2 | n8n + Discord embed |
| Enforce English-only (auto-detect + warn) | P3 | Custom bot or manual mod |
| Spaced repetition reminders | P3 | n8n scheduled |
| Progress dashboard commands (/progress, /streak, /level) | P2 | Discord slash commands via n8n |

---

### 1.5 Welcome Screen & Rules

**Welcome Screen (shown when members join):**

```
🏛️ Welcome to Empire English Community

A Learning Operating System — not a course.
System-driven. American accent from day one.
Community as classroom.

📋 Start here:
1. Read #rules
2. Accept the rules screening
3. Check #roles to understand levels
4. Wait for your placement (48-hour onboarding)

🎯 Your journey: Level 0 → Level 1 → Level 2 → Level 3
```

**Rules Message (pin in #rules):**

```
🏛️ EMPIRE ENGLISH — COMMUNITY RULES

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🗣️ RULE 1: English Only
All text and voice channels are English-only.
Exception: #l0-questions (one-sentence Arabic clarifications).
L0-L1: gentle reminders. L2+: enforcement applies.

📚 RULE 2: Complete Your Daily Tasks
The system works when YOU work it.
7 tasks daily. Check in morning. Report evening.
Consistency > perfection.

🤝 RULE 3: Support, Don't Judge
Everyone here started at zero.
Correct with kindness. Celebrate small wins.
Never mock pronunciation or mistakes.

🎙️ RULE 4: Voice Lounges
Mic required (camera optional).
Max 2 minutes continuous talking (let others speak).
10-minute minimum for it to count.
Stay on topic during structured sessions.

📝 RULE 5: Submissions & Feedback
Record and submit your speaking missions.
Give constructive feedback to others.
Accept feedback gracefully — it's how you grow.

🚫 RULE 6: Zero Tolerance
No harassment, hate speech, or bullying.
No spam, self-promotion, or off-topic flooding.
No sharing of private recordings without consent.
Violations → immediate mod review.

📈 RULE 7: Advancement
No skipping levels. No exceptions.
You advance when you demonstrate competency.
The exit exam is the only way up.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

By being here, you agree to these rules.
Questions? → #support
```

---

### 1.6 Phase 1 Completion Checklist

- [ ] Discord server created with correct name, icon, settings
- [ ] All 11 categories created
- [ ] All 40+ channels created with correct types (text/voice)
- [ ] All 10 roles created in correct hierarchy order
- [ ] Permissions set for every channel (matching the matrix in §1.3)
- [ ] Welcome screen configured
- [ ] Rules message pinned in #rules
- [ ] Rules screening enabled (members must accept before posting)
- [ ] Carl-bot (or equivalent) added for auto-role + welcome
- [ ] #welcome channel has the welcome message
- [ ] #roles channel explains the level system
- [ ] #announcements has a "Coming Soon" post
- [ ] Admin channels are properly hidden from regular members
- [ ] Test: create a test account, join, verify correct channel visibility per role
- [ ] Voice channels are accessible only to appropriate roles

**Phase 1 is complete when:** A new member joining sees only WELCOME channels, and upon receiving a level role, gains access to exactly the correct channels — no more, no less.

---


## PHASE 2: Level 0 Curriculum Build

**Objective:** Create the complete 8-12 week curriculum for Level 0 (Absolute Beginner) — the first content that real learners will use. This includes daily tasks, phoneme drills, vocabulary lists, speaking missions, shadowing materials, and writing exercises.

**Duration:** 2-3 weeks of focused content creation  
**Dependencies:** Phase 1 (Discord channels exist to organize content)  
**Output:** 56-84 days of complete, ready-to-deliver daily learning content

---

### 2.1 Level 0 Parameters (from Blueprint §2.1)

| Parameter | Value |
|-----------|-------|
| Target learner | Zero or near-zero English |
| Duration | 8-12 weeks (56-84 days) |
| Daily time (Core track) | 45-60 minutes |
| Daily time (Intensive track) | 1.5-2 hours |
| Vocabulary target | 500 high-frequency words |
| Grammar target | SVO order, present simple, basic questions |
| Pronunciation target | All 44 English phonemes at 80% accuracy |
| Speaking target | 60-second unscripted self-introduction |
| Advancement exam minimum | 70% overall |

---

### 2.2 Daily Task Structure (7 Tasks, Fixed Order)

Every day follows this identical structure. Only the specific content changes.

| # | Task | Duration (Core) | Duration (Intensive) | Channel |
|---|------|:--------------:|:-------------------:|---------|
| 1 | Accent/Phoneme Drill | 10 min | 20 min | #l0-daily-tasks |
| 2 | Vocabulary Acquisition | 10 min | 20 min | #l0-daily-tasks |
| 3 | Shadowing Practice | 10 min | 15 min | #l0-daily-tasks |
| 4 | Speaking Mission | 10 min | 20 min | #l0-showcase |
| 5 | Listening Exercise | 8 min | 15 min | #l0-daily-tasks |
| 6 | Writing Practice | 7 min | 15 min | #l0-text-practice |
| 7 | Community Participation | — (5 min) | 15 min | #l0-voice-1 or #general-chat |

**Core track total:** ~45-55 min/day  
**Intensive track total:** ~120 min/day

---

### 2.3 Phoneme Sequence (8-Week Build — from Blueprint §5.1)

Each week introduces a set of phonemes. By week 8, all 44 are covered.

| Week | Vowels Introduced | Consonants Introduced | Daily Drill Focus |
|------|-------------------|----------------------|-------------------|
| 1 | /iː/ (sheep), /ɪ/ (ship), /eɪ/ (say), /æ/ (cat) | /p/ /b/ /t/ /d/ /k/ /g/ (stops) | Minimal pairs: sheep/ship, cat/cut, pat/bat |
| 2 | /ɑː/ (father), /oʊ/ (go), /ʊ/ (book), /uː/ (food) | /f/ /v/ /s/ /z/ /θ/ /ð/ (fricatives) | th-sounds (think vs. this), f/v contrast |
| 3 | /ɜːr/ (bird), /ə/ (about), /ɛ/ (bed), /ʌ/ (cup) | /m/ /n/ /ŋ/ (sing), /h/ /w/ /j/ (nasals + glides) | The schwa — most common sound |
| 4 | Diphthongs: /aɪ/ (my), /aʊ/ (how), /ɔɪ/ (boy) | /tʃ/ (chair), /dʒ/ (jump), /l/ /r/ (affricates + liquids) | R vs L contrast (critical for Arabic speakers) |
| 5 | R-colored vowels: /ɪr/ (here), /ɛr/ (hair), /ɑːr/ (car) | Review + combinations | American R (retroflex) practice |
| 6 | Review all vowels in context | Review all consonants in context | Word-level production (not isolated) |
| 7 | Vowel reduction patterns (unstressed → schwa) | Consonant clusters (initial: str-, spl-, thr-) | Multi-syllable words with correct stress |
| 8 | All 44 phonemes in sentence context | Consonant clusters (final: -nds, -lps, -sks) | Connected speech (basic) |

**Daily Phoneme Drill Protocol (10-20 min):**
1. **Isolation (2 min):** Listen to model + produce the target phoneme(s) 10 times
2. **Minimal Pairs (3 min):** Distinguish + produce pairs (e.g., sheep/ship, bad/bed)
3. **Word Level (3 min):** 5 words containing the target sound — say each 3 times
4. **Sentence Level (3 min):** 2 sentences loaded with the target sound — read aloud
5. **Record & Compare (2 min):** Record yourself saying the sentence, compare to model

---

### 2.4 Vocabulary Plan (500 Words in 8-12 Weeks)

**Acquisition Rate:** 8-10 new words per day (Core: 8, Intensive: 10)

**Source:** First 500 words from a frequency-based list (e.g., New General Service List), organized into weekly themes.

| Week | Theme | Words (approx.) | Example Words |
|------|-------|:---------------:|---------------|
| 1 | Greetings & Self | 56 | hello, name, from, I, you, is, am, nice, meet, live |
| 2 | Numbers, Time, Days | 56 | one-twenty, morning, evening, today, tomorrow, yesterday |
| 3 | Family & People | 56 | mother, father, brother, sister, friend, teacher, man, woman |
| 4 | Home & Daily Life | 56 | house, room, bed, eat, drink, cook, clean, work, sleep |
| 5 | Food & Shopping | 56 | water, food, bread, rice, buy, pay, how much, want, need |
| 6 | Places & Directions | 56 | go, come, street, left, right, here, there, near, far |
| 7 | Actions & Descriptions | 56 | big, small, good, bad, fast, slow, hot, cold, open, close |
| 8 | Feelings & Opinions | 56 | happy, sad, tired, hungry, like, love, think, know, want |
| 9-12 | Review + Expansion (travel, health, weather) | 56-112 | Optional weeks if 12-week track |

**Daily Vocabulary Task (10-20 min):**
1. **Encounter (2 min):** See/hear the 8 new words in context sentences
2. **Definition (2 min):** Arabic meaning + image/visual association
3. **Production (3 min):** Say each word in your own sentence (record)
4. **Context (3 min):** Use 3 of today's words in a single short paragraph (written or spoken)
5. **Review (2 min):** Quick review of yesterday's 8 words (spaced repetition)

---

### 2.5 Speaking Missions (Daily — Level 0)

Each day has one structured speaking mission (recorded, 60-120 seconds).

**Mission Types (rotate across the week):**

| Day | Mission Type | Example (Week 1) | Example (Week 5) |
|-----|-------------|-------------------|-------------------|
| Sat | Self-Introduction | "Say your name, where you're from, one thing you like" (30 sec) | "Introduce yourself: name, city, job, family, hobby" (60 sec) |
| Sun | Describe | "Describe what you see in your room" (3 items) | "Describe your daily morning routine" (5 steps) |
| Mon | List/Count | "Count 1-10 and say today's date" | "List 5 foods you ate this week" |
| Tue | Read Aloud | Read a 3-sentence paragraph (provided) | Read a 5-sentence paragraph (with focus on stress) |
| Wed | Answer Questions | "What is your name? Where do you live?" (answer each) | "What did you eat? Where did you go?" (past simple) |
| Thu | Repeat After | Shadow a 30-second slow clip (model provided) | Shadow a 45-second clip, match rhythm |
| Fri | Free Talk | "Say anything in English for 30 seconds — any topic!" | "Talk about your week for 60 seconds — no script" |

**Progression:** Week 1-2: 30 seconds. Week 3-4: 45 seconds. Week 5-6: 60 seconds. Week 7-8: 75-90 seconds.

---

### 2.6 Shadowing Materials (Daily — Level 0)

**Source Material:** Slow, clear English recordings at 60-80 WPM (words per minute).

**Recommended Sources:**
- BBC Learning English (6 Minute English, slow sections)
- English with Lucy (pronunciation-focused clips)
- Rachel's English (slow phoneme demonstrations)
- Custom-recorded slow clips by founder (ideal for pilot)

**Daily Shadowing Task (10-15 min):**
1. **Listen once** without speaking (understand the gist)
2. **Listen + read transcript** simultaneously (connect sound to text)
3. **Shadow 3 times** (speak along with the audio, matching rhythm)
4. **Record attempt #3** and compare to original
5. **Note 2 words** where your pronunciation differed most

**Clip Length:** 30-45 seconds per day (increases to 60s by week 6-8)

---

### 2.7 Listening Exercises (Daily — Level 0)

| Week | Listening Speed | Content Type | Task |
|------|:--------------:|--------------|------|
| 1-2 | 60 WPM | Single sentences, greetings | Choose correct image / answer Yes-No |
| 3-4 | 70 WPM | Short dialogues (2-3 exchanges) | Who said what? / Fill the gap |
| 5-6 | 75 WPM | Mini-stories (4-5 sentences) | Order events / True-False |
| 7-8 | 80 WPM | Short descriptions, simple instructions | Follow instructions / Summarize in 1 sentence |

**Daily Listening Task (8-15 min):**
1. Listen to clip (2-3 times if needed)
2. Answer 3-5 comprehension questions
3. Identify 2 new words from the clip
4. Repeat 1 sentence from the clip verbatim

---

### 2.8 Writing Exercises (Daily — Level 0)

| Weeks | Writing Task | Length | Focus |
|-------|-------------|:------:|-------|
| 1-2 | Copy + modify sentences (change one word) | 3 sentences | SVO word order |
| 3-4 | Complete sentences (fill gaps) | 3-4 sentences | Vocabulary in context |
| 5-6 | Write original sentences using target vocabulary | 4-5 sentences | Present simple tense |
| 7-8 | Write a short paragraph about yourself/your day | 5-7 sentences | Coherence + grammar |

**Daily Writing Task (7-15 min):**
1. Read the prompt
2. Write your response (no translator!)
3. Submit in #l0-text-practice
4. Receive AI/peer feedback within 24h

---

### 2.9 Grammar Introduction (Level 0 — Usage-Based)

Grammar is NOT taught as rules first. It's encountered through tasks, then explained when patterns emerge.

| Week | Grammar Pattern Introduced | How It's Introduced |
|------|---------------------------|---------------------|
| 1 | Subject + Verb + Object (SVO) | Through speaking missions ("I like coffee") |
| 2 | Present simple (I/You + verb) | Through daily routine descriptions |
| 3 | Present simple (He/She + verb-s) | Through describing family members |
| 4 | Negation (don't / doesn't) | Through "What I don't like" speaking task |
| 5 | Questions (Do you...? / Is it...?) | Through pair practice in voice lounge |
| 6 | There is / There are | Through "describe your room" tasks |
| 7 | Can / Can't (ability) | Through "What can you do?" missions |
| 8 | Past simple (was/were, regular -ed) | Through "What did you do yesterday?" |

**Grammar is formalized AFTER learners have used it for 3+ days.** On the 4th day, a Grammar Pattern Card is delivered summarizing what they already know intuitively.

---

### 2.10 Content Production Plan

To build 8 weeks of L0 content, the following must be produced:

| Content Type | Quantity (8 weeks) | Who Creates | Format |
|-------------|:------------------:|:-----------:|--------|
| Phoneme drill audio/instructions | 56 daily drills | AI-generated prompts + founder review | Text + audio links |
| Vocabulary word lists (themed) | 8 weekly lists (448 words) | AI-generated + curated from frequency list | Text + images |
| Speaking mission prompts | 56 daily missions | AI-generated from §2.5 rotation | Text prompts |
| Shadowing clips (30-60s each) | 56 clips | Curated from BBC/Rachel's/Lucy + 5 custom | Audio + transcript |
| Listening exercises | 56 daily exercises | AI-generated + founder audio | Audio + questions |
| Writing prompts | 56 daily prompts | AI-generated from §2.8 progression | Text prompts |
| Grammar Pattern Cards | 8 cards (one per week) | AI-generated from prompt §11.1 | Text/image |
| Spaced repetition review sets | Daily (building) | Auto-generated from vocab lists | Text |

**Production Strategy:**
- **Week 1-2 content:** Fully manual (founder writes + curates). This is the pilot test material.
- **Week 3-8 content:** AI-generated using prompts from Phase 3, founder spot-checks 20%.
- **Batch production:** Create content 1 week ahead minimum (never same-day).

---

### 2.11 Minimum Viable Curriculum (Pilot-Ready Subset)

For the 10-member pilot, you don't need all 8-12 weeks on day one. Build in this order:

| Priority | Content | Covers | Build Time |
|:--------:|---------|--------|:----------:|
| **1** | Week 1-2 complete (14 days of all 7 tasks) | First 2 weeks of pilot | 3-4 days |
| **2** | Week 3-4 complete | Days 15-28 | 2-3 days |
| **3** | Week 5-6 complete | Days 29-42 | 2-3 days |
| **4** | Week 7-8 complete | Days 43-56 (minimum to advancement) | 2-3 days |
| **5** | Week 9-12 (extension for slower learners) | Optional additional time | 2-3 days |

**Pilot launch requires only Priority 1 complete (14 days).** Build the rest while the pilot is running (you're 2 weeks ahead at all times).

---

### 2.12 Phase 2 Completion Checklist

- [ ] Week 1-2 curriculum fully written (14 days × 7 tasks = 98 task items)
- [ ] All Week 1-2 phoneme drills have audio sources identified
- [ ] 112 vocabulary words (Week 1-2) with Arabic definitions + context sentences
- [ ] 14 shadowing clips identified/prepared with transcripts
- [ ] 14 speaking missions written with clear prompts
- [ ] 14 listening exercises with audio + questions
- [ ] 14 writing prompts matching progression
- [ ] 2 Grammar Pattern Cards (SVO + present simple)
- [ ] Week 3-4 content at least outlined (can be in-progress)
- [ ] All content organized by day and task number
- [ ] Content reviewed for Arabic-speaker-specific challenges (R/L, th-sounds, vowel length)

**Phase 2 is "pilot-ready" when:** 14 complete days of content exist and weeks 3-4 are outlined. Full 8-week content continues building in parallel with the pilot.

---


## PHASE 3: AI Engine Deployment

**Objective:** Deploy the AI prompt ecosystem that generates daily content, evaluates submissions, delivers personalized feedback, and scales the system without additional human instructors. Integrate with the Discord bot and existing n8n infrastructure.

**Duration:** 3-4 days  
**Dependencies:** Phase 1 (Discord server + bot foundation), Phase 2 (curriculum structure defined — AI needs to know WHAT to generate)  
**Can Start:** During Phase 2, Week 2 (once curriculum structure is clear)  
**Output:** Working AI pipeline that generates daily tasks, evaluates submissions, and delivers feedback automatically

---

### 3.1 AI Engine Architecture

```
Content Generation Layer          Evaluation Layer             Delivery Layer
─────────────────────────        ────────────────────         ──────────────────
                                                              
[Prompt Templates]               [Scoring Rubrics]            [n8n Scheduled]
       │                                │                           │
       ▼                                ▼                           ▼
[LLM API Call]                   [LLM API Call]               [Discord Webhook]
(Gemini / Claude / GPT)          (Gemini / Claude)            (to #lX-daily-tasks)
       │                                │                           │
       ▼                                ▼                           ▼
[Content Output]                 [Score + Feedback]           [Member Receives]
(task, vocab, drill)             (rubric-based)               (daily at set time)
       │                                │                    
       ▼                                ▼                    
[Quality Check]                  [Store in CRM/Sheet]         
(spot-check 20%)                 (progress tracking)          
```

**LLM Selection (cost-optimized for solo operator):**

| LLM | Use Case | Cost | API |
|-----|----------|------|-----|
| **Gemini 2.5 Flash** | Content generation (tasks, vocab, drills) | Free tier: 1,000 req/day | generativelanguage.googleapis.com |
| **Gemini 2.5 Flash** | Writing evaluation + feedback | Free tier (same quota) | Same |
| **Groq (Llama 3.3 70B)** | Fallback if Gemini is down | Free tier: generous | api.groq.com |
| **Whisper (local or API)** | Speech-to-text for speaking submissions | Free (local) or $0.006/min | OpenAI or local |
| **Workers AI (Cloudflare)** | Image generation for vocabulary cards | Free quota | Existing CF account |

**Cost Target:** $0/month during pilot (free tiers only). Scale to paid only if >50 members.

---

### 3.2 Core Prompts to Deploy (Priority Order)

From Blueprint §11, these 25 prompts are deployed in phases:

#### Pilot Priority (Deploy Before First Member)

| # | Prompt | Purpose | Trigger | Output To |
|---|--------|---------|---------|-----------|
| 1 | **Daily Speaking Mission Generator** | Create today's speaking task | n8n cron (daily 6AM) | #lX-daily-tasks |
| 2 | **Weekly Vocabulary Cheat Sheet** | This week's 56 words + contexts | n8n cron (Sunday) | #cheat-sheets |
| 3 | **Grammar Pattern Card** | Weekly grammar pattern summary | n8n cron (day 4 of week) | #cheat-sheets |
| 4 | **Writing Assessment & Correction** | Score + correct submitted writing | On submission (webhook) | DM to member |
| 5 | **Speaking Evaluation & Feedback** | Score submitted recordings | On submission (manual for pilot) | DM to member |
| 6 | **Personalized Study Plan Generator** | Generate plan after placement | On new member onboarding | DM to member |

#### Post-Pilot (Deploy After Week 2)

| # | Prompt | Purpose | Trigger |
|---|--------|---------|---------|
| 7 | Personal Error Log Cheat Sheet | Top 5 errors + fixes | Weekly (per member) |
| 8 | Role-Play Scenario Generator | Pair practice scenarios | 3x/week |
| 9 | Listening Comprehension Exercise Creator | Daily listening task | Daily |
| 10 | Transcription Exercise Generator | Advanced listening | L1+ daily |
| 11 | Weekly Progress Report Generator | Member progress summary | Sunday |
| 12 | Accent Analysis Report | Pronunciation breakdown | Monthly |
| 13 | Leveled Reading Passage Generator | Custom reading material | 2x/week |
| 14 | Conversation Starter Pack | Voice lounge topics | Daily |
| 15 | Shadowing Audio Script Generator | Annotated scripts | Daily |

#### Scale Phase (Deploy at 50+ Members)

| # | Prompt | Purpose |
|---|--------|---------|
| 16-20 | Assessment Question Bank, Onboarding Messages, Debate Topics, Song Analysis, Movie Scene Transcript | Automated at scale |
| 21-25 | Phoneme Drill Generator, Linked Speech Exercise, Intonation Drill, Writing Prompt, Grammar Error Explanation | Full automation |

---

### 3.3 Prompt Implementation: Daily Speaking Mission Generator

**Full Prompt (ready to deploy):**

```
You are the AI engine for Empire English Community — a system-driven English learning program for Arabic speakers focused on American accent mastery.

Generate a Daily Speaking Mission for a Level {LEVEL} learner.

LEARNER CONTEXT:
- Level: {LEVEL} (0=absolute beginner, 1=survival, 2=communication, 3=fluency)
- Week: {WEEK_NUMBER} of the level
- Day of week: {DAY_NAME}
- Today's vocabulary theme: {VOCAB_THEME}
- Recent grammar pattern: {GRAMMAR_PATTERN}
- Mission type for today: {MISSION_TYPE}

MISSION TYPES (rotate daily):
- Saturday: Self-Introduction (progressive complexity)
- Sunday: Describe (objects, routines, places)
- Monday: List/Count (quantities, sequences)
- Tuesday: Read Aloud (provided text with phoneme focus)
- Wednesday: Answer Questions (respond to prompts)
- Thursday: Shadow & Repeat (model provided)
- Friday: Free Talk (any topic, target duration)

LEVEL 0 CONSTRAINTS:
- Maximum 5-8 sentences expected
- Use only vocabulary from weeks 1 to {WEEK_NUMBER}
- Grammar limited to: {GRAMMAR_PATTERN} and below
- Target duration: {TARGET_SECONDS} seconds
- Include 2-3 guiding questions to help the learner

OUTPUT FORMAT (JSON):
{
  "mission_title": "short engaging title in English",
  "mission_title_ar": "Arabic translation of title",
  "instructions_en": "clear English instructions (2-3 sentences)",
  "instructions_ar": "Arabic translation of instructions",
  "guiding_questions": ["question 1", "question 2", "question 3"],
  "target_duration_seconds": number,
  "target_phrases": ["phrase they should try to use", "another one"],
  "phoneme_focus": "today's target sound to practice within the mission",
  "recording_instructions": "Record yourself. Post in #l0-showcase. Duration: X seconds minimum.",
  "example_response": "A short example of what a good response sounds like (2-3 sentences)"
}
```

---

### 3.4 Prompt Implementation: Writing Assessment & Correction

**Full Prompt (ready to deploy):**

```
You are a supportive English writing tutor for Empire English Community. The learner is an Arabic speaker at Level {LEVEL}.

EVALUATE this writing submission:

SUBMISSION:
"{SUBMISSION_TEXT}"

TASK PROMPT THAT WAS GIVEN:
"{ORIGINAL_PROMPT}"

LEARNER LEVEL: {LEVEL}
- Level 0: simple sentences, SVO, present simple, 500-word vocabulary
- Level 1: paragraphs, past/future tense, 1500 words
- Level 2: essays, all tenses, conditionals, 3000 words
- Level 3: advanced style, near-native accuracy

SCORING RUBRIC (score each 0-100):
1. Grammar Accuracy (weight 30%): correct sentence structure, verb forms, articles
2. Vocabulary (weight 25%): appropriate word choice, variety, level-appropriate
3. Organization (weight 25%): logical order, coherence, transitions
4. Task Completion (weight 20%): addressed the prompt fully, met length requirement

FEEDBACK RULES:
- Be encouraging first, then constructive
- Maximum 3 corrections per submission (don't overwhelm)
- For Level 0: focus ONLY on word order and verb form — ignore articles/prepositions
- Show the correction inline: ~~wrong~~ → **correct**
- End with ONE specific thing to practice this week
- Use simple English for L0-L1 feedback (they must understand it)

OUTPUT FORMAT (JSON):
{
  "overall_score": number (0-100),
  "grammar_score": number,
  "vocabulary_score": number,
  "organization_score": number,
  "task_completion_score": number,
  "feedback_en": "encouraging feedback + 3 corrections + 1 focus area",
  "feedback_ar": "Arabic summary of key points (for L0 only)",
  "corrected_version": "the full text with corrections applied",
  "one_thing_to_practice": "specific, actionable improvement focus",
  "rating": "Excellent / Strong / Satisfactory / Needs Work / Keep Trying"
}
```

---

### 3.5 Prompt Implementation: Weekly Vocabulary Cheat Sheet

**Full Prompt (ready to deploy):**

```
Generate a Weekly Vocabulary Cheat Sheet for Empire English Community.

PARAMETERS:
- Level: {LEVEL}
- Week: {WEEK_NUMBER}
- Theme: {THEME}
- Word count: {WORD_COUNT} words (Level 0 = 56 words/week)
- Learner's first language: Arabic

For each word, provide:
1. The English word
2. Phonetic pronunciation (simplified, not full IPA — readable by beginners)
3. Arabic translation
4. Part of speech
5. One example sentence (using only words from this level or below)
6. One common mistake Arabic speakers make with this word
7. One collocation (common word pair)

FORMAT: Return as a structured list, grouped by day (8 words per day for Level 0).

ADDITIONAL REQUIREMENTS:
- Words must come from the top 500 frequency list for Level 0
- Order words from concrete/visual (nouns) to abstract (verbs, adjectives)
- Include pronunciation notes for sounds that don't exist in Arabic (p/b, v/f, θ/ð)
- Mark words with difficult-for-Arabic-speakers sounds with a ⚠️

OUTPUT: JSON array of 56 word objects grouped by day.
```

---

### 3.6 n8n Integration Architecture

The AI engine connects to the Discord server through n8n workflows:

**New Workflows to Create:**

| Workflow | Trigger | What It Does |
|----------|---------|--------------|
| `Empire — Daily Task Delivery` | Cron: 6:00 AM daily | Generates today's 7 tasks via AI → Posts to #lX-daily-tasks channels |
| `Empire — Submission Evaluator` | Discord webhook (on message in #feedback channels) | Detects submissions → Calls AI for scoring → DMs feedback to member |
| `Empire — Weekly Content Generator` | Cron: Sunday 5:00 AM | Generates vocab cheat sheet + grammar card → Posts to #cheat-sheets |
| `Empire — Streak Tracker` | Cron: 11:00 PM daily | Checks daily check-ins → Updates streak counts → Posts to #streak-tracker |
| `Empire — Progress Reporter` | Cron: Sunday 8:00 PM | Generates per-member weekly progress → DMs each member |

**Integration with Existing Infrastructure:**

```
Existing n8n (bot.empireenglish.online)
├── Empire Bot (Telegram) — funnel/acquisition [EXISTING]
├── Empire Weekly Report — funnel KPIs [EXISTING]
├── Nudges + Backup + Scoring [EXISTING]
│
└── NEW: Learning System Workflows
    ├── Daily Task Delivery (Discord webhook out)
    ├── Submission Evaluator (Discord webhook in → AI → Discord DM)
    ├── Weekly Content Generator (AI → Discord)
    ├── Streak Tracker (Discord → Sheets → Discord)
    └── Progress Reporter (Sheets → AI → Discord DM)
```

**Discord Webhook Setup:**
1. Create a webhook for each level's #daily-tasks channel (4 webhooks total)
2. Create a webhook for #cheat-sheets and #leaderboard
3. Store webhook URLs in n8n credentials or environment variables
4. All content delivery uses Discord webhooks (no complex bot code needed for pilot)

---

### 3.7 Content Delivery Format (Discord Messages)

**Daily Task Post (delivered at 6 AM to #l0-daily-tasks):**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 DAY 15 — Tuesday, Week 3
🏛️ EMPIRE ENGLISH — Level 0 Daily Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ ACCENT DRILL (10 min)
Today's sounds: /θ/ (think) and /ð/ (this)
→ Listen: [audio link]
→ Practice: "think, three, thank, the, this, that"
→ Record yourself saying: "I think this is the third thing."

2️⃣ VOCABULARY (10 min)
Today's 8 words (Week 3: Family & People):
mother · father · brother · sister · son · daughter · family · friend
→ Learn: [vocab card link]
→ Say each in a sentence: "My mother is kind."

3️⃣ SHADOWING (10 min)
Today's clip: "Meeting new people" (35 seconds, 65 WPM)
→ Audio: [link]
→ Transcript: [link]
→ Shadow 3 times. Record attempt #3.

4️⃣ SPEAKING MISSION (10 min)
🎙️ "Tell me about your family"
→ Who is in your family? What do they do?
→ Target: 45 seconds
→ Record and post in #l0-showcase

5️⃣ LISTENING (8 min)
🎧 Listen to the dialogue: [link]
→ Answer: Who is speaking? What are their names?
→ Post your answers below.

6️⃣ WRITING (7 min)
✍️ Write 4 sentences about your family.
→ Use: mother, father, brother/sister
→ Post in #l0-text-practice

7️⃣ COMMUNITY (5+ min)
💬 Join #voice-lounge-open or reply to someone in #general-chat
→ Say one thing in English today!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ When done: Post "Done ✅" in #daily-check-in
🔥 Your streak: {STREAK_COUNT} days
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 3.8 Submission Detection & Evaluation Flow

**How it works for the pilot (semi-automated):**

1. Member posts a voice recording in #speaking-feedback or #l0-showcase
2. n8n webhook detects the message (Discord event → n8n)
3. For **writing:** extract text → call AI Writing Assessment prompt → DM feedback
4. For **speaking:** (Phase 1 pilot = manual evaluation by founder. Phase 2+ = Whisper transcription → AI evaluation)
5. Score is logged to Google Sheets (new tab: `Learning_Progress`)
6. Streak is updated

**Pilot Simplification:**
- Speaking evaluation is **manual** (founder listens + gives feedback) for the first 10 members
- Writing evaluation is **AI-automated** from day one (text is easy to process)
- AI generates feedback drafts for speaking too — founder approves/edits before sending
- This validates AI quality before fully automating in Phase 2

---

### 3.9 Google Sheets: Learning Progress Tab

Add to Empire CRM (new tab):

| Column | Type | Purpose |
|--------|------|---------|
| date | Date | Task date |
| telegram_id | Number | Member ID (links to Subscribers) |
| discord_id | Text | Discord user ID |
| task_type | Text | accent/vocab/shadow/speaking/listening/writing/community |
| submitted | Boolean | Did they submit? |
| score | Number (0-100) | AI or manual score (null if not evaluated) |
| feedback_sent | Boolean | Was feedback delivered? |
| streak_day | Number | Current streak count |
| week | Number | Which week of the level |
| level | Text | L0/L1/L2/L3 |

---

### 3.10 Phase 3 Completion Checklist

- [ ] Gemini API key configured in n8n environment
- [ ] Daily Speaking Mission prompt tested and producing correct output
- [ ] Writing Assessment prompt tested and producing useful feedback
- [ ] Weekly Vocabulary Cheat Sheet prompt tested
- [ ] Discord webhooks created for all task-delivery channels
- [ ] n8n workflow: Daily Task Delivery (posts to Discord at 6AM)
- [ ] n8n workflow: Weekly Content Generator (posts cheat sheets Sunday)
- [ ] n8n workflow: Streak Tracker (updates daily)
- [ ] Submission detection working (at least for text in #writing-feedback)
- [ ] AI writing feedback being delivered to test submissions
- [ ] Learning_Progress tab created in CRM
- [ ] All prompts produce Arabic support content for Level 0
- [ ] Fallback: if AI fails, a pre-written task is posted instead (never empty)

**Phase 3 is complete when:** Daily tasks auto-post to Discord, written submissions receive AI feedback within 2 hours, and streaks are tracked automatically.

---


## PHASE 4: Evaluation & Tracking System

**Objective:** Build the measurement framework that tracks learner progress, delivers weekly assessments, enables level advancement decisions, and provides the data needed to prove the system works.

**Duration:** 2-3 days  
**Dependencies:** Phase 2 (curriculum defines what to assess), Phase 3 (AI engine scores submissions)  
**Output:** Working assessment system with weekly scoring, progress dashboards, and advancement exam structure

---

### 4.1 Weekly Assessment Protocol (Every Sunday)

**From Blueprint §9.1:** A standardized 30-minute assessment across 5 dimensions + task completion.

| Dimension | Weight | How It's Assessed (Level 0) |
|-----------|:------:|----------------------------|
| Speaking Fluency | 30% | 60-second recorded response to a prompt. Scored on: words/min, pauses, grammar. |
| Listening Comprehension | 20% | 5 questions on a 60-80 WPM audio clip. Multiple choice. |
| Vocabulary Recall | 15% | 15 words from this week + last week. Match definition or use in sentence. |
| Accent/Pronunciation | 15% | Read a 3-sentence passage. Scored on phoneme accuracy for this week's targets. |
| Writing Sample | 10% | Write 5 sentences on a given topic (timed: 8 minutes). |
| Task Completion Rate | 10% | Automatic: (tasks submitted this week / total tasks) × 100 |

**Assessment Delivery (via Discord bot/n8n):**

```
Sunday 10:00 AM → Bot posts assessment prompt in DM to each member:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 WEEKLY ASSESSMENT — Week {N}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Complete these 5 tasks today (30 min total):

1️⃣ SPEAKING (5 min)
Record yourself answering: "{prompt}"
→ Target: 60 seconds, no script
→ Send recording here (this DM)

2️⃣ LISTENING (5 min)
Listen: {audio_link}
Answer these 5 questions: {questions}
→ Type your answers here

3️⃣ VOCABULARY (5 min)
Match these 15 words to their meanings:
{word_list with options}
→ Type your answers (1-A, 2-C, etc.)

4️⃣ PRONUNCIATION (5 min)
Read this passage aloud and record:
"{passage with target phonemes}"
→ Send recording here

5️⃣ WRITING (8 min)
Write 5 sentences about: "{topic}"
→ Type your response here

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Due by: Sunday 11:59 PM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Scoring (Pilot):**
- Listening + Vocabulary: auto-scored (objective answers)
- Writing: AI-scored using the Writing Assessment prompt (Phase 3)
- Speaking + Pronunciation: founder-scored manually (10 members × 2 min each = 20 min/week)
- Task Completion: auto-calculated from submission records

**Score Storage:** Add to `Learning_Progress` sheet or create dedicated `Assessments` tab:

| Column | Type | Purpose |
|--------|------|---------|
| member_id | Text | Discord ID |
| week | Number | Assessment week number |
| speaking_score | Number (0-100) | Speaking fluency score |
| listening_score | Number (0-100) | Comprehension score |
| vocabulary_score | Number (0-100) | Recall accuracy |
| accent_score | Number (0-100) | Pronunciation score |
| writing_score | Number (0-100) | Writing quality |
| task_completion | Number (0-100) | % of tasks submitted |
| overall_score | Number (0-100) | Weighted composite |
| rating | Text | Excellent/Strong/Satisfactory/At Risk/Critical |
| notes | Text | Specific feedback notes |

---

### 4.2 Weekly Score Interpretation & Actions

| Score | Rating | Automated Action |
|:-----:|--------|-----------------|
| 90-100 | Excellent | Congratulations message + suggest peer mentoring |
| 80-89 | Strong | Positive message + "focus on {weakest dimension}" |
| 70-79 | Satisfactory | Encouragement + specific practice recommendation |
| 60-69 | At Risk | Founder check-in triggered. Buddy outreach. Revised plan offered. |
| <60 | Critical | Immediate 1-on-1. Possible level adjustment or track change. |

**Automated Weekly Report (to member, Monday morning):**

```
📊 Your Week {N} Results
━━━━━━━━━━━━━━━━━━━━━━━━
Overall: {score}/100 — {rating}

Speaking:     {score} ████████░░ 
Listening:    {score} ██████████ 
Vocabulary:   {score} ███████░░░
Pronunciation:{score} █████░░░░░ ← Focus here
Writing:      {score} ████████░░
Completion:   {score} ██████████

🎯 This week's focus: {weakest_area}
💡 Tip: {specific_actionable_advice}
🔥 Streak: {streak} days

{if_at_risk: "Your buddy will reach out. Let's get back on track together."}
```

---

### 4.3 Level Advancement Examination (L0 → L1)

**From Blueprint §9.3:** 60-minute exam, all sections must pass individually.

| Section | Duration | Content (L0 Exit) | Passing Score |
|---------|:--------:|-------------------|:-------------:|
| Live Speaking | 10 min | 60-sec self-intro (no script) + 5-min Q&A on familiar topics | 70% |
| Listening Test | 15 min | 15 questions at 80 WPM (multiple choice + short answer) | 70% |
| Vocabulary Test | 10 min | 50 words from the 500-word list (meaning + usage) | 70% |
| Accent Evaluation | 5 min | Read passage (2 min) + spontaneous speech (3 min) | 70% |
| Writing Test | 20 min | Write a paragraph: "Describe your daily routine" (minimum 7 sentences) | 70% |

**Exam Protocol:**
- Available after Week 8 minimum (earlier if all weekly scores are 80%+)
- Maximum one attempt per month
- All 5 sections must pass — failing one = retake entire exam next month
- Exam is recorded for quality assurance
- Results delivered within 48 hours
- Passing triggers: automatic Discord role upgrade (L0 → L1), celebration in #announcements

**Pilot Approach:**
- Founder administers the speaking + accent sections live (voice call)
- Listening, vocabulary, writing are delivered via Discord DM (auto-scored or AI-scored)
- Recorded for calibration data (to train AI scoring in Phase 2+)

---

### 4.4 Progress Dashboard (Per Member)

Tracked in Google Sheets. Delivered weekly via DM. Visual version in future web app.

**Data Points Tracked:**

| Metric | Source | Updated |
|--------|--------|---------|
| Current level | Advancement exam results | On exam pass |
| Current week | Day count / 7 | Daily |
| Overall score trend | Weekly assessments | Weekly |
| Streak (current) | Daily check-ins | Daily |
| Streak (longest) | Historical max | Daily |
| Tasks completed (total) | Submission count | Daily |
| Tasks completed (%) | Submitted / assigned | Daily |
| Time invested (est.) | Tasks × avg duration | Daily |
| Vocabulary mastered | Spaced repetition passes | Weekly |
| Phonemes mastered | Accent drill scores | Weekly |
| Speaking duration growth | First recording vs latest | Monthly |
| Community participation | Voice lounge time + messages | Weekly |

---

### 4.5 Spaced Repetition Integration

From Blueprint §6.2 — vocabulary is reviewed on a schedule:

| Review | Timing | Format | Auto-Delivered? |
|--------|--------|--------|:---------------:|
| Review 1 | Next day | Fill-in-blank in context | Yes (in daily tasks) |
| Review 2 | +2 days | Use in spoken sentence (recorded) | Yes (speaking mission) |
| Review 3 | +3 days | Match to definition + write sentence | Yes (writing task) |
| Review 4 | +7 days | Verbal definition without prompts | Yes (weekly assessment) |
| Review 5 | +14 days | Use correctly in voice lounge | Encouraged (not enforced) |

**Implementation:** The Daily Task Delivery workflow (Phase 3) includes 2-3 review words from previous weeks alongside new vocabulary. This is generated automatically by referencing the member's vocabulary history.

---

### 4.6 Phase 4 Completion Checklist

- [ ] Weekly assessment prompt template written (all 5 sections for L0)
- [ ] Assessment delivery workflow in n8n (Sunday 10AM DM to each member)
- [ ] Auto-scoring working for: listening (objective), vocabulary (objective), task completion (count)
- [ ] AI scoring working for: writing (via Phase 3 prompt)
- [ ] Manual scoring process defined for: speaking + accent (founder evaluates)
- [ ] Score storage tab created in CRM (Assessments)
- [ ] Weekly report template generated and tested
- [ ] At-Risk threshold triggers defined (score <70 → buddy outreach)
- [ ] Level advancement exam content written (L0 exit: 50 vocab words, 15 listening questions, reading passage, writing prompt, speaking Q&A questions)
- [ ] Advancement exam protocol documented (who administers, recording, timing)
- [ ] Spaced repetition logic integrated into daily task generation
- [ ] Progress data flowing correctly to sheets on every submission

**Phase 4 is complete when:** The first weekly assessment can be delivered, scored, and results reported to a test member end-to-end.

---


## PHASE 5: Onboarding & Pilot Launch (10 VIP Members)

**Objective:** Build the 48-hour onboarding flow, recruit 10 pilot members, and launch the 8-week validation experiment. This is where the system meets real humans for the first time.

**Duration:** 1 week preparation + 8 weeks pilot execution  
**Dependencies:** Phases 1-4 all complete (Discord + content + AI + evaluation)  
**Output:** 10 real learners actively using the system, generating data, and providing feedback

---

### 5.1 The 48-Hour Onboarding Flow (from Blueprint §3.3)

| Step | Time | Action | Delivered Via | Language |
|------|------|--------|--------------|----------|
| 1 | Hour 0 | Complete application form (motivation, goals, availability, track choice) | Google Form (link from Telegram bot or DM) | Arabic + English |
| 2 | Hour 0-2 | Receive welcome message + rules + level system overview | Discord DM (from bot/founder) | Arabic for L0 |
| 3 | Hour 2-6 | Complete placement assessment (simplified for pilot — 15 min version) | Discord DM (bot-delivered prompts) | Bilingual |
| 4 | Hour 6-8 | Receive level assignment + personalized study plan | Discord DM | Arabic + English |
| 5 | Hour 8-12 | Assigned onboarding buddy makes contact | Discord DM (buddy → new member) | Arabic OK |
| 6 | Hour 12-24 | Attend mandatory 30-min orientation voice session | Scheduled Discord voice channel | Bilingual |
| 7 | Hour 24-36 | Complete first day of tasks (simplified: 3 tasks only, not 7) | #l0-daily-tasks | English (with Arabic support) |
| 8 | Hour 36-48 | First checkpoint: buddy reviews Day 1 completion | Discord DM or voice | Bilingual |

**Onboarding Success Metric:** ≥8 of 10 members complete all 8 steps within 48 hours.

**Pilot Simplification (Refinement from Blueprint):**
- Step 3 uses the existing 7-question Telegram quiz as initial placement (not the full 45-minute diagnostic)
- Step 7: Day 1 has only 3 tasks (phoneme drill + 1 speaking mission + community hello) — NOT full 7-task load
- Full 7-task loop introduced gradually: Day 1-3 = 3 tasks, Day 4-7 = 5 tasks, Week 2+ = full 7 tasks
- Founder personally conducts orientation (Step 6) for all pilot members

---

### 5.2 Placement Assessment (Pilot Version)

For the 10-member pilot, use a **simplified placement** (not the full 45-minute diagnostic):

| Method | Duration | What It Captures |
|--------|:--------:|-----------------|
| Existing Telegram bot quiz (7Q) | 2 min | Self-assessed level + goal + availability |
| Short voice recording request | 3 min | "Record yourself speaking English for 30-60 seconds — any topic" |
| 5 written sentences | 3 min | "Write 5 sentences about yourself in English" |
| Founder judgment call | — | Listen to recording + read sentences → assign level |

**Why simplified:** With 10 members, the founder can personally place each one in 5 minutes. The full diagnostic is built for scale (100+ members). Building it now would delay the pilot for no benefit.

**Note:** Record all pilot placement data — it becomes calibration data for the automated placement in Phase 2.

---

### 5.3 Pilot Member Recruitment

**Target:** 10 members. **Source:** Existing Telegram channel (57 members) + founder's personal network.

**Recruitment Criteria (select carefully):**

| Criterion | Why |
|-----------|-----|
| Genuinely wants to improve English | Motivated = completes tasks = generates data |
| Available 45-75 min/day (Core track) | Realistic commitment |
| Has Discord (or willing to install) | Platform requirement |
| Has a smartphone with voice recording | Can submit speaking tasks |
| Mix of levels (ideally: 6-7 L0, 2-3 L1) | Tests the primary audience |
| Willing to give honest feedback | Critical for iteration |
| Understands this is a pilot (free, in exchange for feedback) | Sets expectations |

**Recruitment Message (Arabic — send to engaged Telegram users):**

```
مرحبًا! 👋

أبني الحين نظام تعليم إنجليزي جديد كليًا — مو كورس عادي، نظام يومي كامل مع مجتمع ونطق أمريكي من اليوم الأول.

أبي 10 أشخاص فقط يجربونه مجانًا لمدة 8 أسابيع.

في المقابل:
• تلتزم بـ 45-60 دقيقة يوميًا
• تعطيني رأيك الصريح أسبوعيًا
• تسجّل تقدمك

اللي بتحصل عليه:
• نظام يومي مصمم لك (7 مهام/يوم)
• تدريب نطق أمريكي من البداية
• مجتمع يدعمك + متابعة شخصية
• تقييم أسبوعي + خطة مخصصة

مجاني بالكامل. 10 مقاعد فقط.
مهتم؟ رد بـ "أنا" وأرسلك التفاصيل.
```

---

### 5.4 Pre-Launch Checklist (Before First Member Enters Discord)

- [ ] All Phase 1-4 completion checklists pass
- [ ] Week 1-2 curriculum fully loaded and tested
- [ ] Daily task delivery workflow tested (fires at 6AM, posts correctly)
- [ ] Assessment delivery tested (fires Sunday, DMs correctly)
- [ ] At least 1 full dry-run (founder goes through Day 1-7 as a test member)
- [ ] Onboarding flow tested (all 8 steps, timing correct)
- [ ] Welcome messages + rules pinned in Discord
- [ ] Buddy assignments prepared (founder = buddy for first 5, recruit 1 moderator for rest)
- [ ] Orientation session scheduled (date/time communicated to all 10)
- [ ] Google Form for application ready
- [ ] Feedback collection method chosen (weekly 3-question form or DM)
- [ ] Kill/fix thresholds defined (from Blueprint §12.1 refinement)
- [ ] First week of content ready to deliver manually if automation fails

---

### 5.5 Pilot Execution Timeline

| Week | Focus | Key Activities |
|------|-------|----------------|
| **Week 0** | Recruitment | Send invitations. Confirm 10 members. Assign buddies. Schedule orientation. |
| **Week 1** | Onboarding + Day 1-7 | Run 48-hour onboarding. Gradually introduce tasks (3→5→7). First check-in. |
| **Week 2** | Full loop running | All 7 daily tasks active. First weekly assessment (Sunday). Fix any friction. |
| **Week 3** | Stabilization | Members in rhythm. Collect first feedback. Address any drops. Iterate tasks. |
| **Week 4** | Mid-point review | Formal check-in with each member. Review scores. Adjust plans. |
| **Week 5-6** | Momentum | Community developing. Voice lounges active. Members helping each other. |
| **Week 7** | Pre-assessment prep | Prepare L0 exit exam materials. Brief members on advancement. |
| **Week 8** | Advancement + Evaluation | Administer exit exams. Measure outcomes. Collect final feedback. Celebrate. |

---

### 5.6 Pilot Success Metrics (Pre-Registered — from Blueprint §12.1)

These determine whether the system works. Define them BEFORE the pilot starts.

| Metric | Target | "Fix" Threshold | "Kill" Threshold |
|--------|--------|:---------------:|:----------------:|
| Week 4 retention | ≥8 of 10 active | 6-7 active → investigate | <6 → fundamental redesign |
| Daily task completion (median) | ≥60% | 40-59% → adjust difficulty | <40% → tasks too hard/long |
| Weekly assessment completion | ≥80% submit | 60-79% → simplify process | <60% → process too complex |
| Onboarding (8 steps in 48h) | ≥8 of 10 complete | 7 → minor fixes | <7 → onboarding too complex |
| Member satisfaction (weekly survey) | ≥7/10 average | 5-6 → identify friction | <5 → major problem |
| Measurable improvement (Week 1 vs Week 8) | Visible in scores/recordings | Marginal → content issue | None → system not working |
| AI feedback quality (founder spot-check) | ≥80% "useful" | 60-79% → refine prompts | <60% → AI scoring unreliable |

**Data Collection:**
- All metrics auto-tracked via submissions + CRM + assessment scores
- Weekly 3-question satisfaction survey (DM on Friday):
  1. "How useful were this week's tasks? (1-10)"
  2. "What was the hardest part?"
  3. "What would you change?"

---

### 5.7 Phase 5 Completion Criteria

**Pilot is "done" when:**
- [ ] 10 members recruited and confirmed
- [ ] All complete the 48-hour onboarding (≥8 of 10)
- [ ] 8 weeks of execution completed
- [ ] Weekly assessments delivered all 8 weeks
- [ ] Retention, completion, and satisfaction metrics collected
- [ ] At least 1 member attempts the advancement exam
- [ ] Final feedback session conducted (voice or written)
- [ ] Outcomes documented: what worked, what didn't, what to change
- [ ] Decision made: continue to Phase 2 (100 members) or iterate first

---


## PHASE 6: Operations & Governance

**Objective:** Establish the operational processes, moderation framework, privacy protections, and sustainability practices that allow the system to run reliably from the pilot onward.

**Duration:** Ongoing — starts with pilot, formalizes over time  
**Dependencies:** Phases 1-5 provide the systems to operate  
**Output:** Documented SOPs, moderation playbook, privacy framework, and operational health checks

---

### 6.1 English-Only Enforcement (from Blueprint §8.3)

**Policy (Level-Adjusted):**

| Level | Policy | Response to Native Language Use |
|-------|--------|--------------------------------|
| L0 (Weeks 1-4) | Gentle encouragement | Friendly model: "Great idea! In English: {translation}" |
| L0 (Weeks 5+) | Soft enforcement | Friendly redirect + encourage correction |
| L1 | Standard enforcement | Reminder DM from bot after 2 instances |
| L2-L3 | Full enforcement | Warning → timeout escalation (§8.3 protocol) |

**Exception:** #l0-questions allows one-sentence Arabic clarification questions at all times.

**Implementation (Pilot):** Founder monitors manually. At scale: AI-based language detection bot.

---

### 6.2 Moderation & Safety

**Code of Conduct (pinned in #rules):**
- No harassment, bullying, or personal attacks
- No sharing others' recordings without consent
- No spam, self-promotion, or off-topic flooding
- Supportive corrections only — never mocking pronunciation
- Voice lounges: respectful turn-taking, no dominating
- Zero tolerance for hate speech, discrimination, or inappropriate content

**Escalation Path:**
1. Member reports issue → moderator reviews within 4 hours
2. Minor violation → DM warning + reminder of rules
3. Repeated violation → temporary mute (1-24h depending on severity)
4. Serious violation → immediate ban + case documented in #mod-actions
5. Appeal → founder reviews within 48h

**Pilot Moderation:** Founder + 1 recruited moderator (from trusted community member or friend). Formal moderation team at 50+ members.

---

### 6.3 Data Privacy & Consent

**Required Before First Member Joins:**

| Document | Purpose | Delivered When |
|----------|---------|---------------|
| Privacy Notice (Arabic + English) | What data is collected, why, where stored, how to delete | Onboarding Step 1 (application form) |
| Voice Recording Consent | Explicit opt-in for storing and AI-processing voice | Onboarding Step 2 (separate checkbox) |
| Marketing Consent | Permission to use progress for testimonials/marketing | Separate opt-in (not required) |
| Data Deletion Instructions | How to request deletion of all data | In Privacy Notice + #support pinned |

**Data Handling Rules:**
- Voice recordings stored in Google Drive (founder-controlled, not public)
- Retention: 12 months after last activity, then auto-archived
- Right to deletion: honored within 7 days of request
- No minor-specific data without parental consent (enforce 16+ minimum age)
- All AI providers: data not used for training (Gemini API ToS, Groq ToS — verify)

---

### 6.4 Operational Health Checks

**Daily (automated):**
- [ ] Daily tasks posted to all active level channels (check Discord webhook logs)
- [ ] Streak tracker updated
- [ ] No bot errors in #bot-logs

**Weekly (founder, 15 minutes):**
- [ ] Weekly assessment delivered + scores computed
- [ ] At-risk members identified + outreach triggered
- [ ] Submission rate reviewed (are people actually doing tasks?)
- [ ] Voice lounge activity reviewed (is anyone joining?)
- [ ] Quick community sentiment check (#general-chat activity)

**Monthly:**
- [ ] Monthly progress review for each active member
- [ ] Content quality spot-check (are AI-generated tasks appropriate?)
- [ ] Curriculum pacing check (are learners progressing on schedule?)
- [ ] Unit economics tracked (AI cost, time spent, projected at scale)
- [ ] System iteration: what to change based on data

---

### 6.5 Buddy System Operations

**From Blueprint §8.4 — Mentorship Ladder:**

| Role | Who | Responsibility | Ratio |
|------|-----|----------------|:-----:|
| Onboarding Buddy | Founder (pilot) or L1+ member | Guide new member through first week | 1:2 max |
| Peer Mentor | L1+ member (voluntary) | Weekly check-in, answer questions | 1:3 max |
| Level Ambassador | L2-3 member (appointed) | Lead voice sessions, moderate level zone | 1:10 |
| Community Moderator | Trusted member (paid or volunteer) | Enforce rules, manage escalations | 1:25 |

**Pilot:** Founder is the buddy for all 10 members. At 50+ members, recruit the first L1 graduates as buddies.

---

### 6.6 Content Iteration Process

| When | What | Who |
|------|------|-----|
| After Week 2 | Review: are tasks too easy/hard? Adjust vocabulary pace if needed | Founder |
| After Week 4 | Review: which task types get lowest completion? Simplify or replace | Founder + member feedback |
| After Week 8 | Full curriculum review: what to keep, change, remove for next cohort | Founder + data |
| Monthly (post-pilot) | AI prompt refinement based on feedback quality scores | Founder |
| Quarterly | Full system review: level criteria, content freshness, community health | Founder + advisors |

---

### 6.7 Phase 6 Completion Checklist

- [ ] Privacy Notice written (Arabic + English) and ready to present at onboarding
- [ ] Voice recording consent form created
- [ ] Moderation playbook documented (escalation path, consequences)
- [ ] English-only enforcement rules documented and communicated
- [ ] Buddy assignments for pilot confirmed
- [ ] Daily health check automation running (task delivery verification)
- [ ] Weekly operational checklist documented for founder
- [ ] Feedback collection survey created (3-question weekly form)
- [ ] Data retention policy defined (12 months, then archive)
- [ ] Age requirement set and communicated (16+)
- [ ] #admin-chat and #mod-actions channels active

**Phase 6 is "operational" when:** The pilot can run for 8 weeks with documented processes for every operational question that arises, and no member's data rights are violated.

---


## SUMMARY: Complete Execution Sequence

### The 5-Week Sprint to Pilot Launch

```
WEEK 1 (Days 1-7): FOUNDATION + CONTENT START
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 1:   Phase 1 — Create Discord server (all channels, roles, permissions)
Day 2-3: Phase 2 — Write L0 Week 1 curriculum (7 days × 7 tasks)
Day 4-5: Phase 2 — Write L0 Week 2 curriculum (7 days × 7 tasks)
Day 6:   Phase 3 — Deploy AI prompts + task delivery workflow
Day 7:   Phase 3 — Test daily task posting + writing feedback

WEEK 2 (Days 8-14): AUTOMATION + EVALUATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 8-9: Phase 3 — Complete all n8n workflows (streak, progress, content gen)
Day 10:  Phase 4 — Build weekly assessment (template + delivery)
Day 11:  Phase 4 — Test full assessment cycle (deliver → score → report)
Day 12:  Phase 5 — Write onboarding flow + orientation script
Day 13:  Phase 6 — Write privacy notice + consent forms + moderation rules
Day 14:  FULL DRY RUN (founder goes through Day 1-7 as a test member)

WEEK 3 (Days 15-21): RECRUITMENT + PREP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 15-17: Recruit 10 pilot members (DMs, calls, confirmations)
Day 18-19: Write L0 Week 3-4 curriculum (stay 2 weeks ahead)
Day 20:    Final system check — all workflows firing correctly
Day 21:    Schedule orientation session (Day 22 or 23)

WEEK 4-5 (Days 22-35): PILOT LAUNCH + FIRST 2 WEEKS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 22-23: Onboarding (48-hour flow for all 10 members)
Day 24:    Orientation voice session (all 10 attend)
Day 25-28: First week of daily tasks (simplified: 3→5 tasks)
Day 29:    First weekly assessment (Sunday)
Day 30-35: Second week (full 7 tasks). Build Week 5-6 content in parallel.

WEEKS 6-12: PILOT EXECUTION (8 total weeks)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Continue the rhythm:
- Daily: tasks posted, submissions evaluated
- Weekly: assessment + report + feedback survey
- Bi-weekly: content batch for next 2 weeks
- Monthly: full review + iteration
- Week 8: advancement exams + final evaluation
```

---

### What You Have When This Plan Is Complete

| Asset | Value |
|-------|-------|
| A working Discord learning community | The actual product — not just a funnel |
| 8+ weeks of L0 curriculum | Ready-to-use daily content for beginners |
| AI-powered content generation | Scales to 100+ members without manual effort |
| Automated task delivery | Daily at 6AM, no human intervention |
| AI writing feedback | Instant, rubric-based corrections |
| Weekly assessments with scoring | Objective progress measurement |
| Level advancement exam | Quality gate for L0 → L1 |
| 10 real learners with 8 weeks of data | Validation of the entire model |
| Before/after recordings | Proof of transformation (marketing gold) |
| Unit economics data | Know the real cost per learner before scaling |
| Operational playbook | Documented processes for everything |
| A product to sell | When someone books a call via the Telegram funnel — there's something to deliver |

---

### How This Connects to the Existing Funnel

```
EXISTING (Built):                          NEW (This Plan Builds):
━━━━━━━━━━━━━━━━━━━                       ━━━━━━━━━━━━━━━━━━━━━━━
Telegram Channel                           
    ↓ (content posts)                      
Telegram Bot                               
    ↓ (quiz + CRM + nurture)              
Cal.com Booking                            
    ↓ (free strategy call)                
FOUNDER SELLS ON CALL ─────────────────→  Discord Learning Community
                                               ↓
                                           48-Hour Onboarding
                                               ↓
                                           Daily Tasks (7/day)
                                               ↓
                                           Weekly Assessments
                                               ↓
                                           Level Advancement
                                               ↓
                                           REAL TRANSFORMATION
                                               ↓
                                           Testimonials → Back to Channel
                                           (growth loop)
```

The funnel attracts. The learning system delivers. Together, they form the complete Empire English business.

---

*End of Learning System Implementation Plan v1.0*
