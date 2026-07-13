#!/usr/bin/env python3
"""Generate the visual journey map infographic (Arabic, PNG).

Bawaba Phase B3: a visual infographic showing the student's path
through the system — arrows, steps, clean design. Sent as a Discord
DM attachment in the welcome sequence.

Requires empire-html2img service running on the server (localhost:3200).
Run: python3 scripts/onboarding/generate_journey_map.py

Output: scripts/onboarding/images/journey_map.png
"""
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

HTML2IMG_URL = os.environ.get("HTML2IMG_URL", "http://localhost:3200/convert")
OUTPUT_DIR = Path(__file__).resolve().parent / "images"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "journey_map.png"

# The infographic HTML — Arabic, RTL, clean dark design matching Empire branding
JOURNEY_MAP_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Segoe UI', Tahoma, sans-serif;
    background: #1a1a2e;
    color: #eee;
    padding: 40px;
    width: 800px;
}
.header {
    text-align: center;
    margin-bottom: 30px;
}
.header h1 {
    color: #d4af37;
    font-size: 28px;
    margin-bottom: 8px;
}
.header p {
    color: #aaa;
    font-size: 16px;
}
.steps {
    display: flex;
    flex-direction: column;
    gap: 20px;
}
.step {
    display: flex;
    align-items: center;
    gap: 20px;
    background: #16213e;
    border-radius: 12px;
    padding: 20px;
    border-right: 4px solid #d4af37;
}
.step-number {
    background: #d4af37;
    color: #1a1a2e;
    width: 50px;
    height: 50px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    font-weight: bold;
    flex-shrink: 0;
}
.step-content h3 {
    color: #d4af37;
    font-size: 18px;
    margin-bottom: 6px;
}
.step-content p {
    color: #ccc;
    font-size: 14px;
    line-height: 1.5;
}
.step-content code {
    background: #0f3460;
    padding: 2px 8px;
    border-radius: 4px;
    color: #4ecdc4;
    font-size: 14px;
}
.arrow {
    text-align: center;
    color: #d4af37;
    font-size: 24px;
}
.footer {
    text-align: center;
    margin-top: 30px;
    color: #888;
    font-size: 13px;
}
</style>
</head>
<body>
<div class="header">
    <h1>🏛️ رحلتك في Empire English</h1>
    <p>5 خطوات بس وتبدأ تتعلم إنجليزي كل يوم</p>
</div>
<div class="steps">
    <div class="step">
        <div class="step-number">1</div>
        <div class="step-content">
            <h3>سجّل نفسك</h3>
            <p>اكتب <code>!انضم</code> أو اعمل ✅ على أي رسالة</p>
        </div>
    </div>
    <div class="arrow">⬇️</div>
    <div class="step">
        <div class="step-number">2</div>
        <div class="step-content">
            <h3>كل يوم الساعة 6 الصبح</h3>
            <p>هتلاقي 7 مهام مرقمة في قناة المهام اليومية</p>
        </div>
    </div>
    <div class="arrow">⬇️</div>
    <div class="step">
        <div class="step-number">3</div>
        <div class="step-content">
            <h3>اعمل المهمة</h3>
            <p>كل مهمة 10 دقايق: نطق، مفردات، استماع، كتابة...</p>
        </div>
    </div>
    <div class="arrow">⬇️</div>
    <div class="step">
        <div class="step-number">4</div>
        <div class="step-content">
            <h3>سجّل إنك خلصت</h3>
            <p>اكتب رقم المهمة: <code>!1</code> أو <code>!2</code> ... إلخ</p>
        </div>
    </div>
    <div class="arrow">⬇️</div>
    <div class="step">
        <div class="step-number">5</div>
        <div class="step-content">
            <h3>شوف تقدمك يكبر! 🔥</h3>
            <p>اكتب <code>!تقدم</code> — نقاطك وستريكك هيزيدوا كل يوم</p>
        </div>
    </div>
</div>
<div class="footer">
    Empire English Community — System over instructor. Common Sense First. 🏛️
</div>
</body>
</html>"""


def generate_map():
    """Call html2img service and save the PNG."""
    print("Generating journey map infographic...")
    print(f"  html2img URL: {HTML2IMG_URL}")
    print(f"  Output: {OUTPUT_PATH}")

    payload = {
        "html": JOURNEY_MAP_HTML,
        "width": 800,
        "height": 900,
    }

    try:
        resp = requests.post(HTML2IMG_URL, json=payload, timeout=30)
        if resp.status_code == 200:
            OUTPUT_PATH.write_bytes(resp.content)
            size_kb = len(resp.content) / 1024
            print(f"  ✅ journey_map.png ({size_kb:.1f} KB)")
            return True
        else:
            print(f"  ❌ HTTP {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    if generate_map():
        print("\n✅ Journey map ready. It'll be sent in the welcome DM.")
        sys.exit(0)
    else:
        print("\n⚠️  Generation failed. Check if html2img is running:")
        print("    docker ps | grep html2img")
        sys.exit(1)


if __name__ == "__main__":
    main()
