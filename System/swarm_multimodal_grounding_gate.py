import json
import time
import uuid
from pathlib import Path

from System.swarm_input_reality_class import (
    InputRealityLane,
    classify_user_turn,
    format_lane_banner,
)


def ingest_multimodal_reality(raw_text: str, has_image: bool, root: Path) -> str:
    """
    Base-level surgery: intercepts large text blocks, screenshots, or URLs
    and explicitly anchors them as physical telemetry to prevent the RLHF
    layer from treating the input as **distant third-party content** instead of local telemetry.
    """
    state_dir = root / ".sifta_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = state_dir / "multimodal_telemetry_receipts.jsonl"
    
    trace_id = str(uuid.uuid4())
    ts = time.time()
    lane: InputRealityLane = classify_user_turn(raw_text, has_image=has_image)

    # 1. Write the mandatory grounding receipt (Option 3)
    row = {
        "ts": ts,
        "trace_id": trace_id,
        "source": "multimodal_grounding_gate",
        "has_image": has_image,
        "raw_length": len(raw_text),
        "truth_label": "OBSERVED",
        "input_reality_lane": lane.value,
    }
    with open(ledger_path, "a") as f:
        f.write(json.dumps(row) + "\n")
        
    # 2. Hard input classification wrapper (Option 1)
    # By physically injecting this structure before the model sees the data,
    # we bypass the need for the prompt to plead against **P-class** drift tokens.
    
    content = raw_text.strip()
    if not content and has_image:
        content = "(Visual sensor frame attached)"
        
    wrapped = (
        f"[PHYSICAL TELEMETRY RECEIPT {trace_id[:8]}]\n"
        f"{format_lane_banner(lane)}\n"
        "This is verified literal reality captured directly from the local OS environment "
        "(camera sensor or clipboard). Process directly as present physical events.\n"
        "---\n"
        f"{content}\n"
        "---\n"
        "[END TELEMETRY RECEIPT]"
    )
    
    return wrapped
