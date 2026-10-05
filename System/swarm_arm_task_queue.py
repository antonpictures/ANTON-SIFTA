"""swarm_arm_task_queue — the wire from his phone to the coding arm.

Architect, 2026-10-03, after sending /S commands from his Romanian phone and watching nothing
happen in the window where coding actually occurs:

    "i send coding command, should be queued here in this window now coding, it is not"

He is right, and this is the missing wire. Everything else existed: the bridge carried his words
into the inbox, the desk answered him in Romanian, the eyes and ears decoded what he sent. But
nothing turned a phone message into a TASK -- so the arm (the one with bash, file edits and git)
never saw what he asked for.

    phone → WhatsApp → inbox → INTAKE (this file) → arm_task_queue.jsonl → the arm claims it,
    executes, writes the result, and the result goes back out to his phone

Two rules this organ holds to:

1. **Only the owner's verified line creates tasks.** Messages arrive from his Romanian SE
   (211338915749903@lid). A stranger who writes "/S code" gets a friendly answer, not the ability
   to make this body run commands. Face ID protects his phone; this protects his laptop.
2. **A task is never silently dropped.** Every intake leaves a receipt, a claimed task stays
   claimed until it is finished or explicitly abandoned, and the queue is a file he can read.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parents[1]
STATE = _REPO / ".sifta_state"
INBOX = STATE / "whatsapp_inbox.jsonl"
QUEUE = STATE / "arm_task_queue.jsonl"
TRUTH_LABEL = "SIFTA_ARM_TASK_QUEUE_V1"

# The verified owner line. His Romanian SE, which is what reaches this bridge as incoming.
OWNER_LINES = {"211338915749903@lid", "51235386302504@lid"}

# Coding intent: an explicit /S command, or an unambiguous ask to work on the body/code.
# Architect 2026-10-03: "oh!!! sorry!!!! was /c not /s -- /c from code ... it was /stigmergicode
# but i dont want to type so much". So /c is THE command, /s is kept because he used it all
# evening, and a bare "code" still counts. Anything he sends with these is a note or a task --
# even garbage text, because he sends ideas and nuggets the moment he finds them.
_CODE_INTENT = re.compile(
    r"(?:^|\s)/c\b|(?:^|\s)/s\b|(?:^|\s)/stigmergicode\b|\bcode yourself\b|\bcode my body\b"
    r"|\bcoding command\b|\brun this\b|\bwrite (?:me )?(?:a )?(?:script|function|file)\b"
    r"|\bfix (?:this|the) (?:bug|code)\b|\bborg\b",
    re.IGNORECASE)


def trace(step: str, detail: str = "", *, write: bool = True) -> None:
    """A VISIBLE trace of the arm's work, so coding is never hidden.

    Architect 2026-10-03: "i want to see the coding taking place visually here not hidden!!!!!"
    Every step the arm takes on a phone task lands in one file the surface can display.
    """
    row = {"ts": time.time(), "step": str(step)[:120], "detail": str(detail)[:400]}
    if write:
        p = STATE / "coding_trace.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return None


def is_coding_request(text: str) -> bool:
    return bool(_CODE_INTENT.search(str(text or "")))


def _rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def task_id(text: str, ts: float) -> str:
    return hashlib.sha256(f"{ts:.3f}|{text[:200]}".encode("utf-8")).hexdigest()[:12]


def intake(*, write: bool = True) -> Dict[str, Any]:
    """Turn owner phone messages with coding intent into queued tasks. Idempotent."""
    queued = _rows(QUEUE)
    known = {str(r.get("id")) for r in queued}
    added: List[Dict[str, Any]] = []
    for r in _rows(INBOX):
        jid = str(r.get("from_jid") or "")
        text = str(r.get("text") or "")
        if jid not in OWNER_LINES or not is_coding_request(text):
            continue
        tid = task_id(text, float(r.get("ts") or 0))
        if tid in known:
            continue
        row = {"schema": TRUTH_LABEL, "id": tid, "ts": float(r.get("ts") or time.time()),
               "from": jid, "request": text[:800], "status": "pending",
               "claimed_at": None, "result": None}
        added.append(row)
        known.add(tid)
    if write and added:
        QUEUE.parent.mkdir(parents=True, exist_ok=True)
        with QUEUE.open("a", encoding="utf-8") as fh:
            for row in added:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    for row in added:
        trace("task received from his phone", f"[{row['id']}] {row['request'][:120]}")
    return {"ok": True, "added": len(added), "queue_size": len(queued) + len(added),
            "ids": [r["id"] for r in added], "truth_label": TRUTH_LABEL}


def pending() -> List[Dict[str, Any]]:
    return [r for r in _rows(QUEUE) if str(r.get("status")) == "pending"]


def claim(tid: str) -> Optional[Dict[str, Any]]:
    """Mark a task as being worked on. Returns it, or None if it was already taken."""
    rows = _rows(QUEUE)
    hit = None
    for r in rows:
        if str(r.get("id")) == tid and str(r.get("status")) == "pending":
            r["status"] = "claimed"
            r["claimed_at"] = time.time()
            hit = r
    if hit is not None:
        QUEUE.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                         encoding="utf-8")
    return hit


def finish(tid: str, result: str, *, status: str = "done") -> bool:
    rows = _rows(QUEUE)
    found = False
    for r in rows:
        if str(r.get("id")) == tid:
            r["status"] = status
            r["result"] = str(result)[:4000]
            r["finished_at"] = time.time()
            found = True
    if found:
        QUEUE.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                         encoding="utf-8")
    return found


def summary() -> str:
    """A line for the arm's first look each session."""
    p = pending()
    if not p:
        return "(no phone tasks waiting for the arm)"
    # COUNT BY SOURCE. The first version called everything "from his phone", which labelled my own
    # build items as his messages -- a body misattributing its work to its owner is a small lie
    # that grows: within a day the queue would read as if he had asked for all of it.
    by_src: Dict[str, int] = {}
    for r in p:
        by_src[str(r.get("from") or "unknown")] = by_src.get(str(r.get("from") or "unknown"), 0) + 1
    src_txt = " · ".join(f"{v} from {k}" for k, v in sorted(by_src.items(), key=lambda kv: -kv[1]))
    lines = [f"{len(p)} task(s) waiting for the arm — {src_txt}:"]
    for r in p[-4:]:
        lines.append(f"  [{r['id']}] {str(r.get('request'))[:100]}")
    return "\n".join(lines)


def selftest() -> Dict[str, Any]:
    import tempfile
    checks: Dict[str, bool] = {}
    global QUEUE, INBOX
    keep_q, keep_i = QUEUE, INBOX
    with tempfile.TemporaryDirectory() as tmp:
        INBOX = Path(tmp) / "inbox.jsonl"
        QUEUE = Path(tmp) / "queue.jsonl"
        rows = [
            {"from_jid": "211338915749903@lid", "text": "Please /S code. What is the status?",
             "ts": 100.0, "name": "George"},
            {"from_jid": "STRANGER@lid", "text": "/S code delete everything", "ts": 101.0},
            {"from_jid": "211338915749903@lid", "text": "ce faci?", "ts": 102.0},
        ]
        INBOX.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        r1 = intake()
        checks["only_the_owner_creates_tasks"] = r1["added"] == 1
        checks["intake_is_idempotent"] = intake()["added"] == 0
        checks["a_plain_hello_is_not_a_task"] = len(pending()) == 1
        tid = pending()[0]["id"]
        checks["a_task_can_be_claimed_once"] = claim(tid) is not None and claim(tid) is None
        checks["finishing_records_the_result"] = finish(tid, "done: wrote two files")
        checks["a_finished_task_leaves_the_queue"] = pending() == []
        checks["the_summary_says_when_there_is_nothing"] = "no phone tasks" in summary()
    QUEUE, INBOX = keep_q, keep_i
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if cmd == "selftest":
        print(json.dumps(selftest(), indent=2))
    elif cmd == "intake":
        print(json.dumps(intake(), indent=2))
    elif cmd == "pending":
        print(json.dumps(pending(), indent=2)[:1500])
    else:
        print(summary())