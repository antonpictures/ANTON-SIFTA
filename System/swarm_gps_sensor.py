#!/usr/bin/env python3
"""
System/swarm_gps_sensor.py — CoreLocation Sensory Bridge
══════════════════════════════════════════════════════════════════════
SIFTA OS — stigmergic cognitive suite

Leverages macOS native CoreLocation to extract absolute position data.
This serves as the Phase 2 'Owner Genesis GPS Anchor' sensory organ.
"""

import json
import time
import subprocess
import sys
import os
import math
import tempfile
import threading
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
    def __init__(self, state_dir=None):
        self.state_dir = Path(state_dir) if state_dir is not None else _REPO / ".sifta_state"
        self.ledger = self.state_dir / "gps_traces.jsonl"
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.extractor_bin = self.state_dir / "sifta_gps_sensor_v2"
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
        manager.requestWhenInUseAuthorization()
        manager.startUpdatingLocation()
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        if let location = locations.last {
            // Only accept reasonably recent location fixes
            if location.horizontalAccuracy < 0 || abs(location.timestamp.timeIntervalSinceNow) > 300 { return }
            
            let json = """
            {
                "status": "SUCCESS",
                "latitude": \(location.coordinate.latitude),
                "longitude": \(location.coordinate.longitude),
                "altitude": \(location.altitude),
                "accuracy": \(location.horizontalAccuracy),
                "observed_at": \(location.timestamp.timeIntervalSince1970),
                "source": "macos_corelocation"
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
        swift_src = self.state_dir / "gps_src_v2.swift"
        swift_src.write_text(swift_code)
        try:
            print("[*] Compiling native Swift GPS bridge...")
            subprocess.run(["swiftc", str(swift_src), "-o", str(self.extractor_bin)], check=True,
                           capture_output=True, timeout=60)
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

_REFRESH_LOCK = threading.Lock()
_LAST_ATTEMPT = None


def read_location_snapshot(*, state_dir=None, now=None, max_age=300) -> dict:
    """Accept only dated, finite native fixes. Timezone never implies GPS."""
    path = Path(state_dir) if state_dir is not None else _REPO / ".sifta_state"
    try:
        data = json.loads((path / "mac_location_latest.json").read_text())
        if data.get("status") != "SUCCESS":
            return {"status": str(data.get("status") or "UNAVAILABLE")}
        lat, lon, accuracy, observed = (float(data[k]) for k in
                                       ("latitude", "longitude", "accuracy", "observed_at"))
        age = (time.time() if now is None else float(now)) - observed
        if not all(math.isfinite(x) for x in (lat, lon, accuracy, observed, age)):
            return {"status": "INVALID"}
        if data.get("source") != "macos_corelocation" or not (-90 <= lat <= 90 and -180 <= lon <= 180) or accuracy < 0:
            return {"status": "INVALID"}
        if age < -5 or age > max_age:
            return {"status": "STALE"}
        return {"status": "SUCCESS", "latitude": lat, "longitude": lon,
                "accuracy": accuracy, "observed_at": observed, "age_seconds": max(0, age),
                "source": "macos_corelocation"}
    except (OSError, ValueError, TypeError, KeyError):
        return {"status": "UNAVAILABLE"}


def refresh_location(*, state_dir=None) -> dict:
    """Bounded native request; persist success OR failure, never disguise an old fix."""
    path = Path(state_dir) if state_dir is not None else _REPO / ".sifta_state"
    path.mkdir(parents=True, exist_ok=True)
    try:
        data = SwarmGPSSensor(state_dir=path).get_current_location()
    except Exception as exc:
        data = {"status": "ERROR", "error": type(exc).__name__}
    data = {**data, "sampled_at": time.time()}
    with tempfile.NamedTemporaryFile("w", dir=path, delete=False) as handle:
        json.dump(data, handle)
        name = handle.name
    os.chmod(name, 0o600)
    os.replace(name, path / "mac_location_latest.json")
    return data


def request_location_refresh() -> bool:
    """Refresh at boot/owner turns, at most every five minutes, off the UI thread."""
    global _LAST_ATTEMPT
    if sys.platform != "darwin" or not _REFRESH_LOCK.acquire(blocking=False):
        return False
    now = time.monotonic()
    if _LAST_ATTEMPT is not None and now - _LAST_ATTEMPT < 300:
        _REFRESH_LOCK.release()
        return False
    _LAST_ATTEMPT = now

    def run():
        try:
            refresh_location()
        finally:
            _REFRESH_LOCK.release()

    threading.Thread(target=run, name="alice-location-refresh", daemon=True).start()
    return True


def location_prompt_block(*, public=False, state_dir=None, now=None) -> str:
    if public:
        return "Physical host location is private and is not supplied to visitor sessions. Do not infer it from timezone."
    data = read_location_snapshot(state_dir=state_dir, now=now)
    if data["status"] != "SUCCESS":
        return (f"CURRENT MAC LOCATION: {data['status']}. No fresh native location fix. "
                "Do not claim a current city from old journal entries or timezone settings. "
                "macOS Location Services permission may be required.")
    return (f"CURRENT MAC LOCATION: native CoreLocation latitude={data['latitude']:.5f}, "
            f"longitude={data['longitude']:.5f}, accuracy_radius_m={data['accuracy']:.0f}, "
            f"age_seconds={data['age_seconds']:.0f}. City name not reverse-geocoded. "
            "This is an approximate sensor fix, not certainty. Keep coordinates private.")


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
