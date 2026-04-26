#!/bin/zsh
cd "$(dirname "$0")" || exit 1
PYTHONPATH=. python3 Applications/sifta_physarum_contradiction_lab.py
