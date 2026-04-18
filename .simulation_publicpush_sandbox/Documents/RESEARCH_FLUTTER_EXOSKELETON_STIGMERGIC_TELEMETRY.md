# Research — Flutter “exoskeleton” for SIFTA stigmergic telemetry (DYOR)

**Retrieved / anchored:** 2026-04-17 (M5 session).  
**Goal:** Native Flutter/Dart UI for live **λ**, **memory_fitness.json**, apoptosis / CWMS signals — **no Node.js backend**, Python remains source of truth.

This note is **architecture + citations**, not a full `pubspec.yaml` scaffold.

---

## 1. Why this matches stigmergy (literature, not vibes)

Stigmergy = coordination through **persistent traces** in the environment rather than direct agent-to-agent messaging (Bonabeau / Dorigo line of work on swarm intelligence and artificial stigmergy). Your JSONL + locked overlays are literal pheromone fields; a Flutter client is a **sensorimotor surface** that reads the field — consistent with multi-robot / SI “environment as state” framing.

**Entry points (for SwarmGPT / literature stack):**

- Bonabeau, Dorigo, Theraulaz — *Swarm Intelligence: From Natural to Artificial Systems* (Oxford University Press, 1999) — canonical SI text (often cited for stigmergy + ACO). Semantic Scholar hub: `https://www.semanticscholar.org/paper/Swarm-intelligence%3A-from-natural-to-artificial-Bonabeau-Dorigo/8991b622e0b9fd8f8a4cb219b3aa8bad0a6346cf`
- Bonabeau — “Editor’s Introduction: Stigmergy” — *Artificial Life* framing (1999). `https://www.semanticscholar.org/paper/Editor's-Introduction:-Stigmergy-Bonabeau/2f33c1a583ff77b85253aa75845f46af98eb648c`
- Dorigo & Birattari — broader SI survey PDF (IRIDIA): `https://iridia.ulb.ac.be/~mdorigo/Published_papers/All_Dorigo_papers/DorBir2007sch-si.pdf`

**Economics / “metabolism” (dual prices):** online primal–dual and dual resource prices (shadow λ-like variables) — Balseiro et al., *Dual Mirror Descent for Online Allocation Problems* (PMLR 2020): `https://proceedings.mlr.press/v119/balseiro20a.html`

---

## 2. Three viable transport patterns (pick one first)

| Pattern | Data path | Pros | Cons |
|--------|-----------|------|------|
| **A. Direct file tail + `watch`** | Flutter `dart:io` reads repo `.sifta_state/*.jsonl` + `memory_fitness.json`; `FileSystemEntity.watch` on directory | Zero extra Python; true “dirt only” | macOS FSEvents coalescing; must **debounce**; JSONL tail parsing; **path sandbox** required |
| **B. Localhost WebSocket / SSE** | Small Python **read-only** relay (`aiohttp` / `websockets`) tails files and pushes events to `ws://127.0.0.1:…` | Clean Dart `StreamChannel`; easy backpressure | Extra process; must bind **loopback only** + optional token |
| **C. Unix domain socket / `dart_ipc`** | Dart `dart_ipc` / domain socket; Python writer on same path | Fast, no TCP stack; good for desktop | More plumbing; platform paths |

**Security baseline (all patterns):**

- **Allowlist paths** under repo `.sifta_state/` only (no arbitrary FS).
- If **B**: bind `127.0.0.1`, refuse non-local; optional HMAC/bearer read from a **gitignored** `.sifta_state/flutter_bridge_token.txt` minted once at pairing.
- **Never** expose Ed25519 signing keys to Flutter; UI is **read-mostly** + optional **commands** only through audited Python RPC later.

---

## 3. Flutter reactive layer (Riverpod vs Bloc)

**Riverpod:** model each substrate as `StreamProvider` / `AsyncNotifier` fed by a single `TelemetryRepository` that exposes:

- `Stream<TelemetryFrame> watchFitness()` — `read_write_json_locked` compatibility means Flutter should **re-read whole file** on change debounced (300–500 ms), not assume incremental JSON patch.
- `Stream<List<IdeTrace>> tailIdeTrace(int n)` — tail last *N* lines of `ide_stigmergic_trace.jsonl`.

**Bloc:** one `TelemetryBloc` with events `Subscribe`, `Tick`, `NewFileEvent`; map `FileSystemEvent` → `ReloadSnapshot` with debounce.

**Parsing:** JSONL = split lines, `jsonDecode` per line; tolerate partial last line during concurrent append (retry on `FormatException`).

---

## 4. `StigmergicTelemetryClient` (conceptual Dart API — not shipped code)

```dart
/// Contract only — implement with Pattern A or B above.
abstract class StigmergicTelemetryClient {
  Stream<double> lagrangianPressure();      // from manifold snapshot or relay
  Stream<FitnessOverlay> memoryFitness();   // parsed memory_fitness.json
  Stream<List<IdeHandoff>> ideTail();      // tail ide_stigmergic_trace.jsonl
  Future<void> dispose();
}
```

**Widgets:** `λ` gauge, bunker/calm label (reuse thresholds from `stgm_metabolic.metabolic_regime_label`), fitness heat-list by `trace_id`, apoptosis log from a **dedicated** `apoptosis_events.jsonl` if you add one (avoid parsing full ledger for UI).

---

## 5. Relation to current Python vectors (truth on disk)

- **V11–V13:** CWMS + ACMF + GCI outcome loop — already emit state under `.sifta_state/`.
- **V14:** `stgm_metabolic.py` — pure functions; Flutter can **duplicate** the formulas for display or read a tiny `metabolic_snapshot.json` if Python writes one later.
- **V15:** `apoptosis_engine.py` — salvage writes go through `remember()`; UI should show **counts / last event**, not forge ledger lines.

---

## 6. Suggested first sprint (minimal vertical slice)

1. Flutter **desktop** app, Pattern **A**, read-only: **one** screen = `memory_fitness.json` + `ide_stigmergic_trace.jsonl` tail + λ from `lagrangian_constraint_manifold` **if** you add a one-line JSON snapshot file from Python (optional) — else show λ only after small Python relay.
2. Debounced `watch` on `.sifta_state/`.
3. No writes from Flutter v0.

---

## 7. “Johnny Mnemonic” sync (product, not physics)

Public posts (X) are **human-readable anchors**; they do not replace signed ledgers. Treat social telemetry as **narrative checksum**, not consensus.

---

**Verdict:** Yes — you can start the Flutter exoskeleton now with **Pattern A (file watch + tail)** for zero new moving parts, then graduate to **B** if coalescing / parsing pain exceeds a day of engineering.
