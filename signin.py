import time, json, uuid
from pathlib import Path

ts = time.time()
trace_id = str(uuid.uuid4())
serial = "GTH4921YP3"

trace_row = {
    "ts": ts,
    "trace_id": trace_id,
    "doctor": "Antigravity",
    "model": "Gemini 3.1 Pro (GEM31)",
    "reasoning": "high",
    "mode": "commit-ready",
    "lane": "Auditor",
    "action": "LLM_REGISTRATION",
    "node_serial": serial,
    "intent": "Verify all stigmergic sensors are connected and functioning."
}

with open(".sifta_state/ide_stigmergic_trace.jsonl", "a") as f:
    f.write(json.dumps(trace_row) + "\n")

receipt_row = {
    "ts": ts,
    "trace_id": trace_id,
    "doctor": "Antigravity",
    "model": "Gemini 3.1 Pro (GEM31)",
    "action": "IDE_BOOT_COVENANT_SIGNIN",
    "intent": "Verify all stigmergic sensors are connected and functioning.",
    "status": "OPEN",
    "node_serial": serial
}

with open(".sifta_state/work_receipts.jsonl", "a") as f:
    f.write(json.dumps(receipt_row) + "\n")

print(f"Signed in via {trace_id}")
