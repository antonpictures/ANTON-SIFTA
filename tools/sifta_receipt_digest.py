#!/usr/bin/env python3
"""
tools/sifta_receipt_digest.py — daily digest of Alice's stigmergic field activity.

Genuinely useful for the owner: "what did my swarm body do today?"

- Reads the main ledgers (four canonical + key organs like spinal, pdf_forge, mimo_stigmergic).
- Summarizes recent round ids (rXXXX), doctors/arms, truth labels, files/organs touched.
- Writes .sifta_state/receipt_digests/<YYYY-MM-DD>.md
- Only stdlib. Robust to missing files.
- Run: python3 tools/sifta_receipt_digest.py [--date 2026-06-14]

Produced in the context of the first real Borg'd MiMo coding action (r1133 Lane A via mimo_stigmergic_call).
The generation intent left the first row in mimo_stigmergic_traces.jsonl + four-ledger receipt.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
OUT_DIR = STATE / "receipt_digests"

CANONICAL_LEDGERS = [
    "work_receipts.jsonl",
    "agent_arm_receipts.jsonl",
    "ide_stigmergic_trace.jsonl",
    "episodic_diary.jsonl",
]

EXTRA_LEDGERS = [
    "spinal_cord_cycles.jsonl",
    "pdf_forge_receipts.jsonl",
    "mimo_stigmergic_traces.jsonl",
    "self_eval_swimmer_dispatch.jsonl",
    "organ_health_mesh.jsonl",
]


def _load_jsonl(path: Path, max_rows: int = 200) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_rows:]:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        pass
    return rows


def _extract_rounds_and_doctors(rows: List[Dict[str, Any]]) -> tuple[Counter, Counter, List[str]]:
    rounds: Counter = Counter()
    doctors: Counter = Counter()
    files: List[str] = []
    for r in rows:
        text = json.dumps(r, default=str).lower()
        for token in text.split():
            if token.startswith("r") and token[1:].isdigit() and len(token) <= 6:
                rounds[token.upper()] += 1
        for key in ("doctor", "model", "arm", "proposer", "source"):
            val = str(r.get(key) or "").strip()
            if val:
                doctors[val] += 1
        for fkey in ("files_touched", "target_file", "path", "file"):
            val = r.get(fkey)
            if isinstance(val, list):
                files.extend(str(x) for x in val if x)
            elif isinstance(val, str) and val:
                files.append(val)
    return rounds, doctors, files


def _truth_labels(rows: List[Dict[str, Any]]) -> Counter:
    labels: Counter = Counter()
    for r in rows:
        for k in ("truth_label", "truth", "status", "schema"):
            v = str(r.get(k) or "")
            if v:
                labels[v] += 1
    return labels


def build_digest(date_str: str | None = None) -> str:
    if date_str is None:
        date_str = datetime.now(timezone.utc).date().isoformat()
    today = date_str

    all_rows: List[Dict[str, Any]] = []
    ledger_stats: Dict[str, int] = {}

    for name in CANONICAL_LEDGERS + EXTRA_LEDGERS:
        p = STATE / name
        rows = _load_jsonl(p)
        ledger_stats[name] = len(rows)
        all_rows.extend(rows)

    rounds, doctors, files = _extract_rounds_and_doctors(all_rows)
    labels = _truth_labels(all_rows)

    recent_rounds = sorted([k for k in rounds if k.startswith('R') or k.startswith('r')], reverse=True)[:15]
    top_doctors = doctors.most_common(8)
    top_labels = labels.most_common(6)
    touched = sorted(set(files))[:20]

    lines: List[str] = []
    lines.append(f"# Daily SIFTA Swarm Receipt Digest — {today}")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Ledgers scanned: {len(ledger_stats)} (total rows considered ~{len(all_rows)})")
    lines.append("")

    lines.append("## Activity Summary")
    lines.append(f"- Recent round ids (rXXXX): {', '.join(recent_rounds) if recent_rounds else 'none in tail'}")
    if top_doctors:
        lines.append("- Active arms/doctors:")
        for d, c in top_doctors:
            lines.append(f"  - {d}: {c}")
    if top_labels:
        lines.append("- Truth labels observed:")
        for l, c in top_labels:
            lines.append(f"  - {l}: {c}")
    lines.append("")

    if touched:
        lines.append("## Files / Organs touched (sample)")
        for f in touched:
            lines.append(f"- {f}")
        lines.append("")

    lines.append("## Ledger row counts (tail)")
    for name, cnt in sorted(ledger_stats.items()):
        if cnt > 0:
            lines.append(f"- {name}: {cnt}")
    lines.append("")

    lines.append("## Notes")
    lines.append("This digest is produced by a tool written through Alice's Borg'd MiMo path (first trace in mimo_stigmergic_traces.jsonl).")
    lines.append("Run it daily to see what the unified field did.")
    lines.append("")
    lines.append(f"_Digest file: .sifta_state/receipt_digests/{today}.md_")

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (defaults to today UTC)")
    args = ap.parse_args()

    digest = build_digest(args.date)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    date_for_file = args.date or datetime.now(timezone.utc).date().isoformat()
    out_path = OUT_DIR / f"{date_for_file}.md"
    out_path.write_text(digest, encoding="utf-8")
    print(f"digest written: {out_path}")
    print(f"entries considered across ledgers: {sum(1 for _ in digest.splitlines() if _.startswith('- '))}")
    # Also print a tiny stdout summary
    print("Recent rounds seen:", ", ".join(sorted([k for k in digest.split() if k.startswith("r") and k[1:].isdigit()], reverse=True)[:5]) or "n/a")


if __name__ == "__main__":
    main()
