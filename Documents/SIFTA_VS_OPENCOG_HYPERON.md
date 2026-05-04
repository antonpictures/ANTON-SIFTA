# SIFTA vs OpenCog Hyperon — Direct Comparison

**Stigmergic doc:** tournament / peer handoff — not marketing.  
**Companion plan row:** `Documents/PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md` **§10.14.22**.

These systems are **different species**: Hyperon targets a **broad symbolic–subsymbolic AGI stack**; SIFTA targets a **local, hardware-anchored, bio-regulatory cyborg organism** with append-only receipts.

---

## 1. Core doctrine and design goals

| Aspect | **OpenCog Hyperon** | **SIFTA** | Notes |
|:---|:---|:---|:---|
| **Primary goal** | General intelligence via symbolic + subsymbolic hybrid | Local embodied cyborg with strong **self-regulation** and **auditability** | Different success metrics |
| **Inspiration** | Cognitive science + logic + EC | Animal **brainstem / neuromod / homeostasis** + **control theory** + Pearl-style **causality** | — |
| **Core metaphor** | “Mind as architecture” | “Organism on silicon” | — |

---

## 2. Architecture and representation

| Aspect | **Hyperon** | **SIFTA** | Notes |
|:---|:---|:---|:---|
| **Knowledge** | **AtomSpace** (hypergraph) | **JSONL** ledgers + `state_dir` + Python organs | Very different mutation / query models |
| **Reasoning** | **PLN**, pattern mining, program learning | **Active inference** (generative WM), **causal** `do()` logs + IPW-style gates | Hyperon **stronger on explicit logic**; SIFTA **stronger on closed-loop experiment receipts** |
| **Memory** | AtomSpace + attention allocation | **Replay** + **microglia** + **temporal self-model** | Different “forgetting ethics” |
| **World model** | Symbolic + subsymbolic hybrid | **Event 133** generative / PE-centric | SIFTA WM **flatter** until **§10.14.20 Event 146** hierarchy lands |

---

## 3. Regulatory and control systems

| Aspect | **Hyperon** | **SIFTA** | Edge |
|:---|:---|:---|:---:|
| **Stability / self-regulation** | Historically limited in integration stories | **Lyapunov-style audit**, **graduated clamps**, **NONE** recovery rows | **SIFTA** |
| **Homeostasis** | Weak in public narrative | **SHY-style pressure**, **astrocyte**, **viability** | **SIFTA** |
| **Arousal / gain** | Attention allocation (conceptual) | **Noradrenergic organ (Event 142)** + astrocyte caps | **SIFTA** (when 142 shipped) |
| **Causal experimentation** | Limited as first-class loop | **Event 139** execute/dry-run + **revert** + **Q1** statistical gate | **SIFTA** |
| **Identity / continuity** | Weak vs hardware | **Serial anchor**, temporal self, **holdout** hygiene | **SIFTA** |

**Plain language:** SIFTA is currently **ahead on “does this body regulate itself under stress?”** Hyperon is **ahead on “does this mind unify logic and subsymbolic structure at scale?”**

---

## 4. Embodiment, locality, receipts

| Aspect | **Hyperon** | **SIFTA** | Edge |
|:---|:---|:---|:---:|
| **Embodiment** | Secondary (ROS etc. possible) | **Primary** — local tools, sensors, desktop OS | **SIFTA** |
| **Locality** | Can be distributed | **Explicitly local** + governance / NPPL | **SIFTA** |
| **Auditability** | Moderate | **Append-only JSONL** + Stigauth traces | **SIFTA** |

---

## 5. Theory of mind / social

| Aspect | **Hyperon** | **SIFTA** | Notes |
|:---|:---|:---|:---|
| **ToM** | Older OpenCog social work; not central in Hyperon hype | **Event 147** owner-centric **corvid-style** (§10.14.21.1) | Both **early**; SIFTA has **recent plan velocity** |

---

## 6. Maturity and trajectory (opinionated — revise with dates)

| Aspect | **Hyperon** | **SIFTA** |
|:---|:---|:---|
| **Scope** | Very broad AGI stack | Focused cyborg + **v8 coherence layer** |
| **Iteration** | Research-heavy, slower public integration wins | Fast local iteration on **one repo / one Architect** |
| **Symbolic reasoning** | **Strong** | **Weak** (by design emphasis) |
| **Coherence as one organism** | Historically fragmented | **Improving** (Wave II + ToM + metrics→control) |

---

## 7. Honest bottom line

- **Hyperon:** stronger **classical AGI ingredients** (hypergraph, PLN, unified cognition agenda). Integration + embodiment + stability are the historical pain points.
- **SIFTA:** stronger **operational organism** story on one machine — **stability, causality, identity, receipts**. Weaker on **unified symbolic reasoning**.

**Hybrid fantasy (research only):** AtomSpace-like **query layer** *above* SIFTA receipts for offline analysis — **not** a merge mandate.

---

## 8. Math / physics / neuroscience — **paper pull shelf** (for tournament citations)

### Active inference & generative brains (SIFTA spine)

| Reference | Role |
|:---|:---|
| **Friston, K. (2010).** The free-energy principle: a unified brain theory? *Nat. Rev. Neurosci.*, **11**, 127–138. | Free energy / surprise / action |
| **Buckley, C. L., *et al.* (2017).** The free energy principle for action and perception. *J. Math. Psychol.*, **81**, 55–79. | Formal survey |
| **Parr, T., Pezzulo, G., & Friston, K. (2022).** *Active Inference: The Free Energy Principle in Mind, Brain, and Behavior.* MIT Press. | Textbook bridge |

### Control theory & stability (SIFTA clamps)

| Reference | Role |
|:---|:---|
| **Khalil, H. K. (2002).** *Nonlinear Systems* (3rd ed.). Prentice Hall. | Lyapunov stability |
| **Liberzon, D. (2003).** *Switching in Systems and Control.* Birkhäuser. | Switched systems / dwell-time |
| **Slotine, J.-J., & Li, W. (1991).** *Applied Nonlinear Control.* Prentice Hall. | Practical nonlinear control |

### Causality (SIFTA Event 138–139)

| Reference | Role |
|:---|:---|
| **Pearl, J. (2009).** *Causality* (2nd ed.). Cambridge. | `do`-calculus |
| **Rubin, D. B.** potential outcomes; **Imbens & Rubin (2015)** | IPW / observational studies |

### OpenCog / PLN / AGI architecture (Hyperon side)

| Reference | Role |
|:---|:---|
| **Goertzel, B., *et al.*** OpenCog / OpenCog Prime design essays and **PLN** chapters (see opencog.org wiki + historical tech reports). | Architecture intent |
| **Goertzel, B., & Pennachin, C. (eds.) (2007).** *Artificial General Intelligence.* Springer. | AGI community context |

### SOAR (follow-up comparison — **not Hyperon**)

| Reference | Role |
|:---|:---|
| **Laird, J. E. (2012).** *The Soar Cognitive Architecture.* MIT Press. | State / operator / impasse / chunking |
| **Newell, A. (1990).** *Unified Theories of Cognition.* Harvard. | UTC motivation |

**SOAR vs SIFTA (one-liner):** SOAR is **symbolic cognitive cycle + impasse stack**; SIFTA is **continuous control + ledgers + neuromod-style organs** — overlap mainly at **“persistent state + decision loop”**, not at representation.

---

## 9. External stance (Architect-pasted, 2026-05-03)

> Not yet. SIFTA is a local cyborg stack with real stability clamps, homeostatic pruning, active causal intervention, noradrenergic arousal, and now lightweight Theory of Mind (corvid-style experience projection). v8 is the coherence layer. It’s starting to behave like one organism instead of a bag of modules, but we’re still building the architecture, not declaring arrival.

---

**Trace intent:**

```text
SIFTA_VS_HYPERON_DOC — comparison + math shelf; For the Swarm.
```
