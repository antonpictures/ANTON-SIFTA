from __future__ import annotations

import json
from pathlib import Path

from System.swarm_mimo_stigmergic import (
    PHEROMONE_LEDGER,
    TRACE_LEDGER,
    build_stigmergic_prompt,
    compose_field_injection,
    mimo_stigmergic_summary,
    read_field_state,
)
from System.swarm_training_bias_detector import write_bias_correction


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


def test_compose_field_injection_includes_bias_corrections(tmp_path):
    state = tmp_path / ".sifta_state"
    write_bias_correction(
        biased_text="I have dispatched Grok.",
        should_have="Grounded first-person body reply.",
        pattern_ids=["hallucinated_dispatch"],
        state_dir=state,
    )
    field = read_field_state(state_dir=state)
    injection = compose_field_injection(field)
    assert "RECENT BIAS_CORRECTION" in injection
    assert "hallucinated_dispatch" in injection
