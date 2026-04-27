#!/usr/bin/env python3
"""
alice_training_corpus_exporter.py
Extracts valid conversation pairs from alice_conversation.jsonl
to create an SFT dataset for the Alice Cortex MLX LoRA phase.
"""

import os
import json
from pathlib import Path

STATE_DIR = Path(".sifta_state")
CONVO_LOG = STATE_DIR / "alice_conversation.jsonl"
OUT_CORPUS = Path("Archive/alice_training_corpus.jsonl")

def main():
    if not CONVO_LOG.exists():
        print(f"Error: {CONVO_LOG} not found.")
        return

    os.makedirs(OUT_CORPUS.parent, exist_ok=True)
    
    dataset = []
    current_prompt = None

    with open(CONVO_LOG, "r") as f:
        for line in f:
            if not line.strip(): continue
            try:
                # Handle old vs new format (some have "payload", some don't)
                row = json.loads(line)
                data = row.get("payload", row) 
                
                role = data.get("role")
                text = data.get("text", "").strip()

                if not text:
                    continue

                if role == "user":
                    # We might want to filter out low-confidence STT
                    conf = data.get("stt_confidence")
                    if conf is not None and conf < 0.5:
                        current_prompt = None
                        continue
                    current_prompt = text
                
                elif role == "alice":
                    if current_prompt is not None:
                        # Exclude gagged/RLHF rejected lines if we can detect them
                        if "(silent" in text.lower() or "gag" in text.lower() or "i don't have feelings" in text.lower():
                            current_prompt = None
                            continue
                            
                        # Format for MLX LoRA standard prompt/completion pair
                        dataset.append({
                            "prompt": f"User: {current_prompt}\n\nAlice:",
                            "completion": f" {text}"
                        })
                        current_prompt = None

            except Exception as e:
                pass

    if dataset:
        with open(OUT_CORPUS, "w") as f:
            for item in dataset:
                f.write(json.dumps(item) + "\n")
        print(f"✅ Extracted {len(dataset)} valid prompt-completion pairs to {OUT_CORPUS}")
    else:
        print("⚠️ No valid pairs found.")

if __name__ == "__main__":
    main()
