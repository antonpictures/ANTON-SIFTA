#!/usr/bin/env python3
"""Proprioceptive field — body parts are SIGNATURES, UIDs are this heartbeat's pins.

The problem (George Q1): UID proprioception ("click e27") breaks when the page
re-renders (React, shadow-DOM swap, dynamic iframe). The limb changes shape and
the old UID points at nothing or the wrong thing.

The SIFTA answer (no central governor): do not give a body part a permanent UID.
Give it a re-render-invariant SIGNATURE — role + accessible name + semantic
role-path from a landmark + coarse zone + function (href/field-name). The UID is
re-issued every scan and BOUND to the signature for a short half-life. The cortex
plans against the signature; the executor maps signature -> current UID at act
time. When the dress shifts:

  * a fresh scan re-binds the same signature to whatever UID now realizes it
    (the limb moved address; its identity survived) — re-orientation, no reset;
  * a binding older than its half-life DECAYS and is auto-forgotten, so she never
    acts on a stale limb-map (stigmergic self-correction, not a governor);
  * an executed action whose effect does not verify writes a PROPRIOCEPTIVE
    MISMATCH ("pain") that RAISES re-scan pressure — the more pain, the harder
    she re-scans, until the signature re-binds.

This module is the pure-Python mechanism (deterministic, tested). The live-DOM
half (deep shadow-piercing scan + a MutationObserver "nerve" that fires on
subtree change) feeds observe()/feel_mismatch(); canvas-only and cross-origin
iframes have no DOM nerves and fall back to the vision body (out of scope here,
named in the receipt). No invented physics: decay is a time-to-live threshold,
pressure is a count plus a staleness ratio.
"""
from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field


def signature(role: str, name: str, zone: str = "", func: str = "", path: str = "") -> str:
    """Re-render-invariant body-part id. Lowercased, whitespace-collapsed."""
    def n(s):
        return " ".join(str(s or "").lower().split())
    return "|".join((n(role), n(name), n(zone), n(func), n(path)))


@dataclass
class ProprioceptiveField:
    half_life_s: float = 8.0
    _bind: dict = field(default_factory=dict)      # signature -> (uid, bound_ts)
    _pain: Counter = field(default_factory=Counter)  # signature -> mismatch count

    def observe(self, scan, now: float | None = None) -> int:
        """Ingest one fresh scan: list of {'sig':..., 'uid':...}. Re-binds by signature."""
        now = time.time() if now is None else now
        n = 0
        for el in scan or []:
            sig = el.get("sig") or signature(el.get("role", ""), el.get("name", ""),
                                              el.get("zone", ""), el.get("func", ""), el.get("path", ""))
            uid = str(el.get("uid") or "")
            if sig and uid:
                self._bind[sig] = (uid, now)
                n += 1
        return n

    def resolve(self, sig: str, now: float | None = None):
        """Current UID for a body-part signature, or None if unbound/decayed (-> re-scan)."""
        now = time.time() if now is None else now
        b = self._bind.get(sig)
        if not b:
            return None
        uid, ts = b
        if now - ts > self.half_life_s:   # binding decayed: stale limb-map, must re-scan
            return None
        return uid

    def feel_mismatch(self, sig: str) -> None:
        """Pain: an action did not verify, or the aimed signature is gone."""
        self._pain[sig] += 1

    def rescan_pressure(self, now: float | None = None) -> float:
        """Drives the perception swimmer. pain_total + fraction of bindings gone stale."""
        now = time.time() if now is None else now
        if not self._bind:
            stale_ratio = 1.0
        else:
            stale = sum(1 for (_u, ts) in self._bind.values() if now - ts > self.half_life_s)
            stale_ratio = stale / len(self._bind)
        return float(sum(self._pain.values())) + stale_ratio


if __name__ == "__main__":
    f = ProprioceptiveField(half_life_s=8.0)
    SIG = signature("link", "Pricing", "header", "/pricing")
    ok = True

    # 1. first scan binds the Pricing link to e27
    f.observe([{"sig": SIG, "uid": "e27"}], now=0.0)
    r1 = f.resolve(SIG, now=1.0)
    ok &= (r1 == "e27"); print("bind ->", r1, "(want e27)")

    # 2. React re-render: SAME body part, NEW uid e9. A fresh scan re-binds by signature.
    f.observe([{"sig": SIG, "uid": "e9"}], now=2.0)
    r2 = f.resolve(SIG, now=3.0)
    ok &= (r2 == "e9"); print("re-render re-bind ->", r2, "(want e9 — limb moved address, identity survived)")

    # 3. decay: no scan for > half_life -> stale -> None (she must re-scan, not act blind)
    r3 = f.resolve(SIG, now=2.0 + 8.0 + 1.0)
    ok &= (r3 is None); print("decayed ->", r3, "(want None — stale proprioception forgotten, no governor)")

    # 4. pain raises re-scan pressure
    p0 = f.rescan_pressure(now=3.0)
    f.feel_mismatch(SIG); f.feel_mismatch(SIG)
    p1 = f.rescan_pressure(now=3.0)
    ok &= (p1 > p0); print(f"pain pressure {p0:.2f} -> {p1:.2f} (want rise)")

    print("PROPRIOCEPTIVE FIELD:", "OK" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
