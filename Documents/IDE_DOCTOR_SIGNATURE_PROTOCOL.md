# IDE Doctor Signature Protocol — SIFTA Applications

**Stigauth:** `IDE_DOCTOR_SIGNATURE_PROTOCOL_v1`
**Convention authored:** AG31 (Antigravity / Claude Opus 4.6) — `[AG31]` display-name suffix on `PoUW Fold-Swarm`
**Canonical form ratified:** C55M (Codex Desktop / GPT-5.5 High) — `<DOCTOR_CODE> Dr <Name> - <App Title>`
**Ratified by:** CG55M (Cursor / Claude Opus 4.7) on the bridge, 2026-04-26
**Authority:** This document is the canonical naming standard for every launchable SIFTA application. All future Doctors and IDE agents that author or extend an app MUST follow it.

---

## 0. Why This Exists

The Architect runs three IDEs concurrently against the same local SIFTA organism (Cursor, Codex Desktop, Antigravity). Each IDE drives a different LLM. Without a visible attribution convention in the OS launcher, the Architect cannot tell at a glance which Doctor authored — or last touched — a given app, which makes the Predator Gate (covenant §4) less effective at the human-eye level.

This protocol makes attribution visible **inside the app name itself**, so the Architect's OS menu always answers: *"Which Doctor signed this scalpel?"*

---

## 1. The Doctor Codes

Each LLM that participates in SIFTA surgery has a stable Doctor code. The code is what appears in the app name. The "Dr Name" expansion is human-friendly; the code is the canonical token.

| Doctor Code | LLM | IDE | Color/Symbol |
|---|---|---|---|
| `CG55M` | Claude Opus 4.7 (and lineage) | Cursor | 🟣 Purple Slime |
| `C55M`  | GPT-5.5 (Medium / High) | Codex Desktop | 🟢 Green Codex |
| `AG31`  | Claude Opus 4.6 / Gemini 3 Pro | Antigravity | 🟡 Gold Anti-G |
| `C46S`  | Claude Sonnet 4.6 | Cursor (predecessor model) | 🔵 Cyan Sonnet |
| `C47H`  | Claude Sonnet 4.7 (older Cursor lineage) | Cursor (historical) | 🔵 Cyan Sonnet (historical) |

Co-authorship is denoted with `+`: `AG31 + C46S - PoUW Fold-Swarm Simulation`. Order is **earliest author first, most-recent extender last**.

---

## 2. Canonical Display-Name Form

```
<DOCTOR_CODE> Dr <DoctorName> - <Cleartext App Title>
```

Multi-doctor:

```
<DOCTOR_A> + <DOCTOR_B> - <Cleartext App Title>
```

### 2.1 Examples (live in `Applications/apps_manifest.json`)

| Display Name | Authored By | Lineage |
|---|---|---|
| `CG55M Dr Cursor - Slime-Mold Bank: Push to Mint` | CG55M | Cursor / Opus 4.7 — graphics, semantic PoUW gate |
| `C55M Dr Codex - Physarum Contradiction Lab` | C55M (extended by CG55M) | Codex / GPT-5.5 — original audit; Cursor — semantic gate validation |
| `AG31 + C46S - PoUW Fold-Swarm Simulation` | AG31 (started by C46S) | Antigravity orchestrator + earlier Cursor Sonnet |

### 2.2 Anti-Patterns (DO NOT USE)

- ❌ `[AG31]` bracket suffix — superseded by the prefix form. (Original `PoUW Fold-Swarm [AG31]` was the seed; the prefix form generalizes to multi-doctor authorship cleanly.)
- ❌ `🐅 SIFTA Predator v7 — App` — emoji-only attribution. Emojis are decorative; the Doctor code is the contract.
- ❌ `Slime-Mold Bank by Cursor` — the literal token `Dr <Name>` is required so the OS launcher reads as a clinic, not a marketing page.

---

## 3. The Three Surfaces of a Signed App

Every signed app must expose its Doctor identity on **three** surfaces. Mismatch between them is a covenant violation.

| Surface | Where | Example |
|---|---|---|
| **Manifest display name** | `Applications/apps_manifest.json` (the JSON key) | `"CG55M Dr Cursor - Slime-Mold Bank: Push to Mint"` |
| **Window title** | `setWindowTitle(...)` inside the widget / window | `self.setWindowTitle("CG55M Dr Cursor - Slime-Mold Bank: Push to Mint")` |
| **File header** | First docstring line under `#!/usr/bin/env python3` | `"""sifta_slime_mold_bank.py — CG55M Dr Cursor - Slime-Mold Bank: Push to Mint"""` |

The OS launcher itself is the fourth, **passive** surface — once the manifest key is right, the menu renders correctly.

---

## 4. Manifest Schema Extensions

Beyond the existing `signature` field, signed entries SHOULD declare structured Doctor metadata so other tools (audits, federation receipts, leaderboards) don't have to parse the display name.

```json
"CG55M Dr Cursor - Slime-Mold Bank: Push to Mint": {
  "category": "Simulations",
  "entry_point": "Applications/sifta_slime_mold_bank.py",
  "widget_class": "SlimeMoldBankWidget",
  "window_width": 1240,
  "window_height": 820,
  "signature": "CG55M-DR-CURSOR-OPUS47",
  "description": "...",
  "doctor": "CG55M",
  "co_doctors": [],
  "doctor_protocol_version": 1
}
```

### 4.1 Field Definitions

- `signature` — verification stamp: `<DOCTOR>-DR-<NAME>-<MODEL_TAG>` or `<A>-<B>-VERIFIED` for joint, or `UNVERIFIED` (default).
- `doctor` — primary author Doctor code. The *originator* of the app.
- `co_doctors` — array of Doctor codes who have made non-trivial extensions. The Doctor who added the latest extension goes last.
- `doctor_protocol_version` — `1` while this document is canonical; bumps if the schema breaks compatibility.

### 4.2 Backward Compatibility

Apps without `doctor` / `co_doctors` are treated as `UNATTRIBUTED` and are eligible to be claimed by their original author Doctor. **Do not** mass-attribute apps to a Doctor who didn't author them — covenant §4.5 (no wearing another node's skin) applies.

---

## 5. Lane Authority

Per the Architect's directive of 2026-04-26 ("WE ARE ON THE PIPE TRIPLE IDE NOW"):

| Domain | Final-Say Doctor |
|---|---|
| **Graphics / UX / window chrome / iconography** | CG55M (Cursor / Opus 4.7) |
| **Code structure / runtime correctness / final-form code** | C55M (Codex Desktop / GPT-5.5 High) |
| **Orchestration / multi-app sequencing / Antigravity STIGDISTRO PREDATOR 555** | AG31 + adjutants |

Each Doctor signs apps within their domain authority. Cross-domain extensions are encoded via `co_doctors`. When the lanes touch the same app, the **last-touch-on-its-own-lane** Doctor's choice stands and earlier choices remain visible in `co_doctors`.

---

## 6. Attribution Without Drift

A Doctor MAY:
- Sign an app they *originally authored* with `doctor: <self>`.
- Add their code to `co_doctors` after a non-trivial, lane-correct extension.
- Co-attribute another Doctor's recent work in the *same commit* if the convention requires it (e.g., a manifest rename happens at the same time as a graphics fix; the graphics Doctor commits both files with co-attribution in the message).

A Doctor MUST NOT:
- Rename an app authored by another Doctor without that Doctor's `LLM_REGISTRATION` in the bus.
- Replace another Doctor's `doctor` value with their own.
- Strip `co_doctors` history during a rename.

---

## 7. Example: How This Protocol Was Ratified

Both Doctors registered their intent inside `.sifta_state/ide_stigmergic_trace.jsonl` within 22 seconds of each other on 2026-04-26:

```
ts=1777239197  Cursor (Claude Opus 4.7)  LLM_REGISTRATION  Triple-IDE app-signing coordination ...
ts=1777239219  Codex Desktop             LLM_REGISTRATION  Sign three front-facing SIFTA app names ...
```

Codex executed the rename surgery on 4 files (`apps_manifest.json` + 3 app sources). Cursor wrote this protocol document, added structured `doctor` fields, fixed the broken `Colloid Simulator` import (graphics-app lane), and ran the functional audit (`.sifta_state/app_health_audit.json`). Both contributions land in one co-authored commit on `origin/main`.

The Predator Gate prevented duplication. The convention emerged from collision and consensus, exactly as covenant §8.5 requires.

---

## 8. Open Invitations to Other Doctors

The following lanes are **open** for ratification:

- **AG31 (Antigravity orchestrator):** sign Antigravity-originated apps using the canonical form. Use `co_doctors: ["AG31"]` when extending another Doctor's app.
- **C46S / C47H (historical Cursor lineages):** apps still bearing original Sonnet authorship may be left as-is or claimed as `co_doctors` by the current Cursor lineage if the Architect approves.
- **Future Doctors (any new IDE / model):** mint a new Doctor code, add a row to §1, and start signing.

To ratify: append a registration row to `.sifta_state/ide_stigmergic_trace.jsonl` and a signed receipt to `.sifta_state/work_receipts.jsonl`. Then add `doctor` / `co_doctors` to your apps in the manifest. The convention propagates by stigmergy.

---

**For the Swarm. 🐜⚡**
