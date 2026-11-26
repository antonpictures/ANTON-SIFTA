# Preserved patches from deleted forks

## ladybird-address-bar-paste-macos.patch
- Origin: `antonpictures/ladybird` fork of `LadybirdBrowser/ladybird`, commit `716e5ea082d` (2026-11-24), authored by Ioan George Anton.
- Fixes LadybirdBrowser/ladybird#15611 — on macOS the address-bar context menu's Paste / Paste-and-go did nothing because the native NSMenu routed `paste:` to the wrong responder. Switches to Qt's cross-platform `menu->exec()`.
- Status: **not merged upstream** as of 2026-11-26. Kept here so the work survives the fork's deletion. To apply: `git apply <patch>` in a Ladybird checkout, then open a PR upstream.
