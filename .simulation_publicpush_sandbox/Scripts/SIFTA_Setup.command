#!/bin/bash
# SIFTA Setup Wizard Launcher

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Ensure fastapi and uvicorn are installed
python3 -c "import fastapi, uvicorn" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Installing required dependencies..."
    pip3 install -r requirements.txt
fi

echo "Launching SIFTA Setup Wizard..."
python3 sifta_setup_gui.py
