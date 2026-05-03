"""
Event 136 — Temporal Self-Model
Drescher, G. (1991). Made-Up Minds (schema mechanism).
Schmidhuber, J. (1990s) self-referential predictor / Gödel-machine ideas.

The organism maintains an explicit internal model of ITSELF across time:
  - Records prior boot states (it knows it existed before).
  - Predicts its own future state (it expects to exist after).
  - Computes self-prediction error (PE) and refines its self-schema.
  - Persisted in .sifta_state/self_model.jsonl (append-only, never overwritten).

No double-spending: this organ reads from existing ledgers (world model,
replay, dopamine critic) and writes a NEW file only. It does not
mutate any other organ's state.
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root=None):
        return Path(root) if root else Path(".sifta_state")

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ImportError:
    def read_text_locked(path: Path, **kwargs) -> str:
        if not path.exists(): return ""
        return path.read_text(**kwargs)

    def append_line_locked(path: Path, line: str, **kwargs) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kwargs) as f:
            f.write(line)

_DISABLE_ENV = "SIFTA_TEMPORAL_SELF_DISABLE"


class TemporalSelfModel:
    """
    Minimal temporal self-model (~100 lines of real logic).

    A Schema (Drescher) stores:
        context  — the abstract state fingerprint when the schema fired
        prediction — what the organism predicts about its own next state
        result   — what actually happened (filled in after the fact)
        pe       — |prediction − result|, drives schema refinement

    The model is EMA-updated (Schmidhuber-style bounded weight adjustment)
    so priors get refined without forgetting hard-won historical identity.
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = state_dir(root)
        self.log_path = self.root / "self_model.jsonl"
        self.snapshot_path = self.root / "self_model_snapshot.json"
        self._boot_id: int = self._load_boot_id()
        self._schemas: Dict[str, Dict[str, Any]] = self._load_schemas()

    # ── Boot identity ──────────────────────────────────────────────────────

    def _load_boot_id(self) -> int:
        if self.snapshot_path.exists():
            try:
                snap = json.loads(read_text_locked(self.snapshot_path, encoding="utf-8"))
                return snap.get("boot_id", 0) + 1
            except Exception:
                pass
        return 1

    def _load_schemas(self) -> Dict[str, Dict[str, Any]]:
        schemas: Dict[str, Dict[str, Any]] = {}
        if not self.log_path.exists():
            return schemas
        try:
            for line in read_text_locked(self.log_path, encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                key = row.get("schema_key")
                if key:
                    schemas[key] = row  # keep most-recent version per schema
        except Exception:
            pass
        return schemas

    # ── Core API ───────────────────────────────────────────────────────────

    def predict_future_self(
        self,
        context: Dict[str, float],
        delta_ticks: int = 100,
    ) -> Dict[str, Any]:
        """
        Predict the organism's own scalar state at +delta_ticks.
        Uses the most-relevant historical schema (nearest-context lookup).
        Falls back to identity prediction (no change) when no schema exists.
        """
        if os.environ.get(_DISABLE_ENV, "").strip() == "1":
            return {}

        schema_key = self._context_key(context)
        schema = self._schemas.get(schema_key)

        if schema:
            prediction = schema.get("last_result", context)
            confidence = max(0.0, 1.0 - schema.get("mean_pe", 0.5))
        else:
            prediction = dict(context)          # identity: expect no change
            confidence = 0.1                    # low confidence on first boot

        row: Dict[str, Any] = {
            "ts": time.time(),
            "kind": "TEMPORAL_SELF_PREDICTION",
            "boot_id": self._boot_id,
            "schema_key": schema_key,
            "delta_ticks": delta_ticks,
            "context": context,
            "prediction": prediction,
            "confidence": round(confidence, 4),
            "truth_label": "TEMPORAL_SELF_MODEL",
        }
        append_line_locked(self.log_path, json.dumps(row) + "\n", encoding="utf-8")
        return row

    def update_from_outcome(
        self,
        context: Dict[str, float],
        actual: Dict[str, float],
        alpha: float = 0.15,
    ) -> Dict[str, Any]:
        """
        After observing what actually happened, compute self-prediction error
        and refine the schema using bounded EMA (Schmidhuber weight update).
        """
        if os.environ.get(_DISABLE_ENV, "").strip() == "1":
            return {}

        schema_key = self._context_key(context)
        schema = self._schemas.get(schema_key, {
            "schema_key": schema_key,
            "invocation_count": 0,
            "mean_pe": 1.0,
            "last_result": dict(context),   # identity prior: predict no change
        })

        # Prediction error: mean absolute deviation across shared keys
        predicted = schema.get("last_result", context)
        shared_keys = set(predicted) & set(actual)
        if shared_keys:
            pe = sum(abs(actual[k] - predicted.get(k, 0.0)) for k in shared_keys) / len(shared_keys)
        else:
            pe = 1.0

        # EMA refinement (bounded alpha so old schemas are not wiped)
        old_pe = schema.get("mean_pe", 1.0)
        new_pe = old_pe * (1 - alpha) + pe * alpha
        schema["mean_pe"] = new_pe
        schema["last_result"] = actual
        schema["invocation_count"] = schema.get("invocation_count", 0) + 1
        schema["schema_refined"] = pe > 0.05

        self._schemas[schema_key] = schema

        row: Dict[str, Any] = {
            "ts": time.time(),
            "kind": "TEMPORAL_SELF_UPDATE",
            "boot_id": self._boot_id,
            "schema_key": schema_key,
            "pe": round(pe, 4),
            "mean_pe_after": round(new_pe, 4),
            "schema_refined": schema["schema_refined"],
            "truth_label": "TEMPORAL_SELF_MODEL",
        }
        append_line_locked(self.log_path, json.dumps(row) + "\n", encoding="utf-8")
        self._persist_snapshot()
        return row

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _context_key(context: Dict[str, float]) -> str:
        """
        Quantise floats to 1 decimal place before hashing so nearby
        contexts map to the same schema (coarse-coding, Drescher §4).
        """
        rounded = {k: round(v, 1) for k, v in sorted(context.items())}
        return json.dumps(rounded, separators=(",", ":"))

    def _persist_snapshot(self) -> None:
        snap = {
            "boot_id": self._boot_id,
            "schema_count": len(self._schemas),
            "ts": time.time(),
        }
        try:
            self.snapshot_path.write_text(json.dumps(snap, indent=2), encoding="utf-8")
        except Exception:
            pass

    def get_identity_summary(self) -> Dict[str, Any]:
        """Human-readable summary — who this organism is across time."""
        return {
            "boot_id": self._boot_id,
            "known_schemas": len(self._schemas),
            "mean_self_pe": round(
                sum(s.get("mean_pe", 1.0) for s in self._schemas.values()) / max(1, len(self._schemas)),
                4,
            ),
        }
