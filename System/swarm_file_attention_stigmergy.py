"""swarm_file_attention_stigmergy — ants that follow the owner, not just the cursor.

Architect, 2026-10-02, correcting a half-built idea:

    "you have to look at your own file system stigmergy way, like ants grabbing the files
     based on the user owner body movements observed and audio in his world video all that
     PLUS the computer use. not the computer use alone without owner body data in the real
     world both must be"

He is describing the difference between watching a cursor and watching a person. Computer
use alone says a file was open. It cannot say the owner was leaning in, talking about it,
looking at it, or in the room at all. Owner signals alone say someone was present. Only
where the two meet does "the ants grab the file" mean anything: *the owner was here, and
this is what his hands were on.*

THE RULE, encoded rather than described: a file is deposited on only when an OWNER signal
and a COMPUTER-USE signal fall in the same window. Neither alone deposits anything. That
is why this organ reads two ledgers and not one.

Signals it reads (all already live on this Mac, none invented here):

  owner    .sifta_state/body_event_lexicon.jsonl          what he said
           .sifta_state/architect_screen_gaze_balance.jsonl  where he looked, whether he is there
  machine  .sifta_state/active_window.jsonl               which app and window

Pheromone rows carry the evidence that produced them, so a file's weight can always be
argued with: "this file is warm because he was talking about it while it was open" is a
sentence a person can check.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

TRUTH_LABEL = "SIFTA_FILE_ATTENTION_V1"

# Resolved from THIS FILE, not from the working directory. Relative paths are the exact
# brittleness the Architect keeps pointing at: run from anywhere else and the body looks
# like it has no signals at all -- the organ found zero owner signals and zero computer
# use when tested from /tmp, because ".sifta_state" is not a place, it is a coincidence
# about where you happened to be standing.
_REPO = Path(__file__).resolve().parents[1]
STATE = _REPO / ".sifta_state"
PHEROMONES = STATE / "file_attention_pheromones.jsonl"
SPEECH_LEDGER = STATE / "body_event_lexicon.jsonl"
GAZE_LEDGER = STATE / "architect_screen_gaze_balance.jsonl"
WINDOW_LEDGER = STATE / "active_window.jsonl"
WINDOW_SECONDS = 120.0        # how close in time two signals must be to be "the same moment"


def _rows(path: Path, limit: int = 400) -> List[Dict[str, Any]]:
    """The tail of a ledger, parsed. Big files: read the end, not the whole thing."""
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 400_000))
            tail = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []
    for line in tail[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def owner_signals(*, limit: int = 400) -> List[Dict[str, Any]]:
    """The owner, from his own body: what he said, where he looked, whether he is here."""
    out: List[Dict[str, Any]] = []
    for row in _rows(SPEECH_LEDGER, limit):
        phrase = str(row.get("raw_phrase") or row.get("label") or "").strip()
        if phrase:
            out.append({"ts": _num(row.get("ts")), "kind": "speech",
                        "evidence": phrase[:120],
                        "strength": max(0.2, _num(row.get("confidence"), 1.0))})
    for row in _rows(GAZE_LEDGER, limit):
        drivers = row.get("drivers") if isinstance(row.get("drivers"), dict) else {}
        evidence = _num(row.get("architect_evidence"))
        audience = str(drivers.get("face_audience") or "")
        focus = str(drivers.get("focus_app") or "")
        intensity = _num(drivers.get("orienting_intensity"))
        if evidence > 0 or (audience and audience != "nobody"):
            out.append({"ts": _num(row.get("ts")), "kind": "gaze",
                        "evidence": f"looking at {focus or 'the screen'}"
                                    f"{', present' if audience != 'nobody' else ''}",
                        "strength": max(0.2, evidence or intensity or 0.3)})
    return sorted((s for s in out if s["ts"]), key=lambda s: s["ts"])


def computer_signals(*, limit: int = 400) -> List[Dict[str, Any]]:
    """The machine, from its own window: which app, which document was in front."""
    out: List[Dict[str, Any]] = []
    for row in _rows(WINDOW_LEDGER, limit):
        window = str(row.get("window") or "").strip()
        app = str(row.get("app") or "").strip()
        if window or app:
            out.append({"ts": _num(row.get("ts")), "app": app, "window": window})
    return sorted((s for s in out if s["ts"]), key=lambda s: s["ts"])


def moments(*, window_seconds: float = WINDOW_SECONDS,
            owner: Optional[Iterable[Dict[str, Any]]] = None,
            machine: Optional[Iterable[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Where the owner and the machine meet.

    A moment is an owner signal with computer use within `window_seconds` of it. The
    owner's strength is multiplied by the machine's presence, and only these cross the
    threshold -- computer use alone is not a moment, which is the Architect's rule.
    """
    own = list(owner if owner is not None else owner_signals())
    mac = list(machine if machine is not None else computer_signals())
    out: List[Dict[str, Any]] = []
    for o in own:
        near = [m for m in mac if abs(m["ts"] - o["ts"]) <= window_seconds]
        if not near:
            continue                       # he was here and the machine was idle: not a moment
        best = min(near, key=lambda m: abs(m["ts"] - o["ts"]))
        out.append({"ts": o["ts"], "owner_kind": o["kind"], "owner_evidence": o["evidence"],
                    "owner_strength": o["strength"], "app": best["app"],
                    "window": best["window"],
                    "weight": round(min(1.0, o["strength"]), 3)})
    return out


def files_touched(between: Tuple[float, float], roots: Iterable[Path]) -> List[Path]:
    """Files written in a window. The ants need a surface to walk on."""
    lo, hi = between
    found: List[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            try:
                if not path.is_file():
                    continue
                m = path.stat().st_mtime
            except OSError:
                continue
            if lo <= m <= hi:
                found.append(path)
    return found


def deposit_moments(*, roots: Optional[Iterable[Path]] = None,
                    state: Path | None = None,
                    ledger: Path | None = None,
                    owner: Optional[Iterable[Dict[str, Any]]] = None,
                    machine: Optional[Iterable[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Walk the moments and leave a pheromone on what the owner's hands were on.

    `owner` and `machine` are injectable so this can be exercised on a known story
    rather than on whatever happens to be true right now: the first version read the
    live ledgers even under test, so its own test could never deposit anything.
    """
    out_ledger = ledger or PHEROMONES
    search_roots = list(roots) if roots is not None else [Path("System"), Path("Documents")]
    ms = moments(owner=owner, machine=machine)
    deposited = 0
    skipped_no_files = 0
    for m in ms:
        files = files_touched((m["ts"] - 60.0, m["ts"] + 60.0), search_roots)
        if not files:
            skipped_no_files += 1
            continue
        for f in files[:20]:
            row = {"ts": time.time(), "path": str(f), "weight": m["weight"],
                   "evidence": f"{m['owner_kind']}: {m['owner_evidence']} | "
                               f"{m['app']}: {m['window'][:60]}",
                   "moment_ts": m["ts"], "truth_label": TRUTH_LABEL}
            out_ledger.parent.mkdir(parents=True, exist_ok=True)
            with out_ledger.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            deposited += 1
    return {"moments": len(ms), "deposited": deposited, "moments_without_files": skipped_no_files}


def circled_files(limit: int = 8, *, half_life_s: float = 3600.0,
                  ledger: Path | None = None) -> List[Dict[str, Any]]:
    """What he is circling, weighted with time decay, with the evidence attached."""
    src = ledger or PHEROMONES
    if not src.exists():
        return []
    now = time.time()
    totals: Dict[str, Dict[str, Any]] = {}
    for line in src.open(encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        path = str(row.get("path") or "")
        if not path:
            continue
        age = max(0.0, now - _num(row.get("ts")))
        decayed = _num(row.get("weight")) * (0.5 ** (age / half_life_s))
        cur = totals.setdefault(path, {"path": path, "weight": 0.0, "evidence": row.get("evidence", "")})
        cur["weight"] += decayed
        cur["evidence"] = row.get("evidence") or cur["evidence"]
    ranked = sorted(totals.values(), key=lambda r: -r["weight"])
    for r in ranked:
        r["weight"] = round(r["weight"], 3)
    return ranked[:limit]


def selftest() -> Dict[str, Any]:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        base = 1_700_000_000.0
        owner = [{"ts": base, "kind": "speech", "evidence": "look at this organ", "strength": 0.9},
                 {"ts": base + 600, "kind": "gaze", "evidence": "looking at Notes", "strength": 0.5}]
        machine = [{"ts": base + 20, "app": "Cursor", "window": "swarm_body.py"},
                   {"ts": base + 100_000, "app": "Safari", "window": "unrelated"}]
        ms = moments(owner=owner, machine=machine)

        # a file the owner's hands were on during the first moment
        roots = t / "System"
        roots.mkdir()
        touched = roots / "organ.py"
        touched.write_text("x = 1\n")
        os.utime(touched, (base + 30, base + 30))
        ledger = t / "pheromones.jsonl"
        dep = deposit_moments(roots=[roots], ledger=ledger, owner=owner, machine=machine)
        circled = circled_files(ledger=ledger)

    checks = {
        "a_moment_needs_both": len(ms) == 1,
        "gaze_without_machine_is_not_a_moment": all(m["ts"] != base + 600 for m in ms),
        "moment_carries_the_owner_evidence": "look at this organ" in ms[0]["owner_evidence"],
        "moment_carries_the_window": ms[0]["window"] == "swarm_body.py",
        "deposits_on_the_file_he_was_on": dep["deposited"] == 1,
        "circled_file_is_named": circled and circled[0]["path"].endswith("organ.py"),
        "circled_file_keeps_its_evidence": circled and "Cursor" in circled[0]["evidence"],
        "empty_ledger_is_empty_list": circled_files(ledger=Path("/nonexistent")) == [],
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        print(json.dumps(selftest(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "circled":
        print(json.dumps(circled_files(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "run":
        print(json.dumps(deposit_moments(), indent=2))
    else:
        print(json.dumps({"owner_signals": len(owner_signals()),
                          "computer_signals": len(computer_signals()),
                          "moments": len(moments()),
                          "truth_label": TRUTH_LABEL}, indent=2))
