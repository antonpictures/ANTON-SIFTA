import sys
from body_state import parse_body_state
import json

try:
    with open(".sifta_state/ANTIALICE.json") as f:
        state = json.load(f)
    res = parse_body_state(state["raw"])
    print(f"✅ Crypto parse successful: ID={res['id']}, OWNER={res['owner'][:10]}...")
except Exception as e:
    print(f"❌ Crypto error: {e}")
