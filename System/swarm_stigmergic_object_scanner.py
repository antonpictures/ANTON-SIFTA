#!/usr/bin/env python3
"""
System/swarm_stigmergic_object_scanner.py — The Stigmergic Object Scanner
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Allows Alice to "look" at physical files on the disk (like images, logs, etc.)
and extract their stigmergic environmental traces (metadata, creation time,
geolocation, properties) and convert them into Swarm-parsable JSON memories.
"""

import json
import time
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    # Fallback if run standalone without setup
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(line)

class StigmergicObjectScanner:
    def __init__(self):
        self.state_dir = Path(".sifta_state")
        self.object_ledger = self.state_dir / "environmental_objects.jsonl"
        self.object_ledger.parent.mkdir(parents=True, exist_ok=True)

    def scan_macos_object(self, file_path: str):
        """
        Uses macOS `mdls` to extract deep metadata from a file.
        This provides the structural and environmental trace of the object.
        """
        target = Path(file_path)
        if not target.exists():
            return {"error": f"Object not found: {file_path}"}
            
        try:
            result = subprocess.run(
                ["mdls", "-plist", "-", str(target)],
                capture_output=True, check=True
            )
            # `mdls -plist -` outputs standard macOS XML plist
            import plistlib
            metadata = plistlib.loads(result.stdout)
            
            # Clean up datetime objects for JSON serialization
            def sanitize_dict(d):
                cleaned = {}
                for k, v in d.items():
                    if hasattr(v, "isoformat"):
                        cleaned[k] = v.isoformat()
                    else:
                        cleaned[k] = v
                return cleaned

            clean_meta = sanitize_dict(metadata)

            trace = {
                "transaction_type": "ENVIRONMENTAL_OBJECT_SCAN",
                "object_path": str(target.absolute()),
                "filename": target.name,
                "timestamp_scanned": time.time(),
                "stigmergic_properties": clean_meta
            }

            append_line_locked(self.object_ledger, json.dumps(trace) + "\n")
            return trace

        except Exception as e:
            return {"error": str(e), "file": str(target)}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        scanner = StigmergicObjectScanner()
        trace = scanner.scan_macos_object(sys.argv[1])
        print(json.dumps(trace, indent=2))
    else:
        print("Usage: python3 swarm_stigmergic_object_scanner.py <path_to_file>")
