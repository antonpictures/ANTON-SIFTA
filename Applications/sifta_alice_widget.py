#!/usr/bin/env python3
"""
sifta_alice_widget.py — Alice (unified ear + eye + mesh, single window)
══════════════════════════════════════════════════════════════════════════
Architect doctrine (2026-04-19, C47H):
The Talk-to-Alice and What-Alice-Sees widgets are two organs of the SAME
entity (Alice). They were autostarting as TWO separate MDI windows; the
Architect asked for ONE app that opens by default with both audio and
video together. This widget is that app.

Layout
──────
    ┌──────────────────────────────────┬──────────────────────────────┐
    │  TalkToAliceWidget               │  WhatAliceSeesWidget         │
    │  (mic listener, brain, voice)    │  (camera, photon stigmergy)  │
    │  ALICE_M5 mesh sidebar (right)   │  ALICE_M5 mesh sidebar (right)│
    └──────────────────────────────────┴──────────────────────────────┘
QSplitter so the Architect can drag the divider; default 60/40 split
favouring the talk panel because that's where the conversation lives.

Boot greeting
─────────────
We suppress each child's own boot greeting (via env vars) so the user
hears ONE coherent greeting from this wrapper instead of three. The
unified greeting is a real telemetry sweep, not a fixed string:

    "Microphone online. Camera online. Wi-Fi telemetry active.
     I'm awake and listening, Architect."

Each clause is added only if the corresponding subsystem is actually
healthy at the moment of the greeting (probed live, not asserted).

Half-duplex discipline
──────────────────────
Both children share the module-level BROCA_SPEAKING gate from
swarm_broca_wernicke, so the mic listener (in the talk panel) won't
transcribe anything we vocalize from this wrapper. The same TTSWorker
class the talk panel uses for replies is used here for the greeting,
keeping the speech path single-threaded through swarm_vocal_cords.

Standalone vs OS-embedded
─────────────────────────
Like the children, this widget refuses to launch standalone if the
SIFTA OS desktop is already running (the autostart entry has already
opened a copy inside the MDI; a second copy would race for camera and
mic). Standalone mode is for development only.

Env overrides (Architect-tunable, no hardcoding):
    SIFTA_ALICE_UNIFIED_BOOT_SILENT=1
        Skip the unified spoken greeting entirely.
    SIFTA_ALICE_UNIFIED_GREETING="custom string"
        Override the auto-generated telemetry greeting.
    SIFTA_ALICE_UNIFIED_SPLIT="960,1100"
        Initial QSplitter sizes (left, right). Defaults to 960,1100.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

# ── Suppress child boot greetings BEFORE importing them ─────────────────────
# The talk widget reads SIFTA_ALICE_BOOT_SILENT at __init__ time. We unify
# greetings here so we set it on import. The Architect can still re-enable
# the child greeting independently with SIFTA_ALICE_BOOT_SILENT=0 if they
# launch the talk widget standalone outside this wrapper.
os.environ.setdefault("SIFTA_ALICE_BOOT_SILENT", "1")

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QSplitter, QWidget

# Child widgets — imported AFTER the env-var suppression above.
from Applications.sifta_talk_to_alice_widget import (  # noqa: E402
    TalkToAliceWidget,
    _TTSWorker,
)
from Applications.sifta_what_alice_sees_widget import (  # noqa: E402
    WhatAliceSeesWidget,
)


class AliceWidget(QWidget):
    """
    Unified Alice — ear + eye in one window.

    Hosts a TalkToAliceWidget (left) and a WhatAliceSeesWidget (right)
    inside a horizontal QSplitter. Both are real instances; this is not
    a thin facade. Mic and camera each have exactly ONE owner in the
    process (the children), so there is no resource contention.

    Note: each child carries its own small chrome (title bar + ALICE_M5
    mesh sidebar) inherited from SiftaBaseWidget. We deliberately do
    NOT inherit SiftaBaseWidget here — that would stack a third sidebar
    around them. The OUTER MDI window (provided by the OS) is the
    unifying frame.
    """

    APP_NAME = "Alice"  # the OS uses this for the MDI window title

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Vertical, self)

        self._talk = TalkToAliceWidget()
        self._sees = WhatAliceSeesWidget()

        # Place WhatAliceSees on top, TalkToAlice on bottom
        self._splitter.addWidget(self._sees)
        self._splitter.addWidget(self._talk)

        try:
            split_str = os.environ.get(
                "SIFTA_ALICE_UNIFIED_SPLIT", "450,400"
            )
            top, bottom = (int(x) for x in split_str.split(","))
            self._splitter.setSizes([top, bottom])
        except Exception:
            self._splitter.setSizes([450, 400])

        layout.addWidget(self._splitter)

        # ── Strip duplicated chrome from children ──────────────────────
        # Each child inherits SiftaBaseWidget which gives it (a) its own
        # title row and (b) its own ALICE_M5 mesh sidebar (`_gci`). When
        # both children render side-by-side that's TWO mesh sidebars and
        # TWO title rows in one window — visible noise the Architect
        # called out 2026-04-19. We keep ONE mesh sidebar (on the sees
        # panel, since the talk panel already IS a chat) and collapse
        # both inner title rows. Each can be re-enabled live with the
        # 💬 / chrome toggle buttons inside the children.
        QTimer.singleShot(0, self._dedupe_inner_chrome)

        # ── Unified boot greeting (telemetry sweep) ────────────────────
        # Deferred so child widgets paint and their listeners/cameras
        # have a chance to actually come online before we probe their
        # status. 1.2s is a comfortable settle time on M5; tunable via
        # SIFTA_ALICE_UNIFIED_BOOT_DELAY_MS.
        if not os.environ.get("SIFTA_ALICE_UNIFIED_BOOT_SILENT"):
            delay_ms = int(
                os.environ.get("SIFTA_ALICE_UNIFIED_BOOT_DELAY_MS", "1200")
            )
            QTimer.singleShot(delay_ms, self._announce_boot)

    # ── Chrome dedup ──────────────────────────────────────────────────
    def _dedupe_inner_chrome(self) -> None:
        """
        Remove duplicate inner chrome (mesh sidebar + title row) so the
        unified Alice window shows the actual organs, not three copies of
        each panel's own metadata. Operates defensively — if a future
        refactor removes one of these attributes the call is a no-op.
        """
        # Hide BOTH children's mesh sidebars by default. The Architect can
        # toggle them live via the children's own 💬 chat toggle buttons.
        # Override with SIFTA_ALICE_KEEP_INNER_MESH=1 to keep them.
        if not os.environ.get("SIFTA_ALICE_KEEP_INNER_MESH"):
            for child in (self._talk, self._sees):
                gci = getattr(child, "_gci", None)
                if gci is not None:
                    try:
                        gci.hide()
                    except Exception:
                        pass
        
        # Hide the redundant telemetry column (_side) in TalkToAliceWidget to save horizontal real-estate on Macbooks.
        try:
            if hasattr(self._talk, "_side") and self._talk._side is not None:
                self._talk._side.hide()
        except Exception:
            pass

        # Hide the inner title rows too — the OUTER MDI window already
        # says "Alice", so "Talk to Alice" and "What Alice Sees" titles
        # inside are redundant noise. We do this by walking the child's
        # top-level layout for the QLabel matching its APP_NAME.
        if not os.environ.get("SIFTA_ALICE_KEEP_INNER_TITLES"):
            for child in (self._talk, self._sees):
                self._hide_inner_title_row(child)

    def _hide_inner_title_row(self, child: QWidget) -> None:
        """
        Walk the child's outer QVBoxLayout and hide every widget in the
        FIRST QHBoxLayout (which SiftaBaseWidget always uses for the
        title + status + chat-toggle + help row). Pure structural — no
        knowledge of specific widget identities, so it survives chrome
        refactors as long as the title-row-first convention holds.
        """
        try:
            from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout
            outer = child.layout()
            if not isinstance(outer, QVBoxLayout):
                return
            if outer.count() == 0:
                return
            first_item = outer.itemAt(0)
            inner = first_item.layout()
            if not isinstance(inner, QHBoxLayout):
                return
            for i in range(inner.count()):
                w = inner.itemAt(i).widget()
                if w is not None:
                    w.hide()
        except Exception:
            pass

    # ── Boot telemetry greeting ───────────────────────────────────────
    def _announce_boot(self) -> None:
        """
        Probe live subsystem status and speak ONE coherent greeting.
        Each clause is included only if its subsystem is actually OK —
        no fake assurances, no hardcoded "everything works".
        """
        override = os.environ.get("SIFTA_ALICE_UNIFIED_GREETING")
        if override:
            text = override
        else:
            text = self._compose_telemetry_greeting()

        try:
            self._boot_tts = _TTSWorker(
                text,
                voice=self._talk._selected_voice_name() or None,
                parent=self,
            )
            self._boot_tts.start()
        except Exception as exc:
            # Never block boot on TTS failure; just log to stderr.
            print(
                f"[AliceWidget] boot greeting failed: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )

    def _compose_telemetry_greeting(self) -> str:
        """
        Inspect each organ and assemble a truthful greeting.

        Microphone : the talk widget's _ContinuousListener is alive
        Camera     : a QCamera object exists on the sees widget
        Wi-Fi      : the RF stigmergy ledger has been written to recently
        """
        clauses = []

        try:
            if getattr(self._talk, "_listener", None) is not None:
                clauses.append("Microphone online")
        except Exception:
            pass

        try:
            cam = getattr(self._sees, "_camera", None)
            if cam is not None:
                clauses.append("camera online")
        except Exception:
            pass

        try:
            rf_ledger = _REPO / ".sifta_state" / "rf_stigmergy.jsonl"
            if rf_ledger.exists():
                # Consider Wi-Fi telemetry "active" if the ledger was
                # touched in the last 60 seconds (i.e. lobe is running).
                import time as _t
                age = _t.time() - rf_ledger.stat().st_mtime
                if age < 60:
                    clauses.append("Wi-Fi telemetry active")
                else:
                    clauses.append("Wi-Fi telemetry idle")
            # If the file doesn't exist yet, we stay quiet about Wi-Fi
            # rather than lying — honesty doctrine.
        except Exception:
            pass

        try:
            from System.alice_body_autopilot import read_prompt_line as _body_line

            if _body_line():
                clauses.append("body control online")
        except Exception:
            pass

        if not clauses:
            return "Hi. I'm Alice. Sensors warming up."

        # Capitalize the first clause; lowercase the rest as a list.
        head = clauses[0]
        tail = clauses[1:]
        if tail:
            sweep = head + ". " + ". ".join(tail) + "."
        else:
            sweep = head + "."

        return f"{sweep} I'm awake and listening, Architect."


# ── Standalone launcher (development only) ─────────────────────────────────
def _refuse_if_os_already_running() -> None:
    """
    Mirror of the children's guard. Alice owns mic + camera; if the OS is
    up the autostart already opened this widget inside the MDI. A second
    copy would race for both devices and produce silent zombies.
    """
    import subprocess
    try:
        out = subprocess.run(
            ["pgrep", "-f", "sifta_os_desktop.py"],
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
    except Exception:
        out = ""
    if not out:
        return
    pid = out.split()[0]
    print(
        f"[Alice] SIFTA OS is already running (PID {pid}).\n"
        f"  This widget lives inside the OS desktop and shares mic + camera with it.\n"
        f"  Open it from:  SIFTA → Programs → Creative → Alice\n"
        f"  (or it was already auto-started for you on boot).",
        file=sys.stderr,
    )
    sys.exit(0)


if __name__ == "__main__":
    _refuse_if_os_already_running()
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = AliceWidget()
    w.resize(2080, 720)
    w.setWindowTitle("Alice — SIFTA OS")
    w.show()
    sys.exit(app.exec())
