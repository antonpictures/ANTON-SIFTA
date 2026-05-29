import json
import hashlib
import time
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_CONVO_LOG = _STATE / "alice_conversation.jsonl"
_REACTIONS_LOG = _STATE / "chat_reactions.jsonl"

@dataclass
class ChatTurn:
    id: str  # hash of content/timestamp
    ts: float
    speaker: str  # "user" | "alice" | "system" | "arm:<arm_id>"
    text: str
    modality: str  # "TYPED" | "SPOKEN" | "SYSTEM"
    receipt_refs: List[str]
    model: Optional[str] = None
    surface: Optional[str] = None
    reaction: Optional[str] = None  # "like" | "dislike" etc.

def get_turn_id(payload: Dict[str, Any]) -> str:
    row_hash = str(payload.get("_row_hash") or payload.get("hash") or payload.get("sha256") or "").strip()
    if row_hash:
        return row_hash
    raw = json.dumps(
        {
            "ts": payload.get("ts"),
            "role": payload.get("role"),
            "text": payload.get("text"),
            "model": payload.get("model"),
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()

def load_reactions() -> Dict[str, str]:
    reactions = {}
    if _REACTIONS_LOG.exists():
        try:
            with open(_REACTIONS_LOG, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                        turn_ref = row.get("turn_ref")
                        reaction = row.get("reaction")
                        if turn_ref and reaction:
                            reactions[turn_ref] = reaction
                    except Exception:
                        continue
        except Exception:
            pass
    return reactions

def add_reaction(turn_id: str, reaction: str, actor: str = "owner") -> str:
    ts = time.time()
    receipt_id = f"react-{os.urandom(6).hex()}"
    row = {
        "ts": ts,
        "turn_ref": turn_id,
        "reaction": reaction,
        "actor": actor,
        "receipt_id": receipt_id,
        "truth_label": "OBSERVED"
    }
    _STATE.mkdir(parents=True, exist_ok=True)
    with open(_REACTIONS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    
    # Also write to work_receipts.jsonl for stigmergic trace compliance
    work_receipt = {
        "ts": ts,
        "trace_id": receipt_id,
        "doctor": "Antigravity",
        "model": "Gemini 3.5 Flash (GEM35F)",
        "action": f"chat_reaction_{reaction}",
        "intent": f"Record owner {reaction} reaction to turn {turn_id[:8]}",
        "status": "SUCCESS",
        "node_serial": "GTH4921YP3"
    }
    with open(_STATE / "work_receipts.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(work_receipt) + "\n")

    return receipt_id

def load_recent_turns(n: int = 200) -> List[ChatTurn]:
    turns = []
    if not _CONVO_LOG.exists():
        return turns

    reactions = load_reactions()
    seen_ids = set()

    try:
        with open(_CONVO_LOG, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return turns

    # Process lines backwards to get the most recent ones first, but keep chronological order
    recent_lines = lines[-max(1, n * 2):]
    
    for line in recent_lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
        if not isinstance(payload, dict):
            continue
            
        role = str(payload.get("role") or "").strip().lower()
        text = str(payload.get("text") or "").strip()
        if not role or not text:
            continue
            
        if role not in {"user", "alice", "assistant", "reflex", "system"}:
            continue
            
        turn_id = get_turn_id(payload)
        if turn_id in seen_ids:
            continue
        seen_ids.add(turn_id)
        
        ts = float(payload.get("ts") or time.time())
        model = payload.get("model")
        
        # Determine speaker
        if role == "user":
            speaker = "user"
            modality = "TYPED" if text.endswith(")") and "(" in text else "SPOKEN"
            if "typed_turn" in payload or "typed" in str(payload.get("input_modality", "")).lower():
                modality = "TYPED"
        elif role in {"alice", "assistant"}:
            speaker = "alice"
            modality = "SPOKEN"
        else:
            speaker = "system"
            modality = "SYSTEM"
            
        # Modality check
        modality_raw = payload.get("input_modality") or payload.get("modality")
        if modality_raw:
            modality = str(modality_raw).upper()

        meta = payload.get("routing_metadata") or {}
        surface = meta.get("surface") or meta.get("territory") or ""
        
        # Check for receipt refs in text
        receipt_refs = []
        # Find receipt UUIDs or rXX-XXXX patterns
        for word in text.split():
            clean_word = word.strip("()[]{},.:;\"'")
            if (clean_word.startswith("r") and "-" in clean_word and len(clean_word) >= 5) or len(clean_word) == 36:
                receipt_refs.append(clean_word)
                
        turn = ChatTurn(
            id=turn_id,
            ts=ts,
            speaker=speaker,
            text=text,
            modality=modality,
            receipt_refs=receipt_refs,
            model=model,
            surface=surface if surface else None,
            reaction=reactions.get(turn_id)
        )
        turns.append(turn)
        
    return turns[-n:]
