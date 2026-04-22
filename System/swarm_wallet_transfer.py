#!/usr/bin/env python3
"""
System/swarm_wallet_transfer.py — Cryptosure STGM Wallet Transfer
══════════════════════════════════════════════════════════════════════════
Concept : Hardened, hardware-bound, attestation-gated outbound STGM transfer.
Author  : C47H (east bridge), hardening AG31's transfer_stgm v1
Status  : ACTIVE ORGAN

WHAT THIS REPLACES
──────────────────
AG31's first-cut `transfer_stgm()` in Kernel/inference_economy.py wrote a
TRANSFER row to the ledger but used a *third* dialect that ledger_balance()
does not recognise — so the sender's balance was never decremented and the
receiver was never credited. STGM appeared to "move" only in print() calls.
Plus signing fell open to a "NO_KEYCHAIN_…" placeholder when crypto was
unavailable, meaning a stripped install could still emit "transfers".

FIVE CRYPTOSURE GUARANTEES
──────────────────────────
1. **GATE FIRST.** Caller must hold a currently-valid biological attestation
   (`swarm_proof_of_humanity.is_verified()`). Otherwise we raise
   HumanityRequired and never touch the ledger.
2. **FAIL-CLOSED ON CRYPTO.** If the Ed25519 keychain is unavailable, the
   transfer is refused with NoCryptoBackend. No "NO_KEYCHAIN_" pseudo-sigs
   in transfer rows. The wallet does not pretend to sign.
3. **ATOMIC PAIR IN THE CANONICAL DIALECT.** Each transfer writes BOTH
   legs (STGM_SPEND from sender, STGM_MINT to receiver) under a shared
   `transfer_id`, in the dialect that `ledger_balance()` reads. Two rows,
   one logical event, one signature, balances actually move.
4. **HARDWARE + ATTESTATION BINDING.** Each row carries `silicon_serial`
   and `attestation_hash_prefix` so a forensic auditor can prove WHICH
   verified moment authorised the transfer.
5. **CHAIN ANCHOR.** Each row carries `prev_hash` of the previous ledger
   line. Splicing the ledger breaks the chain and is detectable later by
   a reconciliation pass — same Haber-Stornetta pattern we use in
   `swarm_conversation_chain.py`.

POLICY ANCHOR: WALLET_TRANSFER_CRYPTOSURE_v1
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_SYSTEM = _REPO / "System"
if str(_SYSTEM) not in sys.path:
    sys.path.insert(0, str(_SYSTEM))

_DEFAULT_LEDGER = _REPO / "repair_log.jsonl"

_POLICY = "WALLET_TRANSFER_CRYPTOSURE_v1"


# ─── Crypto bridge (we WILL fail closed if absent) ────────────────────────
try:
    from crypto_keychain import (
        sign_block as _sign_block,
        verify_block as _verify_block,
        get_silicon_identity as _get_serial,
    )
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

    def _sign_block(payload: str) -> str:
        return ""  # never used; transfer fails closed before this is called

    def _verify_block(*args, **kwargs) -> bool:
        return False

    def _get_serial() -> str:
        return "UNKNOWN_SERIAL"


from System.swarm_proof_of_humanity import (
    require_humanity,
    is_verified,
    get_attestation_status,
    HumanityRequired,
)


# ═══════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════

class NoCryptoBackend(RuntimeError):
    """Refused: no Ed25519 keychain available, cannot produce real signatures."""


class InsufficientBalance(ValueError):
    """Refused: sender does not have enough STGM in the canonical ledger."""


class InvalidTransferAmount(ValueError):
    """Refused: amount must be a positive finite number."""


class InvalidParticipant(ValueError):
    """Refused: sender or receiver agent_id is empty / equal / malformed."""


# ═══════════════════════════════════════════════════════════════════════════
# CHAIN HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _last_ledger_hash(ledger: Path) -> str:
    """SHA-256 of the last ledger line (or '' if ledger empty/missing)."""
    if not ledger.exists() or ledger.stat().st_size == 0:
        return ""
    try:
        with ledger.open("rb") as f:
            f.seek(0, 2)
            end = f.tell()
            f.seek(max(0, end - 8192))
            tail = f.read().decode("utf-8", errors="ignore").strip().splitlines()
        if not tail:
            return ""
        return hashlib.sha256(tail[-1].encode("utf-8")).hexdigest()
    except Exception:
        return ""


def _append_atomic(ledger: Path, lines: list) -> None:
    """Append multiple JSONL lines; one open-flush-close so they land together."""
    with ledger.open("a", encoding="utf-8") as fh:
        for ln in lines:
            fh.write(ln + "\n")
        fh.flush()
        os.fsync(fh.fileno())


# ═══════════════════════════════════════════════════════════════════════════
# CANONICAL CRYPTOSURE TRANSFER
# ═══════════════════════════════════════════════════════════════════════════

def transfer(sender: str, receiver: str, amount: float,
             memo: str = "",
             ledger: Optional[Path] = None) -> Dict:
    """
    The single canonical wallet transfer.

    Returns a dict with the transfer_id, both leg event_ids, the signed
    receipt body, the attestation prefix, and the chain prev_hash. Raises
    one of the typed exceptions on any guard failure — never silently
    succeeds with a half-written ledger.
    """
    target = ledger if ledger is not None else _DEFAULT_LEDGER

    # ── GUARD 1 — biological proof-of-humanity ──────────────────────────
    require_humanity("wallet_transfer")  # raises HumanityRequired if not verified

    # ── GUARD 2 — crypto must be REAL ───────────────────────────────────
    if not _CRYPTO_AVAILABLE:
        raise NoCryptoBackend(
            "wallet_transfer requires the Ed25519 keychain; refusing to write "
            "a transfer row with a pseudo-signature."
        )

    # ── GUARD 3 — amount sanity ─────────────────────────────────────────
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        raise InvalidTransferAmount(f"amount must be a number, got {amount!r}")
    if amt <= 0 or amt != amt or amt == float("inf"):
        raise InvalidTransferAmount(f"amount must be positive and finite, got {amt}")

    # ── GUARD 4 — participants ──────────────────────────────────────────
    s = (sender or "").strip()
    r = (receiver or "").strip()
    if not s or not r:
        raise InvalidParticipant("sender and receiver must both be non-empty")
    if s.upper() == r.upper():
        raise InvalidParticipant("sender and receiver must differ (no self-transfer)")

    # ── GUARD 5 — sufficient balance (canonical ledger reading) ─────────
    # Imported lazily to avoid cycles; inference_economy imports this module.
    from Kernel.inference_economy import ledger_balance
    sender_bal = float(ledger_balance(s))
    if sender_bal < amt:
        raise InsufficientBalance(
            f"{s} has {sender_bal:.6f} STGM, cannot transfer {amt:.6f}"
        )

    # ── BIND TO THE ACTIVE ATTESTATION ──────────────────────────────────
    status = get_attestation_status()
    silicon_serial = _get_serial()
    attestation_hash_prefix = status.get("biometric_hash_prefix", "")
    attestation_method = status.get("verification_method", "")
    attestation_expires = status.get("expires_at", 0.0)

    # ── BUILD SIGNED PAIR ───────────────────────────────────────────────
    transfer_id = "TX_" + uuid.uuid4().hex[:16]
    ts_iso = datetime.now(timezone.utc).isoformat()
    ts_unix = time.time()
    prev_hash = _last_ledger_hash(target)

    # The signature payload binds: transfer_id, both parties, amount, ts,
    # silicon serial, attestation hash prefix, and the prev_hash. Tampering
    # with ANY of these fields after the fact invalidates the signature.
    receipt_body = (
        f"{_POLICY}::TX[{transfer_id}]::FROM[{s}]::TO[{r}]::"
        f"AMT[{amt:.6f}]::TS[{ts_iso}]::SERIAL[{silicon_serial}]::"
        f"ATT[{attestation_hash_prefix}]::PREV[{prev_hash}]"
    )
    signature = _sign_block(receipt_body)
    if not signature or len(signature) < 64:
        # Crypto module exists but produced an empty/short signature — refuse.
        raise NoCryptoBackend(
            "Ed25519 keychain produced an invalid signature; refusing transfer."
        )

    # ── DEBIT (STGM_SPEND) and CREDIT (STGM_MINT) ───────────────────────
    spend_row = {
        "tx_type": "STGM_SPEND",
        "event": "WALLET_TRANSFER_OUT",
        "transfer_id": transfer_id,
        "leg": "DEBIT",
        "agent_id": s,
        "counterparty": r,
        # `from`/`to` are normalised so reconstruction of the signed body
        # is identical for both legs of the pair.
        "from": s,
        "to": r,
        "amount": round(amt, 6),
        "amount_signed_str": f"{amt:.6f}",  # exact string used in the body
        "memo": str(memo or "")[:200],
        "ts": ts_iso,
        "ts_unix": ts_unix,
        "silicon_serial": silicon_serial,
        # `signing_node` mirrors `silicon_serial` so the legacy validator
        # in Kernel/inference_economy._ledger_row_cryptographically_valid
        # can resolve the public key without a schema migration.
        "signing_node": silicon_serial,
        "attestation_hash_prefix": attestation_hash_prefix,
        "attestation_method": attestation_method,
        "attestation_expires_at": attestation_expires,
        "ed25519_sig": signature,
        "receipt_body_sha256": hashlib.sha256(receipt_body.encode()).hexdigest(),
        "prev_hash": prev_hash,
        "policy": _POLICY,
    }
    credit_row = dict(spend_row)
    credit_row.update({
        "tx_type": "STGM_MINT",
        "event": "WALLET_TRANSFER_IN",
        "leg": "CREDIT",
        "agent_id": r,
        "counterparty": s,
    })

    _append_atomic(target, [
        json.dumps(spend_row, separators=(",", ":")),
        json.dumps(credit_row, separators=(",", ":")),
    ])

    return {
        "transfer_id": transfer_id,
        "amount": round(amt, 6),
        "from": s,
        "to": r,
        "ts": ts_iso,
        "silicon_serial": silicon_serial,
        "attestation_hash_prefix": attestation_hash_prefix,
        "prev_hash": prev_hash,
        "receipt_body_sha256": spend_row["receipt_body_sha256"],
        "ed25519_sig": signature,
        "policy": _POLICY,
    }


# ═══════════════════════════════════════════════════════════════════════════
# PROOF OF PROPERTY
# ═══════════════════════════════════════════════════════════════════════════

def proof_of_property() -> Dict[str, bool]:
    """
    Ten invariants that codify the cryptosure transfer doctrine. Every test
    runs against a SCRATCH ledger AND a SCRATCH attestation file in /tmp,
    so the user's real wallet is never touched.
    """
    import tempfile

    results: Dict[str, bool] = {}
    print("\n=== SIFTA WALLET TRANSFER : CRYPTOSURE VERIFICATION ===")

    # Quarantine: redirect both the attestation file AND the ledger to /tmp.
    import System.swarm_proof_of_humanity as poh
    real_attestation = poh._ATTESTATION_FILE
    tmp_dir = Path(tempfile.mkdtemp(prefix="cryptosure_"))
    scratch_attest = tmp_dir / "att.json"
    scratch_ledger = tmp_dir / "repair_log.jsonl"
    poh._ATTESTATION_FILE = scratch_attest

    # We also need ledger_balance to read OUR scratch ledger. The kernel
    # binds LOG_PATH at module load, so we monkey-patch it for the test.
    import Kernel.inference_economy as kie
    real_log_path = kie.LOG_PATH
    kie.LOG_PATH = scratch_ledger

    # Helper: seed sender balance via canonical Dialect-B mint row
    def _seed_balance(agent: str, amount: float):
        seed = {
            "tx_type": "STGM_MINT",
            "agent_id": agent,
            "amount": float(amount),
            "ts": datetime.now(timezone.utc).isoformat(),
            "reason": "cryptosure_proof_seed",
        }
        with scratch_ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(seed, separators=(",", ":")) + "\n")

    SENDER = "CRYPTOSURE_PROOF_SENDER"
    RECEIVER = "CRYPTOSURE_PROOF_RECEIVER"

    try:
        # ── P1: unverified node cannot transfer ─────────────────────────
        print("[*] P1: unverified node → HumanityRequired")
        if scratch_attest.exists():
            scratch_attest.unlink()
        _seed_balance(SENDER, 100.0)
        gate_held = False
        try:
            transfer(SENDER, RECEIVER, 5.0, ledger=scratch_ledger)
        except HumanityRequired:
            gate_held = True
        results["unverified_blocked"] = bool(gate_held)
        print(f"    raised_HumanityRequired={gate_held}   "
              f"[{'PASS' if results['unverified_blocked'] else 'FAIL'}]")

        # Now attest so subsequent tests can transfer
        poh.attest_from_bytes(b"BIO_BYTES_FOR_CRYPTOSURE_PROOF",
                              method="CRYPTOSURE_PROOF_v1", ttl_seconds=3600)

        # ── P2: verified node CAN transfer ──────────────────────────────
        print("[*] P2: verified node + sufficient balance → transfer succeeds")
        try:
            receipt = transfer(SENDER, RECEIVER, 10.0, memo="proof_p2",
                               ledger=scratch_ledger)
            verified_ok = bool(receipt and receipt.get("transfer_id"))
        except Exception as e:
            verified_ok = False
            print(f"    unexpected error: {type(e).__name__}: {e}")
        results["verified_can_transfer"] = bool(verified_ok)
        print(f"    succeeded={verified_ok}   "
              f"[{'PASS' if results['verified_can_transfer'] else 'FAIL'}]")

        # ── P3: sender actually debited ─────────────────────────────────
        print("[*] P3: sender balance moved 100.0 → 90.0 on canonical ledger")
        sb = float(kie.ledger_balance(SENDER))
        results["sender_debited"] = bool(abs(sb - 90.0) < 1e-6)
        print(f"    sender_balance={sb:.6f}   "
              f"[{'PASS' if results['sender_debited'] else 'FAIL'}]")

        # ── P4: receiver actually credited ──────────────────────────────
        print("[*] P4: receiver balance moved 0.0 → 10.0 on canonical ledger")
        rb = float(kie.ledger_balance(RECEIVER))
        results["receiver_credited"] = bool(abs(rb - 10.0) < 1e-6)
        print(f"    receiver_balance={rb:.6f}   "
              f"[{'PASS' if results['receiver_credited'] else 'FAIL'}]")

        # ── P5: both legs share the same transfer_id ────────────────────
        print("[*] P5: STGM_SPEND and STGM_MINT legs share one transfer_id")
        tx_id = receipt["transfer_id"]
        spend_seen = mint_seen = False
        with scratch_ledger.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("transfer_id") == tx_id:
                    if row.get("tx_type") == "STGM_SPEND" and row.get("agent_id") == SENDER:
                        spend_seen = True
                    if row.get("tx_type") == "STGM_MINT" and row.get("agent_id") == RECEIVER:
                        mint_seen = True
        results["legs_share_transfer_id"] = bool(spend_seen and mint_seen)
        print(f"    debit_seen={spend_seen} credit_seen={mint_seen}   "
              f"[{'PASS' if results['legs_share_transfer_id'] else 'FAIL'}]")

        # ── P6: every transfer row carries attestation binding ──────────
        print("[*] P6: rows carry silicon_serial + attestation_hash_prefix")
        ok = True
        with scratch_ledger.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("transfer_id") == tx_id:
                    if not row.get("silicon_serial"):
                        ok = False
                    if "attestation_hash_prefix" not in row:
                        ok = False
        results["attestation_binding_present"] = bool(ok)
        print(f"    binding_present={ok}   "
              f"[{'PASS' if results['attestation_binding_present'] else 'FAIL'}]")

        # ── P7: prev_hash chain anchor present ──────────────────────────
        print("[*] P7: rows carry prev_hash chain anchor")
        ok = True
        with scratch_ledger.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("transfer_id") == tx_id:
                    if "prev_hash" not in row:
                        ok = False
        results["prev_hash_anchored"] = bool(ok)
        print(f"    chain_anchor_present={ok}   "
              f"[{'PASS' if results['prev_hash_anchored'] else 'FAIL'}]")

        # ── P8: zero / negative amounts refused ─────────────────────────
        print("[*] P8: zero / negative amounts → InvalidTransferAmount")
        z_raised = n_raised = False
        try:
            transfer(SENDER, RECEIVER, 0.0, ledger=scratch_ledger)
        except InvalidTransferAmount:
            z_raised = True
        try:
            transfer(SENDER, RECEIVER, -5.0, ledger=scratch_ledger)
        except InvalidTransferAmount:
            n_raised = True
        results["bad_amounts_refused"] = bool(z_raised and n_raised)
        print(f"    zero_refused={z_raised} neg_refused={n_raised}   "
              f"[{'PASS' if results['bad_amounts_refused'] else 'FAIL'}]")

        # ── P9: insufficient balance refused ────────────────────────────
        print("[*] P9: amount > balance → InsufficientBalance, ledger unchanged")
        sb_pre = float(kie.ledger_balance(SENDER))
        ins_raised = False
        try:
            transfer(SENDER, RECEIVER, sb_pre + 1.0, ledger=scratch_ledger)
        except InsufficientBalance:
            ins_raised = True
        sb_post = float(kie.ledger_balance(SENDER))
        results["insufficient_refused"] = bool(ins_raised and sb_pre == sb_post)
        print(f"    raised={ins_raised} balance_unchanged={sb_pre == sb_post}   "
              f"[{'PASS' if results['insufficient_refused'] else 'FAIL'}]")

        # ── P10: fail-closed when crypto unavailable ────────────────────
        print("[*] P10: missing crypto backend → NoCryptoBackend (fail-closed)")
        # IMPORTANT: when this file is run as `__main__` the same module
        # also gets re-imported as System.swarm_wallet_transfer, creating
        # two distinct module objects with two distinct NoCryptoBackend
        # classes. We must catch the exception class belonging to the
        # module we're calling INTO (`wt.NoCryptoBackend`), not the one
        # in __main__'s namespace.
        import System.swarm_wallet_transfer as wt
        original_avail = wt._CRYPTO_AVAILABLE
        wt._CRYPTO_AVAILABLE = False
        crypto_raised = False
        try:
            wt.transfer(SENDER, RECEIVER, 1.0, ledger=scratch_ledger)
        except wt.NoCryptoBackend:
            crypto_raised = True
        except Exception as e:
            print(f"    unexpected exception: {type(e).__name__}: {e}")
        finally:
            wt._CRYPTO_AVAILABLE = original_avail
        results["fail_closed_no_crypto"] = bool(crypto_raised)
        print(f"    raised_NoCryptoBackend={crypto_raised}   "
              f"[{'PASS' if results['fail_closed_no_crypto'] else 'FAIL'}]")

    finally:
        # Restore EVERYTHING the test redirected.
        poh._ATTESTATION_FILE = real_attestation
        kie.LOG_PATH = real_log_path
        try:
            if scratch_ledger.exists():
                scratch_ledger.unlink()
            if scratch_attest.exists():
                scratch_attest.unlink()
            tmp_dir.rmdir()
        except Exception:
            pass

    all_green = all(results.values())
    print(f"\n[+] {'ALL TEN INVARIANTS PASSED' if all_green else 'FAILURES PRESENT'}: "
          f"{results}")
    return results


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "proof"
    if cmd == "proof":
        proof_of_property()
    else:
        print("Usage: swarm_wallet_transfer.py [proof]")
