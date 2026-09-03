# Podcast Studio (Sawt) — Design

## Decisions resolved

- **D1 — Owner's voice:** CLONE. The owner records a ~10-second reference clip;
  Chatterbox Nano uses it to synthesize the owner's lines from text. The clip is
  stored server-side as `data_persist/sawt/owner_voice_ref.wav`. Consent is
  recorded via a `!sawt-consent` command that stores `sawt_voice_consent=yes` in
  settings (the clone function refuses to run without it).
- **D2 — TTS engine / budget:** FREE. Chatterbox Nano (110M, MIT, CPU) for
  voice-cloned lines; Kokoro (82M, Apache 2.0, CPU, already integrated) for
  non-clone AI co-host voices. Both run on the existing bot server. ElevenLabs
  is a later drop-in upgrade behind an API key flag.
- **Phase strategy:** produce-outside first (Phase 1), then script generation
  (Phase 2), then in-bot audio (Phase 3). Owner gets value from Phase 1 alone.

## Architecture overview

```
                     ┌──────────────┐
  Owner produces     │  Episode DB  │ ← episode metadata
  audio externally   │ (SQLite tbl) │   (level, title, format, audio_url,
  OR in-bot pipeline │              │    speakers, created_at, published)
                     └──────┬───────┘
                            │ /publish-episode
                            ▼
               ┌────────────────────────┐
               │  Level-zone routing    │ post to #{slug}-podcast
               │  (reuses config.CEFR)  │ or per-level daily-tasks
               └────────────┬───────────┘
                            │
                            ▼
               ┌────────────────────────┐
               │  Student interaction   │ listen → mark → credit
               │  (reaction / command)  │
               └────────────────────────┘
```

## Data model

### `podcast_episodes` table (new, in the existing SQLite DB)

| Column | Type | Description |
|--------|------|-------------|
| `episode_id` | INTEGER PK AUTOINCREMENT | |
| `level` | TEXT NOT NULL | CEFR code (A1–C2) |
| `title` | TEXT NOT NULL | Episode title (bilingual) |
| `description` | TEXT | Short description |
| `format` | TEXT NOT NULL | `solo_ai`, `owner_group`, `ai_only` |
| `speakers` | TEXT | JSON list of speaker names/roles |
| `audio_url` | TEXT | URL or local path to the audio file |
| `audio_message_id` | TEXT | Discord message ID once published |
| `duration_seconds` | INTEGER | Approximate length |
| `arabic_ratio` | REAL | Target Arabic % (from level profile) |
| `script` | TEXT | The conversation script (if generated) |
| `published` | INTEGER DEFAULT 0 | 0=draft, 1=published |
| `published_at` | TEXT | ISO datetime of publication |
| `created_at` | TEXT DEFAULT (datetime('now')) | |

### `podcast_listens` table (new)

| Column | Type | Description |
|--------|------|-------------|
| `discord_id` | TEXT NOT NULL | FK → members |
| `episode_id` | INTEGER NOT NULL | FK → podcast_episodes |
| `listened_at` | TEXT DEFAULT (datetime('now')) | |
| PK | (discord_id, episode_id) | One credit per episode |

### Level profiles (in config, not DB)

```python
PODCAST_LEVEL_PROFILES = {
    "A1": {"arabic_ratio": 0.40, "pace": "very_slow", "vocab": "basic",
            "duration_min": 180, "duration_max": 300},
    "A2": {"arabic_ratio": 0.20, "pace": "slow", "vocab": "elementary",
            "duration_min": 300, "duration_max": 420},
    "B1": {"arabic_ratio": 0.05, "pace": "moderate", "vocab": "everyday",
            "duration_min": 420, "duration_max": 600},
    "B2": {"arabic_ratio": 0.00, "pace": "natural", "vocab": "varied",
            "duration_min": 600, "duration_max": 720},
    "C1": {"arabic_ratio": 0.00, "pace": "fast", "vocab": "advanced",
            "duration_min": 720, "duration_max": 900},
    "C2": {"arabic_ratio": 0.00, "pace": "native", "vocab": "academic",
            "duration_min": 900, "duration_max": 1200},
}
```

## Phase 1 — Produce outside, publish inside (MVP)

**What it gives the owner:** upload a finished audio file + metadata → the bot
publishes it to the right level zone, students listen + earn credit, the owner
can manage episodes via commands.

### New commands (Phase 1)

| Command | What |
|---------|------|
| `/create-episode level:<L> title:<T> format:<F>` | Create a draft episode; attach audio file |
| `/publish-episode id:<N>` | Publish to the level zone (dry-run/confirm) |
| `/episodes level:<L>` | List episodes for a level (admin view) |
| `!listened <episode_id>` | Student marks as listened → credit (once per ep) |

### Delivery to students

Each CEFR zone gets a `#{slug}-podcast` text channel (e.g. `#a1-podcast`) OR
episodes post directly into the existing `#{slug}-daily-tasks` channel as a
special "🎙️ Podcast" message. Decision: **dedicated `#{slug}-podcast` channel**
(cleaner, doesn't clutter daily tasks, can be pinned/browsed). Created by
`/setupgate` when the `sawt_episodes` flag is on; level-isolated like every
other zone channel.

### Listening credit

A ✅ reaction on the episode message (or `!listened <id>`) records one listen
per student per episode. Awards a small, capped credit (e.g. 5 points, config-
tunable, never exceeding the daily task cap). Gated behind `sawt_listen_credit`.

## Phase 2 — Script generation (LLM-assisted)

The owner gives a topic + level + format; the bot's existing LLM (ai_engine)
generates a multi-speaker script following the level profile (Arabic ratio,
pace, vocabulary). The owner reviews/edits the script in a thread or DM, then
either records the audio externally from it, or (Phase 3) hands it to the TTS.

### Script prompt structure

```
You are writing a podcast script for an English learning community.
Level: {level} ({name}) — {profile description}
Arabic ratio: {ratio}% (explain hard words in Arabic, rest in English)
Pace: {pace}
Format: {format} (speakers: {speakers})
Topic: {topic}

Write a natural conversation with turn-taking, back-channels ("mm-hmm",
"right", "exactly"), pauses [PAUSE], and natural transitions. Each speaker
line is prefixed with their name. Keep vocabulary within the {vocab} band.
Target duration: ~{duration} minutes of spoken content.
```

## Phase 3 — In-bot audio generation (TTS pipeline)

Synthesizes multi-speaker audio from a reviewed script:

1. Parse the script into per-speaker segments.
2. For the **owner's lines**: use Chatterbox Nano with the stored reference clip
   (`data_persist/sawt/owner_voice_ref.wav`). Consent check: `sawt_voice_consent`
   must be `yes` in settings.
3. For **AI co-host lines**: use Kokoro with distinct voice presets (e.g.
   `am_adam` for a male co-host, `af_heart` for female).
4. Concatenate segments with natural pauses between speakers.
5. Apply loudness normalization (reuse the existing Kokoro pipeline's
   `pyloudnorm` normalizer from empire-dojo).
6. Store the final audio; the owner previews before publishing.

### Voice registry (config)

```python
PODCAST_VOICES = {
    "owner": {"engine": "chatterbox_nano", "ref_clip": "owner_voice_ref.wav"},
    "adam":  {"engine": "kokoro", "voice_id": "am_adam"},
    "sarah": {"engine": "kokoro", "voice_id": "af_sarah"},
    "heart": {"engine": "kokoro", "voice_id": "af_heart"},
}
```

## Flag registry (sawt initiative)

| Flag | Default | Phase | Description |
|------|---------|-------|-------------|
| `sawt_episodes` | OFF | 1 | Episode management + publishing |
| `sawt_listen_credit` | OFF | 1 | Listening credit (points on ✅) |
| `sawt_script_gen` | OFF | 2 | LLM script generation |
| `sawt_tts_pipeline` | OFF | 3 | In-bot audio generation (Chatterbox+Kokoro) |
| `sawt_voice_clone` | OFF | 3 | Owner voice cloning (requires consent) |

## Security & permissions

- Podcast channels are created inside each CEFR zone category → inherit level
  isolation automatically (only that level's role can see them).
- `setupgate` recognizes `#{slug}-podcast` as a zone channel (add to
  `level_zone_of` detection).
- Suspended students cannot see them (gateway role denied on zones).
- Episode management commands are admin-only.
- Voice cloning requires explicit stored consent; the ref clip is stored
  server-side, never exposed to students.



## Phase 3 — REVISED architecture decision (2026-09-04)

Investigation found two hard infra facts that change the Phase 3 plan:

1. **The Discord bot runs in a 512MB / 0.5-CPU container** (docker-compose.yml).
   Chatterbox voice-cloning needs ~2–3GB + real CPU; even Kokoro is not
   installed in the bot. Running any TTS *inside the bot process* would OOM/crash
   it. So in-process synthesis is off the table.
2. **empire-dojo already solved this**: it renders all Kokoro audio **offline in
   GitHub Actions** (.github/workflows/audio-render.yml) and commits the files.
   Its own comment notes the *voice-cloning engines needed a GPU*, which is why
   dojo uses Kokoro. Runtime never synthesizes.

**Decision: mirror dojo — "render offline, publish inside."**
- The bot does NOT synthesize audio in-process. It handles consent, the voice
  registry, script→segment parsing, and publishing (Phase 1 commands).
- A GitHub Actions workflow renders a script into a multi-speaker episode
  (Chatterbox for the owner's cloned lines from a stored reference clip; Kokoro
  for AI co-hosts), then the finished audio is attached via /create-episode.
- The bot-side TTS adapter is **pluggable and degrades gracefully**: if the
  engine isn't importable on the host (the normal case for the 512MB bot), it
  returns a clear "render this offline" result instead of crashing. This keeps
  everything flag-gated, testable, and safe, and leaves a clean seam to plug in
  the CI renderer (or a future dedicated GPU service / ElevenLabs API) with no
  redesign.

Bot-side scope for this phase (all additive, flag-gated, off by default):
- `sawt_voice_clone` + `sawt_tts_pipeline` flags.
- `!sawt-consent` — records the owner's voice-clone consent; the clone path
  refuses without it. Reference clip stored at data_persist/sawt/owner_voice_ref.*.
- `sawt_tts` module: parse a script into per-speaker segments, a voice registry
  (owner→clone, co-hosts→Kokoro voices), and an `assemble_episode` interface
  that calls a pluggable engine adapter — which no-ops with a clear message when
  no engine is available in-process.
- `/generate-audio` (admin, flag-gated): wires the pipeline; on the bot host it
  explains that rendering happens via the offline workflow, and points the owner
  to it. When an engine IS available (CI / GPU host / future service) the same
  code path produces the audio.


## Phase 3 — Offline renderer (shipped 2026-09-02)

The "render offline" half of the decision above is now concrete:

- **`bots/discord-learning-bot/scripts/render_podcast_episode.py`** — the CLI
  renderer. It imports the bot's OWN `src.sawt_tts.parse_script` + `voice_for`,
  so the renderer and the bot can never disagree on how a script is split or
  which voice a speaker gets. Co-host lines synthesize with Kokoro
  (`af_heart` / `am_adam`); owner lines use a Chatterbox clone from a reference
  clip when one is supplied, and otherwise fall back to a Kokoro voice so an
  episode always renders. Delivery pace is graded per level from the profile's
  `pace` descriptor (`very_slow` → `native`). Segments are stitched with natural
  pauses (longer on speaker change and on `[PAUSE]`) and peak-normalized.

- **`.github/workflows/podcast-render.yml`** — the `workflow_dispatch` renderer,
  modeled on empire-dojo's `audio-render.yml`. Inputs: `script_path` (a file
  under `content/podcast-scripts/`), `level`, optional `voice_ref_url` + `clone`
  for owner cloning. It downloads the verified Kokoro model, installs Chatterbox
  only when cloning, runs the script, and uploads the MP3 as the
  **`episode-audio`** artifact.

- **`content/podcast-scripts/`** — where reviewed scripts live (one `.txt` per
  episode, `Speaker: text` lines). See its README for the full owner flow.

**Owner flow:** `/generate-script` → review → save script to
`content/podcast-scripts/<name>.txt` → run **podcast render (sawt)** → download
the `episode-audio` MP3 → `/create-episode` (attach MP3) → `/publish-episode`.
`/generate-audio` on the bot prints this exact plan + these steps.

**Voice cloning** stays owner-only + consent-gated: `!sawt-consent` (attach the
clip) records consent and stores the clip server-side; the same clip is passed
to the renderer via `voice_ref_url` (with `clone: true`) to synthesize the
owner's lines. Cloning is best-effort — if Chatterbox can't install/run, the
owner's lines fall back to Kokoro and the episode still renders.
