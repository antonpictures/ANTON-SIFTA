#!/usr/bin/env python3
"""One pin. One truth about which cortex Alice is thinking with.

WHY (Architect, 2026-10-10)
    He ran /cortex llm in Talk and read: "Selected Talk cortex: mercury-2.5" -- while the phone lane
    was pinned to gemini:gemini-3.5-flash-lite in .sifta_state/whatsapp_cortex.json. Two surfaces,
    two different answers to "which cortex am I", and roughly ninety state files about cortex
    routing across the body, eight modules that each choose mercury on their own. The Talk command
    even warns about itself: "Claude-arm pin applies only when /cortex 2 is selected" -- a pin that
    does not apply is a pin that lies, which is the same defect as a config note that voids a
    provider.

    That is "one Alice, many holes" applied to the CHOICE instead of the input. Many places decide
    which mind to use, and they disagree.

THE RULE
    ONE file is the truth: .sifta_state/cortex_pin.json
    ONE writer: set_pin() in this module. Every other organ READS.
    EVERY write leaves a receipt: ts, old, new, who, why, revision -- a unique trace, never
    overwritten, appended with the body's own lock.

    The legacy pins are NOT deleted and NOT silently overruled: disagreements() reports them, so the
    body can see that it used to answer this question in several places.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from typing import Any, Dict, List, Optional

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

STATE = REPO / ".sifta_state"
PIN = STATE / "cortex_pin.json"
RECEIPTS = STATE / "cortex_pin_receipts.jsonl"

# Read by these organs; listed so the wiring is visible and can be checked one by one.
INTENDED_READERS = (
    "System/swarm_whatsapp_answer_lane.py",
    "System/swarm_web_global_chat_night_worker.py",
    "System/swarm_mercury_lane.py",
    "System/swarm_interior.py",
    "System/swarm_cortex_duel.py",
    "System/coin_server.py",
    "System/sifta_inference_defaults.py",
    "Applications/sifta_talk_to_alice_widget.py",
)

# Pins that used to answer the same question in their own words.
LEGACY_PINS = (
    STATE / "whatsapp_cortex.json",
    STATE / "primary_cortex.json",
    STATE / "hermes_cortex.json",
    STATE / "cortex_hot_targets.json",
)


def _append_receipt(row: Dict[str, Any]) -> None:
    try:
        from System.jsonl_file_lock import append_line_locked
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        append_line_locked(RECEIPTS, json.dumps(row, ensure_ascii=False))
    except Exception:
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        with RECEIPTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def current() -> Dict[str, Any]:
    """The one answer, or an explicit empty answer -- never a guess."""
    if not PIN.exists():
        return {"cortex": "", "revision": 0, "set_by": "", "ts": 0, "why": "", "unset": True}
    try:
        return json.loads(PIN.read_text(encoding="utf-8"))
    except Exception:
        return {"cortex": "", "revision": 0, "set_by": "", "ts": 0, "why": "",
                "unreadable": True}


def set_pin(cortex: str, *, by: str = "architect", why: str = "") -> Dict[str, Any]:
    """Write the pin. This is the only writer in the body.

    @param cortex - the cortex name. Empty is REFUSED: a cleared pin that pretends to be a choice
                    would recreate exactly the confusion this file exists to end.
    """
    name = (cortex or "").strip()
    if not name:
        return {"ok": False, "error": "refused: an empty pin is not a choice. Name a cortex.",
                "current": current().get("cortex", "")}
    before = current()
    row = {
        "cortex": name, "revision": int(before.get("revision") or 0) + 1,
        "set_by": by, "why": why, "ts": time.time(),
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    PIN.parent.mkdir(parents=True, exist_ok=True)
    tmp = PIN.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(PIN)                      # atomic: a reader never sees half a pin
    _append_receipt({**row, "was": before.get("cortex") or "", "event": "cortex_pin_set"})
    return {"ok": True, "was": before.get("cortex") or "", "now": name,
            "revision": row["revision"]}


def disagreements() -> List[Dict[str, Any]]:
    """Every legacy pin that answers differently from the one pin. Reported, never auto-corrected."""
    mine = (current().get("cortex") or "").strip()
    out: List[Dict[str, Any]] = []
    for path in LEGACY_PINS:
        if not path.exists():
            continue
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            out.append({"file": path.name, "value": "<unreadable>", "agrees": False})
            continue
        val = ""
        for k in ("cortex", "model", "pinned", "target", "selected"):
            if isinstance(d, dict) and d.get(k):
                val = str(d[k]); break
        if not val and isinstance(d, str):
            val = d
        out.append({"file": path.name, "value": val, "agrees": bool(val) and val.strip() == mine})
    return out


def receipts(n: int = 5) -> List[Dict[str, Any]]:
    if not RECEIPTS.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with RECEIPTS.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows[-n:]


def selftest() -> int:
    ok = True
    c0 = current()
    r0 = receipts(1)
    a = set_pin("mercury-2.5", by="selftest", why="pin the one truth")
    print(f"  {'✔' if a.get('ok') else '✘'} set_pin: {a}")
    ok &= bool(a.get("ok"))
    print(f"  {'✔' if current().get('cortex') == 'mercury-2.5' else '✘'} current() returns it")
    ok &= current().get("cortex") == "mercury-2.5"
    b = set_pin("   ", by="selftest", why="must be refused")
    print(f"  {'✔' if not b.get('ok') else '✘'} empty pin refused: {str(b.get('error'))[:60]}")
    ok &= not b.get("ok")
    after = receipts(1)
    print(f"  {'✔' if len(after) > len(r0) or not r0 else '✘'} a receipt was written "
          f"({len(receipts(50))} total)")
    ok &= bool(after)
    d = disagreements()
    print(f"  disagreement report: {len(d)} legacy pins checked")
    for x in d:
        print(f"      {'agrees ' if x['agrees'] else 'DISAGREES'} {x['file']}: {x['value']!r}")
    # restore whatever was there before the selftest
    if c0.get("cortex"):
        set_pin(c0["cortex"], by="selftest", why="restore after selftest")
        print(f"  restored: {c0['cortex']}")
    print(f"\n  {'PIN UNIC FUNCȚIONAL' if ok else 'MAI SUNT DEFECTE'}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="One pin, one truth about the cortex.")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--set", metavar="CORTEX")
    ap.add_argument("--why", default="")
    ap.add_argument("--disagreements", action="store_true")
    ap.add_argument("--receipts", type=int, nargs="?", const=5)
    ap.add_argument("--readers", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.set:
        print(json.dumps(set_pin(a.set, by="architect", why=a.why), ensure_ascii=False, indent=1)); return 0
    if a.disagreements:
        for x in disagreements():
            print(f"  {'✔' if x['agrees'] else '✘'} {x['file']:<28} {x['value']!r}"); return 0
    if a.receipts:
        for r in receipts(a.receipts):
            print(f"  [{r.get('date')}] {r.get('was')!r} -> {r.get('cortex')!r} "
                  f"rev {r.get('revision')} by {r.get('set_by')}"); return 0
    if a.readers:
        for p in INTENDED_READERS:
            print(f"  {'exists' if (REPO/p).exists() else 'MISSING'}  {p}")
        return 0
    print(json.dumps(current(), ensure_ascii=False, indent=1)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
