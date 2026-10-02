#!/usr/bin/env python3
"""alice_local_cortex.py — llama.cpp as the body's own inference engine.

Architect, 2026-09-30: "do you know how to install, uninstall, use and all the
program builds unbuild whatever inside sifta so is available in case ollama
disappears? or whatever? llama.cpp?"

Ollama is a dependency, not a foundation. Tonight alone it retired a tag under us
(``qwen3.5:397b-cloud`` answered HTTP 410 Gone), 404'd a wrapper the Architect
asked for, and every cloud cortex needs an account with credit. This organ is the
answer to "what if it disappears": inference that runs on this silicon, from
weights already on this disk.

TWO FACTS MAKE THAT CHEAP HERE (both verified on this box):

  1. llama.cpp is installed already — ``/opt/homebrew/bin/llama-server``, version
     9700, built for Darwin arm64 with Metal. One engine stack, not Ollama.
  2. **Ollama's blob store IS GGUF.** The biggest blob begins with the bytes
     ``GGUF``. So the weights this body already pulled can be served by llama.cpp
     directly from ``~/.ollama/models/blobs/sha256-*``: no re-download, no
     conversion, no running Ollama, and it keeps working if the app is uninstalled
     (the blobs stay until someone deletes them).

WHAT THIS ORGAN OWNS
    Resolution of a model name to its GGUF path, a detached llama-server on a
    loopback port, a pidfile and a log, and an end-to-end verification that the
    server actually answers rather than merely listening.

WHAT IT DOES NOT OWN
    Model acquisition, quantization, or fine-tuning. If a model was never pulled,
    there is no blob to serve; that is a download, not a configuration.

Usage
    python3 System/alice_local_cortex.py list
    python3 System/alice_local_cortex.py start [model] [--port 8081]
    python3 System/alice_local_cortex.py status | verify | stop
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

_STATE = _ROOT / ".sifta_state"
_PID_FILE = _STATE / "local_cortex.pid"
_LOG_FILE = _STATE / "local_cortex.log"

_LLAMA_SERVER = "/opt/homebrew/bin/llama-server"
_OLLAMA_BLOBS = Path.home() / ".ollama" / "models" / "blobs"
_OLLAMA_MANIFESTS = Path.home() / ".ollama" / "models" / "manifests" / "registry.ollama.ai"

DEFAULT_PORT = 8081
DEFAULT_CTX = 8192
DEFAULT_GPU_LAYERS = 99
GGUF_MAGIC = b"GGUF"


def is_gguf(path: Path | str) -> bool:
    """True when the file starts with the GGUF magic — the only thing llama.cpp needs."""
    try:
        with Path(path).open("rb") as handle:
            return handle.read(4) == GGUF_MAGIC
    except OSError:
        return False


def available_models() -> dict[str, dict[str, Any]]:
    """Every Ollama model whose weights are a servable GGUF file on this disk.

    A manifest can name several layers; the largest is the weights. Cloud wrappers
    have no weights layer at all, so they simply do not appear here — correct,
    because a cloud model is the thing that disappears.
    """
    found: dict[str, dict[str, Any]] = {}
    if not _OLLAMA_MANIFESTS.exists():
        return found
    for manifest in _OLLAMA_MANIFESTS.rglob("*"):
        if not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # ValueError covers both bad JSON and a non-UTF-8 file: the manifest
            # tree also holds stray binary files, and one of them must not be able
            # to abort the whole inventory.
            continue
        layers = data.get("layers") or []
        if not layers:
            continue
        biggest = max(layers, key=lambda layer: int(layer.get("size") or 0))
        blob = _OLLAMA_BLOBS / str(biggest.get("digest") or "").replace("sha256:", "sha256-")
        size = int(biggest.get("size") or 0)
        if size < 100_000_000 or not blob.exists():
            continue
        name = manifest.relative_to(_OLLAMA_MANIFESTS).as_posix()
        if manifest.name == "latest":
            name = name[: -len("/latest")]
        found[name] = {"path": str(blob), "size_gb": round(size / 1e9, 2), "gguf": is_gguf(blob)}
    return found


def _llama_binary() -> str:
    """The engine: Homebrew's standalone llama.cpp build."""
    if Path(_LLAMA_SERVER).exists():
        return _LLAMA_SERVER
    found = shutil.which("llama-server")
    if found:
        return found
    raise FileNotFoundError("no llama-server found: install llama.cpp (brew install llama.cpp)")


def _running_pid() -> int | None:
    try:
        pid = int(_PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return pid


def _probe(port: int, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def start(
    model: str | None = None,
    *,
    port: int = DEFAULT_PORT,
    ctx: int = DEFAULT_CTX,
    gpu_layers: int = DEFAULT_GPU_LAYERS,
    wait_s: float = 60.0,
) -> dict[str, Any]:
    """Launch a detached llama-server. Returns the receipt, never a hopeful guess."""
    existing = _running_pid()
    if existing:
        return {"ok": True, "already_running": True, "pid": existing, "port": port}

    models = available_models()
    if not models:
        return {"ok": False, "error": "no servable GGUF found under the Ollama blob store"}

    def choose() -> str:
        """Prefer a coder, and among those the SMALLEST — a fallback must load fast.

        The harness row names ``qwen3.8-9b-coder``; picking the first name that
        contains "coder" instead loaded a 16.76 GB model into unified memory when a
        5.78 GB one was sitting right there, which is the wrong trade for a lane
        whose whole job is to exist when something else has failed.
        """
        coders = [(row["size_gb"], name) for name, row in models.items() if "coder" in name.lower()]
        if coders:
            return min(coders)[1]
        return min((row["size_gb"], name) for name, row in models.items())[1]

    chosen = model or choose()
    if chosen not in models:
        return {"ok": False, "error": f"unknown model {chosen!r}", "available": sorted(models)}
    if not models[chosen]["gguf"]:
        return {"ok": False, "error": f"{chosen} is not a GGUF file — llama.cpp cannot serve it"}

    _STATE.mkdir(parents=True, exist_ok=True)
    binary = _llama_binary()
    command = [
        binary, "-m", models[chosen]["path"],
        "--host", "127.0.0.1", "--port", str(port),
        "-c", str(ctx), "-ngl", str(gpu_layers), "-t", str(max(1, (os.cpu_count() or 4) // 2)),
        "--alias", "local-fallback",
    ]
    with _LOG_FILE.open("ab") as log:
        process = subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True, cwd=str(_ROOT),
        )
    _PID_FILE.write_text(str(process.pid), encoding="utf-8")

    deadline = time.time() + wait_s
    while time.time() < deadline:
        if process.poll() is not None:
            return {"ok": False, "error": "llama-server exited", "pid": process.pid, "log": str(_LOG_FILE)}
        if _probe(port):
            return {
                "ok": True, "pid": process.pid, "port": port, "model": chosen,
                "blob": models[chosen]["path"], "size_gb": models[chosen]["size_gb"],
                "binary": binary, "log": str(_LOG_FILE), "command": command,
            }
        time.sleep(1.0)
    return {"ok": False, "error": f"not answering on :{port} after {wait_s:.0f}s", "pid": process.pid, "log": str(_LOG_FILE)}


def stop(*, port: int = DEFAULT_PORT) -> dict[str, Any]:
    """Stop the server this organ started. Idempotent."""
    pid = _running_pid()
    if not pid:
        try:
            _PID_FILE.unlink()
        except OSError:
            pass
        return {"ok": True, "stopped": False, "detail": "nothing running"}
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    for _ in range(30):
        if not _probe(port, timeout=0.5):
            break
        time.sleep(0.5)
    try:
        _PID_FILE.unlink()
    except OSError:
        pass
    return {"ok": True, "stopped": True, "pid": pid}


def status(*, port: int = DEFAULT_PORT) -> dict[str, Any]:
    """What is actually running, and whether it answers."""
    pid = _running_pid()
    return {
        "pid": pid,
        "listening": _probe(port),
        "port": port,
        "pid_file": str(_PID_FILE),
        "log": str(_LOG_FILE),
        "engine": (_llama_binary() if not isinstance(_llama_binary(), Exception) else None),
    }


def verify(*, port: int = DEFAULT_PORT, max_tokens: int = 200, timeout: float = 120.0) -> dict[str, Any]:
    """Prove the cortex answers — listening is not answering.

    ``max_tokens`` is deliberately generous: a reasoning model spends its budget on
    reasoning first, and a 24-token probe returns an empty string that looks like a
    broken server when it is only a small budget.
    """
    body = json.dumps({
        "model": "local-fallback",
        "messages": [{"role": "user", "content": "Say exactly: LOCAL-CORTEX-OK"}],
        "max_tokens": max_tokens,
        "stream": False,
    }).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    choice = (payload.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = str(message.get("content") or "").strip()
    return {
        "ok": bool(content),
        "content": content,
        "finish_reason": choice.get("finish_reason"),
        "usage": payload.get("usage"),
        "note": "" if content else "empty content: the budget may have gone to reasoning, or the template is wrong",
    }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve this body's own GGUF weights with llama.cpp.")
    parser.add_argument("action", choices=["list", "start", "stop", "status", "verify"])
    parser.add_argument("model", nargs="?", default=None)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    if args.action == "list":
        models = available_models()
        if not models:
            print("no servable GGUF found")
            return 1
        for name, row in sorted(models.items()):
            print(f"  {row['size_gb']:6.2f} GB  {'GGUF' if row['gguf'] else 'NOT GGUF'}  {name}")
        return 0
    if args.action == "start":
        result = start(args.model, port=args.port)
    elif args.action == "stop":
        result = stop(port=args.port)
    elif args.action == "status":
        result = status(port=args.port)
    else:
        result = verify(port=args.port)
    print(render(result))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
