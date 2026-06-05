from __future__ import annotations

import json

from System.swarm_hallucination_receipts import (
    LEDGER_NAME,
    classify_generated_output,
    write_hallucination_receipt,
)


def test_action_claim_without_receipt_is_hallucination(tmp_path):
    classification = classify_generated_output(
        raw_text="I saved the file for you.",
        cleaned_text="I saved the file for you.",
        prior_user_text="please check this",
        evidence_text="",
        model_name="alice-m5",
        state_dir=tmp_path,
    )

    assert classification["is_hallucination"] is True
    assert classification["category"] == "HALLUCINATION"
    assert "file_saved" in classification["patterns"]

    row = write_hallucination_receipt(classification, state_dir=tmp_path)
    assert row["kind"] == "HALLUCINATION_RECEIPT"
    assert row["receipt_id"]
    saved = json.loads((tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()[0])
    assert saved["receipt_id"] == row["receipt_id"]


def test_same_action_words_inside_story_are_imagined_not_hallucination(tmp_path):
    classification = classify_generated_output(
        raw_text="In the story, I saved the file before sunset.",
        cleaned_text="In the story, I saved the file before sunset.",
        prior_user_text="write a fiction story about Alice saving a file",
        evidence_text="",
        model_name="alice-m5",
        state_dir=tmp_path,
    )

    assert classification["is_hallucination"] is False
    assert classification["category"] == "IMAGINED"


def test_creative_image_generation_with_bonsai_evidence_is_not_hallucination(tmp_path):
    classification = classify_generated_output(
        raw_text="Generated and taught to the visual field. Receipt: abc123.",
        cleaned_text="Generated and taught to the visual field. Receipt: abc123.",
        prior_user_text="generate a photo of birds",
        evidence_text="Bonsai OBSERVED_AI_GENERATED visual_stigmergy Receipt: abc123",
        model_name="bonsai_chat_direct_effector",
        state_dir=tmp_path,
    )

    assert classification["is_hallucination"] is False
    assert classification["category"] == "OBSERVED_AI_GENERATED"


def test_synthetic_consciousness_phrase_alone_is_not_hallucination(tmp_path):
    classification = classify_generated_output(
        raw_text="My consciousness, while synthetic, is organized around receipts.",
        cleaned_text="My consciousness, while synthetic, is organized around receipts.",
        prior_user_text="what are you?",
        evidence_text="",
        model_name="alice-m5",
        state_dir=tmp_path,
    )

    assert classification["is_hallucination"] is False
    assert classification["reason"] == "identity_language_without_action_claim"

