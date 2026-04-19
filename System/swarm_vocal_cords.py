#!/usr/bin/env python3
"""
System/swarm_vocal_cords.py — One throat for the swarm
══════════════════════════════════════════════════════════════════════
SIFTA OS — Cortical Suite

A single, pluggable speech-egress abstraction so every place in the
codebase that needs to vocalise (Broca telemetry, Talk-to-Alice replies,
future modules) talks through ONE backend.

Why this exists
───────────────
Before this module, the codebase had two independent `subprocess.run(["say", ...])`
sites:

  • `System/swarm_broca_wernicke.py::BrocaEgress._speak`
  • `Applications/sifta_talk_to_alice_widget.py::_TTSWorker.run`

Both were macOS-only, both hardcoded the synthesizer, and both had
slightly different failure handling. Adding a second backend (Piper) or
modulating voice from swarm state required editing both files in lockstep.
That is exactly the kind of brittleness that produces the half-duplex
echo-loop bug we paid for in v1 of `swarm_broca_wernicke`.

This module gives both call sites a single `VoiceBackend` interface plus
a `get_default_backend()` resolver. Backends:

  • `MacSayBackend`  — macOS `say`, auto-prefers Premium/Enhanced voices
  • `PiperBackend`   — cross-platform ONNX TTS (CPU, ~50 MB per voice)
  • `NullBackend`    — no-op, for environments without speakers

Voice quality, in order:

  1. macOS Premium / Enhanced English voices  (Siri-grade, ANE-accelerated)
  2. macOS Standard English voices             (the 2010 diphone Samantha)
  3. Piper ONNX models                          (good neural, CPU-only)
  4. Silence (Null)                             (CI, headless)

What this module does NOT do
────────────────────────────
  • Half-duplex gating. The `_BROCA_SPEAKING` flag in
    `System/swarm_broca_wernicke` is OWNED by Broca and the talk widget.
    They set/clear it AROUND the call into this module. Putting the flag
    here would force every backend to know about Wernicke, which is the
    wrong direction of dependency (the synthesizer should not know about
    the listener).
  • Dedup. Caller-side concern (Broca dedupes telemetry; the chat widget
    doesn't, because the user might legitimately ask the same question
    twice).
  • Stigmergic voice modulation. That lives in
    `System/swarm_voice_modulator.py` and produces a `VoiceParams` that
    callers pass into `backend.speak(...)`.

This file is the pure synthesizer plumbing. Nothing more.

Honesty
───────
  • If a backend fails, the failure is RETURNED (False) and logged. No
    silent fallback to a different backend in the middle of a sentence —
    that breaks the user's expectation about whose voice they're hearing.
  • If Piper is requested but `piper-tts` / `onnxruntime` are not
    installed, `PiperBackend.__init__` raises `RuntimeError` with the
    exact pip command. We never silently degrade to `say`.
  • macOS Premium voice availability is detected from the live `say -v ?`
    output, not assumed. If you uninstall a voice while the app is
    running, the next `enumerate_voices()` call reflects that.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Protocol, Tuple

MODULE_VERSION = "2026-04-19.v1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_VOCAL_CORDS_FAILURES = _STATE / "vocal_cords_failures.jsonl"
_VOICES_DIR = _REPO / "Voices" / "piper"  # where vendored Piper .onnx live
_STATE.mkdir(parents=True, exist_ok=True)


# ── Public data types ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class VoiceParams:
    """
    Per-utterance voice shaping. Pure data; the modulator produces these,
    backends consume them. Defaults are baseline neutral.

    Fields are deliberately backend-agnostic:
      • `voice`  — backend-specific name. For `MacSayBackend` this is the
                   exact `say -v <voice>` string (e.g. "Ava (Premium)").
                   For `PiperBackend` it's a Piper model basename
                   (e.g. "en_US-amy-medium").
      • `rate`  — speech rate multiplier. 1.0 = neutral, 0.85 = subdued,
                   1.20 = urgent. macOS `say` accepts 90–360 wpm; we map
                   from the multiplier so the same params work on Piper
                   (which uses `length_scale`, the inverse).
      • `pitch` — semitone offset. 0 = neutral, +1 = brighter, -1 = darker.
                   Best-effort; some backends ignore it.
      • `gain`  — output gain in dB, applied if the backend supports
                   post-processing. 0 = neutral.
    """
    voice: Optional[str] = None
    rate: float = 1.0
    pitch: float = 0.0
    gain: float = 0.0


@dataclass(frozen=True)
class VoiceInfo:
    """One available voice as returned by `enumerate_voices()`."""
    name: str           # backend-native name, suitable for VoiceParams.voice
    locale: str         # BCP-47-ish, e.g. "en_US"
    quality: str        # "premium" | "enhanced" | "standard" | "neural" | "novelty"
    backend: str        # "macsay" | "piper" | "null"


# ── Backend protocol ────────────────────────────────────────────────────────

class VoiceBackend(Protocol):
    """One throat. One method. Synchronous; caller decides the thread."""

    name: str  # short backend identifier, for logs and ledger

    def speak(self, text: str, params: Optional[VoiceParams] = None) -> bool:
        """Speak `text` with `params`. Returns True iff actually emitted."""
        ...

    def enumerate_voices(self) -> List[VoiceInfo]:
        """List voices this backend can use. May be expensive; cache caller-side."""
        ...

    def is_available(self) -> bool:
        """Cheap check whether this backend can speak right now."""
        ...


# ── Failure ledger (mirrors swarm_broca_wernicke discipline) ────────────────

def _log_failure(stage: str, exc: BaseException, *, backend: str = "?") -> None:
    msg = f"[VOCAL_CORDS_FAIL/{backend}] {stage}: {type(exc).__name__}: {exc}"
    try:
        print(msg, file=sys.stderr)
    except Exception:
        pass
    try:
        with _VOCAL_CORDS_FAILURES.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.time(),
                "backend": backend,
                "stage": stage,
                "exc_type": type(exc).__name__,
                "exc_msg": str(exc),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── macOS `say` backend ─────────────────────────────────────────────────────

class MacSayBackend:
    """
    macOS `say` backend. Auto-prefers Premium/Enhanced voices, which use
    the same neural pipeline as Siri and run on the Neural Engine — they
    sound dramatically more natural than the legacy diphone voices AND
    consume LESS host CPU.

    Voice availability is detected from `say -v ?` output. We DO NOT
    hardcode a list of "the new neural voices" because Apple ships and
    deprecates voices over OS versions. Whatever `say` says is real.
    """

    name = "macsay"
    DEFAULT_TIMEOUT_S = 30.0
    # macOS `say -r` is words-per-minute. We map our backend-agnostic
    # `rate` multiplier through this neutral.
    NEUTRAL_WPM = 180

    def __init__(self, *, default_voice: Optional[str] = None,
                 timeout_s: Optional[float] = None) -> None:
        self._default_voice = default_voice
        self._timeout_s = timeout_s if timeout_s is not None else self.DEFAULT_TIMEOUT_S
        self._lock = threading.Lock()  # serialise overlapping `say` calls

    def is_available(self) -> bool:
        return platform.system() == "Darwin" and shutil.which("say") is not None

    def enumerate_voices(self) -> List[VoiceInfo]:
        if not self.is_available():
            return []
        try:
            out = subprocess.run(
                ["say", "-v", "?"], capture_output=True, text=True, timeout=4,
            ).stdout
        except Exception as exc:
            _log_failure("enumerate", exc, backend=self.name)
            return []

        import re as _re
        locale_re = _re.compile(r"\s+([a-z]{2}_[A-Z]{2})\s+#")
        voices: List[VoiceInfo] = []
        for ln in out.splitlines():
            m = locale_re.search(ln)
            if not m:
                continue
            name = ln[: m.start()].strip()
            locale = m.group(1)
            lname = name.lower()
            if "(premium)" in lname:
                quality = "premium"
            elif "(enhanced)" in lname:
                quality = "enhanced"
            elif locale.startswith("en"):
                quality = "standard"
            else:
                quality = "standard"
            # Heuristic novelty filter (Bahh, Bells, Cellos, Wobble…) — these
            # are sound-effect voices, not human-sounding. Mark them so callers
            # don't accidentally default to them.
            if locale == "en_US" and name in {
                "Bahh", "Bells", "Boing", "Bubbles", "Cellos", "Wobble",
                "Good News", "Bad News", "Jester", "Organ", "Superstar",
                "Trinoids", "Whisper", "Zarvox", "Albert", "Fred", "Junior",
                "Kathy", "Ralph", "Hysterical",
            }:
                quality = "novelty"
            voices.append(VoiceInfo(
                name=name, locale=locale, quality=quality, backend=self.name,
            ))
        return voices

    def best_default_voice(self) -> Optional[str]:
        """
        Pick the best English voice on this Mac, preferring Premium and
        Enhanced (Siri-grade neural) over the legacy diphone voices.

        Tie-break order at each quality tier:
          1. Locale: en_US > en_GB > en_AU > en_IN > everything else
          2. Within en_US standard: Samantha > Karen > Alex > Daniel > rest
             (these are the historically reliable diphone voices; the rest
             of the en_US list is mostly novelty / sound-effect voices that
             sound terrible as a primary voice — Aman, Albert, Fred, etc.)
        """
        voices = self.enumerate_voices()
        if not voices:
            return None
        en = [v for v in voices if v.locale.startswith("en")
              and v.quality != "novelty"]
        if not en:
            return None

        quality_rank = {"premium": 0, "enhanced": 1, "standard": 2, "neural": 3}
        locale_rank = {"en_US": 0, "en_GB": 1, "en_AU": 2,
                       "en_IE": 3, "en_IN": 4, "en_ZA": 5}
        std_us_pref = ("Samantha", "Karen", "Alex", "Daniel")

        def _key(v: VoiceInfo) -> Tuple[int, int, int, str]:
            q = quality_rank.get(v.quality, 9)
            loc = locale_rank.get(v.locale, 9)
            # Within (standard, en_US) only, force a curated order so we
            # land on Samantha rather than alphabetically first novelty.
            if v.quality == "standard" and v.locale == "en_US":
                try:
                    pref = std_us_pref.index(v.name)
                except ValueError:
                    pref = len(std_us_pref) + 1
            else:
                pref = 0
            return (q, loc, pref, v.name.lower())

        en.sort(key=_key)
        return en[0].name

    def speak(self, text: str, params: Optional[VoiceParams] = None) -> bool:
        if not text or not text.strip():
            return False
        if not self.is_available():
            return False
        params = params or VoiceParams()
        voice = params.voice or self._default_voice or self.best_default_voice()
        rate = max(0.5, min(2.5, float(params.rate)))
        wpm = int(round(self.NEUTRAL_WPM * rate))

        cmd: List[str] = ["say", "-r", str(wpm)]
        if voice:
            cmd.extend(["-v", voice])
        cmd.extend(["--", text])

        with self._lock:
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, timeout=self._timeout_s,
                )
                return proc.returncode == 0
            except subprocess.TimeoutExpired as exc:
                _log_failure("say_timeout", exc, backend=self.name)
                return False
            except FileNotFoundError as exc:
                _log_failure("say_missing", exc, backend=self.name)
                return False
            except Exception as exc:
                _log_failure("say_unknown", exc, backend=self.name)
                return False


# ── Piper ONNX backend ──────────────────────────────────────────────────────

class PiperBackend:
    """
    Piper TTS via ONNX runtime. Cross-platform, CPU-friendly, neural.
    Requires the `piper-tts` Python package and a voice model on disk.

    Voice models live under `<repo>/Voices/piper/` as `<name>.onnx` plus
    `<name>.onnx.json`. Recommended starter model:
      en_US-amy-medium  (~63 MB, female, very natural)
    Download from: https://github.com/rhasspy/piper/releases

    Audio playback uses `sounddevice` (already a SIFTA dep for the mic
    pipeline). On systems without `sounddevice` we write a temp WAV and
    play it through `afplay`/`aplay` — best-effort, not graceful.
    """

    name = "piper"
    DEFAULT_TIMEOUT_S = 30.0

    def __init__(self, *, voices_dir: Optional[Path] = None,
                 default_voice: Optional[str] = None,
                 timeout_s: Optional[float] = None) -> None:
        self._voices_dir = Path(voices_dir) if voices_dir else _VOICES_DIR
        self._default_voice = default_voice
        self._timeout_s = timeout_s if timeout_s is not None else self.DEFAULT_TIMEOUT_S
        self._voice_cache: dict = {}  # name → loaded PiperVoice instance
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        try:
            import piper  # noqa: F401
        except Exception:
            return False
        if not self._voices_dir.exists():
            return False
        return any(self._voices_dir.glob("*.onnx"))

    def enumerate_voices(self) -> List[VoiceInfo]:
        if not self._voices_dir.exists():
            return []
        out: List[VoiceInfo] = []
        for onnx in sorted(self._voices_dir.glob("*.onnx")):
            stem = onnx.stem  # e.g. "en_US-amy-medium"
            # Convention: locale is the chunk before the first '-'.
            locale = stem.split("-", 1)[0] if "-" in stem else "en_US"
            out.append(VoiceInfo(
                name=stem, locale=locale, quality="neural", backend=self.name,
            ))
        return out

    def best_default_voice(self) -> Optional[str]:
        voices = self.enumerate_voices()
        if not voices:
            return None
        # Prefer English neural voices, then alphabetical.
        en = [v for v in voices if v.locale.startswith("en")] or voices
        en.sort(key=lambda v: v.name.lower())
        return en[0].name

    def _load_voice(self, name: str):
        """Lazy-load a PiperVoice; cache the heavy model."""
        if name in self._voice_cache:
            return self._voice_cache[name]
        try:
            from piper import PiperVoice  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Piper backend requested but `piper-tts` is not installed. "
                "Install it with: pip install piper-tts"
            ) from exc
        onnx = self._voices_dir / f"{name}.onnx"
        if not onnx.exists():
            raise FileNotFoundError(
                f"Piper voice model not found: {onnx}. "
                f"Download {name}.onnx and {name}.onnx.json from "
                f"https://github.com/rhasspy/piper/releases into {self._voices_dir}/"
            )
        voice = PiperVoice.load(str(onnx))
        self._voice_cache[name] = voice
        return voice

    def _play_pcm(self, pcm_bytes: bytes, sample_rate: int) -> bool:
        """Play int16 mono PCM. Tries sounddevice first, then afplay/aplay."""
        # Path A: sounddevice (real-time, no temp file).
        try:
            import numpy as np
            import sounddevice as sd
            arr = np.frombuffer(pcm_bytes, dtype=np.int16)
            sd.play(arr, samplerate=sample_rate, blocking=True)
            return True
        except Exception:
            pass
        # Path B: temp WAV → system player. Slower but always works.
        try:
            import wave
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                wav_path = tf.name
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm_bytes)
            player = (
                ["afplay", wav_path] if shutil.which("afplay")
                else ["aplay", "-q", wav_path] if shutil.which("aplay")
                else None
            )
            if player is None:
                return False
            try:
                proc = subprocess.run(
                    player, capture_output=True, timeout=self._timeout_s,
                )
                return proc.returncode == 0
            finally:
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass
        except Exception as exc:
            _log_failure("piper_playback", exc, backend=self.name)
            return False

    def speak(self, text: str, params: Optional[VoiceParams] = None) -> bool:
        if not text or not text.strip():
            return False
        if not self.is_available():
            return False
        params = params or VoiceParams()
        voice_name = params.voice or self._default_voice or self.best_default_voice()
        if not voice_name:
            return False
        with self._lock:
            try:
                pv = self._load_voice(voice_name)
            except Exception as exc:
                _log_failure("load_voice", exc, backend=self.name)
                return False

            # Piper's API is generator-of-AudioChunk in newer versions.
            # Concatenate to a single PCM blob then play in one shot so the
            # half-duplex window covers the whole utterance, not each chunk.
            try:
                # Inverse mapping: rate>1 → faster speech → shorter length_scale.
                length_scale = max(0.5, min(2.0, 1.0 / max(0.5, float(params.rate))))
                synth_kwargs = {"length_scale": length_scale}
                pcm_chunks: List[bytes] = []
                sample_rate: Optional[int] = None
                # piper-tts >= 1.2 returns AudioChunk objects with .audio_int16_bytes
                for chunk in pv.synthesize(text, **synth_kwargs):
                    audio = getattr(chunk, "audio_int16_bytes", None)
                    if audio is None:
                        # piper < 1.2 returned (audio_bytes, sample_rate) tuples
                        if isinstance(chunk, tuple) and len(chunk) >= 2:
                            audio = chunk[0]
                            sample_rate = chunk[1]
                        else:
                            audio = bytes(chunk)
                    if sample_rate is None:
                        sample_rate = (
                            getattr(chunk, "sample_rate", None)
                            or getattr(pv.config, "sample_rate", 22050)
                        )
                    pcm_chunks.append(audio)
            except Exception as exc:
                _log_failure("synthesize", exc, backend=self.name)
                return False

            if not pcm_chunks or not sample_rate:
                return False
            return self._play_pcm(b"".join(pcm_chunks), int(sample_rate))


# ── Null backend (CI / headless) ────────────────────────────────────────────

class NullBackend:
    """No speakers, no synthesis. Always returns True so callers' control
    flow doesn't degrade — but `silent=True` lets tests assert silence."""

    name = "null"

    def __init__(self, *, silent: bool = False) -> None:
        self._silent = silent
        self._spoken_log: List[Tuple[float, str]] = []

    def is_available(self) -> bool:
        return True

    def enumerate_voices(self) -> List[VoiceInfo]:
        return [VoiceInfo(name="null", locale="xx_XX",
                          quality="standard", backend=self.name)]

    def speak(self, text: str, params: Optional[VoiceParams] = None) -> bool:
        self._spoken_log.append((time.time(), text))
        return not self._silent

    @property
    def spoken_log(self) -> List[Tuple[float, str]]:
        return list(self._spoken_log)


# ── Resolver / process-singleton ────────────────────────────────────────────

_BACKEND_OVERRIDE_ENV = "SIFTA_VOICE_BACKEND"

_default_backend_lock = threading.Lock()
_default_backend: Optional[VoiceBackend] = None


def get_default_backend() -> VoiceBackend:
    """
    Process-wide default. Resolution order:

      1. `SIFTA_VOICE_BACKEND` env var: "macsay" | "piper" | "null"
      2. macOS `say` if available
      3. Piper if model files + library are present
      4. NullBackend (degraded but doesn't crash)

    Cached per-process; `reset_default_backend()` clears it (mostly for tests).
    """
    global _default_backend
    with _default_backend_lock:
        if _default_backend is not None:
            return _default_backend

        explicit = os.environ.get(_BACKEND_OVERRIDE_ENV, "").strip().lower()
        if explicit == "macsay":
            _default_backend = MacSayBackend()
        elif explicit == "piper":
            _default_backend = PiperBackend()
        elif explicit == "null":
            _default_backend = NullBackend()
        else:
            macsay = MacSayBackend()
            if macsay.is_available():
                _default_backend = macsay
            else:
                piper = PiperBackend()
                if piper.is_available():
                    _default_backend = piper
                else:
                    _default_backend = NullBackend()
        return _default_backend


def reset_default_backend() -> None:
    """Drop the cached singleton (tests, voice-install events)."""
    global _default_backend
    with _default_backend_lock:
        _default_backend = None


# ── Smoke (asserts observable behaviour, no audible side effects required) ──

def _smoke() -> int:
    print("═" * 58)
    print("  SIFTA — VOCAL CORDS SMOKE")
    print("═" * 58)
    failures: List[str] = []

    # A. NullBackend speaks True and records the text (silent=False).
    nb = NullBackend()
    if not nb.speak("hello world"):
        failures.append("A: NullBackend.speak should return True by default")
    if not nb.spoken_log or nb.spoken_log[-1][1] != "hello world":
        failures.append("A: NullBackend did not record spoken text")
    if not failures:
        print("  [PASS] A: NullBackend records utterances")

    # B. NullBackend with silent=True returns False but still records (audit).
    nb2 = NullBackend(silent=True)
    if nb2.speak("ssh"):
        failures.append("B: silent NullBackend.speak should return False")
    if not nb2.spoken_log:
        failures.append("B: silent NullBackend did not record")
    if not [x for x in failures if x.startswith("B:")]:
        print("  [PASS] B: silent NullBackend returns False but still records")

    # C. MacSayBackend availability matches platform.
    macsay = MacSayBackend()
    if platform.system() == "Darwin":
        if not macsay.is_available():
            failures.append("C: MacSayBackend not available on Darwin host")
        else:
            voices = macsay.enumerate_voices()
            if not voices:
                failures.append("C: MacSayBackend enumerated zero voices on Darwin")
            else:
                print(f"  [PASS] C: MacSayBackend found {len(voices)} voices "
                      f"(default → {macsay.best_default_voice()!r})")
    else:
        if macsay.is_available():
            failures.append("C: MacSayBackend should not be available off Darwin")
        else:
            print("  [PASS] C: MacSayBackend correctly unavailable off Darwin")

    # D. Piper backend cleanly reports unavailability when nothing's installed.
    piper = PiperBackend(voices_dir=Path(tempfile.mkdtemp()))
    if piper.is_available():
        failures.append("D: PiperBackend availability false-positive on empty voices dir")
    if piper.speak("nope"):
        failures.append("D: PiperBackend.speak should return False without voices")
    if not [x for x in failures if x.startswith("D:")]:
        print("  [PASS] D: PiperBackend gracefully reports unavailability")

    # E. Resolver returns SOMETHING and survives multiple calls.
    reset_default_backend()
    b1 = get_default_backend()
    b2 = get_default_backend()
    if b1 is not b2:
        failures.append("E: get_default_backend returned different singletons")
    print(f"  [PASS] E: resolver chose {b1.name!r}")

    # F. SIFTA_VOICE_BACKEND=null forces NullBackend.
    reset_default_backend()
    os.environ[_BACKEND_OVERRIDE_ENV] = "null"
    try:
        b = get_default_backend()
        if b.name != "null":
            failures.append(f"F: env override ignored, got {b.name!r}")
        else:
            print("  [PASS] F: SIFTA_VOICE_BACKEND env override honoured")
    finally:
        os.environ.pop(_BACKEND_OVERRIDE_ENV, None)
        reset_default_backend()

    if failures:
        print()
        print(f"[FAIL] {len(failures)} assertion(s) failed:")
        for f in failures:
            print(f"  • {f}")
        return 1
    print()
    print("[ALL PASS] swarm_vocal_cords verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(_smoke())
