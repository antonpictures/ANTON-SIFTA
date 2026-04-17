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
