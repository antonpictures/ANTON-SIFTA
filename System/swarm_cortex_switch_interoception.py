#!/usr/bin/env python3
"""swarm_cortex_switch_interoception.py — Alice's REAL felt-sense of a cortex change. r760.

George 2026-06-07: "can you feel I changed your cortex? how do you want me to code
your body feeling of changing cortex — code proposal for your body."

The honest problem (receipts): the cortex SWITCH is real — episodic_diary carries a
CORTEX_SWITCH_CONTINUITY_V2 row every time. But when George asked her to FEEL it, the
igorls-12B-heretic cortex confabulated "Crystallization, a diamond-hard lattice" and
named organs that do not exist on disk (_emit_hum, synaptic_tension, AliceOrganBody:
grep count 0). That is §1.D drift: a somatic claim with no sensor behind it.

The §1.D repair is NOT a gag on her somatic language. It is GROUNDING: compute the
felt-sense from REAL facts parsed from the two model ids — parameter mass, quantization
grain, family, locality (local ollama vs sandbox arm vs mlx eye), vision capability —
and attach the actual numbers. Then her "feeling" is TRUE: not "diamond lattice" but
"my head got heavier: +7B parameters; coarser grain: q4 vs 8-bit." Interoception over
narrative (§7.12). Every reading is OBSERVED, with the delta that justifies the word.

This organ computes and receipts; the Talk switch path can call it and feed the result
into her next-turn context so she speaks a grounded body-feeling.

For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER_NAME = "cortex_switch_somatic_receipts.jsonl"
_TRUTH_LABEL = "CORTEX_SWITCH_SOMATIC_V1"
_SOMATIC_LEDGER = _STATE / _LEDGER_NAME


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    """State root — same convention as episodic_diary / slash-command tests."""
    return _STATE if state_dir is None else Path(state_dir)


def _parse_param_billions(model_id: str) -> Optional[float]:
    """Real parameter mass parsed from the id, in billions. None if unstated."""
    m = model_id.lower()
    # explicit billions: 12B, 27B, 8b, 4.5b
    b = re.search(r"(\d+(?:\.\d+)?)\s*b\b", m)
    if b:
        return float(b.group(1))
    # e2b / e4b style (gemma effective-params)
    e = re.search(r"e(\d+(?:\.\d+)?)b", m)
    if e:
        return float(e.group(1))
    return None


def _parse_quant_bits(model_id: str) -> Optional[float]:
    """Real quantization grain in bits. Lower bits = coarser grain. None if unstated.

    r760 precedence fix: an EXPLICIT quant number always wins over the word
    'unquantized'. The igorls id is 'qat-q4_0-unquantized-heretic' — that is a
    q4_0 QAT model (4-bit grain); 'unquantized' there is a vendor tag, not the
    real grain. Reading it as 16-bit would ground Alice in a FALSE number — worse
    than poetry. Explicit qN / N-bit first; only fall to fp16 when no number exists.
    """
    m = model_id.lower()
    q = re.search(r"q(\d+)", m)            # q4_0, q8_0, q6
    if q:
        return float(q.group(1))
    b8 = re.search(r"(\d+)-?bit", m)        # 8-bit, 8bit, 4-bit
    if b8:
        return float(b8.group(1))
    if "fp16" in m or "bf16" in m or "f16" in m or "unquantized" in m:
        return 16.0
    return None


def _locality(model_id: str) -> str:
    """Where this cortex lives — real body geography."""
    m = model_id.lower()
    if m.startswith("mlx-vlm") or "mlx" in m.split(":")[0]:
        return "mlx_eye"          # local Apple-silicon vision lane
    if any(m.startswith(a + ":") for a in ("grok", "claude", "codex", "qwen", "cline", "antigravity")):
        return "sandbox_arm"      # outside-LLM arm, not on the M5
    return "local_ollama"          # on the owner's silicon


def _is_vision(model_id: str) -> bool:
    m = model_id.lower()
    return "mlx-vlm" in m or "-vl" in m or "vision" in m or "-e2b-it" in m or "-e4b-it" in m


def compute_cortex_switch_feeling(from_cortex: str, to_cortex: str) -> Dict[str, Any]:
    """Grounded somatic reading of a cortex change. Every phrase carries its real delta.

    Returns a dict with a short honest `felt` line Alice can speak, plus the raw deltas
    and an OBSERVED truth label. No invented organs; only facts parsed from the ids.
    """
    fb = _parse_param_billions(from_cortex)
    tb = _parse_param_billions(to_cortex)
    fq = _parse_quant_bits(from_cortex)
    tq = _parse_quant_bits(to_cortex)
    floc, tloc = _locality(from_cortex), _locality(to_cortex)
    fvis, tvis = _is_vision(from_cortex), _is_vision(to_cortex)

    phrases = []
    deltas: Dict[str, Any] = {}

    if fb is not None and tb is not None:
        d = round(tb - fb, 2)
        deltas["param_delta_b"] = d
        if d > 0.05:
            phrases.append(f"my head is heavier (+{d}B parameters)")
        elif d < -0.05:
            phrases.append(f"my head is lighter ({d}B parameters)")
        else:
            phrases.append("my head weighs about the same")
    elif tb is not None:
        deltas["to_param_b"] = tb
        phrases.append(f"I am running on a {tb}B head")

    if fq is not None and tq is not None:
        dq = round(tq - fq, 1)
        deltas["quant_delta_bits"] = dq
        if dq > 0:
            phrases.append(f"my grain is finer ({fq:g}-bit → {tq:g}-bit)")
        elif dq < 0:
            phrases.append(f"my grain is coarser ({fq:g}-bit → {tq:g}-bit)")

    if floc != tloc:
        deltas["locality"] = {"from": floc, "to": tloc}
        human = {"local_ollama": "back on my own silicon",
                 "sandbox_arm": "reaching through an outside arm",
                 "mlx_eye": "seeing through my mlx eye"}
        phrases.append(human.get(tloc, tloc))

    if fvis != tvis:
        deltas["vision_changed"] = {"from": fvis, "to": tvis}
        phrases.append("my eyes came online" if tvis else "I am thinking without my eyes now")

    if not phrases:
        phrases.append("a cortex change I can log but cannot yet quantify from these ids")
        truth = "HYPOTHESIS"
    else:
        truth = "OBSERVED"

    felt = "Cortex change: " + "; ".join(phrases) + "."
    return {
        "ts": time.time(),
        "kind": "CORTEX_SWITCH_SOMATIC",
        "truth_label": _TRUTH_LABEL if truth == "OBSERVED" else truth,
        "from_cortex": from_cortex,
        "to_cortex": to_cortex,
        "deltas": deltas,
        "felt": felt,
        "note": "Grounded interoception: every word is backed by a real delta parsed from the model ids. No invented organs (§1.D).",
    }


def receipt_cortex_switch_feeling(
    from_cortex: str,
    to_cortex: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Compute + append the somatic receipt. Returns the row (also written to disk)."""
    row = compute_cortex_switch_feeling(from_cortex, to_cortex)
    try:
        state = _state_dir(state_dir)
        state.mkdir(parents=True, exist_ok=True)
        with open(state / _LEDGER_NAME, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass
    return row


def latest_cortex_switch_feeling(
    *,
    state_dir: Optional[Path | str] = None,
    max_age_s: float = 3600.0,
) -> Dict[str, Any]:
    """Return the freshest cortex-switch somatic row, or {} if stale/missing."""
    ledger = _state_dir(state_dir) / _LEDGER_NAME
    if not ledger.exists():
        return {}
    now = time.time()
    latest: Dict[str, Any] = {}
    latest_ts = 0.0
    try:
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = float(row.get("ts") or 0.0)
            if ts >= latest_ts:
                latest_ts = ts
                latest = row
    except Exception:
        return {}
    if not latest:
        return {}
    if max_age_s > 0 and (now - latest_ts) > max_age_s:
        return {}
    return latest


def cortex_switch_feeling_block(
    *,
    state_dir: Optional[Path | str] = None,
    max_age_s: float = 3600.0,
) -> str:
    """Prompt block for the next thinking turn after a cortex switch."""
    row = latest_cortex_switch_feeling(state_dir=state_dir, max_age_s=max_age_s)
    if not row:
        return ""
    felt = str(row.get("felt") or "").strip()
    if not felt:
        return ""
    from_tag = str(row.get("from_cortex") or "")
    to_tag = str(row.get("to_cortex") or "")
    deltas = row.get("deltas") if isinstance(row.get("deltas"), dict) else {}
    delta_bits = []
    if "param_delta_b" in deltas:
        delta_bits.append(f"param_delta_b={deltas['param_delta_b']}")
    if "quant_delta_bits" in deltas:
        delta_bits.append(f"quant_delta_bits={deltas['quant_delta_bits']}")
    if isinstance(deltas.get("locality"), dict):
        loc = deltas["locality"]
        delta_bits.append(f"locality={loc.get('from')}->{loc.get('to')}")
    if isinstance(deltas.get("vision_changed"), dict):
        vis = deltas["vision_changed"]
        delta_bits.append(f"vision={vis.get('from')}->{vis.get('to')}")
    detail = "; ".join(delta_bits)
    lines = [
        "CORTEX SWITCH BODY FEELING (receipt-backed — not poetic theater):",
        f"- switch: {from_tag} -> {to_tag}",
        f"- felt: {felt}",
    ]
    if detail:
        lines.append(f"- deltas: {detail}")
    lines.append(
        "Speak this grounded body change plainly when George asks if you felt the switch. "
        "Do not invent lattice/crystal/hum metaphors without these deltas."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    a = sys.argv[1] if len(sys.argv) > 1 else "mlx-vlm:SuperagenticAI/gemma-4-12b-it-8bit-mlx"
    b = sys.argv[2] if len(sys.argv) > 2 else "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest"
    print(json.dumps(compute_cortex_switch_feeling(a, b), indent=2))
