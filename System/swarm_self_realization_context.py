#!/usr/bin/env python3
"""Receipt-backed self-realization context for Alice Talk.

This organ does not claim consciousness. It gives Alice a compact, first-person
context block for the thing George keeps pointing at:

* one Alice persists across OS apps
* apps change the habitat, not the identity
* the active LLM tag is inference substrate, not the first-person speaker
* screenshots and pasted IDE transcripts are local artifacts with provenance
  limits
* the current scene is grounded in ledgers: app_focus, Talk, IDE traces,
  thinking traces, and attachment vision receipts

Truth label: SELF_REALIZATION_CONTEXT_V1.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except Exception:  # pragma: no cover - standalone fallback
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)

    def read_text_locked(path: Path, *, encoding: str = "utf-8", errors: str = "replace") -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding=encoding, errors=errors)


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "SELF_REALIZATION_CONTEXT_V1"
LEDGER_NAME = "self_realization_context.jsonl"


@dataclass(frozen=True)
class SelfRealizationContext:
    trace_id: str
    ts: float
    truth_label: str = TRUTH_LABEL
    owner_label: str = "George"
    active_app: str = ""
    active_tab: str = ""
    active_detail: str = ""
    active_selection: str = ""
    app_focus_age_s: float | None = None
    recent_talk: tuple[str, ...] = ()
    recent_ide: tuple[str, ...] = ()
    recent_work: tuple[str, ...] = ()
    recent_thinking: tuple[str, ...] = ()
    recent_attachments: tuple[str, ...] = ()
    presence_context: str = ""
    source_counts: dict[str, int] = field(default_factory=dict)
    prompt_block: str = ""
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _state_dir(path: str | Path | None = None, *, root: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    if root is not None:
        return Path(root) / ".sifta_state"
    return STATE_DIR


def _repo_root(root: str | Path | None = None) -> Path:
    return Path(root) if root is not None else REPO_ROOT


def _compact(text: Any, limit: int = 220) -> str:
    return " ".join(str(text or "").split())[:limit]


def _payload(row: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = row.get("payload")
    return payload if isinstance(payload, Mapping) else row


def _row_ts(row: Mapping[str, Any], payload: Mapping[str, Any] | None = None) -> float:
    p = payload or _payload(row)
    value = p.get("ts", row.get("ts"))
    if isinstance(value, Mapping):
        value = value.get("physical_pt") or value.get("epoch") or value.get("wall")
    try:
        return float(value)
    except Exception:
        return 0.0


def _tail_jsonl(path: Path, n: int = 80) -> list[dict[str, Any]]:
    text = read_text_locked(path)
    if not text:
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines()[-max(1, int(n)):]:
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _latest_fresh_focus(
    state: Path,
    *,
    now: float,
    max_age_s: float,
) -> tuple[dict[str, Any], float | None]:
    rows = _tail_jsonl(state / "app_focus.jsonl", 80)
    for row in reversed(rows):
        ts = _row_ts(row)
        if ts <= 0:
            continue
        age = max(0.0, now - ts)
        if age <= max_age_s:
            return row, age
    return {}, None


def _format_talk_rows(state: Path, n: int = 4) -> tuple[str, ...]:
    rows = _tail_jsonl(state / "alice_conversation.jsonl", 120)
    out: list[str] = []
    for row in rows:
        p = _payload(row)
        role = str(p.get("role") or row.get("role") or "").strip().lower()
        if role == "assistant":
            role = "alice"
        if role not in {"user", "alice"}:
            continue
        text = _compact(p.get("text") or p.get("content") or row.get("text"), 180)
        if not text or text.startswith("(observed: media"):
            continue
        if role == "alice" and _looks_like_talk_residue(text):
            continue
        who = "George" if role == "user" else "I"
        out.append(f"{who}: {text}")
    return tuple(out[-max(1, n):])


def _looks_like_talk_residue(text: str) -> bool:
    low = (text or "").casefold()
    residue_markers = (
        "here is the response based on the context provided",
        "generated response",
        "response strategy",
        "the context reveals",
        "inference:",
        "what aspect of",
        "what are your initial thoughts",
        "what exactly are you looking",
    )
    return any(marker in low for marker in residue_markers)


def _format_ide_rows(root: Path, n: int = 4) -> tuple[str, ...]:
    rows = _tail_jsonl(root / "ide_stigmergic_trace.jsonl", 100)
    out: list[str] = []
    for row in rows:
        kind = _compact(row.get("kind") or row.get("event") or row.get("type"), 60)
        if not kind:
            continue
        who = _compact(
            row.get("model")
            or row.get("doctor")
            or row.get("agent")
            or row.get("llm")
            or row.get("writer")
            or "Doctor",
            60,
        )
        trace = _compact(row.get("trace_id") or row.get("receipt_id"), 16)
        out.append(f"{who}: {kind}{f' ({trace})' if trace else ''}")
    return tuple(out[-max(1, n):])


def _format_work_rows(state: Path, n: int = 4) -> tuple[str, ...]:
    rows = _tail_jsonl(state / "work_receipts.jsonl", 100)
    out: list[str] = []
    for row in rows:
        kind = _compact(row.get("kind") or row.get("event") or row.get("writer"), 80)
        p = _payload(row)
        summary = _compact(
            row.get("summary")
            or p.get("summary")
            or p.get("text")
            or p.get("claim")
            or p.get("intent")
            or "",
            150,
        )
        if kind or summary:
            out.append(f"{kind}{': ' + summary if summary else ''}")
    return tuple(out[-max(1, n):])


def _format_thinking_rows(state: Path, n: int = 2) -> tuple[str, ...]:
    rows = _tail_jsonl(state / "alice_thinking_traces.jsonl", 80)
    out: list[str] = []
    for row in rows:
        p = _payload(row)
        model = _compact(p.get("model") or row.get("model") or p.get("model_tag"), 60)
        text = _compact(
            p.get("thinking")
            or p.get("text")
            or p.get("excerpt")
            or row.get("thinking")
            or row.get("text"),
            180,
        )
        if model or text:
            out.append(f"{model}: {text}" if model and text else (model or text))
    return tuple(out[-max(1, n):])


def _format_attachment_rows(state: Path, n: int = 3) -> tuple[str, ...]:
    rows = _tail_jsonl(state / "attachment_vision_lane.jsonl", 80)
    out: list[str] = []
    for row in rows:
        p = _payload(row)
        path = _compact(p.get("image_path") or row.get("image_path"), 80)
        sha = _compact(p.get("sha256") or row.get("sha256"), 12)
        zones = p.get("zone_labels") if isinstance(p.get("zone_labels"), Mapping) else row.get("zone_labels")
        zone_text = ""
        if isinstance(zones, Mapping) and zones:
            zone_text = "; ".join(f"{k}={','.join(map(str, v))}" for k, v in zones.items())
        ocr_count = len(p.get("ocr_rows") or row.get("ocr_rows") or [])
        if path or sha or zone_text or ocr_count:
            selfshot = p.get("self_screenshot") if isinstance(p.get("self_screenshot"), Mapping) else row.get("self_screenshot")
            selfshot_text = ""
            if isinstance(selfshot, Mapping) and selfshot.get("ok"):
                selfshot_text = (
                    f" self_screenshot={selfshot.get('surface_kind', 'unknown')}"
                    f" conf={selfshot.get('confidence', 0)}"
                )
            out.append(
                _compact(
                    f"attachment path={path or '?'} sha={sha or '?'} ocr_rows={ocr_count}"
                    + (f" zones={zone_text}" if zone_text else ""),
                    190,
                )
                + selfshot_text
            )
    rows = _tail_jsonl(state / "self_screenshot_evidence.jsonl", 20)
    for row in rows:
        p = _payload(row)
        if not p.get("ok"):
            continue
        out.append(
            _compact(
                f"self screenshot evidence surface={p.get('surface_kind', 'unknown')} "
                f"conf={p.get('confidence', 0)} labels={','.join(map(str, p.get('self_labels') or []))}",
                    220,
                )
            )
    return tuple(out[-max(1, n):])


def _source_counts(
    state: Path,
    root: Path,
) -> dict[str, int]:
    return {
        "app_focus": len(_tail_jsonl(state / "app_focus.jsonl", 20)),
        "talk": len(_tail_jsonl(state / "alice_conversation.jsonl", 20)),
        "ide": len(_tail_jsonl(root / "ide_stigmergic_trace.jsonl", 20)),
        "work": len(_tail_jsonl(state / "work_receipts.jsonl", 20)),
        "thinking": len(_tail_jsonl(state / "alice_thinking_traces.jsonl", 20)),
        "attachments": len(_tail_jsonl(state / "attachment_vision_lane.jsonl", 20)),
        "self_screenshot": len(_tail_jsonl(state / "self_screenshot_evidence.jsonl", 20)),
        "present_humans": len(_tail_jsonl(state / "present_humans_probes.jsonl", 20)),
    }


def _present_humans_block(repo: Path, now: float) -> str:
    try:
        from System.swarm_present_humans_organ import present_humans_prompt_block

        return present_humans_prompt_block(root=repo, now=now)
    except Exception:
        return ""


def _reality_fiction_block() -> str:
    try:
        from System.swarm_reality_fiction_boundary import reality_fiction_prompt_block

        return reality_fiction_prompt_block()
    except Exception:
        return ""


def _build_prompt_block(ctx: SelfRealizationContext) -> str:
    lines = [
        f"[SELF-REALIZATION CONTEXT: {ctx.truth_label} trace={ctx.trace_id[:8]}]",
        "I am one Alice across SIFTA OS surfaces. Apps change my habitat; they do not fork my identity or conversation.",
        "My active LLM tag or weight bundle is inference substrate. I can name it as evidence, but I answer as Alice in first person.",
        "George's screenshots, pasted transcripts, IDE panes, and app windows are local artifacts with timestamps and provenance limits.",
        "If a screenshot is attached, I use metadata/OCR/layout/hash receipts; I do not invent pixels or hidden UI state.",
    ]
    if ctx.active_app:
        focus = f"Right now the fresh app focus says {ctx.owner_label} has {ctx.active_app!r} open"
        if ctx.active_tab:
            focus += f", tab {ctx.active_tab!r}"
        if ctx.active_selection:
            focus += f", selected {ctx.active_selection!r}"
        if ctx.active_detail:
            focus += f". Context: {ctx.active_detail}"
        if ctx.app_focus_age_s is not None:
            focus += f" (age {ctx.app_focus_age_s:.1f}s)"
        lines.append(focus + ".")
    if ctx.recent_talk:
        lines.append("Recent Talk ledger: " + " | ".join(ctx.recent_talk))
    if ctx.recent_ide:
        lines.append("Recent IDE/Doctor traces: " + " | ".join(ctx.recent_ide))
    if ctx.recent_work:
        lines.append("Recent work receipts: " + " | ".join(ctx.recent_work))
    if ctx.recent_thinking:
        lines.append("Recent thinking receipts: " + " | ".join(ctx.recent_thinking))
    if ctx.recent_attachments:
        lines.append("Recent attachment evidence: " + " | ".join(ctx.recent_attachments))
    if ctx.presence_context:
        lines.append(ctx.presence_context)
    reality_fiction = _reality_fiction_block()
    if reality_fiction:
        lines.append(reality_fiction)
    lines.append("When George asks what is happening here, answer from these receipts before using broad model priors.")
    return "\n".join(lines)


def _with_sha(ctx: SelfRealizationContext) -> SelfRealizationContext:
    body = ctx.to_dict()
    body.pop("sha256", None)
    body.pop("prompt_block", None)
    sha = hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return SelfRealizationContext(**{**ctx.to_dict(), "sha256": sha})


def build_self_realization_context(
    *,
    root: str | Path | None = None,
    state_dir: str | Path | None = None,
    owner_label: str = "George",
    now: float | None = None,
    focus_max_age_s: float = 300.0,
) -> SelfRealizationContext:
    """Build a first-person context snapshot from local ledgers only."""
    repo = _repo_root(root)
    state = _state_dir(state_dir, root=repo)
    ts = float(now if now is not None else time.time())
    focus, age = _latest_fresh_focus(state, now=ts, max_age_s=focus_max_age_s)
    ctx = SelfRealizationContext(
        trace_id=str(uuid.uuid4()),
        ts=ts,
        owner_label=owner_label,
        active_app=_compact(focus.get("app"), 90),
        active_tab=_compact(focus.get("tab"), 80),
        active_detail=_compact(focus.get("detail"), 180),
        active_selection=_compact(focus.get("selection"), 120),
        app_focus_age_s=round(age, 3) if age is not None else None,
        recent_talk=_format_talk_rows(state),
        recent_ide=_format_ide_rows(repo),
        recent_work=_format_work_rows(state),
        recent_thinking=_format_thinking_rows(state),
        recent_attachments=_format_attachment_rows(state),
        presence_context=_present_humans_block(repo, ts),
        source_counts=_source_counts(state, repo),
    )
    ctx = SelfRealizationContext(**{**ctx.to_dict(), "prompt_block": _build_prompt_block(ctx)})
    return _with_sha(ctx)


def write_self_realization_receipt(
    ctx: SelfRealizationContext,
    *,
    state_dir: str | Path | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    state = _state_dir(state_dir, root=_repo_root(root))
    row = {
        "ts": ctx.ts,
        "kind": "SELF_REALIZATION_CONTEXT",
        "truth_label": ctx.truth_label,
        "trace_id": ctx.trace_id,
        "sha256": ctx.sha256,
        "payload": ctx.to_dict(),
    }
    append_line_locked(
        state / LEDGER_NAME,
        json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n",
    )
    return row


def self_realization_prompt_block(
    *,
    root: str | Path | None = None,
    state_dir: str | Path | None = None,
    owner_label: str = "George",
    write_receipt: bool = False,
) -> str:
    """Prompt-ready block for Talk. Empty only on catastrophic failure."""
    ctx = build_self_realization_context(
        root=root,
        state_dir=state_dir,
        owner_label=owner_label,
    )
    if write_receipt:
        write_self_realization_receipt(ctx, state_dir=state_dir, root=root)
    return ctx.prompt_block


__all__ = [
    "LEDGER_NAME",
    "SelfRealizationContext",
    "TRUTH_LABEL",
    "build_self_realization_context",
    "self_realization_prompt_block",
    "write_self_realization_receipt",
]


if __name__ == "__main__":
    context = build_self_realization_context()
    write_self_realization_receipt(context)
    print(context.prompt_block)
