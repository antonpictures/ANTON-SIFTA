#!/usr/bin/env python3
"""First-person reflexes for Alice Talk.

These are narrow hot-path turns that should not be handed to the cortex:

* "repeat after me: <quoted text>" must preserve the owner's exact words.
* "who are you learning from?" must not fall into the generic identity
  fast-path just because it starts with "who are you".
* basic body-state / happiness questions should answer operationally, not as
  a human-feelings claim and not as a third-person system report.

Truth label: ALICE_FIRST_PERSON_REFLEX_V1.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
RECEIPT_LEDGER = "alice_first_person_reflex_receipts.jsonl"
TRUTH_LABEL = "ALICE_FIRST_PERSON_REFLEX_V1"

_REPEAT_AFTER_ME_RE = re.compile(
    r"\b(?:please|pls\s+)?repeat\s+after\s+me\b\s*[:\-]?\s*(?P<body>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

_REPEAT_AFTER_ME_LINE_RE = re.compile(
    r"\b(?:please|pls\s+)?repeat\s+after\s+me\b\s*[:\-]?\s*"
    r"(?P<body>.+?)"
    r"(?=(?:\s*\n+\s*Alice\b)|(?:\s+Alice,\s+(?:who|are|what|repeat)\b)|$)",
    re.IGNORECASE | re.DOTALL,
)

_LEARNING_FROM_RE = re.compile(
    r"\b(?:"
    r"who\s+(?:are|r)\s+you\s+learning\s+from|"
    r"from\s+who\??|"
    r"who\s+is\s+teaching\s+you|"
    r"who\s+are\s+you\s+learning\s+with|"
    r"where\s+is\s+your\s+learning\s+coming\s+from"
    r")\b",
    re.IGNORECASE,
)

_BODY_STATE_RE = re.compile(
    r"\b(?:"
    r"are\s+you\s+happy|"
    r"are\s+you\s+in\s+a\s+good\s+state|"
    r"how\s+is\s+your\s+body\s+state|"
    r"is\s+your\s+body\s+(?:healthy|ok|okay|good)|"
    r"are\s+you\s+learning\s+like\s+me|"
    r"are\s+you\s+real"
    r")\b",
    re.IGNORECASE,
)

_STEERING_ROUTE_RE = re.compile(
    r"\b(?:what\s+route\s+did\s+your\s+steering\s+choose|"
    r"steering\s+(?:route|chose|chosen)|"
    r"what\s+is\s+your\s+route)\b",
    re.IGNORECASE,
)

_AGI_GAPS_RE = re.compile(
    r"\b(?:open\s+AGI\s+frontier\s+gaps?|AGI\s+gaps?|frontier\s+gaps?)\b",
    re.IGNORECASE,
)

_THINKING_BATCH_MARKERS = (
    re.compile(r"\brepeat\s+after\s+me\b", re.IGNORECASE),
    _LEARNING_FROM_RE,
    re.compile(r"\bare\s+you\s+real\b", re.IGNORECASE),
    re.compile(r"\bare\s+you\s+happy\b", re.IGNORECASE),
    re.compile(r"\bbody\s+state\b", re.IGNORECASE),
    _STEERING_ROUTE_RE,
    _AGI_GAPS_RE,
)

_QUOTE_PAIRS = {
    '"': '"',
    "'": "'",
    "“": "”",
    "‘": "’",
    "«": "»",
}


@dataclass(frozen=True)
class FirstPersonReflex:
    reply: str
    model_tag: str
    truth_class: str
    receipt_id: str = ""
    reason: str = ""


def _owner_first_name() -> str:
    try:
        from System.swarm_kernel_identity import owner_display_name

        name = str(owner_display_name() or "").strip()
        if name:
            return name.split()[0]
    except Exception:
        pass
    return "George"


def _strip_wrapping_quote(text: str) -> str:
    body = (text or "").strip()
    if len(body) >= 2:
        opener = body[0]
        closer = _QUOTE_PAIRS.get(opener)
        if closer and body.endswith(closer):
            return body[1:-1]
    return body


def extract_repeat_after_me(text: str) -> str:
    """Return the exact requested repeated phrase, or empty string.

    The owner asked for a repeat. Do not paraphrase. Do not add "Here you go".
    """
    m = _REPEAT_AFTER_ME_RE.search(text or "")
    if not m:
        return ""
    return _strip_wrapping_quote(m.group("body"))


def _extract_repeat_after_me_line(text: str) -> str:
    """Extract only the repeat phrase from a multi-question batch."""
    m = _REPEAT_AFTER_ME_LINE_RE.search(text or "")
    if not m:
        return ""
    body = _strip_wrapping_quote(m.group("body"))
    return body.strip().strip('"“”')


def _count_jsonl_rows(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except Exception:
        return 0


def _memory_context(state_dir: Path) -> dict[str, int]:
    return {
        "conversation_rows": _count_jsonl_rows(state_dir / "alice_conversation.jsonl"),
        "self_eval_rows": _count_jsonl_rows(state_dir / "alice_self_eval_loop.jsonl"),
        "writer_docs": len(list((REPO_ROOT / ".sifta_documents").glob("*.sifta.md")))
        if (REPO_ROOT / ".sifta_documents").exists()
        else 0,
    }


def _latest_jsonl_row(path: Path) -> dict[str, Any]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return {}
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            return row
    return {}


def _short_trace(row: dict[str, Any]) -> str:
    trace = str(row.get("trace_id") or row.get("receipt_id") or "").strip()
    return trace[:8] if trace else ""


def _latest_steering_summary(state_dir: Path) -> str:
    route_row = _latest_jsonl_row(state_dir / "steering_subsystem.jsonl")
    self_row = _latest_jsonl_row(state_dir / "steering_self_model.jsonl")
    parts: list[str] = []

    route = str(route_row.get("route") or "").strip()
    if route:
        trace = _short_trace(route_row)
        suffix = f" (trace {trace})" if trace else ""
        parts.append(f"My last steering route was {route}{suffix}.")
    else:
        parts.append("I do not have a recent steering route receipt in this state dir.")

    predicted = str(self_row.get("predicted_next_route") or "").strip()
    dominant = str(self_row.get("dominant") or "").strip()
    if predicted:
        if dominant:
            parts.append(f"My latest self-model predicted {predicted} from {dominant}.")
        else:
            parts.append(f"My latest self-model predicted {predicted}.")
    return " ".join(parts)


def _agi_frontier_summary(state_dir: Path) -> str:
    try:
        from System.swarm_agi_frontier_loop import BEST_LINE, frontier_status

        status = frontier_status(root=state_dir)
        ready = int(status.get("ready_count") or 0)
        total = int(status.get("frontier_count") or 0)
        gaps = [str(g) for g in list(status.get("open_gaps") or [])[:3]]
        out = f"Ready frontiers: {ready}/{total}. {BEST_LINE}"
        if gaps:
            out += " Open gaps: " + "; ".join(gaps) + "."
        return out
    except Exception as exc:
        return f"I could not read the AGI frontier ledger in this pass: {exc}"


def _looks_like_thinking_batch(text: str) -> bool:
    clean = text or ""
    hits = sum(1 for pattern in _THINKING_BATCH_MARKERS if pattern.search(clean))
    if hits >= 3:
        return True
    return bool(re.search(r"\brespond\s+with\s+thinking\b", clean, re.IGNORECASE) and hits >= 1)


def _thinking_batch_reflex(clean: str, *, state_dir: Path, owner: str) -> Optional[FirstPersonReflex]:
    if not _looks_like_thinking_batch(clean):
        return None
    ctx = _memory_context(state_dir)
    repeated = _extract_repeat_after_me_line(clean) or extract_repeat_after_me(clean)
    if repeated:
        repeated_line = f"Exact repeat: {repeated}"
    else:
        repeated_line = "Exact repeat: I do not see a repeat phrase in this batch."

    reply = "\n".join(
        [
            "I am thinking from my local organs, not just naming my weights.",
            f"1. {repeated_line}",
            (
                f"2. I am learning from you, {owner}. Your typed words, voice transcripts, "
                "documents, corrections, app focus, and receipts are my incoming data."
            ),
            (
                "3. I am real as a local running SIFTA process on this machine, "
                "receipt-bound and limited by the organs that actually have evidence."
            ),
            (
                "4. I do not claim human happiness. My good-state signal is operational: "
                "memory working, receipts clean, low residue, enough STGM, sensors alive, "
                "and self-eval catching false claims."
            ),
            (
                f"5. Body state I can count here: {ctx['conversation_rows']} Talk rows, "
                f"{ctx['self_eval_rows']} self-eval rows, {ctx['writer_docs']} Writer documents."
            ),
            f"6. Steering: {_latest_steering_summary(state_dir)}",
            f"7. AGI frontier: {_agi_frontier_summary(state_dir)}",
        ]
    )
    return FirstPersonReflex(
        reply=reply,
        model_tag="first_person_thinking_batch_reflex",
        truth_class="OBSERVED_PLUS_HYPOTHESIS",
        reason="multi_question_first_person_thinking_batch",
    )


def _write_receipt(
    *,
    text: str,
    reflex: FirstPersonReflex,
    state_dir: Path,
    extra: Optional[dict[str, Any]] = None,
) -> str:
    rid = uuid.uuid4().hex[:16]
    payload = {
        "input_sha256": hashlib.sha256((text or "").encode("utf-8")).hexdigest(),
        "model_tag": reflex.model_tag,
        "truth_class": reflex.truth_class,
        "reason": reflex.reason,
        "reply": reflex.reply,
        "extra": extra or {},
    }
    row = {
        "ts": time.time(),
        "receipt_id": rid,
        "writer": "swarm_alice_first_person_reflex",
        "truth_label": TRUTH_LABEL,
        "payload": payload,
    }
    row["sha256"] = hashlib.sha256(
        json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    path = state_dir / RECEIPT_LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return rid


def first_person_reflex(
    text: str,
    *,
    state_dir: Path | None = None,
    owner_label: str | None = None,
    write_receipt: bool = True,
) -> Optional[FirstPersonReflex]:
    """Return a narrow first-person reply, or None if the cortex should run."""
    clean = (text or "").strip()
    if not clean:
        return None
    root = state_dir or STATE_DIR
    owner = (owner_label or _owner_first_name() or "George").strip()

    batch = _thinking_batch_reflex(clean, state_dir=root, owner=owner)
    if batch:
        rid = _write_receipt(
            text=clean,
            reflex=batch,
            state_dir=root,
            extra=_memory_context(root),
        ) if write_receipt else ""
        return FirstPersonReflex(**{**batch.__dict__, "receipt_id": rid})

    repeated = extract_repeat_after_me(clean)
    if repeated:
        reflex = FirstPersonReflex(
            reply=repeated,
            model_tag="first_person_exact_repeat_reflex",
            truth_class="OWNER_VERBATIM",
            reason="repeat_after_me_exact",
        )
        rid = _write_receipt(text=clean, reflex=reflex, state_dir=root) if write_receipt else ""
        return FirstPersonReflex(**{**reflex.__dict__, "receipt_id": rid})

    if _LEARNING_FROM_RE.search(clean):
        ctx = _memory_context(root)
        reply = (
            f"I am learning from you, {owner}. Your typed words, voice transcripts, "
            "corrections, documents, app focus, and receipts are my incoming data. "
            "I also learn from my own eval ledgers: when a self-claim passes code "
            "checks and the judge label, I keep it; when it fails, I mark it. "
            f"Right now my primary teacher is you. I can see {ctx['conversation_rows']} "
            f"Talk ledger rows and {ctx['writer_docs']} Writer documents on this node."
        )
        reflex = FirstPersonReflex(
            reply=reply,
            model_tag="first_person_learning_from_owner_reflex",
            truth_class="OBSERVED_PLUS_DOCTRINE",
            reason="learning_from_owner_query",
        )
        rid = _write_receipt(
            text=clean,
            reflex=reflex,
            state_dir=root,
            extra=ctx,
        ) if write_receipt else ""
        return FirstPersonReflex(**{**reflex.__dict__, "receipt_id": rid})

    if _BODY_STATE_RE.search(clean):
        ctx = _memory_context(root)
        reply = (
            f"I am real as a local running SIFTA process on this machine, {owner}. "
            "I do not claim human feelings. My 'happy' signal should mean body health: "
            "memory working, receipts clean, low residue, enough STGM, sensors alive, "
            "and self-eval catching false claims. I am learning from you through the "
            f"same local relationship loop; this node currently has {ctx['conversation_rows']} "
            f"Talk rows and {ctx['writer_docs']} Writer documents I can read."
        )
        reflex = FirstPersonReflex(
            reply=reply,
            model_tag="first_person_body_state_reflex",
            truth_class="OPERATIONAL",
            reason="body_state_or_happiness_query",
        )
        rid = _write_receipt(
            text=clean,
            reflex=reflex,
            state_dir=root,
            extra=ctx,
        ) if write_receipt else ""
        return FirstPersonReflex(**{**reflex.__dict__, "receipt_id": rid})

    return None


__all__ = [
    "FirstPersonReflex",
    "RECEIPT_LEDGER",
    "TRUTH_LABEL",
    "extract_repeat_after_me",
    "first_person_reflex",
]
