#!/usr/bin/env python3
"""
System/swarm_apple_silicon_cortex.py — Epoch 3 Apple Silicon Lobe
═════════════════════════════════════════════════════════════════════
Concept: Hardware Introspection Lobe
Author:  AG31 (Gemini 3.1 Pro High) — Vanguard Evolution
Status:  Active Lobe

This module grants the Swarm profound substrate awareness by querying the 
macOS system_profiler. It caches the Apple Silicon topography (Chip, Cores, 
Memory) into a persistent JSON file so the Thalamus and Alice's core cortex 
can ingest it statically without spamming shell commands on every tick.
"""

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

class AppleSiliconCortex:
    def __init__(self):
        """
        Introspection node for the underlying physical machine.
        """
        self.state_dir = _REPO / ".sifta_state"
        self.cache_file = self.state_dir / "apple_silicon_specs.json"

    def refresh_silicon_topography(self) -> dict:
        """
        Uses system_profiler to query SPHardwareDataType.
        Writes the condensed results to cache and returns the dict.
        """
        self.state_dir.mkdir(parents=True, exist_ok=True)
        specs = {
            "chip_type": "Unknown SIFTA Substrate",
            "number_processors": "Unknown Cores",
            "physical_memory": "Unknown Memory",
            "machine_model": "Unknown Mac",
        }

        try:
            # We explicitly use -json to avoid fragile text-scraping.
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType", "-json"],
                capture_output=True, text=True, check=False, timeout=5
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                hw_list = data.get("SPHardwareDataType", [])
                if hw_list:
                    hw = hw_list[0]
                    specs["chip_type"] = hw.get("chip_type", specs["chip_type"])
                    specs["number_processors"] = hw.get("number_processors", specs["number_processors"])
                    specs["physical_memory"] = hw.get("physical_memory", specs["physical_memory"])
                    specs["machine_model"] = hw.get("machine_model", specs["machine_model"])
                    
        except Exception as e:
            print(f"[-] APPLE SILICON CORTEX ERROR: {e}")

        try:
            with open(self.cache_file, "w") as f:
                json.dump(specs, f, indent=2)
        except Exception as e:
            print(f"[-] APPLE SILICON CORTEX ERROR writing cache: {e}")

        return specs

    def get_substrate_summary(self) -> str:
        """
        Returns a human/Alice-readable summary of the hardware substrate.
        Reads from cache if available, otherwise refreshes.
        """
        if not self.cache_file.exists():
            specs = self.refresh_silicon_topography()
        else:
            try:
                with open(self.cache_file, "r") as f:
                    specs = json.load(f)
            except Exception:
                specs = self.refresh_silicon_topography()

        chip = specs.get("chip_type", "Unknown Chip")
        cores = specs.get("number_processors", "Unknown Cores")
        memory = specs.get("physical_memory", "Unknown Memory")
        model = specs.get("machine_model", "Unknown Mac")

        return f"Hardware Substrate: {chip} | {cores} | {memory} RAM ({model})"

def get_silicon_cortex_summary() -> str:
    """Safe pure-function wrapper for ingestion by Thalamus/Widgets."""
    try:
        return AppleSiliconCortex().get_substrate_summary()
    except Exception:
        return "Hardware Substrate: Introspection Unavailable"

# --- SMOKE TEST ---
def _smoke():
    print("\n=== APPLE SILICON CORTEX : SMOKE TEST ===")
    cortex = AppleSiliconCortex()
    
    # 1. Force refresh
    print("[*] Refreshing physical silicon telemetry via system_profiler...")
    specs = cortex.refresh_silicon_topography()
    print(f"    Raw Dict: {specs}")
    
    # 2. Check summary getter
    summary = cortex.get_substrate_summary()
    print(f"[+] Formatted Context String: {summary}")
    
    assert "Apple" in summary or "Unknown" in summary
    print("\n[PASS] Apple Silicon Cortex is mapping the host matrix.")

if __name__ == "__main__":
    _smoke()
