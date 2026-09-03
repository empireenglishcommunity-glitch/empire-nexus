# Podcast Studio — Requirements

> **Codename: Sawt (صوت)** — "voice." A studio that turns curriculum topics into
> natural, level-graded English podcast episodes with lifelike AI voices — where
> the owner can appear (solo with an AI co-host, hosting a group of AI voices, or
> curating an AI-only conversation) — and delivers them to students **at their own
> CEFR level** inside the existing Empire English system. Directory name
> (`podcast-studio`) stays literal so it's discoverable.

## Origin

Empire English is a result-driven English program for Arabic-speaking learners,
organized around **six CEFR levels (A1→C2)**, each with its own channel *zone*,
vocabulary target, and speaking target. Students already do 7 daily tasks and
practice on the web app (Darb).

The owner wants to add **podcast content**: engaging spoken-English episodes the
students can listen to. The twist: instead of hiring co-hosts, use **AI voices
so natural that listeners take them for human**. The owner can be *in* an
episode in three ways:

1. **Solo + AI** — the owner and one AI co-host.
2. **Owner amid a group** — the owner hosting/among several AI voices.
3. **AI-only** — a full AI conversation the owner curates (owner may or may not speak).

Crucially, **content must be level-graded**. Learners are at different levels, so
one episode does not fit all:

- **A1** — significant Arabic support (~40%), very simple + slow English, every
  new word explained, short (3–5 min).
- **A2** — light Arabic (~20%) for clarifications, slow, short sentences (5–7 min).
- **B1** — mostly English (~5% Arabic for hard words), everyday pace (7–10 min).
- **B2** — English 100%, natural pace, real dialogue (10–12 min).
- **C1** — English 100%, faster, idioms/depth (12–15 min).
- **C2** — English 100%, near-native, academic/cultural (15+ min).

Episodes should route to the right **level zone** so a student sees the episodes
for *their* level (leveraging the level-role isolation already in place), earn a
little credit for listening, and feel professional and high-quality.

## Constraints

1. **Zero disruption to the live system.** Existing tasks, streaks, points,
   assessments, the role-gate, level isolation, and the practice app must keep
   working exactly as they do today. Everything here is **additive** and
   **flag-gated** (a `sawt_*` initiative), off by default, owner-tunable.
2. **Reuse the existing level model.** Levels, level slugs, zone routing, and
   level roles come from `config` (CEFR A1–C2) — the podcast never invents its
   own level scheme.
3. **Infra/budget:** same bot server; **no GPU assumed**. Audio generation is the
   heaviest part, so the design MUST support an **"produce-outside, publish-inside"**
   mode first (owner produces audio with any tool; the bot organizes/publishes it),
   with optional in-bot generation added later behind a flag. Any paid TTS
   (e.g. ElevenLabs) is **opt-in via an API key**; the default path uses the
   **already-integrated Kokoro** or a free/open model — the owner chooses.
4. **Voice consent & safety.** Voice cloning is supported **only for the owner's
   own voice, with explicit consent.** The system MUST NOT clone or imitate any
   other real person's voice. AI voices used for co-hosts are synthetic/licensed.
5. **Naturalness is a first-class goal.** The pipeline must support conversational
   realism — turn-taking, short back-channels ("mm-hmm", "right"), pauses, and
   distinct voices per speaker — not flat single-voice narration.
6. **Bilingual, Arabic-first where the level calls for it, and bidi-safe** (project
   text rules): Arabic and Latin/command tokens never mixed on one line in a way
   that breaks reading order.
7. **Owner stays in control.** Every surface is flag-gated and owner-driven:
   nothing auto-publishes without the owner's action; a dry-run/preview exists
   before anything goes live to students.
8. **Suspension/gating respected.** Podcast channels obey the same permission
   model — hidden appropriately, level-isolated, and never exposed to suspended
   students.

## Open decisions (owner to confirm — defaults chosen so we can proceed)

- **D1 — Owner's voice:** _default = owner records their own lines_ (highest
  quality, zero cloning risk). Alternative: clone the owner's voice (with
  consent) so the AI speaks the owner's lines from text. **Owner picks.**
- **D2 — TTS engine / budget:** _default = free/open (start with Kokoro, already
  integrated)_, with an **optional** paid ElevenLabs path behind an API key for
  top realism. **Owner picks.**

## Requirements (EARS-style)

### R1 — Level-graded episode profiles
- WHEN an episode is created for a level, THE SYSTEM SHALL apply that level's
  **profile**: target Arabic ratio, speaking pace, sentence complexity,
  vocabulary band, and target duration (per the A1→C2 table in Origin).
- THE SYSTEM SHALL source the level list, slugs, and names from `config` (CEFR),
  never a hardcoded parallel scheme.

### R2 — Episode formats
- THE SYSTEM SHALL support three formats per episode: **solo+AI**, **owner+group**,
  and **AI-only**, recorded as metadata on the episode.
- WHERE the owner appears, THE SYSTEM SHALL allow either an owner-recorded audio
  track or (if D1=clone) owner-voice TTS for the owner's lines.

### R3 — Script generation (assistive)
- WHEN given a topic + level + format, THE SYSTEM SHALL be able to generate a
  **conversational script** (multi-speaker, level-appropriate Arabic/English mix,
  natural turn-taking) using the existing LLM, for the owner to review/edit.
- THE SYSTEM SHALL never publish a script as audio without owner review.

### R4 — Audio: produce-outside-publish-inside (Phase 1) + optional in-bot (later)
- THE SYSTEM SHALL let the owner **upload/attach a finished audio file** for an
  episode and publish it — no in-bot generation required to launch.
- WHERE in-bot generation is enabled (later phase, flag-gated), THE SYSTEM SHALL
  synthesize multi-speaker audio from a reviewed script via the configured TTS
  (Kokoro default; ElevenLabs if key present).

### R5 — Delivery & routing
- WHEN an episode for level L is published, THE SYSTEM SHALL post it to the
  **level-L zone** (or a dedicated per-level podcast channel), so only students
  at that level (and staff) can see it — reusing the existing level isolation.
- THE SYSTEM SHALL keep an index/catalog of episodes (level, title, format, date).

### R6 — Listening credit (light, optional)
- WHERE enabled, THE SYSTEM SHALL let a student mark an episode listened (or
  detect it) and award a small, capped acknowledgement — never breaking existing
  points/streak rules; fully additive.

### R7 — Safety, consent, permissions
- THE SYSTEM SHALL only voice-clone the owner, only with explicit stored consent.
- THE SYSTEM SHALL never expose podcast channels to suspended students, and SHALL
  obey the admin/hidden/level-isolation permission model.

### R8 — Owner control & preview
- THE SYSTEM SHALL be flag-gated (`sawt_*`), off by default, with a **dry-run
  preview** (show the script and/or the target channel) before anything goes live.

## Out of scope (for now)
- Public/RSS podcast distribution outside Discord.
- Real-time/live AI voice in voice channels.
- Cloning any non-owner voice.
