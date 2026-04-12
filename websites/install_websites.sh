#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# STIGMERGICODE — Mac Mini Web Host Install Script
# Installs nginx and sets up stigmergicode.com + stigmergicoin.com
# Run this on the M1 Mac Mini as the host machine.
#
# Usage:
#   chmod +x install_websites.sh
#   ./install_websites.sh
# ──────────────────────────────────────────────────────────────────────────────

set -e

CYAN='\033[0;36m'
GOLD='\033[0;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  STIGMERGICODE — Website Install${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ── Check for Homebrew
if ! command -v brew &> /dev/null; then
  echo -e "${GOLD}  [BREW] Installing Homebrew...${NC}"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
  echo -e "${GREEN}  [✅] Homebrew found${NC}"
fi

# ── Install nginx
if ! command -v nginx &> /dev/null; then
  echo -e "${GOLD}  [NGINX] Installing nginx...${NC}"
  brew install nginx
else
  echo -e "${GREEN}  [✅] nginx found: $(nginx -v 2>&1)${NC}"
fi

# ── Create web root directories
WEBROOT="/opt/homebrew/var/www"
echo -e "${CYAN}  [DIR] Creating web roots...${NC}"
mkdir -p "$WEBROOT/stigmergicode.com"
mkdir -p "$WEBROOT/stigmergicoin.com"

# ── Copy site files from USB (same directory as this script)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$SCRIPT_DIR/stigmergicode.com/index.html" ]; then
  cp -r "$SCRIPT_DIR/stigmergicode.com/." "$WEBROOT/stigmergicode.com/"
  echo -e "${GREEN}  [✅] stigmergicode.com files copied${NC}"
else
  echo -e "${RED}  [WARN] stigmergicode.com/index.html not found next to this script${NC}"
fi

if [ -f "$SCRIPT_DIR/stigmergicoin.com/index.html" ]; then
  cp -r "$SCRIPT_DIR/stigmergicoin.com/." "$WEBROOT/stigmergicoin.com/"
  echo -e "${GREEN}  [✅] stigmergicoin.com files copied${NC}"
else
  echo -e "${RED}  [WARN] stigmergicoin.com/index.html not found next to this script${NC}"
fi

# ── Write nginx config
NGINX_CONF_DIR="/opt/homebrew/etc/nginx/servers"
mkdir -p "$NGINX_CONF_DIR"

cat > "$NGINX_CONF_DIR/stigmergicode.conf" << 'EOF'
server {
    listen 3001;
    server_name stigmergicode.com www.stigmergicode.com;

    root /opt/homebrew/var/www/stigmergicode.com;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    # Wormhole Chat API Proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8090/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_addrs;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header Referrer-Policy "strict-origin-when-cross-origin";

    # Gzip
    gzip on;
    gzip_types text/html text/css application/javascript;
}

server {
    listen 3002;
    server_name stigmergicoin.com www.stigmergicoin.com;

    root /opt/homebrew/var/www/stigmergicoin.com;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header Referrer-Policy "strict-origin-when-cross-origin";

    gzip on;
    gzip_types text/html text/css application/javascript;
}
EOF

echo -e "${GREEN}  [✅] nginx config written${NC}"

# ── Test nginx config
nginx -t && echo -e "${GREEN}  [✅] nginx config valid${NC}"

# ── Start / reload nginx
if pgrep nginx > /dev/null; then
  nginx -s reload
  echo -e "${GREEN}  [✅] nginx reloaded${NC}"
else
  nginx
  echo -e "${GREEN}  [✅] nginx started${NC}"
fi

# ── Auto-start nginx on boot
brew services start nginx
echo -e "${GREEN}  [✅] nginx set to auto-start on boot${NC}"

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  INSTALL COMPLETE${NC}"
echo ""
echo -e "  Sites are live on this machine."
echo -e "  Access locally:"
echo -e "    ${CYAN}http://stigmergicode.com${NC}   (after DNS is set)"
echo -e "    ${CYAN}http://stigmergicoin.com${NC}   (after DNS is set)"
echo ""
echo -e "  Your public IP: ${GOLD}$(curl -s https://api.ipify.org)${NC}"
echo ""
echo -e "  ${GOLD}GoDaddy / Cloudflare Setup:${NC}
  1. Your Cloudflare Tunnels should map directly to:
     http://localhost:3001 (for stigmergicode.com)
     http://localhost:3002 (for stigmergicoin.com)
  2. NGINX handles those specific ports internally now!"
echo -e ""
echo -e "  Find this Mac Mini's local IP:"
echo -e "    ${CYAN}$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo 'run: ipconfig getifaddr en0')${NC}"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
