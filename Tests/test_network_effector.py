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
    WhitelistRedirectHandler,
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

def test_whitelist_logic(temp_env):
    receipt_path = temp_env
    runtime = NetworkEffectorRuntime(
        receipt_path=receipt_path,
        default_caller_id="tester",
        require_registered_caller=False
    )
    
    # Allowed
    p = runtime.propose({
        "kind": KIND_NETWORK_READ,
        "url": "https://huggingface.co/foo"
    })
    assert p.url == "https://huggingface.co/foo"
    
    # Rejected
    with pytest.raises(ValueError, match="domain_not_whitelisted"):
        runtime.propose({
            "kind": KIND_NETWORK_READ,
            "url": "https://evil.com/malware"
        })

@patch("System.swarm_network_effector._build_opener")
def test_sandbox_and_commit(mock_build_opener, temp_env):
    receipt_path = temp_env
    
    # Mock the opener and its response
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
    
    action = {
        "kind": KIND_NETWORK_READ,
        "url": "https://api.openai.com/v1/models"
    }
    p = runtime.propose(action)
    
    # Sandbox (HEAD)
    sb = runtime.sandbox(p.action_id)
    assert sb["ok"] is True
    assert sb["status_code"] == 200
    # Check that HEAD was called
    call_args = mock_opener.open.call_args[0][0]
    assert call_args.method == "HEAD"
    
    # Commit (GET)
    commit_res = runtime.commit(p.action_id)
    assert commit_res["ok"] is True
    assert commit_res["status_code"] == 200
    assert commit_res["content"] == b'{"status": "alive"}'
    
    # Verify GET was called
    call_args2 = mock_opener.open.call_args[0][0]
    assert call_args2.method == "GET"
    
    # Check receipt
    rec = runtime.receipt(p.action_id)
    assert rec is not None
    assert rec["phase"] == "COMMIT"
    assert rec["ok"] is True
    assert rec["content_sha256"] == "09cff42e0cbfe11915a333cc5d2b988b2e364cc939c3aa2102688933499e437b" # sha256 of the mock data

@patch("System.swarm_network_effector._build_opener")
def test_sandbox_failure_writes_broken_receipt(mock_build_opener, temp_env):
    receipt_path = temp_env
    
    mock_opener = MagicMock()
    # Simulate a 404 in sandbox
    mock_opener.open.side_effect = urllib.error.HTTPError(
        "https://huggingface.co/missing", 404, "Not Found", {}, None
    )
    mock_build_opener.return_value = mock_opener

    runtime = NetworkEffectorRuntime(
        receipt_path=receipt_path,
        default_caller_id="tester",
        require_registered_caller=False
    )
    
    p = runtime.propose({
        "kind": KIND_NETWORK_READ,
        "url": "https://huggingface.co/missing"
    })
    
    commit_res = runtime.commit(p.action_id)
    assert commit_res["ok"] is False
    assert "http_error_404" in commit_res["error"]
    
    rec = runtime.receipt(p.action_id)
    assert rec is not None
    assert rec["phase"] == "BROKEN"

def test_whitelist_redirect_handler():
    handler = WhitelistRedirectHandler()
    req = MagicMock()
    req.get_method.return_value = "GET"
    req.full_url = "https://huggingface.co/orig"
    fp = MagicMock()
    
    # Redirect to another whitelisted domain should not raise
    try:
        handler.redirect_request(req, fp, 302, "Found", {}, "https://developer.nvidia.com/foo")
    except Exception as e:
        pytest.fail(f"Unexpected exception raised: {e}")
        
    # Redirect to non-whitelisted domain should raise
    with pytest.raises(urllib.error.URLError, match="redirect_domain_escape:evil.com"):
        handler.redirect_request(req, fp, 302, "Found", {}, "https://evil.com/steal")
