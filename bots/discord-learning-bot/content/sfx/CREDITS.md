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
| `male_us_1.ogg` | Jerry Coyne (Voice intro project) — Wikimedia Commons | Public domain / CC | Leo / male lead — trimmed, pitch-adjusted for a younger read, de-muffled |
| `male_us_2.ogg` | Aaron Halfaker (Minnesota) — Wikimedia Commons | Public domain / CC | Omar / spare male — de-muffled |
| `female_us_1.ogg` | Mary Mackey (Indiana) — Wikimedia Commons | Public domain / CC | Sara / elder / spare female — de-muffled |

> **Audio note:** the character reference clips are processed with a presence/air
> high-shelf ("de-muffle") so cloned voices don't sound telephone-like. Leo's
> original reference (Mike Delph) had almost no energy above 3.4 kHz and could
> not be de-muffled by EQ, so it was replaced with a clearer source and given a
> younger pitch.
| `owner_voice.ogg` | **Mahmoud Ashri** (EEC founder) — own recording, consented | Owner-owned, EEC use | **Narrator + owner's character** — the owner's real voice |
| `mai_voice.ogg` | **Mai** — own recording, consent on file | Consent-gated, EEC use | **Maya** — Mai's real, consented voice |

### The Narrator + Maya are real EEC voices (owner requirement)

The owner requires the Narrator to be **his own voice** and Maya to be **Mai's voice**.
`owner_voice.ogg` and `mai_voice.ogg` are cleaned + de-muffled from their real
recordings and committed so the daily pipeline stays self-contained (no expiring
URLs). A runtime `--ref-clip` / `--ref-mai` still overrides (e.g. a fresh, higher-
quality studio recording). Mai's consent is recorded in
`content/voice-clone-consent.md`; these clips are for **EEC educational content
only** and are never shared with third parties (see that document).

## Adding new assets

Only add audio that is **CC0, public domain, or CC-BY** (with attribution
recorded here). Never add copyrighted/commercial tracks. Prefer Wikimedia
Commons, freepd.com, or clearly-licensed CC0 libraries.
