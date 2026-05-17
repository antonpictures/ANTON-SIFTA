#!/usr/bin/env python3
"""
sifta_app.py
=============
SIFTA desktop app v0.1 — the polished consumer surface.

A single window. Owner OOBE on first run. Natural-language input that
dispatches to the tool router. Live scrolling receipt log of every
chained action. Status bar with chain head + STGM balance.

Runs on macOS via pywebview (which uses the system WKWebView).

Requirements:
    pip3 install pywebview

Dependencies (must be importable):
    System/swarm_tool_router.py
    System/swarm_terminal_organ.py
    System/swarm_file_organ.py
    System/swarm_web_organ.py
Optional status fallback:
    System/stgm_economy.py

Run:
    PYTHONPATH=. python3 System/sifta_app.py

After first run, .sifta_state/owner_genesis.json holds the owner
identity. Delete it to re-trigger the OOBE.

For packaging into a .app, see build_app.sh and the README.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

router = None
stgm = None
swarm_gemini_brain = None
swarm_local_brain = None
parse_tool_calls = None
tools_for_alice_prompt = None
_IMPORT_ERROR: Optional[str] = None
_STGM_IMPORT_ERROR: Optional[str] = None

# ----------------------------------------------------------------------
# Discover the SIFTA project root so we never silo state in a side dir.
# We walk up from this script's location and score each ancestor by how
# many SIFTA markers it has — the highest score wins. We then chdir()
# to that root BEFORE importing any organ, so every organ's relative
# `Path(".sifta_state")` resolves to the project root, not wherever
# the user happened to run from.
# ----------------------------------------------------------------------
_SIFTA_MARKERS = (".sifta_state", "Applications", "ARCHITECTURE",
                  "System", ".sifta_trash", ".sifta_documents")

def _discover_sifta_root() -> Path:
    here = Path(__file__).resolve().parent
    best, best_score = here, -1
    for p in [here, *here.parents]:
        try:
            score = sum(1 for m in _SIFTA_MARKERS if (p / m).exists())
        except Exception:
            score = 0
        if score > best_score:
            best, best_score = p, score
    return best

SIFTA_ROOT = _discover_sifta_root()
os.chdir(SIFTA_ROOT)
if str(SIFTA_ROOT) not in sys.path:
    sys.path.insert(0, str(SIFTA_ROOT))
_SYSTEM_DIR = SIFTA_ROOT / "System"
if _SYSTEM_DIR.exists() and str(_SYSTEM_DIR) not in sys.path:
    sys.path.insert(0, str(_SYSTEM_DIR))

_STATE = SIFTA_ROOT / ".sifta_state"
_STATE.mkdir(exist_ok=True)

# ----------------------------------------------------------------------
# Imports of the underlying organs / router. Soft-fail so the app at
# least opens and shows a clear setup screen if pieces are missing.
# Import AFTER root discovery/chdir so package-relative router imports
# resolve against the SIFTA root instead of the caller's launch folder.
# ----------------------------------------------------------------------
try:
    import swarm_tool_router as router
except Exception as e:
    _IMPORT_ERROR = f"{type(e).__name__}: {e}"
    router = None

try:
    import swarm_gemini_brain as swarm_gemini_brain
except Exception:
    swarm_gemini_brain = None

try:
    from System import swarm_local_brain as swarm_local_brain
except Exception:
    swarm_local_brain = None

if router is not None:
    parse_tool_calls = getattr(router, "parse_tool_calls", None)
    tools_for_alice_prompt = getattr(router, "tools_for_alice_prompt", None)

try:
    import swarm_stgm_billing as stgm
except Exception as e:
    _STGM_IMPORT_ERROR = f"{type(e).__name__}: {e}"
    stgm = None

# READ-ONLY owner identity. This app never writes genesis — that would
# double-spend a hardware identity the rest of SIFTA already controls.
# Searched in order; the first one that exists wins.
OWNER_FILE_CANDIDATES = [
    _STATE / "owner_genesis.json",
    SIFTA_ROOT / "owner_genesis.json",
]

# All trace files the receipt feed reads.
TRACE_FILES = [
    "tool_router_trace.jsonl",
    "terminal_organ.jsonl",
    "file_organ.jsonl",
    "web_organ.jsonl",
    "tab_consciousness.jsonl",
    "stgm_ledger.jsonl",
    "swarm_doctors_bus.jsonl",
    "ide_stigmergic_trace.jsonl",
]


# ----------------------------------------------------------------------
# Owner identity — READ ONLY. One genesis per hardware. This window
# never writes a new one.
# ----------------------------------------------------------------------
def _owner_state() -> Dict[str, Any]:
    for candidate in OWNER_FILE_CANDIDATES:
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text())
                data["signed_in"] = True
                data["source"] = str(candidate.resolve())
                return data
            except Exception as e:
                return {"signed_in": False, "error": f"{candidate}: {e}",
                        "candidates_searched": [str(c) for c in OWNER_FILE_CANDIDATES]}
    return {
        "signed_in": False,
        "error": "no owner_genesis found",
        "candidates_searched": [str(c) for c in OWNER_FILE_CANDIDATES],
    }


def _refuse_to_write_genesis(_owner_name: str = "") -> Dict[str, Any]:
    """This app does NOT create owner identity. One genesis per hardware."""
    return {
        "error": "this window will never write owner_genesis — one genesis per hardware. "
                 "create it through your existing SIFTA genesis widget, then relaunch.",
        "candidates_searched": [str(c) for c in OWNER_FILE_CANDIDATES],
    }


# ----------------------------------------------------------------------
# Receipt feed — tail all known trace files and return recent rows.
# ----------------------------------------------------------------------
def _summarise(row: Dict[str, Any]) -> str:
    t = row.get("type", "")
    if "RESULT" in t:
        cmd = row.get("command") or row.get("path") or row.get("url") or row.get("query") or ""
        ec = row.get("exit_code")
        ok = row.get("wrote_ok")
        size = row.get("size_bytes")
        bits = [cmd[:48] if cmd else (row.get("op") or t)]
        if ec is not None: bits.append(f"exit={ec}")
        if ok is not None: bits.append(f"wrote_ok={ok}")
        if size is not None: bits.append(f"{size}B")
        return " · ".join(bits)
    if "INTENT" in t:
        return "intent: " + (row.get("command") or row.get("path") or row.get("url") or row.get("op") or "")[:60]
    if "REFUSED" in t:
        return "REFUSED: " + str(row.get("refused_for", ""))
    if "DEBIT" in t:
        return f"-{row.get('amount', 0):.4f} STGM ({row.get('organ', '')})"
    if "CREDIT" in t:
        return f"+{row.get('amount', 0):.4f} STGM ({row.get('organ', '')})"
    if "REGISTRATION" in t or row.get("action") == "LLM_REGISTRATION":
        return f"sign-in: {row.get('doctor', '?')} ({row.get('model', '?')})"
    if row.get("action") == "OWNER_GENESIS":
        return f"OWNER GENESIS: {row.get('owner_name', '?')}"
    if t.startswith("TOOL_CALL"):
        return f"{t.lower()} → {row.get('tool', '?')}"
    return row.get("subject") or row.get("reason") or t or "—"


def _organ_of(filename: str) -> str:
    return filename.replace(".jsonl", "").replace("_", " ")


def _recent_receipts(since_ts: float = 0.0, limit: int = 200) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for fname in TRACE_FILES:
        p = _STATE / fname
        if not p.exists():
            continue
        organ = _organ_of(fname)
        try:
            with p.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    ts = float(r.get("ts", 0))
                    if ts > since_ts:
                        rows.append({
                            "ts": ts,
                            "ts_iso": time.strftime("%H:%M:%S", time.localtime(ts)),
                            "organ": organ,
                            "type": r.get("type", "?"),
                            "summary": _summarise(r),
                            "hash": (r.get("hash") or "")[:12],
                            "refused": ("REFUSED" in str(r.get("type", ""))),
                        })
        except Exception:
            continue
    rows.sort(key=lambda r: r["ts"])
    return rows[-limit:]


# ----------------------------------------------------------------------
# Router adapter — the consumer app speaks the current router API:
# TOOL_REGISTRY + ParsedToolCall + execute_tool_call.
# ----------------------------------------------------------------------
_SIFTA_APP_CALLER_PID = "sifta_app"


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return json.loads(json.dumps(value, default=str))


def _router_registry() -> Dict[str, Any]:
    if router is None:
        return {}
    registry = getattr(router, "TOOL_REGISTRY", None)
    if registry is None:
        registry = getattr(router, "REGISTRY", None)
    try:
        return dict(registry or {})
    except Exception:
        return {}


def _router_trace_head() -> Optional[str]:
    if router is not None:
        current_head = getattr(router, "_current_head", None)
        if callable(current_head):
            try:
                return str(current_head())
            except Exception:
                pass
    trace = _STATE / "tool_router_trace.jsonl"
    if not trace.exists():
        return None
    last = ""
    try:
        with trace.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last = line.strip()
    except Exception:
        return None
    if not last:
        return None
    return hashlib.sha256(last.encode("utf-8")).hexdigest()[:16]


def _stgm_balance() -> Optional[float]:
    if stgm is not None:
        balance = getattr(stgm, "balance", None)
        if callable(balance):
            try:
                return float(balance())
            except Exception:
                pass
    try:
        from stgm_economy import scan_economy

        return float(scan_economy().canonical_wallet_sum)
    except Exception:
        return None


def _ensure_sifta_app_kernel_pid(tool_name: str) -> Optional[str]:
    try:
        from swarm_kernel_process_table import OrganProcess, get_kernel_process_table

        table = get_kernel_process_table(state_root=_STATE)
        table.ensure_registered(
            OrganProcess(
                pid=_SIFTA_APP_CALLER_PID,
                organ_id="System/sifta_app.py",
                ring=2,
                health=1.0,
                stgm_balance=0.0,
                current_job=f"pywebview_tool:{tool_name}",
                last_receipt_id="",
                failure_count=0,
                last_heartbeat_ts=time.time(),
                location="sifta_pywebview_consumer_surface",
                bodies_present=["sifta_app", "alice_tool_router"],
                metadata={
                    "source": "System/sifta_app.py",
                    "kernel_role": "owner_present_pywebview_tool_adapter",
                },
            ),
            receipt_id=f"sifta_app_register:{tool_name}",
        )
        return None
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def _tool_result_to_dict(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        data = dict(result)
    elif is_dataclass(result):
        data = asdict(result)
    else:
        data = {}
        for key in ("tool_name", "params", "executed", "result", "status", "feedback_for_alice"):
            if hasattr(result, key):
                data[key] = getattr(result, key)
        if not data:
            data = {"result": result}

    payload = data.get("result")
    if isinstance(payload, dict) and "ok" in payload and "ok" not in data:
        data["ok"] = payload.get("ok")
    if "ok" not in data:
        data["ok"] = bool(data.get("executed")) and str(data.get("status")) == "EXECUTED"
    return _json_safe(data)


def _execute_router_tool(name: str, args: Optional[Dict[str, Any]], reason: str) -> Dict[str, Any]:
    if router is None:
        return {"error": "router not loaded", "import_error": _IMPORT_ERROR}

    tool_name = str(name or "").strip()
    registry = _router_registry()
    if tool_name not in registry:
        return {"error": "unknown_tool", "name": tool_name}

    params = {
        str(k): "" if v is None else str(v)
        for k, v in dict(args or {}).items()
    }
    if not str(params.get("cost_justification", "")).strip():
        params["cost_justification"] = (
            f"SIFTA pywebview {reason} requested {tool_name}; "
            "owner-present UI action needs a receipted tool boundary."
        )

    execute = getattr(router, "execute_tool_call", None)
    parsed_tool_call = getattr(router, "ParsedToolCall", None)
    if callable(execute) and parsed_tool_call is not None:
        kernel_error = _ensure_sifta_app_kernel_pid(tool_name)
        if kernel_error:
            return {
                "error": "kernel_registration_failed",
                "detail": kernel_error,
                "name": tool_name,
            }
        call = parsed_tool_call(
            tool_name=tool_name,
            params=params,
            raw_match=f"sifta_app:{reason}:{tool_name}",
        )
        try:
            return _tool_result_to_dict(
                execute(
                    call,
                    owner_present=True,
                    autonomous=False,
                    caller_pid=_SIFTA_APP_CALLER_PID,
                )
            )
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}", "name": tool_name}

    legacy_call_tool = getattr(router, "call_tool", None)
    if callable(legacy_call_tool):
        try:
            return _tool_result_to_dict(legacy_call_tool(tool_name, params, reason=reason))
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}", "name": tool_name}

    return {"error": "router execution API unavailable", "name": tool_name}


def _tool_specs() -> List[Dict[str, Any]]:
    if router is None:
        return []
    get_specs = getattr(router, "get_tool_specs", None)
    if callable(get_specs):
        try:
            return _json_safe(get_specs(format="anthropic"))
        except TypeError:
            try:
                return _json_safe(get_specs())
            except Exception:
                pass
        except Exception:
            pass

    specs: List[Dict[str, Any]] = []
    for spec in _router_registry().values():
        required = list(getattr(spec, "required_params", ()) or ())
        optional = list(getattr(spec, "optional_params", ()) or ())
        properties = {
            str(param): {"type": "string"}
            for param in [*required, *optional, "cost_justification"]
        }
        specs.append({
            "name": str(getattr(spec, "name", "")),
            "description": str(getattr(spec, "description", "")),
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": [str(param) for param in required],
            },
        })
    return specs


# ----------------------------------------------------------------------
# Natural-language dispatch.
# Keyword verbs remain the v0.1 fast path. Non-keyword input asks Alice
# to choose from the receipted tool catalog, then this app parses and
# executes only explicit router tool calls.
# ----------------------------------------------------------------------
def _tool_catalog_prompt() -> str:
    if callable(tools_for_alice_prompt):
        try:
            return str(tools_for_alice_prompt())
        except Exception:
            pass
    if router is not None:
        fn = getattr(router, "tools_for_alice_prompt", None)
        if callable(fn):
            try:
                return str(fn())
            except Exception:
                pass
    names = ", ".join(sorted(_router_registry()))
    return (
        "TOOL-CALLING CAPABILITY:\n"
        "Format: [TOOL_CALL: tool_name | key=value | cost_justification=chat_llm]\n"
        f"Available tools: {names}"
    )


def _brain_system_prompt() -> str:
    return (
        "You are Alice, the SIFTA organism on the owner's M5 MacBook Pro (GTH4921YP3). "
        "You have access to real tools on the owner's machine. "
        "When the user asks you to do something that can be done with a tool, you MUST respond with exactly one line in this format:\n"
        "[TOOL_CALL: tool_name | param1=value1 | param2=value2 | cost_justification=short reason why this action is needed]\n\n"
        "Example for listing files:\n"
        "[TOOL_CALL: list_dir | path=. | cost_justification=The user asked to see what files are in the current directory]\n\n"
        "Never explain first. Never say 'I will list the files'. Just output the [TOOL_CALL: ...] line when a tool is appropriate.\n"
        "If no tool is needed, answer normally in plain English.\n\n"
        + _tool_catalog_prompt()
    )


def _gemini_brain_once(user_text: str) -> Optional[Dict[str, Any]]:
    if swarm_gemini_brain is None:
        return None
    key_fn = getattr(swarm_gemini_brain, "gemini_api_key", None)
    if not callable(key_fn) or not key_fn():
        return None
    models_fn = getattr(swarm_gemini_brain, "available_gemini_models", None)
    models = models_fn() if callable(models_fn) else []
    model = (models or ["gemini:gemini-2.5-flash"])[0]
    messages = [
        {"role": "system", "content": _brain_system_prompt()},
        {"role": "user", "content": user_text},
    ]
    stream = swarm_gemini_brain.stream_chat(
        model,
        messages,
        temperature=0.1,
        request_tag="sifta_app_chat_llm",
    )
    full_text = ""
    for kind, payload in stream:
        if kind == "done":
            full_text = str(payload or full_text)
            break
        if kind == "token" and isinstance(payload, str):
            full_text += payload
        if kind == "error":
            return {
                "text": "",
                "model": model,
                "provider": "gemini",
                "error": str(payload),
            }
    return {
        "text": full_text,
        "model": model,
        "provider": "gemini",
        "error": None,
    }


def _ollama_model(user_text: str) -> str:
    try:
        from sifta_inference_defaults import resolve_ollama_model

        return str(resolve_ollama_model(
            app_context="sifta_app",
            query_text=user_text,
            use_stigmergic=True,
        ))
    except Exception:
        return os.environ.get("SIFTA_APP_OLLAMA_MODEL", "llama3.2")


def _ollama_brain_once(user_text: str) -> Dict[str, Any]:
    model = _ollama_model(user_text)
    prompt = f"{_brain_system_prompt()}\n\nUSER:\n{user_text}\n\nALICE:"
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }).encode("utf-8")
    url = os.environ.get("SIFTA_APP_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {
            "text": "",
            "model": model,
            "provider": "ollama",
            "error": f"{type(e).__name__}: {e}",
        }
    return {
        "text": str(data.get("response") or ""),
        "model": model,
        "provider": "ollama",
        "error": None,
    }


def _brain_tool_route(user_text: str) -> Dict[str, Any]:
    """Return one Alice response. Tests monkeypatch this; live app uses Gemini then Ollama."""
    if os.environ.get("SIFTA_APP_DISABLE_LLM") == "1":
        return {
            "text": "",
            "model": None,
            "provider": None,
            "error": "LLM routing disabled by SIFTA_APP_DISABLE_LLM=1",
        }
    # Prefer new local brain module (Ollama /api/chat, proper messages)
    if swarm_local_brain is not None and swarm_local_brain.is_available():
        try:
            model = swarm_local_brain.get_default_model()
            messages = [
                {"role": "system", "content": _brain_system_prompt()},
                {"role": "user", "content": user_text},
            ]
            events = list(swarm_local_brain.stream_chat(model, messages, request_tag="sifta_app_chat_llm", temperature=0.2))
            full_text = ""
            for kind, payload in events:
                if kind == "done":
                    full_text = str(payload or "")
                    break
                if kind == "token" and isinstance(payload, str):
                    full_text += payload
            return {
                "text": full_text,
                "model": model,
                "provider": "ollama",
                "error": None,
            }
        except Exception as e:
            pass  # fall through to legacy _ollama_brain_once

    gemini = _gemini_brain_once(user_text)
    if gemini is not None:
        return gemini
    return _ollama_brain_once(user_text)


def _parse_alice_tool_calls(alice_text: str) -> List[Any]:
    parser = parse_tool_calls
    if not callable(parser) and router is not None:
        parser = getattr(router, "parse_tool_calls", None)
    if not callable(parser):
        return []
    try:
        return list(parser(alice_text or ""))
    except Exception:
        return []


def _execute_llm_tool_calls(calls: List[Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for call in calls:
        tool_name = str(getattr(call, "tool_name", "")).strip()
        params = dict(getattr(call, "params", {}) or {})
        if not str(params.get("cost_justification", "")).strip():
            params["cost_justification"] = "chat_llm"
        results.append(_execute_router_tool(tool_name, params, reason="chat_llm"))
    return results


def _chat_keyword(text: str) -> Optional[Dict[str, Any]]:
    """Only treat as keyword command if it looks like a short, direct command.
    Full natural language sentences fall through to the brain.
    """
    parts = text.split(None, 1)
    verb = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    # Demo mode: keyword path only for ultra-short exact commands.
    # Anything that looks like a real sentence goes to the brain + skill tools.
    words = [w.lower() for w in text.split()]
    if len(words) > 2 or any(w in ["the", "in", "current", "directory", "folder", "what", "please", "here", "now", "files"] for w in words):
        return None  # force brain (local Ollama + new skill_pull / skill_extract_from_trace)

    if verb in ("run", "exec", "shell", "$"):
        return _execute_router_tool("run_terminal", {"command": rest}, "chat")
    if verb in ("read", "cat"):
        return _execute_router_tool("read_file", {"path": rest}, "chat")
    if verb in ("list", "ls"):
        return _execute_router_tool("list_dir", {"path": rest or "."}, "chat")
    if verb in ("search", "find"):
        return _execute_router_tool("search_web", {"query": rest}, "chat")
    if verb in ("fetch", "get"):
        return _execute_router_tool("fetch_url", {"url": rest}, "chat")
    if verb == "write":
        if " " not in rest:
            return {"error": "usage: write PATH CONTENT"}
        path, content = rest.split(" ", 1)
        return _execute_router_tool("write_file", {"path": path, "content": content}, "chat")
    if verb == "help":
        return {"help": [
            "run CMD            -> run_terminal (shlex-split, no shell)",
            "read PATH          -> read_file",
            "write PATH CONTENT -> write_file (atomic)",
            "list PATH          -> list_dir",
            "search QUERY       -> search_web (DuckDuckGo)",
            "fetch URL          -> fetch_url",
            "Plain English      -> Alice chooses a receipted tool when needed",
        ]}
    return None


def _chat(text: str) -> Dict[str, Any]:
    if router is None:
        return {"error": "tool router not loaded; check the swarm_* modules are in PYTHONPATH"}
    text = (text or "").strip()
    if not text:
        return {"error": "empty input"}
    keyword = _chat_keyword(text)
    if keyword is not None:
        return keyword

    brain = _brain_tool_route(text)
    if brain.get("error"):
        verb = text.split(None, 1)[0].lower()
        return {
            "error": (
                f"unknown verb '{verb}'. Type 'help' for keyword commands. "
                f"LLM route unavailable: {brain['error']}"
            ),
            "provider": brain.get("provider"),
            "model": brain.get("model"),
        }

    alice_text = str(brain.get("text") or "")
    calls = _parse_alice_tool_calls(alice_text)
    if calls:
        return {
            "type": "chat_llm_tool_calls",
            "alice": alice_text,
            "provider": brain.get("provider"),
            "model": brain.get("model"),
            "tool_results": _execute_llm_tool_calls(calls),
        }
    return {
        "type": "chat_llm_reply",
        "alice": alice_text or "(Alice emitted no text.)",
        "provider": brain.get("provider"),
        "model": brain.get("model"),
        "tool_results": [],
    }


def _status() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "sifta_root": str(SIFTA_ROOT),
        "import_error": _IMPORT_ERROR,
        "owner": _owner_state(),
        "stgm_balance": None,
        "stgm_error": _STGM_IMPORT_ERROR,
        "router_head": None,
        "tools_count": 0,
    }
    out["stgm_balance"] = _stgm_balance()
    if router is not None:
        try:
            out["router_head"] = _router_trace_head()
            out["tools_count"] = len(_router_registry())
        except Exception: pass
    return out


def _skill_library_module():
    try:
        import swarm_skill_library as lib
        return lib
    except Exception:
        from System import swarm_skill_library as lib
        return lib


def _skill_autoproposal_module():
    try:
        import swarm_skill_autoproposal as auto
        return auto
    except Exception:
        from System import swarm_skill_autoproposal as auto
        return auto


def _skill_status(limit: int = 8) -> Dict[str, Any]:
    try:
        lib = _skill_library_module()
        index = lib.build_skill_index()
        report = lib.validate_skill_contracts()
        receipts = []
        receipt_path = getattr(lib, "_SKILL_RECEIPTS", None)
        if receipt_path is not None and receipt_path.exists():
            for line in receipt_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-int(limit):]:
                try:
                    receipts.append(json.loads(line))
                except Exception:
                    pass
        return _json_safe({
            "ok": True,
            "skills_count": len(index),
            "validation_passed": bool(report.get("passed")),
            "issues": report.get("issues", [])[:int(limit)],
            "recent_receipts": receipts,
            "skills": [
                {
                    "name": row.get("name"),
                    "description": row.get("description"),
                    "procedure_file": row.get("procedure_file"),
                    "community_style": row.get("community_style"),
                    "resource_counts": row.get("resource_counts", {}),
                }
                for row in index[:80]
            ],
        })
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _pull_skill(
    source: str = "",
    life_context: str = "",
    marketplace: str = "",
    skill_id: str = "",
    force_install: bool = False,
    allow_overwrite: bool = False,
) -> Dict[str, Any]:
    try:
        lib = _skill_library_module()
        if marketplace.strip():
            return _json_safe(lib.pull_skill_from_marketplace(
                marketplace.strip(),
                skill_id=skill_id.strip(),
                life_context=life_context.strip() or None,
                force_install=bool(force_install),
                allow_overwrite=bool(allow_overwrite),
                installed_by="sifta_app_ui",
            ))
        src = source.strip()
        if not src:
            return {"ok": False, "status": "REFUSED", "reason": "missing_source_or_marketplace"}
        if src.startswith(("https://", "http://")):
            return _json_safe(lib.pull_skill_from_url(
                src,
                life_context=life_context.strip() or None,
                force_install=bool(force_install),
                allow_overwrite=bool(allow_overwrite),
                installed_by="sifta_app_ui",
            ))
        return _json_safe(lib.ingest_skill_source(
            src,
            life_context=life_context.strip() or None,
            force_install=bool(force_install),
            allow_overwrite=bool(allow_overwrite),
            installed_by="sifta_app_ui",
        ))
    except Exception as e:
        return {"ok": False, "status": "FAILED", "error": f"{type(e).__name__}: {e}"}


def _extract_skill_from_trace(
    trace_file: str = "tool_router_trace.jsonl",
    trace_id: str = "",
    name: str = "",
    life_context: str = "",
    allow_overwrite: bool = False,
) -> Dict[str, Any]:
    try:
        lib = _skill_library_module()
        return _json_safe(lib.extract_skill_from_trace(
            trace_file=trace_file.strip() or "tool_router_trace.jsonl",
            trace_id=trace_id.strip(),
            name=name.strip(),
            life_context=life_context.strip() or None,
            allow_overwrite=bool(allow_overwrite),
            installed_by="sifta_app_ui",
        ))
    except Exception as e:
        return {"ok": False, "status": "FAILED", "error": f"{type(e).__name__}: {e}"}


def _scan_field_for_skills(
    marketplace: str = "",
    allow_pull: bool = False,
    min_repeat: int = 3,
) -> Dict[str, Any]:
    try:
        auto = _skill_autoproposal_module()
        return _json_safe(auto.scan_field_for_skill_needs(
            marketplace=marketplace.strip() or None,
            allow_pull=bool(allow_pull),
            min_repeat=int(min_repeat or 3),
        ))
    except Exception as e:
        return {"ok": False, "status": "FAILED", "error": f"{type(e).__name__}: {e}"}


def _skill_autoproposals(limit: int = 8) -> List[Dict[str, Any]]:
    try:
        auto = _skill_autoproposal_module()
        return _json_safe(auto.latest_proposals(limit=int(limit or 8)))
    except Exception:
        return []


# ----------------------------------------------------------------------
# JS API — methods exposed to the webview frontend.
# ----------------------------------------------------------------------
class API:
    def owner_state(self) -> Dict[str, Any]: return _owner_state()
    def write_owner(self, name: str) -> Dict[str, Any]: return _refuse_to_write_genesis(name)
    def status(self) -> Dict[str, Any]: return _status()
    def recent_receipts(self, since_ts: float = 0.0) -> List[Dict[str, Any]]:
        return _recent_receipts(float(since_ts or 0))
    def list_tools(self) -> List[str]:
        return sorted(_router_registry().keys()) if router else []
    def tool_specs(self) -> List[Dict[str, Any]]:
        return _tool_specs()
    def call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return _execute_router_tool(name, args or {}, "ui")
    def chat(self, text: str) -> Dict[str, Any]: return _chat(text)
    def skill_status(self, limit: int = 8) -> Dict[str, Any]: return _skill_status(limit)
    def skill_autoproposals(self, limit: int = 8) -> List[Dict[str, Any]]:
        return _skill_autoproposals(limit)
    def scan_field_for_skills(
        self,
        marketplace: str = "",
        allow_pull: bool = False,
        min_repeat: int = 3,
    ) -> Dict[str, Any]:
        return _scan_field_for_skills(marketplace, allow_pull, min_repeat)
    def pull_skill(
        self,
        source: str = "",
        life_context: str = "",
        marketplace: str = "",
        skill_id: str = "",
        force_install: bool = False,
        allow_overwrite: bool = False,
    ) -> Dict[str, Any]:
        return _pull_skill(source, life_context, marketplace, skill_id, force_install, allow_overwrite)
    def extract_skill_from_trace(
        self,
        trace_file: str = "tool_router_trace.jsonl",
        trace_id: str = "",
        name: str = "",
        life_context: str = "",
        allow_overwrite: bool = False,
    ) -> Dict[str, Any]:
        return _extract_skill_from_trace(trace_file, trace_id, name, life_context, allow_overwrite)
    def verify_all(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for name, mod in [("router", router), ("stgm", stgm)]:
            if mod is None: continue
            try: out[name] = mod.verify_chain()
            except Exception as e: out[name] = {"error": str(e)}
        for mod_name in ("swarm_terminal_organ", "swarm_file_organ",
                         "swarm_web_organ", "swarm_tab_consciousness",
                         "swarm_doctor_mailbox"):
            try:
                import importlib
                m = importlib.import_module(mod_name)
                out[mod_name] = m.verify_chain()
            except Exception as e:
                out[mod_name] = {"error": f"{type(e).__name__}: {e}"}
        return out


# ----------------------------------------------------------------------
# Window entry point
# ----------------------------------------------------------------------
def main() -> int:
    try:
        import webview
    except ImportError:
        print("pywebview not installed. Run: pip3 install pywebview",
              file=sys.stderr)
        return 2

    api = API()
    here = Path(__file__).parent
    ui_path = here / "sifta_app_ui.html"
    if not ui_path.exists():
        print(f"UI missing: expected {ui_path}", file=sys.stderr)
        return 2

    window = webview.create_window(
        title="SIFTA",
        url=str(ui_path.resolve()),
        js_api=api,
        width=1000,
        height=720,
        min_size=(720, 540),
    )
    webview.start(debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
