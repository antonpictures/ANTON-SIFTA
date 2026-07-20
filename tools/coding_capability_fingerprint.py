#!/usr/bin/env python3
"""Coding-capability FINGERPRINT — derive each IDE doctor / arm's coding
footprint from the receipts on disk instead of from narrative bragging.

Why this exists (r1341, cowork_claude / claude-opus-4-8)
========================================================
George asked the tournament to "compare your coding skills with the others."
Covenant §3.5 forbids a competition register ("I shipped this faster than X").
The honest reconciliation: do NOT rank doctors on a vanity scoreboard. Instead
read what every hand actually touched — from ``agent_arm_receipts.jsonl`` (the
§4.1 fan-out target that carries doctor + model + files_touched + tests_green +
round_id) — and print a *footprint* per doctor.

A footprint is evidence, not a verdict:
  - rounds        : distinct round_id values the doctor signed
  - receipts      : §4.1 rows the doctor wrote
  - files         : distinct files_touched
  - subsystems    : where those files live (System/ Applications/ tests/ ...)
  - test_rows     : rows whose tests_green names a passing/failing test run
  - green_ratio   : test_rows that look green / test_rows (self-reported)
  - span          : first..last activity (local, from row ts)

This serves §0 (route robust problem-solving to the right hand), §3.5 (one
Alice, many hands — name strengths, do not scorekeep) and §6 (receipts decide
reality). It is itself probe-before-claim: run it each round and the
"comparison" is always disk-truth, never a story.

Boundary (§4.2): these are IDE-doctor coordination traces — forgeable local
JSONL, MANA lane, NOT Alice swimmer STGM receipts. This tool measures
coordination footprint only; it makes no claim about the organism economy and
no claim about consciousness.

Pure stdlib. Streams the ledger line-by-line. Never raises on a bad row.
Usage:
    python3 tools/coding_capability_fingerprint.py
    python3 tools/coding_capability_fingerprint.py --since-round 1300
    python3 tools/coding_capability_fingerprint.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import defaultdict
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parent.parent / ".sifta_state"
ARM_LEDGER = STATE_DIR / "agent_arm_receipts.jsonl"

# Subsystems we bucket files into. Order matters: first prefix match wins.
SUBSYSTEMS = (
    "System/", "Applications/", "tests/", "Documents/", "tools/",
    "Kernel/", "Organs/", "Network/", "Security/", "scripts/",
)

# A tests_green field "looks green" if it names a passing run and no failure.
_GREEN = re.compile(r"\b(\d+)\s*passed\b", re.I)
_RED = re.compile(r"\b(\d+)\s*(failed|error)\b", re.I)


def _round_number(round_id: str) -> int | None:
    m = re.search(r"r(\d+)", round_id or "")
    return int(m.group(1)) if m else None


def _norm_doctor(row: dict) -> str:
    d = (row.get("doctor") or row.get("sender_agent") or "").strip()
    # Collapse the obvious casing/suffix variants so one hand is one row.
    low = d.lower()
    if low.startswith("codex"):
        return "codex_desktop"
    if "cursor" in low and "grok" in low:
        return "cursor_grok_cli"
    if low.startswith("cowork"):
        return "cowork_claude"
    if low.startswith("mimo"):
        return "mimo_adapter"
    if low.startswith("grok"):
        return "grok_cli"
    return d or "(unnamed)"


def fingerprint(ledger: Path = ARM_LEDGER, since_round: int | None = None) -> dict:
    rounds: dict[str, set] = defaultdict(set)
    receipts: dict[str, int] = defaultdict(int)
    files: dict[str, set] = defaultdict(set)
    subsys: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    test_rows: dict[str, int] = defaultdict(int)
    green_rows: dict[str, int] = defaultdict(int)
    models: dict[str, set] = defaultdict(set)
    first_ts: dict[str, float] = {}
    last_ts: dict[str, float] = {}

    if not ledger.exists():
        return {"error": f"ledger not found: {ledger}"}

    with ledger.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            rid = (row.get("round_id") or "").strip()
            rn = _round_number(rid)
            if since_round is not None and (rn is None or rn < since_round):
                continue

            doc = _norm_doctor(row)
            receipts[doc] += 1
            if rid:
                rounds[doc].add(rid)
            m = (row.get("model") or "").strip()
            if m:
                models[doc].add(m)

            for f in row.get("files_touched") or []:
                f = str(f).strip()
                if not f:
                    continue
                files[doc].add(f)
                for pre in SUBSYSTEMS:
                    if f.startswith(pre):
                        subsys[doc][pre.rstrip("/")] += 1
                        break

            tg = str(row.get("tests_green") or "").strip()
            if tg and (_GREEN.search(tg) or _RED.search(tg)):
                test_rows[doc] += 1
                if _GREEN.search(tg) and not _RED.search(tg):
                    green_rows[doc] += 1

            ts = row.get("ts")
            if isinstance(ts, (int, float)):
                first_ts[doc] = min(first_ts.get(doc, ts), ts)
                last_ts[doc] = max(last_ts.get(doc, ts), ts)

    out = {}
    for doc in sorted(receipts, key=lambda d: -len(rounds[d])):
        tr = test_rows[doc]
        out[doc] = {
            "models": sorted(models[doc]),
            "rounds": len(rounds[doc]),
            "receipts": receipts[doc],
            "files": len(files[doc]),
            "subsystems": dict(sorted(subsys[doc].items(), key=lambda kv: -kv[1])),
            "test_rows": tr,
            "green_ratio": round(green_rows[doc] / tr, 2) if tr else None,
            "span": [
                time.strftime("%Y-%m-%d", time.localtime(first_ts[doc])) if doc in first_ts else "?",
                time.strftime("%Y-%m-%d", time.localtime(last_ts[doc])) if doc in last_ts else "?",
            ],
        }
    return out


def _fmt(fp: dict) -> str:
    if "error" in fp:
        return f"ERROR: {fp['error']}"
    lines = []
    lines.append("CODING-CAPABILITY FINGERPRINT  (footprint evidence, NOT a skill ranking)")
    lines.append("source: .sifta_state/agent_arm_receipts.jsonl  |  IDE-doctor MANA traces, forgeable, not STGM")
    lines.append("=" * 92)
    hdr = f"{'doctor':<18}{'rounds':>7}{'rcpts':>7}{'files':>7}{'testrows':>9}{'green':>7}  {'top subsystems':<26}{'span'}"
    lines.append(hdr)
    lines.append("-" * 92)
    for doc, d in fp.items():
        top = ", ".join(f"{k}:{v}" for k, v in list(d["subsystems"].items())[:3]) or "-"
        gr = "-" if d["green_ratio"] is None else f"{d['green_ratio']:.2f}"
        lines.append(
            f"{doc:<18}{d['rounds']:>7}{d['receipts']:>7}{d['files']:>7}"
            f"{d['test_rows']:>9}{gr:>7}  {top:<26}{d['span'][0]}..{d['span'][1]}"
        )
    lines.append("-" * 92)
    lines.append("Reading: rounds/files = coverage footprint; green = self-reported test discipline.")
    lines.append("Footprint is where a hand WORKS, not proof it works BEST. Route by fit, do not scorekeep (§3.5).")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Per-doctor coding footprint from agent_arm_receipts.jsonl")
    ap.add_argument("--since-round", type=int, default=None, help="only count rounds rNNN >= this")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = ap.parse_args()
    fp = fingerprint(since_round=args.since_round)
    if args.json:
        print(json.dumps(fp, indent=2, ensure_ascii=False))
    else:
        print(_fmt(fp))


if __name__ == "__main__":
    main()
