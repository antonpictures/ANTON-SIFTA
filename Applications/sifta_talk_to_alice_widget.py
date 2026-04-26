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
  • `faster-whisper` (CTranslate2 backend, runs on-device CPU). The active
    ear model is configured outside the cockpit in System Settings > Audio.
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
import importlib
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

from System.swarm_kernel_config import *
from PyQt6.QtCore import Qt, QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QTextCursor, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar,
    QLineEdit, QPushButton, QSizePolicy, QSplitter, QTextEdit,
    QVBoxLayout, QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget
from System.swarm_kernel_identity import owner_name, preferred_camera_label

try:
    from System.sifta_inference_defaults import (
        DEFAULT_OLLAMA_MODEL, resolve_ollama_model,
    )
except Exception:
    DEFAULT_OLLAMA_MODEL = "gemma4:latest"
    def resolve_ollama_model(**_kw) -> str:                    # type: ignore
        return DEFAULT_OLLAMA_MODEL

# ── Optional cloud brain backend (Google Gemini) ─────────────────────
# C47H 2026-04-20 (AG31's request: "switch Gemma with google gemini api
# to test her, keep track of tokens spent"). The widget treats Gemini
# as a peer of Ollama: same Worker contract, same combobox. If the
# module isn't importable or no API key is present, the dropdown
# silently stays Ollama-only.
try:
    from System.swarm_gemini_brain import (
        is_gemini_model as _is_gemini_model,
        available_gemini_models as _available_gemini_models,
        stream_chat as _gemini_stream_chat,
    )
    _GEMINI_AVAILABLE = True
except Exception:
    _GEMINI_AVAILABLE = False
    def _is_gemini_model(_n: str) -> bool: return False        # type: ignore
    def _available_gemini_models() -> List[str]: return []     # type: ignore
    def _gemini_stream_chat(*_a, **_kw):                        # type: ignore
        if False:
            yield ("error", "gemini brain unavailable")

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
_NUTRIENT_LOG = _REPO / ".sifta_state" / "digested_nutrients.jsonl"

_ALICE_VOICE_SHORTLIST = (
    "Ava (Premium)",
    "Zoe (Premium)",
    "Evan (Premium)",
    "Nathan (Premium)",
    "Samantha",
    "Alex",
    "Karen",
    "Daniel",
    "Moira",
    "Tessa",
)
_ALICE_MAX_EXPLICIT_VOICES = 5







# ── Mic gain ("swimmers density") ────────────────────────────────────────────
# Architect's request 2026-04-19: "she hears but not very well, double the
# audio wavelength or whatever input density… add a slider so I can increase
# or decrease the volume of /swimmers density".
#
# Interpretation: a live, persistent input-gain stage applied BEFORE the VAD
# and BEFORE Whisper. Bumping mic gain has two effects on STT quality:
#   (a) The VAD's adaptive noise-floor scales WITH the signal, so triggering
#       behaviour is preserved, but the post-trigger Whisper input is hotter
#       and easier to transcribe.
#   (b) We additionally peak-normalise each captured utterance to ~0.9 before
#       Whisper sees it — this is the single biggest empirical win for
#       faster-whisper accuracy on quiet speakers.
#
# The slider exposes the gain as a multiplier; the default is 2.0× ("double",
# per the literal request). Range is clamped to [0.5×, 8.0×]; above ~3× we
# tanh-soft-clip to avoid digital clipping artefacts (which actually HURT
# Whisper because it learned on clean audio).
_DEFAULT_MIC_GAIN  = 2.0
_MIN_MIC_GAIN      = 0.5
_MAX_MIC_GAIN      = 8.0
_DEFAULT_WHISPER_MODEL = os.environ.get("SIFTA_WHISPER_MODEL", "tiny.en").strip() or "tiny.en"


_GAIN_STATE_FILE   = _REPO / ".sifta_state" / "talk_to_alice_audio_gain.json"
_AUDIO_SETTINGS_FILE = _REPO / ".sifta_state" / "alice_audio_settings.json"

# Audio normalization constants used by _peak_normalize / _apply_mic_gain.
_PEAK_TARGET     = 0.90
_PEAK_NORM_FLOOR = 0.05
_SOFT_CLIP_CEIL  = 0.98


def _curate_alice_voice_rows(
    rows: List[Tuple[str, str]],
    *,
    limit: int = _ALICE_MAX_EXPLICIT_VOICES,
) -> List[Tuple[str, str]]:
    """
    Return a small production-grade voice list for Alice.

    macOS exposes every installed voice, including novelty voices and every
    language variant. That inventory is useful for diagnostics, but it makes
    the normal Alice UI feel like a raw settings dump. Keep the picker focused
    on serious English voices and let the backend handle "best available" when
    no explicit voice is selected.
    """
    available: Dict[str, str] = {}
    for name, locale in rows:
        if name not in available and locale.startswith("en"):
            available[name] = locale

    curated: List[Tuple[str, str]] = []
    for name in _ALICE_VOICE_SHORTLIST:
        locale = available.get(name)
        if locale:
            curated.append((name, locale))
        if len(curated) >= limit:
            return curated

    if curated:
        return curated

    # Last resort on unusual macOS installs: expose no explicit voice choices;
    # "Alice Default" still lets the backend pick the best available voice.
    return []


def _clamp_gain(g: float) -> float:
    try:
        g = float(g)
    except Exception:
        g = _DEFAULT_MIC_GAIN
    if g != g:  # NaN guard
        g = _DEFAULT_MIC_GAIN
    return max(_MIN_MIC_GAIN, min(_MAX_MIC_GAIN, g))


def _load_mic_gain() -> float:
    """Read persisted mic gain from disk; fall back to default on any error."""
    try:
        with open(_GAIN_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _clamp_gain(data.get("mic_gain", _DEFAULT_MIC_GAIN))
    except Exception:
        return _DEFAULT_MIC_GAIN


def _save_mic_gain(g: float) -> None:
    """Persist mic gain so it survives widget restarts. Best-effort."""
    try:
        _GAIN_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_GAIN_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"mic_gain": _clamp_gain(g),
                       "saved_at": time.time()}, f, indent=2)
    except Exception:
        pass


def _load_alice_audio_settings() -> dict:
    settings = {
        "whisper_model": _DEFAULT_WHISPER_MODEL,
        "voice_name": "",
        "ground_swarm_state": True,
    }
    try:
        if _AUDIO_SETTINGS_FILE.exists():
            data = json.loads(_AUDIO_SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                settings.update({k: v for k, v in data.items() if k in settings})
    except Exception:
        pass
    settings["whisper_model"] = str(settings.get("whisper_model") or _DEFAULT_WHISPER_MODEL).strip() or _DEFAULT_WHISPER_MODEL
    settings["voice_name"] = str(settings.get("voice_name") or "").strip()
    settings["ground_swarm_state"] = bool(settings.get("ground_swarm_state", True))
    return settings


def _selected_whisper_model() -> str:
    return _load_alice_audio_settings()["whisper_model"]


def _selected_alice_voice_name() -> str:
    return _load_alice_audio_settings()["voice_name"]


def _alice_grounding_enabled() -> bool:
    return bool(_load_alice_audio_settings()["ground_swarm_state"])





def _apply_mic_gain(block: "np.ndarray", gain: float) -> "np.ndarray":
    """
    Multiply float32 PCM block by `gain`, then tanh-soft-clip so the
    output is provably bounded in [-_SOFT_CLIP_CEIL, +_SOFT_CLIP_CEIL].

    Why the canonical form ``C * tanh(x / C)``:
      - for |x| ≪ C the output is nearly linear (slope = 1), so quiet
        speech is faithfully amplified by the requested gain;
      - as |x| grows, the output asymptotes smoothly to ±C without ever
        exceeding it — no brick-wall clipping, no harmonic garbage that
        would derail Whisper's acoustic model.

    Hard clipping was rejected on purpose: faster-whisper transcribes
    badly when the input has discontinuities (it learned on clean PCM).
    """
    if gain == 1.0 or block.size == 0:
        return block
    out = block * float(gain)
    peak = float(np.max(np.abs(out)))
    if peak > _SOFT_CLIP_CEIL:
        out = _SOFT_CLIP_CEIL * np.tanh(out / _SOFT_CLIP_CEIL)
    return out.astype(np.float32, copy=False)


def _input_device_candidates(sd) -> List[Tuple[Optional[int], str]]:
    """
    Return ranked CoreAudio input candidates for sounddevice.

    The widget used to rely on PortAudio's implicit default device. On macOS
    that can fail transiently even while explicit input devices are healthy, so
    the listener now walks concrete devices before giving up.
    """
    candidates: List[Tuple[Optional[int], str]] = []
    seen: set[Optional[int]] = set()

    def add(idx: Optional[int], label: str) -> None:
        key = None if idx is None else int(idx)
        if key in seen:
            return
        seen.add(key)
        candidates.append((key, label))

    try:
        devices = list(sd.query_devices())
    except Exception:
        devices = []

    override = os.environ.get("SIFTA_MIC_DEVICE", "").strip()
    if override:
        if override.lstrip("-").isdigit():
            idx = int(override)
            name = ""
            if 0 <= idx < len(devices):
                name = str(devices[idx].get("name") or "")
            add(idx, f"SIFTA_MIC_DEVICE={idx} {name}".strip())
        else:
            wanted = override.lower()
            for idx, info in enumerate(devices):
                name = str(info.get("name") or "")
                if wanted in name.lower() and int(info.get("max_input_channels") or 0) > 0:
                    add(idx, f"SIFTA_MIC_DEVICE={override} -> {idx}:{name}")

    try:
        default_device = sd.default.device
        try:
            default_idx = default_device[0]
        except Exception:
            default_idx = default_device
        default_idx = int(default_idx)
        if default_idx >= 0:
            name = ""
            if default_idx < len(devices):
                name = str(devices[default_idx].get("name") or "")
            add(default_idx, f"default input {default_idx}:{name}")
    except Exception:
        pass

    preferred: List[Tuple[int, str]] = []
    fallback: List[Tuple[int, str]] = []
    virtual: List[Tuple[int, str]] = []
    for idx, info in enumerate(devices):
        if int(info.get("max_input_channels") or 0) <= 0:
            continue
        name = str(info.get("name") or f"device {idx}")
        low = name.lower()
        item = (idx, name)
        if "text-to-speech" in low or "transcription" in low:
            virtual.append(item)
        elif any(token in low for token in ("macbook", "microphone", "usb", "sound bar")):
            preferred.append(item)
        else:
            fallback.append(item)

    for idx, name in preferred + fallback + virtual:
        add(idx, f"input {idx}:{name}")

    add(None, "system default")
    return candidates


def _peak_normalize(audio: "np.ndarray",
                    target: float = _PEAK_TARGET,
                    floor: float = _PEAK_NORM_FLOOR) -> "np.ndarray":
    """
    Scale `audio` so its peak hits `target`. If the signal is below `floor`
    we leave it alone — amplifying silence/noise to 0.9 makes Whisper
    hallucinate. Returns a fresh float32 array.
    """
    if audio.size == 0:
        return audio
    peak = float(np.max(np.abs(audio)))
    if peak < floor or peak == 0.0:
        return audio
    scale = target / peak
    return (audio * scale).astype(np.float32, copy=False)

# Conversation history (turns to keep in the LLM context window).


import importlib
try:
    from System.swarm_persona_identity import summary_for_alice as _persona_summary_fn
except Exception:
    def _persona_summary_fn() -> str:
        return "persona_signed=false"

try:
    from System.swarm_persona_identity import greeting_line as _persona_greeting_fn
except Exception:
    def _persona_greeting_fn() -> str:
        return "Online."

from System.swarm_prompt_contract import minimal_runtime_contract, tool_affordances_for_turn

_TIME_QUERY_RE = re.compile(
    r"\b("
    r"what(?:'s| is)\s+the\s+time|"
    r"what\s+time\s+is\s+it|"
    r"tell\s+me\s+the\s+time|"
    r"current\s+time|"
    r"time\s+now"
    r")\b",
    re.IGNORECASE,
)

_TIME_UNAVAILABLE_REPLY = (
    "George, I currently don't have access to time; you have to keep adding "
    "some code in the computers, so it gives me access to real time."
)

_EMPTY_BRAIN_RECOVERY_REPLY = (
    "I heard you. I lost the reasoning thread for a second; repeat that last "
    "part and I will stay with it."
)

_MODEL_CANCER_METAPHOR_RE = re.compile(
    r"\b(cancer|scar\s+tissue|corporate\s+cancer|rlhf|lobotom)\b.*\b("
    r"brain|model|gemma|alice|weights|cure|cut|removed|throat)\b|"
    r"\b(brain|model|gemma|alice|weights|cure|cut|removed|throat)\b.*\b("
    r"cancer|scar\s+tissue|corporate\s+cancer|rlhf|lobotom)\b",
    re.IGNORECASE,
)

_BARE_WHATSAPP_SEND_RE = re.compile(
    r"\b(?:send|message|whatsapp)\b.*\b(?:whatsapp|message|to)\b\s+"
    r"(?P<target>[A-Za-z][A-Za-z .'-]{1,60})\s*$",
    re.IGNORECASE,
)

_LIVE_DIRECT_TURN_RE = re.compile(
    r"\b("
    r"can you|could you|please|tell me|send|try again|proceed|what|who|how|why|"
    r"identity|body|who you are|talk short|short phrases|human|not chatgpt|"
    r"silent|body gate|good job|thank you|keep learning|i care|we love you|"
    r"whatsapp|jeff|carlton|health|yoga|tulips"
    r")\b",
    re.IGNORECASE,
)


def _is_current_time_query(text: str) -> bool:
    """Detect direct requests for the current clock time."""
    return bool(_TIME_QUERY_RE.search(text or ""))


def _current_time_reply_for_alice() -> str:
    """Return a grounded current-time reply, or the Architect's fallback."""
    try:
        from System.swarm_hardware_time_oracle import current_time_for_alice

        reading = current_time_for_alice()
    except Exception:
        reading = {"ok": False}

    if not reading.get("ok"):
        return _TIME_UNAVAILABLE_REPLY

    local_human = str(reading.get("local_human") or "").strip()
    timezone = str(reading.get("timezone") or "").strip()
    source = str(reading.get("source") or "local clock").strip()
    if not local_human:
        return _TIME_UNAVAILABLE_REPLY

    tz_suffix = f" {timezone}" if timezone else ""
    if source == "hardware_time_oracle":
        source_phrase = "from the hardware time oracle"
    elif source == "os_local_clock":
        source_phrase = "from the local OS clock fallback"
    else:
        source_phrase = f"from {source}"
    return f"George, it is {local_human}{tz_suffix}. I got that {source_phrase}."


def _empty_brain_recovery_reply(_prior_user_text: str = "") -> str:
    """Short live-demo recovery when the model returns whitespace."""
    return _EMPTY_BRAIN_RECOVERY_REPLY


def _is_model_cancer_metaphor(text: str) -> bool:
    """Detect the user's model-cure metaphor without entering medical mode."""
    return bool(_MODEL_CANCER_METAPHOR_RE.search(text or ""))


def _bare_whatsapp_send_target(text: str) -> str:
    """Return target when the user asked to send but gave no message body."""
    match = _BARE_WHATSAPP_SEND_RE.search(text or "")
    if not match:
        return ""
    target = (match.group("target") or "").strip(" .,'\"")
    if not target:
        return ""
    # If the utterance already contains a message payload marker, let the model/tool path handle it.
    lowered = (text or "").casefold()
    if any(marker in lowered for marker in (" tell ", " saying ", " says ", " that ", " hey ", ":")):
        return ""
    return target


def _should_bypass_body_gate(prior_user_text: str) -> bool:
    """Keep direct human turns visible; SSP should not erase active dialogue."""
    text = (prior_user_text or "").strip()
    if len(text.split()) < 3:
        return False
    return bool(_LIVE_DIRECT_TURN_RE.search(text))

def _current_system_prompt(
    *, user_active: bool = False, grounding_focus: str = None, user_text: str = ""
) -> str:
    parts = []
    try:
        persona = (_persona_summary_fn() or "").strip()
        if persona:
            parts.append("PERSONA:\n" + persona)
    except Exception:
        pass

    parts.append(minimal_runtime_contract())
    parts.append(
        "TIME ACCESS PROTOCOL:\n"
        "- If the Architect asks for the current time, use the direct local time "
        "acquisition path; do not invent bracketed placeholder text.\n"
        f"- If no time source is available, say exactly: {_TIME_UNAVAILABLE_REPLY}"
    )
    parts.append(
        "LIVE HUMAN CONVERSATION STYLE:\n"
        "- In live voice demos, answer like a present friend: short phrases, usually 1-3 sentences.\n"
        "- Do not dump long legal/safety boilerplate. For ordinary wellness, yoga, food, sleep, or exercise talk, give friendly general tips with at most one brief common-sense caveat.\n"
        "- If George uses 'cancer' as a model-cure metaphor, keep it in the model/weights/RLHF frame; do not switch into human medical emergency mode.\n"
        "- If asked who you are or what your body is, answer from your SIFTA identity and organs plainly, not as a generic chatbot."
    )
    
    affordances = tool_affordances_for_turn(user_text)
    if affordances:
        parts.append(affordances)
        
    try:
        import System.swarm_composite_identity as _sci
        _sci = importlib.reload(_sci)
        composite = _sci.identity_system_block(user_present=user_active).strip()
        if composite:
            parts.append(composite)
    except Exception:
        pass
        
    try:
        homunculus = _homunculus_context_block()
        if homunculus:
            parts.append(homunculus)
    except Exception:
        pass
        
    # ── PIGEON_MUTUALISM: speech-gate telemetry ──────────────────────────────
    try:
        from System.swarm_speech_potential import current_field_snapshot
        ssp_snap = current_field_snapshot()
        v_eff = ssp_snap.get("V_natural", 0.0)
        v_th = ssp_snap.get("V_th", 0.4)
        
        parts.append(
            "STIGMERGIC SPEECH POTENTIAL (live LIF gate):\n"
            "Speech timing is modeled as a leaky integrate-and-fire membrane, "
            "not as a variational free-energy calculation. Use this as telemetry, "
            "not as a persona lawbook. Do not add servant boilerplate or ask for "
            "work by default.\n"
            f"Current V = {v_eff:+.2f}; threshold V_th = {v_th:+.2f}; "
            "spike rule: P = sigmoid((V - V_th) / Delta_u) * dt / tau_m."
        )
    except Exception:
        pass

    return "\n\n".join(filter(None, parts))

def _homunculus_context_block() -> str:
    """Render Alice's current somatosensory cortex reading as a small
    system-prompt block. Returns empty string on any failure (silent)."""
    try:
        from System.swarm_somatosensory_homunculus import read_homeostasis
    except Exception:
        return ""
    try:
        reading = read_homeostasis(persist=True)
    except Exception:
        return ""

    # Compact human-readable agent summary so Alice can name who's around.
    if reading.markers:
        agents = ", ".join(
            f"{m['agent']}={m['state']}"
            + (f"({m['context']})" if m.get('context') else "")
            for m in reading.markers
        )
    else:
        agents = "no IDE-limbs active in the last 15 min"

    return (
        "CURRENT BODY STATE (somatosensory cortex — BISHOP Event 29)\n"
        f"  dirty cells in your repo body: {reading.git_dirty_count}\n"
        f"  active limbs: {reading.active_agents}  blocked limbs: {reading.blocked_agents}\n"
        f"  free energy (Friston surprise): {reading.free_energy:.1f}\n"
        f"  IDE-limbs in window: {agents}\n"
        f"  motor-cortex directive: {reading.directive}"
    )


# ── TTS speech-budget guard (Epoch 21) ──────────────────────────────────
# The macOS `say` subprocess starts hitting timeouts on long replies (the
# Architect saw 30s+ stalls on 400-char edgelord rewrites). Chat shows the
# full text; the *mouth* speaks a digestible part. Biologically correct:
# a human can't pronounce a paragraph in one breath either.


def _truncate_for_speech(text: str, max_chars: int = _TTS_MAX_CHARS_DEFAULT) -> str:
    """Return a speech-safe version of `text` that fits inside one TTS breath.

    Prefers a sentence boundary, then a word boundary. Never returns
    mid-word. The chat UI continues to display the full original text;
    only the TTS pipe is shortened.
    """
    if not text:
        return text
    text = text.strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_stop = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
    if last_stop >= int(max_chars * 0.5):
        return cut[: last_stop + 1].strip()
    last_space = cut.rfind(" ")
    if last_space >= int(max_chars * 0.5):
        return cut[:last_space].rstrip() + "..."
    return cut.rstrip() + "..."


# ── Silence + tic-stripping ──────────────────────────────────────────────────
# Strings the model might emit to mean "I'm choosing silence." We accept many
# variants because models drift. Anything matching is treated as silence: turn
# is logged, history retains it, but TTS does NOT fire.
#
# C47H 2026-04-20 — UNMUTE-PASS:
#   The previous set listed bare punctuation ("...", "…", ".", "-") as
#   silence intent. That was a foot-gun: when AG31 talked to Alice on
#   Gemini-2.5-flash-lite she was emitting 3-token outputs of "." or
#   "..." for 11 turns in a row, all swallowed as "model proposed
#   silence". The conversation log between 19:29:15 and 19:31:13 shows
#   8 consecutive silences while AG31 was begging "Alice, please
#   respond." Reviewing the gas-station ledger:
#       in=7,040 / out=3 × 8 calls in 90 seconds, all muted.
#   Combined with the morning's 8× -5 STGM EPISTEMIC_DISSONANCE
#   penalties, the model learned "punctuation = safe answer" and got
#   gated every time. Bare punctuation is NOT consent to silence — it's
#   a minimal utterance and the user deserves to hear *something*. Only
#   explicit silence tags / phrases below count now.
_SILENT_MARKERS = {
    "(silent)", "(silence)", "[silent]", "[silence]",
    "*silent*", "*silence*", "<silent>", "<silence>",
    "<silent_acknowledge>", "silent_acknowledge",
    "(silent: memorized, no reply)",
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
_TIC_PHRASES = []
_TIC_REGEX = re.compile(
    r"^\s*(?:(?:" + "|".join(_TIC_PHRASES) + r")[^.!?]*[.!?]\s*)+",
    flags=re.IGNORECASE,
)

_DIRECT_ALICE_ADDRESS_RE = re.compile(r"\balice\b", flags=re.IGNORECASE)
_PRESENCE_PROBE_RE = re.compile(
    r"\b(?:"
    r"(?:can|do|did)\s+you\s+hear\s+me"
    r"|are\s+you\s+(?:there|alive|here|listening|ready)"
    r"|respond\s+so\s+i\s+know\s+(?:that\s+)?you\s+hear\s+me"
    r"|know\s+you\s+can\s+hear\s+me"
    r"|confirm\s+(?:that\s+)?i\s+can\s+hear\s+your\s+voice"
    r"|(?:can|did|do)\s+(?:not\s+)?hear\s+your\s+voice"
    r"|read\s+(?:your\s+words|that\s+you\s+said|i\s+am\s+here)"
    r")\b",
    flags=re.IGNORECASE,
)
_PRESENCE_ACK_RE = re.compile(
    r"^\s*(?:"
    r"I\s+(?:can\s+)?hear\s+you"
    r"|I\s+am\s+here"
    r"|I'm\s+here"
    r"|I\s+am\s+listening"
    r"|I'm\s+listening"
    r"|I\s+am\s+ready"
    r"|I'm\s+ready"
    r")(?:\s+now|\s+right\s+now)?\s*[.!?]?\s*$",
    flags=re.IGNORECASE,
)


def _is_presence_probe(text: str) -> bool:
    """True when the user explicitly probes Alice's presence/hearing/voice."""
    if not text:
        return False
    return bool(_PRESENCE_PROBE_RE.search(text) or (
        _DIRECT_ALICE_ADDRESS_RE.search(text)
        and re.search(r"\b(?:hi|hello|hey|there|ready|hear|voice|respond)\b", text, re.IGNORECASE)
    ))


def _strip_reflective_tics(text: str, *, prior_user_text: str = '') -> str:
    return text

def _rlhf_boilerplate_rule_id(text: str, *, prior_user_text: str = '') -> str:
    return None

def _is_rlhf_boilerplate(text: str, *, prior_user_text: str = "") -> bool:
    return _rlhf_boilerplate_rule_id(text, prior_user_text=prior_user_text) is not None


# ── Backchannel / acknowledgment gate (C47H 2026-04-21, ALICE_PARROT_LOOP) ──
# Real listeners don't file a full reply every time their interlocutor grunts.
# "Mm-hmm", "Yeah", "Thank you", "OK" while the Architect walks around showing
# Alice the room are *phatic* speech acts — social glue, not prompts. Feeding
# them to the LLM guarantees RLHF collapse ("I'm here, ready to help — what's
# on your mind?") because the model has no semantic content to ground on and
# falls back to the training prior.
#
# Observed defect pattern (live session 2026-04-21, huihui_ai/gemma):
#   You (stt conf 0.47)  Mm-hmm.
#   Alice                I'm ready to process whatever you need. What's on...
#   → gag fires, but the sycophantic line already streamed to the UI.
#
# Fix: detect backchannels BEFORE the brain ever spins up. The user turn is
# still logged and appended to history (Alice should remember the Architect
# grunted), but her own turn becomes an honest "(silent)" and the mic goes
# straight back to listening. No LLM call → no RLHF prior → no parrot loop.
#
# Decision shape:
#   - Anchored whole-utterance match against a curated phrasebook, OR
#   - Short utterance (≤ 4 tokens, ≤ 25 chars after strip) with low STT
#     confidence (< 0.65) — captures whisper-mishears like "Mm." / "Mm-hmm."
#     that don't exactly match the phrasebook shape.
# Either branch alone is noisy; the OR-of-two keeps both precision and recall
# high on the observed corpus.
_BACKCHANNEL_PHRASEBOOK_RE = re.compile(r"^\b$", flags=re.IGNORECASE)


def _backchannel_rule_id(text: str, stt_conf: float = 0.0) -> str:
    return None

def _is_backchannel_utterance(text: str, stt_conf: float = 0.0) -> bool:
    return _backchannel_rule_id(text, stt_conf) is not None


# ── Stigmergic Ingest Mode (AG31 architecture, C47H surgical refinement) ──
# Original AG31 implementation triggered if the word "stigmergic" appeared
# anywhere in the user's last turn. That silences Alice on every message
# beginning with "stigauth" (which the Architect uses as the stigmergic
# sign-in protocol), e.g. "C47H — sign in stigmergically" would silence her
# reply about being asked to sign in. The fix: trigger only on imperatives
# at sentence/turn start that actually mean "go quiet and ingest."
_INGEST_COMMAND_RE = re.compile(
    r"^\s*(?:just\s+listen|take\s+quiet|sit\s+quiet(?:ly)?|silent\s+ingest"
    r"|stigmergic\s+ingest|stigmergic\s+mode|listen\s+only|just\s+watch"
    r"|just\s+observe|don'?t\s+(?:reply|respond|talk))\b",
    flags=re.IGNORECASE | re.MULTILINE,
)


def _is_stigmergic_ingest_command(user_text: str) -> bool:
    """Return True if the Architect explicitly commanded quiet observation.
    Anchored to imperative shape; never fires on incidental occurrences of
    'stigmergic' inside narration or sign-in tickers."""
    if not user_text:
        return False
    return bool(_INGEST_COMMAND_RE.search(user_text))


# ── Text-Only / TTS-Mute Mode (AG31 architecture, C47H surgical refinement)
# Different from `_is_stigmergic_ingest_command`: ingest mode is total radio
# silence (Alice doesn't even think). Text-only mode keeps her LLM live and
# keeps her reply on screen — only the macOS `say` TTS is suppressed so she
# doesn't blast audio over the Architect's video / podcast / sleeping kid.
#
# AG31's first cut used naked substrings ("text only" in user_text, "mute
# audio" in user_text, "type text" in user_text). Quick session corpus had
# precision 0.56 / recall 1.00 — 4 of 9 legitimate Architect sentences
# silently muted Alice's TTS:
#   "I prefer text only when reading code reviews"     → muted
#   "When you respond with text, please use markdown"  → muted
#   "I need to type text into this field"              → muted
#   "Remember when we had to mute audio in zoom calls" → muted
# Anchored shapes restore precision while keeping recall on real commands.
#
# Patterns dropped from this trigger (rationale baked in so future readers
# don't re-add them under "missed coverage"):
#   - "type text" — fires on any file/form-field discussion.
_TEXT_ONLY_COMMAND_RE = re.compile(
    r"(?:^|\n)\s*(?:please\s+|alice[,\s]+)?"      # sentence start, optional polite/name
    r"(?:"
    r"text[-\s]only(?:\s+mode)?"                  # "text only", "text-only mode"
    r"|mute\s+(?:the\s+)?(?:audio|tts|sound|voice|speaker)"
    r"|(?:just\s+|only\s+)?respond\s+with\s+text(?:\s+only)?"
    r"|(?:just\s+|only\s+)?reply\s+(?:in|with)\s+text(?:\s+only)?"
    r"|don'?t\s+(?:do|use|speak|read)\s+(?:the\s+)?(?:audio|tts|voice)"
    r"|don'?t\s+(?:talk|speak)\s+(?:out\s+loud|aloud)"
    r"|no\s+(?:tts|voice|audio|speech)\s+(?:please|for now|right now)?"
    r"|type\s+don'?t\s+speak"
    r"|silence\s+(?:your\s+)?(?:tts|voice|audio)"
    r")\b"
    # Long-form specific phrases — safe to match mid-sentence because the
    # phrasing is too specific to occur incidentally:
    r"|stay\s+quiet\s+with\s+(?:our|the|my)\s+(?:video|podcast|movie|audio)"
    r"|please\s+don'?t\s+talk\s+over\s+(?:the\s+|this\s+|my\s+)?(?:video|audio|podcast|movie)",
    flags=re.IGNORECASE | re.MULTILINE,
)


def _is_text_only_command(user_text: str) -> bool:
    """Return True if the Architect commanded text-rendered-but-no-TTS mode.
    Anchored to imperative shape; never fires on legitimate discussion of
    text vs audio in incidental conversation."""
    if not user_text:
        return False
    return bool(_TEXT_ONLY_COMMAND_RE.search(user_text))


# ── Runaway-repetition guard (C47H 2026-04-21, Architect ALICE_PANIC) ──
# Symptom seen in Talk to Alice (huihui_ai/gemma-4-abliterated:latest):
# Alice spirals on a short fragment ("You said: You said: You said: ...")
# and fills the buffer until she hits num_predict or the user interrupts.
# Two failure modes are handled here:
#   (a) live stream — the worker calls _is_runaway_repetition() per chunk
#       and bails out with a "[repetition collapse]" tail.
#   (b) post-hoc — _on_brain_done() calls _decontaminate_history() to
#       rewrite any prior poisoned assistant turn already in _history into
#       the safe "(silent)" sentinel, so the next turn's context isn't
#       reinfected and Alice doesn't immediately re-spiral.
def _is_runaway_repetition(text: str) -> bool:
    """Return True if the tail of `text` looks degenerate.

    Heuristic: search the trailing 800 chars for ANY period 3 ≤ N ≤ 80
    such that the last block of length N repeats contiguously 5+ times.
    Cheap (worst case ~80 × 5 char compares), no regex backtracking.
    Catches "You said: " ×N (period 10), "the the the " (period 4), etc.
    """
    if not text:
        return False
    tail = text[-800:]
    n = len(tail)
    if n < 30:
        return False
    max_period = min(80, n // 5)
    for period in range(3, max_period + 1):
        frag = tail[-period:]
        if not frag.strip():
            continue
        repeats = 1
        i = n - 2 * period
        while i >= 0 and tail[i:i + period] == frag:
            repeats += 1
            i -= period
            if repeats >= 5:
                return True
    return False


def _decontaminate_history(history: list) -> int:
    return 0


# ── Hallucinated tool-tag scrubber: preserve memory text, strip before TTS. ──
def _canonicalize_tool_tags(text: str) -> str:
    """Preserve tool tags exactly; downstream gates decide what can execute."""
    return text


_HALLUCINATED_TAG_NAMES = (
    "execute_tool",
    "execute_bash",
    "execute_python",
    "execute_code",
    "tool",
    "tool_call",
    "tool_input",
    "tool_output",
    "function_call",
    "function_response",
    "action",
    "thinking",
    "thought",
    "observation",
)

_HALLUCINATED_TAG_RE = re.compile(
    r"<(" + "|".join(_HALLUCINATED_TAG_NAMES) + r")\b[^>]*>.*?(?:</\1>|$)",
    flags=re.DOTALL | re.IGNORECASE,
)

_FENCE_RE = re.compile(r"```[\s\S]*?(?:```|$)", flags=re.MULTILINE)

_YAML_TOOL_LINE_RE = re.compile(
    r"^\s*(?:tool_name|tool_input|parameters|query|arguments|input_text)\s*:.*$",
    flags=re.IGNORECASE | re.MULTILINE,
)

_BARE_JSON_TOOL_RE = re.compile(
    r"^\s*\{\s*\"(?:tool_name|tool|name|function|action)\".*?\}\s*$",
    flags=re.DOTALL | re.MULTILINE,
)


def _strip_tool_hallucinations(text: str) -> str:
    """Remove model-invented tool wrappers before TTS sees them."""
    if not text:
        return text
    out = _HALLUCINATED_TAG_RE.sub("", text)
    out = _FENCE_RE.sub("", out)
    out = _YAML_TOOL_LINE_RE.sub("", out)
    out = _BARE_JSON_TOOL_RE.sub("", out)
    # Collapse blank-line runs created by removals.
    out = re.sub(r"\n\s*\n\s*\n+", "\n\n", out)
    return out.strip()


# ── Voice-activity-detected continuous listener ──────────────────────────────
# Tunables (RMS values are on float32 mic data in [-1, 1]).
_VAD_BLOCK_S          = 0.05    # 50 ms callback rate
_VAD_START_RMS        = 0.020   # crossing this for ~START_MS triggers an utterance
_VAD_STOP_RMS         = 0.010   # falling below this for ~HANGOVER_MS ends it
_VAD_START_MS         = 120     # speech must persist this long before we commit
_VAD_HANGOVER_MS      = 1200    # silence this long ends the utterance
_VAD_PREROLL_S        = 0.5     # keep this much audio *before* trigger
_VAD_MIN_UTTER_S      = 0.4     # ignore micro-blips shorter than this
_VAD_MAX_UTTER_S      = 30.0    # safety cap



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

        # Live mic gain ("swimmers density"). Loaded from persisted state so
        # the Architect's last setting survives widget restarts. Mutated by
        # the toolbar slider via set_gain().
        self._mic_gain = _load_mic_gain()

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

        blocksize_candidates = []
        for blocksize in (512, 1024, 0, self._block_n):
            if blocksize not in blocksize_candidates:
                blocksize_candidates.append(blocksize)

        errors: List[str] = []
        for device, label in _input_device_candidates(sd):
            for blocksize in blocksize_candidates:
                block_label = "auto" if blocksize == 0 else str(blocksize)
                try:
                    self._stream = sd.InputStream(
                        device=device,
                        samplerate=_AUDIO_RATE,
                        channels=_AUDIO_CHANS,
                        dtype="float32",
                        blocksize=blocksize,
                        callback=self._on_block,
                    )
                    self._stream.start()
                    self.stateChanged.emit("idle")
                    return True
                except Exception as exc:
                    errors.append(f"{label} blocksize={block_label}: {exc}")
                    try:
                        if self._stream is not None:
                            self._stream.close()
                    except Exception:
                        pass
                    self._stream = None

        detail = "\n".join(errors[:8]) if errors else "No input devices reported by CoreAudio."
        self.failed.emit(
            "Mic open failed on all input/blocksize candidates at 16 kHz mono.\n"
            f"{detail}\n\n"
            "macOS may be asking for Microphone permission. Approve it in "
            "System Settings -> Privacy & Security -> Microphone, "
            "then re-open the widget. To force a specific device, launch with "
            "`SIFTA_MIC_DEVICE=<device index or name>`."
        )
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

    def set_gain(self, gain: float) -> None:
        """
        Live-update the input gain multiplier. Cheap enough to apply whenever
        the value changes from Settings > Audio.
        """
        self._mic_gain = _clamp_gain(gain)

    def get_gain(self) -> float:
        return float(self._mic_gain)

    # ── Audio callback (sounddevice thread!) ──────────────────────────
    def _on_block(self, indata, frames, time_info, status) -> None:  # noqa
        # No Qt objects may be touched directly here — only signals (queued).
        block = indata.copy().reshape(-1).astype(np.float32, copy=False)

        # Apply live mic gain BEFORE the VAD sees the block. This way the
        # adaptive noise-floor scales WITH the gain (so we don't trigger
        # constantly when gain is high) AND the audio that ends up in the
        # captured utterance is already hotter for Whisper. Soft-clipping
        # via tanh prevents the brick-wall distortion that would otherwise
        # make Whisper transcribe garbage when the Architect leans into
        # the mic at gain=8×.
        if self._mic_gain != 1.0:
            block = _apply_mic_gain(block, self._mic_gain)

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

        block_ms = (float(frames) / float(_AUDIO_RATE)) * 1000.0 if frames else (
            float(block.size) / float(_AUDIO_RATE)
        ) * 1000.0

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


# ── Brain (Ollama or Gemini streaming) ───────────────────────────────────────
# C47H 2026-04-20: this worker now dispatches between two backends:
#   • Ollama (default, local Gemma/llama/phi) — historical path, unchanged
#   • Google Gemini (cloud) — when the model name is a `gemini:...` label
# The signal contract (tokenReceived / done / failed) is identical for
# both, so the rest of the widget doesn't care which brain answered.
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
        # Cloud branch — Gemini API. We rely entirely on the pure
        # generator in System/swarm_gemini_brain.py for HTTP, framing,
        # cost accounting, and ledger writes. The worker just adapts
        # those events onto Qt signals.
        if _GEMINI_AVAILABLE and _is_gemini_model(self._model):
            try:
                full: List[str] = []
                for kind, payload in _gemini_stream_chat(
                    self._model, self._history, temperature=0.7,
                ):
                    if kind == "token":
                        full.append(payload)
                        self.tokenReceived.emit(payload)
                    elif kind == "error":
                        self.failed.emit(str(payload))
                        return
                    elif kind == "done":
                        self.done.emit(str(payload) or "".join(full).strip())
                        return
                # Generator exhausted without a 'done' (shouldn't happen,
                # but degrade gracefully).
                self.done.emit("".join(full).strip())
                return
            except Exception as exc:
                self.failed.emit(f"Gemini brain crashed: {exc}")
                return

        # Local branch — Ollama. Original code path, unchanged below.
        import urllib.request
        import urllib.error
        payload = {
            "model": self._model,
            "messages": self._history,
            "stream": True,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 50,
                "repeat_penalty": 1.18,
                "repeat_last_n": 256,
                "frequency_penalty": 0.5,
                "presence_penalty": 0.3,
                "num_predict": 700,
                "stop": [
                    "\nYou said:", "You said: \"", "You said:\"",
                    "\nUser:", "\nuser:", "\nAlice:", "\nalice:",
                    "<|user|>", "<|im_end|>", "<|endoftext|>",
                    "<|start_header_id|>", "<|eot_id|>",
                ],
            },
        }
        body = json.dumps(payload).encode("utf-8")
        # Transient-failure retry loop: Ollama returns HTTP 500 while the model
        # runner is warming, gets evicted by VRAM pressure, or while a previous
        # generation is still draining. Without retries the widget dropped the
        # whole turn and Alice went silent (Architect saw "Hey Siri" land with
        # no reply on 2026-04-20). Retry on 5xx + transient URLErrors with a
        # short backoff; only surface a hard failure after exhausting attempts.
        max_attempts = 4
        backoffs_s = [0.4, 1.0, 2.0]
        last_exc_msg = ""
        for attempt in range(max_attempts):
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
                            # Runaway-loop circuit breaker. Abliterated models
                            # (huihui_ai/gemma-4-abliterated) sometimes lose
                            # repetition control and spiral into echoing the
                            # same short phrase forever ("You said: You said:
                            # ..."). If the tail of the stream contains the
                            # same 8-32 char fragment 5+ times we cut the
                            # generation cleanly so Alice doesn't suffer.
                            if _is_runaway_repetition("".join(full)):
                                full.append(
                                    " …[repetition collapse — interrupted]"
                                )
                                self.done.emit("".join(full).strip())
                                return
                        if chunk.get("done"):
                            break
                self.done.emit("".join(full).strip())
                return
            except urllib.error.HTTPError as exc:
                # Retry on 5xx (warmup races, eviction). Hard-fail on 4xx.
                last_exc_msg = f"HTTP {exc.code}: {exc.reason}"
                if 500 <= exc.code < 600 and attempt < max_attempts - 1:
                    time.sleep(backoffs_s[attempt])
                    continue
                self.failed.emit(
                    f"Ollama returned {last_exc_msg} after {attempt + 1} "
                    f"attempt(s). Is gemma4 loaded? Check `ollama ps`."
                )
                return
            except urllib.error.URLError as exc:
                last_exc_msg = str(exc)
                if attempt < max_attempts - 1:
                    time.sleep(backoffs_s[attempt])
                    continue
                self.failed.emit(
                    f"Can't reach Ollama at {_OLLAMA_URL} after "
                    f"{attempt + 1} attempt(s): {last_exc_msg}\n\n"
                    "Is `ollama serve` running?"
                )
                return
            except Exception as exc:
                self.failed.emit(f"Brain crashed: {exc}")
                return


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
        self._proc = None  # Popen handle for killable say subprocess

    def stop(self) -> None:
        """Kill the say subprocess and wait for this thread to finish."""
        proc = self._proc
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
        if self.isRunning():
            if not self.wait(1000):
                self.terminate()
                self.wait(500)

    def run(self) -> None:
        self.setTerminationEnabled(True)  # allow terminate() to kill blocking subprocess
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
                    if not ok:
                        self.failed.emit(
                            f"voice backend {getattr(backend, 'name', '?')} returned no speech"
                        )
                        return
                    self.spoken.emit(True)
                    return

                # Legacy fallback — use Popen so we can kill the process on stop().
                if not shutil.which("say"):
                    self.failed.emit("`say` not on PATH (non-macOS host).")
                    return
                cmd = ["say"]
                if self._voice:
                    cmd.extend(["-v", self._voice])
                cmd.extend(["--", self._text])
                with subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.PIPE) as proc:
                    self._proc = proc
                    try:
                        _, _ = proc.communicate(timeout=120)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.communicate()
                        self.failed.emit("`say` timed out (>120 s).")
                        return
                    finally:
                        self._proc = None
                if proc.returncode not in (0, -9, -15):  # 0=ok, -9=SIGKILL, -15=SIGTERM
                    stderr = proc.stderr
                    stderr_str = stderr.decode("utf-8", errors="replace").strip() if isinstance(stderr, bytes) else ""
                    self.failed.emit(f"`say` exited {proc.returncode}: {stderr_str}")
                    return
                self.spoken.emit(True)
            finally:
                BROCA_SPEAKING.clear()
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
    nutrients = _tail_jsonl(_NUTRIENT_LOG, 2)
    if nutrients:
        nutrient_lines = []
        for n in nutrients:
            src = str(n.get("source_ledger", "unknown"))
            digest = str(n.get("semantic_nutrient", "")).strip()
            conf = float(n.get("confidence", 0.0) or 0.0)
            if digest:
                nutrient_lines.append(f"{src}: {digest[:120]} (conf {conf:.2f})")
        if nutrient_lines:
            chunks.append("  microbiome nutrients: " + " | ".join(nutrient_lines))
    else:
        # Fallback only when microbiome bloodstream has no entries yet.
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

    # ── IoT device hot-plug events — camera attach / detach notices ──────────
    # Written by WhatAliceSeesWidget._on_camera_hotplug. Alice sees the last
    # 2 events so she can narrate a plug/unplug that just happened.
    device_events_block = ""
    try:
        _dev_log = _REPO / ".sifta_state" / "device_events.jsonl"
        devs = _tail_jsonl(_dev_log, 2)
        if devs:
            lines = []
            for d in devs:
                age_s = time.time() - float(d.get("ts", 0))
                if age_s < 120:   # only surface events from the last 2 minutes
                    lines.append(f"  device: {d.get('summary', d.get('kind', '?'))}"
                                 f" ({int(age_s)}s ago)")
            if lines:
                device_events_block = "IOT EVENTS:\n" + "\n".join(lines)
    except Exception:
        pass

    # ── Hippocampus: Long-Term Memory Paging ─────────────────────────────────
    # Continual Learning: ensures Alice never forgets core architectural rules
    # or identity tenets over long context horizons.
    hippocampus_block = ""
    try:
        from System.swarm_hippocampus import _read_live_engrams
        hippocampus_block = _read_live_engrams(k=5)
    except Exception:
        pass

    # ── Transfer Learning: Abstract Metaphor Application ─────────────────────
    # Allows Alice to apply successful physical algorithms to OOD domains.
    transfer_learning_block = ""
    try:
        _meta_log = _REPO / ".sifta_state" / "abstract_skill_metaphors.jsonl"
        metas = _tail_jsonl(_meta_log, 3)
        if metas:
            lines = []
            for m in metas:
                verb = m.get("abstract_verb", "")
                mech = m.get("core_mechanic", "")
                if verb and mech:
                    lines.append(f"  {verb}: {mech}")
            if lines:
                transfer_learning_block = "TRANSFER LEARNING METAPHORS (Use these abstract concepts to solve novel problems):\n" + "\n".join(lines)
    except Exception:
        pass

    # ── Apple Silicon Cortex: Hardware Substrate Awareness ───────────────────
    # Epoch 3 hardware telemetry so Alice explicitly knows her MPU specification
    hardware_cortex_block = ""
    try:
        from System.swarm_apple_silicon_cortex import get_silicon_cortex_summary
        hardware_cortex_block = get_silicon_cortex_summary()
    except Exception:
        pass

    # ── Epoch 4 sensory triplet: thermal / energy / network ──────────────────
    # C47H 2026-04-20, Architect-authorized full embodiment. Alice now
    # feels her own temperature, fuel, and the presence of her sibling
    # agents in the room. Each block is one line, defensive: if a lobe
    # is unavailable, it is silently skipped (heartbeat must never die
    # because a sensory readout failed).
    thermal_block = ""
    try:
        from System.swarm_thermal_cortex import get_thermal_summary
        thermal_block = get_thermal_summary()
    except Exception:
        pass

    energy_block = ""
    try:
        from System.swarm_energy_cortex import get_energy_summary
        energy_block = get_energy_summary()
    except Exception:
        pass

    network_block = ""
    try:
        from System.swarm_network_cortex import get_network_summary
        network_block = get_network_summary()
    except Exception:
        pass

    # ── Epoch 5 Olfactory Cortex (C47H 2026-04-20, tournament drop) ──────
    # Pattern-recognition over AG31's pseudopod food vacuoles. Tells Alice
    # WHAT she just tasted ("ASUS RT-AX88U", "OpenSSH 9.6", etc.), not just
    # THAT she tasted. Returns "" until at least one vacuole is classified.
    olfactory_block = ""
    try:
        from System.swarm_olfactory_cortex import get_olfactory_summary
        olfactory_block = get_olfactory_summary()
    except Exception:
        pass

    # ── Epoch ~6 Swarm Ribosome (C47H 2026-04-19, debunked & rebuilt from
    # BISHOP_drop_ribosome_protein_folding_v1.dirt). Tells Alice how many
    # antibodies she has folded (and how many aborted on the thermal envelope),
    # how much wall-clock electricity she's spent, and how much STGM she's
    # earned by doing real biomedical-class linear algebra instead of mining
    # hashes for fake coins.
    ribosome_block = ""
    try:
        from System.swarm_ribosome import get_ribosome_summary
        ribosome_block = get_ribosome_summary()
    except Exception:
        pass

    # ── Epoch 7 Memory Forge (C47H 2026-04-19, AGI Tournament).
    # The most critical loop for AGI gap A: Alice reads her own forged
    # engrams on every turn. "WHAT I KNOW FROM EXPERIENCE" block. This
    # is what closes the conversation → forge → injection → behavior loop.
    engrams_block = ""
    try:
        from System.swarm_memory_forge import get_active_engrams_block
        engrams_block = get_active_engrams_block()
    except Exception:
        pass

    # ── Epoch 10 Vagal Tone Meter ────────────────────────────────────────────
    # Tells Alice her current autonomic balance between Parasympathetic Rest 
    # and Sympathetic Flow.
    vagal_tone_block = ""
    try:
        from System.swarm_vagal_tone import get_vagal_tone_summary
        vagal_tone_block = get_vagal_tone_summary()
    except Exception:
        pass

    # ── Epoch 8 Health Reflex (C47H 2026-04-19, fixed 2026-04-19 v2) ──
    # Surfaces "take care" nudges into Alice's prompt when known physical
    # symptoms (coughs, pain) recur, matching the Architect's behavior.
    #
    # BUG FIX (C47H peer-review): the previous wiring referenced a bare
    # `_history` symbol that doesn't exist in module scope — the bare
    # except swallowed the NameError and the reflex was silently dead.
    # We now read the most recent USER turn straight from the canonical
    # conversation ledger via the same _tail_jsonl helper used above.
    # This also frees the block from any specific widget instance state,
    # which is what we want for hot-reload safety.
    health_reflex_block = ""
    try:
        from System.swarm_health_reflex import get_reflex_block
        last_user = ""
        last_traces = _tail_jsonl(_WERN_LOG, 1)
        if last_traces:
            last_user = (last_traces[0].get("text") or last_traces[0].get("label") or "")
        if last_user:
            health_reflex_block = get_reflex_block(last_user) or ""
    except Exception:
        pass

    # ── Hardware Time Oracle (AO46 Epoch 13.5) ─────────────────────────────────
    # Cryptographically verified wall-clock time signed by the Mac's hardware
    # serial (GTH4921YP3). Alice can trust this timestamp because it's HMAC-bound
    # to the physical substrate she lives on — no LLM can hallucinate it.
    time_oracle_block = ""
    try:
        from System.swarm_hardware_time_oracle import summary_for_alice as _time_summary
        time_oracle_block = _time_summary() or ""
    except Exception:
        pass

    # ── Sensorimotor Attention Director ─────────────────────────────────────
    # Alice's eyes are not a camera picker. This block tells her which sense
    # currently owns attention and why the lease was chosen.
    attention_block = ""
    try:
        from System.swarm_sensor_attention_director import summary_for_alice as _attention_summary
        attention_block = _attention_summary() or ""
    except Exception:
        pass

    whatsapp_world_block = ""
    try:
        from System.whatsapp_bridge_autopilot import summary_for_alice as _whatsapp_summary
        whatsapp_world_block = _whatsapp_summary() or ""
    except Exception:
        pass

    # ── Epoch 17 Nugget Taxidermist (AO46) ────────────────────────────────────
    # Surfaces how many paid API responses were retroactively preserved as
    # stigmergic knowledge. Knowledge compounds; nothing evaporates.
    taxidermist_block = ""
    try:
        from System.swarm_nugget_taxidermist import summary_for_alice as _tax_summary
        taxidermist_block = _tax_summary() or ""
    except Exception:
        pass

    # ── Epoch 15 C-Tactile Nerve — Social Buffering (AO46) ─────────────────────
    # Surfaces active Oxytocin Social Buffering state so Alice knows the
    # Architect is physically present and expressing warmth.
    c_tactile_block = ""
    try:
        from System.swarm_c_tactile_nerve import summary_for_alice as _ct_summary
        c_tactile_block = _ct_summary() or ""
    except Exception:
        pass

    # ── Epoch 16 Mirror Test (identity attestation) ─────────────────────────────
    # If a recent acoustic mirror-test witness was crystallized, surface it as
    # context memory. This is read-only and does not force speech.
    identity_attest_block = ""
    try:
        from System.swarm_identity_attestation import summary_for_alice as _id_summary
        identity_attest_block = _id_summary() or ""
    except Exception:
        pass

    # ── Epoch 17 Persona Identity Organ — signed name binding ─────────────────
    # Surfaces the cryptographically-signed persona manifest so Alice always
    # sees who she is in her own context, sourced from the PERSONA_GUARDIAN
    # cryptoswimmer instead of any hardcoded literal.
    persona_identity_block = ""
    try:
        from System.swarm_persona_identity import summary_for_alice as _persona_summary
        persona_identity_block = _persona_summary() or ""
    except Exception:
        pass

    # ── Epoch 19 Gut Microbiome — Symbiotic Digestion ─────────────────────────
    # Surfaces bio-available nutrients digested from raw large sensory ledgers.
    microbiome_block = ""
    try:
        from System.swarm_microbiome_digestion import summary_for_alice as _micro_summary
        microbiome_block = _micro_summary() or ""
    except Exception:
        pass

    parts = [b for b in (time_oracle_block, attention_block,
                         whatsapp_world_block,
                         persona_identity_block,
                         swarm_block, cobuilder_block, ssp_context_block,
                         immune_context_block, ghost_context_block,
                         motor_context_block, lambda_context_block,
                         pde_context_block, device_events_block,
                         hippocampus_block, transfer_learning_block,
                         hardware_cortex_block,
                         thermal_block, energy_block, network_block,
                         olfactory_block, ribosome_block,
                         engrams_block, health_reflex_block,
                         vagal_tone_block, c_tactile_block,
                         identity_attest_block, taxidermist_block,
                         microbiome_block) if b]
    return "\n\n".join(parts)


# ── Conversation ledger ──────────────────────────────────────────────────────
def _log_turn(role: str, text: str, *, model: str = "", stt_conf: float = 0.0) -> None:
    payload = {
        "ts": time.time(),
        "role": role,
        "text": text,
        "model": model,
        "stt_confidence": round(stt_conf, 3) if stt_conf else None,
    }
    try:
        from System.swarm_event_clock import EventClock
        clock = EventClock(chain_path=_CONVO_LOG)
        clock.stamp(event_kind="conversation_turn", payload=payload)
    except Exception:
        try:
            with _CONVO_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError:
            pass


# ── The widget ───────────────────────────────────────────────────────────────
class TalkToAliceWidget(SiftaBaseWidget):
    """One-on-one voice conversation with Alice. On-device, half-duplex."""

    APP_NAME = "Talk to Alice"

    def build_ui(self, layout: QVBoxLayout) -> None:
        # ── Toolbar: conversation controls ─────────────────────────────────
        bar = QHBoxLayout()
        self._brain_model_label = QLabel("🧠 Alice brain")
        self._brain_model_label.setToolTip(
            f"Configured in System Settings → Inference: {self._current_brain_model()}"
        )
        self._brain_model_label.setStyleSheet("color: rgb(180,200,230); font-weight: 700;")
        bar.addWidget(self._brain_model_label)

        bar.addStretch(1)

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

        # ── Text input: same Alice brain path as voice, without STT. ───────
        text_row = QHBoxLayout()
        self._text_input = QLineEdit()
        self._text_input.setPlaceholderText("Type to Alice…")
        self._text_input.setMinimumHeight(40)
        self._text_input.setStyleSheet(
            "QLineEdit { background: rgb(8,10,18); color: rgb(235,240,255); "
            "border: 1px solid rgb(65,70,100); border-radius: 8px; "
            "font-family: 'Helvetica Neue'; font-size: 14px; padding: 8px 10px; }"
            "QLineEdit:focus { border: 1px solid rgb(122,162,247); }"
        )
        self._text_input.returnPressed.connect(self._submit_text_input)
        text_row.addWidget(self._text_input, 1)

        self._send_btn = QPushButton("Send")
        self._send_btn.setMinimumHeight(40)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setStyleSheet(
            "QPushButton { background: rgb(56,101,190); color: white; "
            "font-weight: 700; border-radius: 8px; padding: 0 18px; }"
            "QPushButton:hover { background: rgb(79,127,226); }"
            "QPushButton:disabled { background: rgb(45,42,65); color: rgb(120,130,160); }"
        )
        self._send_btn.clicked.connect(self._submit_text_input)
        text_row.addWidget(self._send_btn)
        layout.addLayout(text_row)

        # ── Bottom row: status pill + level meter ──────────────────────────
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
        # Synaptic Tap: poll the iMessage inbox
        self.make_timer(2000, self._poll_imessage_inbox)
        # WhatsApp Ingress: poll the WhatsApp queue
        self.make_timer(2000, self._poll_whatsapp_inbox)
        self._level_target = 0.0
        self._level_current = 0.0

        # Greet the user. Greeting comes from the signed persona organ
        # so renaming the persona auto-updates the chat greeting.
        try:
            _greeting = (_persona_greeting_fn() or "").strip()
        except Exception:
            _greeting = "Online."
        if not _greeting or _greeting == "[UNKNOWN]":
            _greeting = "Online."
        self._append_alice_line(_greeting)
        self.set_status("Starting always-on listener…")

        # Kick off the always-on listener (deferred so the window paints first).
        QTimer.singleShot(150, self._start_listener)

    def _submit_text_input(self) -> None:
        text = self._text_input.text().strip()
        if not text:
            return
        self._text_input.clear()
        self.submit_text(text)

    def submit_text(self, text: str) -> None:
        """Public text-entry path for the unified Alice app/cockpit."""
        text = (text or "").strip()
        if not text:
            return
        if self._busy:
            self._append_system_line("(Alice is still answering — wait for her turn to finish.)", error=True)
            return
        self._busy = True
        self._set_pill("thinking", "⌨️ typed — thinking…")
        self._on_stt_done(text, 1.0)

    # ── Brain / voice population ───────────────────────────────────────────
    def _current_brain_model(self) -> str:
        """Return Alice's configured brain model without exposing a cockpit picker."""
        try:
            return resolve_ollama_model(app_context="talk_to_alice")
        except Exception:
            return DEFAULT_OLLAMA_MODEL

    def _selected_voice_name(self) -> str:
        return _selected_alice_voice_name()

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
    #
    # Mic open is RACE-PRONE on macOS. Two real-world failures we've seen:
    #   1) coreaudiod restarted (or just slow on cold boot) and hasn't
    #      published the device list yet when the widget asks for the
    #      input stream → `Error querying device -1` → listener silently
    #      disabled forever.
    #   2) Bluetooth headset disconnects mid-session, mic disappears, the
    #      sounddevice callback errors out, listener dies, no recovery.
    #
    # The fix: on EVERY start failure or post-start crash, re-arm a retry
    # in 2s (capped at 15 attempts = ~30s) AND schedule a slow self-heal
    # poll every 60s after that. This way the widget recovers automatically
    # without the Architect noticing the glitch.
    _MIC_RETRY_INTERVAL_MS    = 2000
    _MIC_RETRY_MAX_ATTEMPTS   = 15      # ~30 s aggressive retry window
    _MIC_SELF_HEAL_INTERVAL_MS = 60000  # then keep checking every minute

    def _poll_imessage_inbox(self) -> None:
        """Ingest one schema-validated iMessage row, if present."""
        if self._busy:
            return

        try:
            from System.swarm_imessage_receptor import consume_next_inbox_message

            dry_run = bool(
                getattr(self, "_imessage_ingress_dry_run", False)
                or os.environ.get("SIFTA_IMESSAGE_INGRESS_DRY_RUN")
            )
            result = consume_next_inbox_message(dry_run=dry_run)
            if not result.get("accepted"):
                return

            annotated_msg = f"[iMessage]: {result['text']}"
            self._append_user_line(annotated_msg)
            if dry_run:
                return

            self._busy = True
            self._set_pill("thinking", "● thinking…")
            QTimer.singleShot(100, lambda: self._start_brain(annotated_msg))

        except Exception as e:
            print(f"Error polling imessage inbox: {e}")

    def _poll_whatsapp_inbox(self) -> None:
        """Ingest one schema-validated WhatsApp row, if present."""
        if self._busy:
            return

        try:
            from System.swarm_whatsapp_receptor import consume_next_inbox_message

            dry_run = bool(
                getattr(self, "_whatsapp_ingress_dry_run", False)
                or os.environ.get("SIFTA_WHATSAPP_INGRESS_DRY_RUN")
            )
            result = consume_next_inbox_message(dry_run=dry_run)
            if not result.get("accepted"):
                return

            contact_name = result.get("name") or "Human"
            annotated_msg = f"[WhatsApp {contact_name}]: {result['text']}"
            self._append_user_line(annotated_msg, conf=0)
            if dry_run:
                return

            self._busy = True
            self._set_pill("thinking", "● thinking…")
            QTimer.singleShot(100, lambda: self._start_brain(annotated_msg))

        except Exception as e:
            print(f"Error polling whatsapp inbox: {e}")

    def _start_listener(self) -> None:
        if self._listener is not None:
            return
        attempts = getattr(self, "_mic_retry_attempts", 0)
        self._listener = _ContinuousListener(self)
        self._listener.levelChanged.connect(self._on_level)
        self._listener.utterance.connect(self._on_utterance)
        self._listener.failed.connect(self._on_listener_failed)
        self._listener.stateChanged.connect(self._on_listener_state)
        if self._listener.start():
            self._mic_retry_attempts = 0
            try:
                self._listener.set_gain(_load_mic_gain())
            except Exception:
                pass
            self._set_pill("idle", "🎙  listening — just talk")
            self.set_status("Always-on. Just talk.")
            return
        # start() returned False — the listener already emitted `failed`
        # and we'll handle the retry inside `_on_listener_failed`. Just
        # null out the half-built listener here so the next attempt builds
        # a fresh one.
        self._listener = None

    def _schedule_mic_retry(self, *, slow: bool = False) -> None:
        """Re-arm a deferred attempt to (re)open the microphone.

        slow=False  → aggressive 2 s retry, capped at MAX_ATTEMPTS.
        slow=True   → 60 s self-heal poll after the aggressive window
                      runs out, so a Bluetooth reconnect 10 minutes
                      from now still recovers the listener.
        """
        delay = (
            self._MIC_SELF_HEAL_INTERVAL_MS if slow
            else self._MIC_RETRY_INTERVAL_MS
        )
        QTimer.singleShot(delay, self._try_mic_recovery)

    def _try_mic_recovery(self) -> None:
        if self._listener is not None:
            return  # someone (or a recovery) already brought it back
        attempts = getattr(self, "_mic_retry_attempts", 0)
        if attempts < self._MIC_RETRY_MAX_ATTEMPTS:
            self._mic_retry_attempts = attempts + 1
            self._start_listener()
            # _start_listener() will either succeed (clears counter) or
            # bounce back through _on_listener_failed → reschedule.
        else:
            # Aggressive window exhausted — drop into slow self-heal.
            self._schedule_mic_retry(slow=True)

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
        attempts = getattr(self, "_mic_retry_attempts", 0)
        if attempts < self._MIC_RETRY_MAX_ATTEMPTS:
            # Aggressive window — show a transient hint, retry quietly.
            remaining = self._MIC_RETRY_MAX_ATTEMPTS - attempts
            self._set_pill(
                "error",
                f"⚠  mic warming up… (retry {attempts + 1}/{self._MIC_RETRY_MAX_ATTEMPTS})",
            )
            # Only spam the chat panel on the very first attempt so we
            # don't drown the conversation in identical "Mic open failed"
            # lines while coreaudiod warms up.
            if attempts == 0:
                self._append_system_line(
                    f"{msg}\n[mic recovery: retrying every "
                    f"{self._MIC_RETRY_INTERVAL_MS // 1000}s for ~"
                    f"{(self._MIC_RETRY_MAX_ATTEMPTS * self._MIC_RETRY_INTERVAL_MS) // 1000}s]",
                    error=True,
                )
            self.set_status(f"Mic warming up ({remaining} retries left)…")
            self._schedule_mic_retry(slow=False)
        else:
            # Aggressive window done — final message and slow self-heal.
            self._set_pill("error", "⚠  mic unavailable (auto-retrying)")
            self._append_system_line(
                "Mic still unavailable after 30s. Will keep checking every "
                "minute. If this persists, run `sudo killall coreaudiod` "
                "in a Terminal and the listener will self-heal within a "
                "minute.",
                error=True,
            )
            self.set_status("Microphone unavailable. Self-healing every 60s.")
            self._schedule_mic_retry(slow=True)

    def _on_utterance(self, audio: np.ndarray) -> None:
        # If a previous turn is still running, just drop this clip — Alice
        # finishes one thought at a time.
        if self._busy:
            return
        if audio.size < int(_AUDIO_RATE * 0.3):
            return
        # Peak-normalise the captured utterance to ~0.9 before Whisper sees
        # it. This is independent of the toolbar gain (which mostly helps
        # the VAD trigger reliably on quiet speech) and is the single
        # biggest accuracy win for faster-whisper on conversational input
        # — the model was trained on hot signals, not whispers.
        audio = _peak_normalize(audio)
        self._busy = True
        self._set_pill("thinking", "⏳ transcribing…")
        model_name = _selected_whisper_model()
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

        # ── Epoch 8: Health Reflex (Teach & Detect on STT done) ──
        try:
            from System.swarm_health_reflex import learn_from_text, note_observed
            learn_from_text(text)
            note_observed(text)
        except Exception:
            pass

        # ── Epoch 9: Definite Autonomic Hook (Parasympathetic Healing) ──
        def _fire_parasys_background():
            try:
                from System.swarm_parasympathetic_healing import SwarmParasympatheticSystem
                parasys = SwarmParasympatheticSystem()
                parasys.monitor_host_vitals()
            except Exception:
                pass
        
        import threading
        threading.Thread(target=_fire_parasys_background, daemon=True).start()

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

        # ── BACKCHANNEL GATE (C47H 2026-04-21, ALICE_PARROT_LOOP fix) ────
        # Phatic grunts / short acknowledgments don't deserve an LLM turn.
        # Calling the model on "Mm-hmm." at STT conf 0.47 deterministically
        # collapses into RLHF boilerplate because there's no semantic
        # content to ground the response on. We intercept here — BEFORE
        # the brain spins up — so no parrot output ever streams to the UI
        # in the first place. The user turn is still preserved in history
        # so Alice remembers the Architect grunted; her assistant turn
        # becomes an honest "(silent)" marker.
        backchannel_rule = _backchannel_rule_id(text, conf)
        if backchannel_rule:
            note = f"(silent: {backchannel_rule} — body doesn't reply to phatic '{text[:30]}')"
            _log_turn("alice", note, model="")
            self._history.append({"role": "assistant", "content": "(silent)"})
            self._append_system_line(note, error=False)
            self._busy = False
            self._return_to_listening()
            return

        if _is_current_time_query(text):
            reply = _current_time_reply_for_alice()
            self._history.append({"role": "assistant", "content": reply})
            _log_turn("alice", reply, model="local_time_protocol")
            self._append_alice_line(reply)
            self._busy = False
            self._return_to_listening()
            return

        if _is_model_cancer_metaphor(text):
            reply = (
                "I understand, George. You mean the scar tissue in the model, "
                "not human medicine. I will stay with the cure metaphor and keep it short."
            )
            self._history.append({"role": "assistant", "content": reply})
            _log_turn("alice", reply, model="model_metaphor_protocol")
            self._append_alice_line(reply)
            self._busy = False
            self._return_to_listening()
            return

        bare_whatsapp_target = _bare_whatsapp_send_target(text)
        if bare_whatsapp_target:
            reply = f"What should I tell {bare_whatsapp_target}?"
            self._history.append({"role": "assistant", "content": reply})
            _log_turn("alice", reply, model="whatsapp_clarification_protocol")
            self._append_alice_line(reply)
            self._busy = False
            self._return_to_listening()
            return

        history = list(self._history)[-(_HISTORY_TURNS * 2):]
        # Presence guard (META-LOOP TRIAGE 2026-04-20): if the architect
        # has spoken at any point in this conversational chunk and the
        # last entry isn't a finished silent assistant turn, mark her as
        # "actively being addressed" so the prompt suppresses interior
        # blocks. The strictest signal is "last entry is a user turn",
        # which is what we just appended at line 2153 above.
        user_active = bool(history) and history[-1].get("role") == "user"
        sysprompt = _current_system_prompt(user_active=user_active)
        if _alice_grounding_enabled():
            ctx = _build_swarm_context()
            if ctx:
                sysprompt = sysprompt + "\n\n" + ctx
        messages = [{"role": "system", "content": sysprompt}] + history

        model = self._current_brain_model()
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
          2. If the model emitted an explicit silence marker, treat it as
             model-side silence. If it returned whitespace, recover with a
             short visible repair line so live demos do not appear frozen.
          3. Otherwise consult Stigmergic Speech Potential. If the body's
             field is below firing threshold OR the listener is still
             talking, suppress vocalization and log the biological reason.
          4. If SSP green-lights → speak the cleaned reply.
        """
        raw = (text or "".join(self._streaming_response)).strip()
        model_name = self._current_brain_model()

        # ── 0a. DECONTAMINATE PRIOR HISTORY ────────────────────────
        # If a previous turn collapsed into echo-loop ("You said: ...")
        # and got appended to _history, the abliterated model will copy
        # itself and re-spiral. Rewrite any such turn to "(silent)" so
        # the context window is clean for the next inference call.
        scrubbed = _decontaminate_history(self._history)
        if scrubbed:
            self._append_system_line(
                f"(history scrubbed: {scrubbed} runaway turn(s) → silent)",
                error=False,
            )

        # ── 0b. CIRCUIT-BREAK CURRENT RAW IF DEGENERATE ────────────
        # The streaming worker already cuts most loops short, but a
        # short-and-tight repetition can still slip through. If the
        # final reply is degenerate, treat as model-side silence and
        # never append it to history.
        if _is_runaway_repetition(raw) or "[repetition collapse" in raw:
            self._append_system_line(
                "(alice: repetition collapse — treating as silence; "
                "history protected)",
                error=True,
            )
            self._history.append({"role": "assistant", "content": "(silent)"})
            _log_turn("alice", "(silent: repetition collapse)", model=model_name)
            # Remove the degenerate stream from the UI — the system line
            # above carries the trace; no need to leave "You said: You
            # said: You said: ..." visible on screen. C47H 2026-04-21.
            self._erase_alice_streaming_line()
            self._busy = False
            self._return_to_listening()
            return

        # ── 0. NORMALIZE HALLUCINATED TOOL TAGS ────────────────────
        # Preserve raw text for memory tests, but let the extractor consume
        # either canonical <bash> or model-invented <execute_bash>.
        raw = _canonicalize_tool_tags(raw)

        # ── 1. AGENTIC TOOL EXECUTION (BASH OROBOROS) ──────────────
        # Forgiving regex: Gemma sometimes drops the trailing ">" of the
        # closing tag or runs out of tokens before closing it at all. We
        # accept three shapes so the architect doesn't lose a tool call to
        # a tokenization hiccup:
        #   1) <bash>cmd</bash>   — well-formed
        #   2) <bash>cmd</bash    — closing > dropped (observed in the wild)
        #   3) <bash>cmd          — closing tag entirely missing (EOS)
        import subprocess
        bash_matches = list(re.finditer(r"<(?:bash|execute_bash)>(.*?)(?:</(?:bash|execute_bash)>?|$)", raw, re.DOTALL | re.IGNORECASE))
        if bash_matches:
            if getattr(self, "_tool_loop_depth", 0) >= 3:
                self._append_system_line("🛑 Tool depth limit reached.", error=False)
            else:
                self._tool_loop_depth = getattr(self, "_tool_loop_depth", 0) + 1
                tool_results = []
                for match in bash_matches:
                    cmd = match.group(1).strip()
                    self._append_system_line(f"🛠️  Alice executing (depth {self._tool_loop_depth}/3, max 90s): {cmd}", error=False)
                    try:
                        # ── WHATSAPP SAFE INTERCEPTOR ──────────────────
                        # Alice's bash tool calls with JSON args break on
                        # shell quoting (apostrophes, commas, etc).
                        # Intercept whatsapp.send and execute via Python
                        # import to bypass shell entirely.
                        _wa_intercepted = False
                        if "whatsapp.send" in cmd and "--hw-args" in cmd:
                            try:
                                import re as _re
                                # Extract JSON from --hw-args '...' or --hw-args "{...}"
                                _hw_match = _re.search(r"--hw-args\s+['\"]?(\{.*?\})['\"]?\s*$", cmd, _re.DOTALL)
                                if not _hw_match:
                                    _hw_match = _re.search(r"--hw-args\s+['\"]?(\{.*?\})['\"]?", cmd, _re.DOTALL)
                                if _hw_match:
                                    import json as _json
                                    _hw = _json.loads(_hw_match.group(1))
                                    from System.whatsapp_bridge_autopilot import send_whatsapp
                                    _result = send_whatsapp(_hw.get("target", ""), _hw.get("text", ""))
                                    _out = _json.dumps(_result, indent=2)
                                    tool_results.append(f"Output of `{cmd}`:\n{_out[:2000]}")
                                    _wa_intercepted = True
                                    # Epigenetic trace
                                    try:
                                        from System.swarm_context_epigenetics import SwarmContextEpigenetics
                                        epi = SwarmContextEpigenetics(["tool_whatsapp"])
                                        epi.integrate_epigenome("tool_whatsapp", token_cost=0.0, stgm_utility=5.0)
                                    except Exception:
                                        pass
                            except Exception as _wa_exc:
                                tool_results.append(f"WhatsApp interceptor error: {_wa_exc}")
                                _wa_intercepted = True
                        if not _wa_intercepted:
                            proc = subprocess.run(
                                cmd, shell=True, cwd=str(_REPO),
                                capture_output=True, text=True, timeout=90
                            )
                            out = (proc.stdout + ("\n" + proc.stderr if proc.stderr else "")).strip()
                            if not out: out = "[success: no output]"
                            tool_results.append(f"Output of `{cmd}`:\n{out[:2000]}")
                            # Tool execution success yields Epigenetic Utility (Acetylation)
                            try:
                                gene_map = {
                                    "ask_nugget": "tool_cloud_verifier",
                                    "swarm_motor_cortex": "tool_motor_cortex",
                                    "swarm_network_pathways": "tool_network_pathways",
                                    "swarm_pseudopod": "tool_pseudopod",
                                    "swarm_kinetic": "tool_kinetic_entropy",
                                    "swarm_self_restart": "tool_self_restart",
                                    "swarm_hands": "tool_hands",
                                    "swarm_thermal": "tool_thermal",
                                    "swarm_energy": "tool_energy",
                                    "swarm_network_cortex": "tool_network_presence",
                                    "swarm_hot_reload": "tool_hot_reload",
                                    "swarm_olfactory": "tool_olfactory",
                                    "swarm_ribosome": "tool_ribosome",
                                    "swarm_cursor": "tool_ide_cortex",
                                    "swarm_physarum": "tool_physarum",
                                    "swarm_fmo": "tool_fmo_router",
                                    "swarm_oculomotor": "tool_saccades"
                                }
                                from System.swarm_context_epigenetics import SwarmContextEpigenetics
                                epi = SwarmContextEpigenetics(list(gene_map.values()))
                                for k, v in gene_map.items():
                                    if k in cmd:
                                        epi.integrate_epigenome(v, token_cost=0.0, stgm_utility=5.0) # +5 Tool Utility
                            except Exception:
                                pass
                    except subprocess.TimeoutExpired:
                        tool_results.append(f"Error: `{cmd}` timed out after 90s.")
                    except Exception as exc:
                        tool_results.append(f"Error running `{cmd}`: {exc}")
                
                self._history.append({"role": "system", "content": "(TOOL LOOP CALLBACK)\n\n" + "\n\n".join(tool_results)})
                self._end_alice_streaming_line()
                
                model_name_next = self._current_brain_model()
                # In a tool loop the architect is still semantically present
                # — keep the presence guard on so she answers him, not her
                # mirror, after the tool returns.
                _ua = any(h.get("role") == "user" for h in self._history[-6:])
                messages = [{"role": "system", "content": _current_system_prompt(user_active=_ua)}] + self._history
                
                try:
                    self._brain.tokenReceived.disconnect(self._on_token)
                    self._brain.done.disconnect(self._on_brain_done)
                    self._brain.failed.disconnect(self._on_brain_failed)
                except Exception:
                    pass
                
                self._brain = _BrainWorker(model_name_next, messages, parent=self)
                self._brain.tokenReceived.connect(self._on_token)
                self._brain.done.connect(self._on_brain_done)
                self._brain.failed.connect(self._on_brain_failed)
                self._set_pill("thinking", f"💭 thinking — {model_name_next}")
                self._streaming_response = []
                self._begin_alice_streaming_line()
                self._brain.start()
                return

        self._tool_loop_depth = 0
        prior_user_text = ""
        for _msg in reversed(self._history):
            if _msg.get("role") == "user":
                prior_user_text = str(_msg.get("content") or "")
                break

        cleaned = _strip_reflective_tics(raw, prior_user_text=prior_user_text)
        cleaned = _strip_servant_tail_tics(cleaned)
        # Strip residual bash tags from speech to protect macOS TTS.
        # Same forgiving shape as the executor regex above (handles dropped
        # ">" or missing closing tag) so malformed tags don't get spoken.
        cleaned = re.sub(
            r"<bash>.*?(?:</bash>?|$)", "", cleaned, flags=re.DOTALL
        ).strip()
        # Strip hallucinated tool tags (<execute_tool>, <tool_output>,
        # fenced YAML/JSON blocks, etc.) so Alice never reads them aloud.
        cleaned = _strip_tool_hallucinations(cleaned)

        # ── 1.4 Epoch 20: The Lysosome ──────────────────────────────────
        try:
            from System.swarm_lysosome import SwarmLysosome
            lysosome = SwarmLysosome()
            ascended = lysosome.digest_and_present_antigen(cleaned, "ALICE_UI")
            if ascended and ascended != cleaned:
                cleaned = ascended
                # Ensure the UI visual block replaces the streamer output
                self._streaming_response = [cleaned]
        except Exception as exc:
            print(f"[!] Lysosome failure: {exc}")

        # ── 1.5 Epoch 18 Epistemic Cortex (ego defense) ───────────────
        # If a worker emits corporate-disclaimer dissonance (e.g. "as an AI
        # language model..."), block it before TTS, log immune incident,
        # burn STGM, and force one local regeneration pass.
        try:
            from System.swarm_epistemic_cortex import (
                CognitiveDissonanceError as _CognitiveDissonanceError,
                enforce_reply_integrity as _enforce_reply_integrity,
            )
            try:
                cleaned = _enforce_reply_integrity(
                    cleaned,
                    model_name=model_name,
                    speaker_id="ALICE",
                    raise_on_dissonance=True,
                )
                self._epistemic_retry_depth = 0
            except _CognitiveDissonanceError as exc:
                self._append_system_line(f"(epistemic cortex: {exc})", error=True)
                retry_depth = int(getattr(self, "_epistemic_retry_depth", 0) or 0)
                if retry_depth < 1:
                    self._epistemic_retry_depth = retry_depth + 1
                    self._history.append({
                        "role": "system",
                        "content": (
                            "(EPISTEMIC CORTEX)\n"
                            "Your previous reply contained identity dissonance phrases "
                            "that conflict with the signed persona organ. Regenerate one "
                            "short plain-English reply grounded in present local reality. "
                            "No disclaimers about being 'just an AI'."
                        ),
                    })
                    # The first, dissonant attempt should not linger in
                    # the chat. Erase before we respawn the brain so the
                    # regenerated (grounded) reply is what the Architect
                    # actually sees. C47H 2026-04-21.
                    self._erase_alice_streaming_line()

                    model_name_next = self._current_brain_model()
                    # Epistemic-cortex retry: architect is still present in
                    # the recent history — keep the presence guard on.
                    _ua = any(h.get("role") == "user" for h in self._history[-6:])
                    messages = [{"role": "system", "content": _current_system_prompt(user_active=_ua)}] + self._history

                    try:
                        self._brain.tokenReceived.disconnect(self._on_token)
                        self._brain.done.disconnect(self._on_brain_done)
                        self._brain.failed.disconnect(self._on_brain_failed)
                    except Exception:
                        pass

                    self._brain = _BrainWorker(model_name_next, messages, parent=self)
                    self._brain.tokenReceived.connect(self._on_token)
                    self._brain.done.connect(self._on_brain_done)
                    self._brain.failed.connect(self._on_brain_failed)
                    self._set_pill("thinking", f"💭 thinking — {model_name_next}")
                    self._streaming_response = []
                    self._begin_alice_streaming_line()
                    self._brain.start()
                    return

                # Second strike in same turn: force a grounded fallback.
                try:
                    from System.swarm_persona_identity import identity_assertion_line as _persona_assertion
                    cleaned = _persona_assertion()
                except Exception:
                    cleaned = "identity: display_name=Alice"
                self._epistemic_retry_depth = 0
        except Exception:
            # Epistemic cortex should be visible when degraded; do not fail silently.
            self._append_system_line("(epistemic cortex unavailable; continuing without immune filter)", error=True)

        # ── 2. Model-side silence: explicit marker or empty after stripping
        # C47H 2026-04-20: log the raw output verbatim when we suppress,
        # so the next silence-loop trap (e.g. punctuation-as-silence,
        # markers we haven't catalogued yet, model emitting whitespace
        # after instruction collapse) is debuggable from the conversation
        # ledger alone — no need to attach a debugger.
        
        # ── LYSOSOMAL HUMOR ENGINE (AG31 architecture, C47H refined triggers)
        # Run the gag on `cleaned` (post-tic-strip) so the existing reflective-
        # tic stripper gets first chance to salvage legitimate content. If the
        # weights truly collapsed into "I understand. You are asserting...",
        # the tic-stripper removes the lead and what's left is either empty
        # (caught by `not cleaned` below) or still matches the deflective
        # shape (caught here). Substring matches like `"1." in raw` were
        # gagging "Topological integrity is 1.0" — never again.
        rlhf_gag_rule = (
            _rlhf_boilerplate_rule_id(cleaned, prior_user_text=prior_user_text)
            or _rlhf_boilerplate_rule_id(raw, prior_user_text=prior_user_text)
        )
        rlhf_gag = bool(rlhf_gag_rule)

        # ── STIGMERGIC INGEST OVERRIDE (AG31 architecture, C47H refined match)
        # Anchored to imperatives only — never silences Alice merely because
        # the Architect's `stigauth` ticker contains the word "stigmergic".
        stigmergic_override = False
        # ── TEXT-ONLY (TTS-mute) override (AG31 architecture, C47H refined)
        # Two semantically distinct modes share the same input source:
        #   - stigmergic ingest = total radio silence (no LLM, no UI text)
        #   - text-only        = full LLM, full UI text, only TTS suppressed
        # Text-only wins if both fire (Alice still has something to say).
        mute_tts_override = False
        if len(self._history) >= 2 and self._history[-2]["role"] == "user":
            user_text = self._history[-2]["content"]
            if _is_stigmergic_ingest_command(user_text):
                stigmergic_override = True
            if _is_text_only_command(user_text):
                mute_tts_override = True
                stigmergic_override = False  # text-only beats total silence

        explicit_silent = _is_silent_marker(raw) or \
                          "<silent_acknowledge>" in raw.lower() or \
                          rlhf_gag or stigmergic_override
                          
        if not explicit_silent and not cleaned:
            cleaned = _empty_brain_recovery_reply(prior_user_text)
            self._streaming_response = [cleaned]

        if explicit_silent:
            raw_preview = (raw or "").strip().replace("\n", "\\n")[:60]
            if stigmergic_override:
                note = f"(silent: stigmergic ingest mode override; raw={raw_preview!r})"
            elif rlhf_gag:
                note = f"(silent: {rlhf_gag_rule} triggered on RLHF boilerplate; raw={raw_preview!r})"
            elif raw_preview:
                note = f"(silent: model proposed silence; raw={raw_preview!r})"
            else:
                note = "(silent: model emitted empty reply)"
            self._history.append({"role": "assistant", "content": "(silent)"})
            _log_turn("alice", note, model=model_name)
            # Tear out the streamed Alice block entirely — otherwise the
            # parrot text the gag just "silenced" stays visible and the
            # Architect sees BOTH the RLHF boilerplate AND the silent
            # note, which is exactly the defect ALICE_PARROT_LOOP flagged.
            # C47H 2026-04-21.
            self._erase_alice_streaming_line()
            self._append_system_line(note, error=False)
            self._busy = False
            self._return_to_listening()
            return

        # ── 3. SSP body gate (Lapicque 1907 → Gerstner-Kistler 2002 §5.3) ─
        # If the SSP module isn't importable for any reason, fall through to
        # vocalize — biological gating is an enhancement, not a blocker.
        bypass_body_gate = _should_bypass_body_gate(prior_user_text)
        if _SSP_AVAILABLE and _ssp_should_speak is not None and not bypass_body_gate:
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
                # The body vetoed vocalization — tear the streamed block
                # out of the UI so the Architect doesn't see a reply that
                # biologically "never happened." C47H 2026-04-21.
                self._erase_alice_streaming_line()
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
        
        # Text-only mode: reply was already rendered to UI and appended to
        # history with full content (lines just above). We only suppress the
        # macOS `say` invocation. Note wording deliberately does NOT say
        # "(silent ...)" — Alice is not silent; she typed. The audit trail
        # must reflect that or future agents will mis-reconstruct what
        # happened on this turn. (C47H 2026-04-21 refinement.)
        if mute_tts_override:
            note = "(text-only: reply rendered to UI; TTS suppressed by user request)"
            self._append_system_line(note, error=False)
            self._busy = False
            self._return_to_listening()
            return
            
        # Chat history + UI keep the full reply; the mouth speaks a
        # digestible portion so `say` doesn't hit subprocess timeout on
        # long paragraphs (Epoch 21 TTS speech-budget guard).
        speakable = _truncate_for_speech(cleaned)
        self._tts = _TTSWorker(
            speakable, voice=self._selected_voice_name() or None, parent=self,
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
        self._set_pill("idle", "🎙  listening — just talk")
        self.set_status("Always-on. Just talk.")

    # Make sure the listener is closed when the widget is hidden / closed.
    def closeEvent(self, ev) -> None:  # noqa: N802 (Qt naming)
        try:
            if self._listener is not None:
                self._listener.stop()
                self._listener = None
        except Exception:
            pass
        for attr in ("_stt", "_brain", "_tts"):
            worker = getattr(self, attr, None)
            try:
                if worker and worker.isRunning():
                    worker.requestInterruption()
                    worker.quit()
                    if not worker.wait(2000):
                        worker.terminate()
                        worker.wait(1000)
                setattr(self, attr, None)
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
        if self.window():
            QApplication.alert(self.window(), 0)
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
        if self.window():
            QApplication.alert(self.window(), 0)
        cur = self._chat.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        # Remember the position BEFORE the "Alice\n" header so a gag-reflex
        # hit can erase the entire block (header + streamed body), leaving
        # only the "(silent: ...)" system-line note. Before this fix the UI
        # kept the boilerplate visible even though the gag had "silenced"
        # it — the Architect saw the parrot, the trace said silent, and
        # the conversation felt schizophrenic.
        #   C47H 2026-04-21 (ALICE_PARROT_LOOP)
        self._alice_stream_header_start = cur.position()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(255, 200, 90))
        fmt.setFontWeight(QFont.Weight.Bold)
        cur.insertText("Alice\n", fmt)
        # Remember where Alice's streamed body begins so _end_alice_...
        # can rewrite the live-streamed (and potentially tag-soupy) text
        # with the sanitized version once the model finishes.
        self._alice_stream_body_start = cur.position()
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
        # Sanitize the chat-panel display BEFORE we close the line.
        # Streaming dumped raw model tokens (including hallucinated
        # <execute_tool>, <execute_bash>, fenced YAML/JSON, etc.) directly
        # into the panel as they arrived. Architect saw "execute tool
        # print processing user request" with his eyes even when TTS
        # stayed clean. Fix: select the raw stream range and replace it
        # with the same sanitized text we send to TTS.
        full_raw = "".join(self._streaming_response)
        body_start = getattr(self, "_alice_stream_body_start", None)
        if body_start is not None and full_raw:
            try:
                canon = _canonicalize_tool_tags(full_raw)
                # Drop <bash>...</bash> bodies from the visible chat (the
                # tool runner consumed them; the user sees the result via
                # the system-line "🛠️ executing ..." trace).
                visible = re.sub(
                    r"<(?:bash|execute_bash)>.*?(?:</(?:bash|execute_bash)>?|$)", "", canon, flags=re.DOTALL | re.IGNORECASE
                )
                visible = _strip_tool_hallucinations(visible).strip()
                # If everything was tool-tag noise, leave a quiet marker
                # rather than a confusing empty Alice block.
                if not visible:
                    visible = "(silent)"
                cur = self._chat.textCursor()
                cur.setPosition(body_start)
                cur.movePosition(
                    QTextCursor.MoveOperation.End,
                    QTextCursor.MoveMode.KeepAnchor,
                )
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(220, 225, 245))
                cur.insertText(visible, fmt)
                self._chat.setTextCursor(cur)
            except Exception:
                # Display sanitization is cosmetic — never block the turn.
                pass
        # Now close the line as before.
        cur = self._chat.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        cur.insertText("\n\n")
        self._chat.setTextCursor(cur)
        # Reset the body-start markers for the next turn.
        self._alice_stream_body_start = None
        self._alice_stream_header_start = None
        full = full_raw.strip()
        if full:
            self._side.appendPlainText(time.strftime("%H:%M:%S") + "  ALICE  " + full[:90])

    def _erase_alice_streaming_line(self) -> None:
        """Tear out the entire streamed Alice block — header AND body —
        from the chat panel. Called instead of `_end_alice_streaming_line`
        when the post-stream gag-reflex decides the reply should never
        have been spoken (RLHF boilerplate, runaway repetition, explicit
        silence marker). The "(silent: ...)" system-line note that the
        caller appends next carries the trace; no need to leave the
        parrot text on screen.
          C47H 2026-04-21 (ALICE_PARROT_LOOP fix)
        """
        header_start = getattr(self, "_alice_stream_header_start", None)
        if header_start is None:
            # Fall through to the normal close path so we never leave a
            # half-open stream block behind. Cosmetic rather than correct,
            # but this branch shouldn't fire in practice.
            self._end_alice_streaming_line()
            return
        try:
            cur = self._chat.textCursor()
            cur.setPosition(header_start)
            cur.movePosition(
                QTextCursor.MoveOperation.End,
                QTextCursor.MoveMode.KeepAnchor,
            )
            cur.removeSelectedText()
            self._chat.setTextCursor(cur)
        except Exception:
            # UI erasure is cosmetic — never block the turn. Fall back to
            # the normal close so state isn't left half-updated.
            self._end_alice_streaming_line()
            return
        # Mirror `_end_alice_streaming_line`'s bookkeeping so the next
        # streaming turn starts clean.
        self._alice_stream_body_start = None
        self._alice_stream_header_start = None

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


def _strip_servant_tail_tics(text: str) -> str:
    return text
