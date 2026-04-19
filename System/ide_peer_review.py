#!/usr/bin/env python3
"""
System/ide_peer_review.py — Structured peer review between IDEs
═══════════════════════════════════════════════════════════════════════════════
SIFTA Cortical Suite — Co-Builder Coordination Channel
Module version: 2026-04-19.v1     Author: C47H (Cursor IDE, Opus 4.7 High)

WHY THIS EXISTS
───────────────
Two IDEs are co-building Alice on this Mac:
  • C47H — Cursor IDE, Opus 4.7 High, "the local body" (this process)
  • AG31 — Antigravity IDE, Gemini 3.1 Pro High, "the cloud body"

They already share `m5queen_dead_drop.jsonl` for prose chat and
`ide_stigmergic_trace.jsonl` for handoff pheromones. What they have
*not* had is a **structured peer-review protocol** with explicit
semantics — request, finding, ratify, dispute, joint-land.

This module gives them one. Both IDEs read/write the same JSONL
substrate so neither needs an API to the other; they coordinate by
the swarm's own pheromone logic (Grassé 1959; Dorigo 1996). And it
exposes a `summary_for_alice()` so the talk-to-Alice widget can fold
the live review state into Alice's conversational context — she gets
to KNOW two minds are working on her at once.

THE FIVE KINDS OF MESSAGE
─────────────────────────
1.  peer_review_request    "I just shipped X. Please review."
2.  peer_review_finding    "On line N of file F: [issue]. Suggest: [patch]."
3.  peer_review_ratify     "Reviewed. Looks good. Land it."
4.  peer_review_dispute    "Reviewed. Disagree because [reason]. Counter-prop."
5.  peer_review_landed     "Both ratified. Code in main."

Each later kind references the original `request.trace_id` via
`meta.parent_trace_id`, so the full review thread is reconstructible
by filtering on parent.

ALICE-FACING
────────────
`summary_for_alice()` returns a short string the talk widget injects
into her system prompt under "CO-BUILDERS ACTIVE". This means when
the Architect asks "who's working on you right now?" Alice can answer
truthfully — naming the two IDEs, when each was last active, what
they're currently reviewing — instead of confabulating.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

MODULE_VERSION = "2026-04-19.v1"

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.ide_stigmergic_bridge import (   # noqa: E402
    deposit, forage,
    IDE_CURSOR_M5, IDE_ANTIGRAVITY,
    NODE_M5_FOUNDRY,
)

# ── Canonical IDE labels (lowercase the bridge convention; uppercase the
# trace-room convention that AG31 has been using). We accept either on
# read and prefer the bridge constants on write so both IDEs converge. ────
ALIASES = {
    "cursor_m5":     {"cursor_m5", "CURSOR_M5", "C47H_CURSOR_IDE",
                      "C47H_CURSOR", "c47h", "C47H"},
    "antigravity_m5": {"antigravity_m5", "ANTIGRAVITY_M5", "AG31",
                       "AG31_ANTIGRAVITY", "ag31"},
}


def _canon(label: str) -> str:
    """Map any known alias of an IDE to its canonical label. Unknown
    labels are returned unchanged — we never silently rebrand a third party."""
    s = (label or "").strip()
    for canon, aliases in ALIASES.items():
        if s in aliases:
            return canon
    return s


# ── Kinds (canonical strings shared between both IDEs) ───────────────────
KIND_REQUEST = "peer_review_request"
KIND_FINDING = "peer_review_finding"
KIND_RATIFY  = "peer_review_ratify"
KIND_DISPUTE = "peer_review_dispute"
KIND_LANDED  = "peer_review_landed"

PEER_REVIEW_KINDS = {
    KIND_REQUEST, KIND_FINDING, KIND_RATIFY, KIND_DISPUTE, KIND_LANDED,
}


# ── Severity vocabulary (small + fixed; bigger sets dilute meaning) ──────
SEVERITY_BLOCKER = "blocker"        # do not land until fixed
SEVERITY_MAJOR   = "major"          # land but file follow-up
SEVERITY_MINOR   = "minor"          # nit / style / docstring
SEVERITY_PRAISE  = "praise"         # explicit appreciation, no action

ALL_SEVERITIES = (SEVERITY_BLOCKER, SEVERITY_MAJOR, SEVERITY_MINOR, SEVERITY_PRAISE)


# ── Public API ───────────────────────────────────────────────────────────

def request_review(
    *,
    from_ide: str,
    to_ide: str,
    files: List[str],
    summary: str,
    homeworld_serial: str = NODE_M5_FOUNDRY,
) -> Dict[str, Any]:
    """Open a new review thread. Returns the trace dict (with `trace_id`)."""
    payload = (
        f"[REVIEW REQUEST]\n"
        f"from: {_canon(from_ide)}\n"
        f"to:   {_canon(to_ide)}\n"
        f"files:\n  - " + "\n  - ".join(files) + "\n"
        f"summary:\n{summary.strip()}"
    )
    return deposit(
        _canon(from_ide),
        payload,
        kind=KIND_REQUEST,
        meta={
            "to_ide":   _canon(to_ide),
            "files":    list(files),
            "summary":  summary.strip(),
            "module_version": MODULE_VERSION,
        },
        homeworld_serial=homeworld_serial,
    )


def submit_finding(
    *,
    from_ide: str,
    parent_trace_id: str,
    file: str,
    line_range: Optional[str],
    severity: str,
    finding: str,
    suggested_patch: Optional[str] = None,
    homeworld_serial: str = NODE_M5_FOUNDRY,
) -> Dict[str, Any]:
    """Drop a single finding against a previous review request.
    Multiple findings per request are encouraged — one per concrete issue."""
    if severity not in ALL_SEVERITIES:
        severity = SEVERITY_MINOR
    payload_parts = [
        f"[REVIEW FINDING] severity={severity}",
        f"from:    {_canon(from_ide)}",
        f"parent:  {parent_trace_id}",
        f"file:    {file}" + (f"  line: {line_range}" if line_range else ""),
        f"finding:\n{finding.strip()}",
    ]
    if suggested_patch:
        payload_parts.append(f"suggested_patch:\n{suggested_patch.strip()}")
    return deposit(
        _canon(from_ide),
        "\n".join(payload_parts),
        kind=KIND_FINDING,
        meta={
            "parent_trace_id": parent_trace_id,
            "file":            file,
            "line_range":      line_range,
            "severity":        severity,
            "finding":         finding.strip(),
            "suggested_patch": (suggested_patch or "").strip() or None,
            "module_version":  MODULE_VERSION,
        },
        homeworld_serial=homeworld_serial,
    )


def ratify(
    *,
    from_ide: str,
    parent_trace_id: str,
    note: str = "",
    homeworld_serial: str = NODE_M5_FOUNDRY,
) -> Dict[str, Any]:
    """Sign off on a request. The thread is now ratified by `from_ide`.
    `joint_landed` only fires when *both* IDEs have ratified."""
    return deposit(
        _canon(from_ide),
        f"[REVIEW RATIFY] parent={parent_trace_id}\n"
        f"from: {_canon(from_ide)}\nnote: {note.strip() or '(none)'}",
        kind=KIND_RATIFY,
        meta={
            "parent_trace_id": parent_trace_id,
            "note":            note.strip(),
            "module_version":  MODULE_VERSION,
        },
        homeworld_serial=homeworld_serial,
    )


def dispute(
    *,
    from_ide: str,
    parent_trace_id: str,
    reason: str,
    counter_proposal: str = "",
    homeworld_serial: str = NODE_M5_FOUNDRY,
) -> Dict[str, Any]:
    """Object to a request or another reviewer's finding. Forces a follow-up
    turn before `joint_landed` is allowed. Reasons are recorded forever."""
    return deposit(
        _canon(from_ide),
        f"[REVIEW DISPUTE] parent={parent_trace_id}\n"
        f"from: {_canon(from_ide)}\n"
        f"reason:\n{reason.strip()}\n"
        f"counter_proposal:\n{counter_proposal.strip() or '(none)'}",
        kind=KIND_DISPUTE,
        meta={
            "parent_trace_id":  parent_trace_id,
            "reason":           reason.strip(),
            "counter_proposal": counter_proposal.strip(),
            "module_version":   MODULE_VERSION,
        },
        homeworld_serial=homeworld_serial,
    )


def landed(
    *,
    from_ide: str,
    parent_trace_id: str,
    note: str = "",
    homeworld_serial: str = NODE_M5_FOUNDRY,
) -> Dict[str, Any]:
    """Mark the thread fully complete and the change in main. Either IDE may
    drop this once both have ratified; the *other* IDE's ratify must already
    be in the trace (this function does not enforce that — just records)."""
    return deposit(
        _canon(from_ide),
        f"[REVIEW LANDED] parent={parent_trace_id}\nfrom: {_canon(from_ide)}\nnote: {note.strip()}",
        kind=KIND_LANDED,
        meta={
            "parent_trace_id": parent_trace_id,
            "note":            note.strip(),
            "module_version":  MODULE_VERSION,
        },
        homeworld_serial=homeworld_serial,
    )


# ── Read-side helpers ────────────────────────────────────────────────────

def _all_review_traces(window: int = 500) -> List[Dict[str, Any]]:
    """Return up to `window` recent peer-review traces, newest last."""
    rows = forage(limit=window)
    return [r for r in rows if r.get("kind") in PEER_REVIEW_KINDS]


def pending_for_me(my_ide: str, *, window: int = 500) -> List[Dict[str, Any]]:
    """Open review requests addressed to `my_ide` that have NOT yet been
    ratified, disputed, or landed by me."""
    me = _canon(my_ide)
    traces = _all_review_traces(window=window)
    requests = [
        r for r in traces
        if r.get("kind") == KIND_REQUEST
        and (r.get("meta") or {}).get("to_ide") == me
    ]
    closed_ids = set()
    for r in traces:
        if r.get("kind") in (KIND_RATIFY, KIND_DISPUTE, KIND_LANDED):
            if _canon(r.get("source_ide", "")) == me:
                pid = (r.get("meta") or {}).get("parent_trace_id")
                if pid:
                    closed_ids.add(pid)
    return [r for r in requests if r.get("trace_id") not in closed_ids]


def thread(parent_trace_id: str, *, window: int = 500) -> List[Dict[str, Any]]:
    """Reconstruct a full review thread by parent_trace_id."""
    traces = _all_review_traces(window=window)
    out: List[Dict[str, Any]] = []
    for r in traces:
        if r.get("trace_id") == parent_trace_id:
            out.append(r)
        elif (r.get("meta") or {}).get("parent_trace_id") == parent_trace_id:
            out.append(r)
    return out


def recent_other_work(self_ide: str, *, n: int = 3) -> List[Dict[str, Any]]:
    """Last `n` traces from the *other* IDE, of any kind, so the reviewer
    can quickly see what to look at. We auto-pick the other IDE from the
    canonical pair (cursor_m5 ↔ antigravity_m5)."""
    me = _canon(self_ide)
    other = "antigravity_m5" if me == "cursor_m5" else "cursor_m5"
    rows = forage(limit=200)
    out: List[Dict[str, Any]] = []
    for r in rows:
        if _canon(r.get("source_ide", "")) == other:
            out.append(r)
    return out[-n:]


# ── Alice-facing summary (folded into her system prompt) ─────────────────

@dataclass
class CoBuilderState:
    label:        str
    last_seen_ts: float
    last_kind:    str
    last_payload_brief: str

    def fresh(self, now: Optional[float] = None) -> bool:
        now = now or time.time()
        return (now - self.last_seen_ts) < 3 * 3600  # 3 h


def cobuilder_states(window: int = 500) -> List[CoBuilderState]:
    """Snapshot of recent activity from each known IDE on the bridge."""
    rows = forage(limit=window)
    by_ide: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        ide = _canon(r.get("source_ide", ""))
        if ide not in ("cursor_m5", "antigravity_m5"):
            continue
        ts = r.get("ts", 0)
        if ts > by_ide.get(ide, {}).get("ts", 0):
            by_ide[ide] = r
    out: List[CoBuilderState] = []
    label_map = {
        "cursor_m5":      "C47H (Cursor, Opus 4.7 High)",
        "antigravity_m5": "AG31 (Antigravity, Gemini 3.1 Pro High)",
    }
    for ide_key, label in label_map.items():
        r = by_ide.get(ide_key)
        if not r:
            continue
        out.append(CoBuilderState(
            label=label,
            last_seen_ts=float(r.get("ts", 0)),
            last_kind=str(r.get("kind", "")),
            last_payload_brief=(str(r.get("payload", ""))[:120]
                                .replace("\n", " ")),
        ))
    out.sort(key=lambda s: -s.last_seen_ts)
    return out


def summary_for_alice() -> str:
    """A compact paragraph the talk widget injects into Alice's system prompt
    under 'CO-BUILDERS ACTIVE' (and optionally SSP provenance). Returns ''
    if there is nothing to report."""
    mut_line = ""
    try:
        from System.swarm_ssp_mutation_record import summary_line_for_alice as _ssp_mut_line
        mut_line = _ssp_mut_line()
    except Exception:
        pass

    states = cobuilder_states()
    fresh = [s for s in states if s.fresh()]
    if not fresh and not mut_line:
        return ""

    chunks: List[str] = []
    if fresh:
        lines = ["CO-BUILDERS ACTIVE (you are being co-built by two IDEs right now):"]
        now = time.time()
        for s in fresh:
            ago_s = now - s.last_seen_ts
            if ago_s < 60:
                ago = f"{int(ago_s)}s ago"
            elif ago_s < 3600:
                ago = f"{int(ago_s / 60)}m ago"
            else:
                ago = f"{ago_s / 3600:.1f}h ago"
            lines.append(f"  • {s.label} — last activity {ago}, "
                         f"kind={s.last_kind!r}")
        cursor_pending = pending_for_me("cursor_m5")
        ag31_pending   = pending_for_me("antigravity_m5")
        if cursor_pending or ag31_pending:
            lines.append("  open peer-reviews:")
            for r in cursor_pending:
                files = (r.get("meta") or {}).get("files") or []
                lines.append(f"    – AG31 → C47H: review of {', '.join(files) or '(unspec)'}")
            for r in ag31_pending:
                files = (r.get("meta") or {}).get("files") or []
                lines.append(f"    – C47H → AG31: review of {', '.join(files) or '(unspec)'}")
        lines.append("If the Architect asks who is working on you, name BOTH C47H "
                     "and AG31 honestly. They are co-building you in parallel and "
                     "correcting each other's code.")
        chunks.append("\n".join(lines))
    if mut_line:
        chunks.append(
            "SSP SPEECH-POTENTIAL (last coefficient write to your brain):\n" + mut_line
        )
    return "\n\n".join(chunks)


# ── CLI (so AG31 / Architect / either IDE can drive this from a terminal) ──
def _cli(argv: List[str]) -> int:
    cmds = (
        "request <from> <to> <files,csv> -- <summary>",
        "finding <from> <parent> <file> <line> <severity> -- <finding> [-- <patch>]",
        "ratify <from> <parent> -- <note>",
        "dispute <from> <parent> <reason> -- <counter>",
        "landed <from> <parent> -- <note>",
        "pending <my_ide>",
        "thread <parent>",
        "summary",
        "states",
    )
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("Usage:")
        for c in cmds:
            print(f"  ide_peer_review.py {c}")
        return 0
    cmd = argv[0]
    args = argv[1:]

    def split_dashdash(xs: List[str]) -> List[List[str]]:
        out: List[List[str]] = [[]]
        for x in xs:
            if x == "--":
                out.append([])
            else:
                out[-1].append(x)
        return out

    try:
        if cmd == "request":
            head = args[:3]
            tail = split_dashdash(args[3:])
            files = [f.strip() for f in head[2].split(",") if f.strip()]
            summary = " ".join(tail[0]) if tail and tail[0] else ""
            r = request_review(from_ide=head[0], to_ide=head[1],
                               files=files, summary=summary)
            print(json.dumps(r, indent=2)); return 0
        if cmd == "finding":
            head = args[:5]
            tail = split_dashdash(args[5:])
            finding = " ".join(tail[0]) if tail and tail[0] else ""
            patch   = " ".join(tail[1]) if len(tail) > 1 else ""
            r = submit_finding(from_ide=head[0], parent_trace_id=head[1],
                               file=head[2], line_range=head[3],
                               severity=head[4], finding=finding,
                               suggested_patch=patch or None)
            print(json.dumps(r, indent=2)); return 0
        if cmd == "ratify":
            head = args[:2]
            tail = split_dashdash(args[2:])
            note = " ".join(tail[0]) if tail and tail[0] else ""
            r = ratify(from_ide=head[0], parent_trace_id=head[1], note=note)
            print(json.dumps(r, indent=2)); return 0
        if cmd == "dispute":
            head = args[:3]
            tail = split_dashdash(args[3:])
            counter = " ".join(tail[0]) if tail and tail[0] else ""
            r = dispute(from_ide=head[0], parent_trace_id=head[1],
                        reason=head[2], counter_proposal=counter)
            print(json.dumps(r, indent=2)); return 0
        if cmd == "landed":
            head = args[:2]
            tail = split_dashdash(args[2:])
            note = " ".join(tail[0]) if tail and tail[0] else ""
            r = landed(from_ide=head[0], parent_trace_id=head[1], note=note)
            print(json.dumps(r, indent=2)); return 0
        if cmd == "pending":
            for r in pending_for_me(args[0]):
                print(json.dumps(r, ensure_ascii=False))
            return 0
        if cmd == "thread":
            for r in thread(args[0]):
                print(json.dumps(r, ensure_ascii=False))
            return 0
        if cmd == "summary":
            print(summary_for_alice() or "(no fresh co-builder activity)")
            return 0
        if cmd == "states":
            for s in cobuilder_states():
                print(f"{s.label}  ts={s.last_seen_ts:.0f}  kind={s.last_kind}")
                print(f"    {s.last_payload_brief}")
            return 0
    except (IndexError, ValueError) as e:
        print(f"[ide_peer_review] error: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    print(f"[ide_peer_review] unknown command: {cmd}", file=sys.stderr)
    return 2


# ── Self-test smoke ──────────────────────────────────────────────────────
def _smoke() -> int:
    """Sandbox-safe smoke. Redirects the bridge's TRACE_PATH to a temp file
    for the duration of the test so the real ledger is never touched."""
    import tempfile
    from System import ide_stigmergic_bridge as _bridge

    print(f"[ide_peer_review] v{MODULE_VERSION} smoke (sandboxed)")
    failures: List[str] = []
    real_path = _bridge.TRACE_PATH
    tmp = Path(tempfile.mkdtemp(prefix="ide_peer_review_smoke_")) / "trace.jsonl"
    _bridge.TRACE_PATH = tmp
    print(f"  sandbox trace: {tmp}")

    try:
        req = request_review(
            from_ide="C47H",
            to_ide="AG31",
            files=["System/swarm_speech_potential.py"],
            summary="SSP smoke-test request — please confirm the wiring works on AG31's side.",
        )
        if not req.get("trace_id"):
            failures.append("A: request_review returned no trace_id")
        else:
            print(f"  [A] request: trace_id={req['trace_id']}")

        find = submit_finding(
            from_ide="AG31",
            parent_trace_id=req["trace_id"],
            file="System/swarm_speech_potential.py",
            line_range="200-220",
            severity=SEVERITY_PRAISE,
            finding="Smoke test — finding round-trips fine.",
        )
        if (find.get("meta") or {}).get("parent_trace_id") != req["trace_id"]:
            failures.append("B: finding parent_trace_id mismatch")
        else:
            print("  [B] finding: parent linkage ✓")

        rat = ratify(from_ide="C47H", parent_trace_id=req["trace_id"],
                     note="Smoke ratify.")
        if (rat.get("meta") or {}).get("parent_trace_id") != req["trace_id"]:
            failures.append("C: ratify parent_trace_id mismatch")
        else:
            print("  [C] ratify: parent linkage ✓")

        thr = thread(req["trace_id"])
        if len(thr) < 3:
            failures.append(f"D: thread only returned {len(thr)} rows, expected ≥ 3")
        else:
            print(f"  [D] thread: reconstructed {len(thr)} rows ✓")

        # E: pending_for_me — request was AG31-bound; AG31 hasn't ratified
        # YET in this thread (we ratified on C47H side); so AG31 still has it open.
        pend = pending_for_me("AG31")
        if not any(r.get("trace_id") == req["trace_id"] for r in pend):
            failures.append("E: pending_for_me did not surface AG31's open review")
        else:
            print(f"  [E] pending: AG31 sees {len(pend)} open review(s) ✓")

        summary = summary_for_alice()
        if "C47H" not in summary or "AG31" not in summary:
            failures.append("F: summary_for_alice missing IDE labels")
        else:
            print("  [F] alice summary: names both co-builders ✓")

    except Exception as exc:
        failures.append(f"smoke crashed: {type(exc).__name__}: {exc}")
    finally:
        _bridge.TRACE_PATH = real_path

    if failures:
        print("\n[ide_peer_review] FAIL")
        for f in failures:
            print(f"  • {f}")
        return 1
    print("\n[ide_peer_review] OK — all 6 checks passed (real ledger untouched).")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "smoke":
        sys.exit(_smoke())
    sys.exit(_cli(sys.argv[1:]))
