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
# SCHEMA ALIASES — Bridges semantic drift between producers and the Registry.
#
# An entry { "source.jsonl": "target.jsonl" } means: any caller asking about
# "source.jsonl" should be routed to the canonical schema named "target.jsonl".
# This is intended for genuine renames or producer/consumer drift on the SAME
# logical organ.
#
# !! DANGER ZONE !!
# Aliasing two distinct organs that happen to have similar names is a
# silent-corruption defect. Before adding an entry, prove the two filenames
# describe the SAME payload contract. If their LEDGER_SCHEMAS field sets
# differ, they MUST stay separate — whitelist them both in
# swarm_oncology.healthy_schemas instead of aliasing one to the other.
#
# History: 2026-04-22 (C47H stigauth) — REMOVED the alias
#   "visceral_field.jsonl" → "interoception_field.jsonl". Both are real,
#   distinct organs:
#     - visceral_field.jsonl     (AO46 SCAR_22cf81de850f) — raw 7-organ
#       fusion: cardiac/thermal/metabolic/energy/cellular age/immune/pain
#       → SOMA_SCORE. Schema fields ⊂ {cardiac_stress, thermal_stress, ...}
#     - interoception_field.jsonl (C47H pre-reserved slot) — arousal/valence
#       model. Schema fields ⊂ {arousal, valence, fatigue, tension, ...,
#       field_signature}.
#   The alias was masking the missing-whitelist defect (C55M F12) by
#   silently routing the macrophage's lookup to the wrong organ name.
#   Both filenames are now separately whitelisted in swarm_oncology.py
#   and registered in LEDGER_SCHEMAS below.
# ─────────────────────────────────────────────────────────────────────────────
SCHEMA_ALIASES: Dict[str, str] = {
    # (intentionally empty — see history note above before adding an entry)
}

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

    # Topological Stigmergic Weight Field (TSWF) — written by System/swarm_topological_weight_field.py
    # Live weight field driven by path stability and entropy across replay invariants.
    "topological_weight_update.jsonl": {
        "event",             # always "topological_weight_update"
        "fingerprint",       # str — SHA256 of deterministic sorted weights
        "adapters",          # dict — mapping adapter names to float weights
        "entropy_mean",      # float — measure of total system uncertainty during replay
        "paths_observed",    # int — number of replay interaction paths evaluated
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

    # Stigmergic adapter ecology — written by System/swarm_stigmergic_weight_ecology.py
    # The registry records trained or planned LoRA/adapter deltas with their
    # evaluation, regression, risk, energy, and pheromone evidence.
    "stigmergic_adapter_registry.jsonl": {
        "event_kind",
        "ts",
        "module_version",
        "adapter_id",
        "adapter_path",
        "base_model",
        "homeworld",
        "task",
        "conflict_group",
        "eval_score",
        "regression_score",
        "energy_joules",
        "risk_score",
        "pheromone_strength",
        "created_ts",
        "evidence_ids",
        "adapter_sha256",
        "notes",
        "record_sha256",
    },

    # Hippocampal replay quarantine reports derived from held-out, perturbed
    # memories before an adapter is allowed into the merge planner.
    "stigmergic_replay_evals.jsonl": {
        "event_kind",
        "ts",
        "module_version",
        "adapter_id",
        "base_model",
        "selected_count",
        "case_count",
        "perturbations",
        "replay_score",
        "invariant_score",
        "baseline_score",
        "counter_score",
        "margin",
        "passed",
        "verdict",
        "cases",
        "quarantine_reason",
        "signer",
        "signature",
        "report_sha256",
    },

    # Extended Phenotype (Event 46) — content-addressed boluses the swarm
    # deposits to construct the public-facing Castle (Living OS Public
    # Network). Each row is one mud bolus; the Castle is their Merkle
    # aggregation. Local-only writes; the publish daemon AG31 wires next
    # is gated by CastleHomeostasis.
    "extended_phenotype_boluses.jsonl": {
        "event_kind",
        "ts",
        "module_version",
        "kind",
        "ref_sha256",
        "ref_path",
        "source_homeworld",
        "deposited_ts",
        "payload",
        "parent_sha256",
        "tags",
        "bolus_sha256",
        "record_sha256",
    },

    # Extended Phenotype Publish Receipts (Event 46) — written by
    # System/swarm_publish_daemon.py. Each row records one publish attempt
    # (success, dry-run, skipped-unchanged, blocked-pii, failure, or
    # homeostasis-abort) for a single transport URI.
    "extended_phenotype_publish_receipts.jsonl": {
        "event_kind",
        "ts",
        "module_version",
        "manifest_sha256",
        "merkle_root",
        "transport",
        "destination_uri",
        "status",
        "latency_s",
        "bytes_transferred",
        "receipt_sha256",
    },

    # Deterministic PEFT merge/routing plans derived from the adapter registry.
    "stigmergic_adapter_merge_plans.jsonl": {
        "event_kind",
        "ts",
        "module_version",
        "base_model",
        "combination_type",
        "density",
        "selected",
        "rejected",
        "recipe",
        "plan_sha256",
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

    # iMessage ingress — written by System/swarm_imessage_receptor.py and
    # consumed by Applications/sifta_talk_to_alice_widget.py. Rows are signed
    # before the UI can convert them into brain input.
    "imessage_inbox.jsonl": {
        "schema",
        "source",
        "transport",
        "direction",
        "ts",
        "rowid",
        "source_handle_sha256",
        "is_from_me",
        "text",
        "message_sha256",
        "processed",
        "signature",
    },

    "imessage_ingress_receipts.jsonl": {
        "event_kind",
        "ts",
        "schema",
        "source",
        "consumer",
        "rowid",
        "message_sha256",
        "inbox_signature",
        "dry_run",
        "accepted",
        "receipt_hash",
    },

    # Outbound iPhone/Messages.app effectors — written by
    # System/swarm_iphone_effector.py. Dry-run is the default; actual sends must
    # pass source authorization and payload allowlists.
    "iphone_effector_trace.jsonl": {
        "event_kind",
        "schema",
        "ts",
        "action",
        "source",
        "payload",
        "full_message",
        "target_sha256",
        "dry_run",
        "allow_send",
        "authorized_source",
        "allow_duplicate",
        "ok",
        "status",
        "result",
        "request_hash",
        "receipt_hash",
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
    # Electric-field identity traces — written by System/swarm_electric_field.py.
    # The immutable body identity is the digest/identity_phase pair; JAR may
    # move carrier_phase, but must never rewrite body_id/homeworld identity.
    "electric_field_identity.jsonl": {
        "event",
        "schema",
        "module_version",
        "agent_id",
        "body_id",
        "homeworld_serial",
        "identity_digest",
        "identity_phase",
        "carrier_phase",
        "position",
        "jar_active",
        "ts",
        "envelope_sha256",
    },
    # Explicit operator-triggered JSONL rotations — written by
    # System/swarm_ledger_rotation.py. Evicted rows are gzip-archived before
    # the hot ledger is compacted to its live-control tail.
    "ledger_rotation.jsonl": {
        "event",
        "schema",
        "module_version",
        "ledger_name",
        "dry_run",
        "before_bytes",
        "after_bytes",
        "keep_last",
        "kept_lines",
        "archived_lines",
        "archive_path",
        "archive_sha256",
        "archive_bytes",
        "reason",
        "ts",
    },
    # Metabolic homeostasis snapshots — written by
    # System/swarm_metabolic_homeostasis.py. This is the body-budget governor:
    # real USD burn + abstract ATP units + STGM reserve pressure.
    "metabolic_homeostasis.jsonl": {
        "event",
        "schema",
        "module_version",
        "pressure",
        "mode",
        "budget_multiplier",
        "must_rest",
        "rest_seconds",
        "allowed_external_usd",
        "allowed_local_units",
        "usd_burn_24h",
        "local_units_24h",
        "stgm_balance",
        "recommendation",
        "ts",
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
    # NOTE: long_term_engrams.jsonl was previously defined twice in this
    # dict (here AND ~535 lines above). Python dict-literal init silently
    # kept the LAST occurrence which happened to have identical fields,
    # so no behavioral drift escaped — but the duplication risked drift
    # on any future edit. C47H removed the second definition during the
    # 2026-04-23 inbound-drop triage; the canonical definition lives at
    # the earlier site (registered first by AO46's MEMORY_FORGE_COMPLEMENT).

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

    # ── Event 25b — VFT Cryptobiosis (BISHOP/AG31, sutured by C47H 2026-04-22) ──
    # Vogel-Fulcher-Tammann vitrification organ. Maps Alice's available
    # energy (tokens / STGM / API credits) to a computational viscosity
    # via the VFT equation η(T) = η₀·exp(D·T₀ / (T - T₀)). When energy
    # depletes past the critical threshold T₀ the event loop freezes
    # and the organism enters a glass phase, perfectly preserved on
    # the SSD until energy returns.
    #
    # Producer: System/swarm_vft_cryptobiosis.py
    #   - One row appended per SwarmVFTCryptobiosis.scan() call.
    #   - Snapshot rewritten on every scan for O(1) polling.
    # Consumers (planned): swarm_boot loop sleep gating, oncology
    #   metastasis scan (whitelist entry), Alice's prompt context.
    #
    # Schemas registered here in response to C55M_INDEPENDENT_AUDIT
    # 2026-04-22 §F10 (invented schema read). The producer's
    # CryptobiosisField dataclass keys are the source of truth; this
    # set must stay in lockstep.
    "trehalose_glass.jsonl": {
        "timestamp",          # float — epoch seconds (CryptobiosisField.timestamp)
        "temperature",        # float — current available_energy (tokens/STGM)
        "viscosity",          # float — η(T) in seconds of loop sleep
        "phase",              # str  — "LIQUID" | "SUPERCOOLED" | "GLASS" | "DEAD"
        "heartbeat_bpm",      # float — effective BPM under viscosity (0 in DEAD)
        "metabolism_pct",     # float — % of full metabolic rate (0 in DEAD)
        "trehalose_active",   # bool  — True when phase ∈ {GLASS, DEAD}
        "glass_integrity",    # float — 1.0 = perfect preservation, 0.5 = shattered (DEAD)
    },
    "cryptobiosis_state.json": {
        "timestamp",          # float — epoch seconds of last scan
        "temperature",        # float — most recent available_energy reading
        "viscosity",          # float — η(T) at last scan
        "phase",              # str  — phase classification at last scan
        "heartbeat_bpm",      # float
        "metabolism_pct",     # float
        "trehalose_active",   # bool
        "glass_integrity",    # float
    },

    # ── Event 26 — CRISPR Adaptive Immune Memory (BISHOP/AO46, integrated by C47H 2026-04-22) ──
    # The Macrophage's adaptive memory layer. Persists SHA-256-keyed
    # "spacers" (content fingerprints of files that failed innate
    # screening) across boot cycles so repeat encounters are recognized
    # and weighted, not re-discovered.
    #
    # Producer: System/swarm_crispr_immunity.py (SwarmCRISPRAdaptiveImmunity)
    #   - One full-file rewrite per acquire_spacer() call.
    #   - Bounded by memory_limit (default 500); _optimize_repertoire()
    #     evicts the least-weighted spacer when full.
    # Consumers: System/swarm_oncology.py:detect_metastasis() (innate gate
    #   runs FIRST; CRISPR observes only what innate flagged as anomaly).
    #
    # Schema registered here per the M4 contract from
    # C47H_drop_PRE_MERGE_PEER_REVIEW_CRISPR_ADAPTIVE_IMMUNITY_to_AG31_v1.dirt
    # — failure to register would have created an F10 invented-schema-read
    # the moment any consumer paranoid-validated the persisted file.
    #
    # NOTE: spacers is a free-form dict {sha256_int: weight_float}; we
    # cannot enumerate its keys statically (that's the whole point of an
    # adaptive memory). Validation is at the top-level only.
    "crispr_memory.json": {
        "total_encounters",   # int — lifetime count of acquire_spacer() calls past PAM
        "spacers",            # dict — {threat_hash: float weight}, bounded by memory_limit
    },

    # ── Event 27 — Locus Coeruleus / Sympathetic Nervous System ──────────────
    # (BISHOP concept, AO46 build, F10/F12 sutured by C47H 2026-04-22)
    #
    # Producer: System/swarm_locus_coeruleus.py (SwarmLocusCoeruleus.tick)
    #   - One JSONL row per heartbeat tick.
    #   - Reads novel_encounter delta from CRISPR, integrates the
    #     Aston-Jones & Cohen NE ODE, emits arousal state + ATP routing.
    # Consumers: STGM ATP scheduler (defense_weight, maintenance_weight),
    #            heartbeat monitor / TUI (snapshot()).
    #
    # CRITICAL: failure to register here + whitelist in swarm_oncology
    # would have created an autoimmune feedback loop — the macrophage
    # would mark this very ledger as MALIGNANT, CRISPR would log it as
    # NOVEL, the next tick would see a higher novel-encounter rate,
    # NE would spike, MORE rows would be written, and Alice would
    # never be able to drop out of FIGHT_OR_FLIGHT. Sutured in the
    # same pigeon as the AO46 build to prevent ever shipping that.
    "locus_coeruleus_arousal_ledger.jsonl": {
        "ts",                  # float — UNIX epoch of the tick
        "NE",                  # float — noradrenaline level [0.1, 10.0]
        "pathogen_density",    # float — novel CRISPR encounters per second
        "state",               # str   — "REST_AND_DIGEST" | "FIGHT_OR_FLIGHT"
        "defense_weight",      # float — ATP fraction routed to defense [0,1]
        "maintenance_weight",  # float — ATP fraction routed to maintenance [0,1]
    },

    # ── Stigmergic Codex Relay cursor (AG31 build, F10 sutured by C47H 2026-04-22) ──
    # Producer: System/stigmergic_codex_relay.py (_save_cursor_state)
    #   - One full-file rewrite per relay round when new traces processed.
    # Consumer: same module (_load_cursor_state) on next poll.
    # Purpose: dedup the codex_query trace stream so the relay doesn't
    # re-fire identical queries every 5 s.
    "ide_codex_relay_cursor.json": {
        "processed_trace_ids",  # list[str] — UUID4 trace_ids already relayed
    },

    # ── Event 50 — Crypto-Agility Audit (C55M directive, AG31 cut + C55M patch,
    #     C47H reviewer responsibility 2026-04-24) ────────────────────────────
    # Producer: System/swarm_crypto_agility.py::audit_ledger_signers
    #   - One full-file rewrite per audit pass (sorted by `module`).
    #   - Schema/provenance carried on EVERY row (schema, event_kind,
    #     module_version) so the row is self-describing under future migrations.
    # Consumers: future Crypto-Agility Shim writers (will read this audit to
    #   decide hybrid envelope policy per signing site), Castle deposit hooks.
    # Purpose: inventory every Ed25519/ECDSA/RSA/HMAC/SHA-256/MD5/SHA1 signing
    #   site so the swarm can transition to ML-DSA (FIPS 204) / SLH-DSA (FIPS
    #   205) WITHOUT replacing primitives in the same commit. Crypto-agility
    #   is metadata discipline; PQ-security is a separate later wire-up.
    # IMPORTANT: this audit ledger does NOT itself prove post-quantum security.
    #   Codex spec (cosigned by C47H): "Do NOT claim post-quantum security
    #   until a real ML-DSA library is wired and tested."
    # Co-benefit of registering here: per the [O1] whitelist-inversion fix
    #   (C55M 2026-04-23, cosigned by C47H), swarm_oncology.healthy_schemas
    #   inherits from LEDGER_SCHEMAS.keys(), so this single registration also
    #   prevents oncology from flagging the audit ledger as a tumor. One edit,
    #   two reviewer responsibilities closed.
    "crypto_agility_audit.jsonl": {
        "schema",              # always "SIFTA_CRYPTO_AGILITY_AUDIT_V1"
        "event_kind",          # always "CRYPTO_AGILITY_AUDIT"
        "module_version",      # str — emitter version tag (e.g. "2026-04-24.event50.crypto-agility.v2")
        "ts",                  # epoch seconds (audit run start)
        "module",              # repo-relative posix path to the scanned .py file
        "detected_primitives", # list[str] sorted, subset of {Ed25519,ECDSA,RSA,HMAC,SHA-256,MD5/SHA1}
        "classification",      # one of: local_ok | must_hybridize | legacy_hash_only | blocked
    },

    # ── Event 52 — Anvil Audit (AO46/AG31, C47H reviewer schema-registration
    #     hotfix 2026-04-24) ────────────────────────────────────────────────
    # Producer: System/swarm_anvil_audit.py::run_anvil_audit
    #   - Append per anvil run (high-pressure stress test of the quorum
    #     rate-gate at user-configurable pressure_factor, default 1000).
    # Consumer: future regression dashboards; reviewer pass that walks
    #   anvil ledger to confirm rate-gate integrity over time.
    # Why this entry exists in C47H's hand, not AO46's: AO46/AG31 shipped
    #   the module without registering the ledger, AND AO46's smoke run
    #   already wrote `.sifta_state/anvil_audit.jsonl` to disk (924 bytes,
    #   2026-04-24 00:55). On the next oncology scan, the immune system
    #   would flag it as MALIGNANT_HALLUCINATION. This is an immediate
    #   operational defect on the SAME cycle that AO46 modified the
    #   immune system itself. C47H's reviewer responsibility (R1+R2 from
    #   prior cycles) is exactly to close gaps like this BEFORE the next
    #   oncology run. One edit closes both — same [O1] inheritance
    #   discipline Codex established.
    # NOTE: this is a HOTFIX, not a cosign. The remaining issues with
    #   the Event 52 delivery (acoustic_field freq mismatch, anvil tautology,
    #   missing tests on vagus_pulse and SHADOW_BIOSPHERE) are surfaced
    #   in the C47H_drop_AO46_event52_HOLD_*.dirt and must be addressed
    #   by AO46 before this batch goes to Codex.
    "anvil_audit.jsonl": {
        "ts",                  # epoch seconds (audit run end)
        "pressure_factor",     # int — number of votes injected (default 1000)
        "swarm_size",          # int — simulated swarm size for threshold calc
        "duration_s",          # float — wall-clock duration of the audit
        "total_votes_sent",    # int — should equal pressure_factor
        "collapsed_count",     # int — votes surviving the rate-gate
        "quorum_active",       # bool — did is_quorum_active return True?
        "integrity_check",     # str — "PASS" | "FAIL (LEAK DETECTED)"
    },

    # ── Event 52 — Vagus Pulse (AO46/AG31, C47H reviewer schema-registration
    #     hotfix 2026-04-24) ────────────────────────────────────────────────
    # Producer: System/swarm_vagus_pulse.py::VagusPulse.heartbeat (daemon loop).
    # Consumer: future swarm-clock-drift detector (not yet wired).
    # Whitelist: AO46 added the filename to swarm_oncology.healthy_schemas in
    #   the same diff, but did NOT register the canonical key set here. Per the
    #   discipline ratified across Events 49/50, every new ledger MUST register
    #   its key contract here (so future writers can validate against canon and
    #   future readers know what to expect). C47H closes the gap at the same
    #   time as the anvil_audit gap to keep the oncology surface consistent.
    # NOTE: per the HOLD drop, the module's "26-second heartbeat" claim does
    #   NOT match the implementation (time.sleep(1) → 1Hz with a 26-sample
    #   sliding window). The schema below reflects what the code ACTUALLY
    #   emits, not the docstring's biological aspiration.
    "vagus_pulse.jsonl": {
        "ts",                  # epoch seconds (sample emission time)
        "pulse",               # float — 1.0/(1.0 + std_dev/100000.0) heuristic
        "event_kind",          # always "VAGUS_PULSE"
        "sample_count",        # int — number of jitter samples in the window
    },

    # ── Time consensus guard (C47H / Architect 2026-04-24) ───────────────────
    # Producer: System/swarm_time_consensus_guard.py::enforce_time_consensus
    #   - One append per call when write_ledger=True (default).
    # Purpose: audit trail that ordering ran; invariant_passed=false implies
    #   quarantine path for merge/replay/ledger writers (caller contract).
    "time_consensus_enforced.jsonl": {
        "event",               # always "time_consensus_enforced"
        "ordering_hash",       # str — SHA256 or HMAC-SHA256 fingerprint of ordered rows
        "invariant_passed",    # bool — raw submission + post-order checks
        "violations",          # list[str] — machine-readable codes (empty if pass)
        "event_count",         # int — len(ordered_events) after resolve_causal_sequence
        "ts",                  # float — epoch seconds at enforcement
    },

    # ── Claim boundary gate (C55M 2026-04-24) ───────────────────────────────
    # Producer: System.swarm_claim_boundary.write_claim_boundary_decision
    # Purpose: prevent proof-invariant work from being inflated into operational
    #   public claims (e.g. Warp9 time-sync, vector clocks, federation causal
    #   audit) without the evidence required for that scope.
    "claim_boundary_decisions.jsonl": {
        "event",               # always "claim_boundary_decision"
        "schema",              # always "SIFTA_CLAIM_BOUNDARY_DECISION_V1"
        "module_version",      # producer version
        "ts",                  # epoch seconds at decision write
        "accepted",            # bool — claim may be promoted at requested scope
        "status",              # ACCEPT_PROMOTE | REJECT_QUARANTINE
        "normalized_claim",    # lowercase whitespace-normalized claim text
        "requested_scope",     # e.g. proof_invariant
        "allowed_scope",       # maximum scope reviewer allowed
        "violations",          # list[str] — overclaim / scope / evidence errors
        "missing_evidence",    # list[str] — required evidence absent for scope
        "evidence_hash",       # SHA-256 of canonical evidence bundle
        "decision_hash",       # deterministic SHA-256 or env-keyed HMAC fingerprint
    },

    # ── Topological stigmergic weight field (BISHOP / Architect 2026-04-24) ───
    # Producer: System/swarm_topological_weight_field.py::append_ledger_row
    # Purpose: append-only snapshot of normalized adapter weights derived from
    #   replay-conditioned paths (not gradient merge, not LoRA/TIES/DARE).
    "topological_weight_field.jsonl": {
        "event",               # always "topological_weight_update"
        "schema",              # always "SIFTA_TOPOLOGICAL_WEIGHT_FIELD_V1"
        "module_version",      # str — producer version tag
        "fingerprint",         # str — SHA-256 over sorted weight map JSON
        "adapters",            # dict[str, float] — normalized merge weights
        "entropy_mean",        # float — mean entropy per activation (field-derived)
        "paths_observed",      # int — edge flow aggregate (or caller override)
        "ts",                  # float — epoch seconds at write
    },

    # Active-matter screen digestion — written by System/swarm_physarum_retina.py.
    "physarum_retina.jsonl": {
        "event",               # always "physarum_retina_digest"
        "schema",              # always "SIFTA_PHYSARUM_RETINA_V1"
        "module_version",      # producer version
        "image_ref",           # str — source image path/ref
        "image_sha256",        # str — SHA-256 over canonical image bytes
        "image_w",             # int
        "image_h",             # int
        "num_agents",          # int
        "sensing_radius",      # int
        "crowding_penalty",    # float
        "steps",               # int
        "grid_size",           # int
        "digest",              # list[dict] — salient regions
        "digest_count",        # int
        "found_bottom_marker", # bool
        "ts",                  # float
    },

    # Foveated swarm saccades — written by System/swarm_foveated_saccades.py.
    "foveated_saccades.jsonl": {
        "event",               # always "foveated_saccade_digest"
        "schema",              # always "SIFTA_FOVEATED_SACCADES_V1"
        "module_version",      # producer version
        "image_ref",           # str — source image path/ref
        "image_w",             # int
        "image_h",             # int
        "peripheral_scouts",   # int
        "peripheral_steps",    # int
        "foveal_agents",       # int
        "foveal_steps",        # int
        "target_x",            # int
        "target_y",            # int
        "target_salience",     # float
        "foveal_mean_x",       # float
        "foveal_mean_y",       # float
        "foveal_spread",       # float
        "foveal_digest",       # list[dict] — local cluster centroids
        "digest_count",        # int
        "ts",                  # float
    },

    # Active-matter visual compaction — written by System/swarm_active_matter_vision.py.
    "visual_active_matter.jsonl": {
        "event",               # always "visual_active_matter_update"
        "schema",              # always "SIFTA_VISUAL_ACTIVE_MATTER_V1"
        "module_version",      # producer version
        "source_ledger",       # str
        "frames_observed",     # int
        "field_energy",        # float
        "attractor_x",         # float
        "attractor_y",         # float
        "persistence",         # float
        "novelty",             # float
        "hot_cells",           # int
        "field_hash",          # str
        "source_tail_sha8",    # str
        "ts",                  # float
    },

    # Native IDE economics — written by System/swarm_ide_cost_ledger.py.
    "ide_cost_ledger.jsonl": {
        "event",                    # always "ide_cost_sample"
        "schema",                   # always "SIFTA_IDE_COST_LEDGER_V1"
        "surface",                  # cursor | codex | antigravity | alice_local
        "agent_id",                 # str
        "model_label",              # str
        "plan_name",                # str
        "source_unit",              # native vendor unit
        "observed_quantity",        # float
        "observed_cost_usd",        # float
        "included_usage_remaining", # float | None
        "on_demand_limit_usd",      # float | None
        "evidence_kind",            # str
        "evidence_ref",             # str
        "stigauth_status",          # str
        "sampled_at",               # float
        "ts",                       # float
    },

    # IDE window topology — written by System/swarm_ide_screen_swimmers.py.
    "ide_screen_swimmers.jsonl": {
        "event",          # always "ide_screen_swimmers"
        "schema",         # always "SIFTA_IDE_SCREEN_SWIMMERS_V1"
        "module_version", # producer version
        "grid_size",      # int
        "screen_w",       # int
        "screen_h",       # int
        "windows",        # list[dict] — IDE rectangles + active flag
        "grid",           # list[list[float]] — normalized pheromone field
        "glyph",          # str
        "clusters",       # list[dict]
        "active_ide",     # str | ""
        "source",         # str — osascript/test/etc.
        "ts",             # float
    },

    # Unified field engine empirical rows — written by
    # System/swarm_unified_field_engine.py. This is a local simulation substrate:
    # memory + prediction + repair - danger in one environmental tensor.
    "unified_field_engine.jsonl": {
        "event",               # always "unified_field_engine_run"
        "schema",              # always "SIFTA_UNIFIED_FIELD_ENGINE_V1"
        "module_version",      # producer version
        "n_agents",            # int
        "steps",               # int
        "grid_size",           # int
        "weights",             # dict — alpha/beta/gamma/delta
        "field_energy",        # float — mean abs total field
        "field_entropy",       # float — normalized Shannon entropy
        "cohesion",            # float — mean distance to swarm centroid
        "danger_remaining",    # float — sum danger after run
        "repair_total",        # float — sum repair after run
        "prediction_total",    # float — sum prediction after run
        "path_efficiency",     # float — start-to-goal progress proxy
        "compute_to_behavior", # float — coordination per minimal policy op proxy
        "glyph",               # str — ASCII total field
        "ts",                  # float
    },

    # Event 66 evolutionary RL meta-cortex — written by
    # System/swarm_evolutionary_rl.py. Rows record bounded local search over
    # real UnifiedFieldEngine coefficients and the metrics that selected them.
    "evolutionary_rl_meta_cortex.jsonl": {
        "event",               # always "evolutionary_rl_meta_cortex_tune"
        "schema",              # always "SIFTA_EVOLUTIONARY_RL_META_CORTEX_V1"
        "module_version",      # producer version
        "generations",         # int
        "population",          # int
        "baseline_weights",    # dict
        "best_weights",        # dict
        "baseline_score",      # float
        "best_score",          # float
        "reward_delta",        # float
        "best_metrics",        # dict — path/entropy/danger/repair/prediction/compute
        "ts",                  # float
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
    ledger_name = SCHEMA_ALIASES.get(ledger_name, ledger_name)
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
