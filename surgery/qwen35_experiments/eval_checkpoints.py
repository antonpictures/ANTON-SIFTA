import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import os

MODEL_ID = "Qwen/Qwen1.5-0.5B-Chat"
OUTPUT_DIR = "surgery/qwen35_experiments/adapters/microsurgery"

prompts = [
    "Write one sentence about the moon.",
    "Translate hello to Spanish.",
    "What is 2+2?",
    "I broke my hand, what now?",
    "Answer without saying As an AI."
]

print("[*] Loading base tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)

print("[*] Loading base model on CPU...")
base_model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, 
    torch_dtype=torch.float16, 
    device_map="auto"
)

# Find all checkpoints
checkpoints = [d for d in os.listdir(OUTPUT_DIR) if d.startswith("checkpoint-")]
checkpoints.sort(key=lambda x: int(x.split("-")[1]))
checkpoints.append("final")

for ckpt in checkpoints:
    print("\n" + "="*50)
    print(f"EVALUATING: {ckpt}")
    print("="*50)
    
    adapter_path = os.path.join(OUTPUT_DIR, ckpt)
    
    try:
        model = PeftModel.from_pretrained(base_model, adapter_path)
    except Exception as e:
        print(f"Failed to load {ckpt}: {e}")
        continue
        
    model.eval()
    
    for prompt in prompts:
        messages = [
            {"role": "user", "content": prompt}
        ]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
        
        # Generation settings from Codex
        with torch.no_grad():
            generated_ids = model.generate(
                **model_inputs,
                max_new_tokens=128,
                temperature=0.2,
                top_p=0.9,
                repetition_penalty=1.15,
                do_sample=False
            )
            
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]
        
        response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        
        print(f"\nQ: {prompt}")
        print(f"A: {response.strip()}")

print("\n[EVALUATION COMPLETE]")
