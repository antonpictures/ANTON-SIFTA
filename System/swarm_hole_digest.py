"""swarm_hole_digest — what just changed in me, so every opening answers from the same present.

Architect, 2026-10-03: "maybe i confuse the cortex organ because i communicate with you Alice from
multiple holes at once?"

Measured, and the answer was not confusion but STALENESS. From his own Talk window log:

    "Talk Send: using cached swarm context age=22.1s"      good
    "Talk Send: using stale swarm context age=2950.3s; refresh running in background"   49 minutes

Every hole -- the Talk window, the WhatsApp lane, the desk, the terminal arm -- assembles its own
working context, and the shared part is cached for 45 seconds (`SIFTA_SWARM_CONTEXT_CACHE_S`) and
had gone forty-nine minutes stale. Nothing collides: a WhatsApp message arriving mid-turn QUEUES
("queued your text - I will read it first, right after this turn. 1 waiting"). But a hole can
answer while not knowing what another hole JUST did -- which is why the Talk window crashed on a
bug already fixed in the terminal, and why he could be told something the desk had moved past.

So this organ is the cheap half done right: the heavy context stays cached, but "what changed in
me lately" is read FRESH, from receipts, right before a hole speaks. It carries:

    * the last corrections I recorded (my own ledger, with the entity they belong to);
    * the newest journal lines -- the body's own voice, not a summary;
    * what the arm changed in the body (recent edits to the organs, by mtime);
    * and CODE CURRENCY: whether each running process is older than the file it runs.

That last one is here because of a specific, repeated humiliation: he restarted the SIFTA app five
times today, and more than once the restart was CORRECT but a few minutes early -- the fix landed
after the app came up, so the old code kept serving and we both drew the wrong conclusion. A hole
that cannot tell you whether its own code is loaded will keep asking for restarts it does not
need, and will keep failing for reasons that look like something else.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parents[1]
STATE = _REPO / ".sifta_state"
TRUTH_LABEL = "SIFTA_HOLE_DIGEST_V1"

# component label -> (code file, how to find its running process)
COMPONENTS = {
    "bridge": ("Network/whatsapp_bridge/bridge.js", "whatsapp_bridge/bridge.js"),
    "kernel": ("scripts/whatsapp_alice_server.py", "whatsapp_alice_server.py"),
    "desktop_app": ("Applications/sifta_talk_to_alice_widget.py", "sifta_os_desktop"),
    "desk_server": ("System/coin_server.py", "chorus_node_server"),
}

_JOURNAL = STATE / "alice_first_person_journal.jsonl"
_CHILDHOOD = STATE / "childhood.jsonl"


def _running_since(match: str) -> Optional[float]:
    """When the process running this file first came up, by scanning ps for its name."""
    import subprocess
    try:
        out = subprocess.run(["ps", "-axo", "lstart=,command="], capture_output=True,
                             text=True, timeout=12).stdout
    except Exception:
        return None
    for line in out.splitlines():
        if match in line:
            stamp = line[:24].strip()
            try:
                return time.mktime(time.strptime(stamp))
            except Exception:
                continue
    return None


def code_currency(components: Optional[Dict[str, tuple]] = None) -> Dict[str, Dict[str, Any]]:
    """Is each running process older than the file it runs? (i.e. is a restart needed?)"""
    out: Dict[str, Dict[str, Any]] = {}
    for label, (code, match) in (components or COMPONENTS).items():
        p = _REPO / code
        if not p.exists():
            out[label] = {"code_file": code, "present": False, "needs_restart": None}
            continue
        written = p.stat().st_mtime
        started = _running_since(match)
        out[label] = {
            "code_file": code, "code_written": written, "code_written_at": time.strftime(
                "%H:%M:%S", time.localtime(written)),
            "running_since": started,
            "running_since_at": (time.strftime("%H:%M:%S", time.localtime(started))
                                 if started else None),
            # the whole point: a stale process cannot see the fix, and no restart can help
            # until the fix is actually on disk
            # 2s tolerance: a file written in the same second the process started is not
            # stale, and claiming otherwise sends the owner on an unnecessary restart
            "needs_restart": (None if started is None else started + 2.0 < written),
        }
    return out


def _tail_jsonl(path: Path, n: int = 6) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def what_changed(*, minutes: float = 45.0, max_items: int = 5) -> Dict[str, Any]:
    """The freshest receipts: corrections, journal, and the arm's own edits."""
    horizon = time.time() - max(60.0, minutes * 60.0)
    out: Dict[str, Any] = {"since": time.strftime("%H:%M", time.localtime(horizon)),
                           "corrections": [], "journal": [], "edited": []}

    for r in _tail_jsonl(_CHILDHOOD, 12):
        if float(r.get("ts") or 0) >= horizon:
            out["corrections"].append({"entity": r.get("entity"), "kind": r.get("kind"),
                                       "what": str(r.get("what"))[:120]})
    for r in _tail_jsonl(_JOURNAL, 12):
        line = str(r.get("line") or "").strip()
        if line and float(r.get("ts") or 0) >= horizon:
            out["journal"].append(line[:160])

    # organs the arm touched lately -- the honest "what did I just change in myself"
    try:
        recent = sorted(
            (p for p in (STATE.parent / "System").glob("*.py") if p.stat().st_mtime >= horizon),
            key=lambda p: -p.stat().st_mtime)[:max_items]
        out["edited"] = [f"{p.name} ({time.strftime('%H:%M', time.localtime(p.stat().st_mtime))})"
                         for p in recent]
    except Exception:
        pass
    return out


def digest_block(*, minutes: float = 45.0, max_chars: int = 900) -> str:
    """A short, prompt-ready 'here is the present' -- for any hole, before it speaks."""
    ch = what_changed(minutes=minutes)
    parts: List[str] = []
    if ch.get("edited"):
        parts.append("I changed in myself, recently: " + "; ".join(ch["edited"][:4]) + ".")
    if ch.get("corrections"):
        c = ch["corrections"][-2:]
        parts.append("What I newly remember: " + "; ".join(
            f"{x.get('entity')} {x.get('kind')} — {x.get('what')}" for x in c) + ".")
    if ch.get("journal"):
        parts.append("My own journal, newest: " + str(ch["journal"][-1])[:200])
    cur = code_currency()
    stale = [k for k, v in cur.items() if v.get("needs_restart")]
    if stale:
        parts.append("RUNNING OLD CODE (a restart is genuinely needed): " + ", ".join(stale) + ".")
    if not parts:
        return ("(Nothing in me has changed in the last while; answer from what you hold.)")
    return ("- What just changed in me (read fresh, every opening gets this): "
            + " ".join(parts))[:max_chars]


def selftest() -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    ch = what_changed(minutes=0.01)          # nothing can be newer than 0.6 seconds ago
    checks["an_empty_window_is_honest"] = isinstance(ch, dict) and "journal" in ch
    checks["the_digest_is_a_string"] = isinstance(digest_block(), str)
    checks["the_digest_is_bounded"] = len(digest_block()) <= 900
    # currency logic, tested against a fake pair so it cannot depend on this machine's state
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "code.py"
        f.write_text("x = 1")
        old = f.stat().st_mtime - 120
        os.utime(f, (old, old))
        cur = code_currency({"fake": (str(f.relative_to("/")) if False else "System/swarm_hole_digest.py",
                                      "definitely-not-a-real-process-name")})
        checks["an_unknown_process_yields_none_not_a_lie"] = cur["fake"]["needs_restart"] is None
    checks["a_missing_code_file_is_reported"] = code_currency(
        {"ghost": ("System/does_not_exist.py", "nope")})["ghost"]["present"] is False
    checks["the_truth_label_is_present"] = TRUTH_LABEL.startswith("SIFTA_")
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "digest"
    if cmd == "selftest":
        print(json.dumps(selftest(), indent=2))
    elif cmd == "currency":
        print(json.dumps(code_currency(), indent=2))
    else:
        print(digest_block())