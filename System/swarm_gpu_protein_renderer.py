"""GPU-ready molecular geometry and Qt/OpenGL renderer for SIFTA proteins.

The deterministic buffer helpers convert PDB text into compact, typed arrays
that the ``SwarmGPUProteinRenderer`` QOpenGLWidget can upload to the local
OpenGL/ModernGL context:

- sphere impostor instances for atoms
- cylinder/capsule impostor instances for bonds
- Catmull-Rom/parallel-transport ribbon tube geometry for CA backbones
- stigmergic bloom strength derived from local SIFTA ledgers

Truth label for exported buffers: GPU_READY_GEOMETRY. The widget is an
operational local renderer; visible-frame claims still require pixel/readback
tests at the UI layer.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

import time
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QSurfaceFormat

try:
    import moderngl
except ImportError:
    moderngl = None


SCHEMA_VERSION = "sifta_gpu_protein_renderer.geometry_v1"
TRUTH_LABEL = "GPU_READY_GEOMETRY"

# Approximate visual radii and covalent radii in Angstroms. Values are kept
# local so rendering remains deterministic even without an external chemistry
# package.
VDW_RADII: dict[str, float] = {
    "H": 1.20,
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "P": 1.80,
    "S": 1.80,
    "SE": 1.90,
}

COVALENT_RADII: dict[str, float] = {
    "H": 0.31,
    "C": 0.76,
    "N": 0.71,
    "O": 0.66,
    "P": 1.07,
    "S": 1.05,
    "SE": 1.20,
}

ELEMENT_COLORS: dict[str, tuple[float, float, float]] = {
    "H": (0.90, 0.92, 0.95),
    "C": (0.00, 1.00, 0.62),
    "N": (0.00, 0.68, 1.00),
    "O": (1.00, 0.20, 0.40),
    "P": (1.00, 0.70, 0.10),
    "S": (1.00, 0.84, 0.00),
    "SE": (0.95, 0.55, 0.10),
}

RIBBON_COLOR = (0.36, 1.00, 0.62)
BOND_RADIUS = 0.12
RIBBON_RADIUS = 0.20


@dataclass(frozen=True)
class AtomRecord:
    """Parsed PDB atom with enough metadata for chemistry and ribbons."""

    serial: int
    name: str
    residue_name: str
    chain_id: str
    residue_index: int
    element: str
    position: tuple[float, float, float]

    @property
    def is_ca(self) -> bool:
        return self.name.strip().upper() == "CA"


@dataclass(frozen=True)
class MoleculeBuffers:
    """Typed buffers ready for ModernGL upload."""

    atoms: tuple[AtomRecord, ...]
    bonds: tuple[tuple[int, int], ...]
    sphere_instances: np.ndarray
    cylinder_instances: np.ndarray
    backbone_points: np.ndarray
    ribbon_vertices: np.ndarray
    ribbon_indices: np.ndarray
    metadata: dict[str, object]


def _safe_int(value: str, default: int = 0) -> int:
    try:
        return int(value.strip())
    except ValueError:
        return default


def _safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value.strip())
    except ValueError:
        return default


def _infer_element(atom_name: str, element_hint: str = "") -> str:
    hint = element_hint.strip().upper()
    if hint:
        return hint
    cleaned = "".join(ch for ch in atom_name.strip().upper() if ch.isalpha())
    if cleaned.startswith("SE"):
        return "SE"
    if cleaned:
        return cleaned[0]
    return "C"


def parse_pdb_atoms(pdb_text: str) -> tuple[AtomRecord, ...]:
    """Parse ATOM/HETATM rows from PDB text.

    The parser follows fixed-width PDB columns but is intentionally tolerant of
    missing element fields because SIFTA's local toy folders emit compact PDB.
    """

    atoms: list[AtomRecord] = []
    for raw_line in pdb_text.splitlines():
        line = raw_line.rstrip("\n")
        if not (line.startswith("ATOM") or line.startswith("HETATM")):
            continue
        element_hint = line[76:78] if len(line) >= 78 else ""
        atom = AtomRecord(
            serial=_safe_int(line[6:11], len(atoms) + 1),
            name=line[12:16].strip() or "C",
            residue_name=line[17:20].strip() or "UNK",
            chain_id=(line[21:22].strip() or "A"),
            residue_index=_safe_int(line[22:26], len(atoms) + 1),
            element=_infer_element(line[12:16], element_hint),
            position=(
                _safe_float(line[30:38]),
                _safe_float(line[38:46]),
                _safe_float(line[46:54]),
            ),
        )
        atoms.append(atom)
    return tuple(atoms)


def parse_pdb_file(path: str | Path) -> tuple[AtomRecord, ...]:
    return parse_pdb_atoms(Path(path).read_text())


def _element_radius(element: str) -> float:
    return VDW_RADII.get(element.upper(), VDW_RADII["C"])


def _covalent_radius(element: str) -> float:
    return COVALENT_RADII.get(element.upper(), COVALENT_RADII["C"])


def _element_color(element: str) -> tuple[float, float, float]:
    return ELEMENT_COLORS.get(element.upper(), ELEMENT_COLORS["C"])


def _positions(atoms: Sequence[AtomRecord]) -> np.ndarray:
    if not atoms:
        return np.zeros((0, 3), dtype=np.float32)
    return np.asarray([atom.position for atom in atoms], dtype=np.float32)


def build_sphere_instance_buffer(atoms: Sequence[AtomRecord]) -> np.ndarray:
    """Return N x 7 float32 rows: center.xyz, radius, color.rgb."""

    rows: list[list[float]] = []
    for atom in atoms:
        color = _element_color(atom.element)
        rows.append([*atom.position, _element_radius(atom.element), *color])
    return np.asarray(rows, dtype=np.float32).reshape((len(rows), 7))


def infer_bonds(
    atoms: Sequence[AtomRecord],
    *,
    tolerance: float = 0.45,
    max_distance: float = 2.45,
    include_ca_backbone: bool = True,
) -> tuple[tuple[int, int], ...]:
    """Infer bonds with a small spatial hash plus CA-backbone fallback.

    PDB files from experimental sources often omit CONECT records for proteins.
    This keeps the renderer useful while avoiding an O(N^2) pass for larger
    structures.
    """

    if len(atoms) < 2:
        return tuple()

    positions = _positions(atoms)
    cell_size = max_distance
    cells: dict[tuple[int, int, int], list[int]] = {}
    for idx, pos in enumerate(positions):
        key = tuple(int(math.floor(float(coord) / cell_size)) for coord in pos)
        cells.setdefault(key, []).append(idx)

    bonds: set[tuple[int, int]] = set()
    for key, indices in cells.items():
        neighbor_keys = (
            (key[0] + dx, key[1] + dy, key[2] + dz)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            for dz in (-1, 0, 1)
        )
        for neighbor_key in neighbor_keys:
            for i in indices:
                for j in cells.get(neighbor_key, []):
                    if j <= i:
                        continue
                    distance = float(np.linalg.norm(positions[i] - positions[j]))
                    if distance < 0.40 or distance > max_distance:
                        continue
                    covalent_limit = (
                        _covalent_radius(atoms[i].element)
                        + _covalent_radius(atoms[j].element)
                        + tolerance
                    )
                    if distance <= covalent_limit:
                        bonds.add((i, j))

    if include_ca_backbone:
        ca_by_chain = _ca_indices_by_chain(atoms)
        for chain_indices in ca_by_chain.values():
            ordered = sorted(chain_indices, key=lambda idx: atoms[idx].residue_index)
            for left, right in zip(ordered, ordered[1:]):
                residue_gap = atoms[right].residue_index - atoms[left].residue_index
                distance = float(np.linalg.norm(positions[left] - positions[right]))
                if 0 < residue_gap <= 1 and distance <= 4.50:
                    bonds.add((min(left, right), max(left, right)))

    return tuple(sorted(bonds))


def _ca_indices_by_chain(atoms: Sequence[AtomRecord]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for idx, atom in enumerate(atoms):
        if atom.is_ca:
            result.setdefault(atom.chain_id, []).append(idx)
    return result


def build_cylinder_instance_buffer(
    atoms: Sequence[AtomRecord],
    bonds: Sequence[tuple[int, int]],
    *,
    radius: float = BOND_RADIUS,
) -> np.ndarray:
    """Return M x 13 float32 rows: start.xyz, end.xyz, radius, color_a.rgb, color_b.rgb."""

    rows: list[list[float]] = []
    for left, right in bonds:
        atom_a = atoms[left]
        atom_b = atoms[right]
        rows.append([
            *atom_a.position,
            *atom_b.position,
            radius,
            *_element_color(atom_a.element),
            *_element_color(atom_b.element),
        ])
    return np.asarray(rows, dtype=np.float32).reshape((len(rows), 13))


def extract_ca_backbone(atoms: Sequence[AtomRecord]) -> np.ndarray:
    ca_atoms = sorted(
        (atom for atom in atoms if atom.is_ca),
        key=lambda atom: (atom.chain_id, atom.residue_index),
    )
    return np.asarray([atom.position for atom in ca_atoms], dtype=np.float32).reshape((len(ca_atoms), 3))


def catmull_rom_spline(points: np.ndarray, samples_per_segment: int = 8) -> np.ndarray:
    """Sample a Catmull-Rom spline through backbone points."""

    points = np.asarray(points, dtype=np.float32).reshape((-1, 3))
    if len(points) < 2:
        return points.copy()

    samples = max(2, int(samples_per_segment))
    output: list[np.ndarray] = []
    for idx in range(len(points) - 1):
        p0 = points[max(idx - 1, 0)]
        p1 = points[idx]
        p2 = points[idx + 1]
        p3 = points[min(idx + 2, len(points) - 1)]
        for step in range(samples):
            t = step / float(samples)
            t2 = t * t
            t3 = t2 * t
            sample = 0.5 * (
                (2.0 * p1)
                + (-p0 + p2) * t
                + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
                + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
            )
            output.append(sample.astype(np.float32))
    output.append(points[-1])
    return np.asarray(output, dtype=np.float32)


def _normalize(vector: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm < 1e-7:
        return fallback.astype(np.float32)
    return (vector / norm).astype(np.float32)


def parallel_transport_frames(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return stable tangent, normal, binormal vectors for a curve."""

    points = np.asarray(points, dtype=np.float32).reshape((-1, 3))
    count = len(points)
    if count == 0:
        empty = np.zeros((0, 3), dtype=np.float32)
        return empty, empty, empty
    if count == 1:
        tangent = np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32)
        normal = np.asarray([[0.0, 1.0, 0.0]], dtype=np.float32)
        binormal = np.asarray([[0.0, 0.0, 1.0]], dtype=np.float32)
        return tangent, normal, binormal

    tangents: list[np.ndarray] = []
    for idx in range(count):
        if idx == 0:
            raw = points[1] - points[0]
        elif idx == count - 1:
            raw = points[-1] - points[-2]
        else:
            raw = points[idx + 1] - points[idx - 1]
        tangents.append(_normalize(raw, np.asarray([1.0, 0.0, 0.0], dtype=np.float32)))

    up = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
    if abs(float(np.dot(tangents[0], up))) > 0.90:
        up = np.asarray([0.0, 0.0, 1.0], dtype=np.float32)

    normals: list[np.ndarray] = []
    binormals: list[np.ndarray] = []
    first_binormal = _normalize(
        np.cross(tangents[0], up),
        np.asarray([0.0, 0.0, 1.0], dtype=np.float32),
    )
    first_normal = _normalize(np.cross(first_binormal, tangents[0]), up)
    normals.append(first_normal)
    binormals.append(first_binormal)

    for idx in range(1, count):
        previous_normal = normals[-1]
        tangent = tangents[idx]
        projected_normal = previous_normal - tangent * float(np.dot(previous_normal, tangent))
        normal = _normalize(projected_normal, first_normal)
        binormal = _normalize(np.cross(tangent, normal), first_binormal)
        normals.append(normal)
        binormals.append(binormal)

    return (
        np.asarray(tangents, dtype=np.float32),
        np.asarray(normals, dtype=np.float32),
        np.asarray(binormals, dtype=np.float32),
    )


def build_ribbon_tube_mesh(
    backbone_points: np.ndarray,
    *,
    samples_per_segment: int = 8,
    sides: int = 8,
    radius: float = RIBBON_RADIUS,
) -> tuple[np.ndarray, np.ndarray]:
    """Build a small tube mesh around the CA spline.

    Vertices are N x 9 float32 rows: position.xyz, normal.xyz, color.rgb.
    Indices are uint32 triangles.
    """

    backbone_points = np.asarray(backbone_points, dtype=np.float32).reshape((-1, 3))
    if len(backbone_points) < 2:
        return np.zeros((0, 9), dtype=np.float32), np.zeros((0,), dtype=np.uint32)

    centers = catmull_rom_spline(backbone_points, samples_per_segment=samples_per_segment)
    _tangents, normals, binormals = parallel_transport_frames(centers)
    ring_sides = max(3, int(sides))
    vertices: list[list[float]] = []
    indices: list[int] = []

    for ring_idx, center in enumerate(centers):
        for side in range(ring_sides):
            theta = (2.0 * math.pi * side) / ring_sides
            radial = math.cos(theta) * normals[ring_idx] + math.sin(theta) * binormals[ring_idx]
            point = center + radius * radial
            vertices.append([
                *point.tolist(),
                *_normalize(radial, normals[ring_idx]).tolist(),
                *RIBBON_COLOR,
            ])

    for ring_idx in range(len(centers) - 1):
        ring_a = ring_idx * ring_sides
        ring_b = (ring_idx + 1) * ring_sides
        for side in range(ring_sides):
            next_side = (side + 1) % ring_sides
            indices.extend([
                ring_a + side,
                ring_b + side,
                ring_a + next_side,
                ring_a + next_side,
                ring_b + side,
                ring_b + next_side,
            ])

    return np.asarray(vertices, dtype=np.float32), np.asarray(indices, dtype=np.uint32)


def build_molecule_buffers_from_pdb_text(
    pdb_text: str,
    *,
    samples_per_segment: int = 8,
    ribbon_sides: int = 8,
) -> MoleculeBuffers:
    atoms = parse_pdb_atoms(pdb_text)
    bonds = infer_bonds(atoms)
    backbone = extract_ca_backbone(atoms)
    ribbon_vertices, ribbon_indices = build_ribbon_tube_mesh(
        backbone,
        samples_per_segment=samples_per_segment,
        sides=ribbon_sides,
    )
    metadata: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "truth_label": TRUTH_LABEL,
        "atom_count": len(atoms),
        "bond_count": len(bonds),
        "ca_count": int(len(backbone)),
        "sphere_instance_columns": ["x", "y", "z", "radius", "r", "g", "b"],
        "cylinder_instance_columns": [
            "start_x",
            "start_y",
            "start_z",
            "end_x",
            "end_y",
            "end_z",
            "radius",
            "r_a",
            "g_a",
            "b_a",
            "r_b",
            "g_b",
            "b_b",
        ],
        "ribbon_vertex_columns": ["x", "y", "z", "nx", "ny", "nz", "r", "g", "b"],
    }
    return MoleculeBuffers(
        atoms=atoms,
        bonds=bonds,
        sphere_instances=build_sphere_instance_buffer(atoms),
        cylinder_instances=build_cylinder_instance_buffer(atoms, bonds),
        backbone_points=backbone,
        ribbon_vertices=ribbon_vertices,
        ribbon_indices=ribbon_indices,
        metadata=metadata,
    )


def build_molecule_buffers_from_pdb_file(path: str | Path, **kwargs: object) -> MoleculeBuffers:
    return build_molecule_buffers_from_pdb_text(Path(path).read_text(), **kwargs)


def bloom_strength_from_drive_rows(
    rows: Iterable[dict[str, object]],
    *,
    active_drive_domain: str = "",
    base_strength: float = 0.35,
) -> float:
    """Map SIFTA internal-drive/body-brain rows onto a bounded bloom scalar."""

    strength = float(base_strength)
    if active_drive_domain.strip().lower() == "biology":
        strength += 0.35

    max_td = 0.0
    biology_hits = 0
    for row in rows:
        domain = str(row.get("drive_domain") or row.get("domain") or row.get("topic") or "").lower()
        if domain == "biology":
            biology_hits += 1
        try:
            td_value = abs(float(row.get("td_value", row.get("value", 0.0))))
        except (TypeError, ValueError):
            td_value = 0.0
        max_td = max(max_td, td_value)

    strength += min(0.55, max_td * 0.25)
    strength += min(0.20, biology_hits * 0.05)
    return max(0.0, min(1.75, strength))


def read_recent_jsonl(path: str | Path, *, limit: int = 64) -> list[dict[str, object]]:
    source = Path(path)
    if not source.exists():
        return []
    lines = source.read_text().splitlines()[-max(1, int(limit)) :]
    rows: list[dict[str, object]] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def shader_sources() -> dict[str, str]:
    """Return GLSL 4.10 shader skeletons matching the buffer layout."""

    return {
        "sphere_vertex": """#version 410 core
in vec3 a_center;
in float a_radius;
in vec3 a_color;
out vec3 v_center;
out float v_radius;
out vec3 v_color;
void main() {
    v_center = a_center;
    v_radius = a_radius;
    v_color = a_color;
    gl_Position = vec4(a_center, 1.0);
}
""",
        "sphere_fragment": """#version 410 core
in vec3 v_center;
in float v_radius;
in vec3 v_color;
out vec4 frag_color;
void main() {
    vec3 normal = normalize(vec3(0.0, 0.0, 1.0));
    float diffuse = max(dot(normal, normalize(vec3(0.2, 0.5, 1.0))), 0.0);
    frag_color = vec4(v_color * (0.25 + diffuse), 1.0);
    gl_FragDepth = gl_FragCoord.z;
}
""",
        "cylinder_vertex": """#version 410 core
in vec3 a_start;
in vec3 a_end;
in float a_radius;
in vec3 a_color_a;
in vec3 a_color_b;
out vec3 v_start;
out vec3 v_end;
out float v_radius;
out vec3 v_color_a;
out vec3 v_color_b;
void main() {
    v_start = a_start;
    v_end = a_end;
    v_radius = a_radius;
    v_color_a = a_color_a;
    v_color_b = a_color_b;
    gl_Position = vec4(mix(a_start, a_end, 0.5), 1.0);
}
""",
        "tone_map_fragment": """#version 410 core
uniform sampler2D u_scene;
uniform sampler2D u_bloom;
uniform float u_bloom_strength;
out vec4 frag_color;
void main() {
    vec2 uv = gl_FragCoord.xy / vec2(textureSize(u_scene, 0));
    vec3 hdr = texture(u_scene, uv).rgb + texture(u_bloom, uv).rgb * u_bloom_strength;
    vec3 mapped = hdr / (hdr + vec3(1.0));
    frag_color = vec4(pow(mapped, vec3(1.0 / 2.2)), 1.0);
}
""",
    }


__all__ = [
    "AtomRecord",
    "MoleculeBuffers",
    "SCHEMA_VERSION",
    "TRUTH_LABEL",
    "bloom_strength_from_drive_rows",
    "build_cylinder_instance_buffer",
    "build_molecule_buffers_from_pdb_file",
    "build_molecule_buffers_from_pdb_text",
    "build_ribbon_tube_mesh",
    "build_sphere_instance_buffer",
    "catmull_rom_spline",
    "extract_ca_backbone",
    "infer_bonds",
    "parallel_transport_frames",
    "parse_pdb_atoms",
    "parse_pdb_file",
    "read_recent_jsonl",
    "shader_sources",
    "SwarmGPUProteinRenderer",
]


class SwarmGPUProteinRenderer(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        fmt = QSurfaceFormat()
        fmt.setVersion(4, 1)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setSamples(4)
        self.setFormat(fmt)
        
        self.ctx = None
        self.buffers = None
        
        self.vbo_spheres = None
        self.vbo_cylinders = None
        self.vbo_ribbon = None
        self.ibo_ribbon = None
        
        self.vao_spheres = None
        self.vao_cylinders = None
        self.vao_ribbon = None
        
        self.prog_spheres = None
        self.prog_cylinders = None
        self.prog_ribbon = None
        
        self._azimuth = 0.0
        self._elevation = 0.0
        self._zoom = 1.0
        self._bloom_strength = 0.35
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60 FPS
        self._start_time = time.time()
        
    def set_molecule(self, buffers):
        self.buffers = buffers
        if self.ctx is not None:
            self._upload_buffers()
            self.update()
            
    def set_camera(self, azimuth, elevation, zoom=1.0):
        self._azimuth = azimuth
        self._elevation = elevation
        self._zoom = zoom
        self.update()
        
    def _tick(self):
        # Read stigmergic ledgers for bloom (same module — avoid self-import).
        try:
            bb_rows = read_recent_jsonl(".sifta_state/body_brain_memory.jsonl", limit=5)
            self._bloom_strength = bloom_strength_from_drive_rows(bb_rows, base_strength=0.2)
        except Exception:
            pass
        self.update()

    def initializeGL(self):
        if moderngl is None:
            return
        self.ctx = moderngl.create_context()
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE | moderngl.BLEND)
        
        # Simple shaders for now to satisfy the geometry
        sphere_vs = '''#version 410 core
        in vec3 a_center;
        in float a_radius;
        in vec3 a_color;
        
        uniform mat4 u_mvp;
        
        out vec3 v_center;
        out float v_radius;
        out vec3 v_color;
        
        void main() {
            v_center = a_center;
            v_radius = a_radius;
            v_color = a_color;
            gl_Position = u_mvp * vec4(a_center, 1.0);
            gl_PointSize = max(1.0, 500.0 * a_radius / gl_Position.w);
        }
        '''
        
        sphere_fs = '''#version 410 core
        in vec3 v_center;
        in float v_radius;
        in vec3 v_color;
        
        out vec4 frag_color;
        
        void main() {
            vec2 coord = gl_PointCoord * 2.0 - 1.0;
            float r2 = dot(coord, coord);
            if (r2 > 1.0) discard;
            float z = sqrt(1.0 - r2);
            vec3 normal = vec3(coord.x, -coord.y, z);
            
            vec3 light_dir = normalize(vec3(1.0, 1.0, 1.0));
            float diffuse = max(dot(normal, light_dir), 0.0);
            float ambient = 0.3;
            
            frag_color = vec4(v_color * (ambient + diffuse * 0.7), 1.0);
            
            // Depth correction
            float depth = gl_FragCoord.z; // simplified
            gl_FragDepth = depth;
        }
        '''
        
        cylinder_vs = '''#version 410 core
        in vec3 a_start;
        in vec3 a_end;
        in float a_radius;
        in vec3 a_color_a;
        in vec3 a_color_b;
        
        uniform mat4 u_mvp;
        
        out vec3 v_color;
        
        void main() {
            v_color = mix(a_color_a, a_color_b, 0.5);
            gl_Position = u_mvp * vec4(mix(a_start, a_end, 0.5), 1.0);
            gl_PointSize = max(1.0, 200.0 * a_radius / gl_Position.w);
        }
        '''
        
        cylinder_fs = '''#version 410 core
        in vec3 v_color;
        out vec4 frag_color;
        void main() {
            vec2 coord = gl_PointCoord * 2.0 - 1.0;
            float r2 = dot(coord, coord);
            if (r2 > 1.0) discard;
            frag_color = vec4(v_color, 1.0);
        }
        '''
        
        ribbon_vs = '''#version 410 core
        in vec3 a_pos;
        in vec3 a_norm;
        in vec3 a_color;
        
        uniform mat4 u_mvp;
        
        out vec3 v_norm;
        out vec3 v_color;
        
        void main() {
            v_norm = a_norm;
            v_color = a_color;
            gl_Position = u_mvp * vec4(a_pos, 1.0);
        }
        '''
        
        ribbon_fs = '''#version 410 core
        in vec3 v_norm;
        in vec3 v_color;
        out vec4 frag_color;
        void main() {
            vec3 light_dir = normalize(vec3(1.0, 1.0, 1.0));
            float diffuse = max(dot(normalize(v_norm), light_dir), 0.0);
            frag_color = vec4(v_color * (0.3 + diffuse * 0.7), 1.0);
        }
        '''
        
        self.prog_spheres = self.ctx.program(vertex_shader=sphere_vs, fragment_shader=sphere_fs)
        self.prog_cylinders = self.ctx.program(vertex_shader=cylinder_vs, fragment_shader=cylinder_fs)
        self.prog_ribbon = self.ctx.program(vertex_shader=ribbon_vs, fragment_shader=ribbon_fs)
        
        if self.buffers:
            self._upload_buffers()

    def _upload_buffers(self):
        if not self.ctx or not self.buffers:
            return
            
        if self.vbo_spheres: self.vbo_spheres.release()
        if self.vbo_cylinders: self.vbo_cylinders.release()
        if self.vbo_ribbon: self.vbo_ribbon.release()
        if self.ibo_ribbon: self.ibo_ribbon.release()
        
        if self.vao_spheres: self.vao_spheres.release()
        if self.vao_cylinders: self.vao_cylinders.release()
        if self.vao_ribbon: self.vao_ribbon.release()
        
        self.vbo_spheres = self.ctx.buffer(self.buffers.sphere_instances.tobytes())
        self.vao_spheres = self.ctx.vertex_array(self.prog_spheres, [
            (self.vbo_spheres, '3f 1f 3f', 'a_center', 'a_radius', 'a_color')
        ])
        
        self.vbo_cylinders = self.ctx.buffer(self.buffers.cylinder_instances.tobytes())
        self.vao_cylinders = self.ctx.vertex_array(self.prog_cylinders, [
            (self.vbo_cylinders, '3f 3f 1f 3f 3f', 'a_start', 'a_end', 'a_radius', 'a_color_a', 'a_color_b')
        ])
        
        if len(self.buffers.ribbon_vertices) > 0:
            self.vbo_ribbon = self.ctx.buffer(self.buffers.ribbon_vertices.tobytes())
            self.ibo_ribbon = self.ctx.buffer(self.buffers.ribbon_indices.tobytes())
            self.vao_ribbon = self.ctx.vertex_array(self.prog_ribbon, [
                (self.vbo_ribbon, '3f 3f 3f', 'a_pos', 'a_norm', 'a_color')
            ], index_buffer=self.ibo_ribbon)
        else:
            self.vao_ribbon = None


    def paintGL(self):
        if not self.ctx: return
            
        if not hasattr(self, 'fbo') or getattr(self, 'fbo', None) is None:
            # Create FBO
            self.fbo_color = self.ctx.texture((self.width(), self.height()), 4)
            self.fbo_depth = self.ctx.depth_texture((self.width(), self.height()))
            self.fbo = self.ctx.framebuffer(color_attachments=[self.fbo_color], depth_attachment=self.fbo_depth)
            
            # Post-process quad
            self.quad_vbo = self.ctx.buffer(np.array([
                -1.0, -1.0, 0.0, 0.0,
                 1.0, -1.0, 1.0, 0.0,
                -1.0,  1.0, 0.0, 1.0,
                 1.0,  1.0, 1.0, 1.0,
            ], dtype='f4'))
            
            self.prog_post = self.ctx.program(
                vertex_shader='''#version 410 core
                in vec2 a_pos;
                in vec2 a_uv;
                out vec2 v_uv;
                void main() {
                    v_uv = a_uv;
                    gl_Position = vec4(a_pos, 0.0, 1.0);
                }''',
                fragment_shader='''#version 410 core
                uniform sampler2D u_tex;
                uniform float u_bloom;
                in vec2 v_uv;
                out vec4 frag_color;
                void main() {
                    vec4 color = texture(u_tex, v_uv);
                    // simple fake bloom threshold
                    float brightness = dot(color.rgb, vec3(0.2126, 0.7152, 0.0722));
                    vec3 bloom = color.rgb * max(0.0, brightness - 0.5) * u_bloom * 2.0;
                    
                    // simple screen-space vignette (fake SSAO/depth)
                    float dist = distance(v_uv, vec2(0.5));
                    float vignette = smoothstep(0.8, 0.2, dist);
                    
                    vec3 hdr = (color.rgb + bloom) * vignette;
                    // tone map
                    vec3 mapped = hdr / (hdr + vec3(1.0));
                    frag_color = vec4(pow(mapped, vec3(1.0 / 2.2)), color.a);
                }'''
            )
            self.quad_vao = self.ctx.vertex_array(self.prog_post, [(self.quad_vbo, '2f 2f', 'a_pos', 'a_uv')])

        self.fbo.use()
        self.ctx.clear(0.01, 0.02, 0.06, 1.0)
        
        if not self.buffers:
            self.ctx.screen.use()
            self.ctx.clear(0.01, 0.02, 0.06, 1.0)
            return
            
        width = self.width()
        height = self.height()
        aspect = width / max(1.0, height)
        fov = 45.0 * np.pi / 180.0
        f = 1.0 / np.tan(fov / 2.0)
        zNear, zFar = 0.1, 1000.0
        proj = np.array([
            [f/aspect, 0, 0, 0],
            [0, f, 0, 0],
            [0, 0, (zFar+zNear)/(zNear-zFar), -1],
            [0, 0, (2*zFar*zNear)/(zNear-zFar), 0]
        ], dtype=np.float32)
        
        az, el = np.radians(self._azimuth), np.radians(self._elevation)
        rx = np.array([[1,0,0,0], [0,np.cos(el),-np.sin(el),0], [0,np.sin(el),np.cos(el),0], [0,0,0,1]], dtype=np.float32)
        ry = np.array([[np.cos(az),0,np.sin(az),0], [0,1,0,0], [-np.sin(az),0,np.cos(az),0], [0,0,0,1]], dtype=np.float32)
        
        center = np.mean([a.position for a in self.buffers.atoms], axis=0) if len(self.buffers.atoms) > 0 else np.zeros(3)
        view = np.identity(4, dtype=np.float32)
        view[3, 2] = -50.0 / self._zoom
        model = np.identity(4, dtype=np.float32)
        model[3, :3] = -center
        
        mvp = model @ ry @ rx @ view @ proj
        mvp_bytes = mvp.tobytes()
        
        self.ctx.enable(moderngl.PROGRAM_POINT_SIZE)
        if self.vao_ribbon:
            self.prog_ribbon['u_mvp'].write(mvp_bytes)
            self.vao_ribbon.render(moderngl.TRIANGLES)
        if self.vao_cylinders and len(self.buffers.bonds) > 0:
            self.prog_cylinders['u_mvp'].write(mvp_bytes)
            self.vao_cylinders.render(moderngl.POINTS)
        if self.vao_spheres and len(self.buffers.atoms) > 0:
            self.prog_spheres['u_mvp'].write(mvp_bytes)
            self.vao_spheres.render(moderngl.POINTS)
            
        self.ctx.screen.use()
        self.fbo_color.use(0)
        self.prog_post['u_tex'].value = 0
        self.prog_post['u_bloom'].value = float(self._bloom_strength)
        self.quad_vao.render(moderngl.TRIANGLE_STRIP)
        self.ctx.finish()

    def resizeGL(self, w, h):
        if self.ctx:
            self.ctx.viewport = (0, 0, w, h)
        fbo = getattr(self, "fbo", None)
        if fbo is not None:
            fbo.release()
            self.fbo_color.release()
            self.fbo_depth.release()
            self.fbo = None  # Recreated on next paintGL

