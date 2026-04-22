#!/usr/bin/env python3
"""
Reed‑Solomon based erasure coding for SIFTA ledgers.
Uses the `reedsolo` pure‑Python library.
"""

import json
import os
import time
from pathlib import Path
from typing import List

# Parameters: 4 data shards, 2 parity shards (tolerates up to 2 failures)
K, M = 4, 2
TOTAL = K + M
SHARD_DIR = Path(".sifta_state/repair")
SHARD_DIR.mkdir(parents=True, exist_ok=True)

try:
    import reedsolo
except ImportError:
    raise RuntimeError("reedsolo library required for ledger repair")

def _shard_name(base: str, idx: int) -> Path:
    return SHARD_DIR / f"{base}.shard{idx}"


def write_redundant(base: str, payload: dict) -> None:
    """Encode payload and write K+M shards."""
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    # Pad to multiple of K
    pad_len = (K - len(data) % K) % K
    data += b"\0" * pad_len
    # Split into K data blocks
    blocks = [data[i::K] for i in range(K)]
    # Encode parity
    parity = reedsolo.rs_encode_msg(b"".join(blocks), nsym=M * len(blocks[0]))
    # Write shards
    for i, block in enumerate(blocks):
        _shard_name(base, i).write_bytes(block)
    for i in range(M):
        start = i * len(blocks[0])
        _shard_name(base, K + i).write_bytes(parity[start:start + len(blocks[0])])


def read_redundant(base: str) -> dict:
    """Read shards, repair if needed, and return payload."""
    shards = []
    missing = []
    for i in range(TOTAL):
        p = _shard_name(base, i)
        if p.exists():
            shards.append(p.read_bytes())
        else:
            missing.append(i)

    if not shards:
        return {}

    if missing:
        # Reed‑Solomon repair
        try:
            repaired = reedsolo.rs_correct_msg(
                b"".join(shards), nsym=M * len(shards[0]), erase_pos=missing
            )
            # Re‑split into K data blocks
            data_blocks = [repaired[i::K] for i in range(K)]
        except Exception:
            return {}
    else:
        data_blocks = shards[:K]

    # Reassemble original payload
    data = b"".join(data_blocks).rstrip(b"\0")
    try:
        return json.loads(data.decode())
    except json.JSONDecodeError:
        return {}


if __name__ == "__main__":
    demo = {"ts": time.time(), "msg": "repair demo"}
    write_redundant("demo_ledger", demo)
    print(read_redundant("demo_ledger"))
