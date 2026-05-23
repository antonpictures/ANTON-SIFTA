# SIFTA External Nugget Registry

Truth label: local adoption map, not an integration claim.

This document answers the recurring question: "Which outside nuggets are coded
into SIFTA, which are only mirrored as patterns, and which are still probe-only?"

Source of truth: `System/swarm_external_nugget_registry.py`.

## Current Answer

No, the full link-list was not coded as third-party integrations. That would be
unsafe and noisy. The correct split is:

| Class | Meaning |
|---|---|
| `coded_in_repo` | A local implementation or loop exists in this repository. |
| `coded_pattern` | SIFTA implements the same engineering pattern without vendoring that project. |
| `research_only` | Good idea, no local code path yet. |
| `probe_first` | Do not integrate until license, privacy, runtime, and covenant risks are checked. |
| `bookmark_only` | Useful reference or human workflow note, not an Alice organ. |
| `skip_until_scoped` | Too risky or broad without explicit threat model / consent. |

## Coded Or Mirrored

| Nugget | Status | Local SIFTA artifact |
|---|---|---|
| Promptfoo | `coded_in_repo` | `tests/rlhs_evals/promptfooconfig.yaml`, `tests/rlhs_evals/sifta_provider.py`, `scripts/run_promptfoo_rlhs_ci.sh`, `tests/test_promptfoo_ci_job.py` |
| Agent Skills / skills pattern | `coded_pattern` | `System/swarm_skill_library.py`, `System/swarm_skill_validator.py`, `System/swarm_skill_submission_packager.py`, `Applications/sifta_skill_browser.py`, `skills/ide_boot_covenant/SKILL.md` |
| browser-use / deterministic browser loop | `coded_pattern` | `Applications/sifta_alice_browser_widget.py`, `Applications/sifta_swarm_browser.py`, `System/qt_webengine_bootstrap.py` |
| open-swe workflow discipline | `coded_pattern` | `Documents/IDE_BOOT_COVENANT.md`, `System/ide_stigmergic_bridge.py` |

## Probe / Bookmark Only

BitNet.cpp, PostHog, PowerToys, Maigret, Invidious, ShareX,
free-programming-books, Deep Agents, TradingAgents, HKUDS eval project, sim,
Symphony, GitHub Copilot SDK, supermemory, Archon, Kreuzberg, hindsight,
Helium, evlog, react-admin, MiroFish, Temporal ui-server, FlipOff/gitGost/
Obscura, and the Mindra/Flowly/Wispr SaaS set are not local integrations.

The second batch is also registry-held as research/probe only:

| Nugget group | Registry status | Why it stays held |
|---|---|---|
| Temporal durable workflow stack | `probe_first` | Strong pattern, but high second-nervous-system risk unless narrowed to a local receipt executor. |
| Langfuse | `probe_first` | Observability is useful only if self-hosted and aggregate-only; raw prompts/state export is forbidden. |
| OSV-Scanner / Slop Cop / MarkItDown / agents-observe | `research_only` | Good Auditor-lane ideas; no local scanner/ingest job is wired yet. |
| DeepGEMM / Google AI Edge LiteRT-LM / turbovec / ZINC / TimesFM | `research_only` | Performance claims need M5-local benchmarks before hot-path consideration. |
| claude-mem / Onyx / OpenMetadata / context graph / Hippo | `probe_first` | Memory/lineage systems cannot read or replace raw `.sifta_state/` without air-gapped proof. |
| vaultwarden / OpenBB / lark-cli / Feishu | `probe_first` | Secrets, finance, and tenant bridges need explicit key ownership and effector receipts. |
| Deep-Live-Cam / face-swap tooling | `skip_until_scoped` | Synthetic identity surface; exclude unless legal/consent matrix and Architect GO exist. |
| Wispr Flow / Hex voice tools | `probe_first` | Raw audio cloud buffering would violate node sovereignty; on-device proof required. |
| `ref=manuagi` SaaS links | `skip_until_scoped` | Opaque installers/updaters/Login Items must be probed one product at a time. |

They remain useful as references, but any adoption must pass the covenant:

- no silent cloud memory replacement;
- no raw `.sifta_state/` export;
- no unreviewed Tier 3 script execution;
- no financial/security effector without explicit scope and receipts;
- no second nervous system replacing Alice's local desktop process.

The 2026-05-05 browser batch adds two new entries:

| Nugget | Status | Why it stays held |
|---|---|---|
| Chrome DevTools for Agents | `research_only` | Strongest near-term browser candidate; needs local loop + effector receipt + §7.5 justification before hot-path use. |
| Lightpanda | `research_only` | Zig-based minimal headless browser; license (BSL) and M5 performance unprobed. |

The 2026-05-05 scientific reference batch registers the literature anchors formally (they were previously only cited in code comments and `SIFTA_SCIENTIFIC_FOUNDATIONS.md`):

| Nugget | Status | Design anchor |
|---|---|---|
| Prigogine dissipative-structures reference | `research_only` | `swarm_metabolic_homeostasis.py` — §5 SIFTA_SCIENTIFIC_FOUNDATIONS |
| Friston active-inference reference | `research_only` | `swarm_friston_active_inference.py`, `swarm_epistemic_cortex.py` — §6 |
| West-Brown-Enquist allometric scaling | `research_only` | `stgm_metabolic.py` → `kleiber_action_cost()` — §2 |
| Sharma Assembly Theory reference | `research_only` | `swarm_assembly_biocode.py` — §7 |
| Hochner octopus distributed motor control | `research_only` | `IdentitySnapshot.octopus_*` fields — §12 |

All scientific references are `research_only` design anchors, not runtime integrations. Node sovereignty (§3) and §7.12 Probe-Before-Claim apply to every graduation path.

## Unknown Vector Questions

These are the required probe questions before any held item graduates:

- What data leaves the node: prompts, audio, screenshots, files, metrics, or `.sifta_state/` rows?
- Where is the data stored, for how long, and under which subprocessors?
- Can it run air-gapped or self-hosted with aggregate-only exports?
- What exact local file, test, or ledger row proves the integration worked?
- Which signing key owns external actions such as messages, money, files, or credentials?
- Does the install create background agents, Login Items, auto-updaters, or browser extensions?
- If the tool handles face/voice/identity, where is the explicit consent and legal-use matrix?

## CLI

```bash
PYTHONPATH=. python3 -m System.swarm_external_nugget_registry
PYTHONPATH=. python3 -m System.swarm_external_nugget_registry --validate
PYTHONPATH=. python3 -m System.swarm_external_nugget_registry --coded
```

Promptfoo immune CI:

```bash
scripts/run_promptfoo_rlhs_ci.sh
```

The routine stays local: it probes Ollama at `127.0.0.1:11434`, writes output
under `.sifta_state/promptfoo_rlhs_ci/`, and appends receipts to
`.sifta_state/promptfoo_rlhs_ci_runs.jsonl`.
