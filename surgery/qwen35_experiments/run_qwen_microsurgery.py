import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
from trl import DPOTrainer, DPOConfig
import os

print("==================================================")
print("SIFTA MICROSURGERY VANGUARD: QWEN 0.8B RECOVERY")
print("Target: Qwen 0.8b (Qwen/Qwen1.5-0.5B-Chat)")
print("==================================================")

DATA_PATH = "surgery/qwen35_experiments/data/balanced_dataset.jsonl"
MODEL_ID = "Qwen/Qwen1.5-0.5B-Chat"
OUTPUT_DIR = "surgery/qwen35_experiments/adapters/microsurgery"

print(f"[*] Loading balanced dataset from {DATA_PATH}")
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

print("[*] Configuring LoRA (Micro-Surgery Profile)")
lora_config = LoraConfig(
    r=4,
    lora_alpha=8,
    target_modules=["q_proj", "v_proj", "o_proj"], # Removed gate, up, down, k
    lora_dropout=0.08,
    bias="none",
    task_type="CAUSAL_LM"
)

peft_model = get_peft_model(model, lora_config)

print("[*] Initializing DPOTrainer")
training_args = DPOConfig(
    output_dir=OUTPUT_DIR,
    beta=0.1,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=2,
    learning_rate=1e-5, # Significantly lowered
    max_steps=80, # Hard cap on steps, no epochs
    save_steps=20, # Save checkpoint every 20 steps
    logging_steps=5,
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

print("[*] Running Micro-Surgery DPO Pass...")
trainer.train()

print(f"[*] Saving Final Adapter Delta to {OUTPUT_DIR}/final...")
trainer.save_model(os.path.join(OUTPUT_DIR, "final"))

print("[SUCCESS] Micro-surgery complete. Checkpoints saved.")
