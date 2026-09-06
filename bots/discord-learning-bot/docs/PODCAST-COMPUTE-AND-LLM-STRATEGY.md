# Empire English Chronicles — Compute & LLM Strategy

**Decision record.** Answers two owner questions (2026-09-06):
1. *"For the Groq limit we need to check for a better alternative if possible."*
2. *"Check if Kaggle can help us in this podcast project at all or not."*

Everything below is measured against the live systems, not assumed.

---

## 1. LLM providers — what was actually wrong

The problem was **not** simply "Groq is rate-limited". There were two faults, and the
second one is why the first one hurt.

### Fault A — Groq's configured model is the wrong tool for long text
`GROQ_MODEL = openai/gpt-oss-120b` is a **reasoning** model: it spends part of its
token budget thinking before answering. On a short JSON reply that is fine. On a
CEFR-length episode it produces:

| `max_tokens` | Result |
|---|---|
| unset | truncated JSON → unparseable |
| 8000 | **HTTP 413** — the cap covers prompt **+** completion together |
| ~1850 | **HTTP 200 with EMPTY content** — budget consumed by reasoning |
| 2000 | ✅ worked once (725-word script) |

It also rate-limits quickly on the free tier (**HTTP 429**, `Retry-After` 8–30 s).

### Fault B — the Gemini fallback had been silently DEAD 🔴
Gemini is the fallback for the **whole bot**, not just the podcast. Every call was
returning **404**, because the configured models are **retired**:

```
gemini-2.5-flash-lite → 404 "no longer available to new users …
                              use models/gemini-3.5-flash-lite"
gemini-2.5-flash      → 404 "… use models/gemini-3.6-flash"
gemini-2.5-pro        → 404
```

So when Groq rate-limited, **there was no safety net at all** — the pipeline simply
produced no episode. This is the single most important finding of the investigation.

### What was changed

| Change | Why |
|---|---|
| `GEMINI_MODEL` → **`gemini-3.5-flash-lite`** | the previous default is retired |
| Added **`GEMINI_MODEL_FALLBACKS`** (`gemini-3.1-flash-lite`, `gemini-3.6-flash`, `gemini-flash-lite-latest`) | all five verified working live on 2026-09-06 |
| `_call_gemini` walks the list, retrying on **404 / 503 / 429 / 500** | 404 = retired model, 503 = temporary demand spike; another model usually works |
| Story generation now tries **Gemini FIRST**, Groq second | measured: Groq failed 3 consecutive attempts on a CEFR-length episode while Gemini returned a complete 586-word script |
| Groq retry ladder responds per failure mode | **413 → shrink**, **empty-200 → grow**, **429 → back off**; a blanket retry fixes none of these |
| Length target **over-asks ~1.3×** | models under-deliver: asked 780 words, got 586 (75%) |

> **Note:** Groq remains primary for the rest of the bot, where it is genuinely fast
> for short structured answers. The podcast is the exception, and deliberately so.

### Alternatives considered, and why we did not add one yet
Adding a third provider (OpenRouter / Cerebras / Together / DeepSeek) is **not
needed**: the real problem was a dead fallback, and with Gemini working there are now
two independent providers plus five Gemini model options. Each extra provider costs
another API key to hold, rotate and monitor. **Revisit only if Gemini and Groq fail
together in practice** — the logs will show it, since every failure now records the
provider, model, status and token budget.

---

## 2. Kaggle — genuinely useful, but not for the daily pipeline

### Where the render time actually goes (measured, 26-line episode)

| Stage | Time |
|---|---|
| Kokoro cast (18 lines) | ~3.5 s/line → **~63 s** |
| Chatterbox clone, Mai only (8 lines) | ~16 s/line → **~130 s** |
| **Total render** | **~200 s** (v1, cloning every voice, was ~450 s) |

Extrapolated to a full A2 episode (~1020 words, ~45 lines): **≈ 5–7 minutes**.
GitHub Actions allows **120 minutes**. There is ~20× headroom.

**Kokoro needs no GPU at all** — it is ONNX/CPU by design. The only GPU-hungry part
is Mai's cloned voice, which is a minority of each episode.

### Kaggle free tier (verified 2026)
- **~30 GPU hours/week** (T4 ×2 = 2×16 GB, or P100 16 GB), quota resets weekly —
  [Kaggle docs](https://www.kaggle.com/docs/efficient-gpu-usage)
- **~12-hour session limit**, automatic disconnects, shared allocation
- Explicitly intended for *prototyping, education and small-to-medium training* —
  **not production or long-running inference**
  ([overview](https://electronics.alibaba.com/question/free-gpu-access-in-2026-real-options-limits))

*(Sources summarised; content rephrased for licensing compliance.)*

### Verdict

❌ **Do NOT use Kaggle for the daily automated pipeline.**
- Kaggle notebooks are **interactive**; there is no dependable free scheduler, and
  sessions can be disconnected. A podcast that must publish every morning cannot
  depend on that.
- GitHub Actions already does this job: **scheduled**, unattended, free for this
  repo, secrets handled, and the render fits in ~5–7 min of a 120-min allowance.
- Kaggle's own guidance excludes production workloads.

✅ **DO use Kaggle for heavy one-off / experimental work**, where its free GPU is a
real advantage and no schedule is involved:

| Use case | Why Kaggle wins |
|---|---|
| **Bulk voice benchmarking** — all 54 Kokoro voices × several speeds × several surfaces | this session benchmarked ~20 voices × 2 speeds on CPU and it was the slowest part of the work; a GPU session does far more, far faster |
| **A better clone of Mai's voice** — trying higher-quality clone models (XTTS/StyleTTS2-class) that realistically need a GPU | would improve the one voice the owner actually likes; pure experimentation, no schedule |
| **Building the Podcast Lab** — batch-normalising hundreds of music/ambience/SFX assets, auto-tagging by mood | a single long session beats many short CI runs |
| **Pre-rendering a backlog** — e.g. a week of episodes in one GPU session as a buffer | useful as insurance, not as the daily mechanism |
| **Any future fine-tuning** | the ecosystem already uses Kaggle this way for LoRA training in `macal-empire-image-forge` |

### Recommended split

```
DAILY, AUTOMATIC  →  GitHub Actions   (generate → render → quality gate → commit → post)
HEAVY, OCCASIONAL →  Kaggle GPU       (voice research, clone quality, asset library, backlogs)
```

This keeps the thing that must never fail on the platform built for reliability, and
uses Kaggle's free GPU exactly where it adds value.

---

## 3. What to watch

- **Model retirement is a recurring failure mode.** A 404 from Gemini means *the
  model was retired*, not that the key or the code broke. Re-list the models the key
  can use (`GET /v1beta/models`) and update `GEMINI_MODEL`.
- **Groq's free tier will keep rate-limiting.** That is now survivable, not fatal.
- **If both providers fail**, the daily job must not publish a bad or missing episode
  silently — that is the fail-closed behaviour built in Phase 2 of the spec.
