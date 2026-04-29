"""Safe effector runtime (filesystem v1) — execution law tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_effector_runtime as ser

CALLER_ID = "TEST_DOCTOR"


def _rt(tmp: Path) -> ser.EffectorRuntime:
    root = tmp / "root"
    ledger = tmp / "effector_receipts.jsonl"
    undo = tmp / "undo"
    trace = tmp / "ide_stigmergic_trace.jsonl"
    trace.write_text(json.dumps({"doctor": CALLER_ID, "trace_id": "trace-test-1"}) + "\n", encoding="utf-8")
    return ser.EffectorRuntime(
        root,
        receipt_path=ledger,
        undo_dir=undo,
        registration_trace_path=trace,
        default_caller_id=CALLER_ID,
    )


def test_commit_writes_file(tmp_path: Path) -> None:
    rt = _rt(tmp_path)
    p = rt.propose(
        {"kind": "fs_write", "rel_path": "a/b.txt", "content": "hello", "mode": "create"}
    )
    assert "a/b.txt" in rt.preview(p.action_id) and "(5 bytes)" in rt.preview(p.action_id)
    out = rt.commit(p.action_id)
    assert out["ok"] is True
    assert (tmp_path / "root" / "a" / "b.txt").read_text() == "hello"


def test_undo_restores_file(tmp_path: Path) -> None:
    rt = _rt(tmp_path)
    path = tmp_path / "root" / "x.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ORIG", encoding="utf-8")

    p = rt.propose(
        {
            "kind": "fs_write",
            "rel_path": "x.txt",
            "content": "NEW",
            "mode": "replace",
        }
    )
    assert rt.commit(p.action_id)["ok"] is True
    assert path.read_text() == "NEW"
    assert rt.undo(p.action_id)["ok"] is True
    assert path.read_text() == "ORIG"


def test_failed_action_writes_broken_receipt(tmp_path: Path) -> None:
    rt = _rt(tmp_path)
    f = tmp_path / "root" / "c.txt"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("exists", encoding="utf-8")

    p = rt.propose(
        {
            "kind": "fs_write",
            "rel_path": "c.txt",
            "content": "nope",
            "mode": "create",
        }
    )
    out = rt.commit(p.action_id)
    assert out["ok"] is False
    row = rt.receipt(p.action_id)
    assert row is not None
    assert row.get("phase") == ser.PHASE_BROKEN
    assert row.get("ok") is False
    assert row.get("status") == "rejected"
    assert row.get("truth_note")
    assert ser.verify_receipt_row(row) is True


def test_double_commit_rejected(tmp_path: Path) -> None:
    rt = _rt(tmp_path)
    p = rt.propose(
        {"kind": "fs_write", "rel_path": "d.txt", "content": "one", "mode": "create"}
    )
    assert rt.commit(p.action_id)["ok"] is True
    second = rt.commit(p.action_id)
    assert second["ok"] is False
    assert second["error"] == "double_commit"
    tail = rt.receipt(p.action_id)
    assert tail.get("phase") == ser.PHASE_BROKEN


def test_replay_reconstructs_final_state(tmp_path: Path) -> None:
    rt = _rt(tmp_path)
    p1 = rt.propose(
        {"kind": "fs_write", "rel_path": "r.txt", "content": "A", "mode": "create"}
    )
    assert rt.commit(p1.action_id)["ok"] is True
    p2 = rt.propose(
        {"kind": "fs_write", "rel_path": "r.txt", "content": "B", "mode": "replace"}
    )
    assert rt.commit(p2.action_id)["ok"] is True
    assert rt.undo(p2.action_id)["ok"] is True

    fresh_root = tmp_path / "replay_root"
    fresh_root.mkdir()
    res = ser.replay_from_ledger(fresh_root, rt.receipt_path)
    assert res["ok"] is True
    assert (fresh_root / "r.txt").read_text() == "A"


def test_tampered_receipt_rejected_on_replay(tmp_path: Path) -> None:
    rt = _rt(tmp_path)
    p = rt.propose(
        {"kind": "fs_write", "rel_path": "t.txt", "content": "ok", "mode": "create"}
    )
    assert rt.commit(p.action_id)["ok"] is True

    raw_lines = rt.receipt_path.read_text(encoding="utf-8").strip().splitlines()
    row = json.loads(raw_lines[0])
    row["integrity"] = "aa" * 32
    raw_lines[0] = json.dumps(row, separators=(",", ":"))
    rt.receipt_path.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")

    fresh = tmp_path / "tamper_root"
    fresh.mkdir()
    res = ser.replay_from_ledger(fresh, rt.receipt_path)
    assert "integrity_fail" in res["warnings"]
    assert not (fresh / "t.txt").exists()


def test_propose_rejects_path_escape(tmp_path: Path) -> None:
    rt = _rt(tmp_path)
    with pytest.raises(ValueError, match="path_escape"):
        rt.propose(
            {
                "kind": "fs_write",
                "rel_path": "../outside.txt",
                "content": "x",
                "mode": "create",
            }
        )


def test_receipt_returns_last_row_for_action(tmp_path: Path) -> None:
    rt = _rt(tmp_path)
    aid = "fixed-id-1"
    p = rt.propose(
        {
            "action_id": aid,
            "kind": "fs_write",
            "rel_path": "z.txt",
            "content": "z",
            "mode": "create",
        }
    )
    assert p.action_id == aid
    assert rt.commit(aid)["ok"] is True
    assert rt.undo(aid)["ok"] is True
    last = rt.receipt(aid)
    assert last.get("phase") == ser.PHASE_UNDO


def test_anonymous_caller_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    ledger = tmp_path / "effector_receipts.jsonl"
    undo = tmp_path / "undo"
    rt = ser.EffectorRuntime(root, receipt_path=ledger, undo_dir=undo)

    with pytest.raises(ValueError, match="anonymous_caller_refused"):
        rt.propose({"kind": "fs_write", "rel_path": "anon.txt", "content": "x", "mode": "create"})


def test_unregistered_caller_rejected(tmp_path: Path) -> None:
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    trace.write_text(json.dumps({"doctor": CALLER_ID}) + "\n", encoding="utf-8")
    rt = ser.EffectorRuntime(
        tmp_path / "root",
        receipt_path=tmp_path / "effector_receipts.jsonl",
        undo_dir=tmp_path / "undo",
        registration_trace_path=trace,
    )

    with pytest.raises(ValueError, match="unregistered_caller_refused"):
        rt.propose(
            {
                "caller_id": "NOT_REGISTERED",
                "kind": "fs_write",
                "rel_path": "bad.txt",
                "content": "x",
                "mode": "create",
            }
        )


def test_undo_rejects_unregistered_acting_caller(tmp_path: Path) -> None:
    rt = _rt(tmp_path)
    p = rt.propose(
        {"kind": "fs_write", "rel_path": "owned.txt", "content": "owned", "mode": "create"}
    )
    assert rt.commit(p.action_id)["ok"] is True

    out = rt.undo(p.action_id, caller_id="NOT_REGISTERED")
    assert out["ok"] is False
    assert out["error"] == "unregistered_caller_refused"
    assert (tmp_path / "root" / "owned.txt").read_text() == "owned"
    row = rt.receipt(p.action_id)
    assert row.get("phase") == ser.PHASE_BROKEN
    assert row.get("status") == "rejected"
