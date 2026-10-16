#!/bin/bash
# Re-apply every local modification to the INSTALLED dsh build.
#
# Why this exists: both patches live inside built bundles under
# /opt/homebrew/lib/node_modules/@deepseek-ai/dsh, so any
#   npm install -g @deepseek-ai/dsh@...
# silently reverts them. That is how the first-person label was lost once
# already. Run this after every dsh upgrade.
#
# The two patches, and why each is owed:
#
#  1. FIRST-PERSON STATUS LINE. Upstream ships `"chat.deepDiving": "Deep diving"`.
#     Architect, 2026-10-15: in this room there are exactly two entities — George
#     who types, and Alice whose body this laptop is. A status line naming her in
#     the third person invents a third entity reporting on her to herself. It now
#     reads "I am thinking". See the first-person rule in AGENTS.md.
#
#  2. LOOPBACK AUTH BYPASS. dsh 0.2.0 gates the UI behind a per-launch token.
#     The embedded browser cannot be handed a fresh token on every boot, so it
#     sat on "dsh web authentication required". The /api browser-trust fence
#     already accepts loopback (and still rejects DNS-rebinding), so the token
#     only ever punished the owner's own browser. The arm binds 127.0.0.1 only.
#     This restores the pre-0.2.0 behaviour and is deliberately local-only.
#
# Idempotent. Backs up before writing. Refuses rather than guesses if an anchor
# is not found exactly once.
set -euo pipefail

if [[ "${1:-}" == "--acknowledge-loopback-risk" ]]; then
  ACK=1
else
  ACK=0
fi

/usr/bin/python3 - "$ACK" <<'PY'
import sys, shutil, datetime, pathlib

ack = sys.argv[1] == "1"
H = pathlib.Path("/opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai")
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

jobs = []

# ---- 1. first-person status label -------------------------------------------
label = H / "dsh-client-ui-chat/lib/client.js"
jobs.append((label, [
    ('"chat.deepDiving": "Deep diving",',    '"chat.deepDiving": "I am thinking",'),
    ('"chat.deepDivingFor": "Deep diving for {duration} ···",',
                                             '"chat.deepDivingFor": "I am thinking for {duration} ···",'),
], 'first-person status label', True, '"chat.deepDiving": "I am thinking",'))

# ---- 2. loopback auth bypass ------------------------------------------------
auth = H / "dsh-client-connection/lib/index.js"
jobs.append((auth, [(
'''	isAuthenticated(request) {
		const authority = requestAuthority(request.headers);
		const rawCookie = header(request.headers, "cookie");''',
'''	isAuthenticated(request) {
		const authority = requestAuthority(request.headers);
		// LOCAL PATCH (SIFTA 2026-10-15). Loopback is the owner's own machine and
		// the /api browser-trust fence already accepted it above. The launch token
		// guards against a *remote* page driving a local agent; on 127.0.0.1 it
		// only broke the embedded browser, which cannot be handed a fresh token on
		// every boot. See scripts/restore_dsh_local_patches.sh for the reasoning.
		if (authority !== void 0) {
			let host;
			try { host = new URL(`http://${authority}`).hostname; } catch { host = void 0; }
			if (host !== void 0 && isLoopbackHostname(host)) return true;
		}
		const rawCookie = header(request.headers, "cookie");''',
)], 'loopback auth bypass', ack, 'isLoopbackHostname(host)) return true'))

for path, pairs, name, enabled, marker in jobs:
    if not path.exists():
        print(f"SKIP  {name}: no bundle at {path}")
        continue
    text = path.read_text(encoding="utf-8")
    # Detect on the functional line, never on a comment: comments get reworded
    # and a stale marker would make this re-apply over its own work.
    if marker in text:
        print(f"ok    {name}: already applied")
        continue
    if not enabled:
        print(f"HELD  {name}: needs --acknowledge-loopback-risk (it removes a security gate)")
        continue
    for old, new in pairs:
        if text.count(old) != 1:
            raise SystemExit(f"REFUSED {name}: anchor found {text.count(old)}x, expected 1")
    backup = path.with_name(path.name + f".bak-{stamp}")
    shutil.copy2(path, backup)
    for old, new in pairs:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"done  {name}  (backup: {backup.name})")
PY

echo
echo "Restart the arm to serve the changes:"
echo "  launchctl kickstart -k gui/\$(id -u)/com.sifta.dsh-web"
