"""Local LM Studio OpenAI-compatible cortex adapter.

The adapter keeps LM Studio models separate from Ollama tags.  A SIFTA model
reference has the form ``lmstudio:<server-model-id>`` and is routed to the
LM Studio local server, normally ``http://127.0.0.1:1234/v1``.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping, Sequence
from typing import Any


LMSTUDIO_MODEL_TAG = "lmstudio:prism-ml/Ternary-Bonsai-27B-mlx-2bit"
LMSTUDIO_MODEL_ID = "prism-ml/Ternary-Bonsai-27B-mlx-2bit"
LMSTUDIO_BASE_URL = "http://127.0.0.1:1234/v1"


def is_lmstudio_model(model: str) -> bool:
    return str(model or "").strip().lower().startswith("lmstudio:")


def model_id_for_tag(model: str) -> str:
    value = str(model or "").strip()
    return value.split(":", 1)[1].strip() if is_lmstudio_model(value) else value


def base_url() -> str:
    return os.environ.get("SIFTA_LMSTUDIO_BASE_URL", LMSTUDIO_BASE_URL).rstrip("/")


def _json_request(path: str, *, timeout: float = 2.0) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url()}{path}",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
    return payload if isinstance(payload, dict) else {}


def advertised_models(*, timeout: float = 2.0) -> list[str]:
    """Return model ids advertised by the live LM Studio server."""
    try:
        payload = _json_request("/models", timeout=timeout)
    except Exception:
        return []
    rows = payload.get("data")
    if not isinstance(rows, list):
        return []
    result: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        model = str(row.get("id") or row.get("model") or "").strip()
        if model and model not in result:
            result.append(model)
    return result


def model_available(model: str = LMSTUDIO_MODEL_TAG, *, timeout: float = 2.0) -> bool:
    target = model_id_for_tag(model)
    return target in advertised_models(timeout=timeout)


def _message_for_openai(message: Mapping[str, Any]) -> dict[str, Any]:
    """Keep SIFTA history JSON-compatible with OpenAI-style local servers."""
    result = {
        "role": str(message.get("role") or "user"),
        "content": message.get("content") or "",
    }
    # Preserve already-normalized multimodal content when a vision-capable
    # model supplies it. Unknown SIFTA bookkeeping keys stay out of the wire.
    if isinstance(result["content"], list):
        result["content"] = list(result["content"])
    return result


def stream_chat(
    model: str,
    history: Sequence[Mapping[str, Any]],
    *,
    temperature: float = 0.7,
    timeout_s: float = 300.0,
    max_tokens: int = 4096,
) -> Iterator[tuple[str, Any]]:
    """Stream ``(token|done|error, payload)`` events from LM Studio."""
    model_id = model_id_for_tag(model)
    payload = {
        "model": model_id,
        "messages": [_message_for_openai(item) for item in history],
        "stream": True,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
    }
    request = urllib.request.Request(
        f"{base_url()}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=float(timeout_s)) as response:
            for raw_line in response:
                if time.monotonic() - started > float(timeout_s):
                    yield "error", f"LM Studio timed out after {timeout_s}s"
                    return
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    yield "done", None
                    return
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") if isinstance(chunk, Mapping) else None
                choice = choices[0] if isinstance(choices, list) and choices else {}
                delta = choice.get("delta") if isinstance(choice, Mapping) else {}
                text = delta.get("content") if isinstance(delta, Mapping) else ""
                if text:
                    yield "token", str(text)
        yield "done", None
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:600]
        except Exception:
            detail = str(exc)
        yield "error", f"LM Studio HTTP {exc.code}: {detail or exc.reason}"
    except Exception as exc:
        yield "error", f"LM Studio unavailable at {base_url()}: {type(exc).__name__}: {exc}"


__all__ = [
    "LMSTUDIO_BASE_URL",
    "LMSTUDIO_MODEL_ID",
    "LMSTUDIO_MODEL_TAG",
    "advertised_models",
    "base_url",
    "is_lmstudio_model",
    "model_available",
    "model_id_for_tag",
    "stream_chat",
]
