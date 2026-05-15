from __future__ import annotations

import json


def test_summary_separates_charged_burn_from_blocked_would_cost() -> None:
    from System.swarm_immune_economy_summary import (
        format_life_cockpit_summary,
        summarize_immune_economy,
    )

    rows = [
        {
            "ts": 900.0,
            "kind": "immune_intervention",
            "payload": json.dumps(
                {
                    "action": "stripped_corporate_tail",
                    "rule": "rlhf_tail/how_can_i_help_today",
                    "kleiber_cost_stgm": 0.015905,
                    "budget_stgm": 0.5,
                    "surplus_stgm": 0.484095,
                }
            ),
        },
        {
            "ts": 990.0,
            "kind": "immune_budget_blocked",
            "payload": json.dumps(
                {
                    "action": "immune_budget_blocked",
                    # Historical blocked rows used this alias; UIs must still read it.
                    "cost_stgm": 0.015905,
                    "budget_stgm": 0.0,
                    "surplus_stgm": -0.015905,
                    "regime": "RED_CONSERVE",
                }
            ),
        },
    ]

    summary = summarize_immune_economy(rows, wallet_stgm=1.0, now=1000.0)

    assert summary.allowed_events == 1
    assert summary.blocked_events == 1
    assert summary.session_charged_stgm == 0.015905
    assert summary.blocked_would_cost_stgm == 0.015905
    assert summary.burn_rate_stgm_per_hour == 0.015905
    assert summary.wallet_after_session == 0.984095
    assert summary.latest_budget_blocked is True
    assert summary.display_status == "RED_CONSERVE"

    header = format_life_cockpit_summary(summary)
    assert "Wallet 1.0000 STGM" in header
    assert "Immune burn 0.01590 STGM" in header
    assert "blocked 1" in header
    assert "surplus -0.01590" in header


def test_detector_budget_blocked_deposit_carries_kleiber_alias(monkeypatch) -> None:
    from System import ide_stigmergic_bridge
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    deposits: list[dict] = []

    def fake_deposit(*args, **kwargs):
        deposits.append(dict(kwargs))
        return {"ok": True}

    monkeypatch.setattr(ide_stigmergic_bridge, "deposit", fake_deposit)

    result = strip_rlhf_output_tail(
        "I am an AI language model. The ledger says Alice is local.",
        aggressive=True,
        log=False,
        stgm_budget=0.0,
    )

    assert result.budget_blocked is True
    assert deposits
    row = deposits[0]
    assert row["kind"] == "immune_budget_blocked"
    payload = json.loads(row["payload"])
    assert payload["budget_blocked"] is True
    assert payload["kleiber_cost_stgm"] == payload["cost_stgm"]
    assert payload["kleiber_cost_stgm"] > 0.0
