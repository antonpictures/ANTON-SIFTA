#!/usr/bin/env python3
"""
System/alice_training_corpus_exporter.py
Stage 1 of Alice Cortex v1 Tournament.
Sanitized JSONL exporter — extracts training pairs from SIFTA ledgers.
Writes per-row redaction manifests. Refuses private-tier data without --include-private.
Authors: CG55M (vector-vision), C55M (math/runtime), AG31 (autopsy origin)
Bishop merge: LIMA cap, 70/30 bimodal split, curriculum ordering, Gemma chat template.

Biology:
  70% Spinal Cord (Engineering) — ide_stigmergic_trace, work_receipts
  30% Prefrontal Cortex (Social) — alice_conversation (NOT wernicke — wernicke is raw RMS sensor telemetry)
Physics:
  LIMA (Zhou et al. 2023): 1,000 curated pairs > 50,000 noisy ones.
  Curriculum: deterministic engineering first, social autonomy second.
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


def _approval_status(approval_path: Path) -> tuple[bool, str]:
    """
    Return (ok, reason) for exporting LOCAL-tier rows.
    Used by tests and CLI --include-private gate.
    """
    if not approval_path.is_file():
        return False, "missing architect_approval.txt"
    raw = approval_path.read_text(encoding="utf-8", errors="replace")
    upper = raw.upper()
    if "PENDING" in upper:
        return False, "Architect approval PENDING"
    if "George Anton" in raw:
        return True, "Architect George Anton signed export"
    if "Ioan George Anton" in raw:
        return True, "Architect Ioan George Anton signed export"
    return False, "architect_approval.txt present but not signed"


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
OWNER_NAME_RE     = re.compile(r"\b(George|Ioan)\b")
SWARM_CONTACT_RE  = re.compile(r"\b(Carlton|Daniel|Jeff)\b")
PHONE_RE          = re.compile(r"\+1\s*[\d\-]{10,16}")
GPS_COORD_RE      = re.compile(r"-?\d{1,3}\.\d{4,}")

def _sanitize(text: str, redactions: list, tier: str) -> str:
    """Apply sanitization rules and track what was changed."""
    orig = text

    text, n = ABSOLUTE_PATH_RE.subn("[PATH_REDACTED]", text)
    if n: redactions.append({"rule": "abs_path", "count": n})

    if tier != PUBLIC:
        text, n = OWNER_NAME_RE.subn("[OWNER]", text)
        if n:
            redactions.append({"rule": "owner_name", "count": n})
        text, n = SWARM_CONTACT_RE.subn("[CONTACT_N]", text)
        if n:
            redactions.append({"rule": "contact_name", "count": n})
        text, n = PHONE_RE.subn("[PHONE_REDACTED]", text)
        if n:
            redactions.append({"rule": "phone", "count": n})

        text, n = GPS_COORD_RE.subn("[LOC_REDACTED]", text)
        if n: redactions.append({"rule": "gps_coord", "count": n})

    text, n = SERIAL_RE.subn("[SERIAL_REDACTED]", text)
    if n: redactions.append({"rule": "hw_serial", "count": n})

    return text


# ── LIMA size discipline (Zhou et al. 2023) + 70/30 bimodal split ─────────────
LIMA_TARGET      = 1000   # Total curated rows; quality beats quantity
ENG_RATIO        = 0.70   # Spinal Cord: tool calls, JSON schemas, receipts
SOCIAL_RATIO     = 0.30   # Prefrontal Cortex: alice_conversation autonomy/silence
ENG_TARGET       = int(LIMA_TARGET * ENG_RATIO)
SOCIAL_TARGET    = int(LIMA_TARGET * SOCIAL_RATIO)

# ── Gemma chat template (NOT Llama/Mistral — Bishop's dirt used wrong format) ─
def _gemma_fmt(user_text: str, model_text: str) -> str:
    """Format a turn pair in Gemma's native chat template."""
    return (
        f"<start_of_turn>user\n{user_text}<end_of_turn>\n"
        f"<start_of_turn>model\n{model_text}<end_of_turn>"
    )


def _reject_rlhf(text: str) -> bool:
    """Return True if this reply is a corporate-voice reject."""
    patterns = [
        # Original Lysosome patterns
        "is there anything else",
        "i don't have feelings",
        "as an ai",
        "as a language model",
        "i cannot fulfill",
        "i'm just a model",
        "i'm unable to",
        "(silent",   # Lysosome intercept marker
        "gag fire",
        # Bishop additions — GPT-style RLHF tells
        "delve",
        "tapestry",
        "realm of",
        "it is important to note",
        "i cannot",
        "i want to be transparent",
        "i should clarify",
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
                            "corpus_split": "social",
                            # Gemma-native chat template (fixed from Bishop's Llama/Mistral format)
                            "text": _gemma_fmt(san_prompt, san_reply),
                            "prompt": san_prompt,
                            "completion": san_reply,
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

                user_text  = f"Describe your last action and cite your receipt."
                model_text = f"{san_intent} [Receipt: action={action}, files={files}]"

                rows.append({
                    "id": str(uuid.uuid4()),
                    "source_ledger": str(src),
                    "tier": PUBLIC,
                    "corpus_split": "engineering",
                    # Gemma-native chat template
                    "text": _gemma_fmt(user_text, model_text),
                    "prompt": user_text,
                    "completion": model_text,
                    "redactions_applied": redactions,
                    "architect_approval_required": False,
                })
            except Exception:
                continue

    return rows


def write_corpus(rows: list, out_path: Path):
    """
    Apply LIMA discipline, 70/30 bimodal split, and curriculum ordering.
    Curriculum: Spinal Cord (engineering) first → Prefrontal Cortex (social) second.
    LIMA cap: 1,000 total rows. Quality over quantity (Zhou et al. 2023).
    """
    import random
    eng_rows    = [r for r in rows if r.get("corpus_split") == "engineering"]
    social_rows = [r for r in rows if r.get("corpus_split") == "social"]
    other_rows  = [r for r in rows if r.get("corpus_split") not in ("engineering", "social")]

    random.shuffle(eng_rows)
    random.shuffle(social_rows)

    # Enforce 70/30 split up to LIMA_TARGET
    eng_rows    = eng_rows[:ENG_TARGET]
    social_rows = social_rows[:SOCIAL_TARGET]

    # Curriculum: engineering first (easy/deterministic) → social (nuanced)
    final_rows = eng_rows + social_rows + other_rows

    manifest = {
        "manifest": True,
        "generated_at": time.time(),
        "lima_target": LIMA_TARGET,
        "total_rows": len(final_rows),
        "engineering_rows": len(eng_rows),
        "social_rows": len(social_rows),
        "local_tier_rows": sum(1 for r in final_rows if r.get("tier") == LOCAL),
        "public_tier_rows": sum(1 for r in final_rows if r.get("tier") == PUBLIC),
        "architect_approval_rows": sum(1 for r in final_rows if r.get("architect_approval_required")),
        "chat_template": "gemma",
        "corpus_sha256": hashlib.sha256(
            json.dumps(final_rows, sort_keys=True).encode()
        ).hexdigest(),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(json.dumps(manifest) + "\n")
        for row in final_rows:
            f.write(json.dumps(row) + "\n")

    print(f"✅ Corpus written: {out_path}")
    print(f"   LIMA target: {LIMA_TARGET}  |  Actual: {len(final_rows)}")
    print(f"   Spinal Cord (engineering, 70%): {len(eng_rows)}")
    print(f"   Prefrontal Cortex (social, 30%): {len(social_rows)}")
    print(f"   PUBLIC: {manifest['public_tier_rows']}  LOCAL: {manifest['local_tier_rows']}")
    print(f"   Requires architect approval: {manifest['architect_approval_rows']}")
    print(f"   Chat template: {manifest['chat_template']} (Gemma-native)")
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
        ok, reason = _approval_status(approval)
        if not ok:
            print(f"❌ --include-private blocked: {reason}")
            print("   Create architect_approval.txt in the repo root and sign (see tournament docs).")
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
