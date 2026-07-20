import json
from pathlib import Path

from System import swarm_crypto_behavior_memory
from System.swarm_sifta_chart_memory import behavior_gate, rebuild_memory


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_chart_memory_deduplicates_tickers_and_does_not_call_outcomes_price_chop(
    tmp_path: Path, monkeypatch
) -> None:
    state = tmp_path / ".sifta_state"
    path = state / "alice_15m_settled.jsonl"
    for i in range(8):
        row = {
            "ticker": f"BTC-{i}",
            "asset": "BTC",
            "win": bool(i % 2),
            "pnl": 0.2 if i % 2 else -0.2,
            "strategy": "follow_crowd",
            "ts": 1000 + i,
        }
        _append(path, row)
        if i == 3:
            _append(path, row)

    memory = rebuild_memory(state_dir=state)
    btc = memory["assets"]["BTC"]
    assert memory["n_raw_rows"] == 9
    assert memory["n_settled_rows"] == 8
    assert memory["n_duplicate_tickers_ignored"] == 1
    assert btc["outcome_flip_noise"] is True

    monkeypatch.setattr(
        swarm_crypto_behavior_memory,
        "behavior_snapshot",
        lambda *_args, **_kwargs: {
            "available": True,
            "trusted": False,
            "predicted_side": "DOWN",
            "summary": "spot mixed · shadow learning",
        },
    )
    gate = behavior_gate(
        "BTC",
        side="yes",
        kalshi_yes=0.75,
        state_dir=state,
    )
    assert gate["action"] == "ok"
    assert gate["memory"]["outcome_flip_noise"] is True
    assert "spot mixed" in gate["summary"]


def test_only_proven_proxy_signal_can_veto(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        swarm_crypto_behavior_memory,
        "behavior_snapshot",
        lambda *_args, **_kwargs: {
            "available": True,
            "trusted": True,
            "predicted_side": "DOWN",
            "summary": "spot trend down · trusted veto",
        },
    )
    gate = behavior_gate(
        "SOL",
        side="yes",
        kalshi_yes=0.74,
        state_dir=tmp_path,
    )
    assert gate["action"] == "sit_out"
    assert "trusted_spot_disagrees=DOWN" in gate["reasons"]

