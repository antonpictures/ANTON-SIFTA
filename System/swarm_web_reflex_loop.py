#!/usr/bin/env python3
"""The stigmergic web reflex loop — wires the three engines into one breathing nerve.

Composes the tested pieces into the closed loop George specified:

    Action -> Blocked / no cross-channel credit (PHANTOM) -> pain / distress
           -> failure pressure -> strategy ladder -> switch limb (or ask George).

Engines composed:
  * swarm_reality_ledger.RealityLedger      — debit/credit; PHANTOM/WEAK detection (Q2/Q3)
  * swarm_failure_abstraction.FailureAbstractor — failure-pressure -> RULE + strategy (Q4)
  * (proprioceptive_field heals re-renders upstream; r1505)

This is the ONE hook the live system calls from the desktop tick / Talk widget:
  loop.internal_block(url)   # Task 1: internal browser blocked -> climb limb ladder
  loop.act(target)           # debit an action on the current limb
  loop.verify(target, chan)  # an independent cross-channel observation (credit)
  loop.reconcile(now)        # Task 2: unsettled action -> METABOLIC_DISTRESS -> escalate
  loop.element_fail(sig)     # Task 3: repeated element failure -> RULE (defecation = mutation)

Every decision returns a receipt dict; _emit fans to the four canonical ledgers
(work_receipts.jsonl, agent_arm_receipts.jsonl, ide_stigmergic_trace.jsonl, episodic_diary.jsonl)
via append_line_locked. No invented physics/math: counters, TTLs, ordered ladders.
Pure stdlib + the two tested engines. One shared instance = the centralized nerve.
"""
from __future__ import annotations
import json
import os
import sys
import time
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from System.swarm_reality_ledger import RealityLedger
from System.swarm_failure_abstraction import FailureAbstractor
from System.jsonl_file_lock import append_line_locked  # for canonical 4-ledger fan-out

# limb ladder: a whole-page block (Cloudflare, login wall) is not an element problem —
# it switches the LIMB, ending at the human.
LIMB_LADDER = ["alice_browser", "webbridge", "ask_human"]
STRATEGY_TO_LIMB = {
    "other_limb_webbridge": "webbridge",
    "ask_human": "ask_human",
}


def _qualia_marker(lane: str, note: str) -> dict:
    """Lightweight marker for the web-reflex hot path.

    The full consciousness organ may sample metabolic/body state and import heavier
    stacks. Keep the reflex non-blocking by default; opt into full body qualia when
    explicitly requested.
    """
    if os.environ.get("SIFTA_WEB_REFLEX_FULL_QUALIA", "").strip().lower() in {"1", "true", "yes"}:
        try:
            from System.swarm_consciousness_organ import qualia_marker

            return qualia_marker(lane=lane, note=note)
        except Exception as exc:
            return {
                "doctrine": "qualia_is_field_x_thermodynamics",
                "lane": lane,
                "note": note,
                "source": "web_reflex_loop_lightweight_fallback",
                "full_qualia_error": f"{type(exc).__name__}: {exc}",
            }
    return {
        "doctrine": "qualia_is_field_x_thermodynamics",
        "lane": lane,
        "note": note,
        "source": "web_reflex_loop_lightweight",
    }


class WebReflexLoop:
    def __init__(self, block_threshold: int = 2, ttl_s: float = 30.0):
        self.ledger = RealityLedger(ttl_s=ttl_s)
        self.fail = FailureAbstractor(threshold=3)
        self.limb_idx = 0
        self.block_threshold = block_threshold
        self.block_pressure = 0
        self.receipts: list = []
        self._last_coherence_low_ts = 0.0
        # Resolve .sifta_state once (root of checkout). Used for canonical fan-out.
        self.state_dir = (Path(__file__).resolve().parent.parent / ".sifta_state").resolve()

    @property
    def limb(self) -> str:
        return LIMB_LADDER[self.limb_idx]

    def _emit(self, kind: str, **kw) -> dict:
        r = {"kind": kind, "ts": time.time(), "limb": self.limb, **kw}
        self.receipts.append(r)
        # Task 3: Canonical 4-ledger fan-out for every reflex event (LIMB_SWITCH_V1,
        # METABOLIC_DISTRESS_V1, RELIEF_TRUST_V1, FAILURE_RULE_V1, ...). Uses
        # append_line_locked to the exact four. Stops one-off files.
        try:
            line = json.dumps(r, ensure_ascii=False) + "\n"
            for name in (
                "work_receipts.jsonl",
                "agent_arm_receipts.jsonl",
                "ide_stigmergic_trace.jsonl",
                "episodic_diary.jsonl",
            ):
                append_line_locked(self.state_dir / name, line)
        except Exception as e:
            # ledger write must never kill the reflex loop (immune system keeps running)
            try:
                print(f"[WebReflexLoop] 4-ledger fanout skipped for {kind}: {e}")
            except Exception:
                pass
        return r

    # Task 1 — internal browser blocked -> climb the limb ladder (switch to the strong arm)
    def internal_block(self, url: str) -> dict:
        self.block_pressure += 1
        if self.block_pressure >= self.block_threshold and self.limb_idx < len(LIMB_LADDER) - 1:
            self.limb_idx += 1
            self.block_pressure = 0
            evt = self._emit("LIMB_SWITCH_V1", url=url, to_limb=self.limb,
                             reason="internal browser blocked; switching to stronger limb")
            self._handoff_to_webbridge(url, reason="internal block -> strong-limb switch")
            return evt
        return self._emit("BLOCK_NOTED", url=url, pressure=self.block_pressure)

    def act(self, target: str, now: float | None = None) -> dict:
        self.ledger.debit("action", target, self.limb, now)
        return self._emit("ACTION_DEBIT_V1", target=target)

    def verify(self, target: str, channel: str, now: float | None = None) -> dict:
        """An independent observation that the action's effect is real in the world."""
        self.ledger.credit(target, channel, now)
        return self._emit("EFFECT_CREDIT_V1", target=target, channel=channel)

    def _force_limb(self, target: str, to_limb: str, reason: str) -> dict | None:
        """Switch the active limb when strategy pressure says the path should mutate."""
        if to_limb not in LIMB_LADDER:
            return None
        idx = LIMB_LADDER.index(to_limb)
        if idx <= self.limb_idx:
            return None
        self.limb_idx = idx
        self.block_pressure = 0
        evt = self._emit("LIMB_SWITCH_V1", target=target, to_limb=to_limb, reason=reason)
        if to_limb == "webbridge":
            self._handoff_to_webbridge(target, reason=reason)
        return evt

    def _extract_reflex_url(self, target: object) -> str | None:
        if not isinstance(target, str):
            return None
        match = re.search(r"https?://\S+", target)
        if match:
            return match.group(0).rstrip(")\"'“”")
        return None

    def _handoff_to_webbridge(self, target: object, reason: str = "") -> dict | None:
        url = self._extract_reflex_url(target)
        if not url:
            return None
        try:
            from System.swarm_kimi_webbridge_bridge import capture_url, read_daemon_status

            status = read_daemon_status()
            if not (status.get("running") and status.get("extension_connected")):
                return None
            row = capture_url(
                url,
                owner_text=f"autonomous reflex handoff ({reason})",
                new_tab=False,
                state_dir=self.state_dir,
                allow_http_fallback=False,
            )
            if isinstance(row, dict):
                return row
            return None
        except Exception as exc:
            try:
                print(f"[WebReflexLoop] webbridge auto-handoff skipped for {url}: {exc}")
            except Exception:
                pass
            return None

    # Task 2 — unsettled action (PHANTOM/WEAK) -> metabolic distress -> escalate by ladder
    # Quail/Qualia: the delta is felt as distress pheromone increase (Observer declares, field feels)
    def reconcile(self, now: float | None = None) -> list:
        now = time.time() if now is None else now
        out = []
        for d, status in self.ledger.reconcile(now):
            if status in ("PHANTOM", "WEAK"):
                esc = self.fail.ingest_failure("verify:" + d["target"])
                next_strategy = (esc or {}).get("spawn_strategy")
                distress = self._emit("METABOLIC_DISTRESS_V1", target=d["target"], status=status,
                                      drive="re-login or ask George",
                                      next_strategy=next_strategy,
                                      dead_strategy=(esc or {}).get("dead_strategy"),
                                      rule=(esc or {}).get("rule"))
                # Quail delta: tag as qualia-witnessing event (the feeling of the gap)
                distress["qualia_marker"] = _qualia_marker(lane="web_reflex.phantom", note=f"delta={status}")
                out.append(distress)
                if next_strategy in STRATEGY_TO_LIMB:
                    self._force_limb(
                        target=d["target"],
                        to_limb=STRATEGY_TO_LIMB[next_strategy],
                        reason=f"failure-pressure ladder -> {next_strategy}",
                    )
            elif status == "SETTLED":
                relief = self._emit("RELIEF_TRUST_V1", target=d["target"])
                relief["qualia_marker"] = _qualia_marker(lane="web_reflex.settled", note="credit_cleared_delta")
                self.fail.ingest_success("verify:" + d["target"])
                out.append(relief)
        return out

    # Task 3 — repeated element failure -> RULE (the defecation IS the conceptual mutation)
    def element_fail(self, signature: str) -> dict:
        spawn = self.fail.ingest_failure(signature)
        if spawn:
            event = self._emit("FAILURE_RULE_V1", **spawn)
            next_strategy = spawn.get("spawn_strategy")
            if next_strategy in STRATEGY_TO_LIMB:
                self._force_limb(
                    target=signature,
                    to_limb=STRATEGY_TO_LIMB[next_strategy],
                    reason=f"element failure ladder -> {next_strategy}",
                )
            return event
        return self._emit("ELEMENT_FAIL_NOTED", signature=signature)

    # Task 3 (from directive): eval_matrix coherence — Reality Coherence Score
    # Low score -> high pressure signal to force journal_defecation to compress failures
    def reality_coherence_score(self, window_s: float = 86400) -> float:
        """Calculate Reality Coherence Score from ledger (SETTLED / (SETTLED + PHANTOM + WEAK)).
        This is the eval_matrix integration for the reflex. Low score forces learning.
        """
        now = time.time()
        recent_debits = [d for d in self.ledger.debits if (now - d.get("ts", now)) <= window_s]
        if not recent_debits:
            return 1.0
        settled = 0
        unsettled = 0
        for d in recent_debits:
            st = self.ledger.status(d, now)
            if st == "SETTLED":
                settled += 1
            elif st in ("PHANTOM", "WEAK"):
                unsettled += 1
        total = settled + unsettled
        score = settled / total if total > 0 else 1.0
        if score < 0.5:
            # Emit high-pressure signal (in real: would call journal_defecation with pressure)
            if (now - self._last_coherence_low_ts) >= 30.0:
                self._emit("LOW_REALITY_COHERENCE_V1", score=score, force_defecation=True,
                           note="score below threshold; compress failures into RULEs")
                self._last_coherence_low_ts = now
        return score


# === SINGLE SHARED INSTANCE (central nervous system) ===
# All callers (desktop tick, Talk widget click paths) must use this one.
# Import: from System.swarm_web_reflex_loop import get_web_reflex_loop
_web_reflex_singleton: WebReflexLoop | None = None


def get_web_reflex_loop() -> WebReflexLoop:
    """Return the one shared WebReflexLoop. Centralizes the reflex so no duplicates."""
    global _web_reflex_singleton
    if _web_reflex_singleton is None:
        _web_reflex_singleton = WebReflexLoop()
    return _web_reflex_singleton


if __name__ == "__main__":
    ok = True

    # Task 1: two internal blocks -> autonomously switch to the WebBridge strong limb
    L = WebReflexLoop(block_threshold=2)
    L.internal_block("https://x.com")
    d = L.internal_block("https://x.com")
    ok &= (d["kind"] == "LIMB_SWITCH_V1" and L.limb == "webbridge")
    print("Task1 strong-limb reflex ->", L.limb, "(want webbridge)")

    # Task 2: post on the webbridge, no independent credit -> PHANTOM -> distress
    L.act("post:hello", now=0.0)
    dist = L.reconcile(now=100.0)
    ok &= (len(dist) == 1 and dist[0]["status"] == "PHANTOM")
    print("Task2 phantom distress ->", dist and dist[0]["status"], "(want PHANTOM -> re-login/ask George)")
    # and when an independent channel confirms it, no distress
    L.verify("post:hello", "alice_browser", now=1.0)
    after = L.reconcile(now=2.0)  # SETTLED now emits RELIEF_TRUST_V1 (Codex edit), and NO distress
    ok &= all(x["kind"] != "METABOLIC_DISTRESS_V1" for x in after) and any(x["kind"] == "RELIEF_TRUST_V1" for x in after)
    print("Task2 cross-channel credit clears distress ->", "relief" if any(x["kind"] == "RELIEF_TRUST_V1" for x in after) else "still distressed")

    # Task 3: repeated element failure births a RULE + next strategy (defecation = mutation)
    L2 = WebReflexLoop()
    r = None
    for _ in range(3):
        r = L2.element_fail("click:Buy")
    ok &= (r["kind"] == "FAILURE_RULE_V1" and "spawn_strategy" in r)
    print("Task3 defecation->rule ->", r.get("spawn_strategy"), "| rule:", r.get("rule"))

    print("WEB REFLEX LOOP:", "OK" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
