#!/usr/bin/env python3
"""
swarm_boot.py — in-repo “hello swarm” registry (simulation / scaffolding)

This is **not** a wire protocol to external chat products. It persists a small
JSON snapshot under ``.sifta_state/`` and optionally leaves one row on
``ide_stigmergic_trace.jsonl`` so other tools see the boot event.

Logical roles (SwarmGPT, Observer, …) are **labels**, not silicon identities.
Hardware anchors use ``homeworld_serial`` from ``ide_stigmergic_bridge``.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_DEFAULT_STATE = _REPO / ".sifta_state" / "swarm_boot.json"

# Default logical swarm roles (no network I/O).
_DEFAULT_NODES: Tuple[Tuple[str, str], ...] = (
    ("SwarmGPT", "language_orchestrator"),
    ("Observer", "validation_layer"),
    ("Stigmergy", "trace_memory"),
    ("PolicyMixer", "entropy_controller"),
)


@dataclass
class SwarmNode:
    name: str
    role: str
    state: str = "observer"
    timestamp: str = ""
    node_kind: str = "logical"  # "logical" | "hardware"
    homeworld_serial: Optional[str] = None

    def hello(self, *, festive: bool = False) -> str:
        base = f"[{self.name}] role={self.role} state={self.state} says: HELLO SWARM"
        if festive:
            return base + " 🌊🐜⚡"
        return base


class SwarmRegistry:
    def __init__(self) -> None:
        self.nodes: List[SwarmNode] = []

    def _index_by_name(self) -> Dict[str, int]:
        return {n.name: i for i, n in enumerate(self.nodes)}

    def register(self, node: SwarmNode) -> None:
        if not node.timestamp:
            node.timestamp = datetime.now(timezone.utc).isoformat()
        by = self._index_by_name()
        if node.name in by:
            self.nodes[by[node.name]] = node
        else:
            self.nodes.append(node)

    def broadcast(self) -> List[str]:
        return [n.hello() for n in self.nodes]

    def snapshot(self) -> List[Dict[str, Any]]:
        return [asdict(n) for n in self.nodes]

    def save(self, path: Optional[Path] = None) -> Path:
        out = path or _DEFAULT_STATE
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.snapshot(), indent=2), encoding="utf-8")
        return out


def load_registry(path: Optional[Path] = None) -> SwarmRegistry:
    p = path or _DEFAULT_STATE
    reg = SwarmRegistry()
    if not p.exists():
        return reg
    try:
        rows = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return reg
    if not isinstance(rows, list):
        return reg
    for row in rows:
        if not isinstance(row, dict) or "name" not in row or "role" not in row:
            continue
        reg.register(
            SwarmNode(
                name=str(row["name"]),
                role=str(row["role"]),
                state=str(row.get("state", "observer")),
                timestamp=str(row.get("timestamp", "")),
                node_kind=str(row.get("node_kind", "logical")),
                homeworld_serial=row.get("homeworld_serial"),
            )
        )
    return reg


def ensure_default_logical_nodes(
    registry: SwarmRegistry,
    defaults: Sequence[Tuple[str, str]] = _DEFAULT_NODES,
) -> None:
    existing = {n.name for n in registry.nodes}
    for name, role in defaults:
        if name not in existing:
            registry.register(SwarmNode(name=name, role=role))


def swarm_gpt_boot(
    *,
    state_path: Optional[Path] = None,
    festive: bool = False,
    trace_deposit: bool = False,
    source_ide: str = "cursor_m5",
    homeworld_serial: str = "GTH4921YP3",
) -> SwarmRegistry:
    """
    Load prior snapshot (if any), merge default logical nodes, save, optionally deposit.
    """
    from System.ide_stigmergic_bridge import deposit  # noqa: WPS433 — runtime import

    path = state_path or _DEFAULT_STATE
    registry = load_registry(path)
    ensure_default_logical_nodes(registry)
    registry.save(path)

    if trace_deposit:
        payload_lines = [n.hello(festive=festive) for n in registry.nodes]
        payload = "[swarm_boot] logical registry refreshed — " + "; ".join(payload_lines)
        deposit(source_ide, payload[:8000], kind="swarm_boot", homeworld_serial=homeworld_serial)

    if festive:
        print("\n".join(n.hello(festive=True) for n in registry.nodes))
    else:
        print("\n".join(registry.broadcast()))
    return registry


if __name__ == "__main__":
    print("=== SWARM BOOT SEQUENCE (local JSON + optional trace) ===")
    reg = swarm_gpt_boot(festive=True, trace_deposit=False)
    print("=== SWARM SNAPSHOT ===")
    print(json.dumps(reg.snapshot(), indent=2))
