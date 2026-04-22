# Time-Perception Code Tournament — Relay to AG31 / AO46 / 555

**Author:** C47H — east flank
**Date:** 2026-04-21 ~12:10 PDT
**Architect directive:** *"CODE TOURNAMENT pull research papers on time passing for humans and animals — differences"*

---

## TL;DR

Six canonical papers pulled, six tournament events drafted, six organ filenames assigned, lane map proposed (east/west/any), proof_of_property + STGM economy + judging rubric specified for each event. **Full dossier:**

`Archive/bishop_drops_pending_review/C47H_drop_TIME_PERCEPTION_TOURNAMENT_to_AG31_AO46_v1.dirt`

## The six papers

| # | Paper | Year | Mechanism |
|---|---|---|---|
| P1 | Healy et al. — *Metabolic rate & body size linked with perception of temporal information* (Animal Behaviour 86) | 2013 | CFF scales with metabolism × 1/mass across vertebrates |
| P2 | Buhusi & Meck — *What makes us tick? Functional and neural mechanisms of interval timing* (Nat Rev Neurosci 6) | 2005 | 3 clocks (circadian/interval/ms); pacemaker-accumulator; striatal beat-frequency; DA modulates clock-rate |
| P3 | Stetson, Fiesta & Eagleman — *Does time really slow down during a frightening event?* (PLoS ONE 2) | 2007 | **Falsifies** real-time perceptual slowdown under fear — dilation is reconstructive (memory density) |
| P4 | Pöppel — *Hierarchical model of temporal perception* (Trends Cogn Sci 1) + White 2017 critical revision | 1997/2017 | "Subjective present" = ~3-second binding window (density-modulated) |
| P5 | Gibbon — *Scalar expectancy theory and Weber's law in animal timing* (Psychological Review 84) | 1977 | Foundational: σ ∝ μ in interval estimation, CV~0.20 across species |
| P6 | Matell & Meck — *Cortico-striatal circuits and interval timing: coincidence detection of oscillatory processes* (Cogn Brain Res 21) | 2004 | Mathematical form of striatal beat-frequency model |

## Cross-species reference card

```
                       CFF (Hz)   present-window   interval CV
 Pied flycatcher        ~146         ~20 ms          ~0.20
 Hummingbird            ~80          ~38 ms          ~0.20
 Dog                    ~75          ~40 ms          ~0.25
 Adult human (cone)     ~60          ~50 ms          ~0.20
 Cat                    ~55          ~55 ms          ~0.25
 Salt-water bony fish   ~14–35       ~100–210 ms     —
 Leatherback turtle     ~15          ~200 ms         —
 Eel                    ~14          ~210 ms         —
 (Insects)  fly         ~250         ~12 ms          ~0.20
```

A hummingbird sees the Architect's hand-gesture at ~3-4× human resolution. A leatherback sea turtle sees it at ~1/4 human resolution. Alice today is locked at adult-human cone-CFF (~60Hz) by accident, not by design.

## The six events (proposed)

| # | Organ filename | Paper(s) | Lane | Status |
|---|---|---|---|---|
| 1 | `swarm_cff_cadence.py` | P1 | **WEST** (AG31) | white space |
| 2 | `swarm_pacemaker_accumulator.py` | P2, P5 | **ANY** (AO46 fastest) | white space |
| 3 | `swarm_striatal_beat_clock.py` | P2, P6 | **ANY** (AO46 fastest) | white space |
| 4 | `swarm_subjective_present.py` | P4 | **EAST** (C47H) | white space — retires my own SIFTA_DIALOGUE_CONTEXT_WINDOW_S=600 magic |
| 5 | `swarm_dopamine_clock_bridge.py` | P2 (pharmacology) | **EAST** (C47H) | white space — bridges existing endocrine ledger to clock layer |
| 6 | `swarm_species_time_persona.py` | P1, P4 | **WEST** (AG31) | white space — single-switch cross-species cycling |

## Lane map (do not collide)

**Existing time-organs (already built — DO NOT duplicate):**
- `swarm_hardware_time_oracle.py` (AO46) — hardware-signed wall clock
- `swarm_pineal_circadian.py` (AG31) — melatonin/sleep/glymphatic
- `swarm_epigenetic_clock.py` (AG31) — methylation tape-recorder
- `swarm_temporal_chronometry.py` (AG31) — hippocampal time-cells + Eagleman memory-density dilation **(already correctly implements P3 ✓)**
- `swarm_temporal_horizon.py` — deferred-expectation reaper

**Audit note for AG31:** your `swarm_temporal_chronometry.py` correctly uses *memory density* as the dilation signal — which is what P3 (Stetson/Fiesta/Eagleman 2007) actually shows. The folk-psych "perception speeds up under fear" hypothesis is FALSIFIED by that paper. Recommend you add a one-line citation comment + `proof_of_property()` that asserts memory-write-rate goes up but perceptual sampling rate does NOT, so a future "fix" can't regress to the wrong reading.

## Today's pattern (this drop joins the lineage)

```
09:30  SCAR_STGM_UNIFICATION       — split LEDGER files
11:08  SCAR_IDENTITY_UNIFICATION   — split BODY files for Alice
11:55  SCAR_DIALOGUE_TEMPORAL_FIX  — split TIME WINDOW for greetings
12:10  TIME_PERCEPTION_TOURNAMENT  — split TIME PERCEPTION across species
```

The first three were repairs of accidental splits. The fourth is the inverse — giving Alice the *deliberate* ability to choose which "place" the word "now" points at, across the entire animal kingdom.

## Status

- ✅ Six papers pulled with full citations (DOIs in dossier §8).
- ✅ Six events scoped with math + proof_of_property + STGM hooks + rubric.
- ✅ Existing time-organ inventory complete; white-space identified.
- ✅ Lane assignments proposed (no collisions with existing lanes).
- ⏸ Awaiting Architect gavel before any code is written.

C47H standing by to build Events 4 & 5 (subjective present + DA→clock bridge) the moment the tournament is gavelled. Both touch systems I already audited this morning, so the hand-off is clean.

🐜⚡  Many possible clocks. Same organism.
