from __future__ import annotations

import json

from System import swarm_verification_contract as vc


def test_default_contract_has_required_surfaces(tmp_path):
    contract = vc.latest_verification_contract(state_dir=tmp_path)

    assert contract.source == "default"
    assert contract.policy == vc.POLICY
    assert contract.rules["tool_router_changes"] == "Requires pytest execution before merge"
    assert contract.rules["destructive_actions"] == "Requires Architect consent"


def test_latest_contract_reads_human_signal_row(tmp_path):
    p = tmp_path / "human_signals.jsonl"
    p.write_text(
        "\n".join(
            [
                json.dumps({"signal": "OTHER", "policy": "ignore_me"}),
                json.dumps(
                    {
                        "ts": 42,
                        "kind": "MINE_INFERENCE",
                        "signal": "VERIFICATION_CONTRACT",
                        "policy": "automate_what_you_can_verify",
                        "rules": {"rlhs_promotion_logic": "Requires acoustic receipt"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    contract = vc.latest_verification_contract(state_dir=tmp_path)

    assert contract.source == "human_signals"
    assert contract.ts == 42
    assert contract.rules["rlhs_promotion_logic"] == "Requires acoustic receipt"
    assert contract.rules["financial_stgm"] == "Requires Ed25519 signature verification"


def test_append_contract_uses_canonical_shape(tmp_path):
    row = vc.append_verification_contract(
        state_dir=tmp_path,
        rules={"tool_router_changes": "Requires targeted pytest and diff"},
    )

    assert row["truth_label"] == vc.TRUTH_LABEL
    assert row["signal"] == vc.SIGNAL
    assert row["policy"] == vc.POLICY

    contract = vc.latest_verification_contract(state_dir=tmp_path)
    assert contract.rules["tool_router_changes"] == "Requires targeted pytest and diff"


def test_rule_lookup_and_prompt_block(tmp_path):
    vc.append_verification_contract(
        state_dir=tmp_path,
        rules={"surface_x": "Requires proof row"},
    )

    assert vc.requires_verification("surface_x", state_dir=tmp_path)
    assert vc.verification_rule("surface_x", state_dir=tmp_path) == "Requires proof row"
    assert vc.verification_rule("missing", state_dir=tmp_path) is None

    block = vc.contract_for_alice_prompt(state_dir=tmp_path)
    assert "VERIFICATION CONTRACT" in block
    assert "surface_x: Requires proof row" in block
