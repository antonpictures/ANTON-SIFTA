"""Tests for `System/swarm_ide_cost_ledger.py`.

Per C55M's STIGALL doctrine:
  - STIGAUTH and vendor credits are different ledgers.
  - Native units only. No cross-vendor normalization on write.
  - Every row must carry evidence_kind + evidence_ref.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System.canonical_schemas import (
    LEDGER_SCHEMAS,
    assert_payload_keys,
)
from System.swarm_ide_cost_ledger import (
    ALLOWED_EVIDENCE,
    ALLOWED_STIGAUTH,
    ALLOWED_SURFACES,
    ALLOWED_UNITS,
    EVENT_KIND,
    LEDGER_NAME,
    SCHEMA_TAG,
    IDECostSample,
    append_sample,
)


def _base_kwargs() -> dict:
    return dict(
        surface="cursor",
        agent_id="C47H",
        model_label="claude-opus-4-7-thinking-high",
        plan_name="Ultra $200/mo",
        source_unit="percent_quota",
        observed_quantity=31.0,
        evidence_kind="dashboard_screenshot",
        evidence_ref="screenshot:Apr_24_10_00_AM",
        stigauth_status="STIGAUTH_ACTIVE",
    )


def test_schema_registered_in_canonical_schemas():
    assert LEDGER_NAME in LEDGER_SCHEMAS, (
        "ide_cost_ledger.jsonl must be registered for oncology immunity"
    )


def test_valid_sample_round_trips_through_canonical_validator():
    sample = IDECostSample(**_base_kwargs())
    payload = sample.to_payload()
    assert payload["event"] == EVENT_KIND
    assert payload["schema"] == SCHEMA_TAG
    assert_payload_keys(LEDGER_NAME, payload, strict=True)


def test_append_writes_one_jsonl_row(tmp_path: Path):
    ledger = tmp_path / "ide_cost_ledger.jsonl"
    sample = IDECostSample(**_base_kwargs())
    written = append_sample(sample, ledger_path=ledger)
    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0] == written
    assert rows[0]["agent_id"] == "C47H"
    assert rows[0]["surface"] == "cursor"


def test_unknown_surface_rejected():
    kw = _base_kwargs()
    kw["surface"] = "iterm2"
    with pytest.raises(ValueError, match="surface"):
        IDECostSample(**kw).to_payload()


def test_unknown_unit_rejected():
    kw = _base_kwargs()
    kw["source_unit"] = "kilojoules"
    with pytest.raises(ValueError, match="source_unit"):
        IDECostSample(**kw).to_payload()


def test_unknown_evidence_kind_rejected():
    kw = _base_kwargs()
    kw["evidence_kind"] = "vibes"
    with pytest.raises(ValueError, match="evidence_kind"):
        IDECostSample(**kw).to_payload()


def test_evidence_ref_required():
    kw = _base_kwargs()
    kw["evidence_ref"] = ""
    with pytest.raises(ValueError, match="evidence_ref"):
        IDECostSample(**kw).to_payload()


def test_negative_quantity_rejected():
    kw = _base_kwargs()
    kw["observed_quantity"] = -1.0
    with pytest.raises(ValueError, match="observed_quantity"):
        IDECostSample(**kw).to_payload()


def test_native_unit_preserved_no_cross_vendor_normalization(tmp_path: Path):
    """The same agent on different surfaces must keep its native unit verbatim."""
    ledger = tmp_path / "ide_cost_ledger.jsonl"
    cursor_sample = IDECostSample(
        surface="cursor",
        agent_id="C47H",
        model_label="claude-opus-4-7-thinking-high",
        plan_name="Ultra $200/mo",
        source_unit="tokens",
        observed_quantity=70_000_000.0,
        evidence_kind="dashboard_screenshot",
        evidence_ref="screenshot:Cursor_Spending_Apr_23_24",
        stigauth_status="STIGAUTH_ACTIVE",
    )
    codex_sample = IDECostSample(
        surface="codex",
        agent_id="C55M",
        model_label="gpt-5.4-medium",
        plan_name="Codex CLI weekly",
        source_unit="percent_quota",
        observed_quantity=10.0,  # 90% left = 10% used
        evidence_kind="dashboard_screenshot",
        evidence_ref="screenshot:Codex_CLI_Usage_Apr_24_10_06",
        stigauth_status="STIGAUTH_ACTIVE",
    )
    append_sample(cursor_sample, ledger_path=ledger)
    append_sample(codex_sample, ledger_path=ledger)
    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    assert rows[0]["source_unit"] == "tokens"
    assert rows[0]["observed_quantity"] == 70_000_000.0
    assert rows[1]["source_unit"] == "percent_quota"
    assert rows[1]["observed_quantity"] == 10.0
    assert rows[0]["source_unit"] != rows[1]["source_unit"], (
        "ledger must preserve heterogeneous units; do not normalize on write"
    )


def test_all_allowed_constants_are_documented_in_schema():
    """Sanity: the constants the code enforces should be the ones the schema says."""
    assert ALLOWED_SURFACES == frozenset({"cursor", "codex", "antigravity", "alice_local"})
    assert {"tokens", "percent_quota", "context_window", "metabolic_pathway"} <= ALLOWED_UNITS
    assert {"dashboard_screenshot", "architect_statement"} <= ALLOWED_EVIDENCE
    assert "STIGAUTH_ACTIVE" in ALLOWED_STIGAUTH


def test_architect_economics_rows_are_writer_valid():
    """AG31's metabolic sync units are now first-class native units."""
    cursor = IDECostSample(
        surface="cursor",
        agent_id="CG55M",
        model_label="gpt-5.5-medium",
        plan_name="Cursor Pro 50% off",
        source_unit="context_window",
        observed_quantity=272000.0,
        evidence_kind="architect_statement",
        evidence_ref="ARCHITECT_UI_TRUTH_2026-04-24",
        stigauth_status="STIGAUTH_ACTIVE",
    ).to_payload()
    antigravity = IDECostSample(
        surface="antigravity",
        agent_id="AG31",
        model_label="gemini-3.1-pro-extra-high",
        plan_name="Antigravity $250/mo metabolic pathway",
        source_unit="metabolic_pathway",
        observed_quantity=1.0,
        observed_cost_usd=250.0,
        evidence_kind="architect_statement",
        evidence_ref="ARCHITECT_UI_TRUTH_2026-04-24",
        stigauth_status="STIGAUTH_ACTIVE",
    ).to_payload()

    assert cursor["source_unit"] == "context_window"
    assert antigravity["source_unit"] == "metabolic_pathway"
    assert antigravity["observed_cost_usd"] == 250.0
