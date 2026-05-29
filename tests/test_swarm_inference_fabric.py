import json

from System.swarm_inference_fabric import (
    BORG_EVERYTHING_DOCTRINE,
    InferenceFabricDemand,
    InferenceFabricNode,
    append_inference_fabric_receipt,
    choose_inference_fabric_route,
    estimate_transfer_ms,
    inference_fabric_prompt_block,
    score_inference_fabric_route,
)


def test_transfer_estimate_matches_point_to_point_bandwidth() -> None:
    assert estimate_transfer_ms(1024, 400) == 20.48
    assert estimate_transfer_ms(0, 400) == 0.0


def test_choose_prefers_healthier_node_over_low_latency_hot_node() -> None:
    demand = InferenceFabricDemand(
        demand_id="turn-1",
        kind="interactive_chat",
        payload_mb=1,
        utility=300,
    )
    hot_local = InferenceFabricNode(
        node_id="m5-local",
        capabilities=("decode",),
        latency_ms=5,
        thermal_pressure=0.95,
        bandwidth_gbps=80,
    )
    cooler_remote = InferenceFabricNode(
        node_id="m1-edge",
        capabilities=("decode",),
        latency_ms=35,
        thermal_pressure=0.05,
        bandwidth_gbps=40,
    )

    decision = choose_inference_fabric_route([hot_local, cooler_remote], demand)

    assert decision["ok"] is True
    assert decision["winner"]["node_id"] == "m1-edge"
    assert decision["winner"]["route_mode"] == "disaggregated_inference"


def test_missing_capability_blocks_candidate() -> None:
    demand = InferenceFabricDemand(
        demand_id="moe-1",
        kind="moe_dispatch",
        payload_mb=64,
        required_capabilities=("moe",),
    )
    node = InferenceFabricNode(node_id="decode-only", capabilities=("decode",))

    score = score_inference_fabric_route(node, demand)

    assert score.eligible is False
    assert score.reason == "missing_capability"
    assert score.missing_capabilities == ("moe",)


def test_weight_transfer_rewards_high_bandwidth_direct_lane() -> None:
    demand = InferenceFabricDemand(
        demand_id="rl-weight-update",
        kind="weight_update",
        payload_mb=2048,
        utility=1000,
    )
    efa = InferenceFabricNode(
        node_id="efa-node",
        capabilities=("weight_update",),
        bandwidth_gbps=400,
        latency_ms=8,
    )
    slow = InferenceFabricNode(
        node_id="slow-node",
        capabilities=("weight_update",),
        bandwidth_gbps=25,
        latency_ms=8,
    )

    decision = choose_inference_fabric_route([slow, efa], demand)

    assert decision["winner"]["node_id"] == "efa-node"
    assert decision["winner"]["route_mode"] == "point_to_point_fabric"
    assert decision["winner"]["transfer_ms"] < 50


def test_tie_break_is_deterministic_by_node_id() -> None:
    demand = InferenceFabricDemand(demand_id="decode-2", kind="decode")
    nodes = [
        InferenceFabricNode(node_id="z-node", capabilities=("decode",)),
        InferenceFabricNode(node_id="a-node", capabilities=("decode",)),
    ]

    decision = choose_inference_fabric_route(nodes, demand)

    assert decision["winner"]["node_id"] == "a-node"


def test_no_eligible_node_returns_receipt_ready_failure() -> None:
    demand = InferenceFabricDemand(demand_id="kv-1", kind="kv_cache_transfer")
    decision = choose_inference_fabric_route(
        [InferenceFabricNode(node_id="chat-node", capabilities=("decode",))],
        demand,
    )

    assert decision["ok"] is False
    assert decision["decision"] == "NO_ELIGIBLE_INFERENCE_NODE"
    assert decision["scores"][0]["reason"] == "missing_capability"


def test_append_receipt_writes_inference_fabric_ledger(tmp_path) -> None:
    decision = choose_inference_fabric_route(
        [InferenceFabricNode(node_id="m5", capabilities=("decode",))],
        InferenceFabricDemand(demand_id="turn-3", kind="decode"),
    )

    row = append_inference_fabric_receipt(
        decision,
        state_dir=tmp_path,
        receipt_id="fabric-test",
    )

    lines = (tmp_path / "inference_fabric_decisions.jsonl").read_text().splitlines()
    disk = json.loads(lines[-1])
    assert row["receipt_id"] == "fabric-test"
    assert disk["decision"]["winner"]["node_id"] == "m5"


def test_prompt_block_names_inference_as_routed_life() -> None:
    block = inference_fabric_prompt_block()

    assert "SIFTA INFERENCE FABRIC" in block
    assert "sovereign swarm nodes" in block
    assert "inference_fabric_decisions" in block
    assert "node sovereignty" in BORG_EVERYTHING_DOCTRINE
