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
    ts: float | None = None,
) -> dict:
    payload = {
        "field_completeness": completeness,
        "unknown_vector_count": unknowns,
        "connected_organ_count": connected,
        "coupling_density": density,
    }
    if ts is not None:
        payload["ts"] = ts
    return {
        "payload": {
            **payload,
        }
    }


def _truth_row(*, score: float = 1.0, flags: list[str] | None = None, ts: float | None = None) -> dict:
    payload = {
        "continuity_score": score,
        "drift_flags": flags or [],
    }
    if ts is not None:
        payload["ts"] = ts
    return {
        "payload": {
            **payload,
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
    field_path.write_text(json.dumps(_field_row(ts=100.0)) + "\n", encoding="utf-8")
    truth_path.write_text(json.dumps(_truth_row(ts=100.0)) + "\n", encoding="utf-8")

    row = append_state_dir_report(tmp_path)
    receipt_path = tmp_path / "unified_field_slo.jsonl"

    assert row["schema"] == SLO_SCHEMA_LITERAL
    assert row["retention_class"] == "operational"
    assert receipt_path.exists()
    written = json.loads(receipt_path.read_text(encoding="utf-8").splitlines()[-1])
    assert written["schema"] == SLO_SCHEMA_LITERAL
    assert "freshness" in written
    assert written["freshness"]["latest_field_ts"] is not None
    assert written["report"]["boundary"].startswith("alive_real=OPERATIONAL_UNDER_POWER")


def test_summary_for_prompt_marks_stale_field_rows(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("System.swarm_field_slo.time.time", lambda: 10_000.0)
    field_path = tmp_path / "organ_field_vector.jsonl"
    truth_path = tmp_path / "truth_continuity_events.jsonl"
    field_path.write_text(json.dumps(_field_row(ts=1_000.0)) + "\n", encoding="utf-8")
    truth_path.write_text(json.dumps(_truth_row(ts=9_980.0)) + "\n", encoding="utf-8")

    prompt = summary_for_prompt(tmp_path)

    assert "field_latest_age=2.5h" in prompt
    assert "truth_latest_age=20s" in prompt
    assert "field_freshness=STALE_DO_NOT_CALL_LIVE" in prompt
    assert "last field snapshot, not this-turn live health" in prompt


def test_summary_for_prompt_wraps_day_old_values_as_last_snapshot(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("System.swarm_field_slo.time.time", lambda: 400_000.0)
    field_path = tmp_path / "organ_field_vector.jsonl"
    truth_path = tmp_path / "truth_continuity_events.jsonl"
    old_ts = 400_000.0 - 105 * 3600
    field_rows = [_field_row(completeness=1.0, ts=old_ts) for _ in range(467)]
    field_rows.extend(_field_row(completeness=0.0, ts=old_ts) for _ in range(533))
    field_path.write_text("\n".join(json.dumps(row) for row in field_rows) + "\n", encoding="utf-8")
    truth_path.write_text(json.dumps(_truth_row(ts=399_990.0)) + "\n", encoding="utf-8")

    prompt = summary_for_prompt(tmp_path)

    assert "completeness_rate=<last snapshot 105 hours ago, was 0.467>" in prompt
    assert "min_connected_organs=<last snapshot 105 hours ago" in prompt
