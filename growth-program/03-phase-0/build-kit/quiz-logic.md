# Build Kit — Quiz Logic, Plan Templates & CRM Formulas

Implements spec §5 + §11 and Content Asset 3 + 4. Use this while building Make.com scenario **A2 (Quiz handler)** and the `Subscribers` formula columns.

---

## 1. Quiz questions, options & points

> Built as Telegram inline buttons / quiz polls. **Q1–Q5 scored (0–3 each).** Q6 → `goal_tag`. Q7 → `time_track`. Bilingual; Arabic-led.

### Q1 — Self-assessment (scored)
**AR:** كيف تصف إنجليزيتك اليوم؟ · **EN:** How would you describe your English today?
| Option (AR / EN) | points |
|---|---|
| أعرف حروف/كلمات بسيطة فقط / I only know letters or a few words | 0 |
| أكوّن جُمل بسيطة بصعوبة / I make simple sentences with effort | 1 |
| أتعامل مع محادثات يومية / I handle daily conversations | 2 |
| أتحدث بطلاقة عن معظم المواضيع / I speak fluently on most topics | 3 |

### Q2 — Speaking (scored) — *also the edge-rule signal*
**AR:** تقدر تعرّف عن نفسك بالإنجليزي 30 ثانية؟ · **EN:** Can you introduce yourself in English for 30 seconds?
| Option | points |
|---|---|
| لا، ليس بعد / Not yet | 0 |
| بصعوبة وبجُمل قصيرة / With effort, short sentences | 1 |
| نعم، بشكل مقبول / Yes, reasonably well | 2 |
| نعم، بسهولة وثقة / Yes, easily and confidently | 3 |

### Q3 — Grammar (scored, objective)
**AR/EN:** Which sentence is correct?
| Option | points |
|---|---|
| She go to work every day. | 0 |
| **She goes to work every day.** ✅ | 3 |
| She going to work every day. | 1 |
| She is go to work every day. | 0 |

### Q4 — Vocabulary (scored, objective)
**AR:** ماذا تعني كلمة "improve"؟ · **EN:** What does "improve" mean?
| Option | points |
|---|---|
| يتحسّن / to get better ✅ | 3 |
| يتوقف / to stop | 0 |
| يسافر / to travel | 0 |
| ينسى / to forget | 0 |

### Q5 — Listening (scored)
**AR:** تقدر تتابع فيديو/بودكاست إنجليزي بسرعة طبيعية؟ · **EN:** Can you follow English at natural speed?
| Option | points |
|---|---|
| لا أفهم تقريبًا شيء / Almost nothing | 0 |
| أفهم بعض الكلمات / Some words | 1 |
| أفهم معظم الفكرة / Most of it | 2 |
| أفهم كل شيء تقريبًا / Almost everything | 3 |

### Q6 — Goal (tag → `goal_tag`)
| Option (AR / EN) | goal_tag |
|---|---|
| أتكلم بثقة / Speak confidently | confidence |
| مقابلة عمل / Job interview | interview |
| السفر / Travel | travel |
| اختبار / Exam | exam |
| تحسين اللهجة / American accent | accent |

### Q7 — Time (tag → `time_track`)
| Option (AR / EN) | time_track |
|---|---|
| ~15 دقيقة / ~15 min | Core |
| ~30 دقيقة / ~30 min | Core |
| 60+ دقيقة / 60+ min | Intensive |

---

## 2. Scoring → provisional level

`level_score = Q1 + Q2 + Q3 + Q4 + Q5` (range 0–15). Bands are read from the `Config` tab (`LEVEL_BAND_*`):

| level_score | level | level_name key |
|---|---|---|
| 0–3 | L0 | name_l0 |
| 4–7 | L1 | name_l1 |
| 8–11 | L2 | name_l2 |
| 12–15 | L3 | name_l3 |

**Level-name strings** (add to `String_Table` if you want them keyed, or inline in A2):
- name_l0 — AR: المستوى صفر — مبتدئ تمامًا / EN: Level 0 — Absolute Beginner
- name_l1 — AR: المستوى الأول — إنجليزية النجاة / EN: Level 1 — Survival English
- name_l2 — AR: المستوى الثاني — التواصل / EN: Level 2 — Communication
- name_l3 — AR: المستوى الثالث — الطلاقة واللهجة / EN: Level 3 — Fluency & Accent

### Edge rule (set `review_flag = TRUE` + nudge up one level)
Let `others_avg = (Q1 + Q3 + Q4 + Q5) / 4`.
If `Q2 - others_avg >= QUIZ_EDGE_GAP` **or** `others_avg - Q2 >= QUIZ_EDGE_GAP` → set `review_flag = TRUE`; if the disagreement points to a higher adjacent level, place at the **higher** band on trial.

**Make.com A2 pseudocode:**
```
score = q1+q2+q3+q4+q5
if score <= LEVEL_BAND_L0_MAX: level=L0
elif score <= LEVEL_BAND_L1_MAX: level=L1
elif score <= LEVEL_BAND_L2_MAX: level=L2
else: level=L3
others_avg = (q1+q3+q4+q5)/4
review_flag = abs(q2 - others_avg) >= QUIZ_EDGE_GAP
# write level, level_score, goal_tag, time_track, quiz_completed_at, review_flag
# log QUIZ_COMPLETED ; then send plan_{level}
```

---

## 3. Plan templates (bot output after scoring)

> Add these 4 as `String_Table` keys `plan_l0`–`plan_l3`. Variables: `{first_name}`, `{goal}` (use the matching `goal_*` string), `{track}`. Append `plan_review_note` when `review_flag=TRUE`.

### plan_l0
**AR:**
نتيجتك يا {first_name}: المستوى صفر — مبتدئ تمامًا 🌱
هذا ممتاز — البداية الصحيحة أهم من البداية السريعة. نركّز أول شي على:
• أصوات الإنجليزية الأساسية (نطق سليم من اليوم الأول)
• أول 500 كلمة الأكثر استخدامًا
• جُمل تعريف بسيطة عن نفسك
وبما إن هدفك {goal}، رح نوجّه التمارين نحوه من البداية.
المسار المناسب لك: {track}.
**EN:**
Your result, {first_name}: Level 0 — Absolute Beginner 🌱
Starting right matters more than starting fast. We focus first on:
• Core English sounds (correct pronunciation from day one)
• Your first 500 most-used words
• Simple sentences to introduce yourself
Since your goal is {goal}, we'll aim the practice toward it from the start.
Your recommended track: {track}.
*Buttons:* Start the free 7-Day Starter · Book a free call · How Empire works

### plan_l1
**AR:**
نتيجتك يا {first_name}: المستوى الأول — إنجليزية النجاة 💪
عندك أساس — هدفنا الحين تتكلم في المواقف اليومية بدون توتر. نركّز على:
• محادثات يومية (طلبات، اتجاهات، تعارف)
• التشديد وإيقاع الجملة الأمريكي
• توسيع المفردات إلى ~1500 كلمة
وبما إن هدفك {goal}، رح نختار المواقف الأقرب له.
المسار المناسب لك: {track}.
**EN:**
Your result, {first_name}: Level 1 — Survival English 💪
You have a base — now the goal is everyday situations without stress. We focus on:
• Daily conversations (ordering, directions, small talk)
• American stress and sentence rhythm
• Growing vocabulary toward ~1,500 words
Since your goal is {goal}, we'll pick the closest scenarios.
Your recommended track: {track}.
*Buttons:* Start the free 7-Day Starter · Book a free call · How Empire works

### plan_l2
**AR:**
نتيجتك يا {first_name}: المستوى الثاني — التواصل 🚀
أنت تتواصل — هدفنا الحين السرعة، الطلاقة، وفهم الكلام الطبيعي. نركّز على:
• مواضيع أعقد (آراء، شرح، حكايات)
• الربط والاختزال في النطق
• فهم السرعة الطبيعية + التعابير الشائعة
وبما إن هدفك {goal}، رح نكثّف التمارين المرتبطة فيه.
المسار المناسب لك: {track}.
**EN:**
Your result, {first_name}: Level 2 — Communication 🚀
Now the goal is speed, fluency, and understanding natural speech. We focus on:
• More complex topics (opinions, explanations, stories)
• Linking and reduction (connected speech)
• Natural speed + common idioms
Since your goal is {goal}, we'll concentrate the practice around it.
Your recommended track: {track}.
*Buttons:* Start the free 7-Day Starter · Book a free call · How Empire works

### plan_l3
**AR:**
نتيجتك يا {first_name}: المستوى الثالث — الطلاقة واللهجة 🏆
مستوى متقدم! هدفنا الحين الصقل: طلاقة طبيعية ولهجة أوضح. نركّز على:
• صقل دقيق للنطق (Flap T، الشوا، الربط)
• مفردات وتعابير ومصطلحات أصلية
• التعبير الحر والثقة في أي موضوع
وبما إن هدفك {goal}، رح نخصّص التمارين له.
المسار المناسب لك: {track}.
(ملاحظة صادقة: الوصول للهجة "أصلية تمامًا" نادر للكبار — هدفنا الوضوح والثقة والطلاقة القابلة للقياس.)
**EN:**
Your result, {first_name}: Level 3 — Fluency & Accent 🏆
The goal now is refinement: natural fluency and a clearer accent. We focus on:
• Micro-refinement (Flap T, schwa, linking)
• Native-like vocabulary, idioms, expressions
• Free expression and confidence on any topic
Since your goal is {goal}, we'll tailor the practice to it.
Your recommended track: {track}.
(Honest note: a truly "native" accent is rare for adults — our aim is measurable clarity, confidence, and fluency.)
*Buttons:* Start the free 7-Day Starter · Book a free call · How Empire works

---

## 4. Lead score & segment formulas (Subscribers tab)

> Two approaches — pick one. **(A) Make.com recompute (recommended):** scenario A7 reads the `Events` tab + Config weights and writes `lead_score`/`segment` back. **(B) In-sheet formulas:** if you prefer the Sheet to self-calculate.

### Option B — in-sheet formulas (paste into `Subscribers`, row 2, fill down)

**lead_score** (sums weighted events for this telegram_id; weights read from Config):
```
=SUMPRODUCT(
  (Events!$B:$B=$A2) * (
     (Events!$C:$C="JOINED_BOT")      * VLOOKUP("SCORE_JOINED_BOT",Config!$A:$B,2,FALSE) +
     (Events!$C:$C="QUIZ_COMPLETED")  * VLOOKUP("SCORE_QUIZ_COMPLETED",Config!$A:$B,2,FALSE) +
     (Events!$C:$C="RESOURCE_CLAIMED")* VLOOKUP("SCORE_RESOURCE_CLAIMED",Config!$A:$B,2,FALSE) +
     (Events!$C:$C="OFFER_OPENED")    * VLOOKUP("SCORE_OFFER_OPENED",Config!$A:$B,2,FALSE) +
     (Events!$C:$C="BOOKED")          * VLOOKUP("SCORE_BOOKED",Config!$A:$B,2,FALSE) +
     (Events!$C:$C="COMMUNITY_CLICK") * VLOOKUP("SCORE_COMMUNITY_CLICK",Config!$A:$B,2,FALSE)
  )
)
```
*(Inactivity decay is simplest to apply in A7 rather than in-sheet.)*

**segment** (from score + state):
```
=IF($R2=TRUE,"Customer",
  IF(OR($S2=TRUE,$L2>=VLOOKUP("HOT_LEAD_THRESHOLD",Config!$A:$B,2,FALSE)),"Hot",
   IF(AND(COUNTIFS(Events!$B:$B,$A2,Events!$C:$C,"OFFER_OPENED")>0,$J2=TRUE),"Lead",
    IF(OR(COUNTIFS(Events!$B:$B,$A2,Events!$C:$C,"QUIZ_COMPLETED")>0,COUNTIFS(Events!$B:$B,$A2,Events!$C:$C,"RESOURCE_CLAIMED")>0),"Engager",
     "Lurker"))))
```
> Column letters assume the `subscribers.csv` order: J=consent, L=lead_score, R=booked... **verify against your imported columns** and adjust letters. The logic is what matters.

> **Recommendation:** use **Option A (A7 in Make.com)** for clarity and to apply decay; keep Option B only if you want a live in-sheet view.
