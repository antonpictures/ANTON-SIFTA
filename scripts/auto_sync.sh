#!/usr/bin/env bash
# auto_sync.sh
#
# Runs every 5 s under launchd (antonia.sifta.warp9.spool.sync.v5).
# Pulls the peer's warp9 spool delta into our local mirror.
#
# Peer coordinates live in .sifta_state/federation_peer.conf so that the
# Cursor sandbox secret-redactor (which strips IP-shaped strings from .env)
# can't blow them away. .env still holds HMAC + federation gate flags.
#
# federation_peer.conf format:
#   PEER_IP=192.168.1.71
#   PEER_USER=ioanganton           (optional, default ioanganton)
set -euo pipefail

cd "$(dirname "$0")/.."

PEER_CONF=".sifta_state/federation_peer.conf"
PEER_IP=""
PEER_USER=""

if [ -f "$PEER_CONF" ]; then
    while IFS='=' read -r key value; do
        case "$key" in
            PEER_IP)   PEER_IP="${value//\"/}" ;;
            PEER_USER) PEER_USER="${value//\"/}" ;;
        esac
    done < <(grep -v '^[[:space:]]*#' "$PEER_CONF" | grep '=')
fi

if [ -f ".env" ]; then
    while IFS='=' read -r key value; do
        case "$key" in
            SIFTA_PEER_IP*) PEER_IP="${value//\"/}" ;;
        esac
    done < <(grep -v '^[[:space:]]*#' .env | grep '=')
fi

if [ -z "${PEER_IP:-}" ]; then
    exit 0
fi

[ -n "${PEER_USER:-}" ] && export PEER_USER

exec ./scripts/federation_rsync.sh pull "$PEER_IP"
