#!/usr/bin/env python3
"""r302: real signatures elevate the swimmer chain from tamper-evident to cryptographic.

George: "make it like bitcoin." A bitcoin transaction is valid only if signed by the
holder's key. These pin the same property on the swimmer field: a trace is truth only if
its signature verifies, an altered message fails, a forged signature is rejected, and the
whole chain reports crypto_verified only when every row was signature-validated.
"""
import json

from System import swarm_swimmer_crypto as cr
from System import swarm_swimmer_happiness as sw


def test_sign_verify_roundtrip_and_tamper(tmp_path):
    msg = "receipt-hash-abc123"
    sig = cr.sign(msg, state_dir=tmp_path)
    assert sig                                                   # a signature was produced
    assert cr.verify(msg, sig, state_dir=tmp_path) is True
    assert cr.verify("receipt-hash-DIFFERENT", sig, state_dir=tmp_path) is False   # message changed
    assert cr.verify(msg, "00" * 16, state_dir=tmp_path) is False                  # forged signature
    assert cr.backend(tmp_path) in ("ed25519", "hmac-sha256")
    assert cr.public_identity(tmp_path)


def test_bound_learning_rows_are_signed(tmp_path):
    a = sw.bind_swimmer_learning("calm#1", "observed_owner", content="George ate well", state_dir=tmp_path)
    assert a.get("signature") and a.get("sig_backend") in ("ed25519", "hmac-sha256")
    # the signature actually verifies against the row's own receipt hash
    assert cr.verify(a["receipt_hash"], a["signature"], state_dir=tmp_path,
                     public_key_hex=a.get("signer")) is True


def test_chain_is_cryptographically_verified(tmp_path):
    sw.bind_swimmer_learning("calm#1", "a", content="one", state_dir=tmp_path)
    sw.bind_swimmer_learning("calm#1", "b", content="two", state_dir=tmp_path)
    res = sw.verify_swimmer_chain("calm#1", state_dir=tmp_path)
    assert res["ok"] is True
    assert res["crypto_verified"] is True            # every row signature-validated
    assert res["backend"] in ("ed25519", "hmac-sha256")


def test_forged_row_signature_is_rejected(tmp_path):
    sw.bind_swimmer_learning("x#9", "a", content="one", state_dir=tmp_path)
    sw.bind_swimmer_learning("x#9", "b", content="two", state_dir=tmp_path)
    chain = tmp_path / ".sifta_state" / "swimmer_learning_chain.jsonl"
    lines = chain.read_text().strip().splitlines()
    row1 = json.loads(lines[1])
    row1["signature"] = "ab" * (64 if row1.get("sig_backend") == "ed25519" else 32)  # wrong sig
    lines[1] = json.dumps(row1)
    chain.write_text("\n".join(lines) + "\n")
    res = sw.verify_swimmer_chain("x#9", state_dir=tmp_path)
    assert res["ok"] is False and res["reason"] == "signature mismatch" and res["broken_at"] == 1
