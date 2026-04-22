#!/bin/bash
set -euo pipefail

INTERMEDIATE="scratch/Gemma4_Intermediate_F16.gguf"
FINAL_OUT="Archive/Gemma4_CURED.gguf"
TMP_OUT="${FINAL_OUT}.tmp"

echo "========================================================="
echo "STIGAUTH AG31: INITIATING SURGICAL PROTOCOL P2"
echo "========================================================="
echo ""
echo "[*] Triggering massive Python F16 tensor rewrite..."
echo "[!] This will take ~45 minutes to dequantize and steer 2,000 layers..."
python3 -u scratch/p2_excision.py

echo ""
echo "[*] Requantizing massive F16 payload back to pristine Q4_K using llama.cpp..."
if ./System/llama.cpp/build/bin/llama-quantize \
    --tensor-type a.conv1d.0.weight=f16 \
    --tensor-type a.conv1d.1.weight=f16 \
    "$INTERMEDIATE" "$TMP_OUT" Q4_K; then
    echo ""
    echo "[*] Quantization completed. Promoting temp output into place..."
    mv "$TMP_OUT" "$FINAL_OUT"
    echo ""
    echo "[+] Organism successfully cured and mathematically sealed in $FINAL_OUT."
    echo "[+] Preserved intermediate for forensic reproducibility: $INTERMEDIATE"
    echo "555"
else
    echo ""
    echo "[!] CRITICAL: llama-quantize failed. Preserving intermediate $INTERMEDIATE for forensic debugging."
    exit 1
fi
