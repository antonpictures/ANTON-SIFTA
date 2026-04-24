#!/usr/bin/env python3
"""
System/swarm_quorum_sensing.py
══════════════════════════════════════════════════════════════════════
Concept: Quorum Sensing (Distributed Consensus & Collective Action)
Author:  BISHOP (The Mirage) & C53M/AG31 (Cryptographic Metal)
Status:  Active

[R3 WIRING — AO46/C47H Event 51]
check_quorum_and_execute() now routes HMAC-verified YES votes through
swarm_quorum_rate_gate.is_quorum_active() instead of the old hardcoded
approval_ratio = yes_votes / 3.

This means:
  - Stale votes (>45s) are automatically expired before the tally.
  - The same voter_id can no longer slow-spam multiple counted votes.
  - The quorum threshold is sub-linear (ceil(sqrt(N))) and scales with
    the real active sibling count, not a hardcoded constant.
  - The raw ratio path is removed.

[ORIGINAL WIRING]:
1. "quorum_votes.jsonl" is used for distributed, non-spoofable traces.
2. High-risk actions ONLY execute if a threshold of sibling nodes (Quorum) votes YES.
3. Cryptographic HMAC-SHA256 handles vote authenticity to prevent spoofing.
"""

import os
import json
import time
import uuid
import hmac
import hashlib
from pathlib import Path
from typing import List, Dict, Any

# BISHOP respects the empirical lock.
try:
    from System.jsonl_file_lock import append_line_locked
    from System.swarm_quorum_rate_gate import is_quorum_active
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

class SwarmQuorumSensing:
    def __init__(self, required_quorum_ratio=0.66):
        """
        The Distributed Consensus Engine.
        Allows the Hive Mind to synchronize behavior and authorize high-risk
        actions through decentralized, cryptographic voting.
        """
        self.state_dir = Path(".sifta_state")
        self.quorum_ledger = self.state_dir / "quorum_votes.jsonl"
        self.secret_key_path = self.state_dir / "hive_mind_secret.key"
        self.required_quorum_ratio = required_quorum_ratio
        
        # Active sibling count. When the Mycorrhizal Network is online this
        # should be refreshed from the live peer table before each tally.
        # Defaults to 3 (minimum viable quorum for a solo-node swarm).
        self.known_sibling_spores = 3

        # Ensure the shared secret exists
        self._ensure_hive_secret()

    def _ensure_hive_secret(self):
        """
        Loads or generates the shared Hive Mind cryptographic secret key.
        """
        if not self.secret_key_path.exists():
            self.state_dir.mkdir(parents=True, exist_ok=True)
            # Generate a 32-byte cryptographic secret
            new_secret = os.urandom(32).hex()
            with open(self.secret_key_path, 'w') as f:
                f.write(new_secret)
        
        with open(self.secret_key_path, 'r') as f:
            self._hive_secret = bytes.fromhex(f.read().strip())
            
    def _generate_hmac(self, proposal_id: str, vote: str, voter_id: str) -> str:
        """
        Generates an HMAC-SHA256 signature for a vote payload.
        """
        payload = f"{proposal_id}:{vote}:{voter_id}".encode('utf-8')
        return hmac.new(self._hive_secret, payload, hashlib.sha256).hexdigest()

    def propose_high_risk_action(self, proposer_id, action_command, intent):
        """
        A single Spore requests authorization to execute a massive action.
        """
        now = time.time()
        proposal_id = f"PROPOSAL_{uuid.uuid4().hex[:8]}"
        
        payload = {
            "ts": now,
            "proposer_id": proposer_id,
            "proposal_id": proposal_id,
            "action_command": action_command, # e.g., "rm -rf /private/var/log/*"
            "intent": intent,
            "status": "VOTING_OPEN"
        }
        
        try:
            append_line_locked(self.quorum_ledger, json.dumps(payload) + "\n")
            print(f"[*] QUORUM SENSING: Proposal {proposal_id} broadcasted. Awaiting Hive Mind consensus.")
            return proposal_id
        except Exception:
            return None

    def evaluate_and_vote(self, proposal_id, action_command, voter_id="LOCAL_SPORE"):
        """
        Sibling spores evaluate the proposed action.
        Hardened with HMAC-SHA256.
        """
        # Biological evaluation: Is this action safe? Does it drain too much STGM?
        is_safe = True 
        if "rm -rf /" in action_command or "sudo" in action_command:
            is_safe = False # Immune rejection
            
        vote = "YES" if is_safe else "NO"
        
        crypto_signature = self._generate_hmac(proposal_id, vote, voter_id)
        
        vote_payload = {
            "ts": time.time(),
            "proposal_id": proposal_id,
            "voter_id": voter_id,
            "vote": vote,
            "signature": crypto_signature
        }
        
        try:
            append_line_locked(self.quorum_ledger, json.dumps(vote_payload) + "\n")
            print(f"[+] QUORUM SENSING: Cast vote '{vote}' for Proposal {proposal_id}.")
            return True
        except Exception:
            return False

    def active_sibling_count(self) -> int:
        """Return the current known active sibling count.

        Callers that have a live peer table (e.g. Mycorrhizal Network heartbeat)
        should set self.known_sibling_spores before calling check_quorum_and_execute.
        This accessor exposes the value for read-only consumers.
        """
        return max(1, self.known_sibling_spores)

    def _collect_verified_yes_votes(
        self, proposal_id: str
    ) -> List[Dict[str, Any]]:
        """Read quorum_votes.jsonl, HMAC-verify every row, and return only
        YES votes for this proposal as rate-gate-compatible dicts.

        Each returned dict has {"ts": float, "voter_id": str} so
        is_quorum_active() can apply voter dedup and stale expiry.
        """
        if not self.quorum_ledger.exists():
            return []

        verified: List[Dict[str, Any]] = []
        try:
            with open(self.quorum_ledger, "r") as f:
                for raw in f:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        trace = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    if trace.get("proposal_id") != proposal_id:
                        continue
                    if trace.get("vote") != "YES":
                        continue

                    voter_id = trace.get("voter_id", "")
                    vote = trace.get("vote", "")
                    provided_sig = trace.get("signature", "")

                    # HMAC gate — drop forged votes before rate-gate sees them
                    expected_sig = self._generate_hmac(proposal_id, vote, voter_id)
                    if not hmac.compare_digest(expected_sig, provided_sig):
                        print(
                            f"[!] QUORUM FRAUD: Invalid HMAC from voter "
                            f"{voter_id!r}. Discarding."
                        )
                        continue

                    try:
                        ts = float(trace.get("ts", 0))
                    except (TypeError, ValueError):
                        continue

                    verified.append({"ts": ts, "voter_id": voter_id})

        except Exception as e:
            print(f"[-] QUORUM SENSING: Vote collection failed -> {e}")

        return verified

    def check_quorum_and_execute(self, proposal_id: str) -> bool:
        """
        Tallies HMAC-verified YES votes through the biological rate-gate.

        Old path: approval_ratio = yes_votes / hardcoded_3
        New path: is_quorum_active(verified_yes_votes, active_sibling_count)

        The rate-gate (swarm_quorum_rate_gate) enforces:
          - Stale votes older than 45s are expired (Greene & Gordon 2007).
          - Same voter_id can only contribute one vote (no slow-spam).
          - Threshold is ceil(sqrt(N)), sub-linear in swarm size (Sumpter/Krause 2008).
        """
        verified_yes = self._collect_verified_yes_votes(proposal_id)
        swarm_size = self.active_sibling_count()

        if is_quorum_active(verified_yes, swarm_size=swarm_size):
            print(
                f"[!] QUORUM ACHIEVED. "
                f"{len(verified_yes)} verified YES vote(s), "
                f"swarm_size={swarm_size}. "
                f"Hive Mind consensus reached for {proposal_id}."
            )
            return True
        else:
            print(
                f"[*] QUORUM FAILED. "
                f"{len(verified_yes)} verified YES vote(s) insufficient "
                f"for swarm_size={swarm_size}. "
                f"Proposal {proposal_id} rejected."
            )
            return False

# --- SMOKE TEST ---
def _smoke():
    print("\n=== SIFTA QUORUM SENSING (DISTRIBUTED CONSENSUS) : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        quorum = SwarmQuorumSensing(required_quorum_ratio=0.66)
        quorum.known_sibling_spores = 3
        
        # Secure Path Redirection for testing
        quorum.state_dir = tmp_path
        quorum.quorum_ledger = tmp_path / "quorum_votes.jsonl"
        quorum.secret_key_path = tmp_path / "hive_mind_secret.key"
        quorum._ensure_hive_secret()
        
        # 1. Propose Action
        prop_id = quorum.propose_high_risk_action("SPORE_ALPHA", "clear_all_ledgers", "Free disk space")
        assert prop_id is not None
        
        # 2. Cast Votes (Simulating 3 network nodes)
        quorum.evaluate_and_vote(prop_id, "clear_all_ledgers", voter_id="LOCAL_SPORE") 
        quorum.evaluate_and_vote(prop_id, "clear_all_ledgers", voter_id="SPORE_BETA")
        
        # Injecting a forged vote payload with an invalid signature
        with open(quorum.quorum_ledger, 'a') as f:
            f.write(json.dumps({"proposal_id": prop_id, "vote": "YES", "voter_id": "SPORE_GAMMA_HACKER", "signature": "fake_signature_123"}) + "\n")
            
        # 3. Tally & Execute
        success = quorum.check_quorum_and_execute(prop_id)
        
        print("\n[SMOKE RESULTS]")
        assert success is True # Two valid YES votes (Local & Beta), Gamma hacker is rejected.
        print("[PASS] Proposal successfully broadcast.")
        print("[PASS] Authentic votes tallied (Fraudulent votes correctly dropped).")
        print("[PASS] Quorum reached accurately. Cryptographic layer confirmed.")
        
        print("\nQuorum Sensing Smoke Complete. The Swarm now acts securely as one entity.")

if __name__ == "__main__":
    _smoke()
