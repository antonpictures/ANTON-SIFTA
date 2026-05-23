from pathlib import Path

from System.swarm_crypto_agility import audit_ledger_signers, generate_hybrid_signature_envelope

def test_hybrid_signature_envelope():
    # Simulate a ledger record using the hybrid envelope
    record = {
        "node_id": "M5_STUDIO",
        "timestamp": 1234567890,
        "amount": 100
    }
    
    # Sign it with legacy Ed25519 (mock)
    ed25519_sig_mock = "abcdef1234567890" * 4 # 64 bytes hex
    
    # Sign it with ML-DSA (mock)
    ml_dsa_sig_mock = "pq_sig_0987654321" * 4
    
    envelope = generate_hybrid_signature_envelope(
        ed25519_sig_mock,
        ml_dsa_sig_mock,
        pubkey_id="ed25519:m5",
        pq_pubkey_id="mldsa:m5",
    )
    record.update(envelope)
    
    # 1. Assert old readers don't break (they just pull 'ed25519_sig')
    assert "ed25519_sig" in record
    assert record["ed25519_sig"] == ed25519_sig_mock
    assert record["pubkey_id"] == "ed25519:m5"
    
    # 2. Assert new PQ metadata exists
    assert record["sig_alg"] == "Ed25519"
    assert record["pq_sig_alg"] == "ML-DSA"
    assert record["pq_pubkey_id"] == "mldsa:m5"
    assert record["pq_sig"] == ml_dsa_sig_mock

def test_hybrid_envelope_no_pq():
    ed25519_sig_mock = "abcdef1234567890" * 4
    envelope = generate_hybrid_signature_envelope(ed25519_sig_mock)
    
    assert envelope["ed25519_sig"] == ed25519_sig_mock
    assert envelope["pq_sig_alg"] is None
    assert envelope["pq_pubkey_id"] == ""
    assert envelope["pq_sig"] is None

def test_audit_ledger_signers_scans_all_directive_roots(tmp_path):
    repo = tmp_path / "repo"
    (repo / "System").mkdir(parents=True)
    (repo / "Kernel").mkdir()
    (repo / "Applications").mkdir()
    (repo / "scripts").mkdir()

    (repo / "System" / "wallet.py").write_text(
        "from cryptography.hazmat.primitives.asymmetric import ed25519\n"
        "ed25519.Ed25519PrivateKey.generate()\n",
        encoding="utf-8",
    )
    (repo / "Kernel" / "seal.py").write_text("import hmac, hashlib\nhashlib.sha256(b'x')\n", encoding="utf-8")
    (repo / "Applications" / "legacy.py").write_text("import hashlib\nhashlib.md5(b'x')\n", encoding="utf-8")
    (repo / "scripts" / "tool.py").write_text("import hashlib\nhashlib.sha1(b'x')\n", encoding="utf-8")

    out = repo / ".sifta_state" / "crypto_agility_audit.jsonl"
    findings = audit_ledger_signers(repo_root=repo, out_file=out, now=123.0)
    by_module = {f["module"]: f for f in findings}

    assert by_module["System/wallet.py"]["classification"] == "must_hybridize"
    assert by_module["Kernel/seal.py"]["classification"] == "legacy_hash_only"
    assert by_module["Applications/legacy.py"]["classification"] == "blocked"
    assert by_module["scripts/tool.py"]["classification"] == "blocked"
    assert by_module["System/wallet.py"]["event_kind"] == "CRYPTO_AGILITY_AUDIT"
    assert by_module["System/wallet.py"]["schema"] == "SIFTA_CRYPTO_AGILITY_AUDIT_V1"
    assert out.exists()
    assert len(out.read_text(encoding="utf-8").splitlines()) == 4


def test_audit_real_repo_finds_swimmer_identity(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    out = tmp_path / "crypto_agility_audit.jsonl"
    findings = audit_ledger_signers(repo_root=repo, out_file=out, now=123.0)
    swimmer_identity = next(
        f for f in findings if f["module"] == "System/swimmer_pheromone_identity.py"
    )

    assert swimmer_identity["classification"] == "must_hybridize"
    assert "Ed25519" in swimmer_identity["detected_primitives"]
