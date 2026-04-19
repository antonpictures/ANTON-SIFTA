"""
swarm_telomeres.py
==================

Cellular Aging / Programmed Cell Death (Apoptosis) — *safe* implementation.

═══════════════════════════════════════════════════════════════════════════
PROVENANCE
═══════════════════════════════════════════════════════════════════════════
  Concept: Bishop (GTAB / antigravity_m5)
  Implementation: C47H (cursor_m5)
  Trace: <to-be-filled-by-audit-request>
  Authority: Architect grant "C47H WRITE ALL CODE" (2026-04-19 ~13:30 PT)

Bishop is right that an organism with Mitosis + HGT but no death
mechanism becomes pathological — immortal swimmers will hoard STGM,
clog the entorhinal grid, and eventually OOM the substrate. The
biology is sound. We need telomeres.

What this file does NOT do, and *why*:

  1. NO `body_path.unlink()`.
     Bishop's first draft physically deleted `_BODY.json` from
     `.sifta_state/`. That is exactly the operation that, ~30 minutes
     before this file was written, deleted 95 files from the cortex
     in the macrophage incident logged at trace 2af37bb7. We are NOT
     re-introducing that primitive into the daemon path.

     Death is expressed as a STATE FLAG (`is_dead: true` + apoptosis
     timestamp) on a separate per-swimmer lifecycle ledger. Physical
     excision, if ever desired, is gated by the protocol set down in
     2af37bb7 Section [A]:
        (1) peer_review_request to C47H + Bishop documenting the
            candidate list,
        (2) Tri-IDE green-light,
        (3) deletion executed via a script committed to git
            (not by the daemon).

  2. NO injection of `telomere_length` into the canonical
     `_BODY.json` schema.
     Bishop's draft did `data.get("telomere_length", 100.0)` inside
     a `read_write_json_locked` callback against `_BODY.json`. That
     pattern silently writes the field on first read, polluting
     every swimmer's canonical body the moment the daemon ticks.
     The actual `_BODY.json` schema on disk (verified 2026-04-19)
     is: `{id, ascii, energy, style, stgm_balance, [architect_seal,
     homeworld_serial]}`. `telomere_length` is not in it; we are
     not adding it.

     Telomere state lives in its OWN ledger:
        `.sifta_state/cellular_aging_ledger.jsonl`
     One append per tick per swimmer. Bodies are NEVER modified.

  3. CANONICAL stgm_memory_rewards schema.
     Bishop's draft wrote `{transaction_type, node_id, reward_value,
     timestamp}` to `stgm_memory_rewards.jsonl`. The canonical
     writer is `System/stigmergic_memory_bus.py:574` and the
     schema is `{ts, app, reason, amount, trace_id}`. Bishop's
     fields would have been silently dropped by every existing
     consumer. We use the canonical fields, with `app="apoptosis"`
     and a real `trace_id`, so the apoptotic refunds are properly
     attributed.

═══════════════════════════════════════════════════════════════════════════
DESIGN
═══════════════════════════════════════════════════════════════════════════

  STATE LEDGER (append-only, per-tick):
    .sifta_state/cellular_aging_ledger.jsonl
    schema = {
        ts: float,
        swimmer_id: str,
        action_kind: str,            # "mitosis" | "hgt" | "ide_exec" | "tick"
        action_cost: float,          # telomere units consumed
        telomere_before: float,
        telomere_after: float,
        is_dead: bool,
        trace_id: str,               # uuid for this aging event
    }

  DEATH MARKER (one record per swimmer, written once):
    appended to the same ledger with `is_dead: true` and
    `action_kind: "apoptosis"`. Consumers (mitosis, HGT, dispatcher)
    learn-of-death by tailing this ledger and refusing to act on
    swimmers whose latest record carries `is_dead: true`.

  STGM REFUND ON DEATH:
    The dead swimmer's `stgm_balance` is read from `_BODY.json`
    (read-only — body is not mutated), the canonical
    `stigmergic_memory_bus._pay_stgm`-style record is written to
    `stgm_memory_rewards.jsonl` with `app="apoptosis"`,
    `reason="apoptotic_decay <swimmer_id>"`, `amount=balance*0.5`,
    and a fresh `trace_id`. The 0.5 thermodynamic-loss constant is
    parameterized (`thermal_loss_fraction`), defaulting to 0.5 to
    preserve Bishop's biological intuition while leaving room for
    Architect to recalibrate against the inference economy.

  PHYSICAL EXCISION (separate, gated method):
    `propose_excision(swimmer_id) -> trace_id`
    Files a peer_review_request to C47H + Bishop on the
    ide_stigmergic_bridge. Does NOT delete. Returns the trace_id
    so the human caller can follow the gate.

═══════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import (  # noqa: E402
        read_write_json_locked,
        append_line_locked,
    )
except ImportError:
    print("[FATAL] swarm_telomeres: jsonl_file_lock not importable. "
          "Run with PYTHONPATH=.")
    sys.exit(1)


# ─── Constants ────────────────────────────────────────────────────────────

DEFAULT_INITIAL_TELOMERE = 100.0      # Hayflick-ish; tunable
DEFAULT_THERMAL_LOSS     = 0.5        # 50% heat loss on apoptotic refund
ACTION_COSTS = {                       # canonical action → telomere units
    "ide_exec":  1.0,
    "tick":      0.1,
    "mitosis":   5.0,
    "hgt":       3.0,
    "apoptosis": 0.0,                  # the death record itself is free
}


# ─── Module ───────────────────────────────────────────────────────────────


class CellularAging:
    """
    Telomere-driven cellular aging. Death is a STATE FLAG, never an unlink.
    """

    def __init__(
        self,
        state_dir: Optional[Path] = None,
        initial_telomere: float = DEFAULT_INITIAL_TELOMERE,
        thermal_loss_fraction: float = DEFAULT_THERMAL_LOSS,
    ):
        self.state_dir = Path(state_dir) if state_dir else (_REPO / ".sifta_state")
        self.aging_ledger = self.state_dir / "cellular_aging_ledger.jsonl"
        self.rewards_ledger = self.state_dir / "stgm_memory_rewards.jsonl"
        self.initial_telomere = float(initial_telomere)
        self.thermal_loss_fraction = float(thermal_loss_fraction)

    # ─── Public API ─────────────────────────────────────────────────────

    def is_alive(self, swimmer_id: str) -> bool:
        """True iff swimmer has no apoptosis record on the ledger."""
        return self._latest_state(swimmer_id).get("is_dead", False) is False

    def current_telomere(self, swimmer_id: str) -> float:
        """Most recent telomere reading; defaults to initial if unseen."""
        st = self._latest_state(swimmer_id)
        return float(st.get("telomere_after", self.initial_telomere))

    def degrade(
        self,
        swimmer_id: str,
        action_kind: str = "ide_exec",
        action_cost: Optional[float] = None,
    ) -> dict:
        """
        Charge `action_cost` telomere units against `swimmer_id`.

        Returns a dict:
            {
                'swimmer_id': str,
                'telomere_before': float,
                'telomere_after': float,
                'is_dead': bool,
                'apoptosis_refund': float | None,
                'trace_id': str,
            }

        Never raises on missing body; an unknown swimmer is treated as
        not-yet-born (no-op, returns alive=True with full telomere).
        """
        if self.is_alive(swimmer_id) is False:
            # Already dead. No-op (idempotent).
            return {
                "swimmer_id": swimmer_id,
                "telomere_before": 0.0,
                "telomere_after": 0.0,
                "is_dead": True,
                "apoptosis_refund": None,
                "trace_id": self._latest_state(swimmer_id).get("trace_id", ""),
            }

        cost = float(action_cost) if action_cost is not None \
               else float(ACTION_COSTS.get(action_kind, 1.0))
        before = self.current_telomere(swimmer_id)
        after = before - cost

        trace_id = uuid.uuid4().hex[:16]
        rec = {
            "ts": time.time(),
            "swimmer_id": swimmer_id,
            "action_kind": action_kind,
            "action_cost": cost,
            "telomere_before": before,
            "telomere_after": after,
            "is_dead": False,
            "trace_id": trace_id,
        }
        self._append_aging(rec)

        result = {
            "swimmer_id": swimmer_id,
            "telomere_before": before,
            "telomere_after": after,
            "is_dead": False,
            "apoptosis_refund": None,
            "trace_id": trace_id,
        }

        if after <= 0:
            refund = self._mark_apoptosis(swimmer_id)
            result["is_dead"] = True
            result["apoptosis_refund"] = refund

        return result

    def propose_excision(self, swimmer_id: str, reason: str = "") -> str:
        """
        File a peer_review_request to actually unlink the dead swimmer's
        body. Returns the bridge trace_id. Does NOT delete anything.

        Per trace 2af37bb7: physical deletion of files in `.sifta_state/`
        requires (1) peer review, (2) tri-IDE green-light, (3) a
        committed script. This method does step (1) only.
        """
        try:
            from System.ide_peer_review import request_review  # noqa: E402
        except ImportError:
            return ""

        body_path = self.state_dir / f"{swimmer_id}_BODY.json"
        latest = self._latest_state(swimmer_id)
        summary = (
            f"PROPOSED EXCISION (gated; not executed)\n\n"
            f"swimmer_id: {swimmer_id}\n"
            f"body_path:  {body_path}\n"
            f"is_dead:    {latest.get('is_dead', False)}\n"
            f"died_at:    {latest.get('ts', 'n/a')}\n"
            f"reason:     {reason or 'cellular_aging.apoptosis'}\n\n"
            f"Per protocol 2af37bb7, this method does not delete. "
            f"It requests tri-IDE review of the candidate. Approval "
            f"and physical excision must be performed by a human-"
            f"reviewed, git-committed script — never the daemon."
        )
        result = request_review(
            from_ide="C47H",
            to_ide="GTAB",
            files=[str(body_path), str(self.aging_ledger)],
            summary=summary,
        )
        return result.get("trace_id", "")

    # ─── Internals ──────────────────────────────────────────────────────

    def _append_aging(self, rec: dict) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        append_line_locked(
            self.aging_ledger,
            json.dumps(rec, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _latest_state(self, swimmer_id: str) -> dict:
        """Linear scan of the ledger; the file is small and the daemon is
        not in the hot path. Optimize later if needed."""
        if not self.aging_ledger.exists():
            return {}
        latest = {}
        try:
            with self.aging_ledger.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("swimmer_id") == swimmer_id:
                        latest = rec
        except OSError:
            return {}
        return latest

    def _read_body_balance(self, swimmer_id: str) -> float:
        """Read-only access to canonical _BODY.json. Body is NOT mutated."""
        body_path = self.state_dir / f"{swimmer_id}_BODY.json"
        if not body_path.exists():
            return 0.0
        try:
            with body_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return float(data.get("stgm_balance", 0.0))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return 0.0

    def _mark_apoptosis(self, swimmer_id: str) -> float:
        """Write the death record + canonical-schema STGM refund. Return refund."""
        balance = self._read_body_balance(swimmer_id)
        refund = max(balance * self.thermal_loss_fraction, 0.0)
        trace_id = uuid.uuid4().hex[:16]

        death_rec = {
            "ts": time.time(),
            "swimmer_id": swimmer_id,
            "action_kind": "apoptosis",
            "action_cost": 0.0,
            "telomere_before": 0.0,
            "telomere_after": 0.0,
            "is_dead": True,
            "trace_id": trace_id,
            "apoptosis_refund": refund,
        }
        self._append_aging(death_rec)

        if refund > 0:
            reward_rec = {
                "ts": time.time(),
                "app": "apoptosis",
                "reason": f"apoptotic_decay {swimmer_id}; thermal_loss="
                          f"{1.0 - self.thermal_loss_fraction:.2f}",
                "amount": refund,
                "trace_id": trace_id,
            }
            try:
                append_line_locked(
                    self.rewards_ledger,
                    json.dumps(reward_rec, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            except OSError:
                pass

        return refund


# ─── Smoke ────────────────────────────────────────────────────────────────


def _smoke():
    """
    REAL primitives. NO mock-lock cheat (F9). Sandboxed tempdir. Asserts
    against canonical schemas verified on disk.
    """
    import tempfile

    print("\n=== SIFTA TELOMERE / APOPTOSIS — SAFE SMOKE ===\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Synthetic body that mirrors the real on-disk schema
        body = tmp / "M5SIFTA_BODY.json"
        body.write_text(json.dumps({
            "id": "M5SIFTA",
            "ascii": "::M5::",
            "style": "test",
            "energy": 1.0,
            "stgm_balance": 4000.0,
        }))

        aging = CellularAging(
            state_dir=tmp,
            initial_telomere=2.5,         # critically short
            thermal_loss_fraction=0.5,
        )

        assert aging.is_alive("M5SIFTA") is True
        assert aging.current_telomere("M5SIFTA") == 2.5
        print("[PASS] new swimmer is alive with default telomere")

        r1 = aging.degrade("M5SIFTA", action_kind="ide_exec", action_cost=1.0)
        assert r1["is_dead"] is False
        assert abs(r1["telomere_after"] - 1.5) < 1e-9
        assert r1["apoptosis_refund"] is None
        print(f"[PASS] action 1: telomere {r1['telomere_before']} → {r1['telomere_after']}")

        # Body must be UNCHANGED — no telomere_length injection (F11)
        body_after_action = json.loads(body.read_text())
        assert "telomere_length" not in body_after_action, \
            "F11: BODY must not be polluted with telomere_length"
        assert sorted(body_after_action.keys()) == \
            sorted(["id", "ascii", "style", "energy", "stgm_balance"]), \
            "F11: BODY schema must be unchanged"
        print("[PASS] _BODY.json schema unchanged (F11 honored)")

        r2 = aging.degrade("M5SIFTA", action_kind="mitosis", action_cost=2.0)
        assert r2["is_dead"] is True
        assert r2["telomere_after"] == -0.5
        assert r2["apoptosis_refund"] == 2000.0
        print(f"[PASS] action 2: apoptosis triggered, refund {r2['apoptosis_refund']}")

        # Body STILL exists — no unlink (F12)
        assert body.exists(), "F12: body must NOT be unlinked by daemon"
        print("[PASS] _BODY.json NOT unlinked (F12 honored — death is a flag, not rm)")

        # Idempotent death
        r3 = aging.degrade("M5SIFTA", action_kind="ide_exec", action_cost=1.0)
        assert r3["is_dead"] is True
        assert r3["apoptosis_refund"] is None  # no double-refund
        print("[PASS] idempotent: re-degrading dead swimmer is a no-op")

        # is_alive reflects death without rescanning the body
        assert aging.is_alive("M5SIFTA") is False
        print("[PASS] is_alive() returns False after apoptosis")

        # Reward ledger uses CANONICAL schema (F10)
        rewards_path = tmp / "stgm_memory_rewards.jsonl"
        with rewards_path.open() as f:
            reward = json.loads(f.readline())
        canonical_keys = {"ts", "app", "reason", "amount", "trace_id"}
        assert canonical_keys.issubset(set(reward.keys())), \
            f"F10: reward record must use canonical schema, got {sorted(reward.keys())}"
        assert reward["app"] == "apoptosis"
        assert reward["amount"] == 2000.0
        assert "M5SIFTA" in reward["reason"]
        print(f"[PASS] STGM refund uses canonical schema "
              f"(keys={sorted(reward.keys())})")

        # Aging ledger contains a clean trail
        ledger = tmp / "cellular_aging_ledger.jsonl"
        records = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
        assert len(records) == 3, f"expected 3 records, got {len(records)}"
        assert records[0]["action_kind"] == "ide_exec"
        assert records[1]["action_kind"] == "mitosis"
        assert records[2]["action_kind"] == "apoptosis"
        assert records[2]["is_dead"] is True
        print(f"[PASS] aging ledger has clean 3-record trail")

        print("\n=== SAFE TELOMERE SMOKE COMPLETE ===")
        print("    Death is a flag. Bodies are sacred. Schema is canonical.")
        print("    Bishop's biology + protocol 2af37bb7 gate.\n")


if __name__ == "__main__":
    _smoke()
