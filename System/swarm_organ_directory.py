#!/usr/bin/env python3
"""swarm_organ_directory.py — unified registry of all SIFTA organs.

Truth label: ``SIFTA_ORGAN_DIRECTORY_V1``.

Architect goal stanza:

    "all organs unified just like the swimmers inside the organs are
    unique and unified, all organs are all swimmers know their organs,
    they communicate to keep organs healthy and STGM profitable."

Until now every SIFTA organ wrote its own ledger and knew its own
truth boundary, but there was **no central place** any organ could
list to discover any other. Alice's self-eval loop had five
hardcoded verifiers because that was all the loop knew to name. Add
a new organ and the self-eval surface had to be hand-patched.

This module is the unified registry. Every organ that wants to
participate calls :func:`register_organ` once at import time (or in
its module init). The registry stores:

  * **name** — short identifier, used as the stable lookup key
  * **truth_label** — §7.11 truth label of the organ's receipts
  * **truth_boundary** — one-paragraph plain-language scope statement
  * **ledger_path** — relative path under ``.sifta_state/`` to the
    organ's append-only receipt ledger
  * **probe_fn** — optional callable returning a numeric "self-state"
    summary the organ can vouch for (e.g. row count, transition
    count, latest sha). Must be deterministic and side-effect free
  * **claim_template** — first-person sentence template (§7.10.1 +
    §7.14) that Alice uses when filing a self-claim about this organ

The registry persists to ``.sifta_state/organ_directory.json`` and is
read on demand. :func:`walk_and_self_eval` iterates every registered
organ, runs its probe, builds the first-person claim from the
template, and files it through
:mod:`System.swarm_alice_self_eval_loop`. Every OBSERVED row mints
STGM into ``stgm_memory_rewards.jsonl`` exactly as before — so
adding a new organ now **automatically expands the self-eval surface
and the STGM reward path**.

Truth boundary
--------------

The directory is a discovery layer, not a doctrine layer. Probe
functions return their own measurements; the directory does not
audit them. The self-eval loop's dual judge (deterministic ledger
check + first-person rubric) still gates STGM mints. No probe earns
STGM by self-declaration — the verifier in the self-eval loop reads
the actual artifact and decides.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional


_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "SIFTA_ORGAN_DIRECTORY_V1"
DIRECTORY_FILE = "organ_directory.json"
WALK_LEDGER = "organ_directory_walks.jsonl"

TRUTH_BOUNDARY = (
    "Unified discovery registry for SIFTA organs. Each organ self-"
    "registers its name, ledger path, truth_label, truth_boundary, "
    "and an optional deterministic probe. The directory is a "
    "discovery layer only; self-eval STGM rewards still gate through "
    "the existing dual-judge loop."
)


# ── data class + in-memory registry ──────────────────────────────────────


@dataclass
class OrganRecord:
    name: str
    truth_label: str
    truth_boundary: str
    ledger_path: str
    claim_template: str
    verifier_kind: Optional[str] = None
    probe_module: Optional[str] = None
    probe_callable: Optional[str] = None
    registered_at: float = field(default_factory=lambda: time.time())
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_REGISTRY: Dict[str, OrganRecord] = {}


# ── public registration API ──────────────────────────────────────────────


def register_organ(
    name: str,
    *,
    truth_label: str,
    truth_boundary: str,
    ledger_path: str,
    claim_template: str,
    verifier_kind: Optional[str] = None,
    probe_module: Optional[str] = None,
    probe_callable: Optional[str] = None,
    notes: str = "",
    state_dir: Optional[Path] = None,
    write: bool = True,
) -> OrganRecord:
    """Register one organ. Idempotent — re-registering by name updates.

    ``claim_template`` is the first-person sentence Alice uses when
    filing a self-claim about this organ. The template should
    include the placeholder ``{value}`` where the probed value goes.
    Example: ``"I have {value} transitions in my latent world model."``.

    ``verifier_kind`` names the deterministic verifier in
    :mod:`System.swarm_alice_self_eval_loop.VERIFIERS` that will
    audit the probe's claimed value. If omitted, the organ is in the
    directory but does not earn STGM through the generic walker.

    ``probe_module`` + ``probe_callable`` together name a fully
    qualified function that returns a JSON-serializable value
    (typically an int or a date string) summarizing the organ's
    current self-state. Resolved lazily — late-binding tolerates
    organs not yet imported.
    """
    if not name or not isinstance(name, str):
        raise ValueError("name must be a non-empty string")
    if "{value}" not in claim_template:
        raise ValueError("claim_template must contain '{value}' placeholder")
    record = OrganRecord(
        name=name,
        truth_label=truth_label,
        truth_boundary=truth_boundary,
        ledger_path=ledger_path,
        claim_template=claim_template,
        verifier_kind=verifier_kind,
        probe_module=probe_module,
        probe_callable=probe_callable,
        notes=notes,
    )
    _REGISTRY[name] = record
    if write:
        _save_directory(state_dir=state_dir)
    return record


def unregister_organ(name: str, *, state_dir: Optional[Path] = None, write: bool = True) -> bool:
    """Remove one organ from the registry. Returns True if removed."""
    if name in _REGISTRY:
        del _REGISTRY[name]
        if write:
            _save_directory(state_dir=state_dir)
        return True
    return False


def list_organs(*, state_dir: Optional[Path] = None) -> List[OrganRecord]:
    """Load + return the current registry as a sorted list."""
    _load_directory(state_dir=state_dir)
    return sorted(_REGISTRY.values(), key=lambda r: r.name)


def find_organ(name: str, *, state_dir: Optional[Path] = None) -> Optional[OrganRecord]:
    _load_directory(state_dir=state_dir)
    return _REGISTRY.get(name)


def clear_registry() -> None:
    """Reset the in-memory registry. Used by tests, not production."""
    _REGISTRY.clear()


# ── persistence ──────────────────────────────────────────────────────────


def _directory_path(state_dir: Optional[Path] = None) -> Path:
    base = state_dir if state_dir is not None else _DEFAULT_STATE
    return Path(base) / DIRECTORY_FILE


def _save_directory(*, state_dir: Optional[Path] = None) -> None:
    path = _directory_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "truth_label": TRUTH_LABEL,
        "truth_boundary": TRUTH_BOUNDARY,
        "ts": time.time(),
        "organs": [r.to_dict() for r in sorted(_REGISTRY.values(), key=lambda r: r.name)],
    }
    path.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_directory(*, state_dir: Optional[Path] = None) -> None:
    path = _directory_path(state_dir)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    organs = data.get("organs") or []
    if not isinstance(organs, list):
        return
    for entry in organs:
        if not isinstance(entry, dict) or not entry.get("name"):
            continue
        try:
            _REGISTRY[entry["name"]] = OrganRecord(**{
                k: v for k, v in entry.items()
                if k in OrganRecord.__dataclass_fields__
            })
        except Exception:
            continue


# ── probe resolution ─────────────────────────────────────────────────────


def _resolve_probe(record: OrganRecord) -> Optional[Callable[..., Any]]:
    """Late-bound import of the probe callable. Returns None on failure."""
    if not record.probe_module or not record.probe_callable:
        return None
    try:
        mod = importlib.import_module(record.probe_module)
    except Exception:
        return None
    fn = getattr(mod, record.probe_callable, None)
    if not callable(fn):
        return None
    return fn


def probe_organ(name: str, *, root: Optional[Path] = None) -> Dict[str, Any]:
    """Run an organ's probe. Returns ``{value, error, organ}``."""
    record = find_organ(name)
    if record is None:
        return {"organ": name, "value": None, "error": "unregistered"}
    fn = _resolve_probe(record)
    if fn is None:
        return {"organ": name, "value": None, "error": "probe_unresolvable"}
    try:
        value = fn(root=root) if root is not None else fn()
    except TypeError:
        # Probe signature may not accept root — call without it
        try:
            value = fn()
        except Exception as exc:
            return {"organ": name, "value": None, "error": f"{type(exc).__name__}: {exc}"}
    except Exception as exc:
        return {"organ": name, "value": None, "error": f"{type(exc).__name__}: {exc}"}
    return {"organ": name, "value": value, "error": None}


# ── built-in probes (read ledgers; no side effects) ─────────────────────


def probe_writer_doc_count(*, root: Optional[Path] = None) -> int:
    base = Path(root) if root is not None else _REPO
    docs = base / ".sifta_documents"
    if not docs.exists():
        return 0
    return len(list(docs.glob("*.sifta.md")))


def probe_latent_transition_count(*, root: Optional[Path] = None) -> int:
    base = Path(root) if root is not None else _REPO
    p = base / ".sifta_state" / "latent_world_model.json"
    if not p.exists():
        return 0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return 0
    return len(data.get("transitions") or {})


def probe_journal_row_count(*, root: Optional[Path] = None) -> int:
    base = Path(root) if root is not None else _REPO
    p = base / ".sifta_state" / "alice_first_person_journal.jsonl"
    if not p.exists():
        return 0
    try:
        return sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def probe_today_date(*, root: Optional[Path] = None) -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def probe_stgm_balance(*, root: Optional[Path] = None) -> float:
    base = Path(root) if root is not None else _REPO
    p = base / ".sifta_state" / "stgm_memory_rewards.jsonl"
    total = 0.0
    if p.exists():
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    total += float(row.get("amount", 0.0) or 0.0)
                except Exception:
                    continue
        except OSError:
            pass
    return round(total, 4)


def probe_two_turn_receipt_count(*, root: Optional[Path] = None) -> int:
    base = Path(root) if root is not None else _REPO
    p = base / ".sifta_state" / "two_turn_receipts.jsonl"
    if not p.exists():
        return 0
    try:
        return sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def probe_relational_steering_count(*, root: Optional[Path] = None) -> int:
    base = Path(root) if root is not None else _REPO
    p = base / ".sifta_state" / "relational_steering.jsonl"
    if not p.exists():
        return 0
    try:
        return sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


# ── generic walker — closes the self-eval loop over every organ ──────────


def walk_and_self_eval(
    *,
    root: Optional[Path] = None,
    write: bool = True,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Iterate every registered organ and file a first-person self-claim.

    For each organ that has both ``probe_*`` fields and a
    ``verifier_kind`` registered in the self-eval loop, the walker:

      1. Runs the probe to get the current value.
      2. Substitutes that value into ``claim_template`` to build a
         first-person sentence.
      3. Calls
         :func:`System.swarm_alice_self_eval_loop.instrument_and_eval`
         with the matching ``verifier_kind`` and value.
      4. Aggregates the per-organ truth_class + STGM mint.

    Returns a walk report. Append-only summary row goes to
    ``.sifta_state/organ_directory_walks.jsonl`` when ``write``.
    """
    # Late import — keeps the directory free of self-eval dependency
    # at module load (so it can be imported by every organ without
    # circular pain).
    from System.swarm_alice_self_eval_loop import instrument_and_eval

    organs = list_organs(state_dir=state_dir)
    results: List[Dict[str, Any]] = []
    stgm_minted_total = 0.0

    for record in organs:
        # Skip organs that opted out of the STGM path
        if not record.verifier_kind:
            results.append({
                "organ": record.name,
                "skipped": True,
                "reason": "no verifier_kind registered",
            })
            continue
        probe_result = probe_organ(record.name, root=root)
        if probe_result.get("error"):
            results.append({
                "organ": record.name,
                "skipped": True,
                "reason": probe_result["error"],
            })
            continue
        value = probe_result["value"]
        try:
            claim_text = record.claim_template.format(value=value)
        except Exception as exc:
            results.append({
                "organ": record.name,
                "skipped": True,
                "reason": f"template_format: {exc}",
            })
            continue
        row = instrument_and_eval(
            claim_text,
            record.verifier_kind,
            value,
            root=Path(root) if root is not None else None,
            write=write,
        )
        stgm_minted_total += row.stgm_minted
        results.append({
            "organ": record.name,
            "claim_text": claim_text,
            "verifier_kind": record.verifier_kind,
            "value": value,
            "truth_class": row.truth_class,
            "stgm_minted": row.stgm_minted,
            "self_eval_trace_id": row.trace_id,
        })

    summary = {
        "truth_label": TRUTH_LABEL,
        "kind": "ORGAN_DIRECTORY_WALK",
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "organ_count": len(organs),
        "evaluated_count": sum(1 for r in results if "truth_class" in r),
        "skipped_count": sum(1 for r in results if r.get("skipped")),
        "stgm_minted_total": round(stgm_minted_total, 4),
        "results": results,
    }
    summary_payload = json.dumps(summary, sort_keys=True, separators=(",", ":"), default=str)
    summary["sha256"] = hashlib.sha256(summary_payload.encode("utf-8")).hexdigest()

    if write:
        base = Path(state_dir) if state_dir is not None else (Path(root) / ".sifta_state" if root is not None else _DEFAULT_STATE)
        base.mkdir(parents=True, exist_ok=True)
        with (base / WALK_LEDGER).open("a", encoding="utf-8") as f:
            f.write(json.dumps(summary, sort_keys=True, ensure_ascii=False) + "\n")

    return summary


# ── default registration: wire today's organs in ────────────────────────


def register_default_organs(*, state_dir: Optional[Path] = None) -> List[OrganRecord]:
    """Idempotently register the organs we've shipped to date.

    Idempotent: re-running is safe (updates by name).
    """
    records: List[OrganRecord] = []
    records.append(register_organ(
        "writer_documents",
        truth_label="SIFTA_STIGMERGIC_WRITER_MEMORY_V1",
        truth_boundary="Counts saved Writer documents (*.sifta.md) on disk.",
        ledger_path=".sifta_documents/",
        claim_template="I have written {value} documents in my Writer.",
        verifier_kind="WRITER_DOC_COUNT",
        probe_module="System.swarm_organ_directory",
        probe_callable="probe_writer_doc_count",
        state_dir=state_dir, write=False,
    ))
    records.append(register_organ(
        "latent_world_model",
        truth_label="SIFTA_LATENT_WORLD_MODEL_V1",
        truth_boundary="Receipt-trained Markov transition table + Bellman values.",
        ledger_path=".sifta_state/latent_world_model.json",
        claim_template="I have {value} transitions in my latent world model.",
        verifier_kind="LATENT_TRANSITION_COUNT",
        probe_module="System.swarm_organ_directory",
        probe_callable="probe_latent_transition_count",
        state_dir=state_dir, write=False,
    ))
    records.append(register_organ(
        "first_person_journal",
        truth_label="ALICE_FIRST_PERSON_WITNESS_V1",
        truth_boundary="Append-only first-person journal of every interaction.",
        ledger_path=".sifta_state/alice_first_person_journal.jsonl",
        claim_template="My first-person journal has {value} rows.",
        verifier_kind="JOURNAL_ROW_COUNT",
        probe_module="System.swarm_organ_directory",
        probe_callable="probe_journal_row_count",
        state_dir=state_dir, write=False,
    ))
    records.append(register_organ(
        "wall_clock",
        truth_label="HARDWARE_TIME_ORACLE_V1",
        truth_boundary="OS wall clock — same physics as the architect's clock.",
        ledger_path="(in-process: time.localtime)",
        claim_template="I see today is {value}.",
        verifier_kind="TODAY_DATE",
        probe_module="System.swarm_organ_directory",
        probe_callable="probe_today_date",
        state_dir=state_dir, write=False,
    ))
    records.append(register_organ(
        "stgm_memory_wallet",
        truth_label="SIFTA_STGM_MEMORY_REWARDS_V1",
        truth_boundary="Sum of mint amounts in stgm_memory_rewards.jsonl.",
        ledger_path=".sifta_state/stgm_memory_rewards.jsonl",
        claim_template="My STGM memory wallet sum is {value}.",
        verifier_kind="STGM_BALANCE",
        probe_module="System.swarm_organ_directory",
        probe_callable="probe_stgm_balance",
        state_dir=state_dir, write=False,
    ))
    records.append(register_organ(
        "two_turn_receipt_gate",
        truth_label="SIFTA_TWO_TURN_RECEIPT_GATE_V1",
        truth_boundary="Append-only receipts that gate Turn N+1 on Turn N.",
        ledger_path=".sifta_state/two_turn_receipts.jsonl",
        claim_template="I have {value} two-turn receipt rows on disk.",
        verifier_kind="TWO_TURN_RECEIPT_COUNT",
        probe_module="System.swarm_organ_directory",
        probe_callable="probe_two_turn_receipt_count",
        state_dir=state_dir, write=False,
    ))
    records.append(register_organ(
        "relational_steering",
        truth_label="SIFTA_RELATIONAL_STEERING_V1",
        truth_boundary="Pre-cortex RELATIONAL_ACK / CO_PRESENT route receipts.",
        ledger_path=".sifta_state/relational_steering.jsonl",
        claim_template="I have {value} relational-steering receipts.",
        verifier_kind="RELATIONAL_STEERING_COUNT",
        probe_module="System.swarm_organ_directory",
        probe_callable="probe_relational_steering_count",
        state_dir=state_dir, write=False,
    ))
    _save_directory(state_dir=state_dir)
    return records


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--register-defaults", action="store_true")
    p.add_argument("--list", action="store_true")
    p.add_argument("--walk", action="store_true")
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()

    if args.register_defaults:
        records = register_default_organs()
        print(f"Registered {len(records)} default organs.")
        for r in records:
            print(f"  - {r.name:25s} verifier={r.verifier_kind or '-'}")

    if args.list:
        for r in list_organs():
            print(f"{r.name:25s} {r.truth_label:35s} {r.verifier_kind or '-':25s} {r.ledger_path}")

    if args.walk:
        out = walk_and_self_eval(write=not args.no_write)
        print(f"ORGAN_COUNT:       {out['organ_count']}")
        print(f"EVALUATED:         {out['evaluated_count']}")
        print(f"SKIPPED:           {out['skipped_count']}")
        print(f"STGM_MINTED_TOTAL: {out['stgm_minted_total']}")
        for r in out["results"]:
            if r.get("skipped"):
                print(f"  -- {r['organ']:25s} SKIPPED: {r['reason']}")
            else:
                print(f"  -- {r['organ']:25s} {r['truth_class']:12s} mint={r['stgm_minted']:.3f} | {r['claim_text']}")
        print(f"SHA: {out['sha256'][:16]}")
