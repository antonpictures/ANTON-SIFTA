"""Ledger-strict /cortex llm list binding — bare numbers bind to last render (r1018 P1)."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]

SCHEMA = "CORTEX_LLM_RENDERED_LIST_V1"
BINDING_SCHEMA = "CORTEX_LLM_BINDING_RECEIPT_V1"
LEDGER_NAME = "cortex_llm_rendered_lists.jsonl"
BINDING_LEDGER = "cortex_llm_binding_receipts.jsonl"
PENDING_NAME = "cortex_llm_pending_binding.json"
STALE_SECONDS = 600.0
INCIDENT_P1_SPARK_MISBIND = "p1-193000-spark-misbind"

NAMESPACE_CLINE = "cline_attached"
NAMESPACE_GROK = "grok_attached"
NAMESPACE_CLAUDE = "claude_arm"
NAMESPACE_CODEX = "codex_attached"
NAMESPACE_MIMO = "mimo_attached"
NAMESPACE_QWEN = "fireworks_attached"

UPSTREAM_NAMESPACES = frozenset(
    {NAMESPACE_CLINE, NAMESPACE_CODEX, NAMESPACE_MIMO}
)
MUTABLE_NAMESPACES = frozenset({NAMESPACE_CLAUDE, NAMESPACE_GROK})


def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return Path(__file__).resolve().parents[1] / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _append(sd: Path, name: str, row: Dict[str, Any]) -> None:
    line = json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
    path = sd / name
    if append_line_locked is not None:
        append_line_locked(path, line)
    else:  # pragma: no cover
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def format_render_clock(render_ts: float) -> str:
    try:
        return time.strftime("%H:%M:%S", time.localtime(render_ts))
    except Exception:
        return str(render_ts)


def record_rendered_list(
    *,
    namespace: str,
    items: List[str],
    labels: Optional[List[str]] = None,
    selected_cortex: str = "",
    is_primary: bool = False,
    owner_text: str = "",
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    sd = _state_dir(state_dir)
    now = time.time()
    row = {
        "schema": SCHEMA,
        "list_id": str(uuid.uuid4()),
        "namespace": namespace,
        "items": [str(x) for x in items],
        "labels": [str(x) for x in (labels or items)],
        "render_ts": now,
        "selected_cortex": str(selected_cortex or ""),
        "is_primary": bool(is_primary),
        "owner_text_preview": (owner_text or "")[:120],
    }
    _append(sd, LEDGER_NAME, row)
    return row


def last_primary_list(*, state_dir: Path | str | None = None) -> Optional[Dict[str, Any]]:
    sd = _state_dir(state_dir)
    path = sd / LEDGER_NAME
    if not path.exists():
        return None
    last: Optional[Dict[str, Any]] = None
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except Exception:
            continue
        if row.get("is_primary"):
            last = row
    return last


def last_list_for_namespace(
    namespace: str,
    *,
    state_dir: Path | str | None = None,
) -> Optional[Dict[str, Any]]:
    sd = _state_dir(state_dir)
    path = sd / LEDGER_NAME
    if not path.exists():
        return None
    last: Optional[Dict[str, Any]] = None
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except Exception:
            continue
        if row.get("namespace") == namespace:
            last = row
    return last


def is_stale(row: Dict[str, Any], *, threshold: float = STALE_SECONDS) -> bool:
    try:
        age = time.time() - float(row.get("render_ts") or 0.0)
    except Exception:
        return True
    return age > float(threshold)


def resolve_index(row: Dict[str, Any], index: int) -> Optional[str]:
    items = row.get("items") or []
    if 1 <= int(index) <= len(items):
        return str(items[int(index) - 1])
    return None


@dataclass
class ParsedMutationArg:
    kind: str
    namespace: str = ""
    index: int = 0
    model_id: str = ""


def normalize_namespace(ns: str) -> str:
    key = str(ns or "").strip().lower()
    return {
        "cline": NAMESPACE_CLINE,
        "grok": NAMESPACE_GROK,
        "claude": NAMESPACE_CLAUDE,
        "codex": NAMESPACE_CODEX,
        "mimo": NAMESPACE_MIMO,
        "qwen": NAMESPACE_QWEN,
        "fireworks": NAMESPACE_QWEN,
        NAMESPACE_CLINE: NAMESPACE_CLINE,
        NAMESPACE_GROK: NAMESPACE_GROK,
        NAMESPACE_CLAUDE: NAMESPACE_CLAUDE,
        NAMESPACE_CODEX: NAMESPACE_CODEX,
        NAMESPACE_MIMO: NAMESPACE_MIMO,
        NAMESPACE_QWEN: NAMESPACE_QWEN,
    }.get(key, key)


def parse_mutation_arg(arg: str) -> ParsedMutationArg:
    text = (arg or "").strip()
    if not text:
        return ParsedMutationArg(kind="list")
    low = text.lower()
    if low in ("confirm", "yes", "y"):
        return ParsedMutationArg(kind="confirm")
    parts = text.split()
    if parts[0].lower() == "pin" and len(parts) >= 3:
        ns = normalize_namespace(parts[1])
        tail = parts[2]
        if tail.isdigit():
            return ParsedMutationArg(kind="namespaced", namespace=ns, index=int(tail))
        return ParsedMutationArg(kind="namespaced", namespace=ns, model_id=tail)
    if parts[0].lower() in ("cline", "grok", "claude", "codex", "mimo", "qwen", "fireworks") and len(parts) >= 2:
        ns = normalize_namespace(parts[0])
        tail = parts[1]
        if tail.isdigit():
            return ParsedMutationArg(kind="namespaced", namespace=ns, index=int(tail))
        return ParsedMutationArg(kind="namespaced", namespace=ns, model_id=tail)
    if len(parts) == 1 and parts[0].isdigit():
        return ParsedMutationArg(kind="bare_number", index=int(parts[0]))
    if low in ("default", "cli", "clear", "off", "reset"):
        return ParsedMutationArg(kind="clear")
    return ParsedMutationArg(kind="model_id", model_id=parts[0])


def namespace_title(namespace: str) -> str:
    return {
        NAMESPACE_CLINE: "Cline upstream list",
        NAMESPACE_GROK: "Grok attached list",
        NAMESPACE_CLAUDE: "Claude arm pin list",
        NAMESPACE_CODEX: "Codex upstream list",
        NAMESPACE_MIMO: "MiMo upstream list",
        NAMESPACE_QWEN: "Fireworks attached list",
    }.get(namespace, namespace)


def save_pending_binding(payload: Dict[str, Any], *, state_dir: Path | str | None = None) -> None:
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    (sd / PENDING_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_pending_binding(*, state_dir: Path | str | None = None) -> Optional[Dict[str, Any]]:
    path = _state_dir(state_dir) / PENDING_NAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def clear_pending_binding(*, state_dir: Path | str | None = None) -> None:
    path = _state_dir(state_dir) / PENDING_NAME
    if path.exists():
        path.unlink()


def write_binding_receipt(
    *,
    action: str,
    payload: Dict[str, Any],
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    sd = _state_dir(state_dir)
    row = {
        "schema": BINDING_SCHEMA,
        "action": action,
        "receipt_id": str(uuid.uuid4()),
        "ts": time.time(),
        **payload,
    }
    _append(sd, BINDING_LEDGER, row)
    return row


def resolve_binding(
    parsed: ParsedMutationArg,
    *,
    state_dir: Path | str | None = None,
    claude_catalog: List[str],
    grok_catalog: List[str],
    fireworks_catalog: Optional[List[str]] = None,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Return (binding_dict, error_code). binding_dict has namespace, model_id, list_row, index."""
    if parsed.kind == "bare_number":
        row = last_primary_list(state_dir=state_dir)
        if not row:
            return None, "no_rendered_list"
        if is_stale(row):
            return None, "stale_rendered_list"
        model_id = resolve_index(row, parsed.index)
        if not model_id:
            return None, "index_out_of_range"
        return {
            "namespace": str(row.get("namespace") or ""),
            "model_id": model_id,
            "index": parsed.index,
            "list_row": row,
        }, ""

    if parsed.kind == "namespaced":
        ns = normalize_namespace(parsed.namespace)
        if ns == NAMESPACE_CLAUDE:
            catalog = claude_catalog
            row = last_list_for_namespace(ns, state_dir=state_dir) or {
                "namespace": ns,
                "items": catalog,
                "render_ts": time.time(),
                "list_id": "catalog-fallback",
            }
        elif ns == NAMESPACE_GROK:
            catalog = grok_catalog
            row = last_list_for_namespace(ns, state_dir=state_dir) or {
                "namespace": ns,
                "items": catalog,
                "render_ts": time.time(),
                "list_id": "catalog-fallback",
            }
        elif ns == NAMESPACE_QWEN:
            catalog = list(fireworks_catalog or [])
            row = last_list_for_namespace(ns, state_dir=state_dir) or {
                "namespace": ns,
                "items": catalog,
                "render_ts": time.time(),
                "list_id": "catalog-fallback",
            }
        else:
            row = last_list_for_namespace(ns, state_dir=state_dir)
            if not row:
                return None, "no_rendered_list"
            catalog = list(row.get("items") or [])
        if parsed.index:
            if not (1 <= parsed.index <= len(catalog)):
                return None, "index_out_of_range"
            model_id = str(catalog[parsed.index - 1])
            return {
                "namespace": ns,
                "model_id": model_id,
                "index": parsed.index,
                "list_row": row,
            }, ""
        if parsed.model_id:
            return {
                "namespace": ns,
                "model_id": parsed.model_id,
                "index": 0,
                "list_row": row,
            }, ""
        return None, "missing_selector"

    return None, "unsupported_parse"


def mutation_echo(
    binding: Dict[str, Any],
    *,
    format_model: Callable[[str], str],
) -> str:
    row = binding.get("list_row") or {}
    render_ts = float(row.get("render_ts") or time.time())
    ns = str(binding.get("namespace") or "")
    idx = int(binding.get("index") or 0)
    model_id = str(binding.get("model_id") or "")
    label = format_model(model_id) if model_id else "(default)"
    idx_part = f"{idx} → " if idx else ""
    return (
        f"Binding {idx_part}{label} ({namespace_title(ns)} from {format_render_clock(render_ts)}). "
        "Confirm?"
    )


def close_incident_if_spark_safe(
    *,
    binding: Dict[str, Any],
    claude_env_before: str,
    claude_env_after: str,
    state_dir: Path | str | None = None,
) -> Optional[Dict[str, Any]]:
    """Close p1 incident when bare 4 on cline list refused Claude mutation."""
    ns = str(binding.get("namespace") or "")
    idx = int(binding.get("index") or 0)
    model_id = str(binding.get("model_id") or "")
    if ns != NAMESPACE_CLINE or idx != 4 or "GPT-5.3-Codex-Spark" not in model_id:
        return None
    if claude_env_after != claude_env_before:
        return None
    return write_binding_receipt(
        action="incident_closed",
        payload={
            "incident_id": INCIDENT_P1_SPARK_MISBIND,
            "verdict": "REFUSED_CLAUDE_MUTATION",
            "resolved_model": model_id,
            "namespace": ns,
            "index": idx,
            "claude_pin_unchanged": True,
        },
        state_dir=state_dir,
    )