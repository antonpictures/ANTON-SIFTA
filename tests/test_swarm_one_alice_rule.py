from System.swarm_one_alice_rule import (
 classify_identity_text,
 explain_the_one,
 surface_receipt,
)


def test_explain_the_one_names_single_body_and_many_surfaces():
 text = explain_the_one().casefold()

 assert "one organism" in text
 assert "many surfaces" in text
 assert "one global chat" in text
 assert "focus routes actions" in text


def test_split_identity_language_is_detected():
 verdict = classify_identity_text("Terminal Alice and app Alice are different Alice instances.")

 assert verdict.ok is False
 assert verdict.label == "split_identity_language"
 assert verdict.matched
 assert "one organism" in verdict.correction.casefold()


def test_surface_language_stays_one_alice():
 verdict = classify_identity_text("The Matrix Terminal is a surface and the app is a hand.")

 assert verdict.ok is True
 assert verdict.label == "one_alice_surface_language"
 assert "matrix terminal" in verdict.matched
 assert "app" in verdict.matched


def test_surface_receipt_points_to_global_chat():
 row = surface_receipt("cortex bridge", "answer George")

 assert row["truth_label"] == "ONE_ALICE_SURFACE_RECEIPT_V1"
 assert row["identity"] == "one_alice_many_surfaces"
 assert row["surface"] == "cortex bridge"
 assert row["global_chat_ledger"].endswith(".sifta_state/alice_conversation.jsonl")
