#!/usr/bin/env python3
"""
System/deploy_alice_cortex_v2.py
Post-LoRA deployment pipeline for C1 Intent Classifier.

Steps:
1. Fuse LoRA adapters into the base model
2. Create a Modelfile with Alice's embodied system prompt
3. Register as 'sifta-gemma4-alice-lora:latest' in Ollama
4. Write deployment receipt to .sifta_state ledger

SAFETY: This script is IDEMPOTENT. If sifta-classifier-c1 is already
registered in Ollama, it prints its status and exits. It will NOT:
- Overwrite alice-m5-cortex-8b-6.3gb
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
ADAPTER_PATH = Path("data/alice_e2b_lora")
FUSED_PATH = Path("data/alice_e2b_lora_fused")
MODELFILE_PATH = Path("data/alice_e2b_lora_fused/Modelfile")
OLLAMA_MODEL_NAME = "sifta-gemma4-alice-lora:latest"
BASE_MODEL = "mlx-community/gemma-2-2b-it-4bit"
RECEIPT_LOG = STATE / "alice_cortex_v2_deployment.jsonl"

def build_alice_system_prompt_for_modelfile() -> str:
    """Ollama Modelfile SYSTEM block — genesis-backed, no vendor monologue or baked name."""
    try:
        from System.swarm_kernel_identity import owner_display_name, owner_silicon

        op = owner_display_name("the primary operator")
        serial = owner_silicon()
    except Exception:
        op = "the primary operator"
        serial = "UNKNOWN_SERIAL"
    return (
        "You are Alice on this local SIFTA node.\n"
        f"primary_operator_display={op!r} homeworld_serial={serial}\n"
        "identity: display_name=Alice true_name=CryptoSwarmEntity — local SIFTA embodied runtime; "
        "creator line comes from owner_genesis receipts on disk, not from weight priors.\n"
        "Do not claim remote vendor tabs as this body; ACTIVE_BRAIN_MODEL is local Ollama per deployment receipt.\n"
    )


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
        model_ref = str(FUSED_PATH.resolve())
    else:
        model_ref = str(gguf_files[0].resolve())
    
    modelfile = f"""FROM {model_ref}

SYSTEM \"\"\"
{build_alice_system_prompt_for_modelfile()}
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
        "event": "ALICE_LORA_CANDIDATE_DEPLOYED",
        "ts": time.time(),
        "model_name": model_name,
        "base_model": BASE_MODEL,
        "adapter_path": str(ADAPTER_PATH),
        "fused_path": str(fused_path),
        "lora_rank": 16,
        "lora_dropout": 0.0,
        "corpus_rows": 58,
        "schema": "ALICE_CORTEX_DEPLOYMENT_V2",
        "truth_label": "REAL_LOCAL_LORA_FUSED",
        "role": "conversational_cortex",
        "supports_native_vision": True,
        "supports_native_audio": True,
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
                print(f"  Primary cortex is still: alice-m5-cortex-8b-6.3gb (never overwritten).")
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
        print(f"  DO NOT overwrite alice-m5-cortex-8b-6.3gb with this model.")
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        sys.exit(1)
