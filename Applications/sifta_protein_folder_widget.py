#!/usr/bin/env python3
"""
Applications/sifta_protein_folder_widget.py
A SIFTA OS widget to visually demonstrate the peptide folding engine.
It generates a 3D animated HTML visualization with glassmorphism UI and particle effects.
"""

import sys
import json
import os
import argparse
import webbrowser
from pathlib import Path
import numpy as np

# Add project root to path
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.sifta_peptide_backbone_demo import fold, AA
except ImportError:
    print("Error: Could not import System.sifta_peptide_backbone_demo")
    sys.exit(1)

def build_html_viewer(
    seq: str,
    trajectory: list,
    final_e: float,
    output_path: Path,
    *,
    title: str = "SIFTA Protein Folder",
    event_label: str = "Event 78 Vanguard",
    engine_label: str = "toy_CA_backbone_monte_carlo",
    signature_line: str = "SIFTA folding engine",
):
    # Prepare data for JS
    js_traj = json.dumps(trajectory)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            margin: 0;
            overflow: hidden;
            background-color: #050505;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #fff;
        }}
        #canvas-container {{
            width: 100vw;
            height: 100vh;
            position: absolute;
            top: 0;
            left: 0;
            z-index: 1;
        }}
        .ui-overlay {{
            position: absolute;
            top: 30px;
            left: 30px;
            z-index: 10;
            background: rgba(20, 20, 25, 0.6);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 24px;
            width: 320px;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
            transition: all 0.3s ease;
        }}
        .ui-overlay:hover {{
            background: rgba(30, 30, 35, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}
        h1 {{
            margin: 0 0 8px 0;
            font-size: 20px;
            font-weight: 600;
            background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 0.5px;
        }}
        h2 {{
            margin: 0 0 16px 0;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: #888;
            font-weight: 500;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .metric:last-child {{
            margin-bottom: 0;
            padding-bottom: 0;
            border-bottom: none;
        }}
        .label {{
            color: #aaa;
            font-size: 13px;
        }}
        .value {{
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
            font-size: 14px;
            font-weight: 600;
            color: #4facfe;
        }}
        .seq-container {{
            word-wrap: break-word;
            font-family: "SFMono-Regular", Consolas, monospace;
            font-size: 12px;
            color: #00f2fe;
            margin-top: 4px;
            line-height: 1.5;
            letter-spacing: 1px;
        }}
        
        .controls {{
            margin-top: 20px;
            display: flex;
            gap: 10px;
        }}
        button {{
            flex: 1;
            background: rgba(79, 172, 254, 0.1);
            border: 1px solid rgba(79, 172, 254, 0.3);
            color: #4facfe;
            padding: 8px 12px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-size: 12px;
            transition: all 0.2s;
        }}
        button:hover {{
            background: rgba(79, 172, 254, 0.2);
            box-shadow: 0 0 15px rgba(79, 172, 254, 0.4);
        }}
        
        .paper-cite {{
            position: absolute;
            bottom: 30px;
            right: 30px;
            z-index: 10;
            font-size: 11px;
            color: rgba(255,255,255,0.4);
            text-align: right;
            line-height: 1.6;
        }}
        .paper-cite strong {{
            color: rgba(255,255,255,0.6);
        }}
    </style>
    <!-- Use Three.js from CDN -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
    <div id="canvas-container"></div>
    
    <div class="ui-overlay">
        <h1>{title}</h1>
        <h2>{event_label}</h2>
        
        <div class="metric">
            <span class="label">Sequence</span>
        </div>
        <div class="seq-container">{seq}</div>
        
        <div style="height: 16px;"></div>
        
        <div class="metric">
            <span class="label">Residues</span>
            <span class="value">{len(seq)}</span>
        </div>

        <div class="metric">
            <span class="label">Engine</span>
            <span class="value">{engine_label}</span>
        </div>
        
        <div class="metric">
            <span class="label">Energy State</span>
            <span class="value" id="energy-val">Folding...</span>
        </div>
        
        <div class="metric">
            <span class="label">Step</span>
            <span class="value" id="step-val">0</span>
        </div>
        
        <div class="controls">
            <button id="btn-replay">Replay Fold</button>
            <button id="btn-auto">Auto-Rotate</button>
        </div>
    </div>
    
    <div class="paper-cite">
        <strong>{signature_line}</strong><br>
        <strong>Thermodynamic Hypothesis</strong><br>
        Anfinsen (1973) Science 181:223<br>
        <strong>HP lattice abstraction</strong><br>
        Dill (1985) Biochemistry 24:1501<br>
        <strong>Modern neural predictor comparison</strong><br>
        Jumper et al. (2021) Nature 596:583
    </div>

    <script>
        const trajectory = {js_traj};
        const finalEnergy = {final_e};
        
        // Scene Setup
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x050505, 0.02);
        
        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.set(0, 0, 40);
        
        const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        document.getElementById('canvas-container').appendChild(renderer.domElement);
        
        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.autoRotate = true;
        controls.autoRotateSpeed = 2.0;
        
        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
        scene.add(ambientLight);
        
        const dirLight1 = new THREE.DirectionalLight(0x00f2fe, 1.5);
        dirLight1.position.set(10, 20, 10);
        scene.add(dirLight1);
        
        const dirLight2 = new THREE.DirectionalLight(0x4facfe, 1.0);
        dirLight2.position.set(-10, -20, -10);
        scene.add(dirLight2);
        
        // Materials
        // Atoms
        const atomGeometry = new THREE.SphereGeometry(0.8, 32, 32);
        const atomMaterial = new THREE.MeshPhysicalMaterial({{
            color: 0x00f2fe,
            metalness: 0.2,
            roughness: 0.2,
            clearcoat: 1.0,
            clearcoatRoughness: 0.1,
            emissive: 0x004488,
            emissiveIntensity: 0.4
        }});
        
        // Bonds
        const bondMaterial = new THREE.MeshPhysicalMaterial({{
            color: 0xffffff,
            metalness: 0.5,
            roughness: 0.2,
            transparent: true,
            opacity: 0.6
        }});
        
        // Group to hold current frame
        const proteinGroup = new THREE.Group();
        scene.add(proteinGroup);
        
        // Background particles
        const particlesGeometry = new THREE.BufferGeometry();
        const particlesCount = 1000;
        const posArray = new Float32Array(particlesCount * 3);
        
        for(let i=0; i<particlesCount * 3; i++) {{
            posArray[i] = (Math.random() - 0.5) * 100;
        }}
        particlesGeometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
        const particlesMaterial = new THREE.PointsMaterial({{
            size: 0.2,
            color: 0x4facfe,
            transparent: true,
            opacity: 0.4,
            blending: THREE.AdditiveBlending
        }});
        const particlesMesh = new THREE.Points(particlesGeometry, particlesMaterial);
        scene.add(particlesMesh);
        
        // Animation State
        let currentFrame = 0;
        let isAnimating = true;
        let lastTime = 0;
        const frameRate = 1000 / 30; // 30 FPS
        
        // Build protein meshes
        let atoms = [];
        let bonds = [];
        
        function initProteinMeshes() {{
            // Clear existing
            while(proteinGroup.children.length > 0){{ 
                proteinGroup.remove(proteinGroup.children[0]); 
            }}
            atoms = [];
            bonds = [];
            
            const numAtoms = trajectory[0].length;
            
            // Create spheres
            for(let i=0; i<numAtoms; i++) {{
                const mesh = new THREE.Mesh(atomGeometry, atomMaterial);
                proteinGroup.add(mesh);
                atoms.push(mesh);
            }}
            
            // Create cylinders for bonds
            for(let i=0; i<numAtoms-1; i++) {{
                const cylinder = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 1, 16), bondMaterial);
                proteinGroup.add(cylinder);
                bonds.push(cylinder);
            }}
        }}
        
        function updateProteinFrame(frameIdx) {{
            const coords = trajectory[frameIdx];
            if(!coords) return;
            
            // Update atom positions
            for(let i=0; i<coords.length; i++) {{
                atoms[i].position.set(coords[i][0], coords[i][1], coords[i][2]);
            }}
            
            // Update bond positions and rotations
            for(let i=0; i<coords.length-1; i++) {{
                const start = new THREE.Vector3(coords[i][0], coords[i][1], coords[i][2]);
                const end = new THREE.Vector3(coords[i+1][0], coords[i+1][1], coords[i+1][2]);
                
                const distance = start.distanceTo(end);
                bonds[i].scale.set(1, distance, 1);
                
                const position = start.clone().lerp(end, 0.5);
                bonds[i].position.copy(position);
                
                bonds[i].quaternion.setFromUnitVectors(
                    new THREE.Vector3(0, 1, 0),
                    end.clone().sub(start).normalize()
                );
            }}
            
            // Update UI
            document.getElementById('step-val').innerText = frameIdx * 50;
            // Interpolate energy visually (fake curve for effect, we only have final)
            if(frameIdx === trajectory.length - 1) {{
                document.getElementById('energy-val').innerText = finalEnergy.toFixed(2);
                document.getElementById('energy-val').style.color = '#00ff88';
            }} else {{
                const progress = frameIdx / trajectory.length;
                const fakeE = 2000 - (2000 - finalEnergy) * Math.pow(progress, 0.5);
                document.getElementById('energy-val').innerText = fakeE.toFixed(1);
                document.getElementById('energy-val').style.color = '#4facfe';
            }}
        }}
        
        // Init
        initProteinMeshes();
        
        // Loop
        function animate(time) {{
            requestAnimationFrame(animate);
            
            controls.update();
            
            // Rotate background particles slowly
            particlesMesh.rotation.y = time * 0.0001;
            particlesMesh.rotation.x = time * 0.00005;
            
            // Update fold animation
            if(isAnimating && time - lastTime > frameRate) {{
                lastTime = time;
                updateProteinFrame(currentFrame);
                
                currentFrame++;
                if(currentFrame >= trajectory.length) {{
                    currentFrame = trajectory.length - 1;
                    isAnimating = false; // Stop at end
                }}
            }}
            
            renderer.render(scene, camera);
        }}
        
        animate(0);
        
        // Window Resize
        window.addEventListener('resize', () => {{
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }});
        
        // Buttons
        document.getElementById('btn-replay').addEventListener('click', () => {{
            currentFrame = 0;
            isAnimating = true;
            document.getElementById('energy-val').style.color = '#4facfe';
        }});
        
        document.getElementById('btn-auto').addEventListener('click', () => {{
            controls.autoRotate = !controls.autoRotate;
            document.getElementById('btn-auto').style.background = controls.autoRotate ? 'rgba(79, 172, 254, 0.2)' : 'rgba(79, 172, 254, 0.1)';
        }});
    </script>
</body>
</html>
"""
    
    with open(output_path, "w") as f:
        f.write(html)
    return output_path


def _parse_pdb_ca(pdb_path: Path) -> np.ndarray:
    coords = []
    with pdb_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("ATOM") and " CA " in line:
                coords.append([
                    float(line[30:38]),
                    float(line[38:46]),
                    float(line[46:54]),
                ])
    if not coords:
        raise ValueError(f"No CA atoms found in {pdb_path}")
    arr = np.array(coords, dtype=float)
    return arr - arr.mean(axis=0, keepdims=True)


def _morph_trajectory(final_xyz: np.ndarray, frames: int = 90) -> list:
    n = final_xyz.shape[0]
    start = np.zeros_like(final_xyz)
    start[:, 0] = np.arange(n, dtype=float) * 3.8
    start -= start.mean(axis=0, keepdims=True)
    out = []
    for k in range(frames):
        t = k / max(1, frames - 1)
        smooth = t * t * (3.0 - 2.0 * t)
        xyz = (1.0 - smooth) * start + smooth * final_xyz
        out.append(xyz.tolist())
    return out


def run_c55m_george_batch(limit: int = 0, beam: int = 512) -> dict:
    from System.sifta_hp_lattice_folder import DEFAULT_PROTEIN_PANEL
    from System.sifta_protein_folding_broker import FoldingJob, ProteinFoldingBroker

    os.environ["SIFTA_HP_LATTICE_BEAM"] = str(int(beam))
    out_dir = _REPO / ".sifta_state" / "protein_folds"
    out_dir.mkdir(parents=True, exist_ok=True)
    broker = ProteinFoldingBroker()
    panel = DEFAULT_PROTEIN_PANEL[:limit] if limit and limit > 0 else DEFAULT_PROTEIN_PANEL
    folds = []
    for name, seq in panel:
        meta = broker.run(
            FoldingJob(
                sequence=seq,
                name=f"C55M + George :: {name}",
                engine="c55m_hp_lattice",
                out_dir=str(out_dir),
            )
        )
        folds.append(meta)

    summary = {
        "title": "C55M + George Protein Fold Colosseum",
        "engine": "c55m_hp_lattice",
        "beam_width": int(beam),
        "fold_count": len(folds),
        "folds": folds,
    }
    summary_path = out_dir / "c55m_george_batch_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SIFTA protein folding visualizer")
    parser.add_argument("sequence", nargs="?", default="ACFLIVGPGKTYL")
    parser.add_argument("--engine", default="c55m_hp_lattice",
                        choices=["toy", "c55m_hp_lattice"])
    parser.add_argument("--beam", type=int, default=1024)
    parser.add_argument("--batch", action="store_true",
                        help="Fold the default C55M + George protein panel first.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit batch fold count; 0 means all defaults.")
    args = parser.parse_args()

    print("SIFTA Protein Folding Visualizer")

    if args.batch:
        summary = run_c55m_george_batch(limit=args.limit, beam=args.beam)
        print(f"Batch folded {summary['fold_count']} proteins")
        print(f"Summary: {summary['summary_path']}")
        # Show the lowest-energy fold after the batch finishes.
        best = min(summary["folds"], key=lambda row: row.get("energy", 0))
        seq = best["sequence"]
        final_e = float(best["energy"])
        pdb_path = Path(best["pdb_path"])
        trajectory = _morph_trajectory(_parse_pdb_ca(pdb_path))
        engine_label = "c55m_hp_lattice_batch_best"
    elif args.engine == "toy":
        seq = args.sequence.upper()
        print(f"Folding sequence: {seq} (Length: {len(seq)})")
        print("Running Monte Carlo simulation...")
        best_xyz, final_e, trajectory = fold(seq, steps=8000, temp=1.2, save_trajectory=True)
        print(f"Folding complete. Final energy: {final_e:.2f}")
        engine_label = "toy_CA_backbone_monte_carlo"
    else:
        from System.sifta_protein_folding_broker import FoldingJob, ProteinFoldingBroker

        seq = args.sequence.upper()
        os.environ["SIFTA_HP_LATTICE_BEAM"] = str(int(args.beam))
        print(f"Folding sequence: {seq} (Length: {len(seq)})")
        print(f"Running C55M + George HP lattice beam search (beam={args.beam})...")
        broker = ProteinFoldingBroker()
        meta = broker.run(
            FoldingJob(
                sequence=seq,
                name="C55M + George co-signed fold",
                engine="c55m_hp_lattice",
            )
        )
        final_e = float(meta["energy"])
        trajectory = _morph_trajectory(_parse_pdb_ca(Path(meta["pdb_path"])))
        print(f"Folding complete. Energy: {final_e:.2f}")
        print(f"PDB: {meta['pdb_path']}")
        engine_label = "c55m_hp_lattice_beam_search"
    
    # Save widget HTML
    html_path = _REPO / ".sifta_state" / "protein_viewer.html"
    html_path.parent.mkdir(exist_ok=True)
    
    build_html_viewer(
        seq,
        trajectory,
        final_e,
        html_path,
        title="C55M + George Protein Fold Colosseum",
        event_label="Event 80: HP Lattice Batch Folder",
        engine_label=engine_label,
        signature_line="Co-signed: C55M-DR-CODEX + George Anton",
    )
    
    print(f"Opening visualizer: {html_path}")
    webbrowser.open("file://" + str(html_path))
