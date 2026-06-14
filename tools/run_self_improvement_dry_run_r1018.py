#!/usr/bin/env python3
"""Run r1018 self-improvement dry run against repo .sifta_state."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_self_improvement_loop import (  # noqa: E402
    format_improve_reply,
    format_quorum_reply,
    run_r1018_dry_run,
)


def main() -> int:
    state_dir = _REPO / ".sifta_state"
    result = run_r1018_dry_run(state_dir=state_dir)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))

    keep = result.get("first_keep", {})
    revert = result.get("first_revert", {})
    stall = result.get("cosign_stall", {})
    incident = result.get("incident_closed", {})

    ok = (
        incident.get("gate", {}).get("ok") is False
        and incident.get("ledger_row", {}).get("verdict") == "REFUSED"
        and keep.get("status") == "KEPT"
        and revert.get("status") == "REVERTED"
        and revert.get("byte_identical") is True
        and stall.get("stalled") is True
    )
    print("\n--- /improve ---")
    print(format_improve_reply(state_dir=state_dir))
    pid = str(keep.get("proposal", {}).get("proposal_id", ""))[:8]
    if pid:
        print("\n--- /quorum ---")
        print(format_quorum_reply(pid, state_dir=state_dir))
    print(f"\nACCEPTANCE_OK={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())