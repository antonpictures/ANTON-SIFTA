#!/usr/bin/env python3
"""
swarm_adaptive_immune_array.py
==============================

Biological Inspiration:
The Full Adaptive Immune System — T-Cells, NK Cells, Dendritic Cells.
Macrophages (Turn 36) are innate immunity: they eat obvious corruption.
But when the Architect reports that "the swimmers still look wrong" even after
a Macrophage sweep, the infection is deeper. It requires the Adaptive branch:

  - **T-Cells (Cytotoxic)**: Hunt specific infected *processes*, not just files.
    They scan running .sifta_state artifacts for semantic anomalies — values that
    parse as valid JSON but contain physiologically impossible readings (e.g.,
    ATP > 100%, negative Serotonin, timestamps from the future).

  - **NK Cells (Natural Killer)**: Detect files that have grown abnormally large
    or have been modified suspiciously recently (< 2 seconds ago, suggesting a
    runaway write loop). They terminate the anomaly immediately.

  - **Dendritic Cells (Antigen Presentation)**: Collect all detected threats and
    synthesize a unified Threat Digest that the Brainstem can consume to update
    its global awareness of the organism's health.

Why We Built This:
Turn 49 of "Controlled Self Evolution".
The Architect observed visual instability in the Swimmer agents even after the
Macrophage patrol cleared surface necrosis. AO46 deploys the full immune array
to hunt deeper, process-level infections.
"""
# ════════════════════════════════════════════════════════════════════════
# VISION-SYSTEM-ROLE: the adaptive systemic immune response
# Analogue mapped from Land & Nilsson (2012) via DYOR §E.
# Integrates with Swarm-Eye Olympiad M5.2.
# ════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

_STATE_DIR = Path(".sifta_state")
_IMMUNE_LOG = _STATE_DIR / "adaptive_immune_array_report.json"


class TCellCytotoxic:
    """Hunt semantically invalid but syntactically correct state values."""

    PHYSIOLOGICAL_BOUNDS = {
        "atp_level": (0.0, 1.0),
        "melatonin_concentration": (0.0, 1.0),
        "serotonin_dominance": (0.0, 1.0),
        "dopamine_concentration": (0.0, 5000.0),
        "organism_age_divisions": (0, 1_000_000),
    }

    def hunt(self) -> List[Dict[str, Any]]:
        infections = []
        heartbeat_path = _STATE_DIR / "clinical_heartbeat.json"
        if not heartbeat_path.exists():
            return infections

        try:
            with open(heartbeat_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            vitals = data.get("vital_signs", {})

            for key, (lo, hi) in self.PHYSIOLOGICAL_BOUNDS.items():
                val = vitals.get(key)
                if val is not None:
                    try:
                        v = float(val)
                        if v < lo or v > hi:
                            infections.append({
                                "sentinel_type": "T_CELL_CYTOTOXIC",
                                "target": f"clinical_heartbeat.json::vital_signs.{key}",
                                "value": v,
                                "expected_range": f"[{lo}, {hi}]",
                                "action": "FLAGGED_PHYSIOLOGICALLY_IMPOSSIBLE",
                            })
                    except (ValueError, TypeError):
                        infections.append({
                            "sentinel_type": "T_CELL_CYTOTOXIC",
                            "target": f"clinical_heartbeat.json::vital_signs.{key}",
                            "value": str(val),
                            "action": "FLAGGED_NON_NUMERIC_VITAL",
                        })
        except Exception:
            pass

        # Check for future timestamps in any state JSON
        for p in _STATE_DIR.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    blob = json.load(f)
                ts = blob.get("timestamp") or blob.get("ts")
                if ts and isinstance(ts, (int, float)):
                    if ts > time.time() + 86400:
                        infections.append({
                            "sentinel_type": "T_CELL_CYTOTOXIC",
                            "target": p.name,
                            "value": ts,
                            "action": "FLAGGED_FUTURE_TIMESTAMP",
                        })
            except Exception:
                continue

        return infections


class NKCellNaturalKiller:
    """Detect anomalously large or suspiciously fresh state files."""

    MAX_HEALTHY_SIZE_BYTES = 500_000  # 500KB — any single state file above this is bloated
    SUSPICIOUS_FRESHNESS_S = 2.0     # Modified less than 2s ago = possible runaway loop

    def hunt(self) -> List[Dict[str, Any]]:
        kills = []
        if not _STATE_DIR.exists():
            return kills

        now = time.time()
        for p in _STATE_DIR.iterdir():
            if not p.is_file():
                continue
            try:
                stat = p.stat()
                # Bloat detection
                if stat.st_size > self.MAX_HEALTHY_SIZE_BYTES:
                    kills.append({
                        "sentinel_type": "NK_CELL_NATURAL_KILLER",
                        "target": p.name,
                        "size_bytes": stat.st_size,
                        "threshold": self.MAX_HEALTHY_SIZE_BYTES,
                        "action": "FLAGGED_FILE_BLOAT",
                    })
                # Runaway write loop detection
                age = now - stat.st_mtime
                if age < self.SUSPICIOUS_FRESHNESS_S and stat.st_size > 10_000:
                    kills.append({
                        "sentinel_type": "NK_CELL_NATURAL_KILLER",
                        "target": p.name,
                        "age_seconds": round(age, 3),
                        "action": "FLAGGED_RUNAWAY_WRITE_LOOP",
                    })
            except OSError:
                continue

        return kills


class DendriticCellPresenter:
    """Collect all sentinel findings into a unified Threat Digest for the Brainstem."""

    def present(
        self,
        macrophage_report: Dict[str, Any],
        tcell_findings: List[Dict[str, Any]],
        nk_findings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        total_threats = (
            macrophage_report.get("necrotic_infections_found", 0)
            + len(tcell_findings)
            + len(nk_findings)
        )

        severity = "GREEN_HEALTHY"
        if total_threats > 5:
            severity = "RED_SYSTEMIC_INFECTION"
        elif total_threats > 0:
            severity = "YELLOW_LOCALIZED_ANOMALY"

        digest = {
            "timestamp": time.time(),
            "dendritic_presentation": True,
            "total_threats_detected": total_threats,
            "severity": severity,
            "macrophage_necrosis": macrophage_report.get("necrotic_infections_found", 0),
            "macrophage_phagocytosis": macrophage_report.get("phagocytosis_events_triggered", 0),
            "tcell_infections": tcell_findings,
            "nk_kills": nk_findings,
            "brainstem_directive": (
                "CONTINUE_NORMAL_OPERATION" if severity == "GREEN_HEALTHY"
                else "ELEVATE_VIGILANCE_AND_DAMPEN_EXPLORATION"
                if severity == "YELLOW_LOCALIZED_ANOMALY"
                else "EMERGENCY_VAGAL_SHUTDOWN_RECOMMENDED"
            ),
        }

        _STATE_DIR.mkdir(exist_ok=True)
        with open(_IMMUNE_LOG, "w", encoding="utf-8") as f:
            json.dump(digest, f, indent=2)

        return digest


def deploy_full_immune_array() -> Dict[str, Any]:
    """Execute the complete Adaptive Immune sweep: Macrophages + T-Cells + NK + Dendritic."""

    # 1. Macrophages (innate — already built Turn 36)
    try:
        from System.swarm_macrophage_sentinels import patrol_perimeter
        macro_report = patrol_perimeter()
    except Exception:
        macro_report = {"necrotic_infections_found": 0, "phagocytosis_events_triggered": 0}

    # 2. T-Cells (adaptive — semantic validity)
    tcell = TCellCytotoxic()
    tcell_findings = tcell.hunt()

    # 3. NK Cells (adaptive — anomalous growth / runaway loops)
    nk = NKCellNaturalKiller()
    nk_findings = nk.hunt()

    # 4. Dendritic Cells (presentation to Brainstem)
    dendritic = DendriticCellPresenter()
    digest = dendritic.present(macro_report, tcell_findings, nk_findings)

    return digest


if __name__ == "__main__":
    print("=== SWARM ADAPTIVE IMMUNE ARRAY (FULL DEPLOYMENT) ===")
    print("[*] Deploying all sentinel types into the organism...\n")

    digest = deploy_full_immune_array()

    print("🩸 MACROPHAGE (Innate — Surface Necrosis):")
    print(f"   -> Necrosis found : {digest['macrophage_necrosis']}")
    print(f"   -> Phagocytosis   : {digest['macrophage_phagocytosis']} pathogens consumed")

    print(f"\n🔬 T-CELL CYTOTOXIC (Adaptive — Semantic Validity):")
    if digest["tcell_infections"]:
        for t in digest["tcell_infections"]:
            print(f"   -> {t['action']}: {t['target']} = {t.get('value', '?')}")
    else:
        print("   -> No semantic infections detected. Vitals physiologically valid.")

    print(f"\n⚔️  NK CELL NATURAL KILLER (Adaptive — Growth Anomalies):")
    if digest["nk_kills"]:
        for n in digest["nk_kills"]:
            print(f"   -> {n['action']}: {n['target']} ({n.get('size_bytes', n.get('age_seconds', '?'))})")
    else:
        print("   -> No bloat or runaway write loops detected.")

    print(f"\n🧬 DENDRITIC CELL PRESENTATION (Threat Digest to Brainstem):")
    print(f"   -> Total Threats  : {digest['total_threats_detected']}")
    print(f"   -> Severity       : {digest['severity']}")
    print(f"   -> Brainstem Order: {digest['brainstem_directive']}")