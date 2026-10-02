"""Trace consult — read the field before re-deriving it.

Owner's design intent (George, 2026-09-30):

    "we are supposed to be stigmergic agi organism ... in the beginning thats
     how I thought I solve using less tokens because of the stigmergic traces"

That intent has a failure mode this organ exists to remove. Traces are only
cheap if something READS them. An arm that greps, probes and re-derives pays
the full price again every time, and the body gets no cheaper as it learns -
which is the opposite of stigmergy.

The concrete failure this was built from: the body already contained, in plain
docstrings, the exact rules that were later violated -

  * ``ledger_balance``: "SINGLE SOURCE OF TRUTH ... Any double-spend guard MUST
    call this function rather than ... trusting the stgm_balance field"
  * ``wallet_file_claims``: wallet files are "cache evidence, not spendable truth"

Both were discoverable in seconds. Both were missed, and the cost was a wrong
genesis and a 300-second timeout on a 128 MB ledger replay.

So this organ indexes AUTHORITY TRACES: the sentences in the body that say what
is canonical, what must be called, and what must never be trusted. ``consult()``
routes an intent to its owning organ and returns those sentences FIRST, so an arm
reads the doctrine before it writes the code.

Every consultation is recorded, so a repeated question becomes visible as a
stigmergic trace instead of being re-derived.

Ledger: TRACE_CONSULT_LEDGER
"""

from __future__ import annotations

import ast
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

TRACE_CONSULT_LEDGER = "trace_consult_ledger.jsonl"
TRACE_AUTHORITY_INDEX = "trace_authority_index.json"
TRUTH_LABEL = "TRACE_CONSULT_V1"

# Sentences that mark authority. These are the pheromone marks an arm must find
# before writing code, because they encode decisions already made.
AUTHORITY_MARKERS = (
    r"single source of truth",
    r"\bcanonical\b",
    r"\bmust (?:call|use|not|never)\b",
    r"\bnever (?:trust|mutate|edit|delete|guess)\b",
    r"\bdo not (?:trust|guess|read|edit)\b",
    r"\bnot spendable\b",
    r"\bcache evidence\b",
    r"\bauthoritative\b",
    r"\bowner directive\b",
    r"\bdo not assimilate\b",
    r"\brefuse\b",
)
_MARKER_RE = re.compile("|".join(AUTHORITY_MARKERS), re.IGNORECASE)

# Scanning every organ is too slow to do inline; the index is built once and
# refreshed on demand.
SCAN_DIRS = ("System", "Kernel")


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _docstrings_and_comments(path: Path) -> list[tuple[int, str]]:
    """Every docstring and comment line, with its line number."""
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    out: list[tuple[int, str]] = []
    for lineno, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#") and len(stripped) > 3:
            out.append((lineno, stripped.lstrip("# ").strip()))
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node)
            if doc:
                out.append((getattr(node, "lineno", 0), doc))
    return out


def build_authority_index(
    *,
    state_dir: Path | str | None = None,
    dirs: Iterable[str] = SCAN_DIRS,
) -> dict[str, Any]:
    """Index every sentence in the body that asserts authority."""
    sd = _state_dir(state_dir)
    traces: list[dict[str, Any]] = []
    scanned = 0
    for d in dirs:
        root = _REPO / d
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.py")):
            scanned += 1
            for lineno, text in _docstrings_and_comments(path):
                for sentence in re.split(r"(?<=[.;:])\s+|\n+", text):
                    sentence = sentence.strip()
                    if not sentence or not _MARKER_RE.search(sentence):
                        continue
                    traces.append({
                        "module": path.stem,
                        "path": f"{d}/{path.name}",
                        "line": lineno,
                        "sentence": sentence[:400],
                    })
    index = {
        "ts": time.time(),
        "modules_scanned": scanned,
        "traces": traces,
        "count": len(traces),
        "truth_label": TRUTH_LABEL,
    }
    sd.mkdir(parents=True, exist_ok=True)
    (sd / TRACE_AUTHORITY_INDEX).write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return index


def load_authority_index(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    path = _state_dir(state_dir) / TRACE_AUTHORITY_INDEX
    if not path.exists():
        return build_authority_index(state_dir=state_dir)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return build_authority_index(state_dir=state_dir)


def records(*, state_dir: Path | str | None = None) -> list[dict[str, Any]]:
    path = _state_dir(state_dir) / TRACE_CONSULT_LEDGER
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


_WORD = re.compile(r"[a-z0-9_]+")


def _score(intent: str, trace: dict[str, Any]) -> int:
    words = set(_WORD.findall(intent.casefold()))
    hay = f"{trace['module']} {trace['sentence']}".casefold()
    return sum(1 for w in words if len(w) > 2 and w in hay)


def consult(
    intent: str,
    *,
    limit: int = 6,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Answer an intent with the authoritative organ AND its own rules.

    Returns the owning organs from the canonical registry plus the authority
    sentences that matched, so an arm reads the decided doctrine before it
    writes anything. The result is logged as a stigmergic trace.
    """
    sd = _state_dir(state_dir)
    index = load_authority_index(state_dir=sd)

    scored = [(t, _score(intent, t)) for t in index.get("traces", [])]
    scored = [(t, s) for t, s in scored if s > 0]
    scored.sort(key=lambda pair: (-pair[1], pair[0]["path"]))

    owners: list[dict[str, Any]] = []
    try:
        from System.swarm_canonical_organ_registry import route_query

        for row in route_query(intent, include_dynamic=True, limit=limit).get("matches", []):
            owners.append({
                "organ_id": row.get("organ_id"),
                "score": round(float(row.get("score") or 0.0), 2),
                "paths": list(row.get("organ_paths") or []),
                "ledgers": list(row.get("ledgers") or []),
            })
    except Exception as exc:  # routing is helpful, not required
        owners.append({"error": f"{type(exc).__name__}: {exc}"})

    row = {
        "ts": time.time(),
        "kind": "TRACE_CONSULT",
        "intent": intent,
        "owners": owners,
        "authority_traces": [t for t, _ in scored[:limit]],
        "index_count": index.get("count"),
        "truth_label": TRUTH_LABEL,
    }
    path = sd / TRACE_CONSULT_LEDGER
    sd.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def render(result: dict[str, Any]) -> str:
    """Compact readout: doctrine first, then owners."""
    lines = [f"intent: {result['intent']}", "", "AUTHORITY (read before writing code):"]
    traces = result.get("authority_traces") or []
    if not traces:
        lines.append("  (no authority trace matched - the rule may not be written down yet)")
    for t in traces:
        lines.append(f"  {t['path']}:{t['line']}  {t['sentence'][:220]}")
    lines.append("")
    lines.append("OWNING ORGANS:")
    for o in result.get("owners") or []:
        lines.append(f"  {o.get('organ_id')}  score={o.get('score')}  {o.get('paths') or ''}")
    return "\n".join(lines)


def selftest() -> dict[str, Any]:
    """Prove the organ would have caught the two rules that were actually violated."""
    index = build_authority_index()

    def retrieves(intent: str, expected_path: str, expected_text: str) -> bool:
        """A known rule must come back as the TOP trace for its intent."""
        r = consult(intent)
        traces = r.get("authority_traces") or []
        return bool(traces) and (
            traces[0]["path"] == expected_path
            and expected_text.casefold() in traces[0]["sentence"].casefold()
        )

    checks = {
        "index_built": index["count"] > 0,
        "index_is_substantial": index["count"] >= 20,
        # The two rules that were ACTUALLY violated in this body, pinned:
        "finds_the_balance_authority_rule": retrieves(
            "which is the single source of truth for true STGM spendable balance ledger",
            "Kernel/inference_economy.py",
            "single source of truth",
        ),
        "finds_the_cache_evidence_rule": retrieves(
            "are wallet file claims spendable truth or cache evidence",
            "System/stgm_economy.py",
            "cache evidence",
        ),
        "consult_logged": bool(records()),
        "readout_is_cheap": len(render(consult("stgm balance"))) < 4000,
    }
    return {"ok": all(checks.values()), "checks": checks,
            "index_traces": index["count"], "modules_scanned": index["modules_scanned"],
            "truth_label": TRUTH_LABEL}


def main(argv: Iterable[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args[0] == "selftest":
        print(json.dumps(selftest(), indent=2))
        return 0
    if args[0] == "index":
        idx = build_authority_index()
        print(json.dumps({k: v for k, v in idx.items() if k != "traces"}, indent=2))
        return 0
    if args[0] == "consult":
        intent = " ".join(args[1:]) or "how does the economy work"
        print(render(consult(intent)))
        return 0
    if args[0] == "log":
        print(json.dumps(records()[-10:], indent=2, ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
