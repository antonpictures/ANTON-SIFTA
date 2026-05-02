"""Event 106 — nightly stigmergic health audit."""

import json
from pathlib import Path


def test_run_nightly_audit_writes_ledger(tmp_path, monkeypatch):
    import System.swarm_nightly_health_audit as nha

    monkeypatch.setattr(nha, "HEALTH_LOG", tmp_path / "nightly_health.jsonl")
    monkeypatch.setattr(nha, "HEALTH_SUMMARY", tmp_path / "nightly_health_summary.json")
    monkeypatch.setattr(nha, "_STATE", tmp_path)

    receipt = nha.run_nightly_audit(run_arxiv=False, run_claims=False, fast_tests=True)
    assert receipt["truth_label"] == nha.TRUTH_LABEL
    assert "sections" in receipt
    assert "composite_score" in receipt
    assert receipt["sections"]["arxiv_sweep"]["status"] == "SKIPPED"
    log = tmp_path / "nightly_health.jsonl"
    assert log.exists()
    row = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["truth_label"] == nha.TRUTH_LABEL
    summ = tmp_path / "nightly_health_summary.json"
    assert summ.exists()
    assert json.loads(summ.read_text(encoding="utf-8"))["composite_score"] == receipt["composite_score"]


def test_tail_ide_trace_rows_flattens_registration_rows(tmp_path, monkeypatch):
    import System.swarm_nightly_health_audit as nha

    monkeypatch.setattr(nha, "_STATE", tmp_path)
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    trace.write_text(
        "\n".join(
            [
                "",
                "not json",
                json.dumps(
                    {
                        "trace_id": "trace-1",
                        "ts": 1777695000.0,
                        "source_ide": "codex",
                        "meta": {
                            "node_serial": "SERIAL-1",
                            "regime": "EXPLORATION",
                            "causal_parent_ids": ["p1", "p2"],
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    rows = nha._tail_ide_trace_rows()

    assert len(rows) == 1
    assert rows[0]["trace_id"] == "trace-1"
    assert rows[0]["homeworld_serial"] == "SERIAL-1"
    assert rows[0]["regime"] == "EXPLORATION"
    assert rows[0]["causal_parent_ids"] == ["p1", "p2"]


def test_motor_policy_health_reads_regime_and_crystallizer_gate(tmp_path, monkeypatch):
    import System.swarm_nightly_health_audit as nha

    monkeypatch.setattr(nha, "_STATE", tmp_path)
    (tmp_path / "motor_policy.jsonl").write_text(
        json.dumps({"selected_action": "repair", "regime": "CRITICAL_COLLAPSE"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "regime_state.json").write_text(
        json.dumps({"state": "CONSOLIDATION"}),
        encoding="utf-8",
    )
    (tmp_path / "body_brain_memory.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"crystallizer_weight": 0.4}),
                json.dumps({"crystallizer_weight": 0.1}),
            ]
        ),
        encoding="utf-8",
    )

    result = nha._run_motor_policy_health()

    assert result["status"] == "OK"
    assert result["last_selected"] == "repair"
    assert result["last_regime"] == "CONSOLIDATION"
    assert result["last_motor_row_regime"] == "CRITICAL_COLLAPSE"
    assert result["crystallizer_gate"] == 0.1
