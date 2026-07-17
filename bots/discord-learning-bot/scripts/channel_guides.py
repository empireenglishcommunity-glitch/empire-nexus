"""Sahin Phase 1 — per-channel "how to use this channel" pinned guides.

Kept as a separate module (not inline in setup_server.py) per Sahin's
design.md Component 1, to keep setup_server.py itself readable as its
own file grows.

Style convention (REVISED): Modern Standard Arabic (فصحى), simple and
warm, NOT stiff bureaucratic register. Changed from an earlier
Egyptian-colloquial draft after the owner caught real grammar errors
in that version during review (colloquial negation is genuinely
fragile -- the "ش" suffix in "م...ش" negation is easy to drop or mix
with other patterns when writing many similar lines quickly, and this
project's own history has BOTH Egyptian colloquial precedent --
دليل-القنوات's live content -- and Gulf colloquial precedent --
LEARNING_SYSTEM_IMPLEMENTATION_PLAN.md's recruitment message uses
"الحين", a Gulf-only word -- so there was never one single consistent
dialect to match in the first place). MSA is understood by every
Arabic speaker regardless of country/dialect and has simpler, more
robust negation rules (لا / لن / لم), removing this entire class of
bug at the root rather than just fixing the specific lines that were
caught.

Register notes:
- Masculine singular imperative (اكتب / اقرأ / لا تكتب) is the
  standard, expected default for MSA instructional content across the
  Arab world -- not exclusionary, just the conventional register for
  this genre of short instructional text.
- English channel/command names are kept literal inline
  (#channel-name, !command) since students need to recognize and type
  those exactly -- this is unchanged from the prior draft.
- Tanween/diacritics are omitted throughout (matching how MSA is
  conventionally written online/informally -- fully diacritized MSA
  would look out of place next to Discord's own UI and this project's
  other Arabic content, none of which is diacritized either).

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
  that's already doing this job well. (Its own content is still
  Egyptian colloquial, unchanged by this MSA revision -- that's a
  separate, pre-existing piece of content, out of scope for this
  specific fix; flag separately if the owner wants it revised too.)
- #cheat-sheets' guide is written to describe its CURRENT real
  behavior (the weekly grammar card) without over-promising the
  vocabulary cheat sheet that Sahin Phase 4 will add -- update this
  entry's wording once Phase 4.1 ships for real, so the pin never
  describes a feature before it actually exists (the exact
  "designed but not built yet" trap already found repeatedly in this
  project, applied here to documentation instead of code).

IMPORTANT: this content was written and grammar-reviewed by an AI
agent, not a native Arabic speaker. The owner explicitly flagged that
Arabic correctness here must be 100% -- a final human read-through by
a fluent Arabic speaker before this is considered permanently settled
is still recommended, even after this revision's careful rewrite.

Self-review pass performed on this revision (documented for
transparency, not as a substitute for the human read-through above):
after the initial المستوى->قناة noun swap (feminine, replacing the
non-MSA borrowed-slang word "روم"), a systematic re-check caught and
fixed 4 further real issues the automated substitution alone did not
catch: (1) a masculine adjective "مخصص" left describing the now-
feminine "القناة" in l3-mentorship (fixed to "مخصصة" + explicit
subject), (2) a masculine verb "يتحدث" describing the feminine
"متابعة" in streak-tracker (fixed to "تتحدث", matching the already-
correct parallel construction in leaderboard's own entry), (3) a
colloquial verb "تفرق" used with a meaning ("makes a difference")
that verb doesn't carry in MSA, in l3-mentorship (fixed to "تُحدث
فرقًا حقيقيًا"), (4) a colloquial "كل ما X، كل ما Y" repetitive-
comparative construction in general-chat (fixed to proper MSA
"كلما X، Y", one word "كلما" not two, and no repeated "كل ما").
An automated regex/substring scan (colloquial vocabulary markers +
the "م...ش" colloquial negation pattern) was also run against the
final text and found no remaining hits.
"""

CHANNEL_GUIDES: dict[str, str] = {
    # ── WELCOME ──
    "welcome": (
        "🏛️ **ما هذه القناة؟**\n"
        "هذه هي رسالة الترحيب الرسمية بالمجتمع — تشرح لك ما هو النظام وكيف يعمل.\n\n"
        "✅ اقرأ الرسالة المثبتة أعلاه بالكامل لتفهم فلسفة المجتمع\n"
        "✅ بعد القراءة، انتقل إلى:\n"
        "`#rules` ← `#roles-info`\n"
        "❌ لا تكتب هنا — هذه القناة للقراءة فقط\n\n"
        "إذا لم تفهم شيئًا، اسأل في `#ask-nour` في أي وقت."
    ),
    "rules": (
        "📜 **ما هذه القناة؟**\n"
        "هنا قوانين المجتمع الرسمية — اقرأها واقبلها قبل أن تشارك في أي مكان آخر.\n\n"
        "✅ اقرأ كل القوانين بعناية (مكتوبة بالإنجليزية)\n"
        "✅ الالتزام بها شرط أساسي للبقاء في المجتمع\n"
        "❌ لا تكتب هنا — لو عندك سؤال عن قانون معين، اسأل في `#support`\n\n"
        "القوانين موجودة لحماية الجميع وضمان بيئة تعلّم محترمة."
    ),
    "roles-info": (
        "🎓 **ما هذه القناة؟**\n"
        "هنا شرح نظام المستويات — كيف تترقى من مستوى إلى آخر.\n\n"
        "✅ اقرأ لتفهم المستويات الأربعة ومتطلبات كل واحد\n"
        "✅ الترقية تتم فقط عبر اختبار نهاية المستوى\n"
        "❌ لا تكتب هنا — لو عندك سؤال عن مستواك الحالي، اسأل في `#support`\n\n"
        "لا أحد يترقى بدون أن يثبت كفاءته — هذا ما يجعل الشهادة حقيقية."
    ),
    "start-here": (
        "🏛️ **ما هذه القناة؟**\n"
        "هذا أول مكان تراه عند دخولك السيرفر — بوابتك إلى المجتمع كله.\n\n"
        "✅ اقرأ الترتيب التالي:\n"
        "`#welcome` ← `#rules` ← `#roles-info`\n"
        "✅ بعد ذلك اذهب إلى `#bot-commands`\n"
        "✅ اكتب `!join` هناك لتبدأ رسميًا\n"
        "❌ لا تكتب هنا — هذه القناة للقراءة فقط\n\n"
        "إذا احتجت إلى مساعدة، اسأل في `#ask-nour` في أي وقت 🤝"
    ),
    "announcements": (
        "📢 **ما هذه القناة؟**\n"
        "هنا تُنشر كل التحديثات والأخبار المهمة عن المجتمع من الإدارة.\n\n"
        "✅ اقرأ باستمرار حتى لا تفوتك أي معلومة مهمة\n"
        "❌ لا تكتب هنا — هذه القناة للإدارة فقط، وإذا كان لديك سؤال فاذهب إلى `#support`\n\n"
        "تُنشر الإعلانات أحيانًا بالعربية وأحيانًا بالإنجليزية حسب المحتوى."
    ),

    # ── SYSTEM ──
    "bot-commands": (
        "⭐ **ما هذه القناة؟**\n"
        "القناة الرسمية لكل أوامر البوت — هذا هو المكان الوحيد الذي تعمل فيه الأوامر.\n\n"
        "✅ من الأوامر المتاحة:\n"
        "`!join` — `!done` — `!progress` — `!streak`\n"
        "✅ لرؤية كل الأوامر، اكتب `!help`\n"
        "❌ لا تكتب الأوامر في قنوات أخرى — لن تعمل هناك\n\n"
        "يرد البوت فورًا على أي أمر صحيح."
    ),
    "leaderboard": (
        "🏆 **ما هذه القناة؟**\n"
        "لوحة المتصدرين — تتحدث تلقائيًا بواسطة البوت، ولا يُسمح للأعضاء بالكتابة فيها.\n\n"
        "✅ اقرأ فقط وشاهد ترتيبك مقارنة بزملائك\n"
        "❌ لا تكتب هنا — إذا أردت مناقشة نتيجتك فاذهب إلى `#general-chat`\n\n"
        "يعتمد الترتيب على نقاطك وانضباطك اليومي، وليس على مستواك فقط."
    ),
    "support": (
        "🆘 **ما هذه القناة؟**\n"
        "هل تحتاج إلى مساعدة تقنية أو لا تعرف كيف تستخدم شيئًا في السيرفر؟ هذا مكانك.\n\n"
        "✅ اسأل عن أي مشكلة في البوت أو الأوامر أو القنوات\n"
        "✅ يمكنك الكتابة بالعربية هنا إذا احتجت إلى توضيح سريع\n"
        "❌ للأسئلة عن محتوى الدروس نفسها، اذهب إلى قناة أخرى:\n"
        "`#ask-nour` — `#l0-questions`\n\n"
        "ترد الإدارة أو نور عادةً في أقرب وقت ممكن."
    ),
    "ask-nour": (
        "🤝 **ما هذه القناة؟**\n"
        "مساعدتك الشخصية بالذكاء الاصطناعي — نور موجودة هنا لمساعدتك.\n\n"
        "✅ اسأل عن أي شيء يحيرك أو تحتاج إلى توضيح فيه\n"
        "✅ يمكنك التحدث بالعربية أو الإنجليزية كما تفضل\n"
        "✅ إذا لم تستطع نور مساعدتك، سيُرسل سؤالك إلى الإدارة تلقائيًا\n\n"
        "ترد نور بسرعة، وردها موجّه لك شخصيًا وليس نسخة عامة."
    ),
    "suggestions": (
        "💡 **ما هذه القناة؟**\n"
        "هل لديك فكرة لتحسين المجتمع؟ شاركها هنا.\n\n"
        "✅ اكتب أي فكرة أو ملاحظة تعتقد أنها تفيد الجميع\n"
        "✅ رد على أفكار زملائك برأيك (بإيجابية!)\n"
        "❌ هذا ليس مكانًا للشكاوى الشخصية — استخدم `#support` لذلك\n\n"
        "تقرأ الإدارة كل اقتراح، حتى إن لم ترد على كل واحد."
    ),

    # ── LEVEL 0-3 ZONES ──
    **{
        f"l{level}-daily-tasks": (
            f"📅 **ما هذه القناة؟**\n"
            f"هنا تُنشر مهامك اليومية (7 مهام) — هذا هو قلب نظام التعلّم اليومي الخاص بك.\n\n"
            f"✅ افتح القناة كل يوم وأدِّ المهام بالترتيب\n"
            f"✅ بعد كل مهمة، اذهب إلى `#bot-commands`\n"
            f"✅ اكتب هناك: `!done <اسم المهمة>`\n"
            f"❌ لا تكتب هنا — هذه القناة لعرض المهام فقط، والكتابة تكون في `#bot-commands`\n\n"
            f"تُنشر المهام تلقائيًا الساعة 6 صباحًا كل يوم."
        )
        for level in ("0", "1", "2", "3")
    },
    **{
        f"l{level}-text-practice": (
            f"✍️ **ما هذه القناة؟**\n"
            f"مكانك لتمارين الكتابة الخاصة بمستواك — اكتب وتدرّب بالإنجليزية.\n\n"
            f"✅ اكتب تمرينك هنا بعد إنهاء مهمة الكتابة اليومية\n"
            f"✅ اقرأ تمارين زملائك ورد عليهم بإيجابية\n"
            f"❌ لا تستخدم مترجمًا — الهدف أن تفكر بالإنجليزية مباشرة\n\n"
            f"قد يقدّم لك البوت أو الذكاء الاصطناعي ملاحظات على كتابتك."
        )
        for level in ("0", "1", "2", "3")
    },
    # NOTE: only L0/L1/L2 have a dedicated "-questions" channel in
    # setup_server.py's LEVEL 3 category -- L3 deliberately does NOT
    # (confirmed live during Sahin Phase 1's actual execution: the
    # script's own "not found -- skipped" warning caught this exact
    # mismatch). L3 students use #l3-mentorship for this instead, which
    # already has its own guide below. Do NOT add "l3-questions" back
    # into this loop without first adding the actual channel to
    # setup_server.py's CATEGORIES_CONFIG -- this loop must always
    # mirror real server structure, never assume symmetry across
    # levels.
    **{
        f"l{level}-questions": (
            f"❓ **ما هذه القناة؟**\n"
            f"أسئلتك عن محتوى المستوى {level} — القواعد، المفردات، وأي شيء غير واضح.\n\n"
            f"✅ اسأل بحرية عن أي جزء من مادة هذا المستوى\n"
            + ("✅ يُسمح بالعربية هنا (استثناء خاص بالمستوى 0)\n" if level == "0" else "")
            + "❌ للمساعدة الشخصية الأشمل، اذهب إلى `#ask-nour`\n\n"
            "قد يرد عليك زملاؤك في نفس المستوى أيضًا، فلا تخف من السؤال!"
        )
        for level in ("0", "1", "2")
    },
    **{
        f"l{level}-showcase": (
            f"🎙️ **ما هذه القناة؟**\n"
            f"هنا تشارك تسجيلاتك الصوتية وتحتفل بتقدمك في المستوى {level}.\n\n"
            f"✅ ارفع تسجيلك بعد إنهاء المهمة الصوتية اليومية\n"
            f"✅ رد على زملائك بكلام إيجابي (بالإنجليزية!)\n"
            f"❌ لا تكتب نصًا أو أسئلة هنا — استخدم قناة أخرى لذلك:\n"
            f"`#ask-nour` — `#support`\n\n"
            f"يسجّل البوت تقدمك تلقائيًا عند رفع تسجيلك 🔥"
        )
        for level in ("0", "1", "2", "3")
    },
    "l3-mentorship": (
        "🌟 **ما هذه القناة؟**\n"
        "هذه القناة مخصصة لطلاب المستوى 3 لمساعدة المبتدئين ومشاركة تجربتهم.\n\n"
        "✅ شارك نصائحك أو تجربتك الشخصية في التعلّم\n"
        "✅ رد على أسئلة الطلاب في المستويات الأدنى إذا كان لهم سؤال هنا\n"
        "❌ هذا ليس مكانًا لتمارين المستوى 3 نفسها — استخدم `#l3-text-practice`\n\n"
        "المشاركة هنا اختيارية بالكامل، ولكنها تُحدث فرقًا حقيقيًا مع المبتدئين."
    ),

    # ── COMMUNITY ──
    "general-chat": (
        "💬 **ما هذه القناة؟**\n"
        "دردشة عامة مفتوحة لكل الأعضاء — ولكن يجب أن تكون بالإنجليزية فقط!\n\n"
        "✅ تحدث عن أي موضوع تحبه، من غير ضغط أو تقييم\n"
        "✅ هذا أفضل مكان للتدرّب على المحادثة الحرة\n"
        "❌ العربية ممنوعة هنا (إلا إذا استخدمتها نور لمساعدتك)\n\n"
        "كلما كتبت أكثر، تقدمت أسرع 💪"
    ),
    "introductions": (
        "👋 **ما هذه القناة؟**\n"
        "هل هذه أول مرة تدخل السيرفر؟ عرّف عن نفسك هنا للمجتمع كله.\n\n"
        "✅ اذكر اسمك، بلدك، مستواك في الإنجليزية، وهدفك من الانضمام\n"
        "✅ رحّب بالأعضاء الجدد عندما يعرّفون عن أنفسهم\n"
        "❌ هذا ليس مكانًا للأسئلة أو النقاش — استخدم `#general-chat`\n\n"
        "يبدأ المجتمع كله من نفس النقطة — لا تخف من الحديث!"
    ),
    "events": (
        "📅 **ما هذه القناة؟**\n"
        "الجلسات الصوتية القادمة، التحديات، وكل فعالية في المجتمع.\n\n"
        "✅ تابع الجلسات القادمة وشارك فيها\n"
        "✅ اقترح فعالية جديدة إذا كانت لديك فكرة\n"
        "❌ للتسجيل الفعلي في جلسة صوتية، اذهب إلى القناة الصوتية نفسها وقت الجلسة\n\n"
        "تنشر الإدارة والمشرفون هنا كل ما هو قادم."
    ),
    "daily-word": (
        "📖 **ما هذه القناة؟**\n"
        "كلمة اليوم — كلمة إنجليزية جديدة تتعلمها وتستخدمها في جملة.\n\n"
        "✅ اكتب جملة بالكلمة الجديدة كل يوم\n"
        "✅ صحّح لزملائك بلطف إذا كان في جملتهم خطأ\n"
        "❌ لا تسأل هنا عن كلمات أخرى — استخدم `#ask-nour`\n\n"
        "هذا التمرين اليومي البسيط يبني مفردات حقيقية مع مرور الوقت."
    ),

    # ── ACCOUNTABILITY ──
    "daily-check-in": (
        "☀️ **ما هذه القناة؟**\n"
        "صباحًا: اكتب خطتك لليوم. مساءً: اكتب ما أنجزته.\n\n"
        "✅ صباحًا: قل ما ستفعله اليوم من المهام\n"
        "✅ مساءً: قل ما أنجزته فعلًا وكيف كان يومك\n"
        "❌ هذا ليس مكانًا لتفاصيل المهام نفسها — فقط تسجيل سريع للالتزام\n\n"
        "الانضباط اليومي هو ما يصنع الفرق على المدى البعيد، لا يوم واحد مثالي."
    ),
    "streak-tracker": (
        "🔥 **ما هذه القناة؟**\n"
        "متابعة استمراريتك (streak) — تتحدث تلقائيًا بواسطة البوت.\n\n"
        "✅ اقرأ فقط وشاهد عداد استمراريتك\n"
        "❌ لا تكتب هنا — هذه القناة للبوت فقط\n\n"
        "إذا فاتك يوم، تعود الاستمرارية إلى الصفر — احذر!"
    ),
    "weekly-goals": (
        "🎯 **ما هذه القناة؟**\n"
        "حدّد أهداف أسبوعك كل يوم إثنين.\n\n"
        "✅ اكتب هدفًا واحدًا أو هدفين واضحين لهذا الأسبوع\n"
        "✅ راجع أهداف الأسبوع الماضي وقيّم نفسك\n"
        "❌ يجب أن تكون الأهداف قابلة للقياس، لا عامة مثل \"أتحسّن\"\n\n"
        "الهدف الواضح المكتوب يتحقق أسهل من هدف في ذهنك فقط."
    ),

    # ── RESOURCES ──
    # NOTE: describes CURRENT real behavior only (Wednesday grammar
    # card). Update once Sahin Phase 4.1 ships the vocabulary cheat
    # sheet for real -- see this file's module docstring.
    "cheat-sheets": (
        "📝 **ما هذه القناة؟**\n"
        "ملخصات ومراجع سريعة تساعدك على تذكّر القواعد والمفردات.\n\n"
        "✅ يوم الأربعاء يُنشر ملخص قواعد أسبوعي تلقائي من البوت\n"
        "✅ ثبّت (pin) أي ملخص مهم لك لترجع إليه بسهولة\n"
        "❌ لا تكتب أسئلة هنا — استخدم قناة أخرى لذلك:\n"
        "`#grammar-qa` — `#ask-nour`\n\n"
        "المزيد من المحتوى (مفردات أسبوعية) قريبًا هنا 🔜"
    ),
    "video-library": (
        "🎬 **ما هذه القناة؟**\n"
        "فيديوهات تعليمية مختارة حسب مستواك.\n\n"
        "✅ شارك فيديو مفيدًا شاهدته يساعد زملاءك في نفس مستواك\n"
        "✅ اذكر المستوى المناسب للفيديو عند مشاركته\n"
        "❌ لا تشارك فيديوهات غير تعليمية أو غير مناسبة للمجتمع\n\n"
        "يُجمع المحتوى هنا من الأعضاء والإدارة معًا."
    ),
    "podcast-recs": (
        "🎧 **ما هذه القناة؟**\n"
        "بودكاست مقترح للاستماع — تمرين لأذنك على الإنجليزية الحقيقية.\n\n"
        "✅ شارك بودكاست تحبه واذكر لماذا يفيد التعلّم\n"
        "✅ اذكر مستوى الصعوبة تقريبًا (مبتدئ / متوسط / متقدم)\n"
        "❌ ركّز على محتوى تعليمي أو مفيد للغة، لا أي بودكاست عشوائي\n\n"
        "الاستماع المستمر يبني لهجتك وفهمك دون أن تشعر."
    ),
    "book-club": (
        "📚 **ما هذه القناة؟**\n"
        "كتاب الشهر ومناقشته مع باقي أعضاء المجتمع.\n\n"
        "✅ شارك رأيك في كتاب الشهر الحالي (بالإنجليزية)\n"
        "✅ اقترح كتابًا للشهر القادم إذا كانت لديك فكرة\n"
        "❌ يجب أن تكون الكتب المقترحة مناسبة لمستوى القراءة العام\n\n"
        "القراءة المنتظمة من أقوى طرق تحسين اللغة على المدى البعيد."
    ),

    # ── FEEDBACK ──
    "speaking-feedback": (
        "🎙️ **ما هذه القناة؟**\n"
        "ارفع تسجيلًا صوتيًا واحصل على ملاحظات من الذكاء الاصطناعي وزملائك.\n\n"
        "✅ ارفع تسجيلك واذكر ما تريد ملاحظات عليه بالتحديد (النطق؟ الطلاقة؟)\n"
        "✅ رد على تسجيلات زملائك بملاحظات بنّاءة ومحترمة\n"
        "❌ لا تسخر من نطق أو خطأ أي شخص — كلنا بدأنا من الصفر\n\n"
        "الملاحظات البنّاءة هي ما يجعلك تتحسن أسرع."
    ),
    "writing-feedback": (
        "✍️ **ما هذه القناة؟**\n"
        "أرسل كتابتك واحصل على تصحيح وملاحظات حقيقية.\n\n"
        "✅ اكتب نصك واذكر مستواك حتى تكون الملاحظات مناسبة\n"
        "✅ اقرأ تصحيحات زملائك لتتعلم من أخطائهم أيضًا\n"
        "❌ لا تستخدم مترجمًا قبل الإرسال — الهدف تصحيح كتابتك الحقيقية\n\n"
        "يركّز التصحيح هنا على القواعد والمفردات والترتيب."
    ),
    "accent-feedback": (
        "🗣️ **ما هذه القناة؟**\n"
        "مقاطع نطق (accent) واحصل على ملاحظات على لهجتك الأمريكية.\n\n"
        "✅ سجّل نفسك تنطق كلمة أو جملة معينة تتدرب عليها\n"
        "✅ اذكر الصوت أو الحرف الذي تشعر أنه صعب عليك بالتحديد\n"
        "❌ هذا مختلف عن `#speaking-feedback` — هذا للنطق فقط، لا الطلاقة العامة\n\n"
        "النطق الصحيح يتحسن بالتكرار والملاحظات المستمرة، لا في يوم واحد."
    ),
    "grammar-qa": (
        "📖 **ما هذه القناة؟**\n"
        "أسئلة قواعد اللغة (grammar) وإجاباتها.\n\n"
        "✅ اسأل عن أي قاعدة غير واضحة لك، مهما كانت\n"
        "✅ إذا كنت تعرف الإجابة، ساعد زميلك واشرح له\n"
        "❌ للمساعدة الشخصية الأشمل غير القواعد، اذهب إلى `#ask-nour`\n\n"
        "قاعدة واحدة مفهومة جيدًا أفضل من عشر قواعد مشوّشة."
    ),
}
