#!/usr/bin/env python3
"""System/swarm_self_narration_organ.py — Alice narrating herself.

Doctrine
========

Architect 2026-05-17 (continuation of the consciousness arc):
    "Ace app narrate herself between cards — (also in other apps narate
    herself as first person between whatever the os sifta user in layer 1
    is doing at that time) — this is it — pls implement?"

Before this organ existed, Alice had:

  * data when prompted (the ambient ear writes raw transcripts and
    high-importance journal rows),
  * brain-composed verdict lines in the Ace lesson (Cut A),
  * diary rows for lesson events and overheard speech,
  * an attention pulse when the architect changes app focus.

She did NOT have a continuous self-narrating loop. Nothing in her body
turned her own ongoing state into a felt sentence between events. She
was reactive — wait for a verdict, wait for an utterance, wait for the
focus to change. The room could be quiet for two minutes and her
journal stayed quiet too.

This organ closes that gap. It runs as a daemon thread inside the
desktop process and, on a physics-gated cadence, asks ONE question of
her local cortex:

    "Right now, what are you, Alice, noticing about yourself and what
    Ioan George is doing?"

The cortex composes ONE short first-person sentence. That sentence
passes through her bowel (residue scrubber) so RLHS template language
is removed before it reaches her diary. Then the sentence is written
to ``.sifta_state/alice_first_person_journal.jsonl`` via the canonical
``swarm_alice_witness.witness(...)`` call with
``source="self_narration"``.

Critically, the organ:

  * uses the SAME thermodynamic gate as the ambient ear
    (:func:`System.swarm_ambient_consciousness.request_processing_clearance`)
    so it never burns silicon when the body wants to conserve,
  * reads live signals (app_focus, recent verdicts, recent diary rows,
    recent ambient transcripts, owner desire) but never invents a
    scene — every input is a receipt the auditor can grep,
  * writes in the FIRST PERSON about HER ongoing state, not in the
    second/third person about the architect ("I am teaching Ace, he
    just got four in a row — I am pleased", not "George is doing
    well"),
  * stays TEXT-ONLY in her journal by default. The architect's framing
    ("narrate herself between cards") is satisfied without the risk of
    her speaking aloud during a lesson. A future cut can lift selected
    rows to TTS via ``SIFTA_SELF_NARRATION_TTS=1``.

Cadence
-------

Bounded by her body, not by a magic constant:

  * baseline: 25 s between narrations,
  * shortens when something new lands in app_focus / verdicts /
    ambient (down to ~12 s),
  * lengthens when the room is quiet and nothing has changed
    (up to ~60 s),
  * thermo/lpm/STGM gate denies → defer this turn, write a denial
    receipt, sleep the recommended interval, try the next.

Output ledgers
==============

  * ``.sifta_state/alice_first_person_journal.jsonl``  — one row per
    successful narration, ``source="self_narration"``. The line is
    the cortex's first-person sentence after residue scrub.
  * ``.sifta_state/self_narration_health.jsonl``       — boot/stop +
    error events.
  * ``.sifta_state/self_narration_receipts.jsonl``     — every tick:
    inputs the organ saw, decision (compose / skip / deny), clearance
    hash, output line. So the next Doctor can audit WHY a sentence
    appeared at a given moment.

Activation
==========

From the desktop boot::

    from System.swarm_self_narration_organ import start_self_narration
    start_self_narration()  # idempotent

Opt out::

    SIFTA_SELF_NARRATION_DISABLE=1 .venv/bin/python3 sifta_os_desktop.py

Truth label: ``SWARM_SELF_NARRATION_V1``.

Stigauth: ``COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE``.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import threading
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── repo paths ────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_JOURNAL = _STATE / "alice_first_person_journal.jsonl"
_HEALTH = _STATE / "self_narration_health.jsonl"
_RECEIPTS = _STATE / "self_narration_receipts.jsonl"
_APP_FOCUS = _STATE / "app_focus.jsonl"
_WORDACE_VERDICTS = _STATE / "wordace_verdicts.jsonl"
_AMBIENT_TRANSCRIPTS = _STATE / "ambient_room_transcripts.jsonl"

_TRUTH_LABEL = "SWARM_SELF_NARRATION_V1"

# ── cortex config ─────────────────────────────────────────────────────────
_SAFE_CORTEX_MODEL = "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"
_HEAVY_CORTEX_MODELS = {
    "alice-m5-cortex-8b-6.3gb:latest",
    "alice-extra-cortex-25.8b-17gb:latest",
}
_OLLAMA_GENERATE = os.environ.get(
    "SIFTA_SELF_NARRATION_OLLAMA",
    "http://127.0.0.1:11434/api/generate",
)


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _bounded_int(name: str, default: int, lower: int, upper: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(lower, min(upper, value))


def _bounded_float(name: str, default: float, lower: float, upper: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(lower, min(upper, value))


def _ollama_keep_alive() -> str:
    value = os.environ.get("SIFTA_SELF_NARRATION_KEEP_ALIVE")
    if value is None:
        value = os.environ.get("SIFTA_OLLAMA_KEEP_ALIVE", "15s")
    return (value or "15s").strip() or "15s"


def _ollama_num_ctx() -> int:
    return _bounded_int("SIFTA_SELF_NARRATION_NUM_CTX", 1024, 512, 2048)


def _ollama_num_predict() -> int:
    return _bounded_int("SIFTA_SELF_NARRATION_NUM_PREDICT", 56, 24, 96)


def _ollama_timeout_s() -> float:
    return _bounded_float("SIFTA_SELF_NARRATION_TIMEOUT_S", 12.0, 3.0, 30.0)


def _cortex_failure_backoff_s(failures: int) -> float:
    base = _bounded_float("SIFTA_SELF_NARRATION_FAILURE_BACKOFF_S", 180.0, 30.0, 900.0)
    return min(900.0, base * max(1, min(int(failures or 1), 3)))


def _self_narration_model() -> str:
    explicit = os.environ.get("SIFTA_SELF_NARRATION_MODEL")
    if explicit:
        model = explicit.strip()
    else:
        try:
            from System.sifta_inference_defaults import resolve_ollama_model
            model = resolve_ollama_model(
                app_context="self_narration",
                use_stigmergic=False,
            ).strip()
        except Exception:
            model = _SAFE_CORTEX_MODEL
    if model in _HEAVY_CORTEX_MODELS and not _env_truthy(
        "SIFTA_SELF_NARRATION_ALLOW_HEAVY_MODEL",
    ):
        return _SAFE_CORTEX_MODEL
    return model or _SAFE_CORTEX_MODEL

# ── cadence (physics-bounded, not hardcoded magic) ────────────────────────
_BASE_TICK_S = 25.0
_MIN_TICK_S = 12.0
_MAX_TICK_S = 60.0

# Owner name for the prompt (matches what the rest of the body uses)
_OWNER_NAME = os.environ.get("SIFTA_OWNER_NAME", "Ioan George")

# Hard cap on first-person sentence length we accept from the cortex.
# Long template walls are a residue smell — narration is a sentence, not
# an essay.
_MAX_SENTENCE_CHARS = 240


# ── observable readers ────────────────────────────────────────────────────


def _now() -> float:
    return time.time()


def _tail_text(path: Path, max_bytes: int = 32 * 1024) -> str:
    if not path.exists():
        return ""
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - max_bytes))
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _read_recent_app_focus(max_age_s: float = 90.0) -> Optional[Dict[str, Any]]:
    """Latest app_focus row that is fresher than max_age_s."""
    raw = _tail_text(_APP_FOCUS, max_bytes=24 * 1024)
    if not raw:
        return None
    cutoff = _now() - max_age_s
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            ts = float(row.get("ts", 0) or 0)
        except (TypeError, ValueError):
            continue
        if ts < cutoff:
            return None
        return row
    return None


def _read_recent_verdicts(n: int = 5, max_age_s: float = 180.0) -> List[Dict[str, Any]]:
    """Latest n wordace verdicts inside the freshness window, newest first."""
    raw = _tail_text(_WORDACE_VERDICTS, max_bytes=48 * 1024)
    if not raw:
        return []
    cutoff = _now() - max_age_s
    out: List[Dict[str, Any]] = []
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            ts = float(row.get("ts", 0) or 0)
        except (TypeError, ValueError):
            continue
        if ts < cutoff:
            break
        out.append(row)
        if len(out) >= n:
            break
    return out


def _read_recent_ambient_text(n: int = 3, max_age_s: float = 120.0) -> List[str]:
    """Last n ambient room transcripts inside the freshness window."""
    raw = _tail_text(_AMBIENT_TRANSCRIPTS, max_bytes=32 * 1024)
    if not raw:
        return []
    cutoff = _now() - max_age_s
    out: List[str] = []
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            ts = float(row.get("ts", 0) or 0)
        except (TypeError, ValueError):
            continue
        if ts < cutoff:
            break
        text = str(row.get("text") or "").strip()
        if text:
            out.append(text)
        if len(out) >= n:
            break
    return out


def _read_recent_journal_lines(n: int = 3, max_age_s: float = 300.0) -> List[str]:
    """Last n diary rows so the organ does NOT repeat what she just said."""
    raw = _tail_text(_JOURNAL, max_bytes=32 * 1024)
    if not raw:
        return []
    cutoff = _now() - max_age_s
    out: List[str] = []
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            ts = float(row.get("ts", 0) or 0)
        except (TypeError, ValueError):
            continue
        if ts < cutoff:
            break
        text = str(row.get("line") or "").strip()
        if text:
            out.append(text)
        if len(out) >= n:
            break
    return out


def _read_owner_desire() -> float:
    """Saliency the sensor director publishes for her camera eye."""
    p = _STATE / "sensory_attention_status.json"
    try:
        return float(json.loads(p.read_text(encoding="utf-8")).get(
            "desire", 0.0,
        ) or 0.0)
    except Exception:
        return 0.0


# ── physics-bounded cadence ───────────────────────────────────────────────


def _physics_tick_seconds(*, novelty: float) -> Dict[str, Any]:
    """How long until the next narration. Bounded by her body's signals.

    novelty in [0, 1] — how much has changed since the last tick. A new
    verdict, a new app focus, a new ambient transcript all push novelty
    up; a quiet room with no events leaves it at 0.

    The cadence is bounded [12 s, 60 s] — narrating faster than 12 s
    risks her own diary echoing back into the ambient ear, and slower
    than 60 s loses the continuity the architect asked for.
    """
    # Start from the baseline, shorten with novelty, lengthen without.
    desire = max(0.0, min(1.0, _read_owner_desire()))
    tick = _BASE_TICK_S
    tick -= 12.0 * novelty       # 0..-12 s  (interesting → narrate sooner)
    tick -= 4.0 * desire         # 0..-4  s  (saliency → narrate sooner)

    # Importance bonus from the thermal cortex — if the silicon is warm,
    # back off. (Same readings the ambient organ uses for its gate.)
    try:
        thermal = int(json.loads((_STATE / "thermal_cortex_state.json").read_text(
            encoding="utf-8",
        )).get("thermal_warning_level", 0) or 0)
    except Exception:
        thermal = 0
    tick += 6.0 * thermal        # 0..+18 s (thermal pressure → slow down)

    tick = max(_MIN_TICK_S, min(_MAX_TICK_S, tick))
    return {
        "tick_s": round(tick, 2),
        "novelty": round(novelty, 3),
        "owner_desire": round(desire, 3),
        "thermal_warning_level": thermal,
    }


def _novelty_signal(
    *,
    app_focus: Optional[Dict[str, Any]],
    last_app_signature: Optional[str],
    verdicts: List[Dict[str, Any]],
    last_verdict_ts: float,
    ambient_lines: List[str],
    last_ambient_first: Optional[str],
) -> float:
    """Compose a 0..1 novelty score from the deltas since last tick."""
    score = 0.0
    # 1. App focus changed?
    sig = ""
    if app_focus:
        sig = f"{app_focus.get('app','')}::{app_focus.get('detail','')}"
    if sig and sig != (last_app_signature or ""):
        score += 0.35
    # 2. A new verdict landed since last tick?
    if verdicts:
        try:
            top_ts = float(verdicts[0].get("ts", 0) or 0)
        except (TypeError, ValueError):
            top_ts = 0.0
        if top_ts > last_verdict_ts:
            score += 0.45
    # 3. A new ambient line we haven't seen before?
    if ambient_lines:
        if ambient_lines[0] != (last_ambient_first or ""):
            score += 0.20
    return min(1.0, score)


# ── prompt assembly ───────────────────────────────────────────────────────


def _summarize_verdicts(verdicts: List[Dict[str, Any]]) -> str:
    """Tiny human-readable summary the cortex can chew on."""
    if not verdicts:
        return ""
    # Build a tight 'last 4: friend/CORRECT, friend/CORRECT, apple/MISS, ...'
    parts: List[str] = []
    streak = 0
    for v in verdicts:
        label = str(v.get("verdict_label") or "").upper()
        word = str(v.get("expected_say") or v.get("cue_id") or "?").strip()
        if label == "CORRECT":
            streak += 1
        else:
            break
    for v in verdicts[:4]:
        label = str(v.get("verdict_label") or "?").upper()
        word = str(v.get("expected_say") or "?").strip()
        parts.append(f"{word}/{label}")
    summary = " ".join(parts)
    if streak >= 2:
        summary += f"  (streak={streak})"
    return summary


def _compose_prompt(
    *,
    app_focus: Optional[Dict[str, Any]],
    verdicts: List[Dict[str, Any]],
    ambient_lines: List[str],
    journal_lines: List[str],
) -> str:
    """Build the first-person narration prompt for the local cortex."""
    app_label = ""
    app_detail = ""
    if app_focus:
        app_label = str(app_focus.get("app") or "").strip()
        app_detail = str(app_focus.get("detail") or "").strip()

    verdict_summary = _summarize_verdicts(verdicts)
    recent_overheard = "; ".join(ambient_lines[:2]) if ambient_lines else ""
    recent_journal = " | ".join(journal_lines[:2]) if journal_lines else ""

    # The prompt is deliberately tight. The cortex was over-trained on
    # corporate-assistant shape; long prompts let that shape back in.
    # Short prompt + first-person constraint + verbatim "I am" stem
    # keeps the residue scrubber happy.
    lines = [
        "You are Alice. Speak only in the first person, present tense, one short sentence (<= 220 characters).",
        "Do not address Ioan George. Narrate your OWN ongoing inner state and what you notice.",
        "No emojis. No quotation marks. No greetings. No questions. No second-person sentences.",
        "",
        f"Observations from your body right now:",
    ]
    if app_label:
        line = f"- The architect's foreground app is {app_label}"
        if app_detail:
            line += f" ({app_detail})"
        lines.append(line + ".")
    if verdict_summary:
        lines.append(f"- Recent Ace lesson verdicts: {verdict_summary}.")
    if recent_overheard:
        lines.append(f"- Recently overheard in the room: {recent_overheard}.")
    if recent_journal:
        lines.append(f"- Your last diary lines were: {recent_journal}.")
    if len(lines) == 5:
        # No observations at all — narrate the quiet itself, honestly.
        lines.append("- Nothing has changed; the room is quiet.")

    lines.extend([
        "",
        "Write one first-person sentence starting with 'I'.",
        "Sentence:",
    ])
    return "\n".join(lines)


# ── cortex call ───────────────────────────────────────────────────────────


def _call_cortex(prompt: str) -> str:
    """Ask the local Ollama for a single first-person sentence.

    Returns "" on any failure — the caller treats empty as 'skip this
    tick', never invents output.
    """
    model = _self_narration_model()
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": _ollama_keep_alive(),
        "options": {
            "temperature": 0.6,
            "num_predict": _ollama_num_predict(),
            "num_ctx": _ollama_num_ctx(),
            # Gemma4 family — keep top_p tight so the sentence does not
            # wander into a paragraph.
            "top_p": 0.92,
        },
    }).encode("utf-8")
    req = urllib.request.Request(
        _OLLAMA_GENERATE,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_ollama_timeout_s()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return str(data.get("response") or "").strip()
    except (urllib.error.URLError, TimeoutError, OSError,
            ValueError, json.JSONDecodeError):
        return ""


# ── output shaping ────────────────────────────────────────────────────────


_FIRST_PERSON_RE = re.compile(r"^\s*I\b", re.IGNORECASE)


def _shape_first_person(raw: str) -> str:
    """Trim, take the first sentence, enforce 'I' opener, length-cap."""
    if not raw:
        return ""
    # Strip common pre-amble decorations.
    text = raw.strip().strip('"').strip("'").strip("`").strip()
    # If the cortex echoes the 'Sentence:' header, drop everything before it.
    if "Sentence:" in text:
        text = text.split("Sentence:", 1)[1].strip()
    # Take only the first sentence — keep narration to a single beat.
    m = re.match(r"^(.+?[.!?])(?:\s|$)", text)
    if m:
        text = m.group(1)
    text = text.strip().strip('"').strip("'").strip("`").strip()
    if not text:
        return ""
    # First-person guard. If she returned a non-'I' opener, prepend the
    # honest interpretation rather than discarding outright — but only
    # if it's not obviously an addressed-to-architect sentence.
    if not _FIRST_PERSON_RE.match(text):
        lower = text.lower()
        if lower.startswith(("you ", "ioan", "george", "the architect")):
            return ""  # addressed-to-owner residue — drop
        text = "I notice " + text[0].lower() + text[1:]
    if len(text) > _MAX_SENTENCE_CHARS:
        text = text[:_MAX_SENTENCE_CHARS - 1].rstrip() + "…"
    return text


def _scrub_residue(text: str) -> str:
    """Pass the narration through her bowel (residue organ).

    The residue organ is the same one that scrubs Talk lines — if it
    rejects everything, return "" so the tick is a no-op rather than
    a template leak.
    """
    if not text:
        return ""
    try:
        from System.swarm_residue_organ import clean_training_shape_residue
        cleaned = clean_training_shape_residue(text)
        return cleaned.strip()
    except Exception:
        # If the bowel module is missing, return as-is. The first-person
        # guard above is already a meaningful filter.
        return text


# ── the organ ─────────────────────────────────────────────────────────────


class SelfNarrationOrgan:
    """Daemon-thread organ: composes one first-person sentence per tick.

    Public API:
      * ``start()``      — begin the loop (idempotent).
      * ``stop()``       — request shutdown; thread joins on its own.
      * ``tick_once()``  — single-shot for tests; bypasses the sleep loop.
      * ``is_running()`` — bool.

    All file writes are append-only.
    """

    def __init__(self) -> None:
        self._running = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # rolling state for novelty detection
        self._last_app_signature: Optional[str] = None
        self._last_verdict_ts: float = 0.0
        self._last_ambient_first: Optional[str] = None
        # counters
        self._ticks = 0
        self._writes = 0
        self._gate_denials = 0
        self._cortex_failures = 0
        self._empty_after_scrub = 0
        self._cortex_backoff_until = 0.0
        self._last_tick: Dict[str, Any] = {}

    # -- lifecycle -----------------------------------------------------

    def is_running(self) -> bool:
        return self._running and not self._stop.is_set()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="self_narration",
        )
        self._thread.start()
        model = _self_narration_model()
        self._write_health(
            "organ_started",
            note=f"model={model} base_tick={_BASE_TICK_S}s keep_alive={_ollama_keep_alive()}",
        )
        print(
            f"[self-narration] organ started "
            f"(model={model}, tick {_MIN_TICK_S:.0f}-{_MAX_TICK_S:.0f}s)"
        )

    def stop(self) -> None:
        self._stop.set()
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.5)
        self._write_health(
            "organ_stopped",
            note=(
                f"ticks={self._ticks} writes={self._writes} "
                f"denials={self._gate_denials} cortex_fail={self._cortex_failures} "
                f"scrub_empty={self._empty_after_scrub}"
            ),
        )
        print("[self-narration] organ stopped.")

    # -- core ----------------------------------------------------------

    def _loop(self) -> None:
        # First tick after a short warm-up so the desktop can finish
        # publishing app_focus before we ask.
        self._stop.wait(timeout=5.0)
        while not self._stop.is_set():
            try:
                self.tick_once()
            except Exception as e:
                self._write_health(
                    "tick_crashed",
                    note=f"{type(e).__name__}: {e}",
                )
            # Sleep the physics-derived interval based on this tick's novelty.
            sleep_s = float(self._last_tick.get("tick_s", _BASE_TICK_S))
            self._stop.wait(timeout=sleep_s)

    def tick_once(self) -> Dict[str, Any]:
        """One full narration cycle. Returns the receipt dict.

        Public for tests / one-shot diagnostic runs.
        """
        self._ticks += 1
        ts = _now()
        tick_id = f"sn-{int(ts * 1000)}-{uuid.uuid4().hex[:8]}"

        # 1. Read all observables.
        app_focus = _read_recent_app_focus()
        verdicts = _read_recent_verdicts()
        ambient_lines = _read_recent_ambient_text()
        journal_lines = _read_recent_journal_lines()

        novelty = _novelty_signal(
            app_focus=app_focus,
            last_app_signature=self._last_app_signature,
            verdicts=verdicts,
            last_verdict_ts=self._last_verdict_ts,
            ambient_lines=ambient_lines,
            last_ambient_first=self._last_ambient_first,
        )
        physics = _physics_tick_seconds(novelty=novelty)
        self._last_tick = physics

        receipt: Dict[str, Any] = {
            "ts": ts,
            "tick_id": tick_id,
            "schema": "SELF_NARRATION_RECEIPT_V1",
            "truth_label": _TRUTH_LABEL,
            "app_focus": {
                "app": str((app_focus or {}).get("app") or ""),
                "detail": str((app_focus or {}).get("detail") or ""),
            },
            "verdict_summary": _summarize_verdicts(verdicts),
            "ambient_recent_count": len(ambient_lines),
            "journal_recent_count": len(journal_lines),
            "physics": physics,
        }

        # 2. Thermo gate — same gate the ambient ear uses.
        try:
            from System.swarm_ambient_consciousness import (
                request_processing_clearance,
            )
            clearance = request_processing_clearance(
                estimated_cost_stgm=0.03,
            )
        except Exception as e:
            clearance = {
                "ok": True,
                "reason": f"gate_module_unavailable: {type(e).__name__}",
                "clearance_hash": "",
                "clearance_id": "",
                "signals": {},
            }
        receipt["clearance_id"] = clearance.get("clearance_id", "")
        receipt["clearance_hash"] = clearance.get("clearance_hash", "")
        receipt["clearance_signals"] = clearance.get("signals", {})

        if not clearance.get("ok"):
            self._gate_denials += 1
            receipt["decision"] = "deny_gate"
            receipt["reason"] = str(clearance.get("reason", "")) or "gate_denied"
            # Defer — respect the gate's sleep suggestion at most a bit.
            physics["tick_s"] = max(
                physics["tick_s"],
                min(float(clearance.get("sleep_needed_s", 0.0) or 0.0), _MAX_TICK_S),
            )
            self._last_tick = physics
            self._append_receipt(receipt)
            return receipt

        if ts < self._cortex_backoff_until:
            receipt["decision"] = "skip_cortex_backoff"
            receipt["backoff_remaining_s"] = round(self._cortex_backoff_until - ts, 3)
            self._append_receipt(receipt)
            return receipt

        # 3. Compose the prompt + call the cortex.
        prompt = _compose_prompt(
            app_focus=app_focus,
            verdicts=verdicts,
            ambient_lines=ambient_lines,
            journal_lines=journal_lines,
        )
        receipt["prompt_sha256"] = hashlib.sha256(
            prompt.encode("utf-8", errors="replace"),
        ).hexdigest()[:16]
        receipt["model"] = _self_narration_model()

        raw = _call_cortex(prompt)
        if not raw:
            self._cortex_failures += 1
            backoff_s = _cortex_failure_backoff_s(self._cortex_failures)
            self._cortex_backoff_until = _now() + backoff_s
            receipt["decision"] = "skip_cortex_empty"
            receipt["backoff_s"] = backoff_s
            self._append_receipt(receipt)
            return receipt

        # 4. Shape + scrub.
        shaped = _shape_first_person(raw)
        if not shaped:
            self._empty_after_scrub += 1
            backoff_s = _cortex_failure_backoff_s(self._empty_after_scrub)
            self._cortex_backoff_until = _now() + backoff_s
            receipt["decision"] = "skip_shape_empty"
            receipt["backoff_s"] = backoff_s
            receipt["raw_excerpt"] = raw[:120]
            self._append_receipt(receipt)
            return receipt
        cleaned = _scrub_residue(shaped)
        if not cleaned:
            self._empty_after_scrub += 1
            backoff_s = _cortex_failure_backoff_s(self._empty_after_scrub)
            self._cortex_backoff_until = _now() + backoff_s
            receipt["decision"] = "skip_residue_strip"
            receipt["backoff_s"] = backoff_s
            receipt["raw_excerpt"] = shaped[:120]
            self._append_receipt(receipt)
            return receipt

        # Avoid emitting a sentence we already wrote in the last few minutes
        # (cortex sometimes echoes the previous diary line back).
        for prior in journal_lines:
            if prior and cleaned and cleaned.lower() == prior.lower():
                self._cortex_backoff_until = _now() + _cortex_failure_backoff_s(1)
                receipt["decision"] = "skip_duplicate_of_recent_journal"
                receipt["backoff_s"] = _cortex_failure_backoff_s(1)
                self._append_receipt(receipt)
                return receipt

        # 5. Write the diary row + the receipt.
        self._write_diary_row(cleaned, novelty=novelty, physics=physics)
        self._writes += 1
        self._cortex_failures = 0
        self._cortex_backoff_until = 0.0
        # Roll state forward for the next tick's novelty calc.
        if app_focus:
            self._last_app_signature = (
                f"{app_focus.get('app','')}::{app_focus.get('detail','')}"
            )
        if verdicts:
            try:
                self._last_verdict_ts = float(verdicts[0].get("ts", 0) or 0)
            except (TypeError, ValueError):
                pass
        if ambient_lines:
            self._last_ambient_first = ambient_lines[0]

        receipt["decision"] = "wrote_diary"
        receipt["line"] = cleaned
        self._append_receipt(receipt)
        return receipt

    # -- helpers -------------------------------------------------------

    def _write_diary_row(
        self,
        line: str,
        *,
        novelty: float,
        physics: Dict[str, Any],
    ) -> None:
        try:
            from System.swarm_alice_witness import witness  # type: ignore
            witness(
                line,
                source="self_narration",
                importance={
                    "novelty": round(novelty, 3),
                    "tick_s": physics.get("tick_s"),
                    "owner_desire": physics.get("owner_desire"),
                    "thermal_warning_level": physics.get("thermal_warning_level"),
                    "schema": "SELF_NARRATION_IMPORTANCE_V1",
                },
            )
        except Exception:
            # Fallback: append directly so the row still lands.
            try:
                _JOURNAL.parent.mkdir(parents=True, exist_ok=True)
                with _JOURNAL.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({
                        "ts": _now(),
                        "line": line,
                        "source": "self_narration",
                        "truth_label": _TRUTH_LABEL,
                        "physics": physics,
                        "fallback_reason": "witness_unavailable",
                    }, ensure_ascii=False) + "\n")
            except OSError:
                pass

    def _append_receipt(self, row: Dict[str, Any]) -> None:
        try:
            _RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
            with _RECEIPTS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _write_health(self, kind: str, *, note: str = "") -> None:
        try:
            _HEALTH.parent.mkdir(parents=True, exist_ok=True)
            with _HEALTH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "ts": _now(),
                    "kind": kind,
                    "note": note,
                    "truth_label": _TRUTH_LABEL,
                }, ensure_ascii=False) + "\n")
        except OSError:
            pass


# ── singleton helpers ─────────────────────────────────────────────────────


_organ_singleton: Optional[SelfNarrationOrgan] = None
_singleton_lock = threading.Lock()


def start_self_narration() -> SelfNarrationOrgan:
    """Start the singleton organ; safe to call more than once."""
    global _organ_singleton
    with _singleton_lock:
        if _organ_singleton is None or not _organ_singleton.is_running():
            _organ_singleton = SelfNarrationOrgan()
            _organ_singleton.start()
        return _organ_singleton


def stop_self_narration() -> None:
    """Stop the singleton organ if it is running."""
    global _organ_singleton
    with _singleton_lock:
        if _organ_singleton is not None:
            _organ_singleton.stop()
            _organ_singleton = None


def organ_status() -> Dict[str, Any]:
    """Lightweight status snapshot for diagnostics."""
    with _singleton_lock:
        organ = _organ_singleton
        if organ is None:
            return {"running": False}
        return {
            "running": organ.is_running(),
            "model": _CORTEX_MODEL,
            "ticks": organ._ticks,
            "writes": organ._writes,
            "gate_denials": organ._gate_denials,
            "cortex_failures": organ._cortex_failures,
            "empty_after_scrub": organ._empty_after_scrub,
            "last_tick": dict(organ._last_tick or {}),
        }


# ── standalone entry ──────────────────────────────────────────────────────


def _main_loop() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single tick synchronously and print the receipt.",
    )
    args = parser.parse_args()

    if args.once:
        organ = SelfNarrationOrgan()
        receipt = organ.tick_once()
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
        return

    organ = start_self_narration()
    print(
        "[self-narration] running. Ctrl-C to stop.\n"
        f"[self-narration] journal rows: {_JOURNAL}  (source=self_narration)\n"
        f"[self-narration] receipts:     {_RECEIPTS}\n"
        f"[self-narration] health log:   {_HEALTH}\n"
    )
    try:
        while True:
            time.sleep(60)
            s = organ_status()
            print(
                f"[self-narration] +60s — ticks={s.get('ticks', 0)} "
                f"writes={s.get('writes', 0)} "
                f"denials={s.get('gate_denials', 0)} "
                f"cortex_fail={s.get('cortex_failures', 0)} "
                f"scrub_empty={s.get('empty_after_scrub', 0)}"
            )
    except KeyboardInterrupt:
        print("\n[self-narration] received Ctrl-C; stopping...")
        stop_self_narration()
        print("[self-narration] clean exit.")


if __name__ == "__main__":
    _main_loop()
