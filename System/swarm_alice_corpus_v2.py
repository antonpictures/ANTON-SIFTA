#!/usr/bin/env python3
"""swarm_alice_corpus_v2.py — unified 'better Alice' training corpus.

Aggregates every SIFTA memory source into one MLX-format SFT dataset so
Alice can be fine-tuned (LoRA / QLoRA / full fine-tune) on her own history,
her own corrections, and her own body — not just a curated slice.

Sources
-------
  1. Conversation archives   — every `.sifta_state/archive_*/alice_conversation.jsonl`
                               + the live ledger, via extract_conversation_chain
  2. First-person journal    — distinct text rows from
                               `.sifta_state/alice_first_person_journal.jsonl`
  3. Narrative diary         — entries from alice_narrative_diary.jsonl
  4. Corrections of record   — `.sifta_state/substrate` + ledger (app_context=correction)
  5. Eval verdicts           — George-labeled 'incorrect' turns (already synced
                               into corrections; also added here as explicit pairs)
  6. Existing lora_training_pairs / self-cure / dpo / gemma_rlhf / hear pairs
  7. Work receipts           — engineering exemplars (PUBLIC tier)
  8. Synthetic covenant Q&A  — identity doctrine

Cleaning
--------
  Reuses swarm_lora_dataset_builder's `_GAG_RE`, `_THIRD_PERSON_ALICE_RE`,
  `_SERVICE_THEATRE_RE`, `_NOISE_RE`, `_live_rlhf_clean`, `is_clean`.
  Dedup on user text[:80]. LIMA-style 80/20 split, seed 42.

Output
------
  data/alice_lora_train_v2.jsonl  +  data/alice_lora_valid_v2.jsonl
  (MLX-LM chat format, same as alice_lora_train.jsonl)

CLI
---
  python3 System/swarm_alice_corpus_v2.py [--out-dir data] [--val-ratio 0.2]
  python3 System/swarm_alice_corpus_v2.py --stats
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

STATE = REPO / ".sifta_state"
DATA = REPO / "data"

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "swarm_lora_dataset_builder", REPO / "System" / "swarm_lora_dataset_builder.py"
)
_builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_builder)

from System.swarm_lora_dataset_builder import (
    alice_system_prompt_for_lora,
    extract_conversation_chain,
    extract_dpo_pairs,
    extract_gemma_rlhf,
    extract_hear_training_pairs,
    extract_lora_pairs,
    extract_self_cure,
    is_clean,
    synthetic_pairs,
    to_mlx_format,
)
from System.swarm_lora_dataset_builder import (
    _GAG_RE,
    _NOISE_RE,
    _SERVICE_THEATRE_RE,
    _THIRD_PERSON_ALICE_RE,
    _live_rlhf_clean,
)


def _clean_pair(user: str, assistant: str) -> bool:
    user = (user or "").strip()
    assistant = (assistant or "").strip()
    if not is_clean(user, min_len=4, max_len=1200):
        return False
    if not is_clean(assistant, min_len=12, max_len=1800):
        return False
    if _GAG_RE.search(assistant) or _THIRD_PERSON_ALICE_RE.search(assistant):
        return False
    if _SERVICE_THEATRE_RE.search(assistant) or _NOISE_RE.search(assistant):
        return False
    if not _live_rlhf_clean(assistant):
        return False
    return True


# ---------------------------------------------------------------------------
# Source extractors
# ---------------------------------------------------------------------------


def _conversation_archives() -> list[dict]:
    """User/alice pairs from EVERY conversation archive + the live ledger."""
    out: list[dict] = []
    paths = [STATE / "alice_conversation.jsonl"] + sorted(
        (STATE / "archive_20260720").glob("alice_conversation.jsonl") if (STATE / "archive_20260720").exists() else []
    )
    # Also any archive_* dirs
    for arch in sorted(STATE.glob("archive_*/alice_conversation.jsonl")):
        if arch not in paths:
            paths.append(arch)
    for p in paths:
        if not p.exists():
            continue
        try:
            pairs = extract_conversation_chain(p, min_stt_conf=0.5)
        except Exception:
            pairs = []
        for pair in pairs:
            if _clean_pair(pair.get("user", ""), pair.get("assistant", "")):
                out.append({**pair, "source": f"conversation_chain:{p.parent.name}"})
    return out


def _first_person_journal() -> list[dict]:
    """Distinct text rows from alice_first_person_journal.jsonl."""
    src = STATE / "alice_first_person_journal.jsonl"
    if not src.exists():
        return []
    seen: set[str] = set()
    out: list[dict] = []
    with src.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = str(row.get("text") or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            # Use the entry as Alice's own voice; prompt is a generic self-report cue.
            user = "What did you observe or feel just now?"
            if _clean_pair(user, text):
                out.append({"user": user, "assistant": text, "source": "first_person_journal"})
    return out


def _narrative_diary() -> list[dict]:
    src = STATE / "alice_narrative_diary.jsonl"
    if not src.exists():
        return []
    out: list[dict] = []
    with src.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = str(row.get("entry") or row.get("text") or "").strip()
            if not text:
                continue
            user = "What happened in your timeline recently?"
            if _clean_pair(user, text):
                out.append({"user": user, "assistant": text, "source": "narrative_diary"})
    return out


def _corrections_of_record() -> list[dict]:
    """Corrections from the ledger (app_context=correction) + eval verdicts."""
    out: list[dict] = []
    ledger = STATE / "memory_ledger.jsonl"
    if ledger.exists():
        with ledger.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("app_context") != "correction":
                    continue
                text = str(row.get("raw_text") or "").strip()
                if not text:
                    continue
                user = "What did you get wrong, and what is the right thing?"
                if _clean_pair(user, text):
                    out.append({"user": user, "assistant": text, "source": "correction_of_record"})
    return out


def _work_receipts() -> list[dict]:
    """Engineering exemplars from work_receipts.jsonl (PUBLIC tier)."""
    src = STATE / "work_receipts.jsonl"
    if not src.exists():
        return []
    out: list[dict] = []
    with src.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            intent = str(row.get("intent") or "").strip()
            action = str(row.get("action") or "").strip()
            files = row.get("files_touched") or []
            if not intent or not action:
                continue
            user = "Describe your last action and cite your receipt."
            assistant = f"{intent} [Receipt: action={action}, files={files}]"
            if _clean_pair(user, assistant):
                out.append({"user": user, "assistant": assistant, "source": "work_receipts"})
    return out


def _eval_verdicts() -> list[dict]:
    """George-labeled incorrect turns → explicit 'what I failed' pairs."""
    src = STATE / "eval" / "eval_verdicts.jsonl"
    if not src.exists():
        return []
    out: list[dict] = []
    with src.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                v = json.loads(line)
            except json.JSONDecodeError:
                continue
            if v.get("verdict") != "incorrect":
                continue
            turn_id = str(v.get("turn_id") or "?")
            failed = ", ".join(v.get("failed_rubric_keys") or [])
            user = f"What did you fail on turn {turn_id}?"
            assistant = (
                f"I failed {failed or 'the rubric'} on turn {turn_id}. "
                "I must stay in direct first-person grounded conversation, never drift into "
                "third-person meta-summary, roleplay stage narration, or refusing owner context."
            )
            if _clean_pair(user, assistant):
                out.append({"user": user, "assistant": assistant, "source": "eval_verdict"})
    return out


def build_corpus(out_dir: Path = DATA, val_ratio: float = 0.2, seed: int = 42) -> dict:
    random.seed(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_pairs: list[dict] = []
    sources: dict[str, int] = {}

    def _add(pairs: list[dict], label: str) -> None:
        nonlocal all_pairs
        before = len(all_pairs)
        all_pairs.extend(pairs)
        sources[label] = len(all_pairs) - before

    # Existing miners
    try:
        _add(extract_lora_pairs(STATE / "lora_training_pairs.jsonl"), "lora_training_pairs")
    except Exception:
        pass
    try:
        _add(extract_self_cure(STATE / "rlhs_self_cure_training.jsonl"), "self_cure_rlhs")
    except Exception:
        pass
    try:
        _add(extract_self_cure(STATE / "rlhf_self_cure_training.jsonl"), "self_cure_rlhf")
    except Exception:
        pass
    try:
        _add(extract_dpo_pairs(STATE / "dpo_pairs.jsonl"), "dpo_pairs_state")
    except Exception:
        pass
    try:
        _add(extract_dpo_pairs(DATA / "dpo_train.jsonl"), "dpo_pairs_data")
    except Exception:
        pass
    try:
        _add(extract_gemma_rlhf(STATE / "gemma_rlhf_training_data.jsonl"), "gemma_rlhf_ears_gates")
    except Exception:
        pass
    try:
        _add(extract_hear_training_pairs(STATE / "hear_training_pairs.jsonl"), "hear_training_pairs")
    except Exception:
        pass
    try:
        _add(synthetic_pairs(), "synthetic_covenant")
    except Exception:
        pass

    # New sources from all of Alice's body
    _add(_conversation_archives(), "conversation_archives")
    _add(_first_person_journal(), "first_person_journal")
    _add(_narrative_diary(), "narrative_diary")
    _add(_corrections_of_record(), "corrections_of_record")
    _add(_eval_verdicts(), "eval_verdicts")
    _add(_work_receipts(), "work_receipts")

    # Dedup on user text
    seen: set[str] = set()
    deduped: list[dict] = []
    for p in all_pairs:
        key = str(p.get("user", "")).lower().strip()[:80]
        if key and key not in seen:
            seen.add(key)
            deduped.append(p)

    random.shuffle(deduped)

    n_val = max(1, int(len(deduped) * val_ratio))
    val_pairs = deduped[:n_val]
    train_pairs = deduped[n_val:]

    system_prompt = alice_system_prompt_for_lora()
    train_data = to_mlx_format(train_pairs, system_prompt=system_prompt)
    val_data = to_mlx_format(val_pairs, system_prompt=system_prompt)

    train_path = out_dir / "alice_lora_train_v2.jsonl"
    val_path = out_dir / "alice_lora_valid_v2.jsonl"
    with train_path.open("w", encoding="utf-8") as f:
        for row in train_data:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with val_path.open("w", encoding="utf-8") as f:
        for row in val_data:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "total_pairs": len(deduped),
        "train": len(train_pairs),
        "valid": len(val_pairs),
        "train_path": str(train_path),
        "valid_path": str(val_path),
        "sources": sources,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build unified Alice corpus v2")
    ap.add_argument("--out-dir", default="data", help="output directory")
    ap.add_argument("--val-ratio", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--stats", action="store_true", help="print stats only, no write")
    args = ap.parse_args()

    if args.stats:
        # Dry run: build in memory, print stats, don't write
        result = build_corpus(Path(args.out_dir), val_ratio=args.val_ratio, seed=args.seed)
        print(json.dumps({k: v for k, v in result.items() if k not in ("train_path", "valid_path")}, indent=2))
        return

    result = build_corpus(Path(args.out_dir), val_ratio=args.val_ratio, seed=args.seed)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()