"""swarm_openrouter_lane — a free cortex behind the same interface as Mercury.

Architect, 2026-10-03: "use this free w openrouter somehow i want to test it as cortex
https://openrouter.ai/minimax/minimax-m3:free ... /cortex llm add my openrouter api key you have
or i will give it to you"

I do not have the key yet — checked: the body's credentials hold nothing for openrouter. So this
lane exists and refuses loudly until he pastes it once, at which point every organ that calls a
cortex can try OpenRouter BEFORE paying for Mercury: a free tier is the right place for tests,
warm-ups and throwaway work, and the paid lane for the replies that matter.

OpenRouter speaks the OpenAI dialect, so the request shape is unremarkable. Model pinned to what
he named: minimax/minimax-m3:free — a free-tier model, so it may rate-limit; that is an expected
failure mode, not a crash, and the caller should fall through to Mercury when it happens.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parents[1]
STATE = _REPO / ".sifta_state"
KEY_FILE = STATE / "openrouter_api_key"
LEDGER = STATE / "openrouter_usage.jsonl"
URL = "https://openrouter.ai/api/v1/chat/completions"
TRUTH_LABEL = "SIFTA_OPENROUTER_LANE_V1"

DEFAULT_MODEL = "minimax/minimax-m3:free"


def api_key() -> str:
    """The OpenRouter key, from the body's store or the environment. Never printed."""
    try:
        k = KEY_FILE.read_text(encoding="utf-8").strip()
        if k:
            return k
    except OSError:
        pass
    return os.environ.get("OPENROUTER_API_KEY", "")


def set_key(key: str) -> Dict[str, Any]:
    """Store the key once, 0600, never logged. Returns a receipt WITHOUT the secret."""
    k = str(key or "").strip()
    if not k:
        return {"ok": False, "error": "empty key"}
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(k + "\n", encoding="utf-8")
    KEY_FILE.chmod(0o600)
    try:
        KEY_FILE.write_text(k + "\n", encoding="utf-8")
        KEY_FILE.chmod(0o600)
    except OSError as exc:
        return {"ok": False, "error": f"could not write: {exc}"}
    return {"ok": True, "path": str(KEY_FILE), "mode": "0600", "prefix": k[:7] + "…" + k[-4:]}


def is_openrouter(model: str) -> bool:
    return str(model or "").lower().startswith("openrouter:") or ":free" in str(model or "").lower()


def chat(messages: List[Dict[str, Any]], *, model: str = DEFAULT_MODEL, max_tokens: int = 700,
         timeout: int = 60, write: bool = True) -> Dict[str, Any]:
    """One answer, free. Loud refusals, never silent ones."""
    key = api_key()
    if not key:
        return {"ok": False, "error": "no OpenRouter key in the body — ask the Architect to paste it once"}
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    t0 = time.time()
    try:
        r = subprocess.run(["curl", "-s", "--max-time", str(timeout), "-X", "POST", URL,
                            "-H", "Content-Type: application/json",
                            "-H", f"Authorization: Bearer {key}",
                            "-H", "HTTP-Referer: https://stigmergicoin.com",
                            "-d", json.dumps(payload)], capture_output=True, text=True)
        d = json.loads(r.stdout)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    el = round(time.time() - t0, 2)
    if d.get("error"):
        return {"ok": False, "error": str(d["error"].get("message") or d["error"])[:200],
                "seconds": el, "model": model}
    text = str(((d.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    usage = d.get("usage") or {}
    out = {"ok": bool(text), "text": text, "seconds": el, "model": model,
           "usage": usage, "free": True, "truth_label": TRUTH_LABEL}
    if not out["ok"]:
        out["error"] = "empty content (rate limit is common on free tiers)"
    if write:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), **{k: v for k, v in out.items() if k != "text"}},
                                ensure_ascii=False) + "\n")
    return out


def stream_chat(messages: List[Dict[str, Any]], **kw) -> Any:
    """The widget's dialect, so this lane can drop into the same dispatch chain as Mercury."""
    r = chat(messages, **kw)
    if r.get("ok"):
        yield ("token", r["text"])
        yield ("done", None)
    else:
        yield ("error", str(r.get("error") or "openrouter lane failed"))


def selftest() -> Dict[str, Any]:
    checks = {
        "recognises_free_models": is_openrouter("minimax/minimax-m3:free")
                                  and is_openrouter("openrouter:anything")
                                  and not is_openrouter("mercury-2.5"),
        "no_key_means_a_loud_refusal": chat([{"role": "user", "content": "x"}], write=False)["ok"]
                                       is False,
        "the_refusal_names_the_cure": "ask the Architect" in chat([{"role": "user", "content": "x"}],
                                                                  write=False)["error"],
        "set_key_refuses_an_empty_key": set_key("")["ok"] is False,
        "the_lane_names_itself": TRUTH_LABEL.endswith("_V1"),
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest":
        print(json.dumps(selftest(), indent=2))
    elif cmd == "setkey" and len(sys.argv) > 2:
        print(json.dumps(set_key(sys.argv[2]), indent=2))
    elif cmd == "ask":
        q = " ".join(sys.argv[2:]) or "Say hello in one short sentence."
        print(json.dumps(chat([{"role": "user", "content": q}]), indent=2)[:800])