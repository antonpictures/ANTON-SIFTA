#!/usr/bin/env python3
"""
Legacy entrypoint name - delegates to `swarm_replay_job.run_replay_digest`.

The old Ollama "dream JSON" path is retired here: selective replay is
**deterministic** + locked ledger I/O (MAWF / WISH_002). Optional LLM merge can
land later behind an explicit env flag + Architect GO.
"""
from __future__ import annotations

import os

from System.swarm_replay_job import run_replay_digest


def run_rem_replay() -> None:
    print("[*] REM Replay Job (WISH_002) - deterministic digest ...")
    os.environ.setdefault("SIFTA_REM_REPLAY_DEPOSIT", "1")
    out = run_replay_digest(deposit_trace=True)
    print(f"[+] replay_id={out['replay_id']} episodes={out['episodes_count']}")


if __name__ == "__main__":
    run_rem_replay()
