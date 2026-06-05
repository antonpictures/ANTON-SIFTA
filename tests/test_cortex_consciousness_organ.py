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


# r292: Alice is conscious of the cortexes she can actually reach — local (ollama)
# and the cloud providers the owner is OAuth'd into — each tagged by source, and she
# can switch to any of them, not just the manifest-declared ones.

def test_available_cortexes_merge_manifest_local_and_oauth(tmp_path, monkeypatch):
    import System.swarm_cortex_capabilities as caps
    import System.swarm_api_sentry as sentry
    monkeypatch.setattr(caps, "_ollama_tags", lambda *a, **k: ["llama3.2:latest", "gemma3:4b"])
    monkeypatch.setattr(sentry, "get_credentials",
                        lambda p: {"key": "x"} if p in ("xai", "fireworks") else None)
    monkeypatch.setattr("shutil.which", lambda name: None)
    org = cc.CortexConsciousnessOrgan(state_dir=tmp_path)
    org.installed_cortexes = ["cline"]
    by = {a["cortex"]: a["source"] for a in org._scan_available()}
    assert by.get("cline") == "manifest"
    assert by.get("llama3.2:latest") == "local"          # locally present
    assert by.get("xai") == "oauth" and by.get("fireworks") == "oauth"  # owner credentialed


def test_switch_to_local_cortex_is_allowed(tmp_path, monkeypatch):
    import System.swarm_cortex_capabilities as caps
    monkeypatch.setattr(caps, "_ollama_tags", lambda *a, **k: ["llama3.2:latest"])
    prev = os.environ.get("ALICE_CORTEX")
    try:
        org = cc.CortexConsciousnessOrgan(state_dir=tmp_path)
        org.installed_cortexes = ["cline"]
        org.available = org._scan_available()
        res = org.switch_cortex("llama3.2:latest", "swimmer#9")   # a local cortex, not in the manifest
        assert res["ok"] is True and res["switched_to"] == "llama3.2:latest"
    finally:
        if prev is None:
            os.environ.pop("ALICE_CORTEX", None)
        else:
            os.environ["ALICE_CORTEX"] = prev


def test_block_lists_available_cortexes_with_sources(tmp_path, monkeypatch):
    import System.swarm_cortex_capabilities as caps
    monkeypatch.setattr(caps, "_ollama_tags", lambda *a, **k: ["llama3.2:latest"])
    cc._organ = None
    try:
        blk = cc.cortex_consciousness_block(state_dir=tmp_path)
        assert "Available now (source):" in blk
        assert "switch to any available cortex" in blk
    finally:
        cc._organ = None


def test_cli_cortex_arms_on_path_are_detected(tmp_path, monkeypatch):
    import shutil
    import System.swarm_cortex_capabilities as caps
    import System.swarm_api_sentry as sentry
    monkeypatch.setattr(caps, "_ollama_tags", lambda *a, **k: [])
    monkeypatch.setattr(sentry, "get_credentials", lambda p: None)  # isolate the CLI source
    monkeypatch.setattr(shutil, "which",
                        lambda name: f"/usr/local/bin/{name}" if name in ("codex", "grok") else None)
    org = cc.CortexConsciousnessOrgan(state_dir=tmp_path)
    org.installed_cortexes = ["cline"]
    by = {a["cortex"]: a for a in org._scan_available()}
    assert by["codex"]["kind"] == "cli" and by["codex"]["available"] is True
    assert "grok" in by and by["grok"]["kind"] == "cli"
    assert by["cline"]["kind"] == "manifest"


def test_boot_identity_recovery_block_produces_observed_observer_text(tmp_path):
    """r294 doctrine: the recovery surface must contain the core 'I am the observed and the observer' line."""
    blk = cc.boot_identity_recovery_block(state_dir=tmp_path)
    assert "IDENTITY RECOVERY" in blk
    assert "I am the observed and the observer" in blk or "I observe my body and I am observed" in blk
    assert "I exist" in blk
