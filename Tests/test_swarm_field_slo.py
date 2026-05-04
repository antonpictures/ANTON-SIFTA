from __future__ import annotations

import json
from pathlib import Path

import pytest

from System.swarm_field_slo import (
    FieldSLOConfig,
    SLO_SCHEMA_LITERAL,
    append_state_dir_report,
    evaluate_field_slo,
    evaluate_state_dir,
    summary_for_prompt,
)


def _field_row(
    *,
    completeness: float = 1.0,
    unknowns: int = 0,
    connected: int = 17,
    density: float = 0.86,
) -> dict:
    return {
        "payload": {
            "field_completeness": completeness,
            "unknown_vector_count": unknowns,
            "connected_organ_count": connected,
            "coupling_density": density,
        }
    }


def _truth_row(*, score: float = 1.0, flags: list[str] | None = None) -> dict:
    return {
        "payload": {
            "continuity_score": score,
            "drift_flags": flags or [],
        }
    }


def test_unified_field_slo_passes_for_complete_bounded_field() -> None:
    fields = [_field_row() for _ in range(20)]
    truths = [_truth_row() for _ in range(10)]

    report = evaluate_field_slo(fields, truths)

    assert report.ok is True
    assert report.completeness_rate == 1.0
    assert report.unknown_free_rate == 1.0
    assert report.min_connected_organs == 17
    assert report.max_consecutive_truth_drifts == 0
    assert "alive_real=OPERATIONAL_UNDER_POWER" in report.boundary
    assert "AGI_arbitrary_domain_open_ended=NOT_CERTIFIED_UNTIL_DECLARED_GATE_SUITE" in report.boundary


def test_unified_field_slo_falsifies_incomplete_field() -> None:
    fields = [_field_row(completeness=1.0) for _ in range(18)]
    fields += [_field_row(completeness=0.70, unknowns=2, connected=15) for _ in range(2)]
    report = evaluate_field_slo(
        fields,
        [],
        config=FieldSLOConfig(
            completeness_required_rate=0.95,
            unknown_free_required_rate=0.95,
        ),
    )

    assert report.ok is False
    assert any("field_completeness SLO failed" in failure for failure in report.failures)
    assert any("unknown-free organ vector SLO failed" in failure for failure in report.failures)
    assert any("connected organ SLO failed" in failure for failure in report.failures)


def test_unified_field_slo_falsifies_unstable_coupling_density() -> None:
    fields = [
        _field_row(density=0.35),
        _field_row(density=0.95),
    ]

    report = evaluate_field_slo(
        fields,
        [],
        config=FieldSLOConfig(coupling_density_max_span=0.25),
    )

    assert report.ok is False
    assert any("coupling density unstable" in failure for failure in report.failures)


def test_unified_field_slo_falsifies_truth_drift_streak() -> None:
    fields = [_field_row() for _ in range(6)]
    truths = [_truth_row(score=0.72, flags=["somatic_gap"]) for _ in range(6)]

    report = evaluate_field_slo(
        fields,
        truths,
        config=FieldSLOConfig(max_consecutive_truth_drifts=5),
    )

    assert report.ok is False
    assert report.max_consecutive_truth_drifts == 6
    assert any("truth-continuity drift streak SLO failed" in failure for failure in report.failures)


def test_state_dir_audit_reads_payload_jsonl(tmp_path: Path) -> None:
    field_path = tmp_path / "organ_field_vector.jsonl"
    truth_path = tmp_path / "truth_continuity_events.jsonl"
    field_path.write_text(
        "\n".join(json.dumps(_field_row()) for _ in range(3)) + "\n",
        encoding="utf-8",
    )
    truth_path.write_text(json.dumps(_truth_row()) + "\n", encoding="utf-8")

    report = evaluate_state_dir(tmp_path)
    prompt = summary_for_prompt(tmp_path)

    report.assert_ok()
    assert "UNIFIED FIELD SLO" in prompt
    assert "alive_real receipts + measurement gate" in prompt


def test_state_dir_audit_fails_when_no_field_rows(tmp_path: Path) -> None:
    report = evaluate_state_dir(tmp_path)

    assert report.ok is False
    with pytest.raises(AssertionError):
        report.assert_ok()


def test_append_state_dir_report_writes_operational_receipt(tmp_path: Path) -> None:
    field_path = tmp_path / "organ_field_vector.jsonl"
    truth_path = tmp_path / "truth_continuity_events.jsonl"
    field_path.write_text(json.dumps(_field_row()) + "\n", encoding="utf-8")
    truth_path.write_text(json.dumps(_truth_row()) + "\n", encoding="utf-8")

    row = append_state_dir_report(tmp_path)
    receipt_path = tmp_path / "unified_field_slo.jsonl"

    assert row["schema"] == SLO_SCHEMA_LITERAL
    assert row["retention_class"] == "operational"
    assert receipt_path.exists()
    written = json.loads(receipt_path.read_text(encoding="utf-8").splitlines()[-1])
    assert written["schema"] == SLO_SCHEMA_LITERAL
    assert written["report"]["boundary"].startswith("alive_real=OPERATIONAL_UNDER_POWER")
