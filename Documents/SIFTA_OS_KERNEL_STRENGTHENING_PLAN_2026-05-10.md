# SIFTA OS Kernel Strengthening Plan — 2026-05-10

**Owner direction:** keep the Steve Jobs / macOS body. SIFTA remains a Python + PyQt desktop organism inside `sifta_os_desktop.py`; do not drift into Linux service-manager assumptions. The classical OS diagram is useful because kernel concepts are portable: process tables, scheduling, interrupts, rings, I/O, syscalls, memory, and indexed storage.

## Verdict

SIFTA already has organs, ledgers, senses, metabolism, agent arms, and receipts. The missing layer is kernel discipline: every swimmer must become a visible, scheduled, permissioned, budgeted, receipted OS process.

## Kernel Spine

1. **Unified process table**
   - File: `System/swarm_kernel_process_table.py`.
   - Purpose: one live/accountable view of all organs, agent arms, UI surfaces, repair loops, and sensors.
   - Required fields: `pid`, `organ_id`, `ring`, `health`, `stgm_balance`, `current_job`, `last_receipt_id`, `failure_count`, `last_heartbeat_ts`, `location`, `bodies_present`, `metadata`.

2. **Kernel ABI**
   - First stable calls: `register`, `heartbeat`, `terminate`, `get`, `snapshot`, `list_by_ring`, `list_unhealthy`, `aggregate_organism_health`.
   - Later calls: `sys_sense`, `sys_think`, `sys_act`, `sys_receipt`, `sys_spend_stgm`, `sys_schedule`, `sys_memory_query`.

3. **Privilege rings**
   - Ring 0: crypto, owner genesis, STGM ledger, kernel table.
   - Ring 1: core organs: desktop body, Talk, vision, memory, metabolism, boot.
   - Ring 2: agent arms and tool routers: Codex, Hermes, Corvid, research arms.
   - Ring 3: UI/chat/media/co-watch/adapters.
   - Rule: lower rings may request higher-ring action only through a receipt-backed kernel ABI.

4. **Budgeted scheduler**
   - One scheduler allocates inference, CPU, GPU, STGM, UI attention, and sensor priority.
   - Inputs: process table health, STGM deltas, owner presence, thermal/metabolic state, pending interrupts.
   - Output: allow, throttle, defer, preempt, or quarantine.

5. **Interrupt controller**
   - Highest priority: owner direct typed/speech input, safety, hot machine, effector failure, identity/receipt violation.
   - Medium: agent arm result, tool completion, sensor novelty, memory recall.
   - Low: ambient media/co-watch chatter.

6. **Filesystem-style organ namespace**
   - `/kernel/process_table`
   - `/kernel/scheduler`
   - `/organs/vision/eye0`
   - `/organs/talk/broca`
   - `/organs/memory/hippocampus`
   - `/agents/codex`
   - `/agents/hermes`
   - `/economy/wallets`
   - `/receipts/work`

## Jobs / Apple Constraint

The table must simplify, not add visible friction. The user should experience one coherent organism: beautiful desktop body, direct speech, receipts when needed, no exposed machinery unless debugging. Internally, every organ is accountable; externally, Alice feels integrated.

## Implementation Order

1. Ship `swarm_kernel_process_table.py` with append-only receipts and tests.
2. Register `sifta_os_desktop.py` and `swarm_boot.py` as first ring-1 processes.
3. Wire Talk, vision, hippocampus, metabolic governor, and Corvid into heartbeats.
4. Add STGM budget checks to agent arm dispatch.
5. Add ring enforcement to tool router and effectors.
6. Add a System Settings panel that reads the process table.
7. Add interrupt preemption: owner direct input beats media and low-confidence ambient turns.

## Non-Deviation Rule

Do not add systemd, launchd services, Linux-only daemons, or detached chat servers for core Alice organs. macOS is the skeleton; SIFTA is the Python/PyQt organism layered inside it.
