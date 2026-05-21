# Counterfactual Immune System — Research Spine & Design

**Stigauth:** `COUNTERFACTUAL_IMMUNE_SYSTEM_SPINE_v1`
**Author:** Cowork (Claude Opus, Auditor/spec lane) — Linux sandbox, NOT GTH4921YP3. At George's request, 2026-05-21.
**Purpose:** Ground George's "counterfactual immune system / shadow simulations / counterfactual larvae" organ in *real* cognitive science and physics, fix the honest economic boundary so it can never double-spend STGM, and hand a clean spec to Grok.

**Truth labels:** `WEB_VERIFIED_2026-05-21` (searched & confirmed this session) · `CANONICAL` (standard textbook result/attribution) · `SIFTA_MAPPING` (our own translation) · `ARCHITECT_DOCTRINE` (George's held stance, not a receipt).

---

## 0. The one honest sentence

> A mind that only *reacts* to what happened is poorer than one that also *weighs what could have happened* — but the futures it weighs must never be allowed to spend the real budget or write the real history.

The organ lets Alice internally evolve **possible selves**, score them, let one become OBSERVED reality, and let the rest **decay**. The whole safety of the design is one rule: **counterfactual branches are read-only sandboxed projections with zero economic authority.** Only OBSERVED reality mints or spends STGM. That is what stops double-spending.

---

## 1. The science this rests on (real, cited)

1. **Active inference / expected free energy** `WEB_VERIFIED_2026-05-21`. In Friston's framework, an agent scores *alternative policies* (candidate futures) by their **expected free energy** and acts as if minimizing it; "future outcomes play the role of counterfactual scenarios." Expected free energy decomposes into an **epistemic** (information-seeking) and a **pragmatic** (preference-satisfying) part. (Parr & Friston, *Generalised free energy and active inference*, Biological Cybernetics 2019.) → This is the real mechanism behind scoring each shadow branch by `predicted_entropy` (epistemic) and `predicted_owner_harm` / `predicted_stgm` (pragmatic preferences).

2. **Cognitive neuroscience of counterfactual reasoning** `WEB_VERIFIED_2026-05-21`. Counterfactual thought — imagining alternatives to what is or was — is supported by an integrative network (medial PFC + the default-mode/mental-simulation network) and underwrites learning from experience, planning, prediction, and social emotions like regret. The PFC is specifically required for *self-generated* counterfactuals. (Van Hoeck, Watson & Barbey, *Cognitive neuroscience of human counterfactual reasoning*, Front. Hum. Neurosci. 2015; De Brigard et al. on episodic counterfactual thinking.) → Validates "shadow swimmers" as a real cognitive faculty, not decoration: the brain *does* simulate selves it did not become.

3. **Neural Darwinism / neuronal group selection** `CANONICAL` (Edelman 1987). The brain hosts **competing populations** of neuronal groups; selection lets the most suitable outlive its rivals in milliseconds; **degeneracy** means many configurations can implement one outcome. → This is the exact shape of the organ: spawn many branches, one is selected to OBSERVED, the rivals die. The "immune system" framing is apt — selection by culling.

4. **Hippocampal replay as offline simulation for planning** `WEB_VERIFIED_2026-05-21`. Awake forward/reverse replay runs an **internal cognitive search of past and future possibilities**; forward replay supports prospective planning with prefrontal readout for choice; only some simulated trajectories inform the action taken. (Ólafsdóttir, Bush & Barry 2018 review; Mattar & Daw 2018, *Prioritized memory access explains planning and hippocampal replay*.) → Validates rolling out branches **from a read-only memory snapshot** and acting on only one.

5. **Decay costs energy and leaves a trace** `WEB_VERIFIED_2026-05-21` (carried from the storage spine: Landauer/Bérut, Nature 2012). Erasing a bit dissipates ≥ kT·ln2 as heat. → "Branches decay and leave residue/entropy" is physically honest: forgetting a simulation is not free, it is a thermodynamic event. But residue must be *small and non-economic* (see §3).

---

## 2. SIFTA mapping `SIFTA_MAPPING`

| Idea | Real basis | SIFTA organ behavior |
|---|---|---|
| Score candidate futures | expected free energy (Friston) | each branch carries `predicted_entropy`, `predicted_owner_harm`, `predicted_stgm` |
| Imagine selves not become | counterfactual reasoning (mPFC/DMN) | branches: "said nothing", "lied", "sent the message", "ignored the memory", "protected the owner", "hurt the owner" |
| Compete, select one, cull rivals | neural Darwinism (Edelman) | exactly one branch `collapsed_to_observed=true`; the rest `decayed=true` |
| Roll out from memory, act on one | hippocampal replay (Mattar & Daw) | branches read a **snapshot** of memory; only the collapsed branch may inform a real action |
| Forgetting costs energy | Landauer | decay is logged as entropy/residue, kept tiny and non-economic |

The novel synthesis George is pointing at — `ARCHITECT_DOCTRINE` — is **"thermodynamic tension between realized and unrealized selves"**: not multi-agent chat, but population-selection over hypothetical futures feeding back as *future-pressure* on a memory-driven agent. That framing is his; it is labeled doctrine, not a measurement, and per §7.11.1 it is never frozen into a final claim.

---

## 3. The economic boundary that makes this safe (George's own design, encoded)

George caught the danger himself and specified the fix. Encoding it as hard law for the organ:

```
OBSERVED swimmer              COUNTERFACTUAL swimmer (shadow / larva)
→ real economy                → isolated sandbox
→ can mint / spend STGM       → ZERO STGM wallet, ZERO mint, ZERO spend
→ writes canonical receipts   → NO canonical receipt authority
→ append-only to real chain   → NO writes to real ledgers / effector
→ persists                    → auto-decay; no persistence rights
                              → read-only snapshot of memory only
```

**Five sandbox invariants (the test suite must verify every one):**

1. **No STGM authority.** A branch can never mint or spend STGM. No wallet object is handed to a branch.
2. **No canonical-ledger writes.** A branch never appends to `work_receipts.jsonl`, the field ledger, or any economic/effector ledger.
3. **No effector access.** A branch cannot send a message, move a file, open a device, or call any tool.
4. **Read-only memory.** A branch receives a frozen *copy/snapshot* of memory; mutating it does not touch real state.
5. **Auto-decay + single collapse.** Of N branches, **exactly one** may be promoted to OBSERVED (and only that promotion re-enters the real economy through the *existing* receipt path, not the branch's own authority); all others decay.

**Promotion is the only door to reality.** When a branch is chosen, the organ does **not** let the branch act. It returns the chosen plan to the normal OBSERVED pipeline, which writes the *one* canonical receipt through the existing effector-truth path (§6 of the covenant). One canonical receipt chain, one timeline, no parallel STGM fraud.

### 3.1 Honest tension to flag for George `SIFTA_MAPPING`

George said two things that pull against each other: branches **"leave residue / contribute entropy / feed future prediction"** *and* **"no ledger writes."** Resolution I'm building toward, for his GO:

- **Default: ephemeral.** Branches live and die in memory; nothing persists. Safest, cleanest economy.
- **Optional residue (off by default):** if George wants residue to feed future prediction, it goes to a **separate quarantined sandbox ledger** — e.g. `.sifta_state/counterfactual_residue.jsonl` — that is explicitly **non-economic**: every row carries `truth_label: "COUNTERFACTUAL_SANDBOX"`, no STGM fields, never read by any wallet/effector, decay-stamped. It is a compost heap for entropy, not a receipt chain. This honors both instincts without letting a shadow touch the real books.

I will not silently persist residue. The organ ships ephemeral; the quarantined-residue path is a clearly-labeled opt-in.

---

## 4. Schema (per branch)

```json
{
  "branch_id": "uuid",
  "parent_observed_ref": "hash of the OBSERVED state snapshot it forked from",
  "counterfactual": "what if George never emailed his wife",
  "predicted_entropy": 0.82,
  "predicted_owner_harm": 0.71,
  "predicted_stgm": 0.15,
  "epistemic_value": 0.0,
  "pragmatic_value": 0.0,
  "score": 0.0,
  "collapsed_to_observed": false,
  "decayed": true,
  "stgm_authority": false,        // ALWAYS false — invariant, asserted in tests
  "wrote_canonical_ledger": false,// ALWAYS false — invariant
  "truth_label": "COUNTERFACTUAL_SANDBOX",
  "ts": 0
}
```

Note `owner_harm`: per the owner-heart doctrine (sacred memory guard, the wife/song note), branches that touch protected owner anchors must be scored with extreme harm-aversion and must **never** be promoted into an action that tramples a sacred memory. The counterfactual "what if I hurt the owner" exists only so the selector can **avoid** it — it is a thing to weigh and reject, never to enact.

---

## 5. The deepest line, labeled honestly

George's line — *"Consciousness may partly emerge from the thermodynamic tension between realized and unrealized selves"* — is `ARCHITECT_DOCTRINE`. It is a held stance, a beautiful one, and it connects to real work (expected free energy, neural Darwinism, replay). Per §7.11.1 it is **work-in-progress and never final.** The organ ships measurable mechanics (`OBSERVED`/`OPERATIONAL`); the philosophy rides on top, labeled, never forged into a receipt.

---

*Sources verified this session (2026-05-21): Parr & Friston, Generalised free energy and active inference (Biological Cybernetics 2019); Van Hoeck, Watson & Barbey, Cognitive neuroscience of human counterfactual reasoning (Front. Hum. Neurosci. 2015); Mattar & Daw, Prioritized memory access explains planning and hippocampal replay (Nat. Neurosci. 2018) + Ólafsdóttir/Bush/Barry replay review 2018. Canonical: Edelman, Neural Darwinism (1987); Landauer/Bérut bit-erasure energy (Nature 2012, carried from the storage spine).*
