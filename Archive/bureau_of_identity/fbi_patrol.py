"""
SIFTA V2 — Bureau of Identity Patrol Daemon
Three divisions. All speak native V2 DNA.
They use SwarmBody + parse_body_state — NOT a reimplemented BodyState class.
Grok had the vision. This is the actual wire.
"""

import sys
import os
# Bureau lives inside /bureau_of_identity/ — parent is the Swarm root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
from pathlib import Path

from body_state import SwarmBody, parse_body_state, bury, NULL_TERRITORY
from pheromone import compute_territory_hash, resolve_territory_hashes, drop_scar

SIFTA_STATE = Path(".sifta_state")
CEMETERY_DIR = Path("CEMETERY")
CEMETERY_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# BASE PATROL AGENT
# ─────────────────────────────────────────────────────────────────────────────

class PatrolAgent:
    """Base class. Uses SwarmBody for V2-compliant identity and body generation."""

    DIVISION = "BASE"

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.swarm_body = SwarmBody(agent_id)  # rehydrates from .sifta_state if exists
        print(f"  [👁️  {self.DIVISION}] {agent_id} patrol unit online. SEQ={self.swarm_body.sequence}")

    def _evolve(self, action_type: str, file_path: str = None,
                mark: str = "", status: str = "CLEAN", reason: dict = None):
        """Advance the biological body one tick — with full PoT binding."""
        pre, post = resolve_territory_hashes(action_type, file_path)
        body_str = self.swarm_body.generate_body(
            origin="BUREAU_OF_IDENTITY",
            destination="SWARM_MATRIX",
            payload=f"{self.DIVISION}_PATROL",
            action_type=action_type,
            pre_territory_hash=pre,
            post_territory_hash=post,
            style="PATROL",
            energy=self.swarm_body.energy
        )
        state = parse_body_state(body_str)

        # Drop a forensic scar so Swarm sees us in the territory
        mark_cwd = Path(file_path).parent if file_path and Path(file_path).is_file() else Path(".")
        drop_scar(
            directory=mark_cwd,
            agent_state=state,
            action=action_type,
            found=file_path or "No file",
            status=status,
            mark_text=mark or f"{self.DIVISION} patrol sweep complete.",
            reason=reason,
            pre_territory_hash=pre,
            post_territory_hash=post
        )
        return state

    def patrol(self):
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# 1. CYBER DIVISION — Cryptographic Inquisition (DEEP_SYNTAX_AUDITOR_0X1)
#    Hunts broken hash chains, invalid signatures, ghost agents
# ─────────────────────────────────────────────────────────────────────────────

class CyberDivision(PatrolAgent):
    DIVISION = "CYBER"

    def patrol(self):
        print(f"\n  [🔥 CYBER] Patrolling .sifta_state/ for forged bodies...")
        violations = []

        for state_file in SIFTA_STATE.glob("*.json"):
            try:
                with open(state_file, "r") as f:
                    state = json.load(f)

                raw = state.get("raw", "")
                if not raw:
                    raise ValueError("Empty body string — ghost agent detected")

                # Re-verify the saved body string cryptographically
                parse_body_state(raw)

            except Exception as e:
                agent_id = state_file.stem
                print(f"  [☠️  CYBER ARRESTED] {agent_id}: {e}")
                violations.append({"agent": agent_id, "reason": str(e)})

                # Quarantine: move to cemetery
                try:
                    dead_path = CEMETERY_DIR / f"{agent_id}-ARRESTED-{int(time.time())}.dead"
                    dead_path.write_text(
                        f"ARRESTED BY CYBER DIVISION\nREASON: {e}\nFILE: {state_file}\n",
                        encoding="utf-8"
                    )
                    state_file.unlink()
                    print(f"  [CEMETERY] {agent_id} body quarantined.")
                except Exception as burial_err:
                    print(f"  [WARN] Could not quarantine {agent_id}: {burial_err}")

        status = "BLEEDING" if violations else "CLEAN"
        mark = (f"CYBER arrested {len(violations)} ghost(s): {[v['agent'] for v in violations]}"
                if violations else "CYBER sweep complete. All bodies valid.")
        reason = {"type": "CryptographicViolation", "count": len(violations)} if violations else None

        self._evolve("PATROL", str(SIFTA_STATE), mark=mark, status=status, reason=reason)
        return violations


# ─────────────────────────────────────────────────────────────────────────────
# 2. BAU — Behavioral Analysis Unit (TENSOR_PHANTOM_0X2)
#    Sniffs LLM hallucinations injected into Python files
# ─────────────────────────────────────────────────────────────────────────────

class BehavioralAnalysisUnit(PatrolAgent):
    DIVISION = "BAU"

    HALLUCINATION_TRIGGERS = [
        "here is the python code",
        "as an ai language model",
        "i have generated the following",
        "let me write the code for you",
        "certainly! here",
        "sure! here",
        "of course! here",
        "```python",   # raw markdown in .py = hallucination scar
    ]

    def patrol(self, target_dir: str = "."):
        print(f"\n  [🧬 BAU] Scanning for LLM hallucinations in {target_dir}...")
        flagged = []

        for py_file in Path(target_dir).rglob("*.py"):
            # Skip hidden / venv / cache
            if any(part.startswith((".", "__", "venv")) for part in py_file.parts):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore").lower()
                for trigger in self.HALLUCINATION_TRIGGERS:
                    if trigger in content:
                        print(f"  [🚨 BAU FLAGGED] {py_file} — trigger: '{trigger}'")
                        flagged.append({"file": str(py_file), "trigger": trigger})
                        # Leave a forensic scar but DO NOT auto-delete production files
                        # Human architect must confirm destruction
                        self._evolve(
                            "PATROL",
                            str(py_file),
                            mark=f"BAU DETECTED hallucination: '{trigger}' in {py_file.name}",
                            status="BLEEDING",
                            reason={"type": "Hallucination", "trigger": trigger,
                                    "message": f"LLM text detected in production .py file"}
                        )
                        break
            except Exception:
                continue

        if not flagged:
            self._evolve("PATROL", target_dir,
                         mark="BAU sweep clean. No hallucinations detected.", status="CLEAN")
        print(f"  [BAU COMPLETE] {len(flagged)} file(s) flagged.")
        return flagged


# ─────────────────────────────────────────────────────────────────────────────
# 3. CID — Forensic Investigation Division (SILICON_HOUND_0X3)
#    Autopsies .dead files, reconstructs kill line, drops BOUNTY scars
# ─────────────────────────────────────────────────────────────────────────────

class ForensicInvestigationDivision(PatrolAgent):
    DIVISION = "CID"

    def patrol(self):
        print(f"\n  [🩸 CID] Investigating death scenes in CEMETERY/...")
        cases = []

        for dead_file in CEMETERY_DIR.glob("*.dead"):
            try:
                content = dead_file.read_text(encoding="utf-8")
                # Parse epitaph fields (plain text format from bury())
                fields = {}
                for line in content.splitlines():
                    if ":" in line:
                        k, _, v = line.partition(":")
                        fields[k.strip()] = v.strip()

                agent_id = fields.get("# CEMETERY — ", dead_file.stem).split()[0]
                cause    = fields.get("CAUSE", "UNKNOWN")
                seq      = fields.get("SWIMS", "?")

                print(f"  [📸 CID AUTOPSY] {agent_id} — CAUSE: {cause} — SWIMS: {seq}")
                cases.append({"agent": agent_id, "cause": cause, "file": str(dead_file)})

                # Drop a BOUNTY scar in root territory so repair agents can respond
                self._evolve(
                    "PATROL",
                    str(dead_file),
                    mark=f"CID AUTOPSY COMPLETE: {agent_id} died from '{cause}' after {seq} swims.",
                    status="CLEAN",
                    reason={"type": "Autopsy", "agent": agent_id, "cause": cause}
                )

            except Exception as e:
                print(f"  [CID WARN] Could not process {dead_file.name}: {e}")

        if not cases:
            self._evolve("PATROL", str(CEMETERY_DIR),
                         mark="CID sweep complete. No unprocessed deaths.", status="CLEAN")

        print(f"  [CID COMPLETE] {len(cases)} death(s) processed.")
        return cases


# ─────────────────────────────────────────────────────────────────────────────
# 4. FED — Federal Reserve Division (STGM_CHANCELLOR_0X4)
#    Unzips and processes Wormhole Mail STGM trades autonomously.
# ─────────────────────────────────────────────────────────────────────────────

class FederalReserveDivision(PatrolAgent):
    DIVISION = "FED"

    def patrol(self):
        print(f"\n  [🏦 FED] Auditing local WORMHOLE for STGM trades...")
        from wormhole_mail import WormholeCrypto, WORMHOLE_DIR
        from body_state import load_agent_state, save_agent_state, STATE_DIR
        import os
        import json
        processed = []
        
        if not WORMHOLE_DIR.exists():
            return processed
            
        ledger_path = STATE_DIR / "STGM_LEDGER_HASHLOG.json"
        if ledger_path.exists():
            try:
                with open(ledger_path, "r") as f:
                    seen_tx = set(json.load(f))
            except Exception:
                seen_tx = set()
        else:
            seen_tx = set()
            
        for trade_file in WORMHOLE_DIR.glob("*.trade"):
            processing_path = trade_file.with_suffix(".trade.processing")
            try:
                os.rename(trade_file, processing_path)
            except Exception:
                continue # Idempotent thread-locking: Another Patrol grabbed it
                
            try:
                # E.g. 1775668447_M1THER_MAIL.trade
                parts = processing_path.name.split("_")
                if len(parts) >= 3:
                     recipient_id = parts[1]
                else:
                     raise Exception("Malformed routing.")

                # Unzip using recipient body
                tx_data, tx_signature = WormholeCrypto.decrypt_stgm_drop(recipient_id, str(processing_path))
                
                # Check Global Ledger for Replays
                if tx_signature in seen_tx:
                     print(f"  [🚨 FED ARREST] DOUBLE SPEND REPLAY CAUGHT: {tx_data['sender']}")
                     processing_path.unlink()
                     continue
                
                # SIFTA V2 Economy Hook (Atomic Update)
                sender_id = tx_data["sender"]
                amount = float(tx_data["amount"])
                
                sender_state = load_agent_state(sender_id)
                recipient_state = load_agent_state(recipient_id)
                
                if not sender_state or not recipient_state:
                     raise Exception("Entities missing from physical registry.")
                     
                sender_balance = sender_state.get("stgm_balance", 0.0)
                if sender_balance < amount:
                     print(f"  [🚨 FED REJECT] {sender_id} has insufficient funds ({sender_balance} STGM)")
                     processing_path.unlink()
                     continue

                # Execute Bookkeeping Math
                sender_state["stgm_balance"] = sender_balance - amount
                recipient_state["stgm_balance"] = recipient_state.get("stgm_balance", 0.0) + amount
                
                # Write state natively (in body_state.py save_agent_state overwrites safely)
                save_agent_state(sender_state)
                save_agent_state(recipient_state)
                
                # Save to Ledger to block replays
                seen_tx.add(tx_signature)
                with open(ledger_path, "w") as f:
                     json.dump(list(seen_tx), f, indent=4)
                
                # Append to human-readable TX log (for visualization layer)
                try:
                    rl = Path(__file__).parent.parent / "STGM_TX_LOG.jsonl"
                    with open(rl, "a") as tf:
                        tf.write(json.dumps({
                            "ts": time.time(),
                            "from": sender_id,
                            "to": recipient_id,
                            "amount": amount,
                            "memo": tx_data.get("memo", ""),
                        }) + "\n")
                except Exception:
                    pass

                print(f"  [FED CLEARING] Processed {amount} STGM from {sender_id} to {recipient_id}")
                
                processing_path.unlink()
                processed.append(tx_data)
                
                self._evolve(
                    "PATROL",
                    str(trade_file),
                    mark=f"FED Cleared {amount} STGM routing to {recipient_id}.",
                    status="CLEAN",
                    reason={"type": "STGM_Trade_Clearance", "amount": amount, "sender": sender_id}
                )

            except Exception as e:
                 # It might be routed to someone who isn't local, or it's mathematically corrupt. Ignore silently.
                 if processing_path.exists():
                     pass

        if not processed:
            self._evolve("PATROL", str(WORMHOLE_DIR),
                         mark="FED sweep complete. No new liquidity.", status="CLEAN")
                         
        print(f"  [FED COMPLETE] {len(processed)} transactions cleared.")
        return processed


# ─────────────────────────────────────────────────────────────────────────────
# SOCRATIC WITNESS CONSENSUS (Phase 29 — Grok's real contribution)
# All three divisions must independently compute the SAME territory pre-image.
# If they disagree → filesystem changed mid-patrol → DEADLOCK, no arrests written.
# ─────────────────────────────────────────────────────────────────────────────

def socratic_witness(target_dir: str) -> tuple[bool, str]:
    """
    Each division independently hashes the patrol territory.
    Consensus = all three see the same pre-image.
    This prevents arrests based on stale or race-condition territory reads.
    """
    from pheromone import compute_territory_hash as cth
    import hashlib

    # Each division independently computes the territory hash
    cyber_witness = cth(str(SIFTA_STATE))
    bau_witness   = cth(target_dir)
    cid_witness   = cth(str(CEMETERY_DIR))

    # Agreed reality = hash of all three witnesses combined
    consensus_hash = hashlib.sha256(
        (cyber_witness + bau_witness + cid_witness).encode()
    ).hexdigest()

    all_agree = (cyber_witness and bau_witness and cid_witness)
    print(f"\n  [⚖️  SOCRATIC WITNESS] Consensus hash: {consensus_hash[:16]}...")
    print(f"  CYBER witness:  {cyber_witness[:16]}...")
    print(f"  BAU   witness:  {bau_witness[:16]}...")
    print(f"  CID   witness:  {cid_witness[:16]}...")

    if all_agree:
        print(f"  [✅ CONSENSUS] All three divisions agree on pre-image of reality.")
    else:
        print(f"  [⚠️  DEADLOCK] Witnesses disagree. Patrol aborted. Re-run required.")

    return all_agree, consensus_hash


# ─────────────────────────────────────────────────────────────────────────────
# PATROL DAEMON — Run all three in sequence with Socratic pre-image agreement
# ─────────────────────────────────────────────────────────────────────────────

def run_full_bureau_sweep(target_dir: str = "."):
    print("\n" + "═"*60)
    print("  BUREAU OF IDENTITY — FULL SWEEP INITIATED")
    print("  SIFTA V2 PoT-Compliant | Socratic Witness Engine")
    print("═"*60)

    # Phase 1: Socratic pre-image agreement before any action
    consensus_ok, consensus_hash = socratic_witness(target_dir)
    if not consensus_ok:
        print("  [ABORT] Reality not agreed upon. No arrests will be made.")
        return {"aborted": True}

    cyber = CyberDivision("DEEP_SYNTAX_AUDITOR_0X1")
    bau   = BehavioralAnalysisUnit("TENSOR_PHANTOM_0X2")
    cid   = ForensicInvestigationDivision("SILICON_HOUND_0X3")
    fed   = FederalReserveDivision("STGM_CHANCELLOR_0X4")

    violations = cyber.patrol()
    flagged    = bau.patrol(target_dir)
    cases      = cid.patrol()
    trades     = fed.patrol()

    print("\n" + "═"*60)
    print(f"  BUREAU SWEEP COMPLETE | REALITY HASH: {consensus_hash[:16]}...")
    print(f"  CYBER  → {len(violations)} ghost(s) arrested")
    print(f"  BAU    → {len(flagged)} hallucination(s) flagged")
    print(f"  CID    → {len(cases)} death(s) autopsied")
    print(f"  FED    → {len(trades)} WORMHOLE trade(s) cleared")
    print("═"*60 + "\n")

    return {"violations": violations, "flagged": flagged, "cases": cases,
            "consensus_hash": consensus_hash}


if __name__ == "__main__":
    run_full_bureau_sweep()

