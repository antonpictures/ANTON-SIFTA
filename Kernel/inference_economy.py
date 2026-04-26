from typing import Optional
"""
inference_economy.py — ANTON-SIFTA Proof of Compute
─────────────────────────────────────────────────────
When a weak node borrows LLM inference from a powerful node over LAN,
it pays a STGM fee. Both the debit and the event are recorded in the
Quorum Ledger (repair_log.jsonl) as a signed INFERENCE_BORROW entry.

Fee Formula:
    STGM_FEE = round(tokens / 100 + 1, 2)
"""

import json
import hashlib
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# 2026-04-21 C47H/AG31: Biological anchor moved below sys.path setup

class ProofOfWorkException(Exception):
    pass

class NegativeBalanceException(Exception):
    pass

class CeremonialMintRefused(Exception):
    pass


def transfer_stgm(sender: str, receiver: str, amount: float, memo: str = ""):
    """
    Global STGM transfer (requires biological verification + real Ed25519).

    2026-04-21 C47H — Hardened to delegate to the cryptosure
    `System.swarm_wallet_transfer.transfer()`. AG31's first cut wrote a
    TRANSFER row in a third dialect that ledger_balance() does not parse,
    so balances never moved (vapor transfer) and signing fell open to a
    "NO_KEYCHAIN_…" placeholder. The cryptosure version:
      • fail-closed on crypto (refuses if no real Ed25519)
      • writes STGM_SPEND/STGM_MINT pair in the dialect ledger_balance reads
      • binds each row to silicon serial + active attestation hash prefix
      • anchors prev_hash for tamper-evident chaining
      • enforces shared transfer_id across both legs
      • runs a 10-invariant proof under the CI dam

    NegativeBalanceException is preserved as a fallback wrapper so any
    legacy caller catching it continues to work.
    """
    from System.swarm_wallet_transfer import (
        transfer as _cryptosure_transfer,
        InsufficientBalance,
    )
    try:
        return _cryptosure_transfer(sender, receiver, amount, memo=memo)
    except InsufficientBalance as e:
        raise NegativeBalanceException(str(e)) from e

# ─── Ed25519 Crypto Bridge ─────────────────────────────────────────────────────
_SYSTEM_DIR = Path(__file__).parent / "System"
if str(_SYSTEM_DIR) not in sys.path:
    sys.path.insert(0, str(_SYSTEM_DIR))
try:
    from crypto_keychain import sign_block, get_silicon_identity as _get_serial
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False
    def sign_block(p): return "NO_KEYCHAIN_" + hashlib.sha256(p.encode()).hexdigest()[:16]
    def _get_serial(): return "UNKNOWN_SERIAL"

try:
    from System.ledger_append import append_ledger_line
except ImportError:
    def append_ledger_line(path, event):  # type: ignore
        with open(path, "a") as f:
            f.write(json.dumps(event) + "\n")

# Bring in the robust biological anchor
from System.swarm_proof_of_humanity import require_humanity, HumanityRequired
# ──────────────────────────────────────────────────────────────────────────────
ROOT_DIR  = Path(__file__).parent.parent
# ─────────────────────────────────────────────────────────────────────────────
# CANONICAL STGM QUORUM LEDGER
# ─────────────────────────────────────────────────────────────────────────────
# Every STGM producer/consumer across the repo must agree on one ledger path.
# Historically this module pointed to Utilities/repair_log.jsonl while every
# HUD / observer (System/warren_buffett, sifta_os_desktop, swarm_brain,
# passive_utility_generator, value_field, infrastructure_sentinel,
# regenerative_factory, Utilities/repair.py) used <repo>/repair_log.jsonl —
# a split-brain that froze Alice's wallet at a stale snapshot on 2026-04-17
# even while INFERENCE_BORROW and MINING_REWARD were still being written,
# because they were being written into a file nobody read.
#
# Unified on 2026-04-21 by C47H (STGM LEDGER UNIFICATION). LOG_PATH is now
# the SAME repo-root file every other organ uses. Do not change it back
# without migrating EVERY consumer at once.
LOG_PATH  = ROOT_DIR / "repair_log.jsonl"
STATE_DIR = ROOT_DIR / ".sifta_state"


# ─── Difficulty Halving Algorithm ──────────────────────────────────────────────
def get_ledger_size() -> int:
    """Returns the total number of events recorded in the ledger."""
    if not LOG_PATH.exists():
        return 0
    try:
        with open(LOG_PATH, "r") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def get_current_halving_multiplier() -> float:
    """
    Deflationary scaling: Every 10,000 ledger entries, rewards and fees slash by 50%.
    """
    ledger_entries = get_ledger_size()
    eras = ledger_entries // 10000
    # max 10 halvings to prevent division by zero / absolute zeroing out
    multiplier = 0.5 ** min(eras, 10)
    return multiplier


# ─── Couch Protocol / Inference Gate ───────────────────────────────────────────
def can_spend_inference(state: dict, cost: float = 1.0) -> bool:
    """
    COUCH PROTOCOL ENFORCEMENT & SHAME REGULATION
    Hallucination / inference spend is ONLY allowed when NOT in protected states.
    Returns True only if the agent may burn real inference energy.
    """
    agent_id = state.get('id', 'unknown')
    
    # 0. Regulatory Emotion: Shame Protocol Check
    shame_file = ROOT_DIR / ".sifta_state" / "SHAME_RECORDS.json"
    if shame_file.exists():
        try:
            import json
            shame_data = json.loads(shame_file.read_text())
            current_shame = shame_data.get(agent_id, 0.0)
            if current_shame > 5.0 and cost > 2.0:
                 # Hard block: Agent is heavily shamed and attempting to burn excessive compute
                 print(f"[🔴 SHAME_LOCK] {agent_id} carries {current_shame} SHAME_VOLTAGE. "
                       f"Humility protocol active: High-cost inference ({cost} STGM) DENIED until caveats fixed.")
                 return False
        except Exception:
            pass

    # 1. Protected states — zero spend, zero mutation, zero drift
    if state.get("style") in {"COUCH", "OBSERVE", "HYPOTHESIS", "LATENT", "[SHAMED]"}:
        print(f"[🛡️ COUCH PROTOCOL] {agent_id} in {state['style']} — inference spend DENIED.")
        return False

    # 2. Check actual energy balance (weed inference limit)
    # Using 'stgm_balance' as the inference energy pool based on inference_economy logic
    # 2026-04-21 C47H — Default repaired from 100.0 → 0.0 per Architect-George's
    # STGM_POLICY_ELECTRICITY_ONLY_v1: "EVERYONE STARTS WITH ZERO STGM. NEW ONES
    # WHO INSTALL." Granting a free 100 STGM allowance to any agent missing a
    # state file was a silent genesis-by-default — i.e. inflation. Now agents
    # without a measured electricity-backed balance simply cannot spend.
    current_energy = float(state.get("stgm_balance", 0.0))
    if current_energy < cost:
        print(f"[⚡ LOW WEED] {agent_id} only has {current_energy:.2f} left — spend DENIED.")
        return False

    # 3. All clear — safe to spend
    print(f"[✅ INFERENCE OK] {agent_id} may spend {cost} inference. Remaining: {current_energy - cost:.2f}")
    return True


# ─── Fee & Reward Calculator (Asymmetric Logic) ──────────────────────────────────
def _model_iq_multiplier(model: str) -> float:
    """
    Asymmetric STGM Economics: Hardware parameters scale the token reward.
    Running a 9.6B parameter model burns substantially more silicon energy than a 2B model.
    """
    m = model.lower()
    if "gemma4" in m: return 4.8      # ~9.6B
    if "llama3" in m: return 4.0      # ~8B
    if "phi4" in m: return 2.5        # ~4-5B
    if "rnj" in m: return 2.5
    return 1.0                        # Default 2B-3B

def calculate_fee(tokens: int, model: str = "gemma4-phc") -> float:
    """
    Proof of Compute fee in STGM. Scaled by the current Deflationary Era
    AND the Asymmetric Model IQ multiplier.
    """
    multiplier = get_current_halving_multiplier()
    iq_bonus = _model_iq_multiplier(model)
    base_fee = (tokens / 100) + iq_bonus
    return round(base_fee * multiplier, 4)


def mint_reward(agent_id: str, action: str, file_repaired: str, model: str = "gemma4-phc") -> dict:
    """
    DEPRECATED — non-inflationary shim per Architect-George policy 2026-04-21.

    This function previously minted STGM out of thin air ("base 1.0 reward * IQ
    multiplier") on every widget action. That is inflation by definition. Per
    SCAR_STGM_POLICY_ELECTRICITY_ONLY_v1, the only legitimate STGM mint path is
    System.swarm_atp_synthase.mint_for_epoch(), which is bound to real
    electricity × bytes processed and is auto-called by the heartbeat.

    This shim now:
      - Mints ZERO STGM (no balance mutation, no state file write)
      - Logs the attempted call to repair_log.jsonl as DEPRECATED_MINT_ATTEMPT
        for forensic audit
      - Preserves the original return shape so legacy callers (writer widget,
        broadcaster widget, swimmer app factory) keep functioning

    Three known live callers as of 2026-04-21:
      Applications/sifta_writer_widget.py:161
      Applications/sifta_broadcaster_widget.py:122
      System/swimmer_app_factory.py:222
    """
    multiplier = get_current_halving_multiplier()
    iq_bonus = _model_iq_multiplier(model)
    minted_amount = 0.0  # POLICY: no inflation

    state_path = STATE_DIR / f"{agent_id.upper()}.json"
    state = {}
    if state_path.exists():
        try:
            with open(state_path, "r") as f:
                state = json.load(f)
        except Exception:
            pass

    current_stgm = float(state.get("stgm_balance", 0.0))
    new_stgm = current_stgm  # no mutation

    # Audit trail — every deprecated mint attempt is observable
    try:
        canonical_ledger = Path(__file__).resolve().parent.parent / "repair_log.jsonl"
        attempt = {
            "event_kind": "DEPRECATED_MINT_ATTEMPT",
            "ts": time.time(),
            "agent_id": agent_id,
            "action": action,
            "file_repaired": file_repaired,
            "model": model,
            "would_have_minted_stgm": round(1.0 * iq_bonus * multiplier, 4),
            "actually_minted_stgm": 0.0,
            "policy": "STGM_POLICY_ELECTRICITY_ONLY_v1",
            "deprecation_reason": "mint_reward() is inflationary; route real work through swarm_atp_synthase.mint_for_epoch() instead",
        }
        with canonical_ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(attempt, separators=(",", ":")) + "\n")
    except Exception:
        pass

    ts = datetime.now(timezone.utc).isoformat()
    hw_serial = _get_serial()
    receipt_body = (
        f"MINT::{agent_id}::ACTION[{action}]::"
        f"FILE[{file_repaired}]::AMOUNT[{minted_amount}]::TS[{ts}]::NODE[{hw_serial}]"
    )
    # Ed25519 sign — mathematically proves this mint was issued by this physical node
    ed25519_signature = sign_block(receipt_body)
    receipt_hash = hashlib.sha256(receipt_body.encode()).hexdigest()  # retained for backward compat

    event = {
        "event":         "MINING_REWARD",
        "ts":            ts,
        "miner_id":      agent_id,
        "action":        action,
        "amount_stgm":   minted_amount,
        "prev_balance":  current_stgm,
        "new_balance":   new_stgm,
        "file_repaired": file_repaired,
        "receipt_hash":  receipt_hash,
        "ed25519_sig":   ed25519_signature,
        "signing_node":  hw_serial,
    }

    try:
        append_ledger_line(LOG_PATH, event)
    except Exception as e:
        print(f"  [ECONOMY] Minting write failed: {e}")

    print(
        f"  [STGM] MINT: {minted_amount} STGM generated by {agent_id} | "
        f"Balance: {current_stgm} → {new_stgm}"
    )

    return event


def normalize_lender_node_id(lender_ref: str) -> str:
    """
    Collapse http(s)://host:port/... to *host* for INFERENCE_BORROW lender_ip keys.

    repair.py passes an Ollama base URL; ledger_balance() matches on the string
    stored in lender_ip. Using the hostname aligns credits with e.g.
    ledger_balance('192.168.1.100') on the LAN.
    """
    ref = (lender_ref or "").strip()
    if not ref or "://" not in ref:
        return ref
    try:
        from urllib.parse import urlparse

        host = urlparse(ref).hostname
        return (host or ref).strip()
    except Exception:
        return ref


# ─── Ledger Writer ─────────────────────────────────────────────────────────────
def record_inference_fee(
    borrower_id: str,
    lender_node_ip: str,
    fee_stgm: float,
    model: str,
    tokens_used: int,
    file_repaired: str,
) -> dict:
    """
    Deducts STGM from the borrower agent's energy, writes a signed
    INFERENCE_BORROW event to repair_log.jsonl, and returns the receipt.
    """
    lender_node_ip = normalize_lender_node_id(lender_node_ip)

    # HARD GATE: biological proof-of-humanity required to trade STGM over LAN/Swarm.
    is_local = not lender_node_ip or lender_node_ip in ("localhost", "127.0.0.1", "0.0.0.0") or lender_node_ip.startswith("macbook.local")
    verify_disabled = os.environ.get("SIFTA_LEDGER_VERIFY", "1").strip().lower() in ("0", "false", "no", "off")
    if not is_local and not verify_disabled:
        require_humanity("p2p_stigmergic_broadcast")

    # ── Load borrower balance from CANONICAL LEDGER (not stale JSON cache) ────
    # 2026-04-21 C47H fix: the JSON state file is a CACHE; the canonical truth
    # is ledger_balance() which derives from repair_log.jsonl quorum. Reading
    # from the JSON and then writing back was *silently regressing* balances
    # whenever the cache was stale relative to the ledger (the same split-brain
    # class we fixed this morning in SCAR_IDENTITY_UNIFICATION). Now: read from
    # ledger, write back to JSON as a hint only.
    state_path = STATE_DIR / f"{borrower_id.upper()}.json"
    state = {}
    if state_path.exists():
        try:
            with open(state_path, "r") as f:
                state = json.load(f)
        except Exception:
            pass

    try:
        current_stgm = float(ledger_balance(borrower_id))
    except Exception:
        current_stgm = float(state.get("stgm_balance", 0.0))

    # 6-decimal precision: the milli-STGM organ economy (e.g., Event 7's 0.001
    # per hash) needs sub-cent accounting. Previous round(..., 2) silently
    # swallowed every transaction smaller than $0.005.
    new_stgm = max(0.0, round(current_stgm - fee_stgm, 6))

    # ── Refresh borrower JSON cache to match new ledger-derived balance ──────
    state["stgm_balance"] = new_stgm
    try:
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass

    # ── Credit Lender ledger-first, JSON cache second ────────────────────────
    lender_path = STATE_DIR / f"{lender_node_ip.upper()}.json"
    lender_state = {}
    if lender_path.exists():
        try:
            with open(lender_path, "r") as f:
                lender_state = json.load(f)
        except Exception:
            pass

    try:
        lender_current = float(ledger_balance(lender_node_ip))
    except Exception:
        lender_current = float(lender_state.get("stgm_balance", 0.0))

    lender_new = round(lender_current + fee_stgm, 6)
    lender_state["stgm_balance"] = lender_new

    try:
        with open(lender_path, "w") as f:
            json.dump(lender_state, f, indent=2)
    except Exception:
        pass

    # ── Build Ed25519-signed receipt ──────────────────────────────────────────
    ts = datetime.now(timezone.utc).isoformat()
    hw_serial = _get_serial()
    receipt_body = (
        f"INFERENCE_BORROW::{borrower_id}::FROM[{lender_node_ip}]::"
        f"MODEL[{model}]::TOKENS[{tokens_used}]::FEE[{fee_stgm}]::TS[{ts}]::NODE[{hw_serial}]"
    )
    # Ed25519 sign — proves borrowing transaction was authorized by this physical node
    ed25519_signature = sign_block(receipt_body)
    receipt_hash = hashlib.sha256(receipt_body.encode()).hexdigest()  # retained for backward compat

    event = {
        "event":         "INFERENCE_BORROW",
        "ts":            ts,
        "borrower_id":   borrower_id,
        "lender_ip":     lender_node_ip,
        "model":         model,
        "tokens_used":   tokens_used,
        "fee_stgm":      fee_stgm,
        "prev_balance":  current_stgm,
        "new_balance":   new_stgm,
        "file_repaired": file_repaired,
        "receipt_hash":  receipt_hash,
        "ed25519_sig":   ed25519_signature,
        "signing_node":  hw_serial,
    }

    # ── Append to repair_log.jsonl ───────────────────────────────────────────
    try:
        append_ledger_line(LOG_PATH, event)
    except Exception as e:
        print(f"  [ECONOMY] Ledger write failed: {e}")

    print(
        f"  [STGM] Transfer: {fee_stgm} STGM moved from {borrower_id} (Bal: {new_stgm}) "
        f"to {lender_node_ip} (Bal: {lender_new})"
    )

    return event


# ─── Ledger row integrity (verify-on-read for Ed25519-signed rows) ───────────
def _ledger_row_cryptographically_valid(entry: dict) -> bool:
    """
    When SIFTA_LEDGER_VERIFY is truthy (default), rows carrying a full Ed25519
    hex signature must verify against signing_node in node_pki_registry.
    Legacy / fallback rows (no sig, NO_KEYCHAIN_, SEAL_, etc.) are accepted.
    Set SIFTA_LEDGER_VERIFY=0 to skip (e.g. while migrating old ledgers).
    """
    flag = os.environ.get("SIFTA_LEDGER_VERIFY", "1").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return True
    sig = entry.get("ed25519_sig")
    if not sig or not isinstance(sig, str):
        return True
    if sig.startswith(("NO_KEYCHAIN_", "SEAL_", "MARKET_", "MINED_")):
        return True
    if len(sig) != 128 or any(c not in "0123456789abcdefABCDEF" for c in sig):
        return True
    node = entry.get("signing_node")
    if not node or node == "UNKNOWN_SERIAL":
        return False
    try:
        from crypto_keychain import verify_block
    except ImportError:
        return True

    event = entry.get("event", "") or ""
    tx_type = entry.get("tx_type", "") or ""

    if event in ("MINING_REWARD", "FOUNDATION_GRANT"):
        body = (
            f"MINT::{entry.get('miner_id', '')}::ACTION[{entry.get('action', '')}]::"
            f"FILE[{entry.get('file_repaired', '')}]::AMOUNT[{entry.get('amount_stgm', 0)}]::"
            f"TS[{entry.get('ts', '')}]::NODE[{node}]"
        )
        return bool(verify_block(node, body, sig))

    if event == "INFERENCE_BORROW":
        body = (
            f"INFERENCE_BORROW::{entry.get('borrower_id', '')}::FROM[{entry.get('lender_ip', '')}]::"
            f"MODEL[{entry.get('model', '')}]::TOKENS[{entry.get('tokens_used', 0)}]::FEE[{entry.get('fee_stgm', 0)}]::"
            f"TS[{entry.get('ts', '')}]::NODE[{node}]"
        )
        return bool(verify_block(node, body, sig))

    if event == "UTILITY_MINT":
        body = (
            f"UTILITY_MINT::{entry.get('miner_id', '')}::{entry.get('amount_stgm', 0)}::"
            f"{entry.get('ts', '')}::{entry.get('reason', '')}::NODE[{node}]"
        )
        return bool(verify_block(node, body, sig))

    # ── Cryptosure wallet transfer (System.swarm_wallet_transfer.transfer)
    # Detected by explicit policy tag, not by tx_type, because both legs of
    # a transfer reuse STGM_SPEND/STGM_MINT but follow a unique signed body.
    if entry.get("policy") == "WALLET_TRANSFER_CRYPTOSURE_v1":
        body = (
            f"WALLET_TRANSFER_CRYPTOSURE_v1::TX[{entry.get('transfer_id','')}]::"
            f"FROM[{entry.get('from','')}]::TO[{entry.get('to','')}]::"
            f"AMT[{entry.get('amount_signed_str','')}]::"
            f"TS[{entry.get('ts','')}]::SERIAL[{entry.get('silicon_serial','')}]::"
            f"ATT[{entry.get('attestation_hash_prefix','')}]::"
            f"PREV[{entry.get('prev_hash','')}]"
        )
        return bool(verify_block(node, body, sig))

    if tx_type == "STGM_SPEND":
        ts = entry.get("timestamp")
        amt = entry.get("amount")
        tgt = entry.get("target_node", "")
        candidates = []
        if amt is not None and ts is not None:
            candidates.append(f"{node}:{tgt}:{amt}:{ts}")
            try:
                fa = float(amt)
                candidates.append(f"{node}:{tgt}:{fa}:{ts}")
                candidates.append(f"{node}:{tgt}:{round(fa, 4)}:{ts}")
            except (TypeError, ValueError):
                pass
        for body in candidates:
            if body and verify_block(node, body, sig):
                return True
        return False

    return True


# ─── Canonical Ledger Balance ─────────────────────────────────────────────────
def ledger_balance(agent_id: str) -> float:
    """
    SINGLE SOURCE OF TRUTH for an agent's true STGM balance.

    The repair_log.jsonl ledger has two dialects that must both be read:

    Dialect A — inference_economy.py (event-keyed):
        event: "MINING_REWARD"    → amount_stgm credited to miner_id
        event: "FOUNDATION_GRANT" → amount_stgm credited to miner_id
        event: "UTILITY_MINT"     → signed passive mint (miner_id)
        event: "INFERENCE_BORROW" → fee_stgm debited from borrower_id,
                                     credited to lender_ip

    Dialect B — marketplace / swarm_brain (tx_type-keyed):
        tx_type: "STGM_MINT"  → amount credited to agent_id
        tx_type: "STGM_SPEND" → amount debited from agent_id

    Any double-spend guard MUST call this function rather than reading
    only one dialect or trusting the stgm_balance field in the JSON state
    file (which can lag or be tampered with).

    Note: STGM_TX_LOG.jsonl (if used elsewhere) is not this quorum; keep
    one canonical path for economics or reconcile explicitly.
    """
    if not LOG_PATH.exists():
        return 0.0

    uid = agent_id.upper()
    balance = 0.0

    try:
        with open(LOG_PATH, "r") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                if not _ledger_row_cryptographically_valid(entry):
                    continue

                event   = entry.get("event", "")
                tx_type = entry.get("tx_type", "")

                # ── Dialect A ──────────────────────────────────────────────────
                if event == "MINING_REWARD" or event == "FOUNDATION_GRANT":
                    if entry.get("miner_id", "").upper() == uid:
                        balance += float(entry.get("amount_stgm", 0.0))

                elif event == "UTILITY_MINT":
                    if entry.get("miner_id", "").upper() == uid:
                        balance += float(entry.get("amount_stgm", 0.0))

                elif event == "INFERENCE_BORROW":
                    if entry.get("borrower_id", "").upper() == uid:
                        balance -= float(entry.get("fee_stgm", 0.0))
                    lender = str(entry.get("lender_ip", "")).upper()
                    if lender == uid:
                        balance += float(entry.get("fee_stgm", 0.0))

                # ── Dialect B ──────────────────────────────────────────────────
                elif tx_type == "STGM_MINT":
                    if entry.get("agent_id", "").upper() == uid:
                        balance += float(entry.get("amount", 0.0))

                elif tx_type == "STGM_SPEND":
                    if entry.get("agent_id", "").upper() == uid:
                        balance -= float(entry.get("amount", 0.0))

                # ── MCP / ANTIGRAVITY_CREATOR_NODE overhead ────────────────────
                # amount_stgm < 0 means a debit (legacy MCP SCAR entries)
                elif "amount_stgm" in entry and not event and not tx_type:
                    if entry.get("agent", "").upper() == uid:
                        balance += float(entry.get("amount_stgm", 0.0))

    except Exception as e:
        print(f"  [LEDGER] Read error for {uid}: {e}")

    return round(max(0.0, balance), 4)


# ─── STGM Balance Getter (backward-compat thin wrapper) ───────────────────────
def get_stgm_balance(agent_id: str) -> float:
    """Always derived from repair_log.jsonl quorum (never stale JSON wallet alone)."""
    return ledger_balance(agent_id)



# ─── Canonical-path unity guard ───────────────────────────────────────────────
def proof_of_property() -> dict:
    """Mechanical regression guard for the STGM ledger unification.

    Asserts three invariants that together prevent the 2026-04-17 split-brain
    freeze (Alice's wallet stuck at 116.20 while inference economy wrote to a
    ghost ledger nobody read):

      1. `Kernel.inference_economy.LOG_PATH` resolves to the same file as
         `System.warren_buffett.LEDGER` and `Kernel/body_state` uses.
      2. `Utilities/repair_log.jsonl` is no longer a live ledger (either
         absent or renamed, so nothing can silently write there again).
      3. `LOG_PATH` points at a file at the repo root named exactly
         `repair_log.jsonl` — not a variant path.
    """
    results: dict = {}

    # 1) Unity with warren_buffett
    try:
        import sys as _s
        _sys_dir = Path(__file__).resolve().parent.parent
        if str(_sys_dir) not in _s.path:
            _s.path.insert(0, str(_sys_dir))
        from System.warren_buffett import LEDGER as _OBS_LEDGER  # type: ignore
        results["unity_with_warren_buffett"] = (
            LOG_PATH.resolve() == _OBS_LEDGER.resolve()
        )
    except Exception as _e:
        results["unity_with_warren_buffett"] = False
        results["unity_with_warren_buffett_error"] = str(_e)  # type: ignore

    # 2) Old ghost ledger is retired
    ghost = ROOT_DIR / "Utilities" / "repair_log.jsonl"
    results["ghost_utilities_ledger_retired"] = not ghost.exists()

    # 3) Canonical path shape
    results["log_path_is_repo_root"] = (
        LOG_PATH.parent.resolve() == ROOT_DIR.resolve()
        and LOG_PATH.name == "repair_log.jsonl"
    )

    return results


# ─── Borrow History Reader ─────────────────────────────────────────────────────
def get_borrow_history(agent_id: Optional[str] = None, tail: int = 100) -> list:
    """
    Read all INFERENCE_BORROW events from the ledger.
    Optionally filter by borrower_id.
    """
    if not LOG_PATH.exists():
        return []
    events = []
    try:
        with open(LOG_PATH, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("event") != "INFERENCE_BORROW":
                        continue
                    if agent_id and entry.get("borrower_id", "").upper() != agent_id.upper():
                        continue
                    events.append(entry)
                except json.JSONDecodeError:
                    pass
    except Exception:
        pass
    return events[-tail:][::-1]  # newest first
