# Empire English — Phase 0 Content Assets (Bilingual, Arabic-Led)

**Content Pack v1.0** · *Confidential* · **Date:** June 2026

> **What this is.** The ready-to-use **copy and content** that fills the logic defined in `PHASE_0_IMPLEMENTATION_SPEC.md` §16. Every user-facing string for the Phase 0 Telegram bot lives here, in **Arabic (lead) + English**. This is content only — it does **not** build, deploy, or configure anything.

> **Parent docs.** Fills `PHASE_0_IMPLEMENTATION_SPEC.md` (§4 bot, §5 quiz, §6 CRM, §7 consent, §8 booking). Tone, pricing ladder, and positioning follow `CHANNEL_GROWTH_CONVERSION_BLUEPRINT.md` (v1.1) and `STRATEGIC_EXPANSION_ROADMAP.md`.

---

## How to use this pack (conventions)

### Variables (replace at build time — never hard-code)
Curly-brace tokens are filled by the bot/CRM or set once in the Sheets `Config` tab:

| Variable | Meaning | Source |
|---|---|---|
| `{first_name}` | User's Telegram first name | Telegram |
| `{level_name}` | Provisional level label | Quiz result |
| `{goal}` | Chosen goal (confidence/interview/travel/exam/accent) | Quiz Q6 |
| `{track}` | Core or Intensive | Quiz Q7 |
| `{CORE_PRICE}` | Core membership price (local-friendly) | **Reserved — not used day one (pricing via call/DM)** |
| `{CITIZEN_PRICE}` | Citizen tier price | **Reserved — not used day one (pricing via call/DM)** |
| `{FOUNDING_PRICE}` | Founding Citizen one-time price | **Reserved — not used day one (pricing via call/DM)** |
| `{FOUNDING_SEATS}` | Remaining founding seats | **Discussed on call/DM; must be real** |
| `{CALL_URL}` | Cal.com booking link (with `?src=bot&tid=`) | Config |
| `{DISCORD_INVITE}` | Discord community invite | Config |
| `{GROUP_INVITE}` | Telegram discussion-group link | Config |
| `{RESOURCE_LINK}` | "3 American Sounds" file/link | Config |

> **PRICING — DAY-ONE DECISION (locked).** Prices are **not displayed publicly** in the bot on launch. Pricing is handled **via a short call or DM**, so the founder can price-discover and match the right tier to each lead while the audience is small. The `{CORE_PRICE}` / `{CITIZEN_PRICE}` / `{FOUNDING_PRICE}` / `{FOUNDING_SEATS}` tokens are **reserved for a later phase** and are not used in any go-live copy. Canonical pricing home remains `STRATEGIC_EXPANSION_ROADMAP.md` §7.

### Style rules
- **Arabic-led:** Arabic appears first, English second. Default bot language = Arabic; English on toggle.
- **Tone:** warm, personal, founder-voice; confident but honest (no "sound 100% native" promises — lead with attainable wins: confidence, clarity, fluency, scores). Mirrors the audit's under-promise/over-deliver guardrail.
- **Arabic register (locked):** **Modern Standard Arabic (MSA)** — kept **fresh and conversational**, not stiff or formal. Pan-Arab so it reads naturally from the Gulf to North Africa; short sentences, warm tone, minimal jargon, light use of everyday phrasing. Beginners must be able to read it easily.
- **RTL note:** Arabic strings render right-to-left. In the bot, store Arabic and English as separate fields; do not mix LTR/RTL in one line where avoidable. Emoji placement may shift in RTL — test on-device.
- **Length:** keep each bot message short (1–3 lines); prefer buttons over paragraphs.
- **Buttons:** button labels are bilingual on one line where short (`عربي / English`); longer flows use the user's stored language only.

### Asset index (maps to spec §16)
1. String Table (foundation keys) · 2. Welcome · 3. Quiz (7 Q + scoring) · 4. Plan templates (×4) · 5. "3 American Sounds" quick-win · 6. How Empire works + pricing · 7. What you'll get on the call · 8. Community invites · 9. Consent + opt-out · 10. Hot-lead alert (internal).


---

## Asset 1 — String Table (foundation keys)

> Goes into the Sheets `String_Table` tab as `key | ar | en`. These are the shared/system strings. Flow-specific copy (welcome, quiz, plans, etc.) is in Assets 2–10 and should also be keyed into this table at build time. Keep keys stable; edit text freely.

| key | ar | en |
|---|---|---|
| `lang_toggle` | English 🇬🇧 | عربي 🇸🇦 |
| `menu_title` | 🏛 أهلاً بك في Empire English | 🏛 Welcome to Empire English |
| `btn_quiz` | 🎯 حدّد مستواي (دقيقتان) | 🎯 Find my level (2 min) |
| `btn_resource` | 🎁 هديتي المجانية | 🎁 My free gift |
| `btn_how` | 📚 كيف يعمل Empire + الأسعار | 📚 How Empire works + pricing |
| `btn_call` | 📅 احجز مكالمة مجانية | 📅 Book a free call |
| `btn_community` | 💬 انضم للمجتمع | 💬 Join the community |
| `btn_back` | ↩️ رجوع للقائمة | ↩️ Back to menu |
| `btn_yes` | نعم | Yes |
| `btn_no` | لا | No |
| `btn_start_quiz` | لنبدأ الاختبار | Start the quiz |
| `fallback` | لم أفهم ذلك تمامًا 🙂 اختر من القائمة بالأسفل. | I didn't quite get that 🙂 Pick an option below. |
| `help_text` | أنا بوت Empire English. أساعدك تعرف مستواك، تحصل على هدية مجانية، تعرف كيف نعمل، وتحجز مكالمة. اكتب /menu للقائمة، أو /language لتغيير اللغة. لإيقاف الرسائل: /stop | I'm the Empire English bot. I help you find your level, get a free gift, learn how we work, and book a call. Send /menu for the menu, /language to switch language. To stop messages: /stop |
| `talk_human` | تفضّل التحدث مع إنسان؟ احجز مكالمة مجانية 👇 | Prefer to talk to a human? Book a free call 👇 |
| `done_thanks` | تمام! 🙌 | Done! 🙌 |
| `optout_done` | تم إيقاف الرسائل الترويجية. تقدر ترجع في أي وقت بكتابة /menu. | Marketing messages stopped. You can return anytime with /menu. |

> **Build note:** the main menu is rendered as a 5-button inline keyboard using `btn_quiz`, `btn_resource`, `btn_how`, `btn_call`, `btn_community`, under `menu_title`.

---

## Asset 2 — Welcome message (`/start`, founder voice)

> Sent on first `/start` (and on deep-link entry). Two short messages, then the immediate quiz nudge. Default Arabic; offer the language toggle on message 1. Fires CRM upsert (status `New`) + event `JOINED_BOT` (spec §4.4 Flow A).

### Message 1 — greeting + language toggle

**AR:**
> أهلاً بك في **Empire English** 🏛
> أنا هنا عشان أساعدك تتكلم إنجليزي بثقة — خطوة بخطوة، بنظام واضح، مش مجرد دروس.
> تحب نكمل بالعربي ولا English؟

*(Inline buttons: `عربي 🇸🇦` · `English 🇬🇧`)*

**EN:**
> Welcome to **Empire English** 🏛
> I'm here to help you speak English with confidence — step by step, with a clear system, not just random lessons.
> Continue in العربية or English?

*(Inline buttons: `عربي 🇸🇦` · `English 🇬🇧`)*

### Message 2 — the promise + quick win

**AR:**
> رائع يا {first_name} 👋
> في Empire ما نعتمد على "معلم شاطر" — نعتمد على **نظام** يمشي معك كل يوم: نطق أمريكي من أول يوم، ممارسة كلام حقيقية، ومجتمع يدعمك.
> تعرف وش أفضل بداية؟ نشوف مستواك الحالي في **دقيقتين** بس — وبعدها أعطيك خطة شخصية مجانية.

*(Inline buttons: `btn_start_quiz` · `btn_resource` · `↩️ القائمة`)*

**EN:**
> Awesome, {first_name} 👋
> At Empire we don't rely on a "talented teacher" — we rely on a **system** that walks with you every day: American pronunciation from day one, real speaking practice, and a community that backs you.
> Best first step? Let's find your current level in just **2 minutes** — then I'll give you a free personalized plan.

*(Inline buttons: `Start the quiz` · `My free gift` · `↩️ Menu`)*

> **Tone check:** message leads with the "system over instructor" wedge (a core differentiator), gives a concrete, attainable promise, and offers a 2-minute micro-commitment — not a hard sell. No outcome over-promise.


---

## Asset 3 — The 2-Minute Level Quiz (7 questions, bilingual + scoring)

> Implements spec §5. All tap-to-answer (inline buttons / Telegram quiz). **Q1–Q5 are scored** (0–3 points each → sum 0–15 → provisional level). **Q6 = goal tag**, **Q7 = time/track** (not scored). Intro + per-question copy below; the score→level map and edge rule follow.

### Quiz intro

**AR:**
> تمام يا {first_name}! 7 أسئلة سريعة، تقريبًا دقيقتين. اضغط الإجابة الأقرب لك — ما في صح وغلط، بس نعرف نقطة بدايتك. 🚀

**EN:**
> Great, {first_name}! 7 quick questions, about 2 minutes. Tap the answer closest to you — there's no right or wrong, we just find your starting point. 🚀

### Q1 — Self-assessment (scored)

**AR:** كيف تصف إنجليزيتك اليوم؟
**EN:** How would you describe your English today?

| Option (AR / EN) | Points |
|---|---|
| أعرف حروف/كلمات بسيطة فقط / I only know letters or a few words | 0 |
| أكوّن جُمل بسيطة بصعوبة / I make simple sentences with effort | 1 |
| أتعامل مع محادثات يومية / I handle daily conversations | 2 |
| أتحدث بطلاقة عن معظم المواضيع / I speak fluently on most topics | 3 |

### Q2 — Speaking (scored)

**AR:** تقدر تعرّف عن نفسك بالإنجليزي لمدة 30 ثانية؟
**EN:** Can you introduce yourself in English for 30 seconds?

| Option (AR / EN) | Points |
|---|---|
| لا، ليس بعد / Not yet | 0 |
| بصعوبة وبجُمل قصيرة / With effort, short sentences | 1 |
| نعم، بشكل مقبول / Yes, reasonably well | 2 |
| نعم، بسهولة وثقة / Yes, easily and confidently | 3 |

### Q3 — Grammar, objective (scored)

**AR:** أي جملة صحيحة؟
**EN:** Which sentence is correct?

| Option (AR shown as English item / EN) | Points |
|---|---|
| "She go to work every day." | 0 |
| "She goes to work every day." ✅ | 3 |
| "She going to work every day." | 1 |
| "She is go to work every day." | 0 |

> Scoring: correct = 3, the "-ing/almost" distractor = 1, others = 0. (Single correct answer; show as quiz mode with explanation off to keep it fast.)

### Q4 — Vocabulary, objective (scored)

**AR:** ماذا تعني كلمة **"improve"**؟
**EN:** What does **"improve"** mean?

| Option (AR / EN) | Points |
|---|---|
| يتحسّن / to get better ✅ | 3 |
| يتوقف / to stop | 0 |
| يسافر / to travel | 0 |
| ينسى / to forget | 0 |

> Scoring: correct = 3, else 0.

### Q5 — Listening (scored)

**AR:** تقدر تتابع فيديو أو بودكاست إنجليزي بسرعة طبيعية؟
**EN:** Can you follow an English video or podcast at natural speed?

| Option (AR / EN) | Points |
|---|---|
| لا أفهم تقريبًا شيء / Almost nothing | 0 |
| أفهم بعض الكلمات / Some words | 1 |
| أفهم معظم الفكرة / Most of it | 2 |
| أفهم كل شيء تقريبًا / Almost everything | 3 |

### Q6 — Goal (tag, not scored) → writes `goal_tag`

**AR:** ما هو هدفك الأول من تعلّم الإنجليزي؟
**EN:** What's your #1 goal for learning English?

| Option (AR / EN) | `goal_tag` |
|---|---|
| أتكلم بثقة / Speak confidently | `confidence` |
| مقابلة عمل / وظيفة / Job interview / work | `interview` |
| السفر / Travel | `travel` |
| اختبار (IELTS/TOEFL) / Exam | `exam` |
| تحسين اللهجة الأمريكية / American accent | `accent` |

### Q7 — Time/track (tag, not scored) → writes `time_track`

**AR:** كم وقت تقدر تعطي يوميًا؟
**EN:** How much time can you give daily?

| Option (AR / EN) | `time_track` |
|---|---|
| حوالي 15 دقيقة / About 15 min | `Core` |
| حوالي 30 دقيقة / About 30 min | `Core` |
| 60 دقيقة أو أكثر / 60+ min | `Intensive` |

### Scoring → provisional level (sum of Q1–Q5, range 0–15)

| Sum | `level` | `level_name` (AR / EN) |
|---|---|---|
| 0–3 | L0 | المستوى صفر — مبتدئ تمامًا / Level 0 — Absolute Beginner |
| 4–7 | L1 | المستوى الأول — إنجليزية النجاة / Level 1 — Survival English |
| 8–11 | L2 | المستوى الثاني — التواصل / Level 2 — Communication |
| 12–15 | L3 | المستوى الثالث — الطلاقة واللهجة / Level 3 — Fluency & Accent |

### Edge rule (mirrors spec §5.3 / Learning System §3.2)

- If **Q2 (speaking)** points are ≥ 2 higher or lower than the *average* of Q1, Q3–Q5, nudge to the **higher** adjacent level on a trial basis and set `review_flag = TRUE`.
- Example: low self-rating but strong speaking → place up, flag for a quick human check.

### Transition to plan

**AR:** ممتاز! حسبت نتيجتك… لحظة 👇
**EN:** Perfect! Calculating your result… one moment 👇

> On completion the bot writes `level`, `level_score`, `goal_tag`, `time_track`, `quiz_completed_at`, `review_flag`; logs `QUIZ_COMPLETED`; then sends the matching plan template (Asset 4).


---

## Asset 4 — Personalized Plan Templates (one per level)

> Sent right after the quiz (spec §5.4). Each template: (1) provisional level, (2) 3 "focus first" bullets from that level's objectives, (3) goal echo, (4) recommended track, (5) CTA buttons. Variables: `{first_name}`, `{goal}`, `{track}`. The `{goal}` echo uses a short phrase keyed off `goal_tag` (see goal-phrase table at the end).

> **Honesty guardrail:** plans promise *attainable* first steps, not "you'll sound native." Mirrors the under-promise/over-deliver rule.

### Plan — Level 0 (Absolute Beginner)

**AR:**
> نتيجتك يا {first_name}: **المستوى صفر — مبتدئ تمامًا** 🌱
> هذا ممتاز — البداية الصحيحة أهم من البداية السريعة. نركّز أول شي على:
> • أصوات الإنجليزية الأساسية (نطق سليم من اليوم الأول)
> • أول 500 كلمة الأكثر استخدامًا
> • جُمل تعريف بسيطة عن نفسك
> وبما إن هدفك **{goal}**، رح نوجّه التمارين نحوه من البداية.
> المسار المناسب لك: **{track}**.

*(Buttons: `ابدأ تحدي 7 أيام المجاني` · `احجز مكالمة مجانية` · `شوف الأسعار`)*

**EN:**
> Your result, {first_name}: **Level 0 — Absolute Beginner** 🌱
> That's great — starting right matters more than starting fast. We focus first on:
> • Core English sounds (correct pronunciation from day one)
> • Your first 500 most-used words
> • Simple sentences to introduce yourself
> Since your goal is **{goal}**, we'll aim the practice toward it from the start.
> Your recommended track: **{track}**.

*(Buttons: `Start the free 7-Day Starter` · `Book a free call` · `See pricing`)*

### Plan — Level 1 (Survival English)

**AR:**
> نتيجتك يا {first_name}: **المستوى الأول — إنجليزية النجاة** 💪
> عندك أساس — هدفنا الحين نخليك تتكلم في المواقف اليومية بدون توتر. نركّز على:
> • محادثات يومية (طلبات، اتجاهات، تعارف)
> • التشديد وإيقاع الجملة الأمريكي
> • توسيع المفردات إلى ~1500 كلمة
> وبما إن هدفك **{goal}**، رح نختار المواقف الأقرب له.
> المسار المناسب لك: **{track}**.

*(Buttons: `ابدأ تحدي 7 أيام المجاني` · `احجز مكالمة مجانية` · `شوف الأسعار`)*

**EN:**
> Your result, {first_name}: **Level 1 — Survival English** 💪
> You have a base — now the goal is to make you speak in everyday situations without stress. We focus on:
> • Daily conversations (ordering, directions, small talk)
> • American stress and sentence rhythm
> • Growing your vocabulary toward ~1,500 words
> Since your goal is **{goal}**, we'll pick the scenarios closest to it.
> Your recommended track: **{track}**.

*(Buttons: `Start the free 7-Day Starter` · `Book a free call` · `See pricing`)*

### Plan — Level 2 (Communication)

**AR:**
> نتيجتك يا {first_name}: **المستوى الثاني — التواصل** 🚀
> أنت تتواصل — هدفنا الحين السرعة، الطلاقة، وفهم الكلام الطبيعي. نركّز على:
> • مواضيع أعقد (آراء، شرح، حكايات)
> • الربط والاختزال في النطق (connected speech)
> • فهم السرعة الطبيعية + التعابير الشائعة
> وبما إن هدفك **{goal}**، رح نكثّف التمارين المرتبطة فيه.
> المسار المناسب لك: **{track}**.

*(Buttons: `ابدأ تحدي 7 أيام المجاني` · `احجز مكالمة مجانية` · `شوف الأسعار`)*

**EN:**
> Your result, {first_name}: **Level 2 — Communication** 🚀
> You can communicate — now the goal is speed, fluency, and understanding natural speech. We focus on:
> • More complex topics (opinions, explanations, stories)
> • Linking and reduction (connected speech)
> • Understanding natural speed + common idioms
> Since your goal is **{goal}**, we'll concentrate the practice around it.
> Your recommended track: **{track}**.

*(Buttons: `Start the free 7-Day Starter` · `Book a free call` · `See pricing`)*

### Plan — Level 3 (Fluency & Accent)

**AR:**
> نتيجتك يا {first_name}: **المستوى الثالث — الطلاقة واللهجة** 🏆
> مستوى متقدم! هدفنا الحين الصقل: طلاقة طبيعية ولهجة أوضح. نركّز على:
> • صقل دقيق للنطق (Flap T، الشوا، الربط)
> • مفردات وتعابير ومصطلحات أصلية (native-like)
> • التعبير الحر والثقة في أي موضوع
> وبما إن هدفك **{goal}**، رح نخصّص التمارين له.
> المسار المناسب لك: **{track}**.
> *(ملاحظة صادقة: الوصول للهجة "أصلية تمامًا" نادر للكبار — هدفنا الوضوح والثقة والطلاقة القابلة للقياس.)*

*(Buttons: `ابدأ تحدي 7 أيام المجاني` · `احجز مكالمة مجانية` · `شوف الأسعار`)*

**EN:**
> Your result, {first_name}: **Level 3 — Fluency & Accent** 🏆
> Advanced level! The goal now is refinement: natural fluency and a clearer accent. We focus on:
> • Micro-refinement of pronunciation (Flap T, schwa, linking)
> • Native-like vocabulary, idioms, and expressions
> • Free expression and confidence on any topic
> Since your goal is **{goal}**, we'll tailor the practice to it.
> Your recommended track: **{track}**.
> *(Honest note: a truly "native" accent is rare for adults — our aim is measurable clarity, confidence, and fluency.)*

*(Buttons: `Start the free 7-Day Starter` · `Book a free call` · `See pricing`)*

### Review-flag variant (append when `review_flag = TRUE`)

**AR:** *(يُضاف سطر)* ملاحظة: نتيجتك قريبة بين مستويين — رح نتأكد من أنسب مستوى لك في مكالمة قصيرة أو في أول أيام التجربة. ما عليك شي 🙂
**EN:** *(append line)* Note: your result is close between two levels — we'll confirm the best fit in a short call or during your first trial days. No worries 🙂

### Goal-phrase table (fills `{goal}` naturally)

| `goal_tag` | AR phrase | EN phrase |
|---|---|---|
| `confidence` | التحدث بثقة | speaking with confidence |
| `interview` | اجتياز مقابلة عمل | passing a job interview |
| `travel` | السفر والتعامل بالخارج | traveling and getting by abroad |
| `exam` | اجتياز اختبار (IELTS/TOEFL) | passing an exam (IELTS/TOEFL) |
| `accent` | تحسين اللهجة الأمريكية | improving your American accent |


---

## Asset 5 — Quick-Win Lead Magnet: "3 Sounds That Make You Sound More American"

> The instant-gratification freebie (spec §5 ladder rung 2). Two parts: **(A)** the bot delivery messages, **(B)** the PDF content (1–2 pages, bilingual). The 3 audio clips are short recordings the founder must produce — **scripts provided below; recording is a production task, not done here.** Source material is packaged from the Learning System doc's sound-pattern tables (Table 19) — minimal new research.

### Part A — Bot delivery messages

**AR (on "🎁 هديتي المجانية"):**
> هديتك جاهزة يا {first_name}! 🎁
> **3 أصوات تخليك تنطق أمريكي أكثر** — دليل قصير + 3 مقاطع صوتية تتمرّن معها.
> حمّلها من هنا 👇
> {RESOURCE_LINK}
> جرّب صوت واحد اليوم فقط — النتيجة تفاجئك 🔥

*(Buttons: `كيف يعمل Empire` · `ابدأ تحدي 7 أيام` · `↩️ القائمة`)*

**EN (on "🎁 My free gift"):**
> Your gift is ready, {first_name}! 🎁
> **3 Sounds That Make You Sound More American** — a short guide + 3 audio clips to practice with.
> Download it here 👇
> {RESOURCE_LINK}
> Try just one sound today — the result will surprise you 🔥

*(Buttons: `How Empire works` · `Start 7-Day Starter` · `↩️ Menu`)*

> Delivery fires consent check first (Asset 9) then logs `RESOURCE_CLAIMED`.

### Part B — PDF content (bilingual, ~1–2 pages)

**Title (AR):** 3 أصوات تخليك تنطق أمريكي أكثر — من Empire English
**Title (EN):** 3 Sounds That Make You Sound More American — by Empire English

**Intro (AR):** معظم متعلمي الإنجليزي يتعبون على القواعد وينسون الأصوات. هذه 3 أصوات صغيرة تغيّر إحساس كلامك فورًا. اسمع المقطع، كرّر بصوت عالٍ، وسجّل نفسك.
**Intro (EN):** Most learners grind on grammar and ignore the sounds. These 3 small sounds instantly change how your speech feels. Listen to the clip, repeat out loud, and record yourself.

**Sound 1 — The Flap T (الـ T اللينة)**
- **AR:** في أمريكا، الـ T بين حرفين متحركين تصير قريبة من الـ D السريعة. "water" تُنطق "wah-der"، و"better" تصير "beh-der".
- **EN:** In American English, a T between two vowels becomes a quick D-like flap. "water" → "wah-der", "better" → "beh-der".
- **Practice words:** water · better · city · later · party
- **🎧 Audio clip 1** (see script A5-1)

**Sound 2 — The Schwa /ə/ (الشوا — الصوت الكسول)**
- **AR:** أكثر صوت شائع في الإنجليزية! الحروف غير المشدّدة "تكسل" وتصير /ə/ خفيفة. "about" = "uh-bout"، "banana" = "buh-NAE-nuh". لا تنطق كل حرف بوضوح — الأمريكي يختزل.
- **EN:** The most common sound in English! Unstressed vowels "relax" into a soft /ə/. "about" = "uh-bout", "banana" = "buh-NAE-nuh". Don't pronounce every vowel fully — Americans reduce.
- **Practice words:** about · banana · problem · sofa · the (uh)
- **🎧 Audio clip 2** (see script A5-2)

**Sound 3 — Linking (الربط بين الكلمات)**
- **AR:** الأمريكي ما يوقف بين الكلمات — يربطها. حرف ساكن في آخر كلمة يلتصق بحرف متحرك في بداية الكلمة اللي بعدها. "pick it up" تصير "pi-ki-tup"، "an apple" تصير "a-napple".
- **EN:** Americans don't stop between words — they link them. A final consonant glides into the next word's starting vowel. "pick it up" → "pi-ki-tup", "an apple" → "a-napple".
- **Practice phrases:** pick it up · an apple · turn it on · come in
- **🎧 Audio clip 3** (see script A5-3)

**Closing CTA (AR):** تمرّنت على صوت؟ في Empire تتمرّن على هذي الأصوات كل يوم بنظام يصحّح لك. ابدأ تحدي 7 أيام المجاني 👇
**Closing CTA (EN):** Practiced a sound? At Empire you train these sounds daily with a system that corrects you. Start the free 7-Day Starter 👇

### Part C — Audio clip scripts (for founder to record; ~20–30 sec each)

> Production note: record clear, slow→natural-speed audio. Each clip: say the rule in one line, then the words twice (slow, then natural). Keep under 30 seconds. These are **recordings to produce later**, not deliverable here.

- **A5-1 (Flap T):** "The American T between vowels sounds like a soft D. Listen: water… water. Better… better. City… city. Now you try."
- **A5-2 (Schwa):** "The schwa is the lazy 'uh' sound. Listen: about… about. Banana… banana. Problem… problem. Relax the vowel — uh."
- **A5-3 (Linking):** "Americans link words together. Listen: pick it up… pickitup. An apple… anapple. Turn it on… turniton. Glide, don't stop."

> **Build mapping:** the PDF + 3 audio files are produced, uploaded, and the share URL set as `{RESOURCE_LINK}` in `Config`. Until produced, the bot can deliver the PDF text alone and mark audio "coming soon."


---

## Asset 6 — "How Empire Works + Pricing" explainer

> Shown on the `📚 How Empire works + pricing` button (spec §4.4 Flow D). Three short messages: (1) how it works, (2) the value ladder, (3) CTA. Logs `OFFER_OPENED`. **Day-one decision (locked):** prices are **not shown publicly** in the bot — pricing is handled in a short call or DM. Price tokens are reserved for a later phase.

### Message 1 — how it works

**AR:**
> في Empire، ما نبيعك "كورس" — نعطيك **نظام تعلّم كامل** يمشي معك كل يوم 👇
> • نطق أمريكي من اليوم الأول
> • مهام كلام يومية (مو بس نظري — تتكلم فعلاً)
> • مجتمع يدعمك + متابعة لتقدّمك
> • مستويات واضحة: ما ترتقي إلا لما تتقن — جودة حقيقية مش وهمية.

**EN:**
> At Empire, we don't sell a "course" — we give you a complete **learning system** that walks with you daily 👇
> • American pronunciation from day one
> • Daily speaking missions (not just theory — you actually talk)
> • A community that supports you + progress tracking
> • Clear levels: you only advance when you've mastered it — real quality, not fake.

### Message 2 — the value ladder (no public prices on day one; pricing via call/DM)

**AR:**
> عندنا مسار واضح يبدأ من المجاني:
> 🆓 **Recruit (مجاني):** تذوّق المستوى صفر + المجتمع + كلمة اليوم
> ⭐ **Core (الأساس):** النظام اليومي الكامل + المجتمع + المتابعة
> 👑 **Citizen:** كل ما سبق + مدرّب ذكاء اصطناعي + أولوية في التصحيح
> 🏛️ **Founding Citizen (مقاعد محدودة):** عضوية دائمة + لقب مؤسس
> الأسعار نرتّبها لك حسب هدفك في مكالمة قصيرة أو رسالة خاصة — عشان تختار الأنسب لك فعلاً، مو الأغلى.

**EN:**
> We have a clear path that starts free:
> 🆓 **Recruit (free):** Level 0 taster + community + word of the day
> ⭐ **Core:** the full daily system + community + tracking
> 👑 **Citizen:** all that + AI tutor + priority feedback
> 🏛️ **Founding Citizen (limited seats):** lifetime access + founder status
> We'll sort out pricing around your goal in a short call or DM — so you pick what truly fits you, not the most expensive.

### Message 3 — CTA

**AR:** أنصحك تبدأ بتجربة 7 أيام المجانية وتشوف بنفسك 👇 وإذا حبيت تفاصيل الأسعار والباقات، احجز مكالمة قصيرة أو راسلنا.
**EN:** I'd start with the free 7-day trial and see for yourself 👇 and if you'd like pricing and package details, book a short call or DM us.

*(Buttons: `ابدأ تحدي 7 أيام / Start 7-Day Starter` · `احجز مكالمة / Book a call` · `↩️`)*

> **Honesty + scarcity rule:** "limited seats" for Founding Citizen must reflect *real* availability when discussed on the call/DM. Never fabricate scarcity. When public prices are later introduced, anchor with the high tier so the mid tier feels sensible (Strategic Expansion §7).

---

## Asset 7 — "What you'll get on the call"

> Shown on `📅 Book a free call` before the Cal.com link (spec §4.4 Flow E). Reassures + sets expectations → raises booking + show-up rates.

**AR:**
> مكالمة قصيرة (15–20 دقيقة)، بدون ضغط بيع 🙂
> في المكالمة:
> • نحدّد مستواك وهدفك بدقة
> • نرسم لك خطة واضحة للأسابيع القادمة
> • تسأل أي شي وتشوف إذا Empire يناسبك
> اختر وقت يناسبك 👇
> {CALL_URL}

**EN:**
> A short call (15–20 min), zero sales pressure 🙂
> On the call we'll:
> • Pinpoint your exact level and goal
> • Map a clear plan for your coming weeks
> • Answer anything, so you can see if Empire fits you
> Pick a time that suits you 👇
> {CALL_URL}

*(Buttons: open `{CALL_URL}` · `↩️ القائمة / Menu`)*

> Build: `{CALL_URL}` carries `?src=bot&tid={telegram_id}` so the Cal.com webhook matches the booking back to the CRM row (spec §8).

---

## Asset 8 — Community invites

> Shown on `💬 Join the community` (spec §4.4 Flow F). Logs `COMMUNITY_CLICK`.

**AR:**
> أهلاً فيك في عائلة Empire 🏛
> • مجتمع Discord (تمارين، صوتيات، فعاليات): {DISCORD_INVITE}
> • مجموعة النقاش على تيليجرام (أسئلة + كلمة اليوم): {GROUP_INVITE}
> ادخل، عرّف عن نفسك، وابدأ معنا 💪

**EN:**
> Welcome to the Empire family 🏛
> • Discord community (drills, voice rooms, events): {DISCORD_INVITE}
> • Telegram discussion group (Q&A + word of the day): {GROUP_INVITE}
> Hop in, introduce yourself, and start with us 💪

*(Buttons: open Discord · open group · `↩️`)*

---

## Asset 9 — Consent + opt-out

> Consent prompt shown before first resource/plan delivery (spec §7). On Yes → `consent=TRUE`, `consent_at=now`. On No → still deliver immediate value, no marketing flag.

**Consent prompt — AR:**
> قبل ما نكمل: تسمح لنا نرسل لك خطتك ونصائح مفيدة من وقت لآخر؟ (تقدر توقفها أي وقت بكتابة /stop)

**Consent prompt — EN:**
> Before we continue: may we send you your plan and occasional helpful tips? (You can stop anytime with /stop)

*(Buttons: `نعم / Yes` · `لا / No`)*

**On "No" — AR:** تمام، ما رح نرسل رسائل ترويجية 🙂 هديتك/خطتك تحت 👇
**On "No" — EN:** No problem, we won't send marketing messages 🙂 Your gift/plan is below 👇

**Opt-out (`/stop`) confirmation — AR:** تم إيقاف الرسائل الترويجية. ترجع في أي وقت بكتابة /menu 🙏
**Opt-out (`/stop`) confirmation — EN:** Marketing messages stopped. Come back anytime with /menu 🙏

---

## Asset 10 — Hot-lead alert (internal — to founder, not the user)

> Sent to the founder (DM/email) when a lead turns Hot (booked, or lead_score ≥ threshold) — spec §9 A9, §11. Internal; single language (founder's choice — English default).

```
🔥 HOT LEAD — Empire English
Name: {first_name} (@{username})
Telegram ID: {telegram_id}
Level: {level_name}   Goal: {goal}   Track: {track}
Lead score: {lead_score}   Segment: {segment}
Trigger: {trigger}   (BOOKED / score threshold)
Booked: {booked}   When: {booking_time}
Last action: {last_event} at {last_active_at}
Consent: {consent}
→ Suggested next step: {if booked: "prep for call" else: "send a personal DM within 24h"}
```

> Keep this internal template short and scannable — its only job is to prompt the founder's highest-value manual action fast.

---

## Coverage check (vs. spec §16)

| §16 asset | Covered by |
|---|---|
| 1. String Table | Asset 1 |
| 2. Welcome message | Asset 2 |
| 3. Quiz Q + options + scoring | Asset 3 |
| 4. 4 plan templates | Asset 4 |
| 5. "3 American Sounds" (PDF + audio) | Asset 5 (audio = recording task) |
| 6. How Empire works + pricing | Asset 6 |
| 7. What you'll get on the call | Asset 7 |
| 8. Community invites | Asset 8 |
| 9. Consent + opt-out | Asset 9 |
| 10. Hot-lead alert | Asset 10 |

### Still needed before go-live (not content — production/decisions)
- ~~Confirm prices~~ ✅ **Decided:** no public prices day one — pricing via call/DM. Price tokens reserved for later.
- **Record** the 3 audio clips (scripts A5-1/2/3) and **produce** the PDF in Canva.
- **Set** `{CALL_URL}`, `{DISCORD_INVITE}`, `{GROUP_INVITE}`, `{RESOURCE_LINK}` in `Config`.
- **Arabic register decided:** MSA, fresh/conversational. A light native-speaker proofread before publishing is still recommended (final polish only).

---

*End of Phase 0 Content Assets v1.0 — content/copy artifact. No bot has been built or deployed.*
