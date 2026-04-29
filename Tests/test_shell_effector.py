import json
import tempfile
from pathlib import Path

import pytest
from System.swarm_shell_effector import (
    ShellEffectorRuntime,
    is_command_whitelisted,
    verify_receipt_row,
    KIND_SHELL_EXEC
)

@pytest.fixture
def temp_env():
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        root = tdp / "root"
        root.mkdir()
        receipt_path = tdp / "effector_receipts.jsonl"
        yield root, receipt_path

def test_whitelist_logic():
    assert is_command_whitelisted(["git", "status"]) is True
    assert is_command_whitelisted(["git", "diff", "HEAD"]) is True
    assert is_command_whitelisted(["git", "diff", "--ext-diff"]) is False
    assert is_command_whitelisted(["pytest", "tests/"]) is True
    assert is_command_whitelisted(["python3", "-m", "pytest", "tests/"]) is True
    assert is_command_whitelisted(["python3", "-m", "py_compile", "file.py"]) is True
    assert is_command_whitelisted(["rm", "-rf", "/"]) is False
    assert is_command_whitelisted(["python3", "-m", "http.server"]) is False
    assert is_command_whitelisted([]) is False

def test_shell_commit_writes_receipt_and_runs(temp_env):
    root, receipt_path = temp_env
    # Let's write a small py file to py_compile
    test_py = root / "test_file.py"
    test_py.write_text("print('hello')", encoding="utf-8")

    runtime = ShellEffectorRuntime(
        root=root, 
        receipt_path=receipt_path, 
        default_caller_id="tester",
        require_registered_caller=False
    )
    
    action = {
        "kind": KIND_SHELL_EXEC,
        "command": ["python3", "-m", "py_compile", "test_file.py"]
    }
    p = runtime.propose(action)
    sb = runtime.sandbox(p.action_id)
    assert sb["ok"] is True
    
    commit_res = runtime.commit(p.action_id)
    assert commit_res["ok"] is True
    assert commit_res["exit_code"] == 0
    
    # Check if pyc was created (in __pycache__ usually)
    pycache = root / "__pycache__"
    assert pycache.exists()
    
    rec = runtime.receipt(p.action_id)
    assert rec is not None
    assert rec["phase"] == "COMMIT"
    assert rec["ok"] is True
    assert "stdout_b64" in rec
    assert verify_receipt_row(rec) is True

def test_failed_sandbox_writes_broken_receipt(temp_env):
    root, receipt_path = temp_env
    runtime = ShellEffectorRuntime(
        root=root, 
        receipt_path=receipt_path, 
        default_caller_id="tester",
        require_registered_caller=False
    )
    
    # Command not whitelisted should fail in propose
    action = {
        "kind": KIND_SHELL_EXEC,
        "command": ["rm", "-rf", "/"]
    }
    with pytest.raises(ValueError, match="command_not_whitelisted"):
        runtime.propose(action)

def test_double_commit_rejected(temp_env):
    root, receipt_path = temp_env
    runtime = ShellEffectorRuntime(
        root=root, 
        receipt_path=receipt_path, 
        default_caller_id="tester",
        require_registered_caller=False
    )
    
    action = {
        "kind": KIND_SHELL_EXEC,
        "command": ["git", "status"]
    }
    p = runtime.propose(action)
    res1 = runtime.commit(p.action_id)
    assert res1["ok"] is True
    
    res2 = runtime.commit(p.action_id)
    assert res2["ok"] is False
    assert res2["error"] == "double_commit"
    
    # The last receipt should be broken
    rec = runtime.receipt(p.action_id)
    assert rec["phase"] == "BROKEN"

def test_undo_not_supported(temp_env):
    root, receipt_path = temp_env
    runtime = ShellEffectorRuntime(
        root=root, 
        receipt_path=receipt_path, 
        default_caller_id="tester",
        require_registered_caller=False
    )
    
    action = {
        "kind": KIND_SHELL_EXEC,
        "command": ["git", "status"]
    }
    p = runtime.propose(action)
    runtime.commit(p.action_id)
    
    undo_res = runtime.undo(p.action_id)
    assert undo_res["ok"] is False
    assert undo_res["error"] == "shell_exec_not_undoable"

    rec = runtime.receipt(p.action_id)
    assert rec["phase"] == "BROKEN"
