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

| File | Speaker (source) | Used for |
|------|------------------|----------|
| `male_us_1.ogg` | Mike Delph (Indiana) — Wikimedia Commons | Leo / male lead |
| `male_us_2.ogg` | Aaron Halfaker (Minnesota) — Wikimedia Commons | spare male |
| `female_us_1.ogg` | Mary Mackey (Indiana) — Wikimedia Commons | spare female |

## Adding new assets

Only add audio that is **CC0, public domain, or CC-BY** (with attribution
recorded here). Never add copyrighted/commercial tracks. Prefer Wikimedia
Commons, freepd.com, or clearly-licensed CC0 libraries.
