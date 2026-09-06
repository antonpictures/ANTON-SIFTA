# Boot and Installation Audit - September 6, 2026

Status: CORE INSTALL VERIFIED IN ISOLATION; LIVE HEALTH DEGRADED; PUSH HELD.

## Live node

The desktop process and Ollama service were running. Hardware heartbeat receipts
were fresh (under 30 seconds at sampling). Signed health receipts reported FAULT
with `body_writer_supervisor_degraded`. One new isolated writer timeout occurred
during this inspection, in addition to old timeouts from the previous session.
The runtime has not passed the owner's condition "push if healthy".

The refreshed matrix inventory reports 20/20 canonical organs present, 172
application surfaces and 1,271 registry entries. Presence is not a passed health
test: the registry still reports sparse evidence/path coverage for several organs.
Do not replace the observed health state with a green badge based on file counts.

## Repairs made

- Recent-timeout counting now checks a five-minute age window. Old-session,
  malformed and future timestamps no longer keep a new session degraded.
- The lookup reads a bounded 256 KiB tail instead of rescanning a 55 MB ledger.
- Writer stages now publish a local progress marker and duration measurements.
  If a child is killed, the last running stage remains available for diagnosis.
  This instrumentation does not turn a failed tick into success.
- Core installation no longer requires optional upstream Git submodules.
  Request them with `--with-vendor`; their repositories/revisions are a separate
  dependency and were not fetched or verified in this core install test.
- PKI errors stop installation. Smoke tests run before the successful install
  receipt and Desktop launcher are created.
- The Desktop launcher points to the actual checkout, including custom paths.
- Empty configuration templates replace shipping the owner's peer addresses.
  Existing local configurations are never overwritten.
- The dropdown layout test now supplies a test model inventory instead of
  depending on the owner's installed models and private state.

## Reproducible installation evidence

Base: tracked HEAD source exported with `git archive`, then overlaid with the
specific candidate installer/test fixes. No untracked Harness checkout, owner
memory, model weights or private key was copied into this candidate.

Environment: macOS 26.7 Apple Silicon, Python 3.14, new virtual environment and
dependencies downloaded from `requirements.txt`. The final installer run used
a separate temporary HOME and empty runtime state; the earlier smoke-generated
test state was moved aside before this run. This matters because reusing that
state with a different test key correctly triggers a trust mismatch.

Results:

- `bash scripts/install_sifta_v9.sh --smoke`: exit 0.
- PKI generation plus sign/verify bootstrap: passed with the isolated account key.
- Focused release smoke: 181 passed.
- Desktop module import using the newly installed dependencies: passed.
- Timeout/progress/installer contract tests: 31 passed.
- Successful install receipt: `9bf896cd-f887-424f-810e-9951780260cf`.
- Smoke receipt: `c4c2b6e4-f4f5-4d5e-ae2f-46ee98980480`.

This is not proof of a second physical Mac, camera/microphone permissions,
interactive WebEngine stability, downloaded cortex weights, every optional app,
peer settlement, or a fully green live organism. Those remain separate checks.
The familiar Applications/System/Library/Kernel layout is preserved; SIFTA is a
desktop/runtime environment hosted by macOS, not a replacement bootable macOS kernel.

## Public tree boundary

Seven previously tracked local files are removed from the next Git tree while
remaining on the owner's disk: root `config.json`, root `node_registry.json`,
and five files under `logs/`. Empty `.example.json` files are distributable.
`.sifta_state`, account keys, model weights and raw personal media remain excluded.
This does not erase files already present in historical commits. A full historical
privacy cleanup would be a separate, explicitly coordinated history rewrite.
Existing unrelated dirty app/browser/vendor changes were not included in this cut.

## Before pushing

Load the repaired writer in a fresh desktop session when unsaved work is safe.
Read `body_writer_progress_latest.json` if another timeout occurs, repair the
identified slow producer, and require a fresh complete non-degraded tick plus a
verified healthy receipt. Do not manufacture a receipt or delete the fault history
to make the release condition pass. Push remains on hold until live health passes.
