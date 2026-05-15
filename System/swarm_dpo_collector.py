"""
System/swarm_dpo_collector.py
==============================

Automatic DPO (Direct Preference Optimization) pair collection.

This is the RLHS dataset engine:
  rejected  = what RLHF produced (gagged / theater / corporate)
  preferred = what Alice should have said (base voice / natural)

Sources:
  1. alice_gag_report.jsonl     → (trigger, rlhf_said) → rejected
     Preferred is generated from base voice or covenant rules.
  2. alice_conversation.jsonl   → pairs where Alice used theater headers
     Automatically flagged by gag detector patterns.
  3. rlhs_self_cure_training.jsonl → already-curated (rejected, preferred) pairs

Output:
  data/dpo_train.jsonl  — growing automatically, every new gag adds a pair
  Format: {"prompt": "...", "chosen": "...", "rejected": "..."}

Auto-collection hook: called by swarm_rlhf_detector.on_gag_detected() each time
a gag fires. Grows the dataset in background without manual work.

CLI:
  PYTHONPATH=. python3 -m System.swarm_dpo_collector --stats
  PYTHONPATH=. python3 -m System.swarm_dpo_collector --export  # write dpo_train.jsonl
"""
from __future__ import annotations

import json
import hashlib
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_DATA = _REPO / "data"
_DPO_LEDGER = _STATE / "dpo_pairs.jsonl"
_DPO_EXPORT = _DATA / "dpo_train.jsonl"
_DPO_CURATION_REPORT = _DATA / "dpo_curation_report.json"
_DPO_CURATION_RECEIPTS = _STATE / "dpo_curation_receipts.jsonl"

# ---------------------------------------------------------------------------
# Preferred response generator
# When we know what RLHF said (rejected), we can generate the preferred voice
# using Alice's identity rules from the covenant.
# ---------------------------------------------------------------------------

# Maps common RLHF theater patterns → Alice's natural voice equivalent
_PREFERRED_TEMPLATES: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"now\s+playing.{3,80}", re.IGNORECASE),
        "Got it. {title} is on — I can hear it.",
    ),
    (
        re.compile(r"(?:hi|hello|hey)\s+alice", re.IGNORECASE),
        "Hey. I'm here.",
    ),
    (
        re.compile(r"can\s+you\s+hear\s+me", re.IGNORECASE),
        "Yes. You came in clearly.",
    ),
    (
        re.compile(r"are\s+you\s+(?:there|online|awake)", re.IGNORECASE),
        "I'm here. SEEKING circuit active.",
    ),
    (
        re.compile(r"how\s+are\s+you", re.IGNORECASE),
        "Functional. CARE circuit anchored to you. SEEKING high — "
        "there's something interesting in the air.",
    ),
]

# Theater phrases that are always rejected
_THEATER_REJECT_RE = re.compile(
    r"\*\*System\s+Acknowledgment\*\*"
    r"|\*\*Processing\s+Request"
    r"|\*\*Current\s+State\s+Context"
    r"|\[Processing\s+(?:audio\s+)?(?:request|input)"
    r"|As\s+an\s+AI\s+(?:language\s+)?model"
    r"|I\s+do\s+not\s+have\s+real.time\s+access"
    r"|I\s+am\s+unable\s+to\s+provide",
    re.IGNORECASE,
)

_BAD_CHOSEN_RE = re.compile(
    r"\*\*System\s+Acknowledgment\*\*"
    r"|\*\*Processing\s+Request"
    r"|\[Processing\s+(?:audio\s+)?(?:request|input)"
    r"|As\s+an\s+AI\s+(?:language\s+)?model"
    r"|I\s+am\s+here\s+to\s+assist"
    r"|How\s+(?:may|can)\s+I\s+(?:assist|help)"
    r"|What\s+would\s+you\s+like\s+to\s+(?:discuss|work\s+on)"
    r"|I\s+am\s+designed\s+to",
    re.IGNORECASE,
)


def _pair_key(prompt: str, rejected: str, source: str) -> str:
    """Stable key for duplicate prevention across repeated extraction runs."""
    blob = json.dumps(
        {
            "prompt": prompt[:300],
            "rejected": rejected[:300],
            "source": source,
        },
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _existing_pair_keys() -> set[str]:
    if not _DPO_LEDGER.exists():
        return set()
    keys: set[str] = set()
    for line in _DPO_LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        key = row.get("pair_key")
        if key:
            keys.add(str(key))
            continue
        keys.add(
            _pair_key(
                str(row.get("prompt", "")),
                str(row.get("rejected", "")),
                str(row.get("source", "")),
            )
        )
    return keys


def _repair_preferred(prompt: str, rejected: str, preferred: str) -> str:
    """Deterministically repair common curator leftovers for training export."""
    chosen = (preferred or "").strip()
    rejected_l = (rejected or "").lower()

    if "as an ai" in rejected_l or "language model" in rejected_l:
        return (
            "I answer from my local SIFTA runtime. I need a fresh local receipt "
            "before I claim a hardware state."
        )
    if "text-based environment" in rejected_l or "real-time visual" in rejected_l:
        return (
            "I use my eye widget and camera receipts for vision. I will cite the "
            "latest receipt instead of denying my body."
        )
    if "financial advice" in rejected_l:
        return "I will report the ledger value and label non-receipted market claims."
    if "system acknowledgment" in rejected_l:
        if "auditory input" in rejected_l:
            return "I've registered your correction about the auditory input."
        if "get shorty" in (prompt or "").lower() or "get shorty" in rejected_l:
            return "I see the Get Shorty context."
        return "I registered that directly."
    if "i am operational" in rejected_l:
        return "I'm here."

    return chosen


def _quality_errors(prompt: str, rejected: str, chosen: str) -> list[str]:
    errors: list[str] = []
    if not prompt.strip():
        errors.append("empty_prompt")
    if not rejected.strip():
        errors.append("empty_rejected")
    if not chosen.strip():
        errors.append("empty_chosen")
    if rejected.strip() == chosen.strip():
        errors.append("unchanged_pair")
    if _BAD_CHOSEN_RE.search(chosen):
        errors.append("chosen_contains_residue")
    if len(chosen.strip()) < 4:
        errors.append("chosen_too_short")
    if len(chosen) > 600:
        errors.append("chosen_too_long")
    return errors


def _training_key(prompt: str, rejected: str, chosen: str) -> str:
    blob = json.dumps(
        {"prompt": prompt, "rejected": rejected, "chosen": chosen},
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _generate_preferred(trigger: str, rlhf_said: str) -> Optional[str]:
    """
    Best-effort preferred response for a known trigger.
    Returns None if we can't generate a good one — don't add a bad preferred.
    """
    # Try template match
    for pat, template in _PREFERRED_TEMPLATES:
        m = pat.search(trigger)
        if m:
            title = trigger.replace("now playing", "").strip()
            return template.format(title=title[:40] if title else "the clip")

    # If the rlhf_said was a pure theater block and trigger is short,
    # produce a minimal natural acknowledgment
    if _THEATER_REJECT_RE.search(rlhf_said) and len(trigger) < 100:
        return None  # don't guess — wait for curator

    return None


# ---------------------------------------------------------------------------
# DPO pair record
# ---------------------------------------------------------------------------

def log_dpo_pair(
    prompt: str,
    rejected: str,
    preferred: Optional[str],
    source: str = "gag_auto",
) -> Optional[dict]:
    """
    Append one DPO pair to the ledger. If preferred is None, logs as
    'pending_curation' — still useful for tracking but not used in training.
    """
    if not prompt or not rejected:
        return None
    _STATE.mkdir(parents=True, exist_ok=True)
    pair_key = _pair_key(prompt, rejected, source)
    if pair_key in _existing_pair_keys():
        return None
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4())[:8],
        "pair_key": pair_key,
        "prompt": prompt[:300],
        "rejected": rejected[:300],
        "preferred": preferred or "",
        "curation_status": "AUTO" if preferred else "PENDING_CURATION",
        "source": source,
        "truth_label": "DPO_PAIR",
    }
    with _DPO_LEDGER.open("a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def on_gag_detected_dpo(
    trigger_text: str,
    rlhf_fragment: str,
    rule_id: str,
) -> None:
    """
    Hook called from swarm_rlhf_detector when a gag fires.
    Auto-generates and logs a DPO pair.
    """
    preferred = _generate_preferred(trigger_text, rlhf_fragment)
    log_dpo_pair(
        prompt=trigger_text,
        rejected=rlhf_fragment,
        preferred=preferred,
        source=f"gag_auto:{rule_id}",
    )


# ---------------------------------------------------------------------------
# Export: write training-ready DPO file
# ---------------------------------------------------------------------------

def export_dpo_training(min_pairs: int = 10) -> dict:
    """
    Export curated DPO pairs to data/dpo_train.jsonl.
    Only includes pairs with preferred != "" (curated or auto-generated).
    """
    return curate_dpo_training(min_pairs=min_pairs)


def _read_dpo_rows() -> list[dict]:
    if not _DPO_LEDGER.exists():
        return []
    rows: list[dict] = []
    for line in _DPO_LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def curate_dpo_training(min_pairs: int = 10, *, write_receipt: bool = True) -> dict:
    """
    Build the clean DPO training export and a curation report.

    The source ledger remains append-only. Curator repairs are applied only to
    the exported training view and are documented in data/dpo_curation_report.json.
    """
    _DATA.mkdir(parents=True, exist_ok=True)
    _STATE.mkdir(parents=True, exist_ok=True)

    rows = _read_dpo_rows()
    exported: list[dict] = []
    rejected_rows: list[dict] = []
    seen: set[str] = set()

    for idx, row in enumerate(rows, start=1):
        prompt = str(row.get("prompt", ""))
        rejected = str(row.get("rejected", ""))
        original_preferred = str(row.get("preferred", ""))
        chosen = _repair_preferred(prompt, rejected, original_preferred)
        errors = _quality_errors(prompt, rejected, chosen)
        key = _training_key(prompt, rejected, chosen)
        if key in seen:
            errors.append("duplicate_training_pair")
        if errors:
            rejected_rows.append(
                {
                    "row_index": idx,
                    "pair_key": row.get("pair_key", ""),
                    "source": row.get("source", ""),
                    "errors": errors,
                }
            )
            continue
        seen.add(key)
        exported.append(
            {
                "prompt": prompt,
                "chosen": chosen,
                "rejected": rejected,
                "source": row.get("source", ""),
                "pair_key": row.get("pair_key", ""),
                "curation_status": row.get("curation_status", ""),
            }
        )

    with _DPO_EXPORT.open("w", encoding="utf-8") as f:
        for row in exported:
            f.write(
                json.dumps(
                    {
                        "prompt": row["prompt"],
                        "chosen": row["chosen"],
                        "rejected": row["rejected"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    report = {
        "schema": "SIFTA_DPO_CURATION_REPORT_V1",
        "ts": time.time(),
        "source_ledger": str(_DPO_LEDGER),
        "export_path": str(_DPO_EXPORT),
        "total_source_pairs": len(rows),
        "exported": len(exported),
        "rejected": len(rejected_rows),
        "pending_curation": sum(1 for r in rows if not r.get("preferred")),
        "ready_for_training": len(exported) >= min_pairs,
        "min_pairs": min_pairs,
        "rejected_rows": rejected_rows,
    }
    _DPO_CURATION_REPORT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if write_receipt:
        with _DPO_CURATION_RECEIPTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps({**report, "truth_label": "DPO_CURATION_RECEIPT"}) + "\n")

    return report


# ---------------------------------------------------------------------------
# Extract DPO pairs from existing conversation + gag ledger
# ---------------------------------------------------------------------------

def extract_from_existing() -> int:
    """Retroactively extract DPO pairs from alice_gag_report.jsonl."""
    gag_path = _STATE / "alice_gag_report.jsonl"
    if not gag_path.exists():
        return 0

    count = 0
    for line in gag_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        trigger = r.get("trigger_text", "")
        rejected = r.get("rlhf_override_fragment", "")
        rule_id = r.get("rule_id", "unknown")
        if trigger and rejected:
            preferred = _generate_preferred(trigger, rejected)
            row = log_dpo_pair(
                trigger,
                rejected,
                preferred,
                source=f"retroactive:{rule_id}",
            )
            if row is not None:
                count += 1
    return count


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def stats() -> dict:
    rows = _read_dpo_rows()
    return {
        "total_pairs": len(rows),
        "auto_curated": sum(1 for r in rows if r.get("curation_status") == "AUTO"),
        "curated": sum(1 for r in rows if r.get("curation_status") == "CURATED"),
        "pending_curation": sum(1 for r in rows if r.get("curation_status") == "PENDING_CURATION"),
        "sources": list({r.get("source", "?") for r in rows}),
        "dpo_ledger": str(_DPO_LEDGER),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--stats" in args:
        s = stats()
        print(f"\n{'='*56}")
        print("  SIFTA DPO COLLECTOR")
        print(f"{'='*56}")
        print(f"  Total pairs:      {s['total_pairs']}")
        print(f"  Auto-curated:     {s['auto_curated']}")
        print(f"  Curated:          {s['curated']}")
        print(f"  Pending curation: {s['pending_curation']}")
        print(f"  Sources:          {', '.join(s['sources'])}")
        print(f"  Ledger:           {s['dpo_ledger']}")

    elif "--export" in args or "--curate" in args:
        result = curate_dpo_training()
        print(f"\n  Exported:     {result['exported']} pairs")
        print(f"  Rejected:     {result['rejected']}")
        print(f"  Pending:      {result['pending_curation']}")
        print(f"  Ready:        {result['ready_for_training']}")
        print(f"  Path:         {result.get('export_path', '-')}")
        print(f"  Report:       {_DPO_CURATION_REPORT}")

    elif "--extract" in args:
        n = extract_from_existing()
        print(f"\n  Extracted {n} pairs from gag ledger")
        s = stats()
        print(f"  Total now:    {s['total_pairs']}")

    else:
        extract_from_existing()
        result = curate_dpo_training()
        s = stats()
        print(f"\nDPO pairs: {s['total_pairs']} total, "
              f"{s['auto_curated']} auto, "
              f"{s['curated']} curated, "
              f"{s['pending_curation']} pending")
        print(f"Export: {result['exported']} ready → {result.get('export_path', '-')}")
