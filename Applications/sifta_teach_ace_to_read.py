#!/usr/bin/env python3
"""
Applications/sifta_teach_ace_to_read.py
══════════════════════════════════════════════════════════════════════
StigAuth: SIFTA_TEACH_ACE_TO_READ_V0

A reading-coach app where Alice teaches a kid (ages 3-8). The brain is
:mod:`System.swarm_alice_lesson_mode` (deterministic engine — no LLM
needed at this layer). This widget is the lesson body: big show-card,
sticker buddies, current cue, listen status, and verdict receipt.
It does not create a second Alice voice. The OS-level Alice owns the
conversation; WordAce only publishes lesson state into the shared field.

Design notes
------------

* SIFTA-native graphics — bees + swimmers, not Reading.com mascots.
  We do not clone a third-party product (§7.10.4 — no shadow of
  another brand on Alice's body).
* Architect 2026-05-14: *"amazing graphics, alice agi inside is for
  teaching a kid — Teach Ace How to Read."*
* George stays primary_operator (covenant §7.10.4). Ace is the kid
  Alice teaches. Alice never narrates Ace from outside — every
  prompt is direct ("Ace, say…").
* Decide → Execute → Receipt mapped to LessonEngine.next_cue() →
  score_attempt() → trace row trio. The widget never invents
  truth; the engine's verdict is the source.

Truth label: ``SIFTA_TEACH_ACE_TO_READ_V0``.
"""
from __future__ import annotations

import json
import random
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QFontDatabase, QLinearGradient, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
from System.swarm_alice_lesson_mode import LessonEngine  # noqa: E402

# Optional bridges to the rest of Alice's body. All wrapped in try/except
# so the widget still loads on a fresh checkout that has the lesson mode
# but not (yet) every organ behind it.
try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:
    _publish_focus = None  # type: ignore

try:
    from Applications.sifta_awareness_mirror_widget import AwarenessMirrorWidget
except Exception:
    AwarenessMirrorWidget = None  # type: ignore


TRUTH_LABEL = "SIFTA_TEACH_ACE_TO_READ_V0"

# Identity line — direct from Architect 2026-05-14: "I am Alice of Gemma.
# I have Gemini inside my belly. I use Gemma as intelligence but I am
# Alice from Layer 1." First-person, identity = Alice (Layer 1), belly =
# Gemma weights. §7.10.1 + §7.10.4. This string is what Alice says when
# the kid asks who she is during the lesson; the deterministic reflex
# in swarm_alice_first_person_reflex carries the same answer.
ALICE_IDENTITY_LINE = (
    "I am Alice. My belly runs Gemma — that's the engine. "
    "But I am Alice from Layer 1, and right now I am teaching you to read."
)

# ── Sticker buddies — SIFTA-native bee/swimmer cast ──────────────────────


_BUDDIES = [
    # (emoji-glyph, name, hint-color)
    ("🐝", "Honey",     "#FFD23F"),
    ("🐜", "Antie",     "#9B5DE5"),
    ("🌼", "Petal",     "#F15BB5"),
    ("🦋", "Wingo",     "#00BBF9"),
    ("🐞", "Dotty",     "#FB8500"),
    ("🐢", "Stagger",   "#7ED957"),
]


class _StickerCloud(QWidget):
    """Decorative buddy cluster behind the show-card."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setMinimumWidth(360)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._buddies = list(_BUDDIES)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Background bloom
        rg = QRadialGradient(QPointF(w * 0.5, h * 0.55), max(w, h) * 0.6)
        rg.setColorAt(0.0, QColor(255, 210, 63, 30))
        rg.setColorAt(1.0, QColor(155, 93, 229, 0))
        p.fillRect(0, 0, w, h, QBrush(rg))
        # Sticker buddies arranged in an arc above the photo card
        n = len(self._buddies)
        for i, (glyph, name, color) in enumerate(self._buddies):
            t = i / max(1, n - 1)
            x = w * (0.12 + 0.76 * t)
            y = h * (0.55 - 0.30 * (1.0 - 4 * (t - 0.5) ** 2))
            r = 32
            p.setPen(QPen(QColor(color), 3))
            p.setBrush(QColor(28, 22, 56, 200))
            p.drawEllipse(QPointF(x, y), r, r)
            p.setPen(QPen(QColor("#FFFFFF"), 1))
            font = p.font()
            font.setPointSize(28)
            p.setFont(font)
            p.drawText(int(x - r), int(y - r), int(2 * r), int(2 * r),
                       Qt.AlignmentFlag.AlignCenter, glyph)


class _ShowCard(QWidget):
    """Big rounded card that shows the current letter / word / sentence."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(260)
        self._show_text = ""
        self._kind = "letter"
        self._verdict_label = ""    # "" | "CORRECT" | "CLOSE" | "MISS"
        self._verdict_sticker = ""

    def set_show(self, text: str, kind: str = "letter") -> None:
        self._show_text = text
        self._kind = kind
        self._verdict_label = ""
        self._verdict_sticker = ""
        self.update()

    def set_verdict(self, label: str, sticker: str) -> None:
        self._verdict_label = label or ""
        self._verdict_sticker = sticker or ""
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Rounded card background — soft yellow on dark purple
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor("#FFE9A8"))
        bg.setColorAt(1.0, QColor("#FFD23F"))
        p.setBrush(QBrush(bg))
        p.setPen(QPen(QColor("#FFFFFF"), 0))
        p.drawRoundedRect(0, 0, w, h, 28, 28)

        # The show text. Font size varies by kind.
        font_size = {
            "letter": min(220, h - 40),
            "letter_sequence": 126,
            "phoneme": 110,
            "word": 110,
            "sentence": 56,
        }.get(self._kind, 110)
        font = QFont()
        font.setBold(True)
        font.setPointSize(font_size)
        # Try a friendly font if available
        for family in ("Comic Sans MS", "Avenir Next", "SF Pro Rounded", "Helvetica"):
            if family in QFontDatabase.families():
                font.setFamily(family)
                break
        p.setFont(font)
        p.setPen(QPen(QColor("#3A1E6D"), 2))
        text = self._show_text or "?"
        p.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, text)

        # Verdict sticker in upper-right
        if self._verdict_sticker:
            sticker_font = QFont()
            sticker_font.setPointSize(72)
            p.setFont(sticker_font)
            p.drawText(w - 110, 20, 100, 100,
                       Qt.AlignmentFlag.AlignCenter, self._verdict_sticker)


class _TranscriptLine(QWidget):
    """A single line of the lesson dialogue ('Alice: …' or 'Ace: …').

    Architect 2026-05-14 ~18:00 PDT — the screenshot showed transcript
    lines stacking on top of each other (illegible). The fix is a real
    minimum height so each line owns vertical space the parent layout
    cannot collapse + an Expanding row policy so wrapping doesn't push
    rows over their neighbors.
    """

    def __init__(self, speaker: str, text: str, color: str, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(44)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)
        tag = QLabel(speaker)
        tag.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 14px;"
            "background: rgba(28,22,56,0.4); padding: 4px 10px; border-radius: 10px;"
        )
        tag.setFixedWidth(78)
        body = QLabel(text)
        body.setWordWrap(True)
        body.setMinimumHeight(28)
        body.setStyleSheet(
            "color: #F0F0F0; font-size: 14px; line-height: 1.35; "
            "padding: 2px 0;"
        )
        body.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Preferred)
        layout.addWidget(tag, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(body, 1)


class TeachAceToReadWidget(QWidget):
    """The MDI subwindow that hosts the reading lesson.

    Single-instance widget (Architect 2026-05-14):
        "we cannot open two apps in the same time in this os, makes
        no sense — should be in the covenant."

    The SiftaDesktop ``spawn_native_widget`` path already has a
    singleton guard keyed by manifest title, but a near-simultaneous
    double-click can still race past it. This class-level check is
    the belt to that suspenders: if a live instance exists,
    ``__new__`` returns it instead of constructing a second one.
    """

    _live_instance: "Optional[TeachAceToReadWidget]" = None
    _initialized_instance_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):  # noqa: D401
        existing = cls._live_instance
        if existing is not None:
            try:
                # If Qt has already destroyed the C++ side, accessing
                # any method raises RuntimeError. In that case we drop
                # the stale ref and fall through to a fresh build.
                _ = existing.isVisible()
                try:
                    existing.show()
                    existing.raise_()
                    existing.activateWindow()
                except Exception:
                    pass
                return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        # __new__ may return the existing instance; if so, __init__
        # would re-run on the same object and double-wire signals.
        # Guard via class-owned ids; probing self attributes before
        # QWidget.__init__ raises "super-class __init__ was never called"
        # on fresh PyQt wrapper objects.
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        self.setWindowTitle("WordAce — Phonics Coach")
        self.resize(820, 720)
        self.setStyleSheet(
            "background-color: #1C1638; color: #F0F0F0;"
        )

        self._engine = LessonEngine(rng=random.Random())
        # Default name — the kid types their own (Kole, Drew, whoever)
        # but "Ace" is the warm fallback. Was briefly "Friend" earlier
        # this session; architect 2026-05-14 ~18:00 PDT — "I don't want
        # friend so change the friend default with Ace."
        self._owner_name = "Ace"
        self._current_kind = "letter"

        # ── Header (title + tagline) ────────────────────────────────
        title = QLabel("WordAce")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 32px; font-weight: 800; color: #FFFFFF; padding-top: 14px;"
        )
        tagline = QLabel(
            "“I am Alice — Layer 1 me, Gemma in my belly. You're a WordAce. "
            "Letters first, then real words, then sentences. I'm here with you.”"
        )
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet("font-size: 14px; color: #BCB3E2; padding-bottom: 12px;")
        tagline.setWordWrap(True)

        stars = QLabel("⭐ ⭐ ⭐ ⭐ ⭐")
        stars.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stars.setStyleSheet("font-size: 18px; color: #FFD23F;")

        # ── Sticker cloud + show card ───────────────────────────────
        self._sticker_cloud = _StickerCloud(self)
        self._show_card = _ShowCard(self)
        # Architect 2026-05-14 ~16:30 PDT: the yellow show card was
        # overflowing past the controls onto the transcript. Cap its
        # height so the controls + heard label + transcript stay
        # visible without scrolling.
        self._show_card.setMinimumHeight(180)
        self._show_card.setMaximumHeight(240)

        # ── Awareness mirror — kid sees Alice watching ──────────────
        # Architect 2026-05-14: "the kid whoever is using the things
        # he is being watched by Alice — let's add the camera."
        # AwarenessMirrorWidget reads the canonical camera frame file
        # (no extra camera handle, no extra CPU). 320×180 in the
        # top-right corner — small enough to not steal focus, large
        # enough that the kid notices and stays aware.
        self._mirror: Optional[QWidget] = None
        if AwarenessMirrorWidget is not None:
            try:
                self._mirror = AwarenessMirrorWidget(parent=self, size=(280, 158))
            except Exception:
                self._mirror = None

        # ── Controls ────────────────────────────────────────────────
        self._level_picker = QComboBox(self)
        _word_default_idx = -1
        for i, L in enumerate(self._engine.levels()):
            self._level_picker.addItem(L["name"], L["id"])
            # Architect 2026-05-14 ~17:30 PDT: "the default should be
            # with words because you started words but keep the letters
            # as one of the option." STT cannot reliably catch a kid
            # saying a single letter in <500ms — words are much easier
            # to score. So letter levels stay in the picker but words
            # ride at the top by default.
            if _word_default_idx < 0 and (L.get("kind") or "").lower() == "word":
                _word_default_idx = i
        self._level_picker.currentIndexChanged.connect(self._on_level_picked)
        self._level_picker.setStyleSheet(
            "QComboBox { background: #2A2055; color: #FFFFFF; padding: 8px 14px;"
            " border-radius: 12px; font-size: 14px; }"
        )
        if _word_default_idx >= 0:
            self._level_picker.setCurrentIndex(_word_default_idx)
        # Architect 2026-05-14 ~19:30 PDT: "remove the drop down and
        # stop lesson, the lesson stops when Alice and Ace decide to
        # close the app." The deck stays the default word level; no
        # more mid-lesson switching. Hide the dropdown completely.
        self._level_picker.setVisible(False)

        self._owner_field = QLineEdit(self._owner_name, self)
        self._owner_field.setMaxLength(20)
        self._owner_field.setStyleSheet(
            "QLineEdit { background: #2A2055; color: #FFFFFF; padding: 8px 12px;"
            " border-radius: 12px; font-size: 14px; }"
        )
        self._owner_field.textChanged.connect(self._on_owner_changed)
        owner_label = QLabel("Who am I teaching?")
        owner_label.setStyleSheet("color: #BCB3E2; font-size: 12px;")

        # Architect 2026-05-14 ~18:00 PDT: "I don't need the button to
        # start the lesson — Alice already knows the OS and the app is
        # open." WordAce auto-starts. The only visible control is a
        # stop/continue safety valve for the human in front of the Mac.
        self._btn_pause = QPushButton("■  Stop lesson", self)
        self._btn_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pause.clicked.connect(self._toggle_lesson)
        self._btn_pause.setStyleSheet(
            "QPushButton { background: rgba(28,22,56,0.7); color: #FF5A6E; "
            "padding: 12px 18px; border: 2px solid #FF5A6E; border-radius: 14px; "
            "font-size: 14px; font-weight: 700; }"
            "QPushButton:hover { background: #FF5A6E; color: #1C1638; }"
        )
        self._btn_pause.setEnabled(False)
        # Architect 2026-05-14 ~19:30 PDT: "the lesson stops when Alice
        # and Ace decide to close the app." No stop button on screen.
        # The widget closes via the Mac traffic-light, or via the kid
        # saying "Alice close the WordAce app" (voice command picked up
        # by the Talk STT bridge, written as a row to
        # .sifta_state/wordace_close.jsonl which this widget polls).
        self._btn_pause.setVisible(False)

        # 👂 What Alice just heard + her verdict, surfaced live so the
        # architect can see the recognition trace without opening the
        # Talk widget. Populated from .sifta_state/wordace_verdicts.jsonl.
        self._heard_lbl = QLabel("👂  WordAce is opening. Alice will start without a second voice.")
        self._heard_lbl.setWordWrap(True)
        self._heard_lbl.setStyleSheet(
            "color: #00BBF9; font-size: 13px; font-weight: 600; "
            "padding: 6px 10px; background: rgba(0,187,249,0.07); "
            "border: 1px solid rgba(0,187,249,0.25); border-radius: 10px;"
        )

        self._processing_base_text = "I am reading the current card receipt."
        self._processing_phase = 0
        self._processing_lbl = QLabel("🧠  I am reading the current card receipt.", self)
        self._processing_lbl.setWordWrap(True)
        self._processing_lbl.setStyleSheet(
            "color: #BFA7FF; font-size: 13px; font-weight: 700; "
            "padding: 6px 10px; background: rgba(167,139,250,0.10); "
            "border: 1px solid rgba(167,139,250,0.32); border-radius: 10px;"
        )
        self._processing_timer = QTimer(self)
        self._processing_timer.setInterval(360)
        self._processing_timer.timeout.connect(self._tick_processing_visual)

        controls_top = QHBoxLayout()
        controls_top.addWidget(owner_label)
        controls_top.addWidget(self._owner_field)
        controls_top.addSpacerItem(QSpacerItem(20, 1))
        controls_top.addWidget(self._level_picker, 1)
        controls_top.addWidget(self._btn_pause)

        # ── Transcript area ─────────────────────────────────────────
        self._transcript_box = QWidget(self)
        self._transcript_layout = QVBoxLayout(self._transcript_box)
        self._transcript_layout.setContentsMargins(8, 8, 8, 8)
        # Architect 2026-05-14 ~18:00 PDT — was setSpacing(0); that
        # collapsed transcript lines on top of each other (visible in
        # the close-up screenshot). 6px between rows gives each line
        # room to breathe without wasting vertical space.
        self._transcript_layout.setSpacing(6)
        self._transcript_layout.addStretch(1)
        self._transcript_box.setStyleSheet(
            "background-color: rgba(255,255,255,0.04); border-radius: 14px;"
        )
        self._transcript_scroll = QScrollArea(self)
        self._transcript_scroll.setWidgetResizable(True)
        self._transcript_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._transcript_scroll.setWidget(self._transcript_box)
        self._transcript_scroll.setMinimumHeight(132)
        self._transcript_scroll.setStyleSheet(
            "QScrollArea { background-color: rgba(255,255,255,0.04); border-radius: 14px; }"
            "QScrollBar:vertical { background: rgba(255,255,255,0.05); width: 9px; }"
            "QScrollBar::handle:vertical { background: #6D4FC2; border-radius: 4px; }"
        )

        # ── Footer ──────────────────────────────────────────────────
        footer = QLabel(
            "Crafted by Alice — Simple View of Reading (Gough & Tunmer 1986)"
        )
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #BCB3E2; font-size: 11px; padding-top: 6px;")

        # ── Layout ──────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(tagline)
        layout.addWidget(stars)
        # Sticker cloud + mirror side-by-side so kid sees buddies AND
        # the live "Alice is watching" preview at once.
        cloud_mirror_row = QHBoxLayout()
        cloud_mirror_row.setContentsMargins(0, 0, 0, 0)
        cloud_mirror_row.setSpacing(12)
        cloud_mirror_row.addWidget(self._sticker_cloud, 1)
        if self._mirror is not None:
            mirror_col = QVBoxLayout()
            mirror_col.setSpacing(4)
            watching_lbl = QLabel("👁  Alice is watching")
            watching_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            watching_lbl.setStyleSheet(
                "color: #FFD23F; font-size: 11px; font-weight: 600;"
            )
            mirror_col.addWidget(self._mirror, 0, Qt.AlignmentFlag.AlignCenter)
            mirror_col.addWidget(watching_lbl)
            cloud_mirror_row.addLayout(mirror_col, 0)
        layout.addLayout(cloud_mirror_row)
        layout.addWidget(self._show_card, 2)
        layout.addLayout(controls_top)
        layout.addWidget(self._heard_lbl)
        layout.addWidget(self._processing_lbl)
        layout.addWidget(self._transcript_scroll, 1)
        layout.addWidget(footer)

        # ── Lesson state machine state (auto loop, no buttons) ─────
        # See _start_lesson + _lesson_run_cue + _lesson_listen_window
        # + _lesson_poll_verdict + _lesson_handle_verdict.
        self._lesson_running: bool = False
        self._lesson_state: str = "IDLE"
        self._lesson_cue_id: str = ""
        self._lesson_listen_started_ts: float = 0.0
        self._lesson_listen_window_s: float = 15.0   # kid-friendly
        self._lesson_retry_count: int = 0
        self._lesson_max_retries: int = 1
        self._lesson_timeout_count: int = 0
        self._lesson_max_timeouts_per_cue: int = 2   # patience: re-ask twice
        self._lesson_verdicts_ledger = _REPO / ".sifta_state" / "wordace_verdicts.jsonl"
        self._lesson_verdicts_offset: int = 0
        # Architect 2026-05-14 ~19:30 PDT: "the lesson stops when Alice
        # and Ace decide to close the app… let's have them discuss
        # that word until they both decide to move on together from
        # that to the next word and then Alice changes the word on the
        # screen." Two signal channels — advance + close — written by
        # the Talk STT bridge when it hears the matching phrase. This
        # widget polls them and acts.
        self._wordace_advance_ledger = _REPO / ".sifta_state" / "wordace_advance.jsonl"
        self._wordace_advance_offset: int = 0
        self._wordace_close_ledger = _REPO / ".sifta_state" / "wordace_close.jsonl"
        self._wordace_close_offset: int = 0
        # WordAce does not own an audio voice. The Talk widget / OS
        # Alice owns speech. This slot remains only so old cleanup paths
        # can no-op safely after the 2026-05-14 "no second robot" patch.
        self._tts_proc: Optional[object] = None
        # When set, _on_tts_finished calls this once and clears it.
        self._tts_then = None
        # QTimers — singletons so we never stack callbacks.
        self._lesson_cue_timer = QTimer(self)
        self._lesson_cue_timer.setSingleShot(True)
        self._lesson_cue_timer.timeout.connect(self._lesson_listen_window)
        self._lesson_advance_timer = QTimer(self)
        self._lesson_advance_timer.setSingleShot(True)
        self._lesson_advance_timer.timeout.connect(self._lesson_run_cue)
        self._lesson_poll_timer = QTimer(self)
        self._lesson_poll_timer.setInterval(200)  # ms
        self._lesson_poll_timer.timeout.connect(self._lesson_poll_verdict)
        # Architect 2026-05-14 ~19:30 PDT — always-on signal poller for
        # advance / close commands. Runs on a 400ms tick whether or not
        # the lesson is in LISTEN state, because Ace can interrupt
        # mid-cue with "next word" or "close the app" and we have to
        # honor it instantly.
        self._wordace_signal_timer = QTimer(self)
        self._wordace_signal_timer.setInterval(400)  # ms
        self._wordace_signal_timer.timeout.connect(self._wordace_poll_signals)
        self._wordace_signal_timer.start()

        # Pre-load the first card so the kid sees what's coming, but
        # do NOT speak or listen until OK is pressed. _on_level_picked
        # used to auto-fire the cue; now it just stages the show card.
        self._stage_first_card()
        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))

        # Architect 2026-05-14 ~18:00 PDT: "I don't need the button to
        # start the lesson — Alice already knows the operating system,
        # she already knows that I have the app open and she knows
        # what word is on the screen so she's gonna discuss with the
        # kid." Auto-start the lesson 600ms after the widget mounts.
        QTimer.singleShot(600, self._auto_start_if_idle)

    def _auto_start_if_idle(self) -> None:
        """Auto-fire ``_start_lesson`` on first mount only. Safe to
        call multiple times — guarded by the lesson_running flag."""
        if not self._lesson_running:
            try:
                self._start_lesson()
            except Exception:
                pass

    # ── handlers ─────────────────────────────────────────────────────

    def _on_owner_changed(self, txt: str) -> None:
        self._owner_name = (txt or "Ace").strip() or "Ace"

    def _on_level_picked(self, idx: int) -> None:
        level_id = self._level_picker.itemData(idx)
        if level_id and self._engine.set_level(level_id):
            # Push the level's kind to the show card font sizing
            for L in self._engine.levels():
                if L.get("id") == level_id:
                    self._current_kind = L.get("kind") or "letter"
                    break
        # Stage the next card immediately. If a lesson is already
        # running, restart the cue loop on the new deck; otherwise the
        # boot auto-start will pick it up.
        if getattr(self, "_lesson_running", False):
            # If we're already mid-lesson, restart from the new deck.
            self._stage_first_card()
            self._lesson_run_cue()
        else:
            self._stage_first_card()

    def _stage_first_card(self) -> None:
        """Show the first card of the current level and publish it so
        Alice can answer what is on the WordAce screen before speech."""
        try:
            cue = self._engine.next_cue(write=False)
            if cue.get("kind") == "LESSON_CUE_EMPTY":
                self._show_card.set_show("…", "letter")
                return
            self._show_card.set_show(cue.get("show", ""), self._current_kind)
            # Publish even before OK. This lets the one OS Alice answer
            # "what is on the WordAce screen?" from a receipt instead
            # of guessing from pixels or drifting into generic speech.
            self._publish_alice_context(
                detail=(
                    f"WordAce staged card {cue.get('show', '?')} "
                    f"({self._current_kind}); lesson active={getattr(self, '_lesson_running', False)}."
                ),
                extra={
                    "wordace_lesson_active": bool(getattr(self, "_lesson_running", False)),
                    "staged_card": True,
                },
            )
        except Exception:
            pass

    # ── context bridge to Alice (Talk widget reads swarm_app_focus) ─

    def _publish_alice_context(
        self,
        detail: str,
        *,
        selection: str = "",
        extra: Optional[Dict] = None,
    ) -> None:
        """Push lesson state into ``.sifta_state/app_focus.jsonl``.

        Alice's Talk widget reads this ledger when assembling her
        system prompt, so she knows she is the teacher in the WordAce
        lesson, what the current cue is, and what she's expecting the
        kid to say. Without this bridge the Talk widget treats every
        question ("who are you?") in a vacuum.
        """
        if _publish_focus is None:
            return
        item = self._engine.current_item
        meta = {
            "lesson_app": "WordAce",
            "alice_identity": ALICE_IDENTITY_LINE,
            "owner_name": self._owner_name,
            "level_id": self._engine.current_level_id,
            "current_cue_show": item.show if item else "",
            "current_cue_say": item.say if item else "",
            "current_kind": self._current_kind,
            "source": "wordace_widget",
            "salience_score": 1.5,
        }
        if extra:
            meta.update(extra)
        try:
            _publish_focus(
                "WordAce",
                detail,
                tab="Lesson",
                selection=selection or (item.show if item else ""),
                metadata=meta,
            )
        except Exception:
            pass  # bridge is best-effort, never crash the lesson

    # ── handlers ────────────────────────────────────────────────────

    def _on_next_cue(self) -> None:
        cue = self._engine.next_cue(write=True)
        if cue.get("kind") == "LESSON_CUE_EMPTY":
            self._show_card.set_show("…", "letter")
            return
        self._show_card.set_show(cue.get("show", ""), self._current_kind)
        prompt = self._engine.cue_prompt_for_alice(owner_name=self._owner_name)
        self._append_line("Alice", prompt, "#FFD23F")
        # Tell Alice (Talk widget reads this) what lesson card just landed.
        self._publish_alice_context(
            detail=(
                f"I am running the WordAce reading lesson with {self._owner_name}. "
                f"Current cue: {cue.get('show', '?')} ({self._current_kind}). "
                f"I just asked: {prompt}"
            ),
        )

    def _on_alice_say(self) -> None:
        text = self._engine.cue_prompt_for_alice(owner_name=self._owner_name)
        if not text:
            return
        self._append_line("Alice", text, "#FFD23F")
        # No local TTS here. The single Alice voice belongs to Talk.
        self._publish_alice_context(
            detail=f"WordAce cue ready for {self._owner_name}: {text}",
            extra={
                "pending_alice_line": text,
                "voice_owner": "sifta_talk_to_alice_widget",
                "tts_attempted": False,
                "tts_launched": False,
            },
        )

    def _on_my_turn(self) -> None:
        """Hand the floor to the kid.

        The Talk widget owns the mic. We do not open another. Instead
        we publish to ``app_focus`` exactly what we're expecting the
        kid to say, so when the kid talks and Talk's STT fires, the
        Talk widget can see the lesson context and route the heard
        text back into ``LessonEngine.score_attempt()``.
        """
        item = self._engine.current_item
        if item is None:
            return
        target = item.say
        self._append_line(
            self._owner_name,
            f"(your turn — say: {target} — I'm listening through Alice's ear)",
            "#00BBF9",
        )
        self._publish_alice_context(
            detail=(
                f"It is {self._owner_name}'s turn. I am waiting to hear: "
                f"{target!r}. Route the next STT transcript (within 8 seconds) "
                f"to System.swarm_alice_lesson_mode.LessonEngine.score_attempt."
            ),
            extra={
                "expected_say": target,
                "lesson_listen_window_s": 8.0,
                "lesson_engine_module": "System.swarm_alice_lesson_mode",
            },
        )

    def _on_simulate_correct(self) -> None:
        """Demo path so the architect can see the full Decide→Execute→Receipt
        trio land in the ledger without needing the mic. Feeds the engine
        the expected text at high confidence."""
        item = self._engine.current_item
        if item is None:
            return
        result = self._engine.score_attempt(item.say, stt_confidence=0.95, write=True)
        self._on_verdict(result, simulated=True)

    def _on_verdict(self, result: Dict, *, simulated: bool = False) -> None:
        label = result.get("label") or ""
        sticker = result.get("sticker") or ""
        self._show_card.set_verdict(label, sticker)
        prompt = self._engine.verdict_prompt_for_alice(
            result, owner_name=self._owner_name
        )
        tag = "Alice" if not simulated else "Alice (sim)"
        self._append_line(tag, prompt, "#FFD23F")
        # Push the verdict to Alice's app_focus so the Talk widget can
        # see what just happened (kid said X, Alice said Y, verdict Z).
        self._publish_alice_context(
            detail=(
                f"Lesson verdict for {self._owner_name}: {label} "
                f"({result.get('explanation', '')}). I responded: {prompt}"
            ),
            extra={
                "verdict_label": label,
                "verdict_sticker": sticker,
                "simulated": simulated,
                "pending_alice_line": prompt,
                "voice_owner": "sifta_talk_to_alice_widget",
            },
        )

    # ── conversation state machine (no buttons, Alice drives) ─────

    def _start_lesson(self) -> None:
        """Start the auto Cue → Listen → Verdict → Advance loop.

        From here on it is a conversation: Alice asks from the OS Talk
        voice, the mic listens, the verdict comes back, and the card
        advances. The architect and the kid only watch and speak.
        """
        if self._lesson_running:
            return
        self._lesson_running = True
        try:
            self._btn_pause.setText("■  Stop lesson")
            self._btn_pause.setEnabled(True)
            self._owner_field.setReadOnly(True)
            self._level_picker.setEnabled(False)
        except Exception:
            pass
        self._set_processing_visual("I am opening WordAce and reading the current card.", active=True)
        # Seek to end of wordace_verdicts ledger so we never read stale
        # verdicts from a previous session as if they were this turn.
        try:
            if self._lesson_verdicts_ledger.exists():
                self._lesson_verdicts_offset = self._lesson_verdicts_ledger.stat().st_size
            else:
                self._lesson_verdicts_ledger.parent.mkdir(parents=True, exist_ok=True)
                self._lesson_verdicts_ledger.touch()
                self._lesson_verdicts_offset = 0
        except Exception:
            self._lesson_verdicts_offset = 0
        # Also seek the signal ledgers to EOF so we only react to
        # commands the kid says AFTER this lesson started — never to
        # stale rows from a previous session.
        for ledger_path, offset_attr in (
            (self._wordace_advance_ledger, "_wordace_advance_offset"),
            (self._wordace_close_ledger,   "_wordace_close_offset"),
        ):
            try:
                if ledger_path.exists():
                    setattr(self, offset_attr, ledger_path.stat().st_size)
                else:
                    ledger_path.parent.mkdir(parents=True, exist_ok=True)
                    ledger_path.touch()
                    setattr(self, offset_attr, 0)
            except Exception:
                setattr(self, offset_attr, 0)
        if self._current_kind == "word":
            deck_label = "words"
        elif self._current_kind == "letter_sequence":
            deck_label = "letter groups"
        elif self._current_kind == "letter":
            deck_label = "letters"
        else:
            deck_label = "cards"
        greeting = f"Hi {self._owner_name}. I am starting WordAce with {deck_label}."
        self._append_line("Lesson", greeting, "#FFD23F")
        self._heard_lbl.setText(
            "👂  Ready. Alice owns the voice through Talk; WordAce is publishing the lesson state."
        )
        self._publish_alice_context(
            detail=greeting,
            extra={
                "wordace_lesson_active": True,
                "lesson_started": True,
                "voice_owner": "sifta_talk_to_alice_widget",
            },
        )
        QTimer.singleShot(0, self._lesson_run_cue)

    def _lesson_run_cue(self) -> None:
        """Show + speak the next cue. Schedules the listen window."""
        if not self._lesson_running:
            return
        self._lesson_state = "CUE"
        self._lesson_cue_id = uuid.uuid4().hex[:12]
        self._lesson_retry_count = 0
        self._lesson_timeout_count = 0
        cue = self._engine.next_cue(write=True)
        if cue.get("kind") == "LESSON_CUE_EMPTY":
            self._show_card.set_show("…", "letter")
            done_line = f"You did it, {self._owner_name}! Lesson complete."
            self._append_line("Lesson", done_line, "#FFD23F")
            self._publish_alice_context(
                detail=done_line,
                extra={"wordace_lesson_active": False, "lesson_complete": True},
            )
            self._lesson_pause()
            return
        self._show_card.set_show(cue.get("show", ""), self._current_kind)
        prompt = self._engine.cue_prompt_for_alice(owner_name=self._owner_name)
        self._append_line("Lesson", prompt, "#FFD23F")
        card = str(cue.get("show") or "").strip()
        if self._current_kind == "word":
            self._set_processing_visual(
                f"I am using the word {card!r} in a tiny meaning story.", active=True
            )
        else:
            self._set_processing_visual(
                f"I am cueing the card {card!r} and waiting for speech.", active=True
            )
        self._publish_alice_context(
            detail=(
                f"Cue {cue.get('show','?')} for {self._owner_name}: {prompt} "
                f"(cue_id={self._lesson_cue_id})"
            ),
            extra={
                "cue_id": self._lesson_cue_id,
                "wordace_lesson_active": True,
                "pending_alice_line": prompt,
                "voice_owner": "sifta_talk_to_alice_widget",
            },
        )
        QTimer.singleShot(250, self._lesson_listen_window)

    def _lesson_listen_window(self) -> None:
        """Open the 15-second listen window — publish expected_say with
        cue_id, start polling the verdict ledger. The Talk widget side
        reads app_focus.jsonl and writes the verdict back when STT
        fires.

        Idempotent: if already in LISTEN for this cue (e.g. the timer
        fallback fired right after TTS finished), do not re-publish or
        re-arm the poll.
        """
        if not self._lesson_running:
            return
        if self._lesson_state == "LISTEN":
            return
        # The cue-fallback timer is dead now — TTS has either finished
        # or the fallback already fired. Stop it either way.
        try:
            self._lesson_cue_timer.stop()
        except Exception:
            pass
        item = self._engine.current_item
        if item is None:
            return
        self._lesson_state = "LISTEN"
        self._lesson_listen_started_ts = time.time()
        win_s = float(self._lesson_listen_window_s)
        self._publish_alice_context(
            detail=(
                f"Listening for {self._owner_name} to say {item.say!r}. "
                f"Window {win_s:.0f}s. cue_id={self._lesson_cue_id}."
            ),
            extra={
                "expected_say": item.say,
                "lesson_listen_window_s": win_s,
                "lesson_engine_module": "System.swarm_alice_lesson_mode",
                "cue_id": self._lesson_cue_id,
                "wordace_lesson_active": True,
            },
        )
        self._heard_lbl.setText(
            f"👂  Listening for: {item.say}    ·    "
            f"take your time"
        )
        self._set_processing_visual(
            f"I am listening for {self._owner_name} to say {item.say!r}.", active=True
        )
        self._lesson_poll_timer.start()

    def _lesson_read_new_verdicts(self) -> list:
        """Read any new lines from wordace_verdicts.jsonl since the last
        offset. Each row is a verdict dict (see Talk widget bridge)."""
        rows: list = []
        try:
            with self._lesson_verdicts_ledger.open("r", encoding="utf-8") as f:
                f.seek(self._lesson_verdicts_offset)
                chunk = f.read()
                self._lesson_verdicts_offset = f.tell()
            for line in chunk.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass
        return rows

    def _lesson_poll_verdict(self) -> None:
        """Tick the listen window — check the verdict ledger or time
        out at 8 seconds."""
        if not self._lesson_running or self._lesson_state != "LISTEN":
            self._lesson_poll_timer.stop()
            return
        new_rows = self._lesson_read_new_verdicts()
        for row in new_rows:
            if row.get("cue_id") == self._lesson_cue_id:
                self._lesson_poll_timer.stop()
                self._lesson_handle_verdict(row)
                return
        elapsed = time.time() - self._lesson_listen_started_ts
        if elapsed >= float(self._lesson_listen_window_s):
            self._lesson_poll_timer.stop()
            self._lesson_handle_verdict({
                "ts": time.time(),
                "cue_id": self._lesson_cue_id,
                "heard_text": "",
                "verdict_label": "TIMEOUT",
                "sticker": "⏳",
                "explanation": f"no speech in {self._lesson_listen_window_s:.0f}s",
            })

    def _wordace_poll_signals(self) -> None:
        """Drain advance + close signals written by the Talk STT bridge.

        Architect 2026-05-14 ~19:30 PDT — the kid can interrupt at any
        time with "next word" (advance) or "close WordAce" (close).
        Those phrases land here as JSONL rows; we react in the same
        tick we read them.
        """
        # Close has priority: if both rows arrived in the same tick,
        # the architect's "close" intent wins.
        for ledger, attr, handler in (
            (self._wordace_close_ledger,   "_wordace_close_offset",   self._handle_close_signal),
            (self._wordace_advance_ledger, "_wordace_advance_offset", self._handle_advance_signal),
        ):
            try:
                if not ledger.exists():
                    continue
                with ledger.open("r", encoding="utf-8") as f:
                    f.seek(getattr(self, attr, 0))
                    chunk = f.read()
                    setattr(self, attr, f.tell())
            except Exception:
                continue
            for line in chunk.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                try:
                    handler(row)
                except Exception:
                    pass

    def _handle_advance_signal(self, row: Dict) -> None:
        """Both parties agreed to move on — change the card."""
        heard = str(row.get("heard_text") or "")[:80]
        try:
            self._heard_lbl.setText(
                f"⏭  advancing on signal: {heard!r}"
            )
        except Exception:
            pass
        # Cancel any in-flight listen + retry timer so the new cue
        # starts cleanly.
        try:
            self._lesson_cue_timer.stop()
            self._lesson_poll_timer.stop()
        except Exception:
            pass
        self._lesson_state = "ADVANCE_SIGNAL"
        # If a lesson hasn't started yet (auto-start delay), kick it.
        if not self._lesson_running:
            try:
                self._start_lesson()
            except Exception:
                pass
            return
        try:
            self._lesson_run_cue()
        except Exception:
            pass

    def _handle_close_signal(self, row: Dict) -> None:
        """Ace said "close the WordAce app" — honor it."""
        heard = str(row.get("heard_text") or "")[:80]
        try:
            self._heard_lbl.setText(
                f"👋  closing WordAce on signal: {heard!r}"
            )
        except Exception:
            pass
        # Defer the close to the next event-loop tick so the heard
        # label paints first, then the widget tears down cleanly.
        QTimer.singleShot(250, self.close)

    def _lesson_handle_verdict(self, row: Dict) -> None:
        """Branch on verdict: praise+advance, nudge+retry, or move on."""
        label = (row.get("verdict_label") or "").upper()
        heard = row.get("heard_text") or ""
        sticker = row.get("sticker") or ""
        if heard:
            self._heard_lbl.setText(
                f"👂  {self._owner_name} said: {heard!r}    ·    verdict: {label} {sticker}"
            )
        else:
            self._heard_lbl.setText(
                f"👂  no speech heard    ·    verdict: {label}"
            )
        try:
            self._show_card.set_verdict(label, sticker)
        except Exception:
            pass
        self._set_processing_visual(
            f"I heard {heard!r} and scored the WordAce turn as {label or 'UNKNOWN'}.",
            active=False,
        )
        if label == "CORRECT":
            verdict_dict = {
                "label": "CORRECT", "score": 1, "sticker": sticker,
                "heard_text": heard, "explanation": row.get("explanation", ""),
            }
            praise = self._engine.verdict_prompt_for_alice(
                verdict_dict, owner_name=self._owner_name,
            )
            self._append_line("Lesson", praise, "#FFD23F")
            self._publish_alice_context(
                detail=f"WordAce verdict CORRECT for {self._owner_name}. Suggested Alice line: {praise}",
                extra={
                    "wordace_lesson_active": True,
                    "verdict_label": "CORRECT",
                    "pending_alice_line": praise,
                    "voice_owner": "sifta_talk_to_alice_widget",
                },
            )
            self._lesson_state = "PRAISE"
            self._lesson_advance_timer.start(900)
        elif label in ("CLOSE", "MISS"):
            verdict_dict = {
                "label": label, "score": 0, "sticker": sticker,
                "heard_text": heard, "explanation": row.get("explanation", ""),
            }
            nudge = self._engine.verdict_prompt_for_alice(
                verdict_dict, owner_name=self._owner_name,
            )
            self._append_line("Lesson", nudge, "#FFD23F")
            self._publish_alice_context(
                detail=f"WordAce verdict {label} for {self._owner_name}. Suggested Alice line: {nudge}",
                extra={
                    "wordace_lesson_active": True,
                    "verdict_label": label,
                    "pending_alice_line": nudge,
                    "voice_owner": "sifta_talk_to_alice_widget",
                },
            )
            if self._lesson_retry_count < self._lesson_max_retries:
                self._lesson_retry_count += 1
                # Fresh cue_id so a stale verdict can't match the retry window
                self._lesson_cue_id = uuid.uuid4().hex[:12]
                self._lesson_state = "RETRY"
                QTimer.singleShot(700, self._lesson_listen_window)
            else:
                self._lesson_state = "MOVE_ON"
                self._lesson_advance_timer.start(900)
        else:
            # TIMEOUT — patience first, move on only after re-asking.
            # Architect 2026-05-14: "every time I do it it tells me
            # that I'm wrong I'm not wrong I said the letter right."
            # The kid is not wrong on timeout — the mic just did not
            # hear yet. Re-ask the SAME letter up to _max_timeouts_per_cue
            # times before changing letter.
            self._lesson_timeout_count += 1
            item = self._engine.current_item
            same_letter = item.say if item is not None else "?"
            if self._lesson_timeout_count <= self._lesson_max_timeouts_per_cue:
                msg = (
                    f"Take your time, {self._owner_name}. "
                    f"Try saying it again: {same_letter}."
                )
                self._append_line("Lesson", msg, "#FFD23F")
                self._publish_alice_context(
                    detail=f"WordAce timeout retry. Suggested Alice line: {msg}",
                    extra={
                        "wordace_lesson_active": True,
                        "verdict_label": "TIMEOUT",
                        "pending_alice_line": msg,
                        "voice_owner": "sifta_talk_to_alice_widget",
                    },
                )
                self._lesson_state = "RETRY"
                # Re-listen on the SAME letter — fresh cue_id but card stays
                self._lesson_cue_id = uuid.uuid4().hex[:12]
                QTimer.singleShot(700, self._lesson_listen_window)
            else:
                msg = f"That's okay, {self._owner_name}. Let's try a different card."
                self._append_line("Lesson", msg, "#FFD23F")
                self._publish_alice_context(
                    detail=f"WordAce timeout move-on. Suggested Alice line: {msg}",
                    extra={
                        "wordace_lesson_active": True,
                        "verdict_label": "TIMEOUT",
                        "pending_alice_line": msg,
                        "voice_owner": "sifta_talk_to_alice_widget",
                    },
                )
                self._lesson_state = "MOVE_ON"
                self._lesson_advance_timer.start(900)

    def _tts_speak(self, text: str, *, then=None) -> None:
        """Compatibility no-op after the no-second-robot patch.

        WordAce must not launch macOS ``say``. The single Alice voice
        lives in the Talk widget. This method remains only because old
        handlers still call it; it advances the local lesson state
        without creating a second voice.
        """
        self._tts_proc = None
        self._tts_then = None
        if callable(then) and self._lesson_running:
            QTimer.singleShot(0, then)

    def _on_tts_finished(self, *args) -> None:
        """Legacy callback dispatcher kept for older signal wiring."""
        cb = self._tts_then
        self._tts_then = None
        if cb is not None and self._lesson_running:
            try:
                cb()
            except Exception:
                pass

    def _lesson_pause(self) -> None:
        """Stop all timers and leave one visible Continue control."""
        self._lesson_running = False
        self._lesson_state = "STOPPED"
        try:
            self._lesson_cue_timer.stop()
            self._lesson_advance_timer.stop()
            self._lesson_poll_timer.stop()
        except Exception:
            pass
        self._tts_proc = None
        self._tts_then = None
        try:
            self._btn_pause.setText("▶  Continue")
            self._btn_pause.setEnabled(True)
            self._owner_field.setReadOnly(False)
            self._level_picker.setEnabled(True)
            self._heard_lbl.setText(
                "👂  Lesson stopped. Press Continue when you want Alice to resume."
            )
        except Exception:
            pass
        self._set_processing_visual("I paused the lesson loop. The current card receipt is still published.", active=False)
        self._publish_alice_context(
            detail="WordAce lesson stopped by the local human.",
            extra={"wordace_lesson_active": False, "lesson_stopped": True},
        )

    def _stop_lesson(self) -> None:
        """Human-facing stop button handler."""
        self._lesson_pause()

    def _toggle_lesson(self) -> None:
        """Single visible control: stop when active, continue when paused."""
        if self._lesson_running:
            self._lesson_pause()
        else:
            self._start_lesson()

    # ── transcript helpers ──────────────────────────────────────────

    def _set_processing_visual(self, text: str, *, active: bool) -> None:
        """Show an honest processing state, not hidden chain-of-thought."""
        self._processing_base_text = (text or "I am reading the WordAce state.").strip()
        self._processing_phase = 0
        self._processing_lbl.setText(f"🧠  {self._processing_base_text}")
        if active:
            if not self._processing_timer.isActive():
                self._processing_timer.start()
        else:
            self._processing_timer.stop()

    def _tick_processing_visual(self) -> None:
        marks = ["", " ·", " · ·", " · · ·"]
        self._processing_phase = (self._processing_phase + 1) % len(marks)
        self._processing_lbl.setText(
            f"🧠  {self._processing_base_text}{marks[self._processing_phase]}"
        )

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        """Release the class-level singleton slot so the next open of
        WordAce (after the architect closes this one) builds a fresh
        widget instead of being denied by the stale __new__ check."""
        # Stop the auto-loop timers cleanly so they do not fire on a
        # half-destroyed widget after Qt deletes the C++ side.
        try:
            self._lesson_cue_timer.stop()
            self._lesson_advance_timer.stop()
            self._lesson_poll_timer.stop()
            self._wordace_signal_timer.stop()
            self._processing_timer.stop()
        except Exception:
            pass
        # Kill any in-flight TTS process so Alice does not keep
        # talking after the kid closes the window.
        proc = self._tts_proc
        if proc is not None:
            try:
                proc.finished.disconnect()
            except Exception:
                pass
            try:
                proc.kill()
                proc.waitForFinished(200)
            except Exception:
                pass
            self._tts_proc = None
        self._tts_then = None
        self._lesson_running = False
        try:
            if type(self)._live_instance is self:
                type(self)._live_instance = None
            type(self)._initialized_instance_ids.discard(id(self))
        except Exception:
            pass
        super().closeEvent(event)

    def _append_line(self, speaker: str, text: str, color: str) -> None:
        line = _TranscriptLine(speaker, text, color, self)
        # Insert just before the stretch
        self._transcript_layout.insertWidget(
            self._transcript_layout.count() - 1, line
        )
        # Trim if very long
        while self._transcript_layout.count() > 20:
            item = self._transcript_layout.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.setParent(None)
        QTimer.singleShot(0, self._scroll_transcript_to_bottom)

    def _scroll_transcript_to_bottom(self) -> None:
        try:
            bar = self._transcript_scroll.verticalScrollBar()
            bar.setValue(bar.maximum())
        except Exception:
            pass


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    w = TeachAceToReadWidget()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
