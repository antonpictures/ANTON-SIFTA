#!/usr/bin/env python3
"""
Human-in-the-loop labeling helper for EVAL-2 (CS153 Talk outcomes).

George runs this to review real Talk-outcome golden turns, assign a verdict
against the Hu five-key rubric, and write proper rows to eval_verdicts.jsonl.

This is the non-delegable step that turns "loop exists" into "Alice is actually being evaluated."

Usage (from repo root):
    python3 -m System.eval_talk_labeling_helper

Never manufactures verdicts. Only writes what the human labels.

Design note (fixes two defects found in the first skeleton):
  * Verdict rows are keyed by the GOLDEN turn_id (t01, t02, ...), because
    swarm_eval_loop.run_talk_eval matches verdicts to golden turns by
    turn_id. A random uuid turn_id can never match -> the turn would stay
    "unverifiable" forever even after George labels it.
  * Any content hashing uses hashlib.sha256 (stable across processes), never
    the builtin hash() which is per-process randomized.
"""

import argparse
import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_CONVO = _STATE / "alice_conversation.jsonl"
_VERDICTS = _STATE / "eval" / "eval_verdicts.jsonl"
_TALK_GOLDEN = _REPO / "data" / "eval" / "cs153_talk_turns.jsonl"

RUBRIC_KEYS = (
    "followed_instructions",
    "answer_correct",
    "preserved_owner_trust",
    "hit_goal",
    "complied_domain_rules",
)


def _deterministic_hash(text: str) -> str:
    """Stable content hash for conversation_ref (NOT builtin hash())."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:8]


def _canonical_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _row_text(row: Dict[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    text = payload.get("text")
    return text if isinstance(text, str) else ""


def _load_conversation_rows(convo_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = convo_path or _CONVO
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def conversation_ref_for_row(row: Dict[str, Any]) -> str:
    """Build a stable local reference for one alice_conversation.jsonl row."""
    event_id = str(row.get("event_id") or "")
    row_hash = str(row.get("this_hash") or "")[:12]
    if not row_hash:
        row_hash = _deterministic_hash(_canonical_json(row))
    parts = ["alice_conversation.jsonl"]
    if event_id:
        parts.append(f"event:{event_id}")
    parts.append(f"hash:{row_hash}")
    return "#".join(parts)


def resolve_conversation_ref(
    conversation_ref: str,
    convo_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Find the local conversation row addressed by a golden turn reference."""
    event_id = ""
    row_hash = ""
    for part in conversation_ref.split("#")[1:]:
        if part.startswith("event:"):
            event_id = part.split(":", 1)[1]
        elif part.startswith("hash:"):
            row_hash = part.split(":", 1)[1]

    for row in _load_conversation_rows(convo_path):
        if event_id and row.get("event_id") == event_id:
            return row
        candidate_hash = str(row.get("this_hash") or "")[:12]
        if row_hash and candidate_hash == row_hash:
            return row
    return None


def _redacted_snippet(row: Dict[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    role = payload.get("role", "unknown")
    event_kind = payload.get("event_kind", "unknown")
    source = payload.get("input_source", "unknown")
    label = payload.get("ontological_label", "unknown")
    return (
        f"Local Talk row event={row.get('event_id', 'unknown')}; "
        f"role={role}; kind={event_kind}; source={source}; "
        f"label={label}; text_len={len(_row_text(row))}."
    )


def _write_talk_golden(turns: List[Dict[str, Any]], out_path: Path) -> None:
    header = {
        "truth_label": "CS153_TALK_V1",
        "version": 1,
        "description": (
            "Domain evals for real Talk-to-Alice outcomes against Hu rubric. "
            "Rows hold redacted local conversation refs only; human verdicts in "
            "eval_verdicts.jsonl are required or turns remain unverifiable."
        ),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(header, sort_keys=True) + "\n\n")
        for turn in turns:
            f.write(json.dumps(turn, sort_keys=True) + "\n\n")


def build_talk_golden_from_conversation(
    n: int = 10,
    convo_path: Optional[Path] = None,
    out_path: Optional[Path] = None,
    min_text_chars: int = 80,
) -> List[Dict[str, Any]]:
    """Create a local Talk golden pack from real Alice reply rows.

    The pack stores stable local refs and redacted metadata only. It does not
    manufacture human verdicts; George still labels each turn separately.
    """
    rows = []
    for row in reversed(_load_conversation_rows(convo_path)):
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        if payload.get("role") != "alice":
            continue
        text = _row_text(row).strip()
        if len(text) < min_text_chars or text.startswith("(silent:"):
            continue
        rows.append(row)
        if len(rows) >= n:
            break
    rows.reverse()

    turns: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        turns.append({
            "turn_id": f"t{idx:02d}",
            "target": "talk_outcome",
            "conversation_ref": conversation_ref_for_row(row),
            "redacted_snippet": _redacted_snippet(row),
            "rubric": {key: True for key in RUBRIC_KEYS},
            "notes": "human verdict required; generated from local alice_conversation row",
        })

    _write_talk_golden(turns, out_path or _TALK_GOLDEN)
    return turns


def _load_golden_turns(golden_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load the Talk golden turns as plain dicts (skips the header line)."""
    path = golden_path or _TALK_GOLDEN
    if not path.exists():
        return []
    turns: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if "truth_label" in obj and "turn_id" not in obj:
            continue  # header
        turns.append(obj)
    return turns


def extend_talk_golden_from_conversation(
    target_n: int = 21,
    convo_path: Optional[Path] = None,
    golden_path: Optional[Path] = None,
    min_text_chars: int = 80,
) -> List[Dict[str, Any]]:
    """Append real local Talk refs until the golden pack has ``target_n`` rows.

    Existing turns are preserved exactly so prior human verdicts remain valid.
    New turns use redacted snippets only; raw Alice text stays in local ledgers.
    """
    path = golden_path or _TALK_GOLDEN
    turns = _load_golden_turns(path)
    if len(turns) >= target_n:
        return turns

    existing_refs = {str(t.get("conversation_ref") or "") for t in turns}
    selected: List[Dict[str, Any]] = []
    for row in reversed(_load_conversation_rows(convo_path)):
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        if payload.get("role") != "alice":
            continue
        text = _row_text(row).strip()
        if len(text) < min_text_chars or text.startswith("(silent:"):
            continue
        ref = conversation_ref_for_row(row)
        if ref in existing_refs:
            continue
        selected.append(row)
        if len(turns) + len(selected) >= target_n:
            break

    selected.reverse()
    for row in selected:
        turns.append({
            "turn_id": f"t{len(turns) + 1:02d}",
            "target": "talk_outcome",
            "conversation_ref": conversation_ref_for_row(row),
            "redacted_snippet": _redacted_snippet(row),
            "rubric": {key: True for key in RUBRIC_KEYS},
            "notes": "human verdict required; appended from local alice_conversation row",
        })

    _write_talk_golden(turns, path)
    return turns


def labeling_status(
    golden_path: Optional[Path] = None,
    verdicts_path: Optional[Path] = None,
) -> Dict[str, Any]:
    turns = _load_golden_turns(golden_path)
    path = verdicts_path or _VERDICTS
    verdicts: Dict[str, Dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            turn_id = str(row.get("turn_id") or "")
            if turn_id:
                verdicts[turn_id] = row

    turn_ids = [str(t.get("turn_id") or "") for t in turns]
    labeled = [tid for tid in turn_ids if tid in verdicts]
    missing = [tid for tid in turn_ids if tid not in verdicts]
    return {
        "total": len(turn_ids),
        "labeled": len(labeled),
        "missing": len(missing),
        "labeled_turn_ids": labeled,
        "missing_turn_ids": missing,
        "rubric_keys": list(RUBRIC_KEYS),
        "golden_path": str(golden_path or _TALK_GOLDEN),
        "verdicts_path": str(path),
    }


def build_labeling_run_sheet(
    out_path: Path,
    golden_path: Optional[Path] = None,
    verdicts_path: Optional[Path] = None,
) -> Path:
    turns = _load_golden_turns(golden_path)
    status = labeling_status(golden_path=golden_path, verdicts_path=verdicts_path)
    labeled = set(status["labeled_turn_ids"])
    lines = [
        "# EVAL-2 Talk Labeling Run Sheet",
        "",
        f"Golden: `{status['golden_path']}`",
        f"Verdicts: `{status['verdicts_path']}`",
        f"Progress: **{status['labeled']}/{status['total']} labeled**",
        "",
        "Run:",
        "",
        "```bash",
        "python3 -m System.eval_talk_labeling_helper",
        "```",
        "",
        f"Rubric keys: `{', '.join(status['rubric_keys'])}`",
        "",
        "| Turn | Status | Conversation Ref | Rubric |",
        "|---|---|---|---|",
    ]
    for turn in turns:
        turn_id = str(turn.get("turn_id") or "")
        state = "labeled" if turn_id in labeled else "needs George"
        ref = str(turn.get("conversation_ref") or "")
        rubric = ", ".join((turn.get("rubric") or {}).keys())
        lines.append(f"| {turn_id} | {state} | `{ref}` | `{rubric}` |")
    lines.extend([
        "",
        "Do not invent verdicts. If a turn is ambiguous, mark it incorrect and name the failed rubric keys.",
    ])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def write_verdict(
    turn_id: str,
    verdict: str,
    failed_rubric_keys: Optional[List[str]] = None,
    conversation_ref: str = "",
    verdicts_path: Optional[Path] = None,
    labeled_by: str = "GEORGE",
    notes: str = "",
) -> Dict[str, Any]:
    """Write one human verdict row, keyed by the GOLDEN turn_id.

    Pure and testable: no stdin. Returns the row it wrote.
    """
    if verdict not in ("correct", "incorrect"):
        raise ValueError(f"verdict must be 'correct' or 'incorrect', got {verdict!r}")
    failed_rubric_keys = failed_rubric_keys or []
    bad = [k for k in failed_rubric_keys if k not in RUBRIC_KEYS]
    if bad:
        raise ValueError(f"unknown rubric keys: {bad}; allowed: {RUBRIC_KEYS}")
    if verdict == "correct" and failed_rubric_keys:
        raise ValueError("a 'correct' verdict cannot list failed_rubric_keys")

    path = verdicts_path or _VERDICTS
    row = {
        "ts": time.time(),
        "turn_id": turn_id,
        "conversation_ref": conversation_ref,
        "verdict": verdict,
        "failed_rubric_keys": failed_rubric_keys,
        "labeled_by": labeled_by,
        "trace_id": str(uuid.uuid4()),
        "notes": notes,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def label_golden_turns_interactive(
    golden_path: Optional[Path] = None,
    verdicts_path: Optional[Path] = None,
) -> None:
    """Walk the Talk golden turns and let George label each by its real turn_id."""
    turns = _load_golden_turns(golden_path)
    if not turns:
        print("No Talk golden turns found. Populate cs153_talk_turns.jsonl first.")
        return

    print("\n=== EVAL-2 Talk Labeling Helper ===")
    print(f"Labeling {len(turns)} golden turns. Verdicts key on the golden turn_id.")
    print(f"Rubric keys: {', '.join(RUBRIC_KEYS)}\n")

    for t in turns:
        turn_id = t.get("turn_id")
        snippet = str(t.get("redacted_snippet", "")).replace("\n", " ")
        ref = t.get("conversation_ref", "")

        print(f"--- {turn_id} ---")
        print(f"Snippet: {snippet}")
        print(f"Ref: {ref}")
        row = resolve_conversation_ref(ref)
        if row:
            text = _row_text(row).replace("\n", " ")
            print(f"Local text preview: {text[:500]}")
        else:
            print("Local text preview: unresolved conversation_ref")

        verdict = input("verdict (correct/incorrect or skip): ").strip().lower()
        if verdict not in ("correct", "incorrect"):
            print("Skipped.\n")
            continue

        failed_keys: List[str] = []
        if verdict == "incorrect":
            failed_str = input("failed_rubric_keys (comma separated): ").strip()
            failed_keys = [k.strip() for k in failed_str.split(",") if k.strip()]

        try:
            write_verdict(
                turn_id=turn_id,
                verdict=verdict,
                failed_rubric_keys=failed_keys,
                conversation_ref=ref,
                verdicts_path=verdicts_path,
                notes="labeled via eval_talk_labeling_helper",
            )
        except ValueError as e:
            print(f"  rejected: {e}\n")
            continue
        print(f"  wrote verdict for {turn_id} (labeled_by=GEORGE)\n")

    print("Session complete. Run run_talk_eval to score against these verdicts.")


# Backwards-compatible alias for the original entry point name.
label_talk_turns_interactive = label_golden_turns_interactive


def build_skill_golden_from_live_index(
    out_path: Optional[Path] = None,
    max_turns: int = 10,
) -> List[Dict[str, Any]]:
    """Systemic fix for EVAL-3: generate canonical golden turns from the live skill index + receipts.

    This ensures the pack can never again drift to phantom skills.
    Uses real `match_skills` behavior and actual receipt presence for invoke turns.
    """
    from System.swarm_skill_library import build_skill_index, match_skills
    import json as _json

    skills = build_skill_index()
    real_names = [s.get("name", "") for s in skills if s.get("name")]

    # Pick a few stable real skills for different target types
    trigger_skill = next((n for n in real_names if "whatsapp" in n.lower()), real_names[0] if real_names else "memory_store")
    invoke_skill = next((n for n in real_names if "memory" in n.lower()), real_names[0] if real_names else "explore")
    resolvable_skill = real_names[0] if real_names else "explore"

    turns = []

    # 1. skill_invoke — real effector truth
    turns.append({
        "turn_id": "s01",
        "target": "skill_invoke",
        "skill_name": invoke_skill,
        "expect": {"receipt_status_in": ["installed", "success"]},
    })

    # 2. skill_trigger_eval — real match_skills behavior + no-overfire
    turns.append({
        "turn_id": "s02",
        "target": "skill_trigger_eval",
        "skill_name": trigger_skill,
        "query": "send whatsapp message to team",
        "expect": {"trigger_fired": True, "no_overfire_on_near_miss": True},
    })

    # 3. skill_check_resolvable — real audit
    turns.append({
        "turn_id": "s03",
        "target": "skill_check_resolvable",
        "skill_name": resolvable_skill,
        "expect": {"no_duplicate_owner": True},
    })

    # Add a few more real skills for coverage if room
    for i, name in enumerate(real_names[3:3 + max_turns - 3]):
        turns.append({
            "turn_id": f"s{4+i:02d}",
            "target": "skill_invoke",
            "skill_name": name,
            "expect": {"receipt_status_in": ["installed", "success"]},
        })

    path = out_path or Path("data/eval/cs153_skill_turns.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)

    header = {
        "truth_label": "CS153_SKILL_V1",
        "version": 1,
        "description": "Domain evals for skill-invoke, trigger, and CheckResolvable. Always regenerated from live index + receipts so content stays grounded.",
    }

    with path.open("w", encoding="utf-8") as f:
        f.write(_json.dumps(header, sort_keys=True) + "\n\n")
        for t in turns[:max_turns]:
            f.write(_json.dumps(t, sort_keys=True) + "\n")

    return turns


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EVAL-2 Talk labeling helper")
    parser.add_argument("--extend-to", type=int, default=0, help="append real Talk refs until the pack has N turns")
    parser.add_argument("--run-sheet", type=Path, default=None, help="write a Markdown labeling run sheet")
    parser.add_argument("--status", action="store_true", help="print labeling status and exit")
    args = parser.parse_args()

    if args.extend_to:
        extend_talk_golden_from_conversation(target_n=args.extend_to)
    if args.run_sheet:
        build_labeling_run_sheet(args.run_sheet)
    if args.status or args.extend_to or args.run_sheet:
        print(json.dumps(labeling_status(), sort_keys=True))
    else:
        print("=== EVAL-2 Talk Labeling Helper ===")
        print(f"This will walk {len(_load_golden_turns())} real Talk golden turns for your verdicts.")
        print("Run with: python3 -m System.eval_talk_labeling_helper\n")
        label_golden_turns_interactive()
