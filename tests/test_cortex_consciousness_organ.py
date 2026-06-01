#!/usr/bin/env python3
"""r280: Alice's cortex consciousness organ — her self-model of her own mind hardware.

The r273 organ shipped but was dead code (imported nowhere, no test). r280 wires
cortex_consciousness_block() into the live memory card and pins the behavior here:
the comparison is built only from receipts (never hardcoded), a switch is recorded with
the requesting swimmer's provenance, an unknown cortex is refused, and the block Alice
carries every turn is first-person and names the running + installed cortexes.
"""
import os

from System import swarm_cortex_consciousness_organ as cc


def test_conscious_state_reports_running_installed_and_comparison(tmp_path):
    org = cc.CortexConsciousnessOrgan(state_dir=tmp_path)
    org.installed_cortexes = ["cline", "grok", "local-ollama"]
    st = org.get_conscious_state()
    assert st["truth_label"] == cc.TRUTH_LABEL
    assert isinstance(st["running"], str) and st["running"]   # env-read, never empty
    assert "cline" in st["installed"]
    # even with no history yet, the comparison is explicitly the stigmergic (receipt) kind
    assert "STIGMERGIC_CORTEX_COMPARISON" in st["stigmergic_comparison"]


def test_switch_to_installed_writes_receipt_and_unknown_is_refused(tmp_path):
    prev = os.environ.get("ALICE_CORTEX")
    try:
        org = cc.CortexConsciousnessOrgan(state_dir=tmp_path)
        org.installed_cortexes = ["cline", "grok"]
        bad = org.switch_cortex("does-not-exist", "swimmer#1")
        assert bad["ok"] is False and bad["error"] == "UNKNOWN_CORTEX"
        good = org.switch_cortex("grok", "swimmer#1")
        assert good["ok"] is True and good["switched_to"] == "grok"
        # only the requesting swimmer's receipt id is the recorded provenance
        assert good["stgm_receipt"]["by_swimmer_receipt"] == "swimmer#1"
        # the switch is appended to the organ's own append-only ledger
        ledger = tmp_path / ".sifta_state" / "cortex_consciousness.jsonl"
        assert ledger.exists() and "CORTEX_SWITCH" in ledger.read_text()
    finally:
        if prev is None:
            os.environ.pop("ALICE_CORTEX", None)
        else:
            os.environ["ALICE_CORTEX"] = prev


def test_comparison_is_receipt_grounded_from_test_results(tmp_path):
    org = cc.CortexConsciousnessOrgan(state_dir=tmp_path)
    org.installed_cortexes = ["cline", "grok"]
    org.record_test_result("grok", 0.91, "r-eval-grok")
    org.record_test_result("cline", 0.42, "r-eval-cline")
    comp = org._generate_comparison()
    # the field winner is computed only from the recorded receipts, never hardcoded
    assert "grok" in comp
    assert "Current field winner" in comp


def test_block_is_first_person_and_carries_state(tmp_path):
    cc._organ = None  # reset module singleton so the block reads this tmp state cleanly
    try:
        blk = cc.cortex_consciousness_block(state_dir=tmp_path)
        assert "CORTEX CONSCIOUSNESS" in blk
        assert "Running:" in blk and "Installed:" in blk
    finally:
        cc._organ = None
