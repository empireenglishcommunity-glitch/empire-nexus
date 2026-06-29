#!/usr/bin/env python3
"""
Empire English Community Bot — Discord Server Setup Script
===========================================================

This script AUTOMATICALLY configures your Discord server with the complete
Empire English Learning System structure:
  - Creates 9 roles with correct colors, permissions, and hierarchy
  - Locks down @everyone (no default access)
  - Creates 11 categories with 42+ channels
  - Applies level-gated permissions (L0 can't see L1 zone, etc.)
  - Sets up voice channels with correct connect/speak permissions
  - Posts welcome, rules, and roles content
  - Prints all webhook-ready channel IDs for n8n integration

Usage:
    1. Set DISCORD_TOKEN and GUILD_ID below (or in .env)
    2. Run: python scripts/setup_server.py
    3. Done — full server configured in ~60 seconds

WARNING: This MODIFIES your server. Run on a fresh/test server first.

Requirements: discord.py >= 2.3 (in requirements.txt)
"""
import asyncio
import os
import sys
from pathlib import Path

# Add parent to path so we can import config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import discord
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ============================================================
#  CONFIGURATION
# ============================================================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID", "0") or "0")

# ============================================================
#  ROLE DEFINITIONS (top to bottom hierarchy)
# ============================================================
ROLES_CONFIG = [
    {
        "name": "🏛️ Founder",
        "color": 0xD4AF37,
        "hoist": True,
        "permissions": discord.Permissions(administrator=True),
    },
    {
        "name": "🛡️ Admin",
        "color": 0xE74C3C,
        "hoist": True,
        "permissions": discord.Permissions(administrator=True),
    },
    {
        "name": "⚔️ Moderator",
        "color": 0xE67E22,
        "hoist": True,
        "permissions": discord.Permissions(
            view_channel=True, send_messages=True, manage_messages=True,
            kick_members=True, mute_members=True, move_members=True,
            mention_everyone=True, embed_links=True, attach_files=True,
            read_message_history=True, add_reactions=True, connect=True, speak=True,
        ),
    },
    {
        "name": "🌟 سفير | Ambassador",
        "color": 0x9B59B6,
        "hoist": True,
        "permissions": discord.Permissions(
            view_channel=True, send_messages=True, embed_links=True,
            attach_files=True, read_message_history=True, add_reactions=True,
            connect=True, speak=True, priority_speaker=True,
        ),
    },
    {
        "name": "👑 Level 3 | طليق",
        "color": 0xC27C0E,
        "hoist": True,
        "permissions": discord.Permissions.none(),
    },
    {
        "name": "🚀 Level 2 | متواصل",
        "color": 0x3498DB,
        "hoist": True,
        "permissions": discord.Permissions.none(),
    },
    {
        "name": "💪 Level 1 | متقدم",
        "color": 0x2ECC71,
        "hoist": True,
        "permissions": discord.Permissions.none(),
    },
    {
        "name": "🌱 Level 0 | مبتدئ",
        "color": 0xA8E6CF,
        "hoist": True,
        "permissions": discord.Permissions.none(),
    },
    {
        "name": "🤖 Empire Bot",
        "color": 0x2C3E50,
        "hoist": False,
        "permissions": discord.Permissions(
            view_channel=True, send_messages=True, manage_messages=True,
            embed_links=True, attach_files=True, read_message_history=True,
            add_reactions=True, connect=True, speak=True, manage_roles=True,
        ),
    },
]


# ============================================================
#  CATEGORY & CHANNEL DEFINITIONS
# ============================================================
# Permission overwrite keys:
#   "@everyone" = guild default role
#   "bot" = the bot's own role
#   Any other string = role name from ROLES_CONFIG

def _ow(**kwargs):
    """Shortcut to create a PermissionOverwrite."""
    return discord.PermissionOverwrite(**kwargs)

# --- Reusable permission patterns ---
_DENY_ALL = _ow(view_channel=False)
_VIEW_ONLY = _ow(view_channel=True, send_messages=False, read_message_history=True, add_reactions=True)
_VIEW_SEND = _ow(view_channel=True, send_messages=True, read_message_history=True, add_reactions=True, embed_links=True, attach_files=True)
_VIEW_SEND_VOICE = _ow(view_channel=True, send_messages=True, read_message_history=True, add_reactions=True, embed_links=True, attach_files=True, connect=True, speak=True, use_voice_activation=True)
_VOICE_ONLY = _ow(view_channel=True, connect=True, speak=True, use_voice_activation=True)
_BOT_FULL = _ow(view_channel=True, send_messages=True, embed_links=True, attach_files=True, manage_messages=True, add_reactions=True, mention_everyone=True)
_READ_ONLY_ADMIN = _ow(view_channel=True, send_messages=False, read_message_history=True, add_reactions=True)

CATEGORIES_CONFIG = [
    # ── Category 1: WELCOME (visible to everyone, read-only) ──
    {
        "name": "📋 أهلاً | WELCOME",
        "overwrites": {
            "@everyone": _ow(view_channel=True, send_messages=False, read_message_history=True, add_reactions=True),
            "bot": _BOT_FULL,
            "⚔️ Moderator": _ow(send_messages=True),
            "🛡️ Admin": _ow(send_messages=True),
        },
        "channels": [
            {"name": "welcome", "type": "text", "topic": "مرحبًا بيك في Empire English Community 🏛️"},
            {"name": "rules", "type": "text", "topic": "قوانين المجتمع — اقرأها واقبلها"},
            {"name": "roles-info", "type": "text", "topic": "إزاي المستويات شغالة وإزاي تترقى"},
            {"name": "announcements", "type": "text", "topic": "إعلانات رسمية وتحديثات"},
        ],
    },
    # ── Category 2: SYSTEM ──
    {
        "name": "⚙️ الأوامر | SYSTEM",
        "overwrites": {
            "@everyone": _DENY_ALL,
            "🌱 Level 0 | مبتدئ": _VIEW_SEND,
            "💪 Level 1 | متقدم": _VIEW_SEND,
            "🚀 Level 2 | متواصل": _VIEW_SEND,
            "👑 Level 3 | طليق": _VIEW_SEND,
            "🌟 سفير | Ambassador": _VIEW_SEND,
            "bot": _BOT_FULL,
        },
        "channels": [
            {"name": "bot-commands", "type": "text", "topic": "⭐ اكتب الأوامر هنا: !join !done !progress !streak"},
            {"name": "leaderboard", "type": "text", "topic": "🏆 لوحة المتصدرين — تتحدث تلقائيًا",
             "override": {"🌱 Level 0 | مبتدئ": _VIEW_ONLY, "💪 Level 1 | متقدم": _VIEW_ONLY, "🚀 Level 2 | متواصل": _VIEW_ONLY, "👑 Level 3 | طليق": _VIEW_ONLY}},
            {"name": "support", "type": "text", "topic": "🆘 محتاج مساعدة؟ اسأل هنا"},
            {"name": "suggestions", "type": "text", "topic": "💡 عندك فكرة لتحسين المجتمع؟"},
        ],
    },
    # ── Category 3: LEVEL 0 ZONE ──
    {
        "name": "🌱 المستوى 0 | LEVEL 0",
        "overwrites": {
            "@everyone": _DENY_ALL,
            "🌱 Level 0 | مبتدئ": _VIEW_SEND_VOICE,
            "💪 Level 1 | متقدم": _VIEW_SEND_VOICE,
            "🚀 Level 2 | متواصل": _VIEW_ONLY,
            "👑 Level 3 | طليق": _VIEW_ONLY,
            "🌟 سفير | Ambassador": _VIEW_SEND_VOICE,
            "bot": _BOT_FULL,
        },
        "channels": [
            {"name": "l0-daily-tasks", "type": "text", "topic": "📅 المهام اليومية — تنزل الساعة 6 صباحًا كل يوم"},
            {"name": "l0-text-practice", "type": "text", "topic": "✍️ تمارين الكتابة — اكتب هنا"},
            {"name": "l0-voice-1", "type": "voice"},
            {"name": "l0-voice-2", "type": "voice"},
            {"name": "l0-questions", "type": "text", "topic": "❓ أسئلة — العربي مسموح هنا بس"},
            {"name": "l0-showcase", "type": "text", "topic": "🎙️ شارك تسجيلاتك واحتفل بتقدمك!"},
        ],
    },
    # ── Category 4: LEVEL 1 ZONE ──
    {
        "name": "💪 المستوى 1 | LEVEL 1",
        "overwrites": {
            "@everyone": _DENY_ALL,
            "🌱 Level 0 | مبتدئ": _DENY_ALL,
            "💪 Level 1 | متقدم": _VIEW_SEND_VOICE,
            "🚀 Level 2 | متواصل": _VIEW_SEND_VOICE,
            "👑 Level 3 | طليق": _VIEW_ONLY,
            "🌟 سفير | Ambassador": _VIEW_SEND_VOICE,
            "bot": _BOT_FULL,
        },
        "channels": [
            {"name": "l1-daily-tasks", "type": "text", "topic": "📅 مهام المستوى الأول اليومية"},
            {"name": "l1-text-practice", "type": "text", "topic": "✍️ تمارين فقرات كاملة"},
            {"name": "l1-voice-1", "type": "voice"},
            {"name": "l1-voice-2", "type": "voice"},
            {"name": "l1-questions", "type": "text", "topic": "❓ أسئلة عن محتوى Level 1"},
            {"name": "l1-showcase", "type": "text", "topic": "🎙️ شارك تسجيلاتك وتقدمك"},
        ],
    },
    # ── Category 5: LEVEL 2 ZONE ──
    {
        "name": "🚀 المستوى 2 | LEVEL 2",
        "overwrites": {
            "@everyone": _DENY_ALL,
            "🌱 Level 0 | مبتدئ": _DENY_ALL,
            "💪 Level 1 | متقدم": _DENY_ALL,
            "🚀 Level 2 | متواصل": _VIEW_SEND_VOICE,
            "👑 Level 3 | طليق": _VIEW_SEND_VOICE,
            "🌟 سفير | Ambassador": _VIEW_SEND_VOICE,
            "bot": _BOT_FULL,
        },
        "channels": [
            {"name": "l2-daily-tasks", "type": "text", "topic": "📅 مهام المستوى الثاني"},
            {"name": "l2-text-practice", "type": "text", "topic": "✍️ مقالات وآراء وكتابة متقدمة"},
            {"name": "l2-voice-1", "type": "voice"},
            {"name": "l2-voice-2", "type": "voice"},
            {"name": "l2-debate", "type": "voice"},
            {"name": "l2-questions", "type": "text", "topic": "❓ أسئلة عن محتوى Level 2"},
            {"name": "l2-showcase", "type": "text", "topic": "📝 شارك مقالاتك وعروضك"},
        ],
    },
    # ── Category 6: LEVEL 3 ZONE ──
    {
        "name": "👑 المستوى 3 | LEVEL 3",
        "overwrites": {
            "@everyone": _DENY_ALL,
            "🌱 Level 0 | مبتدئ": _DENY_ALL,
            "💪 Level 1 | متقدم": _DENY_ALL,
            "🚀 Level 2 | متواصل": _DENY_ALL,
            "👑 Level 3 | طليق": _VIEW_SEND_VOICE,
            "🌟 سفير | Ambassador": _VIEW_SEND_VOICE,
            "bot": _BOT_FULL,
        },
        "channels": [
            {"name": "l3-daily-tasks", "type": "text", "topic": "📅 مهام المستوى الثالث المتقدمة"},
            {"name": "l3-text-practice", "type": "text", "topic": "✍️ كتابة متقدمة وأسلوب"},
            {"name": "l3-voice-1", "type": "voice"},
            {"name": "l3-voice-2", "type": "voice"},
            {"name": "l3-debate", "type": "voice"},
            {"name": "l3-mentorship", "type": "text", "topic": "🌟 ساعد المبتدئين وشارك تجربتك"},
            {"name": "l3-showcase", "type": "text", "topic": "👑 أعمال متقدمة وعروض"},
        ],
    },
    # ── Category 7: COMMUNITY (all members) ──
    {
        "name": "🌍 المجتمع | COMMUNITY",
        "overwrites": {
            "@everyone": _DENY_ALL,
            "🌱 Level 0 | مبتدئ": _VIEW_SEND_VOICE,
            "💪 Level 1 | متقدم": _VIEW_SEND_VOICE,
            "🚀 Level 2 | متواصل": _VIEW_SEND_VOICE,
            "👑 Level 3 | طليق": _VIEW_SEND_VOICE,
            "🌟 سفير | Ambassador": _VIEW_SEND_VOICE,
            "bot": _BOT_FULL,
        },
        "channels": [
            {"name": "general-chat", "type": "text", "topic": "💬 دردشة عامة — بالإنجليزي بس!"},
            {"name": "introductions", "type": "text", "topic": "👋 عرّف نفسك للمجتمع!"},
            {"name": "voice-lounge", "type": "voice"},
            {"name": "events", "type": "text", "topic": "📅 جلسات صوتية قادمة وتحديات"},
            {"name": "daily-word", "type": "text", "topic": "📖 كلمة اليوم — استخدمها في جملة!"},
        ],
    },
    # ── Category 8: ACCOUNTABILITY ──
    {
        "name": "📊 المتابعة | ACCOUNTABILITY",
        "overwrites": {
            "@everyone": _DENY_ALL,
            "🌱 Level 0 | مبتدئ": _VIEW_SEND,
            "💪 Level 1 | متقدم": _VIEW_SEND,
            "🚀 Level 2 | متواصل": _VIEW_SEND,
            "👑 Level 3 | طليق": _VIEW_SEND,
            "🌟 سفير | Ambassador": _VIEW_SEND,
            "bot": _BOT_FULL,
        },
        "channels": [
            {"name": "daily-check-in", "type": "text", "topic": "☀️ الصبح: خطتك. 🌙 بالليل: إنجازك"},
            {"name": "streak-tracker", "type": "text", "topic": "🔥 متابعة الاستمرارية — تتحدث تلقائيًا",
             "override": {"🌱 Level 0 | مبتدئ": _VIEW_ONLY, "💪 Level 1 | متقدم": _VIEW_ONLY, "🚀 Level 2 | متواصل": _VIEW_ONLY, "👑 Level 3 | طليق": _VIEW_ONLY}},
            {"name": "weekly-goals", "type": "text", "topic": "🎯 حدد أهداف الأسبوع كل إثنين"},
        ],
    },
    # ── Category 9: RESOURCES ──
    {
        "name": "📚 المصادر | RESOURCES",
        "overwrites": {
            "@everyone": _DENY_ALL,
            "🌱 Level 0 | مبتدئ": _VIEW_SEND,
            "💪 Level 1 | متقدم": _VIEW_SEND,
            "🚀 Level 2 | متواصل": _VIEW_SEND,
            "👑 Level 3 | طليق": _VIEW_SEND,
            "🌟 سفير | Ambassador": _VIEW_SEND,
            "bot": _BOT_FULL,
        },
        "channels": [
            {"name": "cheat-sheets", "type": "text", "topic": "📝 ملخصات سريعة ومراجع"},
            {"name": "video-library", "type": "text", "topic": "🎬 فيديوهات مختارة حسب المستوى"},
            {"name": "podcast-recs", "type": "text", "topic": "🎧 بودكاست مقترح للاستماع"},
            {"name": "book-club", "type": "text", "topic": "📚 كتاب الشهر + مناقشة"},
        ],
    },
    # ── Category 10: FEEDBACK ──
    {
        "name": "💬 التقييم | FEEDBACK",
        "overwrites": {
            "@everyone": _DENY_ALL,
            "🌱 Level 0 | مبتدئ": _VIEW_SEND,
            "💪 Level 1 | متقدم": _VIEW_SEND,
            "🚀 Level 2 | متواصل": _VIEW_SEND,
            "👑 Level 3 | طليق": _VIEW_SEND,
            "🌟 سفير | Ambassador": _VIEW_SEND,
            "bot": _BOT_FULL,
        },
        "channels": [
            {"name": "speaking-feedback", "type": "text", "topic": "🎙️ ارفع تسجيل ← AI + زملائك يردوا عليك"},
            {"name": "writing-feedback", "type": "text", "topic": "✍️ ابعت كتابتك ← تصحيح وملاحظات"},
            {"name": "accent-feedback", "type": "text", "topic": "🗣️ مقاطع نطق ← feedback على لهجتك"},
            {"name": "grammar-qa", "type": "text", "topic": "📖 أسئلة قواعد وإجابات"},
        ],
    },
    # ── Category 11: ADMIN (hidden) ──
    {
        "name": "🔒 الإدارة | ADMIN",
        "overwrites": {
            "@everyone": _DENY_ALL,
            "🌱 Level 0 | مبتدئ": _DENY_ALL,
            "💪 Level 1 | متقدم": _DENY_ALL,
            "🚀 Level 2 | متواصل": _DENY_ALL,
            "👑 Level 3 | طليق": _DENY_ALL,
            "🌟 سفير | Ambassador": _DENY_ALL,
            "⚔️ Moderator": _VIEW_SEND,
            "🛡️ Admin": _VIEW_SEND,
            "bot": _BOT_FULL,
        },
        "channels": [
            {"name": "admin-chat", "type": "text", "topic": "نقاش خاص بالإدارة"},
            {"name": "mod-actions", "type": "text", "topic": "سجل إجراءات الإدارة"},
            {"name": "member-notes", "type": "text", "topic": "ملاحظات على الأعضاء"},
            {"name": "bot-logs", "type": "text", "topic": "سجل أخطاء البوت"},
        ],
    },
]


# ============================================================
#  WELCOME CONTENT (auto-posted to channels after creation)
# ============================================================
WELCOME_MESSAGE = """🏛️ **Welcome to Empire English Community**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The Empire English System is **NOT a course.**
It is a **Learning Operating System.**

✅ American accent training from Day 1
✅ 7 daily tasks (45-75 min for Core track)
✅ Weekly assessments with real scores
✅ AI-powered feedback on every submission
✅ Community voice lounges for real practice
✅ Level advancement through demonstrated competency

**YOUR JOURNEY:**
🌱 Level 0: Absolute Beginner (8-12 weeks)
💪 Level 1: Survival English (10-14 weeks)
🚀 Level 2: Communication (12-16 weeks)
👑 Level 3: Fluency & Native Accent (ongoing mastery)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 **START HERE:**
1. Read #rules
2. Accept the rules screening
3. Check #roles-info to understand levels
4. Your onboarding buddy will contact you within 12 hours

🏛️ *System over instructor. Execution over theory. Common sense first.*
"""

RULES_MESSAGE = """🏛️ **EMPIRE ENGLISH — COMMUNITY RULES**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🗣️ **RULE 1: English Only**
All text and voice channels are English-only.
Exception: #l0-questions (one-sentence Arabic clarifications).
L0-L1: gentle reminders. L2+: enforcement applies.

📚 **RULE 2: Complete Your Daily Tasks**
The system works when YOU work it.
7 tasks daily. Check in morning. Report evening.
Consistency > perfection.

🤝 **RULE 3: Support, Don't Judge**
Everyone here started at zero.
Correct with kindness. Celebrate small wins.
Never mock pronunciation or mistakes.

🎙️ **RULE 4: Voice Lounges**
Mic required (camera optional).
Max 2 minutes continuous talking (let others speak).
10-minute minimum for it to count.
Stay on topic during structured sessions.

📝 **RULE 5: Submissions & Feedback**
Record and submit your speaking missions.
Give constructive feedback to others.
Accept feedback gracefully — it's how you grow.

🚫 **RULE 6: Zero Tolerance**
No harassment, hate speech, or bullying.
No spam, self-promotion, or off-topic flooding.
No sharing of private recordings without consent.
Violations → immediate mod review.

📈 **RULE 7: Advancement**
No skipping levels. No exceptions.
You advance when you demonstrate competency.
The exit exam is the only way up.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

By being here, you agree to these rules.
Questions? → #support
"""


ROLES_INFO_MESSAGE = """🏛️ **HOW LEVELS WORK**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Every member starts at their placement level.
You advance ONLY by passing the Level Exit Exam.
No shortcuts. No exceptions. The system works because the standards are real.

🌱 **LEVEL 0 — Absolute Beginner**
• 0-500 words | All 44 English sounds
• Goal: 60-second self-introduction
• Duration: 8-12 weeks

💪 **LEVEL 1 — Survival English**
• 500-1,500 words | Daily conversations
• Goal: 2-minute unscripted monologue
• Duration: 10-14 weeks

🚀 **LEVEL 2 — Communication**
• 1,500-3,000 words | Complex topics
• Goal: 5-minute presentation on any topic
• Duration: 12-16 weeks

👑 **LEVEL 3 — Fluency & Native Accent**
• 3,000-5,000+ words | Native-like flow
• Ongoing mastery with quarterly certification
• Duration: Lifetime membership

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 **HOW TO ADVANCE:**
1. Complete daily tasks consistently (7/day)
2. Score well on weekly assessments (Sunday)
3. When ready: request the Exit Exam
4. Pass ALL 5 sections → automatic level-up 🎉

No one advances without earning it.
That's what makes an Empire credential real.
"""


# ============================================================
#  MAIN SETUP CLASS
# ============================================================

class ServerSetup(discord.Client):
    """Automated Discord server configuration client."""

    def __init__(self, guild_id: int):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        super().__init__(intents=intents)
        self.target_guild_id = guild_id
        self.created_roles: dict[str, discord.Role] = {}

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")
        guild = self.get_guild(self.target_guild_id)
        if not guild:
            print(f"❌ Guild ID {self.target_guild_id} not found.")
            await self.close()
            return

        print(f"🎯 Target server: {guild.name} ({guild.member_count} members)")
        print("=" * 60)

        try:
            await self._setup_server(guild)
            print("\n" + "=" * 60)
            print("🎉 SERVER SETUP COMPLETE!")
            print("=" * 60)
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.close()

    async def _setup_server(self, guild: discord.Guild):
        """Execute the full server setup."""
        # Step 1: Lock @everyone
        print("\n[1/6] Locking down @everyone...")
        await self._setup_everyone(guild)

        # Step 2: Create roles
        print("\n[2/6] Creating roles...")
        await self._create_roles(guild)

        # Step 3: Order role hierarchy
        print("\n[3/6] Ordering role hierarchy...")
        await self._order_roles(guild)

        # Step 4: Create categories + channels
        print("\n[4/6] Creating categories and channels...")
        await self._create_channels(guild)

        # Step 5: Post welcome content
        print("\n[5/6] Posting welcome content...")
        await self._post_content(guild)

        # Step 6: Print summary
        print("\n[6/6] Verifying setup...")
        await self._verify(guild)

    async def _setup_everyone(self, guild: discord.Guild):
        """Lock @everyone — deny view/send by default."""
        everyone = guild.default_role
        await everyone.edit(permissions=discord.Permissions(
            read_message_history=True,
            add_reactions=True,
        ))
        print("  ✅ @everyone locked (view/send denied)")

    async def _create_roles(self, guild: discord.Guild):
        """Create all roles (or update existing)."""
        existing = {r.name: r for r in guild.roles}
        for cfg in ROLES_CONFIG:
            name = cfg["name"]
            if name in existing:
                role = existing[name]
                await role.edit(
                    color=discord.Color(cfg["color"]),
                    hoist=cfg["hoist"],
                    permissions=cfg["permissions"],
                )
                self.created_roles[name] = role
                print(f"  ✏️  Updated: {name}")
            else:
                role = await guild.create_role(
                    name=name,
                    color=discord.Color(cfg["color"]),
                    hoist=cfg["hoist"],
                    permissions=cfg["permissions"],
                )
                self.created_roles[name] = role
                print(f"  ✅ Created: {name}")
            await asyncio.sleep(0.5)

    async def _order_roles(self, guild: discord.Guild):
        """Position roles in correct hierarchy."""
        desired_order = [r["name"] for r in ROLES_CONFIG]
        positions = {}
        pos = 1
        for name in reversed(desired_order):
            role = self.created_roles.get(name)
            if role:
                positions[role] = pos
                pos += 1
        # Place bot's integration role above all custom roles
        bot_role = guild.self_role
        if bot_role:
            positions[bot_role] = pos
        try:
            await guild.edit_role_positions(positions=positions)
            print("  ✅ Role hierarchy set")
        except discord.HTTPException as e:
            print(f"  ⚠️  Partial hierarchy set: {e}")
            print("     → Manual fix: drag bot role above '🌱 Level 0' in Server Settings")


    async def _create_channels(self, guild: discord.Guild):
        """Create all categories and channels with permissions."""
        guild = self.get_guild(self.target_guild_id)
        for cat_cfg in CATEGORIES_CONFIG:
            overwrites = self._resolve_overwrites(guild, cat_cfg["overwrites"])
            existing_cat = discord.utils.get(guild.categories, name=cat_cfg["name"])
            if existing_cat:
                await existing_cat.edit(overwrites=overwrites)
                category = existing_cat
                print(f"\n  ✏️  Category: {cat_cfg['name']}")
            else:
                category = await guild.create_category(name=cat_cfg["name"], overwrites=overwrites)
                print(f"\n  ✅ Category: {cat_cfg['name']}")
            await asyncio.sleep(0.4)

            for ch_cfg in cat_cfg["channels"]:
                ch_name = ch_cfg["name"]
                is_voice = ch_cfg["type"] == "voice"
                existing_ch = discord.utils.get(
                    category.voice_channels if is_voice else category.text_channels,
                    name=ch_name,
                )
                # Build channel-specific overwrites if any
                ch_overwrites = None
                if ch_cfg.get("override"):
                    ch_overwrites = dict(overwrites)
                    ch_overwrites.update(self._resolve_overwrites(guild, ch_cfg["override"]))

                if existing_ch:
                    if ch_overwrites:
                        await existing_ch.edit(overwrites=ch_overwrites)
                    print(f"    ✏️  #{ch_name}")
                else:
                    if is_voice:
                        await category.create_voice_channel(
                            name=ch_name,
                            overwrites=ch_overwrites if ch_overwrites else None,
                        )
                    else:
                        await category.create_text_channel(
                            name=ch_name,
                            topic=ch_cfg.get("topic", ""),
                            overwrites=ch_overwrites if ch_overwrites else None,
                        )
                    print(f"    ✅ #{ch_name}")
                await asyncio.sleep(0.3)

    def _resolve_overwrites(self, guild: discord.Guild, cfg: dict) -> dict:
        """Convert string role names to actual role/overwrite pairs."""
        result = {}
        for key, overwrite in cfg.items():
            if key == "@everyone":
                target = guild.default_role
            elif key == "bot":
                target = guild.self_role
            else:
                target = self.created_roles.get(key) or discord.utils.get(guild.roles, name=key)
            if target:
                result[target] = overwrite
        return result

    async def _post_content(self, guild: discord.Guild):
        """Post welcome, rules, and roles content."""
        guild = self.get_guild(self.target_guild_id)
        content_map = {
            "welcome": WELCOME_MESSAGE,
            "rules": RULES_MESSAGE,
            "roles-info": ROLES_INFO_MESSAGE,
        }
        for ch_name, content in content_map.items():
            channel = discord.utils.get(guild.text_channels, name=ch_name)
            if channel:
                # Check if content already posted (avoid duplicates)
                async for msg in channel.history(limit=5):
                    if msg.author == self.user and len(msg.content) > 100:
                        print(f"  ⏭️  #{ch_name} already has content — skipped")
                        break
                else:
                    await channel.send(content)
                    print(f"  ✅ Posted content in #{ch_name}")
            await asyncio.sleep(0.5)


    async def _verify(self, guild: discord.Guild):
        """Print verification summary with channel IDs."""
        guild = self.get_guild(self.target_guild_id)
        print(f"\n  📊 Server State:")
        print(f"     Roles: {len(guild.roles)}")
        print(f"     Categories: {len(guild.categories)}")
        print(f"     Text channels: {len(guild.text_channels)}")
        print(f"     Voice channels: {len(guild.voice_channels)}")

        print(f"\n  🔑 Role Hierarchy:")
        for role in reversed(guild.roles):
            if role.name == "@everyone":
                continue
            marker = "🤖" if role == guild.self_role else "  "
            print(f"     {marker} {role.name} (pos {role.position})")

        # Print key channel IDs for n8n webhook configuration
        print(f"\n  📌 KEY CHANNEL IDs (for n8n/webhook config):")
        key_channels = [
            "l0-daily-tasks", "l1-daily-tasks", "l2-daily-tasks", "l3-daily-tasks",
            "cheat-sheets", "leaderboard", "streak-tracker", "daily-word",
            "announcements", "bot-logs", "speaking-feedback", "writing-feedback",
        ]
        for name in key_channels:
            ch = discord.utils.get(guild.text_channels, name=name)
            if ch:
                print(f"     #{name}: {ch.id}")

        # Check bot can assign level roles
        bot_role = guild.self_role
        level_roles = ["🌱 Level 0 | مبتدئ", "💪 Level 1 | متقدم", "🚀 Level 2 | متواصل", "👑 Level 3 | طليق"]
        can_assign = all(
            bot_role.position > self.created_roles[n].position
            for n in level_roles if n in self.created_roles
        )
        if can_assign:
            print("\n  ✅ Bot CAN assign all level roles (hierarchy correct)")
        else:
            print("\n  ⚠️  Bot CANNOT assign level roles — fix hierarchy manually")

        print(f"\n  🔗 Server Invite: create one in Server Settings → Invites")


# ============================================================
#  ENTRY POINT
# ============================================================

def main():
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN not set. Add it to .env or set at top of this file.")
        return
    if not GUILD_ID:
        print("❌ GUILD_ID not set. Right-click server → Copy Server ID.")
        print("   (Enable Developer Mode: User Settings → Advanced → Developer Mode)")
        return

    print("🚀 Empire English Community — Server Setup Script")
    print("=" * 60)
    print(f"   Guild ID: {GUILD_ID}")
    print(f"   Token: {DISCORD_TOKEN[:20]}...")
    print("=" * 60)
    print("\n⚠️  This will MODIFY your server roles, channels, and permissions.")
    print("   Press Ctrl+C within 5 seconds to cancel...\n")

    try:
        import time
        for i in range(5, 0, -1):
            print(f"   Starting in {i}...", end="\r")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled.")
        return

    print("\n\n🔧 Starting setup...\n")
    client = ServerSetup(GUILD_ID)
    client.run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
