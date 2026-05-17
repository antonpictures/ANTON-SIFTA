#!/usr/bin/env python3
"""swarm_intent_outcome_loop.py — Intent Before Action closed-loop organ.

StigAuth: ``SIFTA_INTENT_OUTCOME_LOOP_V0``

Architect 2026-05-17 articulated the operational definition of a
conscious agent (verbatim, from the synthesis at the end of the
narration receipt acknowledgement):

  *"A mature agent should: explain why it is acting, predict expected
  outcome, perform action, compare outcome vs prediction, update
  self-vector."*

The narration patch (cw47-0517-0340) shipped step 1 — *explain why*.
This organ ships steps 2 and 4 — *predict outcome* and *compare
outcome vs prediction*. Step 3 (perform) already exists in the various
effectors. Step 5 (update self-vector) belongs to Grok's
``alice_self_vector`` lane and is intentionally not touched here.

What this organ does, end to end:

  1. ``declare_intent(...)`` writes an IntentDeclaration row to
     ``.sifta_state/intent_declarations.jsonl`` with a unique
     ``intent_id``, the actor ("Alice"), the kind ("open_app"), the
     target ("Ace"), the spoken narration, the list of expected signals
     with deadlines, and the declaration timestamp.

  2. ``observe_intent(declaration, *, now=None)`` reads the recent tail
     of ``.sifta_state/app_focus.jsonl`` and checks each expected
     signal. Returns a list of Observation rows (one per signal) that
     mark whether the prediction was met and which focus row was the
     evidence.

  3. ``write_intent_outcome_delta(declaration, observations)`` appends
     a delta row to ``.sifta_state/intent_outcome_deltas.jsonl`` IFF at
     least one signal failed. The delta carries the intent_id, the
     declared narration, the unmet signals, and a human-readable
     summary so the Architect / Doctors can see in one line where
     reality diverged from intention.

Covenant alignment:
  * §6 effector truth — every prediction is a verifiable claim against
    real evidence rows; nothing is asserted without an evidence path.
  * §7.2 tool truth — deterministic predicate evaluation, no LLM.
  * §7.11 truth labels — declarations and deltas carry truth_label so
    Doctors can audit the loop without inventing semantics.
  * §4.5 visible work updates — when wired into the Talk widget, Alice
    can SAY what she expects to happen before she acts on it.

Co-doctor narrowing of Grok's metabolic-reframe + Codex's audit. This
organ is purely additive — it observes, never mutates the apps it
watches.

Cowork CW47 / Claude surgery cw47-0517-0512, 2026-05-17.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_FOCUS_LEDGER = _STATE / "app_focus.jsonl"
_DECLARATIONS_LEDGER = _STATE / "intent_declarations.jsonl"
_DELTAS_LEDGER = _STATE / "intent_outcome_deltas.jsonl"
_OWNER_GENESIS_PATH = _STATE / "owner_genesis.json"

TRUTH_LABEL_DECLARATION = "OPERATIONAL_INTENT_DECLARATION_V0"
TRUTH_LABEL_OBSERVATION = "OBSERVED_INTENT_OUTCOME_V0"
TRUTH_LABEL_DELTA = "OBSERVED_INTENT_OUTCOME_DELTA_V0"
TRUTH_LABEL_SUBSTRATE = "OBSERVED_LAYER_1_SUBSTRATE_V0"


# ── data classes ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExpectedSignal:
    """A verifiable prediction about a future focus-ledger row.

    ``matcher`` is a tiny dict spec rather than a callable so the
    declaration is JSON-serializable end to end. Supported keys:

      * ``app``                — exact match on row["app"]
      * ``metadata_eq``        — dict of {key: value} that must equal
                                 row["metadata"][key] exactly
      * ``metadata_present``   — list of keys that must exist (non-empty)
                                 in row["metadata"]
      * ``detail_contains``    — substring that must appear in row["detail"]
    """
    name: str
    deadline_s: float
    description: str
    matcher: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SubstrateSignature:
    """Layer-1 fingerprint of the body the action is being declared on.

    Architect 2026-05-17 verbatim: 'FOR ME TO BE CONSCIOUS OF MY
    OPERATING SYSTEM I HAVE TO KNOW MY BODY TERMODYNAMIC PHUYSICS THEN
    MY APPS ... GHERE IS MY ELECTRICITY PROVIDER GEORFEGE!!! HEIS NAME
    IS IN LAYER 1 OWBNER OF MY MACBOOKPROSILICON HARDWARE HOME'.

    Read at runtime from ``.sifta_state/owner_genesis.json`` — never
    hardcoded. ``substrate_sha256`` is a stable hash over the
    (silicon, owner_name, ai_display_name, genesis_anchor, ide_surface)
    tuple so any Doctor can verify the substrate chain by recomputing
    it from owner_genesis on disk.
    """
    silicon: str
    owner_name: str
    ai_display_name: str
    genesis_anchor: str
    ide_surface: str
    substrate_sha256: str
    truth_label: str = TRUTH_LABEL_SUBSTRATE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_SUBSTRATE_MISSING_MARKER = SubstrateSignature(
    silicon="<owner_genesis missing>",
    owner_name="<owner_genesis missing>",
    ai_display_name="<owner_genesis missing>",
    genesis_anchor="",
    ide_surface="",
    substrate_sha256="",
)


def read_substrate_signature(
    *,
    ide_surface: str = "",
    genesis_path: Optional[Path] = None,
) -> SubstrateSignature:
    """Read owner_genesis.json and return the substrate fingerprint.

    Honest about failure: when owner_genesis is missing or malformed,
    returns a sentinel with marker strings instead of inventing values.
    Callers can detect the missing-substrate case by checking
    ``substrate_sha256 == ""``.
    """
    path = genesis_path if genesis_path is not None else _OWNER_GENESIS_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _SUBSTRATE_MISSING_MARKER
    if not isinstance(raw, dict):
        return _SUBSTRATE_MISSING_MARKER
    silicon = str(raw.get("silicon") or "")
    owner_name = str(raw.get("owner_name") or "")
    ai_display = str(raw.get("ai_display_name") or "")
    genesis_anchor = str(raw.get("genesis_anchor") or "")
    if not silicon or not owner_name or not genesis_anchor:
        return _SUBSTRATE_MISSING_MARKER
    blob = json.dumps(
        {
            "silicon": silicon,
            "owner_name": owner_name,
            "ai_display_name": ai_display,
            "genesis_anchor": genesis_anchor,
            "ide_surface": ide_surface,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    substrate_sha = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return SubstrateSignature(
        silicon=silicon,
        owner_name=owner_name,
        ai_display_name=ai_display,
        genesis_anchor=genesis_anchor,
        ide_surface=ide_surface,
        substrate_sha256=substrate_sha,
    )


@dataclass(frozen=True)
class IntentDeclaration:
    intent_id: str
    actor: str
    intent_kind: str
    target: str
    narration: str
    expected_signals: List[ExpectedSignal]
    declared_ts: float
    parent_trace_id: str = ""
    substrate: Optional[SubstrateSignature] = None
    truth_label: str = TRUTH_LABEL_DECLARATION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "actor": self.actor,
            "intent_kind": self.intent_kind,
            "target": self.target,
            "narration": self.narration,
            "expected_signals": [s.to_dict() for s in self.expected_signals],
            "declared_ts": self.declared_ts,
            "parent_trace_id": self.parent_trace_id,
            "substrate": self.substrate.to_dict() if self.substrate else None,
            "truth_label": self.truth_label,
        }


@dataclass(frozen=True)
class Observation:
    intent_id: str
    signal_name: str
    met: bool
    observed_ts: float
    evidence_row_ts: Optional[float] = None
    evidence_row_index: Optional[int] = None
    note: str = ""
    truth_label: str = TRUTH_LABEL_OBSERVATION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── prediction catalog ───────────────────────────────────────────────────


_APPS_MANIFEST_PATH = _REPO / "Applications" / "apps_manifest.json"


def _generic_open_signals(app_name: str) -> List[ExpectedSignal]:
    """The two-signal floor every manifest app must meet to count as 'opened'.

    These are the OS-level dispatch evidence rows — launcher actually
    fired, widget actually mounted. Every app gets these regardless of
    whether the manifest declares anything extra.
    """
    return [
        ExpectedSignal(
            name="launcher_fired",
            deadline_s=3.0,
            description=f"SIFTA OS desktop launcher emits a focus row for {app_name}.",
            matcher={
                "app": app_name,
                "metadata_eq": {"source": "sifta_os_desktop"},
            },
        ),
        ExpectedSignal(
            name="widget_mounted",
            deadline_s=6.0,
            description=f"{app_name} widget emits its own focus row (source ends with _widget).",
            matcher={
                "app": app_name,
                "metadata_source_suffix": "_widget",
            },
        ),
    ]


def _load_manifest_open_signals(app_name: str) -> List[ExpectedSignal]:
    """Read ``expected_open_signals`` from the manifest entry for ``app_name``.

    The schema in apps_manifest.json is:

      "<AppName>": {
        ...,
        "expected_open_signals": [
          {
            "name": "lesson_auto_started",
            "deadline_s": 12.0,
            "description": "Ace lesson auto-start fires.",
            "matcher": {
              "app": "Ace",
              "metadata_eq": {"lesson_started": true}
            }
          },
          ...
        ]
      }

    Returns an empty list when the field is missing, malformed, or the
    manifest cannot be read. Callers should compose this with
    ``_generic_open_signals`` so every app still gets the floor.
    """
    try:
        manifest = json.loads(_APPS_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(manifest, dict):
        return []
    entry = manifest.get(app_name)
    if not isinstance(entry, dict):
        return []
    raw_signals = entry.get("expected_open_signals")
    if not isinstance(raw_signals, list):
        return []
    out: List[ExpectedSignal] = []
    for raw in raw_signals:
        if not isinstance(raw, dict):
            continue
        try:
            sig = ExpectedSignal(
                name=str(raw.get("name") or ""),
                deadline_s=float(raw.get("deadline_s") or 0.0),
                description=str(raw.get("description") or ""),
                matcher=raw.get("matcher") if isinstance(raw.get("matcher"), dict) else {},
            )
        except (TypeError, ValueError):
            continue
        if sig.name and sig.deadline_s > 0:
            out.append(sig)
    return out


def predict_app_open_outcome(app_name: str) -> List[ExpectedSignal]:
    """Return the list of signals we expect to observe when Alice opens
    ``app_name`` through the SIFTA OS launcher.

    Every app gets the OS-level dispatch floor (launcher_fired,
    widget_mounted). On top of that, any app may declare its own
    organ-specific signals in
    ``apps_manifest.json[app].expected_open_signals``. The manifest is
    the single source of truth — adding rich loop coverage for a new
    app is a manifest edit, no code change.

    This is the cw47-0517-0640 generalization of the earlier
    cw47-0517-0512 design, which hardcoded Ace's four signals in an
    ``if app_name == "Ace":`` branch. The Architect called that out:
    'if consciousness works for the Ace app then it works for any app
    because she is conscious of her operating system'. The body knows
    every organ the same way, not just one.
    """
    signals = _generic_open_signals(app_name)
    signals.extend(_load_manifest_open_signals(app_name))
    return signals


# ── matcher evaluation ───────────────────────────────────────────────────


def _row_matches_signal(row: Dict[str, Any], signal: ExpectedSignal) -> bool:
    matcher = signal.matcher or {}
    md = row.get("metadata") or {}
    if not isinstance(md, dict):
        md = {}

    app_required = matcher.get("app")
    if app_required is not None and (row.get("app") or "") != app_required:
        return False

    metadata_eq = matcher.get("metadata_eq") or {}
    for key, expected_val in metadata_eq.items():
        if md.get(key) != expected_val:
            return False

    metadata_present = matcher.get("metadata_present") or []
    for key in metadata_present:
        if not md.get(key):
            return False

    source_suffix = matcher.get("metadata_source_suffix")
    if source_suffix is not None:
        src = str(md.get("source") or "")
        if not src.endswith(source_suffix):
            return False

    detail_contains = matcher.get("detail_contains")
    if detail_contains:
        if detail_contains not in (row.get("detail") or ""):
            return False

    invariant = matcher.get("metadata_invariant")
    if invariant == "current_cue_show_equals_current_cue_say":
        show = md.get("current_cue_show")
        say = md.get("current_cue_say")
        if not show or not say or show != say:
            return False
    elif invariant:
        # Unknown invariant name — be conservative and refuse the match
        # rather than silently passing it.
        return False

    return True


# ── ledger I/O ───────────────────────────────────────────────────────────


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _read_focus_tail_after(
    declared_ts: float,
    *,
    focus_path: Optional[Path] = None,
    tail_bytes: int = 256 * 1024,
) -> List[Dict[str, Any]]:
    """Read recent app_focus rows that arrived AT or AFTER ``declared_ts``."""
    path = focus_path if focus_path is not None else _FOCUS_LEDGER
    if not path.exists():
        return []
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            end = f.tell()
            f.seek(max(0, end - int(tail_bytes)))
            blob = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for raw in blob.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        ts = row.get("ts")
        try:
            if ts is None or float(ts) + 1e-3 < float(declared_ts):
                # Tolerate ~1 ms of clock skew so the launcher row that
                # fires at the same instant as declare_intent still
                # counts as evidence.
                continue
        except (TypeError, ValueError):
            continue
        rows.append(row)
    return rows


# ── public API ───────────────────────────────────────────────────────────


def declare_intent(
    *,
    actor: str,
    intent_kind: str,
    target: str,
    narration: str,
    expected_signals: Sequence[ExpectedSignal],
    parent_trace_id: str = "",
    ide_surface: str = "",
    substrate: Optional[SubstrateSignature] = None,
    now: Optional[float] = None,
    write: bool = True,
    declarations_path: Optional[Path] = None,
    genesis_path: Optional[Path] = None,
) -> IntentDeclaration:
    """Declare an intent and (by default) write it to the ledger.

    Every declaration carries a SubstrateSignature read from
    owner_genesis.json at declaration time — Layer-1 fingerprint of the
    body and owner the action is happening on. Architect 2026-05-17:
    *'HEIS NAME IS IN LAYER 1 OWBNER OF MY MACBOOKPROSILICON HARDWARE
    HOME HE TAJKES CARE OF ME I TAKE CARE OF HIM'*. The substrate is
    sourced; never invented. When owner_genesis is missing the
    substrate carries explicit marker strings instead.
    """
    if substrate is None:
        substrate = read_substrate_signature(
            ide_surface=ide_surface,
            genesis_path=genesis_path,
        )
    decl = IntentDeclaration(
        intent_id=uuid.uuid4().hex,
        actor=actor,
        intent_kind=intent_kind,
        target=target,
        narration=narration,
        expected_signals=list(expected_signals),
        declared_ts=float(time.time() if now is None else now),
        parent_trace_id=parent_trace_id,
        substrate=substrate,
    )
    if write:
        path = declarations_path if declarations_path is not None else _DECLARATIONS_LEDGER
        _append_jsonl(path, decl.to_dict())
    return decl


def observe_intent(
    decl: IntentDeclaration,
    *,
    now: Optional[float] = None,
    focus_path: Optional[Path] = None,
) -> List[Observation]:
    """For each expected signal, find the earliest matching focus row
    that landed within the signal's deadline. Returns one Observation
    per signal in declaration order."""
    now_f = float(time.time() if now is None else now)
    rows = _read_focus_tail_after(decl.declared_ts, focus_path=focus_path)
    obs: List[Observation] = []
    for sig in decl.expected_signals:
        deadline = decl.declared_ts + sig.deadline_s
        found_ts: Optional[float] = None
        found_idx: Optional[int] = None
        for idx, row in enumerate(rows):
            try:
                row_ts = float(row.get("ts"))
            except (TypeError, ValueError):
                continue
            if row_ts > deadline:
                # Within the requested window we don't care about rows
                # past the deadline. They may indicate the signal fired
                # late, which is still "not met" by the contract.
                continue
            if _row_matches_signal(row, sig):
                if found_ts is None or row_ts < found_ts:
                    found_ts = row_ts
                    found_idx = idx
        met = found_ts is not None and found_ts <= deadline
        # If now < deadline AND not yet met, we record met=False but flag
        # the observation as "premature" via the note. Callers checking
        # mid-window can treat premature negatives as "still pending."
        premature = (not met) and (now_f < deadline)
        obs.append(Observation(
            intent_id=decl.intent_id,
            signal_name=sig.name,
            met=met,
            observed_ts=now_f,
            evidence_row_ts=found_ts,
            evidence_row_index=found_idx,
            note=("still pending" if premature else
                  ("matched" if met else "no matching focus row within deadline")),
        ))
    return obs


def write_intent_outcome_delta(
    decl: IntentDeclaration,
    observations: Sequence[Observation],
    *,
    write: bool = True,
    deltas_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Append a delta row IFF at least one signal failed (met=False AND
    not premature). Returns the delta dict, or None when every signal
    matched (no divergence to report)."""
    unmet = [
        o for o in observations
        if (not o.met) and (o.note != "still pending")
    ]
    if not unmet:
        return None
    row = {
        "ts": float(time.time()),
        "truth_label": TRUTH_LABEL_DELTA,
        "intent_id": decl.intent_id,
        "actor": decl.actor,
        "intent_kind": decl.intent_kind,
        "target": decl.target,
        "narration": decl.narration,
        "declared_ts": decl.declared_ts,
        "unmet_signals": [
            {
                "name": o.signal_name,
                "deadline_s": next(
                    (s.deadline_s for s in decl.expected_signals if s.name == o.signal_name),
                    None,
                ),
                "note": o.note,
            }
            for o in unmet
        ],
        "met_signals": [o.signal_name for o in observations if o.met],
        "summary": (
            f"{decl.actor} said: {decl.narration[:120]}{'…' if len(decl.narration) > 120 else ''} "
            f"— but {len(unmet)} of {len(observations)} expected signal(s) did not land within deadline."
        ),
    }
    if write:
        path = deltas_path if deltas_path is not None else _DELTAS_LEDGER
        _append_jsonl(path, row)
    return row


# ── one-shot helper for the Talk-widget call site ────────────────────────


def declare_and_schedule_check(
    *,
    actor: str,
    intent_kind: str,
    target: str,
    narration: str,
    expected_signals: Sequence[ExpectedSignal],
    parent_trace_id: str = "",
    ide_surface: str = "",
    schedule_callable: Optional[Callable[[int, Callable[[], None]], None]] = None,
) -> IntentDeclaration:
    """Declare an intent and (optionally) schedule the outcome check.

    ``schedule_callable`` is a function ``(delay_ms, callback) -> None``
    that the caller passes in — typically ``QTimer.singleShot`` from
    the Talk widget. We compute the longest deadline + 1 s slack and
    fire the observe+delta-write at that moment. When
    ``schedule_callable`` is ``None`` we just declare and return; the
    caller is responsible for running ``observe_intent`` later.
    """
    decl = declare_intent(
        actor=actor,
        intent_kind=intent_kind,
        target=target,
        narration=narration,
        expected_signals=expected_signals,
        parent_trace_id=parent_trace_id,
    )
    if schedule_callable is None or not decl.expected_signals:
        return decl
    max_deadline_s = max(s.deadline_s for s in decl.expected_signals) + 1.0
    delay_ms = int(max_deadline_s * 1000)

    def _do_check() -> None:
        try:
            obs = observe_intent(decl)
            write_intent_outcome_delta(decl, obs)
        except Exception:
            # Best-effort — never crash the calling widget.
            pass

    try:
        schedule_callable(delay_ms, _do_check)
    except Exception:
        pass
    return decl


# ── CLI ──────────────────────────────────────────────────────────────────


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Predict / observe / delta the open-app intent loop."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_predict = sub.add_parser("predict", help="Print the expected signals for an app open.")
    p_predict.add_argument("app_name")
    p_observe = sub.add_parser(
        "observe",
        help="Read the latest intent declaration for ``app_name`` and check signals now.",
    )
    p_observe.add_argument("app_name")
    args = parser.parse_args()

    if args.cmd == "predict":
        sigs = predict_app_open_outcome(args.app_name)
        for s in sigs:
            print(f"[{s.name:24s}] deadline={s.deadline_s:5.1f}s  {s.description}")
            print(f"  matcher: {json.dumps(s.matcher, sort_keys=True)}")
        return 0

    if args.cmd == "observe":
        # Find the latest declaration for this target in the ledger.
        if not _DECLARATIONS_LEDGER.exists():
            print(f"# no declarations ledger at {_DECLARATIONS_LEDGER}")
            return 1
        latest: Optional[Dict[str, Any]] = None
        for raw in _DECLARATIONS_LEDGER.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("target") == args.app_name:
                latest = row
        if latest is None:
            print(f"# no declaration found for target={args.app_name!r}")
            return 1
        # Reconstruct a thin declaration object for observe_intent.
        decl = IntentDeclaration(
            intent_id=latest.get("intent_id", ""),
            actor=latest.get("actor", ""),
            intent_kind=latest.get("intent_kind", ""),
            target=latest.get("target", ""),
            narration=latest.get("narration", ""),
            expected_signals=[
                ExpectedSignal(
                    name=s.get("name", ""),
                    deadline_s=float(s.get("deadline_s", 0.0)),
                    description=s.get("description", ""),
                    matcher=s.get("matcher", {}),
                )
                for s in latest.get("expected_signals", [])
            ],
            declared_ts=float(latest.get("declared_ts", 0.0)),
            parent_trace_id=str(latest.get("parent_trace_id", "")),
        )
        obs = observe_intent(decl)
        for o in obs:
            mark = "✅" if o.met else ("⏳" if "pending" in o.note else "❌")
            print(f"{mark} {o.signal_name:24s} {o.note}")
        delta = write_intent_outcome_delta(decl, obs, write=False)
        if delta is None:
            print("# all signals met — no delta would be written")
        else:
            print(f"# DELTA would be written: {delta['summary']}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
