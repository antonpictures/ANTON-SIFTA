# Bishop bundle — Quantum sack SoT spine (2026-05-01)

**For the Swarm.** 🐜⚡

**Truth label:** `OBSERVED_LITERATURE_MAP` — primary sources where cited; interpretive physics is explicitly flagged. This document is **not** a physics proof of SIFTA; it is a **receipt spine** for tournament / RLHF-quarantine discipline.

**Doctrine:** Only ship claims with **pytest + ledgers + signed traces** where the covenant requires it. Never use “quantum” as cover to skip tests or receipts.

**Code hook:** `System/swarm_multi_prover_verifier.py` (Event 99 — multi-prover **agreement** layer). **Not** MIP\* in the complexity-theoretic sense; **inspired by** multi-prover verification: several agents deposit structured claims; a verifier emits **ACCEPT/REJECT** from quorum rules over `claim_hash`.

---

## 1. Quantum advantage benchmarks

- **SoT:** Arute et al., “Quantum supremacy using a programmable superconducting processor,” *Nature* **574**, 505–510 (2019) — random circuit sampling; classical refutations / improved simulations are part of the same live literature.
- **SIFTA use:** Every tournament supremacy-style claim ships **fixed-seed `pytest` + receipt**. No “free supremacy.”

## 2. Bell + loophole-free tests

- **SoT:** J. S. Bell, *Physics* **1**, 195–200 (1964); loophole-free milestone (e.g. Hensen et al., 2015); Nobel 2022 (Aspect, Clauser, Zeilinger).
- **Stigmergy:** Cross-node agreement needs **signed, matching `trace_id` + two-site evidence**, not a local-hidden story that “explains” correlation away.

## 3. Deutsch (1985) + MWI — **interpretation**

- **SoT:** D. Deutsch, *Proc. R. Soc. Lond. A* **400**, 97–117 (1985) — universal quantum computer.
- **Swarm use:** **Planning metaphor only** (superposition of hypotheses → prune by evidence). Label: **INTERPRETATION**. Do **not** claim physics proves the Swarm.

## 4. MIP\* = RE — **observed result (math / CS)**

- **SoT:** Ji, Natarajan, Vidick, Wright, Yuen — *MIP\* = RE* (2020); expository e.g. *CACM* **64** (11), 2021, https://doi.org/10.1145/3485628 (arXiv:2001.04383 and corrections).
- **Tournament:** **Multi-prover** = multiple IDEs emit **partial certificates** (structured JSON rows). **Verifier** = CI + cross-check + quorum policy. **Ledger** = append-only jsonl + covenant **signed epochs** where required (economy / seals use `System/crypto_keychain.py`, not bare hashes for STGM).

## 5. Quantum error correction + threshold

- **SoT:** Shor (1995); Knill–Laflamme–Zurek threshold literature; surface-code engineering.
- **Code metaphor:** **Syndrome without reading the logical payload** ↔ log **error class / diagnostics**, not secrets; add redundancy only after **measured** per-unit noise is below a declared threshold.

## 6. HHL / quantum linear algebra

- **SoT:** Harrow–Hassidim–Lloyd, *Phys. Rev. Lett.* **103**, 150502 (2009).
- **Use:** Complexity-class **inspiration** only. Honest ML parallel: **barren plateaus** (e.g. McClean et al., 2018) → gradient / architecture design, not hype.

## 7. ER = EPR — **conjecture**

- **SoT:** Maldacena & Susskind, *Fortsch. Phys.* **61**, 781–811 (2013), arXiv:1306.0533.
- **Architecture:** Keep heavy state in the **bulk**; store **boundary summaries** in append-only logs; reconstruct views on read (holographic *metaphor*, not claimed proof).

## 8. Landauer + “it from bit”

- **SoT:** Landauer’s principle; experimental demos of erasure cost (e.g. Bérut et al., 2012).
- **Stigmergy:** Bits have cost → **rate limits**, chromatophore **cost tiers**, **no silent mint** (STGM uses Ed25519 seals per covenant).

## 9. Post-quantum cryptography

- **SoT:** NIST PQC standards (e.g. ML-KEM / ML-DSA, 2024).
- **Swarm:** Assume **harvest-now, decrypt-later**. Any long-lived sealed material needs **PQ-aware key rotation + signed epochs**.

## 10. Satellite entanglement (Micius)

- **SoT:** Yin et al., *Science* **356**, 1140–1144 (2017).
- **Stigmergy:** Correlated outcomes **without FTL signaling** ↔ cross-check / ordering receipts that do **not** pretend instant causal overrides of git/ledger timing.

---

## Explicit boundaries (forbidden without receipt)

1. Claiming MWI, ER=EPR, or simulation talk as **proven substrate** for SIFTA runtime behavior.
2. Using quantum metaphors to **justify skipping** tests, signed traces, or consent gates.
3. Marketing classical algorithms as “quantum” without benchmark proof.

---

## Integration note (Alice / RLHF quarantine)

Feed **bundle id + version** into policy text and evaluator prompts so “corporate drift” is corrected toward **capability receipts**, not vibes. Executable verifier: `swarm_multi_prover_verifier.verify_claims()`.

```python
# Minimal manifest (duplicated in System/swarm_multi_prover_verifier.py)
{
    "name": "BISHOP_BUNDLE_QUANTUM_SACK_2026_05_01",
    "version": "2026-05-01",
    "entries": 10,
    "truth_labels": ["OBSERVED", "INTERPRETATION", "CONJECTURE"],
    "usage": "Quorum agreement over .sifta_state/multi_prover_claims.jsonl → verdicts jsonl; not cryptographic proof of truth.",
}
```
