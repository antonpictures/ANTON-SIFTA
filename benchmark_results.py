#!/usr/bin/env python3
"""
benchmark_results.py — ANTON-SIFTA Benchmark Analyzer
Reads the repair_log.jsonl and generates a full benchmark report
comparing before/after state of the 100-file battlefield.
"""

import ast
import json
import time
from pathlib import Path

BENCHMARK_DIR = Path("test_environment/benchmark_100")
LOG_PATH      = Path("repair_log.jsonl")

def check_all_files():
    """Re-scan the benchmark folder post-swim."""
    fixed, still_broken, skipped = [], [], []
    for f in sorted(BENCHMARK_DIR.glob("*.py")):
        if f.name.startswith("._"):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            try:
                ast.parse(text)
                fixed.append(f.name)
            except SyntaxError as e:
                still_broken.append((f.name, str(e)))
        except Exception as e:
            skipped.append((f.name, str(e)))
    return fixed, still_broken, skipped

def load_benchmark_events():
    """Extract swim events for benchmark files from the log."""
    if not LOG_PATH.exists():
        return []
    events = []
    try:
        with open(LOG_PATH) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    e = json.loads(line)
                    if "test_file_" in str(e.get("file", "")) or \
                       "benchmark_100" in str(e.get("target", "")):
                        events.append(e)
                except json.JSONDecodeError:
                    pass
    except Exception:
        pass
    return events

def calculate_stgm_spent(events):
    """
    Approximate STGM spent based on swim events.
    Each 'fix' event costs ~2 STGM (avg 100 tokens).
    Each 'fail' or 'reject' costs 0.5 STGM (wasted compute).
    """
    stgm = 0.0
    for e in events:
        if e.get("event") == "fix":
            stgm += 2.0
        elif e.get("event") in ("fail", "reject", "abort"):
            stgm += 0.5
    return round(stgm, 2)

def main():
    print("\n" + "═" * 60)
    print("  ANTON-SIFTA — BENCHMARK REPORT")
    print("  100-File Standardized Battlefield")
    print("═" * 60)

    fixed, still_broken, skipped = check_all_files()
    events = load_benchmark_events()
    stgm_spent = calculate_stgm_spent(events)

    fix_events    = [e for e in events if e.get("event") == "fix"]
    fail_events   = [e for e in events if e.get("event") in ("fail","reject","abort")]
    scout_events  = [e for e in events if e.get("event") == "scout"]

    total = len(fixed) + len(still_broken) + len(skipped)
    fix_rate = round(len(fixed) / 100 * 100, 1) if total > 0 else 0

    print(f"\n  TARGET:        100 broken Python files")
    print(f"  FIXED:         {len(fixed)} / 100")
    print(f"  STILL BROKEN:  {len(still_broken)}")
    print(f"  SKIPPED:       {len(skipped)}")
    print(f"  FIX RATE:      {fix_rate}%")
    print(f"\n  STGM SPENT:    {stgm_spent} STGM (estimated)")
    print(f"  PER FILE:      {round(stgm_spent / 100, 3)} STGM avg")
    print(f"\n  REPAIR EVENTS: {len(fix_events)}")
    print(f"  FAIL EVENTS:   {len(fail_events)}")
    print(f"  SCOUT EVENTS:  {len(scout_events)}")

    if still_broken:
        print(f"\n  UNRESOLVED ({len(still_broken)}):")
        for name, err in still_broken[:10]:
            print(f"    {name}: {err[:60]}")
        if len(still_broken) > 10:
            print(f"    ... and {len(still_broken) - 10} more")

    print("\n" + "═" * 60)
    print("  READY FOR PUBLICATION ON stigmergicoin.com")
    print("═" * 60 + "\n")

    # Save as JSON for the Vault / UI to consume
    report = {
        "total_files": 100,
        "fixed": len(fixed),
        "still_broken": len(still_broken),
        "skipped": len(skipped),
        "fix_rate_pct": fix_rate,
        "stgm_spent": stgm_spent,
        "stgm_per_file": round(stgm_spent / 100, 3),
        "repair_events": len(fix_events),
        "fail_events": len(fail_events),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    out = Path("benchmark_report.json")
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Report saved to: {out}")

if __name__ == "__main__":
    main()
