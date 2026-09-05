import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from System import crypto_keychain as crypto


@pytest.fixture
def keychain(tmp_path, monkeypatch):
    directory = tmp_path / "keys"
    monkeypatch.setattr(crypto, "KEY_DIR", str(directory))
    monkeypatch.setattr(crypto, "PRIV_KEY_FILE", str(directory / "private.pem"))
    monkeypatch.setattr(crypto, "PKI_REGISTRY", str(tmp_path / "state" / "pki.json"))
    monkeypatch.setattr(crypto, "get_silicon_identity", lambda: "TEST_NODE")
    return directory


def test_serial_knowledge_does_not_allow_forgery(keychain):
    payload = "receipt-1"
    signature = crypto.sign_block(payload)
    assert crypto.verify_block("TEST_NODE", payload, signature)
    assert not crypto.verify_block("TEST_NODE", "altered", signature)
    forged = Ed25519PrivateKey.generate().sign(payload.encode()).hex()
    assert not crypto.verify_block("TEST_NODE", payload, forged)
    assert not crypto.verify_block("OTHER_NODE", payload, signature)


def test_permissions_repaired_without_rotating_key(keychain):
    signature = crypto.sign_block("same")
    os.chmod(keychain, 0o755)
    os.chmod(crypto.PRIV_KEY_FILE, 0o644)
    assert crypto.sign_block("same") == signature
    assert keychain.stat().st_mode & 0o777 == 0o700
    assert os.stat(crypto.PRIV_KEY_FILE).st_mode & 0o777 == 0o600


def test_concurrent_first_use_preserves_one_key(keychain):
    with ThreadPoolExecutor(max_workers=8) as pool:
        signatures = list(pool.map(crypto.sign_block, ["same"] * 16))
    assert len(set(signatures)) == 1
    assert crypto.verify_block("TEST_NODE", "same", signatures[0])


@pytest.mark.parametrize("contents", ['{"TEST_NODE": "different"}', "broken", "[]"])
def test_registry_conflict_never_overwritten(keychain, contents):
    crypto.sign_block("initial")
    with open(crypto.PKI_REGISTRY, "w") as stream:
        stream.write(contents)
    with pytest.raises(ValueError):
        crypto.sign_block("next")
    with open(crypto.PKI_REGISTRY) as stream:
        assert stream.read() == contents


def test_private_key_symlink_rejected(keychain, tmp_path):
    crypto.sign_block("initial")
    target = tmp_path / "original.pem"
    os.rename(crypto.PRIV_KEY_FILE, target)
    os.symlink(target, crypto.PRIV_KEY_FILE)
    with pytest.raises(OSError):
        crypto.sign_block("next")


def test_directory_symlink_rejected(keychain, tmp_path):
    target = tmp_path / "elsewhere"
    target.mkdir()
    keychain.symlink_to(target, target_is_directory=True)
    with pytest.raises(PermissionError):
        crypto.sign_block("next")
