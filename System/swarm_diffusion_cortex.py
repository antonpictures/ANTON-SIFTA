"""swarm_diffusion_cortex.py — Alice's local GGUF diffusion cortex (llama-diffusion-cli).

CUR-F1 (2026-06-13): wires the existing ``Library/llama.cpp/build/bin/llama-diffusion-cli``
into the same (``token`` | ``done`` | ``error``) contract as ``swarm_local_brain`` /
``swarm_mlx_brain``. Diffusion models use ``diffusion:<id>`` picker tags.

Today on the M5:
  - ``diffusion:llada-8b`` — OBSERVED loadable via ``am17an/LLaDA-8B-GGUF`` (arch=llada).
  - ``diffusion:diffusiongemma-26b`` — honest not_installed until the DiffusionGemma
    GGUF and dedicated ``llama-diffusion-cli`` runner are present on this node.

Truth boundary: cortex composes from receipts; this organ only runs the denoising runner.
"""
from __future__ import annotations

import os
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_CLI = _REPO / "Library" / "llama.cpp" / "build" / "bin" / "llama-diffusion-cli"
_PREFIX = "diffusion:"
_RECEIPT_LEDGER = "diffusion_cortex_receipts.jsonl"

# Catalog ids -> HF repo + gguf filename. Only listed when weights resolve on disk.
_DIFFUSION_CATALOG: Dict[str, Dict[str, Any]] = {
    "llada-8b": {
        "display": "LLaDA 8B diffusion (GGUF llama-diffusion-cli)",
        "repo": "am17an/LLaDA-8B-GGUF",
        "gguf": "llada-8b.gguf",
        "schedule": "block",
        "block_length": 32,
        "installed": "unknown",
    },
    "diffusiongemma-26b": {
        "display": "DiffusionGemma 26B (GGUF llama-diffusion-cli, not installed)",
        "repo": "unsloth/diffusiongemma-26B-A4B-it-GGUF",
        "gguf": "diffusiongemma-26B-A4B-it-Q4_K_M.gguf",
        "schedule": "entropy_bounded",
        "installed": "unknown",
        "block_reason": (
            "DiffusionGemma needs its GGUF weights and the dedicated "
            "llama-diffusion-cli runner; standard llama-cli/llama-server/Ollama "
            "cannot generate from this block-diffusion architecture."
        ),
    },
}

_LOG_PREFIXES = (
    "ggml_",
    "llama_",
    "load_",
    "print_info",
    "sched_",
    "diffusion_params",
    "diffusion step:",
    "total time:",
    "real ",
    "user ",
    "sys ",
)


def _state_root() -> Path:
    raw = os.environ.get("SIFTA_STATE_DIR", "").strip()
    if raw:
        p = Path(raw).expanduser()
        return p if p.name == ".sifta_state" else (p / ".sifta_state")
    return _REPO / ".sifta_state"


def _append_receipt(row: Dict[str, Any]) -> None:
    """Append one local diffusion run receipt; never raises into generation."""
    try:
        payload = dict(row)
        payload.setdefault("ts", time.time())
        payload.setdefault("trace_id", str(uuid.uuid4()))
        payload.setdefault("truth_label", "SIFTA_DIFFUSION_CORTEX_RUN_V1")
        path = _state_root() / _RECEIPT_LEDGER
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def _cli_path() -> Path:
    raw = os.environ.get("SIFTA_LLAMA_DIFFUSION_CLI", "").strip()
    return Path(raw).expanduser() if raw else _DEFAULT_CLI


def strip_prefix(model: str) -> str:
    m = str(model or "").strip()
    return m[len(_PREFIX):] if m.lower().startswith(_PREFIX) else m


def _hf_cache_roots() -> tuple[Path, ...]:
    hf_home = os.environ.get("HF_HOME")
    roots: list[Path] = []
    if hf_home:
        roots.append(Path(hf_home).expanduser() / "hub")
    roots.extend((
        Path("~/.cache/huggingface/hub").expanduser(),
        Path("~/Library/Caches/huggingface/hub").expanduser(),
    ))
    return tuple(dict.fromkeys(roots))


def _resolve_gguf(repo: str, filename: str) -> Optional[Path]:
    slug = "models--" + repo.strip().replace("/", "--")
    for root in _hf_cache_roots():
        base = root / slug / "snapshots"
        if not base.is_dir():
            continue
        for snap in sorted(base.iterdir()):
            if not snap.is_dir():
                continue
            direct = snap / filename
            if direct.is_file():
                return direct
            for hit in snap.glob(filename):
                if hit.is_file():
                    return hit
    return None


def resolve_model_spec(model_id: str) -> Tuple[Optional[Path], Dict[str, Any], str]:
    """Return (gguf_path | None, catalog_entry, error_reason)."""
    bare = strip_prefix(model_id).strip().lower()
    if not bare:
        return None, {}, "empty diffusion model id"
    entry = _DIFFUSION_CATALOG.get(bare)
    if not entry:
        return None, {}, f"unknown diffusion cortex id '{bare}'"
    if entry.get("installed") is False:
        return None, entry, str(entry.get("block_reason") or "not installed")
    gguf_name = entry.get("gguf")
    if not gguf_name:
        return None, entry, str(entry.get("block_reason") or "no GGUF filename configured")
    path = _resolve_gguf(str(entry["repo"]), str(gguf_name))
    if path is None:
        return None, entry, (
            f"GGUF not cached — run: hf download {entry['repo']} "
            f"(need {gguf_name} on disk)"
        )
    return path, entry, ""


def is_cli_built() -> bool:
    cli = _cli_path()
    return cli.is_file() and os.access(cli, os.X_OK)


def is_available(model: Optional[str] = None) -> bool:
    if not is_cli_built():
        return False
    if model:
        path, _, err = resolve_model_spec(model)
        return path is not None and not err
    for mid in _DIFFUSION_CATALOG:
        path, _, err = resolve_model_spec(f"{_PREFIX}{mid}")
        if path is not None and not err:
            return True
    return False


def available_models() -> List[str]:
    """Picker ids for diffusion cortexes with cached GGUF + built CLI."""
    if not is_cli_built():
        return []
    out: List[str] = []
    for mid in _DIFFUSION_CATALOG:
        path, _, err = resolve_model_spec(f"{_PREFIX}{mid}")
        if path is not None and not err:
            out.append(f"{_PREFIX}{mid}")
    return out


def _env_int(name: str, default: int, *, low: int, high: int) -> int:
    try:
        value = int(float(os.environ.get(name, str(default)).strip()))
    except Exception:
        value = int(default)
    return max(int(low), min(int(high), int(value)))


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, list):
        bits: List[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    bits.append(str(part.get("text") or ""))
                elif "text" in part:
                    bits.append(str(part.get("text") or ""))
        return " ".join(bits)
    return str(content or "")


def _clip_text(text: str, max_chars: int) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= max_chars:
        return clean
    if max_chars <= 24:
        return clean[:max_chars]
    head = max_chars // 2
    tail = max_chars - head - 19
    return clean[:head].rstrip() + " ...[clipped]... " + clean[-tail:].lstrip()


def compact_messages_for_diffusion(messages: List[Dict[str, Any]]) -> str:
    """Build a bounded Talk prompt for llama-diffusion-cli.

    The diffusion runner is not a long-context chat engine. Feeding Alice's
    full system prompt/history can push Metal memory over the edge or leave no
    denoising canvas for the answer. This compactor preserves the current owner
    turn plus a small recent dialogue tail, with an honest Alice grounding stub.
    """
    max_prompt_chars = _env_int("SIFTA_DIFFUSION_MAX_PROMPT_CHARS", 2400, low=600, high=12000)
    max_message_chars = _env_int("SIFTA_DIFFUSION_MAX_MESSAGE_CHARS", 700, low=160, high=3000)
    keep_turns = _env_int("SIFTA_DIFFUSION_KEEP_TURNS", 6, low=1, high=20)
    system_hint_chars = _env_int("SIFTA_DIFFUSION_SYSTEM_HINT_CHARS", 520, low=0, high=2000)

    system_texts: List[str] = []
    dialogue: List[Tuple[str, str]] = []
    for m in messages or []:
        role = str(m.get("role") or "user").lower()
        content = _message_content_to_text(m.get("content", "")).strip()
        if not content:
            continue
        if role == "system":
            system_texts.append(content)
        elif role == "assistant":
            dialogue.append(("ASSISTANT", content))
        else:
            dialogue.append(("USER", content))

    parts: List[str] = [
        (
            "SYSTEM: You are Alice's local diffusion text cortex. "
            "Answer George directly in first person, grounded in the recent context. "
            "If evidence is missing, say what is known and what is not."
        )
    ]
    if system_hint_chars and system_texts:
        parts.append("SYSTEM_CONTEXT: " + _clip_text(system_texts[-1], system_hint_chars))
    for role, content in dialogue[-keep_turns:]:
        parts.append(f"{role}: {_clip_text(content, max_message_chars)}")

    if not parts:
        return ""
    prompt = "\n\n".join(parts)
    if len(prompt) <= max_prompt_chars:
        return prompt
    header = parts[0]
    marker = "\n\n[diffusion prompt clipped to recent tail]\n"
    budget = max(0, max_prompt_chars - len(header) - len(marker))
    return header + marker + prompt[-budget:]


def _messages_to_prompt(messages: List[Dict[str, Any]]) -> str:
    return compact_messages_for_diffusion(messages)


def _is_diffusion_log_line(low: str) -> bool:
    """True if a CLI line is timing/log/memory noise rather than decoded text."""
    if any(low.startswith(p) for p in _LOG_PREFIXES):
        return True
    if "mib" in low or low.startswith("["):
        return True
    return False


def parse_diffusion_cli_output(stdout: str, stderr: str) -> str:
    """Extract the final denoised text from llama-diffusion-cli combined output.

    Robust to CLI layout drift: the decoded text may print AFTER the
    ``total time:`` line (historical layout), BEFORE it, or with no timing
    marker at all across llama-diffusion-cli builds. We still prefer the last
    non-log line after the marker, but fall back to the last non-log candidate
    anywhere — so a clean exit-0 run is not reported as "no decoded text" just
    because the marker moved. (r10xx: prior logic dropped all text unless it
    strictly followed ``total time:``, which silenced llada-8b on this node.)
    """
    lines = ((stdout or "") + "\n" + (stderr or "")).splitlines()
    after_total: List[str] = []
    all_candidates: List[str] = []
    seen_total = False
    for raw in lines:
        ln = raw.strip()
        if not ln:
            continue
        low = ln.lower()
        if low.startswith("total time:"):
            seen_total = True
            continue
        if _is_diffusion_log_line(low):
            continue
        all_candidates.append(ln)
        if seen_total:
            after_total.append(ln)
    if after_total:
        return after_total[-1].strip()
    if all_candidates:
        return all_candidates[-1].strip()
    return ""


def build_cli_command(
    gguf: Path,
    prompt: str,
    entry: Dict[str, Any],
    *,
    temperature: float = 0.0,
    prompt_id: str = "",
) -> List[str]:
    steps = int(os.environ.get("SIFTA_DIFFUSION_STEPS", "64"))
    ub = int(os.environ.get("SIFTA_DIFFUSION_UB", os.environ.get("SIFTA_DIFFUSION_CANVAS_LEN", "128")))
    ngl = int(os.environ.get("SIFTA_DIFFUSION_NGL", "99"))
    block_length = int(entry.get("block_length") or os.environ.get("SIFTA_DIFFUSION_BLOCK_LENGTH", "32"))

    algorithm = 4  # CONFIDENCE_BASED default
    try:
        from System.swarm_diffusion_stigmergic_policy import StigmergicDiffusionState

        tuning = StigmergicDiffusionState.load().tune(
            base_steps=steps,
            block_length=block_length,
            canvas_ub=ub,
            prompt_id=prompt_id or prompt[:64],
        )
        steps = tuning.steps
        algorithm = tuning.algorithm
    except Exception:
        pass

    cmd = [
        str(_cli_path()),
        "-m", str(gguf),
        "-p", prompt,
        "-ub", str(ub),
        "--diffusion-steps", str(steps),
        "--diffusion-algorithm", str(algorithm),
        "-ngl", str(ngl),
        "--temp", str(float(temperature)),
    ]
    schedule = str(entry.get("schedule") or "block")
    if schedule == "block":
        cmd.extend(["--diffusion-block-length", str(block_length)])
    else:
        eps = os.environ.get("SIFTA_DIFFUSION_EPS", "0.001")
        cmd.extend(["--diffusion-eps", str(eps)])
    return cmd


def stream_chat(
    model: str,
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.0,
    request_tag: Optional[str] = None,
    timeout_s: Optional[int] = None,
) -> Iterator[Tuple[str, Any]]:
    """Run llama-diffusion-cli and yield token/done/error like other local brains."""
    started = time.time()
    _tag = request_tag or f"diffusion-{int(started)}"
    if not is_cli_built():
        _append_receipt({
            "status": "error",
            "model": str(model or ""),
            "request_tag": _tag,
            "error": f"llama-diffusion-cli not found at {_cli_path()}",
        })
        yield (
            "error",
            f"llama-diffusion-cli not found at {_cli_path()} — build with: "
            "cd Library/llama.cpp && cmake -B build -DGGML_METAL=ON && "
            "cmake --build build --target llama-diffusion-cli",
        )
        return

    gguf, entry, err = resolve_model_spec(model)
    if gguf is None:
        _append_receipt({
            "status": "error",
            "model": str(model or ""),
            "request_tag": _tag,
            "error": f"diffusion cortex unavailable: {err}",
        })
        yield ("error", f"diffusion cortex unavailable for {model}: {err}")
        return

    prompt = _messages_to_prompt(messages)
    if not prompt.strip():
        _append_receipt({
            "status": "error",
            "model": str(model or ""),
            "request_tag": _tag,
            "gguf": str(gguf),
            "error": "empty compacted prompt",
        })
        yield ("error", "diffusion cortex received empty prompt")
        return

    if timeout_s is None:
        _raw = os.environ.get("SIFTA_CORTEX_TIMEOUT_S", "600").strip().lower()
        try:
            timeout_s = None if _raw in {"0", "none", "off", ""} else int(float(_raw))
        except Exception:
            timeout_s = 600

    cmd = build_cli_command(gguf, prompt, entry, temperature=temperature, prompt_id=_tag)
    base_receipt = {
        "model": str(model or ""),
        "request_tag": _tag,
        "gguf": str(gguf),
        "cli": str(_cli_path()),
        "timeout_s": timeout_s,
        "prompt_chars": len(prompt),
        "message_count": len(messages or []),
        "steps": os.environ.get("SIFTA_DIFFUSION_STEPS", "64"),
        "canvas_ub": os.environ.get("SIFTA_DIFFUSION_UB", os.environ.get("SIFTA_DIFFUSION_CANVAS_LEN", "128")),
    }
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(_REPO),
        )
    except subprocess.TimeoutExpired:
        _append_receipt({
            **base_receipt,
            "status": "timeout",
            "elapsed_s": round(time.time() - started, 3),
            "error": f"llama-diffusion-cli timed out after {timeout_s}s",
        })
        yield ("error", f"llama-diffusion-cli timed out after {timeout_s}s (tag={_tag})")
        return
    except Exception as exc:
        _append_receipt({
            **base_receipt,
            "status": "error",
            "elapsed_s": round(time.time() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
        })
        yield ("error", f"llama-diffusion-cli failed to start: {type(exc).__name__}: {exc}")
        return

    text = parse_diffusion_cli_output(proc.stdout or "", proc.stderr or "")
    if proc.returncode != 0:
        tail = ((proc.stderr or "") + (proc.stdout or ""))[-400:].strip()
        _append_receipt({
            **base_receipt,
            "status": "error",
            "returncode": proc.returncode,
            "elapsed_s": round(time.time() - started, 3),
            "error": tail or text or "no output",
        })
        yield ("error", f"llama-diffusion-cli exit {proc.returncode}: {tail or text or 'no output'}")
        return
    if not text:
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-400:].strip()
        _append_receipt({
            **base_receipt,
            "status": "empty",
            "returncode": proc.returncode,
            "elapsed_s": round(time.time() - started, 3),
            "error": tail or "empty",
        })
        yield (
            "error",
            f"llama-diffusion-cli returned no decoded text (exit {proc.returncode}); "
            f"raw tail: {tail or 'empty'}",
        )
        return

    words = text.split()
    acc: List[str] = []
    for w in words:
        acc.append(w)
        yield ("token", w + " ")
        time.sleep(0.002)
    full = " ".join(acc).strip() or text.strip()
    try:
        from System.swarm_diffusion_stigmergic_policy import StigmergicDiffusionState

        StigmergicDiffusionState.load().record_generation(
            prompt_id=_tag,
            repeat_idx=0,
            output=full,
        )
    except Exception:
        pass
    _append_receipt({
        **base_receipt,
        "status": "success",
        "returncode": proc.returncode,
        "elapsed_s": round(time.time() - started, 3),
        "output_chars": len(full),
        "output_preview": full[:240],
    })
    yield ("done", full)


__all__ = [
    "available_models",
    "build_cli_command",
    "compact_messages_for_diffusion",
    "is_available",
    "is_cli_built",
    "parse_diffusion_cli_output",
    "resolve_model_spec",
    "stream_chat",
    "strip_prefix",
]
