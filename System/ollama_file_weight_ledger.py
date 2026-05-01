#!/usr/bin/env python3
"""
Read-only Ollama file-weight probe for Event 85.

The probe observes `/api/tags` and appends one ledger row per Ollama tag with
`file_weight_mb`. It never invokes `ollama show`, pulls models, deletes models,
or activates a global mesh scalar. This is instrumentation only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from collections.abc import Iterable as AbcIterable
from pathlib import Path
from typing import Any, Iterable, Mapping

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.ledger_append import append_jsonl_line

SCHEMA = "SIFTA_OLLAMA_FILE_WEIGHT_LEDGER_V1"
DEFAULT_TAGS_URL = "http://127.0.0.1:11434/api/tags"
DEFAULT_LEDGER_PATH = _REPO / ".sifta_state" / "ollama_file_weight_ledger.jsonl"


def _now() -> float:
    return time.time()


def _size_bytes(model: Mapping[str, Any]) -> int:
    raw = model.get("size", model.get("size_bytes", 0))
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Ollama model size must be an integer byte count, got {raw!r}") from exc
    if value < 0:
        raise ValueError(f"Ollama model size must be non-negative, got {value!r}")
    return value


def _row_hash(row: Mapping[str, Any]) -> str:
    body = json.dumps(dict(row), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def fetch_ollama_tags(source_url: str = DEFAULT_TAGS_URL, timeout: float = 2.0) -> dict[str, Any]:
    """Fetch the local Ollama tags payload through the read-only HTTP API."""
    req = urllib.request.Request(source_url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ollama_file_weight_rows_from_payload(
    payload: Mapping[str, Any],
    *,
    trace_id: str = "",
    source_url: str = DEFAULT_TAGS_URL,
    ts: float | None = None,
) -> list[dict[str, Any]]:
    """Convert an Ollama `/api/tags` payload into one row per model tag."""
    observed_ts = _now() if ts is None else ts
    rows: list[dict[str, Any]] = []
    models = payload.get("models", [])
    if not isinstance(models, AbcIterable) or isinstance(models, (str, bytes)):
        raise ValueError("Ollama tags payload must contain a list-like 'models' value")

    for model in sorted((dict(item) for item in models), key=lambda item: str(item.get("name") or item.get("model") or "")):
        name = str(model.get("name") or model.get("model") or "").strip()
        if not name:
            raise ValueError(f"Ollama model row missing name/model field: {model!r}")
        size = _size_bytes(model)
        row = {
            "ts": observed_ts,
            "event": "OLLAMA_FILE_WEIGHT_PROBE",
            "schema": SCHEMA,
            "trace_id": trace_id,
            "tag": name,
            "model": str(model.get("model") or name),
            "digest": str(model.get("digest") or ""),
            "modified_at": str(model.get("modified_at") or ""),
            "size_bytes": size,
            "file_weight_mb": round(size / (1024 * 1024), 3),
            "file_weight_unit": "MiB",
            "source_url": source_url,
            "read_only_probe": True,
            "no_global_mesh_scalar": True,
        }
        row["row_hash"] = _row_hash(row)
        rows.append(row)
    return rows


def append_ollama_file_weight_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
) -> list[dict[str, Any]]:
    """Append prepared file-weight rows to the JSONL ledger."""
    appended: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        append_jsonl_line(ledger_path, payload)
        appended.append(payload)
    return appended


def probe_and_append_ollama_file_weights(
    *,
    trace_id: str = "",
    source_url: str = DEFAULT_TAGS_URL,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
    timeout: float = 2.0,
) -> list[dict[str, Any]]:
    payload = fetch_ollama_tags(source_url, timeout=timeout)
    rows = ollama_file_weight_rows_from_payload(payload, trace_id=trace_id, source_url=source_url)
    return append_ollama_file_weight_rows(rows, ledger_path=ledger_path)


def _tail_jsonl(path: Path, count: int = 3) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    out: list[dict[str, Any]] = []
    for line in lines[-count:]:
        out.append(json.loads(line))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append read-only Ollama file_weight_mb rows.")
    parser.add_argument("--trace-id", default="", help="Registration trace id to bind to rows.")
    parser.add_argument("--source-url", default=DEFAULT_TAGS_URL, help="Read-only Ollama /api/tags URL.")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH), help="Target JSONL ledger path.")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--tail", type=int, default=3, help="Number of appended ledger rows to print.")
    args = parser.parse_args(argv)

    ledger = Path(args.ledger)
    rows = probe_and_append_ollama_file_weights(
        trace_id=args.trace_id,
        source_url=args.source_url,
        ledger_path=ledger,
        timeout=args.timeout,
    )
    summary = {
        "ok": True,
        "event": "OLLAMA_FILE_WEIGHT_PROBE_SUMMARY",
        "schema": SCHEMA,
        "trace_id": args.trace_id,
        "ledger": str(ledger),
        "rows_appended": len(rows),
        "sample_tail": _tail_jsonl(ledger, max(args.tail, 0)),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
