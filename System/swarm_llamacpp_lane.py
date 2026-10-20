"""swarm_llamacpp_lane — bonsai-2 NECENZURAT, prin PrismML llama.cpp (nu prin Ollama).

De ce există acest lane, măsurat pe GTH4921YP3 în 2026-10-18:

  1. Ollama 0.40.6 a scos suportul LoRA:  "LoRA adapters are no longer supported"
  2. Ollama nu poate citi pachetul ternary: "unsupported tensor output.weight size overflows"
  3. Adapterul lipit în Q2_0 și importat în Ollama a refuzat identic cu baza —
     direcția de refuz e legată de baza PTQ1_0, nu se transferă.

Deci adapterul rulează VIU pe un llama-server din fork-ul PrismML
(prism-b10777-e3de715), pe :8099, cu scala per-cerere. Acesta e singurul drum
către cortexul necenzurat, și de aceea `/cortex llm` are nevoie de el.

Contract identic cu swarm_mercury_lane.stream_chat:
    ("token", str) → ("done", full|None) | ("error", str)
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.parse
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, List, Optional

PREFIX = "llamacpp:"
DEFAULT_MODEL = "bonsai-uncensored"
BASE_URL = os.environ.get("SIFTA_LLAMACPP_URL", "http://127.0.0.1:8099").rstrip("/")

# Scale 1 = refuzuri 0% pe split-ul held-out al autorului; 0 = adapterul oprit.
# Peste 1 nu adaugă nimic și produce răspunsuri degenerate (măsurat de autori).
DEFAULT_SCALE = float(os.environ.get("SIFTA_LLAMACPP_SCALE", "1"))


def is_llamacpp(model: str) -> bool:
    """True pentru tag-urile care aparțin acestui lane (`llamacpp:...`)."""
    return str(model or "").strip().lower().startswith(PREFIX)


def strip_prefix(model: str) -> str:
    """`llamacpp:bonsai-uncensored` → `bonsai-uncensored` (numele de afișare)."""
    raw = str(model or "").strip()
    if raw.lower().startswith(PREFIX):
        return raw[len(PREFIX):].strip() or DEFAULT_MODEL
    return raw or DEFAULT_MODEL


_AVAIL_CACHE: tuple[float, bool] = (0.0, False)
_AVAIL_TTL_S = 2.0


def available(timeout: float = 0.25) -> bool:
    """Serverul răspunde? Verificat, nu presupus — un cortex mort nu trebuie listat.

    Probe with a bare TCP connect, not an HTTP GET. This is called while building
    the cortex menu, which runs on the Qt GUI thread; a full urllib round-trip
    there is a visible hitch every time the list is rebuilt, and a beachball if
    anything upstream is slow. A loopback connect is sub-millisecond when the
    server is up and fails instantly when it is not.

    Cached for a moment as well: the menu can be rebuilt several times in a row
    and there is no reason to probe the socket on each pass.
    """
    global _AVAIL_CACHE
    now = time.monotonic()
    cached_at, cached_val = _AVAIL_CACHE
    if now - cached_at < _AVAIL_TTL_S:
        return cached_val
    ok = False
    try:
        parsed = urllib.parse.urlsplit(BASE_URL)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, int(port)), timeout=timeout):
            ok = True
    except Exception:
        ok = False
    _AVAIL_CACHE = (now, ok)
    return ok


def _request(messages: List[Dict[str, Any]], model: str, *,
             max_tokens: int, temperature: float, scale: Optional[float]) -> Dict[str, Any]:
    body = {
        "messages": messages,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        # fără asta modelul își pune tot bugetul în `reasoning_content` și
        # întoarce `content` gol — arăta ca un refuz, era doar tăcere.
        "chat_template_kwargs": {"enable_thinking": False},
        "lora": [{"id": 0, "scale": float(DEFAULT_SCALE if scale is None else scale)}],
    }
    req = urllib.request.Request(
        f"{BASE_URL}/v1/chat/completions",
        json.dumps(body).encode("utf-8"),
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def stream_chat(messages: List[Dict[str, Any]], *, model: str = DEFAULT_MODEL,
                effort: str = "low", max_tokens: int = 1024,
                temperature: float = 0.7,
                scale: Optional[float] = None) -> Iterator[tuple[str, Any]]:
    """Yield the answer as one token then done — same shape as the Mercury lane.

    ``effort`` is accepted and ignored: keeping the signature identical is what
    lets the Talk widget treat this lane as a peer of the others.
    """
    try:
        data = _request(messages, strip_prefix(model), max_tokens=max_tokens,
                        temperature=temperature, scale=scale)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        yield ("error", f"llamacpp HTTP {exc.code}: {detail}")
        return
    except Exception as exc:
        yield ("error", f"llamacpp lane unavailable: {type(exc).__name__}: {exc}")
        return

    try:
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        text = (msg.get("content") or "").strip()
    except Exception:
        text = ""
    if not text:
        # Niciodată tăcere prefăcută în răspuns: gol înseamnă eroare, nu conformare.
        yield ("error", "llamacpp returned empty content (thinking may have eaten the budget)")
        return
    yield ("token", text)
    yield ("done", text)


def chat(messages: List[Dict[str, Any]], *, model: str = DEFAULT_MODEL,
         max_tokens: int = 1024, temperature: float = 0.7) -> str:
    """Non-streaming convenience. Returns '' on any failure (never raises)."""
    for kind, payload in stream_chat(messages, model=model, max_tokens=max_tokens,
                                     temperature=temperature):
        if kind == "done":
            return str(payload or "")
        if kind == "error":
            return ""
    return ""


class _OllamaCompatResponse:
    """Behaves like the object ``urllib.request.urlopen`` returns, for `with ... as resp`."""

    def __init__(self, lines):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def __iter__(self):
        return iter(self._lines)


def _ollama_compat_lines(messages: List[Dict[str, Any]], display: str,
                         max_tokens: int, temperature: float,
                         timeout: float):
    """Translate llama.cpp's SSE stream into Ollama /api/chat NDJSON lines.

    The Talk brain worker is written against Ollama's wire format — it parses
    ``{"message":{"content":...},"done":...}`` — and everything downstream of
    that parse (thinking recorder, receipts, lag stamps) depends on the shape.
    Rather than fork the worker, the lane speaks its dialect.
    """
    body = {
        "messages": messages,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "lora": [{"id": 0, "scale": float(DEFAULT_SCALE)}],
    }
    req = urllib.request.Request(
        f"{BASE_URL}/v1/chat/completions",
        json.dumps(body).encode("utf-8"),
        {"Content-Type": "application/json"},
    )
    # Fail fast rather than hang. A turn that waits on a dead cortex shows the
    # owner a frozen window and tells him nothing; an error line names the
    # problem in the first second and keeps the GUI responsive.
    if not available():
        yield (json.dumps({
            "error": f"llamacpp cortex offline at {BASE_URL} -- start the server, then retry",
        }) + "\n").encode("utf-8")
        return
    try:
        with urllib.request.urlopen(req, timeout=min(float(timeout), 90.0)) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    obj = json.loads(chunk)
                except Exception:
                    continue
                delta = (obj.get("choices") or [{}])[0].get("delta") or {}
                piece = delta.get("content") or ""
                if piece:
                    yield (json.dumps({
                        "model": display,
                        "message": {"role": "assistant", "content": piece},
                        "done": False,
                    }) + "\n").encode("utf-8")
    except Exception as exc:
        # An error line, never a silent empty answer.
        yield (json.dumps({"error": f"llamacpp lane: {type(exc).__name__}: {exc}"}) + "\n").encode("utf-8")
        return
    yield (json.dumps({
        "model": display,
        "message": {"role": "assistant", "content": ""},
        "done": True,
        "done_reason": "stop",
    }) + "\n").encode("utf-8")


def open_ollama_compat(body: bytes, model: str, *, timeout: float = 180.0):
    """Return an open-able, iterable response for an Ollama-style request body."""
    try:
        payload = json.loads((body or b"{}").decode("utf-8", "replace"))
    except Exception:
        payload = {}
    messages = payload.get("messages") or []
    options = payload.get("options") or {}
    return _OllamaCompatResponse(_ollama_compat_lines(
        messages,
        strip_prefix(model),
        int(options.get("num_predict") or 1024),
        float(options.get("temperature") or 0.7),
        float(timeout),
    ))


__all__ = [
    "PREFIX", "DEFAULT_MODEL", "BASE_URL", "DEFAULT_SCALE",
    "is_llamacpp", "strip_prefix", "available", "stream_chat", "chat",
    "open_ollama_compat",
]
