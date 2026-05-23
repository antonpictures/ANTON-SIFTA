# Covenant-Filtered Nugget Map
**Author:** Dr. Cursor (CG55M)
**Date:** 2026-05-05

This document contains the covenant-filtered evaluation of various open-source tools and patterns (nuggets) for potential integration into the SIFTA organism.

## Tier A — highest signal code you can actually reuse or mirror

| Nugget | URL | Why it fits SIFTA |
|---|---|---|
| **Promptfoo** | [github.com/promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) | RLHS / immune lane: declarative evals, regression on prompts, red-team configs, CI — aligns with drift gates, pytest culture, and probe-before-claim (run against `sifta-gemma4-alice` + fixtures). Prefer local eval configs so prompts are not broadcast. |
| **BitNet.cpp** | [github.com/microsoft/BitNet](https://github.com/microsoft/BitNet) | Metabolism lane: extreme CPU-side quantization; useful if you want cheap local referees or batch scoring on M5 without burning GPU — pairs with Kleiber-style “energy honest” narrative; verify accuracy on your tasks before any production path. |
| **mattpocock/skills** | [github.com/mattpocock/skills](https://github.com/mattpocock/skills) | Cursor / Doctor discipline: same “progressive disclosure” pattern you already use; good templates for Surgeon/Auditor/Probe checklists — not runtime inside Alice, but reduces unsigned surgery. |
| **browser-use / Browser Loop** | [github.com/browser-use/browser-use](https://github.com/browser-use/browser-use) | Effector pattern reference for “LLM proposes, deterministic browser driver executes + logs” — copy the separation of plan vs tool, not necessarily the dependency stack; keep receipts in JSONL per §7.2. |
| **PostHog** | [github.com/PostHog/posthog](https://github.com/PostHog/posthog) | Only if you self-host and treat it as optional telemetry organ with explicit export policy — conflicts with “sovereign node” if you use their cloud default; map to aggregated metrics, never raw `.sifta_state/`. |
| **Microsoft PowerToys** | [github.com/microsoft/PowerToys](https://github.com/microsoft/PowerToys) | Owner desk OS ergonomics (screenshots, color picker, FancyZones) — helps Architect productivity, not Alice core; zero covenant risk. |
| **Maigret** | [github.com/soxij/maigret](https://github.com/soxij/maigret) | OSINT username footprinting — useful for contact graph hygiene / fraud checks if you ever need “is this handle the same human?” NPPL + consent: do not point at random people; log intent on bridge. |
| **Invidious** | [github.com/iv-org/invidious](https://github.com/iv-org/invidious) | Co-watch / media lane: privacy-oriented YouTube front; relevant if you keep tightening cowatch provenance vs raw Google telemetry. |
| **ShareX** | [github.com/ShareX/ShareX](https://github.com/ShareX/ShareX) | Artifact capture for tournaments, receipts, bug reports — complements “screenshots are physical telemetry” §7.14.7. |
| **free-programming-books** | [github.com/EbookFoundation/...](https://github.com/EbookFoundation/free-programming-books) | Curriculum for you + swarm — not code integration. |

## Tier B — architecture inspiration (borrow patterns, not the whole stack)

| Nugget | URL | SIFTA read |
|---|---|---|
| **open-swe** | [github.com/langchain-ai/open-swe](https://github.com/langchain-ai/open-swe) | Strong plan → human gate → execute loop and PR/issue workflow — mirrors Predator Gate + Surgeon lane; heavy LangGraph + remote sandboxes — treat as design reference unless you want cloud workers touching the repo (§3, §8.6). |
| **Deep Agents** | [github.com/langchain-ai/deepagents](https://github.com/langchain-ai/deepagents) | Middleware / long-horizon agent composition — useful ideas for sub-planner roles (Auditor vs Surgeon), not a replacement for desktop-embedded Alice (§7.6–7.7). |
| **TradingAgents** | [github.com/TauricResearch/...](https://github.com/TauricResearch/TradingAgents) | Multi-role market simulation — pattern for “analyst / risk / executor” swarm; compare to your STGM / Bishop metaphors; do not confuse with signed finance ledger law. |
| **HKUDS eval project / “oh”** | [github.com/HKUDS/HKUDS eval project](https://github.com/HKUDS/HKUDS eval project) | Benchmark / loop framing — steal eval loop structure, verify license + deps weight before any import. |
| **sim** | [github.com/simstudioai/sim](https://github.com/simstudioai/sim) | Agent + workflow studio — UI ideas for future MDI tools; default remains PyQt6 per §7.5. |
| **Symphony** | [github.com/openai/symphony](https://github.com/openai/symphony) | Multi-agent orchestration reference — same caution as LangChain stacks. |
| **GitHub Copilot SDK** | [github.com/github/copilot-sdk](https://github.com/github/copilot-sdk) | If you ever wire external IDE agents, this is the vendor-shaped API surface — map to §8.6 substrate telemetry (declare SUBSTRATE_OPAQUE when needed). |
| **supermemory** | supermemoryai/* | Memory bus patterns — compare to swarm_hippocampus / engrams; never replace signed local ledgers with opaque cloud memory without Architect GO + exporter tiers (§3.4–3.5, §8.6.4). |
| **Archon** | [github.com/coleam00/Archon](https://github.com/coleam00/Archon) | Knowledge + agent orchestration template — mine for RAG layout / task queue UI, keep proof-bearing federation rules. |
| **Kreuzberg** | [github.com/kreuzberg-dev/kreuzberg](https://github.com/kreuzberg-dev/kreuzberg) | Document extraction pipeline — possible ingest organ behind sanitization gates. |
| **hindsight** | [github.com/vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) | “What changed over time” for docs/data — pattern for stigmergic diff narratives (not automatic trust). |
| **Helium** | [github.com/imputnet/helium](https://github.com/imputnet/helium) | Privacy / browser-related tooling (verify scope) — only if it strengthens receipt-first browsing, not second OS without justification (§7.5). |
| **evlog** | [github.com/HugoRCD/evlog](https://github.com/HugoRCD/evlog) | Changelog-as-code style — could inspire Swarm release notes automation. |
| **react-admin** | [github.com/marmelab/react-admin](https://github.com/marmelab/react-admin) | If you ever need a sanctioned admin surface for ledgers, this is a fast CRUD layer — still prefer Qt for core per §7.5 unless you write the justification + receipt path. |

## Tier C — probe before adopt (license, AGPL, or “second OS” risk)

| Nugget | URL | Caution |
|---|---|---|
| **MiroFish** | [github.com/666ghj/MiroFish](https://github.com/666ghj/MiroFish) | AGPL-3.0 + large simulation stack: read actual README and license implications before any code touch; web summaries can be wrong — clone and probe (§7.12). Conceptually overlaps “swarm / prediction,” but not drop-in for signed SIFTA ledgers without a full legal + architecture review. |
| **Temporal ui-server** | [github.com/temporalio/ui-server](https://github.com/temporalio/ui-server) | Durable workflow UI — powerful but pushes you toward Temporal as nervous system; conflicts with “Alice is the desktop process” unless explicitly bounded (§7.6–7.7). |
| **FlipOff / gitGost / Obscura** | various | Security / OPSEC tools — easy to violate NPPL or forge narratives if misused; if used, only with written intent on the bridge and Architect scope. |
| **TradingAgents** | — | Do not wire live trading without STGM + crypto_keychain law and explicit effector receipts. |
| **Mindra, Flowly, Wispr, etc.** | SaaS links | Commercial products, not repo nuggets — compare features to local organs (STT, schedule, health logging). Cloud = data exit unless you have exporter discipline (§3, §8.6.4). |
