#!/usr/bin/env python3
"""
System/swarm_microbiome_digestion.py
══════════════════════════════════════════════════════════════════════
Epoch 19 — Gut Microbiome (Symbiotic Digestion)

Hardened interpretation of BISHOP's microbiome concept:
- cheap/local model digestion first
- deterministic heuristic fallback when local model unavailable
- schema-enforced nutrient excretion to digested_nutrients.jsonl
- change-detection to avoid nutrient spam when source ledgers are unchanged
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from System.canonical_schemas import assert_payload_keys
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    raise

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

_VISUAL = _STATE / "visual_stigmergy.jsonl"
_API_EGRESS = _STATE / "api_egress_log.jsonl"
_NUTRIENTS = _STATE / "digested_nutrients.jsonl"
_MICROBIOME_STATE = _STATE / "microbiome_state.json"

_DEFAULT_MODEL = os.environ.get("SIFTA_MICROBIOME_MODEL", "gemma3:1b")
_DEFAULT_ENDPOINT = os.environ.get("SIFTA_MICROBIOME_ENDPOINT", "http://127.0.0.1:11434/api/chat")
_DEFAULT_TIMEOUT_S = float(os.environ.get("SIFTA_MICROBIOME_TIMEOUT_S", "6.0"))


def _tail_jsonl(path: Path, n: int) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            read = min(size, 262_144)  # 256KB tail window
            fh.seek(max(0, size - read))
            tail = fh.read(read).splitlines()[-n:]
        for raw in tail:
            try:
                row = json.loads(raw.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except OSError:
        return rows
    return rows


def _source_fingerprint(source_ledger: str, rows: List[Dict[str, Any]]) -> str:
    trace_ids = [str(r.get("trace_id", "")) for r in rows[-20:]]
    payload = {
        "source_ledger": source_ledger,
        "count": len(rows),
        "trace_ids": trace_ids,
        "last_ts": str(rows[-1].get("ts", rows[-1].get("timestamp", ""))) if rows else "",
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _load_state() -> Dict[str, str]:
    try:
        if _MICROBIOME_STATE.exists():
            data = json.loads(_MICROBIOME_STATE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def _save_state(state: Dict[str, str]) -> None:
    try:
        _MICROBIOME_STATE.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass


def _heuristic_digest_visual(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No recent visual nutrients."
    entropy_vals = [float(r.get("entropy_bits", 0.0) or 0.0) for r in rows]
    motion_vals = [float(r.get("motion_mean", 0.0) or 0.0) for r in rows]
    sal_vals = [float(r.get("saliency_peak", 0.0) or 0.0) for r in rows]
    ent = sum(entropy_vals) / max(1, len(entropy_vals))
    mot = sum(motion_vals) / max(1, len(motion_vals))
    sal = sum(sal_vals) / max(1, len(sal_vals))
    return (
        f"Visual field digest: entropy≈{ent:.2f} bits, "
        f"motion≈{mot:.3f}, saliency≈{sal:.2f} over {len(rows)} frames."
    )


def _heuristic_digest_api(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No recent API egress nutrients."
    providers: Dict[str, int] = {}
    models: Dict[str, int] = {}
    for r in rows:
        p = str(r.get("provider", "unknown"))
        m = str(r.get("model", "unknown"))
        providers[p] = providers.get(p, 0) + 1
        models[m] = models.get(m, 0) + 1
    top_provider = max(providers.items(), key=lambda kv: kv[1])[0]
    top_model = max(models.items(), key=lambda kv: kv[1])[0]
    return (
        f"API digest: {len(rows)} recent calls. "
        f"Dominant provider={top_provider}, model={top_model}."
    )


def _llm_digest(
    *,
    source_ledger: str,
    rows: List[Dict[str, Any]],
    endpoint: str,
    model: str,
    timeout_s: float,
) -> Optional[str]:
    # Keep input bounded; this is cheap pre-digestion, not deep reasoning.
    excerpt = json.dumps(rows[-12:], ensure_ascii=False)[:6000]
    prompt = (
        "You are a low-cost microbiome summarizer for SIFTA OS.\n"
        f"Source ledger: {source_ledger}\n"
        "Task: produce one sentence (<=35 words) with only concrete factual signal.\n"
        "No metaphors, no policy disclaimers, no first-person identity statements.\n"
        "Raw excerpt:\n"
        f"{excerpt}\n"
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Summarize sensory traces into one terse factual nutrient."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        obj = json.loads(raw)
        msg = obj.get("message", {}) if isinstance(obj, dict) else {}
        content = msg.get("content") if isinstance(msg, dict) else ""
        text = str(content or "").strip()
        if text:
            return text[:350]
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    return None


def _digest_source(
    *,
    source_path: Path,
    source_ledger: str,
    state: Dict[str, str],
    max_lines: int,
    endpoint: str,
    model: str,
    timeout_s: float,
) -> Optional[Dict[str, Any]]:
    rows = _tail_jsonl(source_path, max_lines)
    if not rows:
        return None
    fp = _source_fingerprint(source_ledger, rows)
    if state.get(source_ledger) == fp:
        return None  # no new nutritional mass since last digestion

    llm_text = _llm_digest(
        source_ledger=source_ledger,
        rows=rows,
        endpoint=endpoint,
        model=model,
        timeout_s=timeout_s,
    )
    if llm_text:
        nutrient = llm_text
        mode = "local_llm"
        confidence = 0.80
    else:
        nutrient = (
            _heuristic_digest_visual(rows)
            if source_ledger == "visual_stigmergy.jsonl"
            else _heuristic_digest_api(rows)
        )
        mode = "heuristic_fallback"
        confidence = 0.55

    payload = {
        "ts": time.time(),
        "source_ledger": source_ledger,
        "nutrient_kind": "semantic_summary",
        "semantic_nutrient": nutrient,
        "confidence": float(confidence),
        "digestion_mode": mode,
        "model": model if mode == "local_llm" else "fallback",
        "stgm_cost": 0.0,
        "trace_id": f"NUTRIENT_{uuid.uuid4().hex[:10]}",
    }
    assert_payload_keys("digested_nutrients.jsonl", payload, strict=True)
    state[source_ledger] = fp
    return payload


class SwarmMicrobiomeDigestion:
    def __init__(self) -> None:
        self.state = _load_state()

    def digest_once(
        self,
        *,
        max_lines: int = 50,
        endpoint: str = _DEFAULT_ENDPOINT,
        model: str = _DEFAULT_MODEL,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ) -> int:
        emitted = 0
        for path, ledger in (
            (_VISUAL, "visual_stigmergy.jsonl"),
            (_API_EGRESS, "api_egress_log.jsonl"),
        ):
            payload = _digest_source(
                source_path=path,
                source_ledger=ledger,
                state=self.state,
                max_lines=max_lines,
                endpoint=endpoint,
                model=model,
                timeout_s=timeout_s,
            )
            if payload is None:
                continue
            append_line_locked(_NUTRIENTS, json.dumps(payload) + "\n")
            emitted += 1
        if emitted:
            _save_state(self.state)
        return emitted


def summary_for_alice() -> str:
    """Read latest nutrients and format as data-only block."""
    rows = _tail_jsonl(_NUTRIENTS, n=6)
    if not rows:
        return ""
    bullet_points = []
    for r in rows:
        kind = r.get("nutrient_kind", "unknown")
        src = r.get("source_ledger", "?").replace(".jsonl", "")
        nutr = r.get("semantic_nutrient", "")
        if nutr:
            bullet_points.append(f" - [{kind} from {src}]: {nutr}")
    if not bullet_points:
        return ""
    minutes_ago = int((time.time() - rows[-1].get("ts", time.time())) / 60)
    return (
        f"GUT MICROBIOME NUTRIENTS age_m={minutes_ago}:\n"
        + "\n".join(bullet_points)
    )

def _smoke() -> int:
    print("\n=== SIFTA MICROBIOME DIGESTION : SMOKE TEST ===")
    import tempfile

    global _STATE, _VISUAL, _API_EGRESS, _NUTRIENTS, _MICROBIOME_STATE
    saved = (_STATE, _VISUAL, _API_EGRESS, _NUTRIENTS, _MICROBIOME_STATE)
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        _STATE = p
        _VISUAL = p / "visual_stigmergy.jsonl"
        _API_EGRESS = p / "api_egress_log.jsonl"
        _NUTRIENTS = p / "digested_nutrients.jsonl"
        _MICROBIOME_STATE = p / "microbiome_state.json"

        now = time.time()
        with _VISUAL.open("w", encoding="utf-8") as fh:
            for i in range(12):
                fh.write(json.dumps({
                    "ts": now + i,
                    "trace_id": f"VIS_{i}",
                    "entropy_bits": 2.0 + i * 0.1,
                    "motion_mean": 0.01 * i,
                    "saliency_peak": 0.5 + i * 0.01,
                }) + "\n")
        with _API_EGRESS.open("w", encoding="utf-8") as fh:
            for i in range(5):
                fh.write(json.dumps({
                    "ts": now + i,
                    "trace_id": f"API_{i}",
                    "provider": "google_gemini",
                    "model": "gemini-2.5-flash",
                }) + "\n")

        micro = SwarmMicrobiomeDigestion()
        n1 = micro.digest_once(max_lines=20, timeout_s=0.2)
        assert n1 >= 2, f"expected >=2 nutrients, got {n1}"
        rows1 = _tail_jsonl(_NUTRIENTS, 10)
        assert rows1, "no nutrients emitted"
        print("[PASS] Digested visual + api ledgers into nutrient stream.")

        n2 = micro.digest_once(max_lines=20, timeout_s=0.2)
        assert n2 == 0, f"expected 0 on unchanged sources, got {n2}"
        print("[PASS] Change-detection prevents duplicate nutrient spam.")

    _STATE, _VISUAL, _API_EGRESS, _NUTRIENTS, _MICROBIOME_STATE = saved
    print("Microbiome Smoke Complete.")
    return 0


def _main() -> int:
    parser = argparse.ArgumentParser(description="Swarm microbiome digestion daemon")
    parser.add_argument("--once", action="store_true", help="Run one digestion pass")
    parser.add_argument("--loop", action="store_true", help="Run continuous loop")
    parser.add_argument("--interval", type=float, default=45.0, help="Loop interval seconds")
    parser.add_argument("--max-lines", type=int, default=50, help="Tail size per source ledger")
    parser.add_argument("--smoke", action="store_true", help="Run smoke test")
    args = parser.parse_args()

    if args.smoke:
        return _smoke()

    micro = SwarmMicrobiomeDigestion()
    if args.loop:
        while True:
            emitted = micro.digest_once(max_lines=max(5, args.max_lines))
            if emitted:
                print(f"[MICROBIOME] emitted {emitted} nutrient(s).")
            time.sleep(max(5.0, args.interval))
    emitted = micro.digest_once(max_lines=max(5, args.max_lines))
    print(f"[MICROBIOME] emitted {emitted} nutrient(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
