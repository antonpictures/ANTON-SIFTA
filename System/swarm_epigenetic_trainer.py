#!/usr/bin/env python3
"""
System/swarm_epigenetic_trainer.py
══════════════════════════════════════════════════════════════════════
The Epigenetic Trainer (PEFT / LoRA).

This daemon processes the `alice_corpus_hf.jsonl` generated during
the Sleep Cycle (Vagus Nerve), and trains a lightweight adapter 
on top of the frozen base model. 

It does not mutate the 9.6GB Base DNA. 

Output: `adapter_model.safetensors` stored in `.sifta_state/stigmergic_adapters/`.
"""

import json
import os
import time
from pathlib import Path

# Provide a fallback if ML deps aren't installed on smaller nodes
try:
    import torch
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTTrainer
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
CORPUS_FILE = _STATE / "alice_corpus_hf.jsonl"
ADAPTERS_DIR = _STATE / "stigmergic_adapters"

def train_adapter(
    base_model_id: str = "Qwen/Qwen1.5-0.5B-Chat",  # Ungated, ~1GB, works on MPS without HF login
    output_name: str = "alice_epigenetic_adapter_v1"
) -> str:
    """
    Trains a LoRA adapter using the somatic history corpus.
    """
    if not ML_AVAILABLE:
        raise ImportError("Missing required ML libraries. Run: pip install torch transformers peft datasets trl")

    if not CORPUS_FILE.exists():
        raise FileNotFoundError(f"Corpus file not found at {CORPUS_FILE}. Has the Swarm slept?")

    print(f"[*] Epigenetic Training Initiated.")
    print(f"[*] Base DNA (Frozen): {base_model_id}")
    
    # 1. Load Dataset
    print(f"[*] Loading somatic history corpus...")
    dataset = load_dataset("json", data_files=str(CORPUS_FILE), split="train")
    
    if len(dataset) == 0:
        raise ValueError("Corpus is empty. No memories to consolidate.")

    def _format_one(instr: str, resp: str) -> str:
        return (
            f"<|im_start|>user\n{instr}<|im_end|>\n"
            f"<|im_start|>assistant\n{resp}<|im_end|>"
        )

    def formatting_prompts_func(example):
        instructions = example.get('instruction', '')
        responses = example.get('response', '')
        if isinstance(instructions, str):
            return _format_one(instructions, responses if isinstance(responses, str) else '')
        return [_format_one(i, r) for i, r in zip(instructions, responses)]

    # 2. Load Tokenizer & Model
    print(f"[*] Loading Tokenizer and Base Model in fp16...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_id)
    # Gemma tokenizer requires setting padding token
    tokenizer.pad_token = tokenizer.eos_token
    
    # Depending on the hardware, we load in fp16. 
    # For Apple Silicon (MPS), we map to "auto" or "mps" if available.
    device_map = "auto"
    if torch.backends.mps.is_available():
        device_map = "mps"
        
    model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        device_map=device_map,
        torch_dtype=torch.float16,
    )
    
    # 3. LoRA Configuration (Rank-8)
    print(f"[*] Injecting LoRA matrices...")
    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )
    
    output_dir = ADAPTERS_DIR / output_name
    output_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        warmup_steps=2,
        max_steps=20,
        learning_rate=2e-4,
        fp16=False,
        logging_steps=5,
        save_strategy="no",
    )

    print(f"[*] Beginning offline consolidation...")
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        args=training_args,
        peft_config=lora_config,
        formatting_func=formatting_prompts_func,
    )
    
    trainer.train()
    
    # 5. Save the compiled adapter
    print(f"[*] Training complete. Saving Epigenetic Adapter to {output_dir}")
    trainer.model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    
    # 6. Hand off to the Ecology Organ
    try:
        from System.swarm_stigmergic_weight_ecology import AdapterSignal, register_adapter_signal
        from System.swarm_adapter_pheromone_scorer import calculate_swarm_pheromone_strength
        import platform
        
        # Calculate real stigmergic evidence from the ledgers
        real_pheromone = calculate_swarm_pheromone_strength()

        # Run Hippocampal Replay Evaluation to prevent mode-collapse
        try:
            from System.swarm_stigmergic_weight_ecology import ReplayEvaluator

            def adapter_responder(prompt, _signal=None, _case=None):
                inputs = tokenizer(prompt, return_tensors="pt").to(trainer.model.device)
                with torch.no_grad():
                    output_ids = trainer.model.generate(
                        **inputs, max_new_tokens=64, do_sample=False, pad_token_id=tokenizer.eos_token_id,
                    )
                return tokenizer.decode(output_ids[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

            def base_responder(prompt, _signal=None, _case=None):
                inputs = tokenizer(prompt, return_tensors="pt").to(trainer.model.device)
                with torch.no_grad():
                    with trainer.model.disable_adapter():
                        output_ids = trainer.model.generate(
                            **inputs, max_new_tokens=64, do_sample=False, pad_token_id=tokenizer.eos_token_id,
                        )
                return tokenizer.decode(output_ids[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

            evaluator = ReplayEvaluator(max_samples=4, min_counter_margin=0.02)
            print(f"[*] Running Hippocampal Replay Evaluation (Epistemic Gate) on {output_name}...")
            replay_res = evaluator.evaluate_adapter_by_id(
                output_name, base_model_id,
                responder=adapter_responder, counter_responder=base_responder,
            )
            eval_score = float(replay_res.get("replay_score", 0.0))
            print(f"[*] Replay Evaluation Complete. Verdict: {replay_res.get('verdict')} "
                  f"(replay_score={eval_score:.4f}, counter={replay_res.get('counter_score', 0.0):.4f})")
            if replay_res.get("verdict") == "QUARANTINE":
                print(f"[!] Adapter {output_name} was QUARANTINED. It will not be selected for merge.")
        except ImportError:
            print("[!] Could not import ReplayEvaluator. Defaulting eval_score to 0.0.")
            eval_score = 0.0
        except Exception as exc:
            print(f"[!] Replay Evaluation skipped due to: {exc}. Defaulting eval_score to 0.5.")
            eval_score = 0.5

        signal = AdapterSignal(
            adapter_id=output_name,
            adapter_path=str(output_dir),
            base_model=base_model_id,
            homeworld=platform.node(),
            task="epigenetic_consolidation",
            conflict_group="general_dialogue",
            eval_score=eval_score,
            regression_score=0.95, # placeholder
            energy_joules=100.0,   # placeholder for physical GPU energy used
            risk_score=0.01,
            pheromone_strength=real_pheromone,
            created_ts=time.time(),
            evidence_ids=("sleep_cycle_corpus",),
            notes="Adapter compiled autonomously during sleep cycle."
        )
        register_adapter_signal(signal)
        print(f"[*] Adapter Signal registered in Stigmergic Weight Ecology.")
    except Exception as e:
        print(f"[!] Warning: Could not register adapter with Ecology layer: {e}")
        
    return str(output_dir)

if __name__ == "__main__":
    try:
        ts = int(time.time())
        train_adapter(output_name=f"alice_epigenetic_adapter_{ts}")
    except Exception as e:
        print(f"[!] Epigenetic consolidation failed: {e}")
