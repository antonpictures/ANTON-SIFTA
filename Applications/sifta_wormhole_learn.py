#!/usr/bin/env python3
"""
sifta_wormhole_learn.py — Wormhole (W) learning app for the SIFTA Swarm.

George bought some Wormhole (W) as an investment but had not studied it; this is
an embedded, offline, EDUCATIONAL panel so he (and Alice) can learn what it is.
Category: Economy (sits next to the Finance dashboard). Pure PyQt6, no network,
no trading, no price feeds — facts grounded in a 2026-06-05 web pass, kept to the
stable fundamentals. NOT financial advice; crypto is volatile, verify live.

§7.5 Python-first / §7.6 embedded QWidget: no browser escape, no subprocess.
Cowork Claude, r537, 2026-06-05.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QTabWidget, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

_REPO = Path(__file__).resolve().parent.parent

# ── Palette (matches SIFTA dark panels) ───────────────────────────────
_BG = "#0a0c10"
_PANEL = "#141820"
_TEXT = "#dce1eb"
_DIM = "#6b7488"
_ACCENT = "#7c5cff"   # wormhole violet
_GOOD = "#00e08a"
_WARN = "#ffcc33"
_BAD = "#ff5c6c"

_SS = f"""
QWidget#WormholeRoot {{ background:{_BG}; }}
QTabWidget::pane {{ border:1px solid #232838; border-radius:10px; background:{_PANEL}; }}
QTabBar::tab {{ background:#11151d; color:{_DIM}; padding:8px 14px; margin-right:3px;
  border-top-left-radius:8px; border-top-right-radius:8px; font-size:12px; }}
QTabBar::tab:selected {{ background:{_PANEL}; color:{_TEXT}; border-bottom:2px solid {_ACCENT}; }}
QTabBar::tab:hover {{ color:{_TEXT}; }}
QScrollArea {{ border:none; background:transparent; }}
QLabel#Body {{ color:{_TEXT}; font-size:13px; }}
QLabel#Hero {{ color:{_TEXT}; }}
QLabel#Sub {{ color:{_DIM}; }}
QFrame#Disc {{ background:#1a1410; border:1px solid #3a2c10; border-radius:8px; }}
QLabel#DiscTxt {{ color:{_WARN}; font-size:12px; }}
"""

# ── Educational content (offline, grounded 2026-06-05) ────────────────
_TABS: dict[str, str] = {
    "Overview": f"""
<h2 style="color:{_ACCENT};">What is Wormhole?</h2>
<p>Wormhole is a <b>cross-chain interoperability protocol</b> — a generic
<i>message-passing layer</i> that lets separate blockchains talk to each other.
It is <b>not a blockchain itself</b>; it sits on top of existing chains and moves
tokens, NFTs, and arbitrary data between them.</p>
<ul>
<li>Launched (2021) as a bridge between <b>Ethereum and Solana</b>.</li>
<li>By 2026 it connects <b>30+ chains</b> (Ethereum, Solana, Cosmos, Sui, Base, and more).</li>
<li>Stewarded by the <b>Wormhole Foundation</b>; open-source at
<span style="color:{_ACCENT};">github.com/wormhole-foundation</span>.</li>
<li>Its native token is <b>W</b> (airdropped April 2024).</li>
</ul>
<p style="color:{_DIM};">Plain words: if money or data lives on chain A and you want it usable on chain B,
Wormhole is the "post office" that carries a verified message between them.</p>
""",
    "How it works": f"""
<h2 style="color:{_ACCENT};">Guardians &amp; VAAs</h2>
<p>The heart of Wormhole is the <b>Guardian Network</b> — <b>19 validators</b>
(Figment, P2P Validator, and others) that watch messages on the source chain.</p>
<ol>
<li>You do something on chain A (e.g. lock a token).</li>
<li>The Guardians observe it and each <b>sign</b> an attestation.</li>
<li>When a <b>supermajority — 13 of 19</b> — sign, they produce a
<b>VAA</b> (Verifiable Action Approval): a portable, signed cross-chain "receipt".</li>
<li>Chain B verifies the VAA's signatures and releases / mints the asset or runs the action.</li>
</ol>
<p style="color:{_GOOD};">Note for the Swarm 🐜⚡: a VAA is basically Wormhole's version of one of
<b>our</b> receipts — a signed, verifiable record that an action really happened, that
the other side checks before trusting it. Same instinct: <i>receipts decide, not trust.</i></p>
<p style="color:{_DIM};">The trust assumption: you are trusting that 13/19 Guardians are honest and
their keys are safe. That is the security model — and the main thing to understand before you rely on it.</p>
""",
    "The W token": f"""
<h2 style="color:{_ACCENT};">The W token</h2>
<p><b>W</b> is Wormhole's native <b>governance + utility</b> token.</p>
<ul>
<li><b>April 2024</b> — launched via a community airdrop.</li>
<li><b>Late 2025 — "W 2.0"</b> upgrade: evolved from governance-only into a
<b>multi-utility</b> asset, giving Guardians, builders, and holders real incentives
to keep the network healthy.</li>
<li><b>Governance</b> — vote on protocol changes.</li>
<li><b>Staking</b> — delegate W to Guardians; stakers/active users can accrue points and yields.</li>
<li><b>2026</b> — a <b>strategic W reserve</b> funded by on-chain + off-chain protocol revenue.</li>
</ul>
<p style="color:{_DIM};">What gives W value is demand for the protocol's services + the incentive
design — not a promise. Token <b>unlocks/vesting</b> (new supply entering circulation) can pressure price;
worth tracking the unlock schedule.</p>
""",
    "Products": f"""
<h2 style="color:{_ACCENT};">What you can actually do with it</h2>
<ul>
<li><b>Portal</b> — the flagship multichain bridge/swap app: move tokens between dozens of chains.</li>
<li><b>NTT (Native Token Transfers)</b> — move a token across chains <i>natively</i>,
without creating a separate "wrapped" version of it. A cleaner model than classic wrapped-asset bridges.</li>
<li><b>Queries</b> — read data <i>from</i> another chain on demand (cross-chain reads).</li>
<li><b>Connect</b> — a developer SDK/widget to drop bridging into any app.</li>
<li><b>Settlement</b> — fast cross-chain transfer/settlement rails for apps and intents.</li>
</ul>
<p style="color:{_DIM};">2026: a Portal upgrade + brand refresh aimed at faster, cheaper, more intuitive
cross-chain swaps, plus new incentive campaigns for W stakers.</p>
""",
    "Risks": f"""
<h2 style="color:{_BAD};">Risks — read this before you decide anything</h2>
<ul>
<li><b>Bridges are the #1 hack target in crypto.</b> They concentrate huge value in one
contract/validator set, so they get attacked.</li>
<li><b>Wormhole was hacked in Feb 2022</b> — about <b>$320M</b> drained via a
signature-verification bug on the Solana↔Ethereum bridge. Jump Crypto replaced the funds to
keep it solvent, but it is the textbook example of bridge risk.</li>
<li><b>Validator trust:</b> security rests on 13/19 Guardians staying honest and keeping keys safe.</li>
<li><b>Smart-contract risk:</b> bugs in the contracts on any connected chain.</li>
<li><b>Token risk:</b> unlocks/vesting add supply; price is volatile; utility is still maturing.</li>
</ul>
<p style="color:{_WARN};"><b>Not financial advice.</b> This panel exists to help you <i>understand</i>
what you bought, not to tell you to buy, hold, or sell. Prices and facts change — verify live, and the
decision is yours, George.</p>
""",
    "Glossary": f"""
<h2 style="color:{_ACCENT};">Glossary</h2>
<p><b>Interoperability</b> — different blockchains being able to work together.</p>
<p><b>Bridge</b> — infrastructure that moves value/data between two chains.</p>
<p><b>Guardian</b> — one of the 19 validators that observe and sign cross-chain messages.</p>
<p><b>VAA (Verifiable Action Approval)</b> — the signed, portable cross-chain receipt a destination chain verifies.</p>
<p><b>Supermajority</b> — here, 13 of 19 Guardians must agree for a transfer to go through.</p>
<p><b>Wrapped asset</b> — a stand-in token representing an asset that actually lives on another chain.</p>
<p><b>NTT</b> — Native Token Transfers; moving a token across chains <i>without</i> wrapping it.</p>
<p><b>W</b> — Wormhole's governance + utility token.</p>
""",
    "Links": f"""
<h2 style="color:{_ACCENT};">Learn more (open in your real browser)</h2>
<ul>
<li><b>wormhole.com</b> — official site</li>
<li><b>github.com/wormhole-foundation</b> — the open-source code</li>
<li><b>docs.wormhole.com</b> — developer + protocol docs</li>
<li><b>Wormhole Foundation</b> blog — product + token updates</li>
</ul>
<p style="color:{_DIM};">These are reference pointers. For anything involving your wallet or your
real W, use your own trusted browser/wallet — never paste keys into an embedded surface.</p>
"""
}


class WormholeLearnApp(QWidget):
    """Embedded educational panel about Wormhole (W). Offline, no trading."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("WormholeRoot")
        self.setStyleSheet(_SS)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # Header
        hero = QLabel("🌀  Wormhole — Learn")
        hero.setObjectName("Hero")
        hf = QFont()
        hf.setPointSize(20)
        hf.setBold(True)
        hero.setFont(hf)
        root.addWidget(hero)

        sub = QLabel("Cross-chain interoperability protocol · the W token · educational, not financial advice")
        sub.setObjectName("Sub")
        root.addWidget(sub)

        # Tabs of content
        tabs = QTabWidget()
        for name, html in _TABS.items():
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            body = QLabel(html.strip())
            body.setObjectName("Body")
            body.setWordWrap(True)
            body.setTextFormat(Qt.TextFormat.RichText)
            body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            body.setContentsMargins(14, 12, 14, 12)
            scroll.setWidget(body)
            tabs.addTab(scroll, name)
        root.addWidget(tabs, 1)

        # Footer disclaimer
        disc = QFrame()
        disc.setObjectName("Disc")
        dl = QVBoxLayout(disc)
        dl.setContentsMargins(12, 8, 12, 8)
        dtxt = QLabel(
            "⚠️ Educational only — not financial advice. Facts grounded 2026-06-05; "
            "crypto is volatile, verify live. Your W, your decision."
        )
        dtxt.setObjectName("DiscTxt")
        dtxt.setWordWrap(True)
        dl.addWidget(dtxt)
        root.addWidget(disc)


# Standalone run for headless dev/testing.
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = WormholeLearnApp()
    w.resize(820, 640)
    w.show()
    sys.exit(app.exec())
