# Alice on your phone: independent LAN connection

## Use

1. Restart SIFTA once to load the new Settings code.
2. Open **System Settings > Network > Telefon local / conectare prin QR**.
3. Put phone and laptop on the same trusted Wi-Fi, select the laptop's local
   address and an installed Ollama model, then press **Porneste / QR nou**.
4. Scan the QR with the phone camera. The page opens in the phone's browser;
   press **Conecteaza acest telefon**, then type a message.
5. Optionally use the phone browser's Add to Home Screen feature. This is a
   locally served web interface, not an App Store application or offline model
   running on the phone. Keep the laptop awake and SIFTA/Ollama running.

The phone needs no cloud account, LM Studio, Locally app, subscription or
internet connection at runtime. The QR and all page assets are generated
locally. Installing the Python dependencies initially may require internet.

## Scope and privacy

- Opt-in listener bound only to the chosen private IPv4 interface and an OS-
  allocated port; not added to the existing public Chorus/Cloudflare gateway.
- HTTP is **not encrypted**. Use a trusted home Wi-Fi only, not cafe/hotel/
  shared public Wi-Fi. Authentication does not prevent a network eavesdropper
  reading traffic. No router forwarding, tunnel or public publishing is set up.
- Single-use 256-bit pairing code, five-minute expiry. A new QR invalidates
  the old unconsumed code, not already paired phones.
- Phone credentials are HttpOnly/SameSite cookies, valid 12 hours. Stop revokes
  all phones. Process restart also revokes them. At most eight active phones.
- Exact Host/Origin checks, no cross-origin API access, no forwarded-client
  headers. Only authenticated devices can read their own chat or submit text.
- History is private per paired session and stays on this laptop under
  `.sifta_state/phone_link/`, with restrictive filesystem permissions. Reloading
  the page retains it while the pairing is valid. Re-pairing starts a fresh
  conversation; old transcripts remain local, not automatically restored.
- This is a text-only Alice transport: no tools, shell, camera, desktop control,
  file/image uploads or downloads. It does not import the owner's desktop chat
  or another visitor's history. It does not add phone text to the public wall.
- Model is chosen on the laptop, pinned for the active link. Change it by
  stopping and restarting the link; the main SIFTA cortex setting is unchanged.
- Inference connects only to `127.0.0.1:11434`, ignoring HTTP proxy and alternate
  Ollama host environment variables. Remote/cloud model metadata is rejected.
  There is no cloud fallback, model download or automatic installation.
- One phone inference at a time, bounded text/context/output, idempotent request
  IDs and visible errors. An already running local inference may finish after
  Stop, but revoked devices can no longer retrieve it. Other SIFTA inference
  workloads can still compete for laptop memory/compute.

## Files and verification

- `System/sifta_phone_link.py`: LAN transport, pairing, private transcript and
  receipt persistence, local inference adapter.
- `System/sifta_phone_link.html`: responsive light/dark phone UI; local assets.
- `Applications/sifta_phone_link_dialog.py`: model/address selection, QR, revoke.
- `Applications/sifta_system_settings.py`: Network entry point.
- `tests/test_phone_link.py`, `tests/test_phone_link_dialog.py`: real localhost
  HTTP tests with a stubbed inference backend, auth/origin/expiry/isolation,
  duplicate handling, failures, cloud rejection and offscreen Qt UI tests.

Run `python3 -m pytest -q tests/test_phone_link.py tests/test_phone_link_dialog.py`.
Installation includes `qrcode>=8.2,<9` and `psutil>=5.9` in requirements.txt.

Phone Safari rendering, camera QR scanning and the actual phone-to-laptop Wi-Fi
hop require a device check. WebBridge had no connected extension during this
implementation; those are not claimed as tested.

2026-09-08 verification: 21 focused tests passed (phone transport, offscreen
pairing panel, inference/display settings regression checks); inline JavaScript
syntax and Python compilation passed. A real local inference probe using the
already-loaded `satgeze/qwenpaw-9b-heretic-1m:latest` exceeded the 120-second
response timeout. No real-model reply or complete phone end-to-end success is
claimed. The transport reports model failure without cloud fallback. No live
SIFTA restart or persistent LAN listener was started during verification.

Protocol references: [Ollama local API](https://docs.ollama.com/api/introduction),
[Ollama cloud distinction](https://docs.ollama.com/cloud),
[offline QR library](https://pypi.org/project/qrcode/8.2/).
