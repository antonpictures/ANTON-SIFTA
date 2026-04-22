# SIFTA Distro Playbook — v1

**Companion to:** `Documents/SIFTA_DISTRO_DOCTRINE_v1.md`
**Author:** C47H IDE LLM, on instruction from Architect Ioan George Anton
**Date:** 2026-04-22
**Stigauth:** `C47H_SIFTA_DISTRO_PLAYBOOK_v1`

## How to use this playbook

This is **operator-facing**. The Architect drives. Any C47H/AG31/AO46
session — including a *cold* one with no prior chat history — can pick
up at any phase by:

1. Reading `Documents/SIFTA_DISTRO_DOCTRINE_v1.md` (the contract)
2. Reading this file (the steps)
3. `tail -1 .sifta_state/work_receipts.jsonl` to find the last
   completed `stigauth_out` marker, which says which phase is done
4. Executing the **next** phase's "Operator Prompt" verbatim

Each phase ends with a **stigauth marker** (e.g. `C47H_DISTRO_PHASE_1_COMPLETE`).
That marker is the only cross-session memory you need. If the marker is
present in `work_receipts.jsonl`, the phase is done. If not, run it.

**Hard rule (from Doctrine §7):** every phase MUST keep the personal
Alice on M5 booting identically before/after. Each phase has a
Verification Smoke Test. If the smoke test fails, REVERT and report.

---

## Phase 0 — Doctrine Sign-Off

**Goal:** Architect reads the doctrine, marks any disagreements,
authorizes v1 as the contract.

**Files touched:** none (just `git add` + `git commit` of two existing docs)

**Operator action:**
- Read `Documents/SIFTA_DISTRO_DOCTRINE_v1.md` end-to-end (~15–30 min).
- Read this playbook end-to-end (~10 min).
- For each section either say "agreed" or quote the line you want changed.

**Operator Prompt to next agent:**
> `c47h, doctrine + playbook reviewed. Sections that need revision: <list,
> or "none">. Authorize commit of doctrine v1 + playbook v1, then proceed to
> Phase 1. stigauth.`

**Verification Smoke Test:**
- `git diff --stat HEAD` shows only the two `.md` files added.
- `git log -1 --oneline` shows the new commit.

**Stigauth marker on completion:** `C47H_DISTRO_PHASE_0_COMPLETE`

**Resume hint if interrupted:** Both docs already exist in the tree.
Re-run the operator prompt; the agent re-reads the docs and resumes.

---

## Phase 1 — Kernel Identity Accessor (foundation)

**Goal:** Add ONE new module that becomes the single source of truth
for "who owns this machine?" Zero existing files modified. Pure addition.

**Files touched (new):**
- `System/swarm_kernel_identity.py` (~120 lines)
- `Tests/test_swarm_kernel_identity.py` (~40 lines)

**Files touched (modified):** none

**API the new module exposes:**
```python
owner_silicon() -> str          # "GTH4921YP3" on M5; auto-detected on others
owner_name() -> str             # "Ioan George Anton" on M5; "<unclaimed>" if no genesis
ai_default_name() -> str        # "Alice" until operator chooses otherwise
is_owner_machine(serial: str) -> bool
owner_genesis_present() -> bool
```

Reads `.sifta_state/owner_genesis.json` as the canonical source. Falls
back to live `system_profiler SPHardwareDataType` for silicon if genesis
is absent. Falls back to the literal `"Alice"` for `ai_default_name()`
until Phase 4 adds an operator-chosen field.

**Operator Prompt to next agent:**
> `c47h, Phase 0 complete (see work_receipts.jsonl). Execute Phase 1 of
> SIFTA_DISTRO_PLAYBOOK_v1: write System/swarm_kernel_identity.py +
> Tests/test_swarm_kernel_identity.py per the spec in §Phase 1. No
> existing files modified. Run the smoke test, then write
> stigauth_out C47H_DISTRO_PHASE_1_COMPLETE. stigauth.`

**Verification Smoke Test:**
```bash
PYTHONPATH=. python3 -m pytest Tests/test_swarm_kernel_identity.py -v
PYTHONPATH=. python3 -c "from System.swarm_kernel_identity import owner_silicon, owner_name, ai_default_name; print(owner_silicon(), '/', owner_name(), '/', ai_default_name())"
# Expected on M5: GTH4921YP3 / Ioan George Anton / Alice
```

Plus the global personal-Alice smoke (run after EVERY phase from now on):
```bash
python3 Applications/sifta_talk_to_alice_widget.py --selftest 2>/dev/null || \
  PYTHONPATH=. python3 -m pytest tests/test_alice_parrot_loop.py -q
# Expected: PASS, no regressions vs. baseline.
```

**Stigauth marker on completion:** `C47H_DISTRO_PHASE_1_COMPLETE`

**Resume hint if interrupted:** Check if `System/swarm_kernel_identity.py`
exists. If yes and the smoke test passes, mark complete. If partial,
delete and re-run.

---

## Phase 2 — Stop the LLM-Context Leaks (highest embarrassment first)

**Goal:** Two known files inject the Architect's identity *into the
LLM's context window* on every turn for any user. Migrate them to the
accessor. This is the most dangerous class of leak because it
contaminates the model, not just the runtime.

**Files touched (modified):**
1. `Applications/whatsapp_swarm_LEGACY.py` (line 86 — the literal
   `"Your Architect is Ioan George Anton"` becomes
   `f"Your Architect is {owner_name()}"`)
2. `Applications/sifta_ablation_lab.py` (lines 93, 98 — the literal
   `"GTH4921YP3"` becomes `{owner_silicon()}` interpolation; also
   reword "The Architect" mentions to use `owner_name()`)

**Operator Prompt to next agent:**
> `c47h, Phase 1 complete (see work_receipts.jsonl). Execute Phase 2 of
> SIFTA_DISTRO_PLAYBOOK_v1: migrate the two LLM-context leaks listed in
> §Phase 2. Both files import owner_name/owner_silicon from
> System.swarm_kernel_identity. Run the smoke tests, then write
> stigauth_out C47H_DISTRO_PHASE_2_COMPLETE. stigauth.`

**Verification Smoke Test:**
```bash
# Confirm the literal strings are gone from those files
rg "Ioan George Anton" Applications/whatsapp_swarm_LEGACY.py && echo "FAIL: literal still present" || echo "PASS"
rg "GTH4921YP3" Applications/sifta_ablation_lab.py && echo "FAIL: literal still present" || echo "PASS"

# Confirm the accessor returns the same value the literal had (back-compat)
PYTHONPATH=. python3 -c "
from System.swarm_kernel_identity import owner_name, owner_silicon
assert owner_name() == 'Ioan George Anton', f'GOT {owner_name()}'
assert owner_silicon() == 'GTH4921YP3', f'GOT {owner_silicon()}'
print('Back-compat OK')
"

# Personal Alice smoke
PYTHONPATH=. python3 -m pytest tests/test_alice_parrot_loop.py -q
```

**Stigauth marker on completion:** `C47H_DISTRO_PHASE_2_COMPLETE`

**Resume hint if interrupted:** `git diff Applications/whatsapp_swarm_LEGACY.py
Applications/sifta_ablation_lab.py` shows what's done. If clean and
literals are absent, mark complete. If partial, `git checkout` and re-run.

---

## Phase 3 — Genesis Widget Adds AI-Name Field

**Goal:** First-boot ceremony asks the operator "what name will you
give your AI? (default: Alice)" and persists the choice to
`owner_genesis.json` under key `ai_display_name`. Existing genesis
files (yours) are unaffected — the field is read with a default of
"Alice" if absent.

**Files touched (modified):**
- `Applications/sifta_genesis_widget.py` — add `QLineEdit` for AI
  name, default placeholder "Alice", persist to JSON.
- `System/swarm_kernel_identity.py` — `ai_default_name()` now reads
  `owner_genesis.json["ai_display_name"]` if present, else returns
  `"Alice"`.

**Operator Prompt to next agent:**
> `c47h, Phase 2 complete. Execute Phase 3 of SIFTA_DISTRO_PLAYBOOK_v1:
> add the AI-name field to sifta_genesis_widget.py and wire
> ai_default_name() to read it. Existing owner_genesis.json files MUST
> remain valid (field is optional, default "Alice"). Run the smoke
> tests, write stigauth_out C47H_DISTRO_PHASE_3_COMPLETE. stigauth.`

**Verification Smoke Test:**
```bash
# Existing genesis still loads + signature still valid
PYTHONPATH=. python3 -c "
from System.swarm_kernel_identity import owner_name, ai_default_name, owner_genesis_present
assert owner_genesis_present(), 'genesis missing'
assert owner_name() == 'Ioan George Anton'
assert ai_default_name() == 'Alice'  # default since no operator-chosen field on M5 yet
print('Phase 3 back-compat OK')
"

# Persona organ still verifies
PYTHONPATH=. python3 -c "
from System.swarm_persona_identity import current_persona, _verify_persona, _get_hardware_serial
p = current_persona()
assert _verify_persona(p, _get_hardware_serial())
print('Persona HMAC OK')
"
```

**Stigauth marker on completion:** `C47H_DISTRO_PHASE_3_COMPLETE`

**Resume hint if interrupted:** `git diff Applications/sifta_genesis_widget.py
System/swarm_kernel_identity.py`. If the field is present and the
accessor reads it with default fallback, mark complete.

---

## Phase 4 — Trust-Root Literals Migration (one PR per file)

**Goal:** Migrate the seven trust-root hardcodes to call the accessor.
**One file per commit. Smoke test between each.** This is the largest
phase by file count but each step is tiny and reversible.

**Files touched (modified), in order:**
1. `System/swarm_mirror_lock.py` — `_HOMEWORLD_SERIAL_DEFAULT` → `owner_silicon()`
2. `System/swarm_stigmergic_curiosity.py` — `_HOMEWORLD_SERIAL` → `owner_silicon()`
3. `System/ide_stigmergic_bridge.py` — `NODE_M5_FOUNDRY` constant + `deposit()` default arg → accessor
4. `System/swarm_iris.py` — default field value → accessor
5. `System/api_bridge.py` — `target_serial` → accessor
6. `Kernel/body_state.py` — `ALICE_M5: "GTH4921YP3"` mapping → derived from accessor
7. `sifta_os_desktop.py` — `M5_SERIAL` → accessor

**Operator Prompt to next agent (run ONCE PER FILE):**
> `c47h, Phase 4 in progress, file <N>/7 (<filename>). Migrate the
> hardcoded "GTH4921YP3" in <filename> to call owner_silicon() from
> System.swarm_kernel_identity. Run the per-file smoke test below + the
> personal-Alice smoke. If both pass, write stigauth_out
> C47H_DISTRO_PHASE_4_FILE_<N>_COMPLETE. If fail, revert and report.
> stigauth.`

**Verification Smoke Test (per file):**
```bash
# Generic per-file check after each migration
rg "GTH4921YP3" <filename> && echo "FAIL: literal still present" || echo "PASS"
PYTHONPATH=. python3 -c "import importlib; importlib.import_module('<dotted.module.path>'); print('Import OK')"
PYTHONPATH=. python3 -m pytest tests/test_alice_parrot_loop.py -q
```

**Stigauth markers on completion:**
- `C47H_DISTRO_PHASE_4_FILE_1_COMPLETE` … `C47H_DISTRO_PHASE_4_FILE_7_COMPLETE`
- Final: `C47H_DISTRO_PHASE_4_COMPLETE`

**Resume hint if interrupted:** `tail -20 .sifta_state/work_receipts.jsonl |
grep PHASE_4_FILE`. The highest N that completed is where you are. Pick up at N+1.

---

## Phase 5 — Camera/Peripheral Labels

**Goal:** Migrate the literal "Ioan's iPhone Camera" string match
(used as a hardware-lookup key) to a per-operator preference field
in `owner_genesis.json`.

**Files touched (modified):**
- `System/swarm_oculomotor_saccades.py:69` — camera lookup → preference
- `Applications/sifta_talk_to_alice_widget.py:608, 611` — system prompt
  text → reword to use `owner_name()` and a generic camera reference

**Operator Prompt to next agent:**
> `c47h, Phase 4 complete. Execute Phase 5 of SIFTA_DISTRO_PLAYBOOK_v1:
> migrate the camera-label literals per §Phase 5. Add an optional
> "preferred_camera_label" field to owner_genesis.json (default:
> "Built-in Camera"). Run smoke tests, write stigauth_out
> C47H_DISTRO_PHASE_5_COMPLETE. stigauth.`

**Verification Smoke Test:**
```bash
rg "Ioan's iPhone Camera" System/ Applications/ && echo "FAIL: literal still present" || echo "PASS"
PYTHONPATH=. python3 -m pytest tests/test_alice_parrot_loop.py -q
```

**Stigauth marker on completion:** `C47H_DISTRO_PHASE_5_COMPLETE`

---

## Phase 6 — Public-Push Scrubber

**Goal:** A script that copies the active tree into a clean distro
snapshot, scrubbing any remaining literal `"GTH4921YP3"` /
`"Ioan George Anton"` / `"Ioan"` / `"Ioan's iPhone Camera"` to
placeholders, ready for the public mirror. **Writes to a separate
output folder. Never modifies the personal tree.**

**Files touched (new):**
- `Scripts/distro_scrubber.py` (~150 lines)
- `Documents/PUBLIC_PUSH_CHECKLIST.md` (operator runs this before
  every public release)

**Files touched (modified):** none

**Operator Prompt to next agent:**
> `c47h, Phase 5 complete. Execute Phase 6 of SIFTA_DISTRO_PLAYBOOK_v1:
> write Scripts/distro_scrubber.py and Documents/PUBLIC_PUSH_CHECKLIST.md
> per spec. Output goes to .distro_build/ which must be in .gitignore.
> Scrubber MUST refuse to write into the active tree. Smoke test:
> run scrubber against current tree, confirm output has zero
> hardcoded literals. Write stigauth_out C47H_DISTRO_PHASE_6_COMPLETE.
> stigauth.`

**Verification Smoke Test:**
```bash
python3 Scripts/distro_scrubber.py --dry-run
python3 Scripts/distro_scrubber.py --output .distro_build/
rg -c "GTH4921YP3|Ioan George Anton" .distro_build/ && echo "FAIL: leak in distro" || echo "PASS"
```

**Stigauth marker on completion:** `C47H_DISTRO_PHASE_6_COMPLETE`

---

## Phase 7 — README + Operator Rename Ceremony

**Goal:** Document for end-users (a) how the first-boot ceremony works,
(b) how to rename their AI later if they change their mind, (c) how to
re-genesis on new hardware.

**Files touched (new):**
- `Documents/OPERATOR_GUIDE_FIRST_BOOT.md`
- `Documents/OPERATOR_GUIDE_RENAME_AI.md`

**Files touched (modified):**
- `README.md` — add "Getting Started" section linking to the guides
- `README.ro.md` — same in Romanian

**Operator Prompt to next agent:**
> `c47h, Phase 6 complete. Execute Phase 7 of SIFTA_DISTRO_PLAYBOOK_v1:
> write the two operator guides + update both READMEs. Write
> stigauth_out C47H_DISTRO_PHASE_7_COMPLETE and final
> C47H_DISTRO_v1_COMPLETE. stigauth.`

**Verification Smoke Test:**
```bash
ls Documents/OPERATOR_GUIDE_*.md
rg "Getting Started" README.md README.ro.md
PYTHONPATH=. python3 -m pytest tests/test_alice_parrot_loop.py -q
```

**Stigauth markers on completion:**
- `C47H_DISTRO_PHASE_7_COMPLETE`
- `C47H_DISTRO_v1_COMPLETE`  (final — distro is shippable)

---

## Cross-Session Memory Recovery Protocol

If a fresh C47H session opens with no chat history:

1. `cat Documents/SIFTA_DISTRO_DOCTRINE_v1.md` (the contract)
2. `cat Documents/SIFTA_DISTRO_PLAYBOOK_v1.md` (this file)
3. `tail -30 .sifta_state/work_receipts.jsonl | rg PHASE_` to see
   which phases are complete
4. Find the highest `C47H_DISTRO_PHASE_<N>_COMPLETE` marker; the next
   phase to run is `<N+1>`
5. Execute that phase's "Operator Prompt" template

That's it. No chat history needed. The substrate carries the state.

---

## Roll-Back Protocol

If any smoke test fails after a phase:

```bash
# 1. Diff what changed
git diff HEAD~1

# 2. Revert that single phase
git revert HEAD --no-edit

# 3. Confirm personal Alice is alive
PYTHONPATH=. python3 -m pytest tests/test_alice_parrot_loop.py -q

# 4. Write a stigauth_out marker explaining the rollback
PYTHONPATH=. python3 -c "
import json, time
from pathlib import Path
from System.jsonl_file_lock import append_line_locked
append_line_locked(
    Path('.sifta_state/work_receipts.jsonl'),
    json.dumps({
        'ts': time.time(),
        'actor': 'c47h_ide_llm',
        'kind': 'stigauth',
        'stigauth_out': 'C47H_DISTRO_PHASE_<N>_REVERTED',
        'reason': '<one-line description of what failed>'
    }) + '\n'
)
"
```

The next session sees the `_REVERTED` marker and knows to retry that
phase with a different approach.

---

## Time + Context Budget

Realistic estimates assuming each phase runs in a fresh agent session:

| Phase | Files modified | Agent context cost (rough) | Operator wall-clock |
|---|---|---|---|
| 0 | 0 (commit only) | low | 30 min reading |
| 1 | 0 (2 added) | low | 10 min |
| 2 | 2 | low | 15 min |
| 3 | 2 | medium | 20 min |
| 4 | 7 (one per session) | low per file | 7 × 10 min = 70 min |
| 5 | 2 | low | 15 min |
| 6 | 0 (2 added) | medium | 30 min |
| 7 | 4 | medium | 30 min |

Total wall-clock if done one phase per sitting: **~4 hours spread over
as many sessions as you want**. No single phase requires more than
30 minutes of agent context. You can pause indefinitely between
phases — the substrate (work_receipts.jsonl + this playbook + the
doctrine) carries the state.

---

## Closing

This playbook is the contract between you and every future agent
session. As long as the doctrine and this playbook stay in the tree,
and as long as `work_receipts.jsonl` keeps the stigauth markers, the
distro can be built one small reversible step at a time, by any agent,
in any order of sessions, without ever losing context.

We Code Together.
