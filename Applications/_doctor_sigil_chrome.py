"""
_doctor_sigil_chrome.py — shared graphics chrome for SIFTA flagship apps.

Final-graphics-approval lane: CG55M Dr Cursor / Claude Opus 4.7
Authors a small, reusable Doctor Sigil Bar plus a shared palette so every
flagship app in apps_manifest.json wears the same triple-IDE provenance
chrome. Code-lane work by C55M, AG31, and CG55M is preserved untouched —
this module only paints on top.

Usage (canvas-paint):
    from Applications._doctor_sigil_chrome import (
        paint_doctor_sigil_bar, DOCTOR_PALETTE, app_chrome_font,
    )
    p.fillRect(0, 0, W, H, C_BG)
    paint_doctor_sigil_bar(
        p, doctors=["AG31","C46S","C55M","CG55M"],
        title="ARTIFFICIAL GENERAL INTELLIGENCE",
        x=0, y=0, w=W, h=42,
    )

Usage (QLabel banner):
    from Applications._doctor_sigil_chrome import doctor_sigil_html
    label.setText(doctor_sigil_html(["C55M","CG55M"], "Physarum Contradiction Lab"))

The convention is canonical per Documents/IDE_DOCTOR_SIGNATURE_PROTOCOL.md.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
)


# ── Palette ────────────────────────────────────────────────────────────────
# Each Doctor Code maps to a primary color used everywhere the Doctor
# appears (sigil bar, leader-board, federation receipt). These are stable
# and intended to be the canonical visual identity per Doctor.
DOCTOR_PALETTE: dict[str, QColor] = {
    "CG55M": QColor(168, 107, 255),   # Cursor / Opus 4.7 — slime-mold purple
    "C55M":  QColor( 91, 255, 147),   # Codex / GPT-5.5    — green
    "AG31":  QColor(255, 200,  87),   # Antigravity        — gold
    "C46S":  QColor( 91, 217, 255),   # Cursor Sonnet 4.6  — cyan
    "C47H":  QColor( 91, 184, 255),   # Cursor Sonnet 4.7  — sky cyan
}

# Generic accent palette for the four flagship apps.
C_BG_DEEP        = QColor(  8,   7,  26)
C_BG_BAR         = QColor( 13,  13,  31)
C_BAR_HAIRLINE   = QColor(120, 100, 200,  90)
C_BAR_DIVIDER    = QColor(255, 255, 255,  20)
C_TEXT_PRIMARY   = QColor(245, 245, 255)
C_TEXT_SECONDARY = QColor(170, 175, 215)
C_MINT_HIGHLIGHT = QColor(255, 100, 170)


def doctor_color(code: str) -> QColor:
    """Return the canonical color for a doctor code, or a neutral fallback."""
    return DOCTOR_PALETTE.get(code, QColor(180, 180, 200))


# ── Fonts ──────────────────────────────────────────────────────────────────
def app_chrome_font(size: int = 11, *, bold: bool = False, mono: bool = True) -> QFont:
    """A consistent monospace HUD font for SIFTA flagship apps."""
    fam = "JetBrains Mono" if mono else "Inter"
    f = QFont(fam, size)
    if bold:
        f.setWeight(QFont.Weight.DemiBold)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return f


# ── Canvas painter API ─────────────────────────────────────────────────────
def paint_doctor_sigil_bar(
    painter: QPainter,
    doctors: list[str],
    *,
    x: int = 0,
    y: int = 0,
    w: int = 1200,
    h: int = 42,
    title: str | None = None,
    subtitle: str | None = None,
    show_protocol_chip: bool = True,
) -> None:
    """Paints the canonical Doctor Sigil Bar across `w` pixels at (x, y).

    Layout, left-to-right:
       [ DOCTOR_PILL · DOCTOR_PILL · ... ]    title           subtitle  ⓘ
    """
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    # ── Background gradient -------------------------------------------------
    grad = QLinearGradient(x, y, x + w, y)
    grad.setColorAt(0.0, QColor(13, 13, 31, 235))
    if doctors:
        c = doctor_color(doctors[0])
        tinted = QColor(c.red() // 6, c.green() // 6, c.blue() // 6, 230)
        grad.setColorAt(1.0, tinted)
    else:
        grad.setColorAt(1.0, QColor(13, 13, 31, 230))
    painter.fillRect(QRectF(x, y, w, h), QBrush(grad))

    # 1px top + bottom hairline so the bar reads as a UI surface, not paint
    painter.setPen(QPen(C_BAR_HAIRLINE, 1.0))
    painter.drawLine(x, y, x + w, y)
    painter.drawLine(x, y + h - 1, x + w, y + h - 1)

    # ── Doctor pills (left side) -------------------------------------------
    pad_x = 12
    pill_h = h - 14
    pill_y = y + (h - pill_h) // 2
    cursor_x = x + pad_x

    pill_font = app_chrome_font(11, bold=True)
    fm = QFontMetrics(pill_font)
    painter.setFont(pill_font)

    for i, code in enumerate(doctors):
        color = doctor_color(code)
        text_w = fm.horizontalAdvance(code)
        pill_w = text_w + 18

        # filled pill (slightly translucent)
        bg = QColor(color)
        bg.setAlpha(40)
        painter.setBrush(QBrush(bg))
        painter.setPen(QPen(color, 1.2))
        painter.drawRoundedRect(QRectF(cursor_x, pill_y, pill_w, pill_h),
                                pill_h / 2, pill_h / 2)

        # 4px doctor dot at left of pill
        dot_r = 4
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            QPointF(cursor_x + 9, pill_y + pill_h / 2),
            dot_r, dot_r,
        )

        # code text
        painter.setPen(QPen(QColor(245, 245, 255)))
        painter.drawText(
            QRectF(cursor_x + 17, pill_y, pill_w - 17, pill_h),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            code,
        )

        cursor_x += pill_w + 6
        if i < len(doctors) - 1:
            # subtle interpunct divider
            painter.setPen(QPen(C_BAR_DIVIDER, 1.0))
            cx = int(cursor_x - 3)
            cy = int(y + h / 2)
            painter.drawLine(cx, cy - 2, cx, cy + 2)

    # ── Title / subtitle (center / right) ---------------------------------
    if title:
        title_font = app_chrome_font(13, bold=True)
        painter.setFont(title_font)
        painter.setPen(QPen(C_TEXT_PRIMARY))
        title_rect = QRectF(cursor_x + 16, y, w - (cursor_x + 16) - 14, h)
        painter.drawText(
            title_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            title,
        )

    if subtitle:
        sub_font = app_chrome_font(10, mono=True)
        painter.setFont(sub_font)
        painter.setPen(QPen(C_TEXT_SECONDARY))
        sub_fm = QFontMetrics(sub_font)
        sub_w = sub_fm.horizontalAdvance(subtitle)
        sub_rect = QRectF(x + w - sub_w - 14, y, sub_w + 8, h)
        painter.drawText(
            sub_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
            subtitle,
        )

    # ── Protocol-doc chip (a small ⓘ at the far right) --------------------
    if show_protocol_chip:
        chip_r = 7
        cx_chip = x + w - 14
        cy_chip = y + h / 2 + (8 if subtitle else 0)
        if subtitle:
            cy_chip = y + h - 10
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(120, 130, 200, 160), 1.0))
        # painter.drawEllipse(QPointF(cx_chip, cy_chip), chip_r, chip_r)
        # Skip the chip when subtitle is present to avoid crowding.

    painter.restore()


# ── HTML / QLabel API ──────────────────────────────────────────────────────
def doctor_sigil_html(
    doctors: list[str],
    title: str,
    *,
    subtitle: str | None = None,
) -> str:
    """Return rich HTML for a QLabel-based banner. Same visual language as
    the canvas painter but rendered via Qt's HTML subset for layouts that
    can't easily host a QPainter overlay (e.g., the Physarum Lab report)."""
    pills = []
    for code in doctors:
        c = doctor_color(code)
        hex_c = f"#{c.red():02x}{c.green():02x}{c.blue():02x}"
        pills.append(
            f'<span style="display:inline-block;'
            f'border:1px solid {hex_c};border-radius:9px;'
            f'padding:1px 10px 1px 8px;margin-right:6px;'
            f'background-color:rgba({c.red()},{c.green()},{c.blue()},0.12);'
            f'color:#f5f5ff;font-family:JetBrains Mono,Menlo,monospace;'
            f'font-size:11px;font-weight:600;">'
            f'<span style="color:{hex_c};">●</span>&nbsp;{code}'
            f'</span>'
        )
    pills_html = "".join(pills)
    sub_html = (
        f'<span style="color:#aab0d7;font-family:JetBrains Mono,Menlo,'
        f'monospace;font-size:10px;margin-left:14px;">{subtitle}</span>'
        if subtitle else ""
    )
    return (
        f'<div style="background:#0d0d1f;'
        f'padding:8px 14px;border-bottom:1px solid #5b3fa0;">'
        f'{pills_html}'
        f'<span style="color:#f5f5ff;font-family:JetBrains Mono,Menlo,'
        f'monospace;font-size:13px;font-weight:700;margin-left:14px;">'
        f'{title}</span>{sub_html}</div>'
    )
