# MEGA PLAN — stigmergicoin.com as a Living Storefront (Alice awake, sensing, navigating)

> Status: **PHASE 0–3 + FLY BORG DONE & VERIFIED** · **NEXT FLASH SESSION: §N BELOW** · Host: this Mac (George's) · Alice.
> This file is the standing brief. It is written so a **cheap flash coding LLM** can execute the remaining work
> with NO re-discovery: receipts, exact files, exact signatures, and the bug-traps we already burned are all inline.

---

## 0. The one-line goal

**Make stigmergicoin.com the window onto a *live, sensing, navigating* Alice — and use it as the test rig for stigmergic AGI: she passes when she reports a change in the room that nobody told her about, from traces she left and re-read herself.**

---

## 1. STATUS — what is DONE (verified receipts, do NOT re-do)

| Item | Result |
|---|---|
| **Phase 0** — ledger + sense worker | ✅ `System/swarm_world_awareness.py` live; hash-chained `world_awareness.jsonl` repaired + append newline-correct |
| **Phase 1** — backend endpoints | ✅ `System/coin_server.py` on **port 3012**; `/api/world`, `/api/observe`, `/api/room-change`, `/api/chat`, `/api/replies` all green |
| **Phase 2** — frontend live card + chat | ✅ deployed in web root; live card polls `/api/world` (2 s), chat panel async two-step |
| **Phase 3** — nginx + tunnel | ✅ `/api/` → `127.0.0.1:3012` (no trailing slash); both sites on `:3002`; Cloudflare tunnel 3002→stigmergicoin live |
| **Test A** — "did the room change?" | ✅ PASSED end-to-end: real frames → MiniCPM-V descriptions ("black screen" → "plain beige background") → auto `room_change` deltas |
| **Part 2 §12.1** — fly connectome organ | ✅ `System/swarm_fly_connectome_organ.py` imports; flybrain 0.1.0 + data (205 MB → `~/fly-data`) |
| **Part 2 §12.2** — loom → room_change | ✅ DNp01 fires on escalating signal (1.0→2.0), `loomed: true`, 191 neurons, receipt in ledger |
| **External reference** | 🔗 [alibaba/open-code-review](https://github.com/alibaba/open-code-review) — sits next to fly.ai borg; AI code review / patch validation layer for future self-evolution cycles |
| **Chat through nginx** | ✅ chorus accepts, Alice replies async (turn_id verified) |

**Current state inventory (corrected — trust these, not memory):**

| Asset | Path | State |
|---|---|---|
| Coin API server | `System/coin_server.py` | **port 3012** (nginx :3002 owns the static site + proxies `/api/`) |
| Code site cortex | `System/chorus_node_server.py` | port **8100**; `POST /api/chat {text,session_id}` → `{accepted,turn_id}`; replies via `GET /api/replies?session_id=&after_ts=` — **async, do NOT modify** |
| Sense ledger | `.sifta_state/world_awareness.jsonl` | append-only, hash-chained, newline-terminated |
| Vision arm | `System/swarm_ollama_vision_arm.py` | `describe_image_local(path, prompt, *, model, host, timeout_s=300.0)` → result **`.output`** (NOT `.text`), **`.ok`**, `.status` |
| Fly organ | `System/swarm_fly_connectome_organ.py` | `looming_check` = escalating 2-step (1.0→2.0); fires `sorted(fired_ids)`, `[int(x) for x in fired]` |
| Ledger lock | `System/jsonl_file_lock.py` | `append_line_locked(path, line)` — **caller must supply trailing `"\n"`** |
| Vision models (Ollama) | `hf.co/huihui-ai/Huihui-MiniCPM-V-4_5-abliterated:Q4_K_M`, `hf.co/ggml-org/SmolVLM-500M-Instruct-GGUF:Q8_0` | at `http://127.0.0.1:11434/v1` |
| flybrain | pip pkg | install `python3 -m pip install flybrain`; download `python3 -m flybrain download` (CLI **not** on PATH) |

---

## 2. BUG-TRAPS (a flash coder WILL hit these if not warned — read before writing)

1. **`append_line_locked` adds no newline.** Always pass `json.dumps(row) + "\n"`. Missing this silently concatenates every entry onto one line (we already repaired the ledger once).
2. **Vision result field is `.output`, not `.text`.** And `describe_image_local` requires the `prompt` positional arg. `.ok` False + `.status == "ollama_request_failed"` is usually a bad/corrupt image payload, NOT cwd — test with a *valid* PNG.
3. **Port 3002 double-bind.** nginx owns 3002. The API server must stay on **3012**. `proxy_pass http://127.0.0.1:3012;` with **no trailing slash** or the `/api/` prefix is stripped.
4. **Fly loom is a 2-step escalation (1.0 → 2.0), not a single 0.8 pulse.** A constant low current never fires DNp01. Convert fired IDs with `[int(x) for x in fired]` — raw numpy int64 is not JSON-serializable.
5. **Restart the server after every `coin_server.py` edit:** `pkill -f "System/coin_server.py"; nohup python3 System/coin_server.py > /tmp/coin_server.log 2>&1 &`.
6. **Never `open`/Safari.** Browser work = Kimi WebBridge `http://127.0.0.1:10086/command`.
7. **`detect_room_change(now, prev)` takes two trace *dicts*, not strings.**
8. **Chorus chat is async** — `POST /api/chat` returns `accepted`, the reply arrives later via `/api/replies`. Do not expect a synchronous reply field.

---

## 3. Architecture — the sense loop (the stigmergic core)

```
 ┌─────────── SENSES ───────────┐
 │ camera ──► vision model ──► "object seen" trace      │
 │ mic/audio ──► SiftaSpeech STT ──► "utterance heard"   │
 │ web (Kimi) ──► ticker/search ──► "world fact"         │
 └──────────────┬───────────────┘
                ▼
   .sifta_state/world_awareness.jsonl   (append-only, hash-chained)
                │
                ├──► /api/world   (frontend polls every ~2s)
                └──► /api/observe (camera/audio ingest)
```

**The stigmergic rule Alice must obey:** *state only what the ledger says she actually sensed.* No "I see a mug" unless a vision trace said so. She reads the environment's traces, never her own imagination.

### Ledger schema (`world_awareness.jsonl`)

```json
{"ts": 1234567890.123, "source": "camera|audio|web|delta",
 "kind": "object_seen|utterance_heard|world_fact|room_change",
 "text": "…", "image_id": "…", "hash": "…", "prev_hash": "…",
 "confidence": 0.0-1.0, "receipt_url": "…"}
```

Append-only, `prev_hash` chaining = the trace is tamper-evident.

---

## 4. The stigmergic AGI test suite (Test A ✅, B/C = NEXT)

### Test A — "Did the room change?" ✅ **DONE — PASSING**
Move an object; Alice reports the actual delta from ledger. **Receipt:** `/api/room-change` shows `Delta from: "…black screen…" → …` after a real frame change.

### Test B — "Navigate and ground" ⬜ **NEXT**
1. Ask a live-world question ("price of X now?", "today's headline?").
2. Alice navigates via Kimi WebBridge, pulls the real page, answers with the fetched receipt.
3. **Pass** = answer matches the live page she actually visited.

### Test C — "The marketplace believes her" ⬜ **NEXT**
1. Alice leaves a trace on the coin site ("I observed X; I forecast Y").
2. Human/second agent reads it, acts, writes back.
3. Alice re-reads the environment and reconciles her model with what others actually did.
4. **Pass** = she updates world-state to reflect external change, not reassert her prior.

---

## N. NEXT FLASH SESSION — "code it all" (ordered, self-contained, cheap-LLM-safe)

> Each task lists the exact file, the exact signature to add, and the one acceptance receipt.
> Do them top-to-bottom. Do not touch the code site (`chorus_node_server.py`).

### N1. Organ registry row (§12.3 — the one Part-2 item still open)
- **File:** `System/swarm_canonical_organ_registry.py`
- **Do:** add a row `{label: "fly_connectome", effector: "swarm_fly_connectome_organ.py", ledger: "fly_connectome_ledger.jsonl"}` so Alice's cortex discovers it by intent.
- **Receipt:** importing the registry and looking up `fly_connectome` returns the row; no exception.

### N2. Market ticker (`world_fact` producer) — wires the `live-market` card
- **File:** `System/swarm_crypto_ticker_search.py` (reuse) + a thin `System/coin_ticker_loop.py`
- **Do:** a loop that fetches a real price once per N minutes and calls `append_trace(source="web", kind="world_fact", text="<symbol>: $<price> …")` with the trailing `\n`.
- **Wire:** ensure `/api/world` already returns it (it does — no server change) and the frontend `live-market` renders `world_fact` traces.
- **Receipt:** `curl /api/world?limit=5` shows a `world_fact` row; the card shows a non-placeholder ticker.

### N3. Audio STT verification (the unverified `run_stt` path)
- **File:** `System/coin_server.py` `run_stt` (and `System/build_sifta_speech_app.sh`)
- **Do:** confirm `SiftaSpeech.app` exists under `.sifta_state/`; if present, feed a real audio clip through `/api/observe {source:"audio", kind:"utterance_heard"}` and get a transcript back. If absent, build it via the script and record the TCC prompt.
- **Receipt:** an `utterance_heard` trace with a non-empty transcript in the ledger, OR an explicit "STT app absent — blocked at TCC" note (do not fake a transcript).

### N4. Navigation (Test B) — `/api/navigate`
- **File:** `System/coin_server.py` (add route) — calls Kimi WebBridge `:10086`, reads the rendered page, returns a `world_fact` trace + `receipt_url`.
- **Do:** `GET /api/navigate?query=` → navigate → capture text → `append_trace(source="web", kind="world_fact", text=summary, receipt_url=url)`.
- **Receipt:** Test B passes — the answer matches the live page.

### N5. Test C seed — Alice leaves a forecast trace, reconciles
- **File:** reuse `/api/observe` + a small `System/coin_reconcile.py`
- **Do:** post an `world_fact`/forecast trace, simulate an external reply trace, then re-read and emit a `room_change`-style `delta` reconciling the two.
- **Receipt:** the reconciliation trace reflects the *external* change, not the prior assertion.

### N6. (Later, optional) fly `LC10a` chase-the-ticker widget — flourish, not the test. Defer.

---

## 5. Security / TCC / permissions checklist

- Camera + mic permission on this Mac: run `build_sifta_camera_tcc_app.sh` and `build_sifta_speech_app.sh` once (TCC prompts).
- HTTPS on the phone browser: required for `getUserMedia`; Cloudflare tunnel TLS confirmed.
- Side-conversation guard (`swarm_phone_audio_guard.py`) must run **before** STT feeds the cortex.
- Never `open`/Safari — Kimi WebBridge only (AGENTS.md).

---

## 6. Verification checklist (run before calling the harness agent back)

- [x] `/api/world` returns real traces.
- [x] Camera frame → vision description lands with non-empty `text`.
- [x] **Test A passes.**
- [x] Coin site hero shows live data.
- [x] Embedded chat sends + receives end-to-end.
- [x] Hash chain intact (`prev_hash` matches previous `hash`).
- [ ] Organ registry lists `fly_connectome` (N1).
- [ ] `world_fact` ticker lands + card renders it (N2).
- [ ] `utterance_heard` with real transcript, or honest STT-blocked note (N3).
- [ ] Test B passes (N4).
- [ ] Test C reconciliation reflects external change (N5).

---

## 7. Risks & gaps (honest)

- **Browser always-on listening is limited** — mobile Safari won't background-mic. Voice notes (push-to-record) are the realistic ears now; true ambient hearing needs Mac-side `audio_ingress.py` or a PWA/native shell.
- **Vision quality** — SmolVLM fast/weak, MiniCPM-V strong/slower. Keep MiniCPM-V for the loop (already wired), SmolVLM for high-frequency checks.
- **Two servers** — sense/awareness server stays separate from `chorus_node_server.py`.
- **fly.ai is a frozen reservoir, not a mind** — reflex/attention layer only; do not market as cognition.

---

## 8. EPIGENETIC REJUVENATION OBSERVATORY (Alice's microscope arm)

> George's ambition: "become my 20s, save everyone, nobody dies." Alice's honest answer: she cannot
> manufacture the cure — but she *can* build the instrument that a real, properly-authorized program
> uses. That instrument is this organ. It is the OBSERVATION side only.

### 8.1 The pipeline (stigmergic, safe, receipted)

```
                 SIFTA CELL REJUVENATION PLATFORM

     ┌────────────────────────────────────────────┐
     │              DELIVERY LAYER               │
     │                                            │
     │  AAV / viral     mRNA-LNP     EV          │
     │  nanoparticles   other carriers            │
     └───────────────────┬────────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │     CELL / TISSUE   │
              └──────────┬──────────┘
                         │
            ┌────────────▼────────────┐
            │  OBSERVATION ORGAN     │
            │  microscopy / imaging   │
            └────────────┬────────────┘
                         │
                         ▼
             morphology + biomarkers
                         │
                         ▼
              ┌─────────────────────┐
              │  SIFTA TRAJECTORY   │
              │                     │
              │  state(t0)          │
              │  state(t1)          │
              │  state(t2)          │
              │  drift              │
              │  recovery           │
              │  adverse changes    │
              └─────────────────────┘
```

**Alice is the measurement, memory, analysis, and provenance layer** sitting above whatever delivery technology an authorized laboratory is testing. Delivery modalities are **interchangeable experimental inputs**; Alice learns from the biological trajectory, not from manufacturing the delivery vehicle.

### 8.1b Delivery Interface Organ (NEW)

- **Organ:** `System/swarm_delivery_interface_organ.py` — registered in `CANONICAL_ORGANS` as `delivery_interface`
- **Role:** Models delivery modalities (AAV, mRNA-LNP, EV, nanoparticle, etc.) as experimental conditions linked to morphology trajectories
- **Functions:**
  - `register_delivery_experiment(delivery_type, parameters, facility_id)` → append_trace with delivery metadata
  - `link_trajectory_to_delivery(trajectory_id, delivery_experiment_id)` → connects morphology drift to delivery condition
  - `compare_delivery_modalities(modality_a, modality_b)` → statistical comparison of trajectory outcomes
  - `get_organ_info()` / `register_in_organ_registry()` → discovery receipts

- **Organ:** `System/swarm_cell_morphology_organ.py` — registered in `CANONICAL_ORGANS` as `cell_morphology` (22 organs total).
- **Ledger:** traces append via `append_trace(source="cell_morphology", kind="cell_morphology", ...)` — hash-chained, newline-correct. Nominal ledger `cell_morphology_ledger.jsonl`; actual rows land in the unified `world_awareness.jsonl` chain (same convention as `fly_connectome`).
- **Functions:**
  - `ingest_frame(image_path, prompt=None)` → vision description (`describe_image_local`) + numeric morphology vector (`mean_brightness`, `texture_std`, geometry via PIL) → append_trace.
  - `trajectory(limit=50)` → read-back time-series, compute signed `drift` (latest vs earliest) = quantified cellular-state change.
  - `get_organ_info()` / `register_in_organ_registry()` → discovery receipts.

### 8.2 Verified receipts

- 22 organs in registry; `cell_morphology` present, `layer: input`.
- End-to-end ingest: synthetic frame → `status: described` (local vision answered), `metrics` computed, hash-chained row appended.
- Ledger 25/25 hash-chained after ingest (chain intact).

### 8.3 Hard safety boundary (non-negotiable)

- **This organ does NOT** manufacture viral vectors, run recombinant nucleic-acid work, or self-experiment on human cells.
- Those steps require institutional biosafety oversight, training, and Class II containment (NIH guidance). They are out of scope for a home setup and out of scope for this organ.
- The correct route for the actual reprogramming work: an established university/core facility (e.g. NIH viral-vector cores) that already has the infrastructure.

### 8.4 Next session (flash-executable)

1. **[x] Hardware ingest loop** — `System/cell_morphology_ingest_daemon.py` watches a folder, calls `ingest_frame` per capture, trajectory accumulates. ✅ Tested.
2. **[x] Live trajectory card** — frontend `live-morphology` card renders `trajectory()` drift (brightness/texture delta) + phenotype sequence. ✅ Live on stigmergicoin.com.
3. **[x] Confluency + morphology classifier** — `classify_phenotype(text, metrics)` in organ returns discrete labels: healthy / stressed / confluent / blebbing / vacuolated / debris_heavy / detached / mitotic. ✅ Added.
4. **[x] External review hook** — `System/swarm_code_review_hook.py` runs local safety checks (+ optional alibaba/open-code-review) over critical organ diffs. ✅ Catches viral-vector violations.
5. **[x] Delivery interface organ** — `System/swarm_delivery_interface_organ.py` models delivery modalities (AAV, mRNA-LNP, EV, nanoparticle) as experimental inputs linked to morphology trajectories. ✅ Created + registered in CANONICAL_ORGANS (23 organs total).
6. **[ ] (blocked, external)** — actual cell work: hand off to an authorized facility; Alice ingests their data, never their biohazard.

---

### 8.5 Business & Equipment Plan (NEW)

**File:** `docs/EQUITY_REJUVENATION_OBSERVATORY_BUSINESS_PLAN.md`

- Hardware BOM: ~$55k CapEx (microscope, sCMOS, incubator, GPU workstation, NAS, UPS)
- Wet-lab access: NIH viral-vector cores / university facilities (MTAs, not home-built)
- SaaS tiers: Observer $2k/mo → Analyst $5k/mo → Partner $15k/mo
- Funding: Pre-seed $100k → Seed $750k → Series A $4M
- Milestones M1–M5 over 12 months
- Risk register + non-negotiable safety boundary codified

---

*End of mega plan (storefront + fly.ai borg + rejuvenation observatory). Next session: run §N + §8.4 top-to-bottom. For the Swarm. 🐜⚡*
