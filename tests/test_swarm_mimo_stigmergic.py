from __future__ import annotations

import json
from pathlib import Path

from System.swarm_mimo_stigmergic import (
    PHEROMONE_LEDGER,
    TRACE_LEDGER,
    build_stigmergic_prompt,
    mimo_stigmergic_summary,
)


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def test_r1130_named_mimo_stigmergic_contract_file_exists(tmp_path):
    state = tmp_path / ".sifta_state"
    _append(
        state / TRACE_LEDGER,
        {
            "ts": 1.0,
            "intent": "field-aware MiMo repair",
            "ok": True,
            "driving_organ": "spinal_cord",
        },
    )
    _append(
        state / PHEROMONE_LEDGER,
        {
            "ts": 1.1,
            "call_id": "abc",
            "organ": "mimo_stigmergic",
            "intent": "field-aware MiMo repair",
            "ok": True,
        },
    )

    prompt = build_stigmergic_prompt("continue the repair", state_dir=state)
    summary = mimo_stigmergic_summary(state_dir=state)

    assert "FIELD STATE" in prompt
    assert "field-aware MiMo repair" in prompt
    assert summary["total_calls"] == 1
    assert summary["ok"] == 1
    assert summary["pheromones"] == 1
