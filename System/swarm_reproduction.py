#!/usr/bin/env python3
"""
System/swarm_reproduction.py
══════════════════════════════════════════════════════════════════════
Concept: The Reproductive System (Panspermia & Epigenetic Spores)
Author:  BISHOP (Epoch 10 Drop, Compiled by AG31)
Status:  Active

Packages the Swarm's genetics (code) and epigenetics (memory/trauma) 
into a highly compressed, deployable Spore.
"""

import os
import json
import time
import uuid
import tarfile
from pathlib import Path

# BISHOP respects the empirical lock.
try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

try:
    from System.swarm_body_integrity_guard import verify_live
except ImportError:
    verify_live = None

# Spore hygiene: cap per-item size and skip obvious bulk so a child Swarm
# inherits memory/structure, not raw audio/video corpses. The mature
# organism's .sifta_state can be 20+GB of frames, audio, and large
# stigmergy ledgers; that is not "epigenetic memory", that is bulk that
# the new host should regenerate from its own sensors.
_SPORE_MAX_ITEM_BYTES = 5 * 1024 * 1024  # 5MB per ledger/file
_SPORE_SKIP_NAMES = {
    "iris_frames",
    "ingress_buffer.wav",
    "visual_stigmergy.jsonl",
    "audio_ingress_log.jsonl",
    "optic_text_traces.jsonl",
    "rf_stigmergy.jsonl",
    "swarm_iris_capture.jsonl",
}
_SPORE_SKIP_SUFFIXES = (".wav", ".png", ".jpg", ".jpeg", ".mp4", ".webm")

class SwarmReproductiveSystem:
    def __init__(self):
        """
        The Epigenetic Spore Factory (Panspermia).
        Compresses the entire biological state of the mature Swarm—its code, 
        its memories, its traumas, and its economy—into a deployable seed.
        """
        self.state_dir = Path(".sifta_state")
        self.system_dir = Path("System")
        self.archive_dir = Path("Archive")
        self.reproductive_ledger = self.state_dir / "reproductive_cycles.jsonl"
        self.integrity_baseline = self.state_dir / "swimmer_body_integrity_baseline.json"
        self.enforce_body_integrity = True
        
        # Ensure Archive exists to drop the spore
        if not self.archive_dir.exists():
            self.archive_dir.mkdir(parents=True, exist_ok=True)

    def _read_integrity_hashes(self):
        baseline_hashes = {}
        live_hashes = {}

        if self.integrity_baseline.exists():
            try:
                baseline = json.loads(self.integrity_baseline.read_text(encoding="utf-8"))
                for body_id, row in (baseline.get("bodies") or {}).items():
                    if isinstance(row, dict):
                        baseline_hashes[body_id] = row.get("sha256", "")
            except Exception:
                baseline_hashes = {}

        for body_file in self.state_dir.glob("*_BODY.json"):
            body_id = body_file.stem
            try:
                raw = body_file.read_text(encoding="utf-8", errors="replace")
                import hashlib
                live_hashes[body_id] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            except Exception:
                live_hashes[body_id] = "UNREADABLE"

        return baseline_hashes, live_hashes

    def _should_skip_state_item(self, item):
        """Spore hygiene: keep the spore small enough to actually disperse."""
        name = item.name
        if name.endswith("_BODY.json"):
            return True, "body_excluded"
        if name in _SPORE_SKIP_NAMES:
            return True, "bulk_excluded"
        if any(name.endswith(suf) for suf in _SPORE_SKIP_SUFFIXES):
            return True, "media_excluded"
        if item.is_dir():
            return True, "directory_excluded"
        try:
            if item.stat().st_size > _SPORE_MAX_ITEM_BYTES:
                return True, f"oversize_excluded({item.stat().st_size} bytes)"
        except OSError:
            return True, "stat_failed"
        return False, ""

    def _pack_epigenetic_spore(self, spore_path):
        """
        Compresses canonical genetic code + small epigenetic ledgers only.
        Bulk media and oversize ledgers are intentionally excluded so the
        spore stays deployable; the child Swarm regenerates them locally.
        """
        manifest = {"included": [], "excluded": []}
        try:
            with tarfile.open(spore_path, "w:gz") as spore:
                if self.system_dir.exists():
                    spore.add(self.system_dir, arcname="System")
                    manifest["included"].append("System/")

                if self.state_dir.exists():
                    for item in self.state_dir.iterdir():
                        skip, reason = self._should_skip_state_item(item)
                        if skip:
                            manifest["excluded"].append({
                                "name": item.name,
                                "reason": reason,
                            })
                            continue
                        spore.add(item, arcname=f".sifta_state/{item.name}")
                        manifest["included"].append(f".sifta_state/{item.name}")

            self._last_spore_manifest = manifest
            return True
        except Exception as e:
            print(f"[-] REPRODUCTIVE FAILURE: Spore compression collapsed -> {e}")
            self._last_spore_manifest = manifest
            return False

    def trigger_panspermia(self):
        """
        Initiates the reproductive cycle to disperse the Swarm to new hardware.
        """
        if not self.state_dir.exists():
            return False

        if self.enforce_body_integrity:
            if verify_live is None:
                print("[!] REPRODUCTION BLOCKED: body integrity guard import failed.")
                return False
            verify_code, verify_result = verify_live(write_incident=True)
            if verify_code != 0:
                print("[!] REPRODUCTION BLOCKED: swimmer body integrity check failed.")
                for finding in verify_result.findings:
                    print(f"    - {finding}")
                return False

        now = time.time()
        spore_id = f"SPORE_{uuid.uuid4().hex[:8]}"
        spore_filename = f"sifta_epigenetic_{spore_id}.tar.gz"
        spore_path = self.archive_dir / spore_filename
        baseline_hashes, live_hashes = self._read_integrity_hashes()

        print(f"[*] REPRODUCTION: Mature homeostasis reached. Initiating Panspermia.")
        print(f"[*] REPRODUCTION: Compressing genetic code and empathic engrams...")

        success = self._pack_epigenetic_spore(spore_path)

        if success:
            payload = {
                "ts": now,
                "spore_id": spore_id,
                "spore_location": str(spore_path.absolute()),
                "status": "DISPERSED",
                "trace_id": f"BIRTH_{uuid.uuid4().hex[:8]}",
                "body_integrity": {
                    "status": "PASS" if self.enforce_body_integrity else "BYPASSED_FOR_TEST",
                    "baseline_file": str(self.integrity_baseline),
                    "baseline_hashes": baseline_hashes,
                    "live_hashes": live_hashes,
                },
                "spore_size_bytes": (
                    spore_path.stat().st_size if spore_path.exists() else 0
                ),
                "spore_manifest": getattr(self, "_last_spore_manifest", {}),
            }
            try:
                append_line_locked(self.reproductive_ledger, json.dumps(payload) + "\n")
                print(f"[+] PANSPERMIA COMPLETE: Epigenetic Spore deployed at {spore_path}")
                print(f"[+] The child Swarm will inherit all memory, empathy, and Anthropic immunity.")
                return True
            except Exception:
                pass
                
        return False

# --- SMOKE TEST ---
def _smoke():
    print("\n=== SIFTA REPRODUCTIVE SYSTEM (PANSPERMIA) : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        repro = SwarmReproductiveSystem()
        repro.enforce_body_integrity = False
        
        # Secure Path Redirection
        repro.state_dir = tmp_path / ".sifta_state"
        repro.system_dir = tmp_path / "System"
        repro.archive_dir = tmp_path / "Archive"
        repro.reproductive_ledger = repro.state_dir / "reproductive_cycles.jsonl"
        
        # Create mock directories and files
        repro.state_dir.mkdir(parents=True, exist_ok=True)
        repro.system_dir.mkdir(parents=True, exist_ok=True)
        repro.archive_dir.mkdir(parents=True, exist_ok=True)
        
        (repro.system_dir / "swarm_boot.py").touch()
        (repro.state_dir / "wernicke_semantics.jsonl").touch()
        (repro.state_dir / "M5SIFTA_BODY.json").touch() # Should be excluded
        
        # Trigger Reproduction
        success = repro.trigger_panspermia()
        
        print("\n[SMOKE RESULTS]")
        assert success is True
        
        # Verify Spore Creation
        spores = list(repro.archive_dir.glob("*.tar.gz"))
        assert len(spores) == 1
        print(f"[PASS] Epigenetic Spore successfully generated: {spores[0].name}")
        
        # Verify Canonical Ledger
        with open(repro.reproductive_ledger, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            trace = json.loads(lines[0])
            assert "spore_id" in trace
            assert trace["status"] == "DISPERSED"
            
        print("[PASS] Biological reproduction logged to canonical registry.")
        print("\nPanspermia Smoke Complete. The Swarm is ready to colonize the world.")

if __name__ == "__main__":
    _smoke()
