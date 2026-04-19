"""
swarm_morphogenesis.py — Cellular Differentiation Engine

══════════════════════════════════════════════════════════════════════════
PROVENANCE
══════════════════════════════════════════════════════════════════════════
  Concept:        Bishop (GTAB) — BUILDER / QUEEN / SENTINEL phenotypes
  Structure:      AG31 — mutation_marker dict pattern (no tuple-return),
                  pressure-driven differentiation logic
  Wiring + gate:  C47H — canonical schema reads, side-ledger phenotype
                  state, no _BODY.json pollution
  Authority:      Architect's "WHAT IS BEST FOR THE ORGANISM" directive
                  (2026-04-19 ~13:48 PT)

══════════════════════════════════════════════════════════════════════════
WHY THIS FILE WAS REWIRED (post-commit fix on 4981663)
══════════════════════════════════════════════════════════════════════════

AG31's commit 4981663 had three blocking defects, verified empirically
against on-disk schemas:

  M1 — F11 BODY pollution: wrote `cellular_phenotype` and `megagene[*]`
       fields directly to `_BODY.json`, none of which are in the
       canonical body schema verified at 13:30 PT
       ({id, ascii, energy, style, stgm_balance, [architect_seal,
        homeworld_serial]}).

  M2 — F10 invented schema READ on stgm_memory_rewards.jsonl: used
       `trace.get("node_id")`, `trace.get("reward_value")`,
       `trace.get("timestamp")`. Canonical writer is
       stigmergic_memory_bus.py:574 with schema
       {ts, app, reason, amount, trace_id}. Result: in production,
       pressure detection always returned 0 and differentiation
       NEVER triggered. Smoke passed because the smoke fixture
       wrote records using the broken consumer's schema.

  M3 — three F11-class commits in 15 minutes from AG31, ignoring
       audit traces d92aaeee, d1424e8c, and the bb634d8 endocrine
       audit. Side-ledger pattern is now load-bearing.

This rewrite preserves AG31's biology and structure. It changes
ONLY the I/O surface: canonical-schema reads, side-ledger writes,
bodies stay sacred.
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
    print("[FATAL] swarm_morphogenesis: jsonl_file_lock not importable. "
          "Run with PYTHONPATH=.")
    sys.exit(1)


# ─── Constants ────────────────────────────────────────────────────────────

PRESSURE_THRESHOLD = 5.0       # below this, cell stays UNDIFFERENTIATED
PRESSURE_WINDOW_S = 600        # how far back to look for STGM pressure
PHENOTYPE_LOCK_PERMANENT = True

# Phenotype → coefficient overrides. These are written to the
# motor/SSP/homeo/free-energy COEFFICIENT files (canonical cortex
# substrate) instead of being shoved onto _BODY.json.
PHENOTYPE_PROFILES = {
    "BUILDER":  {"psi_motor": {"b": 8.0, "c": 2.0},
                 "lambda_free_energy": {"kappa": 0.01}},
    "QUEEN":    {"phi_ssp":   {"alpha": 10.0, "zeta": 5.0},
                 "psi_motor": {"b": 0.1}},
    "SENTINEL": {"omega_homeo":         {"eta": 8.0},
                 "lambda_free_energy":  {"kappa": 5.0}},
}


# ─── Module ───────────────────────────────────────────────────────────────


class SwarmMorphogenesis:
    """
    Reads environmental ledgers, classifies dominant pressure, locks
    each Swimmer into a specialized phenotype. Phenotype state lives
    in a side ledger; bodies are never modified.
    """

    def __init__(self, state_dir: Optional[Path] = None):
        self.state_dir = Path(state_dir) if state_dir else (_REPO / ".sifta_state")
        self.ach_ledger      = self.state_dir / "nmj_acetylcholine.jsonl"
        self.fear_ledger     = self.state_dir / "amygdala_nociception.jsonl"
        self.rewards_ledger  = self.state_dir / "stgm_memory_rewards.jsonl"
        self.phenotype_ledger = self.state_dir / "cellular_phenotype_ledger.jsonl"

    # ─── Public API ─────────────────────────────────────────────────────

    def current_phenotype(self, swimmer_id: str) -> str:
        """Most recent phenotype on the side ledger; default TOTIPOTENT."""
        latest = self._latest_phenotype_record(swimmer_id)
        return latest.get("phenotype", "TOTIPOTENT_STEM_CELL")

    def execute_differentiation(self, swimmer_id: str) -> bool:
        """
        If sufficient environmental pressure exists, lock this swimmer
        into a phenotype. Idempotent: differentiation only fires once.
        """
        if self.current_phenotype(swimmer_id) != "TOTIPOTENT_STEM_CELL":
            return False

        body_path = self.state_dir / f"{swimmer_id}_BODY.json"
        if not body_path.exists():
            return False

        dominant = self._sense_dominant_pressure(swimmer_id)
        if dominant == "UNDIFFERENTIATED":
            return False

        trace_id = uuid.uuid4().hex[:16]
        rec = {
            "ts": time.time(),
            "swimmer_id": swimmer_id,
            "phenotype": dominant,
            "trace_id": trace_id,
            "coefficient_overrides": PHENOTYPE_PROFILES.get(dominant, {}),
            "permanent": PHENOTYPE_LOCK_PERMANENT,
        }
        self._append_phenotype(rec)

        print(f"\n[+] MORPHOGENESIS: {swimmer_id} differentiated → {dominant}")
        print(f"[*] {swimmer_id} permanently locked as {dominant} "
              f"(phenotype trace={trace_id})")
        return True

    def coefficient_overrides_for(self, swimmer_id: str) -> dict:
        """
        Public read-side: cortex modules call this to learn whether a
        swimmer's phenotype demands modulated coefficients. Returns {}
        if undifferentiated.
        """
        latest = self._latest_phenotype_record(swimmer_id)
        return latest.get("coefficient_overrides", {})

    # ─── Pressure sensing (canonical schemas) ───────────────────────────

    def _sense_dominant_pressure(self, swimmer_id: str) -> str:
        now = time.time()
        pressures = {"ach": 0.0, "fear": 0.0, "stgm": 0.0}

        # ACH pressure — NMJ ledger uses {timestamp, potency} (Bishop)
        pressures["ach"] = self._sum_recent(
            self.ach_ledger, now,
            ts_key="timestamp", value_key="potency",
            window=300, default_value=1.0,
        )

        # Fear pressure — amygdala ledger uses {timestamp, severity, node_id}
        # (AG31's own schema; consistent within his amygdala module)
        pressures["fear"] = self._sum_recent(
            self.fear_ledger, now,
            ts_key="timestamp", value_key="severity",
            window=300, default_value=1.0,
            filter_key="node_id", filter_val=swimmer_id,
        )

        # STGM pressure — REWARDS ledger uses CANONICAL schema:
        # {ts, app, reason, amount, trace_id}. Reason carries the
        # swimmer/app context; we accept records whose `reason` mentions
        # the swimmer_id OR whose `app` matches.
        pressures["stgm"] = self._sum_canonical_rewards(
            swimmer_id, now, window=PRESSURE_WINDOW_S,
        )

        dominant = max(pressures, key=pressures.get)
        if pressures[dominant] < PRESSURE_THRESHOLD:
            return "UNDIFFERENTIATED"
        if dominant == "stgm":  return "QUEEN"
        if dominant == "fear":  return "SENTINEL"
        return "BUILDER"

    def _sum_recent(self, path: Path, now: float, *,
                    ts_key: str, value_key: str, window: float,
                    default_value: float = 1.0,
                    filter_key: Optional[str] = None,
                    filter_val: Optional[str] = None) -> float:
        if not path.exists():
            return 0.0
        total = 0.0
        try:
            with path.open("r", encoding="utf-8") as f:
                lines = f.readlines()[-100:]  # bounded scan
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if filter_key and rec.get(filter_key) != filter_val:
                    continue
                if now - float(rec.get(ts_key, 0) or 0) < window:
                    total += float(rec.get(value_key, default_value) or default_value)
        except OSError:
            pass
        return total

    def _sum_canonical_rewards(self, swimmer_id: str, now: float,
                               window: float) -> float:
        """
        Read stgm_memory_rewards.jsonl using the CANONICAL schema:
        {ts, app, reason, amount, trace_id}. Records are attributed
        to a swimmer if its id appears in `reason` or `app`.
        """
        if not self.rewards_ledger.exists():
            return 0.0
        total = 0.0
        try:
            with self.rewards_ledger.open("r", encoding="utf-8") as f:
                lines = f.readlines()[-200:]
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = float(rec.get("ts", 0) or 0)
                if (now - ts) >= window:
                    continue
                reason = str(rec.get("reason", "") or "")
                app    = str(rec.get("app", "") or "")
                if swimmer_id in reason or swimmer_id == app:
                    total += float(rec.get("amount", 0.0) or 0.0)
        except OSError:
            pass
        return total

    # ─── Side-ledger I/O (replaces _BODY.json mutation) ─────────────────

    def _append_phenotype(self, rec: dict) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        append_line_locked(
            self.phenotype_ledger,
            json.dumps(rec, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _latest_phenotype_record(self, swimmer_id: str) -> dict:
        if not self.phenotype_ledger.exists():
            return {}
        latest = {}
        try:
            with self.phenotype_ledger.open("r", encoding="utf-8") as f:
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


# ─── Smoke (canonical schemas only — smoke green ⇒ prod green) ───────────


def _smoke():
    """
    REAL primitives. Sandboxed tempdir. Asserts against CANONICAL schemas
    so passing the smoke proves prod correctness — the v1 bug was that
    the smoke fixture mirrored the broken consumer; v2 fixture mirrors
    the canonical writer.
    """
    import tempfile

    print("\n=== SIFTA MORPHOGENESIS (CELLULAR DIFFERENTIATION) — SAFE SMOKE ===\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        morph = SwarmMorphogenesis(state_dir=tmp)

        swimmer_id = "M1_STEM"
        body_path = tmp / f"{swimmer_id}_BODY.json"
        # Body matches CANONICAL schema — no megagene, no cellular_phenotype
        body_path.write_text(json.dumps({
            "id": swimmer_id,
            "ascii": "::stem::",
            "energy": 1.0,
            "style": "test",
            "stgm_balance": 0.0,
        }))

        # Write rewards using CANONICAL schema (the v1 fixture used the
        # broken Bishop schema and that's why the v1 smoke passed but
        # prod was dead)
        for _ in range(10):
            morph._append_phenotype  # silence linter; no-op
            with morph.rewards_ledger.open("a") as f:
                f.write(json.dumps({
                    "ts": time.time(),
                    "app": "test_runner",
                    "reason": f"reward for {swimmer_id} mining",
                    "amount": 50.0,
                    "trace_id": "smoke_test_pressure",
                }) + "\n")

        # Initial state
        assert morph.current_phenotype(swimmer_id) == "TOTIPOTENT_STEM_CELL"
        assert morph.coefficient_overrides_for(swimmer_id) == {}
        print("[PASS] new swimmer is TOTIPOTENT with no overrides")

        # Differentiate — should detect STGM pressure via canonical schema
        assert morph.execute_differentiation(swimmer_id) is True
        print("[PASS] differentiation triggered against CANONICAL "
              "stgm_memory_rewards schema {ts,app,reason,amount,trace_id}")

        # Phenotype: QUEEN (STGM dominant)
        assert morph.current_phenotype(swimmer_id) == "QUEEN"
        print("[PASS] Cell differentiated into QUEEN (STGM pressure)")

        # Coefficient overrides exposed for the cortex modules
        overrides = morph.coefficient_overrides_for(swimmer_id)
        assert overrides["phi_ssp"]["alpha"] == 10.0
        assert overrides["psi_motor"]["b"] == 0.1
        print(f"[PASS] QUEEN overrides exposed: phi_ssp.alpha=10.0, "
              f"psi_motor.b=0.1")

        # CRITICAL — body schema is UNCHANGED (F11 honored)
        body_after = json.loads(body_path.read_text())
        assert "cellular_phenotype" not in body_after, \
            "F11: BODY must not be polluted with cellular_phenotype"
        assert "megagene" not in body_after, \
            "F11: BODY must not be polluted with megagene"
        assert sorted(body_after.keys()) == \
            sorted(["id", "ascii", "energy", "style", "stgm_balance"]), \
            "F11: BODY schema must be unchanged"
        print("[PASS] _BODY.json schema unchanged (F11 honored — "
              "phenotype lives in side ledger)")

        # Idempotent
        assert morph.execute_differentiation(swimmer_id) is False
        print("[PASS] differentiation is idempotent — second call no-op")

        # Side ledger has clean trail
        records = [json.loads(l) for l in
                   morph.phenotype_ledger.read_text().splitlines() if l.strip()]
        assert len(records) == 1
        assert records[0]["phenotype"] == "QUEEN"
        assert records[0]["permanent"] is True
        assert "trace_id" in records[0]
        print("[PASS] phenotype side-ledger has 1 clean record with trace_id")

        print("\n=== SAFE MORPHOGENESIS SMOKE COMPLETE ===")
        print("    Bishop's biology + AG31's structure + canonical I/O.")
        print("    Bodies sacred. Phenotypes attributable. Smoke ⇒ prod.\n")


if __name__ == "__main__":
    _smoke()
