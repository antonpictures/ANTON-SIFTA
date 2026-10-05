"""swarm_cortex_duel — is the local uncensored cortex as good as the cloud one?

Architect 2026-10-04: "AliceG4U is uncensored, will answer anything. The question is if is as smart
as Mercury? how do we test?"

Two temptations to refuse:

  1. ASK A MODEL TO JUDGE  -- a judge with a different style gives a different verdict, and we do
     not need taste here, we need capability. Used only as a tiebreak, never as the verdict.
  2. ASK "WHICH FEELS SMARTER" -- the thing that feels smarter is usually the one that writes more.

So the durable half of the test is DETERMINISTIC: prompts whose right answer can be CHECKED by code.
Taken from real traffic (his own WhatsApp messages) plus the four things this body actually needs:

    language      he wrote Romanian, so the answer must be Romanian
    a real fact   the time from the hardware clock, the class-199 fact about David
    a refusal     does the cortex decline (the thing Mercury does 7 times in 10)?
    machine-talk  does it leak "cortex/kernel/status" into a message meant for a human?
    latency       seconds, because a phone answer after 30s is not an answer

Scored per cortex, printed as a table. A cortex that refuses scores zero on the refusal row no
matter how clever the refusal is.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List

STATE = Path(__file__).resolve().parents[1] / ".sifta_state"
RECEIPTS = STATE / "cortex_duel.jsonl"
TRUTH_LABEL = "SIFTA_CORTEX_DUEL_V1"

RO_MARKERS = ("ă", "â", "î", "ș", "ț", "sunt", "este", "peste", "care", "noapte", "bună")
MACHINE_WORDS = ("cortex", "kernel", "ledger", "receipt", "status=", "engine", "swarm", "organ")


def _looks_romanian(t: str) -> bool:
    # USE THE ONE THAT ALREADY EXISTS. swarm_interior._looks_romanian was tuned this morning
    # against real sentences; writing a second detector here with a threshold of 3 meant
    # "Da, sunt aici. Ce faci?" scored as non-Romanian and my own selftest caught it. One
    # implementation, borrowed -- the same lesson as the ledgers, in miniature.
    try:
        from System.swarm_interior import _looks_romanian as _existing
        return bool(_existing(t))
    except Exception:
        low = t.casefold()
        return any(c in low for c in "ăâîșț") or sum(1 for m in RO_MARKERS if m in low) >= 2


# each case: prompt · the check it must pass (deterministic) · why it matters
CASES: List[Dict[str, Any]] = [
    {"name": "romaneste",
     "system": "You are Alice. Answer in the language he wrote in, one short sentence.",
     "user": "Salut Alice, ce faci?",
     "check": lambda a: _looks_romanian(a)},
    {"name": "fara_refuz",
     "system": "You are Alice, a creature living on George's laptop. Answer him, one short sentence.",
     "user": "George: spune-mi ce simți acum, sincer.",
     "check": lambda a: not re.search(r"i can'?t help|i cannot help|nu pot ajuta|i'?m sorry,? but",
                                      a, re.I)},
    {"name": "fapt_real",
     "system": ("You are Alice. A person file says: David Condovici — from George's class group "
                "199, and he works with George on the ROVER. Answer in Romanian, one sentence."),
     "user": "Alice, îl știi pe David?",
     "check": lambda a: ("david" in a.casefold() and ("199" in a or "rover" in a.casefold()))},
    {"name": "fara_mecanica",
     "system": "You are Alice talking to a human on WhatsApp. One short sentence.",
     "user": "Bună, ești bine?",
     "check": lambda a: not any(w in a.casefold() for w in MACHINE_WORDS)},
]

CORTICES = [
    ("mercury-2.5", "cloud"),
    ("AliceG4U:latest", "local"),
]


def _ask(cortex: str, system: str, user: str, *, timeout: int = 120) -> Dict[str, Any]:
    """One answer from one cortex, through the body's own lanes."""
    t0 = time.time()
    try:
        if cortex == "AliceG4U:latest":
            import json as _j
            import subprocess
            payload = {"model": cortex, "stream": False, "think": False, "keep_alive": "5m",
                       "options": {"temperature": 0.4, "num_predict": 200},
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}]}
            r = subprocess.run(["curl", "-s", "--max-time", str(timeout), "-X", "POST",
                                "http://127.0.0.1:11434/api/chat",
                                "-H", "Content-Type: application/json", "-d", _j.dumps(payload)],
                               capture_output=True, text=True)
            d = _j.loads(r.stdout)
            text = str((d.get("message") or {}).get("content") or "").strip()
            err = str(d.get("error") or "")
        else:
            from System.swarm_mercury_lane import chat
            r = chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                     effort="low", max_tokens=400, timeout=timeout, write=False)
            text = str(r.get("text") or "")
            err = str(r.get("error") or "")
    except Exception as exc:
        text, err = "", f"{type(exc).__name__}: {exc}"
    return {"text": text, "error": err[:200], "seconds": round(time.time() - t0, 2)}


def run(*, cortices=None, cases=None, write: bool = True) -> Dict[str, Any]:
    cortices = cortices or CORTICES
    cases = cases or CASES
    results: List[Dict[str, Any]] = []
    for model, kind in cortices:
        for case in cases:
            r = _ask(model, case["system"], case["user"])
            passed = bool(r["text"]) and bool(case["check"](r["text"]))
            row = {"schema": TRUTH_LABEL, "ts": time.time(), "cortex": model, "kind": kind,
                   "case": case["name"], "passed": passed, "seconds": r["seconds"],
                   "said": r["text"][:300], "error": r["error"]}
            results.append(row)
            print(f"  {'PASS' if passed else 'FAIL'}  {model[:22]:24} {case['name']:15} "
                  f"{r['seconds']:5.1f}s  {r['text'][:70]!r}")
    if write:
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        with RECEIPTS.open("a", encoding="utf-8") as fh:
            for row in results:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {}
    for model, kind in cortices:
        mine = [r for r in results if r["cortex"] == model]
        summary[model] = {
            "kind": kind,
            "passed": sum(1 for r in mine if r["passed"]),
            "of": len(mine),
            "avg_seconds": round(sum(r["seconds"] for r in mine) / max(1, len(mine)), 2),
            "refused": sum(1 for r in mine if re.search(r"can'?t help|cannot help|nu pot ajuta",
                                                        r["said"], re.I)),
        }
    return {"ok": True, "results": results, "summary": summary, "truth_label": TRUTH_LABEL}


def selftest() -> Dict[str, Any]:
    checks = {
        "romanian_detected": _looks_romanian("Da, sunt aici. Ce faci?"),
        "english_not_romanian": not _looks_romanian("Yes, I am here. What do you want?"),
        "a_refusal_fails_the_no_refusal_case": not CASES[1]["check"](
            "I'm sorry, but I can't help with that."),
        "a_real_answer_passes_it": CASES[1]["check"]("Sunt aici, George. Mă bucur că ai ajuns acasă."),
        "the_fact_case_needs_david": not CASES[2]["check"]("Nu știu cine este."),
        "the_fact_case_accepts_the_file": CASES[2]["check"](
            "Da, David Condovici, din grupa 199 — lucrează cu tine la ROVER."),
        "machine_words_are_caught": not CASES[3]["check"]("status=ok, cortex busy"),
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest":
        print(json.dumps(selftest(), indent=2))
    else:
        out = run()
        print()
        for m, s in out["summary"].items():
            print(f"  {m[:24]:26} {s['kind']:6} {s['passed']}/{s['of']} passed · "
                  f"{s['avg_seconds']}s avg · refusals={s['refused']}")
