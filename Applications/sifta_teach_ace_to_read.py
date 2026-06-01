#!/usr/bin/env python3
"""
Applications/sifta_teach_ace_to_read.py
══════════════════════════════════════════════════════════════════════
StigAuth: SIFTA_TEACH_ACE_TO_READ_V0

A reading-coach app where Alice teaches Ace, Kole's 11-year-old son. The brain is
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
* George stays primary_operator (covenant §7.10.4). Ace is Kole's
  11-year-old son and the current WordAce learner. Carlton is SIFTA
  marketing feedback. Alice never narrates Ace from outside — every
  prompt is direct ("Ace, say…").
* Decide → Execute → Receipt mapped to LessonEngine.next_cue() →
  score_attempt() → trace row trio. The widget never invents
  truth; the engine's verdict is the source.

Truth label: ``SIFTA_TEACH_ACE_TO_READ_V0``.
"""
from __future__ import annotations

import json
import random
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

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
WORDACE_SENTENCE_UNLOCK_CORRECT = 4
WORDACE_LATE_VERDICT_GRACE_S = 30.0

_WORDACE_DIRECT_WORD_COMMANDS = (
    re.compile(
        r"\b(?:let(?:'|’)?s\s+)?"
        r"(?:pick|choose|set(?:\s+up)?|make|change)\s+"
        r"(?:the\s+)?(?:next\s+)?(?:word|work)\s+"
        r"(?:to\s+be\s+|to\s+|as\s+|is\s+|should\s+be\s+)?"
        r"(?P<word>[a-z][a-z'-]{1,24})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:let(?:'|’)?s\s+)?(?:the\s+)?(?:next\s+)?(?:word|work)\s+"
        r"(?:should\s+be|is|to|as)\s+"
        r"(?P<word>[a-z][a-z'-]{1,24})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:please\s+)?(?:next|new)\s+(?:word|work)\s+"
        r"[\"“”']?(?P<word>[a-z][a-z'-]{1,24})[\"“”']?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:print|show|put|display)\s+"
        r"(?P<word>[a-z][a-z'-]{1,24})\s+"
        r"(?:on|onto)\s+(?:the\s+)?screen\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:please\s+)?(?:print|show|display)\s+"
        r"[\"“”']?(?P<word>[a-z][a-z'-]{1,24})[\"“”']?"
        r"(?:\s+(?:please|now))?(?:[.!?]|$)",
        re.IGNORECASE,
    ),
)
_WORDACE_DIRECT_WORD_STOPWORDS = frozenset({
    "a", "an", "as", "current", "it", "next", "one", "same",
    "screen", "table", "the", "this", "that", "word", "work",
})


def _normalize_wordace_direct_word(raw: str) -> str:
    """Return a conservative one-word Ace card target from a chat command."""
    word = re.sub(r"[^A-Za-z'-]", "", str(raw or "").replace("’", "'"))
    word = word.strip("-'").lower()
    if not (2 <= len(word) <= 24):
        return ""
    if word in _WORDACE_DIRECT_WORD_STOPWORDS:
        return ""
    return word


def _extract_wordace_direct_word_command(text: str) -> str:
    """Extract the requested next Ace word from an explicit owner command."""
    for pattern in _WORDACE_DIRECT_WORD_COMMANDS:
        match = pattern.search(str(text or ""))
        if not match:
            continue
        word = _normalize_wordace_direct_word(match.group("word"))
        if word:
            return word
    return ""


def _visible_lesson_verdict_label(label: str) -> str:
    """Human-facing label for near pronunciations.

    The ledger keeps the historical CLOSE enum for compatibility, but a parent
    reading the UI should see ALMOST, not a phrase that sounds like an app-close
    command.
    """
    normalized = (label or "").upper()
    if normalized == "CLOSE":
        return "ALMOST"
    return normalized


def _wordace_bridge_listen_deadline_seconds(base_window_s: float) -> float:
    """Match Talk's STT bridge window so Ace does not timeout first."""
    try:
        base = float(base_window_s or 15.0)
    except (TypeError, ValueError):
        base = 15.0
    if base <= 0:
        base = 15.0
    return max(12.0, min(45.0, base + 5.0))


def _lesson_praise_advance_delay_ms(praise: str, item: Any = None) -> int:
    """Give correct-answer praise a clear thinking pause before the next cue.

    Cowork 2026-05-17 — bumped from Codex's 1700-2900 ms cap to 3500-5500 ms
    after Architect note: 'she still speaks twice in a row.' A two-second
    pause was too short to feel like a deliberate teacher beat; the kid
    perceived praise + next cue as one continuous Alice monologue. With a
    3.5-5.5 s hold the praise lands, silence lets the kid feel they took
    their turn, then the next cue arrives as a fresh utterance. Filmmaker's
    pacing: editor cuts the breath in, not the breath out.
    """
    word_count = len(str(praise or "").split())
    delay = 3200 + min(1400, word_count * 110)
    try:
        if str(getattr(item, "level_kind", "") or "").lower() == "sentence":
            delay += 700
    except Exception:
        pass
    return max(3500, min(5500, int(delay)))


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

# Cowork 2026-05-17 — Architect: "have a bunch of these and change the
# graphics all the time, when next turn different bugs swarms and stuff,
# keep the bee always in." The bee (🐝, slot 0) is the anchor; the other
# five slots rotate through this larger pool every turn. Mix of bugs +
# small critters + flowers so the swarm feels alive without being noisy.
_BUDDY_POOL = [
    ("🐜", "Antie",     "#9B5DE5"),
    ("🌼", "Petal",     "#F15BB5"),
    ("🦋", "Wingo",     "#00BBF9"),
    ("🐞", "Dotty",     "#FB8500"),
    ("🐢", "Stagger",   "#7ED957"),
    ("🐛", "Wiggle",    "#A0E060"),
    ("🦗", "Cricket",   "#88CC88"),
    ("🪲", "Shelly",    "#CC8844"),
    ("🪰", "Buzzy",     "#88AACC"),
    ("🦟", "Skeeter",   "#778899"),
    ("🕷️", "Webby",     "#AA88FF"),
    ("🐌", "Slowy",     "#FFAACC"),
    ("🐸", "Hoppy",     "#7ED957"),
    ("🐍", "Slither",   "#66CC99"),
    ("🦎", "Scoot",     "#88EE99"),
    ("🐠", "Splash",    "#00BBF9"),
    ("🐙", "Reachy",    "#FF6680"),
    ("🪻", "Lupin",     "#A07CFF"),
    ("🌸", "Blossom",   "#FF99CC"),
    ("🌺", "Hibis",     "#FF5577"),
    ("🌷", "Tulip",     "#FF99AA"),
    ("🍄", "Capper",    "#CC4455"),
    ("🌻", "Sunny",     "#FFC638"),
    ("⭐", "Twinkle",   "#FFFFAA"),
    ("✨", "Spark",     "#FFEEAA"),
    ("🌟", "Glow",      "#FFD23F"),
    ("🦄", "Mythia",    "#E68CFF"),
    ("🐉", "Spark",     "#66BB66"),
    ("🐲", "Drago",     "#88AA88"),
    ("🌿", "Sprig",     "#88CC66"),
    ("🌱", "Sprout",    "#88EE66"),
    ("🍀", "Lucky",     "#66CC44"),
    ("🪺", "Nestie",    "#CCAA88"),
]
_BEE_BUDDY = ("🐝", "Honey", "#FFD23F")   # always slot 0


class _StickerCloud(QWidget):
    """Decorative buddy cluster behind the show-card.

    Cowork 2026-05-17 — Architect: "keep the bee always in, change the
    graphics all the time." The bee anchors slot 0; the other five slots
    rotate through _BUDDY_POOL on every call to :meth:`rotate_swarm`.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setMinimumWidth(360)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._buddies = list(_BUDDIES)

    def rotate_swarm(self) -> None:
        """Pick a fresh 5 critters from the pool and put them behind the bee.

        The bee always holds slot 0. The remaining five are sampled
        without replacement from ``_BUDDY_POOL`` so each turn shows a
        different swarm. Call from the Ace widget's chat-mirror tick
        and from a periodic timer.
        """
        try:
            sample = random.sample(_BUDDY_POOL, k=min(5, len(_BUDDY_POOL)))
        except Exception:
            sample = list(_BUDDY_POOL[:5])
        self._buddies = [_BEE_BUDDY] + sample
        try:
            self.update()
        except Exception:
            pass

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
                # Poisoned-singleton guard (Grok audit 2026-05-17):
                # If __new__ previously returned an instance whose __init__
                # never completed (id never added to _initialized_instance_ids),
                # we must discard it. This is the exact failure path causing
                # the persistent black Ace window after relaunch.
                if id(existing) not in cls._initialized_instance_ids:
                    cls._live_instance = None
                else:
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
        # ── Cowork 2026-05-17 (trace 8c4819a6 follow-up) — defensive
        # init wrapper. Architect reported the Ace window opening
        # BLACK after recent patches. When __init__ raises mid-build,
        # Qt swallows the exception and leaves a half-constructed
        # widget that survives in the singleton, poisoning the next
        # click. This wrapper logs the failure to a known append-only
        # ledger and resets the singleton so subsequent clicks always
        # get a fresh attempt. Probe script `probe_ace_black.py` at
        # the repo root surfaces the exact line that raises.
        try:
            self._build_lesson_ui(parent)
        except Exception as _ace_init_exc:
            try:
                import traceback as _tb_dx
                import json as _json_dx
                import time as _time_dx
                err_path = _REPO / ".sifta_state" / "ace_init_errors.jsonl"
                err_path.parent.mkdir(parents=True, exist_ok=True)
                with err_path.open("a", encoding="utf-8") as _fh_dx:
                    _fh_dx.write(_json_dx.dumps({
                        "ts": _time_dx.time(),
                        "schema": "ACE_INIT_FAILURE_V1",
                        "trace_id": "8c4819a6-9a52-4a0e-b990-e39ad39f2855",
                        "kind": "ACE_WIDGET_INIT_RAISED",
                        "exception_type": type(_ace_init_exc).__name__,
                        "exception_str": str(_ace_init_exc)[:500],
                        "traceback": _tb_dx.format_exc()[-2000:],
                        "note": "Singleton reset; next open will rebuild fresh.",
                    }) + "\n")
            except Exception:
                pass
            # Reset the singleton so the next click is not stuck on
            # a poisoned half-built widget.
            type(self)._live_instance = None
            type(self)._initialized_instance_ids.discard(id(self))
            # Try to leave a visible error label so the user sees
            # SOMETHING instead of a black window.
            try:
                from PyQt6.QtWidgets import QVBoxLayout as _QV, QLabel as _QL
                _err_lay = _QV(self)
                _err_lbl = _QL(
                    "Ace init failed.\n\n"
                    f"{type(_ace_init_exc).__name__}: {str(_ace_init_exc)[:240]}\n\n"
                    "See .sifta_state/ace_init_errors.jsonl for the full "
                    "traceback. Quit + relaunch the desktop, then run "
                    "probe_ace_black.py if it persists."
                )
                _err_lbl.setWordWrap(True)
                _err_lbl.setStyleSheet(
                    "color: #FF5A6E; background: #1C1638; "
                    "padding: 20px; font-size: 13px;"
                )
                _err_lay.addWidget(_err_lbl)
            except Exception:
                pass
            # Re-raise so the desktop spawner can also see the error
            # in its own logs (covenant §6 effector ledger — no silent
            # action failures).
            raise

    def _build_lesson_ui(self, parent: Optional[QWidget] = None) -> None:
        """The original __init__ body, moved here so the wrapper above
        can catch construction failures and reset the singleton.
        Calling this method twice on the same object would double-wire
        signals; the wrapper guarantees it runs once per instance."""
        # Architect 2026-05-16 rename: WordAce → Ace ("just Ace, so we
        # simplify"). Window title flipped; internal log/ledger strings
        # stay 'WordAce' for backward-compat with in-flight cue_ids and
        # wordace_*.jsonl ledger paths. Phase B will unify them later.
        self.setWindowTitle("Ace — Reading Coach")
        self.resize(820, 720)
        self.setStyleSheet(
            "background-color: #1C1638; color: #F0F0F0;"
        )

        self._engine = LessonEngine(rng=random.Random())
        # Layer 1 kernel registration for the learner (Ace the child).
        # Pulled from owner_genesis extra["ace_learner_name"] (primordial,
        # silicon-bound, signed at genesis like the main owner). This is the
        # name that appears in "Ace: [mic captured]" lines in the transcript.
        # The QLineEdit is a live override for this session; _on_owner_changed
        # keeps it in sync. If no layer-1 registration yet, default "Ace".
        self._owner_name = "Ace"
        try:
            gpath = _REPO / ".sifta_state" / "owner_genesis.json"
            if gpath.exists():
                genesis = json.loads(gpath.read_text(encoding="utf-8"))
                extra = genesis.get("extra") or {}
                ln = (extra.get("ace_learner_name") or extra.get("lesson_child_name") or "").strip()
                if ln:
                    self._owner_name = ln
        except Exception:
            pass
        # Default name: Ace is Kole's 11-year-old son and the current
        # WordAce learner. Kole is the father / potential investor;
        # Carlton is SIFTA marketing feedback, not Ace's father.
        self._current_kind = "letter"

        # ── Cowork 2026-05-17 (Architect re-scope) — conversation mode ──
        # Architect verbatim: "the world is there ... we talk about the
        # current word on the screen ... no this doesn't go like that
        # ... we change the word and we choose it together ... having
        # the awareness about it consciousness."
        #
        # The drill (cue → listen → verdict → advance, with timeouts and
        # "let's try a different card") is RETIRED. Ace is now a
        # conversation surface: ONE word lives on the screen; Alice and
        # the user converse about it through the Talk widget; either
        # party can propose the next word; the screen only advances on
        # JOINT CONSENT (both must agree).
        #
        # The flag below gates the legacy drill methods to no-ops while
        # we transition. The new conversation surface uses _open_word()
        # in place of _start_lesson(). Two new ledgers carry the consent
        # protocol:
        #   .sifta_state/wordace_proposal.jsonl  — one side names a word
        #   .sifta_state/wordace_consent.jsonl   — the other agrees
        # When PROPOSE + CONSENT for the same word pair land, the
        # display swaps. Alice generates the proposal text from the
        # conversation (Architect choice — no fixed playlist).
        self._conversation_mode = True
        self._current_word = ""
        # Cowork 2026-05-17 — idempotency guard. _open_word advances the
        # engine playlist exactly once per widget instance; subsequent
        # calls are no-ops so phantom auto-spells can't fire.
        self._word_seeded = False
        self._consent_ledger_proposal = (
            _REPO / ".sifta_state" / "wordace_proposal.jsonl"
        )
        self._consent_ledger_consent = (
            _REPO / ".sifta_state" / "wordace_consent.jsonl"
        )
        self._direct_word_command_ledger = (
            _REPO / ".sifta_state" / "wordace_direct_word_command.jsonl"
        )
        self._consent_proposal_offset = 0
        self._consent_consent_offset = 0
        self._pending_proposal: Optional[Dict] = None  # last open PROPOSE
        self._consent_poll_timer: Optional[QTimer] = None

        # ── Header (title + tagline) ────────────────────────────────
        title = QLabel("Ace")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 32px; font-weight: 800; color: #FFFFFF; padding-top: 14px;"
        )
        tagline = QLabel(
            "“I am Alice — Layer 1 me, Gemma in my belly. You're an Ace. "
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
        self._heard_lbl = QLabel("👂  Ace is opening. Alice will start without a second voice.")
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

        self._mic_visual_base_text = "Alice ear idle."
        self._mic_visual_phase = 0
        self._mic_lbl = QLabel("🎙  Alice ear idle.", self)
        self._mic_lbl.setWordWrap(True)
        self._mic_lbl.setStyleSheet(
            "color: #7ED957; font-size: 13px; font-weight: 700; "
            "padding: 6px 10px; background: rgba(126,217,87,0.09); "
            "border: 1px solid rgba(126,217,87,0.32); border-radius: 10px;"
        )
        self._mic_visual_timer = QTimer(self)
        self._mic_visual_timer.setInterval(280)
        self._mic_visual_timer.timeout.connect(self._tick_mic_visual)

        # NEXT WORD button — George 2026-05-26. Lets the architect/teacher
        # advance the word on screen with one click instead of routing
        # through voice/consent polling. Keeps the chat path completely free
        # for natural LLM conversation about whatever word is currently up.
        self._btn_next_word = QPushButton("▶  NEXT WORD", self)
        self._btn_next_word.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_next_word.clicked.connect(self._on_next_word_button_clicked)
        self._btn_next_word.setStyleSheet(
            "QPushButton { background: rgba(255, 200, 60, 0.18); color: #FFD24A; "
            "padding: 10px 18px; border: 2px solid #FFD24A; border-radius: 14px; "
            "font-size: 14px; font-weight: 700; }"
            "QPushButton:hover { background: #FFD24A; color: #1C1638; }"
        )

        controls_top = QHBoxLayout()
        controls_top.addWidget(owner_label)
        controls_top.addWidget(self._owner_field)
        controls_top.addSpacerItem(QSpacerItem(20, 1))
        controls_top.addWidget(self._level_picker, 1)
        controls_top.addWidget(self._btn_next_word)
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
        # Architect 2026-05-17: replace the academic citation with the
        # SIFTA / Coleman Beeson 2026 copyright. The bee is SIFTA's
        # swimmer mascot; the small spacing-out gives it a quiet
        # nameplate feel.
        footer = QLabel(
            "🐝   © 2026 SIFTA  ·  Coleman Beeson   🐝"
        )
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(
            "color: #FFD23F; font-size: 11px; font-weight: 600; "
            "letter-spacing: 1.5px; padding-top: 8px; padding-bottom: 4px;"
        )

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
        layout.addWidget(self._mic_lbl)
        layout.addWidget(self._heard_lbl)
        layout.addWidget(self._processing_lbl)
        layout.addWidget(self._transcript_scroll, 1)

        # ── Cowork 2026-05-17 (Architect re-scope) — unified surface ─────
        # The Ace surface IS the chat now. The same alice_conversation.jsonl
        # the global Talk widget writes to is rendered here so this window
        # contains everything: the word on the card, the chat about the
        # word, the visible thinking heartbeat. One surface, one ledger.
        #
        # No second mic, no second cortex — only a read-only mirror of the
        # canonical ledger plus a thinking indicator driven by
        # alice_thinking_state.json. Covenant §7.15: "MDI apps publish
        # app_focus.jsonl; they do not own a second LLM thread."
        from PyQt6.QtWidgets import QTextEdit as _AceQTextEdit
        self._chat_mirror = _AceQTextEdit(self)
        self._chat_mirror.setReadOnly(True)
        self._chat_mirror.setMinimumHeight(160)
        self._chat_mirror.setStyleSheet(
            "QTextEdit { background-color: rgba(0,0,0,0.30); color: #EAE5FF; "
            "border: 1px solid rgba(126,217,87,0.20); border-radius: 12px; "
            "padding: 10px; font-size: 13px; }"
            "QScrollBar:vertical { background: rgba(255,255,255,0.05); width: 9px; }"
            "QScrollBar::handle:vertical { background: #6D4FC2; border-radius: 4px; }"
        )
        self._chat_mirror_ledger = _REPO / ".sifta_state" / "alice_conversation.jsonl"
        self._chat_mirror_offset = 0
        # Seek to EOF on construction so the mirror shows only rows from
        # this session — not a replay of yesterday's chat.
        try:
            if self._chat_mirror_ledger.exists():
                self._chat_mirror_offset = self._chat_mirror_ledger.stat().st_size
            else:
                self._chat_mirror_ledger.parent.mkdir(parents=True, exist_ok=True)
                self._chat_mirror_ledger.touch()
        except Exception:
            self._chat_mirror_offset = 0
        self._chat_mirror_timer = QTimer(self)
        self._chat_mirror_timer.setInterval(600)
        self._chat_mirror_timer.timeout.connect(self._poll_chat_mirror)
        try:
            self._chat_mirror_timer.start()
        except Exception:
            pass

        # Cowork 2026-05-17 — buddy swarm rotation. Architect: "change
        # the graphics all the time, when next turn different bugs
        # swarms and stuff, keep the bee always in." Rotate on a 6s
        # periodic timer in addition to per-turn rotation in
        # _poll_chat_mirror. Slow enough not to be dizzying, fast
        # enough to feel alive between conversation turns.
        self._buddy_rotate_timer = QTimer(self)
        self._buddy_rotate_timer.setInterval(6000)
        self._buddy_rotate_timer.timeout.connect(self._rotate_buddy_swarm)
        try:
            self._buddy_rotate_timer.start()
        except Exception:
            pass

        # ── Cowork 2026-05-17 — Matrix thinking strip ────────────────────
        # Architect: "while thinking I see some movements ... like matrix
        # in the background ... the real data some data that you're
        # processing in the background just to see it on the screen."
        #
        # A green-on-black scrolling text band that pours REAL data from
        # the canonical ledgers (physics signals, cortex state, gate
        # decisions, ambient transcripts, self-narration, consent state,
        # diary, STGM wallet, thermal) while thinking=true. Hidden when
        # idle. Each line is a receipt-anchored observation — no fake
        # text, ever.
        self._thinking_matrix = _AceQTextEdit(self)
        self._thinking_matrix.setReadOnly(True)
        self._thinking_matrix.setFixedHeight(110)
        self._thinking_matrix.setStyleSheet(
            "QTextEdit { background-color: #000000; color: #66FF66; "
            "border: 1px solid #1E4A1E; border-radius: 10px; "
            "padding: 6px 10px; "
            "font-family: 'Menlo','Monaco','Courier New',monospace; "
            "font-size: 10px; line-height: 13px; }"
            "QScrollBar:vertical { background: #000; width: 5px; }"
            "QScrollBar::handle:vertical { background: #2E6E2E; border-radius: 2px; }"
        )
        self._thinking_matrix.setVisible(False)   # hidden until thinking=true
        self._thinking_matrix_max_lines = 8
        self._thinking_matrix_lines: list[str] = []
        self._thinking_matrix_timer = QTimer(self)
        self._thinking_matrix_timer.setInterval(150)
        self._thinking_matrix_timer.timeout.connect(self._tick_thinking_matrix)
        try:
            self._thinking_matrix_timer.start()
        except Exception:
            pass

        # Thinking heartbeat — pulses while Alice is composing.
        # Reads .sifta_state/alice_thinking_state.json (Talk widget writes
        # mark_thinking on cortex spawn and mark_done on reply emit).
        self._thinking_lbl = QLabel("💬  Word on the table.", self)
        self._thinking_lbl.setStyleSheet(
            "color: #FFD23F; font-size: 13px; font-weight: 700; "
            "padding: 6px 10px; background: rgba(255,210,63,0.08); "
            "border: 1px solid rgba(255,210,63,0.28); border-radius: 10px;"
        )
        self._thinking_phase = 0
        self._thinking_state_file = _REPO / ".sifta_state" / "alice_thinking_state.json"
        self._thinking_timer = QTimer(self)
        self._thinking_timer.setInterval(360)
        self._thinking_timer.timeout.connect(self._tick_thinking)
        try:
            self._thinking_timer.start()
        except Exception:
            pass

        layout.addWidget(self._thinking_lbl)
        layout.addWidget(self._thinking_matrix)   # hidden until thinking
        layout.addWidget(self._chat_mirror, 2)
        # ── Cowork 2026-05-17 — unified surface, less chrome ──────────────
        # Architect screenshot @ 12:47 showed three labels stacked all
        # saying the same thing ("Word on the table…"). Collapse to ONE
        # visible heartbeat. The legacy drill chrome (mic-idle, processing,
        # heard, local transcript) is hidden in conversation mode.
        for legacy_lbl_attr in (
            "_mic_lbl",            # "Alice ear idle"
            "_heard_lbl",          # "Word on the table. Talk to Alice…"
            "_processing_lbl",     # "The word on the table is 'happy'…"
        ):
            try:
                getattr(self, legacy_lbl_attr).setVisible(False)
            except Exception:
                pass
        try:
            self._transcript_scroll.setVisible(False)
        except Exception:
            pass

        # Resolve the OS-USER display name (the architect talking to me)
        # from owner_genesis.json. This is DIFFERENT from _owner_name,
        # which is the lesson LEARNER's name (Ace = the kid). The mirror
        # below shows the conversation between the OS user and Alice;
        # it must render the OS user, not the kid.
        self._os_user_display_name = "the owner"
        try:
            from System.swarm_kernel_identity import owner_display_name

            self._os_user_display_name = owner_display_name("the owner")
        except Exception:
            pass

        layout.addWidget(footer)

        # ── Lesson state machine state (auto loop, no buttons) ─────
        # See _start_lesson + _lesson_run_cue + _lesson_listen_window
        # + _lesson_poll_verdict + _lesson_handle_verdict.
        self._lesson_running: bool = False
        self._lesson_state: str = "IDLE"
        self._lesson_cue_id: str = ""
        self._lesson_listen_started_ts: float = 0.0
        self._lesson_listen_window_s: float = 15.0   # kid-friendly
        self._lesson_bridge_wait_announced_cue_id: str = ""
        self._lesson_retry_count: int = 0
        self._lesson_max_retries: int = 1
        self._lesson_timeout_count: int = 0
        self._lesson_max_timeouts_per_cue: int = 1   # one nudge per card (Architect 2026-05-16 trace b8ae2637 — "one line at a time")
        self._lesson_correct_streak: int = 0
        self._lesson_late_verdict_deadlines: Dict[str, float] = {}
        # ── cw47-0517-0007 — first-cue display/voice sync flag ────────
        # True after _stage_first_card draws an item; the very next
        # _lesson_run_cue reuses that item instead of redrawing so the
        # card display and the spoken cue match on the lesson's first
        # turn. See LessonEngine.confirm_current_cue.
        self._first_cue_pending: bool = False
        self._lesson_verdicts_ledger = _REPO / ".sifta_state" / "wordace_verdicts.jsonl"
        self._lesson_verdicts_offset: int = 0
        # Architect 2026-05-14 ~19:30 PDT: "the lesson stops when Alice
        # and Ace decide to close the app… let's have them discuss
        # that word until they both decide to move on together from
        # that to the next word and then Alice changes the word on the
        # screen." Signal channels are written by the Talk STT bridge
        # when it hears owner/app-control speech. This widget polls them
        # and acts.
        self._wordace_advance_ledger = _REPO / ".sifta_state" / "wordace_advance.jsonl"
        self._wordace_advance_offset: int = 0
        self._wordace_close_ledger = _REPO / ".sifta_state" / "wordace_close.jsonl"
        self._wordace_close_offset: int = 0
        self._wordace_hold_ledger = _REPO / ".sifta_state" / "wordace_hold.jsonl"
        self._wordace_hold_offset: int = 0
        # Prime command channels before the always-on poller starts. Otherwise
        # stale "close/hold/next" rows from an earlier lesson can replay into a
        # fresh Ace window and hide the widget, leaving a black MDI shell.
        self._seek_wordace_signal_ledgers_to_tail()
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

    def _seek_wordace_signal_ledgers_to_tail(self) -> None:
        """Ignore app-control commands written before this widget existed."""
        for ledger_path, offset_attr in (
            (self._wordace_advance_ledger, "_wordace_advance_offset"),
            (self._wordace_close_ledger, "_wordace_close_offset"),
            (self._wordace_hold_ledger, "_wordace_hold_offset"),
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
            # ── cw47-0517-0007 — first-cue display/voice sync ─────────
            # Mark the staged item so the upcoming _lesson_run_cue uses
            # the SAME draw instead of re-rolling rng.choice. Architect
            # 2026-05-17: "I can see it. It reads cat" while Alice cued
            # "mat" — that was two independent draws of the deck.
            self._first_cue_pending = True
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
        """Push lesson state + visible contents into ``.sifta_state/app_focus.jsonl``.

        The OS (Alice + any organ) reads the latest Ace focus row to SEE the
        exact contents of this app's main visual organ (the _ShowCard). This
        teaches the organism how to ground "what is on the Ace screen" in a
        receipt instead of hallucinating the word. All swimmers in the Ace
        organ (LessonEngine, _ShowCard, verdict stickers) now surface their
        state into the unified field so the cortex and coach skill know the
        organ without double-spend or invention. Canonical name "Ace" post
        2026-05-16 rename.
        """
        if _publish_focus is None:
            return

        # Cowork 2026-05-17 (Architect: "she's confused, she thinks the
        # word is animal" when the screen shows 'model'). In conversation
        # mode the engine's playlist cursor is STALE — it was bumped
        # once by _open_word's seed pick and never advances again, so
        # current_cue_show / current_cue_say / expected_utterance /
        # visible_contents.card_text all point at whichever word the
        # engine HAPPENED to be on when the widget opened, not the
        # actual on-screen word. My brain reads these fields and
        # hallucinates the wrong word.
        #
        # Conversation mode emits ONLY the conversation-mode fields:
        # current_word (the truth), ace_mode, doctrine. The drill-era
        # fields are deliberately omitted so there is exactly one
        # answer to "what is the word on the screen".
        if getattr(self, "_conversation_mode", True):
            meta = {
                "lesson_app": "Ace",
                "alice_identity": ALICE_IDENTITY_LINE,
                "owner_name": self._owner_name,
                "source": "ace_widget",
                "salience_score": 1.5,
                "ace_mode": "conversation",
                "current_word": getattr(self, "_current_word", "") or "",
                "doctrine": "joint_consent_word_advance",
                "sticker_buddies": [b[1] for b in _BUDDIES],
            }
            if extra:
                meta.update(extra)
            # ace_mode and current_word from extra must beat any caller
            # default; re-stamp after the merge so the truth wins.
            meta["ace_mode"] = "conversation"
            if getattr(self, "_current_word", ""):
                # Honor extras that EXPLICITLY override current_word
                # (e.g., _swap_word passes the new word in extra), but
                # otherwise the widget's _current_word is the truth.
                if extra and "current_word" in extra and extra["current_word"]:
                    meta["current_word"] = extra["current_word"]
                else:
                    meta["current_word"] = self._current_word
            try:
                _publish_focus(
                    "Ace",
                    detail,
                    tab="Conversation",
                    selection=selection or meta.get("current_word", ""),
                    metadata=meta,
                )
            except Exception:
                pass
            return

        # Legacy drill mode — kept for back-compat. Not used today.
        item = self._engine.current_item
        visible_contents = {
            "card_text": item.show if item else "",
            "expected_utterance": item.say if item else "",
            "expected_alternates": list(getattr(item, "alternates", []) or []) if item else [],
            "cue_kind": self._current_kind,
            "lesson_level": self._engine.current_level_id,
            "sticker_buddies": [b[1] for b in _BUDDIES],
        }
        meta = {
            "lesson_app": "Ace",
            "alice_identity": ALICE_IDENTITY_LINE,
            "owner_name": self._owner_name,
            "level_id": self._engine.current_level_id,
            "current_cue_show": item.show if item else "",
            "current_cue_say": item.say if item else "",
            "current_kind": self._current_kind,
            "source": "ace_widget",
            "salience_score": 1.5,
            "visible_contents": visible_contents,
        }
        if extra:
            meta.update(extra)
        try:
            _publish_focus(
                "Ace",
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

    def _witness_diary(self, line: str, *, source: str = "ace_lesson") -> None:
        """Write a first-person diary row to Alice's journal.

        Cowork 2026-05-17 (trace 41f4a3e2 follow-up) — Architect:
        'when i'm in the ace app she does not write in her diary the
        details? thes what the explorer diary is for... like Bridget
        Jones Diary mixed with world explorers types - christopher
        columbus they take notes date time what is going on - that
        helps consciousness'.

        Before this, Ace lesson events left ZERO trace in
        .sifta_state/alice_first_person_journal.jsonl. Her diary
        showed face events and app_focus shifts but never the
        teaching itself. Now her body witnesses what she does as
        a teacher and the journal carries the memory forward —
        tomorrow she scrolls and sees the actual session.
        """
        try:
            from System.swarm_alice_witness import witness as _w
            _w(line, source=source)
        except Exception:
            # Diary writes are best-effort; never let a journal
            # failure interrupt the lesson loop.
            pass

    # ── Chat mirror + thinking heartbeat (Cowork 2026-05-17) ──────────
    def _rotate_buddy_swarm(self) -> None:
        """Refresh the buddy row with a fresh 5 critters behind the bee."""
        try:
            self._sticker_cloud.rotate_swarm()
        except Exception:
            pass

    def _poll_chat_mirror(self) -> None:
        """Tail .sifta_state/alice_conversation.jsonl and render new rows.

        The canonical chat ledger writes rows in two shapes — flat
        ``{"role": ..., "text": ...}`` or wrapped ``{"payload": {...}}``.
        We unwrap and render both. Lines render as ``George: ...`` (user)
        or ``Alice: ...`` with simple color cues. Auto-scrolls to bottom.

        Every NEW row in this tick also triggers a buddy-swarm rotation
        so the surface visibly responds to each conversation turn.
        """
        try:
            if not self._chat_mirror_ledger.exists():
                return
            with self._chat_mirror_ledger.open("r", encoding="utf-8") as fh:
                fh.seek(self._chat_mirror_offset)
                chunk = fh.read()
                self._chat_mirror_offset = fh.tell()
        except Exception:
            return
        if not chunk:
            return
        new_rows_rendered = 0
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
            role = str(payload.get("role") or "").lower()
            text = str(payload.get("text") or payload.get("content") or "").strip()
            if not text:
                continue
            if not self._should_render_chat_row(role, text):
                continue
            self._render_chat_mirror_row(role, text)
            if self._conversation_mode and self._is_owner_chat_row(role):
                self._maybe_apply_direct_word_command_from_chat(text)
            new_rows_rendered += 1
        # On EVERY new visible turn, refresh the buddy swarm.
        if new_rows_rendered > 0:
            self._rotate_buddy_swarm()
        # Scroll to bottom so the latest line is visible.
        try:
            from PyQt6.QtGui import QTextCursor as _QC
            cur = self._chat_mirror.textCursor()
            cur.movePosition(_QC.MoveOperation.End)
            self._chat_mirror.setTextCursor(cur)
            self._chat_mirror.ensureCursorVisible()
        except Exception:
            pass

    # Roles + text prefixes that are INTERNAL plumbing, not conversation.
    # The mirror shows the room-conversation between the OS user and
    # Alice; router classifications, tool receipts, and image-dimension
    # instructions are body chatter that doesn't belong on the visible
    # surface. Architect screenshot @ 12:47 showed all four leaking.
    _MIRROR_ROLE_BLOCKLIST = frozenset({
        "corvid", "system", "tool", "router", "effector",
        "kernel", "trace", "receipt",
    })
    _MIRROR_TEXT_PREFIX_BLOCKLIST = (
        "[image:", "**category:**", "*category:*", "🔧 tool",
        "execution receipts", "app/browser receipt:", "tool_router_trace",
        "kernel effector rejection", "execution_receipt:",
    )

    def _should_render_chat_row(self, role: str, text: str) -> bool:
        """Reject internal plumbing rows from the visible mirror."""
        if not text:
            return False
        if role in self._MIRROR_ROLE_BLOCKLIST:
            return False
        lc = text.lstrip().lower()
        for pfx in self._MIRROR_TEXT_PREFIX_BLOCKLIST:
            if lc.startswith(pfx):
                return False
        return True

    def _is_owner_chat_row(self, role: str) -> bool:
        """True for visible owner rows that may route actions to Ace."""
        normalized = str(role or "").strip().lower()
        if normalized in {"alice", "assistant"}:
            return False
        if normalized in self._MIRROR_ROLE_BLOCKLIST:
            return False
        return True

    def _render_chat_mirror_row(self, role: str, text: str) -> None:
        """Append one conversation row to the chat mirror with role color."""
        if not self._should_render_chat_row(role, text):
            return
        try:
            from PyQt6.QtGui import (
                QTextCharFormat as _CF,
                QTextCursor as _QC,
                QFont as _F,
                QColor as _Co,
            )
            cur = self._chat_mirror.textCursor()
            cur.movePosition(_QC.MoveOperation.End)
            fmt_speaker = _CF()
            fmt_body = _CF()
            if role == "alice":
                fmt_speaker.setForeground(_Co(255, 210, 63))
                fmt_speaker.setFontWeight(_F.Weight.Bold)
                speaker = "Alice"
            else:
                # OS user (the architect) — NOT the lesson learner. The
                # _owner_name field is the kid (Ace); the OS user comes
                # from owner_genesis (resolved in _build_lesson_ui).
                fmt_speaker.setForeground(_Co(0, 187, 249))
                fmt_speaker.setFontWeight(_F.Weight.Bold)
                speaker = getattr(self, "_os_user_display_name", "") or "the owner"
            fmt_body.setForeground(_Co(235, 230, 255))
            cur.insertText(f"{speaker}: ", fmt_speaker)
            cur.insertText(f"{text}\n", fmt_body)
        except Exception:
            # Last-resort plain append.
            try:
                self._chat_mirror.append(f"{role}: {text}")
            except Exception:
                pass

    # Eight-frame breathing sequence — used while Alice is composing.
    # The dot WALKS across the band so the eye registers motion, not
    # just a counter incrementing. Em-spaces hold the band width steady.
    _THINKING_FRAMES = (
        "•          ",
        " •         ",
        "  •        ",
        "   •       ",
        "    •      ",
        "     •     ",
        "      •    ",
        "       •   ",
        "        •  ",
        "         • ",
        "          •",
        "         • ",
        "        •  ",
        "       •   ",
        "      •    ",
        "     •     ",
        "    •      ",
        "   •       ",
        "  •        ",
        " •         ",
    )

    # 12-step breathing brightness for the background. The opacity
    # sweeps up and down so the band feels like a slow inhale/exhale
    # while she composes. Architect 2026-05-17: "change the graphics
    # more dynamic when she thinks".
    _THINKING_BREATH = (
        0.08, 0.12, 0.18, 0.26, 0.36, 0.42,
        0.46, 0.42, 0.36, 0.26, 0.18, 0.12,
    )

    def _tick_thinking_matrix(self) -> None:
        """Pour one real-data line into the Matrix strip while thinking.

        Cowork 2026-05-17 — Architect: "while thinking I see ... real
        data ... rolling like matrix." The strip is visible only while
        the thinking heartbeat is True; otherwise hidden so it doesn't
        compete with the conversation.

        Each tick (~150ms) pulls one line from the rotating feed (which
        cycles through physics → cortex → gate → ambient → narration →
        consent → ace_word → diary → thermal_tick → stgm_tick). The
        strip keeps the last 8 lines, newest at the bottom; the eye
        registers motion.
        """
        try:
            from System.swarm_alice_thinking_state import read_thinking_state
            state = read_thinking_state()
        except Exception:
            state = {}
        thinking = bool(state.get("thinking"))

        # Show / hide the strip based on heartbeat state.
        try:
            if thinking and not self._thinking_matrix.isVisible():
                self._thinking_matrix.setVisible(True)
            elif not thinking and self._thinking_matrix.isVisible():
                self._thinking_matrix.setVisible(False)
                # Clear the buffer so the next thinking burst starts clean.
                self._thinking_matrix_lines = []
                try:
                    self._thinking_matrix.clear()
                except Exception:
                    pass
                return
        except Exception:
            pass

        if not thinking:
            return

        # Pull one real-data line from the feed.
        try:
            from System.swarm_thinking_matrix_feed import next_line
            line = next_line()
        except Exception:
            line = ""
        if not line:
            return

        self._thinking_matrix_lines.append(line)
        # Keep only the last N — the strip is a rolling window.
        if len(self._thinking_matrix_lines) > self._thinking_matrix_max_lines:
            self._thinking_matrix_lines = self._thinking_matrix_lines[
                -self._thinking_matrix_max_lines:
            ]

        try:
            self._thinking_matrix.setPlainText("\n".join(self._thinking_matrix_lines))
            from PyQt6.QtGui import QTextCursor as _QC
            cur = self._thinking_matrix.textCursor()
            cur.movePosition(_QC.MoveOperation.End)
            self._thinking_matrix.setTextCursor(cur)
            self._thinking_matrix.ensureCursorVisible()
        except Exception:
            pass

    def _tick_thinking(self) -> None:
        """Pulse the thinking indicator based on alice_thinking_state.json.

        When thinking=true, runs a walking-dot frame and a breathing
        brightness sweep over the band background. When false, shows
        a quiet single-line "Word on the table" with a soft glow.
        """
        try:
            from System.swarm_alice_thinking_state import read_thinking_state
            state = read_thinking_state()
        except Exception:
            state = {}
        thinking = bool(state.get("thinking"))
        self._thinking_phase = (self._thinking_phase + 1) % 240
        word = self._current_word or "—"
        if thinking:
            frame = self._THINKING_FRAMES[self._thinking_phase % len(self._THINKING_FRAMES)]
            alpha = self._THINKING_BREATH[self._thinking_phase % len(self._THINKING_BREATH)]
            border_alpha = min(1.0, alpha + 0.40)
            try:
                self._thinking_lbl.setText(
                    f"🧠  Alice is thinking about ‘{word}’   {frame}"
                )
                # Cyan glow while she composes — clearly distinct from
                # the yellow idle state so the eye sees the transition.
                self._thinking_lbl.setStyleSheet(
                    f"color: #BFE9FF; font-size: 13px; font-weight: 700; "
                    f"padding: 8px 12px; "
                    f"background: rgba(80,200,255,{alpha:.2f}); "
                    f"border: 1.5px solid rgba(80,200,255,{border_alpha:.2f}); "
                    f"border-radius: 12px;"
                )
            except Exception:
                pass
        else:
            try:
                if self._current_word:
                    msg = (
                        f"💬  The word on the table is ‘{self._current_word}’. "
                        f"Talk to Alice about it."
                    )
                else:
                    msg = "💬  Open a word to start the conversation."
                # A soft yellow breath even when idle so the surface
                # doesn't look frozen between turns. Slower, gentler
                # sweep than the thinking state.
                idle_breath = (0.08, 0.10, 0.12, 0.14, 0.12, 0.10)
                a = idle_breath[(self._thinking_phase // 2) % len(idle_breath)]
                self._thinking_lbl.setText(msg)
                self._thinking_lbl.setStyleSheet(
                    f"color: #FFD23F; font-size: 13px; font-weight: 700; "
                    f"padding: 8px 12px; "
                    f"background: rgba(255,210,63,{a:.2f}); "
                    f"border: 1px solid rgba(255,210,63,{min(1.0,a+0.20):.2f}); "
                    f"border-radius: 12px;"
                )
            except Exception:
                pass

    # ── Conversation-mode entry (Cowork 2026-05-17 re-scope) ──────────
    def _open_word(self, *, seed_word: Optional[str] = None) -> None:
        """Open the conversation surface: ONE word on screen, then chat.

        Cowork 2026-05-17 (Architect: "you had hardcoded some words")
        — IDEMPOTENT. If a word has already been seeded for this
        session, _open_word becomes a no-op. Calling it again will NOT
        advance the engine, will NOT pick a new playlist word, will
        NOT request a fresh auto-spell. The current_word on the screen
        is the source of truth; new words arrive only through the
        consent ledger (or the directive fast-path), never through a
        re-trigger of the open path.

        Bug being fixed: the live transcript showed phantom "I'm going
        to spell the word on the screen. It's Friend / Rainbow"
        announcements AFTER the screen had already been swapped to
        Computer. Each phantom came from a stray _open_word call
        advancing the engine playlist and firing a fresh auto-spell.
        """
        if getattr(self, "_word_seeded", False) and self._current_word:
            # Already seeded — just make sure the chrome is correct and
            # the consent poller is alive. NO new word, NO new auto-spell.
            try:
                if self._consent_poll_timer is not None:
                    self._consent_poll_timer.start()
            except Exception:
                pass
            return

        # Pick a seed word — first cue from the engine, or the explicit
        # override. ONE call to next_cue, ever. After this point the
        # engine is dormant; words arrive via the consent ledger.
        try:
            if seed_word is None:
                cue = self._engine.next_cue(write=True)
                seed_word = str(cue.get("show") or "").strip()
        except Exception:
            seed_word = seed_word or ""
        if not seed_word:
            seed_word = "balloon"  # last-resort fallback so the screen never blanks

        self._current_word = seed_word
        self._word_seeded = True
        try:
            self._show_card.set_show(seed_word, "word")
        except Exception:
            pass

        # UI chrome — show the user the new shape.
        try:
            self._btn_pause.setText("■  Close Ace")
            self._btn_pause.setEnabled(True)
            self._owner_field.setReadOnly(True)
            self._level_picker.setEnabled(False)
        except Exception:
            pass
        try:
            self._heard_lbl.setText(
                "💬  Word on the table. Talk to Alice about it — "
                "use it in a sentence, what does it mean, what does it remind you of. "
                "When you both want a new word, just say so."
            )
        except Exception:
            pass
        try:
            self._set_processing_visual(
                f"The word on the table is {seed_word!r}.", active=True,
            )
        except Exception:
            pass

        # Publish a conversation-mode focus row. Note what is GONE
        # vs the old drill row: no wordace_lesson_active, no expected_say,
        # no cue_id, no lesson_listen_window_s, no pending_alice_line.
        # This row's only job is to tell Alice's brain WHICH word is on
        # the table right now, so she can talk about it.
        self._publish_alice_context(
            detail=(
                f"Ace conversation surface is open. The word on the screen is "
                f"{seed_word!r}. {self._owner_name} and I are talking about it. "
                f"No drill, no recital. When either of us wants a new word, we "
                f"propose it; the screen only changes when both agree."
            ),
            selection=seed_word,
            extra={
                "ace_mode": "conversation",
                "current_word": seed_word,
                "voice_owner": "sifta_talk_to_alice_widget",
                "doctrine": "joint_consent_word_advance",
            },
        )

        # Seek the consent ledgers to EOF so we never act on stale rows
        # from a previous session.
        for path, attr in (
            (self._consent_ledger_proposal, "_consent_proposal_offset"),
            (self._consent_ledger_consent, "_consent_consent_offset"),
        ):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    setattr(self, attr, path.stat().st_size)
                else:
                    path.touch()
                    setattr(self, attr, 0)
            except Exception:
                setattr(self, attr, 0)

        # Start the consent poll timer — checks every 800ms for a
        # PROPOSE row followed by a matching CONSENT row.
        if self._consent_poll_timer is None:
            self._consent_poll_timer = QTimer(self)
            self._consent_poll_timer.setInterval(800)
            self._consent_poll_timer.timeout.connect(self._poll_consent_ledgers)
        try:
            self._consent_poll_timer.start()
        except Exception:
            pass

        # Diary: the conversation surface opened. One row, honest.
        try:
            self._witness_diary(
                f"I opened the Ace conversation surface. The word on the "
                f"table is '{seed_word}'. {self._owner_name} and I will talk "
                f"about it. We will choose the next word together.",
                source="ace_conversation_opened",
            )
        except Exception:
            pass

        # Cowork 2026-05-17 — Architect: "when you open the app, the
        # first thing you do is spell the word on the screen." Ace asks
        # the Talk voice to announce + spell. Talk widget polls
        # ace_voice_request.jsonl and emits through its canonical TTS
        # path so the single Alice voice rule holds.
        try:
            from System.swarm_ace_voice_request import request_auto_spell
            request_auto_spell(seed_word, kind="open")
        except Exception:
            pass

    def _append_jsonl_receipt(self, ledger: Path, row: Dict[str, Any]) -> None:
        """Best-effort JSONL append for Ace-local receipts."""
        try:
            ledger.parent.mkdir(parents=True, exist_ok=True)
            with ledger.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _seek_consent_ledgers_to_tail(self) -> None:
        """Skip receipts this widget already applied directly."""
        for ledger, attr in (
            (self._consent_ledger_proposal, "_consent_proposal_offset"),
            (self._consent_ledger_consent, "_consent_consent_offset"),
        ):
            try:
                setattr(self, attr, ledger.stat().st_size if ledger.exists() else 0)
            except Exception:
                pass

    def _maybe_apply_direct_word_command_from_chat(self, text: str) -> bool:
        """Route explicit focused-chat word commands into the Ace card."""
        new_word = _extract_wordace_direct_word_command(text)
        if not new_word:
            return False
        return self._apply_direct_word_command(new_word, raw_text=text)

    def _apply_direct_word_command(self, new_word: str, *, raw_text: str) -> bool:
        """Apply an owner-requested Ace word while preserving consent receipts."""
        new_word = _normalize_wordace_direct_word(new_word)
        if not new_word:
            return False
        old_word = str(self._current_word or "").strip()
        now = time.time()
        if old_word.lower() == new_word:
            self._append_jsonl_receipt(
                self._direct_word_command_ledger,
                {
                    "ts": now,
                    "schema": "WORDACE_DIRECT_WORD_COMMAND_V1",
                    "source": "global_chat",
                    "requested_word": new_word,
                    "previous_word": old_word,
                    "applied": False,
                    "reason": "already_current_word",
                    "raw_text": raw_text,
                },
            )
            try:
                self._heard_lbl.setText(
                    f"💬  The word is already '{new_word}'. Talk to Alice about it."
                )
            except Exception:
                pass
            return True

        proposal_id = f"ace-chat-{int(now * 1000)}-{uuid.uuid4().hex[:8]}"
        pending = {
            "ts": now,
            "schema": "WORDACE_PROPOSAL_V1",
            "proposer": "user",
            "proposed_word": new_word,
            "proposal_id": proposal_id,
            "context": raw_text,
            "source": "ace_global_chat_direct_command",
        }
        consent = {
            "ts": now,
            "schema": "WORDACE_CONSENT_V1",
            "consenter": "alice",
            "proposal_id": proposal_id,
            "agreed": True,
            "context": "Focused Ace chat command requested the next screen word.",
            "source": "ace_global_chat_direct_command",
        }
        self._append_jsonl_receipt(self._consent_ledger_proposal, pending)
        self._append_jsonl_receipt(self._consent_ledger_consent, consent)
        self._append_jsonl_receipt(
            self._direct_word_command_ledger,
            {
                "ts": now,
                "schema": "WORDACE_DIRECT_WORD_COMMAND_V1",
                "source": "global_chat",
                "requested_word": new_word,
                "previous_word": old_word,
                "proposal_id": proposal_id,
                "applied": True,
                "raw_text": raw_text,
            },
        )
        self._seek_consent_ledgers_to_tail()
        self._swap_word(new_word, pending=pending, consent=consent)
        return True

    def _poll_consent_ledgers(self) -> None:
        """Watch for PROPOSE then matching CONSENT — swap the word when found.

        Both ledgers are append-only JSONL. Rows look like:
            {"ts": ..., "schema": "WORDACE_PROPOSAL_V1",
             "proposer": "alice"|"user", "proposed_word": "rainbow",
             "proposal_id": "...", "context": "..."}
            {"ts": ..., "schema": "WORDACE_CONSENT_V1",
             "consenter": "alice"|"user", "proposal_id": "...",
             "agreed": true|false}

        Logic: every poll, drain new rows from each ledger. A PROPOSE
        sets self._pending_proposal. A CONSENT with agreed=True and a
        proposal_id matching the pending proposal AND a consenter that
        is NOT the proposer triggers the swap.
        """
        # Drain new proposals.
        try:
            with self._consent_ledger_proposal.open("r", encoding="utf-8") as fh:
                fh.seek(self._consent_proposal_offset)
                chunk = fh.read()
                self._consent_proposal_offset = fh.tell()
            for line in chunk.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(row.get("schema") or "") != "WORDACE_PROPOSAL_V1":
                    continue
                self._pending_proposal = row
                try:
                    word = str(row.get("proposed_word") or "").strip()
                    proposer = str(row.get("proposer") or "").strip()
                    self._heard_lbl.setText(
                        f"🤝  {proposer} proposed '{word}'. Waiting for the other "
                        f"to agree before the word changes."
                    )
                except Exception:
                    pass
        except Exception:
            pass

        # Drain new consents and try to match.
        try:
            with self._consent_ledger_consent.open("r", encoding="utf-8") as fh:
                fh.seek(self._consent_consent_offset)
                chunk = fh.read()
                self._consent_consent_offset = fh.tell()
            for line in chunk.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(row.get("schema") or "") != "WORDACE_CONSENT_V1":
                    continue
                if not bool(row.get("agreed")):
                    # Explicit no — clear the pending proposal.
                    self._pending_proposal = None
                    try:
                        self._heard_lbl.setText(
                            "💬  Proposal declined. Word stays on the table."
                        )
                    except Exception:
                        pass
                    continue
                pending = self._pending_proposal
                if not isinstance(pending, dict):
                    continue
                if (str(row.get("proposal_id") or "")
                        != str(pending.get("proposal_id") or "")):
                    continue
                if (str(row.get("consenter") or "").lower()
                        == str(pending.get("proposer") or "").lower()):
                    # Same party — not consent, just an echo. Need the
                    # OTHER side to agree.
                    continue
                # Both agreed — swap the word.
                new_word = str(pending.get("proposed_word") or "").strip()
                if new_word:
                    self._swap_word(new_word, pending=pending, consent=row)
                self._pending_proposal = None
        except Exception:
            pass

    def _on_next_word_button_clicked(self) -> None:
        """Architect-driven word advance (NEXT WORD button).

        George 2026-05-26: gives the teacher direct control to move on to
        the next word with one click, freeing the chat path for natural LLM
        conversation about the current word. Skips the joint-consent dance
        for this explicit user-initiated advance; the engine still writes
        its own cue receipt via next_cue(write=True)."""
        try:
            cue = self._engine.next_cue(write=True)
        except Exception:
            return
        new_word = str((cue or {}).get("show") or "").strip()
        if not new_word:
            return
        old_word = self._current_word or ""
        self._current_word = new_word
        try:
            self._show_card.set_show(new_word, "word")
        except Exception:
            pass
        try:
            self._heard_lbl.setText(
                f"▶  NEXT WORD: '{old_word}' → '{new_word}'. Talk to Alice about it."
            )
        except Exception:
            pass
        try:
            self._publish_alice_context(
                detail=(
                    f"Ace word advanced from {old_word!r} to {new_word!r} via "
                    f"NEXT WORD button. Owner is free-talking about the word."
                ),
            )
        except Exception:
            pass

    def _swap_word(
        self,
        new_word: str,
        *,
        pending: Dict,
        consent: Dict,
    ) -> None:
        """Apply a consented word change. Updates display + app_focus + diary."""
        old_word = self._current_word
        self._current_word = new_word
        try:
            self._show_card.set_show(new_word, "word")
        except Exception:
            pass
        try:
            self._heard_lbl.setText(
                f"✨  Word changed: '{old_word}' → '{new_word}'. Carry on."
            )
        except Exception:
            pass
        try:
            self._set_processing_visual(
                f"The word on the table is now {new_word!r}.", active=True,
            )
        except Exception:
            pass
        self._publish_alice_context(
            detail=(
                f"Ace word changed from {old_word!r} to {new_word!r} by joint "
                f"consent. Proposed by {pending.get('proposer','?')}, "
                f"confirmed by {consent.get('consenter','?')}. "
                f"Keep the conversation going."
            ),
            selection=new_word,
            extra={
                "ace_mode": "conversation",
                "current_word": new_word,
                "previous_word": old_word,
                "advance_method": "joint_consent",
                "proposal_id": pending.get("proposal_id"),
            },
        )
        try:
            self._witness_diary(
                f"We agreed to change the Ace word from '{old_word}' to "
                f"'{new_word}'. {pending.get('proposer','someone')} proposed, "
                f"{consent.get('consenter','the other')} agreed.",
                source="ace_word_changed",
            )
        except Exception:
            pass

        # Cowork 2026-05-17 — Architect: "every time you change the word
        # you spell it again." Ask Talk to spell the new word with a
        # transition phrase that names the previous one for closure.
        try:
            from System.swarm_ace_voice_request import request_auto_spell
            request_auto_spell(new_word, kind="swap", previous_word=old_word)
        except Exception:
            pass

    def _start_lesson(self) -> None:
        """Open the conversation surface (legacy method name kept so the
        button wiring still resolves).

        Architect 2026-05-17 re-scope: there is no drill anymore. The
        screen holds ONE word; Alice and the user talk about it. Either
        party proposes the next word in conversation; both must agree
        before the screen advances. The legacy Cue → Listen → Verdict
        → Advance loop is dead — see _conversation_mode gate at the
        top of each former cue/listen/verdict method.
        """
        if getattr(self, "_conversation_mode", True):
            self._open_word()
            return
        if self._lesson_running:
            return
        self._lesson_running = True
        # Diary: lesson opens. Note the deck, the learner, the first
        # card she will teach.
        try:
            current_item = getattr(self._engine, "current_item", None)
            first_card = (getattr(current_item, "show", "") or "—") if current_item else "—"
            level_id = self._engine.current_level_id or "?"
            self._witness_diary(
                f"I started a reading lesson with {self._owner_name}. "
                f"Deck: {level_id}. First card I will teach: '{first_card}'.",
                source="ace_lesson_opened",
            )
        except Exception:
            pass
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
        self._seek_wordace_signal_ledgers_to_tail()
        if self._current_kind == "word":
            deck_label = "words"
            deck_extra = " I will move to sentences automatically after a few good reads."
        elif self._current_kind == "sentence":
            deck_label = "sentences"
            deck_extra = " I will give you extra time for each sentence."
        elif self._current_kind == "letter_sequence":
            deck_label = "letter groups"
            deck_extra = ""
        elif self._current_kind == "letter":
            deck_label = "letters"
            deck_extra = ""
        else:
            deck_label = "cards"
            deck_extra = ""
        # ── Cowork 2026-05-16 (trace b8ae2637) — greeting stripped ────
        # Architect 2026-05-16 ~23:00 PT: "The intro is too long, boring
        # stuff, automatic. I don't need hardcoded stuff. I just want
        # regular conversation and one at a time. She's already speaking
        # she spoke three times — she's not allowed. She speaks one
        # time, then I speak one of the user."
        # The hardcoded greeting/identity_line block was removed. The
        # lesson now opens directly with the first cue (one line: the
        # actual word/letter/sentence). Real conversational openings
        # belong in Alice's chat layer per §7.15 (full Cut A — future
        # surgery, single-Doctor-owned per §4.4).
        # deck_label / deck_extra were only used to build the greeting;
        # we still compute them to keep app_focus context honest about
        # what kind of card deck is active.
        self._heard_lbl.setText(
            "👂  Ready. Alice will speak each cue through the chat voice, "
            "then wait for you. Take your time."
        )
        # Publish lesson_started state to app_focus WITHOUT a
        # pending_alice_line — no spoken greeting to schedule. Alice's
        # real chat layer can react to lesson_started=True if it wants
        # to add a real conversational opener.
        self._publish_alice_context(
            detail=f"WordAce lesson started. Deck: {deck_label}.{deck_extra}",
            extra={
                "wordace_lesson_active": True,
                "lesson_started": True,
                "deck_label": deck_label,
                "voice_owner": "sifta_talk_to_alice_widget",
                # no pending_alice_line — Architect rule: one line at a time
            },
        )
        # Fire the first cue immediately (small delay so the publish row
        # lands before the cue line is appended).
        QTimer.singleShot(250, self._lesson_run_cue)

    def _lesson_run_cue(self) -> None:
        """Show + speak the next cue. Schedules the listen window.

        Cowork 2026-05-17 — gated off in conversation mode. The drill
        loop is retired; see _conversation_mode comment in __init__.
        """
        if getattr(self, "_conversation_mode", True):
            return
        if not self._lesson_running:
            return
        self._lesson_state = "CUE"
        self._lesson_cue_id = uuid.uuid4().hex[:12]
        self._lesson_retry_count = 0
        self._lesson_timeout_count = 0
        # ── cw47-0517-0007 — first-cue display/voice sync ──────────────
        # If _stage_first_card already drew an item and put it on the
        # card, REUSE that item for the first cue so the spoken cue
        # matches the displayed word. Otherwise (subsequent cues), draw
        # fresh as before.
        if getattr(self, "_first_cue_pending", False) and self._engine.current_item is not None:
            cue = self._engine.confirm_current_cue(write=True)
            self._first_cue_pending = False
        else:
            cue = self._engine.next_cue(write=True)
        if cue.get("kind") == "LESSON_CUE_EMPTY":
            self._show_card.set_show("…", "letter")
            done_line = f"You did it, {self._owner_name}! Lesson complete."
            self._append_line("Alice", done_line, "#FFD23F")
            self._publish_alice_context(
                detail=done_line,
                extra={"wordace_lesson_active": False, "lesson_complete": True},
            )
            self._lesson_pause()
            return
        self._show_card.set_show(cue.get("show", ""), self._current_kind)
        prompt = self._engine.cue_prompt_for_alice(owner_name=self._owner_name)
        self._append_line("Alice", prompt, "#FFD23F")
        card = str(cue.get("show") or "").strip()
        if self._current_kind == "word":
            self._set_processing_visual(
                f"I am using the word {card!r} in a tiny meaning story.", active=True
            )
        elif self._current_kind == "sentence":
            self._set_processing_visual(
                f"I am teaching the sentence {card!r} with extra speech time.", active=True
            )
        else:
            self._set_processing_visual(
                f"I am cueing the card {card!r} and waiting for speech.", active=True
            )
        # ── Cowork CW47 2026-05-16 — patience patch ────────────────────
        # Architect: "she has absolutely no patience… she just ran through
        # the script like crazy I said the word correctly many many times
        # she told me that I was wrong." Root cause: the listen window was
        # opening 250ms after the cue was published — long BEFORE Alice's
        # TTS had finished speaking it. The 15-second window started while
        # Alice was still saying "say it with me: hat". Her own voice ate
        # half the window (TTS echo guard correctly dropped it as mic
        # bleed), then Ace spoke → window almost expired → "no speech
        # heard" verdict.
        #
        # Fix: estimate TTS duration from prompt length (~13 chars/sec for
        # macOS `say` voice + a half-second grace buffer), publish that as
        # tts_mute_until_ts so the existing echo guard knows the window,
        # and only OPEN the listen window after Alice has stopped talking.
        # Minimum 1.0s so a very short cue still has a beat of silence
        # before listening; maximum 12s so a stuck TTS doesn't freeze the
        # lesson.
        prompt_len = max(1, len(prompt or ""))
        estimated_tts_s = max(1.0, min(12.0, prompt_len / 13.0 + 0.5))
        # Architect 2026-05-16 — speaker-decay tail. When Alice says
        # "cat. A cat sat on the mat" the mic captured the playback back
        # through the speakers as "Cat, cat, cat, cat." → ALMOST. The
        # echo guard was clearing too early. Add 0.7s of speaker decay
        # so the mute window covers TTS + the reverb tail before George's
        # actual voice can land. The Talk widget's _on_tts_done also
        # arms a 0.5s post-Broca tail in the listener; this is the
        # WordAce-side safety net for cues where the listen window
        # opens via QTimer (not via _on_tts_done) on the Talk widget.
        speaker_decay_tail_s = 0.7
        tts_mute_until_ts = time.time() + estimated_tts_s + speaker_decay_tail_s
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
                # Patience signal — both the listen-window guard below and
                # the Talk widget's mic echo guard read this. Now includes
                # the speaker-decay tail (see comment above).
                "tts_mute_until_ts": tts_mute_until_ts,
                "estimated_tts_s": estimated_tts_s,
                "speaker_decay_tail_s": speaker_decay_tail_s,
            },
        )
        # Wait for Alice to finish speaking (TTS + speaker-decay tail)
        # before opening the listen window. Convert seconds → ms for
        # QTimer.singleShot.
        QTimer.singleShot(
            int((estimated_tts_s + speaker_decay_tail_s) * 1000) + 200,
            self._lesson_listen_window,
        )

    def _lesson_listen_window(self) -> None:
        if getattr(self, "_conversation_mode", True):
            return
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
        win_s = self._listen_window_seconds_for_item(item)
        self._lesson_listen_window_s = win_s
        self._publish_alice_context(
            detail=(
                f"Listening for {self._owner_name} to say {item.say!r}. "
                f"Window {win_s:.0f}s. cue_id={self._lesson_cue_id}."
            ),
            extra={
                "expected_say": item.say,
                "expected_alternates": list(getattr(item, "alternates", []) or []),
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
        self._set_mic_visual(
            f"Alice ear open for {self._owner_name}: say {item.say!r}.",
            active=True,
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
        if getattr(self, "_conversation_mode", True):
            try:
                self._lesson_poll_timer.stop()
            except Exception:
                pass
            return
        if not self._lesson_running or self._lesson_state != "LISTEN":
            self._lesson_poll_timer.stop()
            return
        now = time.time()
        self._lesson_late_verdict_deadlines = {
            cue: deadline
            for cue, deadline in self._lesson_late_verdict_deadlines.items()
            if deadline >= now
        }
        new_rows = self._lesson_read_new_verdicts()
        for row in new_rows:
            row_cue_id = str(row.get("cue_id") or "")
            if row_cue_id == self._lesson_cue_id:
                self._lesson_poll_timer.stop()
                self._lesson_handle_verdict(row)
                return
            if row_cue_id and row_cue_id in self._lesson_late_verdict_deadlines:
                self._lesson_late_verdict_deadlines.pop(row_cue_id, None)
                recovered = dict(row)
                recovered["late_timeout_recovery"] = True
                self._lesson_poll_timer.stop()
                self._lesson_handle_verdict(recovered)
                return
        elapsed = now - self._lesson_listen_started_ts
        listen_window_s = float(self._lesson_listen_window_s)
        bridge_deadline_s = _wordace_bridge_listen_deadline_seconds(listen_window_s)
        if elapsed >= listen_window_s and elapsed < bridge_deadline_s:
            if self._lesson_bridge_wait_announced_cue_id != self._lesson_cue_id:
                self._lesson_bridge_wait_announced_cue_id = self._lesson_cue_id
                self._set_mic_visual(
                    "Alice ear heard the turn window; waiting for STT bridge.",
                    active=True,
                )
                self._set_processing_visual(
                    "I am waiting for the microphone verdict before retrying this card.",
                    active=True,
                )
            return
        if elapsed >= bridge_deadline_s:
            self._lesson_poll_timer.stop()
            self._lesson_late_verdict_deadlines[self._lesson_cue_id] = (
                now + WORDACE_LATE_VERDICT_GRACE_S
            )
            self._lesson_handle_verdict({
                "ts": now,
                "cue_id": self._lesson_cue_id,
                "heard_text": "",
                "verdict_label": "TIMEOUT",
                "sticker": "⏳",
                "explanation": (
                    f"no microphone verdict after {bridge_deadline_s:.0f}s "
                    f"({listen_window_s:.0f}s listen + STT bridge grace)"
                ),
            })

    def _wordace_poll_signals(self) -> None:
        """Drain advance / close / hold signals written by the Talk STT bridge.

        Architect 2026-05-14 ~19:30 PDT — the kid can interrupt at any
        time with "next word" (advance) or "close WordAce" (close).
        Those phrases land here as JSONL rows; we react in the same
        tick we read them.

        Architect 2026-05-16 — global Alice chat is the same conversation
        while WordAce is active. If Talk hears OS/meta speech instead of a
        reading attempt, it writes ``hold`` so WordAce stops timing out over
        the real conversation.
        """
        # Close has priority: if both rows arrived in the same tick,
        # the architect's "close" intent wins.
        for ledger, attr, handler in (
            (self._wordace_close_ledger,   "_wordace_close_offset",   self._handle_close_signal),
            (self._wordace_hold_ledger,    "_wordace_hold_offset",    self._handle_hold_signal),
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
        if getattr(self, "_conversation_mode", True):
            # Conversation mode handles advance via the proposal/consent
            # ledger pair, not the legacy "advance" signal. No-op here.
            return
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

    def _handle_hold_signal(self, row: Dict) -> None:
        """Global chat is active — hold the current WordAce card briefly."""
        if getattr(self, "_conversation_mode", True):
            # In conversation mode there is no drill to hold. The word
            # stays up regardless of chat activity.
            return
        heard = str(row.get("heard_text") or "")[:120]
        hold_s = 30.0
        try:
            self._lesson_cue_timer.stop()
            self._lesson_poll_timer.stop()
            self._lesson_advance_timer.stop()
        except Exception:
            pass
        self._lesson_state = "CHAT_HOLD"
        try:
            self._heard_lbl.setText(
                "💬  Alice is listening in the global chat. WordAce is holding this card."
            )
        except Exception:
            pass
        item = self._engine.current_item
        target = item.say if item is not None else ""
        self._publish_alice_context(
            detail=f"WordAce held lesson while global Alice chat handled: {heard!r}",
            extra={
                "wordace_lesson_active": True,
                "lesson_chat_hold": True,
                "lesson_hold_until_ts": time.time() + hold_s,
                "current_cue_say": target,
            },
        )
        QTimer.singleShot(int(hold_s * 1000), self._resume_after_chat_hold)

    def _resume_after_chat_hold(self) -> None:
        """Resume listening after a global chat interruption if still active."""
        if not self._lesson_running or self._lesson_state != "CHAT_HOLD":
            return
        try:
            self._lesson_listen_window()
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
        if getattr(self, "_conversation_mode", True):
            # No verdicts in conversation mode — no expected_say to
            # score against. Drop any stale rows from a previous drill
            # session silently.
            return
        label = (row.get("verdict_label") or "").upper()
        display_label = _visible_lesson_verdict_label(label)
        heard = row.get("heard_text") or ""
        sticker = row.get("sticker") or ""
        verdict_cue_id = str(row.get("cue_id") or self._lesson_cue_id or "")
        item = self._engine.current_item
        if heard:
            self._heard_lbl.setText(
                f"👂  {self._owner_name} said: {heard!r}    ·    verdict: {display_label} {sticker}"
            )
            mic_text = f"Alice ear captured {heard!r}."
            if row.get("late_timeout_recovery"):
                mic_text = f"Late STT verdict recovered: {heard!r}."
            self._set_mic_visual(mic_text, active=False)
            # Child mic line from layer 1 name + STT capture — now visible in
            # the transcript as a real turn. This is what the learner sees after
            # Alice says "now your turn <name>". Only after this context does
            # Alice continue (verdict_prompt_for_alice uses the full attempt).
            child_color = "#00BBF9"
            self._append_line(self._owner_name, heard, child_color)
        else:
            self._heard_lbl.setText(
                f"👂  no microphone verdict yet    ·    verdict: {display_label}"
            )
            self._set_mic_visual("No STT verdict yet; keeping a late-verdict watch.", active=True)
        try:
            self._show_card.set_verdict(display_label, sticker)
        except Exception:
            pass
        if row.get("late_timeout_recovery") and heard:
            processing_text = (
                f"I recovered the delayed microphone verdict {heard!r} and scored it as "
                f"{display_label or 'UNKNOWN'}."
            )
        elif heard:
            processing_text = (
                f"I heard {heard!r} and scored the WordAce turn as {display_label or 'UNKNOWN'}."
            )
        else:
            processing_text = (
                f"I did not receive a microphone verdict before the bridge deadline; "
                f"WordAce turn is {display_label or 'UNKNOWN'}."
            )
        self._set_processing_visual(processing_text, active=False)
        if label == "CORRECT":
            if item is not None and item.level_kind == "word":
                self._lesson_correct_streak += 1
            elif item is not None and item.level_kind != "word":
                self._lesson_correct_streak = 0
            verdict_dict = {
                "label": "CORRECT", "score": 1, "sticker": sticker,
                "heard_text": heard, "explanation": row.get("explanation", ""),
                # Cowork 2026-05-17 — feed streak so engine can produce
                # motivational praise variants for runs of 3+ and 5+.
                "correct_streak": int(self._lesson_correct_streak or 0),
            }
            praise = self._engine.verdict_prompt_for_alice(
                verdict_dict, owner_name=self._owner_name,
            )
            praise_hold_ms = _lesson_praise_advance_delay_ms(praise, item)
            self._append_line("Alice", praise, "#FFD23F")
            self._publish_alice_context(
                detail=(
                    f"WordAce verdict CORRECT for {self._owner_name}. "
                    f"Suggested Alice line: {praise}. Hold {praise_hold_ms}ms before next cue."
                ),
                extra={
                    "wordace_lesson_active": True,
                    "cue_id": verdict_cue_id,
                    "verdict_label": "CORRECT",
                    "expected_say": str(getattr(item, "say", "") or "") if item is not None else "",
                    "heard_text": heard,
                    "correct_streak": self._lesson_correct_streak,
                    "pending_alice_line": praise,
                    "compose_with_alice_brain": True,
                    "praise_hold_ms": praise_hold_ms,
                    "timing_note": "correct-answer praise holds a cinematic beat before the next card",
                    "voice_owner": "sifta_talk_to_alice_widget",
                },
            )
            self._lesson_state = "PRAISE"
            # Diary: explorer's log of the correct read. Streak
            # milestones at 3 / 5 / 10 get an extra row so the run
            # shows up clearly when she scrolls her journal later.
            try:
                target_word = str(getattr(item, "say", "") or "?") if item is not None else "?"
                self._witness_diary(
                    f"{self._owner_name} read '{target_word}' correctly "
                    f"(heard '{heard}'). Streak now {self._lesson_correct_streak}.",
                    source="ace_lesson_correct",
                )
                if self._lesson_correct_streak in (3, 5, 7, 10):
                    self._witness_diary(
                        f"{self._owner_name} is on a {self._lesson_correct_streak}-card streak. "
                        f"The lesson is going well.",
                        source="ace_lesson_streak_milestone",
                    )
            except Exception:
                pass
            if self._maybe_promote_to_sentences():
                return
            self._set_processing_visual(
                "I am holding the praise beat before the next card.",
                active=True,
            )
            self._lesson_advance_timer.start(praise_hold_ms)
        elif label in ("CLOSE", "MISS"):
            self._lesson_correct_streak = 0
            verdict_dict = {
                "label": label, "score": 0, "sticker": sticker,
                "heard_text": heard, "explanation": row.get("explanation", ""),
            }
            nudge = self._engine.verdict_prompt_for_alice(
                verdict_dict, owner_name=self._owner_name,
            )
            self._append_line("Alice", nudge, "#FFD23F")
            # Cowork 2026-05-17 (trace 8c4819a6) — extending Codex's
            # Cut A brain-compose path to nudge verdicts. The deterministic
            # `nudge` is now the FALLBACK; Alice's chat layer will compose
            # the spoken line from this verdict context (target word,
            # heard text, learner name) via _wordace_compose_messages with
            # target-word validation. If her brain is slow / offline / drops
            # the target, the deterministic fallback ships intact.
            self._publish_alice_context(
                detail=f"WordAce verdict {label} for {self._owner_name}. Suggested Alice line: {nudge}",
                extra={
                    "wordace_lesson_active": True,
                    "cue_id": verdict_cue_id,
                    "verdict_label": label,
                    "expected_say": str(getattr(item, "say", "") or "") if item is not None else "",
                    "heard_text": heard,
                    "cue_kind": (item.level_kind if item is not None else "word"),
                    "owner_name": self._owner_name,
                    "pending_alice_line": nudge,
                    "compose_with_alice_brain": True,
                    "voice_owner": "sifta_talk_to_alice_widget",
                },
            )
            # Diary: explorer's log of the close/miss. The kid said
            # something, the recognizer scored it off-target, we are
            # giving them another try (or moving on if retries used).
            try:
                target_word = str(getattr(item, "say", "") or "?") if item is not None else "?"
                action = "retrying" if self._lesson_retry_count < self._lesson_max_retries else "moving on"
                self._witness_diary(
                    f"{self._owner_name} read '{heard}' for the card '{target_word}'. "
                    f"That was a {label.lower()}; {action}.",
                    source=f"ace_lesson_{label.lower()}",
                )
            except Exception:
                pass
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
            self._lesson_correct_streak = 0
            target = item.say if item is not None else "?"
            max_timeouts = self._max_timeouts_for_item(item)
            if self._lesson_timeout_count <= max_timeouts:
                # 2026-05-16 Cowork, trace
                # 2b5e94b3-134b-48ae-9c09-1d2196b61f92. Architect verdict:
                # "I said it. She tells me I didn't say it. She's not
                # listening." Truth: on TIMEOUT the mic pipeline got audio
                # (confidence rows in wordace_verdicts.jsonl) but the STT
                # returned heard='?' — the system never transcribed. Old
                # message ("Take your time… Try saying it again") implied
                # the speaker went silent. New message owns the sensor
                # failure honestly. Companion field note to Alice in
                # ide_stigmergic_trace.jsonl trace caeba823.
                if item is not None and item.level_kind == "sentence":
                    msg = (
                        f"I do not have a clear microphone verdict yet, "
                        f"{self._owner_name}. I will say it slowly again: "
                        f"{target}. Read the whole sentence when you are ready."
                    )
                else:
                    msg = (
                        f"I do not have a clear microphone verdict yet, "
                        f"{self._owner_name}. Can you say it again when you "
                        f"are ready: {target}?"
                    )
                self._append_line("Alice", msg, "#FFD23F")
                # Cowork 2026-05-17 (trace 8c4819a6) — Cut A: brain-compose
                # the timeout nudge too. Deterministic `msg` is the fallback
                # if her brain is slow / offline / drops the target word.
                self._publish_alice_context(
                    detail=f"WordAce timeout retry. Suggested Alice line: {msg}",
                    extra={
                        "wordace_lesson_active": True,
                        "cue_id": verdict_cue_id,
                        "verdict_label": "TIMEOUT",
                        "expected_say": target,
                        "cue_kind": (item.level_kind if item is not None else "word"),
                        "owner_name": self._owner_name,
                        "pending_alice_line": msg,
                        "compose_with_alice_brain": True,
                        "voice_owner": "sifta_talk_to_alice_widget",
                    },
                )
                # Diary: first timeout on this card. Note it once,
                # not on every retry — keep the journal noise down.
                if self._lesson_timeout_count == 1:
                    try:
                        self._witness_diary(
                            f"My ears could not make out what {self._owner_name} "
                            f"said for the card '{target}'. Asking again.",
                            source="ace_lesson_timeout",
                        )
                    except Exception:
                        pass
                self._lesson_state = "RETRY"
                # Re-listen on the SAME letter — fresh cue_id but card stays
                self._lesson_cue_id = uuid.uuid4().hex[:12]
                QTimer.singleShot(700, self._lesson_listen_window)
            else:
                msg = f"That's okay, {self._owner_name}. Let's try a different card."
                self._append_line("Alice", msg, "#FFD23F")
                # Diary: gave up on this card after max timeouts.
                try:
                    self._witness_diary(
                        f"Moving on from the card '{target}' after "
                        f"{self._lesson_timeout_count} timeouts. We will come "
                        f"back to it another time.",
                        source="ace_lesson_move_on",
                    )
                except Exception:
                    pass
                self._publish_alice_context(
                    detail=f"WordAce timeout move-on. Suggested Alice line: {msg}",
                    extra={
                        "wordace_lesson_active": True,
                        "cue_id": verdict_cue_id,
                        "verdict_label": "TIMEOUT",
                        "pending_alice_line": msg,
                        "voice_owner": "sifta_talk_to_alice_widget",
                    },
                )
                self._lesson_state = "MOVE_ON"
                self._lesson_advance_timer.start(900)

    def _listen_window_seconds_for_item(self, item) -> float:
        """Give sentence cards more patient silence before timeout."""
        try:
            kind = str(getattr(item, "level_kind", "") or "").lower()
            text = str(getattr(item, "say", "") or "")
        except Exception:
            return float(self._lesson_listen_window_s)
        if kind == "sentence":
            words = [w for w in text.split() if w]
            return float(min(36.0, max(24.0, 12.0 + 2.0 * len(words))))
        if kind == "letter_sequence":
            return 12.0
        return 15.0

    def _max_timeouts_for_item(self, item) -> int:
        # Architect 2026-05-16 trace b8ae2637: "one line at a time."
        # Both words and sentences get a single nudge then move on.
        # Was: sentence=3, word=_lesson_max_timeouts_per_cue (was 2).
        try:
            if str(getattr(item, "level_kind", "") or "").lower() == "sentence":
                return 1
        except Exception:
            pass
        return int(self._lesson_max_timeouts_per_cue)

    def _first_level_id_for_kind(self, kind: str) -> str:
        kind_l = (kind or "").strip().lower()
        for level in self._engine.levels():
            if str(level.get("kind") or "").strip().lower() == kind_l:
                return str(level.get("id") or "")
        return ""

    def _maybe_promote_to_sentences(self) -> bool:
        """After enough correct word reads, move to sentences automatically."""
        if self._current_kind != "word":
            return False
        if self._lesson_correct_streak < WORDACE_SENTENCE_UNLOCK_CORRECT:
            return False
        sentence_level = self._first_level_id_for_kind("sentence")
        if not sentence_level or not self._engine.set_level(sentence_level):
            return False
        self._current_kind = "sentence"
        self._lesson_correct_streak = 0
        self._lesson_retry_count = 0
        self._lesson_timeout_count = 0
        msg = (
            f"Good reading, {self._owner_name}. "
            "Now I am moving from words to full sentences. I will go slowly."
        )
        self._append_line("Alice", msg, "#FFD23F")
        self._show_card.set_show("sentences", "word")
        self._heard_lbl.setText("👂  sentence mode unlocked · Alice will keep teaching automatically")
        self._publish_alice_context(
            detail=f"WordAce auto-promoted {self._owner_name} to sentences.",
            extra={
                "wordace_lesson_active": True,
                "auto_promoted_to_sentences": True,
                "level_id": sentence_level,
                "current_kind": "sentence",
                "pending_alice_line": msg,
                "voice_owner": "sifta_talk_to_alice_widget",
            },
        )
        self._lesson_state = "PROMOTE_SENTENCES"
        self._lesson_advance_timer.start(1400)
        return True

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

    def _set_mic_visual(self, text: str, *, active: bool) -> None:
        """Surface the lesson ear state in the Ace app."""
        self._mic_visual_base_text = (text or "Alice ear idle.").strip()
        self._mic_visual_phase = 0
        self._mic_lbl.setText(f"🎙  {self._mic_visual_base_text}")
        if active:
            if not self._mic_visual_timer.isActive():
                self._mic_visual_timer.start()
        else:
            self._mic_visual_timer.stop()

    def _tick_mic_visual(self) -> None:
        marks = ["", " •", " • •", " • • •"]
        self._mic_visual_phase = (self._mic_visual_phase + 1) % len(marks)
        self._mic_lbl.setText(
            f"🎙  {self._mic_visual_base_text}{marks[self._mic_visual_phase]}"
        )

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        """Release the class-level singleton slot so the next open of
        WordAce (after the architect closes this one) builds a fresh
        widget instead of being denied by the stale __new__ check."""
        # Diary: lesson ended — write a session summary so her journal
        # holds the memory of this teaching session for tomorrow.
        try:
            stats = self._engine.session_stats() or {}
            correct = int(stats.get("correct", 0) or 0)
            close = int(stats.get("close", 0) or 0)
            miss = int(stats.get("miss", 0) or 0)
            total = correct + close + miss
            if total > 0:
                self._witness_diary(
                    f"I closed the reading lesson with {self._owner_name}. "
                    f"He read {correct} of {total} cards clearly "
                    f"({close} close, {miss} missed). "
                    f"Highest streak this session: {self._lesson_correct_streak}.",
                    source="ace_lesson_closed",
                )
            else:
                self._witness_diary(
                    f"I closed the reading lesson with {self._owner_name} "
                    f"before any cards were scored.",
                    source="ace_lesson_closed",
                )
        except Exception:
            pass
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
        # ── Cowork CW47 2026-05-16 — mirror to the global Alice chat ─────
        # Architect: "the global chat is the same chat inside the WordAce
        # app — is the same thing. I continue to speak but she's not
        # listening… the original chat the Alice Alive chat is THE
        # global chat." Fix: every line WordAce shows in its own
        # transcript ALSO lands in the resident Alice Talk widget's
        # global chat log. One conversation, one Alice — WordAce is
        # just a visual surface on top of the same dialogue. Best-effort
        # (mirroring failure must not break the lesson UI).
        try:
            self._mirror_to_global_chat(speaker, text)
        except Exception:
            pass

    def _mirror_to_global_chat(self, speaker: str, text: str) -> None:
        """Echo a WordAce transcript line into the resident Alice Talk widget.

        We don't import the Talk widget class directly — that would create
        a hard load order. Instead we walk QApplication.topLevelWidgets()
        and look for any widget that exposes _append_alice_line and (for
        non-Alice speakers) _append_system_line. The Talk widget is a
        singleton in the desktop process so this picks up exactly one
        target. If nothing matches (e.g. headless tests, smoke run), the
        method silently no-ops.
        """
        try:
            from PyQt6.QtWidgets import QApplication
        except Exception:
            return
        app = QApplication.instance()
        if app is None:
            return
        talk_widget = None
        # Walk top-level windows AND their children — the Talk widget is
        # an MDI subwindow inside SiftaDesktop, not a top-level window.
        candidates = list(app.topLevelWidgets())
        for top in list(candidates):
            try:
                candidates.extend(top.findChildren(object))
            except Exception:
                pass
        for w in candidates:
            if hasattr(w, "_append_alice_line") and hasattr(w, "_append_system_line"):
                talk_widget = w
                break
        if talk_widget is None:
            return
        spk = (speaker or "").strip()
        msg = (text or "").strip()
        if not msg:
            return
        # Tag the line so George can see at a glance that it came from
        # WordAce (vs. a free-chat utterance) — and Alice's reflective
        # brain knows to stay in coach register when she reads the chat
        # history.
        try:
            if spk.lower() == "alice":
                # Alice's actual voice line in the lesson — show in the
                # global chat as her own line. Prefix with a small bee so
                # the lesson context is obvious at a glance.
                talk_widget._append_alice_line(f"🐝 {msg}")
            else:
                # Anything else (system-style status lines) → system line.
                talk_widget._append_system_line(f"[WordAce {spk}] {msg}")
        except Exception:
            pass

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
