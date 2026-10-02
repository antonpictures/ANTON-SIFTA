#!/usr/bin/env python3
"""Probe every configured Ollama model with a real completion and record the result.

`ollama show` proves a model is *installed*; it does not prove the route answers.
This script sends the same OpenAI-compatible chat request the harness sends, so a
model that fails here fails in the picker for the same reason. Each probe unloads
the model afterwards (`keep_alive: 0`) so large weights do not accumulate in RAM
while the sweep runs.

Usage:
  python3 System/ollama_model_probe.py [--timeout 150] [--budget 1800]
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

SETTINGS = Path.home() / ".dsh" / "settings.yaml"
RESULTS = Path(__file__).resolve().parents[1] / ".sifta_state" / "ollama_probe_results.jsonl"
OLLAMA = "http://127.0.0.1:11434"


def _post(url: str, payload: dict, timeout: float) -> dict:
    """POST JSON and return the decoded body; raise on any transport or HTTP fault."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def unload(model: str) -> None:
    """Ask Ollama to drop the model's weights from memory."""
    try:
        _post(f"{OLLAMA}/api/generate", {"model": model, "keep_alive": 0}, timeout=10)
    except Exception:  # noqa: BLE001 - unloading is best effort and never decides a verdict
        pass


def probe(model: str, timeout: float) -> dict:
    """Send one minimal chat completion and classify the outcome."""
    started = time.time()
    try:
        body = _post(f"{OLLAMA}/v1/chat/completions", {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with the single word OK."}],
            "max_tokens": 64,
            "temperature": 0,
            "stream": False,
        }, timeout)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:300]
        return {"model": model, "ok": False, "error": f"HTTP {error.code}: {detail}",
                "seconds": round(time.time() - started, 1)}
    except Exception as error:  # noqa: BLE001 - the failure text is the diagnosis
        return {"model": model, "ok": False, "error": f"{type(error).__name__}: {error}",
                "seconds": round(time.time() - started, 1)}
    finally:
        unload(model)
    choices = body.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    text = str(message.get("content") or "").strip()
    # A reasoning model spends its whole small budget on reasoning_content and
    # leaves content empty; that is a working route, not a dead one.
    reasoning = str(message.get("reasoning_content") or message.get("reasoning") or "").strip()
    finish = (choices[0].get("finish_reason") if choices else None) or "none"
    if not text and not reasoning:
        return {"model": model, "ok": False, "error": f"empty completion (finish_reason={finish})",
                "body": json.dumps(body)[:300], "seconds": round(time.time() - started, 1)}
    return {"model": model, "ok": True, "reply": (text or f"[reasoning only] {reasoning}")[:80],
            "finishReason": finish, "seconds": round(time.time() - started, 1)}


def configured_models() -> list[str]:
    """Return the local-ollama model ids currently declared in settings."""
    document = yaml.safe_load(SETTINGS.read_text())
    provider = (document.get("llm-pi-ai", {}).get("providers") or {}).get("local-ollama") or {}
    return [str(entry.get("id")) for entry in (provider.get("models") or []) if entry.get("id")]


def main() -> int:
    """Probe every configured model in order, appending one result row each."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument("--budget", type=float, default=1800.0, help="stop starting new probes after this many seconds")
    args = parser.parse_args()

    models = configured_models()
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    for model in models:
        if time.time() - started > args.budget:
            print(f"budget reached; {model} and later left unprobed", flush=True)
            break
        result = probe(model, args.timeout)
        with RESULTS.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
        verdict = "OK  " if result["ok"] else "FAIL"
        detail = result.get("reply") or result.get("error")
        print(f"{verdict} {model} ({result['seconds']}s) {detail}", flush=True)
    print("sweep complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
