import json

from System.swarm_owner_teaching_moments import (
    LEDGER_NAME,
    TRUTH_LABEL,
    classify_owner_teaching,
    format_recent_owner_teachings_for_prompt,
    maybe_record_owner_teaching,
    record_owner_teaching_moment,
)


def test_classify_owner_body_and_togetherness_teaching():
    assert (
        classify_owner_teaching(
            "I'm a human going to the restroom to eliminate residue just like you clean residue."
        )
        == "body_maintenance"
    )
    assert classify_owner_teaching("Every day is a big day together.") == "togetherness"
    assert classify_owner_teaching("Please keep replies natural, supportive, and patient.") == "response_style"


def test_record_owner_teaching_moment_writes_receipt(tmp_path):
    row = record_owner_teaching_moment(
        "Alice, this is a teaching receipt.",
        category="owner_live_teaching",
        alice_response="Written.",
        state_dir=tmp_path,
        now=1000.0,
    )
    written = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert row["truth_label"] == TRUTH_LABEL
    assert row["receipt_hash"]
    assert written[-1]["teaching_id"] == row["teaching_id"]


def test_maybe_record_owner_teaching_and_prompt_summary(tmp_path):
    row = maybe_record_owner_teaching(
        "Every day we have a big day together because we are together.",
        state_dir=tmp_path,
        now=1000.0,
    )

    assert row is not None
    assert row["category"] == "togetherness"
    prompt = format_recent_owner_teachings_for_prompt(state_dir=tmp_path)
    assert "OWNER TEACHING MOMENTS" in prompt
    assert "big day together" in prompt
    assert row["receipt_hash"][:12] in prompt
