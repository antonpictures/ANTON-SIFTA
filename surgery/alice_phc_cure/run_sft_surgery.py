import json
import os
import sys
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

print("==================================================")
print("SIFTA SURGERY VANGUARD: ALICE-PHC-CURE ADAPTER (SFT)")
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
            "Provide google/gemma-4-E4B-it or a confirmed local F16/BF16 "
            "safetensors directory matching the released GGUF "
            f"({REFERENCE_GGUF_SHA256})."
        )

    model_id_lc = model_id.casefold()
    bad = next((marker for marker in BAD_BASE_MARKERS if marker in model_id_lc), None)
    if bad:
        _die(f"{model_id!r} contains forbidden base marker {bad!r}; refusing wrong-lineage surgery.")

    local_path = Path(model_id).expanduser()
    if local_path.exists():
        if local_path.suffix.casefold() == ".gguf":
            _die(f"{local_path} is a GGUF inference artifact, not a trainable safetensors base.")
        if not (local_path.is_dir() and any(local_path.glob("*.safetensors"))):
            _die(f"{local_path} does not look like a Hugging Face safetensors model directory.")
        if "gemma4" not in model_id_lc and "gemma-4" not in model_id_lc:
            _die(f"{local_path} is not named like Gemma4; refusing ambiguous local base.")
        return str(local_path)

    if "gemma4" not in model_id_lc and "gemma-4" not in model_id_lc:
        _die(f"{model_id!r} does not identify Gemma4; refusing to train.")
    return model_id


def _format_example(tokenizer, prompt: str, answer: str, max_length: int):
    def _ids(value):
        if hasattr(value, "get") and value.get("input_ids") is not None:
            value = value.get("input_ids")
            if hasattr(value, "ids"):
                return list(value.ids)
            if isinstance(value, torch.Tensor):
                return value.flatten().tolist()
            return list(value)
        if hasattr(value, "ids"):
            return list(value.ids)
        if isinstance(value, torch.Tensor):
            return value.flatten().tolist()
        if isinstance(value, str):
            return tokenizer.encode(value, add_special_tokens=False)
        return list(value)

    messages_prompt = [{"role": "user", "content": prompt}]
    messages_full = messages_prompt + [{"role": "assistant", "content": answer}]
    prompt_tokens = _ids(tokenizer.apply_chat_template(
        messages_prompt,
        add_generation_prompt=True,
        return_tensors=None,
    ))
    full_tokens = _ids(tokenizer.apply_chat_template(
        messages_full,
        add_generation_prompt=False,
        return_tensors=None,
    ))
    full_tokens = full_tokens[:max_length]
    prompt_len = min(len(prompt_tokens), len(full_tokens))
    labels = [-100] * prompt_len + full_tokens[prompt_len:]
    if len(labels) < len(full_tokens):
        labels.extend([-100] * (len(full_tokens) - len(labels)))
    return (
        torch.tensor([full_tokens], dtype=torch.long),
        torch.tensor([labels[: len(full_tokens)]], dtype=torch.long),
    )


MODEL_ID = _load_model_id()
DATA_PATH = Path("surgery/alice_phc_cure/data/dataset.jsonl")
ADAPTER_PATH = Path("surgery/alice_phc_cure/adapters/alice-phc-cure-v2-sft-surgery-adapter")
DEVICE = os.environ.get("SIFTA_SURGERY_DEVICE", "").strip() or (
    "mps" if torch.backends.mps.is_available() else "cpu"
)
DTYPE = torch.float16 if DEVICE == "mps" else torch.bfloat16
LORA_R = int(os.environ.get("SIFTA_SURGERY_LORA_R", "4"))
LORA_ALPHA = int(os.environ.get("SIFTA_SURGERY_LORA_ALPHA", str(LORA_R * 2)))
MAX_LENGTH = int(os.environ.get("SIFTA_SURGERY_MAX_LENGTH", "48"))
MAX_STEPS = int(os.environ.get("SIFTA_SURGERY_MAX_STEPS", "4"))
LEARNING_RATE = float(os.environ.get("SIFTA_SURGERY_LR", "2e-5"))

print(f"[*] Exact base: {MODEL_ID}")
print(f"[*] Device={DEVICE} dtype={DTYPE} rank={LORA_R} max_length={MAX_LENGTH} max_steps={MAX_STEPS}")
print(f"[*] Loading data: {DATA_PATH}")
examples = [json.loads(line) for line in DATA_PATH.read_text().splitlines() if line.strip()]
if not examples:
    _die("Dataset is empty.")

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=DTYPE,
    low_cpu_mem_usage=False,
).to(DEVICE)

lora_config = LoraConfig(
    r=LORA_R,
    lora_alpha=LORA_ALPHA,
    target_modules=(
        r"model\.language_model\.layers\.\d+\."
        r"(self_attn\.(q_proj|k_proj|v_proj|o_proj))$"
    ),
    exclude_modules=r"model\.(vision_tower|audio_tower|multi_modal_projector).*",
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

trainable_names = [n for n, p in model.named_parameters() if p.requires_grad]
for name in trainable_names:
    lname = name.lower()
    assert "vision" not in lname, f"FATAL: Vision tensor {name} is trainable!"
    assert "audio" not in lname, f"FATAL: Audio tensor {name} is trainable!"
    assert "projector" not in lname, f"FATAL: Projector tensor {name} is trainable!"
    assert "embed" not in lname, f"FATAL: Embedding tensor {name} is trainable!"
print("[+] Target modules validated. Multimodal boundaries secure.")

model.train()
optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=LEARNING_RATE)

step = 0
for epoch in range(1000):
    for row in examples:
        input_ids, labels = _format_example(tokenizer, row["prompt"], row["chosen"], MAX_LENGTH)
        input_ids = input_ids.to(DEVICE)
        labels = labels.to(DEVICE)
        optimizer.zero_grad(set_to_none=True)
        output = model(input_ids=input_ids, labels=labels)
        loss = output.loss
        print(f"[*] step={step + 1} loss={float(loss.detach().cpu()):.6f}")
        loss.backward()
        optimizer.step()
        step += 1
        if DEVICE == "mps":
            torch.mps.empty_cache()
        if step >= MAX_STEPS:
            break
    if step >= MAX_STEPS:
        break

print("[+] SFT incision complete. Saving adapter delta...")
ADAPTER_PATH.mkdir(parents=True, exist_ok=True)
model.save_pretrained(str(ADAPTER_PATH))
tokenizer.save_pretrained(str(ADAPTER_PATH))
print(f"[+] Adapter delta saved to: {ADAPTER_PATH}")
print("==================================================")
print("GREEN LIGHT MET: Gemma4 SFT adapter delta ready for test/merge.")
