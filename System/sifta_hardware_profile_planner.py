#!/usr/bin/env python3
"""Plan SIFTA install roles from hardware facts.

The planner keeps installer language aligned with physical RAM. It does not
pull models or mutate the machine; it emits the role, model policy, and commands
that an installer or human can review.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class HardwareFacts:
    os_name: str
    machine: str
    memory_gb: float
    cpu_brand: str = ""
    is_raspberry_pi: bool = False


@dataclass(frozen=True)
class ModelSlot:
    name: str
    role: str
    status: str
    reason: str


@dataclass(frozen=True)
class HardwarePlan:
    hardware_role: str
    summary: str
    local_models: list[ModelSlot] = field(default_factory=list)
    skipped_models: list[ModelSlot] = field(default_factory=list)
    optional_lanes: list[str] = field(default_factory=list)
    install_commands: list[str] = field(default_factory=list)
    truth_label: str = "OPERATIONAL_INSTALL_PLAN"


def _run_text(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=4).stdout
    except Exception:
        return ""


def _mac_memory_gb() -> float:
    text = _run_text(["system_profiler", "SPHardwareDataType"])
    match = re.search(r"Memory:\s*([0-9.]+)\s*GB", text)
    if match:
        return float(match.group(1))
    return 0.0


def _mac_cpu_brand() -> str:
    text = _run_text(["system_profiler", "SPHardwareDataType"])
    for line in text.splitlines():
        if "Chip:" in line or "Processor Name:" in line:
            return line.split(":", 1)[-1].strip()
    return platform.processor() or platform.machine()


def _linux_memory_gb() -> float:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return 0.0
    match = re.search(r"MemTotal:\s*(\d+)\s*kB", meminfo.read_text(errors="ignore"))
    if not match:
        return 0.0
    return int(match.group(1)) / (1024 * 1024)


def _linux_cpu_brand() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.exists():
        return platform.processor() or platform.machine()
    text = cpuinfo.read_text(errors="ignore")
    for key in ("Model", "Hardware", "model name"):
        match = re.search(rf"^{re.escape(key)}\s*:\s*(.+)$", text, re.MULTILINE)
        if match:
            return match.group(1).strip()
    return platform.processor() or platform.machine()


def _is_raspberry_pi(cpu_brand: str) -> bool:
    model_path = Path("/proc/device-tree/model")
    model = model_path.read_text(errors="ignore").replace("\\x00", "") if model_path.exists() else ""
    text = f"{model} {cpu_brand}".lower()
    return "raspberry pi" in text


def detect_hardware_facts() -> HardwareFacts:
    os_name = platform.system()
    machine = platform.machine()
    if os_name == "Darwin":
        memory_gb = _mac_memory_gb()
        cpu_brand = _mac_cpu_brand()
        return HardwareFacts(
            os_name=os_name,
            machine=machine,
            memory_gb=memory_gb,
            cpu_brand=cpu_brand,
            is_raspberry_pi=False,
        )

    if os_name == "Linux":
        memory_gb = _linux_memory_gb()
        cpu_brand = _linux_cpu_brand()
        return HardwareFacts(
            os_name=os_name,
            machine=machine,
            memory_gb=memory_gb,
            cpu_brand=cpu_brand,
            is_raspberry_pi=_is_raspberry_pi(cpu_brand),
        )

    return HardwareFacts(
        os_name=os_name,
        machine=machine,
        memory_gb=0.0,
        cpu_brand=platform.processor() or machine,
        is_raspberry_pi=False,
    )


def plan_for_hardware(facts: HardwareFacts) -> HardwarePlan:
    """Return the SIFTA install plan for a hardware profile."""

    if facts.os_name == "Darwin" and facts.memory_gb >= 24:
        return HardwarePlan(
            hardware_role="M5_FOUNDRY",
            summary="Alice primary body. Gemma4 runs locally; smaller models are scouts/reflexes.",
            local_models=[
                ModelSlot("sifta-gemma4-alice:latest", "Alice primary cortex", "required", "24GB+ unified memory tier"),
                ModelSlot("qwen3.5:2b", "corvid/reflex", "recommended", "fast small local reflex organ"),
                ModelSlot("sifta-classifier-c1:latest", "intent classifier", "optional", "only if C1 path is enabled"),
            ],
            skipped_models=[],
            optional_lanes=[
                "qwen3.5:9b multimodal scout after pull/benchmark",
                "granite4.1:3b doctor/tool prover after comparison tests",
            ],
            install_commands=[
                "ollama pull sifta-gemma4-alice",
                "ollama pull qwen3.5:2b",
            ],
        )

    if facts.os_name == "Darwin" and facts.memory_gb >= 8:
        return HardwarePlan(
            hardware_role="MAC_SENTRY",
            summary="Scout/sentry node. Local Qwen scouts; M5 Foundry handles Gemma4 primary responses.",
            local_models=[
                ModelSlot("qwen3.5:4b", "local multimodal scout", "recommended", "8GB-safe scout tier"),
                ModelSlot("qwen3.5:2b", "corvid/reflex", "recommended", "fast small local reflex organ"),
            ],
            skipped_models=[
                ModelSlot("sifta-gemma4-alice:latest", "Alice primary cortex", "skip", "Gemma4 does not fit safely in soldered 8GB RAM"),
            ],
            optional_lanes=["borrow M5 Gemma4 inference over swarm network"],
            install_commands=[
                "ollama pull qwen3.5:4b",
                "ollama pull qwen3.5:2b",
            ],
        )

    if facts.is_raspberry_pi and facts.memory_gb >= 7.0:
        return HardwarePlan(
            hardware_role="PI5_EDGE_SCOUT",
            summary="Edge scout and sensor node. Python writes receipts; compiled backends do heavy inference.",
            local_models=[
                ModelSlot("qwen3.5:0.8b", "tiny edge scout", "test", "verify runtime footprint before default"),
            ],
            skipped_models=[
                ModelSlot("sifta-gemma4-alice:latest", "Alice primary cortex", "skip", "Gemma4 belongs on Foundry, not Pi 5 8GB"),
            ],
            optional_lanes=[
                "3B-class Q4 GGUF via llama.cpp",
                "slow 7B-class Q4 GGUF only if latency is acceptable",
                "Raspberry Pi AI HAT+/Hailo CV lane",
                "borrow M5 Gemma4 inference over swarm network",
            ],
            install_commands=[
                "# boot sensor/receipt services first",
                "# optional after proof: qwen3.5:0.8b or llama.cpp GGUF",
            ],
        )

    if facts.memory_gb >= 2.0:
        return HardwarePlan(
            hardware_role="PYTHON_FIELD_NODE",
            summary="Generic sensor/field node. Signed receipts first; local tiny model only after proof.",
            local_models=[
                ModelSlot("qwen3.5:0.8b", "tiny local scout", "test", "2GB+ target; verify by receipt"),
            ],
            skipped_models=[
                ModelSlot("sifta-gemma4-alice:latest", "Alice primary cortex", "skip", "Gemma4 belongs on Foundry"),
            ],
            optional_lanes=["borrow M5 Gemma4 inference over swarm network"],
            install_commands=[
                "# no default model pull",
                "# boot signed sensor/feature receipts first",
            ],
        )

    return HardwarePlan(
        hardware_role="TINY_SENSOR_LIMB",
        summary="Sensor limb only. No local LLM by default.",
        local_models=[],
        skipped_models=[
            ModelSlot("qwen3.5:0.8b", "tiny local scout", "skip", "RAM below 2GB target"),
            ModelSlot("sifta-gemma4-alice:latest", "Alice primary cortex", "skip", "Gemma4 belongs on Foundry"),
        ],
        optional_lanes=["signed JSONL feature receipts", "borrow M5 Gemma4 inference if networked"],
        install_commands=[
            "# no default model pull",
            "# run Python receipt/sensor services only",
        ],
    )


def render_plan(facts: HardwareFacts, plan: HardwarePlan) -> str:
    lines = [
        f"Hardware: {facts.os_name} {facts.machine} | {facts.cpu_brand} | {facts.memory_gb:.1f} GB",
        f"Role: {plan.hardware_role}",
        f"Summary: {plan.summary}",
        "",
        "Local models:",
    ]
    if plan.local_models:
        for slot in plan.local_models:
            lines.append(f"  - {slot.name}: {slot.role} [{slot.status}] — {slot.reason}")
    else:
        lines.append("  - none")

    lines.append("")
    lines.append("Skipped models:")
    if plan.skipped_models:
        for slot in plan.skipped_models:
            lines.append(f"  - {slot.name}: {slot.role} [{slot.status}] — {slot.reason}")
    else:
        lines.append("  - none")

    lines.append("")
    lines.append("Optional lanes:")
    for lane in plan.optional_lanes or ["none"]:
        lines.append(f"  - {lane}")

    lines.append("")
    lines.append("Install commands:")
    for command in plan.install_commands or ["# no model commands"]:
        lines.append(f"  {command}")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--os-name")
    parser.add_argument("--machine")
    parser.add_argument("--memory-gb", type=float)
    parser.add_argument("--cpu-brand", default="")
    parser.add_argument("--raspberry-pi", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.memory_gb is not None:
        facts = HardwareFacts(
            os_name=args.os_name or platform.system(),
            machine=args.machine or platform.machine(),
            memory_gb=args.memory_gb,
            cpu_brand=args.cpu_brand,
            is_raspberry_pi=args.raspberry_pi,
        )
    else:
        facts = detect_hardware_facts()

    plan = plan_for_hardware(facts)
    if args.json:
        print(json.dumps({"facts": asdict(facts), "plan": asdict(plan)}, indent=2, sort_keys=True))
    else:
        print(render_plan(facts, plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
