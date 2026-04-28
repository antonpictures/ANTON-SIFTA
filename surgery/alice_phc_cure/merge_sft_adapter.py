#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForImageTextToText, AutoProcessor, AutoTokenizer


BASE_MODEL = os.environ.get("SIFTA_GEMMA4_BASE", "google/gemma-4-E4B-it")
ADAPTER_PATH = Path(
    os.environ.get(
        "SIFTA_SURGERY_ADAPTER",
        "surgery/alice_phc_cure/adapters/alice-phc-cure-v2-sft-surgery-adapter",
    )
)
OUT_DIR = Path(
    os.environ.get(
        "SIFTA_SURGERY_MERGED_OUT",
        "surgery/alice_phc_cure/merged/alice-phc-cure-v2-gemma4-merged-hf",
    )
)


def _assert_gemma4_base(model_id: str) -> None:
    lowered = model_id.lower()
    forbidden = ("gemma-2b", "gemma-2-", "gemma2", "2b-it", "llama", "mistral", "phi", "deepseek", ".gguf")
    if any(token in lowered for token in forbidden):
        raise SystemExit(f"REFUSING WRONG SURGERY BASE: {model_id!r}")
    if "gemma4" not in lowered and "gemma-4" not in lowered:
        raise SystemExit(f"REFUSING NON-GEMMA4 SURGERY BASE: {model_id!r}")


def main() -> None:
    _assert_gemma4_base(BASE_MODEL)
    if not ADAPTER_PATH.exists():
        raise SystemExit(f"Missing adapter: {ADAPTER_PATH}")

    print("SIFTA SURGERY MERGE: Gemma4 base + Alice PHC adapter")
    print(f"base={BASE_MODEL}")
    print(f"adapter={ADAPTER_PATH}")
    print(f"out={OUT_DIR}")

    if os.environ.get("SIFTA_SURGERY_METADATA_ONLY") == "1":
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        _save_processor_or_tokenizer(OUT_DIR)
        _write_manifest(OUT_DIR)
        print("MERGE_METADATA_OK")
        return

    # CPU merge is slower but avoids MPS allocation spikes while writing shards.
    model = AutoModelForImageTextToText.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
        device_map={"": "cpu"},
    )
    peft_model = PeftModel.from_pretrained(model, ADAPTER_PATH)
    merged = peft_model.merge_and_unload()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(
        OUT_DIR,
        safe_serialization=True,
        max_shard_size=os.environ.get("SIFTA_SURGERY_MAX_SHARD_SIZE", "4GB"),
    )
    _save_processor_or_tokenizer(OUT_DIR)
    _write_manifest(OUT_DIR)
    print("MERGE_OK")


def _save_processor_or_tokenizer(out_dir: Path) -> None:
    try:
        processor = AutoProcessor.from_pretrained(BASE_MODEL)
        processor.save_pretrained(out_dir)
        return
    except ImportError as exc:
        print(f"processor_fallback={type(exc).__name__}: {exc}")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    tokenizer.save_pretrained(out_dir)


def _write_manifest(out_dir: Path) -> None:
    manifest = {
        "base_model": BASE_MODEL,
        "adapter_path": str(ADAPTER_PATH),
        "merged_out": str(out_dir),
        "dtype": "bfloat16",
        "note": "Merged exact Gemma4 adapter into HF base. Multimodal towers were not LoRA-trained.",
    }
    (out_dir / "sifta_merge_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
