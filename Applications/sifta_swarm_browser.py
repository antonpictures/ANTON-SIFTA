#!/usr/bin/env python3
"""
sifta_swarm_browser.py — Stigmergic Swarm Browser
═══════════════════════════════════════════════════════════════════════
The web is hostile territory. The Swarm enters it for you.

You type a URL. The browser fetches the HTML, parses the DOM into a
graph, and deploys four swimmer species into it:

  SkeletonMapper   — maps <div> structure, marks content vs noise
  EntityHarvester  — dives into <p>/<h1-h6>, extracts text + entities
  LinkSentinel     — follows <a href>, checks against hostile patterns
  MediaExtractor   — finds <img>/<video> URLs, strips tracking pixels

Swimmers leave pheromone: green on useful nodes, red on hostile.
The DOM graph renders as a living radial tree with swimmers crawling it.

STGM minted for: entity extraction, tracker neutralization, clean text.

First app built on SiftaBaseWidget — inherits chrome, help, styling.
"""
from __future__ import annotations

import math
import random
import re
import ssl
import sys
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "System") not in sys.path:
    sys.path.insert(0, str(_REPO / "System"))

from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSplitter,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, QThread, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QRadialGradient, QPainterPath,
)

from sifta_base_widget import SiftaBaseWidget

# ── Hostile patterns ──────────────────────────────────────────────
AD_DOMAINS = {
    "doubleclick.net", "googlesyndication.com", "googleadservices.com",
    "facebook.com/tr", "analytics.google.com", "pixel.facebook.com",
    "ads.twitter.com", "amazon-adsystem.com", "adnxs.com",
    "criteo.com", "outbrain.com", "taboola.com", "scorecardresearch.com",
}
AD_CLASS_PATTERNS = re.compile(
    r"(ad[-_]?banner|ad[-_]?slot|sponsored|tracking|cookie[-_]?consent|popup[-_]?overlay)",
    re.IGNORECASE,
)
CONTENT_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "article", "section", "blockquote", "li", "td", "th"}
HOSTILE_TAGS = {"script", "noscript", "iframe", "object", "embed"}
MEDIA_TAGS = {"img", "video", "audio", "source", "picture"}
LINK_TAG = "a"
STRUCTURAL_TAGS = {"html", "head", "body", "div", "span", "main", "nav", "header", "footer", "aside", "form"}


# ═══════════════════════════════════════════════════════════════════
#  DOM PARSING
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DomNode:
    """A node in the parsed DOM tree."""
    id: int
    tag: str
    attrs: Dict[str, str] = field(default_factory=dict)
    text: str = ""
    children: List[int] = field(default_factory=list)
    parent: int = -1
    # Visualization
    x: float = 0.0
    y: float = 0.0
    # Swarm state
    pheromone_good: float = 0.0
    pheromone_bad: float = 0.0
    visited_count: int = 0
    classification: str = "unknown"  # content, hostile, structural, link, media


class DomTreeParser(HTMLParser):
    """Parse HTML into a flat list of DomNode with parent-child relationships."""

    def __init__(self):
        super().__init__()
        self.nodes: List[DomNode] = []
        self._stack: List[int] = []
        self._next_id = 0
        root = DomNode(id=0, tag="document", classification="structural")
        self.nodes.append(root)
        self._next_id = 1
        self._stack.append(0)

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        attr_dict = {k: v for k, v in attrs if k and v}
        node = DomNode(id=self._next_id, tag=tag, attrs=attr_dict)
        self._next_id += 1

        if tag in CONTENT_TAGS:
            node.classification = "content"
        elif tag in HOSTILE_TAGS:
            node.classification = "hostile"
        elif tag in MEDIA_TAGS:
            node.classification = "media"
        elif tag == LINK_TAG:
            node.classification = "link"
        else:
            node.classification = "structural"

        cls_str = attr_dict.get("class", "") + " " + attr_dict.get("id", "")
        if AD_CLASS_PATTERNS.search(cls_str):
            node.classification = "hostile"

        if tag == LINK_TAG:
            href = attr_dict.get("href", "")
            for ad in AD_DOMAINS:
                if ad in href:
                    node.classification = "hostile"
                    break

        parent_id = self._stack[-1] if self._stack else 0
        node.parent = parent_id
        if parent_id < len(self.nodes):
            self.nodes[parent_id].children.append(node.id)

        self.nodes.append(node)
        self._stack.append(node.id)

    def handle_endtag(self, tag):
        if len(self._stack) > 1:
            self._stack.pop()

    def handle_data(self, data):
        text = data.strip()
        if text and self._stack:
            parent_id = self._stack[-1]
            if parent_id < len(self.nodes):
                self.nodes[parent_id].text += " " + text


def parse_html(html: str) -> List[DomNode]:
    """Parse HTML string into DomNode list."""
    parser = DomTreeParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser.nodes


def layout_radial(nodes: List[DomNode], cx: float, cy: float, radius: float):
    """Assign x,y positions to nodes in a radial tree layout."""
    if not nodes:
        return
    nodes[0].x, nodes[0].y = cx, cy

    def _layout(node_id: int, angle_start: float, angle_span: float, depth: int):
        if node_id >= len(nodes):
            return
        node = nodes[node_id]
        children = [c for c in node.children if c < len(nodes)]
        if not children:
            return
        child_span = angle_span / max(len(children), 1)
        for i, cid in enumerate(children):
            a = angle_start + i * child_span + child_span / 2
            r = radius * (0.15 + depth * 0.18)
            r = min(r, radius * 0.95)
            nodes[cid].x = cx + r * math.cos(a)
            nodes[cid].y = cy + r * math.sin(a)
            _layout(cid, angle_start + i * child_span, child_span, depth + 1)

    _layout(0, 0, 2 * math.pi, 1)


# ═══════════════════════════════════════════════════════════════════
#  SWIMMERS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DomSwimmer:
    """A swimmer agent crawling the DOM tree."""
    species: str       # "skeleton", "entity", "link", "media"
    node_id: int = 0   # current node
    target_id: int = -1
    progress: float = 0.0  # 0→1 lerp between node and target
    entities_found: int = 0
    trackers_killed: int = 0
    stgm_earned: float = 0.0


# ═══════════════════════════════════════════════════════════════════
#  CANVAS
# ═══════════════════════════════════════════════════════════════════

NODE_COLORS = {
    "content":    QColor(0, 220, 160),
    "hostile":    QColor(255, 50, 80),
    "structural": QColor(60, 65, 90),
    "link":       QColor(100, 180, 255),
    "media":      QColor(255, 200, 60),
    "unknown":    QColor(50, 50, 65),
}

SWIMMER_COLORS = {
    "skeleton": QColor(120, 130, 180, 200),
    "entity":  QColor(0, 255, 200, 220),
    "link":    QColor(100, 180, 255, 200),
    "media":   QColor(255, 200, 60, 200),
}


class DomGraphCanvas(QWidget):
    """Renders the DOM graph, swimmers, and pheromone trails."""

    entity_found = pyqtSignal(str)
    tracker_killed = pyqtSignal(str)
    log_msg = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 400)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.nodes: List[DomNode] = []
        self.swimmers: List[DomSwimmer] = []
        self.tick_count = 0
        self.total_stgm = 0.0
        self.entities: List[str] = []
        self.quarantined: List[str] = []
        self.clean_text: List[str] = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def load_dom(self, nodes: List[DomNode]):
        self.nodes = nodes
        w, h = self.width() or 800, self.height() or 600
        layout_radial(self.nodes, w / 2, h / 2, min(w, h) / 2 - 30)
        self._spawn_swimmers()
        self._timer.start(40)

    def _spawn_swimmers(self):
        self.swimmers.clear()
        specs = [("skeleton", 25), ("entity", 20), ("link", 15), ("media", 10)]
        for species, count in specs:
            for _ in range(count):
                self.swimmers.append(DomSwimmer(species=species, node_id=0))

    def _tick(self):
        self.tick_count += 1
        if not self.nodes:
            return

        for ph in self.nodes:
            ph.pheromone_good *= 0.995
            ph.pheromone_bad *= 0.995

        for sw in self.swimmers:
            if sw.target_id >= 0 and sw.target_id < len(self.nodes):
                sw.progress += 0.08
                if sw.progress >= 1.0:
                    sw.node_id = sw.target_id
                    sw.target_id = -1
                    sw.progress = 0.0
                    self._process_arrival(sw)
                continue

            node = self.nodes[sw.node_id] if sw.node_id < len(self.nodes) else None
            if not node:
                continue

            candidates = list(node.children)
            if node.parent >= 0:
                candidates.append(node.parent)

            if not candidates:
                sw.node_id = 0
                continue

            if sw.species == "entity":
                content_kids = [c for c in candidates if c < len(self.nodes) and
                                self.nodes[c].classification == "content"]
                if content_kids:
                    candidates = content_kids
            elif sw.species == "link":
                link_kids = [c for c in candidates if c < len(self.nodes) and
                             self.nodes[c].classification == "link"]
                if link_kids:
                    candidates = link_kids
            elif sw.species == "media":
                media_kids = [c for c in candidates if c < len(self.nodes) and
                              self.nodes[c].classification == "media"]
                if media_kids:
                    candidates = media_kids

            weights = []
            for cid in candidates:
                if cid >= len(self.nodes):
                    weights.append(0.1)
                    continue
                cn = self.nodes[cid]
                w = 1.0 + cn.pheromone_good * 3.0 - cn.pheromone_bad * 5.0
                if cn.visited_count == 0:
                    w += 2.0
                weights.append(max(0.01, w))

            total_w = sum(weights)
            r = random.uniform(0, total_w)
            cumulative = 0.0
            chosen = candidates[0]
            for cid, wt in zip(candidates, weights):
                cumulative += wt
                if r <= cumulative:
                    chosen = cid
                    break

            sw.target_id = chosen
            sw.progress = 0.0

        self.update()

    def _process_arrival(self, sw: DomSwimmer):
        if sw.node_id >= len(self.nodes):
            return
        node = self.nodes[sw.node_id]
        node.visited_count += 1

        if node.classification == "hostile":
            node.pheromone_bad = min(1.0, node.pheromone_bad + 0.3)
            if node.visited_count == 1:
                sw.trackers_killed += 1
                sw.stgm_earned += 0.05
                self.total_stgm += 0.05
                desc = f"{node.tag}"
                href = node.attrs.get("src", node.attrs.get("href", ""))
                if href:
                    desc += f" → {href[:60]}"
                self.quarantined.append(desc)
                self.tracker_killed.emit(desc)
                self.log_msg.emit(f"QUARANTINE [{sw.species}] {desc}")

        elif node.classification == "content":
            node.pheromone_good = min(1.0, node.pheromone_good + 0.15)
            text = node.text.strip()
            if text and len(text) > 10 and sw.species == "entity":
                if text not in self.clean_text:
                    self.clean_text.append(text)
                    sw.entities_found += 1
                    sw.stgm_earned += 0.02
                    self.total_stgm += 0.02

                    entities = self._extract_entities(text)
                    for ent in entities:
                        if ent not in self.entities:
                            self.entities.append(ent)
                            self.entity_found.emit(ent)
                            self.log_msg.emit(f"ENTITY [{sw.species}] {ent}")

        elif node.classification == "link":
            href = node.attrs.get("href", "")
            if href:
                hostile = any(ad in href for ad in AD_DOMAINS)
                if hostile:
                    node.pheromone_bad = min(1.0, node.pheromone_bad + 0.4)
                    node.classification = "hostile"
                    self.log_msg.emit(f"LINK HOSTILE [{sw.species}] {href[:60]}")
                else:
                    node.pheromone_good = min(1.0, node.pheromone_good + 0.05)

        elif node.classification == "media":
            src = node.attrs.get("src", node.attrs.get("data-src", ""))
            if src and node.visited_count == 1:
                node.pheromone_good = min(1.0, node.pheromone_good + 0.1)
                self.log_msg.emit(f"MEDIA [{sw.species}] {src[:60]}")

    @staticmethod
    def _extract_entities(text: str) -> List[str]:
        """Basic entity extraction — names, dates, prices, emails."""
        found = []
        emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
        found.extend(f"EMAIL: {e}" for e in emails)
        prices = re.findall(r"\$[\d,]+(?:\.\d{2})?", text)
        found.extend(f"PRICE: {p}" for p in prices)
        dates = re.findall(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", text)
        found.extend(f"DATE: {d}" for d in dates)
        caps = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text)
        for c in caps[:3]:
            found.append(f"NAME: {c}")
        return found

    # ── Rendering ─────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(6, 8, 16))

        if not self.nodes:
            p.setPen(QPen(QColor(100, 108, 140)))
            p.setFont(QFont("Menlo", 14))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter,
                       "Enter a URL and press GO\nSwimmers will map the DOM territory")
            p.end()
            return

        # Edges
        for node in self.nodes:
            for cid in node.children:
                if cid < len(self.nodes):
                    child = self.nodes[cid]
                    alpha = 30 + int(node.pheromone_good * 80)
                    p.setPen(QPen(QColor(60, 65, 90, alpha), 0.5))
                    p.drawLine(QPointF(node.x, node.y), QPointF(child.x, child.y))

        # Pheromone glow on edges
        for node in self.nodes:
            if node.pheromone_good > 0.1:
                for cid in node.children:
                    if cid < len(self.nodes):
                        child = self.nodes[cid]
                        a = int(node.pheromone_good * 150)
                        p.setPen(QPen(QColor(0, 255, 200, a), 1.5))
                        p.drawLine(QPointF(node.x, node.y), QPointF(child.x, child.y))
            if node.pheromone_bad > 0.1:
                for cid in node.children:
                    if cid < len(self.nodes):
                        child = self.nodes[cid]
                        a = int(node.pheromone_bad * 150)
                        p.setPen(QPen(QColor(255, 40, 60, a), 1.5))
                        p.drawLine(QPointF(node.x, node.y), QPointF(child.x, child.y))

        # Nodes
        for node in self.nodes[1:]:
            color = NODE_COLORS.get(node.classification, NODE_COLORS["unknown"])
            radius = 3.0
            if node.classification == "content":
                radius = 4.0 + node.pheromone_good * 3
            elif node.classification == "hostile":
                radius = 3.5 + node.pheromone_bad * 3

            if node.visited_count > 0:
                glow = QRadialGradient(node.x, node.y, radius * 3)
                glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 60))
                glow.setColorAt(1, QColor(0, 0, 0, 0))
                p.setBrush(QBrush(glow))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(node.x, node.y), radius * 3, radius * 3)

            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(node.x, node.y), radius, radius)

        # Swimmers
        for sw in self.swimmers:
            if sw.node_id >= len(self.nodes):
                continue
            src = self.nodes[sw.node_id]
            sx, sy = src.x, src.y

            if sw.target_id >= 0 and sw.target_id < len(self.nodes):
                tgt = self.nodes[sw.target_id]
                t = sw.progress
                sx = src.x + (tgt.x - src.x) * t
                sy = src.y + (tgt.y - src.y) * t

            color = SWIMMER_COLORS.get(sw.species, QColor(200, 200, 200, 180))
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            r = 2.5 if sw.species == "skeleton" else 3.0
            p.drawEllipse(QPointF(sx, sy), r, r)

        # HUD
        p.setPen(QPen(QColor(0, 255, 200)))
        p.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        stats = (f"Nodes: {len(self.nodes)}  |  Swimmers: {len(self.swimmers)}  |  "
                 f"Entities: {len(self.entities)}  |  "
                 f"Quarantined: {len(self.quarantined)}  |  "
                 f"Clean Text: {len(self.clean_text)}  |  "
                 f"STGM: {self.total_stgm:.2f}")
        p.drawText(QPointF(10, h - 12), stats)

        # Legend
        p.setFont(QFont("Menlo", 10))
        legend_y = 18
        for name, color in [("Content", NODE_COLORS["content"]),
                            ("Hostile", NODE_COLORS["hostile"]),
                            ("Link", NODE_COLORS["link"]),
                            ("Media", NODE_COLORS["media"]),
                            ("Structure", NODE_COLORS["structural"])]:
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(w - 120, legend_y), 5, 5)
            p.setPen(QPen(QColor(160, 168, 200)))
            p.drawText(QPointF(w - 108, legend_y + 5), name)
            legend_y += 18

        p.end()

    def resizeEvent(self, event):
        if self.nodes:
            w, h = self.width(), self.height()
            layout_radial(self.nodes, w / 2, h / 2, min(w, h) / 2 - 30)
        super().resizeEvent(event)


# ═══════════════════════════════════════════════════════════════════
#  FETCH WORKER (background thread)
# ═══════════════════════════════════════════════════════════════════

def _ssl_context_for_https() -> ssl.SSLContext:
    """
    urllib uses the interpreter's default CA store; on many macOS Python installs
    that store is incomplete → CERTIFICATE_VERIFY_FAILED. Prefer certifi's Mozilla
    CA bundle when installed.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class FetchWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            req = Request(self.url, headers={"User-Agent": "SIFTA-SwarmBrowser/1.0"})
            ctx = None
            if self.url.startswith("https://"):
                ctx = _ssl_context_for_https()
            kw = {"timeout": 15}
            if ctx is not None:
                kw["context"] = ctx
            with urlopen(req, **kw) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            self.finished.emit(html)
        except Exception as e:
            err = str(e)
            if "CERTIFICATE_VERIFY_FAILED" in err or "SSL: CERTIFICATE_VERIFY_FAILED" in err:
                err += (
                    " — Install CA bundle: pip install certifi (added to requirements.txt). "
                    "On macOS you can also run Applications/Python 3.x/Install Certificates.command."
                )
            self.error.emit(err)


# ═══════════════════════════════════════════════════════════════════
#  DEMO HTML (when no URL)
# ═══════════════════════════════════════════════════════════════════

DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head><title>SIFTA Swarm Browser Demo Page</title>
<script src="https://ads.doubleclick.net/tracker.js"></script>
</head>
<body>
<header><nav><a href="/">Home</a><a href="/about">About</a><a href="/contact">Contact</a></nav></header>
<main>
<article>
<h1>Stigmergic Intelligence: How Ants Solve Problems Computers Cannot</h1>
<p>Professor Marco Dorigo at Universite Libre de Bruxelles first described Ant Colony Optimization in 1992. His work showed that simple agents following pheromone trails could solve NP-hard routing problems faster than classical algorithms.</p>
<p>On April 14, 2026, researcher Ioan George Anton demonstrated a sovereign operating system where all coordination emerges from environmental traces rather than message passing.</p>
<h2>Key Findings from the SIFTA Project</h2>
<p>The system maintains $0.00 external dependency costs. Two Apple Silicon nodes communicate via git-synced append-only ledgers signed with Ed25519 cryptography.</p>
<p>Contact the lab at sifta@example.com or visit the demo at https://sifta.example.com for more information. The next presentation is on 05/15/2026.</p>
<p>Professor Eric Bonabeau and Guy Theraulaz at Santa Fe Institute extended the theory to show that stigmergic systems exhibit robust fault tolerance under partial node failure.</p>
<div class="ad-banner sponsored"><iframe src="https://googlesyndication.com/ad/12345"></iframe></div>
<h3>Economic Model: Proof of Useful Work</h3>
<p>Unlike Bitcoin mining which wastes energy on hash puzzles, SIFTA rewards agents only for verified utility: repairing code, routing inference, destroying authenticated hostile injections.</p>
<img src="/images/swarm_topology.png" alt="Swarm topology diagram">
<img src="https://pixel.facebook.com/tr?ev=PageView" alt="">
</article>
<aside>
<div class="tracking" id="ad_slot_sidebar">
<script src="https://criteo.com/track.js"></script>
<a href="https://taboola.com/click?id=spam123">Sponsored Content</a>
</div>
</aside>
</main>
<footer><p>Copyright 2026 SIFTA Research Lab. All rights reserved.</p>
<a href="https://outbrain.com/tracking/pixel.gif">
<img src="https://scorecardresearch.com/beacon.js" alt="">
</a>
</footer>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════
#  MAIN WIDGET
# ═══════════════════════════════════════════════════════════════════

class SwarmBrowserWidget(SiftaBaseWidget):
    APP_NAME = "SIFTA Swarm Browser"

    def build_ui(self, layout: QVBoxLayout) -> None:
        # URL bar
        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        lbl = QLabel("TARGET:")
        lbl.setStyleSheet("color: rgb(0,255,200); font-weight: bold; font-size: 11px;")
        url_row.addWidget(lbl)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com — or press DEMO to deploy on synthetic DOM")
        self.url_input.returnPressed.connect(self._go)
        url_row.addWidget(self.url_input, 1)

        btn_go = QPushButton("DEPLOY")
        btn_go.clicked.connect(self._go)
        url_row.addWidget(btn_go)

        btn_demo = QPushButton("DEMO")
        btn_demo.clicked.connect(self._load_demo)
        url_row.addWidget(btn_demo)

        layout.addLayout(url_row)

        # Splitter: canvas + sidebar
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.canvas = DomGraphCanvas()
        self.canvas.entity_found.connect(self._on_entity)
        self.canvas.tracker_killed.connect(self._on_tracker)
        self.canvas.log_msg.connect(self._on_log)
        splitter.addWidget(self.canvas)

        sidebar = QTabWidget()
        sidebar.setMinimumWidth(360)
        sidebar.setMaximumWidth(480)
        sidebar.setStyleSheet(
            "QTabBar::tab { font-size: 11px; padding: 5px 12px; min-width: 80px; }"
        )

        # Quarantine FIRST — the user wants to see hostile data front and center
        self.quarantine_view = QTextEdit()
        self.quarantine_view.setReadOnly(True)
        self.quarantine_view.setStyleSheet(
            "QTextEdit { background: rgb(10,8,16); color: rgb(255,80,100); font-size: 13px; }"
        )
        sidebar.addTab(self.quarantine_view, "🛡 Quarantine")

        self.entity_view = QTextEdit()
        self.entity_view.setReadOnly(True)
        self.entity_view.setStyleSheet(
            "QTextEdit { font-size: 13px; }"
        )
        sidebar.addTab(self.entity_view, "🔍 Entities")

        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setStyleSheet(
            "QTextEdit { font-size: 13px; }"
        )
        sidebar.addTab(self.text_view, "📄 Text")

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "QTextEdit { font-size: 12px; }"
        )
        sidebar.addTab(self.log_view, "📋 Log")

        splitter.addWidget(sidebar)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self._log_lines: List[str] = []
        self._fetch_worker: Optional[FetchWorker] = None

        self._refresh_timer = self.make_timer(500, self._refresh_panels)

    def _go(self):
        url = self.url_input.text().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.url_input.setText(url)

        self.set_status(f"Fetching {url}...")
        self._fetch_worker = FetchWorker(url)
        self._fetch_worker.finished.connect(self._on_html)
        self._fetch_worker.error.connect(self._on_error)
        self._fetch_worker.start()

    def _load_demo(self):
        self._on_html(DEMO_HTML)
        self.url_input.setText("demo://sifta-swarm-browser-test-page")
        self.set_status("Demo DOM loaded — swimmers deployed")

    def _on_html(self, html: str):
        nodes = parse_html(html)
        self.canvas.entities.clear()
        self.canvas.quarantined.clear()
        self.canvas.clean_text.clear()
        self.canvas.total_stgm = 0.0
        self._log_lines.clear()

        self.canvas.load_dom(nodes)

        hostile_count = sum(1 for n in nodes if n.classification == "hostile")
        content_count = sum(1 for n in nodes if n.classification == "content")
        self.set_status(f"DOM: {len(nodes)} nodes ({content_count} content, {hostile_count} hostile) — 70 swimmers deployed")
        self._log_lines.append(f"[{time.strftime('%H:%M:%S')}] DOM parsed: {len(nodes)} nodes")
        self._log_lines.append(f"[{time.strftime('%H:%M:%S')}] Hostile nodes pre-flagged: {hostile_count}")
        self._log_lines.append(f"[{time.strftime('%H:%M:%S')}] Swimmers deployed: 70 (25 skeleton, 20 entity, 15 link, 10 media)")

    def _on_error(self, err: str):
        self.set_status(f"Fetch failed: {err}")
        self._log_lines.append(f"[{time.strftime('%H:%M:%S')}] ERROR: {err}")

    def _on_entity(self, ent: str):
        pass

    def _on_tracker(self, desc: str):
        pass

    def _on_log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self._log_lines.append(f"[{ts}] {msg}")
        if len(self._log_lines) > 500:
            self._log_lines = self._log_lines[-500:]

    def _refresh_panels(self):
        if self.canvas.entities:
            self.entity_view.setPlainText("\n".join(self.canvas.entities[-100:]))
        if self.canvas.clean_text:
            self.text_view.setPlainText("\n\n---\n\n".join(self.canvas.clean_text[-50:]))
        if self.canvas.quarantined:
            lines = []
            for i, desc in enumerate(self.canvas.quarantined[-100:], 1):
                lines.append(f"⛔ #{i}  {desc}")
            header = (f"=== HOSTILE INTERCEPTORS ===\n"
                      f"Trackers neutralized: {len(self.canvas.quarantined)}\n"
                      f"STGM earned from quarantine: "
                      f"{len(self.canvas.quarantined) * 0.05:.2f}\n\n")
            self.quarantine_view.setPlainText(header + "\n".join(lines))
        if self._log_lines:
            self.log_view.setPlainText("\n".join(self._log_lines[-100:]))
            sb = self.log_view.verticalScrollBar()
            sb.setValue(sb.maximum())

    def closeEvent(self, event):
        self.canvas._timer.stop()
        super().closeEvent(event)
