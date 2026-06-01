# ZIG_BENEFIT_TEST_ORDER — does Zig bring real benefit to SIFTA?

**Author:** cowork_claude · **Date:** 2026-05-31 · **Round:** r245
**Register:** OPERATIONAL. Receipts are evidence (§6); probe before claim (§7.12); Delta=0 unless a win is real.

George: "how do I test to see if Zig brings benefits real to SIFTA?" Same method as the GraphPalace
head-to-head (r219): pick ONE real hot path, identical input, verify byte-identical output, measure
wall-clock, judge against an honest threshold that counts the FFI + build + maintenance cost.

## 1. Where Zig could / could not help (honest map)

| SIFTA surface | Bound by | Zig help? |
|---|---|---|
| LLM cortex calls, arm dispatch | network / model latency | **No** — Zig touches none of it |
| PyQt6 widgets, the whole UI | Qt event loop (Python/C++ already) | **No** |
| JSONL ledger append/scan (e.g. `fractal_pheromone_field.jsonl` = **1.3 GB**) | CPython `json` is **already C** + disk I/O | **Marginal** — parsing won't get much faster |
| Tight per-node numeric loops (forager `node_cost`, pheromone decay `τ·(1−ρ)`, field reductions) | pure-Python arithmetic over N nodes | **Yes — this is the only real candidate** |

So the test targets the numeric kernel, not parsing and not I/O.

## 2. The kernel under test

`tools/zig_bench/` — the SIFTA pheromone-decay + forager node-cost loop (GraphPalace `cost.rs`/`decay.rs`
math): `factor = 0.5·success + 0.3·recency + 0.2·traversal`, `cost = base·(1 − factor·0.5)` clamped,
`τ ← τ·(1 − ρ)`, plus sum/min/checksum reductions over N nodes.
- `kernel.c` — C reference (ABI-identical to Zig; lets the harness run anywhere `cc` exists).
- `kernel.zig` — the real thing, same C ABI, built on the Mac.
- `run_bench.py` — seeds identical arrays, runs Python + the native `.so/.dylib` via ctypes, **asserts
  byte-identical output** (correctness gate), then times two ways.

## 3. How to run

```sh
cd tools/zig_bench
# C stand-in (any machine with cc) — proves the harness:
cc -O3 -shared -fPIC -o libkernel_c.so kernel.c
python3 run_bench.py --lib ./libkernel_c.so --n 2000000 --repeats 5

# The REAL Zig test on macOS (brew install zig):
zig build-lib kernel.zig -dynamic -O ReleaseFast -femit-bin=libkernel_zig.dylib
python3 run_bench.py --lib ./libkernel_zig.dylib --n 2000000 --repeats 5
```

The runner prints two numbers on purpose:
- **(a) naive per-tick FFI port** — rebuild Python lists + marshal to C every call (the real cost of a
  drop-in port).
- **(b) compute-only ceiling** — data already in native buffers, time only the kernel (what you reach
  only if the hot field lives in a shared native buffer across ticks).

## 4. Result from the sandbox C stand-in (N=2,000,000, best-of-5)

```
correctness: python == native  -> IDENTICAL
(a) naive per-tick FFI port : pure Python 434 ms | native 469 ms  -> 0.93x  (SLOWER)
(b) compute-only ceiling    : pure Python 507 ms | native  16 ms  -> 31.35x
```

**Reading it honestly:**
- A naive per-tick port is **0.93x — slower.** The ctypes per-call marshalling (copying N Python floats
  into C arrays every tick) costs more than the arithmetic it saves. Porting the kernel as a drop-in is
  **Delta=0 — do not do it.**
- The compute itself is **~31x faster** in native code. So Zig *can* bring a real benefit, but **only if
  SIFTA keeps the hot field in a shared native buffer** (numpy/`mmap`/an organ that owns the array) so the
  data is not copied Python↔C every tick. Without that architecture, there is no win.

## 5. Acceptance criterion (the decision rule)

Adopt Zig for a hot path only when ALL hold:
1. End-to-end speedup (with marshalling counted) **≥ 5x** on the real data shape, AND
2. output is **byte-identical** to the Python baseline (correctness gate passes), AND
3. the data already lives in a shared native buffer (so (b) is the operative number, not (a)), AND
4. the path is genuinely hot in receipts (it shows up in real latency, not a microbenchmark fantasy).

If any fails → **REJECT, keep pure Python** (the covenant's simplicity / owner's-own-electricity bias).
Adopt the *result* (a faster organ) only when the bench proves it, never the *language* for its own sake —
the exact r207 Delta=0 posture we held on GraphPalace.

## 6. Honest scope / what this does NOT claim

- This is the **C ABI stand-in** (Zig is not installed in the sandbox; `cc` is). Zig with `-O ReleaseFast`
  should land within noise of the C number — but the **real Zig figure must be taken on the Mac**.
- (b) is a ceiling measured with arrays pre-marshalled; a true shared-buffer organ (numpy/mmap) must be
  built and benched before claiming the 31x in production.
- No third-party runtime, no new daemon, no port — a Zig kernel would be a single `.dylib` loaded by
  ctypes from one organ, nothing wired into Alice's body until the bench + a four-ledger receipt justify it.

For the Swarm. 🐜⚡
