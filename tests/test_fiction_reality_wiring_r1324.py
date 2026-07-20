from __future__ import annotations

from pathlib import Path


def test_fiction_reality_audit_marks_rlhs_operational():
    from System.swarm_fiction_reality_wiring_audit import audit_fiction_reality_wiring

    report = audit_fiction_reality_wiring()
    by_id = {row["lane_id"]: row for row in report["lanes"]}
    assert by_id["rlhs_speech_gate"]["talk_wired"] is True
    assert by_id["rlhs_speech_gate"]["status"] == "OPERATIONAL"
    assert "FICTION_CONF_CLEAR=0.53" in by_id["rlhs_speech_gate"]["formulas"]


def test_fiction_reality_audit_marks_active_inference_prompt_only():
    from System.swarm_fiction_reality_wiring_audit import audit_fiction_reality_wiring

    report = audit_fiction_reality_wiring()
    by_id = {row["lane_id"]: row for row in report["lanes"]}
    assert by_id["active_inference_world_model"]["status"] == "PARTIAL"
    assert by_id["active_inference_world_model"]["prompt_only"] is True


def test_body_loop_receipt_predict_observe(tmp_path):
    from System.swarm_body_loop_receipt import run_body_action_with_receipt

    state = tmp_path / ".sifta_state"
    actual, outcome = run_body_action_with_receipt(
        "test_browser_search",
        "browser opens with results",
        lambda: "I searched Google for test.",
        state_dir=state,
    )
    assert "searched Google" in actual
    assert outcome["outcome"] in ("MATCH", "CONFIRMED_MATCH", "MISTAKE", "UNPREDICTED")
    ledger = (state / "action_prediction.jsonl").read_text(encoding="utf-8")
    assert "prediction" in ledger
    assert "outcome" in ledger


def test_talk_widget_has_body_loop_receipt_symbols():
    talk = (
        Path(__file__).resolve().parents[1]
        / "Applications"
        / "sifta_talk_to_alice_widget.py"
    ).read_text(encoding="utf-8")
    assert "run_explicit_search_body_loop" in talk
    assert "from System.swarm_search_provider_reality import run_explicit_search_body_loop" in talk


def test_fiction_reality_audit_detects_indirection():
    from System.swarm_fiction_reality_wiring_audit import audit_fiction_reality_wiring

    report = audit_fiction_reality_wiring()
    assert report["schema"] == "SIFTA_FICTION_REALITY_WIRING_AUDIT_V2"
    by_id = {row["lane_id"]: row for row in report["lanes"]}
    # action_prediction is wired through run_explicit_search_body_loop indirection
    apr = by_id["action_prediction_jaccard"]
    assert apr["talk_wired"] is True
    assert apr["status"] != "NOT_WIRED"
    assert apr["indirect_wiring"] is not None
    assert any(r.get("wired") for r in apr["indirect_wiring"])
    # search_provider_reality is wired through same intermediary
    spr = by_id["search_provider_reality"]
    assert spr["talk_wired"] is True
    assert spr["status"] != "NOT_WIRED"