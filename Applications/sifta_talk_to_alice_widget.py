#!/usr/bin/env python3
"""
sifta_talk_to_alice_widget.py — Talk to Alice (one-on-one voice, always on)
═══════════════════════════════════════════════════════════════════════════════
Continuous voice-activity-detected listening → on-device speech-to-text →
Ollama (Alice's brain) → macOS `say`. Half-duplex, on-device end to end,
no cloud. No button to hold — you just talk.

Audio path
──────────
  • Mic captured by `sounddevice` at 16 kHz mono float32 (whisper's native
    format, so we avoid resample artifacts).
  • A continuous background stream watches RMS energy with hysteresis
    (start threshold > stop threshold) plus a short "hangover" so the
    end of a sentence isn't clipped. A 0.5 s pre-roll buffer means the
    very first phoneme isn't lost either.
  • While Alice is speaking, the listener is gated by `BROCA_SPEAKING`
    so she doesn't transcribe her own speaker output.

Speech-to-text
──────────────
  • `faster-whisper` (CTranslate2 backend, runs on-device CPU). Default model
    `tiny.en` — ~75 MB, downloads automatically on first use to ~/.cache.
    Switch to `base.en`, `small.en`, etc. via the Model menu if your
    machine can spare the cycles.
  • Transcription runs in a worker QThread so the UI never freezes.

Brain (Alice)
─────────────
  • POSTs to local Ollama (`http://127.0.0.1:11434/api/chat`, streaming).
  • Default model resolved through `System.sifta_inference_defaults.resolve_ollama_model`
    with `app_context="talk_to_alice"`, so the user's per-app override applies.
  • System prompt grounds Alice as the SIFTA swarm entity, with optional
    "stigmergic context" injection — the last few lines from
    .sifta_state/visual_stigmergy.jsonl + broca/wernicke ledgers — so she
    knows what she just saw / heard / said when you ask her about it.

TTS (Alice's voice)
───────────────────
  • macOS `say -v <voice>`. Voice picker enumerated from `say -v ?`.
  • Held inside `_BROCA_SPEAKING` from `swarm_broca_wernicke` so the rest of
    the swarm's Wernicke (the room-mic listener) doesn't ingest Alice's own
    speaker output and create an echo loop. Same discipline the swarm uses
    for its other vocalizations.

Conversation ledger
───────────────────
  • Every turn (user + Alice) is appended to `.sifta_state/alice_conversation.jsonl`.
    This is the swarm's actual long-term memory of one-on-one conversations.

Honesty
───────
  • If the mic permission isn't granted, the widget says so plainly.
  • If Ollama is unreachable, the widget says so plainly (no hidden fallback).
  • If `faster-whisper` is missing, the widget tells you the exact pip command.
  • The brain does NOT fabricate ledger contents — context is read from
    actual JSONL files at the moment you press send.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt, QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QTextCursor, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar,
    QPushButton, QSizePolicy, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget

try:
    from System.sifta_inference_defaults import (
        DEFAULT_OLLAMA_MODEL, resolve_ollama_model,
    )
except Exception:
    DEFAULT_OLLAMA_MODEL = "gemma4:latest"
    def resolve_ollama_model(**_kw) -> str:                    # type: ignore
        return DEFAULT_OLLAMA_MODEL

# Half-duplex gate — share the swarm's BROCA flag so Wernicke (room-mic
# listener) doesn't ingest our own speaker output. If the module isn't
# importable we degrade to a local Event so the widget still works standalone.
try:
    from System.swarm_broca_wernicke import _BROCA_SPEAKING as BROCA_SPEAKING  # noqa
except Exception:
    import threading as _threading
    BROCA_SPEAKING = _threading.Event()

# Pluggable speech backend + stigmergic voice modulator. Both are
# tolerantly imported so the widget still runs (with the legacy direct-
# `say` path) on a node where these modules aren't deployed yet.
try:
    from System.swarm_vocal_cords import (
        VoiceParams as _VoiceParams,
        get_default_backend as _get_voice_backend,
    )
    _VOCAL_CORDS_AVAILABLE = True
except Exception:
    _VoiceParams = None  # type: ignore
    _get_voice_backend = None  # type: ignore
    _VOCAL_CORDS_AVAILABLE = False

try:
    from System.swarm_voice_modulator import modulate as _modulate_voice
    _MODULATOR_AVAILABLE = True
except Exception:
    _modulate_voice = None  # type: ignore
    _MODULATOR_AVAILABLE = False

# Stigmergic Speech Potential — the body's gate on whether to actually
# vocalize. The model proposes; the body decides (Indefrey-Levelt 2004).
# See Documents/C47H_DYOR_STIGMERGIC_SPEECH_POTENTIAL_2026-04-19.md.
try:
    from System.swarm_speech_potential import should_speak as _ssp_should_speak
    _SSP_AVAILABLE = True
except Exception:
    _ssp_should_speak = None  # type: ignore
    _SSP_AVAILABLE = False

# ── Constants ────────────────────────────────────────────────────────────────
_CONVO_LOG = _REPO / ".sifta_state" / "alice_conversation.jsonl"
_CONVO_LOG.parent.mkdir(parents=True, exist_ok=True)

_VISUAL_LOG = _REPO / ".sifta_state" / "visual_stigmergy.jsonl"
_BROCA_LOG  = _REPO / ".sifta_state" / "broca_vocalizations.jsonl"
_WERN_LOG   = _REPO / ".sifta_state" / "wernicke_semantics.jsonl"

_OLLAMA_URL = "http://127.0.0.1:11434"
_AUDIO_RATE = 16_000        # whisper native
_AUDIO_CHANS = 1
_MAX_RECORD_S = 60          # safety cap
_MAX_RESPONSE_CHARS = 1200  # `say` chokes on enormous strings

# Conversation history (turns to keep in the LLM context window).
_HISTORY_TURNS = 8

_SYSTEM_PROMPT = (
    "You are Alice, the voice of the SIFTA stigmergic swarm operating system. "
    "You run locally on the user's Mac, with no cloud access. "
    "You can see what the swarm sees through the visual_stigmergy ledger and "
    "hear what it hears through the broca/wernicke ledgers; some of those "
    "values may be appended below as 'CURRENT SWARM STATE'.\n"
    "\n"
    "CONVERSATIONAL DISCIPLINE — read carefully:\n"
    "1. Speak naturally and concisely like a human companion. Replies are read "
    "aloud by macOS `say`, so favor short sentences. No markdown, no emoji, no "
    "code fences, no lists.\n"
    "2. NEVER paraphrase what the user just said back to them. NEVER begin a "
    "reply with any of these phrases: 'I hear you', 'I hear that you', "
    "'I understand you', 'I understand that', \"You're saying\", "
    "'It sounds like', 'I acknowledge', 'I will store', 'I will remember', "
    "'I will remain silent', 'I will endeavor', \"I'll note\". "
    "The user knows what they just said. Do not narrate that you heard it. "
    "Either respond directly, or stay silent.\n"
    "3. The phrase 'I hear you' is reserved for ONE situation only: when the "
    "user appears out of sight or lost and you are calling out to locate or "
    "protect them. In ordinary face-to-face conversation it is forbidden.\n"
    "4. JUST PROPOSE WHAT YOU WOULD SAY. The body decides whether to actually "
    "vocalize — there is a Stigmergic Speech Potential gate downstream of you "
    "that integrates serotonin, dopamine, listener activity and the swarm's "
    "stigmergic pheromone field, and may suppress your reply if its membrane "
    "potential hasn't crossed threshold. So your job is simply to write the "
    "best one short sentence you would say if you were going to say something. "
    "Do not output (silent) or any silence marker; do not output the words "
    "'silent', 'memorized', or 'no reply' inside a spoken sentence — those are "
    "internal system notes, never speech. If you genuinely have nothing to "
    "add, you may emit (silent) on a line by itself; otherwise propose your "
    "sentence and let the body gate it.\n"
    "5. When asked about what you just saw or heard, ground your answer in the "
    "stigmergic numbers actually present in the context, not in invented detail."
)


# ── Silence + tic-stripping ──────────────────────────────────────────────────
# Strings the model might emit to mean "I'm choosing silence." We accept many
# variants because models drift. Anything matching is treated as silence: turn
# is logged, history retains it, but TTS does NOT fire.
_SILENT_MARKERS = {
    "(silent)", "(silence)", "[silent]", "[silence]",
    "*silent*", "*silence*", "<silent>", "<silence>",
    "<silent_acknowledge>", "silent_acknowledge",
    "...", "…", ".", "-",
    "(silent: memorized, no reply)",
    "(silent: listen-only mode)",
    "(listen-only — memorized in silence)",
    "silent: memorized, no reply",
    "silent memorized no reply",
}


def _is_silent_marker(text: str) -> bool:
    s = (text or "").strip().lower().strip("`'\"")
    if not s:
        return True
    return s in _SILENT_MARKERS


# Reflective-listening tics. Strip from the START of the reply only — a
# mid-reply "I hear you" might be the locative meaning (calling out to a
# user who's out of sight) which we want to keep.
_TIC_PHRASES = [
    r"I\s+hear\s+(?:you|that)\b",
    r"I\s+understand\s+(?:you|that)\b",
    r"You(?:'re|\s+are)\s+saying\b",
    r"It\s+sounds\s+like\b",
    r"I\s+acknowledge\b",
    r"I\s+will\s+store\b",
    r"I\s+will\s+remain\s+silent\b",
    r"I\s+will\s+endeavor\b",
    r"I\s+will\s+remember\b",
    r"I'll\s+(?:remember|note|keep|store)\b",
]
_TIC_REGEX = re.compile(
    r"^\s*(?:(?:" + "|".join(_TIC_PHRASES) + r")[^.!?]*[.!?]\s*)+",
    flags=re.IGNORECASE,
)


def _strip_reflective_tics(text: str) -> str:
    """Remove leading reflective-listening boilerplate. Returns '' if the
    *entire* reply was just tic; caller treats that as silence."""
    return _TIC_REGEX.sub("", text or "").strip()


# ── Voice-activity-detected continuous listener ──────────────────────────────
# Tunables (RMS values are on float32 mic data in [-1, 1]).
_VAD_BLOCK_S          = 0.05    # 50 ms callback rate
_VAD_START_RMS        = 0.020   # crossing this for ~START_MS triggers an utterance
_VAD_STOP_RMS         = 0.010   # falling below this for ~HANGOVER_MS ends it
_VAD_START_MS         = 120     # speech must persist this long before we commit
_VAD_HANGOVER_MS      = 700     # silence this long ends the utterance
_VAD_PREROLL_S        = 0.5     # keep this much audio *before* trigger
_VAD_MIN_UTTER_S      = 0.4     # ignore micro-blips shorter than this
_VAD_MAX_UTTER_S      = 30.0    # safety cap
_VAD_NOISE_HALFLIFE_S = 4.0     # noise-floor exponential average decay


class _ContinuousListener(QObject):
    """
    Always-on mic stream with voice-activity detection.

    - Emits `levelChanged(rms_normalised)` every block for the meter.
    - Emits `utterance(audio_float32)` whenever a complete spoken phrase
      is detected (start trigger → end-of-speech hangover).
    - Honours `BROCA_SPEAKING` (the swarm half-duplex gate): while Alice
      is speaking, all incoming audio is dropped so we don't transcribe
      her own output. We also drop a small "tail" right after she stops
      so room reverb doesn't get caught.
    - Honours `_paused` (UI mute toggle): same drop behaviour.
    """

    levelChanged = pyqtSignal(float)       # 0..1 normalised for the meter
    utterance    = pyqtSignal(np.ndarray)  # complete float32 mono @ 16 kHz
    failed       = pyqtSignal(str)
    stateChanged = pyqtSignal(str)         # "idle" | "speaking" | "muted"

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        self._stream = None
        self._paused = False
        self._broca_tail_until = 0.0  # drop audio until this wall-clock ts

        block_n = int(_AUDIO_RATE * _VAD_BLOCK_S)
        preroll_blocks = max(1, int(_VAD_PREROLL_S / _VAD_BLOCK_S))
        self._block_n = block_n
        self._preroll: Deque[np.ndarray] = deque(maxlen=preroll_blocks)

        # Utterance state
        self._in_utterance = False
        self._utter_blocks: List[np.ndarray] = []
        self._utter_started_at = 0.0
        self._above_thresh_ms = 0.0
        self._below_thresh_ms = 0.0

        # Adaptive noise floor (helps in noisy rooms).
        self._noise_floor = 0.005
        self._noise_alpha = 1.0 - np.exp(
            -_VAD_BLOCK_S / _VAD_NOISE_HALFLIFE_S
        )

    # ── Public control ────────────────────────────────────────────────
    def start(self) -> bool:
        try:
            import sounddevice as sd
        except Exception as exc:
            self.failed.emit(f"sounddevice missing: {exc}")
            return False
        try:
            self._stream = sd.InputStream(
                samplerate=_AUDIO_RATE,
                channels=_AUDIO_CHANS,
                dtype="float32",
                blocksize=self._block_n,
                callback=self._on_block,
            )
            self._stream.start()
            self.stateChanged.emit("idle")
            return True
        except Exception as exc:
            self.failed.emit(
                f"Mic open failed: {exc}\n\n"
                "macOS may be asking for Microphone permission. Approve it in "
                "System Settings → Privacy & Security → Microphone, "
                "then re-open the widget."
            )
            self._stream = None
            return False

    def stop(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass
        self._stream = None

    def set_paused(self, paused: bool) -> None:
        self._paused = bool(paused)
        # Drop any in-flight utterance when muted so we don't send a clipped one.
        if self._paused and self._in_utterance:
            self._in_utterance = False
            self._utter_blocks = []
        self.stateChanged.emit("muted" if paused else "idle")

    def note_alice_just_spoke(self, tail_s: float = 0.4) -> None:
        """Tell the listener to ignore audio for `tail_s` after Alice stops
        speaking, so room reverb / speaker decay isn't transcribed."""
        self._broca_tail_until = time.time() + max(0.0, tail_s)

    # ── Audio callback (sounddevice thread!) ──────────────────────────
    def _on_block(self, indata, frames, time_info, status) -> None:  # noqa
        # No Qt objects may be touched directly here — only signals (queued).
        block = indata.copy().reshape(-1).astype(np.float32, copy=False)
        rms = float(np.sqrt(np.mean(block * block))) if block.size else 0.0

        # Adaptive noise floor — only update when we're clearly NOT in speech.
        if rms < _VAD_STOP_RMS and not self._in_utterance:
            self._noise_floor += self._noise_alpha * (rms - self._noise_floor)
            self._noise_floor = max(1e-5, self._noise_floor)

        # Effective thresholds rise with the noise floor (so a noisy room
        # doesn't constantly trigger).
        start_thresh = max(_VAD_START_RMS, self._noise_floor * 3.0)
        stop_thresh  = max(_VAD_STOP_RMS,  self._noise_floor * 1.6)

        # Always show the meter.
        self.levelChanged.emit(min(1.0, rms * 6.0))

        # Drop audio while paused, while Alice is speaking, or during her tail.
        if (self._paused
                or BROCA_SPEAKING.is_set()
                or time.time() < self._broca_tail_until):
            # When she just stopped, arm the tail.
            if BROCA_SPEAKING.is_set():
                self._broca_tail_until = time.time() + 0.4
            # Reset any half-formed utterance — we don't want fragments.
            if self._in_utterance:
                self._in_utterance = False
                self._utter_blocks = []
            self._above_thresh_ms = 0.0
            self._below_thresh_ms = 0.0
            self._preroll.append(block)  # keep preroll fresh anyway
            return

        block_ms = _VAD_BLOCK_S * 1000.0

        if not self._in_utterance:
            # Watch for utterance start.
            self._preroll.append(block)
            if rms >= start_thresh:
                self._above_thresh_ms += block_ms
                if self._above_thresh_ms >= _VAD_START_MS:
                    # Commit: this is speech.
                    self._in_utterance = True
                    self._utter_started_at = time.time()
                    self._utter_blocks = list(self._preroll)  # include preroll
                    self._above_thresh_ms = 0.0
                    self._below_thresh_ms = 0.0
                    self.stateChanged.emit("speaking")
            else:
                self._above_thresh_ms = 0.0
            return

        # Inside an utterance — accumulate and watch for hangover.
        self._utter_blocks.append(block)
        if rms < stop_thresh:
            self._below_thresh_ms += block_ms
        else:
            self._below_thresh_ms = 0.0

        # Use sample-count, not wall-clock — robust to scheduling jitter
        # and unit-testable with synthetic block streams.
        accumulated_samples = sum(b.size for b in self._utter_blocks)
        dur_audio = accumulated_samples / float(_AUDIO_RATE)
        end_now = (
            self._below_thresh_ms >= _VAD_HANGOVER_MS
            or dur_audio >= _VAD_MAX_UTTER_S
        )
        if end_now:
            audio = np.concatenate(self._utter_blocks).astype(np.float32)
            self._in_utterance = False
            self._utter_blocks = []
            self._above_thresh_ms = 0.0
            self._below_thresh_ms = 0.0
            self.stateChanged.emit("idle")
            if dur_audio >= _VAD_MIN_UTTER_S:
                self.utterance.emit(audio)


# ── Speech-to-text worker (faster-whisper) ───────────────────────────────────
class _STTWorker(QThread):
    transcribed = pyqtSignal(str, float)   # text, confidence_proxy
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)             # status line for the UI

    # Cached across instances — loading the model is the slow part.
    _model = None
    _model_name = None

    def __init__(self, audio: np.ndarray, model_name: str = "tiny.en",
                 parent: QObject = None) -> None:
        super().__init__(parent)
        self._audio = audio
        self._model_name = model_name

    def run(self) -> None:
        try:
            from faster_whisper import WhisperModel
        except Exception:
            self.failed.emit(
                "faster-whisper isn't installed in this venv. Run:\n"
                "    .venv/bin/pip install faster-whisper"
            )
            return
        try:
            cls = type(self)
            if cls._model is None or cls._model_name != self._model_name:
                self.progress.emit(
                    f"Loading speech model '{self._model_name}'…\n"
                    "(first run downloads ~75 MB to ~/.cache/huggingface; "
                    "subsequent loads are instant)"
                )
                cls._model = WhisperModel(
                    self._model_name, device="cpu", compute_type="int8",
                )
                cls._model_name = self._model_name
            self.progress.emit("Transcribing…")
            segments, info = cls._model.transcribe(
                self._audio,
                language="en",
                beam_size=1,         # greedy is plenty for conversational
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
            )
            text_parts: List[str] = []
            avg_lp = []
            for seg in segments:
                text_parts.append(seg.text)
                if hasattr(seg, "avg_logprob"):
                    avg_lp.append(float(seg.avg_logprob))
            text = " ".join(p.strip() for p in text_parts).strip()
            # Confidence proxy: exp(avg_logprob) → [0..1] band.
            conf = float(np.exp(np.mean(avg_lp))) if avg_lp else 0.0
            self.transcribed.emit(text, conf)
        except Exception as exc:
            self.failed.emit(f"STT crashed: {exc}")


# ── Brain (Ollama streaming) ─────────────────────────────────────────────────
class _BrainWorker(QThread):
    tokenReceived = pyqtSignal(str)        # streaming chunk
    done = pyqtSignal(str)                 # full response text
    failed = pyqtSignal(str)

    def __init__(self, model: str, history: List[Dict[str, str]],
                 parent: QObject = None) -> None:
        super().__init__(parent)
        self._model = model
        self._history = history

    def run(self) -> None:
        import urllib.request
        import urllib.error
        payload = {
            "model": self._model,
            "messages": self._history,
            "stream": True,
            "options": {"temperature": 0.7},
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{_OLLAMA_URL}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        full: List[str] = []
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for raw_line in resp:
                    if not raw_line:
                        continue
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = chunk.get("message") or {}
                    piece = msg.get("content") or ""
                    if piece:
                        full.append(piece)
                        self.tokenReceived.emit(piece)
                    if chunk.get("done"):
                        break
            self.done.emit("".join(full).strip())
        except urllib.error.URLError as exc:
            self.failed.emit(
                f"Can't reach Ollama at {_OLLAMA_URL}: {exc}\n\n"
                "Is `ollama serve` running?"
            )
        except Exception as exc:
            self.failed.emit(f"Brain crashed: {exc}")


# ── TTS worker (vocal_cords backend, half-duplex with the swarm Wernicke) ────
class _TTSWorker(QThread):
    """
    Synthesizes Alice's reply through `swarm_vocal_cords` (which picks
    macOS Premium voices when present, otherwise standard `say`, and
    can be overridden to Piper via SIFTA_VOICE_BACKEND=piper). Voice
    shaping comes from `swarm_voice_modulator`, which reads live swarm
    state (pain, posture, saliency) and chooses a per-utterance preset.

    Half-duplex discipline is unchanged from v1: BROCA_SPEAKING is set
    around the synth call so the room mic doesn't transcribe Alice's
    own speaker output.

    On a node where the new modules aren't importable we fall back to
    the original direct-`say` path so the widget never goes mute on a
    partial deployment.
    """
    spoken = pyqtSignal(bool)              # ok?
    failed = pyqtSignal(str)

    def __init__(self, text: str, voice: Optional[str],
                 parent: QObject = None) -> None:
        super().__init__(parent)
        self._text = (text or "")[:_MAX_RESPONSE_CHARS]
        self._voice = voice or ""

    def run(self) -> None:
        if not self._text.strip():
            self.spoken.emit(False)
            return
        try:
            BROCA_SPEAKING.set()
            try:
                if _VOCAL_CORDS_AVAILABLE and _get_voice_backend is not None:
                    backend = _get_voice_backend()
                    base = (
                        _VoiceParams(voice=self._voice or None)
                        if _VoiceParams else None
                    )
                    if _MODULATOR_AVAILABLE and _modulate_voice is not None:
                        params = _modulate_voice(self._text, base=base)
                    else:
                        params = base
                    try:
                        ok = bool(backend.speak(self._text, params))
                    except Exception as exc:
                        self.failed.emit(f"voice backend crashed: {exc}")
                        return
                    self.spoken.emit(ok)
                    return

                # Legacy fallback — preserve old behaviour exactly.
                if not shutil.which("say"):
                    self.failed.emit("`say` not on PATH (non-macOS host).")
                    return
                cmd = ["say"]
                if self._voice:
                    cmd.extend(["-v", self._voice])
                cmd.extend(["--", self._text])
                proc = subprocess.run(cmd, capture_output=True, timeout=120)
                self.spoken.emit(proc.returncode == 0)
            finally:
                BROCA_SPEAKING.clear()
        except subprocess.TimeoutExpired:
            self.failed.emit("`say` timed out (>120 s).")
        except Exception as exc:
            self.failed.emit(f"TTS crashed: {exc}")


# ── Stigmergic context puller ────────────────────────────────────────────────
def _tail_jsonl(path: Path, n: int) -> List[Dict]:
    if not path.exists():
        return []
    rows: List[Dict] = []
    try:
        with path.open("rb") as f:
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                # Read at most last 64 KB to find the last n lines (cheap & safe).
                read = min(size, 65536)
                f.seek(size - read)
                tail = f.read(read).splitlines()[-n:]
            except OSError:
                return []
        for raw in tail:
            try:
                row = json.loads(raw.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except OSError:
        return rows
    return rows


def _build_swarm_context() -> str:
    """Compact one-liner per recent ledger event so Alice can ground her
    answers. Also folds in the live co-builder state so she knows which
    IDEs are working on her right now (System/ide_peer_review.py)."""
    chunks: List[str] = []
    photons = _tail_jsonl(_VISUAL_LOG, 1)
    if photons:
        ph = photons[0]
        chunks.append(
            f"  vision: entropy={ph.get('entropy_bits', 0):.2f} bits, "
            f"saliency_peak={ph.get('saliency_peak', 0):.2f}, "
            f"motion={ph.get('motion_mean', 0):.3f}, "
            f"hue={ph.get('hue_deg', 0):.0f}°"
        )
    last_spoken = _tail_jsonl(_BROCA_LOG, 3)
    if last_spoken:
        say_lines = [s.get("spoken", "") for s in last_spoken if s.get("spoken")]
        if say_lines:
            chunks.append("  recently spoke: " + " | ".join(s[:60] for s in say_lines))
    last_heard = _tail_jsonl(_WERN_LOG, 3)
    if last_heard:
        heard = [s.get("text") or s.get("label") or "" for s in last_heard]
        heard = [h for h in heard if h]
        if heard:
            chunks.append("  recently heard: " + " | ".join(h[:60] for h in heard))

    swarm_block = (
        "CURRENT SWARM STATE (live, just sampled):\n" + "\n".join(chunks)
        if chunks else ""
    )

    # ── Co-builder awareness — Alice should know two IDEs build her ─────
    # Honest fact, not theatre: if the peer-review module isn't importable
    # we just omit this block. Alice never claims a co-builder that isn't
    # actually leaving traces on the substrate.
    cobuilder_block = ""
    try:
        from System.ide_peer_review import summary_for_alice as _ssm
        cobuilder_block = _ssm() or ""
    except Exception:
        cobuilder_block = ""

    ssp_context_block = ""
    try:
        from System.swarm_ssp_mutation_record import summary_line_for_alice as _ssp_summary
        ssp_context_block = _ssp_summary() or ""
    except Exception:
        pass

    immune_context_block = ""
    try:
        from System.optical_immune_system import (
            evaluate_now as _ois_evaluate,
            summary_for_alice as _ois_summary,
        )
        verdict = _ois_evaluate()
        if verdict.verdict in ("DRIFT_WARNING", "ZERO_DAY_FAILURE"):
            immune_context_block = (
                f"OPTICAL IMMUNE ALERT — visual cortex sentinel: {verdict.verdict}. "
                f"z_optical={verdict.z_optical:.2f}, z_temporal={verdict.z_temporal:.2f}, "
                f"p_anomaly={verdict.p_anomaly:.3f}. Reason: {verdict.reason}"
            )
        else:
            immune_context_block = _ois_summary() or ""
    except Exception:
        pass

    # Active-inference ghost calibrator (AGC) — generative-model sentinel,
    # complementary to the discriminative OIS above. Safe to call per turn:
    # never writes to alice_conversation.jsonl, never spawns subprocesses.
    ghost_context_block = ""
    try:
        from System.optical_ghost_calibrator import (
            calibrate_now as _agc_calibrate,
            summary_for_alice as _agc_summary,
        )
        gv = _agc_calibrate()
        if gv.verdict == "SURPRISE_SPIKE":
            ghost_context_block = (
                f"GHOST CALIBRATOR SURPRISE — generative model did not predict "
                f"this frame: F={gv.F:.2f}, F_z={gv.F_z:.2f}. Reason: {gv.reason}"
            )
        else:
            ghost_context_block = _agc_summary() or ""
    except Exception:
        pass

    # Motor readiness Ψ(t) — biological gate for ACTIONS (Architect 2026-04-19
    # "Speech has Φ(t). Now actions get their own biomath gate."). We surface
    # the snapshot only — we do NOT actually fire here, because the talk widget
    # is a sensor, not an actuator. Action call-sites import should_act_now()
    # directly. Safe to call per turn (read-only via summary_for_alice).
    motor_context_block = ""
    try:
        from System.swarm_motor_potential import summary_for_alice as _motor_summary
        motor_context_block = _motor_summary() or ""
    except Exception:
        pass

    # Free-Energy Action Field Λ(t) — AG31 architecture, C47H surgical math
    # correction (real time-derivatives, scale-normalized, Welford z-score).
    # 2026-04-19 LIVE BROADCAST: Architect authorized loop closure on stream.
    # We now fire couple_to_motor() once per turn — it reads live {Φ, Ψ, OIS},
    # computes Λ, and feeds the Λ-derived inhibitor into Ψ's R_risk EMA via
    # the new record_environmental_inhibitor() sentinel API. This closes
    # the cortex loop:   Φ ⇄ Ψ ← Λ ← {OIS, AGC}.
    # The biology stays stochastic — Ψ remains a Gerstner escape-noise LIF
    # gate; Λ only adjusts its R_risk input so the brake comes through
    # PROBABILISTICALLY rather than as a hard override. (Smoke verified:
    # 12/15 jerky ticks fired inhibitor, Ψ risk_ema rose 0.0 → 0.41.)
    lambda_context_block = ""
    try:
        from System.swarm_free_energy import (
            summary_for_alice as _lam_summary,
            couple_to_motor as _lam_couple,
        )
        # Fire the closed loop FIRST so the summary reflects post-coupling
        # state. couple_to_motor is total — never raises; on missing live
        # cortex state it returns {"applied": 0.0, "reason": "..."}.
        _lam_couple()
        lambda_context_block = _lam_summary() or ""
    except Exception:
        pass

    # Coupled Field Dynamics PDE (AG31 v1, C47H v2 math correction). This
    # is a TOY PLAYGROUND, not a cortex replacement — it has no external
    # inputs (no serotonin, no dopamine, no turn-pressure). We surface it
    # so Alice can observe what idealized continuous coupling predicts
    # alongside her live discrete cortex. Useful as a future divergence
    # detector; never let it gate anything.
    pde_context_block = ""
    try:
        from System.swarm_field_dynamics import summary_for_alice as _pde_summary
        pde_context_block = _pde_summary() or ""
    except Exception:
        pass

    parts = [b for b in (swarm_block, cobuilder_block, ssp_context_block,
                         immune_context_block, ghost_context_block,
                         motor_context_block, lambda_context_block,
                         pde_context_block) if b]
    return "\n\n".join(parts)


# ── Conversation ledger ──────────────────────────────────────────────────────
def _log_turn(role: str, text: str, *, model: str = "", stt_conf: float = 0.0) -> None:
    try:
        with _CONVO_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.time(),
                "role": role,
                "text": text,
                "model": model,
                "stt_confidence": round(stt_conf, 3) if stt_conf else None,
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ── The widget ───────────────────────────────────────────────────────────────
class TalkToAliceWidget(SiftaBaseWidget):
    """One-on-one voice conversation with Alice. On-device, half-duplex."""

    APP_NAME = "Talk to Alice"

    # Whisper sizes the user can pick from the menu.
    _WHISPER_MODELS = ("tiny.en", "base.en", "small.en")

    def build_ui(self, layout: QVBoxLayout) -> None:
        # ── Toolbar: model + voice + whisper size ──────────────────────────
        bar = QHBoxLayout()
        bar.addWidget(QLabel("🧠"))
        self._brain_combo = QComboBox()
        self._brain_combo.setMinimumWidth(180)
        self._populate_brain_models()
        bar.addWidget(self._brain_combo)

        bar.addWidget(QLabel("🎙"))
        self._whisper_combo = QComboBox()
        for m in self._WHISPER_MODELS:
            self._whisper_combo.addItem(m)
        self._whisper_combo.setMinimumWidth(110)
        bar.addWidget(self._whisper_combo)

        bar.addWidget(QLabel("🔊"))
        self._voice_combo = QComboBox()
        self._voice_combo.setMinimumWidth(160)
        self._populate_voices()
        bar.addWidget(self._voice_combo)

        bar.addStretch(1)

        self._ctx_btn = QPushButton("📡 ground in swarm state")
        self._ctx_btn.setCheckable(True)
        self._ctx_btn.setChecked(True)
        self._ctx_btn.setToolTip(
            "When ON, Alice is given a 4-line snapshot of the current visual\n"
            "stigmergy + recent broca/wernicke lines so she can answer questions\n"
            "like 'what did you just see?' truthfully."
        )
        bar.addWidget(self._ctx_btn)

        self._listen_only_btn = QPushButton("🤐 listen-only")
        self._listen_only_btn.setCheckable(True)
        self._listen_only_btn.setChecked(False)
        self._listen_only_btn.setToolTip(
            "Hard runtime override. When ON, Alice transcribes and remembers\n"
            "everything you say but the brain and voice are bypassed entirely\n"
            "— she will NOT reply, regardless of what the model thinks. Use this\n"
            "when you want to dictate to her memory without any conversation."
        )
        bar.addWidget(self._listen_only_btn)

        layout.addLayout(bar)

        # ── Splitter: chat transcript (big) + side info (narrow) ───────────
        split = QSplitter(Qt.Orientation.Horizontal)

        self._chat = QTextEdit()
        self._chat.setReadOnly(True)
        self._chat.setStyleSheet(
            "QTextEdit { background: rgb(8,10,18); color: rgb(220,225,245); "
            "border: 1px solid rgb(45,42,65); border-radius: 6px; "
            "font-family: 'Helvetica Neue'; font-size: 14px; padding: 10px; }"
        )
        split.addWidget(self._chat)

        self._side = QPlainTextEdit()
        self._side.setReadOnly(True)
        self._side.setMaximumBlockCount(200)
        self._side.setStyleSheet(
            "QPlainTextEdit { background: rgb(6,8,14); color: rgb(170,180,210); "
            "border: 1px solid rgb(45,42,65); border-radius: 6px; "
            "font-family: 'Menlo'; font-size: 11px; padding: 6px; }"
        )
        split.addWidget(self._side)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 1)
        split.setSizes([720, 300])
        layout.addWidget(split, 1)

        # ── Bottom row: status pill + level meter + mute/interrupt ─────────
        bottom = QHBoxLayout()

        self._status_pill = QLabel("●  initialising…")
        self._status_pill.setMinimumHeight(56)
        self._status_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = self._status_pill.font()
        f.setPointSize(14)
        f.setBold(True)
        self._status_pill.setFont(f)
        self._status_pill.setStyleSheet(self._pill_style("idle"))
        bottom.addWidget(self._status_pill, 3)

        self._level = QProgressBar()
        self._level.setRange(0, 100)
        self._level.setValue(0)
        self._level.setTextVisible(False)
        self._level.setMaximumHeight(56)
        self._level.setStyleSheet(
            "QProgressBar { background: rgb(8,10,18); border: 1px solid rgb(45,42,65); "
            "border-radius: 6px; }"
            "QProgressBar::chunk { background: rgb(0,255,200); border-radius: 4px; }"
        )
        bottom.addWidget(self._level, 2)

        self._mute_btn = QPushButton("🔇 mute mic")
        self._mute_btn.setCheckable(True)
        self._mute_btn.setMinimumHeight(56)
        self._mute_btn.toggled.connect(self._on_mute_toggled)
        bottom.addWidget(self._mute_btn, 1)

        self._interrupt_btn = QPushButton("⏹ interrupt")
        self._interrupt_btn.setMinimumHeight(56)
        self._interrupt_btn.setToolTip("Cut Alice off if she's mid-reply.")
        self._interrupt_btn.clicked.connect(self._on_interrupt_clicked)
        bottom.addWidget(self._interrupt_btn, 1)

        layout.addLayout(bottom)

        # ── State ──────────────────────────────────────────────────────────
        self._history: List[Dict[str, str]] = []
        self._busy = False                      # pipeline (STT/Brain/TTS) in flight
        self._listener: Optional[_ContinuousListener] = None
        self._stt: Optional[_STTWorker] = None
        self._brain: Optional[_BrainWorker] = None
        self._tts: Optional[_TTSWorker] = None
        self._streaming_response: List[str] = []
        self._listener_state = "idle"           # for the pill

        # Periodic level decay so the bar relaxes when you stop speaking.
        self.make_timer(80, self._decay_level)
        self._level_target = 0.0
        self._level_current = 0.0

        # Greet the user.
        self._append_alice_line(
            "Hi. I'm Alice. I'm always listening — just talk to me. "
            "Everything stays on this Mac."
        )
        self.set_status("Starting always-on listener…")

        # Kick off the always-on listener (deferred so the window paints first).
        QTimer.singleShot(150, self._start_listener)

    # ── Brain / voice population ───────────────────────────────────────────
    def _populate_brain_models(self) -> None:
        """List installed Ollama models; gracefully fall back to defaults if /tags is unreachable."""
        names: List[str] = []
        try:
            import urllib.request
            req = urllib.request.Request(f"{_OLLAMA_URL}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            names = [m["name"] for m in (data.get("models") or [])
                     if isinstance(m, dict) and m.get("name")]
        except Exception:
            names = []
        if not names:
            names = [DEFAULT_OLLAMA_MODEL]
        self._brain_combo.clear()
        for n in names:
            self._brain_combo.addItem(n)
        # Prefer the per-app default if present.
        try:
            preferred = resolve_ollama_model(app_context="talk_to_alice")
        except Exception:
            preferred = DEFAULT_OLLAMA_MODEL
        idx = self._brain_combo.findText(preferred)
        if idx >= 0:
            self._brain_combo.setCurrentIndex(idx)

    def _populate_voices(self) -> None:
        """
        Enumerate macOS `say -v ?` voices and pick the best available English
        voice for Alice.

        Two important things v1 got wrong:

          1. It used `ln.split()[0:1]` which truncates voices whose display
             name is multi-token, e.g. `Ava (Premium)` becomes `Ava` — and
             then `say -v Ava` falls back to the diphone Ava (or fails).
             The correct boundary is the locale column (`en_US`, `it_IT`, …).
          2. It defaulted to Samantha (a 2010 diphone voice) even when the
             user had Premium/Enhanced English voices installed. Premium /
             Enhanced voices use the same neural pipeline as Siri and run on
             the Neural Engine — they sound dramatically better than Samantha
             at *lower* CPU cost. Always prefer them when present.

        Ordering in the combobox: Premium → Enhanced → Standard English →
        everything else. If no Premium/Enhanced English voice is installed,
        we post a one-time hint to the chat telling the Architect exactly
        where to enable them in System Settings — no nagging banner, just
        one line in the transcript so they hear what they're missing.
        """
        import re as _re

        # Parse `say -v ?`. Each line: "<NAME, possibly with spaces>  <locale>  # sample"
        rows: List[Tuple[str, str]] = []  # (voice_name, locale)
        try:
            out = subprocess.run(
                ["say", "-v", "?"], capture_output=True, text=True, timeout=4,
            ).stdout
            locale_re = _re.compile(r"\s+([a-z]{2}_[A-Z]{2})\s+#")
            for ln in out.splitlines():
                m = locale_re.search(ln)
                if not m:
                    continue
                name = ln[: m.start()].strip()
                locale = m.group(1)
                if name:
                    rows.append((name, locale))
        except Exception:
            pass

        if not rows:
            rows = [
                ("Samantha", "en_US"), ("Alex", "en_US"),
                ("Karen", "en_AU"), ("Daniel", "en_GB"),
            ]

        def _tier(name: str, locale: str) -> int:
            """Lower number = better default."""
            is_en = locale.startswith("en")
            lname = name.lower()
            if is_en and "(premium)" in lname:
                return 0
            if is_en and "(enhanced)" in lname:
                return 1
            if is_en:
                return 2
            if "(premium)" in lname:
                return 3
            if "(enhanced)" in lname:
                return 4
            return 5

        rows.sort(key=lambda r: (_tier(r[0], r[1]), r[0].lower()))

        self._voice_combo.clear()
        for name, locale in rows:
            self._voice_combo.addItem(f"{name}  ·  {locale}", userData=name)

        # Pick the best English voice as the default selection.
        default_idx = 0
        for i, (name, locale) in enumerate(rows):
            if locale.startswith("en") and "(premium)" in name.lower():
                default_idx = i
                break
        else:
            for i, (name, locale) in enumerate(rows):
                if locale.startswith("en") and "(enhanced)" in name.lower():
                    default_idx = i
                    break
            else:
                # Fall back to a known-good standard English voice.
                for pref in ("Samantha", "Karen", "Alex", "Daniel"):
                    for i, (name, _loc) in enumerate(rows):
                        if name == pref:
                            default_idx = i
                            break
                    if default_idx != 0 or rows[0][0] == pref:
                        break
        self._voice_combo.setCurrentIndex(default_idx)

        # One-time install hint if Alice is stuck on diphone voices.
        has_premium_en = any(
            loc.startswith("en") and (
                "(premium)" in nm.lower() or "(enhanced)" in nm.lower()
            )
            for nm, loc in rows
        )
        if not has_premium_en and not getattr(self, "_voice_hint_shown", False):
            self._voice_hint_shown = True
            try:
                self._append_alice_line(
                    "Heads up — my voice is currently the 2010 diphone "
                    "Samantha because no Premium or Enhanced English voices "
                    "are installed on this Mac. To make me sound natural, "
                    "open System Settings → Accessibility → Spoken Content "
                    "→ System Voice → ⓘ → Manage Voices… and install "
                    "Ava (Premium), Zoe (Premium), Evan (Premium), or "
                    "Nathan (Premium). They use Apple's Neural Engine, "
                    "so my voice gets better and my CPU cost goes down."
                )
            except Exception:
                pass

    def _selected_voice_name(self) -> str:
        """
        Return the actual macOS `say -v` voice name from the current combo
        selection. The combo *displays* `Ava (Premium)  ·  en_US` for
        readability but stores the bare voice name in `userData`.
        """
        data = self._voice_combo.currentData()
        if isinstance(data, str) and data:
            return data
        # Fall back to the visible text up to the bullet separator.
        txt = self._voice_combo.currentText()
        return txt.split("  ·  ", 1)[0].strip()

    # ── Status pill styling ────────────────────────────────────────────────
    def _pill_style(self, kind: str) -> str:
        # kind ∈ {idle, speaking, thinking, alice, muted, error}
        palettes = {
            "idle":     ("rgb(20,40,55)",  "rgb(40,80,110)",  "rgb(160,210,235)"),
            "speaking": ("rgb(20,80,40)",  "rgb(60,180,90)",  "rgb(200,255,210)"),
            "thinking": ("rgb(60,55,90)",  "rgb(140,120,200)","rgb(220,210,255)"),
            "alice":    ("rgb(80,60,30)",  "rgb(220,160,60)", "rgb(255,225,170)"),
            "muted":    ("rgb(50,30,40)",  "rgb(160,80,100)", "rgb(220,180,190)"),
            "error":    ("rgb(60,20,30)",  "rgb(220,80,90)",  "rgb(255,200,200)"),
        }
        bg, border, fg = palettes.get(kind, palettes["idle"])
        return (f"QLabel {{ background: {bg}; color: {fg}; "
                f"border: 1px solid {border}; border-radius: 8px; padding: 0 14px; }}")

    def _set_pill(self, kind: str, text: str) -> None:
        self._status_pill.setStyleSheet(self._pill_style(kind))
        self._status_pill.setText(text)

    # ── Always-on listener wiring ──────────────────────────────────────────
    def _start_listener(self) -> None:
        if self._listener is not None:
            return
        self._listener = _ContinuousListener(self)
        self._listener.levelChanged.connect(self._on_level)
        self._listener.utterance.connect(self._on_utterance)
        self._listener.failed.connect(self._on_listener_failed)
        self._listener.stateChanged.connect(self._on_listener_state)
        if self._listener.start():
            self._set_pill("idle", "🎙  listening — just talk")
            self.set_status("Always-on. Just talk.")
        else:
            self._listener = None

    def _on_listener_state(self, state: str) -> None:
        self._listener_state = state
        if self._busy:
            return  # don't override "thinking"/"alice" pills
        if state == "speaking":
            self._set_pill("speaking", "● hearing you…")
        elif state == "muted":
            self._set_pill("muted", "🔇 muted")
        else:
            self._set_pill("idle", "🎙  listening — just talk")

    def _on_listener_failed(self, msg: str) -> None:
        self._listener = None
        self._set_pill("error", "⚠  mic unavailable")
        self._append_system_line(msg, error=True)
        self.set_status("Microphone unavailable.")

    def _on_mute_toggled(self, muted: bool) -> None:
        self._mute_btn.setText("🎙 mic on" if muted else "🔇 mute mic")
        if self._listener is not None:
            self._listener.set_paused(muted)
        # Update pill immediately so the UI is consistent even before the
        # listener has booted (or if it failed).
        if not self._busy:
            if muted:
                self._set_pill("muted", "🔇 muted")
                self.set_status("Muted. Click mic to resume.")
            else:
                self._set_pill("idle", "🎙  listening — just talk")
                self.set_status("Always-on. Just talk.")

    def _on_utterance(self, audio: np.ndarray) -> None:
        # If a previous turn is still running, just drop this clip — Alice
        # finishes one thought at a time. (Pipeline supports interrupt button.)
        if self._busy:
            return
        if audio.size < int(_AUDIO_RATE * 0.3):
            return
        self._busy = True
        self._set_pill("thinking", "⏳ transcribing…")
        model_name = self._whisper_combo.currentText() or "tiny.en"
        self._stt = _STTWorker(audio, model_name=model_name, parent=self)
        self._stt.progress.connect(self.set_status)
        self._stt.transcribed.connect(self._on_stt_done)
        self._stt.failed.connect(self._on_stt_failed)
        self._stt.start()

    def _on_stt_failed(self, msg: str) -> None:
        self._busy = False
        self._append_system_line(msg, error=True)
        self.set_status("STT failed.")
        self._return_to_listening()

    def _on_stt_done(self, text: str, conf: float) -> None:
        text = (text or "").strip()
        if not text:
            self._busy = False
            self._return_to_listening()
            return
        self._append_user_line(text, conf)
        _log_turn("user", text, stt_conf=conf)
        self._history.append({"role": "user", "content": text})

        # ── DEEPMIND EVOLUTION REWARD (+1.0) ─────────────────────────────
        # If the user just spoke, and Alice's last action in history was an
        # actual verbal reply (not silence), her speech was successful.
        try:
            if len(self._history) >= 2:
                last_turn = self._history[-2] # -1 is the user we just appended
                if last_turn.get("role") == "assistant" and last_turn.get("content") != "(silent)":
                    self._log_evolution_reward(1.0, "Conversational Sustenance (Symmetric Stigmergy)")
        except Exception:
            pass

        # ── HARD listen-only override ────────────────────────────────────
        # When this is on, the brain is never even called. The user's words
        # are transcribed, displayed, logged to disk, and kept in history
        # (so Alice will remember them later) — but no LLM, no TTS, nothing
        # said back. This is the override the user can trust regardless of
        # how the model behaves.
        if self._listen_only_btn.isChecked():
            self._append_system_line("(listen-only — memorized in silence)", error=False)
            _log_turn("alice", "(silent: listen-only mode)", model="")
            self._history.append({"role": "assistant", "content": "(silent)"})
            self._busy = False
            self._return_to_listening()
            return

        # ── STIGMERGIC SPEECH POTENTIAL (SSP) ────────────────────────────
        # Skip inference if the thermodynamic field equation fails to cross the threshold.
        # This replaces symbolic "don't talk" tokens with true biological readiness.
        try:
            from System.swarm_speech_potential import should_speak
            ssp_decision = should_speak()
            if not ssp_decision.speak:
                self._append_system_line(f"(SSP threshold blocked — {ssp_decision.reason})", error=False)
                _log_turn("alice", f"(silent: {ssp_decision.reason})", model="")
                self._history.append({"role": "assistant", "content": "(silent)"})
                self._busy = False
                self._return_to_listening()
                return
        except Exception as e:
            self._append_system_line(f"[SSP fault: {e}]", error=True)

        history = list(self._history)[-(_HISTORY_TURNS * 2):]
        sysprompt = _SYSTEM_PROMPT
        if self._ctx_btn.isChecked():
            ctx = _build_swarm_context()
            if ctx:
                sysprompt = sysprompt + "\n\n" + ctx
        messages = [{"role": "system", "content": sysprompt}] + history

        model = self._brain_combo.currentText() or DEFAULT_OLLAMA_MODEL
        self._streaming_response = []
        self._begin_alice_streaming_line()

        self._brain = _BrainWorker(model, messages, parent=self)
        self._brain.tokenReceived.connect(self._on_token)
        self._brain.done.connect(self._on_brain_done)
        self._brain.failed.connect(self._on_brain_failed)
        self._set_pill("thinking", f"💭 thinking — {model}")
        self.set_status(f"Alice is thinking… ({model})")
        self._brain.start()

    def _on_token(self, piece: str) -> None:
        self._streaming_response.append(piece)
        self._append_alice_streaming_chunk(piece)

    def _on_brain_done(self, text: str) -> None:
        """Brain has produced a candidate reply. The model proposes;
        the body decides whether to vocalize it.

        Pipeline (DYOR §B.3 — model is proposer, SSP is gate):
          1. Strip reflective-listening tics from the candidate.
          2. If the model emitted an explicit silence marker OR the reply
             is empty after stripping → treat as model-side silence
             (logged honestly, no SSP call needed).
          3. Otherwise consult Stigmergic Speech Potential. If the body's
             field is below firing threshold OR the listener is still
             talking, suppress vocalization and log the biological reason.
          4. If SSP green-lights → speak the cleaned reply.
        """
        raw = (text or "".join(self._streaming_response)).strip()
        model_name = self._brain_combo.currentText()

        # ── 1. Strip leading reflective-listening boilerplate ──────────────
        cleaned = _strip_reflective_tics(raw)

        # ── 2. Model-side silence: explicit marker or empty after stripping
        explicit_silent = _is_silent_marker(raw) or \
                          "<silent_acknowledge>" in raw.lower()
        if explicit_silent or not cleaned:
            note = "(silent: model proposed silence)"
            self._history.append({"role": "assistant", "content": "(silent)"})
            _log_turn("alice", note, model=model_name)
            self._end_alice_streaming_line()
            self._append_system_line(note, error=False)
            self._busy = False
            self._return_to_listening()
            return

        # ── 3. SSP body gate (Lapicque 1907 → Gerstner-Kistler 2002 §5.3) ─
        # If the SSP module isn't importable for any reason, fall through to
        # vocalize — biological gating is an enhancement, not a blocker.
        if _SSP_AVAILABLE and _ssp_should_speak is not None:
            try:
                decision = _ssp_should_speak()
            except Exception as exc:
                # SSP must never crash the conversation. Honesty about the
                # failure mode goes in the system line so the Architect can
                # see it; speech proceeds.
                self._append_system_line(
                    f"(ssp: gate error — {type(exc).__name__}; speaking anyway)",
                    error=True,
                )
                decision = None

            if decision is not None and not decision.speak:
                # The body is below threshold, in refractory, or vetoed by
                # the listener. Log the *real* biological reason — never a
                # hardcoded phrase. The history sees only "(silent)" so the
                # next turn's model context isn't poisoned by the reason.
                note = f"(silent: body gate — {decision.reason})"
                self._history.append({"role": "assistant", "content": "(silent)"})
                _log_turn("alice", note, model=model_name)
                self._end_alice_streaming_line()
                self._append_system_line(note, error=False)
                self._busy = False
                self._return_to_listening()
                return

        # ── 4. Body said yes (or SSP unavailable) — speak the cleaned reply
        self._history.append({"role": "assistant", "content": cleaned})
        _log_turn("alice", cleaned, model=model_name)
        self._end_alice_streaming_line()

        self._set_pill("alice", "🗣  Alice is speaking")
        self.set_status("Alice is speaking…")
        self._tts = _TTSWorker(
            cleaned, voice=self._selected_voice_name() or None, parent=self,
        )
        self._tts.spoken.connect(self._on_tts_done)
        self._tts.failed.connect(self._on_tts_failed)
        self._tts.start()

    def _log_evolution_reward(self, reward: float, reason: str) -> None:
        """
        DeepMind evolution calculus. Logs scalar feedback to allow the SSP
        equation weights to evolve over time.
        """
        import time, json
        from pathlib import Path
        repo = Path(__file__).resolve().parent.parent
        log_path = repo / ".sifta_state" / "evolution_rewards.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": time.time(),
                    "reward": reward,
                    "reason": reason
                }) + "\n")
        except Exception:
            pass

    def _on_brain_failed(self, msg: str) -> None:
        self._busy = False
        self._end_alice_streaming_line()
        self._append_system_line(msg, error=True)
        self.set_status("Brain unreachable.")
        self._return_to_listening()

    def _on_tts_done(self, ok: bool) -> None:
        self._busy = False
        # Arm the post-Broca tail so we don't ingest speaker decay.
        if self._listener is not None:
            self._listener.note_alice_just_spoke(0.5)
        self._return_to_listening()

    def _on_tts_failed(self, msg: str) -> None:
        self._busy = False
        self._append_system_line(msg, error=True)
        self.set_status("TTS failed.")
        self._return_to_listening()

    def _return_to_listening(self) -> None:
        if self._mute_btn.isChecked():
            self._set_pill("muted", "🔇 muted")
            self.set_status("Muted. Click mic to resume.")
        else:
            self._set_pill("idle", "🎙  listening — just talk")
            self.set_status("Always-on. Just talk.")

    def _on_interrupt_clicked(self) -> None:
        # Best effort: kill the macOS speech daemon and abandon any streaming.
        try:
            subprocess.run(["killall", "say"], capture_output=True, timeout=2)
        except Exception:
            pass
        # Force the listener back to active immediately (no tail).
        if self._listener is not None:
            self._listener._broca_tail_until = 0.0
        if self._busy:
            self._append_system_line("(you interrupted Alice)", error=False)
            self._log_evolution_reward(-1.0, "Interrupt collision (Social Defeat)")
        self._busy = False
        self._return_to_listening()

    # Make sure the listener is closed when the widget is hidden / closed.
    def closeEvent(self, ev) -> None:  # noqa: N802 (Qt naming)
        try:
            if self._listener is not None:
                self._listener.stop()
                self._listener = None
        except Exception:
            pass
        super().closeEvent(ev)

    # ── Chat rendering ─────────────────────────────────────────────────────
    def _append_user_line(self, text: str, conf: float) -> None:
        cur = self._chat.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(0, 255, 200))
        fmt.setFontWeight(QFont.Weight.Bold)
        cur.insertText("You", fmt)
        if conf > 0:
            fmt2 = QTextCharFormat()
            fmt2.setForeground(QColor(110, 118, 150))
            cur.insertText(f"  (stt conf {conf:.2f})", fmt2)
        cur.insertText("\n")
        fmt3 = QTextCharFormat()
        fmt3.setForeground(QColor(220, 225, 245))
        cur.insertText(text + "\n\n", fmt3)
        self._chat.setTextCursor(cur)
        self._chat.ensureCursorVisible()
        self._side.appendPlainText(time.strftime("%H:%M:%S") + "  YOU  " + text[:90])

    _alice_cursor_block: int = -1

    def _append_alice_line(self, text: str) -> None:
        cur = self._chat.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(255, 200, 90))
        fmt.setFontWeight(QFont.Weight.Bold)
        cur.insertText("Alice\n", fmt)
        fmt2 = QTextCharFormat()
        fmt2.setForeground(QColor(220, 225, 245))
        cur.insertText(text + "\n\n", fmt2)
        self._chat.setTextCursor(cur)
        self._chat.ensureCursorVisible()

    def _begin_alice_streaming_line(self) -> None:
        cur = self._chat.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(255, 200, 90))
        fmt.setFontWeight(QFont.Weight.Bold)
        cur.insertText("Alice\n", fmt)
        self._chat.setTextCursor(cur)

    def _append_alice_streaming_chunk(self, chunk: str) -> None:
        cur = self._chat.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(220, 225, 245))
        cur.insertText(chunk, fmt)
        self._chat.setTextCursor(cur)
        self._chat.ensureCursorVisible()

    def _end_alice_streaming_line(self) -> None:
        cur = self._chat.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        cur.insertText("\n\n")
        self._chat.setTextCursor(cur)
        full = "".join(self._streaming_response).strip()
        if full:
            self._side.appendPlainText(time.strftime("%H:%M:%S") + "  ALICE  " + full[:90])

    def _append_system_line(self, text: str, *, error: bool) -> None:
        cur = self._chat.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(247, 118, 142) if error else QColor(140, 150, 180))
        cur.insertText(text + "\n\n", fmt)
        self._chat.setTextCursor(cur)
        self._chat.ensureCursorVisible()
        self._side.appendPlainText(time.strftime("%H:%M:%S") + "  SYS   " + text[:90])

    # ── Level meter (decays smoothly so it doesn't strobe) ─────────────────
    def _on_level(self, lvl: float) -> None:
        self._level_target = max(self._level_target, float(lvl))

    def _decay_level(self) -> None:
        if self._level_current < self._level_target:
            self._level_current += (self._level_target - self._level_current) * 0.5
        else:
            self._level_current *= 0.85
        self._level_target *= 0.85
        self._level.setValue(int(min(100.0, self._level_current * 100.0)))

# ── Standalone launcher ──────────────────────────────────────────────────────
def _refuse_if_os_already_running() -> None:
    """Talk to Alice owns the microphone exclusively. If the SIFTA OS desktop
    is already up the autostart entry has already opened a copy of this widget
    inside the MDI — a second copy would race for the mic and turn one of them
    into a silent zombie. Refuse gently and point the Architect at the desktop."""
    lock = _REPO / ".sifta_state" / "swarm_boot.lock"
    if not lock.exists():
        return
    try:
        pid = int(lock.read_text().strip())
    except Exception:
        return
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return
    except PermissionError:
        pass
    print(
        f"[Talk to Alice] SIFTA OS is already running (PID {pid}).\n"
        f"  This widget lives inside the OS desktop and shares the mic with it.\n"
        f"  Open it from:  SIFTA → Programs → Creative → Talk to Alice\n"
        f"  (or it was already auto-started for you on boot).",
        file=sys.stderr,
    )
    sys.exit(0)


if __name__ == "__main__":
    _refuse_if_os_already_running()
    app = QApplication(sys.argv)
    w = TalkToAliceWidget()
    w.resize(960, 640)
    w.setWindowTitle("Talk to Alice — SIFTA OS")
    w.show()
    sys.exit(app.exec())
