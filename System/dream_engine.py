#!/usr/bin/env python3
"""
dream_engine.py — Sleep-cycle memory consolidation for Swarm OS
================================================================

When both machines are idle the OS enters a dream cycle:
  1. Replays the day's dead-drop entries, ledger events, error logs
  2. Runs compressed micro-analysis looking for slow-burn anomalies
  3. Evaporates stale immune antibodies
  4. Writes a one-paragraph "dream report" printed at morning boot

Designed to be called by circadian_rhythm.py during the 2–5 AM window,
or manually via:  python3 System/dream_engine.py

Persistence:
  .sifta_state/dream_reports/YYYY-MM-DD.txt
  .sifta_state/dream_meta.json
"""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_DREAM_DIR = _STATE_DIR / "dream_reports"
_META = _STATE_DIR / "dream_meta.json"


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_jsonl(path: Path, max_lines: int = 5000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text().splitlines()[-max_lines:]:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries


def _is_today(ts_like: Any) -> bool:
    """Robust 'is today' check for ISO strings or unix timestamps."""
    if ts_like is None:
        return False
    today = _today()
    s = str(ts_like).strip()
    if not s:
        return False
    # ISO-ish text timestamps
    if s.startswith(today):
        return True
    # Unix epoch (seconds) as int/float/string
    try:
        ts = float(s)
        if ts > 1e9:  # ignore tiny numeric garbage
            return time.strftime("%Y-%m-%d", time.localtime(ts)) == today
    except Exception:
        pass
    return False


def _entry_is_today(entry: dict[str, Any]) -> bool:
    for key in ("ts", "timestamp", "time", "created_at"):
        if key in entry and _is_today(entry.get(key)):
            return True
    return False


def _analyze_dead_drop() -> dict[str, Any]:
    """Scan today's dead-drop messages for anomalies."""
    entries = _read_jsonl(_REPO / "m5queen_dead_drop.jsonl")
    today_entries = [e for e in entries if _entry_is_today(e)]

    senders: Counter[str] = Counter()
    event_types: Counter[str] = Counter()
    errors = 0
    for e in today_entries:
        senders[e.get("from", e.get("sender", "unknown"))] += 1
        event_types[e.get("type", e.get("event", "msg"))] += 1
        if "error" in json.dumps(e).lower():
            errors += 1

    return {
        "total_messages": len(today_entries),
        "unique_senders": len(senders),
        "top_senders": senders.most_common(5),
        "event_types": dict(event_types),
        "error_mentions": errors,
    }


def _analyze_repair_log() -> dict[str, Any]:
    """Scan repair log for recurring failures."""
    entries = _read_jsonl(_REPO / "repair_log.jsonl")
    today_entries = [e for e in entries if _entry_is_today(e)]

    targets: Counter[str] = Counter()
    for e in today_entries:
        targets[e.get("target", e.get("module", "unknown"))] += 1

    return {
        "repairs_today": len(today_entries),
        "repeat_targets": {k: v for k, v in targets.items() if v > 1},
    }


def _analyze_economy() -> dict[str, Any]:
    """Check for token inflation or suspicious mint patterns."""
    ledger_path = _REPO / "inference_economy.py"
    stgm_ledger = _STATE_DIR / "stgm_ledger.jsonl"

    entries = _read_jsonl(stgm_ledger)
    today_mints = [e for e in entries if e.get("event") == "UTILITY_MINT" and _entry_is_today(e)]
    total_minted = sum(float(e.get("amount_stgm", 0)) for e in today_mints)
    unique_miners = len({e.get("miner_id") for e in today_mints})

    return {
        "mints_today": len(today_mints),
        "total_stgm_minted": round(total_minted, 4),
        "unique_miners": unique_miners,
        "inflation_alert": total_minted > 50.0,
    }


def _analyze_fitness() -> dict[str, Any]:
    """Check app fitness scores for anything deeply negative."""
    import sys
    if str(_REPO / "System") not in sys.path:
        sys.path.insert(0, str(_REPO / "System"))
    try:
        from app_fitness import get_scores
        scores = get_scores()
        crashed = {k: v for k, v in scores.items() if v < -3.0}
        thriving = sorted(scores.items(), key=lambda x: -x[1])[:3]
        return {"crashed_apps": crashed, "top_3": thriving}
    except Exception:
        return {"crashed_apps": {}, "top_3": []}


def _evaporate_immune() -> int:
    """Run immune memory evaporation."""
    import sys
    if str(_REPO / "System") not in sys.path:
        sys.path.insert(0, str(_REPO / "System"))
    try:
        from immune_memory import evaporate
        return evaporate()
    except Exception:
        return 0


def _process_fissions() -> dict[str, Any]:
    """Process failure clusters and trigger Stigmergic Task Fissions."""
    import sys
    if str(_REPO / "System") not in sys.path:
        sys.path.insert(0, str(_REPO / "System"))
    try:
        from fission_core import get_fission_engine, DecayController
        dec = DecayController()
        dec.apply_decay()
        
        eng = get_fission_engine()
        fissions = eng.process_failures()
        return {"fissions_spawned": fissions, "decay_applied": True}
    except Exception as e:
        return {"fissions_spawned": 0, "decay_applied": False, "err": str(e)}

def _compose_report(analyses: dict[str, Any]) -> str:
    """Turn raw analysis dicts into a readable dream report paragraph."""
    dd = analyses["dead_drop"]
    rep = analyses["repairs"]
    eco = analyses["economy"]
    fit = analyses["fitness"]
    imm_evap = analyses["immune_evaporated"]

    lines: list[str] = []
    lines.append(f"DREAM REPORT — {_today()}")
    lines.append("=" * 50)
    lines.append("")

    lines.append(f"Dead drop: {dd['total_messages']} messages from {dd['unique_senders']} senders. "
                 f"{dd['error_mentions']} error mentions.")
    if dd["error_mentions"] > 5:
        lines.append("  ⚠ Elevated error chatter — investigate agent stability.")

    lines.append(f"Repairs: {rep['repairs_today']} interventions today.")
    if rep["repeat_targets"]:
        lines.append(f"  ⚠ Repeat failures: {rep['repeat_targets']}")

    lines.append(f"Economy: {eco['mints_today']} mints, {eco['total_stgm_minted']} STGM across "
                 f"{eco['unique_miners']} miners.")
    if eco["inflation_alert"]:
        lines.append("  ⚠ INFLATION ALERT: >50 STGM minted in single day!")

    if fit["crashed_apps"]:
        lines.append(f"  ⚠ Crashing apps: {fit['crashed_apps']}")
    if fit["top_3"]:
        top_str = ", ".join(f"{n}({s:+.1f})" for n, s in fit["top_3"])
        lines.append(f"  Top fitness: {top_str}")

    lines.append(f"Immune: evaporated {imm_evap} stale antibodies.")

    fis = analyses.get("fissions", {"fissions_spawned": 0})
    if fis["fissions_spawned"] > 0:
        lines.append(f"Fissions: Spawned {fis['fissions_spawned']} new Stigmergic task(s) on Blackboard.")

    lines.append("")
    all_clear = (
        dd["error_mentions"] < 3
        and not rep["repeat_targets"]
        and not eco["inflation_alert"]
        and not fit["crashed_apps"]
    )
    if all_clear:
        lines.append("Assessment: All systems nominal. The Swarm rests well.")
    else:
        lines.append("Assessment: Anomalies detected. Review flagged items above.")

    return "\n".join(lines)


def run_dream_cycle() -> str:
    """Execute a full dream cycle. Returns the dream report text."""
    _DREAM_DIR.mkdir(parents=True, exist_ok=True)

    analyses: dict[str, Any] = {
        "dead_drop": _analyze_dead_drop(),
        "repairs": _analyze_repair_log(),
        "economy": _analyze_economy(),
        "fitness": _analyze_fitness(),
        "immune_evaporated": _evaporate_immune(),
        "fissions": _process_fissions(),
    }

    report = _compose_report(analyses)

    report_path = _DREAM_DIR / f"{_today()}.txt"
    report_path.write_text(report + "\n")

    meta: dict[str, Any] = {}
    if _META.exists():
        try:
            meta = json.loads(_META.read_text())
        except Exception:
            pass
    meta["last_dream"] = _now_iso()
    meta["last_report"] = str(report_path)
    meta["analyses"] = analyses
    _META.write_text(json.dumps(meta, indent=2, default=str) + "\n")

    return report


def latest_report() -> str | None:
    """Return the most recent dream report text, or None."""
    _DREAM_DIR.mkdir(parents=True, exist_ok=True)
    reports = sorted(_DREAM_DIR.glob("*.txt"), reverse=True)
    if reports:
        return reports[0].read_text()
    return None


if __name__ == "__main__":
    print(run_dream_cycle())
