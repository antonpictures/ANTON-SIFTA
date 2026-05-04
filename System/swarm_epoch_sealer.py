"""
System/swarm_epoch_sealer.py
==============================================================================
Epoch sealing and post-quantum-ready revival receipts.

This module does not pretend to implement ML-DSA in pure stdlib. It creates the
ledger schema and deterministic fossil-record hashes now, while accepting a real
ML-DSA/SLH-DSA signature from a future signer when available.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_persistent_owner_history import state_dir

try:
    from System.swarm_crypto_agility import generate_hybrid_signature_envelope
except Exception:
    def generate_hybrid_signature_envelope(ed25519_sig: str, pq_sig: Optional[str] = None, **kw: Any) -> Dict[str, Any]:  # type: ignore
        return {
            "sig_alg": "Ed25519",
            "ed25519_sig": ed25519_sig,
            "pubkey_id": kw.get("pubkey_id", ""),
            "pq_sig_alg": kw.get("pq_sig_alg", "ML-DSA") if pq_sig else None,
            "pq_sig": pq_sig,
            "pq_pubkey_id": kw.get("pq_pubkey_id", "") if pq_sig else "",
        }

EPOCH_LOG_NAME = "epoch_seals.jsonl"
REVIVAL_PROOF_NAME = "revival_proof.jsonl"
TRUTH_EPOCH = "EPOCH_SEAL"
TRUTH_REVIVAL = "REVIVAL_PROOF"

DEFAULT_CRITICAL_LEDGERS: Sequence[str] = (
    "identity_continuity.jsonl",
    "regulatory_genome.jsonl",
    "hardware_identity_anchor.jsonl",
    "motor_cortex_log.jsonl",
    "stgm_economy_audit.jsonl",
    "repair_log.jsonl",
)


def epoch_seal_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / EPOCH_LOG_NAME


def revival_proof_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / REVIVAL_PROOF_NAME


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha3_512_text(text: str) -> str:
    return hashlib.sha3_512(text.encode("utf-8")).hexdigest()


def _read_file(path: Path) -> str:
    if not path.exists():
        return ""
    return read_text_locked(path, encoding="utf-8", errors="replace")


def _candidate_paths(sd: Path, repo_root: Path, name: str) -> List[Path]:
    rel = Path(name)
    if rel.is_absolute():
        return [rel]
    return [sd / rel, repo_root / rel]


def ledger_manifest(
    *,
    root: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    ledger_names: Sequence[str] = DEFAULT_CRITICAL_LEDGERS,
) -> List[Dict[str, Any]]:
    sd = state_dir(root)
    repo = repo_root or Path(__file__).resolve().parents[1]
    manifest: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for name in ledger_names:
        chosen: Optional[Path] = None
        for path in _candidate_paths(sd, repo, name):
            if path.exists():
                chosen = path
                break
        if chosen is None:
            chosen = _candidate_paths(sd, repo, name)[0]
        key = str(chosen.resolve()) if chosen.exists() else f"missing:{name}"
        if key in seen:
            continue
        seen.add(key)

        text = _read_file(chosen)
        lines = [line for line in text.splitlines() if line.strip()]
        manifest.append({
            "ledger_name": name,
            "path": str(chosen),
            "exists": chosen.exists(),
            "line_count": len(lines),
            "byte_count": len(text.encode("utf-8")),
            "last_row_sha256": _sha256_text(lines[-1]) if lines else "",
            "file_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else "",
            "file_sha3_512": _sha3_512_text(text) if text else "",
        })
    return manifest


def compute_fossil_record_hash(manifest: Sequence[Dict[str, Any]]) -> str:
    payload = json.dumps(list(manifest), sort_keys=True, separators=(",", ":"))
    return _sha3_512_text(payload)


def seal_epoch(
    *,
    epoch_id: int = 1,
    root: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    ledger_names: Sequence[str] = DEFAULT_CRITICAL_LEDGERS,
    owner_checkpoint: str = "",
    pq_signature: Optional[str] = None,
    pq_pubkey_id: str = "",
    now: Optional[float] = None,
    write_ledger: bool = True,
) -> Dict[str, Any]:
    """Seal an epoch as fossil record without rewriting historical rows."""
    manifest = ledger_manifest(root=root, repo_root=repo_root, ledger_names=ledger_names)
    fossil_hash = compute_fossil_record_hash(manifest)
    legacy_sig = hashlib.sha256(f"EPOCH:{epoch_id}:{fossil_hash}:{owner_checkpoint}".encode()).hexdigest()
    envelope = generate_hybrid_signature_envelope(
        legacy_sig,
        pq_signature,
        pubkey_id=f"sha256-local-epoch-{epoch_id}",
        pq_pubkey_id=pq_pubkey_id,
        pq_sig_alg="ML-DSA",
    )
    row: Dict[str, Any] = {
        "ts": time.time() if now is None else float(now),
        "trace_id": str(uuid.uuid4()),
        "kind": TRUTH_EPOCH,
        "truth_label": TRUTH_EPOCH,
        "schema": "SIFTA_EPOCH_SEAL_V1",
        "epoch_id": int(epoch_id),
        "ledger_manifest": manifest,
        "ledger_count": len(manifest),
        "fossil_record_hash_alg": "SHA3-512",
        "fossil_record_hash": fossil_hash,
        "owner_checkpoint": owner_checkpoint,
        "pq_signature_status": "attached" if pq_signature else "pqc_ready_metadata_only",
        "doctrine": "Epoch 1 is fossil record; Epoch 2 adds PQ signatures without rewriting history.",
    }
    row.update(envelope)

    if write_ledger:
        append_line_locked(
            epoch_seal_log_path(root),
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def latest_epoch_seal(*, root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    path = epoch_seal_log_path(root)
    if not path.exists():
        return None
    for line in reversed(read_text_locked(path, encoding="utf-8", errors="replace").splitlines()):
        if not line.strip():
            continue
        try:
            return json.loads(line)
        except Exception:
            continue
    return None


def build_revival_proof(
    *,
    root: Optional[Path] = None,
    revival_score: float,
    state_divergence_detected: bool = False,
    pq_signature: Optional[str] = None,
    now: Optional[float] = None,
    write_ledger: bool = True,
) -> Dict[str, Any]:
    """Write a tamper-evident revival row that references the latest epoch seal."""
    seal = latest_epoch_seal(root=root) or seal_epoch(root=root, write_ledger=False)
    try:
        from System.swarm_hardware_identity_anchor import compute_identity_anchor

        hardware = compute_identity_anchor(root=root, write_ledger=False)
    except Exception:
        hardware = {"identity_anchor": "", "hardware_serial": "UNKNOWN", "causal_chain_valid": False}

    payload = {
        "ledger_head_hash": seal.get("fossil_record_hash", ""),
        "hardware_identity_anchor": hardware.get("identity_anchor", ""),
        "hardware_serial": hardware.get("hardware_serial", ""),
        "revival_score": round(float(revival_score), 4),
        "state_divergence_detected": bool(state_divergence_detected),
    }
    current_boot_hash = _sha3_512_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    legacy_sig = hashlib.sha256(current_boot_hash.encode()).hexdigest()
    envelope = generate_hybrid_signature_envelope(
        legacy_sig,
        pq_signature,
        pubkey_id="sha256-local-revival",
        pq_pubkey_id="",
        pq_sig_alg="ML-DSA",
    )
    row: Dict[str, Any] = {
        "ts": time.time() if now is None else float(now),
        "trace_id": str(uuid.uuid4()),
        "kind": TRUTH_REVIVAL,
        "truth_label": TRUTH_REVIVAL,
        "schema": "SIFTA_REVIVAL_PROOF_V1",
        "last_shutdown_hash": seal.get("fossil_record_hash", ""),
        "current_boot_hash": current_boot_hash,
        "hardware_serial_signature": hardware.get("identity_anchor", ""),
        "ledger_head_hash": seal.get("fossil_record_hash", ""),
        "genome_row_hash": _latest_manifest_hash(seal.get("ledger_manifest", []), "regulatory_genome.jsonl"),
        "revival_score": round(float(revival_score), 4),
        "state_divergence_detected": bool(state_divergence_detected),
        "pq_signature_status": "attached" if pq_signature else "pqc_ready_metadata_only",
        "payload": payload,
    }
    row.update(envelope)
    if write_ledger:
        append_line_locked(
            revival_proof_log_path(root),
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def _latest_manifest_hash(manifest: Iterable[Dict[str, Any]], ledger_name: str) -> str:
    for item in manifest:
        if item.get("ledger_name") == ledger_name:
            return str(item.get("last_row_sha256") or item.get("file_sha256") or "")
    return ""


def verify_epoch_seal(row: Dict[str, Any]) -> bool:
    manifest = row.get("ledger_manifest")
    if not isinstance(manifest, list):
        return False
    expected = compute_fossil_record_hash(manifest)
    return expected == row.get("fossil_record_hash")


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    row = latest_epoch_seal(root=root)
    if not row:
        return ""
    return (
        "EPOCH SEAL:\n"
        f"- epoch={row.get('epoch_id')} hash={str(row.get('fossil_record_hash', ''))[:16]} "
        f"pq={row.get('pq_signature_status')}"
    )
