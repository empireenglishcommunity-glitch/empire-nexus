"""Feature Flag Registry — the ONE place to see all flags.

Every feature flag in the system is registered here with its name,
description, initiative (grouping), and default state. This file is
the source of truth for "what flags exist" — new code adds its flag
here in the same PR that creates it.

Used by:
- !flag list (shows descriptions and groupings)
- !flag info <name> (shows detailed info)
- Any future dashboard or admin tool

Add new flags to the REGISTRY list below. Keep them grouped by
initiative and in the order they were created.
"""

# Each entry: (name, description, initiative, default_enabled)
# initiative is used for grouping in !flag list output.

REGISTRY = [
    # ── AEGIS (production safety) ──
    ("systemstatus", "Public system health command (!systemstatus)", "aegis", True),

    # ── BAWABA (zero-English onboarding) ──
    ("bawaba_aliases", "Arabic commands + number tasks (!تم, !1-!7)", "bawaba", True),
    ("bawaba_reactions", "Emoji-react registration (✅) + task completion (1️⃣-7️⃣)", "bawaba", True),
    ("bawaba_tutorial", "Interactive 5-step Arabic tutorial quest on join", "bawaba", True),
    ("bawaba_multimedia", "Text journey guide + audio clips in welcome DM", "bawaba", True),
    ("bawaba_buddy_prompt", "Rich buddy DM with voice message suggestion", "bawaba", True),
    ("bawaba_gradual_english", "Bot response language evolves by week (Arabic → bilingual)", "bawaba", True),
    ("bawaba_start_channel", "#start-here mention in welcome DM", "bawaba", True),

    # ── NABD (student notifications) ──
    ("nabd_preferences", "Notification settings command (!notifications / !إشعارات)", "nabd", True),
    ("nabd_morning", "Morning kickstart DM (6:05 AM daily)", "nabd", True),
    ("nabd_evening", "Evening incomplete reminder (8 PM)", "nabd", True),
    ("nabd_streak_alert", "Streak-at-risk alert (9 PM)", "nabd", True),
    ("nabd_celebrations", "Real-time milestone celebrations", "nabd", True),
    ("nabd_weekly_summary", "Friday evening progress summary DM", "nabd", True),
    ("nabd_absence_recovery", "Absence recovery ladder (day 2/3/5/7)", "nabd", True),
    ("nabd_social_proof", "Opt-in peer activity notifications", "nabd", True),
]

# Initiative display names and emoji
INITIATIVES = {
    "aegis": ("⚙️", "AEGIS", "production safety"),
    "bawaba": ("🌍", "BAWABA", "zero-English onboarding"),
    "nabd": ("🔔", "NABD", "student notifications"),
}


def get_registry() -> list[tuple]:
    """Get the full flag registry."""
    return REGISTRY


def get_flag_info(name: str):
    """Get info for a specific flag, or None if not registered."""
    for flag_name, description, initiative, default in REGISTRY:
        if flag_name == name:
            return {
                "name": flag_name,
                "description": description,
                "initiative": initiative,
                "default_enabled": default,
            }
    return None


def get_flags_by_initiative() -> dict[str, list[tuple]]:
    """Group flags by initiative for display."""
    groups: dict[str, list[tuple]] = {}
    for flag_name, description, initiative, default in REGISTRY:
        if initiative not in groups:
            groups[initiative] = []
        groups[initiative].append((flag_name, description, default))
    return groups
