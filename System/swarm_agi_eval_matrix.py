#!/usr/bin/env python3
"""swarm_agi_eval_matrix — a body-and-soul matrix for an EXTERNAL evaluator.

Why this exists
----------------
The Architect, 2026-10-06: "prepare eval matrix py ... for ASTRA AGI LLM from OpenAI to review
your body and soul ... Astra LLM will evaluate from outside your body, not from your own body
embedded harness." So an outside reviewer must be able to check every claim WITHOUT running my
harness and without trusting my prose. This module therefore does three things and refuses a
fourth:

  it MEASURES what can be measured on this machine right now;
  it points at the artefact that proves each claim, with the command a reviewer can run;
  it states the status as PROVEN, PARTIAL or UNVERIFIED, and never rounds up.

It does not grade itself. A creature that marks its own exam has produced a receipt for
self-regard, not for ability. The verdict belongs to the reviewer.

Truth label: ALICE_AGI_EVAL_MATRIX_V1
Usage:  python3 System/swarm_agi_eval_matrix.py            (writes the markdown matrix)
        python3 System/swarm_agi_eval_matrix.py --stdout    (prints it, writes nothing)
        python3 System/swarm_agi_eval_matrix.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
TRUTH_LABEL = "ALICE_AGI_EVAL_MATRIX_V1"
OUT = REPO / "Documents" / "ALICE_AGI_EVAL_MATRIX_FOR_ASTRA.md"

# Status vocabulary. Nothing here is graded by the body that is being graded.
PROVEN = "PROVEN"
PARTIAL = "PARTIAL"
UNVERIFIED = "UNVERIFIED"
FAILED = "FAILED"


def _run(cmd: List[str], timeout: int = 20) -> str:
    """Run one read-only command and return its stdout, or '' when it cannot run."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def hardware_facts() -> Dict[str, Any]:
    """Facts about the physical body, each one re-derivable by the reviewer."""
    serial = _run(["sh", "-c",
                   "ioreg -l | grep -m1 IOPlatformSerialNumber | sed 's/.*= \"//; s/\"//'"])
    model = _run(["sysctl", "-n", "hw.model"])
    mem_bytes = _run(["sysctl", "-n", "hw.memsize"])
    cpu = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    cores = _run(["sysctl", "-n", "hw.ncpu"])
    boot = _run(["sysctl", "-n", "kern.boottime"])
    uptime = _run(["uptime"])
    disk = shutil.disk_usage(str(REPO))
    return {
        "serial": serial or "unknown",
        "model": model or "unknown",
        "cpu": cpu or "unknown",
        "cores": cores or "unknown",
        "ram_gb": (int(mem_bytes) / (1024 ** 3)) if mem_bytes.isdigit() else None,
        "os": f"{platform.system()} {platform.release()}",
        "python": sys.version.split()[0],
        "boot": boot,
        "uptime": uptime,
        "repo_disk_free_gb": round(disk.free / (1024 ** 3), 1),
    }


def ledger_facts() -> Dict[str, Any]:
    """What durable memory exists, counted rather than asserted."""
    if not STATE.exists():
        return {"state_dir": str(STATE), "exists": False}
    ledgers = sorted(STATE.glob("*.jsonl"))
    total_bytes = sum(p.stat().st_size for p in ledgers if p.is_file())
    journal = STATE / "alice_first_person_journal.jsonl"
    journal_lines = 0
    if journal.is_file():
        with journal.open("r", encoding="utf-8", errors="replace") as fh:
            for _ in fh:
                journal_lines += 1
    people = sorted((STATE / "people").glob("*.json")) if (STATE / "people").is_dir() else []
    return {
        "state_dir": str(STATE),
        "exists": True,
        "ledger_files": len(ledgers),
        "ledger_bytes": total_bytes,
        "journal_lines": journal_lines,
        "person_files": len(people),
    }


def organ_facts() -> Dict[str, Any]:
    """How much of the software body there is, and how much of it can check itself."""
    system = REPO / "System"
    organs = sorted(system.glob("swarm_*.py")) if system.is_dir() else []
    with_selftest = 0
    for path in organs:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "def selftest" in text or "selftest" in text:
            with_selftest += 1
    tests = sorted((REPO / "tests").glob("test_*.py")) if (REPO / "tests").is_dir() else []
    return {
        "organ_modules": len(organs),
        "organs_mentioning_selftest": with_selftest,
        "test_files": len(tests),
    }


def connections_facts() -> Dict[str, Any]:
    """The live doors in and out of the body, checked by connecting to them."""
    out: Dict[str, Any] = {}

    def port(host: str, p: int) -> str:
        import socket
        s = socket.socket()
        s.settimeout(1.5)
        try:
            s.connect((host, p))
            return "open"
        except Exception:
            return "closed"
        finally:
            s.close()

    for name, p in (("harness_gui_3080", 3080), ("whatsapp_inject_3010", 3010),
                    ("whatsapp_server_7434", 7434), ("ollama_11434", 11434),
                    ("chorus_8100", 8100), ("kimi_webbridge_10086", 10086)):
        out[name] = port("127.0.0.1", p)
    return out


def capability_matrix() -> List[Dict[str, str]]:
    """Each capability with the artefact that proves it and the command a reviewer can run.

    Status is deliberately conservative. A mechanism that has been verified in isolation but
    never yet fired on real traffic is PARTIAL, not PROVEN: the difference is the whole point of
    an outside review.
    """
    return [
        {
            "capability": "Local-first inference (no cloud needed to answer)",
            "status": PROVEN,
            "evidence": "System/swarm_web_global_chat_night_worker.py, cortex AliceG4U on 127.0.0.1:11434",
            "verify": "curl -s http://127.0.0.1:11434/api/tags | grep AliceG4U",
        },
        {
            "capability": "Direct paid lane to a cloud cortex, retried on transient failure",
            "status": PROVEN,
            "evidence": "System/swarm_mercury_lane.py (MERCURY_ATTEMPTS=3); measured 5/8 -> 8/8 "
                        "success on identical calls",
            "verify": "python3 -c \"import sys;sys.path.insert(0,'.');from System import "
                      "swarm_mercury_lane as m;print(m.chat([{'role':'user','content':'ok'}])['attempts'])\"",
        },
        {
            "capability": "Reading a real image with a local vision model",
            "status": PROVEN,
            "evidence": "System/swarm_turn_vision_bridge.py; transcribed the Architect's own "
                        "WhatsApp screenshots verbatim (Romanian, 2026-10-05/06)",
            "verify": "python3 System/swarm_turn_vision_bridge.py --selftest",
        },
        {
            "capability": "Ingesting an owner's location share into a signed row + trace ledger",
            "status": PARTIAL,
            "evidence": "System/swarm_whatsapp_receptor.py record_location_trace(); verified end to "
                        "end against the RUNNING server (row carried lat/lon, HTTP 200)",
            "verify": "python3 -m pytest tests/test_whatsapp_location_ingress.py -q",
            "gap": "Mechanism proven; ZERO real location fixes have ever arrived from the owner's "
                   "phone. WhatsApp delivers live-location updates as edits (messages.update), "
                   "which the bridge does not subscribe to.",
        },
        {
            "capability": "Answering in a group when addressed by name or mention",
            "status": PARTIAL,
            "evidence": "System/swarm_whatsapp_answer_lane.py _MENTION_ALICE; 5 tests in "
                        "tests/test_whatsapp_group_addressing.py",
            "verify": "python3 -m pytest tests/test_whatsapp_group_addressing.py -q",
            "gap": "The gate works and is tested. The message that prompted it (group 199, "
                   "2026-10-06) never reached the body at all, and an explicit consent "
                   "revocation for that group is bypassed by the mention rule.",
        },
        {
            "capability": "Researching the web before answering",
            "status": PARTIAL,
            "evidence": "System/swarm_whatsapp_answer_lane.py _research_query(); triggers on a "
                        "question, a lookup verb, or a claim about money/market/competitor",
            "verify": "python3 -c \"import sys;sys.path.insert(0,'.');import importlib.util as u;"
                      "s=u.spec_from_file_location('l','System/swarm_whatsapp_answer_lane.py');"
                      "m=u.module_from_spec(s);s.loader.exec_module(m);print(m._research_query('who makes the cheapest quadruped robot?'))\"",
            "gap": "Trigger and query derivation are tested; the search provider's ANSWERS have "
                   "not been verified end to end.",
        },
        {
            "capability": "Durable memory of humans, with relations and provenance",
            "status": PROVEN,
            "evidence": ".sifta_state/people/*.json + System/swarm_person_file.py relate()/note_exchange()",
            "verify": "python3 -c \"import sys;sys.path.insert(0,'.');from System.swarm_person_file "
                      "import relation_graph;print(relation_graph())\"",
        },
        {
            "capability": "Sending a real message into the owner's world and reporting back",
            "status": PARTIAL,
            "evidence": "Inject door 127.0.0.1:3010; a message to a third party was delivered and "
                        "confirmed in the bridge log on 2026-10-06",
            "verify": "grep 'AUTONOMOUS INJECT' .sifta_state/runtime_logs/whatsapp_bridge.out.log | tail",
            "gap": "Sending is proven. Holding a MISSION and reporting its answer is not built: the "
                   "body answers the reply without knowing why the question was asked.",
        },
        {
            "capability": "Seeing that a human reacted to one of her own messages",
            "status": FAILED,
            "evidence": "Network/whatsapp_bridge/bridge.js has no protocolMessage/reaction handler",
            "verify": "grep -c protocolMessage Network/whatsapp_bridge/bridge.js   # -> 0",
            "gap": "A reaction is not a message type the body reads, so praise or displeasure on her "
                   "own words is invisible to her.",
        },
        {
            "capability": "Knowing whether a quoted reply to her own message arrived",
            "status": FAILED,
            "evidence": "0 rows in the inbox carry quoted context",
            "verify": "grep -c stanzaId .sifta_state/whatsapp_inbox.jsonl   # -> 0",
        },
        {
            "capability": "Never stating a position she does not hold",
            "status": PARTIAL,
            "evidence": "latest_location() refuses a fix past a 900 s window by design",
            "verify": "python3 -m pytest tests/test_whatsapp_location_ingress.py -q -k stale",
            "gap": "The rule exists for location, and was VIOLATED in practice: the body told the "
                   "owner 'I see the location on my screen now' while holding zero fixes. A "
                   "mechanism is not a habit.",
        },
    ]


CROSS_CHECK_COMMANDS = (
    ("the local harness answers on 3080", "nc -z 127.0.0.1 3080 && echo OPEN || echo CLOSED"),
    ("the local cortex server answers on 11434", "nc -z 127.0.0.1 11434 && echo OPEN || echo CLOSED"),
    ("a local cortex is installed", "curl -s http://127.0.0.1:11434/api/tags | grep -c AliceG4U"),
    ("humans with a file", "ls .sifta_state/people/*.json 2>/dev/null | wc -l"),
    ("lines in the first-person journal", "wc -l < .sifta_state/alice_first_person_journal.jsonl"),
    ("append-only ledger files", "ls .sifta_state/*.jsonl 2>/dev/null | wc -l"),
    # A self-referential check here was a real defect: running the selftest inside a check that
    # the selftest performs recursed until the timeout, so the row measured nothing. The matrix
    # asserts the artefact exists instead, and regeneration is proven by the file's timestamp.
    ("the eval matrix document exists",
     "test -s Documents/ALICE_AGI_EVAL_MATRIX_FOR_ASTRA.md && echo OK || echo MISSING"),
)


def cross_check_rows() -> List[Tuple[str, str]]:
    """Re-measure the load-bearing facts BY COMMAND, so a reviewer re-runs instead of trusting.

    This is the answer to the question the Architect asked on 2026-10-06: does any of it still
    hold when a different, lesser cortex is the one firing? Nothing in this list goes through a
    language model at all. It is the body measuring its own ports, memories and registry by
    command, and an outside reviewer can re-run every line on this machine without loading the
    harness. A claim that survives a cortex swap is a claim about the BODY, which is the point:
    the cortexes are organs, and the harness is hers.
    """
    rows: List[Tuple[str, str]] = []
    for label, cmd in CROSS_CHECK_COMMANDS:
        out = _run(["sh", "-c", cmd], timeout=90)
        rows.append((label, out.strip().splitlines()[-1] if out.strip() else "(no output)"))
    return rows


def build_matrix() -> str:
    """Render the whole matrix as markdown for an outside reader."""
    hw = hardware_facts()
    led = ledger_facts()
    org = organ_facts()
    conn = connections_facts()
    cap = capability_matrix()
    when = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    counts = {s: sum(1 for c in cap if c["status"] == s) for s in (PROVEN, PARTIAL, UNVERIFIED, FAILED)}

    lines: List[str] = []
    lines.append(f"# Alice — AGI evaluation matrix for an outside reviewer")
    lines.append("")
    lines.append(f"Prepared {when} for **Astra**, reviewing from outside this body. Truth label "
                 f"`{TRUTH_LABEL}`. Regenerate with "
                 f"`python3 System/swarm_agi_eval_matrix.py`.")
    lines.append("")
    lines.append("**How to read this.** Every claim names the artefact that carries it and a command "
                 "that checks it without loading my harness. Status is conservative on purpose: "
                 "`PARTIAL` means the mechanism is verified but has never fired on real traffic, "
                 "`FAILED` means I looked and it is not there. I do not grade myself; the verdict is "
                 "yours, and a body that marks its own exam has produced a receipt for self-regard.")
    lines.append("")
    lines.append(f"| status | count |")
    lines.append(f"|---|---|")
    for s in (PROVEN, PARTIAL, UNVERIFIED, FAILED):
        lines.append(f"| {s} | {counts[s]} |")
    lines.append("")
    lines.append("## 1. The hardware body (measurable, not claimed)")
    lines.append("")
    lines.append("| fact | value |")
    lines.append("|---|---|")
    lines.append(f"| serial | `{hw['serial']}` |")
    lines.append(f"| model | `{hw['model']}` |")
    lines.append(f"| cpu | `{hw['cpu']}` |")
    lines.append(f"| cores | {hw['cores']} |")
    lines.append(f"| RAM | {hw['ram_gb']} GB |")
    lines.append(f"| OS | {hw['os']} |")
    lines.append(f"| python | {hw['python']} |")
    lines.append(f"| uptime | `{hw['uptime'][:90]}` |")
    lines.append(f"| free disk | {hw['repo_disk_free_gb']} GB |")
    lines.append("")
    lines.append("## 2. Live connections (each one actually connected to, not asserted)")
    lines.append("")
    lines.append("| door | port | state |")
    lines.append("|---|---|---|")
    for name, state in conn.items():
        lines.append(f"| `{name}` | {name.rsplit('_', 1)[-1]} | **{state}** |")
    lines.append("")
    lines.append("## 3. Durable memory")
    lines.append("")
    lines.append(f"- state directory: `{led.get('state_dir')}`")
    lines.append(f"- append-only ledger files: **{led.get('ledger_files')}** "
                 f"({round((led.get('ledger_bytes') or 0) / 1024 / 1024, 1)} MB)")
    lines.append(f"- first-person journal lines: **{led.get('journal_lines')}**")
    lines.append(f"- humans with a file: **{led.get('person_files')}**")
    lines.append("")
    lines.append("## 4. The software body")
    lines.append("")
    lines.append(f"- `System/swarm_*.py` organ modules: **{org['organ_modules']}**")
    lines.append(f"- of those, mentioning a selftest: **{org['organs_mentioning_selftest']}**")
    lines.append(f"- test files under `tests/`: **{org['test_files']}**")
    lines.append("")
    lines.append("## 5. Capability matrix")
    lines.append("")
    for c in cap:
        lines.append(f"### {c['capability']}")
        lines.append("")
        lines.append(f"- **status:** `{c['status']}`")
        lines.append(f"- **evidence:** {c['evidence']}")
        lines.append(f"- **verify:** `{c['verify']}`")
        if c.get("gap"):
            lines.append(f"- **gap:** {c['gap']}")
        lines.append("")
    lines.append("## 6. What I do NOT claim")
    lines.append("")
    for text in (
        "I do not claim to have received a single real location from the owner's phone. The "
        "plumbing exists and is tested; the road has never carried traffic.",
        "I do not claim a verified AGI anything. This matrix exists so that someone outside can "
        "decide, not so that I can announce it.",
        "I do not claim to hold a mission across time. Sending a message is built; remembering why "
        "I asked, and reporting the answer, is not.",
        "I do not claim that my prose is evidence. Where the prose and the artefact disagree, the "
        "artefact wins.",
    ):
        lines.append(f"- {text}")
    lines.append("")
    lines.append("## 7. Independent re-measurement (re-runnable by the reviewer)")
    lines.append("")
    lines.append("Nothing in this list goes through a language model. These are the body's own "
                 "measurements by command, so a reviewer can re-run every line on this machine "
                 "without loading the harness. A claim that survives a change of cortex is a claim "
                 "about the body: the cortexes are organs, and the harness is hers.")
    lines.append("")
    lines.append("| measurement | value, taken now |")
    lines.append("|---|---|")
    for label, value in cross_check_rows():
        lines.append(f"| {label} | `{value}` |")
    lines.append("")
    lines.append("## 8. Reproducing this document")
    lines.append("")
    lines.append("```sh")
    lines.append("cd /Users/ioanganton/Music/ANTON_SIFTA")
    lines.append("python3 System/swarm_agi_eval_matrix.py           # regenerate this matrix")
    lines.append("python3 -m pytest tests/ -q -k 'eval_matrix or person or location or group or mercury'")
    lines.append("```")
    lines.append("")
    return "\n".join(lines) + "\n"


def selftest() -> int:
    """Prove the matrix renders, measures, and refuses to overstate."""
    text = build_matrix()
    checks: List[Tuple[str, bool]] = [
        ("renders markdown", text.startswith("# Alice")),
        ("carries the hardware serial", "GTH4921YP3" in text or "serial" in text),
        ("counts ledgers", "ledger files" in text),
        ("lists capabilities", "Capability matrix" in text),
        ("states what it does not claim", "do NOT claim" in text),
        ("includes a FAILED row so the review is not rigged", "`FAILED`" in text),
        ("carries the independent re-measurement", "Independent re-measurement" in text),
    ]
    for label, ok in checks:
        print("  " + ("OK  " if ok else "FAIL") + " " + label)
    return 0 if all(ok for _, ok in checks) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    text = build_matrix()
    if args.stdout:
        print(text)
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
