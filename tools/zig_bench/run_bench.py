#!/usr/bin/env python3
"""Zig-benefit head-to-head for SIFTA — does a native kernel actually beat pure Python? (r245)

George 2026-05-31: "how do I test to see if Zig brings benefits real to SIFTA?" Answer: the same
way we tested GraphPalace (r219) — a falsifiable head-to-head on ONE real hot path, identical input,
verify byte-identical output, measure wall-clock, then judge against an honest threshold.

Hot path under test: the SIFTA pheromone-decay + forager node-cost loop (GraphPalace cost.rs/decay.rs
math), the tight per-node numeric work that runs over the field. (NOT JSON parsing — CPython's json is
already C; the only place native wins is compute.)

Procedure:
  1. seed identical arrays (same seed) for N nodes,
  2. run the pure-Python baseline,
  3. run the native shared library via ctypes (libkernel_c.so here, libkernel_zig.dylib on the Mac),
  4. assert the native result == Python result (sum/min/checksum within float epsilon) — correctness gate,
  5. time both over R repeats, print speedup,
  6. print the VERDICT against the acceptance threshold (speedup must clear ACCEPT_X to justify the
     FFI + build + maintenance + simplicity cost; otherwise REJECT and keep pure Python).

Build the native lib first:
  C  (proves the harness anywhere cc exists):  cc -O3 -shared -fPIC -o libkernel_c.so kernel.c
  Zig (the real test on macOS):  zig build-lib kernel.zig -dynamic -O ReleaseFast -femit-bin=libkernel_zig.dylib
Then:  python3 run_bench.py [--lib ./libkernel_c.so] [--n 2000000] [--repeats 5]
"""
from __future__ import annotations

import argparse
import ctypes
import math
import os
import random
import time

ACCEPT_X = 5.0  # native must be >= 5x faster than pure Python to be worth the FFI+build+maintenance cost


def seed_arrays(n: int, seed: int = 1729):
    rnd = random.Random(seed)
    success = [rnd.random() * 1.3 for _ in range(n)]
    recency = [rnd.random() * 1.3 for _ in range(n)]
    traversal = [rnd.random() * 1.3 for _ in range(n)]
    base = [0.5 + rnd.random() * 9.5 for _ in range(n)]
    tau = [rnd.random() for _ in range(n)]
    return success, recency, traversal, base, tau


def python_kernel(success, recency, traversal, base, tau, rho):
    """Pure-Python baseline — byte-for-byte the same math/order as kernel.c / kernel.zig."""
    s_sum = 0.0
    mn = 1e300
    checksum = 0.0
    for i in range(len(base)):
        s = success[i]
        if s > 1.0:
            s = 1.0
        r = recency[i]
        if r > 1.0:
            r = 1.0
        t = traversal[i]
        if t > 1.0:
            t = 1.0
        factor = 0.5 * s + 0.3 * r + 0.2 * t
        cost = base[i] * (1.0 - factor * 0.5)
        if cost < 0.0:
            cost = 0.0
        if cost > 10.0:
            cost = 10.0
        tau[i] = tau[i] * (1.0 - rho)
        s_sum += cost
        if cost < mn:
            mn = cost
        checksum += cost * float(i % 7 + 1)
    return s_sum, mn, checksum


def native_kernel(lib_path, success, recency, traversal, base, tau, rho):
    lib = ctypes.CDLL(lib_path)
    lib.sifta_pheromone_kernel.restype = ctypes.c_double
    lib.sifta_pheromone_kernel.argtypes = [
        ctypes.POINTER(ctypes.c_double)] * 5 + [
        ctypes.c_double, ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
    n = len(base)
    Arr = ctypes.c_double * n
    c_succ, c_rec, c_trav, c_base = Arr(*success), Arr(*recency), Arr(*traversal), Arr(*base)
    c_tau = Arr(*tau)
    out_sum, out_min = ctypes.c_double(0.0), ctypes.c_double(0.0)
    checksum = lib.sifta_pheromone_kernel(c_succ, c_rec, c_trav, c_base, c_tau,
                                          ctypes.c_double(rho), n,
                                          ctypes.byref(out_sum), ctypes.byref(out_min))
    return out_sum.value, out_min.value, checksum


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", default=os.path.join(os.path.dirname(__file__), "libkernel_c.so"))
    ap.add_argument("--n", type=int, default=2_000_000)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--rho", type=float, default=0.05)
    args = ap.parse_args()

    if not os.path.exists(args.lib):
        print(f"[skip] native lib not built: {args.lib}\n"
              f"  C : cc -O3 -shared -fPIC -o {args.lib} kernel.c\n"
              f"  Zig: zig build-lib kernel.zig -dynamic -O ReleaseFast -femit-bin=libkernel_zig.dylib")
        return 2

    base_arrays = seed_arrays(args.n)

    # correctness gate — identical input, compare results
    py = python_kernel(*[list(a) for a in base_arrays], args.rho)
    nat = native_kernel(args.lib, *[list(a) for a in base_arrays], args.rho)
    eps = 1e-6 * max(1.0, abs(py[2]))
    ok = all(math.isclose(p, q, rel_tol=1e-9, abs_tol=eps) for p, q in zip(py, nat))
    print(f"correctness: python={tuple(round(x,4) for x in py)} native={tuple(round(x,4) for x in nat)} "
          f"-> {'IDENTICAL' if ok else 'MISMATCH!'}")
    if not ok:
        print("VERDICT: native kernel does NOT reproduce the Python result — reject, fix the port first.")
        return 1

    lib_kind = "Zig" if "zig" in os.path.basename(args.lib).lower() else "C(ABI stand-in for Zig)"

    def best_of(fn):
        best = 1e300
        for _ in range(args.repeats):
            t0 = time.perf_counter()
            fn()
            best = min(best, time.perf_counter() - t0)
        return best

    # (a) end-to-end: rebuild Python lists + marshal to ctypes each call — the NAIVE per-call FFI port
    py_e2e = best_of(lambda: python_kernel(*[list(a) for a in base_arrays], args.rho))
    nat_e2e = best_of(lambda: native_kernel(args.lib, *[list(a) for a in base_arrays], args.rho))

    # (b) compute-only: marshal ONCE into native buffers, time just the kernel call — the CEILING you
    #     only reach if SIFTA keeps the hot field in shared native buffers (not Python lists per tick)
    lib = ctypes.CDLL(args.lib)
    lib.sifta_pheromone_kernel.restype = ctypes.c_double
    lib.sifta_pheromone_kernel.argtypes = [ctypes.POINTER(ctypes.c_double)] * 5 + [
        ctypes.c_double, ctypes.c_size_t, ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
    Arr = ctypes.c_double * args.n
    cs, cr, ct, cb, cta = (Arr(*base_arrays[0]), Arr(*base_arrays[1]), Arr(*base_arrays[2]),
                           Arr(*base_arrays[3]), Arr(*base_arrays[4]))
    osum, omin = ctypes.c_double(0.0), ctypes.c_double(0.0)
    nat_compute = best_of(lambda: lib.sifta_pheromone_kernel(
        cs, cr, ct, cb, cta, ctypes.c_double(args.rho), args.n, ctypes.byref(osum), ctypes.byref(omin)))
    py_lists = [list(a) for a in base_arrays]
    py_compute = best_of(lambda: python_kernel(*py_lists, args.rho))

    print(f"\nN={args.n:,}  repeats={args.repeats}  (best-of)")
    print("(a) NAIVE per-call FFI port — rebuild+marshal every tick:")
    print(f"    pure Python            : {py_e2e*1000:8.2f} ms")
    print(f"    {lib_kind:<22} : {nat_e2e*1000:8.2f} ms   speedup {py_e2e/nat_e2e:5.2f}x")
    print("(b) COMPUTE-ONLY — data already in native buffers (the ceiling):")
    print(f"    pure Python            : {py_compute*1000:8.2f} ms")
    print(f"    {lib_kind:<22} : {nat_compute*1000:8.2f} ms   speedup {py_compute/nat_compute:5.2f}x")

    e2e_x = py_e2e / nat_e2e if nat_e2e else float("inf")
    print(f"\nVERDICT (acceptance threshold {ACCEPT_X:.0f}x):")
    if e2e_x >= ACCEPT_X:
        print(f"  - As a drop-in per-tick kernel it clears {ACCEPT_X:.0f}x ({e2e_x:.2f}x) — adopt Zig here.")
    else:
        print(f"  - As a drop-in per-tick kernel it is {e2e_x:.2f}x — marshalling eats the win; do NOT")
        print("    port naively (Delta=0).")
        print(f"  - Compute-only ceiling is {py_compute/nat_compute:.1f}x. Zig is ONLY worth it here if SIFTA")
        print("    keeps the hot field in a SHARED native buffer across ticks (no per-tick Python<->C copy).")
    print("NOTE: this is the C ABI stand-in; rerun on the Mac with the Zig .dylib for the true Zig number,")
    print("      and rerun (b) backed by numpy/mmap buffers to model a real shared-buffer organ.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
