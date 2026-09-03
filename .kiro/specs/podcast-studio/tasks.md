# Podcast Studio (Sawt) — Implementation Tasks

## Phase 1 — Produce outside, publish inside (MVP)

> Get episodes to students as fast as possible. The owner produces audio with any
> tool; the bot organizes, publishes to the right level zone, and tracks listens.

### Task 1.1 — Data model
- [ ] Add `podcast_episodes` + `podcast_listens` tables to `database.py` schema init.
- [ ] Add CRUD helpers: `create_episode`, `get_episode`, `list_episodes(level)`,
      `publish_episode`, `record_listen`, `has_listened`.
- [ ] Add `PODCAST_LEVEL_PROFILES` to `config.py`.
- [ ] Tests: table creation, CRUD round-trip, level-profile lookup.

### Task 1.2 — Flag registry
- [ ] Register `sawt_episodes` + `sawt_listen_credit` flags in `flag_registry.py`
      under a new `sawt` initiative (`🎙️`, `SAWT`, `podcast studio`).
- [ ] Tests: flags registered, default OFF, initiative exists.

### Task 1.3 — Episode management commands
- [ ] `/create-episode level:<L> title:<T> format:<F>` — native slash (autocomplete
      level from CEFR, format from the three options); accepts an audio file
      attachment; stores as a draft episode. Admin-only.
- [ ] `/publish-episode id:<N>` — dry-run/confirm; posts the episode's audio to
      `#{slug}-podcast` (or creates the channel if it doesn't exist inside the
      zone category, level-isolated); updates `published=1`; stores the message
      ID. Admin-only.
- [ ] `/episodes level:<L>` — lists episodes for a level (title, format, published
      status, listens count). Admin-only for the full view; students see only
      published episodes in their channel.
- [ ] Register all as `!` prefix commands too (auto-exposed in `/admin`).
- [ ] Tests: command registration + admin-gating.

### Task 1.4 — Podcast channel creation + isolation
- [ ] On `/publish-episode`, create `#{slug}-podcast` text channel inside the
      level's zone category if it doesn't exist; apply level-isolation overwrites
      (reuse `_access_kwargs` + the zone isolation pattern from `cmd_setupgate`).
- [ ] Add `#{slug}-podcast` recognition to `level_zone_of` so `setupgate` treats
      it as a zone channel (gateway denied, own level allowed).
- [ ] Add a channel guide entry for `#{slug}-podcast` in `channel_guides.py`.
- [ ] Tests: `level_zone_of` recognizes the podcast channel; isolation holds.

### Task 1.5 — Listening credit
- [ ] `!listened <episode_id>` (student command) or ✅ reaction on the published
      episode message → `record_listen` + award points (configurable, capped,
      one per student per episode). Gated behind `sawt_listen_credit`.
- [ ] Tests: credit awarded once; duplicate ignored; flag-gated.

### Task 1.6 — Steering + docs
- [ ] Update `.kiro/steering/project-rules.md` with the Sawt commands.
- [ ] Add user-facing guide (optional: `#podcast` info in channel_guides).

---

## Phase 2 — Script generation (LLM-assisted)

> The bot writes the conversation script; the owner reviews before recording.

### Task 2.1 — Script generator
- [ ] `sawt_script.generate_script(topic, level, format, speakers)` — builds the
      LLM prompt (level profile → Arabic ratio/pace/vocab/duration), calls the
      existing `ai_engine`, returns the multi-speaker script text.
- [ ] `/generate-script topic:<T> level:<L> format:<F>` — admin command; presents
      the generated script for review in a thread or DM; owner can edit and
      approve. Gated behind `sawt_script_gen`.
- [ ] Tests: prompt includes correct level profile; output has speaker labels.

### Task 2.2 — Script → episode draft
- [ ] An approved script is saved to the episode's `script` column; the owner
      then either records audio externally from it (back to Phase 1 publish) or
      hands it to Phase 3.

---

## Phase 3 — In-bot audio generation (TTS pipeline)

> The bot turns a reviewed script into multi-speaker audio.

### Task 3.1 — Voice registry + consent
- [ ] Add `PODCAST_VOICES` to config (owner = chatterbox_nano, co-hosts = kokoro).
- [ ] `!sawt-consent` — the owner records voice-clone consent (`sawt_voice_consent`
      setting). The clone function refuses without it.
- [ ] Owner uploads a ~10s reference clip → stored as
      `data_persist/sawt/owner_voice_ref.wav`.
- [ ] Tests: consent stored/checked; clone refused without consent.

### Task 3.2 — Install + integrate Chatterbox Nano
- [ ] Add `chatterbox-tts` to requirements.
- [ ] `sawt_tts.clone_speak(text, ref_clip_path)` — synthesize one segment using
      Chatterbox Nano + the owner's reference clip. Returns audio bytes.
- [ ] `sawt_tts.speak(text, voice_id)` — synthesize one segment using Kokoro
      (already integrated via empire-dojo's pipeline). Returns audio bytes.
- [ ] Tests: both functions produce valid audio bytes (short test clips).

### Task 3.3 — Multi-speaker audio assembly
- [ ] `sawt_tts.assemble_episode(script, voices)` — parse script into per-speaker
      segments, synthesize each with the right engine/voice, insert natural pauses
      (50–300ms randomized), concatenate, loudness-normalize (reuse pyloudnorm).
- [ ] `/generate-audio episode:<N>` — admin; generates audio from the episode's
      script; owner previews; then publishes via `/publish-episode`.
- [ ] Tests: assembled audio has correct duration range; multiple speakers present.

### Task 3.4 — Chatterbox v3 / ElevenLabs upgrade path
- [ ] Behind a flag / API key: swap Chatterbox Nano → v3 (GPU) or ElevenLabs API
      for higher quality. Architecture already abstracts the engine per voice.
- [ ] No structural changes needed — just a new engine adapter.

---

## Summary: what the owner gets at each phase

| Phase | Owner effort | Student experience |
|-------|-------------|-------------------|
| **1 (MVP)** | Record audio with any tool → upload + publish | 🎙️ Podcast episodes appear in their level zone; listen + earn credit |
| **2** | Give a topic → bot writes the script → owner reviews | Same as Phase 1 (owner still records externally from the script) |
| **3** | Give a topic → bot writes the script AND generates audio | Same, but fully automated end-to-end — owner just reviews + publishes |
