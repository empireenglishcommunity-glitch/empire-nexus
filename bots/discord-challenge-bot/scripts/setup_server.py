#!/usr/bin/env python3
"""
Empire Challenge Bot — Discord Server Setup Script
===================================================

This script AUTOMATICALLY configures your Discord server:
  - Creates all roles with correct colors and hierarchy
  - Sets @everyone permissions (locked down)
  - Creates categories and channels
  - Applies category-level permissions
  - Applies channel-specific overrides
  - Positions the bot role correctly in hierarchy

Usage:
    1. Fill in your DISCORD_TOKEN and GUILD_ID below
    2. Run: python scripts/setup_server.py
    3. Done — server is fully configured

WARNING: This will MODIFY your server roles, channels, and permissions.
         Run on a fresh/test server first if unsure.

Requirements: discord.py >= 2.3 (already in requirements.txt)
"""
import asyncio
import discord

# ============================================================
#  CONFIGURATION — Fill these in before running
# ============================================================
DISCORD_TOKEN = ""  # Your bot token (same as in .env)
GUILD_ID = 0        # Your server ID (right-click server name → Copy Server ID)

# ============================================================
#  ROLE DEFINITIONS
# ============================================================
# Format: (name, color_hex, display_separately, permissions_dict)
# permissions_dict: only non-default permissions; empty = cosmetic role

ROLES_CONFIG = [
    # --- Administrative roles ---
    {
        "name": "Admin / المؤسس",
        "color": 0xD4AF37,
        "hoist": True,  # Display separately
        "permissions": discord.Permissions(administrator=True),
    },
    {
        "name": "Moderator",
        "color": 0xE74C3C,
        "hoist": True,
        "permissions": discord.Permissions(
            view_channel=True,
            send_messages=True,
            manage_messages=True,
            kick_members=True,
            mute_members=True,
            move_members=True,
            mention_everyone=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            connect=True,
            speak=True,
        ),
    },
    # --- Special roles ---
    {
        "name": "Mentor",
        "color": 0x9B59B6,
        "hoist": True,
        "permissions": discord.Permissions(
            view_channel=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            connect=True,
            speak=True,
            priority_speaker=True,
        ),
    },
    # --- Rank roles (cosmetic — bot assigns these) ---
    {
        "name": "بطل المرونة",
        "color": 0xD4AF37,
        "hoist": True,
        "permissions": discord.Permissions.none(),
    },
    {
        "name": "محارب",
        "color": 0xFFD700,
        "hoist": True,
        "permissions": discord.Permissions.none(),
    },
    {
        "name": "مثابر",
        "color": 0xC0C0C0,
        "hoist": False,
        "permissions": discord.Permissions.none(),
    },
    {
        "name": "بدأ الرحلة",
        "color": 0xCD7F32,
        "hoist": False,
        "permissions": discord.Permissions.none(),
    },
    {
        "name": "بطل الأسبوع",
        "color": 0xC0C0C0,
        "hoist": True,
        "permissions": discord.Permissions.none(),
    },
    {
        "name": "محارب نشط",
        "color": 0xE67E22,
        "hoist": False,
        "permissions": discord.Permissions.none(),
    },
    # --- Access roles (these grant actual permissions) ---
    {
        "name": "مشارك",
        "color": 0x2ECC71,
        "hoist": False,
        "permissions": discord.Permissions(
            view_channel=True,
            send_messages=True,
            send_messages_in_threads=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            connect=True,
            speak=True,
            use_voice_activation=True,
        ),
    },
    {
        "name": "زائر",
        "color": 0x95A5A6,
        "hoist": False,
        "permissions": discord.Permissions(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            add_reactions=True,
        ),
    },
]

# ============================================================
#  CATEGORY & CHANNEL DEFINITIONS
# ============================================================
# Each category has:
#   - name: category display name
#   - overwrites: permission overwrites applied at category level
#   - channels: list of channels (name, type, override or None)
#
# Channel types: "text" or "voice"
# Channel override: additional per-channel overrides (on top of category)

CATEGORIES_CONFIG = [
    {
        "name": "📢 الترحيب والقواعد",
        "overwrites": {
            "@everyone": discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,
                add_reactions=True,
                read_message_history=True,
            ),
            "bot": discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                mention_everyone=True,
            ),
            "Moderator": discord.PermissionOverwrite(
                send_messages=True,
            ),
        },
        "channels": [
            {
                "name": "اقرأ-أولًا",
                "type": "text",
                "topic": "شرح التحدي + القواعد + السلامة",
                "override": None,
            },
            {
                "name": "القوانين",
                "type": "text",
                "topic": "قوانين السيرفر والاحترام",
                "override": None,
            },
            {
                "name": "تعريف-بنفسك",
                "type": "text",
                "topic": "عرّف عن نفسك وهدفك من التحدي",
                "override": {
                    # Everyone CAN write in this channel (introduction)
                    "@everyone": discord.PermissionOverwrite(
                        send_messages=True,
                    ),
                },
            },
            {
                "name": "الإعلانات",
                "type": "text",
                "topic": "إعلانات رسمية فقط",
                "override": None,
            },
        ],
    },
    {
        "name": "🎯 التحدي",
        "overwrites": {
            "@everyone": discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False,
            ),
            "زائر": discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,
                read_message_history=True,
                add_reactions=True,
            ),
            "مشارك": discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
                add_reactions=True,
            ),
            "bot": discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                mention_everyone=True,
                add_reactions=True,
            ),
            "Moderator": discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_messages=True,
            ),
        },
        "channels": [
            {
                "name": "تحدي-اليوم",
                "type": "text",
                "topic": "يُنشر هنا تحدي كل يوم تلقائيًا — لا تكتب هنا",
                "override": {
                    # ONLY bot and mods can post here
                    "مشارك": discord.PermissionOverwrite(
                        send_messages=False,
                        add_reactions=True,
                    ),
                    "زائر": discord.PermissionOverwrite(
                        send_messages=False,
                        add_reactions=True,
                    ),
                },
            },
            {
                "name": "سجل-التقدم",
                "type": "text",
                "topic": "سجّل إنجازك هنا: !done <اليوم> <شعورك>",
                "override": None,
            },
            {
                "name": "أثبت-إنجازك",
                "type": "text",
                "topic": "صور وفيديوهات إثبات التحدي",
                "override": None,
            },
            {
                "name": "أسئلة-ومساعدة",
                "type": "text",
                "topic": "استفسارات حول التحديات",
                "override": None,
            },
        ],
    },
    {
        "name": "💬 المجتمع",
        "overwrites": {
            "@everyone": discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False,
            ),
            "زائر": discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                add_reactions=True,
                embed_links=False,
                attach_files=False,
            ),
            "مشارك": discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
                add_reactions=True,
            ),
            "bot": discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
            ),
            "Moderator": discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_messages=True,
            ),
        },
        "channels": [
            {
                "name": "دردشة-عامة",
                "type": "text",
                "topic": "نقاش حر",
                "override": None,
            },
            {
                "name": "تحفيز-ودعم",
                "type": "text",
                "topic": "تشجيع متبادل عند الإحباط",
                "override": None,
            },
            {
                "name": "قصص-النجاح",
                "type": "text",
                "topic": "شارك تحوّلاتك وإنجازاتك",
                "override": None,
            },
            {
                "name": "ركن-الإنجليزية",
                "type": "text",
                "topic": "English only zone - practice here!",
                "override": None,
            },
            {
                "name": "اقتراحات",
                "type": "text",
                "topic": "أفكار لتطوير التحدي والمجتمع",
                "override": None,
            },
        ],
    },
    {
        "name": "🔊 صوتي",
        "overwrites": {
            "@everyone": discord.PermissionOverwrite(
                view_channel=False,
                connect=False,
                speak=False,
            ),
            "زائر": discord.PermissionOverwrite(
                view_channel=True,
                connect=False,
            ),
            "مشارك": discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                use_voice_activation=True,
            ),
            "Mentor": discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                priority_speaker=True,
            ),
            "bot": discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
            ),
            "Moderator": discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                move_members=True,
                mute_members=True,
            ),
        },
        "channels": [
            {
                "name": "لايف المراجعة",
                "type": "voice",
                "override": None,
            },
            {
                "name": "غرفة التأمل",
                "type": "voice",
                "override": None,
            },
            {
                "name": "غرفة الإنجليزية",
                "type": "voice",
                "override": None,
            },
            {
                "name": "غرفة الاسترخاء",
                "type": "voice",
                "override": None,
            },
        ],
    },
]


# ============================================================
#  MAIN SETUP LOGIC
# ============================================================

class ServerSetup(discord.Client):
    def __init__(self, guild_id: int):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        super().__init__(intents=intents)
        self.target_guild_id = guild_id
        self.created_roles = {}  # name -> Role object

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")
        guild = self.get_guild(self.target_guild_id)
        if not guild:
            print(f"❌ Guild ID {self.target_guild_id} not found. Check GUILD_ID.")
            await self.close()
            return

        print(f"🎯 Target server: {guild.name} ({guild.member_count} members)")
        print("=" * 60)

        try:
            await self.setup_server(guild)
            print("\n" + "=" * 60)
            print("🎉 SERVER SETUP COMPLETE!")
            print("=" * 60)
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.close()

    async def setup_server(self, guild: discord.Guild):
        """Execute the full server setup in order."""

        # Step 1: Lock down @everyone
        print("\n[1/5] Locking down @everyone...")
        await self.setup_everyone(guild)

        # Step 2: Create roles
        print("\n[2/5] Creating roles...")
        await self.create_roles(guild)

        # Step 3: Position roles in hierarchy
        print("\n[3/5] Ordering role hierarchy...")
        await self.order_roles(guild)

        # Step 4: Delete default channels (optional — only if empty)
        print("\n[4/5] Creating categories and channels...")
        await self.create_channels(guild)

        # Step 5: Summary
        print("\n[5/5] Verifying setup...")
        await self.verify(guild)

    async def setup_everyone(self, guild: discord.Guild):
        """Set @everyone to deny almost everything."""
        everyone_role = guild.default_role
        locked_perms = discord.Permissions(
            read_message_history=True,
            add_reactions=True,
        )
        # This sets ONLY these as allowed, everything else denied
        await everyone_role.edit(permissions=locked_perms)
        print("  ✅ @everyone locked down (view/send denied, reactions allowed)")

    async def create_roles(self, guild: discord.Guild):
        """Create all roles if they don't exist."""
        existing_roles = {r.name: r for r in guild.roles}

        for role_cfg in ROLES_CONFIG:
            name = role_cfg["name"]
            if name in existing_roles:
                # Update existing role
                role = existing_roles[name]
                await role.edit(
                    color=discord.Color(role_cfg["color"]),
                    hoist=role_cfg["hoist"],
                    permissions=role_cfg["permissions"],
                    mentionable=False,
                )
                self.created_roles[name] = role
                print(f"  ✏️  Updated existing role: {name}")
            else:
                # Create new role
                role = await guild.create_role(
                    name=name,
                    color=discord.Color(role_cfg["color"]),
                    hoist=role_cfg["hoist"],
                    permissions=role_cfg["permissions"],
                    mentionable=False,
                )
                self.created_roles[name] = role
                print(f"  ✅ Created role: {name}")

            await asyncio.sleep(0.5)  # Rate limit protection

    async def order_roles(self, guild: discord.Guild):
        """Position roles in the correct hierarchy order."""
        # Refresh guild data
        guild = self.get_guild(self.target_guild_id)

        # Desired order (top to bottom — higher position = more authority)
        desired_order = [
            "Admin / المؤسس",
            # Bot role is handled separately (it's auto-created by Discord)
            "Moderator",
            "Mentor",
            "بطل المرونة",
            "محارب",
            "مثابر",
            "بدأ الرحلة",
            "بطل الأسبوع",
            "محارب نشط",
            "مشارك",
            "زائر",
        ]

        # Build position map (higher number = higher in list)
        # Start from position 1 (0 is @everyone)
        positions = {}
        pos = 1
        for name in reversed(desired_order):
            role = self.created_roles.get(name)
            if role:
                positions[role] = pos
                pos += 1

        # Also position the bot's own role above rank roles
        bot_role = guild.self_role
        if bot_role:
            # Place bot role just below Admin
            positions[bot_role] = pos
            pos += 1

        try:
            await guild.edit_role_positions(positions=positions)
            print("  ✅ Role hierarchy set correctly")
            print("     (Bot role positioned above all rank roles)")
        except discord.HTTPException as e:
            print(f"  ⚠️  Could not fully reorder roles: {e}")
            print("     (This is OK if the bot role can't move above its own position)")
            print("     → MANUAL FIX: Drag the bot role above 'بطل المرونة' in Server Settings → Roles")

    async def create_channels(self, guild: discord.Guild):
        """Create categories and channels with correct permissions."""
        guild = self.get_guild(self.target_guild_id)

        for cat_cfg in CATEGORIES_CONFIG:
            # Build category overwrites
            cat_overwrites = self._build_overwrites(guild, cat_cfg["overwrites"])

            # Check if category already exists
            existing_cat = discord.utils.get(guild.categories, name=cat_cfg["name"])
            if existing_cat:
                # Update permissions on existing category
                await existing_cat.edit(overwrites=cat_overwrites)
                category = existing_cat
                print(f"\n  ✏️  Updated category: {cat_cfg['name']}")
            else:
                # Create new category
                category = await guild.create_category(
                    name=cat_cfg["name"],
                    overwrites=cat_overwrites,
                )
                print(f"\n  ✅ Created category: {cat_cfg['name']}")

            await asyncio.sleep(0.5)

            # Create channels inside this category
            for ch_cfg in cat_cfg["channels"]:
                ch_name = ch_cfg["name"]

                # Check if channel already exists in this category
                if ch_cfg["type"] == "text":
                    existing_ch = discord.utils.get(
                        category.text_channels, name=ch_name
                    )
                else:
                    existing_ch = discord.utils.get(
                        category.voice_channels, name=ch_name
                    )

                # Build channel-specific overrides (if any)
                ch_overwrites = None
                if ch_cfg.get("override"):
                    # Start with category overwrites and add channel overrides
                    ch_overwrites = self._build_overwrites(guild, ch_cfg["override"])

                if existing_ch:
                    # Update existing channel
                    if ch_overwrites:
                        # Merge: keep category overwrites + add channel overrides
                        merged = dict(category.overwrites)
                        merged.update(ch_overwrites)
                        await existing_ch.edit(overwrites=merged)
                    print(f"    ✏️  Updated: #{ch_name}")
                else:
                    # Create new channel
                    if ch_cfg["type"] == "text":
                        if ch_overwrites:
                            # Merge category + channel overwrites
                            merged = dict(cat_overwrites)
                            merged.update(ch_overwrites)
                            await category.create_text_channel(
                                name=ch_name,
                                topic=ch_cfg.get("topic", ""),
                                overwrites=merged,
                            )
                        else:
                            # No override — just create in category (inherits)
                            await category.create_text_channel(
                                name=ch_name,
                                topic=ch_cfg.get("topic", ""),
                            )
                    else:
                        if ch_overwrites:
                            await category.create_voice_channel(
                                name=ch_name,
                                overwrites=ch_overwrites,
                            )
                        else:
                            await category.create_voice_channel(
                                name=ch_name,
                            )
                    print(f"    ✅ Created: #{ch_name}")

                await asyncio.sleep(0.3)

    def _build_overwrites(
        self, guild: discord.Guild, overwrite_cfg: dict
    ) -> dict:
        """Convert config overwrite dict to Discord overwrite objects."""
        result = {}
        for role_key, perms in overwrite_cfg.items():
            if role_key == "@everyone":
                target = guild.default_role
            elif role_key == "bot":
                target = guild.self_role
            else:
                target = self.created_roles.get(role_key)
                if not target:
                    # Try to find by name in guild roles
                    target = discord.utils.get(guild.roles, name=role_key)
            if target:
                result[target] = perms
        return result

    async def verify(self, guild: discord.Guild):
        """Print final verification summary."""
        guild = self.get_guild(self.target_guild_id)

        print(f"\n  📊 Final Server State:")
        print(f"     Roles: {len(guild.roles)}")
        print(f"     Categories: {len(guild.categories)}")
        print(f"     Text channels: {len(guild.text_channels)}")
        print(f"     Voice channels: {len(guild.voice_channels)}")
        print(f"\n  🔑 Role Hierarchy (top to bottom):")
        for role in reversed(guild.roles):
            if role.name == "@everyone":
                continue
            indicator = "🤖" if role == guild.self_role else "  "
            print(f"     {indicator} {role.name} (pos {role.position})")

        # Check bot can assign rank roles
        bot_role = guild.self_role
        rank_names = ["بطل المرونة", "محارب", "مثابر", "بدأ الرحلة"]
        can_assign = all(
            bot_role.position > (self.created_roles.get(n) or guild.default_role).position
            for n in rank_names
            if n in self.created_roles
        )
        if can_assign:
            print("\n  ✅ Bot CAN assign all rank roles (hierarchy correct)")
        else:
            print("\n  ⚠️  Bot CANNOT assign some rank roles!")
            print("     → Fix: Drag the bot role above 'بطل المرونة' in Server Settings → Roles")

        # Print the challenge channel ID
        challenge_ch = discord.utils.get(guild.text_channels, name="تحدي-اليوم")
        if challenge_ch:
            print(f"\n  📌 #تحدي-اليوم Channel ID: {challenge_ch.id}")
            print(f"     (Use this as CHALLENGE_CHANNEL_ID in .env)")


def main():
    if not DISCORD_TOKEN:
        print("❌ ERROR: Set DISCORD_TOKEN at the top of this file.")
        print("   Use the same token from your .env file.")
        return

    if not GUILD_ID:
        print("❌ ERROR: Set GUILD_ID at the top of this file.")
        print("   Right-click your server name → Copy Server ID")
        print("   (Enable Developer Mode first: User Settings → Advanced → Developer Mode)")
        return

    print("🚀 Empire Challenge Bot — Server Setup Script")
    print("=" * 60)
    print(f"   Guild ID: {GUILD_ID}")
    print(f"   Token: {DISCORD_TOKEN[:20]}...")
    print("=" * 60)
    print("\n⚠️  This will modify your server roles, channels, and permissions.")
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
