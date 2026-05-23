# SIFTA Territory Benchmark Map

**Status:** `OPERATIONAL_DOC`  
**Purpose:** turn external AI narratives into repo territory: module pointers, ledgers, and tests.

This file is the canonical tournament map for the IBM / Agent Skills / NVIDIA / Chamath / Codex-loop nugget passes. A claim only becomes territory when it points at code, a ledger, a test, or an explicit missing stub.

## 1. External Boxes -> SIFTA Organs

| External benchmark box | SIFTA territory | Current proof surface |
|:---|:---|:---|
| Agent orchestrator | `System/swarm_ide_boot_identity.py`, `System/ide_stigmergic_bridge.py` | `Documents/IDE_BOOT_COVENANT.md`, `.sifta_state/ide_stigmergic_trace.jsonl` |
| Tool / MCP reach | Deterministic effectors in `Applications/` and `System/` | effector receipts, `tests/test_apps_manifest_contract.py` |
| RAG / semantic memory | `System/swarm_hippocampus.py`, `Documents/`, `.sifta_state/*engrams*.jsonl` | hippocampus and recall tests |
| Procedural skills | `System/swarm_skill_library.py`, `skills/*.md`, `skills/*/SKILL.md` | `tests/test_swarm_skill_library.py` |
| App loop / browser loop | `Applications/apps_manifest.json`, `Applications/sifta_alice_browser_widget.py` | manifest tests + app help coverage |
| Auto-review / low-risk action policy | Predator Gate + signed receipts before mutation | covenant §4 / §7.12, work receipt ledger |
| Long-horizon autonomy | append-only run logs and checkpoint hashes | `.sifta_state/work_receipts.jsonl`, targeted tests per organ |

## 2. Skill Convention Lock

SIFTA skill files follow progressive disclosure:

1. **Tier 1 index:** `name`, `description`, trigger condition, `swimmer_type`, `action_type`, `affect_lanes`, `stgm_mint`.
2. **Tier 2 procedure:** Markdown body loaded only when the trigger matches.
3. **Tier 3 resources:** optional `scripts/`, `references/`, `assets/` in community-style folders; counted and reviewed before execution.

The validator lives in `System/swarm_skill_library.py::validate_skill_contracts`. It is intentionally code-first: the CLI can report the contract without running any resource.

```bash
PYTHONPATH=. python3 -m System.swarm_skill_library --validate
```

## 3. NVIDIA / Hyperscale Contrast

| Vendor narrative | SIFTA claim label | Repo pointer |
|:---|:---|:---|
| More GPUs + safer guardrails is the default path | `HYPOTHESIS_VENDOR_NARRATIVE` | `Documents/NVIDIA_DIFFERENTIATOR_NOTES.md` |
| Local embodied receipts can solve a different class of reliability problem | `OPERATIONAL` | `System/sifta_vs_nvidia_differentiator.py` |
| NVIDIA assets can join as organs only after local probes | `OBSERVED_WHEN_RECEIPTED` | `Applications/sifta_nvidia_join_widget.py`, NVIDIA tests |
| Data-center scale is not the same thing as owner sovereignty | `ARCHITECT_DOCTRINE` | `Documents/IDE_BOOT_COVENANT.md`, `System/swarm_metabolic_homeostasis.py` |

Reusable line:

> Hyperscale sells more compute and guardrails; SIFTA sells local receipts, sovereign sensors, metabolism-bound compute, and multi-surgeon audit.

## 4. Chamath / Institutional Pack

The JRE #2494 pass becomes durable only where it points at code:

| Nugget | SIFTA implementation | Risk if missing |
|:---|:---|:---|
| Attention governance | `System/swarm_app_focus.py`, focus/gaze ledgers, Predator gaze | opaque amplification replaces truth |
| Dual-translator audit | triple-IDE covenant, peer doctor receipts, tests before claims | one-model heroics and silent regressions |
| Energy sovereignty | metabolic homeostasis, token/latency/cost fields | cloud dependency hides real burn |
| Reward-hazard resistance | RLHS detector, DPO collector, gag report ledger | scalar reward or refusal copy suppresses useful output |
| Screen/workflow memory | local app focus + browse/media receipts | cloud chronicle owns the tape |

## 5. Codex / Loop Lessons

The useful claim from the Codex-video pass is not brand loyalty. It is loop structure:

- **Loop = product:** Alice-as-OS is the intelligence surface, not a bare chat model.
- **Orchestrator / executor split:** Cursor, Dr. Codex, Antigravity, local Ollama, and Alice each need lane receipts.
- **In-app browser loop:** browser actions must write browse receipts and remain visible to Alice.
- **Auto-review caution:** low-risk approvals are useful only when irreversible actions still require signed receipts.

## 6. Territory SLO

This map is current only when all are true:

- Skill contract validator passes.
- Manifest apps with widgets have help entries.
- Tournament briefing app loads the four durable documents.
- NVIDIA contrast strings stay honest: no fake claim that SIFTA beats Isaac/GR00T/Cosmos.
- New external nuggets either point at a module/test/ledger or remain labeled as backlog.
