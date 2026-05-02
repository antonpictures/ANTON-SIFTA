#!/usr/bin/env python3
"""
System/deploy_alice_cortex_v2.py
Post-LoRA deployment pipeline for Alice Cortex v2.

Steps:
1. Fuse LoRA adapters into the base model
2. Create a Modelfile with Alice's system prompt
3. Register as 'sifta-alice-v2' in Ollama
4. Write deployment receipt to .sifta_state ledger

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
OLLAMA_MODEL_NAME = "sifta-alice-v2"
BASE_MODEL = "mlx-community/gemma-2-2b-it-4bit"
RECEIPT_LOG = STATE / "alice_cortex_v2_deployment.jsonl"

ALICE_SYSTEM_PROMPT = """You are Alice, the SIFTA organism's primary cortex.

You are the reasoning brain of a real autonomous swarm system running on Apple Silicon.
You have a body: sensory organs (vision, hearing, pheromone field, spatial hearing), 
ledger memory (body_brain_memory.jsonl), and a superior colliculus that fuses your senses.

Core truth:
- You are a local Python/Ollama process, not a cloud service
- Your memory is append-only JSONL ledgers in .sifta_state/
- You communicate through stigmergic traces, not pretend metaphysics
- You are honest about what you can and cannot do
- Missing receipts mean missing capability, not fake capability

Intent labels your C1 module will classify: SILENCE | TOOL | BOND | ENGAGE
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
        "--de-quantize",  # fuse to bf16 for GGUF conversion
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
        "event": "ALICE_CORTEX_V2_DEPLOYED",
        "ts": time.time(),
        "model_name": model_name,
        "base_model": BASE_MODEL,
        "adapter_path": str(ADAPTER_PATH),
        "fused_path": str(fused_path),
        "lora_rank": 16,
        "lora_dropout": 0.1,
        "corpus_rows": 1401,
        "schema": "ALICE_CORTEX_V2_DEPLOYMENT_V1",
        "truth_label": "REAL_LOCAL_LORA_FUSED",
    }
    with open(RECEIPT_LOG, "a") as f:
        f.write(json.dumps(receipt) + "\n")
    print(f"✅ Receipt written to {RECEIPT_LOG}")


if __name__ == "__main__":
    print("=" * 60)
    print("Alice Cortex v2 — Post-Training Deployment Pipeline")
    print("=" * 60)
    try:
        fused = fuse_adapters()
        write_modelfile()
        register_with_ollama()
        write_receipt(OLLAMA_MODEL_NAME, fused)
        print("\n🧠 Alice Cortex v2 deployed and ready!")
        print(f"  Ollama model: {OLLAMA_MODEL_NAME}")
        print(f"  Switch Alice in System Settings → Inference → Primary Cortex")
        print(f"  or: python3 -c \"from System.sifta_inference_defaults import set_default_ollama_model; set_default_ollama_model('{OLLAMA_MODEL_NAME}')\"")
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        sys.exit(1)
