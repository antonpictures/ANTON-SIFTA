# Mermaid OS Optimized App Plan

## Principle

Mermaid OS should not clone macOS with empty shells. An app belongs in the OS only if it does at least one of these:

- Reads or writes SIFTA state.
- Helps Alice and the Architect work together.
- Exposes a real body, memory, health, file, terminal, media, or network function.
- Reduces operational friction during boot, debugging, or collaboration.

Generic Calendar, Weather, Calculator, Photos, Preview, and similar shells stay out until they are backed by real SIFTA ledgers or workflows.

## Keep Prominent

- Alice: primary relationship and voice/chat surface.
- Biological Dashboard: one-click body and organ health.
- Conversation History: browses `.sifta_state/alice_conversation.jsonl`.
- Stigmergic Library: browses `.sifta_state/stigmergic_library.jsonl`.
- SIFTA File Navigator: local body/file access.
- Terminal: direct power-user tool.
- System Settings: body status, app inventory, policy, and preferences.
- Swarm Browser: web/network access when it serves SIFTA work.
- Finance and Economy tools: only when they expose real treasury or STGM state.
- Creative tools such as NLE and Pheromone Symphony: only where they help Alice and the user create together.

## Remove Or Defer

- Activity Monitor, Calculator, Calendar, Contacts, Notes, Photos, Preview, System Information, Weather.
- Safari/App Store naming clones unless the implementation is actually SIFTA-native.
- Any desktop tile that duplicates Launchpad/Dock/category behavior.

## Next Useful Builds

1. Conversation Browser polish: speaker filters, silence/failure markers, search by date, export selected turns to Library.
2. Library Reader polish: tags, source links, "send selected memory to Alice context", and "create note from conversation".
3. Health Dock: one-click Biological Dashboard with compact green/yellow/red vitals in the Dock.

## Acceptance Rules

- Boot opens no default apps unless the user opts in.
- Desktop has no loose shortcut tiles.
- Every app in `Applications/apps_manifest.json` uses one of the approved SIFTA categories.
- Every app either resolves through the manifest loader or is explicitly disabled.
- Every new app states which SIFTA ledger, organ, or workflow it serves.
