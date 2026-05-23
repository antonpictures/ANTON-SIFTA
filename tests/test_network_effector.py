import json
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from System.swarm_network_effector import (
    KIND_NETWORK_READ,
    NetworkEffectorRuntime,
    MembraneRedirectHandler,
    extract_domain,
    verify_receipt_row,
)

@pytest.fixture
def temp_env():
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        receipt_path = tdp / "network_receipts.jsonl"
        yield receipt_path

def test_extract_domain():
    assert extract_domain("https://huggingface.co/models") == "huggingface.co"
    assert extract_domain("http://api.openai.com:8080/v1/chat") == "api.openai.com"
    assert extract_domain("https://developer.nvidia.com") == "developer.nvidia.com"

def test_default_trusted_domain(temp_env):
    receipt_path = temp_env
    runtime = NetworkEffectorRuntime(
        receipt_path=receipt_path,
        default_caller_id="tester",
        require_registered_caller=False
    )
    
    p = runtime.propose({
        "kind": KIND_NETWORK_READ,
        "url": "https://huggingface.co/foo",
        "method": "GET"
    })
    assert p.trust == "TRUSTED"
    
def test_unknown_domain_starts_quarantine(temp_env):
    receipt_path = temp_env
    runtime = NetworkEffectorRuntime(
        receipt_path=receipt_path,
        default_caller_id="tester",
        require_registered_caller=False
    )
    
    p = runtime.propose({
        "kind": KIND_NETWORK_READ,
        "url": "https://unknown.com/foo",
        "method": "GET"
    })
    assert p.trust == "QUARANTINE"
    
@patch("urllib.request.build_opener")
def test_quarantine_requires_probe(mock_build_opener, temp_env):
    receipt_path = temp_env
    runtime = NetworkEffectorRuntime(
        receipt_path=receipt_path,
        default_caller_id="tester",
        require_registered_caller=False
    )
    
    p = runtime.propose({
        "kind": KIND_NETWORK_READ,
        "url": "https://unknown.com/foo",
        "method": "GET"
    })
    
    commit_res = runtime.commit(p.action_id)
    assert commit_res["ok"] is False
    assert commit_res["error"] == "quarantine_requires_successful_probe_first"

@patch("urllib.request.build_opener")
def test_adaptive_trust_upgrade(mock_build_opener, temp_env):
    receipt_path = temp_env
    
    # Mock successful responses
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.read.return_value = b'{"status": "alive"}'
    
    mock_opener = MagicMock()
    mock_opener.open.return_value = mock_resp
    mock_build_opener.return_value = mock_opener

    runtime = NetworkEffectorRuntime(
        receipt_path=receipt_path,
        default_caller_id="tester",
        require_registered_caller=False
    )
    
    url = "https://unknown.com/api"
    
    # Needs 3 successful HEAD requests to earn TRUSTED
    for i in range(3):
        p = runtime.propose({"kind": KIND_NETWORK_READ, "url": url, "method": "GET"})
        assert p.trust == "QUARANTINE"
        sb = runtime.sandbox(p.action_id)
        assert sb["ok"] is True
        
        # Check trust file
        trust = json.loads(runtime.trust_file.read_text())
        assert trust["unknown.com"]["successes"] == i + 1
        
        # We must commit or cancel. Since we can't GET yet, we just ignore the action.
        # But actually after 3 successes it becomes TRUSTED!

    # 4th proposal should be TRUSTED!
    p4 = runtime.propose({"kind": KIND_NETWORK_READ, "url": url, "method": "GET"})
    assert p4.trust == "TRUSTED"
    
    # Now we can commit a GET
    commit_res = runtime.commit(p4.action_id)
    assert commit_res["ok"] is True
    assert commit_res["status_code"] == 200
    assert commit_res["content"] == b'{"status": "alive"}'

    # Check receipt
    rec = runtime.receipt(p4.action_id)
    assert rec is not None
    assert rec["phase"] == "COMMIT"
    assert rec["ok"] is True
    assert rec["domain"] == "unknown.com"

@patch("urllib.request.build_opener")
def test_sandbox_failure_does_not_upgrade(mock_build_opener, temp_env):
    receipt_path = temp_env
    
    mock_opener = MagicMock()
    mock_opener.open.side_effect = urllib.error.HTTPError(
        "https://unknown.com/missing", 404, "Not Found", {}, None
    )
    mock_build_opener.return_value = mock_opener

    runtime = NetworkEffectorRuntime(
        receipt_path=receipt_path,
        default_caller_id="tester",
        require_registered_caller=False
    )
    
    p = runtime.propose({"kind": KIND_NETWORK_READ, "url": "https://unknown.com/missing"})
    sb = runtime.sandbox(p.action_id)
    assert sb["ok"] is False
    
    trust = json.loads(runtime.trust_file.read_text())
    assert trust["unknown.com"]["failures"] == 1
    assert trust["unknown.com"]["trust"] == "QUARANTINE"

def test_membrane_redirect_handler(temp_env):
    receipt_path = temp_env
    runtime = NetworkEffectorRuntime(
        receipt_path=receipt_path,
        default_caller_id="tester",
        require_registered_caller=False
    )
    
    handler = MembraneRedirectHandler(runtime)
    req = MagicMock()
    req.get_method.return_value = "GET"
    req.full_url = "https://huggingface.co/orig"
    fp = MagicMock()
    
    # Redirect to another TRUSTED domain should not raise
    try:
        handler.redirect_request(req, fp, 302, "Found", {}, "https://developer.nvidia.com/foo")
    except Exception as e:
        pytest.fail(f"Unexpected exception raised: {e}")
        
    # Redirect to QUARANTINE domain should raise
    with pytest.raises(urllib.error.URLError, match="redirect_trust_escape:evil.com is QUARANTINE"):
        handler.redirect_request(req, fp, 302, "Found", {}, "https://evil.com/steal")


def test_propose_domain_hint_append_only(temp_env):
    receipt_path = temp_env
    runtime = NetworkEffectorRuntime(
        receipt_path=receipt_path,
        default_caller_id="tester",
        require_registered_caller=False,
    )
    runtime.propose_domain_hint("somedocs.example", note="mirror for weights")
    prop_path = runtime.trust_file.parent / "network_domain_proposals.jsonl"
    row = json.loads(prop_path.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["kind"] == "DOMAIN_HINT"
    assert row["domain"] == "somedocs.example"
