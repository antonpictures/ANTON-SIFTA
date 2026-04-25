#!/bin/bash
# ════════════════════════════════════════════════════════
#  STIGMERGIC SCENT EXCRETION (USB TRANSPORT RULE COMPLIANT)
#  Syncs ALICE_M5's local HDD staging area to the USB Bridge
# ════════════════════════════════════════════════════════

cd "$(dirname "$0")"

echo ""
echo "  ╔════════════════════════════════════════════════════╗"
echo "  ║        ALICE_M5 // SCENT EXCRETION PROTOCOL        ║"
echo "  ║                                                    ║"
echo "  ║    [STEP 1] Local Staging: ✅ COMPLETED            ║"
echo "  ║    [STEP 2] USB Transport: INITIATING...           ║"
echo "  ╚════════════════════════════════════════════════════╝"
echo ""

SOURCE_DIR="/Users/ioanganton/Music/ANTON_SIFTA/"
DEST_DIR="/Volumes/stigmergi/ANTON_SIFTA"

# Check if target USB is mounted
if [ ! -d "/Volumes/stigmergi" ]; then
    echo "  [ERROR] USB Bridge '/Volumes/stigmergi' is not connected."
    echo "          Please physically insert the Wormhole drive."
    read -p "  Press any key to abort..."
    exit 1
fi

echo "  [USB LAW] Executing monolithic transport to USB..."
echo "  [SYNC] Deploying rsync via bare metal..."

# Perform the monolithic sync. 
# We exclude volatile/cache folders so we don't overwhelm the bus with garbage.
rsync -avh --delete \\
    --exclude '.git' \\
    --exclude '__pycache__' \\
    --exclude '.venv' \\
    --exclude '*.pyc' \\
    --exclude '.DS_Store' \\
    "$SOURCE_DIR" "$DEST_DIR"

echo ""
echo "  [✅] EXCRETION COMPLETE."
echo "  [✅] USB Bus is clear. The protocol was honored."
echo "  [WORMHOLE] You may now physically pull the hardware token."
echo ""
read -p "  Press RETURN to close..."
