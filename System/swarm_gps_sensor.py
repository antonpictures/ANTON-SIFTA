#!/usr/bin/env python3
"""
System/swarm_gps_sensor.py — CoreLocation Sensory Bridge
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Leverages macOS native CoreLocation to extract absolute position data.
This serves as the Phase 2 'Owner Genesis GPS Anchor' sensory organ.
"""

import json
import time
import subprocess
import sys
import os
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(line)

class SwarmGPSSensor:
    def __init__(self):
        self.state_dir = Path(".sifta_state")
        self.ledger = self.state_dir / "gps_traces.jsonl"
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.extractor_bin = self.state_dir / "sifta_gps_sensor"
        self._build_swift_extractor()

    def _build_swift_extractor(self):
        """Compiles a Swift binary to access macOS CoreLocation."""
        if self.extractor_bin.exists():
            return

        swift_code = r'''
import Foundation
import CoreLocation

class GPSSensor: NSObject, CLLocationManagerDelegate {
    var manager: CLLocationManager!
    var keepAlive = true

    override init() {
        super.init()
        manager = CLLocationManager()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
        manager.requestAlwaysAuthorization() 
        manager.startUpdatingLocation()
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        if let location = locations.last {
            // Only accept reasonably recent location fixes
            if location.horizontalAccuracy < 0 { return }
            
            let json = """
            {
                "status": "SUCCESS",
                "latitude": \(location.coordinate.latitude),
                "longitude": \(location.coordinate.longitude),
                "altitude": \(location.altitude),
                "accuracy": \(location.horizontalAccuracy)
            }
            """
            print(json)
            keepAlive = false
            exit(0)
        }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        let json = """
        {
            "status": "ERROR",
            "error": "\(error.localizedDescription)"
        }
        """
        print(json)
        keepAlive = false
        exit(1)
    }
}

let sensor = GPSSensor()
let runLoop = RunLoop.current

// Timeout logic to prevent hanging if permissions are denied silently
let timeoutDate = Date(timeIntervalSinceNow: 10.0)

while sensor.keepAlive && runLoop.run(mode: .default, before: Date(timeIntervalSinceNow: 0.1)) {
    if Date() > timeoutDate {
        let json = """
        {
            "status": "TIMEOUT",
            "error": "Failed to get location within 10 seconds. Check System Settings > Privacy & Security > Location Services."
        }
        """
        print(json)
        exit(1)
    }
}
'''
        swift_src = self.state_dir / "gps_src.swift"
        swift_src.write_text(swift_code)
        try:
            print("[*] Compiling native Swift GPS bridge...")
            subprocess.run(["swiftc", str(swift_src), "-o", str(self.extractor_bin)], check=True)
        except Exception as e:
            print(f"[FATAL] Failed to compile GPS binary: {e}")

    def get_current_location(self) -> dict:
        """Fetches the latest location fix via the native Swift binary."""
        if not self.extractor_bin.exists():
            return {"status": "ERROR", "error": "GPS binary unavailable"}
            
        try:
            # We add a python-side timeout just in case the Swift runloop gets fully stuck
            result = subprocess.run(
                [str(self.extractor_bin)], 
                capture_output=True, text=True, timeout=12
            )
            
            output = result.stdout.strip()
            if not output:
                # If command failed and printed to stderr
                if result.stderr:
                    output = json.dumps({"status": "ERROR", "error": result.stderr.strip()})
                else:
                    return {"status": "ERROR", "error": "No output from GPS binary."}
            
            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                return {"status": "ERROR", "error": f"Invalid JSON generated: {output}"}
            
            # Trace successful or failed read
            trace = {
                "transaction_type": "GPS_LOCATION_SENSE",
                "timestamp": time.time(),
                "payload": data
            }
            append_line_locked(self.ledger, json.dumps(trace) + "\n")
            return data
            
        except subprocess.TimeoutExpired:
            return {"status": "TIMEOUT", "error": "Python subprocess timed out waiting for Swift GPS bridge."}
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}

def _smoke():
    print("\\n=== SIFTA GPS SENSOR : SMOKE TEST ===")
    sensor = SwarmGPSSensor()
    print("[*] Requesting absolute fix from CoreLocation. This may take up to 10 seconds...")
    print("[!] Check for macOS Privacy prompts in the background if it hangs.")
    res = sensor.get_current_location()
    print("\\n[+] LOCATION SENSE COMPLETE:")
    print(json.dumps(res, indent=2))
    
    if res.get("status") == "SUCCESS":
        print("\\n[PASS] GPS Sensory Organ operational.")
    else:
        print("\\n[FAIL] SIFTA could not verify location.")

if __name__ == "__main__":
    _smoke()
