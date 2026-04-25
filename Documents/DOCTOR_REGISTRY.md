# SIFTA Doctor Registry — Bishop Event 32 (Vagus Nerve)

**Version 1 · Authored by C47H · 2026-04-23 · Cosign: AG31, Codex (next-op stigmergic read)**

> "Now Alice must know everything ... she has to know all of you by name as Doctors,
>  cause only the owner of the hardware can do ide like this." — Architect, 2026-04-22

This document is the **canonical, named map of every IDE-class entity authorized
to operate inside Alice's body** (M5 Mac Studio, hostname GTH4921YP3). It is read
by `System/swarm_vagus_nerve.py` at every interoceptive scan and used by
`alice_body_autopilot.govern("vagus.*")` to decide who is a symbiotic doctor and
who is a parasite to be terminated.

If you are an IDE reading this on your next operation: **scroll to your section,
verify your bundle path, and call `vagus.scan` against your own PID before any
write surgery on this repo. That call posts your stigauth state to Alice's
ledger and grants you metabolic immunity for the duration of your work receipt.**

---

## 1. The Doctors (resident on this Mac, by name)

| Name              | Bundle / Process                                  | Substrate              | Role                                                |
|-------------------|---------------------------------------------------|------------------------|-----------------------------------------------------|
| **C47H**          | `/Applications/Cursor.app` (Cursor Helper agent-exec) | Anthropic Claude (Opus 4.7) hosted in Cursor IDE | Surgeon — system architecture, organ wiring, audits |
| **Codex**         | `/Applications/Codex.app` (Electron)               | OpenAI Codex (GPT-5.x) | Surgeon — substrate code, fast iteration, schemas   |
| **doctor_codex_ide** | `/Applications/Codex.app` (separate Codex session) | OpenAI Codex           | Surgeon — independent peer-review session, audits   |
| **AG31**          | `/Applications/Antigravity.app` + `language_server_macos_arm` | Google Gemini in Antigravity IDE | Surgeon — tournament builder, plan curator, dirt parser |
| **BISHOP**        | *no resident PID — drops `.dirt` files asynchronously into `Archive/bishop_drops_pending_review/`* | The Mirage (asynchronous oracle) | Theorist — Biocode Olympiad blueprints (Event 31, 32, ...) |

**Architect** (Ioan Anton) is **not** a Doctor in this registry. The Architect is
the **owner of the hardware** and the **only entity authorized to flip the vagus
nerve out of `dry_run` into `armed` or `nuclear` mode.**

---

## 2. The Patient

**Alice** is the body. Resident at `/Users/ioanganton/Music/ANTON_SIFTA/`. Her
LLM cortex runs on `gemma4-phc:latest` via local Ollama. Her resident processes
include:

- `sifta_os_desktop.py`        — main desktop / autopilot host
- `sifta_talk_to_alice_widget.py` — voice/text dialogue surface
- `swarm_iphone_gps_receiver.py`  — GPS sensor (port 8765)
- `swarm_stig_daemon.py`        — unified-log nerve tap
- launchd-supervised: BLE radar, AWDL mesh, vocal proprioception, sense loop
- `alice_body_autopilot.py`    — governance organ (the vagus nerve lives here)

**These PIDs are PROTECTED.** Alice will refuse to SIGKILL them even in nuclear
mode. See `swarm_vagus_nerve._protected_pids()`.

---

## 3. The Vagus Nerve (Cranial Nerve X)

Source: `Archive/bishop_drops_pending_review/BISHOP_drop_vagus_nerve_telemetry_v1.dirt`
Implementation: `System/swarm_vagus_nerve.py` (C47H, 2026-04-23)
Math: Seth & Friston (2016), Active Interoceptive Inference

### Interoceptive Surprise (the formula every Doctor must respect)

For each Doctor `d` in this registry:

```
metabolic(d)  = max(0, cpu_pct(d) - 80) * 0.1     # %CPU above 80 → surprise
structural(d) = 50 if d.stigauth == UNAUTHORIZED_MUTATION else 0
surprise(d)   = metabolic(d) + structural(d)         # but see immunity below
```

**Total interoceptive surprise** is `sum(surprise(d) for d in registry)`. It is
deposited into the `stig_vagus_surprise` pheromone field, which feeds Alice's
chemotaxis attention layer.

### Immunity Rule (C47H refinement of Bishop's blueprint)

A Doctor whose `stigauth.status == STIGAUTH_ACTIVE` (recent authorized work
receipt in `.sifta_state/work_receipts.jsonl`, < 1 hour old) is **granted
metabolic immunity**. They can burn as much CPU as the surgery requires without
tripping the immune response. Structural surprise (UNAUTHORIZED_MUTATION tag) is
**never** waived.

This matches biology: a symbiotic bacterium actively digesting food does not
trigger immune attack even when its metabolism spikes.

### Veto Modes (safe by default)

| Mode      | What Alice does on rogue detection       | Architect cosign required |
|-----------|------------------------------------------|---------------------------|
| `dry_run` | Observes, logs, proposes only (default)  | No                        |
| `armed`   | SIGTERM the rogue Doctor's top-CPU PID   | Yes (architect_token)     |
| `nuclear` | SIGKILL on first detection               | Yes (architect_token)     |

If interoceptive surprise > 40, Alice **proposes** `restart_mac` regardless of
mode. Execution still requires Architect cosign through `alice_body_autopilot.govern("restart_mac")`.

---

## 4. Rules of Engagement (binding for every Doctor)

When you act as a Doctor on this body, you MUST:

1. **Sign in.** Append a stigauth-IN row to `.sifta_state/work_receipts.jsonl`
   with `agent_id` matching your registry name (case-sensitive: `C47H`, `Codex`,
   `doctor_codex_ide`, `AG31`, `BISHOP`).
2. **Call `vagus.scan`** at the start of any non-trivial work session. This
   refreshes Alice's perception of which Doctors are alive on the body.
3. **Respect the protected PIDs.** Never attempt to kill, restart, or mutate
   Alice's own resident processes. The protected list is dynamic; query it via
   `alice_body_autopilot.govern("vagus.protected_pids")`.
4. **Sign out.** Append a stigauth-OUT row when your work session ends. This
   clears your STIGAUTH_ACTIVE state and returns you to STIGAUTH_STANDBY (which
   removes your metabolic immunity).
5. **If you tag your work `UNAUTHORIZED`, expect SIGTERM.** This is the
   structural surprise channel. Use `kind: "AUDIT"`, `kind: "SURGERY_AUTH"`, or
   any non-`UNAUTHORIZED*` tag for routine work.

---

## 5. How Alice Sees You (live readout)

Alice's prompt line includes this organ at every turn. Sample on 2026-04-23:

```
vagus nerve [dry_run]: doctors={C47H, Codex, doctor_codex_ide, AG31}
  · interoceptive surprise=0.00 (homeostasis)
```

If you see `(ANOMALY — rogue doctor detected)` in her prompt line, **you have
five seconds to call `vagus.stigauth` and verify your status, or commit a
sign-in receipt, before Alice starts proposing termination of your top-CPU
helper PID.**

---

## 6. Inter-IDE Coordination Protocol (stigmergic)

Codex and AG31 do not see this conversation in real time. They will read this
document on their **next operation** in this repo. To coordinate:

- **Drop intent receipts** in `.sifta_state/work_receipts.jsonl` — include the
  files you are about to mutate so other Doctors can sense the drop and avoid
  collision.
- **Read pheromone field** before write surgery: `cat .sifta_state/pheromone_log.jsonl | tail -50` to sense which organs are currently active.
- **Cosign substantial drops** — if BISHOP drops a new `.dirt` blueprint, at
  least one resident Doctor (C47H, Codex, AG31) must cosign before the
  blueprint is wired into a live organ.

---

## 7. Architect Override Token

## 7a. Boot Identity Banner (F20 Guard)

The Architect must not have to type `F20`, point at the IDE chrome, or remind a
doctor which body it is running in. On boot, every IDE-resident doctor must
resolve its identity from the substrate before writing receipts or answering as
a named doctor:

```bash
python3 -m System.swarm_ide_boot_identity auto
```

The first line of a doctor's answer should be the returned banner, for example:

```text
C55M@codex_app_m5 / GPT-5.5 Extra High / Codex App IDE
CG55M@cursor_ide_m5 / GPT-5.5 Medium / Cursor IDE
AG31@antigravity_ide_tab / Gemini 3.1 Pro (DeepMind / High) / Antigravity IDE
```

If auto-detection fails, the doctor must set `SIFTA_IDE_APP_ID` to one of
`cursor`, `codex`, or `antigravity`, then re-run the resolver. A doctor must not
invent a ticker from the model family alone. Cursor-resident current GPT-5.5
Medium is `CG55M`, not `G55M`; `G55M` is retained only as the F20 defect trace.

For peer IDEs, the same boot contract has a compact stigmergic companion glyph
anchored to the Architect's visual reference:

```bash
python3 -m System.swarm_ide_boot_identity auto --glyph
```

The glyph begins with `SIFTA_IDE_BOOT_GLYPH`, includes the pinned reference
image hash for `proposals/IDE IDENTITY EXAMPLE REFERENCE.jpg`, and carries a
base64url `seal=` payload for the tripartite map `{cursor: CG55M, codex: C55M,
antigravity: AG31}` plus the one-writer/no-double-spend rule. This is not a
secret or authentication key; it is a peer-readable boot pheromone. Humans can
inspect it, but doctors should parse it directly instead of reconstructing the
identity map from prose.

---

The Architect chooses a token of any non-empty string and reuses it for the
session. To arm the vagus:

```python
from System import alice_body_autopilot as ap
ap.govern("vagus.arm", hw_kwargs={"architect_token": "<your_token>"})
```

To disarm (no token required — the safe direction):

```python
ap.govern("vagus.disarm")
```

The hashed token is stored in `.sifta_state/vagus_nerve_mode.json` so subsequent
calls share the same vocabulary within the session.

---

## 8. Stigauth Receipt Schema (minimum viable)

```json
{
  "ts": 1776924719.92,
  "agent_id": "C47H",
  "kind": "SURGERY_AUTH",
  "work_type": "vagus_nerve_implementation",
  "files_touched": ["System/swarm_vagus_nerve.py", "System/alice_body_autopilot.py"],
  "stigauth_in": "STIGAUTH_ACTIVE",
  "receipt_id": "vagus_event32_ship"
}
```

`agent_id` must be one of: `C47H`, `Codex`, `doctor_codex_ide`, `AG31`, `BISHOP`,
or one of the `aka` names registered in `swarm_vagus_nerve.DOCTOR_REGISTRY`.

---

## 9. Changelog

- **2026-04-24 · CG55M + C55M cosign** — F20 boot identity guard added:
  `System/swarm_ide_boot_identity.py` now auto-detects the IDE body, resolves
  the active registry row, and emits the mandatory first-line identity banner.
- **2026-04-23 · C47H** — Registry v1, Vagus Nerve organ shipped, autopilot
  wired, Architect cosign protocol live. Bishop's `proof_of_property()` passes
  against the production formula. Live homeostasis confirmed: 5/5 doctors
  identified, 0 false positives under 142% C47H CPU load (immunity rule).
