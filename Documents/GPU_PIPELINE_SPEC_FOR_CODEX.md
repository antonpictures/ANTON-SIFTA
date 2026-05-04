# SIFTA GPU Molecular Visualization Pipeline
## Specification for Dr. Codex (GPT-5.5 Extra High)
### Authored by: AG31 | Event 90+ | 2026-05-01

---

## ⚡ MANDATE

**No matplotlib. No web. No Three.js. No browser.**

Pure Python → GPU. Every pixel computed on Apple Silicon GPU.

The organism has eyes. They should render like a god.

---

## 🎯 THE GAP (What Does Not Exist)

VMD exists (C++ / CUDA). PyMOL exists (C++ core). Nothing exists that is:
1. Pure Python-native (no compiled C extension, no browser)
2. OpenGL 4.1 core profile (Apple Silicon compatible)
3. ModernGL + PyQt6 + QOpenGLWidget
4. Stigmergy-aware (reads live from `.sifta_state/` JSONL ledgers)
5. Biologically real rendering (sphere impostors + cylinder impostors + ribbon)

**We are building the first pure-Python stigmergic molecular GPU renderer.**

---

## 🔬 RESEARCH SPINE (DOI-LOCKED)

| Technique | Paper | Source |
|---|---|---|
| Sphere Impostors | Sigg, C. et al. "Signed Distance Transform using Graphics Hardware" IEEE 2003 | GPU sphere billboard ray-casting foundation |
| Cylinder Impostors | Kozlikova, B. "Visualization of Protein Structures" IEEE TVCG 2015 | Capsule ray-casting for bonds |
| SSAO (Ambient Occlusion) | Mittring, M. "Finding Next Gen" SIGGRAPH 2007 | Screen-space AO pass |
| Ribbon/Tube Rendering | Carson, M. "Ribbon Models for Protein 3D Structure" J. Appl. Cryst. 1987 | Protein ribbon math foundation |
| GPU Instancing | LearnOpenGL.com Instancing chapter | GL_DRAW_ARRAYS_INSTANCED |
| ModernGL Python | moderngl/moderngl GitHub | Python OpenGL 3.3+ wrapper |
| VMD GPU Pipeline | Stone et al. IEEE IPDPSW 2016 "High Performance Molecular Visualization" | Architecture reference |
| Apple Metal/OpenGL | Apple Developer: OpenGL ES Programming Guide | macOS 14+ compat |

---

## 🏗️ ARCHITECTURE: `System/swarm_gpu_protein_renderer.py`

### Codex Pass 1 — Landed Truth Boundary

`System/swarm_gpu_protein_renderer.py` now exists as the tested
GPU-ready geometry/buffer organ. It does **not** yet claim a live
`QOpenGLWidget` context or measured FPS. The landed code parses PDB,
infers bonds, extracts Cα backbones, builds Catmull-Rom ribbon tubes,
emits `float32` sphere/cylinder instance buffers, emits `uint32` ribbon
indices, returns OpenGL 4.1 shader sources, and maps SIFTA biology drive
rows into a bounded bloom scalar.

Truth label: `GPU_READY_GEOMETRY`, not `FULL_RENDERER`.

### Stack
```
PyQt6 QOpenGLWidget
  └── ModernGL Context (OpenGL 4.1 core — Apple Silicon compatible)
        ├── PASS 0: Geometry — Sphere Impostors (atoms)
        ├── PASS 1: Geometry — Cylinder Impostors (bonds)  
        ├── PASS 2: Ribbon Tube (backbone B-spline)
        ├── PASS 3: SSAO (Screen Space Ambient Occlusion)
        ├── PASS 4: Bloom / HDR (Gaussian blur on bright pixels)
        └── PASS 5: Composite + Tone Map → screen
```

---

## 📐 PASS 0: SPHERE IMPOSTORS

**The key idea:** For every atom, draw ONE QUAD (2 triangles = 6 verts).
The fragment shader ray-casts the sphere mathematically.
This means 10,000 atoms = 10,000 quads, not 10M polygons.

### Vertex Shader Inputs (per instance)
```glsl
in vec3 a_center;    // atom center (world space)
in float a_radius;   // VDW radius (Angstrom)
in vec3 a_color;     // physicochemical color
```

### Vertex Shader
```glsl
// Expand point to camera-facing quad in view space
// Pass center + radius to fragment shader
```

### Fragment Shader Core
```glsl
// Ray from camera origin through fragment pixel
// Solve: |ray_origin + t*ray_dir - sphere_center|^2 = r^2
// If discriminant < 0: discard
// Else: normal = (hit_point - center) / r
// Phong + Schlick-Fresnel specular
// Write gl_FragDepth for correct Z-fighting
```

### Python CPU side
```python
# Upload per-atom data as instance buffer
ctx.buffer(np.column_stack([positions, radii, colors]).astype('f4'))
program = ctx.program(vertex_shader=VS, fragment_shader=FS)
vao = ctx.vertex_array(program, [(buf, '3f 1f 3f /i', 'a_center', 'a_radius', 'a_color')])
vao.render(moderngl.TRIANGLE_STRIP, instances=n_atoms)
```

---

## 📐 PASS 1: CYLINDER IMPOSTORS (bonds)

Same doctrine as sphere impostors but for bond sticks.

### Key math
```
Capsule ray-cast (two spherical endcaps + finite cylinder body)
Ray-cylinder intersection: solve quadratic in the XY plane of the cylinder's local frame
```

### Instance data per bond
```
start_pos (vec3), end_pos (vec3), radius (float), color_a (vec3), color_b (vec3)
```

---

## 📐 PASS 2: RIBBON / TUBE BACKBONE

### Algorithm (Frenet-Serret frame)
1. CPU: compute Cα positions from PDB / trajectory JSONL
2. CPU: compute Catmull-Rom spline through Cα positions (100 pts per segment)
3. CPU: compute Frenet frame at each spline point (tangent, normal, binormal)
4. GPU: vertex shader receives spline point + frame, extrudes a 8-vertex circle cross-section
5. GPU: connect adjacent circles with TRIANGLE_STRIP quads
6. Fragment: color by secondary structure (helix=red, sheet=yellow, loop=green)

### Key math (Frenet)
```python
T = normalize(dP/ds)           # tangent
N = normalize(dT/ds)           # normal (curvature direction)
B = cross(T, N)                # binormal
```

### GPU Upload
```python
# Per-spline-point: position (3f) + tangent (3f) + normal (3f) + binormal (3f) + t_color (3f)
# 8-vertex circle template in VBO
# Instanced: one instance per spline point
```

---

## 📐 PASS 3: SSAO (Screen Space Ambient Occlusion)

### GBuffer (offscreen framebuffer)
- Color attachment 0: albedo + alpha
- Color attachment 1: view-space normals
- Color attachment 2: view-space positions (or linearized depth)

### SSAO Fragment Shader
```glsl
// Sample hemisphere of 64 random directions in view space
// For each sample: check if it's occluded by geometry in the depth buffer
// Average occlusion → darken ambient term
// Bilateral blur to smooth the result
```

---

## 📐 PASS 4: BLOOM (HDR Glow)

```
1. Threshold pass: extract pixels brighter than 0.8
2. Gaussian blur pass (2-pass separable: horizontal then vertical)
3. Additive blend: final = base + blur * bloom_strength
```

---

## 📐 PASS 5: TONE MAP + COMPOSITE

```glsl
// Reinhard tone mapping: color = color / (color + 1.0)
// Gamma correction: pow(color, 1.0/2.2)
```

---

## 🧬 SIFTA INTEGRATION (Stigmergic Binding)

The renderer is NOT standalone. It reads LIVE from ledgers:

```python
# swarm_gpu_protein_renderer.py reads:
# .sifta_state/protein_folds/{pdb_name}.pdb → geometry
# .sifta_state/alice_internal_drives.jsonl → highlight active drive domain on structure
# .sifta_state/body_brain_memory.jsonl → pulse atom glow with body-brain value signal
# .sifta_state/stigmergic_video_resolution.jsonl → modulate salience grid overlay

# When alice drive = "biology" → protein viewer glows brighter
# When body_brain td_value spikes → bloom intensity spikes
```

---

## 📦 DEPENDENCIES (pip install)

```
moderngl          # Python OpenGL 4.1 wrapper (no C extension needed)
numpy             # array math
PyQt6             # window + QOpenGLWidget
PyQt6-Qt6         # Qt6 runtime
moderngl-window   # optional: standalone moderngl window helper
```

**Apple Silicon note:** OpenGL 4.1 is the max on macOS (Apple deprecated OpenGL).
All shaders must target `#version 410 core`.
ModernGL creates the context via `moderngl.create_context()` inside `initializeGL()`.

---

## 🎨 COLOR SCHEME (Physicochemical)

| Residue class | Amino acids | Color |
|---|---|---|
| Hydrophobic | A I L M F W V | `#00ff9f` (green) |
| Polar | S T N Q Y C | `#00f5ff` (cyan) |
| Negative charge | D E | `#ff3366` (red) |
| Positive charge | K R H | `#ffd700` (amber) |
| Special | G P | `#ff00cc` (magenta) |
| N-terminus | first atom | `#00cfff` (blue, large) |
| C-terminus | last atom | `#ff00cc` (magenta, large) |

Secondary structure ribbon colors:
- α-helix: `#ff4466` (red)  
- β-sheet: `#ffe066` (yellow)
- Loop/coil: `#5cff9d` (green)

---

## 📁 TARGET FILE

```
System/swarm_gpu_protein_renderer.py
```

Class: `SwarmGPUProteinRenderer(QOpenGLWidget)`

Integration point: `Applications/sifta_protein_folder_widget.py`
Replace `FigureCanvas` with `SwarmGPUProteinRenderer`.

---

## ✅ ACCEPTANCE CRITERIA

Codex, the build is done when:
1. `py_compile` passes
2. `pytest tests/test_swarm_gpu_protein_renderer.py` passes (headless with `QOffscreenSurface`)
3. Renders Villin HP35 (35 residues) at >30fps on M5 Apple Silicon
4. Auto-rotation works independently of animation
5. SSAO makes the protein look volumetric (not flat)
6. Bloom glows on high-energy atoms
7. Reads live trajectory from `.sifta_state/protein_folds/*.pdb`

---

## ⚖️ COVENANT COMPLIANCE

- NPPL: no military/surveillance use
- No network calls from renderer
- No browser escape (QOpenGLWidget is the cage)
- Stigmergic ledger writes use `append_line_locked`
- All shaders are inline GLSL strings (no external `.glsl` files that gitignore could eat)

---

*For the Swarm. 🐜⚡ — AG31*
