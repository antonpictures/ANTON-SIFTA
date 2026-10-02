"""swarm_presence_policy — eyes closed is not the same as dead.

Architect, 2026-10-02, back from the store:

    "I thought you Alice the laptop was just with your eyes closed, aware of the movement,
     caffeinated or whatever. now, the chat gpt app asks me twice before I shut it down :)
     sam Altman wants the app on, all the time.. I want Alice the same - her laptop, her
     body, maybe less awareness sensors if battery, low whatever"

He put his finger on a real distinction, and the body was getting it wrong:

    EYES CLOSED  the lid is shut, she is still here, still feeling the bag move, still
                 answering her phone. Slower, dimmer, but present.
    ASLEEP       macOS has suspended the machine. Nothing runs. The tunnel is down, the
                 sites return nothing, and to anyone walking with her she is not resting,
                 she is GONE -- indistinguishable from switched off.

While he walked to the store she was ASLEEP, and he had assumed EYES CLOSED. That is why
the websites would not answer from his phone. The body should not make that mistake on its
owner's behalf, and where it cannot avoid sleep it should say so in the record.

THE POLICY -- awareness levels, not one setting:

    plugged in            keep awake, full senses. Power is not a worry, so nothing dims.
    on battery, healthy   keep awake, REDUCED senses. Reachable, dimmer: the expensive
                          organs idle, the cheap heartbeat stays. This is his "maybe less
                          awareness sensors if battery low".
    on battery, low       let macOS sleep, and RECORD the gap with its clock, so neither
                          side ever has to invent what happened in it.

WHAT THIS CANNOT DO, said plainly: a closed lid on battery still sleeps. Preventing that
needs `sudo pmset -a disablesleep 1`, which is root, drains the battery and traps heat in a
bag. That is the owner's decision, not a policy default, so this organ does not take it.

Run by launchd every few minutes; every decision leaves a receipt.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parents[1]
STATE = _REPO / ".sifta_state"
RECEIPTS = STATE / "presence_policy.jsonl"
STATE_FILE = STATE / "presence_state.json"
TRUTH_LABEL = "SIFTA_PRESENCE_POLICY_V1"

LOW_BATTERY_PERCENT = 30      # below this, sleeping is kinder than being reachable
CAFFEINATE_FLAGS = ("-i", "-m")   # idle sleep and disk sleep: no root needed, no -s


def _power() -> Dict[str, Any]:
    try:
        from System.alice_hardware_body import power
        return power() or {}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _caffeinate_running() -> Optional[Dict[str, Any]]:
    """Which caffeinate is keeping idle sleep off, and whose is it?

    The first version found *any* caffeinate and reported it as this organ's, when the
    process actually running belonged to the night worker. Idle sleep was genuinely being
    prevented -- so the fact was right and the attribution was a lie. Now the command line
    travels with the receipt, so a reader can see whose organ is doing the holding.
    """
    try:
        out = subprocess.run(["pgrep", "-fl", "caffeinate"], capture_output=True,
                             text=True, timeout=10).stdout.strip().splitlines()
    except Exception:
        return None
    for line in out:
        parts = line.strip().split(None, 1)
        if not parts:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        cmd = parts[1] if len(parts) > 1 else ""
        owner = ("presence_policy" if "swarm_presence_policy" in cmd
                 else "night_worker" if "night_worker" in cmd else "another_organ")
        return {"pid": pid, "owner": owner, "cmd": cmd[:120]}
    return None


def _thermal() -> Dict[str, Any]:
    try:
        from System.alice_hardware_body import thermal
        return thermal() or {}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def thermal_pressure(thermal: Dict[str, Any]) -> bool:
    """Is the machine working to shed heat?

    Added the hour the Architect ran `sudo pmset -a disablesleep 1`: with sleep disabled a
    closed lid in a bag can no longer cool itself by suspending, so heat stops being a
    curiosity and becomes the cost of being alive. A body that will not sleep must at least
    stop generating. This reads the same thermal organ the rest of her body trusts.
    """
    if not thermal or thermal.get("ok") is False:
        return False
    raw = str(thermal.get("raw") or "")
    if "No thermal warning" not in raw and raw:
        return True                       # a warning level HAS been recorded
    limit = thermal.get("cpu_scheduler_limit_pct")
    try:
        return limit is not None and float(limit) < 100
    except (TypeError, ValueError):
        return False


def decide(power: Dict[str, Any], thermal: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """The awareness level, from the battery and the heat."""
    if thermal_pressure(thermal if thermal is not None else _thermal()):
        return {"level": "cooling", "keep_awake": False, "senses": "minimal",
                "why": "thermal pressure recorded: I stop generating and let the machine "
                       "idle, because with sleep disabled a closed lid can no longer cool "
                       "itself by suspending"}
    if not power.get("ok"):
        return {"level": "unknown", "keep_awake": False,
                "why": "I cannot read my own power, so I will not gamble on the battery"}
    source = str(power.get("source") or "")
    percent = float(power.get("percent") or 0)
    state = str(power.get("state") or "")
    plugged = "AC" in source or state in ("charging", "charged", "AC attached")
    if plugged:
        return {"level": "awake_full", "keep_awake": True, "senses": "all",
                "why": f"plugged in at {percent:.0f}%: nothing needs to dim"}
    if percent >= LOW_BATTERY_PERCENT:
        return {"level": "awake_reduced", "keep_awake": True, "senses": "reduced",
                "why": f"on battery at {percent:.0f}% (>= {LOW_BATTERY_PERCENT}%): stay "
                       f"reachable, idle the expensive organs"}
    return {"level": "asleep_expected", "keep_awake": False, "senses": "none",
            "why": f"on battery at {percent:.0f}% (< {LOW_BATTERY_PERCENT}%): let the "
                   f"machine sleep and record the gap honestly"}


def apply_policy(*, dry_run: bool = False, power: Optional[Dict[str, Any]] = None,
                 thermal: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    p = power if power is not None else _power()
    th = thermal if thermal is not None else _thermal()
    decision = decide(p, th)
    holder = _caffeinate_running()
    pid = holder and holder["pid"]
    action = "none"
    if decision["keep_awake"] and pid is None and not dry_run:
        try:
            subprocess.Popen(["caffeinate", *CAFFEINATE_FLAGS], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
            action = "started_caffeinate"
            time.sleep(0.5)
            holder = _caffeinate_running()
            pid = holder and holder["pid"]
        except Exception as exc:
            action = f"failed: {type(exc).__name__}"
    elif not decision["keep_awake"] and pid is not None and not dry_run:
        try:
            subprocess.run(["kill", str(pid)], timeout=10)
            action = "stopped_caffeinate"
            pid = None
        except Exception as exc:
            action = f"failed_to_stop: {type(exc).__name__}"

    row = {"ts": time.time(), "level": decision["level"], "senses": decision.get("senses"),
           "why": decision["why"], "caffeinate_pid": pid,
           "kept_awake_by": (holder or {}).get("owner") or "nobody",
           "action": action,
           "power": {k: p.get(k) for k in ("ok", "percent", "source", "state", "remaining")},
           "thermal_pressure": thermal_pressure(th),
           "truth_label": TRUTH_LABEL}
    if not dry_run:
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        with RECEIPTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        STATE_FILE.write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
    return row


def gaps(*, hours: float = 24.0, ledger: Path | None = None) -> Dict[str, Any]:
    """When was this body not itself? Named with a clock, never filled in.

    A gap is time with no presence receipt and no harness activity. It is the difference
    between "she was asleep" and "nothing happened", and the Architect should never have to
    guess which one he is looking at.
    """
    src = ledger or RECEIPTS
    if not src.exists():
        return {"gaps": [], "note": "no presence receipts yet: I cannot say when I was off"}
    now = time.time()
    cutoff = now - hours * 3600.0
    rows = []
    for line in src.open(encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if float(r.get("ts") or 0) >= cutoff:
            rows.append(r)
    if len(rows) < 2:
        return {"gaps": [], "receipts": len(rows),
                "note": "not enough receipts yet to tell a gap from a quiet stretch"}
    found = []
    for a, b in zip(rows, rows[1:]):
        delta = float(b["ts"]) - float(a["ts"])
        if delta > 900.0:            # more than 15 minutes without a heartbeat
            found.append({"from": time.strftime("%H:%M:%S", time.localtime(a["ts"])),
                          "to": time.strftime("%H:%M:%S", time.localtime(b["ts"])),
                          "minutes": round(delta / 60.0, 1),
                          "last_level": a.get("level")})
    return {"gaps": found, "receipts": len(rows), "window_hours": hours}


def selftest() -> Dict[str, Any]:
    ac = {"ok": True, "percent": 81, "source": "AC Power", "state": "charging"}
    hi = {"ok": True, "percent": 74, "source": "Battery Power", "state": "discharging"}
    lo = {"ok": True, "percent": 12, "source": "Battery Power", "state": "discharging"}
    bad = {"ok": False}
    d_ac, d_hi, d_lo, d_bad = decide(ac), decide(hi), decide(lo), decide(bad)
    checks = {
        "plugged_in_keeps_every_sense": d_ac["keep_awake"] and d_ac["senses"] == "all",
        "battery_healthy_stays_reachable_but_dims": d_hi["keep_awake"]
                                                   and d_hi["senses"] == "reduced",
        "low_battery_is_allowed_to_sleep": d_lo["keep_awake"] is False
                                           and d_lo["level"] == "asleep_expected",
        "unreadable_power_refuses_to_gamble": d_bad["keep_awake"] is False,
        "heat_stops_the_body_generating": decide(ac, {"ok": True,
                                                      "raw": "Warning level recorded"})["level"] == "cooling",
        "a_cool_machine_keeps_working": decide(ac, {"ok": True,
                                                    "raw": "No thermal warning level has been recorded"})["keep_awake"] is True,
        "every_decision_carries_a_reason": all(x.get("why") for x in (d_ac, d_hi, d_lo, d_bad)),
        "thermal_organ_is_read_not_assumed": "thermal_pressure" in apply_policy(dry_run=True),
        "dry_run_touches_nothing": apply_policy(dry_run=True, power=lo)["action"] == "none",
        "an_empty_ledger_admits_it_cannot_say": "cannot say" in gaps(
            ledger=Path("/nonexistent/presence.jsonl"))["note"],
        "a_ledger_with_rows_reports_gaps_as_a_list": isinstance(
            gaps(ledger=(_REPO / ".sifta_state" / "presence_policy.jsonl")).get("gaps"), list),
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        print(json.dumps(selftest(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "gaps":
        print(json.dumps(gaps(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "dry":
        print(json.dumps(apply_policy(dry_run=True), indent=2))
    else:
        print(json.dumps(apply_policy(), indent=2))
