# Restart repair checkpoint

Desktop process was running and the crash log contained no crash after its
latest boot. This is a bounded inspection, not a full-system health guarantee.

Repairs:
- Removed double hashing of session IDs at the generated-image HTTP handler;
  the image service already hashes the raw session ID. Correct sessions were
  otherwise rejected with 404.
- Restored navigation-epoch protection for polling and completed the pending
  message-to-node mapping; guarded missing attachment-host references.
- Local image links use the chorus listener port instead of Harness port 3080.
- Updated the obsolete disclaimer assertion to require #SIFTA and absence of
  the removed sentence.
- Configured SIFTA_BONSAI_DEMO_DIR in the two installed local LaunchAgents.
  Reloaded chorus and the night worker. The worker bootstrap needed one retry;
  it subsequently reported running. These machine-specific settings remain local.

Verification: 39 focused tests passed (image delivery/session isolation,
variation, web routing, display connection). Python compilation and diff
whitespace checks passed. The live chorus now reports image_generation=true
and serves the updated message code. Backend readiness does not prove a fresh
image generation or browser preview; neither was asserted in this checkpoint.

The already-open desktop retains its imported Python code until its next
restart; the local-chat link correction takes effect then. Web fixes are live
after the service reload. Other pre-existing worktree edits remain preserved.
