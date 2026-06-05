#!/usr/bin/env python3
"""Shor Playground swimmers for George's pasted Quantum Playground script.

Hardware-up: electricity on the M5 births no-double-spend ASCII swimmers; this
organ gives them one small, receipted quantum-algorithm job over the Shor
factorization script George pasted from Quantum Playground/libquantum style
code.

Truth boundary:
* This is a local classical order-finding/post-processing proxy.
* It does not claim browser VM execution, QPU execution, or cryptographic-scale
  factoring.
* It corrects a concrete body-map error: N=15 is valid for the script guard
  `if N < 15`; a reply saying 15 is invalid is wrong.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import time
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None


REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LEDGER_NAME = "shor_playground_swimmers.jsonl"
TRUTH_LABEL = "SHOR_PLAYGROUND_SWIMMER_V1"

DEFAULT_SHOR_SCRIPT = """// Based on C++ code from libquantum library.
proc FindFactors N
  x = 0
  if N < 15
    Print "Invalid number!"
    Breakpoint
  endif
  width = QMath.getWidth(N)
  twidth = 2 * width + 3
  for x; (QMath.gcd(N, x) > 1) || (x < 2); x
    x = Math.floor(Math.random() * 10000) % N
  endfor
  Print "Random seed: " + x
  for i = 0; i < twidth; i++
    Hadamard i
  endfor
  ExpModN x, N, twidth
  for i = 0; i < width; i++
    MeasureBit twidth + i
  endfor
  InvQFT 0, twidth
  for i = 0; i < twidth / 2; i++
    Swap i, twidth - i - 1
  endfor
  for trycnt = 100; trycnt >= 0; trycnt--
    Measure
  endfor
endproc
VectorSize 16
FindFactors 15
"""


def _ledger_path(state_dir: Path | str | None = None) -> Path:
    state = Path(state_dir) if state_dir is not None else STATE
    state.mkdir(parents=True, exist_ok=True)
    return state / LEDGER_NAME


def _append_jsonl(row: dict[str, Any], *, state_dir: Path | str | None = None) -> None:
    payload = json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n"
    path = _ledger_path(state_dir)
    if append_line_locked:
        append_line_locked(path, payload)
    else:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(payload)


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _width(n: int) -> int:
    return max(1, int(n).bit_length())


def _multiplicative_order(x: int, n: int, *, max_steps: int | None = None) -> int | None:
    if math.gcd(x, n) != 1:
        return None
    limit = max_steps or max(2, n * n)
    acc = 1
    for r in range(1, limit + 1):
        acc = (acc * x) % n
        if acc == 1:
            return r
    return None


def analyze_shor_playground_script(
    *,
    n: int = 15,
    vector_size: int = 16,
    script_text: str = DEFAULT_SHOR_SCRIPT,
) -> dict[str, Any]:
    """Return deterministic facts about the pasted script shape."""
    width = _width(n)
    twidth = 2 * width + 3
    q_phase = 1 << width
    return {
        "truth_label": "SHOR_PLAYGROUND_SCRIPT_ANALYSIS_V1",
        "script_sha256": _sha_text(script_text),
        "n": int(n),
        "vector_size": int(vector_size),
        "width": width,
        "twidth": twidth,
        "q_phase_denominator_from_script": q_phase,
        "guard_expression": "N < 15",
        "passes_guard": bool(n >= 15),
        "n15_is_invalid": False if n == 15 else bool(n < 15),
        "correction": (
            "For FindFactors 15, the script guard N < 15 is false. "
            "A claim that 15 is rejected by that guard is incorrect."
        ),
        "truth_boundary": (
            "Static analysis of George's pasted Quantum Playground script; not "
            "browser execution."
        ),
    }


def _attempt_base(x: int, n: int, width: int) -> dict[str, Any]:
    order = _multiplicative_order(x, n)
    q_phase = 1 << width
    row: dict[str, Any] = {
        "base": int(x),
        "gcd_base_n": math.gcd(x, n),
        "period": order,
        "status": "period_missing",
    }
    if order is None:
        return row
    sample_num = 1 if order > 1 else 0
    measured_c = int(round(q_phase * sample_num / max(1, order)))
    frac = Fraction(measured_c, q_phase).limit_denominator(1 << width)
    row.update(
        {
            "measurement_proxy": {
                "measured_c": measured_c,
                "denominator": q_phase,
                "fraction": f"{frac.numerator}/{frac.denominator}",
            },
            "status": "period_found",
        }
    )
    if order % 2 == 1:
        row["status"] = "odd_period"
        return row
    half_power = pow(x, order // 2, n)
    plus = math.gcd(n, half_power + 1)
    minus = math.gcd(n, half_power - 1)
    factors = sorted({f for f in (plus, minus) if 1 < f < n})
    row.update(
        {
            "half_power_mod_n": half_power,
            "gcd_plus": plus,
            "gcd_minus": minus,
            "factors": factors,
            "status": "success" if factors else "trivial_factor_failure",
        }
    )
    return row


def send_shor_playground_swimmers(
    *,
    n: int = 15,
    vector_size: int = 16,
    max_swimmers: int = 12,
    seed: int = 20260603,
    script_text: str = DEFAULT_SHOR_SCRIPT,
    state_dir: Path | str | None = None,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Send local Shor post-processing swimmers through the pasted script."""
    analysis = analyze_shor_playground_script(
        n=n,
        vector_size=vector_size,
        script_text=script_text,
    )
    trace_id = f"shor_{uuid.uuid4()}"
    bases = [x for x in range(2, max(3, n)) if math.gcd(x, n) == 1]
    rng = random.Random(seed)
    rng.shuffle(bases)
    bases = bases[: max(1, min(max_swimmers, len(bases)))]
    attempts = [_attempt_base(x, n, analysis["width"]) for x in bases]
    factor_set = sorted({f for a in attempts for f in a.get("factors", [])})
    success = False
    if len(factor_set) >= 2:
        success = any(a * b == n for i, a in enumerate(factor_set) for b in factor_set[i + 1 :])
    elif len(factor_set) == 1:
        success = n % factor_set[0] == 0 and 1 < (n // factor_set[0]) < n
    row = {
        "ts": time.time(),
        "trace_id": trace_id,
        "kind": "shor_playground_swimmer_experiment",
        "truth_label": TRUTH_LABEL,
        "algorithm": "Shor order-finding post-processing over Quantum Playground script",
        "input": {"n": int(n), "vector_size": int(vector_size), "max_swimmers": int(max_swimmers)},
        "script_analysis": analysis,
        "data_authenticity": "user_pasted_quantum_playground_script_local_proxy_not_qpu",
        "attempts": attempts,
        "success": success,
        "factors": factor_set,
        "factor_pairs": [[f, n // f] for f in factor_set if f and n % f == 0 and f != n // f],
        "swimmer_count": len(attempts),
        "successful_swimmers": sum(1 for a in attempts if a.get("status") == "success"),
        "stgm_profit_proxy": round(
            sum(1 for a in attempts if a.get("status") == "success") / max(1, len(attempts))
            - sum(1 for a in attempts if "failure" in a.get("status", "")) * 0.05,
            6,
        ),
        "claim_boundary": (
            "This validates Shor-style period/factor post-processing for N=15 "
            "locally. It is not a browser VM execution, QPU execution, or "
            "cryptographic-scale factoring claim."
        ),
    }
    row["result_hash"] = hashlib.sha256(
        json.dumps({k: v for k, v in row.items() if k != "ts"}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    if write_receipt:
        _append_jsonl(row, state_dir=state_dir)
    return row


def latest_shor_playground_swimmers(*, state_dir: Path | str | None = None) -> dict[str, Any] | None:
    path = _ledger_path(state_dir)
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("kind") == "shor_playground_swimmer_experiment":
            return row
    return None


def format_shor_playground_swimmers(*, state_dir: Path | str | None = None) -> str:
    row = latest_shor_playground_swimmers(state_dir=state_dir)
    if not row:
        row = send_shor_playground_swimmers(state_dir=state_dir, write_receipt=True)
    analysis = row.get("script_analysis", {})
    winners = [a for a in row.get("attempts", []) if a.get("status") == "success"]
    best = winners[0] if winners else {}
    return (
        "Shor Playground swimmers: "
        f"trace={row.get('trace_id')} N={row.get('input', {}).get('n')} "
        f"VectorSize={row.get('input', {}).get('vector_size')} "
        f"guard={analysis.get('guard_expression')} passes_guard={analysis.get('passes_guard')} "
        f"success={row.get('success')} factors={row.get('factors')} "
        f"best_base={best.get('base')} period={best.get('period')} "
        f"truth={row.get('data_authenticity')}; boundary={row.get('claim_boundary')}"
    )


def main() -> None:
    row = send_shor_playground_swimmers()
    print(json.dumps(row, indent=2, sort_keys=True))
    print(format_shor_playground_swimmers())


if __name__ == "__main__":
    main()
