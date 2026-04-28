#!/bin/bash
set -e

echo "=================================================="
echo "SIFTA MASTER PIPELINE: QWEN 0.8B EXPERIMENTAL"
echo "=================================================="

cd /Users/ioanganton/Music/ANTON_SIFTA

echo "[*] Step 1: DPO Ablation Pass in PyTorch"
PYTHONPATH=. .venv-surgery/bin/python3 surgery/qwen35_experiments/run_qwen_ablation.py

echo "[*] Step 2: GGUF Conversion, Quantization, and Ollama Injection"
bash surgery/qwen35_experiments/export_qwen_gguf.sh

echo "=================================================="
echo "ALL DONE. The experimental model is ready in Ollama."
echo "=================================================="
