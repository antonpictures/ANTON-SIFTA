#!/usr/bin/env python3
"""
swarm_inference_model_inventory.py — installed model bodies, separated by runtime.

The Settings page must not flatten MLX, GGUF/Ollama, llama.cpp, vLLM, and
HDD-only files into one vague "model" word. This organ scans installed/runtime
surfaces and returns owner-facing rows with backend, size, path, quant, and
whether the row is directly selectable today.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parent.parent

_MODEL_EXTS = (".gguf", ".safetensors", ".mlx")
_QUANT_RE = re.compile(
    r"(UD-)?(?:IQ\d(?:_[A-Z0-9]+)+|Q\d(?:_[A-Z0-9]+)+|Q\d_K_[A-Z]+|Q\d_[01]|Q\d_NL|BF16|F16)",
    re.IGNORECASE,
)

GEMMA4_QAT_CANDIDATES: tuple[dict[str, Any], ...] = (
    {
        "id": "gemma-4-E2B-it-qat-GGUF",
        "repo": "unsloth/gemma-4-E2B-it-qat-GGUF",
        "runtime": "GGUF / llama.cpp / Unsloth Studio",
        "quant": "UD-Q4_K_XL",
        "memory_gb": 3.0,
        "disk_gb": 2.62,
        "mean_kld": 0.00173,
        "top1_pct": 98.16,
        "modalities": "text/image/audio",
        "sifta_role": "tiny local reflex/mobile test; not enough alone for primary Alice personality",
    },
    {
        "id": "gemma-4-E4B-it-qat-GGUF",
        "repo": "unsloth/gemma-4-E4B-it-qat-GGUF",
        "runtime": "GGUF / llama.cpp / Unsloth Studio",
        "quant": "UD-Q4_K_XL",
        "memory_gb": 5.0,
        "disk_gb": 4.22,
        "mean_kld": 0.00121,
        "top1_pct": 98.54,
        "modalities": "text/image/audio",
        "sifta_role": "cheap multimodal reflex / fast local lab candidate",
    },
    {
        "id": "gemma-4-12B-it-qat-GGUF",
        "repo": "unsloth/gemma-4-12B-it-qat-GGUF",
        "runtime": "GGUF / llama.cpp / Unsloth Studio",
        "quant": "UD-Q4_K_XL",
        "memory_gb": 7.0,
        "disk_gb": 6.72,
        "mean_kld": 0.13288,
        "top1_pct": 88.76,
        "modalities": "text/image/audio",
        "sifta_role": "best first GGUF candidate to test against current 8B and MLX 12B; smaller than older Q6_K lane",
    },
    {
        "id": "gemma-4-26B-A4B-it-qat-GGUF",
        "repo": "unsloth/gemma-4-26B-A4B-it-qat-GGUF",
        "runtime": "GGUF / llama.cpp / Unsloth Studio",
        "quant": "UD-Q4_K_XL",
        "memory_gb": 15.0,
        "disk_gb": 14.25,
        "mean_kld": 0.09788,
        "top1_pct": 85.63,
        "modalities": "text/image",
        "sifta_role": "heavy M5 teacher/agentic-coding candidate; test only with RAM/context receipts",
    },
    {
        "id": "gemma-4-31B-it-qat-GGUF",
        "repo": "unsloth/gemma-4-31B-it-qat-GGUF",
        "runtime": "GGUF / llama.cpp / Unsloth Studio",
        "quant": "UD-Q4_K_XL",
        "memory_gb": 18.0,
        "disk_gb": 17.29,
        "mean_kld": 0.01403,
        "top1_pct": 96.67,
        "modalities": "text/image",
        "sifta_role": "quality ceiling candidate; risky on 24GB desktop unless idle and short context",
    },
)


def bytes_label(size_bytes: int | float | None) -> str:
    try:
        n = float(size_bytes or 0)
    except Exception:
        n = 0.0
    if n <= 0:
        return "size unknown"
    if n >= 1024**3:
        return f"{n / 1024**3:.2f} GB"
    if n >= 1024**2:
        return f"{n / 1024**2:.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{int(n)} B"


def guess_quant(name_or_path: str) -> str:
    text = str(name_or_path or "")
    match = _QUANT_RE.search(text)
    return match.group(0).upper() if match else ""


def runtime_availability() -> dict[str, bool]:
    return {
        "ollama": bool(shutil.which("ollama")),
        "llama.cpp": bool(shutil.which("llama-server") or shutil.which("llama-cli")),
        "mlx": bool(shutil.which("python3")),
        "vllm": bool(shutil.which("vllm")),
        "unsloth": bool(shutil.which("unsloth")),
        "litert-lm": bool(shutil.which("litert-lm")),
    }


def _ollama_rows(timeout: float = 2.0) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        for item in payload.get("models", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            size = int(item.get("size") or 0)
            rows.append(
                {
                    "id": name,
                    "name": name,
                    "backend": "ollama",
                    "runtime": "Ollama / GGUF runtime",
                    "source": "ollama_api",
                    "location": "ollama://local",
                    "size_bytes": size,
                    "size_label": bytes_label(size),
                    "quant": guess_quant(name),
                    "selectable": True,
                    "selectable_value": name,
                    "status": "ready",
                    "advice": "Directly selectable in Alice cortex settings.",
                }
            )
        return rows
    except Exception:
        pass

    if not shutil.which("ollama"):
        return rows
    try:
        out = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return rows
    for line in out.splitlines()[1:]:
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        rows.append(
            {
                "id": name,
                "name": name,
                "backend": "ollama",
                "runtime": "Ollama / GGUF runtime",
                "source": "ollama_list",
                "location": "ollama://local",
                "size_bytes": 0,
                "size_label": "size unknown",
                "quant": guess_quant(name),
                "selectable": True,
                "selectable_value": name,
                "status": "ready",
                "advice": "Directly selectable in Alice cortex settings.",
            }
        )
    return rows


def default_scan_roots() -> list[Path]:
    home = Path.home()
    candidates = [
        REPO / "models",
        REPO / "gallery-main",
        home / "models",
        home / "Downloads",
        home / ".cache" / "huggingface" / "hub",
        home / "Library" / "Caches" / "huggingface" / "hub",
        home / "Library" / "Application Support" / "LM Studio" / "models",
    ]
    seen: set[str] = set()
    roots: list[Path] = []
    for root in candidates:
        try:
            resolved = str(root.expanduser().resolve())
        except Exception:
            resolved = str(root.expanduser())
        if resolved in seen or not root.exists():
            continue
        seen.add(resolved)
        roots.append(root)
    return roots


def _iter_model_files(roots: Iterable[Path], *, max_files: int = 800) -> Iterable[Path]:
    count = 0
    for root in roots:
        if count >= max_files:
            break
        try:
            iterator = root.rglob("*")
        except Exception:
            continue
        for path in iterator:
            if count >= max_files:
                break
            try:
                if not path.is_file():
                    continue
            except Exception:
                continue
            # Hugging Face cache uses .no_exist marker folders for files that
            # are explicitly absent. They are not model bodies and must not
            # appear as selectable Alice cortex candidates.
            if ".no_exist" in path.parts:
                continue
            low = path.name.lower()
            if not low.endswith(_MODEL_EXTS):
                continue
            count += 1
            yield path


def _hf_snapshot_label(path: Path) -> str | None:
    parts = list(path.parts)
    for idx, part in enumerate(parts):
        if not part.startswith("models--"):
            continue
        model_id = part.removeprefix("models--").replace("--", "/")
        snapshot = ""
        if idx + 2 < len(parts) and parts[idx + 1] == "snapshots":
            snapshot = parts[idx + 2][:8]
        return f"{model_id} @{snapshot}" if snapshot else model_id
    return None


def _file_rows(roots: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    safetensor_dirs: set[str] = set()
    for path in _iter_model_files(roots):
        try:
            resolved = str(path.resolve())
            size = path.stat().st_size
        except Exception:
            resolved = str(path)
            size = 0
        if resolved in seen:
            continue
        ext = path.suffix.lower()
        quant = guess_quant(path.name)
        if ext == ".gguf":
            seen.add(resolved)
            backend = "gguf"
            runtime = "llama.cpp / Ollama / Unsloth Studio"
            status = "hdd_only"
            advice = "GGUF body found on disk. Register it in Ollama or start llama-server before selecting as a live cortex."
            selectable = False
            selectable_value = ""
            row_id = path.name
            location = resolved
            size_bytes = size
        elif ext == ".safetensors":
            try:
                parent = path.parent.resolve()
                parent_key = str(parent)
            except Exception:
                parent = path.parent
                parent_key = str(parent)
            if parent_key in safetensor_dirs:
                continue
            safetensor_dirs.add(parent_key)
            files = []
            try:
                files = [p for p in parent.glob("*.safetensors") if p.is_file()]
            except Exception:
                files = [path]
            try:
                size_bytes = sum(p.stat().st_size for p in files)
            except Exception:
                size_bytes = size
            backend = "mlx_safetensors"
            runtime = "MLX / Transformers safetensors candidate"
            has_config = (parent / "config.json").exists()
            status = "installed_candidate" if has_config else "component_or_cache"
            advice = (
                "Safetensors model body found on disk. Visible for inventory/testing, "
                "but not directly selectable as Alice's cortex until a supported MLX/"
                "Transformers runner is wired and receipt-tested."
                if has_config
                else "Safetensors component/cache found. Not enough evidence for a complete model layout; do not select as cortex."
            )
            selectable = False
            selectable_value = ""
            label = _hf_snapshot_label(parent) or parent.name
            row_id = f"{label} ({len(files)} safetensors)"
            location = parent_key
        else:
            seen.add(resolved)
            backend = "mlx"
            runtime = "MLX local artifact candidate"
            status = "installed_candidate"
            advice = "MLX artifact found on disk. Visible for inventory/testing; wire a supported runner before selecting as a live cortex."
            selectable = False
            selectable_value = ""
            row_id = path.name
            location = resolved
            size_bytes = size

        rows.append(
            {
                "id": row_id,
                "name": row_id,
                "backend": backend,
                "runtime": runtime,
                "source": "hdd_scan",
                "location": location,
                "size_bytes": size_bytes,
                "size_label": bytes_label(size_bytes),
                "quant": quant,
                "selectable": selectable,
                "selectable_value": selectable_value,
                "status": status,
                "advice": advice,
            }
        )
    return rows


def list_inference_model_inventory(
    *,
    roots: Iterable[str | Path] | None = None,
    include_ollama: bool = True,
) -> list[dict[str, Any]]:
    """Return installed model bodies with runtime labels for Settings/Matrix."""
    scan_roots = [Path(p).expanduser() for p in (roots if roots is not None else default_scan_roots())]
    rows: list[dict[str, Any]] = []
    if include_ollama:
        rows.extend(_ollama_rows())
    rows.extend(_file_rows(scan_roots))

    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("backend") or ""), str(row.get("id") or ""), str(row.get("location") or ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    unique.sort(
        key=lambda r: (
            0 if r.get("selectable") else 1,
            str(r.get("backend") or ""),
            -int(r.get("size_bytes") or 0),
            str(r.get("id") or "").lower(),
        )
    )
    return unique


def format_inventory_label(row: dict[str, Any]) -> str:
    backend = str(row.get("backend") or "model")
    name = str(row.get("id") or row.get("name") or "unknown")
    size = str(row.get("size_label") or bytes_label(row.get("size_bytes")))
    quant = str(row.get("quant") or "").strip()
    status = "ready/selectable" if row.get("selectable") else str(row.get("status") or "inventory only")
    suffix = f" · {quant}" if quant else ""
    return f"{backend} · {name}{suffix} · {size} · {status}"


def inventory_detail_text(row: dict[str, Any]) -> str:
    if not row:
        return "No model body selected."
    parts = [
        f"Runtime: {row.get('runtime') or row.get('backend') or 'unknown'}",
        f"Status: {row.get('status') or 'unknown'}",
        f"Size: {row.get('size_label') or bytes_label(row.get('size_bytes'))}",
    ]
    if row.get("quant"):
        parts.append(f"Quant: {row.get('quant')}")
    if row.get("location"):
        parts.append(f"Location: {row.get('location')}")
    if row.get("selectable_value"):
        parts.append(f"Selectable value: {row.get('selectable_value')}")
    if row.get("advice"):
        parts.append(str(row.get("advice")))
    return "\n".join(parts)


def inference_runtime_nuggets() -> list[str]:
    return [
        "MLX/safetensors is the Apple Silicon path, but a safetensors folder is only an installed body/candidate until a supported runner is wired and receipt-tested.",
        "GGUF is a llama.cpp/Ollama/Unsloth Studio body format. It can be excellent for portable local inference, but it must be registered or served before Alice can route to it.",
        "vLLM is a server runtime, not a file format. Treat it as a provider endpoint when running on suitable GPU/server hardware.",
        "Unsloth Dynamic 2.0 quants are model/layer-specific; judge them by KL divergence/flip risk and task tests, not only disk size or MMLU headline.",
        "Gemma 4 QAT changes the test order: 12B QAT is a 7GB first GGUF candidate; 26B-A4B QAT is a 15GB heavy teacher; 31B QAT is quality-ceiling but RAM-risky.",
        "Gemma 4 12B Unified GGUF is worth testing for one-body text/image/audio cognition, but Settings must label the runtime and selected quant clearly.",
    ]


def gemma4_qat_candidate_table() -> list[dict[str, Any]]:
    """Return current owner-facing Gemma 4 QAT candidates for matrix/settings notes.

    Values are copied from the current Unsloth QAT page/collection and are used as
    planning metadata only. A candidate is not promoted until SIFTA has runtime
    receipts for memory, latency, and task quality on this M5.
    """
    return [dict(row) for row in GEMMA4_QAT_CANDIDATES]


__all__ = [
    "bytes_label",
    "format_inventory_label",
    "gemma4_qat_candidate_table",
    "guess_quant",
    "inference_runtime_nuggets",
    "inventory_detail_text",
    "list_inference_model_inventory",
    "runtime_availability",
]
