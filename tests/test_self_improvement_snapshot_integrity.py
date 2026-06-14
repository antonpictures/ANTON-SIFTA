"""C11 — corrupt snapshot refuses restore."""
from __future__ import annotations

from System.swarm_self_improvement_snapshot_integrity import (
    restore_from_snapshot_if_valid,
    verify_snapshot_integrity,
)


def test_corrupt_snapshot_refuses_restore(tmp_path):
    snap = tmp_path / "snap.py"
    target = tmp_path / "target.py"
    good = b"print('ok')\n"
    snap.write_bytes(good)
    sha = verify_snapshot_integrity(snap)["sha256"]
    snap.write_bytes(b"broken syntax {{{")
    bad_check = verify_snapshot_integrity(snap, expected_sha256=sha)
    assert bad_check["ok"] is False
    out = restore_from_snapshot_if_valid(snap, target, expected_sha256=sha)
    assert out["ok"] is False
    assert not out.get("restored")


def test_self_improvement_revert_refuses_corrupt_snapshot(tmp_path, monkeypatch):
    from System import swarm_self_improvement_loop as loop

    repo = tmp_path / "repo"
    target = repo / "System" / "tiny.py"
    target.parent.mkdir(parents=True)
    target.write_text("VALUE = 1\n", encoding="utf-8")
    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    monkeypatch.setattr(loop, "_repo_root", lambda: repo)

    proposal_id = "p-corrupt"
    loop.snapshot_before_apply(proposal_id, "System/tiny.py", state_dir=sd)
    target.write_text("VALUE = 2\n", encoding="utf-8")
    snap = sd / "self_improvement_snapshots" / proposal_id / "tiny.py"
    snap.write_text("CORRUPTED\n", encoding="utf-8")

    row = loop.revert_proposal(proposal_id, "System/tiny.py", state_dir=sd)
    assert row["ok"] is False
    assert row["integrity"]["reason"] == "sha_mismatch"
    assert target.read_text(encoding="utf-8") == "VALUE = 2\n"
