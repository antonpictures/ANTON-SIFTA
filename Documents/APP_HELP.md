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

### SIFTA NLE (Video Editor)
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

### Swarm Browser
- **Purpose:** The web is hostile territory. The Swarm enters it for you. Instead of rendering pretty HTML for human eyes, the browser deploys 70 swimmers into the raw DOM tree to map, harvest, and quarantine.
- **State variables:** DOM graph (DomNode tree with pheromone_good/pheromone_bad per node), 70 swimmers (4 species), entity list, quarantine list, clean text corpus.
- **What to watch:**
  - **DOM graph** — radial tree visualization. Green nodes = content. Red = hostile (ads, trackers, scripts). Blue = links. Gold = media. Gray = structural.
  - **Pheromone trails** — green glow on edges = useful paths. Red glow = hostile paths. Swimmers follow green, avoid red.
  - **Swimmers** — colored dots crawling the tree. They physically move between parent/child nodes.
  - **Quarantine panel** — every tracker, ad iframe, and hostile link the swarm neutralized.
  - **Entity panel** — extracted names, dates, prices, emails from content nodes.
  - **Clean Text panel** — article text stripped of noise, ready for consumption.
  - **STGM counter** — tokens earned for useful extractions and tracker kills.
- **Swimmer species:**
  - **SkeletonMapper** (25) — maps div structure, marks content vs noise nodes.
  - **EntityHarvester** (20) — dives into p/h1-h6, extracts text + named entities via regex NLP.
  - **LinkSentinel** (15) — follows a[href], checks domains against hostile pattern database.
  - **MediaExtractor** (10) — finds img/video URLs, flags tracking pixels.
- **Controls:** URL bar + DEPLOY (fetch live page) or DEMO (synthetic test DOM with embedded ads/trackers).
- **Key principle:** Browsing is territory mapping. The swarm treats every DOM node as a location to explore, classify, and either harvest or quarantine. STGM is earned for useful work — entity extraction and tracker neutralization. The browser doesn't show you a pretty page; it shows you the nervous system of the page, alive with swimmers.
- **Failure modes:** Fetch timeout on slow sites, DOM too deep (>10k nodes may slow rendering), hostile JavaScript obfuscation (parser sees static HTML only).

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

### Sebastian Batch Editor
- **Purpose:** Batch media operations with proof-of-useful-work accounting.
- **What to watch:** Edit completion, QoS of cuts, STGM-linked utility outputs.
- **Key principle:** Utility-backed compute economics in media workflows.

### Desktop GUI (Legacy)
- **Purpose:** Historical/fallback desktop shell.
- **What to watch:** Compatibility and parity against the current shell.
- **Key principle:** Evolution with fallback continuity.

---

## System

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

---

## Reading Order For Scientists

1. `README.md` (front-door summary + Part II chronicle)
2. `Documents/README.md` (full long-form history)
3. This file (`Documents/APP_HELP.md`) for app-by-app interpretation
4. `docs/SIFTA_FORMAL_SPEC.md`, `docs/SIFTA_PROTOCOL_v0.1.md`, `docs/SIFTA_WHITEPAPER.md`

If you can explain each app in terms of **state, metric, control, and failure mode**, you understand the swarm at architect level.
