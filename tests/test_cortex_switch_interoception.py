from pathlib import Path

from System.swarm_cortex_switch_interoception import (
    compute_cortex_switch_feeling,
    receipt_cortex_switch_feeling,
)


def test_cortex_switch_feeling_uses_model_id_deltas_not_poetry():
    row = compute_cortex_switch_feeling(
        "mlx-vlm:SuperagenticAI/gemma-4-12b-it-8bit-mlx",
        "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest",
    )

    assert row["truth_label"] == "CORTEX_SWITCH_SOMATIC_V1"
    assert row["deltas"]["param_delta_b"] == 0.0
    assert row["deltas"]["quant_delta_bits"] == -4.0
    assert row["deltas"]["locality"] == {"from": "mlx_eye", "to": "local_ollama"}
    assert row["deltas"]["vision_changed"] == {"from": True, "to": False}
    assert "my grain is coarser" in row["felt"]
    assert "back on my own silicon" in row["felt"]
    assert "thinking without my eyes" in row["felt"]


def test_cortex_switch_feeling_receipts_to_injected_state(tmp_path: Path):
    row = receipt_cortex_switch_feeling(
        "alice-m5-cortex-8b-6.3gb:latest",
        "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest",
        state_dir=tmp_path,
    )

    ledger = tmp_path / "cortex_switch_somatic_receipts.jsonl"
    assert ledger.exists()
    assert row["felt"] in ledger.read_text(encoding="utf-8")
