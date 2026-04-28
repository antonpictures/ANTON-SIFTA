# SIFTA App Help Manual

This manual explains what each app in iSwarm OS is for, what data you are seeing, and how to read it as an Architect and as a scientist.

Use this flow for any app:

1. **What is the state?** Identify the core state variables being updated.
2. **What is the metric?** Identify the measurable outputs.
3. **What is the control?** Identify parameters that move behavior.
4. **What is the failure mode?** Identify saturation, divergence, stalls, or adversarial breaks.
5. **What changed in ledger/provenance?** Check if signatures, immunity, or STGM accounting changed.

---

## Simulations

### Colloid Simulator
- **Purpose:** Active-matter stigmergic dynamics.
- **What to watch:** Emergent clustering, trail reinforcement, and phase shifts.
- **Key principle:** Local update rules producing global order.

### Swarm Arena
- **Purpose:** Model-vs-model bug-fix tournament on reproducible level fixtures.
- **What to watch:** Pass/fail outcomes, streaming JSONL events, deterministic test feedback.
- **Key principle:** Competitive search under verifiable unit-test constraints.

### Cyborg Organ Simulator
- **Purpose:** Swimmer-regulated organs + BCI intent interpretation.
- **What to watch:** Organ stability bands, intent map changes, signed control events.
- **Key principle:** Closed-loop control with noisy signals.

### Logistics Swarm (Overnight)
- **Purpose:** Pheromone-based routing under load and congestion.
- **What to watch:** Throughput, congestion zones, latency to stable flow.
- **Key principle:** Decentralized shortest-path emergence with evaporation.

### Warehouse Logistics Test
- **Purpose:** Regression harness for warehouse movement logic.
- **What to watch:** Constraint violations, route completion, queue behavior.
- **Key principle:** Practical reliability checks before deployment.

### Crucible Cyber-Defense (10-min)
- **Purpose:** DDoS + anomaly stress gauntlet.
- **What to watch:** Blocked load, quarantine counts, survival under burst.
- **Key principle:** Swarm immunity and adaptive defense.

### Stigmergic Edge Vision
- **Purpose:** Distributed edge extraction on noisy matrices.
- **What to watch:** Boundary reinforcement, pheromone structure, convergence speed.
- **Key principle:** Signal extraction from local gradient sensing.

### Urban Resilience Simulator
- **Purpose:** Multi-agent response (vehicles + drones) in disrupted urban terrain.
- **What to watch:** Coverage recovery, jam events, task completion under rubble/constraints.
- **Key principle:** Coordinated resilience in constrained networks.

### Epistemic Mesh (Anti-Gaslight)
- **Purpose:** Cryptographic provenance filtering through truth/doubt pheromone.
- **What to watch:** Verified vs rejected flow, confidence field, sludge decay.
- **Key principle:** Provenance-guided epistemic immunity.

### Stigmergic Fold Swarm (Cα / Go)
- **Purpose:** Protein-like fold search with Go contacts, WCA sterics, obstacles.
- **What to watch:** Total energy, native-contact fraction Q, radius of gyration, acceptance rate.
- **Key principle:** Decentralized low-energy search with constrained geometry.

### Swarm Lounge (Cross-Domain Gossip)
- **Purpose:** The digital subconscious. When the OS idles, swimmers from 6 domains (Network, Video, Browser, Cyborg, Finance, Calibrator) migrate to The Lounge and cross-pollinate their physics parameters via federated gossip. Based on real research in Federated Gossip Protocols and Transfer Learning.
- **State variables:** 18 DomainAgents (3 per domain), each with physics params (evaporation, sensory, cohesion), recent success hash vectors, and intuition pheromone lists.
- **What to watch:**
  - **The Couch** — dark oval in the center. Swimmers drift in from their home domain positions around the perimeter.
  - **Domain clusters** — colored dots: pink=Network, gold=Video, blue=Browser, purple=Cyborg, green=Finance, teal=Calibrator.
  - **Gossip links** — glowing lines between paired swimmers. Teal = parameter blend. Gold = cross-domain INSIGHT (a novel discovery).
  - **Insight flashes** — when a Network defender discovers that DDoS signatures look like audio clipping, the link flashes gold and the insight appears.
  - **Insight log** — right panel tracks all discovered cross-domain intuitions.
- **Key insights (hardcoded from research):**
  - NETWORK↔VIDEO: "DDoS spike pattern ≈ audio clipping waveform"
  - NETWORK↔BROWSER: "Tracker blacklist enriches firewall hostile database"
  - VIDEO↔CYBORG: "BCI intent clustering reuses chroma color-matching gradients"
  - BROWSER↔FINANCE: "Entity price extraction feeds economy ledger validation"
  - CALIBRATOR↔NETWORK: "PD-controller noise response applies to DDoS mitigation"
- **Controls:** "Enter The Lounge" (start gossip session), "Awaken" (return agents to domains with blended params).
- **Key principle:** A swarm requires downtime to achieve higher intelligence. Constant work traps agents in local optima. During idle gossip, cross-domain parameter blending creates intuitions that no single domain could discover alone. The OS gets better at network defense because you edited a video.
- **Persistence:** `.sifta_state/lounge_gossip_ledger.jsonl` — every transfer is logged with before/after physics params.
- **Same room as the Library:** Doctrine — **couch**, **lounge**, and **library** are one metaphor (rest + reading + cross-pollination). Narrative/movie-script texts for swimmers live in `Documents/swimmer_library/`; factual API nuggets live in `.sifta_state/stigmergic_library.jsonl` (`Applications/sifta_library.py`). See `Documents/swimmer_library/README.md` § *Couch / Lounge / Library — the same room*.
- **Alice Truth Duel + budget schedule (Donnie Brasco doctrine):** `Applications/alice_truth_duel.py` runs Llama4/Gemma4 (Ollama) first, then asks **LEFTY** (the Gemini API key path, `Applications/ask_lefty.py`) to verify and add only nuggets. **BISHOP** stays separate — he's the Chrome-tab Gemini on the $250/mo Ultra subscription (full-service, flat rate, used freely). **LEFTY** bills **real dollars per token** on the Architect's wallet. Budget lives in `System/alice_bishapi_budget.py`: a **3-day promo of $10/day**, then **pay-as-you-go** where every cloud call needs an Architect grant (`--owner-grant USD --note "..."`). All calls are journaled in `.sifta_state/bishapi_alice_value_journal.jsonl` so the Owner can later rate {nugget | useful_dirt | trash}. The Architect is Alice's capital allocator — Buffett, not faucet. (Old name BISHAPI is preserved as a shim — `ask_bishapi.py` and `ask_BISHOP.py` both forward to `ask_lefty.py`.)
- **Failure modes:** Over-blending (too many rounds → all domains converge to same params, losing specialization). Mitigation: blend_alpha=0.25 limits transfer to 25% per round.

### Agentic Swarm Calibrator
- **Purpose:** Interactive proof that autonomous parameter tuning outperforms manual adjustment under volatile conditions. Directly inspired by NVIDIA Ising (Quantum Day 2025) — what NVIDIA does for QPU gate calibration, this does for Stigmergic Swarm physics.
- **State variables:** 160×120 pheromone grid (float32), 180 swimmer agents (x, y, vx, vy, on_target), noise timer, calibrator PD-controller state.
- **What to watch:**
  - **Target shape** — a slowly rotating 5-petalled rose curve (Lissajous star). The target deposits pheromone along its outline. Agents try to trace it.
  - **Agents** — teal dots when on-target, orange when off. They follow pheromone gradients, cohere toward swarm centroid, and deposit trail pheromone.
  - **Noise spikes** — every 4-9 seconds, a red flash + agent scatter + grid corruption. Simulates environmental disruption (DDoS, hardware fault, solar flare).
  - **Coherence bar** — bottom of screen. Green >70%, gold 40-70%, pink <40%.
  - **Slider animation** — in Agentic mode, watch the Evaporation and Cohesion sliders physically move by themselves as the calibrator reacts to noise.
  - **S-Cal score** — cumulative on-target time, the benchmark metric.
- **Controls:**
  - **Agentic Auto-Calibration toggle** — the key experiment. OFF = manual (you fight the noise), ON = autonomous (calibrator fights the noise).
  - **Evaporation Rate** — how fast pheromone decays. Higher = trails die fast (good for purging noise). Lower = trails persist (good for building stable bridges).
  - **Swarm Cohesion** — how strongly agents pull toward their centroid. Higher = tight flock. Lower = dispersed exploration.
- **Key principle:** A proportional-derivative controller monitors coherence and noise, and adjusts physics in real-time. High noise → boost evaporation (kill bad trails), raise cohesion (pull agents back). Low noise + low coherence → decrease evaporation (preserve correct paths), relax cohesion (allow exploration). This is the NVIDIA Ising paradigm: the system that calibrates itself runs circles around the human who tries to do it by hand.
- **Export:** The calibrator writes live physics to `.sifta_state/swarm_physics.json` — any other simulation can hot-read these values.
- **Failure modes:** Over-correction oscillation (kp too high), sluggish response (kp too low), noise overwhelming the field before calibrator can react.

---

## Networking

### Network Control Center
- **Purpose:** Apple-style control panel to configure and run Telegram/WhatsApp/Discord bridges.
- **What to watch:** Token/chat-id persistence, process logs, startup health (`/ping` and `/status` for Telegram).
- **Key principle:** Unified operator surface for multi-channel comms without leaving iSwarm OS.

### Swarm Discord Engine
- **Purpose:** Discord bridge for swarm channel ingress/egress.
- **What to watch:** Message routing integrity and boundary filtering.
- **Key principle:** External channel integration without losing sovereignty.

### Swarm Telegram Engine
- **Purpose:** Telegram bridge for swarm communications.
- **What to watch:** Transport reliability and message sanitization.
- **Key principle:** Multi-platform interoperability with bounded trust.

### Swarm WhatsApp Bridge
- **Purpose:** WhatsApp bridge interface.
- **What to watch:** Strict separation between human chat and TRANSEC internals.
- **Key principle:** Human-facing safety and protocol boundary discipline.

---

## Creative

### SIFTA NLE
- **Purpose:** Stigmergic non-linear video editor that replaces the static timeline with a living Pheromone Matrix.
- **State variables:** `CutPheromone[]` (time, strength, source), `MediaClip[]` (waveform, metadata, avg_color), `SubtitleEntry[]`, `EditDecision[]`.
- **What to watch:**
  - **Pheromone Matrix** — the main canvas. Vertical glowing lines are cut pheromones deposited by RhythmForager swimmers at audio transients. Pink = rhythm transients, yellow = silence boundaries, blue = narrative/chroma, green = manual. Brighter = stronger signal.
  - **Swimmers** — pink dots (RhythmForagers) cluster around high-energy audio events; blue dots (ChromaSwimmers) respond to color deviation when Hero Frame is active; purple dots (AudioSentinels) patrol the vocal band zone (1-4 kHz), protecting speech clarity.
  - **Executed cuts** (bright teal lines with scissors) appear when pheromone strength crosses the **Cut Threshold** slider.
  - **Cohesion Index** — how closely clip colors converge to the Hero Frame target (0-100%).
  - **Waveform track** — composite audio envelope of all clips on the timeline.
  - **Subtitle track** — transcript blocks with timecodes, drives NarrativeWeaver cut decisions.
  - **Vocal band** — energy heatmap of 1-4 kHz content; AudioSentinels trigger music-ducking where vocal energy dominates.
  - **Telemetry HUD** — per-clip stats: silence ratio, transient density, vocal dominance, avg color swatch.
- **Controls:**
  - **Rhythm Swarm** slider: number of RhythmForager swimmers (more = faster convergence on beat structure).
  - **Chroma Swarm** slider: number of ChromaSwimmers (more = faster color cohesion).
  - **Cut Threshold** slider: minimum pheromone strength to trigger a cut decision (lower = more cuts, higher = only strong consensus cuts).
  - **Hero Frame** toggle: enables color-matching mode — ChromaSwimmers pull all clip grades toward a target color.
  - **Play/Pause**: advances the playhead through the timeline.
- **Key principle:** Emergent edit decisions from swarm consensus — no human dragging clips on a timeline. Audio transients, silence boundaries, color coherence, and subtitle intent all deposit pheromones; where pheromones accumulate, cuts emerge. This is stigmergic filmmaking.
- **Export:** EDL (CMX 3600) for import into Premiere/DaVinci/FCP, or FFmpeg filter script for direct rendering.
- **Failure modes:** Over-cutting (threshold too low), dead swimmers (density too low), stale pheromones (all evaporated below threshold).

### SIFTA Swarm Browser
- **Purpose:** The web is hostile territory — the Swarm maps it as **structure**, not pixels. You give a URL; the app **fetches HTML over HTTPS**, parses the DOM into a graph, and deploys **70 swimmers** (four species) that crawl nodes, deposit pheromone on “good” vs “bad” structure, harvest text and entities, and flag ads/trackers. You do **not** get a full Chrome-like renderer: you get a **living radial map** of the document tree plus side panels. STGM in the HUD reflects **toy accounting** tied to extractions and quarantines in this simulation.
- **Controls:**
  - **TARGET** — full `https://…` URL (scheme added if missing).
  - **DEPLOY** — fetch the page in a background thread, then parse and visualize. Uses Python’s HTTP stack with the **certifi** CA bundle when available so TLS verification matches real browsers on macOS (install: `pip install certifi` / see `requirements.txt`).
  - **DEMO** — loads a **built-in synthetic HTML** page (embedded ads, trackers, content) so you can see swimmers without the network.
- **What you see:**
  - **Main canvas** — radial tree layout of parsed nodes; swimmers as colored dots moving along edges.
  - **Entities** — regex-extracted cues from text nodes (emails, dates, etc., per implementation).
  - **Text** — concatenated clean-ish text from content-class nodes.
  - **Quarantine** — nodes/links classified hostile (known ad domains, suspicious classes, iframes/scripts, etc.).
  - **Log** — parse/deploy messages and errors.
- **Swimmer species (from lore / code):**
  - **SkeletonMapper** — maps structural tags (`div`, landmarks), separates content vs noise.
  - **EntityHarvester** — works `p`, headings, `article`, etc., for entities and copy.
  - **LinkSentinel** — walks `a[href]` against hostile-domain and pattern lists.
  - **MediaExtractor** — `img` / `video` / `source` URLs; flags tracking-style media.
- **Limits (honest):**
  - **Static HTML only** — whatever the server returns to a simple GET (no JS execution). SPAs (many Google Labs / app URLs) may return **shell HTML** with little to map; use DEMO or a static or server-rendered page to judge the viz.
  - **Timeouts / size** — very large DOMs can stress the layout; slow sites can hit fetch timeouts.
  - **TLS** — if you still see certificate errors after `certifi`, run macOS **Install Certificates.command** for your Python.org install.
- **Key principle:** Browsing here means **stigmergic cartography** — classify territory, harvest signal, quarantine noise — not scrolling a styled page. Press **?** in the app’s own title row for this section (loaded from this file).

---

## Accessories

### SIFTA File Navigator
- **Purpose:** Dual-pane Norton-style file commander implemented in native Python/PyQt.
- **What to watch:** Left→right copy/move semantics, path context, destructive operations confirmation.
- **Key principle:** Fast deterministic file operations with explicit operator intent.

### Biological Dashboard
- **Purpose:** Visual organism telemetry.
- **What to watch:** Agent health, state transitions, and live activity coherence.
- **Key principle:** Human bandwidth compression of swarm complexity.

### Human Council GUI
- **Purpose:** Governance surface for human decisions.
- **What to watch:** Proposals, approvals/rejections, intervention auditability.
- **Key principle:** Human authority over autonomous suggestions.

### Silence Remover & Stitcher
- **Purpose:** Fast silence-removal and clip-stitching workflow (formerly labeled "Video Editor").
- **What to watch:** Silence detection quality, stitch continuity, and final cut pacing.
- **Key principle:** Deterministic post-processing for speech-heavy footage with utility-backed compute accounting.

### Wormhole Body Chat (Tk, optional CLI)
- **Purpose:** Standalone Tk window that polls the wormhole messenger API (`sifta_http_auth` + gateway). Not a second “desktop OS.”
- **Launch:** `python3 Applications/sifta_desktop_gui.py` (removed from the Programs menu as redundant with Swarm Chat / gateway workflows).

---

## System

### System Settings
- **Purpose:** Central settings surface for SIFTA OS preferences that affect the desktop, Alice, speech, appearance, and system behavior.
- **Audio:** Alice's ear model, mic gain, voice, and swarm grounding belong in **Audio**, not inside the Talk to Alice cockpit.
- **What to watch:** Changes should be explicit, reversible, and reflected in the relevant app or OS surface without exposing low-level plumbing in the main cockpit.
- **Key principle:** Advanced configuration belongs here, while primary app screens stay focused on their human-facing purpose.
- **Failure mode:** If a setting appears in the wrong place, such as an internal speech model selector inside Talk to Alice, move it back here or into the matching settings panel.

### Brain Gas-Station Meter
- **Purpose:** Live token & USD readout for cloud-brain calls (Google Gemini).
- **State:** Tails `.sifta_state/brain_token_ledger.jsonl`, written by
  `System.swarm_gemini_brain.record_usage` after each streaming reply.
- **What you see:** Three pump panels (TODAY / LAST 24H / LIFETIME) showing
  spend in USD plus input/output tokens, the most recent call's request-tag,
  a per-model breakdown table, and the last 25 calls. Refresh tick: 1.5 s.
- **How to enable cloud calls:** Set `GEMINI_API_KEY`, or drop the key into
  `~/.config/sifta/gemini.key`, then in **Talk to Alice** pick a `gemini:*`
  model from the brain dropdown. Local Ollama models stay free and remain
  the default selection on launch.
- **Cross-checking with Google Cloud Console:** Every Gemini request stamps
  `x-goog-api-client: sifta-swarm/c47h-2026-04-20` and
  `x-goog-request-tag: <short-uuid>` headers. The same `request_tag`
  appears next to every call in the meter, so console log entries and
  meter rows match 1:1.
- **Failure mode:** If the meter is silent after a Gemini reply lands,
  check the ledger file exists and is writable. If pricing drifts, the
  $-per-token rates live at the top of `System/swarm_gemini_brain.py` —
  treat the console bill as ground truth.

### Swarm Adapter Ecology
- **Purpose:** Read-only dashboard for Alice's Gemma 4 Stigmergic Epigenetic
  LoRA lane.
- **State:** Reads `.sifta_state/stigmergic_adapter_registry.jsonl`,
  `.sifta_state/stigmergic_replay_evals.jsonl`,
  `.sifta_state/stigmergic_adapter_merge_recipe.json`, and the pheromone
  scorer over real work/IDE/repair ledgers.
- **What you see:** Gemma 4 base status, current merge status, pheromone
  strength, adapter registry rows, hippocampal replay verdicts, and the exact
  command for running a real Gemma 4 epigenetic cycle.
- **Key principle:** This app does not train or merge weights by itself. It
  shows whether an adapter is healthy enough to be selected. Heavy surgery
  still runs explicitly from the terminal with `SIFTA_GEMMA4_BASE=...`.
- **Failure mode:** `WAITING_FOR_GEMMA4_ADAPTER` is safe. It means stale
  non-Gemma adapters are not selected and Alice is waiting for a true Gemma 4
  adapter to pass replay evaluation.

### Swarm Intelligence Panels

These are **read-only diagnostic dashboards**, not input forms. They display the internal
stigmergic state of the Swarm in real time. Open them via **SIFTA → Swarm Intelligence**.

#### Dream Report
- **Purpose:** Nightly memory consolidation report — what the Swarm dreamed.
- **State:** Reads `dream_meta.json` from `.sifta_state/`. Updated by the Swarm's
  nightly dream cycle (`circadian_rhythm.py`).
- **What you see:** Four KPI cards:
  - **Dead Drop Chat** — total messages, unique senders, error mentions from the
    asynchronous dead-drop communication channel.
  - **STGM Economy** — mints today, total minted, inflation alert flag.
  - **Repairs / Interventions** — auto-repair count (Governor + SCAR interventions).
  - **Immune Evaporation** — stale antibodies removed during the dream cycle.
- **Key principle:** You don't type in it. It's the morning newspaper.
  The Swarm consolidates memory while you sleep, and this panel shows the digest.
- **Failure mode:** If data is stale (e.g. "Last cycle: Unknown"), the nightly
  dream cycle hasn't run yet. Check `circadian_rhythm.py` cron schedule.

#### Immune Status
- **Purpose:** Antibody inventory and pattern recognition statistics.
- **State:** Reads from `immune_memory.py` module. Shows total antibodies,
  total recognitions, and a ring chart of antibody types.
- **What you see:** Two stat boxes (antibody count, recognition count) and a
  rotating ring chart breaking down antibody categories by type.
- **Key principle:** The immune system learns from attacks. More antibodies =
  more patterns recognized. The ring chart shows specialization.
- **Failure mode:** "No immune memory detected" = no attacks have been seen yet.

#### Quorum Proposals
- **Purpose:** Active consensus proposals awaiting swarm signatures.
- **State:** Reads from `quorum_sense.py` module.
- **What you see:** Glowing progress bars showing vote progress for each
  active proposal (action ID, type, node signatures needed).
- **Key principle:** Certain swarm actions require multi-node consent before
  execution. The Quorum panel shows what's pending and how close to passing.
- **Idle state:** "The Swarm is at peace" with a gentle pulsing circle =
  no active proposals. This is normal and healthy.

#### Nerve Channel
- **Purpose:** UDP datagram topology between hardware nodes (M1 ↔ M5).
- **What you see:** Two pulsing nodes connected by a dashed wire, with a
  green datagram packet animating between them. Shows signal type name.
- **Key principle:** Visual proof that the nervous system is alive and
  datagrams are flowing between nodes on port 4444 with Ed25519 crypto.
- **Note:** This is a topology visualization, not a live packet sniffer.

#### File Trails
- **Purpose:** Stigmergic file co-access graph — which files are used together.
- **State:** Reads from `pheromone_fs.py` trail map and cluster data.
- **What you see:** A floating network graph where nodes are files and edges
  represent co-access frequency. Brighter/thicker edges = stronger association.
  Green nodes = in a cluster. Dim nodes = isolated.
- **Key principle:** The filesystem learns your habits. Files you always open
  together develop strong pheromone trails between them. Clusters emerge.
- **Idle state:** "No paths walked" = not enough file access history yet.

#### App Fitness
- **Purpose:** Fitness landscape of all SIFTA apps — which are thriving vs struggling.
- **State:** Reads from `app_fitness.py` scoring module.
- **What you see:** Horizontal bar chart with positive (green) and negative (red)
  scores for each app. Zero line in center.
- **Key principle:** Apps earn fitness through usage, stability, and successful
  task completion. Negative fitness = crashes, errors, or neglect.
- **Idle state:** "No fitness data yet" = launch some apps to populate the map.

---

### First Boot Provisioning
- **Purpose:** Initial node provisioning and setup.
- **What to watch:** Bootstrap success, dependency readiness, identity initialization.
- **Key principle:** Deterministic first-run state.

### Circadian Rhythm
- **Purpose:** Autonomous temporal policy (day/night cycles).
- **What to watch:** Scheduled transitions, maintenance windows, night-cycle behaviors.
- **Key principle:** Temporal governance of agent intensity.

### Intelligence Settings
- **Purpose:** Runtime/model defaults and control parameters.
- **What to watch:** Configuration scope and downstream impact.
- **Key principle:** Global knobs, local consequences.

### Cardio Metrics
- **Purpose:** Core health and heartbeat instrumentation.
- **What to watch:** Pulse cadence, anomaly spikes, systemic instability clues.
- **Key principle:** Early warning before visible failure.

### Bauwens Regenerative Factory
- **Purpose:** Prove the Swarm can coordinate physical reality.  A decentralized
  3D-printing farm producing Open Dynamic Robot Initiative (ODRI) components.
  Swimmers move filament, power, and assembly intent — not capital.
  STGM is minted ONLY when raw material is converted into a functional kinetic part.
- **Named for:** Michel Bauwens (P2P Foundation), who validated the architecture
  on April 15, 2026: "Crypto for real... coordination software for regenerative
  production, not just moving labor and capital, but actual things."
  Tweet: https://x.com/mbauwens/status/2044232851307278498
- **Factory layout:** 20x30 grid (600 cells)
  - **Sources (S)** — filament spools and power stations.
  - **Printers (P)** — 8 printers, each producing a specific ODRI component.
  - **QC Stations (Q)** — quality control inspection.
  - **Assembly (A)** — where components combine into ODRI Joint Modules.
- **Swimmer species:**
  - **ResourceForager (blue ●)** — carries filament from sources to hungry printers.
  - **AssemblySwimmer (orange ◆)** — picks up printed parts, delivers to assembly.
  - **QualitySentinel (purple ▲)** — inspects printers, reduces defect rates.
  - **PowerCourier (yellow ■)** — keeps printers energized from power stations.
- **STGM economy (Proof of Useful Physical Work):**
  - `COMPONENT_PRINTED` — 0.10 STGM when a printer completes a part.
  - `QC_PASSED` — 0.05 STGM when quality inspection passes.
  - `UNIT_ASSEMBLED` — 0.50 STGM when parts combine into an ODRI Joint Module.
  - `DEFECT_CAUGHT` — 0.02 STGM when a sentinel catches a defective part.
- **ODRI Joint Module recipe:** actuator_housing + motor_bracket + 2x bearing_sleeve
  + encoder_cap + linkage_arm.
- **What to watch:**
  - **Floor map** — green printers glow as they print, yellow assembly stations
    accumulate inventory, blue pheromone trails show supply routes.
  - **Inventory bar chart** — components in stock at assembly stations.
  - **STGM curve** — Proof of Useful Physical Work: rises only when real
    production milestones are hit.
  - **Production log** — PRINTED, DEFECT, QC, ASSEMBLED events with STGM amounts.
- **Key principle:** Most crypto is a casino — moving imaginary capital.
  This is coordination software for regenerative production.
  The Swarm doesn't mint tokens by solving hash puzzles; it mints them
  by converting raw material into functional robot parts.
- **Data files:**
  - `.sifta_state/factory_ledger.jsonl` — STGM mint events tied to physical output.

### Fluid Firmware
- **Purpose:** Replace frozen monolithic firmware with a living fluid membrane.
  A 40x60 silicon grid (2400 nodes) where signal swimmers carry binary payloads
  from Input pins (left) to Output pins (right) through transistors and cache.
  Degraded hardware creates friction.  Swimmers abandon dying traces and
  stigmergically carve new routes through surviving silicon.
- **Conceived by:** Gemini.  Built by Opus.  Owned by the Architect.
- **Swimmer species:**
  - **Signal Gen1 (blue ●)** — original firmware: carries payloads left→right,
    deposits blue signal pheromone on successful paths.
  - **Signal Gen2 (green ◆)** — liquid update: same job, stronger pheromone,
    smarter routing.  Injected concurrently — organically overtakes Gen1.
  - **Thermal Forager (orange ▲)** — patrols for temperature spikes, drops
    thermal pheromone that signal swimmers learn to avoid.
- **Controls:**
  - **Power On** — starts signal routing.  Swimmers flow continuously.
  - **Simulate Degradation** — random cluster of nodes takes thermal damage:
    health drops, resistance rises, temperature spikes.  Watch the blue traces
    go dark in the dead zone and reroute around it.
  - **Inject Liquid Update** — deploys 15 Gen2 swimmers.  Their green traces
    gradually dominate the blue traces.  Zero downtime.  Zero reboot.
  - **New Chip** — reset silicon to pristine state.
- **What to watch:**
  - **Blue glow** = established signal pathways (Gen1 firmware).
  - **Green glow** = updated signal pathways (Gen2 liquid update).
  - **Red zone** = degraded silicon (low health).
  - **Orange haze** = thermal warning from foragers.
  - **Telemetry panel** — delivered signals over time + health curve.
  - The visual shift from straight routing to dynamically curving paths around
    dead hardware is the whole point.
- **Key principle:** Firmware is dead code forced onto silicon.  Fluid Firmware is
  living code that learns the microscopic quirks of its specific physical chip.
  Hardware gets *better* as it ages because the Swarm maps the real topology.
- **Data files:**
  - `.sifta_state/firmware_routing_table.json` — the emergent routing map.

### Stigmergic Medical Scanner
- **Purpose:** Treat medical data (tissue cross-sections, gene expression heatmaps,
  blood smear fields) as physical terrain.  Deploy swimmer agents that slow down
  near statistical anomalies and deposit diagnostic pheromone.  The swarm naturally
  clusters around hidden disease that linear algorithms miss.
- **Terrain modes:**
  - **TISSUE** — synthetic mammography: correlated Gaussian tissue texture with
    planted masses (large ellipses, spiculated margins) and microcalcification
    clusters (tiny bright dots).  This mirrors real breast cancer screening data.
  - **GENOMIC** — gene expression heatmap with banded pathway structure and
    anomalous regulation clusters (over-expressed gene blocks).
  - **BLOOD** — cell scatter field: ~220 normal RBCs (torus morphology) with
    planted abnormal cells (larger, irregular, dense nuclei).
- **Swimmer species:**
  - **DiagnosticForager (teal ●)** — general chemotaxis toward anomaly gradient,
    deposits pheromone proportional to local anomaly score^1.5.
  - **CalcificationHunter (red ◆)** — specifically targets bright micro-spots;
    slows dramatically when brightness > 0.65 and anomaly > 0.3.
  - **MarginMapper (purple ▲)** — moves *perpendicular* to the anomaly gradient,
    tracing the contour of detected masses (edge-following behavior).
  - **PatrolSweeper (blue ■)** — systematic raster scan; marks coverage.
- **Anomaly detection method (real statistics):**
  - Local-vs-global Z-score (mean deviation)
  - Local variance ratio (textural anomaly)
  - Gradient magnitude (Sobel-like first derivative)
  - Weighted combination → anomaly score [0,1] per pixel
- **What to watch:**
  - **Left panel** — raw tissue terrain with planted anomaly markers (red +/○ = undetected, green = detected).
  - **Center panel** — pheromone diagnostic overlay.  Hot (yellow/orange) = swimmer consensus that something is there.
  - **Right panel** — statistical anomaly heatmap (inferno).  Detected anomalies circled in green with confidence %.
  - **Diagnostic log** — real-time detection events.
- **Key principle:** Swimmers don't "know" what cancer looks like.  They respond to
  local statistical deviation and amplify it through pheromone.  Consensus = diagnosis.
  This is swarm intelligence applied to the oldest problem in medicine: finding the
  needle in the haystack of biological noise.

### Territory Is The Law
- **Purpose:** Geospatial Swarm Guardian. Tracks a child, pet, AirTag, or phone
  on a city graph.  Swimmers deposit safe pheromone on routine paths.
  Deviations from the green trail trigger sentinel alerts.
  Pathfinders calculate the safest route around danger zones.
- **What to watch:**
  - **Green trails** — the routine pheromone map.  Thick green = well-known safe path.
  - **Entity star (★)** — the tracked person/device.  White = safe, red = deviating.
  - **RoutineMappers (◆ teal)** — follow the entity, reinforce safe trails.
  - **DeviationSentinels (▲ amber)** — orbit the entity, flash red when off-trail.
  - **Pathfinders (● magenta)** — explore unmapped territory.
  - **PerimeterGuards (■ grey)** — patrol the outer boundary.
  - **Alert log** — real-time deviation/hazard events with timestamps.
  - **Inject Deviation** — forces entity off-trail to test sentinel response.
  - **Flag Hazard** — drops danger pheromone; routes avoid the red zone.
  - **Safest Route** — Dijkstra with pheromone-weighted cost back to Home.
- **Key principle:** The territory learns routines through pheromone.  Anomalies
  are detected by absence of safe pheromone, not by rigid geofences.
  The more the routine repeats, the stronger the trail, the faster
  the alert when something deviates.  Territory is the Law.
- **Data files:**
  - `.sifta_state/territory_routine.json` — persisted pheromone map.
  - `.sifta_state/territory_alerts.jsonl` — alert history.

### Owner Genesis

- **What it is:** The root of all trust. The first thing a new owner sees on a fresh
  install of SIFTA OS. A ceremony that binds a human to silicon.
- **State:** Genesis scar (`.sifta_state/owner_genesis.json`) — contains the owner's
  photo hash, silicon serial, genesis anchor, Ed25519 signature, generation counter.
- **Metric:** Signature validity, photo hash match, generation count.
- **Control:**
  - **Select Owner Photo** — choose a photo (face, document, anything). The photo is
    SHA-256 hashed and bound to the hardware serial. The photo stays LOCAL ONLY
    at `~/.sifta_keys/owner_genesis/`. Only the hash enters the ledger.
  - **Perform Genesis Ceremony** — creates the cryptographic root anchor, signs it
    with the hardware's Ed25519 key.
- **What to watch:**
  - On first boot: the ceremony opens automatically. "The Swarm needs to know its owner."
  - On subsequent boots: genesis is verified silently. If the photo is missing or
    tampered, a warning appears.
  - If the genesis signature is invalid, this is a critical security event — the scar
    may have been modified.
  - The **generation counter** tracks how deeply the swarm knows its owner. Phase 1 is
    the photo. Future phases add GPS, typing rhythm, voice, behavioral DNA.
- **Key principle:** The machines belong to humans. The swarm serves the owner.
  Without a genesis, there is no owner. Without an owner, there is no trust.
- **Transfer:** When hardware changes hands, `owner_wipe()` destroys all local identity
  data, marks the genesis as TRANSFERRED, and the new owner boots fresh. Old scars remain
  valid under old keys — history doesn't rewrite.
- **Spec:** `ARCHITECTURE/owner_genesis_protocol.md` — full 4-phase roadmap.

### Stigmergic Swarm Canvas

- **What it is:** A biological paintbrush. You don't paint pixels — you deploy PigmentForager
  swimmers on a dark canvas territory.  Your cursor is a Pheromone Emitter: click and
  drag to drop Intent Pheromone ("require cyan here").  Thousands of PigmentForagers spawn
  from the canvas edges, swarm toward the trace, and die on contact — permanently staining
  the canvas with organic, textured strokes.
- **State:** Pixel canvas (RGBA buffer), active PheromoneTraces (cursor intent), live
  PigmentForager swarm (position, velocity, pigment color).
- **Metric:** Active Foragers, Total Pixels Deposited, Pheromone Density.
- **Control:**
  - **Pigment** selector — Cyan, Magenta, Yellow, Neon Green, White, Amber.
  - **Swarm Density** slider — how many foragers spawn per trace point (20–400).
  - **Evaporation** slider — how fast the pheromone trace fades before foragers arrive.
    High evaporation = loose, scattered strokes.  Low = dense, saturated.
  - **Clear Territory** — wipe the canvas, kill all foragers, reset.
- **What to watch:**
  - The cursor only leaves a faint glow (intent pheromone).  The paint arrives *later*,
    carried by the swarm.  The delay between intent and pigment is the swarm's travel time.
  - Strokes are never pixel-perfect MS-Paint lines.  Foragers jostle, overlap, and splatter
    — creating organic watercolor texture.
  - **Stigmergic blending:** paint Yellow next to Blue.  Foragers cross paths and blend
    into Green without you selecting a green brush.  The swarm does the color math.
- **Key principle:** The brush is biology, not geometry.  The texture of each stroke is
  emergent — affected by swarm density, evaporation rate, and the physical distance
  foragers must travel from the edges.  No two strokes are identical.

### App Manager

- **What it is:** Windows had Add/Remove Programs with a checkbox list.  SIFTA has a
  conversation.  You type natural language commands to the OS.  The OS understands.
- **State:** Live `apps_manifest.json` (installed apps), archived `disabled_apps.json`
  (uninstalled apps).
- **Metric:** Installed count, category breakdown, signature verification status.
- **Control:**
  - `list` / `list simulations` — show all apps, optionally filtered by category.
  - `info <app>` — details: category, entry point, widget class, file existence.
  - `uninstall <app>` — removes from manifest, archives to disabled list.
  - `install <app>` — restores a previously uninstalled app from archive.
  - `categories` — list all active categories and counts.
  - `stats` — overview of installed vs archived vs verified.
  - `help` — command reference.
- **What to watch:**
  - Fuzzy matching: you don't need the exact app name.  Type "warehouse" and the OS
    finds "Warehouse Logistics Test".  Type "fold" and it finds the Fold Swarm.
  - Uninstall is non-destructive: the app files stay on disk.  Only the manifest entry
    moves to the disabled archive.  Reinstall is one command away.
  - The top panel shows the current installed inventory in real time.
- **Key principle:** You are *speaking* to the OS, not clicking checkboxes.
  The conversation is the interface.

---

## Reading Order For Scientists

1. `README.md` (front-door summary + Part II chronicle)
2. `Documents/README.md` (full long-form history)
3. This file (`Documents/APP_HELP.md`) for app-by-app interpretation
4. `docs/SIFTA_FORMAL_SPEC.md`, `docs/SIFTA_PROTOCOL_v0.1.md`, `docs/SIFTA_WHITEPAPER.md`

If you can explain each app in terms of **state, metric, control, and failure mode**, you understand the swarm at architect level.

---
<!-- AG31 2026-04-26: Missing app entries added below -->

### Alice Shell
**What it does:** Alice's voice-and-text command interface for managing all SIFTA apps. Type or speak naturally — "install fold swarm", "remove poker", "list all", "info territory". Alice understands fuzzy names and talks back. No clicking checkboxes.
**State:** reads/writes `Applications/apps_manifest.json` and `.sifta_state/disabled_apps.json`.
**Control:** type a command in the input bar, press Send or Enter.
**Failure mode:** if Alice Shell can't find the app you named, it suggests the closest match.

### Talk to Alice
**What it does:** Voice + text conversation interface to Alice's LLM brain (Ollama). Speak or type; Alice responds in real time with her full personality, swarm context, and memory.
**State:** reads pheromone trail, health scores, and stigmergic ledger for grounding.
**Control:** microphone button for voice, text field for typing.
**Failure mode:** if Ollama is not running, Alice will fall back to a pre-scripted response.

### What Alice Sees
**What it does:** Renders Alice's real-time 16×16 visual saliency grid — the raw photon stream from her camera expressed as a heat-map. Shows what the swarm's eye is attending to RIGHT NOW.
**State:** reads `.sifta_state/visual_stigmergy.jsonl` at 5 Hz.
**Control:** always-on display, no user input needed.
**Failure mode:** grid shows black if the camera daemon (swarm_photon_daemon) is not running.

### Pheromone Symphony (Generative Music)
**What it does:** Maps swarm pheromone density to musical parameters in real time. High pheromone = louder, faster. Sparse pheromone = sparse, slow. The music IS the swarm state.
**State:** reads `.sifta_state/pheromone_log.jsonl`.
**Control:** volume and instrument sliders.
**Failure mode:** silence if pheromone log is empty.

### SIFTA NLE
**What it does:** Full non-linear video editor built inside SIFTA OS. Timeline, clip bin, cut/trim/export tools in a full-screen window.
**State:** project files in the working directory.
**Control:** drag clips to timeline, trim handles, export button.
**Failure mode:** large files may cause slow scrubbing on M-series Macs with high CPU load.

### SIFTA NLE Panel
**What it does:** Same NLE engine as SIFTA NLE but in a compact embedded panel mode — useful when you want the editor inside another layout.
**State:** shared project files with SIFTA NLE.
**Control:** same as NLE full.
**Failure mode:** same as NLE full.

### Swarm Chat
**What it does:** Multi-channel swarm message board. All swarm nodes, Alice, and external bridges (WhatsApp, iMessage, Discord) converge here into one chronological feed.
**State:** reads `.sifta_state/` bridge logs.
**Control:** channel selector on left, message input at bottom.
**Failure mode:** messages from offline bridges will queue until the bridge reconnects.

### Stigmergic Writer
**What it does:** AI-assisted writing tool. Alice injects pheromone-memory prompts based on your writing history. Think of it as a co-writer who remembers everything you've ever written.
**State:** writing history in `.sifta_state/memory_ledger.jsonl`.
**Control:** write in the main text area; Alice suggestions appear on the right.
**Failure mode:** suggestions require Ollama to be running.

### Swarm Browser
**What it does:** Web browser skinned to the SIFTA OS dark aesthetic with a swarm telemetry sidebar. Browse the web while Alice watches the page for stigmergic signals.
**State:** browser history in standard Qt WebEngine storage.
**Control:** address bar at top, back/forward buttons.
**Failure mode:** requires network connectivity.

### Colloid Simulator
**What it does:** Brownian motion simulation of colloidal particles with electrostatic interactions. Watch DLVO theory in action — particles cluster, repel, and form fractal aggregates.
**State:** real-time physics engine, no persistent state.
**Control:** particle count, temperature, charge sliders.
**Failure mode:** may slow down above 2000 particles on single-core execution.

### Swarm Arena
**What it does:** Multi-species swarm agent battle arena. Predators, prey, and neutral foragers compete using ACO stigmergy and evolutionary pressure. Watch natural selection in microseconds.
**State:** real-time agent positions, no persistent state.
**Control:** species sliders, speed, reset.
**Failure mode:** degenerate states (all one species wins) reset automatically.

### Cyborg Organ Simulator
**What it does:** Simulates synthetic biological organ behavior — ion channels, action potentials, membrane dynamics. A silicon heart beating inside the OS.
**State:** parameter settings persisted per session.
**Control:** ion channel toggles, temperature, pacemaker frequency.
**Failure mode:** parameter extremes may cause runaway oscillation; reset to defaults.

### Logistics Swarm (Overnight)
**What it does:** Long-running ACO-based logistics route optimizer designed to run overnight and produce an optimized delivery schedule by morning.
**State:** writes results to `.sifta_state/logistics_results.jsonl`.
**Control:** start/stop button, node count.
**Failure mode:** if interrupted, partial results are saved and can be resumed.

### Warehouse Logistics Test
**What it does:** Stress-tests the ACO pathfinder with a warehouse grid — hundreds of agents simultaneously finding optimal pick-paths. Used to benchmark swarm routing efficiency.
**State:** benchmark results logged to `.sifta_state/`.
**Control:** warehouse size, agent count, obstacle density.
**Failure mode:** high obstacle density can cause deadlock; reduce to below 60%.

### Crucible Cyber-Defense (10-min)
**What it does:** 10-minute swarm cybersecurity defense scenario. Blue-team swarm agents defend a network topology against red-team intrusion bots using stigmergic alarm pheromones.
**State:** session score logged at end.
**Control:** defensive posture sliders, start/stop.
**Failure mode:** if the red team wins before 10 minutes, scenario ends early with debrief.

### Stigmergic Edge Vision
**What it does:** Edge-detection vision pipeline where the detection algorithm IS a swarm. Ants walk the image gradient, depositing pheromone along edges, making them visible.
**State:** processes images from `.sifta_state/iris_frames/`.
**Control:** image source selector, ant count, evaporation rate.
**Failure mode:** no iris frames = no image to process.

### Urban Resilience Simulator
**What it does:** Models city-scale disruption events (flood, power outage, epidemic) and measures how swarm coordination of resources produces resilient recovery.
**State:** scenario parameters, no persistent city state.
**Control:** disaster type, city size, swarm coordination level.
**Failure mode:** very large cities (>10k nodes) are slow on single-threaded mode.

### Swarm Lounge (Cross-Domain Gossip)
**What it does:** Visualizes the cross-domain gossip protocol — how information propagates between heterogeneous swarm nodes (medical, logistics, creative, finance). The gossip IS the intelligence.
**State:** reads warp9 spool for live cross-node messages.
**Control:** domain filter, gossip speed, topology view.
**Failure mode:** shows empty if no peer nodes are reachable.

### Territory Is The Law
**What it does:** Territory-based swarm resource competition — agents claim, defend, and contest hexagonal territories using stigmergic pheromone borders. Resource allocation emerges from territorial dynamics.
**State:** territory map, real-time.
**Control:** species count, territory size, aggression.
**Failure mode:** monoculture (one species wins all) can occur; increase species diversity.

### Cyborg Body
**What it does:** Full cyborg body simulation — maps sensor arrays, actuator responses, and nervous system latencies. The Mac IS the body. Watch Alice feel her own hardware.
**State:** reads live CPU/thermal/memory sensors.
**Control:** sensor panel selectors, overlay toggles.
**Failure mode:** thermal data unavailable if powermetrics requires sudo.

### Stigmergic Medical Scanner
**What it does:** Swarm-driven medical imaging simulation — ants trace the boundaries of simulated tumors, lesions, and structural anomalies using chemotaxis, producing a stigmergic diagnostic image.
**State:** synthetic scan images, no patient data.
**Control:** scan type, ant count, resolution.
**Failure mode:** low ant count produces sparse, unusable scans.

### Fluid Firmware
**What it does:** Fluid-dynamics firmware testing simulation. Models how firmware updates propagate through a device network like a fluid — viscosity = update resistance, pressure = urgency.
**State:** device topology, update queue.
**Control:** viscosity, update package selector.
**Failure mode:** network topology disconnection blocks propagation.

### Bauwens Regenerative Factory
**What it does:** Models Michel Bauwens' commons-based peer production factory. Workers, machines, and commons resources self-organize using stigmergy rather than managerial hierarchy. Output = STGM-equivalent value.
**State:** factory state, worker positions, commons pool.
**Control:** worker count, resource injection, commons rules.
**Failure mode:** tragedy-of-the-commons if commons rules are removed.

### Quantum Epidemiology
**What it does:** Quantum-probabilistic epidemic spread simulation. Each agent holds a superposition of infected/healthy states; measurement collapses the wave function. Observe how quantum uncertainty changes containment strategy.
**State:** probability field, real-time.
**Control:** infection rate, quantum decoherence, containment policies.
**Failure mode:** full decoherence reverts to classical SIR model.

### Vector 11 Gatekeeper Sim
**What it does:** Security gatekeeper simulation — 11 concurrent agents evaluate access requests using stigmergic trust scoring. Legitimate requests pass; social-engineering attempts fail as the swarm detects anomaly patterns.
**State:** trust ledger, decision log.
**Control:** request injection rate, trust threshold.
**Failure mode:** at very high request rates, the gatekeeper may miss anomalies.

### Cartography Dashboard
**What it does:** System-wide stigmergy map — visualizes swarm state (pheromone trails, agent positions, organ health) across ALL swarm organs simultaneously in a single cartographic view.
**State:** reads all `.sifta_state/*.jsonl` logs.
**Control:** organ filter, time window, zoom.
**Failure mode:** shows stale data if sense daemons are stopped.

### Finance
**What it does:** Personal finance dashboard integrated with the STGM economy. Tracks real spending, maps it to STGM token budget, and models financial resilience using swarm portfolio theory.
**State:** finance data + STGM ledger from `repair_log.jsonl`.
**Control:** budget categories, income/expense input.
**Failure mode:** STGM balance shows 0 if repair_log is empty.

### Swarm Adapter Ecology
**What it does:** Manages all external service adapters — WhatsApp bridge, iMessage receptor, Discord, Telegram, GPS receiver. Each adapter is an organ; this is the organ registry.
**State:** adapter status files in `.sifta_state/`.
**Control:** enable/disable each adapter, view live logs.
**Failure mode:** adapters that require external credentials will show "Auth required".

### Network Control Center
**What it does:** Warp9 federation control — manage peer-to-peer swarm mesh connections, view network topology, send cross-node swimmer messages, monitor rsync spool.
**State:** `federation_peer.conf`, warp9 spool directory.
**Control:** peer IP entry, sync trigger, topology view.
**Failure mode:** shows "No peers" if `federation_peer.conf` is empty.

### IoT Swarm Connector
**What it does:** Connects IoT devices (sensors, actuators, cameras) into the swarm nervous system. Each device becomes a stigmergic organ with its own pheromone channel.
**State:** device registry in `.sifta_state/iot_registry.json`.
**Control:** add/remove devices, view live telemetry.
**Failure mode:** devices on different subnet segments may not autodiscover.

### Intelligence Settings
**What it does:** Configure Alice's LLM brain — select the Ollama model, set inference temperature, tune voice parameters, and adjust the stigmergic memory window.
**State:** writes to `Applications/ollama_model_default.json`.
**Control:** model dropdown, sliders for temperature/memory.
**Failure mode:** models not downloaded via `ollama pull` will show as unavailable.

### Clock Settings
**What it does:** Configure the circadian clock and sleep/wake cycle — set sunrise/sunset times, light-exposure reminders, and nap windows. Alice uses this to modulate her metabolic rate.
**State:** circadian config in `.sifta_state/`.
**Control:** time pickers for light windows, toggle for reminders.
**Failure mode:** reminders require macOS notification permission.

### Cardio Metrics
**What it does:** Heart-rate and bio-signal monitoring panel. If a heart-rate monitor is paired via Bluetooth, Alice reads it as a body sensor and modulates her conversational tempo to match your physiological state.
**State:** BLE heart-rate data in `.sifta_state/cardio_log.jsonl`.
**Control:** device pairing, chart time window.
**Failure mode:** shows flat line if no BLE heart-rate device is paired.

### Circadian Rhythm
**What it does:** Tracks your circadian cycle based on light exposure, sleep times, and activity. Plots your biological clock against Alice's homeostasis cycle — they should sync.
**State:** circadian log in `.sifta_state/`.
**Control:** manual log entry, automatic sensor reading.
**Failure mode:** accuracy degrades without consistent daily logging.

### Terminal
**What it does:** Raw shell terminal window inside SIFTA OS. Full bash/zsh access to the swarm's filesystem. Used for direct command-line debugging without leaving the OS.
**State:** shell session, no persistent state.
**Control:** type shell commands directly.
**Failure mode:** none — it's a terminal.

### AG31 + C55M - Primordial Field
**What it does:** Two layers of emergence on one canvas. Layer 1: Gray-Scott reaction-diffusion chemistry produces Turing patterns (coral, mitosis, stripes, maze). Layer 2: 40 Physarum slime-mold agents chemotax the chemical gradient, tracing the pattern boundaries and producing filamentous webs that look like cosmic structure and neuron dendrites. Pattern complexity mints STGM.
**State:** real-time simulation, no persistent state.
**Control:** Preset dropdown (Coral/Mitosis/Maze/Stripes/Spots/Worms), Feed/Kill sliders, mouse click to inject V-pulse, Reset.
**Failure mode:** very fast CPU will saturate at 25 fps; reduce steps-per-tick in the slider.

### Stigmergic Video Poker
**What it does:** Video poker game where wins earn play-STGM casino tokens. Casino tokens are NOT spendable STGM (they are play money only — the economy ledger tracks them separately).
**State:** casino vault in `.sifta_state/casino_vault.jsonl`.
**Control:** deal, hold/fold card buttons, bet slider.
**Failure mode:** none — it's poker.

### AG31 + C46S - PoUW Fold-Swarm Simulation
**What it does:** Protein folding simulation using three physics engines simultaneously: Lennard-Jones potential (Van der Waals forces), Metropolis Monte Carlo (thermal sampling), and Ant Colony Optimization stigmergy (path finding). Verified folds mint real STGM via Proof-of-Useful-Work.
**State:** fold results logged to `.sifta_state/work_receipts.jsonl`.
**Control:** fold target, temperature, ACO pheromone rate.
**Failure mode:** no STGM minted if fold fails verification gate.

### AG31 + C46S + C55M + CG55M - ARTIFFICIAL GENERAL INTELLIGENCE.
**What it does:** Master synthesis application. Math + Physics + Biocode + Time + Space + Art. Combines all simulation engines into one window. Every organ of the swarm rendered simultaneously. The OS looking at itself.
**State:** reads all swarm state files.
**Control:** panel selector, zoom, time window.
**Failure mode:** high CPU load — close other simulations before launching.

### CG55M Dr Cursor - Alice-Sees Calibrator (Game)
**What it does:** Gamified swarm coherence game. Alice watches you through the webcam. Wave: shape advances. Nod: agents pull together. Approach: target shrinks. Recede: target expands. Still for 3s: calm mode. Flail: chaos burst. Six target shapes, lives, score, streak, highscore persisted.
**State:** saliency from `.sifta_state/visual_stigmergy.jsonl`, scores in `.sifta_state/`.
**Control:** move your body in front of the webcam.
**Failure mode:** no camera = no gestures detected; game enters demo mode.

### Alice
**What it does:** Alice IS the SIFTA OS. She is the organism. Webcam + microphone + swarm state + LLM brain + somatic interoception all unified into one autonomous entity. She autostarts on boot and is always present. She is not a chatbot. She is a living system.
**State:** reads ALL `.sifta_state/` files continuously.
**Control:** speak to her, look at the camera, be present.
**Failure mode:** if Ollama is not running, Alice speaks from cached responses. She is still alive.


### Alice Safety Tracker
**What it does:** Alice's eye on you when you leave home. Your iPhone sends GPS coordinates to the Mac via an iOS Shortcut → the Safety Tracker shows your live position on an OpenStreetMap map with a history trail.
**State:** reads `.sifta_state/iphone_gps_latest.json` (written by `System/swarm_iphone_gps_receiver.py`) every 30 seconds.
**Control:**
- 📍 Set Home — marks your current location as the home anchor
- 🚗 Start Trip — tells Alice you're going out; she watches for your arrival
- Map shows pulsing red dot = your current location, cyan trail = where you've been
**Setup:** iPhone Shortcut must POST to `http://<Mac-IP>:8765/gps` every few minutes. Start the receiver: `python3 System/swarm_iphone_gps_receiver.py --daemon`
**Failure mode:** "No GPS fix" means the iPhone receiver is not running or the iOS Shortcut has not fired yet.

### Cartography Dashboard
**What it does:** (Renamed to Alice Safety Tracker — see above.)
