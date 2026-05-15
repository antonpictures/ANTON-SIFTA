"""SIFTA kernel process table.

This module is the first kernel-discipline layer for the living OS: organs,
agent arms, sensors, repair loops, and UI surfaces register as accountable
processes. It is intentionally pure Python and macOS/PyQt friendly; it does
not introduce Linux service assumptions or detach Alice from the desktop body.
"""

from __future__ import annotations

import json
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional


VALID_RINGS = {0, 1, 2, 3}
DEFAULT_STATE_ROOT = Path(__file__).resolve().parent.parent / ".sifta_state"
DEFAULT_SNAPSHOT_NAME = "kernel_process_table.json"
DEFAULT_LEDGER_NAME = "kernel_process_table.jsonl"
PHYSICAL_GROUNDING_DECAY = 0.15
NEGATIVE_STGM_THRESHOLD = -5.0
NEGATIVE_STGM_HEALTH_PENALTY = 0.2
SEVERE_NEGATIVE_STGM_THRESHOLD = -12.0
NEGATIVE_SPEND_HEALTH_PENALTY = 0.15
SEVERE_NEGATIVE_STGM_HEALTH_PENALTY = 0.25
AMBIENT_DIARY_LEDGER_NAME = "episodic_diary.jsonl"
AMBIENT_DIARY_TRUTH_LABEL = "AMBIENT_WORLD_DIARY_TRACE_V1"
AMBIENT_CONTEXT_MAX_AGE_S = 15 * 60
ACTION_RING_LIMITS = {
    "kernel_maintenance": 0,
    "spend": 1,
    "schedule": 1,
    "effector": 2,
}
SCHEDULER_EFFECTOR_THRESHOLD = 0.0
LOW_SALIENCE_IDLE_PENALTY = 0.05
HIGH_SALIENCE_PRIORITY_BONUS = 0.12


class KernelProcessError(RuntimeError):
    """Base exception for kernel process table failures."""


class KernelRegistrationError(KernelProcessError):
    """Raised when a process registration violates kernel invariants."""


class KernelBudgetError(KernelProcessError):
    """Raised when a heartbeat would violate a process budget."""


@dataclass
class OrganProcess:
    """One accountable SIFTA process.

    Rings:
      0 = kernel / crypto / economy
      1 = core organs
      2 = agent arms and tool routers
      3 = UI / chat / media adapters
    """

    pid: str
    organ_id: str
    ring: int
    health: float
    stgm_balance: float
    current_job: str
    last_receipt_id: str
    failure_count: int
    last_heartbeat_ts: float
    location: str
    bodies_present: List[str]
    metadata: Dict[str, str] = field(default_factory=dict)
    status: str = "alive"

    def normalized(self) -> "OrganProcess":
        pid = str(self.pid or "").strip()
        organ_id = str(self.organ_id or "").strip()
        if not pid:
            raise KernelRegistrationError("pid is required")
        if not organ_id:
            raise KernelRegistrationError("organ_id is required")
        if int(self.ring) not in VALID_RINGS:
            raise KernelRegistrationError(f"invalid ring {self.ring}; expected one of {sorted(VALID_RINGS)}")
        health = max(0.0, min(1.0, float(self.health)))
        metadata = {str(k): str(v) for k, v in dict(self.metadata or {}).items()}
        bodies = [str(x).strip() for x in list(self.bodies_present or []) if str(x).strip()]
        return OrganProcess(
            pid=pid,
            organ_id=organ_id,
            ring=int(self.ring),
            health=health,
            stgm_balance=float(self.stgm_balance),
            current_job=str(self.current_job or "idle"),
            last_receipt_id=str(self.last_receipt_id or ""),
            failure_count=max(0, int(self.failure_count)),
            last_heartbeat_ts=float(self.last_heartbeat_ts or time.time()),
            location=str(self.location or "unknown"),
            bodies_present=bodies,
            metadata=metadata,
            status=str(self.status or "alive"),
        )


class KernelProcessTable:
    """Single accountable view of SIFTA organs and swimmers."""

    def __init__(
        self,
        *,
        state_root: Path | str = DEFAULT_STATE_ROOT,
        snapshot_name: str = DEFAULT_SNAPSHOT_NAME,
        ledger_name: str = DEFAULT_LEDGER_NAME,
        enforce_budget: bool = False,
        load_existing: bool = True,
    ) -> None:
        self.state_root = Path(state_root)
        self.snapshot_path = self.state_root / snapshot_name
        self.ledger_path = self.state_root / ledger_name
        self.enforce_budget = bool(enforce_budget)
        self.boot_ts = time.time()
        self.table: Dict[str, OrganProcess] = {}
        self._lock = RLock()
        if load_existing:
            self._load_snapshot()

    def register(self, process: OrganProcess, *, receipt_id: str = "") -> str:
        """Register or refresh a process, writing an append-only receipt."""
        now = time.time()
        p = process.normalized()
        with self._lock:
            action = "heartbeat_register_existing" if p.pid in self.table else "register"
            if p.pid in self.table:
                old = self.table[p.pid]
                p.last_receipt_id = receipt_id or p.last_receipt_id or old.last_receipt_id
                p.failure_count = max(p.failure_count, old.failure_count)
                p.stgm_balance = old.stgm_balance
                p.status = old.status if old.status != "terminated" else "alive"
            p.last_heartbeat_ts = now
            self.table[p.pid] = p
            self._append_receipt(action, p, receipt_id=receipt_id)
            self._write_snapshot()
            return p.pid

    def ensure_registered(self, process: OrganProcess, *, receipt_id: str = "") -> OrganProcess:
        """Register a process if missing, otherwise refresh identity fields only.

        This is the low-friction ABI for organs and arms. Repeated init paths
        must not reset STGM balance, health, or failure history.
        """
        p = process.normalized()
        with self._lock:
            if p.pid not in self.table:
                self.register(p, receipt_id=receipt_id)
                return self.table[p.pid]
            current = self.table[p.pid]
            current.organ_id = p.organ_id
            current.ring = p.ring
            current.location = p.location or current.location
            current.bodies_present = p.bodies_present or current.bodies_present
            current.metadata.update(p.metadata)
            if p.current_job and p.current_job != "idle":
                current.current_job = p.current_job
            if receipt_id:
                current.last_receipt_id = receipt_id
            current.status = "alive"
            current.last_heartbeat_ts = time.time()
            self._append_receipt("ensure_registered", current, receipt_id=receipt_id)
            self._write_snapshot()
            return current

    def heartbeat(
        self,
        pid: str,
        *,
        health: Optional[float] = None,
        stgm_delta: float = 0.0,
        current_job: Optional[str] = None,
        location: Optional[str] = None,
        bodies_present: Optional[Iterable[str]] = None,
        receipt_id: str = "",
        failure_delta: int = 0,
        metadata: Optional[Dict[str, str]] = None,
    ) -> OrganProcess:
        """Update liveness, budget, and physical grounding for a process."""
        now = time.time()
        with self._lock:
            if pid not in self.table:
                raise KernelRegistrationError(f"unregistered process {pid}")
            proc = self.table[pid]
            action = ""
            if metadata:
                action = str(metadata.get("kernel_action") or metadata.get("action") or "")
            if action:
                self._check_ring(pid, action)
            physical = latest_physical_context(self.state_root)
            used_physical_context = False
            if location is None and physical.get("location"):
                location = str(physical["location"])
                used_physical_context = True
            if bodies_present is None and physical.get("bodies_present"):
                bodies_present = list(physical["bodies_present"])
                used_physical_context = True
            next_balance = proc.stgm_balance + float(stgm_delta)
            if self.enforce_budget and next_balance < 0.0:
                raise KernelBudgetError(f"process {pid} cannot spend STGM below zero")
            if health is not None:
                proc.health = max(0.0, min(1.0, float(health)))
            proc.stgm_balance = next_balance
            if current_job is not None:
                proc.current_job = str(current_job)
            if location is not None:
                proc.location = str(location or "unknown")
            if bodies_present is not None:
                proc.bodies_present = [str(x).strip() for x in bodies_present if str(x).strip()]
            if receipt_id:
                proc.last_receipt_id = receipt_id
            if failure_delta:
                proc.failure_count = max(0, proc.failure_count + int(failure_delta))
            if metadata:
                proc.metadata.update({str(k): str(v) for k, v in metadata.items()})
            if physical.get("source"):
                proc.metadata.setdefault("physical_context_source", str(physical["source"]))
            if physical.get("last_physical_event_ts") is not None:
                proc.metadata["last_physical_event_ts"] = str(physical["last_physical_event_ts"])
            physical_grounded = bool(proc.location and proc.location != "unknown" and proc.bodies_present)
            if used_physical_context:
                proc.metadata["physical_grounding_status"] = "fresh_context"
            elif location is not None or bodies_present is not None:
                proc.metadata["physical_grounding_status"] = "explicit_heartbeat"
            elif not physical_grounded:
                proc.health = max(0.0, round(proc.health - PHYSICAL_GROUNDING_DECAY, 4))
                proc.failure_count += 1
                proc.metadata["physical_grounding_status"] = "missing_decay"
                proc.metadata["physical_grounding_penalty"] = str(PHYSICAL_GROUNDING_DECAY)
            else:
                proc.metadata.setdefault("physical_grounding_status", "carried_forward")
            if proc.stgm_balance < NEGATIVE_STGM_THRESHOLD:
                proc.health = max(0.0, round(proc.health - NEGATIVE_STGM_HEALTH_PENALTY, 4))
                proc.failure_count += 1
                proc.metadata["stgm_budget_status"] = "negative_contributor"
                proc.metadata["stgm_status"] = "negative_contributor"
                proc.metadata["stgm_negative_threshold"] = str(NEGATIVE_STGM_THRESHOLD)
                if float(stgm_delta) < 0.0:
                    proc.health = max(0.0, round(proc.health - NEGATIVE_SPEND_HEALTH_PENALTY, 4))
                    proc.metadata["stgm_negative_spend_penalty"] = str(NEGATIVE_SPEND_HEALTH_PENALTY)
                if proc.stgm_balance < SEVERE_NEGATIVE_STGM_THRESHOLD:
                    proc.health = max(0.0, round(proc.health - SEVERE_NEGATIVE_STGM_HEALTH_PENALTY, 4))
                    proc.metadata["stgm_status"] = "severe_negative_contributor"
                    proc.metadata["stgm_severe_threshold"] = str(SEVERE_NEGATIVE_STGM_THRESHOLD)
            else:
                proc.metadata["stgm_budget_status"] = "ok"
                proc.metadata["stgm_status"] = "ok"
            proc.last_heartbeat_ts = now
            proc.status = "alive"
            self._append_receipt("heartbeat", proc, receipt_id=receipt_id, stgm_delta=stgm_delta)
            self._write_snapshot()
            return proc

    def sys_register(self, organ_spec: Dict[str, Any]) -> str:
        """Minimal syscall ABI: register an organ from a plain spec dict."""
        now = time.time()
        spec = dict(organ_spec or {})
        proc = OrganProcess(
            pid=str(spec.get("pid") or spec.get("organ_id") or "").strip(),
            organ_id=str(spec.get("organ_id") or spec.get("pid") or "").strip(),
            ring=int(spec.get("ring", 3)),
            health=float(spec.get("health", 1.0)),
            stgm_balance=float(spec.get("stgm_balance", 0.0)),
            current_job=str(spec.get("current_job") or "register"),
            last_receipt_id=str(spec.get("last_receipt_id") or ""),
            failure_count=int(spec.get("failure_count", 0)),
            last_heartbeat_ts=float(spec.get("last_heartbeat_ts") or now),
            location=str(spec.get("location") or "unknown"),
            bodies_present=list(spec.get("bodies_present") or spec.get("bodies") or []),
            metadata=dict(spec.get("metadata") or {}),
            status=str(spec.get("status") or "alive"),
        )
        return self.register(proc, receipt_id=str(spec.get("receipt_id") or ""))

    def sys_heartbeat(
        self,
        pid: str,
        health: float,
        stgm_delta: float,
        location: str | None = None,
        bodies: list[str] | None = None,
        receipt_id: str = "",
    ) -> None:
        """Minimal syscall ABI: heartbeat that always writes a receipt before return."""
        self.heartbeat(
            pid,
            health=health,
            stgm_delta=stgm_delta,
            location=location,
            bodies_present=bodies,
            receipt_id=receipt_id,
            metadata={"syscall": "sys_heartbeat"},
        )

    def sys_budget_state(self, pid: str, requested_spend: float = 0.0) -> Dict[str, Any]:
        """Minimal syscall ABI: return a structured ALLOW/THROTTLE/BLOCK view."""
        with self._lock:
            if pid not in self.table:
                raise KernelRegistrationError(f"unregistered process {pid}")
            proc = self.table[pid]
            state = self.budget_state_for(pid, requested_spend=requested_spend)
            thermal_cost = _float_metadata(proc.metadata, "thermal_cost", default=0.0)
            interrupt_risk = _float_metadata(proc.metadata, "interrupt_risk", default=0.0)
            profitability_score = (proc.health * max(proc.stgm_balance, 0.0)) / (
                1.0 + max(0.0, thermal_cost) + max(0.0, interrupt_risk)
            )
            return {
                "pid": pid,
                "state": state,
                "allow": state == "ALLOW",
                "throttle": state == "THROTTLE",
                "block": state == "BLOCK",
                "requested_spend": max(0.0, float(requested_spend)),
                "ring": proc.ring,
                "health": proc.health,
                "stgm_balance": proc.stgm_balance,
                "profitability_score": round(profitability_score, 6),
            }

    def sys_spend(self, pid: str, amount: float, purpose: str) -> str:
        """Minimal syscall ABI: spend STGM from a ring-0/1 process and receipt it."""
        amount_f = float(amount)
        if amount_f < 0.0:
            raise KernelBudgetError("sys_spend amount must be non-negative")
        self._check_ring(pid, "spend")
        receipt_id = f"receipt_{uuid.uuid4()}"
        self.heartbeat(
            pid,
            stgm_delta=-amount_f,
            current_job=f"spend:{purpose}",
            receipt_id=receipt_id,
            metadata={
                "syscall": "sys_spend",
                "spend_purpose": str(purpose),
                "spend_amount_stgm": str(amount_f),
                "kernel_action": "spend",
            },
        )
        return receipt_id

    def sys_effector_request(
        self,
        pid: str,
        action: str,
        estimated_cost: float = 0.0,
        *,
        evidence_gain: float = 0.45,
        stgm_delta: float = 0.0,
        thermal: float = 0.0,
        interrupt_risk: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Gate one physical/economic effector request and write a receipt.

        This is the demo-grade boundary: an organ asks for an action, the kernel
        checks ring + budget + scheduler utility, and only an ALLOW decision pays
        the visible STGM cost. The effector itself still runs outside this method;
        this syscall proves the action was economically admitted first.
        """
        action_s = str(action or "effector").strip() or "effector"
        cost = max(0.0, float(estimated_cost))
        self._check_ring(pid, "effector")
        budget = self.sys_budget_state(pid, requested_spend=cost)
        budget_state = str(budget.get("state") or "UNKNOWN")
        score = self.scheduler_utility(
            pid,
            evidence_gain=float(evidence_gain),
            stgm_delta=float(stgm_delta),
            thermal=float(thermal),
            interrupt_risk=float(interrupt_risk),
        )
        if budget_state == "BLOCK":
            decision = "BLOCK"
        elif budget_state == "THROTTLE" or score < SCHEDULER_EFFECTOR_THRESHOLD:
            decision = "THROTTLE"
        else:
            decision = "ALLOW"

        receipt_id = f"receipt_{uuid.uuid4()}"
        meta = {
            "syscall": "sys_effector_request",
            "kernel_action": "effector",
            "effector_action": action_s,
            "effector_decision": decision,
            "estimated_cost_stgm": f"{cost:.6f}",
            "budget_state": budget_state,
            "scheduler_score": f"{score:.6f}",
            "evidence_gain": f"{float(evidence_gain):.6f}",
            "thermal": f"{float(thermal):.6f}",
            "interrupt_risk": f"{float(interrupt_risk):.6f}",
        }
        if metadata:
            meta.update({str(k): str(v) for k, v in metadata.items()})
        self.heartbeat(
            pid,
            stgm_delta=-cost if decision == "ALLOW" else 0.0,
            current_job=f"effector_request:{action_s}:{decision}",
            receipt_id=receipt_id,
            failure_delta=0 if decision == "ALLOW" else 1,
            metadata=meta,
        )
        return {
            "truth_label": "SIFTA_KERNEL_EFFECTOR_REQUEST_V1",
            "pid": pid,
            "action": action_s,
            "decision": decision,
            "allow": decision == "ALLOW",
            "budget_state": budget_state,
            "scheduler_score": score,
            "estimated_cost_stgm": cost,
            "receipt_id": receipt_id,
            "budget": budget,
        }

    def sys_memory_query(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Minimal syscall ABI: read process-table memory without side effects."""
        q = dict(query or {})
        limit = max(1, min(200, int(q.get("limit", 50))))
        ring_filter = q.get("ring")
        pid_filter = str(q.get("pid") or "").strip()
        unhealthy_only = bool(q.get("unhealthy_only", False))
        with self._lock:
            rows = self.list_unhealthy() if unhealthy_only else list(self.table.values())
            if pid_filter:
                rows = [p for p in rows if p.pid == pid_filter]
            if ring_filter is not None:
                rows = [p for p in rows if p.ring == int(ring_filter)]
            return [asdict(p) for p in rows[:limit]]

    def sys_self_maintenance_tick(self, max_actions: int = 5) -> int:
        """Minimal syscall ABI: run the kernel's own bounded maintenance tick."""
        with self._lock:
            proc = self.table.get("kernel:self_maintenance")
            if proc is not None:
                self._check_ring(proc.pid, "kernel_maintenance")
        return self.self_maintenance_tick(max_actions=max_actions)

    def sys_schedule(self, pid: str, task: Dict[str, Any]) -> str:
        """Minimal syscall ABI: receipt a schedule request from a ring-0/1 process."""
        receipt_id = f"receipt_{uuid.uuid4()}"
        self._check_ring(pid, "schedule")
        with self._lock:
            if pid not in self.table:
                raise KernelRegistrationError(f"unregistered process {pid}")
            proc = self.table[pid]
            proc.current_job = "schedule"
            proc.last_receipt_id = receipt_id
            proc.last_heartbeat_ts = time.time()
            proc.metadata["last_schedule_receipt_id"] = receipt_id
            self._append_receipt(
                "sys_schedule",
                proc,
                receipt_id=receipt_id,
                task=dict(task or {}),
            )
            self._write_snapshot()
            return receipt_id

    def enforce_action(self, pid: str, action: str, *, requested_spend: float = 0.0) -> Dict[str, Any]:
        """Check registration, ring, and budget for an external boundary action."""
        self._check_ring(pid, action)
        with self._lock:
            budget = self.sys_budget_state(pid, requested_spend=requested_spend)
            return budget

    def terminate(self, pid: str, *, reason: str, receipt_id: str = "") -> OrganProcess:
        with self._lock:
            if pid not in self.table:
                raise KernelRegistrationError(f"unregistered process {pid}")
            proc = self.table[pid]
            proc.status = "terminated"
            proc.current_job = f"terminated: {reason}"
            proc.last_heartbeat_ts = time.time()
            if receipt_id:
                proc.last_receipt_id = receipt_id
            self._append_receipt("terminate", proc, receipt_id=receipt_id, reason=reason)
            self._write_snapshot()
            return proc

    def get(self, pid: str) -> Optional[OrganProcess]:
        with self._lock:
            return self.table.get(pid)

    def list_by_ring(self, ring: int) -> List[OrganProcess]:
        with self._lock:
            return [p for p in self.table.values() if p.ring == int(ring)]

    def list_unhealthy(self, threshold: float = 0.6) -> List[OrganProcess]:
        with self._lock:
            return [
                p
                for p in self.table.values()
                if (
                    p.health < float(threshold)
                    or p.status != "alive"
                    or p.metadata.get("stgm_budget_status") == "negative_contributor"
                    or p.metadata.get("physical_grounding_status") == "missing_decay"
                )
            ]

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "truth_label": "SIFTA_KERNEL_PROCESS_TABLE_V1",
                "boot_ts": self.boot_ts,
                "process_count": len(self.table),
                "aggregate_health": self.aggregate_organism_health(),
                "processes": {pid: asdict(proc) for pid, proc in sorted(self.table.items())},
            }

    def aggregate_organism_health(self) -> float:
        if not self.table:
            return 1.0
        live = [p.health for p in self.table.values() if p.status == "alive"]
        if not live:
            return 0.0
        return round(sum(live) / len(live), 4)

    def self_maintenance_tick(self, max_actions: int = 5, stgm_cost: float = 0.001) -> int:
        """Autopoietic kernel tick: the table maintains its own components.

        The process table scans unhealthy organs, marks bounded repair pressure,
        charges a tiny STGM cost to the kernel maintenance process, and writes
        its own signed receipt. It does not perform repairs directly; it makes
        repair need visible and budgeted for the scheduler/tool router.
        """
        now = time.time()
        max_actions = max(0, int(max_actions))
        actions_taken = 0
        with self._lock:
            if "kernel:self_maintenance" not in self.table:
                self.table["kernel:self_maintenance"] = OrganProcess(
                    pid="kernel:self_maintenance",
                    organ_id="kernel/process_table/self_maintenance",
                    ring=0,
                    health=1.0,
                    stgm_balance=0.0,
                    current_job="self_maintenance",
                    last_receipt_id="",
                    failure_count=0,
                    last_heartbeat_ts=now,
                    location="kernel",
                    bodies_present=["sifta_kernel"],
                    metadata={"autopoietic_role": "maintains_process_table"},
                )
            kernel_proc = self.table["kernel:self_maintenance"]
            ambient_context = latest_ambient_world_context(
                self.state_root,
                max_age_s=AMBIENT_CONTEXT_MAX_AGE_S,
            )
            kernel_proc.metadata["current_ambient_context"] = _compact_json_for_metadata(ambient_context)
            kernel_proc.metadata["ambient_context_active"] = str(bool(ambient_context.get("active"))).lower()
            kernel_proc.metadata["ambient_interrupt_risk_delta"] = f"{float(ambient_context.get('interrupt_risk_delta') or 0.0):.3f}"
            kernel_proc.metadata["ambient_owner_priority_boost"] = f"{float(ambient_context.get('owner_priority_boost') or 0.0):.3f}"
            kernel_proc.metadata["ambient_context_query_hint"] = str(ambient_context.get("query_hint") or "")
            unhealthy = sorted(
                self.list_unhealthy(),
                key=lambda p: self.scheduler_utility(
                    p.pid,
                    evidence_gain=_repair_evidence_gain(p),
                    stgm_delta=max(0.0, float(stgm_cost)) * 2.0,
                    thermal=0.01,
                    interrupt_risk=0.0,
                ),
                reverse=True,
            )
            for proc in unhealthy:
                if actions_taken >= max_actions:
                    break
                if proc.pid == "kernel:self_maintenance":
                    continue
                repair_priority = self.scheduler_utility(
                    proc.pid,
                    evidence_gain=_repair_evidence_gain(proc),
                    stgm_delta=max(0.0, float(stgm_cost)) * 2.0,
                    thermal=0.01,
                    interrupt_risk=0.0,
                )
                proc.metadata["repair_needed"] = "true"
                proc.metadata["repair_priority"] = f"{repair_priority:.6f}"
                proc.metadata["repair_budget_stgm"] = f"{max(0.0, float(stgm_cost)):.6f}"
                proc.metadata["last_maintenance_ts"] = str(now)
                if proc.stgm_balance < NEGATIVE_STGM_THRESHOLD:
                    proc.metadata["repair_reason"] = "negative_stgm_contributor"
                elif proc.metadata.get("physical_grounding_status") == "missing_decay":
                    proc.metadata["repair_reason"] = "missing_physical_grounding"
                elif proc.status != "alive":
                    proc.metadata["repair_reason"] = "not_alive"
                else:
                    proc.metadata["repair_reason"] = "low_health"
                actions_taken += 1
            kernel_proc.stgm_balance -= max(0.0, float(stgm_cost))
            kernel_proc.current_job = f"self_maintenance actions={actions_taken}"
            kernel_proc.last_heartbeat_ts = now
            self.decay_routing_field(rate=0.95)
            kernel_proc.metadata["last_self_maintenance_ts"] = str(now)
            kernel_proc.metadata["last_self_maintenance_actions"] = str(actions_taken)

            # Field self-regulation (allostatic loop). Runs on a slower
            # cadence than the maintenance tick itself to keep cost bounded.
            # Cell 2024 brain-body physiology + Sterling 2012 allostasis.
            try:
                tick_count = int(kernel_proc.metadata.get("self_maintenance_tick_count", "0")) + 1
                kernel_proc.metadata["self_maintenance_tick_count"] = str(tick_count)
                if tick_count % 8 == 0:
                    from System.swarm_field_self_regulator import regulate_now
                    reg = regulate_now(dry_run=False)
                    kernel_proc.metadata["last_field_regulation_ts"] = str(now)
                    kernel_proc.metadata["last_field_regulation_actions"] = str(len(reg.get("actions", [])))
                    kernel_proc.metadata["last_field_regulation_issues"] = str(len(reg.get("issues", [])))
            except Exception:
                pass
            self._append_receipt(
                "self_maintenance_tick",
                kernel_proc,
                unhealthy_count=len(self.list_unhealthy()),
                actions_taken=actions_taken,
                stgm_cost=max(0.0, float(stgm_cost)),
                ambient_context=ambient_context,
            )
            self._write_snapshot()
            return actions_taken

    def scheduler_utility(
        self,
        pid: str,
        evidence_gain: float = 0.0,
        stgm_delta: float = 0.0,
        thermal: float = 0.0,
        interrupt_risk: float = 0.0,
    ) -> float:
        """Receipt-derived scheduler utility from the physics/biology spine.

        evidence + STGM delta - Kleiber-scaled thermal - owner interrupt cost,
        bounded by Ashby viability, autopoietic repair pressure, and a Tierra
        scout floor for cheap exploration.
        """
        proc = self.get(pid)
        if not proc:
            return -999.0
        mass = max(1.0, abs(proc.stgm_balance) + len(proc.current_job) * 0.1)
        scaled_thermal = float(thermal) * (mass ** 0.75)
        ambient_context = self._current_ambient_context()
        effective_interrupt_risk = float(interrupt_risk) + float(
            ambient_context.get("interrupt_risk_delta") or 0.0
        )
        score = float(evidence_gain) + float(stgm_delta) - scaled_thermal - effective_interrupt_risk
        salience_score = _safe_float(ambient_context.get("salience_score"), default=0.0)
        if salience_score > 0.0:
            score += min(HIGH_SALIENCE_PRIORITY_BONUS, salience_score * HIGH_SALIENCE_PRIORITY_BONUS)
        if (
            salience_score < 0.15
            and ambient_context.get("sampling_policy") == "idle"
            and not proc.metadata.get("repair_needed")
            and not _is_owner_related_process(proc)
        ):
            score -= LOW_SALIENCE_IDLE_PENALTY
        if ambient_context.get("recent_owner_voice") and _is_owner_related_process(proc):
            score += float(ambient_context.get("owner_priority_boost") or 0.0)
        if proc.health < 0.4 or proc.stgm_balance < NEGATIVE_STGM_THRESHOLD:
            score *= 0.6
        if proc.metadata.get("repair_needed") or "repair" in proc.current_job.lower():
            score += 0.15
        if proc.metadata.get("scout_mode"):
            score = max(score, 0.05)

        # ── Stigmergic routing field boost ─────────────────────
        # The routing field accumulates success/failure traces per
        # task category (like ant pheromone trails for food sources).
        # Successful tasks deposit positive traces; the field decays.
        # This gives the scheduler a self-organizing memory of which
        # task types are currently productive.
        task_cat = proc.metadata.get("task_category", proc.current_job[:20])
        if task_cat and hasattr(self, "_routing_field"):
            field_boost = self._routing_field.get(task_cat, 0.0)
            score += max(-0.15, min(field_boost * 0.05, 0.15))

        return round(float(score), 6)

    # ── stigmergic routing field ───────────────────────────────

    def deposit_routing_trace(
        self, task_category: str, success: bool, amount: float = 1.0,
    ) -> None:
        """Deposit a pheromone trace for a task category.

        Successful tasks deposit positive traces (reinforcement).
        Failed tasks deposit negative traces (avoidance).
        The field decays each maintenance tick (evaporation).

        This is the same mechanism as the Bell app's pheromone field,
        applied to scheduler routing instead of particle measurement.
        General principle: System/stigmergic_field.py
        """
        if not hasattr(self, "_routing_field"):
            self._routing_field: dict[str, float] = {}
        val = amount if success else -amount * 0.5
        self._routing_field[task_category] = (
            self._routing_field.get(task_category, 0.0) + val
        )

    def decay_routing_field(self, rate: float = 0.95) -> None:
        """Evaporate the routing field (called from maintenance tick)."""
        if not hasattr(self, "_routing_field"):
            return
        for k in list(self._routing_field):
            self._routing_field[k] *= rate
            if abs(self._routing_field[k]) < 0.01:
                del self._routing_field[k]

    def _current_ambient_context(self) -> dict[str, Any]:
        """Return the last maintenance-tick ambient context for scheduler scoring."""
        kernel_proc = self.table.get("kernel:self_maintenance")
        if kernel_proc is None:
            return {}
        raw = kernel_proc.metadata.get("current_ambient_context") or ""
        try:
            data = json.loads(raw)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def budget_state_for(self, pid: str, *, requested_spend: float = 0.0) -> str:
        """Return ALLOW, THROTTLE, or BLOCK for a process request."""
        with self._lock:
            proc = self.table.get(pid)
            if proc is None:
                raise KernelRegistrationError(f"unregistered process {pid}")
            next_balance = proc.stgm_balance - max(0.0, float(requested_spend))
            if self.enforce_budget and next_balance < 0.0:
                return "BLOCK"
            if next_balance < SEVERE_NEGATIVE_STGM_THRESHOLD:
                return "BLOCK"
            if proc.status != "alive" or proc.health < 0.35:
                return "THROTTLE"
            if proc.failure_count >= 3:
                return "THROTTLE"
            if next_balance < -5.0:
                return "THROTTLE"
            return "ALLOW"

    def _load_snapshot(self) -> None:
        if not self.snapshot_path.exists():
            return
        try:
            data = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except Exception:
            return
        try:
            self.boot_ts = float(data.get("boot_ts") or self.boot_ts)
        except Exception:
            pass
        processes = data.get("processes") or {}
        if not isinstance(processes, dict):
            return
        for pid, raw in processes.items():
            if not isinstance(raw, dict):
                continue
            try:
                proc = OrganProcess(**{**raw, "pid": raw.get("pid") or pid}).normalized()
            except Exception:
                continue
            self.table[proc.pid] = proc

    def _append_receipt(self, action: str, proc: OrganProcess, **extra: Any) -> str:
        self.state_root.mkdir(parents=True, exist_ok=True)
        trace_id = str(extra.get("receipt_id") or "") or str(uuid.uuid4())
        row = {
            "ts": time.time(),
            "trace_id": trace_id,
            "truth_label": "SIFTA_KERNEL_PROCESS_TABLE_V1",
            "type": _kernel_receipt_type(action),
            "action": action,
            "pid": proc.pid,
            "organ_id": proc.organ_id,
            "ring": proc.ring,
            "health": proc.health,
            "stgm_balance": proc.stgm_balance,
            "current_job": proc.current_job,
            "last_receipt_id": proc.last_receipt_id,
            "failure_count": proc.failure_count,
            "location": proc.location,
            "bodies_present": proc.bodies_present,
            "tokens_per_sec": _float_metadata(proc.metadata, "tokens_per_sec", default=0.0),
            "latency_ms": _float_metadata(proc.metadata, "latency_ms", default=0.0),
            "used_mtp": _bool_metadata(proc.metadata, "used_mtp", default=False),
            "status": proc.status,
            "extra": {k: v for k, v in extra.items() if v not in ("", None, 0.0)},
        }
        if action in {"heartbeat", "self_maintenance_tick"}:
            row["score"] = self.scheduler_utility(proc.pid, stgm_delta=float(extra.get("stgm_delta") or 0.0))
        payload = _canonical_json(row)
        row.update(_sign_receipt_payload(payload))
        row["signature"] = row.get("signature_hex") or "unsigned_fallback"
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return trace_id

    def _write_snapshot(self) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.snapshot_path.write_text(
            json.dumps(self.snapshot(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _check_ring(self, pid: str, action: str) -> None:
        """Enforce the syscall ring table for one registered process."""
        with self._lock:
            if pid not in self.table:
                raise KernelRegistrationError(f"unregistered process {pid}")
            self._require_action_allowed_locked(self.table[pid], action)

    def _require_action_allowed_locked(self, proc: OrganProcess, action: str) -> None:
        normalized = str(action or "").strip().lower()
        max_ring = ACTION_RING_LIMITS.get(normalized)
        if max_ring is None:
            return
        if normalized == "kernel_maintenance" and proc.ring != 0:
            raise PermissionError(f"ring {proc.ring} cannot {normalized}")
        if proc.ring > max_ring:
            raise PermissionError(f"ring {proc.ring} cannot {normalized}")


_GLOBAL_TABLE: Optional[KernelProcessTable] = None


def _read_jsonl_tail(path: Path, *, n: int = 120) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: deque[dict[str, Any]] = deque(maxlen=max(1, int(n)))
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except Exception:
        return []
    return list(rows)


def _compact_json_for_metadata(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_json(row: dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _float_metadata(metadata: Dict[str, str], key: str, *, default: float = 0.0) -> float:
    try:
        return float((metadata or {}).get(key, default))
    except Exception:
        return default


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _bool_metadata(metadata: Dict[str, str], key: str, *, default: bool = False) -> bool:
    value = (metadata or {}).get(key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _repair_evidence_gain(proc: OrganProcess) -> float:
    if proc.metadata.get("stgm_budget_status") == "negative_contributor":
        return 0.35
    if proc.metadata.get("physical_grounding_status") == "missing_decay":
        return 0.28
    if proc.status != "alive":
        return 0.24
    return 0.18


def _is_owner_related_process(proc: OrganProcess) -> bool:
    haystack = " ".join(
        [
            proc.pid,
            proc.organ_id,
            proc.current_job,
            proc.metadata.get("kind", ""),
            proc.metadata.get("owner_related", ""),
            proc.metadata.get("task_family", ""),
        ]
    ).lower()
    return any(token in haystack for token in ("owner", "george", "talk_to_alice", "alice_talk", "care"))


def _ambient_row_mentions_owner_voice(row: dict[str, Any]) -> bool:
    blob = " ".join(
        str(row.get(key) or "")
        for key in ("route", "reason", "summary", "text_preview", "event_type")
    ).lower()
    return any(token in blob for token in ("owner_voice", "owner voice", "nearfield_voice", "george", "wake_word"))


def _ambient_row_mentions_phone_call(row: dict[str, Any]) -> bool:
    blob = " ".join(
        str(row.get(key) or "")
        for key in ("route", "reason", "summary", "text_preview", "event_type")
    ).lower()
    return "phone" in blob or "call" in blob


def _ambient_row_activity(row: dict[str, Any]) -> str | None:
    blob = " ".join(
        str(row.get(key) or "")
        for key in ("route", "reason", "summary", "text_preview", "event_type")
    ).lower()
    if "phone" in blob or "call" in blob:
        return "conversation"
    if "coding" in blob or "code" in blob:
        return "coding"
    if "media" in blob or "youtube" in blob or "video" in blob:
        return "media"
    if "voice" in blob or "conversation" in blob:
        return "conversation"
    return None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def latest_ambient_world_context(
    state_root: Path | str = DEFAULT_STATE_ROOT,
    *,
    max_age_s: float = AMBIENT_CONTEXT_MAX_AGE_S,
    owner_voice_window_s: float = 120.0,
    tail_rows: int = 120,
) -> dict[str, Any]:
    """Summarize recent ambient diary traces for kernel/scout routing.

    This reads only append-only diary receipts. It does not open microphones,
    inspect raw audio, or wake the primary cortex.
    """
    now = time.time()
    ledger = Path(state_root) / AMBIENT_DIARY_LEDGER_NAME
    raw_rows = _read_jsonl_tail(ledger, n=tail_rows)
    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        if row.get("truth_label") != AMBIENT_DIARY_TRUTH_LABEL:
            continue
        try:
            ts = float(row.get("ts") or 0.0)
        except Exception:
            ts = 0.0
        if ts <= 0.0 or now - ts > max(0.0, float(max_age_s)):
            continue
        rows.append(row)

    route_counts: dict[str, int] = {}
    for row in rows:
        route = str(row.get("route") or row.get("event_type") or "unknown")
        route_counts[route] = route_counts.get(route, 0) + 1

    phone_call_active = any(_ambient_row_mentions_phone_call(row) for row in rows)
    recent_owner_voice = any(
        _ambient_row_mentions_owner_voice(row)
        and now - float(row.get("ts") or 0.0) <= max(0.0, float(owner_voice_window_s))
        for row in rows
    )
    high_ambient_noise = phone_call_active or route_counts.get("ambient_media", 0) >= 2
    latest_ts = max((float(row.get("ts") or 0.0) for row in rows), default=0.0)
    activity_counts: dict[str, int] = {}
    for row in rows:
        activity = _ambient_row_activity(row)
        if activity:
            activity_counts[activity] = activity_counts.get(activity, 0) + 1
    dominant_activity = None
    if activity_counts:
        dominant_activity = max(activity_counts.items(), key=lambda item: item[1])[0]
    preview = ""
    if rows:
        preview = " ".join(str(rows[-1].get("text_preview") or rows[-1].get("summary") or "").split())[:160]

    interrupt_delta = 0.0
    if high_ambient_noise:
        interrupt_delta += 0.12
    if phone_call_active:
        interrupt_delta += 0.08
    owner_boost = 0.15 if recent_owner_voice else 0.0
    max_repeated_route = max(route_counts.values(), default=0)
    habituation_score = 0.0
    if not recent_owner_voice:
        habituation_score = min(0.6, max(0, max_repeated_route - 1) * 0.08)
    route_diversity = len(route_counts)
    novelty_score = _clamp01(route_diversity * 0.12 + (0.18 if dominant_activity in {"coding", "conversation"} else 0.0))
    salience_score = 0.08 + novelty_score
    if recent_owner_voice:
        salience_score += 0.55
    if dominant_activity == "coding":
        salience_score += 0.24
    elif dominant_activity == "conversation":
        salience_score += 0.18
    elif dominant_activity == "media":
        salience_score += 0.06
    if phone_call_active:
        salience_score += 0.08
    salience_score = _clamp01(salience_score - habituation_score)
    if salience_score >= 0.55 or recent_owner_voice:
        sampling_policy = "engage"
    elif salience_score >= 0.22:
        sampling_policy = "sample"
    else:
        sampling_policy = "idle"

    return {
        "truth_label": "KERNEL_AMBIENT_CONTEXT_V1",
        "source_ledger": AMBIENT_DIARY_LEDGER_NAME,
        "source_truth_label": AMBIENT_DIARY_TRUTH_LABEL,
        "active": bool(rows),
        "rows": len(rows),
        "route_counts": route_counts,
        "latest_ts": latest_ts,
        "last_update_ts": latest_ts,
        "age_s": round(now - latest_ts, 3) if latest_ts else None,
        "high_ambient_noise": bool(high_ambient_noise),
        "phone_call_active": bool(phone_call_active),
        "recent_owner_voice": bool(recent_owner_voice),
        "recent_owner_voice_detected": bool(recent_owner_voice),
        "dominant_activity": dominant_activity,
        "salience_score": round(salience_score, 3),
        "novelty_score": round(novelty_score, 3),
        "habituation_score": round(habituation_score, 3),
        "sampling_policy": sampling_policy,
        "interrupt_risk_delta": round(interrupt_delta, 3),
        "owner_priority_boost": round(owner_boost, 3),
        "query_hint": (
            "ambient_noise_or_phone_call"
            if high_ambient_noise
            else "recent_owner_voice" if recent_owner_voice else "no_recent_ambient_diary"
        ),
        "latest_preview": preview,
    }


def _kernel_receipt_type(action: str) -> str:
    if action == "heartbeat":
        return "KERNEL_HEARTBEAT"
    if action == "self_maintenance_tick":
        return "KERNEL_SELF_MAINTENANCE"
    return f"KERNEL_{str(action or 'event').upper()}"


def _sign_receipt_payload(payload: str) -> dict[str, str]:
    try:
        from System.crypto_keychain import get_silicon_identity, sign_block

        return {
            "signature_alg": "Ed25519",
            "signature_payload": payload,
            "signature_hex": sign_block(payload),
            "signing_serial": get_silicon_identity(),
        }
    except Exception as exc:
        return {
            "signature_alg": "UNSIGNED_KERNEL_RECEIPT_FALLBACK",
            "signature_payload": payload,
            "signature_hex": "",
            "signing_serial": "",
            "signature_error": f"{type(exc).__name__}: {exc}",
        }


def latest_physical_context(
    state_root: Path | str = DEFAULT_STATE_ROOT,
    *,
    max_age_s: float = 300.0,
) -> dict[str, Any]:
    """Best-effort E35 physical context from recent local ledgers.

    No live sensor is opened here. The kernel only reads existing receipts and
    lets `stigmerobotics_physical_space` normalize them.
    """
    state = Path(state_root)
    ledger_names = (
        "ide_stigmergic_trace.jsonl",
        "visual_stigmergy.jsonl",
        "face_detection_events.jsonl",
        "face_recognition_events.jsonl",
        "owner_body_events.jsonl",
        "unified_stigmergic_field.jsonl",
        "app_focus.jsonl",
    )
    rows: list[dict[str, Any]] = []
    for name in ledger_names:
        rows.extend(_read_jsonl_tail(state / name, n=80))
    if not rows:
        return {}
    try:
        from System.stigmerobotics_physical_space import build_physical_space_report

        report = build_physical_space_report(rows, now_ts=time.time(), max_age_s=max_age_s)
    except Exception:
        return {}
    if not report.grounded:
        return {}
    bodies = [b for b in report.body_ids if b not in {"unknown_body", "silicon_substrate", "unified_field"}]
    if report.physical_presence and "owner_present" not in bodies:
        bodies.append("owner_present")
    location = report.unified_field_location_segment or ""
    return {
        "source": "E35_physical_space_report",
        "location": location,
        "bodies_present": bodies,
        "physical_presence": report.physical_presence,
        "physical_proximity": report.physical_proximity,
        "thermal_load": report.thermal_load,
        "last_physical_event_ts": report.last_physical_event_ts,
        "presence_gates_ok": report.presence_gates_ok,
    }


def get_kernel_process_table(*, state_root: Path | str = DEFAULT_STATE_ROOT) -> KernelProcessTable:
    global _GLOBAL_TABLE
    if _GLOBAL_TABLE is None or Path(state_root) != _GLOBAL_TABLE.state_root:
        _GLOBAL_TABLE = KernelProcessTable(state_root=state_root)
    return _GLOBAL_TABLE


def register_process(process: OrganProcess, *, state_root: Path | str = DEFAULT_STATE_ROOT) -> str:
    return get_kernel_process_table(state_root=state_root).register(process)


def ensure_registered(
    process: OrganProcess,
    *,
    state_root: Path | str = DEFAULT_STATE_ROOT,
    receipt_id: str = "",
) -> OrganProcess:
    return get_kernel_process_table(state_root=state_root).ensure_registered(process, receipt_id=receipt_id)


def heartbeat(pid: str, *, state_root: Path | str = DEFAULT_STATE_ROOT, **kwargs: Any) -> OrganProcess:
    return get_kernel_process_table(state_root=state_root).heartbeat(pid, **kwargs)


def sys_register(organ_spec: Dict[str, Any], *, state_root: Path | str = DEFAULT_STATE_ROOT) -> str:
    return get_kernel_process_table(state_root=state_root).sys_register(organ_spec)


def sys_heartbeat(
    pid: str,
    health: float,
    stgm_delta: float,
    *,
    state_root: Path | str = DEFAULT_STATE_ROOT,
    location: str | None = None,
    bodies: list[str] | None = None,
    receipt_id: str = "",
) -> None:
    return get_kernel_process_table(state_root=state_root).sys_heartbeat(
        pid,
        health,
        stgm_delta,
        location=location,
        bodies=bodies,
        receipt_id=receipt_id,
    )


def sys_budget_state(
    pid: str,
    *,
    state_root: Path | str = DEFAULT_STATE_ROOT,
    requested_spend: float = 0.0,
) -> Dict[str, Any]:
    return get_kernel_process_table(state_root=state_root).sys_budget_state(
        pid,
        requested_spend=requested_spend,
    )


def sys_spend(
    pid: str,
    amount: float,
    purpose: str,
    *,
    state_root: Path | str = DEFAULT_STATE_ROOT,
) -> str:
    return get_kernel_process_table(state_root=state_root).sys_spend(pid, amount, purpose)


def sys_memory_query(
    query: Dict[str, Any],
    *,
    state_root: Path | str = DEFAULT_STATE_ROOT,
) -> List[Dict[str, Any]]:
    return get_kernel_process_table(state_root=state_root).sys_memory_query(query)


def sys_self_maintenance_tick(
    max_actions: int = 5,
    *,
    state_root: Path | str = DEFAULT_STATE_ROOT,
) -> int:
    return get_kernel_process_table(state_root=state_root).sys_self_maintenance_tick(max_actions=max_actions)


def sys_schedule(
    pid: str,
    task: Dict[str, Any],
    *,
    state_root: Path | str = DEFAULT_STATE_ROOT,
) -> str:
    return get_kernel_process_table(state_root=state_root).sys_schedule(pid, task)


def sys_effector_request(
    pid: str,
    action: str,
    estimated_cost: float = 0.0,
    *,
    evidence_gain: float = 0.45,
    stgm_delta: float = 0.0,
    thermal: float = 0.0,
    interrupt_risk: float = 0.0,
    metadata: Optional[Dict[str, Any]] = None,
    state_root: Path | str = DEFAULT_STATE_ROOT,
) -> Dict[str, Any]:
    return get_kernel_process_table(state_root=state_root).sys_effector_request(
        pid,
        action,
        estimated_cost,
        evidence_gain=evidence_gain,
        stgm_delta=stgm_delta,
        thermal=thermal,
        interrupt_risk=interrupt_risk,
        metadata=metadata,
    )


def scheduler_utility(
    pid: str,
    evidence_gain: float = 0.0,
    stgm_delta: float = 0.0,
    thermal: float = 0.0,
    interrupt_risk: float = 0.0,
    *,
    state_root: Path | str = DEFAULT_STATE_ROOT,
) -> float:
    return get_kernel_process_table(state_root=state_root).scheduler_utility(
        pid,
        evidence_gain=evidence_gain,
        stgm_delta=stgm_delta,
        thermal=thermal,
        interrupt_risk=interrupt_risk,
    )
