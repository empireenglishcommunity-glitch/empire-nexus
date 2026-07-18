# مرجع أعلام الميزات (Feature Flag Reference)

> هذا الملف جزء من قاعدة معرفة نور — مخصَّص للمالك فقط. لا يُعرض هذا
> المحتوى للطلاب أبدًا (Aql Phase A2، domain: `flag_registry_reference`).
>
> **تحذير: هذا الملف مُولَّد تلقائيًّا من `src/flag_registry.py`.**
> لا تُعدِّله يدويًّا — أي تعديل يدوي يُفقَد عند إعادة توليد الملف. لتحديث
> المحتوى، غيِّر `REGISTRY` في `src/flag_registry.py` ثم أعد تشغيل
> `python3 scripts/generate_flag_reference.py`.

## نظرة عامة

كل علم (flag) في هذا النظام مُسجَّل في مكان واحد: `src/flag_registry.py`.
هذا يضمن أن أمر `!flag list` (Discord) وأمر `/flag` (Telegram) يعرضان
دائمًا القائمة الكاملة والدقيقة، وأن أي علم جديد يُضاف يظهر تلقائيًّا
بعد إعادة التشغيل التالية دون تفعيل يدوي.

الحالة الافتراضية (enabled=True/False) هي الحالة التي يبدأ بها العلم
عند أول تشغيل لقاعدة بيانات جديدة أو عند إضافته لأول مرة — لا تعكس
بالضرورة حالته الحالية على الخادم المباشر (التي قد يُعدِّلها المالك
يدويًّا عبر `!flag enable/disable` في أي وقت).


## ⚙️ AEGIS — production safety

| العلم (Flag) | الوصف | الحالة الافتراضية |
|---|---|---|
| `systemstatus` | Public system health command (!systemstatus) | مفعَّل |

## 🌍 BAWABA — zero-English onboarding

| العلم (Flag) | الوصف | الحالة الافتراضية |
|---|---|---|
| `bawaba_aliases` | Arabic commands + number tasks (!تم, !1-!7) | مفعَّل |
| `bawaba_reactions` | Emoji-react registration (✅) + task completion (1️⃣-7️⃣) | مفعَّل |
| `bawaba_tutorial` | Interactive 5-step Arabic tutorial quest on join | مفعَّل |
| `bawaba_multimedia` | Text journey guide + audio clips in welcome DM | مفعَّل |
| `bawaba_buddy_prompt` | Rich buddy DM with voice message suggestion | مفعَّل |
| `bawaba_gradual_english` | Bot response language evolves by week (Arabic → bilingual) | مفعَّل |
| `bawaba_start_channel` | #start-here mention in welcome DM | مفعَّل |

## 🔔 NABD — student notifications

| العلم (Flag) | الوصف | الحالة الافتراضية |
|---|---|---|
| `nabd_preferences` | Notification settings command (!notifications / !إشعارات) | مفعَّل |
| `nabd_morning` | Morning kickstart DM (6:05 AM daily) | مفعَّل |
| `nabd_evening` | Evening incomplete reminder (8 PM) | مفعَّل |
| `nabd_streak_alert` | Streak-at-risk alert (9 PM) | مفعَّل |
| `nabd_celebrations` | Real-time milestone celebrations | مفعَّل |
| `nabd_weekly_summary` | Friday evening progress summary DM | مفعَّل |
| `nabd_absence_recovery` | Absence recovery ladder (day 2/3/5/7) | مفعَّل |
| `nabd_social_proof` | Opt-in peer activity notifications | مفعَّل |

## 🚀 TATAWWUR — system evolution

| العلم (Flag) | الوصف | الحالة الافتراضية |
|---|---|---|
| `tatawwur_portfolio` | Voice progress portfolio (!portfolio / !صوتي) | مفعَّل |
| `tatawwur_patterns` | Daily conversational patterns in tasks | مفعَّل |
| `tatawwur_srs` | Spaced repetition for vocabulary recall | مفعَّل |
| `tatawwur_milestones` | Ability milestones (!abilities / !قدراتي) | مفعَّل |
| `tatawwur_pronunciation` | AI pronunciation scoring (Groq Whisper) | معطَّل |
| `tatawwur_conversations` | Structured conversation sessions | مفعَّل |
| `tatawwur_showcase` | Auto-post success stories to showcase channels | مفعَّل |
| `tatawwur_adaptive` | Adaptive difficulty pacing | معطَّل |

## 💬 NOUR — autonomous student concierge

| العلم (Flag) | الوصف | الحالة الافتراضية |
|---|---|---|
| `aql_episodic_summaries` | Aql (#15) Phase A6: weekly per-student episodic summary generation (Groq) | معطَّل |
| `nour_concierge` | AI concierge handles DMs and #ask-nour questions | مفعَّل |
| `nour_proactive` | Proactive outreach (anti-churn check-ins) | معطَّل |
| `nour_escalation` | Telegram alerts for escalated issues | معطَّل |
| `nour_msa` | Rawiya R0: Nour speaks Modern Standard Arabic (فصحى) instead of Egyptian colloquial | مفعَّل |
| `nour_journey` | Rawiya R2: structured 7-day onboarding journey for new students | مفعَّل |
| `nour_enhanced_proactive` | Rawiya R3: expanded proactive triggers (9 conditions) | مفعَّل |
| `nour_tutorials` | Rawiya R4: pre-written MSA micro-tutorials for confused students | مفعَّل |
| `nour_owner_commands` | Rawiya R5: /check and /nudge commands via Telegram | مفعَّل |
| `nour_graduated` | Rawiya R6: graduated presence (decreasing contact for experienced students) | مفعَّل |
| `nour_aql_core` | Aql (#15): role-scoped RAG + tool-calling cognitive core, replaces single-shot nour_concierge pipeline when ON | معطَّل |

## 📡 MARKAZ — Telegram operations hub

| العلم (Flag) | الوصف | الحالة الافتراضية |
|---|---|---|
| `markaz_daily_digest` | Morning Telegram digest via Empire Ops bot (7 AM Dubai) | مفعَّل |
| `markaz_weekly_report` | Sunday weekly business report via Empire Ops bot (9 AM Dubai) | مفعَّل |
| `markaz_monthly_summary` | Monthly engagement/revenue summary (1st of month) | مفعَّل |
| `markaz_churn_alerts` | Churn risk alerts for silent high-value students | مفعَّل |
| `markaz_conversion_alerts` | Conversion-ready alerts when students hit 7-day streak | مفعَّل |

## 🔗 WUSLAH — ecosystem harmony

| العلم (Flag) | الوصف | الحالة الافتراضية |
|---|---|---|
| `wuslah_dashboard_api` | Enable expanded /api/dashboard + /api/leaderboard endpoints | مفعَّل |
| `wuslah_exercise_confirm` | Enable web-to-Discord task confirmation via API | مفعَّل |
| `wuslah_nour_tips` | Enable AI-generated weekly study tips (W4) | مفعَّل |
| `wuslah_adaptive` | Enable adaptive practice recommendations on the web (W3) | مفعَّل |

## 🧭 MASAR — personal growth narrative

| العلم (Flag) | الوصف | الحالة الافتراضية |
|---|---|---|
| `masar_momentum_score` | Momentum Score on dashboard + !progress (replaces XP bar, fixes D012) | معطَّل |
| `masar_growth_letter` | Nour's Weekly Growth Letter (task + API + dashboard card, fixes D020) | معطَّل |
| `masar_milestone_moments` | Personalized milestone unlock DMs | معطَّل |
| `masar_difficulty_notes` | Adaptive difficulty change transparency DMs | معطَّل |

## 🦅 SAHIN — Discord channel experience

| العلم (Flag) | الوصف | الحالة الافتراضية |
|---|---|---|
| `vocab_cheat_sheet` | Weekly Vocabulary Cheat Sheet in #cheat-sheets (Sahin Phase 4) | معطَّل |

## 🏰 HISSAR — security / anti-cheat / copyright

| العلم (Flag) | الوصف | الحالة الافتراضية |
|---|---|---|
| `hissar_role_gate` | Role-gate system: new members must accept rules before seeing channels (replaces removed Discord Rules Screening) | مفعَّل |
| `hissar_anti_cheat` | P4: increased cooldown (180s), persistent cooldown across restarts, progressive quiz delay | مفعَّل |
| `hissar_ip_detection` | P5: log IPs per token, auto-flag on 5+ unique IPs, Telegram alert to owner | مفعَّل |

## إجمالي الأعلام

العدد الكلي للأعلام المُسجَّلة حاليًّا: **52**
