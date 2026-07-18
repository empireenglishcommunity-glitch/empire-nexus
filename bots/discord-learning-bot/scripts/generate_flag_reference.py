#!/usr/bin/env python3
"""
Aql (العقل) Phase A2.4 — generator for
data/nour_knowledge_owner/flag_registry_reference.md.

This file is GENERATED FROM src/flag_registry.py's REGISTRY, never
hand-maintained -- re-run this script whenever a flag is added,
removed, or its description/default changes, so the owner-only
knowledge domain never drifts out of sync with the actual running
flag list (the same "code is the source of truth, docs follow" rule
already applied to database_schema.md's own closing note).

Usage:
    python3 scripts/generate_flag_reference.py
    python3 scripts/generate_flag_reference.py --check   # exit 1 if the
                                                          # existing file
                                                          # is stale
                                                          # (CI-friendly,
                                                          # makes no writes)

After running (without --check), re-run the embed script for just this
one domain to re-index it:
    python3 scripts/embed_knowledge.py flag_registry_reference.md
    # (--dry-run first if you want to sanity-check chunk count before
    #  spending any embedding API quota)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import flag_registry  # noqa: E402

OUTPUT_PATH = (Path(__file__).resolve().parent.parent
               / "data" / "nour_knowledge_owner" / "flag_registry_reference.md")

HEADER = """# مرجع أعلام الميزات (Feature Flag Reference)

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

"""


def _initiative_heading(initiative_key: str) -> str:
    info = flag_registry.INITIATIVES.get(initiative_key)
    if info:
        emoji, name, description = info
        return f"## {emoji} {name} — {description}"
    return f"## {initiative_key}"


def generate_markdown() -> str:
    groups = flag_registry.get_flags_by_initiative()
    # Preserve REGISTRY's own grouping order (first-seen initiative
    # order), not an alphabetical re-sort -- matches
    # get_flags_by_initiative()'s own dict-insertion-order behavior in
    # Python 3.7+, but made explicit here rather than relied upon
    # implicitly.
    seen_order = []
    for _, _, initiative, _ in flag_registry.REGISTRY:
        if initiative not in seen_order:
            seen_order.append(initiative)

    parts = [HEADER]
    for initiative in seen_order:
        flags = groups[initiative]
        parts.append(_initiative_heading(initiative))
        parts.append("")
        parts.append("| العلم (Flag) | الوصف | الحالة الافتراضية |")
        parts.append("|---|---|---|")
        for name, description, default in flags:
            default_ar = "مفعَّل" if default else "معطَّل"
            parts.append(f"| `{name}` | {description} | {default_ar} |")
        parts.append("")

    parts.append("## إجمالي الأعلام")
    parts.append("")
    parts.append(f"العدد الكلي للأعلام المُسجَّلة حاليًّا: **{len(flag_registry.REGISTRY)}**")
    parts.append("")

    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="Exit 1 if the existing file is stale, without writing.")
    args = parser.parse_args()

    new_content = generate_markdown()

    if args.check:
        if not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text(encoding="utf-8") != new_content:
            print(f"STALE: {OUTPUT_PATH} does not match src/flag_registry.py. "
                  f"Run without --check to regenerate.", file=sys.stderr)
            return 1
        print(f"OK: {OUTPUT_PATH} is up to date.")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(new_content, encoding="utf-8")
    print(f"Generated {OUTPUT_PATH} ({len(flag_registry.REGISTRY)} flags, "
          f"{len(flag_registry.get_flags_by_initiative())} initiatives).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
