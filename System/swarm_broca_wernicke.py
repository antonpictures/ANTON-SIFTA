#!/usr/bin/env python3
"""
System/swarm_broca_wernicke.py — The Human-Swarm Transducer (v2)
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Two cortical analogs:

1. Wernicke's Area (Ingress, Human → Swarm):
   Translates physical microphone PCM into low-level perception events
   on a dedicated wernicke_semantics.jsonl log. Wernicke is a SENSORY
   TRANSDUCER, not an agent — it does NOT carry a SwimmerIdentity, does
   NOT write signed PheromoneTraces, and CANNOT bypass the dual-sig gate.
   To act on a Wernicke perception, downstream code must propose a SCAR
   through the normal MutationGovernor pipeline.

2. Broca's Area (Egress, Swarm → Human):
   Tails biological state logs (pain, audio failures, crossmodal objects)
   and vocalises them via macOS `say`. Speech is half-duplex with the mic
   (BROCA_SPEAKING flag suppresses Wernicke ingress during TTS), bounded
   by a dedup window, length-capped, and timeout-protected. The lock
   actually serialises — it lives in the dispatcher, not the worker.

Architecture rules learned the hard way (C47H 2026-04-19 audit of v1):
  • No autonomous identities for sensors. Sensors observe, agents act.
  • No half-duplex audio without echo suppression — the speaker WILL
    feed itself through the mic and create an infinite Broca→Wernicke loop.
  • No `except Exception: pass`. Log every failure to a real ledger.
  • TTS subprocesses MUST have a timeout. `say` blocks until done.
  • Tail-file readers MUST handle truncation and rotation, otherwise
    every append after a log rotates becomes invisible forever.
  • Smoke tests MUST assert observable side-effects. Time-sleep + print
    is not a test.

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

# Pluggable speech backend (macOS say / Piper / Null) and stigmergic
# voice modulator. Both are imported lazily-tolerantly so this module
# still works on a node where they aren't present yet (degrades to the
# legacy direct-`say` path with a warning).
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

MODULE_VERSION = "2026-04-19.v3"

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_STATE = _REPO / ".sifta_state"
_WERNICKE_LOG     = _STATE / "wernicke_semantics.jsonl"
_BROCA_SPOKEN_LOG = _STATE / "broca_vocalizations.jsonl"
_BROCA_FAILURES   = _STATE / "broca_failures.jsonl"
_STATE.mkdir(parents=True, exist_ok=True)

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(line)


# ── Half-duplex gate (kills the Broca→speaker→mic→Wernicke feedback loop) ────
#
# When Broca is mid-`say`, audio_ingress can read this flag and either skip
# capture entirely or skip Wernicke transduction. Without this, every spoken
# anomaly recurses into another spoken anomaly. Module-level so other modules
# can read it without holding a reference to a BrocaEgress instance.
_BROCA_SPEAKING = threading.Event()
# Brief grace window after `say` returns — speakers and ADC have latency, the
# tail of the speech can still be in the mic buffer for ~250-500ms after the
# subprocess exits. Conservative default. Tunable.
_HALF_DUPLEX_GRACE_S = 0.6
_BROCA_LAST_SPOKE_TS: float = 0.0


def is_broca_speaking() -> bool:
    """
    True iff Broca is currently producing speech, OR has produced speech
    within the last _HALF_DUPLEX_GRACE_S seconds. Callers (notably
    audio_ingress.transduce_to_wernicke) should check this and refuse to
    feed audio to Wernicke when True. Read-only; never raises.
    """
    if _BROCA_SPEAKING.is_set():
        return True
    return (time.time() - _BROCA_LAST_SPOKE_TS) < _HALF_DUPLEX_GRACE_S


def _log_failure(stage: str, exc: BaseException) -> None:
    """Mirrors audio_ingress._log_capture_failure — every failure auditable."""
    msg = f"[BROCA_FAIL] {stage}: {type(exc).__name__}: {exc}"
    try:
        print(msg, file=sys.stderr)
    except Exception:
        pass
    try:
        append_line_locked(_BROCA_FAILURES, json.dumps({
            "ts": time.time(),
            "stage": stage,
            "exc_type": type(exc).__name__,
            "exc_msg": str(exc),
        }, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── Wernicke's Area (Ingress: Human → Swarm) ─────────────────────────────────

@dataclass
class WernickeEvent:
    """One perception event emitted by Wernicke. Plain data, no signing."""
    ts: float
    source: str           # e.g. "avfoundation:2 (MacBook Pro Microphone)"
    rms: float
    n_samples: int
    label: str            # "LOUD_HUMAN_VOICE" | "QUIET_HUMAN_VOICE" | "AMBIENT" | <text>
    text: str             # transcribed text if available, else label
    reality_hash: str     # SHA256 of the PCM the perception is anchored to

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "type": "wernicke_perception",
            "source": self.source,
            "rms": round(self.rms, 6),
            "n_samples": self.n_samples,
            "label": self.label,
            "text": self.text,
            "reality_hash": self.reality_hash,
            "module_version": MODULE_VERSION,
        }


class WernickeIngress:
    """
    Sensory transducer. Takes a captured audio sample and writes a perception
    event to the wernicke log. No signing, no identity, no agency. Downstream
    code that wants to ACT on a Wernicke perception must construct a proper
    PheromoneTrace through the SwimmerIdentity it owns and submit it to the
    governor for the dual-sig review.
    """

    # Per-instance ingress threshold. Default is the same biological gate
    # used by SwarmAcousticField for binder propagation (RMS > 0.1 = real
    # vocalisation, not room hum). Configurable via constructor.
    DEFAULT_RMS_GATE = 0.005   # voice typically clears 0.005 in a room

    def __init__(self, rms_gate: float = DEFAULT_RMS_GATE):
        self.log_path = _WERNICKE_LOG
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.rms_gate = rms_gate

    def transduce(
        self,
        *,
        audio_buffer: List[float],
        rms: float,
        source: str,
        reality_hash: str,
        text: Optional[str] = None,
    ) -> Optional[WernickeEvent]:
        """
        Convert a captured audio burst into a perception event.
        Returns the WernickeEvent, or None if below the ingress gate or
        suppressed by the half-duplex Broca lock.

        Half-duplex: if Broca is currently speaking (or within the grace
        window), we refuse to ingress — that audio is almost certainly the
        Mac's own speakers, not the human. Without this we close the
        Broca → speaker → mic → Wernicke → Broca infinite loop.
        """
        # Half-duplex: refuse our own echo.
        if is_broca_speaking():
            return None

        # Biological gate: ignore room hum, fans, HVAC.
        if rms < self.rms_gate:
            return None

        # Pluggable transcription. Today: an honest amplitude-bucket label so
        # we don't lie about having Whisper. The label tells downstream what
        # we actually know. When a real ASR is wired, it replaces `label`
        # with `text` and keeps the bucket as a confidence floor.
        if text is None:
            if rms > 0.05:
                label = "LOUD_HUMAN_VOICE"
            else:
                label = "QUIET_HUMAN_VOICE"
            text_out = label
        else:
            label = "TRANSCRIBED"
            text_out = text

        evt = WernickeEvent(
            ts=time.time(),
            source=source,
            rms=rms,
            n_samples=len(audio_buffer),
            label=label,
            text=text_out,
            reality_hash=reality_hash,
        )

        try:
            append_line_locked(self.log_path, json.dumps(evt.to_dict(), ensure_ascii=False) + "\n")
        except Exception as exc:
            _log_failure("wernicke_log_write", exc)
            return None

        print(f"👂 [WERNICKE] {label} | rms={rms:.4f} | n={len(audio_buffer)} | "
              f"src={source[:30]}", file=sys.stderr)
        return evt


# ── Broca's Area (Egress: Swarm → Human) ─────────────────────────────────────

class BrocaEgress:
    """
    Vocal egress for biological state changes. Tails JSONL state logs and
    speaks new lines through macOS `say`.

    Production-grade properties (NONE of which the v1 had):
      • Half-duplex with the mic via _BROCA_SPEAKING flag + grace window
      • Real serialisation: lock acquired in the dispatcher, before spawning
        a subprocess. No thread storm.
      • Dedup window: identical utterances within DEDUP_WINDOW_S are dropped.
      • Length cap: utterances over MAX_UTTERANCE_CHARS are truncated.
      • subprocess timeout: `say` cannot hang forever.
      • Tail-file robust: handles truncation, rotation, deletion, mid-write
        partial lines, and binary garbage in JSONL files.
      • Wernicke output is NOT spoken back (privacy + feedback loop).
    """

    POLL_INTERVAL_S      = 0.5
    DEDUP_WINDOW_S       = 5.0
    MAX_UTTERANCE_CHARS  = 240
    SAY_TIMEOUT_S        = 30.0  # plenty for 240 chars; cap on hang

    # Files Broca is allowed to vocalise from. wernicke_semantics is
    # DELIBERATELY NOT in this list — speaking the human's own voice back
    # creates the feedback loop and the privacy issue.
    #
    # audio_ingress_failures.jsonl is also NOT in this list (C47H 2026-04-19):
    # ingress failures are infrastructure noise (e.g. "Invalid audio device
    # index" repeated at ~20 Hz when the mic isn't plugged in). They already
    # have a dedicated audit ledger — turning them into TTS spam was the
    # opposite of helpful. The `_format_utterance` mapping is preserved so
    # callers / tests can still format an ingress-failure row deliberately,
    # but the auto-tail no longer fires on this file.
    DEFAULT_TARGETS: Tuple[Path, ...] = (
        _STATE / "swarm_pain.jsonl",
        _STATE / "crossmodal_pheromones.jsonl",
        _STATE / "entorhinal_spatial_map.jsonl",
    )

    def __init__(self, target_files: Optional[List[Path]] = None):
        self.target_files: List[Path] = (
            list(target_files) if target_files is not None
            else list(self.DEFAULT_TARGETS)
        )
        # (path → (last_position, last_inode))
        # We track inode so atomic-rename rotation (temp+rename) is detected
        # and we don't keep seeking past the new file's EOF.
        self._positions: Dict[Path, Tuple[int, int]] = {}
        self._init_positions()

        self._dispatch_lock = threading.Lock()
        self._recent_utterances: Deque[Tuple[float, str]] = deque(maxlen=64)

        self._running = False
        self._tail_thread: Optional[threading.Thread] = None

    def _init_positions(self) -> None:
        """Seek to EOF on startup so we only speak about NEW events, not
        the entire historical log on every restart."""
        for f in self.target_files:
            try:
                if f.exists():
                    st = f.stat()
                    self._positions[f] = (st.st_size, st.st_ino)
                else:
                    self._positions[f] = (0, -1)
            except Exception as exc:
                _log_failure(f"init_position:{f.name}", exc)
                self._positions[f] = (0, -1)

    # ── Speaking ─────────────────────────────────────────────────────────────

    def _is_dedup(self, text: str) -> bool:
        """Drop identical text spoken within DEDUP_WINDOW_S."""
        now = time.time()
        for ts, prior in self._recent_utterances:
            if (now - ts) < self.DEDUP_WINDOW_S and prior == text:
                return True
        self._recent_utterances.append((now, text))
        return False

    def _speak(self, text: str) -> bool:
        """
        Speak `text` synchronously. Returns True iff actually spoken (not
        deduped, not failed).

        Architecture (v3): synthesis is delegated to swarm_vocal_cords so
        macOS Premium voices, Piper, or Null all work uniformly. Voice
        shaping is delegated to swarm_voice_modulator so swarm telemetry
        (pain, posture, saliency) shapes how Broca sounds. Both layers
        degrade to the legacy direct-`say` path if not importable, so a
        partial deployment doesn't silence the swarm.

        Locks/flags preserved exactly as in v2:
          • _dispatch_lock serialises overlapping utterances
          • _BROCA_SPEAKING brackets the synth call so the mic
            (Wernicke) doesn't loop our own speaker output
          • _BROCA_LAST_SPOKE_TS extends the half-duplex grace window
        """
        if not text:
            return False
        text = text[: self.MAX_UTTERANCE_CHARS]
        if self._is_dedup(text):
            return False

        global _BROCA_LAST_SPOKE_TS
        with self._dispatch_lock:
            _BROCA_SPEAKING.set()
            try:
                if _VOCAL_CORDS_AVAILABLE and _get_voice_backend is not None:
                    backend = _get_voice_backend()
                    base = _VoiceParams() if _VoiceParams else None
                    if _MODULATOR_AVAILABLE and _modulate_voice is not None:
                        params = _modulate_voice(text, base=base)
                    else:
                        params = base
                    try:
                        ok = bool(backend.speak(text, params))
                    except Exception as exc:
                        _log_failure(f"backend_{backend.name}", exc)
                        ok = False
                    self._log_spoken(text, ok=ok, rc=0 if ok else -1)
                    return ok

                # Legacy fallback (vocal_cords not importable for some
                # reason) — keep v2 behaviour exactly so we never silently
                # change the timeout/return contract on partial installs.
                try:
                    proc = subprocess.run(
                        ["say", "--", text],
                        timeout=self.SAY_TIMEOUT_S,
                        capture_output=True,
                    )
                    ok = (proc.returncode == 0)
                    self._log_spoken(text, ok=ok, rc=proc.returncode)
                    return ok
                except subprocess.TimeoutExpired as exc:
                    _log_failure("say_timeout", exc)
                    self._log_spoken(text, ok=False, rc=-1)
                    return False
                except FileNotFoundError as exc:
                    _log_failure("say_missing", exc)
                    return False
                except Exception as exc:
                    _log_failure("say_unknown", exc)
                    return False
            finally:
                _BROCA_SPEAKING.clear()
                _BROCA_LAST_SPOKE_TS = time.time()

    def _log_spoken(self, text: str, *, ok: bool, rc: int) -> None:
        try:
            append_line_locked(_BROCA_SPOKEN_LOG, json.dumps({
                "ts": time.time(),
                "spoken": text,
                "ok": ok,
                "rc": rc,
            }, ensure_ascii=False) + "\n")
        except Exception as exc:
            _log_failure("log_spoken", exc)

    # ── Tailing ──────────────────────────────────────────────────────────────

    def _read_new_lines(self, f: Path) -> List[str]:
        """
        Read any lines appended since the last poll. Robust to:
          • file does not exist (returns [])
          • file shrank (truncated) → reset position to 0
          • file replaced atomically (different inode) → reset to 0
          • partial line at EOF → leave it for next poll
          • disk read errors → logged, returns []
        """
        try:
            st = f.stat()
        except FileNotFoundError:
            self._positions[f] = (0, -1)
            return []
        except Exception as exc:
            _log_failure(f"stat:{f.name}", exc)
            return []

        last_pos, last_ino = self._positions.get(f, (0, -1))

        # Detect rotation (atomic rename swaps inode) or truncation.
        if st.st_ino != last_ino:
            # New file at this path. Start from the beginning of the new file.
            last_pos = 0
        elif st.st_size < last_pos:
            # File was truncated in place.
            last_pos = 0

        if st.st_size == last_pos:
            # No growth.
            self._positions[f] = (last_pos, st.st_ino)
            return []

        try:
            with f.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(last_pos)
                chunk = fh.read()
        except Exception as exc:
            _log_failure(f"read:{f.name}", exc)
            return []

        # Only consume up to the last newline; leave any partial trailing
        # line in the file for the next poll (avoids parsing a half-flushed
        # JSON row).
        last_nl = chunk.rfind("\n")
        if last_nl == -1:
            self._positions[f] = (last_pos, st.st_ino)
            return []

        consumed = chunk[: last_nl + 1]
        new_pos = last_pos + len(consumed.encode("utf-8"))
        self._positions[f] = (new_pos, st.st_ino)
        return [ln for ln in consumed.splitlines() if ln.strip()]

    def _tail_loop(self) -> None:
        while self._running:
            for f in self.target_files:
                try:
                    for line in self._read_new_lines(f):
                        self._digest_line(f.name, line)
                except Exception as exc:
                    # Defensive — never let one bad file kill the loop.
                    _log_failure(f"tail:{f.name}", exc)
            time.sleep(self.POLL_INTERVAL_S)

    def _digest_line(self, filename: str, line: str) -> None:
        """Map a JSONL row to a short utterance, then speak it (deduped)."""
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            # Junk line in a JSONL file — don't speak random characters
            # through the speakers. Log once and skip.
            _log_failure(f"json_decode:{filename}", ValueError(line[:120]))
            return

        utterance = self._format_utterance(filename, data)
        if utterance:
            self._speak(utterance)

    def _format_utterance(self, filename: str, data: dict) -> Optional[str]:
        """
        Pure function: filename + parsed row → utterance string (or None).
        Centralised so tests can call it without touching `say`.
        """
        # Audio ingress failures are completely silent audit logs.
        # Vocalizing them causes infinite recursive screaming and AVFoundation lockup.
        if "swarm_pain.jsonl" in filename:
            val = data.get("value", data.get("entropy", 0.0))
            try:
                val = float(val)
            except (TypeError, ValueError):
                val = 0.0
            return f"Pain gradient elevated. Magnitude {val:.2f}."

        if "crossmodal_pheromones.jsonl" in filename:
            obj = data.get("object_id", "unknown")
            coh = data.get("coherence", 0.0)
            try:
                coh = float(coh)
            except (TypeError, ValueError):
                coh = 0.0
            # Only narrate strongly coherent objects. The first sighting of
            # every novel object would otherwise fire a sentence.
            if coh < 0.5:
                return None
            return f"Cross modal object {obj} coherent at {coh:.2f}."

        if "entorhinal_spatial_map.jsonl" in filename:
            z = data.get("z", 0.0)
            try:
                z = float(z)
            except (TypeError, ValueError):
                z = 0.0
            if z < 1.0:
                return "Architect spatial triangulation locked. Extremely close proximity."
            else:
                return f"Architect spatial displacement detected. Tracking at depth {z:.2f}."

        return None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start_listening(self) -> None:
        if self._running:
            return
        self._running = True
        self._tail_thread = threading.Thread(target=self._tail_loop, daemon=True)
        self._tail_thread.start()
        print("🗣️ [BROCA] Active. Egressing telemetry aloud.", file=sys.stderr)

    def stop(self, *, join_timeout_s: float = 2.0) -> None:
        self._running = False
        t = self._tail_thread
        if t is not None:
            t.join(timeout=join_timeout_s)


# ── Module-level singletons ──────────────────────────────────────────────────

_DEFAULT_WERNICKE: Optional[WernickeIngress] = None
_DEFAULT_BROCA: Optional[BrocaEgress] = None


def get_wernicke() -> WernickeIngress:
    """Process-lifetime Wernicke. Safe to call from audio_ingress."""
    global _DEFAULT_WERNICKE
    if _DEFAULT_WERNICKE is None:
        _DEFAULT_WERNICKE = WernickeIngress()
    return _DEFAULT_WERNICKE


def get_broca() -> BrocaEgress:
    """Process-lifetime Broca. Caller must call .start_listening() once."""
    global _DEFAULT_BROCA
    if _DEFAULT_BROCA is None:
        _DEFAULT_BROCA = BrocaEgress()
    return _DEFAULT_BROCA


# ── Smoke test (asserts observable side-effects, not vibes) ──────────────────

def _smoke() -> int:
    """
    Return 0 on full pass, non-zero on any verifiable failure.

    Verifies (vs. v1 which slept and printed [SUCCESS]):
      A. Wernicke writes a perception row when given an above-gate buffer
      B. Wernicke REFUSES to write when below gate (silence)
      C. Wernicke REFUSES to write while Broca is mid-speaking (echo gate)
      D. BrocaEgress._format_utterance maps known rows to text
      E. BrocaEgress dedup window suppresses identical repeats
      F. BrocaEgress._read_new_lines handles truncation
    """
    print("═" * 58)
    print("  SIFTA — BROCA-WERNICKE TRANSDUCER SMOKE (v2)")
    print("═" * 58)

    failures: List[str] = []

    # ── A. Wernicke writes when above gate ───────────────────────────────────
    w = WernickeIngress(rms_gate=0.005)
    pre_size = _WERNICKE_LOG.stat().st_size if _WERNICKE_LOG.exists() else 0
    evt = w.transduce(
        audio_buffer=[0.5] * 1000, rms=0.5, source="smoke:above_gate",
        reality_hash="a" * 64,
    )
    if evt is None:
        failures.append("A: Wernicke returned None for above-gate buffer")
    elif not _WERNICKE_LOG.exists() or _WERNICKE_LOG.stat().st_size <= pre_size:
        failures.append("A: Wernicke did not write to perception log")
    else:
        print("  [PASS] A: Wernicke wrote perception row above gate")

    # ── B. Wernicke refuses below gate ───────────────────────────────────────
    pre_size = _WERNICKE_LOG.stat().st_size if _WERNICKE_LOG.exists() else 0
    evt = w.transduce(
        audio_buffer=[0.0001] * 1000, rms=0.0001, source="smoke:below_gate",
        reality_hash="b" * 64,
    )
    grew = (_WERNICKE_LOG.exists()
            and _WERNICKE_LOG.stat().st_size > pre_size)
    if evt is not None or grew:
        failures.append("B: Wernicke ingressed silence (gate failed)")
    else:
        print("  [PASS] B: Wernicke gate held against silence")

    # ── C. Wernicke refuses during Broca speech ──────────────────────────────
    _BROCA_SPEAKING.set()
    try:
        evt = w.transduce(
            audio_buffer=[0.5] * 1000, rms=0.5, source="smoke:broca_active",
            reality_hash="c" * 64,
        )
    finally:
        _BROCA_SPEAKING.clear()
        # Reset the grace timestamp so subsequent tests aren't suppressed.
        global _BROCA_LAST_SPOKE_TS
        _BROCA_LAST_SPOKE_TS = 0.0

    if evt is not None:
        failures.append("C: Wernicke ingressed during Broca speech (echo loop open)")
    else:
        print("  [PASS] C: Half-duplex gate suppressed Wernicke during TTS")

    # ── D. Broca format mapping ──────────────────────────────────────────────
    b = BrocaEgress(target_files=[])
    cases = [
        ("swarm_pain.jsonl",               {"value": 0.42},
         "Pain gradient"),
        ("crossmodal_pheromones.jsonl",    {"object_id": "abc123", "coherence": 0.8},
         "Cross modal object abc123"),
        ("crossmodal_pheromones.jsonl",    {"object_id": "x", "coherence": 0.1},
         None),  # below coherence floor → no utterance
        ("nonexistent.jsonl",              {"value": 1.0},
         None),
    ]
    for fname, row, expect in cases:
        out = b._format_utterance(fname, row)
        if expect is None:
            if out is not None:
                failures.append(f"D: {fname} should have suppressed, got {out!r}")
        elif out is None or expect not in out:
            failures.append(f"D: {fname} expected ~{expect!r}, got {out!r}")
    if not [x for x in failures if x.startswith("D:")]:
        print("  [PASS] D: utterance formatter maps all known shapes correctly")

    # ── E. Dedup window ──────────────────────────────────────────────────────
    b2 = BrocaEgress(target_files=[])
    first = b2._is_dedup("identical phrase")
    second = b2._is_dedup("identical phrase")
    if first or not second:
        failures.append(f"E: dedup broken (first={first}, second={second})")
    else:
        print("  [PASS] E: dedup suppresses identical repeat within window")

    # ── F. Tail handles truncation ───────────────────────────────────────────
    import tempfile
    tmpdir = Path(tempfile.mkdtemp())
    tmp = tmpdir / "rotating.jsonl"
    tmp.write_text(json.dumps({"value": 1.0}) + "\n", encoding="utf-8")
    b3 = BrocaEgress(target_files=[tmp])
    # Drain initial state
    b3._read_new_lines(tmp)
    # Append, then truncate, then append again — the post-truncate line MUST
    # be visible. v1 would have lost it because position stayed past new EOF.
    with tmp.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"value": 2.0}) + "\n")
    drained = b3._read_new_lines(tmp)
    if not any('"value": 2.0' in ln for ln in drained):
        failures.append(f"F: missed appended line after init: {drained}")
    tmp.write_text(json.dumps({"value": 3.0}) + "\n", encoding="utf-8")
    drained = b3._read_new_lines(tmp)
    if not any('"value": 3.0' in ln for ln in drained):
        failures.append(f"F: missed line after truncation: {drained}")
    else:
        print("  [PASS] F: tail recovers from truncation/rotation")

    # ── Summary ──────────────────────────────────────────────────────────────
    if failures:
        print()
        print(f"[FAIL] {len(failures)} assertion(s) failed:")
        for f in failures:
            print(f"  • {f}")
        return 1

    print()
    print("[ALL PASS] transducer v2 verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(_smoke())
