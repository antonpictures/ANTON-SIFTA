#!/usr/bin/env python3
"""Double-entry bookkeeping for reality (Q2 trace-erasure + Q3 poisoned receipts).

George's two questions are the same accounting problem:

  Q2 — the web wipes its own traces (session expires, cookies purged, SPA wipes DOM).
  Q3 — the web LIES (fake "logged in", shadow-ban, honeypot): the local receipt says
       "I posted" but the world did not receive it.

Answer: a local action/intent is a DEBIT. An independent observation of the EXPECTED
external state is a CREDIT. A claim is SETTLED only when a debit is matched by a credit
**from a different channel** within a TTL.

  * no credit before TTL          -> PHANTOM  (Q3 poison / Q2 session erased: the world
                                               did not reflect the action -> re-act)
  * credit only from the SAME channel that acted -> WEAK (the possibly-lying site
                                               verifying itself; needs an independent eye)
  * credit from an independent channel -> SETTLED

Sovereignty is the key to Q2: the website can erase ITS cookies/DOM, but it cannot erase
Alice's local debits. Her INTENT persists in her own ledger; an intent with no fresh
credit goes PHANTOM and drives re-login. The world is hostile and ephemeral; her body
ledger is not.

No invented physics/math: a TTL threshold + set matching. Pure stdlib.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field


@dataclass
class RealityLedger:
    ttl_s: float = 30.0
    debits: list = field(default_factory=list)    # {kind, target, channel, ts}
    credits: list = field(default_factory=list)   # {target, channel, ts}

    def debit(self, kind: str, target: str, channel: str, ts: float | None = None):
        """kind: 'intent' (Q2, e.g. be logged into github) or 'action' (Q3, e.g. posted)."""
        self.debits.append({"kind": kind, "target": target, "channel": channel,
                            "ts": time.time() if ts is None else ts})

    def credit(self, target: str, channel: str, ts: float | None = None):
        """An independent observation that the expected external state IS present."""
        self.credits.append({"target": target, "channel": channel,
                             "ts": time.time() if ts is None else ts})

    def status(self, d: dict, now: float) -> str:
        if d["kind"] == "intent":
            # an ongoing state (e.g. a session) must be re-confirmed FRESH against now;
            # a stale confirmation = the world erased it -> PHANTOM -> re-act (re-login).
            cs = [c for c in self.credits
                  if c["target"] == d["target"] and 0.0 <= (now - c["ts"]) <= self.ttl_s]
            if not cs:
                return "PHANTOM"
            return "SETTLED" if any(c["channel"] != d["channel"] for c in cs) else "WEAK"
        # an action's effect appears shortly AFTER the action; once settled it stays settled.
        cs = [c for c in self.credits
              if c["target"] == d["target"] and 0.0 <= (c["ts"] - d["ts"]) <= self.ttl_s]
        if not cs:
            return "PENDING" if (now - d["ts"]) <= self.ttl_s else "PHANTOM"
        if any(c["channel"] != d["channel"] for c in cs):
            return "SETTLED"
        return "WEAK"

    def reconcile(self, now: float | None = None) -> list[tuple[dict, str]]:
        now = time.time() if now is None else now
        return [(d, self.status(d, now)) for d in self.debits]


if __name__ == "__main__":
    ok = True
    L = RealityLedger(ttl_s=30.0)
    # Q3 SETTLED: posted via webbridge, seen back via the independent alice_browser eye
    L.debit("action", "post:hello", "webbridge", ts=0.0)
    L.credit("post:hello", "alice_browser", ts=2.0)
    s = L.status(L.debits[-1], now=3.0); ok &= s == "SETTLED"; print("Q3 corroborated ->", s, "(want SETTLED)")
    # Q3 PHANTOM (poison): claimed a post, no independent reflection ever appears
    L2 = RealityLedger(ttl_s=30.0); L2.debit("action", "post:bye", "webbridge", ts=0.0)
    s = L2.status(L2.debits[-1], now=40.0); ok &= s == "PHANTOM"; print("Q3 honeypot/shadowban ->", s, "(want PHANTOM)")
    # Q3 WEAK: only the acting channel confirms itself (a liar verifying its own lie)
    L3 = RealityLedger(ttl_s=30.0); L3.debit("action", "post:x", "webbridge", ts=0.0)
    L3.credit("post:x", "webbridge", ts=1.0)
    s = L3.status(L3.debits[-1], now=2.0); ok &= s == "WEAK"; print("Q3 self-verify ->", s, "(want WEAK)")
    # Q2: intent to hold a session; confirmed once, then the site wipes it -> no fresh credit -> re-act
    L4 = RealityLedger(ttl_s=30.0); L4.debit("intent", "session:github", "alice", ts=0.0)
    L4.credit("session:github", "alice_browser", ts=1.0)
    ok &= L4.status(L4.debits[-1], now=2.0) == "SETTLED"
    s = L4.status(L4.debits[-1], now=100.0)  # session expired, no fresh credit within TTL
    ok &= s == "PHANTOM"; print("Q2 session erased, intent persists ->", s, "(want PHANTOM -> re-login)")
    print("REALITY LEDGER:", "OK" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
