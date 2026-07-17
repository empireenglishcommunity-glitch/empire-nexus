"""Sahin Phase 1 — per-channel "how to use this channel" pinned guides.

Kept as a separate module (not inline in setup_server.py) per Sahin's
design.md Component 1, to keep setup_server.py itself readable as its
own file grows.

Style convention: pure Arabic, informal/colloquial register (matching
the register already used in دليل-القنوات's own live content and in
content/l0/accent/*.json's instructions_ar fields — NOT formal MSA),
with English channel/command names kept literal inline (#channel-name,
!command) since students need to recognize and type those exactly.
This deliberately does NOT use tasks.py's bl() "English / Arabic"
dual-line helper — that pattern is for fixed daily-task instructional
chrome; دليل-القنوات already proved pure-Arabic-with-inline-English-names
is the right register for a "what is this channel for" explainer, and
these guides are the same genre of content.

Each guide is short (aim for 3-6 lines): what the channel is FOR, what
to post / not post, and what happens next (bot response, human reply,
or just for reading). Voice channels are excluded here (Discord doesn't
support pinning a text message the same way in a voice-only channel);
their channel TOPIC already carries an equivalent short description.

Coverage: every student-facing text channel across WELCOME, SYSTEM,
LEVEL 0-3, COMMUNITY, ACCOUNTABILITY, RESOURCES, and FEEDBACK. ADMIN
and Ghost Testing are operator/testing-only, deliberately excluded --
those channels don't need a student-facing "how to use this" guide.

NOTE on دليل-القنوات and #cheat-sheets specifically:
- دليل-القنوات already has real, pinned, per-channel one-line summary
  content of its own (confirmed live during Sahin Phase 0/1) -- it is
  the whole-server INDEX/map, not a single-channel guide. No entry for
  it here, to avoid a redundant/conflicting pin in the one channel
  that's already doing this job well.
- #cheat-sheets' guide is written to describe its CURRENT real
  behavior (the weekly grammar card) without over-promising the
  vocabulary cheat sheet that Sahin Phase 4 will add -- update this
  entry's wording once Phase 4.1 ships for real, so the pin never
  describes a feature before it actually exists (the exact
  "designed but not built yet" trap already found repeatedly in this
  project, applied here to documentation instead of code).
"""

CHANNEL_GUIDES: dict[str, str] = {
    # ── WELCOME ──
    "start-here": (
        "🏛️ **إيه ده الروم؟**\n"
        "ده أول حاجة تشوفها لما تدخل السيرفر — بوابتك للمجتمع كله.\n\n"
        "✅ اقرأ الترتيب: `#welcome` → `#rules` → `#roles-info`\n"
        "✅ بعد كل ده، روح `#bot-commands` واكتب `!join` عشان تبدأ رسميًا\n"
        "❌ متكتبش هنا — ده مكان للقراءة بس\n\n"
        "لو تعبت أو مش فاهم حاجة، اسأل في `#ask-nour` في أي وقت 🤝"
    ),
    "announcements": (
        "📢 **إيه ده الروم؟**\n"
        "هنا بينزل أي تحديث أو خبر مهم عن المجتمع من الإدارة.\n\n"
        "✅ اقرأ باستمرار عشان تفوتك حاجة\n"
        "❌ متكتبش هنا — الروم للإدارة بس، لو عندك سؤال روح `#support`\n\n"
        "الإعلانات بتيجي أحيانًا بالعربي وأحيانًا بالإنجليزي حسب المحتوى."
    ),

    # ── SYSTEM ──
    "bot-commands": (
        "⭐ **إيه ده الروم؟**\n"
        "الروم الرسمي لكل أوامر البوت — ده المكان الوحيد اللي الأوامر بتشتغل فيه.\n\n"
        "✅ اكتب `!join`, `!done`, `!progress`, `!streak`, وأي أمر تاني\n"
        "✅ اكتب `!مساعدة` أو `!help` لو عايز تشوف كل الأوامر المتاحة\n"
        "❌ متكتب أوامر في رومات تانية — مش هتشتغل هناك\n\n"
        "البوت بيرد فورًا على أي أمر صحيح."
    ),
    "leaderboard": (
        "🏆 **إيه ده الروم؟**\n"
        "لوحة المتصدرين — بتتحدث تلقائيًا بالبوت، مفيهاش كتابة من الأعضاء.\n\n"
        "✅ اقرأ بس وشوف ترتيبك مقارنة بزمايلك\n"
        "❌ متكتبش هنا — لو عايز تناقش نتيجتك روح `#general-chat`\n\n"
        "الترتيب بيعتمد على نقاطك وانضباطك اليومي، مش على مستواك بس."
    ),
    "support": (
        "🆘 **إيه ده الروم؟**\n"
        "محتاج مساعدة تقنية أو مش فاهم إزاي تستخدم حاجة في السيرفر؟ هنا مكانك.\n\n"
        "✅ اسأل عن أي مشكلة في البوت، الأوامر، أو الرومات\n"
        "✅ ممكن تكتب بالعربي هنا لو محتاج توضيح سريع\n"
        "❌ للأسئلة عن محتوى الدروس نفسها، روح `#ask-nour` أو `#l0-questions`\n\n"
        "الإدارة أو نور بترد عادةً في أقرب وقت."
    ),
    "ask-nour": (
        "🤝 **إيه ده الروم؟**\n"
        "مساعدتك الشخصية بالذكاء الاصطناعي — نور موجودة هنا عشان تساعدك.\n\n"
        "✅ اسأل عن أي حاجة محيرة أو محتاج توضيح فيها\n"
        "✅ ممكن تتكلم بالعربي أو الإنجليزي، زي ما تحب\n"
        "✅ لو نور مش قادرة تساعد، بتوصل السؤال للإدارة تلقائيًا\n\n"
        "نور بترد بسرعة، وردها شخصي ليك مش نسخة عامة."
    ),
    "suggestions": (
        "💡 **إيه ده الروم؟**\n"
        "عندك فكرة تحسّن بيها المجتمع؟ شاركها هنا.\n\n"
        "✅ اكتب أي فكرة أو ملاحظة تفتكر إنها تفيد الكل\n"
        "✅ رد على أفكار زمايلك برأيك (بإيجابية!)\n"
        "❌ ده مش مكان للشكاوى الشخصية — استخدم `#support` لده\n\n"
        "الإدارة بتقرأ كل اقتراح، حتى لو مردت مش على كل واحد."
    ),

    # ── LEVEL 0-3 ZONES ──
    **{
        f"l{level}-daily-tasks": (
            f"📅 **إيه ده الروم؟**\n"
            f"هنا بتنزل مهامك اليومية (7 مهام) — ده قلب نظام التعلم اليومي بتاعك.\n\n"
            f"✅ افتح الروم كل يوم واعمل المهام بالترتيب\n"
            f"✅ اكتب `!done <اسم المهمة>` في `#bot-commands` بعد كل مهمة\n"
            f"❌ متكتبش هنا — الروم لعرض المهام بس، الكتابة في `#bot-commands`\n\n"
            f"المهام بتنزل تلقائيًا الساعة 6 الصبح كل يوم."
        )
        for level in ("0", "1", "2", "3")
    },
    **{
        f"l{level}-text-practice": (
            f"✍️ **إيه ده الروم؟**\n"
            f"مكانك لتمارين الكتابة الخاصة بمستواك — اكتب واتمرن بالإنجليزي.\n\n"
            f"✅ اكتب تمرينك هنا بعد ما تخلص مهمة الكتابة اليومية\n"
            f"✅ اقرأ وتمرين زمايلك ورد عليهم بإيجابية\n"
            f"❌ متستخدمش مترجم — الهدف إنك تفكر بالإنجليزي مباشرة\n\n"
            f"البوت والـ AI ممكن يعطوك ملاحظات على كتابتك."
        )
        for level in ("0", "1", "2", "3")
    },
    # NOTE: only L0/L1/L2 have a dedicated "-questions" channel in
    # setup_server.py's LEVEL 3 category -- L3 deliberately does NOT
    # (confirmed live during this same phase's execution: the script's
    # own "not found -- skipped" warning caught this exact mismatch).
    # L3 students use #l3-mentorship for this instead, which already
    # has its own guide below. Do NOT add "l3-questions" back into this
    # loop without first adding the actual channel to setup_server.py's
    # CATEGORIES_CONFIG -- this loop must always mirror real server
    # structure, never assume symmetry across levels.
    **{
        f"l{level}-questions": (
            f"❓ **إيه ده الروم؟**\n"
            f"أسئلتك عن محتوى المستوى {level} — قواعد، مفردات، أي حاجة مش واضحة.\n\n"
            f"✅ اسأل بحرية عن أي جزء من مادة المستوى ده\n"
            + ("✅ العربي مسموح هنا (استثناء خاص بالمستوى 0)\n" if level == "0" else "")
            + "❌ للمساعدة الشخصية الأشمل، روح `#ask-nour`\n\n"
            "زمايلك في نفس المستوى ممكن يردوا عليك كمان، متستحيش تسأل!"
        )
        for level in ("0", "1", "2")
    },
    **{
        f"l{level}-showcase": (
            f"🎙️ **إيه ده الروم؟**\n"
            f"هنا بتشارك تسجيلاتك الصوتية وتحتفل بتقدمك في المستوى {level}.\n\n"
            f"✅ حمّل تسجيلك بعد ما تخلص المهمة الصوتية اليومية\n"
            f"✅ رد على زمايلك بكلام إيجابي (بالإنجليزي!)\n"
            f"❌ متبعتش نص أو أسئلة هنا — ده مكانه `#ask-nour` أو `#support`\n\n"
            f"البوت بيسجل تقدمك تلقائيًا لما ترفع تسجيلك 🔥"
        )
        for level in ("0", "1", "2", "3")
    },
    "l3-mentorship": (
        "🌟 **إيه ده الروم؟**\n"
        "مخصص لطلاب المستوى 3 عشان يساعدوا المبتدئين ويشاركوا تجربتهم.\n\n"
        "✅ شارك نصايحك أو تجربتك الشخصية في التعلم\n"
        "✅ رد على أسئلة الطلاب اللي في مستويات أقل لو ليهم سؤال هنا\n"
        "❌ ده مش مكان لتمارين المستوى 3 نفسها — استخدم `#l3-text-practice`\n\n"
        "المشاركة هنا اختيارية بالكامل، بس بتفرق فعلًا مع المبتدئين."
    ),

    # ── COMMUNITY ──
    "general-chat": (
        "💬 **إيه ده الروم؟**\n"
        "دردشة عامة مفتوحة لكل الأعضاء — بس لازم بالإنجليزي بس!\n\n"
        "✅ اتكلم عن أي موضوع تحبه، من غير ضغط أو تقييم\n"
        "✅ ده أفضل مكان تتمرن فيه على المحادثة الحرة\n"
        "❌ العربي ممنوع هنا (إلا لو نور استخدمته معاك لمساعدتك)\n\n"
        "كل ما تكتب أكتر، كل ما تتقدم أسرع 💪"
    ),
    "introductions": (
        "👋 **إيه ده الروم؟**\n"
        "أول مرة تدخل السيرفر؟ عرّف نفسك هنا للمجتمع كله.\n\n"
        "✅ قول اسمك، بلدك، ومستواك في الإنجليزي، وهدفك من الانضمام\n"
        "✅ رحّب بالأعضاء الجداد لما يعرّفوا نفسهم\n"
        "❌ ده مش مكان للأسئلة أو النقاش — استخدم `#general-chat`\n\n"
        "المجتمع كله بيبدأ من نفس النقطة — ما تخافش تتكلم!"
    ),
    "events": (
        "📅 **إيه ده الروم؟**\n"
        "جلسات صوتية قادمة، تحديات، وأي فعالية في المجتمع.\n\n"
        "✅ تابع الجلسات القادمة وشارك فيها\n"
        "✅ اقترح فعالية جديدة لو عندك فكرة\n"
        "❌ للتسجيل الفعلي في جلسة صوتية، روح الروم الصوتي نفسه وقت الجلسة\n\n"
        "الإدارة والمشرفين بينزلوا هنا أي حاجة قادمة."
    ),
    "daily-word": (
        "📖 **إيه ده الروم؟**\n"
        "كلمة اليوم — كلمة إنجليزي جديدة تتعلمها وتستخدمها في جملة.\n\n"
        "✅ اكتب جملة بالكلمة الجديدة كل يوم\n"
        "✅ صحح لزمايلك بلطف لو جملتهم فيها غلطة\n"
        "❌ متسألش هنا عن كلمات تانية — استخدم `#ask-nour`\n\n"
        "التمرين البسيط اليومي ده بيبني مفردات حقيقية بمرور الوقت."
    ),

    # ── ACCOUNTABILITY ──
    "daily-check-in": (
        "☀️ **إيه ده الروم؟**\n"
        "الصبح: اكتب خطتك لليوم. بالليل: اكتب إنجازك.\n\n"
        "✅ صبح: قول هتعمل إيه النهاردة من المهام\n"
        "✅ ليل: قول عملت إيه فعلًا وإزاي كان يومك\n"
        "❌ ده مش مكان لتفاصيل المهام نفسها — بس تسجيل سريع للالتزام\n\n"
        "الانضباط اليومي هو اللي بيفرق على المدى البعيد، مش يوم واحد مثالي."
    ),
    "streak-tracker": (
        "🔥 **إيه ده الروم؟**\n"
        "متابعة الاستمرارية (streak) بتاعتك — بتتحدث تلقائيًا بالبوت.\n\n"
        "✅ اقرأ بس وشوف عداد استمراريتك\n"
        "❌ متكتبش هنا — الروم للبوت بس\n\n"
        "لو فاتك يوم، الاستمرارية بترجع من الصفر — خد بالك!"
    ),
    "weekly-goals": (
        "🎯 **إيه ده الروم؟**\n"
        "حدد أهداف الأسبوع بتاعك كل يوم إثنين.\n\n"
        "✅ اكتب هدف واحد أو اتنين واضحين للأسبوع ده\n"
        "✅ راجع أهداف الأسبوع اللي فات وقيّم نفسك\n"
        "❌ الأهداف لازم تكون قابلة للقياس، مش عمومية زي 'أتحسن'\n\n"
        "هدف واضح ومكتوب بيتحقق أسهل من هدف في دماغك بس."
    ),

    # ── RESOURCES ──
    # NOTE: describes CURRENT real behavior only (Wednesday grammar
    # card). Update once Sahin Phase 4.1 ships the vocabulary cheat
    # sheet for real -- see this file's module docstring.
    "cheat-sheets": (
        "📝 **إيه ده الروم؟**\n"
        "ملخصات ومراجع سريعة تساعدك تتذكر القواعد والمفردات.\n\n"
        "✅ يوم الأربعاء بينزل ملخص قواعد أسبوعي تلقائي من البوت\n"
        "✅ ثبّت (pin) أي ملخص مهم عندك عشان ترجع له بسهولة\n"
        "❌ متكتبش أسئلة هنا — استخدم `#grammar-qa` أو `#ask-nour`\n\n"
        "المزيد من المحتوى (مفردات أسبوعية) قريبًا هنا 🔜"
    ),
    "video-library": (
        "🎬 **إيه ده الروم؟**\n"
        "فيديوهات تعليمية مختارة حسب مستواك.\n\n"
        "✅ شارك فيديو مفيد شاهدته يساعد زمايلك في نفس مستواك\n"
        "✅ قول المستوى المناسب للفيديو لما تشاركه\n"
        "❌ متشاركش فيديوهات مش تعليمية أو مش مناسبة للمجتمع\n\n"
        "المحتوى هنا بيتجمع من الأعضاء والإدارة مع بعض."
    ),
    "podcast-recs": (
        "🎧 **إيه ده الروم؟**\n"
        "بودكاست مقترح للاستماع — تمرين أذنك على الإنجليزي الحقيقي.\n\n"
        "✅ شارك بودكاست تحبه وقول ليه يفيد التعلم\n"
        "✅ قول مستوى الصعوبة تقريبًا (مبتدئ/متوسط/متقدم)\n"
        "❌ ركز على محتوى تعليمي أو مفيد للغة، مش أي بودكاست عشوائي\n\n"
        "الاستماع المستمر بيبني لهجتك وفهمك من غير ما تحس."
    ),
    "book-club": (
        "📚 **إيه ده الروم؟**\n"
        "كتاب الشهر ومناقشته مع باقي أعضاء المجتمع.\n\n"
        "✅ شارك رأيك في كتاب الشهر الحالي (بالإنجليزي)\n"
        "✅ اقترح كتاب للشهر الجاي لو عندك فكرة\n"
        "❌ الكتب المقترحة لازم تكون مناسبة لمستوى القراءة العام\n\n"
        "القراءة المنتظمة من أقوى طرق تحسين اللغة على المدى البعيد."
    ),

    # ── FEEDBACK ──
    "speaking-feedback": (
        "🎙️ **إيه ده الروم؟**\n"
        "ارفع تسجيل صوتي واحصل على ملاحظات من الـ AI وزمايلك.\n\n"
        "✅ ارفع تسجيلك وقول إنت عايز فيدباك على إيه بالتحديد (نطق؟ طلاقة؟)\n"
        "✅ رد على تسجيلات زمايلك بملاحظات بنّاءة ومحترمة\n"
        "❌ متسخرش من نطق أو غلطة أي حد — كلنا بدأنا من الصفر\n\n"
        "الفيدباك البنّاء هو اللي بيخليك تتحسن أسرع."
    ),
    "writing-feedback": (
        "✍️ **إيه ده الروم؟**\n"
        "ابعت كتابتك واحصل على تصحيح وملاحظات حقيقية.\n\n"
        "✅ اكتب نصك وقول المستوى بتاعك عشان الفيدباك يكون مناسب\n"
        "✅ اقرأ تصحيحات زمايلك تتعلم من غلطاتهم كمان\n"
        "❌ متستخدمش مترجم قبل ما تبعت — الهدف تصحيح كتابتك الحقيقية\n\n"
        "التصحيح هنا بيركز على القواعد والمفردات والترتيب."
    ),
    "accent-feedback": (
        "🗣️ **إيه ده الروم؟**\n"
        "مقاطع نطق (accent) واحصل على فيدباك على لهجتك الأمريكية.\n\n"
        "✅ سجل نفسك بتنطق كلمة أو جملة معينة تتمرن عليها\n"
        "✅ قول الصوت أو الحرف اللي حاسس إنه صعب عليك بالتحديد\n"
        "❌ ده مختلف عن `#speaking-feedback` — ده للنطق بس، مش الطلاقة العامة\n\n"
        "النطق الصحيح بيتحسن بالتكرار والفيدباك المستمر، مش بيوم واحد."
    ),
    "grammar-qa": (
        "📖 **إيه ده الروم؟**\n"
        "أسئلة قواعد اللغة (grammar) وإجاباتها.\n\n"
        "✅ اسأل عن أي قاعدة مش واضحة ليك (tenses، prepositions، أي حاجة)\n"
        "✅ لو تعرف الإجابة، ساعد زميلك واشرح له\n"
        "❌ للمساعدة الشخصية الأشمل غير القواعد، روح `#ask-nour`\n\n"
        "قاعدة واحدة مفهومة كويس أفضل من عشر قواعد متلخبطة."
    ),
}
