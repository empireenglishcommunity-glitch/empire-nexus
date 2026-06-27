"""AI automation layer.

Uses Groq's free API (https://console.groq.com) to generate short, personalized
Arabic motivation. If no API key is set, or the network fails, it falls back to
high-quality built-in Arabic messages so the bot ALWAYS works (100% free, no
hard dependency on any paid service).
"""
import random
from . import config

_MODEL = "llama-3.3-70b-versatile"

# Built-in fallback pools (used when no AI key or on error)
_PRAISE = [
    "أحسنت! كل تحدٍّ تنجزه يبني نسخة أقوى منك. 💪",
    "خطوة رائعة اليوم. الاستمرارية هي السرّ، وأنت تثبت ذلك. 🔥",
    "فخور بك! خروجك من منطقة الراحة هو عين الشجاعة. 👑",
    "ممتاز! شعورك الآن دليل على أنك تنمو فعلًا. 🌱",
    "بطل! واصل، فالأيام القادمة ستكون أسهل عليك. ⭐",
]
_LOW_FEELING = [
    "شعور صعب لكنك أنجزت رغم ذلك، وهذا هو الانتصار الحقيقي. 🤍",
    "لا بأس أن يكون اليوم ثقيلًا، المهم أنك لم تستسلم. واصل غدًا. 💛",
    "تذكّر: الانزعاج مؤقّت، لكن القوة التي تبنيها تبقى. أنت تتقدّم. 🌟",
]
_DAILY_INTROS = [
    "صباح الإرادة يا أبطال! تحدّي اليوم في انتظاركم 👇",
    "يوم جديد، فرصة جديدة لتصبحوا أقوى. هيا بنا 🔥",
    "النمو يبدأ عند حافة الراحة. تحدّي اليوم وصل 👑",
]


def _client():
    if not config.GROQ_API_KEY:
        return None
    try:
        from groq import Groq
        return Groq(api_key=config.GROQ_API_KEY)
    except Exception:
        return None


def _ask(prompt: str, max_tokens: int = 160) -> str:
    """Send a prompt to Groq. Returns '' on any failure."""
    client = _client()
    if client is None:
        return ""
    try:
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "أنت مدرّب تحفيزي ودود لمجتمع عربي اسمه Empire English Community. "
                        "ترد دائمًا بالعربية الفصحى المبسّطة، بإيجاز شديد (جملتان كحد أقصى)، "
                        "بأسلوب دافئ ومشجّع. لا تستخدم لغة مبالغ فيها."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.8,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return ""


def feedback(username: str, day: int, feeling: int, task: str) -> str:
    """Personalized response when a participant logs a completed challenge."""
    prompt = (
        f"المشارك {username} أكمل تحدّي اليوم {day}: \"{task}\". "
        f"قيّم شعوره بـ {feeling} من 10. اكتب رسالة تشجيع قصيرة ومخصّصة له."
    )
    ai = _ask(prompt)
    if ai:
        return ai
    if feeling <= 4:
        return random.choice(_LOW_FEELING)
    return random.choice(_PRAISE)


def daily_intro(day: int, task: str) -> str:
    """Motivational intro line posted above the daily challenge."""
    prompt = (
        f"اكتب جملة افتتاحية تحفيزية قصيرة جدًا (سطر واحد) لليوم {day} من تحدٍّ "
        f"مدته 30 يومًا. تحدّي اليوم هو: \"{task}\"."
    )
    ai = _ask(prompt)
    return ai or random.choice(_DAILY_INTROS)


def weekly_recap(week: int, stats: dict) -> str:
    """Generate a weekly summary from aggregate stats."""
    prompt = (
        f"اكتب ملخصًا تحفيزيًا قصيرًا (3 أسطر) لنهاية الأسبوع {week} من تحدّي 30 يوم. "
        f"عدد المشاركين النشطين: {stats.get('active', 0)}. "
        f"إجمالي التحديات المنجزة هذا الأسبوع: {stats.get('done', 0)}. "
        f"بطل الأسبوع: {stats.get('champion', 'لم يُحدّد بعد')}. "
        f"اختم بتشجيع للأسبوع القادم."
    )
    ai = _ask(prompt, max_tokens=220)
    if ai:
        return ai
    return (
        f"🏁 **ملخّص الأسبوع {week}**\n"
        f"المشاركون النشطون: {stats.get('active', 0)} | "
        f"التحديات المنجزة: {stats.get('done', 0)}\n"
        f"🏆 بطل الأسبوع: {stats.get('champion', 'لم يُحدّد بعد')}\n"
        f"أنتم تكبرون كل يوم. الأسبوع القادم أقوى بإذن الله! 💪"
    )
