"""
System/swarm_crypto_agility.py — Post-Quantum Crypto Agility Shim
══════════════════════════════════════════════════════════════════
Event 50: Dr. Codex (C55M) Directive

This module inventories all cryptographic signing sites (Ed25519, HMAC, SHA)
and prepares the swarm for an eventual transition to ML-DSA (FIPS 204)
and SLH-DSA (FIPS 205).

WARNING: This shim does NOT replace Ed25519. It provides the metadata schema
to support hybrid signatures without breaking backward compatibility.
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

# The registry of known cryptographic sites and their target classifications.
# Classes:
#  - local_ok: Ed25519 remains fine for fast/local IPC where long-term trust isn't exposed.
#  - must_hybridize: Long-term trust roots (Passports, Wallet, Merkle) that need PQ security.
#  - legacy_hash_only: HMAC/SHA-256 which are already PQ-safe under Grover's algorithm.
#  - blocked: Fundamentally vulnerable constructs (e.g. bare MD5/SHA1, weak ECDSA).
_KNOWN_SITES: Dict[str, str] = {
    "System/swimmer_pheromone_identity.py": "must_hybridize",
    "System/swarm_wallet_transfer.py": "must_hybridize",
    "System/chorus_node_server.py": "local_ok",
    "System/chorus_engine.py": "local_ok",
    "System/swarm_replay_invariants.py": "legacy_hash_only",
    "System/swarm_merkle_attestor.py": "legacy_hash_only",
    "System/stigmergic_memory_bus.py": "legacy_hash_only",
    "System/owner_genesis.py": "must_hybridize",
    "System/bootstrap_pki.py": "must_hybridize",
    "System/pki_registry_validate.py": "must_hybridize",
    "System/genesis_lock.py": "must_hybridize",
}

DEFAULT_SCAN_ROOTS: Sequence[str] = ("System", "Kernel", "Applications", "scripts")
MODULE_VERSION = "2026-04-24.event50.crypto-agility.v2"
AUDIT_SCHEMA = "SIFTA_CRYPTO_AGILITY_AUDIT_V1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def generate_hybrid_signature_envelope(
    ed25519_sig: str,
    pq_sig: Optional[str] = None,
    *,
    pubkey_id: str = "",
    pq_pubkey_id: str = "",
    sig_version: str = "1.0",
    pq_sig_alg: str = "ML-DSA",
) -> Dict[str, Any]:
    """
    Produce the new crypto-agility envelope for a ledger row.
    Current legacy readers only check for `ed25519_sig`. This function allows
    producers to begin laying down the PQ structure.
    """
    has_pq = bool(pq_sig)
    envelope = {
        "sig_alg": "Ed25519",
        "sig_version": sig_version,
        "pubkey_id": pubkey_id,
        "ed25519_sig": ed25519_sig,
        "pq_sig_alg": pq_sig_alg if has_pq else None,
        "pq_pubkey_id": pq_pubkey_id if has_pq else "",
        "pq_sig": pq_sig,
    }
    return envelope


def _iter_python_files(repo_root: Path, scan_roots: Iterable[str]) -> Iterable[Path]:
    for rel_root in scan_roots:
        root = repo_root / rel_root
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            parts = set(py_file.relative_to(repo_root).parts)
            if "__pycache__" in parts or "node_modules" in parts:
                continue
            yield py_file


def _detect_primitives(content: str) -> List[str]:
    crypto_patterns = {
        "Ed25519": re.compile(r"(Ed25519PrivateKey|Ed25519PublicKey|ed25519)", re.IGNORECASE),
        "ECDSA": re.compile(r"\b(ECDSA|secp256k1|SECP256|ec\.ECDSA)\b"),
        "RSA": re.compile(r"\b(RSAPrivateKey|RSAPublicKey|rsa)\b"),
        "HMAC": re.compile(r"\bhmac\b", re.IGNORECASE),
        "SHA-256": re.compile(r"sha256", re.IGNORECASE),
        "MD5/SHA1": re.compile(r"\bmd5\b|\bsha1\b", re.IGNORECASE),
    }
    return sorted(name for name, pat in crypto_patterns.items() if pat.search(content))


def _classify(file_key: str, detected_primitives: Sequence[str], content: str) -> str:
    primitive_set = set(detected_primitives)
    if "MD5/SHA1" in primitive_set:
        return "blocked"
    if file_key in _KNOWN_SITES:
        return _KNOWN_SITES[file_key]
    if primitive_set & {"Ed25519", "ECDSA", "RSA"}:
        return "must_hybridize"
    if primitive_set & {"HMAC", "SHA-256"}:
        # HMAC/SHA-256 remain acceptable under Grover when sized correctly, but
        # truncated authenticators need manual attention before they become roots.
        if re.search(r"hexdigest\(\)\s*\[\s*:\s*(?:1[0-9]|2[0-9]|3[01])\s*\]", content):
            return "local_ok"
        return "legacy_hash_only"
    return "local_ok"


def audit_ledger_signers(
    *,
    repo_root: Optional[Path] = None,
    scan_roots: Sequence[str] = DEFAULT_SCAN_ROOTS,
    out_file: Optional[Path] = None,
    now: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Scans the codebase for cryptographic primitives and classifies them.
    Writes the result to .sifta_state/crypto_agility_audit.jsonl.
    """
    root = (repo_root or _repo_root()).resolve()
    t = time.time() if now is None else float(now)
    findings: List[Dict[str, Any]] = []

    for py_file in _iter_python_files(root, scan_roots):
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        detected_primitives = _detect_primitives(content)
        if not detected_primitives:
            continue

        file_key = py_file.relative_to(root).as_posix()
        classification = _classify(file_key, detected_primitives, content)

        findings.append({
            "event_kind": "CRYPTO_AGILITY_AUDIT",
            "schema": AUDIT_SCHEMA,
            "module_version": MODULE_VERSION,
            "ts": t,
            "module": file_key,
            "detected_primitives": detected_primitives,
            "classification": classification,
        })

    target = out_file or (root / ".sifta_state" / "crypto_agility_audit.jsonl")
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("w", encoding="utf-8") as f:
        for item in sorted(findings, key=lambda x: x["module"]):
            f.write(json.dumps(item, sort_keys=True) + "\n")

    print(f"Emitted crypto-agility audit to {target}: found {len(findings)} signing sites.")
    return findings

if __name__ == "__main__":
    audit_ledger_signers()
