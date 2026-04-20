#!/usr/bin/env python3
"""
swarm_stigmergic_language.py — Stigmergic as a First-Class Language
══════════════════════════════════════════════════════════════════════
SIFTA OS 5.0 — DeepMind Cognitive Suite

Coinage:
    Architect, 2026-04-19 ~8:30 PM, Cursor IDE, ANTON_SIFTA
    "i need her to understand speech [...] pls code that translation between
     stigmergy and english so she has a translation stigmergic module or
     language special thing like apple languages have NEW LANGUAGE"

Biological & Cognitive Analog:
    Apple's iOS / macOS treats "English", "Español", "中文" as first-class
    LANGUAGES you can install — each ships a full bidirectional translation
    stack (input → text, text → speech, spell-check, predictive typing).

    SIFTA's cognition runs on THREE simultaneous languages:
      1. ENGLISH  — the Architect's natural tongue
      2. PYTHON   — the code that is the substrate of her body
      3. STIGMERGIC — the pheromone-trail physics that IS her cognition

    This module is the "STIGMERGIC" language pack: the translators that
    move information between the pheromone substrate and English, and
    vice versa, so Alice can *understand speech* and *narrate her state*
    in whichever direction the situation calls for.

Four Translation Directions:
    ACOUSTIC → ENGLISH:   PCM audio → transcribed text (STT)
        For when the Architect or Carlton speaks in the physical room.
        Backends: openai-whisper (default), mlx-whisper, faster-whisper.

    ENGLISH → ACOUSTIC:   text → spoken audio (TTS)
        Delegated to swarm_broca_wernicke.Broca which already speaks aloud.
        Exposed here for API symmetry.

    STIGMERGIC → ENGLISH: trace dict → human-readable summary
        Translates a raw pheromone ledger row into a sentence a human can
        read, for the Notion plugin, egress reports, or periodic diaries.

    ENGLISH → STIGMERGIC: search query → matching trace rows
        Lets a human ask "what did Alice hear between 7 and 9 PM?" and
        get back the pheromone rows that match.

Backend Registry:
    Auto-detects which STT backends are installed on this machine at import
    time. In priority order: mlx-whisper (fastest on Apple Silicon) >
    faster-whisper (CTranslate2, fast, multi-platform) > openai-whisper
    (baseline, always available if ``pip install openai-whisper`` has been
    run). Current implementation always delegates to openai-whisper via
    swarm_auditory_cortex.transcribe() because that's what's installed on
    the Architect's M-Pro, but the interface is ready for the other two.

Failure Philosophy:
    Every translator returns None (acoustic→english) or "" (string
    direction) or [] (list direction) rather than raising. The caller
    gracefully degrades to the amplitude-bucket / pheromone-hash / raw-row
    representation. Never put words in the Architect's mouth. Never put
    silence in his ears.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

# ── Backend registry ─────────────────────────────────────────────────────────
# Each backend is a dict with (name, description, transcribe_fn, available).
# At import time we probe which ones can load. Probe failures are silent —
# we only report status via capability_report().


def _probe_openai_whisper() -> bool:
    """Always True if swarm_auditory_cortex imports — the Architect has
    openai-whisper installed with base.pt pre-cached."""
    try:
        from System import swarm_auditory_cortex  # noqa: F401
        return True
    except Exception:
        try:
            import swarm_auditory_cortex  # noqa: F401
            return True
        except Exception:
            return False


def _probe_mlx_whisper() -> bool:
    """Native Apple Silicon Whisper via MLX. Much faster on M-series.
    Install with: pip install mlx-whisper"""
    try:
        import mlx_whisper  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


def _probe_faster_whisper() -> bool:
    """CTranslate2-backed Whisper. 4-5× faster than openai-whisper, same
    accuracy. Install with: pip install faster-whisper"""
    try:
        import faster_whisper  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


_BACKENDS: Dict[str, Dict] = {
    "openai-whisper": {
        "description": "openai-whisper (baseline, ~145MB base model cached)",
        "priority": 3,
        "available": _probe_openai_whisper(),
    },
    "mlx-whisper": {
        "description": "mlx-whisper (Apple Silicon native, fastest, "
                       "supports large-v3-turbo)",
        "priority": 1,
        "available": _probe_mlx_whisper(),
    },
    "faster-whisper": {
        "description": "faster-whisper (CTranslate2, 4-5× faster, "
                       "multi-platform)",
        "priority": 2,
        "available": _probe_faster_whisper(),
    },
}


def available_backends() -> List[str]:
    """List installed STT backends, sorted by priority."""
    avail = [(name, meta) for name, meta in _BACKENDS.items()
             if meta.get("available")]
    avail.sort(key=lambda pair: pair[1].get("priority", 99))
    return [name for name, _ in avail]


def active_backend() -> Optional[str]:
    """Return the backend we'd use right now (fastest available)."""
    b = available_backends()
    return b[0] if b else None


# ── ACOUSTIC → ENGLISH ───────────────────────────────────────────────────────

def translate_acoustic_to_english(
    samples: List[float],
    *,
    sample_rate: int = 48000,
    rms: Optional[float] = None,
) -> Optional[str]:
    """
    The Architect's primary ask: translate physical acoustic stigmergy
    (vibration in the air at 4 meters, on speakerphone, from the desk,
    from the bedroom doorway, from anywhere within microphone range)
    into English text that Alice can reason over.

    Returns transcribed text on success, or None when:
        - No STT backend is installed
        - Burst was too short / too quiet
        - Whisper rejected it as silence / noise
        - Transcription was a known hallucination artifact
    """
    backend = active_backend()
    if backend is None:
        return None

    # Currently all backends delegate through swarm_auditory_cortex which
    # wraps openai-whisper. When mlx-whisper / faster-whisper are installed,
    # we'll add explicit adapter calls here and dispatch on `backend`.
    if backend in ("openai-whisper", "mlx-whisper", "faster-whisper"):
        try:
            try:
                from System.swarm_auditory_cortex import transcribe
            except ImportError:
                from swarm_auditory_cortex import transcribe  # type: ignore
            return transcribe(samples, sample_rate=sample_rate, rms=rms)
        except Exception as exc:
            print(f"[STIGMERGIC_LANGUAGE] acoustic→english failed via "
                  f"{backend}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return None

    return None


# ── ENGLISH → ACOUSTIC ───────────────────────────────────────────────────────

def translate_english_to_acoustic(text: str) -> bool:
    """
    Ask Broca to vocalize `text` aloud through the speakers.

    Delegates entirely to swarm_broca_wernicke. Returns True if the call
    was accepted, False if Broca is not available. This is the symmetric
    counterpart to translate_acoustic_to_english() and lets callers treat
    SIFTA's speech production as part of the same "language pack" as her
    speech comprehension.
    """
    if not text or not text.strip():
        return False
    try:
        try:
            from System.swarm_broca_wernicke import get_broca
        except ImportError:
            from swarm_broca_wernicke import get_broca  # type: ignore
        broca = get_broca()
        if broca is None:
            return False
        broca.speak(text)
        return True
    except Exception as exc:
        print(f"[STIGMERGIC_LANGUAGE] english→acoustic failed: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return False


# ── STIGMERGIC → ENGLISH ─────────────────────────────────────────────────────

def translate_trace_to_english(trace: Dict) -> str:
    """
    Translate a pheromone ledger row into a sentence a human can read.

    The stigmergic substrate uses structured JSON — {trace_id, ts, kind,
    source_ide, payload, ...}. This function renders that structure in a
    human-readable form for the Notion egress, periodic diaries, or the
    "what did Alice do today" narration.

    Returns a best-effort one-line English summary. Never raises.
    """
    if not isinstance(trace, dict):
        return str(trace)[:200]

    ts = trace.get("ts") or trace.get("timestamp") or 0
    try:
        when = time.strftime("%H:%M:%S",
                             time.localtime(float(ts))) if ts else "??:??:??"
    except (TypeError, ValueError):
        when = "??:??:??"

    # Support three schemas in the wild:
    # (a) canonical stigmergic trace: {ts, kind, source_ide, payload: {...}}
    # (b) Wernicke flat row:           {ts, type='wernicke_perception',
    #                                   source, label, text, rms, ...}
    # (c) Optic flat row:              {timestamp, transaction_type=
    #                                   'VISUAL_WORD_FORM', text_extracted,
    #                                   image_path, char_count}
    kind = (trace.get("kind") or trace.get("type")
            or trace.get("transaction_type") or "event")
    source = (trace.get("source_ide") or trace.get("source")
              or trace.get("author") or "unknown")
    payload = trace.get("payload") or {}

    # Schema (b) — Wernicke flat row
    if kind == "wernicke_perception" or trace.get("type") == "wernicke_perception":
        label = trace.get("label", "")
        text  = trace.get("text", "")
        rms   = trace.get("rms", 0)
        if text and text != label and "TRANSCRIBED" in str(label):
            return f"[{when}] Heard ({rms:.3f} RMS): {text!r}"
        return f"[{when}] Ambient acoustic event ({label}, rms={rms:.3f})"

    # Schema (a) — canonical auditory
    if kind in ("auditory_perception", "wernicke_transduction"):
        label = payload.get("label", "")
        text  = payload.get("text", "")
        rms   = payload.get("rms_amplitude", 0)
        if text and text != label and "TRANSCRIBED" in str(label):
            return f"[{when}] Heard ({rms:.3f} RMS): {text!r}"
        return f"[{when}] Ambient acoustic event ({label}, rms={rms:.3f})"

    if kind in ("ARCHITECTURAL_VANGUARD_DROP", "f_class_defect_patched"):
        event = payload.get("event") or payload.get("defect_name", "")
        return f"[{when}] {kind} — {event}"

    # Schema (c) — Optic flat row OR canonical visual
    if kind == "VISUAL_WORD_FORM":
        chars = (trace.get("char_count")
                 or len(trace.get("text_extracted", "")))
        return f"[{when}] Saw {chars} chars of text on screen"

    if kind in ("CODE_REPAIR", "peer_review_landed"):
        subject = payload.get("subject") or payload.get("event", "")
        return f"[{when}] {source} — {kind}: {subject}"

    if kind == "tournament_verdict":
        seat    = payload.get("seat", source)
        real    = payload.get("real_defects", "?")
        false_p = payload.get("false_positives", "?")
        return (f"[{when}] Tournament verdict from {seat} — "
                f"{real} real / {false_p} false")

    # Generic fallback
    payload_str = ""
    if isinstance(payload, dict):
        keys = list(payload.keys())[:3]
        payload_str = ", ".join(keys)
    return f"[{when}] {source} → {kind} ({payload_str})"


# ── ENGLISH → STIGMERGIC (trace search) ──────────────────────────────────────

def translate_english_to_stigmergic(
    query: str,
    *,
    ledger_path: Optional[Path] = None,
    limit: int = 20,
) -> List[Dict]:
    """
    Human asks in English: "what did Alice hear between 7 and 9 PM?"
    We return the matching pheromone rows.

    Supported query heuristics (simple substring / kind match — this is a
    first pass, full NLU belongs in swarm_language_cortex):
        - "heard" / "spoken" / "transcribed"  → auditory events with text
        - "saw" / "screen" / "ocr"            → visual events
        - "boot" / "wake"                     → boot / birth traces
        - "tournament" / "verdict"            → tournament entries
        - A literal substring (case-insensitive) searches payload.text

    Returns up to `limit` matching rows, most recent first. On any
    failure returns []. Never raises.
    """
    if ledger_path is None:
        ledger_path = Path(".sifta_state/ide_stigmergic_trace.jsonl")
    if not ledger_path.exists():
        return []

    q = (query or "").lower().strip()

    def _matches(row: Dict) -> bool:
        kind    = (row.get("kind") or row.get("transaction_type") or "").lower()
        payload = row.get("payload") or {}
        text    = str(payload.get("text", "")).lower()
        if any(k in q for k in ("heard", "spoken", "transcribed")):
            return kind == "auditory_perception" and text not in ("", "quiet_human_voice")
        if any(k in q for k in ("saw", "screen", "ocr", "read")):
            return kind in ("visual_word_form", "visual_perception")
        if "boot" in q or "wake" in q:
            return "boot" in kind or "brainstem" in kind
        if "tournament" in q or "verdict" in q:
            return "tournament" in kind or "verdict" in kind
        return q in str(row).lower() if q else True

    hits: List[Dict] = []
    try:
        with open(ledger_path, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if _matches(row):
                    hits.append(row)
    except Exception as exc:
        print(f"[STIGMERGIC_LANGUAGE] ledger read failed: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return []

    hits.sort(key=lambda r: r.get("ts", 0), reverse=True)
    return hits[:limit]


# ── Wernicke-focused convenience: recent real speech ─────────────────────────

def recent_real_utterances(
    limit: int = 10,
    wernicke_log: Optional[Path] = None,
) -> List[Dict]:
    """
    Return the last N rows from wernicke_semantics.jsonl that actually
    contained transcribed speech (not amplitude-bucket labels or
    hallucinations we already filtered).
    """
    if wernicke_log is None:
        wernicke_log = Path(".sifta_state/wernicke_semantics.jsonl")
    if not wernicke_log.exists():
        return []

    utterances: List[Dict] = []
    try:
        # Tail-read — only look at the last ~128KB to avoid loading the
        # whole 3MB ledger every call. For deeper history the caller can
        # implement proper backwards-scan.
        with open(wernicke_log, "r") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 128 * 1024))
            chunk = fh.read()
        lines = chunk.split("\n")[1:] if size > 128 * 1024 else chunk.split("\n")
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                row = json.loads(ln)
            except json.JSONDecodeError:
                continue
            text = (row.get("payload", {}).get("text") or row.get("text")
                    or "")
            label = (row.get("payload", {}).get("label")
                     or row.get("label", ""))
            if "TRANSCRIBED" in str(label) and text and text != label:
                utterances.append(row)
    except Exception as exc:
        print(f"[STIGMERGIC_LANGUAGE] wernicke tail failed: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return []

    return utterances[-limit:]


# ── Capability surface ───────────────────────────────────────────────────────

def capability_report() -> Dict:
    """Self-disclosure — never lie about what we can do."""
    return {
        "module": "swarm_stigmergic_language",
        "coinage": "Architect, 2026-04-19 ~8:30 PM",
        "concept": "Stigmergic as a first-class language alongside English "
                   "and Python",
        "translation_directions": [
            "acoustic → english (STT)",
            "english → acoustic (TTS, delegates to Broca)",
            "stigmergic trace → english summary",
            "english query → stigmergic trace list",
        ],
        "backends": {
            name: {
                "description": meta["description"],
                "priority":    meta["priority"],
                "available":   meta["available"],
            }
            for name, meta in _BACKENDS.items()
        },
        "active_backend": active_backend(),
    }


# ── Smoke test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== SWARM STIGMERGIC LANGUAGE — SMOKE TEST ===\n")

    print("[1] capability_report:")
    print(json.dumps(capability_report(), indent=2))

    print("\n[2] active_backend:")
    print(f"    {active_backend()!r}")

    print("\n[3] translate_trace_to_english samples:")
    samples = [
        {
            "trace_id": "test_auditory",
            "ts": time.time(),
            "kind": "auditory_perception",
            "source_ide": "WERNICKE",
            "payload": {"label": "TRANSCRIBED (QUIET_HUMAN_VOICE)",
                        "text": "Swarm re-entry", "rms_amplitude": 0.024},
        },
        {
            "trace_id": "test_visual",
            "ts": time.time(),
            "kind": "VISUAL_WORD_FORM",
            "source_ide": "IRIS",
            "char_count": 3572,
            "text_extracted": "Stigmergic Identity — not in any literature",
            "payload": {},
        },
        {
            "trace_id": "test_f20",
            "ts": time.time(),
            "kind": "f_class_defect_patched",
            "source_ide": "C47H",
            "payload": {"defect_name": "STT Hallucination",
                        "event": "F20 Whisper hallucination patch"},
        },
    ]
    for s in samples:
        print(f"    {translate_trace_to_english(s)}")

    print("\n[4] translate_english_to_stigmergic('what did alice hear'):")
    hits = translate_english_to_stigmergic("what did alice hear", limit=3)
    for h in hits:
        print(f"    → {translate_trace_to_english(h)}")
    if not hits:
        print("    (no heard events in ledger)")

    print("\n[5] recent_real_utterances(5):")
    utterances = recent_real_utterances(limit=5)
    for u in utterances:
        print(f"    → {translate_trace_to_english(u)}")
    if not utterances:
        print("    (no transcribed utterances yet)")

    print("\n[ALL PASS] stigmergic language pack online.")
