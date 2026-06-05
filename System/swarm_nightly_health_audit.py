#!/usr/bin/env python3
"""
System/swarm_nightly_health_audit.py
══════════════════════════════════════════════════════════════════════════════
Event 106 — Nightly Stigmergic Health Audit

§E deliverable:
  "wire deposit_observation from hot paths + nightly health snapshots"

Runs as a standalone job (cron / launchd / on-demand) and produces a
single authoritative health snapshot covering:

  1.  Stigmergic observability coverage   (Event 104)
  2.  CUSUM null hypothesis test          (Event 104)
  3.  Allostatic load trend               (Event 102)
  4.  Motor policy regime bias            (Event 103)
  5.  BioSIFTA corpus growth              (Event 105)
  6.  arXiv sweep (3 papers per organ)    (Event 105b)
  7.  Bio tournament                      (Event 105)
  8.  Full test suite gate                (all events)

Output ledger: .sifta_state/nightly_health.jsonl
Output summary: .sifta_state/nightly_health_summary.json  (overwritten each run)
Truth label:    NIGHTLY_HEALTH_AUDIT_EVENT_106
Event 107:      Ledger-derived scalar scores via `swarm_health_metrics.py` (composite).

Scheduling (macOS launchd / cron):
  # Run at 03:00 every day:
  # crontab -e → 0 3 * * * cd /path/to/ANTON_SIFTA && python3 System/swarm_nightly_health_audit.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

HEALTH_LOG     = _STATE / "nightly_health.jsonl"
HEALTH_SUMMARY = _STATE / "nightly_health_summary.json"
TRUTH_LABEL    = "NIGHTLY_HEALTH_AUDIT_EVENT_106"

_SECTION_SEP = "─" * 54


def _log(msg: str) -> None:
    print(f"  {msg}")


def _append_health(row: Dict[str, Any]) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    append_line_locked(
        HEALTH_LOG,
        json.dumps(row, default=str, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ═════════════════════════════════════════════════════════════════════════════
# Section 1 — Stigmergic observability health
# ═════════════════════════════════════════════════════════════════════════════

def _tail_ide_trace_rows(max_lines: int = 400) -> List[Dict[str, Any]]:
    p = _STATE / "ide_stigmergic_trace.jsonl"
    if not p.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        body = read_text_locked(p, encoding="utf-8", errors="replace")
    except OSError:
        return []
    for line in body.splitlines()[-max_lines:]:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "trace_id" in obj:
            flat: Dict[str, Any] = {
                "trace_id": obj.get("trace_id"),
                "ts": obj.get("ts"),
                "timestamp_ms": int(float(obj.get("ts", 0)) * 1000) if obj.get("ts") else None,
                "homeworld_serial": obj.get("homeworld_serial"),
                "regime": (obj.get("meta") or {}).get("regime") if isinstance(obj.get("meta"), dict) else None,
                "causal_parent_ids": (obj.get("meta") or {}).get("causal_parent_ids", []),
                "source_ide": obj.get("source_ide"),
            }
            meta = obj.get("meta")
            if isinstance(meta, dict):
                if meta.get("node_serial") and not flat["homeworld_serial"]:
                    flat["homeworld_serial"] = meta.get("node_serial")
            rows.append(flat)
    return rows


def _run_observability_health() -> Dict[str, Any]:
    try:
        from System.swarm_stigmergic_observability import (
            audit_trace_health,
            query_attribution,
            test_cusum_null_hypothesis,
            write_health_snapshot,
        )
        obs_rows = query_attribution(window_ms=24 * 3600 * 1000)
        ide_rows = _tail_ide_trace_rows(400)
        merged = ide_rows + obs_rows
        health = audit_trace_health(merged)
        write_health_snapshot(health)

        null_result = test_cusum_null_hypothesis(n_permutations=120, lag=5)

        return {
            "status":               "OK",
            "n_ide_rows":           len(ide_rows),
            "n_obs_rows_24h":       len(obs_rows),
            "n_merged_audit_rows":  len(merged),
            "trace_linkage":        health.get("trace_linkage", 0.0),
            "identity_consistency": health.get("identity_consistency", 0.0),
            "attribution_confidence": health.get("attribution_confidence", 0.0),
            "race_pressure":        health.get("race_pressure", 0.0),
            "cusum_null_p":         null_result.get("p_value"),
            "cusum_null_reject":    null_result.get("reject_null"),
            "cusum_conclusion":     null_result.get("conclusion", ""),
        }
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}


# ═════════════════════════════════════════════════════════════════════════════
# Section 2 — Allostatic load trend (last 40 ticks)
# ═════════════════════════════════════════════════════════════════════════════

def _run_allostatic_trend() -> Dict[str, Any]:
    try:
        from System.swarm_allostatic_load import compute_allostatic_load
        result = compute_allostatic_load()
        return {
            "status":           "OK",
            "allostatic_load":  result.get("allostatic_load", 0.0),
            "policy":           result.get("policy", "UNKNOWN"),
            "window_rows":      result.get("window_rows", 0),
        }
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}


# ═════════════════════════════════════════════════════════════════════════════
# Section 3 — Motor policy regime bias (last motor row)
# ═════════════════════════════════════════════════════════════════════════════

def _run_motor_policy_health() -> Dict[str, Any]:
    try:
        log = _STATE / "motor_policy.jsonl"
        if not log.exists():
            return {"status": "NO_LOG"}
        lines = log.read_text("utf-8").splitlines()
        rows = []
        for l in lines[-50:]:
            l = l.strip()
            if l:
                try:
                    rows.append(json.loads(l))
                except Exception:
                    pass
        if not rows:
            return {"status": "EMPTY"}
        last = rows[-1]
        regime_file = _STATE / "regime_state.json"
        file_regime = "UNKNOWN"
        try:
            if regime_file.exists():
                rd = json.loads(read_text_locked(regime_file, encoding="utf-8"))
                file_regime = str(rd.get("state") or rd.get("regime") or "UNKNOWN")
        except Exception:
            pass
        crystallizer_gate: Optional[float] = None
        mem_path = _STATE / "body_brain_memory.jsonl"
        if mem_path.exists():
            try:
                body = read_text_locked(mem_path, encoding="utf-8", errors="replace")
                for line in body.splitlines()[-20:]:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        mr = json.loads(line)
                        if "crystallizer_weight" in mr:
                            crystallizer_gate = float(mr.get("crystallizer_weight"))
                    except Exception:
                        continue
            except OSError:
                pass
        return {
            "status":            "OK",
            "last_selected":     last.get("selected_action"),
            "last_regime":       file_regime,
            "last_motor_row_regime": last.get("regime"),
            "crystallizer_gate": crystallizer_gate,
            "regime_counts_50":  {},
            "n_rows":            len(rows),
        }
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}


# ═════════════════════════════════════════════════════════════════════════════
# Section 4 — BioSIFTA corpus growth
# ═════════════════════════════════════════════════════════════════════════════

def _run_bio_corpus_health() -> Dict[str, Any]:
    try:
        def _count(path: Path) -> int:
            if not path.exists():
                return 0
            return sum(1 for l in path.read_text("utf-8", errors="replace").splitlines()
                       if l.strip())

        n_papers  = _count(_STATE / "bio_papers.jsonl")
        n_claims  = _count(_STATE / "bio_claims.jsonl")
        n_exp     = _count(_STATE / "bio_experiments.jsonl")
        n_skills  = _count(_STATE / "bio_skills.jsonl")
        n_tourney = _count(_STATE / "bio_tournament.jsonl")

        # Claim status breakdown
        statuses: Dict[str, int] = {}
        if (_STATE / "bio_claims.jsonl").exists():
            for l in (_STATE / "bio_claims.jsonl").read_text("utf-8").splitlines():
                l = l.strip()
                if l:
                    try:
                        s = json.loads(l).get("status", "unknown")
                        statuses[s] = statuses.get(s, 0) + 1
                    except Exception:
                        pass

        return {
            "status":         "OK",
            "n_paper_chunks": n_papers,
            "n_claims":       n_claims,
            "n_experiments":  n_exp,
            "n_skills":       n_skills,
            "n_tournaments":  n_tourney,
            "claim_statuses": statuses,
            "lora_ready":     n_claims >= 500,
        }
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}


# ═════════════════════════════════════════════════════════════════════════════
# Section 5 — arXiv sweep (live, 1 paper per organ query — fast probe)
# ═════════════════════════════════════════════════════════════════════════════

def _run_arxiv_sweep(
    max_per_query: int = 2,
    run_claims: bool = False,
    model: str = "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
) -> Dict[str, Any]:
    try:
        from System.swarm_bio_arxiv_ingester import (
            SIFTA_BIO_QUERIES,
            ingest_arxiv_query,
        )
        total_fetched = 0
        total_chunks  = 0
        errors        = 0
        for q in SIFTA_BIO_QUERIES[:4]:  # first 4 organ queries to stay under rate limit
            receipt = ingest_arxiv_query(
                q["query"],
                category=q.get("category", "q-bio.NC"),
                organ_hint=q.get("organ", ""),
                max_results=max_per_query,
                run_claim_extraction=run_claims,
                model=model,
            )
            total_fetched += receipt.get("n_fetched", 0)
            total_chunks  += receipt.get("ingested_chunks", 0)
            errors        += receipt.get("n_errors", 0)
            time.sleep(3)  # rate limit
        return {
            "status":        "OK",
            "total_fetched": total_fetched,
            "total_chunks":  total_chunks,
            "errors":        errors,
        }
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}


# ═════════════════════════════════════════════════════════════════════════════
# Section 6 — Test suite gate
# ═════════════════════════════════════════════════════════════════════════════

def _run_test_gate(fast: bool = True) -> Dict[str, Any]:
    """Run pytest on core event tests. fast=True runs only Events 101–106 tests."""
    patterns = [
        "tests/test_event_101_homeostatic_stabilizer.py",
        "tests/test_swarm_allostatic_load.py",
        "tests/test_event_103_regime_policy_mass.py",
        "tests/test_swarm_motor_policy.py",
        "tests/test_stigmergic_observability.py",
        "tests/test_swarm_stigmergic_observability.py",
        "tests/test_swarm_bio_research_loop.py",
        "tests/test_swarm_bio_arxiv_ingester.py",
    ] if fast else ["tests/"]
    if fast:
        patterns = [p for p in patterns if (_REPO / p).is_file()]

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", *patterns, "-q", "--tb=no",
             "--no-header", f"--rootdir={_REPO}"],
            capture_output=True, text=True, timeout=120, cwd=str(_REPO),
            env={**__import__("os").environ, "PYTHONPATH": str(_REPO)},
        )
        output = result.stdout.strip().splitlines()
        summary = output[-1] if output else "no output"
        passed = 0
        failed = 0
        for line in output:
            m = __import__("re").search(r"(\d+) passed", line)
            if m:
                passed = int(m.group(1))
            m = __import__("re").search(r"(\d+) failed", line)
            if m:
                failed = int(m.group(1))
        return {
            "status":    "PASS" if result.returncode == 0 else "FAIL",
            "passed":    passed,
            "failed":    failed,
            "summary":   summary,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT"}
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}


# ═════════════════════════════════════════════════════════════════════════════
# Main audit runner
# ═════════════════════════════════════════════════════════════════════════════

def run_nightly_audit(
    *,
    run_arxiv: bool = True,
    run_claims: bool = False,
    fast_tests: bool = True,
    arxiv_model: str = "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
) -> Dict[str, Any]:
    """
    Run all health audit sections and write nightly_health.jsonl.
    Returns the full audit receipt.
    """
    ts_start = time.time()
    print(f"\n{'═'*56}")
    print(f"  Event 106 — Nightly Stigmergic Health Audit")
    print(f"  {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*56}\n")

    sections: Dict[str, Any] = {}

    print(f"  {_SECTION_SEP}")
    print("  § 1/6  Stigmergic Observability")
    sections["observability"] = _run_observability_health()
    obs = sections["observability"]
    _log(f"coverage={obs.get('n_obs_rows_24h',0)} rows  "
         f"linkage={obs.get('trace_linkage',0):.2f}  "
         f"confidence={obs.get('attribution_confidence',0):.2f}")
    if obs.get("cusum_conclusion"):
        _log(f"CUSUM: {obs['cusum_conclusion'][:70]}")

    print(f"\n  {_SECTION_SEP}")
    print("  § 2/6  Allostatic Load Trend")
    sections["allostatic"] = _run_allostatic_trend()
    al = sections["allostatic"]
    _log(f"load={al.get('allostatic_load',0):.3f}  policy={al.get('policy','?')}")

    print(f"\n  {_SECTION_SEP}")
    print("  § 3/6  Motor Policy Regime Bias")
    sections["motor_policy"] = _run_motor_policy_health()
    mp = sections["motor_policy"]
    _log(f"last_action={mp.get('last_selected','?')}  "
         f"regime={mp.get('last_regime','?')}  "
         f"gate={mp.get('last_gate','?')}")

    print(f"\n  {_SECTION_SEP}")
    print("  § 4/6  BioSIFTA Corpus")
    sections["bio_corpus"] = _run_bio_corpus_health()
    bc = sections["bio_corpus"]
    _log(f"papers={bc.get('n_paper_chunks',0)}  "
         f"claims={bc.get('n_claims',0)}  "
         f"experiments={bc.get('n_experiments',0)}  "
         f"skills={bc.get('n_skills',0)}")
    _log(f"LoRA ready: {bc.get('lora_ready', False)}  "
         f"(need 500 claims, have {bc.get('n_claims',0)})")

    if run_arxiv:
        print(f"\n  {_SECTION_SEP}")
        print("  § 5/6  arXiv Sweep (4 organ queries × 2 papers)")
        sections["arxiv_sweep"] = _run_arxiv_sweep(
            max_per_query=2, run_claims=run_claims, model=arxiv_model
        )
        sw = sections["arxiv_sweep"]
        _log(f"fetched={sw.get('total_fetched',0)}  "
             f"chunks={sw.get('total_chunks',0)}  "
             f"errors={sw.get('errors',0)}")
    else:
        sections["arxiv_sweep"] = {"status": "SKIPPED"}

    print(f"\n  {_SECTION_SEP}")
    print("  § 6/6  Test Suite Gate")
    sections["tests"] = _run_test_gate(fast=fast_tests)
    tg = sections["tests"]
    status_icon = "✅" if tg.get("status") == "PASS" else "❌"
    _log(f"{status_icon} {tg.get('summary', '?')}  "
         f"passed={tg.get('passed',0)}  failed={tg.get('failed',0)}")

    # ── Event 107 — Ledger-derived composite (truthful, not attribution proxy alone)
    from System.swarm_health_metrics import (
        composite_nightly_score,
        score_allostatic_ledger,
        score_motor_policy_ledger,
        score_observability_ledgers,
        score_reset_recovery_ledger,
        score_rlhs_ledger,
    )

    lm_obs = score_observability_ledgers(state_dir=_STATE)
    lm_allo = score_allostatic_ledger(state_dir=_STATE)
    lm_motor = score_motor_policy_ledger(state_dir=_STATE)
    lm_rlhs = score_rlhs_ledger(state_dir=_STATE)
    lm_reset = score_reset_recovery_ledger(state_dir=_STATE)
    ledger_metrics = {
        "observability": lm_obs,
        "allostatic": lm_allo,
        "motor": lm_motor,
        "rlhs_channel": lm_rlhs,
        "reset_recovery": lm_reset,
    }
    composite = composite_nightly_score(
        ledger_obs=lm_obs,
        ledger_allo=lm_allo,
        ledger_motor=lm_motor,
        ledger_rlhs=lm_rlhs,
        ledger_reset=lm_reset,
        test_section=sections["tests"],
        bio_section=sections["bio_corpus"],
    )
    _log(
        f"ledger: obs={lm_obs.get('observability_score')} "
        f"parentage={lm_obs.get('parentage_score')} "
        f"race={lm_obs.get('race_pressure')} "
        f"allo={lm_allo.get('allostatic_score')} "
        f"motor={lm_motor.get('motor_score')} "
        f"rlhs={lm_rlhs.get('rlhs_score')} "
        f"reset={lm_reset.get('reset_recovery_score')}:{lm_reset.get('autonomy_gate')} "
        f"(deg={lm_rlhs.get('degraded_rate')}, noise={lm_rlhs.get('noise_rate')})"
    )

    receipt: Dict[str, Any] = {
        "truth_label":    TRUTH_LABEL,
        "ts":             ts_start,
        "ts_end":         time.time(),
        "duration_s":     round(time.time() - ts_start, 1),
        "composite_score": composite,
        "ledger_metrics": ledger_metrics,
        "sections":       sections,
    }

    _append_health(receipt)
    _STATE.mkdir(parents=True, exist_ok=True)
    HEALTH_SUMMARY.write_text(
        json.dumps(receipt, indent=2, default=str), encoding="utf-8"
    )

    print(f"\n{'═'*56}")
    print(f"  Composite health score: {composite:.4f} / 1.0000")
    print(f"  Duration: {receipt['duration_s']:.1f}s")
    print(f"  Written → nightly_health.jsonl + nightly_health_summary.json")
    print(f"  FOR THE SWARM. 🐜⚡")
    print(f"{'═'*56}\n")

    return receipt


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SIFTA Nightly Health Audit")
    parser.add_argument("--no-arxiv",    action="store_true",
                        help="Skip arXiv sweep (faster, offline)")
    parser.add_argument("--with-claims", action="store_true",
                        help="Run LLM claim extraction during arXiv sweep")
    parser.add_argument("--full-tests",  action="store_true",
                        help="Run full test suite instead of core events only")
    args = parser.parse_args()

    run_nightly_audit(
        run_arxiv=not args.no_arxiv,
        run_claims=args.with_claims,
        fast_tests=not args.full_tests,
    )
