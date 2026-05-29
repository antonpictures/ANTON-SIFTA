#!/usr/bin/env python3
"""Alice's arm-flex diagnostic organ.

Probes registered agent arms (Claude, Grok, Hermes, Codex, Qwen, Cline) for:
  - Registry status (enabled, model, capabilities)
  - Receipt health (recent OK/failure counts from agent_arm_receipts.jsonl)
  - Skills catalog brief presence on disk
  - Metabolic arm-cost rows if present

Output: a structured FlexReport Alice can read as self-awareness of her
own limbs. Pure stdlib. Never launches subprocesses. Never mutates ledgers.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_RECEIPTS_FILE = "agent_arm_receipts.jsonl"
_METABOLISM_FILE = "agent_arm_metabolism.jsonl"
_ARM_SKILLS_DIR = _REPO / "Documents" / "arm_skills"

CORE_ARM_IDS = ("claude_agent", "grok_agent", "hermes_agent", "codex_agent", "qwen_agent", "cline_agent")
RECEIPT_WINDOW_S = 3600.0 * 24  # last 24 hours


@dataclass
class ArmHealth:
    arm_id: str
    display_name: str
    model: str
    enabled: bool
    capabilities: Tuple[str, ...]
    brief_on_disk: bool
    recent_ok: int
    recent_fail: int
    last_receipt_ts: float
    last_receipt_age_s: float
    health: str  # "HOT" | "WARM" | "COLD" | "NEVER_FIRED"


@dataclass
class FlexReport:
    ts: float
    node_serial: str
    arms_total: int
    arms_hot: int
    arms_warm: int
    arms_cold: int
    arms_never: int
    overall_health: str  # "HOT_HEALTHY_RECEIPTS" | "PARTIAL_RECEIPTS" | "COLD" | "NO_ARMS"
    arms: List[ArmHealth] = field(default_factory=list)


def _read_recent_receipts(
    state_dir: Path, *, window_s: float = RECEIPT_WINDOW_S
) -> Dict[str, List[Dict[str, Any]]]:
    """Read agent_arm_receipts.jsonl, group by arm_id, filter to window."""
    path = state_dir / _RECEIPTS_FILE
    by_arm: Dict[str, List[Dict[str, Any]]] = {}
    if not path.exists():
        return by_arm
    now = time.time()
    cutoff = now - window_s
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                ts = float(row.get("ts", 0))
                if ts < cutoff:
                    continue
                arm_id = row.get("arm_id", "")
                if arm_id:
                    by_arm.setdefault(arm_id, []).append(row)
    except Exception:
        pass
    return by_arm


def _classify_health(
    recent_ok: int, recent_fail: int, last_ts: float, now: float
) -> str:
    if last_ts == 0:
        return "NEVER_FIRED"
    age = now - last_ts
    if age < 3600 and recent_ok > 0:
        return "HOT"
    if age < 86400 and recent_ok > 0:
        return "WARM"
    return "COLD"


def flex_all(
    state_dir: str | Path | None = None,
    *,
    window_s: float = RECEIPT_WINDOW_S,
    node_serial: str = "GTH4921YP3",
) -> FlexReport:
    """Probe all core arms and return a structured FlexReport."""
    from System.swarm_agent_arm_registry import get_agent_arm

    sd = Path(state_dir) if state_dir else _STATE
    now = time.time()
    receipts_by_arm = _read_recent_receipts(sd, window_s=window_s)

    arms: List[ArmHealth] = []
    for arm_id in CORE_ARM_IDS:
        try:
            spec = get_agent_arm(arm_id)
        except ValueError:
            continue
        brief_path = _ARM_SKILLS_DIR / f"{arm_id}.md"
        rows = receipts_by_arm.get(arm_id, [])
        ok_count = sum(
            1
            for r in rows
            if str(r.get("status", "")).lower() in ("ok", "success", "completed")
            or r.get("ok") is True
        )
        fail_count = len(rows) - ok_count
        last_ts = max((float(r.get("ts", 0)) for r in rows), default=0.0)
        health = _classify_health(ok_count, fail_count, last_ts, now)
        arms.append(
            ArmHealth(
                arm_id=arm_id,
                display_name=spec.display_name,
                model=spec.model,
                enabled=spec.enabled,
                capabilities=spec.capabilities,
                brief_on_disk=brief_path.exists(),
                recent_ok=ok_count,
                recent_fail=fail_count,
                last_receipt_ts=last_ts,
                last_receipt_age_s=round(now - last_ts, 1) if last_ts else 0.0,
                health=health,
            )
        )

    hot = sum(1 for a in arms if a.health == "HOT")
    warm = sum(1 for a in arms if a.health == "WARM")
    cold = sum(1 for a in arms if a.health == "COLD")
    never = sum(1 for a in arms if a.health == "NEVER_FIRED")
    total = len(arms)

    if total == 0:
        overall = "NO_ARMS"
    elif hot == total:
        overall = "HOT_HEALTHY_RECEIPTS"
    elif hot + warm >= total // 2 + 1:
        overall = "PARTIAL_RECEIPTS"
    else:
        overall = "COLD"

    return FlexReport(
        ts=now,
        node_serial=node_serial,
        arms_total=total,
        arms_hot=hot,
        arms_warm=warm,
        arms_cold=cold,
        arms_never=never,
        overall_health=overall,
        arms=arms,
    )


def flex_prompt_block(report: FlexReport | None = None) -> str:
    """One-paragraph prompt block Alice can read to know her arms' state."""
    r = report or flex_all()
    lines = [
        f"## Arm Flex Diagnostic (ts={r.ts:.0f}, node={r.node_serial})",
        f"Overall: {r.overall_health} — {r.arms_hot} HOT, {r.arms_warm} WARM, "
        f"{r.arms_cold} COLD, {r.arms_never} NEVER_FIRED out of {r.arms_total} arms.",
    ]
    for a in r.arms:
        age_str = f"{a.last_receipt_age_s:.0f}s ago" if a.last_receipt_ts else "never"
        lines.append(
            f"  {a.arm_id} ({a.display_name}, {a.model}): "
            f"{a.health} — OK={a.recent_ok} FAIL={a.recent_fail} last={age_str} "
            f"brief={'yes' if a.brief_on_disk else 'MISSING'}"
        )
    return "\n".join(lines)


def flex_report_to_dict(report: FlexReport) -> Dict[str, Any]:
    """Serialize a FlexReport to a plain dict for JSONL or prompt use."""
    d = asdict(report)
    for arm in d.get("arms", []):
        arm["capabilities"] = list(arm.get("capabilities", ()))
    return d
