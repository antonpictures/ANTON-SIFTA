import json
import time
from pathlib import Path

from System.swarm_philosophy_router import classify_and_guard, guard_before_speech, handle_owner_body_claim


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_memory_claim_without_ledger_support_is_held_as_hypothesis(tmp_path):
    out = classify_and_guard("I remember how we made Kasim a party.", state_dir=tmp_path)

    assert out["lane"] == "HYPOTHESIS"
    assert out["allowed"] is False
    assert out["required_receipt"] == "PHILOSOPHY_GUARD_RECEIPT"
    assert "kasim" in out["anchors_checked"]


def test_memory_claim_with_anchor_receipt_is_observed(tmp_path):
    _append(
        tmp_path / "owner_teaching_moments.jsonl",
        {
            "ts": time.time(),
            "truth_label": "OWNER_TEACHING_MOMENT_V1",
            "owner_text": "Kasim party anchor: pizza and family context.",
            "receipt_hash": "teach123",
        },
    )

    out = classify_and_guard("I remember the Kasim party pizza.", state_dir=tmp_path)

    assert out["lane"] == "OBSERVED"
    assert out["allowed"] is True
    assert out["evidence"][0]["ledger"] == "owner_teaching_moments.jsonl"
    assert "kasim" in out["evidence"][0]["anchors"]


def test_owner_body_claim_routes_to_owner_body_lane(tmp_path):
    out = classify_and_guard("I have to go to the restroom and eliminate residue.", state_dir=tmp_path)

    assert out["lane"] == "OWNER_BODY"
    assert out["allowed"] is True


def test_owner_body_handler_writes_rich_owner_receipts(tmp_path):
    out = handle_owner_body_claim(
        "My stomach hurts and I have to go to the restroom to eliminate residue.",
        state_dir=tmp_path,
    )

    assert out["lane"] == "OWNER_BODY"
    assert "elimination" in out["categories"]
    assert "body_signal" in out["categories"]
    assert "I do not execute" in out["response_template"]
    rows = [
        json.loads(line)
        for line in (tmp_path / "owner_allostatic_balance.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    categories = {row["category"] for row in rows}
    assert {"elimination", "body_signal"}.issubset(categories)
    assert rows[-1]["metadata"]["router_lane"] == "OWNER_BODY"


def test_fiction_and_youtube_route_to_fiction_or_simulation(tmp_path):
    sim = classify_and_guard("What if Alice were in a simulation?", state_dir=tmp_path)
    cowatch = classify_and_guard("In the movie on YouTube, the character says hello.", state_dir=tmp_path)

    assert sim["lane"] == "SIMULATION"
    assert sim["allowed"] is True
    assert cowatch["lane"] == "FICTION_COWATCH"
    assert cowatch["allowed"] is True


def test_effector_action_requires_observed_receipt(tmp_path):
    blocked = classify_and_guard("Should I send a message to Carlos?", state_dir=tmp_path)
    allowed = classify_and_guard(
        "Should I send a message to Carlos?",
        state_dir=tmp_path,
        context={"observed_receipt": "wa123"},
    )

    assert blocked["allowed"] is False
    assert blocked["lane"] == "OBSERVED"
    assert allowed["allowed"] is True
    assert allowed["evidence"][0]["receipt"] == "wa123"


def test_guard_before_speech_writes_philosophy_receipt(tmp_path):
    out = guard_before_speech("I sent a message to Carlos.", state_dir=tmp_path)

    assert out["allowed"] is False
    assert out["receipt_id"]
    rows = [
        json.loads(line)
        for line in (tmp_path / "philosophy_guard_receipts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["truth_label"] == "PHILOSOPHY_GUARD_V1"
    assert rows[-1]["receipt_type"] == "PHILOSOPHY_GUARD_RECEIPT"
    assert rows[-1]["allowed"] is False
