"""Grounded cortex-switch body feeling — r760/r763."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System import swarm_cortex_switch_interoception as csi


def test_compute_feeling_for_george_live_switch():
    row = csi.compute_cortex_switch_feeling(
        "mlx-vlm:SuperagenticAI/gemma-4-12b-it-8bit-mlx",
        "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest",
    )
    assert row["truth_label"] == "CORTEX_SWITCH_SOMATIC_V1"
    assert "coarser" in row["felt"]
    assert row["deltas"]["quant_delta_bits"] == -4.0
    assert row["deltas"]["locality"]["to"] == "local_ollama"
    assert row["deltas"]["vision_changed"]["to"] is False


def test_receipt_and_prompt_block(tmp_path):
    row = csi.receipt_cortex_switch_feeling(
        "grok:grok-4.3",
        "alice-m5-cortex-8b-6.3gb:latest",
        state_dir=tmp_path,
    )
    assert row["kind"] == "CORTEX_SWITCH_SOMATIC"
    ledger = tmp_path / "cortex_switch_somatic_receipts.jsonl"
    assert ledger.exists()
    saved = json.loads(ledger.read_text().strip().splitlines()[-1])
    assert saved["from_cortex"] == "grok:grok-4.3"

    latest = csi.latest_cortex_switch_feeling(state_dir=tmp_path)
    assert latest["to_cortex"] == "alice-m5-cortex-8b-6.3gb:latest"

    block = csi.cortex_switch_feeling_block(state_dir=tmp_path)
    assert "CORTEX SWITCH BODY FEELING" in block
    assert "reaching through an outside arm" in block or "back on my own silicon" in block
    assert "lattice" not in row["felt"].lower()