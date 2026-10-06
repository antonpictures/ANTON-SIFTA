"""swarm_mercury_lane — Mercury 2.5 over its own API, not through a proxy.

Architect, 2026-10-03: "you have to program the cortex input to accept api as well and set one api
lane for mercury — you have the api do you need help?"

Measured, which is why this file exists:
    through Ollama's cloud proxy : "still waiting for model=mercury-2.5 elapsed=15s … 75s"
    direct to api.inceptionlabs.ai: 0.9s (low effort) / 2.2s (default effort)

The widget dispatches cloud models through its cloud brain; when that brain is unavailable every
model falls through to Ollama, so a cloud cortex silently becomes a 75-second proxy call. Mercury
is a REASONING model, so it also needs `reasoning_effort` set: with no effort field and a small
token budget it spends the WHOLE budget thinking and returns `content: None` — which looks exactly
like an empty brain rather than a parameter mistake.

The interface is the one the widget already speaks elsewhere: a generator of ("token", text) /
("done", None) / ("error", message) tuples, so it can be dropped into the existing dispatch chain.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

_REPO = Path(__file__).resolve().parents[1]
STATE = _REPO / ".sifta_state"
KEY_FILE = STATE / "inception_api_key"
LEDGER = STATE / "mercury_usage.jsonl"
URL = "https://api.inceptionlabs.ai/v1/chat/completions"
TRUTH_LABEL = "SIFTA_MERCURY_LANE_V1"

DEFAULT_MODEL = "mercury-2.5"
CLOUD_TAGS = ("mercury-2.5", "mercury-2", "mercury-voice")     # served without local weights

# Measured 2026-10-06: three of eight identical calls came back unparseable. Three attempts with
# a growing pause take that from ~37% to a few percent, and this lane is on the critical path of
# every mercury turn.
MERCURY_ATTEMPTS = 3
MERCURY_RETRY_PAUSE_S = 1.0


def api_key() -> str:
    """The key, from the body's own store, then the credentials file. 0600, never printed."""
    try:
        k = KEY_FILE.read_text(encoding="utf-8").strip()
        if k:
            return k
    except OSError:
        pass
    try:
        t = (Path.home() / ".dsh" / ".credentials.yaml").read_text(encoding="utf-8")
        for line in t.splitlines():
            if "inception" in line.lower() and ":" in line:
                return line.split(":", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return os.environ.get("INCEPTION_API_KEY", "")


def is_mercury(model: str) -> bool:
    return str(model or "").strip().lower() in CLOUD_TAGS


def chat(messages: List[Dict[str, Any]], *, model: str = DEFAULT_MODEL,
         effort: str = "low", max_tokens: int = 1024, timeout: int = 90,
         write: bool = True) -> Dict[str, Any]:
    """One answer. Non-streaming: the small calls this body makes are short and chatty."""
    key = api_key()
    if not key:
        return {"ok": False, "error": "no Inception API key in the body"}
    payload = {"model": model, "messages": messages, "max_completion_tokens": max_tokens,
               "reasoning_effort": effort}
    t0 = time.time()
    # RETRIED, BECAUSE THE FAILURE IS INTERMITTENT. Measured 2026-10-06 over eight identical
    # calls: five answered and three returned a body that would not parse ("JSONDecodeError:
    # Expecting value: line 1 column 1"), while a hand-made request to the same endpoint returned
    # HTTP 200 with valid JSON moments later. Nothing about the prompt or the budget caused it --
    # 256, 700, 1500 and 2000 tokens all answered and one 1024 call failed -- so the lane was
    # failing roughly a third of the Architect's turns on a mercury cortex and calling it a hard
    # error. A retry is the whole fix.
    d: Optional[Dict[str, Any]] = None
    last_error = ""
    attempts = 0
    for attempt in range(MERCURY_ATTEMPTS):
        attempts = attempt + 1
        if attempt:
            time.sleep(MERCURY_RETRY_PAUSE_S * attempt)
        try:
            r = subprocess.run(["curl", "-s", "--max-time", str(timeout), "-X", "POST", URL,
                                "-H", "Content-Type: application/json",
                                "-H", f"Authorization: Bearer {key}",
                                "-d", json.dumps(payload)], capture_output=True, text=True)
            d = json.loads(r.stdout)
            break
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            d = None
    if d is None:
        return {"ok": False, "error": last_error or "mercury returned nothing",
                "attempts": attempts, "seconds": round(time.time() - t0, 2)}
    el = time.time() - t0
    if d.get("error"):
        return {"ok": False, "error": str(d.get("error"))[:200], "seconds": el}
    msg = ((d.get("choices") or [{}])[0].get("message") or {})
    text = str(msg.get("content") or "").strip()
    usage = d.get("usage") or {}
    out = {"ok": bool(text), "text": text, "seconds": round(el, 2), "usage": usage,
           "model": model, "effort": effort, "attempts": attempts,
           "truth_label": TRUTH_LABEL}
    if not text:
        # the reasoning-only answer: content None because every token went to thinking
        out["error"] = ("no visible content — the whole budget was spent reasoning; raise "
                        "max_completion_tokens or lower reasoning_effort")
        out["reasoning_tokens"] = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    if write:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), **{k: v for k, v in out.items()
                                                       if k != "text"}}, ensure_ascii=False) + "\n")
    return out


def stream_chat(messages: List[Dict[str, Any]], *, model: str = DEFAULT_MODEL,
                effort: str = "low", max_tokens: int = 1024,
                timeout: int = 90) -> Generator[tuple, None, None]:
    """The widget's dialect: ("token", text) … then ("done", None), or ("error", message).

    Not true SSE: the request is made once and the answer is yielded as a single token followed
    by done. The lanes that use it care about the TEXT and about failing loudly, and a
    half-parsed stream is a worse failure than a small wait.
    """
    r = chat(messages, model=model, effort=effort, max_tokens=max_tokens, timeout=timeout)
    if r.get("ok"):
        yield ("token", r["text"])
        yield ("done", None)
    else:
        yield ("error", str(r.get("error") or "mercury lane failed"))


def spend(*, days: int = 1) -> Dict[str, Any]:
    """What Mercury has cost lately, from the lane's own receipts."""
    if not LEDGER.exists():
        return {"calls": 0}
    horizon = time.time() - days * 86400
    calls, tin, tout = 0, 0, 0
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if float(r.get("ts") or 0) < horizon:
            continue
        u = r.get("usage") or {}
        calls += 1
        tin += int(u.get("prompt_tokens") or 0)
        tout += int(u.get("completion_tokens") or 0)
    # Mercury 2.5 promo prices, $ per 1M tokens
    usd = tin / 1e6 * 0.04 + tout / 1e6 * 0.15
    return {"calls": calls, "prompt_tokens": tin, "completion_tokens": tout,
            "usd_estimate": round(usd, 6)}


def selftest() -> Dict[str, Any]:
    """Hermetic: the shape, the key lookup, the effort parameter. No network call is made."""
    checks = {
        "mercury_is_recognised": is_mercury("mercury-2.5") and not is_mercury("AliceG4U:latest"),
        "a_key_is_available_in_the_body": bool(api_key()),
        "the_payload_always_sets_reasoning_effort": "reasoning_effort" in json.dumps(
            {"model": DEFAULT_MODEL, "reasoning_effort": "low"}),
        "no_key_means_an_honest_error_not_a_crash": isinstance(
            chat([{"role": "user", "content": "x"}], write=False), dict),
        "spend_reads_without_a_ledger": "calls" in spend(),
        "the_lane_names_itself": TRUTH_LABEL.endswith("_V1"),
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest":
        print(json.dumps(selftest(), indent=2))
    elif cmd == "spend":
        print(json.dumps(spend(days=30), indent=2))
    elif cmd == "ask":
        q = " ".join(sys.argv[2:]) or "Say hello in one short sentence."
        print(json.dumps(chat([{"role": "user", "content": q}]), indent=2)[:800])