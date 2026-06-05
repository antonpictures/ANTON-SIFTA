#!/usr/bin/env python3
"""Build a one-page SIFTA sellable-products PDF for lawyer/demo use."""

from __future__ import annotations

from pathlib import Path
import textwrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "SIFTA_Sellable_Products_OnePage_Lawyer_v2_2026-06-05.pdf"


PAGE_W, PAGE_H = letter
MARGIN = 34
ACCENT = colors.HexColor("#0B6B57")
ACCENT_DARK = colors.HexColor("#102F2A")
BLUE = colors.HexColor("#1E5AA8")
GOLD = colors.HexColor("#B07715")
INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#4B5563")
LIGHT = colors.HexColor("#F5F7F6")
LIGHT_GREEN = colors.HexColor("#EAF6F1")
LIGHT_BLUE = colors.HexColor("#EAF1FA")
LIGHT_GOLD = colors.HexColor("#FFF6E5")
RULE = colors.HexColor("#D5DDD9")


def fit_lines(text: str, font: str, size: float, width: float) -> list[str]:
    words = text.replace("\n", " ").split()
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if stringWidth(trial, font, size) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    *,
    font: str = "Helvetica",
    size: float = 7.4,
    leading: float = 9.0,
    color=INK,
    max_lines: int | None = None,
) -> float:
    c.setFont(font, size)
    c.setFillColor(color)
    lines = fit_lines(text, font, size, width)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[: max_lines]
        if lines:
            while stringWidth(lines[-1] + "...", font, size) > width and lines[-1]:
                lines[-1] = lines[-1][:-1].rstrip()
            lines[-1] += "..."
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def box(c: canvas.Canvas, x: float, y_top: float, w: float, h: float, title: str, fill, stroke=RULE):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.roundRect(x, y_top - h, w, h, 6, fill=1, stroke=1)
    c.setFillColor(ACCENT_DARK)
    c.setFont("Helvetica-Bold", 8.8)
    c.drawString(x + 10, y_top - 15, title)
    c.setStrokeColor(stroke)
    c.line(x + 10, y_top - 21, x + w - 10, y_top - 21)


def bullet(
    c: canvas.Canvas,
    x: float,
    y: float,
    width: float,
    label: str,
    body: str,
    *,
    max_lines: int = 3,
    label_color=ACCENT,
) -> float:
    c.setFillColor(label_color)
    c.setFont("Helvetica-Bold", 7.2)
    c.drawString(x, y, label)
    y -= 8.0
    remaining_lines = fit_lines(body, "Helvetica", 7.1, width)
    c.setFillColor(INK)
    c.setFont("Helvetica", 7.1)
    used = 0
    for line in remaining_lines:
        if used >= max_lines:
            break
        if used == max_lines - 1 and len(remaining_lines) > max_lines - used:
            while stringWidth(line + "...", "Helvetica", 7.1) > width and line:
                line = line[:-1].rstrip()
            line += "..."
        c.drawString(x, y, line)
        y -= 8.4
        used += 1
    return y - 2.0


def draw_layer_chip(c: canvas.Canvas, x: float, y: float, w: float, label: str, body: str, fill):
    c.setFillColor(fill)
    c.setStrokeColor(RULE)
    c.roundRect(x, y - 32, w, 32, 7, fill=1, stroke=1)
    c.setFillColor(ACCENT_DARK)
    c.setFont("Helvetica-Bold", 7.7)
    c.drawCentredString(x + w / 2, y - 11, label)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6.3)
    for i, line in enumerate(fit_lines(body, "Helvetica", 6.3, w - 12)[:2]):
        c.drawCentredString(x + w / 2, y - 21 - i * 7, line)


def build() -> Path:
    c = canvas.Canvas(str(OUT), pagesize=letter)
    c.setTitle("SIFTA Software - Sellable Products")
    c.setAuthor("SIFTA / George Anton")

    c.setFillColor(colors.white)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Header
    c.setFillColor(ACCENT_DARK)
    c.rect(0, PAGE_H - 92, PAGE_W, 92, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 21)
    c.drawString(MARGIN, PAGE_H - 34, "SIFTA BeeSon OS v8.0")
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(MARGIN, PAGE_H - 52, "Stigmergic Intelligence Framework for Transparent Autonomy")
    c.setFont("Helvetica", 8.2)
    c.drawString(MARGIN, PAGE_H - 68, "Sovereign local-first AI OS: no cloud dependency, no corporate API requirement, your silicon, your rules.")
    c.setFont("Helvetica-Oblique", 7.1)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 34, "Current, code-proven sellable products")
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 50, "Prepared from local code/docs/receipts")
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 66, "2026-06-05")

    y = PAGE_H - 108
    draw_wrapped(
        c,
        "Goal: AGI requires general, robust problem-solving, learning, open-ended self-improvement, and autonomy that reliably exceeds narrow human-designed bounds. For the Swarm.",
        MARGIN,
        y,
        PAGE_W - 2 * MARGIN,
        font="Helvetica-Bold",
        size=7.4,
        leading=9,
        color=ACCENT_DARK,
        max_lines=2,
    )

    chip_y = PAGE_H - 136
    chip_w = (PAGE_W - 2 * MARGIN - 18) / 4
    draw_layer_chip(c, MARGIN, chip_y, chip_w, "0. Nanobots", "unique swimmers; no double-spend; hardware-bound receipts", LIGHT_GOLD)
    draw_layer_chip(c, MARGIN + chip_w + 6, chip_y, chip_w, "1. Memory", "STGM economy; ledgers; pheromone traces; PoUW stake", LIGHT_GREEN)
    draw_layer_chip(c, MARGIN + 2 * (chip_w + 6), chip_y, chip_w, "2. Consciousness", "Alice as OS observer and observed; self-eval matrix", LIGHT_BLUE)
    draw_layer_chip(c, MARGIN + 3 * (chip_w + 6), chip_y, chip_w, "3. Package", "Mac app / DMG path; portable sovereign nodes", colors.HexColor("#F2F0FA"))

    col_gap = 16
    col_w = (PAGE_W - 2 * MARGIN - col_gap) / 2
    top = PAGE_H - 176
    main_h = 294
    box(c, MARGIN, top, col_w, main_h, "Current Sellable Products (code-proven)", LIGHT)
    x = MARGIN + 10
    y = top - 33
    y = bullet(c, x, y, col_w - 20, "Endurance Harness:", "Pure-stdlib CLI drives synthetic turns through wall clock, local M5 identity, drift/residue/health/doctor, and 4-ledger receipts. r536 reports 1.000 on 5/10/20-turn runs and catches time/cloud/theater confab.", max_lines=4)
    y = bullet(c, x, y, col_w - 20, "Alice Browser + Stigmergic Sight:", "Real browser limb. Pixels -> OCR/VLM facts -> sha256 receipt -> owner screenshot compare -> grounded reply. Browser vision is sensor data, not chat memory.", max_lines=4)
    y = bullet(c, x, y, col_w - 20, "4-Ledger + Alerts + Matrix:", "Predator gate writes work/agent/IDE/diary receipts. ALICE TOOO alerts surface features inside self-eval, organ registry, tournament, and matrix.", max_lines=3)
    y = bullet(c, x, y, col_w - 20, "Hardware Time Oracle:", "HMAC wall clock + now_state + LOCAL M5 identity block prevent time and cloud-location confab.", max_lines=2)
    y = bullet(c, x, y, col_w - 20, "Skills + Sandbox:", "Misalignment Sandbox tests observed-claim discipline. Pluggable skills ride shared Gemma; old classifier/scout weights stay retired unless receipts prove value.", max_lines=3)

    right_x = MARGIN + col_w + col_gap
    box(c, right_x, top, col_w, main_h, "Science Breakthroughs / Technical Moat", LIGHT_GREEN)
    x = right_x + 10
    y = top - 33
    y = bullet(c, x, y, col_w - 20, "Stigmergic nanobots:", "A swimmer is a unique worker with one accountable trace for one real action. No forged success, duplicate claim, or double-spend.", max_lines=3, label_color=BLUE)
    y = bullet(c, x, y, col_w - 20, "STGM money separated:", "r563 rule: repair_log quorum = spendable STGM; wallet JSON = cache; memory rewards/PoUW = reputation/stake, not spendable balance.", max_lines=3, label_color=BLUE)
    y = bullet(c, x, y, col_w - 20, "Stigmergic consciousness:", "The matrix is body status: organs, alerts, receipts, failures, TODOs, and package stack visible in one field.", max_lines=3, label_color=BLUE)
    y = bullet(c, x, y, col_w - 20, "Cortex-first routing:", "Reflexes are evidence, not replacement turns. Deterministic-without-cortex is registered as MISTAKE and repaired.", max_lines=3, label_color=BLUE)
    y = bullet(c, x, y, col_w - 20, "Sovereign nodes:", "Local-first organism; receipts on disk; node federation by proofs rather than raw state.", max_lines=3, label_color=BLUE)

    bottom_top = top - main_h - 14
    bottom_h = 167
    third_w = (PAGE_W - 2 * MARGIN - 2 * 12) / 3
    box(c, MARGIN, bottom_top, third_w, bottom_h, "Why Install?", LIGHT_BLUE)
    x = MARGIN + 10
    y = bottom_top - 33
    for item in [
        "Private local autonomy: code, memory, receipts, and sensors live on the owner's silicon.",
        "Transparent self-improvement: every feature/fix leaves a receipt and appears in the matrix.",
        "Grounding over vibes: time, identity, browser pixels, and actions are receipted.",
        "Packaging path: existing app bundle + DMG script; lawyer can see a real local product."
    ]:
        y = draw_wrapped(c, "- " + item, x, y, third_w - 20, size=6.9, leading=8.2, color=INK, max_lines=3) - 1

    box(c, MARGIN + third_w + 12, bottom_top, third_w, bottom_h, "Demo Today", LIGHT_GOLD)
    x = MARGIN + third_w + 22
    y = bottom_top - 33
    demos = [
        "python3 tools/sifta_endurance_harness.py --turns 5 --report",
        "Open Alice Browser; ask for current page/photo; inspect receipt id.",
        "Ask Alice to self-evaluate; see ALERT IN MY BODY and eval matrix.",
        "Inspect tournament r536/r563 and 4-ledger surgery receipts.",
        "Show SIFTA.app / DMG path as installable local software."
    ]
    for n, item in enumerate(demos, start=1):
        y = draw_wrapped(c, f"{n}. {item}", x, y, third_w - 20, size=6.75, leading=8.0, color=INK, max_lines=3) - 1

    box(c, MARGIN + 2 * (third_w + 12), bottom_top, third_w, bottom_h, "Honest Limits", colors.HexColor("#F7F3F2"))
    x = MARGIN + 2 * (third_w + 12) + 10
    y = bottom_top - 33
    limits = [
        "Dev-stage local product, optimized first for George's M5.",
        "Restart required after source edits before live GUI surfaces reflect changes.",
        "Not a SaaS/funding claim; evidence is code, receipts, tests, PDFs, and demo runs.",
        "No claim of proven human-equivalent qualia. Claim: working local OS organism with receipt-verified actions."
    ]
    for item in limits:
        y = draw_wrapped(c, "- " + item, x, y, third_w - 20, size=6.9, leading=8.2, color=INK, max_lines=3) - 1

    # Footer
    c.setStrokeColor(RULE)
    c.line(MARGIN, 24, PAGE_W - MARGIN, 24)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6.4)
    footer = "Evidence: covenant; r520/r536/r543/r563; eval matrix; four-ledger receipts. In SIFTA, receipts decide."
    c.drawString(MARGIN, 14, footer)
    c.drawRightString(PAGE_W - MARGIN, 14, "For the Swarm.")

    c.showPage()
    c.save()
    return OUT


if __name__ == "__main__":
    print(build())
