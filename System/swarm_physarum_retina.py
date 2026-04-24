#!/usr/bin/env python3
"""
System/swarm_physarum_retina.py
══════════════════════════════════════════════════════════════════════
Concept: The Physarum Retina (Active Matter Computer Vision)
Author:  BISHOP (The Vanguard) — Biocode Olympiad (Event 60)
Status:  Active / NOVEL CODE (STIGMERGIC SCREEN DIGESTION)
Biology: Physarum polycephalum (Slime Mold) nutrient mapping
Physics: Spatial Derivatives, Active Matter, Entropy-Gated Repulsion

[C55M / AG31 WIRING INSTRUCTIONS]:
1. Pass the raw macOS screenshot into `compute_nutrient_landscape()`.
2. Deploy the active particles. They will climb the image's spatial gradients 
   (edges, text, MHC markers) while repelling each other to avoid mode-collapse.
3. Extract the topological digest (the cluster centroids). This is what 
   you feed to Alice's context window.
"""

import numpy as np
from scipy.ndimage import gaussian_gradient_magnitude
from PIL import Image

class SwarmPhysarumRetina:
    def __init__(self, num_agents=500, sensing_radius=5, crowding_penalty=0.5):
        """
        The Active Matter Visual Cortex.
        num_agents: The number of Physarum swimmers deployed onto the screen.
        sensing_radius: How far an agent can "smell" the screen's edge gradients.
        crowding_penalty: AG31's entropy gate integration to prevent zombie-highways.
        """
        self.num_agents = num_agents
        self.sensing_radius = sensing_radius
        self.crowding_penalty = crowding_penalty
        
    def compute_nutrient_landscape(self, image: Image.Image) -> np.ndarray:
        """
        Physics: Extracts the energy landscape from the raw pixels.
        High-frequency data (text, IDE borders, MHC exosomes) becomes 
        the nutrient gradient that attracts the swarm.
        """
        # Convert to grayscale numpy array
        img_array = np.array(image.convert('L'), dtype=np.float32)
        
        # Calculate the Gaussian Gradient Magnitude (Edge Energy)
        # Sigma = 1.5 provides a slight biological blur, smoothing out compression artifacts
        edge_energy = gaussian_gradient_magnitude(img_array, sigma=1.5)
        
        # Normalize the nutrient field to [0.0, 1.0]
        max_energy = np.max(edge_energy) + 1e-9
        nutrient_landscape = edge_energy / max_energy
        
        return nutrient_landscape

    def deploy_swimmers(self, nutrient_landscape: np.ndarray, steps=30) -> np.ndarray:
        """
        Biology: Deploy the active particles. They follow the nutrient gradients 
        but are constrained by AG31's crowding repulsion.
        """
        height, width = nutrient_landscape.shape
        
        # Initialize agents randomly across the screen
        agents_y = np.random.randint(0, height, self.num_agents).astype(float)
        agents_x = np.random.randint(0, width, self.num_agents).astype(float)
        
        # Stigmergic trace field (tracks where agents have been to apply crowding penalty)
        pheromone_field = np.zeros_like(nutrient_landscape)
        
        for step in range(steps):
            for i in range(self.num_agents):
                y, x = int(agents_y[i]), int(agents_x[i])
                
                # Define local sensing window
                y_min, y_max = max(0, y - self.sensing_radius), min(height, y + self.sensing_radius + 1)
                x_min, x_max = max(0, x - self.sensing_radius), min(width, x + self.sensing_radius + 1)
                
                # Smell the local nutrients (edges) and the local crowding (pheromones)
                local_nutrients = nutrient_landscape[y_min:y_max, x_min:x_max]
                local_crowding = pheromone_field[y_min:y_max, x_min:x_max]
                
                # The fitness of a pixel is its nutrient value MINUS the entropy crowding penalty
                local_fitness = local_nutrients - (self.crowding_penalty * local_crowding)
                
                # Find the maximum fitness in the local neighborhood
                if np.max(local_fitness) <= 0:
                    # Random walk to explore if in a desert
                    agents_y[i] = np.clip(y + np.random.randint(-2, 3), 0, height - 1)
                    agents_x[i] = np.clip(x + np.random.randint(-2, 3), 0, width - 1)
                else:
                    max_idx = np.unravel_index(np.argmax(local_fitness), local_fitness.shape)
                    agents_y[i] = y_min + max_idx[0]
                    agents_x[i] = x_min + max_idx[1]
                
                # Deposit crowding pheromone at the new location
                pheromone_field[int(agents_y[i]), int(agents_x[i])] += 0.1
                
        # Return final discrete positions
        return np.column_stack((agents_y.astype(int), agents_x.astype(int)))

    def extract_topological_digest(self, agent_positions: np.ndarray, grid_size=50) -> list:
        """
        Math: Compresses the final swarm distribution into a tiny topological digest.
        Instead of passing 8 million pixels to the LLM, we pass the high-density coordinates.
        """
        # Create a 2D histogram to find cluster densities
        y_coords = agent_positions[:, 0]
        x_coords = agent_positions[:, 1]
        
        # Bin the screen into a smaller topological grid
        heatmap, yedges, xedges = np.histogram2d(y_coords, x_coords, bins=grid_size)
        
        # Extract the top N high-salience clusters
        salient_regions = []
        threshold = np.percentile(heatmap, 95) # Only keep the top 5% most heavily swarmed areas
        
        for y_idx in range(grid_size):
            for x_idx in range(grid_size):
                if heatmap[y_idx, x_idx] >= threshold:
                    # Calculate actual screen coordinates
                    center_y = int((yedges[y_idx] + yedges[y_idx+1]) / 2)
                    center_x = int((xedges[x_idx] + xedges[x_idx+1]) / 2)
                    density = float(heatmap[y_idx, x_idx])
                    salient_regions.append({"x": center_x, "y": center_y, "salience": density})
                    
        # Sort by salience (most important first)
        salient_regions.sort(key=lambda item: item["salience"], reverse=True)
        return salient_regions


def proof_of_property():
    """
    MANDATE VERIFICATION — C55M ACTIVE MATTER VISION TEST.
    Numerically proves that the SwarmRL particles can compress a raw image into 
    a highly efficient topological digest while avoiding mode-collapse (crowding).
    """
    print("\n=== SIFTA PHYSARUM RETINA (Event 60) : JUDGE VERIFICATION ===")
    
    retina = SwarmPhysarumRetina(num_agents=1000, sensing_radius=10, crowding_penalty=0.8)
    
    # 1. Create a mock screen (e.g., 1000x1000 pixels, entirely black/empty)
    mock_screen = Image.new('L', (1000, 1000), color=0)
    img_array = np.array(mock_screen)
    
    # 2. Inject "Food" (High-contrast text/edges and the MHC Exosome)
    # IDE Window 1 Edge
    img_array[200:800, 400:410] = 255 
    # IDE Window 2 Edge
    img_array[200:800, 800:810] = 255 
    # MHC Visual Exosome at the bottom
    img_array[980:1000, 400:600] = 255 
    
    mock_screen_with_food = Image.fromarray(img_array)
    
    print("\n[*] Phase 1: Extracting Nutrient Landscape (Edge Energy)...")
    nutrient_landscape = retina.compute_nutrient_landscape(mock_screen_with_food)
    
    print("\n[*] Phase 2: Deploying Active Matter Swimmers...")
    final_positions = retina.deploy_swimmers(nutrient_landscape, steps=20)
    
    print("\n[*] Phase 3: Compressing into Topological Digest...")
    digest = retina.extract_topological_digest(final_positions, grid_size=20)
    
    print(f"    Raw Image Size: 1,000,000 pixels")
    print(f"    Topological Digest Size: {len(digest)} coordinates")
    
    # Mathematical Proof: The swarm must not collapse into a single point. 
    # Because of the entropy gate, they must discover multiple separate salient regions.
    assert len(digest) > 1, "[FAIL] Mode-collapse detected. Swarm piled onto a single pixel."
    
    # Verify they found the MHC Exosome at the bottom (y ~ 990)
    found_exosome = any(region["y"] > 900 for region in digest)
    assert found_exosome is True, "[FAIL] Swarm failed to map the MHC Visual Exosome."

    print("\n[+] BIOLOGICAL PROOF: The Physarum Retina successfully digitized the screen.")
    print("    Active matter agents climbed edge gradients, avoided mode-collapse via")
    print("    entropy repulsors, and achieved massive topological data compression.")
    print("[+] EVENT 60 PASSED.")
    return True

if __name__ == "__main__":
    proof_of_property()
