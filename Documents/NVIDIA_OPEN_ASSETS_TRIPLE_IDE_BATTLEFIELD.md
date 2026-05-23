# NVIDIA open assets — triple-IDE battlefield (real URLs, real hooks)

**For the Swarm.** 🐜⚡  
**Binding:** [IDE_BOOT_COVENANT.md](IDE_BOOT_COVENANT.md) — **NPPL** (no weapons / no autonomous weapons coupling).  
**Language law:** [PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md](PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md) **§8** — we do **not** claim “SIFTA beats Isaac / GR00T / Cosmos”; we **ingest** open weights, datasets, and sim APIs where Architect **GO** + receipts allow.

**Machine-readable registry:** `System/nvidia_open_assets_registry.py` (single source for manifests, pytest, and IDE handoff).

---

## Triple-IDE agreement (one sentence)

**CG55M / C55M / AG31 agree:** SIFTA treats NVIDIA’s **open** robotics stack as **optional organs** — Isaac Lab / datasets wire into `IsaacStigmergicStub` and Sense Forge **truth labels** (`REAL` only with live receipts); **Warp / cuRobo** are performance **upgrades** to Event 74 math, not a replacement for Predator registration or ledgers.

---

## Already in-repo (contrast + numpy proof)

| Item | Role |
|:---|:---|
| GR00T N1 / N1.7 **vendor + paper contrast** | [Isaac GR00T hub](https://developer.nvidia.com/isaac/gr00t), [GR00T N1 blog](https://developer.nvidia.com/blog/accelerate-generalist-humanoid-robot-development-with-nvidia-isaac-gr00t-n1/), paper [arXiv:2503.14734](https://arxiv.org/abs/2503.14734) |
| **Event 74** `VoxelField` / `ArmSegment` / `IsaacStigmergicStub` | `System/swarm_isaac_stigmergy_bridge.py` — `REAL:numpy_proof`, `STUB:isaac_pending` |

---

## Open / downloadable — **not yet churned** (priority table)

| Asset | What it is | License / terms | SIFTA hook | Priority |
|:---|:---|:---|:---|:---:|
| **Hugging Face `nvidia` org** | Models + datasets + spaces hub | Per-repo (Open Model License, CC-BY, etc.) | Discover + pin versions for Sense Forge / tournament | **P0** |
| **`nvidia/GR00T-N1.7-3B`** | Open VLA weights (3B, DiT action head) | [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/) | Read model card; align tensor names with `IsaacStigmergicStub` story only after **GO** | P1 |
| **`nvidia/PhysicalAI-Robotics-GR00T-X-Embodiment-Sim`** | Sim trajectories (LMDB/SquashFS shards) | **CC-BY-4.0** (see dataset card) | **Falsifiable benchmark:** GR00T expert trajectories vs `ArmSegment` gradient paths (same start/goal in reduced state space) | **P0** |
| **Isaac Lab** | `isaac-sim/IsaacLab` — RL / tasks on Isaac Sim | **Apache-2.0** (repo displays Apache-2.0 / BSD-3-Clause) | Supplies `omni.isaac.core` import path used by `IsaacStigmergicStub.is_available()` | **P0** |
| **NVIDIA Warp** | `nvidia/warp` — GPU Python kernels | **BSD-3-Clause** | Accelerate `fill_goal_potential` / voxel ops (replace O(N³) hot loops) | **P0** |
| **cuRobo** | `NVlabs/curobo` — GPU motion / collision planning | **See repo `LICENSE`** (commonly permissive; verify before ship) | Optional **upgrade path** for `ArmSegment` (trajectory feasibility vs naive gradient step) | P1 |
| **NVIDIA Cosmos** | WFMs + tools (Predict / Transfer / Reason) | [NVIDIA Open Model License](https://developer.download.nvidia.com/licenses/nvidia-open-model-license-agreement-june-2024.pdf) (per developer page) | Synthetic video / curation for **future** face + sim-to-real; not blocking Event 74 | P2 |
| **Isaac-GR00T code** | `https://github.com/NVIDIA/Isaac-GR00T` | Repo license (verify) | Training / eval loop reference | P1 |

### Hugging Face CLI (Architect machine — not CI by default)

```bash
# Example: pull GR00T X-Embodiment **Sim** dataset (large — do not run on CI)
huggingface-cli download nvidia/PhysicalAI-Robotics-GR00T-X-Embodiment-Sim --repo-type dataset
```

Use **`HF_HUB_ENABLE_HF_TRANSFER=1`** for fast pulls when the Architect opts in.

---

## Cosmic / “world model” lane (optional)

| Resource | URL |
|:---|:---|
| Cosmos developer portal | https://developer.nvidia.com/cosmos |
| Cosmos Predict 2.5 (example) | https://github.com/nvidia-cosmos/cosmos-predict2.5 |
| Cosmos Cookbook | https://nvidia-cosmos.github.io/cosmos-cookbook/ |

---

## Next receipts (suggested order)

1. **C55M** — short `Documents/ISAAC_LAB_WIRE_SURVEY.md` (import graph, Python entrypoints, headless constraints) + trace row.  
2. **AG31** — optional HF **dataset card** snapshot (checksum + subset path) under `Archive/` or `Documents/` only if Architect **GO** (no multi‑GB blobs in git).  
3. **CG55M** — `pytest` for `nvidia_open_assets_registry.py` + optional **Warp** spike branch (no default dependency until `GO`).

---

*Document version: 2026-04-28 — CG55M (Cursor). URLs verified same-day; HF repos drift — re-check model cards before training.*
