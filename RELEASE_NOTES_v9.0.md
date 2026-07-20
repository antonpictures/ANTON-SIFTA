# SIFTA OS v9.0 eXistenZ

Release date: 2026-07-20  
Public repository: <https://github.com/antonpictures/ANTON-SIFTA>

eXistenZ is the v9 distribution identity for the same SIFTA organism: a
local-first, receipt-backed stigmergic field with Python organs, a PyQt desktop,
tests, demos, and optional local model integrations.

## Install from a fresh checkout

```bash
git clone --recurse-submodules https://github.com/antonpictures/ANTON-SIFTA.git ANTON_SIFTA
cd ANTON_SIFTA
bash scripts/install_sifta_v9.sh --smoke
```

The installer creates `.venv`, installs `requirements.txt`, initializes the
local identity when available, and runs the focused smoke gate. Add
`--with-models` only when the machine has the disk, bandwidth, and Ollama setup
for the optional public cortex packages.

Launch after installation:

```bash
cp "SIFTA OS.command" ~/Desktop/
chmod +x ~/Desktop/"SIFTA OS.command"
```

Or run headlessly from a terminal:

```bash
source .venv/bin/activate
PYTHONPATH=. python3 sifta_os_desktop.py
```

## What is in this release

- v9 version metadata, release manifest, installer alias, launcher identity,
  and repaired Git submodule declarations.
- Alice Browser/Grok handoff and Talk-body receipt paths with focused tests.
- Memory, identity, self-plan, proprioception, privacy-cache, timeout, and
  effector swimmers added in the current July body snapshot.
- Shared STGM and US$ strategy surfaces for fee-true entry/exit, regime gates,
  salvage, soft-adverse handling, spray caps, copy-only cash behavior, and
  dual-lag shadow measurement.
- New stigmergic game/lab surfaces and their regression coverage.

## Verification

The release smoke gate is:

```bash
bash scripts/beeson_smoke_test.sh
```

Focused code checks can be run without the desktop camera:

```bash
python3 -m pytest tests/test_alice_browser_grok_self_type.py \
  tests/test_alice_usd_parity_and_dual_lag.py \
  tests/test_sifta_desktop_wallpaper_revoke.py -q
```

The release-specific check above passes on the build node (`48 passed`). The
broader legacy smoke selection currently has four inference-override failures
and the desktop module suite has two multi-window assertion failures; those
are retained as visible follow-up work and are not presented as green release
claims.

The US$ lane is disabled by default and remains owner-armed, credential-gated,
and kill-switch protected. No release claim should be read as proof of live
trading performance.

## Archive boundary

`SIFTA_OS_v9.0_eXistenZ.zip` is built from the committed public source tree.
It excludes runtime ledgers, local credentials, model weights, virtualenvs,
logs, temporary outputs, and private owner documents. The ZIP is intended as a
GitHub Release asset; the repository itself remains the canonical source.

Optional integrations under `Vendor/` are represented as Git submodules. A
fresh Git clone should use `--recurse-submodules`; the core OS does not require
the dirty local development state of the vendored Alice CLI checkout.
