#!/usr/bin/env python3
"""Build a one-page PDF response to Philippe's commercial-viability checklist."""
from __future__ import annotations

from pathlib import Path
from textwrap import wrap

import fitz


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs"
PDF_OUT = OUT_DIR / "PHILIPPE_SIFTA_COMMERCIAL_RESPONSE_2026-06-14.pdf"
PNG_OUT = OUT_DIR / "PHILIPPE_SIFTA_COMMERCIAL_RESPONSE_2026-06-14.png"

PAGE_W = 612
PAGE_H = 792
MARGIN = 34

INK = (0.07, 0.09, 0.13)
MUTED = (0.29, 0.33, 0.40)
RULE = (0.78, 0.82, 0.86)
GREEN = (0.02, 0.36, 0.28)
GREEN_DARK = (0.02, 0.20, 0.17)
BLUE = (0.08, 0.24, 0.52)
GOLD = (0.70, 0.43, 0.08)
LIGHT_GREEN = (0.91, 0.97, 0.94)
LIGHT_BLUE = (0.91, 0.95, 0.99)
LIGHT_GOLD = (1.00, 0.96, 0.86)
LIGHT_GRAY = (0.96, 0.97, 0.98)
LIGHT_RED = (0.99, 0.94, 0.93)


def rect(page: fitz.Page, box: fitz.Rect, *, fill, stroke=RULE, width: float = 0.8) -> None:
    page.draw_rect(box, color=stroke, fill=fill, width=width)


def text_box(
    page: fitz.Page,
    box: fitz.Rect,
    text: str,
    *,
    size: float = 8.0,
    color=INK,
    font: str = "helv",
    align: int = fitz.TEXT_ALIGN_LEFT,
) -> float:
    return page.insert_textbox(box, text, fontsize=size, fontname=font, color=color, align=align)


def title(page: fitz.Page, x: float, y: float, text: str, *, size: float = 9.0, color=GREEN_DARK) -> None:
    page.insert_text((x, y), text, fontsize=size, fontname="hebo", color=color)


def wrapped_lines(text: str, chars: int) -> list[str]:
    lines: list[str] = []
    for part in text.splitlines():
        if not part.strip():
            lines.append("")
        else:
            lines.extend(wrap(part.strip(), chars))
    return lines


def bullet_list(page: fitz.Page, x: float, y: float, width: float, items: list[str], *, size: float = 7.3) -> float:
    line_h = size + 2.4
    for item in items:
        lines = wrapped_lines(item, max(28, int(width / (size * 0.47))))
        if not lines:
            continue
        page.insert_text((x, y), "-", fontsize=size, fontname="hebo", color=GREEN)
        page.insert_text((x + 8, y), lines[0], fontsize=size, fontname="helv", color=INK)
        y += line_h
        for line in lines[1:]:
            page.insert_text((x + 8, y), line, fontsize=size, fontname="helv", color=INK)
            y += line_h
        y += 1.5
    return y


def callout(page: fitz.Page, box: fitz.Rect, heading: str, body: str, *, fill=LIGHT_GRAY) -> None:
    rect(page, box, fill=fill)
    title(page, box.x0 + 9, box.y0 + 17, heading, size=8.2)
    text_box(page, fitz.Rect(box.x0 + 9, box.y0 + 24, box.x1 - 9, box.y1 - 7), body, size=6.9, color=INK)


def build() -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)

    # Header
    header = fitz.Rect(0, 0, PAGE_W, 82)
    rect(page, header, fill=GREEN_DARK, stroke=GREEN_DARK, width=0)
    page.insert_text((MARGIN, 30), "SIFTA: Commercial Viability Response", fontsize=19, fontname="hebo", color=(1, 1, 1))
    page.insert_text(
        (MARGIN, 50),
        "One-page answer to Philippe's checklist: use case, demo, differentiation, users, pilots",
        fontsize=8.6,
        fontname="helv",
        color=(1, 1, 1),
    )
    page.insert_text((PAGE_W - MARGIN - 116, 30), "Prepared 2026-06-14", fontsize=7.5, fontname="helv", color=(1, 1, 1))
    page.insert_text((PAGE_W - MARGIN - 116, 46), "Evidence: local code + tests", fontsize=7.5, fontname="helv", color=(1, 1, 1))

    summary_box = fitz.Rect(MARGIN, 96, PAGE_W - MARGIN, 142)
    rect(page, summary_box, fill=(0.97, 0.99, 0.98))
    title(page, summary_box.x0 + 10, summary_box.y0 + 17, "Positioning", size=8.4)
    summary = (
        "Short answer: yes, SIFTA can be saleable if it is positioned as a receipt-backed "
        "local agent operating system for high-trust actions, not as another generic "
        "multi-agent framework. The wedge is owner-silicon autonomy: one owner intent, "
        "one nonce, one auditable action, and no double-spend."
    )
    sy = summary_box.y0 + 30
    for line in wrapped_lines(summary, 116)[:3]:
        page.insert_text((summary_box.x0 + 10, sy), line, fontsize=7.2, fontname="hebo", color=GREEN_DARK)
        sy += 9.3

    col_gap = 14
    col_w = (PAGE_W - 2 * MARGIN - col_gap) / 2
    left = MARGIN
    right = MARGIN + col_w + col_gap
    top = 154
    box_h = 216

    rect(page, fitz.Rect(left, top, left + col_w, top + box_h), fill=LIGHT_GREEN)
    title(page, left + 10, top + 18, "1. Concrete use case")
    y = top + 34
    text_box(
        page,
        fitz.Rect(left + 10, y, left + col_w - 10, top + box_h - 10),
        "A local, auditable AI workbench for regulated or safety-sensitive workflows where a buyer must prove what the agent saw, who authorized it, what tool/action ran, and whether a second spend/action was refused.",
        size=7.6,
    )
    y = top + 96
    title(page, left + 10, y, "First saleable wedge", size=7.8, color=BLUE)
    y += 14
    y = bullet_list(
        page,
        left + 13,
        y,
        col_w - 26,
        [
            "Agent-commerce guard: purchase/action intent rows before effectors.",
            "MCP tool receipt wrapper: world-touching tools are classed and gated.",
            "Owner-body effector guard: local hardware and camera/body receipts, not cloud-only policy.",
            "Robot/proof lane: real IK datasets ingested as virtual effectors before any metal claim.",
        ],
        size=6.9,
    )

    rect(page, fitz.Rect(right, top, right + col_w, top + box_h), fill=LIGHT_BLUE)
    title(page, right + 10, top + 18, "2. Five-minute demo")
    demo_items = [
        "Open Alice and show /cortex: multiple brains are arms of one local body.",
        "Ask Alice to list her real body files: answer comes from disk inventory.",
        "Run one receipt-gated action: owner intent -> nonce -> allowed effector.",
        "Attempt the second spend/action: show the refusal receipt.",
        "Show robotics E49/E50 evidence: real datasets, virtual effector receipts, no metal overclaim.",
    ]
    bullet_list(page, right + 13, top + 38, col_w - 26, demo_items, size=7.0)

    mid_top = top + box_h + 13
    mid_h = 151
    rect(page, fitz.Rect(left, mid_top, left + col_w, mid_top + mid_h), fill=LIGHT_GOLD)
    title(page, left + 10, mid_top + 18, "3. Evidence checked today")
    evidence = [
        "59 focused tests passed: commerce gate, MCP manifest, E49/E50 robotics, MiMo lanes, self-improvement spinal/substrate.",
        "E49 ABB IRB 2400: Kaggle dataset path, 18-column schema, virtual effector round-trip.",
        "E50 ARKOMA NAO: real pose-to-joint dataset slice and virtual effector lane.",
        "MiMo/Cline/OpenRouter truth: Xiaomi MiMo endpoint is not overclaimed as OpenRouter.",
    ]
    bullet_list(page, left + 13, mid_top + 38, col_w - 26, evidence, size=6.75)

    rect(page, fitz.Rect(right, mid_top, right + col_w, mid_top + mid_h), fill=LIGHT_GRAY)
    title(page, right + 10, mid_top + 18, "4. Why not just CrewAI / LangGraph / SDKs?")
    text_box(
        page,
        fitz.Rect(right + 10, mid_top + 32, right + col_w - 10, mid_top + mid_h - 8),
        "Those are orchestration libraries. SIFTA's claim is a product stack: local hardware continuity, four-ledger receipts, owner-intent nonces, cortex switching, body-file self-knowledge, and testable effectors. The differentiator is not 'agents called ants'; it is accountable local autonomy with proof before action.",
        size=7.05,
    )

    lower_top = mid_top + mid_h + 13
    third_gap = 10
    third_w = (PAGE_W - 2 * MARGIN - 2 * third_gap) / 3
    callout(
        page,
        fitz.Rect(MARGIN, lower_top, MARGIN + third_w, lower_top + 101),
        "Actual users",
        "Current active operator/user: George on local Apple-silicon node. Public customer count: not yet proven. Treat this as founder-led pilot stage.",
        fill=LIGHT_BLUE,
    )
    callout(
        page,
        fitz.Rect(MARGIN + third_w + third_gap, lower_top, MARGIN + 2 * third_w + third_gap, lower_top + 101),
        "Revenue / pilots",
        "Do not overclaim revenue. The next sellable milestone is one paid pilot or LOI around a specific receipt-gated workflow.",
        fill=LIGHT_RED,
    )
    callout(
        page,
        fitz.Rect(MARGIN + 2 * (third_w + third_gap), lower_top, PAGE_W - MARGIN, lower_top + 101),
        "Ask to Philippe",
        "Give us 30 minutes: watch the five-minute demo, then help choose one narrow pilot where auditability beats a generic agent stack.",
        fill=LIGHT_GREEN,
    )

    truth_top = lower_top + 116
    rect(page, fitz.Rect(MARGIN, truth_top, PAGE_W - MARGIN, truth_top + 78), fill=(1, 1, 1))
    title(page, MARGIN + 10, truth_top + 18, "Truth boundary")
    text_box(
        page,
        fitz.Rect(MARGIN + 10, truth_top + 30, PAGE_W - MARGIN - 10, truth_top + 63),
        "Operational: local code, ledgers, tests, E49/E50 virtual effectors, MiMo/Cline cortex visibility, owner-intent nonce gate. Hypothesis: broad market pull, physical robot motion, revenue, and claims that SIFTA outperforms every framework. Forbidden: saying it is already a mature SaaS, a public token/payment network, or proven AGI.",
        size=6.9,
        color=MUTED,
    )
    page.insert_text(
        (MARGIN + 10, PAGE_H - 34),
        "Useful reply line: 'It is saleable if we sell the receipt-backed local trust layer first, then prove one paid pilot.'",
        fontsize=7.0,
        fontname="hebo",
        color=GREEN_DARK,
    )
    page.insert_text(
        (MARGIN + 10, PAGE_H - 20),
        "Sources: System/* gates, robotics organs, focused tests, and tournament r1127.",
        fontsize=6.2,
        fontname="helv",
        color=MUTED,
    )

    doc.set_metadata(
        {
            "title": "SIFTA Commercial Viability Response",
            "author": "SIFTA / George Anton",
            "subject": "One-page response to commercial viability checklist",
        }
    )
    doc.save(PDF_OUT, deflate=True, garbage=4)
    pix = page.get_pixmap(matrix=fitz.Matrix(1.45, 1.45), alpha=False)
    pix.save(PNG_OUT)
    doc.close()
    return PDF_OUT, PNG_OUT


if __name__ == "__main__":
    pdf, png = build()
    doc = fitz.open(pdf)
    print(f"wrote={pdf}")
    print(f"preview={png}")
    print(f"pages={doc.page_count}")
    doc.close()
