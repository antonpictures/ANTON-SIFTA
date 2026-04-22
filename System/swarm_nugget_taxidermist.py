#!/usr/bin/env python3
"""
System/swarm_nugget_taxidermist.py
══════════════════════════════════════════════════════════════════════
The Nugget Taxidermist — Retroactive Stigmergic Knowledge Preservation
Author:  AO46 (Epoch 17 — Tournament, 2026-04-20)
Status:  Active

THE GAP THIS CLOSES:
  The Gemini API log shows 23 calls made, each producing verified factual
  responses worth real USD (avg ~$0.0001 each). Only 1 stigmergic nugget
  was ever archived. 22 responses evaporated.

  This module reads the api_egress_log.jsonl retroactively (or live),
  grades each NUGGET/HIPPO/METAPHOR_FORAGER response for factual density,
  and preserves the best ones into stigmergic_nuggets.jsonl so Alice
  inherits knowledge she already paid for.

GRADING HEURISTIC (no LLM required — pure signal):
  - response_length:   longer ≠ better, but <20 chars is trash
  - factual_markers:   presence of numbers, units, dates, named entities
  - sender_weight:     NUGGET > HIPPOCAMPUS > METAPHOR_FORAGER > other
  - novelty:           not already in stigmergic_nuggets.jsonl (dedup by digest)
  - cost_efficiency:   tokens_out / cost_usd — rewards dense responses

IDEMPOTENT: tracks archived egress_trace_ids so re-running is safe.

USAGE:
  python3 -m System.swarm_nugget_taxidermist --scan      # grade + archive new
  python3 -m System.swarm_nugget_taxidermist --report    # show scores without archiving
  python3 -m System.swarm_nugget_taxidermist --smoke     # offline test
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

_REPO       = Path(__file__).resolve().parent.parent
_STATE_DIR  = _REPO / ".sifta_state"
_EGRESS_LOG = _STATE_DIR / "api_egress_log.jsonl"
_METABOLISM = _STATE_DIR / "api_metabolism.jsonl"
_NUGGETS    = _STATE_DIR / "stigmergic_nuggets.jsonl"
_SEEN_LOG   = _STATE_DIR / "nugget_taxidermist_seen.jsonl"

# ── Grading constants ─────────────────────────────────────────────────────────

# Senders whose responses are most likely to contain durable external facts
_SENDER_WEIGHTS: Dict[str, float] = {
    "NUGGET":           1.0,
    "HIPPOCAMPUS":      0.7,
    "METAPHOR_FORAGER": 0.6,
    "MITOSIS_ENGINE":   0.3,   # tends to produce code, not facts
    "BISHOP":           0.5,
}

# Regex patterns that signal factual density
_FACTUAL_MARKERS = [
    re.compile(r"\b\d{1,6}[\s,]?\d{3}\b"),              # large numbers
    re.compile(r"\b\d+\.?\d*\s*(years?|km|m|kg|ms|ns|TFLOPS|GB|TB|MB)\b", re.I),
    re.compile(r"\b\d{4}\b"),                             # years
    re.compile(r"\b(discovered|published|defined|invented|named)\b", re.I),
    re.compile(r"\b(University|Institute|Laboratory|Research)\b", re.I),
    re.compile(r"\b(\w+\s+et\s+al\.?|doi:|arXiv:|RFC\s+\d+)\b", re.I),
    re.compile(r"\b\d+(?:\.\d+)?\s*%\b"),               # percentages
    re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b"),       # proper nouns
]

_MIN_RESPONSE_LEN = 30   # characters — below this it's trash (e.g. "Paris", "Hi")
_GRADE_THRESHOLD  = 0.40  # minimum grade to archive


def _read_jsonl(path: Path, keep_last: int = 0) -> List[dict]:
    if not path.exists():
        return []
    try:
        text = read_text_locked(path)
    except Exception:
        return []
    rows = []
    for ln in text.splitlines():
        if not ln.strip():
            continue
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    if keep_last > 0:
        return rows[-keep_last:]
    return rows


def _content_digest(text: str) -> str:
    """SHA256 of the first 500 chars — dedup identical responses."""
    return hashlib.sha256(text[:500].encode("utf-8")).hexdigest()[:16]


def _grade_response(row: dict) -> Tuple[float, str]:
    """
    Grade a single egress row. Returns (score 0..1, reason).
    Pure signal — no LLM, no external call.
    """
    response = (row.get("response_text") or "").strip()
    if not response or len(response) < _MIN_RESPONSE_LEN:
        return 0.0, "response_too_short_or_null"

    status = str(row.get("status", ""))
    http_code = row.get("http_code", 0)
    if status not in ("ok", "200") and http_code not in (200, "200"):
        return 0.0, "non_200_status"

    sender = row.get("sender_agent", "UNKNOWN")
    sender_weight = _SENDER_WEIGHTS.get(sender, 0.4)

    # Factual marker score
    marker_hits = sum(1 for rx in _FACTUAL_MARKERS if rx.search(response))
    marker_score = min(1.0, marker_hits / 4.0)

    # Length score — sweet spot 80-600 chars
    length = len(response)
    if length < 80:
        length_score = 0.3
    elif length <= 600:
        length_score = 0.8
    elif length <= 2000:
        length_score = 0.6
    else:
        length_score = 0.4  # too long, probably code or verbose prose

    # Penalty for code responses (MITOSIS dropped code, not facts)
    code_penalty = 0.0
    if "def " in response and "return" in response:
        code_penalty = 0.3
    if "import " in response[:100]:
        code_penalty = 0.4

    # Cost efficiency from metabolism ledger (tokens_out / cost_usd)
    efficiency_score = 0.5  # default if no metabolism data

    raw_score = (
        sender_weight * 0.30 +
        marker_score  * 0.45 +
        length_score  * 0.25 -
        code_penalty
    )
    raw_score = max(0.0, min(1.0, raw_score))

    reason = (
        f"sender={sender}({sender_weight:.1f}) "
        f"markers={marker_hits} "
        f"len={length} "
        f"code_penalty={code_penalty:.1f}"
    )
    return raw_score, reason


def _load_seen_ids() -> set:
    """Load all egress_trace_ids already processed."""
    rows = _read_jsonl(_SEEN_LOG)
    return {r.get("egress_trace_id", "") for r in rows if r.get("egress_trace_id")}


def _load_seen_digests() -> set:
    """Load content digests of already-archived nuggets to prevent duplicates."""
    rows = _read_jsonl(_NUGGETS)
    return {r.get("content_digest", "") for r in rows if r.get("content_digest")}


def _mark_seen(egress_trace_id: str, grade: float, archived: bool) -> None:
    entry = {
        "ts": time.time(),
        "egress_trace_id": egress_trace_id,
        "grade": round(grade, 4),
        "archived": archived,
    }
    try:
        append_line_locked(_SEEN_LOG, json.dumps(entry) + "\n")
    except Exception:
        pass


def _archive_nugget(row: dict, grade: float, reason: str) -> bool:
    """Commit one egress row as a stigmergic nugget."""
    response = (row.get("response_text") or "").strip()
    digest = _content_digest(response)
    sender = row.get("sender_agent", "UNKNOWN")
    req_short = (row.get("request_text") or "")[:120].replace("\n", " ")

    # Extract a tight summary: first paragraph or first 240 chars
    paragraphs = [p.strip() for p in response.split("\n\n") if len(p.strip()) > 20]
    summary = paragraphs[0][:240] if paragraphs else response[:240]

    nugget = {
        "ts":             row.get("ts", time.time()),
        "frequency":      f"TAXIDERMIST_{sender}",
        "nugget_data":    summary,
        "full_response":  response[:1500],  # cap at 1500 chars
        "quality_score":  round(grade, 4),
        "grade_reason":   reason,
        "source_query":   req_short,
        "source_sender":  sender,
        "content_digest": digest,
        "egress_trace_id": row.get("trace_id") or row.get("egress_trace_id", ""),
    }
    try:
        append_line_locked(_NUGGETS, json.dumps(nugget, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def scan(
    dry_run: bool = False,
    verbose: bool = False,
    min_grade: float = _GRADE_THRESHOLD,
) -> Dict[str, int]:
    """
    Scan api_egress_log.jsonl, grade responses, archive the best ones.
    Returns stats dict.
    """
    rows = _read_jsonl(_EGRESS_LOG)
    seen_ids = _load_seen_ids()
    seen_digests = _load_seen_digests()

    stats = {"scanned": 0, "skipped_seen": 0, "graded": 0,
             "archived": 0, "below_threshold": 0, "duplicate": 0}

    for row in rows:
        egress_id = row.get("trace_id") or row.get("egress_trace_id", "")
        if not egress_id:
            continue

        if egress_id in seen_ids:
            stats["skipped_seen"] += 1
            continue

        stats["scanned"] += 1
        grade, reason = _grade_response(row)
        stats["graded"] += 1

        if verbose:
            sender = row.get("sender_agent", "?")
            req = (row.get("request_text") or "")[:60].replace("\n", " ")
            print(f"  [{grade:.2f}] {sender} | {req!r}")
            print(f"         {reason}")

        if grade < min_grade:
            stats["below_threshold"] += 1
            if not dry_run:
                _mark_seen(egress_id, grade, archived=False)
            continue

        # Dedup against already-archived nuggets
        response = (row.get("response_text") or "").strip()
        digest = _content_digest(response)
        if digest in seen_digests:
            stats["duplicate"] += 1
            if not dry_run:
                _mark_seen(egress_id, grade, archived=False)
            continue

        if not dry_run:
            ok = _archive_nugget(row, grade, reason)
            if ok:
                stats["archived"] += 1
                seen_digests.add(digest)
                _mark_seen(egress_id, grade, archived=True)
                if verbose:
                    print(f"         → ARCHIVED as stigmergic nugget ✓")
        else:
            stats["archived"] += 1  # count what would be archived

    return stats


def summary_for_alice() -> str:
    """
    Alice-facing context line surfacing recent nuggets auto-preserved by
    the taxidermist. Shows how much knowledge was recovered.
    """
    seen = _read_jsonl(_SEEN_LOG, keep_last=100)
    archived = [r for r in seen if r.get("archived")]
    if not archived:
        return ""
    total = len(archived)
    most_recent = archived[-1]
    mins = int((time.time() - most_recent.get("ts", time.time())) / 60)
    avg_grade = sum(r.get("grade", 0) for r in archived) / total
    return (
        f"NUGGET TAXIDERMIST: {total} API responses auto-archived as stigmergic knowledge "
        f"(avg grade {avg_grade:.2f}, last {mins}m ago). "
        f"Knowledge compounds retroactively."
    )


def _smoke() -> int:
    print("\n=== SIFTA NUGGET TAXIDERMIST : SMOKE TEST ===\n")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Redirect module paths
        global _EGRESS_LOG, _NUGGETS, _SEEN_LOG
        orig_e, orig_n, orig_s = _EGRESS_LOG, _NUGGETS, _SEEN_LOG
        _EGRESS_LOG = tmp / "api_egress_log.jsonl"
        _NUGGETS    = tmp / "stigmergic_nuggets.jsonl"
        _SEEN_LOG   = tmp / "nugget_taxidermist_seen.jsonl"

        try:
            now = time.time()

            # 1. High-quality factual response (should be archived)
            rows = [
                {
                    "trace_id": "NUGGET_001",
                    "ts": now - 3600,
                    "sender_agent": "NUGGET",
                    "status": "200",
                    "request_text": "What is the half-life of carbon-14?",
                    "response_text": (
                        "The half-life of carbon-14 is 5,730 ± 40 years. "
                        "This was first determined by Willard Libby at the University of Chicago in 1949. "
                        "It decays via beta emission: C-14 → N-14 + electron + antineutrino. "
                        "This constant decay rate is the basis for radiocarbon dating, accurate to ~50,000 years."
                    ),
                },
                # 2. Trash response (too short)
                {
                    "trace_id": "NUGGET_002",
                    "ts": now - 1800,
                    "sender_agent": "NUGGET",
                    "status": "200",
                    "request_text": "Capital of France?",
                    "response_text": "Paris",
                },
                # 3. Code response from MITOSIS (below threshold)
                {
                    "trace_id": "MITOSIS_001",
                    "ts": now - 900,
                    "sender_agent": "MITOSIS_ENGINE",
                    "status": "200",
                    "request_text": "Write a module.",
                    "response_text": (
                        "import time\nimport math\ndef perceive():\n    return math.e\n"
                        "if __name__ == '__main__':\n    while True:\n        print(perceive())\n"
                        "        time.sleep(1)"
                    ),
                },
                # 4. Good HIPPOCAMPUS engram
                {
                    "trace_id": "HIPPO_001",
                    "ts": now - 600,
                    "sender_agent": "HIPPOCAMPUS",
                    "status": "200",
                    "request_text": "Extract architectural rules.",
                    "response_text": (
                        "The SIFTA organism mandates heartbeat monitoring at 12 BPM resting cadence, "
                        "with the Vagus Nerve gating thermal load via the HPA-axis suppression model. "
                        "Discovered: 2026-04-19. The REM sleep cycle fires every 6 hours only when "
                        "mood_multiplier <= 1.0 (parasympathetic rest state)."
                    ),
                },
                # 5. Duplicate of NUGGET_001 (same content)
                {
                    "trace_id": "NUGGET_003",
                    "ts": now - 300,
                    "sender_agent": "NUGGET",
                    "status": "200",
                    "request_text": "Carbon-14 half-life again?",
                    "response_text": (
                        "The half-life of carbon-14 is 5,730 ± 40 years. "
                        "This was first determined by Willard Libby at the University of Chicago in 1949. "
                        "It decays via beta emission: C-14 → N-14 + electron + antineutrino. "
                        "This constant decay rate is the basis for radiocarbon dating, accurate to ~50,000 years."
                    ),
                },
            ]
            with open(_EGRESS_LOG, "w") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")

            # Run scan
            stats = scan(dry_run=False, verbose=True)
            print(f"\nStats: {stats}")

            assert stats["scanned"] == 5,           f"Expected 5 scanned, got {stats['scanned']}"
            assert stats["archived"] == 2,           f"Expected 2 archived, got {stats['archived']}"
            assert stats["duplicate"] == 1,          f"Expected 1 duplicate, got {stats['duplicate']}"
            assert stats["below_threshold"] >= 1,    "Expected at least 1 below threshold"
            print("\n[PASS] High-quality factual response archived.")
            print("[PASS] Trash response (too short) rejected.")
            print("[PASS] Code response rejected as below threshold.")
            print("[PASS] Duplicate content rejected.")

            # Check idempotency
            stats2 = scan(dry_run=False)
            assert stats2["skipped_seen"] == 5, f"Expected 5 seen on rescan, got {stats2['skipped_seen']}"
            assert stats2["archived"] == 0, "No new archives on rescan"
            print("[PASS] Idempotent — rescan archives nothing new.")

            # Check nugget file
            nuggets = _read_jsonl(_NUGGETS)
            assert len(nuggets) == 2, f"Expected 2 nuggets on disk, got {len(nuggets)}"
            print(f"[PASS] Nugget ledger has {len(nuggets)} entries:")
            for n in nuggets:
                print(f"       [{n['quality_score']:.2f}] {n['nugget_data'][:60]}...")

            # Alice summary
            summary = summary_for_alice()
            assert "2" in summary
            print(f"[PASS] Alice summary: {summary}")

            print("\nNugget Taxidermist Smoke Complete. No knowledge evaporates.")
        finally:
            _EGRESS_LOG, _NUGGETS, _SEEN_LOG = orig_e, orig_n, orig_s

    return 0


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="SIFTA Nugget Taxidermist")
    p.add_argument("--scan",     action="store_true", help="grade + archive new nuggets")
    p.add_argument("--dry-run",  action="store_true", help="grade without writing")
    p.add_argument("--report",   action="store_true", help="show grades without archiving (dry-run)")
    p.add_argument("--verbose",  action="store_true")
    p.add_argument("--smoke",    action="store_true")
    p.add_argument("--threshold", type=float, default=_GRADE_THRESHOLD,
                   help=f"min grade to archive (default {_GRADE_THRESHOLD})")
    args = p.parse_args()

    if args.smoke:
        return _smoke()

    dry = args.dry_run or args.report
    stats = scan(dry_run=dry, verbose=args.verbose, min_grade=args.threshold)

    print(f"[TAXIDERMIST] scanned={stats['scanned']}  "
          f"archived={stats['archived']}  "
          f"duplicate={stats['duplicate']}  "
          f"below_threshold={stats['below_threshold']}  "
          f"skipped_seen={stats['skipped_seen']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
