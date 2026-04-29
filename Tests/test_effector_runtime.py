import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest
from System.swarm_effector_runtime import (
    EffectorRuntime,
    verify_receipt_row,
    replay_from_ledger,
    KIND_FS_WRITE
)

@pytest.fixture
def temp_env():
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        root = tdp / "root"
        root.mkdir()
        receipt_path = tdp / "effector_receipts.jsonl"
        undo_dir = tdp / "effector_undo"
        yield root, receipt_path, undo_dir

def test_commit_writes_file(temp_env):
    """1. commit writes file"""
    root, receipt_path, undo_dir = temp_env
    runtime = EffectorRuntime(root=root, receipt_path=receipt_path, undo_dir=undo_dir)
    
    action = {
        "kind": KIND_FS_WRITE,
        "rel_path": "test.txt",
        "content": "hello world",
        "mode": "create"
    }
    p = runtime.propose(action)
    sb = runtime.sandbox(p.action_id)
    assert sb["ok"] is True
    
    commit_res = runtime.commit(p.action_id)
    assert commit_res["ok"] is True
    
    target_file = root / "test.txt"
    assert target_file.exists()
    assert target_file.read_text() == "hello world"
    
    rec = runtime.receipt(p.action_id)
    assert rec is not None
    assert rec["phase"] == "COMMIT"
    assert rec["ok"] is True

def test_undo_restores_file(temp_env):
    """2. undo restores file"""
    root, receipt_path, undo_dir = temp_env
    runtime = EffectorRuntime(root=root, receipt_path=receipt_path, undo_dir=undo_dir)
    
    target_file = root / "test.txt"
    target_file.write_text("original content")
    
    action = {
        "kind": KIND_FS_WRITE,
        "rel_path": "test.txt",
        "content": "new content",
        "mode": "replace"
    }
    p = runtime.propose(action)
    runtime.commit(p.action_id)
    assert target_file.read_text() == "new content"
    
    undo_res = runtime.undo(p.action_id)
    assert undo_res["ok"] is True
    assert target_file.read_text() == "original content"
    
    rec = runtime.receipt(p.action_id)
    assert rec["phase"] == "UNDO"

def test_failed_action_writes_broken_receipt(temp_env):
    """3. failed action writes BROKEN receipt"""
    root, receipt_path, undo_dir = temp_env
    runtime = EffectorRuntime(root=root, receipt_path=receipt_path, undo_dir=undo_dir)
    
    target_file = root / "test.txt"
    target_file.write_text("existing")
    
    action = {
        "kind": KIND_FS_WRITE,
        "rel_path": "test.txt",
        "content": "conflict",
        "mode": "create" # will fail because file exists
    }
    p = runtime.propose(action)
    commit_res = runtime.commit(p.action_id)
    assert commit_res["ok"] is False
    assert commit_res["error"] == "create_conflict_exists"
    
    rec = runtime.receipt(p.action_id)
    assert rec is not None
    assert rec["phase"] == "BROKEN"

def test_double_commit_rejected(temp_env):
    """4. double commit rejected"""
    root, receipt_path, undo_dir = temp_env
    runtime = EffectorRuntime(root=root, receipt_path=receipt_path, undo_dir=undo_dir)
    
    action = {
        "kind": KIND_FS_WRITE,
        "rel_path": "test.txt",
        "content": "hello",
        "mode": "create"
    }
    p = runtime.propose(action)
    res1 = runtime.commit(p.action_id)
    assert res1["ok"] is True
    
    res2 = runtime.commit(p.action_id)
    assert res2["ok"] is False
    assert res2["error"] == "double_commit"

def test_replay_reconstructs_final_state(temp_env):
    """5. replay reconstructs final state"""
    root, receipt_path, undo_dir = temp_env
    runtime = EffectorRuntime(root=root, receipt_path=receipt_path, undo_dir=undo_dir)
    
    # Action 1: Create f1.txt
    p1 = runtime.propose({
        "kind": KIND_FS_WRITE,
        "rel_path": "f1.txt",
        "content": "f1 content",
        "mode": "create"
    })
    runtime.commit(p1.action_id)
    
    # Action 2: Create f2.txt
    p2 = runtime.propose({
        "kind": KIND_FS_WRITE,
        "rel_path": "f2.txt",
        "content": "f2 content",
        "mode": "create"
    })
    runtime.commit(p2.action_id)
    
    # Undo Action 1
    runtime.undo(p1.action_id)
    
    # Now clear the root directory to simulate a fresh replay
    shutil.rmtree(root)
    root.mkdir()
    
    # Replay
    replay_res = replay_from_ledger(root, receipt_path)
    assert replay_res["ok"] is True
    
    # Check filesystem
    file1 = root / "f1.txt"
    file2 = root / "f2.txt"
    assert not file1.exists()
    assert file2.exists()
    assert file2.read_text() == "f2 content"

def test_tampered_receipt_rejected(temp_env):
    """6. tampered receipt rejected"""
    root, receipt_path, undo_dir = temp_env
    runtime = EffectorRuntime(root=root, receipt_path=receipt_path, undo_dir=undo_dir)
    
    p = runtime.propose({
        "kind": KIND_FS_WRITE,
        "rel_path": "test.txt",
        "content": "hello",
        "mode": "create"
    })
    runtime.commit(p.action_id)
    
    rec = runtime.receipt(p.action_id)
    assert verify_receipt_row(rec) is True
    
    # Tamper with the row in the file
    lines = receipt_path.read_text().splitlines()
    tampered_lines = []
    for line in lines:
        row = json.loads(line)
        if row.get("action_id") == p.action_id:
            row["content_b64"] = "bad_base64"
        tampered_lines.append(json.dumps(row))
    receipt_path.write_text("\n".join(tampered_lines) + "\n")
    
    # Re-read
    tampered_rec = runtime.receipt(p.action_id)
    assert verify_receipt_row(tampered_rec) is False
