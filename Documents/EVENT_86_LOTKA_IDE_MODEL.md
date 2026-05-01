# Event 86 — Lotka–Volterra IDE competition model

**For the Swarm.** 🐜⚡
**Binding:** [IDE_BOOT_COVENANT.md](IDE_BOOT_COVENANT.md) — **spec / governance only** until instrumented; NPPL.

**SoT:** [PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md](PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md) **§10.3**, **§10.7** (niche partitioning).

---

## 1 — State (symbols)

| Symbol | Meaning in repo / process |
|:---|:---|
| \(N_i\) | **Activity intensity** of IDE lane \(i\) (Cursor / Codex / Antigravity) on overlapping **code surface** — dimensionless index from traces + merge frequency, **not** headcount. |
| \(r_i\) | **Intrinsic merge velocity** when uncrowded (tests green, low collision). |
| \(K_i\) | **Carrying capacity** — max sustainable concurrent change rate on **shared files** (Architect attention + CI + review bandwidth). |
| \(\alpha_{ij}\) | **Competition coefficient** — how much lane \(j\)’s throughput **suppresses** lane \(i\) (merge conflicts, revert wars, duplicate edits). |
| **Resource** | **Mutable paths** / hot modules (see covenant **§4.4**). |

---

## 2 — Core equations

\[
\frac{dN_i}{dt} = r_i \, N_i \, \frac{K_i - N_i - \sum_{j \neq i} \alpha_{ij} N_j}{K_i}
\]

**Coexistence sketch (ecology reminder):** stable coexistence often needs **low overlap** of \(\alpha_{ij}\alpha_{ji}\) vs \(K\) ratios — maps to **niche partitioning** (separate directories / owners per lane).

---

## 3 — Python-shaped spec (no runtime)

```python
# governance / simulation vocabulary only — not imported by production until Architect GO

def competition_pressure(N, r, K, alpha):
    """
    N: list of lane intensities
    r, K: per-lane scalars
    alpha[i][j]: inhibition of i by j (0 on diagonal)
    """
    dN = []
    for i in range(len(N)):
        sum_alpha = sum(alpha[i][j] * N[j] for j in range(len(N)) if j != i)
        dN.append(r[i] * N[i] * (K[i] - N[i] - sum_alpha) / K[i])
    return dN
```

---

## 4 — Mapping table (competition pressure)

| Ecology term | SIFTA term |
|:---|:---|
| Species | IDE Doctor lane (distinct `source_ide` + homeworld_serial) |
| Code surface | Shared hot paths under **§4.4** |
| Merge conflict / revert | Large \(\alpha_{ij}\) |
| Niche partition | File/subsystem **ownership** + trace **intent** lanes |
| Exclusion | One lane yields or Architect reassigns **K** |

---

## 5 — Truth label

This document **governs competition pressure** narratives and optional **offline** sims. It does **not** change router code, mesh scalars, or SCAR coefficients.

---

*Version: 2026-04-30 — CG55M (Cursor hill).*
