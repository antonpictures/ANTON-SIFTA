"""Proof: Warp9 spool carries inference_borrow_intent without network code."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest


@pytest.fixture()
def isolated_warp9(monkeypatch, tmp_path):
    import System.swarm_warp9_federation as w9

    spool = tmp_path / "warp9_spool"
    spool.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(w9, "_SPOOL", spool)
    monkeypatch.setattr(w9, "FEDERATION_ENABLED", True)

    def fake_detect_serial():
        return "GTH4921YP3"

    def fake_detect_arch(**_kw):
        return "IOAN_M5"

    monkeypatch.setattr(w9, "detect_self_homeworld_serial", fake_detect_serial)
    monkeypatch.setattr(w9, "detect_self_architect_id", fake_detect_arch)

    def fake_owner(_label: str = "IOAN", persist: bool = True):
        return SimpleNamespace(key="owner_test_key", label="IOAN")

    def fake_list_homeworlds(owner_key: str):
        assert owner_key == "owner_test_key"
        return [
            SimpleNamespace(
                homeworld_serial="GTH4921YP3",
                architect_id="IOAN_M5",
                machine_label="M5",
                role="primary",
            ),
            SimpleNamespace(
                homeworld_serial="C07FL0JAQ6NV",
                architect_id="IOAN_M1",
                machine_label="M1",
                role="peer",
            ),
        ]

    monkeypatch.setattr(w9, "get_or_create_owner", fake_owner)
    monkeypatch.setattr(w9, "list_owner_homeworlds", fake_list_homeworlds)
    return w9


def test_send_inference_borrow_intent_roundtrip(isolated_warp9, monkeypatch):
    w9 = isolated_warp9
    msg = w9.send_inference_borrow_intent(
        "C07FL0JAQ6NV",
        borrower_agent_id="M1THER_EDGE",
        model="alice-m5-cortex-8b-6.3gb",
        tokens_requested=64,
        fee_stgm_offer=0.03,
        owner_label="IOAN",
        force=False,
        note="pytest warp9",
    )
    assert msg is not None
    assert msg.kind == "inference_borrow_intent"
    assert msg.to_homeworld == "C07FL0JAQ6NV"
    assert msg.payload["fee_stgm_offer"] == pytest.approx(0.03)

    # recv() globs ``*__<self_serial>.jsonl`` — M1 (receiver) sees ``GTH__C07FL...``.
    monkeypatch.setattr(w9, "detect_self_homeworld_serial", lambda: "C07FL0JAQ6NV")
    got = w9.recv(kinds=["inference_borrow_intent"], since_ts=0.0, owner_label="IOAN")
    assert len(got) == 1
    assert got[0].msg_id == msg.msg_id

    pairs = w9.list_spool_pairs()
    assert len(pairs) == 1
    assert pairs[0]["from"] == "GTH4921YP3"
    assert pairs[0]["to"] == "C07FL0JAQ6NV"
    assert pairs[0]["rows"] == 1


def test_send_inference_borrow_intent_jsonl_line_shape(isolated_warp9, tmp_path):
    w9 = isolated_warp9
    w9.send_inference_borrow_intent(
        "C07FL0JAQ6NV",
        borrower_agent_id="BORROWER",
        model="m",
        tokens_requested=1,
        fee_stgm_offer=0.01,
        force=False,
    )
    path = tmp_path / "warp9_spool" / "GTH4921YP3__C07FL0JAQ6NV.jsonl"
    line = path.read_text(encoding="utf-8").strip().splitlines()[0]
    row = json.loads(line)
    assert row["kind"] == "inference_borrow_intent"
    assert row["payload"]["borrower_agent_id"] == "BORROWER"
