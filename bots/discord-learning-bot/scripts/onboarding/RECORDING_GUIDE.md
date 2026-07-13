# Voice Recording Guide — Bawaba B3

> Record these 4 clips on your phone (Voice Memos app or similar).
> Each clip should be 20-30 seconds. Egyptian Arabic, informal register.
> Save as MP3 (or m4a — we can convert). Upload to this directory as
> the filenames below.

## How to record:
1. Open Voice Memos (iPhone) or Recorder (Android)
2. Read the script naturally — like you're talking to a friend
3. Save and transfer to the server:
   ```bash
   scp 01_welcome.mp3 root@77.42.43.250:/opt/empire-english-bot/scripts/onboarding/audio/
   ```

---

## Clip 1: `01_welcome.mp3` (20 seconds)

```
أهلاً بيك في إمباير إنجليش!
ده نظام تعلّم يومي هيخليك تتكلم إنجليزي بلهجة أمريكية صح.
مش كورس عادي — ده نظام كل يوم بيديك مهام بسيطة تعملها.
خلينا نبدأ!
```

---

## Clip 2: `02_how_to_register.mp3` (20 seconds)

```
عشان تسجل نفسك، روح قناة بوت كوماندز واكتب: انضم.
أو لو مش عايز تكتب، اعمل ريأكت بعلامة الصح على أي رسالة.
البوت هيسجلك أوتوماتيك ويبعتلك رسالة تأكيد.
```

---

## Clip 3: `03_daily_tasks.mp3` (25 seconds)

```
كل يوم الساعة ستة الصبح، هتلاقي سبع مهام مرقمة في القناة.
المهام بسيطة: تدريب نطق، مفردات، محاكاة، كلام، استماع، كتابة، ومشاركة.
كل مهمة بتاخد عشر دقايق بس.
مش لازم تعمل السبعة — حتى مهمة واحدة أحسن من لا شيء.
```

---

## Clip 4: `04_mark_done.mp3` (25 seconds)

```
لما تخلص مهمة، اكتب رقمها.
يعني لو خلصت المهمة الأولى اكتب: واحد.
المهمة التانية: اتنين. التالتة: تلاتة. وهكذا.
البوت هيتأكد إنك فعلاً عملت المهمة وهيديك خمستاشر نقطة.
لو خلصت السبع مهام كلهم، هتاخد مية نقطة بونص!
```

---

## After recording:

1. Upload all 4 files to the server:
   ```bash
   scp *.mp3 root@77.42.43.250:/opt/empire-english-bot/scripts/onboarding/audio/
   ```
   (This overwrites the old Kokoro-generated files)

2. Test: type `!testwelcome` in Discord — you should hear YOUR voice

3. That's it! The bot sends these automatically to every new member.

## Tips:
- Talk naturally, like explaining to a friend
- Don't worry about being perfect — authenticity > polish
- Background should be quiet (no TV, no traffic)
- Phone at 20-30cm from your mouth
