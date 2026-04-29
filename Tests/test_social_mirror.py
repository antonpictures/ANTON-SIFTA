import json
import tempfile
from pathlib import Path

import pytest
from System.swarm_social_mirror import SwarmSocialMirror, SocialMirrorEvent
from System.whatsapp_bridge_autopilot import send_whatsapp

@pytest.fixture
def mirror_env():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)

def test_social_mirror_blocks_inbound_observation_reply(mirror_env):
    mirror = SwarmSocialMirror(state_dir=str(mirror_env))
    
    # Alice observes a message and tries to reply autonomously without explicit consent
    event = SocialMirrorEvent(
        direction="outbound",
        speaker="alice",
        audience="contact",
        action="send_reply",
        consent="none"
    )
    
    allowed, reason = mirror.may_send_whatsapp(event)
    
    assert allowed is False
    assert reason == "rejected_requires_owner_explicit_consent"

def test_social_mirror_allows_explicit_owner_consent(mirror_env):
    mirror = SwarmSocialMirror(state_dir=str(mirror_env))
    
    # Owner explicitly asks Alice to send a message
    event = SocialMirrorEvent(
        direction="outbound",
        speaker="alice",
        audience="contact",
        action="send_reply",
        consent="owner_explicit"
    )
    
    allowed, reason = mirror.may_send_whatsapp(event)
    
    assert allowed is True
    assert reason == "allowed"

def test_whatsapp_bridge_integration(monkeypatch, mirror_env):
    # Patch the state dir by patching the default arg or the constructor
    def mock_init(self, state_dir=str(mirror_env)):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = self.state_dir / "social_mirror.jsonl"
        
    monkeypatch.setattr("System.swarm_social_mirror.SwarmSocialMirror.__init__", mock_init)
    
    # Mock resolve target so it doesn't fail on unknown contact
    monkeypatch.setattr("System.whatsapp_bridge_autopilot._resolve_target", lambda t: "1234567890@s.whatsapp.net")
    
    # Attempt an autonomous send with no consent
    res = send_whatsapp(target="Daniel", text="Hello", source="alice_autonomous")
    
    assert res["ok"] is False
    assert res["status"] == "BLOCKED_SOCIAL_MIRROR"
    assert "rejected_requires_owner_explicit_consent" in res["result"]

    # Attempt a send WITH owner consent
    # We mock urlopen to raise URLError so it doesn't actually hit the local bridge
    # But it passes the social mirror!
    import urllib.error
    def mock_urlopen(*args, **kwargs):
        raise urllib.error.URLError("mocked")
    
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    
    res_ok = send_whatsapp(target="Daniel", text="Hello", source="owner_explicit")
    
    # It passed the social mirror, but failed at bridge injection (which is expected)
    assert res_ok["status"] == "BRIDGE_UNREACHABLE"
