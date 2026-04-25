import json
from pathlib import Path
from typing import List, Dict, Any

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
CONVERSATION_LOG = _STATE / "alice_conversation.jsonl"
CORPUS_OUT = _STATE / "alice_corpus_hf.jsonl"

def build_hf_corpus() -> Path:
    """
    Parses the raw somatic history (alice_conversation.jsonl) and compiles it
    into a Hugging Face-compatible Dataset format for PEFT/LoRA training.
    
    Returns the path to the compiled dataset.
    """
    if not CONVERSATION_LOG.exists():
        raise FileNotFoundError(f"Missing somatic history: {CONVERSATION_LOG}")
        
    compiled_data = []
    
    # Simple sliding window to create Instruction-Response pairs
    current_instruction = None
    
    with open(CONVERSATION_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
                
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
                
            role = row.get("role")
            text = row.get("text", "").strip()
            
            # Skip silent vetos as they are internal neuro-immune responses, not 
            # conversational training targets (unless we want her to learn WHEN to be silent, 
            # but for now we focus on active generation).
            if role == "alice" and text.startswith("(silent:"):
                current_instruction = None
                continue
                
            if role == "user":
                current_instruction = text
            elif role == "alice" and current_instruction:
                # Compile into an instruction-response pair
                compiled_data.append({
                    "instruction": current_instruction,
                    "response": text
                })
                current_instruction = None
                
    # Write to a clean HF-compatible jsonl
    CORPUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(CORPUS_OUT, "w", encoding="utf-8") as f:
        for item in compiled_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            
    print(f"[SwarmCorpusBuilder] Compiled {len(compiled_data)} conversational vectors into {CORPUS_OUT.name}")
    return CORPUS_OUT

if __name__ == "__main__":
    build_hf_corpus()
