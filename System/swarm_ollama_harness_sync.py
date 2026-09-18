"""Keep the local DeepSeek Harness Ollama registry aligned with Ollama.

Ollama is the source of truth for installed local weights.  DeepSeek Harness
has its own user-facing model registry, so a freshly pulled model otherwise
remains invisible there until someone edits ``~/.dsh/settings.yaml``.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Iterable

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - damaged boot path
    append_line_locked = None  # type: ignore[assignment]


_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
_DEFAULT_SETTINGS = Path.home() / ".dsh" / "settings.yaml"
_SYNC_LEDGER = _STATE / "ollama_harness_sync.jsonl"
_OLLAMA_HOST = "http://127.0.0.1:11434"


def _yaml_scalar(value: str) -> str:
    """Quote a YAML scalar without requiring PyYAML on another machine."""
    return json.dumps(str(value), ensure_ascii=False)


def _context_for_model(name: str) -> tuple[int, int]:
    low = name.lower()
    if "minicpm" in low or "vision" in low or "qwen-vl" in low:
        return 40960, 8192
    return 32768, 8192


def _model_rows(payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    if not isinstance(payload, dict):
        return rows
    for item in payload.get("models") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("model") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        context, max_tokens = _context_for_model(name)
        rows.append({
            "id": name,
            "name": name,
            "contextWindow": context,
            "maxTokens": max_tokens,
            "sizeBytes": int(item.get("size") or 0),
        })
    return rows


def read_ollama_inventory(*, host: str = _OLLAMA_HOST, timeout: float = 3.0) -> list[dict[str, Any]]:
    """Read the live Ollama inventory; return an empty list on offline Ollama."""
    try:
        request = urllib.request.Request(
            f"{host.rstrip('/')}/api/tags",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as handle:
            return _model_rows(json.loads(handle.read().decode("utf-8", "replace")))
    except Exception:
        return []


def _models_yaml(rows: Iterable[dict[str, Any]]) -> str:
    lines = ["      models:"]
    for row in rows:
        size = int(row.get("sizeBytes") or 0)
        label = str(row['name']) + (f" ({size / 1_000_000_000:.1f} GB)" if size else "")
        lines.extend(
            [
                f"        - id: {_yaml_scalar(str(row['id']))}",
                f"          name: {_yaml_scalar(label)}",
                f"          contextWindow: {int(row['contextWindow'])}",
                f"          maxTokens: {int(row['maxTokens'])}",
            ]
        )
    return "\n".join(lines)


def _block_end(lines: list[str], start: int, indent: int) -> int:
    return next((i for i in range(start + 1, len(lines))
                 if lines[i].strip() and not lines[i].lstrip().startswith("#")
                 and len(lines[i]) - len(lines[i].lstrip()) <= indent), len(lines))


def _scalar(text: str) -> str:
    value = text.strip()
    try:
        return str(json.loads(value))
    except (ValueError, TypeError):
        return value.strip("'")


def _replace_local_ollama_models(text: str, rows: list[dict[str, Any]]) -> str:
    """Replace only the local-ollama models list, preserving the rest of YAML."""
    lines = text.splitlines()
    provider_start = next(
        (i for i, line in enumerate(lines) if line.startswith("    local-ollama:")
         and "providers:" in "\n".join(lines[max(0, i - 4):i])),
        None,
    )
    if provider_start is None:
        provider_start = next((i for i, line in enumerate(lines) if line.startswith("    local-ollama:")), None)
    if provider_start is None:
        raise ValueError("local-ollama provider not found")

    provider_end = _block_end(lines, provider_start, 4)
    model_start = next(
        (i for i in range(provider_start + 1, provider_end) if lines[i] == "      models:"),
        None,
    )
    if model_start is None:
        raise ValueError("local-ollama models block not found")

    model_end = min(_block_end(lines, model_start, 6), provider_end)
    # Keep per-model capabilities and user context limits when the tag survives.
    starts = [i for i in range(model_start + 1, model_end) if lines[i].startswith("        - id:")]
    existing = {}
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else model_end
        existing[_scalar(lines[start].split("id:", 1)[1])] = lines[start:end]
    replacement = ["      models:"]
    for row in rows:
        block = list(existing.get(str(row["id"]), []))
        generated = _models_yaml([row]).splitlines()[1:]
        if not block:
            replacement.extend(generated)
            continue
        name_line = next((i for i, line in enumerate(block) if line.startswith("          name:")), None)
        if name_line is None:
            block.insert(1, generated[1])
        else:
            block[name_line] = generated[1]
        replacement.extend(block)
    out = lines[:model_start] + replacement + lines[model_end:]
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _repair_missing_default(text: str, rows: list[dict[str, Any]]) -> tuple[str, str, str]:
    """Preserve a missing selection; model changes require explicit owner choice."""
    live = {str(row.get("id") or "") for row in rows}
    lines = text.splitlines()
    marker = next((i for i, line in enumerate(lines) if line == "agent-default-model:"), None)
    if marker is None:
        return text, "", ""
    end = _block_end(lines, marker, 0)
    provider = next((_scalar(line.split(":", 1)[1]) for line in lines[marker + 1:end]
                     if line.startswith("  provider:")), "")
    if provider != "local-ollama":
        return text, "", ""
    model_line = next(
        (i for i in range(marker + 1, end) if lines[i].startswith("  model:")
         and not lines[i].startswith("    ")),
        None,
    )
    if model_line is None:
        return text, "", ""
    old = _scalar(lines[model_line].split(":", 1)[1])
    if old in live or not rows:
        return text, old, old
    # Never silently swap the owner's cortex to whichever model happens to be
    # first in /api/tags. The UI can surface this exact unavailable selection
    # and ask for an explicit fallback.
    return text, old, old


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp_name = handle.name
    os.chmod(temp_name, mode)
    os.replace(temp_name, path)


def sync_local_ollama_harness(
    *,
    settings_path: Path | str | None = None,
    inventory: list[dict[str, Any]] | None = None,
    host: str = _OLLAMA_HOST,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Synchronize Harness's local Ollama provider with live installed models."""
    path = Path(settings_path or _DEFAULT_SETTINGS).expanduser()
    rows = list(inventory) if inventory is not None else read_ollama_inventory(host=host, timeout=timeout)
    report: dict[str, Any] = {
        "schema": "SIFTA_OLLAMA_HARNESS_SYNC_V1",
        "ts": time.time(),
        "settings_path": str(path),
        "ollama_models": [str(row.get("id") or "") for row in rows],
        "model_count": len(rows),
        "sizes_gb": {str(row["id"]): round(int(row.get("sizeBytes") or 0) / 1_000_000_000, 1) for row in rows},
        "ok": False,
        "changed": False,
    }
    if not rows:
        report["reason"] = "ollama_offline_or_empty"
    elif not path.exists():
        report["reason"] = "harness_settings_missing"
    else:
        original = path.read_text(encoding="utf-8")
        updated = _replace_local_ollama_models(original, rows)
        updated, default_before, default_after = _repair_missing_default(updated, rows)
        report["default_before"] = default_before
        report["default_after"] = default_after
        report["default_repaired"] = bool(default_before and default_after and default_before != default_after)
        report["default_unavailable"] = bool(default_before and default_before not in report["ollama_models"])
        report["changed"] = updated != original
        if updated != original:
            _write_atomic(path, updated)
        report["ok"] = True
        report["reason"] = "synced"
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        if append_line_locked is not None:
            append_line_locked(_SYNC_LEDGER, json.dumps(report, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return report


__all__ = ["read_ollama_inventory", "sync_local_ollama_harness"]
