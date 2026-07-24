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

    # ── TATAWWUR (system evolution) ──
    ("tatawwur_patterns", "Daily conversational patterns in tasks", "tatawwur", True),
    ("tatawwur_srs", "Spaced repetition for vocabulary recall", "tatawwur", True),
    ("tatawwur_pronunciation", "AI pronunciation scoring (Groq Whisper)", "tatawwur", False),
    ("tatawwur_showcase", "Auto-post success stories to showcase channels", "tatawwur", True),
    ("tatawwur_adaptive", "Adaptive difficulty pacing", "tatawwur", False),

    # ── NOUR (onboarding journey + personality) ──
    # The AI concierge and Aql cognitive core were removed; only the
    # rule-based onboarding journey and MSA voice remain active.
    ("nour_msa", "Rawiya R0: Nour speaks Modern Standard Arabic (فصحى) instead of Egyptian colloquial", "nour", True),
    ("nour_journey", "Rawiya R2: structured 7-day onboarding journey for new students", "nour", True),

    # ── MARKAZ (Telegram operations hub) ──
    ("markaz_daily_digest", "Morning Telegram digest via Empire Ops bot (7 AM Dubai)", "markaz", True),
    ("markaz_weekly_report", "Sunday weekly business report via Empire Ops bot (9 AM Dubai)", "markaz", True),
    ("markaz_monthly_summary", "Monthly engagement/revenue summary (1st of month)", "markaz", True),
    ("markaz_churn_alerts", "Churn risk alerts for silent high-value students", "markaz", True),
    ("markaz_conversion_alerts", "Conversion-ready alerts when students hit 7-day streak", "markaz", True),

    # ── WUSLAH (ecosystem harmony) ──
    ("wuslah_dashboard_api", "Enable expanded /api/dashboard + /api/leaderboard endpoints", "wuslah", True),
    ("wuslah_exercise_confirm", "Enable web-to-Discord task confirmation via API", "wuslah", True),
    ("wuslah_nour_tips", "Enable AI-generated weekly study tips (W4)", "wuslah", True),
    ("wuslah_adaptive", "Enable adaptive practice recommendations on the web (W3)", "wuslah", True),

    # ── MASAR (personal growth narrative) ──
    ("masar_momentum_score", "Momentum Score on dashboard + !progress (replaces XP bar, fixes D012)", "masar", False),
    ("masar_growth_letter", "Nour's Weekly Growth Letter (task + API + dashboard card, fixes D020)", "masar", False),
    ("masar_milestone_moments", "Personalized milestone unlock DMs", "masar", False),
    ("masar_difficulty_notes", "Adaptive difficulty change transparency DMs", "masar", False),
    ("vocab_cheat_sheet", "Weekly Vocabulary Cheat Sheet in #cheat-sheets (Sahin Phase 4)", "sahin", False),

    # ── HISSAR (security / anti-cheat / copyright) ──
    ("hissar_role_gate", "Role-gate system: new members must accept rules before seeing channels (replaces removed Discord Rules Screening)", "hissar", True),
    ("hissar_anti_cheat", "P4: increased cooldown (180s), persistent cooldown across restarts, progressive quiz delay", "hissar", True),
    ("hissar_ip_detection", "P5: log IPs per token, auto-flag on 5+ unique IPs, Telegram alert to owner", "hissar", True),

    # ── HAFIZ (motivational engagement) ──
    ("hafiz_motivation", "Phase F (E4): AI-generated, always-varied motivational replies in #lN-text-practice + #lN-showcase, correction-free, throttled", "hafiz", False),
]

# Initiative display names and emoji
INITIATIVES = {
    "aegis": ("⚙️", "AEGIS", "production safety"),
    "bawaba": ("🌍", "BAWABA", "zero-English onboarding"),
    "nabd": ("🔔", "NABD", "student notifications"),
    "tatawwur": ("🚀", "TATAWWUR", "system evolution"),
    "nour": ("💬", "NOUR", "autonomous student concierge"),
    "sahin": ("🦅", "SAHIN", "Discord channel experience"),
    "markaz": ("📡", "MARKAZ", "Telegram operations hub"),
    "wuslah": ("🔗", "WUSLAH", "ecosystem harmony"),
    "masar": ("🧭", "MASAR", "personal growth narrative"),
    "hissar": ("🏰", "HISSAR", "security / anti-cheat / copyright"),
    "hafiz": ("🎉", "HAFIZ", "motivational engagement"),
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
