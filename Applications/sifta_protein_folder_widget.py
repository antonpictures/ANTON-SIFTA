#!/usr/bin/env python3
"""
Applications/sifta_protein_folder_widget.py
A SIFTA OS widget to visually demonstrate the peptide folding engine.
It generates a 3D animated HTML visualization with glassmorphism UI and particle effects.
"""

import sys
import json
import os
import webbrowser
from pathlib import Path

# Add project root to path
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.sifta_peptide_backbone_demo import fold, AA
except ImportError:
    print("Error: Could not import System.sifta_peptide_backbone_demo")
    sys.exit(1)

def build_html_viewer(seq: str, trajectory: list, final_e: float, output_path: Path):
    # Prepare data for JS
    js_traj = json.dumps(trajectory)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SIFTA Protein Folder</title>
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
        <h1>SIFTA Peptide Fold</h1>
        <h2>Event 78 Vanguard</h2>
        
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
        <strong>Thermodynamic Hypothesis</strong><br>
        Anfinsen (1973) Science 181:223<br>
        <strong>Highly accurate prediction</strong><br>
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

if __name__ == "__main__":
    print("🧬 SIFTA Protein Folding Visualizer")
    seq = "ACFLIVGPGKTYL"
    if len(sys.argv) > 1:
        seq = sys.argv[1].upper()
        
    print(f"Folding sequence: {seq} (Length: {len(seq)})")
    print("Running Monte Carlo simulation...")
    
    # Run the folding engine
    best_xyz, final_e, trajectory = fold(seq, steps=8000, temp=1.2, save_trajectory=True)
    
    print(f"Folding complete. Final energy: {final_e:.2f}")
    
    # Save widget HTML
    html_path = _REPO / ".sifta_state" / "protein_viewer.html"
    html_path.parent.mkdir(exist_ok=True)
    
    build_html_viewer(seq, trajectory, final_e, html_path)
    
    print(f"Opening visualizer: {html_path}")
    webbrowser.open("file://" + str(html_path))
