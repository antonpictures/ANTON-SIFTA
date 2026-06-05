#!/usr/bin/env python3
"""
Clean, no-TUI Grok chat for Alice / Matrix Terminal use.
Auth is xAI OAuth (resolved by System.xai_grok_oauth_organ.load_credential).

Usage (interactive):
  python3 ~/Music/ANTON_SIFTA/grok_chat.py
  alias alice-grok='python3 ~/Music/ANTON_SIFTA/grok_chat.py'

One-shot for Alice (the exact one-liner she types inside her Matrix Terminal PTY to delegate
without hallucinating):
  python3 ~/Music/ANTON_SIFTA/grok_chat.py --one-shot "question for full Grok power + context"
  [--receipt]  # mints unique uuid4 no-double-spend swimmer in organism field

This runs real xAI API call, prints the reply, Alice reads it in terminal, waits.
Same power as George. Never hallucinates the answer — code forces delegation.
Auth comes from the xAI OAuth login (Hermes / xai_grok_oauth_token) — no static key.

For the Swarm. 🐜⚡
"""

import os
import sys
import time
import uuid
import hashlib
import json
import base64
import mimetypes
from pathlib import Path
import requests

# Models that can accept image_url content. Alice's Grok photo path uses the
# xAI chat/completions API model id that currently works for multimodal calls;
# grok-2-vision remains an explicit older vision tag.
_VISION_OK_MODELS = ("grok-4", "grok-2-vision", "grok-vision")
# George 2026-05-31: receipts proved grok vision calls returned a non-200 (rc=3) and
# failed over to claude. Root cause = the model id. "grok-4.3" / "grok-4.20-reasoning"
# are product version strings the xAI /v1/chat/completions API does NOT accept; the valid
# multimodal API id is "grok-4". Owner-overridable via SIFTA_GROK_VISION_MODEL.
_DEFAULT_VISION_MODEL = (os.environ.get("SIFTA_GROK_VISION_MODEL", "grok-4").strip() or "grok-4")
_XAI_OAUTH_LEDGER = Path(__file__).resolve().parent / ".sifta_state" / "xai_grok_oauth_calls.jsonl"


def normalize_model_name(model: str) -> str:
    """Normalize Alice cortex labels into xAI API model IDs.

    The desktop may call the cortex ``grok:grok-4.3`` while the xAI API wants
    just ``grok-4.3``. Keep this local and conservative so non-Grok labels are
    still passed through for explicit advanced use.
    """
    m = (model or "").strip()
    if not m:
        return _DEFAULT_VISION_MODEL
    low = m.lower()
    if low.startswith(("grok:", "xai:")):
        m = m.split(":", 1)[1].strip()
    if "/" in m and "grok-" in m.lower():
        m = m.rsplit("/", 1)[-1].strip()
    # Map grok-4.x product-version strings (grok-4.3, grok-4.20-reasoning) — which the
    # xAI API rejects — to the valid API id "grok-4". This is the chokepoint, so a
    # grok-4.3 leaking from the launcher/registry still hits the API as grok-4.
    if m.lower().startswith("grok-4."):
        m = _DEFAULT_VISION_MODEL if _DEFAULT_VISION_MODEL.lower().startswith("grok-4") else "grok-4"
    return m or _DEFAULT_VISION_MODEL


def _image_data_uri(path: str) -> str:
    """Read a local image and return a data: URI (base64) for the xAI image_url field."""
    p = Path(path)
    data = p.read_bytes()
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def build_one_shot_messages(query: str, image_paths=None) -> list:
    """Build the xAI chat messages for a one-shot call. With no images this is the
    plain text form (unchanged). With images, content becomes a list of a text part
    plus one image_url part per local image (base64 data URI) — George r211: this is
    how grok cortex sees with grok's OWN eye instead of failing over to claude."""
    images = [p for p in (image_paths or []) if p]
    if not images:
        return [{"role": "user", "content": (query or "").strip()}]
    content = [{"type": "text", "text": (query or "").strip()}]
    for ip in images:
        content.append({"type": "image_url", "image_url": {"url": _image_data_uri(ip)}})
    return [{"role": "user", "content": content}]


def vision_model_for(model: str, has_image: bool) -> str:
    """Keep grok on a vision-capable model when an image is attached."""
    m = normalize_model_name(model)
    if not has_image:
        return m
    if any(tag in m.lower() for tag in _VISION_OK_MODELS):
        return m
    return _DEFAULT_VISION_MODEL


def get_api_key():
    # George 2026-05-31: grok auth is xAI OAuth, NOT a static XAI_API_KEY. The bearer is
    # resolved by load_credential (Hermes xAI OAuth at ~/.hermes/auth.json,
    # .sifta_state/secrets/xai_grok_oauth_token.json, or XAI_OAUTH_ACCESS_TOKEN). We no
    # longer instruct the owner to set XAI_API_KEY.
    try:
        from System.xai_grok_oauth_organ import load_credential
        cred = load_credential()
        if cred is not None and cred.value:
            return cred.value.strip()
    except Exception as exc:
        print(f"grok auth: could not load xAI OAuth credential: {exc}")
    print("ERROR: no xAI OAuth credential found.")
    print("Log in via xAI OAuth (Hermes). Token is read from ~/.hermes/auth.json or "
          ".sifta_state/secrets/xai_grok_oauth_token.json.")
    sys.exit(1)


def _redact_secret(value: str) -> str:
    text = str(value or "")
    if len(text) <= 10:
        return "***"
    return f"{text[:5]}...{text[-4:]}"


def write_grok_chat_oauth_receipt(
    *,
    ok: bool,
    reason: str,
    model: str,
    status_code: int | None = None,
    response_text: str = "",
    credential_value: str = "",
    had_image: bool = False,
    endpoint: str = "chat/completions",
) -> dict:
    """Record the actual Grok chat/completions health path Alice used.

    The xAI OAuth organ records response-endpoint calls, while this CLI arm uses
    chat/completions directly. Keep the receipt in the same health ledger so
    future arms can inspect whether Grok OAuth is working or stale.
    """
    receipt = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "XAI_GROK_CHAT_COMPLETION_CALL_V1",
        "ok": bool(ok),
        "reason": str(reason or ""),
        "status_code": status_code,
        "model": model,
        "endpoint": endpoint,
        "had_image": bool(had_image),
        "credential_kind": "oauth_access_token" if credential_value else None,
        "credential_redacted": _redact_secret(credential_value) if credential_value else None,
        "response_preview": str(response_text or "")[:500],
        "source": "grok_chat.py",
    }
    try:
        _XAI_OAUTH_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _XAI_OAUTH_LEDGER.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return receipt


def mint_grok_delegation_swimmer(query: str, reply: str, invoker: str = "alice_matrix_terminal") -> dict:
    """Mint a unique no-double-spend organism-level swimmer receipt for Alice→Grok call.
    Distinct from Predator-Gate IDE code-change logs. Appends to .sifta_state/alice_grok_delegations.jsonl
    """
    repo = Path(__file__).resolve().parent
    state_dir = repo / ".sifta_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    ledger = state_dir / "alice_grok_delegations.jsonl"
    swimmer_id = str(uuid.uuid4())
    ts = time.time()
    q_hash = hashlib.sha256((query or "").encode("utf-8")).hexdigest()[:16]
    r_hash = hashlib.sha256((reply or "").encode("utf-8")).hexdigest()[:16]
    receipt = {
        "swimmer_id": swimmer_id,
        "type": "ALICE_GROK_DELEGATION",
        "ts": ts,
        "invoker": invoker,
        "query": (query or "")[:200],  # truncated for ledger; full in transcript
        "query_hash": q_hash,
        "reply_hash": r_hash,
        "reply_len": len(reply or ""),
        "stgm_cost": 0.03,  # symbolic inference cost in STGM for economy; real API billed to key owner
        "no_double_spend": True,
        "covenant": "Read Documents/IDE_BOOT_COVENANT.md; Alice invokes, Grok answers in terminal, Alice reads + waits",
        "node_serial": "GTH4921YP3",
    }
    try:
        with open(ledger, "a", encoding="utf-8") as f:
            f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[receipt warning] could not append swimmer: {e}")
    return receipt

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Clean Grok for Alice Matrix Terminal")
    parser.add_argument("--one-shot", dest="one_shot", type=str, default=None,
                        help="One-shot delegation prompt. Alice types: python ... --one-shot 'question'")
    parser.add_argument("--receipt", action="store_true", help="Mint organism swimmer receipt for this call")
    parser.add_argument("--model", default=_DEFAULT_VISION_MODEL, help="xAI model (default: grok-4)")
    parser.add_argument("--image", dest="image", action="append", default=None,
                        help="Path to a local image grok should LOOK at (repeatable). "
                             "George r211: grok's own eye via xAI image_url, no claude failover.")
    parser.add_argument("--invoker", default="alice_matrix_terminal", help="Who is delegating (for receipt)")
    args = parser.parse_args()

    api_key = get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    model = normalize_model_name(args.model)

    if args.one_shot:
        # Alice's reliable delegation path: real Grok, no hallucination, receipt optional
        query = args.one_shot.strip()
        image_paths = list(args.image or [])
        missing = [p for p in image_paths if not Path(p).exists()]
        if missing:
            print(f"ERROR: image not found: {missing}")
            sys.exit(5)
        has_image = bool(image_paths)
        model = vision_model_for(model, has_image)
        messages = build_one_shot_messages(query, image_paths)
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.6,
            "stream": False
        }
        try:
            resp = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=180
            )
        except Exception as e:
            print(f"Request error: {e}")
            write_grok_chat_oauth_receipt(
                ok=False,
                reason=f"request_error:{type(e).__name__}:{e}",
                model=model,
                credential_value=api_key,
                had_image=has_image,
            )
            sys.exit(2)
        if resp.status_code != 200:
            print(f"API error {resp.status_code}: {resp.text}")
            write_grok_chat_oauth_receipt(
                ok=False,
                reason=f"api_error:{resp.status_code}",
                model=model,
                status_code=resp.status_code,
                response_text=resp.text,
                credential_value=api_key,
                had_image=has_image,
            )
            # George 2026-05-31: capture the EXACT xAI rejection so a future grok failure
            # is self-diagnosing (model-not-found vs 401-auth vs ...), not an opaque rc=3.
            try:
                errp = Path(__file__).resolve().parent / ".sifta_state" / "grok_api_errors.jsonl"
                errp.parent.mkdir(parents=True, exist_ok=True)
                with errp.open("a", encoding="utf-8") as _ef:
                    _ef.write(json.dumps({
                        "ts": time.time(), "http_status": resp.status_code,
                        "body": str(resp.text)[:400], "model": model,
                        "had_image": bool(args.image), "endpoint": "chat/completions",
                    }, ensure_ascii=False) + "\n")
            except Exception:
                pass
            sys.exit(3)
        data = resp.json()
        try:
            reply = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            print("Unexpected response format:", data)
            sys.exit(4)
        print(f"Grok: {reply}\n")
        write_grok_chat_oauth_receipt(
            ok=True,
            reason="api_response",
            model=model,
            status_code=resp.status_code,
            response_text=reply,
            credential_value=api_key,
            had_image=has_image,
        )
        if args.receipt:
            rec = mint_grok_delegation_swimmer(query, reply, args.invoker)
            print(f"[organism receipt] swimmer_id={rec['swimmer_id']} stgm_cost={rec['stgm_cost']}")
        return

    # Interactive mode (owner direct use)
    print("Grok (clean mode) — type 'exit' or 'quit' to leave.\n")

    messages = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if user_input.lower() in ("exit", "quit"):
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "stream": False
        }

        try:
            resp = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            )
        except Exception as e:
            print(f"Request error: {e}")
            write_grok_chat_oauth_receipt(
                ok=False,
                reason=f"request_error:{type(e).__name__}:{e}",
                model=model,
                credential_value=api_key,
            )
            continue

        if resp.status_code != 200:
            print(f"API error {resp.status_code}: {resp.text}")
            write_grok_chat_oauth_receipt(
                ok=False,
                reason=f"api_error:{resp.status_code}",
                model=model,
                status_code=resp.status_code,
                response_text=resp.text,
                credential_value=api_key,
            )
            messages.pop()
            continue

        data = resp.json()
        try:
            reply = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            print("Unexpected response format:", data)
            messages.pop()
            continue

        print(f"Grok: {reply}\n")
        write_grok_chat_oauth_receipt(
            ok=True,
            reason="api_response",
            model=model,
            status_code=resp.status_code,
            response_text=reply,
            credential_value=api_key,
        )
        messages.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    main()
