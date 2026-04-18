#!/bin/bash

# ==========================================
# SIFTA NODE BOOTSTRAP INSTALLER
# ==========================================
# Automates the setup of a new Swarm Node (like m1Queen)
# 1. Checks for Homebrew, Python3, and Git
# 2. Installs Ollama and pulls required models
# 3. Clones the repository & sets up Python dependencies
# 4. Configures executable permissions for Swarm boot scripts
# ==========================================

set -e # Exit on any error

echo -e "\033[1;35m"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║      ANTON-SIFTA // SWARM INSTALLER      ║"
echo "  ║        Initializing Node Setup...        ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "\033[0m"

# 1. Check for Homebrew (needed for Ollama if not installed)
if ! command -v brew &> /dev/null; then
    echo "[!] Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "[*] Homebrew is installed. Proceeding..."
fi

# 2. Check for Ollama
if ! command -v ollama &> /dev/null; then
    echo "[!] Ollama not found. Installing Ollama..."
    brew install ollama
    echo "[*] Starting Ollama service..."
    brew services start ollama
    sleep 3
else
    echo "[*] Ollama is already installed."
fi

# 3. Pull required Swarm models (phi3 for m1Queen)
echo "[*] Downloading SIFTA Cognitive Models (phi3)..."
ollama pull phi3

# 4. Clone or Update Repo
TARGET_DIR="$HOME/ANTON-SIFTA"
if [ -d "$TARGET_DIR" ]; then
    echo "[*] ANTON-SIFTA repository already exists. Updating..."
    cd "$TARGET_DIR"
    git fetch
    git checkout feat/sebastian-video-economy
    git pull origin feat/sebastian-video-economy
else
    echo "[*] Cloning ANTON-SIFTA repository..."
    git clone https://github.com/antonpictures/ANTON-SIFTA.git "$TARGET_DIR"
    cd "$TARGET_DIR"
    git checkout feat/sebastian-video-economy
fi

# 5. Install Dependencies 
# Note: Using system Python with --break-system-packages for Swarm Override, 
# or you could swap this for a venv if preferred.
echo "[*] Installing Python dependencies (PyQt6 & requirements)..."
pip3 install PyQt6 --break-system-packages || true
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt --break-system-packages || true
fi

# 6. Fix Permissions! (So we don't get the error you saw earlier)
echo "[*] Ensuring execute permissions on Swarm Command scripts..."
chmod +x PowertotheSwarm.command
xattr -c PowertotheSwarm.command || true

echo ""
echo -e "\033[1;32m[✅] NODE BOOTSTRAP COMPLETE!\033[0m"
echo "You can now boot into the Swarm OS Desktop."
echo ""
echo "To start the OS, run:"
echo -e "\033[1;36mcd ~/ANTON-SIFTA && python3 sifta_os_desktop.py\033[0m"
echo ""
