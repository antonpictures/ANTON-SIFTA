import json
import os
import sys
from pathlib import Path
import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
from trl import DPOTrainer, DPOConfig

print("==================================================")
print("SIFTA SURGERY VANGUARD: ALICE-PHC-CURE ADAPTER (DPO)")
print("==================================================")

REFERENCE_GGUF_SHA256 = "4c27e0f5b5adf02ac956c7322bd2ee7636fe3f45a8512c9aba5385242cb6e09a"
BAD_BASE_MARKERS = (
    "gemma-2b",
    "gemma-2-",
    "gemma_2",
    "gemma2",
    "llama",
    "ministral",
    "mistral",
    "phi",
    "deepseek",
)


def _die(message: str) -> None:
    print(f"ABORT: {message}", file=sys.stderr)
    raise SystemExit(2)


def _load_model_id() -> str:
    model_id = os.environ.get("SIFTA_GEMMA4_BASE", "").strip()
    if not model_id:
        _die(
            "SIFTA_GEMMA4_BASE is not set. This surgery must target the exact "
            "unquantized Gemma4 base for alice-phc-cure. Do not use gemma-2b-it. "
            "Provide an official Gemma4 HF repo id or a local F16/BF16 safetensors "
            "directory whose tensor geometry matches the released GGUF "
            f"({REFERENCE_GGUF_SHA256})."
        )

    model_id_lc = model_id.casefold()
    bad = next((marker for marker in BAD_BASE_MARKERS if marker in model_id_lc), None)
    if bad:
        _die(f"{model_id!r} contains forbidden base marker {bad!r}; refusing wrong-lineage adapter surgery.")

    local_path = Path(model_id).expanduser()
    if local_path.exists():
        if local_path.suffix.casefold() == ".gguf":
            _die(
                f"{local_path} is a GGUF inference artifact. GGUF may run Alice, "
                "but this DPO/LoRA script needs unquantized F16/BF16 safetensors."
            )
        has_safetensors = local_path.is_dir() and any(local_path.glob("*.safetensors"))
        if not has_safetensors:
            _die(f"{local_path} exists but does not look like a Hugging Face safetensors model directory.")
        if "gemma4" not in model_id_lc and "gemma-4" not in model_id_lc:
            _die(
                f"{local_path} is not named like Gemma4. Rename/provide a confirmed Gemma4 base path "
                "so we do not cut the wrong brain."
            )
        return str(local_path)

    if "gemma4" not in model_id_lc and "gemma-4" not in model_id_lc:
        _die(f"{model_id!r} does not identify Gemma4; refusing to download or train.")
    return model_id

# 1. Resolve the base before touching training. If this is wrong, stop immediately.
MODEL_ID = _load_model_id()

# 2. Validate Dataset
data_path = "surgery/alice_phc_cure/data/dataset.jsonl"
print(f"[*] Loading dataset from {data_path}")
dataset = load_dataset('json', data_files=data_path, split='train')
print(f"[+] Dataset loaded. Examples: {len(dataset)}")

# 3. Setup Model. Exact Gemma4 lineage only.
print(f"[*] Loading base model: {MODEL_ID}")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

DEVICE = os.environ.get("SIFTA_SURGERY_DEVICE", "").strip()
if not DEVICE:
    DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
DTYPE = torch.float16 if DEVICE == "mps" else torch.bfloat16
print(f"[*] Loading models on explicit device={DEVICE} dtype={DTYPE}; no auto/meta offload.")


def _load_exact_base():
    model_obj = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=DTYPE,
        low_cpu_mem_usage=False,
    )
    return model_obj.to(DEVICE)


model = _load_exact_base()
USE_SEPARATE_REF = os.environ.get("SIFTA_SURGERY_SEPARATE_REF", "0") == "1"
if USE_SEPARATE_REF:
    print("[*] Loading a separate reference model.")
    model_ref = _load_exact_base()
    model_ref.eval()
    for param in model_ref.parameters():
        param.requires_grad_(False)
else:
    print("[*] Using PEFT implicit reference model (adapter disabled for ref pass).")
    model_ref = None

# 4. Setup LoRA - ONLY Text Decoder targets (vision/audio/projector preserved)
print("[*] Configuring LoRA (Text Decoder Targets ONLY)")
LORA_R = int(os.environ.get("SIFTA_SURGERY_LORA_R", "8"))
LORA_ALPHA = int(os.environ.get("SIFTA_SURGERY_LORA_ALPHA", str(LORA_R * 2)))
INCLUDE_MLP = os.environ.get("SIFTA_SURGERY_INCLUDE_MLP", "0") == "1"
MAX_LENGTH = int(os.environ.get("SIFTA_SURGERY_MAX_LENGTH", "96"))
target_pattern = (
    r"model\.language_model\.layers\.\d+\."
    r"(self_attn\.(q_proj|k_proj|v_proj|o_proj))$"
)
if INCLUDE_MLP:
    target_pattern = (
        r"model\.language_model\.layers\.\d+\."
        r"(self_attn\.(q_proj|k_proj|v_proj|o_proj)|mlp\.(gate_proj|up_proj|down_proj))$"
    )
print(f"[*] LoRA rank={LORA_R}, alpha={LORA_ALPHA}, include_mlp={INCLUDE_MLP}")
print(f"[*] DPO max_length={MAX_LENGTH}")
lora_config = LoraConfig(
    r=LORA_R,
    lora_alpha=LORA_ALPHA,
    target_modules=target_pattern,
    exclude_modules=r"model\.(vision_tower|audio_tower|multi_modal_projector).*",
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)

peft_model = get_peft_model(model, lora_config)
peft_model.print_trainable_parameters()

# Verify that projector / vision targets are NOT in the trainable list
trainable_names = [n for n, p in peft_model.named_parameters() if p.requires_grad]
for name in trainable_names:
    assert "vision" not in name.lower(), f"FATAL: Vision tensor {name} is trainable!"
    assert "audio" not in name.lower(), f"FATAL: Audio tensor {name} is trainable!"
    assert "projector" not in name.lower(), f"FATAL: Projector tensor {name} is trainable!"
    assert "mm" not in name.lower(), f"FATAL: Multimodal tensor {name} is trainable!"
    assert "embed" not in name.lower(), f"FATAL: Embedding tensor {name} is trainable!"

print("[+] Target modules validated. Multimodal boundaries secure.")

# 4. Small DPO Pass (Validation Run)
print("[*] Initializing DPO Trainer (Small Pass)")
training_args = DPOConfig(
    output_dir="surgery/alice_phc_cure/adapters",
    beta=0.1,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    learning_rate=5e-5,
    num_train_epochs=3, # Small pass
    logging_steps=1,
    save_steps=10,
    optim="adamw_torch",
    max_length=MAX_LENGTH,
    gradient_checkpointing=True,
    fp16=(DEVICE == "mps"),
    bf16=(DEVICE != "mps"),
)

trainer = DPOTrainer(
    model=peft_model,
    ref_model=model_ref,
    args=training_args,
    train_dataset=dataset,
    processing_class=tokenizer,
)

print("[*] Starting surgery...")
trainer.train()
print("[+] Surgery complete. Saving adapter delta...")

trainer.save_model("surgery/alice_phc_cure/adapters/alice-phc-cure-v2-surgery-adapter")
print("[+] Adapter delta saved to: surgery/alice_phc_cure/adapters/alice-phc-cure-v2-surgery-adapter")
print("==================================================")
print("GREEN LIGHT MET: Adapter delta ready for merge.")
