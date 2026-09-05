# Empire Chronicles — Sound & Music Credits

All audio assets in this folder are used under free/open licenses. The renderer
(`scripts/render_podcast_episode.py`, story mode) mixes them under the narration.

## Sound effects

| File | Source | License | Notes |
|------|--------|---------|-------|
| `knock.ogg` | "Knock on door" — Wikimedia Commons | Public domain / CC | A real triple-knock, extracted + normalized. |
| `creak.ogg` | "Door handle creaking" — Wikimedia Commons | Public domain / CC | A real door-handle creak, trimmed + normalized. |

## Music

| File | Track | Composer | License | Attribution required |
|------|-------|----------|---------|----------------------|
| `music_mystery.ogg` | "Lights (Creepy Ambient Suspense)" | **Rafael Krux** | **CC-BY 4.0** | **YES** |

### Required attribution for the music (CC-BY 4.0)

When an episode using `music_mystery.ogg` is published, include this credit in
the episode description / channel post:

> Music: "Lights" by Rafael Krux (freepd.com / filmmusic.io) — licensed under
> Creative Commons Attribution 4.0 (https://creativecommons.org/licenses/by/4.0/).

The bot's publish flow should append this line automatically for any episode
that uses a CC-BY track (see the storytelling publish path).

## Character voice references (`voices/`)

Distinct clean American-English voices used as reference clips for the
non-cloned story characters (so no character reuses another's voice). All are
public-domain / CC "Voice intro project" recordings from Wikimedia Commons,
trimmed + normalized.

| File | Speaker (source) | License | Used for |
|------|------------------|---------|----------|
| `male_us_1.ogg` | Mike Delph (Indiana) — Wikimedia Commons | Public domain / CC | Leo / male lead |
| `male_us_2.ogg` | Aaron Halfaker (Minnesota) — Wikimedia Commons | Public domain / CC | spare male |
| `female_us_1.ogg` | Mary Mackey (Indiana) — Wikimedia Commons | Public domain / CC | spare female |
| `narrator_default.ogg` | Terry Bollinger (Voice intro project) — Wikimedia Commons | **CC-BY 4.0** | **default Narrator** (owner slot) — used when no owner clip is supplied |
| `maya_default.ogg` | Jessamyn West (Voice intro project) — Wikimedia Commons | **CC-BY-SA 4.0** | **default Maya** (mai slot) — used when no Mai clip is supplied |

### Why the two `*_default.ogg` clips exist (self-contained pipeline)

The daily automation (`.github/workflows/podcast-daily.yml`) must render an episode
every day with **no secrets and no expiring URLs**. Discord CDN links expire in
~24h, so relying on them for a daily cron is not viable. These two committed clips
give the Narrator and Maya a distinct, freely-licensed default voice so the pipeline
is fully self-contained. A real runtime clip (`--ref-clip` for the owner's own voice,
`--ref-mai` for Mai's consented voice) still **overrides** these defaults.

### Required attribution for the default voices

`narrator_default.ogg` is **CC-BY 4.0** and `maya_default.ogg` is **CC-BY-SA 4.0** —
both require attribution wherever an episode using them is published:

> Voices: Terry Bollinger (CC-BY 4.0) and Jessamyn West (CC-BY-SA 4.0), from the
> Wikimedia Commons Voice intro project, trimmed + normalized. Licensed under
> Creative Commons — https://creativecommons.org/licenses/

## Adding new assets

Only add audio that is **CC0, public domain, or CC-BY** (with attribution
recorded here). Never add copyrighted/commercial tracks. Prefer Wikimedia
Commons, freepd.com, or clearly-licensed CC0 libraries.
