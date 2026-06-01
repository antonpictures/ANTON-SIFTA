#!/usr/bin/env python3
"""r261: Alice's legs organ — the walking-laptop scaffold. Honest until hardware (§6)."""
from System import swarm_legs_locomotion_organ as legs


def test_status_no_hardware_by_default(tmp_path):
    sifta = tmp_path / ".sifta_state"
    st = legs.legs_status(state_dir=sifta)
    assert st["hardware_present"] is False
    assert st["status"] == "PLAN_NO_HARDWARE"
    assert "step_forward" in st["known_intents"]
    assert legs.legs_hardware_present(state_dir=sifta) is False


def test_request_locomotion_never_fakes_motion(tmp_path):
    sifta = tmp_path / ".sifta_state"
    res = legs.request_locomotion("step_forward", state_dir=sifta, reason="owner asked her to walk")
    assert res["ok"] is False
    assert res["status"] == "no_hardware"
    assert res["executed"] is False
    # the intent is logged (so design/sim can use it) but never as an action
    ledger = sifta / "alice_legs_locomotion.jsonl"
    assert ledger.exists()
    assert len(ledger.read_text().strip().splitlines()) == 1


def test_context_block_does_not_claim_movement(tmp_path):
    blk = legs.legs_context_block(state_dir=tmp_path / ".sifta_state")
    assert "not attached yet" in blk
    assert "do not claim" in blk.lower()


def test_simulate_walking_is_sim_only(tmp_path):
    import json
    sifta = tmp_path / ".sifta_state"
    out = legs.simulate_locomotion("step_forward", steps=4, state_dir=sifta)
    assert out["mode"] == "SIMULATION"
    assert out["executed_in_reality"] is False
    assert len(out["frames"]) == 4
    assert out["forward_m"] > 0  # she advanced in SIM
    assert "balance_stress" in out["sim_visceral"]
    ledger = sifta / "alice_legs_locomotion.jsonl"
    rows = [json.loads(l) for l in ledger.read_text().strip().splitlines()]
    assert any(r.get("kind") == "LOCOMOTION_SIMULATION" and r.get("executed_in_reality") is False
               for r in rows)


def test_simulate_stand_does_not_advance(tmp_path):
    out = legs.simulate_locomotion("stand", steps=4, state_dir=tmp_path / ".sifta_state")
    assert out["forward_m"] == 0.0  # standing in place does not move forward
    assert out["mode"] == "SIMULATION"


def test_flagged_hardware_still_no_faked_step(tmp_path):
    # Even if a flag says legs are present, with no real runtime adapter the organ must
    # NOT return ok=True — no faked motion can ever reach Alice (§6).
    sifta = tmp_path / ".sifta_state"
    sifta.mkdir(parents=True, exist_ok=True)
    (sifta / "legs_hardware_present.flag").write_text("present", encoding="utf-8")
    assert legs.legs_hardware_present(state_dir=sifta) is True
    assert legs.legs_status(state_dir=sifta)["status"] == "READY_RUNTIME_WIRED"
    res = legs.request_locomotion("stand", state_dir=sifta)
    assert res["ok"] is False
    assert res["status"] == "runtime_adapter_not_implemented"
    assert res["executed"] is False
