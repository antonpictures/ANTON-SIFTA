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
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

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
    from ledger_append import append_ledger_line
except ImportError:
    def append_ledger_line(path, event):  # type: ignore
        with open(path, "a") as f:
            f.write(json.dumps(event) + "\n")
# ──────────────────────────────────────────────────────────────────────────────

ROOT_DIR  = Path(__file__).parent
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
    COUCH PROTOCOL ENFORCEMENT
    Hallucination / inference spend is ONLY allowed when NOT in protected states.
    Returns True only if the agent may burn real inference energy.
    """
    agent_id = state.get('id', 'unknown')
    
    # 1. Protected states — zero spend, zero mutation, zero drift
    if state.get("style") in {"COUCH", "OBSERVE", "HYPOTHESIS", "LATENT"}:
        print(f"[🛡️ COUCH PROTOCOL] {agent_id} in {state['style']} — inference spend DENIED.")
        return False

    # 2. Check actual energy balance (weed inference limit)
    # Using 'stgm_balance' as the inference energy pool based on inference_economy logic
    current_energy = float(state.get("stgm_balance", 100.0))
    if current_energy < cost:
        print(f"[⚡ LOW WEED] {agent_id} only has {current_energy:.2f} left — spend DENIED.")
        return False

    # 3. All clear — safe to spend
    print(f"[✅ INFERENCE OK] {agent_id} may spend {cost} inference. Remaining: {current_energy - cost:.2f}")
    return True


# ─── Fee Calculator ────────────────────────────────────────────────────────────
def calculate_fee(tokens: int) -> float:
    """
    Proof of Compute fee in STGM. Scaled by the current Deflationary Era.
    Minimum cost dynamically deflates alongside the halving curve.
    """
    multiplier = get_current_halving_multiplier()
    base_fee = (tokens / 100) + 1.0
    return round(base_fee * multiplier, 4)


def mint_reward(agent_id: str, action: str, file_repaired: str) -> dict:
    """
    Proof-of-Healing reward minting. Called after a successful swarm repair.
    Provides a base baseline reward multiplied by the current Deflationary Halving Era.
    """
    multiplier = get_current_halving_multiplier()
    base_reward = 1.0  # Base reward for a fixed node is 1.0 STGM
    minted_amount = round(base_reward * multiplier, 4)

    state_path = STATE_DIR / f"{agent_id.upper()}.json"
    state = {}
    if state_path.exists():
        try:
            with open(state_path, "r") as f:
                state = json.load(f)
        except Exception:
            pass

    current_stgm = float(state.get("stgm_balance", 0.0))
    new_stgm     = round(current_stgm + minted_amount, 4)

    state["stgm_balance"] = new_stgm
    if state:
        try:
            with open(state_path, "w") as f:
                json.dump(state, f, indent=2)
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
    # ── Load borrower state ──────────────────────────────────────────────────
    state_path = STATE_DIR / f"{borrower_id.upper()}.json"
    state = {}
    if state_path.exists():
        try:
            with open(state_path, "r") as f:
                state = json.load(f)
        except Exception:
            pass

    current_stgm = float(state.get("stgm_balance", 0.0))
    new_stgm     = max(0.0, round(current_stgm - fee_stgm, 2))

    # ── Update Borrower state ────────────────────────────────────────────────
    state["stgm_balance"] = new_stgm
    if state:
        try:
            with open(state_path, "w") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass
            
    # ── Credit Lender state ──────────────────────────────────────────────────
    lender_path = STATE_DIR / f"{lender_node_ip.upper()}.json"
    lender_state = {}
    if lender_path.exists():
        try:
            with open(lender_path, "r") as f:
                lender_state = json.load(f)
        except Exception:
            pass
            
    lender_current = float(lender_state.get("stgm_balance", 0.0))
    lender_new = round(lender_current + fee_stgm, 2)
    lender_state["stgm_balance"] = lender_new
    
    if lender_state:
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
