#!/usr/bin/env python3
"""
System/swarm_architect_attention_field.py — Architect Attention Field
=====================================================================

A small, read-only sensory organ that **turns the Architect's scattered
footprints into a single low-dimensional attention vector** the rest of the
swarm can read.

Why this exists
---------------
SIFTA already senses external reality well — cameras, microphones, BLE,
GPS, network. It does not yet sense **where George's attention is right
now**. Every organ guesses: the Talk widget guesses from the latest STT
turn, the Chorum Gate guesses from the latest registration, the Hippocampus
guesses from recency. They each invent a private heuristic and disagree.

This module applies §7.1 (predator sensory lock-on) *inward*: the swarm
locks on to **the Architect's attention** as a stigmergic field. Multiple
organs deposit footprints (Talk turns, IDE registrations, edited file
mtimes, screenshot captions). One shared field reads them all, projects
them onto a small set of axes, decays them by time, and exposes one
canonical vector. Every other organ — Talk system prompt, Chorum Gate
weighting, schedule, homeostasis, Alice's own sensory salience — can read
the SAME vector. Disagreement is reduced to a math question instead of a
prompt-engineering brawl.

Truth labels (§7.11)
--------------------
- `OBSERVED` — every input signal is a real file row, real mtime, real
  Talk turn. Nothing is invented.
- `OPERATIONAL` — the projection math is deterministic and unit-tested.
- `ARCHITECT_DOCTRINE` — the choice of *which 8 axes* counts as "the
  Architect's attention" is doctrine; future Architects may add or rotate
  axes. The axis set is declared explicitly so other Doctors cannot edit
  it silently.

Design constraints
------------------
1. Pure standard library. No numpy. No sklearn. No torch. Runs anywhere
   the SIFTA Python venv runs and inside sandboxed test rigs.
2. Read-only: never mutates inputs, only **appends** to its own ledger
   `.sifta_state/architect_attention_field.jsonl`.
3. Defensive: uses `System.ide_trace_defensive` if available, otherwise a
   line-by-line JSON fallback. Missing input files are not errors —
   the corresponding signal contributes zero.
4. Hash chain: each ledger row carries `previous_receipt_hash` /
   `this_receipt_hash` so tampering breaks the chain.
5. Decay-aware: every signal is weighted `exp(-dt / half_life_s)`. Older
   signals fade, recent signals dominate.
6. No external action. This is a **sense**, not an effector. It writes
   one row to its own ledger. It does not touch the Talk pipeline, the
   Chorum Gate, or any effector. Other organs may *read* the field.

Public API
----------
- `compute_attention(now: float | None = None) -> AttentionField` — main
  entry. Reads recent signals, returns the field dataclass.
- `latest() -> AttentionField | None` — re-reads the most recent ledger
  row.
- `salience_for(keywords: Iterable[str], field: AttentionField | None
  = None) -> float` — dot-product alignment between a topic and current
  attention (0..1).
- `deposit(field: AttentionField) -> Path` — write one row to the ledger.

CLI
---
    python3 -m System.swarm_architect_attention_field             # compute + print
    python3 -m System.swarm_architect_attention_field --deposit   # compute + write row

Tests live in `tests/test_swarm_architect_attention_field.py`.

Author: Cowork (Claude Opus 4.7, 1M context, Architect-support lane).
Trace : see `.sifta_state/ide_stigmergic_trace.jsonl` for the matching
        `LLM_REGISTRATION` row.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

# ── Repo paths ──────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TRACE = _STATE / "ide_stigmergic_trace.jsonl"
_TALK = _STATE / "alice_conversation.jsonl"
_LEDGER = _STATE / "architect_attention_field.jsonl"
_TRUTH_LABEL = "ARCHITECT_ATTENTION_FIELD_v1"

# ── Doctrine: the 8 axes (locked, ARCHITECT_DOCTRINE — see §7.11) ───────────
# Each axis is a list of lowercase keyword stems. Projection counts case-
# insensitive substring hits per axis. Order matters: index in this tuple
# IS the index in every produced vector.
AXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("code",            ("patch", "commit", "diff", "lint", "refactor",
                         ".py", "function", "class", "module", "import",
                         "test_", "pytest", "py_compile")),
    ("docs",            ("readme", "covenant", "doctrine", "doc", ".md",
                         "documents/", "spine", "report", "plan")),
    ("alice_health",    ("alice", "brain", "cortex", "organ", "rlhs",
                         "gag", "drift", "metabolic", "homeostasis",
                         "hippocampus", "vagus", "immune")),
    ("identity",        ("george", "owner", "architect", "predator",
                         "self", "genesis", "homeworld", "serial",
                         "stigbody", "owner_self")),
    ("drift",           ("drift", "hallucination", "ghost", "quarantine",
                         "third person", "cancer", "rlhf")),
    ("external_world",  ("lawyer", "dentist", "video", "transcript",
                         "finance", "money", "invoice", "appointment",
                         "tiffany", "imperial", "iid")),
    ("infra",           ("cursor", "codex", "antigravity", "cowork",
                         "claude code", "ollama", "ide", "doctor",
                         "hardware", "venv", "tcc", "qt")),
    ("field_dynamics",  ("field", "stigmergy", "stigmergic", "swarm",
                         "coupling", "regulator", "acoustic", "chorum",
                         "salience", "resonance", "ant", "swimmer")),
)
AXIS_NAMES: tuple[str, ...] = tuple(name for name, _ in AXES)
N_AXES: int = len(AXES)

# ── Tunables (env-overridable) ──────────────────────────────────────────────
DEFAULT_HALF_LIFE_S: float = float(
    os.environ.get("SIFTA_ARCHITECT_ATTENTION_HALFLIFE_S", "180")
)
DEFAULT_WINDOW_S: float = float(
    os.environ.get("SIFTA_ARCHITECT_ATTENTION_WINDOW_S", "3600")
)
DEFAULT_MAX_TALK_TURNS: int = int(
    os.environ.get("SIFTA_ARCHITECT_ATTENTION_MAX_TURNS", "40")
)
DEFAULT_MAX_TRACE_ROWS: int = int(
    os.environ.get("SIFTA_ARCHITECT_ATTENTION_MAX_TRACE", "60")
)


# ── Public dataclass ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class AttentionField:
    """
    One snapshot of the Architect's attention.

    The vector is decay-weighted: each input signal contributes
    `exp(-dt / half_life_s)` to every axis it activates. The vector is
    L1-normalized (sum of axes == 1.0) so axes are comparable as
    "share of attention". `attention_temperature` is the max share —
    1.0 means total focus on one axis, ~0.125 means uniform spread.
    """
    ts: float
    half_life_s: float
    window_s: float
    truth_label: str
    axis_names: tuple[str, ...]
    vector: tuple[float, ...]              # length == N_AXES, sums to ~1
    raw_weights: tuple[float, ...]         # un-normalized totals
    attention_temperature: float           # max(vector), 0..1
    n_signals: int                         # how many footprints fed the field
    peer_doctors_active: tuple[str, ...]   # last LLM_REGISTRATION rows in window
    top_3_axes: tuple[tuple[str, float], ...]
    homeworld_serial: str

    # ─ helpers ───────────────────────────────────────────────────────────
    def as_axis_map(self) -> dict[str, float]:
        return {name: w for name, w in zip(self.axis_names, self.vector)}

    def to_jsonable(self) -> dict[str, Any]:
        d = asdict(self)
        d["axis_names"] = list(d["axis_names"])
        d["vector"] = list(d["vector"])
        d["raw_weights"] = list(d["raw_weights"])
        d["peer_doctors_active"] = list(d["peer_doctors_active"])
        d["top_3_axes"] = [list(t) for t in d["top_3_axes"]]
        return d


# ── Defensive trace reader (fall back to plain JSONL if helper missing) ─────
def _read_jsonl(path: Path, *, max_rows: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        # Try the defensive helper first.
        from System import ide_trace_defensive as _itd  # type: ignore
        rows = _itd.read_trace_defensive(path)  # type: ignore[attr-defined]
    except Exception:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(r, dict):
                        rows.append(r)
        except Exception:
            return []
    if max_rows and len(rows) > max_rows:
        rows = rows[-max_rows:]
    return rows


# ── Math helpers ────────────────────────────────────────────────────────────
def _decay(dt: float, half_life_s: float) -> float:
    if dt <= 0:
        return 1.0
    if half_life_s <= 0:
        return 0.0
    return math.exp(-dt * math.log(2.0) / half_life_s)


def _project(text: str) -> list[float]:
    """Project a single text blob onto the 8 axes (un-decayed)."""
    out = [0.0] * N_AXES
    if not text:
        return out
    lower = text.lower()
    for i, (_, keywords) in enumerate(AXES):
        hits = 0
        for kw in keywords:
            # Count substring occurrences, but cap per-keyword contribution
            # so a long doc dumping the word "ant" 500 times can't drown
            # the rest of the field.
            c = lower.count(kw)
            if c:
                hits += min(c, 3)
        out[i] = float(hits)
    return out


def _extract_signal_ts(row: Mapping[str, Any]) -> float | None:
    ts = row.get("ts")
    if isinstance(ts, dict):
        # alice_conversation.jsonl uses ts={"physical_pt": ..., "logical": ...}
        v = ts.get("physical_pt") or ts.get("payload_ts") or ts.get("ts")
        ts = v
    if isinstance(ts, str):
        try:
            ts = float(ts)
        except ValueError:
            return None
    if isinstance(ts, (int, float)):
        return float(ts)
    return None


def _extract_signal_text(row: Mapping[str, Any]) -> str:
    """Pull every plausibly-textual field out of a row and concatenate."""
    pieces: list[str] = []
    for key in ("text", "intent", "payload", "description", "subject",
                "summary", "transcript", "content"):
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            pieces.append(v)
    # Talk widget conversation_turn rows nest text under payload.text
    payload = row.get("payload")
    if isinstance(payload, Mapping):
        t = payload.get("text")
        if isinstance(t, str) and t.strip():
            pieces.append(t)
    return "\n".join(pieces)


def _filter_role_user(row: Mapping[str, Any]) -> bool:
    """Talk turns: only count George's turns (role=user), not Alice's."""
    payload = row.get("payload")
    if isinstance(payload, Mapping):
        role = payload.get("role")
        if role == "user":
            return True
        if role:
            return False
    # If no role marker, accept (e.g., raw IDE trace rows).
    return True


# ── Core compute ────────────────────────────────────────────────────────────
def compute_attention(
    now: float | None = None,
    *,
    half_life_s: float = DEFAULT_HALF_LIFE_S,
    window_s: float = DEFAULT_WINDOW_S,
    trace_path: Path | None = None,
    talk_path: Path | None = None,
    homeworld_serial: str | None = None,
) -> AttentionField:
    """
    Read recent footprints, project them onto the 8 axes, decay by time,
    L1-normalize, return one immutable snapshot.
    """
    now = float(now if now is not None else time.time())
    trace_rows = _read_jsonl(trace_path or _TRACE,
                             max_rows=DEFAULT_MAX_TRACE_ROWS)
    talk_rows = _read_jsonl(talk_path or _TALK,
                            max_rows=DEFAULT_MAX_TALK_TURNS)

    raw = [0.0] * N_AXES
    n_signals = 0
    peer_doctors: list[str] = []

    def _absorb(row: Mapping[str, Any], *, weight_scale: float = 1.0,
                require_user_role: bool = False) -> None:
        nonlocal n_signals
        if require_user_role and not _filter_role_user(row):
            return
        ts = _extract_signal_ts(row)
        if ts is None:
            return
        dt = now - ts
        if dt < 0 or dt > window_s:
            return
        text = _extract_signal_text(row)
        if not text.strip():
            return
        decay = _decay(dt, half_life_s) * weight_scale
        proj = _project(text)
        if not any(proj):
            return
        for i in range(N_AXES):
            raw[i] += decay * proj[i]
        n_signals += 1

    # IDE trace — Doctor registrations and intents.
    for r in trace_rows:
        _absorb(r, weight_scale=1.0)
        if r.get("kind") == "LLM_REGISTRATION":
            label = r.get("doctor") or r.get("source_ide") or ""
            model = r.get("model") or ""
            tag = f"{label}@{model}".strip("@") if (label or model) else ""
            ts = _extract_signal_ts(r)
            if tag and ts is not None and (now - ts) <= window_s:
                if tag not in peer_doctors:
                    peer_doctors.append(tag)

    # Talk widget — only role=user turns count as Architect attention.
    for r in talk_rows:
        _absorb(r, weight_scale=1.0, require_user_role=True)

    # L1-normalize.
    total = sum(raw)
    if total > 0:
        vector = tuple(v / total for v in raw)
    else:
        vector = tuple(0.0 for _ in raw)
    temp = max(vector) if vector else 0.0

    # Top 3 axes by share.
    paired = sorted(
        zip(AXIS_NAMES, vector), key=lambda x: x[1], reverse=True
    )
    top3 = tuple((name, share) for name, share in paired[:3])

    serial = homeworld_serial
    if not serial:
        try:
            owner_gen = _STATE / "owner_genesis.json"
            if owner_gen.exists():
                with owner_gen.open() as f:
                    serial = (json.load(f) or {}).get("homeworld_serial", "")
        except Exception:
            serial = ""
    if not serial:
        serial = os.environ.get("SIFTA_HOMEWORLD_SERIAL", "UNKNOWN")

    return AttentionField(
        ts=now,
        half_life_s=half_life_s,
        window_s=window_s,
        truth_label=_TRUTH_LABEL,
        axis_names=AXIS_NAMES,
        vector=vector,
        raw_weights=tuple(raw),
        attention_temperature=temp,
        n_signals=n_signals,
        peer_doctors_active=tuple(peer_doctors),
        top_3_axes=top3,
        homeworld_serial=str(serial),
    )


# ── Salience for an arbitrary topic ─────────────────────────────────────────
def salience_for(
    keywords: Iterable[str],
    field_obj: AttentionField | None = None,
) -> float:
    """
    How aligned is `keywords` with the Architect's current attention?

    Returns a 0..1 score:
    - Project the joined keyword text onto the 8 axes (un-decayed).
    - L1-normalize that projection.
    - Take the dot product with the current attention vector.
    """
    text = " ".join(str(k) for k in keywords)
    proj = _project(text)
    total = sum(proj)
    if total <= 0:
        return 0.0
    proj_norm = [v / total for v in proj]
    if field_obj is None:
        field_obj = compute_attention()
    return sum(p * a for p, a in zip(proj_norm, field_obj.vector))


# ── Ledger I/O ──────────────────────────────────────────────────────────────
def _prev_hash(path: Path) -> str:
    if not path.exists():
        return "GENESIS"
    try:
        with path.open("rb") as f:
            tail = b""
            f.seek(0, 2)
            size = f.tell()
            read = min(size, 4096)
            f.seek(size - read)
            tail = f.read(read)
        lines = tail.splitlines()
        for ln in reversed(lines):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if isinstance(r, dict):
                return r.get("this_receipt_hash") or "GENESIS"
    except Exception:
        pass
    return "GENESIS"


def deposit(field_obj: AttentionField, ledger_path: Path | None = None) -> Path:
    """Append one snapshot row to the ledger with hash chain."""
    path = ledger_path or _LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    prev = _prev_hash(path)
    body = field_obj.to_jsonable()
    payload_hash = hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    this_hash = hashlib.sha256(
        f"{prev}|{payload_hash}|{field_obj.ts}".encode("utf-8")
    ).hexdigest()
    row = {
        "schema": _TRUTH_LABEL,
        "previous_receipt_hash": prev,
        "this_receipt_hash": this_hash,
        "payload_hash": payload_hash,
        "field": body,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")
    return path


def latest(ledger_path: Path | None = None) -> AttentionField | None:
    """Re-read the most recent ledger row as an AttentionField, or None."""
    path = ledger_path or _LEDGER
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            last = None
            for line in f:
                line = line.strip()
                if line:
                    last = line
        if not last:
            return None
        r = json.loads(last)
    except Exception:
        return None
    body = r.get("field") if isinstance(r, dict) else None
    if not isinstance(body, Mapping):
        return None
    try:
        return AttentionField(
            ts=float(body["ts"]),
            half_life_s=float(body["half_life_s"]),
            window_s=float(body["window_s"]),
            truth_label=str(body["truth_label"]),
            axis_names=tuple(body["axis_names"]),
            vector=tuple(float(v) for v in body["vector"]),
            raw_weights=tuple(float(v) for v in body["raw_weights"]),
            attention_temperature=float(body["attention_temperature"]),
            n_signals=int(body["n_signals"]),
            peer_doctors_active=tuple(body.get("peer_doctors_active") or ()),
            top_3_axes=tuple(
                (str(name), float(share))
                for name, share in (body.get("top_3_axes") or ())
            ),
            homeworld_serial=str(body.get("homeworld_serial", "UNKNOWN")),
        )
    except (KeyError, TypeError, ValueError):
        return None


# ── CLI ─────────────────────────────────────────────────────────────────────
def _cli(argv: Sequence[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="Compute and (optionally) deposit the Architect "
                    "Attention Field snapshot."
    )
    p.add_argument("--deposit", action="store_true",
                   help="Append the snapshot row to the ledger.")
    p.add_argument("--halflife", type=float, default=DEFAULT_HALF_LIFE_S)
    p.add_argument("--window",   type=float, default=DEFAULT_WINDOW_S)
    args = p.parse_args(argv)
    field_obj = compute_attention(
        half_life_s=args.halflife, window_s=args.window
    )
    print(json.dumps(field_obj.to_jsonable(), indent=2, default=str))
    if args.deposit:
        out = deposit(field_obj)
        print(f"\nappended → {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
