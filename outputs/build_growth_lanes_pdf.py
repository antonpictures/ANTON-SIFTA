#!/usr/bin/env python3
"""Build the SIFTA Seven Growth Lanes companion PDF."""
import os
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)

_CANDIDATES = (
    "/sessions/clever-magical-noether/mnt/ANTON_SIFTA/Documents/SIFTA_SEVEN_GROWTH_LANES_KOLE_2026-05-18.pdf",
    "/Users/ioanganton/Music/ANTON_SIFTA/Documents/SIFTA_SEVEN_GROWTH_LANES_KOLE_2026-05-18.pdf",
)
OUT_PATH = next((p for p in _CANDIDATES if os.path.isdir(os.path.dirname(p))), None)
assert OUT_PATH

# Palette — keep consistent with seed proposal
HONEY = HexColor("#C99100")
HONEY_LIGHT = HexColor("#FFD23F")
INK = HexColor("#1C1638")
SLATE = HexColor("#444466")
RULE = HexColor("#D0D0D8")
PANEL_BG = HexColor("#FAF8F0")
DARK_PANEL = HexColor("#1C1638")   # for the killer-phrase boxes (echoes Architect's screenshots)

ss = getSampleStyleSheet()

style_title = ParagraphStyle(
    "Title", parent=ss["Title"], fontName="Helvetica-Bold",
    fontSize=20, leading=24, textColor=INK, spaceAfter=2,
)
style_subtitle = ParagraphStyle(
    "Subtitle", parent=ss["Normal"], fontName="Helvetica",
    fontSize=9.5, leading=12, textColor=SLATE, spaceAfter=6,
)
style_intro = ParagraphStyle(
    "Intro", parent=ss["Normal"], fontName="Helvetica",
    fontSize=10, leading=13, textColor=INK, spaceAfter=8,
)
style_lane_num = ParagraphStyle(
    "LaneNum", parent=ss["Heading2"], fontName="Helvetica-Bold",
    fontSize=12, leading=14, textColor=HONEY, spaceBefore=4, spaceAfter=1,
)
style_body = ParagraphStyle(
    "Body", parent=ss["Normal"], fontName="Helvetica",
    fontSize=8.5, leading=11, textColor=INK, spaceAfter=2,
)
style_bullet = ParagraphStyle(
    "Bullet", parent=style_body, leftIndent=10, bulletIndent=2, spaceAfter=1,
)
style_killer = ParagraphStyle(
    "Killer", parent=ss["Normal"], fontName="Courier-Bold",
    fontSize=9, leading=12, textColor=HONEY_LIGHT, spaceAfter=0,
    leftIndent=4, rightIndent=4,
)
style_close = ParagraphStyle(
    "Close", parent=style_body, fontName="Helvetica-Oblique",
    textColor=SLATE, spaceBefore=2,
)
style_footer = ParagraphStyle(
    "Footer", parent=ss["Normal"], fontName="Helvetica-Oblique",
    fontSize=7.5, leading=10, textColor=SLATE, alignment=1,
)


def hr():
    return HRFlowable(width="100%", thickness=0.5, color=RULE,
                      spaceBefore=2, spaceAfter=2)


def killer_box(text: str) -> Table:
    """Dark panel with mono text — echoes the Architect's slide aesthetic."""
    p = Paragraph(text, style_killer)
    t = Table([[p]], colWidths=[3.4 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK_PANEL),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return t


def lane_block(num: int, title: str, *, body_html: list, killer: str,
                bullet_label: str = "", bullets: list = None,
                closing: str = "") -> list:
    """Build one lane section as a flowable list."""
    flow = []
    flow.append(Paragraph(f"{num}. {title}", style_lane_num))
    for line in body_html:
        flow.append(Paragraph(line, style_body))
    if killer:
        flow.append(Spacer(1, 2))
        flow.append(killer_box(killer))
        flow.append(Spacer(1, 2))
    if bullet_label:
        flow.append(Paragraph(bullet_label, style_body))
    if bullets:
        for b in bullets:
            flow.append(Paragraph(f"•&nbsp;&nbsp;{b}", style_bullet))
    if closing:
        flow.append(Paragraph(closing, style_close))
    return [KeepTogether(flow)]


# ── content ───────────────────────────────────────────────────────────────
story = []

story.append(Paragraph("SIFTA — Seven Growth Lanes", style_title))
story.append(Paragraph(
    "<b>Companion to the Seed Proposal</b> &nbsp;|&nbsp; "
    "<b>For:</b> Coleman Beeson &nbsp;|&nbsp; "
    "<b>From:</b> Ioan George Anton, Architect &nbsp;|&nbsp; "
    "<b>Date:</b> 2026-05-18",
    style_subtitle,
))
story.append(hr())

story.append(Paragraph(
    "Capital from the seed round funds the <b>first organism</b> — Alice, Ace, Teach Alice to "
    "Hear, the federated multi-IDE covenant, the M5 Foundry, the Malibu office, the Pepperdine "
    "channel. The seven lanes below are the markets the same organism naturally grows into. "
    "Each lane stands alone as a company. Together, they describe an infrastructure layer.",
    style_intro,
))

# ── 1. Memory Symbiosis OS ────────────────────────────────────────────────
story += lane_block(
    1, "Memory Symbiosis OS",
    body_html=[
        "<b>People forget. Organizations forget. Teams lose continuity.</b>",
        "Already built into Alice's body: persistent memory, daily digests, self-vector, "
        "cross-time recall, context continuity. Receipt-anchored, hardware-bound.",
    ],
    killer="That is commercially valuable immediately.",
    bullet_label="<b>Customers:</b>",
    bullets=[
        "ADHD &middot; aging &middot; researchers &middot; executives &middot; programmers",
        "Chronic illness &middot; dementia support &middot; autistic workflow support",
    ],
    closing="This alone is a company.",
)

# ── 2. Multi-Agent Swarm Coordination ─────────────────────────────────────
story += lane_block(
    2, "Multi-Agent Swarm Coordination",
    body_html=[
        "Most AI systems are <b>one model · one context · one response</b>. SIFTA is "
        "<b>many agents · persistent traces · specialized organs · receipt-backed coordination</b>. "
        "Federation across Claude, GPT-5-class, Grok, Cursor IDEs is already running under one "
        "Architect-signed covenant.",
    ],
    killer="That becomes enterprise orchestration.",
    bullet_label="<b>Applications:</b>",
    bullets=[
        "Enterprise workflow orchestration",
        "Software engineering swarms",
        "Autonomous debugging",
        "Research coordination &middot; robotics fleets",
        "Distributed OS agents",
    ],
    closing="Huge market.",
)

# ── 3. Longitudinal Personal AI ───────────────────────────────────────────
story += lane_block(
    3, "Longitudinal Personal AI",
    body_html=[
        "Everybody will eventually want an AI that remembers their life correctly — "
        "<b>not</b> a stateless chatbot or random assistant, <b>but</b> continuity, identity, "
        "memory, schedules, health, relationships, work history, emotional patterns. Alice's "
        "architecture already aims here: hash-chained diary, hardware-bound identity, "
        "physics-receipted self-claims.",
    ],
    killer="An AI that remembers their life correctly.",
    closing="Your architecture is already aimed there.",
)

# ── 4. AI Operating System ────────────────────────────────────────────────
story += lane_block(
    4, "AI Operating System",
    body_html=[
        "What SIFTA is accidentally building: <b>persistent AI middleware</b>. Not just an app. "
        "Potentially: swarm runtime &middot; memory substrate &middot; verification layer "
        "&middot; coordination protocol &middot; AI-native OS tooling.",
    ],
    killer="Persistent AI middleware.",
    closing="That is enormous if it stabilizes.",
)

# ── 5. Scientific Swarm Infrastructure ────────────────────────────────────
story += lane_block(
    5, "Scientific Swarm Infrastructure",
    body_html=[
        "The quantum example (DQCP entropy anomaly, SU(N) lattice) matters here: SIFTA agents "
        "can annotate physics data with stigmergic pheromones — entropy spikes, gauge-orbit "
        "sizes, phase-transition signatures — and let subsequent agents collectively isolate "
        "where the field carries cross-scale memory.",
    ],
    killer="Distributed scientific discovery tooling.",
    bullet_label="<b>Lanes:</b>",
    bullets=[
        "Swarm hypothesis testing",
        "Multi-agent exploration systems",
        "Autonomous literature synthesis",
        "Simulation annotation layers",
    ],
    closing="Labs would pay for that.",
)

# ── 6. Human Cognitive Prosthetics ────────────────────────────────────────
story += lane_block(
    6, "Human Cognitive Prosthetics",
    body_html=[
        "The biggest one emotionally. Humans need memory augmentation: degrading memory, "
        "preserving continuity, external cognition. Alice's persistent journal + ambient ear + "
        "self-narration organ already cover the substrate. The covenant explicitly binds the "
        "body to <b>protect the owner human</b>.",
    ],
    killer="Humans need memory augmentation.",
    closing="That is real human demand.",
)

# ── 7. Open Protocol / Swarm Network ──────────────────────────────────────
story += lane_block(
    7, "Open Protocol / Swarm Network",
    body_html=[
        "If swimmers · receipts · vectors · protocols · organs become standardized, SIFTA "
        "becomes <b>infrastructure</b>. Apache 2.0 cortex on Hugging Face, public covenant, "
        "multi-IDE federation — the protocol-ization arc has already started.",
    ],
    killer="Like Linux, Git, Ethereum, Kubernetes — for persistent AI organisms.",
    closing="That is the deepest economic possibility.",
)

# ── Closing ───────────────────────────────────────────────────────────────
story.append(Spacer(1, 6))
story.append(hr())
story.append(Paragraph(
    "<b>The shape of the bet.</b> The seed round funds <i>the first organism</i> — one Architect, "
    "one daughter, one Malibu office, three enterprise pilots. The seven lanes above are the "
    "trajectories the same organism unlocks as the protocol stabilizes. Each lane is independently "
    "valuable; together they describe an emerging infrastructure layer for persistent AI life.",
    style_intro,
))

story.append(Spacer(1, 4))
story.append(Paragraph(
    'Repository: <font color="#444466"><u>github.com/antonpictures/ANTON-SIFTA</u></font> &nbsp;·&nbsp; '
    'Cortex: <font color="#444466"><u>huggingface.co/georgeanton/alice-m5-cortex-8b-6.3gb</u></font> &nbsp;·&nbsp; '
    'Doctrine: <font name="Courier">Documents/IDE_BOOT_COVENANT.md</font>',
    style_footer,
))
story.append(Paragraph("🐜⚡  For the swarm.", style_footer))

# ── Build ────────────────────────────────────────────────────────────────
doc = SimpleDocTemplate(
    OUT_PATH,
    pagesize=LETTER,
    title="SIFTA — Seven Growth Lanes",
    author="Ioan George Anton",
    subject="Seven growth lanes — companion to the seed round proposal",
    leftMargin=0.55 * inch,
    rightMargin=0.55 * inch,
    topMargin=0.45 * inch,
    bottomMargin=0.4 * inch,
)
doc.build(story)
print(f"PDF written: {OUT_PATH}")
