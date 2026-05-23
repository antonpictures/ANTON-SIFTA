"""Cerebellum timing — Event 77 Smith predictor, Bishop mandates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System.swarm_cerebellum_timing import (
    CerebellumTiming,
    SwarmCerebellumTiming,
    proof_of_property,
)


def test_swarm_alias_is_cerebellum_timing() -> None:
    assert SwarmCerebellumTiming is CerebellumTiming


def test_latency_prediction_updates_after_observed_action(tmp_path: Path) -> None:
    c = CerebellumTiming(state_dir=tmp_path, persist_receipts=False)
    assert c.predict("send_whatsapp") == pytest.approx(1.0)
    c.update("send_whatsapp", observed_latency=2.0, ok=True, write_receipt=False)
    assert c.predict("send_whatsapp") > 1.0


def test_repeated_failures_inflate_forward_model(tmp_path: Path) -> None:
    c = CerebellumTiming(state_dir=tmp_path, persist_receipts=False)
    t0 = 500_000.0
    assert c.should_delay("risky_tool", urgency=0.1, now=t0) == 0.0
    c.update("risky_tool", 1.0, ok=False, write_receipt=False, now=t0 + 1.0)
    c.update("risky_tool", 1.0, ok=False, write_receipt=False, now=t0 + 2.0)
    assert c.failure_streak["risky_tool"] >= 2
    assert c.predict("risky_tool") > 1.0


def test_urgency_bypasses_delay_in_shadow(tmp_path: Path) -> None:
    c = CerebellumTiming(state_dir=tmp_path, persist_receipts=False)
    t0 = 600_000.0
    assert c.should_delay("x", urgency=0.1, now=t0) == 0.0
    c.update("x", 3.0, ok=True, write_receipt=False, now=t0 + 0.01)
    assert c.should_delay("x", urgency=0.95, now=t0 + 0.5) == 0.0


def test_smith_shadow_rate_limits_re_fire(tmp_path: Path) -> None:
    c = CerebellumTiming(state_dir=tmp_path, persist_receipts=False)
    t0 = 700_000.0
    assert c.should_delay("send_whatsapp", urgency=0.1, now=t0) == 0.0
    c.update("send_whatsapp", 3.0, ok=True, write_receipt=False, now=t0)
    burst = c.should_delay("send_whatsapp", urgency=0.1, now=t0 + 0.02)
    assert burst > 0.0
    relaxed = c.should_delay("send_whatsapp", urgency=0.1, now=t0 + 30.0)
    assert relaxed == 0.0


def test_receipt_written_for_correction(tmp_path: Path) -> None:
    c = CerebellumTiming(state_dir=tmp_path, persist_receipts=True)
    c.update("ping", 0.5, ok=True, write_receipt=True, now=123.0)
    text = (tmp_path / "cerebellum_timing.jsonl").read_text(encoding="utf-8")
    row = json.loads(text.strip().splitlines()[-1])
    assert row["kind"] == "cerebellum_timing_correction"
    assert row.get("event") == "BISHOP_EVENT_77"
    assert row["action"] == "ping"
    assert "timing_error" in row
    assert row["next_expected_latency"] == pytest.approx(
        1.0 + 0.2 * (0.5 - 1.0), rel=1e-5
    )


def test_bishop_proof_of_property() -> None:
    assert proof_of_property() is True
