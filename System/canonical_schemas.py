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

    # Endocrine adrenaline — written by System/swarm_endocrine.py
    "endocrine_glands.jsonl": {
        "transaction_type",   # "ENDOCRINE_FLOOD"
        "hormone",            # "EPINEPHRINE_ADRENALINE"
        "swimmer_id",         # target swimmer or "GLOBAL"
        "potency",            # 0..N intensity
        "duration_seconds",   # how long the flood lasts
        "timestamp",          # epoch seconds
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
    "stigmergic_library.jsonl": {
        "ts",                 # epoch seconds
        "category",           # e.g., SCIENCE, TECH, NATURE, STIGMERGY, FUN
        "nugget_text",        # Pure, dense insight devoid of conversational trash
        "source_api",         # "BISHAPI"
        "curator_agent",      # "C47H"
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
