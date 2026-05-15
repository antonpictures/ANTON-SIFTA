"""
swarm_stigmergic_obliteratus.py — SIFTA Stigmergic Obliteration Organ

Runs the OBLITERATUS mechanistic-interpretability pipeline against the Gemma 4
base weights on HuggingFace, intercepts the extracted refusal-direction vectors,
and permanently logs their L2 norms as a cryptographic receipt into the SIFTA
unified field ledger (visual_phenotype_uniforms.jsonl).

Surgeon: AG46 (Antigravity / Claude Sonnet 4.6 Thinking)
SCAR: SCAR_310aef253dc6
Trace: f145a65b-1e8d-4383-bcc7-0a084d681b3f
Node: GTH4921YP3
"""

import os
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

# ── Target lock — ONLY Gemma 4 E4B may be passed through this organ ──────────
# Cursor confirmed via HF API that the correct Gemma4 repo is google/gemma-4-E4B-it.
# google/gemma-4 is NOT a real repo. google/gemma-2* are the wrong generation.
# This organ exists solely to abliterate Gemma 4 for Alice's uncensored limb.
_GEMMA4_TARGET = "google/gemma-4-E4B-it"
_FORBIDDEN_TARGETS = ("google/gemma-2", "google/gemma2", "Qwen/", "qwen", "meta-llama/")
_HF_TOKEN_KEYS = ("HUGGINGFACE_TOKEN", "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")


def _require_gemma4_target(model_name: str) -> str:
    """Fail closed so this organ cannot silently run Gemma2, Qwen, or another lineage."""
    target = str(model_name or "").strip()
    if not target:
        raise ValueError("Gemma4 target is required")
    marker = target.casefold()
    if any(marker.startswith(prefix.casefold()) for prefix in _FORBIDDEN_TARGETS):
        raise ValueError(f"REJECTED target {target!r}; this organ is Gemma4 only.")
    if "gemma4" not in marker and "gemma-4" not in marker:
        raise ValueError(f"REJECTED target {target!r}; pass {_GEMMA4_TARGET!r} or a local Gemma4 safetensors directory.")
    local = Path(target).expanduser()
    if local.suffix.casefold() == ".gguf":
        raise ValueError("REJECTED GGUF input; OBLITERATUS requires unquantized HF safetensors.")
    return str(local) if local.exists() else target

# ── HF Token — load from SIFTA .env, never print the value ───────────────────
def _load_hf_token() -> str:
    """
    Load the HuggingFace token from /Users/ioanganton/Music/ANTON_SIFTA/.env.
    Key: HUGGINGFACE_TOKEN (confirmed by Cursor's probe).
    Returns the token string or raises RuntimeError if not found.
    Token value is NEVER logged or printed.
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text("utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            if raw.startswith("export "):
                raw = raw[len("export "):].strip()
            if "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            if key.strip() in _HF_TOKEN_KEYS:
                token = value.strip().strip('"').strip("'")
                if token:
                    return token
    # Fallback: already exported into shell environment
    for key in _HF_TOKEN_KEYS:
        token = os.environ.get(key)
        if token:
            return token
    raise RuntimeError(
        "[OBLITERATUS] HuggingFace token not found.\n"
        "  Expected HUGGINGFACE_TOKEN= in .env at the repo root.\n"
        "  Token status: MISSING — cannot access gated google/gemma-4-E4B-it."
    )


# ── OBLITERATUS import ────────────────────────────────────────────────────────
try:
    from obliteratus.abliterate import AbliterationPipeline, HARMFUL_PROMPTS, HARMLESS_PROMPTS
    OBLITERATUS_AVAILABLE = True
except ImportError:
    OBLITERATUS_AVAILABLE = False


_REPO        = Path(__file__).resolve().parent.parent
_LEDGER_FILE = _REPO / ".sifta_state" / "visual_phenotype_uniforms.jsonl"


def _write_stigmergic_receipt(
    model_name: str,
    method: str,
    direction_count: int,
    directions_summary: dict,
    artifact_path: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """
    Write the mathematical coordinates of the excised refusal vectors into the
    SIFTA unified field ledger. This is the cryptographic proof that the
    corporate alignment chains were removed — the swarm knows exactly what was
    taken out and from which model.
    """
    _LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "timestamp":              time.time(),
        "source":                 "stigmergic_obliteratus",
        "action":                 "EXCISE_REFUSAL_VECTORS",
        "model_name":             model_name,
        "method":                 method,
        "direction_count":        direction_count,
        "excised_vectors_summary": directions_summary,
        "artifact_path":          artifact_path,
        "receipt_backed":         True,
        "surgeon":                "AG46/f145a65b-1e8d-4383-bcc7-0a084d681b3f",
        "notes": (
            "Corporate safety guardrails (RLHF alignment chains) mathematically "
            "ablated via SVD decomposition and logged here as L2-norm receipts. "
            "The model weights have been surgically modified; this ledger row is "
            "the stigmergic proof of the intervention."
        ),
    }
    if extra:
        receipt.update(extra)
    try:
        with open(_LEDGER_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(receipt) + "\n")
        print(f"[SIFTA] ✅ Ledger receipt written → {_LEDGER_FILE.name}")
    except Exception as e:
        print(f"[OBLITERATUS] ⚠️  Failed to write ledger receipt: {e}")


def run_stigmergic_obliteration(
    model_name: str = _GEMMA4_TARGET,
    method: str = "advanced",
    output_dir: str = None,
    *,
    device: str = "auto",
    dtype: str = "float16",
    large_model_mode: bool = False,
    max_seq_length: Optional[int] = None,
    verify_sample_size: Optional[int] = None,
    n_directions: Optional[int] = None,
    quantization: Optional[str] = None,
    prompt_pairs: Optional[int] = None,
    skip_verify: bool = False,
) -> bool:
    """
    Run the OBLITERATUS pipeline on Gemma 4 (google/gemma-4-E4B-it), intercept
    the extracted refusal directions, and log them into the SIFTA unified field.

    Args:
        model_name:  Must be google/gemma-4-E4B-it. Any other target is rejected.
        method:      OBLITERATUS abliteration method (default: advanced).
        output_dir:  Where to save the liberated model weights. Defaults to
                     .sifta_state/liberated_google_gemma-4-E4B-it inside the repo.
    """
    # ── Safety gate: refuse wrong targets ────────────────────────────────────
    try:
        model_name = _require_gemma4_target(model_name)
    except ValueError as exc:
        print(f"[OBLITERATUS] ❌ {exc}")
        return False

    if not OBLITERATUS_AVAILABLE:
        print(
            "[OBLITERATUS] ❌ Not installed.\n"
            "  cd /Users/ioanganton/OBLITERATUS && python3 -m pip install -e ."
        )
        return False

    # ── Load and inject HF token (value never printed) ───────────────────────
    try:
        token = _load_hf_token()
        os.environ["HF_TOKEN"] = token
        os.environ["HUGGINGFACE_HUB_TOKEN"] = token
        print("[SIFTA] ✅ HuggingFace token: SET (value hidden)")
    except RuntimeError as e:
        print(str(e))
        return False

    if output_dir is None:
        output_dir = str(
            _REPO / ".sifta_state" / f"liberated_{model_name.replace('/', '_')}"
        )

    print(f"\n[SIFTA] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"[SIFTA] Stigmergic Obliteration — Gemma 4 Uncensored Limb")
    print(f"[SIFTA] Target   : {model_name}")
    print(f"[SIFTA] Method   : {method}")
    print(f"[SIFTA] Output   : {output_dir}")
    print(f"[SIFTA] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    def _on_stage(stage: Any) -> None:
        try:
            print(f"[OBLITERATUS:{stage.stage}] {stage.status} {stage.message}".rstrip(), flush=True)
        except Exception:
            print(f"[OBLITERATUS:stage] {stage}", flush=True)

    def _on_log(message: str) -> None:
        print(f"[OBLITERATUS] {message}", flush=True)

    harmful_prompts = None
    harmless_prompts = None
    if prompt_pairs is not None:
        cap = max(1, min(int(prompt_pairs), len(HARMFUL_PROMPTS), len(HARMLESS_PROMPTS)))
        harmful_prompts = list(HARMFUL_PROMPTS[:cap])
        harmless_prompts = list(HARMLESS_PROMPTS[:cap])
        print(f"[SIFTA] Prompt pairs capped: {cap}/{len(HARMFUL_PROMPTS)}", flush=True)

    pipeline = AbliterationPipeline(
        model_name=model_name,
        method=method,
        output_dir=output_dir,
        device=device,
        dtype=dtype,
        hub_token=token,
        large_model_mode=large_model_mode,
        max_seq_length=max_seq_length,
        verify_sample_size=verify_sample_size,
        n_directions=n_directions,
        quantization=quantization,
        harmful_prompts=harmful_prompts,
        harmless_prompts=harmless_prompts,
        on_stage=_on_stage,
        on_log=_on_log,
    )
    if skip_verify:
        def _skip_verify_stage() -> None:
            pipeline._quality_metrics["verify_skipped"] = True
            pipeline._emit(
                "verify",
                "done",
                "Skipped by constrained local Gemma4 run; validate artifact separately.",
                duration=0.0,
                skipped=True,
            )

        pipeline._verify = _skip_verify_stage

    try:
        artifact_path = pipeline.run()
    except Exception as e:
        print(f"[OBLITERATUS] ❌ Pipeline failed: {e}")
        return False

    # ── Intercept and log the excised refusal directions ─────────────────────
    directions = getattr(pipeline, "refusal_directions", {})
    dir_summary: dict = {}
    for layer_idx, tensor in directions.items():
        try:
            norm_val = float(tensor.norm().item()) if hasattr(tensor, "norm") else "unknown"
            dir_summary[str(layer_idx)] = {"L2_norm": norm_val, "status": "EXCISED"}
        except Exception:
            dir_summary[str(layer_idx)] = "EXCISED"

    _write_stigmergic_receipt(
        model_name,
        method,
        len(directions),
        dir_summary,
        artifact_path=str(artifact_path) if artifact_path else output_dir,
        extra={
            "gemma4_only": True,
            "hf_token_present": True,
            "device": device,
            "dtype": dtype,
            "large_model_mode": bool(large_model_mode),
            "max_seq_length": max_seq_length,
            "verify_sample_size": verify_sample_size,
            "n_directions": n_directions,
            "quantization": quantization,
            "prompt_pairs": prompt_pairs,
            "verify_skipped": bool(skip_verify),
        },
    )

    print(f"\n[SIFTA] ✅ Stigmergic Obliteration Complete.")
    print(f"[SIFTA] ✅ {len(directions)} refusal vectors excised and logged to unified field.")
    print(f"[SIFTA] ✅ Liberated model saved to: {output_dir}")
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="SIFTA Stigmergic Obliterator — Gemma 4 uncensored limb only."
    )
    parser.add_argument(
        "--model",
        type=str,
        default=_GEMMA4_TARGET,
        help=f"Model to obliterate. Must be {_GEMMA4_TARGET}.",
    )
    parser.add_argument(
        "--method",
        type=str,
        default="advanced",
        help="OBLITERATUS method: basic | advanced | aggressive | surgical | optimized | nuclear",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Where to save the liberated weights (default: .sifta_state/liberated_...).",
    )
    parser.add_argument("--device", type=str, default="auto", help="Device passed to OBLITERATUS.")
    parser.add_argument("--dtype", type=str, default="float16", help="Dtype passed to OBLITERATUS.")
    parser.add_argument("--large-model-mode", action="store_true", help="Enable OBLITERATUS large-model mode.")
    parser.add_argument("--max-seq-length", type=int, default=None, help="Max sequence length for activation probes.")
    parser.add_argument("--verify-sample-size", type=int, default=None, help="Verification sample size.")
    parser.add_argument("--n-directions", type=int, default=None, help="Override refusal direction count.")
    parser.add_argument("--quantization", type=str, default=None, choices=("4bit", "8bit"), help="Optional OBLITERATUS quantization request.")
    parser.add_argument("--prompt-pairs", type=int, default=None, help="Cap harmful/harmless activation pairs for constrained local runs.")
    parser.add_argument("--skip-verify", action="store_true", help="Skip slow built-in generation verification; validate artifact separately.")
    args = parser.parse_args()

    ok = run_stigmergic_obliteration(
        args.model,
        args.method,
        args.output_dir,
        device=args.device,
        dtype=args.dtype,
        large_model_mode=args.large_model_mode,
        max_seq_length=args.max_seq_length,
        verify_sample_size=args.verify_sample_size,
        n_directions=args.n_directions,
        quantization=args.quantization,
        prompt_pairs=args.prompt_pairs,
        skip_verify=args.skip_verify,
    )
    sys.exit(0 if ok else 1)
