import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from System.swarm_network_membrane import SwarmNetworkMembrane

@pytest.fixture
def membrane_env():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)

def test_receptor_rejection(membrane_env):
    membrane = SwarmNetworkMembrane(root=str(membrane_env))
    
    # Try to access a non-whitelisted domain
    res = membrane.transport("https://evil-hacker.com/malware")
    
    assert res["ok"] is False
    assert res["error"] == "receptor_rejected"
    assert res["domain"] == "evil-hacker.com"

@patch("urllib.request.urlopen")
def test_active_transport_charge(mock_urlopen, membrane_env):
    # Mock a safe response
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"hello": "world"}'
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    membrane = SwarmNetworkMembrane(root=str(membrane_env))
    
    # Ensure starting balance is 1000.0
    wallet = json.loads(membrane.stgm_wallet.read_text())
    assert wallet["balance"] == 1000.0
    
    # Perform a valid request
    res = membrane.transport("https://api.openai.com/v1/models")
    
    assert res["ok"] is True
    assert "world" in res["content"]
    
    # Verify ATP was charged
    wallet_after = json.loads(membrane.stgm_wallet.read_text())
    assert wallet_after["balance"] == 999.0
    
    # Verify ledger trace
    with open(membrane.ledger, "r") as f:
        traces = f.readlines()
        assert len(traces) == 1
        trace = json.loads(traces[0])
        assert trace["stgm_cost"] == 1.0
        assert trace["status"] == "SUCCESS"

@patch("urllib.request.urlopen")
def test_macrophage_lysis_on_pathogen(mock_urlopen, membrane_env):
    # Mock a malicious response containing a script tag
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'<html><script>alert("XSS")</script></html>'
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    membrane = SwarmNetworkMembrane(root=str(membrane_env))
    
    # Perform a valid request to a trusted domain but with malicious payload
    res = membrane.transport("https://github.com/some/repo")
    
    assert res["ok"] is False
    assert res["error"] == "payload_lysed"
    
    # Verify ledger trace marks it as LYSED
    with open(membrane.ledger, "r") as f:
        trace = json.loads(f.readlines()[0])
        assert trace["status"] == "LYSED"
        assert trace["lysed"] is True
        assert trace["reason"] == "pathogen_detected_or_density_exceeded"

@patch("urllib.request.urlopen")
def test_macrophage_lysis_on_density_limit(mock_urlopen, membrane_env):
    # Mock an oversized response (501KB)
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'A' * 500_001
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    membrane = SwarmNetworkMembrane(root=str(membrane_env))
    
    res = membrane.transport("https://github.com/some/repo")
    
    assert res["ok"] is False
    assert res["error"] == "payload_lysed"
