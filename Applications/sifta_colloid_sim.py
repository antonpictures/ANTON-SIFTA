#!/usr/bin/env python3
"""
sifta_colloid_sim.py — The Filmmaker's Cut
===========================================
SIFTA × SwarmRL Visual Simulation

Visualizes SIFTA agents as physical colloids navigating a live pheromone
gradient field — the same mathematical framework used by the German SwarmRL
lab to study active-matter microrobotics in colloidal fluids.

No EspressoMD required. No JAX. Pure numpy + matplotlib animation.

Each live SIFTA agent (from physical_registry.json) becomes a colloid.
The consensus_field() becomes the chemical gradient.
The colloids drift toward the fossil attractor without central coordination.

When field_is_stable() fires, all colloids lock onto the gold attractor.
That is the Strogatz firefly sync moment — rendered.

Usage:
    python3 sifta_colloid_sim.py           # Live mode (reads real Swarm state)
    python3 sifta_colloid_sim.py --demo    # Demo mode (seeds synthetic data)
"""

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np

# Matplotlib is imported inside build_renderer() so --max-frames batch mode can run
# without a GUI stack (stress harness / CI).

# SIFTA kernel
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(_REPO))
if str(_REPO / "System") not in sys.path:
    sys.path.insert(0, str(_REPO / "System"))
from scar_kernel import Kernel, consensus_field, field_is_stable, content_addressed_id

try:
    from sim_lab_theme import LAB_ACCENT, LAB_BG, LAB_TEXT, apply_matplotlib_lab_style
except ImportError:
    apply_matplotlib_lab_style = None  # type: ignore
    LAB_BG = "#050508"
    LAB_TEXT = "#c0caf5"
    LAB_ACCENT = "#c084fc"

# ─────────────────────────────────────────────────────────────────────────────
# Color Palette (Filmmaker's Edit)
# ─────────────────────────────────────────────────────────────────────────────
BG_COLOR       = "#050508"       # Deep void
GRID_COLOR     = "#0d0d1a"       # Subtle grid
AGENT_COLORS   = {               # One color per agent type
    "M5QUEEN":    "#00ffcc",     # Teal — main kernel
    "M1THER":     "#c084fc",     # Violet — legacy node
    "MIQUEEN":    "#f472b6",     # Pink
    "REPAIR-DRONE": "#fbbf24",   # Amber
    "DEFAULT":    "#60a5fa",     # Blue
}
FOSSIL_COLOR   = "#fde68a"       # Gold — fossilized attractor
CONTESTED_COLOR = "#ff0055"      # Crimson — contested zone
PHEROMONE_COLOR = "#1e3a5f"      # Deep blue — pheromone wash

# ─────────────────────────────────────────────────────────────────────────────
# Colloid Particle
# ─────────────────────────────────────────────────────────────────────────────

class SIFTAColloid:
    """
    A SIFTA agent rendered as a physical colloid particle.
    Moves via Euler-step physics toward the pheromone attractor.
    """

    def __init__(self, bound_id: str, x: float, y: float, color: str):
        self.bound_id = bound_id
        # Extract readable name from bound_id (e.g., "M5QUEEN@7433@mac.lan#...")
        self.label = bound_id.split("@")[0] if "@" in bound_id else bound_id

        self.x = x
        self.y = y
        self.vx = random.uniform(-0.01, 0.01)
        self.vy = random.uniform(-0.01, 0.01)
        self.color = color
        self.trail_x = [x]
        self.trail_y = [y]
        self.max_trail = 40
        self.pheromone = 0.0  # Current field strength sensed by this colloid

    def step(self, attractor_x: float, attractor_y: float,
             field_strength: float, is_stable: bool, dt: float = 0.016):
        """
        Euler-step physics update.

        In stable fields: strong attraction toward attractor (convergence).
        In evolving fields: Brownian exploration with weak drift.
        """
        dx = attractor_x - self.x
        dy = attractor_y - self.y
        dist = math.hypot(dx, dy) + 1e-6

        if is_stable:
            # Convergence mode: strong directional pull
            force = 0.8 * field_strength
            noise_scale = 0.002
        else:
            # Exploration mode: weak drift + Brownian noise
            force = 0.15 * field_strength
            noise_scale = 0.015

        # Directed force toward attractor
        self.vx += force * (dx / dist) * dt
        self.vy += force * (dy / dist) * dt

        # Brownian noise (biological volatility)
        self.vx += random.gauss(0, noise_scale)
        self.vy += random.gauss(0, noise_scale)

        # Damping (fluid resistance)
        damping = 0.92 if is_stable else 0.88
        self.vx *= damping
        self.vy *= damping

        self.x += self.vx
        self.y += self.vy

        # Boundary reflection
        if self.x < 0.02:
            self.x = 0.02; self.vx *= -0.5
        if self.x > 0.98:
            self.x = 0.98; self.vx *= -0.5
        if self.y < 0.02:
            self.y = 0.02; self.vy *= -0.5
        if self.y > 0.98:
            self.y = 0.98; self.vy *= -0.5

        # Trail
        self.trail_x.append(self.x)
        self.trail_y.append(self.y)
        if len(self.trail_x) > self.max_trail:
            self.trail_x.pop(0)
            self.trail_y.pop(0)


# ─────────────────────────────────────────────────────────────────────────────
# Simulation State
# ─────────────────────────────────────────────────────────────────────────────

class SIFTAColloidSimulation:

    REGISTRY_PATH = Path(".sifta_state/physical_registry.json")
    DEMO_AGENTS = [
        {"bound_id": "M5QUEEN@7433@mac.lan#66d6193e", "biological_name": "M5QUEEN"},
        {"bound_id": "M1THER@9000@mac.lan#0327e3d6",  "biological_name": "M1THER"},
    ]

    def __init__(self, demo_mode: bool = False, target: str = "body_state.py"):
        self.demo_mode = demo_mode
        self.target = target
        self.kernel = Kernel()
        self.colloids: list[SIFTAColloid] = []
        self.attractor_x = 0.5
        self.attractor_y = 0.5
        self.field_strength = 0.0
        self.is_stable = False
        self.field_data = []
        self.frame = 0
        self.synced = False
        self.sync_frame = None
        self.processed_proposals = set()

        self._seed_kernel()
        self._spawn_colloids()

    def _seed_kernel(self):
        """Seed the kernel with proposals to generate a live field."""
        if self.demo_mode:
            # Seed with synthetic proposals to demonstrate the gradient
            self.kernel.propose(self.target, "fix_import_json")
            self.kernel.propose(self.target, "fix_import_json")   # reinforcement
            self.kernel.propose(self.target, "add_type_hints")
            self.kernel.propose(self.target, "add_type_hints")
            self.kernel.propose(self.target, "add_type_hints")    # dominant trail
            self.kernel.propose(self.target, "refactor_class")
        else:
            # Real mode: check if existing scars exist for this target
            # This integrates with actual running Swarm state
            pass

    def _spawn_colloids(self):
        """Create colloids from physical_registry.json or demo agents."""
        if not self.demo_mode and self.REGISTRY_PATH.exists():
            try:
                registry = json.loads(self.REGISTRY_PATH.read_text())
                agents = list(registry.values())
                if not agents:
                    agents = self.DEMO_AGENTS
            except Exception:
                agents = self.DEMO_AGENTS
        else:
            agents = self.DEMO_AGENTS

        # Scatter initial positions in unit square
        positions = [(0.2, 0.3), (0.7, 0.6), (0.15, 0.75),
                     (0.8, 0.2), (0.5, 0.85), (0.6, 0.1)]

        for i, agent in enumerate(agents[:6]):
            bio = agent.get("biological_name", agent.get("bound_id", "AGENT"))
            color = AGENT_COLORS.get(bio, AGENT_COLORS["DEFAULT"])
            x, y = positions[i % len(positions)]
            x += random.uniform(-0.05, 0.05)
            y += random.uniform(-0.05, 0.05)
            self.colloids.append(
                SIFTAColloid(agent.get("bound_id", bio), x, y, color)
            )

    def tick(self):
        """One simulation step: refresh field, compute attractor, step colloids."""
        self.frame += 1

        # Real-time IPC: Poll for new inference outputs
        proposals_dir = Path("bureau_of_identity/proposals")
        if proposals_dir.exists():
            for p in proposals_dir.glob("*.scar"):
                if p.name not in self.processed_proposals:
                    try:
                        content = p.read_text().strip()
                        if content:
                            self.kernel.propose(self.target, content)
                            self.processed_proposals.add(p.name)
                    except Exception:
                        pass

        scars = [
            s for s in self.kernel.scars.values()
            if s.target == self.target and s.state in ("PROPOSED", "LOCKED")
        ]

        if scars:
            self.field_data = consensus_field(scars)
            self.is_stable = field_is_stable(self.field_data)

            if self.field_data:
                self.field_strength = self.field_data[0][1]
                # Map dominant trail hash to a deterministic 2D position
                top_scar = self.field_data[0][0]
                h = int(top_scar.scar_id[:8], 16)
                self.attractor_x = (h % 1000) / 1000.0 * 0.6 + 0.2
                h2 = int(top_scar.scar_id[8:16], 16)
                self.attractor_y = (h2 % 1000) / 1000.0 * 0.6 + 0.2

        if self.is_stable and not self.synced:
            self.synced = True
            self.sync_frame = self.frame

        for colloid in self.colloids:
            colloid.step(
                self.attractor_x, self.attractor_y,
                self.field_strength, self.is_stable
            )
            colloid.pheromone = self.field_strength


# ─────────────────────────────────────────────────────────────────────────────
# Renderer
# ─────────────────────────────────────────────────────────────────────────────

def build_renderer(sim: SIFTAColloidSimulation):
    import matplotlib

    try:
        matplotlib.use("MacOSX")
    except Exception:
        matplotlib.use("Agg")
    import matplotlib.animation as animation
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.patches import Circle

    if apply_matplotlib_lab_style:
        apply_matplotlib_lab_style()
    fig = plt.figure(figsize=(14, 9), facecolor=BG_COLOR)
    fig.canvas.manager.set_window_title("SIFTA × SwarmRL — Cognitive Colloid Simulation")

    # Main physics canvas
    ax = fig.add_axes([0.02, 0.18, 0.68, 0.78])
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#1a1a2e")

    # Info panel
    ax_info = fig.add_axes([0.72, 0.18, 0.26, 0.78])
    ax_info.set_facecolor("#08080f")
    ax_info.set_xticks([])
    ax_info.set_yticks([])
    for spine in ax_info.spines.values():
        spine.set_color("#1a1a2e")

    # Status bar
    ax_status = fig.add_axes([0.02, 0.02, 0.96, 0.12])
    ax_status.set_facecolor("#08080f")
    ax_status.set_xticks([])
    ax_status.set_yticks([])

    # Static title
    ax.text(0.5, 1.03, "COGNITIVE COLLOID — SWARMRL LAB",
            transform=ax.transAxes, color=LAB_ACCENT,
            fontfamily="monospace", fontsize=13, fontweight="bold", ha="center")
    ax.text(0.5, 0.99, f"Target: {sim.target}",
            transform=ax.transAxes, color=LAB_TEXT,
            fontfamily="monospace", fontsize=9, ha="center")

    # Build pheromone heatmap background
    heatmap_data = np.zeros((100, 100))
    # Gaussian halo around attractor
    xs = np.linspace(0, 1, 100)
    ys = np.linspace(0, 1, 100)
    XX, YY = np.meshgrid(xs, ys)

    pheromone_cmap = LinearSegmentedColormap.from_list(
        "sifta_pheromone",
        [(0, BG_COLOR), (0.4, "#0a1628"), (0.7, "#0e2d6e"), (1.0, "#1e3a5f")]
    )
    heatmap = ax.imshow(
        heatmap_data, extent=[0, 1, 0, 1],
        origin="lower", cmap=pheromone_cmap,
        vmin=0, vmax=1, alpha=0.8, zorder=1
    )

    # Attractor point (gold star)
    attractor_dot, = ax.plot(
        [sim.attractor_x], [sim.attractor_y],
        marker="*", color=FOSSIL_COLOR, markersize=22, zorder=10,
        markeredgecolor="#ffffff", markeredgewidth=0.5
    )

    # Contested ring
    contested_ring = Circle(
        (sim.attractor_x, sim.attractor_y), 0.08,
        fill=False, color=CONTESTED_COLOR, linewidth=1.5,
        linestyle="--", alpha=0.0, zorder=9
    )
    ax.add_patch(contested_ring)

    # Sync ring
    sync_ring = Circle(
        (sim.attractor_x, sim.attractor_y), 0.0,
        fill=False, color=FOSSIL_COLOR, linewidth=2.0, alpha=0.0, zorder=11
    )
    ax.add_patch(sync_ring)

    # Colloid artists
    colloid_dots = []
    trail_lines = []
    labels = []

    for c in sim.colloids:
        dot, = ax.plot([c.x], [c.y], "o", color=c.color,
                       markersize=10, zorder=8,
                       markeredgecolor="#ffffff", markeredgewidth=0.8)
        trail, = ax.plot(c.trail_x, c.trail_y,
                         "-", color=c.color, alpha=0.3, linewidth=1.2, zorder=6)
        lbl = ax.text(c.x, c.y + 0.04, c.label, color=c.color,
                      fontfamily="monospace", fontsize=7, ha="center", zorder=12)
        colloid_dots.append(dot)
        trail_lines.append(trail)
        labels.append(lbl)

    # HUD text objects
    info_texts = []
    for row in range(20):
        t = ax_info.text(
            0.05, 0.97 - row * 0.048, "",
            transform=ax_info.transAxes, color="#94a3b8",
            fontfamily="monospace", fontsize=7.5, va="top"
        )
        info_texts.append(t)

    status_text = ax_status.text(
        0.5, 0.55, "INITIALIZING SIFTA COLLOID ENGINE...",
        transform=ax_status.transAxes, color="#fde68a",
        fontfamily="monospace", fontsize=10, ha="center", va="center",
        fontweight="bold"
    )

    def update(frame_num):
        sim.tick()

        # Update pheromone heatmap
        cx, cy = sim.attractor_x, sim.attractor_y
        dist = np.sqrt((XX - cx) ** 2 + (YY - cy) ** 2)
        sigma = 0.18 + (1 - sim.field_strength) * 0.12
        heatmap_data = sim.field_strength * np.exp(-dist ** 2 / (2 * sigma ** 2))
        heatmap.set_data(heatmap_data)

        # Update attractor
        attractor_dot.set_data([sim.attractor_x], [sim.attractor_y])

        # Contested ring visibility
        if not sim.is_stable and sim.field_data and len(sim.field_data) > 1:
            score_gap = sim.field_data[0][1] - sim.field_data[1][1]
            contested_ring.set_center((sim.attractor_x, sim.attractor_y))
            contested_ring.set_alpha(max(0, 0.7 - score_gap * 3))
        else:
            contested_ring.set_alpha(0)

        # Sync ring animation
        if sim.synced and sim.sync_frame:
            frames_since_sync = sim.frame - sim.sync_frame
            if frames_since_sync < 60:
                r = (frames_since_sync / 60.0) * 0.35
                alpha = max(0, 1.0 - frames_since_sync / 60.0)
                sync_ring.set_center((sim.attractor_x, sim.attractor_y))
                sync_ring.set_radius(r)
                sync_ring.set_alpha(alpha)
            else:
                sync_ring.set_alpha(0)

        # Update colloids
        for i, c in enumerate(sim.colloids):
            colloid_dots[i].set_data([c.x], [c.y])
            trail_lines[i].set_data(c.trail_x, c.trail_y)
            labels[i].set_position((c.x, c.y + 0.04))

        # Info panel
        row = 0
        def info(text, color="#94a3b8"):
            nonlocal row
            if row < len(info_texts):
                info_texts[row].set_text(text)
                info_texts[row].set_color(color)
                row += 1

        info("══ SIFTA FIELD STATE ══", "#c084fc")
        info("")
        mode_color = "#22c55e" if sim.is_stable else "#f59e0b"
        mode_label = "CONVERGE ✓" if sim.is_stable else "EXPLORE ◌"
        info(f"Mode: {mode_label}", mode_color)
        info(f"Field: {sim.field_strength:.3f}", "#60a5fa")
        info(f"Frame: {sim.frame}", "#60a5fa")
        info("")

        info("══ PHEROMONE GRADIENT ══", "#c084fc")
        info("")
        for rank, (scar, score) in enumerate(sim.field_data[:5]):
            bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
            color = FOSSIL_COLOR if rank == 0 else "#94a3b8"
            info(f"#{rank+1} {bar} {score:.3f}", color)
            short = scar.content[:16] + ("…" if len(scar.content) > 16 else "")
            info(f"   ↳ {short}", "#475569")
        info("")
        info("══ ACTIVE AGENTS ══", "#c084fc")
        info("")
        for c in sim.colloids:
            bar = "█" * int(c.pheromone * 8) + "░" * (8 - int(c.pheromone * 8))
            info(f"{c.label[:10]:<10} {bar}", c.color)

        # Clear unused info rows
        for i in range(row, len(info_texts)):
            info_texts[i].set_text("")

        # Status bar
        if sim.synced:
            st = f"🌊  STROGATZ SYNCHRONIZATION ACHIEVED — Frame {sim.sync_frame}  ·  All colloids locked onto consensus attractor  ·  field_is_stable() = True"
            status_text.set_color(FOSSIL_COLOR)
        elif sim.is_stable:
            st = f"⚡  FIELD STABILIZING  ·  Dominant trail score: {sim.field_strength:.3f}  ·  Colloids converging..."
            status_text.set_color("#22c55e")
        else:
            st = f"◌  EXPLORING  ·  {len(sim.colloids)} colloids navigating pheromone gradient  ·  Field: {sim.field_strength:.3f}  ·  Contested: {'YES' if len(sim.field_data) > 1 else 'NO'}"
            status_text.set_color("#f59e0b")
        status_text.set_text(st)

        return [heatmap, attractor_dot, contested_ring, sync_ring,
                *colloid_dots, *trail_lines, *labels, *info_texts, status_text]

    ani = animation.FuncAnimation(
        fig, update, interval=50, blit=False, cache_frame_data=False
    )

    return fig, ani


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SIFTA Cognitive Colloid Simulation")
    parser.add_argument("--demo", action="store_true",
                        help="Demo mode: seed synthetic data (no live Swarm needed)")
    parser.add_argument("--target", default="body_state.py",
                        help="SIFTA target to visualize (default: body_state.py)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Verify imports and exit without rendering")
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Stress mode: no window — advance physics N ticks (Agg) and exit",
    )
    args = parser.parse_args()

    print("\n[🌊 SIFTA COLLOID SIM] Initializing...")
    print(f"  Target:  {args.target}")
    print(f"  Mode:    {'DEMO' if args.demo else 'LIVE'}")
    print(f"  Physics: Pure numpy (no EspressoMD, no JAX)")
    print()

    sim = SIFTAColloidSimulation(demo_mode=args.demo, target=args.target)

    print(f"[🌊] Spawned {len(sim.colloids)} colloids:")
    for c in sim.colloids:
        print(f"     {c.label:<12} @ ({c.x:.2f}, {c.y:.2f})  color={c.color}")

    print(f"[🌊] Kernel scars: {len(sim.kernel.scars)}")
    print(f"[🌊] Fossils:      {len(sim.kernel.fossils)}")
    print()

    if args.dry_run:
        print("[✅ DRY RUN] All components verified. Exiting.")
        return

    if args.max_frames > 0:
        for _ in range(int(args.max_frames)):
            sim.tick()
        print(f"[🌊 BATCH] frames={args.max_frames} field_stable={sim.is_stable} synced={sim.synced}")
        return

    print("[🌊] Opening filmmaker's window...")
    import matplotlib.pyplot as plt

    fig, ani = build_renderer(sim)
    plt.show()


if __name__ == "__main__":
    main()
