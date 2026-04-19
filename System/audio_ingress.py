#!/usr/bin/env python3
"""
audio_ingress.py — Live Audio Capture & Acoustic Pheromone Bridge
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

The acoustic counterpart to optical_ingress.py. Captures a short audio
burst from the default input device (Dell Sound Bar AE515 microphone or
MacBook Pro built-in mic), hashes the raw PCM buffer as a reality anchor,
and feeds the float samples directly into SwarmAcousticField.ingest_audio()
so the acoustic pheromone field updates from real environmental sound.

Audio device inventory (verified 2026-04-19 via system_profiler):
  Default input  → Unknown Manufacturer USB (likely the Dell Sound Bar mic)
  Fallback input → Apple Inc. Built-in (MacBook Pro internal mic, 1ch 48kHz)
  Default output → Dell Professional Sound Bar AE515 (USB, 44100Hz, 2ch)

Architecture mirrors optical_ingress.py:
  - capture_acoustic_truth()  → raw burst → SHA256 hash (Reality Anchor)
  - live_acoustic_feed()      → generator that yields AcousticSample objects
  - AcousticSample            → dataclass with buffer, hash, device info

Dependency gating (same pattern as swarm_iris.py):
  sounddevice  → preferred (PortAudio backend, cross-platform)
  pyaudio      → fallback
  subprocess   → sox/ffmpeg last resort (no Python audio lib)
  If ALL fail → mock buffer with sinusoidal test tone (never crashes)

Pipeline:
  capture_acoustic_truth()
    → raw PCM float32 list
    → SHA256 hash ("Reality Anchor" — cryptographic proof of sound)
    → SwarmAcousticField.ingest_audio()
    → Acoustic pheromone deposited
    → crossmodal binding triggered (if crossmodal_binder wired)

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterator, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_AUDIO_LOG       = _STATE / "audio_ingress_log.jsonl"
_AUDIO_FAILURES  = _STATE / "audio_ingress_failures.jsonl"
_BUFFER_DIR      = _STATE / "acoustic_buffers"
_BUFFER_DIR.mkdir(parents=True, exist_ok=True)

MODULE_VERSION = "2026-04-19.v3"

# Names that look like inputs on macOS but are virtual / output / unwanted by
# default. Used by _resolve_audio_index() so we don't pick e.g. the BlackHole
# loopback or a "Text-To-Speech" pseudo-device when a real mic exists.
# Position-based matching, not strict equality — substring, case-insensitive.
_AVFOUNDATION_AUDIO_AVOID = (
    "blackhole",
    "loopback",
    "text-to-speech",
    "transcriptions",
    "aggregate",
    "multi-output",
    "screen capture",
)

# Preference order for picking the "best" real mic when multiple candidates
# pass the avoid filter. Earlier match wins. Fall through to first-available.
_AVFOUNDATION_AUDIO_PREFER = (
    "macbook pro microphone",      # built-in is most reliable on this machine
    "macbook air microphone",
    "built-in microphone",
    "iphone microphone",            # Continuity Camera mic
    "usb audio",                    # generic USB mic
)

# Backends that count as REAL audio capture (not synthetic).
# Used by the smoke test to label runs [LIVE] vs [DEGRADED] honestly,
# and by callers that need to know if reality_hash anchors actual photons of sound.
_REAL_SOURCES = frozenset({"sounddevice", "ffmpeg"})


# Identity-aware throttle. Identical (stage, exc_type, msg fingerprint)
# triples collapse to one stderr line AND one ledger row per
# _FAIL_THROTTLE_WINDOW_S; suppressed-count is folded into the next surfaced
# event so the audit trail stays honest without exploding the log.
#
# Why throttle the LEDGER too (not just stderr): when both real backends
# permanently fail (e.g. no mic plugged in / no TCC permission), the swarm
# heartbeat re-tries at ~5–20 Hz forever and the ledger grew to **74 MB of
# the same five error rows**. Genuinely novel failures still surface
# immediately because the (stage, type, fingerprint) key is different.
# (C47H audit 2026-04-18 follow-up.)
_FAIL_THROTTLE_WINDOW_S = 60.0
_FAIL_PRINT_LOCK = threading.Lock()
_LAST_LOGGED_AT: dict[tuple[str, str, str], float] = {}
_SUPPRESSED_COUNTS: dict[tuple[str, str, str], int] = {}


def _msg_fingerprint(msg: str) -> str:
    """Identity for the throttle: first 80 chars, addresses & numbers stripped.

    ffmpeg embeds a different `0x...` device pointer in every error message,
    so we collapse hex addresses; otherwise every retry would be a "novel"
    failure and the throttle would never engage. We do NOT collapse free-form
    diagnostic words — the substantive error text still differentiates one
    class of failure from another.
    """
    s = msg or ""
    # Collapse 0x... pointers (every ffmpeg attempt has a different one).
    import re as _re
    s = _re.sub(r"0x[0-9a-fA-F]+", "0x*", s)
    return s[:80]


def _log_capture_failure(stage: str, exc: BaseException) -> None:
    """
    Record why a real-audio backend fell through to the next.

    Both stderr printing AND the audio_ingress_failures.jsonl ledger row are
    throttled to one event per (stage, exc_type, msg-fingerprint) per
    _FAIL_THROTTLE_WINDOW_S seconds. The next surfaced row carries
    `suppressed_since_last` so no signal is silently dropped.

    Replaces the prior `except Exception: pass` anti-pattern (C47H audit
    2026-04-19): silent fall-through to mock made the entire pipeline appear
    to work while signing hashes of synthetic 440Hz tones.
    """
    now = time.time()
    key = (stage, type(exc).__name__, _msg_fingerprint(str(exc)))

    should_log = False
    suppressed_n = 0
    with _FAIL_PRINT_LOCK:
        last = _LAST_LOGGED_AT.get(key, 0.0)
        if now - last >= _FAIL_THROTTLE_WINDOW_S:
            should_log = True
            suppressed_n = _SUPPRESSED_COUNTS.pop(key, 0)
            _LAST_LOGGED_AT[key] = now
        else:
            _SUPPRESSED_COUNTS[key] = _SUPPRESSED_COUNTS.get(key, 0) + 1

    if not should_log:
        return

    suffix = (f" (+{suppressed_n} suppressed in last "
              f"{_FAIL_THROTTLE_WINDOW_S:.0f}s)" if suppressed_n else "")
    try:
        print(f"[AUDIO_FAIL] {stage}: {type(exc).__name__}: {exc}{suffix}",
              file=sys.stderr)
    except Exception:
        pass

    try:
        row = {
            "ts": now,
            "stage": stage,
            "exc_type": type(exc).__name__,
            "exc_msg": str(exc),
            "suppressed_since_last": suppressed_n,
        }
        with _AUDIO_FAILURES.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass

# ── Capture constants ─────────────────────────────────────────────────────────
SAMPLE_RATE   = 48000   # Hz — matches macOS default for built-in mic
BURST_SECONDS = 0.5     # short burst per capture (avoids blocking the swarm)
N_CHANNELS    = 1       # mono — acoustic field is 1D amplitude model
DTYPE         = "float32"

# ── AVFoundation audio device discovery ───────────────────────────────────────
# Cached because ffmpeg -list_devices spawns a subprocess and TCC may prompt.
# One probe per process lifetime, like swarm_iris._get_default_camera_index().
_AUDIO_INDEX_CACHE: Optional[Tuple[int, str]] = None  # (index, device_name)


def _list_avfoundation_audio_devices() -> List[Tuple[int, str]]:
    """
    Probe ffmpeg for the canonical AVFoundation audio device list.
    Returns [(index, name), ...] in the order ffmpeg reports them.
    Empty list on failure (no ffmpeg, no TCC permission, etc.) — never raises.

    Why ffmpeg and not sounddevice/PortAudio: the AVFoundation audio device
    indices we pass to `ffmpeg -i ":N"` are AVFoundation's, not PortAudio's.
    sounddevice's device list uses a separate enumeration. Mixing them gives
    "Unknown USB Audio Device" when you wanted MacBook Pro Microphone.
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", "avfoundation",
             "-list_devices", "true", "-i", ""],
            capture_output=True, timeout=4,
        )
    except Exception as exc:
        _log_capture_failure("avfoundation_list", exc)
        return []

    # ffmpeg writes the device list to stderr with "AVFoundation audio devices:"
    # followed by lines like "[AVFoundation indev @ 0xXXX] [N] Device Name"
    text = (result.stderr or b"").decode("utf-8", "replace")
    devices: List[Tuple[int, str]] = []
    in_audio_section = False

    for line in text.splitlines():
        if "AVFoundation audio devices:" in line:
            in_audio_section = True
            continue
        if "AVFoundation video devices:" in line:
            in_audio_section = False
            continue
        if not in_audio_section:
            continue
        # Match: "[AVFoundation indev @ 0xHHH] [N] Device Name"
        # Extract the bracketed index after the @ portion.
        idx_start = line.rfind("] [")
        if idx_start == -1:
            continue
        # The "[N] Name" portion starts right after the second "] ["
        try:
            tail = line[idx_start + 2:]            # "[N] Name"
            close = tail.index("]")
            idx = int(tail[1:close])
            name = tail[close + 1:].strip()
            if name:
                devices.append((idx, name))
        except (ValueError, IndexError):
            continue

    return devices


def _resolve_audio_index() -> Tuple[int, str]:
    """
    Pick the best real AVFoundation audio input index.
    Returns (index, device_name). Falls back to (0, "avfoundation_default")
    only if discovery is impossible — and that fallback is what hits the
    "Unknown USB Audio Device" trap, so callers should treat a fallback
    return as 'mic discovery failed, expect [DEGRADED]'.

    Discovery is cached per process lifetime to avoid repeated TCC prompts.
    Call invalidate_audio_cache() to force a re-probe (hot-swap, perm grant).
    """
    global _AUDIO_INDEX_CACHE
    if _AUDIO_INDEX_CACHE is not None:
        return _AUDIO_INDEX_CACHE

    devices = _list_avfoundation_audio_devices()
    if not devices:
        # Fallback path. Log as a real failure so it's auditable.
        _log_capture_failure(
            "avfoundation_list",
            RuntimeError("device list empty — likely missing TCC mic permission "
                         "or ffmpeg unavailable; falling back to index 0"),
        )
        _AUDIO_INDEX_CACHE = (0, "avfoundation_default_unverified")
        return _AUDIO_INDEX_CACHE

    # Filter out virtual / loopback / TTS-style pseudo-devices.
    real = [
        (idx, name) for (idx, name) in devices
        if not any(av in name.lower() for av in _AVFOUNDATION_AUDIO_AVOID)
    ]
    if not real:
        # Every device matched an avoid pattern — pick the first listed anyway,
        # but log it so the next audit knows we're in a strange state.
        _log_capture_failure(
            "avfoundation_list",
            RuntimeError(f"all {len(devices)} audio devices matched avoid list; "
                         f"picking first: {devices[0]}"),
        )
        _AUDIO_INDEX_CACHE = devices[0]
        return _AUDIO_INDEX_CACHE

    # Walk the preference order; return the first preferred match.
    for pref in _AVFOUNDATION_AUDIO_PREFER:
        for idx, name in real:
            if pref in name.lower():
                _AUDIO_INDEX_CACHE = (idx, name)
                return _AUDIO_INDEX_CACHE

    # No preference matched — return the first survivor of the avoid filter.
    _AUDIO_INDEX_CACHE = real[0]
    return _AUDIO_INDEX_CACHE


def invalidate_audio_cache() -> None:
    """
    Force re-probe of AVFoundation audio devices on next capture.
    Use after granting microphone permission, plugging/unplugging USB audio,
    or otherwise mutating the system audio device list.
    """
    global _AUDIO_INDEX_CACHE
    _AUDIO_INDEX_CACHE = None

# ── Dependency gating ─────────────────────────────────────────────────────────
try:
    import sounddevice as _sd   # type: ignore
    HAS_SOUNDDEVICE = True
except ImportError:
    _sd = None
    HAS_SOUNDDEVICE = False

try:
    import numpy as _np         # type: ignore
    HAS_NUMPY = True
except ImportError:
    _np = None
    HAS_NUMPY = False

# ── Mic Consent Gate ──────────────────────────────────────────────────────────
# Analogous to the SCAR dual-sig gate in mutation_governor. The OS refuses to
# open physical biological microphones without a cryptographic ApprovalTrace
# from a registered reviewer.
#
# The mic captures voice biometric data — a higher safety bar than camera
# frames. We fail closed: _MIC_ENABLED defaults to False and the only path to
# True is through enable_microphone(approval, proposer_trace) with a verified
# ApprovalTrace whose reviewer is in the ReviewerRegistry. The same primitive
# the swarm already uses for code mutations.

_MIC_ENABLED: bool = False
_MIC_TEST_OVERRIDE: bool = False  # set True by smoke test only — never in prod


class MicrophoneConsentNeeded(RuntimeError):
    """Raised when capture is attempted before enable_microphone() succeeds."""


def enable_microphone(
    approval: Any,
    proposer_trace: Any,
    *,
    reviewer_registry: Any = None,
    reviewer_allowlist: Any = None,
) -> None:
    """
    Formally unlocks the microphone hardware.

    Both positional arguments are required:
      proposer_trace : PheromoneTrace whose payload starts with 'MIC_ENABLE'
                       and is signed by the proposer.
      approval       : ApprovalTrace from a *different* registered reviewer,
                       counter-signing proposer_trace.signature_hex.

    The check goes through verify_approval() — the exact same primitive that
    gates SCAR mutations. No bespoke crypto. If verify_approval() rejects, the
    mic stays closed and a MicrophoneConsentNeeded is raised so the caller
    cannot silently fall through.

    Sybil resistance: pass either reviewer_registry= (TUF-style, preferred) or
    reviewer_allowlist= (flat set of authorized pubkey hex). If neither is
    provided, falls back to System.reviewer_registry.ReviewerRegistry's default
    on-disk registry — matching the SCAR gate's default trust source.
    """
    global _MIC_ENABLED

    if approval is None or proposer_trace is None:
        raise MicrophoneConsentNeeded(
            "enable_microphone requires both a PheromoneTrace and an ApprovalTrace"
        )

    try:
        try:
            from System.swimmer_pheromone_identity import verify_approval
        except ImportError:
            from swimmer_pheromone_identity import verify_approval  # type: ignore
    except ImportError as exc:
        raise MicrophoneConsentNeeded(
            f"crypto modules unavailable, cannot enforce mic consent gate: {exc}"
        ) from exc

    # Default to the on-disk reviewer registry if caller didn't override.
    if reviewer_registry is None and reviewer_allowlist is None:
        try:
            try:
                from System.reviewer_registry import ReviewerRegistry
            except ImportError:
                from reviewer_registry import ReviewerRegistry  # type: ignore
            reviewer_registry = ReviewerRegistry()
        except ImportError as exc:
            raise MicrophoneConsentNeeded(
                f"no reviewer registry available, cannot enforce mic consent: {exc}"
            ) from exc

    ok = verify_approval(
        proposer_trace,
        approval,
        reviewer_registry=reviewer_registry,
        reviewer_allowlist=reviewer_allowlist,
    )
    if not ok:
        raise MicrophoneConsentNeeded(
            "ApprovalTrace failed verify_approval() — reviewer not in registry, "
            "self-approval, expired TTL, malleated signature, or mismatched "
            "proposal hash. Mic stays closed."
        )

    _MIC_ENABLED = True


def disable_microphone() -> None:
    """Revoke mic consent. Always succeeds. Useful at shutdown / context exit."""
    global _MIC_ENABLED
    _MIC_ENABLED = False


def mic_status() -> dict:
    """Read-only view of the consent gate state. Safe to log."""
    return {
        "enabled": _MIC_ENABLED,
        "test_override": _MIC_TEST_OVERRIDE,
    }

# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class AcousticSample:
    """
    One captured audio burst — the acoustic analog of IrisFrame.
    buffer: raw PCM samples as float32 in [-1.0, 1.0]
    reality_hash: SHA256 of the raw bytes, pinned to this burst
    """
    sample_id:     str
    source:        str            # "sounddevice" | "ffmpeg" | "mock"
    device_name:   str
    ts_captured:   float
    sample_rate:   int
    n_channels:    int
    n_samples:     int
    duration_s:    float
    reality_hash:  str            # SHA256 of raw PCM bytes
    buffer:        List[float]    # float32 samples (mono)
    rms_amplitude: float          # convenience metric for acoustic field
    metadata:      dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("buffer", None)   # never log raw PCM to disk
        return d


# ── Live capture ──────────────────────────────────────────────────────────────

def _rms(samples: List[float]) -> float:
    """Root mean square amplitude — measure of acoustic energy."""
    if not samples:
        return 0.0
    if HAS_NUMPY:
        arr = _np.array(samples, dtype=_np.float32)
        return float(_np.sqrt(_np.mean(arr ** 2)))
    return math.sqrt(sum(x * x for x in samples) / len(samples))


def _samples_to_hash(samples: List[float]) -> str:
    """SHA256 of raw float32 PCM bytes. Reality Anchor."""
    raw = struct.pack(f"{len(samples)}f", *samples)
    return hashlib.sha256(raw).hexdigest()


def _resolve_sounddevice_index() -> int:
    """Find the first real input device index. Fallback if default fails."""
    try:
        # First try the global default
        default_in = _sd.default.device[0]
        if default_in is not None and default_in >= 0:
            return default_in
    except Exception:
        pass
    # Scan all devices for the first input
    try:
        devices = _sd.query_devices()
        for i, d in enumerate(devices):
            if d.get("max_input_channels", 0) >= 1:
                return i
    except Exception:
        pass
    return -1


def _capture_sounddevice(burst_s: float = BURST_SECONDS) -> Tuple[List[float], str]:
    """Capture using sounddevice (PortAudio). Returns (samples, device_name)."""
    idx = _resolve_sounddevice_index()
    if idx < 0:
        raise RuntimeError("No PortAudio input device found.")
        
    n_frames = int(SAMPLE_RATE * burst_s)
    recording = _sd.rec(
        n_frames,
        samplerate=SAMPLE_RATE,
        channels=N_CHANNELS,
        dtype=DTYPE,
        blocking=True,
        device=idx,
    )
    device_info = _sd.query_devices(idx)
    device_name = device_info.get("name", "unknown") if isinstance(device_info, dict) else f"sd_input_{idx}"
    samples = recording.flatten().tolist() if HAS_NUMPY else [float(x) for x in recording]
    return samples, device_name


def _capture_ffmpeg(burst_s: float = BURST_SECONDS) -> Tuple[List[float], str]:
    """
    Capture using ffmpeg avfoundation audio — pure subprocess, no Python audio lib.
    Outputs raw 32-bit float PCM to stdout, parses it back to floats.

    Uses _resolve_audio_index() which parses ffmpeg's own canonical device list
    once per process. This avoids the brute-force-probe approach (which triggers
    the macOS TCC mic prompt up to N times per call and reports the wrong device
    when index 0 happens to be a non-functional USB shim — exactly today's bug).

    Raises on failure rather than returning ([], "ffmpeg_failed") — the outer
    caller logs via _log_capture_failure(). Audit-trail discipline matches the
    optical pipeline (C47H 2026-04-19).
    """
    idx, device_name = _resolve_audio_index()
    idx_str = f":{idx}"

    cmd = [
        "ffmpeg", "-y",
        "-f", "avfoundation",
        "-i", idx_str,
        "-t", str(burst_s),
        "-ar", str(SAMPLE_RATE),
        "-ac", str(N_CHANNELS),
        "-f", "f32le",
        "pipe:1",
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=burst_s + 3)
    if result.returncode != 0:
        stderr_tail = (result.stderr or b"")[-300:].decode("utf-8", "replace").strip()
        raise RuntimeError(
            f"ffmpeg rc={result.returncode} on device {idx_str} "
            f"({device_name}): {stderr_tail}"
        )
    raw = result.stdout
    if len(raw) < 4:
        raise RuntimeError(
            f"ffmpeg returned no PCM data from device {idx_str} ({device_name}) — "
            "input may be muted, unavailable, or TCC permission denied"
        )
    n = len(raw) // 4
    samples = list(struct.unpack(f"{n}f", raw[:n * 4]))
    return samples, f"avfoundation:{idx} ({device_name})"


def _mock_burst(burst_s: float = BURST_SECONDS) -> Tuple[List[float], str]:
    """
    Deterministic sinusoidal test tone (440 Hz A) when no hardware is available.
    Amplitude 0.1 — below conversation level, clearly synthetic.
    The acoustic field still gets a real waveform; the hash still anchors.
    """
    n = int(SAMPLE_RATE * burst_s)
    freq = 440.0
    samples = [0.1 * math.sin(2 * math.pi * freq * i / SAMPLE_RATE) for i in range(n)]
    return samples, "mock_440hz_tone"


def capture_acoustic_truth(
    burst_s: float = BURST_SECONDS,
    *,
    feed_to_acoustic_field: bool = True,
) -> Optional[AcousticSample]:
    """
    Capture one acoustic burst from the default input device.
    Returns an AcousticSample with reality_hash pinned to the raw PCM.

    Pipeline:
      1. Try sounddevice (preferred — PortAudio, lowest latency)
      2. Try ffmpeg avfoundation (no Python audio dep required)
      3. Fall back to synthetic 440 Hz tone (never crashes)

    If feed_to_acoustic_field=True (default), feeds samples into
    SwarmAcousticField.ingest_audio() — acoustic pheromone updates from
    real sound. Set False if you only want the hash.
    """
    now = time.time()
    sample_id = f"audio_{int(now * 1000)}"

    # ── Capture ───────────────────────────────────────────────────────────────
    samples: List[float] = []
    source = "mock"
    device_name = "mock"

    if _MIC_ENABLED:
        if HAS_SOUNDDEVICE:
            try:
                samples, device_name = _capture_sounddevice(burst_s)
                source = "sounddevice"
            except Exception as exc:
                _log_capture_failure("sounddevice", exc)

        if not samples:
            try:
                samples, device_name = _capture_ffmpeg(burst_s)
                source = "ffmpeg"
            except Exception as exc:
                _log_capture_failure("ffmpeg", exc)
    else:
        # Hardware access explicitly denied by OS governance.
        # NOTE: previously a duplicated ffmpeg attempt below this branch leaked
        # past the consent gate — removed in C47H v3 audit. The gate now
        # actually gates.
        _log_capture_failure(
            "consent_gate",
            MicrophoneConsentNeeded(
                "ApprovalTrace required to enable mic. Falling back to synthetic audio."
            ),
        )

    if not samples:
        samples, device_name = _mock_burst(burst_s)
        source = "mock"
        # Loud, structured warning — silent mock-fallback is exactly the bug
        # class we just fixed for cameras (OBS Virtual default). Refuse to be
        # quiet about it. Throttled to one line per _FAIL_PRINT_WINDOW_S so
        # a long-running boot doesn't spam stderr; full record stays in the
        # ledger via _log_capture_failure.
        _log_capture_failure(
            "audio_degraded_mock",
            RuntimeError(
                "all real backends failed — emitting synthetic 440Hz tone; "
                "reality_hash anchors a SINE WAVE, not the room"
            ),
        )

    # ── Hash ──────────────────────────────────────────────────────────────────
    reality_hash = _samples_to_hash(samples)
    rms = _rms(samples)

    result = AcousticSample(
        sample_id=sample_id,
        source=source,
        device_name=device_name,
        ts_captured=now,
        sample_rate=SAMPLE_RATE,
        n_channels=N_CHANNELS,
        n_samples=len(samples),
        duration_s=len(samples) / SAMPLE_RATE,
        reality_hash=reality_hash,
        buffer=samples,
        rms_amplitude=round(rms, 6),
        metadata={"module_version": MODULE_VERSION},
    )

    # ── Feed acoustic field ───────────────────────────────────────────────────
    if feed_to_acoustic_field and samples:
        try:
            try:
                from System.swarm_acoustic_field import SwarmAcousticField
            except ImportError:
                from swarm_acoustic_field import SwarmAcousticField  # type: ignore
                
            try:
                from System.swarm_crossmodal_binding import get_crossmodal_binder
                binder = get_crossmodal_binder()
            except ImportError:
                try:
                    from swarm_crossmodal_binding import get_crossmodal_binder  # type: ignore
                    binder = get_crossmodal_binder()
                except ImportError:
                    binder = None
                    
            field_obj = SwarmAcousticField(crossmodal_binder=binder)
            field_obj.ingest_audio(source_id=device_name, audio_buffer=samples)
        except Exception as exc:
            # Acoustic field wiring is optional, but a *runtime* failure inside
            # ingest_audio() (vs. ImportError) is an event we must not lose.
            _log_capture_failure("acoustic_field_ingest", exc)

    # ── Wernicke transduction (Human → Swarm semantic perception) ────────────
    # Only fire on REAL audio sources. Synthetic 440Hz tone is not a human
    # voice and Wernicke must not be lied to. The half-duplex Broca gate is
    # enforced inside Wernicke.transduce() — no mic-feeds-speaker echo loop.
    if samples and source in _REAL_SOURCES:
        try:
            try:
                from System.swarm_broca_wernicke import get_wernicke
            except ImportError:
                from swarm_broca_wernicke import get_wernicke  # type: ignore
            get_wernicke().transduce(
                audio_buffer=samples,
                rms=rms,
                source=device_name,
                reality_hash=reality_hash,
            )
        except Exception as exc:
            _log_capture_failure("wernicke_transduce", exc)

    # ── Log (no PCM bytes) ────────────────────────────────────────────────────
    _log_sample(result)

    print(f"[🎙️ AUDIO] {source} | device={device_name[:30]} | "
          f"rms={rms:.4f} | hash={reality_hash[:16]}… | "
          f"n={len(samples)} samples")

    return result


def _log_sample(sample: AcousticSample) -> None:
    """Append redacted record (no raw buffer) to audio log. Never raises."""
    try:
        row = sample.to_dict()
        with _AUDIO_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def live_acoustic_feed(
    n_bursts: int = 0,
    burst_s: float = BURST_SECONDS,
    interval_s: float = 1.0,
) -> Iterator[AcousticSample]:
    """
    Generator: yield AcousticSample objects continuously.
    n_bursts=0 → infinite loop (until caller stops iterating).
    interval_s → sleep between bursts (avoids hammering the mic).

    Usage:
        for sample in live_acoustic_feed(n_bursts=10):
            print(sample.rms_amplitude, sample.reality_hash[:8])
    """
    count = 0
    while n_bursts == 0 or count < n_bursts:
        sample = capture_acoustic_truth(burst_s=burst_s)
        if sample is not None:
            yield sample
        count += 1
        if interval_s > 0 and (n_bursts == 0 or count < n_bursts):
            time.sleep(interval_s)


def capability_report() -> dict:
    """AV inputs available on this system."""
    return {
        "sounddevice": HAS_SOUNDDEVICE,
        "numpy": HAS_NUMPY,
        "ffmpeg": bool(subprocess.run(
            ["which", "ffmpeg"], capture_output=True
        ).returncode == 0),
        "sample_rate": SAMPLE_RATE,
        "burst_seconds": BURST_SECONDS,
        "module_version": MODULE_VERSION,
    }


# ── Smoke test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("[AUDIO INGRESS SMOKE]")
    print("Capabilities:", json.dumps(capability_report(), indent=2))

    # Mic consent gate: build a genuine signed proposal + approval pair using
    # two distinct SwimmerIdentity keys and an in-memory allowlist. This
    # exercises the *actual* enable_microphone() path rather than bypassing it
    # — if the gate is broken, the smoke fails here. No on-disk registry mutation.
    try:
        try:
            from System.swimmer_pheromone_identity import SwimmerIdentity
        except ImportError:
            from swimmer_pheromone_identity import SwimmerIdentity  # type: ignore

        proposer = SwimmerIdentity("audio_ingress_smoke_proposer")
        reviewer = SwimmerIdentity("audio_ingress_smoke_reviewer")

        proposal = proposer.deposit("MIC_ENABLE", "smoke_test_burst_capture")
        approval = reviewer.approve(proposal, decision="APPROVED")

        smoke_allowlist = {
            proposer.public_key.hex(),
            reviewer.public_key.hex(),
        }

        enable_microphone(
            approval,
            proposer_trace=proposal,
            reviewer_allowlist=smoke_allowlist,
        )
        print(f"[CONSENT] mic enabled via verified ApprovalTrace from "
              f"{reviewer.id[:12]}… over proposal from {proposer.id[:12]}…")
    except Exception as exc:
        # The smoke is allowed to proceed without mic consent — it'll just land
        # [DEGRADED]. But surface the failure loudly so it's not invisible.
        print(f"[CONSENT_FAIL] could not establish mic consent: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)

    print(f"[CONSENT_STATE] {mic_status()}")

    print("\nCapturing 1 burst…")
    sample = capture_acoustic_truth(feed_to_acoustic_field=True)
    if sample is None:
        print("\n[FAIL] capture_acoustic_truth() returned None — pipeline broken.")
        raise SystemExit(2)

    is_live = sample.source in _REAL_SOURCES
    label = "[LIVE]" if is_live else "[DEGRADED]"
    verdict = (
        "real audio captured from physical input device"
        if is_live
        else "FELL THROUGH to synthetic 440Hz tone — reality_hash anchors a sine wave, "
             "not the room. See .sifta_state/audio_ingress_failures.jsonl for cause."
    )

    print(f"\n{label} {verdict}")
    print(f"  source      : {sample.source}")
    print(f"  device      : {sample.device_name}")
    print(f"  n_samples   : {sample.n_samples}")
    print(f"  duration    : {sample.duration_s:.3f}s")
    print(f"  rms         : {sample.rms_amplitude:.6f}")
    print(f"  reality_hash: {sample.reality_hash}")
    print(f"  hash[:16]   : {sample.reality_hash[:16]}…")

    print("\n[AUDIO INGRESS SMOKE DONE]")
    # Non-zero exit on degraded so CI / agents can treat 'mock fallback' as a real failure.
    raise SystemExit(0 if is_live else 1)
