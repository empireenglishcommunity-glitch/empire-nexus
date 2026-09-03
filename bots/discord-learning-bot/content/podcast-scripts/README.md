# Podcast scripts (Sawt صوت) — offline render inputs

Drop a **reviewed** episode script here (a `.txt` file) and run the
**"podcast render (sawt)"** GitHub Actions workflow to synthesize its audio.

## How to render an episode

1. Generate a draft script in Discord with `/generate-script`, review/edit it.
2. Save the final script as a text file in this folder, e.g.
   `content/podcast-scripts/a1-coffee.txt`. Each line is `Speaker: text`:

   ```
   AI co-host: Welcome to the Empire English podcast!
   Host (you): Good morning everyone. صباح الخير.
   AI co-host: Today we talk about coffee.
   ```

   - `AI co-host` / `AI guest` lines → Kokoro voices (`af_heart`, `am_adam`).
   - `Host (you)` / `owner` lines → your **cloned voice** (needs a reference clip;
     otherwise they fall back to a Kokoro voice so the episode still renders).

3. Run the **podcast render (sawt)** workflow (Actions tab → Run workflow):
   - `script_path`: path to the file above (relative to the bot dir).
   - `level`: the CEFR level (A1–C2) — controls the delivery pace.
   - `voice_ref_url` *(optional)*: a direct URL to your ~10s voice reference clip
     (wav/mp3/…) to enable cloning for your lines. Leave blank to skip cloning.

4. When the run finishes, download the **episode-audio** artifact (an MP3).
5. Back in Discord, create the episode with the finished audio attached:
   `/create-episode` (attach the MP3), then `/publish-episode`.

The renderer reuses the bot's own `src.sawt_tts.parse_script` + `voice_for`, so
the voices and segmentation always match what `/generate-audio` plans.

> Voice cloning is **owner-only and consent-gated**. Record consent + your clip
> in Discord with `!sawt-consent` (attach the clip). The same clip can be passed
> to the renderer via `voice_ref_url`.
