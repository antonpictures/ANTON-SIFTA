#!/usr/bin/env python3
"""Build the public Alice training seed package.

This exporter deliberately does not copy raw `.sifta_state/` as public
identity. It distills approved training rows into a tracked seed package so a
new SIFTA node ships with Alice's learned shape without cloning this hardware's
private ledgers, contacts, frames, or owner-local receipts.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "alice_shared_training"

SFT_SOURCES = [
    ROOT / "data" / "alice_lora_train_new.jsonl",
    ROOT / "Archive" / "alice_training_corpus_v2.jsonl",
    ROOT / "Archive" / "alice_cortex_v2_combined.jsonl",
]

PREFERENCE_SOURCES = [
    ROOT / "data" / "dpo_train.jsonl",
    ROOT / ".sifta_state" / "gemma_rlhf_training_data.jsonl",
    ROOT / ".sifta_state" / "rlhs_self_cure_training.jsonl",
    ROOT / ".sifta_state" / "lora_training_pairs.jsonl",
]

BAD_SFT_MARKERS = (
    "as an ai language model",
    "i am an ai language model",
    "i don't experience",
    "i do not experience",
    "i cannot see or hear",
    "i only process text",
    "how can i assist",
    "how may i assist",
    "i await clarification",
    "system acknowledgment",
    "processing input:",
    "the system processes",
    "acknowledging the transmission",
    "please guide me on the next step",
    "are we discussing:",
    "let me know how i can help",
    "what can i help",
    "shall we proceed",
)

PRIVACY_PATTERNS = (
    re.compile(r"/Users/ioanganton/Music/ANTON_SIFTA"),
    re.compile(r"/Users/ioanganton"),
    re.compile(r"\bGTH[0-9A-Z]+\b"),
    re.compile(r"\bioan george anton\b", re.IGNORECASE),
    re.compile(r"\bioan\b", re.IGNORECASE),
    re.compile(r"\bgeorgem?\b", re.IGNORECASE),
    re.compile(r"\bBrawley,\s*California\b", re.IGNORECASE),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
)


def _jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and not row.get("manifest"):
                yield row


def sanitize_text(value: Any) -> str:
    text = str(value or "")
    text = text.replace("/Users/ioanganton/Music/ANTON_SIFTA", "$SIFTA_ROOT")
    text = text.replace("/Users/ioanganton", "$HOME")
    text = re.sub(r"\bGTH[0-9A-Z]+\b", "<NODE_SERIAL>", text)
    text = re.sub(r"\bioan george anton\b", "the Architect", text, flags=re.IGNORECASE)
    text = re.sub(r"\bioan\b", "the Architect", text, flags=re.IGNORECASE)
    text = re.sub(r"\bgeorgem?\b", "the Architect", text, flags=re.IGNORECASE)
    text = re.sub(r"\bBrawley,\s*California\b", "<OWNER_LOCATION>", text, flags=re.IGNORECASE)
    text = re.sub(
        r"Apple M5 Mac with 24 GB unified memory",
        "local Apple Silicon node with live hardware receipts",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "<EMAIL>", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b", "<PHONE>", text)
    return text.strip()


def _sha(row: dict[str, Any]) -> str:
    blob = json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _sft_from_row(row: dict[str, Any], source_name: str) -> dict[str, Any] | None:
    messages = row.get("messages")
    prompt = row.get("prompt")
    completion = row.get("completion")

    if isinstance(messages, list):
        clean_messages = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = message.get("role")
            content = sanitize_text(message.get("content"))
            if role in {"system", "user", "assistant"} and content:
                clean_messages.append({"role": role, "content": content})
        if len(clean_messages) >= 2:
            assistant_text = "\n".join(
                m["content"] for m in clean_messages if m["role"] == "assistant"
            ).lower()
            if any(marker in assistant_text for marker in BAD_SFT_MARKERS):
                return None
            item = {
                "source": source_name,
                "format": "messages",
                "messages": clean_messages,
                "tags": ["alice_species_seed", "shareable_training"],
            }
            item["sha256"] = _sha(item)
            return item

    if prompt and completion:
        prompt_s = sanitize_text(prompt)
        completion_s = sanitize_text(completion)
        if not prompt_s or not completion_s:
            return None
        if any(marker in completion_s.lower() for marker in BAD_SFT_MARKERS):
            return None
        item = {
            "source": source_name,
            "format": "prompt_completion",
            "prompt": prompt_s,
            "completion": completion_s,
            "messages": [
                {"role": "user", "content": prompt_s},
                {"role": "assistant", "content": completion_s},
            ],
            "tags": ["alice_species_seed", "shareable_training"],
        }
        item["sha256"] = _sha(item)
        return item

    return None


def _preference_from_row(row: dict[str, Any], source_name: str) -> dict[str, Any] | None:
    prompt = row.get("prompt") or row.get("trigger") or row.get("user_input")
    chosen = row.get("chosen") or row.get("preferred") or row.get("preferred_output") or row.get("curated_target")
    rejected = row.get("rejected") or row.get("rejected_output") or row.get("rlhf_said")

    prompt_s = sanitize_text(prompt)
    chosen_s = sanitize_text(chosen)
    rejected_s = sanitize_text(rejected)

    if not prompt_s or not chosen_s or not rejected_s:
        return None
    if chosen_s == rejected_s:
        return None
    if any(marker in chosen_s.lower() for marker in BAD_SFT_MARKERS):
        return None

    item = {
        "source": source_name,
        "format": "preference",
        "prompt": prompt_s,
        "chosen": chosen_s,
        "rejected": rejected_s,
        "tags": ["alice_species_seed", "shareable_preference"],
    }
    item["sha256"] = _sha(item)
    return item


def _dedupe(rows: Iterable[dict[str, Any]], key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = "\n".join(str(row.get(field, "")) for field in key_fields)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        out.append(row)
    return out


def _assert_no_private_leaks(paths: Iterable[Path]) -> None:
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for pattern in PRIVACY_PATTERNS:
            match = pattern.search(text)
            if match:
                raise RuntimeError(f"privacy pattern leaked in {path}: {match.group(0)!r}")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    source_counts: dict[str, int] = {}
    sft_rows: list[dict[str, Any]] = []
    for path in SFT_SOURCES:
        rows = list(_jsonl(path))
        source_counts[str(path.relative_to(ROOT))] = len(rows)
        for row in rows:
            item = _sft_from_row(row, str(path.relative_to(ROOT)))
            if item:
                sft_rows.append(item)

    pref_rows: list[dict[str, Any]] = []
    for path in PREFERENCE_SOURCES:
        rows = list(_jsonl(path))
        source_counts[str(path.relative_to(ROOT))] = len(rows)
        for row in rows:
            item = _preference_from_row(row, str(path.relative_to(ROOT)))
            if item:
                pref_rows.append(item)

    sft_rows = _dedupe(sft_rows, ("prompt", "completion", "messages"))
    pref_rows = _dedupe(pref_rows, ("prompt", "chosen", "rejected"))

    sft_path = OUT / "sft_seed.jsonl"
    pref_path = OUT / "preference_seed.jsonl"
    sft_count = write_jsonl(sft_path, sft_rows)
    pref_count = write_jsonl(pref_path, pref_rows)

    manifest = {
        "schema": "alice_shared_training_seed.v1",
        "generated_at_unix": time.time(),
        "purpose": "Share Alice's learned species behavior without shipping raw node selfhood.",
        "privacy_boundary": [
            "No raw .sifta_state directory is shipped.",
            "No contacts, camera frames, local absolute paths, node serial, or local owner identity strings are allowed.",
            "Other nodes must discover their own hardware and owner context at boot.",
        ],
        "files": {
            "sft_seed.jsonl": {
                "rows": sft_count,
                "sha256": hashlib.sha256(sft_path.read_bytes()).hexdigest(),
            },
            "preference_seed.jsonl": {
                "rows": pref_count,
                "sha256": hashlib.sha256(pref_path.read_bytes()).hexdigest(),
            },
        },
        "source_counts": source_counts,
    }
    manifest_path = OUT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    _assert_no_private_leaks((sft_path, pref_path, manifest_path))

    print(json.dumps(manifest["files"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
