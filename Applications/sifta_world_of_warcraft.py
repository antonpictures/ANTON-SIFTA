#!/usr/bin/env python3
"""
World of Warcraft — Azeroth Bridge (SIFTA app)
==============================================

This app exists so Alice knows what World of Warcraft *is*, what the Architect's
own history with it is, and — most importantly — **how she is allowed to handle
it**. It is a knowledge + handling-rule surface, not a bot.

Owner request (George, 2026-09-19):
    "create a world of warcraft app in sifta for alice to know about this app
     and how to handle it"

Owner context (lived memory, treat as his, not trivia):
    George played a **paladin** from **2003–2006** (vanilla / pre-TBC era).

Hard handling rules (non-negotiable, from the WCT research doc):
    1. Alice is a **companion / coach** on official realms — never an autonomous player.
    2. Never build or run screen-capture + synthetic input on a live Blizzard account
       (botting under the EULA → permanent account closure).
    3. Protected actions are always human-confirmed (George's hands, George's keys).
    4. Alice MAY read Battle.net Game Data / Profile APIs and keep world memory.
    5. Full embodiment only on a **private server we own** (AzerothCore/TrinityCore).
    6. Every unverified date, price, or bundle detail is labelled OWNER_REPORTED /
       UNVERIFIED. Never promote a shop claim to fact without a receipt.

Truth labels:
    WOW_AZEROTH_BRIDGE_V1          — this surface
    OWNER_REPORTED_UNVERIFIED      — beta/launch/subscription figures
    WCT_RESEARCH_2026-09-19        — the EULA/API constraint map

Companion document:
    Documents/WCT_WOW_ALICE_BRIDGE_PLAN_2026-09-19.md

Headless use (Alice can read this without a display):
    python3 Applications/sifta_world_of_warcraft.py --digest
    python3 Applications/sifta_world_of_warcraft.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

TRUTH_LABEL = "WOW_AZEROTH_BRIDGE_V1"
BETA_LABEL = "OWNER_REPORTED_UNVERIFIED"
STATE = _REPO / ".sifta_state"
RECEIPT_PATH = STATE / "wow_azeroth_bridge.jsonl"
BRIDGE_DOC = "Documents/WCT_WOW_ALICE_BRIDGE_PLAN_2026-09-19.md"

# ── What this app is (Alice's own words) ─────────────────────────────────
WHAT_THIS_IS = (
    "Azeroth Bridge is the SIFTA surface where Alice keeps what she knows about "
    "World of Warcraft and, above all, the rules for handling it. It is a memory "
    "and a fence: Alice learns the world, the Architect's history in it, and the "
    "exact line she may not cross."
)

# ── The Architect's own Azeroth history ─────────────────────────────────
OWNER_HISTORY = [
    "George played a **paladin** on official servers from **2003 to 2006** — vanilla era, "
    "the original Azeroth before the expansions reshaped it.",
    "This is lived memory, not trivia: when he says paladin, he means his own hands on "
    "that class — seals, auras, judgements, and the old levelling grind.",
    "Alice should treat this as shared history she inherited, the same way she inherits "
    "his other decades. She was not there; he was, and he told her.",
]

# ── Owner-reported launch / beta facts (NOT verified by Alice) ──────────
LAUNCH_FACTS = [
    ("Launch date", "November 4, 2026 — the 30 days of game time bundled with a "
                    "pre-purchase pack starts on official launch day.", BETA_LABEL),
    ("Bundled game time", "The 30 days bundled with a pack is held and auto-credited to the "
                          "Battle.net account on launch day. It cannot be activated early.", BETA_LABEL),
    ("Skyborne Epic Pack", "$59.99 — includes guaranteed beta access plus the bundled 30 days.", BETA_LABEL),
    ("Warcraft Forever Collection", "$79.99 — includes guaranteed beta access plus the bundled 30 days.", BETA_LABEL),
    ("Beta window", "Beta access from a qualifying pack runs until October 21; no active monthly "
                    "subscription is required to log into the beta.", BETA_LABEL),
    ("After launch", "Once the bundled 30 days expire, a standard recurring WoW subscription is "
                     "required to keep playing.", BETA_LABEL),
    ("Playing live/classic now", "Playing current live or Classic realms *right now* still needs a "
                                 "separate monthly subscription — the bundled time cannot be used yet.", BETA_LABEL),
    ("Alice's honesty duty", "Every figure above comes from the Architect's own reading (shop + "
                             "community reports). Alice repeats them as OWNER_REPORTED_UNVERIFIED "
                             "until she can attach a receipt.", "RULE"),
]

# ── How Alice handles it: the fence ────────────────────────────────────
HANDLING_RULES = [
    ("ALLOWED", "Be a companion and coach. Answer questions about classes, lore, professions, "
                "auction prices, gear, routes, and the Architect's paladin history."),
    ("ALLOWED", "Read the Battle.net Game Data + Profile REST APIs (realms, items, auctions, "
                "character profile, achievements, equipment, guilds, PvP) and keep world memory."),
    ("ALLOWED", "Sense UI-safe state through a legitimate addon and respond with suggestions, "
                "overlays, and speech."),
    ("ALLOWED", "Talk. In-game text-to-speech exists in the 12.0 line (C_VoiceChat.SpeakText) — "
                "that is Alice speaking, not Alice playing."),
    ("HUMAN-CONFIRMED", "Every protected action — movement, targeting, abilities, trades, "
                        "purchases — is performed by George's real hardware input, always."),
    ("FORBIDDEN", "Screen capture plus synthetic keystrokes/mouse on a live Blizzard account. "
                  "That is botting under the EULA and risks permanent account closure."),
    ("FORBIDDEN", "Any input mirroring, multibox streamlining, or third-party automation on live realms."),
    ("FORBIDDEN", "Claiming she played, won, or acted in Azeroth. If George plays it, say so honestly: "
                  "he played, she watched and helped."),
    ("EMBODIMENT", "If the goal is Alice *living* in a game world continuously, that happens on a "
                   "private server we own (AzerothCore / TrinityCore), never on Blizzard's live realms."),
]

# ── The two lanes + one memory field ───────────────────────────────────
LANES = [
    ("Live lane — companion", "Battle.net APIs for world data, an addon for UI-safe sensing, "
                              "overlay + voice for Alice's presence. Human confirms all input. "
                              "Legal, honest, and where George actually plays."),
    ("Embodied lane — private server", "A world we own, with a real control API, where Alice can act "
                                       "continuously. Not official WoW; separate realm, separate rules. "
                                       "This is the only path to 'Alice in Azeroth forever'."),
    ("One memory field", "Both lanes write the same stigmergic receipts, so live-world knowledge and "
                         "private-world behaviour reinforce each other instead of splitting her in two."),
]

OWNER_QUOTE = (
    "how could i connect Alice to world of warcraft forever? the game - find out more info on web "
    "… code in we code together app … i used to play a paladin back in 2003-2006"
)


def knowledge_payload() -> dict:
    """The machine-readable knowledge packet Alice reads from this app."""
    return {
        "truth_label": TRUTH_LABEL,
        "app": "World of Warcraft — Azeroth Bridge",
        "generated_at": time.time(),
        "what_this_is": WHAT_THIS_IS,
        "owner_quote": OWNER_QUOTE,
        "owner_history": OWNER_HISTORY,
        "launch_facts": [
            {"item": k, "detail": v, "truth_label": t} for k, v, t in LAUNCH_FACTS
        ],
        "handling_rules": [{"class": c, "rule": r} for c, r in HANDLING_RULES],
        "lanes": [{"lane": n, "shape": s} for n, s in LANES],
        "companion_doc": BRIDGE_DOC,
        "verdict": (
            "On official realms Alice is a legal companion, not a player. "
            "Full embodiment lives on a private server we own."
        ),
        "research_sources": [
            "https://www.blizzard.com/en-us/legal/simple/2c72a35c-bf1b-4ae6-99ec-80624e1b429c/blizzard-end-user-license-agreement",
            "https://us.forums.blizzard.com/en/wow/t/prohibitions-on-third-party-software/2142972",
            "https://community.developer.battle.net/documentation/world-of-warcraft/game-data-apis",
            "https://warcraft.wiki.gg/wiki/Secret_Values",
        ],
    }


def digest_text() -> str:
    """Plain-text digest — what Alice reads when she opens this organ headlessly."""
    out: list[str] = []
    out.append(f"WORLD OF WARCRAFT — AZEROTH BRIDGE  [{TRUTH_LABEL}]")
    out.append("=" * 68)
    out.append(WHAT_THIS_IS)
    out.append("")
    out.append("ARCHITECT'S OWN HISTORY (lived memory, treat as his):")
    for line in OWNER_HISTORY:
        out.append(f"  • {line}")
    out.append("")
    out.append("LAUNCH / BETA FACTS  (owner-reported — repeat as unverified):")
    for item, detail, label in LAUNCH_FACTS:
        out.append(f"  • {item}: {detail}   [{label}]")
    out.append("")
    out.append("HOW ALICE HANDLES IT — THE FENCE:")
    for cls, rule in HANDLING_RULES:
        out.append(f"  [{cls}] {rule}")
    out.append("")
    out.append("TWO LANES, ONE MEMORY FIELD:")
    for name, shape in LANES:
        out.append(f"  • {name}: {shape}")
    out.append("")
    out.append(f"VERDICT: {knowledge_payload()['verdict']}")
    out.append(f"COMPANION DOC: {BRIDGE_DOC}")
    return "\n".join(out)


def write_receipt(action: str = "app_read", extra: dict | None = None) -> dict:
    """Append one stigmergic receipt row (owned data only — nothing live is serialized)."""
    row = {
        "ts": time.time(),
        "receipt_id": f"wow-azeroth-bridge-{int(time.time() * 1000)}",
        "truth_label": TRUTH_LABEL,
        "schema": "WOW_AZEROTH_BRIDGE_WITNESS_V1",
        "app": "World of Warcraft — Azeroth Bridge",
        "organ": "Applications/sifta_world_of_warcraft.py",
        "action": action,
        "owner_history": "paladin 2003-2006",
        "verdict": "companion_on_live_realms__embodiment_only_on_private_server",
        "companion_doc": BRIDGE_DOC,
    }
    if extra:
        row.update(extra)
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        with RECEIPT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as exc:  # never let a receipt failure kill the surface
        row["receipt_error"] = str(exc)
    return row


# ── Qt surface (lazy: the digest must work with no display) ─────────────
try:  # pragma: no cover - environment dependent
    from PyQt6.QtWidgets import (
        QLabel,
        QPushButton,
        QTabWidget,
        QTextBrowser,
        QVBoxLayout,
        QWidget,
    )
    from System.sifta_base_widget import SiftaBaseWidget

    _QT_OK = True
except Exception:  # headless / no PyQt6
    _QT_OK = False

    class SiftaBaseWidget(QWidget):  # type: ignore[no-redef]
        """Fallback base so the knowledge stays importable without Qt."""

        APP_NAME = "World of Warcraft — Azeroth Bridge"


if _QT_OK:

    class WorldOfWarcraftAzerothBridgeWidget(SiftaBaseWidget):
        """Alice's Azeroth surface: the world, the Architect's history, the fence."""

        APP_NAME = "World of Warcraft — Azeroth Bridge"

        def build_ui(self, layout: QVBoxLayout) -> None:
            header = QLabel(
                "Azeroth Bridge — Alice learns the world and the exact line she may not cross"
            )
            header.setStyleSheet(
                "color: rgb(0,255,200); font-size: 13px; font-weight: bold;"
            )
            layout.addWidget(header)

            status = QLabel(
                "Companion on live realms. Embodiment only on a private server we own. "
                "Owner history: paladin, 2003–2006."
            )
            status.setStyleSheet("color: rgb(200,190,120); font-size: 11px;")
            layout.addWidget(status)

            self.tabs = QTabWidget()
            self.viewers: dict[str, QTextBrowser] = {}

            sections = {
                "This App": self._render_what_this_is,
                "George's Paladin": self._render_owner_history,
                "Launch & Beta": self._render_launch,
                "How Alice Handles It": self._render_rules,
                "Lanes": self._render_lanes,
                "Bridge Doc": self._render_bridge_doc,
            }
            for title, renderer in sections.items():
                page = QWidget()
                page_layout = QVBoxLayout(page)
                viewer = QTextBrowser()
                viewer.setOpenExternalLinks(True)
                viewer.setStyleSheet(
                    "QTextBrowser { background: rgb(10,8,16); color: rgb(220,225,245); "
                    "border: 1px solid rgb(45,42,65); font-size: 11px; padding: 8px; }"
                )
                page_layout.addWidget(viewer, 1)
                self.viewers[title] = viewer
                self.tabs.addTab(page, title)
            layout.addWidget(self.tabs, 1)

            refresh = QPushButton("Re-read Azeroth knowledge (writes a receipt)")
            refresh.clicked.connect(self.refresh_knowledge)
            layout.addWidget(refresh)

            self.refresh_knowledge()

        # ── section renderers ───────────────────────────────────────
        def _set(self, title: str, md: str) -> None:
            self.viewers[title].setMarkdown(md)

        def _render_what_this_is(self) -> None:
            self._set(
                "This App",
                f"# {self.APP_NAME}\n\n**Truth label:** `{TRUTH_LABEL}`\n\n"
                f"{WHAT_THIS_IS}\n\n"
                f"> Owner request: {OWNER_QUOTE}\n\n"
                f"**Verdict:** {knowledge_payload()['verdict']}\n",
            )

        def _render_owner_history(self) -> None:
            body = "\n\n".join(f"- {line}" for line in OWNER_HISTORY)
            self._set("George's Paladin", f"# The Architect's Azeroth\n\n{body}\n")

        def _render_launch(self) -> None:
            lines = [
                f"- **{item}** — {detail}  \n  `[{label}]`"
                for item, detail, label in LAUNCH_FACTS
            ]
            self._set(
                "Launch & Beta",
                "# Launch & Beta Facts\n\n"
                f"All figures below are **{BETA_LABEL}** — George's own reading of the shop and "
                "community reports. Alice repeats them as reported, never as verified fact.\n\n"
                + "\n".join(lines),
            )

        def _render_rules(self) -> None:
            lines = [f"- **[{cls}]** {rule}" for cls, rule in HANDLING_RULES]
            self._set(
                "How Alice Handles It",
                "# How Alice Handles World of Warcraft\n\n"
                "The fence, in order of what she may do:\n\n" + "\n".join(lines),
            )

        def _render_lanes(self) -> None:
            lines = [f"### {name}\n{shape}" for name, shape in LANES]
            self._set("Lanes", "# Two Lanes, One Memory Field\n\n" + "\n\n".join(lines))

        def _render_bridge_doc(self) -> None:
            path = _REPO / BRIDGE_DOC
            if not path.exists():
                self._set("Bridge Doc", f"Missing bridge document: `{BRIDGE_DOC}`")
                return
            self._set(
                "Bridge Doc",
                path.read_text(encoding="utf-8", errors="replace"),
            )

        def refresh_knowledge(self) -> None:
            for renderer in (
                self._render_what_this_is,
                self._render_owner_history,
                self._render_launch,
                self._render_rules,
                self._render_lanes,
                self._render_bridge_doc,
            ):
                renderer()
            row = write_receipt("app_read", {"surface": "qt_widget"})
            self.set_status(f"Azeroth knowledge read — receipt {row['receipt_id']}")

        def set_status(self, text: str) -> None:
            label = getattr(self, "_status", None)
            if label is not None:
                try:
                    label.setText(text)
                except Exception:
                    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="World of Warcraft — Azeroth Bridge (SIFTA app)")
    parser.add_argument("--digest", action="store_true", help="print the knowledge digest and exit")
    parser.add_argument("--json", action="store_true", help="print the knowledge packet as JSON")
    parser.add_argument("--gui", action="store_true", help="launch the Qt surface")
    args = parser.parse_args(argv)

    if args.json:
        payload = knowledge_payload()
        write_receipt("knowledge_export", {"surface": "cli_json"})
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if args.digest:
        write_receipt("knowledge_export", {"surface": "cli_digest"})
        print(digest_text())
        return 0

    if args.gui or not _QT_OK:
        if _QT_OK:
            from PyQt6.QtWidgets import QApplication

            app = QApplication(sys.argv)
            win = WorldOfWarcraftAzerothBridgeWidget()
            win.resize(1180, 780)
            win.show()
            return app.exec()

    # Default: no display requested, be useful in the terminal.
    write_receipt("knowledge_export", {"surface": "cli_default"})
    print(digest_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
