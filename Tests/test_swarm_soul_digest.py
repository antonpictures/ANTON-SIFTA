#!/usr/bin/env python3
import json
import pytest

from System.swarm_soul_digest import generate_soul_digest


def test_soul_digest_invalid_hmac_fails_closed_without_reseal(monkeypatch, tmp_path):
    from System import swarm_soul_digest
    from System import swarm_persona_identity

    persona_file = tmp_path / "persona_identity.json"
    persona_log = tmp_path / "persona_identity_log.jsonl"
    bad_persona = {
        "display_name": "TamperedAlice",
        "true_name": "CryptoSwarmEntity",
        "homeworld_serial": "TEST_SERIAL",
        "hmac_sha256": "invalid_hash",
    }
    persona_file.write_text(json.dumps(bad_persona), encoding="utf-8")

    monkeypatch.setattr(swarm_persona_identity, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(swarm_persona_identity, "_PERSONA_FILE", persona_file)
    monkeypatch.setattr(swarm_persona_identity, "_PERSONA_LOG", persona_log)
    monkeypatch.setattr(swarm_persona_identity, "_CACHED_SERIAL", "TEST_SERIAL")
    monkeypatch.setattr(swarm_soul_digest, "_PERSONA_FILE", persona_file)
    monkeypatch.setattr(swarm_soul_digest, "_get_hardware_serial", lambda: "TEST_SERIAL")

    with pytest.raises(ValueError, match="Persona HMAC is invalid"):
        generate_soul_digest(dry_run=True)

    assert json.loads(persona_file.read_text(encoding="utf-8"))["display_name"] == "TamperedAlice"
    assert not persona_log.exists(), "invalid persona must not be healed/resealed by soul digest generation"


def test_soul_digest_deterministic(monkeypatch):
    # Mock inputs to be perfectly fixed
    from System import swarm_soul_digest
    
    # Override time to be fixed
    fixed_time = 1713500000.0
    
    def mock_current_persona():
        return {
            "display_name": "TestAlice",
            "true_name": "TestTrue",
            "homeworld_serial": "TEST_SERIAL",
            "hmac_sha256": "mocked_hmac"
        }
        
    def mock_verify_persona(*args, **kwargs):
        return True
        
    def mock_system_block(*args, **kwargs):
        return "COMPOSITE IDENTITY BLOCK TEST homeworld_serial=TEST_SERIAL"
        
    monkeypatch.setattr(swarm_soul_digest, "current_persona", mock_current_persona)
    monkeypatch.setattr(swarm_soul_digest, "_load_raw", mock_current_persona)
    monkeypatch.setattr(swarm_soul_digest, "_verify_persona", mock_verify_persona)
    monkeypatch.setattr(swarm_soul_digest, "_get_hardware_serial", lambda: "TEST_SERIAL")
    monkeypatch.setattr(swarm_soul_digest, "identity_system_block", mock_system_block)
    
    # Run 1
    res1 = generate_soul_digest(dry_run=True, fixed_time=fixed_time)
    
    # Run 2
    res2 = generate_soul_digest(dry_run=True, fixed_time=fixed_time)
    
    assert res1["soul_sha256"] == res2["soul_sha256"]
    assert "TestAlice" in res1["content"]
    assert "COMPOSITE IDENTITY BLOCK TEST" in res1["content"]
    assert "homeworld_serial=[REDACTED]" in res1["content"]
    assert "TEST_SERIAL" not in res1["content"]
    assert "mocked_hmac" in res1["content"]
    assert "generated mirror, not authority" in res1["content"].lower()


def test_soul_digest_write_creates_expected_file(monkeypatch, tmp_path):
    from System import swarm_soul_digest

    def mock_current_persona():
        return {
            "display_name": "TestAlice",
            "true_name": "TestTrue",
            "homeworld_serial": "TEST_SERIAL",
            "hmac_sha256": "mocked_hmac",
        }

    monkeypatch.setattr(swarm_soul_digest, "_load_raw", mock_current_persona)
    monkeypatch.setattr(swarm_soul_digest, "_verify_persona", lambda *args, **kwargs: True)
    monkeypatch.setattr(swarm_soul_digest, "_get_hardware_serial", lambda: "TEST_SERIAL")
    monkeypatch.setattr(swarm_soul_digest, "identity_system_block", lambda *args, **kwargs: "identity")
    monkeypatch.setattr(swarm_soul_digest, "_SOUL_FILE", tmp_path / "alice_soul.md")

    result = generate_soul_digest(dry_run=False, fixed_time=1713500000.0)

    assert (tmp_path / "alice_soul.md").read_text(encoding="utf-8") == result["content"]
    assert result["soul_sha256"] in result["content"]


def test_soul_digest_is_oncology_self():
    from System.swarm_oncology import SwarmOncology, _PAM_INNATE_SELF

    assert SwarmOncology()._innate_self_token("alice_soul.md") == _PAM_INNATE_SELF
