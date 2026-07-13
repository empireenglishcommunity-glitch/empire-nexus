#!/usr/bin/env python3
"""Generate Arabic welcome audio clips via Kokoro TTS.

Bawaba Phase B3: pre-generated Arabic voice clips explaining how the
system works. Sent as Discord DM attachments in the welcome sequence.

Requires Kokoro TTS running on the server (localhost:8880).
Run: cd /opt/kokoro-tts && docker compose start
Then: python3 scripts/onboarding/generate_welcome_audio.py

Output: scripts/onboarding/audio/ (4 MP3 files)

NOTE: Kokoro-82M's Arabic voice quality must be tested. If it sounds
robotic, replace these with manually-recorded audio files (same
filenames, same directory). The bot code doesn't care how they were
generated — it just sends whatever files exist in the audio/ directory.
"""
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

KOKORO_URL = os.environ.get("KOKORO_URL", "http://localhost:8880/v1/audio/speech")
OUTPUT_DIR = Path(__file__).resolve().parent / "audio"
OUTPUT_DIR.mkdir(exist_ok=True)

# Arabic scripts for 4 welcome clips — Egyptian colloquial register
# (matching the bot's existing Arabic message style)
CLIPS = [
    {
        "filename": "01_welcome.mp3",
        "text": (
            "أهلاً بيك في إمباير إنجليش! "
            "ده نظام تعلّم يومي هيخليك تتكلم إنجليزي بلهجة أمريكية. "
            "مش كورس عادي، ده نظام كل يوم بيديك مهام بسيطة تعملها. "
            "خلينا نبدأ!"
        ),
        "speed": 0.85,
    },
    {
        "filename": "02_how_to_register.mp3",
        "text": (
            "عشان تسجل نفسك، اكتب علامة التعجب وبعدها كلمة انضم. "
            "يعني اكتب: انضم. "
            "أو لو مش عايز تكتب، اعمل ريأكت بعلامة الصح على أي رسالة. "
            "البوت هيسجلك أوتوماتيك."
        ),
        "speed": 0.85,
    },
    {
        "filename": "03_daily_tasks.mp3",
        "text": (
            "كل يوم الساعة ستة الصبح، هتلاقي سبع مهام مرقمة في القناة. "
            "المهام بسيطة: تدريب نطق، مفردات، محاكاة، كلام، استماع، كتابة، ومشاركة. "
            "كل مهمة بتاخد عشر دقايق بس. "
            "لما تخلص مهمة، تكتب رقمها. يعني لو خلصت المهمة الأولى، اكتب واحد."
        ),
        "speed": 0.80,
    },
    {
        "filename": "04_mark_done.mp3",
        "text": (
            "لما تخلص مهمة، اكتب رقمها في قناة بوت كوماندز. "
            "مثلاً: واحد للنطق، اتنين للمفردات، تلاتة للمحاكاة. "
            "البوت هيتأكد إنك فعلاً عملت المهمة وهيديك خمستاشر نقطة. "
            "لو خلصت السبع مهام، هتاخد مية نقطة بونص! "
            "بالتوفيق!"
        ),
        "speed": 0.80,
    },
]


def generate_clip(text: str, filename: str, speed: float = 0.85):
    """Call Kokoro TTS API and save the result."""
    output_path = OUTPUT_DIR / filename

    payload = {
        "model": "kokoro",
        "input": text,
        "voice": "af_heart",  # best available female voice
        "speed": speed,
        "response_format": "mp3",
    }

    print(f"  Generating: {filename} ({len(text)} chars, speed={speed})...")
    try:
        resp = requests.post(KOKORO_URL, json=payload, timeout=60)
        if resp.status_code == 200:
            output_path.write_bytes(resp.content)
            size_kb = len(resp.content) / 1024
            print(f"    ✅ {filename} ({size_kb:.1f} KB)")
            return True
        else:
            print(f"    ❌ HTTP {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return False


def main():
    print("Generating Arabic welcome audio clips via Kokoro TTS...")
    print(f"  Kokoro URL: {KOKORO_URL}")
    print(f"  Output dir: {OUTPUT_DIR}")
    print()

    success = 0
    for clip in CLIPS:
        if generate_clip(clip["text"], clip["filename"], clip["speed"]):
            success += 1

    print(f"\nDone: {success}/{len(CLIPS)} clips generated.")
    if success < len(CLIPS):
        print("⚠️  Some clips failed. Check if Kokoro TTS is running:")
        print("    cd /opt/kokoro-tts && docker compose start")
        sys.exit(1)
    else:
        print("✅ All clips ready. They'll be sent in the welcome DM.")
        sys.exit(0)


if __name__ == "__main__":
    main()
