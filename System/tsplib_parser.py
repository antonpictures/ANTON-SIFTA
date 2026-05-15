"""tsplib_parser.py — minimal TSPLIB95 EUC_2D reader for the TSP organ.

Truth label: ``SIFTA_TSP_DEMO_V1`` (same family as ``swarm_tsp_solver``).

Supports the common academic subset used by ``http://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/``:

  * ``NAME``, ``TYPE``, ``DIMENSION``, ``EDGE_WEIGHT_TYPE: EUC_2D``
  * ``NODE_COORD_SECTION`` … integer or float ``index x y`` rows
  * ``EOF`` (optional)

Does **not** implement full ATSP / GEO / EXPLICIT matrix families — extend
here when the Architect drops more instances under ``assets/tsplib/``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple


@dataclass(frozen=True)
class TsplibInstance:
    """One Euclidean 2D symmetric TSP instance."""

    name: str
    coords: List[Tuple[float, float]]
    labels: List[str]
    source_path: str | None


_SECTION = re.compile(r"^\s*([A-Z_]+)\s*:\s*(.*)$", re.I)


def parse_tsplib_tsp(text: str, *, source_path: str | None = None) -> TsplibInstance:
    """Parse TSPLIB ``.tsp`` body into floats suitable for ``solve_tsp``."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    name = "UNKNOWN"
    dimension: int | None = None
    edge_type = "EUC_2D"
    in_nodes = False
    raw_nodes: list[tuple[int, float, float]] = []

    for raw in lines:
        up = raw.upper()
        if up.startswith("NODE_COORD_SECTION"):
            in_nodes = True
            continue
        if up == "EOF" or up.startswith("DISPLAY_DATA_SECTION"):
            break
        if not in_nodes:
            m = _SECTION.match(raw)
            if m:
                key, val = m.group(1).upper(), m.group(2).strip()
                if key == "NAME":
                    name = val or name
                elif key == "TYPE" and val.upper() != "TSP":
                    raise ValueError(f"Unsupported TYPE {val!r} (only TSP supported)")
                elif key == "DIMENSION":
                    dimension = int(val.split()[0])
                elif key == "EDGE_WEIGHT_TYPE":
                    edge_type = val.upper()
            continue

        # coord line: index x y
        parts = raw.split()
        if len(parts) < 3:
            continue
        try:
            idx = int(parts[0])
            x, y = float(parts[1]), float(parts[2])
        except ValueError:
            continue
        raw_nodes.append((idx, x, y))

    if edge_type != "EUC_2D":
        raise ValueError(f"Unsupported EDGE_WEIGHT_TYPE {edge_type!r} (need EUC_2D)")

    raw_nodes.sort(key=lambda t: t[0])
    if dimension is not None and len(raw_nodes) != dimension:
        raise ValueError(
            f"DIMENSION={dimension} but read {len(raw_nodes)} NODE_COORD rows"
        )

    coords: List[Tuple[float, float]] = [(x, y) for _, x, y in raw_nodes]
    labels = [str(i) for i, _, _ in raw_nodes]
    if len(coords) < 1:
        raise ValueError("No NODE_COORD_SECTION data")

    return TsplibInstance(
        name=name or "UNKNOWN",
        coords=coords,
        labels=labels,
        source_path=source_path,
    )


def load_tsplib_path(path: Path) -> TsplibInstance:
    return parse_tsplib_tsp(path.read_text(encoding="utf-8"), source_path=str(path))


def coords_only(inst: TsplibInstance) -> Sequence[Tuple[float, float]]:
    return inst.coords
