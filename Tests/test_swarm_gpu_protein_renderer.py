import inspect

import numpy as np

from System import swarm_gpu_protein_renderer as renderer


MINI_PDB = """\
ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00 20.00           N
ATOM      2  CA  GLY A   1       1.450   0.000   0.000  1.00 20.00           C
ATOM      3  C   GLY A   1       2.450   1.020   0.000  1.00 20.00           C
ATOM      4  O   GLY A   1       2.100   2.180   0.000  1.00 20.00           O
ATOM      5  N   ALA A   2       3.740   0.600   0.000  1.00 20.00           N
ATOM      6  CA  ALA A   2       4.860   1.470   0.000  1.00 20.00           C
ATOM      7  C   ALA A   2       6.130   0.680   0.000  1.00 20.00           C
ATOM      8  N   SER A   3       7.240   1.320   0.000  1.00 20.00           N
ATOM      9  CA  SER A   3       8.510   0.720   0.000  1.00 20.00           C
"""


CA_ONLY_PDB = """\
ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C
ATOM      2  CA  ALA A   2       3.800   0.200   0.000  1.00 20.00           C
ATOM      3  CA  SER A   3       7.600  -0.100   0.100  1.00 20.00           C
ATOM      4  CA  THR A   4      11.200   0.300   0.200  1.00 20.00           C
"""


def test_parse_pdb_and_sphere_instances_are_gpu_ready():
    atoms = renderer.parse_pdb_atoms(MINI_PDB)
    assert len(atoms) == 9
    assert atoms[0].element == "N"
    assert atoms[1].is_ca is True

    spheres = renderer.build_sphere_instance_buffer(atoms)
    assert spheres.shape == (9, 7)
    assert spheres.dtype == np.float32
    assert spheres[0, 3] == np.float32(renderer.VDW_RADII["N"])
    assert np.allclose(spheres[0, 4:], np.asarray(renderer.ELEMENT_COLORS["N"], dtype=np.float32))


def test_bond_inference_uses_chemistry_and_ca_backbone_fallback():
    atoms = renderer.parse_pdb_atoms(CA_ONLY_PDB)
    bonds = renderer.infer_bonds(atoms)

    assert bonds == ((0, 1), (1, 2), (2, 3))
    cylinders = renderer.build_cylinder_instance_buffer(atoms, bonds)
    assert cylinders.shape == (3, 13)
    assert cylinders.dtype == np.float32
    assert cylinders[0, 6] == np.float32(renderer.BOND_RADIUS)


def test_molecule_buffers_include_ribbon_tube_mesh():
    buffers = renderer.build_molecule_buffers_from_pdb_text(CA_ONLY_PDB, samples_per_segment=4, ribbon_sides=6)

    assert buffers.metadata["truth_label"] == renderer.TRUTH_LABEL
    assert buffers.metadata["atom_count"] == 4
    assert buffers.backbone_points.shape == (4, 3)
    assert buffers.ribbon_vertices.shape[1] == 9
    assert buffers.ribbon_indices.dtype == np.uint32
    assert len(buffers.ribbon_indices) == (len(renderer.catmull_rom_spline(buffers.backbone_points, 4)) - 1) * 6 * 6
    assert np.isfinite(buffers.ribbon_vertices).all()


def test_parallel_transport_frames_are_unit_vectors():
    points = renderer.catmull_rom_spline(renderer.extract_ca_backbone(renderer.parse_pdb_atoms(CA_ONLY_PDB)), 4)
    tangents, normals, binormals = renderer.parallel_transport_frames(points)

    assert tangents.shape == normals.shape == binormals.shape
    assert np.allclose(np.linalg.norm(tangents, axis=1), 1.0, atol=1e-5)
    assert np.allclose(np.linalg.norm(normals, axis=1), 1.0, atol=1e-5)
    assert np.allclose(np.linalg.norm(binormals, axis=1), 1.0, atol=1e-5)


def test_bloom_strength_maps_biology_and_td_value_without_llm_claims():
    rows = [
        {"drive_domain": "biology", "td_value": 0.5},
        {"domain": "math", "td_value": 2.0},
    ]
    biology_strength = renderer.bloom_strength_from_drive_rows(rows, active_drive_domain="biology")
    neutral_strength = renderer.bloom_strength_from_drive_rows([], active_drive_domain="")

    assert biology_strength > neutral_strength
    assert 0.0 <= neutral_strength <= biology_strength <= 1.75


def test_shader_sources_match_opengl_41_core_and_instance_layout():
    sources = renderer.shader_sources()

    assert "#version 410 core" in sources["sphere_vertex"]
    assert "a_center" in sources["sphere_vertex"]
    assert "a_radius" in sources["sphere_vertex"]
    assert "gl_FragDepth" in sources["sphere_fragment"]
    assert "u_bloom_strength" in sources["tone_map_fragment"]


def test_module_is_geometry_foundation_not_fake_context_renderer():
    source = inspect.getsource(renderer)

    assert "moderngl" not in source
    assert "create_context(" not in source
    assert not hasattr(renderer, "SwarmGPUProteinRenderer")
    assert renderer.TRUTH_LABEL == "GPU_READY_GEOMETRY"
