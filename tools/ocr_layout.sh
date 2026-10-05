#!/bin/bash
# Build (once) and run the screenshot reader. The tool lives in the repo, not /tmp,
# because /tmp is cleaned and took the last copy with it.
set -e
SRC="$(dirname "$0")/ocr_layout.swift"
BIN="/tmp/ocr_layout"
[ -x "$BIN" ] || swiftc -O "$SRC" -o "$BIN"
exec "$BIN" "$@"
