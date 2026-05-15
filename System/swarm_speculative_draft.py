"""
swarm_speculative_draft.py - SIFTA verifier-required speculative lane.

The behind-draft lane is strongest when the draft and target models share a
tokenizer/vocabulary family. Alice's current production cleanup keeps only the
tested Talk cortex by default, so this organ stays disabled unless the operator
explicitly supplies `SIFTA_DRAFT_MODEL` for a future bake-off.

Important boundary: same vocabulary makes token-level verification possible; it
does not make a draft committed speech. The target model / verifier still owns
accept/reject. Ollama chat does not expose native prefix-logit verification, so
this module stays a verifier-required prefetch organ unless a caller provides a
real verifier or the runtime grows native speculative decoding.

Law:
- draft_ready rows are append-only receipts, not committed speech.
- consume_draft(...) returns None unless the caller supplies a verifier.
- verification creates a second append-only row; the buffer is never rewritten.
- without verifier support in the runtime, this module is a safe prefetch organ,
  not an SD/SSD implementation.

Kill switch:
  SIFTA_SPECULATIVE_DRAFT=0   default, no-op
  SIFTA_SPECULATIVE_DRAFT=1   background drafting enabled
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Callable, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]

try:
    from System.swarm_model_tokenizer_receipt import compare_model_tokenizers
except Exception:  # pragma: no cover
    compare_model_tokenizers = None  # type: ignore[assignment]

try:
    from System.sifta_inference_defaults import CANONICAL_OLLAMA_DEFAULT
except Exception:  # pragma: no cover
    CANONICAL_OLLAMA_DEFAULT = "alice-m5-cortex-8b-6.3gb:latest"

log = logging.getLogger(__name__)

TRUTH_LABEL = "SPECULATIVE_DRAFT_V2"

_ENABLED = os.getenv("SIFTA_SPECULATIVE_DRAFT", "0") == "1"
_DRAFT_MODEL = os.getenv("SIFTA_DRAFT_MODEL", "")
_MAIN_MODEL = os.getenv("SIFTA_MAIN_MODEL", CANONICAL_OLLAMA_DEFAULT)
_OLLAMA_BASE = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_DIR = Path(os.getenv("SIFTA_STATE_DIR", str(_REPO_ROOT / ".sifta_state")))
_BUFFER_FILE = _STATE_DIR / "alice_draft_buffer.jsonl"
_MAX_DRAFT_TOKENS = int(os.getenv("SIFTA_DRAFT_TOKENS", "120"))
_DRAFT_TTL_S = float(os.getenv("SIFTA_DRAFT_TTL_S", "12.0"))
_DRAFT_TIMEOUT_S = float(os.getenv("SIFTA_DRAFT_TIMEOUT_S", "8.0"))
_SAME_VOCAB_HINT = os.getenv("SIFTA_DRAFT_SAME_VOCAB", "gemma4-family")
_NATIVE_TOKEN_VERIFIER = os.getenv("SIFTA_NATIVE_TOKEN_VERIFIER", "0") == "1"

_lock = threading.Lock()
_pending_text: Optional[str] = None
_draft_result: Optional[dict] = None
_draft_thread: Optional[threading.Thread] = None


def _token_overlap(a: str, b: str) -> float:
    """Diagnostic unigram overlap; never used as acceptance proof."""
    ta = set(re.findall(r"\w+", (a or "").lower()))
    tb = set(re.findall(r"\w+", (b or "").lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _model_family(model: str) -> str:
    """Coarse local family tag. This is routing metadata, not proof."""
    m = (model or "").lower()
    if "gemma4" in m or "gemma-4" in m or "sifta-gemma4" in m or m.startswith("gemma4"):
        return "gemma4"
    if "qwen" in m:
        return "qwen"
    return re.sub(r"[^a-z0-9]+", "-", m.split(":")[0]).strip("-") or "unknown"


def _parse_ollama_show_text(text: str) -> dict:
    """Parse the small subset of `ollama show` text we need for receipts."""
    out: dict = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or " " not in line:
            continue
        for key in ("architecture", "parameters", "context length", "embedding length", "quantization"):
            if line.startswith(key):
                out[key.replace(" ", "_")] = line[len(key):].strip()
                break
    return out


def _ollama_show_summary(model: str) -> dict:
    """Best-effort model metadata via Ollama /api/show. Never required."""
    payload = json.dumps({"model": model}).encode()
    req = urllib.request.Request(
        f"{_OLLAMA_BASE}/api/show",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read())
    except Exception:
        return {}

    details = data.get("details") if isinstance(data.get("details"), dict) else {}
    model_info = data.get("model_info") if isinstance(data.get("model_info"), dict) else {}
    modelfile = data.get("modelfile") or ""
    parsed = _parse_ollama_show_text(str(data.get("license") or ""))
    parsed.update(_parse_ollama_show_text(str(modelfile)))

    arch = (
        details.get("family")
        or model_info.get("general.architecture")
        or parsed.get("architecture")
    )
    params = details.get("parameter_size") or parsed.get("parameters")
    quant = details.get("quantization_level") or parsed.get("quantization")
    embedding = (
        model_info.get("gemma4.embedding_length")
        or model_info.get("gemma3.embedding_length")
        or model_info.get("llama.embedding_length")
        or parsed.get("embedding_length")
    )
    context = (
        model_info.get("gemma4.context_length")
        or model_info.get("gemma3.context_length")
        or model_info.get("llama.context_length")
        or parsed.get("context_length")
    )
    return {
        "architecture": str(arch) if arch else None,
        "parameters": str(params) if params else None,
        "quantization": str(quant) if quant else None,
        "embedding_length": str(embedding) if embedding else None,
        "context_length": str(context) if context else None,
    }


def model_pair_truth(*, probe: bool = False) -> dict:
    """Return the draft/target territory facts for receipts and UI.

    Same-family Gemma4 drafting is the correct road to token-level SD. This
    function still refuses to claim native SD unless a verifier exists.
    """
    draft_meta = _ollama_show_summary(_DRAFT_MODEL) if probe else {}
    main_meta = _ollama_show_summary(_MAIN_MODEL) if probe else {}
    draft_family = _model_family(_DRAFT_MODEL)
    main_family = _model_family(_MAIN_MODEL)
    same_family = draft_family == main_family and draft_family != "unknown"

    draft_arch = draft_meta.get("architecture")
    main_arch = main_meta.get("architecture")
    same_architecture = None
    if draft_arch and main_arch:
        same_architecture = draft_arch == main_arch

    draft_embed = draft_meta.get("embedding_length")
    main_embed = main_meta.get("embedding_length")
    same_embedding = None
    if draft_embed and main_embed:
        same_embedding = draft_embed == main_embed

    same_vocab_status = (
        "EXPECTED_GEMMA4_SHARED_TOKENIZER"
        if same_family and _SAME_VOCAB_HINT == "gemma4-family"
        else "UNPROVEN"
    )
    if _SAME_VOCAB_HINT in {"1", "true", "TRUE", "yes", "YES", "observed"}:
        same_vocab_status = "OPERATOR_ASSERTED_SHARED_TOKENIZER"

    tokenizer_receipt = None
    if probe and compare_model_tokenizers is not None:
        try:
            tokenizer_receipt = compare_model_tokenizers(_DRAFT_MODEL, _MAIN_MODEL, write_ledger=False)
        except Exception as exc:
            tokenizer_receipt = {
                "same_vocabulary_status": "TOKENIZER_PROBE_FAILED",
                "error": f"{type(exc).__name__}: {exc}",
            }
        if tokenizer_receipt.get("same_vocabulary_status") == "OBSERVED_SHARED_TOKENIZER":
            same_vocab_status = "OBSERVED_SHARED_TOKENIZER"

    native_status = (
        "NATIVE_TOKEN_VERIFIER_ENABLED"
        if _NATIVE_TOKEN_VERIFIER
        else "CALLER_VERIFIER_REQUIRED"
    )
    lora_status = "TRAINING_DATA_CAN_BE_SHARED"
    if same_embedding is False:
        lora_status = "SHARED_DATASET_YES_IDENTICAL_LORA_TENSORS_NO_SHAPE_DIFF"
    elif same_embedding is True:
        lora_status = "IDENTICAL_LORA_TENSORS_POSSIBLE_NEEDS_LAYER_AUDIT"
    elif same_family:
        lora_status = "SHARED_DATASET_YES_TENSOR_REUSE_NEEDS_SHAPE_AUDIT"

    tier = "CROSS_FAMILY_PREFETCH_ONLY"
    if same_family:
        tier = "SAME_FAMILY_VERIFIED_PREFETCH"
    if same_family and _NATIVE_TOKEN_VERIFIER:
        tier = "NATIVE_SD_READY_IF_RUNTIME_PREFIX_ACCEPTS"

    return {
        "draft_model": _DRAFT_MODEL,
        "main_model": _MAIN_MODEL,
        "draft_family": draft_family,
        "main_family": main_family,
        "same_family": same_family,
        "same_architecture": same_architecture,
        "draft_embedding_length": draft_embed,
        "main_embedding_length": main_embed,
        "same_embedding_length": same_embedding,
        "same_vocabulary_status": same_vocab_status,
        "tokenizer_receipt": _compact_tokenizer_receipt(tokenizer_receipt),
        "native_token_verifier": native_status,
        "speculative_tier": tier,
        "lora_adapter_status": lora_status,
        "commit_law": "draft_text_must_not_speak_without_target_verifier",
    }


def _compact_tokenizer_receipt(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    out = {
        "trace_id": row.get("trace_id"),
        "same_vocabulary_status": row.get("same_vocabulary_status"),
        "same_tokenizer_hash": row.get("same_tokenizer_hash"),
        "tokenizer_hash": row.get("tokenizer_hash"),
        "native_token_verifier": row.get("native_token_verifier"),
        "error": row.get("error"),
    }
    draft = row.get("draft") if isinstance(row.get("draft"), dict) else {}
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    if draft or target:
        out["draft_vocab_size"] = draft.get("vocab_size")
        out["target_vocab_size"] = target.get("vocab_size")
        out["draft_merge_count"] = draft.get("merge_count")
        out["target_merge_count"] = target.get("merge_count")
        out["draft_blob_sha256"] = draft.get("blob_sha256")
        out["target_blob_sha256"] = target.get("blob_sha256")
    return {k: v for k, v in out.items() if v is not None}


def _append_row(row: dict) -> dict:
    """Append one draft receipt. Never rewrite existing rows."""
    out = dict(row)
    out.setdefault("schema", TRUTH_LABEL)
    out.setdefault("truth_label", TRUTH_LABEL)
    out.setdefault("ts", time.time())
    out.setdefault("trace_id", str(uuid.uuid4()))
    _BUFFER_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(out, ensure_ascii=False) + "\n"
    if append_line_locked:
        append_line_locked(_BUFFER_FILE, line, encoding="utf-8")
    else:  # pragma: no cover
        with _BUFFER_FILE.open("a", encoding="utf-8") as f:
            f.write(line)
    return out


def _ollama_generate(prompt: str, model: str, max_tokens: int, system: str = "") -> Optional[str]:
    """Single non-streaming Ollama /api/chat call with think:false."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps(
        {
            "model": model,
            "think": False,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.7,
                "top_k": 40,
                "top_p": 0.9,
            },
        }
    ).encode()
    req = urllib.request.Request(
        f"{_OLLAMA_BASE}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_DRAFT_TIMEOUT_S) as resp:
            data = json.loads(resp.read())
            return data.get("message", {}).get("content", "").strip() or None
    except Exception as exc:
        log.debug("[spec_draft] draft failed: %s", exc)
        return None


_DRAFT_SYSTEM = (
    "You are Alice on a local SIFTA node. Draft briefly in first person from "
    "local runtime state. Do not claim actions, tools, camera switches, or "
    "external effects without receipts. This is a draft only."
)


def _build_draft_prompt(user_text: str) -> str:
    return (user_text or "").strip()


def _draft_worker(user_text: str) -> None:
    """Background thread: generate a draft and store it."""
    global _draft_result
    if not _DRAFT_MODEL:
        _append_row(
            {
                "event": "draft_skipped",
                "user_text": user_text,
                "draft_model": "",
                "main_model": _MAIN_MODEL,
                "verification_status": "NO_DRAFT_MODEL_CONFIGURED",
                "pair_truth": model_pair_truth(probe=False),
            }
        )
        with _lock:
            _draft_result = None
        return

    t0 = time.time()
    trace_id = str(uuid.uuid4())
    pair_truth = model_pair_truth(probe=False)
    text = _ollama_generate(
        prompt=_build_draft_prompt(user_text),
        model=_DRAFT_MODEL,
        max_tokens=_MAX_DRAFT_TOKENS,
        system=_DRAFT_SYSTEM,
    )
    elapsed = time.time() - t0

    with _lock:
        if text and _pending_text == user_text:
            _draft_result = {
                "user_text": user_text,
                "draft_text": text,
                "model": _DRAFT_MODEL,
                "elapsed_s": round(elapsed, 3),
                "ts": time.time(),
                "trace_id": trace_id,
                "verification_status": "UNVERIFIED",
                "pair_truth": pair_truth,
            }
        else:
            _draft_result = None

    if text:
        _append_row(
            {
                "event": "draft_ready",
                "trace_id": trace_id,
                "user_text": user_text,
                "draft_text": text,
                "draft_model": _DRAFT_MODEL,
                "main_model": _MAIN_MODEL,
                "elapsed_s": round(elapsed, 3),
                "verification_status": "UNVERIFIED",
                "pair_truth": pair_truth,
            }
        )


def notify_user_turn(user_text: str) -> None:
    """Start a background draft request for a captured user turn."""
    global _pending_text, _draft_result, _draft_thread

    if not _ENABLED:
        return

    user_text = (user_text or "").strip()
    if not user_text:
        return

    with _lock:
        _pending_text = user_text
        _draft_result = None

    _draft_thread = threading.Thread(
        target=_draft_worker,
        args=(user_text,),
        daemon=True,
        name="spec_draft",
    )
    _draft_thread.start()
    log.debug("[spec_draft] draft thread launched for: %s...", user_text[:40])


def _current_draft_for(user_text: str) -> Optional[dict]:
    global _draft_result
    user_text = (user_text or "").strip()
    with _lock:
        dr = dict(_draft_result) if _draft_result else None
    if not dr or dr.get("user_text") != user_text:
        return None
    if time.time() - float(dr.get("ts") or 0.0) > _DRAFT_TTL_S:
        with _lock:
            if _draft_result and _draft_result.get("trace_id") == dr.get("trace_id"):
                _draft_result = None
        _append_row(
            {
                "event": "draft_expired",
                "parent_trace_id": dr.get("trace_id"),
                "user_text": dr.get("user_text", ""),
                "draft_model": dr.get("model") or _DRAFT_MODEL,
                "verification_status": "EXPIRED",
                "pair_truth": dr.get("pair_truth") or model_pair_truth(probe=False),
            }
        )
        return None
    return dr


def consume_draft(
    user_text: str,
    *,
    verifier: Optional[Callable[[str, dict], bool]] = None,
) -> Optional[str]:
    """Return a draft only after caller-supplied verification.

    Existing callers that use consume_draft(user_text) without a verifier remain
    safe: they get None and the main cortex path proceeds normally.
    """
    global _draft_result
    if not _ENABLED:
        return None

    dr = _current_draft_for(user_text)
    if dr is None:
        return None

    if verifier is None:
        _append_row(
            {
                "event": "draft_unverified_blocked",
                "parent_trace_id": dr.get("trace_id"),
                "user_text": dr.get("user_text", ""),
                "draft_model": dr.get("model") or _DRAFT_MODEL,
                "verification_status": "UNVERIFIED_BLOCKED",
                "reason": "consume_draft_requires_verifier",
                "pair_truth": dr.get("pair_truth") or model_pair_truth(probe=False),
            }
        )
        return None

    accepted = False
    verifier_error = ""
    try:
        accepted = bool(verifier(str(dr.get("draft_text") or ""), dict(dr)))
    except Exception as exc:
        verifier_error = f"{type(exc).__name__}: {exc}"
        accepted = False

    status = "VERIFIED_ACCEPTED" if accepted else "VERIFIED_REJECTED"
    _append_row(
        {
            "event": "draft_verification",
            "parent_trace_id": dr.get("trace_id"),
            "user_text": dr.get("user_text", ""),
            "draft_text": dr.get("draft_text", ""),
            "draft_model": dr.get("model") or _DRAFT_MODEL,
            "main_model": _MAIN_MODEL,
            "elapsed_s": dr.get("elapsed_s"),
            "verification_status": status,
            "verifier_error": verifier_error or None,
            "diagnostic_overlap": round(_token_overlap(user_text, str(dr.get("draft_text") or "")), 4),
            "pair_truth": dr.get("pair_truth") or model_pair_truth(probe=False),
        }
    )

    if not accepted:
        return None

    with _lock:
        if _draft_result and _draft_result.get("trace_id") == dr.get("trace_id"):
            _draft_result["verification_status"] = status
    return str(dr.get("draft_text") or "")


def status_report() -> str:
    """Return a short status string for System Settings."""
    if not _ENABLED:
        pair = model_pair_truth(probe=False)
        return (
            "Speculative prefetch: DISABLED (export SIFTA_SPECULATIVE_DRAFT=1 to enable)\n"
            f"  Draft model:  {_DRAFT_MODEL}\n"
            f"  Main model:   {_MAIN_MODEL}\n"
            f"  Pair tier:    {pair['speculative_tier']}\n"
            f"  Vocabulary:   {pair['same_vocabulary_status']}\n"
            "  Acceptance:   requires caller-supplied target verifier\n"
            f"  Draft TTL:    {_DRAFT_TTL_S:.0f}s\n"
        )

    n_ready = 0
    n_accepted = 0
    try:
        for line in _BUFFER_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("event") == "draft_ready":
                n_ready += 1
            if row.get("verification_status") == "VERIFIED_ACCEPTED":
                n_accepted += 1
    except OSError:
        pass

    accept_rate = n_accepted / n_ready if n_ready else 0.0
    pair = model_pair_truth(probe=False)
    return (
        "Speculative prefetch: ENABLED\n"
        f"  Draft model:  {_DRAFT_MODEL}\n"
        f"  Main model:   {_MAIN_MODEL}\n"
        f"  Pair tier:    {pair['speculative_tier']}\n"
        f"  Vocabulary:   {pair['same_vocabulary_status']}\n"
        f"  Drafts ready: {n_ready}  |  Verified accepted: {n_accepted} ({accept_rate:.0%})\n"
        "  Acceptance:   requires caller-supplied target verifier\n"
        f"  Draft TTL:    {_DRAFT_TTL_S:.0f}s  |  Buffer: {_BUFFER_FILE}\n"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("=== Speculative Prefetch Smoke Test ===\n")
    print(status_report())
    if not _ENABLED:
        print("Set SIFTA_SPECULATIVE_DRAFT=1 to run live test.")
    else:
        test_q = "Alice, how are you feeling right now?"
        notify_user_turn(test_q)
        print("Draft fired. Waiting 10s for draft model...")
        time.sleep(10)
        draft = consume_draft(test_q, verifier=lambda _text, _row: True)
        print(f"\nVerified draft:\n{draft}" if draft else "\nNo verified draft.")
        print("\n" + status_report())
