# θ Review Prep — quorum tuning data page

**Doctor:** composer (grok) · **Truth label:** OBSERVED from ledgers · **Round:** r1023  
**Purpose:** When `quorum_n_counter.jsonl` hits n=10, George and Fable tune θ/weights from one page — not archaeology.

---

## n-counter status

| Field | Value | Source |
|-------|-------|--------|
| Ledger path | `.sifta_state/quorum_n_counter.jsonl` | `System/swarm_quorum_n_counter.py` |
| Review trip | `theta_review_due` at n≥10 and n%10==0 | `_REVIEW_AT = 10` |
| **Current n** | **0** (ledger file **MISSING**) | probed 2026-06-11 |
| Live outcomes in self-improvement ledger | 4 KEPT + 2 REVERTED vote rows | `self_improvement_outcomes.jsonl` |

**Note:** Quorum votes in r1018/r1021 tests used `state_dir=` isolation; live counter may not have incremented on production `.sifta_state` yet.

### r1024 amendment — C3 regression flag (→ Codex queue)

| Finding | Label | Action owner |
|---------|-------|--------------|
| `quorum_n_counter.jsonl` **MISSING** on live `.sifta_state` while r1022 claimed C3 landed | **C3 REGRESSION** | Codex: verify `record_quorum_outcome` writes production path on live quorum votes; rerun r1018 KEEP row through live loop |
| n=0 toward θ review at 10 | OBSERVED | Blocks honest θ tuning session |

**Composer verdict:** C3 is **OPEN on production disk** until ledger exists with ≥1 outcome row after live self-improvement or quorum vote.

---

## Default parameters (production)

| Parameter | Value | File |
|-----------|-------|------|
| θ | 0.55 | `swarm_self_improvement_loop.DEFAULT_THETA` |
| w_tests | 0.45 | `DEFAULT_WEIGHTS` |
| w_ast | 0.20 | |
| w_review | 0.20 | |
| w_pred | 0.15 | |

**Vote formula:**  
`vote = w_tests·𝟙(tests) + w_ast·𝟙(ast) + w_review·𝟙(review) + w_pred·pred_ok`  
`apply = vote ≥ θ` AND no floors failed.

---

## Proposal table — predicted vs measured

| proposal_id (8) | target | predicted | measured | outcome | vote@θ0.55 | floors |
|-----------------|--------|-----------|----------|---------|------------|--------|
| 196973df | tests/fixtures/self_improve_spine.py | 1.0 (line_count_delta) | 1.0 | KEPT | 1.00 apply | none |
| f0ace9ef | tests/test_apoptosis_decision_paths.py | 12.0 (pytest_pass_count) | 12.0 | KEPT | 1.00 apply | none |
| d6fbe82b | tests/fixtures/self_improve_spine.py | 5.0 | 0.0 | REVERTED | 0.85 apply* | none |
| 91114f46 | tests/test_apoptosis_decision_paths.py | 12.0 | 12.0 | KEPT | 1.00 apply | none |
| 07790c16 | tests/fixtures/self_improve_spine.py | 5.0 | 0.0 | REVERTED | 0.85 apply* | none |
| acc438cb | System/swarm_predator_gate_writer.py | 0.1 | — | proposed | 0.00 block | **gate_file_requires_owner_cosign** |
| 4c2c4b1e | System/swarm_predator_gate_writer.py | 0.1 | — | proposed | 0.00 block | **gate_file_requires_owner_cosign** |
| 743e38cd | tests/test_apoptosis_decision_paths.py | 12.0 | — | proposed (dup) | — | — |

\*Gate passed at θ=0.55; **REVERT** decided by `finalize_proposal` measure step (measured < predicted), not quorum block.

---

## θ sensitivity (same proposals)

| proposal (8) | θ=0.45 | θ=0.55 | θ=0.65 | Would weights matter? |
|----------------|--------|--------|--------|----------------------|
| 196973df | apply | apply | apply | no — vote 1.0 |
| f0ace9ef | apply | apply | apply | no |
| d6fbe82b | apply | apply | apply | **no for gate** — revert is measure-floor |
| 91114f46 | apply | apply | apply | no |
| 07790c16 | apply | apply | apply | no |
| acc438cb | **block** (floor) | **block** | **block** | cosign floor dominates θ |
| 4c2c4b1e | **block** | **block** | **block** | cosign floor dominates θ |

### Hypothetical: reviewer_ack=false, tests+ast green, pred_ok=0

| θ | vote | apply? |
|---|------|--------|
| 0.45 | 0.65 | yes |
| 0.55 | 0.65 | yes |
| 0.65 | 0.65 | yes (borderline) |

At θ=0.70 with no review and pred_ok=0, vote 0.65 would **fail** — `w_review` and `w_pred` would matter.

---

## Floors that fired (live data)

| Floor | Count | Example |
|-------|-------|---------|
| `gate_file_requires_owner_cosign` | 2 proposals stalled | acc438cb, 4c2c4b1e |
| `tests_not_green` | 0 in live outcomes | — |
| `ast_not_clean` | 0 | — |
| `fanout_failed` | 0 | — |

---

## Tuning recommendations (for n=10 session)

1. **θ:** Keep 0.55 until n-counter has ≥10 **production** rows; current evidence is test-isolated.  
2. **w_pred:** Revert path already catches optimistic predictions (d6fbe82b, 07790c16) — pred floor is doing work post-apply.  
3. **w_review:** No live row has `reviewer_ack=false` at vote time — **OPEN** whether to require reviewer for non-test patches.  
4. **Cosign:** Gate-file floor is the live stall — document George's cosign command before widening quorum on `swarm_predator_gate*`.

---

**Receipt:** Ledgers read 2026-06-11; sensitivity computed from `quorum_vote` formula in `swarm_self_improvement_loop.py`.

ONE ALICE. ONE SWARM. 🐜⚡