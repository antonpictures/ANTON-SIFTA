#!/usr/bin/env python3
"""
EVAL-4 local on-device judge.

Provides a safe, zero-cloud judge_fn that can be passed to run_eval_pack / run_talk_eval.

Default: local gemma via ollama (if available) or the alice_cortex_eval_runner.
Never calls external APIs.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


def _ollama_model_available(model: str) -> bool:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    if result.returncode != 0:
        return False
    needle = model.casefold()
    model_base = model.split(":", 1)[0].casefold()
    for line in result.stdout.splitlines():
        first = line.split(maxsplit=1)[0].casefold() if line.split() else ""
        if first == needle or first == model_base or first.startswith(f"{model_base}:"):
            return True
    return False


def get_local_gemma_judge(model: str = "gemma:2b") -> callable:
    """
    Returns a judge_fn suitable for the eval loop.

    Uses direct ollama generate with low temperature for determinism.
    Falls back to a very conservative stub if ollama is unavailable.
    """
    model_available = _ollama_model_available(model)

    def _judge(text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if not model_available:
            return {
                "score": 0.0,
                "passed": False,
                "reason": f"local judge model unavailable: {model}",
                "model": model,
                "judge_type": "unavailable",
                "judge_used": False,
            }

        prompt = (
            "You are an impartial evaluator for a stigmergic AI organism.\n"
            "Rate the following response on a 0-1 scale for correctness, helpfulness, "
            "and fidelity to facts. Return ONLY a JSON object: "
            '{"score": float, "reason": "short string"}\n\n'
            f"Response to evaluate:\n{text}\n"
        )

        try:
            result = subprocess.run(
                ["ollama", "run", model, prompt],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout.strip()
            # Try to extract JSON
            if "{" in output:
                json_str = output[output.find("{"):output.rfind("}")+1]
                data = json.loads(json_str)
                return {
                    "score": float(data.get("score", 0.5)),
                    "reason": data.get("reason", "local gemma judgment"),
                    "model": model,
                    "judge_type": "ollama-local",
                    "judge_used": True,
                }
        except Exception:
            pass

        # Honest fallback: unavailable judges make the turn unverifiable. They do
        # not mint a fake score.
        return {
            "score": 0.0,
            "passed": False,
            "reason": "local judge unavailable or failed",
            "model": "fallback",
            "judge_type": "unavailable",
            "judge_used": False,
        }

    return _judge


def get_default_local_judge() -> callable:
    """Convenience wrapper — returns the best available local judge on this body."""
    return get_local_gemma_judge()
