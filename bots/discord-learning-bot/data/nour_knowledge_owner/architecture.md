# نظرة عامة على البنية التقنية (Architecture)

> هذا الملف جزء من قاعدة معرفة نور — مخصَّص للمالك فقط. لا يُعرض هذا المحتوى للطلاب أبدًا (Aql Phase A2، domain: `architecture`).

## نظرة عامة على النظام

بوت Empire English (`bots/discord-learning-bot`) هو تطبيق Python واحد يعمل داخل حاوية Docker على خادم Hetzner. نقطة الدخول الرئيسية هي `src/bot.py` — بوت Discord (`discord.py`) يستخدم `message_content` و`members` intents، إلى جانب خادم HTTP خفيف (`src/api_server.py`, aiohttp، منفذ 8099) يخدم منصة التمرين (empire-dojo) وبوت Telegram المنفصل.

## الوحدات الأساسية (Core Modules)

- **`bot.py`** — نقطة الدخول: الأوامر، الأحداث (`on_member_join` إلخ)، المهام المجدولة (`tasks.loop`). يحتوي طبقة استبدال الأوامر العربية (`ARABIC_COMMAND_ALIASES`) التي تُعيد كتابة رسائل عربية إلى ما يعادلها بالإنجليزية قبل `bot.process_commands()`.
- **`config.py`** — كل الإعدادات من `.env`، مصدر الحقيقة الوحيد.
- **`database.py`** — طبقة SQLite الكاملة (اتصال، مخطَّط البيانات، كل دوال القراءة/الكتابة). راجع domain `database_schema` لتفاصيل الجداول.
- **`curriculum.py`** — تحميل محتوى المناهج (مفردات/نطق/قواعد) لكل مستوى وأسبوع.
- **`tasks.py`** — توليد وتنسيق وتسليم المهام اليومية السبع.
- **`verification.py`** — مكافحة الغش: بوابات إثبات العمل، فترات الانتظار (cooldowns)، اختبارات المفردات/الاستماع.
- **`features.py`** — نظام الأصدقاء (Buddy)، الاستبيانات، تقارير، جمع امتحانات الترقية عبر DM، متابعة الأعضاء المعرَّضين للانقطاع.
- **`ai_engine.py`** — كل نداءات Gemini/Groq، التقييم، التوليد.
- **`adaptive_engine.py`**, **`narrative_engine.py`**, **`pronunciation_scorer.py`** — منطق مساعد متخصِّص (الصعوبة التكيُّفية، خطاب النمو الأسبوعي، تقييم النطق بـ Groq Whisper).
- **`role_gate.py`** — نظام قبول القوانين للأعضاء الجدد (Hissar).
- **`flag_registry.py`** — المصدر الوحيد لكل أعلام التشغيل (Feature Flags) في كل المبادرات. راجع domain `flag_registry_reference` للقائمة الكاملة المُولَّدة تلقائيًّا.

## منظومة نور (Nour Subsystem)

- **`nour_concierge.py`** — المستشارة الذكية الحالية (single-shot)، تُجيب على DMs وقناة #ask-nour. هذا هو الكود الحيّ الوحيد الذي يتحدَّث مع الطلاب/المالك اليوم.
- **`nour_proactive.py`** — التواصل الاستباقي لمنع الانقطاع (٩ شروط، Rawiya R3).
- **`nour_escalation.py`** — تصعيد المشكلات إلى Telegram عبر جدول `pending_escalations` الدائم.
- **`nour_journey.py`** — الآلة الخطِّية القديمة لتأهيل الأعضاء الجدد (تُستبدَل تدريجيًّا بجدول `journey_coverage` ضمن مبادرة Aql — راجع أدناه).
- **`nour_tutorials.py`**, **`nour_personality.py`**, **`nour_onboarding.py`**, **`nour_ops_commands.py`** — سلوكيات مساعدة أخرى لنور.
- **`src/nour/`** — الحزمة الجديدة لمبادرة **Aql (العقل، #15)**: نظام معرفي مُبنى على الأدوار (RAG + استدعاء أدوات) يُراد له استبدال خطّ أنابيب `nour_concierge.py` الحالي عندما يُفعَّل علم `nour_aql_core` (معطَّل افتراضيًّا اليوم). يحتوي:
  - `roles.py` — تحديد دور المتحدِّث (مالك/طالب) من `OWNER_DISCORD_ID`.
  - `permissions.py` — خريطة الأدوار إلى نطاقات المعرفة (`KNOWLEDGE_DOMAINS`) وإلى الأدوات المسموحة (`TOOL_REGISTRY`) — هذا هو الحاجز الأمني الحقيقي، وليس تعليمة داخل الـ prompt.
  - `knowledge/` — `chunker.py` (تقطيع ملفات Markdown عند رؤوس `##`)، `embedder.py` (عميل Gemini للتضمين)، `retriever.py` (الاسترجاع الفعلي المُقيَّد بالدور).

**مهم:** حتى تاريخ كتابة هذا الملف، `nour_concierge.py` لا يزال هو الكود الوحيد الذي يتحدَّث مع مستخدمين حقيقيين. كل ما بُني تحت `src/nour/` (Aql) هو بناء متوازٍ وخامل — لا تأثير على أي محادثة حية بعد.

## طبقة عمليات Telegram ("Markaz" مركز)

بوت Telegram منفصل تمامًا (`@empire_ops_eec_bot`, رمز `OPS_BOT_TOKEN`، محادثة `OPS_CHAT_ID`) — مختلف عن `TELEGRAM_ALERT_TOKEN` القديم المشترك. `ops_poller.py` يستطلع (long-poll) تحديثات Telegram لردود المالك على التصعيدات، ويطابقها بجدول `pending_escalations` (يبقى بعد إعادة التشغيل). `ops_commands.py` ينفِّذ أوامر Telegram الإدارية (`/flag`, `/announce`, `/nour`, `/students`، إلخ) — منفصلة عن `nour_ops_commands.py` (أوامر Nour الموجَّهة للطلاب عبر Telegram).

## التكامل مع منصة التمرين (empire-dojo)

`api_server.py` يخدم نقاط نهاية REST (`/api/progress`, `/api/dashboard`, `/api/leaderboard`, `/api/nour-tips`, `/api/notifications`, و`POST /api/complete-exercise`) باستخدام "رموز الربط" الشخصية (جدول `link_tokens`) — كل طالب يربط حسابه بمنصة `https://practice.empireenglish.online` (أو ما يحدِّده `PRACTICE_PLATFORM_URL`) برمز فريد. منصة empire-dojo نفسها مستودع (repo) منفصل، يُنشر تلقائيًّا عبر Cloudflare Pages ولا يتأثَّر بنشر هذا البوت.

## مزودو الذكاء الاصطناعي

- **Gemini** (`GEMINI_API_KEY`, `GEMINI_MODEL` — الدردشة، `GEMINI_EMBEDDING_MODEL` — تضمينات Aql فقط) — المزوِّد الأساسي.
- **Groq** (`GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_WHISPER_MODEL`) — احتياطي للدردشة، وأساسي لتقييم النطق (Whisper).

## نقطة أمان مهمة: البوت الشبح (Ghost Bot)

نسخة ثانية كاملة من نفس الكود تعمل بنفس السيرفر الحقيقي، برمز (token) مختلف، تحت `IS_GHOST_INSTANCE=true` في `.env.ghost` فقط. الغرض: اختبار الأوامر ضد بنية الأدوار/القنوات الحقيقية دون التأثير على الطلاب. **تحذير معروف:** الأحداث على مستوى الخادم (`on_member_join`, تدفُّقات DM) ليست مقيَّدة بالقناة، وتُطلَق لكل نسخة من البوت في الخادم نفسه — هذا سبب موثَّق لحادثة رسائل ترحيب مزدوجة (Hisn D023/H6)، وهو السبب في أن `IS_GHOST_INSTANCE` يجعل هذه المعالِجات لا تفعل شيئًا (no-op) للنسخة الشبح فقط.
