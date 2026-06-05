#!/usr/bin/env python3
"""cortex_usage_audit.py — which installed models are actually USED, so you can
delete the dead weight off the hard drive (receipts decide, not guesses).

Cross-references INSTALLED models (ollama /api/tags + local MLX model dirs)
against USAGE in the .sifta_state ledgers. Flags installed models with no recent
use as deletion candidates and prints the exact remove command. It NEVER deletes
anything — you review and run the commands yourself.

Run on the Mac:  python3 tools/cortex_usage_audit.py [--days 14]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
TAGS = "http://localhost:11434/api/tags"
LEDGERS = (
    "primary_cortex_switches.jsonl", "agent_arm_receipts.jsonl",
    "work_receipts.jsonl", "ide_stigmergic_trace.jsonl", "episodic_diary.jsonl",
    "corvid_apprentice_trace.jsonl", "cortex_route_receipts.jsonl",
)
PROTECTED = ("alice-m5-cortex-8b",)  # never suggest removing the main brain
RETIRED_DEDICATED_MODELS = (
    "sifta-classifier-c1-3.1b-6.2gb",
    "alice-q-m1-scout-2.3b-2.7gb",
)


def installed_ollama() -> dict[str, int]:
    try:
        with urllib.request.urlopen(TAGS, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        return {m["name"]: (m.get("size") or 0) for m in data.get("models", [])}
    except Exception as exc:
        print(f"[warn] ollama not reachable ({exc}); skipping ollama models", file=sys.stderr)
        return {}


def installed_mlx() -> dict[str, tuple[int, Path]]:
    out: dict[str, tuple[int, Path]] = {}
    for base in (Path.home() / "Music/ANTON_SIFTA/models", Path.home() / ".cache/huggingface/hub"):
        if not base.exists():
            continue
        for d in base.iterdir():
            n = d.name.lower()
            if d.is_dir() and any(k in n for k in ("mlx", "gemma-4-12b", "qwopus", "superagentic")):
                size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                out[d.name] = (size, d)
    return out


def load_ledger_lines() -> list[tuple[float, str]]:
    lines: list[tuple[float, str]] = []
    for lname in LEDGERS:
        p = STATE / lname
        if not p.exists():
            continue
        for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not raw.strip():
                continue
            ts = 0.0
            try:
                ts = float(json.loads(raw).get("ts") or 0)
            except Exception:
                pass
            lines.append((ts, raw))
    return lines


def usage_for(name: str, lines: list[tuple[float, str]], cutoff: float) -> tuple[int, float]:
    base = name.split(":")[0]
    count, last = 0, 0.0
    for ts, text in lines:
        if base and base in text:
            count += 1
            if ts >= cutoff:
                last = max(last, ts)
    return count, last


def _gb(n) -> float:
    return round((n or 0) / 1e9, 2)


def _verdict(name: str, count: int, last: float) -> str:
    if any(p in name.lower() for p in RETIRED_DEDICATED_MODELS):
        return "REMOVE(retired)"
    if any(p in name.lower() for p in PROTECTED):
        return "KEEP(core)"
    if last:
        return "USED"
    return "stale" if count else "UNUSED"


def main() -> int:
    ap = argparse.ArgumentParser(description="Which installed models are dead weight?")
    ap.add_argument("--days", type=int, default=14, help="window for 'recently used'")
    args = ap.parse_args()

    lines = load_ledger_lines()
    cutoff = time.time() - args.days * 86400
    candidates: list[str] = []

    print(f"=== INSTALLED MODELS vs USAGE (last {args.days} days, {len(lines)} ledger rows) ===\n")
    print(f"  {'where':5s} {'model':44s} {'size':>8s} {'uses':>6s} recent  verdict")
    print("  " + "-" * 82)

    for name, size in sorted(installed_ollama().items()):
        c, last = usage_for(name, lines, cutoff)
        v = _verdict(name, c, last)
        print(f"  [oll] {name[:44]:44s} {_gb(size):6.2f}GB {c:>6}  {'yes' if last else 'no':3s}   {v}")
        if v in ("UNUSED", "stale", "REMOVE(retired)"):
            candidates.append(f"ollama rm {name}")

    for name, (size, path) in sorted(installed_mlx().items()):
        c, last = usage_for(name, lines, cutoff)
        v = _verdict(name, c, last)
        print(f"  [mlx] {name[:44]:44s} {_gb(size):6.2f}GB {c:>6}  {'yes' if last else 'no':3s}   {v}")
        if v in ("UNUSED", "stale"):
            candidates.append(f"rm -rf '{path}'   # MLX dir for {name} — confirm the path before running")

    print("\n=== DELETION CANDIDATES (review first — this tool deletes NOTHING) ===")
    if not candidates:
        print("  none flagged in this window.")
    for c in candidates:
        print("  " + c)
    print("\n  Rules: never auto-run these; keep alice-m5-cortex-8b. The old dedicated")
    print("  sifta-classifier and alice-Q-m1-scout tags are retired; if they reappear, remove them")
    print("  unless a fresh tournament receipt proves they beat the shared Gemma path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
