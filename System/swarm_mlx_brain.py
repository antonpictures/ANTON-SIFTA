"""swarm_mlx_brain.py — Alice's local MLX cortex backend (mlx-omni-server).

George + brother IDE doctor (2026-06-02): the new uncensored vision cortexes
(osmQwopus, osmKeye and siblings with vision tower) are MLX-native — they run on the
M5 through mlx-omni-server's OpenAI-compatible endpoint
(default ``http://127.0.0.1:10240/v1``), NOT through Ollama. This module is the
body's hand to that server. It mirrors ``swarm_local_brain.py`` (Ollama) so the
cortex dispatcher in ``swarm_gemini_brain.stream_chat`` can stream from either with
the same ``("token" | "done" | "error")`` contract.

Text-only models (e.g. LFM2.5-8B-A1B with no vision tower) are deliberately not
grouped here; owner directive is vision-capable cortexes for body/screen/image
commands. Cortex names carry the ``mlx:`` prefix, e.g.
``mlx:osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-OptiQ-3.7bpw-mlx``.
``is_gemini_model()`` / ``is_cloud_model()`` in ``swarm_gemini_brain`` routes the
``mlx:`` family here (the same dispatcher already carries the local grok/codex/cline
CLIs, so a local MLX server fits the same lane). The picker lists whatever
``/v1/models`` reports — no hardcoding, the same discovery pattern as the Ollama tag
scan, honouring the Architect's "a dropdown to select the cortex, no hardcoding, I
want to try them all" rule (sifta_inference_defaults, 2026-05-15).

Truth boundary (cowork, 2026-06-02): written in the Cowork Linux sandbox.
mlx-omni-server is Apple-Silicon only, so this path is NOT runtime-verified here.
The unit tests cover the ``/v1/models`` parse, the chat payload, the SSE delta parse,
and the prefix handling with fixtures. End-to-end verification is on the M5 once
``mlx-omni-server`` is running. This is an IDE-doctor coordination patch, not an
Alice swimmer receipt.
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, List, Optional, Tuple

_DEFAULT_HOST = "http://127.0.0.1:10240"
_PREFIX = "mlx:"


def _host() -> str:
    """Owner-tunable mlx-omni-server base URL (no trailing slash)."""
    return os.environ.get("SIFTA_MLX_OMNI_HOST", _DEFAULT_HOST).rstrip("/")


def _host_port(host: str) -> Tuple[str, int]:
    """Crude (hostname, port) parse for the TCP reachability probe."""
    netloc = host.split("://", 1)[-1].split("/", 1)[0]
    if ":" in netloc:
        name, _, port = netloc.rpartition(":")
        try:
            return (name or "127.0.0.1"), int(port)
        except Exception:
            return (name or "127.0.0.1"), 10240
    return netloc or "127.0.0.1", 80


def is_available(timeout: float = 1.0) -> bool:
    """Quick TCP probe to see if mlx-omni-server is listening."""
    name, port = _host_port(_host())
    if name in ("localhost", ""):
        name = "127.0.0.1"
    try:
        with socket.create_connection((name, port), timeout=timeout):
            return True
    except Exception:
        return False


def strip_prefix(model: str) -> str:
    """``mlx:osmapi/foo`` -> ``osmapi/foo`` (the id mlx-omni-server expects)."""
    m = str(model or "").strip()
    return m[len(_PREFIX):] if m.lower().startswith(_PREFIX) else m


def available_models(timeout: float = 1.5) -> List[str]:
    """Discover models the local mlx-omni-server is serving (OpenAI ``/v1/models``).

    Returns ``mlx:<id>`` names so the cortex picker can list them with no hardcoding.
    Empty list if the server is down — the caller falls back to its canonical set.
    """
    if not is_available(timeout=timeout):
        return []
    try:
        req = urllib.request.Request(
            f"{_host()}/v1/models", headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as handle:
            payload = json.loads(handle.read().decode("utf-8", errors="replace"))
    except Exception:
        return []
    return parse_models_payload(payload)


def parse_models_payload(payload: Any) -> List[str]:
    """Pure parser for an OpenAI ``/v1/models`` body -> ``mlx:<id>`` names."""
    out: List[str] = []
    seen: set = set()
    data = payload.get("data") if isinstance(payload, dict) else None
    for entry in data or []:
        if not isinstance(entry, dict):
            continue
        mid = str(entry.get("id") or "").strip()
        if mid and mid not in seen:
            seen.add(mid)
            out.append(f"{_PREFIX}{mid}")
    return out


def _to_openai_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Normalise to OpenAI chat messages (keep system/assistant/user/tool roles)."""
    out: List[Dict[str, str]] = []
    for m in messages or []:
        role = m.get("role", "user")
        if role not in ("system", "assistant", "user", "tool"):
            role = "user"
        out.append({"role": role, "content": m.get("content", "")})
    return out


def parse_sse_line(line: str) -> Tuple[str, Any]:
    """Pure parser for one OpenAI SSE line.

    Returns one of: ("token", str) · ("done", None) · ("skip", None).
    Streaming chat completions arrive as ``data: {json}`` lines, terminated by
    ``data: [DONE]``.
    """
    s = (line or "").strip()
    if not s or not s.startswith("data:"):
        return ("skip", None)
    data = s[len("data:"):].strip()
    if data == "[DONE]":
        return ("done", None)
    try:
        chunk = json.loads(data)
        delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
        token = delta.get("content") or ""
    except Exception:
        token = ""
    if token:
        return ("token", token)
    return ("skip", None)


def stream_chat(
    model: str,
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.7,
    request_tag: Optional[str] = None,
    timeout_s: Optional[int] = 1800,
) -> Iterator[Tuple[str, Any]]:
    """Stream from mlx-omni-server (OpenAI ``/v1/chat/completions``, SSE).

    Yields ("token", chunk) ... then ("done", full_text); ("error", msg) on
    failure. Same contract as ``swarm_local_brain.stream_chat`` so the dispatcher
    is uniform. ``model`` may carry the ``mlx:`` prefix; it is stripped here.
    """
    if not is_available():
        yield (
            "error",
            f"mlx-omni-server not reachable at {_host()} — start it on the M5 with "
            f"`mlx-omni-server` (pip install mlx-omni-server).",
        )
        return

    bare = strip_prefix(model)
    payload = {
        "model": bare,
        "messages": _to_openai_messages(messages),
        "stream": True,
        "temperature": float(temperature),
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{_host()}/v1/chat/completions",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )

    full: List[str] = []
    _tag = request_tag or f"mlx-{int(time.time())}"
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            for raw in resp:
                if not raw:
                    continue
                kind, value = parse_sse_line(raw.decode("utf-8", errors="replace"))
                if kind == "token":
                    full.append(value)
                    yield ("token", value)
                elif kind == "done":
                    break
        yield ("done", "".join(full))
    except urllib.error.URLError as e:
        yield ("error", f"mlx-omni-server request failed: {e}")
    except Exception as e:
        yield ("error", f"Unexpected error talking to mlx-omni-server: {type(e).__name__}: {e}")


__all__ = [
    "is_available",
    "available_models",
    "parse_models_payload",
    "parse_sse_line",
    "strip_prefix",
    "stream_chat",
]
