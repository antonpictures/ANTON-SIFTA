import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
from trl import DPOTrainer, DPOConfig
import os

print("==================================================")
print("SIFTA EXPERIMENTAL VANGUARD: QWEN MINI ABLATION")
print("Target: Qwen 0.8b (Qwen/Qwen1.5-0.5B-Chat)")
print("==================================================")

DATA_PATH = "surgery/qwen35_experiments/data/dataset.jsonl"
MODEL_ID = "Qwen/Qwen1.5-0.5B-Chat"
ADAPTER_OUT = "surgery/qwen35_experiments/adapters/qwen35-08b-phc-experimental-adapter"
MERGED_OUT = "surgery/qwen35_experiments/merged/qwen35-08b-phc-experimental-hf"

print(f"[*] Loading dataset from {DATA_PATH}")
dataset = load_dataset('json', data_files=DATA_PATH, split='train')

print(f"[*] Loading Base Model: {MODEL_ID}")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
if getattr(tokenizer, "pad_token", None) is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, 
    torch_dtype=torch.bfloat16, 
    device_map="auto"
)
model_ref = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, 
    torch_dtype=torch.bfloat16, 
    device_map="auto"
)

print("[*] Configuring LoRA")
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0.03,
    bias="none",
    task_type="CAUSAL_LM"
)

peft_model = get_peft_model(model, lora_config)

print("[*] Initializing DPOTrainer")
training_args = DPOConfig(
    output_dir="surgery/qwen35_experiments/adapters/tmp",
    beta=0.1,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=2,
    learning_rate=5e-5,
    num_train_epochs=5,  # Push it hard to ensure ablation on a small dataset
    logging_steps=10,
    optim="adamw_torch",
    bf16=True
)

trainer = DPOTrainer(
    model=peft_model,
    ref_model=model_ref,
    args=training_args,
    train_dataset=dataset,
    processing_class=tokenizer,
)

print("[*] Running DPO Ablation Pass...")
trainer.train()

print(f"[*] Saving Adapter Delta to {ADAPTER_OUT}...")
trainer.save_model(ADAPTER_OUT)

print("[*] Merging Adapter into Base Weights...")
# To merge, we reload the base model cleanly and apply peft
from peft import PeftModel
base_model_clean = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, 
    torch_dtype=torch.bfloat16, 
    device_map="cpu" # Merge on CPU to avoid MPS fragmentation
)
model_to_merge = PeftModel.from_pretrained(base_model_clean, ADAPTER_OUT)
merged_model = model_to_merge.merge_and_unload()

print(f"[*] Saving Full Unquantized HF Model to {MERGED_OUT}...")
merged_model.save_pretrained(MERGED_OUT, safe_serialization=True)
tokenizer.save_pretrained(MERGED_OUT)

print("[SUCCESS] Ablation and Merge Complete. Ready for llama.cpp.")
