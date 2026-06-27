"""Generate a PDF completion certificate for a participant. 100% free (reportlab).

Arabic text needs reshaping + bidi handling so letters connect and read RTL.
Uses the bundled Cairo font (Google Fonts, OFL license) for proper Arabic rendering.
"""
import os
from datetime import date
from . import config


# ── Font registration (done once at import time) ────────────────────────────
_FONT_REGISTERED = False


def _register_font():
    """Register the bundled Cairo Arabic font with reportlab (idempotent)."""
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_dir = os.path.join(config.BASE_DIR, "fonts")
    font_path = os.path.join(font_dir, "Cairo-Variable.ttf")

    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont("Cairo", font_path))
        pdfmetrics.registerFont(TTFont("Cairo-Bold", font_path))  # Variable font handles weight
        _FONT_REGISTERED = True
    else:
        # Fallback: if font file is missing, we'll use Helvetica (won't connect Arabic)
        pass


def _font(bold: bool = False) -> str:
    """Return the best available font name."""
    _register_font()
    if _FONT_REGISTERED:
        return "Cairo-Bold" if bold else "Cairo"
    return "Helvetica-Bold" if bold else "Helvetica"


def _shape(text: str) -> str:
    """Reshape Arabic so it renders correctly in the PDF (connected letters, RTL)."""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def make_certificate(username: str, completed: int, rank_name: str) -> str:
    """Create a certificate PDF and return its file path."""
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    safe = "".join(ch for ch in username if ch.isalnum() or ch in (" ", "_", "-")).strip()
    path = os.path.join(config.OUTPUT_DIR, f"certificate_{safe or 'participant'}.pdf")

    width, height = landscape(A4)
    c = canvas.Canvas(path, pagesize=landscape(A4))

    # Background + gold border
    c.setFillColor(colors.HexColor("#0f1419"))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#d4af37"))
    c.setLineWidth(4)
    c.rect(15 * mm, 15 * mm, width - 30 * mm, height - 30 * mm, fill=0, stroke=1)
    c.setLineWidth(1)
    c.rect(18 * mm, 18 * mm, width - 36 * mm, height - 36 * mm, fill=0, stroke=1)

    cx = width / 2

    # Title
    c.setFillColor(colors.HexColor("#d4af37"))
    c.setFont(_font(bold=True), 30)
    c.drawCentredString(cx, height - 50 * mm, _shape("شهادة إتمام التحدّي"))

    # Subtitle
    c.setFillColor(colors.white)
    c.setFont(_font(), 16)
    c.drawCentredString(cx, height - 68 * mm, _shape("تشهد Empire English Community بأن"))

    # Participant name
    c.setFillColor(colors.HexColor("#ffd700"))
    c.setFont(_font(bold=True), 26)
    c.drawCentredString(cx, height - 88 * mm, _shape(username))

    # Achievement
    c.setFillColor(colors.white)
    c.setFont(_font(), 15)
    c.drawCentredString(
        cx, height - 104 * mm,
        _shape(f"قد أتمّ {completed} من 30 تحدّيًا في برنامج (كن مرتاحًا مع عدم الراحة)"),
    )

    # Rank
    c.setFillColor(colors.HexColor("#d4af37"))
    c.setFont(_font(bold=True), 20)
    c.drawCentredString(cx, height - 124 * mm, _shape(f"الرتبة: {rank_name}"))

    # Date footer
    c.setFillColor(colors.HexColor("#888888"))
    c.setFont(_font(), 12)
    c.drawCentredString(cx, 30 * mm, _shape(f"التاريخ: {date.today().isoformat()}"))

    c.showPage()
    c.save()
    return path
