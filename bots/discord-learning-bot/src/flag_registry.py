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
    # bawaba_start_channel removed 2026-09-03 — the #start-here channel was
    # deleted and its only consumer (the welcome-DM mention) removed with it.

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
    ("tatawwur_pronunciation", "Pronunciation 'Grade my best read' (Azure + free fallback)", "tatawwur", False),
    ("tatawwur_showcase", "Auto-post success stories to showcase channels", "tatawwur", True),
    ("tatawwur_adaptive", "Adaptive difficulty pacing", "tatawwur", False),

    # ── NOUR retired (2026-09-03) ──
    # The Nour subsystem (AI concierge, Aql cognitive core, rule-based
    # onboarding journey, MSA voice) has been fully retired. Its flags
    # (nour_msa, nour_journey) and the "nour" initiative were removed.
    # Onboarding is now team-run via /onboard. Any leftover nour_* rows in
    # the DB are inert. NOTE: the dormant Weekly Growth Letter path lives
    # under the "masar"/"wuslah" initiatives, not here.

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
    ("manual_onboarding", "Team-run onboarding: students do NOT self-onboard. The self-serve rules gate (✅-react and !agree) and the automated Nour journey are disabled; a team member fully sets up each student with !onboard @student <level>, which grants the gateway role (unlocks channels) + the CEFR level role in one step. Channel security (gateway role + overwrites) is UNCHANGED — only the self-grant paths are off.", "hissar", True),
    ("hissar_anti_cheat", "P4: increased cooldown (180s), persistent cooldown across restarts, progressive quiz delay", "hissar", True),
    ("hissar_ip_detection", "P5: log IPs per token, auto-flag on 5+ unique IPs, Telegram alert to owner", "hissar", True),
    ("hissar_bot_integrity", "Bot-profile tamper detection: alerts the owner if the Ops/Discord bot name, description or bio drifts from its baseline or contains spam (added after the 2026-08-29 Ops-token compromise)", "hissar", False),

    # ── HAFIZ (motivational engagement) ──
    ("hafiz_motivation", "Phase F (E4): AI-generated, always-varied motivational replies in #lN-text-practice + #lN-showcase, correction-free, throttled", "hafiz", False),

    # ── ITQAN (weekly mastery assessment) ──
    ("itqan_weekly_assessment", "Weekly Assessment (Itqan): calendar-gated, timed weekly mastery test on the practice page (5 skills, spiral, two-dimension pass, public Champions celebration / private support)", "itqan", False),
    ("itqan_progression_gate", "Itqan R16: mastery-based progression — the next week's content stays locked until the current week's assessment is passed (grandfathers existing students; safety valves keep nobody stuck)", "itqan", False),

    # ── MAJLIS (community lounge) ──
    ("community_together_credit", "Majlis R1: company-aware task #7 — voice half satisfied by 5 min together-time in a Majlis lounge (OR the existing 10 min any-voice path; nobody worse off)", "majlis", False),
    ("community_lounge_beacon", "Majlis R2: smart, self-cleaning presence beacon in #community-live when a Majlis lounge is in the lonely/lively band", "majlis", False),
    ("community_dynamic_rooms", "Majlis R4: join-to-create overflow pods — auto-spawn capped Majlis lounges and auto-reap when empty", "majlis", False),
    ("community_pings_optin", "Majlis R5: opt-in community-pings role + Knock button — only opted-in members get @-mentioned by beacons", "majlis", False),
    ("community_power_hour", "Majlis R6: scheduled Community Hour (9-10 PM Egypt) with rally in #community-live + one Telegram broadcast", "majlis", False),
    ("community_together_reward", "Majlis R8: optional bonus points/acknowledgement when task #7 is completed via the together path", "majlis", False),

    # ── TAQDEEM (assessment progression) ──
    ("assessment_monthly_review", "Taqdeem: Monthly Progress Review — retention-focused assessment after every 4 weekly passes (diagnostic + prerequisite for advancement)", "taqdeem", False),
    ("assessment_advancement_exam", "Taqdeem: Level Advancement Exam — two-part gate (structured skills + integrated production task) for level promotion", "taqdeem", True),

    # ── ASSESSMENT WATCHDOG (find breakage before a student does) ──
    ("assessment_watchdog", "Every 3h, probe the assessment endpoints and look for stranded attempts, finished monthly reviews with no recorded result, and orphan item rows — alerting Empire Ops on a change of state. Added after three assessment defects in a row were found from student complaints rather than monitoring, including /api/assessment/item answering HTTP 500 to every request for ~24h. Read-only: it reports, never repairs. Also exposes !assessment-health", "assessment", False),

    # ── SUSPENSION (membership lifecycle) ──
    ("suspension_lifecycle", "Monthly membership lifecycle: !announce-renewal (notice to students), !suspend (withdraw access — clock + status + Darb sessions + link tokens + the Student gateway role, which is what hides the channels), !restore (give it back and bridge the no-access days so a 40-day streak survives), and the 60-day retention cycle (owner warned at day 53, then JSON archive → permanent purge → VACUUM). Suspension deletes NOTHING; only the purge deletes, and it refuses to run if the archive cannot be written", "suspension", False),

    # ── IJTIHAD (effort economy) ──
    ("ijtihad_award_table", "Ijtihad Phase 7: the new award table — REPLACES POINTS_PER_TASK (15), POINTS_ALL_TASKS (100) and the STREAK_BONUS_POINTS tenure ladder. Base 10/task x difficulty (1.0-1.5) x quality (1.0-1.3, never below 1.0 so trying is never punished), + 25 for meeting YOUR target, + bounded seasonal streak bonuses at 7/14/21/28 days. Fixes the incentive where attempting Challenging content paid the same as Easy. Hard either/or with the legacy table — they can never both fire", "ijtihad", False),
    ("ijtihad_growth_recognition", "Ijtihad Phase 6: growth + grit — !growth, !improved, !spotlight, and five recognitions (Personal Best, Persistence, Comeback, Uphill, Refinement). Growth is measured against the student's OWN 14-day baseline so a beginner can lead; recognitions award NO points, so determination is celebrated without moving anyone above a stronger student on the effort board", "ijtihad", False),
    ("ijtihad_boards", "Ijtihad Phase 5: the board set — !season (effort, resets), !peers (journey-stage cohort with min-3 degradation), !consistency (full-day streaks); !top redirects to the season board; and the nightly #streak-tracker becomes a ROLL of who completed their target instead of a 15-name ranking of >=1-task streaks. Every board caps at top 3-5 and lists only students who earned something, so no surface publishes a bottom half", "ijtihad", False),
    ("ijtihad_personal_target", "Ijtihad Phase 4: Personal Daily Target (3/5/7, one change per season) + Full-Day streaks + streak freezes. A student who can genuinely only manage 3 gets full 'complete day' credit for 3/3 instead of being permanently short of a bar built for someone with more free time; absolute volume still scales so 7/7 earns more", "ijtihad", False),
    ("ijtihad_achievement_awards", "Ijtihad Phase 3: achievement payouts — mastery 150 / distinction 250 / monthly review 300 / promotion 500. Before this, all four awarded ZERO while pure attendance paid 105-205/day, so the economy could not express 'this student improved'. Deduped: each achievement pays once, ever", "ijtihad", False),
    ("ijtihad_seasons", "Ijtihad Phase 2: effort seasons — fixed community-wide 4-week windows. Season effort is DERIVED from points_log date windows (no migration, no new points column), so rank stops being a lifetime integral that rewards seniority over current work", "ijtihad", False),
    ("ijtihad_sijil", "Ijtihad Phase 1: Sijil — the permanent Record of Honour (!sijil, !honour). Read-only view of durable achievements (weeks mastered, distinctions, levels passed, perfect days, best streak, legacy XP) so seasonal effort resets never erase what a student built", "ijtihad", False),

    # ── MI'YAR (CEFR curriculum) ──
    # RETIRED 2026-08-28: `cefr_curriculum` was the rollout gate for Mi'yar, the
    # CEFR restructure. That rollout is complete — all six levels (A1–C2) are
    # authored, live and student-facing — so the gate has no job left.
    #
    # It is removed rather than left in place because it was ON in the live DB and
    # read by NO code, which is the worst state for a flag: it looks like a
    # control, so a future maintainer could disable it expecting CEFR to switch
    # off, and nothing would happen. Dead config that appears live is a trap.
    #
    # Removing it from this list only stops it appearing in `!flag list`;
    # `sync_feature_flags` inserts missing flags and never prunes, so the existing
    # DB row is left exactly as it is. It is inert either way — nothing calls
    # `is_feature_enabled("cefr_curriculum")`. To tidy the row itself (optional,
    # never required):
    #     DELETE FROM feature_flags WHERE name='cefr_curriculum';

    # ── SAWT (podcast studio) ──
    ("sawt_episodes", "Sawt Phase 1: podcast episode management — /create-episode + /publish-episode post level-graded episodes to the per-level #<slug>-podcast channel (level-isolated). OFF until content is ready", "sawt", False),
    ("sawt_listen_credit", "Sawt Phase 1: award a small, capped acknowledgement when a student marks a podcast episode listened (✅ / !listened). Additive; never breaks existing points/streak rules", "sawt", False),
    ("sawt_script_gen", "Sawt Phase 2: LLM-assisted podcast script generation — /generate-script turns a topic + level + format into a level-graded conversation script for the owner to review before recording. Nothing publishes automatically", "sawt", False),
    ("sawt_tts_pipeline", "Sawt Phase 3: in-bot audio assembly — /generate-audio parses a reviewed script into per-speaker segments and renders them via the configured TTS engine. On the 512MB bot host no engine is available, so it explains to render offline (GitHub Actions); the same path produces audio where an engine IS available", "sawt", False),
    ("sawt_voice_clone", "Sawt Phase 3: use the owner's CLONED voice for their lines (Chatterbox). Requires explicit stored consent (!sawt-consent) + a reference clip; refuses without both. Owner voice only — never clones anyone else", "sawt", False),
]

# Initiative display names and emoji
INITIATIVES = {
    "aegis": ("⚙️", "AEGIS", "production safety"),
    "bawaba": ("🌍", "BAWABA", "zero-English onboarding"),
    "nabd": ("🔔", "NABD", "student notifications"),
    "tatawwur": ("🚀", "TATAWWUR", "system evolution"),
    "sahin": ("🦅", "SAHIN", "Discord channel experience"),
    "markaz": ("📡", "MARKAZ", "Telegram operations hub"),
    "wuslah": ("🔗", "WUSLAH", "ecosystem harmony"),
    "masar": ("🧭", "MASAR", "personal growth narrative"),
    "hissar": ("🏰", "HISSAR", "security / anti-cheat / copyright"),
    "hafiz": ("🎉", "HAFIZ", "motivational engagement"),
    "itqan": ("🎓", "ITQAN", "weekly mastery assessment"),
    "majlis": ("🏛️", "MAJLIS", "community lounge"),
    "taqdeem": ("🎓", "TAQDEEM", "assessment progression"),
    "miyar": ("📚", "MI'YAR", "CEFR curriculum"),
    "sawt": ("🎙️", "SAWT", "podcast studio"),
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
