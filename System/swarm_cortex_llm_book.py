from __future__ import annotations
import json, os, shutil, subprocess, sys, time, importlib, urllib.request
from pathlib import Path
from typing import Any

TRUTH_LABEL = "CORTEX_LLM_BOOK_V1"
_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_AGREEMENTS = "cortex_llm_agreements.jsonl"
_DEFAULT = "cortex_llm_talk_default.json"
_OLLAMA = "http://127.0.0.1:11434"
_CLOUD_LANES = ("grok-4.3", "gpt-5.5", "claude-code-cli-default", "cline-cli-default", "antigravity-auto", "kimi-k2.6-fireworks", "deepseek-v4.1-flash-fireworks", "gpt-oss-20b-fireworks", "mimo-coding")
_KNOWN_DUPLICATES = (("krishairnd/Gemma-4-Uncensored:latest", "alice-m5-cortex-8b-6.3gb:latest"),)
_TRANSLATION_ONLY_NEEDLES = ("qwen3.5-mt", "kaelri")

def _get(path, timeout=6):
    try:
        with urllib.request.urlopen(_OLLAMA + path, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception:
        return {}

def _post(path, payload, timeout=8):
    try:
        req = urllib.request.Request(_OLLAMA + path, json.dumps(payload).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception:
        return {}

def inventory() -> Dict[str, Any]:
    tags = (_get("/api/tags").get("models") or [])
    dialogue, vision, aux = [], [], []
    for m in tags:
        name = str(m.get("name") or "")
        if not name:
            continue
        detail = m.get("details") or {}
        show = _post("/api/show", {"model": name})
        caps = [str(c) for c in (show.get("capabilities") or [])]
        row = {"name": name, "size_bytes": int(m.get("size") or 0), "params": detail.get("parameter_size"), "capabilities": caps}
        low = name.lower()
        if any(n in low for n in _TRANSLATION_ONLY_NEEDLES) or (not caps):
            aux.append(row)
        elif "vision" in caps:
            vision.append(row)
        else:
            dialogue.append(row)
    prism = []
    seen = set()
    try:
        out = subprocess.run(["ps", "-axo", "command="], capture_output=True, text=True, timeout=6).stdout
        for line in out.splitlines():
            if ("sifta-llama-prism" not in line) and ("sifta-models" not in line):
                continue
            toks = line.split()
            port = 0
            model = ""
            for i, tok in enumerate(toks):
                if tok == "--port" and i + 1 < len(toks):
                    try:
                        port = int(toks[i + 1])
                    except Exception:
                        pass
                if tok == "-m" and i + 1 < len(toks):
                    model = toks[i + 1]
                if tok == "--model" and i + 1 < len(toks):
                    model = toks[i + 1]
            if port and port not in seen:
                seen.add(port)
                prism.append({"port": port, "model": model})
    except Exception:
        pass
    mlx = []
    try:
        import mlx_vlm  # noqa
        mlx.append("mlx-vlm:SuperagenticAI/gemma-4-12b-it-8bit-mlx (runtime available)")
    except Exception:
        pass
    audit_results = audit_coding_arm()
    return {"local_dialogue": dialogue, "local_vision": vision, "aux_and_translation": aux, "mlx_runtime": mlx, "prism_servers": prism, "cloud_lanes": list(_CLOUD_LANES), "coding_arm_audit": audit_results}

def _load_rows(path):
    rows = []
    if os.path.exists(path):
        for line in open(path, errors="replace"):
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows

def _state(state_dir):
    p = Path(state_dir) if state_dir else _STATE
    return p if p.name == ".sifta_state" else (p / ".sifta_state")

def agree(model, note="both agree after test", state_dir=None):
    sd = _state(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    with (sd / _AGREEMENTS).open("a") as f:
        f.write(json.dumps({"ts": time.time(), "model": model, "action": "agree", "note": note, "truth_label": TRUTH_LABEL}) + "\n")

def revoke(model, state_dir=None):
    sd = _state(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    with (sd / _AGREEMENTS).open("a") as f:
        f.write(json.dumps({"ts": time.time(), "model": model, "action": "revoke", "truth_label": TRUTH_LABEL}) + "\n")

def agreed(state_dir=None):
    status = {}
    for r in _load_rows(_state(state_dir) / _AGREEMENTS):
        status[str(r.get("model"))] = (r.get("action") == "agree")
    return {"agreed": [m for m, ok in status.items() if ok]}

def set_talk_default(model, state_dir=None):
    sd = _state(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    (sd / _DEFAULT).write_text(json.dumps({"model": model, "ts": time.time(), "selected_by": "architect"}))

def get_talk_default(state_dir=None):
    p = _state(state_dir) / _DEFAULT
    if not p.exists():
        return ""
    try:
        return str(json.loads(p.read_text()).get("model") or "")
    except Exception:
        return ""

def fallback_chain(state_dir=None):
    try:
        from System.sifta_inference_defaults import CANONICAL_OLLAMA_FALLBACK
        canon = str(CANONICAL_OLLAMA_FALLBACK)
    except Exception:
        canon = "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"
    chain = [x for x in (get_talk_default(state_dir),) if x]
    for m in agreed(state_dir).get("agreed", []):
        if m not in chain:
            chain.append(m)
    for c in _CLOUD_LANES:
        if c not in chain:
            chain.append(c)
    # FIX 2: Ensure canonical fallback is appended at the very END
    if canon not in chain:
        chain.append(canon)
    return chain

def probe_model(model, timeout=45):
    try:
        payload = {"model": model, "prompt": "hi", "stream": False, "options": {"num_predict": 1}}
        req = urllib.request.Request(_OLLAMA + "/api/generate", json.dumps(payload).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return bool(json.loads(r.read().decode()))
    except Exception:
        return False

def audit_coding_arm() -> Dict[str, Any]:
    arms = []
    try:
        from System import swarm_agent_arm_registry as reg
        for attr in ("list_agent_arms", "list_arms", "ARMS", "arms"):
            v = getattr(reg, attr, None)
            if v is not None:
                arms = v() if callable(v) else list(v)
                break
    except Exception:
        pass
    models = []
    for a in (arms or []):
        if isinstance(a, dict):
            models.append(str(a.get("model") or ""))
        else:
            models.append(str(getattr(a, "model", a)))
    seen = set()
    dups = []
    for m in models:
        if m in seen and m not in dups:
            dups.append(m)
        seen.add(m)
    for a, b in _KNOWN_DUPLICATES:
        if a in seen and b in seen:
            dup_note = a + " (same ollama blob as " + b + ")"
            if dup_note not in dups:
                dups.append(dup_note)
    try:
        tags = (_get("/api/tags").get("models") or [])
        buckets = {}
        for t in tags:
            d = str(t.get("digest") or "")
            if d:
                buckets.setdefault(d[:12], []).append(str(t.get("name") or ""))
        for d, names in sorted(buckets.items()):
            if len(names) > 1:
                dup_note = "same digest " + d + ": " + " == ".join(names)
                if dup_note not in dups:
                    dups.append(dup_note)
    except Exception:
        pass
    return {"arm_models": models, "duplicates": dups, "note": "prune non-working models after live probe"}

def self_check() -> bool:
    inv = inventory()
    assert (inv["local_dialogue"] or inv["local_vision"]), "no local models seen"
    assert fallback_chain(), "fallback chain never empty"
    return True


def engines() -> dict:
    """Engine-aware body view (2026-10-20 owner request): the body is not Ollama-only.

    Running/installed engines get live detail; untested/absent engines appear as
    candidates with owner-supplied descriptions - marked NOT_TESTED, never claimed.
    """
    out = {"engines": [], "candidates": []}
    tags = _get("/api/tags").get("models") or []
    out["engines"].append({"engine": "ollama", "status": "running",
                           "detail": str(len(tags)) + " installed tags, host " + _OLLAMA})
    try:
        probe_ps = subprocess.run(["ps", "-axo", "command="], capture_output=True, text=True, timeout=6).stdout
        rows = []
        for line in probe_ps.splitlines():
            if ("sifta-llama-prism" in line or "sifta-models" in line) and "llama-server" in line:
                toks = line.split()
                port = 0
                model = ""
                for i, tok in enumerate(toks):
                    if tok == "--port" and i + 1 < len(toks):
                        port = int(toks[i + 1])
                    if (tok in ("-m", "--model")) and i + 1 < len(toks):
                        model = toks[i + 1]
                if port:
                    rows.append({"port": port, "model": model})
        out["engines"].append({"engine": "llama_cpp_prism", "status": "running",
                               "detail": rows or "no prism server process"})
    except Exception:
        pass
    try:
        mlx_ver = importlib.import_module("mlx").__version__
    except Exception:
        mlx_ver = ""
    try:
        import mlx_vlm  # noqa
        mlx_state = "installed_runtime"
    except Exception:
        mlx_state = "installed"
    out["engines"].append({"engine": "mlx", "status": mlx_state, "detail": "mlx " + mlx_ver})
    for name, note in (
        ("vllm", "multi-engine serving runtime; not installed on this Mac"),
        ("magnitude", "new open-source local engine; claims up to 2x faster than llama.cpp on Mac "
                      "by tuning kernels to exact hardware (owner note 2026-10-20; NOT tested)"),
        ("tensorsharp", "pure C# bottom-up engine; custom fusion ops, cross-backend MLX/CUDA/CPU, "
                        "natively GGUF-compatible (owner note; NOT tested)"),
        ("rapid-mlx", "specialized local MLX runner built to challenge baseline MLX performance (owner note; NOT tested)"),
    ):
        out["candidates"].append({"engine": name, "status": "not_installed",
                                  "binary": shutil.which(name) or "", "note": note, "mark": "NOT_TESTED"})
    return out


def weights() -> dict:
    """Where the heavy LLM bytes live in this body (owner: know your own weight map)."""
    def _top_dir_bytes(path):
        rows = {}
        total = ""
        try:
            out = subprocess.run(["du", "-sh", path], capture_output=True, text=True, timeout=60).stdout.strip()
            if out:
                total = out.split(chr(9))[0]
        except Exception:
            total = ""
        top = []
        try:
            out = subprocess.run(["find", path, "-type", "f", "-size", "+300M"],
                                 capture_output=True, text=True, timeout=60).stdout
            for fn in out.splitlines():
                try:
                    top.append((os.path.getsize(fn), fn))
                except Exception:
                    pass
            top.sort(reverse=True)
        except Exception:
            pass
        return {"store": path, "total": total, "files_over_300mb": [{"bytes": s, "file": f} for s, f in top[:40]]}

    stores = [_top_dir_bytes(str(Path.home() / ".ollama/models")),
              _top_dir_bytes(str(Path.home() / ".cache/huggingface")),
              _top_dir_bytes("/Users/ioanganton/sifta-models"),
              _top_dir_bytes(str(_REPO / "models"))]
    tag_rows = _get("/api/tags").get("models") or []
    digest_owner = {}
    for t in tag_rows:
        digest_owner.setdefault(str(t.get("digest") or ""), []).append(str(t.get("name") or ""))
    for store in stores:
        if store["store"].endswith(".ollama/models"):
            for entry in store["files_over_300mb"]:
                d = str(Path(entry["file"]).name).replace("sha256-", "", 1)
                entry["tags"] = digest_owner.get(d, [])
    return {"schema": TRUTH_LABEL, "stores": stores,
            "note": "big-file map: where the body weight actually sits; ollama blobs resolved to owning tags"}


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if cmd == 'agreed':
        print(json.dumps(agreed()))
    elif cmd == 'select' and len(sys.argv) > 2:
        set_talk_default(sys.argv[2])
        print(json.dumps({'talk_default': get_talk_default()}))
    elif cmd == 'engines':
        print(json.dumps(engines(), indent=1))
    elif cmd == 'weights':
        print(json.dumps(weights(), indent=1))
    elif cmd == 'fallback':
        print(json.dumps({'fallback_chain': fallback_chain()}))
    elif cmd == 'check':
        for m in [r['name'] for r in inventory()['local_dialogue']]:
            print(json.dumps({'model': m, 'works': probe_model(m)}))
    else:
        print(json.dumps(inventory(), indent=1))