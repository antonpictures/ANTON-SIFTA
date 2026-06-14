"""swarm_diffusion_cortex.py — Alice's local GGUF diffusion cortex (llama-diffusion-cli).

CUR-F1 (2026-06-13): wires the existing ``Library/llama.cpp/build/bin/llama-diffusion-cli``
into the same (``token`` | ``done`` | ``error``) contract as ``swarm_local_brain`` /
``swarm_mlx_brain``. Diffusion models use ``diffusion:<id>`` picker tags.

Today on the M5:
  - ``diffusion:llada-8b`` — OBSERVED loadable via ``am17an/LLaDA-8B-GGUF`` (arch=llada).
  - ``diffusion:diffusiongemma-26b`` — honest not_installed until upstream arch merges.

Truth boundary: cortex composes from receipts; this organ only runs the denoising runner.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_CLI = _REPO / "Library" / "llama.cpp" / "build" / "bin" / "llama-diffusion-cli"
_PREFIX = "diffusion:"

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
        "display": "DiffusionGemma 26B (GGUF — arch not in local llama.cpp yet)",
        "repo": "unsloth/diffusiongemma-26B-A4B-it-GGUF",
        "gguf": None,
        "schedule": "entropy_bounded",
        "installed": False,
        "block_reason": "diffusion-gemma arch unmerged in Library/llama.cpp (PR #24423/#24427); use mlx_vlm fallback",
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


def _messages_to_prompt(messages: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for m in messages or []:
        role = str(m.get("role") or "user").lower()
        content = m.get("content", "")
        if isinstance(content, list):
            bits = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    bits.append(str(part.get("text") or ""))
            content = " ".join(bits)
        content = str(content or "").strip()
        if not content:
            continue
        if role == "system":
            parts.append(f"SYSTEM: {content}")
        elif role == "assistant":
            parts.append(f"ASSISTANT: {content}")
        else:
            parts.append(f"USER: {content}")
    if not parts:
        return ""
    return "\n\n".join(parts)


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
    if not is_cli_built():
        yield (
            "error",
            f"llama-diffusion-cli not found at {_cli_path()} — build with: "
            "cd Library/llama.cpp && cmake -B build -DGGML_METAL=ON && "
            "cmake --build build --target llama-diffusion-cli",
        )
        return

    gguf, entry, err = resolve_model_spec(model)
    if gguf is None:
        yield ("error", f"diffusion cortex unavailable for {model}: {err}")
        return

    prompt = _messages_to_prompt(messages)
    if not prompt.strip():
        yield ("error", "diffusion cortex received empty prompt")
        return

    _tag = request_tag or f"diffusion-{int(time.time())}"
    if timeout_s is None:
        _raw = os.environ.get("SIFTA_CORTEX_TIMEOUT_S", "600").strip().lower()
        try:
            timeout_s = None if _raw in {"0", "none", "off", ""} else int(float(_raw))
        except Exception:
            timeout_s = 600

    cmd = build_cli_command(gguf, prompt, entry, temperature=temperature, prompt_id=_tag)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(_REPO),
        )
    except subprocess.TimeoutExpired:
        yield ("error", f"llama-diffusion-cli timed out after {timeout_s}s (tag={_tag})")
        return
    except Exception as exc:
        yield ("error", f"llama-diffusion-cli failed to start: {type(exc).__name__}: {exc}")
        return

    text = parse_diffusion_cli_output(proc.stdout or "", proc.stderr or "")
    if proc.returncode != 0 and not text:
        tail = ((proc.stderr or "") + (proc.stdout or ""))[-400:].strip()
        yield ("error", f"llama-diffusion-cli exit {proc.returncode}: {tail or 'no output'}")
        return
    if not text:
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-400:].strip()
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
    yield ("done", full)


__all__ = [
    "available_models",
    "build_cli_command",
    "is_available",
    "is_cli_built",
    "parse_diffusion_cli_output",
    "resolve_model_spec",
    "stream_chat",
    "strip_prefix",
]