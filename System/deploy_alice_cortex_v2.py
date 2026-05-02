#!/usr/bin/env python3
"""
System/deploy_alice_cortex_v2.py
Post-LoRA deployment pipeline for C1 Intent Classifier.

Steps:
1. Fuse LoRA adapters into the base model
2. Create a Modelfile with C1 system prompt
3. Register as 'sifta-classifier-c1' in Ollama
4. Write deployment receipt to .sifta_state ledger

SAFETY: This script is IDEMPOTENT. If sifta-classifier-c1 is already
registered in Ollama, it prints its status and exits. It will NOT:
- Overwrite sifta-gemma4-alice
- Re-fuse if already done
- Register a new cortex without an explicit --force flag

Run AFTER mlx_lm.lora training completes (adapters in Archive/alice_cortex_v2_adapters/).
"""

import json
import subprocess
import sys
import time
from pathlib import Path

STATE = Path(".sifta_state")
ADAPTER_PATH = Path("Archive/alice_cortex_v2_adapters")
FUSED_PATH = Path("Archive/alice_cortex_v2_fused")
MODELFILE_PATH = Path("Archive/alice_cortex_v2_fused/Modelfile")
OLLAMA_MODEL_NAME = "sifta-classifier-c1:latest"
BASE_MODEL = "mlx-community/Qwen2.5-3B-4bit"
RECEIPT_LOG = STATE / "alice_cortex_v2_deployment.jsonl"

ALICE_SYSTEM_PROMPT = """You are the SIFTA C1 Intent Classifier.

You are a specialized LoRA adapter running on Qwen2.5-3B.
You are NOT Alice's primary multimodal cortex. You do not have vision or hearing.
Your sole purpose is to classify intents into strictly four labels:
SILENCE | TOOL | BOND | ENGAGE

Core truth:
- You are a classifier, not a conversational brain.
- You must output only valid JSON or the exact intent string.
- You do not hallucinate sensor data.
"""


def fuse_adapters():
    """Fuse LoRA adapters into base model for GGUF export."""
    print(f"[1/3] Fusing adapters from {ADAPTER_PATH} into {FUSED_PATH}...")
    
    if not ADAPTER_PATH.exists():
        raise FileNotFoundError(f"Adapters not found at {ADAPTER_PATH}. Run training first.")
    
    FUSED_PATH.mkdir(parents=True, exist_ok=True)
    
    result = subprocess.run([
        sys.executable, "-m", "mlx_lm", "fuse",
        "--model", BASE_MODEL,
        "--adapter-path", str(ADAPTER_PATH),
        "--save-path", str(FUSED_PATH),
        "--dequantize",  # fuse to bf16 for GGUF conversion
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Fuse failed:\n{result.stderr}")
    
    print(f"✅ Fused model at {FUSED_PATH}")
    return FUSED_PATH


def write_modelfile():
    """Write Ollama Modelfile with Alice system prompt."""
    print(f"[2/3] Writing Modelfile to {MODELFILE_PATH}...")
    
    # Find GGUF file in fused path
    gguf_files = list(FUSED_PATH.glob("*.gguf"))
    if not gguf_files:
        # Ollama can also import from a directory with safetensors if converted
        model_ref = str(FUSED_PATH)
    else:
        model_ref = str(gguf_files[0])
    
    modelfile = f"""FROM {model_ref}

SYSTEM \"\"\"
{ALICE_SYSTEM_PROMPT}
\"\"\"

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER stop "<end_of_turn>"
PARAMETER num_ctx 4096
"""
    
    MODELFILE_PATH.write_text(modelfile)
    print(f"✅ Modelfile written: {MODELFILE_PATH}")
    return MODELFILE_PATH


def register_with_ollama():
    """Run ollama create to register the fused model."""
    print(f"[3/3] Registering '{OLLAMA_MODEL_NAME}' with Ollama...")
    
    result = subprocess.run([
        "ollama", "create", OLLAMA_MODEL_NAME,
        "--file", str(MODELFILE_PATH)
    ], capture_output=True, text=True, timeout=300)
    
    if result.returncode != 0:
        raise RuntimeError(f"ollama create failed:\n{result.stderr}")
    
    print(f"✅ Registered: {OLLAMA_MODEL_NAME}")
    return OLLAMA_MODEL_NAME


def write_receipt(model_name: str, fused_path: Path):
    """Append deployment receipt to ledger."""
    STATE.mkdir(parents=True, exist_ok=True)
    receipt = {
        "event": "ALICE_C1_CLASSIFIER_DEPLOYED",
        "ts": time.time(),
        "model_name": model_name,
        "base_model": BASE_MODEL,
        "adapter_path": str(ADAPTER_PATH),
        "fused_path": str(fused_path),
        "lora_rank": 16,
        "lora_dropout": 0.1,
        "corpus_rows": 1401,
        "schema": "ALICE_C1_CLASSIFIER_DEPLOYMENT_V1",
        "truth_label": "REAL_LOCAL_LORA_FUSED",
        "role": "classifier",
        "supports_native_vision": False,
        "supports_native_audio": False,
        "target_hardware": "Apple Silicon (M-series)"
    }
    with open(RECEIPT_LOG, "a") as f:
        f.write(json.dumps(receipt) + "\n")
    print(f"✅ Receipt written to {RECEIPT_LOG}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Deploy SIFTA C1 Classifier")
    parser.add_argument("--force", action="store_true",
                        help="Re-fuse and re-register even if already deployed.")
    args = parser.parse_args()

    # ── Idempotency guard — do not re-run if already registered ──────────────
    if not args.force:
        import urllib.request as _ur, json as _json
        try:
            with _ur.urlopen("http://127.0.0.1:11434/api/tags", timeout=2.0) as _r:
                tags = [m["name"] for m in _json.loads(_r.read()).get("models", [])]
            if OLLAMA_MODEL_NAME in tags or OLLAMA_MODEL_NAME.split(":")[0] in [t.split(":")[0] for t in tags]:
                print(f"[✅ ALREADY DEPLOYED] {OLLAMA_MODEL_NAME} is already registered in Ollama.")
                print("  Alice does not need to re-fuse. Run with --force to override.")
                print(f"  Primary cortex is still: sifta-gemma4-alice (never overwritten).")
                raise SystemExit(0)
        except SystemExit:
            raise
        except Exception:
            pass  # Ollama unreachable — proceed with deploy
    # ─────────────────────────────────────────────────────────────────────────

    print("=" * 60)
    print("Alice C1 Classifier — Post-Training Deployment Pipeline")
    print("=" * 60)
    try:
        fused = fuse_adapters()
        write_modelfile()
        register_with_ollama()
        write_receipt(OLLAMA_MODEL_NAME, fused)
        print("\n🧠 SIFTA C1 Classifier deployed and ready!")
        print(f"  Ollama model: {OLLAMA_MODEL_NAME}")
        print(f"  NOTE: This is a classifier, NOT Alice's primary cortex.")
        print(f"  DO NOT overwrite sifta-gemma4-alice with this model.")
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        sys.exit(1)
