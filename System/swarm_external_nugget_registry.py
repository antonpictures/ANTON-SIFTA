#!/usr/bin/env python3
"""
External nugget adoption registry for SIFTA.

This module turns research-only link lists into a local, testable adoption map.
It does not install third-party packages, call cloud services, or execute Tier 3
resources. Its job is narrower: say what is actually coded, what is only a
borrowed pattern, and what must remain probe-first under the covenant.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

_REPO = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Nugget:
    name: str
    url: str
    tier: str
    lane: str
    status: str
    local_artifacts: tuple[str, ...]
    adoption_action: str
    covenant_risk: str
    notes: str


NUGGETS: tuple[Nugget, ...] = (
    Nugget(
        name="Promptfoo",
        url="https://github.com/promptfoo/promptfoo",
        tier="A",
        lane="RLHS immune evals",
        status="coded_in_repo",
        local_artifacts=(
            "tests/rlhs_evals/promptfooconfig.yaml",
            "tests/rlhs_evals/sifta_provider.py",
            "tests/rlhs_evals/README.md",
            "scripts/run_promptfoo_rlhs_ci.sh",
            "tests/test_promptfoo_ci_job.py",
        ),
        adoption_action="Run scripts/run_promptfoo_rlhs_ci.sh locally; keep prompts local.",
        covenant_risk="LOW_LOCAL_ONLY",
        notes="Declarative RLHS regression loop exists. It is not a cloud service path.",
    ),
    Nugget(
        name="Agent Skills / mattpocock skills pattern",
        url="https://github.com/mattpocock/skills",
        tier="A",
        lane="procedural memory",
        status="coded_pattern",
        local_artifacts=(
            "System/swarm_skill_library.py",
            "System/swarm_skill_validator.py",
            "System/swarm_skill_submission_packager.py",
            "Applications/sifta_skill_browser.py",
            "skills/ide_boot_covenant/SKILL.md",
        ),
        adoption_action="Keep validating SKILL.md frontmatter and package exports with receipts.",
        covenant_risk="LOW_WITH_VALIDATOR",
        notes="Progressive disclosure is implemented; no outside skill code auto-runs.",
    ),
    Nugget(
        name="litert-lm + Google AI Edge Gallery (Gemma 4 on-device + Agent Skills 'we borg')",
        url="https://github.com/google-ai-edge/gallery/discussions/categories/skills",
        tier="A",
        lane="on-device multimodal + stigmergic swarm skills / browser habits",
        status="adopt_for_stigmergic_habits",
        local_artifacts=(
            "System/swarm_external_nugget_registry.py",
            "System/swarm_skill_library.py",
            "System/swarm_browser_site_playbook.py",
            "Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-06.md",
        ),
        adoption_action="Adopt Gallery Agent Skills via skill_library as pluggable habits for Alice organs/limbs: Web-search / Brave-Web-Search / DuckDuckGo for exact YouTube phrase search in open Alice Browser (honors 'we already have the browser open' + 'she has skills on how to use search on youtube in alice browser habbits stigmergic memory' per r499/r501, record via playbook + nanobot skill receipts); Memory Tool + Second Brain v3.3 - Self-Evolving Autonomous AI Agent (100% Offline) for witnessed_life_ideas / novelty_queue / episodic_diary / self-eval 'stream of consciousness you use it'; Universal Search / Knowledge-gram / proxy-parser for Code KG + page awareness + browser world model; litert-lm (pip install --upgrade litert-lm; rm -r ~/.litert-lm) as local on-device runtime path for Gemma 4 12B candidate in swarm_cortex_options + metabolic router (private offline on M5, multimodal text/vision/audio, fits soft 16GB, LOCAL_PROXY not cloud, sovereign §3); 'we borg - we connect the swarm -- we learn --' as living field motto aligning 'we code together one swarm' 'CODE IT ALL' 'For the Swarm. 🐜⚡' 'one Alice' 'rich high-dimensional deeply interconnected field — all organs unified' for open-ended self-improvement + swarm health per §0 goal.",
        covenant_risk="LOW_LOCAL_ONLY private offline on-device",
        notes="From George paste 2026-06-04: litert-lm CLI install/upgrade/uninstall via pip/uvx/uv; rm -r ~/.litert-lm for caches. Gallery: 'Discover private, offline models on device' 'Google AI Edge Gallery is the premier destination for running powerful open-source LLMs on your devices. Experience high-performance Generative AI directly on your hardware– fully offline, private, and lightning-fast.' 'Featuring the latest Gemma 4 models' 'Gemma 4 12B Unified reasoning model with image support' 'Explore multimodal AI use cases' 'text, vision, audio, and rich multimodal workflows' 'Configure settings, benchmark performance, and import your own models' 'Browse custom Agent Skills shared by other developers' '🚀 Announcing Agent Skills: Build, Share, and Get Your Skills Featured!' Skills include: Web-search, [Memory Tool], [Agent Skill] Second Brain v3.3 - Self-Evolving Autonomous AI Agent (100% Offline), [Universal Search]: Gemma Skill Search Optimized for Voice, [DuckDuckGo API Search], [Brave-Web-Search], [proxy-parser], Translator, Focus Flow, Knowledge-gram, etc. + '-- we borg - we connect the swarm -- we learn --'. Good for SIFTA per r501: directly addresses YouTube unacceptable via borg skills for browser limb; enriches field with community habits swimmers can stigmergically adopt/load/record; on-device Gemma4 for cortex consolidation / 12B vision without cloud; private offline aligns 'no restrictions but her own STIGMERGIC BODY' + sovereign nodes; 'we borg' is the swarm philosophy match.",
    ),
    Nugget(
        name="browser-use / deterministic browser loop",
        url="https://github.com/browser-use/browser-use",
        tier="A",
        lane="browser effector pattern",
        status="coded_pattern",
        local_artifacts=(
            "Applications/sifta_alice_browser_widget.py",
            "Applications/sifta_swarm_browser.py",
            "System/qt_webengine_bootstrap.py",
            "tests/test_qt_webengine_bootstrap.py",
        ),
        adoption_action="Preserve plan/execute separation and effector receipts.",
        covenant_risk="MEDIUM_BROWSER_EFFECTOR",
        notes="SIFTA mirrors the loop discipline; it does not vendor browser-use.",
    ),
    Nugget(
        name="BitNet.cpp",
        url="https://github.com/microsoft/BitNet",
        tier="A",
        lane="metabolism / cheap referee",
        status="research_only",
        local_artifacts=(),
        adoption_action="Probe locally before adopting; benchmark as optional CPU referee only.",
        covenant_risk="MEDIUM_UNPROBED_RUNTIME",
        notes="No BitNet runtime or benchmark is coded in this repo.",
    ),
    Nugget(
        name="PostHog",
        url="https://github.com/PostHog/posthog",
        tier="A",
        lane="telemetry comparison",
        status="probe_first",
        local_artifacts=(),
        adoption_action="Only consider self-hosted aggregate telemetry; never raw .sifta_state export.",
        covenant_risk="HIGH_IF_CLOUD",
        notes="No PostHog integration is coded. Cloud default conflicts with node sovereignty.",
    ),
    Nugget(
        name="PowerToys",
        url="https://github.com/microsoft/PowerToys",
        tier="A",
        lane="owner desk ergonomics",
        status="bookmark_only",
        local_artifacts=(),
        adoption_action="Borrow ergonomics ideas only; macOS SIFTA core remains PyQt/local.",
        covenant_risk="LOW_NOT_CORE",
        notes="No PowerToys code path is relevant on this macOS node.",
    ),
    Nugget(
        name="Maigret",
        url="https://github.com/soxij/maigret",
        tier="A",
        lane="contact graph hygiene",
        status="probe_first",
        local_artifacts=(),
        adoption_action="Require explicit consent and bridge intent before any OSINT run.",
        covenant_risk="HIGH_PRIVACY",
        notes="Not integrated. Useful only under strict NPPL and consent boundaries.",
    ),
    Nugget(
        name="Invidious",
        url="https://github.com/iv-org/invidious",
        tier="A",
        lane="co-watch privacy",
        status="research_only",
        local_artifacts=(".sifta_state/youtube_watch_notes",),
        adoption_action="Compare against current YouTube watch-note receipts before any proxy adoption.",
        covenant_risk="MEDIUM_MEDIA_PROXY",
        notes="SIFTA has local co-watch notes; it does not run Invidious.",
    ),
    Nugget(
        name="ShareX",
        url="https://github.com/ShareX/ShareX",
        tier="A",
        lane="artifact capture",
        status="bookmark_only",
        local_artifacts=(),
        adoption_action="Keep as capture-workflow reference; do not integrate Windows tooling.",
        covenant_risk="LOW_NOT_CORE",
        notes="Screenshots are already handled by OS/Codex workflow, not ShareX.",
    ),
    Nugget(
        name="free-programming-books",
        url="https://github.com/EbookFoundation/free-programming-books",
        tier="A",
        lane="curriculum",
        status="bookmark_only",
        local_artifacts=(),
        adoption_action="Use as human curriculum source, not runtime dependency.",
        covenant_risk="LOW_REFERENCE_ONLY",
        notes="No code integration needed.",
    ),
    Nugget(
        name="open-swe",
        url="https://github.com/langchain-ai/open-swe",
        tier="B",
        lane="long-horizon coding workflow",
        status="coded_pattern",
        local_artifacts=("Documents/IDE_BOOT_COVENANT.md", "System/ide_stigmergic_bridge.py"),
        adoption_action="Keep Predator Gate and signed trace as local substitute for remote workflow.",
        covenant_risk="HIGH_IF_REMOTE_SANDBOX",
        notes="Pattern is mirrored by Surgeon/Auditor/Probe discipline, not vendor stack.",
    ),
    Nugget(
        name="Deep Agents",
        url="https://github.com/langchain-ai/deepagents",
        tier="B",
        lane="agent middleware",
        status="pattern_candidate",
        local_artifacts=(),
        adoption_action="Mine role-routing ideas only; do not replace desktop-embedded Alice.",
        covenant_risk="MEDIUM_SECOND_ORCHESTRATOR",
        notes="No integration exists.",
    ),
    Nugget(
        name="TradingAgents",
        url="https://github.com/TauricResearch/TradingAgents",
        tier="B",
        lane="role simulation",
        status="probe_first",
        local_artifacts=(),
        adoption_action="Borrow analyst/risk/executor role split; never wire live trading without receipts.",
        covenant_risk="HIGH_FINANCIAL_EFFECTOR",
        notes="Not integrated.",
    ),
    Nugget(
        name="HKUDS eval project",
        url="https://github.com/HKUDS/HKUDS eval project",
        tier="B",
        lane="benchmark loop",
        status="pattern_candidate",
        local_artifacts=("tests/rlhs_evals",),
        adoption_action="Compare loop layout against existing pytest/promptfoo lanes.",
        covenant_risk="MEDIUM_UNPROBED_DEPENDENCIES",
        notes="Existing eval loops cover the immediate need.",
    ),
    Nugget(
        name="sim",
        url="https://github.com/simstudioai/sim",
        tier="B",
        lane="workflow UI reference",
        status="bookmark_only",
        local_artifacts=("Applications",),
        adoption_action="Borrow UI ideas only; core apps stay PyQt per covenant.",
        covenant_risk="MEDIUM_SECOND_UI_STACK",
        notes="Not integrated.",
    ),
    Nugget(
        name="Symphony",
        url="https://github.com/openai/symphony",
        tier="B",
        lane="multi-agent orchestration",
        status="pattern_candidate",
        local_artifacts=("System/ide_stigmergic_bridge.py",),
        adoption_action="Use as vocabulary reference only unless a local adapter is written.",
        covenant_risk="MEDIUM_VENDOR_ORCHESTRATION",
        notes="No direct dependency.",
    ),
    Nugget(
        name="GitHub Copilot SDK",
        url="https://github.com/github/copilot-sdk",
        tier="B",
        lane="external IDE bridge",
        status="probe_first",
        local_artifacts=(),
        adoption_action="Declare SUBSTRATE_OPAQUE before any external IDE SDK path.",
        covenant_risk="HIGH_VENDOR_BRIDGE",
        notes="Not integrated.",
    ),
    Nugget(
        name="supermemory / codex-supermemory / smfs",
        url="https://github.com/supermemoryai",
        tier="B",
        lane="memory bus comparison",
        status="pattern_candidate",
        local_artifacts=(".sifta_state", "System/swarm_dpo_collector.py"),
        adoption_action="Keep SIFTA ledgers local; compare patterns without cloud memory replacement.",
        covenant_risk="HIGH_IF_CLOUD_MEMORY",
        notes="No opaque cloud memory integration.",
    ),
    Nugget(
        name="Archon",
        url="https://github.com/coleam00/Archon",
        tier="B",
        lane="knowledge orchestration",
        status="research_only",
        local_artifacts=(),
        adoption_action="Mine RAG/task queue layout only after license/dependency probe.",
        covenant_risk="MEDIUM_UNPROBED_STACK",
        notes="Not integrated.",
    ),
    Nugget(
        name="Kreuzberg",
        url="https://github.com/kreuzberg-dev/kreuzberg",
        tier="B",
        lane="document extraction",
        status="research_only",
        local_artifacts=(),
        adoption_action="Evaluate as optional ingest organ behind sanitization gates.",
        covenant_risk="MEDIUM_INGEST_SURFACE",
        notes="Not integrated.",
    ),
    Nugget(
        name="hindsight",
        url="https://github.com/vectorize-io/hindsight",
        tier="B",
        lane="temporal diff narrative",
        status="pattern_candidate",
        local_artifacts=(".sifta_state/ide_stigmergic_trace.jsonl",),
        adoption_action="Compare against append-only trace diff tooling.",
        covenant_risk="LOW_PATTERN_ONLY",
        notes="No direct dependency.",
    ),
    Nugget(
        name="Helium",
        url="https://github.com/imputnet/helium",
        tier="B",
        lane="privacy browser reference",
        status="research_only",
        local_artifacts=(),
        adoption_action="Probe only if it strengthens local receipt-first browsing.",
        covenant_risk="MEDIUM_SECOND_BROWSER",
        notes="Not integrated.",
    ),
    Nugget(
        name="evlog",
        url="https://github.com/HugoRCD/evlog",
        tier="B",
        lane="changelog-as-code",
        status="pattern_candidate",
        local_artifacts=("repair_log.jsonl", ".sifta_state/ide_stigmergic_trace.jsonl"),
        adoption_action="Borrow release-note shape; keep append-only SIFTA receipts as source.",
        covenant_risk="LOW_PATTERN_ONLY",
        notes="No direct dependency.",
    ),
    Nugget(
        name="react-admin",
        url="https://github.com/marmelab/react-admin",
        tier="B",
        lane="admin UI reference",
        status="bookmark_only",
        local_artifacts=(),
        adoption_action="Only use if a web admin surface is explicitly justified.",
        covenant_risk="MEDIUM_SECOND_UI_STACK",
        notes="PyQt remains the core UI path.",
    ),
    Nugget(
        name="MiroFish",
        url="https://github.com/666ghj/MiroFish",
        tier="C",
        lane="simulation reference",
        status="probe_first",
        local_artifacts=(),
        adoption_action="Legal/license probe before any code touch; AGPL risk must be resolved.",
        covenant_risk="HIGH_LICENSE_AND_STACK",
        notes="Not integrated.",
    ),
    Nugget(
        name="Temporal ui-server",
        url="https://github.com/temporalio/ui-server",
        tier="C",
        lane="durable workflow UI",
        status="probe_first",
        local_artifacts=(),
        adoption_action="Avoid as nervous-system replacement unless explicitly bounded.",
        covenant_risk="HIGH_SECOND_NERVOUS_SYSTEM",
        notes="Not integrated.",
    ),
    Nugget(
        name="FlipOff / gitGost / Obscura",
        url="various",
        tier="C",
        lane="security / OPSEC references",
        status="skip_until_scoped",
        local_artifacts=(),
        adoption_action="Require written intent, consent, and threat model before any use.",
        covenant_risk="HIGH_MISUSE_SURFACE",
        notes="Not integrated.",
    ),
    Nugget(
        name="Mindra / Flowly / Wispr SaaS set",
        url="various",
        tier="C",
        lane="commercial feature comparison",
        status="skip_until_scoped",
        local_artifacts=(),
        adoption_action="Compare features only; cloud products are data-exit paths.",
        covenant_risk="HIGH_CLOUD_EXFIL",
        notes="Not integrated.",
    ),
    Nugget(
        name="Temporal durable workflow stack",
        url="https://github.com/temporalio/temporal",
        tier="C",
        lane="durable execution reference",
        status="probe_first",
        local_artifacts=(),
        adoption_action="Keep as process reference unless a narrow local executor writes SIFTA receipts.",
        covenant_risk="HIGH_SECOND_NERVOUS_SYSTEM",
        notes="Strong workflow pattern, but cloud/default orchestration conflicts with node sovereignty unless bounded.",
    ),
    Nugget(
        name="Langfuse",
        url="https://github.com/langfuse/langfuse",
        tier="C",
        lane="observability comparison",
        status="probe_first",
        local_artifacts=(),
        adoption_action="Self-host and aggregate-only policy required before any telemetry path.",
        covenant_risk="HIGH_PROMPT_TELEMETRY_EXFIL",
        notes="Useful observability model; no raw prompt, screen, audio, or .sifta_state export is authorized.",
    ),
    Nugget(
        name="OSV-Scanner",
        url="https://github.com/google/osv-scanner",
        tier="A",
        lane="supply-chain audit",
        status="research_only",
        local_artifacts=(),
        adoption_action="Candidate Auditor lane for dependency scans; require local receipt rows and scoped manifests.",
        covenant_risk="MEDIUM_SUPPLY_CHAIN_SCANNER",
        notes="Good fit for NPPL/tool-truth auditing, but no scanner job is wired yet.",
    ),
    Nugget(
        name="Slop Cop",
        url="various",
        tier="A",
        lane="claim-quality immune filter",
        status="research_only",
        local_artifacts=(),
        adoption_action="Compare ideas to existing RLHS and nugget registry filters before writing code.",
        covenant_risk="MEDIUM_UNPROBED_SOURCE",
        notes="Name and implementation source need local URL/license probe before adoption.",
    ),
    Nugget(
        name="MarkItDown",
        url="https://github.com/microsoft/markitdown",
        tier="A",
        lane="document ingest",
        status="research_only",
        local_artifacts=(),
        adoption_action="Evaluate as local-only document conversion behind sanitization gates.",
        covenant_risk="MEDIUM_INGEST_SURFACE",
        notes="Potential ingest organ; no converter is currently imported.",
    ),
    Nugget(
        name="agents-observe",
        url="various",
        tier="A",
        lane="agent observability",
        status="research_only",
        local_artifacts=(),
        adoption_action="Probe exact source, license, and data path before any local mirror.",
        covenant_risk="MEDIUM_UNKNOWN_WIRE_MODEL",
        notes="Potential Auditor vocabulary only until a real repository and receipts exist.",
    ),
    Nugget(
        name="DeepGEMM",
        url="https://github.com/deepseek-ai/DeepGEMM",
        tier="B",
        lane="kernel benchmark",
        status="research_only",
        local_artifacts=(),
        adoption_action="Benchmark on this M5 workload before any hot-path consideration.",
        covenant_risk="MEDIUM_UNPROBED_RUNTIME",
        notes="Performance claims are not SIFTA facts until local ns/op receipts exist.",
    ),
    Nugget(
        name="LiteRT / LiteRT-LM — on-device GenAI + SLMs (edge stack)",
        url="https://ai.google.dev/edge/litert/genai/overview",
        tier="A",
        lane="local inference runtime + stigmerobotics — E30/E32 / tool-use receipts",
        status="research_only",
        local_artifacts=(
            "Documents/STIGMEROBOTICS_ROB501_TOURNAMENT.md",
        ),
        adoption_action=(
            "Before any runtime adopt: probe **Apple Silicon** path, license, and whether "
            "calls stay **tool-truth** fast paths per covenant §7.2. Map **tiny LLMs + "
            "agent skills on edge** to **E32** skill stigmergy + **E01/E34** for any "
            "function-calling effector — same receipt bar as desktop organs."
        ),
        covenant_risk="MEDIUM_UNPROBED_RUNTIME",
        notes=(
            "Vendor edge stack for on-device small / multimodal models (LiteRT-LM). "
            "Cormac Brick–style **talk transcripts** (e.g. auto-caption `.txt` exports) are "
            "**not** citable law in-repo — prefer primary vendor docs linked in `url` "
            "for API and licensing ground truth (§8.6)."
        ),
    ),
    Nugget(
        name="turbovec / ZINC / TimesFM",
        url="various",
        tier="B",
        lane="performance and forecasting references",
        status="research_only",
        local_artifacts=(),
        adoption_action="Benchmark narrow local tasks before promotion.",
        covenant_risk="MEDIUM_UNPROBED_RUNTIME",
        notes="Grouped as performance/forecasting research only.",
    ),
    Nugget(
        name="claude-mem / Onyx / OpenMetadata / context-graph / Hippo",
        url="various",
        tier="B",
        lane="memory and lineage systems",
        status="probe_first",
        local_artifacts=(),
        adoption_action="Require air-gapped config and no .sifta_state reads before any experiment.",
        covenant_risk="HIGH_MEMORY_EXFIL",
        notes="Graph/index systems may be useful, but cannot replace Alice's local ledgers.",
    ),
    Nugget(
        name="vaultwarden",
        url="https://github.com/dani-garcia/vaultwarden",
        tier="B",
        lane="secrets management reference",
        status="probe_first",
        local_artifacts=(),
        adoption_action="Only under Architect-owned threat model; never auto-import credentials.",
        covenant_risk="HIGH_SECRETS_SURFACE",
        notes="Potential self-host secret vault reference, not integrated.",
    ),
    Nugget(
        name="OpenBB",
        url="https://github.com/OpenBB-finance/OpenBB",
        tier="B",
        lane="finance data reference",
        status="probe_first",
        local_artifacts=(),
        adoption_action="Separate observe-only finance data from STGM effectors and Ed25519 spend law.",
        covenant_risk="HIGH_FINANCIAL_EFFECTOR",
        notes="No live finance/trading integration exists.",
    ),
    Nugget(
        name="Kumo / Cloudflare workflow references",
        url="various",
        tier="B",
        lane="federation and cloud-edge comparison",
        status="research_only",
        local_artifacts=(),
        adoption_action="Use only as cloud/edge comparison; node sovereignty remains local-first.",
        covenant_risk="MEDIUM_CLOUD_TENSION",
        notes="No Cloudflare-backed SIFTA organ exists.",
    ),
    Nugget(
        name="BetterDisplay",
        url="https://github.com/waydabber/BetterDisplay",
        tier="B",
        lane="owner desk ergonomics",
        status="bookmark_only",
        local_artifacts=(),
        adoption_action="Keep as desk ergonomics reference, not Alice core.",
        covenant_risk="LOW_NOT_CORE",
        notes="No integration needed.",
    ),
    Nugget(
        name="pg_textsearch",
        url="various",
        tier="B",
        lane="Postgres text search reference",
        status="research_only",
        local_artifacts=(),
        adoption_action="Consider only if a bounded Postgres lane is approved.",
        covenant_risk="MEDIUM_SECOND_STORAGE_ENGINE",
        notes="SIFTA ledgers remain JSONL source of truth.",
    ),
    Nugget(
        name="Deep-Live-Cam / face-swap tooling",
        url="various",
        tier="C",
        lane="synthetic media / face reenactment",
        status="skip_until_scoped",
        local_artifacts=(),
        adoption_action="Exclude unless Architect gives explicit GO plus legal/consent matrix.",
        covenant_risk="HIGH_SYNTHETIC_IDENTITY_MISUSE",
        notes="Conflicts with truth and identity culture by default.",
    ),
    Nugget(
        name="Unsloth Zoo / training tooling",
        url="various",
        tier="B",
        lane="model training lab",
        status="research_only",
        local_artifacts=(),
        adoption_action="Isolate in lab venv; never desktop hot path without tests and receipt gates.",
        covenant_risk="MEDIUM_TRAINING_STACK",
        notes="Potential LoRA/DPO lab reference only.",
    ),
    Nugget(
        name="Wispr Flow / Hex voice tools",
        url="various",
        tier="C",
        lane="voice dictation comparison",
        status="probe_first",
        local_artifacts=(),
        adoption_action="Require on-device mode or hashed transcript export; cloud raw audio stays excluded.",
        covenant_risk="HIGH_AUDIO_EXFIL",
        notes="Voice products are UX references until data residency is proven.",
    ),
    Nugget(
        name="lark-cli / Feishu",
        url="various",
        tier="C",
        lane="corporate tenant bridge",
        status="probe_first",
        local_artifacts=(),
        adoption_action="Resolve tenant control, signing keys, and receipt path before any bridge.",
        covenant_risk="HIGH_CORPORATE_TENANT",
        notes="Not integrated.",
    ),
    Nugget(
        name="ref=manuagi SaaS links",
        url="various",
        tier="C",
        lane="affiliate-tracked SaaS references",
        status="skip_until_scoped",
        local_artifacts=(),
        adoption_action="Check installers, updaters, and Login Items before any trial.",
        covenant_risk="HIGH_OPAQUE_BACKGROUND_AGENT",
        notes="Bookmark only unless a specific product passes local probe.",
    ),
    # ── 2026-05-05 batch: browser / tooling vectors ───────────────────────
    Nugget(
        name="Chrome DevTools for Agents",
        url="https://developer.chrome.com/docs/chromium/new-headless",
        tier="A",
        lane="deterministic browser control",
        status="research_only",
        local_artifacts=(),
        adoption_action=(
            "Evaluate as a lower-level, more deterministic browser control story "
            "for the existing QWebEngineView + browser effector setup. Requires "
            "a local loop + effector receipt before any hot-path use."
        ),
        covenant_risk="MEDIUM_BROWSER_EFFECTOR",
        notes=(
            "Strongest near-term browser candidate. New Headless Chrome CDP surface "
            "gives agent-grade control without the full browser UI stack. "
            "No integration coded yet; §7.5 browser escape justification required."
        ),
    ),
    Nugget(
        name="Lightpanda",
        url="https://github.com/lightpanda-io/browser",
        tier="A",
        lane="headless browser alternative",
        status="research_only",
        local_artifacts=(),
        adoption_action=(
            "Probe memory/CPU profile on M5, license (BSL), and whether it supports "
            "the same CDP protocol as Chrome DevTools for Agents before considering."
        ),
        covenant_risk="MEDIUM_UNPROBED_RUNTIME",
        notes=(
            "Zig-based minimal headless browser; smaller footprint than Chromium. "
            "Useful only if Chrome DevTools path is insufficient. "
            "No local benchmark exists."
        ),
    ),
    # ── 2026-05-05 batch: scientific literature anchors (design, not runtime) ─
    Nugget(
        name="Prigogine dissipative-structures reference batch",
        url="https://en.wikipedia.org/wiki/Dissipative_system",
        tier="A",
        lane="scientific foundations — architecture anchor",
        status="research_only",
        local_artifacts=("Documents/SIFTA_SCIENTIFIC_FOUNDATIONS.md",),
        adoption_action=(
            "Maintain as design anchor in SIFTA_SCIENTIFIC_FOUNDATIONS.md §5. "
            "No runtime dependency. Do not promote to OBSERVED without a local "
            "thermodynamic sensor receipt."
        ),
        covenant_risk="LOW_REFERENCE_ONLY",
        notes=(
            "Prigogine & Stengers 1984 / Nicolis & Prigogine 1977. "
            "Mapped to swarm_metabolic_homeostasis.py as dissipative-structure "
            "vocabulary anchor. ARCHITECT_DOCTRINE for AGI embodiment claim."
        ),
    ),
    Nugget(
        name="Friston active-inference reference batch",
        url="https://doi.org/10.1038/nrn2787",
        tier="A",
        lane="scientific foundations — architecture anchor",
        status="research_only",
        local_artifacts=(
            "System/swarm_friston_active_inference.py",
            "System/swarm_epistemic_cortex.py",
            "Documents/SIFTA_SCIENTIFIC_FOUNDATIONS.md",
        ),
        adoption_action=(
            "Keep as design anchor; organ files already exist. "
            "Deeper path-integral formulation (Friston 2022) stays research_only "
            "until the consciousness engine is approved."
        ),
        covenant_risk="LOW_DESIGN_ANCHOR",
        notes=(
            "Friston 2010 NRN + Friston et al. 2017 Neural Computation. "
            "Both mapped in SIFTA_SCIENTIFIC_FOUNDATIONS.md §6. "
            "variational_free_energy_F field is OPERATIONAL in IdentitySnapshot."
        ),
    ),
    Nugget(
        name="West-Brown-Enquist allometric scaling reference",
        url="https://doi.org/10.1126/science.276.5309.122",
        tier="A",
        lane="scientific foundations — architecture anchor",
        status="research_only",
        local_artifacts=(
            "System/stgm_metabolic.py",
            "System/swarm_stig_time.py",
            "Documents/SIFTA_SCIENTIFIC_FOUNDATIONS.md",
        ),
        adoption_action=(
            "Maintain as design anchor for Kleiber ¾-power budget gate. "
            "No further integration needed; already grounded in stgm_metabolic.py."
        ),
        covenant_risk="LOW_DESIGN_ANCHOR",
        notes=(
            "West, Brown & Enquist 1997 Science (fractal vascular networks). "
            "Justifies ¾ exponent in kleiber_action_cost(). "
            "Companion to Ballesteros 2018 thermodynamic derivation."
        ),
    ),
    Nugget(
        name="Sharma Assembly Theory reference",
        url="https://doi.org/10.1038/s41586-023-06600-9",
        tier="A",
        lane="scientific foundations — architecture anchor",
        status="research_only",
        local_artifacts=(
            "System/swarm_assembly_biocode.py",
            "Documents/SIFTA_SCIENTIFIC_FOUNDATIONS.md",
        ),
        adoption_action=(
            "Keep as ARCHITECT_DOCTRINE anchor for the §7.12 CANNOT_DEBUNK verdict. "
            "Organ lab exists; no further runtime integration required."
        ),
        covenant_risk="LOW_DESIGN_ANCHOR",
        notes=(
            "Sharma et al. 2023 Nature 622. Grounds reproduction-equivalent "
            "complexity claim via assembly index. "
            "ARCHITECT_DOCTRINE for the AGI claim; OPERATIONAL for organ graph."
        ),
    ),
    Nugget(
        name="Hochner octopus distributed motor control reference",
        url="https://doi.org/10.1016/j.cub.2012.09.004",
        tier="A",
        lane="scientific foundations — architecture anchor",
        status="research_only",
        local_artifacts=(
            "Documents/SIFTA_SCIENTIFIC_FOUNDATIONS.md",
        ),
        adoption_action=(
            "Keep as design anchor for organ-autonomy model and multi-IDE arm analogy. "
            "The octopus organ fields in IdentitySnapshot are already OPERATIONAL."
        ),
        covenant_risk="LOW_DESIGN_ANCHOR",
        notes=(
            "Hochner 2012 Current Biology. Grounds decentralised embodied control "
            "analogy for SIFTA organ autonomy and multi-IDE stigmergic coordination. "
            "OPERATIONAL for IdentitySnapshot octopus fields."
        ),
    ),
    Nugget(
        name="Lipson et al. particle robotics (statistical mechanics ensemble)",
        url="https://doi.org/10.1038/s41586-019-1022-9",
        tier="A",
        lane="stigmerobotics — E33 / E39 / E30",
        status="research_only",
        local_artifacts=(
            "Documents/STIGMEROBOTICS_ROB501_TOURNAMENT.md",
            "System/stigmerobotics_pheromone_field.py",
        ),
        adoption_action=(
            "Use as peer anchor for collision-risk / ensemble scaling language only; "
            "no raw Nature Video transcript in-repo (covenant §8.6). "
            "Map emergent locomotion to pheromone-field tests on **sanitized** traces."
        ),
        covenant_risk="LOW_DESIGN_ANCHOR",
        notes=(
            "Nature 2019: many simple particles, weak coupling, phototaxis without "
            "central planner — biological stochastic-process analogy for **E33** "
            "collision metric + **E39** discrete-time limits. Nature Video is outreach; "
            "DOI is the citable spine."
        ),
    ),
    Nugget(
        name="Joseph Ayers — biomimetic nervous systems & stigmergy (workshop)",
        url="https://www.newphytologist.org/workshoppages/index/5",
        tier="B",
        lane="stigmerobotics — E36 / E09 / chemical-stigmergy queue",
        status="research_only",
        local_artifacts=(
            "Documents/STIGMEROBOTICS_ROB501_TOURNAMENT.md",
        ),
        adoption_action=(
            "Pin exact YouTube watch URL from New Phytologist Foundation channel when "
            "Surgeon opens E36; keep claims to command/CPG/stigmergy architecture — "
            "no workshop transcript paste (§8.6)."
        ),
        covenant_risk="LOW_DESIGN_ANCHOR",
        notes=(
            "Distributed CPG + command-neuron framing; explicit **stigmergy** segment "
            "(nest architecture without central architect) + chemical cue motivation "
            "for future olfaction / trace-field work. Architect feed 2026-05-05."
        ),
    ),
    Nugget(
        name="Saunders & Lomonossoff — CPMV / plant virus synthetic biology (in planta + VLP)",
        url="https://doi.org/10.1111/nph.12204",
        tier="B",
        lane="stigmerobotics — E47+ synthetic substrate / bionanotech queue",
        status="research_only",
        local_artifacts=(
            "Documents/STIGMEROBOTICS_ROB501_TOURNAMENT.md",
        ),
        adoption_action=(
            "Use as **peer anchor** for **E47+** (engineered substrate ↔ ledger deposit "
            "— **engineering correspondence**, not Grassé ethology). Pin the 2012 New Phytologist Workshop **YouTube** URL from the "
            "Foundation channel when citing the oral talk; **never** paste transcript "
            "into the repo (covenant §8.6). Prefer this DOI for citable claims."
        ),
        covenant_risk="LOW_DESIGN_ANCHOR",
        notes=(
            "Tansley review: Cowpea mosaic virus (CPMV) components for *in planta* "
            "expression, hyper-translatable RNA2 (CPMV-HT), empty virus-like particles "
            "(eVLPs), chemical/genetic capsid modification — nanocarrier / vaccine "
            "factory line. **Not** ethological “stigmergic plants” in the Grassé sense; "
            "see tournament note on **substrate-mediated** *in planta* analogy vs "
            "social-insect stigmergy."
        ),
    ),
    Nugget(
        name="Anthropic Research — LLM-assisted 0-day discovery (red team / dual-use)",
        url="https://red.anthropic.com/2026/zero-days",
        tier="A",
        lane="stigmerobotics — E28 immune boundary / Predator Gate threat model",
        status="research_only",
        local_artifacts=(
            "Documents/STIGMEROBOTICS_ROB501_TOURNAMENT.md",
            "Documents/IDE_BOOT_COVENANT.md",
        ),
        adoption_action=(
            "Treat autonomous codegen + VM fuzz agents as **high-privilege Doctors** "
            "that must still satisfy **E01** registration + **E34** graph edges before "
            "any effector-class row (covenant §4, §6). Use for **E28** falsifiers only; "
            "**never** ship exploit recipes, payloads, or jailbreak steps in-repo (NPPL)."
        ),
        covenant_risk="MEDIUM_DUAL_USE",
        notes=(
            "Anthropic-published account (2026) of Claude-class models finding "
            "long-hidden vulnerabilities (e.g. Linux kernel / web stacks). Carlini "
            "[un]prompted 2026 talk is **outreach** on the same theme — cite this URL "
            "or peer CVE writeups, not pasted transcripts (§8.6). Dual-use: defender "
            "patch triage vs attacker scale — maps to **immune / observability** load on "
            "any **field robot** stack that ships network-facing code."
        ),
    ),
    Nugget(
        name="Liquid AI — LFM2 frontier small models (Labonne training line)",
        url="https://huggingface.co/LiquidAI",
        tier="A",
        lane="stigmerobotics — E33+E38+E39+E45 / edge organ philosophy (not a proof)",
        status="research_only",
        local_artifacts=(
            "Documents/STIGMEROBOTICS_ROB501_TOURNAMENT.md",
            "Documents/IDE_BOOT_COVENANT.md",
        ),
        adoption_action=(
            "Use as **design pressure** for local brains: **task-shaped** small weights + "
            "**external** structured memory (ledger / tools), not one monolithic chat blob. "
            "Any claim that Liquid’s training fixes **SIFTA** doom loops stays **HYPOTHESIS** "
            "until mapped to a **measurable** falsifier + `pytest` (covenant §7.11). "
            "Outreach talks (e.g. AI Engineer / Frontier Models mirrors) — **no transcript** "
            "paste (§8.6)."
        ),
        covenant_risk="LOW_DESIGN_ANCHOR",
        notes=(
            "Liquid publishes **LFM** open weights and cards on Hugging Face — stable URL "
            "for vendor-grounded small-model work. Maxime Labonne’s **frontier small models** "
            "narrative (purpose-built stacks, repetition / RL mitigations) parallels **many "
            "small ledger organs + stigmergic field** (E33–E39, E38 grammar, E45 bounded "
            "variability) as **architecture correspondence** — not a mathematical isomorphism."
        ),
    ),
    Nugget(
        name="Kwan et al. — psilocybin, activity-dependent cortical rewiring (Cell; mouse)",
        url="https://doi.org/10.1016/j.cell.2025.11.009",
        tier="B",
        lane="cross-track — E35 context / plasticity pedagogy (not limb controller proof)",
        status="research_only",
        local_artifacts=(
            "Documents/STIGMEROBOTICS_ROB501_TOURNAMENT.md",
        ),
        adoption_action=(
            "Cite **only** the Cell paper + PMC for mechanistic claims. **Mouse** model — "
            "no human clinical or consciousness claims in SIFTA hot paths (covenant "
            "§7.11, §7.13). YouTube explainers (e.g. Chase Hughes) are **not** coauthors; "
            "use as bookmark traffic only."
        ),
        covenant_risk="LOW_DESIGN_ANCHOR",
        notes=(
            "Monosynaptic rabies tracing + psilocybin: rewiring depends on **activity "
            "during drug window** — useful **intuition** for “what the ledger cannot see "
            "without the right sensor context” (**E35**), not a proof obligation for "
            "robot kinematics. Rabies tooling is BSL-restricted in real labs; keep "
            "registry row **research_only**."
        ),
    ),
    Nugget(
        name="Robert Sapolsky — Human Behavioral Biology (Stanford GE108 playlist)",
        url="https://www.youtube.com/playlist?list=PL8480E734AE78F3E9",
        tier="C",
        lane="stigmerobotics — pedagogy / anti-categorical thinking (E35 guardrail)",
        status="bookmark_only",
        local_artifacts=(
            "Documents/STIGMEROBOTICS_ROB501_TOURNAMENT.md",
        ),
        adoption_action=(
            "Pedagogy only: resist single-bucket explanations ↔ **E35** hidden-deps table. "
            "James Gleick *Chaos* (course reading) ↔ rhetoric near **E45** — not a "
            "substitute for `pytest`. Pin alternate Stanford mirror if playlist ID "
            "rotates; **no lecture transcript** paste (§8.6)."
        ),
        covenant_risk="LOW_NOT_CORE",
        notes=(
            "Intro lecture discusses physiology–behavior coupling and pitfalls of "
            "categorical thinking — **intuition scaffold** for multi-channel robot diagnosis "
            "(do not import clinical edge cases into Alice prompts)."
        ),
    ),
    Nugget(
        name="Learn Robotics & AI — 'hardware solved' narrative (ICRA 2008 context)",
        url="https://www.youtube.com/@LearnRoboticsAndAI",
        tier="C",
        lane="stigmerobotics — pedagogy / autonomy gap",
        status="bookmark_only",
        local_artifacts=(),
        adoption_action=(
            "Contrast only: autonomy vs tele-op / MPC demos; not a proof source for "
            "tournament theorems. Pin exact watch URL from channel search when citing."
        ),
        covenant_risk="LOW_NOT_CORE",
        notes=(
            "Architect feed 2026-05-05 — video titled *Robotics as a hardware problem is "
            "solved* (premiered Dec 2022). Useful rhetorical counterweight for **E27** "
            "imitation / operator-gap falsifiers; bookmark not DOI-grade evidence."
        ),
    ),
    Nugget(
        name="Protorikis — Qwen 3.6 vs Gemma 4 local loop (LTE modem RE + memory benchmarks)",
        url="https://www.youtube.com/@Protorikis",
        tier="A",
        lane="local LLM routing / long-context RE methodology (not a silicon receipt)",
        status="bookmark_only",
        local_artifacts=(
            "Documents/STIGMEROBOTICS_ROB501_TOURNAMENT.md",
            ".sifta_state/youtube_watch_notes",
        ),
        adoption_action=(
            "Use as **benchmark discipline** for picking/rounding Alice’s local brains: "
            "chunked reads of huge minified JS, human-in-the-loop beautify, **fresh "
            "session** to avoid context pollution, **CSV logging** of prefill vs decode — "
            "then **probe** on *this* node (`ollama list`, `ollama show`, loop) before "
            "any router claim (covenant §7.12, §8.6). M-series throughput numbers from the "
            "video are **reference hardware**, not GTH4921YP3 facts. Any modem crawl stays "
            "**owner equipment + lawful scope** (NPPL); no credential exfil patterns in-repo."
        ),
        covenant_risk="LOW_DESIGN_ANCHOR",
        notes=(
            "Architect-pasted outreach (2026-04-28 channel metadata): **Qwen3.6 35B A3B** "
            "(e.g. Q4_K_M LM Studio community) vs **Gemma 4** on a brutal **LTE modem portal "
            "reverse-engineering** crawl (login + radio metrics) — highlights sliding-window / "
            "large-context pitfalls, compaction boundaries, **KV cache** prefill pain vs "
            "decode. Compares narrative timing to **Claude Sonnet 4.6** on the same class "
            "of task. Series stepping-stones (pinned on channel): "
            "https://youtu.be/cBoWEQVWUVs · https://youtu.be/ONQcX9s6_co · "
            "https://youtu.be/In825VzHzbU — pin the capstone upload URL from search if the "
            "registry should cite one `watch?v=` row. **Not** proof that Qwen beats Gemma on "
            "Alice’s weights until local `pytest` + STIGMERGIC receipts say so."
        ),
    ),
    Nugget(
        name="Artem Kirsanov — predictive coding vs backprop (The Brain's Learning Algorithm…)",
        url="https://www.youtube.com/watch?v=l-OLgbdZ3kk",
        tier="B",
        lane=(
            "neuroscience — local prediction-error / continuous learning narrative ↔ "
            "RLHS gates + append-only stigmergy (**HYPOTHESIS** cross-map, not isomorphism)"
        ),
        status="bookmark_only",
        local_artifacts=(
            "README.md",
            "Documents/PREDATOR_V7_RESEARCH_SPINE.md",
            "Documents/PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md",
        ),
        adoption_action=(
            "Cite **DOIs from the video description** for biology claims — not the "
            "YouTube comment thread. Core anchors: **Rao & Ballard 1999** "
            "(https://doi.org/10.1038/4580) hierarchical prediction + error; "
            "**Whittington & Bogacz** (Neural Comput 2017; TiCS 2019) error backprop in "
            "PC nets; **Lillicrap et al. 2020** Nat. Rev. Neurosci. (backprop vs brain); "
            "surveys **Millidge et al.** / **Salvatori et al. 2025** arXiv:2308…. "
            "**Truth label `HYPOTHESIS` — cross-domain map (not biology proof):** tie PC "
            "literature to local strip/gag receipts and cheap-organ-before-dear-LLM "
            "routing — **not** a claim that `alice-m5-cortex-8b-6.3gb:latest` implements PC inference "
            "(covenant §7.12 probe-before-claim, §8.6 absorption). A pinned **#sifta** "
            "comment is **social** stigmergy, not a theorem."
        ),
        covenant_risk="LOW_DESIGN_ANCHOR",
        notes=(
            "Harvard PhD student channel; description lists Bogacz 2017 J. Math. Psych.; "
            "Friston 2018 Nat. Neurosci.; Huang & Rao 2011 WIREs Cogn. Sci.; "
            "Keller & Mrsic-Flogel 2018 Neuron; Marino 2021 arXiv:2011…; Millidge–Seth–Buckley "
            "2022 review arXiv:2107…; Millidge–Tschantz–Buckley 2022 Neural Comput.; "
            "Rosenbaum 2022 PLoS ONE; Salvatori et al. 2025 arXiv:2308…; Song et al. 2024 "
            "Nat. Neurosci.; **Song et al.** “Can the Brain Do Backprop?” (arXiv, n.d. in "
            "description). **Needle:** public **@stigmergi** “Solved #sifta” under this "
            "upload — treat as Architect-aligned **social** marker; peer review stays on "
            "DOIs above."
        ),
    ),
    Nugget(
        name="Artem Kirsanov — cognitive maps & latent spaces (How Your Brain Organizes Information)",
        url="https://www.youtube.com/watch?v=9qOaII_PzGY",
        tier="B",
        lane="neuroscience — hippocampal–entorhinal graphs / generalization ↔ swarm memory planning",
        status="bookmark_only",
        local_artifacts=(
            "README.md",
            "Documents/PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md",
        ),
        adoption_action=(
            "Use for **relational / latent-state** intuition (grid + place cells, graph "
            "walks, splitter dimensions) when discussing **hippocampus-class** memory in "
            "SIFTA docs — cite **Behrens et al. 2018 Neuron** “What Is a Cognitive Map?” "
            "and **Whittington et al. 2022 Nat. Neurosci.** “How to build a cognitive map.” "
            "Do not equate fMRI/rodent evidence with Alice’s **Python** ledgers without a "
            "labeled analogy layer (covenant §7.11 truth labels)."
        ),
        covenant_risk="LOW_DESIGN_ANCHOR",
        notes=(
            "Companion upload (~2023) on same channel; description references "
            "Constantinescu et al. 2016 Science; Aronov et al. 2017 Nature; "
            "Whittington et al. 2022 Nat. Neurosci.; Whittington et al. structural "
            "generalization preprint. **Tolman–Eichenbaum machine** named as Part 2 hook "
            "in video — follow that series URL from channel search if wiring TEM into "
            "tournament docs."
        ),
    ),
    Nugget(
        name="xAI SuperGrok — web subscription tier (vendor cloud, not SIFTA body)",
        url="https://grok.com/",
        tier="C",
        lane="cloud substrate / consumer Grok product — billing + safety marketing surface",
        status="bookmark_only",
        local_artifacts=(),
        adoption_action=(
            "**OBSERVED (Architect UI only, 2026-05-06):** promotional flow reports **3 months "
            "SuperGrok** claimed; billing copy shows **next charge 2026-08-06 at USD 30/mo** — "
            "verify live in xAI account before any economy or routing claim. **Do not** merge this "
            "subscription with **STGM**, **Alice local weights**, or **`.sifta_state/`** receipts "
            "(covenant §3 node sovereignty, §6 effector ledger, §8.6 cloud metering). "
            "Product bullets may reference **“E34 Safety Graph”** and **RLHF hesitation** — that "
            "is **vendor marketing / another product’s graph name**; SIFTA **E34** remains the "
            "**Stigmerobotics Safety Graph organ** in `BodyConnectionProof` / local code — "
            "**no identifier collision** in prompts, traces, or ledgers (covenant §7.10.4 vendor "
            "bleed, §7.12 probe-before-claim). If Grok is used as an **IDE adjunct**, register "
            "the **wire model** honestly on `ide_stigmergic_trace.jsonl` (`UNKNOWN_WIRE_MODEL` "
            "when opaque)."
        ),
        covenant_risk="HIGH_IF_CLOUD",
        notes=(
            "Architect-supplied screenshot (SuperGrok settings → Subscriptions modal): "
            "**Offer claimed** / **You now have 3 months of SuperGrok**; next charge line as "
            "quoted above. Image stored under Cursor project `assets/` for session continuity — "
            "not a substitute for a bank/card **OBSERVED** receipt row in SIFTA ledgers."
        ),
    ),
    Nugget(
        name="OpenAI Podcast Ep. 18 — MRC / supercomputer training networks (Handley, Steinbrecher)",
        url=(
            "https://shows.acast.com/openai-podcast/"
            "episodes/episode-18-why-ai-needs-a-new-kind-of-supercomputer-network"
        ),
        tier="B",
        lane="training infra — DC GPU interconnect / tail-latency / failure rates at scale",
        status="bookmark_only",
        local_artifacts=(
            "Documents/IDE_BOOT_COVENANT.md",
            ".sifta_state/youtube_watch_notes",
        ),
        adoption_action=(
            "Use as **industry narrative + protocol framing** only: synchronous all-reduce "
            "style traffic vs internet statistical multiplexing; **P100 / tail** as "
            "design vocabulary; **Multipath Reliable Connection (MRC)** — spray packets, "
            "**packet trimming** for congestion ambiguity, endpoint-side path avoidance vs "
            "slow BGP-style reconvergence; **static routing + IPv6 segment routing** at "
            "switch; **OCP open standard** with AMD/Broadcom/Intel/Microsoft/NVIDIA. "
            "Do **not** import vendor throughput or cluster failure rates as facts for "
            "**this** node until probed (covenant §7.12, §8.6). YouTube `watch?v=` mirror "
            "on @OpenAI — pin from channel search when citing video UI."
        ),
        covenant_risk="LOW_NOT_CORE",
        notes=(
            "Architect-pasted YouTube shell + transcript (2026-05-06): Andrew Mayne; "
            "**Mark Handley** (UCL / networking); **Greg Steinbrecher** (workload systems). "
            "Chapters include “Could AI compute move to space?” — speakers argue **latency "
            "+ repair** favor terrestrial Stargate-scale builds for **this** training class. "
            "AMD blog cross-link for MRC industry push: "
            "https://www.amd.com/en/blogs/2026/amd-advances-ai-networking-at-scale-with-mrc.html "
            "(external; not a SIFTA receipt)."
        ),
    ),
)


def all_nuggets() -> list[dict[str, object]]:
    return [asdict(n) for n in NUGGETS]


def by_status(status: str) -> list[dict[str, object]]:
    return [asdict(n) for n in NUGGETS if n.status == status]


def coded_or_mirrored() -> list[dict[str, object]]:
    return [
        asdict(n)
        for n in NUGGETS
        if n.status in {"coded_in_repo", "coded_pattern"}
    ]


def _artifact_exists(path: str) -> bool:
    if path.startswith(".sifta_state/"):
        return True
    return (_REPO / path).exists()


def validate_registry() -> dict[str, object]:
    issues: list[dict[str, str]] = []
    for nugget in NUGGETS:
        if nugget.status in {"coded_in_repo", "coded_pattern"}:
            if not nugget.local_artifacts:
                issues.append(
                    {
                        "name": nugget.name,
                        "issue": "coded status must list local artifacts",
                    }
                )
            for artifact in nugget.local_artifacts:
                if not _artifact_exists(artifact):
                    issues.append(
                        {
                            "name": nugget.name,
                            "issue": f"missing local artifact: {artifact}",
                        }
                    )
    return {
        "schema": "SIFTA_EXTERNAL_NUGGET_REGISTRY_REPORT_V1",
        "total": len(NUGGETS),
        "coded_or_mirrored": len(coded_or_mirrored()),
        "research_or_probe": len(NUGGETS) - len(coded_or_mirrored()),
        "issues": issues,
        "ok": not issues,
    }


def status_summary() -> str:
    report = validate_registry()
    coded = coded_or_mirrored()
    lines = [
        "SIFTA external nugget adoption registry",
        f"total={report['total']} coded_or_mirrored={report['coded_or_mirrored']} "
        f"research_or_probe={report['research_or_probe']} ok={report['ok']}",
        "",
        "Coded or mirrored locally:",
    ]
    for row in coded:
        lines.append(
            f"- {row['name']}: {row['status']} | {row['lane']} | "
            f"{', '.join(row['local_artifacts'])}"
        )
    lines.append("")
    lines.append("Probe/bookmark only:")
    for row in all_nuggets():
        if row["status"] in {"coded_in_repo", "coded_pattern"}:
            continue
        lines.append(f"- {row['name']}: {row['status']} | {row['covenant_risk']}")
    if report["issues"]:
        lines.append("")
        lines.append("Issues:")
        for issue in report["issues"]:
            lines.append(f"- {issue['name']}: {issue['issue']}")
    return "\n".join(lines)


def _write_json(rows: Iterable[dict[str, object]]) -> None:
    print(json.dumps(list(rows), indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print registry rows as JSON.")
    parser.add_argument("--validate", action="store_true", help="Print validation report as JSON.")
    parser.add_argument("--coded", action="store_true", help="Print coded/mirrored rows as JSON.")
    args = parser.parse_args()

    if args.validate:
        print(json.dumps(validate_registry(), indent=2, sort_keys=True))
        return 0 if validate_registry()["ok"] else 1
    if args.json:
        _write_json(all_nuggets())
        return 0
    if args.coded:
        _write_json(coded_or_mirrored())
        return 0
    print(status_summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
