#!/usr/bin/env python3
"""swarm_latent_world_model_trainer.py — receipt → Dreamer trainer.

Truth label: ``SIFTA_LATENT_WORLD_MODEL_TRAINER_V1``.

Closes the ``learned_latent_models`` open gap reported by
:mod:`System.swarm_agi_frontier_loop`.

The peer-shipped :mod:`System.swarm_latent_world_model` defines the
Dreamer-style :class:`LatentWorldModel` (transition table, value table,
Bellman TD backup, epsilon-greedy policy). What it does **not** ship is
the wiring that turns local receipts into ``observe_reality`` /
``td_update`` calls — so the file ``latent_world_model.json`` never
appears on disk and the frontier loop stays ``OPEN_NO_ARTIFACT``.

This module is the missing edge per §8.5 of ``IDE_BOOT_COVENANT.md``:
audit, don't redo. It walks two existing ledgers and feeds the peer
model:

  ``.sifta_state/steering_prediction_audit.jsonl``
      Carries ``pairs`` of ``(dominant_detector, predicted_next_route,
      actual_route, correct)`` rows. Each pair is one ``observe_reality``
      call with reward ``1.0`` if ``correct`` else ``0.0``.

  ``.sifta_state/steering_subsystem.jsonl``
      Carries ``importance_label``, ``matched_pattern``, and a list of
      ``predictions``. We take the prediction with the highest confidence
      as the action and use its confidence as reward.

After observation, a sweep of Bellman backups propagates value through
the graph so ``value_table`` is non-trivial. The peer save() flushes
``latent_world_model.json`` to ``.sifta_state/`` — the artifact the
frontier loop is waiting for.

Every run appends a receipt to ``latent_world_model_trainer.jsonl`` so
the swarm can audit the population. Nothing here invents data; every
row maps to a real receipt row.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from System.swarm_latent_world_model import LatentWorldModel, WORLD_MODEL_PATH
except Exception:  # pragma: no cover - import smoke
    LatentWorldModel = None  # type: ignore
    WORLD_MODEL_PATH = None  # type: ignore

try:
    from System.swarm_persistent_owner_history import state_dir
except Exception:  # pragma: no cover - bootstrap fallback
    def state_dir(explicit: Optional[Path] = None) -> Path:  # type: ignore[override]
        if explicit is not None:
            return Path(explicit)
        return Path(__file__).resolve().parent.parent / ".sifta_state"


TRUTH_LABEL = "SIFTA_LATENT_WORLD_MODEL_TRAINER_V1"
TRAINER_LEDGER = "latent_world_model_trainer.jsonl"

TRUTH_BOUNDARY = (
    "Walks two receipt ledgers and feeds them into the peer-shipped "
    "LatentWorldModel (Dreamer-style transition + Bellman TD). No row "
    "is invented; every observation maps to a real receipt row. The "
    "trainer is the wiring, not the model."
)


# ── ledger I/O ───────────────────────────────────────────────────────────


def _sd(root: Optional[Path] = None) -> Path:
    d = state_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_jsonl(path: Path, max_rows: int = 1000) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for line in text.splitlines()[-max(1, max_rows) :]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _clamp(value: Any, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        f = lo
    return round(max(lo, min(hi, f)), 4)


# ── triple extraction (returns canonical strings, not encoded hashes) ────


def _iter_audit_triples(rows: Iterable[Dict[str, Any]]) -> Iterable[Tuple[str, str, str, float]]:
    """Walk audit pairs, yield ``(state, action, next_state, reward)``."""
    for row in rows:
        pairs = row.get("pairs")
        if not isinstance(pairs, list):
            continue
        for p in pairs:
            if not isinstance(p, dict):
                continue
            state = p.get("dominant_detector")
            action = p.get("predicted_next_route")
            next_state = p.get("actual_route")
            if not (state and action and next_state):
                continue
            reward = 1.0 if bool(p.get("correct", False)) else 0.0
            yield (
                f"dom:{state}",
                str(action),
                f"route:{next_state}",
                reward,
            )


def _iter_steering_decision_triples(rows: Iterable[Dict[str, Any]]) -> Iterable[Tuple[str, str, str, float]]:
    """Steering decisions → (importance, action, pattern, confidence)."""
    for row in rows:
        imp = row.get("importance_label")
        pattern = row.get("matched_pattern")
        preds = row.get("predictions") or []
        if not (imp and pattern):
            continue
        if not isinstance(preds, list) or not preds:
            continue
        best: Optional[Dict[str, Any]] = None
        for p in preds:
            if not isinstance(p, dict):
                continue
            if best is None or float(p.get("confidence", 0.0)) > float(
                best.get("confidence", 0.0)
            ):
                best = p
        if best is None:
            continue
        action = best.get("target") or best.get("source") or "default"
        reward = _clamp(best.get("confidence"), 0.0, 1.0)
        yield (
            f"imp:{imp}",
            str(action),
            f"pat:{pattern}",
            reward,
        )


def _iter_journal_sequence_triples(
    rows: List[Dict[str, Any]],
) -> Iterable[Tuple[str, str, str, float]]:
    """Sequential journal pairs: (source[i], 'log_event', source[i+1]).

    Reward is ``importance`` from the next row when present, else 0.5
    (a mid-band neutral signal — the row exists, so something happened).
    """
    if not rows:
        return
    prev_source = None
    for row in rows:
        source = row.get("source")
        if not source:
            continue
        if prev_source is not None and source != prev_source:
            imp = row.get("importance")
            try:
                reward = float(imp) if imp is not None else 0.5
            except (TypeError, ValueError):
                reward = 0.5
            yield (
                f"src:{prev_source}",
                "log_event",
                f"src:{source}",
                max(0.0, min(1.0, reward)),
            )
        prev_source = source


def _iter_work_receipt_triples(rows: List[Dict[str, Any]]) -> Iterable[Tuple[str, str, str, float]]:
    """Work receipts → (lane, action, next_lane).

    The IDE Doctors trace through lanes (Surgeon, Auditor, Probe,
    Release, Architect-support). Each consecutive (lane, action_kind,
    next_lane) is a real workflow transition. Reward is 1.0 when the
    next row carries a ``tests`` string (meaning the action was
    test-backed) else 0.0.
    """
    if not rows:
        return
    prev_lane = None
    for row in rows:
        lane = row.get("lane")
        action = row.get("action") or row.get("kind") or "WORK"
        if not lane:
            continue
        if prev_lane is not None:
            tests = row.get("tests") or row.get("test_summary")
            reward = 1.0 if (isinstance(tests, str) and tests.strip()) else 0.0
            yield (
                f"lane:{prev_lane}",
                str(action),
                f"lane:{lane}",
                reward,
            )
        prev_lane = lane


def _collect_triples(
    *, root: Optional[Path] = None, max_rows_per_source: int = 500
) -> Tuple[List[Tuple[str, str, str, float]], Dict[str, int]]:
    base = _sd(root)
    triples: List[Tuple[str, str, str, float]] = []
    counts: Dict[str, int] = {}

    audit_path = base / "steering_prediction_audit.jsonl"
    audit_rows = _read_jsonl(audit_path, max_rows=max_rows_per_source)
    counts["steering_prediction_audit.jsonl"] = len(audit_rows)
    triples.extend(_iter_audit_triples(audit_rows))

    steer_path = base / "steering_subsystem.jsonl"
    steer_rows = _read_jsonl(steer_path, max_rows=max_rows_per_source)
    counts["steering_subsystem.jsonl"] = len(steer_rows)
    triples.extend(_iter_steering_decision_triples(steer_rows))

    journal_path = base / "alice_first_person_journal.jsonl"
    journal_rows = _read_jsonl(journal_path, max_rows=max_rows_per_source)
    counts["alice_first_person_journal.jsonl"] = len(journal_rows)
    triples.extend(_iter_journal_sequence_triples(journal_rows))

    work_path = base / "work_receipts.jsonl"
    work_rows = _read_jsonl(work_path, max_rows=max_rows_per_source)
    counts["work_receipts.jsonl"] = len(work_rows)
    triples.extend(_iter_work_receipt_triples(work_rows))

    return triples, counts


# ── trainer ──────────────────────────────────────────────────────────────


def train_from_receipts(
    *,
    root: Optional[Path] = None,
    bellman_sweeps: int = 8,
    extra_triples: Optional[Iterable[Tuple[str, str, str, float]]] = None,
    save: bool = True,
) -> Dict[str, Any]:
    """Mine local receipts, feed the peer model, optionally save.

    Returns a receipt dict ``{transition_count, value_count, ...}``. The
    transition / value counts are exactly what the AGI frontier loop
    counts when it gates the latent-world frontier.

    If the peer module is unavailable (import smoke failed), this raises
    a clear ``RuntimeError`` rather than silently shipping fake state.
    """
    if LatentWorldModel is None:
        raise RuntimeError(
            "swarm_latent_world_model.LatentWorldModel is not importable; "
            "cannot train without the peer model."
        )

    # Redirect WORLD_MODEL_PATH to the test/state root so trainer is
    # safe under pytest tmp_path. We patch the module attribute, not the
    # class — the class only touches the attribute when save()/_load()
    # is called.
    from System import swarm_latent_world_model as peer

    base = _sd(root)
    artifact_path = base / "latent_world_model.json"
    original_path = peer.WORLD_MODEL_PATH
    peer.WORLD_MODEL_PATH = artifact_path

    try:
        triples, source_counts = _collect_triples(root=root)
        if extra_triples:
            triples = list(triples) + list(extra_triples)

        # Fresh model so we control the initial state (prevents picking
        # up state from a previous run during tests).
        model = LatentWorldModel()
        # Force a clean slate even if _load() picked up an old artifact
        # from somewhere else (tmp_path is the only place we save).
        model.transitions = {}
        model.value_table = {}

        # Observe every triple — the peer class handles deduplication
        # and counting internally.
        for s, a, ns, r in triples:
            model.observe_reality(s, a, ns, r)

        # A few sweeps of Bellman backup so values propagate.
        for _ in range(max(1, int(bellman_sweeps))):
            for sa_key, t in list(model.transitions.items()):
                state_hash, _, _action = sa_key.partition("::")
                next_hash = t.get("next_state")
                reward = float(t.get("reward", 0.0))
                if state_hash and next_hash:
                    model.td_update(state_hash, next_hash, reward)

        transition_count = len(model.transitions)
        value_count = len(model.value_table)

        if save:
            model.save()

        # Receipt
        receipt = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "kind": "LATENT_WORLD_MODEL_TRAINER_RUN",
            "truth_label": TRUTH_LABEL,
            "truth_boundary": TRUTH_BOUNDARY,
            "triple_count": len(triples),
            "transition_count": transition_count,
            "value_count": value_count,
            "source_counts": source_counts,
            "bellman_sweeps": int(bellman_sweeps),
            "artifact_path": str(artifact_path),
        }
        payload = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        receipt["sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        if save:
            ledger = base / TRAINER_LEDGER
            with ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")

        return receipt
    finally:
        peer.WORLD_MODEL_PATH = original_path


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-save", action="store_true")
    p.add_argument("--sweeps", type=int, default=8)
    args = p.parse_args()
    out = train_from_receipts(bellman_sweeps=args.sweeps, save=not args.no_save)
    print(f"TRUTH:            {out['truth_label']}")
    print(f"TRIPLES_OBSERVED: {out['triple_count']}")
    print(f"TRANSITION_COUNT: {out['transition_count']}")
    print(f"VALUE_COUNT:      {out['value_count']}")
    print(f"SOURCE_COUNTS:    {out['source_counts']}")
    print(f"ARTIFACT:         {out['artifact_path']}")
    print(f"SHA:              {out['sha256'][:16]}")
