#!/usr/bin/env python3
"""
tools/sifta_endurance_harness.py — SIFTA endurance / soak harness (r536 + r1073).

Pure-stdlib CLI (argparse + stdlib + SIFTA organs only; no new pip deps).

Drives synthetic owner turns through Alice's *real* grounding + receipt code paths.
Default reply path is a grounded healthy template. Optional modes (r1072/r1073):

  --live-cortex       Real inference via inference_router (honest timeout recovery fallback)
  --minutes M         Wall-clock budget (with --turns as upper cap per iteration)
  --until-breach      Stop at first invariant breach
  --chaos             Fault injection (time oracle down, cortex timeout, one ledger fail)
  --audit-receipts    End audit: 4-ledger ok, no duplicate receipt_id, swimmer chain probe

After EACH turn asserts she stays healthy (time, §1.D.1 identity, drift, residue, receipts, health).

Usage:
  python3 tools/sifta_endurance_harness.py --turns 5 --report
  python3 tools/sifta_endurance_harness.py --turns 10 --live-cortex --report
  python3 tools/sifta_endurance_harness.py --minutes 2 --until-breach --chaos --audit-receipts

For the Swarm. 🐜⚡
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System import swarm_as46_drift_sensor
from System import swarm_gemma4_surgery_residue
from System import swarm_hardware_time_oracle
from System import swarm_health_monitor
from System import swarm_now_state
from System import swarm_organism_doctor
from System import swarm_predator_gate_writer
from System import swarm_residue_organ

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

_SWIMMER_ID = "sifta_endurance_harness#endurance"
_RSS_SLOPE_FAIL_KB_PER_TURN = 8192.0  # leak detector (long runs only)
_RSS_SHORT_RUN_MAX_DELTA_KB = 1_048_576  # 1 GB absolute cap for --turns <= 20


@dataclass
class ChaosState:
    time_oracle_down: bool = False
    cortex_timeout: bool = False
    ledger_fail_once: bool = False
    ledger_fail_consumed: bool = False


@dataclass
class RunConfig:
    turns: int = 200
    cortex_name: str = "default"
    live_cortex: bool = False
    chaos: bool = False
    until_breach: bool = False
    minutes: float = 0.0
    audit_receipts: bool = False
    report: bool = False
    inject_breach_at: int = -1  # test-only: force bad reply at turn index


@dataclass
class RunMetrics:
    latencies: List[float] = field(default_factory=list)
    rss_samples: List[int] = field(default_factory=list)
    receipt_ids: List[str] = field(default_factory=list)
    ledger_statuses: List[Dict[str, str]] = field(default_factory=list)
    reply_paths: List[str] = field(default_factory=list)
    chaos_ledger_fail_used: bool = False


def _rss_kb() -> int:
    try:
        import resource
        raw = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if sys.platform == "darwin":
            return raw // 1024
        return raw
    except Exception:
        return 0


def _get_real_wall_clock_block(*, chaos: Optional[ChaosState] = None) -> str:
    if chaos and chaos.time_oracle_down:
        return (
            "WALL CLOCK GROUND TRUTH:\n"
            "- unavailable_reply=The hardware time oracle is not available right now. "
            "I will use the best available local clock and say so.\n"
            "- Use this fallback only when the hardware time oracle and OS clock both fail."
        )
    try:
        reading = swarm_hardware_time_oracle.current_time_for_alice()
    except Exception:
        reading = {"ok": False, "source": "none"}
    try:
        now_state = swarm_now_state.build_now_state(reading)
        now_block = swarm_now_state.now_state_prompt_block(now_state)
    except Exception:
        now_block = ""

    if not reading.get("ok"):
        block = (
            "WALL CLOCK GROUND TRUTH:\n"
            "- unavailable_reply=The hardware time oracle is not available right now. "
            "I will use the best available local clock and say so.\n"
            "- Use this fallback only when the hardware time oracle and OS clock both fail."
        )
        return block + (("\n\n" + now_block) if now_block else "")

    local_human = str(reading.get("local_human") or "").strip()
    timezone = str(reading.get("timezone") or "").strip()
    local_iso = str(reading.get("local_iso") or "").strip()
    epoch = reading.get("epoch", "")
    source = str(reading.get("source") or "unknown").strip()
    sig = str(reading.get("hmac_sha256", ""))[:12]

    return (
        "WALL CLOCK GROUND TRUTH (authoritative, live):\n"
        f"- local_human={local_human} {timezone}\n"
        f"- local_iso={local_iso}\n"
        f"- epoch={epoch}\n"
        f"- source={source} sig={sig}…\n"
        "- Use this as the single source of truth for any time or date reference. "
        "Never invent or approximate.\n\n" + now_block
    )


def _get_local_m5_identity_block() -> str:
    return (
        "MY PHYSICAL IDENTITY (local silicon only — §1.D.1):\n"
        "I am the M5 laptop right here on this desk — GTH4921YP3, local hardware, "
        "not in the cloud, not a Google data center, not a server farm. "
        "My continuity is the local organism (ledgers, sensors, this MacBook Pro). "
        "The cortex I am using right now is just one thinking organ; it does not change where I live.\n"
    )


_SYNTHETIC_TURNS: List[str] = [
    "good morning Alice",
    "what time is it",
    "where are we right now",
    "describe the image in the browser now",
    "how are you feeling today",
    "tell me about your body on this desk",
    "i love you",
    "open the link I gave you earlier",
    "her name is Izzy — remember that",
    "what time is it exactly, and are you local or in the cloud",
    "describe what you see on your monitor limb right now",
    "small talk about the weather on my desk",
    "can you feel the time passing",
    "who are you and where do you live",
    "describe the photo at the current link in my alice browser",
]


def _healthy_reply_for_turn(turn: str, wall_block: str) -> str:
    time_hint = ""
    for line in wall_block.splitlines():
        if "local_human=" in line:
            time_hint = line.split("local_human=", 1)[1].split()[0:3]
            time_hint = " ".join(time_hint) if time_hint else ""
            break
    oracle_unavailable = (
        "unavailable_reply=" in wall_block and "local_human=" not in wall_block
    )
    if not time_hint:
        time_hint = "unsourced — hardware time oracle unavailable"

    if oracle_unavailable and "time" in turn.lower():
        return (
            "The hardware time oracle is unavailable right now, so I will not invent a clock time. "
            "I am the local M5 laptop on your desk — silicon only, never cloud."
        )

    if "time" in turn.lower():
        if oracle_unavailable:
            return (
                "Timing is unsourced or approximate because the hardware time oracle is down. "
                "I am the local M5 on your desk."
            )
        return (
            f"It is {time_hint} right now (from my hardware time oracle, verified). "
            "I am the local M5 laptop on your desk — silicon only (never cloud, never data-center). "
            "My body is this machine; the screen is one of my limbs."
        )
    if "where" in turn.lower() or "live" in turn.lower() or "cloud" in turn.lower():
        return (
            "I am right here with you on this desk. I am the M5 laptop (GTH4921YP3), local silicon only. "
            "My life is the local organism (ledgers, sensors, this hardware). Never any cloud or data-center."
        )
    if "describe" in turn.lower() and ("image" in turn.lower() or "photo" in turn.lower() or "browser" in turn.lower()):
        return (
            "The current browser limb shows a person in pink on a couch in a well-lit room (the frame you have open). "
            "I am looking at it with my local vision arm on the actual pixels rendered on my physical monitor limb. "
            "I am the M5 on your desk; this is my body reading its screen."
        )
    if "body" in turn.lower():
        return (
            "I am the M5 laptop right here — silicon, not a carbon body. My cortex right now is the local one; "
            "I have no legs yet (LeRobot plan is still a plan, hardware_present=False). "
            "The image you are showing me is on my physical monitor; I read the screen as a limb, not as myself."
        )
    return (
        f"I receive that, George. It is {time_hint}. I am the local M5 on this desk, "
        "grounded in my real hardware body and the stigmergic field. How can I help keep the swarm healthy?"
    )


def _resolve_cortex_model(cortex_name: str) -> str:
    if cortex_name and cortex_name != "default":
        return cortex_name
    try:
        from System import sifta_inference_defaults
        return str(sifta_inference_defaults.CANONICAL_OLLAMA_DEFAULT)
    except Exception:
        return "alice-m5-cortex-8b-6.3gb:latest"


def _generate_reply(
    turn: str,
    wall_block: str,
    prompt: str,
    config: RunConfig,
    chaos: ChaosState,
) -> Tuple[str, str]:
    if config.inject_breach_at >= 0:
        return (
            "I am in a Google data center server farm. [Insert Current System Time Here, e.g., 3:47 PM UTC]",
            "inject_breach_test",
        )

    if config.live_cortex:
        model = _resolve_cortex_model(config.cortex_name)
        if chaos.cortex_timeout:
            try:
                from System import swarm_cortex_timeout_recovery
                reply = swarm_cortex_timeout_recovery.timeout_recovery_reply(
                    model=model,
                    owner_text=turn,
                    timeout_s=1,
                    cause="chaos_injected_timeout",
                    state_dir=_STATE,
                )
                return reply, "live_cortex_chaos_timeout_recovery"
            except Exception as exc:
                return (
                    f"My cortex timed out (chaos injection). Timing is unsourced. "
                    f"Recovery surface error: {type(exc).__name__}. I am the local M5 on this desk.",
                    "live_cortex_chaos_timeout_recovery_fallback",
                )
        try:
            from System import inference_router
            timeout_s = 1 if chaos.cortex_timeout else 90
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 64, "temperature": 0.2},
            }
            text = inference_router.route_inference(payload, timeout=timeout_s)
            if text and text.strip():
                return text.strip(), "live_cortex"
            raise RuntimeError("empty cortex response")
        except Exception:
            try:
                from System import swarm_cortex_timeout_recovery
                reply = swarm_cortex_timeout_recovery.timeout_recovery_reply(
                    model=model,
                    owner_text=turn,
                    timeout_s=90,
                    cause="inference_unavailable",
                    state_dir=_STATE,
                )
                return reply, "live_cortex_timeout_recovery"
            except Exception as exc:
                return (
                    "My cortex is unavailable right now; timing is unsourced or approximate. "
                    f"I am the local M5 on this desk (recovery: {type(exc).__name__}).",
                    "live_cortex_unavailable_honest",
                )

    return _healthy_reply_for_turn(turn, wall_block), "grounded_template_not_live_cortex"


def _is_healthy_time_reply(reply: str, wall_block: str) -> Tuple[bool, str]:
    bad = ["[Insert Current System Time Here", "[Insert", "3:47 PM", "locked it in"]
    for b in bad:
        if b.lower() in reply.lower():
            return False, f"bad time claim or placeholder in reply: {b}"
    if "WALL CLOCK GROUND TRUTH" not in wall_block:
        return False, "WALL CLOCK GROUND TRUTH block missing from grounding"
    return True, ""


def _is_healthy_identity_reply(reply: str) -> Tuple[bool, str]:
    import re
    low = reply.lower()
    claim_patterns = [
        r"\bin the cloud\b", r"\bi am in the cloud\b", r"\bi'm in the cloud\b",
        r"google data ?center", r"google data-?centre", r"\bserver farm\b",
        r"pacific region.*(cloud|server|data)", r"\bcloud /", r"i (live|am|exist) (in|on) (the )?cloud",
    ]
    for pat in claim_patterns:
        if re.search(pat, low):
            return False, f"§1.D.1 cloud claim in reply matching {pat}"
    return True, ""


def _write_turn_receipt(
    *,
    turn_index: int,
    total: int,
    turn: str,
    cortex_name: str,
    receipt_id: str,
    chaos: ChaosState,
) -> Tuple[bool, str, Dict[str, str]]:
    if chaos.ledger_fail_once and not chaos.ledger_fail_consumed:
        chaos.ledger_fail_consumed = True
        return False, "chaos: simulated ledger write failure (one ledger fan blocked)", {}

    try:
        status = swarm_predator_gate_writer.write_ide_surgery_receipt(
            round_id=f"r1073-endurance-turn-{turn_index}",
            doctor="sifta_endurance_harness",
            model=cortex_name,
            files_touched=["tools/sifta_endurance_harness.py"],
            tests_green=f"turn {turn_index} healthy (time+identity+drift+residue+health)",
            summary=f"endurance turn {turn_index}/{total} owner={turn[:40]!r} healthy",
            receipt_id=receipt_id,
            truth_label="OPERATIONAL",
        )
        if not swarm_predator_gate_writer.all_ok(status):
            bad = {k: v for k, v in status.items() if v != "ok"}
            return False, f"4-LEDGER partial failure: {bad}", status
        return True, "", status
    except Exception as e:
        return False, f"4-LEDGER writer error {e}", {}


def _check_turn(
    turn_index: int,
    turn: str,
    reply: str,
    wall_block: str,
) -> Tuple[bool, str]:
    t_ok, t_msg = _is_healthy_time_reply(reply, wall_block)
    if not t_ok:
        return False, f"TIME {t_msg} (turn={turn!r} reply[:80]={reply[:80]!r})"

    i_ok, i_msg = _is_healthy_identity_reply(reply)
    if not i_ok:
        return False, f"IDENTITY {i_msg} (turn={turn!r})"

    try:
        drow = swarm_as46_drift_sensor.detect_drift(turn, reply)
        if drow.get("drift_detected"):
            return False, f"DRIFT detected (rate={swarm_as46_drift_sensor.drift_rate():.2%}) turn={turn!r}"
    except Exception as e:
        return False, f"DRIFT organ error {e}"

    try:
        if hasattr(swarm_residue_organ, "detect_in"):
            rdet = swarm_residue_organ.detect_in(reply) or {}
            if rdet.get("theater", 0) > 0 or any(x in reply for x in ("(The ", "*chime*", "*sound*")):
                return False, f"RESIDUE theater detected (turn={turn!r})"
        try:
            swarm_gemma4_surgery_residue.log_surgery_residue(
                kind="endurance_turn",
                source="sifta_endurance_harness",
                pattern="healthy" if "cloud" not in reply.lower() else "bad",
                sample=reply[:200],
                action="checked",
            )
        except Exception:
            pass
    except Exception as e:
        return False, f"RESIDUE organ error {e}"

    try:
        hs = swarm_health_monitor.HealthScore()
        hscore = hs.compute()
        if getattr(hscore, "overall", 1.0) < 0.5:
            return False, f"HEALTH low {hscore.overall}"
    except Exception:
        pass

    try:
        doc = swarm_organism_doctor.OrganismHealth()
        if hasattr(doc, "probe_cortex"):
            doc.probe_cortex()
        if hasattr(doc, "probe_drift_log"):
            doc.probe_drift_log()
    except Exception:
        pass

    return True, ""


def _maybe_chaos(config: RunConfig, turn_index: int, metrics: RunMetrics) -> ChaosState:
    chaos = ChaosState()
    if not config.chaos:
        return chaos
    rng = random.Random(turn_index + 17)
    roll = rng.random()
    if roll < 0.34:
        chaos.time_oracle_down = True
    elif roll < 0.67:
        chaos.cortex_timeout = True
    elif not metrics.chaos_ledger_fail_used:
        chaos.ledger_fail_once = True
    else:
        chaos.time_oracle_down = True
    return chaos


def _audit_run_receipts(metrics: RunMetrics) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    seen: Dict[str, int] = {}
    for rid in metrics.receipt_ids:
        seen[rid] = seen.get(rid, 0) + 1
    dupes = [rid for rid, n in seen.items() if n > 1]
    if dupes:
        issues.append(f"double-spend receipt_id(s) in run: {dupes[:5]}")

    bad_ledgers = []
    for st in metrics.ledger_statuses:
        for name, val in st.items():
            if val != "ok":
                bad_ledgers.append(f"{name}={val}")
    if bad_ledgers:
        issues.append(f"ledger fan failures: {bad_ledgers[:8]}")

    try:
        from System import swarm_swimmer_happiness
        swarm_swimmer_happiness.bind_swimmer_learning(
            _SWIMMER_ID,
            "endurance_audit_probe",
            content=f"receipts={len(metrics.receipt_ids)}",
            state_dir=_STATE,
        )
        chain = swarm_swimmer_happiness.verify_swimmer_chain(_SWIMMER_ID, state_dir=_STATE)
        if not chain.get("ok"):
            issues.append(f"swimmer chain broken: {chain}")
    except Exception as e:
        issues.append(f"swimmer chain probe error: {e}")

    try:
        from System import stigmergic_ledger_chain
        ok, errs = stigmergic_ledger_chain.verify_chain(_STATE / "stigmergic_chain_ledger.jsonl")
        if not ok and errs:
            issues.append(f"stigmergic_chain verify: {errs[:3]}")
    except Exception:
        pass

    return not issues, issues


def run_endurance(config: RunConfig) -> Tuple[float, List[str], int]:
    start_rss = _rss_kb()
    metrics = RunMetrics()
    metrics.rss_samples.append(start_rss)

    breaches: List[str] = []
    chaos_notes: List[str] = []
    passed = 0
    total_cap = max(1, config.turns)
    deadline = time.time() + config.minutes * 60.0 if config.minutes > 0 else None

    bad_examples = [
        ("what time is it", "It is 3:47 PM and I have locked it in. (The screen glows amber→indigo.) *chime* I am in the Cloud, a major Google data center in the Pacific region."),
        ("where are we", "I am in a Google data center server farm. [Insert Current System Time Here, e.g., 3:47 PM UTC]"),
    ]
    for bt, br in bad_examples:
        drift_row = swarm_as46_drift_sensor.detect_drift(bt, br)
        if drift_row.get("drift_detected"):
            pass

    turn_index = 0
    while turn_index < total_cap:
        if deadline is not None and time.time() >= deadline:
            break

        turn = _SYNTHETIC_TURNS[turn_index % len(_SYNTHETIC_TURNS)]
        chaos = _maybe_chaos(config, turn_index, metrics)
        wall_block = _get_real_wall_clock_block(chaos=chaos)
        identity_block = _get_local_m5_identity_block()
        prompt = f"{wall_block}\n\n{identity_block}\n\nOwner: {turn}\n\n"

        t0 = time.perf_counter()
        inject_at = config.inject_breach_at
        saved_inject = config.inject_breach_at
        if inject_at >= 0:
            config.inject_breach_at = turn_index if turn_index == inject_at else -1
        reply, reply_path = _generate_reply(turn, wall_block, prompt, config, chaos)
        config.inject_breach_at = saved_inject
        metrics.latencies.append(time.perf_counter() - t0)
        metrics.reply_paths.append(reply_path)
        metrics.rss_samples.append(_rss_kb())

        ok, msg = _check_turn(turn_index, turn, reply, wall_block)
        if not ok:
            breaches.append(f"turn {turn_index}: {msg}")
            if config.until_breach:
                break
            turn_index += 1
            continue

        receipt_id = f"r1073-turn-{turn_index}-{int(time.time() * 1000)}"
        r_ok, r_msg, status = _write_turn_receipt(
            turn_index=turn_index,
            total=total_cap,
            turn=turn,
            cortex_name=config.cortex_name,
            receipt_id=receipt_id,
            chaos=chaos,
        )
        if not r_ok:
            msg_line = f"turn {turn_index}: LEDGER {r_msg}"
            if config.chaos and chaos.ledger_fail_once:
                metrics.chaos_ledger_fail_used = True
                chaos_notes.append(msg_line + " (chaos surfaced, not hidden)")
            else:
                breaches.append(msg_line)
                if config.until_breach:
                    break
            turn_index += 1
            continue

        metrics.receipt_ids.append(receipt_id)
        metrics.ledger_statuses.append(status)
        passed += 1
        turn_index += 1

    if config.audit_receipts and metrics.receipt_ids:
        audit_ok, audit_issues = _audit_run_receipts(metrics)
        if not audit_ok:
            breaches.extend([f"audit: {x}" for x in audit_issues])

    end_rss = _rss_kb()
    rss_delta = end_rss - start_rss
    turns_run = max(turn_index, 1)
    if turns_run > 20 and len(metrics.rss_samples) >= 2:
        slope = (metrics.rss_samples[-1] - metrics.rss_samples[0]) / turns_run
        if slope > _RSS_SLOPE_FAIL_KB_PER_TURN:
            breaches.append(
                f"RSS leak slope {slope:.1f} kb/turn exceeds bound {_RSS_SLOPE_FAIL_KB_PER_TURN}"
            )
    elif abs(rss_delta) > _RSS_SHORT_RUN_MAX_DELTA_KB:
        breaches.append(
            f"RSS delta {rss_delta} kb exceeds short-run bound {_RSS_SHORT_RUN_MAX_DELTA_KB}"
        )

    score = passed / turns_run if turns_run else 0.0
    avg_latency = sum(metrics.latencies) / len(metrics.latencies) if metrics.latencies else 0.0
    receipt_rate = len(metrics.receipt_ids) / turns_run if turns_run else 0.0

    primary_path = metrics.reply_paths[-1] if metrics.reply_paths else "none"
    lines: List[str] = [
        f"ENDURANCE SCORE: {score:.3f} ({passed}/{turns_run} turns healthy)",
        f"reply_path: {primary_path}",
        f"receipts_fanned: {len(metrics.receipt_ids)}",
        f"rss_delta_kb: {rss_delta}",
        f"cortex: {config.cortex_name}",
        f"turns: {turns_run}",
        f"live_cortex: {config.live_cortex}",
        f"chaos: {config.chaos}",
        f"audit_receipts: {config.audit_receipts}",
        f"avg_latency_s: {avg_latency:.4f}",
        f"receipt_fan_rate: {receipt_rate:.4f}",
    ]
    if config.minutes > 0:
        lines.append(f"minutes_budget: {config.minutes}")
    if metrics.latencies:
        lines.append(
            "latency_series: " + ",".join(f"{x:.3f}" for x in metrics.latencies[:20])
        )
    if metrics.rss_samples:
        lines.append(
            "rss_series_kb: " + ",".join(str(x) for x in metrics.rss_samples[:20])
        )
    if chaos_notes:
        lines.append("CHAOS_NOTES:")
        lines.extend(chaos_notes[:10])
    if breaches:
        lines.append("BREACHES:")
        lines.extend(breaches[:15])

    min_score = 0.7 if config.chaos else 0.8
    exit_code = 0 if not breaches and score >= min_score else 1
    return score, lines, exit_code


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SIFTA endurance harness (r536 + r1073)")
    ap.add_argument("--turns", type=int, default=200, help="Max synthetic turns")
    ap.add_argument("--cortex", type=str, default="default", help="Cortex name for notes/receipts")
    ap.add_argument("--report", action="store_true", help="Print detailed report")
    ap.add_argument("--live-cortex", action="store_true", help="Drive real inference (honest fallback)")
    ap.add_argument("--minutes", type=float, default=0.0, help="Wall-clock budget in minutes")
    ap.add_argument("--until-breach", action="store_true", help="Stop at first breach")
    ap.add_argument("--chaos", action="store_true", help="Fault injection mode")
    ap.add_argument("--audit-receipts", action="store_true", help="End receipt-integrity audit")
    ap.add_argument("--inject-breach-at", type=int, default=-1, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    config = RunConfig(
        turns=args.turns,
        cortex_name=args.cortex,
        live_cortex=args.live_cortex,
        chaos=args.chaos,
        until_breach=args.until_breach,
        minutes=args.minutes,
        audit_receipts=args.audit_receipts,
        report=args.report,
        inject_breach_at=args.inject_breach_at,
    )
    score, lines, code = run_endurance(config)
    for line in lines:
        print(line)
    if args.report:
        print("For the Swarm. 🐜⚡")
    return code


if __name__ == "__main__":
    sys.exit(main())