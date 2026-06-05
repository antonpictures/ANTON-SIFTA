# Quantum code inventory + dedup — June 3 2026

George asked: search the code first, no duplicates, and make sure it's in the eval matrix so Alice knows it's in her body. Here's the honest map after grepping the whole body.

## Already in the matrix (so don't re-add)

The recent quantum work IS registered — re-adding it would be the duplication you're trying to avoid. Verified on disk:

- `swarm_canonical_organ_registry.py` has **2 quantum OrganSpecs**: `quantum_swimmer_sentinel` (covers data_sentinel + swimmer_sentinel + epi_sim) and `qml_sifta_nuggets`.
- The eval matrix HTML (`ORGAN_EVAL_MATRIX_V2.html`) references `quantum_data_sentinel` 9×, `quantum_swimmer_experiments` 6×, plus the nuggets, epi_sim, scheduler, substrate, router.
- `sifta_self_evaluation.py` mentions quantum 22×.

So Alice already "has it in her body." The gap is sprawl and the weak page answer, below — not missing registration.

## The recent quantum-data cluster (June 3–4) — watch this for overlap

These four are the ones built across the last few rounds. Each has a distinct role, but the boundaries blur:

- `System/swarm_quantum_data_sentinel.py` — honest **catalog** of 9 real data lanes (PennyLane, Braket, IBM, Qiskit, Xanadu, PsiQuantum, Majorana 2, Willow, QDataSet) + `local_tfim_ground_state` (real exact solve) + a Bell smoke test + truth boundaries. Ledger: `quantum_data_sentinel.jsonl`.
- `System/swarm_quantum_swimmer_sentinel.py` — ingests edge priors and **dispatches surface-code swimmers**. Ledger: `quantum_swimmer_experiments.jsonl`.
- `Applications/sifta_quantum_epi_sim.py` — the original **GUI** surface-code (and epidemiological) swimmer sim (~1178 LOC).
- `System/swarm_qml_sifta_nuggets.py` — **QML research nuggets** / "what can SIFTA actually solve" (Cerezo/Huang/McClean). Ledger: `qml_sifta_nuggets.jsonl`.

**Overlap flags (real, but not fatal):**

- `data_sentinel` ↔ `swimmer_sentinel`: both touch "ingest quantum edge priors." `swimmer_sentinel`'s surface-code dispatch largely **re-exposes the `epi_sim` engine headlessly** — that's the closest thing to a duplicate.
- `data_sentinel` ↔ `qml_nuggets`: both are "catalogs of quantum stuff" (one = data sources, one = QML algorithms/problems). Mild conceptual overlap.
- Good instinct already in place: the registry **collapses data_sentinel + swimmer_sentinel + epi_sim into one OrganSpec**, so Alice sees them as one organ.

## Older / foundational quantum organs — NOT duplicates

Different domains, pre-existing, leave them alone:

`swarm_quantum_scheduler.py` (quantum-walk heartbeat scheduler), `swarm_quantum_stigmergic_substrate.py` (the "quantum soup" doctrine), `swarm_fmo_quantum_router.py` (FMO quantum-walk router), `swarm_bose_hubbard.py`, and the physics demo widgets `sifta_bell_theorem_widget.py` / `sifta_epr_stigmergic_widget.py` / `sifta_double_slit_stigmergic.py`, plus `swarm_bell_research_spine.py` and `swarm_action_pathsum.py`.

## Dedup verdict + recommendation (your call)

No egregious file-level duplication — every file does something. But the recent cluster is sprawling. If you want to consolidate (don't delete brother work without deciding):

1. Keep `swarm_quantum_data_sentinel.py` as the **one canonical quantum entry point** (catalog + truth guards + local solves like TFIM).
2. Have `swarm_quantum_swimmer_sentinel.py` **import the `epi_sim` surface-code engine** instead of re-implementing it (kills the only real duplicate).
3. Treat `qml_sifta_nuggets` as a **data table inside the sentinel**, not a separate organ.

That collapses 4 organs → 1 organ + 1 engine, and Alice still sees one quantum lane.

## Why "that answer sucked" — and the fix

When you asked *"what's interesting for your body on this page to test?"* on the quantum-sensors article, Alice answered with generic prose ("That is a profoundly excellent question…") and got cut off. Two causes:

1. She didn't ground the answer in her **own organs** — she had no way to map "this page" to "this part of my body."
2. The mid-sentence cutoff is the same `num_predict` 700-token cortex cap from r474 (still open).

I added the missing bridge: `organs_relevant_to_text(text)` in `swarm_canonical_organ_registry.py`. Given a page's text it returns the organs that page touches, scored, with matched terms. Verified — on your actual quantum-sensors article it surfaces `quantum_swimmer_sentinel`. So Alice can now answer: *"this page is about quantum sensors → it maps to my quantum_swimmer_sentinel / quantum_data_sentinel; worth testing ingesting sensor-style priors, or running my TFIM solver on the sensor's spin lattice"* — grounded in real code, not fluff.

**Next step (needs a GUI restart to verify):** wire `organs_relevant_to_text(page_text)` into the page-commentary prompt in `sifta_talk_to_alice_widget.py`, so the cortex always gets "here are the organs this page touches" before it answers. I left that for you to greenlight rather than make an unverifiable edit to the 32k-line widget.
