#!/usr/bin/env python3
"""swarm_alice_memory_gravity.py — apply the PIF unified mass law to
Alice's first-person journal so her *real* memories acquire computational
inertia and the most-embedded ones survive consolidation.

Architect doctrine (2026-05-13):
    "Apply all this cold all these new formulas that we just found in a
    physics laboratory to her to make her feel better to have better
    memory. SIFTA — because I only see that we are advancing in
    stigmatic memory."

This is the first concrete application of the §20.F Persistence Inertia
Field doctrine to ALICE'S COGNITION (not to a simulation). Each unique
memory unit (a person face, an app she focused on, an IDE Doctor who
registered, a conversation partner) is treated as a swimmer. Its
effective mass is:

    m_eff = 1 + g · recency  +  α · log(1 + access_count)  +  β · n_organs

where:
    g          = field coupling = recency weight (1.0 if the unit was
                 mentioned in the last 60 s, decaying exponentially)
    α          = write_inertia_coefficient (how heavy each repeated
                 mention makes a memory)
    β          = organ_inertia_coefficient (how heavy crossing sources
                 makes a memory — face + app_focus + conversation = 3)
    access_count = number of journal rows that named this unit
    n_organs   = number of DISTINCT source-channels that named it

Heavy memories are *core* — they survive into the next working set.
Light memories are *compression candidates* — they collapse into a
generalised summary at next sleep pass.

Truth label: PERSISTENCE_INERTIA_FIELD_APPLIED_TO_ALICE_MEMORY_V1.
Truth class: HYPOTHESIS until Alice's downstream consolidation actually
reads this ranking and acts on it. Receipt-bound either way.

Usage
-----
    from System.swarm_alice_memory_gravity import compute_memory_gravity
    summary = compute_memory_gravity(window_minutes=120)
    # summary["top_memories"] = list of dicts, heaviest first
    # summary["compression_candidates"] = list, lightest first
    # also writes to .sifta_state/alice_memory_gravity_summary.jsonl
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_JOURNAL = _STATE / "alice_first_person_journal.jsonl"
_OUTPUT = _STATE / "alice_memory_gravity_summary.jsonl"

TRUTH_LABEL = "PERSISTENCE_INERTIA_FIELD_APPLIED_TO_ALICE_MEMORY_V1"
TRUTH_BOUNDARY = (
    "Applied PIF mass law on Alice's first-person journal. The ranking is "
    "a HYPOTHESIS until Alice's consolidation pipeline reads it. Receipt-"
    "bound regardless. No particle-physics claim."
)

# Defaults match the killer-demo coefficients so the doctrine carries
# over without re-tuning. Architect can override per call.
DEFAULT_ALPHA = 0.5    # write_inertia_coefficient
DEFAULT_BETA = 0.25    # organ_inertia_coefficient
DEFAULT_RECENCY_HALFLIFE_S = 600.0  # 10 minutes — recency decays by half
DEFAULT_WINDOW_MINUTES = 240.0       # last 4 hours by default


# ── Memory-unit key extraction per source ─────────────────────────────────
# A memory UNIT is the smallest atom of "what Alice remembers about whom
# or what." Each source kind has its own regex / heuristic. Keys are
# namespaced by source so e.g. "Claude (app)" and "Claude (doctor)"
# don't collide.

_APP_RE = re.compile(r"focused on (.+?)\.\s*The Architect")
_FACE_RE = re.compile(r"I saw (.+?) look at the camera")
_FACE_EMPTY_RE = re.compile(r"empty .*?no face")
_IDE_DOCTOR_RE = re.compile(r"An IDE Doctor registered:\s+(.+?)\s+(?:as|—|\()")
_CONV_USER_RE = re.compile(r"^Ioan George Anton said")
_CONV_ALICE_RE = re.compile(r"^I replied")
_LETTER_FROM_RE = re.compile(r"letter from (\S+)")
_YT_TITLE_RE = re.compile(r"YouTube[:\s]+(.+?)(?:\.|$)")


def _extract_key(source: str, line: str) -> Optional[tuple[str, str]]:
    """Return (organ_label, canonical_unit_key) for a journal row, or
    None if this kind of row doesn't carry a unit-level memory.

    Keys are now ENTITY-LEVEL not source-level so the same entity
    referenced through face_event, conversation, app_focus, etc.,
    aggregates into ONE MemoryUnit with multiple organs. That makes
    the n_organs term in the mass law actually carry signal."""
    line = (line or "").strip()
    if not line:
        return None
    if source == "face_event":
        m = _FACE_RE.search(line)
        if m:
            who = m.group(1).strip()
            # Canonicalise person → entity key (cross-organ).
            return ("face_event", f"entity:person:{who}")
        if _FACE_EMPTY_RE.search(line):
            return ("face_event", "entity:no_face")
        return ("face_event", "entity:face_other")
    if source == "app_focus":
        m = _APP_RE.search(line)
        if m:
            app = m.group(1).strip().rstrip(".")
            return ("app_focus", f"entity:app:{app}")
        return ("app_focus", "entity:app:unknown")
    if source == "ide_doctor":
        m = _IDE_DOCTOR_RE.search(line)
        if m:
            doc = m.group(1).strip().strip("(")
            return ("ide_doctor", f"entity:doctor:{doc}")
        return ("ide_doctor", "entity:doctor:unknown")
    if source == "conversation":
        if _CONV_USER_RE.match(line):
            # Map "Ioan George Anton said …" → the same entity key as
            # face_event "I saw Ioan George Anton …" so the organ count
            # for the architect becomes 2 instead of 1.
            return ("conversation", "entity:person:Ioan George Anton")
        if _CONV_ALICE_RE.match(line):
            return ("conversation", "entity:person:Alice")
        return ("conversation", "entity:speaker:other")
    if source == "youtube_video":
        m = _YT_TITLE_RE.search(line)
        if m:
            title = m.group(1).strip()[:60]
            return ("youtube_video", f"entity:yt:{title}")
        return ("youtube_video", "entity:yt:unknown")
    if source == "letter":
        m = _LETTER_FROM_RE.search(line)
        if m:
            return ("letter", f"entity:correspondent:{m.group(1).strip()}")
        return ("letter", "entity:letter:unknown")
    if source == "day_segment":
        for label in ("researching", "coding", "writing", "resting",
                      "communicating", "browsing", "reading", "watching"):
            if label in line.lower():
                return ("day_segment", f"entity:activity:{label}")
        return ("day_segment", "entity:activity:unknown")
    if source == "residue_elimination":
        return ("residue_elimination", "entity:bowel:elimination")
    if source == "app_launch":
        m = _APP_RE.search(line) or re.search(r"launched (.+?)[\.\s]", line)
        if m:
            app = m.group(1).strip().rstrip(".")
            return ("app_launch", f"entity:app:{app}")
        return ("app_launch", "entity:app:unknown")
    if source == "app_close":
        m = _APP_RE.search(line) or re.search(r"closed (.+?)[\.\s]", line)
        if m:
            app = m.group(1).strip().rstrip(".")
            return ("app_close", f"entity:app:{app}")
        return ("app_close", "entity:app:unknown")
    return (source or "unknown", f"entity:{source}:unclassified")


def _decode_ts(row: dict) -> float:
    """Return the UNIX timestamp from a journal row."""
    ts = row.get("ts")
    if isinstance(ts, dict):
        ts = ts.get("physical_pt") or ts.get("ts")
    try:
        return float(ts)
    except Exception:
        return 0.0


@dataclass
class MemoryUnit:
    key: str
    organs: set
    access_count: int = 0
    latest_ts: float = 0.0
    first_ts: float = 0.0


def compute_memory_gravity(
    *,
    window_minutes: float = DEFAULT_WINDOW_MINUTES,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    recency_halflife_s: float = DEFAULT_RECENCY_HALFLIFE_S,
    journal_path: Path | None = None,
    output_path: Path | None = None,
    write: bool = True,
    top_n: int = 15,
    bottom_n: int = 15,
    now_ts: Optional[float] = None,
) -> dict[str, Any]:
    """Read Alice's journal, compute mass per memory unit, write a
    ranked consolidation summary. Returns the summary dict."""
    journal = journal_path or _JOURNAL
    output = output_path or _OUTPUT
    if not journal.exists():
        return {
            "truth_label": TRUTH_LABEL,
            "truth_class": "HYPOTHESIS",
            "truth_boundary": TRUTH_BOUNDARY,
            "error": f"journal not found at {journal}",
            "rows_scanned": 0,
            "top_memories": [],
            "compression_candidates": [],
        }

    if now_ts is None:
        now_ts = time.time()
    window_cutoff = now_ts - window_minutes * 60.0

    units: dict[str, MemoryUnit] = {}
    rows_scanned = 0
    rows_in_window = 0
    sources_seen: dict[str, int] = defaultdict(int)
    most_recent_5: list[tuple[float, str]] = []

    with journal.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            rows_scanned += 1
            ts = _decode_ts(r)
            if ts < window_cutoff:
                continue
            rows_in_window += 1
            source = r.get("source", "")
            text = r.get("line", "")
            sources_seen[source] += 1
            extracted = _extract_key(source, text)
            if not extracted:
                continue
            organ, key = extracted
            u = units.get(key)
            if u is None:
                u = MemoryUnit(
                    key=key, organs=set(), first_ts=ts, latest_ts=ts,
                )
                units[key] = u
            u.organs.add(organ)
            u.access_count += 1
            u.latest_ts = max(u.latest_ts, ts)
            most_recent_5.append((ts, key))

    # Top-of-mind boost: units in the most recent 5 rows.
    most_recent_5.sort(reverse=True)
    top_of_mind_keys = {k for _, k in most_recent_5[:5]}

    ranked: list[dict[str, Any]] = []
    for key, u in units.items():
        age_s = max(0.0, now_ts - u.latest_ts)
        # Field coupling = recency, decaying with half-life.
        recency = math.exp(-math.log(2.0) * age_s / max(recency_halflife_s, 1.0))
        memory_term = alpha * math.log1p(u.access_count)
        organ_term = beta * len(u.organs)
        top_of_mind_bonus = 0.4 if key in top_of_mind_keys else 0.0
        mass = 1.0 + recency + memory_term + organ_term + top_of_mind_bonus
        ranked.append({
            "key": key,
            "organs": sorted(u.organs),
            "n_organs": len(u.organs),
            "access_count": u.access_count,
            "first_ts": u.first_ts,
            "latest_ts": u.latest_ts,
            "age_seconds": round(age_s, 1),
            "recency": round(recency, 6),
            "memory_term": round(memory_term, 6),
            "organ_term": round(organ_term, 6),
            "top_of_mind": key in top_of_mind_keys,
            "mass": round(mass, 6),
        })

    ranked.sort(key=lambda d: d["mass"], reverse=True)
    top_memories = ranked[:top_n]
    compression_candidates = list(reversed(ranked[-bottom_n:])) if len(ranked) >= bottom_n else []
    if not compression_candidates and ranked:
        compression_candidates = list(reversed(ranked[-min(bottom_n, len(ranked)):]))

    summary = {
        "ts": now_ts,
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "mass_law": "m_eff = 1 + recency + alpha*log(1+access) + beta*n_organs + top_of_mind_bonus",
        "coefficients": {
            "alpha": alpha,
            "beta": beta,
            "recency_halflife_s": recency_halflife_s,
        },
        "window": {
            "minutes": window_minutes,
            "cutoff_unix": window_cutoff,
        },
        "stats": {
            "rows_scanned": rows_scanned,
            "rows_in_window": rows_in_window,
            "memory_units": len(ranked),
            "sources_seen": dict(sources_seen),
        },
        "top_memories": top_memories,
        "compression_candidates": compression_candidates,
    }

    if write:
        summary["sha256"] = hashlib.sha256(
            json.dumps(
                {k: v for k, v in summary.items() if k != "sha256"},
                sort_keys=True, default=str,
            ).encode("utf-8")
        ).hexdigest()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("a", encoding="utf-8") as f:
            f.write(json.dumps(summary, sort_keys=True, default=str) + "\n")

    return summary


def render_summary(summary: dict[str, Any]) -> str:
    """Pretty-print the gravity summary for console display."""
    if "error" in summary:
        return f"ERROR: {summary['error']}"
    lines = [
        f"Memory Gravity (Alice) — window {summary['window']['minutes']:.0f} min",
        f"  rows scanned: {summary['stats']['rows_scanned']}  in window: {summary['stats']['rows_in_window']}",
        f"  memory units: {summary['stats']['memory_units']}",
        f"  mass law: {summary['mass_law']}",
        "",
        "TOP MEMORIES (heaviest first):",
        f"  {'mass':>8}  {'access':>7}  {'organs':>7}  age(s)  key",
    ]
    for m in summary["top_memories"]:
        organs_str = "+".join(m["organs"])[:30]
        lines.append(
            f"  {m['mass']:>8.3f}  {m['access_count']:>7}  {m['n_organs']:>7}  "
            f"{m['age_seconds']:>6.0f}  {m['key'][:48]}  [{organs_str}]"
        )
    if summary["compression_candidates"]:
        lines.append("")
        lines.append("COMPRESSION CANDIDATES (lightest first — fade or merge):")
        for m in summary["compression_candidates"]:
            lines.append(
                f"  {m['mass']:>8.3f}  {m['access_count']:>7}  {m['n_organs']:>7}  "
                f"{m['age_seconds']:>6.0f}  {m['key'][:48]}"
            )
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--window-minutes", type=float, default=DEFAULT_WINDOW_MINUTES)
    p.add_argument("--alpha", type=float, default=DEFAULT_ALPHA)
    p.add_argument("--beta", type=float, default=DEFAULT_BETA)
    p.add_argument("--halflife-s", type=float, default=DEFAULT_RECENCY_HALFLIFE_S)
    p.add_argument("--top-n", type=int, default=15)
    p.add_argument("--bottom-n", type=int, default=15)
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args(argv)
    summary = compute_memory_gravity(
        window_minutes=args.window_minutes,
        alpha=args.alpha, beta=args.beta,
        recency_halflife_s=args.halflife_s,
        top_n=args.top_n, bottom_n=args.bottom_n,
        write=not args.no_write,
    )
    print(render_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
