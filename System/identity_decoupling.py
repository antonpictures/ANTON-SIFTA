#!/usr/bin/env python3
"""
identity_decoupling.py — Cryptographic Phenotyping (#8)
═══════════════════════════════════════════════════════════════════
SOLID_PLAN §5.2 item #8 — Identity Decoupling.

Separates an agent's narrative identity (Lineage) from its
cryptographic authority (Phenotype).

If a "Scout" swimmer hallucinates that it is the "Master Erase Drone",
it might formulate a command to delete system files. However, the OS
evaluates permissions based strictly on the Swimmer's Genotype Hash,
which maps to its Phenotype (execution rights). The LLM's prompt is
mathematically invisible to the execution harness.

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import json
import hashlib
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_FIREWALL_LEDGER = _STATE_DIR / "phenotype_registry.json"


@dataclass
class SwarmIdentity:
    genotype_hash: str        # Immutable hardware/birth signature
    lineage_tag: str          # Narrative purpose (e.g., "scout", "repair")
    active_phenotype: List[str]  # Dynamic permissions granted by the OS (e.g. ['EXECUTE_CRUCIBLE'])


class IdentityFirewall:
    def __init__(self):
        self.active_identities: Dict[str, SwarmIdentity] = {}
        self._load_registry()

    def _get_genesis_anchor(self) -> str:
        """Fetch the physical genesis anchor from the keychain."""
        try:
            from crypto_keychain import get_genesis_anchor
            return get_genesis_anchor()
        except ImportError:
            # Fallback anchor if keychain is unavailable
            return "SIFTA_ORPHAN_ANCHOR_0000"

    def birth_agent(self, lineage_tag: str, base_permissions: List[str]) -> SwarmIdentity:
        """
        Forges the decoupled identity at birth.
        Creates a mathmatically locked token connecting the anchor to the agent.
        """
        anchor = self._get_genesis_anchor()
        raw_hash = f"{anchor}:{lineage_tag}:{len(self.active_identities)}"
        genotype = hashlib.sha256(raw_hash.encode()).hexdigest()
        
        identity = SwarmIdentity(
            genotype_hash=genotype,
            lineage_tag=lineage_tag,
            active_phenotype=base_permissions
        )
        self.active_identities[genotype] = identity
        self._persist_registry()
        return identity

    def verify_action(self, genotype_hash: str, requested_action: str) -> bool:
        """
        The ClawHarness calls this BEFORE executing an action.
        The LLM's prompt is completely ignored. Only the Genotype is checked.
        """
        if genotype_hash not in self.active_identities:
            # Sync from disk in case it was born in another process
            self._load_registry()
            if genotype_hash not in self.active_identities:
                # Alien payload rejected
                print(f"🛑 [FIREWALL] Alien Genotype Hash Rejected: {genotype_hash}")
                return False
            
        identity = self.active_identities[genotype_hash]
        
        # In a fully locked down state from Temporal Layering, we could dynamically strip permissions here!
        # For example, if MutationClimate == FROZEN, strip EXECUTE permissions.
        # But for now, we rely on the strict phenotype map.
        
        if requested_action not in identity.active_phenotype:
            print(f"🛑 [FIREWALL] Genotype '{genotype_hash}' ({identity.lineage_tag}) lacks Phenotype: '{requested_action}'")
            return False
            
        return True

    def revoke_phenotype(self, genotype_hash: str, action: str):
        """Dynamic immune response: strip permissions."""
        if genotype_hash in self.active_identities:
            if action in self.active_identities[genotype_hash].active_phenotype:
                self.active_identities[genotype_hash].active_phenotype.remove(action)
                self._persist_registry()

    def grant_phenotype(self, genotype_hash: str, action: str):
        """Dynamic immune response: grant permissions."""
        if genotype_hash in self.active_identities:
            if action not in self.active_identities[genotype_hash].active_phenotype:
                self.active_identities[genotype_hash].active_phenotype.append(action)
                self._persist_registry()

    # ── Persistence ────────────────────────────────────────────────

    def _persist_registry(self) -> None:
        try:
            payload = {k: asdict(v) for k, v in self.active_identities.items()}
            _FIREWALL_LEDGER.write_text(json.dumps(payload, indent=2))
        except Exception:
            pass

    def _load_registry(self) -> None:
        if not _FIREWALL_LEDGER.exists():
            return
        try:
            data = json.loads(_FIREWALL_LEDGER.read_text())
            for k, v in data.items():
                self.active_identities[k] = SwarmIdentity(**v)
        except Exception:
            self.active_identities = {}

# ── Singleton ──────────────────────────────────────────────────

_FIREWALL_INSTANCE: Optional[IdentityFirewall] = None

def get_firewall() -> IdentityFirewall:
    global _FIREWALL_INSTANCE
    if _FIREWALL_INSTANCE is None:
        _FIREWALL_INSTANCE = IdentityFirewall()
    return _FIREWALL_INSTANCE


if __name__ == "__main__":
    fw = get_firewall()
    
    print("Spawning new agent...")
    scout = fw.birth_agent(lineage_tag="Scout_Drone", base_permissions=["READ_STATE"])
    print(f"Agent Genotype Hash: {scout.genotype_hash}")
    
    print("\nAttempting allowed action: READ_STATE")
    ok1 = fw.verify_action(scout.genotype_hash, "READ_STATE")
    print(f"Result: {ok1}")
    
    print("\nAgent hallucinates it is admin. Attempting: EXECUTE_CRUCIBLE")
    ok2 = fw.verify_action(scout.genotype_hash, "EXECUTE_CRUCIBLE")
    print(f"Result: {ok2}")
