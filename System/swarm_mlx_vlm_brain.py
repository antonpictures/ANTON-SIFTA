#!/usr/bin/env python3
"""
System/swarm_mlx_vlm_brain.py — Native MLX VLM cortex for Alice (M5 direct, vision+chat).

Drop-in peer to swarm_local_brain.py (same contract) and swarm_gemini_brain.
This is the strong local vision-capable cortex to replace/fallback the blanking 8b on
image describe, attached screenshots, "on your body screen" grids, and general chat.

- Loads the OptiQ-3.7bpw-mlx (Qwen3.5-based VLM) from the local models/ dir.
- Supports text + image= (path or list of paths) for real vision (no more empty/mantra on pics).
- Uses mlx_vlm.generate (full gen + simulated token stream to match contract).
- Tool calling / chat template supported by the underlying model when prompted correctly.
- No extra server process needed (direct, fast on Apple silicon).

Env:
    SIFTA_MLX_VLM_DIR  (override the default local path)
    SIFTA_MLX_VLM_MAX_TOKENS

Contract (identical surface for easy preference in sifta_app / talk widget):
    is_available() -> bool
    available_models() -> list[str]
    stream_chat(model, messages, *, request_tag=None, temperature=0.7, timeout_s=300, images=None)
        -> Iterator[Tuple[str, Any]]
    get_default_model() -> str
"""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False
    Image = None  # type: ignore

load: Any = None
mlx_generate: Any = None
try:
    MLX_VLM_AVAILABLE = importlib.util.find_spec("mlx_vlm") is not None
except Exception:
    MLX_VLM_AVAILABLE = False

_DEFAULT_MODEL_DIR = os.path.expanduser(
    "~/Music/ANTON_SIFTA/models/osmQwopus-3.6-27B-OptiQ-3.7bpw-mlx"
)
_HF_MLX_VLM_REPOS = (
    "SuperagenticAI/gemma-4-12b-it-8bit-mlx",
)
_MODEL: Any = None
_PROCESSOR: Any = None


def _ensure_mlx_vlm_imported() -> bool:
    global MLX_VLM_AVAILABLE, load, mlx_generate
    if load is not None and mlx_generate is not None:
        return True
    if not MLX_VLM_AVAILABLE:
        return False
    try:
        from mlx_vlm import load as _load, generate as _generate
    except Exception:
        MLX_VLM_AVAILABLE = False
        return False
    load = _load
    mlx_generate = _generate
    return True

def _get_model_dir(name: Optional[str] = None) -> str:
    """Resolve model dir. If name given (e.g. from stream_chat model arg 'mlx-vlm:foo'), pick that.
    Falls back to env, then first discovered vision dir, then hardcoded osm default.
    Supports unified multi-VLM field (osm + Keye etc.).
    """
    if name:
        n = name.replace("mlx-vlm:", "").strip()
        base = Path("~/Music/ANTON_SIFTA/models").expanduser()
        cand = base / n
        if cand.exists() and _is_model_present(cand):
            return str(cand)
        hf = _hf_cached_model_dir(n)
        if hf and _is_model_present(Path(hf)):
            return hf
        # try partial match on basename
        for d in _find_vision_model_dirs():
            tag = _model_tag_for_dir(d).replace("mlx-vlm:", "")
            if n in Path(d).name or Path(d).name in n or n.lower() == tag.lower():
                return d
    env = os.environ.get("SIFTA_MLX_VLM_DIR")
    if env and Path(env).exists():
        return env
    found = _find_vision_model_dirs()
    if found:
        return found[0]
    return _DEFAULT_MODEL_DIR

def _is_model_present(d: Path) -> bool:
    if not d.exists():
        return False
    # Look for common MLX/HF weight indicators (config + any weights or mlx shards)
    has_config = (d / "config.json").exists()
    has_weights = bool(list(d.glob("*.safetensors")) or list(d.glob("*model*.npz")) or list(d.glob("*.gguf")))
    has_mlx_marker = (d / "mlx_model").exists() or any("mlx" in p.name.lower() for p in d.iterdir() if p.is_file())
    return has_config or has_weights or has_mlx_marker


def _hf_cache_roots() -> tuple[Path, ...]:
    hf_home = os.environ.get("HF_HOME")
    roots = []
    if hf_home:
        roots.append(Path(hf_home).expanduser() / "hub")
    roots.extend((
        Path("~/.cache/huggingface/hub").expanduser(),
        Path("~/Library/Caches/huggingface/hub").expanduser(),
    ))
    return tuple(dict.fromkeys(roots))


def _hf_repo_cache_name(repo_id: str) -> str:
    return "models--" + repo_id.strip().replace("/", "--")


def _repo_id_from_hf_snapshot(path: str | Path) -> str:
    p = Path(path)
    for parent in (p, *p.parents):
        if parent.name.startswith("models--"):
            return parent.name.removeprefix("models--").replace("--", "/")
    return ""


def _known_mlx_vlm_repo_ids() -> tuple[str, ...]:
    """Static allowlist + curated CORTEX_OPTIONS mlx-vlm repos (r633, r615-twin).

    r615 lesson, mlx-vlm lane: once a model has a curated eval entry it must
    appear automatically when its weights land in the HF cache — no per-model
    code edit. George kept hitting "I pulled it, it's not in the picker" on the
    Ollama side; this closes the same wound for `mlx-vlm:` repos (TyKaoz, AEON-7
    abliterated unified, future candidates). Lazy import breaks the
    cortex_options import cycle; planning rows whose weights are NOT on disk
    still return no snapshot, so nothing fake appears.
    """
    repos: list[str] = list(_HF_MLX_VLM_REPOS)
    try:
        from System.swarm_cortex_options import CORTEX_OPTIONS as _CO
        for opt in _CO:
            raw = str(opt.get("id", "") or "").strip()
            if raw.lower().startswith("mlx-vlm:"):
                repo = raw.split(":", 1)[1].strip().strip("/")
                if repo and repo not in repos:
                    repos.append(repo)
    except Exception:
        pass
    return tuple(repos)


def _hf_cached_model_dir(repo_id_or_name: str) -> str:
    """Resolve a Hugging Face cache snapshot for a known MLX VLM repo."""
    requested = (repo_id_or_name or "").strip().strip("/")
    if not requested:
        return ""
    requested_low = requested.lower()
    for repo_id in _known_mlx_vlm_repo_ids():
        if requested_low not in {repo_id.lower(), repo_id.rsplit("/", 1)[-1].lower()}:
            continue
        cache_name = _hf_repo_cache_name(repo_id)
        for root in _hf_cache_roots():
            model_root = root / cache_name
            snapshots = model_root / "snapshots"
            if not snapshots.exists():
                continue
            ref = model_root / "refs" / "main"
            if ref.exists():
                try:
                    snap = snapshots / ref.read_text(encoding="utf-8").strip()
                    if _is_model_present(snap):
                        return str(snap)
                except Exception:
                    pass
            for snap in sorted(snapshots.iterdir(), reverse=True):
                if snap.is_dir() and _is_model_present(snap):
                    return str(snap)
    return ""


def _hf_cached_mlx_vlm_dirs() -> List[str]:
    out: List[str] = []
    for repo_id in _known_mlx_vlm_repo_ids():
        resolved = _hf_cached_model_dir(repo_id)
        if resolved and resolved not in out:
            out.append(resolved)
    return out


def _model_tag_for_dir(model_dir: str | Path) -> str:
    repo_id = _repo_id_from_hf_snapshot(model_dir)
    if repo_id:
        return f"mlx-vlm:{repo_id}"
    return f"mlx-vlm:{Path(model_dir).name}"


def _find_vision_model_dirs() -> List[str]:
    """Discover all local vision model dirs under models/ (for unified field with multiple VLMs).
    Returns full paths to dirs that look like MLX vision weights (config + safetensors).
    This lets both osmQwopus and Keye (and future) be available without env flip or hardcode.
    """
    base = Path("~/Music/ANTON_SIFTA/models").expanduser()
    if not base.exists():
        return []
    found: List[str] = []
    for d in sorted(base.iterdir()):
        if d.is_dir() and _is_model_present(d):
            found.append(str(d))  # all present models/ dirs with weights are our VLMs (osmQwopus solid + Keye experimental)
    for d in _hf_cached_mlx_vlm_dirs():
        if d not in found:
            found.append(d)
    # r533 (cowork, George 2026-06-04): prefer the SMALL gemma-4 edge VLMs (e2b/e4b) as the
    # in-process eye. The big 27B/30B (osmQwopus/osmKeye) SIGBUS-crash when loaded in-process
    # (r413 guard) — which is why the local eye kept failing even though they were on disk all
    # along. The small gemma loads safely in-process; the big ones drop to last resort (still
    # reachable via the safe mlx-omni-server route).
    def _mlx_eye_rank(name: str) -> int:
        n = name.lower()
        if "e2b" in n or "e4b" in n:
            return 0  # small gemma-4 edge model — safe to load in-process
        if "27b" in n or "30b" in n or "qwopus" in n or "keye" in n:
            return 2  # big MLX VLM — SIGBUS in-process; last resort only
        return 1
    found.sort(key=lambda p: (_mlx_eye_rank(Path(p).name), Path(p).name))
    return found


def _prepare_image(img: Union[str, "Image.Image", List, None]) -> Union[str, "Image.Image", List, None]:
    """Robust image prep for Qwen2-VL style processors in mlx_vlm.
    Accepts path or PIL. Path inputs stay as paths to match the mlx_vlm CLI;
    PIL inputs are resized defensively.
    """
    if img is None:
        return None
    if isinstance(img, (list, tuple)):
        return [_prepare_image(x) for x in img]
    if isinstance(img, str):
        # mlx_vlm's current public API and CLI expect image paths/lists. Passing
        # a PIL object can bypass the same preprocessing path that works from
        # `python -m mlx_vlm.generate`, so keep path inputs as paths.
        return img
    elif Image is not None and isinstance(img, Image.Image):
        p = img.convert("RGB")
    else:
        return img

    # Cap very large images (common cause of "tokens:0, features: N" on VLMs)
    max_side = 1536
    if max(p.size) > max_side:
        ratio = max_side / max(p.size)
        new_size = (max(1, int(p.size[0] * ratio)), max(1, int(p.size[1] * ratio)))
        p = p.resize(new_size, Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.ANTIALIAS)
    return p


def _media_count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (list, tuple)):
        return len(value)
    return 1


def _apply_generation_chat_template(
    prompt: str,
    *,
    image: Any = None,
    audio: Any = None,
    video: Any = None,
) -> str:
    """Apply mlx_vlm's model-specific chat template for multimodal prompts.

    The raw API accepts an already-templated prompt. The CLI applies this
    before generation; without it Gemma 4 can immediately emit EOS and return
    an empty caption even though the same image works through the CLI.
    """
    try:
        from mlx_vlm.prompt_utils import apply_chat_template

        config = getattr(_MODEL, "config", None)
        if _PROCESSOR is None or config is None:
            return prompt
        kwargs: Dict[str, Any] = {
            "num_images": _media_count(image),
            "num_audios": _media_count(audio),
            "enable_thinking": False,
        }
        if video is not None:
            kwargs["video"] = video
        return apply_chat_template(_PROCESSOR, config, prompt, **kwargs)
    except Exception:
        return prompt

def _inprocess_mlx_enabled() -> bool:
    """cowork 2026-06-03 SAFETY GATE. Loading a 27B MLX VLM IN-PROCESS inside the PyQt
    desktop SIGBUS-crashed it twice (George 2026-06-02): MLX drives Metal from the brain
    worker thread while Qt drives Metal on the main thread (QtMultimedia video sink), on
    Python 3.14. The body (the desktop) must not die to load an eye. So the in-process path
    is OFF by default; osmQwopus runs SAFELY in its OWN process via mlx-omni-server (the
    `mlx:` route, swarm_mlx_brain). A native bus error is NOT catchable in Python, so the
    only real protection is to not load in-process at all. Opt back in only if you accept
    the crash risk: SIFTA_ENABLE_INPROCESS_MLX_VLM=1."""
    import os as _os
    return _os.environ.get("SIFTA_ENABLE_INPROCESS_MLX_VLM", "").strip().lower() in {"1", "true", "yes", "on"}


def is_available() -> bool:
    if not MLX_VLM_AVAILABLE:
        return False
    if not _inprocess_mlx_enabled():
        return False
    d = Path(_get_model_dir())
    return _is_model_present(d)


def describe_available(name: Optional[str] = None) -> bool:
    """True when the out-of-process MLX VLM describe helper can be used.

    ``is_available()`` means the in-process PyQt/MLX path is enabled. That
    stays OFF by default after the desktop crash guard. Browser-photo
    descriptions use ``describe_image()``, which launches a child process so
    the desktop body survives even if MLX/Metal crashes.
    """
    if not MLX_VLM_AVAILABLE:
        return False
    d = Path(_get_model_dir(name))
    return _is_model_present(d)


def describe_models() -> List[str]:
    """List local VLM models usable by the safe child-process describe path."""
    if not MLX_VLM_AVAILABLE:
        return []
    found = _find_vision_model_dirs()
    if found:
        return [_model_tag_for_dir(d) for d in found]
    if describe_available():
        return [_model_tag_for_dir(_get_model_dir())]
    return []

def available_models() -> List[str]:
    """List all discovered local vision models (osmQwopus, Keye, future VLMs).
    Enables the picker/dropdown to offer multiple without hardcode.
    """
    if not MLX_VLM_AVAILABLE:
        return []
    if not _inprocess_mlx_enabled():
        return []
    found = _find_vision_model_dirs()
    if not found:
        if is_available():
            return [_model_tag_for_dir(_get_model_dir())]
        return []
    return [_model_tag_for_dir(d) for d in found]

def _load_if_needed(name: Optional[str] = None) -> bool:
    global _MODEL, _PROCESSOR
    if _MODEL is not None and _PROCESSOR is not None:
        return True
    if not _inprocess_mlx_enabled():
        return False
    if not _ensure_mlx_vlm_imported():
        return False
    model_dir = _get_model_dir(name)
    d = Path(model_dir)
    if not _is_model_present(d):
        return False
    try:
        _MODEL, _PROCESSOR = load(str(d), trust_remote_code=True)
        return True
    except Exception as e:
        # Log but do not crash the organism. Common on memory pressure for 27B-class VLMs.
        msg = str(e)
        if "Memory" in msg or "OOM" in msg or "Insufficient" in msg:
            print("[swarm_mlx_vlm_brain] load hit memory pressure (needs ~16-24GB unified RAM headroom). Will retry on next use.")
        else:
            print(f"[swarm_mlx_vlm_brain] load failed for {model_dir}: {e}")
        _MODEL = None
        _PROCESSOR = None
        return False

def _messages_to_prompt(messages: List[Dict[str, Any]]) -> str:
    """Simple text prompt builder. VLM chat template is applied inside the model when possible.
    For better results on Qwen-style, we can later use processor.apply_chat_template.
    """
    parts = []
    for m in messages:
        role = (m.get("role") or "user").lower()
        content = m.get("content", "")
        if isinstance(content, list):
            # Multimodal content: extract text parts for the prompt (image handled separately)
            text_bits = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text_bits.append(part.get("text", ""))
            content = " ".join(text_bits)
        if role == "system":
            parts.append(f"SYSTEM: {content}")
        elif role == "assistant":
            parts.append(f"ASSISTANT: {content}")
        else:
            parts.append(f"USER: {content}")
    return "\n\n".join(parts) + "\n\nASSISTANT:"

def _stream_chat_in_process(
    model: str,
    messages: List[Dict[str, Any]],
    *,
    request_tag: Optional[str] = None,
    temperature: float = 0.7,
    timeout_s: int = 300,
    images: Optional[Union[str, List[str]]] = None,
) -> Iterator[Tuple[str, Any]]:
    """
    Stream chat (and vision) from the local MLX VLM.
    Extra kwarg `images` (path or list of paths) for direct vision calls.
    Yields the same ("token", ...), ("done", full), ("error", ...) as the Ollama local brain.
    """
    if not _load_if_needed(model):
        yield ("error", f"MLX VLM cortex not available (dir={_get_model_dir(model)}, mlx_vlm installed={MLX_VLM_AVAILABLE})")
        return

    prompt = _messages_to_prompt(messages)

    # Resolve images: accept str, list, or pull from last message if it used OpenAI vision shape
    img_arg: Optional[Union[str, List[str]]] = None
    if images:
        img_arg = images
    else:
        # Try to extract from last user message content list (future-proof for widget)
        if messages:
            last = messages[-1]
            if last.get("role") in (None, "user"):
                image_path = str(last.get("image_path") or "").strip()
                if image_path and os.path.exists(image_path):
                    img_arg = image_path
                content = last.get("content")
                if img_arg is None and isinstance(content, list):
                    imgs = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") in ("image", "image_url"):
                            url = part.get("image_url") or part.get("image")
                            if isinstance(url, dict):
                                url = url.get("url", "")
                            if url and (os.path.exists(str(url)) or str(url).startswith(("file:", "/"))):
                                imgs.append(str(url).replace("file://", ""))
                    if imgs:
                        img_arg = imgs[0] if len(imgs) == 1 else imgs

    img_arg = _prepare_image(img_arg)
    prompt = _apply_generation_chat_template(prompt, image=img_arg)

    max_tokens = int(os.environ.get("SIFTA_MLX_VLM_MAX_TOKENS", "768"))

    try:
        result = mlx_generate(
            _MODEL,
            _PROCESSOR,
            prompt,
            image=img_arg,
            temperature=float(temperature),
            max_tokens=max_tokens,
            verbose=False,
        )
        text = ""
        if result is not None:
            if hasattr(result, "text"):
                text = result.text or ""
            else:
                text = str(result)

        if not text:
            yield ("done", "")
            return

        # Simulate streaming to keep UI responsive and match contract used by Talk widget + sifta_app
        # (real token streaming can be added later via lower-level mlx sampling loop)
        words = text.split(" ")
        acc: List[str] = []
        for w in words:
            if w:
                acc.append(w)
                yield ("token", w + " ")
                # tiny yield to let Qt event loop breathe on long responses
                time.sleep(0.002)

        full = " ".join(acc).strip()
        if not full:
            full = text.strip()
        yield ("done", full)

    except Exception as e:
        emsg = str(e)
        if "Memory" in emsg or "OOM" in emsg or "Insufficient" in emsg:
            yield ("error", "MLX VLM out of memory (close other apps / needs more unified RAM headroom for the 27B VLM). Text-only fallback active.")
        else:
            yield ("error", f"MLX VLM generate failed: {type(e).__name__}: {e}")

_IPC_MARKER = "__SIFTA_MLX_VLM_RESULT__"


def _stream_text(text: str) -> Iterator[Tuple[str, Any]]:
    if not text:
        yield ("done", "")
        return
    words = text.split(" ")
    acc: List[str] = []
    for word in words:
        if word:
            acc.append(word)
            yield ("token", word + " ")
            time.sleep(0.002)
    full = " ".join(acc).strip() or text.strip()
    yield ("done", full)


def _run_child_request(request: Dict[str, Any], timeout_s: int) -> Dict[str, Any]:
    env = dict(os.environ)
    env["SIFTA_ENABLE_INPROCESS_MLX_VLM"] = "1"
    cmd = [sys.executable, str(Path(__file__).resolve()), "--sifta-mlx-vlm-child"]
    try:
        proc = subprocess.run(
            cmd,
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=float(timeout_s),
            cwd=str(Path(__file__).resolve().parents[1]),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"MLX VLM subprocess timed out after {timeout_s}s"}
    except Exception as exc:
        return {"ok": False, "error": f"MLX VLM subprocess launch failed: {exc}"}

    stdout = proc.stdout or ""
    marker_index = stdout.rfind(_IPC_MARKER)
    if marker_index >= 0:
        raw = stdout[marker_index + len(_IPC_MARKER):].strip()
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception as exc:
            return {"ok": False, "error": f"MLX VLM subprocess returned invalid JSON: {exc}"}

    if proc.returncode != 0:
        if proc.returncode < 0:
            sig = -proc.returncode
            try:
                sig_name = signal.Signals(sig).name
            except Exception:
                sig_name = f"signal {sig}"
            return {"ok": False, "error": f"MLX VLM subprocess crashed with {sig_name}; desktop process survived."}
        stderr_tail = (proc.stderr or stdout or "").strip()[-700:]
        return {"ok": False, "error": f"MLX VLM subprocess exited rc={proc.returncode}: {stderr_tail or 'no stderr'}"}

    return {"ok": False, "error": "MLX VLM subprocess returned no result"}


def stream_chat(
    model: str,
    messages: List[Dict[str, Any]],
    *,
    request_tag: Optional[str] = None,
    temperature: float = 0.7,
    timeout_s: int = 300,
    images: Optional[Union[str, List[str]]] = None,
) -> Iterator[Tuple[str, Any]]:
    if _inprocess_mlx_enabled():
        yield from _stream_chat_in_process(
            model,
            messages,
            request_tag=request_tag,
            temperature=temperature,
            timeout_s=timeout_s,
            images=images,
        )
        return

    max_tokens = int(os.environ.get("SIFTA_MLX_VLM_MAX_TOKENS", "768"))
    result = _run_child_request(
        {
            "mode": "stream_chat",
            "model": model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": max_tokens,
            "images": images,
        },
        timeout_s=timeout_s,
    )
    if not result.get("ok"):
        yield ("error", str(result.get("error") or "MLX VLM subprocess failed"))
        return
    yield from _stream_text(str(result.get("text") or ""))


def get_default_model() -> str:
    if is_available():
        return available_models()[0]
    return ""

# Convenience for direct vision describe (used by widget describe paths)
def _describe_image_in_process(image_path: str, prompt: str = "Describe this image in detail for George.", **kwargs) -> str:
    """One-shot vision helper. Returns the full text (no streaming)."""
    if not _load_if_needed(None):  # describe uses default or env; pass name if extended
        return "[mlx-vlm not available]"
    try:
        img = _prepare_image(image_path)
        prompt = _apply_generation_chat_template(prompt, image=img)
        result = mlx_generate(
            _MODEL,
            _PROCESSOR,
            prompt,
            image=img,
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 600),
            verbose=False,
        )
        if hasattr(result, "text"):
            return result.text or ""
        return str(result)
    except Exception as e:
        emsg = str(e)
        if "Memory" in emsg or "OOM" in emsg or "Insufficient" in emsg:
            return "[mlx-vlm: out of memory for vision (needs headroom for the full VLM). Use a lighter local eye or free RAM.]"
        return f"[mlx-vlm describe error: {e}]"


def describe_image(image_path: str, prompt: str = "Describe this image in detail for George.", **kwargs) -> str:
    if _inprocess_mlx_enabled():
        return _describe_image_in_process(image_path, prompt, **kwargs)

    timeout_s = int(kwargs.get("timeout_s") or os.environ.get("SIFTA_MLX_VLM_DESCRIBE_TIMEOUT_S", "300"))
    result = _run_child_request(
        {
            "mode": "describe_image",
            "image_path": image_path,
            "prompt": prompt,
            "temperature": float(kwargs.get("temperature", 0.3)),
            "max_tokens": int(kwargs.get("max_tokens", 600)),
        },
        timeout_s=timeout_s,
    )
    if not result.get("ok"):
        return f"[mlx-vlm subprocess describe error: {result.get('error') or 'unknown error'}]"
    return str(result.get("text") or "")


def _child_result(payload: Dict[str, Any]) -> None:
    sys.stdout.write(_IPC_MARKER + json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


def _run_child_once() -> int:
    try:
        request = json.loads(sys.stdin.read() or "{}")
    except Exception as exc:
        _child_result({"ok": False, "error": f"invalid child request JSON: {exc}"})
        return 2

    mode = str(request.get("mode") or "").strip()
    if mode == "stream_chat":
        os.environ["SIFTA_MLX_VLM_MAX_TOKENS"] = str(int(request.get("max_tokens") or 768))
        text_parts: List[str] = []
        done_text = ""
        for kind, payload in _stream_chat_in_process(
            str(request.get("model") or ""),
            request.get("messages") or [],
            temperature=float(request.get("temperature", 0.7)),
            timeout_s=int(request.get("timeout_s") or 300),
            images=request.get("images"),
        ):
            if kind == "token":
                text_parts.append(str(payload))
            elif kind == "done":
                done_text = str(payload or "")
                break
            elif kind == "error":
                _child_result({"ok": False, "error": str(payload)})
                return 1
        _child_result({"ok": True, "text": done_text or "".join(text_parts).strip()})
        return 0

    if mode == "describe_image":
        text = _describe_image_in_process(
            str(request.get("image_path") or ""),
            str(request.get("prompt") or "Describe this image in detail for George."),
            temperature=float(request.get("temperature", 0.3)),
            max_tokens=int(request.get("max_tokens") or 600),
        )
        _child_result({"ok": True, "text": text})
        return 0

    _child_result({"ok": False, "error": f"unknown child mode: {mode or '<empty>'}"})
    return 2


if __name__ == "__main__" and "--sifta-mlx-vlm-child" in sys.argv:
    raise SystemExit(_run_child_once())
