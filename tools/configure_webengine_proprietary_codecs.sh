#!/usr/bin/env bash
# Build Qt WebEngine with proprietary H.264/AAC codecs for Alice Browser.
#
# Why this exists:
#   PyPI PyQt6-WebEngine wheels can render TikTok but may report
#   DEMUXER_ERROR_NO_SUPPORTED_STREAMS for H.264/AAC streams. The product target
#   is Alice Browser playback, not a handoff to another browser.
#
# Default mode is a dry-run probe so this file is safe in tests and in chat.
# Real build:
#   bash tools/configure_webengine_proprietary_codecs.sh --execute
#
# Integration truth:
#   This builds/installs a codec-capable Qt. SIFTA still needs the running PyQt6
#   binding to load that Qt build; verify with Alice Browser canPlayType/live
#   TikTok receipts before claiming the Chromium limb is fixed.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="$REPO/.sifta_state"
BUILD_ROOT="${SIFTA_QT_BUILD_ROOT:-$HOME/sifta-qt-webengine-build}"
QT_REPO="${SIFTA_QT_REPO:-https://code.qt.io/qt/qt5.git}"
QT_BRANCH="${SIFTA_QT_BRANCH:-v6.11.0}"
QT_SRC="${SIFTA_QT_SRC:-$BUILD_ROOT/qt-$QT_BRANCH}"
INSTALL_PREFIX="${SIFTA_QT_INSTALL_PREFIX:-$BUILD_ROOT/install-$QT_BRANCH-proprietary-codecs}"
MODE="${1:---dry-run}"

usage() {
  cat <<EOF
Usage:
  bash tools/configure_webengine_proprietary_codecs.sh --dry-run
  bash tools/configure_webengine_proprietary_codecs.sh --execute

Environment:
  SIFTA_QT_BUILD_ROOT       default: $HOME/sifta-qt-webengine-build
  SIFTA_QT_BRANCH           default: v6.11.0
  SIFTA_QT_SRC              default: \$SIFTA_QT_BUILD_ROOT/qt-\$SIFTA_QT_BRANCH
  SIFTA_QT_INSTALL_PREFIX   default: \$SIFTA_QT_BUILD_ROOT/install-\$SIFTA_QT_BRANCH-proprietary-codecs
EOF
}

require_tool() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: missing required tool: $1" >&2
    return 1
  fi
}

qt_configure_python() {
  if [[ -x /opt/homebrew/Frameworks/Python.framework/Versions/3.14/bin/python3.14 ]]; then
    echo "/opt/homebrew/Frameworks/Python.framework/Versions/3.14/bin/python3.14"
  else
    command -v python3
  fi
}

require_python_module() {
  local py
  py="$(qt_configure_python)"
  if ! "$py" -c "import $1" >/dev/null 2>&1; then
    echo "ERROR: missing required Python module: $1 for $py ($py -m pip install $1)" >&2
    return 1
  fi
}

require_metal_toolchain() {
  if ! xcrun metal -v >/dev/null 2>&1; then
    echo "ERROR: Metal compiler unavailable (ANGLE qtwebengine build needs it)." >&2
    echo "       Install the Xcode Metal Toolchain component, then re-run:" >&2
    echo "         xcodebuild -downloadComponent MetalToolchain" >&2
    return 1
  fi
}

desired_cmake_generator() {
  if command -v ninja >/dev/null 2>&1; then
    echo "Ninja"
  else
    echo "Unix Makefiles"
  fi
}

purge_qt_cmake_artifacts() {
  echo "Purging Qt CMake/Ninja/Make artifacts under $QT_SRC"
  find "$QT_SRC" -name 'CMakeCache.txt' -delete
  while IFS= read -r -d '' dir; do
    rm -rf "$dir"
  done < <(find "$QT_SRC" -type d -name 'CMakeFiles' -print0 2>/dev/null || true)
  find "$QT_SRC" \( -name 'Makefile' -o -name 'build.ninja' -o -name '.ninja_deps' -o -name '.ninja_log' \) -delete 2>/dev/null || true
}

reset_dirty_qt_submodules() {
  echo "Resetting dirty Qt submodules after artifact purge."
  git -C "$QT_SRC" submodule foreach --recursive \
    'git reset --hard HEAD >/dev/null 2>&1 || true; git clean -fd >/dev/null 2>&1 || true'
}

clean_stale_cmake_cache_if_needed() {
  local want
  want="$(desired_cmake_generator)"
  if ! find "$QT_SRC" -name 'CMakeCache.txt' -print -quit 2>/dev/null | grep -q .; then
    return 0
  fi
  if find "$QT_SRC" -name 'CMakeCache.txt' -exec grep -H '^CMAKE_GENERATOR:INTERNAL=' {} + 2>/dev/null \
      | grep -Ev "CMAKE_GENERATOR:INTERNAL=${want}\$" | grep -q .; then
    echo "Stale CMake generator caches detected — want '${want}'; purging build tree for reconfigure."
    purge_qt_cmake_artifacts
    reset_dirty_qt_submodules
    receipt "cache_cleaned" "ok" "purged stale cmake/ninja/make artifacts; reconfigure with ${want}"
  fi
}

webengine_core_installed() {
  [[ -d "$INSTALL_PREFIX/lib/QtWebEngineCore.framework" ]] \
    || [[ -f "$INSTALL_PREFIX/lib/libQt6WebEngineCore.dylib" ]]
}

qtwebengine_ready() {
  [[ -f "$QT_SRC/qtwebengine/CMakeLists.txt" || -f "$QT_SRC/qtwebengine/.git" ]]
}

ensure_qt_submodules() {
  cd "$QT_SRC"
  if qtwebengine_ready; then
    echo "Qt submodules already initialized."
    return 0
  fi
  echo "Initializing Qt submodules (qtwebengine, qtwebchannel, qtdeclarative)..."
  if [[ -x ./init-repository ]]; then
    ./init-repository --module-subset=qtwebengine,qtwebchannel,qtdeclarative
  else
    echo "ERROR: init-repository missing in $QT_SRC" >&2
    return 1
  fi
  if ! qtwebengine_ready; then
    echo "ERROR: qtwebengine still empty after init-repository" >&2
    return 1
  fi
}

receipt() {
  local action="$1"
  local status="$2"
  local extra="${3:-}"
  mkdir -p "$STATE_DIR"
  python3 - "$STATE_DIR/media_codec_bridge.jsonl" "$action" "$status" "$extra" <<'PY'
from __future__ import annotations
import json
import sys
import time
import uuid
from pathlib import Path

path = Path(sys.argv[1])
row = {
    "ts": time.time(),
    "trace_id": str(uuid.uuid4()),
    "truth_label": "QTWEBENGINE_PROPRIETARY_CODEC_BUILD_V1",
    "action": sys.argv[2],
    "status": sys.argv[3],
}
if len(sys.argv) > 4 and sys.argv[4]:
    row["detail"] = sys.argv[4]
path.parent.mkdir(parents=True, exist_ok=True)
with path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
print(json.dumps(row, ensure_ascii=False))
PY
}

raise_fd_limit() {
  # macOS defaults the open-file soft limit to 256. A parallel Chromium jumbo
  # compile blows past that inside a SINGLE clang -> "fatal error: cannot open
  # file ... Too many open files" (EMFILE). r791 raised only the SOFT limit
  # (`ulimit -Sn`), but macOS setrlimit REJECTS that while the hard limit is
  # "unlimited" (RLIM_INFINITY is invalid for NOFILE) — the raise silently failed
  # and the build hit EMFILE again at [5/20593] (r792). Fix: set BOTH soft and
  # hard to a CONCRETE number, trying a descending ladder (the highest the kernel
  # accepts wins, capped by kern.maxfilesperproc), and ABORT LOUD if we cannot
  # clear a safe floor. Never grind into EMFILE again.
  local floor=8192 now t
  for t in 65536 49152 24576 16384 12288 10240 8192; do
    ulimit -n "$t" 2>/dev/null && break    # sets BOTH soft and hard at once
  done
  now="$(ulimit -Sn 2>/dev/null || echo 0)"
  echo "FD limit (ulimit -n): soft=$now hard=$(ulimit -Hn 2>/dev/null)"
  if [[ "$now" == "unlimited" ]]; then
    return 0
  fi
  if (( now < floor )); then
    echo "ERROR: open-file limit stuck at $now (need >= $floor for the Chromium build)." >&2
    echo "       Raise it in THIS shell, then re-run --execute:" >&2
    echo "         ulimit -n 65536      # or the highest your Mac accepts" >&2
    echo "       If that is rejected, raise the kernel cap first (needs sudo):" >&2
    echo "         sudo sysctl -w kern.maxfilesperproc=131072 kern.maxfiles=262144" >&2
    echo "         sudo launchctl limit maxfiles 65536 262144" >&2
    receipt "fd_limit_too_low" "error" "soft=$now floor=$floor — aborting before EMFILE (r792)"
    return 1
  fi
  return 0
}

print_plan() {
  cat <<EOF
SIFTA Qt WebEngine proprietary codec build
Repo:           $REPO
Qt repo:        $QT_REPO
Qt branch:      $QT_BRANCH
Build root:     $BUILD_ROOT
Qt source:      $QT_SRC
Install prefix: $INSTALL_PREFIX

Real build command:
  bash tools/configure_webengine_proprietary_codecs.sh --execute

This is the root Chromium-limb fix. Expected final proof is not "script ran";
expected proof is Alice Browser TikTok <video> playing without
DEMUXER_ERROR_NO_SUPPORTED_STREAMS after SIFTA loads the codec-capable Qt.
EOF
}

if [[ "$MODE" == "--help" || "$MODE" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "$MODE" != "--dry-run" && "$MODE" != "--execute" ]]; then
  usage >&2
  exit 2
fi

print_plan

require_tool git
require_tool cmake
require_tool python3
CMAKE_BUILD_ARGS=(--parallel "$(sysctl -n hw.ncpu 2>/dev/null || echo 4)")

if [[ "$MODE" == "--dry-run" ]]; then
  missing=()
  command -v ninja >/dev/null 2>&1 || missing+=("ninja")
  xcrun metal -v >/dev/null 2>&1 || missing+=("Metal Toolchain (xcodebuild -downloadComponent MetalToolchain)")
  py="$(qt_configure_python)"
  "$py" -c "import html5lib" >/dev/null 2>&1 || missing+=("html5lib for $py")
  if ((${#missing[@]})); then
    receipt "dry_run" "ok" "deps missing: ${missing[*]}; install before --execute"
  else
    receipt "dry_run" "ok" "builder + ninja + html5lib present; run with --execute"
  fi
  exit 0
fi

require_tool ninja
require_python_module html5lib
require_metal_toolchain

trap 'receipt "build_failed" "error" "line=$LINENO cmd=$BASH_COMMAND"' ERR

receipt "build_start" "running" "branch=$QT_BRANCH prefix=$INSTALL_PREFIX"

raise_fd_limit || exit 1
receipt "fd_limit_raised" "ok" "ulimit -n soft=$(ulimit -Sn) hard=$(ulimit -Hn) — set BOTH soft+hard via ladder to clear EMFILE 'Too many open files' (r792)"

mkdir -p "$BUILD_ROOT"
if [[ ! -d "$QT_SRC/.git" ]]; then
  # Full clone: shallow tag clones leave empty submodule dirs and break init-repository.
  git clone "$QT_REPO" "$QT_SRC"
  git -C "$QT_SRC" checkout "$QT_BRANCH"
fi

ensure_qt_submodules

clean_stale_cmake_cache_if_needed

if ! webengine_core_installed; then
  need_purge=""
  if [[ -f "$QT_SRC/config.summary" ]] && grep -Eq 'Build QtWebEngineCore.*no' "$QT_SRC/config.summary"; then
    need_purge="config.summary QtWebEngineCore=no"
  elif [[ -f "$QT_SRC/CMakeCache.txt" ]] && grep -q '^FEATURE_qtwebengine_build:BOOL=OFF' "$QT_SRC/CMakeCache.txt"; then
    need_purge="CMakeCache FEATURE_qtwebengine_build=OFF"
  fi
  if [[ -n "$need_purge" ]]; then
    echo "Prior configure skipped QtWebEngine ($need_purge) — purging for a fresh proprietary-codec build."
    purge_qt_cmake_artifacts
    reset_dirty_qt_submodules
    receipt "reconfigure_for_webengine" "ok" "purged stale configure: ${need_purge}"
  fi
fi

reset_dirty_qt_submodules

cd "$QT_SRC"
./configure \
  -init-submodules \
  -prefix "$INSTALL_PREFIX" \
  -webengine-proprietary-codecs \
  -webengine-ffmpeg \
  -feature-qtwebengine-build \
  -release \
  -nomake examples \
  -nomake tests

cmake --build . "${CMAKE_BUILD_ARGS[@]}"
cmake --install .

if ! webengine_core_installed; then
  echo "ERROR: configure/build finished but QtWebEngineCore is missing in $INSTALL_PREFIX" >&2
  echo "Check $QT_SRC/config.summary for QtWebEngine configure errors." >&2
  receipt "build_failed" "error" "install missing QtWebEngineCore.framework under prefix=$INSTALL_PREFIX"
  exit 1
fi

mkdir -p "$STATE_DIR"
cat > "$STATE_DIR/qt_webengine_proprietary_codecs.env" <<EOF
SIFTA_QT_INSTALL_PREFIX=$INSTALL_PREFIX
QTWEBENGINE_PROPRIETARY_CODECS_BUILT=1
QTWEBENGINE_PROPRIETARY_CODECS_BRANCH=$QT_BRANCH
EOF

receipt "build_complete" "installed" "prefix=$INSTALL_PREFIX webengine_core=1"

cat <<EOF
Build installed at:
  $INSTALL_PREFIX

Next proof step:
  Restart SIFTA with the codec-capable Qt binding path, open TikTok in Alice
  Browser, and verify the page <video> plays without DEMUXER_ERROR.
EOF
