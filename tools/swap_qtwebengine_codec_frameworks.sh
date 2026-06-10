#!/usr/bin/env bash
# Surgically swap PyQt wheel WebEngine frameworks with the codec-built Qt 6.11
# WebEngine frameworks. This avoids broad DYLD_FRAMEWORK_PATH and avoids
# rebuilding PyQt from source.
#
# Usage:
#   bash tools/swap_qtwebengine_codec_frameworks.sh --dry-run
#   bash tools/swap_qtwebengine_codec_frameworks.sh --execute
#   bash tools/swap_qtwebengine_codec_frameworks.sh --probe
#   bash tools/swap_qtwebengine_codec_frameworks.sh --restore latest
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="$REPO/.sifta_state"
ENV_FILE="$STATE_DIR/qt_webengine_proprietary_codecs.env"
LEDGER="$STATE_DIR/media_codec_bridge.jsonl"
BACKUP_ROOT="$STATE_DIR/qtwebengine_framework_backups"
LATEST_FILE="$STATE_DIR/qtwebengine_framework_swap_latest"
MODE="${1:---dry-run}"
RESTORE_TARGET="${2:-latest}"

FRAMEWORKS=(
  QtWebEngineCore
  QtWebEngineWidgets
  QtWebEngineQuick
  QtWebEngineQuickDelegatesQml
)

append_receipt() {
  local action="$1" status="$2" detail="${3:-}"
  mkdir -p "$STATE_DIR"
  python3 - "$LEDGER" "$action" "$status" "$detail" <<'PY'
import json, sys, time, uuid
from pathlib import Path

p = Path(sys.argv[1])
row = {
    "ts": time.time(),
    "trace_id": str(uuid.uuid4()),
    "truth_label": "QTWEBENGINE_SURGICAL_FRAMEWORK_SWAP_V1",
    "action": sys.argv[2],
    "status": sys.argv[3],
    "detail": sys.argv[4],
}
p.parent.mkdir(parents=True, exist_ok=True)
with p.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
print(json.dumps(row, ensure_ascii=False))
PY
}

require_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: missing $ENV_FILE — run tools/configure_webengine_proprietary_codecs.sh --execute first" >&2
    exit 1
  fi
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  SRC_QT_PREFIX="${SIFTA_QT_INSTALL_PREFIX:-}"
  SRC_LIB="$SRC_QT_PREFIX/lib"
  if [[ ! -d "$SRC_LIB/QtWebEngineCore.framework" ]]; then
    echo "ERROR: codec QtWebEngineCore.framework missing under $SRC_LIB" >&2
    exit 1
  fi
  if [[ ! -x "$REPO/.venv/bin/python3" ]]; then
    echo "ERROR: missing $REPO/.venv/bin/python3" >&2
    exit 1
  fi
  DST_QT_PREFIX="$("$REPO/.venv/bin/python3" - <<'PY'
from PyQt6.QtCore import QLibraryInfo
print(QLibraryInfo.path(QLibraryInfo.LibraryPath.PrefixPath))
PY
)"
  DST_LIB="$DST_QT_PREFIX/lib"
  if [[ ! -d "$DST_LIB/QtWebEngineCore.framework" ]]; then
    echo "ERROR: PyQt wheel QtWebEngineCore.framework missing under $DST_LIB" >&2
    exit 1
  fi
}

framework_bin() {
  local root="$1" fw="$2"
  echo "$root/$fw.framework/Versions/A/$fw"
}

framework_sha() {
  local bin
  bin="$(framework_bin "$1" "$2")"
  if [[ -f "$bin" ]]; then
    shasum -a 256 "$bin" | awk '{print $1}'
  else
    echo "missing"
  fi
}

print_plan() {
  require_env
  cat <<EOF
SIFTA surgical QtWebEngine framework swap
Repo:        $REPO
Source Qt:   $SRC_QT_PREFIX
Target Qt:   $DST_QT_PREFIX
Backups:     $BACKUP_ROOT

Frameworks:
EOF
  for fw in "${FRAMEWORKS[@]}"; do
    printf '  %-34s src_sha=%s dst_sha=%s\n' \
      "$fw.framework" "$(framework_sha "$SRC_LIB" "$fw")" "$(framework_sha "$DST_LIB" "$fw")"
  done
}

probe_loaded_framework() {
  require_env
  local tmp pid loaded status
  tmp="$(mktemp "${TMPDIR:-/tmp}/sifta-webengine-probe.XXXXXX")"
  "$REPO/.venv/bin/python3" - <<'PY' >"$tmp" 2>&1 &
import json
import pathlib
import time
from PyQt6.QtCore import QLibraryInfo, QT_VERSION_STR, PYQT_VERSION_STR
from PyQt6.QtWebEngineCore import QWebEngineProfile

qt_prefix = pathlib.Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PrefixPath))
core = qt_prefix / "lib" / "QtWebEngineCore.framework" / "Versions" / "A" / "QtWebEngineCore"
print(json.dumps({
    "pyqt": PYQT_VERSION_STR,
    "qt": QT_VERSION_STR,
    "qt_prefix": str(qt_prefix),
    "core": str(core),
    "core_bytes": core.stat().st_size if core.exists() else 0,
    "profile_type": QWebEngineProfile.__name__,
}, sort_keys=True), flush=True)
time.sleep(4)
PY
  pid=$!
  sleep 1
  loaded="$(lsof -p "$pid" 2>/dev/null | awk '/QtWebEngineCore.framework.*QtWebEngineCore/ {print $NF; exit}' || true)"
  wait "$pid"
  status=$?
  cat "$tmp"
  rm -f "$tmp"
  echo "LOADED_QTWEBENGINECORE=${loaded:-missing}"
  if (( status != 0 )); then
    append_receipt "surgical_webengine_probe" "failed" "probe python failed status=$status loaded=${loaded:-missing}"
    return "$status"
  fi
  local expected
  expected="$DST_LIB/QtWebEngineCore.framework"
  if [[ "${loaded:-}" != "$expected"* ]]; then
    append_receipt "surgical_webengine_probe" "failed" "loaded=${loaded:-missing}; expected prefix=$expected"
    return 2
  fi
  append_receipt "surgical_webengine_probe" "ok" "loaded=$loaded; core_sha=$(framework_sha "$DST_LIB" QtWebEngineCore)"
  return 0
}

backup_and_swap() {
  require_env
  local stamp backup tmp dst src
  stamp="$(date +%Y%m%d-%H%M%S)"
  backup="$BACKUP_ROOT/$stamp"
  mkdir -p "$backup/lib" "$STATE_DIR"
  echo "$backup" >"$LATEST_FILE"

  append_receipt "surgical_webengine_swap_started" "running" "backup=$backup source=$SRC_QT_PREFIX target=$DST_QT_PREFIX frameworks=${FRAMEWORKS[*]}"

  for fw in "${FRAMEWORKS[@]}"; do
    src="$SRC_LIB/$fw.framework"
    dst="$DST_LIB/$fw.framework"
    tmp="$DST_LIB/$fw.framework.sifta-new-$stamp"
    if [[ ! -d "$src" ]]; then
      echo "ERROR: missing source $src" >&2
      return 1
    fi
    if [[ ! -d "$dst" ]]; then
      echo "ERROR: missing target $dst" >&2
      return 1
    fi
    echo "BACKUP $dst -> $backup/lib/$fw.framework"
    /usr/bin/ditto "$dst" "$backup/lib/$fw.framework"
    rm -rf "$tmp"
    echo "COPY $src -> $tmp"
    /usr/bin/ditto "$src" "$tmp"
    echo "SWAP $fw.framework"
    rm -rf "$dst"
    mv "$tmp" "$dst"
  done

  if ! probe_loaded_framework; then
    echo "Probe failed after swap; restoring $backup" >&2
    restore_from "$backup"
    append_receipt "surgical_webengine_swap_failed_restored" "restored" "backup=$backup"
    return 1
  fi
  append_receipt "surgical_webengine_swap_complete" "ok" "backup=$backup; core_sha=$(framework_sha "$DST_LIB" QtWebEngineCore)"
  echo "DONE: WebEngine frameworks swapped. Restart SIFTA, then probe TikTok playback."
}

restore_from() {
  require_env
  local backup="$1" fw dst src
  if [[ "$backup" == "latest" ]]; then
    if [[ ! -f "$LATEST_FILE" ]]; then
      echo "ERROR: no latest backup pointer at $LATEST_FILE" >&2
      return 1
    fi
    backup="$(cat "$LATEST_FILE")"
  fi
  if [[ ! -d "$backup/lib/QtWebEngineCore.framework" ]]; then
    echo "ERROR: invalid backup: $backup" >&2
    return 1
  fi
  append_receipt "surgical_webengine_restore_started" "running" "backup=$backup target=$DST_QT_PREFIX"
  for fw in "${FRAMEWORKS[@]}"; do
    src="$backup/lib/$fw.framework"
    dst="$DST_LIB/$fw.framework"
    if [[ ! -d "$src" ]]; then
      echo "ERROR: missing backup framework $src" >&2
      return 1
    fi
    rm -rf "$dst"
    /usr/bin/ditto "$src" "$dst"
  done
  probe_loaded_framework
  append_receipt "surgical_webengine_restore_complete" "ok" "backup=$backup"
  echo "DONE: restored WebEngine frameworks from $backup"
}

case "$MODE" in
  --dry-run|-n)
    print_plan
    ;;
  --probe)
    probe_loaded_framework
    ;;
  --execute|-x)
    backup_and_swap
    ;;
  --restore)
    restore_from "$RESTORE_TARGET"
    ;;
  --help|-h|help)
    sed -n '1,18p' "$0"
    ;;
  *)
    echo "ERROR: unknown mode: $MODE" >&2
    exit 2
    ;;
esac
