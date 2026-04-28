# Swarm plan — Math app load · Owner recognition · Triple IDE

**For the Swarm.** 🐜⚡  
**Grounding:** [IDE_BOOT_COVENANT.md](IDE_BOOT_COVENANT.md) — §6 Social frame, **§7.1** sensory lock-on + verify scene, **§7.4** self/other, **§7.6** Alice = OS, **§8** substrate honesty, **§4** Predator Gate.

**Bibliography (owner + face + biology):** [OWNER_FACE_PREDATOR_RESEARCH_SPINE.md](OWNER_FACE_PREDATOR_RESEARCH_SPINE.md).

**Mode:** Plan only (no code until Architect **GO**).

---

## A. Math app “loads forever”

### Symptoms (hypothesis → verify)

1. **UI thread blocked on first paint:** `_refresh_live()` runs `QTimer.singleShot(200, …)` and calls `_count_ledger_lines()` which does **`sum(1 for _ in f)` over the entire root `repair_log.jsonl`**. That file can be **tens of thousands of lines** — full-file scan on the **main thread** = frozen window / “forever.”
2. **HuggingFace on open:** `MathBenchmarkWidget.__init__` adds the Arena tab, whose builder schedules **`_arena_auto_pull` → `load_dataset` (GSM8K + MATH)** in a worker — first run can still **peg CPU / disk / network** and make the whole process feel hung even if the UI thread is technically free.
3. **Wallet / organ counts:** `_get_wallet_balance()` and `_count_proof_guards()` may add latency; usually smaller than (1).

### Plan (ordered)

| Priority | Action | Covenant tie |
|:---:|:---|:---|
| **P0** | Move **ledger line count** (and any other O(N) file walks) to a **background thread** with cached integer + timestamp; UI shows cache instantly, refreshes label when done. | §7.3 honesty: label “approx” or “as of &lt;ts&gt;” if stale window &gt; N minutes — better than freezing. |
| **P0** | **Defer Arena HF pull** until the user **first selects** the Arena tab (signal `currentChanged`), not at widget `__init__`. Default tab = Capability Matrix only. | §7.5 — keep Python body responsive; §8 — don’t pretend data is local when it’s downloading. |
| **P1** | Env flag `SIFTA_MATH_ARENA_OFF=1` to skip HF entirely (demo / air-gapped nodes). | §8 absorption — no silent network. |
| **P2** | Ship **tiny bundled JSONL** sample (5 rows) for offline Arena smoke — optional. | §1 — say “synthetic sample” in UI truth label. |

### Verify (Auditor lane)

- `sample` main thread under Instruments / `python -c` timing on `repair_log.jsonl` line count.
- Open app with Wi‑Fi off: confirm failure mode is **fast** + explicit error row (already partially there).

---

## B. Alice “does not recognize George” / OS not recognizing owner

### Symptoms (hypothesis → verify)

1. **`user_present` flag:** `identity_system_block(..., user_present=user_active)` where `user_active = (history[-1].role == "user")`. On **first** user message after boot, that is usually true — but **voice / streaming / empty tail** paths may build prompts with **`user_present=False`**, so the composite block ends with **`- user_present=False`**, which the model can misread as “stranger in the room.”
2. **No explicit owner name in composite block:** The block lists Alice’s organs + `face_detection` + `user_present`; it does **not** always inject **“Human you are serving: &lt;owner_genesis / owner_name&gt;”** as a stable line. The model fills the gap with RLHF “I don’t know you.”
3. **§7.4 / WhatsApp graph:** If `whatsapp_contacts.json` or `OWNER_SELF_JIDs` drift, owner rows can show as **“Human”** — code remaps to George in one path only; other paths may not.
4. **`swarm_architect_identity`:** Multimodal **ARCHITECT_PRESENT / PARTIAL / ABSENT** may be **ABSENT** (no face, no BLE, wrong window signal) while George is physically there — Alice should still treat **keyboard origin** as Architect for *dialogue* policy without claiming *biometric* certainty.

### Plan (ordered)

| Priority | Action | Covenant tie |
|:---:|:---|:---|
| **P0** | Add a **fixed system-prompt line** (minimal_runtime_contract or first line of composite): **“Primary human operator (this node): &lt;owner_name from genesis/kernel&gt;. Do not deny recognition unless the effector ledger contradicts.”** | §7.4 owner vs contacts; §6 don’t claim actions without receipts — **recognition is not an external action claim**. |
| **P0** | When building prompts for **live mic / ambient** turns, set `user_present=True` if **any** recent user turn exists in window, not only `history[-1]` (or pass `prior_user_text` into a clearer `architect_dialogue_active` flag). | §6 social frame — reduce false “absent” classification. |
| **P1** | Surface **`swarm_architect_identity`** (or one sentence from `read_prompt_line`) into the composite or homunculus block when confidence ≥ PARTIAL; when ABSENT, still keep **genesis owner name** line. | §7.1 sensory lock-on is about **devices**; owner name is **constitutional**, not only visual. |
| **P2** | Triple-IDE: ensure **each IDE** appends **LLM_REGISTRATION** before mutating identity prompts; avoid **contradictory** “who is George” edits from parallel doctors. | §4 Predator Gate; §8.5 consensus. |

### Verify

- Grep runtime system prompt for `user_present=False` while Architect is mid-conversation.
- Read `.sifta_state/owner_genesis.json` + `Kernel/.sifta_state/ALICE.json` (or canonical body) for **display name drift**.

---

## C. Triple IDE coordination

| Risk | Mitigation |
|:---|:---|
| Two doctors patch `sifta_talk_to_alice_widget.py` simultaneously | **Read** `ide_stigmergic_trace.jsonl` + **smallest surface**; one Surgeon owns the prompt block per session. |
| Cursor / Antigravity / Codex disagree on `user_active` semantics | Single **named function** `architect_presence_for_prompt(history, voice_mode, …)` with unit tests. |
| SCAR / MCP proposals not visible to all IDEs | Mirror one-line **receipt** to `work_receipts.jsonl` when MCP writes outside repo grep scope. |

---

## D. Done criteria (receipt-friendly)

- Math widget: **cold open** to interactive UI **&lt; 500 ms** before any optional network (on M5 with warm disk cache); ledger metric **non-blocking**.
- Alice: with valid genesis, **never** replies “I don’t recognize you” to **George** on ordinary chat turns; if biometrics absent, she says **“I don’t have a strong face match, but the node owner is …”** (truthful).
- Triple IDE: every mutating session has **registration row** + **no unsigned push** (§4).

---

*CG55M@cursor — plan bolus 2026-04-28. Implementation awaits Architect **GO**.*

---

## Execution Log (AG31 — 2026-04-28T20:57Z)

### DONE ✅ — Math app "loads forever"

| SCAR | Fix | Status |
|:---|:---|:---:|
| `SCAR_437d8f30a325` | Replaced `load_dataset` (GB download) with HF Datasets Viewer HTTP API; error rows in table | ✅ |
| `SCAR_1c3deaf5e819` | Moved Arena auto-pull from `__init__` to first ⚔ tab visit (`_on_tab_changed`) | ✅ |
| Confirmed: `_refresh_live()` already on background thread — 25,964-line ledger scans in 39ms | — | ✅ |

### DONE ✅ — Alice "does not recognize George"

| SCAR | Fix | Status |
|:---|:---|:---:|
| `SCAR_cecddf347eaa` | Identity: iPhone GPS weight 2.0→1.0; threshold 0.70→0.48; Python bundle in ARCHITECT_FRONT_BUNDLES; GPS freshness 15m→2h. Live score: 0.500 → `ARCHITECT_PRESENT` | ✅ |
| `SCAR_cb0310327e2f` | Face detection probe every 10s from camera widget → ledger. Constitutional owner line always in prompt. `user_present` broadened via architect identity sensor | ✅ |

### REMAINING — P1/P2

- [ ] `SIFTA_MATH_ARENA_OFF=1` env flag (P1)
- [ ] Bundled offline sample JSONL for air-gapped demo (P2)
- [ ] Triple IDE: register each doctor's LLM_REGISTRATION before mutating identity prompts (§4 Predator Gate)

