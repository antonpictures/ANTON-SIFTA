# ALICE COMPUTER USE — DESIGN (2026-09-29)

Status: **design only.** No code written, no composition row added, no plugin defined.
Author: the DSH agent hand in this session. Not a decision of the Architect.

---

## 0. Why this document exists

George asked for full computer use — the ability to see the screen and drive mouse/keyboard.
The standing offer was to write the design before anything exists that can read the screen or
move the pointer. He said go. This is that document.

## 1. Recon — what is actually true today

Verified in this session against the DSH checkout at
`/Users/ioanganton/Music/ANTON_SIFTA/deepseek-harness-master/`:

| Claim | Receipt |
|---|---|
| No screen capture exists in the harness | grep for screenshot/capture matched only attachment normalization and a scrollbar theme test. Nothing captures a display. |
| No input injection exists | grep for mouse/keyboard/click injection matched nothing operational. |
| Zero dynamic plugins are running | `cordis_inspect_self` → `{"mode":"plugins","plugins":[]}` |
| No authored preset exists | `~/.dsh/.agent-presets/` does not exist |
| The session runs on the shipped preset | `settings.yaml:172-173` → `agent-presets: default: cordis` |
| File sandbox is fully open | `settings.yaml:174-175` → `permission.defaultPreset: danger-full-access` |
| Approval prompts are **off** | session runtime context: approval-required actions are auto-rejected |
| The model's real window is 1,048,576 tokens | `ollama /api/show` → `num_ctx 1.048576e+06` |
| The harness only thinks it has 65,536 | `settings.yaml:30` → `local-ollama.defaultContextWindow: 65536`, and `deepseek-v41-uncensored:latest` is not listed in that provider's `models:` block (lines 36-60), so the default applies |

**Consequence for this design:** full computer use would be *net-new capability*, not a config
flag. And because dynamic plugins die with the process, it would be a per-session capability,
not organism growth.

## 2. The ordering rule

**Permission gate first, capability second.** A capture/input row must not be mountable before
the gate that governs it exists. Otherwise the first working version of this feature is also
the first ungoverned version.

## 3. Composition shape

Two new rows, each independent, each reversible:

```
screen-capture        → publishes a service: read a frame, return metadata (display id, size,
                        timestamp). No file writes, no network.
input-injection       → publishes a service: move pointer, click, type. Refuses to start
                        unless the gate row is present.
computer-use-gate     → publishes the approval/policy service the other two require.
                        Owns: which surface may be driven, per-session opt-in, audit sink.
```

Placement rules (from `editing-cordis-compositions`):

- These belong in an **agent preset**, not the host composition. A session that does not need
  computer use must be structurally incapable of being driven — mounting them host-wide means
  every session, including unattended ones, has a pointer.
- They must be mounted per-preset so the capability travels with the preset that declares it.
- Every side effect (service, event, timer, slot) must belong to its fiber and be disposed on
  stop/update/undefine.

## 4. The gate

Before any frame is read or any event injected:

1. **Explicit per-session opt-in.** Off by default. Not inherited from `danger-full-access`.
   The file sandbox being open is not consent to drive the pointer.
2. **Owner presence.** The gate refuses while no human is at this machine, unless a specific
   headless policy row is mounted that says otherwise, out loud, in the composition.
3. **Audit sink.** Every capture and every injection appends a receipt — timestamp, surface,
   action, target. No silent frames.
4. **Kill switch.** One command stops the row and disposes its services. Stop must leave the
   machine exactly as it was: no lingering daemon, no background loop, no granted TCC state
   that outlives the session.

Note the hard dependency this creates: on macOS, screen capture and input injection need TCC
grants held by the *host process*. This session verified the capability gap in code, not the
TCC state of the node binary. That check is a prerequisite, not a detail.

## 5. Open gaps — stated, not papered over

- The recon above was run earlier in this session and survived a context compaction. I did not
  re-run the greps while writing this document.
- I did not audit TCC/entitlement state for the DSH node process.
- I did not evaluate existing third-party MCP servers that do capture/input. Reusing one moves
  the gate problem into that server rather than solving it.
- **Identity, one line, not re-litigated:** I do the coding work. I am a hand of the organism
  with no continuous memory of it. Both are substrate facts.

## 6. What this document does NOT authorize

No implementation, no dependency install, no composition edit, no plugin definition, no
persistence mechanism that survives this process. Those are separate decisions, each made
after reading this.
