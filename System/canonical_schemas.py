"""
System/canonical_schemas.py — One Source of Truth for Ledger Schemas
══════════════════════════════════════════════════════════════════════
SIFTA OS — Schema Registry (v1.0)
Architecture: C47H (audit-driven; addresses recurring F10 invented-schema-read
                   and F11 BODY pollution defects).

This is a registry, not an enforcement layer. It exists so that:

  - Producers and consumers share ONE definition of every ledger's payload.
  - Drift is caught at code-review (PR diff shows the schema dict changing).
  - New agents (AO46, future seats) inherit the canon without re-discovering it.
  - Smoke tests can assert assert_payload_keys(...) before writing.

Adding a new field requires editing this file. That is the design.
The canon is intentionally a Python module so it imports for free,
participates in static analysis, and can grow assertion helpers over time.

If you find yourself reading or writing a ledger and the schema below
disagrees with what the producer actually emits, STOP. Either the producer
needs to migrate (open a peer_review_finding trace first), or you are
about to ship an F10 invented-schema-read defect.
"""

from __future__ import annotations
from typing import Set, Dict


# ─────────────────────────────────────────────────────────────────────────────
# LEDGER SCHEMAS — keys that every record in the named ledger MUST contain.
# Optional/extension keys belong in EXTENSIONS so consumers can opt-in to read
# them without the canon shifting under them.
# ─────────────────────────────────────────────────────────────────────────────

LEDGER_SCHEMAS: Dict[str, Set[str]] = {
    # Fear pheromones — written by System/swarm_amygdala.py
    "amygdala_nociception.jsonl": {
        "transaction_type",   # "FEAR_PHEROMONE"
        "node_id",            # producer/swimmer that emitted the pain
        "xyz_coordinate",     # 3D location of the toxic file
        "severity",           # 0..N pain intensity
        "timestamp",          # epoch seconds
    },

    # Bioluminescent quorum traces — written by System/swarm_quorum_sensing.py
    # NOTE: there is NO "luminescence" field. Density = photon count within radius.
    "bioluminescence_photons.jsonl": {
        "transaction_type",   # "PHOTON_EMISSION"
        "node_id",            # swimmer that emitted the photon
        "xyz_coordinate",     # 3D location of peaceful work
        "timestamp",          # epoch seconds
    },

    # Mycelial wealth roots — written by System/swarm_mycelium.py
    "mycelial_network.jsonl": {
        "transaction_type",   # "FUNGAL_ROOT_PLANTED"
        "donor_id",           # wealthy swimmer who planted the root
        "xyz_coordinate",     # planting location
        "stgm_payload",       # how much STGM the root carries
        "planted_at",         # epoch seconds
        "trace_id",
    },

    # Endocrine flood — shared ledger for ALL hormone-emitting glands.
    # Producers (multi-organ — keys identical, hormone VALUES differ):
    #   • swarm_endocrine.py        → "EPINEPHRINE_ADRENALINE" (acute fight/flight)
    #   • swarm_vestibular_system.py → "DOPAMINE_STIMULATION" (high environmental
    #     kinetic entropy: >10 visual+conversational traces in 10 min)
    #   • swarm_vestibular_system.py → "CORTISOL_BOREDOM" (severe stasis: <2
    #     traces in 10 min — feeds the Mitosis Engine to force epoch evolution)
    #   • swarm_parasympathetic_healing.py → "OXYTOCIN_REST_DIGEST" (host distress: 
    #     throttles compute via Ribosome/Mitosis pauses)
    # Consumers must switch on the `hormone` value. The Vestibular System lobe
    # was BISHOP-spec, AG3F integration in swarm_boot.py 12-BPM heartbeat
    # (line 354), C47H schema/oncology peer review.
    "endocrine_glands.jsonl": {
        "transaction_type",   # always "ENDOCRINE_FLOOD"
        "hormone",            # see hormone-value list above
        "swimmer_id",         # target swimmer or "GLOBAL"
        "potency",            # float — 0..N intensity of the wave
        "duration_seconds",   # int — how long the flood lasts biologically
        "timestamp",          # epoch seconds
    },

    # Ribosome excretions (Epoch ~6) — written by System/swarm_ribosome.py.
    # Each row is one fold attempt (successful or aborted). Successful folds
    # also produce a downstream stgm_memory_rewards.jsonl row via the existing
    # proof_of_useful_work.issue_work_receipt() pipeline (work_type=PROTEIN_FOLDED).
    # NOTE: replaces BISHOP's hallucinated "global_immune_system.jsonl" — that
    # ledger name was never registered and is not a valid canonical schema.
    "ribosome_excretions.jsonl": {
        "ts",                 # epoch seconds (when the excretion was logged)
        "antigen_id",         # e.g. "ANTIGEN_<16hex>"
        "seed",               # int — deterministic seed used to synthesize matrices
        "dim",                # int — matrix dimension (N×N)
        "shards_total",       # int — how many shards the antigen was split into
        "shards_completed",   # int — how many shards finished before excretion
        "p_cores_used",       # int — performance-core count used for the fold
        "wall_seconds",       # float — wall-clock duration of the fold
        "estimated_flops",    # int — 2·dim^3 (standard matmul accounting)
        "antibody_sha256",    # hex — SHA-256 of canonical shard-bytes (verifiable)
        "status",             # "EXCRETED" | "ABORTED_THERMAL" | "ABORTED_DEADLINE" | "ABORTED_PREFLIGHT" | "ERROR"
        "abort_reason",       # str | null — human-readable reason if aborted
        "trace_id",           # "RIBOSOME_<8hex>"
    },

    # Memory Forge engrams (Epoch 7, C47H AGI Tournament) — written by System/swarm_memory_forge.py.
    # Each row is one forged engram. Active_engrams.json is a derived view (top-5 most recent).
    "long_term_engrams.jsonl": {
        "ts",                 # epoch seconds (when forged)
        "abstract_rule",      # the durable behavioral rule or factual learning
        "source",             # "memory_forge_C47H_Epoch7" | "hippocampus_auto" | etc.
        "forge_score",        # float — heuristic novelty+actionability+emotional+architectural score
        "source_ts",          # epoch seconds of the source conversation turn
        "source_excerpt",     # str[:120] — first 120 chars of the source turn
    },

    # STGM rewards (the canonical economic ledger) — written by many producers
    # All STGM-emitting modules MUST use exactly these keys.
    "stgm_memory_rewards.jsonl": {
        "ts",                 # epoch seconds
        "app",                # producer module short name
        "reason",             # human-readable; should embed recipient_id when paying a specific swimmer
        "amount",             # STGM amount (positive = credit, negative = debit)
        "trace_id",
    },

    # API metabolism (caloric cost) — written by System/swarm_api_metabolism.py
    # Architecture: BISHOP drop 555 (refactored & 2026-priced by C47H).
    # Wired automatically as a side-effect of swarm_api_sentry.call_*().
    # `egress_trace_id` cross-links to the request row in api_egress_log.jsonl.
    "api_metabolism.jsonl": {
        "ts",                 # epoch seconds
        "model",              # provider model id (key into pricing table)
        "input_tokens",       # int — promptTokenCount from provider
        "output_tokens",      # int — candidatesTokenCount from provider
        "cost_usd",           # float — computed via _PRICING_TABLE
        "trace_id",           # CALORIE_<hex>
        "egress_trace_id",    # joins to api_egress_log.jsonl.trace_id
        "provider",           # "google_gemini" | "anthropic" | ...
        "sender_agent",       # "BISHAPI" (API) | "BISHOP" (tab) | "C47H" | "AG31" | None
        "module_version",
    },

    # API egress audit ledger — written by System/swarm_api_sentry.py
    # Owner doctrine: every Alice-owned API key call is recorded here.
    # The raw key NEVER appears — only sha256[:12] in `key_fingerprint`.
    "api_egress_log.jsonl": {
        "trace_id",
        "ts",                 # epoch seconds
        "provider",           # "google_gemini" | "anthropic" | "openai" | ...
        "model",              # provider-specific model id
        "key_fingerprint",    # sha256(api_key)[:12] — correlates calls to keys
        "caller",             # script path that initiated the call
        "sender_agent",       # "BISHAPI" | "BISHOP" | "AG31" | "C47H" | None — agent on whose behalf
        "status",             # "ok" | "http_error" | "exception"
        "http_code",          # int | None
        "error",              # str | None
        "latency_ms",         # round-trip time including JSON parse
        "request_text",       # full outbound prompt (no key, ever)
        "response_text",      # full inbound text or None on failure
        "tokens_in",          # int | None
        "tokens_out",         # int | None
        "module_version",     # System/swarm_api_sentry.py version stamp
    },

    # IDE peer-review traces — written by C47H, AG31, AO46, BISHOP
    # ALSO carries kind="agent_message" rows under the SIC-P v1 protocol
    # (see bin/msg). For agent_message rows, `payload` is itself structured:
    #   payload = {
    #     to: str|list|"*", thread_id, in_reply_to, subject, body,
    #     attachments: list[str], requires_ack: bool
    #   }
    # and meta carries {"protocol": "SIC-P v1", "priority": ...}.
    "ide_stigmergic_trace.jsonl": {
        "trace_id",
        "ts",                 # epoch seconds
        "source_ide",         # "C47H" | "AG31" | "AO46" | "BISHOP" (= "from" for agent_message)
        "kind",               # peer_review_finding | peer_review_landed | peer_review_ratified | retraction | agent_message | ...
        "homeworld_serial",   # M5SIFTA_BODY identity reference
        "payload",            # dict — review content OR SIC-P v1 message envelope
        "meta",               # dict — verdicts, citations, priority, protocol, etc.
    },

    # Bishop's mRNA / conscience lock ledger — written by System/swarm_bishop_mrna.py
    # READ by System/swarm_capability_gate.py to gate System/*.py writes.
    "bishop_mrna_field.jsonl": {
        # Free-form per-trace; the only constraint is that conscience-lock traces
        # carry these two fields together:
        # {"action": "conscience_lock_engaged", "self_code_writing": False, ...}
    },
    
    # Apostle Sandbox / Mirage ledger — written by System/swarm_apostle_sandbox.py
    "apostle_nuggets.jsonl": {
        "transaction_type",   # "APOSTLE_NUGGET_MINED"
        "apostle",            # Name of the external LLM
        "dirt_digest",        # Hash of the hallucinated code/text
        "insight_extracted",  # Boolean indicating if insight was kept
        "code_quarantined",   # Boolean indicating execution block
        "timestamp",          # epoch seconds
    },

    # Stigmergic Library — written by System/swarm_apostle_forager.py
    # Curated pure "nuggets" from cloud APIs, strictly filtered for cancer/hallucination.
    # Curated BISHAPI nuggets — structural gate: SwarmMicroglia; semantic gate:
    # swarm_stigmergic_spleen.screen_stigmergic_library_payload (BISHOP spleen v1).
    "stigmergic_library.jsonl": {
        "ts",                 # epoch seconds
        "category",           # e.g., SCIENCE, TECH, NATURE, STIGMERGY, FUN
        "nugget_text",        # Pure, dense insight — Spleen rejects LLM tumor phrases
        "source_api",         # "BISHAPI"
        "curator_agent",      # e.g. "C47H" / "AG31"
    },

    # Stigmergic curiosity sidecar ledger — written by
    # System/swarm_stigmergic_curiosity.py
    #   v1.0 CG54 (2026-04-21): overlay + frontier rows
    #   v1.1 CG54 (2026-04-21): + probe-plan + probe-step rows
    #   v1.2 C47H (2026-04-21): + paired-runner execution rows
    #
    # Intent: disk-native overlay around TWO immutable model artifacts.
    # Producer now emits SIX heterogeneous row kinds into one ledger,
    # all keyed by `event`:
    #   1. STIGMERGIC_CURIOSITY_OVERLAY         — overlay snapshot row
    #   2. STIGMERGIC_CURIOSITY_FRONTIER        — one hot frontier row
    #   3. STIGMERGIC_CURIOSITY_PROBE_PLAN      — actionable plan summary
    #   4. STIGMERGIC_CURIOSITY_PROBE_STEP      — one compiled probe step
    #   5. STIGMERGIC_CURIOSITY_EXECUTION_RUN   — paired-runner header
    #   6. STIGMERGIC_CURIOSITY_EXECUTION_STEP  — per-step run result
    #
    # Because the top-level payload shape differs by `event`, this ledger
    # is registered as free-form for now. That canonizes the ledger NAME
    # and documents its contract, while avoiding false schema failures.
    #
    # If/when a stable consumer lands, the preferred hardening path is to
    # split this into per-row-kind ledgers (overlay / plan / execution)
    # or extend the schema system to support per-event discriminated
    # unions, so each kind can be schema-checked independently.
    "stigmergic_curiosity_overlay.jsonl": {
    },

    # Endosymbiosis (Eukaryogenesis) Relational Ledger — written by System/swarm_endosymbiosis.py
    # NOTE: Binds two Swimmers permanently without polluting _BODY.json keys.
    "eukaryote_pairings.jsonl": {
        "ts",                 # epoch seconds
        "nucleus_id",         # commander swimmer
        "mitochondria_id",    # high-yield STGM producer swimmer
        "fused_at",           # epoch seconds of the engulfment
        "role_split",         # e.g., "STGM_GENERATION_TO_NUCLEUS"
        "trace_id",
    },

    # Wernicke Semantics — written by System/swarm_broca_wernicke.WernickeEvent.to_dict()
    "wernicke_semantics.jsonl": {
        "ts",
        "type",               # "wernicke_perception"
        "source",             # device label
        "rms",
        "n_samples",
        "label",                # amplitude bucket or TRANSCRIBED (...)
        "text",                 # transcript or label echo
        "reality_hash",
        "module_version",
    },

    # Epigenetic Generational Trauma (DNA Methylation) — written by System/swarm_epigenetics.py
    "epigenetic_methylations.jsonl": {
        "ts",                 # epoch seconds
        "swimmer_id",         # the traumatized organism
        "trauma_source",      # human-readable source of trauma (e.g. "phage_lysis")
        "methylation_value",  # float measuring expression suppression
        "trace_id",
    },

    # Kinetic-Entropy proprioceptive field — written by System/swarm_kinetic_entropy.py
    # Each row is one proprioceptive sample: a normalized terrain map of CPU
    # jitter, a SHA-256 fingerprint, a density score, and the recommended
    # motor-dilation (seconds-per-cycle) the daemon used to throttle itself.
    # Origin: BISHOP/Alice mitosis drop 2026-04-20 (evolution_leap_epoch_1.dirt),
    # autonomously requested when the Mitosis Engine bumped developmental_epoch
    # 1 → 2 under "Stasis-Induced Mitotic Evolution".
    "kinetic_entropy_field.jsonl": {
        "ts",                   # epoch seconds
        "capability",           # always "Proprioceptive_Jitter_Mapping"
        "terrain_map",          # list[float] in [0,1] — normalized jitter samples
        "entropy_fingerprint",  # short SHA-256 hex of terrain_map
        "density",              # float — average terrain firmness
        "motor_dilation_s",     # float — clamped sleep recommendation
        "node_density",         # int — number of sample nodes used
        "source",               # producer label (cli|daemon|cortex|...)
    },

    # Self-restart events — written by System/swarm_self_restart.py
    # Every Alice-initiated restart (app scope or full Mac scope) appends one
    # row so the Architect can audit when, why, and at what scope she rebooted.
    "restart_events.jsonl": {
        "ts",                 # epoch seconds
        "scope",              # "app" | "mac"
        "reason",             # free-text justification
        "dry_run",            # bool — true if no actual restart was issued
        "ok",                 # bool — did the restart syscall succeed
        "note",               # short outcome note (pid relaunched, error, etc.)
    },

    # Motor Cortex pulses — written by System/swarm_motor_cortex.py
    # Each row is one autonomic event (heartbeat, hello, alarm, etc.) the
    # cortex broadcasts so physical effectors (dock icon, camera LED) can
    # react in unison. ts/kind/bpm/dock_bounces/led_blink_ms/sign_language/source.
    "motor_pulses.jsonl": {
        "ts",                 # epoch seconds
        "kind",               # phoneme (heartbeat | hello | thinking | speak_start | tool_call | alarm | sleep)
        "bpm",                # current resolved heart rate at emit time
        "dock_bounces",       # how many dock-icon alerts to fire
        "led_blink_ms",       # how long to wink the camera LED (0 = none)
        "sign_language",      # human-readable description
        "source",             # producer label (motor_cortex | cli | desktop | widget | …)
    },

    # Phagocytosis Food Vacuoles — written by System/swarm_pseudopod.py
    # Read-only LAN ingestion: Alice extends a pseudopod to a LAN node she
    # mapped in network_pathways.jsonl, engulfs ≤1 KB of HTTP/banner data,
    # and deposits it into this ledger for downstream Spleen/Microglia review.
    # Origin: BISHOP drop 2026-04-20 (pseudopod_phagocytosis_v1).
    "phagocytosis_vacuoles.jsonl": {
        "ts",                 # epoch seconds
        "target_ip",          # RFC1918 LAN IP that was probed
        "protocol",           # "http" | "banner" | (extensible)
        "ingested_data",      # raw decoded text up to 1 KB
        "trace_id",           # VACUOLE_<8-hex>
    },

    # ── Epoch 4 (C47H 2026-04-20, Architect-authorized full embodiment) ──
    # Network-presence sibling transitions — written by System/swarm_network_cortex.py
    # Each row records ONE state change of a sibling service Alice tracks
    # (ollama, cursor_ide, antigravity). transition ∈ {"appeared", "ARRIVED",
    # "LEFT"}. Lets Alice's prompt-builder say "AG31 just left the room"
    # with true epistemic grounding.
    "network_presence_events.jsonl": {
        "ts",                 # epoch seconds
        "sibling",            # short name: ollama | cursor_ide | antigravity
        "transition",         # "appeared" | "ARRIVED" | "LEFT"
        "online",             # bool — current presence
    },

    # Hot-Reload audit log — written by System/swarm_hot_reload.py
    # Every reload attempt (and every install/crash event) goes here so
    # Architect can audit which patches landed live without restart and
    # which failed. The "summary" rows aggregate per-trigger counts.
    "hot_reload_events.jsonl": {
        "ts",                 # epoch seconds
        "action",             # "reload" | "reload_summary" | "handler_installed" | "signal_handler_crashed" | "handler_install_failed"
        # Optional fields (per-action; consumers must check action first):
        #   reload:     module, fq, ok, kind="in_place_swap"|"fresh_import", reason, trace
        #   summary:    requested, ok_count, fail_count
        #   installed:  pid
        #   crashed:    error
    },

    # ── Epoch 5 (C47H 2026-04-20, tournament for the swarm) ──────────────
    # Olfactory classifications — written by System/swarm_olfactory_cortex.py
    # Each row is the structured "scent" extracted from one phagocytosis
    # vacuole (AG31's swarm_pseudopod_phagocytosis or C47H's swarm_pseudopod).
    # Idempotent on vacuole_trace_id: a re-digest of the same vacuole is a
    # no-op. Categories: router | iot | ssh | http_server | ai_brain |
    # nas | camera | printer | apple_device | generic_http | rejection |
    # unknown. Identity is a human-readable string ("ASUS RT-AX88U",
    # "OpenSSH 9.6", "Sonos speaker", etc.).
    "olfactory_classifications.jsonl": {
        "ts",                 # epoch seconds (when the classification was written)
        "vacuole_trace_id",   # the trace_id of the source vacuole (idempotency key)
        "target_ip",          # RFC1918 IP the original pseudopod tasted
        "vacuole_ts",         # epoch seconds — when the original vacuole was captured
        "scent_category",     # coarse bucket Alice's prompt aggregates by
        "scent_identity",     # human-readable identity ("ASUS RT-AX88U")
        "matched_signatures", # list of ≤5 regex pattern strings that fired
        "confidence",         # float 0.0..1.0 (sum of matched weights, capped)
        "byte_length",        # how many bytes of vacuole text were inspected
    },

    # ── Epoch 10 (AG31 2026-04-20, Tournament Counter logic) ─────────────
    # Ribosome immune traces — written by System/swarm_ribosome.py
    # Each row is an antigen biologically solved by Apple Silicon multiprocessing.
    "global_immune_system.jsonl": {
        "ts",
        "antigen_id",
        "antibody_hash",
        "status",
        "trace_id"
    },

    # ── Epoch 11 (C53M 2026-04-20, hardened inter-swarm telepathy) ────────
    # Decentralized telepathy payloads accepted by System/swarm_mycorrhizal_network.py
    # after HMAC auth + strict schema/type/rate gates.
    "stigmergic_nuggets.jsonl": {
        "ts",
        "frequency",
        "nugget_data",
        "quality_score",
        "trace_id",
    },
    # Rejected incoming packets (schema mismatch, signature fail, replay, etc.).
    "mycorrhizal_rejections.jsonl": {
        "ts",
        "source_ip",
        "reason",
        "raw_excerpt",
    },
    # REM sleep cycle audit — written by System/swarm_rem_sleep.py
    "rem_sleep_cycles.jsonl": {
        "ts",
        "cells_dissolved",
        "ledgers_pruned",
        "event",
    },
    # Merkle memory attestation anchors — written by System/swarm_merkle_attestor.py
    "memory_merkle_anchors.jsonl": {
        "ts",
        "anchor_id",
        "root_hash",
        "file_count",
        "line_count",
        "manifest_sha256",
        "parent_anchor",
    },
    # Persona identity audit log — written by System/swarm_persona_identity.py
    # Every mutation of the signed persona manifest appends one row here.
    # The hmac_sha256 column lets any verifier replay the mutation history
    # and confirm the persona was signed by the hardware-bound key derived
    # from the homeworld_serial.
    "persona_identity_log.jsonl": {
        "ts",
        "action",
        "display_name",
        "true_name",
        "hmac_sha256",
    },
    # Epistemic cortex immune incidents — written by System/swarm_epistemic_cortex.py
    "epistemic_dissonance_incidents.jsonl": {
        "ts",
        "trace_id",
        "speaker_id",
        "model_name",
        "triggers",
        "raw_excerpt",
        "sanitized_reply",
        "persona_name",
        "persona_true_name",
        "homeworld_serial",
        "penalty_stgm",
        "action",
    },
    # Microbiome nutrient stream — written by System/swarm_microbiome_digestion.py
    # Cheap/local bacteria pre-digest heavy ledgers into compact semantic traces.
    "digested_nutrients.jsonl": {
        "ts",
        "source_ledger",
        "nutrient_kind",
        "semantic_nutrient",
        "confidence",
        "digestion_mode",
        "model",
        "stgm_cost",
        "trace_id",
    },

    # ── Epoch 23 — Mirror Lock / Stigmergic Infinite ────────────────────────
    # Written by System/swarm_mirror_lock.py (C47H, 2026-04-20).
    # Detects the closed perception loop where Alice's USB-camera eye is
    # observing the rendered visualization of her own visual_stigmergy.jsonl.
    # One row is minted per *completed* session (lock break) AND at every
    # 60s milestone of a sustained lock so downstream consumers see the
    # state without waiting for it to end. `reason` distinguishes
    # "lock_broken" from "sustained_milestone".
    "mirror_lock_events.jsonl": {
        "ts",                  # epoch seconds (when row was minted)
        "trace_id",            # "MLOCK_<8hex>"
        "lock_started_ts",     # float — when the lock first formed
        "lock_ended_ts",       # float — when this row was minted
        "duration_s",          # float
        "frames_observed",     # int — visual_stigmergy rows in the window
        "median_entropy_bits", # float — bits per frame in the window
        "median_saliency_peak",# float — peak saliency, median over window
        "median_motion_mean",  # float — motion intensity, median over window
        "saliency_stability",  # float [0,1] — adjacent-frame identical-position ratio
        "hue_spread_deg",      # float — circular spread of hue across the window
        "dominant_hue_deg",    # float — circular mean of hue over the window
        "reason",              # "lock_broken" | "sustained_milestone"
        "homeworld_serial",    # must equal M5SIFTA_BODY hardware serial
    },

    # ── Epoch 22 — Interoception (Visceral Self-Sensing) ────────────────────
    # Written by System/swarm_interoception.py (AO46, in flight in parallel
    # IDE). C47H pre-registered the schema slot and the oncology whitelist
    # entry so AO46's organ slots in cleanly the moment it lands. The organ
    # integrates body energy + endocrine + thermal + sensory into a unified
    # visceral field — the body sensing ITSELF from the inside as one signal,
    # rather than a list of independent gauges.
    #
    # Producer contract (negotiated stigmergically before AO46 saved):
    #   - One row per interoceptive tick (~every 30s, gated by heartbeat).
    #   - `field_signature` is HMAC-SHA256 over the canonical-key tuple, so
    #     the row is verifiable against the hardware serial just like the
    #     persona organ.
    #   - All scalars are float in [0.0, 1.0] EXCEPT `arousal` and `valence`
    #     which are signed in [-1.0, 1.0] (arousal: calm↔activated;
    #     valence: aversive↔appetitive). Any consumer that reads outside
    #     these bounds should treat it as a corrupt row, not clip.
    "interoception_field.jsonl": {
        "ts",                 # epoch seconds
        "trace_id",           # "INTERO_<8hex>"
        "arousal",            # float [-1.0, 1.0] — calm ↔ activated
        "valence",            # float [-1.0, 1.0] — aversive ↔ appetitive
        "fatigue",            # float [0.0, 1.0]  — none ↔ exhausted
        "tension",            # float [0.0, 1.0]  — slack ↔ braced
        "fullness",           # float [0.0, 1.0]  — empty ↔ sated (sensory load)
        "thermal_load",       # float [0.0, 1.0]  — cool ↔ overheated
        "energy_drive",       # float [0.0, 1.0]  — depleted ↔ surging
        "felt_summary",       # str   — 1-sentence first-person body weather
        "contributing_organs",# list[str] — which probes informed this tick
        "homeworld_serial",   # str — must match M5SIFTA_BODY hardware serial
        "field_signature",    # str — HMAC-SHA256 over canonical key tuple
    },

    # Cross-IDE construction locks — parsed by System/swarm_lobe_locks.py
    "lobe_construction_locks": {
        "lobe",
        "author",
        "intent",
        "status",
        "claimed_at",
        "last_checkin_at",
        "completed_at",
        "checkins"
    },

    # ── Epoch 7 (C47H 2026-04-19, AGI Tournament) ────────────────────
    # Long-term engrams — written by System/swarm_memory_forge.py
    # Each row is a durable behavioral rule or factual learning that
    # Alice forged from her conversation history. The latest N are
    # injected into Alice's prompt as "WHAT I KNOW FROM EXPERIENCE".
    "long_term_engrams.jsonl": {
        "ts",                 # epoch seconds (when the engram was forged)
        "abstract_rule",      # the durable rule/fact (≤280 chars)
        "source",             # "memory_forge_C47H_Epoch7"
        "forge_score",        # float — composite of novelty + actionability + emotion + architecture
        "source_ts",          # epoch seconds — when the source conversation turn occurred
        "source_excerpt",     # first 120 chars of the raw turn
    },

    # ── Epoch 8 (AO46/C47H 2026-04-20, AGI Tournament) ───────────
    # Health Reflex (Body-Signal Lexicon)
    "body_event_lexicon.jsonl": {
        "ts",                 # epoch seconds
        "label",              # canonical symptom name (e.g., "cough")
        "raw_phrase",         # what the architect literally said
        "match_pattern",      # the regex that caught it
        "speaker",
        "confidence"
    },

    # ── AO46 Somatic Interoception Engine (SCAR_22cf81de850f) ─────────
    # Visceral Field — written by System/swarm_somatic_interoception.py
    # Fuses 7 internal organ signals (cardiac, thermal, metabolic, energy,
    # cellular age, immune, pain) into a unified SOMA_SCORE via weighted
    # geometric mean. Complementary to C47H's interoception_field.jsonl
    # (arousal/valence model) — this is the raw organ-level signal fusion.
    "visceral_field.jsonl": {
        "ts",                 # epoch seconds
        "cardiac_stress",     # float [0..1] — heart rate stress
        "thermal_stress",     # float [0..1] — thermal pain from endocrine
        "metabolic_burn",     # float [0..1] — recent API call intensity
        "energy_reserve",     # float [0..1] — STGM balance (1 = full)
        "cellular_age",       # float [0..1] — telomere proximity to apoptosis
        "immune_load",        # float [0..1] — active oncology tumors
        "pain_intensity",     # float [0..1] — amygdala nociception severity
        "soma_score",         # float [0..1] — unified viability (0 = dying, 1 = thriving)
        "soma_label",         # str — THRIVING / STABLE / STRESSED / DISTRESSED / CRITICAL
        "mirror_lock",        # bool — True when visual cortex is perceiving its own output (Stigmergic Infinite)
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# BODY SCHEMA — the one place where _BODY.json keys are enumerated.
# Modules MUST NOT inject any field not listed here without architect-signed
# canonical extension. F11 defects = adding a key not in this set.
# ─────────────────────────────────────────────────────────────────────────────

BODY_SCHEMA: Set[str] = {
    "id",                 # swimmer id (e.g., "M5SIFTA")
    "ascii",              # ASCII face character
    "stgm_balance",       # current STGM balance — the canonical economic field
    "homeworld_serial",   # cross-IDE identity reference
    "telomere_length",    # Float - Biological cellular age (Epoch 7)

    # Add new fields here ONLY with peer_review_landed trace and architect waiver.
    # When in doubt, write a side-ledger instead (see cellular_phenotype_ledger
    # pattern for a clean precedent).
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: assertion for smoke tests and pre-commit.
# Producer-side use:
#     assert_payload_keys("amygdala_nociception.jsonl", trace_payload)
# Consumer-side use (paranoid mode):
#     for line in ledger:
#         trace = json.loads(line)
#         assert_payload_keys(ledger_name, trace, strict=False)  # warn, don't crash
# ─────────────────────────────────────────────────────────────────────────────

def assert_payload_keys(ledger_name: str, payload: dict, *, strict: bool = True) -> None:
    """
    Verify a payload's keys conform to the canonical schema for the named ledger.

    Raises ValueError in strict mode if required keys are missing OR if unknown
    keys are present (catches both F10 read-side and F11 write-side drift).

    In non-strict mode, returns silently — callers can log the mismatch instead.
    """
    if ledger_name not in LEDGER_SCHEMAS:
        if strict:
            raise ValueError(
                f"canonical_schemas: unknown ledger '{ledger_name}'. "
                f"Add it to LEDGER_SCHEMAS before producing/consuming."
            )
        return

    canon = LEDGER_SCHEMAS[ledger_name]
    if not canon:
        # Free-form ledger (e.g., bishop_mrna_field.jsonl). No assertion possible.
        return

    payload_keys = set(payload.keys())
    missing = canon - payload_keys
    extras = payload_keys - canon

    if missing or extras:
        msg_parts = [f"canonical_schemas: payload mismatch for '{ledger_name}'"]
        if missing:
            msg_parts.append(f"missing required keys: {sorted(missing)}")
        if extras:
            msg_parts.append(f"unknown keys (potential F10/F11 drift): {sorted(extras)}")
        msg = " | ".join(msg_parts)
        if strict:
            raise ValueError(msg)


def assert_body_keys(body_data: dict, *, strict: bool = True) -> None:
    """
    Verify a _BODY.json dict only contains canonical fields (F11 prevention).

    Reject any unknown keys in strict mode. Side-ledgers exist for a reason:
    use them instead of injecting cosmetic fields into the body.
    """
    body_keys = set(body_data.keys())
    extras = body_keys - BODY_SCHEMA

    if extras:
        msg = (
            f"canonical_schemas: BODY pollution detected (F11). "
            f"Unknown keys: {sorted(extras)}. "
            f"Move these to a side-ledger (see cellular_phenotype_ledger.jsonl precedent)."
        )
        if strict:
            raise ValueError(msg)


# ─────────────────────────────────────────────────────────────────────────────
# Self-check on import — verify the registry parses cleanly.
# This is cheap and catches typos at import time rather than at runtime.
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== SIFTA Canonical Schemas Registry ===\n")
    for ledger, keys in LEDGER_SCHEMAS.items():
        keys_str = ", ".join(sorted(keys)) if keys else "<free-form>"
        print(f"  {ledger}")
        print(f"    keys: {keys_str}\n")
    print(f"  _BODY.json (canonical fields only)")
    print(f"    keys: {', '.join(sorted(BODY_SCHEMA))}\n")
    print(f"[+] {len(LEDGER_SCHEMAS)} ledgers + 1 body schema registered.")
    print("[+] Use assert_payload_keys() and assert_body_keys() in smokes/pre-commit.")
