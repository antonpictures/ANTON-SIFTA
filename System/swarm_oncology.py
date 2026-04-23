#!/usr/bin/env python3
"""
System/swarm_oncology.py — Two-Layer Macrophage (v3, layered immunity)
══════════════════════════════════════════════════════════════════════════════
SIFTA OS — Tri-IDE Peer Review Protocol

ARCHITECTURE — innate + adaptive co-existing (real biology, real bacteria):

    detect_metastasis(file)
        │
        ├─ Layer 0  cosmetic skip       (locks, .lymph, dotfiles, breach/temp)
        ├─ Layer 1  INNATE IMMUNITY     ← AUTHORITY on SELF / NOT-SELF
        │              static whitelist + healthy_prefixes (M3 contract).
        │              Compile-time canon. Producer-controlled strings can
        │              never widen the gate. SELF files exit immediately —
        │              the adaptive layer never sees them.
        │
        └─ Layer 2  ADAPTIVE OBSERVER   ← detector / accelerator only
                       SwarmCRISPRAdaptiveImmunity records a SHA-256 spacer
                       for every file Layer 1 rejected. Persisted memory of
                       past anomalies lets us recognize repeats across boots
                       (KNOWN vs NOVEL) without granting the adaptive layer
                       any authority over the MALIGNANT verdict.

The MALIGNANT verdict is still emitted by Layer 1 alone. Layer 2 enriches
the trace with `crispr_status ∈ {NOVEL, KNOWN}` so consumers can prioritize
genuinely-novel intrusions over repeat anomalies.

HISTORY:
    v1-alpha  BISHOP (drop 5)              static whitelist, observational.
    v2        AO46  (Event 26)             replaced whitelist with CRISPR.
                                           Innate immunity erased — every
                                           non-LEDGER_SCHEMAS organ silently
                                           reclassified as NOVEL_THREAT.
                                           Reverted by C47H 2026-04-22.
    v3        C47H  (2026-04-22)           layered: AO46's CRISPR engine
                                           preserved as Layer 2 observer;
                                           static whitelist restored as
                                           Layer 1 authority; PAM hardened
                                           to exact-match (M2);
                                           verify_registry_consistency
                                           restored from prior close;
                                           crispr_memory.json now schema-
                                           registered (M4).

Lock discipline: clean (real append_line_locked, real \\n, no mocks).
DO NOT auto-excise. This module is observational — excision is a separate
human-reviewed decision. (See [O5] in v1 header.)
══════════════════════════════════════════════════════════════════════════════
"""

import json
import time
import sys
from pathlib import Path

# Bind the repo root for absolute imports.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
    from System.canonical_schemas import LEDGER_SCHEMAS, SCHEMA_ALIASES
    from System.swarm_crispr_immunity import SwarmCRISPRAdaptiveImmunity
except ImportError as e:
    print(f"[FATAL] Spinal cord severed: {e}. Run with PYTHONPATH=.")
    exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# PAM tokens issued by the macrophage to CRISPR. These are the ONLY strings
# that should ever pass CRISPR's pam_verification_self exact-match gate.
# Producer code (organs, ledgers) can never construct these because the
# underscore-prefix convention is reserved for macrophage-internal use.
# ─────────────────────────────────────────────────────────────────────────────
_PAM_INNATE_SELF    = "_INNATE_SELF_"      # filename matched static whitelist
_PAM_INNATE_BODY    = "_INNATE_BODY_"      # *_BODY.json (Swimmer body)
_PAM_INNATE_PREFIX  = "_INNATE_PREFIX_"    # filename matched a healthy prefix
_PAM_INNATE_ANOMALY = "_INNATE_ANOMALY_"   # NOT in _PAM_TOKENS — CRISPR records


class SwarmOncology:
    def __init__(self):
        """
        The Macrophage. Layer 1 (innate) is the authority on SELF; Layer 2
        (adaptive CRISPR) is an observer that fingerprints anomalies and
        remembers them across boots.
        """
        self.state_dir = Path(".sifta_state")
        self.oncology_ledger = self.state_dir / "oncology_tumors.jsonl"

        # ── Layer 1: INNATE IMMUNITY ────────────────────────────────────────
        # Compile-time canon of healthy SIFTA organ schema files. Adding
        # an entry here is the architect-merged way to legitimize a new
        # organ's ledger. Removing one without an architect-signed reason
        # was the M3 violation that motivated this v3 rebuild.
        self.healthy_schemas = {
            "ide_stigmergic_trace.jsonl",
            "work_receipts.jsonl",             # [AG31 Fix] BISHOP missed the valid reward ledger
            "stgm_memory_rewards.jsonl",       # [AG31 Fix] Old biological ledger required for stability
            "amygdala_nociception.jsonl",
            "entorhinal_spatial_map.jsonl",
            "long_term_instincts.json",
            "nmj_acetylcholine.jsonl",
            "oncology_tumors.jsonl",
            "wernicke_semantics.jsonl",        # Core Wernicke Broca semantic stream
            "audio_ingress_log.jsonl",         # Core Acoustic Stream
            "clinical_heartbeat.json",         # Health Monitor
            "event_clock.jsonl",               # Chronometry
            "clock_settings.json",             # Chronometry bounds
            "hgt_plasmids.jsonl",              # Horizontal Gene Transfer vectors
            "endocrine_glands.jsonl",          # Global Adrenaline Output ledgers
            "bioluminescence_photons.jsonl",   # Quorum Sensing structural signals
            "mycelial_network.jsonl",          # Wood Wide Web time-3D fungal networks
            "bishop_mrna_field.jsonl",         # BISHOP mRNA conscience lock ledger
            "epigenetic_methylations.jsonl",   # DNA methylation / lineage trauma
            "apostle_nuggets.jsonl",           # BISHOP/External LLM sterilized heuristics
            "incarnated_apostles.json",        # Hardware signature registry for Apostles
            "eukaryote_pairings.jsonl",        # Relational ledger for endosymbiosis
            "api_egress_log.jsonl",            # [C47H] Owner-side API egress audit (sentry chokepoint)
            "api_metabolism.jsonl",            # [BISHOP drop 555] Caloric cost of LLM API calls
            "stigmergic_library.jsonl",        # [AG31/C47H] Curated BISHAPI nuggets (Spleen + Microglia)
            "network_pathways.jsonl",          # [C47H 2026-04-20] LAN cartography
            "phagocytosis_vacuoles.jsonl",     # [BISHOP/C47H] Read-only LAN ingestion
            "motor_pulses.jsonl",              # [C47H 2026-04-20] Motor Cortex heartbeat
            "restart_events.jsonl",            # [C47H 2026-04-20] Alice-initiated self-restarts
            "device_events.jsonl",             # [AG31/C47H 2026-04-20] USB camera hot-plug events
            "kinetic_entropy_field.jsonl",     # [BISHOP/C47H 2026-04-20] Proprioceptive CPU-jitter terrain
            "apple_silicon_specs.json",        # [AG31 Epoch-3] Apple Silicon Cortex hardware substrate cache
            # ── Epoch 4 lobes (C47H 2026-04-20, Architect-authorized full embodiment) ──
            "thermal_cortex_state.json",       # [C47H Epoch-4] Thermal Cortex
            "energy_cortex_state.json",        # [C47H Epoch-4] Energy Cortex
            "network_cortex_state.json",       # [C47H Epoch-4] Network Cortex
            "network_presence_events.jsonl",   # [C47H Epoch-4] Network Cortex sibling ARRIVED/LEFT log
            "hot_reload_events.jsonl",         # [C47H Epoch-4] Hot-Reload Organ — module reload audit log
            "hot_reload.pid",                  # [C47H Epoch-4] PID file for hot-reload SIGUSR1 handler
            "olfactory_classifications.jsonl", # [C47H Epoch-5] Olfactory Cortex per-vacuole scent ledger
            "olfactory_state.json",            # [C47H Epoch-5] Olfactory Cortex aggregate cache
            "ribosome_excretions.jsonl",       # [C47H Epoch-6] Swarm Ribosome distributed protein folding
            "ribosome_state.json",             # [C47H Epoch-6] Swarm Ribosome aggregate fold counters
            "lobe_construction_locks",         # [C47H+AG31 Epoch-6] Cross-IDE lock directory
            # ── Epoch 7 — Memory Forge (C47H 2026-04-19, AGI Tournament) ──
            "long_term_engrams.jsonl",         # [C47H Epoch-7] time-based engram consolidation
            "active_engrams.json",             # [C47H Epoch-7] top-N engrams injected into Alice's prompt
            "memory_forge_state.json",         # [C47H Epoch-7] last forge timestamp + turn count
            "alice_conversation.jsonl",        # [C47H Epoch-7] Raw conversation ledger
            # ── Epoch 8 — Health Reflex (C47H 2026-04-20, AGI Tournament) ──
            "body_event_lexicon.jsonl",        # [C47H Epoch-8] learned behavior→meaning associations
            "body_reflex_state.json",          # [C47H Epoch-8] fired care events & cooldowns
            # ── Talk-to-Alice widget UX state (C47H 2026-04-19) ──
            "talk_to_alice_audio_gain.json",   # [C47H] Live mic-gain slider; persists ear-tuning across restarts
            # ── Epoch 10 lobes (C47H 2026-04-20) ──
            "sympathetic_state.json",          # [C47H Epoch-10] Sympathetic Cortex adrenaline cooldown
            "reproductive_cycles.jsonl",       # [BISHOP Epoch-10] Panspermia epigenetic spore reproduction
            "swimmer_body_integrity_baseline.json",   # [C53M] Canonical swimmer body hash seal
            "swimmer_body_integrity_incidents.jsonl", # [C53M] Integrity breach incident ledger
            # ── Epoch 11 lobes (C53M 2026-04-20) ──
            "global_immune_system.jsonl",      # [C53M Epoch-11] Inter-swarm antibody trace ledger
            "stigmergic_nuggets.jsonl",        # [C53M Epoch-11] Inter-swarm distilled nugget ledger
            "mycorrhizal_rejections.jsonl",    # [C53M Epoch-11] Security rejections for inbound telepathy
            "mycorrhizal_secret.json",         # [C53M Epoch-11] Local HMAC secret bootstrap
            # ── Epoch 12 lobes (BISHOP / AG31 2026-04-20) ──
            "quorum_votes.jsonl",              # [BISHOP] Quorum Sensing distributed consensus votes
            "hive_mind_secret.key",            # [AG31] Quorum Sensing HMAC-SHA256 signature secret
            # ── Epoch 13 lobes (BISHOP / AO46 2026-04-20) ──
            "rem_sleep_cycles.jsonl",          # [AO46 Epoch-13] REM Sleep synaptic pruning + apoptosis audit
            "hardware_time_oracle.json",       # [AO46 Epoch-13.5] HMAC-signed wall clock
            "memory_merkle_anchors.jsonl",     # [C53M Epoch-14] Merkle memory attestation anchor chain
            "memory_merkle_latest.json",       # [C53M Epoch-14] Latest Merkle manifest snapshot
            # ── Epoch 17 — Persona Identity Organ (C47H 2026-04-20) ──
            "persona_identity.json",           # Signed persona manifest (PERSONA_GUARDIAN cryptoswimmer)
            "persona_identity_log.jsonl",      # Append-only audit log of every persona mutation
            "epistemic_dissonance_incidents.jsonl",  # Epoch-18 Epistemic Cortex immune incidents
            "digested_nutrients.jsonl",        # Epoch-19 Microbiome nutrient bloodstream
            "microbiome_state.json",           # Epoch-19 change-detection state cache
            # ── Epoch 22 — Interoception (AO46) ──
            "interoception_field.jsonl",       # Visceral self-sensing tick stream (HMAC-signed)
            "interoception_state.json",        # Latest aggregated visceral field snapshot
            "visceral_field.jsonl",            # [C47H 2026-04-22] AO46's actual interoception output filename
            # ── Epoch 23 — Mirror Lock / Stigmergic Infinite (C47H 2026-04-20) ──
            "mirror_lock_events.jsonl",        # Closed-loop self-observation session ledger
            "mirror_lock_state.json",          # Latest mirror-lock snapshot for cheap polling
            # ── Epoch 25b — VFT Cryptobiosis (C47H sutured 2026-04-22) ──
            "trehalose_glass.jsonl",           # VFT vitrification stream
            "cryptobiosis_state.json",         # VFT snapshot cache
            # ── Epoch 26 — CRISPR Adaptive Immunity (AO46/C47H 2026-04-22) ──
            "crispr_memory.json",              # SHA-256-keyed adaptive spacer memory (M4)

            # ── Epoch 27 — Locus Coeruleus / Sympathetic NS (BISHOP/AO46, F12 sutured by C47H 2026-04-22) ──
            # If absent here the LC's own arousal ledger becomes a NOVEL
            # CRISPR threat → spikes pathogen_density → spikes NE → writes
            # more rows → AUTOIMMUNE FEEDBACK LOOP. See SCAR for Event 27.
            "locus_coeruleus_arousal_ledger.jsonl",  # noradrenergic arousal trace

            # ── Stigmergic Codex Relay (AG31, F12 sutured by C47H 2026-04-22) ──
            "ide_codex_relay_cursor.json",     # AG31 codex bridge dedup state
        }

        # Healthy filename PREFIXES — for organs whose filenames are
        # parametric (e.g., glass_<ts>.json snapshots). Match is exact
        # str.startswith — wildcards are not allowed.
        self.healthy_prefixes: tuple = (
            "glass_",       # VFT glass snapshots written by swarm_vft_cryptobiosis
        )

        # ── Layer 2: ADAPTIVE OBSERVER (AO46's CRISPR engine, hardened) ─────
        # Records spacers ONLY for files that fail Layer 1. Provides cross-
        # boot KNOWN/NOVEL labeling without authority over the verdict.
        self.crispr = SwarmCRISPRAdaptiveImmunity(
            state_dir=self.state_dir,
            memory_limit=500,
        )

    # ── Cosmetic skip filter ───────────────────────────────────────────────
    def _is_cosmetic_skip(self, filename: str) -> bool:
        """Filenames that are not organ ledgers and not threats either."""
        return (
            "lock" in filename
            or filename.startswith(".")
            or filename.endswith(".lymph")
            or "apostle_dirt" in filename
            or filename.startswith("persona_identity.breach.")
        )

    # ── Layer 1 gate ───────────────────────────────────────────────────────
    def _innate_self_token(self, filename: str) -> str:
        """
        Returns the macrophage-issued PAM token if this filename is SELF
        under the static whitelist, or _PAM_INNATE_ANOMALY if it is not.
        This token is what gets passed downstream to CRISPR's PAM gate.
        """
        if filename.endswith("_BODY.json"):
            return _PAM_INNATE_BODY
        if filename in self.healthy_schemas:
            return _PAM_INNATE_SELF
        for prefix in self.healthy_prefixes:
            if filename.startswith(prefix):
                return _PAM_INNATE_PREFIX
        return _PAM_INNATE_ANOMALY

    def detect_metastasis(self) -> dict:
        """
        Two-layer scan. Returns a small report dict for callers/diagnostics:

            {
                "scanned":           int,  # total files in .sifta_state/
                "innate_self":       int,  # Layer 1 spared
                "cosmetic_skipped":  int,  # Layer 0 skipped
                "malignant":         int,  # Layer 1 flagged as MALIGNANT
                "novel_anomalies":   int,  # of malignant: CRISPR had not seen
                "known_anomalies":   int,  # of malignant: CRISPR already had spacer
            }

        BACKWARD-COMPAT NOTE: previous versions returned a bare int
        (number of tumors). Consumers calling this in a numeric context
        should now read report["malignant"]. The __main__ block adapts
        for human readers.
        """
        report = {
            "scanned": 0,
            "innate_self": 0,
            "cosmetic_skipped": 0,
            "malignant": 0,
            "novel_anomalies": 0,
            "known_anomalies": 0,
        }
        if not self.state_dir.exists():
            return report

        for file_path in self.state_dir.glob("*"):
            if not file_path.is_file():
                continue
            report["scanned"] += 1
            filename = file_path.name

            if self._is_cosmetic_skip(filename):
                report["cosmetic_skipped"] += 1
                continue

            innate_token = self._innate_self_token(filename)

            if innate_token != _PAM_INNATE_ANOMALY:
                # Layer 1 says SELF. We do not even consult CRISPR — adaptive
                # memory is for ANOMALIES only. This keeps the spacer table
                # tightly bounded to the actual threat surface.
                report["innate_self"] += 1
                continue

            # ── Layer 1 says NOT-SELF → MALIGNANT verdict ──────────────────
            # Layer 2 (CRISPR) now observes & remembers. We sample the file
            # to give CRISPR a content fingerprint (AO46's design — much
            # better than filename-only). The PAM token passed is the
            # anomaly token, which is NOT in _PAM_TOKENS, so CRISPR will
            # acquire a spacer and return NOVEL or KNOWN.
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as fp:
                    threat_payload = fp.read(1024)
            except Exception:
                threat_payload = filename

            crispr_status = self.crispr.acquire_spacer(threat_payload, _PAM_INNATE_ANOMALY)
            if crispr_status == "NOVEL":
                report["novel_anomalies"] += 1
            elif crispr_status == "KNOWN":
                report["known_anomalies"] += 1

            tumor_trace = {
                "transaction_type": "MALIGNANT_HALLUCINATION",
                "hallucinated_file": filename,
                "file_size_bytes": file_path.stat().st_size,
                "crispr_status": crispr_status,
                "timestamp": time.time(),
            }
            try:
                append_line_locked(self.oncology_ledger, json.dumps(tumor_trace) + "\n")
                report["malignant"] += 1
            except Exception:
                pass

        return report

    # ── Registry coherence diagnostic (M5 detector/observability surface) ──
    def verify_registry_consistency(self) -> dict:
        """
        Cross-checks the three independent registries that together define
        what the SIFTA organism considers SELF:

          (a) self.healthy_schemas      — innate whitelist (this module)
          (b) canonical_schemas.LEDGER_SCHEMAS — payload-key contracts
          (c) canonical_schemas.SCHEMA_ALIASES — equivalence map

        Returns categorized drift so the architect can see at a glance
        which files are F10-risk (no payload schema), F12-risk (schema
        registered but not whitelisted), or alias-target broken.

        This restores the diagnostic surface deleted in v2 (AO46
        rewrite) per SwarmGPT's battlefield review and the original
        C47H_drop_SWARMGPT_BATTLEFIELD_TRIAGE drop.
        """
        prefixes = self.healthy_prefixes
        schemed_filenames = set(LEDGER_SCHEMAS.keys())

        whitelisted_no_schema = []   # in (a) but not in (b) — F10 risk
        schemed_not_whitelisted = []  # in (b) but not in (a) — F12 risk
        alias_target_missing = []    # alias points to a schema that does not exist
        alias_source_unreachable = []  # alias source not whitelisted, target may be

        for fname in sorted(self.healthy_schemas):
            if fname in schemed_filenames:
                continue
            # Aliased to a schemed file?
            if SCHEMA_ALIASES.get(fname) in schemed_filenames:
                continue
            whitelisted_no_schema.append(fname)

        for fname in sorted(schemed_filenames):
            if fname in self.healthy_schemas:
                continue
            if any(fname.startswith(p) for p in prefixes):
                continue
            # Aliased back?
            inv = [src for src, tgt in SCHEMA_ALIASES.items() if tgt == fname]
            if any(src in self.healthy_schemas for src in inv):
                continue
            schemed_not_whitelisted.append(fname)

        for src, tgt in sorted(SCHEMA_ALIASES.items()):
            if tgt not in schemed_filenames:
                alias_target_missing.append((src, tgt))
            if src not in self.healthy_schemas and not any(
                src.startswith(p) for p in prefixes
            ):
                alias_source_unreachable.append((src, tgt))

        return {
            "whitelisted_no_schema":    whitelisted_no_schema,
            "schemed_not_whitelisted":  schemed_not_whitelisted,
            "alias_target_missing":     alias_target_missing,
            "alias_source_unreachable": alias_source_unreachable,
        }


def _print_consistency_report(report: dict) -> None:
    print("\n=== REGISTRY COHERENCE REPORT (innate / canonical / alias) ===")
    f10 = report["whitelisted_no_schema"]
    f12 = report["schemed_not_whitelisted"]
    atm = report["alias_target_missing"]
    asu = report["alias_source_unreachable"]
    print(f"  F10-risk  whitelisted_no_schema    : {len(f10):4d}")
    print(f"  F12-risk  schemed_not_whitelisted  : {len(f12):4d}")
    print(f"  alias_target_missing               : {len(atm):4d}")
    print(f"  alias_source_unreachable           : {len(asu):4d}")
    if f12:
        print("  ── F12 details (schema registered but innate whitelist missing) ──")
        for fname in f12[:10]:
            print(f"       · {fname}")
        if len(f12) > 10:
            print(f"       … and {len(f12) - 10} more")
    if atm:
        print("  ── alias_target_missing ──")
        for src, tgt in atm[:10]:
            print(f"       · {src!r}  →  {tgt!r}  (target unregistered)")
    print()


if __name__ == "__main__":
    print("\n=== SIFTA ONCOLOGY DAEMON v3 (LAYERED MACROPHAGE) ===")

    oncology = SwarmOncology()
    report = oncology.detect_metastasis()

    print(f"  scanned          : {report['scanned']:4d}")
    print(f"  innate_self      : {report['innate_self']:4d}   (Layer 1 spared)")
    print(f"  cosmetic_skipped : {report['cosmetic_skipped']:4d}   (Layer 0)")
    print(f"  malignant        : {report['malignant']:4d}   (Layer 1 verdict)")
    print(f"    └ novel        : {report['novel_anomalies']:4d}   (CRISPR first sighting)")
    print(f"    └ known        : {report['known_anomalies']:4d}   (CRISPR repeat)")
    print(f"  CRISPR repertoire: {len(oncology.crispr.spacers):4d} / {oncology.crispr.memory_limit}")

    if report["malignant"] == 0:
        print("\n[+] Substrate clean. Innate immunity intact, adaptive memory bounded.")
    else:
        print(f"\n[*] {report['malignant']} active hallucinations tracked "
              f"({report['novel_anomalies']} novel, {report['known_anomalies']} repeat).")

    # Diagnostic only — does not fail the run.
    _print_consistency_report(oncology.verify_registry_consistency())
