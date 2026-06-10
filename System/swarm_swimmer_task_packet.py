#!/usr/bin/env python3
"""Bounded swimmer task packets for agent-arm delegation (r829/r831).

The field stays rich; the active swimmer reads a narrow bite. A task packet
names organ, job, receipt ids, working-set budget, assumption receipts, and
the output receipt the swimmer must leave — not the whole covenant/tournament.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TRUTH_LABEL = "SWIMMER_TASK_PACKET_V1"
_ASSUMPTION_TRUTH_LABEL = "ASSUMPTION_RECEIPT_V1"

# Context-bolus thresholds (r829): paste a receipt id, not the whole field.
CONTEXT_BOLUS_CHAR_THRESHOLD = 12_000
CONTEXT_BOLUS_TOKEN_ESTIMATE_THRESHOLD = 3_000
DEFAULT_WORKING_SET_BUDGET_CHARS = 4_000

_RECEIPT_REF_RE = re.compile(
    r"\b(?:r\d{2,4}|receipt[_\s-]?[a-f0-9]{6,}|packet_[a-f0-9]{8,})\b",
    re.I,
)
_SECTION_REF_RE = re.compile(
    r"\b(?:##\s*r\d{2,4}|CONSCIOUSNESS_TOURNAMENT|IDE_BOOT_COVENANT|line\s*~?\d{3,6})\b",
    re.I,
)
_EXPENSIVE_ACTION_RE = re.compile(
    r"\b(?:book|reserve|purchase|buy|pay|transfer|send\s+money|schedule\s+flight|"
    r"book\s+flight|book\s+hotel|navigate\s+to|drive\s+to|fly\s+to|travel\s+to)\b",
    re.I,
)
_AMBIGUOUS_PLACE_RE = re.compile(
    r"\b(?:washington|springfield|paris|portland|cambridge|manchester|"
    r"richmond|franklin|georgetown|madison|jackson|salem|arlington)\b(?!\s*,\s*[A-Z]{2}\b)",
    re.I,
)
_COVENANT_DUMP_RE = re.compile(
    r"IDE_BOOT_COVENANT|COVENANT BOOT SPINE|CONSCIOUSNESS TOURNAMENT|"
    r"no-double-spend ASCII swimmers",
    re.I,
)


@dataclass(frozen=True)
class SwimmerTaskPacket:
    packet_id: str
    organ: str
    job: str
    arm_id: str
    owner_task: str
    relevant_receipt_ids: tuple[str, ...] = ()
    working_set_budget_chars: int = DEFAULT_WORKING_SET_BUDGET_CHARS
    assumption_receipt_ids_consumed: tuple[str, ...] = ()
    assumption_receipt_ids_created: tuple[str, ...] = ()
    output_receipt_required: bool = True
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ("agent_arm_receipts.jsonl",)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def prompt_char_count(self) -> int:
        return len(render_swimmer_task_prompt(self))


@dataclass(frozen=True)
class ContextBolusFinding:
    is_bolus: bool
    reason: str
    char_count: int
    has_receipt_ref: bool
    has_section_ref: bool


@dataclass(frozen=True)
class AssumptionReceipt:
    assumption_id: str
    entity: str
    assumption_text: str
    confidence: str
    source: str
    clarification_required: bool
    consumed_by_packet_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row), ensure_ascii=False, default=str) + "\n"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(path, line, encoding="utf-8")
    except Exception:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def new_packet_id() -> str:
    return f"packet_{uuid.uuid4().hex[:12]}"


def new_assumption_id() -> str:
    return f"assume_{uuid.uuid4().hex[:12]}"


def detect_context_bolus(
    prompt: str,
    *,
    char_threshold: int = CONTEXT_BOLUS_CHAR_THRESHOLD,
) -> ContextBolusFinding:
    """Flag huge unrelated global prompts when a receipt id would do."""
    text = prompt or ""
    char_count = len(text)
    has_receipt_ref = bool(_RECEIPT_REF_RE.search(text))
    has_section_ref = bool(_SECTION_REF_RE.search(text))
    has_covenant_dump = bool(_COVENANT_DUMP_RE.search(text)) and char_count > 2_000

    if char_count < char_threshold and not has_covenant_dump:
        return ContextBolusFinding(
            is_bolus=False,
            reason="within_budget",
            char_count=char_count,
            has_receipt_ref=has_receipt_ref,
            has_section_ref=has_section_ref,
        )

    if has_receipt_ref or has_section_ref:
        if char_count < char_threshold * 2:
            return ContextBolusFinding(
                is_bolus=False,
                reason="large_but_focused_by_receipt_or_section_ref",
                char_count=char_count,
                has_receipt_ref=has_receipt_ref,
                has_section_ref=has_section_ref,
            )

    if has_covenant_dump and not has_receipt_ref:
        return ContextBolusFinding(
            is_bolus=True,
            reason="covenant_or_tournament_dump_without_receipt_pointer",
            char_count=char_count,
            has_receipt_ref=has_receipt_ref,
            has_section_ref=has_section_ref,
        )

    if char_count >= char_threshold and not has_receipt_ref and not has_section_ref:
        return ContextBolusFinding(
            is_bolus=True,
            reason="huge_prompt_without_receipt_or_section_pointer",
            char_count=char_count,
            has_receipt_ref=has_receipt_ref,
            has_section_ref=has_section_ref,
        )

    return ContextBolusFinding(
        is_bolus=char_count >= char_threshold * 2,
        reason="oversized_even_with_refs" if char_count >= char_threshold * 2 else "within_budget",
        char_count=char_count,
        has_receipt_ref=has_receipt_ref,
        has_section_ref=has_section_ref,
    )


def detect_ambiguous_entities(text: str) -> list[str]:
    """Surface place/entity names that need an assumption receipt before action."""
    found: list[str] = []
    for match in _AMBIGUOUS_PLACE_RE.finditer(text or ""):
        entity = match.group(0).strip()
        if entity and entity not in found:
            found.append(entity)
    return found


def is_expensive_action(text: str) -> bool:
    return bool(_EXPENSIVE_ACTION_RE.search(text or ""))


def require_assumption_receipt_before_expensive_action(
    text: str,
    *,
    existing_assumption_ids: Sequence[str] | None = None,
    state_dir: Path | str | None = None,
) -> tuple[bool, list[AssumptionReceipt], str]:
    """Block expensive actions on ambiguous entities until assumptions are receipted."""
    if not is_expensive_action(text):
        return True, [], "not_expensive"

    ambiguous = detect_ambiguous_entities(text)
    if not ambiguous:
        return True, [], "no_ambiguous_entity"

    consumed = tuple(existing_assumption_ids or ())
    if consumed:
        return True, [], "assumption_ids_supplied"

    receipts: list[AssumptionReceipt] = []
    for entity in ambiguous:
        assumption_id = new_assumption_id()
        receipts.append(
            AssumptionReceipt(
                assumption_id=assumption_id,
                entity=entity,
                assumption_text=f"Ambiguous entity '{entity}' — clarify jurisdiction before expensive action.",
                confidence="low",
                source="swimmer_task_packet_ambiguity_gate",
                clarification_required=True,
            )
        )
        write_assumption_receipt(receipts[-1], state_dir=state_dir)

    return (
        False,
        receipts,
        "ambiguous_entity_requires_assumption_receipt_before_expensive_action",
    )


def build_task_packet_from_arm_dispatch(
    *,
    arm_id: str,
    owner_task: str,
    organ: str = "agent_arms",
    job: str = "bounded_delegation_pass",
    relevant_receipt_ids: Sequence[str] | None = None,
    working_set_budget_chars: int = DEFAULT_WORKING_SET_BUDGET_CHARS,
    assumption_receipt_ids_consumed: Sequence[str] | None = None,
    reads: Sequence[str] | None = None,
    packet_id: str | None = None,
) -> SwimmerTaskPacket:
    bounded = (owner_task or "").strip()
    if len(bounded) > working_set_budget_chars:
        bounded = bounded[: working_set_budget_chars - 3] + "..."

    return SwimmerTaskPacket(
        packet_id=packet_id or new_packet_id(),
        organ=organ,
        job=job,
        arm_id=arm_id,
        owner_task=bounded,
        relevant_receipt_ids=tuple(relevant_receipt_ids or ()),
        working_set_budget_chars=working_set_budget_chars,
        assumption_receipt_ids_consumed=tuple(assumption_receipt_ids_consumed or ()),
        reads=tuple(reads or ("agent_arm_receipts.jsonl", "work_receipts.jsonl")),
    )


def render_swimmer_task_prompt(packet: SwimmerTaskPacket) -> str:
    """Render a local bite for the swimmer — field is memory, prompt is the bite."""
    receipt_line = (
        ", ".join(packet.relevant_receipt_ids)
        if packet.relevant_receipt_ids
        else "(none — probe only what this job needs)"
    )
    assume_line = (
        ", ".join(packet.assumption_receipt_ids_consumed)
        if packet.assumption_receipt_ids_consumed
        else "(none)"
    )
    return (
        f"SWIMMER TASK PACKET {packet.packet_id}\n"
        f"organ={packet.organ} job={packet.job} arm={packet.arm_id}\n"
        f"working_set_budget_chars={packet.working_set_budget_chars}\n"
        f"relevant_receipt_ids={receipt_line}\n"
        f"assumption_receipts_consumed={assume_line}\n"
        f"output_receipt_required={packet.output_receipt_required}\n"
        "CLOSURE BAR: answer what you read, what you assumed, what you wrote, what remains — from receipts only.\n"
        "Do not reload the full covenant/tournament/transcript. Read receipt ids or probe the named ledgers.\n"
        "Do not speak as Alice. Owner task:\n"
        f"{packet.owner_task}"
    )


def write_task_packet_ledger(
    packet: SwimmerTaskPacket,
    *,
    state_dir: Path | str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state = Path(state_dir or _STATE)
    row = {
        "ts": time.time(),
        "truth_label": _TRUTH_LABEL,
        **packet.to_dict(),
        "prompt_sha256": _sha256_text(render_swimmer_task_prompt(packet)),
        "prompt_chars": packet.prompt_char_count(),
        **(dict(extra) if extra else {}),
    }
    _append_jsonl(state / "swimmer_task_packets.jsonl", row)
    return row


def write_assumption_receipt(
    receipt: AssumptionReceipt,
    *,
    state_dir: Path | str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state = Path(state_dir or _STATE)
    row = {
        "ts": time.time(),
        "truth_label": _ASSUMPTION_TRUTH_LABEL,
        **receipt.to_dict(),
        **(dict(extra) if extra else {}),
    }
    _append_jsonl(state / "assumption_receipts.jsonl", row)
    return row


def packet_closure_summary(
    packet: SwimmerTaskPacket,
    *,
    output_receipt_id: str = "",
    assumptions_created: Sequence[str] | None = None,
    remains: str = "",
) -> str:
    """Compact closure line the arm or cortex can speak from receipts only."""
    return (
        f"packet={packet.packet_id} read_receipts={','.join(packet.relevant_receipt_ids) or 'none'} "
        f"assumed={','.join(packet.assumption_receipt_ids_consumed) or 'none'} "
        f"wrote={output_receipt_id or 'pending'} "
        f"assumptions_created={','.join(assumptions_created or ()) or 'none'} "
        f"remains={remains or 'none'}"
    )


__all__ = [
    "ASSUMPTION_TRUTH_LABEL",
    "CONTEXT_BOLUS_CHAR_THRESHOLD",
    "DEFAULT_WORKING_SET_BUDGET_CHARS",
    "AssumptionReceipt",
    "ContextBolusFinding",
    "SwimmerTaskPacket",
    "TRUTH_LABEL",
    "build_task_packet_from_arm_dispatch",
    "detect_ambiguous_entities",
    "detect_context_bolus",
    "is_expensive_action",
    "new_assumption_id",
    "new_packet_id",
    "packet_closure_summary",
    "render_swimmer_task_prompt",
    "require_assumption_receipt_before_expensive_action",
    "write_assumption_receipt",
    "write_task_packet_ledger",
]

TRUTH_LABEL = _TRUTH_LABEL
ASSUMPTION_TRUTH_LABEL = _ASSUMPTION_TRUTH_LABEL