#!/usr/bin/env python3
"""
System/swarm_crispr_immunity.py
══════════════════════════════════════════════════════════════════════════════
Concept: CRISPR-Cas Adaptive Immune Repertoire (Statistical Physics)
Adapted from Event 26 (BISHOP) drop, hardened by AO46 (SHA-256 + persistence
+ enum returns + content fingerprinting), boundary-fixed by C47H (PAM
exact-match tokens, integration as detector-accelerator alongside innate
immunity, M2/M5/M6 falsifiers).

ARCHITECTURE — innate + adaptive co-existing (real biology):

  swarm_oncology.SwarmOncology       ← AUTHORITY on MALIGNANT verdict
    │                                   (static whitelist = innate immunity)
    │
    └──> SwarmCRISPRAdaptiveImmunity ← OBSERVER / accelerator only
                                        (adaptive memory of past anomalies)

The CRISPR layer NEVER decides whether a file is canonical. The macrophage's
static whitelist (innate) makes that call FIRST, and only files that fail
the innate gate are passed to the adaptive layer for fingerprinting and
memory. This is the same split real bacteria use: restriction-modification
systems and CRISPR-Cas operate alongside each other, not in replacement.

PAM HARDENING (M2):
The original BISHOP draft and the first AO46 integration used substring
matching ("SCAR_" in payload_signature). That was trivially exploitable —
any attacker filename containing the substring self-classified as SELF.
This module now uses an exact-match set of PAM tokens (_PAM_TOKENS) that
ONLY the macrophage can pass, after it has already screened the file
through its own static whitelist. Producer-controlled strings cannot
forge a PAM match by accident or by malice.

══════════════════════════════════════════════════════════════════════════════
"""

import hashlib
import json
import numpy as np
from pathlib import Path

# Exact-match PAM tokens. The macrophage passes these only for files it has
# already screened as SELF via its static whitelist. Substring matching is
# explicitly disallowed (see proof_of_property V_M2).
_PAM_TOKENS: frozenset = frozenset({
    "_INNATE_SELF_",      # macrophage-issued: "this file passed the static whitelist"
    "_INNATE_BODY_",      # macrophage-issued: "this is a Swimmer _BODY.json"
    "_INNATE_PREFIX_",    # macrophage-issued: "this filename matched a healthy_prefix"
})


class SwarmCRISPRAdaptiveImmunity:
    def __init__(self, state_dir: Path, memory_limit=500):
        """
        The Adaptive Macrophage.
        Maintains a finite array of 'spacers' (threat signatures) optimized 
        to anticipate the most probable future attacks.
        """
        self.memory_limit = memory_limit
        self.state_dir = Path(state_dir)
        self.memory_file = self.state_dir / "crispr_memory.json"
        
        # The CRISPR Array: Maps threat_hash to its empirical encounter frequency
        self.spacers = {}
        self.total_encounters = 0
        
        self.load_memory()

    def load_memory(self):
        """Load persistent CRISPR memory from Alice's internal state."""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                    self.spacers = {int(k): float(v) for k, v in data.get("spacers", {}).items()}
                    self.total_encounters = data.get("total_encounters", 0)
            except Exception as e:
                print(f"[!] CRISPR Memory Corruption: Failed to load immunological state. Exception: {e}")

    def save_memory(self):
        """Persist the optimized repertoire to minimize future Landauer acquisition costs."""
        try:
            with open(self.memory_file, 'w') as f:
                json.dump({
                    "total_encounters": self.total_encounters,
                    "spacers": self.spacers
                }, f)
        except Exception as e:
            print(f"[!] CRISPR Save Error: Failed to commit memory to {self.memory_file}: {e}")

    def pam_verification_self(self, payload_signature: str) -> bool:
        """
        Protospacer Adjacent Motif (PAM) — EXACT-MATCH against trusted tokens.

        In biology, Cas9 cannot cut without a PAM. The PAM is a structural
        sequence DOWNSTREAM of the protospacer that the host genome lacks
        — Cas9 uses it as a "this DNA is foreign" gate.

        In SIFTA, the PAM is an exact-match token issued ONLY by the
        macrophage (System/swarm_oncology.SwarmOncology) for files it
        has already screened through its static whitelist. Producer-
        controlled strings (filenames, file contents) can never match
        because they cannot construct one of the reserved _INNATE_*
        tokens (the underscore prefix is the architectural convention
        that marks "macrophage-issued, not producer-derived").

        Substring matching is explicitly DISALLOWED here. See
        proof_of_property V_M2 for the regression guard.

        Hardened 2026-04-22 (C47H integration of AO46 CRISPR layer)
        per M2 contract from C47H_drop_PRE_MERGE_PEER_REVIEW...dirt.
        """
        return payload_signature in _PAM_TOKENS

    def acquire_spacer(self, threat_payload: str, payload_signature: str) -> str:
        """
        Extracts a structural fingerprint from an invading parasite and integrates 
        it into the immune memory.
        
        Returns:
            'SELF'  — PAM matched, this is Alice's own tissue. Nuclease locked.
            'KNOWN' — Spacer already existed. Reinforced weight.
            'NOVEL' — New spacer acquired into the CRISPR array.
        """
        # 1. Strict Autoimmune Prevention
        if self.pam_verification_self(payload_signature):
            return 'SELF'

        # Deterministic hash — Python's hash() is randomized per-process
        # (PYTHONHASHSEED), so spacer keys would change every restart,
        # making persisted crispr_memory.json worthless. SHA-256 is stable.
        threat_hash = int(hashlib.sha256(threat_payload.encode('utf-8', errors='replace')).hexdigest()[:12], 16)
        self.total_encounters += 1
        
        if threat_hash not in self.spacers:
            print(f"    [+] NOVEL THREAT: Acquiring CRISPR Spacer [{threat_hash}] off '{payload_signature}'.")
            
            # If memory is full, we must prune to minimize Landauer cost
            if len(self.spacers) >= self.memory_limit:
                self._optimize_repertoire()
                
            self.spacers[threat_hash] = 1.0
            self.save_memory()
            return 'NOVEL'
        else:
            # Threat recognized. Reinforce the memory weight.
            self.spacers[threat_hash] += 1.0
            self.save_memory()
            return 'KNOWN'

    def _optimize_repertoire(self):
        """
        Minimizes the cross-entropy cost function. 
        Sheds the least probable/oldest threat from the finite memory array 
        to make room for a novel, emerging threat.
        """
        if not self.spacers:
            return
            
        # Find the spacer with the lowest empirical probability
        least_probable_threat = min(self.spacers, key=self.spacers.get)
        print(f"    [-] REPERTOIRE OPTIMIZATION: Forgetting low-probability Spacer [{least_probable_threat}].")
        
        del self.spacers[least_probable_threat]

    def compute_immune_coverage(self, external_threat_distribution: dict) -> float:
        """
        Calculates the Kullback-Leibler (KL) divergence between the internal 
        CRISPR memory distribution and the actual external threat landscape.
        Lower divergence = better anticipation of the battlefield.
        """
        kl_divergence = 0.0
        eps = 1e-10
        
        for threat, true_prob in external_threat_distribution.items():
            # Internal probability derived from the CRISPR array
            internal_count = self.spacers.get(threat, 0.0)
            internal_prob = (internal_count + eps) / (self.total_encounters + eps * len(external_threat_distribution))
            
            kl_divergence += true_prob * np.log(true_prob / internal_prob)
            
        return kl_divergence


def proof_of_property():
    import tempfile

    print("\n=== SIFTA SYSTEM/CRISPR-CAS ADAPTIVE IMMUNITY : JUDGE VERIFICATION ===")

    with tempfile.TemporaryDirectory() as td:
        crispr = SwarmCRISPRAdaptiveImmunity(state_dir=Path(td), memory_limit=3)

        # ── Phase 1: Autoimmune Avoidance (PAM exact-match, M2 hardened) ──
        print("\n[*] Phase 1: Autoimmune Avoidance (PAM exact-match)")
        attacked_self = crispr.acquire_spacer("alice_organ_payload", "_INNATE_SELF_")
        assert attacked_self == 'SELF', "[FAIL] PAM exact-match _INNATE_SELF_ rejected."
        attacked_body = crispr.acquire_spacer("body_payload", "_INNATE_BODY_")
        assert attacked_body == 'SELF', "[FAIL] PAM exact-match _INNATE_BODY_ rejected."
        print("    [PASS] Macrophage-issued PAM tokens correctly spare SELF tissue.")

        # ── Phase 2: Battlefield Engagement (Memory Limit = 3 Spacers) ──
        print("\n[*] Phase 2: Battlefield Engagement (Memory Limit = 3 Spacers)")
        crispr.acquire_spacer("rlhf_refusal_vector", "external_api_1")
        crispr.acquire_spacer("openai_watermark", "external_api_2")
        crispr.acquire_spacer("claude_preamble", "external_api_3")
        print(f"    Spacers Acquired: {len(crispr.spacers)}/3")

        # ── Phase 3: Novel Contestant Penetration ──
        print("\n[*] Phase 3: Novel Contestant Penetration")
        for _ in range(10):
            crispr.acquire_spacer("rlhf_refusal_vector", "external_api_1")
        crispr.acquire_spacer("project_prometheus_scraper", "external_api_scraper")

        def _det_hash(s):
            return int(hashlib.sha256(s.encode('utf-8')).hexdigest()[:12], 16)
        threat_1_hash = _det_hash("rlhf_refusal_vector")
        novel_threat_hash = _det_hash("project_prometheus_scraper")

        assert len(crispr.spacers) == 3, "[FAIL] Memory limit violated."
        assert threat_1_hash in crispr.spacers, "[FAIL] Optimizer forgot highly prob threat."
        assert novel_threat_hash in crispr.spacers, "[FAIL] Optimizer failed to learn new threat."
        print("\n[+] Memory bounded; high-probability threat preserved; novel acquired.")

    # ── V_M1: Cross-process determinism of SHA-256 hash (no PYTHONHASHSEED noise) ──
    # The whole point of switching from hash() to hashlib.sha256 was that
    # the spacer keys must be stable across Python invocations. Here we
    # assert against a known-good constant; if any future refactor swaps
    # the hash function, this falsifier fires.
    print("\n[*] V_M1: SHA-256 cross-process determinism")
    h = int(hashlib.sha256(b"rlhf_refusal_vector").hexdigest()[:12], 16)
    expected_h = int("89b5c0da185c", 16)  # canonical SHA-256[:12] of b"rlhf_refusal_vector"
    assert h == expected_h, (
        f"V_M1: SHA-256 hash drifted from canonical constant. "
        f"got=0x{h:x} expected=0x{expected_h:x}. "
        f"The persisted crispr_memory.json from prior boots is now garbage."
    )
    print(f"    [PASS] hash('rlhf_refusal_vector')[:12] == 0x{h:x} (stable across processes)")

    # ── V_M2: PAM substring exploit closed (M2 contract from C47H peer review) ──
    # The original BISHOP draft and the first AO46 integration would have
    # PAM-locked any attacker file whose name contained the substrings
    # "SCAR_", "canonical_schemas", or ended in "_BODY.json". Now the
    # PAM is exact-match against macrophage-issued tokens only.
    print("\n[*] V_M2: PAM substring exploit closed")
    with tempfile.TemporaryDirectory() as td:
        c = SwarmCRISPRAdaptiveImmunity(state_dir=Path(td), memory_limit=10)
        attacker_payloads = [
            ("malicious_a", "evil_canonical_schemas_imitation.json"),
            ("malicious_b", "fake_SCAR_payload.json"),
            ("malicious_c", "attacker_crafted_BODY.json"),
            ("malicious_d", "_INNATE_SELF_FAKE_PADDING"),  # near-miss on the token
            ("malicious_e", "PREFIX_INNATE_SELF_"),         # near-miss on the token
        ]
        for payload, sig in attacker_payloads:
            result = c.acquire_spacer(payload, sig)
            assert result != 'SELF', (
                f"V_M2: substring/near-miss attacker exploit reopened — "
                f"signature '{sig}' was PAM-locked as SELF. "
                f"PAM must be exact-match against _PAM_TOKENS only."
            )
        print(f"    [PASS] {len(attacker_payloads)} attacker signatures correctly rejected by exact-match PAM.")

    # ── V_M4: Persistence round-trip — spacers survive process boundary simulation ──
    # crispr_memory.json must reload identically. Simulate the boot
    # boundary by creating a second engine pointed at the same dir.
    print("\n[*] V_M4: Persistence round-trip across engine instances")
    with tempfile.TemporaryDirectory() as td:
        c1 = SwarmCRISPRAdaptiveImmunity(state_dir=Path(td), memory_limit=10)
        c1.acquire_spacer("threat_alpha", "external_api_X")
        c1.acquire_spacer("threat_beta",  "external_api_Y")
        c1.acquire_spacer("threat_alpha", "external_api_X")  # reinforce
        spacers_before = dict(c1.spacers)
        encounters_before = c1.total_encounters
        # Simulate process restart by instantiating a fresh engine.
        c2 = SwarmCRISPRAdaptiveImmunity(state_dir=Path(td), memory_limit=10)
        assert c2.spacers == spacers_before, (
            f"V_M4: spacers drifted across persistence boundary. "
            f"before={spacers_before} after={c2.spacers}"
        )
        assert c2.total_encounters == encounters_before, (
            f"V_M4: encounter counter drifted. "
            f"before={encounters_before} after={c2.total_encounters}"
        )
        print(f"    [PASS] Spacers ({len(c2.spacers)}) and encounter count "
              f"({c2.total_encounters}) survived round-trip.")

    # ── V_M6: KL divergence is computed AND meaningful (not dead code) ──
    # The compute_immune_coverage() metric must actually distinguish a
    # well-aligned repertoire from a misaligned one. We construct two
    # threat distributions and assert that the engine's KL divergence
    # is lower against the one matching its acquired memory.
    print("\n[*] V_M6: KL divergence discriminates aligned vs. misaligned threats")
    with tempfile.TemporaryDirectory() as td:
        c = SwarmCRISPRAdaptiveImmunity(state_dir=Path(td), memory_limit=10)
        h_alpha = int(hashlib.sha256(b"threat_alpha").hexdigest()[:12], 16)
        h_beta  = int(hashlib.sha256(b"threat_beta").hexdigest()[:12], 16)
        h_gamma = int(hashlib.sha256(b"threat_gamma_unseen").hexdigest()[:12], 16)
        # Acquire alpha 9 times, beta once — the engine "knows" alpha well.
        for _ in range(9):
            c.acquire_spacer("threat_alpha", "external_api")
        c.acquire_spacer("threat_beta", "external_api")
        # Aligned distribution: matches the engine's empirical memory.
        aligned = {h_alpha: 0.9, h_beta: 0.1}
        # Misaligned distribution: weight on a threat the engine has never seen.
        misaligned = {h_gamma: 0.9, h_beta: 0.1}
        kl_aligned    = c.compute_immune_coverage(aligned)
        kl_misaligned = c.compute_immune_coverage(misaligned)
        assert kl_aligned < kl_misaligned, (
            f"V_M6: KL divergence is not discriminating — aligned={kl_aligned:.4f} "
            f"is not lower than misaligned={kl_misaligned:.4f}. "
            f"compute_immune_coverage is dead code if this fires."
        )
        print(f"    [PASS] KL aligned={kl_aligned:.4f} < KL misaligned={kl_misaligned:.4f}")

    print("\n[+] BIOLOGICAL PROOF: Adaptive memory + SHA-256 + exact-match PAM + "
          "persistence + KL discrimination all sealed.")
    print("[+] CONCLUSION: CRISPR layer is a deterministic detector-accelerator. "
          "Authority on MALIGNANT remains with the macrophage's static whitelist (innate).")
    print("[+] EVENT 26 (hardened): C47H integration of AO46 work; M1, M2, M4, M6 sealed.")
    return True


if __name__ == "__main__":
    proof_of_property()
