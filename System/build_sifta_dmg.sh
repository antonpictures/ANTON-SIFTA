#!/usr/bin/env bash
# System/build_sifta_dmg.sh
# ==========================================================================
# Build SIFTA.app (py2app) and wrap it into a distributable SIFTA.dmg — the
# "device package" ship-layer from swarm_package_manifest.py. This is the
# concrete "real software product" a lawyer can double-click.
#
# Run on macOS:
#
#   cd /Users/ioanganton/Music/ANTON_SIFTA/System
#   chmod +x build_sifta_dmg.sh           # first time only
#   ./build_sifta_dmg.sh                   # unsigned demo .dmg (fine for a lawyer)
#
#   # to ship to other Macs without the Gatekeeper warning, sign + notarize:
#   SIGN_ID="Developer ID Application: Your Name (TEAMID)" \
#   NOTARY_PROFILE="sifta-notary" \
#   ./build_sifta_dmg.sh
#
# Unsigned is enough to DEMO a working product. Signing/notarization only
# matters when other people download it.
# ==========================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

APP="dist/SIFTA.app"
DMG="dist/SIFTA.dmg"
VOLNAME="SIFTA 0.1.0"

if [ "$(uname)" != "Darwin" ]; then
  echo "[!] This builds a macOS .app/.dmg and must run on macOS (Darwin)." >&2
  exit 1
fi

echo "==> 1/4  build SIFTA.app (py2app)"
python3 -m pip install --quiet --upgrade py2app >/dev/null 2>&1 || true
rm -rf build "$APP"
python3 setup.py py2app
[ -d "$APP" ] || { echo "[!] py2app did not produce $APP"; exit 1; }
echo "        built $APP ($(du -sh "$APP" | cut -f1))"

echo "==> 2/4  codesign"
if [ -n "${SIGN_ID:-}" ]; then
  codesign --deep --force --options runtime --timestamp --sign "$SIGN_ID" "$APP"
  codesign --verify --strict --verbose=2 "$APP"
  echo "        signed with: $SIGN_ID"
else
  echo "        skipped (no SIGN_ID) — unsigned demo build"
fi

echo "==> 3/4  wrap into $DMG"
rm -f "$DMG"
if command -v create-dmg >/dev/null 2>&1; then
  create-dmg \
    --volname "$VOLNAME" \
    --window-size 520 320 \
    --icon-size 100 \
    --icon "SIFTA.app" 130 150 \
    --app-drop-link 390 150 \
    "$DMG" "$APP"
else
  echo "        create-dmg not found; using hdiutil (plain image)."
  echo "        for the drag-to-Applications window: brew install create-dmg"
  STAGE="$(mktemp -d)"
  cp -R "$APP" "$STAGE/"
  ln -s /Applications "$STAGE/Applications"
  hdiutil create -volname "$VOLNAME" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
  rm -rf "$STAGE"
fi
[ -f "$DMG" ] || { echo "[!] failed to produce $DMG"; exit 1; }

echo "==> 4/4  notarize"
if [ -n "${SIGN_ID:-}" ] && [ -n "${NOTARY_PROFILE:-}" ]; then
  xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG"
  echo "        notarized + stapled"
else
  echo "        skipped (set SIGN_ID + NOTARY_PROFILE to enable)"
fi

echo ""
echo "DONE -> $DIR/$DMG  ($(du -sh "$DMG" | cut -f1))"
echo "Double-click it: a window opens, drag SIFTA into Applications. A real, local,"
echo "receipt-verified organism — not a model, an app."
