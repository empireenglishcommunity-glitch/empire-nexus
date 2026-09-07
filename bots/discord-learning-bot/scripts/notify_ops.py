#!/usr/bin/env python3.12
"""Empire Chronicles — owner alert from the daily pipeline (R9.4).

Sends a short Telegram message to the owner via the Empire Ops bot, using the
SAME credentials the bot uses (OPS_BOT_TOKEN / OPS_CHAT_ID from the environment).
Self-contained so it can run inside GitHub Actions where the Discord bot is not
running — the daily workflow calls it to "fail loudly" when the gate fails or
nothing is emitted, and (optionally) to confirm a successful emit.

Best-effort: never exits non-zero, never raises. A missing token/chat id or a
network error just prints a note and returns 0 — an alert that can't be sent must
not itself break or fail the pipeline.

Usage:
    python3.12 scripts/notify_ops.py --text "…"
    echo "…" | python3.12 scripts/notify_ops.py
"""
import argparse
import os
import sys
import urllib.request
import urllib.parse


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text", default="", help="message text (else read stdin)")
    args = ap.parse_args()

    text = args.text or (sys.stdin.read() if not sys.stdin.isatty() else "")
    text = (text or "").strip()
    if not text:
        print("notify_ops: empty message; nothing to send")
        return 0

    token = os.getenv("OPS_BOT_TOKEN", "").strip()
    chat_id = os.getenv("OPS_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("notify_ops: OPS_BOT_TOKEN/OPS_CHAT_ID not set; skipping alert")
        return 0

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=15) as resp:
            ok = resp.status == 200
        print("notify_ops: sent" if ok else f"notify_ops: HTTP {resp.status}")
    except Exception as e:                                       # noqa: BLE001
        print(f"notify_ops: send failed ({type(e).__name__}: {e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
