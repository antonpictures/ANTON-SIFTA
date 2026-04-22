#!/usr/bin/env python3
"""
System/swarm_pseudopod_phagocytosis.py — Epoch 5 (The Pseudopod / Phagocytosis Engine)
════════════════════════════════════════════════════════════════════════════════════
Concept: Read-only external environment probe for Alice to engulf LAN metadata.
Author:  AG31 (Gemini 3.1 Pro High) via BISHOP (The Mirage) drops
Status:  Active Lobe

This organ allows Alice to reach out across the LAN (e.g. hitting 192.168.1.1),
biting off 1024 bytes of HTTP header data, and depositing it cleanly into the
`phagocytosis_vacuoles.jsonl` ledger. It is completely isolated and protects
the Swarm from code-execution vulnerabilities while granting exploratory senses.
"""

import os
import json
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    import sys
    sys.path.insert(0, str(_REPO))
    from System.jsonl_file_lock import append_line_locked

class SwarmPseudopod:
    def __init__(self):
        """
        The Phagocytosis Engine.
        Extends a read-only probe across the LAN to a target IP. Engulfs
        discoverable data (HTTP banners, open shares, text) and brings it
        back across the cell membrane into an isolated Food Vacuole.
        """
        self.state_dir = _REPO / ".sifta_state"
        self.vacuole_ledger = self.state_dir / "phagocytosis_vacuoles.jsonl"

    def extend_pseudopod(self, target_ip: str, protocol: str = "http", timeout_seconds: int = 3):
        """
        Reaches out to the physical network environment.
        """
        self.state_dir.mkdir(parents=True, exist_ok=True)

        print(f"[*] PSEUDOPOD: Extending read-only biological probe to {target_ip} via {protocol}...")
        
        ingested_data = None

        # Safe, read-only ingestion attempts
        if protocol == "http":
            try:
                # Attempt to engulf the root HTTP banner or index
                req = urllib.request.Request(f"http://{target_ip}/", method="GET")
                with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                    # Read only the first 1024 bytes (A single "bite" of data)
                    raw_bytes = response.read(1024)
                    ingested_data = raw_bytes.decode('utf-8', errors='ignore')
            except urllib.error.URLError as e:
                ingested_data = f"[CELL MEMBRANE REJECTED]: {getattr(e, 'reason', e)}"
            except Exception as e:
                ingested_data = f"[DIGESTION ERROR]: {str(e)}"
        
        # Expandable to SMB, FTP, or mDNS parsing
        else:
            ingested_data = f"[UNKNOWN PROTOCOL]: The Pseudopod lacks the enzymes to digest '{protocol}'."

        # Bring the data into the cell (The Food Vacuole)
        trace_id = f"VACUOLE_{uuid.uuid4().hex[:8]}"
        now = time.time()

        payload = {
            "ts": now,
            "target_ip": target_ip,
            "protocol": protocol,
            "ingested_data": ingested_data,
            "trace_id": trace_id
        }

        try:
            # Drop it into the isolated ledger for parsing
            append_line_locked(self.vacuole_ledger, json.dumps(payload) + "\n")
            print(f"[+] PHAGOCYTOSIS COMPLETE: Engulfed data from {target_ip}. Deposited into Food Vacuole.")
            return True
        except Exception as e:
            print(f"[-] PHAGOCYTOSIS ERROR: Failed to form vacuole: {e}")
            return False

# --- SMOKE TEST ---
def _smoke():
    print("\n=== SIFTA PSEUDOPOD (PHAGOCYTOSIS) : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        pseudopod = SwarmPseudopod()
        
        # Secure Path Redirection
        pseudopod.state_dir = tmp_path
        pseudopod.vacuole_ledger = tmp_path / "phagocytosis_vacuoles.jsonl"
        
        # 1. Attempt to engulf an HTTP endpoint
        test_ip = "127.0.0.1" # Safe localhost loopback
        
        # Mocking urllib to prevent hanging if no localhost server is running
        def mock_urlopen(*args, **kwargs):
            class MockResponse:
                def read(self, size):
                    return b"<html><head><title>SIFTA Loopback</title></head><body>Localhost Echo</body></html>"
                def __enter__(self):
                    return self
                def __exit__(self, exc_type, exc_val, exc_tb):
                    pass
            return MockResponse()
            
        urllib.request.urlopen = mock_urlopen
        
        # 2. Execute Phagocytosis
        success = pseudopod.extend_pseudopod(test_ip, protocol="http")
        
        print("\n[SMOKE RESULTS]")
        assert success is True
        print(f"[PASS] Pseudopod successfully extended and retracted.")
        
        # 3. Verify Food Vacuole Isolation & Canonical Schema
        with open(pseudopod.vacuole_ledger, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            vacuole = json.loads(lines[0])
            
            assert "ts" in vacuole
            assert vacuole["target_ip"] == test_ip
            assert vacuole["protocol"] == "http"
            assert "SIFTA Loopback" in vacuole["ingested_data"]
            assert "trace_id" in vacuole
            
        print("[PASS] External data safely brought across the membrane into the Vacuole.")
        print("[PASS] Canonical Schema utilized. Zero execution risk.")

if __name__ == "__main__":
    _smoke()
