"""Cerebellum timing — latency learning, caution, urgency, receipts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System.swarm_cerebellum_timing import CerebellumTiming


def test_latency_prediction_updates_after_observed_action(tmp_path: Path) -> None:
    c = CerebellumTiming(state_dir=tmp_path, persist_receipts=False)
    assert c.predict("send_whatsapp") == pytest.approx(1.0)
    c.update("send_whatsapp", observed_latency=2.0, ok=True, write_receipt=False)
    assert c.predict("send_whatsapp") > 1.0


def test_repeated_failures_increase_caution(tmp_path: Path) -> None:
    c = CerebellumTiming(state_dir=tmp_path, persist_receipts=False)
    d0 = c.should_delay("risky_tool", urgency=0.2, now=1000.0)
    c.update("risky_tool", 1.0, ok=False, write_receipt=False, now=1001.0)
    c.update("risky_tool", 1.0, ok=False, write_receipt=False, now=1002.0)
    d1 = c.should_delay("risky_tool", urgency=0.2, now=1002.5)
    assert d1 >= d0
    assert c.failure_streak["risky_tool"] >= 2


def test_urgency_bypasses_delay(tmp_path: Path) -> None:
    c = CerebellumTiming(state_dir=tmp_path, persist_receipts=False)
    c.update("x", 3.0, ok=True, write_receipt=False)
    assert c.should_delay("x", urgency=0.95) == 0.0


def test_repeated_sends_smoothed_rate_limited(tmp_path: Path) -> None:
    c = CerebellumTiming(state_dir=tmp_path, persist_receipts=False)
    t0 = 10_000.0
    c.update("send_whatsapp", 1.0, ok=True, write_receipt=False, now=t0)
    burst = c.should_delay("send_whatsapp", urgency=0.1, now=t0 + 0.02)
    relaxed = c.should_delay("send_whatsapp", urgency=0.1, now=t0 + 30.0)
    assert burst > 0.0
    assert relaxed <= burst


def test_receipt_written_for_correction(tmp_path: Path) -> None:
    c = CerebellumTiming(state_dir=tmp_path, persist_receipts=True)
    c.update("ping", 0.5, ok=True, write_receipt=True, now=123.0)
    text = (tmp_path / "cerebellum_timing.jsonl").read_text(encoding="utf-8")
    row = json.loads(text.strip().splitlines()[-1])
    assert row["kind"] == "cerebellum_timing_correction"
    assert row["action"] == "ping"
    assert "timing_error" in row
    assert row["next_expected_latency"] == pytest.approx(
        1.0 + 0.2 * (0.5 - 1.0), rel=1e-5
    )
