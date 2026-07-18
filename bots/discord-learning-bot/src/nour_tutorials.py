"""Nour (نور) — Micro-Tutorials (Rawiya R4).

Pre-written, MSA, step-by-step guides for common confusion points.
NOT AI-generated — too important to risk grammar errors. Each tutorial
is a fixed MSA string that Nour sends when she detects the student
is stuck on a specific problem.

Gated behind 'nour_tutorials' feature flag.
"""
import logging

import discord

from . import database

logger = logging.getLogger("empire-bot.nour.tutorials")

# ============================================================
#  TUTORIAL CONTENT (all MSA, bidi-safe)
# ============================================================

TUTORIALS = {
    "recording_mobile": (
        "🎙️ **كيف تسجّل صوتك على الهاتف:**\n\n"
        "**الخطوات:**\n"
        "١. اذهب إلى قناة `#l0-showcase`\n"
        "٢. اضغط مع الاستمرار على زر الميكروفون (بجانب مربع الكتابة)\n"
        "٣. تحدّث وأنت تضغط باستمرار\n"
        "٤. ارفع إصبعك لإرسال التسجيل\n\n"
        "**إذا لم تجد زر الميكروفون:**\n"
        "• تأكّد من أن مربع الكتابة فارغ\n"
        "• اذهب إلى إعدادات هاتفك ← التطبيقات ← Discord ← اسمح بالميكروفون\n\n"
        "**للتسجيل الطويل (بدون الضغط المستمر):**\n"
        "اضغط واسحب لأعلى نحو أيقونة القفل 🔒 ← يمكنك التحدث بحرية ← اضغط إرسال عند الانتهاء"
    ),

    "wrong_channel": (
        "📍 **الأوامر تعمل فقط في `#bot-commands`:**\n\n"
        "كل الأوامر التي تبدأ بـ `!` يجب كتابتها في قناة `#bot-commands` فقط.\n\n"
        "**لماذا؟** لأن القنوات الأخرى مخصصة لأغراض مختلفة:\n"
        "• `#l0-showcase` ← للتسجيلات الصوتية فقط\n"
        "• `#l0-text-practice` ← لتمارين الكتابة\n"
        "• `#general-chat` ← للمحادثة\n\n"
        "**الحل:** اذهب إلى `#bot-commands` واكتب أمرك هناك 👍"
    ),

    "done_without_proof": (
        "⚠️ **يجب إنجاز المهمة قبل تسجيلها:**\n\n"
        "النظام يتأكد من أنك أنجزت المهمة فعلًا قبل منحك النقاط:\n\n"
        "• **النطق/المحاكاة/الكلام:** أرسل تسجيلًا صوتيًا في `#l0-showcase` أولًا\n"
        "• **المفردات/الاستماع:** أجب عن سؤال البوت بشكل صحيح\n"
        "• **الكتابة:** اكتب نصًا في `#l0-text-practice` أولًا\n"
        "• **المشاركة:** اكتب في `#general-chat` أو ابقَ في غرفة صوتية ١٠ دقائق\n\n"
        "**الترتيب الصحيح:** أنجز المهمة ← ثم اكتب `!done` في `#bot-commands`"
    ),

    "streak_broken": (
        "💔 **انقطعت سلسلتك — لا بأس!**\n\n"
        "السلسلة تنقطع عندما يمر يوم كامل بدون إنجاز أي مهمة.\n\n"
        "**ما يجب فعله الآن:**\n"
        "١. لا تُحبَط — الجميع يمر بهذا\n"
        "٢. ابدأ سلسلة جديدة **اليوم** — أنجز مهمة واحدة الآن\n"
        "٣. أسهل مهمة: اكتب جملة في `#l0-text-practice` ثم `!6`\n\n"
        "💡 **نصيحة للمستقبل:** في الأيام الصعبة، أنجز مهمة واحدة فقط — "
        "هذا يكفي للحفاظ على السلسلة."
    ),

    "find_tasks": (
        "📋 **أين تجد مهامك اليومية:**\n\n"
        "**الخطوات:**\n"
        "١. افتح Discord\n"
        "٢. اذهب إلى خادم Empire English\n"
        "٣. ابحث عن قناة `#l0-daily-tasks` (في مجموعة LEVEL 0)\n"
        "٤. ستجد المهام السبع مكتوبة هناك\n\n"
        "**أو اكتب:**\n"
        "`!progress` في `#bot-commands` — سيُظهر لك ما أنجزته وما تبقى.\n\n"
        "**ملاحظة:** المهام تُنشر كل يوم الساعة ٦ صباحًا (توقيت دبي)."
    ),

    "practice_platform_access": (
        "🌐 **كيف تدخل منصة التمرين:**\n\n"
        "**الخطوات:**\n"
        "١. اكتب `!link` في `#bot-commands`\n"
        "٢. سيرسل لك البوت رابطًا خاصًا\n"
        "٣. اضغط على الرابط — ستفتح المنصة في المتصفح\n"
        "٤. رمز دخولك يُحفظ تلقائيًا\n\n"
        "**إذا لم تعمل المنصة:**\n"
        "• امسح ذاكرة المتصفح وأعد تحميل الصفحة\n"
        "• اكتب `!link` مرة أخرى للحصول على رابط جديد\n"
        "• جرّب متصفحًا مختلفًا\n\n"
        "⚠️ **مهم:** لا تشارك رابطك مع أحد — هو خاص بك فقط."
    ),

    "quiz_struggling": (
        "📝 **لا تقلق من الإجابات الخاطئة:**\n\n"
        "الخطأ جزء طبيعي من التعلّم. إليك بعض النصائح:\n\n"
        "**للمفردات:**\n"
        "• اكتب `!words` لمراجعة الكلمات السابقة\n"
        "• ركّز على ٣ كلمات جديدة فقط يوميًا\n"
        "• استخدم الكلمة في جملة لتثبيتها\n\n"
        "**للاستماع:**\n"
        "• أعد الاستماع عدة مرات — لا عيب في ذلك\n"
        "• ابدأ بسرعة بطيئة (Slow) ثم زِد تدريجيًا\n\n"
        "💡 **تذكّر:** التحسّن يأتي مع التكرار اليومي، ليس مع الكمال الفوري."
    ),

    "first_day_guide": (
        "🌟 **دليلك ليومك الأول:**\n\n"
        "**ابدأ بهذه الخطوات بالترتيب:**\n\n"
        "١. اكتب `!join` في `#bot-commands` (مرة واحدة فقط)\n"
        "٢. اذهب إلى `#l0-text-practice` واكتب أي جملة بالإنجليزية\n"
        "٣. اكتب `!6` في `#bot-commands` (تسجيل مهمة الكتابة)\n"
        "٤. 🎉 مبارك! أنجزت أول مهمة!\n\n"
        "**بعد ذلك (اختياري اليوم):**\n"
        "٥. اكتب `!link` للحصول على رابط منصة التمرين\n"
        "٦. جرّب تمرين النطق في المنصة\n"
        "٧. أرسل تسجيلك في `#l0-showcase` ثم اكتب `!1`\n\n"
        "**لا تحاول إنجاز ٧/٧ في اليوم الأول** — ابدأ بما تستطيع وزِد تدريجيًا."
    ),
}


# ============================================================
#  TRIGGER DETECTION + DISPATCH
# ============================================================

async def check_and_send_tutorial(discord_id: str, trigger_type: str,
                                  member: discord.Member) -> bool:
    """Check if a tutorial should be sent based on the trigger.

    Returns True if a tutorial was sent, False otherwise.
    """
    if not database.is_feature_enabled("nour_tutorials"):
        return False

    tutorial_key = _get_tutorial_for_trigger(trigger_type)
    if not tutorial_key:
        return False

    # Rate limit: don't send the same tutorial twice in 24h
    conn = database._connect()
    today = __import__("datetime").date.today().isoformat()
    row = conn.execute(
        "SELECT 1 FROM nour_outreach_log WHERE discord_id=? AND outreach_type=? AND date=?",
        (discord_id, f"tutorial_{tutorial_key}", today),
    ).fetchone()
    conn.close()

    if row:
        return False  # Already sent today

    # Send the tutorial
    content = TUTORIALS.get(tutorial_key)
    if not content:
        return False

    try:
        await member.send(content)
        # Log it
        conn = database._connect()
        conn.execute(
            "INSERT INTO nour_outreach_log (discord_id, outreach_type, date) VALUES (?, ?, ?)",
            (discord_id, f"tutorial_{tutorial_key}", today),
        )
        conn.commit()
        conn.close()
        logger.info(f"Nour tutorial: sent '{tutorial_key}' to {member.display_name}")
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


def _get_tutorial_for_trigger(trigger_type: str) -> Optional[str]:
    """Map a trigger to the appropriate tutorial."""
    mapping = {
        "recording_failed": "recording_mobile",
        "wrong_channel_command": "wrong_channel",
        "done_no_proof": "done_without_proof",
        "streak_lost": "streak_broken",
        "cant_find_tasks": "find_tasks",
        "platform_error": "practice_platform_access",
        "quiz_3_wrong": "quiz_struggling",
        "first_day_confused": "first_day_guide",
    }
    return mapping.get(trigger_type)
