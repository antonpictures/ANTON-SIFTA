import time

from System.swarm_kernel_process_table import KernelProcessTable, OrganProcess


def _proc(pid: str = "tool_router:deterministic", failure_count: int = 10) -> OrganProcess:
    return OrganProcess(
        pid=pid,
        organ_id="System/swarm_tool_router.py",
        ring=2,
        health=1.0,
        stgm_balance=0.0,
        current_job="tool_router",
        last_receipt_id="",
        failure_count=failure_count,
        last_heartbeat_ts=time.time(),
        location="sifta_desktop_body",
        bodies_present=["alice_tool_router"],
        metadata={"kernel_role": "cortex_receipted_tool_router"},
    )


def test_sys_decay_failures_halves_failure_count(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_proc(failure_count=10))

    table.sys_decay_failures(0.5)

    assert table.get("tool_router:deterministic").failure_count == 5


def test_sys_success_credit_decrements_and_floors(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_proc(failure_count=2))

    table.sys_success_credit("tool_router:deterministic")
    table.sys_success_credit("tool_router:deterministic")
    table.sys_success_credit("tool_router:deterministic")

    assert table.get("tool_router:deterministic").failure_count == 0


def test_sys_budget_state_allows_after_decay_when_other_conditions_pass(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_proc(failure_count=10))

    assert table.sys_budget_state("tool_router:deterministic")["state"] == "THROTTLE"
    table.sys_decay_failures(0.2)

    state = table.sys_budget_state("tool_router:deterministic")
    assert table.get("tool_router:deterministic").failure_count == 2
    assert state["state"] == "ALLOW"
    assert state["allow"] is True
