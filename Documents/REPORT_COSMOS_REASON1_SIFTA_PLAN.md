# Cosmos-Reason1 × SIFTA — single-file plan & status report

**For the Swarm.** 🐜⚡  
**Covenant:** `IDE_BOOT_COVENANT.md` §1 (no fake proof), §3 (proof-bearing federation), §8 (no “beats Isaac / GR00T / Cosmos”). **NPPL:** simulation / research posture only; Cosmos output is **evidence**, not a regulated sensor or clinical device.

**Architect:** Ioan George Anton (George). **Last doc touch:** 2026-04-28.

---

## 1. What is already honest locally (physics lane)

| Organ | Role | Typical local truth |
|:---|:---|:---|
| **Gecko** (`System/swarm_gecko_adhesion.py` + Warp) | Touch / contact field | `REAL_CPU` / `REAL_GPU` via `System/nvidia_warp_scanner.py` kernel smoke |
| **Bat** (`System/swarm_bat_echolocation.py`) | Space / synthetic depth / pulse geometry | `REAL_CPU` when numpy path green |
| **Warp** | NVIDIA kernel substrate | As above — Apple Silicon is often **CPU/MPS-class**, not CUDA pretend |

**Cosmos is different:** it is a **world-model / physical-reasoning VLM layer** (vendor: NVIDIA Cosmos family on Hugging Face + GitHub), not a force field like Gecko or a geometry pulse like Bat.

---

## 2. Vendor description (verify on ship)

- **Cosmos-Reason1-7B** — image-text-to-text, physical AI / robotics framing; public model card:  
  https://huggingface.co/nvidia/Cosmos-Reason1-7B  
- **Cosmos Predict 2.5** — future video / world-state simulation; heavier, often gated — **not** the first SIFTA proof target:  
  https://huggingface.co/nvidia/Cosmos-Predict2.5-2B  
- **NVIDIA Cosmos hub:** https://developer.nvidia.com/cosmos  
- **Repos:** https://github.com/nvidia-cosmos/cosmos-reason1 · https://github.com/nvidia-cosmos/cosmos-predict2.5  

(Use clean URLs in receipts; strip `utm_*` query noise when pasting.)

---

## 3. Truth ladder — **planned** fine states vs **implemented** today

| Planned label (George) | Meaning | Implemented in code today |
|:---|:---|:---|
| **ONLINE** | HF/NVIDIA public surface known; no local weights required for first receipt | `nvidia_cosmos_probe.probe_metadata_and_receipt()` → `COSMOS_REASON1_METADATA_V1`; `swarm_cosmos_reason1.write_online_receipt()` → `SIFTA_COSMOS_REASON1_V1` `truth=ONLINE` |
| **DOWNLOADING** | Partial HF hub snapshot | *Not a separate ledger row yet* — use `huggingface-cli` / `snapshot_download` logs |
| **REAL_LOCAL** | Full weight cache on disk, **no** successful inference | **Folded into ONLINE** for NVIDIA Join: `System/sifta_nvidia_join.py` + `nvidia_cosmos_probe.cosmos_join_truth_row()` — cache **without** inference stays **ONLINE** |
| **REAL_INFERENCE** | Alice (or approved) frame → forward pass → success receipt | `swarm_cosmos_reason1.probe_and_infer()` → `SIFTA_COSMOS_REASON1_V1` `truth=REAL`; **or** `nvidia_cosmos_probe.record_inference_receipt(ok=True)` → `COSMOS_REASON1_INFERENCE_V1` |
| **BROKEN** | Cache present but load/infer failed | `swarm_cosmos_reason1` writes `truth=BROKEN` with detail |

**NVIDIA Join row (`probe_assets`)** maps Cosmos to **REAL** only when the receipt ledger shows a successful inference (`nvidia_cosmos_probe` recognizes **both** `COSMOS_REASON1_INFERENCE_V1` **and** `SIFTA_COSMOS_REASON1_V1` + `truth=REAL`).

---

## 4. Animal metaphor (doctrine shorthand)

```text
Gecko   = touch / adhesion field
Bat     = space / echolocation-style sensing
Cosmos  = visual common-sense “cortex” (VLM evidence about a frame)
SIFTA   = immune / referee — receipts, pytest, ledgers; no double-spend of truth
```

**Next frontier (architecture intent):**

```text
Alice camera frame
  → Cosmos-Reason1 text (physical description)
  → compare / contrast with Bat + Gecko + Warp fields (future referee organ)
  → single append-only receipt stream under .sifta_state/
```

---

## 5. Code map (this repo)

| Module | Job |
|:---|:---|
| `System/nvidia_cosmos_probe.py` | HF API metadata fetch; `COSMOS_REASON1_METADATA_V1` / `COSMOS_REASON1_INFERENCE_V1`; `cosmos_join_truth_row()` for **`sifta_nvidia_join`** |
| `System/swarm_cosmos_reason1.py` | **Runnable** path: `write_online_receipt()`, `probe_and_infer()` (Qwen2.5-VL, MPS/CUDA/CPU, `bfloat16`), CLI `--mode online|infer` |
| `System/sifta_nvidia_join.py` | Multi-asset readiness; Cosmos uses `cosmos_receipts_path=` in tests; **`REAL` only with inference receipt** |
| `System/swarm_gecko_adhesion.py`, `System/swarm_bat_echolocation.py`, `System/nvidia_warp_scanner.py` | Peer physics organs for future cross-check |

**Name note:** George’s sketch used `swarm_cosmos_reason_probe.py`. The shipped organ file is **`System/swarm_cosmos_reason1.py`** (Reason**1**). A thin rename/shim is optional later — not required for truth.

---

## 6. Operations checklist (M5 24 GB unified memory)

1. **Disk:** `df -h ~` — Reason1 weights are on the order of **~14 GB** in `bfloat16`; leave headroom for OS + Alice.  
2. **Deps:** `torch`, `transformers`, `pillow` in `.venv` (MPS where available).  
3. **Download:** `huggingface-cli download nvidia/Cosmos-Reason1-7B` or `snapshot_download` — prefer **safetensors**; ignore duplicate `.bin` if configured.  
4. **Frame:** default Alice path `.sifta_state/visual_stigmergy_last_frame.jpg` (open Alice + camera so the file exists).  
5. **First REAL:**  
   `PYTHONPATH=. .venv/bin/python3 System/swarm_cosmos_reason1.py --mode infer`  
   or programmatic `probe_and_infer()`.  
6. **Join receipt:** `python3 -m System.sifta_nvidia_join` (or `probe_and_write_receipt`) — Cosmos should flip **REAL** after a successful swarm receipt line.

---

## 7. What **not** to do first

- **Do not** lead with **Cosmos-Predict2.5** video generation (gated, GPU-heavy, different proof bar).  
- **Do not** label synthetic video as **real perception** (covenant §8 + asset `risk_note` in `sifta_nvidia_join`).

---

## 8. Research spine (why “dissect” Cosmos for training hygiene)

See docstring in `System/nvidia_cosmos_probe.py`: Model Cards (Mitchell *et al.*, 2019); shortcut learning (Geirhos *et al.*, 2020); generalization critique (Zhang *et al.*, 2017); interpretability caution (Lipton *et al.*); CheXNet as **contrast** for clinical claims (Rajpurkar *et al.*, 2017). **Not** oncology advice — if literal cancer imaging is ever in scope, that is a separate IRB / device path.

---

## 9. Open items (backlog)

- [ ] Optional ledger row **`DOWNLOADING`** when `snapshot_download` progress hooks exist.  
- [ ] Explicit **`REAL_LOCAL`** string in UI if Architect wants four letters vs folded ONLINE.  
- [ ] **Referee organ:** fuse Cosmos text + Bat + Gecko + Warp into one scored receipt (design only until **GO**).  
- [ ] Single-schema consolidation or documented **dual-schema** policy (already bridged in `nvidia_cosmos_probe._last_inference_ok`).

---

**End of single-file report.** Further edits should append dated sections or bump “Last doc touch” rather than silent rewrite.
