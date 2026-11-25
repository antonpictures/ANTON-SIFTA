#!/usr/bin/env bash
# Alice LoRA fine-tune — overnight run on M5 24GB
# Scheduled via automation: aut_213cb7edd001uxV7l6EVRZAucC (10 PM EST, Nov 25 2026)
# Model: MiMo-V2.6-Distill-Qwen-9B (Qwen3.5 9B architecture, MIT license)
# Data: data/alice_lora_v2/ (8194 pairs: 6556 train / 1638 valid)
# Output: adapters/alice-mimo-v2.6-lora/
# Log: ~/.sifta-logs/alice-lora-train.log
set -euo pipefail
cd /Users/ioanganton/Music/ANTON_SIFTA
mkdir -p ~/.sifta-logs adapters
mlx_lm.lora \
  --model XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B \
  --train \
  --data data/alice_lora_v2 \
  --fine-tune-type lora \
  --batch-size 1 \
  --iters 1000 \
  --learning-rate 1e-5 \
  --num-layers 8 \
  --mask-prompt \
  --grad-checkpoint \
  --adapter-path adapters/alice-mimo-v2.6-lora \
  --save-every 50 \
  --steps-per-report 10 \
  --steps-per-eval 50 \
  --max-seq-length 1024 \
  --seed 42 \
  2>&1 | tee ~/.sifta-logs/alice-lora-train.log
