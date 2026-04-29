#!/usr/bin/env python3
"""
System/swarm_cosmos_reason1.py — NVIDIA Cosmos-Reason1-7B SIFTA organ.

Truth contract (covenant §3 / §8):
  ONLINE  model exists on HuggingFace; not downloaded locally
  REAL    local HF cache exists AND a live Alice frame inference completed
  BROKEN  cached but inference failed

This module NEVER sets truth=REAL from a documentation claim alone.
Evidence chain:  HF mtime → load → tokenize frame → generate → receipt.

Official anchors (verified 2026-04-28):
  https://huggingface.co/nvidia/Cosmos-Reason1-7B
  https://github.com/nvidia-cosmos/cosmos-reason1
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_RECEIPT_PATH = _STATE / "cosmos_reason1_receipts.jsonl"

HF_REPO_ID   = "nvidia/Cosmos-Reason1-7B"
HF_CACHE_ROOT = Path(os.environ.get("HF_HOME",
                     Path.home() / ".cache" / "huggingface")) / "hub"
MODEL_CACHE   = HF_CACHE_ROOT / "models--nvidia--Cosmos-Reason1-7B"

# Covenant question to ask when inference runs on an Alice frame
_SIFTA_PROBE_QUESTION = (
    "You are SIFTA Predator v7.0. Describe what you observe in this image "
    "using physical-world terms only. Maximum 2 sentences."
)


# ─────────────────────────────────────────────────────────────────────────────
# Receipt helpers
# ─────────────────────────────────────────────────────────────────────────────

def _write_receipt(row: dict) -> dict:
    _STATE.mkdir(parents=True, exist_ok=True)
    with _RECEIPT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return row


def _base_receipt(truth: str, *, writer: str, detail: str, **extra) -> dict:
    return {
        "schema":    "SIFTA_COSMOS_REASON1_V1",
        "ts":        time.time(),
        "writer":    writer,
        "truth":     truth,
        "hf_repo":   HF_REPO_ID,
        "detail":    detail,
        **extra,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Probe 1 — ONLINE receipt (no download needed)
# ─────────────────────────────────────────────────────────────────────────────

def write_online_receipt(*, writer: str = "cosmos_reason1_meta") -> dict:
    """Write an ONLINE receipt from public metadata only.
    Truth = ONLINE. No weights downloaded. Covenant-safe first proof.
    """
    row = _base_receipt(
        "ONLINE",
        writer=writer,
        detail="Cosmos-Reason1-7B ungated on HuggingFace; model cache not present locally.",
        hf_url="https://huggingface.co/nvidia/Cosmos-Reason1-7B",
        github_url="https://github.com/nvidia-cosmos/cosmos-reason1",
        gated=False,
        task="image-text-to-text",
        note="REAL requires: local HF cache + live Alice frame inference. Not yet achieved.",
    )
    return _write_receipt(row)


# ─────────────────────────────────────────────────────────────────────────────
# Probe 2 — REAL receipt (cache + inference required)
# ─────────────────────────────────────────────────────────────────────────────

def probe_and_infer(
    image_path: str | Path | None = None,
    *,
    writer: str = "cosmos_reason1_infer",
    max_new_tokens: int = 128,
    device: str = "cpu",
) -> dict:
    """Run Cosmos-Reason1-7B on an Alice camera frame.

    Args:
        image_path: path to a JPEG/PNG frame from the Alice camera.
                    If None, uses the latest frame from .sifta_state/
                    visual_stigmergy_last_frame.jpg if available.
        writer:     receipt writer tag
        max_new_tokens: generation cap (keep small for CPU)
        device:     'cpu' (default, works on Apple Silicon)

    Returns receipt dict. truth='REAL' only on success.
    """
    ts_start = time.time()

    # 1. Check local cache
    if not MODEL_CACHE.exists():
        return _write_receipt(_base_receipt(
            "ONLINE",
            writer=writer,
            detail=f"Model cache not found at {MODEL_CACHE}. Run: "
                   f"huggingface-cli download {HF_REPO_ID}",
            next_step="huggingface-cli download nvidia/Cosmos-Reason1-7B",
        ))

    # 2. Resolve frame
    frame = Path(image_path) if image_path else (
        _STATE / "visual_stigmergy_last_frame.jpg"
    )
    if not frame.exists():
        return _write_receipt(_base_receipt(
            "BROKEN",
            writer=writer,
            detail=f"No Alice frame found at {frame}. "
                   "Open Alice → enable camera → wait for first frame.",
        ))

    frame_sha8 = hashlib.sha256(frame.read_bytes()).hexdigest()[:8]

    # 3. Load model (lazy — only imports transformers when cache is present)
    try:
        from transformers import AutoProcessor, AutoModelForImageTextToText  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError as exc:
        return _write_receipt(_base_receipt(
            "BROKEN",
            writer=writer,
            detail=f"Missing dependency: {exc}. "
                   "Run: pip install transformers pillow",
        ))

    try:
        processor = AutoProcessor.from_pretrained(
            MODEL_CACHE, local_files_only=True
        )
        model = AutoModelForImageTextToText.from_pretrained(
            MODEL_CACHE, local_files_only=True
        ).to(device)
        model.eval()
    except Exception as exc:
        return _write_receipt(_base_receipt(
            "BROKEN",
            writer=writer,
            detail=f"Model load failed: {type(exc).__name__}: {exc}",
        ))

    # 4. Inference
    try:
        import torch  # type: ignore
        pil_img = Image.open(frame).convert("RGB")
        inputs = processor(
            images=pil_img,
            text=_SIFTA_PROBE_QUESTION,
            return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            out_ids = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )
        response = processor.decode(out_ids[0], skip_special_tokens=True).strip()
        elapsed = round(time.time() - ts_start, 2)

        return _write_receipt(_base_receipt(
            "REAL",
            writer=writer,
            detail=f"Alice frame inference complete in {elapsed}s on {device}.",
            frame_sha8=frame_sha8,
            frame_path=str(frame),
            question=_SIFTA_PROBE_QUESTION,
            response=response,
            elapsed_s=elapsed,
            device=device,
        ))

    except Exception as exc:
        return _write_receipt(_base_receipt(
            "BROKEN",
            writer=writer,
            detail=f"Inference failed: {type(exc).__name__}: {exc}",
            frame_sha8=frame_sha8,
        ))


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="SIFTA Cosmos-Reason1-7B organ probe"
    )
    parser.add_argument("--mode", choices=["online", "infer"], default="online",
                        help="online: write ONLINE receipt from metadata only. "
                             "infer: run model on Alice frame (requires local cache).")
    parser.add_argument("--frame", default=None,
                        help="Path to Alice camera frame (JPEG/PNG). "
                             "Defaults to .sifta_state/visual_stigmergy_last_frame.jpg")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-tokens", type=int, default=128)
    args = parser.parse_args()

    if args.mode == "online":
        receipt = write_online_receipt(writer="cosmos_reason1_cli_online")
    else:
        receipt = probe_and_infer(
            image_path=args.frame,
            writer="cosmos_reason1_cli_infer",
            device=args.device,
            max_new_tokens=args.max_tokens,
        )

    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    print(f"\nTruth: {receipt['truth']}")
    print(f"Detail: {receipt['detail']}")
    print(f"Receipt appended to: {_RECEIPT_PATH}")


if __name__ == "__main__":
    _main()
