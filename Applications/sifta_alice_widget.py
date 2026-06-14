#!/usr/bin/env python3
"""
sifta_alice_widget.py — Alice (unified ear + eye + mesh, single window)
══════════════════════════════════════════════════════════════════════════
Architect doctrine (2026-04-19, C47H):
The Talk-to-Alice and What-Alice-Sees widgets are two organs of the SAME
entity (Alice). They were autostarting as TWO separate MDI windows; the
Architect asked for ONE app. By default the **ear** (talk + mic path) and
**eye** (camera / QCamera) both come online so Alice can inhabit the local
machine. The eye *panel* is collapsed by default; the camera organ keeps
running unless `SIFTA_ALICE_UNIFIED_DEFER_EYE=1` is set for a broken TCC host.

Env overrides (Architect-tunable, no hardcoding):
    SIFTA_ALICE_UNIFIED_DEFER_EYE=0   (default)
        Construct WhatAliceSeesWidget immediately; camera may start on boot.
    SIFTA_ALICE_UNIFIED_DEFER_EYE=1
        Emergency fallback: show a one-tap “Enable camera & vision” strip.

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
    SIFTA_ALICE_UNIFIED_SPLIT="180,700"
        Vertical splitter (eye, talk). Default favors Talk; override e.g. ``200,640``.
    SIFTA_ALICE_UNIFIED_DEFER_EYE=1
        Emergency fallback: camera/vision off until Architect taps Enable.
"""
from __future__ import annotations

"""SIFTA Alice Widget — stigmergic organ for Alice body."""

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
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

# Child widgets — imported AFTER the env-var suppression above.
from Applications.sifta_talk_to_alice_widget import (  # noqa: E402
    TalkToAliceWidget,
    _TTSWorker,
)
from Applications.sifta_what_alice_sees_widget import (  # noqa: E402
    WhatAliceSeesWidget,
)
from System.swarm_camera_unified_field_proof import (  # noqa: E402
    build_camera_unified_field_proof,
)
from System.swarm_app_hardening import record_app_hardening_event  # noqa: E402

APP_HARDENING_ID = "queue-007:sifta_alice_widget"


def _record_alice_widget_hardening(event: str, **details) -> None:
    record_app_hardening_event(
        APP_HARDENING_ID,
        event,
        details=details,
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        controls = QHBoxLayout()
        controls.setContentsMargins(8, 5, 8, 5)
        controls.setSpacing(6)
        self._camera_proof_label = QLabel("eye proof: checking unified field…")
        self._camera_proof_label.setToolTip(
            "Receipt-backed proof from visual_stigmergy, active_eye_identity_frames, "
            "face_detection_events, and kernel_process_table. No fresh receipts means no health claim."
        )
        self._camera_proof_label.setStyleSheet(
            "color:#ffd166; font-weight:700; font-size:11px; padding-left:8px;"
        )
        controls.addWidget(self._camera_proof_label, 1)
        controls.addStretch(1)

        # Architect 2026-05-12 20:25: "Please remove that button and hide eye
        # — I don't know why do I have to hide the eye when I don't even see
        # the eye." Removed the hide/show toggle entirely. The eye panel is
        # always visible. Camera capture, photon hashing, and saliency
        # overlay all run continuously; the user sees the dot view (raw is
        # off by default — see sifta_what_alice_sees_widget.py).
        import os as _os
        self._eye_visible = True
        self._photon_overlay_visible = True
        self._event_ticker_visible = True
        self._raw_video_visible = False  # stigmergic-only (dark canvas + dots)

        # No 'show eye' / 'hide eye' button. The eye is the body — you don't
        # toggle your own eye. Developer chrome (photons/ticker/raw) stays
        # gated behind SIFTA_EYE_DEV_CONTROLS=1 for debugging only.
        _show_dev = _os.environ.get("SIFTA_EYE_DEV_CONTROLS", "0").strip() == "1"

        self._btn_photons = QPushButton("hide photons")
        self._btn_photons.setToolTip("Hide/show photon overlay only; camera and ledgers remain real.")
        self._btn_photons.setMinimumWidth(120)
        self._btn_photons.clicked.connect(self._toggle_photon_overlay)
        self._btn_photons.setVisible(_show_dev)
        controls.addWidget(self._btn_photons)

        self._btn_events = QPushButton("hide ticker")
        self._btn_events.setToolTip("Hide/show the live ledger ticker inside the eye monitor.")
        self._btn_events.setMinimumWidth(110)
        self._btn_events.clicked.connect(self._toggle_event_ticker)
        self._btn_events.setVisible(_show_dev)
        controls.addWidget(self._btn_events)

        # `show raw` is developer chrome (Architect 2026-05-11 22:43:
        # "WHAT IS THAT FOR WHY DO I NEED TO CLICK?"). The raw-vs-stigmergic
        # toggle stays available but is hidden from the toolbar unless
        # SIFTA_EYE_DEV_CONTROLS=1. The button is still constructed so
        # _sync_eye_controls / _toggle_raw_video don't crash on attribute
        # access.
        self._btn_raw = QPushButton("hide raw")
        self._btn_raw.setToolTip(
            "Stigmergic-only mode: hide raw camera, show only the entropy/saliency overlay.\n"
            "Real photons are still hashed. Just no mirror."
        )
        self._btn_raw.setMinimumWidth(100)
        self._btn_raw.clicked.connect(self._toggle_raw_video)
        self._btn_raw.setVisible(_show_dev)
        controls.addWidget(self._btn_raw)

        layout.addLayout(controls)

        # ── Eye-behind-chat overlay layout ─────────────────────────────────
        # Architect 2026-05-11 22:43: "WHAT IF THE EYES ARE INSIDE THE CHAT
        # WINDOW BEHIND THE TEXT?" Yes — Qt does this with QStackedLayout
        # in StackAll mode. The eye widget fills the panel; the talk
        # widget sits on top with a translucent dark backing so the camera
        # bleeds through behind the conversation. One pane, two organs,
        # zero splitter to grab.
        #
        # Env kill-switch: SIFTA_ALICE_EYE_OVERLAY=0 reverts to the old
        # vertical splitter for users who hate the new layout.
        # SIFTA_EYE_CHAT_OVERLAY_ALPHA (0..255, default 165 ≈ 65% opaque)
        # dials how much eye shows through the chat panel.
        _overlay_on = os.environ.get(
            "SIFTA_ALICE_EYE_OVERLAY", "1"
        ).strip().lower() not in ("0", "false", "no", "off")

        self._talk = TalkToAliceWidget()
        # ALICE IS FREE — camera starts on boot by default.
        # Set SIFTA_ALICE_UNIFIED_DEFER_EYE=1 ONLY if macOS TCC is broken
        # on this machine and camera init would crash the boot.
        defer_raw = os.environ.get("SIFTA_ALICE_UNIFIED_DEFER_EYE", "0").strip().lower()
        self._defer_eye = defer_raw not in ("0", "false", "no", "")
        self._sees: Optional[WhatAliceSeesWidget] = None
        self._eye_placeholder: Optional[QWidget] = None

        if self._defer_eye:
            self._eye_placeholder = QWidget(self)
            ph = QVBoxLayout(self._eye_placeholder)
            ph.setContentsMargins(24, 24, 24, 24)
            lbl = QLabel(
                "Vision / camera is off at boot.\n"
                "Enable when you want Alice to open the camera (macOS may show TCC)."
            )
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #a9b1d6; font-size: 14px;")
            ph.addWidget(lbl)
            btn = QPushButton("Enable camera & vision")
            btn.setStyleSheet(
                "QPushButton { background: #3865be; color: #ffffff; font-weight: 700;"
                " padding: 10px 18px; border-radius: 8px; }"
                "QPushButton:hover { background: #4f7fe2; }"
            )
            btn.clicked.connect(self._enable_vision)
            ph.addWidget(btn)
            ph.addStretch()
        else:
            self._sees = WhatAliceSeesWidget()

        # Used by toggle code regardless of layout mode.
        self._splitter = None  # legacy attribute; set only if overlay disabled
        self._overlay = None
        self._overlay_layout = None
        self._overlay_on = _overlay_on

        if _overlay_on:
            # Stack: eye (bottom) + talk (top with translucent backing).
            self._overlay = QWidget(self)
            self._overlay_layout = QStackedLayout(self._overlay)
            self._overlay_layout.setStackingMode(
                QStackedLayout.StackingMode.StackAll
            )
            self._overlay_layout.setContentsMargins(0, 0, 0, 0)

            _eye_widget = self._sees if self._sees is not None else self._eye_placeholder
            if _eye_widget is not None:
                self._overlay_layout.addWidget(_eye_widget)
            # Talk on top — apply a translucent dark backing through a palette
            # so the eye widget below is visible around the chat scroll area.
            try:
                _alpha = int(os.environ.get("SIFTA_EYE_CHAT_OVERLAY_ALPHA", "165"))
            except Exception:
                _alpha = 165
            _alpha = max(60, min(230, _alpha))
            self._talk.setAutoFillBackground(True)
            _pal = self._talk.palette()
            _pal.setColor(QPalette.ColorRole.Window, QColor(8, 12, 20, _alpha))
            self._talk.setPalette(_pal)
            self._overlay_layout.addWidget(self._talk)
            # CRITICAL z-order fix (2026-05-11 23:01): QStackedLayout in
            # StackAll mode paints the *current* widget on top. Without
            # this line, the eye (added first → currentIndex 0) hides the
            # whole chat. Make the talk the current widget so chat reads
            # over the eye.
            self._overlay_layout.setCurrentWidget(self._talk)
            self._talk.raise_()
            layout.addWidget(self._overlay)
        else:
            # Legacy splitter layout. Kept reachable via env kill-switch.
            self._splitter = QSplitter(Qt.Orientation.Vertical, self)
            self._splitter.setHandleWidth(8)
            self._splitter.setChildrenCollapsible(False)
            self._splitter.setStyleSheet(
                "QSplitter::handle:vertical { "
                "background: rgba(255, 179, 0, 0.35); margin: 1px 8px; border-radius: 2px; "
                "}"
            )
            _eye_widget = self._sees if self._sees is not None else self._eye_placeholder
            if _eye_widget is not None:
                self._splitter.addWidget(_eye_widget)
            self._splitter.addWidget(self._talk)
            try:
                split_str = os.environ.get(
                    "SIFTA_ALICE_UNIFIED_SPLIT", "160,640"
                )
                top, bottom = (int(x) for x in split_str.split(","))
                self._splitter.setSizes([top, bottom])
            except Exception:
                self._splitter.setSizes([180, 700])
            layout.addWidget(self._splitter)

        # Apply the boot-time eye-visibility default — collapse the eye
        # pane so the desktop is the dominant view. Architect 2026-05-12.
        self._apply_eye_visibility()
        self._apply_eye_subcontrols()
        self._sync_eye_controls()

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
        self._camera_proof_timer = QTimer(self)
        self._camera_proof_timer.setInterval(2000)
        self._camera_proof_timer.timeout.connect(self._refresh_camera_proof)
        self._camera_proof_timer.start()
        QTimer.singleShot(250, self._refresh_camera_proof)

        # ── Unified boot greeting (telemetry sweep) ────────────────────
        # Deferred so child widgets paint and their listeners/mic
        # have a chance to settle. Camera is probed only if the eye is on.
        if not os.environ.get("SIFTA_ALICE_UNIFIED_BOOT_SILENT"):
            delay_ms = int(
                os.environ.get("SIFTA_ALICE_UNIFIED_BOOT_DELAY_MS", "1200")
            )
            QTimer.singleShot(delay_ms, self._announce_boot)

    def _refresh_camera_proof(self) -> None:
        """Render the desktop-visible unified-field eye proof."""
        try:
            now = __import__("time").time()
            last_ts = float(getattr(self, "_last_camera_proof_receipt_ts", 0.0) or 0.0)
            proof = build_camera_unified_field_proof(
                write_receipt=(now - last_ts) >= 30.0
            )
            if (now - last_ts) >= 30.0:
                self._last_camera_proof_receipt_ts = now
            text = proof.summary
            if proof.device:
                text = f"{text} · {proof.device}"
            if proof.frame_sha8:
                text = f"{text} · sha={proof.frame_sha8}"
            self._camera_proof_label.setText(text)
            color = "#00c853" if proof.status == "OWNER_RECOGNIZED" else (
                "#ffd166" if proof.ok else "#ff5c8a"
            )
            self._camera_proof_label.setStyleSheet(
                f"color:{color}; font-weight:700; font-size:11px; padding-left:8px;"
            )
            self._camera_proof_label.setToolTip(
                f"{proof.truth_label}\n"
                f"status={proof.status}\n"
                f"receipt={proof.receipt_id}\n"
                f"connection_state={proof.connection_state}\n"
                f"disconnect_reasons={','.join(proof.disconnect_reasons) or 'none'}\n"
                f"face_age={proof.face_age_s}\n"
                f"frame_age={proof.frame_age_s} fresh={proof.frame_fresh}\n"
                f"visual_age={proof.visual_age_s} fresh={proof.visual_fresh}\n"
                f"vision_health={proof.vision_health}\n"
                f"vision_heartbeat_age={proof.vision_heartbeat_age_s} fresh={proof.vision_fresh}"
            )
        except Exception as exc:
            self._camera_proof_label.setText(f"eye proof failed: {type(exc).__name__}")
            self._camera_proof_label.setStyleSheet(
                "color:#ff5c8a; font-weight:700; font-size:11px; padding-left:8px;"
            )

    def _enable_vision(self) -> None:
        """Construct the eye organ on demand so QCamera never starts implicitly."""
        if self._sees is not None or self._eye_placeholder is None:
            return
        self._sees = WhatAliceSeesWidget()
        if self._overlay_on and self._overlay_layout is not None:
            # Replace the placeholder inside the stacked overlay.
            idx = self._overlay_layout.indexOf(self._eye_placeholder)
            if idx < 0:
                idx = 0
            self._overlay_layout.removeWidget(self._eye_placeholder)
            # Re-insert eye at the bottom of the stack (index 0).
            self._overlay_layout.insertWidget(0, self._sees)
        elif self._splitter is not None:
            idx = self._splitter.indexOf(self._eye_placeholder)
            if idx < 0:
                idx = 0
            self._splitter.replaceWidget(idx, self._sees)
        self._eye_placeholder.deleteLater()
        self._eye_placeholder = None
        self._apply_eye_visibility()
        self._apply_eye_subcontrols()
        QTimer.singleShot(0, self._dedupe_inner_chrome)

    def _visible_eye_widget(self) -> Optional[QWidget]:
        return self._sees if self._sees is not None else self._eye_placeholder

    def _toggle_eye_panel(self) -> None:
        """Defanged 2026-05-12 20:25 — Architect removed the hide-eye toggle.
        Method kept for backward compat in case anything still calls it.
        Always forces the eye visible — does NOT flip the state."""
        self._eye_visible = True
        self._apply_eye_visibility()
        self._sync_eye_controls()

    def _toggle_photon_overlay(self) -> None:
        self._photon_overlay_visible = not self._photon_overlay_visible
        self._apply_eye_subcontrols()
        self._sync_eye_controls()

    def _toggle_event_ticker(self) -> None:
        self._event_ticker_visible = not self._event_ticker_visible
        self._apply_eye_subcontrols()
        self._sync_eye_controls()

    def _toggle_raw_video(self) -> None:
        self._raw_video_visible = not self._raw_video_visible
        self._apply_eye_subcontrols()
        self._sync_eye_controls()

    def _apply_eye_visibility(self) -> None:
        eye = self._visible_eye_widget()
        if eye is None:
            return
        if self._overlay_on and self._overlay_layout is not None:
            # Architect 2026-05-12 17:35: "HIDE EYE SHOW EYE DOES NOTHING".
            # Cause: QStackedLayout in StackAll mode renders every child
            # regardless of per-widget setVisible(False) — Qt manages
            # visibility itself. So we evacuate the eye from the layout
            # entirely when hiding, and re-insert it at index 0 (behind
            # talk) when showing. Talk stays current widget either way.
            if self._eye_visible:
                if self._overlay_layout.indexOf(eye) < 0:
                    self._overlay_layout.insertWidget(0, eye)
                eye.setVisible(True)
                # Keep talk painted on top
                if hasattr(self, "_talk") and self._talk is not None:
                    self._overlay_layout.setCurrentWidget(self._talk)
                    self._talk.raise_()
            else:
                # Pull the eye out of the stack — nothing left under talk.
                if self._overlay_layout.indexOf(eye) >= 0:
                    self._overlay_layout.removeWidget(eye)
                eye.setParent(None)
                eye.setVisible(False)
            return
        # Legacy splitter layout (overlay disabled via env).
        eye.setVisible(self._eye_visible)
        if self._splitter is not None:
            # Eye small, chat big (Architect 2026-05-11 22:43).
            self._splitter.setSizes(
                [160, 640] if self._eye_visible else [0, 800]
            )

    def _apply_eye_subcontrols(self) -> None:
        if self._sees is None:
            return
        if hasattr(self._sees, "set_photon_overlay_visible"):
            self._sees.set_photon_overlay_visible(self._photon_overlay_visible)
        if hasattr(self._sees, "set_event_ticker_visible"):
            self._sees.set_event_ticker_visible(self._event_ticker_visible)
        if hasattr(self._sees, "set_raw_video_visible"):
            self._sees.set_raw_video_visible(self._raw_video_visible)

    def _sync_eye_controls(self) -> None:
        if hasattr(self, "_btn_eye"):
            self._btn_eye.setText("hide eye" if self._eye_visible else "show eye")
        if hasattr(self, "_btn_photons"):
            self._btn_photons.setText(
                "hide photons" if self._photon_overlay_visible else "show photons"
            )
        if hasattr(self, "_btn_events"):
            self._btn_events.setText(
                "hide ticker" if self._event_ticker_visible else "show ticker"
            )
        if hasattr(self, "_btn_raw"):
            self._btn_raw.setText(
                "hide raw" if self._raw_video_visible else "show raw"
            )

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
            _kids = [self._talk]
            if self._sees is not None:
                _kids.append(self._sees)
            for child in _kids:
                gci = getattr(child, "_gci", None)
                if gci is not None:
                    try:
                        gci.hide()
                    except Exception as exc:
                        _record_alice_widget_hardening(
                            "child_mesh_sidebar_hide_failed",
                            error_type=type(exc).__name__,
                            child=type(child).__name__,
                        )
        
        # Hide the redundant telemetry column (_side) in TalkToAliceWidget to save horizontal real-estate on Macbooks.
        try:
            if hasattr(self._talk, "_side") and self._talk._side is not None:
                self._talk._side.hide()
        except Exception as exc:
            _record_alice_widget_hardening(
                "talk_telemetry_column_hide_failed",
                error_type=type(exc).__name__,
            )

        # Hide the inner title rows too — the OUTER MDI window already
        # says "Alice", so "Talk to Alice" and "What Alice Sees" titles
        # inside are redundant noise. We do this by walking the child's
        # top-level layout for the QLabel matching its APP_NAME.
        if not os.environ.get("SIFTA_ALICE_KEEP_INNER_TITLES"):
            for child in [self._talk] + ([self._sees] if self._sees is not None else []):
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
        except Exception as exc:
            _record_alice_widget_hardening(
                "inner_title_row_hide_failed",
                error_type=type(exc).__name__,
                child=type(child).__name__,
            )

    # ── Boot telemetry greeting ───────────────────────────────────────
    def _announce_boot(self) -> None:
        """
        Boot announcement — DISABLED by default (George 2026-05-26).

        The canned telemetry line ("…I'm awake and listening, Architect.") was
        robotic and not Alice. By default Alice now boots in silence; if and
        when she has something to say, the LLM cortex authors it on the first
        real turn, grounded by the memory card. If you specifically want a
        boot greeting, set ``SIFTA_ALICE_UNIFIED_GREETING="your text"`` and
        it will be spoken verbatim.
        """
        override = os.environ.get("SIFTA_ALICE_UNIFIED_GREETING")
        if not override:
            return  # silent boot — no canned line
        try:
            self._boot_tts = _TTSWorker(
                override,
                voice=self._talk._selected_voice_name() or None,
                parent=self,
            )
            self._boot_tts.start()
        except Exception as exc:
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
        except Exception as exc:
            _record_alice_widget_hardening(
                "microphone_telemetry_probe_failed",
                error_type=type(exc).__name__,
            )

        try:
            sees = self._sees
            if sees is not None:
                cam = getattr(sees, "_camera", None)
                if cam is not None:
                    clauses.append("camera online")
        except Exception as exc:
            _record_alice_widget_hardening(
                "camera_telemetry_probe_failed",
                error_type=type(exc).__name__,
            )

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
        except Exception as exc:
            _record_alice_widget_hardening(
                "wifi_telemetry_probe_failed",
                error_type=type(exc).__name__,
            )

        try:
            from System.alice_body_autopilot import read_prompt_line as _body_line

            if _body_line():
                clauses.append("body control online")
        except Exception as exc:
            _record_alice_widget_hardening(
                "body_control_probe_failed",
                error_type=type(exc).__name__,
            )

        if not clauses:
            try:
                from System.swarm_kernel_identity import ai_lineage_title

                return f"Hi. I'm {ai_lineage_title()}. Sensors warming up."
            except Exception:
                return "Hi. I'm the local SIFTA runtime. Sensors warming up."

        # Capitalize the first clause; lowercase the rest as a list.
        head = clauses[0]
        tail = clauses[1:]
        if tail:
            sweep = head + ". " + ". ".join(tail) + "."
        else:
            sweep = head + "."

        return f"{sweep} I'm awake and listening, Architect."

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        try:
            from System.swarm_app_focus import publish_focus
            publish_focus(self.APP_NAME, "User is interacting with Alice Widget")
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        """Stop the boot-greeting TTS thread and close child widgets cleanly."""
        tts = getattr(self, "_boot_tts", None)
        if tts is not None:
            try:
                if tts.isRunning():
                    # Use stop() which kills the subprocess first, then waits for the thread.
                    if hasattr(tts, "stop"):
                        tts.stop()
                    else:
                        tts.terminate()
                        tts.wait(2000)
            except Exception:
                pass
            self._boot_tts = None
        # Delegate to children so their own closeEvent runs
        for child_attr in ("_talk", "_sees"):
            child = getattr(self, child_attr, None)
            if child is not None:
                try:
                    child.close()
                except Exception:
                    pass
        super().closeEvent(event)




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
