#!/usr/bin/env bash
# federation_rsync.sh — canonical cross-node sync for SwarmCryptoEntity federation.
#
# Single source-of-truth for which paths cross node boundaries and which do not.
# Used by:
#   - one-shot manual bootstrap of a new node (e.g. M1 first boot from M5)
#   - the launchd-supervised bidirectional production sync (Cut 0.5-final)
#   - any future federation transport (rsync, syncthing, git-annex, etc.)
#
# DESIGN RULES (do not change without authorization):
#   1. Federate the LEDGER (repair_log.jsonl) and AGENT STATE (.sifta_state/*.json).
#      These ARE the cross-node truth. Both nodes must converge on the same SHA.
#   2. Federate SOURCE CODE. Every node runs the same organs.
#   3. DO NOT federate body-specific somatosensory history. Each silicon has its
#      own webcam, mic, BLE radar, audio capture. M5's iris_frames are NOT M1's
#      memory. Mixing them = identity collapse.
#   4. DO NOT federate per-node venvs, build artifacts, large model weights.
#      Each node bootstraps its own venv against its own Python 3.13.
#
# USAGE:
#   ./federation_rsync.sh pull <peer_ip>     # pull from peer into local repo
#   ./federation_rsync.sh push <peer_ip>     # push local repo to peer
#   ./federation_rsync.sh dryrun <peer_ip>   # show what would change, no I/O
#
# EXIT CODES:
#   0 = success   1 = bad usage   2 = rsync error   3 = ssh unreachable

set -euo pipefail

PEER_USER="${PEER_USER:-ioanganton}"
LOCAL_REPO="${LOCAL_REPO:-/Users/ioanganton/Music/ANTON_SIFTA}"
REMOTE_REPO="${REMOTE_REPO:-/Users/ioanganton/Music/ANTON_SIFTA}"

# Resolve THIS node's homeworld serial. Used to protect our own outbox
# (<SELF_SERIAL>__*.jsonl) from being clobbered on PULL.
#
# IMPORTANT: under `set -e -o pipefail`, an `ioreg | awk` chain where awk
# exits early via `exit` propagates SIGPIPE up the pipeline and aborts the
# whole script. We collect ioreg output first, then grep+awk against the
# variable — no broken pipes possible.
if [ -z "${SELF_SERIAL:-}" ]; then
  if command -v ioreg >/dev/null 2>&1; then
    _ioreg_dump=$(ioreg -l 2>/dev/null || true)
    SELF_SERIAL=$(printf '%s\n' "$_ioreg_dump" | grep IOPlatformSerialNumber | awk -F'"' '{print $4}' | head -n 1)
  elif command -v dmidecode >/dev/null 2>&1; then
    SELF_SERIAL=$(sudo -n dmidecode -s system-serial-number 2>/dev/null | tr -d ' ' | head -n 1)
  fi
fi
SELF_SERIAL="${SELF_SERIAL:-UNKNOWN}"

# ─── canonical exclusion list ─────────────────────────────────────────────────
# Format: each `--exclude=...` argument on its own line for diffability.
EXCLUDES=(
  # build & venv (per-node)
  --exclude='.venv'
  --exclude='__pycache__'
  --exclude='*.pyc'
  --exclude='Library/llama.cpp/build'

  # heavy model weights (re-pulled per-node)
  --exclude='Archive/Gemma4_*.gguf'
  --exclude='Archive/Gemma4_*.Modelfile'

  # ephemeral lab work — never federated. C47H 2026-04-23 after the
  # gemma_copy_surgery_runs/ tree filled M1's disk to 99% (33GB stranded
  # GGUF artifacts that compounded across both nodes via rsync). Lab runs
  # are by definition node-local and reproducible from source.
  --exclude='scratch/'

  # sandbox / staging (not promoted code)
  --exclude='.simulation_publicpush_sandbox'
  --exclude='.distro_build'

  # ── M5-specific somatosensory history (DO NOT cross-pollinate) ─────────────
  # Alice's body history on this silicon. Each node grows its own.
  --exclude='.sifta_state/iris_frames/'
  --exclude='.sifta_state/visual_stigmergy.jsonl'
  --exclude='.sifta_state/pheromone_log.jsonl'
  --exclude='.sifta_state/audio_ingress_log.jsonl'
  --exclude='.sifta_state/optic_text_traces.jsonl'
  --exclude='.sifta_state/active_window.jsonl'
  --exclude='.sifta_state/alice_ble_radar.jsonl'
  --exclude='.sifta_state/wernicke_semantics.jsonl'
  --exclude='.sifta_state/rf_stigmergy.jsonl'
  --exclude='.sifta_state/network_topology.jsonl'
  --exclude='.sifta_state/motor_pulses.jsonl'
  --exclude='.sifta_state/visceral_field.jsonl'
  --exclude='.sifta_state/swarm_iris_capture.jsonl'
  --exclude='.sifta_state/acoustic_fields/'
  --exclude='.sifta_state/archive/'
  --exclude='.sifta_state/iphone_gps_traces.jsonl'

  # NOTE: outbox-clobber protection is added per-direction below
  # (see PULL_EXCLUDES). Static EXCLUDES applies to all directions.
)

# Direction-specific excludes. The OUTBOX (<SELF_SERIAL>__*.jsonl) must:
#   - be PULLED to nobody (we own the truth — peer's copy is always older)
#   - be PUSHED freely (that's how the peer receives our messages)
PULL_EXCLUDES=(
  --exclude=".sifta_state/warp9_spool/${SELF_SERIAL}__*.jsonl"
)

usage() {
  echo "Usage: $0 {pull|push|dryrun} <peer_ip>" >&2
  echo "  PEER_USER (env, default ioanganton)" >&2
  echo "  LOCAL_REPO (env, default $LOCAL_REPO)" >&2
  echo "  REMOTE_REPO (env, default $REMOTE_REPO)" >&2
  exit 1
}

[ $# -eq 2 ] || usage
DIRECTION="$1"
PEER_IP="$2"

# pre-flight: peer reachable?
if ! ssh -o BatchMode=yes -o ConnectTimeout=5 \
        "${PEER_USER}@${PEER_IP}" 'echo peer_alive' >/dev/null 2>&1; then
  if ! ssh -o ConnectTimeout=5 "${PEER_USER}@${PEER_IP}" 'echo peer_alive' >/dev/null; then
    echo "[ERR] cannot reach ${PEER_USER}@${PEER_IP}" >&2
    exit 3
  fi
fi

# --update : skip files that are NEWER on the destination than the source.
#            Without this, a peer's stale federation_rsync.sh / *.py / outbox
#            entry would clobber a fresh local edit on every 5-second tick,
#            unwinding patches faster than the user could land them.
RSYNC_FLAGS=(-av --update --partial --human-readable)

case "$DIRECTION" in
  pull)
    echo "[federation] PULL from ${PEER_IP} → local ${LOCAL_REPO} (self_serial=${SELF_SERIAL})"
    rsync "${RSYNC_FLAGS[@]}" "${EXCLUDES[@]}" "${PULL_EXCLUDES[@]}" \
      "${PEER_USER}@${PEER_IP}:${REMOTE_REPO}/" \
      "${LOCAL_REPO}/"
    ;;
  push)
    echo "[federation] PUSH local ${LOCAL_REPO} → ${PEER_IP} (self_serial=${SELF_SERIAL})"
    rsync "${RSYNC_FLAGS[@]}" "${EXCLUDES[@]}" \
      "${LOCAL_REPO}/" \
      "${PEER_USER}@${PEER_IP}:${REMOTE_REPO}/"
    ;;
  dryrun)
    echo "[federation] DRYRUN diff with ${PEER_IP} (self_serial=${SELF_SERIAL})"
    rsync "${RSYNC_FLAGS[@]}" --dry-run --itemize-changes "${EXCLUDES[@]}" "${PULL_EXCLUDES[@]}" \
      "${PEER_USER}@${PEER_IP}:${REMOTE_REPO}/" \
      "${LOCAL_REPO}/"
    ;;
  *)
    usage
    ;;
esac

EXIT=$?
[ $EXIT -ne 0 ] && { echo "[ERR] rsync exit $EXIT" >&2; exit 2; }

# post-sync ledger integrity check (read-only, fast)
LEDGER="${LOCAL_REPO}/repair_log.jsonl"
if [ -f "$LEDGER" ]; then
  SHA=$(shasum -a 256 "$LEDGER" | awk '{print $1}')
  echo "[federation] post-sync ledger sha256: $SHA"
  echo "[federation] post-sync ledger bytes:  $(wc -c < "$LEDGER" | tr -d ' ')"
fi

echo "[federation] OK"
