#!/usr/bin/env bash
# Build a tiny macOS app bundle that requests Camera permission through
# AVFoundation with NSCameraUsageDescription present in Info.plist.

set -euo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_DIR="$(dirname "$DIR")"
STATE_DIR="${REPO_DIR}/.sifta_state"
SRC_FILE="${STATE_DIR}/sifta_camera_tcc_src.swift"
APP_DIR="${STATE_DIR}/SiftaCameraTCC.app"
BIN_DIR="${APP_DIR}/Contents/MacOS"
INFO_PLIST="${APP_DIR}/Contents/Info.plist"

mkdir -p "$STATE_DIR"

cat > "$SRC_FILE" <<'EOF'
import AVFoundation
import Foundation

func statusName(_ status: AVAuthorizationStatus) -> String {
    switch status {
    case .authorized: return "authorized"
    case .denied: return "denied"
    case .restricted: return "restricted"
    case .notDetermined: return "notDetermined"
    @unknown default: return "unknown"
    }
}

let before = AVCaptureDevice.authorizationStatus(for: .video)
print("camera_authorization_before=\(statusName(before))")

if before == .notDetermined {
    let sem = DispatchSemaphore(value: 0)
    var granted = false
    AVCaptureDevice.requestAccess(for: .video) { ok in
        granted = ok
        print("camera_request_granted=\(ok)")
        sem.signal()
    }
    _ = sem.wait(timeout: .now() + 60)
    let after = AVCaptureDevice.authorizationStatus(for: .video)
    print("camera_authorization_after=\(statusName(after))")
    exit(granted ? 0 : 2)
}

let devices = AVCaptureDevice.DiscoverySession(
    deviceTypes: [.builtInWideAngleCamera, .externalUnknown],
    mediaType: .video,
    position: .unspecified
).devices
print("camera_devices=\(devices.map { $0.localizedName }.joined(separator: ","))")

exit(before == .authorized ? 0 : 2)
EOF

rm -rf "$APP_DIR"
mkdir -p "$BIN_DIR"

cat > "$INFO_PLIST" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>com.antonpictures.siftacameratcc</string>
    <key>CFBundleName</key>
    <string>SiftaCameraTCC</string>
    <key>CFBundleExecutable</key>
    <string>sifta_camera_tcc</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>NSCameraUsageDescription</key>
    <string>SIFTA needs Camera access for Alice's visual organ on this local Mac.</string>
    <key>LSBackgroundOnly</key>
    <true/>
</dict>
</plist>
EOF

swiftc -O "$SRC_FILE" -o "${BIN_DIR}/sifta_camera_tcc"
codesign --force --sign - "$APP_DIR"

echo "$APP_DIR"
