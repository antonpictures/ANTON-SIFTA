#!/bin/bash
set -e

echo "=================================================="
echo "SIFTA GGUF EXPORT: QWEN 0.8B EXPERIMENTAL"
echo "=================================================="

MERGED_DIR="surgery/qwen35_experiments/merged/qwen35-08b-phc-experimental-hf"
GGUF_OUT="surgery/qwen35_experiments/gguf/qwen35-08b-phc-experimental-f16.gguf"
QUANT_OUT="surgery/qwen35_experiments/gguf/qwen35-08b-phc-experimental-q4_k_m.gguf"
OLLAMA_MODEL_NAME="qwen35-08b-phc-experimental"

if [ ! -d "$MERGED_DIR" ]; then
    echo "[ERROR] Merged HF directory not found: $MERGED_DIR"
    exit 1
fi

echo "[*] Step 1: Converting HF to GGUF (F16)"
# Using .venv-surgery python to run llama.cpp converter
.venv-surgery/bin/python3 Library/llama.cpp/convert_hf_to_gguf.py "$MERGED_DIR" --outtype f16 --outfile "$GGUF_OUT"

echo "[*] Step 2: Quantizing to Q4_K_M"
# Use the compiled llama-quantize binary. Assuming it's in Library/llama.cpp/build/bin/ or globally available.
# Actually, the user has llama-quantize installed, or it's in the repo.
if command -v llama-quantize &> /dev/null; then
    QUANT_BIN="llama-quantize"
elif [ -f "Library/llama.cpp/llama-quantize" ]; then
    QUANT_BIN="Library/llama.cpp/llama-quantize"
elif [ -f "Library/llama.cpp/build/bin/llama-quantize" ]; then
    QUANT_BIN="Library/llama.cpp/build/bin/llama-quantize"
else
    echo "[WARNING] llama-quantize binary not found! Falling back to F16 for Ollama."
    cp "$GGUF_OUT" "$QUANT_OUT"
fi

if [ "$QUANT_BIN" != "" ] && [ ! -f "$QUANT_OUT" ]; then
    $QUANT_BIN "$GGUF_OUT" "$QUANT_OUT" Q4_K_M
fi

echo "[*] Step 3: Creating Ollama Modelfile"
MODELFILE_PATH="surgery/qwen35_experiments/Modelfile.08b"
cat << EOF > "$MODELFILE_PATH"
FROM ./gguf/qwen35-08b-phc-experimental-q4_k_m.gguf

TEMPLATE """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
{{ .Response }}<|im_end|>
"""
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
PARAMETER temperature 0.7
EOF

echo "[*] Step 4: Creating Ollama Model ($OLLAMA_MODEL_NAME)"
cd surgery/qwen35_experiments/
ollama create $OLLAMA_MODEL_NAME -f Modelfile.08b
cd ../../

echo "[SUCCESS] Model $OLLAMA_MODEL_NAME is ready in Ollama!"
echo "Test it with: ollama run $OLLAMA_MODEL_NAME"
