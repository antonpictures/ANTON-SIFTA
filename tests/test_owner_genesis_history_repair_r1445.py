from __future__ import annotations

import json
from pathlib import Path


def _full_scar(owner: str = "Ioan George Anton") -> dict:
    return {
        "event": "OWNER_GENESIS",
        "version": 1,
        "ts": 123.0,
        "silicon": "GTH4921YP3",
        "owner_name": owner,
        "ai_display_name": "Alice",
        "photo_hash": "photo_hash",
        "genesis_anchor": "anchor_hash",
        "extra": {},
        "generation": 1,
        "status": "ACTIVE",
        "sig": "valid_sig",
    }


def test_kernel_owner_name_falls_back_to_history_when_current_is_degraded(tmp_path, monkeypatch):
    from System import swarm_kernel_identity as kid

    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(kid, "_STATE", state)
    monkeypatch.setattr(kid, "_GENESIS_FILE", state / "owner_genesis.json")
    monkeypatch.setattr(kid, "_GENESIS_LOG", state / "owner_genesis_history.jsonl")

    (state / "owner_genesis.json").write_text(
        json.dumps({
            "schema": "OWNER_GENESIS_V1",
            "serial_number": "GTH4921YP3",
            "hardware_model": "MacBook Pro M5",
            "created_ts": 1.0,
        }),
        encoding="utf-8",
    )
    (state / "owner_genesis_history.jsonl").write_text(
        json.dumps(_full_scar("ioan george anton")) + "\n",
        encoding="utf-8",
    )

    assert kid.owner_name() == "Ioan George Anton"
    assert kid.owner_display_name() == "Ioan George Anton"
    assert kid.owner_chat_turn_label(default="You") == "Ioan"


def test_verify_genesis_repairs_degraded_current_from_signed_history(tmp_path, monkeypatch):
    from System import owner_genesis as og

    state = tmp_path / ".sifta_state"
    owner_dir = tmp_path / "owner_genesis"
    state.mkdir()
    owner_dir.mkdir()
    (owner_dir / "genesis_photo.jpg").write_text("photo", encoding="utf-8")

    monkeypatch.setattr(og, "STATE_DIR", state)
    monkeypatch.setattr(og, "GENESIS_FILE", state / "owner_genesis.json")
    monkeypatch.setattr(og, "GENESIS_LOG", state / "owner_genesis_history.jsonl")
    monkeypatch.setattr(og, "GENESIS_REPAIR_LOG", state / "owner_genesis_repair.jsonl")
    monkeypatch.setattr(og, "OWNER_DIR", owner_dir)
    monkeypatch.setattr(og, "_verify", lambda serial, payload, sig: sig == "valid_sig")
    monkeypatch.setattr(og, "_hash_file", lambda path: "photo_hash")

    (state / "owner_genesis.json").write_text(
        json.dumps({
            "schema": "OWNER_GENESIS_V1",
            "serial_number": "GTH4921YP3",
            "hardware_model": "MacBook Pro M5",
            "created_ts": 1.0,
        }),
        encoding="utf-8",
    )
    (state / "owner_genesis_history.jsonl").write_text(
        json.dumps(_full_scar()) + "\n",
        encoding="utf-8",
    )

    result = og.verify_genesis()
    repaired = json.loads((state / "owner_genesis.json").read_text(encoding="utf-8"))

    assert result["valid"] is True
    assert result["owner_name"] == "Ioan George Anton"
    assert repaired["owner_name"] == "Ioan George Anton"
    assert (state / "owner_genesis_repair.jsonl").exists()
