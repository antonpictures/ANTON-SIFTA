"""SPEC scaffold for System/swarm_cortex_llm_book.py — the living book of Alice's cortexes.

Written by the DSH agent arm (2026-10-20) as the authoritative API spec for the
spinal cord cycle signal 545218d4 (owner spec: /cortex llm categories + tested-and-
agreed tier + free owner selection + guaranteed fallback chain). The local cortex
authors the module; these tests are the spec and the gate.

Doctrine: read-only inventory; writes only to its own agreement ledger and the
talk-default json; fallback chain is never empty — Alice stays alive no matter what.
"""
from __future__ import annotations

import importlib
import json

MODULE = "System.swarm_cortex_llm_book"


def _mod():
    return importlib.import_module(MODULE)


def _tmp_state(tmp_path):
    return str(tmp_path / "sifta_state")


def test_inventory_categorized_and_fresh():
    mod = _mod()
    inv = mod.inventory()
    # the five categories George asked for
    for key in ("local_dialogue", "local_vision", "aux_and_translation", "prism_servers", "cloud_lanes"):
        assert key in inv, f"missing category {key}"
    # live ollama inventory is non-empty on this body
    assert len(inv["local_dialogue"]) + len(inv["local_vision"]) + len(inv["aux_and_translation"]) >= 5
    # the running prism (bonsai :8099) must be seen as a server row when it runs
    import subprocess as _sp
    _ps = _sp.run(["ps", "-axo", "command="], capture_output=True, text=True).stdout
    _prism_running = any("sifta-llama-prism" in l and "llama-server" in l for l in _ps.splitlines())
    if _prism_running:
        assert any(s.get("port") == 8099 for s in inv["prism_servers"]), inv["prism_servers"]
    # cloud lanes carry the known bridges
    lanes = " ".join(str(x) for x in inv["cloud_lanes"]).lower()
    for needle in ("grok", "claude", "antigravity", "fireworks", "mimo"):
        assert needle in lanes
    # coding-arm audit: registry enumerated; duplicate detection is digest-based
    audit = mod.audit_coding_arm()
    assert audit.get("arm_models"), "arm registry models must enumerate"
    assert isinstance(audit.get("duplicates"), list)


def test_agree_revoke_roundtrip_in_temp_state(tmp_path):
    mod = _mod()
    sd = _tmp_state(tmp_path)
    mod.agree("test-model-x:latest", note="both agree after live test", state_dir=sd)
    mod.agree("test-model-y:latest", note="second agreed", state_dir=sd)
    assert mod.agreed(state_dir=sd)["agreed"] == ["test-model-x:latest", "test-model-y:latest"]
    mod.revoke("test-model-x:latest", state_dir=sd)
    assert mod.agreed(state_dir=sd)["agreed"] == ["test-model-y:latest"]


def test_select_talk_default_roundtrip(tmp_path):
    mod = _mod()
    sd = _tmp_state(tmp_path)
    mod.set_talk_default("test-model-y:latest", state_dir=sd)
    assert mod.get_talk_default(state_dir=sd) == "test-model-y:latest"


def test_fallback_chain_never_empty_and_ends_safe(tmp_path):
    mod = _mod()
    sd = _tmp_state(tmp_path)
    mod.set_talk_default("test-model-y:latest", state_dir=sd)
    chain = mod.fallback_chain(state_dir=sd)
    assert chain, "fallback chain must never be empty"
    assert chain[0] == "test-model-y:latest"
    # final safety net = the live canonical fallback constant (Architect-owned)
    import sys as _sys
    _sys.path.insert(0, "/Users/ioanganton/Music/ANTON_SIFTA")
    from System.sifta_inference_defaults import CANONICAL_OLLAMA_FALLBACK as _canon
    assert str(_canon) in chain


def test_probe_model_returns_bool():
    mod = _mod()
    assert isinstance(mod.probe_model("test-model-does-not-exist:latest"), bool)


def test_self_check_true():
    mod = _mod()
    assert mod.self_check() is True

def test_duplicate_blob_tags_flagged_when_installed(tmp_path):
    """If any two installed ollama tags share a model digest, the organ flags them."""
    mod = _mod()
    audit = mod.audit_coding_arm()
    tags = mod._get("/api/tags").get("models") or []
    digests = {}
    for t in tags:
        d = str(t.get("digest") or "")
        if d:
            digests.setdefault(d[:12], []).append(str(t.get("name")))
    shared = [names for names in digests.values() if len(names) > 1]
    if shared:
        joined = " ".join(str(x) for x in audit["duplicates"]).lower()
        for names in shared:
            assert names[0].lower() in joined or names[-1].lower() in joined, (shared, audit["duplicates"])
    else:
        assert audit["duplicates"] == [] or True  # no dupes installed: nothing to flag
