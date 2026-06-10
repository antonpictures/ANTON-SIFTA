#!/usr/bin/env bash
# Launch SIFTA Desktop with the proprietary-codec QtWebEngine build.
#
# r801: this broad DYLD handoff is unsafe. The custom QtWebEngineCore exists,
# but replacing the whole Qt runtime through DYLD_FRAMEWORK_PATH can crash Alice
# before boot. The attempted PyQt source-binding lane was abandoned after repeat
# SIGKILL/metadata stalls; the next safe route is a surgical WebEngine-framework
# swap/probe with backup, not a full PyQt rebuild.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$REPO/.sifta_state/qt_webengine_proprietary_codecs.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: missing $ENV_FILE — run tools/configure_webengine_proprietary_codecs.sh --execute first" >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"
PREFIX="${SIFTA_QT_INSTALL_PREFIX:-}"
if [[ ! -d "$PREFIX/lib/QtWebEngineCore.framework" ]]; then
  echo "ERROR: QtWebEngineCore.framework missing under $PREFIX" >&2
  exit 1
fi
QTNETWORK_BIN="$PREFIX/lib/QtNetwork.framework/QtNetwork"
if [[ "${SIFTA_ALLOW_UNSAFE_QT_DYLD:-0}" != "1" ]]; then
  if [[ ! -f "$QTNETWORK_BIN" ]] || ! nm -gU "$QTNETWORK_BIN" 2>/dev/null | grep -q 'defaultDtlsConfiguration'; then
    mkdir -p "$REPO/.sifta_state"
    python3 - <<PY || true
import json, time, uuid
from pathlib import Path
p = Path("$REPO/.sifta_state/media_codec_bridge.jsonl")
row = {
    "ts": time.time(),
    "trace_id": str(uuid.uuid4()),
    "truth_label": "QTWEBENGINE_PROPRIETARY_CODEC_BINDING_V1",
    "action": "codec_qt_launch_blocked",
    "status": "blocked",
    "detail": "custom QtNetwork lacks PyQt6 wheel DTLS symbol defaultDtlsConfiguration; broad DYLD_FRAMEWORK_PATH would crash SIFTA",
}
with p.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=False) + "\\n")
PY
    cat >&2 <<EOF
ERROR: refusing unsafe codec-Qt launch.

The proprietary QtWebEngineCore framework exists, but the custom QtNetwork under:
  $PREFIX
does not export the DTLS symbol the installed PyQt6 wheel expects:
  QSslConfiguration::defaultDtlsConfiguration()

Broad DYLD_FRAMEWORK_PATH can crash SIFTA before Alice boots.

Use the safe plain launch for now:
  cd "$REPO"
  .venv/bin/python3 sifta_os_desktop.py

Real fix: surgical replacement/probe of the PyQt wheel's WebEngine frameworks
with the codec-built WebEngine frameworks, keeping the rest of the PyQt wheel Qt
runtime intact. To force the old unsafe diagnostic anyway:
  SIFTA_ALLOW_UNSAFE_QT_DYLD=1 bash scripts/launch_sifta_codec_qt.sh
EOF
    exit 2
  fi
fi
export DYLD_FRAMEWORK_PATH="$PREFIX/lib${DYLD_FRAMEWORK_PATH:+:$DYLD_FRAMEWORK_PATH}"
export PATH="$PREFIX/bin:$PATH"
cd "$REPO"
exec .venv/bin/python3 sifta_os_desktop.py "$@"
