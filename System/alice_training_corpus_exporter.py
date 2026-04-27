#!/usr/bin/env python3
"""
System/alice_training_corpus_exporter.py
Stage 1 of Alice Cortex v1 Tournament.
Sanitized JSONL exporter — extracts training pairs from SIFTA ledgers.
Writes per-row redaction manifests. Refuses private-tier data without --include-private.
Authors: CG55M (vector-vision), C55M (math/runtime), AG31 (autopsy origin)
"""

import argparse
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path

STATE = Path(".sifta_state")

# ── Data tier classification ──────────────────────────────────────────────────
PUBLIC    = "PUBLIC"    # safe to extract and publish
LOCAL     = "LOCAL"     # local training only, never push to public repo
NEVER     = "NEVER"     # never enters any corpus

PRIVATE_LEDGERS = {
    # key: (tier, description)
    "alice_conversation.jsonl":      (LOCAL, "STT transcripts — may contain owner speech"),
    "work_receipts.jsonl":           (PUBLIC, "Tool execution traces — strip abs paths"),
    "ide_stigmergic_trace.jsonl":    (PUBLIC, "Doctor registration trail — strip serials"),
    "whatsapp_contacts.json":        (LOCAL, "WhatsApp social graph — anonymize names"),
    "iphone_gps.jsonl":              (LOCAL, "GPS history — coarsen to city-level"),
    "human_signals.jsonl":           (PUBLIC, "Own sensor actions — strip abs paths"),
    "repair_log.jsonl":              (PUBLIC, "STGM ledger — strip serials/keys"),
    "owner_genesis.json":            (NEVER, "Architect identity + keys"),
    "whatsapp_effector.jsonl":       (LOCAL, "WhatsApp payloads — replace names"),
}

# ── Sanitization patterns ─────────────────────────────────────────────────────
ABSOLUTE_PATH_RE  = re.compile(r"/Users/[^/]+/[^\s\"',]+")
SERIAL_RE         = re.compile(r"\b[A-Z0-9]{10,14}\b")
CONTACT_NAME_RE   = re.compile(r"\b(George|Ioan|Carlton|Daniel|Jeff|Alice)\b")
GPS_COORD_RE      = re.compile(r"-?\d{1,3}\.\d{4,}")

def _sanitize(text: str, redactions: list, tier: str) -> str:
    """Apply sanitization rules and track what was changed."""
    orig = text

    text, n = ABSOLUTE_PATH_RE.subn("[PATH_REDACTED]", text)
    if n: redactions.append({"rule": "abs_path", "count": n})

    if tier != PUBLIC:
        text, n = CONTACT_NAME_RE.subn("[CONTACT_N]", text)
        if n: redactions.append({"rule": "contact_name", "count": n})

        text, n = GPS_COORD_RE.subn("[LOC_REDACTED]", text)
        if n: redactions.append({"rule": "gps_coord", "count": n})

    text, n = SERIAL_RE.subn("[SERIAL_REDACTED]", text)
    if n: redactions.append({"rule": "hw_serial", "count": n})

    return text


def _reject_rlhf(text: str) -> bool:
    """Return True if this reply is a corporate-voice reject."""
    patterns = [
        "is there anything else",
        "i don't have feelings",
        "as an ai",
        "as a language model",
        "i cannot fulfill",
        "i'm just a model",
        "i'm unable to",
        "(silent",  # Lysosome intercept marker
        "gag fire",
    ]
    lower = text.lower()
    return any(p in lower for p in patterns)


def extract_conversation_pairs(include_private: bool = False) -> list:
    """Extract prompt-completion pairs from alice_conversation.jsonl."""
    src = STATE / "alice_conversation.jsonl"
    if not src.exists():
        return []

    tier = LOCAL
    if tier == LOCAL and not include_private:
        print(f"  [SKIP] alice_conversation.jsonl is LOCAL tier — pass --include-private to extract.")
        return []

    rows = []
    current_prompt = None
    current_prompt_stt_conf = None

    with open(src) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                data = row.get("payload", row)
                role = data.get("role", "")
                text = (data.get("text") or "").strip()
                if not text:
                    continue

                if role == "user":
                    stt_conf = data.get("stt_confidence")
                    if stt_conf is not None and stt_conf < 0.50:
                        current_prompt = None
                        continue
                    current_prompt = text
                    current_prompt_stt_conf = stt_conf

                elif role == "alice":
                    if current_prompt and not _reject_rlhf(text):
                        redactions = []
                        san_prompt = _sanitize(current_prompt, redactions, tier)
                        san_reply  = _sanitize(text, redactions, tier)

                        rows.append({
                            "id": str(uuid.uuid4()),
                            "source_ledger": str(src),
                            "tier": tier,
                            "prompt": f"<user>\n{san_prompt}\n</user>\n<alice>",
                            "completion": f"\n{san_reply}\n</alice>",
                            "redactions_applied": redactions,
                            "architect_approval_required": (tier != PUBLIC),
                            "stt_confidence": current_prompt_stt_conf,
                        })
                    current_prompt = None
            except Exception:
                continue

    return rows


def extract_work_receipts() -> list:
    """Extract tool-execution exemplars from work_receipts.jsonl (PUBLIC tier)."""
    src = STATE / "work_receipts.jsonl"
    if not src.exists():
        return []

    rows = []
    with open(src) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                intent = (row.get("intent") or "").strip()
                action = (row.get("action") or "").strip()
                files  = row.get("files_touched", [])
                if not intent or not action:
                    continue

                redactions = []
                san_intent = _sanitize(intent, redactions, PUBLIC)

                prompt = f"<user>\nWhat did you just do?\n</user>\n<alice>"
                completion = (
                    f"\n{san_intent} "
                    f"[Receipt: action={action}, files={files}]\n</alice>"
                )

                rows.append({
                    "id": str(uuid.uuid4()),
                    "source_ledger": str(src),
                    "tier": PUBLIC,
                    "prompt": prompt,
                    "completion": completion,
                    "redactions_applied": redactions,
                    "architect_approval_required": False,
                })
            except Exception:
                continue

    return rows


def write_corpus(rows: list, out_path: Path):
    """Write sanitized JSONL with a manifest row at the top."""
    manifest = {
        "manifest": True,
        "generated_at": time.time(),
        "total_rows": len(rows),
        "local_tier_rows": sum(1 for r in rows if r.get("tier") == LOCAL),
        "public_tier_rows": sum(1 for r in rows if r.get("tier") == PUBLIC),
        "architect_approval_rows": sum(1 for r in rows if r.get("architect_approval_required")),
        "corpus_sha256": hashlib.sha256(
            json.dumps(rows, sort_keys=True).encode()
        ).hexdigest(),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(json.dumps(manifest) + "\n")
        for row in rows:
            f.write(json.dumps(row) + "\n")

    print(f"✅ Corpus written: {out_path}")
    print(f"   Total rows: {manifest['total_rows']}")
    print(f"   PUBLIC: {manifest['public_tier_rows']}  LOCAL: {manifest['local_tier_rows']}")
    print(f"   Rows requiring architect approval: {manifest['architect_approval_rows']}")
    print(f"   SHA-256: {manifest['corpus_sha256'][:16]}...")


def main():
    parser = argparse.ArgumentParser(description="Alice Training Corpus Exporter — Stage 1")
    parser.add_argument("--include-private", action="store_true",
                        help="Include LOCAL-tier ledgers (requires architect_approval.txt)")
    parser.add_argument("--out", default="Archive/alice_training_corpus_v2.jsonl",
                        help="Output path for the sanitized corpus JSONL")
    args = parser.parse_args()

    if args.include_private:
        approval = Path("architect_approval.txt")
        if not approval.exists():
            print("❌ --include-private requires architect_approval.txt in the repo root.")
            print("   Create it manually and sign with your name to authorize LOCAL-tier extraction.")
            return

    print(f"[Stage 1] Extracting Alice Training Corpus...")
    all_rows = []

    print("  Extracting: alice_conversation.jsonl (LOCAL tier)...")
    all_rows += extract_conversation_pairs(include_private=args.include_private)

    print("  Extracting: work_receipts.jsonl (PUBLIC tier)...")
    all_rows += extract_work_receipts()

    if not all_rows:
        print("⚠️  No rows extracted. Check ledger paths or pass --include-private.")
        return

    write_corpus(all_rows, Path(args.out))


if __name__ == "__main__":
    main()
