#!/usr/bin/env bash
# Build a local Python.app wrapper with Camera/Microphone TCC usage strings.
# Use this app's Python executable to launch SIFTA when bare Homebrew Python
# enumerates cameras but macOS refuses frames without showing an Allow dialog.

set -euo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_DIR="$(dirname "$DIR")"
STATE_DIR="${REPO_DIR}/.sifta_state"
SRC_APP=""
if [ ! -d "$SRC_APP" ]; then
  SRC_APP="$(python3 - <<'PY'
import sys
from pathlib import Path
base = Path(sys.executable).resolve()
for parent in [base, *base.parents]:
    candidate = parent / "Resources" / "Python.app"
    if candidate.is_dir():
        print(candidate)
        break
PY
)"
fi

if [ -z "${SRC_APP:-}" ] || [ ! -d "$SRC_APP" ]; then
  echo "[!] Could not find Python.app for this Python framework." >&2
  exit 1
fi

APP_DIR="${STATE_DIR}/SiftaPythonTCC.app"
INFO_PLIST="${APP_DIR}/Contents/Info.plist"

rm -rf "$APP_DIR"
mkdir -p "$STATE_DIR"
cp -R "$SRC_APP" "$APP_DIR"

python3 - "$INFO_PLIST" <<'PY'
import plistlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = plistlib.loads(path.read_bytes())
data["CFBundleIdentifier"] = "com.antonpictures.siftapython.tcc"
data["CFBundleName"] = "SiftaPythonTCC"
data["CFBundleDisplayName"] = "SiftaPythonTCC"
data["NSCameraUsageDescription"] = "SIFTA needs Camera access for Alice's visual organ on this local Mac."
data["NSMicrophoneUsageDescription"] = "SIFTA needs Microphone access for Alice's auditory organ on this local Mac."
path.write_bytes(plistlib.dumps(data, sort_keys=False))
PY

codesign --force --deep --sign - "$APP_DIR"
echo "$APP_DIR"
