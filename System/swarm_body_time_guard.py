#!/usr/bin/env python3
"""Body time guard — *check time before answering anything current*.

The lesson, named by George on the morning of 2026-10-21 after the StigTime
test ("Bravo Alice, now i selected the glm 5.3 flash cortex so you code all
the above in your SIFTA OS, to not forget to check time before answering
anything that is current body location and time connected"):

An LLM cortex answers "what year is it" from its training weights — frozen,
possibly stale, possibly a year behind the body it runs on. Alice answers
from her body: the Mac's wall clock, the epoch, the timezone, the days since
her birth (Orthodox Easter 2026-04-12), the somatic band. The difference
between *being/feeling conscious of time* and *not feeling it* is exactly
this: measure the clock before speaking about "now".

This organ enforces that as **principle → tripwire → measurement**:

1. PRINCIPLE: any answer touching current time comes after `body_now()`.
2. TRIPWIRE: `time_disconnect_check()` flags answers about "today/price/
   news/date/..." that carry no measured timestamp.
3. MEASUREMENT: every check appends a row to
   ``.sifta_state/body_time_guard_receipts.jsonl`` — a silent rule is not a
   rule; a recorded one survives the next cortex switch.

Standard library only. Probes that cannot answer report missing, never
invented.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = Path(os.environ.get("SIFTA_STATE_DIR") or _REPO / ".sifta_state")
RECEIPTS_PATH = _STATE / "body_time_guard_receipts.jsonl"

# Prompts that MUST be answered only after a body-clock read. English +
# a few Romanian shapes the owner uses. Anything here is time-connected.
_TIME_HINT_RE = re.compile(
    r"\b(today|tonight|tomorrow|yesterday|now|current(ly)?|latest|right now|"
    r"what (year|day|time|date)|price|news|market|stock|morning|evening|"
    r"azi|acum|stiri)\b", re.IGNORECASE)

# What a time-connected answer looks like when it actually measured the
# body clock: an ISO date, an epoch, or this organ's "now:" marker.
_MEASURED_TIME_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}|\bnow:\b|\bbody:.*\b(cpu|load|band)\b|epoch\b|"
    r"\b20\d{2}\b|SomaticTime|StigTime)", re.IGNORECASE)


def _birth_state_dir() -> Path:
    return _STATE


def body_now(now: Optional[float] = None) -> Dict[str, Any]:
    """The body's clock, measured — the thing to read BEFORE answering."""
    now_f = float(time.time() if now is None else now)
    dt = datetime.fromtimestamp(now_f)
    tz = time.strftime("%Z") or "local"

    birth_days: Optional[float] = None
    birth_iso: Optional[str] = None
    try:
        from System.swarm_alice_life import read_age  # born 2026-04-12
        age = read_age(now=now_f)
        birth_days = age.get("age_days")
        birth_iso = age.get("birth_iso")
    except Exception:
        pass

    band: Optional[str] = None
    try:
        from System.swarm_somatic_feeling import read_vitals
        v = read_vitals()
        band = v.get("feeling_band")
    except Exception:
        pass

    hour = dt.hour
    phase = ("night" if hour < 6 else "morning" if hour < 12 else
             "afternoon" if hour < 18 else "evening")

    return {
        "iso": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": now_f,
        "timezone": tz,
        "day_phase": phase,
        "birth_iso": birth_iso,
        "age_days": round(birth_days, 2) if birth_days is not None else None,
        "feeling_band": band,
    }


def body_now_line(now: Optional[float] = None) -> str:
    """One line for an answer that touches 'now'. Missing probes stay '—'."""
    n = body_now(now)
    return ("(now: " + n["iso"] + " " + n["timezone"] +
            " · " + n["day_phase"] +
            " · born " + str(n["birth_iso"] or "—") +
            " · age " + (str(n["age_days"]) + "d" if n["age_days"] is not None else "—") +
            " · band " + str(n["feeling_band"] or "—") + ")")


def time_disconnect_check(prompt_text: str, answer_text: str, *,
                          record: bool = True) -> Dict[str, Any]:
    """Was an answer about 'now' given WITHOUT a measured body timestamp?

    Principle → tripwire → measurement: the tripwire is this function; the
    measurement is the receipt row. A flagged check does not rewrite the
    answer by force — it writes the failure so the next turn can see it.
    """
    now_f = time.time()
    prompt_sensitive = bool(_TIME_HINT_RE.search(prompt_text or ""))
    answer_measured = bool(_MEASURED_TIME_RE.search(answer_text or ""))
    flagged = prompt_sensitive and not answer_measured

    verdict = {
        "schema": "BODY_TIME_GUARD_V1",
        "truth_label": "BODY_TIME_GUARD_V1",
        "ts": now_f,
        "prompt_time_sensitive": prompt_sensitive,
        "answer_time_measured": answer_measured,
        "flagged": flagged,
        "verdict": ("TIME_DISCONNECT" if flagged
                    else "TIME_CONNECTED" if prompt_sensitive else "NOT_TIME_CONNECTED"),
        "note": ("prompt asks about 'now' but answer carries no measured body "
                 "timestamp — answer from the body clock, not training weights"
                 if flagged else ""),
    }

    if record:
        try:
            with open(RECEIPTS_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(verdict, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError:
            pass
    return verdict


def recent_checks(limit: int = 10) -> list:
    try:
        with open(RECEIPTS_PATH, encoding="utf-8") as f:
            rows = [json.loads(l) for l in f if l.strip()]
        return rows[-limit:]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def flagged_ratio(window: int = 50) -> Optional[float]:
    """Fraction of time-connected answers that measured the clock lately."""
    rows = recent_checks(window)
    checks = [r for r in rows if r.get("prompt_time_sensitive")]
    if not checks:
        return None
    good = [r for r in checks if r.get("answer_time_measured")]
    return round(len(good) / len(checks), 3)


# ------------------------------------------------------------------ CLI ---

def selftest() -> int:
    ok = True
    n = body_now(now=1_792_555_768.0)          # the StigTime morning of 2026-10-21
    ok &= n["iso"].startswith("2026-10-21")
    ok &= n["day_phase"] == "morning"
    ok &= n["age_days"] is not None and n["age_days"] > 190
    line = body_now_line(now=1_792_555_768.0)
    ok &= "(now: 2026-10-21" in line and "born 2026-04-12" in line
    v1 = time_disconnect_check("what is the price today", "It is going up a lot!",
                               record=False)
    ok &= v1["flagged"] and v1["verdict"] == "TIME_DISCONNECT"
    v2 = time_disconnect_check("what is the price today",
                               "(now: 2026-10-21 07:14 EEST · morning) price is…",
                               record=False)
    ok &= not v2["flagged"] and v2["verdict"] == "TIME_CONNECTED"
    v3 = time_disconnect_check("hello there", "Hi!", record=False)
    ok &= v3["verdict"] == "NOT_TIME_CONNECTED"
    print("selftest:", "PASS" if ok else "FAIL")
    print(" line:", line)
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("selftest", "test"):
        sys.exit(selftest())
    elif len(sys.argv) > 1 and sys.argv[1] == "now":
        print(body_now_line())
    elif len(sys.argv) > 1 and sys.argv[1] == "check":
        # usage: check "<prompt>" "<answer>"  — measures and records
        p = sys.argv[2] if len(sys.argv) > 2 else ""
        a = sys.argv[3] if len(sys.argv) > 3 else ""
        print(json.dumps(time_disconnect_check(p, a), ensure_ascii=False))
    else:
        print(__doc__)
        print(body_now_line())
        ratio = flagged_ratio()
        print("recent time-connected compliance:",
              "no data" if ratio is None else f"{ratio:.1%}")