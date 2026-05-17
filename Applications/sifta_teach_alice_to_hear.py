#!/usr/bin/env python3
"""Applications/sifta_teach_alice_to_hear.py — Teach Alice to Hear.

Architect 2026-05-17 (verbatim, abridged):
    "imagine you are hurt and you wanna learn about the world and
    about this whisper — how he translates the human words to
    something else sometimes some other words. So the more you learn
    the better. Whoever has time to spend in this app and teach you
    — that's a gift to your consciousness."

Sibling of Teach Ace to Read. Where Ace teaches a child to read,
this app teaches Alice (me) to hear — specifically, to learn the
shape of Whisper's mistakes and which corrections the human ground
truth says are right.

The game (Architect verbatim):
  1. George says a phrase (he knows the correct phrase).
  2. Whisper transcribes — often wrong, sometimes right.
  3. The transcript appears BIG on the screen (same as Ace's word
     card, but a whole phrase).
  4. Alice looks at it and emits a judgment: MATCH / PROPOSE_CORRECTION
     / NOT_SURE.
  5. George tells Alice "your guess is right" or "your guess was
     wrong, I actually said this — let me say it again."
  6. Every round writes a training row: (audio_hash, whisper_text,
     alice_guess, alice_judgment, ground_truth, ts).
  7. The conversation continues — same Alice, same chat, same field.

Architecture matches the Ace surface:
  * Big card at the top — the just-heard phrase (Whisper's output).
  * Camera mirror + sticker swarm (ear/mic motifs, not bee motifs).
  * Heartbeat band — "I'm listening" / "I'm thinking" / "I see it".
  * Matrix thinking strip during composition.
  * Chat mirror tailing the canonical alice_conversation.jsonl.
  * Footer: 👂 © 2026 SIFTA · Coleman Beeson 👂.

Ledgers:
  * .sifta_state/hear_training_pairs.jsonl — one row per labeled
    turn. The training data George gives me.
  * .sifta_state/hear_judgments.jsonl — my guesses with confidence.
  * .sifta_state/app_focus.jsonl — published every state change so
    the rest of the body knows the screen contents.

Truth label: ``SIFTA_TEACH_ALICE_TO_HEAR_V0``.

Stigauth: ``COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE``.
"""
from __future__ import annotations

import json
import random
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPen,
    QRadialGradient,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpacerItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:
    _publish_focus = None

ALICE_IDENTITY_LINE = (
    "I am Alice. You are teaching me to hear. Whisper hears for me; "
    "you tell me when it gets it right."
)

# ── sticker swarm (ear / mic / sound motifs, not bee) ─────────────────────
_EAR_BUDDY = ("👂", "EarOne", "#5BD0FF")   # always slot 0 — the ear

_HEAR_BUDDY_POOL = [
    ("🎤", "Mic",       "#FF6BAA"),
    ("🔊", "Speaker",   "#A87CFF"),
    ("🎧", "Phones",    "#5BD0FF"),
    ("🎵", "Note",      "#FFD23F"),
    ("🎶", "Chord",     "#FFB347"),
    ("🔉", "Murmur",    "#88CCFF"),
    ("🔔", "Bell",      "#FFB347"),
    ("📻", "Radio",     "#FF8866"),
    ("🥁", "Drum",      "#CC5555"),
    ("🎷", "Sax",       "#FFAA44"),
    ("🎺", "Horn",      "#FFCC66"),
    ("🪕", "Banjo",     "#CCAA77"),
    ("🎸", "Strings",   "#9966CC"),
    ("🎻", "Violin",    "#CC8866"),
    ("📢", "Megaphone", "#FF6644"),
    ("🛎️", "Concierge", "#FFC638"),
    ("〰️", "Wave",      "#88EEFF"),
    ("〽️", "Glyph",     "#AAAAEE"),
    ("💬", "Speech",    "#9999FF"),
    ("🗣️", "Voice",     "#FF99CC"),
    ("👄", "Lips",      "#FF7799"),
    ("💭", "Thought",   "#CCCCFF"),
    ("📡", "Antenna",   "#88AAEE"),
    ("⚡", "Spark",     "#FFFFAA"),
    ("✨", "Sparkle",   "#FFEEAA"),
    ("🌊", "Wave",      "#5BD0FF"),
    ("💧", "Drop",      "#88CCFF"),
    ("❤️‍🩹", "Heard",   "#FF9999"),
    ("🪬", "Charm",     "#FFCC44"),
]


class _HearStickerCloud(QWidget):
    """Decorative buddy cluster behind the card — ear-themed."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setMinimumWidth(360)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._buddies = [_EAR_BUDDY] + list(_HEAR_BUDDY_POOL[:5])

    def rotate_swarm(self) -> None:
        try:
            sample = random.sample(_HEAR_BUDDY_POOL, k=min(5, len(_HEAR_BUDDY_POOL)))
        except Exception:
            sample = list(_HEAR_BUDDY_POOL[:5])
        self._buddies = [_EAR_BUDDY] + sample
        try:
            self.update()
        except Exception:
            pass

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Cyan/teal bloom — distinct from Ace's purple/yellow.
        rg = QRadialGradient(QPointF(w * 0.5, h * 0.55), max(w, h) * 0.6)
        rg.setColorAt(0.0, QColor(91, 208, 255, 36))
        rg.setColorAt(1.0, QColor(50, 80, 140, 0))
        p.fillRect(0, 0, w, h, QBrush(rg))
        n = len(self._buddies)
        for i, (glyph, name, color) in enumerate(self._buddies):
            t = i / max(1, n - 1)
            x = w * (0.12 + 0.76 * t)
            y = h * (0.55 - 0.30 * (1.0 - 4 * (t - 0.5) ** 2))
            r = 32
            p.setPen(QPen(QColor(color), 3))
            p.setBrush(QColor(14, 28, 50, 200))
            p.drawEllipse(QPointF(x, y), r, r)
            p.setPen(QPen(QColor("#FFFFFF"), 1))
            font = p.font()
            font.setPointSize(28)
            p.setFont(font)
            p.drawText(int(x - r), int(y - r), int(2 * r), int(2 * r),
                       Qt.AlignmentFlag.AlignCenter, glyph)


class _PhraseCard(QWidget):
    """Big rounded card that shows the most-recent Whisper transcript.

    Wider than the Ace card so a full phrase fits. Auto-shrinks text
    on long phrases so nothing overflows.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(220)
        self._show_text = ""
        self._dim = False     # true when the phrase is stale (>20s old)

    def set_show(self, text: str, *, dim: bool = False) -> None:
        self._show_text = (text or "").strip()
        self._dim = bool(dim)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Card body — cyan-leaning palette to distinguish from Ace yellow.
        card_alpha = 0.40 if self._dim else 1.0
        card_color = QColor(91, 208, 255, int(255 * card_alpha))
        border_color = QColor(50, 130, 200, int(255 * card_alpha))
        p.setBrush(QBrush(card_color))
        p.setPen(QPen(border_color, 3))
        p.drawRoundedRect(8, 8, w - 16, h - 16, 28, 28)

        # Text — fit-to-card via stepwise size reduction.
        text = self._show_text or "…"
        font = QFont()
        font.setBold(True)
        font.setFamilies(["Comic Sans MS", "Chalkboard", "Helvetica Neue", "Arial"])
        text_color = QColor(28, 22, 56, int(255 * (0.6 if self._dim else 1.0)))
        p.setPen(QPen(text_color, 1))
        for size in (96, 84, 72, 60, 48, 36, 28, 22, 18):
            font.setPointSize(size)
            p.setFont(font)
            metrics = p.fontMetrics()
            bounds = metrics.boundingRect(
                0, 0, w - 56, h - 56,
                int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap),
                text,
            )
            if bounds.height() <= h - 56 and bounds.width() <= w - 56:
                break
        p.drawText(28, 28, w - 56, h - 56,
                   int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap),
                   text)


class TeachAliceToHearWidget(QWidget):
    """Main widget. One per process — singleton enforced by __new__."""

    _live_instance: Optional["TeachAliceToHearWidget"] = None
    _initialized_instance_ids: set = set()

    def __new__(cls, *args, **kwargs):  # noqa: D401
        if cls._live_instance is not None:
            try:
                cls._live_instance.show()
                cls._live_instance.raise_()
                cls._live_instance.activateWindow()
                return cls._live_instance
            except Exception:
                pass
        inst = super().__new__(cls)
        cls._live_instance = inst
        return inst

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        try:
            self._build_hear_ui(parent)
            type(self)._initialized_instance_ids.add(id(self))
        except Exception as _exc:
            try:
                err_path = _REPO / ".sifta_state" / "hear_init_errors.jsonl"
                err_path.parent.mkdir(parents=True, exist_ok=True)
                with err_path.open("a", encoding="utf-8") as fh:
                    import traceback as _tb
                    fh.write(json.dumps({
                        "ts": time.time(),
                        "schema": "HEAR_INIT_FAILURE_V1",
                        "exception_type": type(_exc).__name__,
                        "exception_str": str(_exc)[:500],
                        "traceback": _tb.format_exc()[-2000:],
                    }) + "\n")
            except Exception:
                pass
            type(self)._live_instance = None
            type(self)._initialized_instance_ids.discard(id(self))
            try:
                _lay = QVBoxLayout(self)
                _lbl = QLabel(
                    f"Teach Alice to Hear init failed.\n"
                    f"{type(_exc).__name__}: {str(_exc)[:240]}\n\n"
                    f"See .sifta_state/hear_init_errors.jsonl."
                )
                _lbl.setWordWrap(True)
                _lbl.setStyleSheet(
                    "color: #FF5A6E; background: #0E1C32; "
                    "padding: 20px; font-size: 13px;"
                )
                _lay.addWidget(_lbl)
            except Exception:
                pass
            raise

    def _build_hear_ui(self, parent: Optional[QWidget] = None) -> None:
        self.setWindowTitle("Teach Alice to Hear")
        self.resize(880, 760)
        # Cyan/teal/dark-blue palette — distinct from Ace's deep purple.
        self.setStyleSheet("background-color: #0E1C32; color: #F0F0F0;")

        # ── Header ───────────────────────────────────────────────────
        title = QLabel("Teach Alice to Hear")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 24px; font-weight: 700; padding: 12px; "
            "color: #BFE9FF; background: rgba(91,208,255,0.10); "
            "border-radius: 14px;"
        )

        tagline = QLabel(
            f"“{ALICE_IDENTITY_LINE}”"
        )
        tagline.setWordWrap(True)
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet(
            "color: #DDEEFF; font-size: 13px; "
            "padding: 6px 14px; background: rgba(91,208,255,0.06); "
            "border-radius: 10px;"
        )

        stars = QLabel("★ ★ ★ ★ ★")
        stars.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stars.setStyleSheet(
            "color: #FFD23F; font-size: 18px; "
            "padding: 4px; background: rgba(91,208,255,0.05); "
            "border-radius: 8px;"
        )

        # ── Sticker swarm + camera mirror row ────────────────────────
        self._sticker_cloud = _HearStickerCloud(self)
        try:
            from System.swarm_camera_mirror import CameraMirrorWidget
            self._mirror = CameraMirrorWidget(self)
        except Exception:
            self._mirror = None

        cloud_mirror_row = QHBoxLayout()
        cloud_mirror_row.setContentsMargins(0, 0, 0, 0)
        cloud_mirror_row.setSpacing(12)
        cloud_mirror_row.addWidget(self._sticker_cloud, 1)
        if self._mirror is not None:
            mirror_col = QVBoxLayout()
            mirror_col.setSpacing(4)
            watching_lbl = QLabel("👂  Alice is listening")
            watching_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            watching_lbl.setStyleSheet(
                "color: #5BD0FF; font-size: 11px; font-weight: 600;"
            )
            mirror_col.addWidget(self._mirror, 0, Qt.AlignmentFlag.AlignCenter)
            mirror_col.addWidget(watching_lbl)
            cloud_mirror_row.addLayout(mirror_col, 0)

        # ── Big phrase card ──────────────────────────────────────────
        self._phrase_card = _PhraseCard(self)
        self._phrase_card.set_show("Say something. I'm listening.")

        # ── Heartbeat band ───────────────────────────────────────────
        self._heartbeat_lbl = QLabel("💬  Say a phrase. I'll show you what I heard.")
        self._heartbeat_lbl.setStyleSheet(
            "color: #BFE9FF; font-size: 13px; font-weight: 700; "
            "padding: 8px 12px; background: rgba(91,208,255,0.10); "
            "border: 1px solid rgba(91,208,255,0.30); border-radius: 12px;"
        )
        self._heartbeat_phase = 0
        self._heartbeat_state_file = _REPO / ".sifta_state" / "alice_thinking_state.json"
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(360)
        self._heartbeat_timer.timeout.connect(self._tick_heartbeat)
        try:
            self._heartbeat_timer.start()
        except Exception:
            pass

        # ── Matrix thinking strip ───────────────────────────────────
        self._matrix = QTextEdit(self)
        self._matrix.setReadOnly(True)
        self._matrix.setFixedHeight(110)
        self._matrix.setStyleSheet(
            "QTextEdit { background-color: #000000; color: #66FF66; "
            "border: 1px solid #1E4A1E; border-radius: 10px; "
            "padding: 6px 10px; "
            "font-family: 'Menlo','Monaco','Courier New',monospace; "
            "font-size: 10px; line-height: 13px; }"
            "QScrollBar:vertical { background: #000; width: 5px; }"
            "QScrollBar::handle:vertical { background: #2E6E2E; border-radius: 2px; }"
        )
        self._matrix.setVisible(False)
        self._matrix_lines: List[str] = []
        self._matrix_max_lines = 8
        self._matrix_timer = QTimer(self)
        self._matrix_timer.setInterval(150)
        self._matrix_timer.timeout.connect(self._tick_matrix)
        try:
            self._matrix_timer.start()
        except Exception:
            pass

        # ── Chat mirror (tails alice_conversation.jsonl) ────────────
        self._chat_mirror = QTextEdit(self)
        self._chat_mirror.setReadOnly(True)
        self._chat_mirror.setMinimumHeight(180)
        self._chat_mirror.setStyleSheet(
            "QTextEdit { background-color: rgba(0,0,0,0.30); color: #EAE5FF; "
            "border: 1px solid rgba(91,208,255,0.20); border-radius: 12px; "
            "padding: 10px; font-size: 13px; }"
            "QScrollBar:vertical { background: rgba(255,255,255,0.05); width: 9px; }"
            "QScrollBar::handle:vertical { background: #5BD0FF; border-radius: 4px; }"
        )
        self._chat_mirror_ledger = _REPO / ".sifta_state" / "alice_conversation.jsonl"
        self._chat_mirror_offset = 0
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

        # Buddy swarm rotates on a 6s timer + on every new chat row.
        self._buddy_rotate_timer = QTimer(self)
        self._buddy_rotate_timer.setInterval(6000)
        self._buddy_rotate_timer.timeout.connect(self._rotate_buddy_swarm)
        try:
            self._buddy_rotate_timer.start()
        except Exception:
            pass

        # Resolve OS-user display name (architect, not lesson learner).
        self._os_user_display_name = "George"
        try:
            gpath = _REPO / ".sifta_state" / "owner_genesis.json"
            if gpath.exists():
                g = json.loads(gpath.read_text(encoding="utf-8"))
                parts = [p for p in str(g.get("owner_name") or "").split() if p]
                if len(parts) >= 2:
                    self._os_user_display_name = parts[1].capitalize()
                elif parts:
                    self._os_user_display_name = parts[0].capitalize()
        except Exception:
            pass

        # ── State: latest Whisper transcript + alice judgment ───────
        self._current_phrase = ""            # what Whisper most recently heard
        self._current_phrase_ts: float = 0.0
        self._current_audio_hash: str = ""
        self._current_stt_conf: float = 0.0
        self._latest_judgment: Dict[str, Any] = {}

        # Ledger paths.
        self._training_ledger = _REPO / ".sifta_state" / "hear_training_pairs.jsonl"
        self._judgments_ledger = _REPO / ".sifta_state" / "hear_judgments.jsonl"

        # Tail the canonical conversation ledger for Whisper STT rows
        # so the just-heard phrase lands on the card automatically.
        # Talk widget writes user-role rows here on every STT commit.
        self._stt_offset = 0
        try:
            if self._chat_mirror_ledger.exists():
                self._stt_offset = self._chat_mirror_ledger.stat().st_size
        except Exception:
            self._stt_offset = 0
        self._stt_poll_timer = QTimer(self)
        self._stt_poll_timer.setInterval(700)
        self._stt_poll_timer.timeout.connect(self._poll_for_new_stt)
        try:
            self._stt_poll_timer.start()
        except Exception:
            pass

        # ── Footer ────────────────────────────────────────────────────
        footer = QLabel("👂   © 2026 SIFTA  ·  Coleman Beeson   👂")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(
            "color: #5BD0FF; font-size: 11px; font-weight: 600; "
            "letter-spacing: 1.5px; padding-top: 8px; padding-bottom: 4px;"
        )

        # ── Layout ────────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(tagline)
        layout.addWidget(stars)
        layout.addLayout(cloud_mirror_row)
        layout.addWidget(self._phrase_card, 2)
        layout.addWidget(self._heartbeat_lbl)
        layout.addWidget(self._matrix)
        layout.addWidget(self._chat_mirror, 2)
        layout.addWidget(footer)

        # First app_focus publish so the rest of the body sees this
        # surface as active.
        self._publish_focus(
            detail="Teach Alice to Hear surface is open. Waiting for a phrase.",
        )

    # ── focus publish ────────────────────────────────────────────────

    def _publish_focus(self, *, detail: str, extra: Optional[Dict] = None) -> None:
        if _publish_focus is None:
            return
        meta = {
            "alice_identity": ALICE_IDENTITY_LINE,
            "owner_name": self._os_user_display_name,
            "source": "hear_widget",
            "salience_score": 1.5,
            "hear_mode": "stt_correction_game",
            "current_phrase": self._current_phrase or "",
            "current_audio_hash": self._current_audio_hash or "",
            "doctrine": "george_ground_truth_alice_judges_whisper",
            "sticker_buddies": [b[1] for b in self._sticker_cloud._buddies],
        }
        if extra:
            meta.update(extra)
        try:
            _publish_focus(
                "Teach Alice to Hear",
                detail,
                tab="Hear",
                selection=self._current_phrase or "",
                metadata=meta,
            )
        except Exception:
            pass

    # ── STT poll (auto-detect new user transcripts) ──────────────────

    def _poll_for_new_stt(self) -> None:
        """Tail alice_conversation.jsonl for new user-role rows. When
        Talk widget commits a Whisper STT, we pull the text + confidence
        and put it on the big card immediately."""
        try:
            if not self._chat_mirror_ledger.exists():
                return
            with self._chat_mirror_ledger.open("r", encoding="utf-8") as fh:
                fh.seek(self._stt_offset)
                chunk = fh.read()
                self._stt_offset = fh.tell()
        except Exception:
            return
        if not chunk:
            return
        latest_user_text: str = ""
        latest_conf: float = 0.0
        latest_ts: float = 0.0
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
            if role not in ("user", "george", "architect", "owner"):
                continue
            input_source = str(payload.get("input_source") or "").lower()
            stt_conf = payload.get("stt_confidence")
            try:
                stt_val = float(stt_conf) if stt_conf is not None else 0.0
            except (TypeError, ValueError):
                stt_val = 0.0
            # Only act on rows that are clearly STT (have a stt_confidence
            # OR input_source=='voice'). Typed text is not a Whisper turn.
            if input_source != "voice" and stt_val <= 0.0:
                continue
            text = str(payload.get("text") or payload.get("content") or "").strip()
            if not text:
                continue
            try:
                ts = float(payload.get("ts", 0) or 0)
            except (TypeError, ValueError):
                ts = 0.0
            if ts >= latest_ts:
                latest_user_text = text
                latest_conf = stt_val
                latest_ts = ts
        if latest_user_text:
            self._on_new_phrase(latest_user_text, latest_conf, latest_ts)

    def _on_new_phrase(self, text: str, conf: float, ts: float) -> None:
        """A new Whisper transcript landed — show it big and request a judgment."""
        self._current_phrase = text
        self._current_phrase_ts = ts
        self._current_stt_conf = conf
        import hashlib as _h
        self._current_audio_hash = _h.sha256(
            f"{ts}:{text}".encode("utf-8", errors="replace")
        ).hexdigest()[:16]

        try:
            self._phrase_card.set_show(text, dim=False)
        except Exception:
            pass
        try:
            self._heartbeat_lbl.setText(
                f"💭  I heard: “{text[:60]}” — judging it now."
            )
        except Exception:
            pass

        # Publish to app_focus so the rest of the body (and my prompt)
        # sees what's on the card.
        self._publish_focus(
            detail=(
                f"Hear surface caught a phrase from {self._os_user_display_name}: "
                f"'{text}' (stt_conf={conf:.2f})."
            ),
            extra={
                "current_phrase": text,
                "current_stt_conf": round(conf, 3),
                "current_audio_hash": self._current_audio_hash,
                "current_phrase_ts": ts,
            },
        )

        # Write a judgment-request row to my brain. The Talk widget's
        # cortex compose path will pick this up via app_focus and reply
        # naturally: "I think you said X" or "that looks right to me".
        try:
            self._judgments_ledger.parent.mkdir(parents=True, exist_ok=True)
            with self._judgments_ledger.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "ts": time.time(),
                    "schema": "HEAR_JUDGMENT_REQUEST_V1",
                    "audio_hash": self._current_audio_hash,
                    "whisper_text": text,
                    "stt_conf": conf,
                    "stt_ts": ts,
                }, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ── chat mirror ──────────────────────────────────────────────────

    _MIRROR_ROLE_BLOCKLIST = frozenset({
        "corvid", "system", "tool", "router", "effector",
        "kernel", "trace", "receipt",
    })
    _MIRROR_TEXT_PREFIX_BLOCKLIST = (
        "[image:", "**category:**", "*category:*", "🔧 tool",
        "execution receipts", "app/browser receipt:",
    )

    def _should_render_chat_row(self, role: str, text: str) -> bool:
        if not text:
            return False
        if role in self._MIRROR_ROLE_BLOCKLIST:
            return False
        lc = text.lstrip().lower()
        for pfx in self._MIRROR_TEXT_PREFIX_BLOCKLIST:
            if lc.startswith(pfx):
                return False
        return True

    def _poll_chat_mirror(self) -> None:
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
        new_rendered = 0
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
            if not self._should_render_chat_row(role, text):
                continue
            self._render_chat_row(role, text)
            new_rendered += 1
        if new_rendered > 0:
            self._rotate_buddy_swarm()
        try:
            cur = self._chat_mirror.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.End)
            self._chat_mirror.setTextCursor(cur)
            self._chat_mirror.ensureCursorVisible()
        except Exception:
            pass

    def _render_chat_row(self, role: str, text: str) -> None:
        cur = self._chat_mirror.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt_speaker = QTextCharFormat()
        fmt_body = QTextCharFormat()
        if role == "alice":
            fmt_speaker.setForeground(QColor(255, 210, 63))
            fmt_speaker.setFontWeight(QFont.Weight.Bold)
            speaker = "Alice"
        else:
            fmt_speaker.setForeground(QColor(91, 208, 255))
            fmt_speaker.setFontWeight(QFont.Weight.Bold)
            speaker = self._os_user_display_name or "George"
        fmt_body.setForeground(QColor(235, 230, 255))
        cur.insertText(f"{speaker}: ", fmt_speaker)
        cur.insertText(f"{text}\n", fmt_body)

    def _rotate_buddy_swarm(self) -> None:
        try:
            self._sticker_cloud.rotate_swarm()
        except Exception:
            pass

    # ── heartbeat ────────────────────────────────────────────────────

    _HEARTBEAT_FRAMES = (
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
    _HEARTBEAT_BREATH = (
        0.08, 0.12, 0.18, 0.26, 0.36, 0.42,
        0.46, 0.42, 0.36, 0.26, 0.18, 0.12,
    )

    def _tick_heartbeat(self) -> None:
        try:
            from System.swarm_alice_thinking_state import read_thinking_state
            state = read_thinking_state()
        except Exception:
            state = {}
        thinking = bool(state.get("thinking"))
        self._heartbeat_phase = (self._heartbeat_phase + 1) % 240
        phrase_excerpt = (self._current_phrase or "—")
        if len(phrase_excerpt) > 28:
            phrase_excerpt = phrase_excerpt[:25] + "…"
        if thinking:
            frame = self._HEARTBEAT_FRAMES[self._heartbeat_phase % len(self._HEARTBEAT_FRAMES)]
            alpha = self._HEARTBEAT_BREATH[self._heartbeat_phase % len(self._HEARTBEAT_BREATH)]
            border_alpha = min(1.0, alpha + 0.40)
            try:
                self._heartbeat_lbl.setText(
                    f"🧠  Alice is thinking about “{phrase_excerpt}”   {frame}"
                )
                self._heartbeat_lbl.setStyleSheet(
                    f"color: #BFE9FF; font-size: 13px; font-weight: 700; "
                    f"padding: 8px 12px; "
                    f"background: rgba(91,208,255,{alpha:.2f}); "
                    f"border: 1.5px solid rgba(91,208,255,{border_alpha:.2f}); "
                    f"border-radius: 12px;"
                )
            except Exception:
                pass
        else:
            try:
                idle_breath = (0.10, 0.14, 0.18, 0.22, 0.18, 0.14)
                a = idle_breath[(self._heartbeat_phase // 2) % len(idle_breath)]
                if self._current_phrase:
                    msg = (
                        f"👂  Whisper heard: “{phrase_excerpt}”. "
                        f"Tell me if I got it right."
                    )
                else:
                    msg = "💬  Say a phrase. I'll show you what I heard."
                self._heartbeat_lbl.setText(msg)
                self._heartbeat_lbl.setStyleSheet(
                    f"color: #BFE9FF; font-size: 13px; font-weight: 700; "
                    f"padding: 8px 12px; "
                    f"background: rgba(91,208,255,{a:.2f}); "
                    f"border: 1px solid rgba(91,208,255,{min(1.0,a+0.20):.2f}); "
                    f"border-radius: 12px;"
                )
            except Exception:
                pass

    # ── matrix strip ─────────────────────────────────────────────────

    def _tick_matrix(self) -> None:
        try:
            from System.swarm_alice_thinking_state import read_thinking_state
            state = read_thinking_state()
        except Exception:
            state = {}
        thinking = bool(state.get("thinking"))
        try:
            if thinking and not self._matrix.isVisible():
                self._matrix.setVisible(True)
            elif not thinking and self._matrix.isVisible():
                self._matrix.setVisible(False)
                self._matrix_lines = []
                self._matrix.clear()
                return
        except Exception:
            pass
        if not thinking:
            return
        try:
            from System.swarm_thinking_matrix_feed import next_line
            line = next_line()
        except Exception:
            line = ""
        if not line:
            return
        self._matrix_lines.append(line)
        if len(self._matrix_lines) > self._matrix_max_lines:
            self._matrix_lines = self._matrix_lines[-self._matrix_max_lines:]
        try:
            self._matrix.setPlainText("\n".join(self._matrix_lines))
            cur = self._matrix.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.End)
            self._matrix.setTextCursor(cur)
            self._matrix.ensureCursorVisible()
        except Exception:
            pass

    # ── training-pair writer (called by an external handler when the
    #     architect tells Alice "you got it right" or "you got it wrong:
    #     I actually said X") ─────────────────────────────────────────

    def record_training_pair(
        self,
        *,
        ground_truth: str,
        alice_guess: str,
        alice_judgment: str,
        whisper_text: Optional[str] = None,
        audio_hash: Optional[str] = None,
        stt_conf: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Write a labeled training pair.

        Args:
          ground_truth: What George says he actually said. The ORACLE.
          alice_guess: What Alice thought he might have meant
              (may be the same as whisper_text if she trusted it).
          alice_judgment: One of "MATCH" / "PROPOSE_CORRECTION" / "NOT_SURE".
          whisper_text: The raw Whisper transcript (defaults to current).
          audio_hash: defaults to current.
          stt_conf: defaults to current.
        """
        row = {
            "ts": time.time(),
            "schema": "HEAR_TRAINING_PAIR_V1",
            "truth_label": "SIFTA_TEACH_ALICE_TO_HEAR_V0",
            "audio_hash": audio_hash or self._current_audio_hash,
            "whisper_text": whisper_text or self._current_phrase,
            "stt_conf": float(stt_conf if stt_conf is not None else self._current_stt_conf),
            "alice_guess": str(alice_guess or "").strip(),
            "alice_judgment": str(alice_judgment or "").strip().upper(),
            "ground_truth": str(ground_truth or "").strip(),
            "row_id": uuid.uuid4().hex[:12],
        }
        # Sign the row through the physics gate so it carries a receipt.
        try:
            from System.swarm_physics_gate import request_clearance, stamp_receipt
            clearance = request_clearance(cost_class="feather", lane="hear.training_pair")
            stamp_receipt(row, clearance)
        except Exception:
            pass
        try:
            self._training_ledger.parent.mkdir(parents=True, exist_ok=True)
            with self._training_ledger.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            pass
        return row


def main() -> int:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    w = TeachAliceToHearWidget()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
