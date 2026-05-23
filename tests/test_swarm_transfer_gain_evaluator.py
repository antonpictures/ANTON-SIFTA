import json
import os

from System.swarm_transfer_gain_evaluator import (
    TransferGainEvaluator,
    evaluation_log_path,
)


def test_evaluate_transfer_gain_logs_and_meaningful(tmp_path, monkeypatch):
    monkeypatch.delenv("SIFTA_TRANSFER_GAIN_EVAL_DISABLE", raising=False)
    ev = TransferGainEvaluator.evaluate_transfer_gain(
        0.42,
        0.68,
        "co_watch_novel_query",
        root=tmp_path,
    )
    assert ev["kind"] == "TRANSFER_GAIN_EVALUATION"
    assert ev["absolute_gain"] == round(0.68 - 0.42, 4)
    assert ev["meaningful_transfer"] is True
    log = evaluation_log_path(tmp_path)
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["task_name"] == "co_watch_novel_query"


def test_zero_baseline_meaningful_via_absolute(monkeypatch, tmp_path):
    monkeypatch.delenv("SIFTA_TRANSFER_GAIN_EVAL_DISABLE", raising=False)
    monkeypatch.setenv("SIFTA_TRANSFER_GAIN_MEANINGFUL_ABS", "0.03")
    ev = TransferGainEvaluator.evaluate_transfer_gain(
        0.0,
        0.1,
        "cold_start_task",
        root=tmp_path,
    )
    assert ev["relative_gain"] == 0.0
    assert ev["meaningful_transfer"] is True


def test_get_overall_transfer_health(tmp_path, monkeypatch):
    monkeypatch.delenv("SIFTA_TRANSFER_GAIN_EVAL_DISABLE", raising=False)
    TransferGainEvaluator.evaluate_transfer_gain(0.5, 0.9, "t1", root=tmp_path)
    TransferGainEvaluator.evaluate_transfer_gain(0.5, 0.52, "t2", root=tmp_path)
    h = TransferGainEvaluator.get_overall_transfer_health(root=tmp_path)
    assert h["tasks_evaluated"] == 2
    assert h["successful_transfers"] >= 1
    assert h["transfer_health"] > 0


def test_disable_skips_write(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_TRANSFER_GAIN_EVAL_DISABLE", "1")
    ev = TransferGainEvaluator.evaluate_transfer_gain(1.0, 2.0, "x", root=tmp_path)
    assert ev.get("skipped") is True
    assert not evaluation_log_path(tmp_path).exists()
