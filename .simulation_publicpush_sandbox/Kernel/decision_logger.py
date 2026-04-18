# decision_logger.py
"""
DECISION LOGGER — Observable Intelligence Module
Grants the Swarm memory of its own judgments. 

Ensures that SIFTA is fully auditable, meaning it can prove 
to investors or users exactly WHY it blocked or allowed a mutation.
"""

import json
import time
from pathlib import Path

# Store in a hidden state directory to keep the root clean
LOG_DIR = Path(".sifta_state")
LOG_FILE = LOG_DIR / "decision_trace.log"

def log_decision(payload: dict):
    """
    Appends a local JSON decision payload to the trace log.
    Ensures SIFTA is self-aware of its history.
    """
    LOG_DIR.mkdir(exist_ok=True)

    entry = {
        "timestamp": time.time(),
        **payload
    }

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
