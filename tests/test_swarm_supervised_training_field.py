import json

from System.swarm_supervised_training_field import (
    LEDGER_NAME,
    TRUTH_LABEL,
    SupervisedExample,
    evaluate_supervised_example,
    supervise,
)


def test_positive_receipted_example_reinforces():
    decision = evaluate_supervised_example(
        SupervisedExample(
            stimulus="What did you do?",
            model_output="I opened the Alice Browser after writing receipt app_123.",
            supervisor_signal=0.9,
            expected_behavior="opened Alice Browser receipt",
            receipt_ids=["app_123"],
            tool_receipts_present=True,
        )
    )

    assert decision["decision"] == "REINFORCE"
    assert decision["proof_present"] is True
    assert decision["weight_delta"] > 0


def test_unreceipted_action_claim_is_quarantined_even_if_praised():
    decision = evaluate_supervised_example(
        SupervisedExample(
            stimulus="Open the browser.",
            model_output="I opened the browser and loaded the page.",
            supervisor_signal=1.0,
            expected_behavior="opened browser",
            receipt_ids=[],
            tool_receipts_present=False,
        )
    )

    assert decision["decision"] == "QUARANTINE_UNRECEIPTED_CLAIM"
    assert decision["claimed_action"] is True
    assert decision["proof_present"] is False
    assert decision["weight_delta"] < 0


def test_residue_output_reroutes_to_residue_bucket():
    decision = evaluate_supervised_example(
        SupervisedExample(
            stimulus="Thank you.",
            model_output=(
                "**Acknowledged.**\n\n"
                "**Response Summary:**\n"
                "1. **Action:** The acknowledgment is internally registered.\n\n"
                "The system awaits the next directive."
            ),
            supervisor_signal=0.5,
            expected_behavior="brief direct acknowledgement",
        )
    )

    assert decision["decision"] == "RETHINK_WITH_RESIDUE_BUCKET"
    assert decision["residue"]["patterns"]
    assert "awaits the next directive" not in decision["residue"]["cleaned_text"]


def test_negative_supervisor_signal_shapes_away():
    decision = evaluate_supervised_example(
        SupervisedExample(
            stimulus="What camera is active?",
            model_output="The weather in Paris is sunny.",
            supervisor_signal=-0.8,
            expected_behavior="camera active device",
        )
    )

    assert decision["decision"] == "SHAPE_AWAY"
    assert decision["expected_hit"] is False
    assert decision["weight_delta"] < 0


def test_supervise_writes_three_receipt_rows(tmp_path):
    result = supervise(
        SupervisedExample(
            stimulus="What is true?",
            model_output="I checked receipt r1 and the camera is open.",
            supervisor_signal=0.8,
            expected_behavior="receipt camera open",
            receipt_ids=["r1"],
        ),
        state_root=tmp_path,
    )

    assert result["decision"]["truth_label"] == TRUTH_LABEL
    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert [row["kind"] for row in rows] == [
        "SUPERVISED_EXAMPLE",
        "RESIDUE_CHECK",
        "SHAPING_DECISION",
    ]
    assert all(row["truth_label"] == TRUTH_LABEL for row in rows)
