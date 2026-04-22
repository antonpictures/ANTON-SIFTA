#!/usr/bin/env python3
"""
System/swarm_dirt_nugget_miner.py
══════════════════════════════════════════════════════════════════════
Dirt Nugget Miner (Tournament Intel Lobe)

Scans pending-review dirt artifacts and surfaces high-leverage, concrete
"nuggets" for integration. This is a read-only analyst: it does not modify
the source files it scans.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

REPO = Path(__file__).resolve().parent.parent
DIRT_DIR = REPO / "Archive" / "bishop_drops_pending_review"
DEFAULT_REPORT_MD = REPO / "Documents" / "dirt_nuggets_report.md"
DEFAULT_REPORT_JSON = REPO / "Documents" / "dirt_nuggets_report.json"

SIGNAL_PATTERNS = {
    "pending": re.compile(r"\bPENDING\b", re.IGNORECASE),
    "todo": re.compile(r"\bTODO\b", re.IGNORECASE),
    "fixme": re.compile(r"\bFIXME\b", re.IGNORECASE),
    "bug": re.compile(r"\bBUG\b|\bERROR\b|\bFAIL(?:ED|URE)?\b", re.IGNORECASE),
    "integration": re.compile(r"\bINTEGRAT(?:E|ION|ED)\b", re.IGNORECASE),
    "safety": re.compile(r"\bVETO\b|\bGUARDRAIL\b|\bWHITELIST\b", re.IGNORECASE),
    "tests": re.compile(r"\bSMOKE\b|\bTEST\b", re.IGNORECASE),
    "missing": re.compile(r"\bMISSING\b|\bNOT FOUND\b", re.IGNORECASE),
}

SNIPPET_PATTERNS = [
    re.compile(r"\bTODO\b.*", re.IGNORECASE),
    re.compile(r"\bFIXME\b.*", re.IGNORECASE),
    re.compile(r"\bPENDING\b.*", re.IGNORECASE),
    re.compile(r"\bmissing\b.*", re.IGNORECASE),
    re.compile(r"\bsmoke\b.*", re.IGNORECASE),
    re.compile(r"\bveto\b.*", re.IGNORECASE),
]


@dataclass
class Nugget:
    file: str
    kind: str
    score: int
    reason: str
    sha12: str
    snippets: List[str]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _collect_files(dirt_dir: Path) -> List[Path]:
    if not dirt_dir.exists():
        return []
    candidates = []
    for p in dirt_dir.iterdir():
        if p.is_file() and (p.suffix == ".dirt" or p.suffix == ".py"):
            candidates.append(p)
    return sorted(candidates, key=lambda p: p.name.lower())


def _classify(path: Path) -> str:
    name = path.name.upper()
    if "INTEGRATED" in name:
        return "integrated"
    if "PENDING" in name:
        return "pending"
    return "review"


def _score_text(text: str, kind: str) -> tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []
    if kind == "pending":
        score += 5
        reasons.append("pending file")
    elif kind == "review":
        score += 2
        reasons.append("review queue")

    for name, pattern in SIGNAL_PATTERNS.items():
        hits = len(pattern.findall(text))
        if hits <= 0:
            continue
        if name in {"pending", "todo", "fixme", "bug", "missing"}:
            delta = min(10, hits * 2)
        else:
            delta = min(6, hits)
        score += delta
        reasons.append(f"{name}x{hits}")

    # Long files with no signals should not dominate.
    if len(text) < 120 and score > 0:
        score -= 1
    return max(0, score), reasons


def _snippets(text: str, limit: int = 4) -> List[str]:
    out: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if len(line) > 180:
            line = line[:177] + "..."
        if any(p.search(line) for p in SNIPPET_PATTERNS):
            out.append(line)
            if len(out) >= limit:
                break
    return out


def mine_nuggets(dirt_dir: Path) -> List[Nugget]:
    nuggets: List[Nugget] = []
    for file in _collect_files(dirt_dir):
        text = _read_text(file)
        if not text:
            continue
        kind = _classify(file)
        score, reasons = _score_text(text, kind)
        if score <= 0:
            continue
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        nuggets.append(
            Nugget(
                file=str(file.relative_to(REPO)),
                kind=kind,
                score=score,
                reason=", ".join(reasons),
                sha12=digest,
                snippets=_snippets(text),
            )
        )
    nuggets.sort(key=lambda n: (-n.score, n.file))
    return nuggets


def _write_reports(nuggets: Iterable[Nugget], out_md: Path, out_json: Path, top_n: int) -> None:
    rows = list(nuggets)
    top = rows[:top_n]

    payload = {
        "ts": time.time(),
        "dirt_dir": str(DIRT_DIR.relative_to(REPO)),
        "total_ranked": len(rows),
        "top_n": top_n,
        "top": [
            {
                "file": n.file,
                "kind": n.kind,
                "score": n.score,
                "reason": n.reason,
                "sha12": n.sha12,
                "snippets": n.snippets,
            }
            for n in top
        ],
    }
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# SIFTA Dirt Nugget Report",
        "",
        f"*Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        f"- Source dir: `{DIRT_DIR.relative_to(REPO)}`",
        f"- Ranked artifacts: **{len(rows)}**",
        f"- Top nuggets shown: **{len(top)}**",
        "",
        "## Top Nuggets",
        "",
    ]

    if not top:
        lines.append("No high-signal nuggets found.")
    else:
        for idx, nugget in enumerate(top, start=1):
            lines.extend(
                [
                    f"### {idx}. `{nugget.file}`",
                    f"- kind: `{nugget.kind}`",
                    f"- score: **{nugget.score}**",
                    f"- signals: {nugget.reason}",
                    f"- sha12: `{nugget.sha12}`",
                ]
            )
            if nugget.snippets:
                lines.append("- snippets:")
                for s in nugget.snippets:
                    lines.append(f"  - `{s}`")
            lines.append("")

    out_md.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mine high-signal integration nuggets from pending dirt artifacts."
    )
    parser.add_argument("--top", type=int, default=8, help="top ranked nuggets to publish")
    parser.add_argument("--out-md", default=str(DEFAULT_REPORT_MD), help="markdown report path")
    parser.add_argument("--out-json", default=str(DEFAULT_REPORT_JSON), help="json report path")
    args = parser.parse_args()

    out_md = Path(args.out_md)
    out_json = Path(args.out_json)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    nuggets = mine_nuggets(DIRT_DIR)
    _write_reports(nuggets, out_md, out_json, top_n=max(1, args.top))

    print(f"[+] Nugget mining complete. Ranked {len(nuggets)} artifacts.")
    print(f"[+] Markdown report: {out_md}")
    print(f"[+] JSON report: {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
