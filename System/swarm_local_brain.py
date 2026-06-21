#!/usr/bin/env python3
"""
System/swarm_local_brain.py — Ollama local backend for Alice.

Drop-in replacement / peer for swarm_gemini_brain.py.
Substrate-owned. No SaaS. No internet required after model pull.

Contract (mirrors swarm_gemini_brain surface for easy swapping):
    - is_available() -> bool
    - available_models() -> list[str]   (returns ["ollama:<name>", ...])
    - stream_chat(model, messages, *, request_tag=None, temperature=0.7, timeout_s=120)
        -> Iterator[Tuple[str, Any]]
        Yields:
            ("token", str)   — incremental text
            ("done", str)    — full accumulated response
            ("error", str)   — failure
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, List, Optional, Tuple

_OLLAMA_HOST = "http://localhost:11434"


def is_available() -> bool:
    """Quick TCP probe to see if Ollama daemon is listening."""
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=1.5):
            return True
    except Exception:
        return False


def available_models() -> List[str]:
    """Return models in the format the rest of the system expects."""
    if not is_available():
        return []
    try:
        with urllib.request.urlopen(f"{_OLLAMA_HOST}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = []
        for m in data.get("models", []):
            name = m.get("name", "")
            if name:
                models.append(f"ollama:{name}")
        return models
    except Exception:
        return []


def _to_ollama_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Convert our standard [{"role": "...", "content": "..."}] to Ollama format."""
    out = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            out.append({"role": "system", "content": content})
        elif role == "assistant":
            out.append({"role": "assistant", "content": content})
        else:
            out.append({"role": "user", "content": content})
    return out


def stream_chat(
    model: str,
    messages: List[Dict[str, str]],
    *,
    request_tag: Optional[str] = None,
    temperature: float = 0.7,
    timeout_s: int = 180,
) -> Iterator[Tuple[str, Any]]:
    """
    Stream chat from local Ollama.
    Yields ("token", text_chunk) and finally ("done", full_text).
    """
    if not is_available():
        yield ("error", "Ollama daemon not reachable on localhost:11434")
        return

    # Strip "ollama:" prefix if present
    bare_model = model.split(":", 1)[1] if model.startswith("ollama:") else model
    if not bare_model:
        try:
            from System.sifta_inference_defaults import resolve_live_local_ollama_default

            bare_model = resolve_live_local_ollama_default()
        except Exception:
            bare_model = "alice-m5-cortex-8b-6.3gb:latest"

    payload = {
        "model": bare_model,
        "messages": _to_ollama_messages(messages),
        "stream": True,
        "options": {
            "temperature": float(temperature),
            "num_ctx": 8192,
            "num_predict": 700,
        },
    }

    url = f"{_OLLAMA_HOST}/api/chat"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")

    full_text = []
    tag = request_tag or f"local-ollama-{int(time.time())}"

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            for raw_line in resp:
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if "message" in chunk and "content" in chunk["message"]:
                    token = chunk["message"]["content"]
                    if token:
                        full_text.append(token)
                        yield ("token", token)

                if chunk.get("done", False):
                    complete = "".join(full_text)
                    yield ("done", complete)
                    # TODO: could emit usage here later for STGM accounting
                    return

    except urllib.error.URLError as e:
        yield ("error", f"Ollama request failed: {e}")
    except Exception as e:
        yield ("error", f"Unexpected error talking to Ollama: {type(e).__name__}: {e}")


# Convenience for sifta_app.py selection logic
def get_default_model() -> str:
    try:
        from System.sifta_inference_defaults import resolve_live_local_ollama_default

        live = resolve_live_local_ollama_default()
        if live:
            return f"ollama:{live}"
    except Exception:
        pass
    models = available_models()
    if models:
        return models[0]
    return "ollama:alice-m5-cortex-8b-6.3gb:latest"
