#!/usr/bin/env python3
"""
System/swarm_cosmos_reason1.py — NVIDIA Cosmos-Reason1-7B SIFTA organ.

Truth contract (Covenant §3/§8 + Dr. Codex 2026-04-28):
  ONLINE        model exists on HuggingFace; not downloaded locally
  DOWNLOADING   cache dir exists but incomplete (download in progress)
  REAL_LOCAL    all model shards present; inference not yet run
  REAL_INFERENCE Alice frame → model answer → receipt written  ← the real prize
  BROKEN        cached but inference failed

Dr. Codex animal metaphor:
  Gecko = touch              (REAL_CPU)
  Bat   = space/depth        (REAL_CPU)
  Warp  = NVIDIA kernel      (REAL_CPU)
  Cosmos-Reason1 = visual common-sense cortex  (ONLINE → REAL_INFERENCE)
  SIFTA referee = immune truth judge

Official anchors (verified 2026-04-28):
  https://huggingface.co/nvidia/Cosmos-Reason1-7B
  https://github.com/nvidia-cosmos/cosmos-reason1

Architecture: Qwen2_5_VLForConditionalGeneration (same family as Qwen2-VL)
  Qwen2-VL-2B-Instruct IS already cached locally → bridge proof available now.
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

# ── Primary target ────────────────────────────────────────────────────────────
COSMOS_REPO_ID  = "nvidia/Cosmos-Reason1-7B"
HF_CACHE_ROOT   = Path(os.environ.get("HF_HOME",
                   Path.home() / ".cache" / "huggingface")) / "hub"
COSMOS_CACHE    = HF_CACHE_ROOT / "models--nvidia--Cosmos-Reason1-7B"

# ── Bridge model (already cached, same Qwen2-VL architecture family) ──────────
BRIDGE_REPO_ID  = "Qwen/Qwen2-VL-2B-Instruct"
BRIDGE_CACHE    = HF_CACHE_ROOT / "models--Qwen--Qwen2-VL-2B-Instruct"

# Covenant question — feeds into Alice frame inference
_SIFTA_PROBE_QUESTION = (
    "You are SIFTA Predator v7.0. Describe what you observe in this image "
    "using physical-world terms only. Maximum 2 sentences."
)

# ── Shard count for completeness check ───────────────────────────────────────
_COSMOS_EXPECTED_SHARDS = 4   # Cosmos-Reason1-7B safetensor shards


# ─────────────────────────────────────────────────────────────────────────────
# Device selection
# ─────────────────────────────────────────────────────────────────────────────

def _auto_device() -> str:
    """Pick best available device: MPS (Apple Silicon) > CUDA > CPU."""
    try:
        import torch
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


# ─────────────────────────────────────────────────────────────────────────────
# Cache state probe
# ─────────────────────────────────────────────────────────────────────────────

def _cosmos_cache_state() -> tuple[str, str]:
    """Return (truth_state, detail) for current Cosmos cache."""
    if not COSMOS_CACHE.exists():
        return ("ONLINE",
                "Cosmos-Reason1-7B not downloaded. "
                f"Run: python {__file__} --download")

    blobs = list((COSMOS_CACHE / "blobs").glob("*")) if (COSMOS_CACHE / "blobs").exists() else []
    snapshots = list(COSMOS_CACHE.glob("snapshots/*/model-*.safetensors"))

    if not snapshots:
        incomplete = sum(f.stat().st_size for f in blobs)
        return ("DOWNLOADING",
                f"Download in progress — {incomplete/1e9:.1f} GB received so far.")

    shard_count = len(snapshots)
    if shard_count < _COSMOS_EXPECTED_SHARDS:
        return ("DOWNLOADING",
                f"Partial: {shard_count}/{_COSMOS_EXPECTED_SHARDS} shards present.")

    return ("REAL_LOCAL",
            f"Cosmos-Reason1-7B fully cached ({shard_count} shards). "
            "Run --mode infer to reach REAL_INFERENCE.")


def _bridge_available() -> tuple[bool, str]:
    """Check if Qwen2-VL-2B-Instruct bridge model is cached."""
    snaps = list(BRIDGE_CACHE.glob("snapshots/*/model-*.safetensors")) if BRIDGE_CACHE.exists() else []
    if snaps:
        return True, f"Qwen2-VL-2B-Instruct bridge cached ({len(snaps)} shards)"
    return False, "Bridge not cached"


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
        "schema":  "SIFTA_COSMOS_REASON1_V2",
        "ts":      time.time(),
        "writer":  writer,
        "truth":   truth,
        "detail":  detail,
        **extra,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Probe 1 — Status receipt (no inference)
# ─────────────────────────────────────────────────────────────────────────────

def write_status_receipt(*, writer: str = "cosmos_status") -> dict:
    """Write current state receipt — ONLINE / DOWNLOADING / REAL_LOCAL."""
    state, detail = _cosmos_cache_state()
    bridge_ok, bridge_detail = _bridge_available()
    row = _base_receipt(
        state, writer=writer, detail=detail,
        hf_repo=COSMOS_REPO_ID,
        hf_url="https://huggingface.co/nvidia/Cosmos-Reason1-7B",
        github_url="https://github.com/nvidia-cosmos/cosmos-reason1",
        architecture="Qwen2_5_VLForConditionalGeneration",
        bridge_available=bridge_ok,
        bridge_detail=bridge_detail,
        note="REAL_INFERENCE requires: model cached + live Alice frame inference.",
    )
    return _write_receipt(row)


# ─────────────────────────────────────────────────────────────────────────────
# Probe 2 — REAL_INFERENCE (full proof)
# ─────────────────────────────────────────────────────────────────────────────

def probe_and_infer(
    image_path: str | Path | None = None,
    *,
    writer: str = "cosmos_infer",
    max_new_tokens: int = 256,
    device: str | None = None,
    use_bridge: bool = False,
) -> dict:
    """Run vision-language inference on an Alice camera frame.

    Args:
        image_path:     Alice camera frame. Default: .sifta_state/visual_stigmergy_last_frame.jpg
        max_new_tokens: generation cap (256 ≈ 2 sentences, ~15s on M5 MPS)
        device:         None = auto (MPS on Apple Silicon)
        use_bridge:     True = use Qwen2-VL-2B-Instruct (already cached, same arch)
                        False (default) = use Cosmos-Reason1-7B (primary target)

    Returns receipt dict. truth='REAL_INFERENCE' only on success.
    """
    ts_start = time.time()
    device = device or _auto_device()

    # ── Select model cache ────────────────────────────────────────────────────
    if use_bridge:
        model_cache = BRIDGE_CACHE
        repo_label  = BRIDGE_REPO_ID
        from_class  = "Qwen2VLForConditionalGeneration"
    else:
        model_cache = COSMOS_CACHE
        repo_label  = COSMOS_REPO_ID
        from_class  = "Qwen2_5_VLForConditionalGeneration"

    # ── Resolve snapshot dir ─────────────────────────────────────────────────
    snaps = list(model_cache.glob("snapshots/*/config.json")) if model_cache.exists() else []
    if not snaps:
        state, detail = _cosmos_cache_state()
        return _write_receipt(_base_receipt(
            state, writer=writer,
            detail=detail + f" (use_bridge={use_bridge})",
            repo=repo_label,
        ))
    snapshot_dir = snaps[0].parent

    # ── Resolve Alice frame ───────────────────────────────────────────────────
    frame = Path(image_path) if image_path else (
        _STATE / "visual_stigmergy_last_frame.jpg"
    )
    if not frame.exists():
        return _write_receipt(_base_receipt(
            "BROKEN", writer=writer,
            detail=f"No Alice frame at {frame}. "
                   "Open Alice → enable camera → wait for first frame.",
        ))

    frame_sha8 = hashlib.sha256(frame.read_bytes()).hexdigest()[:8]
    print(f"[Cosmos] Frame: {frame.name}  sha8={frame_sha8}")
    print(f"[Cosmos] Model: {repo_label}  device={device}")

    # ── Load dependencies ─────────────────────────────────────────────────────
    try:
        import torch
        from PIL import Image  # type: ignore
        if use_bridge:
            from transformers import Qwen2VLForConditionalGeneration, AutoProcessor  # type: ignore
            ModelClass = Qwen2VLForConditionalGeneration
        else:
            from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor  # type: ignore
            ModelClass = Qwen2_5_VLForConditionalGeneration
    except ImportError as exc:
        return _write_receipt(_base_receipt(
            "BROKEN", writer=writer,
            detail=f"Missing dep: {exc}. pip install torch transformers pillow",
        ))

    # ── Load model ────────────────────────────────────────────────────────────
    dtype = torch.bfloat16
    try:
        print(f"[Cosmos] Loading {from_class} in bfloat16 on {device}…")
        processor = AutoProcessor.from_pretrained(str(snapshot_dir), local_files_only=True)
        model = ModelClass.from_pretrained(
            str(snapshot_dir), torch_dtype=dtype, local_files_only=True,
        ).to(device)
        model.eval()
        print("[Cosmos] Model loaded ✓")
    except Exception as exc:
        return _write_receipt(_base_receipt(
            "BROKEN", writer=writer,
            detail=f"Load failed [{from_class}]: {type(exc).__name__}: {exc}",
            frame_sha8=frame_sha8, device=device,
        ))

    # ── Inference ─────────────────────────────────────────────────────────────
    try:
        pil_img = Image.open(frame).convert("RGB")
        messages = [{"role": "user", "content": [
            {"type": "image", "image": pil_img},
            {"type": "text",  "text":  _SIFTA_PROBE_QUESTION},
        ]}]
        text = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = processor(
            text=[text], images=[pil_img], return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            out_ids = model.generate(
                **inputs, max_new_tokens=max_new_tokens, do_sample=False,
            )
        trimmed  = out_ids[:, inputs["input_ids"].shape[1]:]
        response = processor.decode(trimmed[0], skip_special_tokens=True).strip()
        elapsed  = round(time.time() - ts_start, 2)

        print(f"[Cosmos] ✅ REAL_INFERENCE — {elapsed}s on {device}")
        print(f"[Cosmos] Response: {response}")

        return _write_receipt(_base_receipt(
            "REAL_INFERENCE", writer=writer,
            detail=f"Alice frame inference complete — {elapsed}s on {device}.",
            hf_repo=repo_label,
            frame_sha8=frame_sha8,
            frame_path=str(frame),
            question=_SIFTA_PROBE_QUESTION,
            response=response,
            elapsed_s=elapsed,
            device=device,
            architecture=from_class,
            use_bridge=use_bridge,
        ))

    except Exception as exc:
        return _write_receipt(_base_receipt(
            "BROKEN", writer=writer,
            detail=f"Inference failed: {type(exc).__name__}: {exc}",
            frame_sha8=frame_sha8, device=device, repo=repo_label,
        ))


# ─────────────────────────────────────────────────────────────────────────────
# Download helper
# ─────────────────────────────────────────────────────────────────────────────

def start_download(*, show_progress: bool = True) -> None:
    """Download Cosmos-Reason1-7B from HuggingFace (~14 GB)."""
    from huggingface_hub import snapshot_download
    print(f"[Cosmos] Downloading {COSMOS_REPO_ID} (~14 GB)…")
    print(f"[Cosmos] Cache → {COSMOS_CACHE}")
    path = snapshot_download(
        COSMOS_REPO_ID,
        ignore_patterns=["*.pt", "*.bin"],   # prefer safetensors
    )
    print(f"[Cosmos] ✅ Download complete: {path}")
    write_status_receipt(writer="cosmos_download_complete")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="SIFTA Cosmos-Reason1-7B organ")
    p.add_argument("--mode",
                   choices=["status", "infer", "bridge", "download"],
                   default="status",
                   help="status: show cache state  |  "
                        "infer: run Cosmos-Reason1-7B on Alice frame  |  "
                        "bridge: run Qwen2-VL-2B (already cached, same arch)  |  "
                        "download: fetch Cosmos-Reason1-7B from HF")
    p.add_argument("--frame", default=None, help="Alice camera frame path")
    p.add_argument("--device", default=None, help="cpu / mps / cuda (auto if omitted)")
    p.add_argument("--max-tokens", type=int, default=256)
    args = p.parse_args()

    if args.mode == "status":
        receipt = write_status_receipt(writer="cosmos_cli_status")
    elif args.mode == "bridge":
        receipt = probe_and_infer(
            image_path=args.frame, writer="cosmos_cli_bridge",
            device=args.device, max_new_tokens=args.max_tokens,
            use_bridge=True,
        )
    elif args.mode == "infer":
        receipt = probe_and_infer(
            image_path=args.frame, writer="cosmos_cli_infer",
            device=args.device, max_new_tokens=args.max_tokens,
            use_bridge=False,
        )
    elif args.mode == "download":
        start_download()
        receipt = write_status_receipt(writer="cosmos_cli_post_download")

    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    print(f"\nTruth: {receipt['truth']}")
    print(f"Detail: {receipt['detail']}")
    print(f"Receipt → {_RECEIPT_PATH}")


if __name__ == "__main__":
    _main()
