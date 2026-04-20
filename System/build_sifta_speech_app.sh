#!/usr/bin/env bash
# System/build_sifta_speech_app.sh
# ══════════════════════════════════════════════════════════════════════
# Script to compile the Apple Native STT bridge and wrap it in an
# App Bundle to bypass macOS TCC (Transparency, Consent, and Control)
# SIGABRT restrictions on bare binaries.

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_DIR="$(dirname "$DIR")"
STATE_DIR="${REPO_DIR}/.sifta_state"
SRC_FILE="${STATE_DIR}/sifta_speech_src.swift"
APP_DIR="${STATE_DIR}/SiftaSpeech.app"
BIN_DIR="${APP_DIR}/Contents/MacOS"
INFO_PLIST="${APP_DIR}/Contents/Info.plist"

echo "[*] Constructing TCC-Compliant App Bundle: SiftaSpeech.app..."

# 1. Ensure source exists
if [ ! -f "$SRC_FILE" ]; then
    echo "[!] Source file not found: $SRC_FILE"
    exit 1
fi

# 2. Re-create bundle structure
rm -rf "$APP_DIR"
mkdir -p "$BIN_DIR"

# 3. Create Info.plist
cat << 'EOF' > "$INFO_PLIST"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>com.antonpictures.siftaspeech</string>
    <key>CFBundleName</key>
    <string>SiftaSpeech</string>
    <key>CFBundleExecutable</key>
    <string>sifta_speech</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSSpeechRecognitionUsageDescription</key>
    <string>SIFTA Swarm OS requires Speech Recognition to biologically parse Wernicke acoustics.</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>SIFTA Swarm OS requires Microphone access for stigmergic auditory ingress.</string>
    <key>LSBackgroundOnly</key>
    <true/>
</dict>
</plist>
EOF

# 4. Compile the Swift Source
echo "[*] Compiling sifta_speech Swift bridging code..."
swiftc -O "$SRC_FILE" -o "${BIN_DIR}/sifta_speech"

# 5. Ad-Hoc Codesign the Bundle
echo "[*] Applying local ad-hoc codesign to bundle..."
codesign --force --sign - "$APP_DIR"

echo "[+] SiftaSpeech.app successfully built! Path: $APP_DIR"
echo "[+] The macOS kernel will now respect the bundle and prompt for TCC Speech Authorization."
