"""Tests for `System/swarm_alice_doctor_cost_summary.py`.

Doctrinal property under test: the reader must NEVER sum or normalize
across vendor units. C55M's Clause-4 boundary is the load-bearing rule.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from System.swarm_alice_doctor_cost_summary import (
    SURFACE_DISPLAY_ORDER,
    DoctorCostReport,
    SurfaceSummary,
    build_report,
    render_summary,
)
from System.swarm_ide_cost_ledger import IDECostSample, append_sample


def _seed(ledger: Path, samples):
    for s in samples:
        append_sample(s, ledger_path=ledger)


def test_empty_ledger_renders_helpful_placeholder(tmp_path: Path):
    out = render_summary(ledger_path=tmp_path / "ide_cost_ledger.jsonl")
    assert "ledger empty" in out
    assert "STIGAUTH" in out


def test_single_row_renders_one_bullet(tmp_path: Path):
    led = tmp_path / "ide_cost_ledger.jsonl"
    _seed(led, [
        IDECostSample(
            surface="cursor",
            agent_id="C47H",
            model_label="claude-opus-4-7-thinking-high",
            plan_name="Ultra $200/mo",
            source_unit="percent_quota",
            observed_quantity=31.0,
            included_usage_remaining=69.0,
            on_demand_limit_usd=200.0,
            evidence_kind="dashboard_screenshot",
            evidence_ref="screenshot:test",
            stigauth_status="STIGAUTH_ACTIVE",
        )
    ])
    out = render_summary(ledger_path=led)
    assert "C47H@cursor" in out
    assert "claude-opus-4-7-thinking-high" in out
    assert "31 percent_quota" in out
    assert "(69 percent_quota left)" in out
    assert "[dashboard_screenshot]" in out


def test_native_units_are_NOT_summed_across_surfaces(tmp_path: Path):
    """The load-bearing C55M boundary: heterogeneous units stay heterogeneous."""
    led = tmp_path / "ide_cost_ledger.jsonl"
    _seed(led, [
        IDECostSample(
            surface="cursor",
            agent_id="C47H",
            model_label="claude-opus-4-7-thinking-high",
            plan_name="Ultra",
            source_unit="tokens",
            observed_quantity=70_000_000.0,
            evidence_kind="dashboard_screenshot",
            evidence_ref="r1",
            stigauth_status="STIGAUTH_ACTIVE",
        ),
        IDECostSample(
            surface="codex",
            agent_id="C55M",
            model_label="gpt-5.4-medium",
            plan_name="Codex CLI",
            source_unit="percent_quota",
            observed_quantity=10.0,
            evidence_kind="dashboard_screenshot",
            evidence_ref="r2",
            stigauth_status="STIGAUTH_ACTIVE",
        ),
        IDECostSample(
            surface="antigravity",
            agent_id="AG31",
            model_label="gemini-3.1-pro-high",
            plan_name="Antigravity AI Credits",
            source_unit="credits",
            observed_quantity=0.0,
            included_usage_remaining=24122.0,
            evidence_kind="dashboard_screenshot",
            evidence_ref="r3",
            stigauth_status="STIGAUTH_ACTIVE",
        ),
    ])
    report = build_report(ledger_path=led)
    units = {s.source_unit for s in report.surfaces}
    assert units == {"tokens", "percent_quota", "credits"}, (
        f"reader must preserve heterogeneous units; got {units}"
    )
    out = report.render_summary()
    assert "70.0M tokens" in out
    assert "10 percent_quota" in out
    assert "24.1K credits left" in out or "24122" in out
    # The intent: NO number that sums tokens+percent_quota+credits.
    # The footer line "cross-vendor totals deliberately omitted" is the
    # only place "total" is allowed — and only to flag the absence of one.
    assert "deliberately omitted" in out.lower(), (
        "report must explicitly flag the absence of a cross-vendor total"
    )
    forbidden_aggregates = (
        "total cost",
        "grand total",
        "total tokens",
        "total credits",
        "total usd",
        "= 70000010",   # 70M + 10
        "= 70000020",
    )
    for needle in forbidden_aggregates:
        assert needle not in out.lower(), f"forbidden aggregate appeared: {needle}"


def test_latest_sample_supersedes_older_for_same_unit(tmp_path: Path):
    led = tmp_path / "ide_cost_ledger.jsonl"
    older = IDECostSample(
        surface="cursor",
        agent_id="C47H",
        model_label="claude-opus-4-7-thinking-high",
        plan_name="Ultra",
        source_unit="percent_quota",
        observed_quantity=10.0,
        evidence_kind="dashboard_screenshot",
        evidence_ref="r_old",
        stigauth_status="STIGAUTH_ACTIVE",
        sampled_at=1000.0,
    )
    newer = IDECostSample(
        surface="cursor",
        agent_id="C47H",
        model_label="claude-opus-4-7-thinking-high",
        plan_name="Ultra",
        source_unit="percent_quota",
        observed_quantity=31.0,
        evidence_kind="dashboard_screenshot",
        evidence_ref="r_new",
        stigauth_status="STIGAUTH_ACTIVE",
        sampled_at=2000.0,
    )
    _seed(led, [older, newer])
    report = build_report(ledger_path=led)
    assert len(report.surfaces) == 1
    assert report.surfaces[0].observed_quantity == 31.0


def test_two_units_same_agent_both_kept(tmp_path: Path):
    """Two readings of the same agent in different units are both legitimate facets."""
    led = tmp_path / "ide_cost_ledger.jsonl"
    _seed(led, [
        IDECostSample(
            surface="cursor",
            agent_id="C47H",
            model_label="claude-opus-4-7-thinking-high",
            plan_name="Ultra",
            source_unit="percent_quota",
            observed_quantity=31.0,
            evidence_kind="dashboard_screenshot",
            evidence_ref="r1",
            stigauth_status="STIGAUTH_ACTIVE",
        ),
        IDECostSample(
            surface="cursor",
            agent_id="C47H",
            model_label="claude-opus-4-7-thinking-high",
            plan_name="Ultra",
            source_unit="tokens",
            observed_quantity=70_000_000.0,
            evidence_kind="dashboard_screenshot",
            evidence_ref="r2",
            stigauth_status="STIGAUTH_ACTIVE",
        ),
    ])
    report = build_report(ledger_path=led)
    units = sorted(s.source_unit for s in report.surfaces)
    assert units == ["percent_quota", "tokens"]


def test_surface_display_order_is_stable(tmp_path: Path):
    led = tmp_path / "ide_cost_ledger.jsonl"
    _seed(led, [
        IDECostSample(
            surface="alice_local",
            agent_id="ALICE",
            model_label="gemma4-phc:latest",
            plan_name="local",
            source_unit="local_watts",
            observed_quantity=0.0,
            evidence_kind="manual_receipt",
            evidence_ref="r_alice",
            stigauth_status="STIGAUTH_STANDBY",
        ),
        IDECostSample(
            surface="codex",
            agent_id="C55M",
            model_label="gpt-5.4-medium",
            plan_name="Codex CLI",
            source_unit="percent_quota",
            observed_quantity=10.0,
            evidence_kind="dashboard_screenshot",
            evidence_ref="r_codex",
            stigauth_status="STIGAUTH_ACTIVE",
        ),
        IDECostSample(
            surface="cursor",
            agent_id="C47H",
            model_label="claude-opus-4-7-thinking-high",
            plan_name="Ultra",
            source_unit="percent_quota",
            observed_quantity=31.0,
            evidence_kind="dashboard_screenshot",
            evidence_ref="r_cursor",
            stigauth_status="STIGAUTH_ACTIVE",
        ),
    ])
    report = build_report(ledger_path=led)
    surfaces_in_order = [s.surface for s in report.surfaces]
    assert surfaces_in_order == ["cursor", "codex", "alice_local"]
    for i in range(len(surfaces_in_order) - 1):
        a, b = surfaces_in_order[i], surfaces_in_order[i + 1]
        assert SURFACE_DISPLAY_ORDER.index(a) < SURFACE_DISPLAY_ORDER.index(b)


def test_corrupt_lines_are_skipped_not_fatal(tmp_path: Path):
    led = tmp_path / "ide_cost_ledger.jsonl"
    _seed(led, [
        IDECostSample(
            surface="cursor",
            agent_id="C47H",
            model_label="claude-opus-4-7-thinking-high",
            plan_name="Ultra",
            source_unit="percent_quota",
            observed_quantity=31.0,
            evidence_kind="dashboard_screenshot",
            evidence_ref="r1",
            stigauth_status="STIGAUTH_ACTIVE",
        )
    ])
    with led.open("a", encoding="utf-8") as f:
        f.write("not json at all\n")
        f.write("{partial json\n")
    report = build_report(ledger_path=led)
    assert len(report.surfaces) == 1
    assert report.surfaces[0].agent_id == "C47H"
